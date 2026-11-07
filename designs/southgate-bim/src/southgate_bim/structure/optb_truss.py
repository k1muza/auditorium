"""Option B roof truss - construction geometry engine (no IFC).

Builds, for one truss line, every fabricated component of the R2 Option B truss:
12-bay Warren with verticals, paired back-to-back equal angles bolted to 10 mm gussets.

Coordinates
  in-plane 2D (s, z): s = y - 0.30 (horizontal distance from the south bearing), z = absolute level (m)
  world 3D: x = truss line x + offset normal to the truss plane, y = 0.30 + s, z
  truss plane normal n = +x; angle "A" is on the +x side, angle "B" on the -x side.

Every rule used here comes from config/option_b/detailing_rules.yaml, which states its status
(R2 / MODEL / PLACEHOLDER). Nothing in this module is an engineered connection design.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field, asdict
from pathlib import Path

import numpy as np
import yaml
from shapely.geometry import Polygon, Point, LineString, box
from shapely.ops import unary_union
from shapely import affinity

ROOT = Path(__file__).resolve().parents[3]
TAN15, COS15, SIN15 = math.tan(math.radians(15)), math.cos(math.radians(15)), math.sin(math.radians(15))
SPAN, PANEL, NB = 32.4, 2.70, 12
Y0 = 0.30


def load_rules():
    rules = yaml.safe_load(open(ROOT / "config/option_b/detailing_rules.yaml", encoding="utf-8"))
    basis = json.load(open(ROOT / "config/option_b/r2_basis.json", encoding="utf-8"))
    return rules, basis


# --------------------------------------------------------------------------------------------- basics
def v2(x, z):
    return np.array([float(x), float(z)])


def rot90(a):
    """in-plane perpendicular p = n x a  (n = +x):  a = (a_s, a_z) -> p = (-a_z, a_s)"""
    return np.array([-a[1], a[0]])


def rect(origin, a, p, t0, t1, q0, q1):
    """Rectangle {origin + t a + q p : t in [t0,t1], q in [q0,q1]} as a shapely polygon in (s, z)."""
    qa, qb = min(q0, q1), max(q0, q1)
    ta, tb = min(t0, t1), max(t0, t1)
    pts = [origin + ta * a + qa * p, origin + tb * a + qa * p, origin + tb * a + qb * p, origin + ta * a + qb * p]
    return Polygon([tuple(x) for x in pts])


def half_plane(origin, normal, size=50.0):
    """Polygon approximating {x : (x - origin) . normal >= 0}."""
    nrm = normal / np.linalg.norm(normal)
    tng = rot90(nrm)
    o = np.asarray(origin)
    pts = [o - size * tng, o + size * tng, o + size * tng + size * nrm, o - size * tng + size * nrm]
    return Polygon([tuple(x) for x in pts])


@dataclass
class AngleSec:
    name: str
    b: float
    t: float
    r1: float
    r2: float
    A: float      # m2 (catalogue)
    e: float      # m centroid distance from heel face
    kg_m: float
    gauge: float  # m
    max_bolt: str

    @staticmethod
    def from_rules(name, rules):
        c = rules["angles"][name]
        return AngleSec(name, c["b"] / 1000, c["t"] / 1000, c["r1"] / 1000, c["r2"] / 1000, c["A_cm2"] * 1e-4,
                        c["e_cm"] / 100, c["kg_m"], c["gauge"] / 1000, c["max_bolt"])


# --------------------------------------------------------------------------------------------- data model
@dataclass
class Angle:
    id: str
    member: str
    side: str            # "A" (+x) or "B" (-x)
    section: str
    origin: list         # world xyz of the bounding-box centre of the profile at the start cut
    axis_z: list         # member direction
    axis_x: list         # profile x direction
    length: float
    heel_start: list     # world xyz of the heel corner at the start cut (for audit)


@dataclass
class Member:
    id: str
    role: str            # TC BC VP V VK D
    group: str           # R2 group (TC BC VP V VK D)
    section: str
    n1: str
    n2: str
    psi: int
    t_start: float       # along-axis position of the start cut measured from node n1 (m)
    t_end: float         # along-axis position of the end cut measured from node n1 (m)
    a: list              # unit in-plane direction n1 -> n2
    p: list
    node1_sz: list
    node2_sz: list
    length: float
    angles: list = field(default_factory=list)
    packers: list = field(default_factory=list)
    r2_force: dict = field(default_factory=dict)
    piece_of: str = ""   # for chords: which panel nodes the piece covers


@dataclass
class Plate:
    id: str
    kind: str            # GUSSET SPLICE PACKER
    thickness: float
    x0: float            # world x of the plate face with the lowest x (plate extruded +x by thickness)
    outline_sz: list     # in-plane polygon (s, z) - gussets/splices; packers use centre/axis instead
    holes_sz: list       # [(s, z, diameter)]
    joint: str = ""
    member: str = ""
    centre_sz: list = None
    axis_sz: list = None
    size: list = None    # packers: [length along axis, width across]
    rigging_tab: bool = False


@dataclass
class Bolt:
    id: str
    diameter: str        # M20 / M16
    s: float
    z: float
    x_head: float        # world x offset (from truss plane) of the head bearing face (+x side)
    grip: float
    length: float
    stack: list          # component ids it passes through (+x to -x)
    joint: str = ""
    member: str = ""
    role: str = ""       # WEB CHORD SPLICE PACKER


@dataclass
class Joint:
    id: str
    node: str
    family: str          # CT-BH CT-TH CT-BS CT-BC CT-BV CT-TV2 CT-TS CT-TA
    s: float
    z: float
    members: list        # [(member id, end 1|2)]
    gusset: str = ""
    splice_plates: list = field(default_factory=list)
    bolts: list = field(default_factory=list)
    splice: bool = False
    rigging_tab: bool = False
    interfaces: list = field(default_factory=list)
    r2_forces: dict = field(default_factory=dict)
    type_key: str = ""


# --------------------------------------------------------------------------------------------- the truss
class OptionBTruss:
    def __init__(self, line: int, rules=None, basis=None):
        self.rules, self.basis = (rules, basis) if rules else load_rules()
        R = self.rules
        self.line = line
        self.x = R["setting_out"]["truss_x_m"]["value"][line]
        self.ttype = next(k for k, v in R["truss_types"].items() if line in v["lines"])
        self.sec_line = R["truss_types"][self.ttype]["sections_from_line"]
        self.force_line = R["force_basis_line"][str(line)]
        A = R["assembly"]
        self.gap = A["gap_between_angles_m"]["value"]
        self.fit = A["fit_up_clearance_m"]["value"]
        self.jgap = A["chord_joint_gap_m"]["value"]
        self.inset = A["gusset_inset_from_chord_face_m"]["value"]
        P = R["plates"]
        self.t_g = P["gusset_thickness_m"]["value"]
        self.t_sp = P["splice_plate_thickness_m"]["value"]
        self.t_pk = P["packer_thickness_m"]["value"]
        self.tab = P["rigging_tab"]
        self.rigging = line in self.tab["lines"]
        self.bolt_cfg = R["bolts"]["diameters"]
        self.pk_max = R["packers"]["max_spacing_m"]["value"]
        self.z_bc = R["setting_out"]["bottom_chord_centroid_z_m"]["value"]
        self.tos_perp = R["setting_out"]["top_of_steel_perp_offset_m"]["value"]
        sec = self.basis["analysed_lines"][self.sec_line]
        self.sec_tc = AngleSec.from_rules(sec["chord_sections"]["TC"][0][1:], R)
        self.sec_bc = AngleSec.from_rules(sec["chord_sections"]["BC"][0][1:], R)
        self.webs_r2 = sec["webs"]
        self.forces = self.basis["analysed_lines"][self.force_line]
        self.members: dict[str, Member] = {}
        self.plates: dict[str, Plate] = {}
        self.bolts: dict[str, Bolt] = {}
        self.joints: dict[str, Joint] = {}
        self.nodes: dict[str, np.ndarray] = {}
        self.tid = f"T{line + 1:02d}"
        self.issues = []
        self._build()

    # ----------------------------------------------------------------------- setting-out
    def z_tos(self, s):
        return 12.380 + TAN15 * min(s, SPAN - s) + self.tos_perp / COS15

    def z_tc(self, s):
        return self.z_tos(s) - self.sec_tc.e / COS15

    def sid(self, *parts):
        return "SOUTHGATE-RTB-" + "-".join([self.tid] + [str(p) for p in parts])

    def _build(self):
        sk = [round(PANEL * k, 6) for k in range(NB + 1)]
        for k, s in enumerate(sk):
            self.nodes[f"B{k:02d}"] = v2(s, self.z_bc)
            self.nodes[f"T{k:02d}"] = v2(s, self.z_tc(s))
        self._webs()
        self._chords()
        self._joints_setback()
        self._finalise_members()
        self._connections()
        self._packers()

    # ----------------------------------------------------------------------- members
    def _web_force(self, grp, s1, s2):
        for w in self.forces["webs"]:
            if abs(w["s1"] - s1) < 1e-3 and abs(w["s2"] - s2) < 1e-3:
                return {"Nc_kN": w["Nc_kN"], "Nt_kN": w["Nt_kN"], "util": w["util"], "lam": w["lam"], "group": w["group"]}
        raise KeyError((grp, s1, s2))

    def _webs(self):
        """Webs exactly as R2 (options_and_loads.build_panelled('warren', 12))."""
        half = NB // 2
        for w in self.webs_r2:
            s1, s2 = w["s1"], w["s2"]
            k1, k2 = round(s1 / PANEL), round(s2 / PANEL)
            if w["group"] in ("VP", "V", "VK"):
                n1, n2 = f"B{k1:02d}", f"T{k1:02d}"
                mid = f"V{k1:02d}"
                psi = -1 if s1 < SPAN / 2 - 1e-6 else (+1 if s1 > SPAN / 2 + 1e-6 else -1)   # connected leg towards mid-span
                role = w["group"]
            else:
                n1, n2 = f"{w['end1']}{k1:02d}", f"{w['end2']}{k2:02d}"
                mid = f"D{k1:02d}"
                psi = +1
                role = "D"
            a = self.nodes[n2] - self.nodes[n1]
            a = a / np.linalg.norm(a)
            m = Member(mid, role, w["group"], w["section"][1:], n1, n2, psi, 0.0, 0.0, a.tolist(), rot90(a).tolist(),
                       self.nodes[n1].tolist(), self.nodes[n2].tolist(), 0.0)
            m.r2_force = self._web_force(w["group"], s1, s2)
            self.members[mid] = m
        assert sum(1 for m in self.members.values() if m.role != "D") == NB + 1
        assert sum(1 for m in self.members.values() if m.role == "D") == NB

    def _chords(self):
        """6 BC pieces + 6 TC pieces, each spanning two panels; splices at s = 5.4, 10.8, 16.2, 21.6, 27.0."""
        e_vp = AngleSec.from_rules(self.members["V00"].section, self.rules).e
        self.e_vp = e_vp
        cuts = [0, 2, 4, 6, 8, 10, 12]
        for i in range(6):
            ka, kb = cuts[i], cuts[i + 1]
            n1, n2 = f"B{ka:02d}", f"B{kb:02d}"
            a = v2(1, 0)
            m = Member(f"BC{i + 1}", "BC", "BC", self.sec_bc.name, n1, n2, +1, 0, 0, a.tolist(), rot90(a).tolist(),
                       self.nodes[n1].tolist(), self.nodes[n2].tolist(), 0.0, piece_of=f"B{ka:02d}-B{kb:02d}")
            L = PANEL * (kb - ka)
            m.t_start = -e_vp if ka == 0 else self.jgap / 2
            m.t_end = L + e_vp if kb == 12 else L - self.jgap / 2
            m.r2_force = dict(self.forces["chord_forces"]["BC"])
            self.members[m.id] = m
        b, e = self.sec_tc.b, self.sec_tc.e
        for i in range(6):
            ka, kb = cuts[i], cuts[i + 1]
            n1, n2 = f"T{ka:02d}", f"T{kb:02d}"
            d = self.nodes[n2] - self.nodes[n1]
            L = float(np.linalg.norm(d))
            a = d / L
            m = Member(f"TC{i + 1}", "TC", "TC", self.sec_tc.name, n1, n2, -1, 0, 0, a.tolist(), rot90(a).tolist(),
                       self.nodes[n1].tolist(), self.nodes[n2].tolist(), 0.0, piece_of=f"T{ka:02d}-T{kb:02d}")
            south = i < 3
            # start cut
            if ka == 0:                        # heel: outermost point (TOS corner) flush with the end-post heel line s = -e_vp
                m.t_start = (-e_vp + e * SIN15 - 0.0) / COS15      # along-axis distance; negative = beyond node
            elif ka == 6:                      # apex, north half rising southwards: lowest (toe) corner 2.5 mm off the ridge plane
                m.t_start = (self.jgap / 2 + (b - e) * SIN15) / COS15
            else:
                m.t_start = self.jgap / 2
            if kb == 12:
                m.t_end = L + (e_vp - e * SIN15) / COS15
            elif kb == 6:
                m.t_end = L - (self.jgap / 2 + (b - e) * SIN15) / COS15
            else:
                m.t_end = L - self.jgap / 2
            m.r2_force = dict(self.forces["chord_forces"]["TC"])
            self.members[m.id] = m

    # ----------------------------------------------------------------------- geometry helpers
    def sec(self, m: Member) -> AngleSec:
        return AngleSec.from_rules(m.section, self.rules)

    def band_q(self, m: Member):
        s = self.sec(m)
        qh = -m.psi * s.e
        qt = qh + m.psi * s.b
        return qh, qt

    def footprint(self, m: Member, t0, t1):
        qh, qt = self.band_q(m)
        return rect(np.array(m.node1_sz), np.array(m.a), np.array(m.p), t0, t1, qh, qt)

    def bolt_spec(self, m: Member):
        s = self.sec(m)
        dia = "M16" if s.max_bolt == "M16" else "M20"
        return dia, self.bolt_cfg[dia]

    def chords_at(self, node):
        """chord pieces at a panel point (two at a splice / apex, one elsewhere)"""
        k = int(node[1:])
        out = []
        for m in self.members.values():
            if m.role in ("TC", "BC") and m.n1[0] == node[0] and int(m.n1[1:]) <= k <= int(m.n2[1:]):
                out.append(m)
        return out

    def chord_end(self, c, node):
        """1 = piece starts at node, 2 = piece ends at node, 0 = node is interior to the piece"""
        return 1 if c.n1 == node else (2 if c.n2 == node else 0)

    def t_of(self, m, node):
        return float(np.dot(self.nodes[node] - np.array(m.node1_sz), np.array(m.a)))

    def webs_at(self, node):
        return [(m, 1 if m.n1 == node else 2) for m in self.members.values() if m.role not in ("TC", "BC") and node in (m.n1, m.n2)]

    def chord_obstacle(self, node):
        polys = []
        for c in self.chords_at(node):
            L = float(np.linalg.norm(np.array(c.node2_sz) - np.array(c.node1_sz)))
            polys.append(self.footprint(c, c.t_start, c.t_end))
        return unary_union(polys)

    # ----------------------------------------------------------------------- set-backs of web ends
    def _web_rect(self, m, end, d, probe=0.9):
        L = float(np.linalg.norm(np.array(m.node2_sz) - np.array(m.node1_sz)))
        if end == 1:
            return self.footprint(m, d, min(d + probe, L / 2))
        return self.footprint(m, max(L - d - probe, L / 2), L - d)

    def _joints_setback(self):
        step = 0.002
        self.setback = {}
        for node in self.nodes:
            obst = self.chord_obstacle(node)
            ws = self.webs_at(node)
            d = {}
            for m, end in ws:
                dd = 0.0
                while self._web_rect(m, end, dd).distance(obst) < self.fit - 1e-9:
                    dd += step
                    if dd > 1.5:
                        raise RuntimeError(f"{self.tid} {node} {m.id}: no chord clearance")
                d[m.id] = dd
            changed = True
            it = 0
            while changed and it < 2000:
                changed = False
                it += 1
                for i in range(len(ws)):
                    for j in range(i + 1, len(ws)):
                        (mi, ei), (mj, ej) = ws[i], ws[j]
                        if self._web_rect(mi, ei, d[mi.id]).distance(self._web_rect(mj, ej, d[mj.id])) < self.fit - 1e-9:
                            d[mi.id] += step
                            d[mj.id] += step
                            changed = True
            for m, end in ws:
                self.setback[(m.id, node)] = round(d[m.id], 4)

    def _finalise_members(self):
        for m in self.members.values():
            L = float(np.linalg.norm(np.array(m.node2_sz) - np.array(m.node1_sz)))
            if m.role not in ("TC", "BC"):
                m.t_start = self.setback[(m.id, m.n1)]
                m.t_end = L - self.setback[(m.id, m.n2)]
            m.length = round(m.t_end - m.t_start, 5)
            s = self.sec(m)
            a3 = np.array([0.0, m.a[0], m.a[1]])
            p3 = np.array([0.0, m.p[0], m.p[1]])
            n3 = np.array([1.0, 0.0, 0.0])
            qh = -m.psi * s.e
            for side, sig in (("A", +1), ("B", -1)):
                start_sz = np.array(m.node1_sz) + m.t_start * np.array(m.a)
                heel = np.array([self.x, Y0 + start_sz[0], start_sz[1]]) + qh * p3 + sig * (self.gap / 2) * n3
                if sig * m.psi == -1:
                    X = sig * n3
                else:
                    X = m.psi * p3
                origin = heel + (s.b / 2) * (sig * n3 + m.psi * p3)
                m.angles.append(Angle(f"{m.id}-{side}", m.id, side, m.section, origin.round(6).tolist(), a3.round(9).tolist(),
                                      X.round(9).tolist(), m.length, heel.round(6).tolist()))

    # ----------------------------------------------------------------------- connections
    def _family(self, node):
        k = int(node[1:])
        bottom = node[0] == "B"
        nd = len([1 for _ in self.webs_at(node) if _[0].role == "D"])
        if k in (0, 12):
            return "CT-BH" if bottom else "CT-TH"
        if bottom:
            if k == 6:
                return "CT-BC"
            return "CT-BS" if k in (2, 4, 8, 10) else "CT-BV"
        if k == 6:
            return "CT-TA"
        return "CT-TS" if k in (2, 4, 8, 10) else "CT-TV2"

    def _add_bolt(self, joint, member, role, sz, dia, stack_ids, x_head, grip):
        cfg = self.bolt_cfg[dia]
        need = grip + cfg["washer"][2] + cfg["nut_m"] + 2 * cfg["thread_pitch"]
        L = math.ceil(round(need * 1000, 6) / 5.0) * 5 / 1000
        n = sum(1 for b in self.bolts.values() if b.joint == joint and b.member == member and b.role == role) + 1
        bid = (f"{joint}-BLT-{member}-{n}" if role != "SPLICE" else f"{joint}-BLT-SPL-{member}-{n}") if role != "PACKER" else f"{member}-BLT"
        assert bid not in self.bolts or role == "PACKER", bid
        self.bolts[bid] = Bolt(bid, dia, round(float(sz[0]), 6), round(float(sz[1]), 6), round(x_head, 6), round(grip, 6), L,
                               stack_ids, joint, member, role)
        return bid

    def _connections(self):
        half_t = lambda m: self.gap / 2 + self.sec(m).t
        for node, P in self.nodes.items():
            jid = self.sid("J", node)
            fam = self._family(node)
            J = Joint(jid, node, fam, round(float(P[0]), 4), round(float(P[1]), 4), [])
            k = int(node[1:])
            bottom = node[0] == "B"
            J.splice = fam in ("CT-BS", "CT-BC", "CT-TS", "CT-TA")
            J.rigging_tab = self.rigging and bottom and 1 <= k <= 11
            regions = []
            gid = jid + "-GP"
            # ---- webs
            for m, end in self.webs_at(node):
                J.members.append((m.id, end))
                s = self.sec(m)
                dia, cfg = self.bolt_spec(m)
                F = max(m.r2_force["Nc_kN"], m.r2_force["Nt_kN"])
                n = max(2, math.ceil(F / 100.0))
                J.r2_forces[m.id] = {"F_max_kN": F, "bolts_rule": n, "section": "2" + m.section}
                L = m.t_end - m.t_start
                d0 = m.t_start if end == 1 else (float(np.linalg.norm(np.array(m.node2_sz) - np.array(m.node1_sz))) - m.t_end)
                qh, qt = self.band_q(m)
                qg = qh + m.psi * s.gauge
                zone = cfg["end_e1"] * 2 + (n - 1) * cfg["pitch_p1"]
                Lm = float(np.linalg.norm(np.array(m.node2_sz) - np.array(m.node1_sz)))
                for i in range(n):
                    t = (d0 + cfg["end_e1"] + i * cfg["pitch_p1"]) if end == 1 else (Lm - d0 - cfg["end_e1"] - i * cfg["pitch_p1"])
                    sz = np.array(m.node1_sz) + t * np.array(m.a) + qg * np.array(m.p)
                    J.bolts.append(self._add_bolt(jid, m.id, "WEB", sz, dia, [f"{m.id}-A", gid, f"{m.id}-B"], half_t(m), 2 * s.t + self.t_g))
                t0, t1 = (d0, d0 + zone) if end == 1 else (Lm - d0 - zone, Lm - d0)
                qa = min(qh, qt, qg - cfg["edge_e2"])
                qb = max(qh, qt, qg + cfg["edge_e2"])
                regions.append(rect(np.array(m.node1_sz), np.array(m.a), np.array(m.p), t0, t1, qa, qb))
            # ---- chords
            chords = self.chords_at(node)
            for c in chords:
                J.members.append((c.id, self.chord_end(c, node)))
            sc = self.sec(chords[0])
            dia, cfg = self.bolt_spec(chords[0])
            p1, e1 = cfg["pitch_p1"], cfg["end_e1"]
            if J.splice:
                # 4 bolts each side through splice plates + angles + gusset (DEV-03: also chord-to-gusset)
                sp_ids = [jid + "-SP-A", jid + "-SP-B"]
                for c in chords:
                    end = 1 if c.n1 == node else 2
                    Lc = float(np.linalg.norm(np.array(c.node2_sz) - np.array(c.node1_sz)))
                    tcut = c.t_start if end == 1 else c.t_end
                    qh, qt = self.band_q(c)
                    qg = qh + c.psi * sc.gauge
                    ts = [tcut + (e1 + i * p1) * (1 if end == 1 else -1) for i in range(4)]
                    for t in ts:
                        sz = np.array(c.node1_sz) + t * np.array(c.a) + qg * np.array(c.p)
                        J.bolts.append(self._add_bolt(jid, c.id, "SPLICE", sz, dia, [sp_ids[0], f"{c.id}-A", gid, f"{c.id}-B", sp_ids[1]],
                                                      half_t(c) + self.t_sp, 2 * sc.t + self.t_g + 2 * self.t_sp))
                    ta, tb = (tcut, ts[-1] + e1) if end == 1 else (ts[-1] - e1, tcut)
                    regions.append(rect(np.array(c.node1_sz), np.array(c.a), np.array(c.p), ta, tb, qh, qt))
                J.splice_plates = sp_ids
            else:
                c = chords[0]
                end = self.chord_end(c, node)
                qh, qt = self.band_q(c)
                qg = qh + c.psi * sc.gauge
                tn = self.t_of(c, node)
                if k in (0, 12):        # chord end at the heel: all 4 bolts on the inboard side
                    tcut = c.t_start if end == 1 else c.t_end
                    sgn = 1 if end == 1 else -1
                    ts = [tcut + sgn * (e1 + i * p1) for i in range(4)]
                else:                   # continuous chord: 2 bolts each side of the node
                    ts = [tn - p1 / 2 - p1, tn - p1 / 2, tn + p1 / 2, tn + p1 / 2 + p1]
                for t in ts:
                    sz = np.array(c.node1_sz) + t * np.array(c.a) + qg * np.array(c.p)
                    J.bolts.append(self._add_bolt(jid, c.id, "CHORD", sz, dia, [f"{c.id}-A", gid, f"{c.id}-B"], half_t(c), 2 * sc.t + self.t_g))
                regions.append(rect(np.array(c.node1_sz), np.array(c.a), np.array(c.p), min(ts) - e1, max(ts) + e1, qh, qt))
            # ---- gusset outline: convex hull, clipped to the chord outer faces (inset) and the heel line
            hull = unary_union(regions).convex_hull
            for c in chords:
                qh, qt = self.band_q(c)
                inset = qh - (self.inset if c.role == "TC" else -self.inset)
                o = np.array(c.node1_sz) + inset * np.array(c.p)
                nrm = -np.array(c.p) if c.role == "TC" else np.array(c.p)
                hull = hull.intersection(half_plane(o, nrm))
            if k == 0:
                hull = hull.intersection(half_plane(np.array([-self.e_vp, 0.0]), np.array([1.0, 0.0])))
            if k == 12:
                hull = hull.intersection(half_plane(np.array([SPAN + self.e_vp, 0.0]), np.array([-1.0, 0.0])))
            if J.rigging_tab:
                u = self.z_bc - self.sec_bc.e
                tab = box(P[0] - self.tab["width_m"] / 2, u - self.tab["depth_below_chord_m"], P[0] + self.tab["width_m"] / 2, u + self.inset + 0.001)
                hull = unary_union([hull, tab])
            hull = hull.simplify(0.0002)
            holes = [(self.bolts[b].s, self.bolts[b].z, self.bolt_cfg[self.bolts[b].diameter]["d0"]) for b in J.bolts]
            if J.rigging_tab:
                holes.append((float(P[0]), self.z_bc - self.sec_bc.e - self.tab["hole_below_chord_m"], self.tab["hole_diameter_m"]))
            self.plates[gid] = Plate(gid, "GUSSET", self.t_g, -self.t_g / 2, [list(map(float, xy)) for xy in hull.exterior.coords][:-1],
                                     holes, joint=jid, rigging_tab=J.rigging_tab)
            J.gusset = gid
            # ---- splice plates (outer faces of the connected legs, inside the angle corner)
            if J.splice:
                strips = []
                for c in chords:
                    qh, qt = self.band_q(c)
                    q_in = qh + c.psi * (sc.t + sc.r1 + 0.002)
                    sb = [self.bolts[b] for b in J.bolts if self.bolts[b].member == c.id and self.bolts[b].role == "SPLICE"]
                    ts = [float(np.dot(np.array([b.s, b.z]) - np.array(c.node1_sz), np.array(c.a))) for b in sb]
                    end = 1 if c.n1 == node else 2
                    tcut = c.t_start if end == 1 else c.t_end
                    ta, tb = (min(ts) - e1, max(ts) + e1)
                    # extend to the chord cut so the plate bridges the joint
                    ta, tb = (min(ta, tcut), max(tb, tcut))
                    if fam == "CT-TA":           # apex: run each strip to the ridge plane -> one chevron plate
                        ext = 0.25
                        ta, tb = (ta - ext, tb) if end == 1 else (ta, tb + ext)
                        r = rect(np.array(c.node1_sz), np.array(c.a), np.array(c.p), ta, tb, q_in, qt)
                        south = max(np.array(c.node1_sz)[0], np.array(c.node2_sz)[0]) <= SPAN / 2 + 1e-6
                        r = r.intersection(half_plane(np.array([SPAN / 2, 0.0]), np.array([-1.0, 0.0]) if south else np.array([1.0, 0.0])))
                        strips.append(r)
                    else:
                        strips.append(rect(np.array(c.node1_sz), np.array(c.a), np.array(c.p), ta, tb, q_in, qt))
                sp = unary_union(strips)
                if sp.geom_type != "Polygon":
                    sp = sp.convex_hull
                sp = sp.simplify(0.0002)
                holes = [(self.bolts[b].s, self.bolts[b].z, self.bolt_cfg[self.bolts[b].diameter]["d0"]) for b in J.bolts if self.bolts[b].role == "SPLICE"]
                x_face = self.gap / 2 + sc.t
                outline = [list(map(float, xy)) for xy in sp.exterior.coords][:-1]
                self.plates[jid + "-SP-A"] = Plate(jid + "-SP-A", "SPLICE", self.t_sp, x_face, outline, holes, joint=jid)
                self.plates[jid + "-SP-B"] = Plate(jid + "-SP-B", "SPLICE", self.t_sp, -x_face - self.t_sp, outline, holes, joint=jid)
            J.interfaces = self._interfaces(node, fam)
            fam_key = f"{fam}|{self.ttype}|" + ",".join(sorted(f"{self.members[mid].role}:{self.members[mid].section}:{len([b for b in J.bolts if self.bolts[b].member == mid])}"
                                                              for mid, _ in J.members)) + ("|TAB" if J.rigging_tab else "")
            J.type_key = fam_key
            self.joints[jid] = J

    def _interfaces(self, node, fam):
        k = int(node[1:])
        out = []
        if node[0] == "T":
            out.append("PURLIN: rows at s = 0.01 + 1.35 j (existing); every second row lands within 10 mm of a top panel point")
            if k in (0, 12):
                out += ["BEARING: support/column connection NOT MODELLED - depends on the separate support study (conflict C-01)",
                        "BRACING: existing rod-bracing end plate / eaves wind girder (R2 s.6.2) interface - not designed"]
            if k == 6:
                out.append("BRACING: ridge interface of existing roof rod bracing (end bays) and ridge purlins")
        else:
            if k in (2, 4, 6, 8, 10):
                out.append("BOTTOM-CHORD RESTRAINT: R2 assumes out-of-plane ties at <= 5.4 m (s = 5.4, 10.8, 16.2, 21.6, 27.0); ties not modelled")
            if self.rigging and 1 <= k <= 11:
                out.append("EQUIPMENT: rigging pick-up tab provision (capacity NOT_AVAILABLE; rigging load plan required)")
            out.append("SUSPENSION: acoustic raft / fan / tray hangers attach to the bottom chord - coordinate to panel points (R2 s.9)")
        return out

    # ----------------------------------------------------------------------- packers
    def _gusset_extent_on(self, m: Member, node):
        g = self.plates[self.sid("J", node) + "-GP"]
        poly = Polygon(g.outline_sz)
        ts = [float(np.dot(np.array(xy) - np.array(m.node1_sz), np.array(m.a))) for xy in poly.exterior.coords]
        return min(ts), max(ts)

    def _packers(self):
        for m in self.members.values():
            s = self.sec(m)
            dia, cfg = self.bolt_spec(m)
            Lp = 2 * cfg["end_e1"]
            # clear intervals along the member between gusset outlines (and member ends)
            nodes = []
            if m.role in ("TC", "BC"):
                k1, k2 = int(m.n1[1:]), int(m.n2[1:])
                nodes = [f"{m.n1[0]}{k:02d}" for k in range(min(k1, k2), max(k1, k2) + 1)]
            else:
                nodes = [m.n1, m.n2]
            ext = sorted(self._gusset_extent_on(m, nd) for nd in nodes)
            ivals = []
            for (a0, a1), (b0, b1) in zip(ext[:-1], ext[1:]):
                lo, hi = max(a1, m.t_start), min(b0, m.t_end)
                if hi - lo > 0:
                    ivals.append((lo, hi))
            qh, qt = self.band_q(m)
            qg = qh + m.psi * s.gauge
            qc = qh + m.psi * s.b / 2
            for lo, hi in ivals:
                clear = hi - lo
                n = math.ceil(clear / self.pk_max) - 1
                if m.role not in ("TC", "BC"):
                    n = max(1, n)
                n = max(0, n)
                for i in range(n):
                    t = lo + clear * (i + 1) / (n + 1)
                    pid = f"{self.sid(m.id)}-PK-{len(m.packers) + 1}"
                    c = np.array(m.node1_sz) + t * np.array(m.a) + qc * np.array(m.p)
                    bsz = np.array(m.node1_sz) + t * np.array(m.a) + qg * np.array(m.p)
                    self.plates[pid] = Plate(pid, "PACKER", self.t_pk, -self.t_pk / 2, [], [], member=m.id, centre_sz=c.round(6).tolist(),
                                             axis_sz=list(m.a), size=[round(Lp, 4), round(s.b, 4)])
                    m.packers.append(pid)
                    self._add_bolt("", m.id, "PACKER", bsz, dia, [f"{m.id}-A", pid, f"{m.id}-B"], self.gap / 2 + s.t, 2 * s.t + self.t_pk)
                    # rename packer bolt uniquely
                    old = f"{m.id}-BLT"
                    b = self.bolts.pop(old)
                    b.id = pid + "-BLT"
                    self.bolts[b.id] = b

    # ----------------------------------------------------------------------- exports
    def world(self, s, z, dx=0.0):
        return [self.x + dx, Y0 + s, z]

    def summary(self):
        mem = list(self.members.values())
        mass = sum(self.sec(m).kg_m * 2 * m.length for m in mem)
        return dict(truss=self.tid, line=self.line, x=self.x, type=self.ttype, members=len(mem), angles=2 * len(mem),
                    webs=sum(1 for m in mem if m.role not in ("TC", "BC")), chord_pieces=sum(1 for m in mem if m.role in ("TC", "BC")),
                    joints=len(self.joints), gussets=sum(1 for p in self.plates.values() if p.kind == "GUSSET"),
                    splice_plates=sum(1 for p in self.plates.values() if p.kind == "SPLICE"),
                    packers=sum(1 for p in self.plates.values() if p.kind == "PACKER"), bolts=len(self.bolts),
                    member_mass_nominal_kg=round(mass, 1),
                    depth_at_bearing_m=round(float(self.nodes["T00"][1] - self.nodes["B00"][1]), 4),
                    depth_at_ridge_m=round(float(self.nodes["T06"][1] - self.nodes["B06"][1]), 4))

    def to_dict(self):
        return dict(summary=self.summary(), nodes={k: v.round(6).tolist() for k, v in self.nodes.items()},
                    members={k: asdict(v) for k, v in self.members.items()}, plates={k: asdict(v) for k, v in self.plates.items()},
                    bolts={k: asdict(v) for k, v in self.bolts.items()}, joints={k: asdict(v) for k, v in self.joints.items()})


def plate_area_net(p: Plate):
    if p.kind == "PACKER":
        return p.size[0] * p.size[1], p.size[0] * p.size[1]
    g = Polygon(p.outline_sz).area
    h = sum(math.pi * (d / 2) ** 2 for _, _, d in p.holes_sz)
    return g, g - h


def shape_hash(p: Plate, ref_s=None):
    """Fabrication part identity of a plate: outline + holes up to translation along s and mirroring about the mid-span."""
    if p.kind == "PACKER":
        return f"PK-{round(p.size[0] * 1000)}x{round(p.size[1] * 1000)}x{round(p.thickness * 1000)}"
    pts = np.array(p.outline_sz)
    hs = np.array([[h[0], h[1], h[2]] for h in p.holes_sz]) if p.holes_sz else np.zeros((0, 3))
    keys = []
    for mirror in (False, True):
        P = pts.copy(); H = hs.copy()
        if mirror:
            P[:, 0] = -P[:, 0]
            if len(H): H[:, 0] = -H[:, 0]
        c = P.min(axis=0)
        P = np.round((P - c) * 1000).astype(int)
        H2 = np.round((H[:, :2] - c) * 1000).astype(int) if len(H) else H
        sig = sorted(map(tuple, P.tolist())), sorted(map(tuple, H2.tolist())) if len(H) else []
        keys.append(hashlib.sha1(json.dumps([sig, round(p.thickness * 1000)]).encode()).hexdigest()[:10])
    return min(keys)
