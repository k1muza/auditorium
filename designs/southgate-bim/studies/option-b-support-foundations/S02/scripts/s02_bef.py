"""S02 foundation interaction check for the F2 arrangement (pads cast integral with a reinforced wall strip).

Each wall line (south, north, west gable, east gable) is modelled as a continuous reinforced-concrete beam on a
tensionless Winkler foundation: strip sections between pads, pad sections (width B across the wall, length L along
it, depth D) at every column / gable post. Loads per case, all CONCURRENT from one load combination:
  - masonry wall line load net of openings (characteristic 72 kN/m x height fraction), loggia wall via transfer
    beams to columns 7N/8N/9N,
  - strip, pad and backfill self weight,
  - column / post base reactions (vertical force and the in-plane overturning moment from longitudinal shear).
Cases: characteristic (bearing, settlement), ULS uplift/overturning (favourable permanent x 0.9),
construction stage (wall absent, 0.75 W). Transverse pad moments are resisted by the pad width alone (strip torsion
ignored, conservative for the pad).
Outputs per line: peak bearing pressure under strip and pads, strip moments/shears vs capacity, pad lift-off,
uplift force actually transferred into the strip at each pad (= wall weight genuinely mobilised), settlement
and angular distortion.
"""
from __future__ import annotations
import json, math, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import s02cfg as C  # noqa: F401  (path set-up)
import foundations as F
import evaluate as EV
import model_b as MB

EC = 30e6            # kN/m2 short-term concrete modulus (C25/30)
CRACK = 0.5          # cracked-section stiffness factor
KS = {"G1": 50e3, "G2": 30e3, "G3": 12e3, "G3L": 12e3}      # kN/m3 modulus of subgrade reaction (assumed, ~1 m wide footings)
STRIPS = {           # strip options: b, h, top/bottom bars, links -> capacities (SANS 10100-1 / BS 8110 form)
    "SA": dict(b=0.60, h=0.45, bars=(3, 16), links=(10, 200), kgm3=75),     # S01 basis
    "SB": dict(b=0.60, h=0.60, bars=(4, 20), links=(10, 200), kgm3=115),
    "SC": dict(b=0.60, h=0.75, bars=(5, 20), links=(12, 200), kgm3=125),
}


def strip_caps(s, b=None):
    b = b or s["b"]
    n, dia = s["bars"]
    As = n * math.pi * dia ** 2 / 4
    d = s["h"] - 0.05 - 0.010 - dia / 2000
    z = min(0.95 * d, d * (0.5 + math.sqrt(max(0.25 - (0.87 * F.FY_R * As / 1e6) / (0.9 * F.FCU * b * d) / 2, 0))))
    Mr = 0.87 * F.FY_R * As * z / 1000          # kNm
    ld, sv = s["links"]
    Asv = 2 * math.pi * ld ** 2 / 4
    Vr = F.vc(As / b, d) * b * d * 1000 + 0.87 * F.FY_R * Asv / sv * d * 1000 / 1000
    return Mr, Vr, d


def line_geometry(line, bases, pads):
    """Return (x0, x1, list of base dicts with position s along the line)."""
    if line in ("S", "N"):
        side = 0 if line == "S" else 1
        sel = [(b, p) for b, p in zip(bases, pads) if b["kind"] == "column" and b["side"] == side]
        return MB.X_W, MB.X_E, [dict(s=b["x"], b=b, p=p) for b, p in sel]
    li = 0 if line == "W" else 10
    sel = [(b, p) for b, p in zip(bases, pads) if b["kind"] == "post" and b["line"] == li]
    cor = [(b, p) for b, p in zip(bases, pads) if b["kind"] == "column" and b["line"] == li]
    out = [dict(s=b["y"], b=b, p=p) for b, p in sel]
    # corner columns sit on the long-wall strips; the gable strip runs between them
    return 0.6, 32.4, out


