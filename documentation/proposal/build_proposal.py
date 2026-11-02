"""Generate the engineering design proposal for one design, or the comparative feasibility report, from model data only.

  .venv/Scripts/python documentation/proposal/build_proposal.py --design A        -> designs/A-end-stage/proposal/out/
  .venv/Scripts/python documentation/proposal/build_proposal.py --design B        -> designs/B-long-side-stage/proposal/out/
  .venv/Scripts/python documentation/proposal/build_proposal.py --compare         -> comparisons/out/report/

One publication design system (documentation/proposal/template: tokens, self-hosted fonts, A4 report + A3 sheets,
status language) for every document. Every page states the design ID, model revision and measurement provenance.
Contamination guard: a design proposal may only embed files from its own design folder (or sheets generated here from
its own manifest), and the build fails if the other design's ID or revision string appears anywhere in the output.
Prints to PDF with headless Chrome/Edge when available.
"""
import argparse
import csv
import html
import json
import re
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from shared.drawings import sheets as S  # noqa: E402
from shared.env import design_meta  # noqa: E402

TPL = REPO / "documentation" / "proposal" / "template"
DESIGNS = {"A": "A-end-stage", "B": "B-long-side-stage"}
CSS = """
@font-face{font-family:Newsreader;src:url(fonts/Newsreader-300.woff2)}@font-face{font-family:Archivo;src:url(fonts/Archivo-400.woff2)}
@font-face{font-family:Plex;src:url(fonts/IBMPlexMono-400.woff2)}@font-face{font-family:Plex;font-weight:500;src:url(fonts/IBMPlexMono-500.woff2)}
@page{size:A4 portrait;margin:0}@page a3{size:A3 landscape;margin:0}
body{margin:0;background:#cfccc4;font-family:Archivo,Arial,sans-serif;color:#1E1E1C;font-size:8.6pt;line-height:1.55;-webkit-print-color-adjust:exact;print-color-adjust:exact}
section{width:210mm;height:297mm;box-sizing:border-box;padding:24mm 15mm 22mm 25mm;background:#F5F2EC;margin:8mm auto;position:relative;overflow:hidden;page-break-after:always}
section.a3{width:420mm;height:297mm;page:a3;padding:8mm;background:#fff}
section.cover{background:#1F2022;color:#F5F2EC}
h1{font-family:Newsreader,Georgia,serif;font-weight:300;font-size:27pt;line-height:1.04;margin:0 0 6mm}
h2{font-family:Newsreader,Georgia,serif;font-weight:300;font-size:15pt;margin:6mm 0 3mm;border-top:.75pt solid #1E1E1C;padding-top:2mm}
.lead{font-family:Newsreader,Georgia,serif;font-size:13pt;line-height:1.42}
.lbl{font-family:Plex,monospace;font-size:6.2pt;letter-spacing:.07em;text-transform:uppercase;color:#5B636B}
table{border-collapse:collapse;width:100%;font-size:7.2pt;margin:2mm 0}th{text-align:left;border-bottom:.75pt solid #1E1E1C;font-weight:500;padding:1mm}
td{border-bottom:.35pt solid #D5D2CA;padding:.95mm 1mm;vertical-align:top}tr:nth-child(even) td{background:#EEEBE4}td.n{text-align:right;font-family:Plex,monospace}
.hdr{position:absolute;top:9mm;left:25mm;right:15mm;display:flex;justify-content:space-between;font-family:Plex,monospace;font-size:6pt;color:#5B636B}
.ftr{position:absolute;bottom:9mm;left:25mm;right:15mm;display:flex;justify-content:space-between;font-family:Plex,monospace;font-size:6pt;color:#5B636B}
.status{color:#8A3324}.fig{width:100%;border:.35pt solid #D5D2CA;background:#fff}figure{margin:2mm 0}figcaption{font-size:6.8pt;color:#5B636B}
section.a3 img{width:100%;height:100%;object-fit:contain}.src{font-family:Plex,monospace;font-size:5.6pt;color:#5B636B}
.sev-CRITICAL{color:#8A3324;font-weight:500}.sev-MAJOR{color:#8C5E36}
@media print{body{background:none}section{margin:0}}
"""


