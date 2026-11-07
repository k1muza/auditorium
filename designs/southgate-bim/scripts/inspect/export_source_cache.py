"""Export evaluated source geometry of the verified snapshot to a cache (read-only).

Every MESH / CURVE / FONT object is evaluated through the depsgraph (modifiers,
curve bevels and text are converted exactly as Blender displays them). Shared
mesh datablocks without modifiers are exported once and referenced, so that
instanced components (seats, bolts...) can become IFC types.

  blender -b --factory-startup <snapshot.blend> --python-exit-code 1 \
     --python scripts/inspect/export_source_cache.py -- --out work/source_cache.pkl
The .blend is never saved.
"""
import bpy, sys, pickle, argparse, hashlib, datetime
import numpy as np

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
ap = argparse.ArgumentParser()
ap.add_argument("--out", required=True)
args = ap.parse_args(argv)

dg = bpy.context.evaluated_depsgraph_get()
meshes = {}   # key -> {"verts": (n,3) float64 local, "faces": list[tuple]}
objects = {}


def mesh_arrays(me):
    n = len(me.vertices)
    co = np.empty(n * 3, dtype=np.float64)
    me.vertices.foreach_get("co", co)
    faces = [tuple(p.vertices) for p in me.polygons]
    return co.reshape(n, 3), faces


for ob in bpy.context.scene.objects:
    if ob.type not in ("MESH", "CURVE", "FONT"):
        continue
    shared = ob.type == "MESH" and not ob.modifiers and ob.data.users > 1
    key = ("DATA:" + ob.data.name) if shared else ("OBJ:" + ob.name)
    if key not in meshes:
        ev = ob.evaluated_get(dg)
        try:
            me = ev.to_mesh()
        except RuntimeError:
            me = None
        if me is None:
            continue
        v, f = mesh_arrays(me)
        ev.to_mesh_clear()
        h = hashlib.sha1(np.round(v, 5).tobytes() + repr(f).encode()).hexdigest()[:16]
        meshes[key] = {"verts": v, "faces": f, "hash": h}
    objects[ob.name] = {"mesh": key, "matrix": np.array(ob.matrix_world, dtype=np.float64),
                        "type": ob.type, "shared": shared,
                        "materials": [s.material.name for s in ob.material_slots if s.material]}

mats = {}
for m in bpy.data.materials:
    c = list(m.diffuse_color)
    try:
        if m.use_nodes and m.node_tree:
            for n in m.node_tree.nodes:
                if n.type == "BSDF_PRINCIPLED":
                    c = list(n.inputs["Base Color"].default_value)
                    a = n.inputs["Alpha"].default_value
                    c[3] = a
                    break
    except Exception:
        pass
    mats[m.name] = {"rgba": [round(x, 4) for x in c]}

with open(args.out, "wb") as fh:
    pickle.dump({"schema": "southgate_bim.source_cache/1",
                 "generated": datetime.datetime.now().isoformat(timespec="seconds"),
                 "source_file": bpy.data.filepath, "meshes": meshes, "objects": objects,
                 "materials": mats}, fh, protocol=4)
print("CACHE_OK", len(objects), "objects", len(meshes), "meshes", args.out)
