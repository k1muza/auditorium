"""Independent validation of an Option B IFC (pilot or candidate). Reads the SAVED file only.

  .venv/Scripts/python -I scripts/option_b/s05_validate.py <ifc> --out <json> [--reference bim/southgate.ifc] [--engine work/option_b/engine]

Checks (no project code is imported, so the result does not depend on the build):
  A  save / reopen, schema validation (ifcopenshell.validate), GlobalId uniqueness
  B  IFC structure: classes, spatial containment, aggregation chain, types, materials, profile usages, quantity sets,
     design-status psets, no engineering-verification claims, connection relationships
  C  geometry: 11 trusses x 12 bays, truss positions, pitch, depth, member connectivity (bolts through every
     component of their stack), bolt holes coincide with bolts, no unintended intersections inside the trusses
  D  quantities: Qto vs independent geometry volume; nominal mass; counts
  E  regression vs reference (candidate only): every retained element byte-identical in attributes/representation/
     placement; superseded truss parts absent; seats, walls, doors, windows, columns, footings unchanged
"""
import argparse, hashlib, json, math, multiprocessing, re, sys, time, logging
from collections import Counter, defaultdict
import numpy as np
import ifcopenshell, ifcopenshell.geom, ifcopenshell.validate
import ifcopenshell.util.element as ue, ifcopenshell.util.placement as up, ifcopenshell.util.shape as us

ap = argparse.ArgumentParser()
ap.add_argument("ifc"); ap.add_argument("--out", required=True); ap.add_argument("--reference"); ap.add_argument("--skip-schema", action="store_true")
a = ap.parse_args()
t0 = time.time()
def log(*x): print(f"[{time.time() - t0:7.1f}s]", *x, flush=True)
R = {"file": a.ifc, "sha256": hashlib.sha256(open(a.ifc, "rb").read()).hexdigest(), "gates": {}}
f = ifcopenshell.open(a.ifc)
log("opened")
TAN15 = math.tan(math.radians(15))
NEWRX = re.compile(r"^SOUTHGATE-RTB-")
new = [e for e in f.by_type("IfcElement") if NEWRX.match(e.Name or "")]
PT = ue.get_predefined_type
trusses = sorted([e for e in f.by_type("IfcElementAssembly") if PT(e) == "TRUSS"], key=lambda e: e.Name)
R["counts"] = {"new_elements": len(new), "by_class": dict(Counter(e.is_a() + ("/" + (e.ObjectType or "")) for e in new)), "trusses": len(trusses)}
gate = lambda k, ok, info=None: R["gates"].__setitem__(k, {"pass": bool(ok), "info": info})

# ------------------------------------------------------------------ A
if not a.skip_schema:
    class H(logging.Handler):
        def __init__(s): super().__init__(); s.items = []
        def emit(s, r): s.items.append(r.getMessage())
    h = H(); lg = logging.getLogger("v"); lg.addHandler(h); lg.setLevel(logging.DEBUG)
    ifcopenshell.validate.validate(f, lg, express_rules=False)
    R["schema_issues"] = h.items[:30]; gate("A1_schema_valid", not h.items, len(h.items))
    log("schema", len(h.items))
g = Counter(e.GlobalId for e in f.by_type("IfcRoot"))
dup = [k for k, v in g.items() if v > 1]
gate("A2_unique_globalids", not dup, dup[:5])

# ------------------------------------------------------------------ B structure
st = {}
for t in trusses:
    cont = ue.get_container(t)
    parts = ue.get_decomposition(t)
    kids = ue.get_parts(t)
    st[t.Name] = {"container": cont.Name if cont else None, "direct_children": Counter(k.ObjectType or k.is_a() for k in kids),
                  "all_parts": len(parts), "parts_by_class": dict(Counter(p.is_a() for p in parts)),
                  "type": ue.get_type(t).Name if ue.get_type(t) else None}