def esc(v):
    return html.escape(str(v))


class Doc:
    def __init__(self, design_id, revision, provenance, title):
        self.pages, self.n = [], 0
        self.design_id, self.revision, self.prov, self.title = design_id, revision, provenance, title

    def page(self, body, a3=False, cover=False):
        self.n += 1
        if a3:
            self.pages.append(f'<section class="a3">{body}</section>')
            return
        cls = "cover" if cover else ""
        hdr = "" if cover else (f'<div class="hdr"><span>{esc(self.title)}</span><span>{esc(self.design_id)} · {esc(self.revision)}</span></div>'
                                f'<div class="ftr"><span class="status">CONCEPT — UNVERIFIED · NOT FOR CONSTRUCTION</span>'
                                f'<span>{esc(self.prov)}</span><span>{self.n:02d}</span></div>')
        self.pages.append(f'<section class="{cls}">{hdr}{body}</section>')

    def html(self):
        return (f"<!doctype html><html><head><meta charset='utf-8'><title>{esc(self.title)}</title><style>{CSS}</style></head><body>"
                + "".join(self.pages) + "</body></html>")


def tbl(rows, head=None, num=()):
    h = "<tr>" + "".join(f"<th>{esc(c)}</th>" for c in head) + "</tr>" if head else ""
    b = "".join("<tr>" + "".join(f'<td class="{"n" if i in num else ""}">{esc(c)}</td>' for i, c in enumerate(r)) + "</tr>" for r in rows)
    return f"<table>{h}{b}</table>"


def fig(src, cap):
    return f'<figure><img class="fig" src="{src}"><figcaption>{esc(cap)}</figcaption></figure>'


def print_pdf(html_path):
    for exe in (r"C:\Program Files\Google\Chrome\Application\chrome.exe", r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                shutil.which("chromium") or "", shutil.which("google-chrome") or ""):
        if exe and Path(exe).exists():
            pdf = html_path.with_suffix(".pdf")
            subprocess.run([exe, "--headless=new", "--disable-gpu", "--no-pdf-header-footer", f"--print-to-pdf={pdf}",
                            "--virtual-time-budget=20000", html_path.resolve().as_uri()], capture_output=True, timeout=300)
            return pdf if pdf.exists() else None
    return None


def stage_assets(out):
    out.mkdir(parents=True, exist_ok=True)
    shutil.copytree(TPL / "fonts", out / "fonts", dirs_exist_ok=True)


def guard(out_dir, own, other_ids):
    bad = []
    for p in out_dir.rglob("*.html"):
        t = p.read_text(encoding="utf-8")
        for o in other_ids:
            if o in t:
                bad.append((p.name, o))
    if bad:
        raise SystemExit(f"CONTAMINATION GUARD: {own} document mentions {bad}")


