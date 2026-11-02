"""Combine the specialist reviewers' discipline scores into the rubric-weighted score per design and iteration.

  .venv/Scripts/python comparisons/score_reviews.py

Reads comparisons/reviews/iter-NN/<A|B>-*.json. A design not re-reviewed in an iteration keeps its latest earlier
scores (Option A is frozen, so its iteration-1 scores stand). Writes comparisons/out/review_scores.json and .md.
Acceptance (task rule): weighted score > 9.0 and no critical blockers. Scores are QA metrics, not certification.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
W = {"architecture": 15, "church_functionality": 15, "structural_engineering": 15, "life_safety": 15, "accessibility": 10,
     "acoustics_av": 10, "aesthetics": 5, "constructability_maintenance": 10, "cost_drivers": 5}


def main():
    iters = sorted(p.name for p in (ROOT / "reviews").iterdir() if p.is_dir())
    out, latest = {}, {"A": {}, "B": {}}
    for it in iters:
        for d in ("A", "B"):
            files = sorted((ROOT / "reviews" / it).glob(f"{d}-*.json"))
            for f in files:
                j = json.loads(f.read_text(encoding="utf-8"))
                latest[d][f.stem.split("-", 1)[1]] = {"file": f"{it}/{f.name}", "revision": j.get("revision"), "scores": j.get("scores", {}),
                                                      "blockers": j.get("critical_blockers", []),
                                                      "majors": sum(1 for x in j.get("findings", []) if x.get("severity") == "MAJOR")}
            sc, bl, revs, mj = {}, [], set(), 0
            for v in latest[d].values():
                sc.update({k: s for k, s in v["scores"].items() if k in W})
                bl += v["blockers"]
                revs.add(v["revision"])
                mj += v["majors"]
            if len(sc) == len(W):
                ws = sum(sc[k] * W[k] / 100 for k in W)
                out.setdefault(it, {})[d] = {"revisions_reviewed": sorted(r for r in revs if r), "scores": sc, "weighted": round(ws, 3),
                                             "critical_blockers": len(bl), "major_findings": mj,
                                             "accepted": ws > 9.0 and not bl,
                                             "sources": [v["file"] for v in latest[d].values()]}
    (ROOT / "out").mkdir(exist_ok=True)
    (ROOT / "out" / "review_scores.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    lines = ["| Iteration | Design | Revision(s) | " + " | ".join(W) + " | Weighted | Critical | Major | Accepted (>9, 0 critical) |",
             "|---|---|---|" + "---:|" * (len(W) + 3) + "---|"]
    for it, dd in out.items():
        for d, v in dd.items():
            lines.append(f"| {it} | {d} | {', '.join(v['revisions_reviewed'])} | " + " | ".join(f"{v['scores'][k]:.1f}" for k in W)
                         + f" | {v['weighted']:.2f} | {v['critical_blockers']} | {v['major_findings']} | {'yes' if v['accepted'] else 'no'} |")
    (ROOT / "out" / "review_scores.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
