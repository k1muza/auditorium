"""3D analytical model of the Option B roof and its supporting structure (study model, not the IFC).

Geometry: verified against bim/southgate.ifc (sha256 6cb86f6d...) by s02/s03 extraction - truss lines at
x = 3.25 + 5.56 i, columns UC254x254x73 at y = 0.155 / 32.845 from z = -0.80 to +12.28, truss bearings at
y = 0.30 / 32.70 (TC heel z = 12.38, BC z = 10.90), purlins C200x75x20x2.5.
Option B truss: 12 panels @ 2.70 m, Warren with verticals, member sections from the R2 sizing run
(F-site-A-2000-astra-v2/studies/roof-truss-selection/work/study_results.json, option B, central, line 4/0),
read-only.

Schemes (all share the longitudinal system: gable wind posts, end-bay roof girders, end-bay cross frames,
bottom-chord ties, eaves struts and side-wall bracing in bays 1 and 5):
  S1  braced  : pinned bases; eaves wind girders (TC plane, 5.4 m deep) both sides; gable X-bracing;
                both truss bearings pinned (bolts finally tightened after dead load).
  S2  moment  : fixed bases (strong axis) + truss heel knee (TC and BC connected) at every line; no eaves
                girders, no gable transverse bracing.
  S3  hybrid  : as S1 but column bases fixed about the strong axis (propped-cantilever columns).
"""
from __future__ import annotations
import math
from dataclasses import dataclass, field
import numpy as np
from frame3d import Model, Prop
import sections as S

G_ACC = 9.81e-3
SPAN = 32.4
PITCH = math.radians(15.0)
Z_TC0, Z_BC, Z_BASE, Z_COLTOP = 12.38, 10.90, -0.80, 12.28
Y0 = 0.30
YC = (0.155, 32.845)
XL = [3.25 + 5.56 * i for i in range(11)]
NP = 12
PANEL = SPAN / NP
FFL, WALL_TOP = 0.27, 12.50
COL_Z = [-0.80, 0.90, 2.60, 4.30, 6.00, 7.90, 9.90, 10.90, 12.28]
SILL = 9.90
PIER = 1.08
WALL_BRACED_BAYS = (1, 5)
POST_K = (1, 3, 5, 7, 9, 11)           # gable posts at panel points s = 2.7, 8.1, ... 29.7 (clear of doors)
GABLE_BRACE = {0: ((3, 5), (7, 9)), 10: ((1, 3), (9, 11))}   # post pairs (west behind stage; east in stair cores)
POST_DX = {0: -0.20, 10: 0.20}
RIGID = 1e7


def z_top(s):
    return Z_TC0 + math.tan(PITCH) * min(s, SPAN - s)


# ------------------------------------------------------------------ double angles (R2 catalogue values)
ANG = {"L60x60x6": (6.91, 1.82, 1.69, 5.42), "L70x70x6": (8.13, 2.14, 1.93, 6.38), "L75x75x6": (8.73, 2.30, 2.05, 6.85),
       "L80x80x8": (12.3, 2.43, 2.26, 9.63), "L90x90x8": (13.9, 2.74, 2.50, 10.9), "L100x100x8": (15.5, 3.06, 2.74, 12.2)}


def dbl(name):
    A, rxx, e, kg = ANG[name]
    A2 = 2 * A * 1e-4
    Iin = A2 * (rxx * 1e-2) ** 2
    Iout = A2 * ((rxx * 1e-2) ** 2 + (e * 1e-2 + 0.005) ** 2)
    return Prop("2" + name, A2, Iy=Iin, Iz=Iout, J=2 * (A * 1e-4) * (0.008 ** 2) / 3, kg_m=2 * kg)


def B_sections(line):
    gable = line in (0, 10)
    return dict(TC=dbl("L80x80x8" if gable else "L90x90x8"), BC=dbl("L80x80x8"), VP=dbl("L70x70x6"), VK=dbl("L100x100x8"),
                V_short=dbl("L60x60x6"), V_long=dbl("L75x75x6"), D_end=dbl("L100x100x8"), D=dbl("L75x75x6"))


def prop_of(sec: S.Sec, strong_about="y"):
    """frame3d Prop from a catalogue section. For columns/posts the strong axis is mapped to local Iy."""
    return Prop(sec.name, sec.A, Iy=sec.Ix, Iz=sec.Iy, J=max(sec.J, 1e-9), kg_m=sec.kg)


