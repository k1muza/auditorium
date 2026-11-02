"""Render presentation views of the saved model (read-only: never saves the .blend).

  blender --background --factory-startup model/church_3000_concept.blend --python scripts/render_views.py -- renders
"""
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

OUT = Path(sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else "renders").resolve()
OUT.mkdir(parents=True, exist_ok=True)
scene = bpy.context.scene
scene.render.engine = "BLENDER_WORKBENCH"
sh = scene.display.shading
sh.light, sh.color_type = "STUDIO", "OBJECT"
sh.show_cavity, sh.cavity_type = True, "BOTH"
sh.show_shadows = True
sh.show_object_outline = True
scene.display.shading.background_type = "VIEWPORT"
scene.render.resolution_x, scene.render.resolution_y = 1920, 1080
scene.render.film_transparent = False
scene.render.use_stamp = True  # revision stamp so images can't be confused between model revisions
for k in ("use_stamp_date", "use_stamp_time", "use_stamp_render_time", "use_stamp_frame", "use_stamp_camera",
          "use_stamp_lens", "use_stamp_scene", "use_stamp_filename", "use_stamp_memory", "use_stamp_hostname"):
    if hasattr(scene.render, k):
        setattr(scene.render, k, False)
scene.render.use_stamp_note = True
scene.render.stamp_note_text = f"CA3000 concept | rev {scene.get('revision')} | CONCEPT - UNVERIFIED - NOT FOR CONSTRUCTION"
scene.render.stamp_font_size = 18

ALL = list(scene.objects)
for o in ALL:  # documentation text / grid lines and zone volumes never render
    if o.get("ifc_class") == "DOC" or o.users_collection[0].name.startswith(("60_", "50_SRV_Allowances")):
        o.hide_render = True
base_hidden = {o.name for o in ALL if o.hide_render}


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
    return cam


def shoot(fname):
    scene.render.filepath = str(OUT / fname)
    bpy.ops.render.render(write_still=True)
    print("RENDERED", fname, (OUT / fname).is_file())


roofish = ("ENV-ROOF", "ENV-WALL-GABLE", "STR-PURLIN", "STR-BRACE-ROOF", "ENV-FLASHING", "STR-BEAM-FOYROOF")
west = ("ENV-WALL-HALL-W", "ENV-WALL-EXT-W", "ENV-WALL-EXT-FACADE")

# 1 exterior aerial perspective
show(lambda o: True)
camera("CAM1", (-55, -60, 55), (29.5, 44, 4), lens=30)
shoot("01_exterior_aerial.png")
# 2 cutaway: roof, roof framing and west walls removed
show(lambda o: not o.name.startswith(roofish + west))
camera("CAM2", (-50, -35, 62), (29.5, 46, 0), lens=30)
shoot("02_cutaway_aerial.png")
# 3 interior: from the platform looking at the congregation
show(lambda o: not o.name.startswith(("ENV-ROOF", "STR-PURLIN", "STR-BRACE-ROOF")))
camera("CAM3", (29.5, 74.0, 4.2), (29.5, 30.0, 1.5), lens=18)
shoot("03_interior_from_platform.png")
# 4 interior: from the rear platform looking at the stage
camera("CAM4", (29.5, 17.4, 5.8), (29.5, 70.0, 1.2), lens=18)
shoot("04_interior_from_rear.png")
# 5 structure only
show(lambda o: o.users_collection[0].name.startswith("30_STR"))
camera("CAM5", (-45, -40, 45), (29.5, 44, 6), lens=30)
shoot("05_structure_only.png")
# 6 top-down plan (roofs off)
show(lambda o: not o.name.startswith(roofish) and not o.name.startswith(("STR-TRUSS", "STR-BEAM-EAVES", "ENV-WALL-HALL-W-UPPER", "ENV-WALL-HALL-E-UPPER")))
camera("CAM6", (29.5, 44, 120), (29.5, 44.001, 0), ortho=100)
scene.render.resolution_x, scene.render.resolution_y = 1400, 1900
shoot("06_top_plan.png")
print("DONE - .blend not saved")
