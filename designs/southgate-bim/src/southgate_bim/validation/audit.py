"""Migration audits on SAVED IFC files (never on the in-memory build).

Per element: presence by GlobalId, class, containment/aggregation, material,
world-AABB agreement with the source members, volume agreement, quantity
calculability; plus file-level duplicate and relationship checks.
"""
from __future__ import annotations

import multiprocessing
from collections import Counter, defaultdict

import numpy as np
import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util.element as ue
import ifcopenshell.util.shape as us

REP_CHANGE_CLASSES = {"IfcDoor", "IfcWindow"}     # parametric bodies replace modelled parts


def shapes_world(ifc, elements):
    s = ifcopenshell.geom.settings()
    s.set("use-world-coords", True)
    out = {}
    if not elements:
        return out
    it = ifcopenshell.geom.iterator(s, ifc, max(1, multiprocessing.cpu_count() - 1), include=elements)
    if it.initialize():
        while True:
            sh = it.get()
            g = sh.geometry
            v = np.asarray(g.verts).reshape(-1, 3)
            if len(v):
                try:
                    vol = us.get_volume(g)
                except Exception:
                    vol = None
                out[sh.guid] = {"min": v.min(axis=0), "max": v.max(axis=0), "volume": vol,
                                "area": us.get_area(g)}
            if not it.next():
                break
    return out


def relationship_state(e, ifc=None):
    if e.is_a("IfcSpatialZone"):
        refs = [r for r in ifc.get_inverse(e) if r.is_a("IfcRelReferencedInSpatialStructure")] if ifc else []
        return "referenced" if refs else "MISSING"
    if getattr(e, "Decomposes", None):
        return "aggregated"
    if getattr(e, "ContainedInStructure", None):
        return "contained"
    return "MISSING"


