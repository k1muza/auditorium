"""Isolated-copy edit test THROUGH BONSAI (headless, isolated Blender profile).

  blender -b --python-exit-code 1 --python scripts/validate/bonsai_modify_wall.py -- \
      --in work/pilot/pilot_qto.ifc --out work/pilot/pilot_modified_by_bonsai.ifc \
      --wall SOUTHGATE-WALL-0279 --add-height 0.5 --add-length 1.0
Loads the IFC with bim.load_project, edits the wall with Bonsai's own parametric
operators (bim.change_extrusion_depth / bim.change_layer_length), saves a NEW file
with bim.save_project.  The input file is never written.
"""
import bpy, sys, json, argparse, addon_utils, os

argv = sys.argv[sys.argv.index("--") + 1:]
ap = argparse.ArgumentParser()
ap.add_argument("--in", dest="inp", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--wall", required=True)
ap.add_argument("--add-height", type=float, default=0.5)
ap.add_argument("--add-length", type=float, default=1.0)
a = ap.parse_args(argv)
assert os.path.abspath(a.inp) != os.path.abspath(a.out)
name = next(m.__name__ for m in addon_utils.modules() if m.__name__.endswith("bonsai"))
addon_utils.enable(name, default_set=True)
import bonsai.tool as tool
import ifcopenshell.util.element as ue
import ifcopenshell.util.representation as ur

bpy.ops.wm.read_homefile(use_empty=True)
bpy.ops.bim.load_project(filepath=os.path.abspath(a.inp))
ifc = tool.Ifc.get()
wall = next(w for w in ifc.by_type("IfcWall") if w.Name == a.wall)
obj = tool.Ifc.get_object(wall)
res = {"wall": a.wall, "guid": wall.GlobalId, "blender_object": obj.name if obj else None}
ext = tool.Model.get_extrusion(ur.get_representation(wall, "Model", "Body", "MODEL_VIEW"))
res["before_height"] = ext.Depth
axis = ur.get_representation(wall, "Plan", "Axis", "GRAPH_VIEW")
pts = axis.Items[0].Points.CoordList
res["before_length"] = abs(pts[1][0] - pts[0][0])
for o in bpy.context.selected_objects:
    o.select_set(False)
obj.select_set(True)
bpy.context.view_layer.objects.active = obj
r1 = bpy.ops.bim.change_extrusion_depth(depth=res["before_height"] + a.add_height)
r2 = bpy.ops.bim.change_layer_length(length=res["before_length"] + a.add_length)
res["operator_results"] = [list(r1), list(r2)]
ext = tool.Model.get_extrusion(ur.get_representation(wall, "Model", "Body", "MODEL_VIEW"))
res["after_height"] = ext.Depth
axis = ur.get_representation(wall, "Plan", "Axis", "GRAPH_VIEW")
pts = axis.Items[0].Points.CoordList
res["after_length"] = abs(pts[1][0] - pts[0][0])
res["openings_after"] = [o.RelatedOpeningElement.Name for o in wall.HasOpenings]
res["material_after"] = ue.get_material(wall).is_a()
bpy.context.scene.BIMProperties.ifc_file = os.path.abspath(a.out)
bpy.ops.bim.save_project(filepath=os.path.abspath(a.out), should_save_as=True)
res["saved"] = os.path.exists(a.out)
print("BONSAI_EDIT", json.dumps(res))
json.dump(res, open(os.path.splitext(a.out)[0] + "_bonsai_edit.json", "w"), indent=1)
