"""Deliverable B - structural support register, from the read-only IFC extract (data/ifc_structural_extract.json).
Writes data/B_structural_support_register.csv and data/B_footing_register.csv."""
import csv, json, os

ROOT = os.path.abspath(os.path.dirname(__file__) + "/..")
d = json.load(open(ROOT + "/data/ifc_structural_extract.json"))
rows = d["rows"]
foot = [r for r in rows if r["cls"] == "IfcFooting"]
XL = [3.25 + 5.56 * i for i in range(11)]


def grid(b):
    cx, cy = (b[0] + b[3]) / 2, (b[1] + b[4]) / 2
    li = min(range(11), key=lambda i: abs(XL[i] - cx))
    gl = f"{li}" if abs(XL[li] - cx) < 0.4 else f"x{cx:.2f}"
    side = "S" if cy < 1.0 else ("N" if cy > 32.0 else f"y{cy:.2f}")
    return gl, side, cx, cy


def footing_under(b):
    cx, cy = (b[0] + b[3]) / 2, (b[1] + b[4]) / 2
    hits = [f for f in foot if f["bbox"] and f["bbox"][0] - 0.01 <= cx <= f["bbox"][3] + 0.01 and f["bbox"][1] - 0.01 <= cy <= f["bbox"][4] + 0.01
            and f["bbox"][5] <= b[2] + 0.05]
    return hits


def family(src):
    s = src or ""
    for k, v in [("COL-ROOF", "Roof truss support column"), ("COL-GALLERY-REAR", "Gallery rear column"), ("COL-GALLERY", "Gallery front column"),
                 ("TALL-PORTAL", "Entrance tall portal column (architectural frame)"), ("N-PORTAL", "North portal / loggia canopy column"),
                 ("MASONRY-PIER", "Facade masonry pier (5.56 m grid)"), ("STG-STR", "Stage deck post"), ("SPIRAL", "Spiral stair / bridge post"),
                 ("EXT05-STRUCTURAL-STEEL-COLUMN", "Office-wing steel column"), ("EXT13", "Spiral landing frame post")]:
        if k in s:
            return v
    return "Other column"


ACTION = {
    "Roof truss support column": ("Option B roof bearing; side-wall masonry wind; lateral system", "Section not verified; strength and masonry-compatible deflection fail as modelled (study Ch. 8); bearing 145 mm eccentric to column axis",
                                  "Replace section per recommended scheme; concentric bearing detail; engineered base and pad; BIM update after approval"),
    "Gallery rear column": ("Gallery raker tails / upper cross slab", "No footing; RC 'stone' placeholder material; reactions unknown", "Gallery structural design (OW-005); add pad; not to be used for roof stability unless designed"),
    "Gallery front column": ("Gallery transfer beam 450x1200", "Concept pad only; reactions unknown", "Gallery structural design; foundation design"),
    "Entrance tall portal column (architectural frame)": ("Portal frame / canopy (architectural)", "Stops at grade, no footing (O-06)", "Confirm whether structural; foundation or support from main frame"),
    "North portal / loggia canopy column": ("North loggia canopy headers", "Stops at grade, no footing (O-06)", "Design canopy; pads; tie to main frame only if designed"),
    "Facade masonry pier (5.56 m grid)": ("Masonry cladding pier at each grid", "Material is render finish; carried on wall strip (not modelled under long walls)", "Masonry design; wall strip / ground beam"),
    "Stage deck post": ("Stage RC deck", "Concept", "Stage structure design (outside roof scope)"),
    "Office-wing steel column": ("Office roof deck girders (+4.42)", "Concept spread footings exist", "Office design; independent of roof lateral system (see Ch. 10)"),
}

