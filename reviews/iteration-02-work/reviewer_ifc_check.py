"""Reviewer (iteration 2) read-only IFC inspection of a COPY of the IFC."""
import json, csv, sys
from collections import Counter, defaultdict
import numpy as np
import ifcopenshell, ifcopenshell.util.element as ue, ifcopenshell.util.placement as up, ifcopenshell.util.unit as uu
import ifcopenshell.geom, ifcopenshell.validate

ROOT = r"C:\Users\Kelvin\Desktop\auditorium"
W = ROOT + r"\reviews\iteration-02-work"
f = ifcopenshell.open(W + r"\model\copy.ifc")
r = {"schema": f.schema, "length_scale": uu.calculate_unit_scale(f)}
r["units"] = [(u.UnitType, u.Prefix, u.Name) for u in f.by_type("IfcProject")[0].UnitsInContext.Units if u.is_a("IfcSIUnit")]
r["hierarchy"] = [len(f.by_type(t)) for t in ("IfcProject", "IfcSite", "IfcBuilding")]
storeys = sorted(f.by_type("IfcBuildingStorey"), key=lambda s: s.Elevation)
r["storeys"] = [(s.Name, s.LongName, s.Elevation) for s in storeys]
cont = {}
for rel in f.by_type("IfcRelContainedInSpatialStructure"):
    for e in rel.RelatedElements:
        cont[e.id()] = rel.RelatingStructure
agg_parent = {}
for rel in f.by_type("IfcRelAggregates"):
    for e in rel.RelatedObjects:
        agg_parent[e.id()] = rel.RelatingObject


def storey_of(e):
    if e.id() in cont:
        return cont[e.id()]
    p = agg_parent.get(e.id())
    while p is not None and not p.is_a("IfcBuildingStorey"):
        if p.id() in cont:
            return cont[p.id()]
        p = agg_parent.get(p.id())
    return p


elems = [e for e in f.by_type("IfcElement") if not e.is_a("IfcFeatureElement")]
r["n_elements"] = len(elems)
r["uncontained"] = [(e.is_a(), e.Name) for e in elems if storey_of(e) is None][:10]
# geometry-based independent storey check: min z of tessellated shape vs storey band
settings = ifcopenshell.geom.settings()
settings.set("use-world-coords", True)
elev = [(s.Name, s.Elevation) for s in storeys]
zinfo = {}
it = ifcopenshell.geom.iterator(settings, f, 4, include=elems + list(f.by_type("IfcSpace")) + list(f.by_type("IfcSpatialZone")))
if it.initialize():
    while True:
        sh = it.get()
        v = np.array(sh.geometry.verts).reshape(-1, 3)
        zinfo[sh.id] = (v.min(0).tolist(), v.max(0).tolist())
        if not it.next():
            break
r["tessellated"] = len(zinfo)
band_viol = []
by_storey_z = defaultdict(list)
for e in elems + list(f.by_type("IfcSpace")) + list(f.by_type("IfcSpatialZone")):
    s = storey_of(e) if not e.is_a("IfcSpatialElement") else (agg_parent.get(e.id()) or cont.get(e.id()))
    if s is None or e.id() not in zinfo:
        continue
    zmin = zinfo[e.id()][0][2]
    zmax = zinfo[e.id()][1][2]
    by_storey_z[s.Name].append(zmin)
    idx = [n for n, _ in elev].index(s.Name) if s.Name in [n for n, _ in elev] else None
    if idx is None:
        continue
    lo = elev[idx][1]
    hi = elev[idx + 1][1] if idx + 1 < len(elev) else 1e9
    # element must have some part within [lo, hi) and its base not >= next storey
    if zmin >= hi - 1e-6 or zmax < lo - 1.0:
        band_viol.append((e.is_a(), e.Name, s.Name, round(zmin, 3), round(zmax, 3)))
r["storey_band_violations_count"] = len(band_viol)
r["storey_band_violations"] = band_viol[:40]
r["storey_zmin_range"] = {k: [round(min(v), 2), round(max(v), 2), len(v)] for k, v in by_storey_z.items()}
# named elements and their storeys
watch = ["STR-BRACE-GABLE-11-DEa", "STR-BRACE-GABLE-3-DEa", "WN-BOOTH-VIEW", "SRV-02-ZONE", "STR-BEAM-MEZZ-2-CD",
         "ARC-CHOIR-TIER-1", "ENV-WALL-HALL-W", "ENV-WALL-GABLE-REAR", "ENV-ROOF-HALL-E", "ARC-SLAB-REAR-PLATFORM",
         "ACC-REFUGE-1-1", "ARC-WALL-LIFT-E", "SRV-01-ZONE", "ARC-BOOTH-FLOOR", "SPC-SP-08"]
byname = {}
for e in f.by_type("IfcProduct"):
    byname.setdefault(e.Name, e)
r["watch"] = {}
for n in watch:
    e = byname.get(n)
    if e is None:
        r["watch"][n] = None
        continue
    s = storey_of(e) if not e.is_a("IfcSpatialElement") else (agg_parent.get(e.id()) or cont.get(e.id()))
    r["watch"][n] = {"class": e.is_a(), "ptype": getattr(e, "PredefinedType", None), "otype": getattr(e, "ObjectType", None),
                     "storey": s.Name if s else None, "z": [round(zinfo[e.id()][0][2], 3), round(zinfo[e.id()][1][2], 3)] if e.id() in zinfo else None,
                     "psets": ue.get_psets(e)}
# materials
mat_rel = {}
for rel in f.by_type("IfcRelAssociatesMaterial"):
    for o in rel.RelatedObjects:
        mat_rel[o.id()] = rel.RelatingMaterial