def wall_w(line, s):
    """Characteristic masonry line load (kN/m) at position s, net of ground-level openings."""
    w = F.WALL_KN_M
    if line in ("S", "N"):
        ops = EV.OPEN_LONG[0 if line == "S" else 1]
    else:
        ops = EV.OPEN_GABLE[0 if line == "W" else 10]
    for a, z, h in ops:
        if a <= s <= z:
            w -= F.WALL_KN_M * min(h / 13.3, 1.0)
    return max(w, 0.0) * EV.WALL_FACTOR


def solve_line(line, items, case, R_of, soil, strip, wall_on=True, fperm=1.0, dx=0.1):
    """Beam on tensionless Winkler foundation. R_of(base) -> 6-vector reaction (ULS or char) for this case."""
    x0, x1 = items["x0"], items["x1"]
    n = int(round((x1 - x0) / dx))
    xs = np.linspace(x0, x1, n + 1)
    ks = KS[soil]
    gsoil = F.SOILS[soil]["gs"]
    s = STRIPS[strip]
    bS = s["b"] if soil not in ("G3", "G3L") else max(s["b"], 0.85)
    # element properties
    EI = np.full(n, EC * CRACK * bS * s["h"] ** 3 / 12)
    width = np.full(n + 1, bS)
    wdown = np.zeros(n + 1)       # kN/m downward distributed (wall + strip + soil)
    pad_of = np.full(n + 1, -1)
    for j, it in enumerate(items["bases"]):
        p = it["p"]
        Lp = p["L"] if line in ("S", "N") else p["B"]
        Bp = p["B"] if line in ("S", "N") else p["L"]
        m = np.abs(xs - it["s"]) <= Lp / 2 + 1e-9
        pad_of[m] = j
        width[m] = Bp
        me = np.abs((xs[:-1] + xs[1:]) / 2 - it["s"]) <= Lp / 2
        EI[me] = EC * CRACK * Bp * p["D"] ** 3 / 12
    soil_h = F.FGL - F.Z_TOP
    for i, x in enumerate(xs):
        if pad_of[i] >= 0:
            p = items["bases"][pad_of[i]]["p"]
            Bp = width[i]
            self_w = Bp * p["D"] * F.GC + max(Bp - 0.3, 0) * soil_h * gsoil
        else:
            self_w = bS * s["h"] * F.GC + max(bS - 0.3, 0) * soil_h * gsoil
        wdown[i] = fperm * (self_w + (wall_w(line, x) if wall_on else 0.0))
    nd = 2 * (n + 1)
    K = np.zeros((nd, nd))
    for e in range(n):
        L = dx
        k = EI[e] / L ** 3 * np.array([[12, 6 * L, -12, 6 * L], [6 * L, 4 * L * L, -6 * L, 2 * L * L],
                                       [-12, -6 * L, 12, -6 * L], [6 * L, 2 * L * L, -6 * L, 4 * L * L]])
        idx = [2 * e, 2 * e + 1, 2 * e + 2, 2 * e + 3]
        K[np.ix_(idx, idx)] += k
    P = np.zeros(nd)
    trib = np.full(n + 1, dx)
    trib[0] = trib[-1] = dx / 2
    P[0::2] -= wdown * trib
    for it in items["bases"]:
        R = R_of(it["b"])
        if R is None:
            continue
        i = int(round((it["s"] - x0) / dx))
        h = it["p"]["D"]
        N, Hx, Hy, Mxf, Myf = F.found_forces(R, h)
        extra = it.get("extra", 0.0) * fperm
        P[2 * i] -= N + extra
        Min = -Myf if line in ("S", "N") else Mxf       # in-plane moment of the wall beam (sign as derived in calc record)
        P[2 * i + 1] += Min
    ksp = ks * width * trib
    act = np.ones(n + 1, bool)
    for _ in range(60):
        Kt = K.copy()
        Kt[0::2, 0::2][np.diag_indices(n + 1)] += 0
        for i in range(n + 1):
            if act[i]:
                Kt[2 * i, 2 * i] += ksp[i]
        if not act.any():
            return dict(ok=False, why="no soil contact (net uplift of the whole line)")
        try:
            u = np.linalg.solve(Kt, P)
        except np.linalg.LinAlgError:
            return dict(ok=False, why="mechanism (line lifts off)")
        v = u[0::2]
        new = v < 0
        if (new == act).all():
            break
        act = new
    v = u[0::2]
    q = np.where(act, -v * ks, 0.0)                     # kPa contact pressure
    # element end forces
    M = np.zeros(n)
    V = np.zeros(n)
    for e in range(n):
        L = dx
        idx = [2 * e, 2 * e + 1, 2 * e + 2, 2 * e + 3]
        k = EI[e] / L ** 3 * np.array([[12, 6 * L, -12, 6 * L], [6 * L, 4 * L * L, -6 * L, 2 * L * L],
                                       [-12, -6 * L, 12, -6 * L], [6 * L, 2 * L * L, -6 * L, 4 * L * L]])
        f = k @ u[idx]
        V[e] = f[0]
        M[e] = -f[1]
    strip_e = np.array([pad_of[e] < 0 and pad_of[e + 1] < 0 for e in range(n)])
    out = dict(ok=True, q_strip=float(q[pad_of < 0].max()), q_pad=float(q[pad_of >= 0].max()),
               M_strip=float(np.abs(M[strip_e]).max()), V_strip=float(np.abs(V[strip_e]).max()),
               M_strip_hog=float(max(0.0, -M[strip_e].min())), M_strip_sag=float(max(0.0, M[strip_e].max())),
               settle_mm=float(-v.min() * 1000), lift_mm=float(max(v.max(), 0) * 1000))
    # per pad: lift-off, contact fraction, force transferred from the strip (= pad equilibrium residual)
    pads = []
    for j, it in enumerate(items["bases"]):
        m = pad_of == j
        ii = np.where(m)[0]
        soil_R = float((q[m] * width[m] * trib[m]).sum())
        load = float(-P[0::2][m].sum())                      # net downward applied on the pad nodes (+ = down)
        transfer = soil_R - load                             # + : strip pushes the pad down (mobilised weight)
        rot = (v[ii[-1]] - v[ii[0]]) / max(xs[ii[-1]] - xs[ii[0]], 1e-6)
        pads.append(dict(s=it["s"], key=it["key"], lift_mm=float(max(v[m].max(), 0) * 1000), contact=float(act[m].mean()),
                         transfer_kN=transfer, settle_mm=float(-v[m].mean() * 1000), net_applied_kN=load, rot=float(rot)))
    out["pads"] = pads
    # angular distortion between adjacent pads (settlement cases)
    if len(pads) > 1:
        ad = [abs(pads[k + 1]["settle_mm"] - pads[k]["settle_mm"]) / 1000 / abs(pads[k + 1]["s"] - pads[k]["s"]) for k in range(len(pads) - 1)]
        out["ang_dist"] = float(max(ad))
    return out


