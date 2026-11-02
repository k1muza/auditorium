"""Geometry primitives and the Element model shared by every design's layout engine.

Extracted unchanged from designs/A-end-stage/scripts/auditorium_layout.py (PL08-590d273e35, lines 27-208).
Option A keeps its own frozen copy so its revision ID does not change; new designs import this module.
Pure Python (no bpy / numpy): runs under Blender's Python and the project venv. Units: metres.
"""
from __future__ import annotations

import json
import math
from pathlib import Path


def load_params(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))

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


def strut_frame(p0, p1):
    """Orthonormal frame (u along the member, s = width axis, t = depth axis) used for strut meshes and distances."""
    u = _norm(_sub(p1, p0))
    ref = (0.0, 0.0, 1.0) if abs(u[2]) < 0.95 else (0.0, 1.0, 0.0)
    s = _norm(_cross(u, ref))
    t = _cross(u, s)
    if abs(u[2]) >= 0.95:
        s, t = t, _cross(u, t)
        s = _norm(s)
        t = _norm(_cross(u, s))
    return u, s, t


def dist_point_strut(p, p0, p1, w, h):
    """Distance from point p to the (oriented) box of a strut member; 0 if inside."""
    u, s, t = strut_frame(p0, p1)
    d = _sub(p, p0)
    length = math.sqrt(sum(c * c for c in _sub(p1, p0)))
    a = sum(d[i] * u[i] for i in range(3))
    along = max(0.0, -a, a - length)
    ds = max(0.0, abs(sum(d[i] * s[i] for i in range(3))) - w / 2)
    dt = max(0.0, abs(sum(d[i] * t[i] for i in range(3))) - h / 2)
    return math.sqrt(along * along + ds * ds + dt * dt)


def dist_point_aabb(p, bb):
    return math.sqrt(sum(max(0.0, bb[i] - p[i], p[i] - bb[i + 3]) ** 2 for i in range(3)))


def rect_minus(outer, holes):
    """Rectangle (x0,y0,x1,y1) minus rectangular holes -> list of rectangles (grid decomposition, merged along x)."""
    xs = sorted({outer[0], outer[2], *[min(max(h[k], outer[0]), outer[2]) for h in holes for k in (0, 2)]})
    ys = sorted({outer[1], outer[3], *[min(max(h[k], outer[1]), outer[3]) for h in holes for k in (1, 3)]})
    out = []
    for y0, y1 in zip(ys, ys[1:]):
        run = None
        for x0, x1 in zip(xs, xs[1:]):
            cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
            inside = any(h[0] < cx < h[2] and h[1] < cy < h[3] for h in holes)
            if not inside and x1 - x0 > 1e-6 and y1 - y0 > 1e-6:
                run = [run[0], y0, x1, y1] if run else [x0, y0, x1, y1]
            elif run:
                out.append(tuple(run))
                run = None
        if run:
            out.append(tuple(run))
    return out


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
        u, s, t = strut_frame(p0, p1)
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
    if kind == "prism_xy":  # convex plan polygon (counter-clockwise) extruded from z0 to z1 (shared-module addition)
        poly, z0, z1 = part[1]
        n = len(poly)
        v = [(x, y, z0) for x, y in poly] + [(x, y, z1) for x, y in poly]
        faces = [tuple(range(n - 1, -1, -1)), tuple(range(n, 2 * n))]
        for i in range(n):
            j = (i + 1) % n
            faces.append((i, j, n + j, n + i))
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
    """World AABB of an instanced chair (any rotation about Z; exact for multiples of 90 degrees)."""
    x, y, z = el.origin
    c, s = abs(math.cos(math.radians(el.rot_z))), abs(math.sin(math.radians(el.rot_z)))
    hw, hd = rnd(c * CHAIR_HALF_W + s * CHAIR_HALF_D, 9), rnd(s * CHAIR_HALF_W + c * CHAIR_HALF_D, 9)
    return (x - hw, y - hd, z, x + hw, y + hd, z + CHAIR_H)


