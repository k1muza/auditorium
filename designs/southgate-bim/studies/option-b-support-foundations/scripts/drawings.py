"""Deliverable G - preliminary structural concept drawings (PNG + combined PDF sheet set).
NOT FOR CONSTRUCTION. Reads calcs/selection.json (chosen sections per scheme) and the IFC extracts."""
from __future__ import annotations
import json, math, os, sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Polygon, Circle, FancyBboxPatch
from matplotlib.backends.backend_pdf import PdfPages
sys.path.insert(0, os.path.dirname(__file__))
import model_b as MB

ROOT = os.path.abspath(os.path.dirname(__file__) + "/..")
OUT = ROOT + "/drawings"
os.makedirs(OUT, exist_ok=True)
INK, INK2, MUTED, GRID, SURF = "#0b0b0b", "#52514e", "#8a8984", "#d6d5ce", "#fcfcfb"
C1, C2, C3, RED = "#2a78d6", "#eb6834", "#1baf7a", "#e34948"
SCH_COL = {"S1": C1, "S2": C2, "S3": C3}
plt.rcParams.update({"font.family": "Segoe UI", "font.size": 8, "axes.edgecolor": GRID, "axes.labelcolor": INK2,
                     "xtick.color": INK2, "ytick.color": INK2, "figure.facecolor": "white", "savefig.facecolor": "white"})
SEL = json.load(open(ROOT + "/calcs/selection.json")) if os.path.exists(ROOT + "/calcs/selection.json") else {}
EXT = json.load(open(ROOT + "/data/ifc_structural_extract.json"))
OPN = json.load(open(ROOT + "/data/ifc_openings_trusses.json"))


def title_block(fig, num, title, scale="NTS", note="PRELIMINARY CONCEPT - NOT FOR CONSTRUCTION"):
    fig.text(0.012, 0.012, f"SOUTHGATE WORSHIP CENTER | Option B support-structure study | {num} | {title} | {scale}", fontsize=7, color=INK2)
    fig.text(0.988, 0.012, note, fontsize=7, color=RED, ha="right", weight="bold")


def grids(ax, y0=-2.5, y1=35.5, label=True):
    for i, x in enumerate(MB.XL):
        ax.plot([x, x], [y0, y1], color=GRID, lw=0.6, ls=(0, (6, 3)), zorder=0)
        if label:
            ax.add_patch(Circle((x, y1 + 0.9), 0.75, fc="white", ec=INK2, lw=0.6))
            ax.text(x, y1 + 0.9, str(i), ha="center", va="center", fontsize=7, color=INK2)
    for y, t in ((MB.YC[0], "A"), (MB.YC[1], "B")):
        ax.plot([-1.5, 61], [y, y], color=GRID, lw=0.6, ls=(0, (6, 3)), zorder=0)
        if label:
            ax.add_patch(Circle((-2.6, y), 0.75, fc="white", ec=INK2, lw=0.6))
            ax.text(-2.6, y, t, ha="center", va="center", fontsize=7, color=INK2)


def outline(ax):
    ax.add_patch(Rectangle((3.1, 0.0), 55.9, 33.0, fill=False, ec=MUTED, lw=1.0))


