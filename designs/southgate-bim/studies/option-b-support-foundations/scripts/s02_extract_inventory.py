"""Read-only extraction of primary structural support inventory from the authoritative IFC.
Usage: python -I s02_extract_inventory.py <southgate.ifc> <out.json>   (never writes to the IFC)"""
import ifcopenshell, ifcopenshell.geom, ifcopenshell.util.element as ue, sys, json, hashlib, numpy as np
src, out = sys.argv[1], sys.argv[2]
sha = hashlib.sha256(open(src,'rb').read()).hexdigest()
f = ifcopenshell.open(src)
st = ifcopenshell.geom.settings(); st.set("use-world-coords", True)
def bbox(e):
    try:
        sh = ifcopenshell.geom.create_shape(st, e)
        v = np.array(sh.geometry.verts).reshape(-1,3)
        return [round(x,3) for x in v.min(0)] + [round(x,3) for x in v.max(0)]
    except Exception as ex:
        return None
def profile(e):
    for r in ue.get_material(e, should_skip_usage=False) and [ue.get_material(e, should_skip_usage=False)] or []:
        if r.is_a("IfcMaterialProfileSetUsage"):
            ps = r.ForProfileSet
            return ";".join((p.Profile.ProfileName or "") for p in ps.MaterialProfiles), ";".join(p.Material.Name for p in ps.MaterialProfiles if p.Material)
        if r.is_a("IfcMaterial"): return "", r.Name
        if r.is_a("IfcMaterialLayerSetUsage"):
            return "layers:"+",".join(str(round(l.LayerThickness,3)) for l in r.ForLayerSet.MaterialLayers), ",".join(l.Material.Name for l in r.ForLayerSet.MaterialLayers if l.Material)
    return "", ""
rows = []
want = {"IfcColumn":None,"IfcFooting":None,"IfcBeam":None,"IfcSlab":None,"IfcWall":None,"IfcElementAssembly":None}
for cls in want:
    for e in f.by_type(cls):
        ps = ue.get_psets(e)
        pv, ds, ss = ps.get("SOUTHGATE_Provenance",{}), ps.get("SOUTHGATE_DesignStatus",{}), ps.get("SOUTHGATE_SourceSpecification",{})
        t = ue.get_type(e)
        prof, mat = profile(e)
        rows.append(dict(cls=cls, gid=e.GlobalId, name=e.Name, stable=pv.get("StableId"), src=pv.get("SourceObjects"),
            coll=pv.get("SourceCollections"), rule=pv.get("MigrationRule"), type=t.Name if t else None, profile=prof, material=mat,
            status=ds.get("DesignStatus"), src_status=ds.get("SourceDesignStatus"), boq=ds.get("SourceBOQInclusion"),
            spec={k:v for k,v in ss.items() if k!="id"}, bbox=bbox(e) if cls!="IfcElementAssembly" else None,
            container=(ue.get_container(e).Name if ue.get_container(e) else None)))
# members: only braces/ties/wall members + a truss bearing summary
for e in f.by_type("IfcMember"):
    pv = ue.get_psets(e).get("SOUTHGATE_Provenance",{})
    nm = (pv.get("SourceObjects") or "")
    if e.Name.startswith(("SOUTHGATE-BRACE","SOUTHGATE-WALL","SOUTHGATE-LGT")) or any(k in nm.upper() for k in ("BRAC","TIE","GIRDER","STRUT","ROD","GIRT")):
        prof, mat = profile(e)
        rows.append(dict(cls="IfcMember", gid=e.GlobalId, name=e.Name, stable=pv.get("StableId"), src=nm, coll=pv.get("SourceCollections"),
            rule=pv.get("MigrationRule"), type=(ue.get_type(e).Name if ue.get_type(e) else None), profile=prof, material=mat,
            status=ue.get_psets(e).get("SOUTHGATE_DesignStatus",{}).get("DesignStatus"), bbox=bbox(e)))
for e in f.by_type("IfcPlate"):
    pv = ue.get_psets(e).get("SOUTHGATE_Provenance",{}); nm = pv.get("SourceObjects") or ""
    if any(k in nm.upper() for k in ("BASE","CAP","BEARING","SEAT","HEEL")):
        rows.append(dict(cls="IfcPlate", gid=e.GlobalId, name=e.Name, stable=pv.get("StableId"), src=nm, coll=pv.get("SourceCollections"), bbox=bbox(e)))
fast = {}
for e in f.by_type("IfcMechanicalFastener"):
    pv = ue.get_psets(e).get("SOUTHGATE_Provenance",{}); nm = pv.get("SourceObjects") or ""
    key = (pv.get("SourceCollections") or "") + "|" + "-".join(nm.split("-")[:3])
    fast[key] = fast.get(key,0)+1
json.dump(dict(source=src, sha256=sha, n=len(rows), rows=rows, fastener_groups=fast), open(out,"w"), indent=1)
print("sha", sha, "rows", len(rows))