PURLIN = Prop("C200x75x20x2.5", 9.5e-4, Iy=5.6e-6, Iz=0.8e-6, J=2e-9, kg_m=7.46)
# review O-2: purlin cleats are not designed as girder chords; in design runs the purlins are nominal links (0.1 % EA)
PURLIN_NOMINAL = Prop("C200x75x20x2.5 (nominal link)", 9.5e-7, Iy=5.6e-6, Iz=0.8e-6, J=2e-9, kg_m=7.46)


@dataclass
class Design:
    scheme: str = "S1"
    sec: dict = field(default_factory=dict)        # group -> catalogue Sec
    q_unit: float = 1.0
    minor_restraint: float = 3.3                    # m, masonry tie / bond-beam restraint to column minor axis (assumed)
    cladding: str = "masonry"                       # 'masonry' | 'light'
    base_krx: float = 0.0        # kNm/rad rotational base spring (0 = rigid when fixed)
    purlin_chords: bool = False   # purlins NOT relied on as girder chords (review O-2)


DEFAULT_GROUPS = {
    "COL": "UC 254x254x73", "COLC": "UC 254x254x73", "POST": "UB 406x178x60",
    "EAV": "CHS 139.7x4.5", "EGC": "CHS 139.7x4.5", "EGD": "CHS 114.3x3.6", "RBD": "CHS 114.3x3.6",
    "GBX": "CHS 139.7x4.5", "GBS": "CHS 114.3x3.6", "WBX": "CHS 168.3x5", "WBK": "CHS 168.3x5", "WBS": "CHS 168.3x5",
    "BCT": "CHS 76.1x3", "XF": "CHS 60.3x3", "BCB": "CHS 76.1x3",
}
CAT = {s.name: s for s in S.COLUMNS + S.CHS}


def default_design(scheme):
    return Design(scheme=scheme, sec={g: CAT[n] for g, n in DEFAULT_GROUPS.items()})


