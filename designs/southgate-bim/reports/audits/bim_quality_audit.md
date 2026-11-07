# BIM quality audit - bim/southgate.ifc

Generated 2026-11-07T10:00:06. Validation ran on the SAVED file in a clean interpreter (`python -I scripts/validate/validate_ifc.py`, IfcOpenShell only, no project code).

## C. BIM information quality

| Check | Result |
|---|---|
| Schema | IFC4 (Bonsai 0.9.0 default); units VOLUMEUNIT=CUBIC_METRE, PLANEANGLEUNIT=RADIAN, AREAUNIT=SQUARE_METRE, MASSUNIT=KILOGRAM, LENGTHUNIT=METRE |
| Schema validation (ifcopenshell.validate) | 0 issue(s); EXPRESS WHERE rules checked: False |
| Hierarchy | 1 project / 1 site / 1 building / 4 storeys; nesting correct: True |
| Spatial containment | 10521 elements; not contained and not aggregated: 0 |
| Spaces / zones | 14 IfcSpace (aggregated to storeys) / 19 IfcSpatialZone (referenced) |
| Stable identities | Name = SOUTHGATE-<CAT>-NNNN, deterministic GlobalIds (uuid5); duplicates: 0; persistent map `source/source_to_ifc_mapping.csv` |
| Materials | elements without material: 0; layer-set usages 162; profile-set usages 1433; 104 materials (source names kept) |
| Element types | 5921 typed occurrences, 150 type objects |
| Openings / fillings | 58 openings, all voiding a host: True, filled: 58; doors+windows filling openings 58 of 124 |
| Assemblies | 41 ({'IfcElementAssembly': 32, 'IfcCurtainWall': 5, 'IfcRoof': 1, 'IfcStair': 3}); empty: 0 |
| Base quantities | 4222 of 10521 elements carry Qto_*BaseQuantities (ifc5d) |
| Design status | {'CONCEPT_UNVERIFIED': 5220, 'EXISTING_DESIGN_REFERENCE': 2800, 'PRELIMINARY_DESIGN': 2501}; elements claiming engineering verification: 0 |
| Body representation types | {'SweptSolid': 4233, 'Tessellation': 448, 'Clipping': 1473, 'MappedRepresentation': 4326} |
| Geometry | 10480 of 10521 elements produce geometry; extent [68.99, 38.59, 21.02] m |

### Native vs custom representation by class

| IFC class | native | custom (tessellated) |
|---|---:|---:|
| IfcActuator | 28 | 0 |
| IfcAirTerminal | 36 | 18 |
| IfcAudioVisualAppliance | 10 | 0 |
| IfcBeam | 40 | 4 |
| IfcBuildingElementProxy | 5 | 30 |
| IfcColumn | 95 | 4 |
| IfcCovering | 842 | 118 |
| IfcDiscreteAccessory | 85 | 53 |
| IfcDoor | 84 | 0 |
| IfcDuctSegment | 4 | 15 |
| IfcDuctSilencer | 38 | 0 |
| IfcEvaporativeCooler | 10 | 0 |
| IfcFan | 8 | 15 |
| IfcFastener | 268 | 1656 |
| IfcFooting | 92 | 0 |
| IfcFurniture | 19 | 2116 |
| IfcLightFixture | 90 | 6 |
| IfcMechanicalFastener | 1497 | 4 |
| IfcMember | 1340 | 223 |
| IfcOutlet | 6 | 0 |
| IfcPipeFitting | 40 | 41 |
| IfcPipeSegment | 48 | 107 |
| IfcPlate | 914 | 48 |
| IfcRailing | 43 | 18 |
| IfcRampFlight | 4 | 0 |
| IfcSanitaryTerminal | 0 | 66 |
| IfcSensor | 13 | 0 |
| IfcSlab | 81 | 1 |
| IfcSpace | 14 | 0 |
| IfcSpatialZone | 19 | 0 |
| IfcStairFlight | 23 | 0 |
| IfcWall | 112 | 4 |
| IfcWasteTerminal | 18 | 0 |
| IfcWindow | 40 | 0 |

Native = authored with Bonsai/IfcOpenShell native patterns: DumbLayer2 layered walls, DumbLayer3 layered slabs, IfcMaterialProfileSet(Usage) profile members (with end clippings where cut), parametric door/window types, extruded area solids for proven prisms, or type-mapped instances (IfcRepresentationMap). Custom = the exact source tessellation as IfcPolygonalFaceSet on a correctly classified element (seat type body, sanitaryware, luminaires, bent pipes, flashings, signage letters...). Custom geometry is never labelled parametric.

