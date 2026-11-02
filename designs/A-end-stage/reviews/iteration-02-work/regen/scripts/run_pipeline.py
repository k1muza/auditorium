"""Run one full build-and-verify iteration and record evidence.

  .venv/Scripts/python scripts/run_pipeline.py --iteration 1

Steps (each logged to logs/iteration-NN/): unit tests -> Blender build (+renders) -> regeneration
build into a scratch folder and manifest hash comparison -> re-open .blend verification ->
IFC export -> IFC validation -> drawings -> reports -> revision manifest + model index ->
archive copy in archive/iteration-NN/. Exits non-zero if a step fails; failures are logged, not hidden.
"""
import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BLENDER = os.environ.get("BLENDER_EXE", r"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe")
PY = sys.executable
SOURCES = ["config/auditorium_params.json", "scripts/auditorium_layout.py", "scripts/build_auditorium.py",
           "scripts/verify_blend.py", "scripts/export_ifc.py", "scripts/validate_ifc.py", "scripts/make_drawings.py",
           "scripts/generate_reports.py", "scripts/run_pipeline.py", "tests/test_layout.py"]


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def run(name, cmd, logdir, timeout=1800):
    t = time.time()
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=timeout, encoding="utf-8", errors="replace")
    log = logdir / f"{name}.log"
    log.write_text(f"$ {' '.join(map(str, cmd))}\n# exit {proc.returncode}  ({time.time() - t:.1f}s)\n\n--- stdout ---\n"
                   f"{proc.stdout}\n--- stderr ---\n{proc.stderr}", encoding="utf-8")
    print(f"[{name}] exit {proc.returncode} ({time.time() - t:.1f}s)")
    if proc.returncode != 0:
        raise SystemExit(f"step {name} failed - see {log}")
    return proc.stdout


def tagged(stdout, tag):
    for line in stdout.splitlines():
        if line.startswith(tag + " "):
            return json.loads(line[len(tag) + 1:])
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--iteration", type=int, required=True)
    args = ap.parse_args()
    n = args.iteration
    src_hash = hashlib.sha256("".join(sha(ROOT / s) for s in SOURCES).encode()).hexdigest()[:10]
    rev = f"IT{n:02d}-{src_hash}"
    logdir = ROOT / "logs" / f"iteration-{n:02d}"
    logdir.mkdir(parents=True, exist_ok=True)
    for d in ("model", "reports", "exports"):
        (ROOT / d).mkdir(exist_ok=True)
    print("revision", rev)
    t0 = time.time()
    run("00_unit_tests", [PY, "-m", "unittest", "discover", "-s", "tests", "-v"], logdir)
    blend, manifest = "model/church_3000_concept.blend", "model/blender_manifest.json"
    out = run("01_blender_build", [BLENDER, "--background", "--factory-startup", "--python", "scripts/build_auditorium.py",
                                   "--", "--out", blend, "--manifest", manifest, "--revision", rev, "--render", "exports"], logdir)
    b1 = tagged(out, "BUILD_SUMMARY")
    scratch = ROOT / "logs" / "regen_scratch"
    scratch.mkdir(exist_ok=True)
    out2 = run("02_regeneration_build", [BLENDER, "--background", "--factory-startup", "--python", "scripts/build_auditorium.py",
                                         "--", "--out", str(scratch / "regen.blend"), "--manifest", str(scratch / "regen_manifest.json"),
                                         "--revision", rev], logdir)
    b2 = tagged(out2, "BUILD_SUMMARY")
    regen = {"revision": rev, "build_1_manifest_sha256": b1["manifest_sha256"], "build_2_manifest_sha256": b2["manifest_sha256"],
             "identical": b1["manifest_sha256"] == b2["manifest_sha256"], "objects": [b1["objects_exported"], b2["objects_exported"]],
             "seats": [b1["congregation_seats_in_scene"], b2["congregation_seats_in_scene"]],
             "note": "Two independent headless Blender builds from the same config/scripts; the manifest (all object names, "
                     "meshes, world matrices, properties) must be byte-identical. .blend binaries differ only by timestamps."}
    (ROOT / "reports" / "regeneration_check.json").write_text(json.dumps(regen, indent=2), encoding="utf-8")
    shutil.rmtree(scratch, ignore_errors=True)
    if not regen["identical"]:
        raise SystemExit("regeneration check failed")
    run("03_verify_blend", [BLENDER, "--background", "--factory-startup", blend, "--python", "scripts/verify_blend.py", "--",
                            "--config", "config/auditorium_params.json", "--out", "reports/blend_verification.json"], logdir)
    ifc = "model/church_3000_concept.ifc"
    run("04_export_ifc", [PY, "scripts/export_ifc.py", manifest, ifc], logdir, timeout=3600)
    run("05_validate_ifc", [PY, "scripts/validate_ifc.py", ifc, manifest, "reports/ifc_validation.json"], logdir, timeout=3600)
    run("06_drawings", [PY, "scripts/make_drawings.py", manifest, "exports"], logdir)
    run("07_reports", [PY, "scripts/generate_reports.py", manifest, "reports"], logdir)
    # environment record
    import ifcopenshell
    import matplotlib
    env = {"revision": rev, "os": platform.platform(), "python_venv": sys.version.split()[0], "blender_exe": BLENDER,
           "blender_version": b1["blender"], "ifcopenshell": ifcopenshell.version, "matplotlib": matplotlib.__version__,
           "blender_mcp": "NOT AVAILABLE in this session - Blender driven headless via command line (blender --background --python)",
           "bonsai": "not installed; IFC written with IfcOpenShell API from the Blender scene manifest"}
    (ROOT / "reports" / "environment.json").write_text(json.dumps(env, indent=2), encoding="utf-8")
    # revision manifest + index
    outputs = sorted(p for d in ("model", "reports", "exports") for p in (ROOT / d).rglob("*") if p.is_file())
    files = {str(p.relative_to(ROOT)).replace("\\", "/"): {"sha256": sha(p), "bytes": p.stat().st_size} for p in outputs
             if p.name != "model_revision.json"}
    srcs = {s: sha(ROOT / s) for s in SOURCES}
    (ROOT / "reports" / "model_revision.json").write_text(json.dumps(
        {"revision": rev, "iteration": n, "source_hashes": srcs, "outputs": files,
         "pipeline_seconds": round(time.time() - t0, 1)}, indent=2), encoding="utf-8")
    idx = [f"# Model index - revision `{rev}`", "", "CONCEPT - UNVERIFIED - NOT FOR CONSTRUCTION. File hashes in "
           "`reports/model_revision.json`.", "", "| File | Bytes |", "|---|---:|"]
    idx += [f"| `{k}` | {v['bytes']:,} |" for k, v in files.items()]
    idx += ["", "Logs: `logs/iteration-%02d/` (unit tests, Blender build, regeneration build, .blend verification, IFC export, "
            "IFC validation, drawings, reports)." % n]
    (ROOT / "reports" / "model_index.md").write_text("\n".join(idx) + "\n", encoding="utf-8")
    arch = ROOT / "archive" / f"iteration-{n:02d}"
    if arch.exists():
        shutil.rmtree(arch)
    for d in ("model", "reports", "exports"):
        shutil.copytree(ROOT / d, arch / d)
    shutil.copytree(ROOT / "config", arch / "config")
    print(json.dumps({"revision": rev, "seconds": round(time.time() - t0, 1), "regeneration_identical": regen["identical"]}))


if __name__ == "__main__":
    main()
