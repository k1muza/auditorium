"""Section catalogue and member resistances (form of SANS 10162-1:2011, limit states, phi = 0.9).

Catalogue values are nominal published properties for BS 4-1 / SAISC UC and UB sections and EN 10219 CHS
(computed from D, t). They are suitable for preliminary sizing only; confirm against the supplier's tables
and mill certificates. Availability classes are study judgements, not supplier confirmations:
  'SA-stock'   : rolled in South Africa / commonly held by Harare and Johannesburg stockists
  'SA-order'   : rolled regionally, usually to order or in limited stock
  'import'     : not rolled regionally; import from outside SADC expected
"""
from __future__ import annotations
import math
from dataclasses import dataclass

E = 200e6       # kN/m2
G = 77e6
PHI = 0.9
N_CURVE = 1.34  # SANS 10162-1 cl 13.3.1, hot-rolled (n = 1.34)


@dataclass
class Sec:
    name: str
    family: str
    A: float      # m2
    Ix: float     # m4 strong
    Iy: float     # m4 weak
    Zpx: float    # m3 plastic strong
    Zpy: float    # m3 plastic weak
    J: float      # m4
    Cw: float     # m6
    kg: float     # kg/m
    d: float      # m depth
    b: float      # m width
    avail: str = "SA-stock"
    perim: float = 0.0   # m2/m paint area

    @property
    def rx(self):
        return math.sqrt(self.Ix / self.A)

    @property
    def ry(self):
        return math.sqrt(self.Iy / self.A)


def _I(name, A, Ix, Iy, Zpx, Zpy, J, Iw_dm6, kg, d, b, fam, avail):
    # Iw (dm6) -> m6 : 1 dm6 = 1e-6 m6
    return Sec(name, fam, A * 1e-4, Ix * 1e-8, Iy * 1e-8, Zpx * 1e-6, Zpy * 1e-6, J * 1e-8, Iw_dm6 * 1e-6, kg,
               d / 1000, b / 1000, avail, perim=(2 * d + 4 * b - 2 * 10) / 1000)


# name, A cm2, Ix cm4, Iy cm4, Zpx cm3, Zpy cm3, J cm4, Iw dm6, kg/m, d mm, b mm
UC = [_I(*r, "UC", av) for *r, av in [
    ("UC 203x203x46", 58.7, 4568, 1548, 497, 231, 22.2, 0.143, 46.1, 203.2, 203.6, "SA-stock"),
    ("UC 203x203x60", 76.4, 6125, 2065, 656, 305, 47.2, 0.197, 60.0, 209.6, 205.8, "SA-stock"),
    ("UC 203x203x71", 90.4, 7618, 2537, 799, 374, 80.2, 0.250, 71.0, 215.8, 206.4, "SA-stock"),
    ("UC 254x254x73", 93.1, 11410, 3908, 992, 465, 57.6, 0.562, 73.1, 254.1, 254.6, "SA-stock"),
    ("UC 254x254x89", 113, 14270, 4857, 1224, 575, 102, 0.717, 88.9, 260.3, 256.3, "SA-stock"),
    ("UC 254x254x107", 136, 17510, 5928, 1484, 701, 172, 0.898, 107.1, 266.7, 258.8, "SA-order"),
    ("UC 254x254x132", 168, 22530, 7531, 1869, 889, 319, 1.19, 132.0, 276.3, 261.3, "SA-order"),
    ("UC 305x305x97", 123, 22250, 7308, 1592, 726, 91.2, 1.56, 96.9, 307.9, 305.3, "SA-stock"),
    ("UC 305x305x118", 150, 27670, 9059, 1958, 895, 161, 1.98, 117.9, 314.5, 307.4, "SA-stock"),
    ("UC 305x305x137", 174, 32810, 10700, 2297, 1053, 249, 2.39, 136.9, 320.5, 309.2, "SA-order"),
    ("UC 305x305x158", 201, 38750, 12570, 2680, 1238, 378, 2.87, 158.1, 327.1, 311.2, "SA-order"),
    ("UC 356x368x129", 164, 40250, 14610, 2479, 1199, 153, 4.18, 129.0, 355.6, 368.6, "import"),
    ("UC 356x368x153", 195, 48590, 17550, 2965, 1435, 251, 5.11, 152.9, 362.0, 370.5, "import"),
    ("UC 356x368x177", 226, 57120, 20530, 3455, 1671, 381, 6.09, 177.0, 368.2, 372.6, "import"),
]]
UB = [_I(*r, "UB", av) for *r, av in [
    ("UB 356x171x67", 85.5, 19460, 1362, 1211, 243, 55.7, 0.412, 67.1, 363.4, 173.2, "SA-stock"),
    ("UB 406x178x60", 76.5, 21600, 1203, 1199, 209, 33.3, 0.465, 60.1, 406.4, 177.9, "SA-stock"),
    ("UB 406x178x74", 94.5, 27310, 1545, 1501, 267, 62.8, 0.608, 74.2, 412.8, 179.5, "SA-stock"),
    ("UB 457x191x67", 85.5, 29380, 1452, 1471, 237, 37.1, 0.705, 67.1, 453.4, 189.9, "SA-stock"),
    ("UB 457x191x82", 104, 37050, 1871, 1831, 304, 69.2, 0.922, 82.0, 460.0, 191.3, "SA-stock"),
    ("UB 533x210x82", 105, 47540, 2007, 2058, 300, 51.5, 1.33, 82.2, 528.3, 208.8, "SA-order"),
    ("UB 533x210x92", 117, 55230, 2389, 2360, 359, 75.7, 1.60, 92.1, 533.1, 209.3, "SA-order"),
    ("UB 610x229x101", 129, 75780, 2915, 2881, 393, 77.0, 2.52, 101.2, 602.6, 227.6, "SA-order"),
]]
COLUMNS = sorted(UC + UB, key=lambda s: s.kg)


