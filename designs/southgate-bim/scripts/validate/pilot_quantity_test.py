"""Section-10 quantity prototype test on the pilot build.

1 extract quantities (ifc5d IFC4QtoBaseQuantities)      2 independently measure the source meshes
3 reconcile                                              4 modify a wall in an isolated copy (Bonsai)
5 recalculate                                            6 confirm the quantities update
7 save + reopen                                          8 confirm quantities and relationships persist
Outputs: reports/quantities/pilot_*.csv|json|md
"""
import csv, json, os, pickle, shutil, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
import numpy as np  # noqa: E402
import ifcopenshell  # noqa: E402
import ifcopenshell.util.element as ue  # noqa: E402
from southgate_bim.geometry import fit  # noqa: E402
from southgate_bim.quantities import qto  # noqa: E402

BLENDER = r"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe"
pilot_dir = sorted((ROOT / "work/builds").glob("*_pilot"))[-1]
W = ROOT / "work/pilot"
W.mkdir(parents=True, exist_ok=True)
OUT = ROOT / "reports/quantities"
OUT.mkdir(parents=True, exist_ok=True)
plan = pickle.load(open(ROOT / "work/plan/plan.pkl", "rb"))
cache = pickle.load(open(ROOT / "work/source_cache.pkl", "rb"))
inv = json.load(open(ROOT / "source/geometry_inventory.json", encoding="utf-8"))
objects = {o["name"]: o for o in inv["objects"]}
els = {e["global_id"]: e for e in plan["elements"]}

# 1 extract
src_ifc = W / "pilot_build.ifc"
shutil.copy2(pilot_dir / "southgate.ifc", src_ifc)
f = ifcopenshell.open(str(src_ifc))
qto.compute_base_quantities(f)
qto.add_project_quantities(f)
p_qto = W / "pilot_qto.ifc"
f.write(str(p_qto))
rows = qto.schedule_rows(f)
qto.write_csv(rows, OUT / "pilot_quantity_schedule.csv")


# 2 independent source measurement (from the cached source meshes, not from IFC)
def src_measure(names):
    vol, area, boxes = 0.0, 0.0, []
    for n in names:
        c = cache["objects"][n]
        m = cache["meshes"][c["mesh"]]
        w = fit.world_vertices(m["verts"], c["matrix"])
        rv = fit.robust_volume(w, m["faces"])
        vol += rv if rv is not None else float("nan")
        area += fit.mesh_area(w, m["faces"])
        b = fit.fit_box(w, m["faces"])
        if b is not None:
            boxes.append(sorted(b.dims))
    mn = np.min([objects[n]["aabb_min"] for n in names], axis=0)
    mx = np.max([objects[n]["aabb_max"] for n in names], axis=0)
    return {"volume": vol, "surface_area": area, "aabb_dims": (mx - mn).tolist(), "box_dims": boxes}


# 3 reconcile
rec = []
for r in rows:
    el = els.get(r["global_id"])
    if not el:
        continue
    s = src_measure(el["members"])
    ifc_vol = r["NetVolume_m3"] or r["GrossVolume_m3"]
    d = sorted(s["aabb_dims"])
    item = {"stable_id": r["stable_id"], "ifc_class": r["ifc_class"], "members": len(el["members"]),
            "ifc_net_volume_m3": r["NetVolume_m3"], "ifc_gross_volume_m3": r["GrossVolume_m3"],
            "source_mesh_volume_m3": round(s["volume"], 6),
            "ifc_length_m": r["Length_m"], "ifc_width_m": r["Width_m"], "ifc_height_m": r["Height_m"],
            "source_aabb_dims_sorted_m": [round(x, 4) for x in d],
            "ifc_gross_area_m2": r["GrossArea_m2"], "ifc_net_area_m2": r["NetArea_m2"]}
    if ifc_vol and s["volume"]:
        item["volume_rel_diff"] = round((ifc_vol - s["volume"]) / s["volume"], 5)
    e = f.by_guid(r["global_id"])
    if el["method"] == "wall_merged" or el.get("openings"):
        op_vol = 0.0
        for rel in e.HasOpenings:
            fl = rel.RelatedOpeningElement.HasFillings
            op_vol += 0
        item["explanation"] = ("consolidated wall: source = pieces only (no material in openings); "
                               "IFC NetVolume = gross wall minus openings -> should equal the source piece volume")
    elif r["ifc_class"] in ("IfcDoor", "IfcWindow"):
        item["explanation"] = ("representation change: parametric door/window body (lining+panel) replaces the "
                               "modelled frame/leaf/glass parts; overall Width/Height are the reconciled quantities")
    else:
        item["explanation"] = "same geometry (swept solid fitted to source) - expect agreement within 1 %"
    rec.append(item)
