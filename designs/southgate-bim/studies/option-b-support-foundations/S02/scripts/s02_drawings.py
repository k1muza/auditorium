"""S02 structural concept drawings (PNG, 200 dpi) for the recommended arrangement: S3 hybrid, L2 wall bracing, F2.
S-101 roof framing plan | S-102 column, bracing and foundation layout | S-103 side-wall elevations | S-104 gable
elevations | S-105 typical cross-section and load paths | S-106 foundation sections and fixed-base detail |
S-107 architectural coordination plan. Geometry from the study model (verified against the IFC in S01)."""
import json, math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import s02cfg as C
import model_b as MB
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from matplotlib.patches import Rectangle, Polygon, FancyBboxPatch

FONTS = r"C:/Users/Kelvin/Desktop/auditorium/designs/C-site-A-2000/reports/source/fonts"
for f in os.listdir(FONTS):
    if f.endswith(".ttf"):
        fm.fontManager.addfont(os.path.join(FONTS, f))
plt.rcParams.update({"font.family": "Barlow Semi Condensed", "font.size": 7.5, "axes.linewidth": 0.4})
INK, INK2, MUTED, RULE, ACC, ACC2, SLATE, SLATE2, PAPER, GOOD = ("#1f1d1a", "#3b3834", "#6f6961", "#d6ccbc", "#8c4a32", "#c47b52",
                                                                "#2d5a6b", "#dfe7e8", "#fbf8f2", "#4a6b3a")
OUT = C.S02 + "/drawings"
os.makedirs(OUT, exist_ok=True)
REC = next(r for r in json.load(open(C.S02 + "/calcs/sweep_DB_L2_S3.json"))["results"] if r["column"] == "UC 305x305x97")
COST = json.load(open(C.S02 + "/calcs/cost_S3DB_L2.json"))["DB_L2_S3|S3|UC 305x305x97"]["prices"]["G2|F2|central"]
SEC = REC["sections"]
XL, YC = MB.XL, MB.YC
GRID = {i: str(i + 1) for i in range(11)}
BRACED = (1, 5)
BRACE_POSTS = {0: ((3, 5), (7, 9)), 10: ((1, 3), (9, 11))}
PANEL = MB.PANEL


def sheet(w, h, num, title, scale_note):
    fig = plt.figure(figsize=(w, h), dpi=200)
    fig.patch.set_facecolor(PAPER)
    ax = fig.add_axes([0.035, 0.12, 0.93, 0.84])
    ax.set_facecolor(PAPER)
    ax.set_aspect("equal")
    ax.axis("off")
    tb = fig.add_axes([0.035, 0.015, 0.93, 0.075])
    tb.axis("off")
    tb.set_xlim(0, 100)
    tb.set_ylim(0, 10)
    tb.add_patch(Rectangle((0, 0), 100, 10, fill=False, lw=0.6, ec=INK))
    for xv in (14, 70, 84):
        tb.plot([xv, xv], [0, 10], lw=0.4, c=INK)
    tb.text(1, 6.2, num, fontsize=11, weight=600, color=ACC)
    tb.text(1, 2.0, "Revision S02  7 Nov 2026", fontsize=6, color=MUTED)
    tb.text(15, 6.0, title, fontsize=9.5, weight=500, color=INK)
    tb.text(15, 2.0, "Southgate Worship Center  |  Option B roof - primary steel support structure, stability and foundations", fontsize=6, color=MUTED)
    tb.text(71, 6.0, scale_note, fontsize=6.5, color=INK2)
    tb.text(71, 2.0, "Dimensions m, levels m (FFL +0.27)", fontsize=6, color=MUTED)
    tb.text(85, 6.0, "PRELIMINARY - NOT FOR CONSTRUCTION", fontsize=6, weight=600, color=ACC)
    tb.text(85, 2.0, "Concept sizes, to be verified by the appointed engineer", fontsize=5.6, color=MUTED)
    return fig, ax


def grid_bubbles(ax, xs=True, y0=-2.2, y1=35.2, ys=True, x0=0.0, horizontal=True):
    if xs:
        for i, x in enumerate(XL):
            ax.plot([x, x], [y0 + 0.9, y1 - 0.9], lw=0.3, c=MUTED, ls=(0, (6, 2, 1, 2)), zorder=0)
            for yy in (y0, y1):
                ax.add_patch(plt.Circle((x, yy), 0.75, fc=PAPER, ec=INK, lw=0.5, zorder=5))
                ax.text(x, yy, GRID[i], ha="center", va="center", fontsize=6.5, weight=600, zorder=6)
    if ys:
        for lab, y in (("A", YC[0]), ("B", YC[1])):
            ax.plot([x0 + 0.9, 62.0], [y, y], lw=0.3, c=MUTED, ls=(0, (6, 2, 1, 2)), zorder=0)
            ax.add_patch(plt.Circle((x0, y), 0.75, fc=PAPER, ec=INK, lw=0.5, zorder=5))
            ax.text(x0, y, lab, ha="center", va="center", fontsize=6.5, weight=600, zorder=6)


def legend(ax, items, x, y, dy=1.25, title=None):
    if title:
        ax.text(x, y + dy, title, fontsize=6.5, weight=600, color=ACC)
    for k, (lab, kw) in enumerate(items):
        yy = y - k * dy
        if kw.get("kind") == "patch":
            ax.add_patch(Rectangle((x, yy - 0.35), 1.6, 0.7, fc=kw.get("fc", "none"), ec=kw.get("ec", INK), lw=0.5, hatch=kw.get("hatch")))
        elif kw.get("kind") == "dot":
            ax.plot([x + 0.8], [yy], marker=kw.get("m", "s"), ms=kw.get("ms", 3), c=kw.get("c", INK))
        else:
            ax.plot([x, x + 1.6], [yy, yy], c=kw.get("c", INK), lw=kw.get("lw", 0.8), ls=kw.get("ls", "-"))
        ax.text(x + 2.1, yy, lab, va="center", fontsize=6.2, color=INK2)


def zig(ax, x1, x2, ya, yb, **kw):
    ax.plot([x1, x2], [ya, yb], **kw)


