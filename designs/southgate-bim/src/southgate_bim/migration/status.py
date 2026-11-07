"""Design-status assignment.  Never assigns ENGINEERING_VERIFIED / APPROVED_FOR_DOCUMENTATION:
no engineering verification or approval evidence exists in the source project."""
from .plan import STRUCTURAL, SERVICES

ALLOWED = ("EXISTING_DESIGN_REFERENCE", "CONCEPT_UNVERIFIED", "PRELIMINARY_DESIGN",
           "ENGINEERING_VERIFIED", "APPROVED_FOR_DOCUMENTATION")


def design_status(el, props):
    if el.get("status_override"):
        st = el["status_override"]
        basis = f"classification rule {el['rule']} status override"
    elif el["ifc_class"] in STRUCTURAL or el["ifc_class"] == "IfcSlab" or el["rule"] in ("CORE-WALL",):
        st = "CONCEPT_UNVERIFIED"
        basis = "structural / potentially load-bearing element (LoadBearing not asserted): source states 'PRELIMINARY ARCHITECTURAL CONCEPT ONLY - NOT STRUCTURALLY VERIFIED' or carries no engineering evidence"
    elif el["ifc_class"] in SERVICES:
        st = "PRELIMINARY_DESIGN"
        basis = "building-services allowance/proposal from source studies; not engineered"
    else:
        st = "EXISTING_DESIGN_REFERENCE"
        basis = "architectural geometry as modelled in the verified source snapshot; no construction approval"
    sds = str(props.get("design_status", ""))
    if "REQUIRES_ENGINEERING" in sds or "NOT_ENGINEERED" in sds:
        if st == "EXISTING_DESIGN_REFERENCE":
            st = "CONCEPT_UNVERIFIED"
            basis += f"; source design_status={sds}"
    assert st in ALLOWED[:3], st
    return st, basis
