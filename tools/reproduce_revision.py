"""Prove that an archived revision regenerates from its archived sources (read-only on the design).

  .venv/Scripts/python tools/reproduce_revision.py --design A --revision pl-08
  .venv/Scripts/python tools/reproduce_revision.py --design A --revision pl-02

Uses designs/<id>/archive/<revision>/source/ (config, scripts, tests). Steps, all in a temp folder:
1. source hashes are compared with the revision's reports/model_revision.json `source_hashes`;
2. unit tests run against the archived sources;
3. a headless Blender build writes a fresh manifest, compared byte-for-byte (SHA-256) with the
   archived model/blender_manifest.json, and the congregation seat count is read back.
Nothing inside designs/ is written. Exit 1 on any mismatch.
"""
import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from shared.env import blender_exe, design_dir, python_exe  # noqa: E402


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--design", required=True)
    ap.add_argument("--revision", required=True, help="archive folder name, e.g. pl-08")
    args = ap.parse_args()
    arch = design_dir(args.design) / "archive" / args.revision
    src = arch / "source"
    rec = json.loads((arch / "reports" / "model_revision.json").read_text(encoding="utf-8"))
    result = {"design": args.design, "archive": args.revision, "revision": rec["revision"]}
    hashes = {k: (sha(src / k) if (src / k).is_file() else None) for k in rec["source_hashes"]}
    result["source_hash_mismatch"] = [k for k, h in hashes.items() if h != rec["source_hashes"][k]]
    with tempfile.TemporaryDirectory(prefix="repro_") as tmp:
        work = Path(tmp)
        for d in ("config", "scripts", "tests"):
            shutil.copytree(src / d, work / d)
        t = subprocess.run([python_exe(), "-m", "unittest", "discover", "-s", "tests"], cwd=work,
                           capture_output=True, text=True)
        result["unit_tests"] = (t.stderr.strip().splitlines() or ["?"])[-1]
        b = subprocess.run([blender_exe(), "--background", "--factory-startup", "--python", "scripts/build_auditorium.py",
                            "--", "--out", "regen.blend", "--manifest", "regen_manifest.json", "--revision", rec["revision"]],
                           cwd=work, capture_output=True, text=True, encoding="utf-8", errors="replace")
        summ = next((json.loads(ln[14:]) for ln in b.stdout.splitlines() if ln.startswith("BUILD_SUMMARY ")), None)
        if summ is None:
            print(b.stdout[-2000:], b.stderr[-2000:])
            raise SystemExit("build failed")
        result["rebuilt_manifest_sha256"] = sha(work / "regen_manifest.json")
    result["archived_manifest_sha256"] = sha(arch / "model" / "blender_manifest.json")
    result["manifest_identical"] = result["rebuilt_manifest_sha256"] == result["archived_manifest_sha256"]
    result["congregation_seats"] = summ["congregation_seats_in_scene"]
    ok = result["manifest_identical"] and not result["source_hash_mismatch"] and result["unit_tests"] == "OK" \
        and result["congregation_seats"] == 3000
    result["REPRODUCED"] = ok
    print(json.dumps(result, indent=2))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