# ---------------------------------------------------------------- S-101 roof framing plan
def s101():
    fig, ax = sheet(11.7, 8.3, "S-101", "Roof framing plan - recommended arrangement S3 (hybrid)", "Scale 1:250 at A3 (indicative)")
    ax.set_xlim(-6, 90)
    ax.set_ylim(-4, 37)
    grid_bubbles(ax, x0=-1.5)
    Y0, Y1 = 0.30, 32.70
    # purlins
    for k in range(1, 12):
        if k in (2, 10):
            continue
        y = Y0 + k * PANEL
        ax.plot([XL[0], XL[-1]], [y, y], lw=0.25, c=MUTED)
    # trusses
    for i, x in enumerate(XL):
        ax.plot([x, x], [Y0, Y1], lw=1.6, c=INK, solid_capstyle="butt")
        for k in range(13):
            ax.plot([x - 0.25, x + 0.25], [Y0 + k * PANEL] * 2, lw=0.4, c=INK)
    # eaves struts and girder chords
    for y in (Y0, Y1):
        ax.plot([XL[0], XL[-1]], [y, y], lw=1.1, c=ACC)
    for k in (2, 10):
        y = Y0 + k * PANEL
        ax.plot([XL[0], XL[-1]], [y, y], lw=1.1, c=ACC)
    # eaves girder diagonals (Warren) bays 1..8
    for i in range(1, 9):
        for ka, kb in ((0, 2), (12, 10)):
            ya, yb = Y0 + ka * PANEL, Y0 + kb * PANEL
            a, b = (ya, yb) if i % 2 == 0 else (yb, ya)
            ax.plot([XL[i], XL[i + 1]], [a, b], lw=0.9, c=ACC)
    # end-bay roof girders
    for i in (0, 9):
        for k in range(12):
            ya, yb = Y0 + k * PANEL, Y0 + (k + 1) * PANEL
            a, b = (ya, yb) if k % 2 == 0 else (yb, ya)
            ax.plot([XL[i], XL[i + 1]], [a, b], lw=0.8, c=SLATE)
    # bottom-chord ties
    for i in range(10):
        for k in (2, 4, 6, 8, 10):
            y = Y0 + k * PANEL + 0.35
            ax.plot([XL[i], XL[i + 1]], [y, y], lw=0.6, c=GOOD, ls=(0, (3, 2)))
    # columns and posts
    for i, x in enumerate(XL):
        for y in YC:
            ax.add_patch(Rectangle((x - 0.32, y - 0.32), 0.64, 0.64, fc=INK, ec=INK))
    for i in (0, 10):
        for k in MB.POST_K:
            ax.add_patch(Rectangle((XL[i] + MB.POST_DX[i] - 0.28, Y0 + k * PANEL - 0.2), 0.56, 0.4, fc=ACC, ec=ACC))
    # labels
    ax.text(-4.6, 30.2, "N", fontsize=9, weight=600)
    ax.annotate("", xy=(-4.2, 34.4), xytext=(-4.2, 31.6), arrowprops=dict(arrowstyle="-|>", lw=0.6, color=INK))
    tx = 64.5
    legend(ax, [(f"Option B truss (fixed), 11 No. @ 5.56 m", dict(c=INK, lw=1.6)),
                (f"Eaves wind girder chords {SEC['EGC']} / eaves strut {SEC['EAV']}", dict(c=ACC, lw=1.1)),
                (f"Eaves girder diagonals {SEC['EGD']}", dict(c=ACC, lw=0.9)),
                (f"End-bay roof girder diagonals {SEC['RBD']}", dict(c=SLATE, lw=0.8)),
                (f"Bottom-chord ties {SEC['BCT']} at panel points 2-10", dict(c=GOOD, lw=0.6, ls=(0, (3, 2)))),
                ("C200 purlins (Option B, not relied on as girder chords)", dict(c=MUTED, lw=0.3)),
                (f"Side columns {SEC['COL']}, fixed base (semi-rigid)", dict(kind="dot", m="s", c=INK)),
                (f"Gable wind posts {SEC['POST']}", dict(kind="dot", m="s", c=ACC))], tx, 30, dy=1.6, title="LEGEND")
    notes = ["NOTES", "1  Eaves girders: 5.4 m deep (2 panels) in the top-chord plane, both eaves,",
             "    spanning between the end-bay girders; columns propped at the eaves.",
             "2  End-bay roof girders deliver gable wind to the gable bracing",
             "    and wall bracing; cross-frames in end bays at panel points 2-10.",
             "3  Purlin cleats are not designed as girder chords.",
             "4  Gable trusses (lines 1, 11): heel cleat restrains the bottom",
             "    chord out of plane (Option B interface item, see report 12).",
             "5  Truss bearings: preloaded bolts; bearing to be made concentric",
             "    with the column axis (145 mm eccentricity as modelled)."]
    for j, t in enumerate(notes):
        ax.text(tx, 15.5 - j * 1.25, t, fontsize=6.0 if j else 6.5, color=ACC if not j else INK2, weight=600 if not j else 400)
    ax.text(XL[0] - 4.2, 16.5, "WEST GABLE\n(stage)", rotation=90, ha="center", va="center", fontsize=6.5, color=MUTED)
    ax.text(XL[-1] + 2.4, 16.5, "EAST GABLE\n(entrance)", rotation=90, ha="center", va="center", fontsize=6.5, color=MUTED)
    fig.savefig(OUT + "/S-101_roof_framing_plan.png", facecolor=PAPER)
    plt.close(fig)


# ---------------------------------------------------------------- S-102 column, bracing and foundation layout
def pad_types(bases):
    types = {}
    for b in bases:
        p = b["pad"]
        key = (b["kind"], round(p["B"], 1), round(p["L"], 1), round(p["D"], 2))
        types.setdefault(key, []).append(b)
    names = {}
    for n, key in enumerate(sorted(types, key=lambda k: (k[0] != "column", -k[1] * k[2])), 1):
        names[key] = f"P{n}"
    return types, names


