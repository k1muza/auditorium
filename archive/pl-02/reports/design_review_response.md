# Response to the independent design review

> **Status: CONCEPT - UNVERIFIED - NOT FOR CONSTRUCTION.** Preliminary engineering-coordination model for discussion with a qualified architect and structural engineer. No structural analysis, code compliance check, fire/egress approval, geotechnical input or permit review has been performed. QA scores are not engineering approval.

Review: output/independent_design_review (review of PL01-7cafe48b2e, 26 findings). Response revision: `PL02-18dac43917`. Every figure below is generated from this revision.

## Headline measurements (same method as the review)

| Measure | Review (PL01) | This revision |
|---|---:|---:|
| Seats > 45 deg off the pulpit | 542 | 466 |
| Seats > 60 deg off the pulpit | 184 | 108 |
| Seats > 70 deg off the pulpit | 24 | 0 |
| Worst angle to the pulpit | 72.58 deg | 66.17 deg |
| Seats without a usable pulpit or screen view | not measured | 0 |
| Wheelchair places on the lift-only upper level | 8 | 0 |
| Travel to the nearest hall exit (max) | 39.73 m | 39.73 m |
| Structural member ends not touching a support | gaps found | 0 |

Independent re-measurement with the review's own script: `reports/review_response_evidence/`.

## Finding-by-finding response

