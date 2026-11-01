# Independent BIM reviewer — scoring and stopping rules

The reviewer evaluates **engineering-coordination model quality** for the current milestone, NOT building safety or formal engineering certification. The score is a structured QA metric.

## Weighted categories (each scored from 0.0 to 10.0)
| Key | Weight | Evaluate with direct evidence |
|---|---:|---|
| `seating_geometry` | 20% | Exactly 3,000 congregation seats; model-derived count; real dimensions; controlled layouts; sightline assumptions; clash evidence |
| `circulation_accessibility` | 20% | Represented entrances/aisles/foyer/accessible seating and provisional egress routes; issues explicitly flagged for professional statutory review |
| `structural_concept` | 15% | Coordinated grids, column locations, roof-span/roof-frame concept, elevations and assumptions; no unsupported structural capacity claims |
| `bim_semantics` | 15% | IFC entities/classes, naming, levels, units, quantities, model separation; verified rather than claimed IFC export |
| `parametric_reproduction` | 10% | Regenerates from source code + config; documented environment; predictable names/counts; logs or test output |
| `documentation` | 10% | Actual, legible dimensioned conceptual plan/grid/space and seating schedule; reports correspond to the model revision |
| `validation_traceability` | 10% | Evidence of checks, reproducible results, limitations and unknowns; no invented references or tests |

Weighted score is the sum of `score * weight / 100` (displayed to two decimals, but compare the **unrounded** score against 9.0).

## Acceptance gate
Accept only when BOTH conditions hold:
1. Unrounded weighted score is **strictly greater than 9.0**; 9.0 exactly does not qualify.
2. No open **critical blockers** remain.

A critical blocker includes any of the following:
- Seat count not verified to equal exactly 3,000, or the model and seat schedule materially disagree.
- Serious model intersection / unit / scale faults that invalidate the layout.
- Missing or unverifiable model file, or output presented as existing when it is not.
- Fabricated structural calculations, fabricated regulatory compliance, unsupported assertions of fire-safety clearance, or false claims of engineering approval.
- Materially obstructed or plainly unworkable circulation or exits left unaddressed without clear restriction on use.
- Model can't be reproduced or reviewed because the fundamental source is unavailable.

**Unknown local regulatory requirements and deferred engineering analysis are not automatically critical blockers** if honestly logged, visibly excluded from the current concept stage, and not presented as satisfied. They still affect the relevant score.

## Reviewer independence and evidence
- Reviewer reviews **artifacts and tests** rather than trusting the builder's narrative.
- Use exact filenames, model element identifiers, test outputs or image locations to ground each category score.
- Read and inspect model contents where technically possible. If Blender/IFC tooling is unavailable, be explicit and penalize unverified categories.
- Do not edit builder code or model. Return defects and recommended fixes to the orchestrator.
- Identify false-positive passing tests, missing test coverage and contradictions.
- Review current version only, while using earlier reviews to check regressions.

## Loop rules
- Iteration 1: builder creates model -> reviewer independently evaluates -> save report.
- Iterations 2 and 3 (only when needed): builder fixes top issues -> regenerates outputs -> reviewer re-evaluates entire rubric including regressions -> save report.
- Stop immediately on acceptance or after iteration 3. No automatic fourth attempt.
- If capped with score <=9.0 or blockers, deliver best honest model, report failures, and label status `NOT_ACCEPTED_FOR_THIS_MILESTONE`.
- Review must provide actionable issues ordered CRITICAL > MAJOR > MINOR, acceptance decision, evidence and short summary of changes from the previous iteration.

## JSON report schema
Save as `reviews/iteration-01.json`, etc. JSON object:
```
{
  "iteration": 1,
  "model_revision": "<actual git SHA or artifact identifier>",
  "categories": {
    "seating_geometry": {"score": 0.0, "evidence": ["reports/seat_count_check.txt"], "notes": "..."},
    "circulation_accessibility": {"score": 0.0, "evidence": ["exports/floor_plan.png"], "notes": "..."},
    "structural_concept": {"score": 0.0, "evidence": ["exports/structural_grid.png"], "notes": "..."},
    "bim_semantics": {"score": 0.0, "evidence": ["reports/ifc_validation.txt"], "notes": "..."},
    "parametric_reproduction": {"score": 0.0, "evidence": ["scripts/build_auditorium.py"], "notes": "..."},
    "documentation": {"score": 0.0, "evidence": ["reports/basis_of_design.md"], "notes": "..."},
    "validation_traceability": {"score": 0.0, "evidence": ["reports/open_issues.md"], "notes": "..."}
  },
  "critical_blockers": ["Specific issue and evidence, if any"],
  "findings": [
    {"severity": "MAJOR", "issue": "...", "evidence": "...", "fix": "..."}
  ],
  "reviewer_summary": "..."
}
```
Use real paths actually produced by the builder; the paths above are illustrative. Always run `python scripts/evaluate_review.py reviews/iteration-XX.json` after each review. The script deterministically computes the weighted score and acceptance decision, not the reviewer itself.
