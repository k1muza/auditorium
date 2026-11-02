"""Blender builder for the 3,000-seat auditorium coordination concept.

Run headless (no Blender MCP needed):
  blender --background --factory-startup --python scripts/build_auditorium.py -- \
      --config config/auditorium_params.json --out model/church_3000_concept.blend \
      --manifest model/blender_manifest.json --revision IT01-xxxx [--render exports]

Creates the scene from scripts/auditorium_layout.py, saves the .blend, then exports a
manifest by READING BACK the Blender objects (mesh data, world matrices, custom
properties). The IFC exporter and the drawings consume that manifest, so they are
derived from the Blender model rather than from a parallel data path.
"""
import argparse
import hashlib
import json
import math
import sys
import time
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import auditorium_layout as al  # noqa: E402

GROUPS = {
    "00": "00_DOC_Grid_Levels", "10": "10_ENV_Envelope_Group", "20": "20_ARC_Architecture",
    "30": "30_STR_Structure", "40": "40_SEAT_Seating", "50": "50_SRV_Service_Allowances",
    "60": "60_ZONE_Spaces_Circulation",
}
COLOURS = {
    "10_ENV_Envelope": (0.80, 0.78, 0.72, 1.0), "20_ARC_Floors": (0.70, 0.70, 0.68, 1.0),
    "20_ARC_Walls": (0.90, 0.88, 0.82, 1.0), "20_ARC_Circulation": (0.95, 0.75, 0.30, 1.0),
    "20_ARC_Furniture": (0.55, 0.35, 0.20, 1.0), "30_STR_Columns": (0.80, 0.20, 0.20, 1.0),
    "30_STR_Foundations": (0.45, 0.45, 0.45, 1.0), "30_STR_Roof_Trusses": (0.85, 0.30, 0.25, 1.0),
    "30_STR_Bracing": (0.95, 0.55, 0.10, 1.0), "30_STR_Beams": (0.70, 0.25, 0.25, 1.0),
    "40_SEAT_Congregation": (0.15, 0.35, 0.75, 1.0), "40_SEAT_Choir": (0.55, 0.20, 0.65, 1.0),
    "40_SEAT_Companion": (0.10, 0.65, 0.55, 1.0), "40_SEAT_Accessible": (0.10, 0.75, 0.30, 1.0),
    "50_SRV_Allowances": (0.20, 0.80, 0.90, 1.0), "60_ZONE_Spaces": (0.6, 0.9, 0.6, 1.0),
    "50_SRV_AV": (0.12, 0.12, 0.14, 1.0), "50_SRV_Drainage": (0.35, 0.40, 0.45, 1.0), "50_SRV_Lighting": (1.0, 0.85, 0.2, 1.0),
    "60_ZONE_Aisles": (1.0, 0.95, 0.4, 1.0), "00_DOC_Grid": (0.3, 0.3, 0.3, 1.0),
}
WIRE_COLLECTIONS = {"60_ZONE_Spaces", "60_ZONE_Aisles", "50_SRV_Allowances"}


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(al.DEFAULT_CONFIG))
    ap.add_argument("--out", required=True)
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--revision", required=True)
    ap.add_argument("--render", default=None, help="directory for workbench renders (optional)")
    return ap.parse_args(argv)


def get_collection(name, scene):
    if name in bpy.data.collections:
        return bpy.data.collections[name]
    parent_name = GROUPS[name[:2]]
    if parent_name not in bpy.data.collections:
        parent = bpy.data.collections.new(parent_name)
        scene.collection.children.link(parent)
    parent = bpy.data.collections[parent_name]
    col = bpy.data.collections.new(name)
    parent.children.link(col)
    return col


def get_material(col_name):
    name = f"MAT_{col_name}"
    if name in bpy.data.materials:
        return bpy.data.materials[name]
    m = bpy.data.materials.new(name)
    rgba = COLOURS.get(col_name, (0.7, 0.7, 0.7, 1.0))
    m.diffuse_color = rgba
    return m