def s102():
    fig, ax = sheet(11.7, 8.3, "S-102", "Column, bracing and foundation layout - S3 on F2 (pads integral with reinforced wall strip)", "Scale 1:250 at A3 (indicative)")
    ax.set_xlim(-6, 80)
    ax.set_ylim(-5, 38)
    grid_bubbles(ax, y0=-3.4, y1=36.4, x0=-1.8)
    bases = COST["bases"]
    types, names = pad_types(bases)
    # wall strips
    for y in YC:
        ax.add_patch(Rectangle((MB.X_W, y - 0.3), MB.X_E - MB.X_W, 0.6, fc=SLATE2, ec=SLATE, lw=0.4, zorder=1))
    for x in (MB.X_W, MB.X_E):
        ax.add_patch(Rectangle((x - 0.3, 0.0), 0.6, 33.0, fc=SLATE2, ec=SLATE, lw=0.4, zorder=1))
    for b in bases:
        p = b["pad"]
        if b["kind"] == "column":
            w, h = p["L"], p["B"]
        else:
            w, h = p["L"], p["B"]
            w, h = h, w
        key = (b["kind"], round(p["B"], 1), round(p["L"], 1), round(p["D"], 2))
        ax.add_patch(Rectangle((b["x"] - w / 2, b["y"] - h / 2), w, h, fc="#e9eef0", ec=SLATE, lw=0.7, zorder=2))
        off = -h / 2 - 0.7 if b["y"] < 16 else h / 2 + 0.7
        if b["kind"] == "post":
            off = 0
            ax.text(b["x"] + (-w / 2 - 0.4 if b["x"] < 30 else w / 2 + 0.4), b["y"], names[key], fontsize=5.8, color=SLATE, weight=600,
                    ha="right" if b["x"] < 30 else "left", va="center", zorder=6)
        else:
            ax.text(b["x"], b["y"] + off, names[key], fontsize=5.8, color=SLATE, weight=600, ha="center", va="center", zorder=6)
    for i, x in enumerate(XL):
        for y in YC:
            ax.add_patch(Rectangle((x - 0.32, y - 0.32), 0.64, 0.64, fc=INK, ec=INK, zorder=4))
    for i in (0, 10):
        for k in MB.POST_K:
            ax.add_patch(Rectangle((XL[i] + MB.POST_DX[i] - 0.28, MB.Y0 + k * PANEL - 0.2), 0.56, 0.4, fc=ACC, ec=ACC, zorder=4))
    # wall bracing in plan
    for bay in BRACED:
        for y in YC:
            ax.plot([XL[bay], XL[bay + 1]], [y, y], lw=2.6, c=ACC, solid_capstyle="butt", zorder=3)
            ax.text((XL[bay] + XL[bay + 1]) / 2, y + (-1.5 if y < 16 else 1.5), "X-braced bay\n(full height)", ha="center", va="center", fontsize=5.5, color=ACC)
    for i in (0, 10):
        for ka, kb in BRACE_POSTS[i]:
            ya, yb = MB.Y0 + ka * PANEL, MB.Y0 + kb * PANEL
            xx = XL[i] + MB.POST_DX[i]
            ax.plot([xx, xx], [ya, yb], lw=2.6, c=ACC, solid_capstyle="butt", zorder=3)
    # loggia transfer beam
    ax.plot([XL[7], XL[9]], [YC[1] + 0.05] * 2, lw=3.2, c=GOOD, solid_capstyle="butt", zorder=5)
    ax.text((XL[7] + XL[9]) / 2, YC[1] + 2.0, "Loggia transfer beams +4.00\n2 No. UB 457x191x82 + 300x15 soffit plate", ha="center", fontsize=5.6, color=GOOD)
    ax.add_patch(Rectangle((43.0, 30.0), 9.5, 3.0, fill=False, ec=GOOD, lw=0.4, ls=(0, (2, 2))))
    # pad schedule
    tx, ty = 64.0, 33.0
    ax.text(tx, ty, "PAD SCHEDULE (concept, G2 ground, S02)", fontsize=6.5, weight=600, color=ACC)
    ty -= 1.4
    ax.text(tx, ty, "Type   B x L x D (m)        No.   use", fontsize=5.8, color=MUTED)
    for key, nm in sorted(names.items(), key=lambda kv: int(kv[1][1:])):
        ty -= 1.15
        lst = types[key]
        use = lst[0]["kind"]
        tag = "post" if use == "post" else "column"
        ax.text(tx, ty, f"{nm:<5} {key[1]:.1f} x {key[2]:.1f} x {key[3]:.2f}    {len(lst):>3}   {tag}", fontsize=5.8, color=INK2, family="Barlow Semi Condensed")
    ty -= 1.8
    for t in ["Wall strip: 600 x 450, 3Y16 T&B (long walls);", "600 x 600, 4Y20 T&B on both gables", "(850 wide, 600 deep with 4Y20 T&B on all", "walls in wet ground G3 / G3L).",
              "Pads cast integral with the strip; strip bars", "lapped through pads.", "Founding: >= 1.2 m (G2), >= 1.5 m (G3/G3L)", "below finished ground."]:
        ax.text(tx, ty, t, fontsize=5.8, color=INK2)
        ty -= 1.05
    legend(ax, [("Column (UC 305x305x97)", dict(kind="dot", c=INK)), ("Gable wind post (UB 533x210x82)", dict(kind="dot", c=ACC)),
                ("Pad (to scale)", dict(kind="patch", fc="#e9eef0", ec=SLATE)), ("Reinforced wall strip", dict(kind="patch", fc=SLATE2, ec=SLATE)),
                ("Vertical bracing line", dict(c=ACC, lw=2.6)), ("Loggia transfer beam", dict(c=GOOD, lw=3.2))], tx, 6.0, dy=1.25)
    fig.savefig(OUT + "/S-102_column_bracing_foundation_layout.png", facecolor=PAPER)
    plt.close(fig)


