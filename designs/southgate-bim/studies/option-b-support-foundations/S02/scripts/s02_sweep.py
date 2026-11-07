"""S02 sizing runs. Writes S02/calcs/sweep_<tag>.json (same record format as S01 so S01 evaluate.py can price it).
Usage: python s02_sweep.py TAG --long L1 --ea 0.85 --kfi 1.1 --krx 50000 --qsls 0.85 --limit 300
                           --cols "S3=UC 305x305x97|UC 254x254x89;S1=UC 305x305x137" """
import argparse, json, os, sys, time
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import s02cfg as C
import analyse as A
import model_b as MB

ap = argparse.ArgumentParser()
ap.add_argument("tag")
ap.add_argument("--long", default="L0")
ap.add_argument("--ea", type=float, default=1.0)
ap.add_argument("--kfi", type=float, default=1.0)
ap.add_argument("--krx", type=float, default=0.0)
ap.add_argument("--qsls", type=float, default=0.85)
ap.add_argument("--limit", type=float, default=300)
ap.add_argument("--minor", type=float, default=3.3)
ap.add_argument("--scen", default="central")
ap.add_argument("--cols", required=True)
ap.add_argument("--cpi", type=float, default=0.2)
ap.add_argument("--cpin", type=float, default=-0.3)
args = ap.parse_args()
C.CFG["LONG"], C.CFG["EA_BR"] = args.long, args.ea
MB.CPI["p"], MB.CPI["n"] = args.cpi, args.cpin
QP = (round(0.85 * args.kfi, 3), round(1.20 * args.kfi, 3))


def base_record(r):
    m = r.m
    recs = []
    for (i, side), ids in m.C.items():
        recs.append(dict(kind="column", line=i, side=side, x=m.xyz[ids[0]][0], y=m.xyz[ids[0]][1], node=ids[0]))
    for (i, k), ids in m.P.items():
        recs.append(dict(kind="post", line=i, k=k, x=m.xyz[ids[0]][0], y=m.xyz[ids[0]][1], node=ids[0]))
    for rec in recs:
        n = rec.pop("node")
        Rn = r.R[6 * n:6 * n + 6, :].copy()
        # semi-rigid fixed bases: the base moment passes through the rotational spring to a ground node (S02 fix)
        key = (round(rec["x"] / 1e-4), round(rec["y"] / 1e-4), round((MB.Z_BASE - 0.5) / 1e-4))
        g = m._idx.get(key)
        if g is not None and rec["kind"] == "column":
            Rn += r.R[6 * g:6 * g + 6, :]
        rec["R"] = {c: [round(float(v), 2) for v in Rn[:, j]] for j, c in enumerate(r.combos)}
    return recs


def bearing_record(r):
    out = []
    for e, f in zip(r.m.elems, r.f):
        if e.group in ("BEARING", "KNEE", "HEEL"):
            out.append(dict(group=e.group, line=e.tag["line"], side=e.tag["side"],
                            F={c: [round(float(v), 2) for v in f[:3, j]] for j, c in enumerate(r.combos) if not c.startswith("S1")}))
    return out


def quantities(r):
    q = {}
    for e in r.m.elems:
        if e.kind == "spring" or e.group.startswith("TRUSS") or e.group == "PURLIN":
            continue
        L = float(np.linalg.norm(np.array(r.m.xyz[e.n2]) - np.array(r.m.xyz[e.n1])))
        g = q.setdefault(e.group, dict(section=e.prop.name, kg_m=e.prop.kg_m, n=0, L=0.0))
        g["n"] += 1
        g["L"] += L
    for g in q.values():
        g["kg"] = g["kg_m"] * g["L"]
    return q


def chords(r):
    uls = [j for j, k in enumerate(r.kind) if k == "ULS"]
    out = {}
    for e, f in zip(r.m.elems, r.f):
        if e.group in ("TRUSS_TC", "TRUSS_BC"):
            key = f"{e.group}|{'gable' if e.tag['line'] in (0, 10) else 'interior'}"
            o = out.setdefault(key, dict(C=0.0, T=0.0))
            o["C"] = max(o["C"], float(max(f[0, uls])))
            o["T"] = max(o["T"], float(max(-f[0, uls])))
    return out


def brace_forces(r):
    """Envelope ULS axial force per bracing group and per wall braced bay (for connection design and pads)."""
    uls = [j for j, k in enumerate(r.kind) if k == "ULS"]
    out = {}
    for e, f in zip(r.m.elems, r.f):
        if e.group in A.BAR_GROUPS:
            o = out.setdefault(e.group, dict(C=0.0, T=0.0))
            o["C"] = max(o["C"], float(max(f[0, uls])))
            o["T"] = max(o["T"], float(max(-f[0, uls])))
    return out


res = []
for part in args.cols.split(";"):
    sch, cols = part.split("=")
    for col in cols.split("|"):
        t = time.time()
        krx = args.krx if sch in ("S2", "S3") else 0.0
        r = A.size_scheme(sch, col, scen=args.scen, drift_limit=args.limit, minor=args.minor, qp_uls=QP, qp_sls=args.qsls, base_krx=krx)
        rec = dict(scheme=sch, column=col, ok=bool(r.ok), col_util=float(r.col_util), util_unrestrained=float(r.util_unrestrained),
                   post_util_unrestrained=float(r.post_util_unrestrained), drift=r.drift, drift_ratio=float(r.drift_ratio), alpha=r.alpha,
                   post_util=float(r.post_util), post_defl=float(r.post_defl), sections={g: s.name for g, s in r.d.sec.items()},
                   cols=[{k: (float(v) if isinstance(v, (np.floating, float)) else v) for k, v in c.items()} for c in r.cols],
                   env={g: {k: float(v) for k, v in e.items()} for g, e in r.env.items()}, qty=quantities(r), chords=chords(r),
                   braces=brace_forces(r), time=time.time() - t, cfg=dict(C.CFG, kfi=args.kfi, krx=krx, qsls=args.qsls, limit=args.limit))
        rec["bases"] = base_record(r)
        rec["bearings"] = bearing_record(r)
        res.append(rec)
        dr = rec["drift"]
        print(f"{args.tag} {sch} {col:<16} ok={rec['ok']} u={rec['col_util']:.2f} y={dr['SLS_W']['col_y_mm']:.1f} x={dr['SLS_W']['eaves_x_mm']:.1f}"
              f" | q1.2 y={dr['SLS_W12']['col_y_mm']:.1f} x={dr['SLS_W12']['eaves_x_mm']:.1f} WBX={rec['sections']['WBX']} t={rec['time']:.0f}s", flush=True)
os.makedirs(C.S02 + "/calcs", exist_ok=True)
json.dump(dict(args=vars(args), results=res), open(f"{C.S02}/calcs/sweep_{args.tag}.json", "w"))
print("written", args.tag)
