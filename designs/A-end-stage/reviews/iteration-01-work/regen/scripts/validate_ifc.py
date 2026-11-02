"""Validate the exported IFC independently of the exporter.

  .venv/Scripts/python scripts/validate_ifc.py model/church_3000_concept.ifc model/blender_manifest.json reports/ifc_validation.json

Checks: schema validation (ifcopenshell.validate), units, spatial structure, containment,
GlobalId uniqueness, element counts vs the Blender manifest, congregation seat count
from property sets, seat placements vs Blender, geometry tessellation of every product
(ifcopenshell.geom), opening/filling relationships and model extents.
"""
import json
import logging
import multiprocessing
import sys
from collections import Counter
from pathlib import Path

import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util.element as uel
import ifcopenshell.util.placement as upl
import ifcopenshell.util.unit as uunit
import ifcopenshell.validate


def main(ifc_path, manifest_path, out_path):
    f = ifcopenshell.open(ifc_path)
    M = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    res = {"ifc": ifc_path, "ifcopenshell": ifcopenshell.version, "schema": f.schema, "checks": []}

    def check(cid, desc, ok, value, crit, sev="FAIL"):
        res["checks"].append({"id": cid, "description": desc, "result": "PASS" if ok else sev, "value": value,
                              "criterion": crit})

    # 1 schema validation
    class Collect(logging.Handler):
        def __init__(self):
            super().__init__()
            self.records = []

        def emit(self, record):
            self.records.append(self.format(record))

    logger = logging.getLogger("ifcval")
    logger.setLevel(logging.DEBUG)
    h = Collect()
    logger.addHandler(h)
    ifcopenshell.validate.validate(f, logger, express_rules=False)
    errs = [r for r in h.records]
    res["schema_validation_messages"] = errs[:50]
    check("IFC-SCHEMA", "ifcopenshell.validate schema/attribute validation (express_rules=False)", not errs, len(errs),
          "0 messages")
    # 2 units
    scale = uunit.calculate_unit_scale(f)
    check("IFC-UNITS", "Length unit is metre (scale to SI = 1.0)", abs(scale - 1.0) < 1e-12, scale, "1.0")
    # 3 spatial structure
    storeys = sorted((s.Name, round(s.Elevation, 3)) for s in f.by_type("IfcBuildingStorey"))
    exp = sorted((lv["id"], round(lv["elevation"], 3)) for lv in M["levels"])
    check("IFC-STOREYS", "Storeys and elevations match Blender levels", storeys == exp, storeys, str(exp))
    check("IFC-HIERARCHY", "One IfcProject / IfcSite / IfcBuilding", [len(f.by_type(c)) for c in ("IfcProject", "IfcSite", "IfcBuilding")] == [1, 1, 1],
          [len(f.by_type(c)) for c in ("IfcProject", "IfcSite", "IfcBuilding")], "[1,1,1]")
    grids = f.by_type("IfcGrid")
    axes = sorted(a.AxisTag for g in grids for a in (g.UAxes or []) + (g.VAxes or []))
    exp_axes = sorted(list(M["grid"]["x_lines"]) + list(M["grid"]["y_lines"]))
    check("IFC-GRID", "IfcGrid axes match project grid", axes == exp_axes, len(axes), f"{len(exp_axes)} axes A-H / 1-12")
    # 4 containment
    uncontained = []
    for el in f.by_type("IfcElement"):
        if el.is_a("IfcOpeningElement"):
            continue
        if uel.get_container(el) is None and uel.get_aggregate(el) is None:
            uncontained.append(el.Name)
    check("IFC-CONTAIN", "Every IfcElement contained in a storey or aggregated in an assembly", not uncontained,
          uncontained[:10], "0")
    # 5 GlobalIds
    gids = [e.GlobalId for e in f.by_type("IfcRoot")]
    check("IFC-GUID", "GlobalIds unique", len(gids) == len(set(gids)), len(gids) - len(set(gids)), "0 duplicates")
    # 6 counts vs manifest
    man = Counter(f"{o['ifc_class']}:{o['predefined_type']}" for o in M["objects"])
    ifc = Counter()
    names = {o["name"] for o in M["objects"]}
    for e in f.by_type("IfcProduct"):
        if e.Name in names:  # enumerated predefined type: occurrence value, else inherited from its type
            pt = getattr(e, "PredefinedType", None)
            if not pt and uel.get_type(e) is not None:
                pt = getattr(uel.get_type(e), "PredefinedType", None)
            ifc[f"{e.is_a()}:{pt or ''}"] += 1
    diff = {k: [man.get(k, 0), ifc.get(k, 0)] for k in set(man) | set(ifc) if man.get(k, 0) != ifc.get(k, 0)}
    res["counts_by_class"] = dict(sorted(ifc.items()))
    check("IFC-COUNTS", "Element counts by class/predefined type equal Blender manifest", not diff, diff or len(M["objects"]),
          "identical")
    # 7 seat count from psets
    cong = []
    for e in f.by_type("IfcFurniture"):
        ps = uel.get_pset(e, "Pset_CA3000_Concept") or {}
        if ps.get("CountsTowardTarget") is True and ps.get("SeatType") == "congregation":
            cong.append(e)
    check("IFC-SEATS", "Congregation seats (Pset SeatType=congregation, CountsTowardTarget=True)", len(cong) == 3000,
          len(cong), "== 3000")
    typed = sum(1 for e in cong if uel.get_type(e) is not None and uel.get_type(e).PredefinedType == "CHAIR")
    check("IFC-SEAT-TYPE", "Congregation seats typed by IfcFurnitureType CHAIR (mapped representation)", typed == len(cong),
          typed, f"== {len(cong)}")
    # 8 seat placement vs Blender
    bl = {o["name"]: (o["matrix"][0][3], o["matrix"][1][3], o["matrix"][2][3]) for o in M["objects"]}
    worst = 0.0
    for e in cong:
        m = upl.get_local_placement(e.ObjectPlacement)
        p = (m[0][3], m[1][3], m[2][3])
        q = bl[e.Name]
        worst = max(worst, max(abs(p[i] - q[i]) for i in range(3)))
    check("IFC-SEAT-POS", "Max seat placement deviation IFC vs Blender manifest", worst < 1e-4, worst, "< 0.1 mm")
    # independent source: recompute seat coordinates with the layout engine (not via Blender/manifest)
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import auditorium_layout as al
    lay = al.compute(al.load_params())
    ref = {s["seat_id"]: (s["x"], s["y"], s["z_floor"]) for s in lay.seats}
    worst2, missing = 0.0, 0
    for e in cong:
        m = upl.get_local_placement(e.ObjectPlacement)
        if e.Name not in ref:
            missing += 1
            continue
        q = ref[e.Name]
        worst2 = max(worst2, max(abs(m[i][3] - q[i]) for i in range(3)))
    check("IFC-SEAT-POS-LAYOUT", "Max seat placement deviation IFC vs layout engine (independent of Blender)",
          worst2 < 1e-3 and missing == 0, {"max_dev_m": worst2, "ids_not_in_layout": missing}, "< 1 mm, 0 missing")
    nonid = sum(1 for o in M["objects"] if o["matrix"][0][3] == 0 and o["matrix"][1][3] == 0 and o["matrix"][2][3] == 0)
    check("IFC-MANIFEST-MATRIX", "Manifest objects with an all-zero translation (stale matrix guard)", nonid == 0, nonid, "0")
    # 9 openings
    voids = len(f.by_type("IfcRelVoidsElement"))
    fills = len(f.by_type("IfcRelFillsElement"))
    nfill = len(f.by_type("IfcDoor")) + len(f.by_type("IfcWindow"))
    check("IFC-OPENINGS", "Every door/window fills an opening that voids its host wall", voids == fills == nfill,
          [voids, fills, nfill], "voids == fills == doors+windows")
    # 10 geometry tessellation
    settings = ifcopenshell.geom.settings()
    settings.set("use-world-coords", True)
    it = ifcopenshell.geom.iterator(settings, f, multiprocessing.cpu_count())
    ok_ids, xs, ys, zs = set(), [], [], []
    if it.initialize():
        while True:
            shp = it.get()
            ok_ids.add(shp.id)
            v = shp.geometry.verts
            el = f.by_id(shp.id)
            if el.is_a("IfcBuildingElement") or el.is_a("IfcBuiltElement"):
                xs += v[0::3]
                ys += v[1::3]
                zs += v[2::3]
            if not it.next():
                break
    expected = [e for e in f.by_type("IfcProduct") if e.Representation and not e.is_a("IfcGrid")]
    failed = [e.Name for e in expected if e.id() not in ok_ids]
    check("IFC-GEOM", "Every product with a representation tessellates with ifcopenshell.geom", not failed,
          {"tessellated": len(ok_ids), "failed": len(failed), "first_failed": failed[:10]}, "0 failures")
    ext = [round(min(xs), 2), round(min(ys), 2), round(min(zs), 2), round(max(xs), 2), round(max(ys), 2), round(max(zs), 2)]
    res["building_element_extents"] = ext
    check("IFC-EXTENTS", "Building element extents plausible in metres", 55 < ext[3] - ext[0] < 75 and 85 < ext[4] - ext[1] < 95,
          ext, "~59-70 x ~88-92 m")
    res["summary"] = {k: sum(c["result"] == k for c in res["checks"]) for k in ("PASS", "FAIL", "WARN")}
    Path(out_path).write_text(json.dumps(res, indent=2), encoding="utf-8")
    print("IFCVAL_SUMMARY " + json.dumps(res["summary"]))
    for c in res["checks"]:
        print(c["result"], c["id"], json.dumps(c["value"])[:200])


if __name__ == "__main__":
    main(*sys.argv[1:4])
