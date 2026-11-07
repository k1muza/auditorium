# I — Independent review record: Option B support structure study (revision S01)

**What this review is.** A separate AI reviewer was given read-only access to the study code, outputs and draft report. It was not given the author's reasoning. It was asked to challenge the work from three perspectives: structural engineering, geotechnics and foundations, and construction and cost. **This is an AI-assisted internal challenge. It is not an independent professional engineering review or certification.** No registered (ECZ) engineer has reviewed the study.

**Outcome.** The review raised 16 objections: 2 critical, 8 major and 6 moderate or minor. Every objection that affected a number was answered by changing the calculation and re-running the whole chain (sizing, foundations, costs and Monte Carlo); none was answered by editing text alone. The corrections raised all three system totals by about 20%. They also changed the recommendation from "S3, clearly cheapest" to "**S3 on firm ground, S1 on poor/wet ground; the decision is held until the site investigation**".

| # | Perspective | Objection (summary) | Severity | Response and change made | Status |
|---|---|---|---|---|---|
| 1 | Structural / foundations | Holding-down tension was computed from non-concurrent envelopes (maximum compression with maximum moment). At S3 column 1A the concurrent pair (N −291 kN, M −218 kNm) gives T ≈ 648 kN against the 397 kN designed | Critical | `foundations.base_connection` now designs the tension row for the worst **concurrent** (N, M) pair of every ULS combination: T = (M − Nz/2)/z for compression, T = M/z + \|N\|/2 for uplift. Bolt diameter and number rise automatically (S3: 6–8 M24 with anchor plates). Hairpins are sized for the new T | Closed (calculation) |
| 2 | Structural | The purlin-independent girder-chord correction was stated but never applied; the stated CHS 139.7×4.5 was also too small for a 398 kN simple-span chord | Critical/major | In all design runs the purlins are now **nominal links (0.1 % EA)** (`model_b.PURLIN_NOMINAL`). The girders, eaves struts and SLS results come from the analysis without purlin participation. Hard-coded correction text removed | Closed (calculation) |
| 3 | Cost / decision | S3 was "cheapest" only because a 420 mm wall-zone filter excluded cheaper UB designs | Major | The pier enlargement for deep columns is now priced (`architectural_adjustment`), and an unconstrained selection is reported. After corrections 2 and 12, no UB candidate passes in any system, so the filter no longer decides the ranking | Closed |
| 4 | Cost | Sizing heuristic noise (S1 UC305×118 dearer than ×137) was larger than the 5 % margin; the Monte Carlo varied rates only | Major | The stiffening loop now upsizes **one group at a time**, chosen by strain energy per tonne under the governing SLS case. The Monte Carlo adds independent quantity factors per scheme (steel 0.92–1.10, foundations 0.85–1.25). The headline is now P50, with pairwise probabilities: P(S3<S1) ≈ 0.67, P(S3<S2) ≈ 0.89. **The report now states that S3 v S1 is not decisive on cost.** A residual heuristic artefact (S3 UC254×89) is disclosed in §8.1 | Closed; limitation disclosed |
| 5 | Structural | "Only S3 has stiffness reserve" was false longitudinally; S3 eaves sway 41.7 mm at 0.85 kPa and 58.8 mm at 1.20 kPa | Major | Longitudinal sway is now part of the pass criterion (both directions, limit 40.8 mm). The 1.20 kPa case reports both directions and re-sizes the bracing. The claim was removed; §12 reports both directions at both pressures | Closed |
| 6 | Structural / geotechnical | Fixed-base fixity assumed rigid and never checked; lift-off under governing combinations | Major | Rotational base springs added (`Design.base_krx`). Sensitivity runs at ≈50 MNm/rad (G2) and ≈20 MNm/rad (G3), from K = k_s·L·B³/12 halved for partial contact (§11, §15). Subgrade modulus added to the SI scope (R23) | Closed for preliminary stage; SI required |
| 7 | Geotechnical | G3 buoyancy never triggered (strict `>` at equality) | Major | Test changed to `>=`. Design water level raised to −1.00 m (0.4 m above the assumed perched level). G3 costs rose by about USD 50k per system, and **S1 becomes cheapest in G3** | Closed (changes the recommendation) |
| 8 | Foundations | Sliding/shear mechanism mismatch: pad-on-soil sliding was priced as stub keys under the base plate; plate friction used non-concurrent N | Major | Two mechanisms are now priced separately: base-plate shear keys where any uplift combination carries shear, and **pad downstand keys** where concurrent H > μN. Report §11 rewritten | Closed |
| 9 | Geotechnical | F2 wall ballast of 216 kN taken at every pad, including doors, the loggia and the glazed slot; masonry density unverified | Major | Engaged wall weight is now computed per pad net of ground-level openings (`evaluate.engaged_wall`; loggia = no wall on the strip). A 0.7 × density sensitivity is reported (§15). R01 retained | Closed; density remains an assumption |
| 10 | Foundations | Pad checks incomplete: punching ignored moment transfer; anchor hairpins cannot be anchored in a 0.60 m pad with hef 450 | Major | Punching now uses V_eff = V(1 + 1.5M/Vx). Minimum pad depth = hef + 0.30 m, so S3 pads are 0.80 m deep. Upward pull-out is assigned to the designed hairpins. A full EN 1992-4 anchorage design remains for detailed design | Closed for preliminary stage |
| 11 | Structural | h/300 used the column height (13.08 m → 43.6 mm) instead of the masonry height (12.23 m → 40.8 mm); SLS wind basis not justified | Moderate | Limit now uses 12.23 m (40.8 mm). The SLS basis is stated as the characteristic central pressure (0.85 kPa), with 1.20 kPa as a sensitivity (§5.3). Under the correct limit S2 needs UC356×368×153 | Closed |
| 12 | Structural | The "no masonry restraint" sensitivity used 6.5 m, which nothing provides | Moderate | The robustness check now uses the **full height** (13.08 m) and is part of selection. UC305×97 passes (0.93); UC254×73 fails (1.65). The check also showed the gable posts failing (2.6–4.6), so **two rows of restraint struts per gable were added to every system** | Closed (new element added) |
| 13 | Wind | Missing cases: negative dominant cpi (door in suction zone A); uniform −0.8 on the gables under cross-wind; dead code | Moderate | Gable zones A/B are now applied under cross-wind. A cpi −1.08 sensitivity was added (factored at 1.3, conservative if treated as accidental). Dead code removed | Closed |
| 14 | Presentation | Claims stated as fact: eigen-modes "covered", hand-check gap called "plausible", availability claims, missing deliverable I | Minor | The eigen-mode statement was corrected: the bottom-chord mode is referred to the truss design, and the posts get struts. The uplift hand check was redone for the near-edge zone (−83 vs −92 kN, within 10 %). Availability is labelled as study judgement. This record was written | Closed |
| 15 | Consistency | Executive-summary rebar omitted anchor reinforcement; S1 chord text wrong; "5–5 %"; bearing bolts as ties in slotted holes | Minor | All figures are now computed in the report builder. Bearing bolts specified as preloaded (slip-resistant) or fitted | Closed |
| 16 | Constructability | Crossing CHS X-braces cannot pass inside a 300 mm wall; lower ends below FFL; erection productivity optimistic | Minor | X-braces are made in two halves at a central node plate on the inner face or in a chase, with lower gussets inside the encasement pocket. Productivity was reduced to 6 columns, 4 posts and 15 bracing pieces per day plus 2 days of girder assembly (≈23 crane-days) | Closed |

## Items the reviewer checked and found sound
- Solver verification (ratios 0.994–1.001).
- 3D truss reactions 10–25 % above R2.
- Wall-wind tributary application and the zone A/B/C weighting.
- Gross-bearing comparison method.
- Conservative uplift prism.
- Construction-stage case implemented as stated.
- No double count between the strip and the pads.
- Quantities matching the outputs.
- α_cr values justifying first-order analysis.
- CHS bracing consistent with the model stiffness.
- S3 column adequate with no restraint.

## Remaining concerns (not closable in this study)
1. No site investigation. The S1/S3 choice depends on it (gate G-B).
2. Wall construction unconfirmed (gate G-A).
3. The stiffening heuristic is not a true optimiser. Costs carry ±5–10 % method uncertainty, which is included in the Monte Carlo.
4. Anchorage is designed in concept only (EN 1992-4 form, k1 8.9, hairpins sized by force). Full anchorage design is required.
5. The analysis is a verified study model, not a commercial FE package. An independent analysis is required at detailed design.
6. Option B truss items (gable top chord, bottom-chord heel and mid-panel restraint, bearing bolts) are reported to the truss design, not resolved here.
