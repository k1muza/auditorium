"""Generic build-and-verify pipeline for any design that declares a design.json `build` block (Option B onwards).

  .venv/Scripts/python tools/build.py --design B --iteration 1

Steps (logged to designs/<id>/logs/<rev-tag>/): unit tests -> Blender build (+ renders) -> regeneration build into a
scratch folder with manifest hash comparison -> re-open .blend verification -> IFC export -> IFC validation ->
drawings -> reports -> presentation renders -> revision record (source + output hashes) -> archive of outputs AND the
exact sources in archive/<rev-tag>/ (so every revision stays reproducible). Writes only inside the design's folder.
Stops on any failing step or any FAIL check in the verification reports.
"""
import hashlib
import json
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from shared.env import blender_exe, design_meta, python_exe  # noqa: E402


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def run(name, cmd, cwd, logdir, timeout=3600):
    t = time.time()
    proc = subprocess.run([str(c) for c in cmd], cwd=cwd, capture_output=True, text=True, timeout=timeout, encoding="utf-8", errors="replace")
    (logdir / f"{name}.log").write_text(f"$ {' '.join(map(str, cmd))}\n# exit {proc.returncode}  ({time.time() - t:.1f}s)\n\n--- stdout ---\n"
                                        f"{proc.stdout}\n--- stderr ---\n{proc.stderr}", encoding="utf-8")
    print(f"[{name}] exit {proc.returncode} ({time.time() - t:.1f}s)")
    if proc.returncode != 0:
        raise SystemExit(f"step {name} failed - see {logdir / (name + '.log')}")
    return proc.stdout


def require_pass(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    failed = [c["id"] for c in data.get("checks", []) if c.get("result") == "FAIL"]
    if failed:
        raise SystemExit(f"{path}: failed checks {failed}")


def tagged(stdout, tag):
    for line in stdout.splitlines():
        if line.startswith(tag + " "):
            return json.loads(line[len(tag) + 1:])
    return None


def build(design, iteration, render=True):
    D, meta = design_meta(design)
    if "build" not in meta:
        raise SystemExit(f"{meta['design_id']} has no generic build block - it keeps its own frozen pipeline (see its design.json)")
    B = meta["build"]
    srcs = [s for s in meta["sources"] if (D / s).is_file()]
    src_hash = hashlib.sha256("".join(sha(D / s) for s in srcs).encode()).hexdigest()[:10]
    rev = f"{meta['rev_prefix']}{iteration:02d}-{src_hash}"
    tag = f"{meta['rev_prefix'].lower()}-{iteration:02d}"
    logdir = D / "logs" / tag
    logdir.mkdir(parents=True, exist_ok=True)
    for d in ("model", "reports", "exports", "renders"):
        (D / d).mkdir(exist_ok=True)
    print("design", meta["design_id"], "revision", rev)
    t0 = time.time()
    PY, BL = python_exe(), blender_exe()
    run("00_unit_tests", [PY, "-m", "unittest", "discover", "-s", B["tests"], "-v"], D, logdir)
    common = ["--layout", D / B["layout"], "--config", D / B["config"], "--revision", rev]
    out = run("01_blender_build", [BL, "--background", "--factory-startup", "--python", REPO / "shared/bim/build_blender.py", "--",
                                   *common, "--out", D / B["blend"], "--manifest", D / B["manifest"], "--render", D / "exports"], D, logdir)
    b1 = tagged(out, "BUILD_SUMMARY")
    scratch = D / "logs" / "regen_scratch"
    scratch.mkdir(exist_ok=True)
    out2 = run("02_regeneration_build", [BL, "--background", "--factory-startup", "--python", REPO / "shared/bim/build_blender.py", "--",
                                         *common, "--out", scratch / "regen.blend", "--manifest", scratch / "regen_manifest.json"], D, logdir)
    b2 = tagged(out2, "BUILD_SUMMARY")
    regen = {"design_id": meta["design_id"], "revision": rev, "build_1_manifest_sha256": b1["manifest_sha256"],
             "build_2_manifest_sha256": b2["manifest_sha256"], "identical": b1["manifest_sha256"] == b2["manifest_sha256"],
             "objects": [b1["objects_exported"], b2["objects_exported"]], "seats": [b1["congregation_seats_in_scene"], b2["congregation_seats_in_scene"]]}
    (D / "reports" / "regeneration_check.json").write_text(json.dumps(regen, indent=2), encoding="utf-8")
    shutil.rmtree(scratch, ignore_errors=True)
    if not regen["identical"]:
        raise SystemExit("regeneration check failed")
    run("03_verify_blend", [BL, "--background", "--factory-startup", D / B["blend"], "--python", REPO / "shared/bim/verify_blend.py", "--",
                            "--out", D / "reports" / "blend_verification.json"], D, logdir)
    require_pass(D / "reports" / "blend_verification.json")
    run("04_export_ifc", [PY, REPO / "shared/bim/export_ifc.py", D / B["manifest"], D / B["ifc"]], D, logdir)
    run("05_validate_ifc", [PY, REPO / "shared/bim/validate_ifc.py", D / B["ifc"], D / B["manifest"], D / "reports" / "ifc_validation.json",
                            D / B["layout"], D / B["config"]], D, logdir)
    require_pass(D / "reports" / "ifc_validation.json")
    run("06_drawings", [PY, D / B["drawings"], D / B["manifest"], D / "exports"], D, logdir)
    run("07_reports", [PY, D / B["reports"], D / B["manifest"], D / "reports"], D, logdir)
    if render:
        run("08_renders", [BL, "--background", "--factory-startup", D / B["blend"], "--python", REPO / "shared/render_views.py", "--",
                           D / "renders" / rev], D, logdir)
    import ifcopenshell
    import matplotlib
    env = {"design_id": meta["design_id"], "revision": rev, "os": platform.platform(), "python_venv": sys.version.split()[0],
           "blender_version": b1["blender"], "ifcopenshell": ifcopenshell.version, "matplotlib": matplotlib.__version__,
           "blender_mcp": "not used - Blender driven headless (blender --background --python)"}
    (D / "reports" / "environment.json").write_text(json.dumps(env, indent=2), encoding="utf-8")
    outputs = sorted(p for d in ("model", "reports", "exports") for p in (D / d).rglob("*") if p.is_file() and p.name != "model_revision.json")
    files = {p.relative_to(D).as_posix(): {"sha256": sha(p), "bytes": p.stat().st_size} for p in outputs}
    rec = {"design_id": meta["design_id"], "revision": rev, "iteration": iteration, "units": meta["units"],
           "source_hashes": {s: sha(D / s) for s in srcs}, "outputs": files, "renders": f"renders/{rev}/",
           "pipeline_seconds": round(time.time() - t0, 1)}
    (D / "reports" / "model_revision.json").write_text(json.dumps(rec, indent=2), encoding="utf-8")
    arch = D / "archive" / tag
    if arch.exists():
        shutil.rmtree(arch)
    for d in ("model", "reports", "exports"):
        shutil.copytree(D / d, arch / d)
    for s in srcs:
        dst = arch / "source" / Path(s.replace("../../", "repo/"))
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(D / s, dst)
    print(json.dumps({"design_id": meta["design_id"], "revision": rev, "seconds": round(time.time() - t0, 1)}))
    return rev
