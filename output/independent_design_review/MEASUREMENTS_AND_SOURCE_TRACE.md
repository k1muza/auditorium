# Measurements and Source Trace

## Authority and units

| Item | Value | Extraction/source |
|---|---|---|
| Authoritative blend | `model/church_3000_concept.blend` | Latest embedded revision matching current config/IFC/reports |
| Revision | `PL01-7cafe48b2e` | `scene['revision']`; `reports/model_revision.json` |
| SHA-256 | `60993e41f798f68ae12a065a47039515ae73871cb2e4150707df14541971ed80` | Independent file hash |
| Units | Metric; scale 1.0; metres | Blender scene unit settings |
| Blender audit | 5.2.3 LTS | [`EVIDENCE/independent_model_audit.json`](EVIDENCE/independent_model_audit.json) |

The viewing copy is IT03 (`ea94cce7…9c486a`) and was rejected as non-authoritative.

## Spatial and architectural measurements

| Metric | Value | Logic / IDs | Confidence |
|---|---:|---|---|
| Grid footprint | 59.0 × 88.0 m | A–H and 1–12 coordinates in config/scene `grid_json` | High |
| Model extents | X −3.45..62.45; Y −0.90..88.90; Z −1.50..18.40 m | World bounding boxes of all objects with `ifc_class` | High |
| Congregation seats | 3,000 | Objects `SEAT-C-*` in `40_SEAT_Congregation` | High |
| Seat rows | 40 | Parse object IDs / source row schedule | High |
| Full-row blocks | 10/14/14/14/14/10 = 76 | Config + seat IDs | High |
| Seat centre / row pitch | 0.50 / 0.95 m | Config and seat coordinates | High |
| Interior/wall aisle clear | 1.52 / 1.835 m | Source Blender verification; world AABBs | High |
| Stage | 30.0 × 15.6 m; +0.90 m | `ARC-PLATFORM*`; config bounds | High |
| Platform clear centre | 22.8 m | Scene `metrics_json` | High |
| Choir | 144 chairs on six side tiers | `40_SEAT_Choir`; `SEAT-Q-*` | High |
| Wheelchair/companion | 30 / 30 | `ACC-WCS-*`; `SEAT-K-*` | High |
| Longitudinal C-value minima | 0.0603 m N−1; 0.1202 m N−2 | Source recurrence and chair coordinates | Medium–High; focal assumptions unverified |
| Maximum distance to platform edge | 44.5 m | Source `metrics_json` | High |
| Off-axis to pulpit | 542 >45°; 184 >60°; max 72.58° | `atan2(abs(seat_x−29.5), 65.6−seat_y)` for 3,000 world transforms | High geometry; no acceptance threshold asserted |

Full independent angular output: [`EVIDENCE/sightline_off_axis_samples.csv`](EVIDENCE/sightline_off_axis_samples.csv).

## Circulation and egress measurements

| Metric | Value | Source/logic | Status |
|---|---:|---|---|
| Hall exits | 10 openings / 28.8 m nominal total | `DR-HALL-*`, exit schedule | Door operation not represented |
| Nearest hall-exit travel | 39.73 m; 330 occupants over 30 m flag | Source route graph EGR-03N | Geometry verified; flag is placeholder |
| Queue-balanced hall travel | 50.87 m | EGR-03 | Heuristic, not code analysis |
| Exterior travel | 61.17 m | EGR-04 | Geometry verified; flag placeholder |
| Cross-exit shortest-outside sensitivity | 1,032 W / 1,022 E | EGR-01R | Demonstrates crowd concentration |
| Foyer stairs | 4 × 2.7 m = 10.8 m; 23 × 0.173 m risers | `ARC-STAIR-FOYER-*` | Geometry verified |
| Front slope | steepest 1:10.56 | Floor geometry and source recurrence | High |
| Cross-aisle transition | one 0.155 m riser | GEO-01 | High |
| Rear risers | 0.150 / 0.120 / 0.135 m bands; 0.95 m going | `ARC-RAKE-*`; row schedule | High |
| Ambulatory ramp | steepest 1:13.17 | `ARC-RAMP-AMB-*` | High geometry; legal status unknown |
| Platform ramp | 1.5 m wide, 1:12, 0.9 m rise | `ARC-RAMP-PLATFORM-E` world bbox/properties | High |

The configured total of 3,290 people includes 30 BOH staff, but the egress routine tallies 3,060 hall plus 200 platform/choir; 30 staff are omitted.

## Structural measurements

| Metric | Value | Source/logic | Confidence |
|---|---:|---|---|
| Trusses | 9 × 50.0 m; 41 members each | `assembly=STR-TRUSS-*`; centreline JSON | High |
| Bearing/ridge | +14.00 / +18.40 m | World geometry | High |
| Truss spacing | 8/8/6.5/9.5/8/8/8/8 m | Grid Y coordinates | High |
| Purlins | 88; 11 per bay | `predefined_type=PURLIN` | High |
| Columns / pads | 68 / 68 | IFC/object class counts | High |
| Column-pad alignment | max X/Y offset 0.000 m; vertical gap 0.000 m | Nearest-centre pairing + world AABBs | High |
| Braces / gable struts | 72 / 2 | Object class/properties | High |
| Wall-brace connection gap | approximately 34.6 mm to column AABB | Manifest world AABBs | High geometry |
| Gable-strut connection gap | approximately 10 mm | Manifest world AABBs | High geometry |

The independent truss-centreline topology found no isolated non-bearing truss endpoint. This refutes unsupported primary truss ends; it does not verify real bearings or connection adequacy.

## BIM/service inventory

- Scene: 4,683 objects including 66 documentation objects; 4,617 model objects with IFC classes.
- IFC4/source counts include 110 beams, 68 columns, 68 footings, 531 members, 41 doors, 7 stairs, 5 ramps, 25 spaces, 243 spatial zones and 3,175 furniture objects.
- Five service zones exist; actual systems do not.
- One window is modelled (the booth viewing window).
- Independent name audit found zero gutters, downpipes, drains, acoustic treatment, ducts, diffusers, sprinklers, detectors, exit signs, emergency lights or lightning-protection objects.

## Evidence integrity

All images in `EVIDENCE/` were copied from current PL01 exports/renders. Source schedules and verification JSON were copied into the package so the report does not depend on paths outside this directory. The independent script is included and does not save the source blend.

