"""Option B drawing set from the Blender manifest (shared sheet generator, 1:400 at A3 like the comparison sheets).

  .venv/Scripts/python designs/B-long-side-stage/src/drawings.py <blender_manifest.json> <exports dir>
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from shared.drawings import sheets as S  # noqa: E402

DESIGN_ID = "B-long-side-stage"


def main(manifest_path, out_dir):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    M = S.load(manifest_path)
    M["design_id"] = DESIGN_ID
    F = M["grid"]["y_lines"]
    xc = (M["grid"]["x_lines"]["A"] + M["grid"]["x_lines"]["L"]) / 2
    S.plan(M, out / "floor_plan.png", "Ground floor plan", "B-A100")
    S.plan(M, out / "seating_plan.png", "Seating, aisles and exits", "B-A110", spaces=False,
           subtitle="Congregation (blue), choir (purple), wheelchair spaces (green), fire exits (red)")
    S.section(M, out / "section_AA.png", "x", xc + 4.0, "Section A-A (hall depth, beside the axis)", "B-A301")
    S.section(M, out / "section_BB.png", "y", F["3"] - 15.0, "Section B-B (across the fan, 15 m in front of the platform focus)", "B-A302")
    S.structure(M, out / "structural_grid.png", "Structural grid and roof framing", "B-S100")
    files = sorted(p.name for p in out.glob("*.png"))
    print("DRAWINGS " + json.dumps(files))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
