"""Linear-elastic 3D frame solver with geometric stiffness (elastic critical load factor).

Study tool for the Option B support-structure optimisation. NOT a validated commercial FE package:
- 2-node Euler-Bernoulli beam elements (12 DOF), axial-only bar elements, zero-length translational springs.
- End-moment releases by static condensation.
- Geometric stiffness (consistent, without torsional/warping terms) for the elastic critical load factor
  alpha_cr by inverse power iteration on K^-1 Kg.
Units: kN, m. Verified against closed-form results in scripts/hand_checks.py (cantilever, propped beam,
simple truss, Euler column).
"""
from __future__ import annotations
import math
from dataclasses import dataclass, field
import numpy as np

E_STEEL = 200e6     # kN/m2
G_STEEL = 77e6


@dataclass
class Prop:
    name: str
    A: float            # m2
    Iy: float = 0.0     # m4, about local y (bending in local x-z plane)
    Iz: float = 0.0     # m4, about local z (bending in local x-y plane)
    J: float = 1e-8     # m4
    kg_m: float = 0.0
    E: float = E_STEEL
    G: float = G_STEEL


@dataclass
class Elem:
    n1: int
    n2: int
    prop: Prop
    kind: str = "beam"          # 'beam' | 'bar' | 'spring'
    group: str = ""
    ref: tuple = (0.0, 0.0, 1.0)  # vector defining local z (component normal to the member axis)
    release: tuple = ()          # local DOF indices (0..11) released (moments: 3,4,5 at end1; 9,10,11 at end2)
    k6: tuple = ()               # spring: (kx, ky, kz, krx, kry, krz) global
    tag: dict = field(default_factory=dict)


