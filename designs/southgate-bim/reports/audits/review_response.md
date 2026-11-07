# Response to the independent final review

The review (`independent_final_review.md`) was run on the model published at 06:35 (sha `e693b9c2...`).
The fixes below were verified on the model published at 09:37 (sha `6cb86f6d...`) through:

- clean-interpreter validation: 0 schema issues, 0 duplicate GlobalIds, 58/58 openings filled, 162 layer-set and 1,433 profile-set usages, 0 verification claims;
- the stale-quantity check: 0 stale values;
- fresh comparison renders.

| # | Objection | Action | Result |
|---|---|---|---|
| O-01 | Impossible stored volumes and masses (roof lining 6,390 m³, louvre banks 783 t each) | A volume is kept only if the IFC body is a closed, consistently oriented surface and fits inside its own bounding box. Otherwise `Qto` volumes and weights are removed, `VolumeReliable=False` is set, and a note is recorded. | Lining, spiral handrail, roof-screw sets and louvre banks carry no volume. Closed solids (e.g. hall slab 281.98 m³) keep theirs. **Fixed** |
| O-02 | Wall base quantities swapped or wrong on 56 walls | For non-DumbLayer2 walls, Length/Width/Height/GrossSideArea/NetSideArea come from the body extents. Cubicle parts are no longer walls. | Remaining small wall areas are genuine infill pieces with correct dimensions. **Fixed** |
| O-03 | `NativeRepresentation=True` on 2,155 meshes and on stretched primitives | Type-mapped tessellated bodies and non-uniformly scaled mapped primitives are counted as not native, with a note in `MigrationNotes`. | Register: 6,635 native / 4,841 custom source objects, down from 10,644 native. **Fixed** |
| O-04 | Masses from render materials (aluminium brick walls, solid "steel" rakers) | Indicative mass only for steel-category structural/fastener classes that carry a source steel section or bolt designation. | Total indicative mass 79.2 t (all steel; largest item a 13 m UC254 at 940 kg). Real construction materials remain outstanding: OW item. **Fixed / outstanding** |
| O-05 | Misclassification inflating counts | Cubicle legs/rails become IfcMember and panels/dividers IfcPlate, inside their WC cubicle assemblies. Grate bars plus rim become one IfcWasteTerminal per inlet. Lighting hangers become IfcMember. | Walls 210 -> 116, waste terminals 180 -> 18, light fixtures 102 -> 96. **Fixed** |
| O-06 | Nine ground-bearing columns without footings | Not invented: the source has none. | Outstanding work (structural, HIGH). |
| O-07 | Load-bearing slabs and cores marked EXISTING_DESIGN_REFERENCE | All slabs and core walls are `CONCEPT_UNVERIFIED`. `LoadBearing` is still not asserted because the source has no evidence for it. | **Fixed** |
| O-08 | Interior renders hid seats and stage behind space boxes | Space and zone volumes are excluded from both render sides. | Views 07, 08 and 11 now show seating, stage, trusses and rafts. **Fixed** |
| O-09 | Gusset bolts only on truss T06 | Source condition; not invented. | Outstanding work. |
| O-10 | Spaces had no quantities; office rooms have no spaces | IfcSpace is now quantified. Office-room spaces are still outstanding. | **Partly fixed** |
| O-11 | Door offsets (east portal 0.89 m, hall west 1.1 m), unhosted doors and sashes | Source inconsistency (leaves inboard of their jambs/pulls; open leaves). Doors are placed on the frame line. The completeness report now states that door deviations are measured against frame parts. | Needs architectural confirmation: OW item. |
| O-12 | No service ports; no cost classification | Not in the source. | Outstanding work. |
| O-13 | Inventory taken with `is_dirty=True` | The flag is set by the headless read session (mesh evaluation), not by unsaved design work. The snapshot sha256 is unchanged and the deep geometry fingerprint matched before the inventory (`source/source_manifest.json`). | No change needed. |

The 187 phase-E `REVIEW` items, double-angle members whose source meshes are tapered by up to 4.5 mm, are unchanged and explained in the completeness report.
This response, like the review, is not engineering certification.
