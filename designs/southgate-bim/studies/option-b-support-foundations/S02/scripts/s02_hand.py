"""S02 independent hand calculations (written to S02/calcs/hand_S02.json):
 H1 wind basis - air density at Harare altitude, implied peak gust speeds
 H2 masonry side-wall panels - out-of-plane wind, slenderness, panel spanning, ties, movement joints
 H3 north-loggia transfer beams and the effect on columns 7N-9N
 H4 fixed-base anchorage (EN 1992-4 form) and base-plate checks for the governing S3 base
 H5 base rotational stiffness: connection (EN 1993-1-8 component form) in series with pad rotation on soil
Usage: python s02_hand.py <S02 sweep json> <scheme> <column>
"""
import json, math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import s02cfg as C
import sections as S
import foundations as F
import evaluate as EV
import model_b as MB

out = {}
sw = json.load(open(sys.argv[1]))["results"]
rec = next(r for r in sw if r["scheme"] == sys.argv[2] and r["column"] == sys.argv[3])
CAT = {s.name: s for s in S.COLUMNS + S.CHS}

# ---------------------------------------------------------------- H1 wind basis
alt = 1490.0          # m, Harare (approx. site altitude, to be confirmed by survey)
rho = 1.225 * (1 - 2.2558e-5 * alt) ** 4.2559       # ISA density
out["H1"] = dict(alt=alt, rho=rho, v_085=math.sqrt(2 * 850 / rho), v_120=math.sqrt(2 * 1200 / rho),
                 v_085_sea=math.sqrt(2 * 850 / 1.225), v_120_sea=math.sqrt(2 * 1200 / 1.225))

# ---------------------------------------------------------------- H2 masonry panels
t = 0.29             # m effective (300 mm nominal clay masonry, 290 actual assumed)
H_below = MB.SILL - MB.FFL           # 9.63 m solid wall below the clerestory sill
L_clear = 5.56 - 0.31                # clear span between column flanges
fkx_par, fkx_perp, gm = 0.3, 0.9, 3.0  # MPa characteristic flexural strengths (clay brick, mortar class ii, BS 5628 Table 3 form), gamma_m
q = 0.85
cp = 0.72 + 0.30                     # windward wall + internal suction
Wk = q * cp                          # kPa
Wd = 1.3 * Wk * 1.1                  # ULS incl. CC3 factor
Z = t ** 2 / 6
# horizontal spanning only (bed-joint direction strength fkx_perp), simply supported at the column ties
M_h = Wd * L_clear ** 2 / 8
cap_h = fkx_perp / gm * 1000 * Z
# vertical spanning only (fkx_par) over the 9.63 m solid height
M_v = Wd * H_below ** 2 / 8
cap_v = fkx_par / gm * 1000 * Z
# two-way panel: BS 5628-1 Table 9 alpha for a panel with h/L ~ 1.8, three/four edges restrained (approx.)
mu = fkx_par / fkx_perp
alpha = 0.035       # orthotropic coefficient, panel h/L = 1.84, mu = 0.33, simply supported 4 sides (BS 5628 Table 9, interpolated)
M_2w = alpha * Wd * L_clear ** 2
lim_area = 2025 * t ** 2             # BS 5628 / SANS 10164 limiting panel dimensions (4 edges supported)
out["H2"] = dict(t=t, H_below=H_below, L_clear=L_clear, Wk=Wk, Wd=Wd, M_h=M_h, cap_h=cap_h, M_v=M_v, cap_v=cap_v,
                 M_2w=M_2w, cap_2w=cap_h, panel_area=H_below * L_clear, lim_area=lim_area, lim_dim=50 * t,
                 slender_h_over_t=H_below / t, tie_force_per_m_height=Wd * L_clear / 2,
                 tie_force_at_600=Wd * L_clear / 2 * 0.6,
                 wall_weight_kNm=0.3 * 19 * 13.3, density_note="19 kN/m3 solid clay brick assumed; 0.7x sensitivity for hollow units")

