"""Write IFC4 from the Blender manifest (geometry + semantics read back from the .blend scene).

  .venv/Scripts/python scripts/export_ifc.py model/blender_manifest.json model/church_3000_concept.ifc

Uses IfcOpenShell's API. Body geometry = the Blender mesh (IfcPolygonalFaceSet via
add_mesh_representation); chairs share one IfcFurnitureType representation (mapped
items). Doors/windows get IfcOpeningElement voids in their host walls. Truss members
are aggregated into IfcElementAssembly (TRUSS). Spaces carry gross floor area quantities.
"""
import json
import sys
import time
from pathlib import Path

import numpy as np
import ifcopenshell
import ifcopenshell.api
import ifcopenshell.guid
from ifcopenshell.api import aggregate, context, feature, geometry, material, project, pset, root, spatial, unit
from ifcopenshell.api import type as ifctype

PSET = "Pset_CA3000_Concept"
QTO = {"IfcColumn": "Qto_ColumnBaseQuantities", "IfcBeam": "Qto_BeamBaseQuantities", "IfcMember": "Qto_MemberBaseQuantities",
       "IfcSlab": "Qto_SlabBaseQuantities", "IfcWall": "Qto_WallBaseQuantities", "IfcFooting": "Qto_FootingBaseQuantities",
       "IfcDoor": "Qto_DoorBaseQuantities", "IfcWindow": "Qto_WindowBaseQuantities", "IfcRailing": "Qto_RailingBaseQuantities",
       "IfcCovering": "Qto_CoveringBaseQuantities",
       # no IFC4 standard base-quantity set exists for these whole elements: project-named set, clearly not Qto_*
       "IfcStair": "CA3000_BaseQuantities", "IfcRamp": "CA3000_BaseQuantities", "IfcTransportElement": "CA3000_BaseQuantities",
       "IfcFurniture": "CA3000_BaseQuantities"}


def material_for(ob):
    """Placeholder material names (A-23) - for model structure / take-off only, no specification implied."""
    cls, pre = ob["ifc_class"], ob["predefined_type"]
    if cls in ("IfcColumn", "IfcBeam", "IfcMember", "IfcRailing"):
        return "Structural steel (grade TBC)"
    if cls == "IfcFooting":
        return "Reinforced concrete (grade TBC)"
    if cls == "IfcSlab" and pre == "ROOF":
        return "Metal roof sheeting (TBC)"
    if cls in ("IfcSlab", "IfcStair", "IfcRamp"):
        return "Concrete (grade TBC)"
    if cls == "IfcWall":
        if ob["name"].endswith("-UPPER") or "GABLE" in ob["name"]:
            return "Metal wall cladding (TBC)"
        return "Masonry (TBC)" if ob["collection"].startswith("10_") else "Masonry partition (TBC)"
    if cls == "IfcDoor":
        return "Door assembly (TBC)"
    if cls == "IfcWindow":
        return "Glazing (TBC)"
    if cls in ("IfcFurniture", "IfcTransportElement"):
        return "Proprietary item (TBC)"
    if cls == "IfcCovering":
        return "Metal flashing (TBC)"
    if cls == "IfcPipeSegment":
        return "Metal rainwater goods (TBC)"
    if cls in ("IfcAudioVisualAppliance", "IfcLightFixture"):
        return "Proprietary item (TBC)"
    return None


def mesh_volume(verts, faces):
    """Absolute enclosed volume of a closed mesh (sum of signed tetrahedra, fan-triangulated faces)."""
    v = np.asarray(verts, dtype=float)
    vol = 0.0
    for fc in faces:
        for k in range(1, len(fc) - 1):
            vol += np.dot(v[fc[0]], np.cross(v[fc[k]], v[fc[k + 1]])) / 6.0
    return abs(vol)