# ---------------------------------------------------------------- S-103 side-wall elevations
def wall_elev(ax, y0, side, title):
    """Elevation of a long wall, drawn with base at y0 (vertical offset), x along the building."""
    z = lambda v: y0 + v
    ax.add_patch(Rectangle((MB.X_W, z(MB.FFL)), MB.X_E - MB.X_W, MB.WALL_TOP - MB.FFL, fc="#f1ebe1", ec=MUTED, lw=0.4))
    ax.plot([MB.X_W - 2, MB.X_E + 2], [z(0.10)] * 2, c=INK2, lw=0.6)
    ax.text(MB.X_W - 2.4, z(0.10), "FGL +0.10", ha="right", va="center", fontsize=5.4, color=MUTED)
    for lev, lab in ((MB.WALL_TOP, "wall head +12.50"), (MB.SILL, "sill +9.90"), (6.0, "+6.00"), (MB.FFL, "FFL +0.27")):
        ax.plot([MB.X_E + 0.4, MB.X_E + 1.2], [z(lev)] * 2, c=MUTED, lw=0.4)
        ax.text(MB.X_E + 1.4, z(lev), lab, va="center", fontsize=5.4, color=MUTED)
    # clerestory windows bays 0..6
    for b in range(7):
        x0 = XL[b] + 1.08
        crossed = b in BRACED
        ax.add_patch(Rectangle((x0, z(10.1)), 3.4, 1.7, fc="#dfe7e8" if not crossed else "#f3e6da", ec=SLATE if not crossed else ACC, lw=0.5,
                               hatch="////" if crossed else None))
    # doors / loggia
    for a, bnd, h in C.EV_OPEN[side]:
        if h > 5:
            ax.add_patch(Rectangle((a, z(MB.FFL)), bnd - a, 4.0 - MB.FFL, fc=PAPER, ec=GOOD, lw=0.6))
            ax.text(45.3, z(1.6), "NORTH\nLOGGIA\nopening\nto +4.00", ha="center", fontsize=5.2, color=GOOD)
            ax.add_patch(Rectangle((XL[7], z(4.0)), XL[9] - XL[7], 0.46, fc=GOOD, ec=GOOD))
            ax.text(XL[7] + 0.3, z(5.3), "transfer beams UB 457x191x82 + plate (2 spans)", fontsize=5.4, color=GOOD, bbox=dict(fc="#f1ebe1", ec="none", pad=0.6))
        else:
            ax.add_patch(Rectangle((a, z(MB.FFL)), bnd - a, h, fc=PAPER, ec=INK2, lw=0.5))
    # columns
    for x in XL:
        ax.add_patch(Rectangle((x - 0.15, z(MB.Z_BASE)), 0.30, MB.Z_COLTOP - MB.Z_BASE, fc=INK, ec=INK, lw=0.2))
    # eaves strut
    ax.plot([XL[0], XL[-1]], [z(12.28)] * 2, c=ACC, lw=1.2)
    # bracing (L2) two tiers
    for bay in BRACED:
        xa, xb = XL[bay], XL[bay + 1]
        for (z1, z2) in ((MB.Z_BASE + 0.8, 6.0), (6.0, 12.28)):
            ax.plot([xa, xb], [z(z1), z(z2)], c=ACC, lw=1.1)
            ax.plot([xb, xa], [z(z1), z(z2)], c=ACC, lw=1.1)
        ax.plot([xa, xb], [z(6.0)] * 2, c=ACC, lw=0.8)
        ax.add_patch(plt.Circle(((xa + xb) / 2, z(3.0 + 0.1)), 0.35, fc=ACC, ec=ACC))
        ax.add_patch(plt.Circle(((xa + xb) / 2, z(9.14)), 0.35, fc=ACC, ec=ACC))
    # foundations
    for b in COST["bases"]:
        if b["kind"] == "column" and b["side"] == side:
            p = b["pad"]
            ax.add_patch(Rectangle((b["x"] - p["L"] / 2, z(MB.Z_BASE - p["D"])), p["L"], p["D"], fc="#e9eef0", ec=SLATE, lw=0.5))
    ax.add_patch(Rectangle((MB.X_W, z(-1.25)), MB.X_E - MB.X_W, 0.45, fc=SLATE2, ec=SLATE, lw=0.3, zorder=0))
    for i, x in enumerate(XL):
        ax.add_patch(plt.Circle((x, z(14.0)), 0.65, fc=PAPER, ec=INK, lw=0.5))
        ax.text(x, z(14.0), GRID[i], ha="center", va="center", fontsize=6, weight=600)
    ax.text(MB.X_W, z(15.4), title, fontsize=8, weight=600, color=INK)


def s103():
    C.EV_OPEN = __import__("evaluate").OPEN_LONG
    fig, ax = sheet(11.7, 8.3, "S-103", "Side-wall elevations (from inside) - wall bracing, clerestory and loggia interfaces", "Scale 1:250 at A3 (indicative)")
    ax.set_xlim(-2, 84)
    ax.set_ylim(-3, 38)
    wall_elev(ax, 21.0, 1, "NORTH WALL - GRID B")
    wall_elev(ax, 0.5, 0, "SOUTH WALL - GRID A")
    tx = 66.5
    notes = ["NOTES", "1  Full-height two-tier X-bracing (CHS 168.3x5) in bays 2-3", "    and 6-7, node at +6.00, both walls.",
             "2  The braces cross the clerestory windows in those four", "    bays (hatched). Architect to choose: omit the windows", "    (masonry) or keep them with the brace seen behind.",
             "3  Alternative L1 (no change to the clerestory): X below", "    +9.90 with knee braces in bays 2-3, 4-5 and 6-7.",
             "    About USD 10k dearer; less stiff (report section 8).", "4  Masonry panels span horizontally to the columns on", "    flexible ties; movement joints at every column.",
             "5  Column 8 (grid B) stands free in the loggia opening."]
    for j, t in enumerate(notes):
        ax.text(tx, 31 - j * 1.35, t, fontsize=5.7 if j else 6.5, color=ACC if not j else INK2, weight=600 if not j else 400)
    fig.savefig(OUT + "/S-103_side_wall_elevations.png", facecolor=PAPER)
    plt.close(fig)


