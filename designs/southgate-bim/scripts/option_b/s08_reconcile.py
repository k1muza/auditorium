"""Stage 6/7 - quantity reconciliation: model (IFC schedules) vs independent hand calculation vs R2.

  .venv/Scripts/python -I scripts/option_b/s08_reconcile.py <schedules dir> <engine dir> <outdir>

Hand calculation (closed form, no engine/IFC code): node coordinates from the R2 geometry rules,
member setting-out lengths, 2 x catalogue kg/m x length. It is run twice:
  H1  R2 geometry (top-chord centroid line on the 12.380 plane)   -> must reproduce R2's own member masses
  H2  DEV-01 geometry (top of steel 10.5 mm below the plane, centroid e/cos15 lower)
The model's cut-length mass then isolates the effect of web set-backs, heel extensions and splice gaps.
"""
import csv, json, math, sys
from collections import defaultdict
from pathlib import Path

sched, eng, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
out.mkdir(parents=True, exist_ok=True)
ROOT = Path(__file__).resolve().parents[2]
basis = json.load(open(ROOT / "config/option_b/r2_basis.json"))
KG = {"L60x60x6": 5.42, "L70x70x6": 6.38, "L75x75x6": 6.85, "L80x80x8": 9.63, "L90x90x8": 10.9, "L100x100x8": 12.2}
E = {"L80x80x8": 0.0226, "L90x90x8": 0.0250}
T15, C15 = math.tan(math.radians(15)), math.cos(math.radians(15))


def hand(line_key, dev01):
    L = basis["analysed_lines"][line_key]
    tc, bc = L["chord_sections"]["TC"][0][1:], L["chord_sections"]["BC"][0][1:]
    off = (-0.0105 / C15 - E[tc] / C15) if dev01 else 0.0
    zt = lambda s: 12.38 + T15 * min(s, 32.4 - s) + off
    m = 0.0
    lengths = 0.0
    for w in L["webs"]:
        z1 = zt(w["s1"]) if w["end1"] == "T" else 10.9
        z2 = zt(w["s2"]) if w["end2"] == "T" else 10.9
        Lw = math.hypot(w["s2"] - w["s1"], z2 - z1)
        m += 2 * KG[w["section"][1:]] * Lw
        lengths += Lw
    Ltc, Lbc = 32.4 / C15, 32.4
    m += 2 * KG[tc] * Ltc + 2 * KG[bc] * Lbc
    return m, lengths + Ltc + Lbc


rows = []
R2m = {k: v["mass_members_kg"] for k, v in basis["analysed_lines"].items()}
for k in ("0", "2", "4", "1"):
    h1, l1 = hand(k, False)
    h2, l2 = hand(k, True)
    rows.append({"R2_line": k, "R2_member_mass_kg": R2m[k], "H1_R2_geometry_kg": round(h1, 1), "H1_minus_R2_kg": round(h1 - R2m[k], 1),
                 "H1_setting_out_length_m": round(l1, 2), "H2_DEV01_geometry_kg": round(h2, 1), "DEV01_effect_kg": round(h2 - h1, 1),
                 "H2_setting_out_length_m": round(l2, 2)})
def w(n, R):
    cols = list(dict.fromkeys(k for r in R for k in r))
    with open(out / n, "w", newline="", encoding="utf-8") as fh:
        d = csv.DictWriter(fh, fieldnames=cols); d.writeheader(); d.writerows(R)
w("hand_calculation_member_mass.csv", rows)
H = {r["R2_line"]: r for r in rows}

