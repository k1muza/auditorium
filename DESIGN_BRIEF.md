# 3,000-seat church auditorium — design brief

## Purpose and authority
Create a **preliminary, engineering-coordination BIM concept** for a permanent 3,000-congregant-seat church auditorium in Zimbabwe. Deliverables are for review and subsequent development by suitably qualified local design professionals. An AI quality score is never evidence of structural safety, code compliance, permitting, or construction readiness.

## Known project requirements
- Exactly **3,000 congregation seats**, excluding choir/platform seating.
- Permanent building; assembly use; large stage/pulpit, choir and musicians, foyer, media/sound booth, toilets including accessible toilets, prayer/vestry/storage spaces.
- Model using metres, one consistent coordinate system, labelled levels, structural grid, and parametrically editable source scripts.
- Conceptual comparison: single-level auditorium versus floor-plus-balcony (if reasonably feasible); account for sightlines and unobstructed views.
- Represent preliminary access, pedestrian circulation, accessible seating and evacuation paths, with all dimensions clearly identified as **unverified pending professional code review**.
- Structural coordination: preliminary columns, beams, lateral stability concept, roof trusses or frames, bracing zones, foundation reference locations and grid; **not final engineered sizes**.
- Separately identify building envelope, architecture, structure, seating, service allowances and documentation.

## Inputs missing — do not invent these as facts
- Exact site boundary/survey, setbacks, zoning, access/parking, orientation and contours.
- Geotechnical report and allowable soil bearing/settlement criteria.
- Applicable local approvals and legally enforceable building, fire, occupancy and accessibility requirements.
- Budget, target building footprint, materials and procurement constraints.
- Verified loading, wind, rain and seismic design requirements; material grades, connection details and structural design standards.

If a missing input prevents an honest decision, select a clearly labelled, editable **concept assumption**, or defer that decision. Keep an assumptions register with source/status and confidence.

## Milestone for THIS iteration loop
Deliver a first **architecture-and-structure coordination concept** suitable for discussion with an architect and structural engineer. The reviewer must judge this milestone's completeness; do not claim detailed engineering, permit drawings or compliance.

Required files (actual, validated, or report truthful failure):
1. `model/church_3000_concept.blend`
2. `model/church_3000_concept.ifc` (only if successful export and reasonable classification)
3. `scripts/build_auditorium.py` and parameter/config files that reproduce the model
4. `reports/seating_schedule.csv` with exactly 3,000 counted congregation seats, corroborated against model geometry
5. `reports/space_schedule.csv`
6. `reports/assumptions.md`, `reports/open_issues.md`, and `reports/basis_of_design.md`
7. `exports/floor_plan.png` and `exports/structural_grid.png` (labelled schematic images)
8. Evidence logs showing Blender creation, regeneration, seat count, geometry checks and any IFC validation.

All output paths are relative to the project directory. If an artifact cannot be created, write a truthful failure report and treat its rubric category accordingly.

## Stage exclusions
Do not claim to have completed verified member design, foundations, fire evacuation approval, acoustic analysis, MEP engineering, certified cost estimates or construction-ready drawings.

## Client design decisions (recorded after the review loop)
- **2026-11-01 - Choir location (post-loop revision PL01):** the choir is placed on the **two sides of the platform, facing inward** across it, not at the rear of the stage. The rear of the platform is kept free for the band / musicians. Choir seats remain excluded from the 3,000 congregation seats. Choir size (144) remains a concept assumption pending client confirmation.
- **2026-11-01 - Choir seating removed (post-loop revision PL03):** the fixed choir chairs and side choir risers are **removed from the platform**. The whole 30 m platform is one open level for the choir (loose chairs or standing) and the band / musicians, reached step-free by the platform ramp. The platform occupant allowance (200, for egress) is unchanged. This supersedes the PL01 side-choir layout.
- **2026-11-01 - Choir in the platform wings (post-loop revision PL04):** **144 choir chairs** (72 per side, 6 rows x 12) are placed in the **two platform wings on the hall floor, beside the stage, facing inward** towards the platform. The platform itself stays one open level for the band / musicians. The choir is step-free with one wheelchair choir place per wing, and each block keeps at least 1.2 m clear of the platform, its stair / ramp, walls, columns and doors. Choir seats remain excluded from the 3,000. This supersedes PL03 (no choir seating) and PL01 (choir risers on the platform sides).
- **2026-11-01 - Smaller platform (post-loop revision PL05):** the platform is reduced to **20 m wide x 10 m deep** (was 30 m x 15.6 m), keeping the same front edge, centre line, height (+0.90 m) and pulpit position, so the 3,000 seats and their sightlines are unchanged. The wing choir blocks move forward to sit alongside the platform. The floor freed behind and beside the platform is **left empty for now** - no extra chairs.
- **2026-11-02 - Larger choir round the platform (post-loop revision PL06):** following the client's mark-up, the choir fills **four zones round the platform sides** - on each side, a lower block (between the front cross passage and a 1.5 m cross aisle) and an upper block (from the cross aisle back to a rear strip). Chairs are **angled towards the pulpit**. Exit routes stay clear: a 2.4 m corridor along each hall wall to the front, wing and backstage doors, the front cross passage, the cross aisle and the rear strip, with 1.2 m round the platform, its stair and ramp. The six front wheelchair places are kept and there is one wheelchair choir place each side. Choir occupants now count in the egress tally (choir chairs + wheelchair choir places + 60 platform party).
- **2026-11-02 - Platform against the rear wall (post-loop revision PL07):** the 20 m x 10 m platform is **pushed back to touch the stage rear wall**; the pulpit moves with it. The congregation seating stays where it is, leaving **5.85 m of open floor in front of the platform**. Because the sightline target (the platform front edge) is now further from the front rows, only row 1 stays level and the **platform is raised to 1.00 m** (from 0.90 m), which keeps the rest of the rake within the existing ramps and stairs. The platform ramp now lands at the rear east corner and runs down towards the front; the platform stair is at the rear west corner; both side edges of the platform are guarded, and the front edge is left open as the preaching / performance edge (to be risk-assessed).
- **2026-11-02 - Stair, ramp and choir rows (post-loop revision PL08):** the platform **stair** moves to the west side at the **front corner** of the platform. The accessible **ramp runs along the stage rear wall**, from the platform's east edge towards the east wall (the platform is its top landing); the east backstage door moves just east of the ramp foot. **Choir chairs stand in straight rows facing across to the platform** (no angle). The two lower choir blocks stay between the cross aisle and the front passage (exits kept clear) and are **trapezia**, their platform-side edge slanting back 2 m towards the front passage. Wheelchair choir places move to the wall end of the cross aisle.
