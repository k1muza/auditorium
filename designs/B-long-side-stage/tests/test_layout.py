"""Unit tests for the Option B layout engine (pure Python, no Blender)."""
import copy
import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import layout as L  # noqa: E402

P0 = L.load_params(L.DEFAULT_CONFIG)
LAY = L.compute(copy.deepcopy(P0))


class TestOptionB(unittest.TestCase):
    def test_exactly_3000_unique_seats(self):
        ids = [s["seat_id"] for s in LAY.seats]
        self.assertEqual(len(ids), 3000)
        self.assertEqual(len(set(ids)), 3000)

    def test_no_failing_layout_checks(self):
        failing = [c["id"] for c in LAY.checks if c["result"] == "FAIL"]
        self.assertEqual(failing, [])

    def test_deterministic(self):
        again = L.compute(copy.deepcopy(P0))
        self.assertEqual([(s["seat_id"], s["x"], s["y"], s["z_floor"]) for s in again.seats],
                         [(s["seat_id"], s["x"], s["y"], s["z_floor"]) for s in LAY.seats])
        self.assertEqual([e.name for e in again.elements], [e.name for e in LAY.elements])

    def test_unique_prefixed_element_names(self):
        names = [e.name for e in LAY.elements]
        self.assertEqual(len(names), len(set(names)))
        pre = ("ACC-", "ARC-", "DR-", "ENV-", "SEAT-", "SPC-", "SRV-", "STR-", "WN-")
        self.assertEqual([n for n in names if not n.startswith(pre)], [])

    def test_chairs_face_the_platform_focus(self):
        for s in LAY.seats[::97]:
            fx, fy = -math.sin(math.radians(s["rot_z"])), math.cos(math.radians(s["rot_z"]))
            vx, vy = LAY.F[0] - s["x"], LAY.F[1] - s["y"]
            self.assertGreater((fx * vx + fy * vy) / math.hypot(vx, vy), math.cos(math.radians(0.5)))

    def test_c_values(self):
        self.assertGreaterEqual(LAY.metrics["c_min_n1"], 0.06 - 1e-4)
        self.assertGreaterEqual(LAY.metrics["c_min_n2"], 0.12 - 1e-4)

    def test_rows_level_and_rising(self):
        floors = [r["floor"] for r in LAY.rows]
        self.assertEqual(floors, sorted(floors))
        for r in LAY.rows:
            zs = {s["z_floor"] for s in LAY.seats if s["row"] == r["row"]}
            self.assertEqual(len(zs), 1)

    def test_wheelchair_spaces_one_percent(self):
        self.assertGreaterEqual(len(LAY.wc_positions), 30)

    def test_egress_tally(self):
        eg = LAY.metrics["egress"]
        self.assertEqual(eg["seats"], 3000)
        self.assertGreaterEqual(eg["total_hall_exit_clear_width"], eg["total_required_width_placeholder"])

    def test_storeys_follow_the_validator_rule(self):
        lv = sorted(LAY.levels(), key=lambda v: v["elevation"])
        for el in LAY.elements[::53]:
            self.assertIn(el.storey, {v["id"] for v in lv})

    def test_seat_count_responds_to_parameters(self):
        P = copy.deepcopy(P0)
        P["seating"]["target_congregation_seats"] = 2500
        lay = L.LayoutB(P).compute()
        self.assertEqual(len(lay.seats), 2500)

    def test_grid_written_from_seating(self):
        G = LAY.P["grid"]["y_lines"]
        self.assertAlmostEqual(G["4"], LAY.ysw, places=3)
        self.assertLess(G["2"], G["3"])
        self.assertLess(G["3"], G["4"])


if __name__ == "__main__":
    unittest.main()
