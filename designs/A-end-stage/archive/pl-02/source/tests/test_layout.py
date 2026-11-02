"""Unit tests for the parametric layout engine (run: .venv/Scripts/python -m unittest discover -s tests -v)."""
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import auditorium_layout as al  # noqa: E402

P = al.load_params()
LAY = al.compute(copy.deepcopy(P))


class SeatCount(unittest.TestCase):
    def test_exactly_target(self):
        self.assertEqual(len(LAY.seats), 3000)
        self.assertEqual(sum(1 for e in LAY.elements if e.collection == "40_SEAT_Congregation"), 3000)

    def test_unique_ids(self):
        self.assertEqual(len({s["seat_id"] for s in LAY.seats}), 3000)

    def test_target_mismatch_raises(self):
        # a target the layout cannot reach (more seats than the rows hold) must stop the build
        bad = copy.deepcopy(P)
        bad["seating"]["target_congregation_seats"] = 3200
        with self.assertRaises(RuntimeError):
            al.compute(bad)

    def test_trim_removes_only_the_worst_offaxis_seats(self):
        lo, hi = LAY.metrics["trim_removed_angle_range_deg"]
        self.assertEqual(LAY.metrics["trimmed_seats"], 41 * 76 - 40 - 3000)
        self.assertLessEqual(LAY.metrics["offaxis_pulpit"]["max_deg"], lo + 1e-6)  # every kept seat is no worse than any removed one

    def test_parametric_change_changes_count(self):
        p = copy.deepcopy(P)
        p["seating"]["omit"] = []
        p["seating"]["target_congregation_seats"] = 3040
        p["accessibility"]["front_pairs_per_side"] = 0
        self.assertEqual(len(al.compute(p).seats), 3040)

    def test_excluded_seats_not_counted(self):
        for e in LAY.elements:
            if e.collection in ("40_SEAT_Choir", "40_SEAT_Companion"):
                self.assertFalse(e.props["CountsTowardTarget"])


class Geometry(unittest.TestCase):
    def test_no_seat_in_aisle(self):
        for rw in LAY.rows:
            for s in (s for s in LAY.seats if s["row"] == rw["row"]):
                for a0, a1 in rw["aisles"]:
                    self.assertFalse(a0 < s["x"] - 0.24 + 1e-6 < a1 or a0 < s["x"] + 0.24 - 1e-6 < a1, s["seat_id"])

    def test_no_seat_overlap(self):
        by = {}
        for s in LAY.seats:
            by.setdefault(s["row"], []).append(s["x"])
        for xs in by.values():
            xs.sort()
            self.assertTrue(all(b - a >= 0.48 for a, b in zip(xs, xs[1:])))

    def test_rows_monotonic_and_sightlines(self):
        floors = [rw["floor"] for rw in LAY.rows]
        self.assertEqual(floors, sorted(floors))
        for rw in LAY.rows[1:]:
            self.assertGreaterEqual(rw["c_n1"], P["sightlines"]["c_value_target"] - 1e-6, rw["row"])

    def test_wheelchair_positions_level_and_sighted(self):
        self.assertGreaterEqual(len(LAY.wc_positions), 30)
        for k, v in LAY.sight_extra.items():
            self.assertGreaterEqual(v["c_n1"], P["sightlines"]["c_value_target"] - 1e-6, k)

    def test_doors_clear_of_columns(self):
        c = next(c for c in LAY.checks if c["id"] == "CLS-01")
        self.assertEqual(c["result"], "PASS", c["value"])

    def test_seats_inside_hall(self):
        _, _, (x0, x1) = LAY.block_ranges()
        for s in LAY.seats:
            self.assertTrue(x0 + 1.5 <= s["x"] - 0.24 and s["x"] + 0.24 <= x1 - 1.5)
            self.assertTrue(P["grid"]["y_lines"]["3"] < s["y"] < P["stage"]["front_edge_y"])

    def test_unique_element_names(self):
        names = [e.name for e in LAY.elements]
        self.assertEqual(len(names), len(set(names)))

    def test_mesh_faces_valid(self):
        for e in LAY.elements:
            if e.mesh_key:
                continue
            v, f = e.local_mesh()
            self.assertTrue(all(0 <= i < len(v) for face in f for i in face), e.name)


