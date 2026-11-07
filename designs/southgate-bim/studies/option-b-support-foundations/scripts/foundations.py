"""Preliminary foundation and anchorage design for the Option B support structure.

NOT FOR CONSTRUCTION. No site investigation exists; soil parameters are defined scenarios (G1-G3).
Concrete design in the form of SANS 10100-1 (BS 8110 basis): C25/30 (fcu 30 MPa), Y-bars fy 450 MPa.
Anchorage: cast-in headed anchors, concrete cone breakout in the form of EN 1992-4 (cracked, k1 = 8.9).
Load sign convention: reactions R from the 3D model (force ON the structure): Fz > 0 = compression into the footing.
"""
from __future__ import annotations
import math
from dataclasses import dataclass

GC, GS_STEEL = 24.0, 78.5           # kN/m3 concrete, steel
FCU, FCK, FY_R = 30.0, 25.0, 450.0  # MPa
COVER = 0.075                       # m, cast against blinding (SANS 10100 exposure: moderate)
Z_TOP = -0.80                       # m, top of pad = underside of base plate/grout (IFC)
FGL = 0.10                          # m, finished external ground level (assumed; FFL +0.265)

SOILS = {
    "G1": dict(label="G1 favourable: dense residual granite / gravelly sand", qa=200.0, gs=18.0, mu=0.45, dmin=1.0, gw=None, heave=False),
    "G2": dict(label="G2 moderate (base): stiff residual sandy clay", qa=150.0, gs=18.0, mu=0.35, dmin=1.2, gw=None, heave=False),
    "G3": dict(label="G3 poor: firm clay of intermediate plasticity, possibly expansive; perched water", qa=100.0, gs=17.0, mu=0.30,
               dmin=1.5, gw=-1.00, heave=True),   # design water level -1.00 (observed/assumed perched -1.40 + 0.4 m)
}
WALL_KN_M = 72.0      # kN/m characteristic: 300 mm brick masonry (19 kN/m3) x 13.3 m, less clerestory openings (assumption)
ENGAGE = 3.0          # m of wall engaged by a reinforced continuous strip at each column (F2), study assumption


@dataclass
class Pad:
    B: float      # across the wall (y) / plan dimension resisting Mx
    L: float      # along the wall (x)
    D: float      # thickness
    ok: bool = True
    gov: str = ""
    As_bot: float = 0.0   # mm2/m each way
    As_top: float = 0.0
    rebar_kg: float = 0.0
    notes: str = ""


def found_forces(R, h):
    """Footing actions at the founding level from a reaction vector R (Fx,Fy,Fz,Mx,My,Mz) on the structure.
    Returns N (down +), Hx, Hy, Mx_f, My_f (moments about the footing underside centre)."""
    Fx, Fy, Fz, Mx, My, Mz = R
    return Fz, Fx, Fy, -Mx + h * Fy, -My - h * Fx


def vc(As_mm2_per_m, d_m):
    rho = min(max(100 * As_mm2_per_m / (1000 * d_m * 1000), 0.15), 3.0)
    return 0.79 * rho ** (1 / 3) * max(400 / (d_m * 1000), 1.0) ** 0.25 / 1.25 * (FCU / 25) ** (1 / 3)   # MPa


def As_req(M_kNm_per_m, d):
    z = min(0.95 * d, d * (0.5 + math.sqrt(max(0.25 - M_kNm_per_m * 1e-3 / (0.9 * FCU * d * d), 0.0))))
    return M_kNm_per_m * 1e6 / (0.87 * FY_R * z * 1000)   # mm2/m


def bar_mass(As_mm2_per_m, span_m, width_m):
    return As_mm2_per_m * 1e-6 * width_m * (span_m - 2 * COVER) * 7850


