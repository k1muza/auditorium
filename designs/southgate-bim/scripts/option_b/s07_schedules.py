"""Stage 6 - quantity schedules and preliminary BOQ extract, read from the candidate IFC ONLY.

  .venv/Scripts/python -I scripts/option_b/s07_schedules.py <candidate.ifc> <outdir>

Every row carries a MeasurementStatus:
  MODEL_DERIVED         counted / measured from modelled IFC components (geometry or parameters)
  ASSUMPTION_DEPENDENT  modelled, but the count or size follows an unapproved placeholder rule (bolts, packers, splice plates)
  PRELIMINARY_ESTIMATE  R2 appraisal figure (reference only)
  NOT_AVAILABLE         not determinable from the model (rates, waste, welds, bearings, ties)
Measured quantities, waste allowances, procurement quantities, unit rates and amounts are separate columns.
"""
import csv, json, math, re, sys
from collections import Counter, defaultdict
from pathlib import Path
import ifcopenshell, ifcopenshell.util.element as ue, ifcopenshell.geom, ifcopenshell.util.shape as us

src, outdir = sys.argv[1], Path(sys.argv[2])
outdir.mkdir(parents=True, exist_ok=True)
f = ifcopenshell.open(src)
PT = ue.get_predefined_type
trusses = sorted([a for a in f.by_type("IfcElementAssembly") if PT(a) == "TRUSS"], key=lambda a: a.Name)
DENS = 7850.0


def w(name, rows, cols=None):
    cols = cols or list(rows[0].keys())
    with open(outdir / name, "w", newline="", encoding="utf-8") as fh:
        wr = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        wr.writeheader(); wr.writerows(rows)


def tsum(a):
    return ue.get_pset(a, "SOUTHGATE_TrussSummary") or {}


members, plates, bolts = [], [], []
_bm = {}
def bolt_mass(ty):
    """indicative bolt-set mass from the type's simplified geometry (head + shank + washer + nut - nut/shank overlap)"""
    if ty.Name in _bm:
        return _bm[ty.Name]
    st_ = ifcopenshell.geom.settings()
    items = ty.RepresentationMaps[0].MappedRepresentation.Items
    vol = sum(us.get_volume(ifcopenshell.geom.create_shape(st_, it)) for it in items)
    shank_r = items[1].SweptArea.Radius
    vol -= math.pi * shank_r ** 2 * items[3].Depth          # nut hole not modelled: remove the overlap with the shank
    _bm[ty.Name] = round(vol * DENS, 4)
    return _bm[ty.Name]
