"""Build or verify one design alternative.

  .venv/Scripts/python tools/build.py --design B --iteration 1        # Option B: full pipeline (writes only in designs/B-*)
  .venv/Scripts/python tools/build.py --design A                      # Option A: NON-DESTRUCTIVE reproduction of the frozen
                                                                      #   baseline (archive/pl-08) in a temp folder
  .venv/Scripts/python tools/build.py --design A --revision pl-02     # reproduce an older archived A revision

Option A keeps its own frozen pipeline (designs/A-end-stage/scripts/run_pipeline.py). Running that in place would
rewrite A's outputs, so this tool never does; it proves reproducibility instead.
"""
import argparse
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from shared.env import design_meta, python_exe  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--design", required=True)
    ap.add_argument("--iteration", type=int)
    ap.add_argument("--revision", default="pl-08", help="Option A archive to reproduce")
    ap.add_argument("--no-render", action="store_true")
    a = ap.parse_args()
    D, meta = design_meta(a.design)
    if "build" not in meta:
        sys.exit(subprocess.call([python_exe(), str(REPO / "tools" / "reproduce_revision.py"), "--design", a.design, "--revision", a.revision]))
    if a.iteration is None:
        ap.error("--iteration is required for designs with a generic build")
    from shared.pipeline import build
    build(a.design, a.iteration, render=not a.no_render)


if __name__ == "__main__":
    main()