class Egress(unittest.TestCase):
    def test_all_occupants_assigned(self):
        self.assertEqual(len(LAY.egress_results), 3000 + 2 * len(LAY.wc_positions))

    def test_balanced_widths_meet_placeholder(self):
        self.assertTrue(all(ex["ok"] for ex in LAY.exits))

    def test_stair_risers(self):
        self.assertLessEqual(LAY.metrics["foyer_stair_riser"], P["foyer"]["stair_max_riser"] + 1e-9)

    def test_total_capacity_independent_of_assignment(self):
        # independent of how occupants are assigned: summed width vs total placeholder demand
        occupants = len(LAY.egress_results) + P["egress_placeholders"]["choir_and_platform_occupants"]
        total = sum(ex["width"] for ex in LAY.exits)
        self.assertGreaterEqual(total, occupants * P["egress_placeholders"]["level_width_mm_per_person"] / 1000)

    def test_width_check_can_fail(self):
        # negative control: undersized exits must make EGR-01 and EGR-06 fail
        q = copy.deepcopy(P)
        for k in ("hall_front", "hall_wing", "hall_cross_aisle"):
            q["doors"][k]["width"] = 0.9
        q["doors"]["hall_rear_width"] = 0.9
        q["doors"]["cross_aisle_external"]["width"] = 0.9
        lay = al.compute(q)
        res = {c["id"]: c["result"] for c in lay.checks}
        self.assertEqual(res["EGR-01"], "FAIL")
        self.assertEqual(res["EGR-06"], "FAIL")

    def test_stair_heads_open_full_width_and_guarded_at_sides(self):
        # independent of stair metadata: the top tread's full width must meet the slab with no guard across it,
        # while guard pieces run along both sides of the slab opening
        rail = next(e for e in LAY.elements if e.name == "ARC-RAIL-UPPER-FOYER-EDGE")
        pieces = [al.part_aabb(p) for p in rail.parts]
        slab = next(e for e in LAY.elements if e.name == "ARC-SLAB-UPPER-FOYER")
        tl = LAY.top_level
        total = 0.0
        for st in (e for e in LAY.elements if e.name.startswith("ARC-STAIR-FOYER")):
            top = max(st.parts, key=lambda p: (al.part_aabb(p)[5], al.part_aabb(p)[4]))
            x0, _, _, x1, y_top, _ = al.part_aabb(top)
            across = [b for b in pieces if b[0] < x1 and b[3] > x0 and b[1] < y_top + 0.5 and b[4] > y_top - 0.05]
            self.assertFalse(across, st.name)  # nothing blocks the arrival
            arrive = [p for p in slab.parts if al.part_aabb(p)[0] <= x0 + 1e-6 and al.part_aabb(p)[3] >= x1 - 1e-6
                      and abs(al.part_aabb(p)[1] - y_top) < 1e-6 and abs(al.part_aabb(p)[5] - tl) < 1e-6]
            self.assertTrue(arrive, st.name)  # the slab continues at floor level right where the stair arrives
            sides = [b for b in pieces if b[4] > y_top - 0.5 and (abs(b[3] - (x0 - 0.15)) < 0.06 or abs(b[0] - (x1 + 0.15)) < 0.06)]
            self.assertGreaterEqual(len(sides), 2, st.name)
            total += x1 - x0
        self.assertGreaterEqual(total, LAY.metrics["egress"]["upper_foyer_stair_required_placeholder"])

    def test_connectivity_check_catches_a_gap(self):
        n, bad = LAY.connectivity()
        self.assertGreater(n, 300)
        self.assertEqual(bad, [])
        lay = al.compute(copy.deepcopy(P))
        brace = next(e for e in lay.elements if e.name.startswith("STR-BRACE-WALL"))
        p0, p1, w, h = brace.parts[0][1]
        brace.parts[0] = ("strut", ((p0[0], p0[1] + 0.1, p0[2]), p1, w, h))  # pull one end 0.1 m off its column
        _, bad2 = lay.connectivity()
        self.assertTrue(any(b["member"] == brace.name for b in bad2))

    def test_every_room_has_a_door_and_views_are_usable(self):
        res = {c["id"]: c["result"] for c in LAY.checks}
        for cid in ("SPC-03", "SGT-H1", "ACC-03", "ACC-06", "EGR-07", "CIR-05", "CIR-06", "STR-CON"):
            self.assertEqual(res[cid], "PASS", cid)
        acc_doors = [e for e in LAY.elements if e.ifc_class == "IfcDoor" and e.name.startswith("DR-WCA-")]
        self.assertEqual(len(acc_doors), 4)

    def test_no_wheelchair_places_on_lift_only_level(self):
        self.assertEqual(LAY.metrics["wheelchair_spaces_L02"], 0)
        self.assertGreaterEqual(LAY.metrics["wheelchair_spaces"], 30)

    def test_door_sets_reduce_effective_width(self):
        for ex in LAY.exits:
            self.assertLess(ex["width"], ex["width_nominal"])

    def test_travel_not_shorter_than_straight_line(self):
        pos = {s["seat_id"]: (s["x"], s["y"]) for s in LAY.seats}
        ex = {e["id"]: e for e in LAY.exits}
        for r in LAY.egress_results:
            if r["occupant"] not in pos:
                continue
            x, y = pos[r["occupant"]]
            for key, dist in (("nearest_exit", "travel_hall_to_nearest_exit"), ("exit", "travel_hall")):
                e = ex[r[key]]
                self.assertGreaterEqual(r[dist] + 1e-6, ((x - e["x"]) ** 2 + (y - e["y"]) ** 2) ** 0.5, (r["occupant"], key))

    def test_refuges_cover_upper_level_wheelchair_spaces(self):
        self.assertGreaterEqual(len(LAY.refuges), LAY.metrics["wheelchair_spaces_L02"])


