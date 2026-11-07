"""Silhouette overlays, IoU metrics, contact sheet and HTML gallery from matching-camera renders.

Overlay colours (from the renders' alpha channel - no image enhancement):
  grey = both models, red = SOURCE only (possible omission), blue = IFC only (possible addition)
"""
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
C = ROOT / "renders/comparisons"
cfg = json.load(open(ROOT / "config/views.json"))
metrics = []
tiles = []
for v in cfg["views"]:
    if v.get("skip"):
        metrics.append({"id": v["id"], "title": v["title"], "skipped": True})
        continue
    s, i = C / f"{v['id']}_source.png", C / f"{v['id']}_ifc.png"
    if not (s.exists() and i.exists()):
        metrics.append({"id": v["id"], "title": v["title"], "missing": True})
        continue
    S = np.asarray(Image.open(s).convert("RGBA"))
    I = np.asarray(Image.open(i).convert("RGBA"))
    ms, mi = S[..., 3] > 32, I[..., 3] > 32
    both, so, io = ms & mi, ms & ~mi, ~ms & mi
    ov = np.full(S.shape[:2] + (3,), 255, np.uint8)
    ov[both] = (150, 150, 150)
    ov[so] = (220, 30, 30)
    ov[io] = (30, 90, 230)
    Image.fromarray(ov).save(C / f"{v['id']}_overlay.png")
    union = (ms | mi).sum()
    m = {"id": v["id"], "title": v["title"], "iou": round(float(both.sum() / union), 4) if union else None,
         "source_only_px_pct": round(100 * float(so.sum() / max(1, union)), 3),
         "ifc_only_px_pct": round(100 * float(io.sum() / max(1, union)), 3)}
    metrics.append(m)
    tiles.append((v, s, i, C / f"{v['id']}_overlay.png", m))
json.dump(metrics, open(C / "comparison_metrics.json", "w"), indent=1)

# contact sheet: rows = views, cols = source | IFC | overlay
tw, th = 480, 270
sheet = Image.new("RGB", (tw * 3 + 40, (th + 30) * len(tiles) + 50), (245, 245, 245))
d = ImageDraw.Draw(sheet)
d.text((10, 10), "Southgate Worship Center - source Blender snapshot | Bonsai IFC (bim/southgate.ifc) | silhouette overlay (red=source only, blue=IFC only)", fill=(0, 0, 0))
y = 40
for v, s, i, o, m in tiles:
    d.text((10, y), f"{v['id']}  {v['title']}   IoU {m['iou']}  source-only {m['source_only_px_pct']}%  IFC-only {m['ifc_only_px_pct']}%", fill=(0, 0, 0))
    for k, p in enumerate((s, i, o)):
        im = Image.open(p).convert("RGBA")
        bg = Image.new("RGBA", im.size, (40, 42, 48, 255) if k < 2 else (255, 255, 255, 255))
        bg.alpha_composite(im)
        sheet.paste(bg.convert("RGB").resize((tw, th)), (10 + k * (tw + 10), y + 15))
    y += th + 30
sheet.save(C / "contact_sheet.png")

rows = "\n".join(
    f"""<section><h2>{v['title']}</h2><p class="m">IoU <b>{m['iou']}</b> &middot; source-only {m['source_only_px_pct']} % &middot; IFC-only {m['ifc_only_px_pct']} %</p>
<div class="g"><figure><img src="{s.name}" loading="lazy"><figcaption>Source snapshot (Blender)</figcaption></figure>
<figure><img src="{i.name}" loading="lazy"><figcaption>IFC via Bonsai</figcaption></figure>
<figure class="o"><img src="{o.name}" loading="lazy"><figcaption>Overlay: red = source only, blue = IFC only</figcaption></figure></div></section>"""
    for v, s, i, o, m in tiles)
skipped = "".join(f"<li>{m['title']}</li>" for m in metrics if m.get("skipped"))
html = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Southgate Migration Comparison</title><style>
:root{{--bg:#f6f6f4;--fg:#1c1c1c;--card:#fff;--mut:#666}}
@media (prefers-color-scheme:dark){{:root{{--bg:#16181c;--fg:#eee;--card:#22252b;--mut:#aaa}}}}
body{{margin:0;padding:16px;background:var(--bg);color:var(--fg);font:15px/1.45 system-ui,sans-serif}}
h1{{font-size:1.4rem}} h2{{font-size:1.05rem;margin:.2rem 0}} .m{{color:var(--mut);margin:.2rem 0 .6rem}}
section{{background:var(--card);border-radius:10px;padding:12px;margin:0 0 16px}}
.g{{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:10px}}
figure{{margin:0}} img{{width:100%;height:auto;background:#2a2d33;border-radius:6px}} .o img{{background:#fff}}
figcaption{{font-size:.8rem;color:var(--mut)}}</style></head><body>
<h1>Southgate Worship Center - source model vs native IFC</h1>
<p>Matching cameras (<code>config/views.json</code>), Workbench renders without enhancement. Source: verified snapshot
(sha256 f5d61c75...) limited to the auditorium boundary. IFC: <code>bim/southgate.ifc</code> loaded through Bonsai 0.9.0-post1.
Hidden-in-view rules are defined on source objects and applied to IFC elements through the source-to-IFC mapping.</p>
<p>Not rendered (out of scope):</p><ul>{skipped}</ul>
{rows}</body></html>"""
(C / "gallery.html").write_text(html, encoding="utf-8")
print(json.dumps(metrics, indent=1))
