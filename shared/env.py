"""Project-wide environment helpers: repository root, design registry and tool discovery.

No absolute paths are stored in the repository. Blender is found from the BLENDER_EXE environment
variable, then PATH, then the standard Windows install folders.
"""
import glob
import json
import os
import shutil
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DESIGNS = REPO / "designs"


def design_dir(design_id):
    """Resolve 'A', 'B', 'A-end-stage' etc. to the design folder."""
    for d in sorted(DESIGNS.iterdir()):
        if d.is_dir() and (d.name == design_id or d.name.split("-")[0] == design_id):
            return d
    raise SystemExit(f"unknown design {design_id!r}; known: {[d.name for d in DESIGNS.iterdir() if d.is_dir()]}")


def design_meta(design_id):
    d = design_dir(design_id)
    return d, json.loads((d / "design.json").read_text(encoding="utf-8"))


def blender_exe():
    exe = os.environ.get("BLENDER_EXE") or shutil.which("blender")
    if exe:
        return exe
    hits = sorted(glob.glob(os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"),
                                         "Blender Foundation", "Blender *", "blender.exe")))
    if hits:
        return hits[-1]
    raise SystemExit("Blender not found: set BLENDER_EXE")


def python_exe():
    for c in (REPO / ".venv" / "Scripts" / "python.exe", REPO / ".venv" / "bin" / "python"):
        if c.exists():
            return str(c)
    return shutil.which("python") or "python"
