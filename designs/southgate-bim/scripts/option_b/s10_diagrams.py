"""Structural comparison diagrams from exported IFC geometry (run with a Python that has matplotlib).

  py -3.10 scripts/option_b/s10_diagrams.py work/option_b/views/views_geometry.json.gz <outdir>
Every drawing is a projection or a plane section of the actual IFC triangles (no idealised redraw).
"""
import gzip, json, math, sys
from collections import defaultdict
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection, LineCollection
from matplotlib.patches import Polygon as MP, Circle, Rectangle

D = json.load(gzip.open(sys.argv[1], "rt", encoding="utf-8"))
out = Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
C = {"TRUSS_TOP_CHORD": "#3f6fa8", "TRUSS_BOTTOM_CHORD": "#3f6fa8", "TRUSS_WEB_VERTICAL": "#5d9c59", "TRUSS_END_POST": "#2e7d32",
     "TRUSS_KING_POST": "#1b5e20", "TRUSS_WEB_DIAGONAL": "#7fb77e", "GUSSET_PLATE": "#e8a33d", "SPLICE_PLATE": "#c0392b",
     "PACKING_PLATE": "#6d6d6d", "IfcPlate": "#e8a33d", "IfcMechanicalFastener": "#333333"}
EX = "#9e9e9e"
TITLE = dict(fontsize=11, fontweight="bold", loc="left")
NOTE = "Projection / section of the IFC geometry - CONCEPT, NOT FOR CONSTRUCTION"


def hull(P):
    P = sorted(set(map(tuple, np.round(P, 5))))
    if len(P) < 3:
        return P
    def cr(o, a, b): return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lo, up = [], []
    for p in P:
        while len(lo) >= 2 and cr(lo[-2], lo[-1], p) <= 0: lo.pop()
        lo.append(p)
    for p in reversed(P):
        while len(up) >= 2 and cr(up[-2], up[-1], p) <= 0: up.pop()
        up.append(p)
    return lo[:-1] + up[:-1]


def proj(e, ax_i):
    v = np.array(e["v"])
    return v[:, ax_i]


def draw_proj(ax, els, axes=(1, 2), color=None, alpha=1.0, outline=True, lw=0.35, depth_axis=0, zorder=2, ec="k", filt=None):
    els = [e for e in els if (filt is None or filt(e))]
    els = sorted(els, key=lambda e: np.mean(np.array(e["v"])[:, depth_axis]))
    for e in els:
        v = np.array(e["v"]); f = np.array(e["f"])
        if not len(f):
            continue
        col = color or C.get(e["role"], C.get(e["cls"], EX))
        tris = v[f][:, :, list(axes)]
        ax.add_collection(PolyCollection(tris, facecolors=col, edgecolors="none", alpha=alpha, zorder=zorder))
        if outline:
            if e["role"] in ("GUSSET_PLATE",) and len(v) > 8:
                # non-convex outline (rigging tab): boundary edges of the projected front face
                pass
            h = hull(v[:, list(axes)])
            ax.add_patch(MP(h, closed=True, fill=False, ec=ec, lw=lw, zorder=zorder + 0.1))


def section(ax, els, plane_axis, value, axes, color=None, lw=0.9, zorder=3):
    """plane section of the triangle meshes: draws the cut segments"""
    for e in els:
        v = np.array(e["v"]); f = np.array(e["f"])
        if not len(f):
            continue
        d = v[:, plane_axis] - value
        if d.min() > 0 or d.max() < 0:
            continue
        segs = []
        for tri in f:
            dd = d[tri]
            if (dd > 0).all() or (dd < 0).all():
                continue
            pts = []
            for i, j in ((0, 1), (1, 2), (2, 0)):
                a, b = tri[i], tri[j]
                if (d[a] > 0) != (d[b] > 0):
                    t = d[a] / (d[a] - d[b])
                    p = v[a] + t * (v[b] - v[a])
                    pts.append(p[list(axes)])
            if len(pts) == 2:
                segs.append(pts)
        if segs:
            ax.add_collection(LineCollection(segs, colors=color or C.get(e["role"], C.get(e["cls"], EX)), linewidths=lw, zorder=zorder))


