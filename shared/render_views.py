"""Render presentation views of any design's saved model (read-only: never saves the .blend).

  blender --background --factory-startup <model.blend> --python shared/render_views.py -- <out dir>

Generalised from designs/A-end-stage/scripts/render_views.py: cameras come from the scene's own metrics
(metrics_json["render_views"]: pulpit eye point, rear eye point, look targets) and its bounding box, not from A's
coordinates. Every image is stamped with the design ID and model revision.
"""
import json
import sys
from pathlib import Path

import bpy
from mathutils import Vector

OUT = Path(sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else "renders").resolve()
OUT.mkdir(parents=True, exist_ok=True)
scene = bpy.context.scene
metrics = json.loads(scene.get("metrics_json", "{}"))
RV = metrics["render_views"]
scene.render.engine = "BLENDER_WORKBENCH"
sh = scene.display.shading
sh.light, sh.color_type = "STUDIO", "OBJECT"
sh.show_cavity, sh.cavity_type = True, "BOTH"
sh.show_shadows = True
sh.show_object_outline = True
scene.render.resolution_x, scene.render.resolution_y = 1920, 1080
scene.render.use_stamp = True
for k in ("use_stamp_date", "use_stamp_time", "use_stamp_render_time", "use_stamp_frame", "use_stamp_camera", "use_stamp_lens",
          "use_stamp_scene", "use_stamp_filename", "use_stamp_memory", "use_stamp_hostname"):
    if hasattr(scene.render, k):
        setattr(scene.render, k, False)
scene.render.use_stamp_note = True
scene.render.stamp_note_text = f"{RV['design_id']} | rev {scene.get('revision')} | CONCEPT - UNVERIFIED - NOT FOR CONSTRUCTION"
scene.render.stamp_font_size = 18
ALL = list(scene.objects)
for o in ALL:
    if o.get("ifc_class") == "DOC" or o.users_collection[0].name.startswith(("60_", "50_SRV_Allowances")):
        o.hide_render = True
base_hidden = {o.name for o in ALL if o.hide_render}
pts = [o.matrix_world @ Vector(c) for o in ALL if o.type == "MESH" and o.name.startswith(("ENV-", "ARC-SLAB")) for c in o.bound_box]
lo = Vector((min(p.x for p in pts), min(p.y for p in pts), 0.0))
hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
C = (lo + hi) / 2
span = max(hi.x - lo.x, hi.y - lo.y)


def show(pred):
    for o in ALL:
        o.hide_render = o.name in base_hidden or not pred(o)


def camera(name, loc, target, lens=28.0, ortho=None):
    cd = bpy.data.cameras.new(name)
    if ortho:
        cd.type, cd.ortho_scale = "ORTHO", ortho
    else:
        cd.lens = lens
    cd.clip_end = 1000
    cam = bpy.data.objects.new(name, cd)
    scene.collection.objects.link(cam)
    cam.location = loc
    cam.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    scene.camera = cam


def shoot(fname):
    scene.render.filepath = str(OUT / fname)
    bpy.ops.render.render(write_still=True)
    print("RENDERED", fname, (OUT / fname).is_file())


roofish = tuple(RV["roof_prefixes"])
cutaway = tuple(RV["cutaway_prefixes"])
show(lambda o: True)
camera("CAM1", C + Vector((-0.75, -0.95, 0.75)) * span, (C.x, C.y, 4), lens=30)
shoot("01_exterior_aerial.png")
show(lambda o: not o.name.startswith(roofish + cutaway))
camera("CAM2", C + Vector((-0.7, -0.75, 0.85)) * span, (C.x, C.y + 0.05 * span, 0), lens=30)
shoot("02_cutaway_aerial.png")
show(lambda o: not o.name.startswith(roofish))
camera("CAM3", RV["platform_eye"], RV["platform_look"], lens=16)
shoot("03_interior_from_platform.png")
camera("CAM4", RV["rear_eye"], RV["rear_look"], lens=18)
shoot("04_interior_from_rear.png")
camera("CAM4B", RV["side_eye"], RV["side_look"], lens=18)
shoot("04b_interior_from_side_seats.png")
show(lambda o: o.users_collection[0].name.startswith("30_STR"))
camera("CAM5", C + Vector((-0.7, -0.8, 0.65)) * span, (C.x, C.y, 6), lens=30)
shoot("05_structure_only.png")
show(lambda o: not o.name.startswith(roofish) and not o.name.startswith(("STR-TRUSS", "STR-BRACE-ROOF")))
scene.render.resolution_x, scene.render.resolution_y = 1900, 1500
camera("CAM6", (C.x, C.y, 150), (C.x, C.y + 0.001, 0), ortho=1.08 * span)
shoot("06_top_plan.png")
print("DONE - .blend not saved")
