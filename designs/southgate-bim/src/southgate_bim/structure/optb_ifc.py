"""Option B roof trusses - native IFC4 authoring (IfcOpenShell API = Bonsai's authoring core).

Element model (per truss line):
  IfcElementAssembly TRUSS (identity of the existing SOUTHGATE-TRUSS-Txx is reused)
    +- IfcElementAssembly USERDEFINED 'BUILT_UP_MEMBER_2L'  (37: 12 chord pieces + 25 webs)
    |    +- IfcMember x2  (one per angle; IfcLShapeProfileDef, IfcMaterialProfileSetUsage, CardinalPoint 5)
    |    +- IfcPlate packing plates (mapped type geometry) + IfcMechanicalFastener packer bolts
    +- IfcElementAssembly USERDEFINED 'CONNECTION_<family>'  (26 panel points)
         +- IfcPlate gusset (arbitrary profile with bolt-hole voids, IfcMaterialLayerSetUsage AXIS3)
         +- IfcPlate splice plates (at chord splices / apex)
         +- IfcMechanicalFastener bolt sets (mapped type geometry: bolt + nut + washer)
  Relationships: IfcRelAggregates, IfcRelDefinesByType (member/plate/fastener/connection/truss types),
  IfcRelAssociatesMaterial, IfcRelConnectsWithRealizingElements (plate <-> angle, realised by the bolts),
  IfcRelAssociatesClassification on types, shared status/warning psets.
"""
from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict

import numpy as np
import ifcopenshell
import ifcopenshell.api
import ifcopenshell.api.aggregate
import ifcopenshell.api.material
import ifcopenshell.api.pset
import ifcopenshell.api.root
import ifcopenshell.api.spatial
import ifcopenshell.api.style
import ifcopenshell.api.type
import ifcopenshell.guid
import ifcopenshell.util.element as ue
from shapely.geometry import Polygon

from ..migration.plan import guid_for
from .optb_truss import OptionBTruss, AngleSec, Y0, plate_area_net, shape_hash

API = ifcopenshell.api
REV = "OPTB-C01"

ROLE_PTYPE = {  # IfcMemberTypeEnum + ElementType
    "TC": ("CHORD", "TRUSS_TOP_CHORD"), "BC": ("CHORD", "TRUSS_BOTTOM_CHORD"),
    "VP": ("USERDEFINED", "TRUSS_END_POST"), "V": ("USERDEFINED", "TRUSS_WEB_VERTICAL"),
    "VK": ("USERDEFINED", "TRUSS_KING_POST"), "D": ("USERDEFINED", "TRUSS_WEB_DIAGONAL"),
}
FAMILY_NAME = {
    "CT-BH": "Bottom heel: bottom chord end + end post + first diagonal",
    "CT-TH": "Top heel / bearing: top chord end + end post (bearing on column - not modelled)",
    "CT-BS": "Bottom chord splice at panel point + vertical + two diagonals",
    "CT-BC": "Bottom-chord centre: splice + king post + two diagonals",
    "CT-BV": "Bottom panel point: continuous chord + vertical",
    "CT-TV2": "Top panel point: continuous chord + vertical + two diagonals",
    "CT-TS": "Top chord splice at panel point + vertical",
    "CT-TA": "Ridge apex: both top-chord halves (chevron splice plates) + king post",
}
WARNINGS = {
    "Strength": "UNRESOLVED - R2 first-order in-plane screening only; member sizes indicative",
    "Buckling": "UNRESOLVED - flexural buckling only in R2; flexural-torsional buckling of double angles and Class 4 6 mm legs (70-75 mm angles, S355) to check",
    "JointCapacity": "UNRESOLVED - no gusset, block-tearing, net-section or bearing check",
    "BoltGroupDesign": "UNRESOLVED - bolt counts from the R2 take-off rule (max(2, F/100 kN) per web end); no bolt-group design",
    "ConnectionGeometry": "UNRESOLVED - concept detailing placeholders (gauge, pitch, end/edge distances, set-backs)",
    "RestraintRequirements": "UNRESOLVED - top chord relies on purlins + designed roof bracing; bottom-chord ties at <= 5.4 m assumed, not modelled",
    "MaterialGrade": "UNRESOLVED - S355JR assumed (R2), availability/certification and plate grade to confirm",
    "CorrosionProtection": "UNRESOLVED - two-coat paint assumed (R2 cost basis); galvanising decision pending (R2 s.11.3)",
    "FabricationTolerances": "UNRESOLVED - no execution class / tolerance specification (EN 1090 / SANS 2001 to be specified)",
    "BearingDetail": "UNRESOLVED - truss-to-column bearing not designed; conflicts with existing column cap/seat (C-01)",
    "BoltSlip": "UNRESOLVED - clearance-hole slip not modelled; R2 recommends preloaded splice bolts or pre-camber",
}
CLASSIFICATION = {
    "name": "SG-ROOF-BOQ",
    "source": "Southgate project BOQ codes aligned to RICS NRM2 Work Section 15 'Structural metalwork' (item numbering to be confirmed by the QS)",
    "refs": {
        "SG-15-FRAMING": "Structural metalwork - framing, fabrication: roof trusses built up from paired angle sections (measured by mass)",
        "SG-15-FITTINGS": "Structural metalwork - fittings: gusset, splice and packing plates (measured by mass)",
        "SG-15-BOLTS": "Structural metalwork - bolts: bolt sets with nuts and washers (enumerated by type)",
        "SG-15-ASSEMBLY": "Structural metalwork - fabricated assemblies (connection / built-up member / truss) - information grouping, not measured",
    },
}