def analyse(rec, soil, strip, lines=("S", "N", "W", "E")):
    """Run every concurrent case on every wall line for one scheme record."""
    ev = EV.evaluate(rec, soil, "F2")
    if not ev.get("ok"):
        return dict(ok=False, why=ev.get("fail"))
    bases = rec["bases"]
    padmap = {(b["kind"], b["line"], b.get("side"), b.get("k")): b for b in ev["bases"]}
    pads, extras = [], []
    for b in bases:
        e = padmap[(b["kind"], b["line"], b.get("side"), b.get("k"))]
        pads.append(e["pad"])
    Mr, Vr, d = strip_caps(STRIPS[strip])
    res = dict(strip=strip, Mr=Mr, Vr=Vr, soil=soil, lines={})
    combos = list(bases[0]["R"].keys())
    uls_uplift = [c for c in combos if c.startswith("U5")]
    char = [c for c in combos if c.startswith("C ")]
    for line in lines:
        x0, x1, its = line_geometry(line, bases, pads)
        for it in its:
            b = it["b"]
            it["key"] = f"{b['kind']}-{b['line']}-{b.get('side', b.get('k'))}"
            it["extra"] = EV.LOGGIA_EXTRA.get((b["line"], b.get("side", -1)), 0.0) if b["kind"] == "column" else 0.0
        items = dict(x0=x0, x1=x1, bases=its)
        L = dict(uls=[], char=[], constr=[])
        for c in uls_uplift:
            L["uls"].append(dict(case=c, **solve_line(line, items, c, lambda b: b["R"][c], soil, strip, True, 0.9)))
        for c in char:
            L["char"].append(dict(case=c, **solve_line(line, items, c, lambda b: b["R"][c], soil, strip, True, 1.0)))
        # construction stage (no wall): 0.9G + 1.3 x 0.75 x W(q1.2), derived exactly as S01 split_cases
        for w in ("WSp", "WSn", "WNp", "WNn", "WWp", "WWn", "WEp", "WEn"):
            def Rc(b, w=w):
                a, bb = b["R"].get(f"C Gmin+W {w} q1.2"), b["R"].get(f"C Gmin+W {w} q0.85")
                Wv = [(x - y) / 0.35 for x, y in zip(a, bb)]
                Gm = [x - 1.2 * wv for x, wv in zip(a, Wv)]
                return [0.9 * g + 1.3 * 0.75 * 1.2 * wv for g, wv in zip(Gm, Wv)]
            L["constr"].append(dict(case=f"construction {w}", **solve_line(line, items, w, Rc, soil, strip, False, 0.9)))
        res["lines"][line] = L
    return res


