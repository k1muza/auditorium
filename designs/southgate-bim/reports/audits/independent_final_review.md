# Independent final review - bim/southgate.ifc (Southgate Worship Center, main auditorium)

Reviewer: independent AI review (Claude). Date 2026-11-07. Basis: the saved file `bim/southgate.ifc` (91,092,598 bytes, IFC4, header `ViewDefinition[DesignTransferView]`, written by IfcOpenShell 0.9.0.post1, migration run `20261107-060810_full`), opened in a clean interpreter (`.venv/Scripts/python -I`, IfcOpenShell 0.9.0.post1). The review scripts were kept outside the project. No project file was modified. I formed my conclusions from the IFC first and compared them with the project's own reports afterwards.

> **This is not formal engineering certification.** It is an automated, AI-assisted review of the information content of a concept-stage model. It does not check or approve the structural, building-services, fire, acoustic or code compliance of the design. Nothing in this report should be read as engineering verification.

## 1. Verdicts

| Perspective | Verdict | One-line reason |
|---|---|---|
| Architectural | **Accept with objections** | The geometry reproduces the source design to within millimetres for every class except doors. The glazed east and west gables, the north portal with its signage, the stage, the 2000 seats, the gallery, the west office wing with its terrace and spiral stair, and the restrooms are all present. The objections concern door lines, unhosted fills, missing office spaces, and interior comparison renders that do not prove what they claim. |
| BIM and quantity surveying | **Reject (for quantity/BOQ use in the current state)** | The stored and published quantities contain physically impossible values: 4,013 t of "steel" louvres, and a 100 mm insulation lining with a volume of 6,390 m³. Wall Qto values are wrong for 56 of the 210 walls, including the main envelope walls. 2,155 tessellated elements are labelled `NativeRepresentation=True`. The geometry and identity are sound, so the file is fine as a concept geometry model. |
| Structural and services | **Accept with objections** | No element claims engineering verification (`EngineeringVerified=False` on all 10,683 elements). However, 9 ground-bearing structural columns have no footing. Load-bearing slabs and cores carry the softer `EXISTING_DESIGN_REFERENCE` status. Services have no ports or connectivity. Indicative structural masses come from render-material solids. |

## 2. Verified facts (independent measurements)

