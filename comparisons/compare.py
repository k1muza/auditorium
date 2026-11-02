"""Option A vs Option B comparison - every quantity measured from each design's own Blender manifest with the SAME code.

  .venv/Scripts/python comparisons/compare.py

Reads designs/<id>/model/blender_manifest.json and designs/<id>/reports/*.json (the latter only for figures produced
by each design's own verified engine, which are labelled as such). Writes comparisons/out/: comparison.json,
comparison.md, and figures at one common scale. Nothing in designs/ is written.
"""
import json
import math
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from shared.drawings import sheets as S  # noqa: E402

import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.collections import PolyCollection  # noqa: E402

OUT = REPO / "comparisons" / "out"
DESIGNS = {"A": REPO / "designs" / "A-end-stage", "B": REPO / "designs" / "B-long-side-stage"}
EYE = 1.15
HALL_SPACE_WORDS = ("seating hall", "platform", "wing", "front corner", "floor in front of platform")


def pip(p, poly):
    inside = False
    for i in range(len(poly)):
        (x0, y0), (x1, y1) = poly[i], poly[(i + 1) % len(poly)]
        if (y0 > p[1]) != (y1 > p[1]) and p[0] < x0 + (p[1] - y0) * (x1 - x0) / (y1 - y0):
            inside = not inside
    return inside


def seg_d(p, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    t = max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / (dx * dx + dy * dy or 1e-12)))
    return math.hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dy)


def faces_up(M, o, sign=1):
    V = S.world(M, o)
    out = []
    for f in M["meshes"][o["mesh"]]["faces"]:
        pts = [V[i] for i in f]
        if sign * S.normal(pts)[2] > 0.5:
            out.append(pts)
    return out


def plane_z(face, x, y):
    """z of the (planar) face at plan point (x, y) if inside its plan polygon."""
    if not pip((x, y), [(p[0], p[1]) for p in face]):
        return None
    (x0, y0, z0), (x1, y1, z1), (x2, y2, z2) = face[0], face[1], face[2]
    nx = (y1 - y0) * (z2 - z0) - (z1 - z0) * (y2 - y0)
    ny = (z1 - z0) * (x2 - x0) - (x1 - x0) * (z2 - z0)
    nz = (x1 - x0) * (y2 - y0) - (y1 - y0) * (x2 - x0)
    if abs(nz) < 1e-9:
        return None
    return z0 - (nx * (x - x0) + ny * (y - y0)) / nz


