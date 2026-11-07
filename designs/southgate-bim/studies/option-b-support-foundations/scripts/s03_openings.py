"""Read-only: windows, doors, curtain walls and roof truss bearing geometry (positions) for coordination."""
import ifcopenshell, ifcopenshell.geom, ifcopenshell.util.element as ue, sys, json, numpy as np
f = ifcopenshell.open(sys.argv[1]); st = ifcopenshell.geom.settings(); st.set("use-world-coords", True)
out=[]
def bb(e):
    try:
        v=np.array(ifcopenshell.geom.create_shape(st,e).geometry.verts).reshape(-1,3); return [round(x,3) for x in list(v.min(0))+list(v.max(0))]
    except Exception: return None
for cls in ("IfcWindow","IfcDoor","IfcCurtainWall"):
    for e in f.by_type(cls):
        out.append(dict(cls=cls,name=e.Name,src=ue.get_psets(e).get("SOUTHGATE_Provenance",{}).get("SourceObjects"),bbox=bb(e)))
# truss members near bearings: bottom/top chord ends
tr=[]
for a in f.by_type("IfcElementAssembly"):
    if (a.Name or "").startswith("SOUTHGATE-TRUSS"):
        parts=[p for r in a.IsDecomposedBy for p in r.RelatedObjects]
        B=np.array([bb(p) for p in parts if bb(p)])
        tr.append(dict(name=a.Name,src=ue.get_psets(a).get("SOUTHGATE_Provenance",{}).get("SourceObjects"),n=len(parts),
                  bbox=[round(x,3) for x in list(B[:,:3].min(0))+list(B[:,3:].max(0))]))
json.dump(dict(openings=out,trusses=tr),open(sys.argv[2],"w"),indent=1)
