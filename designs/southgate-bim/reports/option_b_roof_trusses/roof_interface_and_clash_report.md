# Roof interface and clash report - Option B candidate

Exact BRep intersections (> 0.5 mm) of every Option B component against the 2340 retained elements that reach a truss zone,
compared with the same test for the superseded 16-panel truss in `bim/southgate.ifc` (`scripts/option_b/s06_interfaces.py`).
**No supporting structure, roof envelope or equipment was moved** - conflicts are documented for the responsible package.

## Clash register summary (component-level rows)

| Group | Category | Status | Rows |
|---|---|---|---|
| C-01 | SUPPORT (column / cap / seat fin) | INHERITED | 286 |
| C-02 | EAVES (outrigger / eaves cleat) | INHERITED | 264 |
| C-03 | BRACING (rod end plate) | INHERITED | 44 |
| C-05 | ACOUSTIC RAFT SUSPENSION | INHERITED | 2 |
| C-08 | WALLS (gable walls / side-wall heads) | INHERITED | 1158 |

Existing elements involved (INHERITED = the same element also clashed with the superseded truss):

| Group | Status | Existing elements |
|---|---|---|
| C-01 | INHERITED | 44 |
| C-02 | INHERITED | 44 |
| C-03 | INHERITED | 12 |
| C-05 | INHERITED | 2 |
| C-08 | INHERITED | 29 |

Existing elements that clashed only with the superseded truss (resolved by Option B): 1269.
Full list: `interfaces/clash_register.csv`.

## Interface register

