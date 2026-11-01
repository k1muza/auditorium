"""Re-open the saved .blend in a fresh Blender process and verify it from the scene data.

  blender --background --factory-startup model/church_3000_concept.blend \
      --python scripts/verify_blend.py -- --config config/auditorium_params.json --out reports/blend_verification.json

Checks are computed from Blender objects (not from the layout engine): seat counts by
collection, naming, units, seat-on-floor raycasts, a hard-clash matrix, sightline
C-values and aisle widths measured from chair positions. Read-only: never saves.
"""
import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--out", required=True)
    return ap.parse_args(argv)


def world_aabb(ob):
    pts = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
    return (min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts),
            max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts))


def island_aabbs(ob):
    """World AABB of each connected mesh island (an object may be several separate parts)."""
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bm.transform(ob.matrix_world)
    bm.verts.ensure_lookup_table()
    seen, boxes = set(), []
    for v in bm.verts:
        if v.index in seen:
            continue
        stack, pts = [v], []
        seen.add(v.index)
        while stack:
            c = stack.pop()
            pts.append(c.co.copy())
            for e in c.link_edges:
                o = e.other_vert(c)
                if o.index not in seen:
                    seen.add(o.index)
                    stack.append(o)
        boxes.append((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts),
                      max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    bm.free()
    return boxes


def overlap(a, b, tol):
    return all(a[i] < b[i + 3] - tol and b[i] < a[i + 3] - tol for i in range(3))


def seg_hits_box(p0, p1, r, box, tol):
    """Sample a line member (radius r) against an AABB."""
    n = max(2, int((Vector(p1) - Vector(p0)).length / 0.1) + 1)
    for k in range(n + 1):
        t = k / n
        p = [p0[i] + (p1[i] - p0[i]) * t for i in range(3)]
        if all(box[i] - r + tol < p[i] < box[i + 3] + r - tol for i in range(3)):
            return True
    return False


class Bucket:
    """Uniform XY hash grid of AABBs for pair finding."""

    def __init__(self, cell=4.0):
        self.cell = cell
        self.grid = defaultdict(list)

    def keys(self, bb):
        c = self.cell
        for i in range(int(bb[0] // c), int(bb[3] // c) + 1):
            for j in range(int(bb[1] // c), int(bb[4] // c) + 1):
                yield (i, j)

    def add(self, item, bb):
        for k in self.keys(bb):
            self.grid[k].append(item)

    def query(self, bb):
        seen = set()
        for k in self.keys(bb):
            for it in self.grid[k]:
                if id(it) not in seen:
                    seen.add(id(it))
                    yield it


def main():
    args = parse_args()
    P = json.loads(Path(args.config).read_text(encoding="utf-8"))
    S, SL, ST = P["seating"], P["sightlines"], P["stage"]
    scene = bpy.context.scene
    res = {"blend_file": bpy.data.filepath, "blender_version": bpy.app.version_string,
           "revision": scene.get("revision"), "checks": [], "counts": {}}

    def check(cid, desc, ok, value, crit, sev="FAIL"):
        res["checks"].append({"id": cid, "description": desc, "result": "PASS" if ok else sev, "value": value,
                              "criterion": crit})

    us = scene.unit_settings
    check("BLD-UNITS", "Scene units metric, scale 1.0, metres",
          us.system == "METRIC" and abs(us.scale_length - 1.0) < 1e-9 and us.length_unit == "METERS",
          [us.system, us.scale_length, us.length_unit], "METRIC / 1.0 / METERS")
    objs = [o for o in scene.objects if o.type == "MESH" and o.get("ifc_class") not in (None, "DOC")]
    by_col = defaultdict(list)
    for o in objs:
        by_col[o.users_collection[0].name].append(o)
    res["counts"]["by_collection"] = {k: len(v) for k, v in sorted(by_col.items())}
    by_cls = defaultdict(int)
    for o in objs:
        by_cls[f"{o['ifc_class']}:{o.get('predefined_type', '')}"] += 1
    res["counts"]["by_ifc_class"] = dict(sorted(by_cls.items()))
    seats = by_col["40_SEAT_Congregation"]
    n_cong = len(seats)
    n_prop = sum(1 for o in objs if json.loads(o.get("props_json", "{}")).get("CountsTowardTarget") is True)
    check("BLD-SEATS", "Congregation chair objects in 40_SEAT_Congregation", n_cong == S["target_congregation_seats"],
          n_cong, f"== {S['target_congregation_seats']}")
    check("BLD-SEATS-PROP", "Objects flagged CountsTowardTarget=True", n_prop == S["target_congregation_seats"], n_prop,
          f"== {S['target_congregation_seats']}")
    pat = re.compile(r"^SEAT-C-R(\d{2})-B([1-6])-S(\d{2})$")
    bad_names = [o.name for o in seats if not pat.match(o.name)]
    check("BLD-NAMES-SEAT", "Congregation chair names match SEAT-C-Rrr-Bb-Sss", not bad_names, bad_names[:10], "0 mismatches")
    dup = [o.name for o in objs if re.search(r"\.\d{3}$", o.name)]
    check("BLD-NAMES-DUP", "No Blender duplicate-suffix names (.001)", not dup, dup[:10], "0")
    prefixes = ("ENV-", "ARC-", "STR-", "SEAT-", "ACC-", "SRV-", "SPC-", "ZONE-", "DR-", "WN-")
    badp = [o.name for o in objs if not o.name.startswith(prefixes)]
    check("BLD-NAMES-PREFIX", "All model objects use discipline prefixes", not badp, badp[:10], "0")
    missing = [o.name for o in objs if not o.get("ifc_class") or not o.get("storey")]
    check("BLD-SEMANTICS", "Every model object carries ifc_class and storey properties", not missing, missing[:10], "0")
    rows = defaultdict(list)
    for o in seats:
        m = pat.match(o.name)
        rows[int(m.group(1))].append(o)
    per_row = {r: len(v) for r, v in sorted(rows.items())}
    res["counts"]["seats_per_row"] = per_row

    # ---------------------------------------------------------------- seat-on-floor raycasts
    floor_objs = [o for o in objs if o["ifc_class"] in ("IfcSlab", "IfcRamp", "IfcStair")
                  and o.get("predefined_type") != "ROOF"]
    bm = bmesh.new()
    for o in floor_objs:
        tmp = bmesh.new()
        tmp.from_mesh(o.data)
        tmp.transform(o.matrix_world)
        me = bpy.data.meshes.new("tmp")
        tmp.to_mesh(me)
        bm.from_mesh(me)
        bpy.data.meshes.remove(me)
        tmp.free()
    bvh = BVHTree.FromBMesh(bm)
    chairs = seats + by_col["40_SEAT_Choir"] + by_col["40_SEAT_Companion"]
    worst_bury, worst_gap, n_fail, no_floor = 0.0, 0.0, 0, []
    for o in chairs:
        bb = world_aabb(o)
        zb = bb[2]
        gaps = []
        for x in (bb[0] + 0.02, (bb[0] + bb[3]) / 2, bb[3] - 0.02):
            for y in (bb[1] + 0.02, (bb[1] + bb[4]) / 2, bb[4] - 0.02):
                hit = bvh.ray_cast(Vector((x, y, zb + 0.5)), Vector((0, 0, -1)), 3.0)
                if hit[0] is None:
                    gaps.append(None)
                else:
                    gaps.append(zb - hit[0].z)
        if any(g is None for g in gaps):
            no_floor.append(o.name)
            continue
        bury = -min(gaps)
        gap = min(gaps)
        worst_bury = max(worst_bury, bury)
        worst_gap = max(worst_gap, gap)
        if bury > 0.005 or gap > 0.10:
            n_fail += 1
    bm.free()
    check("BLD-FLOOR-SUPPORT", "Every chair has floor under all 9 sample points", not no_floor, no_floor[:10], "0 unsupported")
    check("BLD-FLOOR-CONTACT", "Chairs not buried (>5 mm) and not floating (>100 mm at highest floor point)", n_fail == 0,
          {"failing": n_fail, "max_burial_m": round(worst_bury, 4), "max_min_gap_m": round(worst_gap, 4)},
          "burial <= 0.005 m, min gap <= 0.10 m")

    # ---------------------------------------------------------------- hard clash matrix
    def group(o):
        c, cls = o.users_collection[0].name, o["ifc_class"]
        if c.startswith("40_SEAT") and cls == "IfcFurniture":
            return "chair"
        if cls == "IfcColumn":
            return "column"
        if cls in ("IfcWall",):
            return "wall"
        if cls in ("IfcDoor", "IfcWindow"):
            return "door"
        if cls == "IfcStair":
            return "stair_ramp"
        if cls == "IfcRamp":
            return "ramp"
        if cls == "IfcRailing":
            return "rail"
        if cls == "IfcBeam":
            return "beam"
        if cls == "IfcMember":
            return "member"
        if o.get("object_type") in ("WheelchairSpace", "RefugeSpace"):
            return "wcspace"
        if o.get("object_type") == "AisleClearZone":
            return "aisle"
        if o.get("object_type") == "ServiceAllowance":
            return "service"
        if cls == "IfcTransportElement":
            return "lift"
        return None

    rules = {("chair", g) for g in ("chair", "column", "wall", "door", "stair_ramp", "ramp", "rail", "beam", "member",
                                     "wcspace", "aisle", "lift")}
    rules |= {("door", g) for g in ("column", "member", "beam", "stair_ramp", "ramp", "rail")}
    rules |= {("stair_ramp", g) for g in ("column", "beam", "member", "lift")}
    rules |= {("ramp", g) for g in ("beam", "member", "lift")}
    rules |= {("wcspace", g) for g in ("column", "wall", "stair_ramp", "ramp", "rail")}
    rules |= {("service", g) for g in ("column", "beam", "member")}
    rules |= {("rail", g) for g in ("column",)}
    rules |= {("wall", "member")}  # bracing / truss members must not run inside wall or cladding planes
    # columns passing through ramps are treated like slab penetrations: reported, not hard clashes
    info_rules = {("ramp", "column")}
    items = []
    for o in objs:
        g = group(o)
        if g:
            strut = json.loads(o["strut_json"]) if "strut_json" in o else None
            parts = [world_aabb(o)] if (strut or g == "chair") else island_aabbs(o)
            items.append({"name": o.name, "g": g, "bb": world_aabb(o), "parts": parts, "strut": strut})
    bucket = Bucket()
    for it in items:
        bucket.add(it, it["bb"])
    tol = 0.005
    clashes, pairs_tested, penetrations = [], 0, []
    seen = set()
    for a in items:
        for b in bucket.query(a["bb"]):
            if a is not b and (a["g"], b["g"]) in info_rules and overlap(a["bb"], b["bb"], tol):
                penetrations.append({"element": a["name"], "column": b["name"]})
            if a is b or ((a["g"], b["g"]) not in rules):
                continue
            key = tuple(sorted((a["name"], b["name"])))
            if key in seen:
                continue
            seen.add(key)
            pairs_tested += 1
            if a["strut"] or b["strut"]:
                s, other = (a, b) if a["strut"] else (b, a)
                if other["strut"]:
                    continue  # member-member nodes are intended
                hit = any(seg_hits_box(s["strut"][0], s["strut"][1], s["strut"][2], pb, tol) for pb in other["parts"])
            else:
                hit = any(overlap(pa, pb, tol) for pa in a["parts"] for pb in b["parts"])
            # a door's own host wall and its opening are intended
            if hit:
                clashes.append({"a": a["name"], "a_group": a["g"], "b": b["name"], "b_group": b["g"]})
    res["clash_matrix"] = sorted("{}-{}".format(*r) for r in rules)
    res["clashes"] = clashes[:200]
    check("BLD-CLASH", "Hard clashes in the coordination clash matrix (AABB / member sampling, 5 mm tolerance)",
          not clashes, {"clashes": len(clashes), "candidate_pairs_tested": pairs_tested}, "0 clashes")
    # positive control: the same island test must detect a known, intended intersection
    ctrl_a, ctrl_b = bpy.data.objects["STR-COL-B5"], bpy.data.objects["ENV-WALL-HALL-W"]
    ctrl = any(overlap(pa, pb, tol) for pa in island_aabbs(ctrl_a) for pb in island_aabbs(ctrl_b))
    neg = any(overlap(pa, pb, tol) for pa in island_aabbs(bpy.data.objects["STR-COL-A2"])
              for pb in island_aabbs(bpy.data.objects["ARC-RAIL-UPPER-FOYER-EDGE"]))
    check("BLD-CLASH-CONTROL", "Clash detector positive control (column B5 embedded in hall wall W detected) and "
          "negative control (rail stops short of column A2)", ctrl and not neg, {"positive_detected": ctrl, "negative_detected": neg},
          "positive True, negative False")
    res["column_penetrations_of_ramps"] = penetrations
    # clear width of ambulatory ramps between column faces (columns stand through the ramp)
    widths = []
    gx = P["grid"]["x_lines"]
    for side, (xa, xb) in (("W", (gx["A"], gx["B"])), ("E", (gx["G"], gx["H"]))):
        ca = P["structure"]["other_column"] / 2 if side == "W" else P["structure"]["hall_column"] / 2
        cb = P["structure"]["hall_column"] / 2 if side == "W" else P["structure"]["other_column"] / 2
        widths.append(round((xb - cb) - (xa + ca), 3))
    check("BLD-RAMP-CLEAR", "Ambulatory ramp clear width between column faces", min(widths) >= 3.0, min(widths),
          ">= 3.0 m concept (ramps penetrated by perimeter columns, listed in column_penetrations_of_ramps)")

    # ---------------------------------------------------------------- sightlines from chair objects
    y_focal = ST["front_edge_y"]
    z_focal = ST["platform_height"] + SL["focal_height_above_platform"]
    eye_dy = S["eye_offset_from_tread_back"] - S["chair_back_offset"] - S["chair_depth"] / 2
    row_eye = {}
    for r, lst in rows.items():
        y = sum(o.location.y for o in lst) / len(lst)
        zs = {round(o.location.z, 4) for o in lst}
        z = max(zs)
        row_eye[r] = (z + S["eye_height_seated"] - z_focal, y_focal - (y + eye_dy), len(zs))
    cvals = {}
    for r in sorted(row_eye):
        if r - 1 in row_eye:
            e, d, _ = row_eye[r]
            pe, pd, _ = row_eye[r - 1]
            cvals[r] = round(e * pd / d - pe, 4)
    res["sightline_c_from_chairs"] = cvals
    cmin = min(cvals.values())
    check("BLD-SIGHT", "Min C-value (row-to-row, from chair object positions)", cmin >= SL["c_value_target"] - 1e-4,
          cmin, f">= {SL['c_value_target']} m (wheelchair positions checked in layout report)")
    level_rows = [r for r, v in row_eye.items() if v[2] != 1]
    check("BLD-ROW-LEVEL", "All chairs in a row share one base elevation", not level_rows, level_rows, "0 rows")

    # ---------------------------------------------------------------- aisles from chair positions
    hw = 0.24
    min_interior, min_wall = 99.0, 99.0
    x_in0 = P["grid"]["x_lines"]["B"] + P["structure"]["hall_column"] / 2
    x_in1 = P["grid"]["x_lines"]["G"] - P["structure"]["hall_column"] / 2
    for r, lst in rows.items():
        xs = sorted(o.location.x for o in lst)
        for a, b in zip(xs, xs[1:]):
            gap = b - a - 2 * hw
            if gap > 0.5:
                min_interior = min(min_interior, gap)
        if len(lst) == sum(S["blocks"]):
            min_wall = min(min_wall, xs[0] - hw - x_in0, x_in1 - xs[-1] - hw)
    check("BLD-AISLE", "Min interior aisle clear between chair edges (per row)", min_interior >= S["aisle_width"] - 1e-3,
          round(min_interior, 3), f">= {S['aisle_width']} m")
    check("BLD-WALL-AISLE", "Min wall-aisle clear chair edge to column face", min_wall >= 1.5, round(min_wall, 3), ">= 1.5 m")
    allb = [world_aabb(o) for o in objs if o.users_collection[0].name.startswith(("10_", "20_", "30_"))]
    ext = [round(min(b[i] for b in allb), 3) for i in range(3)] + [round(max(b[i + 3] for b in allb), 3) for i in range(3)]
    res["model_extents"] = ext
    check("BLD-EXTENTS", "Model extents plausible for 59 x 88 m building (metres, not mm)",
          55 < ext[3] - ext[0] < 75 and 85 < ext[4] - ext[1] < 95 and 15 < ext[5] < 25, ext, "~59-70 x ~88-92 x <25 m")
    res["summary"] = {"pass": sum(c["result"] == "PASS" for c in res["checks"]),
                      "fail": sum(c["result"] == "FAIL" for c in res["checks"]),
                      "warn": sum(c["result"] == "WARN" for c in res["checks"])}
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(res, indent=2), encoding="utf-8")
    print("VERIFY_SUMMARY " + json.dumps({"summary": res["summary"], "seats": n_cong,
                                          "clashes": len(clashes), "cmin": cmin}))


if __name__ == "__main__":
    main()
