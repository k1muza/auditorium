"""Matching-camera comparison renders (Workbench, no render enhancements).

Source model (read-only snapshot, nothing saved):
  blender -b --factory-startup source/snapshot/southgate_source_snapshot_20261107.blend --python-exit-code 1 \
     --python scripts/export/render_views.py -- --mode source --out renders/comparisons
IFC model through Bonsai (isolated profile, BLENDER_USER_RESOURCES set):
  blender -b --python-exit-code 1 --python scripts/export/render_views.py -- --mode ifc --ifc bim/southgate.ifc --out renders/comparisons
Also: --mode visfile --ifc bim/southgate.ifc  -> writes bim/visualisation.blend (cameras, lights, render settings only)
"""
import bpy, sys, os, json, re, math, argparse
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
ap = argparse.ArgumentParser()
ap.add_argument("--mode", choices=["source", "ifc", "visfile"], required=True)
ap.add_argument("--ifc")
ap.add_argument("--out", default="renders/comparisons")
ap.add_argument("--root", default=os.getcwd())
ap.add_argument("--views", nargs="*")
a = ap.parse_args(argv)
ROOT = a.root
cfg = json.load(open(os.path.join(ROOT, "config/views.json")))
plan_members = json.load(open(os.path.join(ROOT, "work/plan/members_by_stable_id.json")))
src_meta = json.load(open(os.path.join(ROOT, "work/plan/source_render_meta.json")))   # name -> {coll, zmin, visible, in_scope}


def setup_scene(scene):
    scene.render.engine = "BLENDER_WORKBENCH"
    sh = scene.display.shading
    sh.light = "STUDIO"
    sh.color_type = "MATERIAL"
    sh.show_cavity = False
    sh.show_shadows = False
    sh.show_object_outline = True
    sh.show_backface_culling = False
    scene.display.render_aa = "8"
    scene.render.resolution_x, scene.render.resolution_y = cfg["resolution"]
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = True
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.view_settings.view_transform = "Standard"


def make_camera(scene, v):
    cam = bpy.data.cameras.new("CAM-" + v["id"])
    ob = bpy.data.objects.new("CAM-" + v["id"], cam)
    scene.collection.objects.link(ob)
    ob.location = Vector(v["loc"])
    d = Vector(v["target"]) - Vector(v["loc"])
    ob.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    if v["type"] == "ORTHO":
        cam.type = "ORTHO"
        cam.ortho_scale = v["ortho_scale"]
    else:
        cam.lens = v.get("lens", 35)
    cam.clip_start, cam.clip_end = 0.1, 1000
    return ob


def hidden_by_view(name, v):
    h = v.get("hide") or {}
    m = src_meta.get(name)
    if m is None:
        return False
    if "collections" in h and m["coll"] in h["collections"]:
        return True
    if "name_regex" in h and re.search(h["name_regex"], name):
        return True
    if "min_z_above" in h and m["zmin"] > h["min_z_above"]:
        return True
    return False


def render(scene, objs_with_keys, v, tag):
    for ob, key in objs_with_keys:
        hide = key is None or (all(hidden_by_view(n, v) for n in key) if key else False)
        ob.hide_render = hide
    cam = make_camera(scene, v)
    scene.camera = cam
    os.makedirs(os.path.join(ROOT, a.out), exist_ok=True)
    scene.render.filepath = os.path.join(ROOT, a.out, f"{v['id']}_{tag}.png")
    bpy.ops.render.render(write_still=True)
    print("RENDERED", scene.render.filepath, flush=True)


views = [v for v in cfg["views"] if not v.get("skip") and (not a.views or v["id"] in a.views)]
scene = bpy.context.scene

if a.mode == "source":
    setup_scene(scene)
    # material colour: use the principled base colour for Workbench (in memory only)
    for m in bpy.data.materials:
        if m.use_nodes and m.node_tree:
            for n in m.node_tree.nodes:
                if n.type == "BSDF_PRINCIPLED":
                    c = n.inputs["Base Color"].default_value
                    m.diffuse_color = (c[0], c[1], c[2], max(0.25, n.inputs["Alpha"].default_value))
    objs = []
    for ob in scene.objects:
        if ob.type not in ("MESH", "CURVE", "FONT"):
            ob.hide_render = True
            continue
        meta = src_meta.get(ob.name)
        in_scope = meta is not None and meta["in_scope"] and meta["visible"]
        objs.append((ob, [ob.name] if in_scope else None))
    for v in views:
        render(scene, objs, v, "source")
    print("SOURCE_RENDERS_DONE")
    # never saved

elif a.mode in ("ifc", "visfile"):
    import addon_utils
    name = next(m.__name__ for m in addon_utils.modules() if m.__name__.endswith("bonsai"))
    addon_utils.enable(name, default_set=True)
    import bonsai.tool as tool
    bpy.ops.wm.read_homefile(use_empty=True)
    scene = bpy.context.scene
    if a.mode == "visfile":
        setup_scene(scene)
        col = bpy.data.collections.new("SOUTHGATE-COMPARISON-CAMERAS")
        scene.collection.children.link(col)
        for v in cfg["views"]:
            if v.get("skip"):
                continue
            cam = make_camera(scene, v)
            scene.collection.objects.unlink(cam)
            col.objects.link(cam)
        # presentation rigs from the source snapshot (VISUAL_ONLY dispositions): append cameras and lights
        snap = os.path.join(ROOT, "source/snapshot/southgate_source_snapshot_20261107.blend")
        rig = bpy.data.collections.new("SOURCE-PRESENTATION-RIGS (VISUAL_ONLY)")
        scene.collection.children.link(rig)
        with bpy.data.libraries.load(snap, link=False) as (src, dst):
            dst.objects = [n for n in src.objects if src_meta.get(n, {}).get("visual_only")]
        for ob in dst.objects:
            if ob is not None:
                rig.objects.link(ob)
        scene["southgate_note"] = ("Visualisation only. Construction information lives in bim/southgate.ifc (authoritative). "
                                   "Open the IFC with Bonsai (File > Open IFC Project) or run scripts/export/render_views.py --mode ifc. "
                                   "This .blend contains cameras, lights and render settings - no building geometry.")
        scene["southgate_ifc"] = "bim/southgate.ifc"
        out = os.path.join(ROOT, "bim/visualisation.blend")
        if os.path.exists(out):
            raise SystemExit("bim/visualisation.blend exists - refusing to overwrite (move it first)")
        bpy.ops.wm.save_as_mainfile(filepath=out)
        print("VISFILE_SAVED", out, len(rig.objects), "rig objects")
    else:
        bpy.ops.bim.load_project(filepath=os.path.abspath(a.ifc))
        scene = bpy.context.scene          # load_project replaces the scene
        setup_scene(scene)
        ifc = tool.Ifc.get()
        objs = []
        for ob in scene.objects:
            e = tool.Ifc.get_entity(ob)
            if e is None or ob.type != "MESH" or e.is_a("IfcSpatialElement") or e.is_a("IfcOpeningElement") \
                    or e.is_a("IfcSpace") or e.is_a("IfcSpatialZone"):
                ob.hide_render = True
                continue
            objs.append((ob, plan_members.get(e.Name, [])))
        print("IFC objects for render", len(objs))
        for v in views:
            render(scene, objs, v, "ifc")
        print("IFC_RENDERS_DONE")
