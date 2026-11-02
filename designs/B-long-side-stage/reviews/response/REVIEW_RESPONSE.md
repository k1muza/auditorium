# Option B proposal review response | B03-44bc3ae457

**Issue status:** preliminary concept feasibility, for review only, not for construction.  
**Evidence date:** 2 November 2026.  
**Source:** the saved B03 Blender manifest, source layout code and model-derived CSV/JSON reports. The script `../build_review_evidence.py` reproduces the tables and diagram in this folder without changing the building.

## Decision summary

The two critical findings are substantiated. The model reports 45.4 m maximum assigned plan travel within the hall against a **provisional screening flag** of 30 m. The seat-level bearing map reaches 79.98° from the pulpit; 772 of 3,000 congregation chairs exceed 60° bearing. Neither number by itself establishes legal non-compliance or unacceptable worship performance. The current seating geometry should remain B03 until the fire/life-safety designer and client agree on criteria and a response. A reduced fan, redistributed seats, additional exits or changed stage position could alter capacity, circulation and roof geometry, so no such change is made in this evidence issue.

An isolated fan-angle sensitivity check shows why a simple narrowing is not yet a resolved alternative. At ±75°, the engine keeps 3,000 congregation chairs but adds one row, grows the truss span to 54.0 m, increases screen reliance to 1,688 seats and generates 602 choir chairs under the unchanged choir rule. At ±70°, it reaches 55.9 m and a chair-footprint clash check fails. These unbuilt cases are recorded in `fan_sensitivity.csv`; the changing choir count makes them unsuitable for a like-for-like design comparison. Exit locations and a revised choir layout need coordinated study.

The occupancy ambiguity is resolved at the **model-count** level: 3,000 fixed congregation chairs **plus** 30 wheelchair places **plus** 30 companion chairs, 412 choir chairs, and assumptions of 60 platform and 30 BOH occupants. The provisional building load is **3,562**, of which **3,532** are assigned to hall-exit paths. It is not yet a certified design occupancy. Accessible-place provision and loading must be agreed with the fire and accessibility designers.

The reviewed **2,927.9 m² hall area** is traceable: `SP-01 + SP-02 + SP-03 + SP-04 = 2,927.89 m²`. It excludes the separately modelled `SP-02M` ministry floor (43.30 m²). Including that zone gives **2,971.19 m²**. The **4,244 m²** value is only the 80.0 m × 53.05 m *grid rectangle*, not a usable floor area. The reviewed **91.8 m × 79.55 m** is the bounding box of *all* envelope and floor objects in `comparisons/compare.py`, while the layout report's **89.1 m × 75.25 m** measures the narrower facade/grid extent. The reviewed **6,844.1 m²** sums all `ENV-ROOF` upward faces; **5,513.9 m²** is the main sloped roof plane alone. These are different, traceable measurement boundaries, not contradictory model revisions. A non-overlapping footprint/GFA schedule remains to be defined. The sum of `IfcSpace` areas cannot be used as GFA because gross foyer/corner zones contain smaller spaces.

## Evidence method and limits

| Claim | Source / method | Status |
|---|---|---|
| 3,000 congregation chairs | `model/blender_manifest.json` collection `40_SEAT_Congregation`; each `seating_schedule.csv` XY location cross-checked within 2 mm | Verified saved-object count and placement; not an occupancy approval |
| 45.4 m and 535 above flag | `reports/egress_travel.csv`; model `src/layout.py::egress()` follows row → aisle → passage → hall exit and balances exit assignments using placeholder width factors | Reproduced model result; path geometry, real stair travel, queues, door operation and final external discharge need independent fire review |
| 79.98° maximum, 772 seats above 60° | Angle between the saved pulpit and saved congregation chair XY coordinates; `seat_level_screen.csv` | Verified horizontal bearing only; obstruction, vertical sightline and stage action remain untested |
| Extreme-side concept view | Existing B03 `renders/.../04b_interior_from_side_seats.png`; camera starts at the westernmost chair at seated-eye height and uses an 18 mm lens | Useful qualitative view, but wide-angle lens is not a calibrated human field-of-view assessment |
| 1,564 screen-reliant seats | `geometry_checks.json` and `src/layout.py::sightline_checks()` using concept 30 m unaided limit and screen-angle/height rules | Model placeholder, not AV coverage validation |
| 2,927.89 m² legacy hall subtotal | Sum of named `IfcSpace` polygon areas in `space_schedule.csv`; excluding `SP-02M` | Reconciled to rounded reviewed value; area boundary must be drawn and classified |
| 53.05 m truss span | `geometry_checks.json` `truss_span`, grid 2→4 and 11 truss assemblies in saved manifest | Geometric span only; structural feasibility open |

The full source records and reproducible calculation are in `evidence_summary.json`, `seat_level_screen.csv`, `seating_block_screen.csv`, `occupancy_basis.csv`, `area_definitions.csv`, and `egress_and_bearing_maps.png`. All units and model revision are carried in those files. The 30 m and 60 m flags and width factors are **not Zimbabwean statutory criteria**.

The revised client-facing issue is `Option_B_Concept_Feasibility_Proposal.pdf` with a separate `Option_B_A3_Concept_Drawings.pdf`. `DRAWING_INDEX.md` and `PUBLICATION_QA.md` record the sheet references and rendering checks; `PROFESSIONAL_INPUTS.md` specifies the remaining inputs by owner.

**Follow-up concept comparison:** `CONCEPT_ALTERNATIVES.md` compares two exit-point screens, two narrower-fan layouts and a combined case with B03. The matrix and diagrams show that none resolves both critical findings; the exit cases require physical ramp and protected-passage redesign before they can be considered layouts.

## Finding register

