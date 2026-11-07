# Southgate Worship Center - native IFC BIM project

The main auditorium of **Southgate Worship Center** (design F, Site Option A, 2,000 seats), migrated from the Blender
concept model into a native **IFC4** model authored with **Bonsai 0.9.0-post1 / IfcOpenShell 0.9.0.post1**.

> Concept design - **NOT FOR CONSTRUCTION.** No element is engineering-verified or approved for documentation.
> Structural, foundation and services content is migrated as `CONCEPT_UNVERIFIED` or `PRELIMINARY_DESIGN`.

| Deliverable | Path |
|---|---|
| Authoritative BIM model | `bim/southgate.ifc` (IFC4, metres; publish record and sha256 in `bim/publish_record.json`) |
| Visualisation file (cameras, lights, render settings; no geometry) | `bim/visualisation.blend` |
| Verified source snapshot and manifest | `source/snapshot/*.blend` (read-only), `source/source_manifest.json` |
| Source inventory / source-to-IFC mapping | `source/geometry_inventory.json`, `source/source_to_ifc_mapping.csv` |
| Migration register (one row per source object) | `reports/migration/migration_register.csv` |
| Phase audits | `reports/migration/phase_audits.md` |
| Migration completeness / BIM quality audits | `reports/audits/migration_completeness.md`, `reports/audits/bim_quality_audit.md` |
| Independent final review | `reports/audits/independent_final_review.md` |
| Outstanding work register | `reports/audits/outstanding_work.csv` |
| IFC validation (clean interpreter) | `reports/audits/ifc_validation.json` |
| Quantity schedules and prototype test | `reports/quantities/` (`quantity_schedule_*.csv`, `pilot_*`) and `docs/quantity_method.md` |
| Visual comparison | `renders/comparisons/gallery.html`, `renders/comparisons/contact_sheet.png` |

## Scope

The project covers the main auditorium hall plus the components physically integrated with it:

- the east and west glazed gable portals;
- the north entrance canopy and portal;
- the attached west office wing, with its roof terrace, deck structure and spiral stair;
- structure, roof, restrooms, acoustics and services inside or on the building.

The **children's church and other detached buildings, site works, parking and external paving are excluded**. They appear in the register as `EXCLUDED_INTENTIONALLY` and are not counted as omissions. The boundary is defined in `config/project.yaml`.

## How the migration works

1. **Source of truth.** `../F-site-A-2000-astra-v2/model/active_model.json` names `church_auditorium_2000.blend`. The manifest SHA-256 and the deep geometry fingerprint check both passed. No interactive Blender session or MCP socket was running, so no unsaved state existed. The newer-dated files have identical geometry fingerprints. The file was copied byte-for-byte to a read-only snapshot.
2. **Inventory.** Every object was inventoried with its collection, visibility, bounds, topology and custom properties. Hidden groups were traced to their retirement evidence; nothing was migrated just because it exists.
3. **Planning (dry run).** `config/classification_rules.yaml` assigns IFC class, method, phase, system and assembly. The geometry recogniser (`src/southgate_bim/geometry/fit.py`) proves whether each mesh is a box, a prism or a multi-part prism, including oblique and mitred end cuts. Only proven shapes get native parametric or swept bodies.
   - Coplanar wall pieces that tile exactly around doors and windows are consolidated into single walls with real `IfcOpeningElement`s.
   - Frame, leaf and glass parts become parametric door and window types.
4. **Build.** IFC entities are authored through the IfcOpenShell API (Bonsai's authoring core) using Bonsai's own conventions (`docs/bonsai_ifc_workflow.md`). The build runs in eight phases (B spatial … I foundations). Each phase is saved, reopened and audited before the next one starts.
5. **Quantities.** `ifc5d` computes `Qto_*BaseQuantities` from the IFC itself. `SOUTHGATE_Quantities` adds geometry measures, counts and indicative masses.
6. **Publish, validate, compare.** Publishing is hash-guarded. Validation runs in a clean interpreter. Matching-camera renders of the source and of the IFC (loaded through Bonsai) are compared with silhouette overlays.

**Representation honesty.**

- `SOUTHGATE_Provenance.NativeRepresentation` and `.Representation` say exactly how each element was built.
- Tessellated copies of free-form meshes (seats, sanitaryware, luminaires, flashings, bent pipes, signage letters) are classified correctly but are never presented as parametric.
- Every migrated element also carries `SOUTHGATE_DesignStatus` and `SOUTHGATE_SourceSpecification` (the source steel section, material specification and similar).

## Environment setup

```bash
# Python (3.10) - standalone IfcOpenShell identical to Bonsai's
py -3.10 -m venv .venv
.venv/Scripts/python -m pip install ifcopenshell==0.9.0.post1 pyyaml numpy pytest pillow
.venv/Scripts/python -m pip install --no-deps ifc5d==0.9.0
# Bonsai into an ISOLATED Blender profile (does not touch the everyday profile)
set BLENDER_USER_RESOURCES=%LOCALAPPDATA%\SouthgateBIM\blender_user
"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" --command extension install-file -r user_default --enable bonsai-0.9.0-post1-windows-x64.zip
blender -b --python-exit-code 1 --python scripts/validate/bonsai_smoke_test.py -- --out work/bonsai_smoke
```

Download the Bonsai archive from extensions.blender.org (extension id `bonsai`, 0.9.0-post1, windows-x64) and check its sha256 before installing. To work interactively, start Blender with the same `BLENDER_USER_RESOURCES` and open `bim/southgate.ifc` via *File > Open IFC Project*.

## Running

```bash
bash scripts/run_pipeline.sh                    # plan -> build -> quantify -> publish -> validate -> renders -> gallery
.venv/Scripts/python scripts/export/make_reports.py --build work/builds/<run>_full --validation reports/audits/ifc_validation.json
.venv/Scripts/python scripts/validate/pilot_quantity_test.py      # section-10 quantity prototype incl. Bonsai edit
.venv/Scripts/python scripts/export/extract_quantities.py --in bim/southgate.ifc --check   # stale-quantity check
.venv/Scripts/python -m pytest -q
```

Individual steps, their safety rules and the "after Bonsai edits, never rebuild from source" rule are in `AGENTS.md`.

## Safety

- The source project is never written. Blender opens it headless and nothing is saved.
- The snapshot is read-only.
- Every build goes into a new folder.
- GlobalIds are deterministic (uuid5 of the stable IDs), so reruns are identical and cannot duplicate elements.
- Publishing requires the SHA-256 of the file being replaced and archives the previous file.
- A failing phase stops the build and leaves the published model unchanged.

## Known limitations

- Steel sections are exact source cross-sections (arbitrary or composite profiles named by their designation), not catalogue-parameterised profile definitions.
- Materials keep the source render-material names, and most specifications are `UNSPECIFIED`/`CONCEPT`. Wall and slab types have a single layer.
- 187 double-angle truss members have slightly tapered source meshes (skew up to 4.5 mm). The IFC uses the constant section, and volumes differ by up to about 4 %.
- Doors and windows are parametric bodies. Source doors modelled open are represented closed, and glazed leaves are styled by their glass material.
- Doors in curtain walls and WC cubicles are parts of their assemblies, with no wall opening. Two foyer doors stand in the open loggia portal without a host wall.
- West office rooms have no `IfcSpace` volumes, and true north and geolocation are unverified.
- Base quantities are not defined in IFC4 for furniture and fasteners. Those elements carry geometry measures and counts in `SOUTHGATE_Quantities`.
- Bonsai parametric edits do not refresh stored quantities. Re-run `extract_quantities.py` after editing.
