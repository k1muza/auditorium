# Repository migration and change report (2026-11-02)

## 1. Baseline protection (before any move)
- `git init` with `* -text` (byte-exact storage); tag **`baseline-pre-restructure`** (commit `5e4d604`) = the project exactly as found.
- `BASELINE_SHA256.txt` lists 729 files; `tools/verify_baseline.py` re-checks them at their new paths (`path_map.json`);
  two root files are intentionally edited (`.gitignore`, `README.md`) and recorded. Last run: **729/729**.
- Finding: the live model was **PL08**, not PL02. Client decision: Option A = PL08. PL02's generator sources had been
  overwritten; all ten were recovered by exact SHA-256 from local Claude Code file history.

## 2. Moves (Option A unchanged byte-for-byte)
| From | To |
|---|---|
| `config/ scripts/ tests/ model/ reports/ exports/ renders/ logs/ archive/ output/ reviews/ FINAL_REPORT.md RUN_PROMPT.md` | `designs/A-end-stage/` |
| `design/` (template, tokens, fonts, tools) | `documentation/proposal/template/` |
| `design/data, design/model, design/drawings` (populated from unarchived `PL06-21c8b6d8b4`) | `designs/A-end-stage/proposal/legacy-PL06-21c8b6d8b4/` |
| `BASELINE_SHA256.txt` | `documentation/migration/` |

A's scripts resolve every path from their own folder, so A builds only inside `designs/A-end-stage/` and keeps revision
ID `PL08-590d273e35`. One render (`renders/CA3000_orbit_360_PL02-18dac43917.mp4`) was locked by VLC: copied (hash
verified) and the original left untracked at the old path - delete it once VLC is closed.

## 3. Reproducibility proofs (`tools/reproduce_revision.py`, temp folder, nothing in designs/ written)
| Revision | Sources | Rebuilt manifest = archived | Seats | Unit tests |
|---|---|---|---|---|
| PL08-590d273e35 | `archive/pl-08/source` | yes (`155c6b8d...`) | 3000 | OK |
| PL02-18dac43917 | `archive/pl-02/source` (recovered) | yes (`32e375f0...`) | 3000 | OK |

## 4. New structure
- `shared/` - geometry primitives (extracted from A), Blender builder, re-open verifier, IFC export/validation, drawing
  sheets, presentation renders, generic pipeline (archives exact sources with every revision).
- `designs/B-long-side-stage/` - Option B: `config/params.json`, `src/layout.py` (+ reports, drawings), `tests/`,
  model/reports/exports/renders/logs/archive/proposal, `REVISIONS.md` (B01, B02, B03).
- `comparisons/` - `compare.py` (identical measurement code for both), `score_reviews.py`, `reviews/iter-0N/`,
  `RECOMMENDATION.md`, `out/` (tables, figures, comparative report).
- `agents/` - multidisciplinary rubric and reviewer brief (both options reviewed on the same rubric).
- `documentation/proposal/build_proposal.py` - one design system, three documents, contamination guard.
- `tools/` - `verify_baseline.py`, `reproduce_revision.py`, `build.py`.

## 5. Commits
See `git log`: baseline -> restructure -> shared modules -> B01 -> comparison/rubric -> B02 -> B03 -> documents.
