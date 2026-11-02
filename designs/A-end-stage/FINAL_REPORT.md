# Final report: 3,000-seat church auditorium concept BIM

## Status: `NOT_ACCEPTED_FOR_THIS_MILESTONE`

- **Final score:** 8.79 / 10 for revision `IT03-1e06f520e1`. The acceptance threshold is strictly above 9.0.
- **Critical blockers:** none.
- **Iterations:** 3 of 3 used. Under the loop rules there is no fourth attempt.

This is a preliminary model for coordinating the design between disciplines. **No professional engineering, fire or egress, accessibility or code-compliance approval has been given, implied or obtained.** The QA score measures the quality of the model only. It is not evidence of structural safety, compliance, permit readiness or construction readiness.

## Score trend

The independent `bim-reviewer` scored each iteration. `scripts/evaluate_review.py` computed the weighted score, and the builder re-ran it to confirm.

| Iteration | Model revision | Seating | Circulation and access | Structure | BIM data | Reproducibility | Docs | Validation | **Weighted** | Blockers |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | IT01-45b0e08c36 | 9.0 | 7.3 | 8.5 | 8.0 | 9.4 | 8.5 | 8.8 | **8.405** | 0 |
| 2 | IT02-325e67e273 | 9.3 | 7.2 | 8.6 | 8.9 | 9.5 | 8.5 | 8.6 | **8.585** | 0 |
| 3 | IT03-1e06f520e1 | 9.3 | 7.6 | 8.9 | 9.1 | 9.5 | 8.7 | 8.9 | **8.790** | 0 |

The review reports are `reviews/iteration-01.json`, `reviews/iteration-02.json` and `reviews/iteration-03.json`. The reviewers' scripts and outputs are in `reviews/iteration-0N-work/`.

## Findings still open in the final revision (from `reviews/iteration-03.json`)

### MAJOR

1. **The four accessible WCs in the foyer have no door. This was introduced in iteration 3.**
   - In iteration 3 the toilet entrances were moved to the side passages. That left `SPC-SP-WCA-W` and `SPC-SP-WCA-E` enclosed by partitions with no door.
   - Assumption A-17 still claims four accessible WCs in the foyer.
   - No check covered "every room reachable through a door".
   - Fix: give each accessible WC its own door from the public circulation, and add a check that every room can be reached.
2. **Travel distance and exit loading in a 50 m-wide hall.**
   - Travel to the nearest hall exit reaches 39.7 m, and 330 occupants are beyond the 30 m placeholder flag.
   - With the queue-balanced exit allocation, travel reaches 50.9 m to a hall exit and 61.2 m to an external door.
   - If everyone takes the shortest route to the outside, each cross-aisle exit carries about 1,030 people against 3.6 m of width.
   - This is logged as OI-05 and OI-17, with a restriction on use. No layout fix has been modelled: options include vomitories, extra exits, or a narrower and deeper plan.

### MINOR
- **Foyer stairs:** they pass 10 mm from columns B2, D2, E2 and G2, and have no guards or handrails on their open sides.
- **Gable bracing:** the struts and brace planes sit 10 mm off the D/E posts, so the load path isn't physically connected in the model. Portal knee bays are not identified.
- **Stair and ramp quantities:** these come from bounding boxes and contradict the elements' own properties (width 2.76 vs 2.7; ramp rise 1.4 vs 1.15).
- **Flashings:** they have no relationship to their walls in the IFC (no IfcRelCoversBldgElements).
- **Rear-stair capacity check (EGR-02):** uses the queue-balanced rear load (993). The nearest-exit rear load is 1,254, needing 9.41 m of stair width, which still fits within the 10.8 m provided. The EGR-01N note in `open_issues.md` is out of date.
- **`upper_foyer_plan.png`:** the stair-head openings aren't dimensioned, and the seating overprints some grid bubbles.

## What was verified (by the builder's checks and independently by the reviewers)

- **Seat count:** exactly **3,000** congregation seats. Layout engine, Blender scene, saved `.blend` re-opened, IFC and `reports/seating_schedule.csv` all agree, seat by seat (coordinates within 2 µm). See `reports/seat_count_check.txt`.
- **Clashes:** 0 hard clashes in the clash matrix, with positive and negative controls. Every chair sits on a floor (raycast). See `reports/blend_verification.json`.
- **Sightlines:** every row clears the head in front by at least C = 0.06 m, and the head two rows ahead by at least 0.12 m. The wheelchair positions meet C ≥ 0.06 m.
- **IFC4:**
  - 0 schema-validation messages;
  - every product tessellates;
  - each element's storey matches its height when re-derived from the geometry;
  - materials and quantities are present;
  - all 42 doors and windows fill openings in their host walls.
  See `reports/ifc_validation.json`.