def finish(ax, title, xl=None, yl=None, xlabel="y (m)", ylabel="z (m)"):
    ax.set_aspect("equal")
    if xl: ax.set_xlim(*xl)
    if yl: ax.set_ylim(*yl)
    ax.set_title(title, **TITLE)
    ax.set_xlabel(xlabel, fontsize=8); ax.set_ylabel(ylabel, fontsize=8); ax.tick_params(labelsize=7)
    ax.grid(True, lw=0.25, alpha=0.5)


def bolts_in(ax, truss, sel=None, axes=(1, 2), size=0.009):
    for b in D["bolts_new"]:
        if b["truss"] != truss or (sel and not sel(b)):
            continue
        x, y, z = b["xyz"]
        p = (x, y, z)
        ax.add_patch(Circle((p[axes[0]], p[axes[1]]), b["d"] / 2 + 0.002, fc={"WEB": "#111", "CHORD": "#1f4e79", "SPLICE": "#c0392b", "PACKER": "#555"}.get(b["role"], "#111"),
                            ec="white", lw=0.2, zorder=6))


def save(fig, name):
    fig.text(0.995, 0.005, NOTE, ha="right", va="bottom", fontsize=7, color="#a00")
    fig.savefig(out / name, dpi=170, bbox_inches="tight"); plt.close(fig)
    print("saved", name)


def label_members(ax, els, roles=None, fs=6.5):
    seen = set()
    for e in els:
        if e["cls"] != "IfcMember" or (roles and e["role"] not in roles):
            continue
        mark = e["name"].split("-")[-2]
        if mark in seen:
            continue
        seen.add(mark)
        v = np.array(e["v"]); c = v.mean(0)
        sec = (e["tag"] or "").split("/")[-1]
        ax.text(c[1], c[2], mark, fontsize=fs, ha="center", va="center", zorder=8, bbox=dict(boxstyle="round,pad=0.12", fc="white", ec="none", alpha=0.8))


newT, oldT = D["new_T05"], D["old_T05"]
mem_sec = {}
for e in newT:
    if e["cls"] == "IfcMember":
        mem_sec[e["name"].split("-")[-2]] = e["name"]

# ---------------------------------------------------------------- V01 existing vs Option B elevation
fig, axs = plt.subplots(3, 1, figsize=(17, 13))
draw_proj(axs[0], oldT); draw_proj(axs[0], D["heel_existing"], color=EX, alpha=0.35)
for b in D["bolts_old"]:
    if b["truss"] == "SOUTHGATE-TRUSS-T05":
        axs[0].add_patch(Circle((b["xyz"][1], b["xyz"][2]), 0.012, fc="k", zorder=6))
finish(axs[0], "SUPERSEDED - 16-panel migrated truss T05 (line 4, x = 25.49): 16 bays at 2.025 m, 53 members, 17 gussets, 6 splice plates, 18 bolts modelled", (-0.6, 33.3), (10.5, 17.1))
draw_proj(axs[1], newT); draw_proj(axs[1], D["heel_existing"], color=EX, alpha=0.35); bolts_in(axs[1], "SOUTHGATE-TRUSS-T05")
finish(axs[1], "OPTION B CANDIDATE - 12-bay Warren with verticals, truss T05 (type TT-T): 12 bays at 2.70 m, 37 built-up members (74 angles), 26 gussets, 20 splice plates, 86 packers, 330 bolt sets", (-0.6, 33.3), (10.5, 17.1))
draw_proj(axs[2], oldT, color="#d62728", alpha=0.35, outline=False); draw_proj(axs[2], newT, alpha=0.75, outline=False)
finish(axs[2], "Overlay - superseded (red) / Option B (colour): same span, bearings, pitch, ridge and bottom-chord level; 13 bottom panel points instead of 17", (-0.6, 33.3), (10.5, 17.1))
for k in range(13):
    axs[1].annotate(f"s={2.7 * k:.1f}", (0.3 + 2.7 * k, 10.62), fontsize=6, ha="center", color="#555")
