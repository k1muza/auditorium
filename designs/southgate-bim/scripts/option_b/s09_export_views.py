"""Export exact IFC geometry (world triangles) of the element sets needed for the comparison diagrams.

  .venv/Scripts/python -I scripts/option_b/s09_export_views.py <candidate.ifc> <reference.ifc> <out.npz-dir>
Writes <dir>/views_geometry.json.gz : {set_name: [{name, cls, role, label, v, f}]} and bolts / interfaces.
"""
import gzip, json, multiprocessing, re, sys
from pathlib import Path
import numpy as np
import ifcopenshell, ifcopenshell.geom, ifcopenshell.util.element as ue, ifcopenshell.util.placement as up

cand_p, ref_p, outd = sys.argv[1], sys.argv[2], Path(sys.argv[3])
outd.mkdir(parents=True, exist_ok=True)
PT = ue.get_predefined_type
s = ifcopenshell.geom.settings(); s.set("use-world-coords", True)


def mesh(f, els):
    out = {}
    if not els:
        return out
    it = ifcopenshell.geom.iterator(s, f, max(1, multiprocessing.cpu_count() - 1), include=els)
    if it.initialize():
        while True:
            sh = it.get()
            out[sh.guid] = (np.round(np.asarray(sh.geometry.verts).reshape(-1, 3), 5).tolist(), np.asarray(sh.geometry.faces).reshape(-1, 3).tolist())
            if not it.next():
                break
    return out


def role(e):
    md = ue.get_pset(e, "SOUTHGATE_MemberData")
    if md:
        return md["Role"]
    pv = ue.get_pset(e, "SOUTHGATE_Provenance") or {}
    src = pv.get("SourceObjects") or ""
    if e.is_a("IfcMember") and re.match(r"TRUSS-(TOP)", src): return "TRUSS_TOP_CHORD"
    if e.is_a("IfcMember") and re.match(r"TRUSS-CHORD", src): return "TRUSS_BOTTOM_CHORD"
    if e.is_a("IfcMember") and re.match(r"TRUSS-V", src): return "TRUSS_WEB_VERTICAL"
    if e.is_a("IfcMember") and re.match(r"TRUSS-WEB", src): return "TRUSS_WEB_DIAGONAL"
    return str(PT(e) or e.ObjectType or e.is_a())


def pack(f, els, label):
    m = mesh(f, els)
    res = []
    for e in els:
        if e.GlobalId not in m:
            continue
        v, fc = m[e.GlobalId]
        pv = ue.get_pset(e, "SOUTHGATE_Provenance") or {}
        res.append({"name": e.Name, "cls": e.is_a(), "role": role(e), "src": (pv.get("SourceObjects") or "")[:60], "tag": e.Tag, "v": v, "f": fc})
    print(label, len(res), flush=True)
    return res


cand = ifcopenshell.open(cand_p)
ref = ifcopenshell.open(ref_p)
tr_c = {a.Name: a for a in cand.by_type("IfcElementAssembly") if PT(a) == "TRUSS"}
tr_r = {a.Name: a for a in ref.by_type("IfcElementAssembly") if PT(a) == "TRUSS"}
parts = lambda a: [p for p in ue.get_decomposition(a) if p.Representation and not p.is_a("IfcElementAssembly")]
src = lambda e: (ue.get_pset(e, "SOUTHGATE_Provenance") or {}).get("SourceObjects") or ""
D = {}
D["new_T05"] = pack(cand, [p for p in parts(tr_c["SOUTHGATE-TRUSS-T05"]) if not p.is_a("IfcMechanicalFastener")], "new T05")
D["new_T03"] = pack(cand, [p for p in parts(tr_c["SOUTHGATE-TRUSS-T03"]) if not p.is_a("IfcMechanicalFastener")], "new T03")
D["old_T05"] = pack(ref, parts(tr_r["SOUTHGATE-TRUSS-T05"]), "old T05")
D["new_members_all"] = pack(cand, [p for a in tr_c.values() for p in parts(a) if p.is_a("IfcMember")], "new members")
D["old_members_all"] = pack(ref, [p for a in tr_r.values() for p in parts(a) if p.is_a("IfcMember")], "old members")
ret = [e for e in cand.by_type("IfcElement") if e.Representation and not e.is_a("IfcOpeningElement")]
D["purlins"] = pack(cand, [e for e in ret if re.match(r"^(PURLIN-ROW-|ROOF-RIDGE-ADJACENT|ROOF-EDGE-PURLIN)", src(e))], "purlins")
D["bracing"] = pack(cand, [e for e in ret if re.match(r"^BRACE-ROOF", src(e))], "bracing")
D["heel_existing"] = pack(cand, [e for e in ret if re.match(r"^(COL-ROOF-4-0|ROOF-COLUMN-CAP-4-0|ROOF-COLUMN-SEAT-4-0|ROOF-EAVES-RHS-OUTRIGGER-S-04|ROOF-EAVES-CLEAT-S-04|PURLIN-ROW-0[0-2]-BAY-0[34]|PURLIN-CLEAT-04-0[0-2]|ROOF-EDGE-PURLIN-S-BAY-0[34])$", src(e))], "heel existing")
D["equip_line2"] = pack(cand, [e for e in ret if re.match(r"^(ACOUSTIC-TRUSS-CLAMP-0[1-3]|STG-LGT-HANGER-FRONT|STG-LGT-BAR-FRONT|ARRAY-)", src(e))], "equipment line 2")
D["hvls"] = pack(cand, [e for e in ret if re.search(r"VENT-05-HVLS\d-SUPPORT-BEAM", src(e))], "hvls beams")
D["clamps_all"] = pack(cand, [e for e in ret if re.match(r"^ACOUSTIC-TRUSS-CLAMP", src(e))], "clamps")
D["columns"] = pack(cand, [e for e in ret if re.match(r"^COL-ROOF-", src(e))], "columns")
bolts = []
for a in tr_c.values():
    for p in ue.get_decomposition(a):
        if p.is_a("IfcMechanicalFastener"):
            M = up.get_local_placement(p.ObjectPlacement)
            pv = ue.get_pset(p, "SOUTHGATE_Provenance") or {}
            bolts.append({"name": p.Name, "truss": a.Name, "xyz": M[:3, 3].round(5).tolist(), "d": float(p.NominalDiameter), "role": pv.get("BoltRole")})
D["bolts_new"] = bolts
ob = []
for a in tr_r.values():
    for p in ue.get_decomposition(a):
        if p.is_a("IfcMechanicalFastener") and not (p.Name or "").endswith(("HEAD", "NUT")):
            M = up.get_local_placement(p.ObjectPlacement)
            ob.append({"name": p.Name, "truss": a.Name, "xyz": M[:3, 3].round(5).tolist()})
D["bolts_old"] = ob
with gzip.open(outd / "views_geometry.json.gz", "wt", encoding="utf-8") as fh:
    json.dump(D, fh)
print("written", outd / "views_geometry.json.gz")
