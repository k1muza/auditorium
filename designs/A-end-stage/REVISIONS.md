# Option A (end stage) - revision history

Every revision ID is `<tag><nn>-<first 10 hex of SHA-256 over the source files>`. Archived outputs are in `archive/<rev>/`.
Decisions are recorded in `../../DESIGN_BRIEF.md` (Client design decisions).

| Revision | Date | Kind | Change | Sources archived |
|---|---|---|---|---|
| IT01-45b0e08c36 | 2026-11-01 | review loop 1 | first build | outputs only |
| IT02-325e67e273 | 2026-11-01 | review loop 2 | repairs | outputs only |
| IT03-1e06f520e1 | 2026-11-01 | review loop 3 | repairs; 8.79/10 NOT_ACCEPTED (see FINAL_REPORT.md) | outputs only |
| PL01-7cafe48b2e | 2026-11-01 | post-loop | side choir facing inward | outputs only |
| PL02-18dac43917 | 2026-11-01 | post-loop | review response: trimmed off-axis seats, simpler foyer (two central stairs) | **yes - `archive/pl-02/source/`, reproduced** |
| PL03-3e57114669 | 2026-11-01 | post-loop | choir risers removed | outputs only |
| PL04-7e854e086c | 2026-11-01 | post-loop | 144 choir chairs in the wings | outputs only |
| PL05-cba999fc37 | 2026-11-01 | post-loop | platform 20 x 10 m | outputs only |
| PL06-966bde8984 | 2026-11-02 | post-loop | choir in four zones | outputs only |
| PL07-ea0efb2777 | 2026-11-02 | post-loop | platform to rear wall, +1.00 m | outputs only |
| **PL08-590d273e35** | 2026-11-02 | post-loop | stair/ramp moves, straight choir rows (386 chairs) - **Option A baseline** | **yes - `archive/pl-08/source/`, reproduced** |

`proposal/legacy-PL06-21c8b6d8b4/` holds the proposal data and drawings that were built (outside this pipeline) from a
model labelled `PL06-21c8b6d8b4`. That revision ID matches no archived build; treat it as superseded and unverified.
