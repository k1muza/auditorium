# Open issues

> **Status: CONCEPT - UNVERIFIED - NOT FOR CONSTRUCTION.** Preliminary engineering-coordination model for discussion with a qualified architect and structural engineer. No structural analysis, code compliance check, fire/egress approval, geotechnical input or permit review has been performed. QA scores are not engineering approval.

Model revision: `IT01-45b0e08c36`

## Logged design issues (stage-excluded or requiring professional input)

| ID | Priority | Topic | Issue | Owner |
|---|---|---|---|---|
| OI-01 | CRITICAL-PATH | Local statutory review | Applicable Zimbabwean building, fire, occupancy and accessibility requirements have not been identified; all widths, distances, counts and gradients are unverified. | Local architect / fire engineer / authority |
| OI-02 | CRITICAL-PATH | Site | No site boundary, survey, setbacks, access, parking, contours or orientation. Footprint 59 x 88 m must be tested against an actual site. | Client / surveyor |
| OI-03 | CRITICAL-PATH | Geotechnics and foundations | No geotechnical report; foundation type, depth and sizes are reference placeholders only. | Geotechnical + structural engineer |
| OI-04 | CRITICAL-PATH | Structural design | No loads (dead, live, wind, seismic, rain/ponding), analysis, member design, connection design or deflection/vibration checks. 50 m truss span and lateral system require engineering development. | Structural engineer |
| OI-05 | MAJOR | Egress design | Exit widths, number of exits, travel distances, aisle widths and stair/ramp capacities are checked only against placeholder factors. Fire engineering / code-based egress design required. | Fire engineer / architect |
| OI-06 | MAJOR | Aisle steps | Rear-section aisle risers vary row by row (computed values in reports/row_schedule.csv); non-uniform risers, step nosings, handrails and lighting must be resolved in design development. | Architect |
| OI-07 | MAJOR | Cross-aisle riser | A single riser between the front-section slope and the cross aisle exists at aisle mouths (value in reports/geometry_checks.json); detail (ramp, step marking, handrail) required. | Architect |
| OI-08 | MAJOR | Ramps | Ambulatory ramp gradients/landings are generated against placeholder limits; handrails, edge protection and cross-falls not modelled. | Architect / access consultant |
| OI-09 | MAJOR | Acoustics and AV | No acoustic analysis (reverberation, noise, sound reinforcement) and no screen/AV design; rear-row viewing relies on screens assumption. | Acoustic / AV consultant |
| OI-10 | MAJOR | MEP and fire services | No HVAC, electrical, plumbing, drainage, fire detection/suppression, emergency lighting or hydrant design; only space allowances shown. | MEP engineers |
| OI-11 | MINOR | Sanitary fixtures | Toilet fixture counts and layouts not designed; blocks are area allowances. | Architect |
| OI-12 | MINOR | Envelope | Glazing, cladding, insulation, rainwater goods and roof drainage not designed. | Architect |
| OI-13 | MINOR | Cost | No cost plan; no budget provided. | Quantity surveyor |
| OI-14 | MINOR | Water storage | On-site water storage/backup power (often needed locally) not allocated - site dependent. | Client / MEP engineer |
| OI-15 | MINOR | IFC openings | Wall openings are modelled as geometric gaps with IfcOpeningElement voids; door/window types and fire ratings not assigned. | BIM coordinator |

## Automatically raised from model checks (WARN / FAIL in this revision)

| Check | Source | Result | Value | Criterion |
|---|---|---|---|---|
| EGR-01N Each hall exit width >= placeholder demand if everyone uses the NEAREST exit | geometry_checks.json | WARN | {"DR-HALL-W-FRONT": [366, 1.83, 3.6], "DR-HALL-W-WING": [100, 0.5, 2.4], "DR-HALL-W-CROSS": [1006, 5.03, 2.4], "DR-HALL-E-FRONT": [366, 1.83, 3.6], "DR-HALL-... | width >= load x 5 mm (placeholder) - informs exit-signage / door sizing |
| EGR-03 Max within-hall plan travel to a hall exit | geometry_checks.json | WARN | 53.27 | <= 30.0 m placeholder flag |
| EGR-04 Max plan travel to an external door | geometry_checks.json | WARN | 66.67 | <= 60.0 m placeholder flag |
| SGT-02 Min C-value over 2 rows in front (staggered seating) | geometry_checks.json | WARN | 0.1109 | >= 0.12 m |

## Notes on the egress warnings

- Within-hall plan travel reaches 53.3 m (queue-balanced) because the hall is 50 m wide and exits are on the side and rear walls. The 30 m / 60 m flags are placeholders, not local limits. Mitigations to be tested by the fire engineer: additional exits through the platform wings / stage rear, vomitories under the rear rake, sprinklers or smoke control as the local code allows, or a narrower/deeper plan.
- `EGR-01N` shows that if everyone used the nearest exit, the cross-aisle doors would be overloaded; the queue-balanced assignment is a heuristic and must be replaced by a code-based egress analysis.
- Restriction on use: until OI-01/OI-05 are closed, this layout must not be used to fix occupant capacity, exit provision or fire strategy.