# ------------------------------------------------------------------ build
def build(d: Design):
    m = Model()
    sch = d.scheme
    braced_roof = sch in ("S1", "S3")
    T, B = {}, {}
    # trusses
    for i, x in enumerate(XL):
        sp = B_sections(i)
        for k in range(NP + 1):
            s = k * PANEL
            T[i, k] = m.node(x, Y0 + s, z_top(s), "T")
            B[i, k] = m.node(x, Y0 + s, Z_BC, "B")
        for k in range(NP):
            m.add(T[i, k], T[i, k + 1], sp["TC"], "beam", "TRUSS_TC", ref=(0, 0, 1), tag=dict(line=i, k=k))
            m.add(B[i, k], B[i, k + 1], sp["BC"], "beam", "TRUSS_BC", ref=(0, 0, 1), tag=dict(line=i, k=k))
        for k in range(NP + 1):
            p = sp["VP"] if k in (0, NP) else sp["VK"] if k == NP // 2 else (sp["V_long"] if 4 <= k <= 8 else sp["V_short"])
            m.add(B[i, k], T[i, k], p, "bar", "TRUSS_V", tag=dict(line=i, k=k))
        for k in range(NP):
            left = k < NP // 2
            j = k if left else k - NP // 2
            up = j % 2 == 0
            n1, n2 = (B[i, k], T[i, k + 1]) if up else (T[i, k], B[i, k + 1])
            p = sp["D_end"] if k in (0, 1, 10, 11) else sp["D"]
            m.add(n1, n2, p, "bar", "TRUSS_D", tag=dict(line=i, k=k))
    # columns
    C = {}
    for i, x in enumerate(XL):
        for side, yc in enumerate(YC):
            grp = "COLC" if i in (0, 10) else "COL"
            ids = [m.node(x, yc, z, "C") for z in COL_Z]
            for a, b in zip(ids[:-1], ids[1:]):
                m.add(a, b, prop_of(d.sec[grp]), "beam", grp, ref=(0, 1, 0), tag=dict(line=i, side=side))
            C[i, side] = ids
            fixed = sch in ("S2", "S3")
            if fixed and d.base_krx > 0:
                m.support(ids[0], [1, 1, 1, 0, 0, 1])
                g = m.node(x, yc, Z_BASE - 0.5, "GROUND")
                m.support(g, [1] * 6)
                m.add(ids[0], g, Prop("base-spring", 1.0), "spring", "BASESPRING", k6=(0, 0, 0, d.base_krx, 0, 0), tag=dict(line=i, side=side))
            else:
                m.support(ids[0], [1, 1, 1, 1 if fixed else 0, 0, 1])
            # truss bearing (TC heel) - translational springs
            kheel = T[i, 0] if side == 0 else T[i, NP]
            ky = RIGID
            # both bearings pinned: the roof props the column heads; Option B gravity spread is ~1-2 mm (R2),
            # so the resulting thrust is small and is reported (bolts tightened after roof dead load, see report)
            m.add(ids[-1], kheel, Prop("brg", 1.0), "spring", "BEARING", k6=(RIGID, ky, RIGID, 0, 0, 0), tag=dict(line=i, side=side))
            bheel = B[i, 0] if side == 0 else B[i, NP]
            if sch == "S2":
                m.add(ids[COL_Z.index(10.90)], bheel, Prop("knee", 1.0), "spring", "KNEE", k6=(RIGID, RIGID, 0, 0, 0, 0), tag=dict(line=i, side=side))
            elif i in (0, 10):
                # bottom-chord heel restraint cleat (out-of-plane only, slotted in y): added by this study after the
                # eigen-check showed the BC heel panels of the gable trusses buckling under uplift (alpha 0.22) without it
                m.add(ids[COL_Z.index(10.90)], bheel, Prop("heel", 1.0), "spring", "HEEL", k6=(RIGID, 0, 0, 0, 0, 0), tag=dict(line=i, side=side))
    # purlin struts (13 rows at panel points; rows replaced by girder chords where present)
    chord_rows = {0, NP} | ({2, NP - 2} if braced_roof else set())
    for i in range(10):
        for k in range(NP + 1):
            if k in (0, NP):
                m.add(T[i, k], T[i + 1, k], prop_of(d.sec["EAV"]), "bar", "EAV", tag=dict(bay=i, k=k))
            elif k in chord_rows:
                m.add(T[i, k], T[i + 1, k], prop_of(d.sec["EGC"]), "bar", "EGC", tag=dict(bay=i, k=k))
            else:
                m.add(T[i, k], T[i + 1, k], PURLIN if d.purlin_chords else PURLIN_NOMINAL, "bar", "PURLIN", tag=dict(bay=i, k=k))
    # eaves wind girders (S1/S3), TC plane, Warren diagonals in each bay, depth 2 panels (5.4 m)
    if braced_roof:
        for i in range(10):
            if i in (0, 9):
                continue                    # end bays covered by the end-bay roof girder
            for (ka, kb) in ((0, 2), (NP, NP - 2)):
                a, b = (T[i, ka], T[i + 1, kb]) if i % 2 == 0 else (T[i, kb], T[i + 1, ka])
                m.add(a, b, prop_of(d.sec["EGD"]), "bar", "EGD", tag=dict(bay=i))
    # end-bay roof girders (TC plane), cross frames, BC-plane bracing, BC ties
    for i in (0, 9):
        for k in range(NP):
            a, b = (T[i, k], T[i + 1, k + 1]) if k % 2 == 0 else (T[i, k + 1], T[i + 1, k])
            m.add(a, b, prop_of(d.sec["RBD"]), "bar", "RBD", tag=dict(bay=i, k=k))
        for k in (2, 4, 6, 8, 10):
            m.add(B[i, k], T[i + 1, k], prop_of(d.sec["XF"]), "bar", "XF", tag=dict(bay=i, k=k))
            m.add(T[i, k], B[i + 1, k], prop_of(d.sec["XF"]), "bar", "XF", tag=dict(bay=i, k=k))
        for k in (2, 4, 6, 8):
            a, b = (B[i, k], B[i + 1, k + 2]) if k % 4 == 2 else (B[i, k + 2], B[i + 1, k])
            m.add(a, b, prop_of(d.sec["BCB"]), "bar", "BCB", tag=dict(bay=i, k=k))
    for i in range(10):
        for k in (2, 4, 6, 8, 10):
            m.add(B[i, k], B[i + 1, k], prop_of(d.sec["BCT"]), "bar", "BCT", tag=dict(bay=i, k=k))
    # gable wind posts
    P = {}
    for i in (0, 10):
        x = XL[i] + POST_DX[i]
        for k in POST_K:
            s = k * PANEL
            zt = z_top(s)
            zs = [Z_BASE, 1.5, 3.8, 6.1, 8.4, 10.9, zt]
            ids = [m.node(x, Y0 + s, z, "P") for z in zs]
            for a, b in zip(ids[:-1], ids[1:]):
                m.add(a, b, prop_of(d.sec["POST"]), "beam", "POST", ref=(1, 0, 0), tag=dict(line=i, k=k))
            m.support(ids[0], [1, 1, 1, 0, 0, 1])
            braced_post = braced_roof and any(k in pair for pair in GABLE_BRACE[i])
            m.add(ids[-1], T[i, k], Prop("post-top", 1.0), "spring", "POSTTOP", k6=(RIGID, RIGID, 0, 0, 0, 0), tag=dict(line=i, k=k))
            P[i, k] = ids
    # gable transverse bracing (S1/S3): two-tier X between post pairs
    if braced_roof:
        for i in (0, 10):
            for ka, kb in GABLE_BRACE[i]:
                pa, pb = P[i, ka], P[i, kb]
                mid = 3   # node z = 6.1
                m.add(pa[0], pb[mid], prop_of(d.sec["GBX"]), "bar", "GBX", tag=dict(line=i))
                m.add(pb[0], pa[mid], prop_of(d.sec["GBX"]), "bar", "GBX", tag=dict(line=i))
                m.add(pa[mid], pb[-1], prop_of(d.sec["GBX"]), "bar", "GBX", tag=dict(line=i))
                m.add(pb[mid], pa[-1], prop_of(d.sec["GBX"]), "bar", "GBX", tag=dict(line=i))
                m.add(pa[mid], pb[mid], prop_of(d.sec["GBS"]), "bar", "GBS", tag=dict(line=i))
    # side-wall longitudinal bracing (all schemes): bays 1 and 5, below the clerestory with knee braces in the piers
    for bay in WALL_BRACED_BAYS:
        for side in (0, 1):
            ca, cb = C[bay, side], C[bay + 1, side]
            iz = COL_Z.index(SILL)
            xa, xb, yc = XL[bay], XL[bay + 1], YC[side]
            pa = m.node(xa + PIER, yc, SILL, "W")
            pb = m.node(xb - PIER, yc, SILL, "W")
            for a, b in ((ca[iz], pa), (pa, pb), (pb, cb[iz])):
                m.add(a, b, prop_of(d.sec["WBS"]), "beam", "WBS", ref=(0, 0, 1), tag=dict(bay=bay, side=side))
            m.add(ca[-1], pa, prop_of(d.sec["WBK"]), "bar", "WBK", tag=dict(bay=bay, side=side))
            m.add(cb[-1], pb, prop_of(d.sec["WBK"]), "bar", "WBK", tag=dict(bay=bay, side=side))
            m.add(ca[0], cb[iz], prop_of(d.sec["WBX"]), "bar", "WBX", tag=dict(bay=bay, side=side))
            m.add(cb[0], ca[iz], prop_of(d.sec["WBX"]), "bar", "WBX", tag=dict(bay=bay, side=side))
    m.T, m.B, m.C, m.P = T, B, C, P
    m.design = d
    return m


