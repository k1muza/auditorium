"""Report charts (static PNG for the PDF). Palette: validated categorical slots 1-3 (S1 blue, S2 orange, S3 aqua)."""
import json, os, sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
import sections as S

ROOT = os.path.abspath(os.path.dirname(__file__) + "/..")
OUT = ROOT + "/report/img"
os.makedirs(OUT, exist_ok=True)
INK, INK2, MUTED, GRID = "#0b0b0b", "#52514e", "#8a8984", "#e4e3dc"
COL = {"S1": "#2a78d6", "S2": "#eb6834", "S3": "#1baf7a"}
NAME = {"S1": "S1 braced", "S2": "S2 moment frames", "S3": "S3 hybrid"}
plt.rcParams.update({"font.family": "Segoe UI", "font.size": 8.5, "axes.edgecolor": GRID, "axes.labelcolor": INK2, "xtick.color": INK2,
                     "ytick.color": INK2, "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True, "grid.color": GRID,
                     "grid.linewidth": 0.6, "axes.axisbelow": True, "legend.frameon": False})
CAT = {s.name: s for s in S.COLUMNS}
sw = json.load(open(ROOT + "/calcs/sweep_base.json"))["results"]
sel = json.load(open(ROOT + "/calcs/selection.json"))
mc = json.load(open(ROOT + "/calcs/montecarlo.json"))
ev = [e for e in json.load(open(ROOT + "/calcs/eval_base.json")) if e.get("ok")]


def save(fig, name):
    fig.savefig(f"{OUT}/{name}.png", dpi=200, bbox_inches="tight")
    plt.close(fig)


# 1 column sweep: column mass vs SLS deflection, pass/fail -------------------------------------------
fig, ax = plt.subplots(figsize=(7.2, 3.9))
for sch in ("S1", "S2", "S3"):
    R = [r for r in sw if r["scheme"] == sch]
    for r in R:
        kg = CAT[r["column"]].kg
        dft = r["drift"]["SLS_W"]["col_y_mm"]
        robust = r.get("util_unrestrained", 9) <= 1.0
        ok = r["ok"]
        ax.scatter(kg, dft, s=42 if ok else 30, marker="o" if ok and robust else ("D" if ok else "x"),
                   color=COL[sch], edgecolors="white" if ok else None, lw=0.8, zorder=3)
        if r["column"] == sel[sch]["column"]:
            off = {"S1": (8, -14), "S2": (-96, 6), "S3": (10, 5)}[sch]
            ax.annotate(f"{sch}: {r['column']}", (kg, dft), xytext=off, textcoords="offset points", fontsize=7, color=INK)
    ax.plot([], [], "o", color=COL[sch], label=NAME[sch])
ax.axhline(12.23 / 300 * 1000, color=INK2, lw=1, ls="--")
ax.text(56, 12.23 / 300 * 1000 + 0.8, "masonry limit h/300 = 40.8 mm (h = 12.23 m)", fontsize=7, color=INK2, ha="left")
ax.plot([], [], "o", color=MUTED, label="passes; adequate with no masonry restraint")
ax.plot([], [], "D", color=MUTED, label="passes only if masonry restrains the minor axis")
ax.plot([], [], "x", color=MUTED, label="fails strength or deflection")
ax.set_xlabel("Column mass (kg/m)")
ax.set_ylabel("Max. transverse column deflection, SLS 0.85 kPa (mm)")
ax.legend(fontsize=7, loc="upper right", ncol=1)
ax.set_title("Column candidates by stability system (each re-sized for bracing, girders and posts)", loc="left", fontsize=9, color=INK)
save(fig, "c01_column_sweep")

# 2 stacked cost by component, selected designs ----------------------------------------------------------
groups = [("Side columns", ["steel_supply_columns"]), ("Gable posts", ["steel_supply_posts"]), ("Girders + bracing steel", ["steel_supply_girders", "steel_supply_bracing"]),
          ("Connections + fixings", ["connection_plates", "bolts_structural", "holding_down_bolts", "grout", "shear_keys", "anchor_reinforcement"]),
          ("Fabrication + coating + transport", ["fabrication", "corrosion_protection", "transport"]),
          ("Erection, cranes, temporary works", ["erection_labour", "cranes_access", "temporary_works"]),
          ("Column/post foundations", ["column_foundations"]), ("Wall foundations", ["wall_foundations"]),
          ("QA, O&P, contingency", ["qa_testing", "overhead_profit_labour_plant", "contingency"])]
