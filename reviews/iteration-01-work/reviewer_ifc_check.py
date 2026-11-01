"""Reviewer read-only IFC inspection of a COPY of the IFC."""
import json, sys, csv
from collections import Counter, defaultdict
import ifcopenshell, ifcopenshell.util.element as ue, ifcopenshell.util.placement as up, ifcopenshell.util.unit as uu
import numpy as np

ROOT = r"C:\Users\Kelvin\Desktop\auditorium"
f = ifcopenshell.open(ROOT + r"\reviews\iteration-01-work\copy.ifc")
r = {"schema": f.schema}
r["header_desc"] = str(f.header.file_description.description)
proj = f.by_type("IfcProject")
r["projects"] = len(proj)
ua = proj[0].UnitsInContext
r["units"] = [(u.UnitType, getattr(u, "Prefix", None), getattr(u, "Name", None)) for u in ua.Units if u.is_a("IfcSIUnit")]
r["length_scale"] = uu.calculate_unit_scale(f)
r["sites"] = [(s.Name, s.RefLatitude, s.RefElevation) for s in f.by_type("IfcSite")]
r["buildings"] = [b.Name for b in f.by_type("IfcBuilding")]
r["storeys"] = [(s.Name, s.LongName, s.Elevation) for s in f.by_type("IfcBuildingStorey")]
r["class_counts"] = dict(Counter(e.is_a() for e in f.by_type("IfcProduct")))
# containment
cont = {}
for rel in f.by_type("IfcRelContainedInSpatialStructure"):
    for e in rel.RelatedElements:
        cont[e.id()] = rel.RelatingStructure.Name
agg = set()
for rel in f.by_type("IfcRelAggregates"):
    for e in rel.RelatedObjects: agg.add(e.id())
nest = set()
for rel in f.by_type("IfcRelNests"):
    for e in rel.RelatedObjects: nest.add(e.id())
uncontained = [e for e in f.by_type("IfcElement") if e.id() not in cont and e.id() not in agg and not e.is_a("IfcOpeningElement") and not e.is_a("IfcFeatureElement")]
r["uncontained_elements"] = len(uncontained); r["uncontained_examples"] = [(e.is_a(), e.Name) for e in uncontained[:8]]
spaces_unagg = [s.Name for s in f.by_type("IfcSpace") if s.id() not in agg and s.id() not in cont]
r["spaces_not_in_spatial_tree"] = spaces_unagg[:5]
# furniture/seat analysis
furn = f.by_type("IfcFurniture")
r["furniture"] = len(furn)
pset_names = Counter()
seat_types = Counter()
counts_flag = Counter()
cong = []
for e in furn:
    ps = ue.get_psets(e)
    for k in ps: pset_names[k] += 1
    st = None; ct = None
    for k, v in ps.items():
        if "SeatType" in v: st = v["SeatType"]
        if "CountsTowardTarget" in v: ct = v["CountsTowardTarget"]
    seat_types[str(st)] += 1; counts_flag[str(ct)] += 1
    if st == "congregation": cong.append(e)
r["furniture_psets"] = dict(pset_names); r["seat_types"] = dict(seat_types); r["counts_flag"] = dict(counts_flag)
r["seat_storeys"] = dict(Counter(cont.get(e.id(), "NONE") for e in cong))
# positions vs schedule
sched = {row["seat_id"]: row for row in csv.DictReader(open(ROOT + r"\reports\seating_schedule.csv", encoding="utf-8"))}
dev = 0; missing = 0; names = Counter()
for e in cong:
    names[e.Name] += 1
    m = up.get_local_placement(e.ObjectPlacement)
    s = sched.get(e.Name)
    if not s: missing += 1; continue
    dev = max(dev, abs(m[0, 3] - float(s["x"])), abs(m[1, 3] - float(s["y"])), abs(m[2, 3] - float(s["z_floor"])))
r["cong_seat_ifc"] = len(cong); r["cong_seat_not_in_schedule"] = missing; r["cong_dup_names"] = sum(v - 1 for v in names.values() if v > 1)
r["cong_seat_pos_max_dev"] = dev
# Type objects
r["types"] = dict(Counter(t.is_a() for t in f.by_type("IfcTypeObject")))
# quantities
r["element_quantity_sets"] = len(f.by_type("IfcElementQuantity"))
qnames = Counter()
for q in f.by_type("IfcElementQuantity"): qnames[q.Name] += 1
r["qto_names"] = dict(qnames)
# spaces areas vs schedule
sp_sched = {row["space_id"]: row for row in csv.DictReader(open(ROOT + r"\reports\space_schedule.csv", encoding="utf-8"))}
sp = []
for s in f.by_type("IfcSpace"):
    ps = ue.get_psets(s)
    area = None
    for k, v in ps.items():
        for kk, vv in v.items():
            if "Area" in kk and isinstance(vv, float): area = vv
    sp.append((s.Name, s.LongName, area, cont.get(s.id())))
r["spaces"] = sp
# grids
g = f.by_type("IfcGrid")
r["grids"] = [(x.Name, len(x.UAxes), len(x.VAxes), [a.AxisTag for a in x.UAxes], [a.AxisTag for a in x.VAxes]) for x in g]
# psets on structural elements
r["column_psets_sample"] = ue.get_psets(f.by_type("IfcColumn")[0])
r["column_sample_name"] = f.by_type("IfcColumn")[0].Name
r["truss_assembly_parts"] = [(a.Name, sum(len(rel.RelatedObjects) for rel in a.IsDecomposedBy)) for a in f.by_type("IfcElementAssembly")]
# Material assignments
r["material_assoc"] = len(f.by_type("IfcRelAssociatesMaterial"))
r["materials"] = [m.Name for m in f.by_type("IfcMaterial")]
# classification
r["classification_refs"] = len(f.by_type("IfcClassificationReference"))
# check door psets + opening fills
r["fills"] = len(f.by_type("IfcRelFillsElement")); r["voids"] = len(f.by_type("IfcRelVoidsElement"))
r["door_sample_psets"] = ue.get_psets(f.by_type("IfcDoor")[0]); r["door_sample"] = f.by_type("IfcDoor")[0].Name
# Representation types
reps = Counter()
for p in f.by_type("IfcProduct"):
    if p.Representation:
        for rr in p.Representation.Representations: reps[rr.RepresentationType] += 1
r["rep_types"] = dict(reps)
# search for compliance-type claims in strings
words = ["compliant", "complies", "approved", "certified", "SANS", "Eurocode", "BS ", "kN"]
hits = Counter()
for e in f:
    for a in e:
        if isinstance(a, str):
            for w in words:
                if w.lower() in a.lower(): hits[w] += 1
r["string_claim_hits"] = dict(hits)
json.dump(r, open(ROOT + r"\reviews\iteration-01-work\reviewer_ifc_check.json", "w"), indent=1, default=str)
print("IFC_DONE")
