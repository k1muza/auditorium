"""Verify that every file captured in the pre-restructure baseline still exists byte-for-byte.

  .venv/Scripts/python tools/verify_baseline.py

documentation/migration/BASELINE_SHA256.txt was written before the restructure (paths relative to
the old root). documentation/migration/path_map.json maps old prefixes to their new homes. Exit 1
if any baseline file is missing or its hash differs.
"""
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from shared.env import REPO  # noqa: E402

MIG = REPO / "documentation" / "migration"


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    pm = json.loads((MIG / "path_map.json").read_text(encoding="utf-8"))
    pmap, intended = pm["map"], pm.get("intentionally_modified", {})
    rows = [ln.split(" *", 1) if " *" in ln else ln.split("  ", 1)
            for ln in (MIG / "BASELINE_SHA256.txt").read_text(encoding="utf-8").splitlines() if ln.strip()]
    ok, bad = 0, []
    for h, old in rows:
        old = old.strip().removeprefix("./")
        new = old
        for src, dst in sorted(pmap.items(), key=lambda kv: -len(kv[0])):
            if old == src or old.startswith(src.rstrip("/") + "/"):
                new = dst + old[len(src):]
                break
        p = REPO / new
        if not p.is_file():
            bad.append(f"MISSING {old} -> {new}")
        elif sha(p) != h:
            if old in intended:
                print(f"  intentionally modified (recorded): {old} - {intended[old]}")
                ok += 1
            else:
                bad.append(f"CHANGED {old} -> {new}")
        else:
            ok += 1
    print(f"baseline files verified: {ok}/{len(rows)}")
    for b in bad:
        print(" ", b)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
