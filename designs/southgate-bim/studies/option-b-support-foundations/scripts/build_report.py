"""Builds the main engineering report (deliverable A): report/Option_B_Support_Structure_Study.html -> .pdf (headless Edge).
Every number in the tables is read from the study's calculation outputs."""
import base64, csv, json, os, subprocess, sys
sys.path.insert(0, os.path.dirname(__file__))
import evaluate as EV

ROOT = EV.ROOT
R = lambda p: json.load(open(f"{ROOT}/{p}"))
sel, mc = R("calcs/selection.json"), R("calcs/montecarlo.json")
sw = R("calcs/sweep_base.json")["results"]
sens = R("calcs/sensitivity_table.json")
ver = R("calcs/solver_verification.json")
reg = list(csv.DictReader(open(f"{ROOT}/data/B_structural_support_register.csv", encoding="utf-8")))
c1 = list(csv.DictReader(open(f"{ROOT}/data/C1_truss_bearing_reactions.csv")))
c2 = list(csv.DictReader(open(f"{ROOT}/data/C2_base_reactions_and_foundation_schedule.csv")))
c4 = {r["scheme"]: r for r in csv.DictReader(open(f"{ROOT}/data/C4_member_and_stability_summary.csv"))}
risk = list(csv.DictReader(open(f"{ROOT}/data/H_risk_and_outstanding_information_register.csv")))
review = open(f"{ROOT}/review/I_independent_review_record.md", encoding="utf-8").read() if os.path.exists(f"{ROOT}/review/I_independent_review_record.md") else ""
recs = {s: next(r for r in sw if r["scheme"] == s and r["column"] == sel[s]["column"]) for s in sel}
evs = {s: EV.evaluate(recs[s], "G2", "F2") for s in sel}

NAME = {"S1": "S1 Braced frame", "S2": "S2 Moment-resisting", "S3": "S3 Hybrid"}
S = ("S1", "S2", "S3")

# ---- review-round-1 helper values (all computed)
UNC = R("calcs/selection_unconstrained.json")
WD = R("calcs/wall_density_07.json") if os.path.exists(f"{ROOT}/calcs/wall_density_07.json") else {}
PW = mc.get("pairwise", {})
CHEAP = {so: min(S, key=lambda x: sel[x]["by_soil"][so]["F2"]) for so in ("G1", "G2", "G3")}
LIM = 12.23 / 300 * 1000
SENSF = {}
for row in sens:
    for s_, c in zip(S, row[1:]):
        if c is not None and not c[0]:
            SENSF.setdefault(s_, []).append(row[0])
pct = lambda a, b: (a / b - 1) * 100


def img(p, w="100%"):
    f = f"{ROOT}/{p}"
    return f"<img src='data:image/png;base64,{base64.b64encode(open(f, 'rb').read()).decode()}' style='width:{w}'>" if os.path.exists(f) else ""


def fig(p, cap, w="100%"):
    return f"<div class='fig'>{img(p, w)}<p>{cap}</p></div>"


def tbl(head, rows, cls=""):
    h = "".join(f"<th>{x}</th>" for x in head)
    b = "".join("<tr>" + "".join(f"<td>{x}</td>" for x in r) + "</tr>" for r in rows)
    return f"<table class='{cls}'><thead><tr>{h}</tr></thead><tbody>{b}</tbody></table>"


k = lambda v: f"{v/1000:,.0f}k"
usd = lambda v: f"{v:,.0f}"


def cat_cost(e, cats=None, items=None):
    t = 0.0
    for l in e["lines"]:
        if cats and l["category"] not in cats:
            continue
        if items and not any(i in l["item"] for i in items):
            continue
        t += l["qty"] * EV.rate(l["rate"]) * l["factor"]
    return t


def brief_cost_rows():
    F_ = ("Foundations (columns/posts)", "Wall foundations")
    defs = [("Side columns (supply)", lambda e: cat_cost(e, ["Side columns"])),
            ("Gable wind posts (supply, common)", lambda e: cat_cost(e, ["Gable wind posts"])),
            ("Wind girders (supply)", lambda e: cat_cost(e, ["Wind girders"])),
            ("Bracing, ties, struts (supply)", lambda e: cat_cost(e, ["Bracing / ties / struts"])),
            ("Connections, base plates, HD bolts, grout", lambda e: cat_cost(e, ["Connections"])),
            ("Foundations: concrete, blinding, formwork", lambda e: cat_cost(e, F_, ["concrete", "blinding", "formwork"])),
            ("Reinforcement (pads, wall strip)", lambda e: cat_cost(e, F_, ["reinforcement"])),
            ("Groundworks: excavation, backfill, disposal", lambda e: cat_cost(e, F_, ["excavation", "backfill", "disposal", "void"])),
            ("Fabrication and corrosion protection", lambda e: cat_cost(e, ["Fabrication", "Corrosion protection"])),
            ("Transport, erection, cranes, access, temporary works", lambda e: cat_cost(e, ["Erection"])),
            ("QA/testing, O&amp;P on labour and plant, contingency", lambda e: e["cost"]["qa_testing"] + e["cost"]["overhead_profit_labour_plant"] + e["cost"]["contingency"])]
    rows = []
    for lab, fn in defs:
        rows.append([lab] + [usd(fn(evs[s])) for s in S])
    rows.append(["<b>Total supporting-system cost</b>"] + [f"<b>{usd(evs[s]['total'])}</b>" for s in S])
    rows.append(["Difference from S3"] + [("&ndash;" if s == "S3" else f"+{usd(evs[s]['total'] - evs['S3']['total'])} (+{(evs[s]['total'] / evs['S3']['total'] - 1) * 100:.1f}%)") for s in S])
    return rows


def bearing_summary():
    out = []
    for q in ("0.85", "1.2"):
        rr = [r for r in c1 if r["scheme"] == "S3" and r["qp_kPa"] == q]
        inter = [r for r in rr if r["line"] not in ("0", "10")]
        gab = [r for r in rr if r["line"] in ("0", "10")]
        out.append([f"{float(q):.2f}", max(float(r["Rv_comp_ULS_kN"]) for r in rr), min(float(r["Rv_uplift_ULS_kN"]) for r in inter),
                    min(float(r["Rv_uplift_ULS_kN"]) for r in gab), max(float(r["H_transverse_ULS_kN"]) for r in rr), max(float(r["H_longit_ULS_kN"]) for r in rr),
                    {"0.85": "110 / &minus;44", "1.2": "&ndash; / &minus;75 (gable &minus;104)"}[q]])
    return out


# light-cladding decision case: walls not masonry -> no wall strip, no wall ballast (F1), h/150
LIGHT = {}
for r in R("calcs/sweep_light.json")["results"]:
    if not r["ok"]:
        continue
    e = EV.evaluate(r, "G2", "F1")
    if not e.get("ok"):
        continue
    t = e["total"] - e["cost"]["wall_foundations"] * 1.015 * (1 + e["pct"]["cont"])
    if r["scheme"] not in LIGHT or t < LIGHT[r["scheme"]][0]:
        LIGHT[r["scheme"]] = (t, r["column"])
F3PREM = sel["S3"]["by_soil"]["G3"]["F3"] - sel["S3"]["by_soil"]["G3"]["F2"]
G3INC = {s: sel[s]["by_soil"]["G3"]["F2"] - sel[s]["by_soil"]["G2"]["F2"] for s in S}
D13, D23 = None, None
roof_cols = [r for r in reg if r["family"] == "Roof truss support column"]
no_ftg = [r for r in roof_cols if r["foundation"] == "NONE MODELLED"]
gal = [r for r in reg if r["family"].startswith("Gallery") and "column" in r["family"]]
s3b = [r for r in c2 if r["scheme"] == "S3"]


def env_range(kind, key, sch="S3", f=max):
    v = [float(r[key]) for r in c2 if r["scheme"] == sch and r["kind"] == kind]
    return f(v)


sec_rows = []
for g, lab in (("COL", "Side columns (lines 1-9)"), ("COLC", "Gable-line columns (0, 10)"), ("POST", "Gable wind posts (12)"), ("EAV", "Eaves struts"),
               ("EGC", "Eaves girder inner chord"), ("EGD", "Eaves girder diagonals"), ("RBD", "End-bay roof girder diagonals"), ("XF", "End-bay cross frames"),
               ("BCB", "End-bay bottom-chord bracing"), ("BCT", "Bottom-chord ties @ 5.4 m"), ("GBX", "Gable bracing diagonals"), ("WBX", "Wall bracing X (bays 1, 5)"),
               ("WBK", "Wall bracing knees"), ("WBS", "Wall bracing sill strut")):
    row = [lab]
    for s in S:
        st = evs[s]["steel"].get(g)
        row.append(f"{st['section']} &middot; {st['t']:.1f} t" if st else "&ndash; (not required)")
    sec_rows.append(row)

sweep_rows = []
for r in sorted(sw, key=lambda r: (r["scheme"], EV.CAT[r["column"]].kg)):
    c = EV.CAT[r["column"]]
    e = next((x for x in R("calcs/eval_base.json") if x.get("ok") and x["scheme"] == r["scheme"] and x["column"] == r["column"] and x["soil"] == "G2" and x["arrangement"] == "F2"), None)
    sweep_rows.append([r["scheme"], r["column"], f"{c.kg:.0f}", f"{c.d*1000:.0f}" + ("" if c.d <= 0.42 else " &#9888;"), c.avail, f"{r['col_util']:.2f}",
                       f"{r['drift']['SLS_W']['col_y_mm']:.1f}", "pass" if r["ok"] else "<span class='bad'>fail</span>",
                       f"{r.get('util_unrestrained', 0):.2f}" + ("" if r.get('util_unrestrained', 9) <= 1 else " <span class='bad'>fail</span>"), usd(e["total"]) if e else "&ndash;"])

