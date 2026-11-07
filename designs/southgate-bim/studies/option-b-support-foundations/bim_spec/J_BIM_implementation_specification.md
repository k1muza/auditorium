# J — BIM implementation specification: Option B support structure (S3 hybrid)

**Status: specification only. Nothing in `bim/southgate.ifc` has been changed by this study.** Implement only after the recommendation has been reviewed and approved, and after gates G-A (wall construction, wind basis, code set) and G-B (site investigation) have been closed or explicitly waived.

Authoritative file at the time of the study: `bim/southgate.ifc`, sha256 `6cb86f6da743c810ff3281253c0cb72dbca67f8e36f948a88ba9de715b2b035e` (publish record 2026-11-07T09:37:59). Follow `AGENTS.md`: edit with Bonsai or the IfcOpenShell API, save to a new file, refresh quantities with `scripts/export/extract_quantities.py`, then publish with `build_ifc.py --publish --expected-current-sha256 <sha>`. Do **not** rebuild from the source snapshot.

## 1. Principles

1. **Model what the quantity surveyor measures, schedule what they count.** Footings, ground beams, columns, posts, bracing members and base plates are modelled as solids. Bolts, anchor reinforcement and bar reinforcement are carried as counts and masses in quantity sets. Reinforcement is not modelled bar by bar.
2. **Keep identity stable.** Replace geometry or profiles on existing elements where they keep their role (the 22 roof columns `SOUTHGATE-COL-0011…0032`, base plates `SOUTHGATE-PLATE-0576…0597`). Create new elements, with new stable IDs registered in `source/source_to_ifc_mapping.csv`, for anything that has no current counterpart.
3. **Status stays honest.** New and changed elements get `SOUTHGATE_DesignStatus.DesignStatus = CONCEPT_UNVERIFIED` and `StatusBasis = "Option B support study S3, preliminary, not engineered"`. Never set `ENGINEERING_VERIFIED`.
4. **Traceability.** Every new element gets `SOUTHGATE_Provenance` with `SourceKey = "STUDY:option-b-support-foundations/<group>/<index>"` and `MigrationRule = "STUDY-OPTB-S3"`. Existing elements that are changed keep their provenance; add `MigrationNotes` describing the change.

## 2. Element schedule (recommended S3, G2/F2 basis)

Sections and counts below are the study's preliminary values. The authoritative computed values (masses, counts, the pad schedule) are in `bim_spec/J_values.md` and `data/C2_*.csv`. Where they differ from this table, those files govern. If the site investigation selects S1 (gate G-B), regenerate both files for S1 before implementation.