def summarise(res):
    """Governing values per line and overall pass/fail."""
    S = dict(strip=res["strip"], soil=res["soil"], Mr=res["Mr"], Vr=res["Vr"], lines={})
    for line, L in res["lines"].items():
        g = {}
        for kind in ("uls", "char", "constr"):
            rr = [r for r in L[kind] if r.get("ok")]
            bad = [r for r in L[kind] if not r.get("ok")]
            if not rr:
                g[kind] = dict(fail=bad[0]["why"] if bad else "none")
                continue
            g[kind] = dict(M=max(r["M_strip"] for r in rr), V=max(r["V_strip"] for r in rr), q_strip=max(r["q_strip"] for r in rr),
                           q_pad=max(r["q_pad"] for r in rr), lift=max(max(p["lift_mm"] for p in r["pads"]) for r in rr),
                           min_contact=min(min(p["contact"] for p in r["pads"]) for r in rr),
                           transfer_max=max(max(p["transfer_kN"] for p in r["pads"]) for r in rr),
                           settle=max(r["settle_mm"] for r in rr), ang=max(r.get("ang_dist", 0) for r in rr), nfail=len(bad))
        S["lines"][line] = g
    return S


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("sweep")
    ap.add_argument("scheme")
    ap.add_argument("column")
    ap.add_argument("--soils", default="G1,G2,G3")
    ap.add_argument("--strips", default="SA,SB,SC")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    sw = json.load(open(a.sweep))["results"]
    rec = next(r for r in sw if r["scheme"] == a.scheme and r["column"] == a.column)
    rec["_tag"] = a.sweep
    allres = {}
    for soil in a.soils.split(","):
        for st in a.strips.split(","):
            r = analyse(rec, soil, st)
            if not r.get("lines"):
                allres[f"{soil}|{st}"] = r
                print(soil, st, r)
                continue
            s = summarise(r)
            allres[f"{soil}|{st}"] = dict(summary=s, detail=r)
            for ln, g in s["lines"].items():
                u, c, k = g["uls"], g["char"], g["constr"]
                print(f"{a.scheme} {soil} {st} Mr={s['Mr']:.0f} Vr={s['Vr']:.0f} {ln}: ULS M={u.get('M',0):.0f} V={u.get('V',0):.0f} lift={u.get('lift',0):.1f}mm "
                      f"transfer={u.get('transfer_max',0):.0f} | constr M={k.get('M',0):.0f} lift={k.get('lift',0):.1f} | char q_strip={c.get('q_strip',0):.0f} "
                      f"q_pad={c.get('q_pad',0):.0f} settle={c.get('settle',0):.1f} ang=1/{1/max(c.get('ang',1e-9),1e-9):.0f}", flush=True)
    json.dump(allres, open(a.out, "w"), default=float)