# ---------------------------------------------------------------- S-104 gable elevations
def gable(ax, x0, line, title):
    zt = lambda s: MB.z_top(s)
    pts = [(x0 + 0.0, MB.FFL), (x0 + 0.0, MB.WALL_TOP)] + [(x0 + s + 0.3, zt(s) + 0.15) for s in (0.0, 16.2, 32.4)] + [(x0 + 33.0, MB.WALL_TOP), (x0 + 33.0, MB.FFL)]
    ax.add_patch(Polygon(pts, closed=True, fc="#f1ebe1", ec=MUTED, lw=0.4))
    ax.plot([x0 - 1, x0 + 34], [0.10, 0.10], c=INK2, lw=0.6)
    if line == 0:
        ax.add_patch(Rectangle((x0 + 0.3, MB.FFL), 32.4, 1.0, fc="none", ec=MUTED, lw=0.4, hatch="....", ls=(0, (2, 2))))
        ax.text(x0 + 16.5, 1.7, "stage platform in front (x 3.1-5.7)", ha="center", fontsize=5.4, color=MUTED, bbox=dict(fc="#f1ebe1", ec="none", pad=0.5))
        ax.plot([x0, x0 + 33], [4.42, 4.42], c=MUTED, lw=0.6, ls=(0, (4, 2)))
        ax.text(x0 + 1.0, 4.9, "office annex roof +4.42 (beyond)", fontsize=5.2, color=MUTED, bbox=dict(fc="#f1ebe1", ec="none", pad=0.4))
        for a, b_ in ((5.0, 6.2), (26.8, 28.0)):
            ax.add_patch(Rectangle((x0 + a, MB.FFL), b_ - a, 2.4, fc=PAPER, ec=INK2, lw=0.5))
    else:
        ax.add_patch(Rectangle((x0 + 14.0, MB.FFL), 5.0, 12.0, fc="#dfe7e8", ec=SLATE, lw=0.5))
        ax.text(x0 + 16.5, 6.0, "glazed\nentrance\nslot", ha="center", va="center", fontsize=5.6, color=SLATE)
        for a, b_ in ((0.3, 9.8), (23.2, 32.7)):
            ax.add_patch(Rectangle((x0 + a, MB.FFL), b_ - a, 10.8 - MB.FFL, fc="none", ec=MUTED, lw=0.5, ls=(0, (4, 2))))
            ax.text(x0 + (a + b_) / 2, 10.2, "stair core (beyond)", ha="center", fontsize=5.2, color=MUTED)
        ax.plot([x0 + 0.3, x0 + 32.7], [7.25, 7.25], c=MUTED, lw=0.5, ls=(0, (1, 2)))
        ax.text(x0 + 0.5, 7.5, "gallery +7.25", fontsize=5.2, color=MUTED)
    # posts
    P = {}
    for k in MB.POST_K:
        s = k * PANEL
        yy = x0 + 0.3 + s
        top = zt(s)
        P[k] = (yy, top)
        ax.add_patch(Rectangle((yy - 0.22, MB.Z_BASE), 0.44, top - MB.Z_BASE, fc=ACC, ec=ACC))
    for cy in (x0 + 0.155, x0 + 32.845):
        ax.add_patch(Rectangle((cy - 0.15, MB.Z_BASE), 0.30, MB.Z_COLTOP - MB.Z_BASE, fc=INK, ec=INK))
    # truss outline (gable truss)
    ax.plot([x0 + 0.3, x0 + 16.5, x0 + 32.7], [zt(0), zt(16.2), zt(32.4)], c=INK, lw=1.1)
    ax.plot([x0 + 0.3, x0 + 32.7], [MB.Z_BC, MB.Z_BC], c=INK, lw=0.9)
    for k in range(13):
        ax.plot([x0 + 0.3 + k * PANEL] * 2, [MB.Z_BC, zt(k * PANEL)], c=INK, lw=0.35)
    # bracing panels (two-tier X, node at +6.10)
    for ka, kb in BRACE_POSTS[line]:
        (ya, ta), (yb, tb) = P[ka], P[kb]
        for z1, z2 in ((MB.Z_BASE + 0.8, 6.1), (6.1, min(ta, tb))):
            ax.plot([ya, yb], [z1, z2], c=ACC, lw=1.0)
            ax.plot([yb, ya], [z1, z2], c=ACC, lw=1.0)
        ax.plot([ya, yb], [6.1, 6.1], c=ACC, lw=0.7)
    # restraint struts
    for zz in (4.6, 8.8):
        ax.plot([x0 + 0.3, x0 + 32.7], [zz, zz], c=GOOD, lw=0.7, ls=(0, (5, 2)))
    for k in MB.POST_K:
        ax.text(P[k][0], -2.2, f"y {P[k][0] - x0:.1f}", ha="center", fontsize=5.0, color=MUTED, rotation=90)
    ax.text(x0, 18.3, title, fontsize=8, weight=600)


def s104():
    fig, ax = sheet(11.7, 8.3, "S-104", "Gable elevations (from inside) - wind posts, gable bracing and restraint struts", "Scale 1:200 at A3 (indicative)")
    ax.set_xlim(-2, 82)
    ax.set_ylim(-4, 20)
    gable(ax, 0.0, 0, "WEST GABLE - GRID 1 (behind the stage)")
    gable(ax, 38.0, 10, "EAST GABLE - GRID 11 (entrance)")
    notes = ["Posts UB 533x210x82 at y 3.0, 8.4, 13.8, 19.2, 24.6, 30.0 (panel points 1, 3 ... 11), heads tied to the gable truss.",
             "Two-tier X-bracing CHS 193.7x6.3 between post pairs: west behind the stage backdrop (y 8.4-13.8, 19.2-24.6); east inside the stair cores.",
             "Restraint struts CHS 88.9x3.2 at about +4.6 and +8.8 (dashed) restrain the post minor axis; do not rely on masonry ties for post stability.",
             "East posts at y 13.8 / 19.2 form the jambs of the glazed slot (0.2 m clear of the 14.0-19.0 opening): coordinate mullions and fixings.",
             "Optimisation (not adopted): prop the west posts at the office-annex roof +4.42 if that structure is verified to take the reaction."]
    for j, t in enumerate(notes):
        ax.text(0, -0.6 - 0.0 - j * 0.0, "", fontsize=1)
    for j, t in enumerate(notes):
        fig.text(0.04, 0.215 - j * 0.019, f"{j + 1}  {t}", fontsize=6.2, color=INK2)
    fig.savefig(OUT + "/S-104_gable_elevations.png", facecolor=PAPER)
    plt.close(fig)


