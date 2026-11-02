"""True-scale drawing sheets generated from any design's Blender manifest (shared by every design and the comparisons).

Geometry comes only from the manifest (mesh vertices x object matrices read back from the .blend), so a drawing can
never show something the model does not contain. Every sheet carries the design ID, model revision, scale, status
and the manifest SHA-256 it was drawn from.

  plan(M, out, ...)        upward-facing faces below a cut height, by discipline, with grid, exits, spaces, scale bar
  section(M, out, ...)     true mesh cut on a vertical plane (+ structure projected from the next bay behind)
  structure(M, out, ...)   columns, footings, truss lines, purlins and bracing on the grid
Paper: A3 landscape (420 x 297 mm). Default scale 1:400 so designs compare at one scale.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.collections import LineCollection, PolyCollection  # noqa: E402

MM = 1 / 25.4
A3 = (420, 297)
INK, GREY, LIGHT = "#1E1E1C", "#8A8A86", "#D5D2CA"
STYLE = {   # collection prefix -> (face colour, edge colour, z-order)
    "10_ENV": ("#2B2B29", "#2B2B29", 6), "20_ARC_Walls": ("#3A3A37", "#3A3A37", 6), "20_ARC_Floors": ("#F3F1EC", "#B9B6AE", 1),
    "20_ARC_Circulation": ("#E8C88A", "#8C5E36", 3), "20_ARC_Furniture": ("#8C5E36", "#8C5E36", 4),
    "30_STR_Columns": ("#8A3324", "#8A3324", 7), "30_STR_Foundations": ("none", "#B07060", 0),
    "40_SEAT_Congregation": ("#3E6FA8", "none", 5), "40_SEAT_Choir": ("#7A4E9A", "none", 5),
    "40_SEAT_Accessible": ("#2E8B57", "#2E8B57", 5), "40_SEAT_Companion": ("#2E8B57", "none", 5),
}


def load(manifest_path):
    raw = Path(manifest_path).read_bytes()
    M = json.loads(raw)
    M["_sha"] = hashlib.sha256(raw).hexdigest()
    return M


def world(M, ob):
    m = ob["matrix"]
    out = []
    for x, y, z in M["meshes"][ob["mesh"]]["verts"]:
        out.append((m[0][0] * x + m[0][1] * y + m[0][2] * z + m[0][3], m[1][0] * x + m[1][1] * y + m[1][2] * z + m[1][3],
                    m[2][0] * x + m[2][1] * y + m[2][2] * z + m[2][3]))
    return out


def normal(pts):
    nx = ny = nz = 0.0
    for i in range(len(pts)):
        x0, y0, z0 = pts[i]
        x1, y1, z1 = pts[(i + 1) % len(pts)]
        nx += (y0 - y1) * (z0 + z1)
        ny += (z0 - z1) * (x0 + x1)
        nz += (x0 - x1) * (y0 + y1)
    m = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
    return nx / m, ny / m, nz / m


def style(ob):
    for k, v in STYLE.items():
        if ob["collection"].startswith(k):
            return v
    return None


def sheet(M, scale, extent, title, subtitle, sheet_no, kind):
    """A3 landscape figure with a drawing axes at true scale and a right-hand title block."""
    fig = plt.figure(figsize=(A3[0] * MM, A3[1] * MM), dpi=150)
    fig.patch.set_facecolor("white")
    border = fig.add_axes([8 / A3[0], 8 / A3[1], 1 - 16 / A3[0], 1 - 16 / A3[1]])
    border.set_xticks([]), border.set_yticks([])
    for sp in border.spines.values():
        sp.set_linewidth(0.75)
    x0, y0, x1, y1 = extent
    w_mm, h_mm = (x1 - x0) * 1000 / scale, (y1 - y0) * 1000 / scale
    avail_w, avail_h = A3[0] - 16 - 66, A3[1] - 16 - 10
    ox, oy = 8 + 4 + max(0, (avail_w - w_mm) / 2), 8 + 5 + max(0, (avail_h - h_mm) / 2)
    ax = fig.add_axes([ox / A3[0], oy / A3[1], w_mm / A3[0], h_mm / A3[1]])
    ax.set_xlim(x0, x1), ax.set_ylim(y0, y1), ax.set_aspect("equal"), ax.axis("off")
    tb = fig.add_axes([(A3[0] - 8 - 62) / A3[0], 8 / A3[1], 62 / A3[0], 1 - 16 / A3[1]])
    tb.set_xlim(0, 62), tb.set_ylim(0, A3[1] - 16), tb.axis("off")
    tb.axvline(0, color=INK, lw=0.75)
    proj = M["project"]
    rows = [("PROJECT", proj["name"]), ("DESIGN", M.get("design_id", proj.get("design_id", "A-end-stage"))),
            ("MODEL REVISION", M["revision"]), ("DRAWING", title), ("", subtitle), ("SCALE", f"1:{scale} at A3"),
            ("SHEET", sheet_no), ("SOURCE", f"blender_manifest.json\nsha256 {M['_sha'][:16]}"),
            ("UNITS", "metres; levels in m above L00"), ("STATUS", proj["status_label"])]
    y = A3[1] - 16 - 8
    for k, v in rows:
        if k:
            tb.text(3, y, k, fontsize=4.2, family="monospace", color=GREY, va="top")
            y -= 3.6
        import textwrap
        for line in textwrap.wrap(str(v), 34) or [""]:
            tb.text(3, y, line, fontsize=5.4 if k != "STATUS" else 5.0, color="#8A3324" if k == "STATUS" else INK, va="top",
                    family="monospace" if k in ("MODEL REVISION", "SOURCE", "SHEET") else None)
            y -= 3.4
        y -= 2.6
    tb.text(3, 6, "Concept coordination drawing generated from the\nBlender model. Not for construction. Dimensions\n"
                  "unverified pending professional review.", fontsize=3.8, color=GREY, va="bottom")
    return fig, ax


def scale_bar(ax, scale, x, y, length=20):
    for i in range(0, length, 5):
        ax.add_patch(plt.Rectangle((x + i, y), 5, 0.6, fc=INK if (i // 5) % 2 == 0 else "white", ec=INK, lw=0.3, zorder=20))
    for i in range(0, length + 1, 10):
        ax.text(x + i, y - 0.8, f"{i}", fontsize=4, ha="center", va="top", zorder=20)
    ax.text(x + length + 1.5, y + 0.3, f"m   (1:{scale})", fontsize=4, va="center", zorder=20)


def grid(ax, M, extent, axes="xy", label_off=3.0):
    gx, gy = M["grid"]["x_lines"], M["grid"]["y_lines"]
    x0, y0, x1, y1 = extent
    segs = []
    if "x" in axes:
        for k, v in gx.items():
            segs.append([(v, y0 + label_off + 1.2), (v, y1 - label_off - 1.2)])
            for yy in (y0 + label_off, y1 - label_off):
                ax.add_patch(plt.Circle((v, yy), 1.1, fc="white", ec=INK, lw=0.4, zorder=21))
                ax.text(v, yy, k, fontsize=4.2, ha="center", va="center", zorder=22)
    if "y" in axes:
        for k, v in gy.items():
            segs.append([(x0 + label_off + 1.2, v), (x1 - label_off - 1.2, v)])
            for xx in (x0 + label_off, x1 - label_off):
                ax.add_patch(plt.Circle((xx, v), 1.1, fc="white", ec=INK, lw=0.4, zorder=21))
                ax.text(xx, v, k, fontsize=4.2, ha="center", va="center", zorder=22)
    ax.add_collection(LineCollection(segs, colors=GREY, linewidths=0.25, linestyles=(0, (8, 2, 1, 2)), zorder=0.5))


def dim_chain(ax, values, at, axis="x", label_fmt="{:.2f}", off=0):
    """Dimension chain along x (at y=at) or y (at x=at) through the sorted values."""
    v = sorted(values)
    segs = []
    for a, b in zip(v, v[1:]):
        if axis == "x":
            segs += [[(a, at), (b, at)]]
            ax.text((a + b) / 2, at + 0.5, label_fmt.format(b - a), fontsize=3.6, ha="center", va="bottom", zorder=20)
        else:
            segs += [[(at, a), (at, b)]]
            ax.text(at - 0.5, (a + b) / 2, label_fmt.format(b - a), fontsize=3.6, ha="right", va="center", rotation=90, zorder=20)
    for x in v:
        segs += [[(x - 0.4, at - 0.4), (x + 0.4, at + 0.4)]] if axis == "x" else [[(at - 0.4, x - 0.4), (at + 0.4, x + 0.4)]]
    ax.add_collection(LineCollection(segs, colors=INK, linewidths=0.3, zorder=20))


def plan(M, out, title="Ground floor plan", sheet_no="P-100", scale=400, extent=None, z_cut=6.0, spaces=True, exits=True,
         subtitle="Plan at L00, cut below the roof structure"):
    objs = [o for o in M["objects"]]
    if extent is None:
        xs, ys = [], []
        for o in objs:
            if o["collection"].startswith(("10_ENV", "20_ARC_Floors")):
                for x, y, z in world(M, o):
                    xs.append(x), ys.append(y)
        extent = (min(xs) - 9, min(ys) - 9, max(xs) + 9, max(ys) + 9)
    fig, ax = sheet(M, scale, extent, title, subtitle, sheet_no, "plan")
    layers = {}
    for o in objs:
        st = style(o)
        if st is None or o["name"].startswith(("ENV-ROOF", "ENV-CANOPY", "ENV-CLAD", "ENV-FLASHING")):
            continue
        V = world(M, o)
        if min(v[2] for v in V) > z_cut:
            continue
        for f in M["meshes"][o["mesh"]]["faces"]:
            pts = [V[i] for i in f]
            if normal(pts)[2] > 0.5:
                layers.setdefault(st, []).append(([(p[0], p[1]) for p in pts], max(p[2] for p in pts)))
    for st, polys in sorted(layers.items(), key=lambda kv: kv[0][2]):
        polys.sort(key=lambda p: p[1])
        fc, ec, z = st
        ax.add_collection(PolyCollection([p for p, _ in polys], facecolors=fc, edgecolors=ec, linewidths=0.15, zorder=z))
    # canopy / roof outlines dashed
    for o in objs:
        if o["name"].startswith(("ENV-CANOPY", "ENV-ROOF-MAIN", "ENV-ROOF")):
            V = world(M, o)
            xs, ys = [v[0] for v in V], [v[1] for v in V]
            ax.add_patch(plt.Rectangle((min(xs), min(ys)), max(xs) - min(xs), max(ys) - min(ys), fc="none", ec=GREY, lw=0.3,
                                       ls=(0, (4, 3)), zorder=0.8))
    grid(ax, M, extent)
    if spaces:
        for o in objs:
            if o["ifc_class"] == "IfcSpace":
                V = world(M, o)
                cx, cy = sum(v[0] for v in V) / len(V), sum(v[1] for v in V) / len(V)
                p = o["props"]
                if p.get("GrossFloorArea", 0) < 12:
                    continue
                ax.text(cx, cy, f"{p.get('LongName', o['name'])}\n{p.get('GrossFloorArea', 0):,.0f} m²", fontsize=3.4, ha="center",
                        va="center", color="#5B636B", zorder=23,
                        bbox=dict(fc="white", ec="none", alpha=0.7, pad=0.6))
    if exits:
        for o in objs:
            if o["ifc_class"] == "IfcDoor" and o["props"].get("FireExit"):
                V = world(M, o)
                cx, cy = sum(v[0] for v in V) / len(V), sum(v[1] for v in V) / len(V)
                ax.plot(cx, cy, marker="^", ms=3.2, color="#C0392B", zorder=24)
                ax.text(cx, cy + 1.2, o["name"].replace("DR-", ""), fontsize=3.0, color="#C0392B", ha="center", zorder=24)
    scale_bar(ax, scale, extent[0] + 4, extent[1] + 1.5)
    gx = M["grid"]["x_lines"]
    dim_chain(ax, list(gx.values()), extent[3] - 6.0, "x", "{:.2f}")
    dim_chain(ax, list(M["grid"]["y_lines"].values()), extent[0] + 6.0, "y", "{:.2f}")
    ax.text(extent[0] + 4, extent[3] - 1.2, "N (project, assumed)  ↑", fontsize=4, va="top")
    fig.savefig(out, dpi=150, facecolor="white")
    plt.close(fig)
    return extent


def cut_segments(V, faces, axis, c):
    """Intersection segments of mesh faces with the plane coord[axis] = c, in the plane's (u, z) coordinates."""
    i = 0 if axis == "x" else 1
    u = 1 - i
    segs = []
    for f in faces:
        pts = [V[k] for k in f]
        cross = []
        for a, b in zip(pts, pts[1:] + pts[:1]):
            da, db = a[i] - c, b[i] - c
            if (da < 0) != (db < 0) and da != db:
                t = da / (da - db)
                cross.append((a[u] + t * (b[u] - a[u]), a[2] + t * (b[2] - a[2])))
        if len(cross) >= 2:
            segs.append(cross[:2])
    return segs