def build(params, revision):
    t0 = time.time()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.name = "CA3000_Concept"
    us = scene.unit_settings
    us.system, us.scale_length, us.length_unit = "METRIC", 1.0, "METERS"
    lay = al.compute(params)
    shared = {}
    for key, (verts, faces) in al.INSTANCE_MESHES.items():
        me = bpy.data.meshes.new(f"MESH_SHARED_{key}")
        me.from_pydata(verts, [], faces)
        me.update()
        shared[key] = me
    for el in lay.elements:
        col = get_collection(el.collection, scene)
        if el.mesh_key:
            me = shared[el.mesh_key]
        else:
            verts, faces = el.local_mesh()
            me = bpy.data.meshes.new(f"MESH_{el.name}")
            me.from_pydata(verts, [], faces)
            me.update()
            if not me.materials:
                me.materials.append(get_material(el.collection))
        ob = bpy.data.objects.new(el.name, me)
        ob.location = el.origin
        ob.rotation_euler = (0.0, 0.0, math.radians(el.rot_z))
        ob.color = COLOURS.get(el.collection, (0.7, 0.7, 0.7, 1.0))
        ob["ifc_class"] = el.ifc_class
        ob["predefined_type"] = el.predefined or ""
        ob["storey"] = el.storey
        ob["object_type"] = el.object_type or ""
        ob["assembly"] = el.assembly or ""
        ob["kind"] = el.kind
        ob["props_json"] = json.dumps(el.props, sort_keys=True, default=str)
        if el.strut:
            ob["strut_json"] = json.dumps([list(el.strut[0]), list(el.strut[1]), el.strut[2]])
        if el.host:
            ob["host"] = el.host
            ob["opening_json"] = json.dumps([al.rnd(v, 5) for v in el.opening])
        if el.collection in WIRE_COLLECTIONS:
            ob.display_type = "WIRE"
            ob.hide_render = True
        col.objects.link(ob)
    for me in shared.values():
        me.materials.append(get_material("40_SEAT_Congregation"))
    build_grid_doc(lay, scene)
    scene["revision"] = revision
    scene["schema_version"] = al.SCHEMA_VERSION
    scene["status"] = params["project"]["status_label"]
    scene["levels_json"] = json.dumps(lay.levels())
    scene["grid_json"] = json.dumps(params["grid"])
    scene["metrics_json"] = json.dumps(lay.metrics, default=str)
    return lay, time.time() - t0


def build_grid_doc(lay, scene):
    """Grid lines (edge meshes) and text labels in 00_DOC_Grid; levels as text markers."""
    col = get_collection("00_DOC_Grid", scene)
    gx, gy = lay.gx, lay.gy
    ext = 6.0
    xmin, xmax = min(gx.values()) - ext, max(gx.values()) + ext
    ymin, ymax = min(gy.values()) - ext, max(gy.values()) + ext
    lines = [(f"GRID-{k}", (v, ymin, 0.0), (v, ymax, 0.0)) for k, v in gx.items()]
    lines += [(f"GRID-{k}", (xmin, v, 0.0), (xmax, v, 0.0)) for k, v in gy.items()]
    for name, p0, p1 in lines:
        me = bpy.data.meshes.new(f"MESH_{name}")
        me.from_pydata([p0, p1], [(0, 1)], [])
        ob = bpy.data.objects.new(name, me)
        ob["ifc_class"] = "DOC"
        col.objects.link(ob)
        label = name.split("-")[1]
        for end in (p0, p1):
            cu = bpy.data.curves.new(f"TXT_{name}_{end[0]:.0f}_{end[1]:.0f}", "FONT")
            cu.body = label
            cu.size = 2.0
            cu.align_x, cu.align_y = "CENTER", "CENTER"
            t = bpy.data.objects.new(f"LBL-{name}-{'S' if end is p0 else 'E'}", cu)
            t.location = end
            t["ifc_class"] = "DOC"
            col.objects.link(t)
    for lv in lay.levels():
        cu = bpy.data.curves.new(f"TXT_{lv['id']}", "FONT")
        cu.body = f"{lv['id']} {lv['elevation']:+.3f}"
        cu.size = 1.2
        t = bpy.data.objects.new(f"LVL-{lv['id']}", cu)
        t.location = (xmax + 2.0, ymin, lv["elevation"])
        t.rotation_euler = (math.radians(90), 0, 0)
        t["ifc_class"] = "DOC"
        col.objects.link(t)


