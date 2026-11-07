# Migration completeness audit - Southgate Worship Center (main auditorium)

Generated 2026-11-07T10:00:06 from saved artefacts. Build `20261107-073340_full`; IFC sha256 `6cb86f6da743c810ff3281253c0cb72dbca67f8e36f948a88ba9de715b2b035e`.

Scope: main auditorium building and physically integrated components only (see `config/project.yaml` -> `boundary`). Detached buildings (children's church, EX- massings) and site works are excluded and are not counted as omissions.

## A. Migration completeness

Every source object has exactly one disposition in `reports/migration/migration_register.csv` (13699 rows = 13699 objects in the verified snapshot).

| Disposition | Source objects |
|---|---:|
| `MIGRATED_NATIVE` | 6635 |
| `MIGRATED_CUSTOM_IFC` | 4841 |
| `VISUAL_ONLY` | 153 |
| `EXCLUDED_INTENTIONALLY` | 239 |
| `SUPERSEDED_OR_DUPLICATE` | 1823 |
| `MIGRATION_FAILED` | 0 |
| `OUTSTANDING_MIGRATION` | 0 |
| `NEW_DESIGN_REQUIRED` | 8 |
| **Total** | **13699** |

Migrated source objects map onto **10513 IFC elements** (+ 41 assemblies, 58 openings). One IFC element may replace several source meshes, so object counts and element counts are compared through the mapping, not directly.

* IFC elements with native parametric / swept / type-mapped representations: **5966** (56.7 %)
* IFC elements carrying exact source tessellation (classified custom geometry): **4547**
* Consolidations: 170 IFC elements were built from 1133 source objects (e.g. 26 walls rebuilt from pier/header/sill pieces with real openings; 53 doors/windows rebuilt as parametric types from frame/leaf/glass parts).

### By building system (IFC elements)

| Phase / system | IFC elements | native | custom | audit OK | REVIEW | FAIL |
|---|---:|---:|---:|---:|---:|---:|
| B Spatial / spaces | 32 | 32 | 0 | 32 | 0 | 0 |
| C Structural & architectural framework | 63 | 62 | 1 | 63 | 0 | 0 |
| D Openings & facades | 817 | 772 | 45 | 817 | 0 | 0 |
| E Roof & structural steel | 3999 | 3926 | 73 | 3812 | 187 | 0 |
| F Auditorium & stage | 2192 | 182 | 2010 | 2192 | 0 | 0 |
| G Ancillary (offices, restrooms, terrace) | 863 | 523 | 340 | 863 | 0 | 0 |
| H Services & acoustics | 2449 | 371 | 2078 | 2449 | 0 | 0 |
| I Foundations & substructure | 98 | 98 | 0 | 98 | 0 | 0 |

### Why objects were not migrated

**EXCLUDED_INTENTIONALLY** (239):

* 143 - Detached building (children's church) - outside project scope
* 33 - Site works, parking, site boundary and EX- massing blocks of detached buildings - outside building boundary
* 24 - External forecourt study (site works) - outside building boundary
* 10 - External paving apron around office wing (site works) - outside building boundary
* 9 - empty/transform helper without geometry
* 8 - room-name annotation text; name recorded for future IfcSpace (see outstanding work)
* 4 - External approach paving (site works) - outside building boundary
* 3 - External paving subbase (site works) - outside building boundary
* 3 - design-check annotation (turning circle / validation marker) - not a construction element
* 2 - Site grade reference / site walk subbase - outside building boundary

**SUPERSEDED_OR_DUPLICATE** (1823):

* 484 - hidden in source; Old fragmented office floor layers, # lower spiral, sunken pit/sump/rails are superseded by new shared apron and grade-lev
* 372 - hidden in source; retired by a later design revision (hidden, not deleted, for reversibility)
* 255 - archive collection; Archive/history geometry
* 219 - archive collection; retired by a later design revision (hidden, not deleted, for reversibility)
* 95 - hidden in source; MODELLED_NOT_ENGINEERED
* 72 - geometric duplicate of ACOUSTIC-CLAMP-FASTENER-#-#-R (identical bounds and vertex count)
* 72 - geometric duplicate of ACOUSTIC-CLAMP-NECK-#-#-R (identical bounds and vertex count)
* 72 - geometric duplicate of ACOUSTIC-TRUSS-CLAMP-#-#-R (identical bounds and vertex count)
* 72 - hidden in source; ARCHIVED_FLEXIBLE_CHOIR_STRATEGY
* 32 - hidden in source; Replaced by BIM-AUDIT-# floor assembly
* 30 - archive collection; ARCHIVED_PRE_REDNEISGN
* 20 - archive collection; PRELIMINARY_GEOMETRIC
* 4 - hidden in source; Indicative visual joint not construction-detailed, archived in favor of continuous paving
* 4 - geometric duplicate of BRACE-ROOF-# (identical bounds and vertex count)

**VISUAL_ONLY** (153):

* 107 - light - presentation rig, retained in bim/visualisation.blend (not construction)
* 32 - camera - presentation rig, retained in bim/visualisation.blend (not construction)
* 14 - light_probe - presentation rig, retained in bim/visualisation.blend (not construction)

**NEW_DESIGN_REQUIRED** (8):

* 4 - archived because it requires redesign (Platform lift enclosure post); accessible vertical access is an open design issue
* 3 - archived because it requires redesign (Platform lift safety enclosure); accessible vertical access is an open design issue
* 1 - archived because it requires redesign (Vertical platform lift allowance); accessible vertical access is an open design issue

Hidden source objects were not migrated automatically. Each hidden group was traced to its retirement evidence (archive collections, `SUPERSEDED_ARCHIVE` / `RETIRED_*` design status, `exclusion_reason`, the EXT05-EXT10 design audits stating the geometry was 'hidden rather than deleted'). The exception is below-grade foundation concepts, which are hidden only for presentation and were migrated as `CONCEPT_UNVERIFIED` footings.

## B. Geometric fidelity

| Measure | Source (verified snapshot, migrated objects) | IFC (saved file) | Difference |
|---|---|---|---|
| extent x min / max (m) | -6.650 / 62.340 | -6.650 / 62.340 | +0.000 / -0.000 |
| extent y min / max (m) | -1.000 / 37.590 | -1.000 / 37.590 | +0.000 / +0.000 |
| extent z min / max (m) | -1.450 / 19.570 | -1.450 / 19.570 | +0.000 / +0.000 |
| overall length x width x height (m) | 68.990 x 38.590 x 21.020 | 68.990 x 38.590 x 21.020 | |
| storeys | GF +0.265 / mezz +4.0575 / upper +7.85 / roof datum +10.9 (slab tops) | 00 Ground Floor +0.2650, 01 Mezzanine and Gallery +4.0575, 02 Upper Floor +7.8500, 03 Roof +10.9000 | identical |
| fixed congregation seats | 2000 visible (`seat_count_intended` 2000) | 2000 IfcFurniture CHAIR (690 gallery) | 0 |
| walls / columns / beams / slabs | | 116 / 99 / 44 / 82 | consolidations explained above |
| doors / windows | | 84 / 40 | parametric |

Per-element agreement (world bounding box of the IFC body vs the true world-vertex bounds of its source members, and body volume vs orientation-robust source volume), from the audits of the saved checkpoints:

| IFC class | elements | AABB dev max (m) | AABB dev p95 (m) | volume rel. dev max | volume rel. dev p95 |
|---|---:|---:|---:|---:|---:|
| IfcFurniture | 2135 | 0.0 | 0.0 | 1e-05 | 0.0 |
| IfcFastener | 1924 | 0.0 | 0.0 | 0.0 | 0.0 |
| IfcMember | 1563 | 0.00304 | 0.00259 | 0.04093 | 0.03345 |
| IfcMechanicalFastener | 1501 | 0.00024 | 0.0 | 0.01601 | 3e-05 |
| IfcPlate | 962 | 0.0 | 0.0 | 0.0 | 0.0 |
| IfcCovering | 960 | 0.0001 | 0.0 | 0.00597 | 0.00103 |
| IfcPipeSegment | 155 | 0.00037 | 0.0 | 0.0005 | 0.00021 |
| IfcDiscreteAccessory | 138 | 0.0 | 0.0 | 0.0 | 0.0 |
| IfcWall | 116 | 0.0 | 0.0 | 2e-05 | 0.0 |
| IfcColumn | 99 | 0.0 | 0.0 | 0.00012 | 8e-05 |
| IfcLightFixture | 96 | 0.0 | 0.0 | 0.0 | 0.0 |
| IfcFooting | 92 | 0.0 | 0.0 | 0.0 | 0.0 |
| IfcDoor | 84 | 0.04 | 0.0375 | 5.069 | 4.49178 |
| IfcSlab | 82 | 0.0 | 0.0 | 0.0 | 0.0 |
| IfcPipeFitting | 81 | 0.0 | 0.0 | 0.0 | 0.0 |
| IfcSanitaryTerminal | 66 | 0.0 | 0.0 | 0.00011 | 0.00011 |
| IfcRailing | 61 | 0.0 | 0.0 | 1e-05 | 1e-05 |
| IfcAirTerminal | 54 | 1e-05 | 0.0 | 1e-05 | 0.0 |
| IfcBeam | 44 | 0.0 | 0.0 | 1e-05 | 1e-05 |
| IfcWindow | 40 | 0.0125 | 0.0125 | 0.72649 | 0.72649 |
| IfcDuctSilencer | 38 | 0.0 | 0.0 | 0.0 | 0.0 |
| IfcBuildingElementProxy | 35 | 0.0 | 0.0 | 0.0 | 0.0 |
| IfcActuator | 28 | 0.0 | 0.0 | 0.0 | 0.0 |
| IfcStairFlight | 23 | 0.0 | 0.0 | 0.0 | 0.0 |
| IfcFan | 23 | 0.0 | 0.0 | 0.0 | 0.0 |
| IfcDuctSegment | 19 | 0.0 | 0.0 | 0.0 | 0.0 |
| IfcWasteTerminal | 18 | 0.0 | 0.0 | 0.0 | 0.0 |
| IfcSpace | 14 | 0.0 | 0.0 | 0.0 | 0.0 |
| IfcSensor | 13 | 0.0 | 0.0 | 0.0 | 0.0 |
| IfcAudioVisualAppliance | 10 | 0.0 | 0.0 | 0.0 | 0.0 |
| IfcEvaporativeCooler | 10 | 0.0 | 0.0 | 0.0 | 0.0 |
| IfcOutlet | 6 | 0.0 | 0.0 | 0.0 | 0.0 |
| IfcRampFlight | 4 | 0.0 | 0.0 | 0.0 | 0.0 |

Audit status over all elements: {'OK': 10326, 'REVIEW': 187} (tolerances: position 5 mm, volume 1 % swept / 2 % tessellated; doors/windows 80 mm because parametric bodies replace modelled parts).

### Expected representation changes (not design discrepancies)

* **Doors and windows** (84 + 40) are parametric IfcOpenShell/Bonsai types sized from the modelled frame parts; the source leaf/frame/glass meshes are consolidated. Door leaves modelled open in the source are represented closed. NOTE: door/window AABB deviations in the table are measured against the FRAME parts; against all source parts (incl. open or displaced leaves) they reach 1.11 m.
* **Consolidated walls** (26): net volume equals the sum of the source pieces; openings are real IfcOpeningElements.
* **Swept truss members with skewed source geometry** (176 REVIEW items): the source meshes of these double-angle members are slightly tapered (end vertices snapped to node points, lateral skew up to 4.5 mm). The IFC uses the true constant section; volume differs up to about 4 %. The IFC section is the engineering-consistent one; the source distortion is recorded.
* **Open source meshes repaired**: 763 migrated source meshes are not closed (missing faces, e.g. a triangle where a quad belongs). Where the vertices prove a box/prism the IFC solid is closed; 67 remain tessellated copies of open meshes (volume not measurable).

### Genuine discrepancies / items needing architectural confirmation

* 14 door/window groups whose source parts are inconsistent (e.g. the east-portal entrance door leaves lie 1.11 m inboard of their own jambs and pull handles). The IFC door sits on the frame (jamb) line. Confirm intended door line.
* 52 doors/windows are not hosted in a wall opening:
  * `SOUTHGATE-DOOR-0010` (EXT02-E-DOOR-JAMB-00-0-10.55) - assembly `E-CURTAIN-WALL`
  * `SOUTHGATE-DOOR-0011` (EXT02-E-DOOR-JAMB-00-1-11.55) - assembly `E-CURTAIN-WALL`
  * `SOUTHGATE-DOOR-0012` (EXT02-E-DOOR-JAMB-01-0-12.55) - assembly `E-CURTAIN-WALL`
  * `SOUTHGATE-DOOR-0013` (EXT02-E-DOOR-JAMB-01-1-13.55) - assembly `E-CURTAIN-WALL`
  * `SOUTHGATE-DOOR-0014` (EXT02-E-DOOR-JAMB-02-0-14.55) - assembly `E-CURTAIN-WALL`
  * `SOUTHGATE-DOOR-0015` (EXT02-E-DOOR-JAMB-02-1-15.55) - assembly `E-CURTAIN-WALL`
  * `SOUTHGATE-DOOR-0016` (EXT02-E-DOOR-JAMB-03-0-16.55) - assembly `E-CURTAIN-WALL`
  * `SOUTHGATE-DOOR-0017` (EXT02-E-DOOR-JAMB-03-1-17.55) - assembly `E-CURTAIN-WALL`
  * ... 44 more (WC cubicle doors and curtain-wall doors are parts of their IfcElementAssembly / IfcCurtainWall, which is valid IFC)

### Visual comparison

Matching-camera renders of the source snapshot and the IFC loaded through Bonsai, with silhouette overlays (red = source only, blue = IFC only): `renders/comparisons/gallery.html`, contact sheet `renders/comparisons/contact_sheet.png`.
