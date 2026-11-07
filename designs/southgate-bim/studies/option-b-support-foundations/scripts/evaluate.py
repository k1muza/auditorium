"""Whole-system evaluation: connections, base plates, foundations, quantities and installed cost for every
feasible (scheme, column) candidate of a sweep, for each soil scenario and foundation arrangement.
Usage: python evaluate.py [sweep_tag]  -> calcs/eval_<tag>.json
Rates: data/cost_rates.csv (USD, Harare 2026, excl. VAT) - every rate is labelled with its basis there."""
from __future__ import annotations
import csv, json, math, os, sys
sys.path.insert(0, os.path.dirname(__file__))
import foundations as F
import sections as S
import model_b as MB

ROOT = os.path.abspath(os.path.dirname(__file__) + "/..")
RATES = {r["rate"]: (float(r["low"]), float(r["central"]), float(r["high"])) for r in csv.DictReader(open(ROOT + "/data/cost_rates.csv"))}
CAT = {s.name: s for s in S.COLUMNS + S.CHS}
COMMON_GROUPS = ["POST", "PSTR", "EAV", "RBD", "XF", "BCB", "BCT", "WBX", "WBK", "WBS"]
VAR_GROUPS = ["COL", "COLC", "EGC", "EGD", "GBX", "GBS"]
LOGGIA_EXTRA = {(7, 1): 134.0, (8, 1): 267.0, (9, 1): 134.0}   # kN char. permanent: north wall over loggia via transfer beam (study assumption)
WALL_LONG = 2 * (59.0 - 3.1) - 9.5      # m of long-wall masonry on ground (north loggia opening excluded)
WALL_GABLE = 2 * 32.7


WALL_FACTOR = 1.0     # sensitivity: 0.7 = hollow / lighter masonry
# ground-level openings that interrupt the wall weight on the strip (x ranges on the long walls, y ranges on the gables)
OPEN_LONG = {0: [(6.0, 8.4, 2.5), (28.0, 30.4, 2.5), (44.0, 46.8, 2.5), (54.5, 57.3, 2.5)],
             1: [(6.0, 8.4, 2.5), (28.0, 30.4, 2.5), (43.0, 52.5, 13.3), (54.5, 57.3, 2.5)]}   # north loggia: no wall on the strip
OPEN_GABLE = {0: [(5.0, 6.2, 2.4), (26.8, 28.0, 2.4)], 10: [(14.0, 19.0, 13.3)]}


def engaged_wall(b, length):
    """Characteristic wall weight (kN) acting on a pad over an engaged length centred on the base, net of openings."""
    if b["kind"] == "column":
        c, ops = b["x"], OPEN_LONG[b["side"]]
    else:
        c, ops = b["y"], OPEN_GABLE[b["line"]]
    lo, hi = c - length / 2, c + length / 2
    w = F.WALL_KN_M * length
    for a, z, h in ops:
        ov = max(0.0, min(hi, z) - max(lo, a))
        w -= F.WALL_KN_M * min(h / 13.3, 1.0) * ov
    return max(w, 0.0) * WALL_FACTOR


def rate(k, which=1, f=None):
    v = RATES[k][which]
    return v * (f.get(k, 1.0) if f else 1.0)


def split_cases(Rd, wall_construction_factor=0.75):
    char = [(c, R) for c, R in Rd.items() if c.startswith("C ")]
    uls = [(c, R) for c, R in Rd.items() if c.startswith("U")]
    constr = []
    for w in ("WSp", "WSn", "WNp", "WNn", "WWp", "WWn", "WEp", "WEn"):
        a, b = Rd.get(f"C Gmin+W {w} q1.2"), Rd.get(f"C Gmin+W {w} q0.85")
        if a and b:
            W = [(x - y) / 0.35 for x, y in zip(a, b)]
            Gm = [x - 1.2 * wv for x, wv in zip(a, W)]
            constr.append((f"0.9G+1.3x{wall_construction_factor}xW {w}", [0.9 * g + 1.3 * wall_construction_factor * 1.2 * wv for g, wv in zip(Gm, W)]))
    return char, uls, constr


def add_perm(cases, P):
    return [(n, [R[0], R[1], R[2] + P * (1.0 if n.startswith("C") else 1.2 if "1.2G" in n or "1.35G" in n else 0.9), R[3], R[4], R[5]]) for n, R in cases]