with open(OUT / "pilot_reconciliation.csv", "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=sorted({k for x in rec for k in x}))
    w.writeheader()
    w.writerows(rec)

# 4 modify in an isolated copy through Bonsai
wall = next(r for r in rows if r["ifc_class"] == "IfcWall" and r["migration_rule"] in ("ANNEX-WALL",) or
            r["ifc_class"] == "IfcWall")
mod = W / "pilot_modified_by_bonsai.ifc"
if mod.exists():
    mod.unlink()
env = dict(os.environ, BLENDER_USER_RESOURCES=os.path.join(os.environ["LOCALAPPDATA"], "SouthgateBIM", "blender_user"))
cp = subprocess.run([BLENDER, "-b", "--python-exit-code", "1", "--python",
                     str(ROOT / "scripts/validate/bonsai_modify_wall.py"), "--", "--in", str(p_qto), "--out", str(mod),
                     "--wall", wall["stable_id"], "--add-height", "0.5", "--add-length", "1.0"],
                    capture_output=True, text=True, env=env, timeout=1200)
(W / "bonsai_modify.log").write_text(cp.stdout[-20000:] + "\n---stderr---\n" + cp.stderr[-20000:], encoding="utf-8")
edit = json.loads(next(l for l in cp.stdout.splitlines() if l.startswith("BONSAI_EDIT")).split(" ", 1)[1])

# 5 recalculate  6 confirm update (stored values in the modified file are stale until recomputed)
g = ifcopenshell.open(str(mod))
we = g.by_guid(wall["global_id"])
stale = ue.get_pset(we, "Qto_WallBaseQuantities") or {}
qto.compute_base_quantities(g)
qto.add_project_quantities(g)
fresh = ue.get_pset(we, "Qto_WallBaseQuantities") or {}
mod_q = W / "pilot_modified_requantified.ifc"
g.write(str(mod_q))
# 7 save + reopen  8 persistence
h = ifcopenshell.open(str(mod_q))
he = h.by_guid(wall["global_id"])
persist = ue.get_pset(he, "Qto_WallBaseQuantities") or {}
orig = ifcopenshell.open(str(p_qto))
checks = {
    "wall": wall["stable_id"], "bonsai_edit": edit,
    "before_qto": {k: wall[k] for k in ("Length_m", "Height_m", "GrossArea_m2", "NetArea_m2", "GrossVolume_m3", "NetVolume_m3")},
    "stale_qto_in_modified_file": {k: stale.get(k) for k in ("Length", "Height", "GrossSideArea", "NetVolume")},
    "recomputed_qto": {k: fresh.get(k) for k in ("Length", "Height", "GrossSideArea", "NetSideArea", "GrossVolume", "NetVolume")},
    "persisted_after_reopen": {k: persist.get(k) for k in ("Length", "Height", "GrossSideArea", "NetVolume")},
    "expected_gross_side_area": round((wall["Length_m"] + 1.0) * (wall["Height_m"] + 0.5), 4),
}
checks["quantities_updated"] = (abs(fresh.get("Length", 0) - (wall["Length_m"] + 1.0)) < 1e-6 and
                                abs(fresh.get("Height", 0) - (wall["Height_m"] + 0.5)) < 1e-6)
checks["stale_detected"] = abs((stale.get("Length") or 0) - (fresh.get("Length") or 0)) > 1e-6
checks["persisted"] = persist == fresh
rel = {}
for name, fl in (("original", orig), ("modified_reopened", h)):
    rel[name] = {"elements": len(fl.by_type("IfcElement")), "openings": len(fl.by_type("IfcOpeningElement")),
                 "fills": len(fl.by_type("IfcRelFillsElement")), "voids": len(fl.by_type("IfcRelVoidsElement")),
                 "types": len(fl.by_type("IfcRelDefinesByType")), "containment": len(fl.by_type("IfcRelContainedInSpatialStructure")),
                 "aggregates": len(fl.by_type("IfcRelAggregates")), "qto_sets": len([p for p in fl.by_type("IfcElementQuantity")])}
checks["relationships"] = rel
checks["relationships_persist"] = all(rel["original"][k] == rel["modified_reopened"][k] for k in rel["original"])
json.dump(checks, open(OUT / "pilot_modification_test.json", "w"), indent=1, default=float)
print(json.dumps(checks, indent=1, default=float))