sens_rows = [[row[0]] + [("&ndash;" if c is None else (("pass" if c[0] else "<span class='bad'>FAIL</span>") + f" &middot; u {c[1]:.2f} &middot; {c[2]:.0f}/{c[3]:.0f} mm" + ("" if c[4] else f" ({c[5]})"))) for c in row[1:]] for row in sens]
soil_rows = [[NAME[s], so] + [usd(sel[s]["by_soil"][so][a]) for a in ("F1", "F2", "F3")] for s in S for so in ("G1", "G2", "G3")]
q_rows = []
for s in S:
    v = sel[s]
    q_rows.append([NAME[s], v["column"], f"{v['steel_t']['columns']:.1f}", f"{v['steel_t']['posts']:.1f}", f"{v['steel_t']['bracing_girders']:.1f}", f"{v['steel_t']['plates']:.1f}",
                   f"<b>{v['steel_t']['total']:.1f}</b>", f"{v['found_q']['concrete_m3'] + v['wall_q']['concrete_m3']:.0f}",
                   f"{(v['found_q']['rebar_kg'] + v['wall_q']['rebar_kg'] + v['hd']['anchor_reinf_kg'])/1000:.1f}",
                   f"{v['found_q']['excavation_m3'] + v['wall_q']['excavation_m3']:.0f}", f"{v['hd']['n']}", f"{v['bolts']}"])
risk_rows = [[r["id"], r["discipline"], r["issue"], r["likelihood"], r["impact"], r["action / information required"], r["gate"]] for r in risk]
s3cols = [r for r in c2 if r["scheme"] == "S3" and r["kind"] == "column" and r["side"] == "A"]
s3posts = [r for r in c2 if r["scheme"] == "S3" and r["kind"] == "post" and r["line"] == "0"]
found_rows = [[f"{r['kind']} {r['line']}{r['side'] if r['kind']=='column' else ' k' + r['post_k']}", r["N_comp_ULS_kN"], r["N_uplift_ULS_kN"], r["Hy_ULS_kN"], r["Hx_ULS_kN"],
               r["M_base_ULS_kNm"], r["base_plate"], r["holding_down"].replace(" cast-in", ""), r["pad_BxLxD_m"], r["As_bottom_mm2_per_m"], r["As_top_mm2_per_m"]] for r in s3cols + s3posts]
ver_rows = [[v["case"], f"{v['model']:.2f}", f"{v['exact']:.2f}", f"{v['ratio']:.4f}"] for v in ver]

CSS = """
@page { size: A4; margin: 17mm 16mm 18mm 16mm; @bottom-right { content: counter(page); } }
body { font-family: 'Segoe UI', Arial, sans-serif; font-size: 9.4pt; color: #1b1b1a; background:#fff; line-height: 1.45; }
h1 { font-size: 15.5pt; color: #0d2a45; border-bottom: 2px solid #2a5d8f; padding-bottom: 3px; margin: 0 0 8px; page-break-before: always; }
h2 { font-size: 11.5pt; color: #2a5d8f; margin: 14px 0 5px; }
h3 { font-size: 10pt; margin: 10px 0 4px; }
p { margin: 4px 0 7px; text-align: justify; }
ul, ol { margin: 3px 0 8px 18px; padding: 0; } li { margin: 2px 0; }
table { border-collapse: collapse; width: 100%; margin: 6px 0 10px; font-size: 7.9pt; }
th, td { border: 1px solid #d5d3cc; padding: 2.5px 4px; vertical-align: top; text-align: left; }
th { background: #eaf0f7; font-weight: 600; } tr { page-break-inside: avoid; }
table.num td:not(:first-child) { text-align: right; }
.fig { page-break-inside: avoid; margin: 6px 0 12px; } .fig img { border: 1px solid #e3e1da; } .fig p { font-size: 8pt; color: #555; margin: 2px 0; text-align:left; }
.box { border-left: 3px solid #2a5d8f; background: #f3f7fb; padding: 6px 10px; margin: 8px 0; page-break-inside: avoid; }
.warn { border-left: 3px solid #c77700; background: #fff7e8; padding: 6px 10px; margin: 8px 0; page-break-inside: avoid; }
.bad { color: #b3261e; font-weight: 600; }
.cover { height: 255mm; display: flex; flex-direction: column; justify-content: space-between; }
.cover h1 { page-break-before: avoid; border: none; font-size: 24pt; color: #0d2a45; margin-top: 40mm; }
.cover .sub { font-size: 14pt; color: #2a5d8f; margin-top: 4mm; } .cover .it { font-style: italic; font-size: 11pt; color: #444; }
.stamp { color: #b3261e; font-weight: 700; letter-spacing: .03em; font-size: 9pt; }
.meta td { border: none; padding: 1px 8px 1px 0; font-size: 8.6pt; }
.toc li { margin: 1px 0; font-size: 9pt; }
code { font-size: 8pt; background: #f2f1ec; padding: 0 2px; }
"""

H = []
H.append(f"""<html><head><meta charset='utf-8'><title>Southgate Option B Support Structure Study</title><style>{CSS}</style></head><body>
<div class='cover'><div>
<p class='stamp'>PRELIMINARY STRUCTURAL ENGINEERING STUDY &mdash; NOT FOR CONSTRUCTION &mdash; NOT ENGINEER-APPROVED</p>
<h1>SOUTHGATE WORSHIP CENTER</h1>
<div class='sub'>PRIMARY STEEL SUPPORT STRUCTURE, LATERAL STABILITY &amp; FOUNDATION OPTIMISATION STUDY</div>
<p class='it'>Based on the Recommended Option B Roof Truss System</p>
<table class='meta' style='width:auto;margin-top:12mm'>
<tr><td>Project</td><td>Southgate Worship Center, ~2,000-seat main auditorium, Harare, Zimbabwe</td></tr>
<tr><td>Roof basis</td><td>Roof Structure Options Appraisal R2 (7 Nov 2026): Option B, 12-bay bolted paired-angle Warren truss with verticals (fixed)</td></tr>
<tr><td>Model basis</td><td><code>southgate-bim/bim/southgate.ifc</code> (IFC4), sha256 6cb86f6d&hellip;b035e, read-only</td></tr>
<tr><td>Revision / date</td><td>S01 &middot; 7 November 2026</td></tr>
<tr><td>Status</td><td>Recommendation for review. Nothing has been implemented in the BIM.</td></tr>
</table></div>
<div>{img('drawings/S-04_roof_framing_S3.png')}</div>
<p style='font-size:7.8pt;color:#555'>This study was prepared with AI assistance under the direction of the client's design team. It contains preliminary analyses and estimates only. It has not been checked, approved or certified by a registered professional engineer (ECZ) and must not be used for construction, fabrication or statutory submission.</p>
</div>""")

H.append("""<h1 style='page-break-before:always'>Contents</h1><ol class='toc'>
<li>Executive summary</li><li>Project description and study scope</li><li>Recommended roof-truss design basis</li><li>Existing side steel framing and foundation audit</li>
<li>Structural loading and design assumptions</li><li>Existing structural system assessment</li><li>Lateral stability alternatives</li><li>Side-column optimisation</li>
<li>Structural bracing and connection concepts</li><li>Foundation optimisation</li><li>Foundation reinforcement and anchorage considerations</li><li>Structural performance comparison</li>
<li>Material quantity assessment</li><li>Construction cost comparison</li><li>Geotechnical and cost sensitivity</li><li>Architectural coordination</li>
<li>Recommended structural solution</li><li>Outstanding engineering requirements</li><li>Conclusions</li><li>Technical appendices</li></ol>
<p>Deliverables in <code>southgate-bim/studies/option-b-support-foundations/</code>: A this report; B <code>data/B_structural_support_register.csv</code>, <code>B_footing_register.csv</code>;
C <code>data/C1&ndash;C4_*.csv</code>, <code>calcs/*.json</code>, <code>scripts/</code>; D <code>data/D_steel_framing_comparison.csv</code>; E <code>data/E_foundation_comparison.csv</code>;
F <code>data/F_cost_comparison_model.xlsx</code>; G <code>drawings/G_structural_concept_drawings.pdf</code>; H <code>data/H_risk_and_outstanding_information_register.csv</code>;
I <code>review/I_independent_review_record.md</code>; J <code>bim_spec/J_BIM_implementation_specification.md</code>.</p>""")

