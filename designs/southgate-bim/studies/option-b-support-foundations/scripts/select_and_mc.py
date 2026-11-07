"""Selection of the representative design per scheme and Monte-Carlo cost uncertainty (review round 1).
Writes calcs/selection.json, calcs/selection_unconstrained.json, calcs/montecarlo.json.
Representative = cheapest G2/F2 candidate that (a) passes the base case, (b) remains adequate with NO masonry
restraint (column and posts checked over their full height) and (c) fits the 420 mm wall/pier zone.
The unconstrained selection drops (c) and carries the priced pier enlargement instead."""
import json, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
import evaluate as EV

ROOT = EV.ROOT
base = json.load(open(ROOT + "/calcs/sweep_base.json"))["results"]
ev = [e for e in json.load(open(ROOT + "/calcs/eval_base.json")) if e.get("ok")]
robust = {(r["scheme"], r["column"]): (r["ok"] and r.get("util_unrestrained", 9) <= 1.0) for r in base}   # columns; posts get designed restraint struts


def pick(sch, need_fit):
    c = [e for e in ev if e["scheme"] == sch and e["soil"] == "G2" and e["arrangement"] == "F2" and robust.get((sch, e["column"]))
         and (e["fits_wall_zone"] or not need_fit)]
    return min(c, key=lambda e: e["total"]) if c else None


def pack(b, sch):
    rec = next(r for r in base if r["scheme"] == sch and r["column"] == b["column"])
    rep = [x for x in b["bases"] if x["kind"] == "column" and x["line"] == 3 and x["side"] == 0][0]
    return dict(column=b["column"], total=b["total"], cost=b["cost"], steel_t=b["steel_t"], sections=rec["sections"],
                POST=rec["sections"]["POST"], EGD=rec["sections"].get("EGD") if sch != "S2" else None, RBD=rec["sections"]["RBD"],
                BCT=rec["sections"]["BCT"], base=rep["base"], pad=rep["pad"], bases=b["bases"], drift=rec["drift"], col_util=rec["col_util"],
                util_unrestrained=rec.get("util_unrestrained"), alpha=rec["alpha"], found_q=b["found_q"], wall_q=b["wall_q"], hd=b["hd"],
                bolts=b["bolts"], steel=b["steel"], fits=b["fits_wall_zone"], depth_mm=b["col_depth_mm"],
                by_soil={s: {a: next((e["total"] for e in ev if e["scheme"] == sch and e["column"] == b["column"] and e["soil"] == s and e["arrangement"] == a), None)
                             for a in ("F1", "F2", "F3")} for s in ("G1", "G2", "G3")})


sel = {s: pack(pick(s, True), s) for s in ("S1", "S2", "S3")}
unc = {s: pack(pick(s, False), s) for s in ("S1", "S2", "S3")}
json.dump(sel, open(ROOT + "/calcs/selection.json", "w"), indent=1, default=float)
json.dump(unc, open(ROOT + "/calcs/selection_unconstrained.json", "w"), indent=1, default=float)
for lab, d in (("within 420 mm zone", sel), ("unconstrained (+pier enlargement)", unc)):
    print(lab)
    for k, v in d.items():
        print("  ", k, v["column"], round(v["total"]), "arch adj", round(v["cost"].get("architectural_adjustment", 0)),
              {s: {a: round(t / 1000, 1) for a, t in dd.items() if t} for s, dd in v["by_soil"].items()})

# ---------------- Monte Carlo: correlated rate groups + independent quantity/sizing uncertainty per scheme
GROUPS = {"steel": ["steel_ub_uc", "steel_chs", "steel_plate"], "import": ["import_premium"],
          "labour": ["fab_column", "fab_column_fixed", "fab_bracing", "fab_plate", "erect_gang_day"], "plant": ["crane_day", "crane_mob", "mewp_day"],
          "concrete": ["concrete", "blinding", "formwork", "grout"], "rebar": ["rebar"], "earth": ["excavation", "backfill", "disposal"],
          "fixings": ["bolt", "hd_m24", "hd_m30", "hd_m36", "hd_template", "shear_key", "pad_key"], "temp": ["temp_S1", "temp_S2", "temp_S3"],
          "other": ["paint", "transport_t", "long_load", "overhead_profit", "contingency", "void_former", "pier_enlarge"]}
STEEL_Q = ["steel_ub_uc", "steel_chs", "steel_plate", "fab_column", "fab_column_fixed", "fab_bracing", "fab_plate", "paint", "transport_t"]
FOUND_Q = ["concrete", "blinding", "formwork", "rebar", "excavation", "backfill", "disposal", "void_former", "pad_key"]
rng = np.random.default_rng(20261107)
N = 1500
recs = {sch: next(r for r in base if r["scheme"] == sch and r["column"] == sel[sch]["column"]) for sch in sel}
tot = {sch: [] for sch in sel}
wins = {sch: 0 for sch in sel}
for t in range(N):
    f = {}
    for g, keys in GROUPS.items():
        u = rng.random()
        for k in keys:
            lo, c, hi = EV.RATES[k]
            v = rng.triangular(lo, c, hi) if g in ("other", "fixings") else (lo + (hi - lo) * u if hi > lo else c)
            f[k] = v / c if c else 1.0
    res = {}
    for sch in sel:
        qs = rng.triangular(0.92, 1.0, 1.10)     # steel quantity / sizing-method uncertainty (review O-4)
        qf = rng.triangular(0.85, 1.0, 1.25)     # foundation quantity uncertainty (no SI)
        fs = dict(f)
        for k in STEEL_Q:
            fs[k] = fs.get(k, 1.0) * qs
        for k in FOUND_Q:
            fs[k] = fs.get(k, 1.0) * qf
        res[sch] = EV.evaluate(recs[sch], "G2", "F2", fs)["total"]
        tot[sch].append(res[sch])
    wins[min(res, key=res.get)] += 1
T = {s: np.array(v) for s, v in tot.items()}
mc = {sch: dict(p10=float(np.percentile(v, 10)), p50=float(np.percentile(v, 50)), p90=float(np.percentile(v, 90)), mean=float(np.mean(v)),
                cheapest_share=wins[sch] / N) for sch, v in T.items()}
mc["pairwise"] = {f"P(S3<{o})": float(np.mean(T["S3"] < T[o])) for o in ("S1", "S2")}
json.dump(mc, open(ROOT + "/calcs/montecarlo.json", "w"), indent=1)
print(json.dumps(mc, indent=1))
