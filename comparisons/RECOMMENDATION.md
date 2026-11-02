Recommendation - which configuration merits detailed engineering development (2026-11-02)

Compared: Option A end stage PL08-590d273e35 (frozen baseline) and Option B long-side stage B03-44bc3ae457 (after three review iterations). All figures are measured from the two Blender manifests by comparisons/compare.py; review scores are QA metrics from three independent reviewers on one rubric, not engineering certification. Neither option met the acceptance bar (weighted score above 9.0 with no critical blockers): A 5.97, B 6.40, both with no critical blockers.

Recommendation: take Option B (long-side stage) forward to detailed design development, subject to the five gates below. If the client's binding constraint turns out to be capital cost or site area rather than the worship experience, Option A remains the lower-cost, more compact and simpler fallback, and should not be discarded.

Why B. The brief asked whether a wide, shallow room gives a better worship experience for 3,000 people. On the measured evidence it does, and the gain is built into the geometry, so A could never be revised to match it. Mean eye-to-pulpit distance falls from 35.5 m to 28.6 m and the farthest seat from 57.6 m to 40.1 m. Seats within 30 m of the pulpit rise from 38 % to about 48 %. No seat turns its head more than about 15 degrees to the pulpit, where A has 670 seats beyond 30 degrees. The rake top is 3.3 m instead of 4.3 m. The reviewers scored church functionality 7.2 for B against 5.5 for A, and B now leads on six of nine disciplines.

What B costs. Measured against A, B has 33 % more footprint (7,303 vs 5,473 m2), 28 % more roof (6,844 vs 5,332 m2), and about twice the linear roof steel (A's purlins are understated, so the real gap is smaller). Its truss span is not shorter (53 m vs 50 m). Two-thirds of its occupants leave by stairs from +3.3 m. Its straight-line seat-to-exit distances are longer (max 32.8 m vs 26.1 m), and 535 occupants exceed the 30 m in-hall travel flag against A's 490. Its altar-call floor is smaller (43 vs 117 m2), and 232 seats sit more than 75 degrees off the pulpit axis. These are the risks the next stage must close or accept knowingly.

Gates for B before detailed engineering:
1. Egress: add grade-level exits through the side walls at the feet of the cross-aisle ramps. Re-run egress on a proper route graph against the applicable Zimbabwean fire regulations (a fire engineer to confirm factors), and protect the back-of-house exit passages.
2. Cost: a quantity surveyor compares A and B on rates, including purlin optimisation for both. Proceed with B only if the cost premium is acceptable to the client.
3. Worship function: enlarge the ministry / altar-call floor to about 100 m2 by dropping one or two centre rows, and bring the choir tiers against the platform sides by moving the platform stair and ramp outboard. The client must confirm the choir facing the congregation, which departs from the Option A preference.
4. Structure: a structural engineer confirms the 53 m Pratt trusses (uplift restraint, splices and erection in Zimbabwe), the pinned rafter-to-truss connection, wind girts for the 13.5 m walls, and gutter access at +11.3 m.
5. Site: a survey and geotechnical report confirm that the larger footprint fits. A sloping site could lower the front of the hall and reduce the stair dependency.

Known documentation discrepancy (not fixed, because the review loop is closed): the B03 assumptions register still says "about 51 m span, 3.0 m deep, bearing +9.5"; the model has a 53.05 m span, 3.5 m depth and bearing about +12.3. The model and every measured table are correct.

Nothing in this study is construction-ready: member sizes, foundations, fire approval, acoustics, MEP and costs all remain to be done by qualified professionals.
