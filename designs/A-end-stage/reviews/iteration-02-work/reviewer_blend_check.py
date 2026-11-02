"""Reviewer (iteration 2) read-only check of a COPY of the .blend. Never saves."""
import bpy, json, csv, re
from collections import defaultdict, Counter
from mathutils import Vector as V
from mathutils.bvhtree import BVHTree

ROOT = r"C:\Users\Kelvin\Desktop\auditorium"
OUT = ROOT + r"\reviews\iteration-02-work\reviewer_blend_check.json"
res = {}
sc = bpy.context.scene
us = sc.unit_settings
res["file"] = bpy.data.filepath
res["units"] = [us.system, us.scale_length, us.length_unit]
objs = [o for o in sc.objects if o.type == "MESH"]
res["n_mesh_objects"] = len(objs)


def aabb(o):
    m = o.matrix_world
    pts = [m @ v.co for v in o.data.vertices]
    return [min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts),
            max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)]


AB = {o.name: aabb(o) for o in objs if len(o.data.vertices)}
pat = re.compile(r"^SEAT-C-R(\d{2})-B([1-6])-S(\d{2})$")
seats = [o for o in objs if pat.match(o.name)]
res["seats_by_name"] = len(seats)
res["seats_collection"] = dict(Counter(o.users_collection[0].name for o in seats))
res["seats_hidden"] = sum(1 for o in seats if o.hide_render or o.hide_get() or o.hide_viewport)
res["seat_dims"] = dict(Counter(str(tuple(round(AB[o.name][i + 3] - AB[o.name][i], 3) for i in range(3))) for o in seats))
locs = Counter((round(o.location.x, 3), round(o.location.y, 3), round(o.location.z, 3)) for o in seats)
res["dup_seat_locations"] = sum(v - 1 for v in locs.values() if v > 1)
rows = list(csv.DictReader(open(ROOT + r"\reports\seating_schedule.csv", encoding="utf-8")))
res["csv_columns"] = list(rows[0].keys())
sched = {r["seat_id"]: r for r in rows}
names = {o.name: o for o in seats}
res["csv_rows"] = len(rows)
res["csv_not_in_blend"] = len(set(sched) - set(names))
res["blend_not_in_csv"] = len(set(names) - set(sched))
dev = 0
for k, r in sched.items():
    o = names.get(k)
    if o:
        dev = max(dev, abs(o.location.x - float(r["x"])), abs(o.location.y - float(r["y"])), abs(o.location.z - float(r["z_floor"])))
res["csv_vs_blend_max_dev"] = dev
res["seats_per_row"] = dict(sorted(Counter(int(pat.match(o.name).group(1)) for o in seats).items()))

_bvh = {}


def bvh(o):
    if o.name not in _bvh:
        m = o.matrix_world
        _bvh[o.name] = BVHTree.FromPolygons([m @ v.co for v in o.data.vertices], [list(p.vertices) for p in o.data.polygons])
    return _bvh[o.name]


def ov(a, b, t):
    return all(a[i] < b[i + 3] - t and b[i] < a[i + 3] - t for i in range(3))


SOLID = {"IfcColumn", "IfcWall", "IfcStair", "IfcRailing", "IfcBeam", "IfcMember", "IfcDoor", "IfcWindow",
         "IfcTransportElement", "IfcRamp", "IfcFooting", "IfcSlab"}
