"""S02 reconciled reaction schedules.
 data/C1_S02_truss_bearing_reactions.csv  - truss bearing (truss-to-column) forces, by support category
 data/C2_S02_base_reactions.csv           - complete column / post base reactions with governing concurrent combinations
 calcs/reactions_S02.json                 - category summary incl. S01 values, R2 screening values and lateral-system totals
Bearing forces are spring forces between column cap and truss heel (+z = compression on the column).
Base reactions are forces on the structure from the foundation: Fz > 0 compression, M about the global axes."""
import csv, json, math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import s02cfg as C

CAT = {0: "gable truss (lines 0, 10)", 10: "gable truss (lines 0, 10)", 1: "end-adjacent truss (lines 1, 9)", 9: "end-adjacent truss (lines 1, 9)",
       2: "second truss (lines 2, 8)", 8: "second truss (lines 2, 8)"}
R2 = {"compression_085": 110.0, "uplift_085": -44.0, "uplift_120_interior": -75.0, "uplift_120_gable": -104.0}


def cat(line):
    return CAT.get(line, "typical interior truss (lines 3-7)")


def load(fn, sch, col):
    return next(r for r in json.load(open(fn))["results"] if r["scheme"] == sch and r["column"] == col)


def bearing_rows(rec, label):
    rows = []
    for b in rec["bearings"]:
        if b["group"] != "BEARING":
            continue
        for qtag in sorted({c.split(" q")[-1] for c in b["F"] if c.startswith("U4") or c.startswith("U5")}):
            uls = {c: v for c, v in b["F"].items() if (c.startswith("U") and (c.endswith("q" + qtag) or not c.startswith(("U4", "U5"))))}
            comp_c = max(uls, key=lambda c: uls[c][2])
            up_c = min(uls, key=lambda c: uls[c][2])
            ht_c = max(uls, key=lambda c: abs(uls[c][1]))
            hl_c = max(uls, key=lambda c: abs(uls[c][0]))
            rows.append(dict(design=label, scheme=rec["scheme"], line=b["line"], side="south" if b["side"] == 0 else "north", category=cat(b["line"]),
                             qp_ULS=qtag, compression_kN=round(uls[comp_c][2], 1), compression_combo=comp_c, uplift_kN=round(uls[up_c][2], 1),
                             uplift_combo=up_c, H_transverse_kN=round(abs(uls[ht_c][1]), 1), H_transverse_combo=ht_c,
                             H_longitudinal_kN=round(abs(uls[hl_c][0]), 1), H_longitudinal_combo=hl_c))
    return rows


def base_rows(rec, label, braced_lines):
    rows = []
    for b in rec["bases"]:
        U = {c: R for c, R in b["R"].items() if c.startswith("U")}
        if b["kind"] == "column":
            corner = b["line"] in (0, 10)
            c = "corner column" if corner else ("braced-bay column" if b["line"] in braced_lines else "typical side column")
            loc = f"line {b['line']} {'south' if b['side'] == 0 else 'north'}"
        else:
            c = "gable post (braced panel)" if b["k"] in ({0: (3, 5, 7, 9), 10: (1, 3, 9, 11)}[b["line"]]) else "gable post"
            loc = f"{'west' if b['line'] == 0 else 'east'} gable, y = {b['y']:.1f}"
        nmax = max(U, key=lambda k: U[k][2])
        nmin = min(U, key=lambda k: U[k][2])
        mmax = max(U, key=lambda k: abs(U[k][3]))
        hmax = max(U, key=lambda k: math.hypot(U[k][0], U[k][1]))
        rows.append(dict(design=label, scheme=rec["scheme"], location=loc, category=c, x=round(b["x"], 2), y=round(b["y"], 2),
                         N_comp_kN=round(U[nmax][2], 1), N_comp_combo=nmax,
                         N_uplift_kN=round(U[nmin][2], 1), N_uplift_combo=nmin, M_with_uplift_kNm=round(U[nmin][3], 1),
                         M_max_kNm=round(U[mmax][3], 1), M_max_combo=mmax, N_with_M_max_kN=round(U[mmax][2], 1),
                         H_max_kN=round(math.hypot(U[hmax][0], U[hmax][1]), 1), H_max_combo=hmax, N_with_H_max_kN=round(U[hmax][2], 1)))
    return rows


