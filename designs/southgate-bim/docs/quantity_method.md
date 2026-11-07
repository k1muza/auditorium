# Quantity calculation method (prototype)

**This is not a priced or complete construction BOQ.** It is a model-derived measurement layer that a quantity surveyor can build a BOQ from.

## Where quantities come from

1. **Base quantities.** `Qto_*BaseQuantities` (Length, Width, Height, Gross/Net areas, Gross/Net volumes, CrossSectionArea, OuterSurfaceArea and so on) are computed by IfcOpenShell's take-off engine `ifc5d`. It uses the official `IFC4QtoBaseQuantities` rule set and works from the **current IFC geometry and parameters** (for example a wall's axis length and extrusion depth, or the true net volume after openings). It runs with `scripts/export/extract_quantities.py`. No quantity is typed in by hand.
2. **Project quantities (`SOUTHGATE_Quantities`):**
   - `IndicativeMassFromDensity_kg` is the Qto volume × the nominal material density from `config/materials.yaml`. It is computed for steel, aluminium and glass only.
   - `NominalSectionMass_kg` is the Qto Length × the source `nominal_mass_per_m_kg` for steel sections.
   - Both are indicative. The basis is stated in the pset.
3. **Derived items the geometry does not provide** (excavation, blinding, formwork, reinforcement, backfill, roofing fasteners) are listed as **unapproved** rules in `config/quantity_rules.yaml`. None of them is applied yet.

## Freshness

- Geometry edits (in Bonsai or through the API) do not update stored `Qto_*` sets.
- Re-run `extract_quantities.py` after every edit.
- `extract_quantities.py --in bim/southgate.ifc --check` recomputes in memory and lists stale stored values. It exits with code 1 if any are stale.

## Pilot (section 10 of the brief)

The pilot used `reports/quantities/pilot_*`, built from a gallery column, raker beam, footing pad, mezzanine slab, two consolidated walls with a native window and door, a double-angle truss chord, a purlin and an IBR sheet.

1. Quantities were extracted from the IFC (`pilot_quantity_schedule.csv`).
2. They were compared with an **independent** measurement of the source meshes taken from the geometry cache (orientation-robust mesh volume and true world-vertex bounds) in `pilot_reconciliation.csv`. Results:
   - Swept elements agree to within 0.01 %.
   - For consolidated walls, net volume equals the sum of the source pieces.
   - Doors and windows are a representation change: overall Width and Height are the reconciled values.
3. A wall was edited with Bonsai in an isolated copy: +1.0 m length and +0.5 m height. The stored quantities were then detectably stale. After recomputation, Length, Height, GrossSideArea and the volumes updated to the expected values. They persisted after save and reopen, and every relationship count was unchanged (`pilot_modification_test.json`).

## Schedules

- `quantity_schedule_elements.csv` has one row per element. Columns: class, type, storey, assembly, material, profile, base quantities, indicative masses, design status, source BOQ flag and representation.
- `quantity_schedule_summary.csv` gives totals by class, predefined type, object type, profile, material and design status.
- Filter on `design_status` before using any total. `CONCEPT_UNVERIFIED` and `PRELIMINARY_DESIGN` items are not construction quantities.