# ---------------------------------------------------------------- S-105 cross-section and load paths
def s105():
    fig, ax = sheet(11.7, 8.3, "S-105", "Typical cross-section through frame line 5 - structure, levels and load paths", "Scale 1:150 at A3 (indicative)")
    ax.set_xlim(-8, 52)
    ax.set_ylim(-4, 19)
    zt = MB.z_top
    # ground and floor
    ax.add_patch(Rectangle((-6, -3.5), 45, 3.6, fc="#efe6d6", ec="none", zorder=0))
    ax.plot([-6, 39], [0.10, 0.10], c=INK2, lw=0.6)
    ax.plot([0.3, 32.7], [MB.FFL] * 2, c=INK2, lw=0.8)
    # walls
    for y in (0.0, 32.7):
        ax.add_patch(Rectangle((y, MB.FFL), 0.3, MB.WALL_TOP - MB.FFL, fc="#f1ebe1", ec=MUTED, lw=0.4))
        ax.add_patch(Rectangle((y, 10.1), 0.3, 1.7, fc="#dfe7e8", ec=SLATE, lw=0.4))
    # columns
    for y in YC:
        ax.add_patch(Rectangle((y - 0.155, MB.Z_BASE), 0.31, MB.Z_COLTOP - MB.Z_BASE, fc=INK, ec=INK))
    # truss
    ss = [k * PANEL for k in range(13)]
    ax.plot([0.3 + s for s in ss], [zt(s) for s in ss], c=INK, lw=1.3)
    ax.plot([0.3, 32.7], [MB.Z_BC] * 2, c=INK, lw=1.1)
    for k, s in enumerate(ss):
        ax.plot([0.3 + s] * 2, [MB.Z_BC, zt(s)], c=INK, lw=0.45)
    for k in range(12):
        left = k < 6
        j = k if left else k - 6
        up = j % 2 == 0
        a, b = (ss[k], ss[k + 1])
        z1, z2 = (MB.Z_BC, zt(b)) if up else (zt(a), MB.Z_BC)
        ax.plot([0.3 + a, 0.3 + b], [z1, z2], c=INK, lw=0.45)
    # girders (section through) and ties
    for k in (0, 2, 10, 12):
        ax.add_patch(plt.Circle((0.3 + k * PANEL, zt(k * PANEL) + 0.25), 0.22, fc=ACC, ec=ACC))
    for k in (2, 4, 6, 8, 10):
        ax.add_patch(plt.Circle((0.3 + k * PANEL, MB.Z_BC - 0.22), 0.15, fc=GOOD, ec=GOOD))
    # foundations
    for y in (0.155, 32.845):
        ax.add_patch(Rectangle((y - 1.55, MB.Z_BASE - 0.9), 3.1, 0.9, fc="#e9eef0", ec=SLATE, lw=0.6))
        ax.add_patch(Rectangle((y - 0.3, -0.80), 0.6, 0.9, fc="#d9d3c7", ec=MUTED, lw=0.4))
    # levels
    for lev, lab in ((zt(16.2), f"ridge TC +{zt(16.2):.2f}"), (MB.WALL_TOP, "wall head +12.50"), (12.38, "TC heel +12.38"), (MB.Z_BC, "BC +10.90"),
                     (MB.SILL, "sill +9.90"), (MB.FFL, "FFL +0.27"), (MB.Z_BASE, "top of pad -0.80"), (MB.Z_BASE - 0.9, "u/s pad -1.70 (G2)")):
        ax.plot([33.6, 34.4], [lev] * 2, c=MUTED, lw=0.4)
        ax.text(34.6, lev, lab, va="center", fontsize=5.6, color=MUTED)
    # load path arrows
    arr = dict(arrowstyle="-|>", lw=0.9, color=ACC)
    for y in (6, 11, 21, 26):
        ax.annotate("", xy=(y, zt(y - 0.3) + 0.1), xytext=(y, zt(y - 0.3) + 1.8), arrowprops=dict(arrowstyle="-|>", lw=0.8, color=SLATE))
    ax.text(16.5, zt(16.2) + 1.2, "gravity: sheeting > purlins > Option B truss > bearings > columns > pads", ha="center", fontsize=6, color=SLATE)
    for z_ in (2, 5, 8, 11):
        ax.annotate("", xy=(-0.1, z_), xytext=(-3.2, z_), arrowprops=arr)
    ax.text(-3.4, 12.6, "wind on wall", fontsize=6, color=ACC, ha="center")
    ax.text(-5.5, 7.0, "masonry spans\nhorizontally to\ncolumns (ties)", fontsize=5.6, color=INK2, ha="center")
    ax.annotate("eaves girder props the\ncolumn head (both eaves)", xy=(0.3, 12.6), xytext=(4.5, 14.8), fontsize=5.8, color=ACC,
                arrowprops=dict(arrowstyle="-", lw=0.5, color=ACC))
    ax.annotate("semi-rigid fixed base\n(about 25-60 MNm/rad)\nresists part of the moment", xy=(0.155, MB.Z_BASE), xytext=(5.5, -3.0), fontsize=5.8, color=ACC,
                arrowprops=dict(arrowstyle="-", lw=0.5, color=ACC))
    ax.annotate("BC ties restrain the bottom\nchord under wind uplift", xy=(0.3 + 4 * PANEL, MB.Z_BC - 0.22), xytext=(12, 7.6), fontsize=5.8, color=GOOD,
                arrowprops=dict(arrowstyle="-", lw=0.5, color=GOOD))
    ax.annotate("pad integral with the reinforced\nwall strip: uplift resisted by pad,\nsoil and mobilised wall weight", xy=(32.845, -1.2), xytext=(20, -3.2),
                fontsize=5.8, color=SLATE, arrowprops=dict(arrowstyle="-", lw=0.5, color=SLATE))
    ax.text(0.3, 17.8, "SECTION A-A  (looking east)", fontsize=8, weight=600)
    ax.text(40.5, 14.5, "Wind girder at eaves (in the roof plane)\nshown in section as dots; BC ties dots\nbelow the bottom chord.", fontsize=5.8, color=INK2)
    fig.savefig(OUT + "/S-105_cross_section_load_paths.png", facecolor=PAPER)
    plt.close(fig)


