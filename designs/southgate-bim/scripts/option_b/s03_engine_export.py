"""Run the Option B geometry engine for all 11 truss lines; write work/option_b/engine/Txx.json + summary.json.
Usage: .venv/Scripts/python scripts/option_b/s03_engine_export.py"""
import json, sys, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from southgate_bim.structure.optb_truss import OptionBTruss, load_rules
out = ROOT / "work/option_b/engine"; out.mkdir(parents=True, exist_ok=True)
rules, basis = load_rules()
summ = []
for line in range(11):
    T = OptionBTruss(line, rules, basis)
    d = T.to_dict()
    d["footprints"] = {m.id: [list(map(float, xy)) for xy in T.footprint(m, m.t_start, m.t_end).exterior.coords] for m in T.members.values()}
    d["tos"] = [[s / 10, T.z_tos(s / 10)] for s in range(0, 325)]
    json.dump(d, open(out / f"{T.tid}.json", "w"), indent=0)
    summ.append(d["summary"]); print(json.dumps(d["summary"]))
json.dump(summ, open(out / "summary.json", "w"), indent=1)