def envelope(Rd):
    uls = [R for c, R in Rd.items() if c.startswith("U")]
    return dict(Nc=max(R[2] for R in uls), Nt=max(-R[2] for R in uls), H=max(math.hypot(R[0], R[1]) for R in uls),
                M=max(abs(R[3]) for R in uls), Hy=max(abs(R[1]) for R in uls), Hx=max(abs(R[0]) for R in uls))


def found_cost(p, soil, f=None, which=1):
    s = F.SOILS[soil]
    und = F.Z_TOP - p.D
    depth = F.FGL - und + 0.05
    exc = (p.B + 0.6) * (p.L + 0.6) * depth
    conc = p.B * p.L * p.D
    encase = 0.6 * 0.6 * (F.FGL - F.Z_TOP + 0.165)
    blind = p.B * p.L * 0.05
    form = 2 * (p.B + p.L) * p.D + 4 * 0.6 * (F.FGL - F.Z_TOP + 0.165)
    backfill = exc - conc - blind - encase
    disposal = (conc + blind + encase) * 1.25
    ex_rate = rate("excavation", which, f) * (1.3 if s["heave"] else 1.0)
    c = dict(excavation=exc * ex_rate, blinding=blind * rate("blinding", which, f), concrete=(conc + encase) * rate("concrete", which, f),
             rebar=(p.rebar_kg + encase * 60) / 1000 * rate("rebar", which, f), formwork=form * rate("formwork", which, f),
             backfill=backfill * rate("backfill", which, f), disposal=disposal * rate("disposal", which, f))
    q = dict(excavation_m3=exc, blinding_m3=blind, concrete_m3=conc + encase, rebar_kg=p.rebar_kg + encase * 60, formwork_m2=form,
             backfill_m3=backfill, disposal_m3=disposal)
    return c, q


def wall_foundation(arr, soil, f=None, which=1, deduct=0.0):
    """Masonry wall support along the long walls and gables (common to all schemes, arrangement-dependent)."""
    s = F.SOILS[soil]
    Lw = WALL_LONG + WALL_GABLE - deduct     # pads already occupy their length of the wall line (no double count)
    if arr == "F3":
        b, h, kgm3 = 0.35, 0.75, 130
        conc = b * h * Lw
        q = dict(concrete_m3=conc, rebar_kg=conc * kgm3, formwork_m2=2 * h * Lw, excavation_m3=0.95 * (h + 0.3) * Lw,
                 void_former_m=Lw, blinding_m3=b * 0.05 * Lw)
    else:
        B = max(0.6, math.ceil((F.WALL_KN_M / (s["qa"] - 24 * 0.45)) * 20) / 20)
        D = 0.45
        kgm3 = 75 if arr == "F2" else 35
        conc = B * D * Lw
        q = dict(concrete_m3=conc, rebar_kg=conc * kgm3, formwork_m2=2 * D * Lw, excavation_m3=(B + 0.4) * (F.FGL - (F.Z_TOP - D) + 0.05) * Lw,
                 void_former_m=0.0, blinding_m3=B * 0.05 * Lw, width=B)
    q["backfill_m3"] = max(q["excavation_m3"] - q["concrete_m3"] - q["blinding_m3"], 0)
    ex_rate = rate("excavation", which, f) * (1.3 if s["heave"] else 1.0)
    c = dict(excavation=q["excavation_m3"] * ex_rate, concrete=q["concrete_m3"] * rate("concrete", which, f),
             rebar=q["rebar_kg"] / 1000 * rate("rebar", which, f), formwork=q["formwork_m2"] * rate("formwork", which, f),
             blinding=q["blinding_m3"] * rate("blinding", which, f), backfill=q["backfill_m3"] * rate("backfill", which, f),
             disposal=(q["concrete_m3"] + q["blinding_m3"]) * 1.25 * rate("disposal", which, f),
             void_former=q["void_former_m"] * rate("void_former", which, f))
    return c, q


def steel_rate(sec_name, f=None, which=1):
    s = CAT.get(sec_name)
    av = s.avail if s else "SA-stock"
    if s and s.family == "CHS":
        return rate("steel_chs", which, f) * (1.12 if av == "SA-order" else 1.0)
    base = rate("steel_ub_uc", which, f)
    return base * {"SA-stock": 1.0, "SA-order": 1.06, "import": 1.0 + RATES["import_premium"][which]}[av]


