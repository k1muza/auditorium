"""Single source of every number used in the S02 report, registers and memorandum -> calcs/facts_S02.json."""
import csv, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import s02cfg as C
import analyse as A

J = lambda p: json.load(open(p))
S2 = C.S02 + "/calcs/"
LIM = A.H_WALL * 1000 / 300


def rec(fn, col):
    return next(r for r in J(S2 + f"sweep_{fn}.json")["results"] if r["column"] == col)


def s01rec(sch, col):
    return next(r for r in J(C.S01 + "/calcs/sweep_base.json")["results"] if r["scheme"] == sch and r["column"] == col)


def dr(r):
    d = r["drift"]
    return dict(y085=d["SLS_W"]["col_y_mm"], x085=d["SLS_W"]["eaves_x_mm"], y120=d["SLS_W12"]["col_y_mm"], x120=d["SLS_W12"]["eaves_x_mm"],
                util=r["col_util"], util_unres=r["util_unrestrained"], post=r["post_util"], post_unres=r.get("post_util_unrestrained"), ok=r["ok"])


F = dict(LIM=LIM, LIM400=A.H_WALL * 1000 / 400, H_WALL=A.H_WALL)
# ---------------------------------------------------------------- serviceability matrix
F["drift"] = {
    "S01 S3 UC305x97 (L0, rigid base, nominal bracing)": dr(s01rec("S3", "UC 305x305x97")),
    "S01 S1 UC305x137 (L0)": dr(s01rec("S1", "UC 305x305x137")),
    "S01 S2 UC356x368x153 (L0, rigid base)": dr(s01rec("S2", "UC 356x368x153")),
    "S3 UC305x97 L0 reproduced": dr(rec("x_L0", "UC 305x305x97")),
    "S3 UC305x97 L1, EA 0.85, no fixity reduction": dr(rec("x_L1", "UC 305x305x97")),
    "S3 UC305x97 L2, EA 0.85, no fixity reduction": dr(rec("x_L2", "UC 305x305x97")),
    "S3 UC305x97 L1 design basis": dr(rec("DB_L1_S3", "UC 305x305x97")),
    "S3 UC305x97 L2 design basis": dr(rec("DB_L2_S3", "UC 305x305x97")),
    "S3 UC254x107 L2 design basis": dr(rec("DB_L2_S3", "UC 254x254x107")),
    "S3 UC254x89 L2 design basis": dr(rec("DB_L2_S3", "UC 254x254x89")),
    "S3 UC305x97 L2, base 13 MNm/rad (wet ground)": dr(rec("FX3_L2_S3", "UC 305x305x97")),
    "S3 UC305x97 L1, base 13 MNm/rad (wet ground)": dr(rec("FX3_L1_S3", "UC 305x305x97")),
    "S1 UC305x137 L1 design basis": dr(rec("DB_L1_S12", "UC 305x305x137")),
    "S1 UC305x137 L2 design basis": dr(rec("DB_L2_S12", "UC 305x305x137")),
    "S1 UC305x118 L2 design basis": dr(rec("DB_L2_S12", "UC 305x305x118")),
    "S2 UC356x368x177 L1 design basis": dr(rec("DB_L1_S2", "UC 356x368x177")),
    "S3 UC305x97 L2 sized for 1.20 kPa": dr(rec("UW_L2_S3", "UC 305x305x97")),
    "S3 UC305x118 L2 sized for 1.20 kPa": dr(rec("UW2_S3a", "UC 305x305x118")),
    "S3 UC305x137 L2 sized for 1.20 kPa": dr(rec("UW2_S3b", "UC 305x305x137")),
    "S3 UC305x97 L1 sized for 1.20 kPa": dr(rec("UW_L1_S3", "UC 305x305x97")),
    "S1 UC305x158 L2 sized for 1.20 kPa": dr(rec("UW2_S1" if False else "UW_L2_S1", "UC 305x305x158")),
    "S1 UC356x368x129 L2 sized for 1.20 kPa": dr(rec("UW_L2_S1", "UC 356x368x129")),
    "S1 UC356x368x153 L2 sized for 1.20 kPa": dr(rec("UW2_S1", "UC 356x368x153")),
}
F["sections"] = {k: rec(f, c)["sections"] for k, (f, c) in {"S3_L2": ("DB_L2_S3", "UC 305x305x97"), "S3_L1": ("DB_L1_S3", "UC 305x305x97"),
                                                               "S1_L2": ("DB_L2_S12", "UC 305x305x137"), "S3_UW": ("UW2_S3a", "UC 305x305x118"),
                                                               "S1_UW": ("UW2_S1", "UC 356x368x153")}.items()}