# ---------------------------------------------------------------- S-106 foundation sections and base detail
def s106():
    fig, ax = sheet(11.7, 8.3, "S-106", "Foundation sections and typical fixed column base (braced-bay column) - concept", "Scale 1:25 / 1:20 at A3 (indicative)")
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 52)
    gov = max((b for b in COST["bases"] if b["kind"] == "column"), key=lambda b: b["base"]["T_row"])
    p = gov["pad"]
    bc = gov["base"]
    # ---- section through pad + strip (across the wall), scale 10 units = 1 m
    S = 10.0
    ox, oy = 6, 18
    B, D = p["B"], p["D"]
    ax.add_patch(Rectangle((ox, oy), B * S, D * S, fc="#e9eef0", ec=SLATE, lw=0.8))
    cx = ox + B * S / 2
    # column, plate, grout
    ax.add_patch(Rectangle((cx - 1.54, oy + D * S + 0.5), 3.08, 20, fc=INK, ec=INK))
    ax.add_patch(Rectangle((cx - 3.04, oy + D * S + 0.5), 6.08, 0.3, fc=ACC, ec=ACC))
    ax.add_patch(Rectangle((cx - 3.04, oy + D * S), 6.08, 0.5, fc="#cfc6b8", ec=MUTED, lw=0.3))
    # encasement to FFL
    ax.add_patch(Rectangle((cx - 3.0, oy + D * S), 6.0, 10.7, fc="none", ec=MUTED, lw=0.5, ls=(0, (3, 2))))
    # bolts and anchor plates
    for dx in (-2.15, 2.15):
        ax.plot([cx + dx, cx + dx], [oy + D * S + 0.8, oy + D * S - 4.5], c=ACC, lw=1.0)
        ax.add_patch(Rectangle((cx + dx - 0.4, oy + D * S - 4.6), 0.8, 0.2, fc=ACC, ec=ACC))
    # hairpins
    for dx in (-2.6, -1.7, 1.7, 2.6):
        ax.plot([cx + dx, cx + dx, cx + dx * 1.9], [oy + D * S - 3.0, oy + 1.0, oy + 1.0], c=GOOD, lw=0.7)
    # bottom/top mats
    ax.plot([ox + 0.75, ox + B * S - 0.75], [oy + 0.9] * 2, c=INK2, lw=0.6)
    ax.plot([ox + 0.75, ox + B * S - 0.75], [oy + D * S - 0.9] * 2, c=INK2, lw=0.6)
    for xx in [ox + 0.9 + j * 1.5 for j in range(int((B * S - 1.8) / 1.5) + 1)]:
        ax.add_patch(plt.Circle((xx, oy + 1.15), 0.18, fc=INK2))
    # shear key
    ax.add_patch(Rectangle((cx - 2.0, oy - 4.0), 4.0, 4.0, fc="#e9eef0", ec=SLATE, lw=0.6))
    # ground
    ax.plot([ox - 4, ox + B * S + 4], [oy + D * S + 9.0] * 2, c=INK2, lw=0.6)
    ax.text(ox + B * S + 4.3, oy + D * S + 9.0, "FGL +0.10", va="center", fontsize=5.6, color=MUTED)
    ax.text(ox + B * S + 4.3, oy + D * S, "top of pad -0.80", va="center", fontsize=5.6, color=MUTED)
    ax.text(ox + B * S + 4.3, oy, f"u/s pad {-0.80 - D:.2f}", va="center", fontsize=5.6, color=MUTED)
    ax.text(ox, oy + D * S + 23.5, f"SECTION 1 - braced-bay column pad (G2): {B:.1f} x {p['L']:.1f} x {D:.2f} m", fontsize=7, weight=600)
    lab = [f"UC 305x305x97, base plate {bc['plate_mm']} S355 with 4 stiffeners", f"{bc['n_bolts']} No. M{bc['dia']} 8.8 cast-in bolts, hef {bc['hef']} mm, 80x80x15 anchor plates",
           f"Anchor reinforcement: U-bar hairpins (about {int(round(bc['T_row'] * 1000 / (0.87 * 450) / 201 + 0.49))} legs Y16) lapped into the bottom mat",
           "50 mm non-shrink grout; column encased to FFL (corrosion)", "Downstand shear key 400 x 400 (sliding on soil)", "Bottom mat Y16 @ 150 e.w.; top mat Y12 @ 150 e.w. (concept)"]
    for j, t in enumerate(lab):
        ax.text(ox, oy - 6.5 - j * 1.7, f"{j + 1}  {t}", fontsize=5.8, color=INK2)
    # ---- base plate plan (scale 1:10 -> 1 mm = 0.1 unit... use 0.04 units per mm)
    k = 0.04
    px, py = 66, 36
    pd, pb = [int(v) for v in bc["plate_mm"].split(" x ")[:2]]
    ax.add_patch(Rectangle((px - pd * k / 2, py - pb * k / 2), pd * k, pb * k, fc="#f3e6da", ec=ACC, lw=0.8))
    d, b = 307.9, 305.3
    tf, tw = 15.4, 9.9
    for sgn in (-1, 1):
        ax.add_patch(Rectangle((px + sgn * (d / 2 - tf / 2) * k - tf * k / 2, py - b * k / 2), tf * k, b * k, fc=INK, ec=INK))
    ax.add_patch(Rectangle((px - d * k / 2, py - tw * k / 2), d * k, tw * k, fc=INK, ec=INK))
    nside = bc["n_bolts"] // 2
    for sgn in (-1, 1):
        xb = px + sgn * (pd / 2 - 75) * k
        for j in range(nside):
            yb = py + (j - (nside - 1) / 2) * 150 * k * (0.62 if nside > 2 else 1)
            ax.add_patch(plt.Circle((xb, yb), 13 * k, fc=PAPER, ec=ACC, lw=0.8))
    for sgn in (-1, 1):
        ax.plot([px + sgn * d / 2 * k, px + sgn * (pd / 2) * k], [py] * 2, c=ACC, lw=0.8)
    ax.text(px - pd * k / 2, py + pb * k / 2 + 2.0, "PLAN - base plate (1:10)", fontsize=7, weight=600)
    ax.text(px - pd * k / 2, py - pb * k / 2 - 2.0, f"{pd} x {pb} plate, bolt rows outside the flanges,\nlever arm about {pd - 175} mm; tension row resists the base moment", fontsize=5.6, color=INK2, va="top")
    # ---- strip section
    sx, sy = 66, 6
    for j, (lab_, h, bars) in enumerate((("S01 strip 600 x 450\n3Y16 T&B (long walls, G1/G2)", 0.45, 3), ("S02 strip 600 x 600\n4Y20 T&B (gables; all walls G3/G3L)", 0.60, 4))):
        x0 = sx + j * 16
        ax.add_patch(Rectangle((x0, sy), 0.6 * S, h * S, fc=SLATE2, ec=SLATE, lw=0.7))
        ax.add_patch(Rectangle((x0 + 1.5, sy + h * S), 3.0, 4.0, fc="#f1ebe1", ec=MUTED, lw=0.4))
        for yy in (sy + 0.8, sy + h * S - 0.8):
            for i_ in range(bars):
                ax.add_patch(plt.Circle((x0 + 0.8 + i_ * (4.4 / (bars - 1)), yy), 0.22, fc=INK2))
        ax.add_patch(Rectangle((x0 + 0.55, sy + 0.55), 0.6 * S - 1.1, h * S - 1.1, fill=False, ec=INK2, lw=0.4))
        ax.text(x0, sy - 1.0, lab_, fontsize=5.6, color=INK2, va="top")
    ax.text(sx, sy + 12.5, "SECTION 2 - wall strip (1:25)", fontsize=7, weight=600)
    fig.savefig(OUT + "/S-106_foundation_sections_base_detail.png", facecolor=PAPER)
    plt.close(fig)


