"""
extract_model.py — export the concept model to the JSON files the document template consumes.

Run inside Blender (tested against the PL06 naming conventions):
    blender church_3000_concept_PL06.blend --background --python tools/extract_model.py -- --out model/

Writes
    model/model.json       objects[] {n, mn, mx, a?, b?, v?}, empties[] — world-space metres
    model/properties.json  { "OB:<name>": {...custom props}, "SC:<scene>": {...scene props} }

These two files are the only inputs to tools/generate-drawings.js and to the data build
(see HANDOFF.md §5). Nothing here interprets engineering meaning; it only measures.
"""
import bpy, json, sys, os, math
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
out_dir = argv[argv.index("--out") + 1] if "--out" in argv else "model"
os.makedirs(out_dir, exist_ok=True)

R = lambda v: round(float(v), 3)
SKIP_VERTS = ("SEAT-", "ZONE-AISLE", "SRV-LIGHT", "LBL")   # bbox is enough for these
MAX_VERTS = 400

def props_of(idb):
    out = {}
    for k in idb.keys():
        if k.startswith("_"):
            continue
        v = idb[k]
        if hasattr(v, "to_dict"):
            v = v.to_dict()
        elif hasattr(v, "to_list"):
            v = v.to_list()
        if isinstance(v, str) and v.startswith("{"):
            try:
                out.update(json.loads(v)); continue
            except ValueError:
                pass
        out[k] = v
    return out

objects, empties, props = [], [], {}
for ob in bpy.data.objects:
    p = props_of(ob)
    if p:
        props["OB:" + ob.name] = p
    if ob.type != "MESH":
        empties.append({"n": ob.name, "l": [R(c) for c in ob.matrix_world.translation], "type": ob.type})
        continue
    mw = ob.matrix_world
    V = [mw @ v.co for v in ob.data.vertices]
    if not V:
        continue
    mn = [R(min(v[i] for v in V)) for i in range(3)]
    mx = [R(max(v[i] for v in V)) for i in range(3)]
    e = {"n": ob.name, "mn": mn, "mx": mx}
    if ob.name.startswith("STR-") and len(V) <= 64:
        # member end points: farthest vertex pair, thin axes collapsed to the bbox centre
        best, A, B = -1, V[0], V[0]
        for i in range(len(V)):
            for j in range(i + 1, len(V)):
                d = (V[i] - V[j]).length_squared
                if d > best:
                    best, A, B = d, V[i], V[j]
        A, B = list(A), list(B)
        if not ob.name.startswith("STR-FTG"):
            for k in range(3):
                if mx[k] - mn[k] < 0.8:
                    c = (mx[k] + mn[k]) / 2
                    A[k] = B[k] = c
        e["a"], e["b"] = [R(c) for c in A], [R(c) for c in B]
    if not ob.name.startswith(SKIP_VERTS) and len(V) <= MAX_VERTS:
        e["v"] = [[R(c) for c in v] for v in V]
    objects.append(e)

for sc in bpy.data.scenes:
    p = props_of(sc)
    if p:
        props["SC:" + sc.name] = p

src = os.path.basename(bpy.data.filepath)
with open(os.path.join(out_dir, "model.json"), "w") as f:
    json.dump({"source": src, "units": "m", "objects": objects, "empties": empties}, f, separators=(",", ":"))
with open(os.path.join(out_dir, "properties.json"), "w") as f:
    json.dump(props, f, separators=(",", ":"))
print(f"extract_model: {len(objects)} meshes, {len(empties)} other objects, {len(props)} property sets -> {out_dir}")