| Element | IFC class / PredefinedType | Count | Profile / geometry | Material | Assembly | New / changed |
|---|---|---|---|---|---|---|
| Side columns, lines 0–10 | `IfcColumn` COLUMN | 22 | `IfcIShapeProfileDef` UC305x305x97, strong axis normal to the wall, −0.80 → +12.28 | S355JR (`IfcMaterial` "S355JR structural steel", category steel) | `ASM-COLBASE-<line><side>` | **changed**: profile UC254x254x73 → UC305x305x97 |
| Gable wind posts | `IfcColumn` COLUMN | 12 | UB533x210x82, −0.80 → top chord; offset 0.20 m outside the gable truss plane | S355JR | `ASM-POSTBASE-<line>-<k>` | **new** (`SOUTHGATE-COL-0100…0111`) |
| Eaves struts | `IfcMember` STRUT | 20 | CHS168.3x6.3 between truss heels | S355J2H | `ASM-ROOF-BRACING` | **new** |
| Eaves wind girders | `IfcMember` BRACE (diagonals), STRUT (inner chord) | 16 + 20 | CHS168.3x5 / CHS139.7x4.5 (purlin-independent) | S355J2H | `ASM-EAVES-GIRDER-S/N` | **new** |
| End-bay roof girders | `IfcMember` BRACE | 24 | CHS168.3x5 | S355J2H | `ASM-ENDBAY-GIRDER-W/E` | **new**; **retire** `SOUTHGATE-BRACE-0001…0004` (20 mm rods) |
| End-bay cross frames | `IfcMember` BRACE | 20 | CHS139.7x4.5 | S355J2H | `ASM-ENDBAY-GIRDER-W/E` | **new** |
| End-bay bottom-chord bracing | `IfcMember` BRACE | 8 | CHS139.7x4.5 | S355J2H | `ASM-ENDBAY-GIRDER-W/E` | **new** |
| Bottom-chord ties at 5.4 m | `IfcMember` TIEBAR | 50 | CHS88.9x3.2 | S355J2H | `ASM-BC-TIES` | **new** |
| Gable bracing | `IfcMember` BRACE / STRUT | 16 + 4 | CHS193.7x6.3 / CHS88.9x3.2 | S355J2H | `ASM-GABLE-BRACING-W/E` | **new** |
| Gable-post restraint struts | `IfcMember` STRUT | 2 rows per gable | CHS88.9x3.2 | S355J2H | `ASM-GABLE-BRACING-W/E` | **new** |
| Wall bracing, bays 1 and 5 | `IfcMember` BRACE (X in two halves, knees), STRUT (sill) | 16 + 8 + 12 | CHS219.1x8 / CHS114.3x5 / CHS101.6x3.6 | S355J2H | `ASM-WALL-BRACING-<bay><side>` | **new** |
| Base plates | `IfcPlate` BASE_PLATE | 34 | 30 mm plate, sizes from `data/C2_*.csv` | S355JR | `ASM-COLBASE-*` / `ASM-POSTBASE-*` | **changed** (22); **new** (12) |
| Base stiffeners | `IfcPlate` USERDEFINED "STIFFENER" | 88 | 15 mm gussets, 4 per fixed base | S355JR | `ASM-COLBASE-*` | **new** |
| Holding-down bolts | `IfcMechanicalFastener` ANCHORBOLT | 184 | One element per bolt; simple body (cylinder + anchor plate), `NominalDiameter` 0.024, `NominalLength` hef + 0.15 | 8.8 HDG | `ASM-COLBASE-*` | **new** |
| Truss bearing / heel cleats | `IfcPlate` + `IfcMechanicalFastener` BOLT | 22 + 4 | Concentric cap plate; heel restraint cleats at lines 0/10 | S355JR / 8.8 | `ASM-BEARING-<line><side>` | **changed** (cap/seat) / **new** (cleats) |
| Pad downstand shear keys | part of `IfcFooting` geometry (downstand) | per C2 schedule | 0.4 × 0.4 m × pad width | C25/30 | footing | **new** |
| Column pads (F2) | `IfcFooting` PAD_FOOTING | 22 | B × L × D from `data/C2_*.csv` (e.g. 2.3 × 2.3 × 0.80 m at line 0) | C25/30 (`IfcMaterial` "Concrete C25/30") | `ASM-COLBASE-*` | **replace** concept pads `SOUTHGATE-FTG-0002…0021` (geometry and dimensions) and **add** line-10 pads |
| Post pads | `IfcFooting` PAD_FOOTING | 12 | per schedule | C25/30 | `ASM-POSTBASE-*` | **new** |
| Wall strip footing (reinforced, continuous) | `IfcFooting` STRIP_FOOTING | 4 runs | 0.60 × 0.45 m, long walls and gables, integral with pads | C25/30 | `ASM-WALL-FOUNDATION-<side>` | **new**; review overlap with `SOUTHGATE-FTG-0022` (west strip) |
| Column encasement below FFL | `IfcColumn` USERDEFINED "ENCASEMENT" **or** `IfcCovering` WRAPPING | 22 | 0.60 × 0.60, −0.80 → +0.265 | C25/30 | `ASM-COLBASE-*` | **new** |
| Blinding | `IfcSlab` USERDEFINED "BLINDING" | 1 per footing | 50 mm under each footing | Concrete C15 | footing assembly | **new** (optional; see §4) |

Each base is an `IfcElementAssembly` (PredefinedType `USERDEFINED`, ObjectType "COLUMN BASE") aggregating the column foot, plate, stiffeners, anchor bolts, footing and encasement. That gives the QS one countable item per base while each part keeps its own quantities.

## 3. Property sets

