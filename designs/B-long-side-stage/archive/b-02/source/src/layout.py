"""Option B (long-side stage) parametric layout engine for the 3,000-seat church auditorium concept.

The platform stands on the middle of the long north wall; the congregation sits in a wide, shallow
fan of concentric rows centred on the platform focus F. Pure Python (no bpy / numpy) so it runs under
Blender's Python and the project venv. Units: metres. Every value is a concept assumption from
config/params.json - nothing here is a verified code, survey or engineering value.

compute(P) returns a LayoutB with elements (shared.bim.geometry.Element), seats, rows, exits, egress
results, checks and metrics. The shared Blender builder (shared/bim/build_blender.py) turns the
elements into the .blend and the read-back manifest.

Frame: x along the long side (grid A = 0 -> L = 80), y towards the platform (grid 2 = hall rear
column line = 0), z up. Envelope walls stand outside the column lines; the hall's clear interior is
bounded by the column faces (0.3 m inside each column line).
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from shared.bim.geometry import (CHAIR_H, CHAIR_HALF_D, CHAIR_HALF_W, INSTANCE_MESHES, Element,  # noqa: E402,F401
                                 dist_point_aabb, load_params, rnd)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "config" / "params.json"
SCHEMA_VERSION = "layout-B-1.0"
CUTAWAY_HIDE_PREFIXES = ("ENV-ROOF", "STR-PURLIN", "STR-BRACE-ROOF", "ENV-WALL-EXT-S", "ENV-WALL-AMB-W", "ENV-WALL-HALL-W",
                         "ENV-CLAD", "ENV-CANOPY", "SRV-GUTTER")
COL_FACE = 0.3   # half the hall column size: clear interior starts here


# --------------------------------------------------------------------------- plan helpers
def ceil_to(v, step):
    return math.ceil(round(v / step, 6)) * step


def polar(F, r, th):
    """Point at radius r and angle th (radians, 0 = straight away from the platform (-y), + = east) about F."""
    return (F[0] + r * math.sin(th), F[1] - r * math.cos(th))


def ccw(poly):
    a = sum(poly[i][0] * poly[(i + 1) % len(poly)][1] - poly[(i + 1) % len(poly)][0] * poly[i][1] for i in range(len(poly)))
    return list(poly) if a > 0 else list(reversed(poly))


def poly_area(poly):
    return abs(sum(poly[i][0] * poly[(i + 1) % len(poly)][1] - poly[(i + 1) % len(poly)][0] * poly[i][1]
                   for i in range(len(poly)))) / 2


def seg_dist(p, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    t = max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / (dx * dx + dy * dy or 1e-12)))
    return math.hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dy)


def point_in_poly(p, poly):
    inside = False
    n = len(poly)
    for i in range(n):
        (x0, y0), (x1, y1) = poly[i], poly[(i + 1) % n]
        if (y0 > p[1]) != (y1 > p[1]) and p[0] < x0 + (p[1] - y0) * (x1 - x0) / (y1 - y0):
            inside = not inside
    return inside


def poly_dist(p, poly):
    """Distance from a point to a polygon, 0 if inside."""
    if point_in_poly(p, poly):
        return 0.0
    return min(seg_dist(p, poly[i], poly[(i + 1) % len(poly)]) for i in range(len(poly)))


def chair_corners(x, y, rot_deg, hw=CHAIR_HALF_W, hd=CHAIR_HALF_D):
    c, s = math.cos(math.radians(rot_deg)), math.sin(math.radians(rot_deg))
    return [(x + c * a - s * b, y + s * a + c * b) for a, b in ((-hw, -hd), (hw, -hd), (hw, hd), (-hw, hd))]


def obb_overlap(pa, pb, tol=0.0):
    """Separating-axis test for two convex polygons; True if they overlap by more than tol."""
    for poly in (pa, pb):
        for i in range(len(poly)):
            ex, ey = poly[(i + 1) % len(poly)][0] - poly[i][0], poly[(i + 1) % len(poly)][1] - poly[i][1]
            m = math.hypot(ex, ey)
            nx, ny = -ey / m, ex / m
            a = [q[0] * nx + q[1] * ny for q in pa]
            b = [q[0] * nx + q[1] * ny for q in pb]
            if max(a) <= min(b) + tol or max(b) <= min(a) + tol:
                return False
    return True


def rect(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


class LayoutB:
    def __init__(self, P):
        self.P = P
        self.elements: list[Element] = []
        self.names = set()
        self.checks, self.metrics = [], {}
        self.rows, self.seats, self.exits, self.wc_positions, self.spaces = [], [], [], [], []
        self.ramps, self.stairs, self.choir, self.egress_results, self.ext_doors = [], [], [], [], []
        self.columns = {}

    # ------------------------------------------------------------------ element helpers
    def add(self, el):
        if el.name in self.names:
            raise ValueError(f"duplicate element name {el.name}")
        self.names.add(el.name)
        if el.storey is None:
            el.storey = self.storey_for(el)
        self.elements.append(el)
        return el

    def box(self, name, col, cls, pre, bb, props=None, otype=None, storey=None, **kw):
        return self.add(Element(name, col, cls, pre, storey, [("box", tuple(bb))], props=props, object_type=otype, **kw))

    def prism(self, name, col, cls, pre, polys, z0, z1, props=None, otype=None, storey=None, **kw):
        parts = [("prism_xy", (ccw(p), z0, z1)) for p in polys]
        return self.add(Element(name, col, cls, pre, storey, parts, props=props, object_type=otype, **kw))

    def strut(self, name, col, cls, pre, p0, p1, w, h, props=None, storey=None):
        return self.add(Element(name, col, cls, pre, storey, [("strut", (tuple(p0), tuple(p1), w, h))], props=props,
                                strut=(tuple(p0), tuple(p1), max(w, h) / 2)))

    def check(self, cid, desc, passed, value, criterion, status_if_fail="FAIL"):
        self.checks.append({"id": cid, "description": desc, "value": value, "criterion": criterion,
                            "result": "PASS" if passed else status_if_fail})

    def storey_for(self, el):
        """Same rule as the IFC validator: highest level at or below the element's base (slab floors: top)."""
        if el.mesh_key:
            z = el.origin[2]
        else:
            bb = el.aabb()
            z = bb[5] if (el.ifc_class == "IfcSlab" and el.predefined in ("FLOOR", "LANDING")) else bb[2]
        best = self.level_list[0]
        for lv in self.level_list:
            if z >= lv["elevation"] - 0.01:
                best = lv
        return best["id"]

    def levels(self):
        return [dict(lv) for lv in self.level_list]

    # ------------------------------------------------------------------ main
    def compute(self):
        G = self.P["grid"]
        self.gx = G["x_lines"]
        self.x0, self.x1 = self.gx["A"], self.gx["L"]
        self.W = self.x1 - self.x0
        self.xc = (self.x0 + self.x1) / 2
        self.seating_geometry()
        self.place_seats()
        self.set_levels()
        self.gy = G["y_lines"]
        self.roof_geometry()
        self.rake_floors()
        self.platform()
        self.seat_elements()
        self.accessible_places()
        self.envelope()
        self.rear_corners()
        self.foyer()
        self.ambulatories()
        self.choir_zones()
        self.back_of_house()
        self.structure()
        self.av_services()
        self.space_zones()
        self.egress()
        self.sightline_checks()
        self.clash_checks()
        self.summary_metrics()
        return self

    # ------------------------------------------------------------------ seating geometry
    def seating_geometry(self):
        S, ST = self.P["seating"], self.P["stage"]
        self.Rd = ST["thrust_radius"]
        self.rear_depth = ST["rear_band_depth"]
        self.half = math.radians(S["fan_half_angle_deg"])
        self.r1 = self.Rd + S["front_clear_zone"] + S["chair_depth"] / 2
        self.pitch = S["row_pitch"]
        radii, r = [], self.r1
        for n in range(1, S["max_rows"] + 1):
            if n == S["front_rows"] + 1:
                r += S["cross_aisle_passage"] + S["wheelchair_band_depth"]
            radii.append(r)
            r += self.pitch
        self.radii = radii
        nf, nr = S["front_blocks"], S["rear_blocks"]
        self.front_aisles = [-self.half + 2 * self.half * i / nf for i in range(nf + 1)]
        self.rear_aisles = [-self.half + 2 * self.half * i / nr for i in range(nr + 1)]

    def row_floor_levels(self, nrows):
        """C-value recurrence (n1 and staggered n2) on concentric rows. Eye = chair base + eye height at the
        chair centre + eye offset; focal point = thrust front edge on the seat's radial line at platform
        height + focal height. Front rows: chair base on a continuous slope (<= 1:front_max_gradient).
        Rear rows: one uniform riser per row (>= minimum aisle riser) meeting every row's requirement."""
        S, SL, ST = self.P["seating"], self.P["sightlines"], self.P["stage"]
        Hf = ST["platform_height"] + SL["focal_height_above_platform"]
        eye, eo = S["eye_height_seated"], S["eye_offset_from_chair_centre"]
        C, C2, step = SL["c_value_target"], SL["c_value_staggered_target_n2"], SL["elevation_rounding"]
        nf = S["front_rows"]
        d = [r + eo - self.Rd for r in self.radii[:nrows]]

        def need(fl, i):
            req = 0.0
            if i >= 1:
                req = Hf + (fl[i - 1] + eye + C - Hf) * d[i] / d[i - 1] - eye
            if i >= 2:
                req = max(req, Hf + (fl[i - 2] + eye + C2 - Hf) * d[i] / d[i - 2] - eye)
            return req

        fl = []
        for i in range(nf):
            fl.append(max(ceil_to(need(fl, i), step), fl[-1] if fl else 0.0))
        self.front_gradient_max = max((fl[i] - fl[i - 1]) / self.pitch for i in range(1, nf))
        A = self.P["accessibility"]
        rb = self.radii[nf] - 0.55 - A["wheelchair_space_depth"] / 2 - 0.05     # band centre radius
        dw = rb + eo - self.Rd
        e_nf = fl[nf - 1] + eye - Hf
        need_band = (C + e_nf) * dw / d[nf - 1] + Hf - S["eye_height_wheelchair"]
        cross = ceil_to(max(fl[nf - 1], need_band), step)
        if 0 < cross - fl[nf - 1] < SL["min_aisle_riser"]:
            cross = ceil_to(fl[nf - 1] + SL["min_aisle_riser"], step)
        self.cross_step = cross - fl[nf - 1]
        riser = SL["min_aisle_riser"]
        while True:
            full = fl[:nf] + [cross + riser * (k + 1) for k in range(nrows - nf)]
            if all(full[i] + 1e-9 >= need(full, i) for i in range(nf, nrows)):
                break
            riser = round(riser + step, 4)
        self.cross_level, self.rear_riser = cross, riser
        self.eye_d = d
        return full

    def place_seats(self):
        P = self.P
        S, ST = P["seating"], P["stage"]
        target = S["target_congregation_seats"]
        F0 = (0.0, 0.0)
        Pul0 = (0.0, -(self.Rd - ST["pulpit_back_from_edge"]))
        hb = ST["rear_band_width"] / 2
        self.hb = hb
        plat0 = ([(-hb, 0.0)] + [polar(F0, self.Rd, math.radians(a)) for a in range(-90, 91, 6)]
                 + [(hb, 0.0), (hb, self.rear_depth), (-hb, self.rear_depth)])
        wa, sw, maxb = S["aisle_width"], S["seat_width"], S["max_seats_per_block_row"]
        xlim = self.W / 2 - COL_FACE - S["wall_aisle"]
        cand = []
        for ri, r in enumerate(self.radii):
            row = ri + 1
            aisles = self.front_aisles if row <= S["front_rows"] else self.rear_aisles
            for b in range(len(aisles) - 1):
                a0, a1 = aisles[b] + (wa / 2) / r, aisles[b + 1] - (wa / 2) / r
                L = (a1 - a0) * r
                n = min(maxb, int(L / sw + 1e-9))
                off = (L - n * sw) / 2
                if S["stagger"] and row % 2 == 0 and n >= 1:
                    if off < 0.25 - 1e-9:
                        n -= 1
                        off = (L - n * sw) / 2
                    off += 0.25 if b % 2 == 0 else -0.25
                for k in range(n):
                    th = a0 + (off + (k + 0.5) * sw) / r
                    x, y = polar(F0, r, th)
                    rot = math.degrees(th)
                    corners = chair_corners(x, y, rot)
                    reason = None
                    if max(abs(c[0]) for c in corners) > xlim:
                        reason = "wall aisle"
                    elif min(poly_dist(c, plat0) for c in corners) < S["front_clear_zone"] - 1e-6:
                        reason = "platform front clear zone"
                    else:
                        bear = math.degrees(math.atan2(abs(x - Pul0[0]), Pul0[1] - y)) if y < Pul0[1] else 180.0
                        if bear > S["max_bearing_from_pulpit_deg"]:
                            reason = "bearing from pulpit"
                    cand.append({"row": row, "block": b + 1, "k": k, "r": r, "th": th, "x": x, "y": y, "rot": rot,
                                 "reason": reason, "dist": math.hypot(x - Pul0[0], y - Pul0[1])})
        self.candidates = cand
        nfb = len(self.front_aisles) - 1
        self.front_wc_blocks = (nfb // 2, nfb // 2 + 1)
        for c in cand:  # front wheelchair positions replace rows 1-2 of the two centre blocks (review ACC-B: on-axis view)
            if c["reason"] is None and c["row"] in (1, 2) and c["block"] in self.front_wc_blocks:
                c["reason"] = "front wheelchair positions"
        ok = [c for c in cand if c["reason"] is None]
        byrow, tot, nrows = {}, 0, 0
        for c in ok:
            byrow.setdefault(c["row"], []).append(c)
        for row in sorted(byrow):
            tot += len(byrow[row])
            nrows = row
            if tot >= target:
                break
        if tot < target:
            raise ValueError(f"only {tot} seats fit within {len(self.radii)} rows - raise seating.max_rows")
        keep = sorted((c for c in ok if c["row"] <= nrows), key=lambda c: (round(c["dist"], 6), c["row"], c["block"], c["k"]))
        self.trimmed, keep = keep[target:], keep[:target]
        self.nrows = nrows
        self.row_floor = self.row_floor_levels(nrows)
        r_last = self.radii[nrows - 1]
        self.R_rows_back = r_last + 0.4
        self.R_out = self.R_rows_back + S["rear_passage"]
        Fy = self.R_out + COL_FACE
        self.F = (self.xc, Fy)
        self.ysw = Fy + self.rear_depth + COL_FACE
        self.pulpit = (self.xc, Fy + Pul0[1])
        G = P["grid"]["y_lines"]
        G["3"], G["4"] = rnd(Fy, 3), rnd(self.ysw, 3)
        G["5"] = rnd(self.ysw + P["back_of_house"]["depth"], 3)
        self.platform_poly = [(x + self.xc, y + Fy) for x, y in plat0]
        keep.sort(key=lambda c: (c["row"], c["th"]))
        counters = {}
        for c in keep:
            key = (c["row"], c["block"])
            counters[key] = counters.get(key, 0) + 1
            ri = c["row"] - 1
            sid = f"SEAT-C-R{c['row']:02d}-B{c['block']:02d}-S{counters[key]:02d}"
            self.seats.append({"seat_id": sid, "row": c["row"], "block": c["block"], "seat": counters[key],
                               "x": rnd(c["x"] + self.xc, 4), "y": rnd(c["y"] + Fy, 4), "z_floor": rnd(self.row_floor[ri], 4),
                               "rot_z": rnd(c["rot"], 4), "r": c["r"], "th": c["th"],
                               "section": "front" if c["row"] <= S["front_rows"] else "rear"})
        for ri in range(nrows):
            n = sum(1 for s in self.seats if s["row"] == ri + 1)
            self.rows.append({"row": ri + 1, "radius": rnd(self.radii[ri], 3), "floor": rnd(self.row_floor[ri], 3), "seats": n,
                              "section": "front" if ri < S["front_rows"] else "rear",
                              "rise": rnd(self.row_floor[ri] - (self.row_floor[ri - 1] if ri else 0.0), 3)})
        self.metrics["trimmed_seats"] = len(self.trimmed)
        self.metrics["rows"] = nrows
        self.metrics["rejected_candidates"] = {k: sum(1 for c in cand if c["reason"] == k)
                                               for k in sorted({c["reason"] for c in cand if c["reason"]})}

    def set_levels(self):
        self.top_level = self.row_floor[self.nrows - 1]
        self.level_list = [
            {"id": "L00", "elevation": 0.0, "name": "Level 00 - datum +0.000 (ground: foyer, front of hall, choir, back-of-house)"},
            {"id": "L01", "elevation": rnd(self.cross_level, 3),
             "name": f"Level 01 - datum {self.cross_level:+.3f} (cross aisle, rear rake, platform)"},
            {"id": "L02", "elevation": rnd(self.top_level, 3),
             "name": f"Level 02 - datum {self.top_level:+.3f} (rear passage, booth, high-level items)"},
        ]

    # ------------------------------------------------------------------ geometry shared by many parts
    def roof_geometry(self):
        STR = self.P["structure"]
        self.tan = math.tan(math.radians(STR["roof_pitch_deg"]))
        self.y_fac = self.gy["1"]
        self.td = STR["truss_depth"]

    def tc(self, y):
        """Truss top-chord centreline height at y (mono-pitch rising towards the stage)."""
        return self.P["structure"]["truss_bearing_z_rear"] + y * self.tan

    def bc(self, y):
        return self.tc(y) - self.td

    def fan_limit(self, r):
        """Angular half-extent of floor at radius r: edge aisle outer edge, clipped to the side column faces."""
        a = self.half + (self.P["seating"]["aisle_width"] / 2) / r
        lim = (self.W / 2 - COL_FACE) / r
        return min(a, math.asin(lim)) if lim < 1 else a

    def annulus(self, r0, r1, step_deg=3.0):
        """Annular strip clipped to the side walls (and the rear wall), as convex quads."""
        lim = self.fan_limit(r1)
        n = max(2, math.ceil(math.degrees(2 * lim) / step_deg))
        quads = []
        for i in range(n):
            t0, t1 = -lim + 2 * lim * i / n, -lim + 2 * lim * (i + 1) / n
            q = [polar(self.F, r0, t0), polar(self.F, r0, t1), polar(self.F, r1, t1), polar(self.F, r1, t0)]
            q = [(min(max(x, COL_FACE), self.W - COL_FACE), max(y, COL_FACE)) for x, y in q]
            if poly_area(q) > 1e-4:
                quads.append(q)
        return quads

    # ------------------------------------------------------------------ rake
    def slope_z(self, r):
        """Front-section floor, piecewise linear in radius through each row's chair-front point."""
        nf = self.P["seating"]["front_rows"]
        R = [self.radii[i] + CHAIR_HALF_D for i in range(nf)]
        Z = self.row_floor[:nf]
        if r <= R[0]:
            return Z[0]
        for i in range(1, nf):
            if r <= R[i]:
                return Z[i - 1] + (Z[i] - Z[i - 1]) * (r - R[i - 1]) / (R[i] - R[i - 1])
        return Z[-1]

    def rake_floors(self):
        S = self.P["seating"]
        nf = S["front_rows"]
        col = "20_ARC_Floors"
        # ground slab of the hall (grade), under everything
        self.box("ARC-SLAB-HALL", col, "IfcSlab", "FLOOR", (COL_FACE, COL_FACE, -0.25, self.W - COL_FACE, self.ysw - COL_FACE, 0.0),
                 {"Description": "Hall ground-bearing slab (grade)"})
        # front slope: strips between consecutive chair-front radii, sloped top (prism8), bottom at grade
        F = self.F
        for i in range(1, nf):
            r0, r1 = self.radii[i - 1] + CHAIR_HALF_D, self.radii[i] + CHAIR_HALF_D
            z0, z1 = max(self.slope_z(r0), 0.005), self.slope_z(r1)
            if z1 <= 0.0:
                continue
            parts = []
            for q in self.annulus(r0, r1):
                zz = [z0 if math.hypot(x - F[0], y - F[1]) < (r0 + r1) / 2 else z1 for x, y in q]
                parts.append(("prism8", [(x, y, 0.0) for x, y in q] + [(x, y, z) for (x, y), z in zip(q, zz)]))
            self.add(Element(f"ARC-RAKE-F{i + 1:02d}", col, "IfcSlab", "FLOOR", None, parts,
                             props={"Description": f"Front sloped floor, row {i} to {i + 1} (chair-back control points, max 1:{1 / max(self.front_gradient_max, 1e-9):.1f})",
                                    "StoreyOverride": "L00: sloped front floor starts at grade"}))
        a, b = self.radii[nf - 1] + CHAIR_HALF_D, self.radii[nf - 1] + 0.40
        self.prism_multi(f"ARC-RAKE-F{nf:02d}T", col, "IfcSlab", "FLOOR", self.annulus(a, b), 0.0, self.row_floor[nf - 1],
                         {"Description": f"Row {nf} tread (top of the front slope)"})
        # level floor from the riser behind the last front row to the first rear riser = cross aisle
        r_cross0 = self.radii[nf - 1] + 0.40
        r_cross1 = self.radii[nf] - 0.55
        self.cross_r = (r_cross0, r_cross1)
        z_pass = self.row_floor[nf - 1]
        r_band0 = r_cross0 + S["cross_aisle_passage"]
        self.cross_pass_level = z_pass
        self.band_r = (r_band0, r_cross1)
        self.prism_multi("ARC-CROSS-AISLE", col, "IfcSlab", "FLOOR", self.annulus(r_cross0, r_band0), 0.0, z_pass,
                         {"Description": f"Cross aisle passage, level with row {nf} (+{z_pass:.3f}), step-free from the front aisles"})
        A = self.P["accessibility"]
        run = (self.cross_level - z_pass) * A["ramp_gradient_1_in"]
        rm = (r_band0 + r_cross1) / 2
        lim = self.fan_limit(r_cross1)
        dth = run / rm
        band = [q for q in self.annulus(r_band0, r_cross1)]
        F = self.F
        n = max(2, math.ceil(math.degrees(2 * (lim - dth)) / 3.0))
        quads = []
        for i in range(n):
            t0, t1 = -(lim - dth) + 2 * (lim - dth) * i / n, -(lim - dth) + 2 * (lim - dth) * (i + 1) / n
            quads.append([polar(F, r_band0, t0), polar(F, r_band0, t1), polar(F, r_cross1, t1), polar(F, r_cross1, t0)])
        self.prism_multi("ARC-WC-BAND", col, "IfcSlab", "FLOOR", quads, 0.0, self.cross_level,
                         {"Description": f"Raised wheelchair band (+{self.cross_level:.3f}, one {self.cross_level - z_pass:.2f} m step above the passage)"})
        if self.cross_level > z_pass + 1e-6:
            for side, sgn in (("W", -1), ("E", 1)):
                a_in, a_out = sgn * (lim - dth), sgn * lim
                pts = []
                for a, z in ((a_out, z_pass), (a_in, self.cross_level)):
                    pts.append((polar(F, r_band0, a), polar(F, r_cross1, a), z))
                (o0, o1, zo), (i0, i1, zi) = pts
                part = ("prism8", [(o0[0], o0[1], 0.0), (o1[0], o1[1], 0.0), (i1[0], i1[1], 0.0), (i0[0], i0[1], 0.0),
                                   (o0[0], o0[1], zo), (o1[0], o1[1], zo), (i1[0], i1[1], zi), (i0[0], i0[1], zi)])
                name = f"ARC-RAMP-BAND-{side}"
                self.add(Element(name, "20_ARC_Circulation", "IfcRamp", "STRAIGHT_RUN_RAMP", None, [part],
                                 props={"Rise": rnd(self.cross_level - z_pass, 3), "Gradient_1_in": A["ramp_gradient_1_in"],
                                        "Width": rnd(r_cross1 - r_band0, 2), "Flights": 1,
                                        "Role": "Ramp from the cross-aisle passage onto the raised wheelchair band"}))
                self.ramps.append({"name": name, "rise": rnd(self.cross_level - z_pass, 3), "gradient_1_in": A["ramp_gradient_1_in"],
                                   "width": rnd(r_cross1 - r_band0, 2), "flights": 1, "run_per_flight": rnd(run, 2)})
        # rear treads (stepped), rear passage at the top level
        for i in range(nf, self.nrows):
            r0 = self.radii[i] - 0.55
            r1 = self.radii[i] + 0.40 if i < self.nrows - 1 else self.R_out
            name = f"ARC-RAKE-R{i + 1:02d}" if i < self.nrows - 1 else "ARC-REAR-PASSAGE"
            desc = f"Row {i + 1} tread" if i < self.nrows - 1 else f"Last row tread + rear passage (+{self.top_level:.3f})"
            self.prism_multi(name, col, "IfcSlab", "FLOOR", self.annulus(r0, r1), 0.0, self.row_floor[i], {"Description": desc})
        # central rear landing: rear passage extended to the rear column line between the foyer stairs
        fx = self.P["foyer"]["stair_x_centers"]
        lx0, lx1 = fx[0] - 4.0, fx[1] + 4.0
        pts = []
        for x in (lx0, lx1):
            dx = abs(x - F[0])
            pts.append(F[1] - math.sqrt(max(self.R_out ** 2 - dx * dx, 0.0)))
        polys = []
        n = 12
        for k in range(n):
            xa, xb = lx0 + (lx1 - lx0) * k / n, lx0 + (lx1 - lx0) * (k + 1) / n
            ya = F[1] - math.sqrt(self.R_out ** 2 - (xa - F[0]) ** 2) + 0.05
            yb = F[1] - math.sqrt(self.R_out ** 2 - (xb - F[0]) ** 2) + 0.05
            if max(ya, yb) > COL_FACE + 0.01:
                polys.append([(xa, COL_FACE), (xb, COL_FACE), (xb, max(yb, COL_FACE + 0.01)), (xa, max(ya, COL_FACE + 0.01))])
        self.rear_landing_x = (lx0, lx1)
        self.prism_multi("ARC-REAR-LANDING", col, "IfcSlab", "LANDING", polys, 0.0, self.top_level,
                         {"Description": "Rear landing: rear passage extended to the rear wall doors / foyer stair heads"})
        # guard rails on the outer edges of the raised rake beside the front corners (drop > 0.6 m)
        for side, sgn in (("W", -1), ("E", 1)):
            pts = []
            for i in range(nf, self.nrows):
                if self.row_floor[i] < 0.6:
                    continue
                r = self.radii[i]
                th = sgn * self.fan_limit(r + 0.4)
                pts.append((polar(F, r - 0.55, th), polar(F, r + 0.4, th), self.row_floor[i]))
            for k, (a, b, z) in enumerate(pts):
                if a[0] < COL_FACE + 0.05 or b[0] < COL_FACE + 0.05 or a[0] > self.W - COL_FACE - 0.05 or b[0] > self.W - COL_FACE - 0.05:
                    continue
                self.strut(f"ARC-RAIL-EDGE-{side}-{k + 1:02d}", "20_ARC_Circulation", "IfcRailing", "GUARDRAIL",
                           (a[0], a[1], z + 1.05), (b[0], b[1], z + 1.05), 0.05, 0.05,
                           {"Height": 1.1, "Role": "Guard on the raised edge aisle above the front-corner floor"})

    def prism_multi(self, name, col, cls, pre, polys, z0, z1, props=None, otype=None):
        parts = [("prism_xy", (ccw(q), z0, z1)) for q in polys]
        return self.add(Element(name, col, cls, pre, None, parts, props=props, object_type=otype))

    # ------------------------------------------------------------------ platform
    def platform(self):
        ST = self.P["stage"]
        h = ST["platform_height"]
        F, hb, xc = self.F, self.hb, self.xc
        col = "20_ARC_Floors"
        band = rect(xc - hb, F[1], xc + hb, self.ysw - COL_FACE)
        thrust = []
        for i in range(-90, 90, 10):
            a, b = math.radians(i), math.radians(i + 10)
            pa, pb = polar(F, self.Rd, a), polar(F, self.Rd, b)
            thrust.append([(pa[0], F[1]), (pb[0], F[1]), pb, pa])
        self.prism_multi("ARC-PLATFORM", col, "IfcSlab", "FLOOR", [band] + thrust, 0.0, h,
                         {"Description": f"Thrust platform / pulpit stage (+{h:.2f})"})
        self.platform_area = poly_area(band) + math.pi * self.Rd ** 2 / 2
        px, py = self.pulpit
        self.box("ARC-PULPIT", "20_ARC_Furniture", "IfcFurniture", "USERDEFINED", (px - 0.6, py - 0.4, h, px + 0.6, py + 0.4, h + 1.1),
                 {}, "Pulpit")
        # west stair at the front-west corner of the rear band, rising east onto the band
        sw, rz, g = ST["stair_width"], ST["stair_riser"], ST["stair_going"]
        nris = math.ceil(round(h / rz, 6))
        riser = h / nris
        x_top = xc - hb
        y0 = F[1] + 0.3
        parts = []
        for k in range(nris - 1):
            xa = x_top - (nris - 1 - k) * g
            parts.append(("box", (xa, y0, 0.0, xa + g, y0 + sw, riser * (k + 1))))
        self.stair_platform = (x_top - (nris - 1) * g, y0, x_top, y0 + sw)
        self.add(Element("ARC-STAIR-PLATFORM-W", "20_ARC_Circulation", "IfcStair", "STRAIGHT_RUN_STAIR", None, parts,
                         props={"Riser": rnd(riser, 3), "Risers": nris, "Going": g, "Width": sw}))
        self.stairs.append({"name": "ARC-STAIR-PLATFORM-W", "width": sw, "riser": rnd(riser, 3), "risers": nris})
        # east ramp along the stage wall, from the band's east edge towards the east wall (band = top landing)
        rw, grad, land = ST["ramp_width"], ST["ramp_gradient_1_in"], ST["ramp_landing"]
        run = h * grad
        maxrun = self.P["accessibility"]["ramp_max_run"]
        flights = math.ceil(run / maxrun - 1e-9)
        yr1 = self.ysw - COL_FACE
        yr0 = yr1 - rw
        x = xc + hb
        z = h
        parts = []
        per = run / flights
        for f in range(flights):
            parts.append(("prism8", [(x, yr0, 0.0), (x + per, yr0, 0.0), (x + per, yr1, 0.0), (x, yr1, 0.0),
                                     (x, yr0, z), (x + per, yr0, z - per / grad), (x + per, yr1, z - per / grad), (x, yr1, z)]))
            x += per
            z -= per / grad
            if f < flights - 1:
                parts.append(("box", (x, yr0, 0.0, x + land, yr1, z)))
                x += land
        self.ramp_platform = (xc + hb, yr0, x, yr1)
        self.add(Element("ARC-RAMP-PLATFORM-E", "20_ARC_Circulation", "IfcRamp", "STRAIGHT_RUN_RAMP", None, parts,
                         props={"Rise": h, "Gradient_1_in": grad, "Width": rw, "Flights": flights}))
        self.ramps.append({"name": "ARC-RAMP-PLATFORM-E", "rise": h, "gradient_1_in": grad, "width": rw, "flights": flights,
                           "run_per_flight": rnd(per, 2)})
        # guards on the band's side edges and the ramp's open side
        yb0, yb1 = F[1], self.ysw - COL_FACE
        self.strut("ARC-RAIL-PLATFORM-W", "20_ARC_Circulation", "IfcRailing", "GUARDRAIL", (xc - hb + 0.05, y0 + sw + 0.3, h + 1.05),
                   (xc - hb + 0.05, yb1 - 0.05, h + 1.05), 0.05, 0.05, {"Height": 1.1, "Role": "Platform side edge guard"})
        self.strut("ARC-RAIL-PLATFORM-E", "20_ARC_Circulation", "IfcRailing", "GUARDRAIL", (xc + hb - 0.05, yb0 + 0.05, h + 1.05),
                   (xc + hb - 0.05, yr0 - 0.05, h + 1.05), 0.05, 0.05, {"Height": 1.1, "Role": "Platform side edge guard"})
        self.strut("ARC-RAIL-RAMP-PLATFORM", "20_ARC_Circulation", "IfcRailing", "HANDRAIL", (xc + hb + 0.05, yr0 - 0.05, h + 0.9),
                   (x - 0.05, yr0 - 0.05, 0.9), 0.05, 0.05, {"Height": 0.9, "Role": "Ramp handrail / edge guard"})

    # ------------------------------------------------------------------ seats
    def seat_elements(self):
        for s in self.seats:
            self.add(Element(s["seat_id"], "40_SEAT_Congregation", "IfcFurniture", "CHAIR", None, (),
                             origin=(s["x"], s["y"], s["z_floor"]), rot_z=s["rot_z"], mesh_key="CHAIR",
                             props={"Row": s["row"], "Block": s["block"], "SeatNumber": s["seat"], "SeatType": "congregation",
                                    "CountsTowardTarget": True, "FixedSeat": True},
                             object_type="Congregation fixed seat"))

    def accessible_places(self):
        """Front wheelchair places at the outer ends of rows 1-2 (grade) and a dispersed band in the cross aisle."""
        A = self.P["accessibility"]
        S = self.P["seating"]
        ww, wd = A["wheelchair_space_width"], A["wheelchair_space_depth"]
        F = self.F
        places = []
        # front: rows 1-2 of the two centre blocks, either side of the centre aisle (grade, near the axis)
        r = (self.radii[0] + self.radii[1]) / 2
        for side, blk in (("W", self.front_wc_blocks[0]), ("E", self.front_wc_blocks[1])):
            a0 = self.front_aisles[blk - 1] + (S["aisle_width"] / 2 + 0.1) / r
            a1 = self.front_aisles[blk] - (S["aisle_width"] / 2 + 0.1) / r
            n = A["front_pairs_per_side"]
            for k in range(n):
                th_c = a0 + (a1 - a0) * (k + 0.5) / n
                places.append((f"F{side}", k + 1, r, th_c, rnd(self.slope_z(r + wd / 2) + 0.005, 4), f"Front {side} (grade, centre block {blk})"))
        # cross-aisle band: behind the 2.4 m passage, distributed over the rear blocks, clear of aisle mouths
        rb = self.radii[S["front_rows"]] - 0.55 - wd / 2 - 0.05
        rear = self.rear_aisles
        per = [0] * (len(rear) - 1)
        for i in range(A["cross_aisle_pairs"]):
            per[i % len(per)] += 1
        for b in range(len(rear) - 1):
            a0, a1 = rear[b] + (S["aisle_width"] / 2 + 0.3) / rb, rear[b + 1] - (S["aisle_width"] / 2 + 0.3) / rb
            n = per[b]
            for k in range(n):
                th_c = a0 + (a1 - a0) * (k + 0.5) / n
                places.append((f"M{b + 1:02d}", k + 1, rb, th_c, self.cross_level, f"Cross-aisle band, behind block {b + 1}"))
        for zone, k, r, th, z, loc in places:
            x, y = polar(F, r, th)
            rot = math.degrees(th)
            name = f"ACC-WCS-{zone}-{k:02d}"
            corners = chair_corners(x, y, rot, ww / 2, wd / 2)
            self.add(Element(name, "40_SEAT_Accessible", "IfcSpatialZone", "USERDEFINED", None,
                             [("prism_xy", (ccw(corners), z, z + 1.3))],
                             props={"Width": ww, "Depth": wd, "Location": loc, "Status": "Concept wheelchair space"},
                             object_type="WheelchairSpace"))
            # companion loose chair beside the space (tangential neighbour)
            sgn = 1 if th < 0 else -1
            thc = th + sgn * ((ww + A["companion_seat_width"]) / 2) / r
            cx, cy = polar(F, r - (wd / 2 - CHAIR_HALF_D), thc)
            self.add(Element(f"SEAT-K-{zone}-{k:02d}", "40_SEAT_Companion", "IfcFurniture", "CHAIR", None, (),
                             origin=(rnd(cx, 4), rnd(cy, 4), z), rot_z=rnd(math.degrees(thc), 4), mesh_key="CHAIR",
                             props={"SeatType": "companion", "CountsTowardTarget": False, "FixedSeat": False},
                             object_type="Companion loose chair"))
            self.wc_positions.append({"name": name, "group": zone, "x": rnd(x, 3), "y": rnd(y, 3), "z": z, "r": r, "th": th,
                                      "corners": corners, "companion": f"SEAT-K-{zone}-{k:02d}"})

    # ------------------------------------------------------------------ envelope
    def door(self, name, host, axis, c, a_center, width, z, height, role, fire_exit=True, external=True, leaves=None,
             col="10_ENV_Envelope", thickness=0.3, record=None):
        D = self.P["doors"]
        leaves = leaves or max(1, math.ceil(width / D["leaf_max_width"] - 1e-9))
        eff = rnd(width - D["deduction_per_leaf"] * leaves, 3)
        a0, a1 = a_center - width / 2, a_center + width / 2
        t = thickness / 2
        if axis == "x":  # wall along x at y = c
            bb = (a0, c - 0.04, z, a1, c + 0.04, z + height)
            op = (a0, c - t - 0.02, z, a1, c + t + 0.02, z + height)
        else:
            bb = (c - 0.04, a0, z, c + 0.04, a1, z + height)
            op = (c - t - 0.02, a0, z, c + t + 0.02, a1, z + height)
        self.box(name, col, "IfcDoor", "DOOR", bb,
                 {"OverallWidth": width, "OverallHeight": height, "Leaves": leaves, "LeafWidth": rnd(width / leaves, 3),
                  "EffectiveClearWidth": eff, "FireExit": fire_exit, "IsExternal": external, "Role": role,
                  "FireRating": "TBC by fire engineer",
                  "Operation": D["door_hardware"] if fire_exit else "Single/double swing (TBC)"},
                 host=host, opening=op)
        if record is not None:
            rec = {"id": name, "x": rnd((bb[0] + bb[3]) / 2, 3), "y": rnd((bb[1] + bb[4]) / 2, 3), "z": z, "width": width,
                   "clear": eff, "role": role}
            rec.update(record)
            return rec
        return None

    def wall(self, name, axis, c, a0, a1, z0, ztop, openings=(), t=0.3, col="10_ENV_Envelope", pre="SOLIDWALL", props=None,
             cls="IfcWall"):
        """Straight wall along axis 'x' (centred on y = c) or 'y' (centred on x = c). ztop: number or f(a) for a sloped
        top. openings: (a0, a1, z0, z1) holes. Returns the element."""
        zt = ztop if callable(ztop) else (lambda a, v=ztop: v)
        cuts = sorted({a0, a1, *[o[0] for o in openings], *[o[1] for o in openings]})
        parts = []

        def piece(s0, s1, h0, h1, slope):
            if axis == "x":
                pts = [(s0, c - t / 2), (s1, c - t / 2), (s1, c + t / 2), (s0, c + t / 2)]
            else:
                pts = [(c - t / 2, s0), (c + t / 2, s0), (c + t / 2, s1), (c - t / 2, s1)]
            if not slope:
                parts.append(("box", (min(p[0] for p in pts), min(p[1] for p in pts), h0, max(p[0] for p in pts),
                                      max(p[1] for p in pts), h1)))
                return
            za, zb = zt(s0), zt(s1)
            top = [za, zb, zb, za] if axis == "x" else [za, za, zb, zb]
            parts.append(("prism8", [(p[0], p[1], h0) for p in pts] + [(p[0], p[1], z) for p, z in zip(pts, top)]))

        for s0, s1 in zip(cuts, cuts[1:]):
            if s1 - s0 < 1e-6:
                continue
            mid = (s0 + s1) / 2
            holes = sorted((o[2], o[3]) for o in openings if o[0] < mid < o[1])
            zc = z0
            for h0, h1 in holes:
                if h0 > zc + 1e-6:
                    piece(s0, s1, zc, h0, False)
                zc = max(zc, h1)
            if min(zt(s0), zt(s1)) > zc + 1e-6:
                piece(s0, s1, zc, None, True)
        length = a1 - a0
        p = {"Length": rnd(length, 3), "Thickness": t, "Height": rnd(max(zt(a0), zt(a1)) - z0, 3), "IsExternal": col.startswith("10_")}
        p.update(props or {})
        return self.add(Element(name, col, cls, pre, None, parts, props=p))

    def envelope(self):
        P = self.P
        off = P["walls"]["offset_outside_grid"]
        t = P["walls"]["external_thickness"]
        yf, ysw, yb = self.gy["1"], self.ysw, self.gy["5"]
        W = self.W
        DH = P["walls"]["door_height"]
        hx = P["doors"]["hall_exit_width"]
        # ---- hall side walls (x = -off, W + off), y from the rear column line to the stage wall line
        self.side_door_y = {}
        ycr = self.F[1] - self.cross_r[1] * math.cos(self.half) - 1.0
        y_front_exit = ysw - COL_FACE - 3.4
        r_mid = (self.R_rows_back + self.R_out) / 2
        x_in = self.W / 2 - COL_FACE
        y_rp = self.F[1] - math.sqrt(max(r_mid ** 2 - x_in ** 2, 0.0))   # rear passage centreline meets the side column face
        # door centred in the band where the rear passage meets the wall; side-wall posts move clear of it (structure())
        y_band = sorted(self.F[1] - math.sqrt(max(r ** 2 - x_in ** 2, 0.0)) for r in (self.R_rows_back, self.R_out))
        y_rp = (y_band[0] + y_band[1]) / 2
        self.post_avoid = (y_rp - hx / 2 - 0.45, y_rp + hx / 2 + 0.45)
        self.rear_door_in_band = y_band[0] + hx / 2 - 0.3 <= y_rp <= y_band[1] - hx / 2 + 0.3
        self.rear_passage_side_y = y_rp
        for side, xw, sgn in (("W", -off, -1), ("E", W + off, 1)):
            ops, recs = [], []
            # side foyer (rear corner) to ambulatory, at grade, between the first two side posts
            ysf = P["rear_corners"]["ambulatory_door_y"]
            ops.append((ysf - 1.8, ysf + 1.8, 0.0, DH))
            # front-corner exit at grade, rear-passage exit at L02
            for nm, yc, z, role in ((f"DR-HALL-{side}-FRONT", y_front_exit, 0.0, "Hall exit - front corner (grade) to ambulatory"),
                                    (f"DR-HALL-{side}-REAR", y_rp, self.top_level, "Hall exit - rear passage end (L02) to ambulatory stair")):
                ops.append((yc - hx / 2, yc + hx / 2, z, z + DH))
                recs.append((nm, yc, z, role))
            wname = f"ENV-WALL-HALL-{side}"
            self.wall(wname, "y", xw, -off - t / 2, ysw + off + t / 2, 0.0, lambda a: self.bc(a) + 0.0, ops, t,
                      props={"Description": "Hall side wall (outside the column line), top follows the truss bottom chord"})
            for nm, yc, z, role in recs:
                self.exits.append(self.door(nm, wname, "y", xw, yc, hx, z, DH, role, record={"wall": side, "level": "L00" if z == 0 else "L02",
                                                                                                "kind": "to_ambulatory"}))
            self.door(f"DR-CORNER-AMB-{side}", wname, "y", xw, ysf, 3.6, 0.0, DH, "Side foyer to ambulatory (route from the corner stair)",
                      external=False)
            # upper cladding (outside the end truss), truss bottom chord -> roof
            xo = xw + sgn * (t / 2 + 0.1)
            parts = []
            ys = [yf - off - t / 2, 0.0, ysw + off + t / 2]
            for ya, yb_ in zip(ys, ys[1:]):
                pts = [(xo - 0.03, ya), (xo + 0.03, ya), (xo + 0.03, yb_), (xo - 0.03, yb_)]
                za0, zb0 = self.bc(ya), self.bc(yb_)
                za1, zb1 = self.tc(ya) + 0.5, self.tc(yb_) + 0.5
                parts.append(("prism8", [(pts[0][0], pts[0][1], za0), (pts[1][0], pts[1][1], za0), (pts[2][0], pts[2][1], zb0),
                                         (pts[3][0], pts[3][1], zb0), (pts[0][0], pts[0][1], za1), (pts[1][0], pts[1][1], za1),
                                         (pts[2][0], pts[2][1], zb1), (pts[3][0], pts[3][1], zb1)]))
            self.add(Element(f"ENV-CLAD-GABLE-{side}", "10_ENV_Envelope", "IfcWall", "SOLIDWALL", None, parts,
                             props={"Description": "Gable cladding outside the end truss (truss depth zone)", "IsExternal": True,
                                    "Height": rnd(self.td + 0.5, 2), "Thickness": 0.06, "Length": rnd(ysw - yf, 2)}))
        # ---- foyer facade (south), doors + glazing, top = truss bottom chord at grid 1
        F_ = P["foyer"]
        ops = []
        for k, xcn in enumerate(F_["main_door_x_centers"]):
            ops.append((xcn - F_["main_door_width"] / 2, xcn + F_["main_door_width"] / 2, 0.0, DH))
        yfac = yf - off
        xs0, xs1 = -off - 3.5 - 0.6, W + off + 3.5 + 0.6
        self.facade_x = (xs0, xs1)
        wname = "ENV-WALL-EXT-S"
        glaz = []
        for k in range(len(F_["main_door_x_centers"]) - 1):
            a, b = F_["main_door_x_centers"][k] + F_["main_door_width"] / 2 + 1.0, F_["main_door_x_centers"][k + 1] - F_["main_door_width"] / 2 - 1.0
            if b - a > 2.0:
                glaz.append((a, b, 0.9, 3.6))
        self.wall(wname, "x", yfac, xs0, xs1, 0.0, lambda a: min(self.bc(yf), 6.0), ops + glaz, t,
                  props={"Description": "Entrance facade (south long side)"})
        for k, xcn in enumerate(F_["main_door_x_centers"]):
            self.ext_doors.append(self.door(f"DR-EXT-S{k + 1:02d}", wname, "x", yfac, xcn, F_["main_door_width"], 0.0, DH,
                                            "Main entrance / final exit", record={"kind": "external", "wall": "S"}))
        for k, (a, b, z0, z1) in enumerate(glaz):
            self.box(f"WN-FOYER-{k + 1:02d}", "10_ENV_Envelope", "IfcWindow", "WINDOW", (a, yfac - 0.04, z0, b, yfac + 0.04, z1),
                     {"OverallWidth": rnd(b - a, 3), "OverallHeight": rnd(z1 - z0, 3), "IsExternal": True, "Role": "Foyer glazing"},
                     host=wname, opening=(a, yfac - t / 2 - 0.02, z0, b, yfac + t / 2 + 0.02, z1))
        # high-level facade cladding above the foyer wall up to the roof, outside the truss ends
        parts = [("prism8", [(xs0, yfac - 0.18, min(self.bc(yf), 6.0)), (xs1, yfac - 0.18, min(self.bc(yf), 6.0)),
                             (xs1, yfac - 0.12, min(self.bc(yf), 6.0)), (xs0, yfac - 0.12, min(self.bc(yf), 6.0)),
                             (xs0, yfac - 0.18, self.tc(yf - off) + 0.5), (xs1, yfac - 0.18, self.tc(yf - off) + 0.5),
                             (xs1, yfac - 0.12, self.tc(yf - off) + 0.5), (xs0, yfac - 0.12, self.tc(yf - off) + 0.5)])]
        self.add(Element("ENV-CLAD-S", "10_ENV_Envelope", "IfcWall", "SOLIDWALL", None, parts,
                         props={"Description": "Entrance facade upper cladding / high-level louvres (natural ventilation inlet)",
                                "IsExternal": True, "Height": rnd(self.tc(yf) + 0.5 - min(self.bc(yf), 6.0), 2), "Thickness": 0.06,
                                "Length": rnd(xs1 - xs0, 2)}))
        # ---- hall rear wall (internal, between foyer and hall), on the foyer side of grid 2
        yr = -off
        ops = []
        self.rear_doors = []
        rdw = F_["rear_door_width"]
        for k, xcn in enumerate(F_["stair_x_centers"]):
            ops.append((xcn - rdw / 2, xcn + rdw / 2, self.top_level, self.top_level + DH))
        bx = F_["booth"]["x"]
        booth_floor = self.top_level + F_["booth"]["floor_raise"]
        bdx = F_["booth"]["door_x"]
        ops.append((bdx - 0.45, bdx + 0.45, self.top_level, self.top_level + 2.1))  # booth door
        ops.append((bx[0] + 0.5, bx[1] - 0.5, booth_floor + 0.9, booth_floor + 2.1))                                   # booth window
        lx = F_["lift_x"]
        ops.append((lx[0] + 0.2, lx[1] - 0.2, self.top_level, self.top_level + 2.1))                                  # lift door L02
        rc = P["rear_corners"]
        self.corner_doors_x = tuple(rc["foyer_door_x"])
        for xcn in self.corner_doors_x:
            ops.append((xcn - 1.2, xcn + 1.2, 0.0, DH))
        wname = "ENV-WALL-HALL-S"
        wtop = self.bc(yr - t / 2) - P["structure"]["chord_section"] / 2 - 0.02
        self.wall(wname, "x", yr, -off - t / 2, W + off + t / 2, 0.0, lambda a: wtop, ops, t, col="20_ARC_Walls",
                  pre="SOLIDWALL", props={"Description": "Hall rear wall (foyer side of grid 2), up to the truss bottom chord",
                                          "IsExternal": False})
        for k, xcn in enumerate(F_["stair_x_centers"]):
            self.exits.append(self.door(f"DR-HALL-S{k + 1}", wname, "x", yr, xcn, rdw, self.top_level, DH,
                                        "Hall exit - rear landing (L02) to foyer stair", external=False,
                                        record={"wall": "S", "level": "L02", "kind": "to_foyer_stair"}))
        self.door("DR-BOOTH", wname, "x", yr, bdx, 0.9, self.top_level, 2.1, "Booth door from rear landing",
                  fire_exit=False, external=False, col="20_ARC_Walls")
        self.box("WN-BOOTH", "20_ARC_Walls", "IfcWindow", "WINDOW", (bx[0] + 0.5, yr - 0.04, booth_floor + 0.9, bx[1] - 0.5, yr + 0.04, booth_floor + 2.1),
                 {"OverallWidth": rnd(bx[1] - bx[0] - 1.0, 3), "OverallHeight": 1.2, "IsExternal": False, "Role": "Booth viewing window"},
                 host=wname, opening=(bx[0] + 0.5, yr - t / 2 - 0.02, booth_floor + 0.9, bx[1] - 0.5, yr + t / 2 + 0.02, booth_floor + 2.1))
        self.door("DR-LIFT-L02", wname, "x", yr, (lx[0] + lx[1]) / 2, lx[1] - lx[0] - 0.4, self.top_level, 2.1, "Lift door at L02",
                  fire_exit=False, external=False, col="20_ARC_Walls")
        for k, xcn in enumerate(self.corner_doors_x):
            self.door(f"DR-CORNER-{'W' if k == 0 else 'E'}", wname, "x", yr, xcn, 2.4, 0.0, DH,
                      "Side foyer (toilets) from the main foyer", fire_exit=True, external=False, col="20_ARC_Walls")
        # upper infill between trusses above the rear wall (bottom chord -> top chord), clear of chords
        xs = sorted(v for k, v in self.gx.items() if k not in ("A0", "L1"))
        parts = []
        for xa, xb in zip(xs, xs[1:]):
            parts.append(("box", (xa + 0.25, yr - 0.03, wtop, xb - 0.25, yr + 0.03,
                                  self.tc(yr - 0.03) - P["structure"]["chord_section"] / 2 - P["structure"]["brace_section"] - 0.02)))
        self.add(Element("ENV-CLAD-REAR-INFILL", "20_ARC_Walls", "IfcWall", "PARTITIONING", None, parts,
                         props={"Description": "Acoustic infill between trusses above the hall rear wall", "IsExternal": False,
                                "Height": rnd(self.td, 2), "Thickness": 0.06, "Length": rnd(W, 2)}))
        # ---- stage wall (north of the hall), on the back-of-house side of grid 4
        ys = ysw + off
        ops = []
        sdw = P["doors"]["stage_exit_width"]
        ramp_end = self.xc + self.hb + P["stage"]["platform_height"] * P["stage"]["ramp_gradient_1_in"] + P["stage"]["ramp_landing"]
        self.stage_door_x = (self.xc - self.hb - 5.6, ramp_end + 0.6 + sdw / 2)
        for xcn in self.stage_door_x:
            ops.append((xcn - sdw / 2, xcn + sdw / 2, 0.0, DH))
        gd = P["doors"]["goods_door_x"]
        ops.append((gd - 2.0, gd + 2.0, P["stage"]["platform_height"], P["stage"]["platform_height"] + 3.0))  # band / goods door
        STR = P["structure"]
        bz0 = P["back_of_house"]["roof_top"] - 0.3 - STR["low_roof_beam_depth"]
        for k, xg in self.gx.items():
            if k not in ("A0", "L1"):
                ops.append((xg - STR["beam_width"] / 2 - 0.02, xg + STR["beam_width"] / 2 + 0.02, bz0 - 0.02, bz0 + STR["low_roof_beam_depth"] + 0.02))
        wname = "ENV-WALL-HALL-N"
        self.wall(wname, "x", ys, -off - t / 2, W + off + t / 2, 0.0, lambda a: self.bc(ysw), ops, t, col="20_ARC_Walls",
                  props={"Description": "Stage wall (back-of-house side of grid 4)", "IsExternal": False})
        for k, xcn in enumerate(self.stage_door_x):
            rec = self.door(f"DR-STAGE-{'W' if k == 0 else 'E'}", wname, "x", ys, xcn, sdw, 0.0, DH,
                            "Hall exit beside the platform to the back-of-house corridor (protected route to BOH exits)", external=False, leaves=2,
                            col="20_ARC_Walls", record={"wall": "N", "level": "L00", "kind": "to_boh"})
            self.exits.append(rec)
        hp = P["stage"]["platform_height"]
        self.door("DR-STAGE-GOODS", wname, "x", ys, gd, 4.0, hp, 3.0, "Platform to band store (goods)", fire_exit=False,
                  external=False, leaves=2, col="20_ARC_Walls")
        # stage wall upper part above the BOH roof is external: cladding outside the truss end + high louvres
        bohr = P["back_of_house"]["roof_top"]
        self.box("ENV-CLAD-N", "10_ENV_Envelope", "IfcWall", "SOLIDWALL",
                 (-off - t / 2, ys + 0.12, self.bc(ysw), W + off + t / 2, ys + 0.18, self.tc(ysw + off) + 0.5),
                 {"Description": "Stage wall high cladding with high-level louvres (stack-effect outlet, concept)", "IsExternal": True,
                  "Height": rnd(self.tc(ysw) + 0.5 - self.bc(ysw), 2), "Thickness": 0.06, "Length": rnd(W + 2 * off, 2)})
        # ---- main roof: one mono-pitch plane over foyer + hall (sheeting + insulation build-up)
        STR = P["structure"]
        rb = STR["roof_build_up"]
        zb = 0.175 + STR["purlin_section"][1] + 0.01
        x0r, x1r = -off - t / 2 - 0.3, W + off + t / 2 + 0.3
        y0r, y1r = yf - off - t / 2 - 0.6, ysw + off + t / 2 + 0.3
        self.add(Element("ENV-ROOF-MAIN", "10_ENV_Envelope", "IfcSlab", "ROOF", None,
                         [("prism8", [(x0r, y0r, self.tc(y0r) + zb), (x1r, y0r, self.tc(y0r) + zb), (x1r, y1r, self.tc(y1r) + zb),
                                      (x0r, y1r, self.tc(y1r) + zb), (x0r, y0r, self.tc(y0r) + zb + rb), (x1r, y0r, self.tc(y0r) + zb + rb),
                                      (x1r, y1r, self.tc(y1r) + zb + rb), (x0r, y1r, self.tc(y1r) + zb + rb)])],
                         props={"IsExternal": True, "Description": f"Mono-pitch metal roof {STR['roof_pitch_deg']:.0f} deg over foyer + hall",
                                "StoreyOverride": "L02: roof plane (high-level)"}))
        self.roof_main = (x0r, y0r, x1r, y1r)
        self.roof_area_main = (x1r - x0r) * (y1r - y0r) / math.cos(math.atan(self.tan))
        # canopy over the entrance doors
        cd = 4.0
        self.box("ENV-CANOPY", "10_ENV_Envelope", "IfcSlab", "ROOF", (xs0, yfac - t / 2 - cd, 3.6, xs1, yfac - t / 2, 3.85),
                 {"IsExternal": True, "Description": "Continuous entrance canopy (shade + rain at the doors)"}, "Entrance canopy")
        # eaves gutter on the entrance facade (low edge of the main roof) + downpipes on the facade
        zg = self.tc(y0r) + zb - 0.05
        gw, gd_ = P["drainage"]["gutter"]
        self.box("SRV-GUTTER-S", "50_SRV_Drainage", "IfcPipeSegment", "GUTTER", (x0r, y0r - gw, zg - gd_, x1r, y0r, zg),
                 {"Role": "Main roof eaves gutter (external, entrance facade, overflow weirs away from the doors) - concept, size TBC"})
        self.downpipes = 0
        nd = P["drainage"]["downpipes"]
        for k, xd in enumerate([x0r + 2.0 + i * (x1r - x0r - 4.0) / (nd - 1) for i in range(nd)]):
            if any(abs(xd - d) < 2.6 for d in F_["main_door_x_centers"]):
                xd += 3.0
            self.box(f"SRV-DOWNPIPE-S{k + 1:02d}", "50_SRV_Drainage", "IfcPipeSegment", "RIGIDSEGMENT",
                     (xd - 0.075, y0r - 0.3, 0.0, xd + 0.075, y0r - 0.15, zg - gd_),
                     {"Role": "Downpipe to rainwater harvesting tank / soakaway (concept)"})
            self.downpipes += 1

    # ------------------------------------------------------------------ rear corners (side foyers, toilets)
    def rear_corners(self):
        P = self.P
        rc = P["rear_corners"]
        F, R = self.F, self.R_out
        t = P["walls"]["internal_thickness"]
        DH = P["walls"]["door_height"]
        # faceted wall along the outside of the rear passage, from the rear landing to the side column face
        x_in = self.W / 2 - COL_FACE
        th_wall = math.asin(min(x_in / (R + t), 1.0))
        lx0, lx1 = self.rear_landing_x
        th_land = math.asin((F[0] - lx0) / (R + t))
        rcw = R + t / 2
        nfac = max(2, math.ceil(math.degrees(th_wall - th_land) / rc["arc_wall_facet_deg"]))
        door_th = math.radians(rc["rear_passage_door_deg"])
        self.arc_walls = []
        for side, sgn in (("W", -1), ("E", 1)):
            angs = [th_land + (th_wall - th_land) * i / nfac for i in range(nfac + 1)]
            for i in range(nfac):
                a, b = angs[i], angs[i + 1]
                pa, pb = polar(F, rcw, sgn * a), polar(F, rcw, sgn * b)
                name = f"ARC-WALL-ARC-{side}-{i + 1:02d}"
                has_door = a <= door_th < b
                L = math.hypot(pb[0] - pa[0], pb[1] - pa[1])
                ux, uy = (pb[0] - pa[0]) / L, (pb[1] - pa[1]) / L
                nx, ny = -uy * t / 2, ux * t / 2

                def quad(s0, s1):
                    q0, q1 = (pa[0] + ux * s0, pa[1] + uy * s0), (pa[0] + ux * s1, pa[1] + uy * s1)
                    return ccw([(q0[0] - nx, q0[1] - ny), (q1[0] - nx, q1[1] - ny), (q1[0] + nx, q1[1] + ny), (q0[0] + nx, q0[1] + ny)])
                ztop = self.bc(min(pa[1], pb[1]) - t) - P["structure"]["chord_section"] / 2 - 0.02
                if not has_door:
                    self.add(Element(name, "20_ARC_Walls", "IfcWall", "PARTITIONING", None, [("prism_xy", (quad(0, L), 0.0, ztop))],
                                     props={"Length": rnd(L, 3), "Thickness": t, "Height": rnd(ztop, 2), "IsExternal": False,
                                            "Description": "Faceted hall wall behind the rear passage (side foyer side)"}))
                    continue
                dw = P["doors"]["hall_exit_width"]
                s0, s1 = L / 2 - dw / 2, L / 2 + dw / 2
                zd0, zd1 = self.top_level, self.top_level + DH
                parts = [("prism_xy", (quad(0, s0), 0.0, ztop)), ("prism_xy", (quad(s1, L), 0.0, ztop)),
                         ("prism_xy", (quad(s0, s1), 0.0, zd0)), ("prism_xy", (quad(s0, s1), zd1, ztop))]
                self.add(Element(name, "20_ARC_Walls", "IfcWall", "PARTITIONING", None, parts,
                                 props={"Length": rnd(L, 3), "Thickness": t, "Height": rnd(ztop, 2), "IsExternal": False,
                                        "Description": "Faceted hall wall with rear-passage exit door"}))
                dq = quad(s0, s1)
                inner = [(x - nx * 0.7, y - ny * 0.7) for x, y in dq]
                xs, ys = [p[0] for p in dq], [p[1] for p in dq]
                dname = f"DR-HALL-ARC-{side}"
                self.add(Element(dname, "20_ARC_Walls", "IfcDoor", "DOOR", None, [("prism_xy", (ccw(inner), zd0, zd1))],
                                 props={"OverallWidth": dw, "OverallHeight": DH, "Leaves": 3, "LeafWidth": rnd(dw / 3, 3),
                                        "EffectiveClearWidth": rnd(dw - 3 * P["doors"]["deduction_per_leaf"], 3), "FireExit": True,
                                        "IsExternal": False, "Role": "Hall exit - rear passage (L02) to side-foyer stair",
                                        "FireRating": "TBC by fire engineer", "Operation": P["doors"]["door_hardware"]},
                                 host=name, opening=(min(xs), min(ys), zd0, max(xs), max(ys), zd1)))
                mid = polar(F, rcw, sgn * (a + b) / 2)
                self.exits.append({"id": dname, "x": rnd(mid[0], 3), "y": rnd(mid[1], 3), "z": self.top_level, "width": dw,
                                   "clear": rnd(dw - 3 * P["doors"]["deduction_per_leaf"], 3), "wall": f"arc-{side}", "level": "L02",
                                   "kind": "to_corner_stair", "role": "Hall exit - rear passage (L02) to side-foyer stair",
                                   "th": sgn * (a + b) / 2})
                self.arc_door = (a, b)
                # stair from the door landing down into the side foyer, running along x towards the side wall
                self.corner_stair(side, sgn, mid)
        # toilet blocks in each rear corner (W female, E male), each with 2 accessible WCs, entered from the main foyer
        tb = rc["toilet_block"]
        tx0, ty0, tx1, ty1 = COL_FACE + 0.15, COL_FACE + 0.15, tb[2], tb[3]
        for side in ("W", "E"):
            if side == "W":
                X0, X1 = tx0, tx1
            else:
                X0, X1 = self.W - tx1, self.W - tx0
            use = "female" if side == "W" else "male"
            wca_w, wca_d = rc["wca_width"], rc["wca_depth"]
            # partitions: north wall, inner (towards centre) wall; WCA pair at the inner end along the rear wall
            xin = X1 if side == "W" else X0
            xout = X0 if side == "W" else X1
            sg = 1 if side == "W" else -1
            self.box(f"ARC-WALL-WC-{side}-N", "20_ARC_Walls", "IfcWall", "PARTITIONING",
                     (min(X0, X1), ty1, 0.0, max(X0, X1), ty1 + t, 3.2),
                     {"Length": rnd(abs(X1 - X0), 3), "Thickness": t, "Height": 3.2, "IsExternal": False})
            # inner wall with door to the toilets from the side foyer
            dy = (ty0 + ty1) / 2 + 1.5
            self.wall(f"ARC-WALL-WC-{side}-X", "y", xin + sg * t / 2, ty0, ty1, 0.0, 3.2, [(dy - 0.75, dy + 0.75, 0.0, 2.4)], t,
                      col="20_ARC_Walls", pre="PARTITIONING", props={"IsExternal": False})
            self.door(f"DR-WC-{side}", f"ARC-WALL-WC-{side}-X", "y", xin + sg * t / 2, dy, 1.5, 0.0, 2.4,
                      f"Toilets ({use}) from side foyer", fire_exit=False, external=False, col="20_ARC_Walls", thickness=t)
            # accessible WCs: two rooms against the inner wall at the south end
            for k in range(2):
                ya, yb_ = ty0 + k * wca_d, ty0 + (k + 1) * wca_d
                xa = xin - sg * wca_w
                self.box(f"ARC-WALL-WCA-{side}{k + 1}-N", "20_ARC_Walls", "IfcWall", "PARTITIONING",
                         (min(xa, xin), yb_ - t / 2, 0.0, max(xa, xin), yb_ + t / 2, 3.2),
                         {"Length": wca_w, "Thickness": t, "Height": 3.2, "IsExternal": False})
            wy0, wy1 = ty0, ty0 + 2 * wca_d
            xa = xin - sg * wca_w
            ops = [(wy0 + 0.5, wy0 + 1.5, 0.0, 2.2), (wy0 + wca_d + 0.5, wy0 + wca_d + 1.5, 0.0, 2.2)]
            self.wall(f"ARC-WALL-WCA-{side}-X", "y", xa - sg * t / 2, wy0, wy1, 0.0, 3.2, ops, t, col="20_ARC_Walls",
                      pre="PARTITIONING", props={"IsExternal": False})
            for k in range(2):
                self.door(f"DR-WCA-{side}{k + 1}", f"ARC-WALL-WCA-{side}-X", "y", xa - sg * t / 2, wy0 + k * wca_d + 1.0, 1.0, 0.0, 2.2,
                          "Accessible WC", fire_exit=False, external=False, col="20_ARC_Walls", thickness=t)
                self.spaces.append({"id": f"SP-WCA-{side}{k + 1}", "name": f"Accessible WC {side}{k + 1}", "level": "L00",
                                    "poly": rect(min(xa, xin), wy0 + k * wca_d, max(xa, xin), wy0 + (k + 1) * wca_d),
                                    "use": "Accessible WC", "door": f"DR-WCA-{side}{k + 1}"})
            lo, hi = min(X0, X1), max(X0, X1)
            beside = rect(lo, ty0, xa - t, wy1) if side == "W" else rect(xa + t, ty0, hi, wy1)
            self.spaces.append({"id": f"SP-WC-{side}", "name": f"Toilets {side} ({use})", "level": "L00", "use": "Toilets",
                                "door": f"DR-WC-{side}", "rects": [rect(lo, wy1 + t / 2, hi, ty1), beside]})
        self.toilet_y1 = ty1

    def corner_stair(self, side, sgn, door_mid):
        F_ = self.P["foyer"]
        rc = self.P["rear_corners"]
        h = self.top_level
        n = math.ceil(round(h / F_["stair_max_riser"], 6))
        riser = h / n
        g = F_["stair_going"]
        sw = rc["stair_width"]
        land = 1.6
        # landing outside the door (at L02), then flight descending away from the hall towards -y (south)
        x0 = door_mid[0] - sw / 2
        t = self.P["walls"]["internal_thickness"]

        def wall_y(x):
            return self.F[1] - math.sqrt((self.R_out + t) ** 2 - (x - self.F[0]) ** 2) - 0.05
        ya, yb_ = wall_y(x0), wall_y(x0 + sw)
        y_top = min(ya, yb_)
        parts = [("prism_xy", (ccw([(x0, y_top - land), (x0 + sw, y_top - land), (x0 + sw, yb_), (x0, ya)]), 0.0, h))]
        run, y, n, riser, nfl = self.stair_run(x0, sw, y_top - land, h)
        parts += run
        name = f"ARC-STAIR-CORNER-{side}"
        self.add(Element(name, "20_ARC_Circulation", "IfcStair", "STRAIGHT_RUN_STAIR", None, parts,
                         props={"Riser": rnd(riser, 3), "Risers": n, "Going": g, "Width": sw, "Flights": nfl}))
        self.stairs.append({"name": name, "width": sw, "riser": rnd(riser, 3), "risers": n, "flights": nfl, "foot_y": rnd(y, 2),
                            "bbox": (x0, y, x0 + sw, y_top)})
        self.stair_rails(f"ARC-RAIL-CORNER-{side}", x0, sw, y_top - land + 0.05, y, h, riser)

    def stair_run(self, x0, sw, y_start, h, sign=-1):
        """Straight stair descending from height h at y_start along sign*y, in flights of <= max_flight_risers with
        landings between. Returns (parts, y_end, risers, riser, flights) - review LS-B (no 18-riser single flights)."""
        F_ = self.P["foyer"]
        n = math.ceil(round(h / F_["stair_max_riser"], 6))
        riser = h / n
        g, land = F_["stair_going"], F_["stair_mid_landing"]
        nfl = math.ceil(n / F_["max_flight_risers"])
        per = math.ceil(n / nfl)
        parts, y = [], y_start
        for k in range(1, n):
            length = land if k % per == 0 else g
            y2 = y + sign * length
            parts.append(("box", (x0, min(y, y2), 0.0, x0 + sw, max(y, y2), h - riser * k)))
            y = y2
        return parts, y, n, riser, nfl

    def stair_rails(self, prefix, x0, sw, y_top, y_end, h, riser, centre=False):
        xs = [x0 + 0.05, x0 + sw - 0.05] + ([x0 + sw / 2] if centre else [])
        for k, xr in enumerate(xs):
            self.strut(f"{prefix}-{k + 1}", "20_ARC_Circulation", "IfcRailing", "HANDRAIL", (xr, y_top, h + 0.9),
                       (xr, y_end + (0.3 if y_end < y_top else -0.3), 0.9 + riser), 0.05, 0.05,
                       {"Height": 0.9, "Role": "Stair centre handrail" if k == 2 else "Stair handrail / guard"})

    # ------------------------------------------------------------------ foyer
    def foyer(self):
        P = self.P
        F_ = P["foyer"]
        off = P["walls"]["offset_outside_grid"]
        t = P["walls"]["external_thickness"]
        yf = self.gy["1"]
        h = self.top_level
        xs0, xs1 = self.facade_x
        self.box("ARC-SLAB-FOYER", "20_ARC_Floors", "IfcSlab", "FLOOR", (xs0 + t / 2, yf - off + t / 2, -0.25, xs1 - t / 2, -off - t / 2, 0.0),
                 {"Description": "Foyer slab (grade)"})
        sw, land = F_["stair_width"], F_["stair_landing"]
        y_wall = -off - t / 2
        for k, xcn in enumerate(F_["stair_x_centers"]):
            x0 = xcn - sw / 2
            run, y, n, riser, nfl = self.stair_run(x0, sw, y_wall - land, h)
            parts = [("box", (x0, y_wall - land, 0.0, x0 + sw, y_wall, h))] + run
            name = f"ARC-STAIR-FOYER-{'W' if k == 0 else 'E'}"
            self.add(Element(name, "20_ARC_Circulation", "IfcStair", "STRAIGHT_RUN_STAIR", None, parts,
                             props={"Riser": rnd(riser, 3), "Risers": n, "Going": F_["stair_going"], "Width": sw, "Flights": nfl}))
            self.stairs.append({"name": name, "width": sw, "riser": rnd(riser, 3), "risers": n, "flights": nfl, "foot_y": rnd(y, 2),
                                "bbox": (x0, y, x0 + sw, y_wall)})
            self.stair_rails(f"ARC-RAIL-FOYER-{'W' if k == 0 else 'E'}", x0, sw, y_wall - land + 0.05, y, h, riser, centre=True)
        self.foyer_stair_foot = y
        # booth: raised floor on a deck between the stair heads, over the foyer
        bx, bd = F_["booth"]["x"], F_["booth"]["depth"]
        bf = h + F_["booth"]["floor_raise"]
        self.box("ARC-BOOTH", "20_ARC_Floors", "IfcSlab", "FLOOR", (bx[0], y_wall - bd, bf - 0.25, bx[1], y_wall, bf),
                 {"Description": "Sound / media booth floor (raised over the foyer)", "StoreyOverride": "L02: booth"})
        bh = F_["booth"]["height"]
        for nm, bb in (("W", (bx[0], y_wall - bd, bf, bx[0] + 0.15, y_wall, bf + bh)), ("E", (bx[1] - 0.15, y_wall - bd, bf, bx[1], y_wall, bf + bh)),
                       ("S", (bx[0], y_wall - bd, bf, bx[1], y_wall - bd + 0.15, bf + bh))):
            self.box(f"ARC-WALL-BOOTH-{nm}", "20_ARC_Walls", "IfcWall", "PARTITIONING", bb,
                     {"Length": rnd(max(bb[3] - bb[0], bb[4] - bb[1]), 3), "Thickness": 0.15, "Height": bh, "IsExternal": False})
        self.box("ARC-SLAB-BOOTH-ROOF", "20_ARC_Floors", "IfcSlab", "ROOF", (bx[0], y_wall - bd, bf + bh, bx[1], y_wall, bf + bh + 0.2),
                 {"Description": "Booth roof / ceiling slab"})
        # booth landing step (from L02 door up to the booth floor) is inside the booth: three risers, not modelled separately
        self.spaces.append({"id": "SP-08", "name": "Sound / media booth", "level": "L02", "poly": rect(bx[0], y_wall - bd, bx[1], y_wall),
                            "z": bf, "use": "Sound / media booth", "door": "DR-BOOTH"})
        # booth support columns (2) at its south corners
        for k, xx in enumerate((bx[0] + 0.2, bx[1] - 0.2)):
            yy = y_wall - bd + 0.2
            self.box(f"STR-COL-BOOTH-{k + 1}", "30_STR_Columns", "IfcColumn", "COLUMN", (xx - 0.15, yy - 0.15, -0.9, xx + 0.15, yy + 0.15, bf - 0.25),
                     {"Role": "booth support", "NominalSection": "0.30x0.30 placeholder", "DesignStatus": "Space reservation only - not designed"})
            self.box(f"STR-FTG-BOOTH-{k + 1}", "30_STR_Foundations", "IfcFooting", "PAD_FOOTING", (xx - 0.6, yy - 0.6, -1.5, xx + 0.6, yy + 0.6, -0.9),
                     {"DesignStatus": "Reference location only - no geotechnical data, not designed"})
            self.columns[f"STR-COL-BOOTH-{k + 1}"] = (xx, yy, 0.3)
        # lift (shaft allowance from the foyer to L02)
        lx = F_["lift_x"]
        self.box("ARC-LIFT", "20_ARC_Circulation", "IfcTransportElement", "ELEVATOR", (lx[0], y_wall - 2.4, 0.0, lx[1], y_wall, h + 2.4),
                 {"Status": "Space allowance - lift type/capacity not selected"})
        self.spaces.append({"id": "SP-09", "name": "Lift shaft", "level": "L00", "poly": rect(lx[0], y_wall - 2.4, lx[1], y_wall),
                            "use": "Lift", "door": "DR-LIFT-L02"})
        self.lift = (lx[0], y_wall - 2.4, lx[1], y_wall)
        ysw_ = y_wall - 2.4 - 0.075
        self.wall("ARC-WALL-LIFT-S", "x", ysw_, lx[0] - 0.15, lx[1] + 0.15, 0.0, h + 2.4, [(lx[0] + 0.2, lx[1] - 0.2, 0.0, 2.1)], 0.15,
                  col="20_ARC_Walls", pre="PARTITIONING", props={"IsExternal": False, "Description": "Lift shaft front wall"})
        self.door("DR-LIFT-L00", "ARC-WALL-LIFT-S", "x", ysw_, (lx[0] + lx[1]) / 2, lx[1] - lx[0] - 0.4, 0.0, 2.1, "Lift door at L00 (foyer)",
                  fire_exit=False, external=False, col="20_ARC_Walls", thickness=0.15)

    # ------------------------------------------------------------------ ambulatories
    def ambulatories(self):
        P = self.P
        AM = P["ambulatory"]
        off = P["walls"]["offset_outside_grid"]
        t = P["walls"]["external_thickness"]
        DH = P["walls"]["door_height"]
        ysw = self.ysw
        h = self.top_level
        F_ = P["foyer"]
        for side, sgn in (("W", -1), ("E", 1)):
            xh = -off if side == "W" else self.W + off                      # hall wall centre
            xo = xh + sgn * (t / 2 + AM["width"] + t / 2)                     # ambulatory outer wall centre
            xa, xb = sorted((xh + sgn * t / 2, xo - sgn * t / 2))
            y0, y1 = -off - t / 2, ysw + off + t / 2
            self.box(f"ARC-SLAB-AMB-{side}", "20_ARC_Floors", "IfcSlab", "FLOOR", (xa, y0, -0.25, xb, y1, 0.0), {"Description": f"Ambulatory {side} slab"})
            ydoor = y1 - AM["ext_door_y_from_north"] - 1.2
            wname = f"ENV-WALL-AMB-{side}"
            self.wall(wname, "y", xo, y0 - t / 2, y1 + t / 2, 0.0, AM["roof_top"] - 0.3,
                      [(ydoor - 1.8, ydoor + 1.8, 0.0, DH), (ydoor - 1.8 - 9.0, ydoor + 1.8 - 9.0, 0.0, DH)], t,
                      props={"Description": f"Ambulatory {side} outer wall"})
            for k, yd in enumerate((ydoor, ydoor - 9.0)):
                self.ext_doors.append(self.door(f"DR-EXT-AMB-{side}{k + 1}", wname, "y", xo, yd, 3.6, 0.0, DH,
                                                "Ambulatory final exit", record={"kind": "external", "wall": side}))
            self.box(f"ENV-ROOF-AMB-{side}", "10_ENV_Envelope", "IfcSlab", "ROOF",
                     (min(xa, xb) - (0.3 if side == "W" else 0), y0, AM["roof_top"] - 0.25, max(xa, xb) + (0.3 if side == "E" else 0), y1, AM["roof_top"]),
                     {"IsExternal": True, "Description": f"Ambulatory {side} roof (low)"})
            # stair in the ambulatory from the rear-passage side door (L02) down, running south along the ambulatory
            sw = AM["stair_width"]
            yd = self.rear_passage_side_y
            land = 3.8
            sx0 = xa + 0.1 if side == "W" else xb - 0.1 - sw
            run, y, n, riser, nfl = self.stair_run(sx0, sw, yd - land / 2, h)
            parts = [("box", (sx0, yd - land / 2, 0.0, sx0 + sw, yd + land / 2, h))] + run
            name = f"ARC-STAIR-AMB-{side}"
            self.add(Element(name, "20_ARC_Circulation", "IfcStair", "STRAIGHT_RUN_STAIR", None, parts,
                             props={"Riser": rnd(riser, 3), "Risers": n, "Going": F_["stair_going"], "Width": sw, "Flights": nfl}))
            self.stairs.append({"name": name, "width": sw, "riser": rnd(riser, 3), "risers": n, "flights": nfl, "foot_y": rnd(y, 2),
                                "bbox": (sx0, y, sx0 + sw, yd + land / 2)})
            self.stair_rails(f"ARC-RAIL-AMB-{side}", sx0, sw, yd - land / 2 + 0.05, y, h, riser)
            self.spaces.append({"id": f"SP-AMB-{side}", "name": f"Ambulatory {side} (covered circulation / egress)", "level": "L00",
                                "poly": rect(xa, y0, xb, y1), "use": "Circulation"})
            self.amb_x = getattr(self, "amb_x", {})
            self.amb_x[side] = (xa, xb)

    # ------------------------------------------------------------------ choir and front corners
    def choir_zones(self):
        P = self.P
        CH = P["stage"]["choir"]
        S = P["seating"]
        F = self.F
        hb = self.hb
        ysw_in = self.ysw - COL_FACE
        # cross-aisle ends: steps down to the front-corner floor (grade), running north from the radial end face
        rise = self.cross_pass_level
        self.corner_ramps = {}
        for side, sgn in (("W", -1), ("E", 1)):
            r0, r1 = self.cross_r[0], self.band_r[0]
            th = sgn * self.fan_limit(self.cross_r[1])
            p_in, p_out = polar(F, r0, th), polar(F, r1, th)
            xr0, xr1 = sorted((p_in[0], p_out[0]))
            ystart = max(p_in[1], p_out[1]) + 0.02
            lp = ccw([p_in, p_out, (p_out[0], ystart), (p_in[0], ystart)])
            if poly_area(lp) > 0.01:
                self.add(Element(f"ARC-SLAB-CROSSEND-{side}", "20_ARC_Floors", "IfcSlab", "LANDING", None,
                                 [("prism_xy", (lp, 0.0, rise))], props={"Description": "Cross-aisle end landing"}))
            A_ = P["accessibility"]
            rw = A_["cross_end_ramp_width"]
            rx = (xr0, xr0 + rw) if side == "W" else (xr1 - rw, xr1)
            run = rise * A_["ramp_gradient_1_in"]
            self.add(Element(f"ARC-RAMP-CROSS-{side}", "20_ARC_Circulation", "IfcRamp", "STRAIGHT_RUN_RAMP", None,
                             [("prism8", [(rx[0], ystart, 0.0), (rx[1], ystart, 0.0), (rx[1], ystart + run, 0.0), (rx[0], ystart + run, 0.0),
                                          (rx[0], ystart, rise), (rx[1], ystart, rise), (rx[1], ystart + run, 0.0), (rx[0], ystart + run, 0.0)])],
                             props={"Rise": rnd(rise, 3), "Gradient_1_in": A_["ramp_gradient_1_in"], "Width": rw, "Flights": 1,
                                    "Role": "Step-free link: front corner (grade) to the cross-aisle passage"}))
            self.ramps.append({"name": f"ARC-RAMP-CROSS-{side}", "rise": rnd(rise, 3), "gradient_1_in": A_["ramp_gradient_1_in"],
                               "width": rw, "flights": 1, "run_per_flight": rnd(run, 2), "bbox": (rx[0], ystart, rx[1], ystart + run)})
            if side == "W":
                xr0 = rx[1] + 0.05
            else:
                xr1 = rx[0] - 0.05
            nst = max(2, math.ceil(round(rise / 0.17, 6)))
            rs = rise / nst
            sparts = [("box", (xr0, ystart + k * 0.3, 0.0, xr1, ystart + (k + 1) * 0.3, rise - rs * (k + 1))) for k in range(nst - 1)]
            self.add(Element(f"ARC-STAIR-CROSS-{side}", "20_ARC_Circulation", "IfcStair", "STRAIGHT_RUN_STAIR", None, sparts,
                             props={"Riser": rnd(rs, 3), "Risers": nst, "Going": 0.3, "Width": rnd(xr1 - xr0, 2)}))
            self.stairs.append({"name": f"ARC-STAIR-CROSS-{side}", "width": rnd(xr1 - xr0, 2), "riser": rnd(rs, 3), "risers": nst})
            self.corner_ramps[side] = (min(xr0, rx[0]), ystart, max(xr1, rx[1]), ystart + run)
        cl = CH["clearance"]
        # choir: straight rows facing across to the platform (west wing faces +x, east wing faces -x)
        ylo_edge = []
        pitch, sp = CH["row_pitch"], CH["chair_spacing"]
        n_total = 0
        self.choir_blocks = {}
        corridor = 2.4
        for side, sgn in (("W", -1), ("E", 1)):
            xr0, yr0, xr1, yr1 = self.corner_ramps[side]
            # usable rectangle: from the wall aisle to the platform side clearance; from the corridor along the stage wall
            # down to the edge-aisle boundary (+ clearance), avoiding the ramp/steps footprint (+ clearance)
            if side == "W":
                xa, xb = COL_FACE + S["wall_aisle"] + 0.2, self.stair_platform[0] - cl
            else:
                xa, xb = self.xc + hb + cl, self.W - COL_FACE - S["wall_aisle"] - 0.2
            ytop = ysw_in - corridor
            if side == "E":
                ytop = min(ytop, self.ramp_platform[1] - cl)
            rows = []
            x = xa + CHAIR_HALF_D if side == "W" else xb - CHAIR_HALF_D
            k_row = 0
            while (side == "W" and x + CHAIR_HALF_D <= xb) or (side == "E" and x - CHAIR_HALF_D >= xa):
                # edge-aisle boundary at this x: the fan floor extends to the edge aisle's outer edge
                ok_y = []
                y = ytop - CHAIR_HALF_W
                while y - CHAIR_HALF_W > F[1] - 20:
                    c = chair_corners(x, y, 90.0 * (-sgn))
                    bad = False
                    for cx, cy in c:
                        r = math.hypot(cx - F[0], cy - F[1])
                        th = math.atan2(cx - F[0], F[1] - cy)
                        if abs(th) <= self.fan_limit(max(r, 1.0)) + (cl / max(r, 1.0)) and cy < F[1] + 0.01:
                            bad = True
                        if cx < xr1 + cl and cx > xr0 - cl and cy > yr0 - cl and cy < yr1 + cl:
                            bad = True
                        if poly_dist((cx, cy), self.platform_poly) < cl:
                            bad = True
                    if bad:
                        break
                    ok_y.append(y)
                    y -= sp
                if ok_y:
                    k_row += 1
                    rows.append((x, ok_y))
                x += pitch if side == "W" else -pitch
            tr, tmax, tper = CH["riser_height"], CH["max_tiers"], CH["rows_per_tier"]
            nrw = len(rows)
            for i, (x, ys) in enumerate(rows):
                tier = min((nrw - 1 - i) // tper, tmax)      # rows further from the platform stand higher
                zc = rnd(tr * tier, 3)
                if zc > 0:
                    self.box(f"ARC-CHOIR-RISER-{side}-R{i + 1:02d}", "20_ARC_Floors", "IfcSlab", "FLOOR",
                             (x - pitch / 2, min(ys) - CHAIR_HALF_W - 0.4, 0.0, x + pitch / 2, max(ys) + CHAIR_HALF_W + 0.1, zc),
                             {"Description": f"Choir riser tier {tier} (+{zc:.2f})"})
                for j, y in enumerate(ys):
                    name = f"SEAT-H-{side}-R{i + 1:02d}-S{j + 1:02d}"
                    self.add(Element(name, "40_SEAT_Choir", "IfcFurniture", "CHAIR", None, (), origin=(rnd(x, 4), rnd(y, 4), zc),
                                     rot_z=-90.0 if side == "W" else 90.0, mesh_key="CHAIR",
                                     props={"SeatType": "choir", "CountsTowardTarget": False, "FixedSeat": False, "ChoirSection": side,
                                            "Facing": "+X (towards the platform)" if side == "W" else "-X (towards the platform)"},
                                     object_type="Choir seat (excluded from the 3,000)"))
                    self.choir.append({"name": name, "x": x, "y": y, "z": zc, "side": side, "rot": -90.0 if side == "W" else 90.0})
                    n_total += 1
            self.choir_blocks[side] = rows
            # wheelchair choir place at the corridor end of the row nearest the platform (grade tier)
            if rows:
                x, ys = rows[-1]
                y = ys[0] + 0.3 + 0.7 + 0.05
                if y + 0.7 <= ysw_in - 1.2:
                    c = chair_corners(x, y, -90.0 if side == "W" else 90.0, 0.45, 0.7)
                    self.add(Element(f"ACC-WCS-CHOIR-{side}-01", "40_SEAT_Accessible", "IfcSpatialZone", "USERDEFINED", None,
                                     [("prism_xy", (ccw(c), 0.0, 1.3))], props={"Width": 0.9, "Depth": 1.4, "ChoirPlace": True,
                                                                                "Location": f"Choir {side} (grade, step-free)",
                                                                                "Status": "Concept - accessible choir place"},
                                     object_type="WheelchairSpace"))
                    self.wc_choir = getattr(self, "wc_choir", 0) + 1
        self.metrics["choir_seats"] = n_total

    # ------------------------------------------------------------------ back of house
    def back_of_house(self):
        P = self.P
        B = P["back_of_house"]
        off = P["walls"]["offset_outside_grid"]
        t, ti = P["walls"]["external_thickness"], P["walls"]["internal_thickness"]
        ys0 = self.ysw + off + t / 2
        yb = self.gy["5"]
        yn = yb + off
        DH = P["walls"]["door_height"]
        x0, x1 = -off - t / 2, self.W + off + t / 2
        self.box("ARC-SLAB-BOH", "20_ARC_Floors", "IfcSlab", "FLOOR", (x0, ys0, -0.25, x1, yn - t / 2, 0.0), {"Description": "Back-of-house slab"})
        bw_ = P["doors"]["boh_exit_width"]
        bdx = self.stage_door_x                       # passages line up with the stage-side hall exits (review LS-B critical)
        self.boh_passages = [(x - bw_ / 2, x + bw_ / 2) for x in bdx]
        ops = [(x - bw_ / 2, x + bw_ / 2, 0.0, DH) for x in bdx]
        wname = "ENV-WALL-EXT-N"
        self.wall(wname, "x", yn, x0 - 0.0, x1, 0.0, B["roof_top"] - 0.3, ops, t, props={"Description": "Back-of-house north wall"})
        for k, xd in enumerate(bdx):
            self.ext_doors.append(self.door(f"DR-EXT-BOH-{'W' if k == 0 else 'E'}", wname, "x", yn, xd, bw_, 0.0, DH,
                                            "Final exit at the end of a back-of-house exit passage", record={"kind": "external", "wall": "N"}))
        for side, xw in (("W", -off), ("E", self.W + off)):
            self.box(f"ENV-WALL-BOH-{side}", "10_ENV_Envelope", "IfcWall", "SOLIDWALL", (xw - t / 2, ys0, 0.0, xw + t / 2, yn - t / 2, B["roof_top"] - 0.3),
                     {"Length": rnd(yn - ys0, 3), "Thickness": t, "Height": B["roof_top"] - 0.3, "IsExternal": True})
        self.box("ENV-ROOF-BOH", "10_ENV_Envelope", "IfcSlab", "ROOF", (x0, ys0, B["roof_top"] - 0.3, x1, yn + t / 2 + 0.3, B["roof_top"] - 0.05),
                 {"IsExternal": True, "Description": "Back-of-house low roof (plant platform allowance)"})
        yc = ys0 + B["corridor_depth"]
        rooms = B["rooms"]
        ops = [(a, b, 0.0, DH) for a, b in self.boh_passages]     # open passage mouths (no door)
        for code, name, xa, xb in rooms:
            xd = (xa + xb) / 2
            ops.append((xd - 0.6, xd + 0.6, 0.0, DH))
        for k, (a, b) in enumerate(self.boh_passages):
            sd = "W" if k == 0 else "E"
            for j, xw in enumerate((a - ti / 2, b + ti / 2)):
                self.box(f"ARC-WALL-BOH-EXIT-{sd}{j + 1}", "20_ARC_Walls", "IfcWall", "PARTITIONING", (xw - ti / 2, yc + ti, 0.0, xw + ti / 2, yn - t / 2, 3.2),
                         {"Length": rnd(yn - t / 2 - yc - ti, 3), "Thickness": ti, "Height": 3.2, "IsExternal": False,
                          "Description": "Back-of-house exit passage wall (fire separation TBC)"})
            self.spaces.append({"id": f"SP-BOH-X-{sd}", "name": f"BOH exit passage {sd}", "level": "L00", "poly": rect(a, yc + ti, b, yn - t / 2),
                                "use": "Circulation (escape)"})
        cw = "ARC-WALL-BOH-CORRIDOR"
        self.wall(cw, "x", yc + ti / 2, x0 + t, x1 - t, 0.0, 3.2, ops, ti, col="20_ARC_Walls", pre="PARTITIONING",
                  props={"IsExternal": False})
        self.spaces.append({"id": "SP-BOH-C", "name": "BOH corridor", "level": "L00", "poly": rect(x0 + t, ys0, x1 - t, yc), "use": "Circulation"})
        for code, name, xa, xb in rooms:
            xd = (xa + xb) / 2
            self.door(f"DR-{code}", cw, "x", yc + ti / 2, xd, 1.2, 0.0, DH, name, fire_exit=False, external=False, col="20_ARC_Walls",
                      thickness=ti)
            if xb < self.W - 0.5 and not any(abs(xb - a) < 0.2 or abs(xb - b) < 0.2 for a, b in self.boh_passages):
                on_grid = any(abs(xb - v) < 0.35 for v in self.gx.values())
                ye = yb - P["structure"]["other_column"] / 2 if on_grid else yn - t / 2
                self.box(f"ARC-WALL-{code}-E", "20_ARC_Walls", "IfcWall", "PARTITIONING", (xb - ti / 2, yc + ti, 0.0, xb + ti / 2, ye, 3.2),
                         {"Length": rnd(ye - yc - ti, 3), "Thickness": ti, "Height": 3.2, "IsExternal": False})
            self.spaces.append({"id": f"SP-{code}", "name": name, "level": "L00",
                                "poly": rect(max(xa, x0 + t) + (ti / 2 if xa > 0.5 else 0), yc + ti, min(xb, x1 - t) - ti / 2, yn - t / 2),
                                "use": name, "door": f"DR-{code}"})

    # ------------------------------------------------------------------ structure
    def structure(self):
        P = self.P
        STR = P["structure"]
        hc, oc = STR["hall_column"], STR["other_column"]
        pz, pt = STR["pad_top_z"], STR["pad_thickness"]
        xs_keys = [k for k in self.gx if k not in ("A0", "L1")]
        yf, ysw, yb = self.gy["1"], self.ysw, self.gy["5"]
        cs, ws = STR["chord_section"], STR["web_section"]
        self.member_count = 0
        cols = []

        def column(name, x, y, z_top, size, role, pad):
            self.box(name, "30_STR_Columns", "IfcColumn", "COLUMN", (x - size / 2, y - size / 2, pz, x + size / 2, y + size / 2, z_top),
                     {"Role": role, "NominalSection": f"{size:.2f}x{size:.2f} placeholder", "Grid": name.split("STR-COL-")[1],
                      "DesignStatus": "Space reservation only - not designed"})
            self.box(name.replace("STR-COL", "STR-FTG"), "30_STR_Foundations", "IfcFooting", "PAD_FOOTING",
                     (x - pad / 2, y - pad / 2, pz - pt, x + pad / 2, y + pad / 2, pz),
                     {"Grid": name.split("STR-COL-")[1], "DesignStatus": "Reference location only - no geotechnical data, not designed"})
            self.columns[name] = (x, y, size)
            cols.append(name)

        # truss support columns on grids 1, 2, 4 for every lettered line
        for k in xs_keys:
            x = self.gx[k]
            for gy_k, y, role in (("1", yf, "foyer facade (truss back-span support)"), ("2", 0.0, "hall rear (truss support)"),
                                  ("4", ysw, "stage wall (truss support)")):
                size = hc if gy_k in ("2", "4") else oc
                ztop = self.bc(y) - cs / 2 if gy_k != "1" else self.tc(y) + cs / 2 - STR["foyer_rafter_depth"]
                column(f"STR-COL-{k}{gy_k}", x, y, ztop, size, role.replace("truss back-span support", "foyer rafter support"),
                       STR["pad_hall"] if size == hc else STR["pad_other"])
        # side-wall posts between grid 2 and 4 (wind posts / gable frame)
        nb = STR["side_post_bays"]
        self.side_posts_y = [ysw * i / nb for i in range(nb + 1)]
        lo, hi = self.post_avoid
        self.side_posts_y = [(lo if y - lo < hi - y else hi) if lo < y < hi else y for y in self.side_posts_y]
        for k in ("A", "L"):
            for i in range(1, nb):
                y = self.side_posts_y[i]
                column(f"STR-COL-{k}-P{i}", self.gx[k], y, self.bc(y) - cs / 2, oc, "side-wall post (end frame)", STR["pad_other"])
        # back-of-house columns on grid 5 (supporting the low roof beams)
        bohz = P["back_of_house"]["roof_top"] - 0.3 - STR["low_roof_beam_depth"]
        for k in xs_keys:
            column(f"STR-COL-{k}5", self.gx[k], yb, bohz, oc, "back-of-house", STR["pad_other"])
        self.metrics["column_count"] = len(cols)
        # ---- trusses: continuous over grids 1, 2, 4; Pratt webs; panel points
        ypan = []
        nb_main = max(2, round(ysw / STR["truss_panel_target"]))
        if nb_main % 2:
            nb_main += 1
        ypan += [ysw * i / nb_main for i in range(nb_main + 1)]
        self.truss_panels = ypan
        self.truss_count = 0
        for k in xs_keys:
            x = self.gx[k]
            tname = f"STR-TRUSS-{k}"
            mid = (yf + ysw) / 2
            idx = 0

            def mem(role, p0, p1, sec, i=[0]):
                i[0] += 1
                self.strut(f"{tname}-{role}{i[0]:02d}", "30_STR_Roof_Trusses", "IfcMember", "CHORD" if role in ("TC", "BC") else "MEMBER",
                           p0, p1, sec, sec, {"Assembly": tname, "MemberRole": role, "DesignStatus": "Placeholder section"})
                self.elements[-1].assembly = tname
                self.member_count += 1
            for a, b in zip(ypan, ypan[1:]):
                mem("TC", (x, a, self.tc(a)), (x, b, self.tc(b)), cs)
                mem("BC", (x, a, self.bc(a)), (x, b, self.bc(b)), cs)
            for i, y in enumerate(ypan):
                mem("V", (x, y, self.bc(y) + cs / 2), (x, y, self.tc(y) - cs / 2), ws)
            for i in range(len(ypan) - 1):
                a, b = ypan[i], ypan[i + 1]
                # Pratt: diagonals slope down towards the nearest support (0 or ysw) - tension under gravity
                # Pratt: each diagonal runs from the top chord at its support-side node down to the bottom chord towards
                # mid-span, so it is in tension under gravity (review STR-B minor: previous orientation was Howe)
                if (a + b) / 2 < ysw / 2:
                    p0, p1 = (x, a, self.tc(a)), (x, b, self.bc(b))
                else:
                    p0, p1 = (x, a, self.bc(a)), (x, b, self.tc(b))
                mem("D", p0, p1, ws)
            self.truss_count += 1
        self.metrics["truss_count"] = self.truss_count
        self.metrics["truss_main_span"] = rnd(ysw, 2)
        # foyer: simply supported rafters grid 1 -> 2 (continuity over grid 2 released - review STR-B: back-span uplift)
        rd = STR["foyer_rafter_depth"]
        for k in xs_keys:
            x = self.gx[k]
            za, zb = self.tc(yf) + cs / 2 - rd / 2, self.tc(0.0) + cs / 2 - rd / 2
            self.strut(f"STR-BEAM-FOYER-{k}", "30_STR_Beams", "IfcBeam", "BEAM", (x, yf, za), (x, 0.0, zb), STR["beam_width"], rd,
                       {"Role": "Foyer roof rafter, simply supported grid 1 -> 2 (no continuity with the hall truss)"})
        self.metrics["foyer_rafter_span"] = rnd(-yf, 2)
        # ---- purlins along x between trusses at TC level
        ps = STR["purlin_section"]
        npur = max(2, round((ysw - yf) / STR["purlin_spacing_target"]))
        ypur = [yf + (ysw - yf) * (i + 0.5) / npur for i in range(npur)]
        xs = [self.gx[k] for k in xs_keys]
        np_ = 0
        for j, y in enumerate(ypur):
            if abs(y - 0.0) < 0.6:
                y += 0.8
            z = self.tc(y) + cs / 2 + ps[1] / 2
            for xa, xb in zip(xs, xs[1:]):
                np_ += 1
                self.strut(f"STR-PURLIN-{j + 1:02d}-{np_:03d}", "30_STR_Roof_Trusses", "IfcMember", "PURLIN",
                           (xa, y, z), (xb, y, z), ps[0], ps[1], {})
        self.metrics["purlin_count"] = np_
        # ---- roof bracing (top-chord plane) in braced bays, between panel points
        bs = STR["brace_section"]
        nbr = 0
        for ka, kb in STR["roof_braced_bays"]:
            xa, xb = self.gx[ka], self.gx[kb]
            for i in range(0, len(ypan) - 1, 2):
                a, b = ypan[i], ypan[min(i + 2, len(ypan) - 1)]
                for p0, p1 in (((xa, a), (xb, b)), ((xa, b), (xb, a))):
                    nbr += 1
                    self.strut(f"STR-BRACE-ROOF-{ka}{kb}-{nbr:03d}", "30_STR_Bracing", "IfcMember", "BRACE",
                               (p0[0], p0[1], self.tc(p0[1]) - cs / 2 - bs / 2), (p1[0], p1[1], self.tc(p1[1]) - cs / 2 - bs / 2), bs, bs, {})
        # ---- vertical bracing: long walls (grids 2 and 4) in end bays, side walls in chosen post bays
        for gk, y in (("2", 0.0), ("4", ysw)):
            for ka, kb in STR["long_braced_bays"]:
                xa, xb = self.gx[ka] + hc / 2, self.gx[kb] - hc / 2
                z0, z1 = 0.3, self.bc(y) - cs
                for p0, p1 in (((xa, z0), (xb, z1)), ((xa, z1), (xb, z0))):
                    nbr += 1
                    self.strut(f"STR-BRACE-WALL-{gk}{ka}{kb}-{nbr:03d}", "30_STR_Bracing", "IfcMember", "BRACE",
                               (p0[0], y, p0[1]), (p1[0], y, p1[1]), bs, bs, {"Role": "Longitudinal braced bay"})
        for k in ("A", "L"):
            x = self.gx[k]
            for bay in STR["side_braced_bays"]:
                ya, yb_ = self.side_posts_y[bay - 1] + (hc / 2 if bay == 1 else oc / 2), self.side_posts_y[bay] - oc / 2
                z0 = 0.3
                z1a, z1b = self.bc(ya) - cs, self.bc(yb_) - cs
                for p0, p1 in (((ya, z0), (yb_, z1b)), ((ya, z1a), (yb_, z0))):
                    nbr += 1
                    self.strut(f"STR-BRACE-WALL-{k}{bay}-{nbr:03d}", "30_STR_Bracing", "IfcMember", "BRACE",
                               (x, p0[0], p0[1]), (x, p1[0], p1[1]), bs, bs, {"Role": "Transverse braced bay (side wall)"})
        # eaves-line horizontal bracing along both long walls in every bay (wind on the 80 m faces -> end walls; review STR-B)
        braced = {tuple(b) for b in STR["roof_braced_bays"]}
        for ka, kb in zip(xs_keys, xs_keys[1:]):
            if (ka, kb) in braced:
                continue
            xa, xb = self.gx[ka], self.gx[kb]
            for tag, (a, b) in (("2", (ypan[0], ypan[1])), ("4", (ypan[-2], ypan[-1]))):
                for p0, p1 in (((xa, a), (xb, b)), ((xa, b), (xb, a))):
                    nbr += 1
                    self.strut(f"STR-BRACE-ROOF-EAVES{tag}-{ka}{kb}-{nbr:03d}", "30_STR_Bracing", "IfcMember", "BRACE",
                               (p0[0], p0[1], self.tc(p0[1]) - cs / 2 - bs / 2), (p1[0], p1[1], self.tc(p1[1]) - cs / 2 - bs / 2), bs, bs,
                               {"Role": f"Eaves-line wind girder along grid {tag}"})
        self.metrics["brace_count"] = nbr
        # ---- low roofs: ambulatory and BOH beams
        bw, bd = STR["beam_width"], STR["low_roof_beam_depth"]
        nb_ = 0
        for k in xs_keys:
            x = self.gx[k]
            z = bohz + bd / 2
            nb_ += 1
            self.strut(f"STR-BEAM-LOW-BOH-{k}", "30_STR_Beams", "IfcBeam", "BEAM", (x, ysw + hc / 2, z), (x, yb - oc / 2, z), bw, bd, {})
        self.metrics["beam_count"] = nb_
        self.connections_checked = self.member_count

    # ------------------------------------------------------------------ AV and services
    def av_services(self):
        AV = self.P["av"]
        F = (self.xc, self.ysw - COL_FACE)
        self.screens = []
        for s in AV["screens"]:
            cx, cz = F[0] + s["center_offset"][0], s["center_offset"][2]
            cy = (self.ysw - COL_FACE - 0.35) if s["name"] == "MAIN-C" else (self.F[1] + s["center_offset"][1])
            yaw = math.radians(s["yaw_deg"])
            n = (math.sin(yaw), -math.cos(yaw))
            hw = s["width"] / 2
            ux, uy = -n[1], n[0]
            p0, p1 = (cx - ux * hw, cy - uy * hw), (cx + ux * hw, cy + uy * hw)
            q = ccw([(p0[0] - n[0] * 0.1, p0[1] - n[1] * 0.1), (p1[0] - n[0] * 0.1, p1[1] - n[1] * 0.1),
                     (p1[0] + n[0] * 0.1, p1[1] + n[1] * 0.1), (p0[0] + n[0] * 0.1, p0[1] + n[1] * 0.1)])
            self.add(Element(f"SRV-AV-SCREEN-{s['name']}", "50_SRV_AV", "IfcAudioVisualAppliance", "DISPLAY", None,
                             [("prism_xy", (q, cz - s["height"] / 2, cz + s["height"] / 2))],
                             props={"Role": s["role"], "Width": s["width"], "Height": s["height"], "YawDeg": s["yaw_deg"],
                                    "Rigging": AV["rigging_load_note"]}))
            self.screens.append({"name": s["name"], "c": (cx, cy, cz), "n": n, "w": s["width"], "h": s["height"]})
        for s in AV["speakers"]:
            cx, cy, cz = self.F[0] + s["center_offset"][0], self.F[1] + s["center_offset"][1], s["center_offset"][2]
            sx, sy, sz = s["size"]
            self.box(f"SRV-AV-SPK-{s['name']}", "50_SRV_AV", "IfcAudioVisualAppliance", "SPEAKER",
                     (cx - sx / 2, cy - sy / 2, cz - sz / 2, cx + sx / 2, cy + sy / 2, cz + sz / 2),
                     {"Role": s["role"], "Rigging": AV["rigging_load_note"]})
        zones = [
            ("SRV-01", "Rainwater harvesting tank allowance (below grade, foyer frontage)", (20.0, self.gy["1"] - 14.0, -3.0, 60.0, self.gy["1"] - 10.0, 0.0)),
            ("SRV-02", "Front-of-house lighting / AV rig allowance (below trusses, over the front rows)",
             (self.xc - 18.0, self.F[1] - 16.0, self.bc(self.F[1] - 16.0) - 1.4, self.xc + 18.0, self.F[1] - 6.0, self.bc(self.F[1] - 16.0) - 0.2)),
            ("SRV-03", "Electrical / data riser allowance", (66.0, self.ysw + 3.6, 0.0, 67.4, self.ysw + 4.8, 4.0)),
            ("SRV-04", "Plumbing riser allowance (west toilets)", (1.0, self.toilet_y1 - 1.6, 0.0, 1.8, self.toilet_y1 - 0.2, 3.0)),
            ("SRV-05", "Plumbing riser allowance (east toilets)", (self.W - 1.8, self.toilet_y1 - 1.6, 0.0, self.W - 1.0, self.toilet_y1 - 0.2, 3.0)),
            ("SRV-06", "HVAC / condensing units on the back-of-house roof (allowance)", (40.0, self.ysw + 1.0, 5.0, 78.0, self.gy["5"] - 1.0, 7.0)),
        ]
        for code, name, bb in zones:
            self.box(code, "50_SRV_Allowances", "IfcSpatialZone", "USERDEFINED", bb, {"LongName": name, "Status": "Space allowance only - no MEP design"},
                     "ServiceAllowance")

    # ------------------------------------------------------------------ spaces
    def space_zones(self):
        """IfcSpace volumes: every space is a set of convex plan polygons extruded from its floor."""
        F = self.F
        off = self.P["walls"]["offset_outside_grid"]
        t = self.P["walls"]["external_thickness"]
        # seating hall: the fan floor from the thrust edge to the rear passage outer edge (clipped to walls)
        hall_polys = self.annulus(self.Rd + 0.05, self.R_out)
        self.spaces.append({"id": "SP-01", "name": "Auditorium seating hall (fan)", "level": "L00", "rects": hall_polys,
                            "use": "Assembly - congregation seating (3,000 fixed seats)"})
        self.spaces.append({"id": "SP-02", "name": "Platform / pulpit (thrust)", "level": "L00",
                            "rects": [rect(self.xc - self.hb, F[1], self.xc + self.hb, self.ysw - COL_FACE)] +
                            [[(polar(F, self.Rd, math.radians(i))[0], F[1]), (polar(F, self.Rd, math.radians(i + 10))[0], F[1]),
                              polar(F, self.Rd, math.radians(i + 10)), polar(F, self.Rd, math.radians(i))] for i in range(-90, 90, 10)],
                            "use": "Platform"})
        # front corners: between the fan edge ray and the stage wall, outside the platform
        for side, sgn in (("W", -1), ("E", 1)):
            th = self.half + (self.P["seating"]["aisle_width"] / 2) / 30.0
            xw = COL_FACE if side == "W" else self.W - COL_FACE
            r_w = abs(xw - F[0]) / math.sin(th)
            pw = polar(F, r_w, sgn * th)
            xp = self.xc + sgn * self.hb
            rp = abs(xp - F[0]) / math.sin(th)
            pp = polar(F, rp, sgn * th)
            yN = self.ysw - COL_FACE
            A = [(xw, pw[1] + 0.05), (xp, pp[1] + 0.05), (xp, yN), (xw, yN)]
            p1 = polar(F, self.Rd + 0.06, sgn * th)
            B = [(xp, pp[1] + 0.05), (p1[0], p1[1] + 0.05), (polar(F, self.Rd, sgn * math.pi / 2)[0], F[1]), (xp, F[1])]
            self.spaces.append({"id": f"SP-0{3 if side == 'W' else 4}", "name": f"Front corner {side} (choir / platform access)", "level": "L00",
                                "rects": [A, B], "use": "Choir, circulation"})
        # rear corners (side foyers): rectangle minus fan, approximated by vertical strips outside R_out
        for side, sgn in (("W", -1), ("E", 1)):
            strips = []
            n = 16
            xw = COL_FACE if side == "W" else self.W - COL_FACE
            x_end = self.rear_landing_x[0] if side == "W" else self.rear_landing_x[1]
            for k in range(n):
                xa = xw + (x_end - xw) * k / n
                xb = xw + (x_end - xw) * (k + 1) / n
                ya = F[1] - math.sqrt(max(self.R_out ** 2 - (xa - F[0]) ** 2, 0.0)) - 0.2
                yb_ = F[1] - math.sqrt(max(self.R_out ** 2 - (xb - F[0]) ** 2, 0.0)) - 0.2
                ylim = min(ya, yb_)
                lo = COL_FACE
                if ylim - lo > 0.05:
                    strips.append(rect(min(xa, xb), lo, max(xa, xb), ylim))
            self.spaces.append({"id": f"SP-05{side}", "name": f"Side foyer {side} (rear corner, incl. toilets)", "level": "L00",
                                "rects": strips, "use": "Foyer / circulation", "gross_contains_toilets": True})
        xs0, xs1 = self.facade_x
        self.spaces.append({"id": "SP-06", "name": "Main foyer", "level": "L00", "poly": rect(xs0 + t / 2, self.gy["1"] - off + t / 2, xs1 - t / 2, -off - t / 2),
                            "use": "Foyer"})
        # write the spaces as IfcSpace elements; areas from plan polygons
        self.space_area_total = 0.0
        for sp in self.spaces:
            polys = sp.get("rects") or ([sp["poly"]] if sp.get("poly") else [])
            if not polys:
                continue
            area = sum(poly_area(p) for p in polys)
            sp["area"] = rnd(area, 2)
            z = sp.get("z", 0.0)
            self.prism_multi(f"SPC-{sp['id'].replace('SP-', 'SP')}", "60_ZONE_Spaces", "IfcSpace", "INTERNAL", polys, z, z + 2.5,
                             {"LongName": sp["name"], "GrossFloorArea": rnd(area, 2), "Use": sp.get("use", ""),
                              "Status": "Concept allowance - unverified"})
            self.space_area_total += area

    # ------------------------------------------------------------------ egress
    def egress(self):
        """Plan-distance egress model: seat -> along its row to an aisle -> along the aisle to a passage (front zone,
        cross aisle or rear passage) -> along the passage to a hall exit; then exit -> nearest final exit.
        Placeholder factors only (same as Option A)."""
        P = self.P
        E = P["egress_placeholders"]
        S = P["seating"]
        F = self.F
        wa = S["aisle_width"]
        nf = S["front_rows"]
        r_front = self.Rd + 1.5
        r_cross = (self.cross_r[0] + self.cross_r[1]) / 2
        r_rear = (self.R_rows_back + self.R_out) / 2
        ex = {e["id"]: e for e in self.exits}
        stair_of = {"DR-HALL-S1": "ARC-STAIR-FOYER-W", "DR-HALL-S2": "ARC-STAIR-FOYER-E", "DR-HALL-ARC-W": "ARC-STAIR-CORNER-W",
                    "DR-HALL-ARC-E": "ARC-STAIR-CORNER-E", "DR-HALL-W-REAR": "ARC-STAIR-AMB-W", "DR-HALL-E-REAR": "ARC-STAIR-AMB-E"}
        sw = {st["name"]: st["width"] for st in self.stairs}
        for e in self.exits:
            e["stair"] = stair_of.get(e["id"])
            e["capacity_width"] = rnd(min(e["clear"], sw[e["stair"]]) if e["stair"] else e["clear"], 3)
        # passages -> exits: (passage, angle on passage, extra Euclidean leg to the door)

        def arcd(r, a, b):
            return r * abs(a - b)
        side_door = {"W": ex["DR-HALL-W-FRONT"], "E": ex["DR-HALL-E-FRONT"]}
        stage_door = {"W": ex["DR-STAGE-W"], "E": ex["DR-STAGE-E"]}
        rear_side = {"W": ex["DR-HALL-W-REAR"], "E": ex["DR-HALL-E-REAR"]}
        arc_door = {"W": ex["DR-HALL-ARC-W"], "E": ex["DR-HALL-ARC-E"]}
        rear_c = [ex["DR-HALL-S1"], ex["DR-HALL-S2"]]

        def routes_from_passage(kind, th):
            """(exit id, distance from the passage point at angle th) for every exit reachable from that passage."""
            out = []
            if kind in ("front", "cross"):
                r = r_front if kind == "front" else r_cross
                for side, sgn in (("W", -1), ("E", 1)):
                    th_end = sgn * (self.half + (wa / 2) / r)
                    pend = polar(F, r, th_end)
                    if kind == "cross":
                        rx0, ry0, rx1, ry1 = self.corner_ramps[side]
                        pend = ((rx0 + rx1) / 2, ry1 + 0.3)
                        base = arcd(r, th, th_end) + math.hypot(pend[0] - polar(F, r, th_end)[0], pend[1] - polar(F, r, th_end)[1])
                    else:
                        base = arcd(r, th, th_end)
                    for d in (side_door[side], stage_door[side]):
                        out.append((d["id"], base + math.hypot(d["x"] - pend[0], d["y"] - pend[1])))
            if kind == "rear":
                r = r_rear
                for side, sgn in (("W", -1), ("E", 1)):
                    d = rear_side[side]
                    th_end = sgn * math.asin(min((self.W / 2 - COL_FACE) / r, 1.0))
                    pend = polar(F, r, th_end)
                    out.append((d["id"], arcd(r, th, th_end) + math.hypot(d["x"] - pend[0], d["y"] - pend[1])))
                    d = arc_door[side]
                    out.append((d["id"], arcd(r, th, d["th"])))
                for d in rear_c:
                    thd = math.asin(max(-1.0, min(1.0, (d["x"] - F[0]) / r)))
                    pd = polar(F, r, thd)
                    out.append((d["id"], arcd(r, th, thd) + math.hypot(d["x"] - pd[0], d["y"] - pd[1])))
            return out

        # every occupant point: seats, wheelchair places (+ companions), choir, platform party
        occupants = []
        for s in self.seats:
            occupants.append(("seat", s["seat_id"], s))
        for w in self.wc_positions:
            occupants.append(("wc", w["name"], w))
            occupants.append(("companion", w["companion"], w))
        results = []
        for kind, oid, s in occupants:
            r, th = s["r"], s["th"]
            row = s.get("row")
            if row is None:
                section = "front" if r < self.cross_r[0] else "cross"
            else:
                section = "front" if row <= nf else "rear"
            options = []
            if section == "cross":
                options += [(e, d) for e, d in routes_from_passage("cross", th)]
            else:
                aisles = self.front_aisles if section == "front" else self.rear_aisles
                b = max(i for i in range(len(aisles) - 1) if aisles[i] <= th + 1e-9) if th >= aisles[0] else 0
                b = min(b, len(aisles) - 2)
                for a in (aisles[b], aisles[b + 1]):
                    along = arcd(r, th, a)
                    # wall-clipped row end: the wall aisle is nearer than the edge aisle
                    if abs(a) >= self.half - 1e-6:
                        x_wall = COL_FACE + S["wall_aisle"] / 2 if a < 0 else self.W - COL_FACE - S["wall_aisle"] / 2
                        if abs(polar(F, r, a)[0] - F[0]) > abs(x_wall - F[0]):
                            a_w = math.copysign(math.asin(min(abs(x_wall - F[0]) / r, 1.0)), a)
                            along = arcd(r, th, a_w)
                    if section == "front":
                        legs = [("front", r - r_front), ("cross", r_cross - r)]
                    else:
                        legs = [("cross", r - r_cross), ("rear", r_rear - r)]
                    for pk, dr in legs:
                        for e, d in routes_from_passage(pk, a):
                            options.append((e, along + abs(dr) + d))
            if kind in ("wc", "companion"):
                options = [o for o in options if ex[o[0]]["level"] == "L00"]
            best = min(options, key=lambda o: o[1])
            results.append({"occupant": oid, "kind": kind, "x": s["x"], "y": s["y"], "exit": best[0], "travel_hall": rnd(best[1], 2),
                            "travel_nearest": rnd(best[1], 2), "options": options})
        # choir and platform party: nearest of their side's front door / stage door
        for c in self.choir:
            opts = [(d["id"], math.hypot(d["x"] - c["x"], d["y"] - c["y"])) for d in (side_door[c["side"]], stage_door[c["side"]])]
            best = min(opts, key=lambda o: o[1])
            results.append({"occupant": c["name"], "kind": "choir", "x": c["x"], "y": c["y"], "exit": best[0], "travel_hall": rnd(best[1], 2),
                            "travel_nearest": rnd(best[1], 2), "options": opts})
        npl = E["platform_occupants"]
        for k in range(npl):
            side = "W" if k % 2 == 0 else "E"
            px = self.xc + (-1 if side == "W" else 1) * (self.hb * (k // 2 + 1) / (npl // 2 + 1))
            py = self.F[1] + 2.0
            opts = [(d["id"], math.hypot(d["x"] - px, d["y"] - py) + 4.0) for d in (side_door[side], stage_door[side])]
            best = min(opts, key=lambda o: o[1])
            results.append({"occupant": f"PLATFORM-{k + 1:02d}", "kind": "platform", "x": px, "y": py, "exit": best[0],
                            "travel_hall": rnd(best[1], 2), "travel_nearest": rnd(best[1], 2), "options": opts})
        # final exits: distance from each hall exit to its nearest external door (+ stair length for L02 exits)
        finals = {}
        extd = {d["id"]: d for d in self.ext_doors}
        doors_by_name = {el.name: el for el in self.elements if el.ifc_class == "IfcDoor"}
        self.discharge = {}
        for e in self.exits:
            route = self.discharge_route(e["id"])
            cands = [extd[d] for d in route["finals"]]
            best = min(cands, key=lambda d: math.hypot(d["x"] - e["x"], d["y"] - e["y"]))
            stair = 0.0 if e["level"] == "L00" else 8.0
            finals[e["id"]] = (best["id"], math.hypot(best["x"] - e["x"], best["y"] - e["y"]) + stair)
            self.discharge[e["id"]] = {"via": route["via"], "final": best["id"],
                                       "doors_fire_exit": all(doors_by_name[d].props.get("FireExit") for d in route["via"] + [best["id"]])}
        # queue-balanced assignment: start nearest, then move occupants from overloaded exits to their next-best exit
        load = {}
        for r_ in results:
            load[r_["exit"]] = load.get(r_["exit"], 0) + 1
        w_lvl, w_st = E["level_width_mm_per_person"] / 1000, E["stair_width_mm_per_person"] / 1000

        def demand_ok(eid, n):
            return ex[eid]["capacity_width"] >= n * (w_st if ex[eid]["level"] == "L02" else w_lvl)
        for it in range(20):
            moved = 0
            for r_ in sorted(results, key=lambda r: -r["travel_hall"]):
                if demand_ok(r_["exit"], load[r_["exit"]]):
                    continue
                alts = sorted(set(o for o in r_["options"]), key=lambda o: o[1])
                for eid, d in alts:
                    if eid != r_["exit"] and demand_ok(eid, load.get(eid, 0) + 1) and d <= r_["travel_hall"] + 25.0:
                        load[r_["exit"]] -= 1
                        load[eid] = load.get(eid, 0) + 1
                        r_["exit"], r_["travel_hall"] = eid, rnd(d, 2)
                        moved += 1
                        break
            if not moved:
                break
        for r_ in results:
            fe, fd = finals[r_["exit"]]
            r_["final_exit"] = fe
            r_["travel_total"] = rnd(r_["travel_hall"] + fd, 2)
            r_.pop("options", None)
        self.egress_results = results
        for e in self.exits:
            n = load.get(e["id"], 0)
            e["load"] = n
            e["final_exit"] = finals[e["id"]][0]
            factor = w_st if e["level"] == "L02" else w_lvl
            e["required_width"] = rnd(n * factor, 3)
        total_occ = len(results) + E["staff_boh_occupants"]
        tot_w = sum(e["capacity_width"] for e in self.exits)
        req_w = sum(e["required_width"] for e in self.exits)
        th_hall, th_tot = E["travel_flag_within_hall_m"], E["travel_flag_total_m"]
        eg = {"occupants_assigned_in_hall": len(results), "seats": len(self.seats), "wheelchair": len(self.wc_positions),
              "companions": len(self.wc_positions), "choir": len(self.choir), "platform": npl, "boh_staff": E["staff_boh_occupants"],
              "building_total_occupants": total_occ, "hall_exits": len(self.exits), "total_hall_exit_clear_width": rnd(tot_w, 2),
              "total_required_width_placeholder": rnd(req_w, 2), "max_travel_hall": max(r["travel_hall"] for r in results),
              "max_travel_total": max(r["travel_total"] for r in results),
              "mean_travel_hall": rnd(sum(r["travel_hall"] for r in results) / len(results), 2),
              "max_travel_hall_to_nearest_exit": max(r["travel_nearest"] for r in results),
              "count_nearest_travel_over_flag": sum(1 for r in results if r["travel_nearest"] > th_hall),
              "count_travel_hall_over_flag": sum(1 for r in results if r["travel_hall"] > th_hall),
              "count_travel_total_over_flag": sum(1 for r in results if r["travel_total"] > th_tot)}
        self.metrics["egress"] = eg
        bad = [e["id"] for e in self.exits if e["capacity_width"] + 1e-9 < e["required_width"]]
        self.check("EGR-01", "Each hall exit capacity width (door clear width, or the stair behind it if narrower) >= placeholder demand "
                   "(queue-balanced assignment)", not bad,
                   {e["id"]: [e["load"], e["capacity_width"], e["required_width"]] for e in self.exits}, "capacity >= load x factor")
        biggest = max(self.exits, key=lambda e: e["capacity_width"])
        rem = tot_w - biggest["capacity_width"]
        self.check("EGR-06", "Remaining hall exit width with the largest exit blocked >= total placeholder demand",
                   rem >= len(results) * w_lvl, {"remaining": rnd(rem, 2), "demand": rnd(len(results) * w_lvl, 2)}, ">=")
        self.check("EGR-03N", "Max within-hall plan travel to the NEAREST hall exit", eg["max_travel_hall_to_nearest_exit"] <= th_hall,
                   {"max": eg["max_travel_hall_to_nearest_exit"], "over_flag": eg["count_nearest_travel_over_flag"]},
                   f"<= {th_hall} m (placeholder flag)", "WARN")
        self.check("EGR-03", "Max within-hall plan travel to the queue-balanced hall exit", eg["max_travel_hall"] <= th_hall,
                   {"max": eg["max_travel_hall"], "over_flag": eg["count_travel_hall_over_flag"]}, f"<= {th_hall} m (placeholder flag)", "WARN")
        self.check("EGR-04", "Max plan travel to a final (external) exit", eg["max_travel_total"] <= th_tot,
                   {"max": eg["max_travel_total"], "over_flag": eg["count_travel_total_over_flag"]}, f"<= {th_tot} m (placeholder flag)", "WARN")
        self.check("EGR-05", "Number of independent hall exits", len(self.exits) >= 8, len(self.exits), ">= 8")
        # final exits: every external door carries the hall exits that discharge to it (+ BOH staff at the BOH doors)
        fin_load = {}
        for e in self.exits:
            fin_load[finals[e["id"]][0]] = fin_load.get(finals[e["id"]][0], 0) + e["load"]
        for d in self.ext_doors:
            if d["id"].startswith("DR-EXT-BOH"):
                fin_load[d["id"]] = fin_load.get(d["id"], 0) + E["staff_boh_occupants"] // 2
        over = {d["id"]: [fin_load.get(d["id"], 0), d["clear"]] for d in self.ext_doors if d["clear"] + 1e-9 < fin_load.get(d["id"], 0) * w_lvl}
        self.final_exit_loads = fin_load
        self.check("EGR-08", "Each final (external) exit clear width >= the hall-exit load discharging to it (placeholder factor)", not over,
                   {"over": over, "loads": fin_load}, "clear >= load x level factor")
        bad_routes = {k: v for k, v in self.discharge.items() if not v["doors_fire_exit"]}
        self.check("EGR-09", "Every hall exit discharges to a final exit through fire-exit doors only (explicit route, no rooms)",
                   not bad_routes, self.discharge, "all doors on every route are FireExit")
        self.check("EGR-07", "Occupant tally reconciles (seats + wheelchair + companions + choir + platform + BOH)",
                   total_occ == len(self.seats) + 2 * len(self.wc_positions) + len(self.choir) + npl + E["staff_boh_occupants"],
                   total_occ, "sum of parts")

    def discharge_route(self, eid):
        """Explicit route from a hall exit to the final exits it may use (doors passed through, then candidate final doors)."""
        amb = lambda s: [d["id"] for d in self.ext_doors if d["id"].startswith(f"DR-EXT-AMB-{s}")]  # noqa: E731
        main = [d["id"] for d in self.ext_doors if d["id"].startswith("DR-EXT-S")]
        if eid.startswith("DR-HALL-S"):
            return {"via": [], "finals": main}
        if eid.startswith("DR-HALL-ARC-"):
            s_ = eid[-1]
            return {"via": [f"DR-CORNER-AMB-{s_}"], "finals": amb(s_)}
        if eid.startswith(("DR-HALL-W-", "DR-HALL-E-")):
            return {"via": [], "finals": amb(eid[8])}
        if eid.startswith("DR-STAGE-"):
            return {"via": [], "finals": [f"DR-EXT-BOH-{eid[-1]}"]}
        raise KeyError(eid)

    # ------------------------------------------------------------------ sightlines
    def sightline_checks(self):
        P = self.P
        S, SL, ST, AV = P["seating"], P["sightlines"], P["stage"], P["av"]
        Hf = ST["platform_height"] + SL["focal_height_above_platform"]
        eye = S["eye_height_seated"]
        d = self.eye_d
        e = [self.row_floor[i] + eye - Hf for i in range(self.nrows)]
        c1 = [e[i] * d[i - 1] / d[i] - e[i - 1] for i in range(1, self.nrows)]
        c2 = [e[i] * d[i - 2] / d[i] - e[i - 2] for i in range(2, self.nrows)]
        self.metrics["c_min_n1"] = rnd(min(c1), 4)
        self.metrics["c_min_n2"] = rnd(min(c2), 4)
        self.check("SGT-01", "Min C-value over the row in front (all rows, chair positions)", min(c1) >= SL["c_value_target"] - 1e-4,
                   rnd(min(c1), 4), f">= {SL['c_value_target']}")
        self.check("SGT-02", "Min C-value over 2 rows in front (staggered seating)", min(c2) >= SL["c_value_staggered_target_n2"] - 1e-4,
                   rnd(min(c2), 4), f">= {SL['c_value_staggered_target_n2']}")
        # wheelchair band: viewer at the band radius over the last front row
        rb = self.cross_r[1] - P["accessibility"]["wheelchair_space_depth"] / 2
        dw = rb + S["eye_offset_from_chair_centre"] - self.Rd
        ew = self.cross_level + S["eye_height_wheelchair"] - Hf
        cw = ew * d[S["front_rows"] - 1] / dw - e[S["front_rows"] - 1]
        self.check("SGT-WHEELCHAIR_BAND", "C-value for the cross-aisle wheelchair band over the last front row", cw >= SL["c_value_target"] - 1e-4,
                   rnd(cw, 4), f">= {SL['c_value_target']}")
        # horizontal: pulpit within 45 deg of the chair's facing, or a screen within 45 deg of its normal and 8 x its height
        px, py = self.pulpit
        over45 = over60 = no_view = rely = 0
        bearing_max = head_max = 0.0
        dists = []
        for s in self.seats:
            fx, fy = -math.sin(math.radians(s["rot_z"])), math.cos(math.radians(s["rot_z"]))
            vx, vy = px - s["x"], py - s["y"]
            dist = math.hypot(vx, vy)
            dists.append(dist)
            ang = math.degrees(math.acos(max(-1.0, min(1.0, (fx * vx + fy * vy) / dist))))
            head_max = max(head_max, ang)
            bearing = math.degrees(math.atan2(abs(s["x"] - px), py - s["y"]))
            bearing_max = max(bearing_max, bearing)
            if ang > 45:
                over45 += 1
            if ang > 60:
                over60 += 1
            ok_pulpit = ang <= AV["max_viewing_angle_deg"] and dist <= AV["max_unaided_pulpit_distance_m"]
            ok_screen = False
            for sc in self.screens:
                wx, wy = s["x"] - sc["c"][0], s["y"] - sc["c"][1]
                dd = math.hypot(wx, wy)
                a_n = math.degrees(math.acos(max(-1.0, min(1.0, (wx * sc["n"][0] + wy * sc["n"][1]) / dd))))
                a_f = math.degrees(math.acos(max(-1.0, min(1.0, (-wx * fx - wy * fy) / dd))))
                if a_n <= AV["max_viewing_angle_deg"] and a_f <= AV["max_viewing_angle_deg"] and dd <= AV["max_distance_to_height_ratio"] * sc["h"]:
                    ok_screen = True
            if not ok_pulpit:
                rely += 1
            if not (ok_pulpit or ok_screen):
                no_view += 1
        dists.sort()
        self.metrics["offaxis_pulpit"] = {"over_45": over45, "over_60": over60, "max_head_turn_deg": rnd(head_max, 2),
                                          "max_bearing_from_pulpit_deg": rnd(bearing_max, 2), "relying_on_screens": rely,
                                          "without_usable_view": no_view}
        self.metrics["pulpit_distance"] = {"max": rnd(dists[-1], 2), "mean": rnd(sum(dists) / len(dists), 2),
                                           "median": rnd(dists[len(dists) // 2], 2), "p90": rnd(dists[int(0.9 * len(dists))], 2)}
        self.check("SGT-H1", "Every seat has a usable view: pulpit within 45 deg and 30 m, or a screen within 45 deg (of both its normal "
                   "and the chair's facing) and 8x its height", no_view == 0, {"without": no_view, "relying_on_screens": rely}, "0 without")
        self.check("SGT-H2", "Seats with the pulpit more than 60 deg from the chair's facing direction", over60 == 0, over60, "0")

    # ------------------------------------------------------------------ clash / geometry checks
    def clash_checks(self):
        P = self.P
        S = P["seating"]
        self.check("SEAT-01", "Congregation seat count equals target", len(self.seats) == S["target_congregation_seats"],
                   len(self.seats), f"== {S['target_congregation_seats']}")
        # chair-chair overlaps (congregation + companions + choir) by OBB SAT within a spatial hash
        items = [(s["seat_id"], chair_corners(s["x"], s["y"], s["rot_z"])) for s in self.seats]
        items += [(c["name"], chair_corners(c["x"], c["y"], c["rot"])) for c in self.choir]
        items += [(w["name"], w["corners"]) for w in self.wc_positions]
        grid = {}
        for i, (n, c) in enumerate(items):
            cx, cy = sum(p[0] for p in c) / len(c), sum(p[1] for p in c) / len(c)
            grid.setdefault((int(cx // 2), int(cy // 2)), []).append(i)
        clashes = []
        for (gx, gy), idx in grid.items():
            near = [j for dx in (-1, 0, 1) for dy in (-1, 0, 1) for j in grid.get((gx + dx, gy + dy), [])]
            for i in idx:
                for j in near:
                    if j <= i:
                        continue
                    if obb_overlap(items[i][1], items[j][1], 0.005):
                        clashes.append((items[i][0], items[j][0]))
        self.check("CLS-01", "Chair / wheelchair-space footprints do not overlap (oriented boxes, 5 mm tolerance)", not clashes,
                   {"overlaps": len(clashes), "first": clashes[:6]}, "0")
        # chairs vs columns and inside the hall's clear interior
        bad = []
        for n, c in items:
            for cn, (x, y, sz) in self.columns.items():
                if obb_overlap(c, rect(x - sz / 2, y - sz / 2, x + sz / 2, y + sz / 2), 0.0):
                    bad.append((n, cn))
            if min(p[0] for p in c) < COL_FACE - 1e-6 or max(p[0] for p in c) > self.W - COL_FACE + 1e-6:
                bad.append((n, "side wall"))
        self.check("CLS-02", "Chairs clear of columns and inside the hall's clear interior", not bad, {"n": len(bad), "first": bad[:6]}, "0")
        # interior aisle clear width between chair edges of neighbouring blocks (per row)
        aisle_min = 99.0
        byrow = {}
        for s in self.seats:
            byrow.setdefault(s["row"], []).append(s)
        for row, ss in byrow.items():
            ss.sort(key=lambda s: s["th"])
            for a, b in zip(ss, ss[1:]):
                if a["block"] != b["block"]:
                    gap = (b["th"] - a["th"]) * a["r"] - 2 * CHAIR_HALF_W
                    aisle_min = min(aisle_min, gap)
        self.metrics["aisle_min_clear"] = rnd(aisle_min, 3)
        self.check("CIR-03", "Min interior aisle clear width between chair edges (row arc)", aisle_min >= S["aisle_width"] - 0.02,
                   rnd(aisle_min, 3), f">= {S['aisle_width']} (- 20 mm arc tolerance)")
        maxblock = max(sum(1 for s in ss if s["block"] == b) for ss in byrow.values() for b in {s["block"] for s in ss})
        self.metrics["max_seats_to_aisle"] = math.ceil(maxblock / 2)
        self.check("CIR-04", "Max seats from any seat to an aisle", math.ceil(maxblock / 2) <= S["max_seats_per_block_row"] // 2,
                   math.ceil(maxblock / 2), f"<= {S['max_seats_per_block_row'] // 2}")
        # platform front clear zone
        dmin = min(min(poly_dist(p, self.platform_poly) for p in chair_corners(s["x"], s["y"], s["rot_z"])) for s in self.seats)
        self.check("CIR-01", "Front clear zone between the platform and the nearest chair", dmin >= S["front_clear_zone"] - 1e-3,
                   rnd(dmin, 3), f">= {S['front_clear_zone']}")
        # risers / gradients / stairs / ramps
        SL = P["sightlines"]
        self.check("GEO-03", "Single step from the cross-aisle passage up to the raised wheelchair band (band sightline)",
                   self.cross_step == 0 or SL["min_aisle_riser"] - 1e-9 <= self.cross_step <= SL["max_aisle_riser"],
                   rnd(self.cross_step, 3), f"0 or {SL['min_aisle_riser']} - {SL['max_aisle_riser']}")
        self.check("CIR-07", "Rear-passage side doors open onto the rear passage where it meets the side wall (clear of the posts)",
                   self.rear_door_in_band, rnd(self.rear_passage_side_y, 2), "door within the passage band")
        rear_r = [self.rows[i]["rise"] for i in range(S["front_rows"] + 1, self.nrows)]
        self.check("GEO-01", "Rear aisle risers uniform and within limits", max(rear_r) <= SL["max_aisle_riser"] and min(rear_r) >= SL["min_aisle_riser"] - 1e-9,
                   {"min": min(rear_r), "max": max(rear_r)}, f"{SL['min_aisle_riser']} - {SL['max_aisle_riser']}")
        self.check("GEO-02", "Front sloped floor gradient", self.front_gradient_max <= 1 / SL["front_max_gradient_1_in"] + 1e-9,
                   f"1:{1 / self.front_gradient_max:.1f}", f"<= 1:{SL['front_max_gradient_1_in']:.0f}")
        bad_st = [s["name"] for s in self.stairs if s["riser"] > P["foyer"]["stair_max_riser"] + 1e-6]
        self.check("CIR-05", "Stair risers <= foyer stair max riser", not bad_st, [(s["name"], s["riser"]) for s in self.stairs],
                   f"<= {P['foyer']['stair_max_riser']}")
        bad_rp = [r["name"] for r in self.ramps if r["gradient_1_in"] < 12.0 - 1e-6 or r["run_per_flight"] > P["accessibility"]["ramp_max_run"] + 1e-6]
        self.check("ACC-04", "Ramps: gradient <= 1:12 and flights <= max run", not bad_rp, self.ramps, "1:12, <= 9 m per flight")
        A = P["accessibility"]
        nw = len(self.wc_positions)
        self.check("ACC-01", "Wheelchair spaces provided vs concept placeholder (1 %)", nw >= A["concept_target_fraction"] * S["target_congregation_seats"],
                   nw, f">= {A['concept_target_fraction'] * S['target_congregation_seats']:.0f}")
        zones = {w["group"][0] for w in self.wc_positions}
        self.check("ACC-02", "Wheelchair spaces dispersed (front at grade + cross-aisle band, both sides)", len({w["group"] for w in self.wc_positions}) >= 4,
                   sorted({w["group"] for w in self.wc_positions}), ">= 4 groups")
        band = [r for r in self.ramps if r["name"].startswith(("ARC-RAMP-BAND", "ARC-RAMP-CROSS"))]
        self.check("ACC-03", "Step-free route to every wheelchair space: ambulatory -> front-corner door (grade) -> front places; "
                   "front corner -> cross-end ramp (1:12) -> cross-aisle passage -> band end ramp (1:12) -> band; same route out",
                   len(band) == 4 and all(r["gradient_1_in"] >= 12 - 1e-6 for r in band),
                   {"ramps": [r["name"] for r in band]}, "4 ramps, all <= 1:12")
        wc_ex = {r["exit"] for r in self.egress_results if r["kind"] in ("wc", "companion")}
        lv = {e["id"]: e["level"] for e in self.exits}
        self.check("ACC-08", "Wheelchair users (and companions) are assigned only to step-free (grade) hall exits", all(lv[e] == "L00" for e in wc_ex),
                   sorted(wc_ex), "all L00")
        mx = max(r["flights"] for r in self.stairs if "flights" in r)
        per = max(math.ceil(r["risers"] / r["flights"]) for r in self.stairs if "flights" in r)
        self.check("CIR-06", "Egress stair flights <= max risers per flight (landings between flights)", per <= self.P["foyer"]["max_flight_risers"],
                   {"max_risers_per_flight": per, "max_flights": mx}, f"<= {self.P['foyer']['max_flight_risers']}")
        # trusses clear of the highest standing eye in the rear passage
        clr = self.bc(0.3) - (self.top_level + 2.1)
        self.check("STR-CLR", "Truss bottom chord above the rear passage headroom line (+2.1 m)", clr >= 0.5, rnd(clr, 2), ">= 0.5 m")
        # rooms with doors
        nodoor = [sp["id"] for sp in self.spaces if sp.get("door") is None and sp.get("use") in ("Accessible WC", "Toilets", "Lift")]
        self.check("SPC-03", "Every enclosed room (toilets, accessible WCs, BOH rooms, booth, lift) has a door", not nodoor, nodoor, "none missing")

    def summary_metrics(self):
        m = self.metrics
        m.update({"seats": len(self.seats), "wheelchair_spaces": len(self.wc_positions), "cross_aisle_level": self.cross_level,
                  "top_level": self.top_level, "rear_riser": self.rear_riser,
                  "front_slope_gradient_1_in": rnd(1 / self.front_gradient_max, 2), "hall_depth_grid_2_4": rnd(self.ysw, 2),
                  "hall_width": self.W, "platform_area": rnd(self.platform_area, 1), "platform_height": self.P["stage"]["platform_height"],
                  "truss_span": rnd(self.ysw, 2), "roof_area_main_m2": rnd(self.roof_area_main, 1),
                  "hall_ridge_top": rnd(self.tc(self.ysw) + 0.5, 2), "downpipes": self.downpipes,
                  "footprint_m": [rnd(self.facade_x[1] - self.facade_x[0], 2),
                                  rnd(self.gy["5"] + self.P["walls"]["offset_outside_grid"] + 0.15 - (self.gy["1"] - self.P["walls"]["offset_outside_grid"] - 0.15), 2)],
                  "space_area_total_m2": rnd(self.space_area_total, 1), "structural_member_ends_checked": self.member_count,
                  "levels": self.levels()})
        S, SL, ST = self.P["seating"], self.P["sightlines"], self.P["stage"]
        m["sightline_model"] = {"type": "radial", "F": [rnd(self.F[0], 4), rnd(self.F[1], 4)], "thrust_radius": self.Rd,
                                "eye_offset": S["eye_offset_from_chair_centre"], "eye_height": S["eye_height_seated"],
                                "focal_height": ST["platform_height"] + SL["focal_height_above_platform"],
                                "c_target": SL["c_value_target"], "c2_target": SL["c_value_staggered_target_n2"]}
        rs = self.seats_by_extreme = min(self.seats, key=lambda s: s["x"])
        m["render_views"] = {"design_id": P_id(self.P), "platform_eye": [self.pulpit[0], self.pulpit[1] + 1.0, ST["platform_height"] + 1.7],
                             "platform_look": [self.xc, 8.0, 1.5], "rear_eye": [self.xc + 2.0, COL_FACE + 0.8, self.top_level + 1.6],
                             "rear_look": [self.xc, self.ysw - 3.0, 2.0], "side_eye": [rs["x"], rs["y"], rs["z_floor"] + 1.2],
                             "side_look": [self.pulpit[0], self.pulpit[1], ST["platform_height"] + 1.5],
                             "roof_prefixes": ["ENV-ROOF", "STR-PURLIN", "STR-BRACE-ROOF", "ENV-CLAD", "SRV-GUTTER", "ENV-CANOPY"],
                             "cutaway_prefixes": ["ENV-WALL-HALL-W", "ENV-WALL-AMB-W", "ENV-WALL-EXT-S", "ARC-WALL-ARC-W"]}
        self.footprint = m["footprint_m"]
        self.render_target = (self.xc, self.ysw / 2, 4.0)


def P_id(P):
    return P["project"]["design_id"]


def compute(P=None):
    return LayoutB(P or load_params(DEFAULT_CONFIG)).compute()