e1, e2, e3 = evs["S1"], evs["S2"], evs["S3"]
H.append(f"""<h1>1. Executive summary</h1>
<div class='box'><b>Recommendation (conditional).</b> For the ground conditions assumed as the base case (G1/G2: allowable bearing &ge; 150 kPa, no expansive clay, no shallow water), support the Option B trusses on the <b>hybrid stability system S3</b>:
22 <b>UC 305&times;305&times;97</b> side columns with <b>fixed bases about the strong axis</b>, propped at the eaves by two 5.4 m-deep roof-plane wind girders that span between braced gables; gable wind posts with designed minor-axis restraint; end-bay roof girders and bottom-chord ties; and longitudinal wall bracing in bays 1 and 5. Found the columns on reinforced pads <b>cast integral with a continuous reinforced strip under the masonry walls (F2)</b>.
Estimated supporting-system cost: <b>USD {k(mc['S3']['p50'])} (P50)</b>, P10&ndash;P90 {k(mc['S3']['p10'])}&ndash;{k(mc['S3']['p90'])}; deterministic central estimate {k(e3['total'])}.
<b>The margin over the braced system S1 is small</b>: {pct(e1['total'], e3['total']):.1f}% at central rates, and S3 is cheaper than S1 in {PW.get('P(S3<S1)', 0)*100:.0f}% of trials and cheaper than S2 in {PW.get('P(S3<S2)', 0)*100:.0f}%.
<b>If the site investigation finds poor or wet ground (G3), the braced system S1 with pinned bases becomes the cheaper and simpler choice</b> (USD {k(sel['S1']['by_soil']['G3']['F2'])} against {k(sel['S3']['by_soil']['G3']['F2'])}). The stability system should therefore be confirmed after the site investigation (gate G-B).</div>
<h2>Answers to the ten questions</h2>
<ol>
<li><b>Is the existing side-column arrangement suitable?</b> No. With a complete bracing system, the modelled UC 254&times;254&times;73 columns on pinned 4 &times; M24 bases deflect &asymp;80&ndash;100 mm under the central wind (q<sub>p</sub> 0.85 kPa). The limit for the 12.23 m masonry is h/300 = {LIM:.1f} mm. The section also fails strength (utilisation &asymp;1.1) at 1.20 kPa. In addition, two east-gable columns have no footing, there are no gable wind posts, the roof bracing is four 20 mm rods, and the north wall over the loggia has no transfer structure. The grid itself (11 lines @ 5.56 m, columns within the 420 mm wall/pier zone) is suitable and is retained.</li>
<li><b>Sections and restraint.</b> S3: UC 305&times;305&times;97 (regional stock, by study judgement; 308 mm deep), fixed base about the strong axis, propped at the eaves. Utilisation {c4['S3']['column_util_max']}; {c4['S3']['column_util_no_masonry_restraint']} with no masonry restraint over the full 13.08 m. Transverse deflection {c4['S3']['defl_y_SLS_q085_mm']} mm and longitudinal eaves sway {c4['S3']['eaves_x_SLS_q085_mm']} mm against {LIM:.1f} mm. S1 needs UC 305&times;305&times;137 (pinned) and S2 needs UC 356&times;368&times;153 (imported, by study judgement). The UB alternatives no longer pass once the purlins are not relied on as girder chords, and in any case they depend on masonry restraint.</li>
<li><b>Braced, moment or hybrid?</b> Hybrid on firm ground, braced on poor ground. S2 is the most expensive in every soil scenario ({pct(e2['total'], e3['total']):.0f}% above S3 at G2) and is not recommended. The gap between S3 and S1 ({k(e1['total'] - e3['total'])}) is within the estimating uncertainty, so non-cost factors also count. S3 is self-stable during erection, has transverse stiffness reserve and uses the lightest columns. S1 has simpler pinned bases and smaller pads, which win where the ground is poor.</li>
<li><b>Can the gallery or integrated framing help?</b> Not in the recommended scheme. The gallery reaches only +7.85 m, has no designed foundations and carries placeholder sections. The stair cores (walls to +10.80 m, construction unverified, no footings) could replace the east-gable bracing and the bay-5 wall bracing if they are proven to be RC shear walls. That is a conditional optimisation estimated at USD 10&ndash;15k, not a basis for design. The single-storey office wing should remain structurally independent.</li>
<li><b>Most economical credible foundation.</b> F2, reinforced pads cast integral with a 0.60 &times; 0.45 m reinforced wall strip, is the cheapest arrangement for every system in every soil scenario. The wall weight is counted only where the wall actually exists: net of doors, the north loggia and the east glazed slot. For S3 the pads are 2.3&ndash;3.3 m square and 0.80 m deep (the depth is set by the holding-down anchorage). Under G3, F3 (deep pads with ground beams over void formers) costs only about USD {usd(sel['S3']['by_soil']['G3']['F3'] - sel['S3']['by_soil']['G3']['F2'])} more and is the prudent choice if the clay is expansive.</li>
<li><b>Governing foundation actions.</b> Uplift and overturning under the concurrent ULS combinations govern, not bearing. Braced-bay columns see &asymp;{env_range('column','N_uplift_ULS_kN'):.0f} kN uplift and the braced gable posts &asymp;{env_range('post','N_uplift_ULS_kN'):.0f} kN. The S3 fixed bases carry &asymp;200&ndash;220 kNm together with up to &asymp;290 kN of uplift. Ordinary truss bearings deliver 55&ndash;92 kN uplift (q<sub>p</sub> 0.85&ndash;1.20). The construction stage, before the masonry is built, governs several pads.</li>
<li><b>Quantities (S1 / S2 / S3).</b> Supporting steel {sel['S1']['steel_t']['total']:.0f} / {sel['S2']['steel_t']['total']:.0f} / {sel['S3']['steel_t']['total']:.0f} t. Foundation concrete {sel['S1']['found_q']['concrete_m3']+sel['S1']['wall_q']['concrete_m3']:.0f} / {sel['S2']['found_q']['concrete_m3']+sel['S2']['wall_q']['concrete_m3']:.0f} / {sel['S3']['found_q']['concrete_m3']+sel['S3']['wall_q']['concrete_m3']:.0f} m&sup3;. Reinforcement, including anchor reinforcement, {(sel['S1']['found_q']['rebar_kg']+sel['S1']['wall_q']['rebar_kg']+sel['S1']['hd']['anchor_reinf_kg'])/1000:.1f} / {(sel['S2']['found_q']['rebar_kg']+sel['S2']['wall_q']['rebar_kg']+sel['S2']['hd']['anchor_reinf_kg'])/1000:.1f} / {(sel['S3']['found_q']['rebar_kg']+sel['S3']['wall_q']['rebar_kg']+sel['S3']['hd']['anchor_reinf_kg'])/1000:.1f} t. Excavation {sel['S1']['found_q']['excavation_m3']+sel['S1']['wall_q']['excavation_m3']:.0f} / {sel['S2']['found_q']['excavation_m3']+sel['S2']['wall_q']['excavation_m3']:.0f} / {sel['S3']['found_q']['excavation_m3']+sel['S3']['wall_q']['excavation_m3']:.0f} m&sup3; (&sect;13).</li>
<li><b>Costs (central, G2/F2).</b> USD {usd(e1['total'])} / {usd(e2['total'])} / {usd(e3['total'])}. P50 {k(mc['S1']['p50'])} / {k(mc['S2']['p50'])} / {k(mc['S3']['p50'])}. VAT and the common Option B roof package (&asymp;USD 195k, R2) are excluded. S3 has the least steel and the most concrete.</li>
<li><b>Most robust.</b> On firm ground, S3: it keeps its stiffness reserve transversely and is self-stable in erection. Selected-design sensitivity failures: S1 {', '.join(SENSF.get('S1', [])) or 'none'}; S2 {', '.join(SENSF.get('S2', [])) or 'none'}; S3 {', '.join(SENSF.get('S3', [])) or 'none'} (&sect;15). On poor or wet ground, S1. <b>Two assumptions can reverse the choice:</b> the ground (G3 favours S1) and the wall construction (lightweight cladding removes the masonry stiffness criterion; &sect;15).</li>
<li><b>Information needed before detailed design.</b> Confirmation of the wall construction; the Harare design wind speed and the governing code set; a site investigation (trial pits, DPSH/boreholes, swell and collapse tests, groundwater, subgrade modulus for base fixity); equipment and rigging weights; supplier prices for UC 305, CHS and holding-down assemblies; and the construction sequence (&sect;18).</li></ol>
<div class='warn'><b>Option B issues reported, not redesigned.</b> (a) When the gable trusses act as lateral-system collectors, their 2L80&times;8 top chords reach axial utilisation &asymp;0.8&ndash;0.9 before purlin bending, against 0.72 in R2. Consider 2L90&times;8, as on the interior lines. (b) The gable bottom-chord heel panels need out-of-plane restraint under uplift (elastic critical factor 0.22 without it). The eigen-analysis also shows the gable bottom chord between ties at &alpha; &asymp; 2.0, which is a truss-member check for the Option B design. (c) The truss bearing as modelled is 145 mm eccentric to the column axis. (d) The 3D truss reactions are 10&ndash;25% above R2's 2D screening values (Table 3.2). (e) The bearing bolts act as ties in wind and should be preloaded (slip-resistant) or fitted, not ordinary bolts in slotted holes.</div>""")
H.append(f"""<h1>2. Project description and study scope</h1>
<p>The auditorium is a 55.9 &times; 33.0 m hall. Eleven Option B trusses span 32.4 m between side-wall columns at 5.56 m centres (grid lines 0&ndash;10, x = 3.25&ndash;58.85 m). The stage is at the west end (line 0), and the gallery and stair cores are at the east (x 36.6&ndash;58.7 m). A single-storey office wing (+4.42 m) adjoins the west gable. The side walls are 300 mm masonry infill between the columns, 12.5 m high, with clerestory windows at +10.10 to +11.80 m in bays 0&ndash;6 and doors in bays 0, 4, 7 and 9. A 9.5 m loggia opening on the north side (x 43&ndash;52.5 m) rises to +4.00 m.</p>
<p><b>Scope:</b> roof support columns, side-wall and gable framing, longitudinal and transverse stability, roof-plane girders and bracing, bottom-chord restraint, truss-to-column and base connections, foundations and ground beams, and the interfaces with the gallery, entrances, cores and office wing. <b>Excluded:</b> the detached children's church, other standalone buildings, the Option B truss configuration (fixed), and the gallery, core and office structures (interfaces only). The study did not modify <code>southgate.ifc</code> or the original design project. All analysis used isolated study models.</p>
<h2>2.1 Method</h2>
<ol><li>Read-only audit of the authoritative IFC (sha256 verified against <code>bim/publish_record.json</code>) and the migration audit reports.</li>
<li>An independent 3D frame model (<code>scripts/model_b.py</code>, <code>frame3d.py</code>) of all 11 Option B trusses (R2 member sizes), 22 columns, 12 gable posts and every bracing system. Solver verified against closed-form results (Appendix A).</li>
<li>Characteristic load cases with SANS 10160-1 combinations. Eight wind cases (four directions, two internal pressures) at q<sub>p</sub> 0.85 and 1.20 kPa.</li>
<li>For each stability system, a sweep over 6&ndash;9 column sections. In each run the girders, bracing and posts are re-sized for strength and then stiffened until the SLS limits are met.</li>
<li>Pad design for every base: three soil scenarios &times; three arrangements. Bearing, uplift, overturning, sliding, bending, shear and punching are checked, and anchor embedment is coupled to pad depth.</li>
<li>Line-item costing (quantity &times; rate &times; factor), Monte Carlo on correlated rate groups, and sensitivity re-runs of the sizing.</li></ol>""")

