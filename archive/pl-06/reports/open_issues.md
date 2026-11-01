# Open issues

> **Status: CONCEPT - UNVERIFIED - NOT FOR CONSTRUCTION.** Preliminary engineering-coordination model for discussion with a qualified architect and structural engineer. No structural analysis, code compliance check, fire/egress approval, geotechnical input or permit review has been performed. QA scores are not engineering approval.

Model revision: `PL06-966bde8984`

## Logged design issues (stage-excluded or requiring professional input)

| ID | Priority | Topic | Issue | Owner |
|---|---|---|---|---|
| OI-01 | CRITICAL-PATH | Local statutory review | Applicable Zimbabwean building, fire, occupancy and accessibility requirements have not been identified; all widths, distances, counts and gradients are unverified. | Local architect / fire engineer / authority |
| OI-02 | CRITICAL-PATH | Site | No site boundary, survey, setbacks, access, parking, contours or orientation. Footprint 59 x 88 m must be tested against an actual site. | Client / surveyor |
| OI-03 | CRITICAL-PATH | Geotechnics and foundations | No geotechnical report; foundation type, depth and sizes are reference placeholders only. | Geotechnical + structural engineer |
| OI-04 | CRITICAL-PATH | Structural design | No loads (dead, live, wind, seismic, rain/ponding), analysis, member design, connection design or deflection/vibration checks. 50 m truss span and lateral system require engineering development. | Structural engineer |
| OI-05 | MAJOR | Egress design | Exit widths, number of exits, travel distances, aisle widths and stair/ramp capacities are checked only against placeholder factors. Fire engineering / code-based egress design required. | Fire engineer / architect |
| OI-06 | MAJOR | Aisle steps | Rear-section aisle steps use ONE uniform riser for all rear rows (A-22, single band) and the going is 0.95 m; concept handrails and step lights are modelled as allowances - nosings, handrail detail, photometrics and code acceptance of the riser/going must be resolved in design development. | Architect |
| OI-07 | MAJOR | Cross-aisle riser | A single riser between the front-section slope and the cross aisle exists at aisle mouths (value in reports/geometry_checks.json); detail (ramp, step marking, handrail) required. | Architect |
| OI-08 | MAJOR | Ramps | Ambulatory ramp gradients/landings are generated against placeholder limits; handrails, edge protection and cross-falls not modelled. | Architect / access consultant |
| OI-09 | MAJOR | Acoustics and AV | No acoustic analysis (reverberation, noise, sound reinforcement) and no screen/AV design; rear-row viewing relies on screens assumption. | Acoustic / AV consultant |
| OI-10 | MAJOR | MEP and fire services | No HVAC, electrical, plumbing, drainage, fire detection/suppression, emergency lighting or hydrant design; only space allowances shown. | MEP engineers |
| OI-11 | MINOR | Sanitary fixtures | Toilet fixture counts and layouts not designed; blocks are area allowances. | Architect |
| OI-12 | MINOR | Envelope | Glazing, cladding, insulation, rainwater goods and roof drainage not designed. | Architect |
| OI-13 | MINOR | Cost | No cost plan; no budget provided. | Quantity surveyor |
| OI-14 | MINOR | Water storage | On-site water storage/backup power (often needed locally) not allocated - site dependent. | Client / MEP engineer |
| OI-15 | MINOR | IFC openings | Wall openings are modelled as geometric gaps with IfcOpeningElement voids; door/window types, hardware and fire ratings not assigned. Storeys are height datums (see basis_of_design.md section 6). | BIM coordinator |
| OI-16 | MAJOR | Refuge and assisted evacuation | Refuge spaces are space allowances on the open upper foyer; protected enclosure, communication, evacuation lift and management plan are not designed. | Fire engineer / architect |
| OI-17 | MAJOR | Travel distance in a 50 m wide hall | Front-section centre seats are ~25 m laterally from any side-wall exit; no central exit is possible in front of the platform. Measured distances exceed the 30 m placeholder flag; options (vomitories under rear rake, narrower/deeper plan, sprinklers/smoke control per local code) need fire-engineering assessment. | Fire engineer / architect |
| OI-18 | MINOR | Choir | Choir in four zones round the platform sides at hall-floor level, angled towards the pulpit (client decision PL06), with a wheelchair choir place each side; the choir looks up at a 0.90 m platform from the side, and its occupants now count in the egress tally. Choir size, sightlines to the congregation, platform edge protection and choir/band acoustic arrangement still to be confirmed by the client / architect / acoustician. | Architect / client |
| OI-19 | MAJOR | Remaining off-axis seats | After trimming, some side seats are still more than 45 deg off the pulpit; they rely on the IMAG screens (values in reports/geometry_checks.json). A fanned bowl was not studied. | Architect / AV consultant |
| OI-20 | CRITICAL-PATH | Fire systems and building services | Detection, alarm, emergency lighting, exit signs, suppression, smoke control, ventilation, power resilience, earthing and lightning protection are not designed (review LFS-007, MEP-001/004). | Fire / MEP engineers |
| OI-21 | MAJOR | High-level maintenance and erection | Roof access, catwalks, MEWP routes, truss splices, crane access and temporary stability are not designed (review CST-001/002). | Architect / structural engineer / contractor |

## Automatically raised from model checks (WARN / FAIL in this revision)

| Check | Source | Result | Value | Criterion |
|---|---|---|---|---|
| EGR-01R Sensitivity: exit width if everyone takes the shortest route to an EXTERNAL door | geometry_checks.json | WARN | {"DR-HALL-W-FRONT": [328, 1.64, 3.36], "DR-HALL-W-WING": [195, 0.975, 2.24], "DR-HALL-W-CROSS": [817, 4.085, 3.36], "DR-HALL-E-FRONT": [328, 1.64, 3.36], "DR... | width >= load x 5 mm (placeholder) - cross-aisle exits attract this route (OI-17) |
| EGR-03N Max within-hall plan travel to the NEAREST hall exit | geometry_checks.json | WARN | {"max_m": 39.73, "occupants_over_flag": 330} | <= 30.0 m placeholder flag (OI-17) |
| EGR-03 Max within-hall plan travel to the queue-balanced hall exit | geometry_checks.json | WARN | 50.42 | <= 30.0 m placeholder flag |
| EGR-04 Max plan travel to an external door | geometry_checks.json | WARN | 61.12 | <= 60.0 m placeholder flag |
| SGT-H2 Seats more than 60 deg off the pulpit (after trimming the worst seats) | geometry_checks.json | WARN | 108 | 0 (remaining seats are screen-dependent; OI-19) |

## Notes on the egress warnings

- Plan travel to the NEAREST hall exit reaches 39.7 m (330 occupants beyond the 30 m placeholder flag); to the queue-balanced exit 50.4 m. This is because the hall is 50 m wide and exits are on the side and rear walls. The 30 m / 60 m flags are placeholders, not local limits. Mitigations to be tested by the fire engineer: additional exits through the platform wings / stage rear, vomitories under the rear rake, sprinklers or smoke control as the local code allows, or a narrower/deeper plan.
- `EGR-01N` / exit_schedule.csv column `placeholder_check_if_nearest` show which doors would be overloaded if everyone used the nearest exit (iteration 2 widened the cross-aisle exits to 3.6 m by moving grid 6 to y=38.5); the queue-balanced assignment is a heuristic and must be replaced by a code-based egress analysis.
- Restriction on use: until OI-01/OI-05 are closed, this layout must not be used to fix occupant capacity, exit provision or fire strategy.
