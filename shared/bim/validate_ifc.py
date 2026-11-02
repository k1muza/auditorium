"""Validate the exported IFC independently of the exporter.

  .venv/Scripts/python shared/bim/validate_ifc.py <model.ifc> <blender_manifest.json> <out.json> <layout.py> <config.json>

Shared copy of designs/A-end-stage/scripts/validate_ifc.py (PL08). Generalised: the layout engine used for the
independent seat check is passed in, and the extents check uses the layout's declared footprint (manifest
metrics.footprint_m = [x, y]) with a +-10 % band instead of A's hard-coded 59 x 88 m.

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


def main(ifc_path, manifest_path, out_path, layout_path, config_path):
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
    import importlib.util
    spec = importlib.util.spec_from_file_location("design_layout", layout_path)
    al = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    spec.loader.exec_module(al)
    lay = al.compute(al.load_params(config_path))
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
    zrange = {}
    if it.initialize():
        while True:
            shp = it.get()
            ok_ids.add(shp.id)
            v = shp.geometry.verts
            zrange[shp.id] = (min(v[2::3]), max(v[2::3]))
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
    fx, fy = M["metrics"]["footprint_m"]
    check("IFC-EXTENTS", "Building element extents plausible in metres (vs the layout's declared footprint)",
          0.9 * fx < ext[3] - ext[0] < 1.25 * fx and 0.9 * fy < ext[4] - ext[1] < 1.25 * fy,
          ext, f"~{fx:.0f} x {fy:.0f} m (+25 % for canopies/eaves)")
    # 11 storey assignment re-derived from IFC geometry (independent re-implementation of the stated rule:
    #    highest storey whose elevation <= reference z + 10 mm; reference = top for FLOOR/LANDING slabs, base
    #    otherwise; footings L00; Pset StoreyOverride names the storey explicitly)
    st_list = sorted(((s.Elevation, s.Name) for s in f.by_type("IfcBuildingStorey")))

    referenced = {}  # IfcSpatialZone has no inverse to its referencing storey in IFC4, so map the relationships
    for rel in f.by_type("IfcRelReferencedInSpatialStructure"):
        for p in rel.RelatedElements:
            referenced[p.id()] = rel.RelatingStructure

    def storey_of(el):
        c = uel.get_container(el)
        if c is None and uel.get_aggregate(el) is not None:
            agg = uel.get_aggregate(el)
            c = agg if agg.is_a("IfcBuildingStorey") else uel.get_container(agg)
        if c is None:
            c = referenced.get(el.id())
        return c.Name if c is not None else None

    wrong, per_storey, checked = [], Counter(), 0
    for el in list(f.by_type("IfcElement")) + list(f.by_type("IfcSpace")) + list(f.by_type("IfcSpatialZone")):
        if el.is_a("IfcOpeningElement") or el.is_a("IfcElementAssembly") or el.id() not in zrange:
            continue
        actual = storey_of(el)
        per_storey[actual] += 1
        ps = uel.get_pset(el, "Pset_CA3000_Concept") or {}
        if el.is_a("IfcFooting"):
            expect = "L00"
        elif ps.get("StoreyOverride"):
            expect = str(ps["StoreyOverride"]).split(":")[0]
        else:
            z0, z1 = zrange[el.id()]
            ref = z1 if el.is_a("IfcSlab") and el.PredefinedType in ("FLOOR", "LANDING") else z0
            expect = st_list[0][1]
            for elev, name in st_list:
                if ref >= elev - 0.01:
                    expect = name
        checked += 1
        if actual != expect:
            wrong.append(f"{el.Name}: in {actual}, rule gives {expect}")
    check("IFC-STOREY-RULE", "Storey of every element/space/zone matches its height (re-derived from IFC geometry)", not wrong,
          {"checked": checked, "mismatches": len(wrong), "first": wrong[:8]}, "0 mismatches")
    empty = [n for _, n in st_list if not per_storey.get(n)]
    res["elements_per_storey"] = dict(sorted(per_storey.items(), key=lambda kv: str(kv[0])))
    check("IFC-STOREY-NONEMPTY", "Every storey holds at least one element", not empty, res["elements_per_storey"], "no empty storey")
    # 12 materials and base quantities
    nomat = [e.Name for e in f.by_type("IfcElement") if not e.is_a("IfcOpeningElement") and not e.is_a("IfcElementAssembly")
             and uel.get_material(e, should_inherit=True) is None]
    check("IFC-MATERIALS", "Every built element has a (placeholder) material, directly or via its type", not nomat,
          {"without_material": len(nomat), "first": nomat[:8], "materials": sorted({m.Name for m in f.by_type("IfcMaterial")})},
          "0 without")
    qto_cls = ("IfcColumn", "IfcBeam", "IfcMember", "IfcSlab", "IfcWall", "IfcFooting", "IfcStair", "IfcRamp")
    noq = []
    for cls in qto_cls:
        for e in f.by_type(cls):
            q = uel.get_psets(e, qtos_only=True)
            vol = next((v.get("GrossVolume") for v in q.values() if v.get("GrossVolume")), None)
            if not vol or vol <= 0:
                noq.append(e.Name)
    check("IFC-QTO", "Columns, beams, members, slabs, walls, footings, stairs, ramps carry quantities with GrossVolume > 0", not noq,
          {"missing": len(noq), "first": noq[:8]}, "0 missing")
    noq2 = []
    for cls, key in (("IfcDoor", "Area"), ("IfcWindow", "Area"), ("IfcRailing", "Length"), ("IfcCovering", "GrossArea")):
        for e in f.by_type(cls):
            q = uel.get_psets(e, qtos_only=True)
            if not any((v.get(key) or 0) > 0 for v in q.values()):
                noq2.append(e.Name)
    check("IFC-QTO-2", "Doors/windows (Area), railings (Length), coverings (GrossArea) carry base quantities", not noq2,
          {"missing": len(noq2), "first": noq2[:8]}, "0 missing")
    res["summary"] = {k: sum(c["result"] == k for c in res["checks"]) for k in ("PASS", "FAIL", "WARN")}
    Path(out_path).write_text(json.dumps(res, indent=2), encoding="utf-8")
    print("IFCVAL_SUMMARY " + json.dumps(res["summary"]))
    for c in res["checks"]:
        print(c["result"], c["id"], json.dumps(c["value"])[:200])


if __name__ == "__main__":
    main(*sys.argv[1:6])