- **Reproducibility:** two independent headless rebuilds produce byte-identical manifests (`reports/regeneration_check.json`), and the reviewers reproduced the same hash. 28 unit tests pass.

## Files

**Present:**
- **Model:** `model/church_3000_concept.blend`, `model/church_3000_concept.ifc` (IFC4), and `model/blender_manifest.json` (the scene data exported from Blender, which feeds the IFC export and the drawings).
- **Sources:**
  - `config/auditorium_params.json` (all parameters, the assumptions register and the open-issues list);
  - in `scripts/`: `auditorium_layout.py`, `build_auditorium.py`, `verify_blend.py`, `export_ifc.py`, `validate_ifc.py`, `make_drawings.py`, `generate_reports.py`, `run_pipeline.py` and `evaluate_review.py` (provided with the project);
  - `tests/test_layout.py`.
- **Reports:**
  - schedules: `seating_schedule.csv`, `space_schedule.csv`, `row_schedule.csv`, `exit_schedule.csv`, `accessible_positions.csv`, `element_schedule.csv`;
  - design documents: `assumptions.md`, `open_issues.md`, `basis_of_design.md`;
  - checks and validation: `seat_count_check.txt`, `geometry_checks.json`, `blend_verification.json`, `ifc_validation.json`, `regeneration_check.json`;
  - `environment.json`, `model_revision.json` (SHA-256 of every output) and `model_index.md`.
- **Exports:** `floor_plan.png`, `structural_grid.png`, `upper_foyer_plan.png`, `long_section.png`, `balcony_option_section.png` (Option B, computed schematic only), `model_axonometric.png` and `model_cutaway.png` (Blender renders).
- **Evidence:**
  - build logs per iteration in `logs/iteration-0N/` (unit tests, Blender build, regeneration build, .blend verification, IFC export and validation, drawings, reports);
  - outputs of every iteration preserved in `archive/iteration-0N/`;
  - reviews in `reviews/`.

**Missing:**
- Nothing required by the brief is missing.
- The IFC was not written by a Blender IFC add-on (Bonsai is not installed). It was generated with IfcOpenShell from the scene data exported out of the saved Blender model.

## Tooling (stated truthfully)

- **Blender:** **no Blender MCP connection was available in this session.** Blender 5.2.3 LTS was run headless from the command line (`blender --background --python ...`). The model, the renders and the verification all ran in real Blender.
- **Python tools:** IfcOpenShell 0.8.5 and matplotlib 3.10.9, installed in the project's own `.venv`.
- **To reproduce:** `.venv\Scripts\python.exe scripts\run_pipeline.py --iteration N` (takes about 3–8 minutes).

## What a local architect or engineer must verify next

1. Identify the Zimbabwean building, fire, occupancy and accessibility requirements that apply, and replace every placeholder:
   - exit capacity factors and travel flags;
   - aisle, ramp and stair rules;
   - wheelchair and refuge numbers;
   - sanitary fixture counts.
2. Commission a fire-engineering egress strategy. The 50 m-wide hall exceeds the placeholder travel flags, and the cross-aisle exits are sensitive to how people choose routes. Refuge enclosures and assisted evacuation also need to be designed.
3. Fix the defects listed above, starting with the doors to the accessible WCs.
4. Obtain a site survey and orientation, and check that the 59 × 88 m footprint fits, along with access, parking and external levels. The external steps assume a flat site.
5. Carry out the structural design:
   - the loads to design for (wind, seismic, live, roof);
   - the design of the 50 m trusses and the lateral system, including physical connection of the bracing and struts;
   - deflection and ponding checks;
   - foundations, based on a geotechnical report.
6. Make the client decision between Option A (single level, recommended for this milestone) and Option B (floor plus balcony).
7. Commission acoustic, AV and screen design for the rear rows (maximum viewing distance 44.5 m), MEP design, water storage, backup power, and a cost plan.

---

## Post-loop revision PL01 (2026-11-01): NOT independently reviewed

At the client's request, made after the 3-iteration loop closed:
- **Choir moved:** removed from the rear of the platform and placed on its **two sides, facing inward** across it. There are two sections, each with 3 tiers of 24 chairs (144 in total, still excluded from the 3,000).
- **Platform:** now extends to the stage rear wall (30 × 15.6 m), with a 22.8 m clear centre and the rear kept for the band.
- **Records updated:** the design decision is noted in `DESIGN_BRIEF.md`; assumption A-07 and new open issue OI-18 (choir tier steps, handrails, accessible choir place) are in the config.