def design_pad(cases_char, cases_uls, cases_constr, soil, col_b=0.30, wall_kNm=0.0, engaged=0.0, B_fixed=None,
               fixed_base=False, tied=False, D_min=0.45):
    """Search the cheapest B x L x D (concrete + rebar + excavation proxy) that passes all checks.
    cases_*: lists of (name, R) with R the 6-component base reaction. wall_kNm: wall load over the engaged length
    (characteristic) acting on the pad centreline; engaged: engaged wall length (m)."""
    s = SOILS[soil]
    cases_char, cases_uls, cases_constr = governing(cases_char), governing(cases_uls), governing(cases_constr)
    best = None
    for D in [0.45, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.2, 1.4, 1.6]:
        und = Z_TOP - D
        if FGL - und < s["dmin"] - 1e-6 or D < D_min - 1e-6:
            continue   # founding too shallow, or pad thinner than the anchor embedment + 150 mm
        for Lr in (1.0, 1.25, 1.5):
            for B in [x / 10 for x in range(8, 61)]:
                if B_fixed and abs(B - B_fixed) > 1e-6:
                    continue
                L = round(B * Lr, 2)
                res = check_pad(B, L, D, cases_char, cases_uls, cases_constr, s, col_b, wall_kNm, engaged, fixed_base, tied)
                if res.ok:
                    vol = B * L * D
                    exc = (B + 0.6) * (L + 0.6) * (FGL - und + 0.05)
                    cost = vol * 175 + res.rebar_kg * 1.65 + exc * 9 + 2 * (B + L) * D * 18
                    if best is None or cost < best[0]:
                        best = (cost, res)
                    break      # cost rises with B for a given D and aspect: first feasible B is the cheapest
    return best[1] if best else Pad(0, 0, 0, ok=False, gov="no solution in search range")


def governing(cases, keep=6):
    """Reduce a case list to the few that can govern a pad: max/min N, max |Mx|, max |My|, max |Mx|/N, max |H|."""
    if len(cases) <= keep:
        return cases
    sel = {}
    keys = [lambda R: R[2], lambda R: -R[2], lambda R: abs(R[3]) + abs(R[1]) * 0.8, lambda R: abs(R[4]) + abs(R[0]) * 0.8,
            lambda R: (abs(R[3]) + abs(R[1]) * 0.8) / max(R[2], 1.0), lambda R: math.hypot(R[0], R[1])]
    for k in keys:
        n, R = max(cases, key=lambda c: k(c[1]))
        sel[n] = R
    return list(sel.items())


