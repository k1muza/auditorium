# Option B support structure, lateral stability and foundation study (S01, 7 Nov 2026)

Preliminary engineering study. **Not for construction, not engineer-approved.** The authoritative `bim/southgate.ifc` was read only (sha256 6cb86f6d…b035e, unchanged).

| Deliverable | File |
|---|---|
| A Main report | `report/Southgate_Option_B_Support_Structure_Lateral_Stability_Foundation_Study.pdf` (HTML source alongside) |
| B Support register | `data/B_structural_support_register.csv`, `data/B_footing_register.csv` |
| C Analysis and reactions | `data/C1–C4_*.csv`, `calcs/*.json`, `scripts/` |
| D Steel comparison | `data/D_steel_framing_comparison.csv` |
| E Foundation comparison | `data/E_foundation_comparison.csv` |
| F Cost model | `data/F_cost_comparison_model.xlsx` (live formulas; `Rates!B1` selects low/central/high), `data/cost_rates.csv` |
| G Drawings | `drawings/G_structural_concept_drawings.pdf` and `S-0x_*.png` |
| H Risk register | `data/H_risk_and_outstanding_information_register.csv` |
| I Review record | `review/I_independent_review_record.md` |
| J BIM specification | `bim_spec/J_BIM_implementation_specification.md`, `bim_spec/J_values.md` |

## Re-running (Python: the auditorium root `.venv`, which has numpy, matplotlib, openpyxl and pymupdf)

```
python scripts/s02_extract_inventory.py ../../bim/southgate.ifc data/ifc_structural_extract.json   # needs southgate-bim .venv (ifcopenshell), run with -I
python scripts/hand_checks.py                 # solver verification
bash   scripts/run_base.sh                    # base sweep, 3 parallel processes (~30 min)
python scripts/evaluate.py base               # foundations, quantities, costs
python scripts/select_and_mc.py               # selection + Monte Carlo
python scripts/run_sensitivity2.py            # sensitivity sweeps (~40 min)
python scripts/exports.py; python scripts/charts.py; python scripts/drawings.py; python scripts/bim_spec_values.py
python scripts/build_report.py                # HTML + PDF (headless Edge)
```

Superseded intermediate files from before the review (for example `calcs/sweep_minor65.json` and `calcs/sweep_cpi055.json` from the first round) are overwritten or no longer read. `report/` and `data/` reflect review round 1.