# ------------------------------------------------------------------ loads
ROOF_DEAD = 0.178          # kN/m2 plan: sheeting 0.060 + purlins 0.066 + insulation 0.040 + bracing allowance 0.012 (R2 load schedule)
SERVICES = 0.10            # kN/m2 plan, general suspended services (R2 central)
Q_ROOF = 0.25              # kN/m2 plan, inaccessible roof (SANS 10160-2 cat H, to verify)
SCEN = {"central": dict(arr=8.0, lx=0.40, raft=3.4, hvls=1.8, rfan=4.0, tray=0.25, dyn=0.20, cluster=0.0, ntray=2, catwalk=False),
        "future": dict(arr=16.0, lx=1.00, raft=6.8, hvls=2.5, rfan=6.0, tray=0.50, dyn=0.40, cluster=8.0, ntray=4, catwalk=True)}
# EN 1991-1-4 / SANS 10160-3 informative external pressure coefficients (cpe,10)
CPE_D, CPE_E = 0.72, -0.37          # long walls, wind normal to ridge, h/d ~ 0.44
CPE_GD, CPE_GE = 0.70, -0.30        # gables, wind parallel to ridge, h/d ~ 0.26
CPE_ABC = (-1.2, -0.8, -0.5)        # side walls, wind parallel, e = min(b, 2h) = 29 m
E_ZONE = 29.0
CPI = {"p": 0.2, "n": -0.3}     # sweep.py may override (dominant-opening sensitivities)
X_W, X_E = 3.10, 59.00


