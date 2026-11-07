"""Build the Option B roof trusses into a controlled working IFC revision. Never writes bim/southgate.ifc.

  pilot:     .venv/Scripts/python scripts/option_b/s04_build.py pilot [--line 4]
             isolated IFC4 file (project/site/building/'03 Roof' storey, same units and contexts) with ONE truss
  candidate: .venv/Scripts/python scripts/option_b/s04_build.py candidate --expected-source-sha256 <sha>
             1. verifies the authoritative IFC checksum against bim/publish_record.json and --expected-source-sha256
             2. timestamped backup to work/backups/ (sha256 re-verified)
             3. opens a COPY, removes the superseded 16-panel truss parts (identities recorded), reuses the 11
                SOUTHGATE-TRUSS-Txx assembly identities, builds the 11 Option B trusses
             4. ifc5d base quantities for the NEW elements only + SOUTHGATE_Quantities, writes
                work/option_b/candidates/<stamp>/southgate_optionB_candidate.ifc and change_manifest.json
"""
import argparse, hashlib, json, math, shutil, sys, time
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
import yaml  # noqa: E402
import ifcopenshell  # noqa: E402
import ifcopenshell.api  # noqa: E402
import ifcopenshell.api.root, ifcopenshell.api.unit, ifcopenshell.api.context, ifcopenshell.api.aggregate  # noqa: E402,E401
import ifcopenshell.api.spatial, ifcopenshell.api.pset  # noqa: E402,E401
import ifcopenshell.util.element as ue  # noqa: E402
from southgate_bim.structure.optb_truss import OptionBTruss, load_rules, AngleSec  # noqa: E402
from southgate_bim.structure.optb_ifc import OptBAuthor, REV  # noqa: E402
from southgate_bim.quantities import qto  # noqa: E402

API = ifcopenshell.api
ap = argparse.ArgumentParser()
ap.add_argument("mode", choices=["pilot", "candidate"])
ap.add_argument("--line", type=int, default=4)
ap.add_argument("--expected-source-sha256")
ap.add_argument("--source", default=str(ROOT / "bim/southgate.ifc"))
a = ap.parse_args()
cfg = yaml.safe_load(open(ROOT / "config/project.yaml"))
NS = cfg["project"]["guid_namespace"]
stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
rules, basis = load_rules()
t0 = time.time()


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def log(*x):
    print(f"[{time.time() - t0:7.1f}s]", *x, flush=True)


def quantities(f, author):
    """ifc5d base quantities for new members/plates + SOUTHGATE_Quantities with measurement status."""
    targets = [e for e in author.created if e.is_a() in ("IfcMember", "IfcPlate")]
    qto.compute_base_quantities(f, targets)
    dens = float(rules["material"]["density_kg_m3"])
    for e in author.created:
        out = {"Count": 1}
        if e.is_a("IfcMember"):
            t = ue.get_type(e)
            sec = t.Name.split("-")[-1]
            s = AngleSec.from_rules(sec, rules)
            q = ue.get_pset(e, "Qto_MemberBaseQuantities") or {}
            L = q.get("Length")
            out.update({"NominalSectionMass_kg": round(s.kg_m * L, 3) if L else None,
                        "NominalSectionMassBasis": f"Qto Length x catalogue {s.kg_m} kg/m ({sec})",
                        "IndicativeMassFromDensity_kg": round(q["NetVolume"] * dens, 3) if q.get("NetVolume") else None,
                        "MassBasis": f"Qto NetVolume x {dens:.0f} kg/m3 (native L profile incl. root/toe radii; bolt holes in angles not modelled)",
                        "MeasurementStatus": "MODEL_DERIVED", "SizeStatus": "CONCEPT_UNVERIFIED"})
        elif e.is_a("IfcPlate"):
            q = ue.get_pset(e, "Qto_PlateBaseQuantities") or {}
            pdat = ue.get_pset(e, "SOUTHGATE_PlateData") or {}
            th = (q.get("Width") or 0)
            net = q.get("NetVolume") or q.get("GrossVolume")
            out.update({"IndicativeMassFromDensity_kg": round(net * dens, 3) if net else None,
                        "MassBasis": f"Qto volume x {dens:.0f} kg/m3", "MeasurementStatus": "MODEL_DERIVED" if e.ObjectType != "PACKING_PLATE" else "ASSUMPTION_DEPENDENT",
                        "QuantityBasis": "geometry of a concept-detail plate (placeholder rules)"})
        elif e.is_a("IfcMechanicalFastener"):
            out.update({"BoltSets": 1, "Bolts": 1, "Nuts": 1, "Washers": 1, "MeasurementStatus": "ASSUMPTION_DEPENDENT",
                        "CountBasis": "R2 take-off rule + placeholder gauge/pitch; set composition PLACEHOLDER"})
        else:
            continue
        author.pset(e, "SOUTHGATE_Quantities", {k: v for k, v in out.items() if v is not None})