for t in trusses:
    ts = tsum(t)
    for p in ue.get_decomposition(t):
        q = next(iter([v for k, v in ue.get_psets(p, qtos_only=True).items() if k.startswith("Qto_")]), {})
        sq = ue.get_pset(p, "SOUTHGATE_Quantities") or {}
        pv = ue.get_pset(p, "SOUTHGATE_Provenance") or {}
        ty = ue.get_type(p)
        if p.is_a("IfcMember"):
            md = ue.get_pset(p, "SOUTHGATE_MemberData")
            spec = ue.get_pset(ty, "SOUTHGATE_SteelSpecification")
            members.append({"Truss": t.Name, "TrussType": ts.get("TrussType"), "Line": ts.get("Line"), "MemberMark": md["MemberMark"],
                            "Role": md["Role"], "Angle": md["AngleSide"], "StableId": p.Name, "GlobalId": p.GlobalId, "Profile": md["Section"],
                            "BuiltUpSection": md["BuiltUpSection"], "Type": ty.Name, "CutLength_m": round(q["Length"], 4),
                            "SettingOutLength_m": md["SettingOutLength_m"], "CrossSectionArea_m2": round(q.get("CrossSectionArea", 0), 7),
                            "NetVolume_m3": round(q.get("NetVolume", 0), 7), "kg_per_m": spec["NominalMassPerMetre_kg"],
                            "NominalMass_kg": sq.get("NominalSectionMass_kg"), "GeometryMass_kg": sq.get("IndicativeMassFromDensity_kg"),
                            "OuterSurfaceArea_m2": round(q.get("OuterSurfaceArea", 0), 4) if q.get("OuterSurfaceArea") else None,
                            "R2_Nc_kN": md.get("R2_Nc_kN"), "R2_Nt_kN": md.get("R2_Nt_kN"), "R2_Utilisation": md.get("R2_Utilisation"),
                            "MeasurementStatus": "MODEL_DERIVED", "SizeStatus": md["SizeStatus"], "GeometryStatus": md["GeometryStatus"]})
        elif p.is_a("IfcPlate"):
            pdt = ue.get_pset(p, "SOUTHGATE_PlateData") or {}
            role = PT(p)
            th = float(ue.get_pset(ty, "SOUTHGATE_SteelSpecification")["Thickness_mm"])
            vol = q.get("NetVolume") or q.get("GrossVolume")
            ga = pdt.get("GrossArea_m2") or q.get("GrossArea")
            na = pdt.get("NetArea_m2") or q.get("NetArea") or ga
            plates.append({"Truss": t.Name, "TrussType": ts.get("TrussType"), "Line": ts.get("Line"), "Role": role, "StableId": p.Name,
                           "GlobalId": p.GlobalId, "Parent": pv.get("ParentAssembly"), "PartMark": p.Tag.split("/")[-1] if p.Tag else "",
                           "Type": ty.Name, "Thickness_mm": th, "GrossArea_m2": round(ga, 5) if ga else None, "NetArea_m2": round(na, 5) if na else None,
                           "Holes": pdt.get("Holes", 0), "Volume_m3": round(vol, 7) if vol else None, "Mass_kg": round(vol * DENS, 3) if vol else None,
                           "Perimeter_m": round(q.get("Perimeter", 0), 4) if q.get("Perimeter") else None, "RiggingTab": pdt.get("RiggingTab", False),
                           "MeasurementStatus": "ASSUMPTION_DEPENDENT" if role in ("PACKING_PLATE", "SPLICE_PLATE") else "MODEL_DERIVED",
                           "StatusNote": {"GUSSET_PLATE": "outline from placeholder detailing rules; 10 mm per R2",
                                          "SPLICE_PLATE": "thickness 8 mm placeholder; splice not designed",
                                          "PACKING_PLATE": "count from placeholder spacing rule; size placeholder"}[role]})
        elif p.is_a("IfcMechanicalFastener"):
            fs = ue.get_pset(ty, "SOUTHGATE_FastenerSpecification")
            bolts.append({"Truss": t.Name, "TrussType": ts.get("TrussType"), "Line": ts.get("Line"), "StableId": p.Name, "Type": ty.Name,
                          "Diameter": f"M{round(float(ty.NominalDiameter) * 1000)}", "Length_mm": round(float(ty.NominalLength) * 1000),
                          "Grip_mm": fs["Grip_mm"], "Role": pv.get("BoltRole"), "Parent": pv.get("ParentAssembly"),
                          "Bolt": fs["BoltDesignation"], "Nut": fs["NutDesignation"], "Washer": fs["WasherDesignation"],
                          "NutsPerSet": fs["NutsPerSet"], "WashersPerSet": fs["WashersPerSet"], "IndicativeSetMass_kg": bolt_mass(ty)})

# ---------------------------------------------------------------- 3 structural member schedule
w("structural_member_schedule.csv", members)
prof = defaultdict(lambda: defaultdict(float))
for m in members:
    k = (m["Profile"], m["Role"])
    prof[k]["Angles"] += 1; prof[k]["Length_m"] += m["CutLength_m"]; prof[k]["NominalMass_kg"] += m["NominalMass_kg"]
    prof[k]["GeometryMass_kg"] += m["GeometryMass_kg"]; prof[k]["SettingOutLength_m"] += m["SettingOutLength_m"]; prof[k]["kg_per_m"] = m["kg_per_m"]
rows = [{"Profile": k[0], "Role": k[1], "Angles": int(v["Angles"]), "BuiltUpMembers": int(v["Angles"] / 2), "kg_per_m": v["kg_per_m"],
         "TotalCutLength_m": round(v["Length_m"], 3), "TotalSettingOutLength_m_pairs": round(v["SettingOutLength_m"], 3),
         "NominalMass_kg": round(v["NominalMass_kg"], 1), "GeometryMass_kg": round(v["GeometryMass_kg"], 1),
         "MeasurementStatus": "MODEL_DERIVED", "SizeStatus": "CONCEPT_UNVERIFIED"} for k, v in sorted(prof.items())]
