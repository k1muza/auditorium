"""Parametric layout engine for the 3,000-seat church auditorium coordination concept.

Pure Python (no bpy / numpy) so it runs identically under Blender's bundled
Python and under the project venv. All dimensions are metres. Every value is a
concept assumption driven by config/auditorium_params.json - nothing here is a
verified code, survey or engineering value.

compute(params) returns a dict with grid, levels, rows, seats, elements,
exits, egress analysis and checks. Elements carry their own mesh data so the
Blender builder and every checker see the same geometry.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "config" / "auditorium_params.json"
SCHEMA_VERSION = "layout-1.0"


def load_params(path=None):
    return json.loads(Path(path or DEFAULT_CONFIG).read_text(encoding="utf-8"))


def rnd(v, n=4):
    return round(float(v) + 0.0, n)


def ceil_to(v, step):
    return math.ceil(round(v / step, 6)) * step


# --------------------------------------------------------------------------- geometry primitives
BOX_FACES = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _norm(a):
    m = math.sqrt(a[0] ** 2 + a[1] ** 2 + a[2] ** 2)
    return (a[0] / m, a[1] / m, a[2] / m)


def part_mesh(part):
    """Return (verts, faces) in world coordinates for one primitive part."""
    kind = part[0]
    if kind == "box":
        x0, y0, z0, x1, y1, z1 = part[1]
        v = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
             (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
        return v, list(BOX_FACES)
    if kind == "prism8":  # bottom 4 + top 4 corners, same ordering as box
        return [tuple(p) for p in part[1]], list(BOX_FACES)
    if kind == "strut":
        p0, p1, w, h = part[1]
        u = _norm(_sub(p1, p0))
        ref = (0.0, 0.0, 1.0) if abs(u[2]) < 0.95 else (0.0, 1.0, 0.0)
        s = _norm(_cross(u, ref))
        t = _cross(u, s)
        if abs(u[2]) >= 0.95:
            s, t = t, _cross(u, t)
            s = _norm(s)
            t = _norm(_cross(u, s))
        verts = []
        for p in (p0, p1):
            for a, b in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
                verts.append(tuple(p[i] + s[i] * a * w / 2 + t[i] * b * h / 2 for i in range(3)))
        return verts, list(BOX_FACES)
    if kind == "extrude_xz":  # convex polygon in XZ extruded along Y
        poly, y0, y1 = part[1]
        n = len(poly)
        v = [(x, y0, z) for x, z in poly] + [(x, y1, z) for x, z in poly]
        faces = [tuple(range(n)), tuple(range(2 * n - 1, n - 1, -1))]
        for i in range(n):
            j = (i + 1) % n
            faces.append((i, n + i, n + j, j))
        return v, faces
    raise ValueError(f"unknown part kind {kind}")


def part_aabb(part):
    v, _ = part_mesh(part)
    xs, ys, zs = zip(*v)
    return (min(xs), min(ys), min(zs), max(xs), max(ys), max(zs))


class Element:
    """One model object. Parts are world-coordinate primitives; origin is the placement point."""

    def __init__(self, name, collection, ifc_class, predefined=None, storey="L00", parts=(),
                 origin=None, rot_z=0.0, mesh_key=None, props=None, assembly=None, object_type=None,
                 kind="solid", strut=None, host=None, opening=None):
        self.name = name
        self.collection = collection
        self.ifc_class = ifc_class
        self.predefined = predefined
        self.storey = storey
        self.parts = list(parts)
        self.rot_z = rot_z
        self.mesh_key = mesh_key  # shared (instanced) mesh, geometry defined in INSTANCE_MESHES
        self.props = dict(props or {})
        self.assembly = assembly
        self.object_type = object_type
        self.kind = kind
        self.strut = strut  # (p0, p1, radius) for line-member clash checks
        self.host = host  # host wall name for doors/windows
        self.opening = opening  # opening box for IfcOpeningElement
        if origin is None:
            bb = self.aabb()
            origin = ((bb[0] + bb[3]) / 2, (bb[1] + bb[4]) / 2, bb[2])
        self.origin = tuple(rnd(c, 5) for c in origin)

    def aabb(self):
        if self.mesh_key:
            raise ValueError("instanced element AABB comes from instance mesh")
        boxes = [part_aabb(p) for p in self.parts]
        return (min(b[0] for b in boxes), min(b[1] for b in boxes), min(b[2] for b in boxes),
                max(b[3] for b in boxes), max(b[4] for b in boxes), max(b[5] for b in boxes))

    def local_mesh(self):
        """Merged mesh of all parts relative to origin (verts rounded for determinism)."""
        verts, faces = [], []
        ox, oy, oz = self.origin
        for p in self.parts:
            v, f = part_mesh(p)
            base = len(verts)
            verts.extend((rnd(a - ox, 5), rnd(b - oy, 5), rnd(c - oz, 5)) for a, b, c in v)
            faces.extend(tuple(i + base for i in face) for face in f)
        return verts, faces


def chair_mesh():
    """Chair facing +Y, origin at floor centre of footprint. AABB x+-0.24, y+-0.30, z 0..0.85."""
    parts = [("box", (-0.24, -0.30, 0.0, -0.20, 0.30, 0.62)),   # side standard
             ("box", (0.20, -0.30, 0.0, 0.24, 0.30, 0.62)),     # side standard
             ("box", (-0.20, -0.22, 0.40, 0.20, 0.28, 0.46)),   # seat pan
             ("box", (-0.24, -0.30, 0.40, 0.24, -0.22, 0.85))]  # back
    verts, faces = [], []
    for p in parts:
        v, f = part_mesh(p)
        base = len(verts)
        verts.extend(v)
        faces.extend(tuple(i + base for i in face) for face in f)
    return verts, faces


INSTANCE_MESHES = {"CHAIR": chair_mesh()}
CHAIR_HALF_W, CHAIR_HALF_D, CHAIR_H = 0.24, 0.30, 0.85


def instance_aabb(el):
    """World AABB of an instanced chair (rotation 0 or 180 only)."""
    x, y, z = el.origin
    return (x - CHAIR_HALF_W, y - CHAIR_HALF_D, z, x + CHAIR_HALF_W, y + CHAIR_HALF_D, z + CHAIR_H)


# --------------------------------------------------------------------------- layout
class Layout:
    def __init__(self, P):
        self.P = P
        self.gx = P["grid"]["x_lines"]
        self.gy = P["grid"]["y_lines"]
        self.elements: list[Element] = []
        self.names = set()
        self.checks = []
        self.metrics = {}
        self.exits = []
        self.rows = []
        self.seats = []

    # ---------------------------------------------------------------- helpers
    def add(self, el):
        if el.name in self.names:
            raise ValueError(f"duplicate element name {el.name}")
        self.names.add(el.name)
        self.elements.append(el)
        return el

    def check(self, cid, desc, passed, value, criterion, status_if_fail="FAIL"):
        self.checks.append({"id": cid, "description": desc, "value": value, "criterion": criterion,
                            "result": "PASS" if passed else status_if_fail})

    def wall(self, name, collection, axis, c, t, a0, a1, z0, z1, openings=(), predefined="SOLIDWALL",
             storey="L00", props=None, cavity=()):
        """Wall along axis 'x' (constant y=c) or 'y' (constant x=c) with rectangular openings.

        openings: list of dicts {name, a0, a1, z0, z1, kind('door'|'window'), width}
        cavity: list of (a0, a1, total_depth, gap) ranges built as two leaves either side of a centred cavity
        (braced bays: the X-bracing runs in the cavity, clear of the masonry).
        Returns wall element; fills (doors/windows) are added separately by caller via returned list.
        """
        cuts = sorted({a0, a1, *[o["a0"] for o in openings], *[o["a1"] for o in openings],
                       *[cv[0] for cv in cavity], *[cv[1] for cv in cavity]})
        parts = []
        for i in range(len(cuts) - 1):
            s0, s1 = cuts[i], cuts[i + 1]
            if s1 - s0 < 1e-6:
                continue
            mid = (s0 + s1) / 2
            holes = sorted((o["z0"], o["z1"]) for o in openings if o["a0"] < mid < o["a1"])
            zc = z0
            spans = []
            for h0, h1 in holes:
                if h0 > zc + 1e-6:
                    spans.append((zc, h0))
                zc = max(zc, h1)
            if z1 > zc + 1e-6:
                spans.append((zc, z1))
            cv = next((cv for cv in cavity if cv[0] <= mid <= cv[1]), None)
            leaves = [(c - t / 2, c + t / 2)] if cv is None else \
                [(c - cv[2] / 2, c - cv[3] / 2), (c + cv[3] / 2, c + cv[2] / 2)]
            for q0, q1 in spans:
                for l0, l1 in leaves:
                    if axis == "x":
                        parts.append(("box", (s0, l0, q0, s1, l1, q1)))
                    else:
                        parts.append(("box", (l0, s0, q0, l1, s1, q1)))
        if axis == "x":
            origin = ((a0 + a1) / 2, c, z0)
        else:
            origin = (c, (a0 + a1) / 2, z0)
        w = self.add(Element(name, collection, "IfcWall", predefined, storey, parts, origin=origin,
                             props={"Length": rnd(a1 - a0, 3), "Height": rnd(z1 - z0, 3), "Thickness": t,
                                    "IsExternal": collection.startswith("10_"), **(props or {})}))
        for o in openings:
            if axis == "x":
                ob = (o["a0"], c - t / 2, o["z0"], o["a1"], c + t / 2, o["z1"])
                leaf = ("box", (o["a0"], c - 0.025, o["z0"], o["a1"], c + 0.025, o["z1"]))
            else:
                ob = (c - t / 2, o["a0"], o["z0"], c + t / 2, o["a1"], o["z1"])
                leaf = ("box", (c - 0.025, o["a0"], o["z0"], c + 0.025, o["a1"], o["z1"]))
            cls = "IfcDoor" if o.get("kind", "door") == "door" else "IfcWindow"
            pre = "DOOR" if cls == "IfcDoor" else "WINDOW"
            fill_props = {"OverallWidth": rnd(o["a1"] - o["a0"], 3), "OverallHeight": rnd(o["z1"] - o["z0"], 3),
                          "IsExternal": collection.startswith("10_"), "Role": o.get("role", "")}
            fill_props.update(o.get("props", {}))
            self.add(Element(o["name"], collection, cls, pre, storey, [leaf], host=name, opening=ob,
                             origin=((ob[0] + ob[3]) / 2, (ob[1] + ob[4]) / 2, ob[2]), props=fill_props))
        return w

    def opening(self, name, a_center, width, z0, height=None, kind="door", role="", props=None):
        h = height if height is not None else self.P["walls"]["door_height"]
        return {"name": name, "a0": rnd(a_center - width / 2), "a1": rnd(a_center + width / 2), "z0": rnd(z0),
                "z1": rnd(z0 + h), "kind": kind, "role": role, "props": props or {}}

    # ---------------------------------------------------------------- seating geometry
    def build_rows(self):
        S, SL, ST = self.P["seating"], self.P["sightlines"], self.P["stage"]
        pitch = S["row_pitch"]
        y_focal = ST["front_edge_y"]
        z_focal = ST["platform_height"] + SL["focal_height_above_platform"]
        eye_h, eye_wc, eye_off = S["eye_height_seated"], S["eye_height_wheelchair"], S["eye_offset_from_tread_back"]
        C = SL["c_value_target"]
        nf, nr = S["front_rows"], S["rear_rows"]
        y_front = y_focal - ST["front_clear_zone"]
        rows = []
        for r in range(1, nf + 1):
            yf = y_front - (r - 1) * pitch
            rows.append({"row": r, "section": "front", "yf": yf, "yb": yf - pitch})
        yb_front_last = rows[-1]["yb"]
        passage = (yb_front_last - S["cross_aisle_passage"], yb_front_last)
        band = (passage[0] - S["wheelchair_band_depth"], passage[0])
        for k in range(nr):
            yf = band[0] - k * pitch
            rows.append({"row": nf + 1 + k, "section": "rear", "yf": yf, "yb": yf - pitch})
        self.cross_passage, self.band = passage, band
        y_level_end = rows[S["front_level_rows"] - 1]["yb"]  # rows 1..n level at 0.000
        self.y_slope_low, self.y_slope_high = y_level_end, yb_front_last  # slope rises toward -Y

        def eye(rw, floor):
            return floor + eye_h - z_focal, y_focal - (rw["yb"] + eye_off)

        def c_val(e_n, d_n, e_p, d_p):
            return e_n * d_p / d_n - e_p

        # front section: sightline recurrence gives each row's floor at its tread rear edge; the
        # floor between rows is a continuous slope (piecewise linear), so aisles are ramped, not stepped.
        C2 = SL["c_value_staggered_target_n2"]
        prev = prev2 = None
        floor_prev = 0.0
        for rw in rows[:nf]:
            if prev is None or rw["row"] <= S["front_level_rows"]:
                f = 0.0
                if prev is not None:
                    e, d = eye(rw, 0.0)
                    if c_val(e, d, *prev) < C - 1e-9:
                        raise RuntimeError("level front rows fail sightline target; reduce front_level_rows")
            else:
                d = y_focal - (rw["yb"] + eye_off)
                req = (prev[0] + C) * d / prev[1]
                if prev2:  # staggered seating: also clear the head two rows in front by C2
                    req = max(req, (prev2[0] + C2) * d / prev2[1])
                f = max(floor_prev, rnd(ceil_to(req + z_focal - eye_h, SL["elevation_rounding"])))
            rw["floor"] = rnd(f)
            floor_prev = f
            prev2, prev = prev, eye(rw, f)
        top = rows[nf - 1]["floor"]
        self.front_slope_top = top
        # wheelchair band / cross aisle level: wheelchair eye must clear last front row by C
        e19, d19 = eye(rows[nf - 1], rows[nf - 1]["floor"])
        d_band = y_focal - (band[0] + eye_off)
        need = (e19 + C) * d_band / d19  # eye above focal
        ec = max(top, need + z_focal - eye_wc)
        ec = rnd(ceil_to(ec, SL["cross_aisle_rounding"]))
        self.cross_level = ec
        e_band = ec + eye_wc - z_focal
        # rear section stepped rows: clear the wheelchair band eye and the last front row eye
        # rear section: bands of rows with ONE uniform riser per band (A-22). For each band the smallest
        # uniform rise (search step) is found that keeps C over the row in front and C2 over two rows in front.
        prev_list = [(e19, d19), (e_band, d_band)]
        prev2_list = [eye(rows[nf - 2], rows[nf - 2]["floor"])]
        floor_prev = ec
        bands = SL["rear_uniform_bands"]
        if sum(bands) != len(rows) - nf:
            raise RuntimeError("rear_uniform_bands must sum to rear_rows")
        start = nf
        self.rear_bands = []
        for bi, k in enumerate(bands, start=1):
            brows = rows[start:start + k]
            r = 0.0
            while True:
                p1, p2, ok = prev_list, prev2_list, True
                for i, rw in enumerate(brows):
                    e, d = eye(rw, floor_prev + (i + 1) * r)
                    if any(c_val(e, d, *q) < C - 1e-9 for q in p1) or any(c_val(e, d, *q) < C2 - 1e-9 for q in p2):
                        ok = False
                        break
                    p2, p1 = p1, [(e, d)]
                if ok:
                    break
                r = rnd(r + SL["rise_search_step"])
                if r > 1.0:
                    raise RuntimeError("rear band rise search did not converge")
            for i, rw in enumerate(brows):
                rw["floor"] = rnd(floor_prev + (i + 1) * r)
                rw["band"] = bi
            prev2_list = [eye(brows[-2], brows[-2]["floor"])] if k > 1 else prev_list
            prev_list = [eye(brows[-1], brows[-1]["floor"])]
            self.rear_bands.append({"band": bi, "rows": [brows[0]["row"], brows[-1]["row"]], "uniform_riser": r})
            floor_prev = brows[-1]["floor"]
            start += k
        # rear wheelchair platform (cross aisle at top) acts as row 41; riser = last band riser if sufficient
        y_rear_front = rows[-1]["yb"]
        d_rear_wc = y_focal - (y_rear_front - self.P["accessibility"]["wheelchair_space_depth"] + eye_off)
        pe, pd = prev_list[0]
        qe, qd = prev2_list[0]
        req = max((pe + C) * d_rear_wc / pd, (qe + C2) * d_rear_wc / qd)
        self.top_level = rnd(max(floor_prev + self.rear_bands[-1]["uniform_riser"],
                                 ceil_to(req + z_focal - eye_wc, SL["elevation_rounding"])))
        # sightline metrics recomputed over the actual floors (C over n-1 and n-2)
        seq = []
        for rw in rows[:nf]:
            seq.append(("row", rw["row"], *eye(rw, rw["floor"])))
        seq.append(("wheelchair_band", 0, e_band, d_band))
        for rw in rows[nf:]:
            seq.append(("row", rw["row"], *eye(rw, rw["floor"])))
        rear_wc_e = self.top_level + eye_wc - z_focal
        seq.append(("wheelchair_rear", 0, rear_wc_e, d_rear_wc))
        by_row = {}
        for i, (kind, r, e, d) in enumerate(seq):
            c1 = c_val(e, d, *seq[i - 1][2:]) if i > 0 else None
            c2 = c_val(e, d, *seq[i - 2][2:]) if i > 1 else None
            by_row[(kind, r)] = (c1, c2, d)
        prev_floor = 0.0
        for rw in rows:
            c1, c2, d = by_row[("row", rw["row"])]
            rw["c_n1"] = None if c1 is None else rnd(c1)
            rw["c_n2"] = None if c2 is None else rnd(c2)
            rw["eye_distance"] = rnd(d, 3)
            rw["rise"] = rnd(rw["floor"] - (ec if rw["row"] == nf + 1 else prev_floor))
            prev_floor = rw["floor"]
        self.sight_extra = {k[0]: {"c_n1": rnd(v[0]), "c_n2": rnd(v[1]) if v[1] is not None else None,
                                   "eye_distance": rnd(v[2], 3)}
                            for k, v in by_row.items() if k[0] != "row"}
        self.rows = rows
        self.z_focal = z_focal

    def block_ranges(self, offset=0.0):
        S = self.P["seating"]
        x_in0 = self.gx["B"] + self.P["structure"]["hall_column"] / 2
        x_in1 = self.gx["G"] - self.P["structure"]["hall_column"] / 2
        zone = sum(S["blocks"]) * S["seat_width"] + (len(S["blocks"]) - 1) * S["aisle_width"]
        x = (x_in0 + x_in1) / 2 - zone / 2 + offset
        blocks, aisles = [], []
        for i, n in enumerate(S["blocks"]):
            blocks.append((rnd(x), rnd(x + n * S["seat_width"])))
            x += n * S["seat_width"]
            if i < len(S["blocks"]) - 1:
                aisles.append((rnd(x), rnd(x + S["aisle_width"])))
                x += S["aisle_width"]
        return blocks, aisles, (x_in0, x_in1)

    def row_offset(self, r):
        return self.P["seating"]["stagger_offset"] / 2 * (1 if r % 2 else -1)

    def build_seats(self):
        S = self.P["seating"]
        omit = {}
        for o in S["omit"]:
            for r in o["rows"]:
                omit.setdefault(r, set()).update(o["blocks"])
        seats = []
        for rw in self.rows:
            r = rw["row"]
            off = self.row_offset(r)
            blocks, aisles, _ = self.block_ranges(off)
            rw["offset"] = off
            rw["blocks"] = blocks
            rw["aisles"] = aisles
            n_row = 0
            y_c = rw["yb"] + S["chair_back_offset"] + S["chair_depth"] / 2
            z = rw["floor"]
            for bi, (bx0, bx1) in enumerate(blocks, start=1):
                if bi in omit.get(r, ()):
                    continue
                for si in range(S["blocks"][bi - 1]):
                    x_c = bx0 + S["seat_width"] * (si + 0.5)
                    sid = f"SEAT-C-R{r:02d}-B{bi}-S{si + 1:02d}"
                    seats.append({"seat_id": sid, "row": r, "section": rw["section"], "block": bi,
                                  "seat_in_block": si + 1, "x": rnd(x_c), "y": rnd(y_c), "z_floor": rnd(z),
                                  "eye_z": rnd(z + S["eye_height_seated"])})
                    n_row += 1
            rw["seats"] = n_row
        self.seats = seats
        total = len(seats)
        self.check("SEAT-01", "Congregation seat count equals target", total == S["target_congregation_seats"],
                   total, f"== {S['target_congregation_seats']}")
        if total != S["target_congregation_seats"]:
            raise RuntimeError(f"Seat count {total} != target {S['target_congregation_seats']}")
        for s in seats:
            self.add(Element(s["seat_id"], "40_SEAT_Congregation", "IfcFurniture", "CHAIR",
                             "L00" if s["section"] == "front" else "L01", origin=(s["x"], s["y"], s["z_floor"]),
                             mesh_key="CHAIR", object_type="Congregation fixed seat",
                             props={"SeatType": "congregation", "FixedSeat": True, "Row": s["row"],
                                    "Block": s["block"], "SeatNumber": s["seat_in_block"],
                                    "CountsTowardTarget": True}))

    # ---------------------------------------------------------------- floors / rake
    def build_rake(self):
        S, SL = self.P["seating"], self.P["sightlines"]
        _, _, (x_in0, x_in1) = self.block_ranges()
        xw0 = self.gx["B"] + self.P["walls"]["hall_thickness"] / 2
        xw1 = self.gx["G"] - self.P["walls"]["hall_thickness"] / 2
        y_rear_wall = self.gy["3"] + self.P["walls"]["hall_thickness"] / 2
        y_stage_wall = self.gy["11"] - self.P["walls"]["hall_thickness"] / 2
        st = self.P["structure"]["slab_thickness"]
        # level front zone + wings + rows 1..n (0.000)
        self.add(Element("ARC-SLAB-HALL-FRONT", "20_ARC_Floors", "IfcSlab", "FLOOR", "L00",
                         [("box", (xw0, self.y_slope_low, -st, xw1, y_stage_wall, 0.0))],
                         props={"Description": "Hall front zone, wings and level front rows"}))
        # front section: continuous sloped floor through each row's rear-edge elevation (rises toward -Y)
        top = self.front_slope_top
        nf = S["front_rows"]
        parts, steepest = [], None
        fr = self.rows[:nf]
        for a, b in zip(fr[S["front_level_rows"] - 1:-1], fr[S["front_level_rows"]:]):
            ya, za, yb_, zb = b["yb"], b["floor"], a["yb"], a["floor"]  # ya < yb_, za >= zb
            parts.append(("prism8", [(xw0, ya, -st), (xw1, ya, -st), (xw1, yb_, -st), (xw0, yb_, -st),
                                     (xw0, ya, za), (xw1, ya, za), (xw1, yb_, zb), (xw0, yb_, zb)]))
            if za > zb:
                g = (yb_ - ya) / (za - zb)
                steepest = g if steepest is None else min(steepest, g)
        self.add(Element("ARC-SLAB-RAKE-FRONT", "20_ARC_Floors", "IfcSlab", "FLOOR", "L00", parts,
                         origin=(xw0, fr[-1]["yb"], -st),
                         props={"Description": "Front seating section sloped floor (piecewise, follows sightline profile)",
                                "SteepestGradient_1_in": rnd(steepest, 2) if steepest else None}))
        self.metrics["front_slope_gradient_1_in"] = rnd(steepest, 2) if steepest else None
        # cross aisle passage + wheelchair band (level)
        ec = self.cross_level
        self.add(Element("ARC-SLAB-CROSS-AISLE", "20_ARC_Floors", "IfcSlab", "FLOOR", "L01",
                         [("box", (xw0, self.band[0], -st, xw1, self.cross_passage[1], ec))],
                         props={"Description": "Mid cross aisle and wheelchair band (level)"}))
        # rear stepped treads: blocks as treads, aisles as step stacks
        nf = S["front_rows"]
        prev_floor = ec
        max_r = SL["max_aisle_riser"]
        aisle_riser_max, aisle_riser_min_going = 0.0, 9.0
        for rw in self.rows[nf:]:
            f = rw["floor"]
            rise = f - prev_floor
            blocks, aisles = rw["blocks"], rw["aisles"]
            spans = [("B", b) for b in blocks] + [("A", a) for a in aisles]
            spans += [("W", (xw0, blocks[0][0])), ("W", (blocks[-1][1], xw1))]
            n_steps = max(1, math.ceil(round(rise / max_r, 6))) if rise > 0 else 1
            going = S["row_pitch"] / n_steps
            for kind, (sx0, sx1) in sorted(spans, key=lambda s: s[1][0]):
                if kind == "B" or n_steps == 1:
                    tag = "TREAD" if kind == "B" else "AISLE"
                    self.add(Element(f"ARC-RAKE-R{rw['row']:02d}-{tag}-X{sx0:06.2f}", "20_ARC_Floors",
                                     "IfcSlab", "FLOOR", "L01",
                                     [("box", (sx0, rw["yb"], -st, sx1, rw["yf"], f))],
                                     props={"Description": f"Row {rw['row']} {'seating tread' if kind == 'B' else 'aisle tread'}"}))
                else:
                    parts = []
                    for k in range(1, n_steps + 1):
                        zt = prev_floor + rise * k / n_steps
                        ya = rw["yf"] - going * k
                        yb_ = rw["yf"] - going * (k - 1)
                        parts.append(("box", (sx0, ya, -st, sx1, yb_, zt)))
                    self.add(Element(f"ARC-RAKE-R{rw['row']:02d}-AISLE-X{sx0:06.2f}", "20_ARC_Floors",
                                     "IfcSlab", "FLOOR", "L01", parts,
                                     props={"Description": f"Row {rw['row']} aisle steps x{n_steps}"}))
            if rise > 0:
                aisle_riser_max = max(aisle_riser_max, rise / n_steps)
                aisle_riser_min_going = min(aisle_riser_min_going, going)
            rw["aisle_steps"] = n_steps
            rw["aisle_riser"] = rnd(rise / n_steps) if rise > 0 else 0.0
            prev_floor = f
        bad_bands = []
        for b in self.rear_bands:
            rises = [rw["rise"] for rw in self.rows if b["rows"][0] <= rw["row"] <= b["rows"][1]]
            b["max_riser_deviation"] = rnd(max(rises) - min(rises), 4)
            if b["max_riser_deviation"] > 0.001:
                bad_bands.append(b["band"])
        self.metrics["rear_bands"] = self.rear_bands
        self.check("GEO-05", "Aisle risers uniform within each rear band (one riser per row)", not bad_bands,
                   [{k: b[k] for k in ("band", "rows", "uniform_riser", "max_riser_deviation")} for b in self.rear_bands],
                   "deviation <= 1 mm within band (A-22)")
        # rear top platform (rear cross aisle + rear wheelchair positions)
        tl = self.top_level
        self.add(Element("ARC-SLAB-REAR-PLATFORM", "20_ARC_Floors", "IfcSlab", "FLOOR", "L02",
                         [("box", (xw0, y_rear_wall, -st, xw1, self.rows[-1]["yb"], tl))],
                         props={"Description": "Rear cross aisle / rear wheelchair platform"}))
        last_rise = tl - self.rows[-1]["floor"]
        self.metrics.update({
            "cross_aisle_level": ec, "front_slope_top": top, "top_level": tl,
            "cross_aisle_riser_from_front_slope": rnd(ec - top),
            "rear_platform_riser": rnd(last_rise),
            "aisle_riser_max": rnd(aisle_riser_max), "aisle_min_going": rnd(aisle_riser_min_going),
        })
        self.check("GEO-01", "Mid cross-aisle riser above front slope top is a single aisle step",
                   ec - top <= max_r + 1e-9, rnd(ec - top), f"<= {max_r} m (single riser; detail per OI-07)", "WARN")
        self.check("GEO-02", "Max rear aisle riser after subdivision", aisle_riser_max <= max_r + 1e-9,
                   rnd(aisle_riser_max), f"<= {max_r} m placeholder")
        self.check("GEO-03", "Rear platform riser above last row", last_rise <= max_r + 1e-9, rnd(last_rise),
                   f"<= {max_r} m placeholder", "WARN")
        grad = self.metrics["front_slope_gradient_1_in"]
        self.check("GEO-04", "Front section sloped floor gradient", grad is None or grad >= 10.0, grad,
                   ">= 1:10 placeholder for sloped seating floors", "WARN")

    # ---------------------------------------------------------------- accessibility
    def build_accessible_positions(self):
        A, S = self.P["accessibility"], self.P["seating"]
        ww, wd, cw = A["wheelchair_space_width"], A["wheelchair_space_depth"], A["companion_seat_width"]
        pair = ww + cw
        positions = []

        def place(prefix, x0, x1, y_front, z, n, storey, location):
            """n pairs centred in [x0,x1]; wheelchair space front edge at y_front (towards platform)."""
            width = n * pair + (n - 1) * 0.1
            if width > x1 - x0 + 1e-6:
                raise RuntimeError(f"{prefix}: {n} pairs do not fit in {x1 - x0:.2f} m")
            x = (x0 + x1) / 2 - width / 2
            for i in range(n):
                wx0, wx1 = x, x + ww
                idx = len([p for p in positions if p["group"] == prefix]) + 1
                name = f"ACC-WCS-{prefix}-{idx:02d}"
                self.add(Element(name, "40_SEAT_Accessible", "IfcSpatialZone", "USERDEFINED", storey,
                                 [("box", (wx0, y_front - wd, z, wx1, y_front, z + 0.02))],
                                 object_type="WheelchairSpace",
                                 props={"Location": location, "Width": ww, "Depth": wd,
                                        "Status": "Concept - count and dimensions unverified"}))
                cx = wx1 + cw / 2
                cy = y_front - wd + 0.30 + 0.05
                comp = f"SEAT-K-{prefix}-{idx:02d}"
                self.add(Element(comp, "40_SEAT_Companion", "IfcFurniture", "CHAIR", storey,
                                 origin=(rnd(cx), rnd(cy), z), mesh_key="CHAIR", object_type="Companion loose chair",
                                 props={"SeatType": "companion", "FixedSeat": False, "CountsTowardTarget": False}))
                positions.append({"group": prefix, "name": name, "x0": wx0, "x1": wx1, "y0": y_front - wd,
                                  "y1": y_front, "z": z, "companion": comp})
                x += pair + 0.1

        # front: in the omitted side-block area of rows 1-2 (level 0.000)
        blocks, _, _ = self.block_ranges(0.0)
        y_front = self.rows[0]["yf"]
        for side, (bx0, bx1) in (("FW", blocks[0]), ("FE", blocks[-1])):
            place(side, bx0, bx1, y_front, 0.0, A["front_pairs_per_side"], "L00", "Front, level with front zone")
        # mid band (level with cross aisle) in front of each block
        for bi, ((bx0, bx1), n) in enumerate(zip(blocks, A["band_pairs_per_block"]), start=1):
            if n:
                place(f"M{bi}", bx0, bx1, self.band[1], self.cross_level, n, "L01", "Mid cross-aisle band")
        # rear platform behind last row
        for bi, ((bx0, bx1), n) in enumerate(zip(blocks, A["rear_pairs_per_block"]), start=1):
            if n:
                place(f"R{bi}", bx0, bx1, self.rows[-1]["yb"], self.top_level, n, "L02", "Rear platform")
        self.wc_positions = positions
        target = math.ceil(A["concept_target_fraction"] * S["target_congregation_seats"])
        self.metrics["wheelchair_spaces"] = len(positions)
        self.metrics["wheelchair_spaces_L02"] = sum(1 for p in positions if p["group"].startswith("R"))
        self.check("ACC-01", "Wheelchair spaces provided vs concept placeholder (1%)", len(positions) >= target,
                   len(positions), f">= {target} (placeholder, unverified)")
        groups = {p["group"][0] for p in positions}
        self.check("ACC-02", "Wheelchair spaces dispersed across front / mid / rear", groups >= {"F", "M", "R"},
                   sorted(groups), "front, mid and rear locations")

    # ---------------------------------------------------------------- stage
    def build_stage(self):
        ST = self.P["stage"]
        h = ST["platform_height"]
        (x0, x1), (y0, y1) = ST["platform_x"], ST["platform_y"]
        self.add(Element("ARC-PLATFORM", "20_ARC_Floors", "IfcSlab", "FLOOR", "L00",
                         [("box", (x0, y0, 0.0, x1, y1, h))],
                         props={"Description": "Platform / pulpit stage (+0.90)"}))
        cx0, cx1 = ST["choir_x"]
        for i, (ya, yb_, zt) in enumerate(ST["choir_tiers"], start=1):
            self.add(Element(f"ARC-CHOIR-TIER-{i}", "20_ARC_Floors", "IfcSlab", "FLOOR", "L00",
                             [("box", (cx0, ya, 0.0, cx1, yb_, zt))], props={"Description": f"Choir riser tier {i}"}))
            n = int(round((cx1 - cx0) / self.P["seating"]["seat_width"]))
            for s in range(n):
                xc = cx0 + self.P["seating"]["seat_width"] * (s + 0.5)
                yc = yb_ - 0.05 - 0.30  # chair faces -Y (towards congregation), back at rear of tier
                self.add(Element(f"SEAT-H-T{i}-S{s + 1:02d}", "40_SEAT_Choir", "IfcFurniture", "CHAIR", "L00",
                                 origin=(rnd(xc), rnd(yc), zt), rot_z=180.0, mesh_key="CHAIR",
                                 object_type="Choir seat (excluded from congregation count)",
                                 props={"SeatType": "choir", "FixedSeat": False, "CountsTowardTarget": False}))
        px, py = ST["pulpit_xy"]
        self.add(Element("ARC-PULPIT", "20_ARC_Furniture", "IfcFurniture", "USERDEFINED", "L00",
                         [("box", (px - 0.6, py - 0.4, h, px + 0.6, py + 0.4, h + 1.1))], object_type="Pulpit"))
        # accessible platform ramp on east wing (along +Y), top landing abutting platform east edge
        g, w = ST["access_ramp_gradient"], ST["access_ramp_width"]
        run = h * g
        rx0, rx1 = x1, x1 + w
        ry0 = y0
        ry1 = ry0 + run
        top_landing = 1.2  # user turns onto the platform, which provides the turning space
        corners = [(rx0, ry0, 0.0), (rx1, ry0, 0.0), (rx1, ry1, 0.0), (rx0, ry1, 0.0),
                   (rx0, ry0, 0.0), (rx1, ry0, 0.0), (rx1, ry1, h), (rx0, ry1, h)]
        self.add(Element("ARC-RAMP-PLATFORM-E", "20_ARC_Circulation", "IfcRamp", "STRAIGHT_RUN_RAMP", "L00",
                         [("prism8", corners), ("box", (rx0, ry1, 0.0, rx1, ry1 + top_landing, h))],
                         props={"Gradient_1_in": g, "Rise": h, "Status": "Concept - handrails/landings not detailed"}))
        self.check("ACC-03", "Platform access ramp top landing within platform depth", ry1 + top_landing <= y1 + 1e-6,
                   rnd(ry1 + top_landing, 3), f"<= {y1}")
        # west side stair to platform (rises along +X)
        n = math.ceil(h / 0.18)
        r = h / n
        parts = []
        sy0, sy1 = y0 + 0.5, y0 + 2.9
        for k in range(1, n + 1):
            xa = x0 - (n - k + 1) * 0.28
            parts.append(("box", (xa, sy0, 0.0, xa + 0.28, sy1, k * r)))
        self.add(Element("ARC-STAIR-PLATFORM-W", "20_ARC_Circulation", "IfcStair", "STRAIGHT_RUN_STAIR", "L00", parts,
                         props={"Risers": n, "Riser": rnd(r, 3), "Going": 0.28, "Width": rnd(sy1 - sy0, 2)}))

    # ---------------------------------------------------------------- envelope, walls, doors
    def build_walls(self):
        P, W = self.P, self.P["walls"]
        gx, gy = self.gx, self.gy
        te, th, ti = W["external_thickness"], W["hall_thickness"], W["internal_thickness"]
        D = P["doors"]
        dh = W["door_height"]
        st = P["structure"]
        ext_w = D["external_width"]
        hall_top = st["hall_wall_top"]
        amb_top = P["ambulatory"]["roof_top"] - st["roof_build_up"]
        foy_top = P["foyer"]["roof_top"] - st["roof_build_up"]
        boh_top = P["back_of_house"]["roof_top"] - st["roof_build_up"]
        self.exits = []
        # ---- hall long walls (B west, G east)
        ca = self.cross_passage
        for side, xc in (("W", gx["B"]), ("E", gx["G"])):
            ops = [self.opening(f"DR-HALL-{side}-FRONT", D["hall_front"]["y_center"], D["hall_front"]["width"], 0.0,
                                role="Hall exit - front zone"),
                   self.opening(f"DR-HALL-{side}-WING", D["hall_wing"]["y_center"], D["hall_wing"]["width"], 0.0,
                                role="Hall exit - platform wing"),
                   self.opening(f"DR-HALL-{side}-CROSS", (self.band[0] + ca[1]) / 2, D["hall_cross_aisle"]["width"],
                                self.cross_level, role="Hall exit - mid cross aisle")]
            hc = st["hall_column"]
            cav = [(gy[a] + hc / 2, gy[b] - hc / 2, hc, st["brace_section"] + 0.05) for a, b in st["wall_braced_bays"]]
            self.wall(f"ENV-WALL-HALL-{side}", "10_ENV_Envelope", "y", xc, th, gy["3"] + th / 2, gy["11"] - th / 2,
                      -0.3, st["truss_bearing_z"], ops, storey="L00", cavity=cav,
                      props={"BracedBays": "cavity wall (2 leaves) with X-bracing in cavity"})
            hc = st["hall_column"] / 2
            cx0 = xc - hc - 0.2 if side == "W" else xc + hc
            self.add(Element(f"ENV-WALL-HALL-{side}-UPPER", "10_ENV_Envelope", "IfcWall", "SOLIDWALL", "L05",
                             [("box", (cx0, gy["3"] - th / 2, st["truss_bearing_z"], cx0 + 0.2, gy["11"] + th / 2, hall_top))],
                             props={"IsExternal": True, "Description": "Eaves-zone cladding outside column line (clear of truss ends)"}))
            for o in ops:
                self.exits.append({"id": o["name"], "wall": side, "x": xc, "y": (o["a0"] + o["a1"]) / 2,
                                   "z": o["z0"], "width": o["a1"] - o["a0"], "role": o["role"]})
        # ---- hall rear (grid 3) gable wall with rear exits at top level + booth window
        blocks, aisles, _ = self.block_ranges(0.0)
        F = P["foyer"]
        ops = []
        for ai in D["hall_rear_aisles"]:
            a = aisles[ai - 1]
            ops.append(self.opening(f"DR-HALL-REAR-A{ai}", (a[0] + a[1]) / 2, D["hall_rear_width"], self.top_level,
                                    role="Hall exit - rear to upper foyer"))
        bx0, bx1 = F["booth_x"]
        booth_floor = self.top_level + F["booth_floor_raise"]
        ops.append({"name": "WN-BOOTH-VIEW", "a0": bx0 + 0.5, "a1": bx1 - 0.5, "z0": rnd(booth_floor + 0.9),
                    "z1": rnd(booth_floor + 2.1), "kind": "window", "role": "Sound/media booth viewing window",
                    "props": {"StoreyOverride": "L02: booth viewing window - the booth floor is on L02"}})
        self.wall("ENV-WALL-HALL-REAR", "10_ENV_Envelope", "x", gy["3"], th, gx["B"] - th / 2, gx["G"] + th / 2,
                  -0.3, st["truss_bearing_z"], ops, storey="L00")
        for o in ops:
            if o["kind"] == "door":
                self.exits.append({"id": o["name"], "wall": "REAR", "x": (o["a0"] + o["a1"]) / 2, "y": gy["3"],
                                   "z": o["z0"], "width": o["a1"] - o["a0"], "role": o["role"]})
        # stage rear wall (grid 11) with doors to BOH corridor
        ops = [self.opening(f"DR-STAGE-BOH-{i}", x, 1.8, 0.0, role="Stage to BOH corridor")
               for i, x in enumerate(D["stage_rear_doors_x"], start=1)]
        self.wall("ENV-WALL-STAGE-REAR", "10_ENV_Envelope", "x", gy["11"], th, gx["B"] - th / 2, gx["G"] + th / 2,
                  -0.3, st["truss_bearing_z"], ops, storey="L00")
        # closure flashings: wall tops to the offset cladding (prevents an open slot in the envelope)
        hc = st["hall_column"] / 2
        tb = st["truss_bearing_z"]
        gofs_ = st["chord_section"] / 2 + 0.05
        for nm, box in (("W", (gx["B"] - hc - 0.2, gy["3"] - th / 2, tb - 0.05, gx["B"] + th / 2, gy["11"] + th / 2, tb)),
                        ("E", (gx["G"] - th / 2, gy["3"] - th / 2, tb - 0.05, gx["G"] + hc + 0.2, gy["11"] + th / 2, tb)),
                        ("REAR", (gx["B"] - hc - 0.2, gy["3"] - gofs_ - th, tb - 0.05, gx["G"] + hc + 0.2, gy["3"] - th / 2, tb)),
                        ("STAGE", (gx["B"] - hc - 0.2, gy["11"] + th / 2, tb - 0.05, gx["G"] + hc + 0.2, gy["11"] + gofs_ + th, tb))):
            self.add(Element(f"ENV-FLASHING-{nm}", "10_ENV_Envelope", "IfcCovering", "USERDEFINED", "L05", [("box", box)],
                             object_type="Closure flashing",
                             props={"IsExternal": True, "Description": "Closure flashing wall top / offset cladding (concept)"}))
        # gable infills above truss bearing level, following the roof profile
        gofs = st["chord_section"] / 2 + 0.05
        for nm, yc in (("REAR", gy["3"]), ("STAGE", gy["11"])):
            poly = [(gx["B"], st["truss_bearing_z"]), (gx["G"], st["truss_bearing_z"])]
            poly += [(gx["G"], self.roof_z(gx["G"]) - 0.05), ((gx["B"] + gx["G"]) / 2, self.roof_z((gx["B"] + gx["G"]) / 2) - 0.05),
                     (gx["B"], self.roof_z(gx["B"]) - 0.05)]
            self.add(Element(f"ENV-WALL-GABLE-{nm}", "10_ENV_Envelope", "IfcWall", "SOLIDWALL", "L03",
                             [("extrude_xz", (poly, *((yc - gofs - th, yc - gofs) if nm == "REAR" else (yc + gofs, yc + gofs + th))))],
                             props={"IsExternal": True, "Description": "Gable cladding outside the gable truss plane"}))
        # ---- external walls A (west) and H (east), split by roof zone
        for side, xc, hall_door_x in (("W", gx["A"], gx["B"]), ("E", gx["H"], gx["G"])):
            # foyer zone 0..16
            ops = [self.opening(f"DR-EXT-{side}-FOYER", D["foyer_side_ext_y"], ext_w, 0.0, role="External exit - foyer side")]
            self.wall(f"ENV-WALL-EXT-{side}-FOYER", "10_ENV_Envelope", "y", xc, te, gy["1"] - te / 2, gy["3"],
                      -0.3, foy_top, ops)
            # ambulatory zone 16..80
            cx = D["cross_aisle_external"]
            ops = [self.opening(f"DR-EXT-{side}-AMB-S", D["ambulatory_south_ext_y"], ext_w, 0.0,
                                role="External exit - ambulatory south"),
                   self.opening(f"DR-EXT-{side}-AMB-FRONT", D["hall_front"]["y_center"], D["hall_front"]["width"], 0.0,
                                role="External exit - opposite hall front exit"),
                   self.opening(f"DR-EXT-{side}-AMB-WING", D["hall_wing"]["y_center"], ext_w, 0.0,
                                role="External exit - opposite hall wing exit"),
                   self.opening(f"DR-EXT-{side}-AMB-CROSS", (self.band[0] + ca[1]) / 2, cx["width"], self.cross_level,
                                role="External exit - cross-aisle landing to external steps")]
            self.wall(f"ENV-WALL-EXT-{side}-AMB", "10_ENV_Envelope", "y", xc, te, gy["3"], gy["11"], -0.3, amb_top, ops)
            # external steps from the cross-aisle landing down to (assumed flat) grade, running away from the wall
            n = math.ceil(round(self.cross_level / cx["max_riser"], 6))
            r = self.cross_level / n
            sgn = -1 if side == "W" else 1
            face = xc + sgn * te / 2
            yc_x = (self.band[0] + ca[1]) / 2
            ya, yb_ = yc_x - cx["width"] / 2, yc_x + cx["width"] / 2
            parts = [("box", (min(face, face + sgn * cx["landing"]), ya, -0.3, max(face, face + sgn * cx["landing"]), yb_,
                              self.cross_level))]
            x = face + sgn * cx["landing"]
            for k in range(1, n):
                xa, xb = x + sgn * (k - 1) * cx["going"], x + sgn * k * cx["going"]
                parts.append(("box", (min(xa, xb), ya, -0.3, max(xa, xb), yb_, self.cross_level - k * r)))
            self.add(Element(f"ARC-STAIR-EXT-{side}-CROSS", "20_ARC_Circulation", "IfcStair", "STRAIGHT_RUN_STAIR", "L00",
                             parts, props={"IsExternal": True, "Risers": n, "Riser": rnd(r, 3), "Going": cx["going"],
                                           "Width": cx["width"], "Status": "Assumes flat grade - site levels unknown"}))
            ops = [self.opening(f"DR-EXT-{side}-BOH", D["boh_ext_y"], ext_w, 0.0, role="External exit - BOH corridor")]
            self.wall(f"ENV-WALL-EXT-{side}-BOH", "10_ENV_Envelope", "y", xc, te, gy["11"], gy["12"] + te / 2,
                      -0.3, boh_top, ops)
        # foyer facade (grid 1) with main doors
        ops = []
        for i, (a, b) in enumerate(F["main_door_bays"], start=1):
            ops.append(self.opening(f"DR-EXT-MAIN-{i}", (gx[a] + gx[b]) / 2, F["main_door_width"], 0.0,
                                    role="Main entrance / external exit"))
        self.wall("ENV-WALL-EXT-FACADE", "10_ENV_Envelope", "x", gy["1"], te, gx["A"] + te / 2, gx["H"] - te / 2,
                  -0.3, foy_top, ops)
        # BOH rear (grid 12)
        self.wall("ENV-WALL-EXT-BOH-REAR", "10_ENV_Envelope", "x", gy["12"], te, gx["A"] + te / 2, gx["H"] - te / 2,
                  -0.3, boh_top, [])
        # ambulatory/foyer upper walls of hall B/G between roof levels are part of hall walls above.
        # ---- BOH internal walls
        B = P["back_of_house"]
        yc = gy["11"] + th / 2 + B["corridor_depth"]
        ops = []
        for rid, label, xa, xb in B["rooms"]:
            ops.append(self.opening(f"DR-{rid}", (xa + xb) / 2, 1.0 if (xb - xa) < 4 else 1.2, 0.0, role=f"Door to {label}"))
        self.wall("ARC-WALL-BOH-CORRIDOR", "20_ARC_Walls", "x", yc, ti, gx["A"] + te / 2, gx["H"] - te / 2, 0.0, boh_top - 0.5,
                  ops, predefined="PARTITIONING")
        for rid, label, xa, xb in B["rooms"][1:]:
            self.wall(f"ARC-WALL-BOH-{rid}", "20_ARC_Walls", "y", xa, ti, yc + ti / 2, gy["12"] - te / 2, 0.0,
                      boh_top - 0.5, [], predefined="PARTITIONING")
        # ---- foyer toilet blocks, lift shaft, booth
        for side, (x0, y0, x1, y1) in F["toilet_blocks"].items():
            ops = [self.opening(f"DR-WC-{side}-MAIN", (y0 + y1) / 2, 1.2, 0.0, role="Toilet block entrance from foyer side passage")]
            self.wall(f"ARC-WALL-WC-{side}-S", "20_ARC_Walls", "x", y0, ti, x0, x1, 0.0, 3.0, [], predefined="PARTITIONING")
            self.wall(f"ARC-WALL-WC-{side}-W", "20_ARC_Walls", "y", x0, ti, y0, y1, 0.0, 3.0, ops if side == "W" else [],
                      predefined="PARTITIONING")
            self.wall(f"ARC-WALL-WC-{side}-E", "20_ARC_Walls", "y", x1, ti, y0, y1, 0.0, 3.0, ops if side == "E" else [],
                      predefined="PARTITIONING")
            # accessible WC partitions (2 per block at the inner end)
            xa = x1 - 4.4 if side == "W" else x0 + 4.4
            self.wall(f"ARC-WALL-WC-{side}-ACC", "20_ARC_Walls", "y", xa, ti, y0, y1, 0.0, 3.0, [], predefined="PARTITIONING")
        lx0, ly0, lx1, ly1 = F["lift_xy"]
        tl = self.top_level
        for nm, axis, c, a0, a1, ops in (
                ("S", "x", ly0, lx0, lx1, [self.opening("DR-LIFT-L00", (lx0 + lx1) / 2, 1.1, 0.0, height=2.1, role="Lift door L00"),
                                           self.opening("DR-LIFT-L02", (lx0 + lx1) / 2, 1.1, tl, height=2.1, role="Lift door upper foyer")]),
                ("W", "y", lx0, ly0, ly1, []), ("E", "y", lx1, ly0, ly1, [])):
            self.wall(f"ARC-WALL-LIFT-{nm}", "20_ARC_Walls", axis, c, 0.2, a0, a1, 0.0, foy_top - 0.6, ops,
                      predefined="SOLIDWALL", props={"Description": "Lift shaft enclosure - stability contribution NOT assumed (A-13)"})
        self.add(Element("ARC-LIFT-CAR", "20_ARC_Circulation", "IfcTransportElement", "ELEVATOR", "L00",
                         [("box", (lx0 + 0.3, ly0 + 0.3, 0.0, lx1 - 0.3, ly1 - 0.3, 2.3))],
                         props={"Status": "Space allowance - lift type/capacity not selected"}))
        bx0, bx1 = F["booth_x"]
        by0, by1 = F["booth_y"]
        bf = self.top_level + F["booth_floor_raise"]
        self.add(Element("ARC-BOOTH-FLOOR", "20_ARC_Floors", "IfcSlab", "FLOOR", "L02",
                         [("box", (bx0, by0, self.top_level, bx1, by1, bf))],
                         props={"Description": "Raised booth floor", "StoreyOverride": "L02: raised booth platform within the upper foyer"}))
        ops = [self.opening("DR-BOOTH", bx0 + 1.0, 0.9, self.top_level, height=2.1, role="Booth door (step/ramp detail TBC)")]
        self.wall("ARC-WALL-BOOTH-S", "20_ARC_Walls", "x", by0, ti, bx0, bx1, self.top_level, bf + F["booth_height"], ops,
                  predefined="PARTITIONING", storey="L02")
        self.wall("ARC-WALL-BOOTH-W", "20_ARC_Walls", "y", bx0, ti, by0, by1, self.top_level, bf + F["booth_height"], [],
                  predefined="PARTITIONING", storey="L02")
        self.wall("ARC-WALL-BOOTH-E", "20_ARC_Walls", "y", bx1, ti, by0, by1, self.top_level, bf + F["booth_height"], [],
                  predefined="PARTITIONING", storey="L02")

    # ---------------------------------------------------------------- floors outside the hall + circulation
    def build_floors_circulation(self):
        P = self.P
        gx, gy = self.gx, self.gy
        te, th = P["walls"]["external_thickness"], P["walls"]["hall_thickness"]
        st = P["structure"]["slab_thickness"]
        F, AM = P["foyer"], P["ambulatory"]
        # ground slabs
        self.add(Element("ARC-SLAB-FOYER", "20_ARC_Floors", "IfcSlab", "FLOOR", "L00",
                         [("box", (gx["A"] + te / 2, gy["1"] + te / 2, -st, gx["H"] - te / 2, gy["3"] - th / 2, 0.0))]))
        self.add(Element("ARC-SLAB-BOH", "20_ARC_Floors", "IfcSlab", "FLOOR", "L00",
                         [("box", (gx["A"] + te / 2, gy["11"] + th / 2, -st, gx["H"] - te / 2, gy["12"] - te / 2, 0.0))]))
        # mezzanine / upper foyer
        tl = self.top_level
        my0, my1 = F["mezzanine_y"]
        self.add(Element("ARC-SLAB-UPPER-FOYER", "20_ARC_Floors", "IfcSlab", "FLOOR", "L02",
                         [("box", (gx["A"] + te / 2, my0, tl - st, gx["H"] - te / 2, my1 - th / 2, tl))],
                         props={"Description": "Upper foyer (mezzanine) at rear-platform level"}))
        # mezzanine stairs: straight run along +X with mid landing; top landing abuts mezzanine edge
        n_r = math.ceil(round(tl / F["stair_max_riser"], 6))
        r = tl / n_r
        n1 = math.ceil(n_r / 2)
        n2 = n_r - n1
        g = F["stair_going"]
        w = F["stair_width"]
        col = P["structure"]["other_column"]
        stair_info = []
        rail_gaps = []
        for i, ((a, b), sd) in enumerate(zip(F["stair_bays"], F["stair_dirs"]), start=1):
            # the run is parallel to the upper-foyer edge and stays south of the grid-2 columns (y < column face), so
            # it may pass a column line; only the top landing must sit between columns, where it meets the slab edge.
            col_face_y = gy["2"] - col / 2 - 0.01
            sy1 = col_face_y
            sy0 = sy1 - w
            tl_len = F["stair_top_landing"]
            run1, run2 = (n1 - 1) * g, (n2 - 1) * g
            length = run1 + F["stair_mid_landing"] + run2 + tl_len
            sgn = 1 if sd == "+" else -1
            x_top_end = gx[b] - col / 2 - 0.05 if sd == "+" else gx[a] + col / 2 + 0.05  # landing edge at the column
            x_start = x_top_end - sgn * length

            def seg(x0_, x1_):
                return min(x0_, x1_), max(x0_, x1_)

            parts = []
            x = x_start
            for k in range(1, n1):
                xa_, xb_ = seg(x + sgn * (k - 1) * g, x + sgn * k * g)
                parts.append(("box", (xa_, sy0, 0.0, xb_, sy1, k * r)))
            x = x_start + sgn * run1
            xa_, xb_ = seg(x, x + sgn * F["stair_mid_landing"])
            parts.append(("box", (xa_, sy0, 0.0, xb_, sy1, n1 * r)))
            x += sgn * F["stair_mid_landing"]
            for k in range(1, n2):
                xa_, xb_ = seg(x + sgn * (k - 1) * g, x + sgn * k * g)
                parts.append(("box", (xa_, sy0, 0.0, xb_, sy1, (n1 + k) * r)))
            x += sgn * run2
            lx0_, lx1_ = seg(x, x + sgn * tl_len)
            parts.append(("box", (lx0_, sy0, 0.0, lx1_, my0, tl)))  # top landing reaches the slab edge
            self.add(Element(f"ARC-STAIR-FOYER-{i}", "20_ARC_Circulation", "IfcStair", "TWO_STRAIGHT_RUN_STAIR",
                             "L00", parts, props={"Risers": n_r, "Riser": rnd(r, 3), "Going": g, "Width": w,
                                                  "TopLandingOpening": rnd(lx1_ - lx0_, 3),
                                                  "Role": "Upper foyer egress / access stair"}))
            x0_all, x1_all = seg(x_start, x_top_end)
            stair_info.append({"name": f"ARC-STAIR-FOYER-{i}", "x_top": rnd((lx0_ + lx1_) / 2), "x0": rnd(x0_all),
                               "x1": rnd(x1_all), "width": w, "landing": (rnd(lx0_), rnd(lx1_)), "dir": sd,
                               "opening": rnd(lx1_ - lx0_, 3)})
            rail_gaps.append((lx0_, lx1_))
        self.stairs = stair_info
        # refuge spaces for wheelchair users on L02, beside each stair head on the upper-foyer slab (A-21)
        A = P["accessibility"]
        ww, rd = A["wheelchair_space_width"], A["refuge_depth"]
        self.refuges = []
        for st_ in stair_info:
            l0, l1 = st_["landing"]
            for k in range(A["refuge_spaces_per_stair"]):  # beside the landing, on the side away from its column
                if st_["dir"] == "+":
                    x1r = l0 - 0.2 - k * (ww + 0.1)
                    x0r = x1r - ww
                else:
                    x0r = l1 + 0.2 + k * (ww + 0.1)
                    x1r = x0r + ww
                name = f"ACC-REFUGE-{st_['name'][-1]}-{k + 1}"
                self.add(Element(name, "40_SEAT_Accessible", "IfcSpatialZone", "USERDEFINED", "L02",
                                 [("box", (x0r, my0 + 0.45, tl, x1r, my0 + 0.45 + rd, tl + 0.02))],
                                 object_type="RefugeSpace",
                                 props={"Stair": st_["name"], "Width": ww, "Depth": rd,
                                        "Status": "Concept refuge allowance - enclosure/fire separation not designed (OI-16)"}))
                self.refuges.append(name)
        self.metrics["foyer_stair_riser"] = rnd(r, 3)
        self.metrics["foyer_stair_risers"] = n_r
        self.check("CIR-01", "Upper foyer stair riser", r <= F["stair_max_riser"] + 1e-9, rnd(r, 3),
                   f"<= {F['stair_max_riser']} m placeholder")
        # mezzanine edge guardrail with gaps at stair top landings; it stops at each grid-2 column face
        rail_gaps += [(x - col / 2, x + col / 2) for x in gx.values()]
        merged = []
        for a, b in sorted(rail_gaps):
            if merged and a <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], b))
            else:
                merged.append((a, b))
        xs = [gx["A"] + te / 2]
        for a, b in merged:
            xs += [max(a, gx["A"] + te / 2), min(b, gx["H"] - te / 2)]
        xs.append(gx["H"] - te / 2)
        parts = []
        for k in range(0, len(xs), 2):
            if xs[k + 1] - xs[k] > 0.05:
                parts.append(("box", (xs[k], my0, tl, xs[k + 1], my0 + 0.05, tl + 1.1)))
        self.add(Element("ARC-RAIL-UPPER-FOYER-EDGE", "20_ARC_Circulation", "IfcRailing", "GUARDRAIL", "L02", parts,
                         props={"Height": 1.1, "Status": "Concept guard; height/loads to local code"}))
        # ambulatories: level ends, ramps with landings to the cross-aisle door landing at the cross level
        ec = self.cross_level
        ca = self.cross_passage
        xo = {"W": (gx["A"] + te / 2, gx["B"] - th / 2), "E": (gx["G"] + th / 2, gx["H"] - te / 2)}
        land0, land1 = self.band[0] - AM["landing_margin"], ca[1] + AM["landing_margin"]
        ramp_report = []
        for side, (x0, x1) in xo.items():
            self.add(Element(f"ARC-SLAB-AMB-{side}-SOUTH", "20_ARC_Floors", "IfcSlab", "FLOOR", "L00",
                             [("box", (x0, gy["3"] - th / 2, -st, x1, AM["south_level_end_y"], 0.0))]))
            self.add(Element(f"ARC-SLAB-AMB-{side}-NORTH", "20_ARC_Floors", "IfcSlab", "FLOOR", "L00",
                             [("box", (x0, AM["north_level_start_y"], -st, x1, gy["11"] + th / 2, 0.0))]))
            self.add(Element(f"ARC-SLAB-AMB-{side}-LANDING", "20_ARC_Floors", "IfcSlab", "LANDING", "L01",
                             [("box", (x0, land0, -st, x1, land1, ec))]))
            for nm, ya, yb_, z_a, z_b in (("S", AM["south_level_end_y"], land0, 0.0, ec),
                                          ("N", land1, AM["north_level_start_y"], ec, 0.0)):
                parts, info = self.ramp_parts(x0, x1, ya, yb_, z_a, z_b, AM["max_ramp_run"], AM["intermediate_landing"], st)
                self.add(Element(f"ARC-RAMP-AMB-{side}-{nm}", "20_ARC_Circulation", "IfcRamp", "STRAIGHT_RUN_RAMP",
                                 "L00", parts, props={"Gradient_1_in": info["gradient_1_in"], "Rise": rnd(ec, 3),
                                                      "Flights": info["flights"], "Width": rnd(x1 - x0, 2)}))
                ramp_report.append({"name": f"ARC-RAMP-AMB-{side}-{nm}", **info, "width": rnd(x1 - x0, 2)})
        self.ramps = ramp_report
        gmin = min(rp["gradient_1_in"] for rp in ramp_report)
        self.metrics["ambulatory_ramp_steepest_1_in"] = gmin
        self.check("ACC-04", "Ambulatory ramp gradient (accessible route to mid cross aisle)", gmin >= 12.0, gmin,
                   ">= 1:12 placeholder with landings every <= 9 m run")

    def ramp_parts(self, x0, x1, ya, yb_, z_a, z_b, max_run, landing, st):
        """Ramp from (ya,z_a) to (yb_,z_b) along Y split into flights with intermediate landings."""
        total = yb_ - ya
        n = 1
        while (total - (n - 1) * landing) / n > max_run:
            n += 1
        run = (total - (n - 1) * landing) / n
        rise = (z_b - z_a) / n
        parts = []
        y, z = ya, z_a
        for i in range(n):
            za, zb = z, z + rise
            corners = [(x0, y, -st), (x1, y, -st), (x1, y + run, -st), (x0, y + run, -st),
                       (x0, y, za), (x1, y, za), (x1, y + run, zb), (x0, y + run, zb)]
            parts.append(("prism8", corners))
            y += run
            z = zb
            if i < n - 1:
                parts.append(("box", (x0, y, -st, x1, y + landing, z)))
                y += landing
        return parts, {"flights": n, "run_per_flight": rnd(run, 3), "rise_per_flight": rnd(abs(rise), 3),
                       "gradient_1_in": rnd(run / abs(rise), 2) if rise else None}

    # ---------------------------------------------------------------- structure
    def roof_z(self, x):
        """Top-chord centreline z at plan x (duo-pitch truss)."""
        st, gx = self.P["structure"], self.gx
        xm = (gx["B"] + gx["G"]) / 2
        half = (gx["G"] - gx["B"]) / 2
        bz = st["truss_bearing_z"] + st["chord_section"] / 2
        frac = 1 - abs(x - xm) / half
        return bz + st["truss_depth_eaves"] + (st["truss_depth_ridge"] - st["truss_depth_eaves"]) * frac

    def build_structure(self):
        P, st = self.P, self.P["structure"]
        gx, gy = self.gx, self.gy
        tl = self.top_level
        bw = st["beam_width"]
        foy_beam_bot = P["foyer"]["roof_top"] - st["roof_build_up"] - st["foyer_roof_beam_depth"]
        amb_beam_bot = P["ambulatory"]["roof_top"] - st["roof_build_up"] - st["low_roof_beam_depth"]
        boh_beam_bot = P["back_of_house"]["roof_top"] - st["roof_build_up"] - st["low_roof_beam_depth"]
        cols = {}

        def col(letter, num, top, kind):
            key = (letter, num)
            size = st["hall_column"] if kind == "hall" else st["other_column"]
            if key in cols and cols[key]["top"] >= top:
                return
            cols[key] = {"top": top, "size": max(size, cols.get(key, {}).get("size", 0)), "kind": kind}

        hall_nums = [str(n) for n in range(3, 12)]
        for n in hall_nums:
            for L in ("B", "G"):
                col(L, n, st["truss_bearing_z"], "hall")
        for n in ("3", "11"):
            for L in ("C", "D", "E", "F"):
                col(L, n, st["truss_bearing_z"], "gable")
        for L in gx:
            col(L, "1", foy_beam_bot, "foyer")
            col(L, "2", foy_beam_bot, "foyer")
            col(L, "12", boh_beam_bot, "boh")
        for L in ("A", "H"):
            col(L, "3", foy_beam_bot, "perimeter")
            for n in [str(k) for k in range(4, 12)]:
                col(L, n, amb_beam_bot, "perimeter")
        self.columns = []
        for (L, n), c in sorted(cols.items(), key=lambda kv: (int(kv[0][1]), kv[0][0])):
            x, y, s = gx[L], gy[n], c["size"]
            pad = st["pad_hall"] if c["kind"] in ("hall",) else st["pad_other"]
            z0 = st["pad_top_z"]
            self.add(Element(f"STR-COL-{L}{n}", "30_STR_Columns", "IfcColumn", "COLUMN", "L00",
                             [("box", (x - s / 2, y - s / 2, z0, x + s / 2, y + s / 2, c["top"]))], origin=(x, y, z0),
                             props={"Grid": f"{L}/{n}", "NominalSection": f"{s:.2f}x{s:.2f} placeholder",
                                    "Role": c["kind"], "DesignStatus": "Space reservation only - not designed"}))
            self.add(Element(f"STR-FTG-{L}{n}", "30_STR_Foundations", "IfcFooting", "PAD_FOOTING", "L00",
                             [("box", (x - pad / 2, y - pad / 2, z0 - st["pad_thickness"], x + pad / 2, y + pad / 2, z0))],
                             origin=(x, y, z0 - st["pad_thickness"]),
                             props={"Grid": f"{L}/{n}", "DesignStatus": "Reference location only - no geotechnical data, not designed"}))
            self.columns.append({"grid": f"{L}{n}", "x": x, "y": y, "size": s, "top": c["top"], "kind": c["kind"]})
        # ---- trusses
        cs, ws = st["chord_section"], st["web_section"]
        npnl = st["truss_panels"]
        xb, xg = gx["B"], gx["G"]
        bz = st["truss_bearing_z"] + cs / 2
        pts_x = [xb + (xg - xb) * i / npnl for i in range(npnl + 1)]
        self.trusses = []
        for n in hall_nums:
            y = gy[n]
            asm = f"STR-TRUSS-T{n}"
            members = []
            for i in range(npnl):
                members.append(("BC", (pts_x[i], y, bz), (pts_x[i + 1], y, bz), cs, "CHORD"))
                members.append(("TC", (pts_x[i], y, self.roof_z(pts_x[i])), (pts_x[i + 1], y, self.roof_z(pts_x[i + 1])), cs, "CHORD"))
            for i in range(npnl + 1):
                members.append(("V", (pts_x[i], y, bz), (pts_x[i], y, self.roof_z(pts_x[i])), ws, "MEMBER"))
            mid = npnl // 2
            for i in range(npnl):
                if i < mid:  # Pratt: diagonals slope down towards midspan
                    p0, p1 = (pts_x[i], y, self.roof_z(pts_x[i])), (pts_x[i + 1], y, bz)
                else:
                    p0, p1 = (pts_x[i], y, bz), (pts_x[i + 1], y, self.roof_z(pts_x[i + 1]))
                members.append(("D", p0, p1, ws, "MEMBER"))
            for k, (tag, p0, p1, sec, pre) in enumerate(members, start=1):
                self.add(Element(f"{asm}-{tag}{k:02d}", "30_STR_Roof_Trusses", "IfcMember", pre, "L03",
                                 [("strut", (p0, p1, sec, sec))], origin=p0, assembly=asm, kind="strut",
                                 strut=(p0, p1, sec / 2),
                                 props={"Assembly": asm, "MemberRole": tag, "DesignStatus": "Placeholder section"}))
            self.trusses.append({"name": asm, "y": y, "span": xg - xb, "members": len(members)})
        self.metrics["truss_span"] = xg - xb
        self.metrics["truss_count"] = len(self.trusses)
        # purlins along Y at top-chord panel points
        ps = st["purlin_section"]
        for a, b in zip(hall_nums[:-1], hall_nums[1:]):
            for i, x in enumerate(pts_x):
                z = self.roof_z(x) + cs / 2 + ps[1] / 2
                p0, p1 = (x, gy[a] + cs / 2, z), (x, gy[b] - cs / 2, z)
                self.add(Element(f"STR-PURLIN-{a}-{b}-P{i:02d}", "30_STR_Roof_Trusses", "IfcMember", "PURLIN", "L03",
                                 [("strut", (p0, p1, ps[0], ps[1]))], origin=p0, kind="strut", strut=(p0, p1, ps[1] / 2)))
        # roof plane bracing (X in braced bays, at top-chord level)
        bs = st["brace_section"]
        for a, b in st["roof_braced_bays"]:
            for i in range(npnl):
                for j, (xa, xb2) in enumerate(((pts_x[i], pts_x[i + 1]), (pts_x[i + 1], pts_x[i]))):
                    p0 = (xa, gy[a], self.roof_z(xa) - cs)
                    p1 = (xb2, gy[b], self.roof_z(xb2) - cs)
                    self.add(Element(f"STR-BRACE-ROOF-{a}-{b}-{i:02d}{'ab'[j]}", "30_STR_Bracing", "IfcMember", "BRACE",
                                     "L03", [("strut", (p0, p1, bs, bs))], origin=p0, kind="strut", strut=(p0, p1, bs / 2)))
        # vertical wall bracing on B and G in braced bays
        for a, b in st["wall_braced_bays"]:
            for L in ("B", "G"):  # in the column plane, inside the cavity of the braced-bay wall
                x = gx[L]
                z0, z1 = 0.6, st["truss_bearing_z"] - 0.6
                for j, (ya, yb_) in enumerate(((gy[a], gy[b]), (gy[b], gy[a]))):
                    p0 = (x, ya + (0.4 if ya < yb_ else -0.4), z0)
                    p1 = (x, yb_ + (-0.4 if ya < yb_ else 0.4), z1)
                    self.add(Element(f"STR-BRACE-WALL-{L}-{a}-{b}{'ab'[j]}", "30_STR_Bracing", "IfcMember", "BRACE", "L00",
                                     [("strut", (p0, p1, bs, bs))], origin=p0, kind="strut", strut=(p0, p1, bs / 2)))
        # gable bracing above openings
        for a, b in st["gable_braced_bays"]:
            for n, zlow in (("3", tl + 3.5), ("11", st["gable_brace_foot_z"]["11"])):
                off = st["other_column"] / 2 + bs / 2 + 0.01  # hall side of the gable posts, clear of the wall
                y = gy[n] + off if n == "3" else gy[n] - off
                for j, (xa, xb2) in enumerate(((gx[a], gx[b]), (gx[b], gx[a]))):
                    p0 = (xa + (0.3 if xa < xb2 else -0.3), y, zlow)
                    p1 = (xb2 + (-0.3 if xa < xb2 else 0.3), y, st["truss_bearing_z"] - 0.4)
                    self.add(Element(f"STR-BRACE-GABLE-{n}-{a}{b}{'ab'[j]}", "30_STR_Bracing", "IfcMember", "BRACE", "L00",
                                     [("strut", (p0, p1, bs, bs))], origin=p0, kind="strut", strut=(p0, p1, bs / 2)))
                ps0 = (gx[a] + st["other_column"] / 2 + 0.01, y, zlow - bs)
                ps1 = (gx[b] - st["other_column"] / 2 - 0.01, y, zlow - bs)
                self.add(Element(f"STR-STRUT-GABLE-{n}-{a}{b}", "30_STR_Bracing", "IfcMember", "STRUT", "L00",
                                 [("strut", (ps0, ps1, bs, bs))], origin=ps0, kind="strut", strut=(ps0, ps1, bs / 2),
                                 props={"Role": "Collects gable brace feet into gable posts (load path to pad footings)"}))
        # eaves ties along B and G
        for L in ("B", "G"):
            for a, b in zip(hall_nums[:-1], hall_nums[1:]):
                x = gx[L]
                hs = st["hall_column"] / 2
                self.add(Element(f"STR-BEAM-EAVES-{L}-{a}-{b}", "30_STR_Beams", "IfcBeam", "BEAM", "L03",
                                 [("box", (x - bw / 2, gy[a] + hs, st["truss_bearing_z"] - st["eaves_tie_depth"],
                                           x + bw / 2, gy[b] - hs, st["truss_bearing_z"]))]))
        # foyer roof beams (Y direction at each letter, X direction at grids 1,2)
        for L in gx:
            for a, b in (("1", "2"), ("2", "3")):
                self.add(Element(f"STR-BEAM-FOYROOF-{L}-{a}-{b}", "30_STR_Beams", "IfcBeam", "BEAM", "L04",
                                 [("box", (gx[L] - bw / 2, gy[a] + 0.2, foy_beam_bot, gx[L] + bw / 2,
                                           gy[b] - (0.3 if b == "3" and L in "BG" else 0.2),
                                           foy_beam_bot + st["foyer_roof_beam_depth"]))]))
        letters = list(gx)
        for n in ("1", "2"):
            for a, b in zip(letters[:-1], letters[1:]):
                self.add(Element(f"STR-BEAM-FOYROOF-{n}-{a}{b}", "30_STR_Beams", "IfcBeam", "BEAM", "L04",
                                 [("box", (gx[a] + 0.2, gy[n] - bw / 2, foy_beam_bot, gx[b] - 0.2, gy[n] + bw / 2,
                                           foy_beam_bot + st["foyer_roof_beam_depth"]))]))
        # mezzanine beams
        mz_top = tl - st["slab_thickness"]
        mz_bot = mz_top - st["mezz_beam_depth"]
        for L in gx:
            self.add(Element(f"STR-BEAM-MEZZ-{L}-2-3", "30_STR_Beams", "IfcBeam", "BEAM", "L02",
                             [("box", (gx[L] - bw / 2, gy["2"] + 0.2, mz_bot, gx[L] + bw / 2,
                                       gy["3"] - (0.3 if L in "BG" else 0.2), mz_top))]))
        for a, b in zip(letters[:-1], letters[1:]):
            self.add(Element(f"STR-BEAM-MEZZ-2-{a}{b}", "30_STR_Beams", "IfcBeam", "BEAM", "L02",
                             [("box", (gx[a] + 0.2, gy["2"] - bw / 2, mz_bot, gx[b] - 0.2, gy["2"] + bw / 2, mz_top))]))
        # ambulatory roof beams (X direction A-B and G-H at grids 3..11) + edge beams
        for n in hall_nums:
            for a, b in (("A", "B"), ("G", "H")):
                self.add(Element(f"STR-BEAM-AMBROOF-{n}-{a}{b}", "30_STR_Beams", "IfcBeam", "BEAM", "L03",
                                 [("box", (gx[a] + (0.2 if a == "A" else 0.3), gy[n] - bw / 2, amb_beam_bot,
                                           gx[b] - (0.3 if b == "B" else 0.2), gy[n] + bw / 2,
                                           amb_beam_bot + st["low_roof_beam_depth"]))]))
        for L in ("A", "H"):
            for a, b in zip(hall_nums[:-1], hall_nums[1:]):
                self.add(Element(f"STR-BEAM-AMBEDGE-{L}-{a}-{b}", "30_STR_Beams", "IfcBeam", "BEAM", "L03",
                                 [("box", (gx[L] - bw / 2, gy[a] + 0.2, amb_beam_bot, gx[L] + bw / 2, gy[b] - 0.2,
                                           amb_beam_bot + st["low_roof_beam_depth"]))]))
        # BOH roof beams (Y direction 11-12 at each letter) + grid 12 edge beams
        for L in gx:
            self.add(Element(f"STR-BEAM-BOHROOF-{L}-11-12", "30_STR_Beams", "IfcBeam", "BEAM", "L03",
                             [("box", (gx[L] - bw / 2, gy["11"] + (0.3 if L in "BG" else 0.2), boh_beam_bot,
                                       gx[L] + bw / 2, gy["12"] - 0.2, boh_beam_bot + st["low_roof_beam_depth"]))]))
        for a, b in zip(letters[:-1], letters[1:]):
            self.add(Element(f"STR-BEAM-BOHROOF-12-{a}{b}", "30_STR_Beams", "IfcBeam", "BEAM", "L03",
                             [("box", (gx[a] + 0.2, gy["12"] - bw / 2, boh_beam_bot, gx[b] - 0.2, gy["12"] + bw / 2,
                                       boh_beam_bot + st["low_roof_beam_depth"]))]))
        self.metrics["column_count"] = len(self.columns)

    def build_roofs(self):
        P, st, gx, gy = self.P, self.P["structure"], self.gx, self.gy
        te = P["walls"]["external_thickness"]
        ru = st["roof_build_up"]
        cs = st["chord_section"]
        ps = st["purlin_section"]
        xm = (gx["B"] + gx["G"]) / 2
        y0, y1 = gy["3"] - 0.5, gy["11"] + 0.5
        off = cs / 2 + ps[1]  # roof underside sits on purlins
        for nm, xa, xb in (("W", gx["B"] - 0.5, xm), ("E", xm, gx["G"] + 0.5)):
            za, zb = self.roof_z(xa) + off, self.roof_z(xb) + off
            if nm == "W":
                za = self.roof_z(gx["B"]) + off - (self.roof_z(gx["B"] + 0.5) - self.roof_z(gx["B"]))
            else:
                zb = self.roof_z(gx["G"]) + off - (self.roof_z(gx["G"] - 0.5) - self.roof_z(gx["G"]))
            corners = [(xa, y0, za), (xb, y0, zb), (xb, y1, zb), (xa, y1, za),
                       (xa, y0, za + ru), (xb, y0, zb + ru), (xb, y1, zb + ru), (xa, y1, za + ru)]
            self.add(Element(f"ENV-ROOF-HALL-{nm}", "10_ENV_Envelope", "IfcSlab", "ROOF", "L03", [("prism8", corners)],
                             origin=(xa, y0, za), props={"IsExternal": True, "Description": "Hall metal roof (concept)"}))
        self.metrics["hall_ridge_top"] = rnd(self.roof_z(xm) + off + ru, 3)
        ft = P["foyer"]["roof_top"]
        self.add(Element("ENV-ROOF-FOYER", "10_ENV_Envelope", "IfcSlab", "ROOF", "L04",
                         [("box", (gx["A"] - te / 2, gy["1"] - te / 2, ft - ru, gx["H"] + te / 2, gy["3"] - 0.15, ft))],
                         props={"IsExternal": True}))
        at = P["ambulatory"]["roof_top"]
        for nm, xa, xb in (("W", gx["A"] - te / 2, gx["B"] - 0.15), ("E", gx["G"] + 0.15, gx["H"] + te / 2)):
            self.add(Element(f"ENV-ROOF-AMB-{nm}", "10_ENV_Envelope", "IfcSlab", "ROOF", "L03",
                             [("box", (xa, gy["3"] + 0.15, at - ru, xb, gy["11"], at))], props={"IsExternal": True}))
        bt = P["back_of_house"]["roof_top"]
        self.add(Element("ENV-ROOF-BOH", "10_ENV_Envelope", "IfcSlab", "ROOF", "L03",
                         [("box", (gx["A"] - te / 2, gy["11"], bt - ru, gx["H"] + te / 2, gy["12"] + te / 2, bt))],
                         props={"IsExternal": True}))

    # ---------------------------------------------------------------- spaces / zones / services
    def build_spaces(self):
        P, gx, gy = self.P, self.gx, self.gy
        te, th = P["walls"]["external_thickness"], P["walls"]["hall_thickness"]
        F, B, ST = P["foyer"], P["back_of_house"], P["stage"]
        tl = self.top_level
        sp = []
        xw0, xw1 = gx["B"] + th / 2, gx["G"] - th / 2
        xe0, xe1 = gx["A"] + te / 2, gx["H"] - te / 2
        yr = gy["3"] - th / 2  # foyer-side face of hall rear wall
        my0 = F["mezzanine_y"][0]
        tw, tE = F["toilet_blocks"]["W"], F["toilet_blocks"]["E"]
        ty0 = tw[1]
        lx0, ly0, lx1, ly1 = F["lift_xy"]
        bx0, bx1 = F["booth_x"]
        by0, by1 = F["booth_y"]
        bz = tl + F["booth_floor_raise"]
        foy_ceiling = P["foyer"]["roof_top"] - self.P["structure"]["roof_build_up"] - self.P["structure"]["foyer_roof_beam_depth"]
        under = tl - self.P["structure"]["slab_thickness"]
        B_ = lambda x0, y0, z0, x1, y1, z1: (x0, y0, z0, x1, y1, z1)  # noqa: E731
        sp.append(("SP-01", "Auditorium seating hall", "L00", [B_(xw0, gy["3"] + th / 2, 0.0, xw1, ST["front_edge_y"], tl + 9.0)],
                   "Assembly - congregation seating (3,000 fixed seats)", None))
        sp.append(("SP-02", "Platform / pulpit and choir", "L00", [B_(ST["platform_x"][0], ST["platform_y"][0], 0.9, ST["platform_x"][1], gy["11"] - th / 2, 12.0)],
                   "Platform, pulpit, choir risers, musicians", None))
        sp.append(("SP-03", "Platform wing West (musicians / access)", "L00", [B_(xw0, ST["front_edge_y"], 0.0, ST["platform_x"][0], gy["11"] - th / 2, 12.0)], "Wing / stair to platform", None))
        sp.append(("SP-04", "Platform wing East (accessible ramp)", "L00", [B_(ST["platform_x"][1], ST["front_edge_y"], 0.0, xw1, gy["11"] - th / 2, 12.0)], "Wing / accessible ramp", None))
        sp.append(("SP-05", "Main foyer", "L00", [B_(xe0, gy["1"] + te / 2, 0.0, xe1, my0, foy_ceiling), B_(xe0, my0, 0.0, xe1, ty0, under)],
                   "Foyer, welcome, stairs, circulation", None))
        sp.append(("SP-05W", "Foyer side passage West (to ambulatory)", "L00", [B_(xe0, ty0, 0.0, tw[0], yr, under)], "Circulation", None))
        sp.append(("SP-05E", "Foyer side passage East (to ambulatory)", "L00", [B_(tE[2], ty0, 0.0, xe1, yr, under)], "Circulation", None))
        sp.append(("SP-06", "Foyer below upper foyer (centre)", "L00",
                   [B_(tw[2], ty0, 0.0, tE[0], ly0, under), B_(tw[2], ly0, 0.0, lx0, yr, under), B_(lx1, ly0, 0.0, tE[0], yr, under)],
                   "Foyer circulation / info", None))
        for side, (x0, y0, x1, y1) in F["toilet_blocks"].items():
            xa = x1 - 4.4 if side == "W" else x0 + 4.4
            main = (x0, y0, xa, y1) if side == "W" else (xa, y0, x1, y1)
            acc = (xa, y0, x1, y1) if side == "W" else (x0, y0, xa, y1)
            sp.append((f"SP-WC-{side}", f"Toilets {'West (female)' if side == 'W' else 'East (male)'}", "L00", [B_(main[0], main[1], 0.0, main[2], main[3], 3.0)], "Sanitary allowance - fixtures TBC", None))
            sp.append((f"SP-WCA-{side}", f"Accessible WCs {side} (2 cubicles)", "L00", [B_(acc[0], acc[1], 0.0, acc[2], acc[3], 3.0)], "2 accessible WC cubicles allowance", None))
        sp.append(("SP-07", "Upper foyer (mezzanine)", "L02",
                   [B_(xe0, my0, tl, xe1, by0, foy_ceiling), B_(xe0, by0, tl, lx0, yr, foy_ceiling),
                    B_(lx0, by0, tl, lx1, ly0, foy_ceiling), B_(lx1, by0, tl, bx0, yr, foy_ceiling), B_(bx1, by0, tl, xe1, yr, foy_ceiling),
                    B_(bx0, by0, bz + F["booth_height"], bx1, yr, foy_ceiling)],
                   "Rear hall exits, refuge spaces, booth access", None))
        sp.append(("SP-08", "Sound / media booth", "L02", [B_(bx0, by0, bz, bx1, by1, bz + F["booth_height"])], "Media / sound control",
                   "L02: raised booth platform within the upper foyer"))
        sp.append(("SP-09", "Lift shaft", "L00", [B_(lx0, ly0, 0.0, lx1, ly1, foy_ceiling)], "Lift allowance L00-L02", None))
        for side, x0, x1 in (("W", xe0, gx["B"] - th / 2), ("E", gx["G"] + th / 2, xe1)):
            sp.append((f"SP-AMB-{side}", f"Ambulatory {side} (circulation / egress ramps)", "L00", [B_(x0, yr, 0.0, x1, gy["11"] + th / 2, 5.3)], "Circulation / exit route", None))
        yc = gy["11"] + th / 2 + B["corridor_depth"]
        sp.append(("SP-BOH-C", "BOH corridor", "L00", [B_(xe0, gy["11"] + th / 2, 0.0, xe1, yc, 4.3)], "Circulation", None))
        for rid, label, xa, xb in B["rooms"]:
            sp.append((f"SP-{rid}", label, "L00", [B_(max(xa, xe0), yc, 0.0, min(xb, xe1), gy["12"] - te / 2, 4.3)], "Back of house", None))
        self.spaces = []
        self.space_boxes = []
        for sid, name, storey, boxes, use, override in sp:
            boxes = [tuple(rnd(v, 4) for v in b) for b in boxes]
            base_z = min(b[2] for b in boxes)
            area = sum((b[3] - b[0]) * (b[4] - b[1]) for b in boxes if abs(b[2] - base_z) < 1e-6)
            props = {"LongName": name, "Use": use, "GrossFloorArea": rnd(area, 2), "Status": "Concept allowance - unverified"}
            if override:
                props["StoreyOverride"] = override
            self.add(Element(f"SPC-{sid}", "60_ZONE_Spaces", "IfcSpace", "INTERNAL", storey,
                             [("box", b) for b in boxes], props=props))
            xs0, ys0 = min(b[0] for b in boxes), min(b[1] for b in boxes)
            xs1, ys1 = max(b[3] for b in boxes), max(b[4] for b in boxes)
            self.spaces.append({"space_id": sid, "name": name, "level": storey, "x0": rnd(xs0, 3), "y0": rnd(ys0, 3),
                                "x1": rnd(xs1, 3), "y1": rnd(ys1, 3), "area_m2": rnd(area, 2), "use": use,
                                "boxes": len(boxes)})
            self.space_boxes += [(sid, b) for b in boxes]
        self.space_checks()
        for sid, name, box in P["services"]["zones"]:
            self.add(Element(f"SRV-{sid[4:]}-ZONE", "50_SRV_Allowances", "IfcSpatialZone", "USERDEFINED", "L00",
                             [("box", tuple(box))], object_type="ServiceAllowance",
                             props={"LongName": name, "Status": "Space allowance only - no MEP design"}))
        # aisle clear zones (for clash checking and documentation)
        S = P["seating"]
        for rw in self.rows:
            for ai, (a0, a1) in enumerate(rw["aisles"], start=1):
                self.add(Element(f"ZONE-AISLE-R{rw['row']:02d}-A{ai}", "60_ZONE_Aisles", "IfcSpatialZone", "USERDEFINED",
                                 "L00" if rw["section"] == "front" else "L01",
                                 [("box", (a0, rw["yb"], rw["floor"] + 0.05, a1, rw["yf"], rw["floor"] + 2.0))],
                                 object_type="AisleClearZone", props={"Row": rw["row"], "Aisle": ai, "ClearWidth": S["aisle_width"]}))

    def space_checks(self):
        """No two spaces overlap in 3D; ground-floor plan is covered by spaces, walls or columns."""
        bx = self.space_boxes
        over = []
        for i in range(len(bx)):
            for j in range(i + 1, len(bx)):
                (a, p), (b, q) = bx[i], bx[j]
                if a != b and all(p[k] < q[k + 3] - 0.01 and q[k] < p[k + 3] - 0.01 for k in range(3)):
                    over.append(f"{a}/{b}")
        self.check("SPC-01", "IfcSpace volumes do not overlap (3D, 10 mm tolerance)", not over, sorted(set(over)) or 0, "0 overlaps")
        gx, gy = self.gx, self.gy
        te = self.P["walls"]["external_thickness"]
        solids = []
        for e in self.elements:
            if e.ifc_class in ("IfcWall", "IfcColumn") and not e.mesh_key:
                for prt in e.parts:
                    bb = part_aabb(prt)
                    if bb[2] < 1.0:
                        solids.append(bb)
        ground = [b for sid, b in bx if b[2] <= 1.0]
        n = miss = 0
        step = 0.5
        y = gy["1"] + te / 2 + step / 2
        missed = []
        while y < gy["12"] - te / 2:
            x = gx["A"] + te / 2 + step / 2
            while x < gx["H"] - te / 2:
                n += 1
                if not any(b[0] <= x <= b[3] and b[1] <= y <= b[4] for b in ground) and \
                        not any(b[0] - 0.01 <= x <= b[3] + 0.01 and b[1] - 0.01 <= y <= b[4] + 0.01 for b in solids):
                    miss += 1
                    missed.append((rnd(x, 2), rnd(y, 2)))
                x += step
            y += step
        frac = miss / n
        self.metrics["ground_space_coverage_unassigned_fraction"] = rnd(frac, 5)
        self.check("SPC-02", "Ground-level plan points (0.5 m grid) not in any space, wall or column", frac <= 0.005,
                   {"unassigned_points": miss, "of": n, "first": missed[:5]}, "<= 0.5 % of points")

    # ---------------------------------------------------------------- egress analysis
    def egress(self):
        P, E = self.P, self.P["egress_placeholders"]
        S = P["seating"]
        gx, gy = self.gx, self.gy
        front_route_y = (self.rows[0]["yf"] + P["stage"]["front_edge_y"]) / 2
        cross_y = (self.cross_passage[0] + self.cross_passage[1]) / 2
        rear_y = (gy["3"] + P["walls"]["hall_thickness"] / 2 + self.rows[-1]["yb"]) / 2
        xw0, xw1 = gx["B"], gx["G"]
        stair_x = [s["x_top"] for s in self.stairs]
        nf = S["front_rows"]
        # second leg (hall exit -> external door), plan distance along defined routes
        amb_mid = 2.25  # half ambulatory width
        main_doors = [(gx[a] + gx[b]) / 2 for a, b in P["foyer"]["main_door_bays"]]

        def leg2(ex):
            if ex["role"].startswith("Hall exit - front") or ex["role"].startswith("Hall exit - platform"):
                return 4.5, "ambulatory crossing to opposite external door"
            if "cross aisle" in ex["role"]:
                return 4.5 + P["doors"]["cross_aisle_external"]["landing"], "ambulatory landing to external door + external steps"
            # rear: across upper foyer to nearest stair top, down stair (plan run), to nearest main door
            xs = min(stair_x, key=lambda sx: abs(sx - ex["x"]))
            stair_plan = self.stairs[0]["x1"] - self.stairs[0]["x0"]
            xd = min(main_doors, key=lambda dx: abs(dx - (xs - stair_plan)))
            return (abs(ex["x"] - xs) + (gy["3"] - P["foyer"]["mezzanine_y"][0]) + stair_plan
                    + abs(xs - stair_plan - xd) + P["foyer"]["mezzanine_y"][0] - P["foyer"]["stair_width"] / 2,
                    "upper foyer -> stair -> main doors")

        exits = self.exits
        for ex in exits:
            ex["leg2"], ex["leg2_route"] = leg2(ex)
            ex["load"] = 0
        occupants = []
        for s in self.seats:
            occupants.append((s["x"], s["y"], s["row"], s["section"], s["seat_id"]))
        for p in self.wc_positions:
            x, y = (p["x0"] + p["x1"]) / 2, (p["y0"] + p["y1"]) / 2
            sec = {"F": "frontzone", "M": "band", "R": "rearplat"}[p["group"][0]]
            occupants.append((x, y, 0, sec, p["name"]))
            occupants.append((x + 0.7, y, 0, sec, p["companion"]))
        results = []
        for x, y, r, sec, oid in occupants:
            if sec in ("front", "rear"):
                rw = self.rows[r - 1]
                edges = [e for b in rw["blocks"] for e in b]
                xa = min(edges, key=lambda e: abs(e - x))
                # aisle centreline beside the nearest block edge
                cands = [(a0 + a1) / 2 for a0, a1 in rw["aisles"]] + [(xw0 + 0.3 + rw["blocks"][0][0]) / 2,
                                                                       (rw["blocks"][-1][1] + xw1 - 0.3) / 2]
                ax = min(cands, key=lambda c: abs(c - xa))
                dx0 = abs(x - ax)
            else:
                ax, dx0 = x, 0.0
            cands = []
            for ei, ex in enumerate(exits):
                role = ex["role"]
                if "front zone" in role or "platform wing" in role:
                    if sec in ("rear", "rearplat"):
                        continue
                    ry = front_route_y
                elif "cross aisle" in role:
                    if sec == "rearplat":
                        continue
                    ry = cross_y
                else:  # rear doors
                    if sec in ("front", "frontzone"):
                        continue
                    ry = rear_y
                d = dx0 + abs(y - ry)
                if ex["wall"] in ("W", "E"):
                    d += abs(ax - ex["x"]) + abs(ry - ex["y"])
                else:
                    d += abs(ax - ex["x"]) + abs(ry - ex["y"])
                cands.append((d + ex["leg2"], d, ei))
            cands.sort()
            results.append({"occupant": oid, "cands": cands})
        other = E["choir_and_platform_occupants"]
        wing = [i for i, ex in enumerate(exits) if "platform wing" in ex["role"]]
        base = [0] * len(exits)
        for i in wing:  # platform / choir occupants assumed to use the wing doors equally (concept)
            base[i] += other // len(wing)
        # (1) nearest-exit loads: nearest = shortest in-hall plan travel to a hall exit door (one definition, used for
        #     loads, schedule column and travel metric). (1b) sensitivity: shortest route to an EXTERNAL door.
        nearest, route = list(base), list(base)
        for r in results:
            r["near"] = min(r["cands"], key=lambda c: c[1])
            nearest[r["near"][2]] += 1
            route[r["cands"][0][2]] += 1
        # (2) queue-balanced loads: occupants choose min(walk time + queue time) given others' choices.
        #     Placeholder speeds; a heuristic stand-in for proper evacuation modelling.
        v, flow = E["walk_speed_m_s"], E["door_flow_p_per_m_s"]
        choice = [r["near"][2] for r in results]
        loads = list(nearest)
        for _ in range(60):
            changed = 0
            for k, r in enumerate(results):
                cur = choice[k]
                loads[cur] -= 1
                best = min(r["cands"], key=lambda c: c[0] / v + (loads[c[2]] + 1) / (exits[c[2]]["width"] * flow))
                loads[best[2]] += 1
                if best[2] != cur:
                    choice[k] = best[2]
                    changed += 1
            if not changed:
                break
        lvl = E["level_width_mm_per_person"] / 1000.0
        stf = E["stair_width_mm_per_person"] / 1000.0
        for i, ex in enumerate(exits):
            ex["load_nearest"] = nearest[i]
            ex["load_route"] = route[i]
            ex["required_width_route"] = rnd(route[i] * lvl, 3)
            ex["load"] = loads[i]
            ex["required_width"] = rnd(ex["load"] * lvl, 3)
            ex["required_width_nearest"] = rnd(ex["load_nearest"] * lvl, 3)
            ex["ok"] = ex["width"] >= ex["required_width"]
        for k, r in enumerate(results):
            tot, d, ei = next(c for c in r["cands"] if c[2] == choice[k])
            r.update({"exit": exits[ei]["id"], "travel_hall": rnd(d, 2), "travel_total": rnd(tot, 2),
                      "nearest_exit": exits[r["near"][2]]["id"], "travel_hall_to_nearest_exit": rnd(r["near"][1], 2),
                      "shortest_route_exit": exits[r["cands"][0][2]]["id"]})
            del r["near"]
            del r["cands"]
        rear_load = sum(ex["load"] for ex in exits if ex["wall"] == "REAR")
        stair_w = sum(min(s["width"], s["opening"]) for s in self.stairs)  # stair-head opening governs if narrower
        stair_req = rear_load * stf
        self.metrics["egress"] = {
            "occupants_assigned_in_hall": len(occupants), "platform_choir_added": other,
            "total_hall_exit_width": rnd(sum(ex["width"] for ex in exits), 2),
            "total_required_width_placeholder": rnd(sum(ex["required_width"] for ex in exits), 2),
            "rear_load_to_upper_foyer": rear_load, "upper_foyer_stair_width": stair_w,
            "upper_foyer_stair_required_placeholder": rnd(stair_req, 2),
            "max_travel_hall": max(r["travel_hall"] for r in results),
            "max_travel_hall_to_nearest_exit": max(r["travel_hall_to_nearest_exit"] for r in results),
            "count_nearest_travel_over_flag": sum(r["travel_hall_to_nearest_exit"] > E["travel_flag_within_hall_m"] for r in results),
            "max_travel_total": max(r["travel_total"] for r in results),
            "count_travel_hall_over_flag": sum(r["travel_hall"] > E["travel_flag_within_hall_m"] for r in results),
            "count_travel_total_over_flag": sum(r["travel_total"] > E["travel_flag_total_m"] for r in results),
        }
        self.egress_results = results
        eg = self.metrics["egress"]
        self.check("EGR-01", "Each hall exit width >= placeholder demand (queue-balanced assignment)",
                   all(ex["ok"] for ex in exits), {ex["id"]: [ex["load"], ex["required_width"], rnd(ex["width"], 2)] for ex in exits},
                   "width >= load x 5 mm (placeholder)")
        self.check("EGR-01N", "Each hall exit width >= placeholder demand if everyone uses the NEAREST exit (shortest in-hall travel)",
                   all(ex["width"] >= ex["required_width_nearest"] for ex in exits),
                   {ex["id"]: [ex["load_nearest"], ex["required_width_nearest"], rnd(ex["width"], 2)] for ex in exits},
                   "width >= load x 5 mm (placeholder)")
        self.check("EGR-01R", "Sensitivity: exit width if everyone takes the shortest route to an EXTERNAL door",
                   all(ex["width"] >= ex["required_width_route"] for ex in exits),
                   {ex["id"]: [ex["load_route"], ex["required_width_route"], rnd(ex["width"], 2)] for ex in exits},
                   "width >= load x 5 mm (placeholder) - cross-aisle exits attract this route (OI-17)", "WARN")
        total_req = sum(ex["load"] for ex in exits) * lvl
        widths = sorted(ex["width"] for ex in exits)
        self.check("EGR-06", "Remaining exit width with the largest hall exit blocked",
                   sum(widths) - widths[-1] >= total_req, rnd(sum(widths) - widths[-1], 2),
                   f">= {rnd(total_req, 2)} m total placeholder demand")
        self.check("EGR-02", "Upper foyer stair capacity (min of stair width and stair-head rail opening) >= placeholder demand",
                   stair_w >= stair_req, rnd(stair_w, 2),
                   f">= {rnd(stair_req, 2)} m (rear load {rear_load} x 7.5 mm placeholder)")
        self.check("EGR-03N", "Max within-hall plan travel to the NEAREST hall exit",
                   eg["max_travel_hall_to_nearest_exit"] <= E["travel_flag_within_hall_m"],
                   {"max_m": eg["max_travel_hall_to_nearest_exit"], "occupants_over_flag": eg["count_nearest_travel_over_flag"]},
                   f"<= {E['travel_flag_within_hall_m']} m placeholder flag (OI-17)", "WARN")
        self.check("EGR-03", "Max within-hall plan travel to the queue-balanced hall exit", eg["max_travel_hall"] <= E["travel_flag_within_hall_m"],
                   eg["max_travel_hall"], f"<= {E['travel_flag_within_hall_m']} m placeholder flag", "WARN")
        self.check("EGR-04", "Max plan travel to an external door", eg["max_travel_total"] <= E["travel_flag_total_m"],
                   eg["max_travel_total"], f"<= {E['travel_flag_total_m']} m placeholder flag", "WARN")
        hall_exits = [ex for ex in exits]
        self.check("EGR-05", "Number of independent hall exits", len(hall_exits) >= 4, len(hall_exits), ">= 4 (placeholder)")

    # ---------------------------------------------------------------- analytic clash/coordination checks
    def analytic_checks(self):
        S = self.P["seating"]
        self.metrics["refuge_spaces_L02"] = len(self.refuges)
        self.check("ACC-05", "Refuge spaces on the upper level >= wheelchair spaces served only by the lift (L02)",
                   len(self.refuges) >= self.metrics["wheelchair_spaces_L02"],
                   {"refuges": len(self.refuges), "L02_wheelchair_spaces": self.metrics["wheelchair_spaces_L02"]}, "refuges >= L02 spaces")
        cols = [(c["x"] - c["size"] / 2, c["y"] - c["size"] / 2, c["x"] + c["size"] / 2, c["y"] + c["size"] / 2, c["grid"])
                for c in self.columns]
        doors = [e for e in self.elements if e.ifc_class == "IfcDoor"]
        bad = []
        for d in doors:
            o = d.opening
            for x0, y0, x1, y1, g in cols:
                if o[0] < x1 - 1e-6 and o[3] > x0 + 1e-6 and o[1] < y1 - 1e-6 and o[4] > y0 + 1e-6:
                    bad.append(f"{d.name}/{g}")
        self.check("CLS-01", "Door openings clear of columns (analytic)", not bad, bad or 0, "0 conflicts")
        # minimum aisle and wall-aisle clear widths across rows
        wa = []
        straight = S["aisle_width"] - S["stagger_offset"]
        _, _, (x_in0, x_in1) = self.block_ranges()
        for rw in self.rows:
            wa.append(rw["blocks"][0][0] - x_in0)
            wa.append(x_in1 - rw["blocks"][-1][1])
        self.metrics["wall_aisle_min"] = rnd(min(wa), 3)
        self.metrics["aisle_straight_clear"] = rnd(straight, 3)
        self.check("CIR-02", "Wall aisle min clear (to column face)", min(wa) >= 1.5, rnd(min(wa), 3), ">= 1.5 m concept")
        self.check("CIR-03", "Interior aisle straight clear path with stagger", straight >= 1.2, rnd(straight, 3), ">= 1.2 m concept")
        max_to_aisle = max(max(math.ceil(n / 2), 0) for n in S["blocks"][1:-1])
        side = max(S["blocks"][0], S["blocks"][-1])
        self.metrics["max_seats_to_aisle"] = max(max_to_aisle, math.ceil(side / 2))
        self.check("CIR-04", "Max seats from any seat to an aisle", self.metrics["max_seats_to_aisle"] <= 7,
                   self.metrics["max_seats_to_aisle"], "<= 7 (both block ends open to an aisle)")
        cmin1 = min(rw["c_n1"] for rw in self.rows if rw["c_n1"] is not None)
        cmin2 = min(rw["c_n2"] for rw in self.rows if rw["c_n2"] is not None)
        self.metrics["c_min_n1"], self.metrics["c_min_n2"] = cmin1, cmin2
        self.check("SGT-01", "Min C-value over row in front (all rows)", cmin1 >= self.P["sightlines"]["c_value_target"] - 1e-6,
                   cmin1, f">= {self.P['sightlines']['c_value_target']} m")
        self.check("SGT-02", "Min C-value over 2 rows in front (staggered seating)",
                   cmin2 >= self.P["sightlines"]["c_value_staggered_target_n2"] - 1e-6, cmin2,
                   f">= {self.P['sightlines']['c_value_staggered_target_n2']} m", "WARN")
        for k, v in self.sight_extra.items():
            self.check(f"SGT-{k.upper()}", f"C-value for {k.replace('_', ' ')}", v["c_n1"] >= self.P["sightlines"]["c_value_target"] - 1e-6,
                       v["c_n1"], f">= {self.P['sightlines']['c_value_target']} m")
        dmax = max(rw["eye_distance"] for rw in self.rows)
        self.metrics["max_viewing_distance_to_platform_edge"] = dmax

    # ---------------------------------------------------------------- balcony comparison (computed, not modelled)
    def balcony_option(self):
        B, S, ST = self.P["balcony_option"], self.P["seating"], self.P["stage"]
        per_row = sum(S["blocks"])
        floor_rows = math.ceil(B["floor_seats"] / per_row)
        fz = ST["front_clear_zone"]
        d_floor = fz + floor_rows * S["row_pitch"] + S["cross_aisle_passage"] + S["wheelchair_band_depth"]
        bal_rows = B["balcony_rows"]
        bal_front_d = fz + B["balcony_front_over_floor_row"] * S["row_pitch"] + S["cross_aisle_passage"] + S["wheelchair_band_depth"]
        d_bal = bal_front_d + bal_rows * B["balcony_row_pitch"]
        a_rows = len(self.rows)
        # schematic section for option B: same sightline rules applied to a floor rake and a balcony rake
        SL = self.P["sightlines"]
        yf, zf = ST["front_edge_y"], ST["platform_height"] + SL["focal_height_above_platform"]
        eye, C = S["eye_height_seated"], SL["c_value_target"]
        y0 = yf - fz
        floor_pts, prev, f = [], None, 0.0
        for r in range(floor_rows):
            yb = y0 - (r + 1) * S["row_pitch"] - (S["cross_aisle_passage"] if r >= 18 else 0.0)
            d = yf - (yb + S["eye_offset_from_tread_back"])
            if prev:
                f = max(f, ceil_to((prev[0] + C) * d / prev[1] + zf - eye, SL["elevation_rounding"]))
            prev = (f + eye - zf, d)
            floor_pts.append((rnd(yb, 3), rnd(f, 3)))
        y_bal_front = floor_pts[B["balcony_front_over_floor_row"] - 1][0]
        h = B["balcony_floor_level"]
        bal_pts, prev = [], (h + B["parapet_height"] - zf, yf - y_bal_front)  # first row must see over the parapet
        f = h
        for r in range(bal_rows):
            yb = y_bal_front - (r + 1) * B["balcony_row_pitch"]
            d = yf - (yb + S["eye_offset_from_tread_back"])
            f = max(f, ceil_to((prev[0] + C) * d / prev[1] + zf - eye, SL["elevation_rounding"]))
            prev = (f + eye - zf, d)
            bal_pts.append((rnd(yb, 3), rnd(f, 3)))
        rise = bal_pts[-1][1] - h
        run = y_bal_front - bal_pts[-1][0]
        rake_deg = math.degrees(math.atan2(rise, run))
        # rear floor row under the overhang: line from its eye to a target 2.5 m above the platform edge
        yr, fr = floor_pts[-1]
        ye, ze = yr + S["eye_offset_from_tread_back"], fr + eye
        zt = ST["platform_height"] + B["view_target_above_platform"]
        z_at_front = ze + (zt - ze) * (y_bal_front - ye) / (yf - ye)
        soffit = h - B["soffit_depth"]
        overhang = y_bal_front - yr
        self.balcony = {"floor": floor_pts, "balcony": bal_pts, "y_front": y_bal_front, "soffit": soffit,
                        "focal": (yf, zf), "target": (yf, zt), "rear_eye": (ye, ze)}
        bal_metrics = {"balcony_rake_deg": rnd(rake_deg, 1), "balcony_top_floor": bal_pts[-1][1],
                       "rear_floor_row_view_clearance_below_soffit_m": rnd(soffit - z_at_front, 2),
                       "overhang_depth_m": rnd(overhang, 2), "opening_height_m": rnd(soffit - fr, 2),
                       "overhang_depth_to_height": rnd(overhang / (soffit - fr), 2)}
        self.metrics["options"] = {
            "A_single_level": {"rows": a_rows, "max_eye_distance_m": self.metrics["max_viewing_distance_to_platform_edge"],
                               "hall_depth_m": rnd(self.P["stage"]["front_edge_y"] - self.gy["3"], 2),
                               "vertical_egress": "Rear 1,000-1,600 occupants via upper-foyer stairs (rear platform +%.2f m)" % self.top_level,
                               "structure": "Single-storey long-span roof only; no suspended seating structure"},
            "B_floor_plus_balcony": {"floor_rows": floor_rows, "balcony_rows": bal_rows,
                                     "approx_max_floor_distance_m": rnd(d_floor, 1), "approx_max_balcony_distance_m": rnd(d_bal, 1),
                                     "approx_hall_depth_saving_m": rnd((a_rows - floor_rows) * S["row_pitch"] - 0.0, 1),
                                     "balcony_overhang_rows": max(0, floor_rows - B["balcony_front_over_floor_row"]),
                                     "vertical_egress": f"{B['balcony_seats']} occupants via protected stairs from +{B['balcony_floor_level']} m; lifts mandatory for access",
                                     "structure": "Suspended/cantilevered balcony (vibration, back-span, transfer structure) + increased column count",
                                     **bal_metrics},
        }

    # ---------------------------------------------------------------- driver
    def run(self):
        self.build_rows()
        self.build_seats()
        self.build_rake()
        self.build_accessible_positions()
        self.build_stage()
        self.build_walls()
        self.build_floors_circulation()
        self.build_structure()
        self.build_roofs()
        self.build_spaces()
        self.assign_storeys()
        self.egress()
        self.analytic_checks()
        self.balcony_option()
        return self

    def levels(self):
        """Storey datums. L03-L05 are structural datums (underside of the framing they contain)."""
        P = self.P
        st = P["structure"]
        low = min(P["ambulatory"]["roof_top"], P["back_of_house"]["roof_top"]) - st["roof_build_up"] - st["low_roof_beam_depth"]
        foy = P["foyer"]["roof_top"] - st["roof_build_up"] - st["foyer_roof_beam_depth"]
        hall = st["truss_bearing_z"] - st["eaves_tie_depth"]
        return [
            {"id": "L00", "name": "Level 00 - datum +0.000 (ground floor, front of hall)", "elevation": 0.0},
            {"id": "L01", "name": f"Level 01 - datum +{self.cross_level:.3f} (cross aisle, rear rake, framing below upper foyer)", "elevation": self.cross_level},
            {"id": "L02", "name": f"Level 02 - datum +{self.top_level:.3f} (upper foyer, rear platform)", "elevation": self.top_level},
            {"id": "L03", "name": f"Level 03 - datum +{low:.3f} (low-roof framing and items above it)", "elevation": rnd(low, 3)},
            {"id": "L04", "name": f"Level 04 - datum +{foy:.3f} (foyer-roof framing, high-level allowances)", "elevation": rnd(foy, 3)},
            {"id": "L05", "name": f"Level 05 - datum +{hall:.3f} (hall roof structure)", "elevation": rnd(hall, 3)},
        ]

    @staticmethod
    def storey_ref_z(ifc_class, predefined, base_z, top_z):
        """Reference height for storey assignment: walking surface (top) for floor slabs, else base."""
        if ifc_class == "IfcSlab" and predefined in ("FLOOR", "LANDING"):
            return top_z
        return base_z

    @staticmethod
    def storey_for(levels, z):
        cur = levels[0]["id"]
        for lv in sorted(levels, key=lambda l: l["elevation"]):
            if z >= lv["elevation"] - 0.01:
                cur = lv["id"]
        return cur

    def assign_storeys(self):
        """Each element goes to the highest storey whose datum is at or below its reference height
        (footings -> L00). Explicit overrides carry a reason in StoreyOverride and are re-checked in IFC validation."""
        lv = self.levels()
        ev = [l["elevation"] for l in sorted(lv, key=lambda l: l["elevation"])]
        if any(b - a < 0.05 for a, b in zip(ev, ev[1:])):
            raise RuntimeError(f"storey datums too close or out of order: {ev}")
        overrides = 0
        for e in self.elements:
            if e.ifc_class == "IfcFooting":
                e.storey = "L00"
                continue
            if "StoreyOverride" in e.props:
                e.storey = e.props["StoreyOverride"].split(":")[0]
                overrides += 1
                continue
            if e.mesh_key:
                z0 = z1 = e.origin[2]
            else:
                bb = e.aabb()
                z0, z1 = bb[2], bb[5]
            e.storey = self.storey_for(lv, self.storey_ref_z(e.ifc_class, e.predefined, z0, z1))
        counts = {}
        for e in self.elements:
            counts[e.storey] = counts.get(e.storey, 0) + 1
        self.metrics["elements_per_storey"] = dict(sorted(counts.items()))
        self.metrics["storey_overrides"] = overrides
        self.check("BIM-01", "Every storey contains elements (no empty levels)", all(counts.get(l["id"]) for l in lv),
                   self.metrics["elements_per_storey"], "> 0 per storey")


def compute(P=None):
    P = P or load_params()
    lay = Layout(P).run()
    return lay


def element_counts(elements):
    out = {}
    for e in elements:
        key = f"{e.ifc_class}:{e.predefined or ''}"
        out[key] = out.get(key, 0) + 1
    return dict(sorted(out.items()))


if __name__ == "__main__":
    lay = compute()
    print("seats", len(lay.seats), "elements", len(lay.elements))
    print(json.dumps(lay.metrics, indent=1, default=str)[:4000])
    for c in lay.checks:
        print(c["result"], c["id"], c["description"], c["value"] if not isinstance(c["value"], dict) else "...")