def _roof_profile(case, line):
    """Net roof coefficient (positive = downward) incl. cpi, as R2 (options_and_loads.wind_profile)."""
    edge = line in (0, 10)
    near = line in (1, 2, 8, 9)
    e10 = 3.38
    if case == "L_p":
        c = -1.5 if edge else (-0.8 if near else -0.7)
        return lambda s: c
    if case == "L_n":
        c = -1.0 if edge else (-0.3 if near else -0.2)
        return lambda s: c
    if case == "T_p":   # windward slope s <= 16.2 (wind from south)
        return lambda s: ((-0.85 - 0.2) if s < e10 - 0.45 else (-0.3 - 0.2)) if s <= 16.2 else ((-1.0 - 0.2) if s < 16.2 + e10 else (-0.4 - 0.2))
    if case == "T_n":
        return lambda s: (0.2 + 0.3) if s <= 16.2 else (0.0 + 0.3)
    raise KeyError(case)


def _hang(line, sc):
    """Bottom-chord hang loads (s, kN permanent, kN rigging) - R2 positions, snapped to panel points later."""
    out = []
    share = {1: (14.37 - 11.5) / 5.56, 2: (11.5 - 8.81) / 5.56}.get(line, 0.0)
    if share:
        for s in (7.3, 25.1):
            out.append((s, 0.0, sc["arr"] * share * (1 + sc["dyn"])))
    if line in (1, 2):
        w = sc["lx"] * 19.2
        for j in range(7):
            out.append((6.6 + 3.2 * j, 0.0, w / 7 * (1 + sc["dyn"])))
    if line == 2 and sc["cluster"]:
        out.append((16.2, 0.0, sc["cluster"] * (1 + sc["dyn"])))
    clamp = [2.86, 3.74, 4.62, 5.48, 6.36, 7.24, 14.01, 14.89, 15.77, 16.63, 17.51, 18.39, 25.16, 26.04, 26.92, 27.78, 28.66, 29.54]
    sides = sum(1 for b in (line - 1, line) if 2 <= b <= 6)
    for s in clamp:
        if sides:
            out.append((s, sc["raft"] / 12 * sides, 0.0))
    fans = sum(1 for b in (line - 1, line) if 3 <= b <= 6)
    for s in (10.65, 21.75):
        if fans:
            out.append((s, sc["hvls"] / 2 * fans, sc["hvls"] / 2 * fans * 0.5))
    for s in [8.0, 24.4] + ([12.0, 20.4] if sc["ntray"] == 4 else []):
        out.append((s, sc["tray"] * 5.56, 0.0))
    if sc["catwalk"]:
        out.append((16.2, 0.6 * 5.56, 1.5 * 5.56))
    return out


def _ridgefans(line, sc):
    n = sum(1 for b in (line - 1, line) if 1 <= b <= 8)
    return [(14.86, sc["rfan"] * n / 4), (17.54, sc["rfan"] * n / 4)] if n else []


def trib_x(i):
    lo = X_W if i == 0 else (XL[i - 1] + XL[i]) / 2
    hi = X_E if i == 10 else (XL[i] + XL[i + 1]) / 2
    return lo, hi


def wall_nodes_load(m, ids, wline, F, dof, zmax=WALL_TOP):
    """Distribute a wall line load wline (kN/m, as function of nothing) along a vertical chain between FFL and zmax."""
    zs = [m.xyz[n][2] for n in ids]
    for j, n in enumerate(ids):
        lo = (zs[j - 1] + zs[j]) / 2 if j else zs[0]
        hi = (zs[j] + zs[j + 1]) / 2 if j + 1 < len(zs) else zmax
        if j + 1 == len(zs):
            hi = max(hi, zmax)
        lo, hi = max(lo, FFL), min(hi, zmax)
        if hi > lo:
            F[6 * n + dof] += wline * (hi - lo)


