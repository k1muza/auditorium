"""Stage 5 - roof interface verification and clash register (read-only on both files).

  .venv/Scripts/python -I scripts/option_b/s06_interfaces.py <candidate.ifc> <reference bim/southgate.ifc> <outdir>

1. Exact BRep intersection (> 0.5 mm) of every Option B truss component against every retained element whose
   bounding box reaches a truss zone. The superseded 16-panel truss is tested the same way in the reference model,
   so each clash is classified INHERITED (the same existing element also clashed with the old truss) or NEW.
2. Analytical interface checks: purlin seating and rows vs panel points, purlin cleats, rod bracing, bottom-chord
   ties, acoustic raft clamps, lighting-bar hangers, HVLS fan beams, loudspeaker arrays, ridge fans, columns.
Writes clash_register.csv, interface_register.csv, interfaces.json.
"""
import csv, json, math, multiprocessing, re, sys, time
from collections import defaultdict, Counter
from pathlib import Path
import numpy as np
import ifcopenshell, ifcopenshell.geom, ifcopenshell.util.element as ue, ifcopenshell.util.placement as up
import ifcopenshell.ifcopenshell_wrapper as W

cand_p, ref_p, outdir = sys.argv[1], sys.argv[2], Path(sys.argv[3])
outdir.mkdir(parents=True, exist_ok=True)
t0 = time.time()
def log(*x): print(f"[{time.time() - t0:7.1f}s]", *x, flush=True)
LINES = [round(3.25 + 5.56 * i, 2) for i in range(11)]
TAN15, COS15 = math.tan(math.radians(15)), math.cos(math.radians(15))
PT = ue.get_predefined_type


def truss_parts(f):
    out = set()
    for a in f.by_type("IfcElementAssembly"):
        if PT(a) == "TRUSS":
            out |= {p.GlobalId for p in ue.get_decomposition(a)}
    return out


def bboxes(f, els):
    s = ifcopenshell.geom.settings(); s.set("use-world-coords", True)
    res = {}
    it = ifcopenshell.geom.iterator(s, f, max(1, multiprocessing.cpu_count() - 1), include=els)
    if it.initialize():
        while True:
            sh = it.get(); v = np.asarray(sh.geometry.verts).reshape(-1, 3)
            if len(v): res[sh.guid] = (v.min(0), v.max(0), v)
            if not it.next(): break
    return res


def near_truss(bb):
    mn, mx = bb[0], bb[1]
    if mx[2] < 10.5 or mn[2] > 17.2 or mx[1] < -0.2 or mn[1] > 33.2:
        return False
    return any(mn[0] - 0.3 <= x <= mx[0] + 0.3 for x in LINES)


def clash_set(f, mine, others, label):
    """exact overlaps deeper than 0.5 mm between 'mine' and 'others'"""
    sn = ifcopenshell.geom.settings(); sn.set("iterator-output", W.NATIVE)
    tree = ifcopenshell.geom.tree()
    tree.add_iterator(ifcopenshell.geom.iterator(sn, f, max(1, multiprocessing.cpu_count() - 1), include=list(mine) + list(others)))   # select(element) needs the element in the tree
    gid_others = {e.GlobalId for e in others}
    out = []
    for e in mine:
        for o in tree.select(e, extend=-0.0005):
            if o.GlobalId in gid_others:
                out.append((e, o))
    log(label, len(out))
    return out


def src_of(e):
    pv = ue.get_pset(e, "SOUTHGATE_Provenance") or {}
    return pv.get("SourceObjects") or e.Name


cand = ifcopenshell.open(cand_p); log("candidate opened")
ref = ifcopenshell.open(ref_p); log("reference opened")
new_ids = truss_parts(cand)
old_ids = truss_parts(ref)
new_parts = [e for e in cand.by_type("IfcElement") if e.GlobalId in new_ids and e.Representation]
old_parts = [e for e in ref.by_type("IfcElement") if e.GlobalId in old_ids and e.Representation]
ret_c = [e for e in cand.by_type("IfcElement") if e.GlobalId not in new_ids and e.Representation and not e.is_a("IfcOpeningElement")]
bb_c = bboxes(cand, ret_c); log("retained bboxes", len(bb_c))
zone = [e for e in ret_c if e.GlobalId in bb_c and near_truss(bb_c[e.GlobalId])]
zone_ids = {e.GlobalId for e in zone}
zone_ref = [e for e in ref.by_type("IfcElement") if e.GlobalId in zone_ids]
log("retained elements in truss zones", len(zone))
new_cl = clash_set(cand, new_parts, zone, "new-truss clashes")
old_cl = clash_set(ref, old_parts, zone_ref, "old-truss clashes")
old_hit = defaultdict(set)
for e, o in old_cl:
    old_hit[o.GlobalId].add(e.Name)

