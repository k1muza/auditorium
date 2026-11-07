"""Dry-run migration planning.

  .venv/Scripts/python scripts/migrate/plan_migration.py            # dry run: writes work/plan/*
  .venv/Scripts/python scripts/migrate/plan_migration.py --commit-mapping
        # additionally persists new stable IDs to source/source_to_ifc_mapping.csv
No IFC is written. The source snapshot is never opened for writing.
"""
import argparse, json, pickle, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from southgate_bim.migration.plan import Planner, summarise  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--commit-mapping", action="store_true", help="persist stable IDs / GlobalIds to source/")
a = ap.parse_args()

out = ROOT / "work/plan"
out.mkdir(parents=True, exist_ok=True)
pl = Planner(ROOT)
rows, elements, assemblies, n_fit = pl.build(ROOT / "work/fit_cache.pkl")
s = summarise(rows, elements, assemblies)
s["fits_computed_this_run"] = n_fit
with open(out / "plan.pkl", "wb") as fh:
    pickle.dump({"rows": rows, "elements": elements, "assemblies": assemblies, "summary": s}, fh, protocol=4)
json.dump(s, open(out / "plan_summary.json", "w"), indent=1)
if a.commit_mapping:
    pl.save_mapping()
    print("mapping committed:", pl.mapping_path)
print(json.dumps(s, indent=1))