out = []
for r in rows:
    if r["cls"] != "IfcColumn" or not r["bbox"]:
        continue
    b = r["bbox"]
    gl, side, cx, cy = grid(b)
    fam = family(r["src"])
    hits = footing_under(b)
    sup, miss, act = ACTION.get(fam, ("-", "Concept", "Review"))
    fnd = "; ".join(f"{h['stable']} ({h['bbox'][3]-h['bbox'][0]:.2f}x{h['bbox'][4]-h['bbox'][1]:.2f}x{h['bbox'][5]-h['bbox'][2]:.2f} m, {h['status']})" for h in hits) or "NONE MODELLED"
    if fam == "Roof truss support column" and not hits:
        miss = "NO FOOTING MODELLED; " + miss
    out.append(dict(ifc_class="IfcColumn", global_id=r["gid"], stable_id=r["stable"], source_object=r["src"], family=fam,
                    grid_line=gl, side=side, x=round(cx, 3), y=round(cy, 3), z_bottom=b[2], z_top=b[5], height=round(b[5] - b[2], 3),
                    existing_section=r["profile"] or "(mesh / unspecified)", material=r["material"], supported=sup,
                    foundation=fnd, design_status=r["status"], source_status=r.get("src_status"), missing_information=miss, required_action=act,
                    evidence="IFC geometry (read-only extract, sha256 %s...)" % d["sha256"][:12]))
# other primary support elements
for r in rows:
    nm = r["src"] or ""
    if r["cls"] == "IfcWall" and nm.startswith("CORE"):
        fam, sup, miss, act = "Stair core wall", "Stairs, landings, upper slabs; candidate stability element (Ch. 10)", "Construction (RC or masonry) unverified; no footing modelled; tops at +10.80", "Confirm RC; design as shear wall if used (S3-core variant)"
    elif r["cls"] == "IfcBeam" and ("RAKER" in nm or "TRANSFER" in nm):
        fam, sup, miss, act = "Gallery raker / transfer beam", "Gallery tiers", "Solid placeholder sections; not engineered", "Gallery design (OW-005)"
    elif r["cls"] == "IfcMember" and "BRACE-ROOF" in nm:
        fam, sup, miss, act = "Roof bracing rod", "End-bay roof plane", "20 mm rods - inadequate for gable wind girder forces (study Ch. 9)", "Replace by designed end-bay girders"
    elif r["cls"] == "IfcPlate" and "BASEPLATE" in nm:
        fam, sup, miss, act = "Column base plate", "Roof columns", "450x450x30 schematic, 4 M24 schematic", "Engineer per recommended base type"
    else:
        continue
    b = r["bbox"]
    out.append(dict(ifc_class=r["cls"], global_id=r["gid"], stable_id=r["stable"], source_object=nm[:60], family=fam,
                    grid_line="-", side="-", x=round((b[0] + b[3]) / 2, 3), y=round((b[1] + b[4]) / 2, 3), z_bottom=b[2], z_top=b[5],
                    height=round(b[5] - b[2], 3), existing_section=r.get("profile") or "-", material=r.get("material", "-"), supported=sup,
                    foundation="NONE MODELLED" if fam == "Stair core wall" else "-", design_status=r.get("status"), source_status=r.get("src_status"),
                    missing_information=miss, required_action=act, evidence="IFC geometry (read-only extract)"))
with open(ROOT + "/data/B_structural_support_register.csv", "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=list(out[0]))
    w.writeheader()
    w.writerows(out)
# footing register with supported column(s)
cols = [r for r in rows if r["cls"] == "IfcColumn" and r["bbox"]]
fr = []
for f in foot:
    b = f["bbox"]
    sup = [c["stable"] for c in cols if b[0] - 0.01 <= (c["bbox"][0] + c["bbox"][3]) / 2 <= b[3] + 0.01 and b[1] - 0.01 <= (c["bbox"][1] + c["bbox"][4]) / 2 <= b[4] + 0.01]
    fr.append(dict(global_id=f["gid"], stable_id=f["stable"], source_object=f["src"], x0=b[0], x1=b[3], y0=b[1], y1=b[4], z_under=b[2], z_top=b[5],
                   size=f"{b[3]-b[0]:.2f} x {b[4]-b[1]:.2f} x {b[5]-b[2]:.2f}", supports=";".join(sup) or "none (strip / no column)", status=f["status"],
                   note="concept geometry; not an engineered foundation"))
with open(ROOT + "/data/B_footing_register.csv", "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=list(fr[0]))
    w.writeheader()
    w.writerows(fr)
roof = [o for o in out if o["family"] == "Roof truss support column"]
print("register rows", len(out), "roof columns", len(roof), "without footing:", [o["stable_id"] + "@" + o["grid_line"] + o["side"] for o in roof if o["foundation"] == "NONE MODELLED"])
for o in roof[:3] + roof[-3:]:
    print(o["stable_id"], o["grid_line"], o["side"], o["foundation"][:70])