solids = [o for o in objs if o.get("ifc_class") in SOLID and o.name in AB]
res["n_solids"] = len(solids)
grid = defaultdict(list)
for s in solids:
    b = AB[s.name]
    for gx in range(int(b[0] // 4), int(b[3] // 4) + 1):
        for gy in range(int(b[1] // 4), int(b[4] // 4) + 1):
            grid[(gx, gy)].append(s)

chairs = [o for o in objs if o.get("ifc_class") == "IfcFurniture" and o.name in AB]
hits = []
for c in chairs:
    b = AB[c.name]
    cand = {}
    for gx in range(int(b[0] // 4), int(b[3] // 4) + 1):
        for gy in range(int(b[1] // 4), int(b[4] // 4) + 1):
            for s in grid[(gx, gy)]:
                cand[s.name] = s
    for s in cand.values():
        if s.get("ifc_class") == "IfcSlab":
            continue
        if ov(b, AB[s.name], 0.002) and bvh(c).overlap(bvh(s)):
            hits.append((c.name, s.name))
res["chair_vs_solid_mesh_overlaps"] = len(hits)
res["chair_vs_solid_examples"] = hits[:10]

pairs = Counter()
ex = defaultdict(list)
done = set()
for key, lst in grid.items():
    for i, a in enumerate(lst):
        for b in lst[i + 1:]:
            k = tuple(sorted((a.name, b.name)))
            if k in done:
                continue
            done.add(k)
            if ov(AB[a.name], AB[b.name], 0.01) and bvh(a).overlap(bvh(b)):
                cp = " x ".join(sorted((str(a.get("ifc_class")) + ":" + str(a.get("predefined_type", "")),
                                        str(b.get("ifc_class")) + ":" + str(b.get("predefined_type", "")))))
                pairs[cp] += 1
                if len(ex[cp]) < 8:
                    ex[cp].append(k)
res["solid_solid_mesh_overlap_by_class"] = dict(pairs)
res["solid_solid_examples"] = dict(ex)
res["prop_keys_sample"] = {n: list(sc.objects[n].keys()) for n in ("ENV-WALL-HALL-W", "STR-BRACE-WALL-B-3-4a")}


def info(n):
    o = sc.objects.get(n)
    return {"aabb": [round(v, 3) for v in AB[n]], "verts": len(o.data.vertices), "faces": len(o.data.polygons)} if o else None


res["named"] = {n: info(n) for n in ["STR-BRACE-WALL-B-3-4a", "STR-BRACE-WALL-B-3-4b", "STR-BRACE-WALL-G-10-11a",
                                     "ENV-WALL-HALL-W", "ENV-WALL-HALL-E", "ENV-WALL-HALL-REAR", "ENV-WALL-GABLE-REAR",
                                     "ENV-WALL-GABLE-STAGE", "ENV-WALL-HALL-W-UPPER", "STR-BRACE-GABLE-3-DEa",
                                     "STR-BRACE-GABLE-3-DEb", "STR-BRACE-GABLE-11-DEa", "WN-BOOTH-VIEW",
                                     "ENV-WALL-STAGE-REAR", "STR-TRUSS-T3-TC-01", "ENV-ROOF-HALL-E", "ENV-ROOF-HALL-W",
                                     "ARC-SLAB-UPPER-FOYER", "ARC-RAIL-UPPER-FOYER-EDGE", "ARC-SLAB-REAR-PLATFORM"]}
res["truss_T3_names"] = sorted(o.name for o in objs if o.name.startswith("STR-TRUSS-T3"))[:12]


def ray_hits(o, origin, d, maxd=6):
    out = []
    t = bvh(o)
    org = V(origin)
    for _ in range(20):
        loc, nrm, idx, dist = t.ray_cast(org, V(d), maxd)
        if loc is None:
            break
        out.append(round((loc - V(origin)).length, 4))
        org = loc + V(d) * 1e-4
    return out


res["wall_W_ray_x_braced_bay_y20_z6"] = ray_hits(sc.objects["ENV-WALL-HALL-W"], (2.0, 20.0, 6.0), (1, 0, 0))
res["wall_W_ray_x_unbraced_bay_y52_z6"] = ray_hits(sc.objects["ENV-WALL-HALL-W"], (2.0, 52.0, 6.0), (1, 0, 0))
res["wall_rear_ray_y_bayDE_z9"] = ray_hits(sc.objects["ENV-WALL-HALL-REAR"], (29.0, 14.0, 9.0), (0, 1, 0))

ref = [o for o in objs if o.name.startswith("ACC-REFUGE")]
res["refuges"] = {o.name: [round(v, 3) for v in AB[o.name]] for o in ref}
res["stairs"] = {o.name: [round(v, 3) for v in AB[o.name]] for o in objs if o.get("ifc_class") == "IfcStair"}
res["doors"] = {o.name: [round(v, 3) for v in AB[o.name]] for o in objs if o.get("ifc_class") == "IfcDoor"}
res["columns_grid6_3"] = {o.name: [round(v, 3) for v in AB[o.name]] for o in objs
                          if re.match(r"STR-COL-[A-H](6|3)$", o.name)}
res["lift"] = {o.name: [round(v, 3) for v in AB[o.name]] for o in objs if "LIFT" in o.name}

# foyer stair: top surface profile along x and headroom to anything above
above = [o for o in solids if o.get("ifc_class") in ("IfcSlab", "IfcBeam")]
hr = {}
prof = {}
for o in [o for o in objs if o.name.startswith("ARC-STAIR-FOYER")]:
    b = AB[o.name]
    worst = 99
    wpt = None
    pr = []
    for i in range(1, 40):
        for j in range(1, 6):
            x = b[0] + (b[3] - b[0]) * i / 40
            y = b[1] + (b[4] - b[1]) * j / 6
            loc, n, idx, d = bvh(o).ray_cast(V((x, y, 30)), V((0, 0, -1)), 40)
            if loc is None:
                continue
            z = loc.z
            if j == 3:
                pr.append((round(x, 2), round(z, 2)))
            for a in above:
                ab = AB[a.name]
                if ab[0] <= x <= ab[3] and ab[1] <= y <= ab[4] and ab[2] > z + 0.05:
                    l2, *_ = bvh(a).ray_cast(V((x, y, z + 0.01)), V((0, 0, 1)), 20)
                    if l2 is not None and l2.z - z < worst:
                        worst = l2.z - z
                        wpt = (round(x, 2), round(y, 2), round(z, 2), a.name)
    hr[o.name] = [round(worst, 3), wpt]
    prof[o.name] = pr
res["foyer_stair_min_headroom"] = hr
res["foyer_stair_profile_mid"] = prof

st = defaultdict(list)
for o in objs:
    if o.name in AB and o.get("storey"):
        st[o.get("storey")].append(round(AB[o.name][2], 2))
res["storey_base_z_range"] = {k: [min(v), max(v), len(v)] for k, v in sorted(st.items())}
json.dump(res, open(OUT, "w"), indent=1, default=str)
print("REVIEWER_DONE")
