"""Model-derived quantities.

* Standard IFC4 base quantities (Qto_*BaseQuantities) are computed with IfcOpenShell's
  official take-off engine ifc5d (rule set IFC4QtoBaseQuantities) from the CURRENT IFC
  geometry and written back to the model.  Re-running after any edit refreshes them.
* SOUTHGATE_Quantities adds what the base sets do not carry: indicative mass from material
  density (steel/aluminium/glass categories only), profile-based length x nominal mass for
  sections with a source nominal_mass_per_m_kg, counts for grouped fastener sets.
Nothing here is a priced BOQ; see docs/quantity_method.md.
"""
from __future__ import annotations

import csv
from collections import defaultdict

import ifcopenshell
import ifcopenshell.api.pset
import ifcopenshell.util.element as ue
import ifc5d.qto as q5

MASS_CATEGORIES = {"steel", "aluminium", "glass"}
SKIP = ("IfcOpeningElement", "IfcVirtualElement")


def target_elements(ifc):
    return {e for e in ifc.by_type("IfcElement") + ifc.by_type("IfcSpace") if not e.is_a() in SKIP and e.Representation}


STEEL_CLASSES = ("IfcMember", "IfcBeam", "IfcColumn", "IfcPlate", "IfcMechanicalFastener", "IfcFastener", "IfcDiscreteAccessory")


def sanitise(ifc, geo):
    """Reviewer objections O-01/O-02: remove volumes that cannot be true, fix non-layered wall dimensions."""
    import ifcopenshell.api.pset as P
    n_bad = n_wall = 0
    for e in target_elements(ifc):
        gm = geo.get(e.GlobalId)
        if not gm:
            continue
        ext = gm["ext"]
        bbox_vol = ext[0] * ext[1] * ext[2]
        prov = ue.get_pset(e, "SOUTHGATE_Provenance") or {}
        tess = "Tessellation" in str(prov.get("Representation")) or "tessellation" in str(prov.get("MigrationNotes"))
        bad = gm["vol"] is not None and (gm["vol"] > bbox_vol * 1.001 + 1e-9 or gm["vol"] < 0 or not gm.get("closed", True))
        gm["reliable"] = not bad
        if bad:
            n_bad += 1
            for qn, props in ue.get_psets(e, qtos_only=True).items():
                drop = {k: None for k in props if k in ("GrossVolume", "NetVolume", "GrossWeight", "NetWeight")}
                if drop:
                    P.edit_qto(ifc, qto=ifc.by_id(props["id"]), properties=drop)
        if e.is_a("IfcWall") and (ue.get_pset(e, "EPset_Parametric") or {}).get("Engine") != "Bonsai.DumbLayer2":
            qs = ue.get_pset(e, "Qto_WallBaseQuantities")
            if qs:
                L, W = max(ext[0], ext[1]), min(ext[0], ext[1])
                H = ext[2]
                net = (gm["vol"] / W) if (gm.get("reliable") and gm["vol"] and W > 1e-6) else None
                props = {"Length": L, "Width": W, "Height": H, "GrossSideArea": L * H}
                if net:
                    props["NetSideArea"] = min(net, L * H)
                P.edit_qto(ifc, qto=ifc.by_id(qs["id"]), properties=props)
                n_wall += 1
    return n_bad, n_wall


def compute_base_quantities(ifc, elements=None):
    elements = elements or target_elements(ifc)
    results = q5.quantify(ifc, set(elements), q5.rules["IFC4QtoBaseQuantities"])
    q5.edit_qtos(ifc, results)
    _door_window_qtos(ifc, elements)
    remove_empty_qtos(ifc)
    return results


def remove_empty_qtos(ifc):
    """IfcElementQuantity.Quantities is SET[1:?] - drop sets the engine left empty."""
    n = 0
    for q in list(ifc.by_type("IfcElementQuantity")):
        if not q.Quantities:
            for rel in list(ifc.get_inverse(q)):
                if rel.is_a("IfcRelDefinesByProperties"):
                    ifc.remove(rel)
            ifc.remove(q)
            n += 1
    return n


def _door_window_qtos(ifc, elements):
    """Qto_Door/WindowBaseQuantities Width/Height/Area from the parametric overall dimensions."""
    for e in elements:
        if not (e.is_a("IfcDoor") or e.is_a("IfcWindow")) or not e.OverallWidth or not e.OverallHeight:
            continue
        name = "Qto_DoorBaseQuantities" if e.is_a("IfcDoor") else "Qto_WindowBaseQuantities"
        ex = ue.get_pset(e, name)
        q = ifc.by_id(ex["id"]) if ex else ifcopenshell.api.pset.add_qto(ifc, product=e, name=name)
        ifcopenshell.api.pset.edit_qto(ifc, qto=q, properties={
            "Width": float(e.OverallWidth), "Height": float(e.OverallHeight),
            "Area": float(e.OverallWidth) * float(e.OverallHeight)})