def chs(D_mm, t_mm, avail="SA-stock"):
    D, t = D_mm / 1000, t_mm / 1000
    A = math.pi / 4 * (D ** 2 - (D - 2 * t) ** 2)
    I = math.pi / 64 * (D ** 4 - (D - 2 * t) ** 4)
    Zp = (D ** 3 - (D - 2 * t) ** 3) / 6
    return Sec(f"CHS {D_mm:g}x{t_mm:g}", "CHS", A, I, I, Zp, Zp, 2 * I, 0.0, A * 7850, D, D, avail, perim=math.pi * D)


CHS = [chs(*x) for x in [(48.3, 3), (60.3, 3), (76.1, 3), (88.9, 3.2), (101.6, 3.6), (114.3, 3.6), (114.3, 5), (139.7, 4.5),
                         (139.7, 6.3), (168.3, 5), (168.3, 6.3), (193.7, 6.3), (219.1, 6.3), (219.1, 8), (244.5, 8, "SA-order"),
                         (273, 8, "SA-order"), (323.9, 8, "SA-order"), (323.9, 10, "import")]]
CHS.sort(key=lambda s: s.kg)


def rod(d_mm):
    A = math.pi * (d_mm / 1000) ** 2 / 4
    return Sec(f"M{d_mm:g} rod", "ROD", A, 1e-12, 1e-12, 0, 0, 1e-12, 0, A * 7850, d_mm / 1000, d_mm / 1000, "SA-stock", perim=math.pi * d_mm / 1000)


# ------------------------------------------------------------------ resistances (kN, kNm)
def Cr(s: Sec, KLx, KLy, fy=355e3):
    lam = max(KLx / s.rx, KLy / s.ry)
    ln = lam * math.sqrt(fy / (math.pi ** 2 * E))
    return PHI * s.A * fy * (1 + ln ** (2 * N_CURVE)) ** (-1 / N_CURVE), lam


def Tr(s: Sec, fy=355e3, fu=470e3, net=0.85):
    return min(PHI * s.A * fy, 0.75 * net * s.A * fu)


def Mrx(s: Sec, Lu, w2=1.0, fy=355e3):
    """Strong-axis moment resistance incl. lateral-torsional buckling (SANS 10162-1 cl 13.6, class 1/2)."""
    Mp = s.Zpx * fy
    if s.family == "CHS" or Lu <= 0:
        return PHI * Mp
    Mu = w2 * math.pi / Lu * math.sqrt(E * s.Iy * G * s.J + (math.pi * E / Lu) ** 2 * s.Iy * s.Cw)
    if Mu > 0.67 * Mp:
        M = 1.15 * PHI * Mp * (1 - 0.28 * Mp / Mu)
        return min(M, PHI * Mp)
    return PHI * Mu


def Mry(s: Sec, fy=355e3):
    return PHI * s.Zpy * fy


def beam_column(s: Sec, Cu, Mux, Muy, KLx, KLy, Lu, w1=1.0, w2=1.0, fy=355e3):
    """SANS 10162-1 cl 13.8.2 interaction for class 1/2 I-sections (Cu compression positive).
    Returns governing utilisation and the components."""
    Cu = max(Cu, 0.0)
    cr_full, lam = Cr(s, KLx, KLy, fy)
    cr0 = PHI * s.A * fy
    cr_x, _ = Cr(s, KLx, 1e-6, fy)
    Cex = math.pi ** 2 * E * s.Ix / KLx ** 2
    Cey = math.pi ** 2 * E * s.Iy / max(KLy, 1e-6) ** 2
    U1x = max(1.0, w1 / (1 - Cu / Cex)) if Cu < Cex else 99
    U1y = max(1.0, w1 / (1 - Cu / Cey)) if Cu < Cey else 99
    mrx = PHI * s.Zpx * fy
    mry = Mry(s, fy)
    mrx_ltb = Mrx(s, Lu, w2, fy)
    beta = 0.6 + 0.4 * lam / 100 if s.family != "CHS" else 0.85   # cl 13.8.2 (simplified, <= 0.85)
    beta = min(beta, 0.85)
    a = Cu / cr0 + 0.85 * abs(Mux) / mrx + beta * abs(Muy) / mry
    b = Cu / cr_full + 0.85 * U1x * abs(Mux) / mrx + beta * U1y * abs(Muy) / mry
    c = Cu / cr_full + 0.85 * U1x * abs(Mux) / mrx_ltb + beta * U1y * abs(Muy) / mry
    d = abs(Mux) / mrx_ltb + abs(Muy) / mry
    return max(a, b, c, d), dict(xsec=a, overall=b, ltb=c, moment=d, lam=lam, Cr=cr_full, Mrx=mrx, MrxLTB=mrx_ltb)