| Item | Finding in saved IFC |
|---|---|
| Hierarchy | 1 IfcProject (Phase `CONCEPT DESIGN - NOT FOR CONSTRUCTION`), 1 IfcSite, 1 IfcBuilding, 4 storeys: 00 +0.265, 01 +4.0575, 02 +7.85, 03 +10.9. 14 IfcSpace, 19 IfcSpatialZone. SI units in metres. No IfcMapConversion, no TrueNorth, no site lat/long (consistent with `config/project.yaml`: UNVERIFIED). |
| Elements | 10,741 IfcElement in total: 10,642 with a body, 58 IfcOpeningElement, and 41 aggregates (32 IfcElementAssembly, 5 IfcCurtainWall, 3 IfcStair, 1 IfcRoof). Every element is contained or aggregated (0 orphans, 0 that are both). |
| Geometry produced | The IfcOpenShell iterator produced shapes for **10,642 of 10,642** body-bearing elements. 0 failures. |
| Overall extent | x -6.650..62.340, y -1.000..37.590, z -1.450..19.570, which gives **68.99 x 38.59 x 21.02 m**. Walls span x -2.48..59.00 and y 0..33.00, matching the hall 3.1..59.0 x 0..33.0 plus the office wing. The roof sheeting reaches z 16.96. |
| Per-element bounds vs source | I compared all 10,642 elements with `source/geometry_inventory.json` world AABBs, matched through `SOUTHGATE_Provenance.SourceObjects`. Max deviation is **0.0 to 0.3 mm** for walls, slabs, columns, beams, footings, plates, coverings, services and fasteners, and 3.1 mm for members (tapered source truss members, as the project states). Exceptions: windows 12.5 mm, seats 16.7 mm (1,286 ground-floor seats), and doors up to **1.107 m** (see O-11). |
| Seats | 2,000 IfcFurniture of type `FurnitureT-PROTO-PAN` (CHAIR): 1,310 on 00, 612 on 01 and 78 on 02. This is 1,310 stalls plus 690 gallery seats and matches the 2,000 visible source seats. |
| Body representation types | SweptSolid 4,395; Clipping 1,473 (all on extrusions); MappedRepresentation 4,326, of which 2,245 map a **tessellated** source and 1,854 map a unit cube or cylinder through a **non-uniform** scale operator; Tessellation 448. The tessellated total is **2,693 (25.3 %)**. |
| Materials | All elements except openings and aggregates have a material. 87 walls and 75 slabs use IfcMaterialLayerSetUsage. 1,427 beams, columns and members use IfcMaterialProfileSetUsage. There are 104 materials, all render names, e.g. "EXT02 - Warm champagne-grey metallic cladding" and "stone". |
| Types | 149 type objects. Untyped elements include 1,501 mechanical fasteners, 960 coverings, 916 plates and 92 footings. |
| Openings | 58 openings. All void an IfcWall and all are filled (32 doors, 26 windows). 66 of the 124 doors and windows fill no opening: 51 are parts of WC-cubicle assemblies or curtain walls, and 15 are free-standing (`SOUTHGATE-DOOR-0039` DOOR-N-FOYER, and `SOUTHGATE-WIN-0009..0022` VENT-03 sashes). |
| Assemblies | 11 TRUSS assemblies (T01-T11). 10 have 94 parts each (53 members, 23 plates, 18 bolts). T06 has 580 parts. Also: 5 curtain walls (E: 150 parts incl. 14 doors; W: 116), IfcRoof (265: 261 coverings and 4 screw sets), stage (76), north entrance portal (13), 4 WC-cubicle systems, 15 acoustic rafts, and 3 stairs (spiral: 125 parts). |
| Qto presence | Qto_*BaseQuantities on 4,216 elements. Qto NetVolume equals geometry volume (0.00 % deviation) for all walls, slabs, columns, beams, members, plates and footings. **No Qto exists on IfcSpace, IfcFastener, IfcRailing, IfcFurniture or IfcSanitaryTerminal.** |
| Hand checks (pass) | **Wall** `SOUTHGATE-WALL-0070` (CORE-N-END): 6.2 x 0.2 x 11.6 = 14.384 m³; the Qto gives 14.384 m³ and a side area of 71.92 m² (correct). **Slab** `SOUTHGATE-SLAB-0036` (MEZZ-CROSS): 32.4 x 2.6 = 84.24 m², x 0.2 = 16.848 m³, perimeter 70.0 m. All three match the Qto. **Column** `SOUTHGATE-COL-0011` (UC 254x254x73.1): profile area 0.009155 m² x 13.083 m = 0.1198 m³, which matches the Qto. The resulting 940 kg compares with 956 kg nominal at 73.1 kg/m, a 1.7 % gap from the simplified profile. **Purlin** `SOUTHGATE-PURL-0001` (Lipped C200x75x20x2.5): 0.000950 m² x 5.56 m = 0.00528 m³, which matches; that is 41.5 kg against 40.5 kg nominal. **Truss chord** `SOUTHGATE-MEMB-0614` (2L100x100x10): L = 2.113 m, V = 0.0077 m³, which implies 36.6 cm² against about 38.4 cm² catalogue. That is plausible because the root radii are omitted. |
| Hand checks (fail) | See O-01 and O-02. |
| Design status | CONCEPT_UNVERIFIED 5,150; EXISTING_DESIGN_REFERENCE 2,864; PRELIMINARY_DESIGN 2,669. `EngineeringVerified=False` on 10,683 of 10,683. No ENGINEERING_VERIFIED or APPROVED_FOR_DOCUMENTATION values. |
| Services and structure relationships | 8 IfcDistributionSystem groups (rainwater 287, ventilation 134, plumbing 129, lighting 102, sanitary 66, exhaust 51, electro-acoustic 10, electrical 6). **0 IfcDistributionPort, 0 IfcRelConnectsPorts, 0 IfcRelConnectsElements, 0 structural analysis models.** No IfcClassificationReference. |
| Source coverage | The register has 13,699 rows, one per inventory object. Of the 12,000 visible objects, 11,388 were migrated. The 612 visible objects not migrated are: 143 children's church, 152 lights and cameras, about 80 site and paving objects, 8 room-label texts, 8 empties, 3 check markers, 1 archived duplicate slab, and 228 geometric duplicates. I verified all 228 duplicates: identical AABB and vertex count, and the twin was migrated. I found **no significant visible in-scope construction that is missing**. 88 hidden objects (concept footings, terrace stair parts) were migrated deliberately. |

