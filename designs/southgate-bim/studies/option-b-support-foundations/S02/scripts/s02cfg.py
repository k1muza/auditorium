"""Revision S02 extensions to the S01 study model (S01 scripts are imported unchanged, never edited).

S02 design-basis changes (see S02 calculation record, section 2):
  LONG   longitudinal (side-wall) bracing arrangement, common to every stability system
         L0  S01: X-bracing below the clerestory sill (+9.90) in bays 1 and 5, knee braces in 1.08 m piers
         L1  L0 plus a third braced bay (bay 3, x 19.93-25.49, no doors on either wall)
         L2  bays 1 and 5 braced full height in two X tiers (node at +6.00); the clerestory window in each braced
             bay is replaced by masonry or the brace is accepted behind the glazing (architectural decision)
  EA_BR  axial-stiffness factor on bolted bracing members, girders, ties and struts (gusset and bolt flexibility
         with slip-resistant (preloaded) bolts; S01 = 1.0)
  KFI    factor on ULS wind actions for consequence class CC3 / reliability class RC3 (EN 1990 Annex B form)
  KROT   rotational base stiffness (kNm/rad) used for fixed bases in the design-basis model (semi-rigid)
"""
from __future__ import annotations
import os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
S02 = os.path.abspath(HERE + "/..")
S01 = os.path.abspath(S02 + "/..")
sys.path.insert(0, S01 + "/scripts")

import model_b as MB          # noqa: E402
import analyse as A           # noqa: E402
from frame3d import Prop      # noqa: E402

CFG = dict(LONG="L0", EA_BR=1.0, BAYS3=(1, 3, 5))
_orig_build = MB.build
BRACE_GROUPS = set(A.BAR_GROUPS)


def build2(d):
    if CFG["LONG"] == "L1":
        MB.WALL_BRACED_BAYS = CFG["BAYS3"]
    elif CFG["LONG"] == "L2":
        MB.WALL_BRACED_BAYS = ()
    else:
        MB.WALL_BRACED_BAYS = (1, 5)
    m = _orig_build(d)
    if CFG["LONG"] == "L2":
        iz = MB.COL_Z.index(6.00)
        for bay in (1, 5):
            for side in (0, 1):
                ca, cb = m.C[bay, side], m.C[bay + 1, side]
                wbx, wbs = MB.prop_of(d.sec["WBX"]), MB.prop_of(d.sec["WBS"])
                for a, b in ((ca[0], cb[iz]), (cb[0], ca[iz]), (ca[iz], cb[-1]), (cb[iz], ca[-1])):
                    m.add(a, b, wbx, "bar", "WBX", tag=dict(bay=bay, side=side))
                m.add(ca[iz], cb[iz], wbs, "beam", "WBS", ref=(0, 0, 1), tag=dict(bay=bay, side=side))
    f = CFG["EA_BR"]
    if f != 1.0:
        for e in m.elems:
            if e.group in BRACE_GROUPS and e.kind != "spring":
                p = e.prop
                e.prop = Prop(p.name, p.A * f, p.Iy, p.Iz, p.J, p.kg_m)
                e.prop._A_nom = p.A
    return m


MB.build = build2

# ---- S02 ground scenario added after client information (7 Nov 2026): a nearby water borehole struck water at
# about 23 m; the site is described as loam that becomes very wet in the rainy season. Not a site investigation.
# G3L = G3 strength/stiffness (wet, softened loam) WITHOUT a shallow design water table (no buoyancy) and without
# expansive-clay heave allowance. It isolates the cost of the assumed groundwater in the S01 G3 scenario.
import foundations as F  # noqa: E402
F.SOILS["G3L"] = dict(F.SOILS["G3"], label="G3L wet loam, deep water table (client borehole ~23 m): qa 100 kPa, no buoyancy",
                      gw=None, heave=False)

# ---- S02 anchorage: fixed bases with holding-down tension need pad depth >= hef + 0.45 m (EN 1992-4 splitting
# h >= 2 hef is not met at hef + 0.30; anchor reinforcement legs need anchorage below the cone), S01 used hef + 0.30
_orig_design_pad = F.design_pad
CFG["DMIN_FIXED_EXTRA"] = 0.15


def design_pad2(*a, **k):
    if k.get("fixed_base"):
        k["D_min"] = k.get("D_min", 0.45) + CFG["DMIN_FIXED_EXTRA"]
    return _orig_design_pad(*a, **k)


F.design_pad = design_pad2
