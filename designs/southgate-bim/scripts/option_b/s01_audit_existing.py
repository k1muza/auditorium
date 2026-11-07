"""Stage 1 audit (read-only): inventory of the existing roof-truss system and its interfaces.
Usage: .venv/Scripts/python -I scripts/option_b/s01_audit_existing.py bim/southgate.ifc work/option_b/s01_existing.json"""
import sys, json, hashlib, re
from collections import Counter, defaultdict
import numpy as np
import ifcopenshell, ifcopenshell.geom, ifcopenshell.util.element as ue, ifcopenshell.util.placement as up

src, out = sys.argv[1], sys.argv[2]
sha = hashlib.sha256(open(src, "rb").read()).hexdigest()
f = ifcopenshell.open(src)
st = ifcopenshell.geom.settings(); st.set("use-world-coords", True)

def bbox(e):
    try:
        sh = ifcopenshell.geom.create_shape(st, e)
        v = np.array(sh.geometry.verts).reshape(-1, 3)
        return [round(float(x), 4) for x in v.min(0)] + [round(float(x), 4) for x in v.max(0)]
    except Exception:
        return None

def prof(e):
    m = ue.get_material(e, should_skip_usage=False)
    if m is None: return None, None
    if m.is_a("IfcMaterialProfileSetUsage"):
        ps = m.ForProfileSet
        return ";".join((p.Profile.ProfileName or p.Profile.is_a()) + "<" + p.Profile.is_a() + ">" for p in ps.MaterialProfiles), ";".join(p.Material.Name for p in ps.MaterialProfiles if p.Material)
    return None, getattr(m, "Name", m.is_a())

asm = {}
for a in f.by_type("IfcElementAssembly"):
    if a.PredefinedType == "TRUSS" or (a.Name or "").upper().find("TRUSS") >= 0:
        parts = ue.get_decomposition(a)
        cnt = Counter(p.is_a() for p in parts)
        asm[a.Name] = dict(gid=a.GlobalId, ptype=a.PredefinedType, n=len(parts), classes=dict(cnt),
                           container=(ue.get_container(a).Name if ue.get_container(a) else None),
                           psets=list(ue.get_psets(a).keys()))
rows = []
for a in f.by_type("IfcElementAssembly"):
    if a.PredefinedType != "TRUSS": continue
    for p in ue.get_decomposition(a):
        ps = ue.get_psets(p); pv = ps.get("SOUTHGATE_Provenance", {}); ss = ps.get("SOUTHGATE_SourceSpecification", {})
        pr, mat = prof(p); t = ue.get_type(p)
        rows.append(dict(asm=a.Name, cls=p.is_a(), gid=p.GlobalId, name=p.Name, stable=pv.get("StableId"), src=pv.get("SourceObjects"),
                         rule=pv.get("MigrationRule"), rep=pv.get("Representation"), ptype=getattr(p, "PredefinedType", None),
                         otype=p.ObjectType, type=(t.Name if t else None), profile=pr, material=mat, bbox=bbox(p),
                         spec={k: v for k, v in ss.items() if k != "id"}, status=ps.get("SOUTHGATE_DesignStatus", {}).get("DesignStatus")))
# interfaces: anything whose source object / name hints at roof structure, equipment hung from trusses
pat = re.compile(r"COL-ROOF|PURLIN|BRACE|ROOF-(BASEPLATE|COLUMN|ANCHOR|EAVES|EDGE|RIDGE|GABLE)|ACOUSTIC-(TRANSFER|TRUSS|HANGER)|ARRAY|DELAY|LGT|LIGHT|BAR|HVLS|VENT-0[45]|CATWALK|RIG|TIE|GIRDER|TRAY|HANG", re.I)
iface = []
in_truss = {r["gid"] for r in rows}
for e in f.by_type("IfcElement"):
    if e.GlobalId in in_truss or e.is_a("IfcOpeningElement") or e.is_a("IfcElementAssembly"): continue
    pv = ue.get_psets(e).get("SOUTHGATE_Provenance", {})
    s = (pv.get("SourceObjects") or "") + " " + (e.Name or "")
    if pat.search(s):
        b = bbox(e)
        if b and b[5] < 9.0 and not re.search(r"COL-ROOF|ARRAY|DELAY|HVLS|VENT", s, re.I): continue   # keep high-level items only
        pr, mat = prof(e); ag = ue.get_aggregate(e)
        iface.append(dict(cls=e.is_a(), gid=e.GlobalId, name=e.Name, stable=pv.get("StableId"), src=(pv.get("SourceObjects") or "")[:120],
                          rule=pv.get("MigrationRule"), otype=e.ObjectType, profile=pr, material=mat, bbox=b, parent=(ag.Name if ag else None)))
json.dump(dict(source=src, sha256=sha, schema=f.schema, truss_assemblies=asm, truss_parts=rows, interfaces=iface,
               counts=dict(Counter(r["cls"] for r in rows)), iface_counts=dict(Counter((i["rule"] or i["cls"]) for i in iface))),
          open(out, "w"), indent=1)
print("sha", sha); print("assemblies", len(asm), "parts", len(rows), dict(Counter(r["cls"] for r in rows)))
print("interfaces", dict(Counter((i["rule"] or i["cls"]) for i in iface)))
