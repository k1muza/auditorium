#!/usr/bin/env python3
"""Deterministic model QA review aggregator — NOT engineering approval."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys

WEIGHTS = {
    "seating_geometry": 20,
    "circulation_accessibility": 20,
    "structural_concept": 15,
    "bim_semantics": 15,
    "parametric_reproduction": 10,
    "documentation": 10,
    "validation_traceability": 10,
}


def evaluate(report_file: Path, root: Path) -> dict:
    data = json.loads(report_file.read_text(encoding="utf-8"))
    iteration = data.get("iteration")
    if not isinstance(iteration, int) or isinstance(iteration, bool) or not 1 <= iteration <= 3:
        raise ValueError("Report iteration must be an integer in [1, 3].")
    if not str(data.get("model_revision", "")).strip():
        raise ValueError("Missing model_revision.")
    cats = data.get("categories")
    if not isinstance(cats, dict) or set(cats) != set(WEIGHTS):
        raise ValueError("Report must include exactly the seven required categories.")
    critical_blockers = data.get("critical_blockers")
    if not isinstance(critical_blockers, list) or not all(isinstance(x, str) for x in critical_blockers):
        raise ValueError("critical_blockers must be a list of issue strings.")
    if not isinstance(data.get("findings"), list) or not isinstance(data.get("reviewer_summary"), str):
        raise ValueError("Report must have findings list and reviewer_summary string.")
    score = 0.0
    checked_evidence = []
    missing_evidence = []
    for key, weight in WEIGHTS.items():
        item = cats[key]
        value = item.get("score")
        if isinstance(value, bool) or not isinstance(value, (float, int)) or not 0 <= value <= 10:
            raise ValueError(f"{key}.score must be between 0 and 10")
        score += float(value) * weight / 100.0
        evidence = item.get("evidence")
        if not isinstance(evidence, list) or not evidence or not all(isinstance(p, str) and p.strip() for p in evidence):
            missing_evidence.append(f"{key}: no evidence paths listed")
            continue
        for rel in evidence:
            resolved = (root / rel).resolve()
            if not resolved.is_relative_to(root.resolve()) or not resolved.exists() or not resolved.is_file():
                missing_evidence.append(f"{key}: {rel} does not resolve to an existing project file")
            else:
                checked_evidence.append(rel)
    accepted = score > 9.0 and not critical_blockers and not missing_evidence
    return {
        "iteration": iteration,
        "model_revision": data["model_revision"],
        "weighted_score": round(score, 3),
        "threshold": "strictly >9.0/10",
        "critical_blockers": critical_blockers,
        "missing_evidence": missing_evidence,
        "evidence_files_checked": sorted(set(checked_evidence)),
        "accepted_for_concept_model_milestone": accepted,
        "status": "ACCEPTED_FOR_CONCEPT_MODEL_REVIEW" if accepted else "NOT_ACCEPTED_FOR_THIS_MILESTONE",
        "note": "QA scoring is not professional engineering verification, fire approval or authorization for construction.",
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("report", type=Path)
    ap.add_argument("--root", type=Path, default=Path.cwd(), help="Project root; default current directory")
    args = ap.parse_args()
    try:
        result = evaluate(args.report, args.root)
    except (OSError, json.JSONDecodeError, ValueError, KeyError) as exc:
        print(f"INVALID REVIEW: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    return 0 if result["accepted_for_concept_model_milestone"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