| Pset | Applied to | Properties |
|---|---|---|
| `Pset_ColumnCommon` | columns, posts | `LoadBearing = True`, `IsExternal = False`, `Reference` = stable ID |
| `Pset_MemberCommon` | bracing | `LoadBearing = True`, `Span` |
| `Pset_FootingCommon` | footings | `LoadBearing = True` |
| `SOUTHGATE_StructuralDesign` (new) | all structural elements above | `Scheme = "S3"`, `DesignGroup` (COL, POST, EGD…), `BaseFixity` (FIXED_STRONG_AXIS / PINNED), `ULS_N_comp_kN`, `ULS_N_uplift_kN`, `ULS_M_kNm`, `ULS_H_kN`, `Utilisation`, `GoverningCombination`, `SoilScenario = "G2 (assumed)"`, `DesignSource = "studies/option-b-support-foundations/data/C2_base_reactions_and_foundation_schedule.csv"` |
| `SOUTHGATE_Reinforcement` (new) | footings, strips, encasement | `BottomSteel_mm2_per_m`, `TopSteel_mm2_per_m`, `RebarMass_kg`, `AnchorReinforcement_kg`, `RebarBasis = "preliminary - bar schedule required"` |
| `SOUTHGATE_Anchorage` (new) | base assemblies | `BoltCount`, `BoltDiameter_mm`, `Grade = "8.8"`, `Embedment_mm`, `AnchorPlates`, `ConeUtilisationWithoutReinforcement`, `AnchorReinforcement = "designed hairpins"`, `GroutThickness_mm` |
| `SOUTHGATE_DesignStatus` | all | as §1 |

## 4. Quantity sets

- `Qto_ColumnBaseQuantities`, `Qto_MemberBaseQuantities`, `Qto_PlateBaseQuantities`, `Qto_FootingBaseQuantities`: refresh with `extract_quantities.py` (ifc5d). Check that no empty Qto sets are left behind (see the ifc5d gotcha in the project notes).
- `SOUTHGATE_Quantities`: keep the geometry-derived volume and area. Add `NominalMass_kg = length × catalogue kg/m` for steel. Do **not** use render-material densities (O-04).
- **Derived items** (excavation, blinding, formwork, backfill, disposal): keep them out of the geometry. Implement them as approved rules in `config/quantity_rules.yaml` once the QS chooses the measurement standard (OW-025). The study's working assumptions are: working space 0.30 m each side, formation to FGL +0.10, blinding 50 mm, disposal bulking 1.25. These are recorded so the rules can be set; they are not approved.
- **Reinforcement**: mass is carried per footing in `SOUTHGATE_Reinforcement.RebarMass_kg` until bar schedules exist. No `IfcReinforcingBar` geometry at this stage. If bar-level BIM is needed later, use `IfcReinforcingBar` with `IfcReinforcingBarType` and `BarLength`/`NominalDiameter`, generated from the engineer's schedule rather than modelled by hand.
- Blinding may be carried as a quantity on the footing (`SOUTHGATE_Quantities.BlindingVolume_m3`) instead of an `IfcSlab`, if the QS prefers fewer elements.

## 5. Relationships

- `IfcRelAggregates`: base assembly → parts. The bracing assemblies → members.
- `IfcRelConnectsElements` (or `IfcRelConnectsWithRealizingElements` with the plate and bolts as realising elements): column ↔ footing, truss heel ↔ column, brace ↔ column. This lets the validator check column-to-footing support (review item O-06).
- `IfcRelContainedInSpatialStructure`: footings and encasement in storey 00; columns, posts and bracing in storey 00 (vertical elements), roof bracing in storey 03.
- `IfcRelAssignsToGroup`: an `IfcStructuralAnalysisModel`-free group "OPTB-S3-LATERAL-SYSTEM" for scheduling. A structural analysis model (`IfcStructuralAnalysisModel`) is **not** required for the BOQ and should come from the engineer's analysis software if it is wanted.

## 6. Validation after implementation

1. Every roof column and post has exactly one `IfcFooting` beneath it (new validator check).
2. No element is ENGINEERING_VERIFIED.
3. Steel nominal masses within ± 5 % of `bim_spec/J_values.md` and `data/D_steel_framing_comparison.csv`.
4. Footing concrete within ± 3 % of `data/E_foundation_comparison.csv` for the adopted soil and arrangement.
5. The retired roof rods are archived, not deleted, with `DesignStatus = SUPERSEDED_ARCHIVE`.
6. `scripts/validate/validate_ifc.py` passes, and `extract_quantities.py --check` reports no stale quantities.

## 7. What must not be done

- Do not overwrite `bim/southgate.ifc` except through the guarded publish command.
- Do not change the Option B trusses during this update. The gable top-chord issue (R05) is a separate truss-design action.
- Do not model the alternatives S1 and S2. They live only in this study.
