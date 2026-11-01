# Assumptions register

> **Status: CONCEPT - UNVERIFIED - NOT FOR CONSTRUCTION.** Preliminary engineering-coordination model for discussion with a qualified architect and structural engineer. No structural analysis, code compliance check, fire/egress approval, geotechnical input or permit review has been performed. QA scores are not engineering approval.

Model revision: `IT02-325e67e273` - source of truth: `config/auditorium_params.json` (edit there and regenerate with `scripts/run_pipeline.py`).

| ID | Topic | Assumption | Basis / source | Status | Confidence |
|---|---|---|---|---|---|
| A-01 | Site | Flat site; external grade = Level 00 (0.000) on all sides | No survey/contours provided | Concept assumption | Low |
| A-02 | Orientation | Project north = +Y (towards platform); true north unknown | No site/orientation data | Concept assumption | Low |
| A-03 | Seat module | 0.50 m seat centres, 0.60 m chair depth, 0.95 m row pitch (0.35 m clear seatway, seats down) | Common auditorium practice; not checked against local code | Concept assumption - verify | Medium |
| A-04 | Seats between aisles | Max 14 seats between two aisles (7 to nearest aisle); 10 seats in side blocks | Conventional (non-continental) seating practice; local rule unknown | Concept assumption - verify | Medium |
| A-05 | Aisle widths | 1.50 m interior aisles (1.25 m straight clear path with 0.25 m row stagger); wall aisles >= 1.825 m to column faces (computed) | Concept allowance; statutory widths depend on occupant load and local code | Concept assumption - verify | Medium |
| A-06 | Sightlines | C-value 0.06 m over row in front AND 0.12 m over the row two in front (staggered seats, 0.25 m offset); focal point 0.6 m above platform front edge; seated eye 1.15 m, wheelchair eye 1.20 m | Typical concept sightline criteria; client/architect to confirm focal point (screens assumed for rear rows) | Concept assumption - verify | Medium |
| A-07 | Platform | Platform +0.90 m above front floor, 30 m x 12 m, choir risers 3 tiers (~144 choir seats, excluded from 3,000) | Brief requires large platform/choir; size is a concept allowance | Concept assumption | Medium |
| A-08 | Wheelchair positions | 30 wheelchair spaces (approx. 1% of 3,000) each with an adjacent loose companion chair, dispersed front / mid cross-aisle / rear; these are IN ADDITION to the 3,000 fixed congregation seats | Placeholder fraction; local accessibility requirement unknown | Concept assumption - verify | Low |
| A-09 | Egress capacity factors | 5.0 mm/person level routes and doors, 7.5 mm/person stairs used ONLY to flag obvious under-provision; exit loads from a queue-balanced assignment (walk 1.0 m/s, door flow 1.3 p/m/s) and also reported for nearest-exit use | Placeholder; NOT a local code value | Placeholder - must be replaced by local code | Low |
| A-10 | Travel distance flags | Flag within-hall plan travel > 30 m and total plan travel to an external door > 60 m | Placeholder flags only; local limits unknown | Placeholder - must be replaced by local code | Low |
| A-11 | Primary structure | Steel roof trusses spanning 50 m at 8 m centres on steel columns; truss depth 1.5 m eaves / 3.5 m ridge (span/14 at ridge) | Concept proportioning rule of thumb; no loads, analysis or member design | Concept assumption - engineer to develop | Low |
| A-12 | Member sizes | Columns 0.6 m (hall) / 0.4 m (other), chords 0.35 m, webs 0.20 m, braces 0.15 m are SPACE-RESERVATION placeholders, not designed sizes | No analysis performed | Placeholder | Low |
| A-13 | Lateral stability | Transverse: truss-to-column portal action (moment knee) with braced gable bays as alternative/supplement; longitudinal: vertical X-bracing in end bays; roof plane bracing in end and middle bays | Concept scheme only; wind/seismic actions unknown | Concept assumption - engineer to confirm | Low |
| A-14 | Foundations | Pad footing REFERENCE locations under each column (2.4 m / 1.8 m square x 0.6 m, top at -0.90 m) - indicative only | No geotechnical report; bearing capacity unknown | Placeholder - geotechnical input required | Low |
| A-15 | Levels | Level 00 = 0.000 finished floor (foyer, front of hall, ambulatory ends, BOH); cross-aisle and upper foyer levels computed by sightline generator | Generated | Model-derived | High |
| A-16 | Occupancy for egress flagging | 3,000 fixed seats + 30 wheelchair + 30 companion + 200 platform/choir + 30 staff/BOH | Concept tally; legal occupant load to be set by local authority/fire engineer | Concept assumption - verify | Medium |
| A-17 | Toilet provision | Two foyer toilet blocks (~65 m2 each) + 4 foyer accessible WCs + BOH accessible WC and staff WCs as SPACE ALLOWANCES; fixture counts not determined | Local sanitary provision rules unknown | Allowance - verify | Low |
| A-18 | Materials | Steel frame, masonry/infill walls and metal roof assumed for space planning only | No material/procurement brief | Concept assumption | Low |
| A-19 | Services | MEP plant room, roof plant, risers and AV/lighting rig shown as space allowances only | No MEP design at this stage | Allowance | Low |
| A-20 | Option choice | Option A single-level raked hall selected over Option B floor + balcony for this milestone (see basis_of_design.md comparison) | Concept comparison; client/architect decision pending | Recommendation - pending client review | Medium |
| A-21 | Refuge / assisted evacuation | Wheelchair users on the rear platform / upper foyer (+L02) wait in refuge spaces beside each foyer stair head and are evacuated by assisted means or a designated evacuation lift; refuge enclosure / fire separation not yet designed | No fire strategy yet; required to make upper-level wheelchair spaces workable | Concept assumption - fire engineer to confirm | Low |
| A-22 | Rear aisle steps | Rear rake = one transition row off the cross aisle + 2 bands of 10 rows, each band with ONE uniform riser (one riser per row, 0.95 m going); riser changes only at the 2 band boundaries (values in reports/geometry_checks.json) | Concept detailing rule to keep aisle risers uniform; local stair/aisle-step rules unknown | Concept assumption - verify | Medium |
| A-23 | IFC materials | Placeholder material names (steel / concrete / masonry / metal roof - grades TBC) assigned in IFC for quantity take-off structure only | No material specification | Placeholder | Low |

## Missing inputs (from DESIGN_BRIEF.md) - NOT invented
- Site boundary/survey, setbacks, zoning, access/parking, orientation, contours -> A-01, A-02, OI-02
- Geotechnical report, bearing/settlement criteria -> A-14, OI-03
- Local building, fire, occupancy and accessibility requirements -> A-04..A-10, OI-01, OI-05
- Budget, target footprint, materials, procurement -> A-18, OI-13
- Loading, wind, rain, seismic, material grades, design standards -> A-11..A-13, OI-04
