"""Independent validation of a SAVED IFC in a clean interpreter (run with python -I).

  .venv/Scripts/python -I scripts/validate/validate_ifc.py bim/southgate.ifc --out reports/audits/ifc_validation.json [--express]
Uses only ifcopenshell (no project code), so the result does not depend on the build.
"""
import argparse, json, logging, multiprocessing, sys, time
from collections import Counter

import numpy as np
import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util.element as ue
import ifcopenshell.validate

ap = argparse.ArgumentParser()
ap.add_argument("ifc")
ap.add_argument("--out", required=True)
ap.add_argument("--express", action="store_true", help="also evaluate EXPRESS WHERE rules (slow)")
a = ap.parse_args()
t0 = time.time()
f = ifcopenshell.open(a.ifc)
res = {"file": a.ifc, "schema": f.schema, "ifcopenshell": ifcopenshell.version}

# 1 schema validation
class Collect(logging.Handler):
    def __init__(self):
        super().__init__()
        self.items = []
    def emit(self, record):
        self.items.append(record.getMessage() if not isinstance(record.msg, dict) else json.dumps(record.msg, default=str))
log = logging.getLogger("validate")
h = Collect()
log.addHandler(h)
log.setLevel(logging.DEBUG)
try:
    ifcopenshell.validate.validate(f, log, express_rules=a.express)
except Exception as ex:
    h.items.append(f"validator exception: {ex!r}")
res["schema_validation"] = {"issues": len(h.items), "examples": h.items[:25], "express_rules_checked": a.express}

# 2 hierarchy
proj = f.by_type("IfcProject")
sites = f.by_type("IfcSite")
blds = f.by_type("IfcBuilding")
storeys = f.by_type("IfcBuildingStorey")
res["hierarchy"] = {"projects": len(proj), "sites": len(sites), "buildings": len(blds),
                    "storeys": [(s.Name, s.Elevation) for s in sorted(storeys, key=lambda s: s.Elevation)],
                    "site_in_project": all(ue.get_aggregate(s) == proj[0] for s in sites),
                    "building_in_site": all(ue.get_aggregate(b) in sites for b in blds),
                    "storeys_in_building": all(ue.get_aggregate(s) in blds for s in storeys)}
units = [(u.UnitType, getattr(u, "Prefix", None), u.Name) for u in proj[0].UnitsInContext.Units]
res["units"] = units

# 3 elements
els = [e for e in f.by_type("IfcElement") if not e.is_a("IfcOpeningElement")]
res["element_counts"] = dict(Counter(e.is_a() for e in els).most_common())
uncontained = [e.Name for e in els if not ue.get_container(e) and not ue.get_aggregate(e)]
res["spatial"] = {"elements": len(els), "uncontained_and_unaggregated": len(uncontained), "examples": uncontained[:10],
                  "spaces": len(f.by_type("IfcSpace")), "spatial_zones": len(f.by_type("IfcSpatialZone"))}
nomat = [e.Name for e in els if ue.get_material(e, should_inherit=True) is None and not e.is_a("IfcElementAssembly")
         and not e.is_a("IfcCurtainWall") and not e.is_a("IfcRoof") and not e.is_a("IfcStair")]
res["materials"] = {"elements_without_material": len(nomat), "examples": nomat[:10],
                    "usage_layer": sum(1 for e in els if (m := ue.get_material(e)) is not None and m.is_a("IfcMaterialLayerSetUsage")),
                    "usage_profile": sum(1 for e in els if (m := ue.get_material(e)) is not None and m.is_a("IfcMaterialProfileSetUsage")),
                    "materials": len(f.by_type("IfcMaterial"))}
typed = sum(1 for e in els if ue.get_type(e))
res["types"] = {"typed_elements": typed, "type_objects": len(f.by_type("IfcTypeObject"))}
ops = f.by_type("IfcOpeningElement")
res["openings"] = {"openings": len(ops), "filled": sum(1 for o in ops if o.HasFillings),
                   "voiding": sum(1 for o in ops if o.VoidsElements),
                   "doors": len(f.by_type("IfcDoor")), "windows": len(f.by_type("IfcWindow")),
                   "doors_windows_filling_openings": sum(1 for e in f.by_type("IfcDoor") + f.by_type("IfcWindow") if e.FillsVoids)}
asm = f.by_type("IfcElementAssembly") + f.by_type("IfcCurtainWall") + f.by_type("IfcRoof") + f.by_type("IfcStair")
res["assemblies"] = {"assemblies": len(asm), "by_class": dict(Counter(x.is_a() for x in asm)),
                     "empty": [x.Name for x in asm if not ue.get_parts(x)]}
res["systems"] = [(s.Name, len(ue.get_grouped_by(s) if hasattr(ue, "get_grouped_by") else [])) for s in f.by_type("IfcDistributionSystem")]
withq = sum(1 for e in els if any(k.startswith("Qto_") for k in ue.get_psets(e, qtos_only=True)))
res["quantities"] = {"elements_with_base_quantities": withq, "of": len(els)}
st = Counter((ue.get_pset(e, "SOUTHGATE_DesignStatus") or {}).get("DesignStatus") for e in els)
res["design_status"] = dict(st)
ver = sum(1 for e in els if (ue.get_pset(e, "SOUTHGATE_DesignStatus") or {}).get("EngineeringVerified"))
res["engineering_verified_claims"] = ver
g = Counter(e.GlobalId for e in f.by_type("IfcRoot"))
res["guids"] = {"total": len(g), "duplicates": [k for k, v in g.items() if v > 1]}
rep = Counter()
for e in els:
    if e.Representation:
        for r in e.Representation.Representations:
            if r.RepresentationIdentifier == "Body":
                rep[r.RepresentationType] += 1
res["body_representation_types"] = dict(rep)

# 4 overall geometry (world coords) of physical elements
s = ifcopenshell.geom.settings()
s.set("use-world-coords", True)
it = ifcopenshell.geom.iterator(s, f, max(1, multiprocessing.cpu_count() - 1), include=els)
mn, mx, n, bad = np.full(3, 1e9), np.full(3, -1e9), 0, 0
if it.initialize():
    while True:
        sh = it.get()
        v = np.asarray(sh.geometry.verts).reshape(-1, 3)
        if len(v):
            mn = np.minimum(mn, v.min(axis=0)); mx = np.maximum(mx, v.max(axis=0)); n += 1
        if not it.next():
            break
res["geometry"] = {"elements_with_geometry": n, "of": len(els), "world_min": mn.round(3).tolist(),
                   "world_max": mx.round(3).tolist(), "extent_m": (mx - mn).round(3).tolist()}
res["seconds"] = round(time.time() - t0, 1)
json.dump(res, open(a.out, "w"), indent=1, default=str)
print(json.dumps({k: res[k] for k in ("schema_validation", "hierarchy", "spatial", "openings", "guids", "geometry", "quantities")}, default=str)[:3000])
