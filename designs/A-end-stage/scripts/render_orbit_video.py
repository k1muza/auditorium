"""Render a 360-degree orbit + cutaway orbit + interior fly-through MP4 of the saved model (read-only, never saves).

  blender --background --factory-startup model/church_3000_concept.blend --python scripts/render_orbit_video.py -- renders/CA3000_orbit_360.mp4
"""
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

OUT = Path(sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else "renders/CA3000_orbit_360.mp4").resolve()
OUT.parent.mkdir(parents=True, exist_ok=True)
FPS = 30
A0, A1 = 1, 300      # exterior orbit
B0, B1 = 301, 600    # cutaway orbit
C0, C1 = 601, 780    # interior fly-through
CENTER = Vector((29.5, 44.0, 5.0))

scene = bpy.context.scene
rev = scene.get("revision", "unknown")
scene.render.engine = "BLENDER_WORKBENCH"
sh = scene.display.shading
sh.light, sh.color_type = "STUDIO", "OBJECT"
sh.show_cavity, sh.cavity_type = True, "BOTH"
sh.show_shadows = True
sh.show_object_outline = True
scene.render.resolution_x, scene.render.resolution_y = 1280, 720
scene.render.resolution_percentage = 100
scene.render.fps = FPS
scene.frame_start, scene.frame_end = A0, C1
scene.render.use_stamp = True
for k in ("use_stamp_date", "use_stamp_time", "use_stamp_render_time", "use_stamp_frame", "use_stamp_camera",
          "use_stamp_lens", "use_stamp_scene", "use_stamp_filename", "use_stamp_memory", "use_stamp_hostname"):
    if hasattr(scene.render, k):
        setattr(scene.render, k, False)
scene.render.use_stamp_note = True
scene.render.stamp_note_text = f"CA3000 3,000-seat auditorium concept | rev {rev} | CONCEPT - UNVERIFIED - NOT FOR CONSTRUCTION"
scene.render.stamp_font_size = 16

# video output (Blender 5.x uses media_type; older versions only file_format)
ims = scene.render.image_settings
if hasattr(ims, "media_type"):
    ims.media_type = "VIDEO"
ims.file_format = "FFMPEG"
ff = scene.render.ffmpeg
ff.format, ff.codec = "MPEG4", "H264"
ff.constant_rate_factor = "HIGH"
ff.ffmpeg_preset = "GOOD"
scene.render.filepath = str(OUT)

# visibility: documentation / zones never render; roof package hidden after the first orbit
CUT = ("ENV-ROOF", "ENV-WALL-GABLE", "STR-PURLIN", "STR-BRACE-ROOF", "ENV-FLASHING", "ENV-WALL-HALL-W-UPPER",
       "ENV-WALL-HALL-E-UPPER", "STR-BEAM-FOYROOF")
for o in list(scene.objects):
    if o.get("ifc_class") == "DOC" or o.users_collection[0].name.startswith(("60_", "50_SRV_Allowances")):
        o.hide_render = True
    elif o.name.startswith(CUT):
        o.hide_render = False
        o.keyframe_insert("hide_render", frame=A1)
        o.hide_render = True
        o.keyframe_insert("hide_render", frame=B0)
        if o.animation_data and o.animation_data.action:
            for fc in getattr(o.animation_data.action, "fcurves", []):
                for kp in fc.keyframe_points:
                    kp.interpolation = "CONSTANT"

# camera + target empty with track-to
target = bpy.data.objects.new("CAM_TARGET", None)
scene.collection.objects.link(target)
cd = bpy.data.cameras.new("CAM_VIDEO")
cd.lens, cd.clip_end = 30, 1000
cam = bpy.data.objects.new("CAM_VIDEO", cd)
scene.collection.objects.link(cam)
scene.camera = cam
con = cam.constraints.new("TRACK_TO")
con.target, con.track_axis, con.up_axis = target, "TRACK_NEGATIVE_Z", "UP_Y"


def key(frame, cam_loc, tgt_loc, lens=30):
    cam.location, target.location = cam_loc, tgt_loc
    cd.lens = lens
    cam.keyframe_insert("location", frame=frame)
    target.keyframe_insert("location", frame=frame)
    cd.keyframe_insert("lens", frame=frame)


def orbit(f0, f1, radius, height, start_deg, lens):
    for f in range(f0, f1 + 1):
        t = (f - f0) / (f1 - f0 + 1)
        ang = math.radians(start_deg + 360.0 * t)
        key(f, CENTER + Vector((radius * math.cos(ang), radius * math.sin(ang), height)), CENTER, lens)


orbit(A0, A1, 105.0, 45.0, 225.0, 30)
orbit(B0, B1, 90.0, 55.0, 225.0, 30)
# interior: rear platform -> over the seating towards the platform, looking at the stage
for f in range(C0, C1 + 1):
    t = (f - C0) / (C1 - C0)
    s = t * t * (3 - 2 * t)  # ease in/out
    loc = Vector((29.5, 15.0 + 41.0 * s, 8.0 - 3.5 * s))
    key(f, loc, Vector((29.5, 76.0, 2.0 + 0.5 * s)), 20)

if "--stills" in sys.argv:  # preview stills from each segment using the same animation setup
    if hasattr(ims, "media_type"):
        ims.media_type = "IMAGE"
    ims.file_format = "PNG"
    for fr in (75, 450, 720):
        scene.frame_set(fr)
        scene.render.filepath = str(OUT.parent / f"video_preview_f{fr:03d}.png")
        bpy.ops.render.render(write_still=True)
    print("STILLS done")
    raise SystemExit(0)
if "--test" in sys.argv:  # quick encoder check: a few frames from each segment boundary
    scene.frame_start, scene.frame_end = B0 - 1, B0 + 1
bpy.ops.render.render(animation=True)
print("VIDEO", OUT, OUT.is_file(), OUT.stat().st_size if OUT.is_file() else 0)
print("DONE - .blend not saved")