# model per truss (IFC schedules)
tr = list(csv.DictReader(open(sched / "truss_assembly_quantity_schedule.csv", encoding="utf-8")))
per = [r for r in tr if r["Truss"].startswith("SOUTHGATE-TRUSS-")]
allr = [r for r in tr if r["Truss"] == "ALL 11 TRUSSES"][0]
line_sec = {"0": "0", "10": "0", "1": "2", "2": "2", **{str(i): "4" for i in range(3, 10)}}
rec = []
for r in per:
    ln = str(int(float(r["Line"])))
    k = line_sec[ln]
    eng_s = json.load(open(eng / f"{r['Truss'].split('-')[-1]}.json"))["summary"]
    rec.append({"Truss": r["Truss"], "Line": ln, "Type": r["TrussType"], "R2_member_kg": R2m[k], "Hand_R2geom_kg": H[k]["H1_R2_geometry_kg"],
                "Hand_DEV01_kg": H[k]["H2_DEV01_geometry_kg"], "Model_member_cut_kg": float(r["MemberMassNominal_kg"]),
                "Model_member_geometry_kg": float(r["MemberMassGeometry_kg"]), "Engine_member_kg": eng_s["member_mass_nominal_kg"],
                "SetbackAndCut_effect_kg": round(float(r["MemberMassNominal_kg"]) - H[k]["H2_DEV01_geometry_kg"], 1),
                "R2_with_connections_kg": round(R2m[k] * (1 + basis["r2_takeoff_per_typical_truss"]["connection_ratio"]), 1),
                "Model_plates_kg": float(r["PlateMass_kg"]), "Model_boltsets_kg": float(r["BoltSetMass_kg"]),
                "Model_total_indicative_kg": float(r["TotalSteelIndicative_kg"]),
                "Model_vs_R2_total_pct": round(100 * (float(r["TotalSteelIndicative_kg"]) / (R2m[k] * 1.274) - 1), 1),
                "Counts_model(angles/gussets/splice_pl/packers/bolts)": f"{r['Angles']}/{r['Gussets']}/{r['SplicePlates']}/{r['PackingPlates']}/{r['BoltSets']}",
                "Counts_engine": f"{eng_s['angles']}/{eng_s['gussets']}/{eng_s['splice_plates']}/{eng_s['packers']}/{eng_s['bolts']}"})
w("reconciliation_per_truss.csv", rec)