def measure(key):
    D = DESIGNS[key]
    M = S.load(D / "model" / "blender_manifest.json")
    G = json.loads((D / "reports" / "geometry_checks.json").read_text(encoding="utf-8"))
    BV = json.loads((D / "reports" / "blend_verification.json").read_text(encoding="utf-8"))
    IV = json.loads((D / "reports" / "ifc_validation.json").read_text(encoding="utf-8"))
    objs = M["objects"]
    by = {o["name"]: o for o in objs}
    pul = by["ARC-PULPIT"]["matrix"]
    px, py = pul[0][3], pul[1][3]
    plat = [f for f in faces_up(M, by["ARC-PLATFORM"])]
    plat_edges = [(f[i][:2], f[(i + 1) % len(f)][:2]) for f in plat for i in range(len(f))]
    seats = [o for o in objs if o["props"].get("CountsTowardTarget") is True]
    rows = []
    for o in seats:
        m = o["matrix"]
        x, y, z = m[0][3], m[1][3], m[2][3]
        fx, fy = m[0][1], m[1][1]          # local +Y (chair facing) in world
        d = math.hypot(px - x, py - y)
        head = math.degrees(math.acos(max(-1, min(1, (fx * (px - x) + fy * (py - y)) / (d * math.hypot(fx, fy))))))
        bearing = math.degrees(math.atan2(abs(x - px), py - y))
        dedge = min(seg_d((x, y), a, b) for a, b in plat_edges)
        rows.append({"x": x, "y": y, "z": z, "d": d, "head": head, "bearing": bearing, "dedge": dedge})
    ds = sorted(r["d"] for r in rows)

    def pct(v, q):
        return v[min(len(v) - 1, int(q * len(v)))]
    exits = [o for o in objs if o["ifc_class"] == "IfcDoor" and o["props"].get("FireExit")]
    hall_exits = [o for o in exits if o["name"].startswith(("DR-HALL", "DR-STAGE"))]
    ext_exits = [o for o in exits if o["name"].startswith("DR-EXT")]
    ex_pts = [((sum(v[0] for v in S.world(M, o)) / 8), (sum(v[1] for v in S.world(M, o)) / 8)) for o in hall_exits]
    direct = sorted(min(math.hypot(r["x"] - a, r["y"] - b) for a, b in ex_pts) for r in rows)
    # footprint, roof, envelope
    env = [o for o in objs if o["collection"].startswith(("10_ENV", "20_ARC_Floors"))]
    xs = [v[0] for o in env for v in S.world(M, o)]
    ys = [v[1] for o in env for v in S.world(M, o)]
    roof_faces = [f for o in objs if o["name"].startswith("ENV-ROOF") for f in faces_up(M, o)]

    def area3(f):
        ax_ = ay_ = az_ = 0.0
        for i in range(len(f)):
            (x0, y0, z0), (x1, y1, z1) = f[i], f[(i + 1) % len(f)]
            ax_ += y0 * z1 - z0 * y1
            ay_ += z0 * x1 - x0 * z1
            az_ += x0 * y1 - y0 * x1
        return 0.5 * math.sqrt(ax_ * ax_ + ay_ * ay_ + az_ * az_)
    roof_area = sum(area3(f) for f in roof_faces)
    roof_plan = sum(abs(sum(f[i][0] * f[(i + 1) % len(f)][1] - f[(i + 1) % len(f)][0] * f[i][1] for i in range(len(f)))) / 2 for f in roof_faces)
    roof_top = max(v[2] for o in objs if o["name"].startswith("ENV-ROOF") for v in S.world(M, o))
    # spaces
    spaces = [o for o in objs if o["ifc_class"] == "IfcSpace"]
    gfa = sum(o["props"].get("GrossFloorArea", 0) for o in spaces)
    hall_sp = [o for o in spaces if any(w in o["props"].get("LongName", "").lower() for w in HALL_SPACE_WORDS)]
    hall_area = sum(o["props"]["GrossFloorArea"] for o in hall_sp)
    # hall air volume: 1 m sample grid inside the hall spaces, floor (highest up-face below 6 m) to roof underside
    hall_polys = []
    for o in hall_sp:
        for f in faces_up(M, o, -1):
            hall_polys.append([(p[0], p[1]) for p in f])
    floor_faces = [f for o in objs if o["ifc_class"] in ("IfcSlab", "IfcRamp", "IfcStair") and not o["name"].startswith("ENV-ROOF")
                   and o["predefined_type"] != "ROOF" for f in faces_up(M, o)]
    roof_under = [f for o in objs if o["name"].startswith("ENV-ROOF") for f in faces_up(M, o, -1)]
    vol, n = 0.0, 0
    bx0, by0, bx1, by1 = min(xs), min(ys), max(xs), max(ys)
    fgrid = {}
    for f in floor_faces:
        fx_ = [p[0] for p in f]
        fy_ = [p[1] for p in f]
        for i in range(int(min(fx_)), int(max(fx_)) + 1):
            for j in range(int(min(fy_)), int(max(fy_)) + 1):
                fgrid.setdefault((i, j), []).append(f)
    yy = by0 + 0.5
    while yy < by1:
        xx = bx0 + 0.5
        while xx < bx1:
            if any(pip((xx, yy), p) for p in hall_polys):
                zf = max([z for f in fgrid.get((int(xx), int(yy)), []) if (z := plane_z(f, xx, yy)) is not None and z < 6] or [0.0])
                zr = min([z for f in roof_under if (z := plane_z(f, xx, yy)) is not None] or [None]) if roof_under else None
                if zr is not None:
                    vol += zr - zf
                    n += 1
            xx += 1.0
        yy += 1.0
    # structure
    def total_len(pred):
        L, c = 0.0, 0
        for o in objs:
            if o.get("strut") and pred(o["name"]):
                a, b, _ = o["strut"]
                L += math.dist(a, b)
                c += 1
        return round(L, 1), c
    cols = [o for o in objs if o["ifc_class"] == "IfcColumn"]
    col_len = sum(max(v[2] for v in S.world(M, o)) - min(v[2] for v in S.world(M, o)) for o in cols)
    ftg = [o for o in objs if o["ifc_class"] == "IfcFooting"]

    def bbvol(o):
        V = S.world(M, o)
        return (max(v[0] for v in V) - min(v[0] for v in V)) * (max(v[1] for v in V) - min(v[1] for v in V)) * (max(v[2] for v in V) - min(v[2] for v in V))
    trusses = sorted({o["props"].get("Assembly") for o in objs if o["name"].startswith("STR-TRUSS") and o["props"].get("Assembly")})
    ext_walls = [o for o in objs if o["ifc_class"] == "IfcWall" and o["props"].get("IsExternal")]

    def wall_area(o):
        V = S.world(M, o)
        L = max(max(v[0] for v in V) - min(v[0] for v in V), max(v[1] for v in V) - min(v[1] for v in V))
        return L * (max(v[2] for v in V) - min(v[2] for v in V))
    glaz = sum(o["props"].get("OverallWidth", 0) * o["props"].get("OverallHeight", 0) for o in objs if o["ifc_class"] == "IfcWindow")
    wcs = [o for o in objs if o["name"].startswith("ACC-WCS") and not o["props"].get("ChoirPlace")]
    choir = [o for o in objs if o["props"].get("SeatType") == "choir"]
    stairs = [o for o in objs if o["ifc_class"] == "IfcStair"]
    ramps = [o for o in objs if o["ifc_class"] == "IfcRamp"]
    gm = G["metrics"]
    eg = gm["egress"]
    c1 = next((c["value"] for c in BV["checks"] if c["id"] == "BLD-SIGHT"), None)
    c2 = next((c["value"] for c in BV["checks"] if c["id"] == "BLD-SIGHT-N2"), gm.get("c_min_n2"))
    res = {
        "design_id": M.get("design_id") or ("A-end-stage" if key == "A" else "B-long-side-stage"), "revision": M["revision"],
        "manifest_sha256": M["_sha"],
        "seats": len(seats), "rows": gm.get("rows") or len({o['name'][8:10] for o in seats}),
        "pulpit_distance_m": {"mean": round(sum(ds) / len(ds), 2), "median": round(pct(ds, 0.5), 2), "p90": round(pct(ds, 0.9), 2),
                              "max": round(ds[-1], 2), "share_within_20m": round(sum(d <= 20 for d in ds) / len(ds), 3),
                              "share_within_30m": round(sum(d <= 30 for d in ds) / len(ds), 3)},
        "platform_edge_distance_m": {"mean": round(sum(r["dedge"] for r in rows) / len(rows), 2), "max": round(max(r["dedge"] for r in rows), 2)},
        "head_turn_to_pulpit_deg": {"mean": round(sum(r["head"] for r in rows) / len(rows), 1), "max": round(max(r["head"] for r in rows), 1),
                                    "over_45": sum(r["head"] > 45 for r in rows), "over_30": sum(r["head"] > 30 for r in rows)},
        "bearing_from_pulpit_deg": {"max": round(max(r["bearing"] for r in rows), 1), "over_60": sum(r["bearing"] > 60 for r in rows),
                                    "over_75": sum(r["bearing"] > 75 for r in rows)},
        "rake_top_seat_floor_m": round(max(r["z"] for r in rows), 3),
        "c_value_min_from_chair_objects": {"n1": c1, "n2": c2, "source": "each design's blend_verification.json (own method)"},
        "footprint_m": [round(max(xs) - min(xs), 2), round(max(ys) - min(ys), 2)], "footprint_area_m2": round((max(xs) - min(xs)) * (max(ys) - min(ys)), 1),
        "space_gfa_m2": round(gfa, 1), "hall_floor_area_m2": round(hall_area, 1), "hall_area_per_seat_m2": round(hall_area / len(seats), 3),
        "hall_air_volume_m3": round(vol, 0), "hall_volume_per_seat_m3": round(vol / len(seats), 2), "volume_samples": n,
        "roof_area_m2": round(roof_area, 1), "roof_plan_area_m2": round(roof_plan, 1), "roof_top_m": round(roof_top, 2),
        "truss_count": len(trusses), "truss_span_m": gm.get("truss_span"),
        "structure": {"columns": len(cols), "column_length_m": round(col_len, 1), "pad_footings": len(ftg),
                      "footing_concrete_m3": round(sum(bbvol(o) for o in ftg), 1),
                      "truss_members_length_m": total_len(lambda n: n.startswith("STR-TRUSS")),
                      "purlins_length_m": total_len(lambda n: n.startswith("STR-PURLIN")),
                      "bracing_length_m": total_len(lambda n: "BRACE" in n or n.startswith(("STR-KNEE", "STR-STRUT"))),
                      "beams_length_m": total_len(lambda n: n.startswith("STR-BEAM"))},
        "external_wall_area_m2": round(sum(wall_area(o) for o in ext_walls), 0), "glazing_area_m2": round(glaz, 1),
        "exits": {"hall_exits": len(hall_exits), "hall_exit_door_width_m": round(sum(o["props"]["OverallWidth"] for o in hall_exits), 1),
                  "final_exits": len(ext_exits), "final_exit_door_width_m": round(sum(o["props"]["OverallWidth"] for o in ext_exits), 1),
                  "direct_seat_to_nearest_hall_exit_m": {"mean": round(sum(direct) / len(direct), 2), "max": round(direct[-1], 2),
                                                         "method": "straight line seat -> nearest hall exit door (lower bound, same code for both)"}},
        "egress_own_engine": {k: eg.get(k) for k in ("max_travel_hall", "max_travel_hall_to_nearest_exit", "count_travel_hall_over_flag",
                                                     "count_nearest_travel_over_flag", "max_travel_total", "count_travel_total_over_flag",
                                                     "total_hall_exit_width", "total_hall_exit_clear_width", "total_required_width_placeholder",
                                                     "rear_load_to_upper_foyer", "building_total_occupants")},
        "accessibility": {"wheelchair_spaces": len(wcs), "levels_with_wheelchair_spaces": sorted({o["storey"] for o in wcs}),
                          "stairs": len(stairs), "stair_risers_total": sum(int(o["props"].get("Risers", 0)) for o in stairs),
                          "ramps": len(ramps), "lifts": sum(1 for o in objs if o["ifc_class"] == "IfcTransportElement")},
        "choir_chairs": len(choir), "platform_area_m2": round(sum(abs(sum(f[i][0] * f[(i + 1) % len(f)][1] - f[(i + 1) % len(f)][0] * f[i][1]
                                                                     for i in range(len(f)))) / 2 for f in plat), 1),
        "screens": sum(1 for o in objs if o["predefined_type"] == "DISPLAY"),
        "checks": {"blend": BV.get("summary") or {k: sum(c["result"] == k for c in BV["checks"]) for k in ("PASS", "FAIL", "WARN")},
                   "ifc": IV.get("summary"), "layout": {k: sum(c["result"] == k for c in G["checks"]) for k in ("PASS", "FAIL", "WARN")}},
        "_rows": rows,
    }
    return M, res