def pilot_file():
    f = ifcopenshell.file(schema="IFC4")
    proj = API.root.create_entity(f, ifc_class="IfcProject", name="Southgate Worship Center - Option B pilot truss (isolated)")
    units = [API.unit.add_si_unit(f, unit_type=u) for u in ("LENGTHUNIT", "AREAUNIT", "VOLUMEUNIT", "PLANEANGLEUNIT")]
    units.append(API.unit.add_si_unit(f, unit_type="MASSUNIT", prefix="KILO"))
    API.unit.assign_unit(f, units=units)
    model = API.context.add_context(f, context_type="Model")
    API.context.add_context(f, context_type="Model", context_identifier="Body", target_view="MODEL_VIEW", parent=model)
    API.context.add_context(f, context_type="Model", context_identifier="Axis", target_view="GRAPH_VIEW", parent=model)
    site = API.root.create_entity(f, ifc_class="IfcSite", name="Site")
    bld = API.root.create_entity(f, ifc_class="IfcBuilding", name="Southgate Worship Center")
    st = API.root.create_entity(f, ifc_class="IfcBuildingStorey", name="03 Roof")
    st.Elevation = 10.9
    API.aggregate.assign_object(f, products=[site], relating_object=proj)
    API.aggregate.assign_object(f, products=[bld], relating_object=site)
    API.aggregate.assign_object(f, products=[st], relating_object=bld)
    site.ObjectPlacement = f.createIfcLocalPlacement(None, f.createIfcAxis2Placement3D(f.createIfcCartesianPoint((0.0, 0.0, 0.0))))
    bld.ObjectPlacement = f.createIfcLocalPlacement(site.ObjectPlacement, f.createIfcAxis2Placement3D(f.createIfcCartesianPoint((0.0, 0.0, 0.0))))
    st.ObjectPlacement = f.createIfcLocalPlacement(bld.ObjectPlacement, f.createIfcAxis2Placement3D(f.createIfcCartesianPoint((0.0, 0.0, 10.9))))
    return f, st


def superseded_trusses(f):
    """Old 16-panel truss assemblies -> (assembly, parts, line index by mean x)."""
    out = []
    import ifcopenshell.util.placement as up
    for asm in f.by_type("IfcElementAssembly"):
        if asm.PredefinedType != "TRUSS":
            continue
        parts = ue.get_decomposition(asm)
        xs = [up.get_local_placement(p.ObjectPlacement)[0][3] for p in parts if p.ObjectPlacement]
        mx = sum(xs) / len(xs)
        line = min(range(11), key=lambda i: abs(3.25 + 5.56 * i - mx))
        out.append((asm, parts, line, mx))
    return sorted(out, key=lambda t: t[2])