H.append(f"""<h1>3. Recommended roof-truss design basis</h1>
<p>Option B is the fixed basis: a duo-pitch Warren truss with verticals, 12 panels @ 2.70 m, span 32.40 m (bearings at y = 0.30 / 32.70 m), 15&deg; pitch, top chord +12.38 m at the heel and +16.72 m at the ridge, bottom chord +10.90 m, heel depth 1.48 m, ridge depth 5.82 m, 11 trusses @ 5.56 m, &asymp;42.1 t. The geometry was verified against the IFC truss assemblies (bounding boxes x = 3.12&hellip;58.98, z = 10.67&hellip;16.77 m). Member sizes follow the R2 central run: TC 2L90&times;8 (gables 2L80&times;8), BC 2L80&times;8, end diagonals 2L100&times;8, other diagonals 2L75&times;6, verticals 2L60/2L75&times;6, king post 2L100&times;8, end posts 2L70&times;6. The truss was not re-optimised.</p>
<h2>3.1 Bearing condition</h2>
<p>The trusses bear at the top-chord heel on column cap plates at +12.28/+12.38 m. In S1 and S3 both bearings are pinned (bolts finally tightened after the roof dead load is applied), so the roof props both column heads. Option B's gravity spread is only 1&ndash;2 mm, so the resulting thrust is small (it is included in the analysis). In S2 the bottom chord is also connected to the column at +10.90 m (a 1.48 m &ldquo;knee&rdquo;), which makes each truss line a portal. The R2 bearing seat does not provide moment continuity, so S2 needs a purpose-designed heel connection.</p>
<h2>3.2 Support reactions (S3 model, ULS)</h2>
{tbl(['q<sub>p</sub> kPa', 'max compression kN', 'interior uplift kN', 'gable-line uplift kN', 'H transverse kN', 'H longitudinal kN', 'R2 screening (B)'], bearing_summary(), 'num')}
<p>The 3D reactions are 10&ndash;25% above R2's 2D values. They include the eaves girders' share of gravity, frame action, equipment on lines 1&ndash;2 and the near-edge roof zones. The upper-scenario uplift (&minus;92 kN interior, &minus;102 kN at the gables) governs the holding-down design.</p>""")

H.append(f"""<h1>4. Existing side steel framing and foundation audit</h1>
<p>Source: <code>scripts/s02_extract_inventory.py</code> and <code>s04_register.py</code> (read-only), giving 149 register rows (deliverable B). Findings were checked against <code>independent_final_review.md</code> O-06 and <code>outstanding_work.csv</code> OW-001/-028.</p>
{tbl(['Element', 'IFC evidence', 'Verified status', 'Engineering finding'], [
 ['Roof columns (22)', 'SOUTHGATE-COL-0011&hellip;0032, UC 254&times;254&times;73.1, z &minus;0.80&rarr;+12.28, y 0.155 / 32.845', 'CONCEPT_UNVERIFIED', 'Section inadequate for masonry deflection and for strength at 1.20 kPa (&sect;6)'],
 ['Roof-column footings', f"20 concept pads 1.5&times;1.5&times;0.65 m (lines 1&ndash;9), 1.6&times;1.3&times;0.65 m (line 0) + west strip; <b>none at line 10</b> ({', '.join(r['stable_id'] for r in no_ftg)})", 'CONCEPT_UNVERIFIED', 'Too small for uplift (they provide &asymp;35 kN against 55&ndash;310 kN needed); no strip under the long walls'],
 ['Base plates', 'SOUTHGATE-PLATE-0576&hellip;0597, 450&times;450&times;30, 4 M24 (schematic)', 'concept', 'Pinned; no anchorage design; cone breakout not checked'],
 ['Caps / seats', 'PLATE-0664&hellip;0707 at +12.18&hellip;+12.56', 'concept', 'Bearing 145 mm eccentric to the column axis'],
 ['Roof bracing', 'SOUTHGATE-BRACE-0001&hellip;0004, 20 mm rods, bays 0 and 9 only', 'CONCEPT_UNVERIFIED', 'No eaves girders, cross frames, bottom-chord ties or wall bracing'],
 ['Gable wind posts', 'none', '&ndash;', '<b>Missing.</b> 32.4 m gable walls have no intermediate vertical support'],
 ['Gallery columns', f"{len(gal)} columns (RECT 400/300 placeholders); 7 rear columns with no footing", 'CONCEPT_UNVERIFIED', 'Not engineered; not usable for stability'],
 ['Stair cores', 'CORE-* walls 150&ndash;200 mm, to +10.80 m, no footings', 'CONCEPT_UNVERIFIED', 'Construction unknown; candidate stability elements only if proven'],
 ['Masonry piers / walls', 'FACADE-*-BAY-*-BRICK-INFILL (0.30 m, to +12.50) + 260&times;500 piers', 'concept; render-material mass', 'Masonry design intent (source schedule); 72 kN/m self-weight needs a strip footing'],
 ['North loggia', 'EXT-N-19&hellip;21 walls start at +4.00 over a 9.5 m opening', 'existing design reference', 'No lintel / transfer beam modelled'],
])}
{fig('drawings/S-01_existing_framing_audit.png', 'Figure 4.1 Existing structural model: columns (red: no footing), concept pads, cores and roof rods.')}
<p><b>Distinction:</b> every structural object in the IFC has a correct class, profile and stable identity, but none is engineered. Classification does not establish adequacy; this study treats all of them as geometry to be verified.</p>""")

H.append(f"""<h1>5. Structural loading and design assumptions</h1>
<h2>5.1 Design standards</h2>
<p>No Zimbabwean loading or steel design standard could be confirmed from published sources. Statutory Instrument 41 of 1978 references a Standards Association of Zimbabwe concrete code, and the Model Building By-laws govern approvals, but neither sets wind or steel design rules found in this review. Consistent with R2 and regional practice, the study uses <b>SANS 10160-1/-2/-3 (actions)</b>, <b>SANS 10162-1:2011 (steel, limit states, &phi; 0.9, n = 1.34)</b>, <b>SANS 10100-1 (concrete, BS 8110 basis)</b> and <b>EN 1992-4</b> (anchorage, by analogy), with EN 1991-1-4 informative pressure coefficients. These are suitable for the next design stage <i>only if</i> the appointed ECZ-registered engineer and Harare City Council accept them. Edition and consequence class must be confirmed: CC2 is recommended for a 2,000-seat assembly building (reliability class RC2 minimum; consider RC3 for the roof given the occupancy).</p>
<h2>5.2 Loads</h2>
{tbl(['Action', 'Value', 'Basis / status'], [
 ['Roof dead (sheeting, purlins, insulation, bracing allowance)', '0.178 kN/m&sup2; plan', 'R2 load schedule (model quantities + typical supplier masses)'],
 ['Truss / steel self-weight', 'members &times; 1.05&ndash;1.08', 'calculated'],
 ['General suspended services', '0.10 kN/m&sup2;', 'R2 central; future 0.25'],
 ['Acoustic rafts, HVLS fans, ridge fans, trays', '3.4 kN/group, 1.8 kN, 4.0 kN, 0.25 kN/m', 'scenario: no products selected'],
 ['Rigging (line arrays 8 kN, lighting bars 0.40 kN/m), dynamic &times;1.2', 'imposed, &gamma; 1.6', 'scenario; future scenario as sensitivity'],
 ['Roof imposed (inaccessible)', '0.25 kN/m&sup2;', 'SANS 10160-2 category H, to verify'],
 ['Peak velocity pressure q<sub>p</sub>', '0.85 kPa (central, SLS); 1.20 kPa (upper, ULS and holding-down)', 'R2 study values (&asymp;41/49 m/s gust); <b>Harare design gust not confirmed</b>'],
 ['Wall c<sub>pe</sub>: long walls D/E; gables D/E; parallel A/B/C', '+0.72/&minus;0.37; +0.70/&minus;0.30; &minus;1.2/&minus;0.8/&minus;0.5', 'EN 1991-1-4 Table 7.1 (h/d 0.44 / 0.26; e = 29 m)'],
 ['Internal c<sub>pi</sub>', '+0.2 / &minus;0.3 (dominant opening +0.55 sensitivity)', 'large doors may open in storms: confirm management'],
 ['Roof net c<sub>p</sub>', 'R2 duo-pitch profiles, &minus;1.5 at gable lines', 'EN 1991-1-4 Table 7.4a'],
 ['Masonry walls', '72 kN/m (300 mm, 19 kN/m&sup3;, 13.3 m, less openings)', 'assumption: wall type not confirmed'],
 ['Loggia wall over the north opening', '134 / 267 / 134 kN on lines 7/8/9 north', 'assumed transfer beam (not modelled)'],
 ['Notional loads', '0.005 &times; factored gravity', 'SANS 10162-1 cl 8.7.2'],
 ['Seismic, snow, ponding', 'not governing', 'R2 assessment'],
])}
<h2>5.3 Combinations and criteria</h2>
<ul><li>ULS: 1.35G; 1.2G + 1.6Q<sub>r</sub>; 1.2G + 1.6Q<sub>rig</sub>; 1.2G + 1.3W; 0.9G + 1.3W (equipment excluded where favourable), each with notional loads.</li>
<li>SLS: 1.0W at the characteristic central pressure q<sub>p</sub> 0.85 kPa. Masonry cracking is a serviceability state, so the central basis is used, and 1.20 kPa is a sensitivity case. <b>Limit h/300 = 40.8 mm</b>, with h = 12.23 m of masonry (FFL to wall head), for column deflection <i>and</i> longitudinal eaves sway, because the masonry infill spans to the columns. R2 used h/150, which suits lightweight cladding only. Posts: L/300 relative to the chord.</li>
<li>Foundations: allowable bearing under characteristic combinations (Meyerhof effective area); uplift, overturning and sliding under EQU factors (0.9 on permanent stabilising); construction stage with walls absent at 0.75 &times; W(1.20 kPa) (assumed reduced exposure period).</li>
<li>Second order: &alpha;<sub>cr</sub> = (H/V)(h/&delta;) per frame line and wall line; first-order analysis is acceptable if &alpha;<sub>cr</sub> &ge; 10. An elastic eigen-analysis was used to find member-level modes.</li></ul>""")

