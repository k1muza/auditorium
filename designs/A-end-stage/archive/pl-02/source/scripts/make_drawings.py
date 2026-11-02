"""Schematic drawings from the Blender manifest (geometry) + layout engine (annotations).

  .venv/Scripts/python scripts/make_drawings.py model/blender_manifest.json exports

Writes exports/floor_plan.png, exports/upper_foyer_plan.png, exports/structural_grid.png and
exports/long_section.png. Plan geometry = top faces of the Blender meshes and chair placements
read from the manifest, so drawings reflect the model revision named in the title block.
"""
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.collections import LineCollection, PatchCollection, PolyCollection  # noqa: E402
from matplotlib.patches import FancyArrowPatch, Polygon, Rectangle  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import auditorium_layout as al  # noqa: E402

DPI = 150
STATUS = "CONCEPT - UNVERIFIED - NOT FOR CONSTRUCTION"


class Model:
    def __init__(self, manifest):
        self.M = json.loads(Path(manifest).read_text(encoding="utf-8"))
        self.objs = self.M["objects"]
        self.meshes = self.M["meshes"]

    def world(self, ob):
        m = np.array(ob["matrix"])
        v = np.array(self.meshes[ob["mesh"]]["verts"], dtype=float)
        return (np.c_[v, np.ones(len(v))] @ m.T)[:, :3]

    def faces(self, ob, normal_z=0.9):
        """Faces of the world mesh whose normal z exceeds normal_z (top faces)."""
        w = self.world(ob)
        out = []
        for fc in self.meshes[ob["mesh"]]["faces"]:
            p = w[fc]
            n = np.cross(p[1] - p[0], p[2] - p[0])
            ln = np.linalg.norm(n)
            if ln > 1e-12 and n[2] / ln > normal_z:
                out.append(p)
        return out

    def sel(self, pred):
        return [o for o in self.objs if pred(o)]


def grid_and_bubbles(ax, gx, gy, ext=7.0, fs=11):
    xmin, xmax = min(gx.values()) - ext, max(gx.values()) + ext
    ymin, ymax = min(gy.values()) - ext, max(gy.values()) + ext
    for k, v in gx.items():
        ax.plot([v, v], [ymin + 2, ymax - 2], color="0.55", lw=0.6, ls=(0, (8, 3, 1, 3)), zorder=1)
        for y in (ymin + 1, ymax - 1):
            ax.add_patch(plt.Circle((v, y), 1.1, fc="white", ec="k", lw=0.9, zorder=6))
            ax.text(v, y, k, ha="center", va="center", fontsize=fs, weight="bold", zorder=7)
    for k, v in gy.items():
        ax.plot([xmin + 2, xmax - 2], [v, v], color="0.55", lw=0.6, ls=(0, (8, 3, 1, 3)), zorder=1)
        for x in (xmin + 1, xmax - 1):
            ax.add_patch(plt.Circle((x, v), 1.1, fc="white", ec="k", lw=0.9, zorder=6))
            ax.text(x, v, k, ha="center", va="center", fontsize=fs, weight="bold", zorder=7)
    return xmin, xmax, ymin, ymax


def dim(ax, p0, p1, text, off=(0, 0), fs=8, color="k", zorder=8):
    (x0, y0), (x1, y1) = p0, p1
    ox, oy = off
    a = FancyArrowPatch((x0 + ox, y0 + oy), (x1 + ox, y1 + oy), arrowstyle="<|-|>", mutation_scale=7, lw=0.7,
                        color=color, zorder=zorder)
    ax.add_patch(a)
    for (x, y) in (p0, p1):
        ax.plot([x, x + ox * 1.15], [y, y + oy * 1.15], color=color, lw=0.4, zorder=zorder)
    xm, ym = (x0 + x1) / 2 + ox, (y0 + y1) / 2 + oy
    rot = 90 if abs(x1 - x0) < 1e-6 else 0
    ax.text(xm, ym, text, ha="center", va="center", fontsize=fs, rotation=rot, color=color, zorder=zorder + 1,
            bbox=dict(fc="white", ec="none", pad=0.6))


def dim_chain(ax, coords, axis, at, fs=7, color="k"):
    coords = sorted(coords)
    for a, b in zip(coords, coords[1:]):
        if axis == "x":
            dim(ax, (a, at), (b, at), f"{b - a:.2f}".rstrip("0").rstrip("."), fs=fs, color=color)
        else:
            dim(ax, (at, a), (at, b), f"{b - a:.2f}".rstrip("0").rstrip("."), fs=fs, color=color)


def title_block(fig, title, revision, notes, scale_note):
    fig.text(0.012, 0.012, f"{title}\nCA3000 - 3,000-seat church auditorium | Revision {revision} | {scale_note}\n"
                           f"{STATUS}. Dimensions in metres. All widths, distances and gradients UNVERIFIED pending "
                           f"professional / statutory review.\n" + notes,
             fontsize=9, va="bottom", ha="left", family="monospace",
             bbox=dict(fc="#fffbe6", ec="k", lw=0.8, pad=6))