### Known information gaps

* Profiles: steel sections are IfcArbitraryClosedProfileDef / composite profiles taken from the exact source cross-section, named with the source designation (e.g. `2L100x100x10`, `UC 254x254x73.1`). Replacing them with parameterised IfcLShapeProfileDef / IfcIShapeProfileDef / IfcCShapeProfileDef is outstanding (BIM item).
* Material specifications: materials keep the source render-material names; structural/finish specifications are mostly `UNSPECIFIED`/`CONCEPT` (`SOUTHGATE_MaterialStatus`). 'stone' slab material is a render placeholder.
* Pset_*Common carries Reference/Status only; IsExternal, LoadBearing, FireRating, AcousticRating etc. are not asserted because the source does not define them.
* Annex office rooms have names (labels) but no IfcSpace volumes; only the 14 source Spaces were migrated.
* 52 doors/windows without wall openings (see completeness report).

## D. Quantity readiness

Quantities are computed by IfcOpenShell's ifc5d engine (rule set `IFC4QtoBaseQuantities`) from the current IFC geometry and can be re-run at any time (`scripts/export/extract_quantities.py`; `--check` detects stale stored values). Schedules: `reports/quantities/quantity_schedule_elements.csv`, `quantity_schedule_summary.csv`.

| Category | IFC basis | Readiness | Notes |
|---|---|---|---|
| Concrete volumes - ground and suspended slabs | IfcSlab BASESLAB/FLOOR | PRELIMINARY | geometry verified (exact source match); concrete grade, reinforcement and slab build-up unspecified |
| Foundations (pads, strips) | IfcFooting | ASSUMPTION-DEPENDENT | concept geometry only, CONCEPT_UNVERIFIED; not for BOQ until engineered; excavation/blinding/formwork/backfill not modelled |
| Structural steel lengths | IfcMember/IfcBeam/IfcColumn (profile sets) | MODEL-DERIVED (VERIFIED GEOMETRY) | lengths/volumes match source within tolerances; truss scheme itself is preliminary and under separate structural comparison |
| Structural steel mass | SOUTHGATE_Quantities | PRELIMINARY | volume x 7850 kg/m3 and length x source nominal kg/m; grade/certification unconfirmed |
| Connection plates and bolts (counts) | IfcPlate / IfcMechanicalFastener | PRELIMINARY | counts derivable per assembly; connection design not engineered |
| Roof covering (IBR sheets) - count, length, area | IfcCovering ROOFING | MODEL-DERIVED | 166 sheets as individual elements; laps/end-laps per supplier not modelled |
| Flashings, ridge caps, gutters, downpipes | IfcCovering / IfcPipeSegment | PRELIMINARY | lengths available; several are tessellated (volume only approximate) |
| Roofing fasteners | IfcMechanicalFastener ROOF_SCREW_SET | ASSUMPTION-DEPENDENT | source models screws as 4 merged meshes; count requires an approved fixing specification |
| Wall areas (gross/net) | IfcWall Qto_WallBaseQuantities | MODEL-DERIVED | net side areas deduct real openings for consolidated/hosted walls; build-ups (finishes, insulation) not layered |
| Glazing areas | IfcPlate CURTAIN_PANEL / IfcWindow | MODEL-DERIVED | curtain-wall panels and window overall areas; glass specification concept |
| Door and window schedules | IfcDoor / IfcWindow | MODEL-DERIVED | count, overall width/height, type; hardware/fire rating not specified |
| Floor areas | IfcSpace / IfcSlab | MODEL-DERIVED | 14 source spaces; annex rooms have no IfcSpace yet |
| Ceiling areas | IfcCovering CEILING | PRELIMINARY | acoustic raft panels, soffits; general ceilings not modelled in source |
| Seating | IfcFurniture CHAIR (type-mapped) | MODEL-DERIVED | 2000 seats, product not selected |
| Sanitary fittings | IfcSanitaryTerminal | MODEL-DERIVED (COUNTS) | WC/urinal/basin counts by room (RR-V2) |
| Services (vent, plumbing, lighting) | IfcFlow* / IfcLightFixture | ASSUMPTION-DEPENDENT | proposal/allowance geometry - PRELIMINARY_DESIGN; not an engineered services design |
| Reinforcement, formwork, excavation, backfill | - | UNAVAILABLE | not in source; requires structural design and measurement rules |