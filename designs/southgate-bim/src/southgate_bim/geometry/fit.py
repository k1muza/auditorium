"""Pure-numpy geometry recognition for source meshes.

The migration only builds a parametric (swept-solid) IFC representation when the
source mesh is *proven* to be that shape:

* ``fit_prism``  - the mesh is a right prism: two congruent planar caps joined by
  parallel lateral edges of equal length.  Returns the cap loop, the extrusion
  direction and the depth.  Boxes, plates, steel sections (L, C, I, double-angle)
  and most masonry pieces are prisms.
* ``fit_box``    - a prism whose cap is a rectangle; returns three orthogonal edge
  vectors from one corner.

Anything that fails these tests stays a tessellated mesh (custom IFC geometry).
All functions work in world coordinates (metres).
"""
from __future__ import annotations

from dataclasses import dataclass
import numpy as np

TOL = 1e-4


@dataclass
class Prism:
    direction: np.ndarray        # unit extrusion direction
    depth: float                 # extrusion length (m)
    base_loop: np.ndarray        # (n,3) ordered cap vertices (world) at the base
    n_lateral: int
    holes: list = None
    clip_start: tuple = None      # (point, outward normal) of an oblique start cap
    clip_end: tuple = None
    deviation: float = 0.0        # max lateral-edge skew from the sweep axis (m)

    @property
    def cap_area(self) -> float:
        a = polygon_area_3d(self.base_loop, self.direction)
        return a - sum(polygon_area_3d(h, self.direction) for h in (self.holes or []))

    @property
    def volume(self) -> float:
        return self.cap_area * self.depth


@dataclass
class Box:
    origin: np.ndarray           # one corner
    edges: np.ndarray            # (3,3) edge vectors from origin (orthogonal)

    @property
    def dims(self):
        return np.linalg.norm(self.edges, axis=1)

    @property
    def volume(self):
        return float(np.prod(self.dims))

    @property
    def centre(self):
        return self.origin + self.edges.sum(axis=0) / 2


def world_vertices(verts_local: np.ndarray, matrix: np.ndarray) -> np.ndarray:
    v = np.c_[verts_local, np.ones(len(verts_local))]
    return (v @ np.asarray(matrix).T)[:, :3]


def edges_from_faces(faces) -> np.ndarray:
    s = set()
    for f in faces:
        n = len(f)
        for i in range(n):
            a, b = f[i], f[(i + 1) % n]
            s.add((a, b) if a < b else (b, a))
    return np.array(sorted(s), dtype=np.int64).reshape(-1, 2)


def polygon_area_3d(loop: np.ndarray, normal: np.ndarray) -> float:
    n = normal / np.linalg.norm(normal)
    s = np.zeros(3)
    for i in range(len(loop)):
        s += np.cross(loop[i], loop[(i + 1) % len(loop)])
    return abs(float(np.dot(s, n))) / 2.0


def _weld(verts: np.ndarray, faces, tol=1e-5):
    """Merge coincident vertices (exported meshes are sometimes split)."""
    key = np.round(verts / tol).astype(np.int64)
    _, idx, inv = np.unique(key, axis=0, return_index=True, return_inverse=True)
    inv = inv.reshape(-1)
    nv = verts[idx]
    nf = []
    for f in faces:
        g = []
        for i in f:
            j = int(inv[i])
            if not g or g[-1] != j:
                g.append(j)
        if len(g) > 1 and g[0] == g[-1]:
            g.pop()
        if len(g) >= 3:
            nf.append(tuple(g))
    return nv, nf


def _plane_fit(pts):
    c = pts.mean(axis=0)
    u, sv, vt = np.linalg.svd(pts - c)
    return c, vt[2], (sv[2] if len(sv) > 2 else 0.0)