F["alpha"] = {k: rec(f, c)["alpha"] for k, (f, c) in {"S3_L2": ("DB_L2_S3", "UC 305x305x97"), "S1_L2": ("DB_L2_S12", "UC 305x305x137")}.items()}
F["chords"] = {k: rec(f, c)["chords"] for k, (f, c) in {"S3_L2": ("DB_L2_S3", "UC 305x305x97"), "S1_L2": ("DB_L2_S12", "UC 305x305x137")}.items()}
F["braces"] = {k: rec(f, c).get("braces") for k, (f, c) in {"S3_L2": ("DB_L2_S3", "UC 305x305x97"), "S1_L2": ("DB_L2_S12", "UC 305x305x137")}.items()}

# ---------------------------------------------------------------- costs
COSTS = {}
for fn in ("S3DB_L2", "S3DB_L1", "S1DB", "UW"):
    COSTS.update(J(S2 + f"cost_{fn}.json"))
F["cost_keys"] = list(COSTS)


def P(key, soil="G2", arr="F2", lab="central"):
    p = COSTS[key]["prices"].get(f"{soil}|{arr}|{lab}")
    return p if p and p.get("ok") else None


KEYS = {"S3": "DB_L2_S3|S3|UC 305x305x97", "S3_L1": "DB_L1_S3|S3|UC 305x305x97", "S1": "DB_L2_S12|S1|UC 305x305x137",
        "S1_L1": "DB_L1_S12|S1|UC 305x305x137", "S3_107": "DB_L2_S3|S3|UC 254x254x107", "S3_89": "DB_L2_S3|S3|UC 254x254x89",
        "S3_UW": "UW2_S3a|S3|UC 305x305x118", "S3_UW137": "UW2_S3b|S3|UC 305x305x137", "S3_UW97": "UW_L2_S3|S3|UC 305x305x97",
        "S1_UW": "UW2_S1|S1|UC 356x368x153", "S3_FX3": "FX3_L2_S3|S3|UC 305x305x97", "S3_L1_UW": "UW_L1_S3|S3|UC 305x305x97"}
tot = {}
for k, key in KEYS.items():
    if key not in COSTS:
        continue
    tot[k] = {f"{s}|{a}": {lab: (P(key, s, a, lab) or {}).get("total") for lab in ("low", "central", "high")}
              for s in ("G1", "G2", "G3L", "G3") for a in ("F1", "F2", "F3")}
F["totals"] = tot
F["detail"] = {k: P(KEYS[k]) for k in ("S3", "S1", "S3_L1", "S3_UW", "S1_UW")}
for k in F["detail"]:
    F["detail"][k] = {kk: v for kk, v in F["detail"][k].items() if kk != "lines"}
F["detail_G3"] = {k: {kk: v for kk, v in P(KEYS[k], "G3", "F3").items() if kk not in ("lines", "bases")} for k in ("S3", "S1")}
F["detail_G3L"] = {k: {kk: v for kk, v in P(KEYS[k], "G3L", "F2").items() if kk not in ("lines", "bases")} for k in ("S3", "S1")}
F["lines_S3"] = P(KEYS["S3"])["lines"]
F["lines_S1"] = P(KEYS["S1"])["lines"]
F["S01_totals"] = {s: J(C.S01 + "/calcs/selection.json")[s]["total"] for s in ("S1", "S2", "S3")}
F["S01_by_soil"] = {s: J(C.S01 + "/calcs/selection.json")[s]["by_soil"] for s in ("S1", "S2", "S3")}
F["S01_steel"] = {s: J(C.S01 + "/calcs/selection.json")[s]["steel_t"] for s in ("S1", "S2", "S3")}
F["S01_mc"] = J(C.S01 + "/calcs/montecarlo.json")

