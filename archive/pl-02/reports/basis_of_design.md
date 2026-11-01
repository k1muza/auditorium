# Basis of design - 3,000-Seat Church Auditorium - Coordination Concept

> **Status: CONCEPT - UNVERIFIED - NOT FOR CONSTRUCTION.** Preliminary engineering-coordination model for discussion with a qualified architect and structural engineer. No structural analysis, code compliance check, fire/egress approval, geotechnical input or permit review has been performed. QA scores are not engineering approval.

- **Model revision:** `PL02-18dac43917` (Blender 5.2.3 LTS; generator schema layout-1.0)
- **Milestone:** M1 Architecture-and-structure coordination concept
- **Units / coordinates:** metres. Local project coordinates. Origin (0,0,0) = intersection of grid A and grid 1 at Level 00 finished floor. +X = along numbered gridlines toward grid H. +Y = toward the platform (grid 12). +Z = up. Project north ASSUMED = +Y; true north unknown (no survey).
- **Source:** `config/auditorium_params.json` + `scripts/auditorium_layout.py` -> `scripts/build_auditorium.py` (Blender) -> `model/blender_manifest.json` -> `scripts/export_ifc.py` (IFC4). Regenerate with `scripts/run_pipeline.py`.

## 1. Brief summary
Permanent church auditorium in Zimbabwe for exactly 3,000 congregation seats (choir/platform excluded), with platform, choir and musicians, foyer, media/sound booth, toilets incl. accessible WCs, prayer room, vestry and storage. Site, geotechnical, statutory, budget and loading inputs are missing and are NOT invented (see assumptions.md).

## 2. Option comparison: single level vs floor + balcony
| Criterion | A: single-level raked hall (SELECTED for this milestone) | B: floor + balcony (computed estimate, not modelled) |
|---|---|---|
| Seats | 3,000 in 41 rows | 2000 floor (27 rows) + 1000 balcony (13 rows) |
| Max eye distance to platform edge | 45.5 m | ~32.5 m floor / ~35.7 m balcony |
| Hall depth | 48.0 m (grid 3-9) | ~13.3 m shorter |
| Vertical egress | Rear 1,000-1,600 occupants via upper-foyer stairs (rear platform +4.60 m) | 1000 occupants via protected stairs from +6.0 m; lifts mandatory for access |
| Structure | Single-storey long-span roof only; no suspended seating structure | Suspended/cantilevered balcony (vibration, back-span, transfer structure) + increased column count |
| Sightlines | All rows C >= 0.06 m achieved (min 0.060) | Same C rule computed for floor and balcony; balcony rake 18.4 deg; rear floor row view to a point 2.5 m above the platform passes 2.11 m below the soffit |
| Under-balcony volume | n/a | Overhang 10.95 m deep over a 3.43 m opening (depth/height 3.19) - a deep, low under-balcony zone for the rear floor rows |

**Recommendation (pending client/architect decision):** Option A. It keeps most occupants at or near grade, avoids a suspended balcony structure and its vibration/transfer design, and keeps accessible routes short, at the cost of a deeper hall (44.5 m max eye distance, so screens are assumed for rear rows) and a larger footprint. Option B remains viable if the site is too short for 88 m; it should then be modelled and checked the same way. Option B section: exports/balcony_option_section.png (computed schematic, not part of the BIM model).

## 3. Seating geometry
- 76 seats per full row in blocks [10, 14, 14, 14, 14, 10] with 5 interior aisles of 1.5 m and wall aisles >= 1.825 m; side blocks omitted in rows 1-2 (front wheelchair positions). 41 rows; the 76 seats with the worst angle to the pulpit are removed (A-24), leaving exactly 3,000.
- Seat module 0.5 m x 0.6 m chair, row pitch 0.95 m (clear seatway 0.35 m), rows alternately offset +/-0.125 m (staggered).
- Rake from a C-value recurrence: front 19 rows on a continuous slope to +0.99 (steepest 1:10.56); mid cross aisle + wheelchair band at +1.15 (one 0.155 m riser at aisle mouths); rear 22 rows stepped with uniform risers (A-22): rows 20-41 riser 0.150 m; rear platform at +4.600.
- Rake generated so that EVERY row meets C >= 0.06 m over the row in front and >= 0.12 m over the row two in front (staggered seating): achieved minima 0.060 / 0.120 m (row_schedule.csv).
- Model checks: seat count, row levels, floor contact (raycast), clash matrix and sightlines re-measured from the Blender objects (reports/blend_verification.json).

## 4. Circulation, accessibility and provisional egress (UNVERIFIED)
- Hall exits: 10 doorways, total clear width 26.88 m vs placeholder demand 16.3 m (5 mm/person). Per-exit loads in exit_schedule.csv.
- Rear exits discharge to the upper foyer at +4.60; 2 wide foyer stairs (10.8 m total, risers 0.170 m) rise through openings in the upper-foyer slab towards the main doors. Mid cross-aisle exits land on ambulatory landings with external steps AND a direct 1:12 outside ramp (flat grade assumed).
- Exit widths are door sets (A-25): effective clear width = nominal - 0.08 m per leaf; all capacity checks use the effective width.
- Accessible route: ambulatory ramps (steepest 1:13.17, flights <= 9 m with 1.5 m landings) to the mid cross aisle; lift from foyer to upper foyer / rear platform; level front zone from ambulatory front doors; platform ramp 1:12.
- 30 wheelchair spaces (front and mid band) each with a loose companion chair, additional to the 3,000; none on the lift-only upper level (client decision PL02). 4 refuge allowances remain at the stair heads for upper-foyer users (A-21, OI-16). Two further wheelchair places at platform level serve the choir.
- Viewing (A-26): seats > 45 deg off the pulpit 466, > 60 deg 108, worst 66.17 deg; 0 seats without a usable view of the pulpit or a screen (SGT-H1).
- Max plan travel to the nearest hall exit 39.7 m; queue-balanced 52.3 m to a hall exit and 56.8 m to an external door. Placeholder flags are exceeded and logged (OI-05, OI-17) with a restriction on use - not presented as acceptable.

