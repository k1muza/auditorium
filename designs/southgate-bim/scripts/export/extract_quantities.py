"""Model-derived quantity extraction.

  .venv/Scripts/python scripts/export/extract_quantities.py --in <build>/southgate.ifc --out <build>/southgate_qto.ifc
        computes Qto_*BaseQuantities (ifc5d) + SOUTHGATE_Quantities, writes a NEW ifc + schedules
  .venv/Scripts/python scripts/export/extract_quantities.py --in bim/southgate.ifc --check
        recomputes in memory and reports stored quantities that are stale (no file written)
"""
import argparse, csv, json, sys, time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
import ifcopenshell  # noqa: E402
import ifcopenshell.util.element as ue  # noqa: E402
from southgate_bim.quantities import qto  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--in", dest="inp", required=True)
ap.add_argument("--out")
ap.add_argument("--check", action="store_true")
ap.add_argument("--reports", default=str(ROOT / "reports/quantities"))
a = ap.parse_args()
t0 = time.time()
f = ifcopenshell.open(a.inp)

if a.check:
    stored = {e.GlobalId: ue.get_psets(e, qtos_only=True) for e in qto.target_elements(f)}
    qto.compute_base_quantities(f)
    qto.sanitise(f, qto.geometry_measures(f, qto.target_elements(f)))
    stale = []
    for e in qto.target_elements(f):
        new = ue.get_psets(e, qtos_only=True)
        old = stored.get(e.GlobalId, {})
        for qn, props in new.items():
            for k, v in props.items():
                if k == "id" or not isinstance(v, (int, float)):
                    continue
                ov = (old.get(qn) or {}).get(k)
                if ov is None or abs(ov - v) > 1e-6 * max(1.0, abs(v)):
                    stale.append((e.Name, qn, k, ov, v))
    print(json.dumps({"elements": len(stored), "stale_values": len(stale), "examples": stale[:10]}, default=str))
    sys.exit(1 if stale else 0)

qto.compute_base_quantities(f)
qto.add_project_quantities(f)
out = Path(a.out)
if out.exists():
    raise SystemExit(f"{out} exists - refusing to overwrite")
f.write(str(out))
rows = qto.schedule_rows(f)
R = Path(a.reports)
R.mkdir(parents=True, exist_ok=True)
qto.write_csv(rows, R / "quantity_schedule_elements.csv")

# category summary (counts + summed measures) by class / predefined / object type / profile / material / status
summ = defaultdict(lambda: defaultdict(float))
for r in rows:
    k = (r["ifc_class"], r["predefined_type"], r["object_type"], r["profile"], r["material"], r["design_status"])
    s = summ[k]
    s["Count"] += 1
    for m in ("Length_m", "GrossArea_m2", "NetArea_m2", "GrossVolume_m3", "NetVolume_m3", "IndicativeMass_kg", "NominalSectionMass_kg"):
        if r[m] not in (None, ""):
            s[m] += float(r[m])
            s["n_" + m] += 1
with open(R / "quantity_schedule_summary.csv", "w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh)
    cols = ["Count", "Length_m", "GrossArea_m2", "NetArea_m2", "GrossVolume_m3", "NetVolume_m3", "IndicativeMass_kg", "NominalSectionMass_kg"]
    w.writerow(["ifc_class", "predefined_type", "object_type", "profile", "material", "design_status"] + cols +
               ["elements_with_" + c for c in cols[1:]])
    for k in sorted(summ, key=lambda k: (k[0], k[1], k[2], k[3])):
        s = summ[k]
        w.writerow(list(k) + [round(s[c], 4) for c in cols] + [int(s["n_" + c]) for c in cols[1:]])
print(json.dumps({"elements": len(rows), "out": str(out), "seconds": round(time.time() - t0, 1)}))