## 3. Objections

### Blocking

**O-01 Impossible volumes and masses are stored in the IFC and published in the quantity schedules.**
Evidence: 33 tessellated elements store a `SOUTHGATE_Quantities.GeometryVolume_m3` larger than their own bounding-box volume.
- `SOUTHGATE-COV-0153` (VENT-07-LINING-N, 100 mm roof insulation, 899 m²) stores 6,389.6 m³ inside a 3,963.6 m³ box. The true value is about 90 m³.
- `SOUTHGATE-AT-0036..0040` (VENT-01 louvre banks, box 4.66 x 1.0 x 2.3 m = 10.7 m³) store 99.7 m³ each, which gives an `IndicativeMassFromDensity_kg` of **782,793 kg each**.
- The 16 VENT-04 fan aprons (`SOUTHGATE-FAST-1958..2022`, box 0.19 m³) store 4.7 to 8.1 m³, which gives 37 to 64 t each.
- `SOUTHGATE-RAIL-0014` (box 3.2 m³) stores 33.2 m³.

These values are in `reports/quantities/quantity_schedule_elements.csv`. The summary line `IfcAirTerminal, LOUVRE ... IndicativeMass 3,949,258.9 kg` is published. The total indicative mass of the model is 8,255 t, of which IfcAirTerminal accounts for 4,013 t. All 11 roof trusses together come to 45.6 t.
Fix: for any element whose source mesh is open or non-manifold (`source_mesh_closed=False`), set the volume and mass to null (not a number). Add a sanity rule, volume ≤ AABB volume, to `extract_quantities.py --check` and to `validate_ifc.py`. Regenerate the schedules.

**O-02 Wall base quantities are wrong for 56 of the 210 walls, including the primary envelope.**
Evidence: `SOUTHGATE-WALL-0082` and `-0083` (EXT-E-0-T and EXT-E-2-T, the east-end walls; bounding box 0.3 x 13.7 x 13.3 m) have Qto Length 0.30, Width 13.70 and GrossSideArea 4.35 m². The real face is about 13.7 x 13.3, roughly 182 m² gross. `SOUTHGATE-WALL-0123` and `-0124` (GABLE-W and GABLE2-W, 16.2 m long) have side areas of 1.33 m² and 5.06 m². 52 restroom-cubicle components are also affected; for example, the panels `SOUTHGATE-WALL-0163..` (1.68 x 1.95 m) have a GrossSideArea of 0.04 m². These walls are extruded along their length or height rather than along a wall axis, so ifc5d swaps Length and Width. The total wall NetSideArea (3,023 m²) is therefore unreliable, and the audit row "Wall areas (gross/net) - MODEL-DERIVED" is not true.
Fix: rebuild these walls as DumbLayer2 axis-based walls (or extrude the profile along the wall axis), or move the cubicle parts out of IfcWall (see O-05). Re-run the Qto, and add a check that compares GrossSideArea with the AABB face area.

### Major

