# Option B | Exit and seating concept comparison

**Baseline:** saved model `B03-44bc3ae457`. **Study status:** unbuilt desktop screens only; no alternative is adopted, certified or issued as a BIM revision. **Method:** `../compare_concepts.py` reruns the B03 layout engine with documented in-memory parameter changes, then uses its existing provisional route and sightline rules. Detailed values and case definitions are in `concept_option_matrix.csv`; the two diagrams show the metric comparison and stage-wall constraints.

## Results

| Case | Change from B03 | Rows / truss span | Choir chairs | Pulpit bearing: max / chairs >60° | Model screen reliance | Hall travel: max / people >30 m flag | Congregation chairs >30 m | Status |
|---|---|---|---:|---:|---:|---:|---:|---|
| **B03** | Saved baseline, ±80° fan, stage exits x19.4 / 69.7 m | 32 / 53.05 m | 412 | 79.98° / 772 | 1,564 | 45.40 m / 535 | 493 | Saved geometry |
| **E20-60** | Route-only stage exit points x20 / 60 m | 32 / 53.05 m | 412 | 79.98° / 772 | 1,564 | 41.59 m / 410 | 384 | Door, ramp and BOH passage geometry unresolved |
| **E22-58** | Route-only stage exit points x22 / 58 m | 32 / 53.05 m | 412 | 79.98° / 772 | 1,564 | 42.75 m / 388 | 356 | Door, ramp and BOH passage geometry unresolved |
| **S75** | ±75° fan; choir reach reduced to 18.5 m | 33 / 54.00 m | 405 | 74.97° / 604 | 1,688 | 44.91 m / 511 | 467 | Unbuilt engine case; no geometry-check failures |
| **S72** | ±72.5° fan; choir reach reduced to 17.3 m | 34 / 54.95 m | 418 | 72.48° / 500 | 1,756 | 44.77 m / 521 | 477 | Unbuilt engine case; no geometry-check failures |
| **S75+E20-60** | S75 plus route-only exit shift | 33 / 54.00 m | 405 | 74.97° / 604 | 1,688 | 41.41 m / 392 | 364 | Combined screen; exit geometry unresolved |

“People >30 m” includes the modelled congregation, wheelchair users and companions, choir and platform party; the choir count differs slightly in seating cases. The congregation-only column provides a fixed 3,000-chair comparison. All travel values are **within-hall plan distances to assigned hall exits** under the model's placeholder width factors. The 30 m value is a provisional screen, not a Zimbabwean legal limit. No case models a complete safe external discharge path.

## What the alternatives show

1. **Moving exit points helps travel but does not fix it.** E20-60 lowers the maximum modelled hall distance by 3.81 m and reduces the count above the provisional flag by 125. E22-58 reduces that count by 147 but has a longer worst path than E20-60. Neither changes the 772 side seats above 60° bearing. Even if every B03 occupant could use the nearest existing hall exit without a capacity constraint, 459 would still exceed the 30 m flag; increasing widths alone cannot remove the distance pattern.
2. **The tested exit shifts are not physical door designs.** B03's east platform ramp occupies approximately x55.0-67.3 m, immediately in front of the stage wall, and its east protected BOH exit passage is x67.9-71.5 m. The proposed east door openings would be x58.2-61.8 m or x56.2-59.8 m. Their access and protected discharge would require a new ramp arrangement, BOH passage, room layout and door/structure coordination. The route results must not be read as approved exit capacities or total evacuation distances.
3. **Narrowing the fan improves bearing but does not solve travel.** S75 reduces the >60° seat count by 168; S72 reduces it by 272. The 3,000 congregation chairs need one or two more rows, lengthening the truss span by 0.95 or 1.90 m. Model screen reliance increases by 124 or 192 chairs. The remaining hall-travel flags are 511 and 521 people, respectively.
4. **The combined screen is still unresolved.** S75+E20-60 has the lowest tested worst distance (41.41 m) and 392 people above the provisional flag, while 604 chairs remain above 60° bearing. It inherits the exit geometry conflict and needs full physical remodelling.

## Recommended next design brief

Keep B03 as the reference. Develop **two fully modelled concept branches** for professional/client review:

- **Exit-led branch:** retain the 160° fan while creating an actual shorter, step-free route for the front-centre and cross-aisle wheelchair positions. Coordinate any stage-side door shift with the platform ramp, choir zones, BOH protected passages and external safe discharge. Test door/stair loads and route separation on the same occupancy basis.
- **Balanced branch:** use approximately a 150° fan (S75 as the starting geometry), recover a client-approved choir count and distribution, and design the same front-centre exit improvement. Reassess roof span, rake, wheelchair-band spacing, sightlines to platform/choir/displays and structural implications.

Neither branch should be accepted from these numbers alone. First obtain the fire designer's applicable travel/width/discharge basis and the client's acceptable direct-view and IMAG criteria. Then build each branch as a new model revision, run clash and accessible-route checks, issue updated drawings, and submit them for independent professional review.

## Reproduction and limits

`../compare_concepts.py` writes `concept_option_matrix.csv`, `concept_option_comparison.png` and `stage_exit_constraints.png`. Seating cases change only `fan_half_angle_deg`, its matching bearing setting and `stage.choir.max_reach` in memory; the choir reach is retuned to keep the count near B03 (405 and 418 versus 412). Exit cases change only the two stage-exit XY points in the **egress calculation** after the layout has been generated; saved doors, openings, ramp, BOH route and IFC are untouched. Existing geometry checks report no failure for S75 and S72, but neither has a saved Blender/IFC model or independent view/structure/fire validation. The model's screen-reliance rule is an AV placeholder, and the bearing measure is not an obstruction study.
