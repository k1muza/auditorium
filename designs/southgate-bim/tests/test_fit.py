import numpy as np
from southgate_bim.geometry import fit


def box_mesh(dx, dy, dz, rot_deg=0.0, tri=False):
    v = np.array([[x, y, z] for z in (0, dz) for y in (0, dy) for x in (0, dx)], float)
    q = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    f = [t for a, b, c, d in q for t in ((a, b, c), (a, c, d))] if tri else q
    a = np.radians(rot_deg)
    R = np.array([[np.cos(a), -np.sin(a), 0], [np.sin(a), np.cos(a), 0], [0, 0, 1]])
    return v @ R.T + [5, 6, 7], f


def test_box_axis_and_rotated():
    for rot in (0, 33):
        for tri in (False, True):
            v, f = box_mesh(4.0, 0.3, 2.7, rot, tri)
            b = fit.fit_box(v, f)
            assert b is not None
            assert np.allclose(sorted(b.dims), sorted([4.0, 0.3, 2.7]), atol=1e-6)
            assert abs(b.volume - 4.0 * 0.3 * 2.7) < 1e-9


def test_l_prism():
    # equal angle 100x100x10 extruded 2 m along x
    pts2 = [(0, 0), (0.1, 0), (0.1, 0.01), (0.01, 0.01), (0.01, 0.1), (0, 0.1)]
    v = np.array([[x, y, z] for x in (0, 2.0) for (y, z) in pts2])
    n = 6
    f = [tuple(range(n))[::-1], tuple(range(n, 2 * n))]
    f += [(i, (i + 1) % n, n + (i + 1) % n, n + i) for i in range(n)]
    ps = fit.fit_prisms(v, f)
    assert len(ps) == 1
    p = ps[0]
    assert abs(p.depth - 2.0) < 1e-9
    assert abs(p.cap_area - (0.1 * 0.01 + 0.09 * 0.01)) < 1e-9
    assert abs(p.volume - fit.mesh_volume(v, f)) < 1e-9
    assert fit.fit_box(v, f) is None


def test_non_prism_rejected():
    v = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1]], float)
    f = [(0, 2, 1), (0, 1, 3), (1, 2, 3), (0, 3, 2)]
    assert fit.fit_prisms(v, f) == []
    assert fit.fit_box(v, f) is None


def test_components():
    v1, f1 = box_mesh(1, 1, 1)
    v2, f2 = box_mesh(1, 1, 1)
    v = np.r_[v1, v2 + 5]
    f = f1 + [tuple(i + 8 for i in q) for q in f2]
    assert fit.connected_components(len(v), f) == 2


def test_prism_with_hole():
    # 4x3 wall panel, 0.3 thick, with a 1x1 hole, built as a quad-strip mesh
    o = [(0, 0), (4, 0), (4, 3), (0, 3)]
    h = [(1, 1), (2, 1), (2, 2), (1, 2)]
    pts = o + h
    v = np.array([[x, y0, z] for y0 in (0.0, 0.3) for (x, z) in pts])
    n = 8
    f = []
    for ring in ((0, 1, 2, 3), (4, 5, 6, 7)):
        for i in range(4):
            a, b = ring[i], ring[(i + 1) % 4]
            f.append((a, b, n + b, n + a))
    # cap triangulation (outer ring + hole bridged) on both sides
    cap = [(0, 1, 5), (0, 5, 4), (1, 2, 6), (1, 6, 5), (2, 3, 7), (2, 7, 6), (3, 0, 4), (3, 4, 7)]
    f += cap + [tuple(i + n for i in t[::-1]) for t in cap]
    ps = fit.fit_prisms(v, f)
    assert ps and any(p.holes for p in ps)
    p = next(p for p in ps if p.holes)
    assert abs(p.cap_area - (12 - 1)) < 1e-9
    assert abs(p.depth - 0.3) < 1e-9


def test_robust_volume_with_flipped_faces():
    v, f = box_mesh(2.8, 0.3, 9.735)
    f = list(f)
    f[1] = f[1][::-1]          # flip one face (as found in the source)
    f[3] = f[3][::-1]
    assert abs(fit.robust_volume(v, f) - 2.8 * 0.3 * 9.735) < 1e-9
    assert fit.robust_volume(v, f[:-1]) is None      # open mesh