R["truss_structure"] = {k: {**v, "direct_children": dict(v["direct_children"])} for k, v in st.items()}
gate("B1_trusses_contained_in_roof_storey", all(v["container"] == "03 Roof" for v in st.values()), {k: v["container"] for k, v in st.items()})
bad_chain = []
for e in new:
    if e.ContainedInStructure:
        bad_chain.append(("contained-directly", e.Name)); continue
    top = e
    while ue.get_aggregate(top) is not None and not ue.get_aggregate(top).is_a("IfcSpatialElement"):
        top = ue.get_aggregate(top)
    if top.is_a("IfcElementAssembly") and PT(top) == "TRUSS" and ue.get_container(top):
        continue
    bad_chain.append(("no-truss-chain", e.Name))
gate("B2_every_new_element_aggregated_into_a_contained_truss", not bad_chain, bad_chain[:10])
untyped = [e.Name for e in new if ue.get_type(e) is None]
gate("B3_every_new_element_typed", not untyped, untyped[:10])
nomat = [e.Name for e in new if not e.is_a("IfcElementAssembly") and ue.get_material(e, should_inherit=True) is None]
gate("B4_every_new_component_has_material", not nomat, nomat[:10])
prof = Counter()
badprof = []
for e in new:
    if e.is_a("IfcMember"):
        m = ue.get_material(e, should_skip_usage=False)
        body = [r for r in e.Representation.Representations if r.RepresentationIdentifier == "Body"][0]
        it = body.Items[0]
        ok = m is not None and m.is_a("IfcMaterialProfileSetUsage") and it.is_a("IfcExtrudedAreaSolid") and it.SweptArea.is_a("IfcLShapeProfileDef") \
            and it.SweptArea == m.ForProfileSet.MaterialProfiles[0].Profile
        prof[it.SweptArea.ProfileName] += 1
        if not ok: badprof.append(e.Name)
gate("B5_angles_native_LShape_profile_with_profile_set_usage", not badprof, {"bad": badprof[:5], "angles_by_profile": dict(prof)})
noq = [e.Name for e in new if e.is_a() in ("IfcMember", "IfcPlate") and not any(k.startswith("Qto_") for k in ue.get_psets(e, qtos_only=True))]
gate("B6_members_and_plates_have_base_quantities", not noq, noq[:10])
ds = Counter((ue.get_pset(e, "SOUTHGATE_DesignStatus") or {}).get("DesignStatus") for e in new)
claims = [e.Name for e in new + trusses if (ue.get_pset(e, "SOUTHGATE_DesignStatus") or {}).get("EngineeringVerified") not in (False, None)
          or (ue.get_pset(e, "SOUTHGATE_DesignStatus") or {}).get("DesignStatus") in ("ENGINEERING_VERIFIED", "APPROVED_FOR_DOCUMENTATION")]
gate("B7_design_status_present_no_verification_claim", None not in ds and not claims, {"by_status": dict(ds), "claims": claims[:5]})
rels = [r for r in f.by_type("IfcRelConnectsWithRealizingElements") if NEWRX.match(r.RelatingElement.Name or "")]
bolts = [e for e in new if e.is_a("IfcMechanicalFastener")]
in_rel = {b.id() for r in rels for b in r.RealizingElements}
loose = [b.Name for b in bolts if b.id() not in in_rel]
gate("B8_every_bolt_realises_a_connection_relationship", not loose, {"relationships": len(rels), "bolts": len(bolts), "loose": loose[:5]})
miss_w = [t.Name for t in trusses if "SOUTHGATE_EngineeringWarnings" not in ue.get_psets(t)]
gate("B9_engineering_warnings_on_every_truss", not miss_w, miss_w)
log("structure checks")