class Semantics(unittest.TestCase):
    def test_storey_rule(self):
        lv = LAY.levels()
        for e in LAY.elements:
            if e.ifc_class == "IfcFooting" or "StoreyOverride" in e.props:
                continue
            if e.mesh_key:
                z0 = z1 = e.origin[2]
            else:
                bb = e.aabb()
                z0, z1 = bb[2], bb[5]
            self.assertEqual(e.storey, al.Layout.storey_for(lv, al.Layout.storey_ref_z(e.ifc_class, e.predefined, z0, z1)), e.name)

    def test_storey_overrides_applied(self):
        ov = [e for e in LAY.elements if "StoreyOverride" in e.props]
        self.assertTrue(ov)
        for e in ov:
            self.assertEqual(e.storey, e.props["StoreyOverride"].split(":")[0], e.name)

    def test_roof_structure_on_hall_roof_level(self):
        for e in LAY.elements:
            if e.assembly or e.predefined == "PURLIN" or e.name.startswith("STR-BRACE-ROOF"):
                self.assertEqual(e.storey, "L05", e.name)

    def test_no_empty_storey_and_no_space_overlap(self):
        res = {c["id"]: c["result"] for c in LAY.checks}
        self.assertEqual(res["BIM-01"], "PASS")
        self.assertEqual(res["SPC-01"], "PASS")
        self.assertEqual(res["SPC-02"], "PASS")

    def test_rear_risers_uniform_in_bands(self):
        for b in LAY.rear_bands:
            rises = {rw["rise"] for rw in LAY.rows if b["rows"][0] <= rw["row"] <= b["rows"][1]}
            self.assertEqual(len(rises), 1, b)

    def test_no_shear_walls_claimed(self):
        self.assertFalse([e.name for e in LAY.elements if e.predefined == "SHEAR"])


class Choir(unittest.TestCase):
    def test_side_choirs_face_inward_and_rear_clear(self):
        ch = [e for e in LAY.elements if e.collection == "40_SEAT_Choir"]
        self.assertEqual(len(ch), 144)
        x0, x1 = P["stage"]["platform_x"]
        mid = (x0 + x1) / 2
        for e in ch:
            west = e.origin[0] < mid
            self.assertEqual(e.rot_z, -90.0 if west else 90.0, e.name)  # W faces +X, E faces -X (towards centre)
            bb = al.instance_aabb(e)
            self.assertTrue(x0 - 1e-6 <= bb[0] and bb[3] <= x1 + 1e-6, e.name)  # on the platform
        # nothing in the old rear choir zone across the platform centre
        for e in ch:
            self.assertFalse(LAY.choir_sections["W"][1] < e.origin[0] < LAY.choir_sections["E"][0], e.name)
        self.assertGreater(LAY.metrics["platform_clear_centre_width"], 15.0)

    def test_choir_chairs_on_their_tier(self):
        tiers = [e for e in LAY.elements if e.name.startswith("ARC-CHOIR-")]
        for e in (e for e in LAY.elements if e.collection == "40_SEAT_Choir"):
            bb = al.instance_aabb(e)
            sup = [t for t in tiers if t.aabb()[0] - 1e-6 <= bb[0] and bb[3] <= t.aabb()[3] + 1e-6
                   and t.aabb()[1] - 1e-6 <= bb[1] and bb[4] <= t.aabb()[4] + 1e-6]
            self.assertEqual(len(sup), 1, e.name)
            self.assertAlmostEqual(sup[0].aabb()[5], e.origin[2], places=6)


class Determinism(unittest.TestCase):
    def test_repeatable(self):
        a = al.compute(copy.deepcopy(P))
        self.assertEqual([(e.name, e.origin) for e in a.elements], [(e.name, e.origin) for e in LAY.elements])


if __name__ == "__main__":
    unittest.main()
