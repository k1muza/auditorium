# Handoff — Proposed 3,000-Seat Church Auditorium · Design Proposal Template

Implementation notes for populating the proposal from the Blender concept model. The design (layout, type, colour) and the content (values, text, drawings, images) are kept separate. Codex should change content files only, never the inline styles.

## 1. File map

| Path | Role | Edit? |
|---|---|---|
| `Church Auditorium Proposal.dc.html` | The document: 26 fixed pages, inline-styled, data-bound | Layout only |
| `data/project.json` | **All** values, copy, tables, registers (the data contract) | Yes, regenerate |
| `drawings/*.svg` | True-scale drawings in millimetres, generated from the model | Regenerate |
| `model/model.json`, `model/properties.json` | Raw model extract (geometry plus custom properties) | Regenerate |
| `tools/extract_model.py` | Blender → `model/*.json` | — |
| `tools/generate-drawings.js` | `model/*.json` → `drawings/*.svg` | — |
| `design/tokens.json` | Design tokens (reference; styles are inline in the template) | Reference |
| `fonts/*.woff2` | Self-hosted Archivo, Newsreader, IBM Plex Mono (SIL OFL) | — |
| `image-slot.js` | Drop-target placeholders for renders | — |

## 2. Pipeline

```
Blender (.blend, PL06)
  └─ tools/extract_model.py ........ model/model.json + model/properties.json
       ├─ tools/generate-drawings.js  drawings/*.svg  (A-100, A-110, A-200…203, A-301, A-302, S-100, S-200, S-300, S-301, X-000, DS-001)
       └─ build-data (to write) ..... data/project.json  (derivations listed in §4)
Template (.dc.html) + project.json + drawings + renders
  └─ Chrome headless --print-to-pdf  (honours @page A4 / named page "a3")
```

1. `blender <file>.blend --background --python tools/extract_model.py -- --out model/`
2. `node -e "const {generate}=require('./tools/generate-drawings.js'); …"` passes `model.json` and `properties.json` to `generate(model, props, {r:'',m:''}, {})` and writes each entry of `.files` to `drawings/`. The function is pure and has no DOM dependency.
3. Write `data/project.json` (schema below). The current file was built this way from PL06 and is the reference output.
4. Export renders (§6) and print to PDF (§7).

## 3. Data contract — `data/project.json`

Every measured value carries `src`, which the template shows as a mark: `M` measured geometry · `P` authored model property · `E` derived estimate · `C` requires confirmation · `X` excluded. Unfilled fields are written as bracketed tokens such as `[REV]`, and the template prints them literally. **Do not invent values for unfilled fields. Leave the token.**

| Key | Shape | Feeds pages | Source |
|---|---|---|---|
| `doc.{title, subtitle, location, status}` | string | Cover, all footers | Fixed text from brief |
| `doc.{docNo, rev, date, preparedBy, checkedBy, client, site}` | string token | Cover, 02, title blocks, footers | **Project records — currently unfilled** |
| `doc.{model, modelFile, modelScene, modelFlag}` | string | 02, title blocks | `bpy.data.filepath`, scene name, collection flag |
| `metrics[]` `{label, value, unit, src, note}` | 8 items | 03 | §4 derivations |
| `copy.overview[3]`, `copy.vision[3]`, `copy.structure[3]`, `copy.interior[1]` | paragraphs | 03, 04, 08, 10 | Engineering commentary (human-reviewed) |
| `copy.principles[]` `{n, t, b}` | 4 items | 04 | Commentary |
| `glance.{arch, struct, func, model}[]` `{label, value, unit, src, status}` | ≤ 7 each | 05 | §4 |
| `glance.verif[]` `{label, value, status}` | 6 | 05 | Verification records |
| `rooms[]` `{code, name, area, level}` | 28 | 06 | `SPC-*` props `LongName`, `GrossFloorArea` |
| `exits[]` `{id, obj, role, clear, leaves}` | 17 | 06 | `DR-EXT-*` props; `id` = X01… in name order (must match the plan SVG labels) |
| `seating.blocks[]` `{id, seats, rows, nrows}` | 6 | 07 | Count `SEAT-C-Rnn-Bn-Snn` |
| `seating.{totalCongregation, other[], dims[], sight[]}` | — | 07 | Counts plus scene props (`max_seats_to_aisle`, `c_min_n1`, `offaxis_pulpit` …) |
| `schedules.{columns, beams, trusses, purlins, bracing, footings}[]` `{id, grid, type, section, size, grade, qty, status, remarks}` | grouped rows | 12 | §4; `section`/`grade` stay `TBD`/`TBC` until the engineer designs them |
| `columnsFull[]` `{id, grid, role, section, base, top, length, status}` | 76 | 20–21 | `STR-COL-*` bbox and props |
| `quantities[]` `{group, items[{ref, item, qty, unit, basis, note}]}` | 4 groups | 15 | §4. **No rates, amounts or totals.** The template prints `[QS]` |
| `excluded[]` | strings | 15 | Scope decision |
| `services[]` `{n, t, has, verify}` | 8 | 14 | `has` = represented in model, `verify` = unverified requirement |
| `risks[]` `{ref, disc, finding, sev, response, party, status}` | n | 16 | Review register. `sev` ∈ Critical / Major / Minor |
| `phases[]` `{n, name, status, label, note}` | 6 | 17 | `status` ∈ `complete` / `current` / `outstanding`, from project records only |
| `recommendations[]` | strings | 17 | Commentary |
| `drawings[]` `{no, title, scale, size, rev, status, file}` | n | 18 | Drawing register |
| `assumptions[]`, `calcs[]`, `checks[]`, `modelRefs[]`, `revisions[]`, `contents[]` | — | 22–24, 02 | Registers |
| `images.*` `{id, label, file}` | 6 | 01, 04, 08 | Render export paths (§6) |