# ---------------------------------------------------------------- R2 bridge
R2 = {r["component"]: float(r["central_usd"]) for r in csv.DictReader(open(r"C:/Users/Kelvin/Desktop/auditorium/designs/F-site-A-2000-astra-v2/studies/roof-truss-selection/data/r2_cost_comparison.csv")) if r["option"] == "B"}
mass_share, paint_share, fab_share, temp_share = 0.43, 0.466, 0.15, 0.50
alloc = {"Structural steel - primary trusses": 0.0, "Structural steel - roof columns UC254x254x73 (22 No.)": 1.0,
         "Secondary - purlins/cleats/splices (common)": 0.0, "Secondary - bracing / lateral system": 1.0,
         "Secondary - equipment support steel (spreaders, HVLS/array beams)": 0.0, "Fabrication labour (cut, drill, weld, assemble, QA)": fab_share,
         "Connections - bolts (shop/site sets)": fab_share, "Protective finish - 2-coat paint (purlins pre-galvanised)": paint_share,
         "Transport - workshop to site": mass_share, "Installation - erection labour (trusses, columns, purlins, bracing)": mass_share,
         "Installation - crane hire + mobilisation": mass_share, "Installation - MEWP/access": mass_share,
         "Temporary works - erection bracing / props": temp_share, "Foundation implications (difference vs. truss-on-column)": 1.0,
         "Foundations - 22 column pads designed for uplift (common)": 1.0,
         "Lateral system - eaves wind girders, R2 sizing (increase over R1 allowance)": 1.0, "Option-specific residual risk allowance": 0.0}
r2_sup = {k: R2[k] * a for k, a in alloc.items()}
sub_all = sum(v for k, v in R2.items() if k not in ("Contingency (design development)", "TOTAL installed (excl. VAT)"))
cont_share = sum(r2_sup.values()) / sub_all
r2_sup["Contingency (design development)"] = R2["Contingency (design development)"] * cont_share
R2_support = sum(r2_sup.values())
R2_total = R2["TOTAL installed (excl. VAT)"]
F["R2"] = dict(total=R2_total, support=R2_support, roof=R2_total - R2_support, items=R2, alloc=alloc, support_items=r2_sup,
               s01_roof_basis=195000.0, roof_all_labour=R2_total - (R2[ "Structural steel - roof columns UC254x254x73 (22 No.)"] +
                                                                        R2["Secondary - bracing / lateral system"] + R2["Foundations - 22 column pads designed for uplift (common)"] +
                                                                        R2["Lateral system - eaves wind girders, R2 sizing (increase over R1 allowance)"]))