H.append(f"""<h1>6. Existing structural system assessment</h1>
<p>Checking the modelled arrangement (UC 254&times;254&times;73, pinned bases) in the 3D model with a complete S1 bracing system added:</p>
{tbl(['Check', 'Result', 'Limit / capacity', 'Verdict'], [
 ['Column deflection, SLS 0.85 kPa', '&asymp;101 mm (sizing start) / 81 mm column bending alone (hand: 5wL<sup>4</sup>/384EI, w = 4.82 kN/m)', '40.8 mm (h/300, h 12.23 m)', '<span class="bad">fails &times;2.5</span>'],
 ['Column strength, ULS 1.20 kPa (zone A suction, line 1)', 'utilisation 1.09 (M &asymp; 205 kNm vs &phi;M<sub>p</sub> 317 kNm, plus minor-axis moment)', '1.00', '<span class="bad">fails</span>'],
 ['Concept pads 1.5&times;1.5&times;0.65 m', 'weight &asymp; 35 kN (+ soil &asymp; 30 kN) &times; 0.9', '55&ndash;92 kN uplift (bearing), 290&ndash;310 kN (braced bays)', '<span class="bad">fails</span>'],
 ['4 M24 pinned base', 'adequate in tension for ordinary bearings; cone breakout needs hef &ge; 300 mm', 'no design', 'concept only'],
 ['Roof bracing (4 &times; 20 mm rods)', 'capacity &asymp; 80 kN each', 'end-bay girder diagonals 110&ndash;130 kN, plus eaves girders', '<span class="bad">inadequate</span>'],
 ['Gable walls', 'no wind posts', '32.4 m &times; 12.5&ndash;16.9 m walls need vertical support', '<span class="bad">missing</span>'],
 ['Gable BC heels under uplift', 'eigen &alpha;<sub>cr</sub> 0.22 without heel restraint', '&ge; 1 (member)', '<span class="bad">restraint needed</span>'],
])}
<p>R2 had shown the UC 254 column passing with a roof wind girder (sway &asymp;80 mm against h/150). The masonry criterion, the zone-A suction on the end columns, and the gable posts are what change the conclusion. R2's lateral system allowance (&asymp;10.6 t of eaves girders, 22 pads for 80 kN) also covered only a small part of the necessary supporting structure: the complete systems here use {min(sel[x]['steel_t']['total'] for x in S):.0f}&ndash;{max(sel[x]['steel_t']['total'] for x in S):.0f} t of supporting steel.</p>""")

H.append(f"""<h1>7. Lateral stability alternatives</h1>
<p>All three systems share the <b>longitudinal</b> system, because longitudinal moment frames would put the columns into minor-axis bending and are impractical. That system comprises: six gable wind posts per gable (UB 533&times;210&times;82, placed at s = 2.7, 8.1&hellip;29.7 m so as to clear the west doors and the east glazed slot); end-bay roof girders in bays 0 and 9 across the full width; end-bay cross frames and bottom-chord bracing; bottom-chord ties at 5.4 m; eaves struts; and wall bracing in bays 1 and 5 on both sides. The north wall has no bay free of clerestories or openings, so the wall bracing is an X below the sill (+9.90 m) with knee braces inside the 1.08 m window piers.</p>
{tbl(['', 'S1 Braced frame', 'S2 Moment-resisting', 'S3 Hybrid'], [
 ['Transverse system', 'Eaves wind girders (TC plane, 5.4 m deep) &rarr; gable X-bracing', 'Each truss line a portal: fixed bases + TC/BC heel knee', 'As S1, plus fixed column bases (propped cantilevers)'],
 ['Column bases', 'pinned (4 M24)', 'fixed, strong axis', 'fixed, strong axis'],
 ['Truss bearing', 'pinned, TC heel', 'TC + BC knee (moment-capable, to design)', 'pinned, TC heel'],
 ['Gable bracing', '2 two-tier X panels per gable', 'none (posts only)', 'as S1'],
 ['Erection stability', 'columns unstable until girders are complete', 'self-stable cantilevers', 'self-stable cantilevers'],
 ['&alpha;<sub>cr</sub> transverse / longitudinal', f"{c4['S1']['alpha_cr_transverse']} / {c4['S1']['alpha_cr_longitudinal']}", f"{c4['S2']['alpha_cr_transverse']} / {c4['S2']['alpha_cr_longitudinal']}", f"{c4['S3']['alpha_cr_transverse']} / {c4['S3']['alpha_cr_longitudinal']}"],
])}
{fig('drawings/S-05_wall_and_gable_elevations.png', 'Figure 7.1 Longitudinal wall bracing (bays 1 and 5) and gable wind posts / transverse bracing.')}
<p><b>Variants considered and not adopted.</b> (i) <i>Cantilever columns without girders</i> (R2): no catalogue UC meets the deflection limit. (ii) <i>Cores as the east stability elements</i> (S3-core): this would remove the east-gable and bay-5 bracing, but it depends on unverified RC cores that have no foundations. It is held as a conditional optimisation (&sect;10.4). (iii) <i>Intermediate moment frames to shorten the girders</i>: frames stiff enough to help the girders need UC 356 columns, which costs more than the girders they replace. (iv) <i>Masonry gables as shear walls</i>: credible in Harare practice, but it needs reinforced masonry design and a steel erection sequence that does not depend on the masonry. Recorded as an optimisation.</p>
{fig('drawings/S-02_roof_framing_S1.png', 'Figure 7.2 S1 roof-plane framing.')}
{fig('drawings/S-03_roof_framing_S2.png', 'Figure 7.3 S2 roof-plane framing (no eaves girders).')}""")

H.append(f"""<h1>8. Side-column optimisation</h1>
<p>Each candidate was analysed with its complete system re-sized (Figure 8.1, Table 8.1). Column checks follow SANS 10162-1 cl 13.8 (cross-section, overall member and lateral-torsional buckling), with K<sub>x</sub> = 1.0 (S1, S2) or 0.85 (S3), minor-axis and LTB restraint at 3.3 m from the masonry ties (robustness check: no restraint over the full 13.08 m), &omega;<sub>2</sub> = 1.13, and the bearing eccentricity moment included. The governing case in all systems is longitudinal wind with zone-A suction on the end bays plus wall-bracing forces in the braced-bay columns.</p>
{fig('report/img/c01_column_sweep.png', 'Figure 8.1 Column mass against SLS deflection. Diamonds pass only if the masonry restrains the minor axis.')}
{tbl(['System', 'Column', 'kg/m', 'depth mm', 'availability (judgement)', 'util.', 'transverse SLS mm', 'base case (both SLS limits)', 'util. with no masonry restraint', 'total USD (G2/F2)'], sweep_rows, 'num')}
<p>&#9888; depth over 420 mm: projects beyond the wall/pier zone. Not recommended without architectural change.</p>
<h2>8.1 Selection logic</h2>
<p>A candidate must (a) pass strength and both SLS limits (transverse deflection and longitudinal sway, {LIM:.1f} mm), (b) remain adequate with <b>no masonry restraint at all</b>, checked over the full 13.08 m column height, and (c) fit the 420 mm wall/pier zone. Candidates deeper than 420 mm were also costed with the pier enlargement priced, and none of them passes (a) and (b). The resulting columns are UC 305&times;305&times;137 for S1, UC 356&times;368&times;153 for S2 and <b>UC 305&times;305&times;97 for S3</b>. Fixing the bases makes each column &asymp;2.4&times; stiffer against wall wind (wL<sup>4</sup>/185EI against 5wL<sup>4</sup>/384EI), which is why S3's column is 40 kg/m lighter than S1's. The existing UC 254&times;254&times;73 passes in S3 with masonry restraint (39.4 mm, utilisation 0.73) but fails without it (1.65). It is acceptable only if the masonry ties are designed as restraints.</p>
<p><b>Method limitation.</b> The stiffening loop upsizes one bracing group at a time, choosing the group with the largest strain energy per tonne under the governing SLS case. It is a heuristic. The S3 UC 254&times;254&times;89 result (failing longitudinal sway while the lighter UC 254&times;73 passes) is a path artefact of the heuristic, not a property of the section. Costs from the sizing method are uncertain by &asymp;&plusmn;5&ndash;10%, and this is carried into the Monte Carlo (&sect;15).</p>
<p><b>Gable posts:</b> UB 533&times;210&times;82 posts are adequate only with minor-axis restraint. Without it, utilisation is 2.6&ndash;4.6 over the 14&ndash;17.5 m height. All systems therefore include two rows of horizontal restraint struts per gable (CHS 88.9&times;3.2, &asymp;0.9 t), and the masonry ties must not be relied on alone.</p>
<p><b>Construction stage:</b> S2 and S3 columns are self-stable cantilevers once grouted. S1 columns need guying until the girders and gable bracing are complete (priced as temporary works).</p>""")
H.append(f"""<h1>9. Structural bracing and connection concepts</h1>
{tbl(['Member group', 'S1', 'S2', 'S3'], sec_rows)}
<p>All bracing is CHS (S355J2H), designed for compression with both diagonals active, so that the stiffness assumed in the model is the stiffness provided. Tension-only rods would be lighter but would halve the X-panel stiffness, which the deflection limits do not allow without re-analysis. <b>Purlins are not relied on as girder chords.</b> In the design runs the purlins are nominal links (0.1% of their axial stiffness), so the eaves struts and inner chords carry all the girder bending. The independent review found that an earlier draft let the purlins share it.</p>
<h2>9.1 Connection concepts (not connection designs)</h2>
<ul><li><b>Truss bearing (S1/S3):</b> concentric cap plate on the column (eliminating the modelled 145 mm offset, or designing the column for R<sub>v</sub>&times;0.145 &asymp; 18&ndash;21 kNm). <b>Preloaded (slip-resistant) M20 8.8 bolts</b>, because the bearing acts as a tie for the eaves girders in wind; slotted holes only if the bolts are preloaded after the roof dead load. Heel restraint cleats at gable lines 0 and 10.</li>
<li><b>Knee (S2):</b> TC heel and BC heel both bolted to the column flange. Knee forces &asymp;{evs['S2'].get('knee_force_kN', 0):.0f} kN horizontal at ULS. The paired-angle BC and gussets at the heel need re-design for this force (a truss change outside this study's mandate, and a further reason S2 is not recommended).</li>
<li><b>Bracing ends:</b> slotted-tube to 10&ndash;12 mm gusset, 2&ndash;4 M20 8.8 bolts, gusset welded to the column flange or the truss node plate. The wall X-bracing is made in two halves joined at a central node plate (CHS 219 cannot cross inside a 300 mm wall), placed on the inner face or in a wall chase. The lower ends connect to gussets on the column feet below FFL, inside the concrete encasement pocket.</li>
<li><b>Gable posts:</b> base pinned (4 M24), head connected to the gable truss TC node through a vertically slotted bracket (horizontal restraint, vertical freedom).</li>
<li><b>Bases:</b> Figure 9.1 and &sect;11.</li></ul>
{fig('drawings/S-06_base_and_pad_concepts.png', 'Figure 9.1 Pinned (S1) and fixed (S3) base and pad concept sections, indicative.')}""")

