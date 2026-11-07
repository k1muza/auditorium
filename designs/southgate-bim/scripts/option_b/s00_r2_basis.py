"""Extract the Option B design basis from the R2 appraisal (READ-ONLY on the study folder).

Writes config/option_b/r2_basis.json: per analysed truss line the member-by-member sections and the
envelope member forces (central scenario, equipment at drawn positions = R2 quantity basis), plus R2's
reported per-truss take-off and truss-set mass, with sha256 of every source file.
Usage: .venv/Scripts/python -I scripts/option_b/s00_r2_basis.py
"""
import hashlib, json, math, os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
STUDY = os.path.normpath(os.path.join(ROOT, "..", "F-site-A-2000-astra-v2", "studies", "roof-truss-selection"))
SRC = {k: os.path.join(STUDY, p) for k, p in {
    "study_results": "work/study_results.json", "metrics": "work/metrics.json", "cost_summary": "work/cost_summary.json",
    "options_and_loads": "scripts/options_and_loads.py", "metrics_script": "scripts/metrics.py", "cost_model": "scripts/cost_model.py",
    "truss_engine": "scripts/truss_engine.py", "report_pdf": "Roof_Structure_Options_Appraisal_R2.pdf",
    "revision_log": "R2_revision_log.md", "truss_options": "data/truss_options.csv"}.items()}
sha = {k: hashlib.sha256(open(p, "rb").read()).hexdigest() for k, p in SRC.items()}
R = json.load(open(SRC["study_results"]))
M = json.load(open(SRC["metrics"]))["B"]
C = json.load(open(SRC["cost_summary"]))

lines = {}
for r in R["runs"]:
    if r["option"] != "B" or r["scenario"] != "central" or r["node_coordinated"] or "checks" not in r:
        continue
    g = r["geometry"]; N = g["nodes"]; tags = g["tags"]
    webs, chords = [], {"TC": set(), "BC": set()}
    for c in r["checks"]:
        n1, n2, grp, kind = g["members"][c["i"]]
        (x1, z1), (x2, z2) = N[n1], N[n2]
        if kind == "bar":
            # web member keyed by its end panel points (s rounded to the 2.70 m grid); 'from' = bottom/top tag
            lo, hi = (n1, n2) if x1 <= x2 else (n2, n1)
            if abs(x1 - x2) < 1e-6:      # vertical: bottom node first
                lo, hi = (n1, n2) if tags[str(n1)] == "B" else (n2, n1)
            webs.append(dict(group=grp, section=c["sec"], s1=round(N[lo][0], 3), end1=tags[str(lo)], s2=round(N[hi][0], 3),
                             end2=tags[str(hi)], Nc_kN=round(c["Nc"], 1), Nt_kN=round(c["Nt"], 1), util=c["util"], lam=c["lam"]))
        else:
            chords[grp].add(c["sec"])
    # chord envelope forces per chord group (max over elements)
    cf = {}
    for c in r["checks"]:
        n1, n2, grp, kind = g["members"][c["i"]]
        if kind == "beam":
            d = cf.setdefault(grp, {"Nc_kN": 0.0, "Nt_kN": 0.0, "util_max": 0.0})
            d["Nc_kN"] = max(d["Nc_kN"], round(c["Nc"], 1)); d["Nt_kN"] = max(d["Nt_kN"], round(c["Nt"], 1)); d["util_max"] = max(d["util_max"], c["util"])
    lines[str(r["line"])] = dict(line_name=r["line_name"], mass_members_kg=r["mass_kg"], max_util=r["max_util"],
                                 sections=r["sections"], chord_sections={k: sorted(v) for k, v in chords.items()},
                                 chord_forces=cf, webs=sorted(webs, key=lambda w: (w["s1"], w["s2"], w["group"])),
                                 reactions=r["reactions"], f1_hz=r["f1_hz"])
future = {str(r["line"]): r["sections"] for r in R["runs"] if r["option"] == "B" and r["scenario"] == "future"}
basis = dict(
    title="Southgate Worship Center - Roof Structure Options Appraisal, Revision R2, 7 November 2026 - Option B basis",
    status="PRELIMINARY_ESTIMATE - preliminary options appraisal, not a fabrication design; member sizes indicative (R2 s.1, 'must not be used for fabrication')",
    sources={k: {"path": os.path.relpath(p, ROOT).replace("\\", "/"), "sha256": sha[k]} for k, p in SRC.items()},
    geometry=dict(span_m=32.4, bearing_y_m=[0.30, 32.70], pitch_deg=15.0, bays=12, panel_m=2.70, bottom_chord_m=10.900,
                  top_chord_line_at_bearing_m=12.380, ridge_line_m=12.380 + math.tan(math.radians(15)) * 16.2,
                  truss_x_m=[round(3.25 + 5.56 * i, 3) for i in range(11)], spacing_m=5.56,
                  web_pattern="Warren with verticals; diagonals alternate B(k)->T(k+1) for even k in each half (R2 options_and_loads.build_panelled)",
                  note="R2 analysis line 12.380 was the existing model's member axis (leg centre of 2L100), purlins seat on it"),
    analysed_lines=lines,
    line_assignment={"0": "0", "10": "0", "1": "2", "2": "2", **{str(i): "4" for i in range(3, 10)}},
    line_assignment_basis=("R2 cost_model.truss_set_mass: 2 x gable(line 0) + 2 x max(line 1, line 2) + 7 x typical(line 4); "
                           "R2 analysed lines 0, 1, 2, 4 only (symmetry). Lines 1-2 adopt the heavier of lines 1/2 (= line 2)."),
    future_scenario_sections=future,
    r2_takeoff_per_typical_truss=dict(gusset_plates=M["gusset_plates"], bolts=M["bolts"], packers=M["packers"], web_members=M["web_members"],
                                      chord_pieces=M["chord_pieces"], angle_pieces=M["angle_or_tube_pieces"], mass_members_kg=M["mass_typical_kg"],
                                      connection_kg=M["connection_kg"], mass_with_connections_kg=M["mass_with_conn_kg"],
                                      connection_ratio=M["connection_ratio"], member_length_m=M["member_length_per_truss_m"],
                                      rule=("bolts = sum over webs 2*max(2,ceil(F/100 kN)) + 8 per chord splice (chord pieces - 2) + 4 per gusset "
                                            "+ 1 per packer; packers = round(sum(member length)/1.2 + n_webs); conn kg = 15.3/gusset + 1.2/packer "
                                            "+ 8/splice + 0.35/bolt (R2 metrics.py)")),
    r2_truss_set_t=C.get("tonnage", {}).get("B", {}).get("primary_t") if isinstance(C.get("tonnage"), dict) else None,
    working_assumptions=dict(bolt="M20 grade 8.8, design resistance 100 kN per bolt (R2 metrics.py BOLT_KN - study assumption)",
                             gusset_thickness_mm=10, gap_between_angles_mm=10, steel_grade="S355JR (as recorded in the model; R2 truss_engine FY 355, sensitivity 275)",
                             chord_stock_m=6.0, coating="two-coat paint (R2 cost basis); hot-dip galvanising to be decided at design stage (R2 s.11.3)"))
if basis["r2_truss_set_t"] is None:
    basis["r2_truss_set_t"] = C["summary"]["B"]["tonnage"]["primary_t"]; basis["r2_tonnage_B"] = C["summary"]["B"]["tonnage"]
out = os.path.join(ROOT, "config", "option_b", "r2_basis.json")
json.dump(basis, open(out, "w"), indent=1)
print("wrote", out, "lines", sorted(lines), "set t", basis["r2_truss_set_t"])