no_mat = Counter()
for e in elems:
    m = ue.get_material(e)
    if m is None:
        no_mat[e.is_a()] += 1
r["elements_without_material_by_class"] = dict(no_mat)
r["materials"] = sorted({m.Name for m in f.by_type("IfcMaterial")})
r["material_by_class_sample"] = {}
for cls in ("IfcColumn", "IfcBeam", "IfcMember", "IfcSlab", "IfcWall", "IfcFooting", "IfcFurniture", "IfcDoor", "IfcStair", "IfcRamp"):
    es = f.by_type(cls)
    r["material_by_class_sample"][cls] = dict(Counter(getattr(ue.get_material(e), "Name", None) for e in es))
# quantities
q = Counter()
qmissing = Counter()
qsample = {}
for e in elems:
    qs = {k: v for k, v in ue.get_psets(e, qtos_only=True).items()}
    if qs:
        for k in qs:
            q[k] += 1
        if e.is_a() not in qsample:
            qsample[e.is_a()] = (e.Name, qs)
    else:
        qmissing[e.is_a()] += 1
r["qto_names"] = dict(q)
r["qto_missing_by_class"] = dict(qmissing)
r["qto_sample"] = qsample
# check a quantity against geometry: column length vs tessellated z extent
cdev = []
for c in f.by_type("IfcColumn"):
    qs = ue.get_psets(c, qtos_only=True)
    L = None
    for k, v in qs.items():
        L = v.get("Length", L)
    if L and c.id() in zinfo:
        cdev.append(abs(L - (zinfo[c.id()][1][2] - zinfo[c.id()][0][2])))
r["column_length_vs_geom_maxdev"] = max(cdev) if cdev else None
r["columns_with_length_q"] = len(cdev)
# shear walls
r["wall_ptypes"] = dict(Counter((w.PredefinedType) for w in f.by_type("IfcWall")))
r["lift_walls"] = {w.Name: w.PredefinedType for w in f.by_type("IfcWall") if "LIFT" in (w.Name or "")}
# refuges
ref = [z for z in f.by_type("IfcSpatialZone") if (z.ObjectType or "") == "RefugeSpace" or "REFUGE" in (z.Name or "")]
r["refuge_zones"] = [(z.Name, z.ObjectType, (agg_parent.get(z.id()) or cont.get(z.id()) or type("x", (), {"Name": None})).Name,
                      [round(x, 2) for x in zinfo[z.id()][0]] + [round(x, 2) for x in zinfo[z.id()][1]] if z.id() in zinfo else None) for z in ref]
r["zone_rel"] = {"IfcRelReferencedInSpatialStructure": len(f.by_type("IfcRelReferencedInSpatialStructure"))}
# seats
cong = []
for e in f.by_type("IfcFurniture"):
    ps = ue.get_psets(e)
    flat = {k2: v2 for v in ps.values() for k2, v2 in v.items()}
    if flat.get("SeatType") == "congregation" and flat.get("CountsTowardTarget") is True:
        cong.append(e)
r["congregation_seats"] = len(cong)
sched = {row["seat_id"]: row for row in csv.DictReader(open(ROOT + r"\reports\seating_schedule.csv", encoding="utf-8"))}
dev = 0
miss = 0
for e in cong:
    m = up.get_local_placement(e.ObjectPlacement)
    s = sched.get(e.Name)
    if not s:
        miss += 1
        continue
    dev = max(dev, abs(m[0, 3] - float(s["x"])), abs(m[1, 3] - float(s["y"])), abs(m[2, 3] - float(s["z_floor"])))
r["seat_not_in_csv"] = miss
r["seat_pos_max_dev"] = dev
r["seat_storeys"] = dict(Counter(storey_of(e).Name for e in cong))
# space overlaps (bbox) per storey, plus areas vs schedule
sp = [s for s in f.by_type("IfcSpace")]
spb = {s.Name: (zinfo[s.id()] if s.id() in zinfo else None) for s in sp}
ovl = []
names = list(spb)
for i, a in enumerate(names):
    for b in names[i + 1:]:
        A, B = spb[a], spb[b]
        if A and B and all(A[0][k] < B[1][k] - 0.01 and B[0][k] < A[1][k] - 0.01 for k in range(3)):
            ovl.append((a, b))
r["space_bbox_overlaps_3d"] = ovl
r["space_areas"] = {}
for s in sp:
    qs = ue.get_psets(s, qtos_only=True)
    r["space_areas"][s.Name] = {k: v.get("GrossFloorArea") or v.get("NetFloorArea") for k, v in qs.items()}
# grid
r["grids"] = [(g.Name, [a.AxisTag for a in g.UAxes], [a.AxisTag for a in g.VAxes]) for g in f.by_type("IfcGrid")]
# claims in strings
words = ["compliant", "complies", "compliance", "approved", "certified", "SANS", "Eurocode", "BS ", "kN", "fire rated", "designed"]
hits = defaultdict(list)
for e in f:
    for a in e:
        if isinstance(a, str):
            for w in words:
                if w.lower() in a.lower() and len(hits[w]) < 4:
                    hits[w].append(a[:120])
r["string_claim_hits"] = dict(hits)
# schema validation
logger = ifcopenshell.validate.json_logger()
ifcopenshell.validate.validate(f, logger, express_rules=False)
r["schema_validation_messages"] = len(logger.statements)
r["schema_validation_first"] = [str(s)[:200] for s in logger.statements[:5]]
json.dump(r, open(W + r"\reviewer_ifc_check.json", "w"), indent=1, default=str)
print("IFC_DONE")