H.append(f"""<h1>10. Foundation optimisation</h1>
<h2>10.1 Ground conditions</h2>
<p>No geotechnical report exists for the site (project-wide search). Published Harare evidence is limited. A University of Zimbabwe study recorded intermediate- and low-plasticity clays, sodic soils and inadequate bearing in places, and recommended a minimum founding depth of 1.5 m for bearing above 100 kPa. Granite-derived residual soils in the region can be collapsible. The study therefore uses three scenarios, all <b>assumptions</b>:</p>
{tbl(['Scenario', 'Allowable bearing', 'Min. founding below FGL', 'Density', 'Base friction', 'Groundwater / heave'], [
 ['G1 favourable: dense residual granite / gravelly sand', '200 kPa', '1.0 m', '18 kN/m&sup3;', '0.45', 'none'],
 ['G2 moderate (base): stiff residual sandy clay', '150 kPa', '1.2 m', '18 kN/m&sup3;', '0.35', 'none'],
 ['G3 poor: firm intermediate-plasticity clay, possibly expansive', '100 kPa', '1.5 m', '17 kN/m&sup3;', '0.30', 'perched water at &minus;1.40 (buoyant uplift); heave &rarr; F3'],
])}
<p>Below about 75 kPa allowable, or with high swell potential, pads and strips stop being appropriate and a raft or piles would be required. That is outside this study and is identified as the decision threshold.</p>
<h2>10.2 Arrangements</h2>
<ul><li><b>F1</b> independent pads (no wall weight relied on) plus a lightly reinforced wall strip.</li>
<li><b>F2</b> pads cast integral with a continuous reinforced strip under the masonry. The wall weight over 3.0 m (216 kN) counts as permanent ballast. Construction stage checked with the walls absent.</li>
<li><b>F3</b> deeper pads with 0.35 &times; 0.75 m ground beams spanning 5.56 m that carry the wall (void formers in G3). The full bay of wall load (&asymp;400 kN) goes into the pads.</li></ul>
{fig('report/img/c03_soil_arrangement.png', 'Figure 10.1 Total supporting-system cost by soil scenario and arrangement (each system at its selected column).')}
{tbl(['System', 'Soil', 'F1', 'F2', 'F3'], soil_rows, 'num')}
<h2>10.3 Governing actions and R2 concept pads</h2>
<p>Uplift and overturning under the concurrent combinations govern, not bearing. In S3 the ordinary columns need pads of about 2.3&ndash;2.4 m square, the braced-bay columns 3.1&ndash;3.3 m, and the braced gable posts about 3 m, all 0.80 m deep. The depth is set by the anchorage: 450 mm embedment plus room to anchor the hairpins below the heads. R2's 2.0&times;2.0&times;1.0 m pinned pad suits ordinary S1 bearings. Its 3.5&times;3.5&times;0.70 m fixed-base pad is of the right order only for the braced bays. The wall ballast assumed for F2 is the weight actually present over 3.0 m at each pad, net of doors, the north loggia (no wall on the strip) and the east glazed slot. Its sensitivity to a lighter masonry (0.7 &times; 72 kN/m) is given in &sect;15.</p>
{fig('report/img/c06_base_reactions.png', 'Figure 10.2 S3 base reactions along side A.')}
{tbl(['Base', 'N<sub>c</sub> kN', 'N<sub>t</sub> kN', 'H<sub>y</sub> kN', 'H<sub>x</sub> kN', 'M kNm', 'Base plate', 'Holding-down', 'Pad B&times;L&times;D m', 'A<sub>s</sub> bot mm&sup2;/m', 'A<sub>s</sub> top mm&sup2;/m'], found_rows, 'num')}
<h2>10.4 Integrated framing (gallery, cores, office)</h2>
<p><b>Gallery:</b> its slabs (+4.4 to +7.85 m) could restrain columns 7&ndash;9 at mid-height, but they do not reach the eaves, so they cannot shorten the girders. Using them would add lateral load to undesigned rakers and RC columns that have no footings. Not used. <b>Cores:</b> their walls stop at +10.80 m, 0.10 m below the truss bottom chord, and the core end walls (6.2 m long in x) cross under trusses 10 and 11. As designed RC shear walls with foundations they could take the east transverse and longitudinal reactions. That would remove the east gable bracing and the bay-5 wall bracing (&asymp;3&ndash;4 t, USD 10&ndash;15k) but add core reinforcement and footings. Conditional. <b>Office wing:</b> its +4.42 m roof deck could prop the west gable posts, reducing the post size, but only if the office frame is braced for it. Not assumed.</p>
{fig('drawings/S-07_foundation_concept_plan.png', 'Figure 10.3 Foundation concept plan, recommended S3, F2, G2 (indicative).')}""")

H.append(f"""<h1>11. Foundation reinforcement and anchorage considerations</h1>
<ul><li><b>Holding-down design uses concurrent actions.</b> The tension row is designed for the worst <i>concurrent</i> (N, M) pair from each ULS combination: T = (M &minus; N z/2)/z with compression, and T = M/z + |N|/2 with uplift. The independent review showed that combining the envelope maximum compression with the maximum moment under-estimated T by about 60% at the governing base. The S3 fixed bases need 6&ndash;8 M24 8.8 cast-in bolts with anchor plates (4 at the gable lines), hef 450 mm, 30 mm stiffened plates on 40&ndash;50 mm grout.</li>
<li><b>Concrete breakout:</b> without anchor reinforcement the cone utilisation exceeds 1 at most fixed bases and at the braced pinned bases. Designed supplementary reinforcement is therefore mandatory: hairpins around the tension bolts, anchored beyond the cone in both directions. That is why the pads are 0.80 m deep, and it is an inspection hold point. Four M24 bolts are not, by themselves, proof of anchorage.</li>
<li><b>Pads:</b> bottom mesh is the 0.13% minimum or more (&asymp;1,040 mm&sup2;/m at 0.80 m, e.g. Y16 @ 175). Top mesh is provided where uplift or base moment causes hogging. Punching includes moment transfer (V<sub>eff</sub> = V(1 + 1.5M/Vx), BS 8110 3.7.6.2), and one-way shear is checked to SANS 10100. The upward pull-out of the anchor group is resisted by the designed hairpins, not by plain concrete.</li>
<li><b>Wall strip (F2):</b> 0.60 &times; 0.45 m with &asymp;75 kg/m&sup3;, continuous top and bottom bars lapped into the pads so that the engaged wall acts with each pad.</li>
<li><b>Shear transfer and sliding:</b> two mechanisms, priced separately. (i) Base plate to pad: friction 0.2N under the concurrent compression only; where any uplift combination carries shear, a stub shear key in a grout pocket is used. Bolts in shear through grout are not relied on. (ii) Pad to soil: where the concurrent horizontal force exceeds &mu;N, a downstand key or passive resistance is provided (priced per pad).</li>
<li><b>Fixity:</b> the analysis assumes rigid base fixity. A rotational-spring sensitivity, K = k<sub>s</sub>LB<sup>3</sup>/12 halved for partial contact (&asymp;50 MNm/rad for G2, &asymp;20 MNm/rad for G3), is reported in &sect;15. The subgrade modulus must come from the site investigation.</li>
<li><b>Buoyancy:</b> in G3 a design water level of &minus;1.00 m (0.40 m above the assumed perched level) is applied to all pads founded below it. The uplift resistance uses submerged densities.</li>
<li><b>Durability:</b> steel below FFL encased in C25/30. Holding-down assemblies hot-dip galvanised.</li></ul>""")
H.append(f"""<h1>12. Structural performance comparison</h1>
{tbl(['Criterion', 'S1 Braced', 'S2 Moment', 'S3 Hybrid'], [
 ['Column', sel['S1']['column'], sel['S2']['column'], sel['S3']['column']],
 ['Max column utilisation (ULS, masonry restraint 3.3 m)', c4['S1']['column_util_max'], c4['S2']['column_util_max'], c4['S3']['column_util_max']],
 ['Transverse column deflection SLS 0.85 kPa (limit 40.8 mm)', c4['S1']['defl_y_SLS_q085_mm'], c4['S2']['defl_y_SLS_q085_mm'], c4['S3']['defl_y_SLS_q085_mm']],
 ['Column utilisation with no masonry restraint (13.08 m)', c4['S1']['column_util_no_masonry_restraint'], c4['S2']['column_util_no_masonry_restraint'], c4['S3']['column_util_no_masonry_restraint']],
 ['Column deflection at 1.20 kPa', c4['S1']['defl_y_SLS_q120_mm'], c4['S2']['defl_y_SLS_q120_mm'], c4['S3']['defl_y_SLS_q120_mm']],
 ['Longitudinal eaves sway SLS 0.85 kPa (limit 40.8 mm)', c4['S1']['eaves_x_SLS_q085_mm'], c4['S2']['eaves_x_SLS_q085_mm'], c4['S3']['eaves_x_SLS_q085_mm']],
 ['Longitudinal eaves sway at 1.20 kPa (same design)', c4['S1']['eaves_x_SLS_q120_mm'], c4['S2']['eaves_x_SLS_q120_mm'], c4['S3']['eaves_x_SLS_q120_mm']],
 ['&alpha;<sub>cr</sub> transverse / longitudinal', f"{c4['S1']['alpha_cr_transverse']} / {c4['S1']['alpha_cr_longitudinal']}", f"{c4['S2']['alpha_cr_transverse']} / {c4['S2']['alpha_cr_longitudinal']}", f"{c4['S3']['alpha_cr_transverse']} / {c4['S3']['alpha_cr_longitudinal']}"],
 ['Max base moment kNm', '0', f"{env_range('column','M_base_ULS_kNm','S2'):.0f}", f"{env_range('column','M_base_ULS_kNm','S3'):.0f}"],
 ['Max column uplift kN', f"{env_range('column','N_uplift_ULS_kN','S1'):.0f}", f"{env_range('column','N_uplift_ULS_kN','S2'):.0f}", f"{env_range('column','N_uplift_ULS_kN','S3'):.0f}"],
 ['Gable-truss TC axial utilisation (collector)', '&asymp;0.92', '&asymp;0.65', '&asymp;0.84'],
 ['Redundancy', 'single load path per direction', 'every line a frame (high)', 'girder + cantilever columns in parallel'],
 ['Erection stability', 'needs temporary guys', 'self-stable', 'self-stable'],
])}
<p>All systems have &alpha;<sub>cr</sub> &gt; 10, so first-order global analysis is adequate. Two member-level eigen-modes are not global and are not covered by this study's member checks. The gable bottom chord between ties (&alpha; &asymp; 2.0) belongs to the Option B truss design and is reported to it. The braced gable posts about the minor axis (&asymp; 1.3&ndash;1.6) are why the posts get designed restraint struts. Longitudinal sway is at the limit for all systems by design (the wall bracing is stiffened until it passes). At 1.20 kPa every system needs heavier wall bracing; this is costed in the 1.20 kPa sensitivity.</p>""")