# ---------------------------------------------------------------------------------------------------- design proposal
def design_proposal(key):
    D, meta = design_meta(key)
    other = "B" if key == "A" else "A"
    Do, ometa = design_meta(other)
    M = S.load(D / "model" / "blender_manifest.json")
    M["design_id"] = meta["design_id"]
    rev = M["revision"]
    out = D / "proposal" / "out"
    if out.exists():
        shutil.rmtree(out)
    stage_assets(out)
    (out / "img").mkdir()
    # drawings generated here from THIS design's manifest (same sheet system and scale for both designs)
    xs = M["grid"]["x_lines"]
    xmid = (min(xs.values()) + max(xs.values())) / 2
    sheets = [("plan.png", "Ground floor plan", lambda p: S.plan(M, p, "Ground floor plan", f"{key}-P100")),
              ("seating.png", "Seating, aisles and exits", lambda p: S.plan(M, p, "Seating, aisles and exits", f"{key}-P110", spaces=False)),
              ("structure.png", "Structural grid and roof framing", lambda p: S.structure(M, p, "Structural grid and roof framing", f"{key}-S100"))]
    if key == "A":
        sheets.append(("section.png", "Long section through the hall", lambda p: S.section(M, p, "x", 31.0, "Long section", "A-S300")))
    else:
        sheets.append(("section.png", "Section across the hall depth", lambda p: S.section(M, p, "x", xmid + 4.0, "Section A-A", "B-S300")))
    for fn, _, f in sheets:
        f(out / "img" / fn)
    rdir = sorted((D / "renders").glob(f"{rev}*"))
    rdir = rdir[0] if rdir else max((p for p in (D / "renders").iterdir() if p.is_dir()), key=lambda p: p.name)
    render_note = "" if rdir.name.startswith(rev) else f" (renders from {rdir.name}; no renders were archived for {rev})"
    for r in sorted(rdir.glob("*.png")):
        shutil.copy2(r, out / "img" / f"render_{r.name}")
    G = json.loads((D / "reports" / "geometry_checks.json").read_text(encoding="utf-8"))
    BV = json.loads((D / "reports" / "blend_verification.json").read_text(encoding="utf-8"))
    IV = json.loads((D / "reports" / "ifc_validation.json").read_text(encoding="utf-8"))
    cmp = json.loads((REPO / "comparisons" / "out" / "comparison.json").read_text(encoding="utf-8"))[key]
    assert cmp["revision"] == rev, f"comparison.json measured {cmp['revision']}, model is {rev} - rerun comparisons/compare.py"
    prov = f"model {rev} · manifest sha256 {M['_sha'][:12]}"
    doc = Doc(meta["design_id"], rev, prov, f"Engineering design proposal — Option {key}")
    cover = next((f"img/{p.name}" for p in sorted((out / "img").glob("render_01*"))), "img/plan.png")
    doc.page(f'<div class="lbl" style="color:#B9B6AE">Preliminary architectural &amp; structural engineering design proposal</div>'
             f'<h1 style="margin-top:20mm;color:#F5F2EC">Proposed 3,000-seat church auditorium<br>Option {key} — {esc(meta["title"].split(" - ", 1)[-1])}</h1>'
             f'<img src="{cover}" style="width:100%;margin-top:10mm"><p class="lbl" style="color:#B9B6AE;margin-top:8mm">Design ID {esc(meta["design_id"])}'
             f' · model revision {esc(rev)} · Zimbabwe (site not identified) · {date.today().isoformat()}</p>'
             f'<p class="status" style="color:#E0A090">CONCEPT — UNVERIFIED · NOT FOR CONSTRUCTION. Reviewer scores are QA metrics, not certification.</p>',
             cover=True)
    rec = json.loads((D / "reports" / "model_revision.json").read_text(encoding="utf-8"))
    rows = [("Design ID", meta["design_id"]), ("Model revision", rev), ("Manifest SHA-256", M["_sha"]), ("Blender", M["blender_version"]),
            ("Units", "metres"), ("Status", M["project"]["status_label"]), ("Build", meta.get("entrypoint", "")),
            ("Measurement provenance", "Every figure, table and drawing in this document is generated from this design's Blender manifest, "
             "its verified reports (geometry_checks, blend_verification, ifc_validation) and comparisons/compare.py run on the same manifest.")]
    doc.page("<h1>Document control &amp; provenance</h1>" + tbl(rows) + "<h2>Source files hashed in the revision record</h2>"
             + tbl([(k, v[:16]) for k, v in rec["source_hashes"].items()], ["Source", "SHA-256 (16)"]))
    # concept + scope (figures from the measured comparison of THIS model)
    cmp = json.loads((REPO / "comparisons" / "out" / "comparison.json").read_text(encoding="utf-8"))[key]
    if key == "A":
        brief = (REPO / "DESIGN_BRIEF.md").read_text(encoding="utf-8")
        dec = brief.split("## Client design decisions", 1)[1] if "## Client design decisions" in brief else ""
        items = [esc(re.sub(r"\*\*", "", ln.strip("- ").strip())) for ln in dec.splitlines() if ln.startswith("- ")]
        scope = "<h2>Approved scope changes (client decisions, recorded in DESIGN_BRIEF.md)</h2><ul>" + "".join(f"<li>{i}</li>" for i in items) + "</ul>"
        concept = (f"The platform stands at one end of a 50 m wide hall; {cmp['rows']} straight rows rise to an upper foyer at the rear. "
                   f"{cmp['truss_count']} steel trusses of {cmp['truss_span_m']} m span the hall width.")
    else:
        P = json.loads((D / "config" / "params.json").read_text(encoding="utf-8"))
        props = [(sec, k.strip("_"), v) for sec, d in P.items() if isinstance(d, dict) for k, v in d.items() if k.startswith("_") and isinstance(v, str)]
        scope = ("<h2>Carried from the common brief / client preferences</h2><ul>" +
                 "".join(f"<li><b>{esc(s)}</b>: {esc(v)}</li>" for s, k, v in props if "carried" in k.lower() or "source" in k.lower()) +
                 "</ul><h2>New architectural proposals (not yet approved)</h2><ul>" +
                 "".join(f"<li><b>{esc(s)}</b>: {esc(v)}</li>" for s, k, v in props if "proposal" in k.lower()) + "</ul>")
        concept = (f"The platform stands on the middle of the long north wall. {cmp['seats']:,} seats sit in a wide, shallow fan of {cmp['rows']} "
                   "concentric rows facing the platform focus; one mono-pitch roof covers foyer and hall.")
    doc.page(f"<h1>Concept and scope</h1><p class='lead'>{esc(concept)}</p>" + scope)
    m = cmp
    key_rows = [("Congregation seats (verified: layout, .blend, IFC, CSV)", m["seats"]), ("Rows", m["rows"]),
                ("Eye-to-pulpit distance mean / median / max (m)", f"{m['pulpit_distance_m']['mean']} / {m['pulpit_distance_m']['median']} / {m['pulpit_distance_m']['max']}"),
                ("Seats within 20 m / 30 m of the pulpit", f"{m['pulpit_distance_m']['share_within_20m']:.0%} / {m['pulpit_distance_m']['share_within_30m']:.0%}"),
                ("Head turn to pulpit mean / max (deg)", f"{m['head_turn_to_pulpit_deg']['mean']} / {m['head_turn_to_pulpit_deg']['max']}"),
                ("Max bearing from the pulpit (deg)", m["bearing_from_pulpit_deg"]["max"]), ("Min C-value n1 / n2 (from chair objects)",
                f"{m['c_value_min_from_chair_objects']['n1']} / {m['c_value_min_from_chair_objects']['n2']}"),
                ("Footprint (m)", " x ".join(map(str, m["footprint_m"]))), ("Hall floor area / per seat (m2)", f"{m['hall_floor_area_m2']} / {m['hall_area_per_seat_m2']}"),
                ("Hall air volume / per seat (m3)", f"{m['hall_air_volume_m3']:.0f} / {m['hall_volume_per_seat_m3']}"),
                ("Roof area (sloped, m2) / top (m)", f"{m['roof_area_m2']} / {m['roof_top_m']}"), ("Trusses / span (m)", f"{m['truss_count']} / {m['truss_span_m']}"),
                ("Columns / pad footing concrete (m3)", f"{m['structure']['columns']} / {m['structure']['footing_concrete_m3']}"),
                ("Hall exits / door width (m)", f"{m['exits']['hall_exits']} / {m['exits']['hall_exit_door_width_m']}"),
                ("Wheelchair spaces / lifts", f"{m['accessibility']['wheelchair_spaces']} / {m['accessibility']['lifts']}"),
                ("Choir chairs / platform area (m2)", f"{m['choir_chairs']} / {m['platform_area_m2']}")]
    doc.page("<h1>Project at a glance</h1><p class='src'>Measured by comparisons/compare.py from this design's manifest (identical code for both options).</p>"
             + tbl(key_rows, ["Measure", "Value"], num=(1,)) + "<h2>Verification</h2>"
             + tbl([("Layout engine checks", json.dumps({k: sum(c['result'] == k for c in G['checks']) for k in ('PASS', 'FAIL', 'WARN')})),
                    ("Re-opened .blend checks", json.dumps({k: sum(c['result'] == k for c in BV['checks']) for k in ('PASS', 'FAIL', 'WARN')})),
                    ("IFC validation", json.dumps({k: sum(c['result'] == k for c in IV['checks']) for k in ('PASS', 'FAIL', 'WARN')}))], ["Source", "Result"]))
    for fn, cap, _ in sheets:
        doc.page(f'<img src="img/{fn}">', a3=True)
    rimgs = sorted((out / "img").glob("render_*.png"))[:6]
    doc.page("<h1>Visualisations</h1><p class='src'>Workbench renders of the saved model, stamped with the revision" + esc(render_note) + ".</p>"
             + "".join(fig(f"img/{p.name}", p.name.replace("render_", "").replace(".png", "").replace("_", " ")) for p in rimgs[:4]))
    if len(rimgs) > 4:
        doc.page("<h1>Visualisations (continued)</h1>" + "".join(fig(f"img/{p.name}", p.name[7:-4].replace("_", " ")) for p in rimgs[4:]))
    # seating rows / exits from the design's own schedules
    rows_ = list(csv.DictReader((D / "reports" / "row_schedule.csv").open(encoding="utf-8")))
    cols = [c for c in ("row", "section", "seats", "floor", "rise", "radius", "floor_elevation") if c in rows_[0]]
    doc.page("<h1>Seating schedule (rows)</h1><p class='src'>reports/row_schedule.csv</p>" + tbl([[r[c] for c in cols] for r in rows_[:45]], cols))
    ex = list(csv.DictReader((D / "reports" / "exit_schedule.csv").open(encoding="utf-8")))
    ecols = [c for c in ("exit_id", "level", "wall", "clear_width_m", "clear_width", "capacity_width", "assigned_occupants", "load_queue_balanced",
                         "required_width_placeholder", "final_exit") if c in ex[0]]
    eg = G["metrics"]["egress"]
    doc.page("<h1>Egress and accessibility</h1><p class='src'>reports/exit_schedule.csv, geometry_checks.json (placeholder factors, not code values)</p>"
             + tbl([[r[c] for c in ecols] for r in ex], ecols)
             + tbl([(k, v) for k, v in eg.items() if not isinstance(v, (dict, list))], ["Egress metric (own engine)", "Value"]))
    oi = (D / "reports" / "open_issues.md").read_text(encoding="utf-8").splitlines()
    doc.page("<h1>Risks and open issues</h1><ul>" + "".join(f"<li>{esc(l.lstrip('- '))}</li>" for l in oi if l.startswith("- "))[:12000] + "</ul>")
    rv = sorted((REPO / "comparisons" / "reviews").glob(f"iter-*/{key}-*.json"))
    if rv:
        last = max(p.parent.name for p in rv)
        findings, scores = [], {}
        for p in rv:
            if p.parent.name != last:
                continue
            j = json.loads(p.read_text(encoding="utf-8"))
            assert j.get("design_id", meta["design_id"]) == meta["design_id"], p
            scores.update(j.get("scores", {}))
            findings += [(f.get("severity"), f.get("discipline"), f.get("finding", "")[:260]) for f in j.get("findings", [])]
        doc.page(f"<h1>Independent review ({esc(last)})</h1><p class='src'>comparisons/reviews/{esc(last)}/{key}-*.json — QA scores, not certification.</p>"
                 + tbl(sorted(scores.items()), ["Discipline", "Score /10"], num=(1,))
                 + tbl(sorted(findings, key=lambda f: ["CRITICAL", "MAJOR", "MINOR"].index(f[0]) if f[0] in ("CRITICAL", "MAJOR", "MINOR") else 3)[:22],
                       ["Severity", "Discipline", "Finding"]))
    revf = D / "REVISIONS.md"
    if revf.exists():
        doc.page("<h1>Revision history</h1><pre style='white-space:pre-wrap;font-size:6.6pt'>" + esc(revf.read_text(encoding="utf-8")) + "</pre>")
    (out / "proposal.html").write_text(doc.html(), encoding="utf-8")
    guard(out, meta["design_id"], [ometa["design_id"], *(json.loads((Do / "reports" / "model_revision.json").read_text())["revision"],)])
    pdf = print_pdf(out / "proposal.html")
    print(f"PROPOSAL {meta['design_id']} {rev}: {out / 'proposal.html'} pdf={pdf}")