def figures(MA, A, MB, B):
    OUT.mkdir(parents=True, exist_ok=True)
    # common-scale plans (1:400, A3) from the shared sheet generator
    for M, k in ((MA, "A"), (MB, "B")):
        M["design_id"] = A["design_id"] if k == "A" else B["design_id"]
        S.plan(M, OUT / f"plan_{k}_1-400.png", f"Comparison plan - Option {k}", f"CMP-{k}100", scale=400)
    # distance maps on one figure, same colour scale and the same metres-per-inch
    fig, axs = plt.subplots(1, 2, figsize=(16.5, 8.2), dpi=130, gridspec_kw={"width_ratios": [1, 1]})
    vmax = max(A["pulpit_distance_m"]["max"], B["pulpit_distance_m"]["max"])
    for ax, M, R in ((axs[0], MA, A), (axs[1], MB, B)):
        sc = ax.scatter([r["x"] for r in R["_rows"]], [r["y"] for r in R["_rows"]], c=[r["d"] for r in R["_rows"]], s=3, cmap="viridis_r",
                        vmin=0, vmax=vmax)
        pul = next(o for o in M["objects"] if o["name"] == "ARC-PULPIT")["matrix"]
        ax.plot(pul[0][3], pul[1][3], "r*", ms=10)
        ax.set_aspect("equal")
        ax.set_xlim(-10, 95), ax.set_ylim(-15, 95)
        ax.set_title(f"{R['design_id']}  ({R['revision']})\nmean {R['pulpit_distance_m']['mean']} m, max {R['pulpit_distance_m']['max']} m",
                     fontsize=9)
        ax.grid(alpha=0.2)
    fig.colorbar(sc, ax=axs, shrink=0.8, label="eye-to-pulpit plan distance (m)")
    fig.suptitle("Seat-to-pulpit distance, same scale and colour range (measured from each Blender manifest)", fontsize=10)
    fig.savefig(OUT / "distance_maps.png")
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(8, 4.2), dpi=130)
    bins = list(range(0, 62, 2))
    ax.hist([r["d"] for r in A["_rows"]], bins=bins, alpha=0.6, label=f"A {A['revision']}")
    ax.hist([r["d"] for r in B["_rows"]], bins=bins, alpha=0.6, label=f"B {B['revision']}")
    ax.set_xlabel("eye-to-pulpit plan distance (m)"), ax.set_ylabel("seats"), ax.legend(), ax.grid(alpha=0.2)
    ax.set_title("Distribution of seat distances (3,000 seats each)")
    fig.tight_layout()
    fig.savefig(OUT / "distance_histogram.png")
    plt.close(fig)
    # long sections through each design's main axis at the same scale
    S.section(MA, OUT / "section_A_1-400.png", "x", 31.0, "Comparison section - Option A (along the hall axis)", "CMP-A300", scale=400)
    S.section(MB, OUT / "section_B_1-400.png", "x", 44.0, "Comparison section - Option B (across the hall depth)", "CMP-B300", scale=400)