w("member_schedule_by_profile_and_role.csv", rows)
byp = defaultdict(lambda: defaultdict(float))
for m in members:
    byp[m["Profile"]]["Angles"] += 1; byp[m["Profile"]]["Length_m"] += m["CutLength_m"]; byp[m["Profile"]]["Mass_kg"] += m["NominalMass_kg"]
    byp[m["Profile"]]["GeoMass_kg"] += m["GeometryMass_kg"]; byp[m["Profile"]]["kg_m"] = m["kg_per_m"]
# stock cutting (6 m bars, first-fit decreasing, 3 mm saw kerf placeholder)
cut = {}
for pname in byp:
    L = sorted([m["CutLength_m"] for m in members if m["Profile"] == pname], reverse=True)
    bars = []
    for x in L:
        for i, rem in enumerate(bars):
            if rem >= x + 0.003:
                bars[i] -= x + 0.003; break
        else:
            bars.append(6.0 - x - 0.003)
    cut[pname] = {"bars": len(bars), "offcut_m": round(sum(bars), 3)}
rows = [{"Profile": p, "Angles": int(v["Angles"]), "kg_per_m": v["kg_m"], "MeasuredLength_m": round(v["Length_m"], 3), "MeasuredMass_kg": round(v["Mass_kg"], 1),
         "GeometryMass_kg": round(v["GeoMass_kg"], 1), "MeasurementStatus": "MODEL_DERIVED",
         "Stock6mBars_FFD": cut[p]["bars"], "StockLength_m": cut[p]["bars"] * 6.0, "StockMass_kg": round(cut[p]["bars"] * 6.0 * v["kg_m"], 1),
         "CuttingOffcut_m": cut[p]["offcut_m"], "ProcurementStatus": "ASSUMPTION_DEPENDENT (6 m stock per R2, 3 mm kerf placeholder, no offcut reuse across profiles)"}
        for p, v in sorted(byp.items())]
w("steel_by_profile_with_stock_bars.csv", rows)

# ---------------------------------------------------------------- 4 connection component schedule
w("connection_plate_schedule.csv", plates)
w("bolt_set_schedule.csv", bolts)
pc = defaultdict(lambda: defaultdict(float))
for p in plates:
    k = (p["Role"], p["Thickness_mm"], p["Type"])
    pc[k]["Count"] += 1; pc[k]["GrossArea_m2"] += p["GrossArea_m2"] or 0; pc[k]["NetArea_m2"] += p["NetArea_m2"] or 0; pc[k]["Mass_kg"] += p["Mass_kg"] or 0
    pc[k]["Holes"] += p["Holes"]
marks = defaultdict(set)
for p in plates:
    marks[(p["Role"], p["Thickness_mm"], p["Type"])].add(p["PartMark"])
crow = [{"Component": k[0], "Type": k[2], "Thickness_mm": k[1], "Count": int(v["Count"]), "UniquePartMarks": len(marks[k]),
         "GrossArea_m2": round(v["GrossArea_m2"], 4), "NetArea_m2": round(v["NetArea_m2"], 4), "BoltHoles": int(v["Holes"]), "Mass_kg": round(v["Mass_kg"], 1),
         "MeasurementStatus": "ASSUMPTION_DEPENDENT" if k[0] != "GUSSET_PLATE" else "MODEL_DERIVED"} for k, v in sorted(pc.items())]
bc = Counter((b["Type"], b["Diameter"], b["Length_mm"], b["Grip_mm"], b["Bolt"], b["Nut"], b["Washer"]) for b in bolts)
for k, n in sorted(bc.items()):
    crow.append({"Component": "BOLT_SET", "Type": k[0], "Thickness_mm": None, "Count": n, "UniquePartMarks": 1,
                 "Mass_kg": round(n * _bm[k[0]], 1),
                 "Bolts": n, "Nuts": n, "Washers": n, "Designation": f"{k[4]}; {k[5]}; {k[6]}", "MeasurementStatus": "ASSUMPTION_DEPENDENT"})
w("connection_component_summary.csv", crow, ["Component", "Type", "Thickness_mm", "Count", "UniquePartMarks", "GrossArea_m2", "NetArea_m2", "BoltHoles",
                                               "Mass_kg", "Bolts", "Nuts", "Washers", "Designation", "MeasurementStatus"])