def is_closed(verts, tris):
    """True when the triangulated body is a closed, consistently oriented surface (volume is defined)."""
    import numpy as np
    key = np.round(verts / 1e-5).astype(np.int64)
    _, inv = np.unique(key, axis=0, return_inverse=True)
    t = inv.reshape(-1)[tris]
    t = t[(t[:, 0] != t[:, 1]) & (t[:, 1] != t[:, 2]) & (t[:, 0] != t[:, 2])]
    if not len(t):
        return False
    d = np.concatenate([t[:, [0, 1]], t[:, [1, 2]], t[:, [2, 0]]])
    und = np.sort(d, axis=1)
    _, cnt = np.unique(und, axis=0, return_counts=True)
    if not np.all(cnt == 2):
        return False
    _, dcnt = np.unique(d, axis=0, return_counts=True)
    return bool(np.all(dcnt == 1))


def geometry_measures(ifc, elements):
    """Volume, surface area and world-aligned extents of every element body (IfcOpenShell geometry)."""
    import multiprocessing
    import numpy as np
    import ifcopenshell.geom
    import ifcopenshell.util.shape as us
    s = ifcopenshell.geom.settings()
    s.set("use-world-coords", True)
    out = {}
    it = ifcopenshell.geom.iterator(s, ifc, max(1, multiprocessing.cpu_count() - 1), include=list(elements))
    if it.initialize():
        while True:
            sh = it.get()
            g = sh.geometry
            v = np.asarray(g.verts).reshape(-1, 3)
            if len(v):
                try:
                    vol = us.get_volume(g)
                except Exception:
                    vol = None
                out[sh.guid] = {"vol": vol, "area": us.get_area(g), "ext": (v.max(axis=0) - v.min(axis=0)).tolist(),
                                "closed": is_closed(v, np.asarray(g.faces).reshape(-1, 3))}
            if not it.next():
                break
    return out


def density_of(mat):
    if mat is None:
        return None, None
    m = mat
    if m.is_a("IfcMaterialLayerSetUsage"):
        m = m.ForLayerSet.MaterialLayers[0].Material
    elif m.is_a("IfcMaterialLayerSet"):
        m = m.MaterialLayers[0].Material
    elif m.is_a("IfcMaterialProfileSetUsage"):
        m = m.ForProfileSet.MaterialProfiles[0].Material
    elif m.is_a("IfcMaterialProfileSet"):
        m = m.MaterialProfiles[0].Material
    elif m.is_a("IfcMaterialConstituentSet"):
        m = m.MaterialConstituents[0].Material
    if m is None or not m.is_a("IfcMaterial"):
        return None, None
    ps = ue.get_pset(m, "Pset_MaterialCommon") or {}
    return m.Category, ps.get("MassDensity")


def first_qto(e):
    for name, props in ue.get_psets(e, qtos_only=True).items():
        if name.startswith("Qto_"):
            return name, props
    return None, {}


def volume_of(props):
    for k in ("NetVolume", "GrossVolume"):
        if props.get(k):
            return props[k]
    return None


def add_project_quantities(ifc):
    els = target_elements(ifc)
    geo = geometry_measures(ifc, els)
    sanitise(ifc, geo)
    for e in els:
        qn, props = first_qto(e)
        cat, dens = density_of(ue.get_material(e, should_inherit=True))
        out = {"Count": 1}
        gm = geo.get(e.GlobalId)
        if gm:
            out["VolumeReliable"] = bool(gm.get("reliable", True))
            if gm["vol"] and gm["vol"] > 0 and gm.get("reliable", True):
                out["GeometryVolume_m3"] = round(gm["vol"], 6)
            elif gm["vol"]:
                out["VolumeNote"] = "body volume rejected: body is not a closed surface (open/inconsistent source mesh) or exceeds its bounding box"
            out["GeometrySurfaceArea_m2"] = round(gm["area"], 4)
            out["ExtentX_m"], out["ExtentY_m"], out["ExtentZ_m"] = [round(x, 4) for x in gm["ext"]]
            out["GeometryBasis"] = "IfcOpenShell geometry of the current body (openings applied), world-aligned extents"
        spec0 = ue.get_pset(e, "SOUTHGATE_SourceSpecification") or {}
        steel_ok = e.is_a() in STEEL_CLASSES and bool(spec0.get("Source_steel_section") or spec0.get("Source_bolt_designation"))
        if not props and gm and gm["vol"] and gm.get("reliable", True) and steel_ok:
            props = {"NetVolume": gm["vol"]}
            qn = "SOUTHGATE_Quantities.GeometryVolume_m3"
        vol = volume_of(props)
        if vol and dens and cat == "steel" and steel_ok and (not gm or gm.get("reliable", True)):
            out["IndicativeMassFromDensity_kg"] = round(vol * dens, 3)
            out["MassBasis"] = f"{qn} volume x nominal {cat} density {dens} kg/m3 (indicative)"
        spec = ue.get_pset(e, "SOUTHGATE_SourceSpecification") or {}
        npm = spec.get("Source_nominal_mass_per_m_kg")
        L = props.get("Length")
        if npm and L:
            out["NominalSectionMass_kg"] = round(float(npm) * float(L), 3)
            out["NominalSectionMassBasis"] = f"Qto Length x source nominal mass {npm} kg/m"
        if e.is_a("IfcMechanicalFastener") and (ue.get_pset(e, "SOUTHGATE_Provenance") or {}).get("MigrationRule") == "ROOF-FIXINGS":
            out["CountBasis"] = ("element represents a merged set of roof screws from the source; individual count requires "
                                 "an approved fixing specification (config/quantity_rules.yaml)")
        if out:
            ps = ue.get_pset(e, "SOUTHGATE_Quantities")
            ps = ifc.by_id(ps["id"]) if ps else ifcopenshell.api.pset.add_pset(ifc, product=e, name="SOUTHGATE_Quantities")
            ifcopenshell.api.pset.edit_pset(ifc, pset=ps, properties=out)


