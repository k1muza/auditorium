"""Read-only inventory of the verified source snapshot.

Run (never saves the .blend):
  blender -b --factory-startup <snapshot.blend> --python-exit-code 1 \
      --python scripts/inspect/inventory_source.py -- --out source/geometry_inventory.json
"""
import bpy, bmesh, json, sys, math, hashlib, argparse, datetime
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
ap = argparse.ArgumentParser()
ap.add_argument("--out", required=True)
args = ap.parse_args(argv)

scene = bpy.context.scene
vl = bpy.context.view_layer


def r(v, n=4):
    return round(float(v), n)


def layer_collection_map():
    out = {}

    def walk(lc, excluded, hidden, path):
        ex = excluded or lc.exclude
        hd = hidden or lc.hide_viewport or lc.collection.hide_viewport
        out[lc.collection.name] = {"excluded": ex, "hidden": hd, "path": path + [lc.collection.name],
                                   "hide_render": lc.collection.hide_render}
        for c in lc.children:
            walk(c, ex, hd, path + [lc.collection.name])

    for c in vl.layer_collection.children:
        walk(c, False, False, [])
    return out


LC = layer_collection_map()


def custom_props(idb):
    d = {}
    for k in idb.keys():
        if k.startswith("_") or k in ("cycles",):
            continue
        v = idb[k]
        if isinstance(v, (int, float, str, bool)):
            d[k] = v
        else:
            try:
                d[k] = list(v)
            except Exception:
                d[k] = str(v)
    return d


def mesh_stats(ob):
    me = ob.data
    bm = bmesh.new()
    bm.from_mesh(me)
    nv, nf, ne = len(bm.verts), len(bm.faces), len(bm.edges)
    manifold = all(e.is_manifold for e in bm.edges) if ne else False
    # world-space measures (scale applied)
    bm.transform(ob.matrix_world)
    area = sum(f.calc_area() for f in bm.faces)
    vol = abs(bm.calc_volume(signed=True)) if manifold else None
    quads = sum(1 for f in bm.faces if len(f.verts) == 4)
    # box test: 8 verts, 6 quads, every edge parallel to one of 3 mutually orthogonal axes
    is_box = False
    axes = None
    if nv == 8 and nf == 6 and quads == 6 and manifold:
        bm.verts.ensure_lookup_table()
        v0 = bm.verts[0]
        dirs = [(e.other_vert(v0).co - v0.co) for e in v0.link_edges]
        if len(dirs) == 3:
            ok = all(abs(dirs[i].normalized().dot(dirs[j].normalized())) < 1e-3
                     for i in range(3) for j in range(i + 1, 3))
            if ok:
                is_box = True
                axes = {"origin": [r(c) for c in v0.co],
                        "edges": [[r(c) for c in d] for d in dirs]}
    bm.free()
    return {"verts": nv, "faces": nf, "edges": ne, "manifold": manifold,
            "area_m2": r(area, 5), "volume_m3": (r(vol, 6) if vol is not None else None),
            "is_box": is_box, "box": axes, "data_users": me.users}


objs = []
for ob in sorted(scene.objects, key=lambda o: o.name):
    cols = [c.name for c in ob.users_collection]
    col_vis = [LC.get(c, {}) for c in cols]
    excluded = all(cv.get("excluded", False) for cv in col_vis) if col_vis else False
    col_hidden = all(cv.get("hidden", False) for cv in col_vis) if col_vis else False
    try:
        visible = ob.visible_get()
    except Exception:
        visible = None
    mw = ob.matrix_world
    bb = [mw @ Vector(c) for c in ob.bound_box]
    mn = [min(p[i] for p in bb) for i in range(3)]
    mx = [max(p[i] for p in bb) for i in range(3)]
    loc, rot, sca = mw.decompose()
    e = {
        "name": ob.name, "type": ob.type, "data": ob.data.name if ob.data else None,
        "parent": ob.parent.name if ob.parent else None,
        "collections": cols,
        "collection_paths": [LC.get(c, {}).get("path", [c]) for c in cols],
        "hide_viewport": ob.hide_viewport, "hide_render": ob.hide_render,
        "hide_in_view_layer": ob.hide_get() if not excluded else None,
        "collection_excluded": excluded, "collection_hidden": col_hidden,
        "visible": visible,
        "location": [r(c) for c in loc],
        "rotation_euler_deg": [r(math.degrees(a), 3) for a in mw.to_euler()],
        "scale": [r(c) for c in sca],
        "dimensions": [r(c) for c in ob.dimensions],
        "aabb_min": [r(c) for c in mn], "aabb_max": [r(c) for c in mx],
        "materials": [s.material.name for s in getattr(ob, "material_slots", []) if s.material],
        "props": custom_props(ob),
        "instance_collection": ob.instance_collection.name if ob.instance_type == "COLLECTION" and ob.instance_collection else None,
        "modifiers": [m.type for m in getattr(ob, "modifiers", [])],
    }
    if ob.type == "MESH":
        e["mesh"] = mesh_stats(ob)
    elif ob.type == "CAMERA":
        e["camera"] = {"lens": r(ob.data.lens), "type": ob.data.type, "ortho_scale": r(ob.data.ortho_scale),
                       "sensor_width": r(ob.data.sensor_width), "clip": [r(ob.data.clip_start), r(ob.data.clip_end)],
                       "matrix_world": [[r(c, 6) for c in row] for row in mw]}
    elif ob.type == "LIGHT":
        e["light"] = {"type": ob.data.type, "energy": r(ob.data.energy)}
    elif ob.type in ("CURVE", "FONT"):
        e["curve"] = {"bevel_depth": r(getattr(ob.data, "bevel_depth", 0)), "extrude": r(getattr(ob.data, "extrude", 0)),
                      "body": getattr(ob.data, "body", None)}
    objs.append(e)

collections = {name: dict(v, objects=len(bpy.data.collections[name].objects) if name in bpy.data.collections else 0)
               for name, v in LC.items()}

out = {
    "schema": "southgate_bim.geometry_inventory/1",
    "generated": datetime.datetime.now().isoformat(timespec="seconds"),
    "source_file": bpy.data.filepath,
    "is_dirty": bpy.data.is_dirty,
    "blender_version": bpy.app.version_string,
    "scene": scene.name,
    "scene_props": custom_props(scene),
    "unit_system": scene.unit_settings.system, "unit_scale": scene.unit_settings.scale_length,
    "object_count": len(objs),
    "collections": collections,
    "objects": objs,
}
with open(args.out, "w", encoding="utf-8") as f:
    json.dump(out, f, indent=1)
print("INVENTORY_OK", len(objs), args.out)
