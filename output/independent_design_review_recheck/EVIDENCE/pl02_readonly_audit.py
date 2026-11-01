"""Independent, read-only PL02 model audit for the follow-up design review."""

import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

import bpy
from mathutils import Vector


OUT = Path(__file__).resolve().with_name("pl02_readonly_audit.json")
BLEND = Path(bpy.data.filepath).resolve()
SCENE = bpy.context.scene
OBJECTS = list(SCENE.objects)
MODEL = [obj for obj in OBJECTS if obj.get("ifc_class")]


def bbox_world(obj):
    points = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    return (
        Vector(tuple(min(p[i] for p in points) for i in range(3))),
        Vector(tuple(max(p[i] for p in points) for i in range(3))),
    )


def serial_props(obj):
    result = {}
    for key in obj.keys():
        if key == "_RNA_UI":
            continue
        value = obj[key]
        if isinstance(value, (str, int, float, bool)) or value is None:
            result[key] = value
        else:
            try:
                result[key] = list(value)
            except TypeError:
                result[key] = str(value)
    return result


def expanded_props(obj):
    result = serial_props(obj)
    packed = result.get("props_json")
    if isinstance(packed, str):
        try:
            result.update(json.loads(packed))
        except json.JSONDecodeError:
            pass
    return result


def named(prefix):
    return [obj for obj in MODEL if obj.name.upper().startswith(prefix.upper())]


def hits(*terms):
    upper = tuple(term.upper() for term in terms)
    return [obj for obj in MODEL if any(term in obj.name.upper() for term in upper)]


columns = [obj for obj in MODEL if obj.get("ifc_class") == "IfcColumn"]
footings = [obj for obj in MODEL if obj.get("ifc_class") == "IfcFooting"]
support_rows = []
for column in columns:
    cxy = column.matrix_world.translation.xy
    footing = min(footings, key=lambda item: (item.matrix_world.translation.xy - cxy).length)
    cmin, _ = bbox_world(column)
    _, fmax = bbox_world(footing)
    support_rows.append(
        {
            "column": column.name,
            "footing": footing.name,
            "xy_offset_m": round((footing.matrix_world.translation.xy - cxy).length, 6),
            "vertical_gap_m": round(cmin.z - fmax.z, 6),
        }
    )

truss_assemblies = defaultdict(list)
for obj in MODEL:
    assembly = str(obj.get("assembly", ""))
    if assembly.startswith("STR-TRUSS-"):
        truss_assemblies[assembly].append(obj)
truss_topology = []
for assembly, members in sorted(truss_assemblies.items()):
    endpoints = []
    for member in members:
        packed = member.get("strut_json")
        if not packed:
            continue
        definition = json.loads(packed)
        endpoints.extend((Vector(definition[0]), Vector(definition[1])))
    isolated = []
    for index, point in enumerate(endpoints):
        joined = any((point - other).length <= 0.002 for other_index, other in enumerate(endpoints) if index != other_index)
        bearing = abs(point.z - 14.0) <= 0.002 and (abs(point.x - 4.5) <= 0.002 or abs(point.x - 54.5) <= 0.002)
        if not joined and not bearing:
            isolated.append([round(value, 4) for value in point])
    truss_topology.append(
        {"assembly": assembly, "members": len(members), "isolated_nonbearing_endpoints": isolated}
    )

chairs = [obj for obj in MODEL if obj.get("ifc_class") == "IfcFurniture" and obj.name.startswith("SEAT-C-")]
pulpit = Vector((29.5, 65.6))
angles = []
for chair in chairs:
    point = chair.matrix_world.translation
    angle = math.degrees(math.atan2(abs(point.x - pulpit.x), pulpit.y - point.y))
    angles.append((angle, chair.name, point.x, point.y, point.z))
angles.sort(reverse=True)

doors = [obj for obj in MODEL if obj.get("ifc_class") == "IfcDoor"]
fire_exit_doors = [obj for obj in doors if bool(expanded_props(obj).get("FireExit"))]
wheelchairs = hits("ACC-WCS-")
screens = [obj for obj in MODEL if obj.get("ifc_class") == "IfcAudioVisualAppliance" and obj.get("predefined_type") == "DISPLAY"]
speakers = [obj for obj in MODEL if obj.get("ifc_class") == "IfcAudioVisualAppliance" and obj.get("predefined_type") == "SPEAKER"]
ramps = [obj for obj in MODEL if obj.get("ifc_class") == "IfcRamp"]