def fig_existing():
    fig, ax = plt.subplots(figsize=(11.7, 7.4))
    grids(ax)
    outline(ax)
    foot = [r for r in EXT["rows"] if r["cls"] == "IfcFooting"]
    for f in foot:
        b = f["bbox"]
        if b[0] > 2.3:
            ax.add_patch(Rectangle((b[0], b[1]), b[3] - b[0], b[4] - b[1], fc="#eeeeea", ec=MUTED, lw=0.5, zorder=1))
    for r in EXT["rows"]:
        if r["cls"] != "IfcColumn" or not r["bbox"]:
            continue
        b = r["bbox"]
        cx, cy = (b[0] + b[3]) / 2, (b[1] + b[4]) / 2
        if cx < 2.5 or cx > 59.5:
            continue
        src = r["src"] or ""
        has = any(f["bbox"][0] - .01 <= cx <= f["bbox"][3] + .01 and f["bbox"][1] - .01 <= cy <= f["bbox"][4] + .01 for f in foot)
        if "COL-ROOF" in src:
            ax.add_patch(Rectangle((cx - 0.25, cy - 0.25), 0.5, 0.5, fc=INK if has else RED, ec="white", lw=0.6, zorder=4))
        elif "COL-GALLERY" in src:
            ax.add_patch(Rectangle((cx - 0.2, cy - 0.2), 0.4, 0.4, fc=MUTED if has else RED, ec="white", lw=0.5, zorder=4))
    for r in EXT["rows"]:
        if r["cls"] == "IfcWall" and (r["src"] or "").startswith("CORE") and r["bbox"]:
            b = r["bbox"]
            ax.add_patch(Rectangle((b[0], b[1]), b[3] - b[0], b[4] - b[1], fc="#b9b8b1", ec="none", zorder=2))
        if r["cls"] == "IfcMember" and "BRACE-ROOF" in (r["src"] or ""):
            b = r["bbox"]
            ax.plot([b[0], b[3]], [b[1], b[4]], color=C2, lw=1.0, zorder=3)
            ax.plot([b[0], b[3]], [b[4], b[1]], color=C2, lw=1.0, zorder=3)
    ax.text(30, 16.5, "AUDITORIUM\n(clear span 32.4 m, 11 Option B trusses @ 5.56 m)", ha="center", va="center", color=MUTED, fontsize=9)
    ax.text(55.6, 5, "S core", ha="center", fontsize=7, color=INK2)
    ax.text(55.6, 28, "N core", ha="center", fontsize=7, color=INK2)
    ax.text(44.5, 16.5, "gallery\nx 36.6-52.5", ha="center", fontsize=7, color=INK2)
    ax.plot([39.3, 39.3], [0.3, 32.7], color=MUTED, lw=0.8, ls=":")
    ax.text(0.2, 16.5, "office wing\n(single storey,\n+4.42)", ha="center", va="center", fontsize=7, color=INK2)
    leg = [("UC254x254x73 roof column on concept pad (CONCEPT_UNVERIFIED)", INK), ("column with NO footing modelled", RED),
           ("gallery column", MUTED), ("existing roof rods 20 mm (end bays only)", C2), ("concept pad 1.5x1.5x0.65 m", "#eeeeea")]
    for j, (t, c) in enumerate(leg):
        ax.add_patch(Rectangle((3.2 + j * 11.6, -4.6), 0.8, 0.8, fc=c, ec=MUTED, lw=0.4))
        ax.text(4.3 + j * 11.6, -4.2, t, fontsize=6.5, va="center", color=INK2)
    ax.set_xlim(-4, 62)
    ax.set_ylim(-5.5, 37.5)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title("S-01  Existing structural model: roof columns, footings and bracing (IFC, read-only)", loc="left", fontsize=10, color=INK)
    title_block(fig, "S-01", "Existing framing and foundation audit")
    fig.savefig(OUT + "/S-01_existing_framing_audit.png", dpi=180, bbox_inches="tight")
    return fig