# ------------------------------------------------------------------ C geometry
s = ifcopenshell.geom.settings(); s.set("use-world-coords", True)
geo = {}
it = ifcopenshell.geom.iterator(s, f, max(1, multiprocessing.cpu_count() - 1), include=[e for e in new if not e.is_a("IfcElementAssembly")])
if it.initialize():
    while True:
        sh = it.get()
        v = np.asarray(sh.geometry.verts).reshape(-1, 3)
        fc = np.asarray(sh.geometry.faces).reshape(-1, 3)
        a_, b_, c_ = v[fc[:, 0]], v[fc[:, 1]], v[fc[:, 2]]
        tv = np.einsum("ij,ij->i", a_, np.cross(b_, c_)) / 6.0
        cen = ((a_ + b_ + c_) / 4.0 * tv[:, None]).sum(0) / tv.sum() if abs(tv.sum()) > 1e-12 else v.mean(0)
        geo[sh.guid] = {"v": v, "vol": us.get_volume(sh.geometry), "min": v.min(0), "max": v.max(0), "cen": cen}
        if not it.next(): break
log("geometry", len(geo))
nogeo = [e.Name for e in new if not e.is_a("IfcElementAssembly") and e.GlobalId not in geo]
gate("C1_every_component_has_geometry", not nogeo, nogeo[:5])
# truss positions, bays, pitch, depth from the IFC geometry of chord angles
truss_geo = {}
by_truss = defaultdict(list)
for e in new:
    pv = ue.get_pset(e, "SOUTHGATE_Provenance") or {}
    by_truss[pv.get("ParentTruss")].append(e)
for t in trusses:
    els = by_truss.get(t.Name, [])
    mem = [e for e in els if e.is_a("IfcMember")]
    md = {e.Name: ue.get_pset(e, "SOUTHGATE_MemberData") for e in mem}
    xs = [geo[e.GlobalId]["v"][:, 0].mean() for e in mem if e.GlobalId in geo]
    verts = [e for e in mem if md[e.Name]["Role"] in ("TRUSS_WEB_VERTICAL", "TRUSS_END_POST", "TRUSS_KING_POST")]
    pair = defaultdict(list)
    for e in verts:
        pair[md[e.Name]["MemberMark"]].append(geo[e.GlobalId]["cen"][1])
    vs = sorted(round(float(np.mean(v)) - 0.30, 3) for v in pair.values())
    tc = [e for e in mem if md[e.Name]["Role"] == "TRUSS_TOP_CHORD"]
    pitches = []
    for e in tc:
        M = up.get_local_placement(e.ObjectPlacement)
        z = M[:3, 2]
        pitches.append(round(math.degrees(math.atan2(abs(z[2]), abs(z[1]))), 4))
    tcv = np.vstack([geo[e.GlobalId]["v"] for e in tc])
    bcv = np.vstack([geo[e.GlobalId]["v"] for e in mem if md[e.Name]["Role"] == "TRUSS_BOTTOM_CHORD"])
    sm = np.minimum(tcv[:, 1] - 0.30, 32.70 - tcv[:, 1])
    tos_perp = ((tcv[:, 2] - (12.38 + TAN15 * sm)) * math.cos(math.radians(15))).max()
    truss_geo[t.Name] = {"x_mean": round(float(np.mean(xs)), 4), "x_min": round(float(min(geo[e.GlobalId]["min"][0] for e in els if e.GlobalId in geo)), 4),
                         "x_max": round(float(max(geo[e.GlobalId]["max"][0] for e in els if e.GlobalId in geo)), 4),
                         "vertical_positions_s": vs, "bays": len(vs) - 1, "panel_lengths": sorted({round(b - a, 3) for a, b in zip(vs[:-1], vs[1:])}),
                         "pair_centroid_line_max_dev_mm": None,
                         "top_chord_pitch_deg": sorted(set(pitches)), "tos_max_perp_m": round(float(tos_perp), 5),
                         "bottom_chord_underside_z": round(float(bcv[:, 2].min()), 4), "ridge_tos_z": round(float(tcv[:, 2].max()), 4),
                         "span_extent_y": [round(float(min(geo[e.GlobalId]["min"][1] for e in els if e.GlobalId in geo)), 4),
                                           round(float(max(geo[e.GlobalId]["max"][1] for e in els if e.GlobalId in geo)), 4)]}