ifc_counts = Counter(str(obj.get("ifc_class")) for obj in MODEL)
keywords = (
    "GUTTER",
    "DOWNPIPE",
    "DRAIN",
    "ACOUST",
    "DUCT",
    "DIFFUSER",
    "AIR-HANDLING",
    "SPRINK",
    "DETECTOR",
    "EXIT-SIGN",
    "EMERGENCY-LIGHT",
    "LIGHTNING",
    "ROOF-WALK",
    "LADDER",
    "FALL-ARREST",
    "ACCESS-HATCH",
    "SANITARY-FIXTURE",
)

all_points = [obj.matrix_world @ Vector(corner) for obj in MODEL for corner in obj.bound_box]
report = {
    "method": "Fresh independent bpy inspection; opened authoritative blend read-only and did not save it",
    "blend_file": str(BLEND),
    "blend_sha256": hashlib.sha256(BLEND.read_bytes()).hexdigest(),
    "blender_version": bpy.app.version_string,
    "scene_revision": SCENE.get("revision"),
    "units": {
        "system": SCENE.unit_settings.system,
        "scale_length": SCENE.unit_settings.scale_length,
        "length_unit": SCENE.unit_settings.length_unit,
    },
    "counts": {
        "scene_objects": len(OBJECTS),
        "model_objects": len(MODEL),
        "by_ifc_class": dict(sorted(ifc_counts.items())),
        "congregation_seats": len(chairs),
        "wheelchair_objects_named": len(wheelchairs),
        "screens": len(screens),
        "speakers": len(speakers),
        "doors": len(doors),
        "fire_exit_doors": len(fire_exit_doors),
        "ramps": len(ramps),
    },
    "model_extents_m": [
        round(min(p.x for p in all_points), 4),
        round(min(p.y for p in all_points), 4),
        round(min(p.z for p in all_points), 4),
        round(max(p.x for p in all_points), 4),
        round(max(p.y for p in all_points), 4),
        round(max(p.z for p in all_points), 4),
    ],
    "column_foundation_coordination": {
        "columns": len(columns),
        "footings": len(footings),
        "max_xy_offset_m": max(row["xy_offset_m"] for row in support_rows),
        "max_abs_vertical_gap_m": max(abs(row["vertical_gap_m"]) for row in support_rows),
        "unmatched_or_misaligned": [
            row for row in support_rows if row["xy_offset_m"] > 0.001 or abs(row["vertical_gap_m"]) > 0.001
        ],
    },
    "primary_truss_topology": truss_topology,
    "sightline_off_axis": {
        "over_45_deg": sum(item[0] > 45.0 for item in angles),
        "over_60_deg": sum(item[0] > 60.0 for item in angles),
        "over_70_deg": sum(item[0] > 70.0 for item in angles),
        "worst": {
            "angle_deg": round(angles[0][0], 2),
            "seat": angles[0][1],
            "position_m": [round(v, 3) for v in angles[0][2:]],
        },
    },
    "wheelchair_name_groups": dict(sorted(Counter(obj.name.split("-")[2] if len(obj.name.split("-")) > 2 else "UNKNOWN" for obj in wheelchairs).items())),
    "door_property_coverage": {
        "fire_exit_true": len(fire_exit_doors),
        "outward_opening_or_direction_property": sum(
            any("outward" in str(value).lower() for value in expanded_props(obj).values())
            or any("direction" in key.lower() for key in expanded_props(obj))
            for obj in fire_exit_doors
        ),
        "panic_property_or_value": sum(
            any("panic" in key.lower() or "panic" in str(value).lower() for key, value in expanded_props(obj).items())
            for obj in fire_exit_doors
        ),
        "sample": [{"name": obj.name, "properties": expanded_props(obj)} for obj in fire_exit_doors[:5]],
    },
    "access_and_safety_objects": {
        "external_cross_aisle_ramps": [obj.name for obj in hits("ARC-RAMP-EXT-")],
        "aisle_handrails": [obj.name for obj in hits("RAIL-AISLE")],
        "aisle_lights": len(hits("LIGHT-AISLE")),
        "choir_access_steps": [obj.name for obj in hits("STEPS-CHOIR")],
        "choir_rails": [obj.name for obj in hits("RAIL-CHOIR")],
        "choir_wheelchairs": [obj.name for obj in hits("WCS-CHOIR")],
        "refuge_objects": [obj.name for obj in hits("REFUGE")],
    },
    "av_objects": {
        "screens": [{"name": obj.name, "properties": serial_props(obj)} for obj in screens],
        "speakers": [{"name": obj.name, "properties": serial_props(obj)} for obj in speakers],
    },
    "represented_system_keyword_hits": {term: len(hits(term)) for term in keywords},
}

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps({"audit": str(OUT), "sha256": report["blend_sha256"], "revision": report["scene_revision"]}))