def base_quantities(ob, m):
    v = np.asarray(m["verts"], dtype=float)
    ext = v.max(axis=0) - v.min(axis=0)
    q = {"GrossVolume": round(float(mesh_volume(m["verts"], m["faces"])), 4)}
    cls = ob["ifc_class"]
    if ob["strut"]:
        q["Length"] = round(float(np.linalg.norm(np.subtract(ob["strut"][1], ob["strut"][0]))), 4)
    elif cls in ("IfcColumn",):
        q["Length"] = round(float(ext[2]), 4)
    elif cls in ("IfcBeam",):
        q["Length"] = round(float(max(ext[0], ext[1])), 4)
    elif cls == "IfcWall":
        q.update({"Length": round(float(max(ext[0], ext[1])), 4), "Height": round(float(ext[2]), 4),
                  "Width": round(float(min(ext[0], ext[1])), 4)})
    elif cls == "IfcSlab":
        q["GrossArea"] = round(float(ext[0] * ext[1]), 4)
    elif cls in ("IfcDoor", "IfcWindow"):
        w, h = float(ob["props"]["OverallWidth"]), float(ob["props"]["OverallHeight"])
        q = {"Width": w, "Height": h, "Area": round(w * h, 4)}
    elif cls == "IfcRailing":
        q = {"Length": round(float(max(ext[0], ext[1])), 4)}
    elif cls == "IfcCovering":
        q = {"GrossArea": round(float(ext[0] * ext[1]), 4)}
    elif cls in ("IfcStair", "IfcRamp"):
        q.update({"Length": round(float(max(ext[0], ext[1])), 4), "Width": round(float(min(ext[0], ext[1])), 4),
                  "Rise": round(float(ext[2]), 4)})
    return q


def pval(v):
    if isinstance(v, bool) or isinstance(v, (int, float)) or v is None:
        return v
    return str(v)


