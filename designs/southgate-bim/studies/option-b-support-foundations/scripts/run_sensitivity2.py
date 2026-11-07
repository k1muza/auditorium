"""Sensitivity sweeps on the selected designs (review round 1). Run from the study root after evaluate + select_and_mc.
Base fixity springs: K = k_s L B^3 / 12 with k_s 30 MN/m3 (G2) or 12 MN/m3 (G3) for ~2.6 m pads, halved for partial contact
under the governing eccentricity -> ~50,000 / ~20,000 kNm/rad (study estimates; subgrade modulus to come from the SI)."""
import json, os, subprocess, sys, time
sys.path.insert(0, os.path.dirname(__file__))
PY = sys.executable
ROOT = os.path.abspath(os.path.dirname(__file__) + "/..")
sel = json.load(open(ROOT + "/calcs/selection.json"))
unc = json.load(open(ROOT + "/calcs/selection_unconstrained.json"))
cols = lambda schemes: ";".join(f"{s}=" + "|".join(dict.fromkeys([sel[s]["column"], unc[s]["column"]])) for s in schemes)
light = "S1=UB 457x191x67|UC 305x305x118;S2=UB 533x210x92|UC 356x368x129;S3=UB 406x178x60|UC 305x305x97"
jobs = [("qsls12", ["--qsls", "1.2"], cols("S1,S2,S3".split(","))), ("cpi055", ["--cpi", "0.55"], cols(["S1", "S2", "S3"])),
        ("cpin108", ["--cpin", "-1.08"], cols(["S1", "S2", "S3"])), ("q085", ["--qp", "0.85"], cols(["S1", "S2", "S3"])),
        ("future", ["--scen", "future"], cols(["S1", "S2", "S3"])), ("fixG2", ["--krx", "50000", "--schemes", "S2,S3"], cols(["S2", "S3"])),
        ("fixG3", ["--krx", "20000", "--schemes", "S2,S3"], cols(["S2", "S3"])), ("light", ["--limit", "150"], light)]
running = []
for tag, extra, c in jobs:
    while len(running) >= 4:
        running = [p for p in running if p.poll() is None]
        time.sleep(5)
    log = open(f"{ROOT}/work/sweep_{tag}.log", "w")
    running.append(subprocess.Popen([PY, "scripts/sweep.py", tag, *extra, "--cols", c], cwd=ROOT, stdout=log, stderr=subprocess.STDOUT))
for p in running:
    p.wait()
# wall-density sensitivity (re-evaluation only: masonry 0.7 x 72 kN/m)
import evaluate as EV
base = json.load(open(ROOT + "/calcs/sweep_base.json"))["results"]
EV.WALL_FACTOR = 0.7
EV.PADCACHE.clear()
wd = {}
for s in sel:
    rec = next(r for r in base if r["scheme"] == s and r["column"] == sel[s]["column"])
    e = EV.evaluate(rec, "G2", "F2")
    wd[s] = dict(total=e.get("total"), ok=e.get("ok"), fail=e.get("fail"))
json.dump(wd, open(ROOT + "/calcs/wall_density_07.json", "w"), indent=1)
print("done", wd)