# set-level bridge R2 -> model
r2_set_members = sum(R2m[line_sec[str(i)] if str(i) not in ("1", "2") else "2"] for i in range(11))
r2_formula = (2 * R2m["0"] + 2 * max(R2m["1"], R2m["2"]) + 7 * R2m["4"])
h1_set = sum(H[line_sec[str(i)]]["H1_R2_geometry_kg"] for i in range(11))
h2_set = sum(H[line_sec[str(i)]]["H2_DEV01_geometry_kg"] for i in range(11))
model_m = float(allr["MemberMassNominal_kg"])
plates = float(allr["PlateMass_kg"]); boltm = sum(float(r["BoltSetMass_kg"]) for r in per)
r2_set = basis["r2_truss_set_t"] * 1000
T = basis["r2_takeoff_per_typical_truss"]
bridge = [
    {"Step": "R2 truss set incl. connections (reported)", "Mass_kg": round(r2_set), "Status": "PRELIMINARY_ESTIMATE"},
    {"Step": "R2 member mass, 2 gable + 2 rigging + 7 typical (R2 formula)", "Mass_kg": round(r2_formula, 1), "Status": "PRELIMINARY_ESTIMATE"},
    {"Step": "R2 connection allowance (27.4 % of members)", "Mass_kg": round(r2_set - r2_formula, 1), "Status": "PRELIMINARY_ESTIMATE"},
    {"Step": "Hand calc H1 (R2 geometry, node-to-node lengths) - check vs R2 members", "Mass_kg": round(h1_set, 1), "Status": "INDEPENDENT_CHECK",
     "Delta_kg": round(h1_set - r2_formula, 1)},
    {"Step": "Hand calc H2 (DEV-01 setting-out: TOS on the purlin seat)", "Mass_kg": round(h2_set, 1), "Status": "INDEPENDENT_CHECK", "Delta_kg": round(h2_set - h1_set, 1)},
    {"Step": "Model member mass (cut lengths x kg/m; set-backs, heel extensions, splice gaps)", "Mass_kg": round(model_m, 1), "Status": "MODEL_DERIVED",
     "Delta_kg": round(model_m - h2_set, 1)},
    {"Step": "Model plates (gussets + splice + packing, net of holes)", "Mass_kg": round(plates, 1), "Status": "MODEL_DERIVED / ASSUMPTION_DEPENDENT"},
    {"Step": "Model bolt sets (simplified geometry)", "Mass_kg": round(boltm, 1), "Status": "ASSUMPTION_DEPENDENT"},
    {"Step": "Model truss set total (indicative)", "Mass_kg": round(model_m + plates + boltm, 1), "Status": "MODEL_DERIVED (sizes CONCEPT_UNVERIFIED)",
     "Delta_kg": round(model_m + plates + boltm - r2_set, 1)},
]
w("reconciliation_bridge_R2_to_model.csv", bridge)
# connection component bridge per typical truss
typ = [r for r in per if r["TrussType"] == "TT-T"][0]
cc = [
    {"Item": "Gusset plates", "R2_count": T["gusset_plates"], "Model_count": int(typ["Gussets"]), "R2_mass_kg": round(15.3 * T["gusset_plates"], 1),
     "Model_mass_kg": float(typ["GussetMass_kg"]), "Explanation": "R2 used 15.3 kg per gusset (average of the superseded model's gussets); modelled 10 mm gussets are sized to the bolt groups (avg ~7.7 kg)"},
    {"Item": "Splice plates", "R2_count": 2 * (T["chord_pieces"] - 2), "Model_count": int(typ["SplicePlates"]), "R2_mass_kg": 8.0 * (T["chord_pieces"] - 2),
     "Model_mass_kg": float(typ["SpliceMass_kg"]), "Explanation": "same count (10 splices x 2); R2 allowed 4 kg per plate, modelled 8 mm plates within the connected-leg flat ~2.2 kg"},
    {"Item": "Packing plates", "R2_count": T["packers"], "Model_count": int(typ["PackingPlates"]), "R2_mass_kg": round(1.2 * T["packers"], 1),
     "Model_mass_kg": float(typ["PackerMass_kg"]), "Explanation": "R2: round(total length/1.2 + webs) double counts (connections already restrain the ends); model: ceil(clear/1.2)-1 per clear length, >= 1 per web"},
    {"Item": "Bolt sets", "R2_count": T["bolts"], "Model_count": int(typ["BoltSets"]), "R2_mass_kg": round(0.35 * T["bolts"], 1), "Model_mass_kg": float(typ["BoltSetMass_kg"]),
     "Explanation": "webs 100 = 100; splice 80 = 80; chord-to-gusset R2 104 vs model 64 (at the 10 splice nodes the splice bolts pass through the gusset - DEV-03); packer bolts follow the packer count"},
    {"Item": "Angles", "R2_count": T["angle_pieces"], "Model_count": int(typ["Angles"]), "R2_mass_kg": T["mass_members_kg"], "Model_mass_kg": float(typ["MemberMassNominal_kg"]),
     "Explanation": "same piece count; mass difference from DEV-01 and cut lengths (see bridge)"},
]
w("reconciliation_connection_components_typical_truss.csv", cc)
res = {"bridge": bridge, "hand": rows, "connection_typical": cc, "set": {"R2_t": basis["r2_truss_set_t"], "model_t": round((model_m + plates + boltm) / 1000, 2),
       "model_members_t": round(model_m / 1000, 2), "model_connections_t": round((plates + boltm) / 1000, 2),
       "model_vs_R2_pct": round(100 * ((model_m + plates + boltm) / r2_set - 1), 1)},
       "engine_vs_ifc_counts_identical": all(r["Counts_model(angles/gussets/splice_pl/packers/bolts)"] == r["Counts_engine"] for r in rec),
       "engine_vs_ifc_member_mass_max_diff_kg": max(abs(r["Model_member_cut_kg"] - r["Engine_member_kg"]) for r in rec),
       "geometry_vs_nominal_member_mass_pct": round(100 * (float(allr["MemberMassGeometry_kg"]) / model_m - 1), 2)}
json.dump(res, open(out / "reconciliation.json", "w"), indent=1)
print(json.dumps(res["set"], indent=1)); print(json.dumps(bridge, indent=1)); print(rows)
print("engine==ifc counts", res["engine_vs_ifc_counts_identical"], "mass diff", res["engine_vs_ifc_member_mass_max_diff_kg"], "geo vs nominal %", res["geometry_vs_nominal_member_mass_pct"])