shades = ["#1f3b57", "#2e5f8a", "#4b84b8", "#7aa6d1", "#a9c7e6", "#c9b48a", "#8f7a55", "#b8ab92", "#d9d6cc"]
fig, ax = plt.subplots(figsize=(7.2, 3.6))
schs = ["S1", "S2", "S3"]
groups.insert(8, ("Pier enlargement (deep columns)", ["architectural_adjustment"]))
shades.insert(8, "#e8e2d4")
left = np.zeros(3)
for (lab, keys), c in zip(groups, shades):
    v = np.array([sum(sel[s]["cost"][k] for k in keys) / 1000 for s in schs])
    ax.barh(range(3), v, left=left, color=c, edgecolor="white", lw=1.2, height=0.56, label=lab)
    left += v
for i, s in enumerate(schs):
    ax.text(left[i] + 3, i, f"USD {left[i]:.0f}k", va="center", fontsize=8, color=INK)
ax.set_yticks(range(3), [f"{NAME[s]}\n{sel[s]['column']}" for s in schs])
ax.invert_yaxis()
ax.set_xlim(0, 420)
ax.set_xlabel("Installed cost of the supporting system, USD thousands (G2 soil, F2 foundations, central rates)")
ax.grid(axis="y", visible=False)
ax.legend(fontsize=6.8, ncol=3, loc="upper center", bbox_to_anchor=(0.5, -0.22))
ax.set_title("Supporting-system cost by component (Option B trusses excluded - common to all)", loc="left", fontsize=9, color=INK)
save(fig, "c02_cost_stack")

# 3 soil x arrangement matrix -------------------------------------------------------------------------------
fig, axs = plt.subplots(1, 3, figsize=(7.2, 2.7), sharey=True)
for ax, soil in zip(axs, ("G1", "G2", "G3")):
    for j, arr in enumerate(("F1", "F2", "F3")):
        for i, s in enumerate(schs):
            v = sel[s]["by_soil"][soil][arr] / 1000
            ax.scatter(j + (i - 1) * 0.18, v, s=34, color=COL[s], edgecolor="white", lw=0.6, zorder=3)
    ax.set_xticks(range(3), ["F1 pads", "F2 pads +\nwall strip", "F3 pads +\nground beams"], fontsize=7)
    ax.set_title({"G1": "G1 favourable 200 kPa", "G2": "G2 moderate 150 kPa", "G3": "G3 poor 100 kPa, wet"}[soil], fontsize=8, color=INK)
axs[0].set_ylabel("Total, USD thousands")
for s in schs:
    axs[0].scatter([], [], color=COL[s], label=NAME[s])
axs[0].legend(fontsize=7, loc="upper left")
fig.suptitle("Total supporting-system cost by soil scenario and foundation arrangement", x=0.01, y=1.05, ha="left", fontsize=9, color=INK)
save(fig, "c03_soil_arrangement")

# 4 Monte Carlo ranges ---------------------------------------------------------------------------------------
fig, ax = plt.subplots(figsize=(7.2, 1.9))
for i, s in enumerate(schs):
    v = mc[s]
    ax.plot([v["p10"] / 1000, v["p90"] / 1000], [i, i], color=COL[s], lw=6, solid_capstyle="round", alpha=0.55)
    ax.scatter(v["p50"] / 1000, i, color=COL[s], s=50, edgecolor="white", zorder=3)
    ax.text(v["p90"] / 1000 + 2, i, f"P10 {v['p10']/1000:.0f}  P50 {v['p50']/1000:.0f}  P90 {v['p90']/1000:.0f}  | cheapest in {v['cheapest_share']*100:.0f}%",
            va="center", fontsize=7, color=INK2)
ax.set_yticks(range(3), [NAME[s] for s in schs])
ax.invert_yaxis()
ax.set_xlim(300, 460)
ax.set_xlabel("USD thousands (1,500 trials: correlated rate groups + independent quantity uncertainty)")
ax.grid(axis="y", visible=False)
ax.set_title("Cost uncertainty (G2/F2)", loc="left", fontsize=9, color=INK)
save(fig, "c04_montecarlo")

