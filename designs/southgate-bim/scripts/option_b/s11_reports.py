"""Assemble the Option B deliverables into reports/option_b_roof_trusses/ (generated - do not hand-edit).

  .venv/Scripts/python scripts/option_b/s11_reports.py <candidate dir>
"""
import csv, json, shutil, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
C = Path(sys.argv[1])
OUT = ROOT / "reports/option_b_roof_trusses"
for sub in ("schedules", "views", "interfaces", "validation", "reconciliation", "change"):
    (OUT / sub).mkdir(parents=True, exist_ok=True)
W = ROOT / "work/option_b"
for p in (W / "schedules").glob("*"):
    shutil.copy2(p, OUT / "schedules" / p.name)
for p in (W / "reconciliation").glob("*"):
    shutil.copy2(p, OUT / "reconciliation" / p.name)
for p in (W / "interfaces").glob("*"):
    shutil.copy2(p, OUT / "interfaces" / p.name)
for p in (W / "views/png").glob("*.png"):
    shutil.copy2(p, OUT / "views" / p.name)
for p in (W / "views/renders").glob("*.png") if (W / "views/renders").exists() else []:
    shutil.copy2(p, OUT / "views" / p.name)
for n in ("optb_validation.json", "project_ifc_validation.json", "stale_check.json", "bonsai_resaved_bonsai.json"):
    if (C / n).exists():
        shutil.copy2(C / n, OUT / "validation" / n)
pil = sorted((W / "pilot").glob("*/"))[-1]
for n in ("validation.json", "validation_bonsai_saved.json", "pilot_T05_bonsai_saved_bonsai.json", "pilot_manifest.json"):
    if (pil / n).exists():
        shutil.copy2(pil / n, OUT / "validation" / ("pilot_" + n if not n.startswith("pilot") else n))