# ---------------------------------------------------------------- S-107 architectural coordination plan
def s107():
    fig, ax = sheet(11.7, 8.3, "S-107", "Architectural coordination - structure against the stage, gallery, cores, loggia, glazing and services", "Scale 1:250 at A3 (indicative)")
    ax.set_xlim(-8, 80)
    ax.set_ylim(-4, 37)
    grid_bubbles(ax, y0=-2.6, y1=35.6, x0=-6.0)
    ax.add_patch(Rectangle((-3.1, 0.0), 6.2, 33.0, fc="#efe8dc", ec=MUTED, lw=0.4))
    ax.text(0.0, 16.5, "OFFICE ANNEX\nroof +4.42", ha="center", va="center", fontsize=6, color=MUTED, rotation=90)
    ax.add_patch(Rectangle((3.1, 0.3), 2.6, 32.4, fc="#f3e6da", ec=ACC2, lw=0.4))
    ax.text(4.4, 16.5, "STAGE", ha="center", va="center", fontsize=6.5, color=ACC, rotation=90)
    ax.add_patch(Rectangle((39.3, 0.3), 13.2, 32.4, fc="none", ec=SLATE, lw=0.6, hatch="////", alpha=0.6))
    ax.text(45.9, 22.0, "GALLERY over\n(+4.2 to +7.25)", ha="center", fontsize=6, color=SLATE)
    for a, b in ((0.3, 9.8), (23.2, 32.7)):
        ax.add_patch(Rectangle((52.5, a), 6.2, b - a, fc="#e8e1d5", ec=MUTED, lw=0.5))
        ax.text(55.6, (a + b) / 2, "STAIR\nCORE", ha="center", va="center", fontsize=6, color=MUTED)
    ax.add_patch(Rectangle((58.85, 14.0), 0.3, 5.0, fc="#dfe7e8", ec=SLATE, lw=0.8))
    ax.text(60.0, 16.5, "glazed\nentrance slot", va="center", fontsize=5.8, color=SLATE)
    ax.add_patch(Rectangle((43.0, 30.0), 9.5, 3.0, fc="none", ec=GOOD, lw=0.6, ls=(0, (3, 2))))
    ax.text(47.7, 34.2, "NORTH LOGGIA", ha="center", fontsize=6, color=GOOD)
    # services zones (R2 positions): arrays lines 1-2, LX trusses, HVLS fans bays 3-6
    for s in (7.3, 25.1):
        ax.add_patch(plt.Circle((11.5, 0.3 + s), 0.6, fc="none", ec=ACC2, lw=0.8))
    ax.text(11.5, 0.3 + 16.2, "speaker arrays\n+ lighting trusses\n(lines 2-3)", ha="center", va="center", fontsize=5.4, color=ACC2)
    for i in range(3, 7):
        for s in (10.65, 21.75):
            ax.add_patch(plt.Circle(((XL[i] + XL[i + 1]) / 2, 0.3 + s), 1.2, fc="none", ec=SLATE, lw=0.5, ls=(0, (2, 1))))
    ax.text(30.0, 16.5, "HVLS fans (bays 4-7)", ha="center", fontsize=5.6, color=SLATE)
    for x in XL:
        for y in YC:
            ax.add_patch(Rectangle((x - 0.32, y - 0.32), 0.64, 0.64, fc=INK, ec=INK))
    for i in (0, 10):
        for k in MB.POST_K:
            ax.add_patch(Rectangle((XL[i] + MB.POST_DX[i] - 0.28, MB.Y0 + k * PANEL - 0.2), 0.56, 0.4, fc=ACC, ec=ACC))
        for ka, kb in BRACE_POSTS[i]:
            xx = XL[i] + MB.POST_DX[i]
            ax.plot([xx, xx], [MB.Y0 + ka * PANEL, MB.Y0 + kb * PANEL], lw=2.4, c=ACC)
    for bay in BRACED:
        for y in YC:
            ax.plot([XL[bay], XL[bay + 1]], [y, y], lw=2.4, c=ACC)
    ax.plot([XL[7], XL[9]], [YC[1]] * 2, lw=3.0, c=GOOD)
    tx = 64.5
    notes = ["COORDINATION FINDINGS", "A  West gable bracing (y 8.4-13.8, 19.2-24.6) sits in the stage", "    backdrop: enclose in the backdrop wall or accept it visible;",
             "    keep projection / LED zones clear or mount on the posts.", "B  East bracing panels are inside the stair cores: coordinate", "    with core walls, doors and handrails (cores not structural).",
             "C  East posts at y 13.8 / 19.2 frame the glazed slot.", "D  Wall bracing bays 2-3 and 6-7 cross 4 of the 14 clerestory", "    windows (and their vent sashes): architect decision.",
             "E  Eaves girders are in the top-chord plane at both eaves;", "    hung services, arrays and HVLS fans hang from bottom-chord", "    panel points and stay clear of the girder diagonals.",
             "F  BC ties at panel points 2-10 every bay: route catwalks,", "    cable trays and maintenance access between them.",
             "G  Column 8B stands free in the loggia; transfer beams over.", "H  Gallery columns and stair cores need their own foundations", "    (not part of this study; R14)."]
    for j, t in enumerate(notes):
        ax.text(tx, 33.5 - j * 1.32, t, fontsize=5.6 if j else 6.4, color=ACC if not j else INK2, weight=600 if not j else 400)
    fig.savefig(OUT + "/S-107_architectural_coordination.png", facecolor=PAPER)
    plt.close(fig)


if __name__ == "__main__":
    for f in (s101, s102, s103, s104, s105, s106, s107):
        f()
        print("drawn", f.__name__)
