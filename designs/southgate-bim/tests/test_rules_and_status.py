import re
from pathlib import Path

import yaml

from southgate_bim.migration.plan import guid_for
from southgate_bim.migration.status import design_status
from southgate_bim.migration import openings
from southgate_bim.authoring.builder import rect_difference_polygon, polygon_area_2d, linear_to_srgb

ROOT = Path(__file__).resolve().parents[1]
NS = yaml.safe_load(open(ROOT / "config/project.yaml"))["project"]["guid_namespace"]


def test_guids_are_deterministic_and_distinct():
    a = guid_for("SOUTHGATE-WALL-0001", NS)
    assert a == guid_for("SOUTHGATE-WALL-0001", NS)
    assert a != guid_for("SOUTHGATE-WALL-0002", NS)
    assert len(a) == 22


def test_status_never_claims_verification():
    for cls in ("IfcBeam", "IfcWall", "IfcFan", "IfcFooting", "IfcSlab", "IfcFurniture"):
        el = {"ifc_class": cls, "rule": "X", "status_override": None}
        st, _ = design_status(el, {"design_status": "MODELLED_NOT_ENGINEERED"})
        assert st in ("EXISTING_DESIGN_REFERENCE", "CONCEPT_UNVERIFIED", "PRELIMINARY_DESIGN")
    st, _ = design_status({"ifc_class": "IfcMember", "rule": "X", "status_override": None}, {})
    assert st == "CONCEPT_UNVERIFIED"


def test_rect_difference_notch_and_hole():
    U = (0.0, 4.0, 0.0, 3.0)
    loops = rect_difference_polygon(U, [(1.5, 2.5, 2.0, 3.0)])     # lintel notch at the top
    assert len(loops) == 1 and abs(abs(polygon_area_2d(loops[0])) - (12 - 1)) < 1e-9
    loops = rect_difference_polygon(U, [(1.5, 2.5, 1.0, 2.0)])     # interior hole
    assert len(loops) == 2
    assert abs(abs(polygon_area_2d(loops[0])) - abs(polygon_area_2d(loops[1])) - 11) < 1e-9


def test_hole_grows_to_neighbouring_pieces():
    pieces = [(0, 1.0, 0, 3), (2.0, 3.0, 0, 3), (1.0, 2.0, 2.5, 3)]
    h = openings._grow((1.04, 1.96, 0.3, 2.38), pieces, (0, 3, 0, 3))
    assert h == (1.0, 2.0, 0, 2.5)


def test_classification_rules_compile_and_have_fallback():
    rules = yaml.safe_load(open(ROOT / "config/classification_rules.yaml"))["rules"]
    for r in rules:
        for k in ("coll", "name", "etype"):
            if k in r:
                re.compile(r[k])
        assert r["cls"].startswith("Ifc") and r["phase"] in "BCDEFGHI"
    assert "coll" not in rules[-1] and "name" not in rules[-1] and "etype" not in rules[-1]


def test_srgb_conversion():
    assert abs(linear_to_srgb(0.214) - 0.5) < 0.01 and linear_to_srgb(0) == 0 and abs(linear_to_srgb(1) - 1) < 1e-9