| ID | Priority | Response and present status | Owner / acceptance evidence |
|---|---|---|---|
| R-01 | Critical | **Substantiated; open.** 45.4 m maximum within-hall plan travel; 459 people above the flag to their nearest hall exit and 535 above it after queue-balanced assignment. The route algorithm substitutes 8 m for L02 stair travel and does not model path bottlenecks or safe site discharge. | Fire/life-safety engineer: dimensioned seat-to-discharge paths, occupant and exit-capacity schedule, local design basis and review findings. |
| R-02 | Critical | **Substantiated; open.** Seat-level bearing p90 72.72°, maximum 79.98°; 1,362 chairs exceed 45° and 772 exceed 60° bearing. Bearing differs from chair-to-pulpit head turn. Obstruction, vertical view, representative seated views, screen visibility and choir orientation remain open. | Architect, worship/AV team and client: seat-view study, agreed performance criteria and stage/choir decision. |
| R-03 | High | **Geometric statement reconciled; engineering open.** 11 truss assemblies span 53.05 m grid 2→4. The “about 51 m / 3.0 m deep” text in the generated assumptions is stale; current model truss depth is 3.5 m. Member sections are visual placeholders. | Structural engineer: actions, analysis, stability and load-path diagram, reactions, connections, erection and feasibility quantities. |
| R-04 | High | **Reviewed discrepancy explained; full schedule open.** 2,927.89 m² omits 43.30 m² ministry zone. Grid rectangle is 4,244 m². The 91.8 × 79.55 m full envelope/floor box differs from the 89.1 × 75.25 m layout facade extent. The 6,844.1 m² all-roof area differs from the 5,513.9 m² main-plane area. `space_area_total_m2` includes overlapping gross/subzones and must not be reported as GFA. | Architect/BIM lead: non-overlapping net/gross area boundaries, drawing key and signed area definitions. |
| R-05 | High | **Model count resolved; design occupancy open.** 3,562 provisional people including additive wheelchair and companion positions and 90 assumed platform/BOH people. | Client, architect and fire engineer: approved room-by-room peak loads and consistent service, sanitation and egress basis. |
| R-06 | High | **Partly screened; open.** Ten hall exits and assigned loads are tabulated in `exit_schedule.csv`. Step-free routes, actual clear widths, protected back-of-house passage, accessible evacuation and external discharge have no professional verification. | Accessibility and fire team: continuous route/level plans, door and stair schedules, protection and refuge strategy. |
| R-07 | High | **Reclassified with four geometric drivers; measured estimate open.** The revised proposal calls the chapter “Model inventory and preliminary cost drivers” and adds modelled roof face area, footing solid volume and steel member centre-line lengths. These are not a bill or a priced estimate. | Quantity surveyor: classified take-off with units, specifications, methods, confidence, exclusions and local pricing basis. |
| R-08 | High | **Open.** The rear-wall treatment and display/speaker objects are allowances only. | Acoustician and AV designer: speech/reverberation/reflection study, coverage and rigging concept. |
| R-09 | Medium | **Open.** No movement joint is shown across 80 m; the main roof drains to one eaves line. Weirs are modelled but capacity is unknown. | Structural/envelope and civil engineers: thermal movement, primary/emergency drainage, rainfall and maintenance design. |
| R-10 | Medium | **Open.** No surveyed site or detailed MEP basis; plant room is an allowance. | Architect/MEP/civil team: site input register, utility and service loads, plant/shaft zones. |
| R-11 | Medium | **Partly addressed.** Four A3 landscape concept sheets are extracted as a separate PDF with a drawing index. Their pages render at A3, but minimum annotation size and drawing-scale accuracy still need a technical print audit. | Documentation lead: final print-scale QA, individual section numbers and drawing cross-reference audit. |
| R-12 | Low | **Editorial correction issued.** The revised 24-page proposal has aligned contents/body numbering and omits the two internal design-system pages. | Publication lead: final figure and table register check before client issue. |

## Design decisions and required inputs

1. **Client + fire designer:** select a statutory egress design basis and decide whether the hall needs more/redistributed exits or changed seating/rake/circulation. The 30 m placeholder is only a screening prompt.
2. **Client + architect/worship team:** agree what proportion of seats may rely on IMAG and acceptable direct view of preacher, platform and choir. Then compare the B03 fan against one or more revised layouts using the same seat-level methods.
3. **Client:** confirm the Option B choir orientation (412 chairs facing congregation), which departs from the previously recorded inward-facing preference.
4. **Professional team:** obtain site survey, geotechnical and rainfall inputs; establish structural actions, fire separation, accessible evacuation, acoustics/AV and MEP space needs before locking geometry.

## Change log

| Change | Result |
|---|---|
| Preserved B03 model, IFC, drawings and archived source | No geometric revision or safety claim introduced |
| Added reproducible seat-level bearing and travel schedules plus plan maps | R-01 and R-02 quantitatively substantiated; redesign remains a decision |
| Reconciled seat counts and provisional occupant loading | R-05 model ambiguity resolved; certified occupancy carried forward |
| Traced hall-area subtotal to source spaces and exposed ministry-floor omission | R-04 publication figure explained; full area schedule carried forward |
| Distinguished truss assemblies, object inventory and geometric cost drivers | R-03 and R-07 terminology clarified; engineering and pricing carried forward |
| Issued a revised 24-page feasibility proposal and separate four-sheet A3 concept set | R-11 partly addressed; R-12 editorial issue corrected |
| Ran unbuilt ±75° and ±70° fan-angle cases without changing B03 | Neither is a viable direct replacement; coordinated layout studies remain open |

**Independent review status:** This response is a traceable desktop recheck of the current B03 artefacts. It is not an independent professional certification or a replacement for the reviewer’s requested discipline studies.
