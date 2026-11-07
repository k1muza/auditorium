"""Plan-level wall consolidation and opening/host detection (axis-aligned building).

1. Coplanar wall pieces (box walls in one thickness band and material) that,
   together with door/window fillers and lintels, tile an exact rectangle are
   consolidated into ONE wall.  Each filler gets an opening equal to the free
   rectangle around it (grown to the neighbouring piece edges).  Lintels remain
   separate IfcBeam elements; the merged wall's elevation profile excludes them.
2. Every other filler is hosted by the wall whose body overlaps it most.
All evidence (residual areas, hole sizes) is recorded for the audit.
"""
from __future__ import annotations

from collections import defaultdict
import re

import numpy as np

MAX_GROW = 1.2        # max distance a hole may grow beyond its filler (m)
FRAME_RE = re.compile(r"FRAME|JAMB|HEAD(ER)?$|THRESHOLD|SILL$|-HEAD-|GLASS|GLAZING|PRIVACY|MULLION|FROSTED")
LOOSE_RE = re.compile(r"OPEN|HANDLE|PULL|EXIT-BAR|HINGE")


def box_axis_info(fitd):
    if fitd.get("kind") != "box":
        return None
    e = np.asarray(fitd["edges"])
    o = np.asarray(fitd["origin"])
    for v in e:
        if np.max(np.abs(v / np.linalg.norm(v))) < 1 - 1e-6:
            return None
    pts = np.array([o + i * e[0] + j * e[1] + k * e[2] for i in (0, 1) for j in (0, 1) for k in (0, 1)])
    mn, mx = pts.min(axis=0), pts.max(axis=0)
    ext = mx - mn
    nax = 0 if ext[0] < ext[1] else 1
    uax = 1 - nax
    return {"nax": nax, "nmin": mn[nax], "nmax": mx[nax], "umin": mn[uax], "umax": mx[uax],
            "zmin": mn[2], "zmax": mx[2], "mn": mn, "mx": mx}


def aabb_of(names, objects):
    mn = np.min([objects[n]["aabb_min"] for n in names], axis=0)
    mx = np.max([objects[n]["aabb_max"] for n in names], axis=0)
    return mn, mx


def filler_box(el, objects):
    """AABB used for orientation/tiling: frame parts if present, else all non-loose parts."""
    names = el["members"]
    frame = [n for n in names if FRAME_RE.search(n)]
    core = frame or [n for n in names if not LOOSE_RE.search(n)] or names
    return aabb_of(core, objects)


def _area(r):
    return max(0.0, r[1] - r[0]) * max(0.0, r[3] - r[2])


def _inter(a, b):
    return (max(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), min(a[3], b[3]))


def _touch(a, b, tol=0.004):
    ou = min(a[1], b[1]) - max(a[0], b[0])
    oz = min(a[3], b[3]) - max(a[2], b[2])
    return (ou > -tol and oz > 1e-3) or (oz > -tol and ou > 1e-3)


def _grow(fr, solids, bounds):
    """Grow filler rect fr to the free rectangle bounded by solids (list of rects) / bounds."""
    u0, u1, z0, z1 = fr
    B = bounds
    left = [s[1] for s in solids if s[1] <= u0 + 1e-6 and s[3] > z0 + 1e-6 and s[2] < z1 - 1e-6]
    right = [s[0] for s in solids if s[0] >= u1 - 1e-6 and s[3] > z0 + 1e-6 and s[2] < z1 - 1e-6]
    nu0 = max(left) if left else B[0]
    nu1 = min(right) if right else B[1]
    if u0 - nu0 > MAX_GROW or nu1 - u1 > MAX_GROW:
        return None
    below = [s[3] for s in solids if s[3] <= z0 + 1e-6 and s[1] > nu0 + 1e-6 and s[0] < nu1 - 1e-6]
    above = [s[2] for s in solids if s[2] >= z1 - 1e-6 and s[1] > nu0 + 1e-6 and s[0] < nu1 - 1e-6]
    nz0 = max(below) if below else B[2]
    nz1 = min(above) if above else B[3]
    if z0 - nz0 > MAX_GROW or nz1 - z1 > MAX_GROW:
        return None
    return (nu0, nu1, nz0, nz1)


