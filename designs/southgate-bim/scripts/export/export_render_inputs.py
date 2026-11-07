"""Write plain-JSON inputs for the Blender render scripts (no numpy / pickle inside Blender)."""
import json, pickle
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
plan = pickle.load(open(ROOT / "work/plan/plan.pkl", "rb"))
inv = json.load(open(ROOT / "source/geometry_inventory.json", encoding="utf-8"))
members = {e["stable_id"]: e["members"] for e in plan["elements"]}
rows = {r["source"]: r for r in plan["rows"]}
excluded_colls = set(json.load(open(ROOT / "work/plan/plan_summary.json")) and [])
meta = {}
for o in inv["objects"]:
    r = rows[o["name"]]
    disp = r["disposition"]
    in_scope = not (disp == "EXCLUDED_INTENTIONALLY" and ("outside" in r["reason"] or "Detached" in r["reason"]
                                                           or "Site works" in r["reason"] or "site works" in r["reason"]))
    if r.get("ifc_class") in ("IfcSpace", "IfcSpatialZone") or o["collections"][:1] in (["Spaces"], ["Wheelchair"]):
        in_scope = False          # space / zone volumes are not rendered on either side
    meta[o["name"]] = {"coll": o["collections"][0] if o["collections"] else "", "zmin": o["aabb_min"][2],
                       "visible": bool(o["visible"]), "in_scope": in_scope, "visual_only": disp == "VISUAL_ONLY"}
json.dump(members, open(ROOT / "work/plan/members_by_stable_id.json", "w"))
json.dump(meta, open(ROOT / "work/plan/source_render_meta.json", "w"))
print("render inputs:", len(members), "elements,", len(meta), "source objects")