if a.mode == "pilot":
    outdir = ROOT / "work/option_b/pilot" / stamp
    outdir.mkdir(parents=True)
    f, st = pilot_file()
    author = OptBAuthor(f, rules, basis, NS, f"{REV}-pilot-{stamp}")
    T = OptionBTruss(a.line, rules, basis)
    asm = f.create_entity("IfcElementAssembly", GlobalId=author.guid(f"PILOT-SOUTHGATE-TRUSS-{T.tid}"),
                          Name=f"SOUTHGATE-TRUSS-{T.tid}", Description="PILOT - Option B truss", PredefinedType="TRUSS", AssemblyPlace="NOTDEFINED",
                          ObjectPlacement=author.place([T.x, 0.30, 10.9]))
    API.spatial.assign_container(f, products=[asm], relating_structure=st)
    author.build_truss(T, asm)
    author.finish()
    log("authored", len(author.created), "elements")
    quantities(f, author)
    p = outdir / f"pilot_{T.tid}.ifc"
    f.write(str(p))
    log("wrote", p, sha(p))
    json.dump({"file": str(p.relative_to(ROOT)), "sha256": sha(p), "truss": T.summary(), "elements": len(author.created),
               "classes": dict(Counter(e.is_a() for e in author.created))}, open(outdir / "pilot_manifest.json", "w"), indent=1)
    sys.exit(0)

# ------------------------------------------------------------------ candidate
src = Path(a.source)
rec = json.load(open(ROOT / "bim/publish_record.json"))
cur = sha(src)
if cur != rec["sha256"]:
    raise SystemExit(f"authoritative IFC sha {cur} != publish record {rec['sha256']} - newer or unrecorded work; stopping")
if a.expected_source_sha256 and cur != a.expected_source_sha256:
    raise SystemExit(f"authoritative IFC sha {cur} != --expected-source-sha256 {a.expected_source_sha256}; stopping")
bdir = ROOT / "work/backups"
bdir.mkdir(parents=True, exist_ok=True)
bak = bdir / f"{stamp}_southgate_pre-optionB.ifc"
shutil.copy2(src, bak)
if sha(bak) != cur:
    raise SystemExit("backup checksum mismatch")
log("backup", bak, cur)
outdir = ROOT / "work/option_b/candidates" / stamp
outdir.mkdir(parents=True)
work_copy = outdir / "source_copy.ifc"
shutil.copy2(src, work_copy)
f = ifcopenshell.open(str(work_copy))
log("opened working copy")
old = superseded_trusses(f)
assert len(old) == 11 and sorted(t[2] for t in old) == list(range(11)), [(t[0].Name, t[2]) for t in old]
manifest = {"revision": REV, "stamp": stamp, "source": {"path": "bim/southgate.ifc", "sha256": cur, "publish_record": rec},
            "backup": {"path": str(bak.relative_to(ROOT)).replace("\\", "/"), "sha256": cur},
            "superseded": [], "reused": [], "created": {}, "retained_note": "every element not listed as superseded is retained unchanged (verified by s05 regression)"}
old_types = set()
for asm, parts, line, mx in old:
    for p in parts:
        pv = ue.get_pset(p, "SOUTHGATE_Provenance") or {}
        t = ue.get_type(p)
        if t:
            old_types.add(t)
        manifest["superseded"].append({"GlobalId": p.GlobalId, "StableId": pv.get("StableId") or p.Name, "Class": p.is_a(),
                                       "SourceObjects": pv.get("SourceObjects"), "Truss": asm.Name, "Line": line,
                                       "Disposition": "SUPERSEDED_BY_OPTION_B - removed from the candidate model (retained in bim/southgate.ifc and the backup)"})
    manifest["reused"].append({"GlobalId": asm.GlobalId, "StableId": asm.Name, "Line": line, "OldPartCount": len(parts),
                               "Disposition": "IDENTITY_REUSED - same IfcElementAssembly entity re-populated with the Option B truss; psets replaced"})