**O-03 `NativeRepresentation=True` is set on 2,155 meshes, so the "95 % native" claim is overstated.**
Evidence: the 2,089 IfcFurniture (all 2,000 seats and 89 restroom accessories) and the 66 IfcSanitaryTerminal use a MappedRepresentation whose source is an IfcPolygonalFaceSet, yet they carry `NativeRepresentation=True`. Their Provenance text even says "(Tessellation)". A further 1,854 acoustic fasteners and rails (`FastenerT-ACOUSTIC-SHARED-UNIT-CYLINDER`, `MemberT-ACOUSTIC-SHARED-UNIT-CUBE`) are unit primitives distorted by `IfcCartesianTransformationOperator3DnonUniform`. They are not editable profile members and carry no Qto. The measured tessellated share is 25.3 %, not the 5 % that "95.0 % native" implies. The audit sentence "Custom geometry is never labelled parametric" is contradicted by the file. Type-mapped tessellation is a reasonable choice for seats and sanitaryware, but it should not be labelled native.
Fix: set `NativeRepresentation` from the actual item type of the mapped source. Report "type-mapped mesh" as its own category.

**O-04 Materials are render finishes, so indicative masses are meaningless for structure and envelope.**
Evidence:
- The 16 `FACADE-*-BAY-*-BRICK-INFILL` walls (source `facade_system`: "Brick masonry infill") and the 18 `FACADE-*-GRID-*-MASONRY-PIER` IfcColumn carry "Warm champagne-grey metallic cladding". Their masses are computed as solid aluminium: `SOUTHGATE-WALL-0107` comes to 52.0 t, and IfcWall with this material totals 1,804 t.
- The gallery rakers `SOUTHGATE-BEAM-0028..0034` are solid 280x800 "steel" rectangles at 24.5 t each.
- `SOUTHGATE-BEAM-0025` (GALLERY-TRANSFER-FRONT, solid 450x1200 steel) comes to 137.3 t.
- The terrace girders `SOUTHGATE-BEAM-0009..0011` come to 23.8 t each.
- Concrete slabs and columns use "stone" with no density (the ST-stone-* slab types, ColumnT-RECT300x300-stone).

The project notes this (OW-016, OW-026), but the masses are still written into the Qto `GrossWeight`/`NetWeight` and the schedules as numbers.
Fix: map render materials to construction materials (concrete, masonry, steel section). Suppress density masses for solid placeholder sections until real sections are known.

**O-05 Misclassification inflates counts.**
Evidence:
- 94 of the 210 IfcWall are WC-cubicle components (types `WallT-RR-ASSET-CUBICLE-ADJUSTABLE-LEG` x42, `-SIDE-PANEL-1537` x32, `-URINAL-DIVIDER` x12, and 8 pilaster rails/screens). The 42 legs are not walls.
- 180 IfcWasteTerminal (GULLYGRATING) represent only 18 inlets: 162 are individual grate bars (`RWG-CATCHPIT-GRATE-BAR-*`).
- 6 hanger rods (`STG-LGT-HANGER-*`, `SOUTHGATE-LGT-0083..0088`) are IfcLightFixture.

Fix: make each cubicle system one assembly whose parts are IfcPlate/IfcMember/IfcDiscreteAccessory (or IfcFurniture). Make one IfcWasteTerminal per grating, aggregating its bars. Change the hangers to IfcDiscreteAccessory.

**O-06 Structural interface gap: ground-bearing columns have no foundation.**
Evidence: 9 structural columns reach z -0.80 with no IfcFooting beneath them:
- the 7 `COL-GALLERY-REAR-*` columns (`SOUTHGATE-COL-0004..0010`, x = 52.35; the nearest pad, `SOUTHGATE-FTG-0018/0019`, starts at x = 52.54)
- the east-end truss columns `COL-ROOF-10-0/10-1` (`SOUTHGATE-COL-0015/0016`, x = 58.85, no grid-10 pad)

