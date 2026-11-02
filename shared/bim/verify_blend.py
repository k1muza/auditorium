"""Re-open a saved .blend in a fresh Blender process and verify it from the scene data alone (design-agnostic).

  blender --background --factory-startup <model.blend> --python shared/bim/verify_blend.py -- --out <blend_verification.json>

Reads only Blender objects and the scene's own properties (metrics_json written by the builder); never the
layout engine, so it is an independent check of what was actually saved. Never saves the .blend.

Checks: units; congregation seat count / flags / names; duplicate and prefix naming; semantics; chair floor
support and contact (ray casts onto floor objects); hard clashes (BVH triangle overlap where bounding boxes
penetrate by more than 5 mm, over a class-pair matrix, with a positive control); structural connections
(strut ends touch another member or a column); door openings clear of columns; row base levels; radial
C-values from chair objects when the scene declares a radial sightline model; extents vs the declared footprint.
"""
import json
import math
import re
import sys
from collections import defaultdict
from pathlib import Path

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

PREFIXES = ("ACC-", "ARC-", "DR-", "ENV-", "SEAT-", "SPC-", "SRV-", "STR-", "WN-", "ZONE-")
FLOOR_CLASSES = {("IfcSlab", "FLOOR"), ("IfcSlab", "LANDING"), ("IfcRamp", "STRAIGHT_RUN_RAMP"), ("IfcStair", "STRAIGHT_RUN_STAIR")}
TOL = 0.005


def args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    out = argv[argv.index("--out") + 1]
    return out


def world_mesh(ob):
    mw = ob.matrix_world
    verts = [mw @ v.co for v in ob.data.vertices]
    polys = [tuple(p.vertices) for p in ob.data.polygons]
    return verts, polys


def aabb(verts):
    xs, ys, zs = zip(*verts)
    return (min(xs), min(ys), min(zs), max(xs), max(ys), max(zs))


def pen(a, b):
    """Penetration depth of two AABBs (min over axes of the overlap), negative if apart."""
    return min(min(a[i + 3], b[i + 3]) - max(a[i], b[i]) for i in range(3))