log("superseded parts", len(manifest["superseded"]), "types", len(old_types))
for asm, parts, line, mx in old:
    for p in parts:
        API.root.remove_product(f, product=p)
    for rel in list(asm.IsDefinedBy or []):
        if rel.is_a("IfcRelDefinesByProperties"):
            pd = rel.RelatingPropertyDefinition
            API.pset.remove_pset(f, product=asm, pset=pd)
for t in old_types:
    if not ue.get_types(t):
        manifest.setdefault("superseded_types", []).append({"GlobalId": t.GlobalId, "Name": t.Name})
        API.root.remove_product(f, product=t)
log("removed superseded parts and", len(manifest.get("superseded_types", [])), "orphan types")
author = OptBAuthor(f, rules, basis, NS, f"{REV}-{stamp}")
for asm, parts, line, mx in old:
    T = OptionBTruss(line, rules, basis)
    asm.Description = f"Option B roof truss {T.tid} on line {line} (x = {T.x:.2f} m): 12-bay Warren with verticals, paired angles bolted to 10 mm gussets - PRELIMINARY_DESIGN"
    asm.ObjectType = None
    author.build_truss(T, asm)
    author.pset(asm, "SOUTHGATE_Provenance", {"StableId": asm.Name, "SourceKey": f"OPTB:{T.tid}", "Origin": "IDENTITY REUSED - Option B replaces the 16-panel migrated truss",
                                              "PreviousRepresentation": f"16-panel Warren migrated from the source snapshot ({len(parts)} parts, superseded)",
                                              "Revision": REV, "MigrationRun": author.run_id, "MigrationMethod": "aggregate of Option B parts",
                                              "PartCount": len(ue.get_decomposition(asm)) if False else None})
    s = T.summary()
    author.pset(asm, "SOUTHGATE_TrussSummary", {"TrussId": T.tid, "Line": line, "x_m": T.x, "TrussType": T.ttype, "Span_m": 32.4, "Pitch_deg": 15.0,
                                                "Bays": 12, "PanelLength_m": 2.70, "BottomChordPanelPoints": 13, "DepthAtBearing_m": s["depth_at_bearing_m"],
                                                "DepthAtRidge_m": s["depth_at_ridge_m"], "BuiltUpMembers": s["members"], "Angles": s["angles"],
                                                "Gussets": s["gussets"], "SplicePlates": s["splice_plates"], "PackingPlates": s["packers"],
                                                "BoltSets": s["bolts"], "TopChord": "2" + T.sec_tc.name, "BottomChord": "2" + T.sec_bc.name,
                                                "R2SectionsFromLine": T.sec_line, "R2ForcesFromLine": T.force_line})
    author.attach_shared(author._status_psets()["truss"], asm)
    author.attach_shared("basis", asm)
    log("built", T.tid, "line", line)
author.finish()
log("authored", len(author.created), "new elements")
quantities(f, author)
log("quantities done")
manifest["created"] = dict(Counter(e.is_a() + ("/" + e.ObjectType if e.ObjectType else "") for e in author.created))
manifest["created_total"] = len(author.created)
manifest["new_types"] = sorted(t.Name for t in author.types.values())
out = outdir / "southgate_optionB_candidate.ifc"
f.write(str(out))
work_copy.unlink()
manifest["candidate"] = {"path": str(out.relative_to(ROOT)).replace("\\", "/"), "sha256": sha(out)}
json.dump(manifest, open(outdir / "change_manifest.json", "w"), indent=1)
# identity register for the new elements (to merge into source/source_to_ifc_mapping.csv on approval)
import csv
with open(outdir / "identity_register.csv", "w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh)
    w.writerow(["source_key", "stable_id", "global_id", "ifc_class", "object_type", "parent", "revision"])
    for e in author.created:
        pv = ue.get_pset(e, "SOUTHGATE_Provenance") or {}
        w.writerow([pv.get("SourceKey"), e.Name, e.GlobalId, e.is_a(), e.ObjectType or "", pv.get("ParentAssembly"), REV])
log("wrote", out, manifest["candidate"]["sha256"])
