# Evidence Index and Audit Log

All images and copied source extracts in this directory correspond to authoritative revision `PL01-7cafe48b2e`. The stale iteration-03 viewing copy was not used as the review model.

## Independent extraction

- `independent_blender_audit.py` — read-only Blender/bpy extraction script; it never calls a save operator.
- `independent_model_audit.json` — units, file hash, object/class counts, model extents, 68/68 column-footing pairing, truss topology and sightline summary.
- `sightline_off_axis_samples.csv` — one row for each of the 3,000 congregation seats.

Execution environment: Blender 5.2.3 LTS, background mode, source `model/church_3000_concept.blend`. Completed successfully on 2026-11-01. Summary returned 3,000 seats; 542 over 45° off-axis, 184 over 60°, 24 over 70°, maximum 72.58°.

## Images

`01`–`04` are measured/annotated plans and section; `05`–`13` are current-model axonometric, structural, interior, stage, exterior and roof views. The filenames are referenced directly from the main report.

## Copied source extracts

Files prefixed `source_` are immutable copies of the current project reports/schedules used in this review. They make the report package portable and allow the stated checks to be reproduced without navigating outside the package.