class Model:
    def __init__(self):
        self.xyz: list[tuple[float, float, float]] = []
        self.ntag: list[str] = []
        self.elems: list[Elem] = []
        self.sup: dict[int, tuple] = {}
        self._idx: dict = {}

    def node(self, x, y, z, tag="", tol=1e-4):
        key = (round(x / tol), round(y / tol), round(z / tol))
        if key in self._idx:
            return self._idx[key]
        self.xyz.append((float(x), float(y), float(z)))
        self.ntag.append(tag)
        self._idx[key] = len(self.xyz) - 1
        return self._idx[key]

    def add(self, *a, **k):
        e = Elem(*a, **k)
        self.elems.append(e)
        return e

    def support(self, n, flags):
        self.sup[n] = tuple(bool(f) for f in flags)

    # ------------------------------------------------------------------ element matrices
    def _T(self, e):
        p1, p2 = np.array(self.xyz[e.n1]), np.array(self.xyz[e.n2])
        d = p2 - p1
        L = float(np.linalg.norm(d))
        ex = d / L
        r = np.array(e.ref, float)
        if abs(np.dot(r, ex)) > 0.999 * np.linalg.norm(r):
            r = np.array([1.0, 0, 0]) if abs(ex[0]) < 0.9 else np.array([0, 1.0, 0])
        ez = r - np.dot(r, ex) * ex
        ez /= np.linalg.norm(ez)
        ey = np.cross(ez, ex)
        lam = np.vstack([ex, ey, ez])
        T = np.zeros((12, 12))
        for i in range(4):
            T[3 * i:3 * i + 3, 3 * i:3 * i + 3] = lam
        return T, L

    @staticmethod
    def _kl(p: Prop, L, kind):
        k = np.zeros((12, 12))
        EA = p.E * p.A / L
        k[0, 0] = k[6, 6] = EA
        k[0, 6] = k[6, 0] = -EA
        if kind == "bar":
            return k
        GJ = p.G * p.J / L
        k[3, 3] = k[9, 9] = GJ
        k[3, 9] = k[9, 3] = -GJ
        # bending in local x-y plane (v, rz) uses Iz
        for (v1, r1, v2, r2, I, s) in ((1, 5, 7, 11, p.Iz, 1.0), (2, 4, 8, 10, p.Iy, -1.0)):
            EI = p.E * I
            a, b, c = 12 * EI / L ** 3, 6 * EI / L ** 2, EI / L
            k[v1, v1] = k[v2, v2] = a
            k[v1, v2] = k[v2, v1] = -a
            k[v1, r1] = k[r1, v1] = s * b
            k[v1, r2] = k[r2, v1] = s * b
            k[v2, r1] = k[r1, v2] = -s * b
            k[v2, r2] = k[r2, v2] = -s * b
            k[r1, r1] = k[r2, r2] = 4 * c
            k[r1, r2] = k[r2, r1] = 2 * c
        return k

    @staticmethod
    def _kg(N, L, kind):
        """Geometric stiffness, N tension positive."""
        g = np.zeros((12, 12))
        if kind == "bar":
            for a, b in ((1, 7), (2, 8)):
                g[a, a] = g[b, b] = N / L
                g[a, b] = g[b, a] = -N / L
            return g
        c = N / (30 * L)
        for (v1, r1, v2, r2, s) in ((1, 5, 7, 11, 1.0), (2, 4, 8, 10, -1.0)):
            g[v1, v1] = g[v2, v2] = 36 * c
            g[v1, v2] = g[v2, v1] = -36 * c
            g[v1, r1] = g[r1, v1] = s * 3 * L * c
            g[v1, r2] = g[r2, v1] = s * 3 * L * c
            g[v2, r1] = g[r1, v2] = -s * 3 * L * c
            g[v2, r2] = g[r2, v2] = -s * 3 * L * c
            g[r1, r1] = g[r2, r2] = 4 * L * L * c
            g[r1, r2] = g[r2, r1] = -L * L * c
        return g

    @staticmethod
    def _condense(k, rel):
        if not rel:
            return k
        rel = list(rel)
        keep = [i for i in range(12) if i not in rel]
        kbb = k[np.ix_(rel, rel)]
        kab = k[np.ix_(keep, rel)]
        kc = np.zeros_like(k)
        kc[np.ix_(keep, keep)] = k[np.ix_(keep, keep)] - kab @ np.linalg.pinv(kbb) @ kab.T
        return kc

    def elem_k(self, e):
        if e.kind == "spring":
            k = np.zeros((12, 12))
            for i, kv in enumerate(e.k6):
                if kv:
                    k[i, i] = k[i + 6, i + 6] = kv
                    k[i, i + 6] = k[i + 6, i] = -kv
            return k, None, 0.0
        T, L = self._T(e)
        kl = self._condense(self._kl(e.prop, L, e.kind), e.release)
        return T.T @ kl @ T, (T, kl), L

    # ------------------------------------------------------------------ assembly / solve
    def dofs(self, e):
        a, b = e.n1, e.n2
        return np.r_[6 * a:6 * a + 6, 6 * b:6 * b + 6]

    def assemble(self):
        n = 6 * len(self.xyz)
        K = np.zeros((n, n))
        self._cache = []
        for e in self.elems:
            kg, tk, L = self.elem_k(e)
            d = self.dofs(e)
            K[np.ix_(d, d)] += kg
            self._cache.append((tk, L))
        # tiny rotational stiffness at every node (bar-only nodes) - negligible
        for i in range(len(self.xyz)):
            for r in range(3, 6):
                K[6 * i + r, 6 * i + r] += 1e-3
        fixed = np.zeros(n, bool)
        for nn, f in self.sup.items():
            for j in range(6):
                fixed[6 * nn + j] = f[j]
        self.K, self.fixed = K, fixed
        self.free = np.where(~fixed)[0]
        Kff = K[np.ix_(self.free, self.free)]
        self.Kinv = np.linalg.inv(Kff)
        return self

    def solve(self, F):
        """F: (ndof, ncases) global loads. Returns displacements U (ndof, ncases) and reactions R."""
        F = np.atleast_2d(F.T).T if F.ndim == 1 else F
        U = np.zeros_like(F)
        U[self.free] = self.Kinv @ F[self.free]
        R = self.K @ U - F
        R[self.free] = 0.0
        return U, R

    def forces(self, U):
        """Local end forces per element: array (nelem, 12, ncases). Local: N=-f[0] (tension +) etc."""
        out = []
        for e, (tk, L) in zip(self.elems, self._cache):
            d = self.dofs(e)
            if tk is None:
                ue = U[d]
                f = np.zeros((12, U.shape[1]))
                for i, kv in enumerate(e.k6):
                    f[i] = kv * (ue[i] - ue[i + 6])
                    f[i + 6] = -f[i]
                out.append(f)
                continue
            T, kl = tk
            out.append(kl @ (T @ U[d]))
        return out

    def alpha_cr(self, U_case, iters=60):
        """Elastic critical load factor for one load case (column vector U)."""
        fl = self.forces(U_case[:, None])
        n = 6 * len(self.xyz)
        Kg = np.zeros((n, n))
        for e, (tk, L), f in zip(self.elems, self._cache, fl):
            if tk is None:
                continue
            N = -f[0, 0]          # tension positive
            T, _ = tk
            kgl = self._condense(self._kg(N, L, e.kind), e.release) if e.kind != "bar" else self._kg(N, L, "bar")
            d = self.dofs(e)
            Kg[np.ix_(d, d)] += T.T @ kgl @ T
        Kgf = -Kg[np.ix_(self.free, self.free)]   # destabilising part positive
        Kff = self.K[np.ix_(self.free, self.free)]
        Lc = np.linalg.cholesky(Kff)
        Li = np.linalg.inv(Lc)
        Cm = Li @ Kgf @ Li.T
        Cm = (Cm + Cm.T) / 2
        w, v = np.linalg.eigh(Cm)
        mu = w[-1]
        mode = np.zeros(n)
        mode[self.free] = Li.T @ v[:, -1]
        return (1.0 / mu if mu > 0 else float("inf")), mode
