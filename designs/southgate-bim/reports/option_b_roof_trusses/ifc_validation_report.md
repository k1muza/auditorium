# IFC validation report - Option B candidate OPTB-C01

File: `work/option_b/candidates/20261107-115532/southgate_optionB_candidate.ifc` - sha256 `32622e105a690a1f9f8be03547945ea1306ae96b7324ef9e73823be97a087d18`. Validator: `scripts/option_b/s05_validate.py` run with `python -I` on the saved file
(no project code imported), regression reference `bim/southgate.ifc`. Run time 2213.8 s.

## Gates

| Gate | Result | Evidence |
|---|---|---|
| A1_schema_valid | PASS | 0 |
| A2_unique_globalids | PASS | [] |
| B1_trusses_contained_in_roof_storey | PASS | {"SOUTHGATE-TRUSS-T01": "03 Roof", "SOUTHGATE-TRUSS-T02": "03 Roof", "SOUTHGATE-TRUSS-T03": "03 Roof", "SOUTHGATE-TRUSS-T04": "03 Roof", "SOUTHGATE-TRUSS-T05":  |
| B2_every_new_element_aggregated_into_a_contained_truss | PASS | [] |
| B3_every_new_element_typed | PASS | [] |
| B4_every_new_component_has_material | PASS | [] |
| B5_angles_native_LShape_profile_with_profile_set_usage | PASS | {"bad": [], "angles_by_profile": {"L70x70x6": 44, "L75x75x6": 184, "L60x60x6": 176, "L100x100x8": 146, "L80x80x8": 156, "L90x90x8": 108}} |
| B6_members_and_plates_have_base_quantities | PASS | [] |
| B7_design_status_present_no_verification_claim | PASS | {"by_status": {"CONCEPT_UNVERIFIED": 6597}, "claims": []} |
| B8_every_bolt_realises_a_connection_relationship | PASS | {"relationships": 4672, "bolts": 3634, "loose": []} |
| B9_engineering_warnings_on_every_truss | PASS | [] |
| C1_every_component_has_geometry | PASS | [] |
| C2_truss_count_and_positions | PASS | {"n": 11, "x": [3.25, 8.81, 14.37, 19.93, 25.49, 31.05, 36.61, 42.17, 47.73, 53.29, 58.85]} |
| C3_twelve_bays_2700 | PASS | {"SOUTHGATE-TRUSS-T01": [12, [2.7]], "SOUTHGATE-TRUSS-T02": [12, [2.7]], "SOUTHGATE-TRUSS-T03": [12, [2.7]], "SOUTHGATE-TRUSS-T04": [12, [2.7]], "SOUTHGATE-TRUS |
| C4_pitch_15deg | PASS | {"SOUTHGATE-TRUSS-T01": [15.0], "SOUTHGATE-TRUSS-T02": [15.0], "SOUTHGATE-TRUSS-T03": [15.0], "SOUTHGATE-TRUSS-T04": [15.0], "SOUTHGATE-TRUSS-T05": [15.0], "SOU |
| C5_top_of_steel_below_purlin_seat(-10.13mm) | PASS | {"SOUTHGATE-TRUSS-T01": -0.0105, "SOUTHGATE-TRUSS-T02": -0.0105, "SOUTHGATE-TRUSS-T03": -0.0105, "SOUTHGATE-TRUSS-T04": -0.0105, "SOUTHGATE-TRUSS-T05": -0.0105, |
| C6_within_bearings_and_column_line | PASS | {"SOUTHGATE-TRUSS-T01": [0.2807, 32.7193], "SOUTHGATE-TRUSS-T02": [0.2807, 32.7193], "SOUTHGATE-TRUSS-T03": [0.2807, 32.7193], "SOUTHGATE-TRUSS-T04": [0.2807, 3 |
| C7_bolts_pass_through_their_stack | PASS | {"checked": 3634, "failures": 0, "examples": []} |
| C8_plate_holes_coincide_with_bolts | PASS | [] |
| C9_no_intersections_between_new_members_and_plates | PASS | {"n": 0, "examples": []} |
| D1_stored_volumes_match_geometry | PASS | {"n": 0, "examples": []} |
| E1_retained_elements_unchanged | PASS | {"retained": 9048, "missing": [], "changed": []} |
| E2_superseded_parts_absent | PASS | {"superseded": 1520, "still_present": 0} |
| E3_architectural_and_support_counts_unchanged | PASS | {"IfcWall": [116, 116], "IfcDoor": [84, 84], "IfcWindow": [40, 40], "IfcColumn": [99, 99], "IfcFooting": [92, 92], "IfcSlab": [82, 82], "IfcCovering": [960, 960 |
| E4_excluded_buildings_not_introduced | PASS | [] |

## Truss geometry measured from the IFC

| Truss | x (m) | Bays | Panel lengths (m) | TC pitch (deg) | TOS vs 12.380 plane (mm) | BC underside z | y extent |
|---|---|---|---|---|---|---|---|
| T01 | 3.25 | 12 | 2.700 | 15.000 | -10.50 | 10.8774 | 0.2807 - 32.7193 |
| T02 | 8.81 | 12 | 2.700 | 15.000 | -10.50 | 10.8774 | 0.2807 - 32.7193 |
| T03 | 14.37 | 12 | 2.700 | 15.000 | -10.50 | 10.8774 | 0.2807 - 32.7193 |
| T04 | 19.93 | 12 | 2.700 | 15.000 | -10.50 | 10.8774 | 0.2807 - 32.7193 |
| T05 | 25.49 | 12 | 2.700 | 15.000 | -10.50 | 10.8774 | 0.2807 - 32.7193 |
| T06 | 31.05 | 12 | 2.700 | 15.000 | -10.50 | 10.8774 | 0.2807 - 32.7193 |
| T07 | 36.61 | 12 | 2.700 | 15.000 | -10.50 | 10.8774 | 0.2807 - 32.7193 |
| T08 | 42.17 | 12 | 2.700 | 15.000 | -10.50 | 10.8774 | 0.2807 - 32.7193 |
| T09 | 47.73 | 12 | 2.700 | 15.000 | -10.50 | 10.8774 | 0.2807 - 32.7193 |
| T10 | 53.29 | 12 | 2.700 | 15.000 | -10.50 | 10.8774 | 0.2807 - 32.7193 |
| T11 | 58.85 | 12 | 2.700 | 15.000 | -10.50 | 10.8774 | 0.2807 - 32.7193 |

Panel lengths are measured between pair centroids of the verticals (mesh centroids), the pitch from the top-chord angle axes.
Top of steel must be <= -10.13 mm (purlin underside); the y extent must stay inside the column flange faces (0.2771 / 32.7229).

## Project validator (`scripts/validate/validate_ifc.py`)

- schema issues: 0; elements 15598; uncontained/unaggregated 0
- design status: {"CONCEPT_UNVERIFIED": 10286, "EXISTING_DESIGN_REFERENCE": 2800, "PRELIMINARY_DESIGN": 2512}; engineering-verified claims 0
- openings {"openings": 58, "filled": 58, "voiding": 58, "doors": 84, "windows": 40, "doors_windows_filling_openings": 58}
- geometry extent {"elements_with_geometry": 14864, "of": 15598, "world_min": [-6.65, -1.0, -1.45], "world_max": [62.34, 37.59, 19.57], "extent_m": [68.99, 38.59, 21.02]}

## Pilot (Stage 2)

The single-truss pilot (`validation/pilot_validation.json`) passed every gate, loaded in Bonsai 0.9.0-post1, was edited with Bonsai's own
`bim.change_extrusion_depth` (angle D04-A +50 mm: L-profile and profile-set usage preserved) and saved. Re-validating the Bonsai-saved file
detected exactly the two expected consequences: one stale stored volume (D1) and the new 50 mm penetration (C9) - the gates detect real edits.

## Save / reopen

Every check above runs on the reopened saved file. Bonsai round trip of the full candidate: `validation/bonsai_resaved_bonsai.json`.

## Notes on representation

- Angles: `IfcMember` + `IfcLShapeProfileDef` (EN 10056 dimensions incl. root/toe radii) + `IfcMaterialProfileSetUsage` (CardinalPoint 5) - one element per angle, paired by a `BUILT_UP_MEMBER_2L` assembly.
- Plates: `IfcPlate` extruded `IfcArbitraryProfileDefWithVoids` (bolt holes as voids) + `IfcMaterialLayerSetUsage` AXIS3; packing plates are mapped type geometry.
- Bolts: `IfcMechanicalFastener` BOLT occurrences mapped from `IfcMechanicalFastenerType` (head, shank, washer, nut; no threads). Nuts and washers are counted from the set composition (1 + 1 per set).
- Bolt holes in angles are not modelled; the bolt shank volume overlaps the angle legs by design (excluded from the clash gate, documented).
