"""Column-section sweep per stability scheme (writes calcs/sweep_<tag>.json).
Usage: python sweep.py [tag] [--minor 3.3] [--limit 300] [--qp 0.85,1.20] [--scen central]"""
import argparse, json, os, sys, time
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
import analyse as A
import model_b as MB

ROOT = os.path.abspath(os.path.dirname(__file__) + "/..")
ap = argparse.ArgumentParser()
ap.add_argument("tag", nargs="?", default="base")
ap.add_argument("--minor", type=float, default=3.3)
ap.add_argument("--limit", type=float, default=300)
ap.add_argument("--qp", default="0.85,1.20")
ap.add_argument("--scen", default="central")
ap.add_argument("--only", default="")
ap.add_argument("--cols", default="", help="restrict candidates: S1=UC 305x305x137|UC 305x305x158;S3=...")
ap.add_argument("--schemes", default="S1,S2,S3")
ap.add_argument("--qsls", type=float, default=0.85)
ap.add_argument("--cpi", type=float, default=0.2)
ap.add_argument("--cpin", type=float, default=-0.3)
ap.add_argument("--krx", type=float, default=0.0)
args = ap.parse_args()
QP = tuple(float(x) for x in args.qp.split(","))
MB.CPI["p"] = args.cpi
MB.CPI["n"] = args.cpin

CANDS = {
    "S1": ["UC 254x254x107", "UC 254x254x132", "UC 305x305x118", "UC 305x305x137", "UC 305x305x158", "UB 406x178x74",
           "UB 457x191x67", "UB 457x191x82", "UC 356x368x129"],
    "S3": ["UC 254x254x73", "UC 254x254x89", "UC 254x254x107", "UC 305x305x97", "UB 406x178x60", "UB 406x178x74"],
    "S2": ["UC 305x305x137", "UC 305x305x158", "UC 356x368x129", "UC 356x368x153", "UC 356x368x177", "UB 533x210x92",
           "UB 610x229x101"],
}


def base_record(r):
    m = r.m
    recs = []
    for (i, side), ids in m.C.items():
        recs.append(dict(kind="column", line=i, side=side, x=m.xyz[ids[0]][0], y=m.xyz[ids[0]][1], node=ids[0]))
    for (i, k), ids in m.P.items():
        recs.append(dict(kind="post", line=i, k=k, x=m.xyz[ids[0]][0], y=m.xyz[ids[0]][1], node=ids[0]))
    for rec in recs:
        n = rec.pop("node")
        rec["R"] = {c: [round(float(v), 2) for v in r.R[6 * n:6 * n + 6, j]] for j, c in enumerate(r.combos)}
    return recs


def bearing_record(r):
    out = []
    for e, f in zip(r.m.elems, r.f):
        if e.group in ("BEARING", "KNEE", "HEEL"):
            out.append(dict(group=e.group, line=e.tag["line"], side=e.tag["side"],
                            F={c: [round(float(v), 2) for v in f[:3, j]] for j, c in enumerate(r.combos) if not c.startswith("S1")}))
    return out


def quantities(r):
    m = r.m
    q = {}
    for e in m.elems:
        if e.kind == "spring" or e.group.startswith("TRUSS") or e.group == "PURLIN":
            continue
        L = float(np.linalg.norm(np.array(m.xyz[e.n2]) - np.array(m.xyz[e.n1])))
        g = q.setdefault(e.group, dict(section=e.prop.name, kg_m=e.prop.kg_m, n=0, L=0.0))
        g["n"] += 1
        g["L"] += L
    for g in q.values():
        g["kg"] = g["kg_m"] * g["L"]
    return q


def truss_chord_forces(r):
    """Envelope of gable/interior truss chord axial forces incl. lateral-system collector action (ULS)."""
    uls = [j for j, k in enumerate(r.kind) if k == "ULS"]
    out = {}
    for e, f in zip(r.m.elems, r.f):
        if e.group in ("TRUSS_TC", "TRUSS_BC"):
            key = f"{e.group}|{'gable' if e.tag['line'] in (0, 10) else 'interior'}"
            o = out.setdefault(key, dict(C=0.0, T=0.0))
            o["C"] = max(o["C"], float(max(f[0, uls])))
            o["T"] = max(o["T"], float(max(-f[0, uls])))
    return out


if args.cols:
    for part in args.cols.split(";"):
        k, v = part.split("=")
        CANDS[k] = v.split("|")
results = []
for sch in args.schemes.split(","):
    for col in CANDS[sch]:
        if args.only and args.only not in col:
            continue
        t = time.time()
        r = A.size_scheme(sch, col, scen=args.scen, drift_limit=args.limit, minor=args.minor, qp_uls=QP, qp_sls=args.qsls, base_krx=args.krx)
        rec = dict(scheme=sch, column=col, ok=bool(r.ok), col_util=float(r.col_util), util_unrestrained=float(r.util_unrestrained), post_util_unrestrained=float(r.post_util_unrestrained), drift=r.drift, drift_ratio=float(r.drift_ratio),
                   alpha=r.alpha, post_util=float(r.post_util), post_defl=float(r.post_defl),
                   sections={g: s.name for g, s in r.d.sec.items()}, cols=[{k: (float(v) if isinstance(v, (np.floating, float)) else v) for k, v in c.items()} for c in r.cols],
                   env={g: {k: float(v) for k, v in e.items()} for g, e in r.env.items()}, qty=quantities(r),
                   chords=truss_chord_forces(r), time=time.time() - t)
        rec["bases"] = base_record(r)
        rec["bearings"] = bearing_record(r)
        results.append(rec)
        print(f"{sch} {col:<18} ok={rec['ok']} util={rec['col_util']:.3f} drift={rec['drift']['SLS_W']['col_y_mm']:.1f} "
              f"eavesx={rec['drift']['SLS_W']['eaves_x_mm']:.1f} t={rec['time']:.0f}s", flush=True)
os.makedirs(ROOT + "/calcs", exist_ok=True)
json.dump(dict(args=vars(args), results=results), open(f"{ROOT}/calcs/sweep_{args.tag}.json", "w"))
print("written", f"calcs/sweep_{args.tag}.json")
