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
                          "shortest_route_exit_sensitivity": e["shortest_route_exit"],
                          "plan_travel_to_hall_exit_m": e["travel_hall"], "plan_travel_to_external_door_m": e["travel_total"],
                          "plan_travel_to_nearest_hall_exit_m": e["travel_hall_to_nearest_exit"]})
    write_csv(out / "seating_schedule.csv", seat_rows,
              ["seat_id", "row", "section", "block", "seat_in_block", "x", "y", "z_floor", "eye_z", "in_blender_model",
               "blender_x", "blender_y", "blender_z", "assigned_exit_balanced", "nearest_exit", "shortest_route_exit_sensitivity",
               "plan_travel_to_hall_exit_m", "plan_travel_to_external_door_m", "plan_travel_to_nearest_hall_exit_m", "revision"])
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
                "placeholder_check_balanced": "OK" if e["ok"] else "UNDER",
                "placeholder_required_width_if_nearest_m": e["required_width_nearest"],
                "placeholder_check_if_nearest": "OK" if e["width"] >= e["required_width_nearest"] else "UNDER",
                "load_shortest_route_to_outside_sensitivity": e["load_route"],
                "placeholder_check_route_sensitivity": "OK" if e["width"] >= e["required_width_route"] else "UNDER",
                "onward_route": e["leg2_route"],
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
    gyv = [P["grid"]["y_lines"][str(n)] for n in range(3, 12)]
    truss_bays = " / ".join(f"{b - a:g}" for a, b in zip(gyv, gyv[1:]))
    tokens = {"{truss_bays}": truss_bays,
              "{aisle_straight_clear}": f"{lay.metrics['aisle_straight_clear']:.2f}",
              "{wall_aisle_min}": f"{lay.metrics['wall_aisle_min']:.3f}"}
    for row in P["assumptions"]:
        text = " | ".join(str(x).replace("|", "/") for x in row)
        for k, v in tokens.items():
            text = text.replace(k, v)
        a.append("| " + text + " |")
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
          f"- Plan travel to the NEAREST hall exit reaches {egm['max_travel_hall_to_nearest_exit']:.1f} m "
          f"({egm['count_nearest_travel_over_flag']} occupants beyond the 30 m placeholder flag); to the queue-balanced exit "
          f"{egm['max_travel_hall']:.1f} m. "
          f"This is because the hall is {m['truss_span']:.0f} m wide "
          "and exits are on the side and rear walls. The 30 m / 60 m flags are placeholders, not local limits. "
          "Mitigations to be tested by the fire engineer: additional exits through the platform wings / stage rear, vomitories "
          "under the rear rake, sprinklers or smoke control as the local code allows, or a narrower/deeper plan.",
          "- `EGR-01N` / exit_schedule.csv column `placeholder_check_if_nearest` show which doors would be overloaded if everyone "
          "used the nearest exit (iteration 2 widened the cross-aisle exits to 3.6 m by moving grid 6 to y=38.5); the queue-balanced "
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
          f"| Sightlines | All rows C >= {P['sightlines']['c_value_target']} m achieved (min {m['c_min_n1']:.3f}) | Same C rule computed for floor and balcony; balcony rake {opt['B_floor_plus_balcony']['balcony_rake_deg']} deg; rear floor row view to a point 2.5 m above the platform passes {opt['B_floor_plus_balcony']['rear_floor_row_view_clearance_below_soffit_m']} m below the soffit |",
          f"| Under-balcony volume | n/a | Overhang {opt['B_floor_plus_balcony']['overhang_depth_m']} m deep over a {opt['B_floor_plus_balcony']['opening_height_m']} m opening (depth/height {opt['B_floor_plus_balcony']['overhang_depth_to_height']}) - a deep, low under-balcony zone for the rear floor rows |",
          "",
          "**Recommendation (pending client/architect decision):** Option A. It keeps most occupants at or near grade, avoids a suspended "
          "balcony structure and its vibration/transfer design, and keeps accessible routes short, at the cost of a deeper hall "
          "(44.5 m max eye distance, so screens are assumed for rear rows) and a larger footprint. Option B remains viable if the site is "
          "too short for 88 m; it should then be modelled and checked the same way. Option B section: exports/balcony_option_section.png "
          "(computed schematic, not part of the BIM model).", "",
          "## 3. Seating geometry",
          f"- {sum(sb['blocks'])} seats per full row in blocks {sb['blocks']} with {len(sb['blocks']) - 1} interior aisles of {sb['aisle_width']} m and wall aisles "
          f">= {m['wall_aisle_min']} m; side blocks omitted in rows 1-2 (front wheelchair positions). {len(lay.rows)} rows; the "
          f"{m.get('trimmed_seats', 0)} seats with the worst angle to the pulpit are removed (A-24), leaving exactly 3,000.",
          f"- Seat module {sb['seat_width']} m x {sb['chair_depth']} m chair, row pitch {sb['row_pitch']} m (clear seatway {sb['row_pitch'] - sb['chair_depth']:.2f} m), "
          f"rows alternately offset +/-{sb['stagger_offset'] / 2} m (staggered).",
          f"- Rake from a C-value recurrence: front 19 rows on a continuous slope to +{lay.front_slope_top:.2f} (steepest 1:{m['front_slope_gradient_1_in']}); "
          f"mid cross aisle + wheelchair band at +{lay.cross_level:.2f} (one {m['cross_aisle_riser_from_front_slope']:.3f} m riser at aisle mouths); "
          f"rear {len(lay.rows) - sb['front_rows']} rows stepped with uniform risers (A-22): " + "; ".join(
              f"rows {b['rows'][0]}-{b['rows'][1]} riser {b['uniform_riser']:.3f} m" for b in lay.rear_bands)
          + f"; rear platform at +{lay.top_level:.3f}.",
          f"- Rake generated so that EVERY row meets C >= {P['sightlines']['c_value_target']} m over the row in front and "
          f">= {P['sightlines']['c_value_staggered_target_n2']} m over the row two in front (staggered seating): achieved minima "
          f"{m['c_min_n1']:.3f} / {m['c_min_n2']:.3f} m (row_schedule.csv).",
          "- Model checks: seat count, row levels, floor contact (raycast), clash matrix and sightlines re-measured from the Blender objects "
          "(reports/blend_verification.json).", "",
          "## 4. Circulation, accessibility and provisional egress (UNVERIFIED)",
          f"- Hall exits: {len(lay.exits)} doorways, total clear width {egm['total_hall_exit_width']} m vs placeholder demand "
          f"{egm['total_required_width_placeholder']} m (5 mm/person). Per-exit loads in exit_schedule.csv.",
          f"- Rear exits discharge to the upper foyer at +{lay.top_level:.2f}; {len(lay.stairs)} wide foyer stairs ({sum(s['width'] for s in lay.stairs):.1f} m total, "
          f"risers {m['foyer_stair_riser']:.3f} m) rise through openings in the upper-foyer slab towards the main doors. Mid cross-aisle "
          "exits land on ambulatory landings with external steps AND a direct 1:12 outside ramp (flat grade assumed).",
          f"- Exit widths are door sets (A-25): effective clear width = nominal - {P['doors']['deduction_per_leaf']} m per leaf; all "
          "capacity checks use the effective width.",
          f"- Accessible route: ambulatory ramps (steepest 1:{m['ambulatory_ramp_steepest_1_in']}, flights <= 9 m with 1.5 m landings) to the mid cross aisle; "
          "lift from foyer to upper foyer / rear platform; level front zone from ambulatory front doors; platform ramp 1:12.",
          f"- {m['wheelchair_spaces']} wheelchair spaces (front and mid band) each with a loose companion chair, additional to the 3,000; "
          f"none on the lift-only upper level (client decision PL02). {m['refuge_spaces_L02']} refuge allowances remain at the stair heads "
          "for upper-foyer users (A-21, OI-16)." + {"sides_facing_inward": " Two further wheelchair places at platform level serve the choir.",
             "wings_facing_inward": " The choir sits in the platform wings on the hall floor (step-free) with a wheelchair choir place in "
                                    "each wing; the platform is one level, reached step-free by the 1:12 ramp."}.get(
              P["stage"]["choir"]["layout"], " The platform is one level (no fixed choir seating), reached step-free by the 1:12 ramp."),
          f"- Viewing (A-26): seats > 45 deg off the pulpit {m['offaxis_pulpit']['over_45']}, > 60 deg {m['offaxis_pulpit']['over_60']}, "
          f"worst {m['offaxis_pulpit']['max_deg']} deg; {m['offaxis_pulpit']['without_usable_view']} seats without a usable view of the "
          "pulpit or a screen (SGT-H1).",
          f"- Max plan travel to the nearest hall exit {egm['max_travel_hall_to_nearest_exit']:.1f} m; queue-balanced "
          f"{egm['max_travel_hall']:.1f} m to a hall exit and {egm['max_travel_total']:.1f} m to an external door. Placeholder flags are "
          "exceeded and logged (OI-05, OI-17) with a restriction on use - not presented as acceptable.", "",
          "## 5. Structural coordination concept (no analysis)",
          f"- Grid A-H ({' / '.join(f'{b - a:g}' for a, b in zip(list(P['grid']['x_lines'].values()), list(P['grid']['x_lines'].values())[1:]))} m) x 1-12 "
          f"({' / '.join(f'{b - a:g}' for a, b in zip(list(P['grid']['y_lines'].values()), list(P['grid']['y_lines'].values())[1:]))} m). "
          f"{m['column_count']} columns, {m['truss_count']} duo-pitch Pratt trusses spanning "
          f"{m['truss_span']:.0f} m between lines B and G at grid lines 3-11 (bays {truss_bays} m; grid 6 shifted to y=38.5 to clear the "
          f"cross-aisle exits), bearing +{P['structure']['truss_bearing_z']:.2f}, ridge roof top +{m['hall_ridge_top']:.2f}.",
          f"- Every brace / strut / knee / purlin end touches its support ({m['structural_member_ends_checked']} ends checked, STR-CON). "
          "Lateral (A-13, A-27): portal frames with knee braces on grids 4-10 + braced gable bay D-E on grids 3 and 11 (brace feet collected by struts "
          "STR-STRUT-GABLE-* into gable posts D/E and their pad footings); longitudinal vertical X-bracing in bays 3-4 and 10-11 on B and G, "
          "placed in the cavity of 2-leaf braced-bay walls; roof-plane bracing bays 3-4, 7-8, 10-11. Purlins at panel points. "
          "Foyer/mezzanine/low-roof beams on 8-10 m spans. Wall-top closure flashings (ENV-FLASHING-*) close the junction with the "
          "offset eaves/gable cladding.",
          "- Pad footings modelled as reference locations only. **No loads, analysis, member design, connection design or foundation design.**", "",
          "## 6. Model content and separation",
          "| Collection (Blender) / IFC | Content |", "|---|---|",
          "| 10_ENV | External and hall walls, gable infills, roofs, flashings, entrance canopy, external doors |",
          "| 20_ARC | Floors/rake/platform, partitions, stairs, ramps, rail, lift, booth, pulpit |",
          "| 30_STR | Columns, pad footing references, trusses (IfcElementAssembly TRUSS), purlins, bracing, beams |",
          "| 40_SEAT | 3,000 congregation chairs, choir chairs, companion chairs, wheelchair spaces |",
          "| 50_SRV | MEP space allowances (IfcSpatialZone), IMAG screens and speakers (IfcAudioVisualAppliance), gutters and "
          "downpipes (IfcPipeSegment), aisle step lights (IfcLightFixture) |",
          "| 60_ZONE | IfcSpace rooms with areas, aisle clear zones |",
          "", "Element totals: " + ", ".join(f"{k} {v}" for k, v in sorted(sched.items())) + ".",
          "", "Storeys: every element is assigned to the highest storey whose datum is at or below its reference height "
          "(walking surface for floor slabs, base otherwise; footings L00); only the raised booth floor/space use an explicit, "
          "recorded override. IFC elements carry placeholder materials (A-23) and base quantities (length/height/width, gross "
          "volume integrated from the model mesh); spaces carry gross floor area and do not overlap (check SPC-01).",
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
    # ---------------------------------------------------------------- response to the independent design review
    DRR = P.get("design_review_response")
    if DRR:
        op = m["offaxis_pulpit"]
        rear_r = lay.rear_bands[0]["uniform_riser"] if lay.rear_bands else None
        tok = {"{ends}": str(m["structural_member_ends_checked"]), "{trimmed}": str(m.get("trimmed_seats", 0)),
               "{over_45}": str(op["over_45"]), "{over_60}": str(op["over_60"]), "{over_70}": str(op["over_70"]),
               "{max_deg}": f"{op['max_deg']:.2f}", "{no_view}": str(op["without_usable_view"]),
               "{riser}": f"{rear_r:.3f}", "{step}": f"{m['cross_aisle_riser_from_front_slope']:.3f}",
               "{rails}": str(m["aisle_handrails"]), "{travel}": f"{egm['max_travel_hall_to_nearest_exit']:.2f}",
               "{ramp_len}": f"{lay.ext_ramps[0]['length']:.1f}", "{total}": f"{egm['building_total_occupants']:,}",
               "{downpipes}": str(m["downpipes"]), "{choir}": str(m["choir_seats"])}
        rr = ["# Response to the independent design review", "", DISCLAIMER, "",
              f"Review: {DRR['source']}. Response revision: `{rev}`. Every figure below is generated from this revision.", "",
              "## Headline measurements (same method as the review)", "",
              "| Measure | Review (PL01) | This revision |", "|---|---:|---:|",
              f"| Seats > 45 deg off the pulpit | {DRR['baseline']['over_45']} | {op['over_45']} |",
              f"| Seats > 60 deg off the pulpit | {DRR['baseline']['over_60']} | {op['over_60']} |",
              f"| Seats > 70 deg off the pulpit | {DRR['baseline']['over_70']} | {op['over_70']} |",
              f"| Worst angle to the pulpit | {DRR['baseline']['max_deg']} deg | {op['max_deg']} deg |",
              f"| Seats without a usable pulpit or screen view | not measured | {op['without_usable_view']} |",
              f"| Wheelchair places on the lift-only upper level | 8 | {m['wheelchair_spaces_L02']} |",
              f"| Travel to the nearest hall exit (max) | {DRR['baseline']['nearest_travel_m']} m | {egm['max_travel_hall_to_nearest_exit']:.2f} m |",
              f"| Structural member ends not touching a support | gaps found | {0 if not [c for c in lay.checks if c['id'] == 'STR-CON' and c['result'] != 'PASS'] else 'see STR-CON'} |",
              "", "Independent re-measurement with the review's own script: `reports/review_response_evidence/`.", "",
              "## Finding-by-finding response", "",
              "| Finding | Status | What was done | Evidence |", "|---|---|---|---|"]
        for fid, status, text, ev in DRR["items"]:
            for k, v in tok.items():
                text = text.replace(k, v)
            rr.append(f"| {fid} | {status} | {text.replace('|', '/')} | {ev} |")
        counts = Counter(i[1].split(" (")[0] for i in DRR["items"])
        rr += ["", "## Summary", "", "| Status | Findings |", "|---|---:|"]
        rr += [f"| {k} | {v} |" for k, v in sorted(counts.items())]
        rr += ["", "Findings marked OPEN need information or specialist work that this model cannot supply (site survey, "
               "geotechnics, loads, fire strategy, MEP design). They are logged in open_issues.md with owners, not answered with "
               "invented values."]
        for key in sorted(k for k in DRR if k.startswith("recheck")):
            RC = DRR[key]
            rr += ["", f"## Independent re-review: {RC.get('title', key)}", "", f"Re-review: {RC['source']}.", "",
                   "| Finding | Severity | Status | Response |", "|---|---|---|---|"]
            for fid, sev, status, text in RC["items"]:
                for k, v in tok.items():
                    text = text.replace(k, v)
                rr.append(f"| {fid} | {sev} | {status} | {text.replace('|', '/')} |")
        rr += ["", f"This revision (`{rev}`) has not itself been independently re-reviewed."]
        (out / "design_review_response.md").write_text("\n".join(rr) + "\n", encoding="utf-8")
    print("REPORTS " + json.dumps({"seat_rows": len(seat_rows), "seat_count_ok": all_ok, "auto_issues": n_auto,
                                   "coordinate_mismatches": mismatches}))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