def fit_prisms(verts: np.ndarray, faces, tol: float = TOL, max_verts: int = 400,
               par_tol: float = 1e-7, max_dev: float = 0.005):
    """Return every swept-solid interpretation of the mesh.

    A mesh qualifies when its vertices pair up through ``n/2`` parallel lateral
    edges (covering every vertex exactly once) and both end caps are planar loops.
    The cross-section is the cap projected onto the plane perpendicular to the
    lateral direction.  End caps that are not perpendicular to the direction are
    returned as clipping planes (mitred / plumb-cut members).  A box has three
    interpretations; the caller chooses.
    """
    verts, faces = _weld(np.asarray(verts, dtype=np.float64), faces)
    nv = len(verts)
    if nv < 6 or nv % 2 or nv > max_verts or not faces:
        return []
    E = edges_from_faces(faces)
    vec = verts[E[:, 1]] - verts[E[:, 0]]
    ln = np.linalg.norm(vec, axis=1)
    ok = ln > tol
    E, vec, ln = E[ok], vec[ok], ln[ok]
    unit = vec / ln[:, None]
    idx = np.argmax(np.abs(unit), axis=1)
    sgn = np.sign(unit[np.arange(len(unit)), idx])
    unit = unit * sgn[:, None]
    n_half = nv // 2
    scale = max(1.0, float(np.ptp(verts, axis=0).max()))
    ptol = 5e-4                       # absolute 0.5 mm: end-cap perpendicularity / planarity
    results, tried = [], []
    order = np.argsort(-ln)
    for i in order:
        d = unit[i]
        if any(abs(np.dot(d, t)) > 1 - 1e-9 for t in tried):
            continue
        tried.append(d)
        par = np.where(np.abs(unit @ d) > 1 - par_tol)[0]
        if len(par) != n_half:
            continue
        pe = E[par]
        used = np.bincount(pe.ravel(), minlength=nv)
        if not np.all(used == 1):
            continue
        dev = 0.0
        if par_tol > 1e-7:                       # relaxed pass: mean axis + measured skew
            uu = unit[par] * np.sign(unit[par] @ d)[:, None]
            d = uu.mean(axis=0)
            d /= np.linalg.norm(d)
            lv = verts[pe[:, 1]] - verts[pe[:, 0]]
            perp = lv - np.outer(lv @ d, d)
            dev = float(np.linalg.norm(perp, axis=1).max())
            if dev > max_dev:
                continue
        proj = verts @ d
        swap = proj[pe[:, 0]] > proj[pe[:, 1]]
        lo_end = np.where(swap, pe[:, 1], pe[:, 0])
        hi_end = np.where(swap, pe[:, 0], pe[:, 1])
        base = np.zeros(nv, bool); base[lo_end] = True
        top = np.zeros(nv, bool); top[hi_end] = True
        bnd = set()
        for f in faces:
            k = len(f)
            if any(base[v] for v in f) and any(top[v] for v in f):
                for j in range(k):
                    a_, b_ = f[j], f[(j + 1) % k]
                    if base[a_] and base[b_]:
                        bnd.add((min(a_, b_), max(a_, b_)))
        adj = {}
        for a_, b_ in bnd:
            adj.setdefault(a_, []).append(b_)
            adj.setdefault(b_, []).append(a_)
        if len(adj) != n_half or any(len(v) != 2 for v in adj.values()):
            continue
        cycles, seen = [], set()
        for start in adj:
            if start in seen:
                continue
            loop = [start]; seen.add(start)
            prev, cur = None, start
            while True:
                nxt = adj[cur][0] if adj[cur][0] != prev else adj[cur][1]
                if nxt == start:
                    break
                if nxt in seen:
                    loop = None
                    break
                loop.append(nxt); seen.add(nxt)
                prev, cur = cur, nxt
            if loop is None or len(loop) < 3:
                cycles = None
                break
            cycles.append(loop)
        if not cycles:
            continue
        cA = verts[base]; cB = verts[top]
        pA, nA, rA = _plane_fit(cA)
        pB, nB, rB = _plane_fit(cB)
        if rA > ptol or rB > ptol or abs(np.dot(nA, d)) < 0.2 or abs(np.dot(nB, d)) < 0.2:
            continue
        s0 = float(proj[base].min()); s1 = float(proj[top].max())
        perpA = float(np.ptp(proj[base])) < ptol
        perpB = float(np.ptp(proj[top])) < ptol
        if (not perpA or not perpB) and proj[base].max() > proj[top].min() - ptol:
            continue
        loops = []
        for c in cycles:
            bl = verts[c] - np.outer(proj[c] - s0, d)
            sv = np.zeros(3)
            for j in range(len(bl)):
                sv += np.cross(bl[j], bl[(j + 1) % len(bl)])
            loops.append((abs(float(np.dot(sv, d))) / 2, bl if np.dot(sv, d) >= 0 else bl[::-1]))
        loops.sort(key=lambda t: -t[0])
        outer = loops[0][1]
        holes = [lp[::-1] for _, lp in loops[1:]]
        clipA = None if perpA else (pA, (-nA if np.dot(nA, d) > 0 else nA))
        clipB = None if perpB else (pB, (nB if np.dot(nB, d) > 0 else -nB))
        results.append(Prism(direction=d, depth=s1 - s0, base_loop=outer, n_lateral=n_half, holes=holes,
                             clip_start=clipA, clip_end=clipB, deviation=dev))
    return results