def roof_plan(ax, sch, col):
    grids(ax)
    outline(ax)
    br = sch in ("S1", "S3")
    for i, x in enumerate(MB.XL):
        ax.plot([x, x], [MB.Y0, MB.Y0 + MB.SPAN], color=INK, lw=1.3, zorder=3)
        for y in MB.YC:
            ax.add_patch(Rectangle((x - 0.3, y - 0.3), 0.6, 0.6, fc=col, ec="white", lw=0.5, zorder=5))
    for y in (MB.Y0, MB.Y0 + MB.SPAN):
        ax.plot([MB.XL[0], MB.XL[-1]], [y, y], color=INK2, lw=1.4, zorder=3)
    for k in (2, 4, 6, 8, 10):
        ax.plot([MB.XL[0], MB.XL[-1]], [MB.Y0 + k * MB.PANEL] * 2, color=MUTED, lw=0.6, ls="--", zorder=2)
    if br:
        for y in (MB.Y0 + 5.4, MB.Y0 + MB.SPAN - 5.4):
            ax.plot([MB.XL[0], MB.XL[-1]], [y, y], color=col, lw=1.4, zorder=3)
        for i in range(1, 9):
            for ya, yb in ((MB.Y0, MB.Y0 + 5.4), (MB.Y0 + MB.SPAN, MB.Y0 + MB.SPAN - 5.4)):
                a, b = (ya, yb) if i % 2 == 0 else (yb, ya)
                ax.plot([MB.XL[i], MB.XL[i + 1]], [a, b], color=col, lw=1.1, zorder=3)
    for i in (0, 9):
        for k in range(12):
            a, b = (k, k + 1) if k % 2 == 0 else (k + 1, k)
            ax.plot([MB.XL[i], MB.XL[i + 1]], [MB.Y0 + a * MB.PANEL, MB.Y0 + b * MB.PANEL], color=INK2, lw=0.9, zorder=3)
    for i in (0, 10):
        for k in MB.POST_K:
            ax.add_patch(Rectangle((MB.XL[i] + MB.POST_DX[i] - 0.22, MB.Y0 + k * MB.PANEL - 0.12), 0.44, 0.24, fc=INK2, ec="white", lw=0.4, zorder=5))
    for bay in MB.WALL_BRACED_BAYS:
        for y in MB.YC:
            ax.add_patch(Rectangle((MB.XL[bay], y - 0.55), 5.56, 1.1, fc="none", ec=INK, lw=1.0, hatch="xxxx", zorder=4))
    if br:
        for i, pairs in MB.GABLE_BRACE.items():
            for ka, kb in pairs:
                x = MB.XL[i] + MB.POST_DX[i] * 3
                ax.add_patch(Rectangle((x - 0.45, MB.Y0 + ka * MB.PANEL), 0.9, (kb - ka) * MB.PANEL, fc="none", ec=col, lw=1.0, hatch="xxxx", zorder=4))
    ax.set_xlim(-4, 62)
    ax.set_ylim(-5.5, 37.5)
    ax.set_aspect("equal")
    ax.axis("off")


def fig_roof_plans():
    figs = []
    for sch, ttl in (("S1", "S1 braced: pinned bases, eaves wind girders, gable bracing"),
                     ("S2", "S2 moment frames: fixed bases + truss heel knee at every line"),
                     ("S3", "S3 hybrid: fixed-base propped columns, eaves wind girders, gable bracing")):
        fig, ax = plt.subplots(figsize=(11.7, 7.4))
        roof_plan(ax, sch, SCH_COL[sch])
        s = SEL.get(sch, {})
        txt = (f"Columns: {s.get('column', '-')}  |  eaves girders: {s.get('EGD', '-') if sch != 'S2' else 'none'}  |  "
               f"end-bay girders: {s.get('RBD', '-')}  |  gable posts: {s.get('POST', '-')}  |  BC ties: {s.get('BCT', '-')} at 5.4 m")
        ax.text(3.1, -2.2, txt, fontsize=7, color=INK2)
        legend = [("Option B truss (11 No.)", INK), ("eaves strut / girder chord", INK2), ("bottom-chord ties (dashed)", MUTED),
                  ("wall / gable vertical bracing bay (hatched)", INK)] + ([("eaves wind girder (5.4 m deep)", SCH_COL[sch])] if sch != "S2" else [])
        for j, (t, c) in enumerate(legend):
            ax.plot([3.2 + j * 11.4, 4.4 + j * 11.4], [-4.4, -4.4], color=c, lw=1.6, ls="--" if "dashed" in t else "-")
            ax.text(4.7 + j * 11.4, -4.4, t, fontsize=6.5, va="center", color=INK2)
        n = {"S1": "S-02", "S2": "S-03", "S3": "S-04"}[sch]
        ax.set_title(f"{n}  Roof-plane framing and stability plan - {ttl}", loc="left", fontsize=10, color=INK)
        title_block(fig, n, f"Roof framing {sch}")
        fig.savefig(OUT + f"/{n}_roof_framing_{sch}.png", dpi=180, bbox_inches="tight")
        figs.append(fig)
    return figs