def export_manifest(path, params, revision):
    """Read the scene back and write geometry + semantics for IFC export and drawings."""
    scene = bpy.context.scene
    bpy.context.view_layer.update()  # matrix_world is stale for objects created via bpy.data until evaluated
    meshes, objects = {}, []
    for ob in sorted(scene.objects, key=lambda o: o.name):
        if ob.type != "MESH" or ob.get("ifc_class") in (None, "DOC"):
            continue
        me = ob.data
        if me.name not in meshes:
            meshes[me.name] = {
                "verts": [[round(v.co.x, 5), round(v.co.y, 5), round(v.co.z, 5)] for v in me.vertices],
                "faces": [list(p.vertices) for p in me.polygons],
                "users": 0,
            }
        meshes[me.name]["users"] += 1
        mw = ob.matrix_world
        objects.append({
            "name": ob.name,
            "collection": ob.users_collection[0].name,
            "ifc_class": ob["ifc_class"],
            "predefined_type": ob.get("predefined_type", ""),
            "object_type": ob.get("object_type", ""),
            "storey": ob.get("storey", "L00"),
            "assembly": ob.get("assembly", ""),
            "kind": ob.get("kind", "solid"),
            "props": json.loads(ob.get("props_json", "{}")),
            "strut": json.loads(ob["strut_json"]) if "strut_json" in ob else None,
            "host": ob.get("host"),
            "opening": json.loads(ob["opening_json"]) if "opening_json" in ob else None,
            "mesh": me.name,
            "matrix": [[round(mw[i][j], 6) + 0.0 for j in range(4)] for i in range(4)],
        })
    manifest = {
        "schema": "ca3000-blender-manifest-1",
        "revision": revision,
        "blender_version": bpy.app.version_string,
        "units": {"system": scene.unit_settings.system, "scale_length": scene.unit_settings.scale_length,
                  "length_unit": scene.unit_settings.length_unit},
        "project": params["project"],
        "levels": json.loads(scene["levels_json"]),
        "grid": json.loads(scene["grid_json"]),
        "metrics": json.loads(scene["metrics_json"]),
        "meshes": meshes,
        "objects": objects,
    }
    text = json.dumps(manifest, sort_keys=True, separators=(",", ":"))
    Path(path).write_text(text, encoding="utf-8")
    return hashlib.sha256(text.encode("utf-8")).hexdigest(), len(objects), len(meshes)


def render(outdir, revision):
    """Workbench renders of the actual Blender scene (axonometric + roof-off cutaway)."""
    scene = bpy.context.scene
    outdir = Path(outdir).resolve()
    outdir.mkdir(parents=True, exist_ok=True)
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.shading.light = "STUDIO"
    scene.display.shading.color_type = "OBJECT"
    scene.display.shading.show_cavity = True
    scene.render.resolution_x, scene.render.resolution_y = 1800, 1100
    scene.render.film_transparent = False
    scene.world = scene.world or bpy.data.worlds.new("World")
    cam_data = bpy.data.cameras.new("CAM_AXO")
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = 125.0
    cam = bpy.data.objects.new("CAM_AXO", cam_data)
    scene.collection.objects.link(cam)
    target = Vector((29.5, 44.0, 4.0))
    cam.location = target + Vector((-95.0, -110.0, 95.0))
    cam.rotation_euler = (target - cam.location).to_track_quat("-Z", "Y").to_euler()
    scene.camera = cam
    hidden = []
    for ob in scene.objects:
        if ob.get("ifc_class") == "DOC" and ob.type == "FONT":
            ob.hide_render = True
    results = {}
    scene.render.filepath = str(outdir / "model_axonometric.png")
    bpy.ops.render.render(write_still=True)
    results["model_axonometric.png"] = (outdir / "model_axonometric.png").is_file()
    # cutaway: hide roofs, trusses' purlins and gable infill to show seating and structure
    for ob in scene.objects:
        if (ob.name.startswith("ENV-ROOF") or ob.name.startswith("ENV-WALL-GABLE") or ob.name.startswith("STR-PURLIN")
                or ob.name.startswith("STR-BRACE-ROOF") or ob.name.startswith("ENV-WALL-HALL-W")
                or ob.name.startswith("ENV-WALL-EXT-W") or ob.name.startswith("STR-BEAM-FOYROOF")):
            if not ob.hide_render:
                ob.hide_render = True
                hidden.append(ob)
    scene.render.filepath = str(outdir / "model_cutaway.png")
    bpy.ops.render.render(write_still=True)
    results["model_cutaway.png"] = (outdir / "model_cutaway.png").is_file()
    for ob in hidden:
        ob.hide_render = False
    bpy.data.objects.remove(cam)
    return results


def main():
    args = parse_args()
    params = al.load_params(args.config)
    lay, dt = build(params, args.revision)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    sha, n_obj, n_mesh = export_manifest(args.manifest, params, args.revision)
    renders = {}
    if args.render:
        try:
            renders = render(args.render, args.revision)
        except Exception as exc:  # report truthfully, keep the model build
            renders = {"error": repr(exc)}
    bpy.ops.wm.save_as_mainfile(filepath=str(out.resolve()), compress=True)
    seats = len(bpy.data.collections["40_SEAT_Congregation"].objects)
    summary = {"revision": args.revision, "blender": bpy.app.version_string, "blend": str(out),
               "objects_exported": n_obj, "unique_meshes": n_mesh, "manifest_sha256": sha,
               "congregation_seats_in_scene": seats, "build_seconds": round(dt, 2), "renders": renders,
               "total_scene_objects": len(bpy.context.scene.objects)}
    print("BUILD_SUMMARY " + json.dumps(summary))


if __name__ == "__main__":
    main()