| Id | Topic | Item | Status | Finding | Action (needs separate approval) |
|---|---|---|---|---|---|
| I-01 | Purlins | Purlin rows vs Option B top panel points | COMPATIBLE | 26 purlin rows at 1.35 m; 14 rows lie within 10 mm of a panel point (every second row), the others at mid-panel (1.34-1.36 m from a node). The 16-bay layout had rows at arbitrary positions; B reduces top-chord local bending but the R2 analysis already included purlin loads between nodes. | None for geometry; engineer to confirm top-chord bending between nodes (R2 included it) |
| I-02 | Purlins | Purlin seating on the top chord | COMPATIBLE (DEV-01) | Top-of-steel set 0.4 mm under the measured purlin underside (purlin -10.13 mm, TOS -10.50 mm normal to the 12.380 plane). The superseded 2L100 chord was centred on the 12.380 plane and overlapped every purlin by ~59 mm (source modelling inconsistency). | None - roof envelope unchanged; record the setting-out deviation DEV-01 for the engineer |
| I-03 | Purlins | Purlin-to-truss cleats (existing PURLIN-CLEAT) | GAP - DETAIL TO REVISE | Existing cleat soles sit 14.4 mm above the new top of steel (they were modelled on the 12.380 plane, 14 mm above the purlin underside). The cleats are purlin-package items and were not moved. | Purlin package: re-detail cleats to bear on the new top chord (2L90 / 2L80 outstanding legs, 190 / 170 mm wide) |
| I-04 | Purlins | Purlin support continuity | COMPATIBLE | Truss lines, spacing (5.56 m) and top-of-steel plane unchanged, so every purlin keeps its two bearings; no purlin spans changed. | None |
| I-05 | Roof bracing | Existing rod bracing (end bays, 4 rods + 8 end plates + 4 turnbuckles) | CONFLICT (inherited) | 4 rods run heel (s = 0) to ridge (s = 16.2) in bays 0-1 and 9-10; both ends land on Option B panel points (T00 / T06). End plates are modelled in the truss plane and conflict with the 10 mm gusset plane (clash group C-03). | Re-detail as cleats bolted to the heel / apex gussets when the roof bracing and eaves wind girders are designed (R2 s.6.2: girders ~10.6 t) |
| I-06 | Roof bracing | Bottom-chord restraint ties | MISSING (required) | R2 assumes out-of-plane ties at <= 5.4 m (BC panel points s = 5.4, 10.8, 16.2, 21.6, 27.0). No ties exist in the model; under uplift the bottom chord is in compression over 32.4 m without them. | Design and model longitudinal ties / bracing; connection provision noted on the five bottom panel points (SOUTHGATE_ConnectionInstance.Interfaces) |
| I-07 | Roof bracing | Eaves wind girders / lateral stability | MISSING (required) | R2 requires a designed lateral system (eaves wind girders ~10.6 t with wall bracing, or fixed-base columns). Not in the model. | Separate design; heel gussets (CT-TH) will need girder connection provisions |
| I-08 | Acoustic rafts | Raft clamps on bottom chords (108 clamps, lines 2-7) | ATTACHMENT TO REVISE | Clamp positions are 0.08-1.31 m from the nearest Option B panel point (median 0.78 m). Clamp tops sit 5.9-5.9 mm below the new bottom-chord underside (the old 2L90 chord underside was 22 mm lower, clamps overlapped it). New chord 2L80 back-to-back = 170 mm wide (old 190 mm). | Acoustic package: re-space raft rails to 2.70 m panel points (R2 Table 9.1) or confirm chord bending; re-size clamp jaws to 170 mm and re-seat (+5.5 mm) |
| I-09 | Lighting | Stage / FOH lighting-bar hangers (6 on truss lines 1 and 2) | ATTACHMENT TO REVISE | Hanger positions (s, distance to nearest node): [(np.float64(7.45), np.float64(0.65)), (np.float64(16.2), np.float64(0.0)), (np.float64(24.95), np.float64(0.65)), (np.float64(6.95), np.float64(1.15)), (np.float64(16.2), np.float64(0.0)), (np.float64(25.45), np.float64(1.15))]. Hanger tops end 57-57 mm below the bottom chord (they never reached the old chord either). Rigging pick-up tab provisions are modelled at every interior bottom panel point of lines 1-2 (capacity NOT_AVAILABLE). | Lighting/rigging design: move pick-ups to panel points (R2: bars land within 0.8 m) and specify rated hardware to the tabs; rigging load plan |
| I-10 | Ceiling fans | HVLS fan support beams (8, spanning between trusses 3-7) | ATTACHMENT TO REVISE | Beams bear 0.15-0.15 m from the nearest panel point (s = 10.65 / 21.75 vs nodes 10.8 / 21.6); beam tops 17 mm below the bottom chord with no connection modelled. R2 included the fan loads off-node (non-coordinated run) and a dynamic assessment is still required. | Mechanical/structural: move beams 150 mm to the panel points or confirm chord bending; design the beam-to-chord hangers; fan dynamic assessment (R2 s.9.2) |
| I-11 | Loudspeakers | Main L/R arrays (2) | NOT MODELLED - DESIGN REQUIRED | Arrays (s, distance to node, x): [(np.float64(25.1), np.float64(0.8), np.float64(11.5)), (np.float64(7.3), np.float64(0.8), np.float64(11.5))]. They hang midway between truss lines 1 and 2 (x 11.5); no rigging steel modelled. R2 assumed a spreader sharing the load to lines 1 and 2, landing within 0.8 m of a node. | AV/rigging design: spreader beam between lines 1-2 picking up on bottom panel points (tabs provided at s = 5.4 / 8.1 / 24.3 / 27.0); designed rigging hardware |
| I-12 | Ridge fans | Ridge extract fans (VENT-04, 40 parts) and kerbs | COMPATIBLE | Fans sit between truss lines at the ridge on purlin trimmers (rows 11/13); no truss member is in their footprint (no clash recorded). | None for the trusses; trimmers remain a purlin-package item |
| I-13 | Catwalks | Maintenance catwalk allowance | OPEN DECISION | R2: B gives about 2.46 m clear height for a 0.8 m walkway at the centre (E2/E3 3.25 m). No catwalk is modelled; the decision is needed before the geometry is fixed (R2 s.10). | Client/AV/lighting decision on catwalks; if adopted, add catwalk hangers to bottom panel points and re-check web set-outs |
| I-14 | Columns | Truss-to-column interface (22 UC 254x254x73 columns) | CONFLICT - SUPPORT STUDY | Column lines and heights unchanged. Column top +12.283, cap plate +12.293..+12.313 (y -0.03..0.33), seat fin 16 mm in the truss plane. Option B heel: top chord toe at about +12.27 at the bearing (TOS fixed by the purlins), end post and heel gusset at y >= 0.281. The cap plate and seat fin intersect the heel (clash group C-01); the superseded truss had the same seat-fin conflict. | Separate support/foundation study: lower the column top / cap by >= 45 mm or bear the heel on a designed shoe; replace the seat fin with a bearing designed with the heel gusset; holding-down for ~80 kN uplift (R2) |
| I-15 | Walls | Gable walls and side-wall heads (clash group C-08) | CONFLICT (inherited) | 29 wall elements intersect the truss zone (gable trusses inside the gable walls; side-wall infill heads at the heels); every one also intersected the superseded truss. | Envelope package: set wall heads / gable infill around the trusses (pockets or wall head below the bottom chord); architecture unchanged here |

Views: `views/V07_equipment_suspension_interfaces.png`, `views/V08_truss_to_column_interface.png`.
