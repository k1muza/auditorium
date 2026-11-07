"""Verification of frame3d against closed-form results (writes calcs/solver_verification.json)."""
import json, math, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
from frame3d import Model, Prop, E_STEEL

ROOT = os.path.abspath(os.path.dirname(__file__) + "/..")
res = []
I = 11410e-8   # UC254x73 strong axis
P = Prop("UC", 93.1e-4, I, 3908e-8, 57.6e-8)


def chain(m, p0, p1, n, prop, ref=(0, 1, 0)):
    ids = [m.node(*(np.array(p0) + (np.array(p1) - np.array(p0)) * k / n)) for k in range(n + 1)]
    for a, b in zip(ids[:-1], ids[1:]):
        m.add(a, b, prop, "beam", ref=ref)
    return ids


# 1 cantilever 13 m, tip load 10 kN in y  -> PL^3/3EI
m = Model(); ids = chain(m, (0, 0, 0), (0, 0, 13), 8, P)
m.support(ids[0], [1] * 6); m.assemble()
F = np.zeros(6 * len(m.xyz)); F[6 * ids[-1] + 1] = 10
U, R = m.solve(F[:, None])
res.append(dict(case="cantilever tip deflection (mm)", model=U[6 * ids[-1] + 1, 0] * 1000, exact=10 * 13 ** 3 / (3 * E_STEEL * I) * 1000))
res.append(dict(case="cantilever base moment (kNm)", model=abs(R[6 * ids[0] + 3, 0]), exact=130.0))

# 2 pinned-pinned column 13.08 m, UDL 5 kN/m in y lumped -> 5wL^4/384EI, M = wL^2/8
L = 13.08; n = 12
m = Model(); ids = chain(m, (0, 0, 0), (0, 0, L), n, P)
m.support(ids[0], [1, 1, 1, 0, 0, 1]); m.support(ids[-1], [1, 1, 0, 0, 0, 0]); m.assemble()
F = np.zeros(6 * len(m.xyz))
for k, i in enumerate(ids):
    F[6 * i + 1] = 5 * L / n * (0.5 if k in (0, n) else 1)
U, R = m.solve(F[:, None])
fl = m.forces(U)
Mmid = max(abs(f[4, 0]) for f in fl)
res.append(dict(case="propped column mid deflection (mm)", model=U[6 * ids[n // 2] + 1, 0] * 1000, exact=5 * 5 * L ** 4 / (384 * E_STEEL * I) * 1000))
res.append(dict(case="propped column max moment (kNm)", model=Mmid, exact=5 * L ** 2 / 8))

# 3 fixed-base propped column: max deflection wL^4/185EI ; base moment wL^2/8
m = Model(); ids = chain(m, (0, 0, 0), (0, 0, L), 24, P)
m.support(ids[0], [1, 1, 1, 1, 0, 1]); m.support(ids[-1], [1, 1, 0, 0, 0, 0]); m.assemble()
F = np.zeros(6 * len(m.xyz))
for k, i in enumerate(ids):
    F[6 * i + 1] = 5 * L / 24 * (0.5 if k in (0, 24) else 1)
U, R = m.solve(F[:, None])
res.append(dict(case="fixed-base propped column max deflection (mm)", model=max(abs(U[6 * i + 1, 0]) for i in ids) * 1000, exact=5 * L ** 4 / (185 * E_STEEL * I) * 1000))
res.append(dict(case="fixed-base propped column base moment (kNm)", model=abs(R[6 * ids[0] + 3, 0]), exact=5 * L ** 2 / 8))

# 4 Euler buckling, pinned-pinned, minor axis prevented -> pi^2 EI / L^2 (strong axis buckling only)
m = Model(); ids = chain(m, (0, 0, 0), (0, 0, L), 12, Prop("UC", 93.1e-4, I, 1.0, 1.0))
m.support(ids[0], [1, 1, 1, 0, 0, 1]); m.support(ids[-1], [1, 1, 0, 0, 0, 0])
for i in ids[1:-1]:
    m.support(i, [1, 0, 0, 0, 0, 0])
m.assemble()
F = np.zeros(6 * len(m.xyz)); F[6 * ids[-1] + 2] = -1000
U, R = m.solve(F[:, None])
a, _ = m.alpha_cr(U[:, 0])
res.append(dict(case="Euler load pinned column (kN)", model=a * 1000, exact=math.pi ** 2 * E_STEEL * I / L ** 2))

# 5 two-bar truss (statics)
m = Model(); a = m.node(0, 0, 0); b = m.node(0, 4, 0); c = m.node(0, 2, 2)
bp = Prop("bar", 10e-4)
m.add(a, c, bp, "bar"); m.add(b, c, bp, "bar")
m.support(a, [1] * 6); m.support(b, [1] * 6); m.support(c, [1, 0, 0, 1, 1, 1]); m.assemble()
F = np.zeros(6 * len(m.xyz)); F[6 * c + 2] = -100
U, R = m.solve(F[:, None]); fl = m.forces(U)
res.append(dict(case="two-bar truss member force (kN, compression)", model=fl[0][0, 0], exact=100 / 2 / math.sin(math.radians(45))))

for r in res:
    r["ratio"] = r["model"] / r["exact"]
    print(f"{r['case']:<50} model {r['model']:10.3f} exact {r['exact']:10.3f} ratio {r['ratio']:.4f}")
os.makedirs(ROOT + "/calcs", exist_ok=True)
json.dump(res, open(ROOT + "/calcs/solver_verification.json", "w"), indent=1)