def section(M, out, axis="x", c=40.0, title="Section", sheet_no="S-200", scale=400, beyond=8.0, extent=None, subtitle=None):
    """Vertical section on the plane coord[axis] = c, looking towards +axis; structure within `beyond` m behind is projected."""
    i = 0 if axis == "x" else 1
    u = 1 - i
    cut = {}
    proj = []
    umin, umax, zmax = 1e9, -1e9, 0.0
    for o in M["objects"]:
        if o["ifc_class"] in ("IfcSpace", "IfcSpatialZone", "IfcOpeningElement"):
            continue
        V = world(M, o)
        lo, hi = min(v[i] for v in V), max(v[i] for v in V)
        faces = M["meshes"][o["mesh"]]["faces"]
        if lo <= c <= hi:
            segs = cut_segments(V, faces, axis, c)
            if segs:
                key = o["collection"][:6]
                cut.setdefault(key, []).extend(segs)
                for s_ in segs:
                    for p in s_:
                        umin, umax, zmax = min(umin, p[0]), max(umax, p[0]), max(zmax, p[1])
        elif c < lo <= c + beyond and o["collection"].startswith(("30_STR_Roof", "30_STR_Col", "40_SEAT", "50_SRV_AV")):
            for f in faces:
                proj.append([(V[k][u], V[k][2]) for k in f])
    if extent is None:
        extent = (umin - 8, -6, umax + 8, zmax + 6)
    fig, ax = sheet(M, scale, extent, title, subtitle or f"Cut on {axis} = {c:.2f} m, looking towards +{axis}", sheet_no, "section")
    ax.add_collection(PolyCollection(proj, facecolors="none", edgecolors=LIGHT, linewidths=0.2, zorder=1))
    colours = {"10_ENV": INK, "20_ARC": INK, "30_STR": "#8A3324", "40_SEA": "#3E6FA8", "50_SRV": "#5B636B"}
    for key, segs in cut.items():
        ax.add_collection(LineCollection(segs, colors=colours.get(key, GREY), linewidths=0.55 if key in ("10_ENV", "20_ARC") else 0.35,
                                         zorder=5))
    ax.axhline(0, color=GREY, lw=0.3, ls=(0, (6, 2)))
    for lv in M["levels"]:
        ax.plot([extent[0] + 2, extent[0] + 6], [lv["elevation"]] * 2, color=INK, lw=0.4)
        ax.text(extent[0] + 2, lv["elevation"] + 0.3, f"{lv['id']} {lv['elevation']:+.3f}", fontsize=3.6, va="bottom")
    g = M["grid"]["y_lines" if axis == "x" else "x_lines"]
    for k, v in g.items():
        if extent[0] < v < extent[2]:
            ax.plot([v, v], [extent[1] + 3, extent[3] - 3], color=GREY, lw=0.25, ls=(0, (8, 2, 1, 2)), zorder=0.5)
            ax.add_patch(plt.Circle((v, extent[1] + 2), 1.1, fc="white", ec=INK, lw=0.4, zorder=21))
            ax.text(v, extent[1] + 2, k, fontsize=4.2, ha="center", va="center", zorder=22)
    scale_bar(ax, scale, extent[2] - 30, extent[1] + 1.0)
    fig.savefig(out, dpi=150, facecolor="white")
    plt.close(fig)