The 2 north-portal front columns (`SOUTHGATE-COL-0069/0070`) and the 2 east tall-portal columns (`SOUTHGATE-COL-0033/0034`) also stop at grade with no footing. This reproduces the source faithfully, but no element or outstanding-work item names these specific supports. OW-001 is generic.
Fix: add concept pads, marked CONCEPT_UNVERIFIED, or record a per-element `SOUTHGATE_DesignStatus.VerificationNote` "no foundation modelled". Add a column-to-footing check to the validator.

**O-07 The design status of load-bearing slabs and cores is softer than that of their supports.**
Evidence: the gallery tier slabs `SOUTHGATE-SLAB-0051..0064` (TIER-01..14), the suspended slabs MEZZ-CROSS/MEZZ-SERVICE/UPPER-CROSS/UPPER-SERVICES (`-0036/-0037/-0065/-0066`), the core walls (`SOUTHGATE-WALL-0070/0071/0076/0290`) and `SOUTHGATE-SLAB-0001` (BIM-OFFICE-GROUND-BEARING-RC-SLAB, which the source marks PRELIMINARY_GEOMETRIC) all carry `EXISTING_DESIGN_REFERENCE` with the basis "architectural geometry". The rakers and transfer beam that carry those tiers are CONCEPT_UNVERIFIED. No false verification is claimed. However, a structural filter on CONCEPT_UNVERIFIED would miss the gallery deck and cores, and `Pset_*Common.LoadBearing` is not asserted anywhere.
Fix: apply the structural status rule to every slab and wall that carries load, and set LoadBearing where the source intent is clear.

**O-08 The visual comparison does not verify the hall interior.**
Evidence: `scripts/export/render_views.py` (source mode) renders every in-scope visible mesh, including the 14 `Spaces` boxes. These are hidden for render in the source. `SPACE-HALL` (3.4..43.0 x 0.3..32.7 x 0..2.7) is drawn as an opaque tan block. As a result, `07_auditorium_interior_source.png`, `08_stage_source.png` and `11_roof_off_interior_source.png` show no seating and no stage, while the IFC renders show both. The IoU is 1.000 in views 07 and 08 only because the silhouette fills the frame. I verified the seats and stage numerically (section 2), but the gallery does not.
Fix: exclude source `Spaces` from source renders. Use per-class colour or depth comparison for interior views instead of silhouettes.

### Minor

- **O-09 Bolt counts are not representative.** Gusset bolts exist only on truss T06 (486 `ROOF-GUSSET-BOLT-05-*`); the other 10 trusses have 18 splice bolts each. "Connection plates and bolts - counts derivable per assembly" would understate by about 4,860 bolts. Fix: flag T06 as a representative sample, or replicate the bolts.
- **O-10 Spaces are not measurable.** The 14 IfcSpace have no Qto_SpaceBaseQuantities, so the claim that floor areas are "MODEL-DERIVED" from IfcSpace is not supported. The source boxes are crude; HALL, for example, is 2.7 m high. The 8 office rooms have no spaces (OW-018).
- **O-11 Door placement.** 14 east curtain-wall doors (`SOUTHGATE-DOOR-0010..0021`) are 0.888 m off their source leaves. The hall west doors `SOUTHGATE-DOOR-0026/0027` are 1.107 m off because the source leaves are modelled open. `SOUTHGATE-DOOR-0039` and the VENT-03 sashes `SOUTHGATE-WIN-0009..0022` fill no opening; the facade bays have profile voids (OW-024).
- **O-12 No connectivity.** There are no distribution ports or element connections, so services are groupings only, and no IfcClassificationReference (Uniclass/NRM) exists for cost mapping.
- **O-13 Provenance detail.** `source/geometry_inventory.json` records `"is_dirty": true`, meaning the snapshot was inventoried with unsaved in-session state. The snapshot SHA is pinned, so this is low risk, but it is worth confirming that the inventory equals the saved snapshot.

## 4. Points where I disagree with the project's own audit reports

