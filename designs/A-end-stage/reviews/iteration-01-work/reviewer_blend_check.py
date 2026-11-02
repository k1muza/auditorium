"""Reviewer read-only check of a COPY of the .blend. Never saves."""
import bpy, json, csv, re, sys
from collections import defaultdict, Counter
from mathutils import Vector
from mathutils.bvhtree import BVHTree

ROOT = r"C:\Users\Kelvin\Desktop\auditorium"
OUT = ROOT + r"\reviews\iteration-01-work\reviewer_blend_check.json"
res = {}
sc = bpy.context.scene
us = sc.unit_settings
res["units"] = [us.system, us.scale_length, us.length_unit]
res["file"] = bpy.data.filepath
res["revision_prop"] = sc.get("revision")
objs = list(sc.objects)
res["n_objects"] = len(objs)
res["types"] = dict(Counter(o.type for o in objs))
cols = Counter(o.users_collection[0].name for o in objs)
res["collections"] = dict(sorted(cols.items()))

def aabb(o):
    pts = [o.matrix_world @ v.co for v in o.data.vertices] if o.type == "MESH" and len(o.data.vertices) else [o.matrix_world @ Vector(c) for c in o.bound_box]
    return [min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts), max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)]

# seats by name pattern anywhere in scene
pat = re.compile(r"^SEAT-C-R(\d{2})-B([1-6])-S(\d{2})$")
by_name = [o for o in objs if pat.match(o.name)]
res["seat_name_matches_all_scene"] = len(by_name)
res["seat_name_matches_collection"] = Counter(o.users_collection[0].name for o in by_name)
flag = [o for o in objs if json.loads(o.get("props_json", "{}") or "{}").get("CountsTowardTarget") is True]
res["counts_toward_target_flag"] = len(flag)
res["seat_hidden_or_disabled"] = sum(1 for o in by_name if o.hide_render or o.hide_get() or o.hide_viewport)
res["seat_mesh_vertices"] = Counter(len(o.data.vertices) for o in by_name)
res["seat_types"] = Counter(o.type for o in by_name)
# dims
dims = Counter()
for o in by_name:
    b = aabb(o); dims[(round(b[3]-b[0],3), round(b[4]-b[1],3), round(b[5]-b[2],3))] += 1
res["seat_world_dims"] = {str(k): v for k, v in dims.items()}
# exact duplicates in location
locs = Counter((round(o.location.x, 3), round(o.location.y, 3), round(o.location.z, 3)) for o in by_name)
res["duplicate_seat_locations"] = sum(v - 1 for v in locs.values() if v > 1)

# compare with schedule
rows = list(csv.DictReader(open(ROOT + r"\reports\seating_schedule.csv", encoding="utf-8")))
sched = {r["seat_id"]: r for r in rows}
names = {o.name: o for o in by_name}
res["sched_rows"] = len(rows)
res["sched_not_in_blend"] = sorted(set(sched) - set(names))[:10]
res["blend_not_in_sched"] = sorted(set(names) - set(sched))[:10]
maxdev = 0.0
for k, r in sched.items():
    o = names.get(k)
    if o:
        d = max(abs(o.location.x - float(r["x"])), abs(o.location.y - float(r["y"])), abs(o.location.z - float(r["z_floor"])))
        maxdev = max(maxdev, d)
res["sched_vs_blend_max_dev_m"] = maxdev

# seat-seat overlap from vertex AABBs (all chairs incl choir/companion)
chairs = [o for o in objs if o.type == "MESH" and o.get("ifc_class") == "IfcFurniture"]
cb = [(o.name, aabb(o)) for o in chairs]
def ov(a, b, t=1e-4):
    return all(a[i] < b[i+3] - t and b[i] < a[i+3] - t for i in range(3))
