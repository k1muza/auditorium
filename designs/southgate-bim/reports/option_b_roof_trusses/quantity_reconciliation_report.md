# Quantity reconciliation report - Option B candidate

Sources: candidate IFC schedules (`schedules/`), independent closed-form hand calculation (`reconciliation/hand_calculation_member_mass.csv`),
geometry engine output, and R2 (`config/option_b/r2_basis.json`). **No quantity was adjusted to match R2.**

## Bridge from R2 to the model (truss set, 11 trusses)

| Step | Mass (kg) | Delta (kg) | Status |
|---|---|---|---|
| R2 truss set incl. connections (reported) | 42,100.0 |  | PRELIMINARY_ESTIMATE |
| R2 member mass, 2 gable + 2 rigging + 7 typical (R2 formula) | 33,044.7 |  | PRELIMINARY_ESTIMATE |
| R2 connection allowance (27.4 % of members) | 9,055.3 |  | PRELIMINARY_ESTIMATE |
| Hand calc H1 (R2 geometry, node-to-node lengths) - check vs R2 members | 33,044.7 | 0.0 | INDEPENDENT_CHECK |
| Hand calc H2 (DEV-01 setting-out: TOS on the purlin seat) | 32,909.6 | -135.1 | INDEPENDENT_CHECK |
| Model member mass (cut lengths x kg/m; set-backs, heel extensions, splice gaps) | 31,514.7 | -1394.9 | MODEL_DERIVED |
| Model plates (gussets + splice + packing, net of holes) | 3,143.7 |  | MODEL_DERIVED / ASSUMPTION_DEPENDENT |
| Model bolt sets (simplified geometry) | 976.3 |  | ASSUMPTION_DEPENDENT |
| Model truss set total (indicative) | 35,634.7 | -6465.3 | MODEL_DERIVED (sizes CONCEPT_UNVERIFIED) |

- The hand calculation on R2's own geometry reproduces R2's member masses exactly (lines 0, 1, 2, 4: 2873.4, 3033.1, 3033.1, 2947.9 kg), which independently confirms the section schedule and web layout.
- DEV-01 (top of steel on the purlin seat) shortens webs by ~0.8 m per truss: -12.6 kg per typical truss.
- Cut lengths (web set-backs from the panel points, heel extensions, 5 mm splice gaps) remove ~127 kg per truss; R2 measured node to node.
- Connection steel: R2 applied a 27.4 % allowance (9.06 t); the modelled plates and bolts total 4.12 t.
- IFC schedules and the geometry engine give identical counts on every truss (True); member mass from IFC geometry volume differs from the catalogue mass by -0.04 %.

## Connection components, typical truss (TT-T)

| Item | R2 count | Model count | R2 mass (kg) | Model mass (kg) | Explanation |
|---|---|---|---|---|---|
| Gusset plates | 26 | 26 | 397.8 | 198.2 | R2 used 15.3 kg per gusset (average of the superseded model's gussets); modelled 10 mm gussets are sized to the bolt groups (avg ~7.7 kg) |
| Splice plates | 20 | 20 | 80.0 | 43.8 | same count (10 splices x 2); R2 allowed 4 kg per plate, modelled 8 mm plates within the connected-leg flat ~2.2 kg |
| Packing plates | 164 | 86 | 196.8 | 43.7 | R2: round(total length/1.2 + webs) double counts (connections already restrain the ends); model: ceil(clear/1.2)-1 per clear length, >= 1 per web |
| Bolt sets | 448 | 330 | 156.8 | 88.7 | webs 100 = 100; splice 80 = 80; chord-to-gusset R2 104 vs model 64 (at the 10 splice nodes the splice bolts pass through the gusset - DEV-03); packer bolts follow the packer count |
| Angles | 74 | 74 | 3033.1 | 2891.1 | same piece count; mass difference from DEV-01 and cut lengths (see bridge) |

## Reading the difference

The model is **15.4 % lighter** than R2's 42.1 t: about 1.5 t from member lengths (measured rather than node-to-node, DEV-01)
and about 4.9 t from connections (R2 used the superseded model's average gusset of 15.3 kg and generous packer/bolt allowances).
Both figures rest on unverified sizes and placeholder detailing: gusset sizes in particular will grow once bolt groups and
block-tearing are designed. For budgeting, keep R2's 42.1 t (PRELIMINARY_ESTIMATE) until the connection design exists;
use the model quantities for counts, cut lists and the measurement structure.