| Project claim | Independent finding |
|---|---|
| "IFC elements with native parametric / swept / type-mapped representations: 10137 (95.0 %)"; "Custom geometry is never labelled parametric" (bim_quality_audit, completeness A) | 2,155 tessellated mapped elements are flagged native; the tessellated share is 25.3 % (O-03). |
| IfcDoor "AABB dev max 0.04 m"; IfcFurniture "AABB dev max 0.0" | Doors reach 1.107 m (DOOR-0026/0027) and 0.888 m (14 east doors). Seats reach 16.7 mm on 1,286 elements. The table appears to exclude the open or offset leaf parts. |
| "Wall areas (gross/net) - MODEL-DERIVED" | 56 walls have invalid Qto, including the east and west envelope (O-02). |
| "67 remain tessellated copies of open meshes (volume not measurable)" | Volumes are still stored and turned into masses, and 33 are physically impossible (O-01). |
| "Floor areas - MODEL-DERIVED" (IfcSpace) | No space quantities exist (O-10). |
| "Connection plates and bolts (counts) - counts derivable per assembly" | Bolts are present on only 1 of 11 trusses (O-09). |
| Visual comparison IoU 1.0 for 07/08 as fidelity evidence | Not discriminating, because the source renders include opaque space boxes (O-08). |
| "Design status ... elements claiming engineering verification: 0" | **Agree.** Confirmed: 0 of 10,683. |
| Geometry "10642 of 10683 produce geometry", extent 68.99 x 38.59 x 21.02 m, hierarchy and containment correct | **Agree.** Independently reproduced. |

## 5. Perspective notes

**Architectural.** The model does represent the design:
- glazed east gable (`SOUTHGATE-ASM-E-CURTAIN-WALL`, 34 curtain panels, 14 doors) and west gable (`-W-CURTAIN-WALL`, 32 panels)
- north entrance portal assembly (13 parts) with "SOUTHGATE WORSHIP CENTER" letters (`SOUTHGATE-SIGN-0002`, backing, halo and supports), plus the east entrance sign `SOUTHGATE-SIGN-0001`
- stage assembly (76 parts)
- 1,310 stall and 690 gallery seats
- 14 gallery tiers
- west office wing with roof-terrace slabs, the spiral stair assembly (125 parts) and 8 office-room doors (`SOUTHGATE-DOOR-0001..0009`)
- restrooms with 37 WCs, 14 urinals, 15 basins and 4 cubicle systems

The fidelity of the bounding boxes is excellent. The objections are O-08, O-10, O-11 and the 8 office rooms without spaces.

**BIM and quantity surveying.** Identity, provenance, containment, aggregation and profile-set usage are of good quality. Volumes of swept elements are reliable and pass hand checks. The file is not fit for a BOQ until O-01, O-02, O-04 and O-05 are fixed and O-03 is relabelled. Specifically: the published schedules carry impossible values, wall areas fail on the envelope, materials are render finishes, and the counts of walls and waste terminals are inflated.

**Structural and services.** The status discipline is honest: no verification is claimed anywhere, and the statuses for structure (CONCEPT_UNVERIFIED) and services (PRELIMINARY_DESIGN) are applied consistently, with stated bases. The objections are O-06, O-07 and O-12. In addition, solid placeholder sections (rakers, the transfer beam, terrace girders) should not produce tonnage.

## 6. Method notes

The checks ran in a clean interpreter with IfcOpenShell 0.9.0.post1:
- world-coordinate shapes for all elements through the geometry iterator, with mesh volume from `ifcopenshell.util.shape`
- per-element AABB matching against the source inventory through `SourceObjects`
- Qto values read with `ifcopenshell.util.element`
- hand calculations from extrusion depth and profile polygon area
- spatial checks for column-to-footing support
- a review of contact-sheet renders 01-11
- schema validation with EXPRESS WHERE rules (`ifcopenshell.validate`, `express_rules=True`), attempted but **not completed**: I stopped it after about 35 minutes with no result. The WHERE rules therefore remain unchecked, by both the project and this review. I recommend running a full check with buildingSMART's IFC Validation Service before the model is issued.
