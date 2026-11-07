"""Analysis, member checks and sizing for one scheme (S1/S2/S3) of the Option B support structure."""
from __future__ import annotations
import copy, math, time
import numpy as np
import model_b as MB
import sections as S

ECC = 0.145          # m, truss bearing (y = 0.30) to column centreline (y = 0.155) as modelled in the IFC
H_COL = MB.Z_COLTOP - MB.Z_BASE
H_WALL = MB.WALL_TOP - MB.FFL     # 12.23 m masonry height: basis of the h/300 limit (review O-11)
BAR_GROUPS = ["EAV", "EGC", "EGD", "RBD", "GBX", "GBS", "WBX", "WBK", "WBS", "BCT", "XF", "BCB"]
POST_CANDS = [s for s in S.COLUMNS if s.family == "UB"] + [s for s in S.UC if s.name.startswith("UC 305")]


class Result:
    pass


def run(d: MB.Design, scen="central", alpha=True, qp_uls=(0.85, 1.20), qp_sls=None):
    t0 = time.time()
    m = MB.build(d)
    m.assemble()
    L = MB.loads(m, scen)
    names = list(L)
    F = np.column_stack([L[k] for k in names])
    U, R = m.solve(F)
    fl = m.forces(U)                         # list of (12, ncases)
    C = MB.combos(qp_uls, qp_sls or getattr(d, "qp_sls", 0.85))
    cn = list(C)
    Mx = np.zeros((len(names), len(cn)))
    for j, c in enumerate(cn):
        for k, v in C[c][0].items():
            Mx[names.index(k), j] = v
    r = Result()
    r.m, r.d, r.names, r.combos, r.kind = m, d, names, cn, [C[c][1] for c in cn]
    r.U = U @ Mx
    r.R = R @ Mx
    r.f = [f @ Mx for f in fl]
    r.alpha = sway_alpha(r)
    if alpha == "eigen":
        for tag, cname in (("eig_transverse", f"U4 1.2G+1.3W WSn q{qp_uls[-1]}"), ("eig_longitudinal", f"U4 1.2G+1.3W WWp q{qp_uls[-1]}"),
                           ("eig_gravity", "U3 1.2G+1.6Qrig")):
            a, mode = m.alpha_cr(r.U[:, cn.index(cname)])
            k = int(np.argmax(abs(mode)))
            r.alpha[tag] = a
            r.alpha[tag + "_node"] = (m.ntag[k // 6], tuple(round(v, 2) for v in m.xyz[k // 6]), k % 6)
    r.time = time.time() - t0
    return r


def sway_alpha(r):
    """EN 1993-1-1 5.2.1(4)B / SANS 10162-1 sway check: alpha_cr = (H/V)(h/delta) per frame line (transverse) and per
    wall line (longitudinal), minimum over the ULS wind combinations."""
    m = r.m
    out = {"transverse": 99.0, "longitudinal": 99.0}
    js = [j for j, c in enumerate(r.combos) if c.startswith(("U4", "U2", "U3"))]
    for j in js:
        c = r.combos[j]
        trans = (c.split()[2][1] in "SN") if c.startswith("U4") else not c.split()[0].endswith("x")
        if trans:
            for i in range(11):
                H = sum(r.R[6 * m.C[i, s][0] + 1, j] for s in (0, 1))
                V = sum(r.R[6 * m.C[i, s][0] + 2, j] for s in (0, 1))
                dl = np.mean([r.U[6 * m.C[i, s][-1] + 1, j] for s in (0, 1)])
                if abs(H) > 1 and abs(dl) > 1e-5 and V > 0:
                    out["transverse"] = min(out["transverse"], abs(H) / V * H_COL / abs(dl))
        else:
            for s in (0, 1):
                H = sum(r.R[6 * m.C[i, s][0] + 0, j] for i in range(11))
                V = sum(r.R[6 * m.C[i, s][0] + 2, j] for i in range(11))
                dl = np.mean([r.U[6 * m.C[i, s][-1] + 0, j] for i in range(11)])
                if abs(H) > 1 and abs(dl) > 1e-5 and V > 0:
                    out["longitudinal"] = min(out["longitudinal"], abs(H) / V * H_COL / abs(dl))
    return out


def amp(r):
    a = min(r.alpha.get("transverse", 99), r.alpha.get("longitudinal", 99))
    return 1.0 / (1 - 1 / a) if a < 10 else 1.0


def column_checks(r):
    m, d = r.m, r.d
    uls = [j for j, k in enumerate(r.kind) if k == "ULS"]
    k_amp = amp(r)
    KLx = H_COL * {"S1": 1.0, "S3": 0.85, "S2": 1.0}[d.scheme]
    out = []
    # bearing vertical force (spring fz) per line/side
    brg = {}
    for e, f in zip(m.elems, r.f):
        if e.group == "BEARING":
            brg[e.tag["line"], e.tag["side"]] = f[2]       # spring force z (node1 - node2) * k : +ve = column top pushed up rel. heel
    for (i, side), ids in m.C.items():
        grp = "COLC" if i in (0, 10) else "COL"
        sec = d.sec[grp]
        segs = [(e, f) for e, f in zip(m.elems, r.f) if e.group == grp and e.tag["line"] == i and e.tag["side"] == side]
        worst = (0, None)
        zs = [m.xyz[n][2] for n in ids]
        for j in uls:
            Rv = abs(brg[i, side][j])
            Me_top = Rv * ECC
            for e, f in segs:
                z1, z2 = m.xyz[e.n1][2], m.xyz[e.n2][2]
                Cu = max(f[0, j], -f[6, j])
                lateral = "W" in r.combos[j]
                kk = k_amp if lateral else 1.0
                for zz, My, Mz in ((z1, f[4, j], f[5, j]), (z2, f[10, j], f[11, j])):
                    fr = (zz - MB.Z_BASE) / H_COL
                    Me = Me_top * (fr if d.scheme == "S1" else (1.5 * fr - 0.5))
                    Mux = abs(My) * kk + abs(Me)
                    Muy = abs(Mz) * kk
                    u, det = S.beam_column(sec, Cu, Mux, Muy, KLx, d.minor_restraint, d.minor_restraint, w2=1.13)
                    if u > worst[0]:
                        worst = (u, dict(combo=r.combos[j], z=zz, Cu=Cu, Mux=Mux, Muy=Muy, **det))
        out.append(dict(line=i, side=side, section=sec.name, util=worst[0], **(worst[1] or {})))
    return out


def drift(r):
    m = r.m
    res = {}
    for kind, lim_q in (("SLS_W", "q0.85"), ("SLS_W12", "q1.2")):
        js = [j for j, k in enumerate(r.kind) if k == kind]
        uy = max(abs(r.U[6 * n + 1, j]) for ids in m.C.values() for n in ids for j in js)
        ux = max(abs(r.U[6 * ids[-1] + 0, j]) for ids in m.C.values() for j in js)
        up = max(abs(r.U[6 * n + 0, j]) for ids in m.P.values() for n in ids for j in js)
        res[kind] = dict(col_y_mm=uy * 1000, eaves_x_mm=ux * 1000, post_x_mm=up * 1000)
    return res


def group_axial(r):
    """Envelope axial force per bar group (ULS): max tension (+), max compression (+), member length."""
    m = r.m
    uls = [j for j, k in enumerate(r.kind) if k == "ULS"]
    env = {}
    for e, f in zip(m.elems, r.f):
        if e.group not in BAR_GROUPS:
            continue
        L = float(np.linalg.norm(np.array(m.xyz[e.n2]) - np.array(m.xyz[e.n1])))
        comp = max(0.0, max(f[0, uls]))     # end-1 axial force +ve = compression
        ten = max(0.0, max(-f[0, uls]))
        g = env.setdefault(e.group, dict(T=0, C=0, Lmax=0, LC=0, n=0, Ltot=0))
        g["T"] = max(g["T"], ten)
        if comp > 0 and comp * L ** 2 > g["C"] * max(g["LC"], 1e-6) ** 2:
            pass
        g["C"] = max(g["C"], comp)
        g["LC"] = max(g["LC"], L) if comp > 1.0 else g["LC"]
        g["Lmax"] = max(g["Lmax"], L)
        g["n"] += 1
        g["Ltot"] += L
    return env


def size_bars(r, d):
    env = group_axial(r)
    changed = False
    for g, v in env.items():
        best = None
        for s in S.CHS:
            if s.avail == "import":
                continue
            Lc = max(v["LC"], 0.1)
            cr, lam = S.Cr(s, Lc, Lc) if v["C"] > 1.0 else (1e9, v["Lmax"] / s.rx)
            lam_t = v["Lmax"] / s.rx
            ok = cr >= v["C"] and S.Tr(s) >= v["T"] and (lam <= 200 if v["C"] > 1.0 else True) and lam_t <= 300
            if g == "WBS" and s.d < 0.1:
                ok = False
            if ok:
                best = s
                break
        best = best or S.CHS[-1]
        if d.sec[g].name != best.name:
            d.sec[g] = best
            changed = True
    return changed, env


def governing_sls(r, direction):
    js = [j for j, k in enumerate(r.kind) if k == "SLS_W"]
    if direction == "y":
        return max(js, key=lambda j: max(abs(r.U[6 * n + 1, j]) for ids in r.m.C.values() for n in ids))
    return max(js, key=lambda j: max(abs(r.U[6 * ids[-1], j]) for ids in r.m.C.values()))


def size_bars_min(r, d):
    """Strength sizing that only increases sections (keeps stiffness upsizing)."""
    keep = {g: d.sec[g] for g in BAR_GROUPS}
    size_bars(r, d)
    for g in BAR_GROUPS:
        if d.sec[g].A < keep[g].A:
            d.sec[g] = keep[g]


def post_check(r):
    m, d = r.m, r.d
    uls = [j for j, k in enumerate(r.kind) if k == "ULS"]
    worst = 0
    for e, f in zip(m.elems, r.f):
        if e.group != "POST":
            continue
        k = e.tag["k"]
        Lx = MB.z_top(k * MB.PANEL) - MB.Z_BASE
        for j in uls:
            Cu = max(f[0, j], -f[6, j])
            Mux = max(abs(f[4, j]), abs(f[10, j]))
            Muy = max(abs(f[5, j]), abs(f[11, j]))
            u, _ = S.beam_column(d.sec["POST"], Cu, Mux, Muy, Lx, d.minor_restraint, d.minor_restraint, w2=1.13)
            worst = max(worst, u)
    return worst


def post_drift_ok(r, limit=300):
    m = r.m
    js = [j for j, k in enumerate(r.kind) if k == "SLS_W"]
    ok = True
    worst = 0
    for (i, k), ids in m.P.items():
        Lx = MB.z_top(k * MB.PANEL) - MB.Z_BASE
        top = ids[-1]
        for n in ids:
            for j in js:
                rel = abs(r.U[6 * n, j] - r.U[6 * top, j] * (m.xyz[n][2] - MB.Z_BASE) / Lx)   # relative to chord
                worst = max(worst, rel / (Lx / limit))
    return worst


def size_scheme(scheme, col_name, colc_name=None, scen="central", drift_limit=300, minor=3.3, cladding="masonry",
                verbose=False, qp_uls=(0.85, 1.20), fixed_posts=None, qp_sls=0.85, base_krx=0.0):
    d = MB.default_design(scheme)
    d.base_krx = base_krx
    d.qp_sls = qp_sls
    d.minor_restraint = minor
    d.cladding = cladding
    d.sec["COL"] = MB.CAT[col_name]
    d.sec["COLC"] = MB.CAT[colc_name or col_name]
    if fixed_posts:
        d.sec["POST"] = MB.CAT[fixed_posts]
    hist = []
    for it in range(4):
        r = run(d, scen, alpha=False, qp_uls=qp_uls)
        changed, env = size_bars(r, d)
        # posts: strength and L/limit relative deflection
        if not fixed_posts:
            pc, pdft = post_check(r), post_drift_ok(r, drift_limit)
            if pc > 1.0 or pdft > 1.0:
                cand = [s for s in POST_CANDS if s.kg > d.sec["POST"].kg]
                if cand:
                    # stiffness scales with Ix: choose first candidate with Ix >= needed
                    need = d.sec["POST"].Ix * max(pdft, pc)
                    nxt = next((s for s in sorted(cand, key=lambda s: s.kg) if s.Ix >= need), cand[-1])
                    d.sec["POST"] = nxt
                    changed = True
        hist.append([d.sec[g].name for g in BAR_GROUPS])
        if verbose:
            print(it, {g: d.sec[g].name for g in d.sec}, round(r.time, 1))
        if not changed:
            break
    # stiffness iterations (review O-4): one group at a time, choosing the group with the largest strain energy per
    # tonne under the governing SLS case (virtual-work proxy for its share of the deflection), one catalogue step
    lim = H_WALL / drift_limit
    r = run(d, scen, alpha=False, qp_uls=qp_uls)
    for it in range(18):
        dr = drift(r)["SLS_W"]
        need = []
        if dr["eaves_x_mm"] / 1000 > lim:
            need.append(("x", ["WBX", "WBK", "WBS", "EAV", "RBD", "XF", "BCB"]))
        if d.scheme in ("S1", "S3") and dr["col_y_mm"] / 1000 > lim:
            need.append(("y", ["EGD", "EGC", "EAV", "GBX", "GBS"]))
        if not need:
            break
        for direction, groups in need:
            j_c = governing_sls(r, direction)
            best, score = None, -1
            for e, f in zip(r.m.elems, r.f):
                pass
            en = {}
            mass = {}
            for e, f in zip(r.m.elems, r.f):
                if e.group in groups and e.kind != "spring":
                    L = float(np.linalg.norm(np.array(r.m.xyz[e.n2]) - np.array(r.m.xyz[e.n1])))
                    N = f[0, j_c]
                    en[e.group] = en.get(e.group, 0) + N * N * L / (2 * e.prop.E * e.prop.A)
                    mass[e.group] = mass.get(e.group, 0) + e.prop.kg_m * L
            for g in en:
                sc = en[g] / max(mass[g], 1.0)
                cands = [s_ for s_ in S.CHS if s_.avail != "import" and s_.A > d.sec[g].A * 1.15]
                if cands and sc > score:
                    best, score = g, sc
            if best:
                d.sec[best] = [s_ for s_ in S.CHS if s_.avail != "import" and s_.A > d.sec[best].A * 1.15][0]
        r = run(d, scen, alpha=False, qp_uls=qp_uls)
        size_bars_min(r, d)
        r = run(d, scen, alpha=False, qp_uls=qp_uls)
    r = run(d, scen, alpha=True, qp_uls=qp_uls)
    r.cols = column_checks(r)
    r.drift = drift(r)
    r.env = group_axial(r)
    r.post_util = post_check(r)
    # robustness: no masonry restraint at all - true unbraced length = full column / post height (review O-12)
    m0 = d.minor_restraint
    d.minor_restraint = H_COL
    r.util_unrestrained = max(c["util"] for c in column_checks(r))
    r.post_util_unrestrained = post_check(r)
    d.minor_restraint = m0
    r.post_defl = post_drift_ok(r, drift_limit)
    lim = H_WALL * 1000 / drift_limit
    r.col_util = max(c["util"] for c in r.cols)
    r.drift_ratio = max(r.drift["SLS_W"]["col_y_mm"], r.drift["SLS_W"]["eaves_x_mm"]) / lim
    r.ok = r.col_util <= 1.0 and r.drift_ratio <= 1.0 and r.post_util <= 1.0
    return r