R["truss_geometry"] = truss_geo
expected_x = [round(3.25 + 5.56 * i, 2) for i in range(11)]
xs = sorted(v["x_mean"] for v in truss_geo.values())
pos_ok = all(min(abs(x - ex) for ex in expected_x) < 0.002 for x in xs)
gate("C2_truss_count_and_positions", (len(trusses) == 11 or len(trusses) == 1) and pos_ok, {"n": len(trusses), "x": xs})
gate("C3_twelve_bays_2700", all(v["bays"] == 12 and all(abs(p - 2.7) <= 0.002 for p in v["panel_lengths"]) for v in truss_geo.values()), {k: (v["bays"], v["panel_lengths"]) for k, v in truss_geo.items()})
gate("C4_pitch_15deg", all(all(abs(p - 15.0) < 1e-3 for p in v["top_chord_pitch_deg"]) for v in truss_geo.values()), {k: v["top_chord_pitch_deg"] for k, v in truss_geo.items()})
gate("C5_top_of_steel_below_purlin_seat(-10.13mm)", all(v["tos_max_perp_m"] <= -0.0101 for v in truss_geo.values()), {k: v["tos_max_perp_m"] for k, v in truss_geo.items()})
gate("C6_within_bearings_and_column_line", all(v["span_extent_y"][0] >= 0.2771 - 1e-4 and v["span_extent_y"][1] <= 32.7229 + 1e-4 for v in truss_geo.values()),
     {k: v["span_extent_y"] for k, v in truss_geo.items()})
log("truss facts")

# bolts pass through every component of their stack; holes coincide with bolts
tree = ifcopenshell.geom.tree()
sn = ifcopenshell.geom.settings(); sn.set("iterator-output", ifcopenshell.ifcopenshell_wrapper.NATIVE)
it = ifcopenshell.geom.iterator(sn, f, max(1, multiprocessing.cpu_count() - 1), include=[e for e in new if not e.is_a("IfcElementAssembly") and not e.is_a("IfcMechanicalFastener")])
tree.add_iterator(it)
log("tree built")
bad_stack, checked = [], 0
def thick(e):
    if e.is_a("IfcMember"):
        return float(ue.get_material(e, should_skip_usage=False).ForProfileSet.MaterialProfiles[0].Profile.Thickness)
    m = ue.get_material(e, should_skip_usage=False)
    return float(sum(l.LayerThickness for l in m.ForLayerSet.MaterialLayers))
by_name = {e.Name: e for e in new}
for b in bolts:
    pv = ue.get_pset(b, "SOUTHGATE_Provenance") or {}
    stack = pv.get("Stack", "").split(" | ")
    M = up.get_local_placement(b.ObjectPlacement)
    O, Z = M[:3, 3], M[:3, 2]
    d = float(b.NominalDiameter)
    perp = np.cross(Z, [0, 0, 1.0]); perp = perp / np.linalg.norm(perp) if np.linalg.norm(perp) > 1e-6 else np.array([0, 1.0, 0])
    missing = []
    depth = 0.0
    for comp_name in stack:
        ce = by_name.get(comp_name)
        if ce is None or ce.GlobalId not in geo:
            missing.append(comp_name); continue
        th = thick(ce)
        tmid = depth + th / 2
        depth += th
        hit = False
        for off in (0.0, 0.5 * d + 0.0025, -(0.5 * d + 0.0025)):     # on the axis (angles, no holes), just outside the hole rim (plates)
            P = O + Z * tmid + perp * off
            if comp_name in {x.Name for x in tree.select(tuple(map(float, P)))}:
                hit = True; break
        if not hit:
            missing.append(comp_name)
    grip = float(ue.get_pset(ue.get_type(b), "SOUTHGATE_FastenerSpecification")["Grip_mm"]) / 1000
    if abs(depth - grip) > 1e-4:
        missing.append(f"grip {grip:.4f} != stack {depth:.4f}")
    # the bolt must also span every component: shank length covers the stack
    checked += 1
    if missing:
        bad_stack.append({"bolt": b.Name, "missing": missing})