PADCACHE = {}


def evaluate(rec, soil, arr, f=None, which=1):
    sch = rec["scheme"]
    fixed = sch in ("S2", "S3")
    out = dict(scheme=sch, column=rec["column"], soil=soil, arrangement=arr)
    # ---------------- steel quantities
    steel = {}
    for g, q in rec["qty"].items():
        if g in ("BEARING", "KNEE", "HEEL", "POSTTOP"):
            continue
        steel[g] = dict(section=q["section"], n=q["n"], L=q["L"], t=q["kg"] / 1000)
    # gable-post minor-axis restraint struts (review: posts fail by 2.6-4.6x with no restraint): 2 rows per gable, CHS 88.9x3.2
    steel["PSTR"] = dict(section="CHS 88.9x3.2", n=20, L=4 * 32.4, t=4 * 32.4 * CAT["CHS 88.9x3.2"].kg / 1000)
    # member counts for erection: columns 22, posts 12, bracing pieces (count elements of bar groups; chains merged)
    col_n = 22
    post_n = 12
    brace_pieces = sum(steel[g]["n"] for g in steel if g not in ("COL", "COLC", "POST"))
    # connections (mass allowance) and bolts
    conn_kg, bolts = 0.0, 0
    for g in steel:
        if g in ("COL", "COLC", "POST"):
            continue
        sec = CAT.get(steel[g]["section"])
        d = sec.d if sec else 0.1
        kgm = sec.kg if sec else 10
        per_end = 3.0 + 0.15 * kgm          # gusset + slotted-tube cover / end plate, kg per end (concept allowance)
        conn_kg += steel[g]["n"] * 2 * per_end
        bolts += steel[g]["n"] * 2 * (2 if d <= 0.115 else 4)
    # truss-to-column bearings
    if sch == "S2":
        conn_kg += 22 * (40 + 35)
        bolts += 22 * (8 + 6)
        knee = max(abs(v) for b in rec["bearings"] if b["group"] == "KNEE" for F_ in b["F"].values() for v in F_[:2])
        out["knee_force_kN"] = knee
    else:
        conn_kg += 22 * 25 + 4 * 15
        bolts += 22 * 4 + 4 * 2
    post_conn = 12 * (25 + 15)
    conn_kg += post_conn
    bolts += 12 * 6
    # ---------------- bases and foundations
    found_c, found_q, bases = {}, {}, []
    hd = dict(n=0, kg_plate=0.0, anchor_reinf_kg=0.0, grout_m3=0.0, shear_keys=0, bolt_cost=0.0)
    for b in rec["bases"]:
        Rd = b["R"]
        env = envelope(Rd)
        is_col = b["kind"] == "column"
        sec = CAT[rec["sections"]["COLC" if (is_col and b["line"] in (0, 10)) else "COL"]] if is_col else CAT[rec["sections"]["POST"]]
        fx = fixed and is_col
        pairs = [(R[2], R[3] if fx else 0.0, math.hypot(R[0], R[1])) for c, R in Rd.items() if c.startswith("U")]
        bc = F.base_connection(fx, sec.d, sec.b, env["Nt"], env["M"] if fx else 0.0, env["Nc"], env["H"], pairs=pairs)
        char, uls, constr = split_cases(Rd)
        key = (b["line"], b.get("side", -1))
        extra = LOGGIA_EXTRA.get(key, 0.0) if is_col else 0.0
        if extra:
            char, uls = add_perm(char, extra), add_perm(uls, extra)
        if arr == "F1":
            wall = 0.0
        elif arr == "F2":
            wall = engaged_wall(b, F.ENGAGE)
        else:
            wall = engaged_wall(b, 5.56 if is_col else 5.4)
        ck = (rec["scheme"], rec["column"], rec.get("_tag", ""), soil, arr, b["kind"], b["line"], b.get("side"), b.get("k"))
        if ck not in PADCACHE:
            PADCACHE[ck] = F.design_pad(char, uls, constr, soil, col_b=max(sec.d, sec.b) + 0.15, wall_kNm=wall, fixed_base=fx,
                                        D_min=bc['hef'] / 1000 + 0.30)
        p = PADCACHE[ck]
        if not p.ok:
            out["ok"] = False
            out["fail"] = f"foundation {b['kind']} {key}: {p.gov}"
            return out
        c, q = found_cost(p, soil, f, which)
        for k, v in c.items():
            found_c[k] = found_c.get(k, 0) + v
        for k, v in q.items():
            found_q[k] = found_q.get(k, 0) + v
        hd["n"] += bc["n_bolts"]
        hd["kg_plate"] += bc["plate_kg"]
        hd["anchor_reinf_kg"] += bc["anchor_reinf_kg"]
        hd["grout_m3"] += bc["grout_m3"]
        hd["shear_keys"] += int(bc["shear_key"])
        hd["pad_keys"] = hd.get("pad_keys", 0) + int(bool(p.notes))
        hd["bolt_cost"] += bc["n_bolts"] * rate({24: "hd_m24", 30: "hd_m30", 36: "hd_m36"}[bc["dia"]], which, f)
        hd.setdefault("by_dia", {})
        hd["by_dia"][bc["dia"]] = hd["by_dia"].get(bc["dia"], 0) + bc["n_bolts"]
        bases.append(dict(kind=b["kind"], line=b["line"], side=b.get("side"), k=b.get("k"), x=b["x"], y=b["y"], env=env, base=bc,
                          pad=dict(B=p.B, L=p.L, D=p.D, As_bot=p.As_bot, As_top=p.As_top, rebar_kg=p.rebar_kg, notes=p.notes), extra_perm=extra))
    deduct = sum((x["pad"]["L"] if x["kind"] == "column" else x["pad"]["B"]) for x in bases)
    wc, wq = wall_foundation(arr, soil, f, which, deduct)
    wq["length_m"] = WALL_LONG + WALL_GABLE - deduct
    # ---------------- costs
    cost = {}
    t_var = {g: steel[g]["t"] for g in steel}
    supply = sum(steel[g]["t"] * steel_rate(steel[g]["section"], f, which) for g in steel)
    cost["steel_supply_columns"] = sum(steel[g]["t"] * steel_rate(steel[g]["section"], f, which) for g in ("COL", "COLC") if g in steel)
    cost["steel_supply_posts"] = steel["POST"]["t"] * steel_rate(steel["POST"]["section"], f, which)
    cost["steel_supply_girders"] = sum(steel[g]["t"] * steel_rate(steel[g]["section"], f, which) for g in ("EGC", "EGD") if g in steel)
    cost["steel_supply_bracing"] = sum(steel[g]["t"] * steel_rate(steel[g]["section"], f, which) for g in steel if g not in ("COL", "COLC", "POST", "EGC", "EGD"))
    plates_t = (conn_kg + hd["kg_plate"]) / 1000
    cost["connection_plates"] = plates_t * rate("steel_plate", which, f)
    cost["bolts_structural"] = bolts * rate("bolt", which, f)
    cost["holding_down_bolts"] = hd["bolt_cost"] + len(rec["bases"]) * rate("hd_template", which, f)
    cost["grout"] = hd["grout_m3"] * rate("grout", which, f)
    cost["shear_keys"] = hd["shear_keys"] * rate("shear_key", which, f) + hd.get("pad_keys", 0) * rate("pad_key", which, f)
    t_col = sum(steel[g]["t"] for g in ("COL", "COLC"))
    t_post = steel["POST"]["t"]
    t_br = sum(steel[g]["t"] for g in steel if g not in ("COL", "COLC", "POST"))
    fab_col = rate("fab_column_fixed" if fixed else "fab_column", which, f) * (1.15 if sch == "S2" else 1.0)
    cost["fabrication"] = t_col * fab_col + t_post * rate("fab_column", which, f) + t_br * rate("fab_bracing", which, f) + plates_t * rate("fab_plate", which, f)
    area = sum(steel[g]["L"] * (CAT[steel[g]["section"]].perim if steel[g]["section"] in CAT else 0.5) for g in steel) + plates_t * 25
    cost["corrosion_protection"] = area * rate("paint", which, f)
    t_all = sum(steel[g]["t"] for g in steel) + plates_t
    cost["transport"] = t_all * rate("transport_t", which, f) + (col_n + post_n) * rate("long_load", which, f)
    crane_days = col_n / 6 + post_n / 4 + brace_pieces / 15 + 2 + (2 if sch == "S2" else 0) + 1   # review O-16: slower, plus girder assembly
    cost["erection_labour"] = crane_days * rate("erect_gang_day", which, f)
    cost["cranes_access"] = crane_days * (rate("crane_day", which, f) + rate("mewp_day", which, f)) + rate("crane_mob", which, f)
    cost["temporary_works"] = rate({"S1": "temp_S1", "S2": "temp_S2", "S3": "temp_S3"}[sch], which, f)
    col_d = CAT[rec["sections"]["COL"]].d
    excess = max(0.0, col_d + 0.05 - 0.42)
    cost["architectural_adjustment"] = 22 * excess * 0.60 * 12.5 * rate("pier_enlarge", which, f)
    cost["column_foundations"] = sum(found_c.values())
    cost["wall_foundations"] = sum(wc.values())
    cost["anchor_reinforcement"] = hd["anchor_reinf_kg"] / 1000 * rate("rebar", which, f)
    sub = sum(cost.values())
    cost["qa_testing"] = 0.02 * (sub - cost["column_foundations"] - cost["wall_foundations"]) + 0.015 * (cost["column_foundations"] + cost["wall_foundations"])
    sub = sum(cost.values())
    risk = {"S1": 0.0, "S2": 0.04, "S3": 0.02}[sch]
    cost["overhead_profit_labour_plant"] = rate("overhead_profit", which, f) * (cost["fabrication"] + cost["erection_labour"] + cost["cranes_access"])
    sub = sum(cost.values())
    cost["contingency"] = sub * (rate("contingency", which, f) + risk)
    # ---------------- auditable line items (cost = qty x rate x factor; pct lines = base x pct)
    L = []
    def ln(cat, item, qty, unit, key, factor=1.0):
        qa = "found" if cat in ("Foundations (columns/posts)", "Wall foundations") else "steel"
        op = 1 if (cat == "Fabrication" and "paint" not in item) or item in ("erection gang", "crane", "MEWP", "crane mobilisation") else 0
        L.append(dict(category=cat, item=item, qty=qty, unit=unit, rate=key, factor=factor, qa=qa, op=op))
    for g in steel:
        sec = CAT.get(steel[g]["section"])
        cat = "Side columns" if g in ("COL", "COLC") else "Gable wind posts" if g == "POST" else "Wind girders" if g in ("EGC", "EGD") else "Bracing / ties / struts"
        key = "steel_chs" if sec and sec.family == "CHS" else "steel_ub_uc"
        fac = (1.12 if sec and sec.avail == "SA-order" else 1.0) if key == "steel_chs" else {"SA-stock": 1.0, "SA-order": 1.06, "import": 1.0 + RATES["import_premium"][which]}[sec.avail if sec else "SA-stock"]
        ln(cat, f"{g} {steel[g]['section']} supply ({steel[g]['n']} pcs, {steel[g]['L']:.0f} m)", steel[g]["t"], "t", key, fac)
    ln("Connections", "connection + base plates S355", plates_t, "t", "steel_plate")
    ln("Connections", "structural bolt sets M16/M20 8.8", bolts, "No.", "bolt")
    for dia, n in sorted(hd.get("by_dia", {}).items()):
        ln("Connections", f"holding-down bolts M{dia} 8.8 cast-in", n, "No.", {24: "hd_m24", 30: "hd_m30", 36: "hd_m36"}[dia])
    ln("Connections", "HD setting templates / survey", len(rec["bases"]), "base", "hd_template")
    ln("Connections", "non-shrink grout", hd["grout_m3"], "m3", "grout")
    ln("Connections", "base-plate shear keys (uplift with shear)", hd["shear_keys"], "No.", "shear_key")
    ln("Foundations (columns/posts)", "pad downstand shear keys (sliding on soil)", hd.get("pad_keys", 0), "No.", "pad_key")
    ln("Fabrication", "columns", t_col, "t", "fab_column_fixed" if fixed else "fab_column", 1.15 if sch == "S2" else 1.0)
    ln("Fabrication", "gable posts", t_post, "t", "fab_column")
    ln("Fabrication", "bracing, girders, ties", t_br, "t", "fab_bracing")
    ln("Fabrication", "connection plates", plates_t, "t", "fab_plate")
    ln("Corrosion protection", "2-coat shop paint system (internal C2)", area, "m2", "paint")
    ln("Erection", "transport", t_all, "t", "transport_t")
    ln("Erection", "long loads (columns, posts)", col_n + post_n, "piece", "long_load")
    ln("Erection", "erection gang", crane_days, "day", "erect_gang_day")
    ln("Erection", "crane", crane_days, "day", "crane_day")
    ln("Erection", "MEWP", crane_days, "day", "mewp_day")
    ln("Erection", "crane mobilisation", 1, "item", "crane_mob")
    ln("Erection", "temporary works (erection stability)", 1, "item", {"S1": "temp_S1", "S2": "temp_S2", "S3": "temp_S3"}[sch])
    ln("Architectural adjustment", "pier enlargement for columns deeper than the 420 mm zone", 22 * excess * 0.60 * 12.5, "m3", "pier_enlarge")
    hv = 1.3 if F.SOILS[soil]["heave"] else 1.0
    for lab, q, c_ in (("Foundations (columns/posts)", found_q, None), ("Wall foundations", wq, None)):
        ln(lab, "excavation", q["excavation_m3"], "m3", "excavation", hv)
        ln(lab, "blinding", q["blinding_m3"], "m3", "blinding")
        ln(lab, "concrete C25/30 (incl. encasement)" if lab.startswith("Found") else "concrete C25/30", q["concrete_m3"], "m3", "concrete")
        ln(lab, "reinforcement", q["rebar_kg"] / 1000, "t", "rebar")
        ln(lab, "formwork", q["formwork_m2"], "m2", "formwork")
        ln(lab, "backfill", q["backfill_m3"], "m3", "backfill")
        ln(lab, "disposal (bulked)", q.get("disposal_m3", (q["concrete_m3"] + q["blinding_m3"]) * 1.25), "m3", "disposal")
        if q.get("void_former_m"):
            ln(lab, "void former", q["void_former_m"], "m", "void_former")
    ln("Connections", "anchor (supplementary) reinforcement at holding-down bolts", hd["anchor_reinf_kg"] / 1000, "t", "rebar")
    out["lines"] = L
    out["pct"] = dict(qa_steel=0.02, qa_found=0.015, op=rate("overhead_profit", which, f), cont=rate("contingency", which, f) + risk, risk=risk)
    col_d = CAT[rec["sections"]["COL"]].d
    out["fits_wall_zone"] = col_d <= 0.42
    out["col_depth_mm"] = col_d * 1000
    out.update(ok=True, cost=cost, total=sum(cost.values()),
               steel=steel, steel_t=dict(columns=t_col, posts=t_post, bracing_girders=t_br, plates=plates_t, total=t_all),
               bolts=bolts, hd=hd, found_q=found_q, wall_q=wq, wall_c=wc, bases=bases, crane_days=crane_days)
    return out


if __name__ == "__main__":
    tag = sys.argv[1] if len(sys.argv) > 1 else "base"
    sw = json.load(open(f"{ROOT}/calcs/sweep_{tag}.json"))
    res = []
    for rec in sw["results"]:
        if not rec["ok"]:
            res.append(dict(scheme=rec["scheme"], column=rec["column"], ok=False, fail=f"structure: util {rec['col_util']:.2f}, drift ratio {rec['drift_ratio']:.2f}"))
            continue
        for soil in ("G1", "G2", "G3"):
            for arr in ("F1", "F2", "F3"):
                e = evaluate(rec, soil, arr)
                res.append(e)
                if e.get("ok"):
                    print(f"{rec['scheme']} {rec['column']:<18} {soil} {arr} total {e['total']:>9,.0f}  cols {e['cost']['steel_supply_columns']:>8,.0f} "
                          f"found {e['cost']['column_foundations']:>8,.0f} wall {e['cost']['wall_foundations']:>8,.0f}")
                else:
                    print(rec["scheme"], rec["column"], soil, arr, "FAIL", e.get("fail"))
    json.dump(res, open(f"{ROOT}/calcs/eval_{tag}.json", "w"), default=float)