def fig_elevations():
    fig, axs = plt.subplots(2, 1, figsize=(11.7, 8.0), gridspec_kw=dict(height_ratios=[1, 1.05]))
    ax = axs[0]
    # south side-wall elevation (inside face looking south)
    ax.add_patch(Rectangle((3.1, MB.FFL), 55.9, MB.WALL_TOP - MB.FFL, fc="#f3f2ee", ec=MUTED, lw=0.6))
    for o in OPN["openings"]:
        b = o["bbox"]
        if b and b[4] < 0.6 and b[0] > 3:
            ax.add_patch(Rectangle((b[0], b[2]), b[3] - b[0], b[5] - b[2], fc="white", ec=INK2, lw=0.5))
    for i, x in enumerate(MB.XL):
        ax.add_patch(Rectangle((x - 0.16, MB.Z_BASE), 0.32, MB.Z_COLTOP - MB.Z_BASE, fc=INK, ec="none"))
        ax.text(x, -2.3, str(i), ha="center", fontsize=7, color=INK2)
    for bay in MB.WALL_BRACED_BAYS:
        xa, xb = MB.XL[bay], MB.XL[bay + 1]
        ax.plot([xa, xb], [MB.Z_BASE, MB.SILL], color=C2, lw=1.4)
        ax.plot([xb, xa], [MB.Z_BASE, MB.SILL], color=C2, lw=1.4)
        ax.plot([xa, xb], [MB.SILL, MB.SILL], color=C2, lw=1.4)
        ax.plot([xa, xa + MB.PIER], [MB.Z_COLTOP, MB.SILL], color=C2, lw=1.4)
        ax.plot([xb, xb - MB.PIER], [MB.Z_COLTOP, MB.SILL], color=C2, lw=1.4)
    ax.plot([3.1, 59], [MB.Z_COLTOP, MB.Z_COLTOP], color=INK2, lw=1.2)
    ax.plot([0, 62], [0.10, 0.10], color=MUTED, lw=0.8)
    ax.text(3.2, 13.2, "South side wall (north mirror): 300 mm masonry infill between columns, clerestory windows +10.10 to +11.80, doors at bays 0, 4, 7, 9.\n"
            "Longitudinal bracing in bays 1 and 5 only: X below the clerestory sill (+9.90) with knee braces inside the 1.08 m window piers.", fontsize=7, color=INK2)
    ax.set_xlim(0, 62)
    ax.set_ylim(-3, 15)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title("S-05a  Side-wall elevation: column grid, openings and longitudinal bracing (all schemes)", loc="left", fontsize=10, color=INK)
    ax = axs[1]
    # west and east gable elevations side by side (y horizontal)
    for off, i, lab in ((0, 0, "West gable (behind stage), line 0"), (36, 10, "East gable (stair cores), line 10")):
        ys = [off + MB.Y0 + k * MB.PANEL for k in range(13)]
        top = [MB.z_top(k * MB.PANEL) for k in range(13)]
        ax.add_patch(Polygon([(off + 0, MB.FFL), (off + 33, MB.FFL), (off + 33, 12.5)] + [(y, t + 0.12) for y, t in zip(ys[::-1], top[::-1])] + [(off, 12.5)],
                             fc="#f3f2ee", ec=MUTED, lw=0.6))
        ax.plot(ys, top, color=INK, lw=1.2)
        ax.plot([ys[0], ys[-1]], [MB.Z_BC, MB.Z_BC], color=INK, lw=1.0)
        for y in (off + MB.YC[0], off + MB.YC[1]):
            ax.add_patch(Rectangle((y - 0.16, MB.Z_BASE), 0.32, MB.Z_COLTOP - MB.Z_BASE, fc=INK, ec="none"))
        for k in MB.POST_K:
            y = off + MB.Y0 + k * MB.PANEL
            ax.add_patch(Rectangle((y - 0.2, MB.Z_BASE), 0.4, MB.z_top(k * MB.PANEL) - MB.Z_BASE, fc=INK2, ec="none"))
        for ka, kb in MB.GABLE_BRACE[i]:
            ya, yb = off + MB.Y0 + ka * MB.PANEL, off + MB.Y0 + kb * MB.PANEL
            za, zb = MB.z_top(ka * MB.PANEL), MB.z_top(kb * MB.PANEL)
            for p, q in (((ya, MB.Z_BASE), (yb, 6.1)), ((yb, MB.Z_BASE), (ya, 6.1)), ((ya, 6.1), (yb, zb)), ((yb, 6.1), (ya, za)), ((ya, 6.1), (yb, 6.1))):
                ax.plot([p[0], q[0]], [p[1], q[1]], color=C1, lw=1.2)
        for o in OPN["openings"]:
            b = o["bbox"]
            if not b:
                continue
            if i == 0 and 2.9 < b[0] < 3.6 and b[3] < 3.6:
                ax.add_patch(Rectangle((off + b[1], b[2]), b[4] - b[1], b[5] - b[2], fc="white", ec=INK2, lw=0.5))
            if i == 10 and b[0] > 58.5 and b[3] < 59.2:
                ax.add_patch(Rectangle((off + b[1], b[2]), b[4] - b[1], b[5] - b[2], fc="white", ec=INK2, lw=0.5))
        ax.text(off + 0.2, 18.0, lab, fontsize=8, color=INK)
    ax.text(0.2, -2.6, "Gable wind posts (6 No. per gable at 5.4 m, clear of doors and the east glazed slot) span base to top chord. "
            "Blue: transverse gable bracing for S1/S3 (two-tier X). S2 needs posts but no gable bracing.", fontsize=7, color=INK2)
    ax.set_xlim(-1, 70)
    ax.set_ylim(-3.5, 19)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title("S-05b  Gable elevations: wind posts and transverse bracing", loc="left", fontsize=10, color=INK)
    title_block(fig, "S-05", "Wall and gable bracing elevations")
    fig.savefig(OUT + "/S-05_wall_and_gable_elevations.png", dpi=180, bbox_inches="tight")
    return fig