# ---------------------------------------------------------------- 5 truss assembly quantity schedule
tr = []
for t in trusses:
    ts = tsum(t)
    M = [m for m in members if m["Truss"] == t.Name]
    P = [p for p in plates if p["Truss"] == t.Name]
    B = [b for b in bolts if b["Truss"] == t.Name]
    conns = [x for x in ue.get_parts(t) if (x.ObjectType or "").startswith("CONNECTION") or PT(x) and str(PT(x)).startswith("CONNECTION")]
    r = {"Truss": t.Name, "GlobalId": t.GlobalId, "Line": ts.get("Line"), "x_m": ts.get("x_m"), "TrussType": ts.get("TrussType"),
         "Bays": ts.get("Bays"), "DepthAtBearing_m": ts.get("DepthAtBearing_m"), "DepthAtRidge_m": ts.get("DepthAtRidge_m"),
         "BuiltUpMembers": len(M) // 2, "ChordPieces": sum(1 for m in M if "CHORD" in m["Role"]) // 2, "WebMembers": sum(1 for m in M if "CHORD" not in m["Role"]) // 2,
         "Angles": len(M), "AngleLength_m": round(sum(m["CutLength_m"] for m in M), 3), "MemberMassNominal_kg": round(sum(m["NominalMass_kg"] for m in M), 1),
         "MemberMassGeometry_kg": round(sum(m["GeometryMass_kg"] for m in M), 1),
         "ConnectionAssemblies": sum(1 for x in ue.get_parts(t) if x.is_a("IfcElementAssembly") and "-J-" in x.Name),
         "Gussets": sum(1 for p in P if p["Role"] == "GUSSET_PLATE"), "GussetMass_kg": round(sum(p["Mass_kg"] for p in P if p["Role"] == "GUSSET_PLATE"), 1),
         "SplicePlates": sum(1 for p in P if p["Role"] == "SPLICE_PLATE"), "SpliceMass_kg": round(sum(p["Mass_kg"] for p in P if p["Role"] == "SPLICE_PLATE"), 1),
         "PackingPlates": sum(1 for p in P if p["Role"] == "PACKING_PLATE"), "PackerMass_kg": round(sum(p["Mass_kg"] for p in P if p["Role"] == "PACKING_PLATE"), 1),
         "RiggingTabs": sum(1 for p in P if p["RiggingTab"]), "BoltSets": len(B), "BoltSets_M20": sum(1 for b in B if b["Diameter"] == "M20"),
         "BoltSets_M16": sum(1 for b in B if b["Diameter"] == "M16"), "Nuts": len(B), "Washers": len(B)}
    r["PlateMass_kg"] = round(r["GussetMass_kg"] + r["SpliceMass_kg"] + r["PackerMass_kg"], 1)
    r["SteelMassExclBolts_kg"] = round(r["MemberMassNominal_kg"] + r["PlateMass_kg"], 1)
    tr.append(r)
for r in tr:
    r["BoltSetMass_kg"] = round(sum(b["IndicativeSetMass_kg"] for b in bolts if b["Truss"] == r["Truss"]), 1)
    r["TotalSteelIndicative_kg"] = round(r["SteelMassExclBolts_kg"] + r["BoltSetMass_kg"], 1)
tot_keys = [k for k in tr[0] if isinstance(tr[0][k], (int, float)) and k not in ("Line", "x_m", "Bays", "DepthAtBearing_m", "DepthAtRidge_m")]
rows = list(tr)
for tt in sorted({r["TrussType"] for r in tr}):
    sel = [r for r in tr if r["TrussType"] == tt]
    rows.append({"Truss": f"TYPE {tt} ({len(sel)} trusses)", "TrussType": tt, **{k: round(sum(r[k] for r in sel), 1) for k in tot_keys}})
rows.append({"Truss": "ALL 11 TRUSSES", **{k: round(sum(r[k] for r in tr), 1) for k in tot_keys}})
w("truss_assembly_quantity_schedule.csv", rows, list(tr[0].keys()))
TOT = rows[-1]