def main(manifest_path, out_path):
    t0 = time.time()
    M = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    f = project.create_file(version="IFC4")
    prj = root.create_entity(f, ifc_class="IfcProject", name=M["project"]["name"])
    prj.Description = f"{M['project']['status_label']} | revision {M['revision']}"
    unit.assign_unit(f, length={"is_metric": True, "raw": "METERS"}, area={"is_metric": True, "raw": "SQUARE_METRE"},
                     volume={"is_metric": True, "raw": "CUBIC_METRE"})
    model = context.add_context(f, context_type="Model")
    body = context.add_context(f, context_type="Model", context_identifier="Body", target_view="MODEL_VIEW", parent=model)
    site = root.create_entity(f, ifc_class="IfcSite", name="Site (not surveyed)")
    site.Description = M["project"]["country"]
    bldg = root.create_entity(f, ifc_class="IfcBuilding", name="Church auditorium (concept)")
    aggregate.assign_object(f, relating_object=prj, products=[site])
    aggregate.assign_object(f, relating_object=site, products=[bldg])
    storeys = {}
    for lv in M["levels"]:
        s = root.create_entity(f, ifc_class="IfcBuildingStorey", name=lv["id"])
        s.LongName = lv["name"]
        s.Elevation = float(lv["elevation"])
        geometry.edit_object_placement(f, product=s, matrix=np.array(
            [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, float(lv["elevation"])], [0, 0, 0, 1]], dtype=float))
        aggregate.assign_object(f, relating_object=bldg, products=[s])
        storeys[lv["id"]] = s
    # structural grid
    grid = root.create_entity(f, ifc_class="IfcGrid", name="Structural grid")
    gx, gy = M["grid"]["x_lines"], M["grid"]["y_lines"]
    xmin, xmax = min(gx.values()) - 5, max(gx.values()) + 5
    ymin, ymax = min(gy.values()) - 5, max(gy.values()) + 5

    def axis(tag, p0, p1):
        line = f.createIfcPolyline([f.createIfcCartesianPoint(p0), f.createIfcCartesianPoint(p1)])
        return f.createIfcGridAxis(tag, line, True)

    grid.UAxes = [axis(k, (v, ymin), (v, ymax)) for k, v in gx.items()]
    grid.VAxes = [axis(k, (xmin, v), (xmax, v)) for k, v in gy.items()]
    geometry.edit_object_placement(f, product=grid)
    spatial.assign_container(f, relating_structure=storeys["L00"], products=[grid])
    # chair type with shared representation
    meshes = M["meshes"]
    chair_type = root.create_entity(f, ifc_class="IfcFurnitureType", name="Fixed auditorium chair (concept)",
                                    predefined_type="CHAIR")
    cm = meshes["MESH_SHARED_CHAIR"]
    rep = geometry.add_mesh_representation(f, context=body, vertices=[cm["verts"]], faces=[cm["faces"]])
    geometry.assign_representation(f, product=chair_type, representation=rep)
    by_name, assemblies, chairs, contained, by_material = {}, {}, [], {}, {}
    counts = {}
    for ob in M["objects"]:
        cls = ob["ifc_class"]
        pre = ob["predefined_type"] or None
        el = root.create_entity(f, ifc_class=cls, name=ob["name"], predefined_type=pre)
        if ob["object_type"]:
            el.ObjectType = ob["object_type"]
        if hasattr(el, "Description"):
            el.Description = ob["collection"]
        mat = np.array(ob["matrix"], dtype=float)
        geometry.edit_object_placement(f, product=el, matrix=mat, is_si=True)
        if ob["mesh"] == "MESH_SHARED_CHAIR":
            chairs.append(el)
        else:
            m = meshes[ob["mesh"]]
            r = geometry.add_mesh_representation(f, context=body, vertices=[m["verts"]], faces=[m["faces"]])
            geometry.assign_representation(f, product=el, representation=r)
        props = {k: pval(v) for k, v in ob["props"].items() if v is not None and k not in ("LongName",)}
        props["Collection"] = ob["collection"]
        props["Revision"] = M["revision"]
        props["DesignStatus"] = props.get("DesignStatus", "Concept - unverified")
        ps = pset.add_pset(f, product=el, name=PSET)
        pset.edit_pset(f, pset=ps, properties=props)
        if cls == "IfcWall":
            pset.edit_pset(f, pset=pset.add_pset(f, product=el, name="Pset_WallCommon"),
                           properties={"IsExternal": bool(ob["props"].get("IsExternal", False)), "LoadBearing": False})
        if cls in ("IfcDoor", "IfcWindow"):
            el.OverallWidth = float(ob["props"]["OverallWidth"])
            el.OverallHeight = float(ob["props"]["OverallHeight"])
            pn = "Pset_DoorCommon" if cls == "IfcDoor" else "Pset_WindowCommon"
            common = {"IsExternal": bool(ob["props"].get("IsExternal", False))}
            if cls == "IfcDoor":
                common.update({"FireExit": bool(ob["props"].get("FireExit", False)),
                               "HandicapAccessible": float(ob["props"]["OverallWidth"]) >= 0.9})
            pset.edit_pset(f, pset=pset.add_pset(f, product=el, name=pn), properties=common)
        if cls == "IfcColumn":
            pset.edit_pset(f, pset=pset.add_pset(f, product=el, name="Pset_ColumnCommon"),
                           properties={"LoadBearing": True, "Reference": ob["props"].get("Grid", "")})
        if cls == "IfcSpace":
            el.LongName = ob["props"].get("LongName")
            q = pset.add_qto(f, product=el, name="Qto_SpaceBaseQuantities")
            pset.edit_qto(f, qto=q, properties={"GrossFloorArea": float(ob["props"]["GrossFloorArea"])})
        if cls in QTO and not (cls == "IfcFurniture" and ob["mesh"] == "MESH_SHARED_CHAIR"):
            q = pset.add_qto(f, product=el, name=QTO[cls])
            pset.edit_qto(f, qto=q, properties=base_quantities(ob, meshes[ob["mesh"]]))
        mname = material_for(ob)
        if mname and ob["mesh"] != "MESH_SHARED_CHAIR":
            by_material.setdefault(mname, []).append(el)
        if cls == "IfcSpatialZone":
            el.LongName = ob["props"].get("LongName", ob["object_type"])
        by_name[ob["name"]] = el
        counts[f"{cls}:{pre or ''}"] = counts.get(f"{cls}:{pre or ''}", 0) + 1
        st = storeys[ob["storey"]]
        if cls == "IfcSpace":
            aggregate.assign_object(f, relating_object=st, products=[el])
        elif cls == "IfcSpatialZone":
            spatial.reference_structure(f, products=[el], relating_structure=st)
        elif ob["assembly"]:
            assemblies.setdefault(ob["assembly"], {"storey": ob["storey"], "members": []})["members"].append(el)
        else:
            contained.setdefault(ob["storey"], []).append(el)
    for sid, els in contained.items():
        spatial.assign_container(f, relating_structure=storeys[sid], products=els)
    ifctype.assign_type(f, related_objects=chairs, relating_type=chair_type)
    mats = {}
    for mname in sorted(set(by_material) | {"Seating (TBC)"}):
        mats[mname] = material.add_material(f, name=mname, category="concept placeholder")
    material.assign_material(f, products=[chair_type], material=mats["Seating (TBC)"])
    # chair quantities on the type (shared by all occurrences): one set, volume integrated from the shared mesh
    pset.edit_pset(f, pset=pset.add_pset(f, product=chair_type, name="CA3000_TypeQuantities"),
                   properties={"GrossVolumePerChair": round(float(mesh_volume(cm["verts"], cm["faces"])), 5),
                               "Occurrences": len(chairs)})
    for mname, els in sorted(by_material.items()):
        material.assign_material(f, products=els, material=mats[mname])
    for name, a in sorted(assemblies.items()):
        asm = root.create_entity(f, ifc_class="IfcElementAssembly", name=name, predefined_type="TRUSS")
        geometry.edit_object_placement(f, product=asm)
        pset.edit_pset(f, pset=pset.add_pset(f, product=asm, name=PSET),
                       properties={"DesignStatus": "Concept truss geometry - members not designed", "Revision": M["revision"]})
        spatial.assign_container(f, relating_structure=storeys[a["storey"]], products=[asm])
        aggregate.assign_object(f, relating_object=asm, products=a["members"])
        counts["IfcElementAssembly:TRUSS"] = counts.get("IfcElementAssembly:TRUSS", 0) + 1
    # openings: void host walls and fill with doors / windows
    n_open = 0
    for ob in M["objects"]:
        if not ob.get("host"):
            continue
        x0, y0, z0, x1, y1, z1 = ob["opening"]
        op = root.create_entity(f, ifc_class="IfcOpeningElement", name=f"OPN-{ob['name']}", predefined_type="OPENING")
        geometry.edit_object_placement(f, product=op, matrix=np.array(
            [[1, 0, 0, x0], [0, 1, 0, y0], [0, 0, 1, z0], [0, 0, 0, 1]], dtype=float), is_si=True)
        bx, by, bz = x1 - x0, y1 - y0, z1 - z0
        verts = [(0, 0, 0), (bx, 0, 0), (bx, by, 0), (0, by, 0), (0, 0, bz), (bx, 0, bz), (bx, by, bz), (0, by, bz)]
        faces = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
        r = geometry.add_mesh_representation(f, context=body, vertices=[verts], faces=[faces])
        geometry.assign_representation(f, product=op, representation=r)
        feature.add_feature(f, feature=op, element=by_name[ob["host"]])
        feature.add_filling(f, opening=op, element=by_name[ob["name"]])
        n_open += 1
    f.write(out_path)
    summary = {"ifc": str(out_path), "schema": f.schema, "products": len(f.by_type("IfcProduct")),
               "openings": n_open, "counts": dict(sorted(counts.items())), "seconds": round(time.time() - t0, 1)}
    print("IFC_SUMMARY " + json.dumps(summary))
    return summary


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