def scale_bar(ax, x, y, length=20):
    for i in range(0, length, 5):
        ax.add_patch(Rectangle((x + i, y), 5, 0.6, fc="k" if (i // 5) % 2 == 0 else "white", ec="k", lw=0.6, zorder=8))
    for i in range(0, length + 1, 5):
        ax.text(x + i, y - 0.9, f"{i}", ha="center", va="top", fontsize=7)
    ax.text(x + length / 2, y + 1.3, "metres", ha="center", fontsize=7)


def north(ax, x, y):
    ax.annotate("", xy=(x, y + 4), xytext=(x, y), arrowprops=dict(arrowstyle="-|>", lw=1.5, color="k"))
    ax.text(x, y + 4.8, "PN\n(assumed)", ha="center", fontsize=7)


def draw_top(ax, model, objs, fc, ec, lw=0.3, alpha=1.0, z=2, hatch=None):
    polys = []
    for o in objs:
        for p in model.faces(o):
            polys.append(p[:, :2])
    if polys:
        pc = PolyCollection(polys, facecolors=fc, edgecolors=ec, linewidths=lw, alpha=alpha, zorder=z)
        if hatch:
            pc.set_hatch(hatch)
        ax.add_collection(pc)


def chairs(ax, model, colour, col_name, z=4):
    rects = []
    for o in model.sel(lambda o: o["collection"] == col_name):
        x, y = o["matrix"][0][3], o["matrix"][1][3]
        hw, hd = (0.30, 0.24) if abs(o["matrix"][1][0]) > 0.5 else (0.24, 0.30)  # rotated +-90 deg: swap
        rects.append(Rectangle((x - hw, y - hd), 2 * hw, 2 * hd))
    ax.add_collection(PatchCollection(rects, fc=colour, ec="none", zorder=z))
    return len(rects)


def floor_plan(model, lay, out, rev):
    P = lay.P
    gx, gy = P["grid"]["x_lines"], P["grid"]["y_lines"]
    fig = plt.figure(figsize=(26, 34))
    ax = fig.add_axes([0.03, 0.095, 0.94, 0.895])
    ax.set_aspect("equal")
    xmin, xmax, ymin, ymax = grid_and_bubbles(ax, gx, gy, ext=9)
    is_upper = lambda o: o["storey"] in ("L02",) and o["ifc_class"] != "IfcFurniture"  # noqa: E731
    floors = model.sel(lambda o: o["ifc_class"] == "IfcSlab" and o["predefined_type"] in ("FLOOR", "LANDING")
                       and o["storey"] != "L02")
    draw_top(ax, model, floors, "#efefea", "#c8c8c0", 0.25, z=1)
    rake = [o for o in floors if o["name"].startswith("ARC-RAKE") or o["name"] == "ARC-SLAB-RAKE-FRONT"]
    draw_top(ax, model, rake, "#e4e8f0", "#9aa4b8", 0.35, z=2)
    draw_top(ax, model, model.sel(lambda o: o["name"].startswith(("ARC-PLATFORM", "ARC-CHOIR"))), "#f1e2c8", "#8a6d3b", 0.6, z=2)
    draw_top(ax, model, model.sel(lambda o: o["ifc_class"] == "IfcRamp"), "#f7e6a8", "#b08a1e", 0.5, z=3)
    draw_top(ax, model, model.sel(lambda o: o["ifc_class"] == "IfcStair"), "#f3d27a", "#8a6a12", 0.5, z=3)
    # upper foyer outline (dashed) and booth
    up = model.sel(lambda o: o["name"] == "ARC-SLAB-UPPER-FOYER")[0]
    w = model.world(up)
    ax.add_patch(Rectangle((w[:, 0].min(), w[:, 1].min()), np.ptp(w[:, 0]), np.ptp(w[:, 1]), fc="none", ec="#555",
                           lw=1.0, ls="--", zorder=5))
    ax.text(w[:, 0].min() + 1, w[:, 1].max() - 1.2, f"UPPER FOYER OVER (L02 +{lay.top_level:.2f}) - see upper_foyer_plan.png",
            fontsize=8, color="#444", zorder=9)
    walls = model.sel(lambda o: o["ifc_class"] == "IfcWall" and not o["name"].startswith(("ENV-WALL-GABLE", "ARC-WALL-BOOTH")))
    draw_top(ax, model, walls, "#3a3a3a", "#111", 0.3, z=6)
    cols = model.sel(lambda o: o["ifc_class"] == "IfcColumn")
    draw_top(ax, model, cols, "#c0392b", "#5b1a14", 0.4, z=7)
    # doors as white gaps with outline
    for o in model.sel(lambda o: o["ifc_class"] in ("IfcDoor", "IfcWindow")):
        x0, y0, _, x1, y1, _ = o["opening"]
        if o["storey"] == "L02" or "BOOTH" in o["name"] or "L02" in o["name"]:
            continue
        ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, fc="white", ec="#1565c0", lw=0.9, zorder=7))
    n_c = chairs(ax, model, "#2c5aa0", "40_SEAT_Congregation")
    for o in model.sel(lambda o: o["ifc_class"] == "IfcAudioVisualAppliance" and o["predefined_type"] == "DISPLAY"):
        w = model.world(o)
        ax.add_patch(Rectangle((w[:, 0].min(), w[:, 1].min() - 0.2), np.ptp(w[:, 0]), 0.5, fc="#c2185b", ec="none", zorder=9))
        ax.text(w[:, 0].mean(), w[:, 1].min() - 0.9, o["name"].replace("SRV-AV-", ""), ha="center", fontsize=6.5,
                color="#c2185b", zorder=9)
    chairs(ax, model, "#7b3fa0", "40_SEAT_Choir")
    chairs(ax, model, "#12a38a", "40_SEAT_Companion")
    draw_top(ax, model, model.sel(lambda o: o["object_type"] == "WheelchairSpace" and o["storey"] != "L02"),
             "#2ecc71", "#145a32", 0.6, z=5)
    draw_top(ax, model, model.sel(lambda o: o["object_type"] == "WheelchairSpace" and o["storey"] == "L02"),
             "#2ecc71", "#145a32", 0.6, z=5)
    # spaces labels
    for o in model.sel(lambda o: o["ifc_class"] == "IfcSpace" and o["storey"] == "L00"):
        w = model.world(o)
        cx, cy = w[:, 0].mean(), w[:, 1].mean()
        name = o["props"]["LongName"]
        if name.startswith("Auditorium"):
            cy = (lay.cross_passage[0] + lay.cross_passage[1]) / 2
            cx = 29.5
            ax.text(cx, cy, f"MID CROSS AISLE L01 +{lay.cross_level:.2f}  (2.40 passage + 1.50 wheelchair band)",
                    ha="center", va="center", fontsize=9, weight="bold", zorder=9,
                    bbox=dict(fc="#fff3c4", ec="#b08a1e", pad=1.5))
            continue
        if name.startswith(("Platform /", "Foyer below")):
            cy = cy - 2.5
        rot = 90 if np.ptp(w[:, 1]) > 3 * np.ptp(w[:, 0]) else 0
        if name.startswith(("Foyer side passage", "Accessible WCs")):
            name = name.split(" (")[0].replace("Foyer side passage", "Passage").replace("Accessible WCs", "Acc. WC")
            rot = 90
        ax.text(cx, cy, f"{name}\n{o['props']['GrossFloorArea']:.0f} m²", ha="center", va="center", fontsize=7.5,
                rotation=rot, zorder=9, bbox=dict(fc="white", ec="none", alpha=0.75, pad=0.8))
    # egress: exits with balanced load / placeholder required width
    for ex in lay.exits:
        x, y = ex["x"], ex["y"]
        if ex["wall"] == "W":
            tx, ty, dx, dy, ha = x - 3.6, y, -2.2, 0, "right"
        elif ex["wall"] == "E":
            tx, ty, dx, dy, ha = x + 3.6, y, 2.2, 0, "left"
        else:
            tx, ty, dx, dy, ha = x, 3.6, 0, -2.2, "center"
        ax.annotate("", xy=(x + dx, y + dy), xytext=(x - dx * 0.6, y - dy * 0.6),
                    arrowprops=dict(arrowstyle="-|>", color="#d32f2f", lw=2.2), zorder=10)
        lbl = ex["id"].replace("DR-HALL-", "")
        ax.text(tx + (dx * 0.8), ty + (0 if ex["wall"] == "REAR" else dy * 0.9), f"EXIT {lbl}\nw {ex['width']:.2f} | bal {ex['load']} / near {ex['load_nearest']}\nreq {ex['required_width']:.2f} / {ex['required_width_nearest']:.2f}*",
                ha=ha, va="center", fontsize=7, color="#b71c1c", zorder=10,
                bbox=dict(fc="white", ec="#d32f2f", lw=0.5, pad=0.8))
    # egress route lines (schematic): aisles -> cross routes -> exits
    rw0 = lay.rows[0]
    routes = []
    front_y = (rw0["yf"] + P["stage"]["front_edge_y"]) / 2
    cross_y = (lay.cross_passage[0] + lay.cross_passage[1]) / 2
    rear_y = (gy["3"] + 0.15 + lay.rows[-1]["yb"]) / 2
    xa0, xa1 = gx["B"] + 0.5, gx["G"] - 0.5
    for yy in (front_y, cross_y, rear_y):
        routes.append([(xa0, yy), (xa1, yy)])
    for a0, a1 in lay.rows[0]["aisles"]:
        xc = (a0 + a1) / 2
        routes.append([(xc, rear_y), (xc, front_y)])
    ax.add_collection(LineCollection(routes, colors="#e53935", linewidths=1.0, linestyles=(0, (6, 3)), zorder=8, alpha=0.8))
    # dimensions
    dim_chain(ax, list(gx.values()), "x", ymax - 4.0, fs=8)
    dim_chain(ax, list(gy.values()), "y", xmin + 4.0, fs=8)
    dim(ax, (gx["A"], ymax - 6.2), (gx["H"], ymax - 6.2), f"{gx['H'] - gx['A']:.2f} overall (grid)", fs=9)
    dim(ax, (xmin + 6.2, gy["1"]), (xmin + 6.2, gy["12"]), f"{gy['12'] - gy['1']:.2f} overall (grid)", fs=9)
    _, _, (xi0, xi1) = lay.block_ranges()
    yd = 52.0
    blocks, aisles, _ = lay.block_ranges(0.0)
    edges = [xi0] + [e for b in blocks for e in b] + [xi1]
    dim_chain(ax, edges, "x", yd, fs=6.5, color="#0d47a1")
    ax.text(xi0, yd + 1.3, "nominal block / aisle chain (rows alternate +/-0.125 stagger; straight aisle clear 1.25)",
            fontsize=7, color="#0d47a1", zorder=9)
    dim(ax, (xi0, 57.0), (xi1, 57.0), f"{xi1 - xi0:.2f} hall clear (column faces)", fs=8, color="#0d47a1")
    ex = gx["G"] + 2.0
    dim(ax, (ex, lay.rows[0]["yf"]), (ex, P["stage"]["front_edge_y"]), "3.00 front zone", fs=7, color="#0d47a1")
    dim(ax, (ex, lay.cross_passage[0]), (ex, lay.cross_passage[1]), "2.40", fs=7, color="#0d47a1")
    dim(ax, (ex, lay.band[0]), (ex, lay.band[1]), "1.50", fs=7, color="#0d47a1")
    dim(ax, (ex, gy["3"] + 0.15), (ex, lay.rows[-1]["yb"]), f"{lay.rows[-1]['yb'] - gy['3'] - 0.15:.2f} rear X-aisle", fs=7,
        color="#0d47a1")
    r10 = lay.rows[9]
    dim(ax, (blocks[2][0] + 1.0, r10["yb"]), (blocks[2][0] + 1.0, r10["yf"]), "0.95 row", off=(0, 0), fs=6.5, color="#0d47a1")
    for rw in lay.rows:
        if rw["row"] in (1, 5, 10, 15, 19, 20, 25, 30, 35, 40):
            ax.text(blocks[0][0] - 0.3, (rw["yb"] + rw["yf"]) / 2, f"R{rw['row']} {rw['floor']:+.2f}", ha="right",
                    va="center", fontsize=6, color="#333", zorder=9)
    # legend + title
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch
    leg = [Patch(fc="#2c5aa0", label=f"Congregation seat (model count {n_c})"), Patch(fc="#7b3fa0", label="Choir seat (excluded)"),
           Patch(fc="#2ecc71", ec="#145a32", label=f"Wheelchair space ({lay.metrics['wheelchair_spaces']})"),
           Patch(fc="#12a38a", label="Companion chair (loose)"), Patch(fc="#c0392b", label="Column (placeholder size)"),
           Patch(fc="#3a3a3a", label="Wall"), Patch(fc="white", ec="#1565c0", label="Door / opening"),
           Patch(fc="#f7e6a8", ec="#b08a1e", label="Ramp"), Patch(fc="#f3d27a", ec="#8a6a12", label="Stair"),
           Line2D([0], [0], color="#e53935", ls="--", label="Provisional egress route (schematic)"),
           Line2D([0], [0], color="#d32f2f", marker=">", label="Hall exit: width | balanced / nearest load | *placeholder req. widths")]
    fig.legend(handles=leg, loc="lower right", bbox_to_anchor=(0.995, 0.004), ncol=2, fontsize=9, framealpha=0.95)
    scale_bar(ax, xmax - 30, ymin + 4.2)
    north(ax, xmax - 3, ymin + 3)
    ax.set_xlim(xmin, xmax + 2)
    ax.set_ylim(ymin, ymax)
    ax.axis("off")
    eg = lay.metrics["egress"]
    title_block(fig, "FLOOR PLAN - LEVEL 00 / 01 (ground, raked hall, mid cross aisle)", rev,
                f"{len(lay.rows)} rows of up to 76 ({lay.metrics.get('trimmed_seats', 0)} worst off-axis seats removed). Rake: front slope to +{lay.front_slope_top:.2f}, cross aisle +{lay.cross_level:.2f}, "
                f"rear platform +{lay.top_level:.2f}. *Exit req. width = load x 5 mm/person PLACEHOLDER, queue-balanced "
                f"assignment;\nmax plan travel in hall {eg['max_travel_hall']:.1f} m / to external door {eg['max_travel_total']:.1f} m "
                f"(flags 30/60 m are placeholders - local code to govern). Project north assumed.",
                "Scale: schematic, see scale bar")
    fig.savefig(out / "floor_plan.png", dpi=DPI)
    plt.close(fig)


def upper_plan(model, lay, out, rev):
    P = lay.P
    gx, gy = P["grid"]["x_lines"], P["grid"]["y_lines"]
    fig = plt.figure(figsize=(26, 12))
    ax = fig.add_axes([0.03, 0.17, 0.94, 0.8])
    ax.set_aspect("equal")
    sub = {k: v for k, v in gy.items() if int(k) <= 4}
    xmin, xmax, ymin, ymax = grid_and_bubbles(ax, gx, sub, ext=6)
    draw_top(ax, model, model.sel(lambda o: o["name"] in ("ARC-SLAB-UPPER-FOYER", "ARC-SLAB-REAR-PLATFORM", "ARC-BOOTH-FLOOR")),
             "#eef0e8", "#999", 0.5, z=1)
    draw_top(ax, model, model.sel(lambda o: o["name"].startswith("ARC-RAKE-R3") or o["name"].startswith("ARC-RAKE-R4")),
             "#e4e8f0", "#9aa4b8", 0.3, z=1)
    draw_top(ax, model, model.sel(lambda o: o["ifc_class"] == "IfcStair" and "FOYER" in o["name"]), "#f3d27a", "#8a6a12", 0.5, z=3)
    draw_top(ax, model, model.sel(lambda o: o["ifc_class"] == "IfcRailing"), "#555", "#222", 0.5, z=5)
    draw_top(ax, model, model.sel(lambda o: o["ifc_class"] == "IfcWall" and (o["name"].startswith(("ARC-WALL-BOOTH", "ARC-WALL-LIFT", "ENV-WALL-HALL-REAR", "ENV-WALL-EXT")))),
             "#3a3a3a", "#111", 0.3, z=6)
    draw_top(ax, model, model.sel(lambda o: o["ifc_class"] == "IfcColumn"), "#c0392b", "#5b1a14", 0.4, z=7)
    draw_top(ax, model, model.sel(lambda o: o["object_type"] == "WheelchairSpace" and o["storey"] == "L02"), "#2ecc71", "#145a32", 0.6, z=5)
    refs = model.sel(lambda o: o["object_type"] == "RefugeSpace")
    draw_top(ax, model, refs, "#ff8a65", "#bf360c", 0.8, z=6, hatch="//")
    for o in refs:
        if o["name"].endswith("-1"):
            w = model.world(o)
            ax.text(w[:, 0].mean() - 0.5, w[:, 1].max() + 0.35, "REFUGE x2", fontsize=7, color="#bf360c", ha="center", zorder=9)
    chairs(ax, model, "#2c5aa0", "40_SEAT_Congregation")
    for o in model.sel(lambda o: o["ifc_class"] in ("IfcDoor", "IfcWindow") and (o["opening"][2] > 3.0)):
        x0, y0, _, x1, y1, _ = o["opening"]
        ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, fc="white", ec="#1565c0", lw=0.9, zorder=8))
        ax.text((x0 + x1) / 2, y0 - 0.7, o["name"].replace("DR-HALL-", "").replace("DR-", ""), ha="center", fontsize=7, color="#1565c0", zorder=9)
    for s in lay.stairs:
        ax.text((s["x0"] + s["x1"]) / 2, s["y_foot"] - 0.9,
                f"{s['name'][4:]}  w {s['width']:.2f}  {lay.metrics['foyer_stair_risers']} x {lay.metrics['foyer_stair_riser']:.3f} risers",
                ha="center", fontsize=7, zorder=9)
    ax.text(29.5, 13.4, f"SOUND / MEDIA BOOTH\nfloor +{lay.top_level + P['foyer']['booth_floor_raise']:.2f}", ha="center", fontsize=8, zorder=9)
    ax.text(5, 12.0, f"UPPER FOYER L02 +{lay.top_level:.2f}\n(over toilets / foyer)", fontsize=8, zorder=9)
    ax.text(29.5, 18.0, f"REAR PLATFORM / REAR CROSS AISLE +{lay.top_level:.2f} with rear wheelchair spaces", ha="center", fontsize=8, zorder=9,
            bbox=dict(fc="white", ec="none", alpha=0.8))
    lx0, ly0, lx1, ly1 = P["foyer"]["lift_xy"]
    ax.text((lx0 + lx1) / 2, ly1 + 0.4, "LIFT", ha="center", fontsize=8, zorder=9)
    ax.set_xlim(xmin, xmax)
    ax.set_ylim(ymin, 30)
    ax.axis("off")
    scale_bar(ax, xmax - 24, ymin + 1.0)
    title_block(fig, f"UPPER FOYER PLAN - LEVEL 02 (+{lay.top_level:.2f})", rev,
                f"Refuge allowances (hatched, A-21/OI-16): {len(lay.refuges)}; wheelchair places on this level: {lay.metrics['wheelchair_spaces_L02']}. "
                f"{len(lay.stairs)} foyer stairs rising through slab openings, total width {sum(s['width'] for s in lay.stairs):.1f} m; rear-door balanced load "
                f"{lay.metrics['egress']['rear_load_to_upper_foyer']} persons (placeholder demand "
                f"{lay.metrics['egress']['upper_foyer_stair_required_placeholder']:.2f} m @ 7.5 mm/p).", "Scale: see scale bar")
    fig.savefig(out / "upper_foyer_plan.png", dpi=DPI)
    plt.close(fig)