def audit_elements(ifc, plan_elements, objects, tol, src_volumes=None, src_aabbs=None):
    rows = []
    ents = {}
    for el in plan_elements:
        try:
            ents[el["stable_id"]] = ifc.by_guid(el["global_id"])
        except RuntimeError:
            ents[el["stable_id"]] = None
    shapes = shapes_world(ifc, [e for e in ents.values() if e is not None and not e.is_a("IfcSpatialZone")])
    for el in plan_elements:
        e = ents[el["stable_id"]]
        r = {"stable_id": el["stable_id"], "global_id": el["global_id"], "phase": el["phase"],
             "planned_class": el["ifc_class"], "members": len(el["members"])}
        if e is None:
            r.update(status="MISSING_IN_IFC")
            rows.append(r)
            continue
        r["ifc_class"] = e.is_a()
        r["class_ok"] = e.is_a() == el["ifc_class"]
        r["relationship"] = relationship_state(e, ifc)
        mat = ue.get_material(e, should_inherit=True)
        r["material"] = mat.is_a() if mat else None
        prov = ue.get_pset(e, "SOUTHGATE_Provenance") or {}
        r["representation"] = prov.get("Representation")
        r["native"] = prov.get("NativeRepresentation")
        if src_aabbs and all(src_aabbs.get(n) for n in el["members"]):
            smn = np.min([src_aabbs[n][0] for n in el["members"]], axis=0)     # true world-vertex bounds
            smx = np.max([src_aabbs[n][1] for n in el["members"]], axis=0)
        else:
            smn = np.min([objects[n]["aabb_min"] for n in el["members"]], axis=0)
            smx = np.max([objects[n]["aabb_max"] for n in el["members"]], axis=0)
        if el["ifc_class"] in REP_CHANGE_CLASSES and el["method"] in ("door", "window"):
            from ..migration.openings import filler_box
            fmn, fmx = filler_box(el, objects)
            r["source_part_spread_m"] = round(float(max(np.abs(fmn - smn).max(), np.abs(fmx - smx).max())), 4)
            smn, smx = fmn, fmx          # frame parts define the door/window position
        svol = 0.0
        sv_ok = True
        for n in el["members"]:
            v = (src_volumes or {}).get(n)
            if v is None:
                sv_ok = False
            else:
                svol += v
        sh = shapes.get(e.GlobalId)
        if e.is_a("IfcSpatialZone"):
            r.update(geom="n/a (zone)", status="OK" if r["relationship"] != "MISSING" else "FAIL")
            rows.append(r)
            continue
        if sh is None:
            r.update(geom="NO_GEOMETRY", status="FAIL")
            rows.append(r)
            continue
        dmin = np.abs(sh["min"] - smn)
        dmax = np.abs(sh["max"] - smx)
        dev = float(max(dmin.max(), dmax.max()))
        r["aabb_dev_m"] = round(dev, 5)
        r["dim_dev_m"] = round(float(np.abs((sh["max"] - sh["min"]) - (smx - smn)).max()), 5)
        r["ifc_volume_m3"] = None if sh["volume"] is None else round(sh["volume"], 6)
        r["src_volume_m3"] = round(svol, 6) if sv_ok else None
        openings_complete = len(getattr(e, "HasOpenings", []) or []) >= len(el.get("openings") or [])
        r["openings_planned"] = len(el.get("openings") or [])
        r["openings_present"] = len(getattr(e, "HasOpenings", []) or [])
        if sv_ok and sh["volume"] and svol > 1e-9 and (not el.get("openings") or (el["method"] == "wall_merged" and openings_complete)):
            r["vol_rel_dev"] = round(abs(sh["volume"] - svol) / svol, 5)
        else:
            r["vol_rel_dev"] = None
        rep_change = el["ifc_class"] in REP_CHANGE_CLASSES
        lim = tol["position_m"] if not rep_change else 0.08
        vlim = tol["volume_rel"] if r.get("native") else tol["volume_rel_tess"]
        fails = []
        if not r["class_ok"]:
            fails.append("class")
        if r["relationship"] == "MISSING":
            fails.append("relationship")
        if r["material"] is None and not e.is_a("IfcSpace"):
            fails.append("material")
        if dev > lim:
            fails.append(f"aabb>{lim}")
        if r["vol_rel_dev"] is not None and r["vol_rel_dev"] > vlim and not rep_change:
            fails.append(f"volume>{vlim}")
        if (sh["volume"] is None or sh["volume"] <= 0) and not rep_change:
            fails.append("no_volume")
        skew = prov.get("FitMaxDeviation_mm") or 0
        r["fit_deviation_mm"] = skew
        if skew and any(x.startswith("volume") for x in fails):
            fails = [("volume_source_member_skewed" if x.startswith("volume") else x) for x in fails]
        r["checks_failed"] = ",".join(fails)
        r["status"] = "OK" if not fails else ("REVIEW" if all(x.startswith("volume") or x == "no_volume" for x in fails) else "FAIL")
        r["expected_representation_change"] = rep_change
        rows.append(r)
    return rows


def file_checks(ifc, plan_elements):
    g = Counter(e.GlobalId for e in ifc.by_type("IfcRoot"))
    dup_guid = [k for k, v in g.items() if v > 1]
    names = Counter(e.Name for e in ifc.by_type("IfcElement") if e.Name and not e.is_a("IfcOpeningElement"))
    dup_names = [k for k, v in names.items() if v > 1]
    planned = {el["global_id"] for el in plan_elements}
    extra = [e for e in ifc.by_type("IfcElement") if e.GlobalId not in planned and not e.is_a("IfcOpeningElement")
             and not e.is_a("IfcElementAssembly") and not e.is_a("IfcCurtainWall") and not e.is_a("IfcRoof")
             and not e.is_a("IfcStair")]
    fills = ifc.by_type("IfcRelFillsElement")
    voids = ifc.by_type("IfcRelVoidsElement")
    unfilled = [o.Name for o in ifc.by_type("IfcOpeningElement") if not o.HasFillings]
    return {"duplicate_guids": dup_guid, "duplicate_element_names": dup_names[:20], "n_duplicate_names": len(dup_names),
            "unplanned_elements": [e.Name for e in extra][:20], "n_unplanned": len(extra),
            "openings": len(ifc.by_type("IfcOpeningElement")), "fills": len(fills), "voids": len(voids),
            "unfilled_openings": unfilled}