def plan(elements, rows_by_source, objects):
    walls, fillers, lintels = [], [], []
    for el in elements:
        if len(el["members"]) == 1 and el["ifc_class"] in ("IfcWall", "IfcBeam"):
            info = box_axis_info(rows_by_source[el["members"][0]]["_fit"])
            if info is None:
                continue
            mat = (objects[el["members"][0]]["materials"] or [""])[0]
            if el["ifc_class"] == "IfcWall" and el["method"] == "wall":
                walls.append((el, info, mat))
            elif el.get("predefined_type") == "LINTEL":
                lintels.append((el, info))
        if el["ifc_class"] in ("IfcDoor", "IfcWindow") and el["method"] in ("door", "window"):
            mn, mx = filler_box(el, objects)
            ext = mx - mn
            fillers.append((el, mn, mx, 0 if ext[0] < ext[1] else 1))

    merges, used_fillers, used_walls = [], set(), set()
    bands = defaultdict(list)
    for el, info, mat in walls:
        bands[(info["nax"], round(info["nmin"], 3), round(info["nmax"], 3), mat)].append((el, info))
    for (nax, nmin, nmax, mat), ws in bands.items():
        uax = 1 - nax
        W = [(el, (i["umin"], i["umax"], i["zmin"], i["zmax"])) for el, i in ws]
        L = [(el, (i["umin"], i["umax"], i["zmin"], i["zmax"])) for el, i in lintels
             if i["nax"] == nax and abs(i["nmin"] - nmin) < 0.01 and abs(i["nmax"] - nmax) < 0.01]
        F = []
        for fel, mn, mx, fnax in fillers:
            if fnax == nax and fel["stable_id"] not in used_fillers and mn[nax] <= nmax + 0.05 and mx[nax] >= nmin - 0.05:
                F.append((fel, (mn[uax], mx[uax], mn[2], mx[2])))
        if not F or len(W) < 1:
            continue
        # local clusters: filler + touching pieces/lintels; clusters sharing pieces are unioned
        clusters = []
        for fel, fr in F:
            nb = {id(e): (e, r) for e, r in W if _touch(fr, r, 0.06)}
            nl = {id(e): (e, r) for e, r in L if _touch(fr, r, 0.06)}
            if not nb:
                continue
            clusters.append({"F": [(fel, fr)], "W": nb, "L": nl})
        merged = True
        while merged:
            merged = False
            for i in range(len(clusters)):
                for j in range(i + 1, len(clusters)):
                    if set(clusters[i]["W"]) & set(clusters[j]["W"]):
                        clusters[i]["F"] += clusters[j]["F"]
                        clusters[i]["W"].update(clusters[j]["W"])
                        clusters[i]["L"].update(clusters[j]["L"])
                        clusters.pop(j)
                        merged = True
                        break
                if merged:
                    break
        for c in clusters:
            # closure: every coplanar piece / lintel inside the cluster rectangle belongs to it
            while True:
                allr = [r for _, r in c["W"].values()] + [r for _, r in c["L"].values()] + [fr for _, fr in c["F"]]
                U = (min(r[0] for r in allr), max(r[1] for r in allr), min(r[2] for r in allr), max(r[3] for r in allr))
                add = 0
                for e, r in W:
                    if id(e) not in c["W"] and _area(_inter(U, r)) > 1e-4:
                        c["W"][id(e)] = (e, r); add += 1
                for e, r in L:
                    if id(e) not in c["L"] and _area(_inter(U, r)) > 1e-4:
                        c["L"][id(e)] = (e, r); add += 1
                for fel, fr in F:
                    if all(fel is not f for f, _ in c["F"]) and _area(_inter(U, fr)) > 1e-4:
                        c["F"].append((fel, fr)); add += 1
                if not add:
                    break
            wr = [r for _, r in c["W"].values()]
            lr = [r for _, r in c["L"].values()]
            if len(wr) + len(lr) < 2 and len(c["F"]) < 2:
                continue
            allr = wr + lr + [fr for _, fr in c["F"]]
            U = (min(r[0] for r in allr), max(r[1] for r in allr), min(r[2] for r in allr), max(r[3] for r in allr))
            holes, ok = [], True
            for fel, fr in c["F"]:
                h = _grow(fr, wr + lr, U)
                if h is None:
                    ok = False
                    break
                holes.append((fel, h))
            if not ok:
                continue
            solid_area = sum(_area(r) for r in wr + lr)
            resid = _area(U) - solid_area - sum(_area(h) for _, h in holes)
            ov = sum(_area(_inter(a, b)) for i, a in enumerate(wr + lr) for b in (wr + lr)[i + 1:])
            ov += sum(_area(_inter(h, s)) for _, h in holes for s in wr + lr)
            ov += sum(_area(_inter(a[1], b[1])) for i, a in enumerate(holes) for b in holes[i + 1:])
            if abs(resid) < 0.005 and ov < 1e-4:
                pieces = [e for e, _ in c["W"].values()]
                if any(p["stable_id"] in used_walls for p in pieces):
                    continue
                merges.append({"nax": nax, "nmin": nmin, "nmax": nmax, "rect": U, "material": mat,
                               "pieces": pieces, "holes": holes, "lintel_rects": lr,
                               "lintels": [e["stable_id"] for e, _ in c["L"].values()], "residual_m2": resid})
                used_walls.update(p["stable_id"] for p in pieces)
                used_fillers.update(f["stable_id"] for f, _ in holes)

    # host detection for the rest
    hosts = []
    wall_boxes = []
    for el, info, mat in walls:
        if el["stable_id"] not in used_walls:
            wall_boxes.append((el, info["mn"], info["mx"], info["nax"]))
    boxed = {w[0]["stable_id"] for w in wall_boxes} | used_walls
    for el in elements:
        if el["ifc_class"] == "IfcWall" and el["stable_id"] not in boxed and el["method"] == "wall":
            mn, mx = aabb_of(el["members"], objects)
            ext = mx - mn
            wall_boxes.append((el, mn, mx, 0 if ext[0] < ext[1] else 1))
    for fel, mn, mx, fnax in fillers:
        if fel["stable_id"] in used_fillers:
            continue
        best, bv = None, 1e-6
        for wel, wmn, wmx, wnax in wall_boxes:
            if wnax != fnax:
                continue
            ov = np.clip(np.minimum(mx, wmx) - np.maximum(mn, wmn), 0, None)
            v = float(np.prod(ov))
            if v > bv:
                best, bv = wel, v
        if best is not None:
            uax = 1 - fnax
            hosts.append({"filler": fel["stable_id"], "host": best["stable_id"], "nax": fnax,
                          "rect": (mn[uax], mx[uax], mn[2], mx[2]), "overlap_m3": bv})
    return merges, hosts
