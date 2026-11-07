"""S02 installed-cost appraisal of the supporting structure (USD, Harare 2026, excl. VAT).
Base pricing: the S01 itemised model (evaluate.py, data/cost_rates.csv, unchanged) applied to the S02 design-basis
designs. S02 adders (each one a measured quantity x an S01 rate, see calculation record section 9):
  A1 north-loggia transfer beams (2 No. UB 457x191x82 + 300x15 soffit plate, 5.56 m)
  A2 F2 strips upgraded to 600 x 600 with 4Y20 T&B: gables in G1/G2, all walls in G3/G3L (850 wide) - interaction check
  A3 G3 / G3L: wall strip founded at >= 1.50 m below ground (S01 founded at 1.35 m): mass-concrete underfill
  A4 slip-resistant (preloaded) bolts in bracing and girder connections: +40 % on structural bolt cost
  A5 execution class EXC3 (consequence class CC3) inspection and testing: +1 % of steelwork cost
Deeper fixed-base pads (hef + 0.45 m) are applied inside the pad design (s02cfg.design_pad2).
Writes S02/calcs/cost_<tag>.json.  Usage: python s02_cost.py TAG sweepfile:scheme:column [...]"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import s02cfg as C
import evaluate as EV
import foundations as F

R = EV.rate
SOILS = ("G1", "G2", "G3L", "G3")
ARRS = ("F1", "F2", "F3")


def adders(ev, soil, arr, which=1):
    a = {}
    # A1 loggia transfer beams
    t = (2 * 5.56 * (82.0 + 0.30 * 0.015 * 7850) + 4 * 35) / 1000
    a["loggia_transfer_beams"] = t * (R("steel_ub_uc", which) + R("fab_column_fixed", which) + R("transport_t", which)) \
        + t * 1000 / 82 * 1.9 * R("paint", which) + 1.0 * (R("crane_day", which) + R("erect_gang_day", which)) + 8 * 2 * R("bolt", which) * 4
    # A2 gable strip upgrade (F2 only)
    if arr == "F2":
        posts = [b for b in ev["bases"] if b["kind"] == "post"]
        Lg = max(2 * 32.7 - sum(b["pad"]["B"] for b in posts), 0)
        if soil in ("G3", "G3L"):          # wet ground: long-wall strips also exceed the S01 strip capacity (S02 interaction check)
            Lg = ev["wall_q"]["length_m"]
        b_s = 0.85 if soil in ("G3", "G3L") else 0.60
        dconc = b_s * 0.15 * Lg
        drebar = (115 * b_s * 0.60 - 75 * b_s * 0.45) * Lg / 1000
        a["F2_gable_strip_upgrade"] = dconc * R("concrete", which) + drebar * R("rebar", which) + 0.15 * (b_s + 0.4) * Lg * R("excavation", which) \
            + 2 * 0.15 * Lg * R("formwork", which)
    # A3 founding depth of the wall strip in G3 / G3L
    if soil in ("G3", "G3L") and arr in ("F1", "F2"):
        Lw = ev["wall_q"]["length_m"]
        b_s = ev["wall_q"].get("width", 0.85)
        v = 0.15 * b_s * Lw
        a["G3_strip_founding_depth"] = v * (R("blinding", which) + R("excavation", which) * 1.3 + R("disposal", which) * 1.25)
    # A4 preloaded bolts
    a["preloaded_bracing_bolts"] = 0.40 * ev["cost"]["bolts_structural"] * R("bolt", which) / R("bolt", 1)
    # A5 EXC3 inspection
    steel_items = ("steel_supply_columns", "steel_supply_posts", "steel_supply_girders", "steel_supply_bracing", "connection_plates",
                   "fabrication", "bolts_structural")
    a["EXC3_inspection"] = 0.01 * sum(ev["cost"][k] for k in steel_items)
    sub = sum(a.values())
    a["adders_contingency"] = sub * ev["pct"]["cont"]
    return a


def price(rec, soil, arr, which=1, f=None):
    ev = EV.evaluate(rec, soil, arr, f, which)
    if not ev.get("ok"):
        return dict(ok=False, fail=ev.get("fail"))
    ad = adders(ev, soil, arr, which)
    tot = ev["total"] + sum(ad.values())
    return dict(ok=True, total=tot, s01_basis_total=ev["total"], adders=ad, cost=ev["cost"], steel_t=ev["steel_t"], steel=ev["steel"],
                found_q=ev["found_q"], wall_q=ev["wall_q"], wall_c=ev["wall_c"], hd=ev["hd"], bolts=ev["bolts"], crane_days=ev["crane_days"],
                bases=[dict(kind=b["kind"], line=b["line"], side=b["side"], k=b["k"], x=b["x"], y=b["y"], pad=b["pad"], env=b["env"],
                            base={k: v for k, v in b["base"].items()}, extra_perm=b["extra_perm"]) for b in ev["bases"]],
                pct=ev["pct"], lines=ev["lines"])


if __name__ == "__main__":
    tag = sys.argv[1]
    out = {}
    for spec in sys.argv[2:]:
        fn, sch, col = spec.split(":")
        sw = json.load(open(fn))["results"]
        rec = next(r for r in sw if r["scheme"] == sch and r["column"] == col)
        rec["_tag"] = fn                     # pad cache key: distinct per sweep file
        key = f"{os.path.basename(fn)[6:-5]}|{sch}|{col}"
        out[key] = dict(ok=rec["ok"], drift=rec["drift"], col_util=rec["col_util"], util_unrestrained=rec["util_unrestrained"],
                        post_util=rec["post_util"], post_util_unrestrained=rec["post_util_unrestrained"], sections=rec["sections"],
                        alpha=rec["alpha"], cfg=rec.get("cfg"), braces=rec.get("braces"), chords=rec.get("chords"), prices={})
        for soil in SOILS:
            for arr in ARRS:
                for which, lab in ((0, "low"), (1, "central"), (2, "high")):
                    p = price(rec, soil, arr, which)
                    if lab != "central" and p.get("ok"):
                        p = dict(ok=True, total=p["total"])
                    out[key]["prices"][f"{soil}|{arr}|{lab}"] = p
                c = out[key]["prices"][f"{soil}|{arr}|central"]
                print(f"{tag} {key:<22} {soil:<3} {arr} " + (f"{c['total']:>9,.0f} (S01 basis {c['s01_basis_total']:>9,.0f}, adders {sum(c['adders'].values()):>7,.0f})" if c.get("ok") else "FAIL " + str(c.get("fail"))), flush=True)
    json.dump(out, open(f"{C.S02}/calcs/cost_{tag}.json", "w"), default=float)