# ---------------------------------------------------------------- H3 loggia transfer beams
z_head = 4.00
h_wall = MB.WALL_TOP - z_head - 0.45
wk = 0.3 * 19 * h_wall
beam = CAT["UB 457x191x82"]
plate_kg = 0.30 * 0.015 * 7850
g_beam = (beam.kg + plate_kg) * 9.81e-3
L = 5.56
wd = 1.35 * (wk + g_beam)
M = wd * L ** 2 / 8
V = wd * L / 2
Mr_restr = S.PHI * beam.Zpx * 355e3
Mr_lu = S.Mrx(beam, L, w2=1.13)
I_comp = beam.Ix + 0.30 * 0.015 * (beam.d / 2 + 0.0075) ** 2       # with soffit plate (approx., about beam centroid)
defl = 5 * (wk + g_beam) * L ** 4 / (384 * 200e6 * I_comp) * 1000
Vr = S.PHI * 0.66 * 355e3 * beam.d * 0.0099
# columns 7N, 8N, 9N: add the transfer reactions to the governing column check
col = CAT[rec["sections"]["COL"]]
colchk = []
for c in rec["cols"]:
    if c["side"] == 1 and c["line"] in (7, 8, 9):
        dN = (2 if c["line"] == 8 else 1) * V
        dMy = 0.0 if c["line"] == 8 else V * (0.0099 / 2 + 0.10)
        u0 = c["util"]
        u1, _ = S.beam_column(col, c["Cu"] + dN, c["Mux"], c["Muy"] + dMy, A_KLX := (MB.Z_COLTOP - MB.Z_BASE) * (0.85 if rec["scheme"] == "S3" else 1.0),
                              3.3, 3.3, w2=1.13)
        colchk.append(dict(line=c["line"], util_before=u0, util_after=u1, dN=dN, dMy=dMy))
out["H3"] = dict(z_head=z_head, h_wall=h_wall, wk=wk, beam=beam.name + " + 300x15 soffit plate", wd=wd, M=M, V=V, Mr_restr=Mr_restr,
                 Mr_unrestrained=Mr_lu, defl_mm=defl, defl_lim=L * 1000 / 500, Vr=Vr, steel_kg=2 * L * (beam.kg + plate_kg) + 4 * 35,
                 columns=colchk, pad_extra={str(k): v for k, v in EV.LOGGIA_EXTRA.items()})