def lateral_totals(rec):
    """Total ULS wind base shear in each direction and the share carried by the braced bays / fixed columns."""
    out = {}
    for d, k in (("transverse (wind S)", "U4 1.2G+1.3W WSp"), ("longitudinal (wind W)", "U4 1.2G+1.3W WWp")):
        cs = [c for c in rec["bases"][0]["R"] if c.startswith(k)]
        c = max(cs, key=lambda x: float(x.split("q")[-1]))
        comp = 1 if "transverse" in d else 0
        tot = sum(b["R"][c][comp] for b in rec["bases"])
        cols = sum(b["R"][c][comp] for b in rec["bases"] if b["kind"] == "column")
        out[d] = dict(combo=c, total_kN=round(tot, 1), columns_kN=round(cols, 1), posts_kN=round(tot - cols, 1))
    return out


if __name__ == "__main__":
    S01 = C.S01 + "/calcs/sweep_base.json"
    designs = [("S02 S3 (L2)", C.S02 + "/calcs/sweep_DB_L2_S3.json", "S3", "UC 305x305x97", (1, 2, 5, 6)),
               ("S02 S3 (L1)", C.S02 + "/calcs/sweep_DB_L1_S3.json", "S3", "UC 305x305x97", (1, 2, 3, 4, 5, 6)),
               ("S02 S1 (L2)", C.S02 + "/calcs/sweep_DB_L2_S12.json", "S1", "UC 305x305x137", (1, 2, 5, 6)),
               ("S01 S3", S01, "S3", "UC 305x305x97", (1, 2, 5, 6))]
    B, Bs, summ = [], [], {}
    for lab, fn, sch, col, br in designs:
        rec = load(fn, sch, col)
        br_ = bearing_rows(rec, lab)
        bs_ = base_rows(rec, lab, br)
        B += br_
        Bs += bs_
        cs = {}
        for r in br_:
            k = (r["category"], r["qp_ULS"])
            v = cs.setdefault(f"{k[0]} | q {k[1]}", dict(compression=0, uplift=0, Ht=0, Hl=0))
            v["compression"] = max(v["compression"], r["compression_kN"])
            v["uplift"] = min(v["uplift"], r["uplift_kN"])
            v["Ht"] = max(v["Ht"], r["H_transverse_kN"])
            v["Hl"] = max(v["Hl"], r["H_longitudinal_kN"])
        bc = {}
        for r in bs_:
            v = bc.setdefault(r["category"], dict(N_comp=0, N_uplift=0, M=0, H=0, n=0))
            v["N_comp"] = max(v["N_comp"], r["N_comp_kN"])
            v["N_uplift"] = min(v["N_uplift"], r["N_uplift_kN"])
            v["M"] = max(v["M"], abs(r["M_max_kNm"]))
            v["H"] = max(v["H"], r["H_max_kN"])
            v["n"] += 1
        summ[lab] = dict(bearings=cs, bases=bc, lateral=lateral_totals(rec))
    os.makedirs(C.S02 + "/data", exist_ok=True)
    for fn, rows in (("C1_S02_truss_bearing_reactions.csv", B), ("C2_S02_base_reactions.csv", Bs)):
        with open(C.S02 + "/data/" + fn, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
    summ["R2_screening"] = R2
    json.dump(summ, open(C.S02 + "/calcs/reactions_S02.json", "w"), indent=1)
    for lab, s in summ.items():
        if lab == "R2_screening":
            continue
        print("==", lab)
        for k, v in s["bearings"].items():
            print("  BRG", k, v)
        for k, v in s["bases"].items():
            print("  BASE", k, {a: round(b, 1) for a, b in v.items()})
        print("  LAT", s["lateral"])