def table(A, B):
    def g(d, path):
        for k in path.split("."):
            d = d[k]
        return d
    rows = [("Seats (CountsTowardTarget)", "seats"), ("Rows", "rows"), ("Pulpit distance mean (m)", "pulpit_distance_m.mean"),
            ("Pulpit distance median (m)", "pulpit_distance_m.median"), ("Pulpit distance 90th pct (m)", "pulpit_distance_m.p90"),
            ("Pulpit distance max (m)", "pulpit_distance_m.max"), ("Seats within 20 m of pulpit", "pulpit_distance_m.share_within_20m"),
            ("Seats within 30 m of pulpit", "pulpit_distance_m.share_within_30m"), ("Platform-edge distance max (m)", "platform_edge_distance_m.max"),
            ("Head turn to pulpit mean (deg)", "head_turn_to_pulpit_deg.mean"), ("Head turn max (deg)", "head_turn_to_pulpit_deg.max"),
            ("Seats with head turn > 30 deg", "head_turn_to_pulpit_deg.over_30"), ("Max bearing from pulpit (deg)", "bearing_from_pulpit_deg.max"),
            ("Seats > 75 deg bearing (side-on)", "bearing_from_pulpit_deg.over_75"), ("Highest seat floor (m)", "rake_top_seat_floor_m"),
            ("Footprint (m x m)", "footprint_m"), ("Footprint area (m2)", "footprint_area_m2"), ("Space GFA (m2)", "space_gfa_m2"),
            ("Hall floor area (m2)", "hall_floor_area_m2"), ("Hall area per seat (m2)", "hall_area_per_seat_m2"),
            ("Hall air volume (m3)", "hall_air_volume_m3"), ("Hall volume per seat (m3)", "hall_volume_per_seat_m3"),
            ("Roof area, sloped (m2)", "roof_area_m2"), ("Roof top (m)", "roof_top_m"), ("Trusses", "truss_count"), ("Truss span (m)", "truss_span_m"),
            ("Columns", "structure.columns"), ("Footing concrete (m3, pads)", "structure.footing_concrete_m3"),
            ("Truss member length (m, count)", "structure.truss_members_length_m"), ("Purlin length (m, count)", "structure.purlins_length_m"),
            ("Bracing length (m, count)", "structure.bracing_length_m"), ("External wall area (m2)", "external_wall_area_m2"),
            ("Glazing (m2)", "glazing_area_m2"), ("Hall exits / door width (m)", None), ("Final exits / door width (m)", None),
            ("Direct seat-to-exit max (m, same method)", "exits.direct_seat_to_nearest_hall_exit_m.max"),
            ("Direct seat-to-exit mean (m)", "exits.direct_seat_to_nearest_hall_exit_m.mean"),
            ("Own-engine max in-hall travel, nearest exit (m)", "egress_own_engine.max_travel_hall_to_nearest_exit"),
            ("Own-engine max in-hall travel, balanced (m)", "egress_own_engine.max_travel_hall"),
            ("Own-engine occupants > 30 m (balanced)", "egress_own_engine.count_travel_hall_over_flag"),
            ("Own-engine max travel to outside (m)", "egress_own_engine.max_travel_total"),
            ("Wheelchair spaces", "accessibility.wheelchair_spaces"), ("Stairs / total risers", None), ("Ramps", "accessibility.ramps"),
            ("Lifts", "accessibility.lifts"), ("Choir chairs", "choir_chairs"), ("Platform area (m2)", "platform_area_m2"), ("Screens", "screens"),
            ("Min C-value n1 / n2 (from chairs)", None)]
    lines = ["| Measure | Option A | Option B |", "|---|---:|---:|"]
    for label, path in rows:
        if path is None:
            if label.startswith("Hall exits"):
                va, vb = (f"{x['exits']['hall_exits']} / {x['exits']['hall_exit_door_width_m']}" for x in (A, B))
            elif label.startswith("Final"):
                va, vb = (f"{x['exits']['final_exits']} / {x['exits']['final_exit_door_width_m']}" for x in (A, B))
            elif label.startswith("Stairs"):
                va, vb = (f"{x['accessibility']['stairs']} / {x['accessibility']['stair_risers_total']}" for x in (A, B))
            else:
                va, vb = (f"{x['c_value_min_from_chair_objects']['n1']} / {x['c_value_min_from_chair_objects']['n2']}" for x in (A, B))
        else:
            va, vb = g(A, path), g(B, path)
        lines.append(f"| {label} | {va} | {vb} |")
    return lines


def main():
    MA, A = measure("A")
    MB, B = measure("B")
    figures(MA, A, MB, B)
    out = {"generated_from": {k: {"design_id": r["design_id"], "revision": r["revision"], "manifest_sha256": r["manifest_sha256"]}
                              for k, r in (("A", A), ("B", B))},
           "A": {k: v for k, v in A.items() if k != "_rows"}, "B": {k: v for k, v in B.items() if k != "_rows"}}
    (OUT / "comparison.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    md = [f"# Option A vs Option B - measured comparison", "",
          f"Generated by `comparisons/compare.py` from `designs/A-end-stage/model/blender_manifest.json` ({A['revision']}, sha256 "
          f"{A['manifest_sha256'][:16]}) and `designs/B-long-side-stage/model/blender_manifest.json` ({B['revision']}, sha256 "
          f"{B['manifest_sha256'][:16]}). Every row except those marked 'own engine' / 'from chairs' is computed by the same code for both "
          "models. Concept models only - no cost rates, no code-compliance claim.", ""] + table(A, B)
    (OUT / "comparison.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