def simplify_loop(loop: np.ndarray, tol: float = 1e-6) -> np.ndarray:
    """Drop collinear vertices from a closed loop."""
    pts = list(loop)
    changed = True
    while changed and len(pts) > 3:
        changed = False
        for i in range(len(pts)):
            a, b, c = pts[i - 1], pts[i], pts[(i + 1) % len(pts)]
            if np.linalg.norm(np.cross(b - a, c - b)) < tol * max(1e-9, np.linalg.norm(c - a)):
                pts.pop(i)
                changed = True
                break
    return np.array(pts)


def fit_box(verts: np.ndarray, faces, tol: float = TOL) -> Box | None:
    """A mesh is a box if it is a prism with a rectangular (4-vertex) cap."""
    for p in fit_prisms(verts, faces, tol):
        if p.holes or p.clip_start is not None or p.clip_end is not None:
            continue
        loop = simplify_loop(p.base_loop)
        if len(loop) != 4:
            continue
        a = loop[1] - loop[0]
        b = loop[3] - loop[0]
        if abs(np.dot(a, b)) > 1e-4 * np.linalg.norm(a) * np.linalg.norm(b):
            continue
        if np.linalg.norm(loop[0] + a + b - loop[2]) > 1e-3:
            continue
        if abs(np.dot(a, p.direction)) > 1e-4 * np.linalg.norm(a):
            continue
        return Box(origin=loop[0], edges=np.array([a, b, p.direction * p.depth]))
    return None


def mesh_volume(verts: np.ndarray, faces) -> float:
    """Signed-volume (divergence theorem) for a closed mesh; abs value returned."""
    v = 0.0
    for f in faces:
        p0 = verts[f[0]]
        for i in range(1, len(f) - 1):
            v += np.dot(p0, np.cross(verts[f[i]], verts[f[i + 1]]))
    return abs(v) / 6.0


def mesh_area(verts: np.ndarray, faces) -> float:
    a = 0.0
    for f in faces:
        p0 = verts[f[0]]
        for i in range(1, len(f) - 1):
            a += np.linalg.norm(np.cross(verts[f[i]] - p0, verts[f[i + 1]] - p0)) / 2
    return a


def connected_components(nverts: int, faces) -> int:
    parent = list(range(nverts))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for f in faces:
        r = find(f[0])
        for v in f[1:]:
            rv = find(v)
            if rv != r:
                parent[rv] = r
    used = {v for f in faces for v in f}
    return len({find(v) for v in used})


def frame_from_axes(z: np.ndarray, x_hint: np.ndarray | None = None):
    """Right-handed orthonormal frame with Z = z, X as close as possible to x_hint."""
    z = z / np.linalg.norm(z)
    if x_hint is None or abs(np.dot(x_hint / np.linalg.norm(x_hint), z)) > 0.999:
        x_hint = np.array([1.0, 0, 0]) if abs(z[0]) < 0.9 else np.array([0, 1.0, 0])
    x = x_hint - np.dot(x_hint, z) * z
    x /= np.linalg.norm(x)
    y = np.cross(z, x)
    return x, y, z


def split_components(faces):
    """Group face indices by connected vertex sets."""
    parent = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for f in faces:
        r = find(f[0])
        for v in f[1:]:
            rv = find(v)
            if rv != r:
                parent[rv] = r
    comps = {}
    for i, f in enumerate(faces):
        comps.setdefault(find(f[0]), []).append(i)
    return list(comps.values())


