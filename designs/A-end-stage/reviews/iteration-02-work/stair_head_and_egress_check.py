"""Reviewer (iteration 2) read-only check: upper-foyer stair-head openings and nearest-exit metric consistency."""
import json, csv, math
import numpy as np

ROOT = r"C:\Users\Kelvin\Desktop\auditorium"
m = json.load(open(ROOT + r"\model\blender_manifest.json"))
ob = {o["name"]: o for o in m["objects"]}


def world(n):
    o = ob[n]
    me = m["meshes"][o["mesh"]]
    V = np.array(me["verts"])
    M = np.array(o["matrix"])
    return (M[:3, :3] @ V.T).T + M[:3, 3], me["faces"]


def islands(n):
    W, F = world(n)
    p = list(range(len(W)))

    def f(i):
        while p[i] != i:
            p[i] = p[p[i]]
            i = p[i]
        return i
    for fc in F:
        for a in fc[1:]:
            p[f(a)] = f(fc[0])
    g = {}
    for i in range(len(W)):
        g.setdefault(f(i), []).append(i)
    return sorted(np.round(np.r_[W[ix].min(0), W[ix].max(0)], 3).tolist() for ix in g.values())


res = {"rail_islands_xyzxyz": islands("ARC-RAIL-UPPER-FOYER-EDGE")}
xs = [(b[0], b[3]) for b in res["rail_islands_xyzxyz"]]
gaps = [(round(a[1], 3), round(b[0], 3)) for a, b in zip(xs, xs[1:])]
res["rail_gaps"] = [{"x0": g0, "x1": g1, "width": round(g1 - g0, 3)} for g0, g1 in gaps]
stairs = {}
for i in range(1, 5):
    n = f"ARC-STAIR-FOYER-{i}"
    W, _ = world(n)
    top = W[W[:, 2] > 3.9]
    stairs[n] = {"props": ob[n]["props"], "top_landing_xy": [round(top[:, 0].min(), 3), round(top[:, 1].min(), 3),
                                                               round(top[:, 0].max(), 3), round(top[:, 1].max(), 3)]}
res["stairs"] = stairs
stair_gaps = [g for g in res["rail_gaps"] if g["width"] > 0.5]
res["stair_head_openings_total_width"] = round(sum(g["width"] for g in stair_gaps), 3)
geo = json.load(open(ROOT + r"\reports\geometry_checks.json"))
egr02 = [c for c in geo["checks"] if c["id"] == "EGR-02"][0]
res["builder_EGR-02"] = egr02
# nearest-exit metric consistency
ex = {r["exit_id"]: r for r in csv.DictReader(open(ROOT + r"\reports\exit_schedule.csv"))}
bad = []
for r in csv.DictReader(open(ROOT + r"\reports\seating_schedule.csv")):
    e = ex[r["nearest_exit"]]
    hw = float(e["clear_width_m"]) / 2
    x, y, exx, ey = float(r["x"]), float(r["y"]), float(e["x"]), float(e["y"])
    d = math.hypot(x - exx, max(0, abs(y - ey) - hw)) if e["wall"] in ("W", "E") else math.hypot(max(0, abs(x - exx) - hw), y - ey)
    if d > float(r["plan_travel_to_nearest_hall_exit_m"]) + 0.05:
        bad.append((r["seat_id"], r["nearest_exit"], r["plan_travel_to_nearest_hall_exit_m"], round(d, 2)))
res["seats_where_nearest_travel_is_shorter_than_straight_line_to_listed_nearest_exit"] = len(bad)
res["examples"] = bad[:3] + sorted(bad, key=lambda b: float(b[2]) - b[3])[:3]
json.dump(res, open(ROOT + r"\reviews\iteration-02-work\stair_head_and_egress_check.json", "w"), indent=1)
print(json.dumps({k: res[k] for k in ("rail_gaps", "stair_head_openings_total_width",
                                      "seats_where_nearest_travel_is_shorter_than_straight_line_to_listed_nearest_exit")}))