grid = defaultdict(list)
for n, b in cb:
    grid[(int(b[0]//2), int(b[1]//2))].append((n, b))
cc = 0; ex = []
for (gx, gy), lst in grid.items():
    neigh = []
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            neigh += grid.get((gx+dx, gy+dy), [])
    for n, b in lst:
        for m, c in neigh:
            if n < m and ov(b, c):
                cc += 1; ex.append((n, m))
res["chair_chair_overlaps"] = cc; res["chair_chair_examples"] = ex[:5]
# min gap between adjacent seats in a row and between rows
byrow = defaultdict(list)
for o in by_name:
    byrow[int(pat.match(o.name).group(1))].append(aabb(o))
mingap_x = 9;
for r, lst in byrow.items():
    lst.sort(key=lambda b: b[0])
    for a, b in zip(lst, lst[1:]):
        mingap_x = min(mingap_x, b[0]-a[3])
res["min_seat_side_gap_m"] = round(mingap_x, 4)
rowy = {r: (min(b[1] for b in l), max(b[4] for b in l)) for r, l in byrow.items()}
res["row_clear_between_chair_aabbs"] = {r: round(rowy[r-1][0] - rowy[r][1], 3) for r in sorted(rowy) if r-1 in rowy}
res["seats_per_row"] = {r: len(l) for r, l in sorted(byrow.items())}

# Mesh-level (BVH) intersection of congregation chairs vs non-floor solid objects
def bvh(o):
    m = o.matrix_world
    verts = [m @ v.co for v in o.data.vertices]
    polys = [list(p.vertices) for p in o.data.polygons]
    return BVHTree.FromPolygons(verts, polys)
solids = [o for o in objs if o.type == "MESH" and o.get("ifc_class") in ("IfcColumn", "IfcWall", "IfcStair", "IfcRailing", "IfcBeam", "IfcMember", "IfcDoor", "IfcTransportElement", "IfcRamp", "IfcFooting")]
res["solid_count_for_mesh_clash"] = len(solids)
sb = [(o, aabb(o)) for o in solids]
hits = []
for o in by_name + [c for c in chairs if c not in by_name]:
    b = aabb(o)
    for s, bb in sb:
        if all(b[i] <= bb[i+3] and bb[i] <= b[i+3] for i in range(3)):
            if bvh(o).overlap(bvh(s)):
                hits.append((o.name, s.name))
res["chair_mesh_vs_solids_overlaps"] = len(hits); res["chair_mesh_vs_solids_examples"] = hits[:10]

# chair vs floor slabs: chairs penetrating floors (mesh overlap beyond touching is hard; report aabb burial)
# columns vs footings and truss bearing
cols_ = [o for o in objs if o.get("ifc_class") == "IfcColumn"]
foots = [(o.name, aabb(o)) for o in objs if o.get("ifc_class") == "IfcFooting"]
unsupported = []
colinfo = []
for c in cols_:
    b = aabb(c)
    cx, cy = (b[0]+b[3])/2, (b[1]+b[4])/2
    ok = any(f[0] <= cx <= f[3] and f[1] <= cy <= f[4] and abs(f[5] - b[2]) < 0.05 for _, f in foots)
    if not ok: unsupported.append((c.name, [round(v, 2) for v in b]))
    colinfo.append((c.name, round(cx, 2), round(cy, 2), round(b[2], 2), round(b[5], 2)))
res["columns"] = len(cols_); res["columns_not_bearing_on_footing_top"] = unsupported[:20]
res["column_top_z_hist"] = dict(Counter(round(x[4], 2) for x in colinfo))
res["column_bottom_z_hist"] = dict(Counter(round(x[3], 2) for x in colinfo))
# trusses
tr = [o for o in objs if "TRUSS" in o.name and o.users_collection[0].name.startswith("30_STR")]
res["truss_related_objects"] = len(tr)
res["truss_names_sample"] = sorted({re.sub(r"-[A-Z0-9]+$", "", o.name) for o in tr})[:20]
# global extents and units sanity
allb = [aabb(o) for o in objs if o.type == "MESH" and o.users_collection[0].name[:2] in ("10", "20", "30")]
res["extents"] = [round(min(b[i] for b in allb), 3) for i in range(3)] + [round(max(b[i+3] for b in allb), 3) for i in range(3)]
# storeys present on objects
res["storey_props"] = dict(Counter(o.get("storey") for o in objs if o.type == "MESH"))
# doors list
doors = [(o.name, [round(v, 2) for v in aabb(o)]) for o in objs if o.get("ifc_class") == "IfcDoor"]
res["doors"] = doors
# what is directly outside hall cross-aisle doors? objects near x=4.5,y=41.75 and 54.5
near = {}
for key, (x, y) in {"W-CROSS": (2.2, 41.75), "E-CROSS": (56.8, 41.75), "W-FRONT": (2.2, 61.8), "REAR-A2": (21.0, 15.0)}.items():
    near[key] = [(o.name, [round(v, 2) for v in aabb(o)]) for o in objs if o.type == "MESH" and o.get("ifc_class") in ("IfcSlab", "IfcRamp", "IfcStair") and (lambda b: b[0] <= x <= b[3] and b[1] <= y <= b[4])(aabb(o))]
res["floor_objects_under_points"] = near
# columns inside the seating hall interior (view obstruction)
inhall = [x for x in colinfo if 5.0 < x[1] < 54.0 and 16.2 < x[2] < 63.9]
res["columns_inside_seating_zone"] = inhall
# non-manifold / degenerate count for structural+arch meshes
import bmesh
deg = 0; nonman = 0
for o in objs:
    if o.type != "MESH" or o.name.startswith("SEAT-"):
        continue
    bm = bmesh.new(); bm.from_mesh(o.data)
    nonman += sum(1 for e in bm.edges if not e.is_manifold)
    deg += sum(1 for f in bm.faces if f.calc_area() < 1e-8)
    bm.free()
res["non_seat_nonmanifold_edges"] = nonman; res["non_seat_degenerate_faces"] = deg
json.dump(res, open(OUT, "w"), indent=1, default=str)
print("REVIEWER_DONE")
