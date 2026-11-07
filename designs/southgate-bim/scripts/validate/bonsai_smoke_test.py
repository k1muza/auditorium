"""Bonsai capability smoke test (isolated Blender profile, empty scene).

  set BLENDER_USER_RESOURCES=%LOCALAPPDATA%\\SouthgateBIM\\blender_user
  blender -b --python-exit-code 1 --python scripts/validate/bonsai_smoke_test.py -- --out work/bonsai_smoke

Checks: Bonsai importable/enabled, bundled IfcOpenShell version, supported schemas,
native wall authoring through Bonsai operators (bim.create_project + DumbWall API),
save via bim.save_project, reload via bim.load_project, element identity preserved.
"""
import bpy, sys, os, json, argparse, addon_utils, importlib

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
ap = argparse.ArgumentParser(); ap.add_argument("--out", required=True)
a = ap.parse_args(argv)
os.makedirs(a.out, exist_ok=True)
res = {"blender": bpy.app.version_string}

mods = [m.__name__ for m in addon_utils.modules() if "bonsai" in m.__name__]
res["bonsai_modules"] = mods
name = next(m for m in mods if m.endswith("bonsai"))
addon_utils.enable(name, default_set=True)
import bonsai, ifcopenshell, ifcopenshell.api, ifcopenshell.util.element as ue
import bonsai.tool as tool
res["bonsai_version"] = getattr(bonsai, "__version__", None) or str(getattr(bonsai, "bbim_semver", ""))
res["ifcopenshell_version"] = ifcopenshell.version
res["schemas"] = [s for s in ("IFC2X3", "IFC4", "IFC4X3_ADD2") if ifcopenshell.schema_by_name(s)]

# Native authoring through Bonsai operators
bpy.ops.bim.create_project()
ifc = tool.Ifc.get()
res["created_schema"] = ifc.schema
# Bonsai's wall tool: create a layered wall type then a wall occurrence through the UI operator
lset_type = ifcopenshell.api.run("root.create_entity", ifc, ifc_class="IfcWallType", name="SMOKE-WALL-200")
ls = ifcopenshell.api.run("material.add_material_set", ifc, name="SMOKE-LS", set_type="IfcMaterialLayerSet")
mat = ifcopenshell.api.run("material.add_material", ifc, name="Concrete", category="concrete")
layer = ifcopenshell.api.run("material.add_layer", ifc, layer_set=ls, material=mat)
ifcopenshell.api.run("material.edit_layer", ifc, layer=layer, attributes={"LayerThickness": 0.2})
ifcopenshell.api.run("material.assign_material", ifc, products=[lset_type], material=ls)
bpy.context.scene.BIMModelProperties.relating_type_id = str(lset_type.id()) if hasattr(bpy.context.scene, "BIMModelProperties") else None
try:
    from bonsai.bim.module.model import wall as bwall
    obj = bwall.DumbWallGenerator(lset_type).generate()
    res["dumbwall_generator"] = "ok" if obj else "returned None"
except Exception as e:
    res["dumbwall_generator"] = f"error: {e!r}"
walls = ifc.by_type("IfcWall")
res["walls_created"] = len(walls)
if walls:
    w = walls[0]
    res["wall_material_usage"] = ue.get_material(w).is_a()
    res["wall_reps"] = [r.RepresentationIdentifier for r in w.Representation.Representations]
    gid = w.GlobalId
path = os.path.abspath(os.path.join(a.out, "smoke.ifc"))
bpy.context.scene.BIMProperties.ifc_file = path
bpy.ops.bim.save_project(filepath=path, should_save_as=True)
res["saved"] = os.path.exists(path)
# reload through Bonsai
bpy.ops.wm.read_homefile(use_empty=True)
bpy.ops.bim.load_project(filepath=path)
ifc2 = tool.Ifc.get()
res["reloaded_walls"] = len(ifc2.by_type("IfcWall"))
res["guid_preserved"] = bool(walls) and ifc2.by_guid(gid) is not None
res["blender_objects_after_load"] = len(bpy.data.objects)
json.dump(res, open(os.path.join(a.out, "bonsai_smoke.json"), "w"), indent=1)
print("SMOKE", json.dumps(res))