def structural(model, lay, out, rev):
    P = lay.P
    st = P["structure"]
    gx, gy = P["grid"]["x_lines"], P["grid"]["y_lines"]
    fig = plt.figure(figsize=(26, 34))
    ax = fig.add_axes([0.03, 0.27, 0.94, 0.71])
    ax.set_aspect("equal")
    xmin, xmax, ymin, ymax = grid_and_bubbles(ax, gx, gy, ext=9)
    # footings dashed
    for o in model.sel(lambda o: o["ifc_class"] == "IfcFooting"):
        w = model.world(o)
        ax.add_patch(Rectangle((w[:, 0].min(), w[:, 1].min()), np.ptp(w[:, 0]), np.ptp(w[:, 1]), fc="none", ec="0.4",
                               ls="--", lw=0.6, zorder=2))
    # beams
    draw_top(ax, model, model.sel(lambda o: o["ifc_class"] == "IfcBeam"), "#e8b4b0", "#8e3b33", 0.3, alpha=0.9, z=3)
    # members from strut endpoints (plan projection)
    def segs(pred):
        return [[(o["strut"][0][0], o["strut"][0][1]), (o["strut"][1][0], o["strut"][1][1])] for o in model.sel(pred)]
    ax.add_collection(LineCollection(segs(lambda o: o["predefined_type"] == "PURLIN"), colors="#999", linewidths=0.5, zorder=3))
    ax.add_collection(LineCollection(segs(lambda o: o["name"].startswith("STR-BRACE-ROOF")), colors="#ef6c00", linewidths=1.0, zorder=4))
    ax.add_collection(LineCollection(segs(lambda o: o["predefined_type"] == "CHORD" and "-BC" in o["name"]), colors="#b71c1c",
                                     linewidths=2.6, zorder=5))
    for t in lay.trusses:
        ax.text((gx["B"] + gx["G"]) / 2, t["y"] + 0.9, f"{t['name'][4:]}  span {t['span']:.1f} m  ({t['members']} members)",
                ha="center", fontsize=8, color="#b71c1c", zorder=9, bbox=dict(fc="white", ec="none", alpha=0.8, pad=0.5))
    # wall + gable bracing indicators
    for o in model.sel(lambda o: o["name"].startswith(("STR-BRACE-WALL", "STR-BRACE-GABLE"))):
        (x0, y0, _), (x1, y1, _) = o["strut"][0], o["strut"][1]
        ax.plot([x0, x1], [y0, y1], color="#ef6c00", lw=3.0, zorder=6)
    for a, b in st["wall_braced_bays"]:
        for L in ("B", "G"):
            ax.text(gx[L] + (1.5 if L == "B" else -1.5), (gy[a] + gy[b]) / 2, "VB", ha="center", va="center", fontsize=9,
                    weight="bold", color="#ef6c00", zorder=9, bbox=dict(fc="white", ec="#ef6c00", pad=0.6))
    cols = model.sel(lambda o: o["ifc_class"] == "IfcColumn")
    draw_top(ax, model, cols, "#c0392b", "#5b1a14", 0.4, z=7)
    for o in cols:
        w = model.world(o)
        ax.text(w[:, 0].max() + 0.25, w[:, 1].max() + 0.25, f"{o['props']['NominalSection'].split()[0]}\n^{w[:, 2].max():.2f}",
                fontsize=5.5, color="#5b1a14", zorder=9)
    dim_chain(ax, list(gx.values()), "x", ymax - 4.0, fs=8)
    dim_chain(ax, list(gy.values()), "y", xmin + 4.0, fs=8)
    dim(ax, (gx["B"], gy["6"] + 4), (gx["G"], gy["6"] + 4), f"{gx['G'] - gx['B']:.1f} clear-span truss (grid to grid)", fs=9,
        color="#b71c1c")
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch
    leg = [Patch(fc="#c0392b", label=f"Column ({lay.metrics['column_count']}) - placeholder size, ^ = top level"),
           Patch(fc="none", ec="0.4", ls="--", label="Pad footing REFERENCE location (not designed)"),
           Line2D([0], [0], color="#b71c1c", lw=2.6, label="Roof truss (bottom chord in plan)"),
           Line2D([0], [0], color="#999", lw=0.6, label="Purlin"),
           Line2D([0], [0], color="#ef6c00", lw=1.0, label="Roof-plane bracing (braced bays)"),
           Line2D([0], [0], color="#ef6c00", lw=3.0, label="Vertical bracing (VB) / gable bracing"),
           Patch(fc="#e8b4b0", ec="#8e3b33", label="Beams: foyer / mezzanine / low roofs / eaves ties")]
    fig.legend(handles=leg, loc="lower left", bbox_to_anchor=(0.68, 0.175), fontsize=9, framealpha=0.95)
    scale_bar(ax, xmax - 30, ymin + 4.2)
    ax.set_xlim(xmin, xmax + 2)
    ax.set_ylim(ymin, ymax)
    ax.axis("off")
    # truss elevation inset (truss on grid 6) from manifest member endpoints (x-z)
    ax2 = fig.add_axes([0.05, 0.085, 0.6, 0.15])
    tr = model.sel(lambda o: o["assembly"] == "STR-TRUSS-T6")
    ax2.add_collection(LineCollection([[(o["strut"][0][0], o["strut"][0][2]), (o["strut"][1][0], o["strut"][1][2])] for o in tr],
                                      colors=["#b71c1c" if o["predefined_type"] == "CHORD" else "#e57373" for o in tr],
                                      linewidths=[2.2 if o["predefined_type"] == "CHORD" else 1.0 for o in tr]))
    for L in ("B", "G"):
        ax2.add_patch(Rectangle((gx[L] - 0.3, 0), 0.6, st["truss_bearing_z"], fc="#c0392b"))
    ax2.axhline(0, color="k", lw=0.8)
    ax2.set_xlim(gx["B"] - 3, gx["G"] + 3)
    ax2.set_ylim(-1, 20)
    ax2.set_aspect("equal")
    ax2.set_title(f"TYPICAL TRUSS ELEVATION (T6, grid 6) - from model members: bearing +{st['truss_bearing_z']:.2f}, depth "
                  f"{st['truss_depth_eaves']:.1f} eaves / {st['truss_depth_ridge']:.1f} ridge, {st['truss_panels']} panels x "
                  f"{(gx['G'] - gx['B']) / st['truss_panels']:.1f} m (Pratt). Ridge roof top +{lay.metrics['hall_ridge_top']:.2f}", fontsize=9)
    ax2.set_xlabel("x (m)")
    ax2.set_ylabel("z (m)")
    ax2.grid(alpha=0.3)
    lv = "\n".join(f"{l['id']}  {l['elevation']:+7.3f}  {l['name'][10:]}" for l in lay.levels())
    fig.text(0.68, 0.09, "LEVELS (model)\n" + lv, fontsize=9, family="monospace", va="bottom",
             bbox=dict(fc="white", ec="k", lw=0.6, pad=5))
    title_block(fig, "STRUCTURAL GRID & FRAMING CONCEPT (coordination only)", rev,
                "Lateral concept (A-13): transverse portal action truss/column + braced gable bays; longitudinal X-bracing in end bays "
                "(VB); roof-plane bracing bays 3-4, 7-8, 10-11.\nNO loads, analysis or member design. All sizes are space reservations. "
                "Foundations are reference locations only (no geotechnical data).", "Scale: see scale bar")
    fig.savefig(out / "structural_grid.png", dpi=DPI)
    plt.close(fig)