def check_pad(B, L, D, cases_char, cases_uls, cases_constr, s, col_b, wall_kNm, engaged, fixed_base, tied):
    und = Z_TOP - D
    h = D                                    # lever arm base-plate level -> underside
    soil_h = max(FGL - Z_TOP, 0.0)           # backfill over the pad (column passes through)
    buoy = s["gw"] is not None and s["gw"] >= und
    gc = GC - (10.0 if buoy else 0.0)
    gs = s["gs"] - (10.0 if buoy else 0.0)
    Wf = B * L * D * gc
    Ws = B * L * soil_h * gs
    Ww = wall_kNm
    r = Pad(B, L, D)
    # 1 bearing (characteristic), Meyerhof effective area
    qmax_net = 0.0
    for nm, R in cases_char:
        N, Hx, Hy, Mxf, Myf = found_forces(R, h)
        Nt = N + Wf + Ws + Ww
        if Nt <= 0:
            r.ok, r.gov = False, f"net uplift under characteristic {nm}"
            return r
        ex, ey = abs(Myf) / Nt, abs(Mxf) / Nt         # Mx rotates about x -> eccentricity across B (y)
        if ey > B / 3 or ex > L / 3:
            r.ok, r.gov = False, f"eccentricity > B/3 ({nm})"
            return r
        q = Nt / ((B - 2 * ey) * (L - 2 * ex))
        if q > s["qa"] + gs * (FGL - und):           # allowable is net; add overburden for gross comparison
            r.ok, r.gov = False, f"bearing {q:.0f} kPa ({nm})"
            return r
    # 2 uplift and overturning (EQU, ULS factored actions, favourable permanent x 0.9)
    for nm, R in list(cases_uls) + [(n + " [construction, no wall]", Rc) for n, Rc in cases_constr]:
        constr = "construction" in nm
        N, Hx, Hy, Mxf, Myf = found_forces(R, h)
        stab = 0.9 * (Wf + Ws + (0 if constr else Ww))
        if N + stab < 0:
            r.ok, r.gov = False, f"uplift ({nm})"
            return r
        Nt = N + stab
        if abs(Mxf) > Nt * B / 2 or abs(Myf) > Nt * L / 2:
            r.ok, r.gov = False, f"overturning ({nm})"
            return r
        Hres = math.hypot(Hx, Hy)
        if Hres > s["mu"] * max(Nt, 0) and not tied:
            r.notes = "shear key / tie required for sliding"
    # 3 structural design: worst ULS soil pressure (compression cases) across B and along L
    d = D - COVER - 0.016
    Mu_y, Mu_up, Vmax_ratio = 0.0, 0.0, 0.0
    for nm, R in cases_uls:
        N, Hx, Hy, Mxf, Myf = found_forces(R, h)
        Nt = N + 1.2 * (Wf + Ws + Ww)
        if Nt > 0:
            ey = min(abs(Mxf) / Nt, B / 2.2)
            Be = max(B - 2 * ey, 0.3)
            q = Nt / (Be * L)
            a = (B - col_b) / 2
            Mu_y = max(Mu_y, q * min(a, Be) ** 2 / 2 - 1.2 * (Wf + Ws) / (B * L) * a * a / 2)   # kNm per m width
            # one-way shear at d from face
            av = max(a - d, 0.0)
            V = q * min(av, Be)
            Vmax_ratio = max(Vmax_ratio, V / (1000 * d) / 1.0)
            # punching at 1.5d perimeter (BS 8110)
            u = 4 * (col_b + 3 * d)
            Vp = max(N - q * (col_b + 3 * d) ** 2, 0.0)
            if Vp > 0:
                Vp *= 1 + 1.5 * abs(Mxf) / (Vp * (col_b + 3 * d))
            vp = Vp * 1e3 / (u * 1000 * d * 1000)
            As_min = 0.0013 * 1000 * D * 1000
            if vp > vc(As_min, d) * 1.0 + 1e-9 and vp > 0:
                As_need = As_min
                while vp > vc(As_need, d) and As_need < 0.02 * 1000 * d * 1000:
                    As_need *= 1.2
                if vp > vc(As_need, d):
                    r.ok, r.gov = False, f"punching ({nm})"
                    return r
        else:
            # hogging from footing + soil weight held down by uplift at the column
            a = (B - col_b) / 2
            Mu_up = max(Mu_up, 1.2 * (Wf + Ws + Ww) / (B * L) * a * a / 2)
    As_min = 0.0013 * 1000 * D * 1000
    r.As_bot = max(As_req(Mu_y, d), As_min)
    # one-way shear: increase steel or fail
    if Vmax_ratio > vc(r.As_bot, d) * 1.0:
        As_v = r.As_bot
        while Vmax_ratio > vc(As_v, d) and As_v < 0.02 * 1e6 * d:
            As_v *= 1.15
        if Vmax_ratio > vc(As_v, d):
            r.ok, r.gov = False, "one-way shear"
            return r
        r.As_bot = As_v
    r.As_top = max(As_req(Mu_up, d), As_min * 0.6 if (fixed_base or Mu_up > 0) else 0.0)
    r.rebar_kg = 1.10 * (bar_mass(r.As_bot, B, L) + bar_mass(r.As_bot, L, B) + bar_mass(r.As_top, B, L) + bar_mass(r.As_top, L, B))
    return r


# ------------------------------------------------------------------ holding-down and base plates
def bolt_tr(dia):
    An = {20: 245, 24: 353, 30: 561, 36: 817}[dia]
    return 0.75 * 0.8 * An * 830 / 1000          # kN, grade 8.8 (SANS 10162-1 cl 13.12.1.3 form)


def bolt_vr(dia):
    Ab = math.pi * dia ** 2 / 4
    return 0.8 * 0.6 * Ab * 830 / 1000 * 0.7     # kN, threads in shear plane, grout gap reduction 0.7 (assumed)


def cone_breakout(hef_mm, n_side, s_mm, edge_mm=400):
    """EN 1992-4 concrete cone resistance (design, kN) of a row/group of n_side headed anchors in tension."""
    N0 = 8.9 * math.sqrt(FCK) * hef_mm ** 1.5 / 1000
    scr = 3 * hef_mm
    width = min(scr, 2 * edge_mm) + (n_side - 1) * s_mm if n_side > 1 else min(scr, 2 * edge_mm)
    Ac = width * min(scr, 2 * edge_mm)
    A0 = scr * scr
    psi_s = min(1.0, 0.7 + 0.3 * edge_mm / (1.5 * hef_mm))
    return N0 * Ac / A0 * psi_s / 1.5


