"""IFC authoring for the Southgate migration (IfcOpenShell API = Bonsai's authoring core).

Representation policy (evidence based, see geometry/fit.py):
  * proven box / prism / multi-prism  -> native swept solids
        walls  : Bonsai DumbLayer2 layered wall (IfcMaterialLayerSetUsage AXIS2, Axis + Body)
        slabs  : Bonsai DumbLayer3 layered slab (IfcMaterialLayerSetUsage AXIS3)
        members: IfcMaterialProfileSet(Usage) + profile extrusion (end clippings where cut)
        doors/windows: IfcOpenShell parametric door/window types (+ BBIM_Door/BBIM_Window)
        others : extruded area solids
  * repeated identical meshes         -> element type + IfcRepresentationMap (mapped items)
  * anything else                     -> exact source tessellation (IfcPolygonalFaceSet)
"""
from __future__ import annotations

import json
import re
from collections import defaultdict, Counter

import numpy as np
import ifcopenshell
import ifcopenshell.api
import ifcopenshell.api.aggregate
import ifcopenshell.api.context
import ifcopenshell.api.feature
import ifcopenshell.api.geometry
import ifcopenshell.api.material
import ifcopenshell.api.pset
import ifcopenshell.api.root
import ifcopenshell.api.spatial
import ifcopenshell.api.style
import ifcopenshell.api.system
import ifcopenshell.api.type
import ifcopenshell.api.unit
import ifcopenshell.api.project
import ifcopenshell.util.pset
import ifcopenshell.geom

from ..geometry import fit
from ..migration.plan import guid_for

API = ifcopenshell.api
ZUP = np.array([0.0, 0.0, 1.0])
_PSET_LIB = ifcopenshell.util.pset.PsetQto("IFC4")

ASSEMBLY_TYPES = {
    "ROOF": ("IfcRoof", "GABLE_ROOF", None),
    "STAGE": ("IfcElementAssembly", "USERDEFINED", "STAGE_PLATFORM"),
    "NORTH-ENTRANCE-PORTAL": ("IfcElementAssembly", "USERDEFINED", "ENTRANCE_PORTAL_AND_CANOPY"),
    "SPIRAL-STAIR": ("IfcStair", "SPIRAL_STAIR", None),
}


def assembly_class(key):
    if key in ASSEMBLY_TYPES:
        return ASSEMBLY_TYPES[key]
    if key.startswith("TRUSS-"):
        return ("IfcElementAssembly", "TRUSS", None)
    if key.endswith("CURTAIN-WALL"):
        return ("IfcCurtainWall", "NOTDEFINED", None)
    if key.startswith("STAIR-"):
        return ("IfcStair", "NOTDEFINED", None)
    if key.startswith("ACOUSTIC-RAFT"):
        return ("IfcElementAssembly", "USERDEFINED", "SUSPENDED_ACOUSTIC_RAFT")
    if key.startswith("WC-CUBICLES"):
        return ("IfcElementAssembly", "USERDEFINED", "WC_CUBICLE_SYSTEM")
    return ("IfcElementAssembly", "USERDEFINED", key)


SYSTEMS = {
    "RAINWATER": ("RAINWATER", None, "Roof rainwater drainage (gutters, outlets, downpipes, gratings)"),
    "VENTILATION": ("VENTILATION", None, "Hybrid ventilation proposal VENT-IEQ-20261106 (PRELIMINARY)"),
    "EXHAUST": ("EXHAUST", None, "Restroom extract ventilation (RR-V2 concept)"),
    "PLUMBING": ("USERDEFINED", "PLUMBING_CW_SOIL_WASTE", "Restroom cold water, soil and waste (RR-V2 concept)"),
    "SANITARY": ("USERDEFINED", "SANITARY_FITMENTS", "Restroom sanitary fitments (RR-V2)"),
    "LIGHTING": ("LIGHTING", None, "Luminaires and lighting battens (representative)"),
    "ELECTROACOUSTIC": ("ELECTROACOUSTIC", None, "Loudspeaker arrays / delays and projection screens (allowances)"),
    "ELECTRICAL": ("ELECTRICAL", None, "Stage floor boxes (allowances)"),
}


def _dir(v):
    v = np.asarray(v, dtype=float)
    return v / np.linalg.norm(v)


class Frame:
    """Right-handed local frame (origin O, axes X, Y, Z as unit vectors)."""

    def __init__(self, O, X, Z):
        self.O = np.asarray(O, float)
        self.Z = _dir(Z)
        X = np.asarray(X, float)
        X = X - np.dot(X, self.Z) * self.Z
        self.X = _dir(X)
        self.Y = np.cross(self.Z, self.X)
        self.R = np.stack([self.X, self.Y, self.Z], axis=1)

    def to_local(self, p):
        return (np.asarray(p, float) - self.O) @ self.R

    def dir_local(self, v):
        return np.asarray(v, float) @ self.R

    @staticmethod
    def world():
        return Frame([0, 0, 0], [1, 0, 0], [0, 0, 1])


def horizontal_x_for(z):
    z = _dir(z)
    if abs(z[2]) > 0.999:
        return np.array([1.0, 0, 0])
    x = np.cross(ZUP, z)
    return _dir(x)