# ---------------------------------------------------------------- 7 connection type library
lib = []
for t in f.by_type("IfcElementAssemblyType"):
    if not (t.Name or "").startswith("SG-OPTB-"):
        continue
    occ = ue.get_types(t)
    sp = ue.get_pset(t, "SOUTHGATE_AssemblyTypeSpecification") or {}
    kind = "TRUSS" if PT(t) == "TRUSS" else (t.ElementType or "")
    comp = Counter()
    for o in occ[:1]:
        for p in ue.get_parts(o):
            comp[(ue.get_type(p).Name if ue.get_type(p) else p.is_a())] += 1
    lib.append({"TypeName": t.Name, "GlobalId": t.GlobalId, "Kind": "CONNECTION" if kind.startswith("CONNECTION") else kind,
                "Family": sp.get("Family", sp.get("Role", sp.get("TrussType", ""))), "TrussType": sp.get("TrussType", ""),
                "Instances": len(occ), "InstanceIds": ";".join(sorted(o.Name for o in occ))[:2000],
                "ComponentsPerInstance(first)": json.dumps(dict(comp)), "BoltSetsPerInstance": sp.get("BoltSetsPerInstance"),
                "BoltSetsByType": sp.get("BoltSetsByType"), "RiggingTab": sp.get("RiggingTab"), "Description": t.Description,
                "DesignStatus": sp.get("DesignStatus", sp.get("SizeStatus", "CONCEPT_UNVERIFIED")), "BoltPatternStatus": sp.get("BoltPatternStatus", "")})
lib.sort(key=lambda r: (r["Kind"], r["Family"], r["TypeName"]))
w("connection_type_library.csv", lib)
mt = []
for t in f.by_type("IfcMemberType") + f.by_type("IfcPlateType") + f.by_type("IfcMechanicalFastenerType"):
    if not (t.Name or "").startswith("SG-OPTB-"):
        continue
    spec = ue.get_pset(t, "SOUTHGATE_SteelSpecification") or ue.get_pset(t, "SOUTHGATE_FastenerSpecification") or {}
    mt.append({"TypeName": t.Name, "Class": t.is_a(), "GlobalId": t.GlobalId, "Instances": len(ue.get_types(t)),
               "Classification": ";".join(r.RelatingClassification.Identification for r in (t.HasAssociations or []) if r.is_a("IfcRelAssociatesClassification")),
               "Spec": json.dumps({k: v for k, v in spec.items() if k != "id"})[:1500]})
w("component_type_library.csv", sorted(mt, key=lambda r: (r["Class"], r["TypeName"])))

# ---------------------------------------------------------------- 6 preliminary BOQ extract
B = []
def boq(code, desc, unit, qty, status, basis, procurement=None, proc_basis="", note=""):
    B.append({"Code": code, "Description": desc, "Unit": unit, "MeasuredQuantity": qty, "MeasurementStatus": status, "MeasurementBasis": basis,
              "WasteAllowance": "", "WasteStatus": "NOT_AVAILABLE (QS to set)", "ProcurementQuantity": procurement if procurement is not None else "",
              "ProcurementBasis": proc_basis, "UnitRate": "", "RateStatus": "NOT_AVAILABLE (not priced in this extract)", "Amount": "",
              "Notes": note})
for p, v in sorted(byp.items()):
    boq(f"SG-15-FRAMING.{p}", f"Roof trusses: fabricate from paired equal angles {p} (S355JR provisional), cut, drill, assemble (2L back-to-back)", "t",
        round(v["Mass_kg"] / 1000, 3), "MODEL_DERIVED", f"{int(v['Angles'])} angles, {v['Length_m']:.2f} m cut length x {v['kg_m']} kg/m (catalogue nominal)",
        round(cut[p]["bars"] * 6 * v["kg_m"] / 1000, 3), f"{cut[p]['bars']} x 6 m bars (FFD cutting, ASSUMPTION_DEPENDENT)",
        "Member size CONCEPT_UNVERIFIED (R2 indicative) - not for procurement")
g = [r for r in crow if r["Component"] == "GUSSET_PLATE"][0]
boq("SG-15-FITTINGS.GP10", "Gusset plates 10 mm (S355JR provisional), profile cut, drilled", "t", round(g["Mass_kg"] / 1000, 3), "MODEL_DERIVED",
    f"{g['Count']} plates, net area {g['NetArea_m2']:.2f} m2 x 10 mm x 7850 kg/m3 ({g['UniquePartMarks']} unique part marks)", None, "",
    "Outline from placeholder detailing rules; thickness per R2; no gusset design")