def long_section(model, lay, out, rev):
    P = lay.P
    gy = P["grid"]["y_lines"]
    S, ST = P["seating"], P["stage"]
    blocks, _, _ = lay.block_ranges(0.0)
    xs = (blocks[2][0] + blocks[2][1]) / 2
    fig = plt.figure(figsize=(30, 12))
    ax = fig.add_axes([0.04, 0.2, 0.93, 0.76])
    ax.set_aspect("equal")
    # cut elements at x = xs: draw y-z faces of objects whose x-range includes xs
    polys = []
    colours = []
    for o in model.objs:
        if (o["ifc_class"] not in ("IfcSlab", "IfcWall", "IfcStair", "IfcRamp", "IfcRailing") or o["collection"].startswith("60")
                or o["predefined_type"] == "ROOF"):  # pitched roof is drawn from roof_z (not uniform in x)
            continue
        w = model.world(o)
        if not (w[:, 0].min() - 1e-6 <= xs <= w[:, 0].max() + 1e-6):
            continue
        for fc in model.meshes[o["mesh"]]["faces"]:
            p = w[fc]
            n = np.cross(p[1] - p[0], p[2] - p[0])
            ln = np.linalg.norm(n)
            if ln > 1e-12 and abs(n[0]) / ln > 0.9 and p[:, 0].min() <= xs:
                polys.append(p[:, 1:3])
                colours.append("#555" if o["ifc_class"] == "IfcWall" else ("#8a6d3b" if o["name"] == "ARC-PLATFORM" or "CHOIR" in o["name"] else "#bdbdbd"))
    ax.add_collection(PolyCollection(polys, facecolors=colours, edgecolors="#333", linewidths=0.3, zorder=2))
    # chairs in the cut block (from manifest)
    for o in model.sel(lambda o: o["collection"] in ("40_SEAT_Congregation", "40_SEAT_Choir")):
        x, y, z = o["matrix"][0][3], o["matrix"][1][3], o["matrix"][2][3]
        if abs(x - xs) < 0.26:
            s = 1 if o["collection"] == "40_SEAT_Congregation" else -1
            ax.plot([y + s * 0.25, y - s * 0.25, y - s * 0.3], [z + 0.45, z + 0.45, z + 0.85],
                    color="#2c5aa0" if s == 1 else "#7b3fa0", lw=1.4, zorder=4)
    # sightlines from selected rows to focal point
    yf, zf = ST["front_edge_y"], ST["platform_height"] + P["sightlines"]["focal_height_above_platform"]
    ax.plot(yf, zf, marker="*", ms=14, color="#d32f2f", zorder=6)
    ax.text(yf + 0.3, zf + 0.4, f"Focal point: platform edge +0.60 (z {zf:.2f})", fontsize=8, color="#d32f2f")
    for rw in lay.rows:
        if rw["row"] in (3, 10, 19, 20, 30, 40):
            ye = rw["yb"] + S["eye_offset_from_tread_back"]
            ze = rw["floor"] + S["eye_height_seated"]
            ax.plot([ye, yf], [ze, zf], color="#e57373", lw=0.8, zorder=5)
            ax.plot(ye, ze, "o", color="#c62828", ms=3, zorder=6)
            ax.text(ye, ze + 0.35, f"R{rw['row']} C={rw['c_n1']:.3f}" if rw["c_n1"] else f"R{rw['row']}", fontsize=7, ha="center")
    # roof and truss at the cut
    rz = lay.roof_z(xs)
    st = P["structure"]
    ax.plot([gy["3"], gy["11"]], [rz + st["chord_section"] / 2 + st["purlin_section"][1] + st["roof_build_up"]] * 2, color="#555", lw=2.5)
    ax.plot([gy["3"], gy["11"]], [st["truss_bearing_z"] + st["chord_section"] / 2] * 2, color="#b71c1c", lw=1.0, ls="--")
    for n in range(3, 12):
        y = gy[str(n)]
        ax.add_patch(Rectangle((y - 0.18, st["truss_bearing_z"] + 0.02), 0.36, rz - st["truss_bearing_z"] + 0.15, fc="#b71c1c", zorder=4))
        ax.text(y, -2.6, str(n), ha="center", fontsize=11, weight="bold", bbox=dict(boxstyle="circle", fc="white", ec="k"))
    ax.text(gy["6"], rz + 1.4, f"Hall truss cut (depth at x={xs:.1f}: {rz - st['truss_bearing_z']:.2f} m) / roof", fontsize=8, ha="center")
    for lv in lay.levels():
        ax.axhline(lv["elevation"], color="#1565c0", lw=0.5, ls=":", zorder=1)
        ax.text(gy["12"] + 1, lv["elevation"], f"{lv['id']} {lv['elevation']:+.3f}", fontsize=8, color="#1565c0", va="center")
    for y0, y1, t in ((lay.rows[0]["yf"], ST["front_edge_y"], "front zone 3.00"),
                      (lay.cross_passage[0], lay.cross_passage[1], "X-aisle 2.40"),
                      (lay.band[0], lay.band[1], "WC 1.50"),
                      (gy["3"] + 0.15, lay.rows[-1]["yb"], "rear X-aisle")):
        dim(ax, (y0, -1.2), (y1, -1.2), t, fs=7)
    dim(ax, (ST["front_edge_y"] + 6, 0), (ST["front_edge_y"] + 6, ST["platform_height"]), "0.90", fs=7)
    ax.text(gy["2"], 5.5, f"UPPER FOYER / BOOTH\n+{lay.top_level:.2f}", ha="center", fontsize=8)
    ax.text(20.5, 5.9, "stepped rear section, uniform risers per band: " + ", ".join(
        f"R{b['rows'][0]}-{b['rows'][1]} {b['uniform_riser']:.3f}" for b in lay.rear_bands), fontsize=8)
    ax.text(46, 3.4, f"sloped front section (steepest 1:{lay.metrics['front_slope_gradient_1_in']:.1f})", fontsize=8)
    ax.set_xlim(gy["1"] - 3, gy["12"] + 6)
    ax.set_ylim(-3.5, 20)
    ax.set_xlabel("y (m) - towards platform ->")
    ax.grid(alpha=0.15)
    title_block(fig, f"LONGITUDINAL SECTION through block 3 (x = {xs:.2f}) - rake and sightlines", rev,
                f"C-value target {P['sightlines']['c_value_target']} m over row in front (staggered seating), seated eye "
                f"{S['eye_height_seated']} m; min C achieved {lay.metrics['c_min_n1']:.3f} m; max eye distance to platform edge "
                f"{lay.metrics['max_viewing_distance_to_platform_edge']:.1f} m (screens assumed for rear rows).", "Scale: 1:1 aspect, metres")
    fig.savefig(out / "long_section.png", dpi=DPI)
    plt.close(fig)