# ---------------------------------------------------------------------------------------------------- comparative report
def comparative():
    C = json.loads((REPO / "comparisons" / "out" / "comparison.json").read_text(encoding="utf-8"))
    out = REPO / "comparisons" / "out" / "report"
    if out.exists():
        shutil.rmtree(out)
    stage_assets(out)
    (out / "img").mkdir()
    for f in ("distance_maps.png", "distance_histogram.png", "plan_A_1-400.png", "plan_B_1-400.png", "section_A_1-400.png", "section_B_1-400.png"):
        shutil.copy2(REPO / "comparisons" / "out" / f, out / "img" / f)
    A, B = C["A"], C["B"]
    prov = f"A {A['revision']} · B {B['revision']}"
    doc = Doc("A-end-stage vs B-long-side-stage", prov, "comparisons/compare.py on both manifests", "Comparative feasibility report")
    md = (REPO / "comparisons" / "out" / "comparison.md").read_text(encoding="utf-8").splitlines()
    trows = [[c.strip() for c in l.strip("|").split("|")] for l in md if l.startswith("|") and not l.startswith("|---")]
    rec = (REPO / "comparisons" / "RECOMMENDATION.md")
    doc.page('<h1 style="margin-top:20mm;color:#F5F2EC">Comparative architectural &amp; engineering feasibility report</h1>'
             f'<p class="lead" style="color:#F5F2EC">Option A (end stage, {esc(A["revision"])}) vs Option B (long-side stage, {esc(B["revision"])})</p>'
             '<img src="img/distance_maps.png" style="width:100%;margin-top:8mm"><p class="status" style="color:#E0A090">CONCEPT — UNVERIFIED · NOT FOR CONSTRUCTION</p>',
             cover=True)
    doc.page("<h1>Measured comparison</h1><p class='src'>" + esc(md[2]) + "</p>" + tbl(trows[1:31], trows[0], num=(1, 2)))
    doc.page("<h1>Measured comparison (continued)</h1>" + tbl(trows[31:], trows[0], num=(1, 2)) + fig("img/distance_histogram.png", "Seat distance distribution"))
    for f in ("plan_A_1-400.png", "plan_B_1-400.png", "section_A_1-400.png", "section_B_1-400.png"):
        doc.page(f'<img src="img/{f}">', a3=True)
    rv = sorted((REPO / "comparisons" / "reviews").glob("iter-*/*.json"))
    if rv:
        rows = []
        for p in rv:
            j = json.loads(p.read_text(encoding="utf-8"))
            rows.append((p.parent.name, p.stem, j.get("revision", ""), json.dumps(j.get("scores", {}))[:150], len(j.get("critical_blockers", []))))
        doc.page("<h1>Independent review scores</h1>" + tbl(rows, ["Iteration", "File", "Revision", "Scores", "Critical blockers"]))
    if rec.exists():
        doc.page("<h1>Recommendation</h1>" + "".join(f"<p>{esc(p)}</p>" for p in rec.read_text(encoding="utf-8").split("\n\n") if p.strip()))
    (out / "comparative_report.html").write_text(doc.html(), encoding="utf-8")
    pdf = print_pdf(out / "comparative_report.html")
    print(f"COMPARATIVE REPORT: {out / 'comparative_report.html'} pdf={pdf}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--design")
    ap.add_argument("--compare", action="store_true")
    a = ap.parse_args()
    if a.compare:
        comparative()
    else:
        design_proposal(a.design)
