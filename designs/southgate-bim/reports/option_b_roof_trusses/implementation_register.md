# BIM implementation and outstanding-engineering register - Option B candidate OPTB-C01

## Implementation record

| Stage | Result |
|---|---|
| 1 Audit | Authoritative IFC sha `6cb86f6da743c810...` = publish record; no Bonsai session open; existing trusses were 16-panel (53 members, 17 gussets, 6 splice plates; bolts only on T06). Purlin seat measured on every line (`work/option_b/s02_roof_seating.json`). R2 basis extracted read-only with source checksums (`config/option_b/r2_basis.json`). |
| 2 Pilot | Isolated single-truss IFC (T05): all gates passed; Bonsai load / parametric edit / save verified. |
| 3 Library | 35 connection types, 9 built-up member types, 3 truss types, member / plate / bolt-set types (`schedules/*type_library.csv`). Rules in `config/option_b/detailing_rules.yaml` propagate to every instance on rebuild. |
| 4 Truss set | 11 trusses; genuine differences: TT-G sections and heel details, TT-R rigging tabs and line-specific R2 forces, TT-T typical. Connection types are keyed by family, truss type, connected sections and bolt counts. |
| 5 Roof integration | Interface and clash register (`roof_interface_and_clash_report.md`). |
| 6 Quantities | Schedules + BOQ extract from the IFC; reconciliation vs hand calculation and R2. |
| 7 Audit | `ifc_validation_report.md` - gates all pass; regression vs authoritative model. |
| 8 Publication | **Not published.** Candidate awaiting review and explicit approval. |

## Deviations from R2