def analyse(verts: np.ndarray, faces, max_components: int = 12) -> dict:
    """Classify a world-space mesh as box | prism | multiprism | mesh.

    multiprism: every connected component is a prism and all share one
    extrusion direction and depth (e.g. back-to-back double angles).
    """
    verts = np.asarray(verts, dtype=np.float64)
    out = {"kind": "mesh", "nverts": len(verts), "nfaces": len(faces)}
    if not faces or len(verts) < 6:
        return out
    comps = split_components(faces)
    out["components"] = len(comps)
    if len(comps) == 1:
        b = fit_box(verts, faces)
        if b is not None:
            out.update(kind="box", origin=b.origin, edges=b.edges)
            return out
        ps = fit_prisms(verts, faces) or fit_prisms(verts, faces, par_tol=2e-5)
        if ps:
            p = max(ps, key=lambda p: (p.clip_start is None and p.clip_end is None, p.depth))
            out.update(kind="prism", direction=p.direction, depth=p.depth,
                       loops=[simplify_loop(p.base_loop)], holes=[simplify_loop(h) for h in (p.holes or [])],
                       clips=[p.clip_start, p.clip_end], deviation=p.deviation,
                       all_dirs=[q.direction for q in ps])
        return out
    if len(comps) > max_components:
        return out
    per = []
    for fidx in comps:
        cf = [faces[i] for i in fidx]
        used = sorted({v for f in cf for v in f})
        remap = {v: i for i, v in enumerate(used)}
        cv = verts[used]
        cf2 = [tuple(remap[v] for v in f) for f in cf]
        ps = [q for q in (fit_prisms(cv, cf2) or fit_prisms(cv, cf2, par_tol=2e-5)) if not q.holes]
        if not ps:
            return out
        per.append(ps)
    for p0 in per[0]:
        d = p0.direction
        chosen = [p0]
        for ps in per[1:]:
            m = [q for q in ps if abs(abs(np.dot(q.direction, d)) - 1) < 2e-5]
            if not m:
                break
            chosen.append(m[0])
        if len(chosen) == len(per):
            parts = []
            for c in chosen:
                if np.dot(c.direction, d) < 0:
                    lp = (c.base_loop + c.direction * c.depth)[::-1]
                    clips = [c.clip_end, c.clip_start]
                else:
                    lp, clips = c.base_loop, [c.clip_start, c.clip_end]
                parts.append({"loop": simplify_loop(lp), "depth": c.depth, "clips": clips,
                              "direction": c.direction if np.dot(c.direction, d) > 0 else -c.direction})
            out.update(kind="multiprism", direction=d, parts=parts,
                       deviation=max(c.deviation for c in chosen))
            return out
    return out
    return out


def oriented_faces(faces):
    """Re-orient polygon faces consistently (BFS over shared edges).

    Returns (faces, closed) where closed is True when every edge is shared by
    exactly two faces.  Needed because several source meshes have flipped faces,
    which corrupts signed-volume integration.
    """
    faces = [list(f) for f in faces]
    edge_faces = {}
    for i, f in enumerate(faces):
        for j in range(len(f)):
            a, b = f[j], f[(j + 1) % len(f)]
            edge_faces.setdefault((min(a, b), max(a, b)), []).append(i)
    closed = all(len(v) == 2 for v in edge_faces.values())
    done = [False] * len(faces)
    for s in range(len(faces)):
        if done[s]:
            continue
        done[s] = True
        stack = [s]
        while stack:
            i = stack.pop()
            f = faces[i]
            for j in range(len(f)):
                a, b = f[j], f[(j + 1) % len(f)]
                for k in edge_faces[(min(a, b), max(a, b))]:
                    if k == i or done[k]:
                        continue
                    g = faces[k]
                    # consistent neighbour traverses the shared edge as b->a
                    same = any(g[t] == a and g[(t + 1) % len(g)] == b for t in range(len(g)))
                    if same:
                        faces[k] = g[::-1]
                    done[k] = True
                    stack.append(k)
    return faces, closed


def robust_volume(verts, faces):
    """Volume of a closed mesh after consistent re-orientation (per connected shell); None if open."""
    verts, faces = _weld(np.asarray(verts, float), faces)
    total = 0.0
    for comp in split_components(faces):
        cf = [faces[i] for i in comp]
        of, closed = oriented_faces(cf)
        if not closed:
            return None
        v = 0.0
        for f in of:
            p0 = verts[f[0]]
            for i in range(1, len(f) - 1):
                v += np.dot(p0, np.cross(verts[f[i]], verts[f[i + 1]]))
        total += abs(v) / 6.0
    return total
