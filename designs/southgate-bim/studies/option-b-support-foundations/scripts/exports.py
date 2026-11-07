"""Deliverables C, D, E, F: reaction and load schedules, steel/foundation comparisons, auditable cost workbook."""
import csv, json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
import evaluate as EV
import model_b as MB
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter

ROOT = EV.ROOT
OUT = ROOT + "/data"
base = json.load(open(ROOT + "/calcs/sweep_base.json"))["results"]
sel = json.load(open(ROOT + "/calcs/selection.json"))
mc = json.load(open(ROOT + "/calcs/montecarlo.json"))
recs = {s: next(r for r in base if r["scheme"] == s and r["column"] == sel[s]["column"]) for s in sel}
evs = {s: EV.evaluate(recs[s], "G2", "F2") for s in sel}
ROLE = {"COL": "side columns lines 1-9", "COLC": "gable-line columns 0/10", "POST": "gable wind posts", "EAV": "eaves struts",
        "EGC": "eaves girder inner chord", "EGD": "eaves girder diagonals", "RBD": "end-bay roof girder diagonals",
        "XF": "end-bay cross frames", "BCB": "end-bay bottom-chord bracing", "BCT": "bottom-chord ties", "GBX": "gable bracing diagonals",
        "GBS": "gable bracing struts", "PSTR": "gable-post restraint struts (2 rows per gable)", "WBX": "wall bracing diagonals", "WBK": "wall bracing knees", "WBS": "wall bracing sill strut"}