H.append(f"""<h1>13. Material quantity assessment</h1>
{tbl(['System', 'Column', 'Columns t', 'Posts t', 'Girders + bracing t', 'Plates t', 'Total steel t', 'Concrete m&sup3;', 'Rebar t', 'Excavation m&sup3;', 'HD bolts', 'Struct. bolts'], q_rows, 'num')}
{fig('report/img/c05_quantities.png', 'Figure 13.1 Principal quantities, G2/F2.')}
<p><b>Basis:</b> steel = member length &times; catalogue kg/m (calculated). Connections = 3 kg + 0.15 &times; kg/m per member end, plus bearing, base and post plates (allowance). Bolts = 2&ndash;4 per member end (preliminary). Footings, blinding, formwork, excavation (0.30 m working space, formation to FGL +0.10), backfill and disposal (bulking 1.25) = explicit geometry per pad (calculated from preliminary sizes). Reinforcement = designed A<sub>s</sub> with 10% laps, plus 60 kg/m&sup3; in encasement and 35&ndash;130 kg/m&sup3; in the wall strip and ground beams (assumption-dependent). <b>Not reliably quantifiable yet:</b> bar schedules, masonry-tie restraints, transfer beam at the loggia, core and gallery foundations, dewatering. Quantities do not double-count: the wall strip is measured only between pads (pad lengths along the wall are deducted).</p>""")

H.append(f"""<h1>14. Construction cost comparison</h1>
<p>USD, excl. VAT, Harare 2026, central rates (deliverable F gives low, central and high, with live formulas). The Option B trusses, purlins and equipment steel are <b>common</b> and excluded (&asymp;USD 195k from R2, context only). Rates are attributable where possible (R2 Harare steel lists, Zimbabwe crane hire, a January 2026 Harare cement guide at USD 11&ndash;12.50 per 50 kg bag). Ready-mix, rebar per tonne, CHS and holding-down assemblies are <b>inferred</b>: no supplier quotation is included.</p>
{tbl(['Cost component (USD)', 'S1 Braced', 'S2 Moment', 'S3 Hybrid'], brief_cost_rows(), 'num')}
{fig('report/img/c02_cost_stack.png', 'Figure 14.1 Cost by component.')}
<p>S3's columns are 30% lighter than S1's and avoid S2's imported sections, but its fixed-base foundations cost &asymp;USD {usd(cat_cost(e3, ['Foundations (columns/posts)']) - cat_cost(e1, ['Foundations (columns/posts)']))} more than S1's. The net difference ({k(e1['total'] - e3['total'])}, {pct(e1['total'], e3['total']):.1f}%) is <b>smaller than the estimating uncertainty</b>. The headline figures are therefore the P50 values (&sect;15), and the choice between S1 and S3 rests on ground conditions and non-cost factors. Contingency is 10% (design development, no SI) plus scheme risk: S2 +4% (imported sections, knee re-design), S3 +2% (fixed-base anchorage). Erection productivity: 6 columns, 4 posts and 15 bracing pieces per crane day, plus 2 days of girder assembly.</p>""")

H.append(f"""<h1>15. Geotechnical and cost sensitivity</h1>
{fig('report/img/c04_montecarlo.png', 'Figure 15.1 Monte Carlo: correlated rate groups and independent quantity uncertainty per scheme.')}
<h2>15.1 Structural sensitivity (each case fully re-sized)</h2>
{tbl(['Case', 'S1 ' + sel['S1']['column'], 'S2 ' + sel['S2']['column'], 'S3 ' + sel['S3']['column']], sens_rows)}
<p style='font-size:8pt'>Cells: verdict &middot; column utilisation &middot; transverse / longitudinal SLS sway (mm). The bracing is re-sized in each case. The cpi &minus;1.08 case is factored at 1.3, which is conservative if door management makes it an accidental situation (&gamma; 1.0). Base-fixity cases apply to the fixed-base systems S2 and S3 only.</p>
<ul><li><b>Monte Carlo:</b> correlated rate groups, plus independent quantity factors per scheme (steel 0.92&ndash;1.00&ndash;1.10 for the sizing method; foundations 0.85&ndash;1.00&ndash;1.25 for the missing SI). P50: S1 {k(mc['S1']['p50'])}, S2 {k(mc['S2']['p50'])}, S3 {k(mc['S3']['p50'])}. P(S3 &lt; S1) = {PW.get('P(S3<S1)', 0):.2f}; P(S3 &lt; S2) = {PW.get('P(S3<S2)', 0):.2f}. <b>S3 against S1 is not decisive on cost alone.</b></li>
<li><b>Soil (decision threshold):</b> cheapest system G1 {CHEAP['G1']}, G2 {CHEAP['G2']}, G3 {CHEAP['G3']}. In G3 the buoyant, softer ground penalises the large fixed-base pads more than the pinned S1 pads, and S1 becomes cheapest. The SI therefore decides between S1 and S3. Below about 75 kPa allowable, or with high swell potential, a raft or piles would be needed (outside this study).</li>
<li><b>Masonry density 0.7 &times; 72 kN/m (hollow / lighter units):</b> {'; '.join(f"{x}: " + (f"USD {k(v['total'])}" if v.get('ok') else 'no pad solution') for x, v in WD.items())} (G2/F2). There is almost no effect, because the construction stage (walls absent) already governs most pads.</li>
<li><b>Wind, opening and fixity cases:</b> see the table above (each case re-sized for the selected column). <b>Structural robustness favours S3.</b> It is the only system that passes partial base fixity, both dominant-opening cases, and transverse SLS at 1.20 kPa. S1 fails both opening cases and transverse SLS at 1.20 kPa. S2 depends strongly on base fixity (55&ndash;75 mm with springs) and fails transverse SLS at 1.20 kPa.</li>
<li><b>SLS at 1.20 kPa, longitudinal:</b> all three systems exceed the limit longitudinally. The wall bracing in bays 1 and 5, which is common to all systems, would need a third braced bay per side or heavier members, an estimated +1.5&ndash;2.5 t and USD 6&ndash;10k for every system. This does not change the ranking. It must be resolved once the design wind is confirmed.</li>
<li><b>Decision threshold, wall construction:</b> with lightweight cladding (h/150) the masonry stiffness criterion no longer governs, and the lightest passing columns are those shown in the "Lightweight cladding" row. The wall type must be fixed before the stability system is frozen.</li></ul>""")
H.append(f"""<h1>16. Architectural coordination</h1>
{tbl(['Element', 'Impact', 'Mitigation / status'], [
 ['UC 305&times;305&times;97 columns (regional stock, study judgement)', '308&ndash;315 mm deep, within the 420 mm wall + pier zone at each grid; 8&ndash;15 mm beyond the 300 mm wall face if centred', 'Centre the column in the pier zone; adjust the pier cladding. No change to the footprint'],
 ['Wall bracing bays 1 and 5', 'X below the clerestory plus knees in the piers. Visible on the inner face unless built into the masonry', 'Build in with compressible packing, or line internally. Clerestories, doors and circulation unaffected'],
 ['Gable posts (UB 533)', '533 mm deep, outside the truss plane; fit within the gable wall build-up only if the wall zone is &ge; 550 mm', 'West: behind the stage backdrop. East: in the stair cores. Wall thickening or exposed posts to agree'],
 ['Gable bracing', 'West panels behind the stage screens (s 8.1&ndash;13.5, 18.9&ndash;24.3); east panels inside the stair cores', 'Avoids doors and the east glazed slot; screens to be coordinated'],
 ['Eaves wind girders', 'In the roof plane within 5.4 m of each eave, above the ceiling/acoustic zone', 'Clear of catwalk zones; coordinate with the ridge fans (rows 11/13 unaffected)'],
 ['Pads 2.5&ndash;3.6 m and wall strip', 'Below ground. Pads extend &asymp;1.2&ndash;1.7 m inside the wall line under the raked floor and external paving', 'Coordinate with drainage, the hall slab edge and services entries'],
 ['Loggia transfer beam', 'Needed at +4.00 between lines 7&ndash;9 north', 'Architectural depth to agree (not in the model)'],
 ['Glazed elevations, entrances, sightlines, gallery, office wing', 'No change', '&ndash;'],
])}""")