## 5. Structural coordination concept (no analysis)
- Grid A-H (4.5 / 10 / 10 / 10 / 10 / 10 / 4.5 m) x 1-12 (8 / 8 / 8 / 8 / 6.5 / 9.5 / 8 / 8 / 8 / 8 / 8 m). 76 columns, 9 duo-pitch Pratt trusses spanning 50 m between lines B and G at grid lines 3-11 (bays 8 / 8 / 6.5 / 9.5 / 8 / 8 / 8 / 8 m; grid 6 shifted to y=38.5 to clear the cross-aisle exits), bearing +14.00, ridge roof top +18.40.
- Every brace / strut / knee / purlin end touches its support (352 ends checked, STR-CON). Lateral (A-13, A-27): portal frames with knee braces on grids 4-10 + braced gable bay D-E on grids 3 and 11 (brace feet collected by struts STR-STRUT-GABLE-* into gable posts D/E and their pad footings); longitudinal vertical X-bracing in bays 3-4 and 10-11 on B and G, placed in the cavity of 2-leaf braced-bay walls; roof-plane bracing bays 3-4, 7-8, 10-11. Purlins at panel points. Foyer/mezzanine/low-roof beams on 8-10 m spans. Wall-top closure flashings (ENV-FLASHING-*) close the junction with the offset eaves/gable cladding.
- Pad footings modelled as reference locations only. **No loads, analysis, member design, connection design or foundation design.**

## 6. Model content and separation
| Collection (Blender) / IFC | Content |
|---|---|
| 10_ENV | External and hall walls, gable infills, roofs, flashings, entrance canopy, external doors |
| 20_ARC | Floors/rake/platform/choir tiers, partitions, stairs, ramps, rail, lift, booth, pulpit |
| 30_STR | Columns, pad footing references, trusses (IfcElementAssembly TRUSS), purlins, bracing, beams |
| 40_SEAT | 3,000 congregation chairs, choir chairs, companion chairs, wheelchair spaces |
| 50_SRV | MEP space allowances (IfcSpatialZone), IMAG screens and speakers (IfcAudioVisualAppliance), gutters and downpipes (IfcPipeSegment), aisle step lights (IfcLightFixture) |
| 60_ZONE | IfcSpace rooms with areas, aisle clear zones |

Element totals: IfcAudioVisualAppliance 10, IfcBeam 118, IfcColumn 76, IfcCovering 4, IfcDoor 45, IfcFooting 76, IfcFurniture 3175, IfcLightFixture 115, IfcMember 545, IfcPipeSegment 32, IfcRailing 19, IfcRamp 7, IfcSlab 314, IfcSpace 27, IfcSpatialZone 246, IfcStair 7, IfcTransportElement 1, IfcWall 39, IfcWindow 1.

Storeys: every element is assigned to the highest storey whose datum is at or below its reference height (walking surface for floor slabs, base otherwise; footings L00); only the raised booth floor/space use an explicit, recorded override. IFC elements carry placeholder materials (A-23) and base quantities (length/height/width, gross volume integrated from the model mesh); spaces carry gross floor area and do not overlap (check SPC-01).

## 7. Levels
| Level | Elevation | Name |
|---|---|---|
| L00 | +0.000 | Level 00 - datum +0.000 (ground floor, front of hall) |
| L01 | +1.150 | Level 01 - datum +1.150 (cross aisle, rear rake, framing below upper foyer) |
| L02 | +4.600 | Level 02 - datum +4.600 (upper foyer, rear platform) |
| L03 | +4.300 | Level 03 - datum +4.300 (low-roof framing and items above it) |
| L04 | +7.650 | Level 04 - datum +7.650 (foyer-roof framing, high-level allowances) |
| L05 | +13.600 | Level 05 - datum +13.600 (hall roof structure) |

## 8. Deliverables and evidence
See `reports/model_index.md` for the full file list with hashes, and `logs/` for build/validation logs.

## 9. What a local architect / engineer must verify next
1. Applicable Zimbabwean statutes and fire/occupancy/accessibility requirements -> re-set all placeholder widths, distances, ratios.
2. Site survey and orientation; fit of the 59 x 88 m footprint, access, parking, levels (external steps assume flat grade).
3. Egress design by a fire engineer (travel distances currently exceed placeholder flags).
4. Structural scheme: loads, 50 m truss design, lateral system, deflection/ponding, foundations with a geotechnical report.
5. Sightline focal point, screens, acoustics and AV; MEP, sanitary fixture counts, water storage and backup power.
6. Decision Option A vs B with the client; cost plan.