d = F["detail"]["S3"]
c, a = d["cost"], d["adders"]
pstr = d["steel"]["PSTR"]["t"] * 1750
g = lambda *ks: sum(c.get(k, 0) for k in ks)
ga = lambda *ks: sum(a.get(k, 0) for k in ks)
R = r2_sup
rows = [
    ("Side columns: UC 254x254x73 to UC 305x305x97 (supply)", "quantity growth (stiffness criterion)", R["Structural steel - roof columns UC254x254x73 (22 No.)"], g("steel_supply_columns")),
    ("Gable wind posts and restraint struts (supply)", "new scope (omitted in R2)", 0.0, g("steel_supply_posts") + pstr),
    ("Roof girders, wall and gable bracing, ties (supply)", "quantity growth (complete stability system)",
     R["Secondary - bracing / lateral system"] + R["Lateral system - eaves wind girders, R2 sizing (increase over R1 allowance)"], g("steel_supply_girders", "steel_supply_bracing") - pstr),
    ("Connections, structural and holding-down bolts, grout, shear keys, anchor reinforcement", "scope growth (fixed bases, uplift)",
     R["Connections - bolts (shop/site sets)"], g("connection_plates", "bolts_structural", "holding_down_bolts", "grout", "shear_keys", "anchor_reinforcement")),
    ("Fabrication", "scope growth (more members, fixed bases)", R["Fabrication labour (cut, drill, weld, assemble, QA)"], g("fabrication")),
    ("Corrosion protection and transport", "follows tonnage", R["Protective finish - 2-coat paint (purlins pre-galvanised)"] + R["Transport - workshop to site"],
     g("corrosion_protection", "transport")),
    ("Erection, cranes, access and temporary works", "scope growth and slower productivity",
     R["Installation - erection labour (trusses, columns, purlins, bracing)"] + R["Installation - crane hire + mobilisation"] + R["Installation - MEWP/access"] + R["Temporary works - erection bracing / props"],
     g("erection_labour", "cranes_access", "temporary_works", "architectural_adjustment")),
    ("Column and gable-post foundations", "quantity growth (uplift, fixed bases, posts)", R["Foundations - 22 column pads designed for uplift (common)"] + R["Foundation implications (difference vs. truss-on-column)"],
     g("column_foundations")),
    ("Reinforced wall strip (F2)", "building element now included (not in R2 roof scope)", 0.0, g("wall_foundations") + ga("F2_gable_strip_upgrade", "G3_strip_founding_depth")),
    ("Loggia transfer beams, preloaded bracing bolts, EXC3 inspection", "new scope identified in S02", 0.0, ga("loggia_transfer_beams", "preloaded_bracing_bolts", "EXC3_inspection")),
    ("Inspection, fabricator margin, contingency and risk allowance", "allowance basis (10 % + 2 % v R2 5 %)", R["Contingency (design development)"],
     g("qa_testing", "overhead_profit_labour_plant", "contingency") + ga("adders_contingency")),
]
F["bridge"] = [dict(item=a_, nature=b_, r2=r, s02=s, delta=s - r) for a_, b_, r, s in rows]
F["bridge_check"] = dict(r2_sum=sum(r[2] for r in rows), s02_sum=sum(r[3] for r in rows), s02_total=d["total"], r2_support=R2_support)
F["rate_check"] = dict(r2_column_rate=R["Structural steel - roof columns UC254x254x73 (22 No.)"] / (22 * 13.08 * 73.1 / 1000), s02_column_rate=1600.0)

# ---------------------------------------------------------------- foundation interaction summary
bef = {}
for L in ("L2", "L1"):
    for so in ("G1", "G2", "G3L", "G3"):
        fn = S2 + f"bef_{L}_S3_{so}.json"
        if os.path.exists(fn):
            for k, v in J(fn).items():
                if "summary" in v:
                    bef[f"S3|{L}|{k}"] = v["summary"]
for fn, lab in ((S2 + "bef_L1_S1_G2.json", "S1|L1|G2"), (S2 + "bef_L1_S1_G3.json", "S1|L1|G3"), (S2 + "bef_L1_S1_G3L.json", "S1|L1|G3L"), (S2 + "bef_L2_S1.json", "S1|L2")):
    if os.path.exists(fn):
        for k, v in J(fn).items():
            if "summary" in v:
                bef[f"{lab.split('|')[0]}|{lab.split('|')[1]}|{k}"] = v["summary"]
F["bef"] = bef
F["hand"] = {s: J(S2 + f"hand_{s}.json") for s in ("S3", "S1")}
F["reactions"] = J(S2 + "reactions_S02.json")
json.dump(F, open(S2 + "facts_S02.json", "w"), indent=1, default=float)
b = F["bridge_check"]
print("bridge", {k: round(v) for k, v in b.items()}, "R2 roof", round(F["R2"]["roof"]), "support", round(R2_support))
for r in F["bridge"]:
    print(f"  {r['item'][:60]:<60} {r['r2']:>9,.0f} {r['s02']:>9,.0f} {r['delta']:>+9,.0f}")
for k, v in tot.items():
    print(k, {kk: round(vv["central"] / 1000, 1) for kk, vv in v.items() if vv["central"]})
print("BEF keys", len(bef))