# ---------------------------------------------------------------- H4 anchorage (governing S3 / S1 base)
ev = EV.evaluate(rec, "G2", "F2")
cols = [b for b in ev["bases"] if b["kind"] == "column"]
gov = max(cols, key=lambda b: b["base"]["T_row"])
bc, pad = gov["base"], gov["pad"]
dia, nb = bc["dia"], bc["n_bolts"]
n_side = nb // 2 if bc["type"] == "fixed" else 2
T = bc["T_row"]
As = {20: 245, 24: 353, 30: 561, 36: 817}[dia]
NRd_s = As * 800 / 1.5 / 1000                         # EN 1992-4 steel, grade 8.8, gamma_Ms 1.5
Ah = 80 * 80 - math.pi * dia ** 2 / 4                  # 80 x 80 anchor plate under the nut
NRd_p = 7.5 * Ah * 25 / 1.5 / 1000                    # pull-out, cracked, k2 7.5
hef = bc["hef"]
N0 = 8.9 * math.sqrt(25) * hef ** 1.5 / 1000
scr = 3 * hef
s_b = 150
Ac = (scr + (n_side - 1) * s_b) * scr
psi_s = 1.0
sec_ = CAT[rec["sections"]["COLC" if gov["line"] in (0, 10) else "COL"]]
z_lever = (sec_.d + 0.30) - 0.075 - 0.10
psi_M = max(1.0, 2 - z_lever / (1.5 * hef / 1000)) if bc["type"] == "fixed" else 1.0
NRd_c = N0 * Ac / scr ** 2 * psi_s * psi_M / 1.5
# splitting: may be ignored if h >= 2 hef and c >= 1.2 ccr,sp, or if reinforcement limits crack width (EN 1992-4 7.2.1.7)
h_pad = pad["D"] * 1000
split_ok_geom = h_pad >= 2 * hef
# supplementary (anchor) reinforcement: designed for the full row tension; legs within 0.75 hef; anchorage both sides
As_re = T * 1000 / (0.87 * F.FY_R)                    # mm2 total
n_legs = math.ceil(As_re / (math.pi * 16 ** 2 / 4))
lbd16 = 40 * 16                                        # mm, straight anchorage Y16 in C25/30 (good bond, approx.)
avail_below = h_pad - hef - 75
# base plate - tension T-stub (bolt row outside the flange) and compression zone on grout
m_ = 0.06
t_tension = math.sqrt(4 * (T / n_side) * m_ / (0.9 * 355e3 * 0.18)) * 1000
fjd = 0.67 * 25 * 1.5 / 1.5                           # MPa, grout/concrete bearing with confinement (beta_j 0.67, alpha 1.5)
c_ = None
t_plate = int(bc["plate_mm"].split("x")[-1])
c_ = t_plate / 1000 * math.sqrt(355 / (3 * fjd * 1.0))  # effective bearing width either side of the flange
out["H4"] = dict(base=f"{gov['kind']} line {gov['line']} side {gov['side']}", bolts=bc["bolts"], T_row=T, n_side=n_side, NEd_bolt=T / n_side,
                 NRd_s=NRd_s, NRd_p=NRd_p, NRd_c_group=NRd_c, psi_M=psi_M, cone_util=T / NRd_c, pad_D_mm=h_pad, hef=hef,
                 split_ok_geom=split_ok_geom, As_re=As_re, n_legs_Y16=n_legs, lbd16=lbd16, avail_below=avail_below,
                 t_tension_req=t_tension, t_plate=t_plate, c_bearing=c_, plate=bc["plate_mm"], env=gov["env"],
                 pad=pad, shear_key=bc["shear_key"])

# ---------------------------------------------------------------- H5 base rotational stiffness
E = 210e3
z = z_lever
leff_b = 0.455                                         # plate width
k13 = 30e3 * math.sqrt(0.25 * 0.455) / (1.275 * E) * 1000  # compression (mm) - EN 1993-1-8 Table 6.11 form, b_eff ~ 0.25 m
k15 = 0.425 * leff_b * 1000 * t_plate ** 3 / (m_ * 1000) ** 3
Lb = hef + 50 + t_plate + 30
k16 = 1.6 * As * n_side / Lb
Sj_ini = E * (z * 1000) ** 2 / (1 / k13 + 1 / k15 + 1 / k16) / 1e9   # kNm/rad -> E[N/mm2] z[mm]^2 k[mm] = Nmm/rad -> /1e6 kNm/rad
Sj_ini = E * (z * 1000) ** 2 / (1 / k13 + 1 / k15 + 1 / k16) / 1e6
ks = {"G1": 50e3, "G2": 30e3, "G3": 12e3}
B, Lp = pad["B"], pad["L"]
Kf = {k: v * Lp * B ** 3 / 12 for k, v in ks.items()}             # full contact
Ktot = {k: 1 / (1 / Sj_ini + 1 / (0.5 * v)) for k, v in Kf.items()}  # half effective contact under design moment
EIc = 200e6 * col.Ix
Lc = MB.Z_COLTOP - MB.Z_BASE
out["H5"] = dict(Sj_ini=Sj_ini, k13=k13, k15=k15, k16=k16, Kf=Kf, Ktot=Ktot, EI_over_L=EIc / Lc, rigid_threshold=30 * EIc / Lc,
                 ratio={k: v / (EIc / Lc) for k, v in Ktot.items()}, model_krx=rec.get("cfg", {}).get("krx"))
json.dump(out, open(C.S02 + f"/calcs/hand_{sys.argv[2]}.json", "w"), indent=1, default=float)
print(json.dumps(out, indent=1, default=lambda o: round(o, 3) if isinstance(o, float) else str(o))[:6000])