def loads(m, scen="central"):
    """Characteristic load cases. Wind cases at q_p = 1 kPa."""
    sc = SCEN[scen]
    nd = 6 * len(m.xyz)
    L = {}

    def new(k):
        L[k] = np.zeros(nd)
        return L[k]

    G, GEQ, QR, QRIG = new("G"), new("GEQ"), new("QR"), new("QRIG")
    for e in m.elems:
        if e.kind == "spring":
            continue
        a, b = np.array(m.xyz[e.n1]), np.array(m.xyz[e.n2])
        w = e.prop.kg_m * np.linalg.norm(b - a) * G_ACC * (1.05 if e.group in ("COL", "COLC", "POST") else 1.08)
        G[6 * e.n1 + 2] -= w / 2
        G[6 * e.n2 + 2] -= w / 2
    for i in range(11):
        lo, hi = trib_x(i)
        bw = hi - lo
        for k in range(NP + 1):
            ds = PANEL / 2 if k in (0, NP) else PANEL
            ds += 0.30 if k in (0, NP) else 0.0      # eaves overhang to wall line
            A = ds * bw
            G[6 * m.T[i, k] + 2] -= ROOF_DEAD * A
            QR[6 * m.T[i, k] + 2] -= Q_ROOF * A
            GEQ[6 * m.B[i, k] + 2] -= SERVICES * PANEL * bw * (0.5 if k in (0, NP) else 1)
        for s, Pg, Pq in _hang(i, sc):
            k = int(round(s / PANEL))
            GEQ[6 * m.B[i, k] + 2] -= Pg
            QRIG[6 * m.B[i, k] + 2] -= Pq
        for s, P in _ridgefans(i, sc):
            k = int(round(s / PANEL))
            GEQ[6 * m.T[i, k] + 2] -= P
    # wind (q = 1 kPa) --------------------------------------------------------------------------
    d = m.design
    for dirn in ("S", "N", "W", "E"):
        for cp in ("p", "n"):
            W = new(f"W{dirn}{cp}")
            cpi = CPI[cp]
            # roof
            for i in range(11):
                lo, hi = trib_x(i)
                bw = hi - lo
                prof = _roof_profile(("T_" if dirn in "SN" else "L_") + cp, i if dirn in "SN" else (i if dirn == "W" else 10 - i))
                for k in range(NP + 1):
                    s = k * PANEL
                    s_eff = s if dirn != "N" else SPAN - s
                    ds = (PANEL / 2 + 0.30) if k in (0, NP) else PANEL
                    p = prof(s_eff) * ds * bw
                    sign = 1 if s < SPAN / 2 else (-1 if s > SPAN / 2 else 0)
                    W[6 * m.T[i, k] + 2] -= p
                    W[6 * m.T[i, k] + 1] += p * math.tan(PITCH) * sign
            # side walls -> columns (y direction)
            for i in range(11):
                lo, hi = trib_x(i)
                for side in (0, 1):
                    n_in = 1.0 if side == 0 else -1.0
                    if dirn in "SN":
                        windward = (dirn == "S" and side == 0) or (dirn == "N" and side == 1)
                        net = (CPE_D if windward else CPE_E) - cpi
                        wl = net * (hi - lo) * n_in
                    else:
                        # zone-weighted cpe along x from the windward gable
                        acc, nseg = 0.0, 40
                        for j in range(nseg):
                            x = lo + (hi - lo) * (j + 0.5) / nseg
                            dist = (x - X_W) if dirn == "W" else (X_E - x)
                            cpe = CPE_ABC[0] if dist < E_ZONE / 5 else (CPE_ABC[1] if dist < E_ZONE else CPE_ABC[2])
                            acc += (cpe - cpi) * (hi - lo) / nseg
                        wl = acc * n_in
                    wall_nodes_load(m, m.C[i, side], wl, W, 1)
            # gables -> posts and corner columns (x direction)
            for i in (0, 10):
                n_in = 1.0 if i == 0 else -1.0
                if dirn in "WE":
                    windward = (dirn == "W" and i == 0) or (dirn == "E" and i == 10)
                    net = (CPE_GD if windward else CPE_GE) - cpi
                else:
                    net = None    # gables parallel to the wind: zones A (within e/5 = 5.8 m of the windward wall) / B
                ks = list(POST_K)

                def gnet(s_mid):
                    if net is not None:
                        return net
                    dist = (s_mid + 0.30) if dirn == "S" else (SPAN + 0.30 - s_mid)
                    return (CPE_ABC[0] if dist < E_ZONE / 5 else CPE_ABC[1]) - cpi
                bounds = [0.0] + [(ks[j] + ks[j + 1]) / 2 * PANEL for j in range(len(ks) - 1)] + [SPAN]
                # corner columns take from the wall corner to half way to the first post
                for j, k in enumerate(ks):
                    lo_s = (ks[0] * PANEL) / 2 if j == 0 else bounds[j]
                    hi_s = SPAN - (ks[0] * PANEL) / 2 if j == len(ks) - 1 else bounds[j + 1]
                    wl = gnet(k * PANEL) * (hi_s - lo_s) * n_in
                    zt = z_top(k * PANEL) + 0.15
                    wall_nodes_load(m, m.P[i, k], wl, W, 0, zmax=zt)
                for side in (0, 1):
                    wc = gnet(0.0 if side == 0 else SPAN) * ((ks[0] * PANEL) / 2 + 0.30) * n_in
                    wall_nodes_load(m, m.C[i, side], wc, W, 0)
    # notional horizontal loads 0.005 x factored gravity (~1.35 x characteristic), SANS 10162-1 cl 8.7.2
    vert = G + GEQ + QRIG
    for nm, dof in (("NHY", 1), ("NHX", 0)):
        N = new(nm)
        N[dof::6] = -0.005 * 1.35 * vert[2::6]
    return L


