# Multidisciplinary design review rubric (Option A and Option B, identical)

A reviewer score is a structured QA metric for a **concept coordination model**. It is not an engineering certification,
code-compliance statement, fire approval or cost estimate.

## Disciplines (each scored 0.0-10.0 from direct model evidence)

| Key | Weight | What to judge (cite files / element names / measured values) |
|---|---:|---|
| `architecture` | 15% | Plan clarity, proportions, entrances, foyer, support spaces, integration of seating / platform / structure |
| `church_functionality` | 15% | Worship experience: proximity and engagement with the pulpit, choir / band / platform, communion / altar-call floor, AV, booth |
| `structural_engineering` | 15% | Grid, spans, load paths, lateral stability concept, connection logic, honesty about unverified sizes |
| `life_safety` | 15% | Exits, capacity, travel, stairs / rakes, protected routes, assumptions flagged; no claimed compliance |
| `accessibility` | 10% | Step-free routes, wheelchair space number / dispersion / sightlines, lifts, ramps, accessible WCs |
| `acoustics_av` | 10% | Room shape, volume per seat, reflections / focusing risks, screen and loudspeaker placement, sightlines to screens |
| `aesthetics` | 5% | Form, massing, interior character, facade and entrance quality as evidenced by the model and renders |
| `constructability_maintenance` | 10% | Buildability in Zimbabwe (materials, skills, crane / lifting, rainy season), roof drainage, maintenance access, durability |
| `cost_drivers` | 5% | Quantities that drive cost (roof area, steel length, footings, envelope, volume) - qualitative, no invented rates |

Weighted score = sum(score x weight / 100). **Critical blocker** (independent of score): seat count not exactly 3,000 or not
corroborated; unworkable or unflagged egress; model and reports materially disagree; fabricated compliance / calculations;
a defect that invalidates the concept (e.g. obstructed exits, impossible structure).

## Output (JSON written by the reviewer to the path the caller gives)

```json
{"design_id": "...", "revision": "...", "reviewer": "<discipline set>", "scores": {"architecture": 0.0, "...": 0.0},
 "weighted_score": 0.0, "critical_blockers": [{"id": "...", "finding": "...", "evidence": "file / element / value"}],
 "findings": [{"id": "...", "severity": "CRITICAL|MAJOR|MINOR", "discipline": "...", "finding": "...",
               "evidence": "file / element / value", "fix": "..."}],
 "strengths": ["..."], "limitations": "what the reviewer could not verify", "certification_disclaimer": "..."}
```

Reviewers must inspect actual files (manifest, reports, drawings, renders, IFC validation, layout source) and may run
read-only scripts in their own scratch folder. They must not edit any design, config, script or report.