| Finding | Status | What was done | Evidence |
|---|---|---|---|
| STR-001 | ADDRESSED IN MODEL | Wall-brace ends now on the column faces, gable braces and struts touch the D/E posts, roof braces touch the top chords; portal frames identified with knee braces on grids 4-10 (A-27). New connectivity checks pass: 352 member ends, 0 gaps (STR-CON, BLD-CONNECT with a negative control). Analysis of the lateral system is still required. | reports/geometry_checks.json (STR-CON); reports/blend_verification.json (BLD-CONNECT) |
| STR-002 | OPEN - specialist input | No loads, analysis or member design are possible without site actions; logged as OI-04. The 6.5/9.5 m bay (needed to clear the cross-aisle exits) is retained and flagged for the economy study. | reports/open_issues.md |
| STR-003 | OPEN - specialist input | Footings remain reference locations pending a geotechnical investigation (OI-03); canopy posts now also have pad references. | reports/open_issues.md |
| STR-004 | PARTLY ADDRESSED | Screens and speaker arrays are modelled with 'rigging loads TBC' properties so the structural engineer can see where certified rigging points are needed; connection design is not modelled. | IFC SRV-AV-* |
| ARC-001 | ADDRESSED IN MODEL (client decision) | A 41st rear row was added and the 76 seats with the worst angle to the pulpit removed (still exactly 3,000). Seats > 45 deg: 466 (was 542); > 60 deg: 108 (was 184); > 70 deg: 0 (was 24); worst 66.17 deg (was 72.58). Every seat now has a usable view of the pulpit or a screen (SGT-H1: 0 without). Remaining screen-dependent seats logged as OI-19. | reports/geometry_checks.json (SGT-H1/SGT-H2); reports/review_response_evidence/ |
| ARC-002 | ADDRESSED IN MODEL | Six screens are now modelled: a 12.8 x 7.2 m centre LED wall over the band, two side screens and three delay screens at grid 6, plus speaker-array allowances (A-26). Screen package chosen by testing alternatives in the layout engine. | IFC SRV-AV-*; config av._screen_study |
| ARC-003 | ADDRESSED IN MODEL | Rear rows now rise with ONE uniform 0.150 m riser (no band changes), close to the 0.155 m cross-aisle step; central handrails in all front and rear aisles (10) and a step light at every aisle riser. Nosing contrast is a specification note for design development. | reports/row_schedule.csv; ARC-RAIL-AISLE-*; SRV-LIGHT-AISLE-* |
| ARC-004 | ADDRESSED IN MODEL | Choir access steps with 0.15 m risers, guards on the 1.8 m outer edges, handrails on the open sides and one wheelchair choir place per side. Also fixed a PL01 defect: the platform ramp and stair arrived into the choir tiers; they now arrive in the clear front zone (ACC-03). | ARC-STEPS-CHOIR-*; ARC-RAIL-CHOIR-*; ACC-WCS-CHOIR-* |
| LFS-001 | PARTLY ADDRESSED | Exit capacity now uses effective door widths and passes for queue-balanced and nearest-exit use; if everyone took the shortest route to outside, the cross-aisle exits would still be overloaded (EGR-01R) and travel to the nearest exit is still 39.73 m. A code-based evacuation study is still required (OI-05, OI-17). | reports/exit_schedule.csv; reports/open_issues.md |
| LFS-002 | ADDRESSED IN MODEL | Every exit is a door set: leaves <= 1.2 m, effective clear width = nominal - 0.08 m per leaf, outward-opening with panic hardware (A-25); IFC Pset_DoorCommon FireExit set; all capacity checks use the effective widths. | reports/exit_schedule.csv |
| LFS-003 | ADDRESSED IN MODEL (client decision) | No wheelchair places on the lift-only upper level any more; they moved to the mid band, which has a direct outside ramp. Four refuge allowances remain at the stair heads for anyone on the upper foyer who cannot use stairs; their protection is still for the fire engineer (OI-16). | reports/accessible_positions.csv |
| LFS-004 | ADDRESSED IN MODEL | Both cross-aisle landings now have a direct 1:12 outside ramp (15.3 m, 2 flights with a 1.5 m landing) next to the steps, so the mid-band wheelchair places reach grade step-free (ACC-06). Flat grade assumed. | ARC-RAMP-EXT-* |
| LFS-005 | ADDRESSED IN MODEL | The 30 BOH staff are now in the occupant tally (3,290, reconciling with A-16) and checked against the BOH corridor doors (EGR-07). | reports/geometry_checks.json (EGR-07) |
| LFS-006 | PARTLY ADDRESSED | Each of the four foyer accessible WCs is now its own room with its own door from the main foyer, and a new check confirms every enclosed room has a door (SPC-03). Fixtures, grab rails and transfer space still need design. | reports/space_schedule.csv |
| LFS-007 | OPEN - specialist input | Fire detection, alarm, signage, suppression and smoke control need a fire strategy (OI-20); only aisle step-light allowances are modelled. | reports/open_issues.md |
| MEP-001 | OPEN - specialist input | Ventilation and thermal design need a mechanical engineer (OI-20). | reports/open_issues.md |
| MEP-002 | PARTLY ADDRESSED | Speaker-array allowances are modelled; acoustic treatment needs an acoustic study (OI-09). | SRV-AV-SPEAKER-* |
| MEP-003 | PARTLY ADDRESSED | Roof drainage concept modelled: hall eaves gutters, ambulatory gutters and 28 downpipes. Sizes, overflows and roof access are still to be designed (OI-21). | SRV-GUTTER-*; SRV-DOWNPIPE-* |
| MEP-004 | OPEN - specialist input | Power, backup, earthing, lightning protection and lighting need an electrical engineer (OI-20). | reports/open_issues.md |
| AES-001 | PARTLY ADDRESSED | A continuous 59 m x 4 m entrance canopy on slender posts (the review's low-cost option) now shades the main doors. Forecourt, drop-off and identity need the site. | ENV-CANOPY-ENTRANCE |
| CST-001 | OPEN - specialist input | Erection, splices and crane access need a fabricator/erector study (OI-21). | reports/open_issues.md |
| CST-002 | OPEN - specialist input | High-level maintenance access needs a maintainability plan (OI-21). | reports/open_issues.md |
| SIT-001 | OPEN - site data required | No site has been identified; orientation, discharge and civil design remain blocked (OI-02). | reports/open_issues.md |
| BIM-001 | ADDRESSED | The stale viewing copy was deleted; the viewing copy is now regenerated with each revision and carries the revision ID in its file name. | renders/ |
| BIM-002 | ADDRESSED | Structural connectivity is now checked in the generator (STR-CON) and independently in the Blender verifier (BLD-CONNECT), with a negative control. | reports/blend_verification.json |
| BIM-003 | ADDRESSED | model_index.md is written before the hashes are captured, so the revision register matches the files. | reports/model_revision.json |

## Summary

| Status | Findings |
|---|---:|
| ADDRESSED | 3 |
| ADDRESSED IN MODEL | 9 |
| OPEN - site data required | 1 |
| OPEN - specialist input | 7 |
| PARTLY ADDRESSED | 6 |

Findings marked OPEN need information or specialist work that this model cannot supply (site survey, geotechnics, loads, fire strategy, MEP design). They are logged in open_issues.md with owners, not answered with invented values. This revision has not been independently re-reviewed.
