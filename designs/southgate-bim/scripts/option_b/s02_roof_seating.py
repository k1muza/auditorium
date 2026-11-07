"""Stage 1 audit (read-only): measure the purlin / purlin-cleat seating plane on every truss line.
The Option B top-chord top-of-steel is set to this plane so the (out-of-scope) roof envelope is unchanged.
Usage: .venv/Scripts/python -I scripts/option_b/s02_roof_seating.py bim/southgate.ifc work/option_b/s02_roof_seating.json"""
import sys, json, math, re, multiprocessing
import numpy as np, ifcopenshell, ifcopenshell.geom, ifcopenshell.util.element as ue
f = ifcopenshell.open(sys.argv[1])
T, C = math.tan(math.radians(15)), math.cos(math.radians(15))
LINES = [3.25 + 5.56 * i for i in range(11)]
want = []
for e in f.by_type("IfcMember") + f.by_type("IfcPlate"):
    src = (ue.get_pset(e, "SOUTHGATE_Provenance") or {}).get("SourceObjects") or ""
    if re.match(r"^(PURLIN-ROW-|ROOF-RIDGE-ADJACENT-PURLIN|PURLIN-CLEAT-)", src):
        want.append((e, src))
st = ifcopenshell.geom.settings(); st.set("use-world-coords", True)
it = ifcopenshell.geom.iterator(st, f, max(1, multiprocessing.cpu_count() - 1), include=[e for e, _ in want])
geo = {}
if it.initialize():
    while True:
        sh = it.get(); geo[sh.guid] = np.asarray(sh.geometry.verts).reshape(-1, 3)
        if not it.next(): break
res = {"purlin": {}, "cleat": {}}
for e, src in want:
    v = geo.get(e.GlobalId)
    if v is None: continue
    s = v[:, 1] - 0.30
    sm = np.minimum(s, 32.4 - s)
    perp = (v[:, 2] - (12.38 + T * sm)) * C          # normal distance above the 12.38 reference plane
    kind = "cleat" if src.startswith("PURLIN-CLEAT") else "purlin"
    for xl in LINES:
        m = np.abs(v[:, 0] - xl) < 0.12               # vertices within the top-chord width of this truss line
        if m.any():
            res[kind].setdefault(f"{xl:.2f}", []).append(float(perp[m].min()))
out = {k: {x: {"n": len(vs), "min_perp_m": round(min(vs), 5), "max_perp_m": round(max(vs), 5)} for x, vs in d.items()} for k, d in res.items()}
allp = [v for d in res["purlin"].values() for v in d]; allc = [v for d in res["cleat"].values() for v in d]
out["summary"] = {"purlin_underside_min_perp_m": round(min(allp), 5), "purlin_underside_max_perp_m": round(max(allp), 5),
                  "cleat_underside_min_perp_m": round(min(allc), 5), "cleat_underside_max_perp_m": round(max(allc), 5),
                  "reference": "perp = normal distance from the plane z = 12.380 + tan15 * min(s, 32.4 - s), s = y - 0.30"}
json.dump(out, open(sys.argv[2], "w"), indent=1)
print(json.dumps(out["summary"], indent=1))
