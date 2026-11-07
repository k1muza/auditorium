"""Build the Southgate IFC from the migration plan, phase by phase, auditing each saved checkpoint.

  .venv/Scripts/python scripts/migrate/build_ifc.py --dry-run          # report what would be built
  .venv/Scripts/python scripts/migrate/build_ifc.py                    # full build -> work/builds/<run>/
  .venv/Scripts/python scripts/migrate/build_ifc.py --only SOURCE ...  # pilot subset
  .venv/Scripts/python scripts/migrate/build_ifc.py --publish --expected-current-sha256 <sha|NONE>
        # copy the audited build to bim/southgate.ifc (refuses silent overwrite)

Safety: reads only the plan, inventory and geometry cache (never the .blend); writes a NEW
run folder each time; deterministic GlobalIds make reruns identical (no duplicates); a
failed phase stops the run and leaves earlier checkpoints intact (clean reconstruction).
"""
import argparse, datetime as dt, hashlib, json, pickle, shutil, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
import yaml  # noqa: E402
import ifcopenshell  # noqa: E402
from southgate_bim.authoring.builder import Builder  # noqa: E402
from southgate_bim.validation import audit  # noqa: E402
from southgate_bim.migration.status import design_status  # noqa: E402

PHASES = ["B", "C", "D", "E", "F", "G", "H", "I"]
PHASE_NAMES = {"B": "Spatial structure, spaces and zones", "C": "Structural and architectural framework",
               "D": "Openings, facades and portals", "E": "Roof steel, covering and rainwater",
               "F": "Auditorium and stage", "G": "Ancillary rooms (west office wing, restrooms, terrace)",
               "H": "Building services and acoustic systems", "I": "Foundations and substructure (concept)"}


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--only", nargs="*", help="pilot: build only elements containing these source objects")
    ap.add_argument("--name", default="full")
    ap.add_argument("--no-audit", action="store_true")
    ap.add_argument("--publish", action="store_true", help="publish latest successful full build to bim/southgate.ifc")
    ap.add_argument("--expected-current-sha256", help="sha256 of the bim/southgate.ifc being replaced, or NONE")
    a = ap.parse_args()

    if a.publish:
        return publish(a)
    cfg = yaml.safe_load(open(ROOT / "config/project.yaml", encoding="utf-8"))
    mat_cfg = yaml.safe_load(open(ROOT / "config/materials.yaml", encoding="utf-8"))
    plan = pickle.load(open(ROOT / "work/plan/plan.pkl", "rb"))
    inv = json.load(open(ROOT / "source/geometry_inventory.json", encoding="utf-8"))
    objects = {o["name"]: o for o in inv["objects"]}
    elements = plan["elements"]
    if a.only:
        want = set(a.only)
        elements = [e for e in elements if want & set(e["members"])]
        hosts = {e["stable_id"] for e in elements}
        for e in plan["elements"]:   # keep openings only if both sides are in the pilot
            if e["stable_id"] in hosts and e.get("openings"):
                e["openings"] = [o for o in e["openings"] if o["filler"] in hosts]
    if a.dry_run:
        from collections import Counter
        c = Counter((e["phase"], e["ifc_class"]) for e in elements)
        for ph in PHASES:
            items = {k[1]: v for k, v in c.items() if k[0] == ph}
            print(ph, PHASE_NAMES[ph], sum(items.values()), dict(sorted(items.items(), key=lambda kv: -kv[1])[:12]))
        print("DRY RUN - nothing written")
        return 0
    run = dt.datetime.now().strftime("%Y%m%d-%H%M%S") + "_" + a.name
    out = ROOT / "work/builds" / run
    out.mkdir(parents=True, exist_ok=False)
    cache = pickle.load(open(ROOT / "work/source_cache.pkl", "rb"))
    b = Builder(cfg, mat_cfg, inv, cache, plan, run)
    b.create_project()
    b.status_of = {e["stable_id"]: design_status(e, objects[e["members"][0]]["props"])[0] for e in elements}
    assemblies = plan["assemblies"]
    if a.only:
        sids = {e["stable_id"] for e in elements}
        assemblies = {k: dict(v, children=[c for c in v["children"] if c in sids]) for k, v in assemblies.items()
                      if any(c in sids for c in v["children"])}
    phase_log = []
    for ph in PHASES:
        t0 = time.time()
        sub = [e for e in elements if e["phase"] == ph]
        b.build_phase(ph, sub)
        n_open = b.finish_relationships(sub, assemblies, elements)
        b.write_properties(sub, design_status)
        ck = out / f"checkpoint_{ph}.ifc"
        b.f.write(str(ck))
        entry = {"phase": ph, "name": PHASE_NAMES[ph], "elements": len(sub), "openings_added": n_open,
                 "build_s": round(time.time() - t0, 1), "checkpoint": ck.name, "checkpoint_sha256": sha256(ck)}
        if not a.no_audit and sub:
            t1 = time.time()
            reopened = ifcopenshell.open(str(ck))            # audit the SAVED file
            rows = audit.audit_elements(reopened, sub, objects, cfg["tolerances"],
                                        {r["source"]: r.get("_src_volume") for r in plan["rows"]},
                                        {r["source"]: r.get("_src_aabb") for r in plan["rows"]})
            fc = audit.file_checks(reopened, [e for e in elements if e["phase"] <= ph])
            from collections import Counter
            entry["audit"] = {"status_counts": dict(Counter(r["status"] for r in rows)),
                              "file_checks": {k: v for k, v in fc.items() if not isinstance(v, list) or len(v) < 25},
                              "audit_s": round(time.time() - t1, 1)}
            pickle.dump(rows, open(out / f"audit_{ph}.pkl", "wb"))
            if fc["duplicate_guids"]:
                raise SystemExit(f"phase {ph}: duplicate GlobalIds {fc['duplicate_guids'][:5]} - stopping")
        phase_log.append(entry)
        print(json.dumps(entry), flush=True)
    final = out / "southgate.ifc"
    b.f.write(str(final))
    meta = {"run": run, "elements_planned": len(elements), "phases": phase_log, "fallbacks": b.log,
            "final": final.name, "final_sha256": sha256(final), "pilot": bool(a.only),
            "ifcopenshell": ifcopenshell.version, "completed": dt.datetime.now().isoformat(timespec="seconds")}
    json.dump(meta, open(out / "build_log.json", "w"), indent=1, default=str)
    pickle.dump({"info": b.info, "frames": {k: (v.O, v.X, v.Z) for k, v in b.frames.items()}}, open(out / "build_info.pkl", "wb"))
    print("BUILD_OK", final, meta["final_sha256"], "fallbacks", len(b.log))
    return 0