def fig_base_details():
    fig, axs = plt.subplots(1, 2, figsize=(11.7, 6.2))
    for ax, (ttl, key) in zip(axs, (("Pinned base (S1)", "S1"), ("Fixed base (S3 recommended)", "S3"))):
        s = SEL.get(key, {})
        bc = s.get("base", {})
        pad = s.get("pad", {})
        B, D = pad.get("B", 2.0), pad.get("D", 0.6)
        # elevation section through pad
        ax.add_patch(Rectangle((-B / 2, -0.8 - D), B, D, fc="#e6e5df", ec=INK2, lw=0.8))
        ax.add_patch(Rectangle((-B / 2 - 0.1, -0.85 - D), B + 0.2, 0.05, fc="#cfcec7", ec="none"))
        ax.add_patch(Rectangle((-0.3, -0.8), 0.6, 1.065, fc="#efeee9", ec=MUTED, lw=0.6, ls="--"))
        d = 0.32 if key == "S1" else 0.33
        ax.add_patch(Rectangle((-d / 2, -0.78), d, 2.4, fc=INK, ec="none"))
        pw = 0.47 if key == "S1" else 0.63
        ax.add_patch(Rectangle((-pw / 2, -0.80), pw, 0.03, fc=C1 if key == "S1" else C3, ec="none"))
        ax.add_patch(Rectangle((-pw / 2, -0.84), pw, 0.04, fc="#bdbcb5", ec="none"))
        hef = bc.get("hef", 300) / 1000
        xs = (-0.08, 0.08) if key == "S1" else (-0.24, 0.24)
        for xb in xs:
            ax.plot([xb, xb], [-0.70, -0.80 - hef], color=C2, lw=1.6)
            ax.add_patch(Rectangle((xb - 0.04, -0.82 - hef), 0.08, 0.02, fc=C2, ec="none"))
        if key != "S1":
            for xb in xs:
                ax.plot([xb - 0.05, xb - 0.05, xb + 0.05, xb + 0.05], [-0.85, -0.80 - min(hef + 0.05, D - 0.1), -0.80 - min(hef + 0.05, D - 0.1), -0.85], color=RED, lw=0.8)
            ax.plot([-0.17, -0.31], [-0.77, -0.45], color=C3, lw=1.2)
            ax.plot([0.17, 0.31], [-0.77, -0.45], color=C3, lw=1.2)
        for yy in (-0.8 - D + 0.08, -0.86):
            ax.plot([-B / 2 + 0.08, B / 2 - 0.08], [yy, yy], color=RED, lw=0.9, ls=(0, (1, 1.5)))
        ax.plot([-B / 2 - 0.5, B / 2 + 0.5], [0.10, 0.10], color=MUTED, lw=0.8)
        ax.plot([-B / 2 - 0.5, -0.3], [0.265, 0.265], color=MUTED, lw=1.5)
        ax.text(-B / 2 - 0.45, 0.32, "FFL +0.265", fontsize=6.5, color=INK2)
        ax.text(B / 2 + 0.05, 0.14, "FGL ~+0.10 (assumed)", fontsize=6.5, color=INK2)
        notes = [f"Column {s.get('column', '-')}", f"Base plate {bc.get('plate_mm', '-')} mm S355 on 40-50 mm non-shrink grout",
                 f"Holding-down: {bc.get('bolts', '-')}", f"Pad {pad.get('B', 0):.1f} x {pad.get('L', 0):.1f} x {pad.get('D', 0):.2f} m C25/30, G2 soil, F2 arrangement",
                 f"Bottom steel ~{pad.get('As_bot', 0):.0f} mm2/m each way; top ~{pad.get('As_top', 0):.0f} mm2/m",
                 "Column encased in C25/30 from pad to slab (corrosion protection below FFL)"]
        if key != "S1":
            notes += ["Anchor (supplementary) reinforcement: hairpins around tension bolts", "Stiffened base: 4 gussets (concept)"]
        for j, t in enumerate(notes):
            ax.text(-B / 2 - 0.4, -0.95 - D - 0.25 - j * 0.17, t, fontsize=6.8, color=INK2)
        ax.set_xlim(-B / 2 - 0.6, B / 2 + 0.9)
        ax.set_ylim(-0.95 - D - 1.7, 1.75)
        ax.set_aspect("equal")
        ax.axis("off")
        ax.set_title(ttl, loc="left", fontsize=10, color=INK)
    fig.suptitle("S-06  Column base and pad concept sections (indicative; anchorage and reinforcement to be designed)", x=0.01, ha="left", fontsize=10, color=INK)
    title_block(fig, "S-06", "Base connection and pad concepts")
    fig.savefig(OUT + "/S-06_base_and_pad_concepts.png", dpi=180, bbox_inches="tight")
    return fig