def schedule_rows(ifc):
    rows = []
    for e in sorted(target_elements(ifc), key=lambda x: x.Name or ""):
        qn, props = first_qto(e)
        sq = ue.get_pset(e, "SOUTHGATE_Quantities") or {}
        ds = ue.get_pset(e, "SOUTHGATE_DesignStatus") or {}
        pv = ue.get_pset(e, "SOUTHGATE_Provenance") or {}
        container = ue.get_container(e)
        agg = ue.get_aggregate(e)
        mat = ue.get_material(e, should_inherit=True)
        prof = ""
        if mat is not None and mat.is_a("IfcMaterialProfileSetUsage"):
            prof = mat.ForProfileSet.MaterialProfiles[0].Profile.ProfileName or ""
        t = ue.get_type(e)
        rows.append({
            "stable_id": e.Name, "global_id": e.GlobalId, "ifc_class": e.is_a(),
            "predefined_type": getattr(e, "PredefinedType", "") or "", "object_type": getattr(e, "ObjectType", "") or "",
            "type_name": t.Name if t else "", "storey": _storey_name(container, agg),
            "assembly": agg.Name if agg is not None and not agg.is_a("IfcSpatialStructureElement") else "",
            "material": _mat_name(mat), "profile": prof, "qto_set": qn or "",
            "Count": 1, "Length_m": props.get("Length"), "Width_m": props.get("Width"), "Height_m": props.get("Height") or props.get("Depth"),
            "GrossArea_m2": props.get("GrossArea") or props.get("GrossSideArea") or props.get("GrossFloorArea") or props.get("Area"),
            "NetArea_m2": props.get("NetArea") or props.get("NetSideArea") or props.get("NetFloorArea"),
            "GrossVolume_m3": props.get("GrossVolume"), "NetVolume_m3": props.get("NetVolume"),
            "CrossSectionArea_m2": props.get("CrossSectionArea"), "OuterSurfaceArea_m2": props.get("OuterSurfaceArea"),
            "IndicativeMass_kg": sq.get("IndicativeMassFromDensity_kg"), "NominalSectionMass_kg": sq.get("NominalSectionMass_kg"),
            "GeometryVolume_m3": sq.get("GeometryVolume_m3"), "GeometrySurfaceArea_m2": sq.get("GeometrySurfaceArea_m2"),
            "ExtentX_m": sq.get("ExtentX_m"), "ExtentY_m": sq.get("ExtentY_m"), "ExtentZ_m": sq.get("ExtentZ_m"),
            "design_status": ds.get("DesignStatus"), "source_boq_inclusion": ds.get("SourceBOQInclusion"),
            "representation": pv.get("Representation"), "migration_rule": pv.get("MigrationRule")})
    return rows


def _storey_name(container, agg):
    if container is not None:
        return container.Name
    if agg is not None and agg.is_a("IfcBuildingStorey"):
        return agg.Name
    c = ue.get_container(agg) if agg is not None else None
    return c.Name if c is not None else ""


def _mat_name(m):
    if m is None:
        return ""
    if m.is_a("IfcMaterial"):
        return m.Name
    for attr in ("ForLayerSet", "ForProfileSet"):
        if hasattr(m, attr):
            m = getattr(m, attr)
    if m.is_a("IfcMaterialLayerSet"):
        return "; ".join(l.Material.Name for l in m.MaterialLayers)
    if m.is_a("IfcMaterialProfileSet"):
        return "; ".join(p.Material.Name for p in m.MaterialProfiles if p.Material)
    if m.is_a("IfcMaterialConstituentSet"):
        return "; ".join(c.Material.Name for c in m.MaterialConstituents)
    return m.is_a()


def write_csv(rows, path):
    if not rows:
        return
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
