"""Bonsai round trip for an Option B IFC (headless, isolated Blender profile). The input file is never written.

  set BLENDER_USER_RESOURCES=%LOCALAPPDATA%\\SouthgateBIM\\blender_user
  blender -b --python-exit-code 1 --python scripts/option_b/bonsai_roundtrip.py -- --in <ifc> --out <new ifc> [--edit SOUTHGATE-RTB-T05-D04-A]

1. bim.load_project; counts Blender objects created for the Option B elements (every element must load)
2. optional parametric edit of one angle with Bonsai's own operator (bim.change_extrusion_depth +50 mm)
3. bim.save_project to a NEW file; writes <out>_bonsai.json
"""
import bpy, sys, json, argparse, addon_utils, os, time
argv = sys.argv[sys.argv.index("--") + 1:]
ap = argparse.ArgumentParser()
ap.add_argument("--in", dest="inp", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--edit")
a = ap.parse_args(argv)
assert os.path.abspath(a.inp) != os.path.abspath(a.out)
name = next(m.__name__ for m in addon_utils.modules() if m.__name__.endswith("bonsai"))
addon_utils.enable(name, default_set=True)
import bonsai.tool as tool
import ifcopenshell.util.element as ue
import ifcopenshell.util.representation as ur
t0 = time.time()
bpy.ops.wm.read_homefile(use_empty=True)
bpy.ops.bim.load_project(filepath=os.path.abspath(a.inp))
ifc = tool.Ifc.get()
new = [e for e in ifc.by_type("IfcElement") if (e.Name or "").startswith("SOUTHGATE-RTB-")]
geom = [e for e in new if e.Representation]
loaded = [e for e in geom if tool.Ifc.get_object(e) is not None]
res = {"input": a.inp, "bonsai": name, "load_seconds": round(time.time() - t0, 1), "new_elements": len(new),
       "with_geometry": len(geom), "blender_objects_for_them": len(loaded),
       "not_loaded": [e.Name for e in geom if tool.Ifc.get_object(e) is None][:10],
       "ifc_elements_total": len(ifc.by_type("IfcElement"))}
if a.edit:
    el = next(e for e in new if e.Name == a.edit)
    obj = tool.Ifc.get_object(el)
    ext = tool.Model.get_extrusion(ur.get_representation(el, "Model", "Body", "MODEL_VIEW"))
    res["edit"] = {"element": a.edit, "before_depth": ext.Depth, "profile": ext.SweptArea.ProfileName,
                   "usage_before": ue.get_material(el, should_skip_usage=False).is_a()}
    for o in bpy.context.selected_objects:
        o.select_set(False)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    r = bpy.ops.bim.change_extrusion_depth(depth=ext.Depth + 0.05)
    ext = tool.Model.get_extrusion(ur.get_representation(el, "Model", "Body", "MODEL_VIEW"))
    res["edit"].update({"operator": list(r), "after_depth": ext.Depth, "profile_after": ext.SweptArea.ProfileName,
                        "profile_is_LShape": ext.SweptArea.is_a("IfcLShapeProfileDef"),
                        "usage_after": ue.get_material(el, should_skip_usage=False).is_a(),
                        "type_after": ue.get_type(el).Name if ue.get_type(el) else None})
bpy.context.scene.BIMProperties.ifc_file = os.path.abspath(a.out)
bpy.ops.bim.save_project(filepath=os.path.abspath(a.out), should_save_as=True)
res["saved"] = os.path.exists(a.out)
res["seconds"] = round(time.time() - t0, 1)
print("BONSAI_ROUNDTRIP", json.dumps(res))
json.dump(res, open(os.path.splitext(a.out)[0] + "_bonsai.json", "w"), indent=1)