def fig_foundation_plan():
    fig, ax = plt.subplots(figsize=(11.7, 7.4))
    grids(ax)
    s = SEL.get("S3", {})
    bases = s.get("bases", [])
    # wall strip (F2)
    for y0 in (0.0 - 0.2, 33.0 - 0.5):
        ax.add_patch(Rectangle((3.1, y0), 55.9, 0.7, fc="#e6e5df", ec=MUTED, lw=0.5))
    for x0 in (3.1, 58.3):
        ax.add_patch(Rectangle((x0, 0), 0.7, 33, fc="#e6e5df", ec=MUTED, lw=0.5))
    for b in bases:
        p = b["pad"]
        x, y = b["x"], b["y"]
        if b["kind"] == "column":
            L, B = p["L"], p["B"]
        else:
            L, B = p["B"], p["L"]
        ax.add_patch(Rectangle((x - L / 2, y - B / 2), L, B, fc="#cfe0f5" if b["kind"] == "column" else "#d9efe5", ec=INK2, lw=0.6, zorder=3))
        ax.add_patch(Rectangle((x - 0.17, y - 0.17), 0.34, 0.34, fc=INK, ec="none", zorder=4))
        if b["kind"] == "column" and b["line"] in (0, 1, 5, 8, 10):
            ax.text(x, y + (B / 2 + 0.5) * (1 if y < 16 else -1), f"{p['B']:.1f}x{p['L']:.1f}x{p['D']:.2f}", ha="center", va="center", fontsize=6, color=INK2, zorder=5)
    ax.text(3.1, -2.8, "F2 arrangement, G2 soil (150 kPa assumed): column pads cast integral with a reinforced continuous strip under the masonry walls; "
            "gable post pads green. Sizes indicative only - no site investigation.", fontsize=7, color=INK2)
    ax.set_xlim(-4, 62)
    ax.set_ylim(-3.5, 37.5)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title("S-07  Foundation concept plan - recommended S3 hybrid (indicative)", loc="left", fontsize=10, color=INK)
    title_block(fig, "S-07", "Foundation concept plan")
    fig.savefig(OUT + "/S-07_foundation_concept_plan.png", dpi=180, bbox_inches="tight")
    return fig