**Revision ID:** `PL01-7cafe48b2e`, built with `scripts/run_pipeline.py --iteration 1 --tag PL`.

**Builder checks:**
- 30/30 unit tests pass;
- Blender verification 17/17 PASS (0 clashes);
- IFC validation 21/21 PASS;
- seat count PASS (exactly 3,000);
- regeneration byte-identical.

**What these files now contain:**
- `model/`, `reports/`, `exports/` and `logs/pl-01/` now hold **PL01**, with a copy in `archive/pl-01/`.
- The **independently reviewed** revision is still `IT03-1e06f520e1`, preserved unchanged in `archive/iteration-03/`.
- PL01 has **no review score**. The iteration-3 status, `NOT_ACCEPTED_FOR_THIS_MILESTONE` at 8.79, still applies, and none of the iteration-3 findings were addressed in PL01.

**Renders:** `renders/PL01/stage_aerial.png` and `renders/PL01/stage_from_congregation.png`.

---

## Post-loop revision PL02 (2026-11-01): response to the independent design review, NOT independently re-reviewed

This revision answers all 26 findings in `output/independent_design_review/`, which reviewed PL01. The answers are in **`reports/design_review_response.md`**:
- 12 addressed;
- 6 partly addressed;
- 8 still open, because they need a site, soil data, loads or specialist design. Those are logged with owners.

**Client decisions in this revision:**
- No wheelchair places on the lift-only upper level. They moved to the mid band, which now has a direct outside ramp.
- The 76 seats with the worst angle to the pulpit were removed, replaced by a 41st rear row, still exactly 3,000.
- A simpler foyer: two wide central stairs.

**Results, re-measured with the review's own script (`reports/review_response_evidence/`):**

| Measure | PL01 | PL02 |
|---|---|---|
| Seats > 45° off the pulpit | 542 | 466 |
| Seats > 60° off the pulpit | 184 | 108 |
| Seats > 70° off the pulpit | 24 | 0 |
| Worst angle to the pulpit | 72.6° | 66.2° |
| Seats with no usable pulpit or screen view | — | 0 |
| Disconnected brace/strut ends | gaps | 0 |

**Revision ID:** `PL02-18dac43917`.

**Checks:**
- 35/35 unit tests;
- Blender verification 18/18, including 0 clashes and structural connectivity;
- IFC validation 21/21;
- seat count exactly 3,000 in every source;
- regeneration identical;
- revision register hashes all match.

**Still open:**
- Escape-route travel (39.7 m to the nearest exit) and cross-aisle crowding if everyone takes the shortest route outside still need a fire engineer.
- Structure, foundations, fire systems, building services and the site remain specialist or site inputs.

**Viewing copy and renders:**
- The model's viewing copy is `renders/church_3000_concept_PL02-18dac43917_VIEWING_COPY.blend`.
- Current renders are in `renders/`; earlier renders are in `renders/PL01-7cafe48b2e/` and `renders/IT03-1e06f520e1/`.

## Post-loop revision PL03 (2026-11-01): choir seating removed; response to the independent re-review, NOT independently re-reviewed

**Re-review of PL02** (`output/independent_design_review_recheck/RECHECK_REVIEW.md`):
- It scored PL02 **6.0/10**, up from 4.7. That review uses its own eight-discipline scale, separate from the QUALITY_RUBRIC evaluator.
- Its seven residual findings are answered in `reports/design_review_response.md` (section "Independent re-review").
- R2-BIM-01 (stale register wording) is fixed: OI-06 now states the single uniform rear riser band.
- The other six findings stay OPEN because they need specialist or site input: evacuation analysis, structural design, MEP, an AV/sightline study, the site, and roof maintenance access.

**Client decision:** the fixed choir chairs and side choir risers are removed from the platform. The whole 30 m platform is one open level for the choir (loose chairs or standing) and the band, reached step-free by the 1:12 ramp. Removed from the model: 144 choir chairs, 6 risers, 2 step flights, 4 rails and 2 choir wheelchair places. The platform occupant allowance (200) used for egress is unchanged.

**Revision ID:** `PL03-3e57114669`.

**Checks:**
- 35/35 unit tests;
- Blender verification 18/18 (0 clashes);
- IFC validation 21/21;
- exactly 3,000 seats in every source;
- regeneration identical.