class OptBAuthor:
    def __init__(self, f, rules, basis, namespace, run_id, storey_name="03 Roof"):
        self.f, self.rules, self.basis, self.ns, self.run_id = f, rules, basis, namespace, run_id
        self.storey = next(s for s in f.by_type("IfcBuildingStorey") if s.Name == storey_name)
        self.zst = float(self.storey.Elevation or 0.0)
        ctxs = f.by_type("IfcGeometricRepresentationSubContext")
        self.body = next(c for c in ctxs if c.ContextIdentifier == "Body" and c.TargetView == "MODEL_VIEW")
        self.axis_ctx = next(c for c in ctxs if c.ContextIdentifier == "Axis" and c.ContextType == "Model")
        self.created = []           # every new IfcElement
        self.by_sid = {}
        self.types = {}
        self.profiles = {}
        self.psets_shared = {}
        self.rel_buffer = defaultdict(list)
        self.rules_sha = hashlib.sha256(json.dumps(rules, sort_keys=True, default=str).encode()).hexdigest()
        self._materials()
        self._classification()

    # ------------------------------------------------------------------ low-level helpers
    def guid(self, sid):
        return guid_for(sid, self.ns)

    def pt(self, xyz):
        return self.f.createIfcCartesianPoint(tuple(float(round(v, 7)) for v in xyz))

    def dr(self, v):
        return self.f.createIfcDirection(tuple(float(round(c, 9)) for c in v))

    def a2p(self, o, z=(0, 0, 1), x=(1, 0, 0)):
        return self.f.createIfcAxis2Placement3D(self.pt(o), self.dr(z), self.dr(x))

    def place(self, world_origin, z=(0, 0, 1), x=(1, 0, 0)):
        o = [world_origin[0], world_origin[1], world_origin[2] - self.zst]
        return self.f.createIfcLocalPlacement(self.storey.ObjectPlacement, self.a2p(o, z, x))

    def val(self, v):
        f = self.f
        if isinstance(v, bool):
            return f.create_entity("IfcBoolean", v)
        if isinstance(v, int):
            return f.create_entity("IfcInteger", v)
        if isinstance(v, float):
            return f.create_entity("IfcReal", float(v))
        s = str(v)
        return f.create_entity("IfcText", s) if len(s) > 255 else f.create_entity("IfcLabel", s)

    def pset(self, products, name, props):
        f = self.f
        ps = f.create_entity("IfcPropertySet", GlobalId=ifcopenshell.guid.new(), Name=name,
                             HasProperties=[f.create_entity("IfcPropertySingleValue", Name=k, NominalValue=self.val(v))
                                            for k, v in props.items() if v is not None])
        products = products if isinstance(products, (list, tuple)) else [products]
        types = [p for p in products if p.is_a("IfcTypeObject")]
        occ = [p for p in products if not p.is_a("IfcTypeObject")]
        for t in types:                       # IFC4: type properties via HasPropertySets (no IfcRelDefinesByProperties)
            t.HasPropertySets = list(t.HasPropertySets or []) + [ps]
        if occ:
            f.create_entity("IfcRelDefinesByProperties", GlobalId=ifcopenshell.guid.new(), RelatedObjects=occ,
                            RelatingPropertyDefinition=ps)
        return ps

    def shared(self, key, name, props):
        if key not in self.psets_shared:
            self.psets_shared[key] = (self.pset([], name, props), [])
        return key

    def attach_shared(self, key, products):
        self.psets_shared[key][1].extend(products if isinstance(products, list) else [products])

    def flush_shared(self):
        for key, (ps, prods) in self.psets_shared.items():
            if prods:
                self.f.create_entity("IfcRelDefinesByProperties", GlobalId=ifcopenshell.guid.new(), RelatedObjects=prods,
                                     RelatingPropertyDefinition=ps)

    # ------------------------------------------------------------------ materials / classification
    def _materials(self):
        f = self.f
        M = self.rules["material"]
        self.mat_steel = API.material.add_material(f, name="SOUTHGATE-OPTB-STEEL-S355JR-PROVISIONAL", category="steel")
        self.mat_steel.Description = "Hot-rolled structural steel, grade S355JR PROVISIONAL (R2 basis); specification not approved"
        self.mat_bolt = API.material.add_material(f, name="SOUTHGATE-OPTB-BOLT-GR8.8-PROVISIONAL", category="steel")
        self.mat_bolt.Description = "Bolt sets property class 8.8 with class 8 nuts PROVISIONAL (R2 working assumption)"
        for m, grade in ((self.mat_steel, "S355JR (PROVISIONAL)"), (self.mat_bolt, "8.8 / 8 (PROVISIONAL)")):
            ps = API.pset.add_pset(f, product=m, name="Pset_MaterialCommon")
            API.pset.edit_pset(f, pset=ps, properties={"MassDensity": float(M["density_kg_m3"])})
            p2 = f.create_entity("IfcMaterialProperties", Name="SOUTHGATE_MaterialSpecification", Material=m,
                                 Properties=[f.create_entity("IfcPropertySingleValue", Name=k, NominalValue=self.val(v)) for k, v in {
                                     "Grade": grade, "SpecificationStatus": "PROVISIONAL - not approved",
                                     "Source": "R2 Option B working assumption (config/option_b/detailing_rules.yaml)",
                                     "Coating": M["coating"]["value"], "Corrosivity": M["corrosivity"]["value"]}.items()])
        style = API.style.add_style(f, name="SOUTHGATE-OPTB-STEEL")
        API.style.add_surface_style(f, style=style, ifc_class="IfcSurfaceStyleShading",
                                    attributes={"SurfaceColour": {"Name": None, "Red": 0.42, "Green": 0.47, "Blue": 0.53}, "Transparency": 0.0})
        API.style.assign_material_style(f, material=self.mat_steel, style=style, context=self.body)
        style2 = API.style.add_style(f, name="SOUTHGATE-OPTB-BOLT")
        API.style.add_surface_style(f, style=style2, ifc_class="IfcSurfaceStyleShading",
                                    attributes={"SurfaceColour": {"Name": None, "Red": 0.75, "Green": 0.62, "Blue": 0.18}, "Transparency": 0.0})
        API.style.assign_material_style(f, material=self.mat_bolt, style=style2, context=self.body)
        self.styles = {"steel": style, "bolt": style2}

    def _classification(self):
        f = self.f
        c = f.create_entity("IfcClassification", Source="Southgate BIM project", Edition=REV, Name=CLASSIFICATION["name"],
                            Description=CLASSIFICATION["source"])
        self.cls_refs = {k: f.create_entity("IfcClassificationReference", Identification=k, Name=v, ReferencedSource=c)
                         for k, v in CLASSIFICATION["refs"].items()}
        self.cls_assign = defaultdict(list)

    # ------------------------------------------------------------------ types
    def l_profile(self, name):
        if name not in self.profiles:
            s = AngleSec.from_rules(name, self.rules)
            self.profiles[name] = self.f.create_entity("IfcLShapeProfileDef", ProfileType="AREA", ProfileName=name,
                                                       Depth=s.b, Width=s.b, Thickness=s.t, FilletRadius=s.r1, EdgeRadius=s.r2)
        return self.profiles[name]

    def member_type(self, role, section):
        key = ("M", role, section)
        if key in self.types:
            return self.types[key]
        ptype, etype = ROLE_PTYPE[role]
        sid = f"SOUTHGATE-RTB-TYPE-MEMBER-{role}-{section}"
        t = API.root.create_entity(self.f, ifc_class="IfcMemberType", predefined_type=ptype, name=f"SG-OPTB-{role}-{section}")
        t.GlobalId = self.guid(sid)
        if ptype == "USERDEFINED":
            t.ElementType = etype
        t.Description = f"Option B truss {etype.lower().replace('_', ' ')}: single equal angle {section} (one of a back-to-back pair)"
        ps = API.material.add_material_set(self.f, name=f"SG-OPTB-{section}", set_type="IfcMaterialProfileSet")
        API.material.add_profile(self.f, profile_set=ps, material=self.mat_steel, profile=self.l_profile(section))
        API.material.assign_material(self.f, products=[t], type="IfcMaterialProfileSet", material=ps)
        s = AngleSec.from_rules(section, self.rules)
        self.pset(t, "SOUTHGATE_SteelSpecification", {
            "ProfileDesignation": section, "ProfileStandard": "EN 10056-1 equal angle (SAISC tabulated) - availability to confirm",
            "LegLength_mm": round(s.b * 1000, 1), "Thickness_mm": round(s.t * 1000, 1), "RootRadius_mm": round(s.r1 * 1000, 1),
            "ToeRadius_mm": round(s.r2 * 1000, 1), "CatalogueArea_cm2": round(s.A * 1e4, 2), "CentroidDistance_e_mm": round(s.e * 1000, 1),
            "NominalMassPerMetre_kg": s.kg_m, "SteelGrade": "S355JR - PROVISIONAL", "Coating": "two-coat paint - PROVISIONAL (galvanising undecided)",
            "BuiltUpArrangement": "2L back-to-back, 10 mm gap (gusset / packing plates)", "BoltBackmark_mm": round(s.gauge * 1000),
            "MaxBoltOnBackmark": s.max_bolt, "MemberRole": etype, "SizeStatus": "CONCEPT_UNVERIFIED (R2 indicative size, not for fabrication)",
            "QuantityMeasurementMethod": "cut length x catalogue mass per metre (nominal); volume from native profile geometry",
            "SourceReference": "R2 Option B, central scenario member schedule (config/option_b/r2_basis.json)"})
        self.cls_assign["SG-15-FRAMING"].append(t)
        self.types[key] = t
        return t

    def plate_type(self, kind, thickness, size=None):
        key = ("P", kind, round(thickness, 4), tuple(size) if size else None)
        if key in self.types:
            return self.types[key]
        tmm = round(thickness * 1000)
        nm = {"GUSSET": f"SG-OPTB-GUSSET-{tmm}", "SPLICE": f"SG-OPTB-SPLICE-{tmm}",
              "PACKER": f"SG-OPTB-PACKER-{round(size[0] * 1000)}x{round(size[1] * 1000)}x{tmm}" if size else None}[kind]
        t = API.root.create_entity(self.f, ifc_class="IfcPlateType", predefined_type="USERDEFINED", name=nm)
        t.GlobalId = self.guid("SOUTHGATE-RTB-TYPE-" + nm)
        t.ElementType = {"GUSSET": "GUSSET_PLATE", "SPLICE": "SPLICE_PLATE", "PACKER": "PACKING_PLATE"}[kind]
        ls = API.material.add_material_set(self.f, name=nm, set_type="IfcMaterialLayerSet")
        layer = API.material.add_layer(self.f, layer_set=ls, material=self.mat_steel)
        layer.LayerThickness = thickness
        API.material.assign_material(self.f, products=[t], type="IfcMaterialLayerSet", material=ls)
        status = {"GUSSET": "R2 (10 mm gussets)", "SPLICE": "PLACEHOLDER (thickness not in R2)", "PACKER": "R2 (fills 10 mm gap); size PLACEHOLDER"}[kind]
        self.pset(t, "SOUTHGATE_SteelSpecification", {
            "PlateRole": t.ElementType, "Thickness_mm": tmm, "ThicknessStatus": status, "SteelGrade": "S355JR - PROVISIONAL (plate grade not in R2)",
            "Coating": "two-coat paint - PROVISIONAL", "SizeStatus": "CONCEPT_UNVERIFIED", "HolesModelled": kind != "PACKER",
            "QuantityMeasurementMethod": "net plate area (holes deducted) x thickness x 7850 kg/m3" if kind != "PACKER" else "plate area x thickness x 7850 kg/m3 (hole not modelled)",
            "SourceReference": "config/option_b/detailing_rules.yaml"})
        if kind == "PACKER":
            L, W = size
            prof = self.f.create_entity("IfcRectangleProfileDef", ProfileType="AREA", ProfileName=nm, XDim=L, YDim=W)
            solid = self.f.create_entity("IfcExtrudedAreaSolid", SweptArea=prof, Position=self.a2p((0, 0, 0)), ExtrudedDirection=self.dr((0, 0, 1)), Depth=thickness)
            rep = self.f.create_entity("IfcShapeRepresentation", ContextOfItems=self.body, RepresentationIdentifier="Body", RepresentationType="SweptSolid", Items=[solid])
            t.RepresentationMaps = [self.f.create_entity("IfcRepresentationMap", MappingOrigin=self.a2p((0, 0, 0)), MappedRepresentation=rep)]
        self.cls_assign["SG-15-FITTINGS"].append(t)
        self.types[key] = t
        return t

    def bolt_type(self, dia, length, grip):
        key = ("B", dia, round(length, 4), round(grip, 4))
        if key in self.types:
            return self.types[key]
        c = self.rules["bolts"]["diameters"][dia]
        nm = f"SG-OPTB-BOLTSET-{dia}x{round(length * 1000)}-8.8-G{round(grip * 1000)}"
        t = API.root.create_entity(self.f, ifc_class="IfcMechanicalFastenerType", predefined_type="BOLT", name=nm)
        t.GlobalId = self.guid("SOUTHGATE-RTB-TYPE-" + nm)
        t.NominalDiameter, t.NominalLength = c["d"], length
        API.material.assign_material(self.f, products=[t], type="IfcMaterial", material=self.mat_bolt)
        f = self.f
        def hexagon(s):
            R = s / math.sqrt(3)
            pts = [(R * math.cos(math.radians(30 + 60 * i)), R * math.sin(math.radians(30 + 60 * i))) for i in range(6)]
            return f.create_entity("IfcArbitraryClosedProfileDef", ProfileType="AREA",
                                   OuterCurve=f.createIfcPolyline([f.createIfcCartesianPoint(p) for p in pts + [pts[0]]]))
        ow, iw, hw = c["washer"]
        items = [
            f.create_entity("IfcExtrudedAreaSolid", SweptArea=hexagon(c["head_s"]), Position=self.a2p((0, 0, -c["head_k"])), ExtrudedDirection=self.dr((0, 0, 1)), Depth=c["head_k"]),
            f.create_entity("IfcExtrudedAreaSolid", SweptArea=f.create_entity("IfcCircleProfileDef", ProfileType="AREA", Radius=c["d"] / 2), Position=self.a2p((0, 0, 0)), ExtrudedDirection=self.dr((0, 0, 1)), Depth=length),
            f.create_entity("IfcExtrudedAreaSolid", SweptArea=f.create_entity("IfcCircleHollowProfileDef", ProfileType="AREA", Radius=ow / 2, WallThickness=(ow - iw) / 2), Position=self.a2p((0, 0, grip)), ExtrudedDirection=self.dr((0, 0, 1)), Depth=hw),
            f.create_entity("IfcExtrudedAreaSolid", SweptArea=hexagon(c["nut_s"]), Position=self.a2p((0, 0, grip + hw)), ExtrudedDirection=self.dr((0, 0, 1)), Depth=c["nut_m"]),
        ]
        rep = f.create_entity("IfcShapeRepresentation", ContextOfItems=self.body, RepresentationIdentifier="Body", RepresentationType="SweptSolid", Items=items)
        t.RepresentationMaps = [f.create_entity("IfcRepresentationMap", MappingOrigin=self.a2p((0, 0, 0)), MappedRepresentation=rep)]
        self.pset(t, "SOUTHGATE_FastenerSpecification", {
            "BoltDesignation": f"{dia} x {round(length * 1000)} hexagon head, property class 8.8 - PROVISIONAL",
            "NutDesignation": f"{dia} hexagon nut class 8 - PROVISIONAL", "WasherDesignation": f"{dia} plain washer {round(iw * 1000)}/{round(ow * 1000)}/{round(hw * 1000)} - PROVISIONAL",
            "BoltsPerSet": 1, "NutsPerSet": 1, "WashersPerSet": 1, "SetCompositionStatus": "PLACEHOLDER - washer count not stated in R2",
            "Grip_mm": round(grip * 1000, 1), "HoleDiameter_mm": round(c["d0"] * 1000), "HoleType": "normal round clearance - PLACEHOLDER",
            "Preload": "not specified (R2: preloaded bolts at chord splices or pre-camber recommended)",
            "Coating": "to match steelwork - PROVISIONAL", "DiameterStatus": "R2 working assumption M20 8.8; M16 on 60 mm legs (PLACEHOLDER)",
            "CountStatus": "ASSUMPTION_DEPENDENT - R2 take-off rule, not a bolt-group design",
            "GeometryNote": "lightweight representation: hexagon head, plain shank, washer, nut (no threads, no chamfers)",
            "SourceReference": "config/option_b/detailing_rules.yaml"})
        self.cls_assign["SG-15-BOLTS"].append(t)
        self.types[key] = t
        return t

    def assembly_type(self, kind, key, name, desc, props):
        k = ("A", kind, key)
        if k in self.types:
            return self.types[k]
        t = API.root.create_entity(self.f, ifc_class="IfcElementAssemblyType",
                                   predefined_type="TRUSS" if kind == "TRUSS" else "USERDEFINED", name=name)
        t.GlobalId = self.guid("SOUTHGATE-RTB-TYPE-" + name)
        if kind != "TRUSS":
            t.ElementType = kind
        t.Description = desc
        self.pset(t, "SOUTHGATE_AssemblyTypeSpecification", props)
        self.cls_assign["SG-15-ASSEMBLY"].append(t)
        self.types[k] = t
        return t

    # ------------------------------------------------------------------ element creation
    def new(self, ifc_class, sid, desc, placement, rep=None, ptype=None, otype=None, tag=None, **attrs):
        e = self.f.create_entity(ifc_class, GlobalId=self.guid(sid), Name=sid, Description=desc, ObjectPlacement=placement,
                                 Representation=rep, Tag=tag, **attrs)
        if ptype:
            e.PredefinedType = ptype
        if otype:
            e.ObjectType = otype
        self.created.append(e)
        self.by_sid[sid] = e
        return e

    def pds(self, reps):
        return self.f.create_entity("IfcProductDefinitionShape", Representations=reps)

    def body_rep(self, items, rtype="SweptSolid"):
        return self.f.create_entity("IfcShapeRepresentation", ContextOfItems=self.body, RepresentationIdentifier="Body",
                                    RepresentationType=rtype, Items=items)

    def plate_outline_profile(self, outline, holes, s0, z0, name):
        f = self.f
        pts = [(round(s - s0, 6), round(z - z0, 6)) for s, z in outline]
        P = Polygon(pts)
        if not P.exterior.is_ccw:
            pts = pts[::-1]
        outer = f.createIfcPolyline([f.createIfcCartesianPoint(p) for p in pts + [pts[0]]])
        if not holes:
            return f.create_entity("IfcArbitraryClosedProfileDef", ProfileType="AREA", ProfileName=name, OuterCurve=outer)
        inner = [f.create_entity("IfcCircle", Position=f.createIfcAxis2Placement2D(f.createIfcCartesianPoint((round(s - s0, 6), round(z - z0, 6)))), Radius=d / 2)
                 for s, z, d in holes]
        return f.create_entity("IfcArbitraryProfileDefWithVoids", ProfileType="AREA", ProfileName=name, OuterCurve=outer, InnerCurves=inner)

    # ------------------------------------------------------------------ one truss
    def build_truss(self, T: OptionBTruss, asm):
        f = self.f
        R2 = self.basis
        tid = T.tid
        x = T.x
        parts_of = defaultdict(list)
        status_keys = self._status_psets()
        basis_key = self.shared("basis", "SOUTHGATE_OptionB_Basis", {
            "Implementation": "Option B - 12-bay Warren truss with verticals, bolted paired-angle steel members",
            "GoverningReference": R2["title"], "ReferenceStatus": R2["status"],
            "R2ResultsSHA256": R2["sources"]["study_results"]["sha256"], "R2ReportSHA256": R2["sources"]["report_pdf"]["sha256"],
            "DetailingRules": "config/option_b/detailing_rules.yaml (NOT APPROVED)", "DetailingRulesSHA256": self.rules_sha,
            "Revision": REV, "Run": self.run_id, "EngineeringCertification": "NOT CLAIMED - no registered engineer has reviewed R2 or this model",
            "NotForConstruction": True})
        warn_key = self.shared("warn", "SOUTHGATE_EngineeringWarnings", WARNINGS)

        # ---------------- built-up members and their angles
        bum = {}
        for m in T.members.values():
            sid_bu = T.sid(m.id)
            a3 = [0.0, m.a[0], m.a[1]]
            n1 = T.nodes[m.n1]
            org = T.world(n1[0] + m.t_start * m.a[0], n1[1] + m.t_start * m.a[1])
            role_txt = ROLE_PTYPE[m.role][1].lower().replace("_", " ")
            e = self.new("IfcElementAssembly", sid_bu, f"{tid} {role_txt} {m.id}: 2{m.section} back-to-back, cut length {m.length:.3f} m",
                         self.place(org, a3, [1, 0, 0]), ptype="USERDEFINED", otype="BUILT_UP_MEMBER_2L", tag=f"{T.ttype}/{m.id}",
                         AssemblyPlace="NOTDEFINED")
            bum[m.id] = e
            parts_of[asm].append(e)
            mt = self.member_type(m.role, m.section)
            sec = AngleSec.from_rules(m.section, self.rules)
            but = self.assembly_type("BUILT_UP_MEMBER_2L", (m.role, m.section), f"SG-OPTB-BUM-{m.role}-2{m.section}",
                                     f"Built-up {role_txt}: two {m.section} back-to-back with 10 mm gap, packing plates at <= 1.2 m clear",
                                     {"Role": ROLE_PTYPE[m.role][1], "Section": "2" + m.section, "Angles": 2, "Gap_mm": 10,
                                      "NominalMassPerMetrePair_kg": round(2 * sec.kg_m, 2), "PackerRule": self.rules["packers"]["modelled_rule"]["value"],
                                      "PackerBolt": "M16" if sec.max_bolt == "M16" else "M20", "SizeStatus": "CONCEPT_UNVERIFIED"})
            self.rel_buffer[("type", but)].append(e)
            Lnode = float(np.linalg.norm(np.array(m.node2_sz) - np.array(m.node1_sz)))
            for ang in m.angles:
                sid = T.sid(ang.id)
                solid = f.create_entity("IfcExtrudedAreaSolid", SweptArea=self.l_profile(m.section), Position=self.a2p((0, 0, 0)),
                                        ExtrudedDirection=self.dr((0, 0, 1)), Depth=ang.length)
                axis = f.create_entity("IfcShapeRepresentation", ContextOfItems=self.axis_ctx, RepresentationIdentifier="Axis",
                                       RepresentationType="Curve3D", Items=[f.createIfcPolyline([self.pt((0, 0, 0)), self.pt((0, 0, ang.length))])])
                ptype, etype = ROLE_PTYPE[m.role]
                el = self.new("IfcMember", sid, f"{tid} {m.id} angle {ang.side} ({'+x' if ang.side == 'A' else '-x'} side) L{m.section[1:]} cut {ang.length:.3f} m",
                              self.place(ang.origin, ang.axis_z, ang.axis_x), self.pds([axis, self.body_rep([solid])]),
                              ptype=ptype, otype=etype if ptype == "USERDEFINED" else None, tag=f"{T.ttype}/{m.id}-{ang.side}")
                self.rel_buffer[("type", mt)].append(el)
                self.rel_buffer[("profile_usage", m.section)].append(el)
                parts_of[e].append(el)
                self.pset(el, "SOUTHGATE_Provenance", {"StableId": sid, "SourceKey": f"OPTB:{tid}:{m.id}:{ang.side}", "Origin": "NEW - Option B implementation",
                                                       "ParentTruss": asm.Name, "ParentAssembly": sid_bu, "Revision": REV, "MigrationRun": self.run_id,
                                                       "Representation": f"SweptSolid (IfcLShapeProfileDef {m.section}, IfcMaterialProfileSetUsage CardinalPoint 5)",
                                                       "NativeRepresentation": True})
                F = m.r2_force
                self.pset(el, "SOUTHGATE_MemberData", {
                    "TrussLine": T.line, "TrussType": T.ttype, "MemberMark": m.id, "Role": etype, "R2Group": m.group, "AngleSide": ang.side,
                    "Section": m.section, "BuiltUpSection": "2" + m.section, "StartNode": m.n1, "EndNode": m.n2,
                    "SettingOutLength_m": round(Lnode, 4), "CutLength_m": round(ang.length, 4),
                    "R2_Nc_kN": F.get("Nc_kN"), "R2_Nt_kN": F.get("Nt_kN"), "R2_Utilisation": F.get("util") if "util" in F else F.get("util_max"),
                    "R2ForceBasis": f"R2 central scenario, analysed line {T.force_line} (envelope over ULS combinations)",
                    "SizeStatus": "CONCEPT_UNVERIFIED", "GeometryStatus": "PRELIMINARY_DESIGN"})
                self.attach_shared(status_keys["member"], el)
            # packers + packer bolts
            for pid in m.packers:
                p = T.plates[pid]
                pt_ = self.plate_type("PACKER", p.thickness, p.size)
                c = p.centre_sz
                a = np.array([0.0, p.axis_sz[0], p.axis_sz[1]])
                el = self.new("IfcPlate", pid, f"{tid} {m.id} packing plate {round(p.size[0]*1000)}x{round(p.size[1]*1000)}x{round(p.thickness*1000)}",
                              self.place([x + p.x0, Y0 + c[0], c[1]], [1, 0, 0], a.tolist()),
                              self.body_rep_mapped(pt_), ptype="USERDEFINED", otype="PACKING_PLATE", tag=f"{T.ttype}/{shape_hash(p)}")
                self.rel_buffer[("type", pt_)].append(el)
                self.rel_buffer[("layer_usage", pt_)].append(el)
                parts_of[e].append(el)
                self._prov(el, pid, f"OPTB:{tid}:{m.id}:packer", asm.Name, sid_bu, "MappedRepresentation (IfcRectangleProfileDef extrusion, type map)")
                self.attach_shared(status_keys["packer"], el)
                b = T.bolts[pid + "-BLT"]
                be = self._bolt(T, b, asm, sid_bu, status_keys)
                parts_of[e].append(be)
                self._connect(T, [(b, be)], sid_bu)
            self.attach_shared(status_keys["builtup"], e)
            self._prov(e, sid_bu, f"OPTB:{tid}:{m.id}", asm.Name, asm.Name, "aggregate (2 angles + packing plates + packer bolts)")

        # ---------------- connections
        for J in T.joints.values():
            P = J.s, J.z
            fam = J.family
            ct = self.assembly_type("CONNECTION_" + fam, J.type_key, self._conn_type_name(J, T), FAMILY_NAME[fam], self._conn_type_props(J, T))
            ce = self.new("IfcElementAssembly", J.id, f"{tid} panel point {J.node}: {FAMILY_NAME[fam]}",
                          self.place(T.world(*P), [1, 0, 0], [0, 1, 0]), ptype="USERDEFINED", otype="CONNECTION_" + fam,
                          tag=f"{T.ttype}/{J.node}", AssemblyPlace="NOTDEFINED")
            self.rel_buffer[("type", ct)].append(ce)
            parts_of[asm].append(ce)
            # gusset
            g = T.plates[J.gusset]
            gt = self.plate_type("GUSSET", g.thickness)
            ge = self._plate(T, g, gt, asm, J.id, "GUSSET_PLATE", status_keys["gusset"])
            parts_of[ce].append(ge)
            sps = []
            for spid in J.splice_plates:
                sp = T.plates[spid]
                st_ = self.plate_type("SPLICE", sp.thickness)
                se = self._plate(T, sp, st_, asm, J.id, "SPLICE_PLATE", status_keys["splice"])
                parts_of[ce].append(se)
                sps.append(se)
            bolt_els = {}
            for bid in J.bolts:
                be = self._bolt(T, T.bolts[bid], asm, J.id, status_keys)
                parts_of[ce].append(be)
                bolt_els[bid] = be
            self._connect(T, [(T.bolts[bid], be) for bid, be in bolt_els.items()], J.id)
            r2 = {f"R2_F_{mid}_kN": v["F_max_kN"] for mid, v in J.r2_forces.items()}
            nb = defaultdict(int)
            for bid in J.bolts:
                nb[T.bolts[bid].role] += 1
            self.pset(ce, "SOUTHGATE_ConnectionInstance", {
                "TrussLine": T.line, "TrussType": T.ttype, "PanelPoint": J.node, "Family": fam, "ConnectionType": ct.Name,
                "Position_s_m": J.s, "Position_z_m": J.z, "ChordSplice": J.splice, "RiggingTabProvision": J.rigging_tab,
                "ConnectedMembers": ";".join(f"{mid}({'start' if e == 1 else 'end' if e == 2 else 'through'})" for mid, e in J.members),
                "BoltsWeb": nb["WEB"], "BoltsChord": nb["CHORD"], "BoltsSplice": nb["SPLICE"], "BoltsTotal": len(J.bolts),
                "R2RuleChordToGussetBolts": 4, "R2RuleSpliceBolts": 8 if J.splice else 0,
                "BoltCountStatus": "ASSUMPTION_DEPENDENT (R2 take-off rule)", "GeometryStatus": "CONCEPT_UNVERIFIED",
                "Interfaces": " | ".join(J.interfaces), **r2})
            self._prov(ce, J.id, f"OPTB:{tid}:{J.node}", asm.Name, asm.Name, "aggregate (gusset + splice plates + bolt sets)")
            self.attach_shared(status_keys["connection"], ce)

        # ---------------- the truss assembly (identity reused)
        tt = self.assembly_type("TRUSS", T.ttype, f"SG-OPTB-{T.ttype}", self.rules["truss_types"][T.ttype]["name"], {
            "TrussType": T.ttype, "Lines": ",".join(str(v) for v in self.rules["truss_types"][T.ttype]["lines"]),
            "Configuration": "12-bay Warren with verticals, paired back-to-back angles bolted to 10 mm gussets",
            "SectionsFromR2Line": T.sec_line, "TopChord": "2" + T.sec_tc.name, "BottomChord": "2" + T.sec_bc.name,
            "Note": self.rules["truss_types"][T.ttype].get("note", "-"), "SizeStatus": "CONCEPT_UNVERIFIED"})
        self.rel_buffer[("type", tt)].append(asm)
        for parent, kids in parts_of.items():
            API.aggregate.assign_object(f, products=kids, relating_object=parent)
        self.attach_shared(basis_key, [e for e in self.created if e not in getattr(self, "_basis_done", set())])
        self._basis_done = set(self.created)
        self.attach_shared(warn_key, [asm])
        return asm

    # ------------------------------------------------------------------ helpers for plates / bolts
    def body_rep_mapped(self, typ):
        f = self.f
        mi = f.create_entity("IfcMappedItem", MappingSource=typ.RepresentationMaps[0],
                             MappingTarget=f.create_entity("IfcCartesianTransformationOperator3D", LocalOrigin=self.pt((0, 0, 0))))
        return self.pds([self.body_rep([mi], "MappedRepresentation")])

    def _prov(self, el, sid, key, truss, parent, rep):
        self.pset(el, "SOUTHGATE_Provenance", {"StableId": sid, "SourceKey": key, "Origin": "NEW - Option B implementation", "ParentTruss": truss,
                                               "ParentAssembly": parent, "Revision": REV, "MigrationRun": self.run_id, "Representation": rep,
                                               "NativeRepresentation": True})

    def _plate(self, T, p, typ, asm, joint_sid, otype, status_key):
        outline = p.outline_sz
        s0 = min(s for s, _ in outline)
        z0 = min(z for _, z in outline)
        prof = self.plate_outline_profile(outline, p.holes_sz, s0, z0, p.id)
        solid = self.f.create_entity("IfcExtrudedAreaSolid", SweptArea=prof, Position=self.a2p((0, 0, 0)), ExtrudedDirection=self.dr((0, 0, 1)), Depth=p.thickness)
        el = self.new("IfcPlate", p.id, f"{T.tid} {otype.lower().replace('_', ' ')} at {p.joint.split('-J-')[-1]} t={round(p.thickness*1000)} mm"
                      + (" with rigging pick-up tab" if p.rigging_tab else ""),
                      self.place([T.x + p.x0, Y0 + s0, z0], [1, 0, 0], [0, 1, 0]), self.pds([self.body_rep([solid])]),
                      ptype="USERDEFINED", otype=otype, tag=f"{T.ttype}/{shape_hash(p)}")
        self.rel_buffer[("type", typ)].append(el)
        self.rel_buffer[("layer_usage", typ)].append(el)
        g, n = plate_area_net(p)
        self.pset(el, "SOUTHGATE_PlateData", {"PartMark": shape_hash(p), "GrossArea_m2": round(g, 6), "NetArea_m2": round(n, 6),
                                              "Holes": len(p.holes_sz), "Thickness_mm": round(p.thickness * 1000), "RiggingTab": p.rigging_tab,
                                              "Joint": joint_sid})
        self._prov(el, p.id, f"OPTB:{T.tid}:{p.joint.split('-J-')[-1]}:{otype}", asm.Name, joint_sid,
                   "SweptSolid (IfcArbitraryProfileDefWithVoids, bolt holes as voids, IfcMaterialLayerSetUsage AXIS3)")
        self.attach_shared(status_key, el)
        return el

    def _bolt(self, T, b, asm, parent_sid, status_keys):
        bt = self.bolt_type(b.diameter, b.length, b.grip)
        el = self.new("IfcMechanicalFastener", T.sid(b.id) if not b.id.startswith("SOUTHGATE") else b.id,
                      f"{T.tid} bolt set {b.diameter}x{round(b.length*1000)} ({b.role.lower()}) through {' / '.join(s.split('-')[-1] if s.startswith('SOUTHGATE') else s for s in b.stack)}",
                      self.place([T.x + b.x_head, Y0 + b.s, b.z], [-1, 0, 0], [0, 1, 0]), self.body_rep_mapped(bt),
                      ptype="BOLT", tag=f"{T.ttype}/{b.diameter}x{round(b.length*1000)}", NominalDiameter=bt.NominalDiameter, NominalLength=bt.NominalLength)
        self.rel_buffer[("type", bt)].append(el)
        self.pset(el, "SOUTHGATE_Provenance", {"StableId": el.Name, "SourceKey": f"OPTB:{T.tid}:{b.role}", "Origin": "NEW - Option B implementation",
                                               "ParentTruss": asm.Name, "ParentAssembly": parent_sid, "Revision": REV, "MigrationRun": self.run_id,
                                               "Representation": "MappedRepresentation (bolt set type map)", "NativeRepresentation": True,
                                               "Stack": " | ".join(T.sid(s) if not s.startswith("SOUTHGATE") else s for s in b.stack), "BoltRole": b.role})
        self.attach_shared(status_keys["bolt"], el)
        return el

    def _connect(self, T, bolts, label):
        """IfcRelConnectsWithRealizingElements: every plate in a bolt's stack <-> every angle in the same stack."""
        groups = defaultdict(list)
        for b, be in bolts:
            plates = [c for c in b.stack if c.startswith("SOUTHGATE")]
            angles = [c for c in b.stack if not c.startswith("SOUTHGATE")]
            for pl in plates:
                for an in angles:
                    groups[(pl, an)].append(be)
        for (pl, an), bes in groups.items():
            pe, ae = self.by_sid.get(pl), self.by_sid.get(T.sid(an))
            if pe is None or ae is None:
                raise KeyError((pl, an))
            self.f.create_entity("IfcRelConnectsWithRealizingElements", GlobalId=self.guid(f"REL:{pl}:{an}"), Name=f"{label} {an}",
                                 Description="bolted - concept detail", RelatingElement=pe, RelatedElement=ae,
                                 RealizingElements=list(dict.fromkeys(bes)), ConnectionType="BOLTED")

    def _conn_type_name(self, J, T):
        h = hashlib.sha1(J.type_key.encode()).hexdigest()[:6]
        return f"SG-OPTB-{J.family}-{T.ttype}{'-TAB' if J.rigging_tab else ''}-{h}"

    def _conn_type_props(self, J, T):
        comp = defaultdict(int)
        for bid in J.bolts:
            b = T.bolts[bid]
            comp[f"{b.diameter}x{round(b.length*1000)}"] += 1
        return {"Family": J.family, "FamilyDescription": FAMILY_NAME[J.family], "TrussType": T.ttype, "TypeKey": J.type_key,
                "GussetThickness_mm": 10, "SplicePlates": len(J.splice_plates), "SplicePlateThickness_mm": 8 if J.splice_plates else 0,
                "BoltSetsPerInstance": len(J.bolts), "BoltSetsByType": json.dumps(dict(comp)), "RiggingTab": J.rigging_tab,
                "GussetGeometry": "instance-specific outline from the detailing rules (set-backs, gauge, pitch, end/edge distances)",
                "DesignStatus": "CONCEPT_UNVERIFIED", "BoltPatternStatus": "ASSUMPTION_DEPENDENT (R2 take-off rule)",
                "Propagation": "change config/option_b/detailing_rules.yaml (rules) and rebuild the candidate; instance counts per type are scheduled"}

    def _status_psets(self):
        if hasattr(self, "_sk"):
            return self._sk
        base = {"EngineeringVerified": False, "EngineeringCertification": "NOT CLAIMED",
                "VerificationNote": "R2 is a preliminary options appraisal; no registered engineer has reviewed it or this model",
                "SourceDesignStatus": "R2 Option B (recommended), preliminary"}
        S = {
            "truss": ("PRELIMINARY_DESIGN", "Truss geometry per R2 Option B (12 bays, 15 deg, 32.4 m) on unchanged supports; setting-out adjusted to the roof envelope (DEV-01)",
                      {"GeometryStatus": "PRELIMINARY_DESIGN", "MemberSizeStatus": "CONCEPT_UNVERIFIED", "ConnectionStatus": "CONCEPT_UNVERIFIED"}),
            "builtup": ("CONCEPT_UNVERIFIED", "Built-up 2L member, R2 indicative size", {"GeometryStatus": "PRELIMINARY_DESIGN", "MemberSizeStatus": "CONCEPT_UNVERIFIED"}),
            "member": ("CONCEPT_UNVERIFIED", "Indicative R2 member size (not for fabrication)", {"GeometryStatus": "PRELIMINARY_DESIGN", "MemberSizeStatus": "CONCEPT_UNVERIFIED"}),
            "connection": ("CONCEPT_UNVERIFIED", "Concept connection detail from placeholder rules", {"ConnectionStatus": "CONCEPT_UNVERIFIED", "BoltPatternStatus": "ASSUMPTION_DEPENDENT"}),
            "gusset": ("CONCEPT_UNVERIFIED", "Gusset outline generated from placeholder detailing rules; 10 mm per R2", {"ConnectionStatus": "CONCEPT_UNVERIFIED"}),
            "splice": ("CONCEPT_UNVERIFIED", "Splice plate placeholder (thickness not in R2; splice not designed)", {"ConnectionStatus": "CONCEPT_UNVERIFIED"}),
            "packer": ("CONCEPT_UNVERIFIED", "Packing plate per placeholder spacing rule (R2: 1 per 1.2 m)", {"QuantityStatus": "ASSUMPTION_DEPENDENT"}),
            "bolt": ("CONCEPT_UNVERIFIED", "Bolt set position/count from the R2 take-off rule and placeholder gauge/pitch", {"BoltPatternStatus": "ASSUMPTION_DEPENDENT", "QuantityStatus": "ASSUMPTION_DEPENDENT"}),
        }
        self._sk = {}
        for k, (st, basis, extra) in S.items():
            self._sk[k] = self.shared("status-" + k, "SOUTHGATE_DesignStatus", {"DesignStatus": st, "StatusBasis": basis, **extra, **base})
        return self._sk

    # ------------------------------------------------------------------ finish: bulk relationships
    def finish(self):
        f = self.f
        for (kind, k), els in self.rel_buffer.items():
            if kind == "type":
                API.type.assign_type(f, related_objects=els, relating_type=k, should_map_representations=False)
        prof_sets = {}
        for (kind, k), els in self.rel_buffer.items():
            if kind == "profile_usage":
                for e in els:
                    u = f.create_entity("IfcMaterialProfileSetUsage", ForProfileSet=ue.get_material(ue.get_type(e)), CardinalPoint=5)
                    f.create_entity("IfcRelAssociatesMaterial", GlobalId=ifcopenshell.guid.new(), RelatedObjects=[e], RelatingMaterial=u)
            elif kind == "layer_usage":
                ls = ue.get_material(k)
                u = None
                for e in els:
                    u = f.create_entity("IfcMaterialLayerSetUsage", ForLayerSet=ls, LayerSetDirection="AXIS3", DirectionSense="POSITIVE", OffsetFromReferenceLine=0.0)
                    f.create_entity("IfcRelAssociatesMaterial", GlobalId=ifcopenshell.guid.new(), RelatedObjects=[e], RelatingMaterial=u)
        for code, ts in self.cls_assign.items():
            if ts:
                f.create_entity("IfcRelAssociatesClassification", GlobalId=ifcopenshell.guid.new(), RelatedObjects=ts,
                                RelatingClassification=self.cls_refs[code])
        self.flush_shared()