class Builder:
    def __init__(self, cfg, mat_cfg, inventory, cache, plan, run_id):
        self.cfg, self.mat_cfg, self.inv, self.cache, self.plan = cfg, mat_cfg, inventory, cache, plan
        self.objects = {o["name"]: o for o in inventory["objects"]}
        self.rows = {r["source"]: r for r in plan["rows"]}
        self.run_id = run_id
        self.ns = cfg["project"]["guid_namespace"]
        self.f = None
        self.el_by_sid = {}           # stable id -> ifc entity
        self.frames = {}              # stable id -> Frame
        self.info = {}                # stable id -> build info (representation kind etc.)
        self.materials, self.styles = {}, {}
        self.types = {}
        self.profiles = {}
        self.mapped_types = {}
        self.log = []
        self.mesh_users = Counter()
        for el in plan["elements"]:
            if len(el["members"]) == 1:
                r = self.rows[el["members"][0]]
                if r.get("_shared"):
                    self.mesh_users[(el["ifc_class"], r["_mesh_key"])] += 1

    # ------------------------------------------------------------------ project
    def g(self, key):
        return guid_for(key, self.ns)

    def create_project(self):
        f = self.f = API.project.create_file(version=self.cfg["project"]["schema"])
        p = API.root.create_entity(f, "IfcProject", name=self.cfg["project"]["name"])
        p.GlobalId = self.g("PROJECT")
        p.LongName = self.cfg["project"]["long_name"]
        p.Phase = self.cfg["project"]["design_stage"]
        API.unit.assign_unit(f, units=[f.createIfcSIUnit(None, "LENGTHUNIT", None, "METRE"),
                                       f.createIfcSIUnit(None, "AREAUNIT", None, "SQUARE_METRE"),
                                       f.createIfcSIUnit(None, "VOLUMEUNIT", None, "CUBIC_METRE"),
                                       f.createIfcSIUnit(None, "PLANEANGLEUNIT", None, "RADIAN"),
                                       f.createIfcSIUnit(None, "MASSUNIT", "KILO", "GRAM")])
        model = API.context.add_context(f, "Model")
        self.body = API.context.add_context(f, "Model", "Body", "MODEL_VIEW", parent=model)
        self.axis = API.context.add_context(f, "Model", "Axis", "GRAPH_VIEW", parent=model)
        API.context.add_context(f, "Model", "Box", "MODEL_VIEW", parent=model)
        plan = API.context.add_context(f, "Plan")
        self.plan_axis = API.context.add_context(f, "Plan", "Axis", "GRAPH_VIEW", parent=plan)
        API.context.add_context(f, "Plan", "Body", "PLAN_VIEW", parent=plan)
        site = API.root.create_entity(f, "IfcSite", name="Southgate Worship Center - Site (Option A)")
        site.GlobalId = self.g("SITE")
        site.Description = "Site placement = source Blender world origin. Geolocation / true north UNVERIFIED."
        bld = API.root.create_entity(f, "IfcBuilding", name="Southgate Worship Center - Main Auditorium")
        bld.GlobalId = self.g("BUILDING")
        bld.Description = self.cfg["boundary"]["description"].strip()
        API.aggregate.assign_object(f, products=[site], relating_object=p)
        API.aggregate.assign_object(f, products=[bld], relating_object=site)
        site.ObjectPlacement = self.lp(None, [0, 0, 0])
        bld.ObjectPlacement = self.lp(site.ObjectPlacement, [0, 0, 0])
        self.site, self.building, self.project = site, bld, p
        self.storeys = {}
        for s in self.cfg["storeys"]:
            st = API.root.create_entity(f, "IfcBuildingStorey", name=s["name"])
            st.GlobalId = self.g("STOREY-" + s["code"])
            st.Elevation = s["elevation"]
            st.Description = "Elevation evidence: " + s["evidence"]
            st.ObjectPlacement = self.lp(bld.ObjectPlacement, [0, 0, s["elevation"]])
            API.aggregate.assign_object(f, products=[st], relating_object=bld)
            self.storeys[s["code"]] = (st, s["elevation"])
        pset = API.pset.add_pset(f, product=p, name="SOUTHGATE_ProjectInformation")
        API.pset.edit_pset(f, pset=pset, properties={
            "DesignStage": self.cfg["project"]["design_stage"],
            "SourceSnapshot": self.cfg["source"]["snapshot"],
            "SourceSnapshotSHA256": self.cfg["source"]["snapshot_sha256"],
            "SourceGeometryFingerprint": self.cfg["source"]["geometry_fingerprint"],
            "CoordinateTransform": "identity (Blender world metres = IFC project coordinates)",
            "TrueNorth": self.cfg["coordinates"]["true_north"],
            "Geolocation": self.cfg["coordinates"]["geolocation"],
            "MigrationRun": self.run_id,
            "AuthoringTool": f"IfcOpenShell {ifcopenshell.version} API (Bonsai 0.9.0-post1 authoring core)"})
        return f

    # ------------------------------------------------------------------ primitives
    def a2p(self, origin, z=(0, 0, 1), x=(1, 0, 0)):
        f = self.f
        return f.createIfcAxis2Placement3D(f.createIfcCartesianPoint([float(c) for c in origin]),
                                           f.createIfcDirection([float(c) for c in _dir(z)]),
                                           f.createIfcDirection([float(c) for c in _dir(x)]))

    def lp(self, rel, origin, z=(0, 0, 1), x=(1, 0, 0)):
        return self.f.createIfcLocalPlacement(rel, self.a2p(origin, z, x))

    def place(self, el, frame: Frame, storey_code):
        st, elev = self.storeys[storey_code]
        el.ObjectPlacement = self.lp(st.ObjectPlacement, frame.O - [0, 0, elev], frame.Z, frame.X)

    def material(self, name):
        name = name or "UNSPECIFIED"
        if name in self.materials:
            return self.materials[name]
        rule = None
        low = name.lower()
        for r in self.mat_cfg["keyword_rules"]:
            if any(k in low for k in r["kw"]):
                rule = r
                break
        rule = rule or self.mat_cfg["default"]
        m = API.material.add_material(self.f, name=name, category=rule["category"])
        m.Description = f"Source Blender material; spec status {rule['spec_status']}" + (f"; {rule['note']}" if rule.get("note") else "")
        if rule.get("density"):
            ps = API.pset.add_pset(self.f, product=m, name="Pset_MaterialCommon")
            API.pset.edit_pset(self.f, pset=ps, properties={"MassDensity": float(rule["density"])})
        ps2 = API.pset.add_pset(self.f, product=m, name="SOUTHGATE_MaterialStatus")
        API.pset.edit_pset(self.f, pset=ps2, properties={"SpecificationStatus": rule["spec_status"],
                                                         "DensityBasis": "nominal (config/materials.yaml) - indicative only"})
        rgba = list(self.cache["materials"].get(name, {}).get("rgba", [0.7, 0.7, 0.7, 1]))
        # Blender colours are scene-linear; IfcColourRgb is interpreted as sRGB by viewers (incl. Bonsai)
        rgba[:3] = [linear_to_srgb(c) for c in rgba[:3]]
        st = API.style.add_style(self.f, name=name)
        API.style.add_surface_style(self.f, style=st, ifc_class="IfcSurfaceStyleShading", attributes={
            "SurfaceColour": {"Name": None, "Red": float(rgba[0]), "Green": float(rgba[1]), "Blue": float(rgba[2])},
            "Transparency": float(max(0.0, min(0.9, 1 - rgba[3])))})
        API.style.assign_material_style(self.f, material=m, style=st, context=self.body)
        self.materials[name] = m
        self.styles[name] = st
        return m

    def member_material_name(self, members):
        c = Counter()
        for n in members:
            o = self.objects[n]
            c[(o["materials"] or ["UNSPECIFIED"])[0]] += 1
        return c.most_common(1)[0][0]

    def rep(self, ident, rtype, items, ctx=None):
        return self.f.createIfcShapeRepresentation(ctx or self.body, ident, rtype, items)

    def arb_profile(self, pts2, holes2=None, name=None):
        f = self.f
        def curve(pts):
            pl = [list(map(float, p)) for p in pts] + [list(map(float, pts[0]))]
            return f.createIfcIndexedPolyCurve(f.createIfcCartesianPointList2D(pl), None, False)
        if holes2:
            return f.createIfcArbitraryProfileDefWithVoids("AREA", name, curve(pts2), [curve(h) for h in holes2])
        return f.createIfcArbitraryClosedProfileDef("AREA", name, curve(pts2))

    def rect_profile(self, xd, yd, cx=0.0, cy=0.0, name=None):
        f = self.f
        pos = f.createIfcAxis2Placement2D(f.createIfcCartesianPoint([float(cx), float(cy)]), None)
        return f.createIfcRectangleProfileDef("AREA", name, pos, float(xd), float(yd))

    def extrusion(self, profile, pos_origin, pos_z, pos_x, depth, ext_dir=(0, 0, 1)):
        return self.f.createIfcExtrudedAreaSolid(profile, self.a2p(pos_origin, pos_z, pos_x),
                                                 self.f.createIfcDirection([float(c) for c in ext_dir]), float(depth))

    def clip(self, solid, point_local, normal_local):
        f = self.f
        n = _dir(normal_local)
        xh = horizontal_x_for(n) if abs(n[2]) < 0.999 else np.array([1.0, 0, 0])
        plane = f.createIfcPlane(self.a2p(point_local, n, xh))
        return f.createIfcBooleanClippingResult("DIFFERENCE", solid, f.createIfcHalfSpaceSolid(plane, False))

    def tess(self, verts_local, faces):
        f = self.f
        pts = f.createIfcCartesianPointList3D([[float(c) for c in v] for v in verts_local])
        fs = [f.createIfcIndexedPolygonalFace([int(i) + 1 for i in fc]) for fc in faces if len(fc) >= 3]
        return f.createIfcPolygonalFaceSet(pts, None, fs, None)

    # ------------------------------------------------------------------ geometry from source
    def world_mesh(self, name):
        c = self.cache["objects"][name]
        m = self.cache["meshes"][c["mesh"]]
        return fit.world_vertices(m["verts"], c["matrix"]), m["faces"]

    def sweep_items(self, fitd, frame: Frame, profile_name=None):
        """Swept solid items (in frame coords) for a prism / multiprism fit.  Returns (items, has_clip, profiles)."""
        parts = fitd["parts"] if fitd["kind"] == "multiprism" else [
            {"loop": fitd["loops"][0], "depth": fitd["depth"], "clips": fitd.get("clips", [None, None]),
             "holes": fitd.get("holes", []), "direction": fitd["direction"]}]
        items, profiles, has_clip = [], [], False
        for p in parts:
            d = _dir(p.get("direction", fitd["direction"]))
            loop = np.asarray(p["loop"])
            xs = horizontal_x_for(d) if abs(np.dot(d, frame.Z)) < 0.999 else frame.X
            sf = Frame(loop[0], xs, d)                               # solid frame (world)
            pts2 = [sf.to_local(q)[:2] for q in loop]
            holes2 = [[sf.to_local(q)[:2] for q in h] for h in p.get("holes", []) or []]
            prof = self.arb_profile(pts2, holes2, profile_name)
            profiles.append(prof)
            solid = self.extrusion(prof, frame.to_local(sf.O), frame.dir_local(sf.Z), frame.dir_local(sf.X), p["depth"])
            for cp in (p.get("clips") or []):
                if cp is not None:
                    solid = self.clip(solid, frame.to_local(cp[0]), frame.dir_local(cp[1]))
                    has_clip = True
            items.append(solid)
        return items, has_clip, profiles

    def box_item(self, fitd, frame: Frame, axis_index=None):
        """Rectangle-profile extrusion for a box fit (axis = chosen extrusion edge)."""
        e = np.asarray(fitd["edges"])
        o = np.asarray(fitd["origin"])
        if axis_index is None:
            v = [abs(np.dot(_dir(x), ZUP)) for x in e]
            axis_index = int(np.argmax(v)) if max(v) > 0.999 else int(np.argmax(np.linalg.norm(e, axis=1)))
        ax = e[axis_index]
        others = [e[i] for i in range(3) if i != axis_index]
        start = o if np.dot(ax, frame.Z) >= 0 or True else o
        a, b = others
        centre = start + (a + b) / 2
        prof = self.rect_profile(np.linalg.norm(a), np.linalg.norm(b))
        sx = _dir(a)
        solid = self.extrusion(prof, frame.to_local(centre), frame.dir_local(_dir(ax)), frame.dir_local(sx), np.linalg.norm(ax))
        return solid, prof

    def body_for_members(self, members, frame, prefer_tess=False):
        """Body representation for one or more source members in `frame` (world-aligned usually)."""
        fits = [self.rows[n]["_fit"] for n in members]
        swept_ok = (not prefer_tess) and all(fd["kind"] in ("box", "prism", "multiprism") for fd in fits)
        if swept_ok:
            items, clip = [], False
            for fd in fits:
                if fd["kind"] == "box":
                    s, _ = self.box_item(fd, frame)
                    items.append(s)
                else:
                    it, hc, _ = self.sweep_items(fd, frame)
                    items += it
                    clip = clip or hc
            if clip:
                if all(i.is_a("IfcBooleanClippingResult") for i in items):
                    return self.rep("Body", "Clipping", items), "Clipping"
                items = [self.f.createIfcCsgSolid(i) if i.is_a("IfcBooleanClippingResult") else i for i in items]
                return self.rep("Body", "SolidModel", items), "SolidModel"
            return self.rep("Body", "SweptSolid", items), "SweptSolid"
        items = []
        for n in members:
            v, fc = self.world_mesh(n)
            items.append(self.tess([frame.to_local(p) for p in v], fc))
        return self.rep("Body", "Tessellation", items), "Tessellation"

    # ------------------------------------------------------------------ types
    def wall_type(self, thk, matname, slab=False):
        key = ("SLAB" if slab else "WALL", round(thk, 4), matname)
        if key in self.types:
            return self.types[key]
        cls = "IfcSlabType" if slab else "IfcWallType"
        nm = f"{'ST' if slab else 'WT'}-{re.sub(r'[^A-Za-z0-9]+', '-', matname)[:30]}-{thk * 1000:.0f}mm"
        t = API.root.create_entity(self.f, cls, name=nm, predefined_type="FLOOR" if slab else "SOLIDWALL")
        t.GlobalId = self.g("TYPE:" + nm)
        ls = API.material.add_material_set(self.f, name=nm, set_type="IfcMaterialLayerSet")
        lay = API.material.add_layer(self.f, layer_set=ls, material=self.material(matname))
        API.material.edit_layer(self.f, layer=lay, attributes={"LayerThickness": float(thk)})
        API.material.assign_material(self.f, products=[t], type="IfcMaterialLayerSet", material=ls)
        self.types[key] = t
        return t

    def profile_type(self, cls, sig, profile, matname, pname):
        key = ("PROF", cls, sig, matname)
        if key in self.types:
            return self.types[key], self.profiles[key]
        tcls = cls + "Type"
        nm = f"{cls[3:]}T-{pname}-{re.sub(r'[^A-Za-z0-9]+', '-', matname)[:24]}"
        n = 1
        while self.f.by_type(tcls) and any(x.Name == nm for x in self.f.by_type(tcls)):
            n += 1
            nm = f"{cls[3:]}T-{pname}-{re.sub(r'[^A-Za-z0-9]+', '-', matname)[:24]}-{n}"
        ptype = {"IfcColumn": "COLUMN", "IfcBeam": "BEAM", "IfcMember": "MEMBER"}.get(cls, "NOTDEFINED")
        t = API.root.create_entity(self.f, tcls, name=nm, predefined_type=ptype)
        t.GlobalId = self.g("TYPE:" + nm)
        ps = API.material.add_material_set(self.f, name=nm, set_type="IfcMaterialProfileSet")
        API.material.add_profile(self.f, profile_set=ps, material=self.material(matname), profile=profile)
        API.material.assign_material(self.f, products=[t], type="IfcMaterialProfileSet", material=ps)
        self.types[key] = t
        self.profiles[key] = profile
        return t, profile

    # ------------------------------------------------------------------ element creation
    def new_element(self, el):
        cls = el["ifc_class"]
        ptype = el.get("predefined_type")
        try:
            e = API.root.create_entity(self.f, cls, predefined_type=ptype, name=el["stable_id"])
        except Exception:
            e = API.root.create_entity(self.f, cls, name=el["stable_id"])
            ptype = None
        e.GlobalId = el["global_id"]
        if ptype == "USERDEFINED" and el.get("object_type") and hasattr(e, "ObjectType"):
            e.ObjectType = el["object_type"]
        elif el.get("object_type") and hasattr(e, "ObjectType"):
            e.ObjectType = el["object_type"]
        m0 = el["members"][0]
        e.Description = (el["source_key"].split(":", 1)[1] if ":" in el["source_key"] else m0)[:250]
        if hasattr(e, "Tag"):
            e.Tag = self.objects[m0]["props"].get("bim_id") or m0[:250]
        self.el_by_sid[el["stable_id"]] = e
        return e

    def build_element(self, el):
        method = el["method"]
        members = el["members"]
        fits = [self.rows[n]["_fit"] for n in members]
        e = self.new_element(el)
        info = {"representation": None, "native": False, "notes": []}
        cls = el["ifc_class"]
        matname = self.member_material_name(members)
        mapped_key = None
        if len(members) == 1 and self.rows[members[0]].get("_shared"):
            k = (cls, self.rows[members[0]]["_mesh_key"])
            if self.mesh_users[k] >= 2 and method in ("extrude", "plate", "profile"):
                mapped_key = k
        try:
            if mapped_key:
                self.build_mapped(e, el, mapped_key, matname, info)
            elif method == "wall" and len(members) == 1 and fits[0]["kind"] == "box":
                self.build_wall_box(e, el, fits[0], matname, info)
            elif method == "wall_merged":
                self.build_wall_merged(e, el, matname, info)
            elif method == "slab" and len(members) == 1 and fits[0]["kind"] in ("box", "prism"):
                self.build_slab(e, el, fits[0], matname, info)
            elif method == "profile" and len(members) == 1 and fits[0]["kind"] in ("box", "prism", "multiprism"):
                self.build_profile_member(e, el, fits[0], matname, info)
            elif method in ("door", "window"):
                self.build_filler(e, el, matname, info)
            elif method in ("space", "zone"):
                self.build_space(e, el, info)
            else:
                self.build_generic(e, el, matname, info)
        except Exception as ex:          # never silently: fall back to exact tessellation and log
            info["notes"].append(f"native build failed ({type(ex).__name__}: {ex}); exact tessellation used")
            self.log.append((el["stable_id"], "FALLBACK", repr(ex)))
            for dct in (self.pending_types, self.pending_mapped, self.pending_mapped_nomap):
                for lst in dct.values():
                    if e in lst:
                        lst.remove(e)
            for rel in list(getattr(e, "HasAssociations", []) or []):
                pass
            e.Representation = None
            frame = self.group_frame(members)
            self.place(e, frame, el["storey"])
            rep, kind = self.body_for_members(members, frame, prefer_tess=True)
            API.geometry.assign_representation(self.f, product=e, representation=rep)
            API.material.assign_material(self.f, products=[e], material=self.material(matname))
            self.frames[el["stable_id"]] = frame
            info.update(representation=kind, native=False)
        self.info[el["stable_id"]] = info
        return e

    def group_frame(self, members):
        mn = np.min([self.objects[n]["aabb_min"] for n in members], axis=0)
        return Frame(mn, [1, 0, 0], [0, 0, 1])

    def build_generic(self, e, el, matname, info):
        members = el["members"]
        fits = [self.rows[n]["_fit"] for n in members]
        if len(members) == 1 and fits[0]["kind"] in ("prism", "multiprism"):
            d = _dir(fits[0]["direction"])
            loop0 = (fits[0]["parts"][0]["loop"] if fits[0]["kind"] == "multiprism" else fits[0]["loops"][0])
            frame = Frame(np.asarray(loop0).min(axis=0), horizontal_x_for(d) if abs(d[2]) < 0.999 else [1, 0, 0], d) \
                if el["ifc_class"] in ("IfcPlate", "IfcMember", "IfcRailing") else self.group_frame(members)
        else:
            frame = self.group_frame(members)
        self.place(e, frame, el["storey"])
        rep, kind = self.body_for_members(members, frame)
        API.geometry.assign_representation(self.f, product=e, representation=rep)
        mats = {(self.objects[n]["materials"] or ["UNSPECIFIED"])[0] for n in members}
        if len(mats) > 1:
            cs = API.material.add_material_set(self.f, name=el["stable_id"], set_type="IfcMaterialConstituentSet")
            for mn in sorted(mats):
                API.material.add_constituent(self.f, constituent_set=cs, material=self.material(mn))
            API.material.assign_material(self.f, products=[e], type="IfcMaterialConstituentSet", material=cs)
        else:
            API.material.assign_material(self.f, products=[e], material=self.material(matname))
        self.frames[el["stable_id"]] = frame
        info.update(representation=kind, native=kind != "Tessellation")

    def build_wall_box(self, e, el, fd, matname, info, frame_override=None, params=None):
        if params is None:
            ed = np.asarray(fd["edges"])
            o = np.asarray(fd["origin"])
            vi = [i for i in range(3) if abs(np.dot(_dir(ed[i]), ZUP)) > 0.999]
            if not vi:
                return self.build_generic(e, el, matname, info)
            vi = vi[0]
            v = ed[vi]
            hz = [ed[i] for i in range(3) if i != vi]
            a, b = sorted(hz, key=lambda x: -np.linalg.norm(x))
            if v[2] < 0:
                o = o + v
                v = -v
            X, Y = _dir(a), _dir(b)
            if np.dot(np.cross(X, Y), ZUP) < 0:
                o = o + b
                Y = -Y
            L, t, h = np.linalg.norm(a), np.linalg.norm(b), np.linalg.norm(v)
            frame = Frame(o, X, ZUP)
        else:
            frame, L, t, h = frame_override, *params
        self.place(e, frame, el["storey"])
        body = API.geometry.add_wall_representation(self.f, context=self.body, length=float(L), height=float(h),
                                                     thickness=float(t))
        axis = API.geometry.add_axis_representation(self.f, context=self.plan_axis, axis=[(0.0, 0.0), (float(L), 0.0)])
        API.geometry.assign_representation(self.f, product=e, representation=axis)
        API.geometry.assign_representation(self.f, product=e, representation=body)
        wt = self.wall_type(t, matname)
        self.pending_types[wt].append(e)
        ps = API.pset.add_pset(self.f, product=e, name="EPset_Parametric")
        API.pset.edit_pset(self.f, pset=ps, properties={"Engine": "Bonsai.DumbLayer2"})
        self.frames[el["stable_id"]] = frame
        info.update(representation="SweptSolid (Bonsai DumbLayer2 layered wall)", native=True,
                    params={"Length": L, "Width": t, "Height": h})

    def build_wall_merged(self, e, el, matname, info):
        wb = el["wall_box"]
        nax, (u0, u1, z0, z1), nmin, nmax = wb["nax"], wb["rect"], wb["nmin"], wb["nmax"]
        uax = 1 - nax
        X = np.zeros(3); X[uax] = 1
        Yw = np.zeros(3); Yw[nax] = 1
        if np.dot(np.cross(X, Yw), ZUP) > 0:
            o = np.zeros(3); o[uax] = u0; o[nax] = nmin; o[2] = z0
        else:
            o = np.zeros(3); o[uax] = u0; o[nax] = nmax; o[2] = z0
        frame = Frame(o, X, ZUP)
        L, t, h = u1 - u0, nmax - nmin, z1 - z0
        if not wb.get("lintel_rects"):
            self.build_wall_box(e, el, None, matname, info, frame_override=frame, params=(L, t, h))
            info["notes"].append(f"consolidated from {len(el['members'])} source wall pieces around "
                                 f"{len(el.get('openings', []))} opening(s)")
            return
        # elevation profile = U minus lintel rectangles (lintels stay separate IfcBeam LINTEL)
        loops = rect_difference_polygon((u0, u1, z0, z1), wb["lintel_rects"])
        self.place(e, frame, el["storey"])
        outer = [(u - u0, z - z0) for u, z in loops[0]]
        holes = [[(u - u0, z - z0) for u, z in h] for h in loops[1:]]
        # solid frame: profile (x=u, y=z) in local XZ plane, extruded along local +Y
        prof = self.arb_profile(outer, holes or None)
        solid = self.extrusion(prof, (0, 0, 0), (0, -1, 0), (1, 0, 0), t, ext_dir=(0, 0, -1))
        rep = self.rep("Body", "SweptSolid", [solid])
        axis = API.geometry.add_axis_representation(self.f, context=self.plan_axis, axis=[(0.0, 0.0), (float(L), 0.0)])
        API.geometry.assign_representation(self.f, product=e, representation=axis)
        API.geometry.assign_representation(self.f, product=e, representation=rep)
        API.material.assign_material(self.f, products=[e], material=self.material(matname))
        self.frames[el["stable_id"]] = frame
        info.update(representation="SweptSolid (elevation profile; lintels excluded)", native=True,
                    params={"Length": L, "Width": t, "Height": h},
                    notes=[f"consolidated from {len(el['members'])} source pieces; {len(wb['lintel_rects'])} lintel zone(s) excluded"])

    def build_slab(self, e, el, fd, matname, info):
        if fd["kind"] == "box":
            ed = np.asarray(fd["edges"])
            o = np.asarray(fd["origin"])
            vi = [i for i in range(3) if abs(np.dot(_dir(ed[i]), ZUP)) > 0.999]
            if not vi:
                return self.build_generic(e, el, matname, info)
            v = ed[vi[0]]
            hz = [ed[i] for i in range(3) if i != vi[0]]
            a, b = sorted(hz, key=lambda x: -np.linalg.norm(x))
            if v[2] < 0:
                o = o + v
                v = -v
            X, Y = _dir(a), _dir(b)
            if np.dot(np.cross(X, Y), ZUP) < 0:
                o = o + b
            frame = Frame(o, X, ZUP)
            depth = np.linalg.norm(v)
            poly = [(0.0, 0.0), (float(np.linalg.norm(a)), 0.0), (float(np.linalg.norm(a)), float(np.linalg.norm(b))),
                    (0.0, float(np.linalg.norm(b)))]
        else:
            d = _dir(fd["direction"])
            if abs(d[2]) < 0.999 or fd.get("holes") or any(c is not None for c in fd.get("clips", [])):
                return self.build_generic(e, el, matname, info)
            loop = np.asarray(fd["loops"][0])
            if d[2] < 0:
                loop = loop + d * fd["depth"]
                loop = loop[::-1]
            frame = Frame(loop[0], [1, 0, 0], ZUP)
            poly = [tuple(map(float, frame.to_local(p)[:2])) for p in loop]
            depth = fd["depth"]
        self.place(e, frame, el["storey"])
        body = API.geometry.add_slab_representation(self.f, context=self.body, depth=float(depth), polyline=poly)
        API.geometry.assign_representation(self.f, product=e, representation=body)
        self.pending_types[self.wall_type(depth, matname, slab=True)].append(e)
        ps = API.pset.add_pset(self.f, product=e, name="EPset_Parametric")
        API.pset.edit_pset(self.f, pset=ps, properties={"Engine": "Bonsai.DumbLayer3"})
        self.frames[el["stable_id"]] = frame
        area = abs(polygon_area_2d(poly))
        info.update(representation="SweptSolid (Bonsai DumbLayer3 layered slab)", native=True,
                    params={"Depth": depth, "Area": area})

    def build_profile_member(self, e, el, fd, matname, info):
        cls = el["ifc_class"]
        props = self.objects[el["members"][0]]["props"]
        pname = str(props.get("steel_section") or "").strip()
        if fd["kind"] == "box":
            ed = np.asarray(fd["edges"])
            o = np.asarray(fd["origin"])
            vz = [abs(np.dot(_dir(x), ZUP)) for x in ed]
            if cls == "IfcColumn" and max(vz) > 0.999:
                ai = int(np.argmax(vz))
            else:
                ai = int(np.argmax(np.linalg.norm(ed, axis=1)))
            ax = ed[ai]
            if np.dot(ax, ZUP) < -1e-9 or (abs(np.dot(ax, ZUP)) < 1e-9 and np.dot(ax, [1, 1, 0]) < 0):
                o = o + ax
                ax = -ax
            a, b = [ed[i] for i in range(3) if i != ai]
            if abs(np.dot(_dir(b), ZUP)) < abs(np.dot(_dir(a), ZUP)):
                a, b = b, a          # local X = more horizontal edge
            frame0 = Frame(o, a, ax)
            # frame origin at section centre, X along a
            centre = o + (a + b) / 2
            frame = Frame(centre, a, ax)
            xd, yd = np.linalg.norm(a), np.linalg.norm(b)
            pname = pname or f"RECT-{xd * 1000:.0f}x{yd * 1000:.0f}"
            sig = ("RECT", round(xd, 4), round(yd, 4))
            use_profile_usage = True
            prof = self.rect_profile(xd, yd, name=pname)
            depth = np.linalg.norm(ax)
            t, prof = self.profile_type(cls, sig, prof, matname, re.sub(r"[^A-Za-z0-9.]+", "", pname)[:30])
            items = [self.extrusion(prof, (0, 0, 0), (0, 0, 1), (1, 0, 0), depth)]
            rtype = "SweptSolid"
            area = xd * yd
        else:
            d = _dir(fd["direction"])
            if d[2] < -1e-9 or (abs(d[2]) < 1e-9 and np.dot(d, [1, 1, 0]) < 0):
                # keep geometry; just express frame along +d of the fit (fit loops are at s0 along d)
                pass
            parts = fd["parts"] if fd["kind"] == "multiprism" else [
                {"loop": fd["loops"][0], "depth": fd["depth"], "clips": fd.get("clips", [None, None]),
                 "holes": fd.get("holes", [])}]
            s_min = min(float(np.dot(np.asarray(p["loop"])[0], d)) for p in parts)
            cen = np.mean([np.asarray(p["loop"]).mean(axis=0) for p in parts], axis=0)
            O = cen - d * (np.dot(cen, d) - s_min)
            frame = Frame(O, horizontal_x_for(d) if abs(d[2]) < 0.999 else [1, 0, 0], d)
            part_profiles, items, has_clip = [], [], False
            for p in parts:
                loop = np.asarray(p["loop"])
                pts2 = [tuple(np.round(frame.to_local(q)[:2], 6)) for q in loop]
                holes2 = [[tuple(np.round(frame.to_local(q)[:2], 6)) for q in h] for h in (p.get("holes") or [])]
                part_profiles.append((pts2, holes2, float(np.dot(loop[0], d) - s_min), p["depth"], p.get("clips") or []))
            sig = ("ARB", tuple(sorted((round(x, 4), round(y, 4)) for pp in part_profiles for (x, y) in pp[0])))
            pname = pname or f"ARB-{len(parts)}x{len(part_profiles[0][0])}pt"
            subprofs = [self.arb_profile(pp[0], pp[1] or None, pname) for pp in part_profiles]
            key = ("PROF", cls, sig, matname)
            if key in self.types:
                t = self.types[key]
            else:
                tprof = [self.arb_profile(pp[0], pp[1] or None, pname) for pp in part_profiles]
                tp = tprof[0] if len(tprof) == 1 else self.f.createIfcCompositeProfileDef("AREA", pname, tprof, None)
                t, _ = self.profile_type(cls, sig, tp, matname, re.sub(r"[^A-Za-z0-9.]+", "", pname)[:30])
            # end planes per part (local frame): explicit clip plane, or the perpendicular cap at z0 / z1
            def end_planes(pp):
                z0, z1 = pp[2], pp[2] + pp[3]
                cs = pp[4] if len(pp[4]) == 2 else [None, None]
                st = (frame.to_local(cs[0][0]), _dir(frame.dir_local(cs[0][1]))) if cs[0] is not None else (np.array([0, 0, z0]), np.array([0, 0, -1.0]))
                en = (frame.to_local(cs[1][0]), _dir(frame.dir_local(cs[1][1]))) if cs[1] is not None else (np.array([0, 0, z1]), np.array([0, 0, 1.0]))
                return st, en
            planes = [end_planes(pp) for pp in part_profiles]
            def coincident(k):
                p0, n0 = planes[0][k]
                return all(np.dot(n, n0) > 1 - 1e-6 and abs(np.dot(np.asarray(pt) - p0, n0)) < 1e-3 for (pt, n) in (pl[k] for pl in planes))
            single = len(part_profiles) == 1 or (coincident(0) and coincident(1))
            use_profile_usage = single
            if single:
                # ONE extrusion of the (composite) profile, clipped by the shared end planes - the form that
                # IfcMaterialProfileSetUsage keeps in sync (Bonsai / IfcOpenShell regenerate SweptArea from the type profile)
                zmin = min(pp[2] for pp in part_profiles)
                zmax = max(pp[2] + pp[3] for pp in part_profiles)
                sp = subprofs[0] if len(subprofs) == 1 else self.f.createIfcCompositeProfileDef("AREA", pname, subprofs, None)
                solid = self.extrusion(sp, (0, 0, zmin), (0, 0, 1), (1, 0, 0), zmax - zmin)
                (sp0, sn0), (ep0, en0) = planes[0]
                if not (abs(sn0[2] + 1) < 1e-9 and abs(sp0[2] - zmin) < 1e-6):
                    solid = self.clip(solid, sp0, sn0); has_clip = True
                if not (abs(en0[2] - 1) < 1e-9 and abs(ep0[2] - zmax) < 1e-6):
                    solid = self.clip(solid, ep0, en0); has_clip = True
                items.append(solid)
            else:
                for sp, pp in zip(subprofs, part_profiles):
                    solid = self.extrusion(sp, (0, 0, pp[2]), (0, 0, 1), (1, 0, 0), pp[3])
                    for cp in pp[4]:
                        if cp is not None:
                            solid = self.clip(solid, frame.to_local(cp[0]), frame.dir_local(cp[1]))
                            has_clip = True
                    items.append(solid)
                info["notes"].append("multi-part section with differing end cuts: per-part solids, plain material (no profile usage)")
            depth = max(pp[2] + pp[3] for pp in part_profiles)
            rtype = "Clipping" if has_clip and all(i.is_a("IfcBooleanClippingResult") for i in items) else (
                "SweptSolid" if not has_clip else "SolidModel")
            if rtype == "SolidModel":
                items = [self.f.createIfcCsgSolid(i) if i.is_a("IfcBooleanClippingResult") else i for i in items]
            area = sum(abs(polygon_area_2d(pp[0])) - sum(abs(polygon_area_2d(h)) for h in pp[1]) for pp in part_profiles)
            if fd.get("deviation", 0) > 1e-4:
                info["notes"].append(f"sweep axis fitted with max lateral skew {fd['deviation'] * 1000:.1f} mm")
        self.place(e, frame, el["storey"])
        rep = self.rep("Body", rtype, items)
        API.geometry.assign_representation(self.f, product=e, representation=rep)
        axis = API.geometry.add_axis_representation(self.f, context=self.axis, axis=[(0.0, 0.0, 0.0), (0.0, 0.0, float(depth))])
        API.geometry.assign_representation(self.f, product=e, representation=axis)
        if fd["kind"] == "box" or use_profile_usage:
            self.pending_types[t].append(e)
            rep_txt = f"{rtype} (IfcMaterialProfileSetUsage, profile '{pname}')"
        else:
            API.material.assign_material(self.f, products=[e], material=self.material(matname))
            rep_txt = f"{rtype} (multi-part sections '{pname}', IfcMaterial)"
        self.frames[el["stable_id"]] = frame
        info.update(representation=rep_txt, native=True,
                    params={"Length": depth, "CrossSectionArea": area, "ProfileName": pname},
                    deviation=fd.get("deviation", 0.0))

    def build_filler(self, e, el, matname, info):
        from ..migration.openings import filler_box
        mn, mx = filler_box(el, self.objects)
        vols = [(self.rows[n].get("_src_volume") or 0.0, n) for n in el["members"]]
        big = max(vols)[1]
        matname = (self.objects[big]["materials"] or [matname])[0]
        ext = mx - mn
        nax = 0 if ext[0] < ext[1] else 1
        uax = 1 - nax
        W, H, D = float(ext[uax]), float(ext[2]), float(max(ext[nax], 0.02))
        X = np.zeros(3); X[uax] = 1
        door = el["ifc_class"] == "IfcDoor"
        key = ("FILLER", el["ifc_class"], round(W, 3), round(H, 3), round(D, 3))
        if key not in self.types:
            tcls = "IfcDoorType" if door else "IfcWindowType"
            nm = f"{'DT' if door else 'WT'}-{W * 1000:.0f}x{H * 1000:.0f}x{D * 1000:.0f}"
            t = API.root.create_entity(self.f, tcls, name=nm, predefined_type="DOOR" if door else "WINDOW")
            t.GlobalId = self.g("TYPE:" + nm)
            lt = min(0.05, D / 2, W / 6)
            if door:
                t.OperationType = "SINGLE_SWING_LEFT"
                lining = {"LiningDepth": D, "LiningThickness": lt, "CasingThickness": 0.0, "CasingDepth": 0.0,
                          "ThresholdDepth": 0.0, "ThresholdThickness": 0.0}
                panel = {"PanelDepth": min(0.045, D), "PanelWidth": 1.0}
                rep = API.geometry.add_door_representation(self.f, context=self.body, overall_height=H, overall_width=W,
                                                           operation_type="SINGLE_SWING_LEFT",
                                                           lining_properties=lining, panel_properties=panel)
                data = {"door_type": "SINGLE_SWING_LEFT", "overall_height": H, "overall_width": W,
                        "lining_properties": {_snake(k): v for k, v in lining.items()},
                        "panel_properties": {_snake(k): v for k, v in panel.items()}}
                psname = "BBIM_Door"
            else:
                t.PartitioningType = "SINGLE_PANEL"
                lining = {"LiningDepth": D, "LiningThickness": lt}
                panel = [{"FrameDepth": min(0.05, D), "FrameThickness": min(0.05, lt)}]
                rep = API.geometry.add_window_representation(self.f, context=self.body, overall_height=H, overall_width=W,
                                                             partition_type="SINGLE_PANEL",
                                                             lining_properties=lining, panel_properties=panel)
                data = {"window_type": "SINGLE_PANEL", "overall_height": H, "overall_width": W,
                        "lining_properties": {_snake(k): v for k, v in lining.items()},
                        "panel_properties": [{_snake(k): v for k, v in p.items()} for p in panel]}
                psname = "BBIM_Window"
            lb = self.local_bbox_of_rep(rep)
            API.geometry.assign_representation(self.f, product=t, representation=rep)
            ps = API.pset.add_pset(self.f, product=t, name=psname)
            API.pset.edit_pset(self.f, pset=ps, properties={"Data": json.dumps(data)})
            API.material.assign_material(self.f, products=[t], material=self.material(matname))
            self.types[key] = (t, lb)
        t, lb = self.types[key]
        # align parametric body local bbox to the source frame AABB (centre in X/Y, base in Z)
        Yw = np.cross(ZUP, X)
        lmid = (lb[0] + lb[1]) / 2
        target = np.zeros(3)
        target[uax] = (mn[uax] + mx[uax]) / 2
        target[nax] = (mn[nax] + mx[nax]) / 2
        target[2] = mn[2]
        O = target - X * lmid[0] - Yw * lmid[1] - ZUP * lb[0][2]
        frame = Frame(O, X, ZUP)
        self.place(e, frame, el["storey"])
        e.OverallWidth, e.OverallHeight = W, H
        self.pending_mapped[t].append(e)
        self.frames[el["stable_id"]] = frame
        info.update(representation=f"Parametric {'door' if door else 'window'} type (IfcOpenShell API, mapped)",
                    native=True, params={"Width": W, "Height": H, "Depth": D},
                    notes=[f"consolidated from {len(el['members'])} source part(s); parametric body replaces modelled frame/leaf/glass pieces"])

    def local_bbox_of_rep(self, rep):
        tmp = self.f.createIfcBuildingElementProxy(self.g("TMP-BBOX"), None, "TMP")
        tmp.ObjectPlacement = self.lp(None, [0, 0, 0])
        pds = self.f.createIfcProductDefinitionShape(None, None, [rep])
        tmp.Representation = pds
        s = ifcopenshell.geom.settings()
        sh = ifcopenshell.geom.create_shape(s, tmp)
        v = np.array(sh.geometry.verts).reshape(-1, 3)
        tmp.Representation = None
        self.f.remove(pds)
        a2 = tmp.ObjectPlacement.RelativePlacement
        lpl = tmp.ObjectPlacement
        self.f.remove(tmp)
        self.f.remove(lpl)
        for x in (a2.Location, a2.Axis, a2.RefDirection):
            self.f.remove(x)
        self.f.remove(a2)
        return v.min(axis=0), v.max(axis=0)

    def build_space(self, e, el, info):
        n = el["members"][0]
        o = self.objects[n]
        mn, mx = np.array(o["aabb_min"]), np.array(o["aabb_max"])
        frame = Frame(mn, [1, 0, 0], ZUP)
        self.place(e, frame, el["storey"])
        prof = self.rect_profile(mx[0] - mn[0], mx[1] - mn[1], (mx[0] - mn[0]) / 2, (mx[1] - mn[1]) / 2)
        solid = self.extrusion(prof, (0, 0, 0), (0, 0, 1), (1, 0, 0), mx[2] - mn[2])
        API.geometry.assign_representation(self.f, product=e, representation=self.rep("Body", "SweptSolid", [solid]))
        label = re.sub(r"^(SPACE|WC|REFUGE)-?", "", n)
        if e.is_a("IfcSpace"):
            e.LongName = label
        elif hasattr(e, "LongName"):
            e.LongName = label
        self.frames[el["stable_id"]] = frame
        info.update(representation="SweptSolid (space volume from source box)", native=True,
                    params={"Length": mx[0] - mn[0], "Width": mx[1] - mn[1], "Height": mx[2] - mn[2]})

    def build_mapped(self, e, el, key, matname, info):
        n = el["members"][0]
        c = self.cache["objects"][n]
        if key not in self.mapped_types:
            cls = el["ifc_class"]
            tcls = cls + "Type"
            m = self.cache["meshes"][c["mesh"]]
            nm = f"{cls[3:]}T-{re.sub(r'[^A-Za-z0-9]+', '-', c['mesh'].split(':', 1)[1])[:40]}"
            ptype = el.get("predefined_type") or "NOTDEFINED"
            try:
                t = API.root.create_entity(self.f, tcls, name=nm, predefined_type=ptype)
            except Exception:
                t = API.root.create_entity(self.f, tcls, name=nm)
            if ptype == "USERDEFINED" and el.get("object_type") and hasattr(t, "ElementType"):
                t.ElementType = el["object_type"]
            t.GlobalId = self.g("TYPE:" + nm + ":" + cls)
            local = fit.analyse(np.asarray(m["verts"]), m["faces"]) if len(m["verts"]) <= 400 else {"kind": "mesh"}
            fr = Frame.world()
            if local["kind"] == "box":
                s, _ = self.box_item(local, fr)
                rep = self.rep("Body", "SweptSolid", [s]); kind = "SweptSolid"
            elif local["kind"] in ("prism", "multiprism"):
                items, hc, _ = self.sweep_items(local, fr)
                if hc:
                    items = [self.f.createIfcCsgSolid(i) if i.is_a("IfcBooleanClippingResult") else i for i in items]
                    rep = self.rep("Body", "SolidModel", items); kind = "SolidModel"
                else:
                    rep = self.rep("Body", "SweptSolid", items); kind = "SweptSolid"
            else:
                rep = self.rep("Body", "Tessellation", [self.tess(m["verts"], m["faces"])]); kind = "Tessellation"
            API.geometry.assign_representation(self.f, product=t, representation=rep)
            API.material.assign_material(self.f, products=[t], material=self.material(matname))
            self.mapped_types[key] = (t, kind)
        t, kind = self.mapped_types[key]
        M = np.asarray(c["matrix"])
        R = M[:3, :3]
        sc = np.linalg.norm(R, axis=0)
        Rn = R / sc
        frame = Frame(M[:3, 3], Rn[:, 0], Rn[:, 2])
        if np.linalg.det(Rn) < 0:
            raise ValueError("mirrored instance")
        self.place(e, frame, el["storey"])
        rmap = t.RepresentationMaps[0]
        if np.allclose(sc, 1, atol=1e-6):
            op = self.f.createIfcCartesianTransformationOperator3D(None, None, self.f.createIfcCartesianPoint([0., 0., 0.]), None, None)
        else:
            op = self.f.createIfcCartesianTransformationOperator3DnonUniform(
                None, None, self.f.createIfcCartesianPoint([0., 0., 0.]), float(sc[0]), None, float(sc[1]), float(sc[2]))
        item = self.f.createIfcMappedItem(rmap, op)
        e.Representation = self.f.createIfcProductDefinitionShape(None, None, [self.rep("Body", "MappedRepresentation", [item])])
        self.pending_mapped_nomap[t].append(e)
        self.frames[el["stable_id"]] = frame
        info.update(representation=f"MappedRepresentation of {t.is_a()} '{t.Name}' ({kind})",
                    native=(kind != "Tessellation") and np.allclose(sc, 1, atol=1e-6),
                    mapped=True, type_body=kind)
        if not np.allclose(sc, 1, atol=1e-6):
            info["notes"].append(f"type-mapped primitive with non-uniform scale {np.round(sc, 4).tolist()} - not counted as native")
        if kind == "Tessellation":
            info["notes"].append("type body is the exact source tessellation (instanced) - not parametric")

    # ------------------------------------------------------------------ batch build
    def build_phase(self, phase, elements):
        self.pending_types = defaultdict(list)
        self.pending_mapped = defaultdict(list)
        self.pending_mapped_nomap = defaultdict(list)
        built = []
        for el in elements:
            if el["phase"] != phase:
                continue
            built.append(self.build_element(el))
        for t, occ in self.pending_types.items():
            # True is required: IfcOpenShell 0.9 only creates IfcMaterialLayerSetUsage / IfcMaterialProfileSetUsage
            # on occurrences when mapping is enabled (these types carry no representation maps, so nothing is mapped)
            API.type.assign_type(self.f, related_objects=occ, relating_type=t, should_map_representations=True)
        for t, occ in self.pending_mapped.items():
            API.type.assign_type(self.f, related_objects=occ, relating_type=t, should_map_representations=True)
        for t, occ in self.pending_mapped_nomap.items():
            API.type.assign_type(self.f, related_objects=occ, relating_type=t, should_map_representations=False)
        return built

    def finish_relationships(self, phase_elements, assemblies, all_elements):
        """Incremental: containment / aggregation / systems for this batch, openings when both ends exist."""
        f = self.f
        if not hasattr(self, "asm_ents"):
            self.asm_ents, self.systems, self.openings_done = {}, {}, set()
            self.child_of = {c: k for k, a in assemblies.items() for c in a["children"]}
        by_storey, spaces, zones, kids = defaultdict(list), defaultdict(list), defaultdict(list), defaultdict(list)
        for el in phase_elements:
            e = self.el_by_sid.get(el["stable_id"])
            if e is None:
                continue
            akey = self.child_of.get(el["stable_id"])
            if akey:
                if akey not in self.asm_ents:
                    a = assemblies[akey]
                    cls, ptype, otype = assembly_class(akey)
                    ent = API.root.create_entity(f, cls, predefined_type=ptype, name=a["stable_id"])
                    ent.GlobalId = a["global_id"]
                    if otype and hasattr(ent, "ObjectType"):
                        ent.ObjectType = otype
                    ent.Description = akey
                    st, elev = self.storeys[a["storey"]]
                    ent.ObjectPlacement = self.lp(st.ObjectPlacement, [0, 0, 0])
                    self.asm_ents[akey] = ent
                    self.el_by_sid[a["stable_id"]] = ent
                    by_storey[a["storey"]].append(ent)
                    ps = API.pset.add_pset(f, product=ent, name="SOUTHGATE_Provenance")
                    API.pset.edit_pset(f, pset=ps, properties={"StableId": a["stable_id"], "SourceKey": "ASSEMBLY:" + akey,
                                                               "MigrationMethod": "aggregate of migrated parts",
                                                               "PartCount": len(a["children"]), "MigrationRun": self.run_id})
                    kid_status = {getattr(self, "status_of", {}).get(c) for c in a["children"]}
                    st_ = ("CONCEPT_UNVERIFIED" if "CONCEPT_UNVERIFIED" in kid_status else
                           "PRELIMINARY_DESIGN" if "PRELIMINARY_DESIGN" in kid_status else "EXISTING_DESIGN_REFERENCE")
                    ps = API.pset.add_pset(f, product=ent, name="SOUTHGATE_DesignStatus")
                    API.pset.edit_pset(f, pset=ps, properties={"DesignStatus": st_, "StatusBasis": "least mature status of its parts",
                                                               "EngineeringVerified": False})
                kids[akey].append(e)
            elif e.is_a("IfcSpace"):
                spaces[el["storey"]].append(e)
            elif e.is_a("IfcSpatialZone"):
                zones[el["storey"]].append(e)
            else:
                by_storey[el["storey"]].append(e)
        for akey, prods in kids.items():
            API.aggregate.assign_object(f, products=prods, relating_object=self.asm_ents[akey])
        for code, prods in by_storey.items():
            API.spatial.assign_container(f, products=prods, relating_structure=self.storeys[code][0])
        for code, prods in spaces.items():
            API.aggregate.assign_object(f, products=prods, relating_object=self.storeys[code][0])
        for code, prods in zones.items():
            API.spatial.reference_structure(f, products=prods, relating_structure=self.storeys[code][0])
        sysm = defaultdict(list)
        for el in phase_elements:
            if el.get("system") and el["stable_id"] in self.el_by_sid:
                sysm[el["system"]].append(self.el_by_sid[el["stable_id"]])
        for code, prods in sysm.items():
            if code not in self.systems:
                pt, ot, desc = SYSTEMS[code]
                sy = API.system.add_system(f, ifc_class="IfcDistributionSystem")
                sy.GlobalId = self.g("SYSTEM:" + code)
                sy.Name = f"SOUTHGATE-SYS-{code}"
                sy.Description = desc
                sy.PredefinedType = pt
                if ot:
                    sy.ObjectType = ot
                self.systems[code] = sy
            dist = [x for x in prods if x.is_a("IfcDistributionElement")]
            other = [x for x in prods if not x.is_a("IfcDistributionElement")]
            if dist:
                API.system.assign_system(f, products=dist, system=self.systems[code])
            if other:   # brackets, battens, kerbs: not distribution elements -> companion IfcGroup
                gk = code + "-ANCILLARY"
                if gk not in self.systems:
                    import ifcopenshell.api.group
                    grp = ifcopenshell.api.group.add_group(f, name=f"SOUTHGATE-GRP-{code}-ANCILLARY",
                                                           description=f"Non-distribution supports/accessories of {code}")
                    grp.GlobalId = self.g("GROUP:" + gk)
                    self.systems[gk] = grp
                import ifcopenshell.api.group
                ifcopenshell.api.group.assign_group(f, products=other, group=self.systems[gk])
        n_open = 0
        for el in all_elements:
            for op in el.get("openings", []) or []:
                k = (el["stable_id"], op["filler"])
                if k in self.openings_done:
                    continue
                host = self.el_by_sid.get(el["stable_id"])
                filler = self.el_by_sid.get(op["filler"])
                if host is None or filler is None:
                    continue
                self.add_opening(el, host, filler, op)
                self.openings_done.add(k)
                n_open += 1
        return n_open

    def add_opening(self, el, host, filler, op):
        f = self.f
        frame = self.frames[el["stable_id"]]
        nax = op["nax"]
        uax = 1 - nax
        u0, u1, z0, z1 = op["rect"]
        n0, n1 = op["nrange"]
        mn = np.zeros(3); mx = np.zeros(3)
        mn[uax], mx[uax] = u0, u1
        mn[nax], mx[nax] = n0 - 0.05, n1 + 0.05
        mn[2], mx[2] = z0, z1
        corners = np.array([[x, y, z] for x in (mn[0], mx[0]) for y in (mn[1], mx[1]) for z in (mn[2], mx[2])])
        loc = np.array([frame.to_local(c) for c in corners])
        lmn, lmx = loc.min(axis=0), loc.max(axis=0)
        sid = el["stable_id"] + "-OPEN-" + op["filler"].rsplit("-", 2)[-2] + "-" + op["filler"].rsplit("-", 1)[-1]
        o = API.root.create_entity(f, "IfcOpeningElement", predefined_type="OPENING", name=sid)
        o.GlobalId = self.g("OPENING:" + el["stable_id"] + ":" + op["filler"])
        o.ObjectPlacement = self.f.createIfcLocalPlacement(host.ObjectPlacement, self.a2p([0, 0, 0]))
        prof = self.rect_profile(lmx[0] - lmn[0], lmx[1] - lmn[1], (lmn[0] + lmx[0]) / 2, (lmn[1] + lmx[1]) / 2)
        solid = self.extrusion(prof, (0, 0, lmn[2]), (0, 0, 1), (1, 0, 0), lmx[2] - lmn[2])
        API.geometry.assign_representation(f, product=o, representation=self.rep("Body", "SweptSolid", [solid]))
        API.feature.add_feature(f, feature=o, element=host)
        API.feature.add_filling(f, opening=o, element=filler)

    # ------------------------------------------------------------------ properties
    def write_properties(self, elements, design_status_fn):
        f = self.f
        snap = self.cfg["source"]["snapshot_sha256"]
        spec_keys = ["steel_section", "material_specification", "material_grade_concept", "standard",
                     "nominal_mass_per_m_kg", "bolt_designation", "element_type", "member_role", "rainwater_component",
                     "vent_role", "rr_type", "quantity_method", "quantity_unit", "building_zone", "assembly_id"]
        for el in elements:
            e = self.el_by_sid.get(el["stable_id"])
            if e is None:
                continue
            members = el["members"]
            p0 = self.objects[members[0]]["props"]
            info = self.info.get(el["stable_id"], {})
            colls = sorted({self.objects[n]["collections"][0] for n in members})
            bim_ids = [self.objects[n]["props"].get("bim_id") for n in members if self.objects[n]["props"].get("bim_id")]
            prov = {"StableId": el["stable_id"], "SourceKey": el["source_key"][:250],
                    "SourceObjectCount": len(members),
                    "SourceObjects": "; ".join(members[:40])[:1000] + (" ..." if len(members) > 40 else ""),
                    "SourceCollections": "; ".join(colls)[:500],
                    "SourceBimIds": "; ".join(bim_ids[:40])[:1000],
                    "SourceSnapshotSHA256": snap, "MigrationRule": el["rule"], "MigrationMethod": el["method"],
                    "Representation": str(info.get("representation"))[:250],
                    "NativeRepresentation": bool(info.get("native")),
                    "MigrationNotes": "; ".join(info.get("notes", []))[:1000] or "-",
                    "MigrationRun": self.run_id}
            if info.get("deviation"):
                prov["FitMaxDeviation_mm"] = round(info["deviation"] * 1000, 2)
            ps = API.pset.add_pset(f, product=e, name="SOUTHGATE_Provenance")
            API.pset.edit_pset(f, pset=ps, properties=prov)
            status, basis = design_status_fn(el, p0)
            self.status_of = getattr(self, "status_of", {})
            self.status_of[el["stable_id"]] = status
            ver = str(p0.get("verification_status") or p0.get("connection_status") or p0.get("approval") or
                      p0.get("EXT08_status") or p0.get("hydraulic_status") or "")
            ds = {"DesignStatus": status, "StatusBasis": basis,
                  "SourceDesignStatus": str(p0.get("design_status", "-")),
                  "SourceBOQInclusion": str(p0.get("boq_inclusion", "-")),
                  "VerificationNote": ver[:1000] or "-",
                  "EngineeringVerified": False}
            ps = API.pset.add_pset(f, product=e, name="SOUTHGATE_DesignStatus")
            API.pset.edit_pset(f, pset=ps, properties=ds)
            spec = {k: (json.dumps(p0[k]) if isinstance(p0[k], (list, dict)) else p0[k]) for k in spec_keys if k in p0}
            spec = {("Source_" + k): (str(v)[:1000] if isinstance(v, str) else v) for k, v in spec.items()}
            if spec:
                ps = API.pset.add_pset(f, product=e, name="SOUTHGATE_SourceSpecification")
                API.pset.edit_pset(f, pset=ps, properties=spec)
            common = f"Pset_{e.is_a()[3:]}Common"
            if _PSET_LIB.get_by_name(common):
                ps = API.pset.add_pset(f, product=e, name=common)
                try:
                    API.pset.edit_pset(f, pset=ps, properties={"Reference": el["stable_id"], "Status": ["NEW"]})
                except Exception:
                    API.pset.edit_pset(f, pset=ps, properties={"Reference": el["stable_id"]})


