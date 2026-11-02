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
        bad = copy.deepcopy(P)
        bad["seating"]["target_congregation_seats"] = 3001
        with self.assertRaises(RuntimeError):
            al.compute(bad)

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


class Determinism(unittest.TestCase):
    def test_repeatable(self):
        a = al.compute(copy.deepcopy(P))
        self.assertEqual([(e.name, e.origin) for e in a.elements], [(e.name, e.origin) for e in LAY.elements])


if __name__ == "__main__":
    unittest.main()
