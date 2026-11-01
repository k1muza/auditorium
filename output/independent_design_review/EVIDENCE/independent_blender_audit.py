"""Read-only evidence extraction for the CA3000 independent design review."""

import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

import bpy
from mathutils import Vector

OUT = Path(__file__).resolve().parent
BLEND = Path(bpy.data.filepath).resolve()
scene = bpy.context.scene
objects = list(scene.objects)
model_objects = [o for o in objects if o.get("ifc_class")]


def bbox(obj):
    pts = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    return ([min(p[i] for p in pts) for i in range(3)],
            [max(p[i] for p in pts) for i in range(3)])


def jprop(obj, name):
    return json.loads(obj[name]) if obj.get(name) else None


all_points = [p for o in model_objects for p in [o.matrix_world @ Vector(c) for c in o.bound_box]]
extents = [min(p.x for p in all_points), min(p.y for p in all_points), min(p.z for p in all_points),
           max(p.x for p in all_points), max(p.y for p in all_points), max(p.z for p in all_points)]

columns = [o for o in model_objects if o.get("ifc_class") == "IfcColumn"]
footings = [o for o in model_objects if o.get("ifc_class") == "IfcFooting"]
support_pairs = []
for col in columns:
    cp = col.matrix_world.translation.xy
    ftg = min(footings, key=lambda f: (cp - f.matrix_world.translation.xy).length)
    cmin, _ = bbox(col)
    _, fmax = bbox(ftg)
    support_pairs.append({
        "column": col.name,
        "footing": ftg.name,
        "xy_offset_m": round((cp - ftg.matrix_world.translation.xy).length, 6),
        "vertical_gap_m": round(cmin[2] - fmax[2], 6),
    })

assemblies = defaultdict(list)
for obj in model_objects:
    if str(obj.get("assembly", "")).startswith("STR-TRUSS-"):
        assemblies[obj["assembly"]].append(obj)
truss_topology = []
for name, members in sorted(assemblies.items()):
    points = []
    for member in members:
        s = jprop(member, "strut_json")
        if s:
            points.extend([Vector(s[0]), Vector(s[1])])
    isolated = []
    for i, p in enumerate(points):
        joined = any((p - q).length <= 0.002 for k, q in enumerate(points) if k != i)
        bearing = abs(p.z - 14.0) <= 0.002 and (abs(p.x - 4.5) <= 0.002 or abs(p.x - 54.5) <= 0.002)
        if not joined and not bearing:
            isolated.append([round(v, 4) for v in p])
    truss_topology.append({"assembly": name, "members": len(members), "isolated_nonbearing_endpoints": isolated})

pulpit = Vector((29.5, 65.6))
angles = []
for obj in model_objects:
    if obj.name.startswith("SEAT-C-"):
        p = obj.matrix_world.translation
        angle = math.degrees(math.atan2(abs(p.x - pulpit.x), pulpit.y - p.y))
        angles.append({"seat_id": obj.name, "x_m": round(p.x, 4), "y_m": round(p.y, 4),
                       "z_floor_m": round(p.z, 4), "off_axis_to_pulpit_deg": round(angle, 2),
                       "plan_distance_to_pulpit_m": round(math.hypot(p.x - pulpit.x, pulpit.y - p.y), 2)})
angles.sort(key=lambda r: r["off_axis_to_pulpit_deg"], reverse=True)
with (OUT / "sightline_off_axis_samples.csv").open("w", newline="", encoding="utf-8") as handle:
    writer = csv.DictWriter(handle, fieldnames=list(angles[0]))
    writer.writeheader()
    writer.writerows(angles)

keywords = ("GUTTER", "DOWNPIPE", "DRAIN", "ACOUST", "DUCT", "DIFFUSER", "SPRINK",
            "DETECTOR", "EXIT-SIGN", "EMERGENCY-LIGHT", "LIGHTNING")
ifc_counts = Counter(f"{o.get('ifc_class')}:{o.get('predefined_type', '')}" for o in model_objects)
report = {
    "method": "Independent bpy read; source blend not saved",
    "blend_file": str(BLEND),
    "blend_sha256": hashlib.sha256(BLEND.read_bytes()).hexdigest(),
    "blender_version": bpy.app.version_string,
    "scene_revision": scene.get("revision"),
    "units": {"system": scene.unit_settings.system, "scale_length": scene.unit_settings.scale_length,
              "length_unit": scene.unit_settings.length_unit},
    "counts": {"scene_objects_including_documentation": len(objects),
               "model_objects_with_ifc_class": len(model_objects), "by_ifc_class": dict(sorted(ifc_counts.items()))},
    "model_extents_m": [round(v, 4) for v in extents],
    "column_foundation_coordination": {"columns": len(columns), "footings": len(footings),
        "max_xy_offset_m": max(r["xy_offset_m"] for r in support_pairs),
        "max_abs_vertical_gap_m": max(abs(r["vertical_gap_m"]) for r in support_pairs), "pairs": support_pairs},
    "truss_topology": truss_topology,
    "sightline_off_axis": {"seat_count": len(angles), "modelled_pulpit_xy_m": list(pulpit),
        "count_over_45_deg": sum(r["off_axis_to_pulpit_deg"] > 45 for r in angles),
        "count_over_60_deg": sum(r["off_axis_to_pulpit_deg"] > 60 for r in angles),
        "count_over_70_deg": sum(r["off_axis_to_pulpit_deg"] > 70 for r in angles), "maximum": angles[0],
        "note": "Geometric diagnostic, not a statutory acceptance test."},
    "represented_system_keyword_hits": {k: sum(k in o.name.upper() for o in model_objects) for k in keywords},
}
(OUT / "independent_model_audit.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps({"output": str(OUT / "independent_model_audit.json"), "sightline": report["sightline_off_axis"]}))