def wcsv(name, rows):
    with open(f"{OUT}/{name}", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


# C1 truss bearing reactions
rows = []
for s, r in recs.items():
    for b in r["bearings"]:
        if b["group"] != "BEARING":
            continue
        for q in ("0.85", "1.2"):
            uls = {c: F for c, F in b["F"].items() if c.startswith("U") and (f"q{q}" in c or "W" not in c)}
            rows.append(dict(scheme=s, line=b["line"], side="A (south)" if b["side"] == 0 else "B (north)", qp_kPa=q,
                             Rv_comp_ULS_kN=round(max(v[2] for v in uls.values()), 1), Rv_uplift_ULS_kN=round(min(v[2] for v in uls.values()), 1),
                             H_transverse_ULS_kN=round(max(abs(v[1]) for v in uls.values()), 1), H_longit_ULS_kN=round(max(abs(v[0]) for v in uls.values()), 1)))
wcsv("C1_truss_bearing_reactions.csv", rows)
# C2 base reactions and foundation schedule
rows = []
for s, e in evs.items():
    for b in e["bases"]:
        en = b["env"]
        rows.append(dict(scheme=s, column=sel[s]["column"], kind=b["kind"], line=b["line"], side={0: "A", 1: "B"}.get(b["side"], "-"), post_k=b.get("k") or "-",
                         x=round(b["x"], 2), y=round(b["y"], 2), N_comp_ULS_kN=round(en["Nc"], 1), N_uplift_ULS_kN=round(en["Nt"], 1),
                         Hx_ULS_kN=round(en["Hx"], 1), Hy_ULS_kN=round(en["Hy"], 1), M_base_ULS_kNm=round(en["M"], 1),
                         extra_perm_kN=b["extra_perm"], base_plate=b["base"]["plate_mm"], holding_down=b["base"]["bolts"],
                         anchor_reinforcement=b["base"].get("anchor_reinf", "-"), pad_BxLxD_m=f"{b['pad']['B']:.1f} x {b['pad']['L']:.2f} x {b['pad']['D']:.2f}",
                         As_bottom_mm2_per_m=round(b["pad"]["As_bot"]), As_top_mm2_per_m=round(b["pad"]["As_top"]), pad_rebar_kg=round(b["pad"]["rebar_kg"], 1),
                         note=b["pad"]["notes"] or "-"))
wcsv("C2_base_reactions_and_foundation_schedule.csv", rows)
# C3 load schedule
L = [("Permanent", "Roof dead (sheeting 0.060, purlins 0.066, insulation 0.040, bracing 0.012)", MB.ROOF_DEAD, "kN/m2 plan", "R2 load schedule"),
     ("Permanent", "General suspended services", MB.SERVICES, "kN/m2 plan", "R2 central"),
     ("Permanent", "Truss, column, post, bracing self-weight", "model", "kg/m x L x 1.05-1.08", "calculated"),
     ("Permanent", "Acoustic rafts 3.4 kN/group, HVLS fans 1.8 kN, ridge fans 4.0 kN, cable trays 0.25 kN/m (central)", "see model_b.SCEN", "kN", "R2 scenario values (no products selected)"),
     ("Variable", "Roof imposed (maintenance, inaccessible)", MB.Q_ROOF, "kN/m2 plan", "SANS 10160-2 cat H (to verify)"),
     ("Variable", "Rigging: line arrays 8 kN each, lighting bars 0.40 kN/m, x1.20 dynamic", "see model_b.SCEN", "kN", "R2 scenario; future scenario as sensitivity"),
     ("Permanent", "North wall masonry over loggia via transfer beam (lines 7-9 north)", "134 / 267 / 134", "kN", "study assumption - no transfer structure modelled"),
     ("Wind", "Peak velocity pressure q_p", "0.85 (SLS, ULS) / 1.20 (ULS)", "kPa", "R2 central/upper; Harare design gust unconfirmed"),
     ("Wind", "Long walls cpe D/E", f"{MB.CPE_D}/{MB.CPE_E}", "-", "EN 1991-1-4 Table 7.1, h/d 0.44"),
     ("Wind", "Gables cpe D/E", f"{MB.CPE_GD}/{MB.CPE_GE}", "-", "h/d 0.26"),
     ("Wind", "Side walls, wind parallel to ridge, zones A/B/C", "/".join(str(c) for c in MB.CPE_ABC), "-", "e = 29 m"),
     ("Wind", "Internal pressure cpi", "+0.2 / -0.3 (dominant opening +0.55 as sensitivity)", "-", "EN 1991-1-4 7.2.9"),
     ("Wind", "Roof net cp", "R2 profiles (duopitch 15 deg, zones F-J)", "-", "R2 options_and_loads.wind_profile"),
     ("Imperfection", "Notional horizontal load", "0.005 x factored gravity", "-", "SANS 10162-1 cl 8.7.2"),
     ("Combination", "ULS", "1.35G; 1.2G+1.6Qr; 1.2G+1.6Qrig; 1.2G+1.3W; 0.9G+1.3W", "-", "SANS 10160-1 STR/EQU"),
     ("Combination", "SLS deflection", "1.0W at q_p 0.85 (1.20 as sensitivity); limit h/300 for masonry", "-", "study criterion"),
     ("Combination", "Construction stage", "0.9G + 1.3 x 0.75 x W(q 1.20), walls not yet built", "-", "study assumption - to confirm"),
     ("Combination", "Foundation bearing", "characteristic G+W, G+Q (allowable bearing)", "-", "Harare practice (SANS 10160-5 to confirm)")]
wcsv("C3_load_schedule.csv", [dict(category=a, item=b, value=c, unit=d, basis=e) for a, b, c, d, e in L])
# C4 member and stability summary
rows = []
for s, r in recs.items():
    worst = max(r["cols"], key=lambda c: c["util"])
    rows.append(dict(scheme=s, column=r["column"], column_util_max=round(r["col_util"], 3), governing_combo=worst["combo"], at_z=worst["z"],
                     defl_y_SLS_q085_mm=round(r["drift"]["SLS_W"]["col_y_mm"], 1), limit_mm=round(12.23 / 300 * 1000, 1),
                     defl_y_SLS_q120_mm=round(r["drift"]["SLS_W12"]["col_y_mm"], 1), eaves_x_SLS_q085_mm=round(r["drift"]["SLS_W"]["eaves_x_mm"], 1),
                     eaves_x_SLS_q120_mm=round(r["drift"]["SLS_W12"]["eaves_x_mm"], 1), column_util_no_masonry_restraint=round(r.get("util_unrestrained", 0), 3),
                     post_util=round(r["post_util"], 3), post_defl_ratio=round(r["post_defl"], 3), alpha_cr_transverse=round(r["alpha"]["transverse"], 1),
                     alpha_cr_longitudinal=round(r["alpha"]["longitudinal"], 1)))
wcsv("C4_member_and_stability_summary.csv", rows)
# D steel comparison
rows = []
for s, e in evs.items():
    for g, v in e["steel"].items():
        rows.append(dict(scheme=s, group=g, section=v["section"], pieces=v["n"], length_m=round(v["L"], 1), mass_t=round(v["t"], 3),
                         role=ROLE.get(g, g), common_to_all=g in EV.COMMON_GROUPS))
    rows.append(dict(scheme=s, group="PLATES", section="S355 plate", pieces="-", length_m="-", mass_t=round(e["steel_t"]["plates"], 3),
                     role="connection and base plates (allowance)", common_to_all=False))
wcsv("D_steel_framing_comparison.csv", rows)
# E foundation comparison
ev_all = [x for x in json.load(open(ROOT + "/calcs/eval_base.json")) if x.get("ok")]
rows = []
for s in sel:
    for x in ev_all:
        if x["scheme"] == s and x["column"] == sel[s]["column"]:
            q, w = x["found_q"], x["wall_q"]
            rows.append(dict(scheme=s, column=x["column"], soil=x["soil"], arrangement=x["arrangement"], pad_concrete_m3=round(q["concrete_m3"], 1),
                             pad_rebar_t=round(q["rebar_kg"] / 1000, 2), pad_excavation_m3=round(q["excavation_m3"], 0), pad_formwork_m2=round(q["formwork_m2"], 0),
                             wall_concrete_m3=round(w["concrete_m3"], 1), wall_rebar_t=round(w["rebar_kg"] / 1000, 2), wall_excavation_m3=round(w["excavation_m3"], 0),
                             column_foundation_cost_usd=round(x["cost"]["column_foundations"]), wall_foundation_cost_usd=round(x["cost"]["wall_foundations"]),
                             total_supporting_system_usd=round(x["total"])))
wcsv("E_foundation_comparison.csv", rows)

# F workbook with live formulas
wb = Workbook()
H = Font(bold=True, color="FFFFFF")
HF = PatternFill("solid", fgColor="2A5D8F")


def head(ws, cols, r=1):
    for j, c in enumerate(cols, 1):
        x = ws.cell(r, j, c)
        x.font, x.fill = H, HF
        x.alignment = Alignment(wrap_text=True, vertical="top")


ws = wb.active
ws.title = "README"
for i, t in enumerate([
        "SOUTHGATE WORSHIP CENTER - Option B support structure: cost comparison model (deliverable F)",
        "Preliminary estimate, USD, excl. VAT, Harare 2026. NOT a tender price. No supplier quotations are included.",
        "Rates!B1 selects the rate column: 1 = low, 2 = central, 3 = high. Every cost is qty x rate x factor (sheet Lines).",
        "Quantities come from the study's 3D analysis, sizing and foundation design (scripts/sweep.py, evaluate.py), soil G2, arrangement F2.",
        "The Option B trusses, purlins and equipment steel are COMMON to all schemes and are excluded (context value on Summary).",
        "At central rates the Summary totals reproduce scripts/evaluate.py (row 'Model totals').",
        "Evidence class for every rate is in Rates!G. Treat INFERRED / ASSUMPTION rates as placeholders for tender enquiry."], 1):
    ws.cell(i, 1, t)
ws.column_dimensions["A"].width = 130
wr = wb.create_sheet("Rates")
wr["A1"], wr["B1"] = "Rate column selector (1 low, 2 central, 3 high)", 2
head(wr, ["rate", "low", "central", "high", "unit", "basis", "evidence class", "SELECTED"], 3)
meta = {x["rate"]: x for x in csv.DictReader(open(ROOT + "/data/cost_rates.csv"))}
rr = {}
for i, k in enumerate(EV.RATES, 4):
    lo, c, hi = EV.RATES[k]
    for j, v in enumerate([k, lo, c, hi, meta[k]["unit"], meta[k]["basis"], meta[k]["evidence_class"]], 1):
        wr.cell(i, j, v)
    wr.cell(i, 8, f"=CHOOSE($B$1,B{i},C{i},D{i})")
    rr[k] = i
for col, wdt in zip("ABCDEFGH", (22, 9, 9, 9, 12, 90, 22, 11)):
    wr.column_dimensions[col].width = wdt
wl = wb.create_sheet("Lines")
head(wl, ["scheme", "category", "item", "qty", "unit", "rate key", "rate (selected)", "factor", "cost USD", "QA base", "O&P base"])
r = 2
for s, e in evs.items():
    for l in e["lines"]:
        vals = [s, l["category"], l["item"], round(l["qty"], 4), l["unit"], l["rate"], f"=Rates!H{rr[l['rate']]}", round(l["factor"], 4),
                f"=D{r}*G{r}*H{r}", l["qa"], l["op"]]
        for j, v in enumerate(vals, 1):
            wl.cell(r, j, v)
        r += 1
last = r - 1
for col, wdt in zip("ABCDEFGHIJK", (7, 26, 58, 11, 7, 16, 12, 8, 12, 8, 8)):
    wl.column_dimensions[col].width = wdt
wsu = wb.create_sheet("Summary")
cats = ["Side columns", "Gable wind posts", "Wind girders", "Bracing / ties / struts", "Connections", "Fabrication", "Corrosion protection",
        "Erection", "Architectural adjustment", "Foundations (columns/posts)", "Wall foundations"]
head(wsu, ["Cost component (USD)"] + [f"{s} ({sel[s]['column']})" for s in evs])
for i, c in enumerate(cats, 2):
    wsu.cell(i, 1, c)
    for j, s in enumerate(evs, 2):
        wsu.cell(i, j, f'=SUMIFS(Lines!$I$2:$I${last},Lines!$A$2:$A${last},"{s}",Lines!$B$2:$B${last},"{c}")')
n = len(cats) + 2
labels = ["Subtotal (direct)", "QA / testing (2 % steel, 1.5 % foundations)", "Overhead & profit on labour and plant", "Contingency (design development + scheme risk)",
          "TOTAL supporting-system cost", "Scheme risk allowance (fraction)", "Contingency (fraction, Rates)", "O&P (fraction, Rates)"]
for k, t in enumerate(labels):
    wsu.cell(n + k, 1, t)
for j, s in enumerate(evs, 2):
    cl = get_column_letter(j)
    p = evs[s]["pct"]
    wsu.cell(n, j, f"=SUM({cl}2:{cl}{n-1})")
    wsu.cell(n + 1, j, f'=0.02*SUMIFS(Lines!$I$2:$I${last},Lines!$A$2:$A${last},"{s}",Lines!$J$2:$J${last},"steel")'
                       f'+0.015*SUMIFS(Lines!$I$2:$I${last},Lines!$A$2:$A${last},"{s}",Lines!$J$2:$J${last},"found")')
    wsu.cell(n + 7, j, f"=Rates!H{rr['overhead_profit']}")
    wsu.cell(n + 2, j, f'={cl}{n+7}*SUMIFS(Lines!$I$2:$I${last},Lines!$A$2:$A${last},"{s}",Lines!$K$2:$K${last},1)')
    wsu.cell(n + 5, j, p["risk"])
    wsu.cell(n + 6, j, f"=Rates!H{rr['contingency']}")
    wsu.cell(n + 3, j, f"=({cl}{n}+{cl}{n+1}+{cl}{n+2})*({cl}{n+6}+{cl}{n+5})")
    wsu.cell(n + 4, j, f"={cl}{n}+{cl}{n+1}+{cl}{n+2}+{cl}{n+3}")
    wsu.cell(n + 4, j).font = Font(bold=True)
wsu.cell(n + 9, 1, "Model totals (scripts/evaluate.py, central rates, G2/F2)")
for j, s in enumerate(evs, 2):
    wsu.cell(n + 9, j, round(evs[s]["total"]))
wsu.cell(n + 11, 1, "Common Option B roof package (trusses, purlins, equipment steel and their fabrication/erection): ~USD 195,000 from R2 option B "
                    "(R2 total 298,802 less columns, lateral system, foundations, temporary works and contingency). Context only, not re-estimated.")
wsu.column_dimensions["A"].width = 52
for c in "BCD":
    wsu.column_dimensions[c].width = 22
ws2 = wb.create_sheet("Soil_Arrangement")
head(ws2, ["scheme", "column", "soil", "F1 independent pads", "F2 pads + reinforced wall strip", "F3 deep pads + ground beams"])
r = 2
for s in sel:
    for so in ("G1", "G2", "G3"):
        for j, v in enumerate([s, sel[s]["column"], so] + [round(sel[s]["by_soil"][so][a] or 0) for a in ("F1", "F2", "F3")], 1):
            ws2.cell(r, j, v)
        r += 1
ws3 = wb.create_sheet("MonteCarlo")
head(ws3, ["scheme", "P10", "P50", "P90", "mean", "share of trials cheapest"])
for i, (s, v) in enumerate([(s, mc[s]) for s in ("S1", "S2", "S3")], 2):
    ws3.cell(i, 1, s)
    for j, k in enumerate(["p10", "p50", "p90", "mean", "cheapest_share"], 2):
        ws3.cell(i, j, round(v[k], 3) if k == "cheapest_share" else round(v[k]))
ws3.cell(6, 1, "1,500 trials; correlated rate groups (steel, labour, plant, concrete, rebar, earthworks), triangular fixings/other; independent quantity factors per scheme: steel 0.92-1.00-1.10, foundations 0.85-1.00-1.25.")
for j, (kk, vv) in enumerate(mc["pairwise"].items(), 7):
    ws3.cell(j, 1, kk); ws3.cell(j, 2, round(vv, 3))
wb.save(OUT + "/F_cost_comparison_model.xlsx")
for s, e in evs.items():
    print(s, sel[s]["column"], round(e["total"]))