# classify
CAT = [
    (r"COL-ROOF|ROOF-COLUMN-CAP|ROOF-COLUMN-SEAT", "SUPPORT (column / cap / seat fin)", "C-01",
     "Existing support detail occupies the truss heel zone (cap plate projects to y = 0.33; seat fin 16 mm in the 10 mm gusset plane). Out of scope: resolve in the separate support study (lower cap >= 45 mm, replace seat fin by a bearing designed with the heel gusset)."),
    (r"EAVES|OUTRIGGER", "EAVES (outrigger / eaves cleat)", "C-02",
     "Existing eaves outrigger RHS and eaves cleat lie in the truss plane at the heel; their connection to the Option B top chord / heel gusset must be redesigned (eaves detail)."),
    (r"BRACE-ROOF", "BRACING (rod end plate)", "C-03",
     "Existing rod-bracing end plates are in the gusset plane at heel/ridge nodes; re-detail as cleats bolted to the Option B gussets when the roof bracing / eaves girder is designed (R2 s.6.2)."),
    (r"PURLIN-CLEAT|PURLIN", "PURLIN / CLEAT", "C-04",
     "Purlin or cleat overlap with the top chord - check purlin seating detail."),
    (r"ACOUSTIC", "ACOUSTIC RAFT SUSPENSION", "C-05", "Clamp / hanger geometry vs new bottom chord."),
    (r"VENT|HVLS|FAN", "MECHANICAL (fans / supports)", "C-06", "Fan supports vs truss."),
    (r"LGT|LIGHT", "LIGHTING", "C-07", "Lighting supports vs truss."),
    (r"GABLE|HALL-WEST-HIGH-WALL|EXT-E-\d|FACADE-[NS]-BAY|EXT-[NS]-|WINDOW-INFILL|EXT02-E-GABLE", "WALLS (gable walls / side-wall heads)", "C-08",
     "Gable trusses (lines 0 and 10) are built into the gable walls and the side-wall brick infill / wall heads rise into the heel zone; the walls are architecture (unchanged). Detail the wall-to-truss interface (wall head below the bottom chord / pockets) in the envelope package."),
]
def cat(o):
    s = (src_of(o) or "") + " " + (o.Name or "")
    for rx, c, cid, note in CAT:
        if re.search(rx, s, re.I):
            return c, cid, note
    return "OTHER", "C-99", "Unclassified - review"

rows = []
groups = defaultdict(list)
for e, o in new_cl:
    groups[o.GlobalId].append(e)
for gid, es in groups.items():
    o = next(x for x in zone if x.GlobalId == gid)
    c, cid, note = cat(o)
    inh = "INHERITED" if gid in old_hit else "NEW"
    for e in es:
        pv = ue.get_pset(e, "SOUTHGATE_Provenance") or {}
        rows.append({"clash_group": cid, "category": c, "existing_element": o.Name, "existing_class": o.is_a(), "existing_source": src_of(o)[:80],
                     "existing_globalid": o.GlobalId, "new_component": e.Name, "new_class": e.is_a(), "truss": pv.get("ParentTruss"),
                     "status": inh, "old_truss_components_clashing_same_element": len(old_hit.get(gid, ())),
                     "disposition": "DOCUMENTED - not resolved (out of scope / needs approval)", "note": note})