def combos(qp_uls=(0.85, 1.20), qp_sls=0.85):
    """Return dict name -> (factors dict, kind)."""
    C = {}
    C["U1 1.35G"] = ({"G": 1.35, "GEQ": 1.35, "NHY": 1.0}, "ULS")
    C["U2 1.2G+1.6Qr"] = ({"G": 1.2, "GEQ": 1.2, "QR": 1.6, "NHY": 1.0}, "ULS")
    C["U3 1.2G+1.6Qrig"] = ({"G": 1.2, "GEQ": 1.2, "QRIG": 1.6, "NHY": 1.0}, "ULS")
    C["U3x 1.2G+1.6Qrig"] = ({"G": 1.2, "GEQ": 1.2, "QRIG": 1.6, "NHX": 1.0}, "ULS")
    C["U2x 1.2G+1.6Qr"] = ({"G": 1.2, "GEQ": 1.2, "QR": 1.6, "NHX": 1.0}, "ULS")
    for q in qp_uls:
        for w in ("WSp", "WSn", "WNp", "WNn", "WWp", "WWn", "WEp", "WEn"):
            nh = {"S": ("NHY", 1), "N": ("NHY", -1), "W": ("NHX", 1), "E": ("NHX", -1)}[w[1]]
            C[f"U4 1.2G+1.3W {w} q{q}"] = ({"G": 1.2, "GEQ": 1.2, w: 1.3 * q, nh[0]: nh[1]}, "ULS")
            C[f"U5 0.9G+1.3W {w} q{q}"] = ({"G": 0.9, w: 1.3 * q, nh[0]: nh[1] * 0.67}, "ULS")
    for w in ("WSp", "WSn", "WNp", "WNn", "WWp", "WWn", "WEp", "WEn"):
        C[f"S1 W {w} q{qp_sls}"] = ({w: qp_sls}, "SLS_W")   # deflection-limit basis
        C[f"S12 W {w} q1.2"] = ({w: 1.20}, "SLS_W12")
        C[f"C G+W {w} q1.2"] = ({"G": 1.0, "GEQ": 1.0, w: 1.20}, "CHAR")
        C[f"C Gmin+W {w} q1.2"] = ({"G": 1.0, w: 1.20}, "CHAR")
        C[f"C G+W {w} q0.85"] = ({"G": 1.0, "GEQ": 1.0, w: 0.85}, "CHAR")
        C[f"C Gmin+W {w} q0.85"] = ({"G": 1.0, w: 0.85}, "CHAR")
    C["C G+Qrig"] = ({"G": 1.0, "GEQ": 1.0, "QRIG": 1.0}, "CHAR")
    C["C G+Qr"] = ({"G": 1.0, "GEQ": 1.0, "QR": 1.0}, "CHAR")
    C["C G"] = ({"G": 1.0, "GEQ": 1.0}, "CHAR")
    return C
