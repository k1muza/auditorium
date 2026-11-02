# Option B (long-side stage) - revision history

Revision ID = `B<nn>-<first 10 hex of SHA-256 over the declared sources>` (design.json `sources`, incl. the shared modules).
Every revision's outputs AND exact sources are archived in `archive/b-<nn>/` (rebuildable with tools/build.py).

| Revision | Date | Kind | Change |
|---|---|---|---|
| B01-5f175dba4d | 2026-11-02 | first complete model | Wide shallow fan, 31 rows, thrust platform on the long wall, mono-pitch roof on 11 continuous trusses, ambulatories, two 6 m foyer stairs. Pre-release design iterations (seating study, clash and egress fixes) are recorded in the commit history and config `_notes`. |
| B02-3c1014f7b9 | 2026-11-02 | review iteration 2 | Response to iter-01 review (B 5.30/10, 1 critical blocker): BOH exit passages to north-wall final exits (blocker) + discharge-route check; stair flights <= 12 risers with landings, centre rails; 5 m ambulatories; fan +-80 deg; 4.5 m ministry floor, thrust R 4.5 m; choir on risers (377); centre-block front wheelchair places, cross-end ramps, grade-only wheelchair exits; trusses simply supported + foyer rafters, eaves wind girders, Pratt webs, larger gutter; 5 deg rear facets. |
| B03-44bc3ae457 | 2026-11-02 | review iteration 3 (final) | Response to iter-02 review (B 6.08/10, 0 critical) and client comment "roof too low": truss bearing derived from the rake (>= 5.5 m clear over the rear passage, roof top +17.8 m), 3.5 m deep trusses, purlins on every node/half-panel, foyer bracing, gutter weirs; BOH exit passages enclosed from the stage wall; full-width cross-end ramps; 3.6 m side-foyer stairs (toilet blocks reshaped 17 x 5.5 m); upper-level refuges; acoustic panels on the concave wall; choir facing the congregation on tiers rising to the stage wall (412, client to confirm); platform 30 x 6.5 m + 5 m thrust (234 m2); 2.5 m ministry floor as a named space; booth +0.9 m; 16 x 7 m main screen. |