def publish(a):
    builds = sorted((ROOT / "work/builds").glob("*_full"), key=lambda p: p.name)
    ok = [p for p in builds if (p / "build_log.json").exists()]
    if not ok:
        raise SystemExit("no completed full build to publish")
    src = ok[-1] / "southgate_qto.ifc"          # quantified + validated build
    if not src.exists():
        raise SystemExit(f"{src} missing - run scripts/export/extract_quantities.py on the build first")
    dst = ROOT / "bim/southgate.ifc"
    if dst.exists():
        cur = sha256(dst)
        if a.expected_current_sha256 != cur:
            raise SystemExit(f"refusing to overwrite bim/southgate.ifc (current sha256 {cur}); "
                             f"pass --expected-current-sha256 {cur} to confirm")
        bak = ROOT / "work/published_history" / (dt.datetime.now().strftime("%Y%m%d-%H%M%S") + "_southgate.ifc")
        bak.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(dst, bak)
    elif a.expected_current_sha256 not in (None, "NONE"):
        raise SystemExit("bim/southgate.ifc does not exist; use --expected-current-sha256 NONE")
    shutil.copy2(src, dst)
    rec = {"published": dt.datetime.now().isoformat(timespec="seconds"), "from_build": ok[-1].name,
           "sha256": sha256(dst)}
    json.dump(rec, open(ROOT / "bim/publish_record.json", "w"), indent=1)
    print("PUBLISHED", rec)
    return 0


if __name__ == "__main__":
    sys.exit(main())