save(fig, "V01_existing_vs_optionB_truss_elevation.png")

# ---------------------------------------------------------------- V02 roof framing plan
fig, axs = plt.subplots(1, 2, figsize=(20, 9.5))
for ax, mem, title in ((axs[0], D["old_members_all"], "SUPERSEDED roof framing - 11 x 16-panel trusses (members only)"),
                       (axs[1], D["new_members_all"], "OPTION B roof framing - 11 x 12-panel trusses (members; types TT-G / TT-R / TT-T)")):
    draw_proj(ax, D["purlins"], axes=(0, 1), color="#c8c8c8", alpha=0.9, outline=False, depth_axis=2, zorder=1)
    draw_proj(ax, D["bracing"], axes=(0, 1), color="#8e24aa", alpha=0.9, outline=False, depth_axis=2, zorder=2)
    draw_proj(ax, D["columns"], axes=(0, 1), color="#000", alpha=1, outline=False, depth_axis=2, zorder=4)
    draw_proj(ax, mem, axes=(0, 1), alpha=1, outline=False, depth_axis=2, zorder=3)
    finish(ax, title, (1.5, 60.6), (-1.0, 33.8), xlabel="x (m)", ylabel="y (m)")
types = {0: "TT-G", 10: "TT-G", 1: "TT-R", 2: "TT-R"}
for i in range(11):
    x = 3.25 + 5.56 * i
    axs[1].text(x, 33.4, f"T{i + 1:02d}\n{types.get(i, 'TT-T')}", ha="center", fontsize=7)
    axs[0].text(x, 33.4, f"T{i + 1:02d}", ha="center", fontsize=7)
    for k in range(13):
        axs[1].plot([x], [0.3 + 2.7 * k], "o", ms=1.8, color="#e8a33d", zorder=5)
axs[1].text(31, -0.8, "grey: existing purlins (unchanged) | purple: existing rod bracing (end bays) | black: UC254 columns | orange dots: Option B panel points", ha="center", fontsize=7)
save(fig, "V02_roof_framing_plan_existing_vs_optionB.png")

# ---------------------------------------------------------------- V03 typical truss elevation labelled
fig, ax = plt.subplots(figsize=(19, 6.5))
draw_proj(ax, newT); bolts_in(ax, "SOUTHGATE-TRUSS-T05"); label_members(ax, newT)
for k in range(13):
    ax.text(0.3 + 2.7 * k, 10.55, f"B{k:02d}", ha="center", fontsize=6.5, color="#7a4b00")
    ax.text(0.3 + 2.7 * k, 12.37 + math.tan(math.radians(15)) * min(2.7 * k, 32.4 - 2.7 * k) + 0.25, f"T{k:02d}", ha="center", fontsize=6.5, color="#7a4b00")
for s in (5.4, 10.8, 16.2, 21.6, 27.0):
    ax.annotate("BC splice", (0.3 + s, 10.85), (0.3 + s, 10.25), fontsize=6, ha="center", color="#c0392b", arrowprops=dict(arrowstyle="-", color="#c0392b", lw=0.5))
ax.annotate("", (0.3, 10.0), (32.7, 10.0), arrowprops=dict(arrowstyle="<->", lw=0.6)); ax.text(16.5, 9.88, "span 32.40 m between bearings (y = 0.30 .. 32.70); 12 bays x 2.70 m", ha="center", va="top", fontsize=7.5)
ax.annotate("", (-0.05, 10.9), (-0.05, 12.344), arrowprops=dict(arrowstyle="<->", lw=0.6)); ax.text(-0.15, 11.6, "1.444\n(setting-out)", ha="right", fontsize=6.5)
ax.annotate("", (16.95, 10.9), (16.95, 16.684), arrowprops=dict(arrowstyle="<->", lw=0.6)); ax.text(17.05, 13.8, "5.784 m depth at ridge (centroid lines)", fontsize=6.5, rotation=90, va="center")
ax.text(26, 16.4, "Top chord 2L90x90x8   Bottom chord 2L80x80x8\nDiagonals 2L100x100x8 / 2L75x75x6   Verticals 2L60x60x6 / 2L75x75x6\nEnd posts 2L70x70x6   King post 2L100x100x8   Gussets 10 mm\n15 deg pitch; top of steel on the existing purlin seat (DEV-01)",
        fontsize=7.5, va="top", bbox=dict(fc="white", ec="#999", lw=0.5))