def fig_load_path():
    fig, ax = plt.subplots(figsize=(11.7, 5.0))
    boxes = [("Roof cladding, purlins,\nservices, rigging", 0.3), ("Option B trusses\n(11 No., fixed)", 2.15), ("Bearings / knee\n(truss-to-column)", 4.0),
             ("Side columns\n(22 No.)", 5.85), ("Base plates +\nholding-down bolts", 7.7), ("Pads + wall strip\n(F2)", 9.55), ("Ground\n(G1-G3, no SI)", 11.4)]
    for t, x in boxes:
        ax.add_patch(FancyBboxPatch((x, 2.3), 1.6, 1.1, boxstyle="round,pad=0.02,rounding_size=0.08", fc="#eef4fc", ec=C1, lw=0.8))
        ax.text(x + 0.8, 2.85, t, ha="center", va="center", fontsize=7.5, color=INK)
    for (t, x), (_, x2) in zip(boxes[:-1], boxes[1:]):
        ax.annotate("", xy=(x2, 2.85), xytext=(x + 1.6, 2.85), arrowprops=dict(arrowstyle="-|>", color=INK2, lw=0.9))
    lat = [("Wall wind on 300 mm\nmasonry -> columns", 4.0), ("Eaves wind girders\n(S1/S3) or frames (S2)", 5.85), ("Gable bracing / posts\n-> base", 7.7)]
    for t, x in lat:
        ax.add_patch(FancyBboxPatch((x, 0.5), 1.6, 1.0, boxstyle="round,pad=0.02,rounding_size=0.08", fc="#eaf6f1", ec=C3, lw=0.8))
        ax.text(x + 0.8, 1.0, t, ha="center", va="center", fontsize=7, color=INK)
    ax.annotate("", xy=(6.65, 2.3), xytext=(6.65, 1.5), arrowprops=dict(arrowstyle="-|>", color=C3, lw=0.9))
    ax.annotate("", xy=(5.85, 1.0), xytext=(5.6, 1.0), arrowprops=dict(arrowstyle="-|>", color=C3, lw=0.9))
    ax.annotate("", xy=(7.7, 1.0), xytext=(7.45, 1.0), arrowprops=dict(arrowstyle="-|>", color=C3, lw=0.9))
    ax.annotate("", xy=(9.55, 1.0), xytext=(9.3, 1.0), arrowprops=dict(arrowstyle="-|>", color=C3, lw=0.9))
    ax.add_patch(FancyBboxPatch((9.55, 0.5), 1.6, 1.0, boxstyle="round,pad=0.02,rounding_size=0.08", fc="#eaf6f1", ec=C3, lw=0.8))
    ax.text(10.35, 1.0, "Base shear, moment,\nuplift to pads", ha="center", va="center", fontsize=7, color=INK)
    ax.add_patch(FancyBboxPatch((0.3, 0.5), 3.4, 1.0, boxstyle="round,pad=0.02,rounding_size=0.08", fc="#fdf0e9", ec=C2, lw=0.8))
    ax.text(2.0, 1.0, "Longitudinal: gable posts -> end-bay roof girders ->\neaves struts -> wall bracing bays 1 & 5 -> pads", ha="center", va="center", fontsize=7, color=INK)
    ax.text(0.3, 3.75, "Gravity (blue) and lateral (green / orange) load paths, Option B roof to ground", fontsize=8, color=INK2)
    ax.set_xlim(0, 13.2)
    ax.set_ylim(0.2, 4.0)
    ax.axis("off")
    ax.set_title("S-08  Structural load path", loc="left", fontsize=10, color=INK)
    title_block(fig, "S-08", "Load path diagram")
    fig.savefig(OUT + "/S-08_load_path.png", dpi=180, bbox_inches="tight")
    return fig


if __name__ == "__main__":
    figs = [fig_existing()] + fig_roof_plans() + [fig_elevations(), fig_base_details(), fig_foundation_plan(), fig_load_path()]
    with PdfPages(OUT + "/G_structural_concept_drawings.pdf") as pdf:
        for f in figs:
            pdf.savefig(f)
    print("drawings written", len(figs))
