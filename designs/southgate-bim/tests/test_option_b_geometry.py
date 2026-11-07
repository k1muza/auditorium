"""Option B roof-truss geometry engine invariants (no IFC needed)."""
import math

import numpy as np
import pytest
from shapely.geometry import Point, Polygon

from southgate_bim.structure.optb_truss import OptionBTruss, load_rules, PANEL


@pytest.fixture(scope="module")
def trusses():
    rules, basis = load_rules()
    return {ln: OptionBTruss(ln, rules, basis) for ln in (0, 2, 4)}


def test_topology_matches_r2(trusses):
    for T in trusses.values():
        s = T.summary()
        assert s["webs"] == 25 and s["chord_pieces"] == 12 and s["angles"] == 74
        assert s["gussets"] == 26 and s["joints"] == 26 and s["splice_plates"] == 20
        bottom = sorted(n for n in T.nodes if n[0] == "B")
        assert len(bottom) == 13
        assert all(abs(T.nodes[f"B{k:02d}"][0] - PANEL * k) < 1e-9 for k in range(13))


def test_sections_follow_r2_basis(trusses):
    assert trusses[0].sec_tc.name == "L80x80x8" and trusses[4].sec_tc.name == "L90x90x8"
    assert trusses[4].members["D00"].section == "L100x100x8"
    assert trusses[0].members["D00"].section == "L75x75x6"


def test_top_of_steel_on_purlin_seat(trusses):
    for T in trusses.values():
        for s in (0.0, 5.4, 16.2, 27.0):
            perp = (T.z_tos(s) - (12.38 + math.tan(math.radians(15)) * min(s, 32.4 - s))) * math.cos(math.radians(15))
            assert abs(perp + 0.0105) < 1e-9


def test_bolts_inside_their_gusset_with_edge_distance(trusses):
    T = trusses[4]
    for J in T.joints.values():
        g = Polygon(T.plates[J.gusset].outline_sz)
        for bid in J.bolts:
            b = T.bolts[bid]
            assert g.contains(Point(b.s, b.z)), bid
            assert g.exterior.distance(Point(b.s, b.z)) >= T.bolt_cfg[b.diameter]["d0"] / 2 + 0.010, bid


def test_bolt_counts_follow_rules(trusses):
    T = trusses[4]
    roles = {}
    for b in T.bolts.values():
        roles[b.role] = roles.get(b.role, 0) + 1
    assert roles["WEB"] == 100 and roles["SPLICE"] == 80 and roles["CHORD"] == 64
    assert roles["PACKER"] == sum(1 for p in T.plates.values() if p.kind == "PACKER")


def test_webs_clear_chords(trusses):
    T = trusses[4]
    for m in T.members.values():
        if m.role in ("TC", "BC"):
            continue
        fp = T.footprint(m, m.t_start, m.t_end)
        for c in T.members.values():
            if c.role in ("TC", "BC"):
                assert fp.distance(T.footprint(c, c.t_start, c.t_end)) >= T.fit - 1e-6, (m.id, c.id)