finish(ax, "Typical Option B truss T05 (TT-T) - member marks, panel points and splices (truss shop/site joints: 10 chord splices incl. ridge apex)", (-1.2, 33.4), (9.6, 17.2))
save(fig, "V03_typical_truss_elevation_labelled.png")

# ---------------------------------------------------------------- V04 chord and web construction (sections)
fig, axs = plt.subplots(1, 4, figsize=(19, 5.6))
x0 = 25.49
cases = [(1, 0.3 + 1.35, "Bottom chord BC1 at mid-panel (y = 1.65): 2L80x80x8, 10 mm gap, packing plate + M20 bolt", (10.80, 11.05)),
         (1, 0.3 + 8.1 + 1.35 - 0.0, "Top chord TC2 vertical section (y = 9.75): 2L90x90x8, outstanding legs up, purlin seat above", None),
         (1, 0.3 + 10.8, "Bottom node B04 section (y = 11.10): BC splice - 2 splice plates + gusset + 2 angles, M20x70", (10.75, 11.25)),
         (1, 0.3 + 16.2, "Ridge apex T06 / king post section (y = 16.50)", None)]
for ax, (pa, val, title, zl) in zip(axs, cases):
    section(ax, newT, pa, val, (0, 2))
    section(ax, D["purlins"], pa, val, (0, 2), color="#999", lw=0.6)
    for b in D["bolts_new"]:
        if b["truss"] == "SOUTHGATE-TRUSS-T05" and abs(b["xyz"][1] - val) < 0.035:
            ax.plot([b["xyz"][0] - 0.035, b["xyz"][0] + 0.02], [b["xyz"][2]] * 2, color={"SPLICE": "#c0392b"}.get(b["role"], "#111"), lw=2.2, zorder=6)
    if zl is None:
        zz = [p[2] for e in newT for p in e["v"] if abs(p[1] - val) < 0.05]
        zl = (max(zz) - 0.35, max(zz) + 0.12) if zz else None
    finish(ax, title, (x0 - 0.16, x0 + 0.16), zl, xlabel="x (m)")
    ax.title.set_fontsize(7.5)
save(fig, "V04_chord_and_web_construction_sections.png")

# ---------------------------------------------------------------- V05 representative gusset connections
nodes = [("B00", 0.0, 10.9, "CT-BH bottom heel"), ("T00", 0.0, 12.34, "CT-TH top heel / bearing"), ("T01", 2.7, 13.07, "CT-TV2 top: V + 2 diagonals"),
         ("B01", 2.7, 10.9, "CT-BV bottom: vertical only"), ("T05", 13.5, 15.96, "CT-TV2 near ridge (steep diagonals)"), ("B06", 16.2, 10.9, "CT-BC centre: splice + king post + 2 D")]
fig, axs = plt.subplots(2, 3, figsize=(18, 12))
for ax, (nd, s, z, t) in zip(axs.flat, nodes):
    y = 0.3 + s
    sel = lambda e: abs(np.mean(np.array(e["v"])[:, 1]) - y) < 3.2
    draw_proj(ax, newT, filt=sel)
    bolts_in(ax, "SOUTHGATE-TRUSS-T05", sel=lambda b: abs(b["xyz"][1] - y) < 0.9)
    if nd in ("B00", "T00"):
        draw_proj(ax, D["heel_existing"], color=EX, alpha=0.45)
    for e in newT:
        if e["role"] == "GUSSET_PLATE" and e["name"].endswith(f"J-{nd}-GP"):
            c = np.array(e["v"]).mean(0)
            ax.text(c[1], c[2], f"{nd}-GP\n10 mm", fontsize=7, ha="center", va="center", zorder=9, bbox=dict(fc="#fff3d6", ec="#e8a33d", lw=0.5))
    for e in newT:
        if e["cls"] == "IfcMember" and e["name"].endswith("-A"):
            v = np.array(e["v"]); c = v.mean(0)
            if abs(c[1] - y) < 0.75 and abs(c[2] - z) < 0.75:
                ax.text(c[1], c[2], e["name"].split("-")[-2], fontsize=7, ha="center", zorder=9, bbox=dict(fc="white", ec="none", alpha=0.8))
    finish(ax, f"{nd} - {t}", (y - 0.7, y + 0.7), (z - 0.6, z + 0.6))