def structure(M, out, title="Structural grid and roof framing", sheet_no="ST-100", scale=400, extent=None):
    fig, ax = sheet(M, scale, extent or plan_extent(M), title, "Columns, pad footings (dashed), trusses, purlins and bracing",
                    sheet_no, "structure")
    extent = extent or plan_extent(M)
    lines = {"truss": [], "purlin": [], "brace": [], "beam": []}
    for o in M["objects"]:
        V = world(M, o)
        n = o["name"]
        if o["ifc_class"] == "IfcColumn":
            xs, ys = [v[0] for v in V], [v[1] for v in V]
            ax.add_patch(plt.Rectangle((min(xs), min(ys)), max(xs) - min(xs), max(ys) - min(ys), fc="#8A3324", ec="none", zorder=6))
        elif o["ifc_class"] == "IfcFooting":
            xs, ys = [v[0] for v in V], [v[1] for v in V]
            ax.add_patch(plt.Rectangle((min(xs), min(ys)), max(xs) - min(xs), max(ys) - min(ys), fc="none", ec="#B07060", lw=0.3,
                                       ls=(0, (3, 2)), zorder=2))
        elif o.get("strut"):
            (a, b, _) = o["strut"]
            key = "truss" if n.startswith("STR-TRUSS") else "purlin" if n.startswith("STR-PURLIN") else "brace" if "BRACE" in n else "beam"
            lines[key].append([(a[0], a[1]), (b[0], b[1])])
        elif o["collection"].startswith(("10_ENV", "20_ARC_Walls")) and o["ifc_class"] == "IfcWall":
            for f in M["meshes"][o["mesh"]]["faces"]:
                pts = [V[i] for i in f]
                if normal(pts)[2] > 0.5:
                    ax.add_patch(plt.Polygon([(p[0], p[1]) for p in pts], fc=LIGHT, ec="none", zorder=1))
    sty = {"truss": ("#8A3324", 0.9), "purlin": ("#B9B6AE", 0.25), "brace": ("#C98A2B", 0.45), "beam": ("#5B636B", 0.6)}
    for k, segs in lines.items():
        ax.add_collection(LineCollection(segs, colors=sty[k][0], linewidths=sty[k][1], zorder=4 if k != "purlin" else 3))
    grid(ax, M, extent)
    dim_chain(ax, list(M["grid"]["x_lines"].values()), extent[3] - 6.0, "x")
    dim_chain(ax, list(M["grid"]["y_lines"].values()), extent[0] + 6.0, "y")
    scale_bar(ax, scale, extent[0] + 4, extent[1] + 1.5)
    fig.savefig(out, dpi=150, facecolor="white")
    plt.close(fig)


def plan_extent(M):
    xs, ys = [], []
    for o in M["objects"]:
        if o["collection"].startswith(("10_ENV", "20_ARC_Floors")):
            for x, y, z in world(M, o):
                xs.append(x), ys.append(y)
    return (min(xs) - 9, min(ys) - 9, max(xs) + 9, max(ys) + 9)