# 5 quantities small multiples ------------------------------------------------------------------------------
qs = [("Supporting steel (t)", lambda s: sel[s]["steel_t"]["total"]), ("Foundation concrete (m3)", lambda s: sel[s]["found_q"]["concrete_m3"] + sel[s]["wall_q"]["concrete_m3"]),
      ("Reinforcement (t)", lambda s: (sel[s]["found_q"]["rebar_kg"] + sel[s]["wall_q"]["rebar_kg"] + sel[s]["hd"]["anchor_reinf_kg"]) / 1000),
      ("Excavation (m3)", lambda s: sel[s]["found_q"]["excavation_m3"] + sel[s]["wall_q"]["excavation_m3"])]
fig, axs = plt.subplots(1, 4, figsize=(7.2, 2.2))
for ax, (lab, fn) in zip(axs, qs):
    v = [fn(s) for s in schs]
    ax.bar(range(3), v, color=[COL[s] for s in schs], width=0.6, edgecolor="white")
    for i, x in enumerate(v):
        ax.text(i, x, f"{x:.0f}" if x > 20 else f"{x:.1f}", ha="center", va="bottom", fontsize=7, color=INK)
    ax.set_xticks(range(3), schs)
    ax.set_title(lab, fontsize=8, color=INK)
    ax.set_ylim(0, max(v) * 1.2)
    ax.grid(axis="x", visible=False)
fig.suptitle("Principal quantities (G2 soil, F2 arrangement)", x=0.01, y=1.06, ha="left", fontsize=9, color=INK)
save(fig, "c05_quantities")

# 6 base reactions S3 ----------------------------------------------------------------------------------------
b = [x for x in sel["S3"]["bases"] if x["kind"] == "column" and x["side"] == 0]
fig, ax = plt.subplots(figsize=(7.2, 2.6))
x = np.array([q["line"] for q in b])
ax.bar(x - 0.2, [q["env"]["Nc"] for q in b], width=0.38, color="#2a78d6", label="max compression (ULS)")
ax.bar(x + 0.2, [-q["env"]["Nt"] for q in b], width=0.38, color="#e34948", label="max uplift (ULS)")
for q in b:
    ax.text(q["line"], q["env"]["Nc"] + 8, f"M {q['env']['M']:.0f}", ha="center", fontsize=6.5, color=INK2)
ax.axhline(0, color=INK2, lw=0.8)
ax.set_xticks(range(11), [f"{i}" + (" br" if i in (1, 2, 5, 6) else "") for i in range(11)])
ax.set_xlabel("Grid line, side A (br = wall-bracing bay column).  M = base moment kNm (ULS)")
ax.set_ylabel("kN")
ax.legend(fontsize=7, loc="upper center", ncol=2, bbox_to_anchor=(0.5, -0.25))
ax.grid(axis="x", visible=False)
ax.set_title("S3 column base reactions: braced-bay columns govern uplift", loc="left", fontsize=9, color=INK)
save(fig, "c06_base_reactions")

# 7 sensitivity summary (if available) --------------------------------------------------------------------
cases = [("base", "Base case"), ("qsls12", "SLS wind at 1.20 kPa"), ("cpi055", "Dominant opening cpi +0.55"),
         ("cpin108", "Dominant opening in suction zone, cpi -1.08 (factored 1.3)"), ("q085", "ULS wind 0.85 kPa only"), ("future", "Future rigging/equipment"),
         ("fixG2", "Base fixity: rotational spring 50 MNm/rad (G2)"), ("fixG3", "Base fixity: rotational spring 20 MNm/rad (G3)"), ("light", "Lightweight cladding, h/150")]
rows = []
for tag, lab in cases:
    p = f"{ROOT}/calcs/sweep_{tag}.json"
    if not os.path.exists(p):
        continue
    R = json.load(open(p))["results"]
    row = [lab]
    for s in schs:
        r = next((r for r in R if r["scheme"] == s and r["column"] == sel[s]["column"]), None)
        if r is None and tag == "light":
            ok = [x for x in R if x["scheme"] == s and x["ok"]]
            r = min(ok, key=lambda x: x["col_util"]) if ok else None
        if r is None and tag in ("fixG2", "fixG3") and s == "S1":
            r = next((r for r in json.load(open(f"{ROOT}/calcs/sweep_base.json"))["results"] if r["scheme"] == s and r["column"] == sel[s]["column"]), None)
        row.append(None if r is None else (r["ok"], r["col_util"], r["drift"]["SLS_W"]["col_y_mm"], r["drift"]["SLS_W"]["eaves_x_mm"],
                                           r["column"] == sel[s]["column"], r["column"]))
    rows.append(row)
json.dump(rows, open(ROOT + "/calcs/sensitivity_table.json", "w"))
print("charts written; sensitivity rows", len(rows))