| Id | Deviation | Reason | Effect |
|---|---|---|---|
| DEV-01 | Top-chord top of steel 10.5 mm below the R2 12.380 line (centroid line ~25-26 mm lower) | Keep the existing purlins / roof envelope unchanged (R2's line was the old member axis) | depth -2.4 % at bearing, -0.6 % at ridge; -12.6 kg per truss |
| DEV-02 | Lines 1-2 use line-2 sections (TC 2L90) | R2 cost basis takes max(line 1, line 2) | +85 kg on T02 vs R2 line-1 sizing |
| DEV-03 | Chord-to-gusset bolts at the 10 splice nodes are the splice bolts | the 8 splice bolts pass through the gusset; separate bolts would collide on the single gauge line | -40 bolts per truss vs the R2 rule |
| DEV-04 | Packers: ceil(clear/1.2)-1 per clear length, >= 1 per web | R2's take-off formula counts both ends twice | 86-88 vs 164 per truss |
| DEV-05 | M16 bolts on 60 mm legs | backmark 35 mm leaves 25 mm to the toe | 46-48 M16 sets per truss |

## Model conventions

- Stable IDs `SOUTHGATE-RTB-Txx-...`; GlobalIds = uuid5(project namespace, stable ID) - reruns are identical. Reused: `SOUTHGATE-TRUSS-T01..T11`.
- `SOUTHGATE_DesignStatus.DesignStatus` stays within the project vocabulary (truss PRELIMINARY_DESIGN; members, plates, bolts, connections CONCEPT_UNVERIFIED) with `GeometryStatus`, `MemberSizeStatus`, `ConnectionStatus`, `BoltPatternStatus` = ASSUMPTION_DEPENDENT, `EngineeringVerified` false, `EngineeringCertification` NOT CLAIMED.
- `SOUTHGATE_EngineeringWarnings` (strength, buckling, joint capacity, bolt group, connection geometry, restraint, grade, corrosion, tolerances, bearing, bolt slip) on every truss.
- Classification `SG-ROOF-BOQ` (aligned to RICS NRM2 work section 15 - QS to confirm) on every type.

## Outstanding engineering and information register

| Id | Category | Item | Severity | Description | Owner |
|---|---|---|---|---|---|
| OE-01 | Engineering | Member design | HIGH | All member sizes are R2 indicative sizes (central scenario). Strength, flexural-torsional buckling of double angles and Class 4 6 mm legs (70-75 mm angles in S355) unchecked. | Structural engineer |
| OE-02 | Engineering | Connection / bolt-group design | HIGH | Bolt counts follow the R2 take-off rule (max(2, F/100 kN) per web end; 4 chord bolts; 8 splice bolts). No bolt group, gusset, block tearing or net-section design. | Structural engineer |
| OE-03 | Engineering | Chord splice design | HIGH | Splice plates (8 mm placeholder) splice the connected legs only; outstanding legs unspliced. R2 recommends preloaded splice bolts or pre-camber (bolt slip). Shop vs site splices undecided. | Structural engineer |
| OE-04 | Engineering | Bearing / heel and support interface | HIGH | Truss-to-column bearing not designed; existing cap plate and 16 mm seat fin conflict with the heel (clash group C-01). Holding-down for ~80 kN uplift (R2). | Support study (separate) |
| OE-05 | Engineering | Lateral system and restraint | HIGH | Eaves wind girders / wall bracing (R2 ~10.6 t) and bottom-chord ties at <= 5.4 m are required and not modelled; existing rod-bracing end plates conflict with gussets (C-03). | Structural engineer |
| OE-06 | Engineering | Rigging trusses (lines 1-2) | MEDIUM | R2 recommends designing the rigging trusses for the future scenario (BC 2L100, TC 2L90/2L100). Modelled at the R2 central basis. Rigging tab provisions have no rated capacity. | Structural engineer + AV/rigging |
| OE-07 | Engineering | Wind-edge truss lines | MEDIUM | R2 analysed lines 0, 1, 2 and 4 only; lines 8-9 (edge-zone wind coefficients) adopt the line-4 sizes. | Structural engineer |
| OE-08 | Engineering | Setting-out deviation DEV-01 | MEDIUM | Top of steel set on the existing purlin seat (10.5 mm below R2's 12.380 line): centroid depth 1.444-1.447 m at bearing vs R2 1.48 m (-2.4 %), 5.784 m at ridge vs 5.82 m. Confirm in design analysis. | Structural engineer |
| OE-09 | Specification | Material grade | MEDIUM | S355JR assumed for members and plates (plate grade not in R2); availability and certification to confirm; S275 sensitivity in R2. | Engineer / QS |
| OE-10 | Specification | Corrosion protection | MEDIUM | Two-coat paint assumed (R2 cost basis); hot-dip galvanising decision pending (R2 s.11.3; bath length for 6 m members). | Client / engineer |
| OE-11 | Specification | Bolt specification | MEDIUM | M20 8.8 (R2 working assumption), M16 on 60 mm legs (placeholder); washer count, hole type, preload, coating not specified. | Engineer |
| OE-12 | Specification | Fabrication tolerances / execution class | MEDIUM | No execution class or tolerance specification (EN 1090 / SANS 2001-CS1). | Engineer |
| OE-13 | Detailing | Edge distances on 80 mm legs | LOW | Splice plates on 2L80 chords give a 25 mm edge distance at M20 (EN 1993-1-8 minimum 1.2 d0 = 26.4 mm). Placeholder detail; resolve at design (wider plate, M16, or 2L90). | Detailer |
| OE-14 | Detailing | Packing-plate spacing | LOW | Packers at <= 1.2 m clear (R2 rule) - verify against SANS 10162-1 / EN 1993-1-1 6.4.4 for compression members. | Engineer |
| OE-15 | Detailing | Holes in angles | LOW | Bolt holes are modelled in plates (voids) but not in angles; angle masses are gross nominal (BOQ convention). | BIM |
| OE-16 | Interfaces | Purlin cleats | LOW | Existing purlin cleats sit ~14 mm above the new top of steel; purlin package to re-detail. | Purlin package |
| OE-17 | Interfaces | Suspended equipment | MEDIUM | Raft clamps, lighting hangers, HVLS beams and arrays are off the 2.70 m panel points and have no designed attachments; rigging load plan, fan dynamic assessment and catwalk decision outstanding (R2 s.9-11). | Acoustic / AV / mechanical / client |
| OE-18 | Quantities | BOQ readiness | HIGH | Measured quantities are MODEL_DERIVED for concept-size members; bolts, packers and splice plates are ASSUMPTION_DEPENDENT. No waste, spares, rates or amounts applied. Not procurement-ready. | QS |
| OE-19 | BIM | Mapping / register merge on approval | LOW | New identities are in reports/option_b_roof_trusses/change/identity_register_new_elements.csv; merge into source/source_to_ifc_mapping.csv and update make_reports.py dispositions only after approval and publication. | BIM manager |