def balcony_section(lay, out, rev):
    """Option B schematic (computed from the same sightline rules) - NOT part of the BIM model."""
    B = lay.balcony
    P = lay.P
    m = lay.metrics["options"]["B_floor_plus_balcony"]
    fig = plt.figure(figsize=(24, 9))
    ax = fig.add_axes([0.05, 0.22, 0.92, 0.72])
    ax.set_aspect("equal")
    yf, zf = B["focal"]
    fl = B["floor"]
    ys = [yf - P["stage"]["front_clear_zone"]] + [p[0] for p in fl]
    zs = [0.0] + [p[1] for p in fl]
    ax.step(ys, zs, where="post", color="#555", lw=1.5)
    ax.fill_between(ys, -0.3, zs, step="post", color="#ddd")
    bl = B["balcony"]
    by = [B["y_front"]] + [p[0] for p in bl]
    bz = [P["balcony_option"]["balcony_floor_level"]] + [p[1] for p in bl]
    ax.step(by, bz, where="post", color="#6a1b9a", lw=1.5)
    ax.fill_between(by, B["soffit"], bz, step="post", color="#e1bee7")
    ax.plot([B["y_front"], B["y_front"]], [B["soffit"], P["balcony_option"]["balcony_floor_level"] + P["balcony_option"]["parapet_height"]],
            color="#6a1b9a", lw=2)
    ax.add_patch(Rectangle((yf, 0), 12, P["stage"]["platform_height"], fc="#f1e2c8", ec="#8a6d3b"))
    ax.plot(yf, zf, marker="*", ms=14, color="#d32f2f")
    ye, ze = B["rear_eye"]
    ax.plot([ye, B["target"][0]], [ze, B["target"][1]], color="#e57373", lw=1)
    for (y, z) in (fl[0], fl[len(fl) // 2], bl[0], bl[-1]):
        ax.plot([y + 0.4, yf], [z + 1.15, zf], color="#ef9a9a", lw=0.7)
    ax.axhline(B["soffit"], xmin=0, xmax=1, color="#6a1b9a", lw=0.4, ls=":")
    ax.text(B["y_front"] - 2, B["soffit"] - 0.6, f"soffit +{B['soffit']:.2f}", fontsize=8, color="#6a1b9a")
    ax.text(bl[-1][0], bl[-1][1] + 1.6, f"balcony top row +{bl[-1][1]:.2f}  ({m['balcony_rake_deg']} deg rake)", fontsize=8, color="#6a1b9a")
    ax.text(fl[-1][0], -1.4, f"rear floor row: view to +2.5 m over platform passes {m['rear_floor_row_view_clearance_below_soffit_m']} m below soffit;"
            f" overhang {m['overhang_depth_m']} m / opening {m['opening_height_m']} m = {m['overhang_depth_to_height']}", fontsize=8)
    ax.set_xlim(min(by) - 4, yf + 14)
    ax.set_ylim(-2.5, max(bz) + 4)
    ax.set_xlabel("distance (m) - towards platform ->")
    ax.grid(alpha=0.2)
    title_block(fig, "OPTION B - FLOOR + BALCONY: COMPUTED SCHEMATIC SECTION (comparison only, not modelled in BIM)", rev,
                f"{P['balcony_option']['floor_seats']} floor seats in {m['floor_rows']} rows + {P['balcony_option']['balcony_seats']} balcony seats in "
                f"{m['balcony_rows']} rows; same C-value rule (0.06 m) as Option A. Structural, egress and acoustic implications in basis_of_design.md.",
                "Scale: 1:1 aspect, metres")
    fig.savefig(out / "balcony_option_section.png", dpi=DPI)
    plt.close(fig)


def main(manifest, outdir):
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    model = Model(manifest)
    lay = al.compute(al.load_params())
    rev = model.M["revision"]
    floor_plan(model, lay, out, rev)
    upper_plan(model, lay, out, rev)
    structural(model, lay, out, rev)
    long_section(model, lay, out, rev)
    balcony_section(lay, out, rev)
    print("DRAWINGS " + json.dumps(sorted(p.name for p in out.glob("*.png"))))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