**Re-review audit script:** run from a copy in `reports/recheck_response_evidence/` (created after the hash register was written). It confirms:
- no choir objects;
- 3,000 seats;
- 30 congregation wheelchair places;
- sightlines unchanged (466 seats > 45°, 108 seats > 60°, worst angle 66.17°).

**Renders:** current renders are in `renders/`. The PL02 renders, including the side-choir stage views, are in `renders/PL02-18dac43917/`. The 360 video has not been re-rendered for PL03.

## Post-loop revision PL04 (2026-11-01): choir in the platform wings, NOT independently re-reviewed

**Client decision:** 144 choir chairs are placed in the two platform wings on the hall floor, beside the stage. Each side has 72 chairs (6 rows of 12) facing inward towards the platform. The platform stays one open level for the band.

**Details:**
- The choir is step-free, with one wheelchair choir place in each wing.
- Each block keeps at least 1.2 m clear of the platform, the platform stair and ramp, walls, columns, the wing exit doors and the backstage doors (new check ACC-07).
- Choir seats remain excluded from the 3,000.

**Revision ID:** `PL04-7e854e086c`.

**Checks:**
- 37/37 unit tests;
- Blender verification 18/18 (0 clashes);
- IFC validation 21/21;
- exactly 3,000 congregation seats in every source;
- regeneration identical.

**Unchanged warnings:** EGR-01R, EGR-03N, EGR-03 and SGT-H2 (see PL02).

**Renders:** current renders are in `renders/`. The PL03 renders are in `renders/PL03-3e57114669/`. The 360 video has not been re-rendered since PL02.

## Post-loop revision PL05 (2026-11-02): smaller platform, NOT independently re-reviewed

**Client decision:** the platform is reduced from 30.0 × 15.6 m (about 468 m²) to **20.0 m wide × 10.0 m deep (200 m²)**. These stay the same:
- the front edge;
- the centre line;
- the +0.90 m height;
- the pulpit position;
- the 3,000 seats and their sightlines.

**Knock-on changes:**
- The platform stair and the 1:12 ramp moved in with the platform's side edges.
- The wing choir blocks (144 chairs) moved forward to sit alongside the platform.
- The freed floor is left empty, as instructed. Behind the platform it is a new unallocated space, SP-02B (117 m²). The wings are now 235 m² each.

**Revision ID:** `PL05-cba999fc37`.

**Checks:**
- 37/37 unit tests;
- Blender verification 18/18 (0 clashes);
- IFC validation 21/21;
- exactly 3,000 congregation seats in every source;
- regeneration identical.

**Warnings:** unchanged.

**Renders:** current renders are in `renders/`. The PL04 renders are in `renders/PL04-7e854e086c/`. The 360 video has not been re-rendered since PL02.

## Post-loop revision PL06 (2026-11-02): choir round the platform sides, NOT independently re-reviewed

**Client decision (from a plan mark-up):** the choir fills four zones beside the platform: a lower and an upper block on each side, **329 chairs** in total.
- West: 50 + 129 chairs. East: 45 + 105 chairs. The east side is smaller because of the ramp.
- All chairs are on the hall floor and angled towards the pulpit.
- Rows hold at most 13 chairs and are reached from a passage at each end.

**Kept clear (new check ACC-07):**
- a 2.4 m corridor along each hall wall to the front, wing and backstage doors;
- the front cross passage;
- a 1.5 m cross aisle between the blocks;
- a rear strip;
- 1.2 m round the platform, its stair and ramp.

The six front wheelchair places stay, and there is one wheelchair choir place each side.

**Egress:** choir occupants now come from the model (choir chairs + wheelchair choir places + a 60-person platform party), not a fixed 200. The building tally rises to 3,481. EGR-01 still passes, and the existing warnings are unchanged.

**QA fixes found while building this revision:**
- The Blender clash check compared chairs by axis-aligned boxes, which flagged 212 false chair-to-chair clashes between neighbouring angled chairs. Chair pairs are now tested on their true rotated footprints. New test cases confirm that angled chairs 0.40 m apart are still caught and that 0.50 m apart is clear.
- `run_pipeline.py` now stops when the Blender or IFC verification report contains a FAIL. Previously those scripts always exited 0, so a failed check did not stop the run. All earlier revisions' reports had 0 FAILs.

**Revision ID:** `PL06-966bde8984`.

**Checks:**
- 38/38 unit tests;
- Blender verification 18/18 (0 clashes);
- IFC validation 21/21;
- exactly 3,000 congregation seats in every source;
- regeneration identical.

**Renders:** current renders are in `renders/`. The PL05 renders are in `renders/PL05-cba999fc37/`. The 360 video has not been re-rendered since PL02.