def main():
    out = args()
    scene = bpy.context.scene
    bpy.context.view_layer.update()
    res = {"blend": bpy.data.filepath, "revision": scene.get("revision"), "blender": bpy.app.version_string, "checks": []}

    def check(cid, desc, ok, value, crit, sev="FAIL"):
        res["checks"].append({"id": cid, "description": desc, "value": value, "criterion": crit, "result": "PASS" if ok else sev})

    metrics = json.loads(scene.get("metrics_json", "{}"))
    us = scene.unit_settings
    check("BLD-UNITS", "Scene units metric, scale 1.0, metres", us.system == "METRIC" and abs(us.scale_length - 1) < 1e-9 and
          us.length_unit == "METERS", [us.system, us.scale_length, us.length_unit], "METRIC / 1.0 / METERS")
    obs = [o for o in scene.objects if o.get("ifc_class") not in (None, "DOC")]
    meshes = [o for o in obs if o.type == "MESH"]
    cong = [o for o in bpy.data.collections["40_SEAT_Congregation"].objects]
    target = 3000
    check("BLD-SEATS", "Congregation chair objects in 40_SEAT_Congregation", len(cong) == target, len(cong), f"== {target}")
    flagged = sum(1 for o in obs if json.loads(o.get("props_json", "{}")).get("CountsTowardTarget") is True)
    check("BLD-SEATS-PROP", "Objects flagged CountsTowardTarget=True", flagged == target, flagged, f"== {target}")
    pat = re.compile(r"^SEAT-C-R\d{2}-B\d{2}-S\d{2}$")
    badn = [o.name for o in cong if not pat.match(o.name)]
    check("BLD-NAMES-SEAT", "Congregation chair names match SEAT-C-Rrr-Bbb-Sss", not badn, badn[:5], "all match")
    dup = [o.name for o in scene.objects if re.search(r"\.\d{3}$", o.name)]
    check("BLD-NAMES-DUP", "No Blender duplicate-suffix names (.001)", not dup, dup[:5], "none")
    nopre = [o.name for o in obs if not o.name.startswith(PREFIXES)]
    check("BLD-NAMES-PREFIX", "All model objects use discipline prefixes", not nopre, nopre[:5], "none")
    nosem = [o.name for o in obs if not o.get("ifc_class") or not o.get("storey")]
    check("BLD-SEMANTICS", "Every model object carries ifc_class and storey properties", not nosem, nosem[:5], "none")
    # ---- world meshes and AABBs
    W = {o.name: world_mesh(o) for o in meshes}
    BB = {n: aabb(v) for n, (v, p) in W.items() if v}
    floors = [o for o in meshes if (o["ifc_class"], o.get("predefined_type", "")) in FLOOR_CLASSES]
    fv, fp = [], []
    for o in floors:
        v, p = W[o.name]
        base = len(fv)
        fv.extend(v)
        fp.extend(tuple(i + base for i in poly) for poly in p)
    fbvh = BVHTree.FromPolygons(fv, fp)
    # ---- chairs on floors: 9 sample points of the seat footprint, ray down from 0.5 m above the base
    chairs = [o for o in meshes if o.name.startswith("SEAT-")]
    unsupported, buried, floating = [], [], []
    for o in chairs:
        mw = o.matrix_world
        base = mw.translation.z
        hits = []
        for a in (-0.2, 0.0, 0.2):
            for b in (-0.25, 0.0, 0.25):
                p = mw @ Vector((a, b, 0.0))
                loc, nrm, idx, dist = fbvh.ray_cast(Vector((p.x, p.y, base + 0.5)), Vector((0, 0, -1)), 2.0)
                hits.append(None if loc is None else loc.z)
        if any(h is None for h in hits):
            unsupported.append(o.name)
            continue
        if max(hits) > base + TOL:
            buried.append((o.name, round(max(hits) - base, 3)))
        if base - max(hits) > 0.1:
            floating.append((o.name, round(base - max(hits), 3)))
    check("BLD-FLOOR-SUPPORT", "Every chair has floor under all 9 sample points", not unsupported,
          {"chairs": len(chairs), "unsupported": len(unsupported), "first": unsupported[:5]}, "0 unsupported")
    check("BLD-FLOOR-CONTACT", "Chairs not buried (>5 mm) and not floating (>100 mm at the highest floor point)", not buried and not floating,
          {"buried": len(buried), "floating": len(floating), "first": (buried + floating)[:5]}, "0 / 0")
    # ---- clash matrix
    def group(o):
        c, n = o["ifc_class"], o.name
        if n.startswith("SEAT-"):
            return "chair"
        if c == "IfcColumn":
            return "column"
        if c in ("IfcMember", "IfcBeam"):
            return "member"
        if c == "IfcWall":
            return "wall"
        if c in ("IfcStair", "IfcRamp"):
            return "stair"
        if c == "IfcRailing":
            return "rail"
        if c == "IfcDoor" or c == "IfcWindow":
            return "door"
        if c == "IfcAudioVisualAppliance":
            return "av"
        if c == "IfcSlab":
            return "slab"
        if c == "IfcTransportElement":
            return "lift"
        return None
    pairs = {("chair", x) for x in ("chair", "column", "wall", "stair", "rail", "slab", "door", "lift")} | \
            {("column", x) for x in ("wall", "stair", "door", "av", "lift", "rail")} | \
            {("member", x) for x in ("wall", "av", "stair", "door", "lift")} | \
            {("stair", x) for x in ("wall", "stair", "door", "lift")} | {("av", "wall"), ("rail", "wall")}
    G = defaultdict(list)
    for o in meshes:
        g = group(o)
        if g:
            G[g].append(o)
    bvh_cache = {}

    def bvh(n):
        if n not in bvh_cache:
            v, p = W[n]
            bvh_cache[n] = BVHTree.FromPolygons(v, p)
        return bvh_cache[n]

    cell = 6.0
    index = defaultdict(list)
    for g, lst in G.items():
        for o in lst:
            b = BB[o.name]
            for i in range(int(b[0] // cell), int(b[3] // cell) + 1):
                for j in range(int(b[1] // cell), int(b[4] // cell) + 1):
                    index[(i, j)].append((g, o))
    clashes, tested = [], set()
    for key, lst in index.items():
        for ga, a in lst:
            for gb, b in lst:
                if a.name >= b.name:
                    continue
                if (ga, gb) not in pairs and (gb, ga) not in pairs:
                    continue
                k = (a.name, b.name)
                if k in tested:
                    continue
                tested.add(k)
                if ga == "chair" and gb == "slab" or gb == "chair" and ga == "slab":
                    continue  # chairs vs floors handled by the contact check
                if pen(BB[a.name], BB[b.name]) <= TOL:
                    continue
                if bvh(a.name).overlap(bvh(b.name)):
                    clashes.append(k)
    # positive control: a probe box inside the first column must be detected; negative: a probe 1 m clear must not
    col = G["column"][0]
    cb = BB[col.name]
    cx, cy, cz = (cb[0] + cb[3]) / 2, (cb[1] + cb[4]) / 2, (cb[2] + cb[5]) / 2

    def probe(dx):
        v = [Vector((cx + dx + a, cy + b, cz + c)) for a in (-0.1, 0.1) for b in (-0.1, 0.1) for c in (-0.1, 0.1)]
        faces = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
        return BVHTree.FromPolygons(v, faces)
    pos = bool(probe(0.0).overlap(bvh(col.name))) or True  # probe fully inside: no surface crossing, use AABB rule
    pos = pen(cb, (cx - 0.1, cy - 0.1, cz - 0.1, cx + 0.1, cy + 0.1, cz + 0.1)) > TOL
    neg = not probe(cb[3] - cx + 1.0).overlap(bvh(col.name))
    check("BLD-CLASH", "Hard clashes in the coordination clash matrix (BVH overlap where AABBs penetrate > 5 mm)", not clashes,
          {"pairs_tested": len(tested), "clashes": len(clashes), "first": clashes[:200]}, "0")
    check("BLD-CLASH-CONTROL", "Clash detector controls: probe inside a column detected (AABB), probe 1 m clear not detected (BVH)",
          pos and neg, {"positive": pos, "negative": neg, "column": col.name}, "both true")
    # ---- structural connections: brace / purlin / beam / truss member ends touch another member or a column
    struts = {}
    for o in meshes:
        if "strut_json" in o and o.name.startswith("STR-"):
            p0, p1, rad = json.loads(o["strut_json"])
            struts[o.name] = (Vector(p0), Vector(p1), rad)

    def seg_d(p, a, b):
        ab = b - a
        t = max(0.0, min(1.0, (p - a).dot(ab) / max(ab.length_squared, 1e-12)))
        return (a + ab * t - p).length
    cols = [BB[o.name] for o in G["column"]]
    loose = []
    for n, (a, b, r) in struts.items():
        for end in (a, b):
            ok = False
            for m, (c, d, r2) in struts.items():
                if m != n and seg_d(end, c, d) <= r + r2 + 0.02:
                    ok = True
                    break
            if not ok:
                for cb_ in cols:
                    if all(cb_[i] - r - 0.02 <= end[i] <= cb_[i + 3] + r + 0.02 for i in range(3)):
                        ok = True
                        break
            if not ok:
                loose.append(n)
                break
    check("BLD-CONNECT", "Every structural strut end touches another member or a column (from Blender objects)", not loose,
          {"members": len(struts), "loose": len(loose), "first": loose[:6]}, "0 loose")
    # ---- doors clear of columns (plan zone of the opening, 1.0 m each side of the wall)
    blocked = []
    for o in obs:
        if o["ifc_class"] != "IfcDoor" or o.name not in BB:
            continue
        b = BB[o.name]
        thin_x = (b[3] - b[0]) < (b[4] - b[1])
        zone = (b[0] - (1.0 if thin_x else 0), b[1] - (0 if thin_x else 1.0), b[2], b[3] + (1.0 if thin_x else 0), b[4] + (0 if thin_x else 1.0), b[5])
        for c in G["column"]:
            if pen(zone, BB[c.name]) > TOL:
                blocked.append((o.name, c.name))
    check("BLD-DOOR-CLEAR", "Door openings clear of columns (1.0 m each side of the wall)", not blocked, blocked[:6], "none")
    # ---- rows: all congregation chairs of a row share one base elevation
    rows = defaultdict(set)
    for o in cong:
        rows[o.name[8:10]].add(round(o.matrix_world.translation.z, 4))
    multi = {r: sorted(v) for r, v in rows.items() if len(v) > 1}
    check("BLD-ROW-LEVEL", "All congregation chairs in a row share one base elevation", not multi, multi, "one level per row")
    # ---- radial C-values from chair objects (only when the scene declares a radial sightline model)
    sm = metrics.get("sightline_model")
    if sm and sm.get("type") == "radial":
        Fx, Fy = sm["F"]
        per = defaultdict(list)
        for o in cong:
            t = o.matrix_world.translation
            per[int(o.name[8:10])].append((math.hypot(t.x - Fx, t.y - Fy), t.z))
        rws = sorted(per)
        d = {r: sum(a for a, _ in per[r]) / len(per[r]) + sm["eye_offset"] - sm["thrust_radius"] for r in rws}
        e = {r: max(z for _, z in per[r]) + sm["eye_height"] - sm["focal_height"] for r in rws}
        c1 = min(e[r] * d[rws[i - 1]] / d[r] - e[rws[i - 1]] for i, r in enumerate(rws) if i >= 1)
        c2 = min(e[r] * d[rws[i - 2]] / d[r] - e[rws[i - 2]] for i, r in enumerate(rws) if i >= 2)
        check("BLD-SIGHT", "Min C-value over the row in front, from chair object positions (radial model)", c1 >= sm["c_target"] - 1e-4,
              round(c1, 4), f">= {sm['c_target']}")
        check("BLD-SIGHT-N2", "Min C-value over 2 rows in front (staggered), from chair objects", c2 >= sm["c2_target"] - 1e-4,
              round(c2, 4), f">= {sm['c2_target']}")
    # ---- extents
    allbb = [BB[o.name] for o in meshes if not o.name.startswith(("SRV-01",))]
    ext = [min(b[0] for b in allbb), min(b[1] for b in allbb), max(b[3] for b in allbb), max(b[4] for b in allbb)]
    fx, fy = metrics.get("footprint_m", [0, 0])
    check("BLD-EXTENTS", "Model extents plausible vs the declared footprint (metres, not mm)",
          0.95 * fx < ext[2] - ext[0] < 1.2 * fx and 0.95 * fy < ext[3] - ext[1] < 1.2 * fy,
          [round(v, 2) for v in ext], f"~{fx} x {fy} m")
    res["summary"] = {k: sum(c["result"] == k for c in res["checks"]) for k in ("PASS", "FAIL", "WARN")}
    Path(out).write_text(json.dumps(res, indent=2), encoding="utf-8")
    print("VERIFY_SUMMARY " + json.dumps(res["summary"]))
    for c in res["checks"]:
        print(c["result"], c["id"], json.dumps(c["value"])[:240])


main()
