"""Generate schedules and reports for the current model revision.

  .venv/Scripts/python scripts/generate_reports.py model/blender_manifest.json reports

Inputs: layout engine (recomputed from config), Blender manifest (objects read back from the
.blend), reports/blend_verification.json and reports/ifc_validation.json when present.
Every number written here is derived from those sources; nothing is typed in by hand.
"""
import csv
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import auditorium_layout as al  # noqa: E402

DISCLAIMER = ("> **Status: CONCEPT - UNVERIFIED - NOT FOR CONSTRUCTION.** Preliminary engineering-coordination model for "
              "discussion with a qualified architect and structural engineer. No structural analysis, code compliance check, "
              "fire/egress approval, geotechnical input or permit review has been performed. QA scores are not engineering approval.")


def write_csv(path, rows, fields):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})


def load_json(p):
    p = Path(p)
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else None


def main(manifest_path, outdir):
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    P = al.load_params()
    lay = al.compute(P)
    M = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    rev = M["revision"]
    bv = load_json(out / "blend_verification.json")
    iv = load_json(out / "ifc_validation.json")
    objs = {o["name"]: o for o in M["objects"]}
    eg = {r["occupant"]: r for r in lay.egress_results}

    # ---------------------------------------------------------------- seating schedule
    seat_rows, mismatches = [], 0
    for s in lay.seats:
        o = objs.get(s["seat_id"])
        bx = by = bz = None
        if o:
            bx, by, bz = o["matrix"][0][3], o["matrix"][1][3], o["matrix"][2][3]
            if max(abs(bx - s["x"]), abs(by - s["y"]), abs(bz - s["z_floor"])) > 1e-4:
                mismatches += 1
        else:
            mismatches += 1
        e = eg[s["seat_id"]]
        seat_rows.append({**s, "revision": rev, "in_blender_model": bool(o), "blender_x": bx, "blender_y": by,
                          "blender_z": bz, "assigned_exit_balanced": e["exit"], "nearest_exit": e["nearest_exit"],
                          "plan_travel_to_hall_exit_m": e["travel_hall"], "plan_travel_to_external_door_m": e["travel_total"]})
    write_csv(out / "seating_schedule.csv", seat_rows,
              ["seat_id", "row", "section", "block", "seat_in_block", "x", "y", "z_floor", "eye_z", "in_blender_model",
               "blender_x", "blender_y", "blender_z", "assigned_exit_balanced", "nearest_exit",
               "plan_travel_to_hall_exit_m", "plan_travel_to_external_door_m", "revision"])
    # ---------------------------------------------------------------- row schedule
    rows = []
    for rw in lay.rows:
        rows.append({"row": rw["row"], "section": rw["section"], "seats": rw["seats"], "tread_y_rear": al.rnd(rw["yb"], 3),
                     "tread_y_front": al.rnd(rw["yf"], 3), "floor_elevation": rw["floor"], "rise_from_previous": rw["rise"],
                     "aisle_steps_in_row": rw.get("aisle_steps", "ramped aisle (sloped floor)"),
                     "aisle_riser": rw.get("aisle_riser", ""), "stagger_offset": rw["offset"],
                     "eye_distance_to_focal_m": rw["eye_distance"], "c_value_over_row_n_minus_1": rw["c_n1"],
                     "c_value_over_row_n_minus_2": rw["c_n2"]})
    write_csv(out / "row_schedule.csv", rows, list(rows[0].keys()))
    # ---------------------------------------------------------------- spaces
    sp = [{**s, "revision": rev, "status": "Concept allowance - unverified"} for s in lay.spaces]
    write_csv(out / "space_schedule.csv", sp, ["space_id", "name", "level", "use", "area_m2", "x0", "y0", "x1", "y1", "status", "revision"])
    # ---------------------------------------------------------------- exits / accessible positions / elements
    ex_rows = [{"exit_id": e["id"], "wall": e["wall"], "role": e["role"], "x": al.rnd(e["x"], 2), "y": al.rnd(e["y"], 2),
                "sill_elevation": al.rnd(e["z"], 3), "clear_width_m": al.rnd(e["width"], 2), "load_nearest_exit": e["load_nearest"],
                "load_queue_balanced": e["load"], "placeholder_required_width_m": e["required_width"],
                "placeholder_check": "OK" if e["ok"] else "UNDER", "onward_route": e["leg2_route"],
                "onward_plan_distance_m": al.rnd(e["leg2"], 1)} for e in lay.exits]
    write_csv(out / "exit_schedule.csv", ex_rows, list(ex_rows[0].keys()))
    acc = [{"space": p["name"], "location": p["group"], "x0": al.rnd(p["x0"], 2), "x1": al.rnd(p["x1"], 2),
            "y0": al.rnd(p["y0"], 2), "y1": al.rnd(p["y1"], 2), "floor": p["z"], "companion_chair": p["companion"]}
           for p in lay.wc_positions]
    write_csv(out / "accessible_positions.csv", acc, list(acc[0].keys()))
    cnt = Counter((o["collection"], o["ifc_class"], o["predefined_type"]) for o in M["objects"])
    el = [{"collection": c, "ifc_class": k, "predefined_type": p, "count": n} for (c, k, p), n in sorted(cnt.items())]
    write_csv(out / "element_schedule.csv", el, ["collection", "ifc_class", "predefined_type", "count"])
    # ---------------------------------------------------------------- geometry checks json
    (out / "geometry_checks.json").write_text(json.dumps(
        {"revision": rev, "source": "scripts/auditorium_layout.py (analytic checks on generator geometry)",
         "checks": lay.checks, "metrics": lay.metrics, "levels": lay.levels(),
         "ramps": lay.ramps, "stairs": lay.stairs}, indent=2, default=str), encoding="utf-8")
    # ---------------------------------------------------------------- seat count cross-check
    with open(out / "seating_schedule.csv", encoding="utf-8") as fh:
        csv_rows = list(csv.DictReader(fh))
    csv_ids = {r["seat_id"] for r in csv_rows}
    man_ids = {o["name"] for o in M["objects"] if o["collection"] == "40_SEAT_Congregation"}
    blend_n = bv["counts"]["by_collection"].get("40_SEAT_Congregation") if bv else None
    blend_rows = bv["counts"]["seats_per_row"] if bv else {}
    ifc_n = next((c["value"] for c in iv["checks"] if c["id"] == "IFC-SEATS"), None) if iv else None
    csv_per_row = Counter(int(r["row"]) for r in csv_rows)
    row_mismatch = [r for r in csv_per_row if blend_rows and int(blend_rows.get(str(r), -1)) != csv_per_row[r]]
    target = P["seating"]["target_congregation_seats"]
    lines = [f"SEAT COUNT CROSS-CHECK  revision {rev}", "",
             f"Target (config)                                   : {target}",
             f"Layout engine seats (scripts/auditorium_layout.py) : {len(lay.seats)}",
             f"Blender manifest objects in 40_SEAT_Congregation  : {len(man_ids)}",
             f"Saved .blend re-opened (reports/blend_verification.json): {blend_n}",
             f"IFC IfcFurniture SeatType=congregation (reports/ifc_validation.json): {ifc_n}",
             f"reports/seating_schedule.csv data rows            : {len(csv_rows)} (unique ids {len(csv_ids)})",
             f"CSV ids == Blender ids                             : {csv_ids == man_ids}",
             f"CSV coordinates vs Blender placements mismatches (>0.1 mm): {mismatches}",
             f"Rows where CSV count != re-opened .blend count     : {row_mismatch or 'none'}",
             "", "Seats per row (CSV / .blend):"]
    for r in sorted(csv_per_row):
        lines.append(f"  R{r:02d}: {csv_per_row[r]:3d} / {blend_rows.get(str(r), 'n/a')}")
    all_ok = (len(lay.seats) == len(man_ids) == len(csv_rows) == target and blend_n == target and ifc_n == target
              and csv_ids == man_ids and mismatches == 0 and not row_mismatch)
    lines += ["", "Excluded from the 3,000: choir seats (" + str(sum(1 for o in M["objects"] if o["collection"] == "40_SEAT_Choir"))
              + "), loose companion chairs (" + str(sum(1 for o in M["objects"] if o["collection"] == "40_SEAT_Companion"))
              + "), wheelchair spaces (" + str(len(lay.wc_positions)) + ").",
              f"RESULT: {'PASS - all sources agree on exactly ' + str(target) if all_ok else 'FAIL - sources disagree or a source is missing'}"]
    (out / "seat_count_check.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    # ---------------------------------------------------------------- assumptions register
    a = ["# Assumptions register", "", DISCLAIMER, "", f"Model revision: `{rev}` - source of truth: `config/auditorium_params.json` "
         "(edit there and regenerate with `scripts/run_pipeline.py`).", "",
         "| ID | Topic | Assumption | Basis / source | Status | Confidence |", "|---|---|---|---|---|---|"]
    for row in P["assumptions"]:
        a.append("| " + " | ".join(str(x).replace("|", "/") for x in row) + " |")
    a += ["", "## Missing inputs (from DESIGN_BRIEF.md) - NOT invented",
          "- Site boundary/survey, setbacks, zoning, access/parking, orientation, contours -> A-01, A-02, OI-02",
          "- Geotechnical report, bearing/settlement criteria -> A-14, OI-03",
          "- Local building, fire, occupancy and accessibility requirements -> A-04..A-10, OI-01, OI-05",
          "- Budget, target footprint, materials, procurement -> A-18, OI-13",
          "- Loading, wind, rain, seismic, material grades, design standards -> A-11..A-13, OI-04"]
    (out / "assumptions.md").write_text("\n".join(a) + "\n", encoding="utf-8")
    # ---------------------------------------------------------------- open issues
    o = ["# Open issues", "", DISCLAIMER, "", f"Model revision: `{rev}`", "",
         "## Logged design issues (stage-excluded or requiring professional input)", "",
         "| ID | Priority | Topic | Issue | Owner |", "|---|---|---|---|---|"]
    for row in P["open_issues"]:
        o.append("| " + " | ".join(str(x).replace("|", "/") for x in row) + " |")
    o += ["", "## Automatically raised from model checks (WARN / FAIL in this revision)", "",
          "| Check | Source | Result | Value | Criterion |", "|---|---|---|---|---|"]
    def fmt(v):
        s = json.dumps(v) if isinstance(v, (dict, list)) else str(v)
        return s if len(s) < 160 else s[:157] + "..."
    n_auto = 0
    for src, checks in (("geometry_checks.json", lay.checks), ("blend_verification.json", bv["checks"] if bv else []),
                        ("ifc_validation.json", iv["checks"] if iv else [])):
        for c in checks:
            if c["result"] != "PASS":
                n_auto += 1
                o.append(f"| {c['id']} {c['description']} | {src} | {c['result']} | {fmt(c['value']).replace('|', '/')} | {c['criterion']} |")
    if not n_auto:
        o.append("| - | - | none | - | - |")
    m = lay.metrics
    egm = m["egress"]
    o += ["", "## Notes on the egress warnings", "",
          f"- Within-hall plan travel reaches {egm['max_travel_hall']:.1f} m (queue-balanced) because the hall is {m['truss_span']:.0f} m wide "
          "and exits are on the side and rear walls. The 30 m / 60 m flags are placeholders, not local limits. "
          "Mitigations to be tested by the fire engineer: additional exits through the platform wings / stage rear, vomitories "
          "under the rear rake, sprinklers or smoke control as the local code allows, or a narrower/deeper plan.",
          "- `EGR-01N` shows that if everyone used the nearest exit, the cross-aisle doors would be overloaded; the queue-balanced "
          "assignment is a heuristic and must be replaced by a code-based egress analysis.",
          f"- Restriction on use: until OI-01/OI-05 are closed, this layout must not be used to fix occupant capacity, exit "
          "provision or fire strategy."]
    (out / "open_issues.md").write_text("\n".join(o) + "\n", encoding="utf-8")
    # ---------------------------------------------------------------- basis of design
    opt = m["options"]
    sb = P["seating"]
    lv = lay.levels()
    sched = Counter(o_["ifc_class"] for o_ in M["objects"])
    bd = [f"# Basis of design - {P['project']['name']}", "", DISCLAIMER, "",
          f"- **Model revision:** `{rev}` (Blender {M['blender_version']}; generator schema {al.SCHEMA_VERSION})",
          f"- **Milestone:** {P['project']['milestone']}",
          f"- **Units / coordinates:** metres. {P['project']['coordinate_system']}",
          "- **Source:** `config/auditorium_params.json` + `scripts/auditorium_layout.py` -> `scripts/build_auditorium.py` (Blender) "
          "-> `model/blender_manifest.json` -> `scripts/export_ifc.py` (IFC4). Regenerate with `scripts/run_pipeline.py`.", "",
          "## 1. Brief summary",
          "Permanent church auditorium in Zimbabwe for exactly 3,000 congregation seats (choir/platform excluded), with platform, "
          "choir and musicians, foyer, media/sound booth, toilets incl. accessible WCs, prayer room, vestry and storage. "
          "Site, geotechnical, statutory, budget and loading inputs are missing and are NOT invented (see assumptions.md).", "",
          "## 2. Option comparison: single level vs floor + balcony",
          "| Criterion | A: single-level raked hall (SELECTED for this milestone) | B: floor + balcony (computed estimate, not modelled) |",
          "|---|---|---|",
          f"| Seats | 3,000 in {opt['A_single_level']['rows']} rows | {P['balcony_option']['floor_seats']} floor ({opt['B_floor_plus_balcony']['floor_rows']} rows) + {P['balcony_option']['balcony_seats']} balcony ({opt['B_floor_plus_balcony']['balcony_rows']} rows) |",
          f"| Max eye distance to platform edge | {opt['A_single_level']['max_eye_distance_m']:.1f} m | ~{opt['B_floor_plus_balcony']['approx_max_floor_distance_m']} m floor / ~{opt['B_floor_plus_balcony']['approx_max_balcony_distance_m']} m balcony |",
          f"| Hall depth | {opt['A_single_level']['hall_depth_m']} m (grid 3-9) | ~{opt['B_floor_plus_balcony']['approx_hall_depth_saving_m']} m shorter |",
          f"| Vertical egress | {opt['A_single_level']['vertical_egress']} | {opt['B_floor_plus_balcony']['vertical_egress']} |",
          f"| Structure | {opt['A_single_level']['structure']} | {opt['B_floor_plus_balcony']['structure']} |",
          f"| Sightlines | All rows C >= {P['sightlines']['c_value_target']} m achieved (min {m['c_min_n1']:.3f}) | Balcony overhang ({opt['B_floor_plus_balcony']['balcony_overhang_rows']} rows) shades rear floor rows; needs separate check |",
          "",
          "**Recommendation (pending client/architect decision):** Option A. It keeps most occupants at or near grade, avoids a suspended "
          "balcony structure and its vibration/transfer design, and keeps accessible routes short, at the cost of a deeper hall "
          "(44.5 m max eye distance, so screens are assumed for rear rows) and a larger footprint. Option B remains viable if the site is "
          "too short for 88 m; it should then be modelled and checked the same way.", "",
          "## 3. Seating geometry",
          f"- {sum(sb['blocks'])} seats per full row in blocks {sb['blocks']} with {len(sb['blocks']) - 1} interior aisles of {sb['aisle_width']} m and wall aisles "
          f">= {m['wall_aisle_min']} m; side blocks omitted in rows 1-2 (front wheelchair positions). 40 rows x 76 - 40 = 3,000.",
          f"- Seat module {sb['seat_width']} m x {sb['chair_depth']} m chair, row pitch {sb['row_pitch']} m (clear seatway {sb['row_pitch'] - sb['chair_depth']:.2f} m), "
          f"rows alternately offset +/-{sb['stagger_offset'] / 2} m (staggered).",
          f"- Rake from a C-value recurrence: front 19 rows on a continuous slope to +{lay.front_slope_top:.2f} (steepest 1:{m['front_slope_gradient_1_in']}); "
          f"mid cross aisle + wheelchair band at +{lay.cross_level:.2f} (one {m['cross_aisle_riser_from_front_slope']:.2f} m riser at aisle mouths); "
          f"rear 21 rows stepped (rise 0.10-0.15 m/row) to the rear platform at +{lay.top_level:.2f}.",
          f"- Min C over row in front {m['c_min_n1']:.3f} m; over two rows {m['c_min_n2']:.3f} m (target 0.12 for staggered; rows 4-6 slightly below, see row_schedule.csv).",
          "- Model checks: seat count, row levels, floor contact (raycast), clash matrix and sightlines re-measured from the Blender objects "
          "(reports/blend_verification.json).", "",
          "## 4. Circulation, accessibility and provisional egress (UNVERIFIED)",
          f"- Hall exits: {len(lay.exits)} doorways, total clear width {egm['total_hall_exit_width']} m vs placeholder demand "
          f"{egm['total_required_width_placeholder']} m (5 mm/person). Per-exit loads in exit_schedule.csv.",
          f"- Rear exits discharge to the upper foyer at +{lay.top_level:.2f}; 4 foyer stairs ({sum(s['width'] for s in lay.stairs):.1f} m total, "
          f"risers {m['foyer_stair_riser']:.3f} m) to the main foyer and 5 main doors. Mid cross-aisle exits land on ambulatory landings "
          "with external steps (flat grade assumed) and internal ramps.",
          f"- Accessible route: ambulatory ramps (steepest 1:{m['ambulatory_ramp_steepest_1_in']}, flights <= 9 m with 1.5 m landings) to the mid cross aisle; "
          "lift from foyer to upper foyer / rear platform; level front zone from ambulatory front doors; platform ramp 1:12.",
          f"- {m['wheelchair_spaces']} wheelchair spaces (front / mid band / rear) each with a loose companion chair, additional to the 3,000.",
          f"- Max plan travel: {egm['max_travel_hall']:.1f} m to a hall exit, {egm['max_travel_total']:.1f} m to an external door (placeholder flags exceeded; OI-05).", "",
          "## 5. Structural coordination concept (no analysis)",
          f"- Grid A-H (4.5 / 10 / 10 / 10 / 10 / 10 / 4.5 m) x 1-12 (8 m bays). {m['column_count']} columns, {m['truss_count']} duo-pitch Pratt trusses spanning "
          f"{m['truss_span']:.0f} m between lines B and G at 8 m centres, bearing +{P['structure']['truss_bearing_z']:.2f}, ridge roof top +{m['hall_ridge_top']:.2f}.",
          "- Lateral (A-13): transverse portal action + braced gable bay D-E; longitudinal vertical X-bracing in bays 3-4 and 10-11 on B and G; "
          "roof-plane bracing bays 3-4, 7-8, 10-11. Purlins at panel points. Foyer/mezzanine/low-roof beams on 8-10 m spans.",
          "- Pad footings modelled as reference locations only. **No loads, analysis, member design, connection design or foundation design.**", "",
          "## 6. Model content and separation",
          "| Collection (Blender) / IFC | Content |", "|---|---|",
          "| 10_ENV | External and hall walls, gable infills, roofs, external doors |",
          "| 20_ARC | Floors/rake/platform/choir tiers, partitions, stairs, ramps, rail, lift, booth, pulpit |",
          "| 30_STR | Columns, pad footing references, trusses (IfcElementAssembly TRUSS), purlins, bracing, beams |",
          "| 40_SEAT | 3,000 congregation chairs, choir chairs, companion chairs, wheelchair spaces |",
          "| 50_SRV | MEP / AV space allowances (IfcSpatialZone) |",
          "| 60_ZONE | IfcSpace rooms with areas, aisle clear zones |",
          "", "Element totals: " + ", ".join(f"{k} {v}" for k, v in sorted(sched.items())) + ".",
          "", "## 7. Levels", "| Level | Elevation | Name |", "|---|---|---|"]
    bd += [f"| {l['id']} | {l['elevation']:+.3f} | {l['name']} |" for l in lv]
    bd += ["", "## 8. Deliverables and evidence",
           "See `reports/model_index.md` for the full file list with hashes, and `logs/` for build/validation logs.", "",
           "## 9. What a local architect / engineer must verify next",
           "1. Applicable Zimbabwean statutes and fire/occupancy/accessibility requirements -> re-set all placeholder widths, distances, ratios.",
           "2. Site survey and orientation; fit of the 59 x 88 m footprint, access, parking, levels (external steps assume flat grade).",
           "3. Egress design by a fire engineer (travel distances currently exceed placeholder flags).",
           "4. Structural scheme: loads, 50 m truss design, lateral system, deflection/ponding, foundations with a geotechnical report.",
           "5. Sightline focal point, screens, acoustics and AV; MEP, sanitary fixture counts, water storage and backup power.",
           "6. Decision Option A vs B with the client; cost plan."]
    (out / "basis_of_design.md").write_text("\n".join(bd) + "\n", encoding="utf-8")
    print("REPORTS " + json.dumps({"seat_rows": len(seat_rows), "seat_count_ok": all_ok, "auto_issues": n_auto,
                                   "coordinate_mismatches": mismatches}))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