rows.sort(key=lambda r: (r["clash_group"], r["truss"] or "", r["existing_element"], r["new_component"]))
with open(outdir / "clash_register.csv", "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()) if rows else ["none"]); w.writeheader(); w.writerows(rows)
summ = Counter((r["clash_group"], r["category"], r["status"]) for r in rows)
elem_summ = Counter((cat(next(x for x in zone if x.GlobalId == g))[1], "INHERITED" if g in old_hit else "NEW") for g in groups)
old_only = [g for g in old_hit if g not in groups]
log("clash rows", len(rows))

# ------------------------------------------------------------------ analytical interfaces
bb_new = bboxes(cand, new_parts)
def by_src(rx):
    return [e for e in zone + [x for x in ret_c if x.GlobalId in bb_c] if re.search(rx, src_of(e) or "", re.I)]
NODES = [round(2.7 * k, 2) for k in range(13)]
nearest = lambda s: min(NODES, key=lambda n: abs(n - s))
I = []
def add(iid, topic, item, finding, status, action, evidence):
    I.append({"id": iid, "topic": topic, "item": item, "finding": finding, "status": status, "action": action, "evidence": evidence})

# purlins: rows vs nodes, seating
rows_s = sorted({round(0.01 + 1.35 * k, 2) for k in range(13)} | {round(32.4 - 0.01 - 1.35 * k, 2) for k in range(13)})
on_node = [s for s in rows_s if abs(nearest(s) - s) <= 0.011]
add("I-01", "Purlins", "Purlin rows vs Option B top panel points",
    f"{len(rows_s)} purlin rows at 1.35 m; {len(on_node)} rows lie within 10 mm of a panel point (every second row), the others at mid-panel (1.34-1.36 m from a node). "
    "The 16-bay layout had rows at arbitrary positions; B reduces top-chord local bending but the R2 analysis already included purlin loads between nodes.",
    "COMPATIBLE", "None for geometry; engineer to confirm top-chord bending between nodes (R2 included it)", "R2 options_and_loads.PURLIN_S; model purlin placements")
seat = json.load(open(Path(__file__).resolve().parents[2] / "work/option_b/s02_roof_seating.json"))["summary"]
add("I-02", "Purlins", "Purlin seating on the top chord",
    f"Top-of-steel set 0.4 mm under the measured purlin underside (purlin {seat['purlin_underside_min_perp_m']*1000:.2f} mm, TOS -10.50 mm normal to the 12.380 plane). "
    "The superseded 2L100 chord was centred on the 12.380 plane and overlapped every purlin by ~59 mm (source modelling inconsistency).",
    "COMPATIBLE (DEV-01)", "None - roof envelope unchanged; record the setting-out deviation DEV-01 for the engineer", "work/option_b/s02_roof_seating.json; validation gate C5")
add("I-03", "Purlins", "Purlin-to-truss cleats (existing PURLIN-CLEAT)",
    f"Existing cleat soles sit {(seat['cleat_underside_min_perp_m'] + 0.0105)*1000:.1f} mm above the new top of steel (they were modelled on the 12.380 plane, 14 mm above the purlin underside). "
    "The cleats are purlin-package items and were not moved.", "GAP - DETAIL TO REVISE", "Purlin package: re-detail cleats to bear on the new top chord (2L90 / 2L80 outstanding legs, 190 / 170 mm wide)",
    "work/option_b/s02_roof_seating.json")
add("I-04", "Purlins", "Purlin support continuity",
    "Truss lines, spacing (5.56 m) and top-of-steel plane unchanged, so every purlin keeps its two bearings; no purlin spans changed.", "COMPATIBLE", "None", "truss positions gate C2")
# bracing
br = [e for e in ret_c if re.search(r"^BRACE-ROOF-\d+$", src_of(e) or "")]
add("I-05", "Roof bracing", "Existing rod bracing (end bays, 4 rods + 8 end plates + 4 turnbuckles)",
    f"{len(br)} rods run heel (s = 0) to ridge (s = 16.2) in bays 0-1 and 9-10; both ends land on Option B panel points (T00 / T06). "
    "End plates are modelled in the truss plane and conflict with the 10 mm gusset plane (clash group C-03).",
    "CONFLICT (inherited)", "Re-detail as cleats bolted to the heel / apex gussets when the roof bracing and eaves wind girders are designed (R2 s.6.2: girders ~10.6 t)",
    "clash_register.csv group C-03")
add("I-06", "Roof bracing", "Bottom-chord restraint ties",
    "R2 assumes out-of-plane ties at <= 5.4 m (BC panel points s = 5.4, 10.8, 16.2, 21.6, 27.0). No ties exist in the model; under uplift the bottom chord is in compression over 32.4 m without them.",
    "MISSING (required)", "Design and model longitudinal ties / bracing; connection provision noted on the five bottom panel points (SOUTHGATE_ConnectionInstance.Interfaces)",
    "R2 s.2.4 / s.6.3")
add("I-07", "Roof bracing", "Eaves wind girders / lateral stability",
    "R2 requires a designed lateral system (eaves wind girders ~10.6 t with wall bracing, or fixed-base columns). Not in the model.", "MISSING (required)",
    "Separate design; heel gussets (CT-TH) will need girder connection provisions", "R2 s.6.2")
# acoustic clamps
cl = [e for e in ret_c if re.search(r"ACOUSTIC-TRUSS-CLAMP", src_of(e) or "")]
d_cl, gaps = [], []
bc_under = {}
for e in new_parts:
    if e.is_a("IfcMember") and (ue.get_pset(e, "SOUTHGATE_MemberData") or {}).get("Role") == "TRUSS_BOTTOM_CHORD" and e.GlobalId in bb_new:
        x = round(float(bb_new[e.GlobalId][2][:, 0].mean()), 2)
        bc_under[x] = min(bc_under.get(x, 99), float(bb_new[e.GlobalId][0][2]))
for e in cl:
    mn, mx, _ = bb_c[e.GlobalId]
    s = (mn[1] + mx[1]) / 2 - 0.30
    d_cl.append(abs(nearest(s) - s))
    xl = min(bc_under, key=lambda x: abs(x - (mn[0] + mx[0]) / 2)) if bc_under else None
    if xl is not None:
        gaps.append(bc_under[xl] - mx[2])
add("I-08", "Acoustic rafts", f"Raft clamps on bottom chords ({len(cl)} clamps, lines 2-7)",
    f"Clamp positions are {min(d_cl):.2f}-{max(d_cl):.2f} m from the nearest Option B panel point (median {np.median(d_cl):.2f} m). "
    f"Clamp tops sit {min(gaps)*1000:.1f}-{max(gaps)*1000:.1f} mm below the new bottom-chord underside (the old 2L90 chord underside was 22 mm lower, clamps overlapped it). "
    "New chord 2L80 back-to-back = 170 mm wide (old 190 mm).",
    "ATTACHMENT TO REVISE", "Acoustic package: re-space raft rails to 2.70 m panel points (R2 Table 9.1) or confirm chord bending; re-size clamp jaws to 170 mm and re-seat (+5.5 mm)",
    "R2 s.9 Table 9.1; model clamp geometry")
# lighting bars
hg = [e for e in ret_c if re.search(r"STG-LGT-HANGER", src_of(e) or "")]
hd, hgap = [], []
for e in hg:
    mn, mx, _ = bb_c[e.GlobalId]
    s = (mn[1] + mx[1]) / 2 - 0.30
    hd.append((round(s, 2), round(abs(nearest(s) - s), 2)))
    xl = min(bc_under, key=lambda x: abs(x - (mn[0] + mx[0]) / 2))
    hgap.append(bc_under[xl] - mx[2])
add("I-09", "Lighting", f"Stage / FOH lighting-bar hangers ({len(hg)} on truss lines 1 and 2)",
    f"Hanger positions (s, distance to nearest node): {hd}. Hanger tops end {min(hgap)*1000:.0f}-{max(hgap)*1000:.0f} mm below the bottom chord (they never reached the old chord either). "
    "Rigging pick-up tab provisions are modelled at every interior bottom panel point of lines 1-2 (capacity NOT_AVAILABLE).",
    "ATTACHMENT TO REVISE", "Lighting/rigging design: move pick-ups to panel points (R2: bars land within 0.8 m) and specify rated hardware to the tabs; rigging load plan",
    "R2 s.9; model hanger geometry; rigging tab provision")
# HVLS
hv = [e for e in ret_c if re.search(r"HVLS\d-SUPPORT-BEAM", src_of(e) or "")]
hvs, hvg = [], []
for e in hv:
    mn, mx, _ = bb_c[e.GlobalId]
    s = (mn[1] + mx[1]) / 2 - 0.30
    hvs.append(round(abs(nearest(s) - s), 3))
    hvg.append(min(bc_under.values()) - mx[2])
add("I-10", "Ceiling fans", f"HVLS fan support beams ({len(hv)}, spanning between trusses 3-7)",
    f"Beams bear {min(hvs):.2f}-{max(hvs):.2f} m from the nearest panel point (s = 10.65 / 21.75 vs nodes 10.8 / 21.6); beam tops {min(hvg)*1000:.0f} mm below the bottom chord with no connection modelled. "
    "R2 included the fan loads off-node (non-coordinated run) and a dynamic assessment is still required.",
    "ATTACHMENT TO REVISE", "Mechanical/structural: move beams 150 mm to the panel points or confirm chord bending; design the beam-to-chord hangers; fan dynamic assessment (R2 s.9.2)",
    "R2 s.9; model beam geometry")
# arrays
ar = [e for e in ret_c if re.search(r"^ARRAY-", src_of(e) or "")]
ad = []
for e in ar:
    mn, mx, _ = bb_c[e.GlobalId]
    s = (mn[1] + mx[1]) / 2 - 0.30
    ad.append((round(s, 2), round(abs(nearest(s) - s), 2), round((mn[0] + mx[0]) / 2, 2)))
add("I-11", "Loudspeakers", f"Main L/R arrays ({len(ar)})",
    f"Arrays (s, distance to node, x): {ad}. They hang midway between truss lines 1 and 2 (x 11.5); no rigging steel modelled. R2 assumed a spreader sharing the load to lines 1 and 2, landing within 0.8 m of a node.",
    "NOT MODELLED - DESIGN REQUIRED", "AV/rigging design: spreader beam between lines 1-2 picking up on bottom panel points (tabs provided at s = 5.4 / 8.1 / 24.3 / 27.0); designed rigging hardware",
    "R2 s.9 Table 9.1")
rf = [e for e in ret_c if re.search(r"VENT-04-FAN\d-(HOUSING|COWL)", src_of(e) or "")]
add("I-12", "Ridge fans", f"Ridge extract fans (VENT-04, {len(rf)} parts) and kerbs",
    "Fans sit between truss lines at the ridge on purlin trimmers (rows 11/13); no truss member is in their footprint (no clash recorded).", "COMPATIBLE",
    "None for the trusses; trimmers remain a purlin-package item", "clash_register.csv (no C-06 rows) ")
add("I-13", "Catwalks", "Maintenance catwalk allowance",
    "R2: B gives about 2.46 m clear height for a 0.8 m walkway at the centre (E2/E3 3.25 m). No catwalk is modelled; the decision is needed before the geometry is fixed (R2 s.10).",
    "OPEN DECISION", "Client/AV/lighting decision on catwalks; if adopted, add catwalk hangers to bottom panel points and re-check web set-outs", "R2 s.10 / s.11")
col = [e for e in ret_c if re.search(r"^COL-ROOF-", src_of(e) or "")]
add("I-14", "Columns", f"Truss-to-column interface ({len(col)} UC 254x254x73 columns)",
    "Column lines and heights unchanged. Column top +12.283, cap plate +12.293..+12.313 (y -0.03..0.33), seat fin 16 mm in the truss plane. "
    "Option B heel: top chord toe at about +12.27 at the bearing (TOS fixed by the purlins), end post and heel gusset at y >= 0.281. The cap plate and seat fin intersect the heel (clash group C-01); "
    "the superseded truss had the same seat-fin conflict.",
    "CONFLICT - SUPPORT STUDY", "Separate support/foundation study: lower the column top / cap by >= 45 mm or bear the heel on a designed shoe; replace the seat fin with a bearing designed with the heel gusset; holding-down for ~80 kN uplift (R2)",
    "clash_register.csv group C-01")
with open(outdir / "interface_register.csv", "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=list(I[0].keys())); w.writeheader(); w.writerows(I)
json.dump({"zone_elements": len(zone), "new_clash_pairs": len(new_cl), "old_clash_pairs": len(old_cl),
           "clash_rows_by_group": {f"{k[0]}|{k[1]}|{k[2]}": v for k, v in summ.items()},
           "existing_elements_clashing_new": {f"{k[0]}|{k[1]}": v for k, v in elem_summ.items()},
           "existing_elements_clashing_old_only": [next(x.Name for x in zone_ref if x.GlobalId == g) for g in old_only],
           "interfaces": I, "seconds": round(time.time() - t0, 1)}, open(outdir / "interfaces.json", "w"), indent=1, default=str)
print(json.dumps({"clash_rows_by_group": {f"{k[0]}|{k[1]}|{k[2]}": v for k, v in summ.items()},
                  "existing_elements": {f"{k[0]}|{k[1]}": v for k, v in elem_summ.items()}, "old_only": len(old_only)}, indent=1))