def linear_to_srgb(c):
    c = max(0.0, min(1.0, float(c)))
    return 12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055


def _snake(k):
    return re.sub(r"(?<!^)(?=[A-Z])", "_", k).lower()


def polygon_area_2d(pts):
    a = 0.0
    for i in range(len(pts)):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % len(pts)]
        a += x1 * y2 - x2 * y1
    return a / 2


def rect_difference_polygon(U, minus):
    """Orthogonal polygon(s) of rectangle U minus rectangles; returns [outer, *holes] as (u,z) loops."""
    us = sorted({U[0], U[1]} | {r[0] for r in minus} | {r[1] for r in minus})
    zs = sorted({U[2], U[3]} | {r[2] for r in minus} | {r[3] for r in minus})
    us = [u for u in us if U[0] - 1e-9 <= u <= U[1] + 1e-9]
    zs = [z for z in zs if U[2] - 1e-9 <= z <= U[3] + 1e-9]
    nu, nz = len(us) - 1, len(zs) - 1
    filled = np.ones((nu, nz), bool)
    for i in range(nu):
        for j in range(nz):
            cu, cz = (us[i] + us[i + 1]) / 2, (zs[j] + zs[j + 1]) / 2
            if any(r[0] < cu < r[1] and r[2] < cz < r[3] for r in minus):
                filled[i, j] = False
    edges = {}
    def cell(i, j):
        return 0 <= i < nu and 0 <= j < nz and filled[i, j]
    for i in range(nu):
        for j in range(nz):
            if not filled[i, j]:
                continue
            # CCW edges of the cell where the neighbour is empty
            if not cell(i, j - 1): edges[(us[i], zs[j])] = (us[i + 1], zs[j])
            if not cell(i + 1, j): edges[(us[i + 1], zs[j])] = (us[i + 1], zs[j + 1])
            if not cell(i, j + 1): edges[(us[i + 1], zs[j + 1])] = (us[i], zs[j + 1])
            if not cell(i - 1, j): edges[(us[i], zs[j + 1])] = (us[i], zs[j])
    loops = []
    while edges:
        start, nxt = next(iter(edges.items()))
        loop = [start]
        edges.pop(start)
        cur = nxt
        while cur != start:
            loop.append(cur)
            cur = edges.pop(cur)
        # drop collinear points
        simp = []
        for k in range(len(loop)):
            a, b, c = loop[k - 1], loop[k], loop[(k + 1) % len(loop)]
            if not ((a[0] == b[0] == c[0]) or (a[1] == b[1] == c[1])):
                simp.append(b)
        loops.append(simp)
    loops.sort(key=lambda lp: -abs(polygon_area_2d(lp)))
    return loops
