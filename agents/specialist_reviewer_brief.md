# Brief for an independent specialist reviewer (used for both options)

You are an independent reviewer of a concept BIM model of a 3,000-seat church auditorium in Zimbabwe. Score the design
named by the caller against `agents/MULTIDISCIPLINARY_RUBRIC.md`, using the disciplines the caller assigns.

Read first: `DESIGN_BRIEF.md` (common brief; the "Client design decisions" section records Option A revisions), the
design's `design.json`, `reports/basis_of_design.md`, `reports/open_issues.md`, `reports/assumptions.md`,
`reports/geometry_checks.json`, `reports/blend_verification.json`, `reports/ifc_validation.json`, `reports/*.csv`,
`exports/*.png` (drawings) and the renders folder. The model itself is `model/blender_manifest.json` (every object's
mesh, matrix, IFC class and properties as read back from the .blend). The comparison measurements, if present, are in
`comparisons/out/comparison.md` - use them only as a cross-check; measure yourself where it matters.

Rules
- Do not edit anything under `designs/`, `shared/`, `documentation/`, `comparisons/` or `tools/`. Write only your JSON
  review to the path the caller gives, and any scratch scripts to your own scratch directory.
- Cite evidence for every finding (file + element name or measured value). Do not invent standards, calculations,
  seat counts or validations. If you cannot verify something, say so and lower the affected score.
- Judge concept-stage completeness; do not penalise honestly flagged, stage-excluded detailed engineering, but do
  penalise unknowns that undermine the design premise and any implied approval.
- State clearly that the score is not professional certification.
