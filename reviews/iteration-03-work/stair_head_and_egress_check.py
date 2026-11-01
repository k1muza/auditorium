"""Reviewer (iteration 3) read-only check: upper-foyer stair-head openings and nearest-exit metric consistency."""
import json, csv, math
import numpy as np

ROOT = r"C:\Users\Kelvin\Desktop\auditorium"
m = json.load(open(ROOT + r"\reviews\iteration-03-work\model\manifest_copy.json"))
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
json.dump(res, open(ROOT + r"\reviews\iteration-03-work\stair_head_and_egress_check.json", "w"), indent=1)
print(json.dumps({k: res[k] for k in ("rail_gaps", "stair_head_openings_total_width",
                                      "seats_where_nearest_travel_is_shorter_than_straight_line_to_listed_nearest_exit")}))
# --- iteration 3 additions
from collections import Counter
rows = list(csv.DictReader(open(ROOT + r"\reports\seating_schedule.csv")))
for col, excol in (("nearest_exit", "load_nearest_exit"), ("assigned_exit_balanced", "load_queue_balanced"),
                   ("shortest_route_exit_sensitivity", "load_shortest_route_to_outside_sensitivity")):
    c = Counter(r[col] for r in rows)
    res["csv_vs_exit_schedule_" + col] = {k: [c.get(k, 0), int(ex[k][excol])] for k in ex}
# straight-line nearest (lower bound) vs listed nearest
def sl(r, e):
    hw = float(e["clear_width_m"]) / 2
    x, y, exx, ey = float(r["x"]), float(r["y"]), float(e["x"]), float(e["y"])
    return math.hypot(x - exx, max(0, abs(y - ey) - hw)) if e["wall"] in ("W", "E") else math.hypot(max(0, abs(x - exx) - hw), y - ey)
res["straight_line_nearest_counts"] = dict(Counter(min(ex, key=lambda k: sl(r, ex[k])) for r in rows))
# listed nearest travel should be <= listed balanced travel
res["nearest_travel_gt_balanced_travel"] = sum(float(r["plan_travel_to_nearest_hall_exit_m"]) > float(r["plan_travel_to_hall_exit_m"]) + 1e-6 for r in rows)
res["nearest_travel_max"] = max(float(r["plan_travel_to_nearest_hall_exit_m"]) for r in rows)
res["nearest_travel_over30"] = sum(float(r["plan_travel_to_nearest_hall_exit_m"]) > 30 for r in rows)
res["balanced_travel_max"] = max(float(r["plan_travel_to_hall_exit_m"]) for r in rows)
res["balanced_travel_over30"] = sum(float(r["plan_travel_to_hall_exit_m"]) > 30 for r in rows)
res["external_travel_max"] = max(float(r["plan_travel_to_external_door_m"]) for r in rows)
res["external_travel_over60"] = sum(float(r["plan_travel_to_external_door_m"]) > 60 for r in rows)
# stair geometry vs grid-2 columns and slab edge
cols = {n: world(n)[0] for n in ob if n.startswith("STR-COL-") and n.endswith("2") and len(n) == 10}
st = {}
for i in range(1, 5):
    W_, _ = world(f"ARC-STAIR-FOYER-{i}")
    mn, mx = W_.min(0), W_.max(0)
    land = W_[W_[:, 2] > 3.9]
    near = []
    for cn, CV in cols.items():
        cmn, cmx = CV.min(0), CV.max(0)
        dx = max(0, cmn[0] - mx[0], mn[0] - cmx[0]); dy = max(0, cmn[1] - mx[1], mn[1] - cmx[1])
        if dx < 1 and dy < 1:
            near.append((cn, round(float(dx), 3), round(float(dy), 3)))
    st[f"ARC-STAIR-FOYER-{i}"] = {"aabb": np.round(np.r_[mn, mx], 3).tolist(),
                                  "landing_x": [round(float(land[:, 0].min()), 3), round(float(land[:, 0].max()), 3)],
                                  "landing_y": [round(float(land[:, 1].min()), 3), round(float(land[:, 1].max()), 3)],
                                  "near_cols_dx_dy": near}
res["stairs_iter3"] = st
json.dump(res, open(ROOT + r"\reviews\iteration-03-work\stair_head_and_egress_check.json", "w"), indent=1)
print(json.dumps({k: res[k] for k in res if k not in ("rail_islands_xyzxyz", "stairs", "builder_EGR-02", "examples")}, indent=0))
