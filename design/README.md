# Handoff: Proposed 3,000-Seat Church Auditorium — Design Proposal Document

## Overview
A 26-page preliminary architectural and structural engineering proposal (A4 portrait report plus A3 landscape drawing sheets). Every value, table and drawing is populated from the Blender concept model `church_3000_concept_PL06-21c8b6d8b4`. The audience is a church building committee, prospective contributors and consulting engineers.

## About the design files
`Church Auditorium Proposal.dc.html` is a **working, print-capable HTML template**, not a mock-up. It can be used as is: it loads `data/project.json` and the SVGs in `drawings/` and prints straight to PDF. If your toolchain is different (Paged.js, Typst, LaTeX, a React PDF renderer), treat the HTML as the visual reference and rebuild it, keeping the measurements, type and colours in `design/tokens.json`.

The file is a "Design Component": plain HTML with `{{ path }}` holes and a small logic class at the bottom. Holes resolve against `data/project.json`. `support.js` is the runtime that makes it work in a browser; keep it next to the HTML.

## Fidelity
**High fidelity.** Final type, colour, grid, table and drawing styling. The only open items are content placeholders: bracketed fields such as `[REV]`, and five empty render slots.

## Quick start (Claude Code)
```bash
npm install            # installs puppeteer (headless Chrome)
npm run serve          # http://localhost:8080/Church%20Auditorium%20Proposal.dc.html — needs http, not file://
npm run pdf            # proposal-a3.pdf : A4 pages + true A3 landscape sheets, zero margins
npm run pdf:a4         # proposal-a4.pdf : all A4; A3 sheets rotated 90° and fitted (scales halve)
```
`print-pdf.mjs` prints with `preferCSSPageSize` and zero margins, so the pages carry no white border. To print from a desktop browser instead, set **Margins: None**, **Scale: 100 %** and **Background graphics: on**.

Print modes are chosen with the URL query `?sheets=a3` (mixed sizes) or no query (A4 everywhere with rotated sheets). See the `@media print` block in the template `<helmet>`.

## Pages
| # | Page | Size | Main data keys |
|---|---|---|---|
| 01 | Cover | A4 | `doc.*`; prop `coverImage` switches line drawing ↔ render slot `img-cover` |
| 02 | Contents and document control | A4 | `contents`, `doc.*` |
| 03 | Project overview | A4 | `copy.overview`, `metrics` |
| 04 | Architectural vision (spread) | A3 L | `copy.vision`, `copy.principles`; slots `img-aerial`, `img-cutaway` |
| 05 | Project at a glance | A4 | `glance.*` |
| 06 | Floor plan A-100 | A3 sheet | `rooms`, `exits`; `drawings/A-100_plan_L00.svg` |
| 07 | Seating layout | A4 | `seating.*`; `A-110_seating.svg` |
| 08 | Interior architecture | A4 | slots `img-from-rear`, `img-from-platform`; `A-301_section_AA.svg` |
| 09 | Chapter opener | A4 | static |
| 10 | Structural concept (spread) | A3 L | `copy.structure`; `S-100_structural_axo.svg` |
| 11 | Roof structure S-200 | A3 sheet | `S-200_roof_framing.svg`, `S-300_section_T6.svg` |
| 12 | Member schedules | A3 L | `schedules.*` |
| 13 | Elevations and sections | A3 sheet | `A-200…A-203`, `A-301`, `A-302` |
| 14 | Functional and services review | A4 | `services` |
| 15 | Quantities and cost framework | A4 | `quantities`, `excluded`; rates print `[QS]` |
| 16 | Design review and risks | A4 | `risks` |
| 17 | Recommendations and next steps | A4 | `phases`, `recommendations` |
| 18–24 | Appendices A–F | A4 / A3 | `drawings`, `columnsFull`, `assumptions`, `calcs`, `checks`, `modelRefs`, `revisions` |
| 25–26 | Design system | A4 / A3 | static specimen and `DS-001_drawing_language.svg` |

## Design tokens
Full set in `design/tokens.json`. The key values:
- **Colour:** ink `#1E1E1C` · paper `#F5F2EC` · drawing `#FFFFFF` · slate `#5B636B` · rule `#D5D2CA` · zebra `#EEEBE4` · bronze `#8C5E36` · oxide (critical/unverified) `#8A3324` · cover `#1F2022`
- **Type:** Newsreader 300–400 for display (cover 31 pt, H1 27 pt / 1.04, lead 13 pt / 1.42) · Archivo 400–500 for body (8.6 pt / 1.55) and tables (6.2–7.2 pt) · IBM Plex Mono 400/500 for labels (6.2 pt caps, +0.07 em) and data (5.2–9 pt). Fonts are self-hosted in `fonts/` (SIL OFL).
- **A4 grid:** binding 25 mm, outer 15 mm, top 24 mm, bottom 22 mm. Left rail 38 mm + 4 mm gutter + 128 mm text. Running header and folio each 9 mm from the page edge.
- **A3 sheet:** 8 mm border (0.75 pt), 62 mm title block on the right, drawing area ≈ 338 × 277 mm.
- **Rules:** 0.75 pt ink for table and section heads; 0.35 / 0.3 pt rule for rows.
- **Drawing line weights (mm):** cut 0.50 · heavy 0.35 · medium 0.25 · thin 0.18 · hair 0.13. Dashed = assumption, dotted = unresolved.

## Assets
- `drawings/*.svg` — generated from model geometry by `tools/generate-drawings.js`. True scale in mm.
- Renders — **not supplied yet**. Export them from Blender at the sizes in `HANDOFF.md` §6 and swap each `<image-slot id="…">` for `<img src="renders/…" style="width:100%;height:100%;object-fit:cover">`.
- Fonts — `fonts/`, self-hosted.

## Files
- `Church Auditorium Proposal.dc.html` — the document · `support.js`, `image-slot.js` — runtime
- `data/project.json` — data contract (every value tagged M / P / E / C / X)
- `model/model.json`, `model/properties.json` — raw model extract
- `tools/extract_model.py` (Blender → model JSON) · `tools/generate-drawings.js` (model JSON → SVG) · `tools/print-pdf.mjs` (→ PDF)
- `design/tokens.json` · `HANDOFF.md` — full field contract, derivations, pagination rules and known constraints

## Rules for whoever populates it
1. Change `data/project.json`, the drawings and the renders. Do not change inline styles.
2. Never invent engineering values. Leave a bracketed token until project records supply the value.
3. Every sheet must keep the status "CONCEPT — UNVERIFIED · NOT FOR CONSTRUCTION" until a registered engineer signs off.