## 4. Derivations used for PL06 (repeat them for later model revisions)

- **Grid** — `scene.x_lines` / `y_lines`: A–H = 0, 4.5, 14.5, 24.5, 34.5, 44.5, 54.5, 59.0; 1–12 = 0, 8, 16, 24, 32, 38.5, 48, 56, 64, 72, 80, 88.
- **Footprint** — bbox of `ENV-WALL-EXT-*` (−0.15…59.15 × −0.15…88.15) = 59.30 × 88.30 m.
- **Space allowances** — Σ `GrossFloorArea` over `SPC-*` = 5,500.65 m² (L00 + L02).
- **Truss span** — `scene.truss_span`, checked against grid B–G. **Roof pitch** — top-chord rise 0.4 m per 5.0 m panel.
- **Roof area** — Σ ENV-ROOF plan areas, hall planes divided by cos(atan 0.08).
- **Member lengths** — ‖b − a‖ of the endpoints exported by `extract_model.py`.
- **Seat counts** — object counts by prefix. Congregation = `SEAT-C` where `CountsTowardTarget` is true.
- **Egress and sightline figures** — scene properties, reported as "placeholder method". They are not verification.

## 5. Pagination

Pages are fixed-size `<section data-page>` boxes (A4 210 × 297 mm, or A3 420 × 297 mm with `page: a3`). Content does not reflow between pages. This is intentional: drawing sheets and editorial spreads need exact placement.

**Long tables** use explicit continuation pages, generated from data:
1. Choose rows per page from the table's row height. Column schedule: 0.95 mm padding + 6.2 pt text ≈ 5.0 mm/row, about 40 rows on the first page (under a heading) and about 48 on continuation pages.
2. Chunk the array (`columnsFull.slice(0,40)`, `.slice(40,88)` …) and emit one Appendix C section per chunk. Repeat the table number, the title with "(continued)", the column header and the row range "Rows 41–76 of 76".
3. Break between rows only. Never split a row.

The template does this with `colsA` / `colsB`. To generalise, duplicate the Appendix C continuation `<section>` per chunk, or render the sections from an array. If fully automatic flow is ever needed, Paged.js is the practical route, but the drawing sheets should stay fixed pages.

**Figures** have fixed boxes. Renders fill their box with `object-fit: cover`, so new images need no resizing. Drawings are sized in mm to their stated scale. If a regenerated SVG changes size, read the new size from `drawings/sizes.json` and update the `width/height` on that `<img>`, or let it scale and change the stated scale to "NTS".

## 6. Renders (Blender cameras → image slots)

| Slot id | View | Box (mm) | Export at 300 dpi |
|---|---|---|---|
| `img-cover` | Exterior aerial perspective | 210 × 158 | 2480 × 1866 |
| `img-aerial` | Exterior aerial perspective | 210 × 297 | 2480 × 3508 |
| `img-cutaway` | Cutaway aerial | ≈ 128 × 62 | 1512 × 732 |
| `img-from-rear` | Interior from rear | 170 × 84 | 2008 × 992 |
| `img-from-platform` | Interior from platform | 170 × 70 | 2008 × 827 |

Structure-only and top-down renders are not placed. The structural axonometric (S-100) and plan (A-100) are generated as true engineering geometry instead, as the brief requires. To make renders permanent, replace each `<image-slot>` with `<img src="renders/…" style="width:100%;height:100%;object-fit:cover">`. The cover switches between the generated line drawing and the render with the `coverImage` prop.

## 7. Print / PDF

- `@page { size: A4 portrait; margin: 0 }` and `@page a3 { size: A3 landscape; margin: 0 }` are in the template head. A3 sections set `page: a3`. Chrome and Edge honour named pages, and the PDF contains mixed sheet sizes.
- Print at 100% with background graphics on (`print-color-adjust: exact` is set). Stated drawing scales hold only at 100%.
- Bound A4 copies: print the A3 sheets as fold-outs, or as A4 at 50% (scale becomes 1:600 / 1:800 / 1:1000, so use the scale bars).
- Images are `loading="lazy"`. A `beforeprint` handler switches them to eager. For headless printing, wait for the network to go idle first.

## 8. Known constraints

- SVG text inside `<img>` uses the system monospace, because SVG-as-image cannot load web fonts. For print-grade drawing type, inline the SVG into the page, or convert text to outlines when generating the PDF.
- Drawings are **bounding-box and centreline schematics** of model objects. Openings, wall build-ups and member profiles are not represented.
- Orientation is in model axes. True north is not defined in the model (risk DR-12).
- Level L03 (+4.300) sits below L02 (+4.600) in the model and is reported as found.
- The model's own flag reads "CONCEPT – UNVERIFIED – NOT FOR CONSTRUCTION". Every sheet carries this status, and it must stay until a registered engineer signs off.
