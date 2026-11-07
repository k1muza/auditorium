#!/usr/bin/env bash
# Sensitivity sweeps on restricted candidate lists (representative designs and next sizes up). Run from the study root.
PY=${PY:-/c/Users/Kelvin/Desktop/auditorium/.venv/Scripts/python.exe}
C="S1=UC 305x305x137|UC 305x305x158|UC 356x368x129;S2=UC 356x368x129|UC 356x368x153;S3=UC 305x305x97|UC 254x254x107|UB 406x178x60"
# full sweeps already run: minor65 (--minor 6.5), light (--limit 150)
$PY scripts/sweep.py qsls12 --qsls 1.2    --cols "$C" > work/sweep_qsls12.log 2>&1 &
$PY scripts/sweep.py cpi055 --cpi 0.55    --cols "$C" > work/sweep_cpi055.log 2>&1 &
$PY scripts/sweep.py q085   --qp 0.85     --cols "$C" > work/sweep_q085.log 2>&1 &
$PY scripts/sweep.py future --scen future --cols "$C" > work/sweep_future.log 2>&1 &
wait
echo done