for comp, code, desc in (("SPLICE_PLATE", "SG-15-FITTINGS.SP8", "Chord splice plates 8 mm (placeholder thickness), drilled"),
                         ("PACKING_PLATE", "SG-15-FITTINGS.PK10", "Packing plates 10 mm between back-to-back angles")):
    rr = [r for r in crow if r["Component"] == comp]
    boq(code, desc, "t", round(sum(r["Mass_kg"] for r in rr) / 1000, 3), "ASSUMPTION_DEPENDENT",
        f"{sum(r['Count'] for r in rr)} plates; geometry of placeholder details", None, "", "Count/size from unapproved rules")
    boq(code + ".NR", desc + " - number", "nr", sum(r["Count"] for r in rr), "ASSUMPTION_DEPENDENT", "count of modelled plates")
boq("SG-15-FITTINGS.GP10.NR", "Gusset plates 10 mm - number", "nr", g["Count"], "MODEL_DERIVED", "count of modelled plates (one per panel point)")
for k, n in sorted(bc.items()):
    boq(f"SG-15-BOLTS.{k[1]}x{k[2]}", f"Bolt sets {k[1]} x {k[2]} mm, 8.8 (provisional), each with 1 nut and 1 washer; grip {k[3]} mm", "nr", n,
        "ASSUMPTION_DEPENDENT", "count of modelled bolt-set occurrences (R2 take-off rule, placeholder gauge/pitch)", None, "",
        "NOT procurement-ready: bolt-group design, preload and spares allowance outstanding")
boq("SG-15-BOLTS.NUTS", "Hexagon nuts (included in bolt sets above) - number", "nr", len(bolts), "ASSUMPTION_DEPENDENT", "1 per modelled bolt set (set composition placeholder)")
boq("SG-15-BOLTS.WASHERS", "Plain washers (included in bolt sets above) - number", "nr", len(bolts), "ASSUMPTION_DEPENDENT", "1 per modelled bolt set (set composition placeholder)")
area = sum(m["OuterSurfaceArea_m2"] or 0 for m in members)
boq("SG-15-SURFACE.MEMBERS", "Surface treatment to truss angles (two-coat paint provisional; galvanising undecided)", "m2", round(area, 2), "MODEL_DERIVED",
    "Qto OuterSurfaceArea of the modelled angles (plates, bolts excluded)", None, "", "Coating specification NOT approved; plates add about 2 x plate area")
for code, desc in (("SG-15-NA.BEARINGS", "Truss bearings / holding-down at 22 column heads"), ("SG-15-NA.TIES", "Bottom-chord restraint ties (R2: <= 5.4 m)"),
                   ("SG-15-NA.GIRDERS", "Eaves wind girders and roof bracing re-detail (R2 ~10.6 t)"), ("SG-15-NA.RIGGING", "Rated rigging hardware / spreader steel"),
                   ("SG-15-NA.WELDS", "Welding (none assumed: bolted truss)"), ("SG-15-NA.ERECTION", "Erection, temporary works, transport of 32.4 m trusses")):
    boq(code, desc, "item", "", "NOT_AVAILABLE", "not modelled / not designed", note="see outstanding engineering register")
boq("REF-R2.TRUSS-SET", "R2 indicative truss steel incl. connection allowance (reference only, not a measured quantity)", "t", 42.1, "PRELIMINARY_ESTIMATE",
    "R2: (2 gable + 2 rigging + 7 typical) x member mass x 1.274 connection ratio")
w("preliminary_boq_extract.csv", B)

summary = {"trusses": len(trusses), "totals": TOT, "by_profile": {p: {"angles": int(v["Angles"]), "length_m": round(v["Length_m"], 2), "mass_kg": round(v["Mass_kg"], 1)} for p, v in byp.items()},
           "plates": {r["Component"]: r for r in crow if r["Component"] != "BOLT_SET"}, "bolt_types": {r["Type"]: r["Count"] for r in crow if r["Component"] == "BOLT_SET"},
           "connection_types": sum(1 for r in lib if r["Kind"] == "CONNECTION"), "connection_instances": sum(r["Instances"] for r in lib if r["Kind"] == "CONNECTION"),
           "built_up_types": sum(1 for r in lib if r["Kind"] == "BUILT_UP_MEMBER_2L"), "truss_types": {r["TypeName"]: r["Instances"] for r in lib if r["Kind"] == "TRUSS"},
           "member_surface_m2": round(area, 2), "stock_bars": cut}
json.dump(summary, open(outdir / "schedule_summary.json", "w"), indent=1, default=str)
print(json.dumps({k: summary[k] for k in ("trusses", "connection_types", "connection_instances", "truss_types")}, indent=1))
print(json.dumps(TOT, indent=1))