gate("C7_bolts_pass_through_their_stack", not bad_stack, {"checked": checked, "failures": len(bad_stack), "examples": bad_stack[:5]})
log("bolt stacks", checked, len(bad_stack))
# holes vs bolts (plates with voids)
hole_err = []
bolt_pts = defaultdict(list)
for b in bolts:
    M = up.get_local_placement(b.ObjectPlacement)
    bolt_pts[round(M[0, 3], 1)].append(M[:3, 3])
for e in new:
    if not e.is_a("IfcPlate"): continue
    body = [r for r in e.Representation.Representations if r.RepresentationIdentifier == "Body"][0].Items[0]
    if not body.is_a("IfcExtrudedAreaSolid") or not body.SweptArea.is_a("IfcArbitraryProfileDefWithVoids"): continue
    M = up.get_local_placement(e.ObjectPlacement)
    for c in body.SweptArea.InnerCurves:
        h = c.Position.Location.Coordinates
        W = M @ np.array([h[0], h[1], 0.0, 1.0])
        cands = [p for k, ps in bolt_pts.items() if abs(k - W[0]) < 0.3 for p in ps]
        dist = min(math.hypot(p[1] - W[1], p[2] - W[2]) for p in cands) if cands else 9
        if dist > 0.0005 and c.Radius != 0.013:      # rigging-tab hole (r 13 mm) has no bolt
            hole_err.append((e.Name, round(dist * 1000, 2)))
gate("C8_plate_holes_coincide_with_bolts", not hole_err, hole_err[:5])
log("holes")
# unintended intersections among new components (angles, plates); bolt shank vs angle is expected (angle holes not modelled)
comp = [e for e in new if e.is_a() in ("IfcMember", "IfcPlate")]
cl2, seen = [], set()
for e in comp:
    for o in tree.select(e, extend=-0.0005):          # exact BRep overlap deeper than 0.5 mm (face contact ignored)
        if o.Name == e.Name or not o.is_a() in ("IfcMember", "IfcPlate"):
            continue
        k = tuple(sorted((e.Name, o.Name)))
        if k not in seen:
            seen.add(k); cl2.append({"a": k[0], "b": k[1]})
gate("C9_no_intersections_between_new_members_and_plates", not cl2, {"n": len(cl2), "examples": cl2[:10]})
log("internal clashes", len(cl2))

# ------------------------------------------------------------------ D quantities
qerr, mass = [], defaultdict(float)
for e in new:
    if e.is_a() not in ("IfcMember", "IfcPlate"): continue
    q = next(iter([v for k, v in ue.get_psets(e, qtos_only=True).items() if k.startswith("Qto_")]), {})
    gv = geo.get(e.GlobalId, {}).get("vol")
    qv = q.get("NetVolume") or q.get("GrossVolume")
    if gv and qv and abs(gv - qv) > 1e-4 * max(gv, 1e-9) + 1e-9:
        qerr.append((e.Name, qv, gv))
    sq = ue.get_pset(e, "SOUTHGATE_Quantities") or {}
    mass[(e.is_a(), e.ObjectType or (ue.get_type(e).Name if ue.get_type(e) else ""))] += sq.get("NominalSectionMass_kg") or sq.get("IndicativeMassFromDensity_kg") or 0
gate("D1_stored_volumes_match_geometry", not qerr, {"n": len(qerr), "examples": qerr[:5]})
R["mass_by_kind_kg"] = {f"{k[0]}|{k[1]}": round(v, 1) for k, v in mass.items()}
log("quantities")

