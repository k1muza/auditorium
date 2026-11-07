#!/usr/bin/env bash
# Base-case sweep after review round 1, one process per scheme. Run from the study root.
PY=${PY:-/c/Users/Kelvin/Desktop/auditorium/.venv/Scripts/python.exe}
$PY scripts/sweep.py base_S1 --schemes S1 --cols "S1=UC 305x305x118|UC 305x305x137|UC 305x305x158|UB 406x178x74|UB 457x191x67|UB 457x191x82|UC 356x368x129" > work/sweep_base_S1.log 2>&1 &
$PY scripts/sweep.py base_S2 --schemes S2 --cols "S2=UC 305x305x158|UC 356x368x129|UC 356x368x153|UB 533x210x92|UB 610x229x101" > work/sweep_base_S2.log 2>&1 &
$PY scripts/sweep.py base_S3 --schemes S3 --cols "S3=UC 254x254x73|UC 254x254x89|UC 305x305x97|UB 406x178x60|UB 406x178x74" > work/sweep_base_S3.log 2>&1 &
wait
$PY - <<'PY'
import json
out = {"args": {"note": "merged base_S1/S2/S3 after review round 1"}, "results": []}
for s in ("S1", "S2", "S3"):
    out["results"] += json.load(open(f"calcs/sweep_base_{s}.json"))["results"]
json.dump(out, open("calcs/sweep_base.json", "w"))
print("merged", len(out["results"]))
PY
echo done