save(fig, "V05_representative_gusset_connections.png")

# ---------------------------------------------------------------- V06 splices and apex
fig, axs = plt.subplots(1, 3, figsize=(19, 6.4))
for ax, (nd, s, z, t) in zip(axs, [("B04", 10.8, 10.9, "CT-BS bottom-chord splice at B04 (8 x M20x70 through 2 splice plates, 2 angles, gusset)"),
                                   ("T04", 10.8, 15.25, "CT-TS top-chord splice at T04 (+ vertical V04)"),
                                   ("T06", 16.2, 16.65, "CT-TA ridge apex: chevron splice plates + king post VK06")]):
    y = 0.3 + s
    draw_proj(ax, newT, filt=lambda e: abs(np.mean(np.array(e["v"])[:, 1]) - y) < 3.2)
    bolts_in(ax, "SOUTHGATE-TRUSS-T05", sel=lambda b: abs(b["xyz"][1] - y) < 0.9)
    for e in newT:
        if e["role"] == "SPLICE_PLATE" and f"J-{nd}-SP-A" in e["name"]:
            h = hull(np.array(e["v"])[:, [1, 2]])
            ax.add_patch(MP(h, closed=True, fill=False, ec="#c0392b", lw=1.6, ls="--", zorder=10))
            c = np.array(e["v"]).mean(0)
            ax.annotate(f"{nd}-SP-A / -B (8 mm,\nouter faces of connected legs)", (c[1], c[2]), (c[1] + 0.05, c[2] - 0.38), fontsize=7, color="#c0392b",
                        arrowprops=dict(arrowstyle="->", color="#c0392b", lw=0.6), zorder=11)
    finish(ax, f"{nd} - {t}", (y - 0.75, y + 0.75), (z - 0.55, z + 0.45))
    ax.title.set_fontsize(8)
save(fig, "V06_splice_arrangements_and_apex.png")

# ---------------------------------------------------------------- V07 equipment suspension interfaces (line 2)
n3 = D["new_T03"]
fig, axs = plt.subplots(2, 1, figsize=(19, 9.5))
ax = axs[0]
draw_proj(ax, n3, filt=lambda e: np.array(e["v"])[:, 2].min() < 11.6)
draw_proj(ax, [e for e in D["equip_line2"] if abs(np.array(e["v"])[:, 0].mean() - 14.37) < 0.4], color="#8e24aa", alpha=0.85)
bolts_in(ax, "SOUTHGATE-TRUSS-T03", sel=lambda b: b["xyz"][2] < 11.6)
for k in range(13):
    ax.axvline(0.3 + 2.7 * k, color="#e8a33d", lw=0.4, ls=":")
    ax.text(0.3 + 2.7 * k, 11.62, f"B{k:02d}", fontsize=6.5, ha="center", color="#7a4b00")
for e in D["equip_line2"]:
    v = np.array(e["v"])
    if "CLAMP" in e["src"] and abs(v[:, 0].mean() - 14.37) < 0.4:
        yy = v[:, 1].mean(); d = min(abs(yy - (0.3 + 2.7 * k)) for k in range(13))
        ax.text(yy, 10.74, f"{d:.2f}", fontsize=5.5, ha="center", color="#8e24aa", rotation=90)
finish(ax, "Truss T03 (TT-R, line 2) bottom chord: rigging pick-up tabs at B01-B11 (provision, capacity NOT_AVAILABLE) and existing raft clamps / FOH hangers (purple, numbers = distance to the nearest panel point, m)",
       (-0.3, 33.0), (10.55, 11.7))