def base_connection(fixed, sec_d, sec_b, uplift_kN, M_kNm, N_comp_kN, H_kN, pairs=None):
    """Concept holding-down arrangement. pairs: list of concurrent (N, M, H) from the ULS combinations
    (N > 0 compression) - the tension row is designed for the worst concurrent pair (review O-1)."""
    pairs = pairs or [(N_comp_kN, M_kNm, H_kN), (-uplift_kN, M_kNm, H_kN)]
    if not fixed:
        plate = (round(sec_d + 0.15, 2), round(sec_b + 0.15, 2))
        nb, dia = 4, 24
        if uplift_kN / nb > bolt_tr(24) * 0.9:
            dia = 30
        Tb = uplift_kN / nb
        hef = 300
        while cone_breakout(hef, 2, 150) * 2 < uplift_kN and hef < 450:
            hef += 75
        cone = uplift_kN / (2 * cone_breakout(hef, 2, 150)) if uplift_kN > 0 else 0.0
        anchor_reinf = uplift_kN * 1000 / (0.87 * FY_R) * 1e-6 * 2 * 1.4 * 7850 if cone > 1.0 else 0.0
        t = 25 if Tb < 60 else 30
        key = any(N < 0 and H > 10 for N, M, H in pairs) or any(H > 0.2 * max(N, 0) for N, M, H in pairs if N >= 0 and H > 25)
        return dict(type="pinned", plate_mm=f"{plate[0]*1000:.0f} x {plate[1]*1000:.0f} x {t}", plate_kg=plate[0] * plate[1] * t / 1000 * 7850,
                    bolts=f"{nb} M{dia} 8.8 cast-in, hef {hef} mm", n_bolts=nb, dia=dia, hef=hef, bolt_util=Tb / bolt_tr(dia),
                    cone_util=cone, shear_key=key, anchor_reinf_kg=anchor_reinf, grout_m3=plate[0] * plate[1] * 0.04, T_row=uplift_kN / 2,
                    anchor_reinf=("designed hairpins (cone utilisation %.2f without)" % cone) if anchor_reinf else "not required")
    plate_d = sec_d + 0.30
    plate_b = sec_b + 0.15
    z = plate_d - 0.075 - 0.10
    T = 0.0
    for N, M, H in pairs:
        M = abs(M)
        t_ = (M - N * z / 2) / z if N >= 0 else M / z + (-N) / 2
        T = max(T, t_)
    best = None
    for dia in (24, 30, 36):
        for n_side in (2, 3, 4):
            if T / n_side <= bolt_tr(dia):
                best = (dia, n_side)
                break
        if best:
            break
    dia, n_side = best or (36, 4)
    hef = 375
    while cone_breakout(hef, n_side, 150) < T and hef < 450:
        hef += 75
    cone = T / cone_breakout(hef, n_side, 150)
    anchor_reinf = T * 1000 / (0.87 * FY_R) * 1e-6 * 2 * 1.4 * 7850 if cone > 1.0 else 0.0   # hairpins, 2 legs x 1.4 m
    m_ = 0.06
    t = max(30, math.ceil(math.sqrt(4 * (T / n_side) * m_ * 1e3 / (0.9 * 355 * 0.18)) / 5) * 5)
    nb = 2 * n_side
    key = any(N < 0 and H > 10 for N, M, H in pairs) or any(H > 0.2 * max(N, 0) + 1e-9 for N, M, H in pairs if H > 25)
    return dict(type="fixed", plate_mm=f"{plate_d*1000:.0f} x {plate_b*1000:.0f} x {t}", plate_kg=plate_d * plate_b * t / 1000 * 7850 * 1.15,
                bolts=f"{nb} M{dia} 8.8 cast-in with anchor plates, hef {hef} mm", n_bolts=nb, dia=dia, hef=hef, T_row=T,
                bolt_util=T / n_side / bolt_tr(dia), cone_util=cone, anchor_reinf_kg=anchor_reinf,
                shear_key=key, grout_m3=plate_d * plate_b * 0.05,
                anchor_reinf=("designed hairpins (cone utilisation %.2f without)" % cone) if anchor_reinf else "not required",
                stiffeners="4 No. 15 mm gusset stiffeners (concept)")
