# Bonsai / IFC workflow and technology decisions

## Installed and verified environment (2026-11-07)

| Component | Version | How verified |
|---|---|---|
| Blender | 5.2.3 LTS (Python 3.13) | `blender --version` |
| Bonsai | 0.9.0-post1 (windows-x64, Blender >= 5.1) | Official Blender extensions platform (`extensions.blender.org`, id `bonsai`). Archive sha256 `9467fdfb...04d6c` checked before install. Installed with `blender --command extension install-file -r user_default --enable` into an **isolated** profile (`BLENDER_USER_RESOURCES=%LOCALAPPDATA%\SouthgateBIM\blender_user`). The user's everyday Blender profile and live sessions were not changed. |
| IfcOpenShell (in Bonsai) | 0.9.0.post1 | `scripts/validate/bonsai_smoke_test.py` |
| IfcOpenShell (standalone) | 0.9.0.post1 in `.venv` (Python 3.10) | same build as Bonsai, so files written by one are read identically by the other |
| ifc5d (quantity take-off) | 0.9.0 (`--no-deps`, uses the 0.9.0.post1 core) | pilot quantity test |
| Schemas available | IFC2X3, IFC4, IFC4X3_ADD2 | smoke test |

The Bonsai documentation (docs.bonsaibim.org, "Installation") specifies installation through Blender's Get Extensions. The headless CLI install above uses the same package.

## Schema: IFC4

- IFC4 (ADD2 TC1) is Bonsai's default for new projects and the best-supported schema in IfcOpenShell geometry and in ifc5d (`IFC4QtoBaseQuantities`).
- Everything the model needs exists in IFC4: layered walls and slabs, profile sets, parametric door/window properties, `IfcSpatialZone`, `IfcDistributionSystem`, `IfcPolygonalFaceSet` and `ELECTROACOUSTIC` systems.
- IFC4X3 would add `IfcCourse`, `IfcSign` and infrastructure classes, but tool support for building models is less mature. The two IFC4X3-only concepts in the source are handled in IFC4 as follows:
  - Compacted subbase becomes `IfcBuildingElementProxy` with ObjectType `COMPACTED_GRANULAR_SUBBASE`.
  - Signage becomes `IfcBuildingElementProxy` with ObjectType `SIGNAGE`.

## Native authoring: what "native" means here

Bonsai's operators are thin layers over the IfcOpenShell API (`ifcopenshell.api.*`), which is Bonsai's authoring core. The migration calls that API directly, in batch, and reproduces Bonsai's own conventions. These were checked against an IFC written by Bonsai's wall generator in the smoke test:

- **Walls:** a type carries `IfcMaterialLayerSet`. The occurrence carries `IfcMaterialLayerSetUsage` (AXIS2, POSITIVE, offset 0). Representations are an Axis (`Plan/Axis`, Curve2D) and a Body footprint extrusion. `EPset_Parametric.Engine = "Bonsai.DumbLayer2"`.
- **Slabs:** the same pattern with AXIS3 and `Bonsai.DumbLayer3`.
- **Members, columns and beams:** `IfcMaterialProfileSet` on the type and `IfcMaterialProfileSetUsage` on occurrences. The body is the profile extruded along local Z, with `IfcBooleanClippingResult` half-spaces at mitred or plumb-cut ends.
- **Doors and windows:** types use IfcOpenShell's parametric door/window representations, with a `BBIM_Door` / `BBIM_Window` pset whose `Data` JSON follows Bonsai's format. Occurrences are mapped. Openings are `IfcOpeningElement` with `IfcRelVoidsElement` and `IfcRelFillsElement`.
- **Repeated components** (seats, bolts, fixtures): an element type with `IfcRepresentationMap` and `IfcMappedItem` occurrences.

**Verification through Bonsai itself:**

1. The smoke test created, saved and reloaded a Bonsai wall headless.
2. The pilot quantity test loaded the migrated IFC with `bim.load_project`. It edited a migrated wall with Bonsai's own `bim.change_extrusion_depth` and `bim.change_layer_length`, and saved it with `bim.save_project`. The openings, materials and types survived, and the recomputed quantities changed exactly as expected (`reports/quantities/pilot_modification_test.json`).
3. The comparison renders load the complete `bim/southgate.ifc` through Bonsai.

## Saving and update behaviour (Bonsai 0.9.0)

- `bim.save_project` writes the in-memory IFC to the path in `BIMProperties.ifc_file`. Blender objects are a cache of the IFC; they are not a second model.
- Parametric edits rewrite the representation (for example the axis length and the extrusion) but **do not refresh stored `Qto_*` sets**. Stored quantities are stale until `extract_quantities.py` runs again. The `--check` mode detects this, and the pilot test demonstrates it.
- A `.blend` saved while a project is loaded holds derived objects only. That is why `bim/visualisation.blend` deliberately contains no building geometry.

## Coordinates

Blender world metres are used 1:1 as IFC coordinates; Site and Building placements are identity. Storeys are placed at their elevations, and element placements are relative to their storey. True north, geolocation and the absolute datum are **UNVERIFIED** and recorded as such in `SOUTHGATE_ProjectInformation`.