ax.title.set_fontsize(8.5)
ax = axs[1]
draw_proj(ax, D["new_members_all"], axes=(0, 1), outline=False, depth_axis=2, filt=lambda e: e["role"] == "TRUSS_BOTTOM_CHORD")
draw_proj(ax, D["hvls"], axes=(0, 1), color="#00838f", alpha=0.9, outline=True, depth_axis=2)
draw_proj(ax, D["clamps_all"], axes=(0, 1), color="#8e24aa", alpha=0.9, outline=False, depth_axis=2)
for e in D["equip_line2"]:
    if e["src"].startswith("ARRAY"):
        draw_proj(ax, [e], axes=(0, 1), color="#d81b60", alpha=0.9, depth_axis=2)
for i in range(11):
    for k in range(13):
        ax.plot(3.25 + 5.56 * i, 0.3 + 2.7 * k, "o", ms=2.2, color="#e8a33d", zorder=6)
ax.text(31, 33.5, "plan: Option B bottom chords (blue), panel points (orange), HVLS fan beams (teal, 0.15 m off node), raft clamps (purple), L/R arrays between lines 1-2 (pink, ~0.8 m off node)", ha="center", fontsize=7.5)
finish(ax, "Suspended-equipment interface plan", (1.5, 60.6), (-0.8, 34.2), xlabel="x (m)", ylabel="y (m)")
save(fig, "V07_equipment_suspension_interfaces.png")

# ---------------------------------------------------------------- V08 truss-to-column interface
fig, axs = plt.subplots(1, 2, figsize=(17, 8))
ax = axs[0]
draw_proj(ax, D["heel_existing"], color=EX, alpha=0.55, outline=True, ec="#555")
draw_proj(ax, newT, filt=lambda e: np.array(e["v"])[:, 1].min() < 1.6, alpha=0.9)
bolts_in(ax, "SOUTHGATE-TRUSS-T05", sel=lambda b: b["xyz"][1] < 1.6)
for e in D["heel_existing"]:
    c = np.array(e["v"]).mean(0)
    lab = e["src"].replace("ROOF-", "").replace("-RHS", "")
    if any(k in lab for k in ("COL-ROOF", "CAP", "SEAT", "OUTRIGGER", "EAVES-CLEAT")):
        ax.annotate(lab, (c[1], c[2]), (c[1] - 0.25 if "COL" in lab else c[1] + 0.35, c[2] + (0.25 if "CAP" in lab else -0.3 if "SEAT" in lab else 0.4)),
                    fontsize=6.5, color="#333", arrowprops=dict(arrowstyle="->", lw=0.5, color="#333"), zorder=12)
ax.add_patch(Rectangle((0.281, 12.18), 0.05, 0.14, fill=False, ec="#d00", lw=1.4, ls="--", zorder=13))
ax.text(0.36, 12.08, "C-01 conflict zone: cap plate (y <= 0.33) and 16 mm seat fin\nin the heel; top-chord toe at ~+12.27 below the cap top +12.313", fontsize=6.8, color="#d00")
finish(ax, "Heel at column COL-ROOF-4-0 (line 4, south) - elevation", (-0.45, 1.55), (10.6, 13.0))
ax = axs[1]
for val, col, lab in ((0.30, "#d00", "y = 0.30 (bearing / end-post line)"),):
    section(ax, newT, 1, val, (0, 2), lw=1.1)
    section(ax, D["heel_existing"], 1, val, (0, 2), color="#555", lw=0.9)
for b in D["bolts_new"]:
    if b["truss"] == "SOUTHGATE-TRUSS-T05" and abs(b["xyz"][1] - 0.30) < 0.04:
        ax.plot([b["xyz"][0] - 0.03, b["xyz"][0] + 0.015], [b["xyz"][2]] * 2, color="#111", lw=2)
finish(ax, "Section at y = 0.30: end post 2L70 + heel gusset vs column top, cap plate and seat fin (grey)", (25.2, 25.78), (11.9, 12.7), xlabel="x (m)")
ax.title.set_fontsize(8.5)
save(fig, "V08_truss_to_column_interface.png")
print("done")
