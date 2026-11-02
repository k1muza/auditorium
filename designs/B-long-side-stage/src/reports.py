"""Option B reports, generated from the layout engine AND cross-checked against the Blender manifest, the re-opened
.blend verification and the IFC validation (whichever exist).

  .venv/Scripts/python designs/B-long-side-stage/src/reports.py <blender_manifest.json> <reports dir>
"""
import csv
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import layout as L  # noqa: E402

STATUS = ("CONCEPT - UNVERIFIED - NOT FOR CONSTRUCTION. Placeholder factors only; no code compliance, fire/egress approval, "
          "structural design, geotechnical input or cost estimate is claimed. Reviewer scores are QA metrics, not approval.")


def write_csv(path, rows):
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def main(manifest_path, out_dir):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    P = L.load_params(L.DEFAULT_CONFIG)
    lay = L.compute(P)
    M = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    rev = M["revision"]
    did = P["project"]["design_id"]
    man_seats = {o["name"]: o for o in M["objects"] if o["collection"] == "40_SEAT_Congregation"}
    # ---- schedules
    seats = [{"design_id": did, "revision": rev, "seat_id": s["seat_id"], "row": s["row"], "block": s["block"], "seat": s["seat"],
              "section": s["section"], "x": s["x"], "y": s["y"], "z_floor": s["z_floor"], "facing_deg": s["rot_z"],
              "radius_from_focus": round(s["r"], 3)} for s in lay.seats]
    write_csv(out / "seating_schedule.csv", seats)
    write_csv(out / "row_schedule.csv", [{"design_id": did, "revision": rev, **r} for r in lay.rows])
    write_csv(out / "space_schedule.csv", [{"design_id": did, "revision": rev, "space_id": s["id"], "name": s["name"],
                                            "level": s["level"], "use": s.get("use", ""), "area_m2": s.get("area", ""),
                                            "status": "Concept allowance - unverified"} for s in lay.spaces])
    write_csv(out / "exit_schedule.csv", [{"design_id": did, "revision": rev, "exit_id": e["id"], "wall": e["wall"], "level": e["level"],
                                           "kind": e["kind"], "x": e["x"], "y": e["y"], "sill_z": round(e["z"], 3), "door_width": e["width"],
                                           "clear_width": e["clear"], "capacity_width": e["capacity_width"], "stair_behind": e.get("stair") or "",
                                           "assigned_occupants": e["load"], "required_width_placeholder": e["required_width"],
                                           "final_exit": e["final_exit"], "role": e["role"]} for e in lay.exits])
    write_csv(out / "accessible_positions.csv", [{"design_id": did, "revision": rev, "space": w["name"], "group": w["group"],
                                                  "x": w["x"], "y": w["y"], "floor": w["z"], "companion_chair": w["companion"]}
                                                 for w in lay.wc_positions])
    write_csv(out / "egress_travel.csv", [{"occupant": r["occupant"], "kind": r["kind"], "x": round(r["x"], 2), "y": round(r["y"], 2),
                                           "hall_exit": r["exit"], "travel_hall_m": r["travel_hall"], "travel_nearest_m": r["travel_nearest"],
                                           "final_exit": r["final_exit"], "travel_total_m": r["travel_total"]} for r in lay.egress_results])
    cls = Counter((o["ifc_class"], o["predefined_type"], o["collection"]) for o in M["objects"])
    write_csv(out / "element_schedule.csv", [{"design_id": did, "revision": rev, "ifc_class": c, "predefined_type": p, "collection": col,
                                              "count": n} for (c, p, col), n in sorted(cls.items())])
    # ---- seat count corroboration across independent sources
    bv = json.loads((out / "blend_verification.json").read_text(encoding="utf-8")) if (out / "blend_verification.json").exists() else None
    iv = json.loads((out / "ifc_validation.json").read_text(encoding="utf-8")) if (out / "ifc_validation.json").exists() else None
    blend_n = next((c["value"] for c in bv["checks"] if c["id"] == "BLD-SEATS"), None) if bv else None
    ifc_n = next((c["value"] for c in iv["checks"] if c["id"] == "IFC-SEATS"), None) if iv else None
    csv_ids = {s["seat_id"] for s in seats}
    target = P["seating"]["target_congregation_seats"]
    ok = len(lay.seats) == len(man_seats) == len(csv_ids) == target and blend_n == target and ifc_n == target and csv_ids == set(man_seats)
    lines = [f"Seat count check - {did} revision {rev}", "",
             f"Layout engine seats (src/layout.py)              : {len(lay.seats)}",
             f"Blender manifest objects in 40_SEAT_Congregation : {len(man_seats)}",
             f"Saved .blend re-opened (blend_verification.json) : {blend_n}",
             f"IFC congregation seats (ifc_validation.json)     : {ifc_n}",
             f"seating_schedule.csv rows (unique ids)           : {len(seats)} ({len(csv_ids)})",
             f"CSV ids == manifest names                         : {csv_ids == set(man_seats)}", "",
             f"Excluded and counted separately: choir chairs {len(lay.choir)}, wheelchair spaces {len(lay.wc_positions)}, "
             f"companion chairs {len(lay.wc_positions)}.", "", "RESULT: " + ("PASS - all sources agree on exactly 3,000" if ok else "FAIL")]
    (out / "seat_count_check.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (out / "geometry_checks.json").write_text(json.dumps({"design_id": did, "revision": rev, "checks": lay.checks, "metrics": lay.metrics,
                                                          "levels": lay.levels(), "ramps": lay.ramps, "stairs": lay.stairs},
                                                         indent=2, default=str), encoding="utf-8")
    # ---- assumptions, open issues, basis of design
    m, eg = lay.metrics, lay.metrics["egress"]
    a = [f"# Assumptions register - {did} ({rev})", "", STATUS, "",
         "Common basis (carried from the project brief / Option A so the comparison is like-for-like) vs NEW PROPOSAL (Option B only).", "",
         "| ID | Assumption | Basis | Confidence |", "|---|---|---|---|"]
    for row in P["assumptions_extra"]:
        a.append(f"| {row[0]} | {row[1]} | {row[2]} | {row[3]} |")
    for sec in ("seating", "stage", "foyer", "structure", "av", "accessibility", "ambulatory", "rear_corners", "walls"):
        for k, v in P[sec].items():
            if k.startswith("_") and isinstance(v, str):
                a.append(f"| {sec}.{k.strip('_')} | {v} | {'Common basis' if 'Option A' in v and 'carried' in v.lower() else 'Proposal / note'} | - |")
    a += ["", "Egress factors are placeholders identical to Option A (5 mm/person level, 7.5 mm/person stair, 30 m / 60 m travel flags); "
          "they are not Zimbabwean code values."]
    (out / "assumptions.md").write_text("\n".join(a) + "\n", encoding="utf-8")
    warns = [c for c in lay.checks if c["result"] != "PASS"]
    oi = [f"# Open issues - {did} ({rev})", "", STATUS, "", "## Model checks not passing", ""]
    oi += [f"- **{c['id']}** ({c['result']}): {c['description']} - value {json.dumps(c['value'], default=str)[:200]}, criterion {c['criterion']}"
           for c in warns] or ["- none"]
    oi += ["", "## Unverified design items (for the professional team)", "",
           f"- Roof: {m['truss_count']} trusses simply supported over {m['truss_span']} m; foyer on {m['foyer_rafter_span']} m rafters; member sizes, "
           "connections, splices (transport length), erection / crane plan, deflection, wind uplift and foundations are NOT designed.",
           "- No movement joint is shown in the 80 m long building; thermal movement joints / roof expansion details TBC.",
           "- Single eaves gutter drains the whole main roof (about 60 m of roof per metre of gutter): overflow weirs, gutter access "
           "(fall protection) and rainwater-harvesting tank capacity TBC.",
           "- Excavation-free flat site assumed; survey, geotechnical report and storm-water strategy required (Zimbabwean rainy-season intensities).",
           f"- Egress: {eg['count_travel_hall_over_flag']} occupants exceed the 30 m in-hall placeholder flag (max {eg['max_travel_hall']} m); "
           "the stage-side exits cross the back-of-house corridor into dedicated exit passages, which need fire separation (TBC).",
           f"- Side seats reach {m['offaxis_pulpit']['max_bearing_from_pulpit_deg']:.0f} deg bearing from the pulpit: preaching to a "
           f"{2 * P['seating']['fan_half_angle_deg']:.0f} deg fan needs a speaker who turns, and IMAG reliance "
           f"({m['offaxis_pulpit']['relying_on_screens']} seats rely on screens - placeholder 30 m unaided limit).",
           f"- Choir: {m['choir_seats']} chairs on tiers beside the band, facing the congregation (Option A PL08: 386, facing inward). "
           "This changes the client's Option A preference (choir facing inward) - client to confirm for Option B.",
           "- Two-thirds of the congregation leaves at the rear-passage level (+L02) by stairs; the rake height is inherent to "
           "the shared C-value targets and to a 32-row fan.",
           "- Acoustic infill above the faceted rear-passage wall and over the rear wall between truss chords is not modelled (gap below roof).",
           "- Booth sits 0.4-6.2 m east of the centre line because the grid-F truss passes over the axis.",
           "- Concave faceted rear wall: absorptive / diffusive finish allowance only; focused-echo risk to be checked by an acoustician.",
           "- Rainwater harvesting tank shown as an allowance only; capacity, treatment and overflow not designed.",
           "- Acoustics (RT, early reflections across a wide fan), AV design, MEP, fire engineering and accessibility audits not done."]
    (out / "open_issues.md").write_text("\n".join(oi) + "\n", encoding="utf-8")
    pd = m["pulpit_distance"]
    bod = [f"# Basis of design - {did}", "", f"- **Model revision:** `{rev}` (Blender {M['blender_version']}; layout schema {L.SCHEMA_VERSION})",
           f"- **Status:** {STATUS}", "", "## Concept",
           "The platform stands on the middle of the long (north) wall. The congregation sits in a wide, shallow fan of concentric rows centred "
           "on the platform focus, so every chair faces the platform centre. One mono-pitch roof covers foyer and hall.", "",
           "## Key figures (measured from the model)", "",
           f"- Congregation seats: **{len(lay.seats)}** in {m['rows']} rows ({P['seating']['front_rows']} front rows on a slope to "
           f"+{lay.row_floor[P['seating']['front_rows'] - 1]:.2f}, cross aisle, {m['rows'] - P['seating']['front_rows']} stepped rear rows with "
           f"{m['rear_riser']:.3f} m risers to +{m['top_level']:.2f})",
           f"- Fan: +-{P['seating']['fan_half_angle_deg']:.0f} deg, {P['seating']['front_blocks']} front / {P['seating']['rear_blocks']} rear "
           f"blocks, max {m['max_seats_to_aisle']} seats to an aisle, aisles >= {m['aisle_min_clear']:.2f} m clear",
           f"- Eye-to-pulpit distance: max {pd['max']} m, mean {pd['mean']} m, 90th percentile {pd['p90']} m",
           f"- C-values: min {m['c_min_n1']} (row in front), {m['c_min_n2']} (2 rows, staggered)",
           f"- Max head turn to the pulpit {m['offaxis_pulpit']['max_head_turn_deg']} deg; max bearing from the pulpit "
           f"{m['offaxis_pulpit']['max_bearing_from_pulpit_deg']} deg",
           f"- Hall 80.0 x {m['hall_depth_grid_2_4']} m (grid A-L x 2-4); building footprint {m['footprint_m'][0]} x {m['footprint_m'][1]} m",
           f"- Platform {m['platform_area']} m2 at +{m['platform_height']:.2f}; choir {m['choir_seats']} chairs; wheelchair spaces "
           f"{m['wheelchair_spaces']} (+ companions)",
           f"- Structure: {m['column_count']} columns, {m['truss_count']} trusses (span {m['truss_span']} m), {m['purlin_count']} purlins, "
           f"{m['brace_count']} braces (incl. eaves-line wind girders); main roof {m['roof_area_main_m2']} m2 (sloped)",
           f"- Egress (placeholders): {eg['hall_exits']} hall exits, capacity width {eg['total_hall_exit_clear_width']} m vs "
           f"{eg['total_required_width_placeholder']} m required; max in-hall travel {eg['max_travel_hall']} m (nearest exit "
           f"{eg['max_travel_hall_to_nearest_exit']} m), mean {eg['mean_travel_hall']} m, max to outside {eg['max_travel_total']} m",
           "", "## Levels", ""] + [f"- {lv['id']} {lv['elevation']:+.3f} - {lv['name']}" for lv in lay.levels()]
    (out / "basis_of_design.md").write_text("\n".join(bod) + "\n", encoding="utf-8")
    print("REPORTS", json.dumps({"seats": len(lay.seats), "seat_check": ok, "files": 13}))
    if not ok and bv and iv:
        sys.exit("seat count sources disagree")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