man = json.load(open(C / "change_manifest.json"))
shutil.copy2(C / "identity_register.csv", OUT / "change" / "identity_register_new_elements.csv")
with open(OUT / "change" / "superseded_elements.csv", "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=list(man["superseded"][0].keys())); w.writeheader(); w.writerows(man["superseded"])
with open(OUT / "change" / "reused_identities.csv", "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=list(man["reused"][0].keys())); w.writeheader(); w.writerows(man["reused"])
slim = {k: v for k, v in man.items() if k not in ("superseded",)}
slim["superseded_count"] = len(man["superseded"])
json.dump(slim, open(OUT / "change" / "change_manifest.json", "w"), indent=1)

V = json.load(open(C / "optb_validation.json"))
PV = json.load(open(C / "project_ifc_validation.json")) if (C / "project_ifc_validation.json").exists() else {}
ST = json.load(open(C / "stale_check.json")) if (C / "stale_check.json").exists() and (C / "stale_check.json").stat().st_size else {}
BR = json.load(open(C / "bonsai_resaved_bonsai.json")) if (C / "bonsai_resaved_bonsai.json").exists() else {}
REC = json.load(open(W / "reconciliation/reconciliation.json"))
SS = json.load(open(W / "schedules/schedule_summary.json"))
IF = json.load(open(W / "interfaces/interfaces.json"))
T = SS["totals"]

# ------------------------------------------------------------------ outstanding engineering register
ENG = [
 ("OE-01", "Engineering", "Member design", "All member sizes are R2 indicative sizes (central scenario). Strength, flexural-torsional buckling of double angles and Class 4 6 mm legs (70-75 mm angles in S355) unchecked.", "HIGH", "Structural engineer", "member sizes, tonnage"),
 ("OE-02", "Engineering", "Connection / bolt-group design", "Bolt counts follow the R2 take-off rule (max(2, F/100 kN) per web end; 4 chord bolts; 8 splice bolts). No bolt group, gusset, block tearing or net-section design.", "HIGH", "Structural engineer", "bolt and plate counts"),
 ("OE-03", "Engineering", "Chord splice design", "Splice plates (8 mm placeholder) splice the connected legs only; outstanding legs unspliced. R2 recommends preloaded splice bolts or pre-camber (bolt slip). Shop vs site splices undecided.", "HIGH", "Structural engineer", "splice plates, bolts, erection"),
 ("OE-04", "Engineering", "Bearing / heel and support interface", "Truss-to-column bearing not designed; existing cap plate and 16 mm seat fin conflict with the heel (clash group C-01). Holding-down for ~80 kN uplift (R2).", "HIGH", "Support study (separate)", "bearing plates, HD bolts, columns"),
 ("OE-05", "Engineering", "Lateral system and restraint", "Eaves wind girders / wall bracing (R2 ~10.6 t) and bottom-chord ties at <= 5.4 m are required and not modelled; existing rod-bracing end plates conflict with gussets (C-03).", "HIGH", "Structural engineer", "bracing steel, connection provisions"),
 ("OE-06", "Engineering", "Rigging trusses (lines 1-2)", "R2 recommends designing the rigging trusses for the future scenario (BC 2L100, TC 2L90/2L100). Modelled at the R2 central basis. Rigging tab provisions have no rated capacity.", "MEDIUM", "Structural engineer + AV/rigging", "TT-R sections, tabs"),
 ("OE-07", "Engineering", "Wind-edge truss lines", "R2 analysed lines 0, 1, 2 and 4 only; lines 8-9 (edge-zone wind coefficients) adopt the line-4 sizes.", "MEDIUM", "Structural engineer", "TT-T sizes at lines 8-9"),
 ("OE-08", "Engineering", "Setting-out deviation DEV-01", "Top of steel set on the existing purlin seat (10.5 mm below R2's 12.380 line): centroid depth 1.444-1.447 m at bearing vs R2 1.48 m (-2.4 %), 5.784 m at ridge vs 5.82 m. Confirm in design analysis.", "MEDIUM", "Structural engineer", "member forces at the heel panels"),
 ("OE-09", "Specification", "Material grade", "S355JR assumed for members and plates (plate grade not in R2); availability and certification to confirm; S275 sensitivity in R2.", "MEDIUM", "Engineer / QS", "steel specification"),
 ("OE-10", "Specification", "Corrosion protection", "Two-coat paint assumed (R2 cost basis); hot-dip galvanising decision pending (R2 s.11.3; bath length for 6 m members).", "MEDIUM", "Client / engineer", "surface treatment item"),
 ("OE-11", "Specification", "Bolt specification", "M20 8.8 (R2 working assumption), M16 on 60 mm legs (placeholder); washer count, hole type, preload, coating not specified.", "MEDIUM", "Engineer", "bolt sets"),
 ("OE-12", "Specification", "Fabrication tolerances / execution class", "No execution class or tolerance specification (EN 1090 / SANS 2001-CS1).", "MEDIUM", "Engineer", "fabrication"),
 ("OE-13", "Detailing", "Edge distances on 80 mm legs", "Splice plates on 2L80 chords give a 25 mm edge distance at M20 (EN 1993-1-8 minimum 1.2 d0 = 26.4 mm). Placeholder detail; resolve at design (wider plate, M16, or 2L90).", "LOW", "Detailer", "splice plates"),
 ("OE-14", "Detailing", "Packing-plate spacing", "Packers at <= 1.2 m clear (R2 rule) - verify against SANS 10162-1 / EN 1993-1-1 6.4.4 for compression members.", "LOW", "Engineer", "packer count"),
 ("OE-15", "Detailing", "Holes in angles", "Bolt holes are modelled in plates (voids) but not in angles; angle masses are gross nominal (BOQ convention).", "LOW", "BIM", "net angle mass"),
 ("OE-16", "Interfaces", "Purlin cleats", "Existing purlin cleats sit ~14 mm above the new top of steel; purlin package to re-detail.", "LOW", "Purlin package", "cleats"),
 ("OE-17", "Interfaces", "Suspended equipment", "Raft clamps, lighting hangers, HVLS beams and arrays are off the 2.70 m panel points and have no designed attachments; rigging load plan, fan dynamic assessment and catwalk decision outstanding (R2 s.9-11).", "MEDIUM", "Acoustic / AV / mechanical / client", "secondary steel ~1.8 t (R2)"),
 ("OE-18", "Quantities", "BOQ readiness", "Measured quantities are MODEL_DERIVED for concept-size members; bolts, packers and splice plates are ASSUMPTION_DEPENDENT. No waste, spares, rates or amounts applied. Not procurement-ready.", "HIGH", "QS", "all BOQ items"),
 ("OE-19", "BIM", "Mapping / register merge on approval", "New identities are in reports/option_b_roof_trusses/change/identity_register_new_elements.csv; merge into source/source_to_ifc_mapping.csv and update make_reports.py dispositions only after approval and publication.", "LOW", "BIM manager", "registers"),
]
with open(OUT / "outstanding_engineering_register.csv", "w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh); w.writerow(["id", "category", "item", "description", "severity", "owner", "affects"]); w.writerows(ENG)

g = V["gates"]
gate_lines = "\n".join(f"| {k} | {'PASS' if v['pass'] else '**FAIL**'} | {json.dumps(v['info'], default=str)[:160] if v['info'] is not None else ''} |" for k, v in g.items())
tg = V["truss_geometry"]
trow = "\n".join(f"| {k.split('-')[-1]} | {v['x_mean']:.2f} | {v['bays']} | {', '.join(f'{p:.3f}' for p in v['panel_lengths'])} | {v['top_chord_pitch_deg'][0]:.3f} | {v['tos_max_perp_m']*1000:.2f} | {v['bottom_chord_underside_z']:.4f} | {v['span_extent_y'][0]:.4f} - {v['span_extent_y'][1]:.4f} |" for k, v in sorted(tg.items()))
sch = PV.get("schema_validation", {})
br = REC["bridge"]
bridge_rows = "\n".join(f"| {b['Step']} | {b['Mass_kg']:,.1f} | {b.get('Delta_kg', '')} | {b['Status']} |" for b in br)
cc = "\n".join(f"| {r['Item']} | {r['R2_count']} | {r['Model_count']} | {r['R2_mass_kg']} | {r['Model_mass_kg']} | {r['Explanation']} |" for r in REC["connection_typical"])
clash = IF.get("clash_rows_by_group", {})
clash_rows = "\n".join(f"| {k.split('|')[0]} | {k.split('|')[1]} | {k.split('|')[2]} | {v} |" for k, v in sorted(clash.items()))
el_rows = "\n".join(f"| {k.split('|')[0]} | {k.split('|')[1]} | {v} |" for k, v in sorted(IF.get("existing_elements_clashing_new", {}).items()))
iface_rows = "\n".join(f"| {i['id']} | {i['topic']} | {i['item']} | {i['status']} | {i['finding']} | {i['action']} |" for i in IF["interfaces"])
prof_rows = "\n".join(f"| {p} | {v['angles']} | {v['length_m']:,.2f} | {v['mass_kg']:,.1f} | {SS['stock_bars'][p]['bars']} |" for p, v in sorted(SS["by_profile"].items()))
ok_all = V["all_pass"]

md = f"""# Option B roof trusses - candidate IFC revision {man['revision']}

**Southgate Worship Center, main auditorium - native IFC4 / Bonsai.** Concept design - NOT FOR CONSTRUCTION.
Generated by `scripts/option_b/s11_reports.py` from the candidate build `{man['stamp']}`. Do not hand-edit.

> **Status: CANDIDATE FOR REVIEW - not published.** `bim/southgate.ifc` (sha256 `{man['source']['sha256']}`) is unchanged.
> Nothing in this revision is engineering-verified; no engineering certification is claimed. Member sizes are R2 indicative sizes.

## 1. What was implemented

- **Option B** of *Roof Structure Options Appraisal, Revision R2, 7 November 2026*: 12-bay Warren truss with verticals, bolted paired-angle members, on all **11** truss lines (x = 3.25 ... 58.85 m at 5.56 m), span 32.4 m, 15 deg, 13 bottom-chord panel points at 2.70 m.
- The 11 existing assembly identities `SOUTHGATE-TRUSS-T01..T11` (GlobalIds unchanged) now hold the Option B trusses; the **{slim['superseded_count']} superseded 16-panel parts** and 8 orphan types were removed from the candidate (they remain in the authoritative IFC and the backup).
- **{man['created_total']} new IFC elements**: {', '.join(f'{v} {k}' for k, v in sorted(man['created'].items()))}.
- Truss types: TT-G gable (lines 0, 10), TT-R rigging (lines 1, 2), TT-T typical (lines 3-9). Sections per R2 central basis; R2 member forces per analysed line are stored on every member and connection.

| Deliverable | Location |
|---|---|
| 1 Candidate IFC | `{man['candidate']['path']}` (sha256 `{man['candidate']['sha256']}`) |
| 2 Timestamped backup | `{man['backup']['path']}` (sha256 verified = source) |
| 3 Structural member schedule | `schedules/structural_member_schedule.csv`, `member_schedule_by_profile_and_role.csv`, `steel_by_profile_with_stock_bars.csv` |
| 4 Connection component schedule | `schedules/connection_plate_schedule.csv`, `bolt_set_schedule.csv`, `connection_component_summary.csv` |
| 5 Truss assembly quantity schedule | `schedules/truss_assembly_quantity_schedule.csv` (each truss, each type, all 11) |
| 6 Preliminary BOQ extract | `schedules/preliminary_boq_extract.csv` |
| 7 Connection type library | `schedules/connection_type_library.csv`, `component_type_library.csv` |
| 8 Roof interface and clash report | `roof_interface_and_clash_report.md`, `interfaces/clash_register.csv`, `interfaces/interface_register.csv` |
| 9 IFC validation report | `ifc_validation_report.md`, `validation/*.json` |
| 10 Quantity reconciliation report | `quantity_reconciliation_report.md`, `reconciliation/*.csv` |
| 11 Before / after views | `views/V01..V08_*.png` (+ Bonsai renders where present) |
| 12 Implementation and outstanding-engineering register | `implementation_register.md`, `outstanding_engineering_register.csv` |
| 13 Change manifest | `change/change_manifest.json`, `superseded_elements.csv`, `reused_identities.csv`, `identity_register_new_elements.csv` |

## 2. Headline quantities (all 11 trusses, model-derived from the candidate IFC)

| Item | Quantity | Measurement status |
|---|---|---|
| Built-up members / angles | {T['BuiltUpMembers']:.0f} / {T['Angles']:.0f} | MODEL_DERIVED (sizes CONCEPT_UNVERIFIED) |
| Angle cut length | {T['AngleLength_m']:,.1f} m | MODEL_DERIVED |
| Member steel (cut length x catalogue kg/m) | {T['MemberMassNominal_kg']/1000:,.2f} t | MODEL_DERIVED |
| Gusset plates 10 mm | {T['Gussets']:.0f} nr, {T['GussetMass_kg']/1000:.2f} t | MODEL_DERIVED (placeholder outlines) |
| Splice plates 8 mm | {T['SplicePlates']:.0f} nr, {T['SpliceMass_kg']/1000:.2f} t | ASSUMPTION_DEPENDENT |
| Packing plates 10 mm | {T['PackingPlates']:.0f} nr, {T['PackerMass_kg']/1000:.2f} t | ASSUMPTION_DEPENDENT |
| Bolt sets (bolt + nut + washer) | {T['BoltSets']:.0f} nr (M20 {T['BoltSets_M20']:.0f}, M16 {T['BoltSets_M16']:.0f}); {T['BoltSetMass_kg']/1000:.2f} t | ASSUMPTION_DEPENDENT |
| Connection assemblies | {T['ConnectionAssemblies']:.0f} ({SS['connection_types']} connection types) | MODEL_DERIVED |
| Rigging pick-up tab provisions | {T['RiggingTabs']:.0f} | ASSUMPTION_DEPENDENT (no capacity) |
| **Truss set, indicative** | **{REC['set']['model_t']:.2f} t** vs R2 42.1 t ({REC['set']['model_vs_R2_pct']:+.1f} %) | MODEL_DERIVED - see reconciliation |

| Profile | Angles | Cut length (m) | Mass (kg) | 6 m bars (FFD) |
|---|---|---|---|---|
{prof_rows}

## 3. Validation gate summary

All gates {'**PASS**' if ok_all else '**do NOT all pass**'} - details in `ifc_validation_report.md`.
Project validator (`scripts/validate/validate_ifc.py`): schema issues {sch.get('issues', 'n/a')}, uncontained elements {PV.get('spatial', {}).get('uncontained_and_unaggregated', 'n/a')}, duplicate GlobalIds {len(PV.get('guids', {}).get('duplicates', [])) if PV else 'n/a'}.
Stale-quantity check (`extract_quantities.py --check`): {ST.get('stale_values', 'n/a')} stale values over {ST.get('elements', 'n/a')} elements.
Bonsai round trip (full candidate): {('loaded ' + str(BR.get('blender_objects_for_them')) + ' / ' + str(BR.get('with_geometry')) + ' Option B objects, parametric edit ' + str(BR.get('edit', {}).get('operator')) + ', saved ' + str(BR.get('saved'))) if BR else 'see validation/'}.

## 4. Decisions needed before publication

1. Accept the candidate as the model of record for the roof trusses (then publish with `build_ifc.py --publish`-equivalent hash-guarded step and merge the identity register).
2. Accept deviation **DEV-01** (top of steel on the existing purlin seat; ~26 mm lower setting-out than R2's line).
3. Route the documented interface conflicts - **all inherited from the superseded truss, none new** - to their packages: C-01 cap plate / seat fin (support study),
   C-02 eaves outriggers / cleats (eaves detail), C-03 rod-bracing end plates (bracing design), C-05 two raft clamps (acoustic), C-08 gable walls and side-wall heads (envelope).
   {len(IF.get('existing_elements_clashing_old_only', []))} existing elements that clashed with the old truss (mostly purlins, cleats and old bolts) are clear of Option B.
4. Decide the rigging-truss design scenario (OE-06), catwalks, and coating (OE-10).
"""
open(OUT / "README.md", "w", encoding="utf-8").write(md)

val = f"""# IFC validation report - Option B candidate {man['revision']}

File: `{man['candidate']['path']}` - sha256 `{V['sha256']}`. Validator: `scripts/option_b/s05_validate.py` run with `python -I` on the saved file
(no project code imported), regression reference `bim/southgate.ifc`. Run time {V['seconds']} s.

## Gates

| Gate | Result | Evidence |
|---|---|---|
{gate_lines}

## Truss geometry measured from the IFC

| Truss | x (m) | Bays | Panel lengths (m) | TC pitch (deg) | TOS vs 12.380 plane (mm) | BC underside z | y extent |
|---|---|---|---|---|---|---|---|
{trow}

Panel lengths are measured between pair centroids of the verticals (mesh centroids), the pitch from the top-chord angle axes.
Top of steel must be <= -10.13 mm (purlin underside); the y extent must stay inside the column flange faces (0.2771 / 32.7229).

## Project validator (`scripts/validate/validate_ifc.py`)

- schema issues: {sch.get('issues', 'n/a')}; elements {PV.get('spatial', {}).get('elements', 'n/a')}; uncontained/unaggregated {PV.get('spatial', {}).get('uncontained_and_unaggregated', 'n/a')}
- design status: {json.dumps(PV.get('design_status', {}))}; engineering-verified claims {PV.get('engineering_verified_claims', 'n/a')}
- openings {json.dumps(PV.get('openings', {}))}
- geometry extent {json.dumps(PV.get('geometry', {}))}

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
"""
open(OUT / "ifc_validation_report.md", "w", encoding="utf-8").write(val)

rec = f"""# Quantity reconciliation report - Option B candidate

Sources: candidate IFC schedules (`schedules/`), independent closed-form hand calculation (`reconciliation/hand_calculation_member_mass.csv`),
geometry engine output, and R2 (`config/option_b/r2_basis.json`). **No quantity was adjusted to match R2.**

## Bridge from R2 to the model (truss set, 11 trusses)

| Step | Mass (kg) | Delta (kg) | Status |
|---|---|---|---|
{bridge_rows}

- The hand calculation on R2's own geometry reproduces R2's member masses exactly (lines 0, 1, 2, 4: {', '.join(f"{r['H1_R2_geometry_kg']}" for r in REC['hand'])} kg), which independently confirms the section schedule and web layout.
- DEV-01 (top of steel on the purlin seat) shortens webs by ~0.8 m per truss: {sum(r['DEV01_effect_kg'] for r in REC['hand'] if r['R2_line']=='4'):.1f} kg per typical truss.
- Cut lengths (web set-backs from the panel points, heel extensions, 5 mm splice gaps) remove ~127 kg per truss; R2 measured node to node.
- Connection steel: R2 applied a 27.4 % allowance (9.06 t); the modelled plates and bolts total {REC['set']['model_connections_t']:.2f} t.
- IFC schedules and the geometry engine give identical counts on every truss ({REC['engine_vs_ifc_counts_identical']}); member mass from IFC geometry volume differs from the catalogue mass by {REC['geometry_vs_nominal_member_mass_pct']} %.

## Connection components, typical truss (TT-T)

| Item | R2 count | Model count | R2 mass (kg) | Model mass (kg) | Explanation |
|---|---|---|---|---|---|
{cc}

## Reading the difference

The model is **{abs(REC['set']['model_vs_R2_pct']):.1f} % lighter** than R2's 42.1 t: about 1.5 t from member lengths (measured rather than node-to-node, DEV-01)
and about 4.9 t from connections (R2 used the superseded model's average gusset of 15.3 kg and generous packer/bolt allowances).
Both figures rest on unverified sizes and placeholder detailing: gusset sizes in particular will grow once bolt groups and
block-tearing are designed. For budgeting, keep R2's 42.1 t (PRELIMINARY_ESTIMATE) until the connection design exists;
use the model quantities for counts, cut lists and the measurement structure.
"""
open(OUT / "quantity_reconciliation_report.md", "w", encoding="utf-8").write(rec)

cl = f"""# Roof interface and clash report - Option B candidate

Exact BRep intersections (> 0.5 mm) of every Option B component against the {IF['zone_elements']} retained elements that reach a truss zone,
compared with the same test for the superseded 16-panel truss in `bim/southgate.ifc` (`scripts/option_b/s06_interfaces.py`).
**No supporting structure, roof envelope or equipment was moved** - conflicts are documented for the responsible package.

## Clash register summary (component-level rows)

| Group | Category | Status | Rows |
|---|---|---|---|
{clash_rows}

Existing elements involved (INHERITED = the same element also clashed with the superseded truss):

| Group | Status | Existing elements |
|---|---|---|
{el_rows}

Existing elements that clashed only with the superseded truss (resolved by Option B): {len(IF.get('existing_elements_clashing_old_only', []))}.
Full list: `interfaces/clash_register.csv`.

## Interface register

| Id | Topic | Item | Status | Finding | Action (needs separate approval) |
|---|---|---|---|---|---|
{iface_rows}

Views: `views/V07_equipment_suspension_interfaces.png`, `views/V08_truss_to_column_interface.png`.
"""
open(OUT / "roof_interface_and_clash_report.md", "w", encoding="utf-8").write(cl)

eng_rows = "\n".join(f"| {r[0]} | {r[1]} | {r[2]} | {r[4]} | {r[3]} | {r[5]} |" for r in ENG)
imp = f"""# BIM implementation and outstanding-engineering register - Option B candidate {man['revision']}

## Implementation record

| Stage | Result |
|---|---|
| 1 Audit | Authoritative IFC sha `{man['source']['sha256'][:16]}...` = publish record; no Bonsai session open; existing trusses were 16-panel (53 members, 17 gussets, 6 splice plates; bolts only on T06). Purlin seat measured on every line (`work/option_b/s02_roof_seating.json`). R2 basis extracted read-only with source checksums (`config/option_b/r2_basis.json`). |
| 2 Pilot | Isolated single-truss IFC (T05): all gates passed; Bonsai load / parametric edit / save verified. |
| 3 Library | {SS['connection_types']} connection types, {SS['built_up_types']} built-up member types, 3 truss types, member / plate / bolt-set types (`schedules/*type_library.csv`). Rules in `config/option_b/detailing_rules.yaml` propagate to every instance on rebuild. |
| 4 Truss set | 11 trusses; genuine differences: TT-G sections and heel details, TT-R rigging tabs and line-specific R2 forces, TT-T typical. Connection types are keyed by family, truss type, connected sections and bolt counts. |
| 5 Roof integration | Interface and clash register (`roof_interface_and_clash_report.md`). |
| 6 Quantities | Schedules + BOQ extract from the IFC; reconciliation vs hand calculation and R2. |
| 7 Audit | `ifc_validation_report.md` - gates {'all pass' if ok_all else 'NOT all passing'}; regression vs authoritative model. |
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
{eng_rows}
"""
open(OUT / "implementation_register.md", "w", encoding="utf-8").write(imp)
print("reports written to", OUT)