H.append(f"""<h1>17. Recommended structural solution</h1>
<div class='box'><b>Base case (G1/G2 ground, masonry walls): S3 Hybrid on F2 foundations</b> (indicative member sizes, not for fabrication):
<ul><li>22 columns {sel['S3']['column']} S355, strong axis normal to the wall, fixed bases (stiffened 30 mm plate, 4&ndash;8 M24 8.8 with anchor plates, hef 450 mm, designed hairpins), propped at the eaves.</li>
<li>Eaves wind girders both sides, TC plane, 5.4 m deep: diagonals {evs['S3']['steel']['EGD']['section']}, inner chord {evs['S3']['steel']['EGC']['section']}, eaves struts {evs['S3']['steel']['EAV']['section']} (purlins not relied on).</li>
<li>End-bay roof girders {evs['S3']['steel']['RBD']['section']}; cross frames {evs['S3']['steel']['XF']['section']}; bottom-chord bracing {evs['S3']['steel']['BCB']['section']}; ties {evs['S3']['steel']['BCT']['section']} @ 5.4 m; heel restraint at the gable trusses.</li>
<li>12 gable posts {evs['S3']['steel']['POST']['section']} with two rows of restraint struts per gable; gable bracing {evs['S3']['steel']['GBX']['section']} (two-tier X, 2 panels per gable).</li>
<li>Wall bracing bays 1 and 5: X {evs['S3']['steel']['WBX']['section']} below +9.90 (in two halves), knees {evs['S3']['steel']['WBK']['section']}, sill {evs['S3']['steel']['WBS']['section']}.</li>
<li>Pads &asymp;2.3&ndash;3.3 m &times; 0.80 m C25/30 integral with a 0.60 &times; 0.45 m reinforced wall strip (G2). Re-size after the site investigation.</li>
<li>Supporting steel &asymp;{sel['S3']['steel_t']['total']:.0f} t; concrete &asymp;{sel['S3']['found_q']['concrete_m3']+sel['S3']['wall_q']['concrete_m3']:.0f} m&sup3;; reinforcement &asymp;{(sel['S3']['found_q']['rebar_kg']+sel['S3']['wall_q']['rebar_kg']+sel['S3']['hd']['anchor_reinf_kg'])/1000:.1f} t; cost P50 &asymp;USD {k(mc['S3']['p50'])} (central {k(e3['total'])}).</li></ul>
<b>Alternative to adopt if the SI finds G3-type ground (or if fixed-base anchorage is unattractive to the contractor): S1 Braced</b>, {sel['S1']['column']} on pinned 4 &times; M24 bases, the same roof girders and bracing, and smaller pads. P50 &asymp;USD {k(mc['S1']['p50'])}. S2 is not recommended in any scenario.</div>
<h2>17.1 Approval gates</h2>
<ol><li><b>G-A (before design freeze):</b> confirm masonry walls (if they are lightweight cladding, re-run); confirm the code set and the Harare design wind; agree the visibility of the wall bracing.</li>
<li><b>G-B (before the stability system is fixed):</b> site investigation. Confirm q<sub>a</sub>, groundwater, swell/collapse potential and subgrade modulus. G1/G2 &rarr; S3 + F2. G3 &rarr; S1 + F2/F3, or S3 + F3 if the swell potential requires ground beams anyway.</li>
<li><b>G-C (before BIM implementation):</b> review of this study by the appointed ECZ engineer, then a controlled IFC update per deliverable J.</li></ol>""")
H.append(f"""<h1>18. Outstanding engineering requirements</h1>
{tbl(['ID', 'Discipline', 'Issue', 'L', 'I', 'Action / information', 'Gate'], risk_rows)}""")

H.append(f"""<h1>19. Conclusions</h1>
<ol><li>The existing columns, bases, footings and bracing are concept geometry. They do not form a complete or adequate load path for the Option B roof and the masonry walls.</li>
<li>With 12.23 m of masonry spanning to the columns, the column criterion is stiffness (h/300 = {LIM:.1f} mm), in both directions, not strength. That moves the optimum away from R2's pinned UC 254 columns.</li>
<li>All three stability systems can be made to work. S2 (moment frames) is the most expensive in every scenario. S3 (hybrid) and S1 (braced) are within the estimating uncertainty of each other ({pct(e1['total'], e3['total']):.1f}% at G2). S3 is preferred on firm ground for its lighter columns, erection self-stability and transverse stiffness reserve. S1 is preferred on poor or wet ground, where its smaller pinned-base pads are cheaper.</li>
<li>Foundations are governed by uplift and overturning under concurrent actions at the braced bays, the gable posts and the fixed bases. Anchorage, not bending, sets the pad depth. Integrating the pads with a reinforced wall strip is the cheapest arrangement in every case.</li>
<li>The ground and the wall construction are the assumptions that can change the recommendation. Both must be confirmed before the stability system is frozen.</li>
<li>The Option B truss remains appropriate. Its gable top chords, its bottom-chord heels and the bearing bolts need attention in its own detailed design.</li>
<li>The independent review changed the study materially: concurrent anchorage actions, purlin-independent girders, buoyancy, anchorage-led pad depth, a no-restraint robustness test, post restraint and slower erection raised all totals by about 20%, and turned a clear S3 preference into a conditional one (deliverable I).</li></ol>""")
H.append(f"""<h1>20. Technical appendices</h1>
<h2>A. Solver verification (scripts/hand_checks.py)</h2>
{tbl(['Case', 'Model', 'Closed form', 'Ratio'], ver_rows, 'num')}
<h2>B. Independent hand checks of key results</h2>
{tbl(['Quantity', 'Hand calculation', 'Model', 'Agreement'], [
 ['UC 254&times;73 pinned column deflection, q 0.85', '5wL<sup>4</sup>/384EI, w = 0.85&times;1.02&times;5.56 = 4.82 kN/m, L 13.08 &rarr; 80.5 mm', '81 mm column + &asymp;20 mm girder = 101 mm', 'consistent'],
 ['UC 305&times;97 fixed-base propped deflection', 'wL<sup>4</sup>/185EI = 17.1 mm, + girder &asymp;11 mm', '28.7 mm', 'consistent'],
 ['S3 base moment, ULS 1.20', 'wL<sup>2</sup>/8, w = 1.3&times;1.2&times;1.02&times;5.56 = 8.85 kN/m &rarr; 189 kNm (+ zone A, eccentricity)', '198&ndash;218 kNm', 'consistent'],
 ['Eaves girder (S1), both walls shared', 'net 1.09 q<sub>p</sub>; ULS 5.6 kN/m per girder; M = 2,150 kNm; chord 398 kN (simple span, columns not sharing)', 'R2 2,135 kNm / 395 kN; design model with purlins as nominal links: see D (columns and gable bracing share part of the load)', 'consistent'],
 ['Bearing uplift, ULS 1.20, near-edge line (c<sub>p,net</sub> &minus;0.8)', '(&minus;0.8&times;1.2&times;1.3 + 0.9&times;0.36) &times; 90 m&sup2; &asymp; &minus;83 kN; plus windward-ridge zones in transverse wind', '&minus;92 kN (lines 1&ndash;2)', 'consistent within 10%'],
 ['Braced-bay uplift', 'H &asymp; 200 kN &times; 13.1 m / 5.56 m &asymp; 470 kN gross, less gravity', '285&ndash;313 kN', 'order of magnitude'],
])}
<h2>C. Model limitations</h2>
<ul><li>Linear elastic 3D frame, small displacements. Webs and bracing pin-ended. Joint flexibility, bolt slip and gusset eccentricities ignored. Masonry not modelled structurally (loads only; minor-axis restraint assumed in the checks).</li>
<li>Member checks are in the form of SANS 10162-1, with simplified LTB and the &beta;-factor. Purlins are modelled as axial struts only. Truss member design is not re-checked (R2's scope), except for the collector forces reported.</li>
<li>Second order by &alpha;<sub>cr</sub> &ge; 10 (no amplification required). The eigen-analysis is used diagnostically.</li>
<li>Results are reliable for comparing and ranking systems and for preliminary sizing. They are not a compliance check. An independent analysis in recognised software is required at detailed design.</li></ul>
<h2>D. Sources</h2>
<ul><li>Roof Structure Options Appraisal R2 and its data (<code>F-site-A-2000-astra-v2/studies/roof-truss-selection</code>, read-only).</li>
<li>Southgate BIM audit reports: bim_quality_audit.md, migration_completeness.md, independent_final_review.md (O-04, O-06), review_response.md, outstanding_work.csv.</li>
<li>Harare building materials guide (cement USD 11&ndash;12.50/bag), urbanedgezw.blogspot.com, Jan 2026. UZ structural cracks case study (ir.uz.ac.zw/handle/10646/3566). Zimbabwe soil classification (CCARDESA). Trade-barriers listing of SAZ concrete code / SI 41 of 1978. Herald: Model Building By-laws.</li>
<li>SANS 10160 parts 1&ndash;3, SANS 10162-1:2011, SANS 10100-1, EN 1991-1-4, EN 1992-4, EN 1993-1-1 (by reference; not reproduced).</li></ul>
<h2>E. Independent review</h2>
<p>A separate AI reviewer, given the code and outputs but not the author's reasoning, raised 16 objections (2 critical, 8 major). All were addressed by changing the calculations, not the text; the record is deliverable I (<code>review/I_independent_review_record.md</code>). This is an AI-assisted internal challenge, <b>not</b> independent professional engineering certification.</p>""")

H.append("</body></html>")
out = f"{ROOT}/report/Option_B_Support_Structure_Study.html"
open(out, "w", encoding="utf-8").write("\n".join(H))
pdf = f"{ROOT}/report/Southgate_Option_B_Support_Structure_Lateral_Stability_Foundation_Study.pdf"
edge = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
subprocess.run([edge, "--headless", "--disable-gpu", "--no-pdf-header-footer", f"--print-to-pdf={pdf}", "file:///" + out.replace("\\", "/")], check=True, timeout=180)
print("written", pdf, os.path.getsize(pdf))