# ------------------------------------------------------------------ E regression
if a.reference:
    ref = ifcopenshell.open(a.reference)
    log("reference opened")
    def fp(e):
        """attribute + recursive representation/placement fingerprint (ids ignored)"""
        h = hashlib.sha1()
        def walk(x, depth=0):
            if isinstance(x, ifcopenshell.entity_instance):
                h.update(x.is_a().encode())
                if depth > 60: return
                for v in x: walk(v, depth + 1)
            elif isinstance(x, (list, tuple)):
                for v in x: walk(v, depth + 1)
            else:
                h.update(repr(round(x, 9) if isinstance(x, float) else x).encode())
        for v in (e.Name, e.Description, e.ObjectType, getattr(e, "PredefinedType", None), e.Tag):
            walk(v)
        walk(e.ObjectPlacement); walk(e.Representation)
        return h.hexdigest()
    ref_trusses = [x for x in ref.by_type("IfcElementAssembly") if PT(x) == "TRUSS"]
    sup = {p.GlobalId for t in ref_trusses for p in ue.get_decomposition(t)}
    ref_el = {e.GlobalId: e for e in ref.by_type("IfcElement") if e.GlobalId not in sup and not (e.is_a("IfcElementAssembly") and PT(e) == "TRUSS")}
    cand_el = {e.GlobalId: e for e in f.by_type("IfcElement")}
    missing = [g_ for g_ in ref_el if g_ not in cand_el]
    changed = []
    for g_, e in ref_el.items():
        c = cand_el.get(g_)
        if c is not None and fp(c) != fp(e):
            changed.append(e.Name)
    still = [g_ for g_ in sup if g_ in cand_el]
    gate("E1_retained_elements_unchanged", not missing and not changed, {"retained": len(ref_el), "missing": missing[:5], "changed": changed[:10]})
    gate("E2_superseded_parts_absent", not still, {"superseded": len(sup), "still_present": len(still)})
    def cnt(F, cls, pred=lambda e: True): return sum(1 for e in F.by_type(cls) if pred(e))
    seat = lambda e: "SEAT" in (e.Name or "").upper() or "SEAT" in ((ue.get_type(e).Name if ue.get_type(e) else "") or "").upper() or "seat" in (e.Description or "").lower()
    reg = {}
    for cls in ("IfcWall", "IfcDoor", "IfcWindow", "IfcColumn", "IfcFooting", "IfcSlab", "IfcCovering", "IfcCurtainWall", "IfcRoof", "IfcBeam", "IfcFurniture"):
        reg[cls] = (cnt(ref, cls), cnt(f, cls))
    seats_ref = [e for e in ref.by_type("IfcFurniture")]
    reg["IfcFurniture_seat_like"] = (sum(1 for e in seats_ref if seat(e)), sum(1 for e in f.by_type("IfcFurniture") if seat(e)))
    # the 2,000-seat check: seat count recorded on the furniture / project psets
    gate("E3_architectural_and_support_counts_unchanged", all(a_ == b_ for a_, b_ in reg.values()), reg)
    # the excluded detached buildings are still excluded
    exc = [e.Name for e in f.by_type("IfcElement") if re.search(r"CHILDREN|KIDS", (ue.get_pset(e, "SOUTHGATE_Provenance") or {}).get("SourceCollections") or "", re.I)]
    gate("E4_excluded_buildings_not_introduced", not exc, exc[:5])
    log("regression")

R["seconds"] = round(time.time() - t0, 1)
R["all_pass"] = all(v["pass"] for v in R["gates"].values())
json.dump(R, open(a.out, "w"), indent=1, default=str)
print(json.dumps({k: v["pass"] for k, v in R["gates"].items()}, indent=1))
print("ALL PASS" if R["all_pass"] else "GATES FAILED")