## Post-loop revision PL07 (2026-11-02): platform against the rear wall; response to the Blender MCP re-review of PL06, NOT independently re-reviewed

**Re-review of PL06** (`output/independent_design_review_mcp_pl06/MCP_REVIEW_PL06.md`): **6.0/10**, unchanged. Its eight findings are answered in `reports/design_review_response.md`:
- **R3-ARC-02** (platform edges unguarded): addressed. Both side edges now have 1.1 m guards, and the rear edge now abuts the wall. The front edge is left open as the preaching / performance edge, to be risk-assessed.
- **R3-BIM-01** (stale ARC-004 text): addressed. The text now takes the choir count from the model.
- **R3-ARC-03** (sightlines): much improved by this revision but kept OPEN, because the screen study is still outstanding.
- The rest stay OPEN for specialists: evacuation, structure, MEP, the choir/AV study and the site.

**Client decision:** the 20 × 10 m platform is pushed back to the stage rear wall, and the pulpit moves with it. The congregation seats do not move, so 5.85 m of open floor is left in front of the platform (new unallocated space SP-02F).

**Consequences, all generated from the model:**
- **Sightline target:** the sightline focal point now follows the platform front edge, 9.85 m from row 1. With row 2 level, it failed the C-value target, so only row 1 stays level.
- **Platform height:** raised from 0.90 m to **1.00 m**, chosen by a parameter sweep. This keeps the rake inside the existing ramps and stairs. The cross aisle is at +1.20 (was +1.15) and the top of the rake at +4.42 (was +4.60). Keeping 0.90 m would have raised the rake to +1.40 / +4.85, making the ambulatory ramps 1:10.8 and pushing the foyer stair foot too close to the facade.
- **Ramp, stair and wheelchair places:** the platform ramp lands at the rear east corner and runs down to the open floor at the front. The platform stair is at the rear west corner. The front wheelchair places moved 0.45 m forward to stay on level floor.
- **Viewing:** seats more than 60° off the pulpit fell from **108 to 0**, and seats more than 45° from 466 to 156. The worst angle is 52.45° (was 66.17°). SGT-H2 now passes.
- **Choir:** 347 chairs (was 329), with the same clearances (ACC-07). The occupant tally is 3,499.

**Revision ID:** `PL07-ea0efb2777`.

**Checks:**
- 38/38 unit tests;
- Blender verification 18/18 (0 clashes);
- IFC validation 21/21;
- exactly 3,000 congregation seats in every source;
- regeneration identical.

**Warnings:**
- EGR-01R (cross-exit route sensitivity);
- EGR-03N (39.73 m nearest-exit travel);
- EGR-03 (51.37 m);
- EGR-04 (60.67 m total travel).

**Renders:** current renders are in `renders/`. The PL06 renders are in `renders/PL06-966bde8984/`. The 360 video has not been re-rendered since PL02.

## Post-loop revision PL08 (2026-11-02): stair, ramp and choir rows, NOT independently re-reviewed

**Client decisions (from a plan mark-up):**
- **Stair:** the platform stair moves to the west side at the platform's **front corner**.
- **Ramp:** the accessible **ramp runs along the stage rear wall**, from the platform's east edge towards the east wall, at 1:12 and 12 m long. The platform is its top landing. The east stage-to-backstage door moves just east of the ramp foot so the ramp does not block it.
- **Choir layout:** choir chairs are in **straight rows facing across to the platform**, with no angle. The lower blocks stay between the cross aisle and the front passage, so exits stay clear, and are **trapezia**: their platform-side edge slants back 2 m towards the front passage.
- **Wheelchair choir places:** moved to the wall end of the cross aisle.

**Results:**
- **Choir:** **386 chairs** (W 132 + 51, E 152 + 51). The east upper block gained room from the ramp moving to the rear wall. Rows hold at most 13 chairs, and the ACC-07 clearances hold.
- **Occupant tally:** 3,538.
- **Views:** still 0 seats > 60° off the pulpit.

**Revision ID:** `PL08-590d273e35`.

**Checks:**
- 39/39 unit tests;
- Blender verification 18/18 (0 clashes);
- IFC validation 21/21;
- exactly 3,000 congregation seats in every source;
- regeneration identical.

**Warnings:** EGR-01R, EGR-03N, EGR-03 and EGR-04 (max total travel 61.62 m, against the 60 m placeholder flag).

**Renders:** current renders are in `renders/`. The PL07 renders are in `renders/PL07-ea0efb2777/`.
