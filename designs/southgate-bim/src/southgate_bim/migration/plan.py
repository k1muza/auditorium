"""Migration planning (dry run): decide what happens to every source object.

Nothing is written to IFC here.  The plan records, for every source object, a
provisional disposition and (for migrating objects) the target element it maps
to, its IFC class, method, storey, assembly, stable identifier and GlobalId.

Dispositions (exactly one per source object, finalised after the build):
  MIGRATED_NATIVE, MIGRATED_CUSTOM_IFC, VISUAL_ONLY, EXCLUDED_INTENTIONALLY,
  SUPERSEDED_OR_DUPLICATE, MIGRATION_FAILED, OUTSTANDING_MIGRATION, NEW_DESIGN_REQUIRED
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import pickle
import re
import uuid
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import yaml

from ..geometry import fit

STRUCTURAL = {"IfcBeam", "IfcColumn", "IfcMember", "IfcPlate", "IfcFooting", "IfcMechanicalFastener",
              "IfcDiscreteAccessory"}
SERVICES = {"IfcPipeSegment", "IfcPipeFitting", "IfcDuctSegment", "IfcAirTerminal", "IfcFan", "IfcDuctSilencer",
            "IfcSensor", "IfcActuator", "IfcEvaporativeCooler", "IfcLightFixture", "IfcAudioVisualAppliance",
            "IfcOutlet", "IfcWasteTerminal", "IfcSanitaryTerminal", "IfcFastener"}
SUPERSEDED_STATUS = re.compile(r"SUPERSEDED|ARCHIVED|RETIRED", re.I)
EXCLUDE_BOQ = re.compile(r"^EXCLUDE", re.I)


def load_yaml(p):
    with open(p, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def guid_for(stable_id: str, namespace: str) -> str:
    import ifcopenshell.guid
    return ifcopenshell.guid.compress(uuid.uuid5(uuid.UUID(namespace), stable_id).hex)


class Planner:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.cfg = load_yaml(self.root / "config/project.yaml")
        self.rules = load_yaml(self.root / "config/classification_rules.yaml")["rules"]
        for r in self.rules:
            for k in ("coll", "name", "etype"):
                if k in r:
                    r["_" + k] = re.compile(r[k], re.I if k == "etype" else 0)
        self.inv = json.load(open(self.root / "source/geometry_inventory.json", encoding="utf-8"))
        with open(self.root / "work/source_cache.pkl", "rb") as fh:
            self.cache = pickle.load(fh)
        self.objects = {o["name"]: o for o in self.inv["objects"]}
        self.mapping_path = self.root / "source/source_to_ifc_mapping.csv"

    # ------------------------------------------------------------------ helpers
    def world_mesh(self, name):
        c = self.cache["objects"].get(name)
        if not c:
            return None, None
        m = self.cache["meshes"][c["mesh"]]
        return fit.world_vertices(m["verts"], c["matrix"]), m["faces"]

    def match_rule(self, o):
        coll = o["collections"][0] if o["collections"] else ""
        et = str(o["props"].get("element_type", ""))
        for r in self.rules:
            if "_coll" in r and not r["_coll"].search(coll):
                continue
            if "_etype" in r and not r["_etype"].search(et):
                continue
            m = None
            if "_name" in r:
                m = r["_name"].search(o["name"])
                if not m:
                    continue
            return r, (m.groupdict() if m else {})
        raise RuntimeError("no rule (fallback missing) for " + o["name"])

    @staticmethod
    def template(t, o, groups):
        if t is None:
            return None
        coll = o["collections"][0]
        ctx = {k: (str(int(v)) if isinstance(v, str) and v.isdigit() else v) for k, v in groups.items()}
        mm = re.search(r"(\d+)$", coll)
        ctx["_coll_suffix"] = mm.group(1) if mm else coll
        mv = re.match(r"^(VENT-\d+-(?:[NSEW]-)?(?:[A-Z]+\d+|[A-Z]+(?:-[NS])?))", o["name"])
        ctx["_vent_unit"] = mv.group(1) if mv else o["name"]
        return t.format(**ctx)

    def in_boundary(self, o):
        b = self.cfg["boundary"]["include_box"]
        c = [(o["aabb_min"][i] + o["aabb_max"][i]) / 2 for i in range(3)]
        return all(b["min"][i] <= c[i] <= b["max"][i] for i in range(3))

    def storey_for(self, zmin):
        st = sorted(self.cfg["storeys"], key=lambda s: s["elevation"])
        chosen = st[0]
        for s in st:
            if zmin + 0.35 >= s["elevation"]:
                chosen = s
        return chosen["code"]

    # ------------------------------------------------------------------ disposition
    def pre_disposition(self, o):
        """Returns (disposition|None, reason). None = candidate for migration."""
        p = o["props"]
        coll = o["collections"][0] if o["collections"] else ""
        ex_c = self.cfg["boundary"]["excluded_collections"]
        if o["type"] in ("CAMERA", "LIGHT", "LIGHT_PROBE"):
            return "VISUAL_ONLY", f"{o['type'].lower()} - presentation rig, retained in bim/visualisation.blend (not construction)"
        if o["type"] == "EMPTY":
            return "EXCLUDED_INTENTIONALLY", "empty/transform helper without geometry"
        if coll in ex_c:
            return "EXCLUDED_INTENTIONALLY", ex_c[coll]
        for pat, why in self.cfg["boundary"]["excluded_name_patterns"].items():
            if re.search(pat, o["name"]):
                return "EXCLUDED_INTENTIONALLY", why
        if not self.in_boundary(o):
            return "EXCLUDED_INTENTIONALLY", "outside the documented auditorium boundary box"
        ds = str(p.get("design_status", ""))
        why_sup = p.get("exclusion_reason") or p.get("EXT10_archived_hidden") or ds
        archived_coll = bool(re.search(r"ARCHIV|LEGACY|PLACEHOLDERS-ARCHIVED|BEFORE-STRAIGHTENING|ALT-[AC]-|CAPACITY-STUDY", coll))
        if not o["visible"]:
            is_fdn = str(p.get("element_type", "")) == "Foundation" or re.search(r"FOOTING|FOUNDATION|-PAD$|PAD-", o["name"])
            if is_fdn and not archived_coll and not SUPERSEDED_STATUS.search(ds) and not EXCLUDE_BOQ.search(str(p.get("boq_inclusion", ""))):
                return None, "hidden in source for presentation (below-grade foundation concept) - migrated as CONCEPT_UNVERIFIED"
            src = "archive collection" if archived_coll else "hidden in source"
            return "SUPERSEDED_OR_DUPLICATE", f"{src}; {why_sup or 'retired by a later design revision (hidden, not deleted, for reversibility)'}"
        if re.search(r"ARCHIVED", o["name"]) or SUPERSEDED_STATUS.search(ds) or (
                EXCLUDE_BOQ.search(str(p.get("boq_inclusion", ""))) and p.get("exclusion_reason")):
            return "SUPERSEDED_OR_DUPLICATE", f"visible but marked superseded in source: {why_sup or o['name']}"
        if o["type"] == "FONT" and o["name"].startswith("ANNEX-ROOM-LABEL"):
            return "EXCLUDED_INTENTIONALLY", "room-name annotation text; name recorded for future IfcSpace (see outstanding work)"
        if coll.startswith("RR Documentation and Validation"):
            return "EXCLUDED_INTENTIONALLY", "design-check annotation (turning circle / validation marker) - not a construction element"
        if o["type"] not in ("MESH", "CURVE", "FONT"):
            return "EXCLUDED_INTENTIONALLY", f"unsupported object type {o['type']}"
        if o["name"] not in self.cache["objects"]:
            return "MIGRATION_FAILED", "no evaluable geometry in source cache"
        return None, ""

    # ------------------------------------------------------------------ main
    def build(self, fit_cache_path: Path | None = None):
        fit_cache = {}
        if fit_cache_path and fit_cache_path.exists():
            with open(fit_cache_path, "rb") as fh:
                fit_cache = pickle.load(fh)
        rows, cands = [], []
        for o in self.inv["objects"]:
            disp, reason = self.pre_disposition(o)
            row = {"source": o["name"], "collection": o["collections"][0] if o["collections"] else "",
                   "type": o["type"], "visible": o["visible"], "disposition": disp, "reason": reason,
                   "bim_id": o["props"].get("bim_id", "")}
            rows.append(row)
            if disp is None:
                cands.append((o, row))
        # duplicates (identical bounds + vertex count) among candidates
        seen = {}
        for o, row in sorted(cands, key=lambda t: (not t[0]["visible"], t[0]["name"])):
            key = (tuple(round(x, 3) for x in o["aabb_min"] + o["aabb_max"]), o.get("mesh", {}).get("verts"))
            if key in seen:
                row["disposition"] = "SUPERSEDED_OR_DUPLICATE"
                row["reason"] = f"geometric duplicate of {seen[key]} (identical bounds and vertex count)"
            else:
                seen[key] = o["name"]
        cands = [(o, r) for o, r in cands if r["disposition"] is None]

        # rules, fits, groups
        groups = defaultdict(list)
        n_fit = 0
        for o, row in cands:
            r, g = self.match_rule(o)
            row["rule"] = r["id"]
            gkey = self.template(r.get("group"), o, g)
            row["group"] = gkey
            row["assembly"] = self.template(r.get("assembly"), o, g)
            c = self.cache["objects"][o["name"]]
            mesh = self.cache["meshes"][c["mesh"]]
            fk = (c["mesh"], mesh["hash"], np.round(c["matrix"], 6).tobytes())
            if fk not in fit_cache or "src_aabb" not in fit_cache[fk]:
                w = fit.world_vertices(mesh["verts"], c["matrix"])
                if fk not in fit_cache:
                    fit_cache[fk] = fit.analyse(w, mesh["faces"]) if len(w) <= 400 else {"kind": "mesh", "nverts": len(w)}
                rv = fit.robust_volume(w, mesh["faces"])
                fd = fit_cache[fk]
                fd["src_closed"] = rv is not None
                fd["src_volume_method"] = "closed mesh (re-oriented divergence)"
                if rv is None and fd["kind"] == "box":
                    rv = float(np.prod(np.linalg.norm(np.asarray(fd["edges"]), axis=1)))
                    fd["src_volume_method"] = "OPEN source mesh - volume from proven box vertices"
                elif rv is None and fd["kind"] == "prism" and not any(c is not None for c in fd.get("clips", [])):
                    lp = np.asarray(fd["loops"][0])
                    rv = fit.polygon_area_3d(lp, fd["direction"]) * fd["depth"] - sum(
                        fit.polygon_area_3d(np.asarray(h), fd["direction"]) * fd["depth"] for h in fd.get("holes", []))
                    fd["src_volume_method"] = "OPEN source mesh - volume from proven prism vertices"
                elif rv is None:
                    fd["src_volume_method"] = "OPEN source mesh - volume not measurable"
                fd["src_volume"] = rv
                fd["src_aabb"] = (w.min(axis=0).tolist(), w.max(axis=0).tolist())
                n_fit += 1
            row["_fit"] = fit_cache[fk]
            row["_src_volume"] = fit_cache[fk]["src_volume"]
            row["_src_aabb"] = fit_cache[fk]["src_aabb"]
            row["_mesh_key"] = c["mesh"]
            row["_shared"] = c["shared"]
            groups[gkey or ("OBJ:" + o["name"])].append((o, row, r))
        if fit_cache_path:
            with open(fit_cache_path, "wb") as fh:
                pickle.dump(fit_cache, fh, protocol=4)

        mapping = self.load_mapping()
        seq = Counter()
        for v in mapping.values():
            m = re.match(r".*-(\d{4})$", v["stable_id"])
            if m:
                cat = v["stable_id"].rsplit("-", 1)[0]
                seq[cat] = max(seq[cat], int(m.group(1)))
        prefix = self.cfg["project"]["id_prefix"]
        ns = self.cfg["project"]["guid_namespace"]
        elements = []
        for key, members in sorted(groups.items(), key=lambda kv: kv[0]):
            o0, row0, r = members[0]
            skey = key if not key.startswith("OBJ:") else key
            skey = ("GROUP:" + key) if not key.startswith("OBJ:") else key
            if skey in mapping:
                sid = mapping[skey]["stable_id"]
            else:
                cat = f"{prefix}-{r['cat']}"
                seq[cat] += 1
                sid = f"{cat}-{seq[cat]:04d}"
            gid = guid_for(sid, ns)
            mapping[skey] = {"source_key": skey, "stable_id": sid, "global_id": gid, "ifc_class": r["cls"]}
            zmin = min(m[0]["aabb_min"][2] for m in members)
            asm = row0.get("assembly")
            el = {"stable_id": sid, "global_id": gid, "source_key": skey, "rule": r["id"], "ifc_class": r["cls"],
                  "predefined_type": r.get("ptype"), "object_type": r.get("otype"), "method": r["method"],
                  "phase": r["phase"], "system": r.get("system"), "assembly": asm, "status_override": r.get("status"),
                  "storey": self.storey_for(zmin), "members": [m[0]["name"] for m in members]}
            elements.append(el)
            for _, row, _ in members:
                row["target"] = sid
                row["target_guid"] = gid
                row["ifc_class"] = r["cls"]
                row["phase"] = r["phase"]
        # wall consolidation + openings
        from . import openings as op
        rows_by_source = {r["source"]: r for r in rows}
        merges, hosts = op.plan(elements, rows_by_source, self.objects)
        by_sid = {e["stable_id"]: e for e in elements}
        for m in merges:
            pieces = m["pieces"]
            names = sorted(n for p in pieces for n in p["members"])
            skey = "WALLMERGE:" + names[0]
            if skey in mapping:
                sid = mapping[skey]["stable_id"]
            else:
                cat = f"{prefix}-WALL"
                seq[cat] += 1
                sid = f"{cat}-{seq[cat]:04d}"
            gid = guid_for(sid, ns)
            mapping[skey] = {"source_key": skey, "stable_id": sid, "global_id": gid, "ifc_class": "IfcWall"}
            p0 = pieces[0]
            el = dict(p0, stable_id=sid, global_id=gid, source_key=skey, method="wall_merged", members=names,
                      storey=min(p["storey"] for p in pieces), phase=min(p["phase"] for p in pieces),
                      wall_box={k: m[k] for k in ("nax", "nmin", "nmax", "rect", "lintel_rects")},
                      openings=[{"filler": f["stable_id"], "rect": h, "nax": m["nax"], "nrange": (m["nmin"], m["nmax"])}
                                for f, h in m["holes"]],
                      merge_evidence={"pieces": [p["stable_id"] for p in pieces], "residual_m2": m["residual_m2"], "lintels": m["lintels"]})
            for p in pieces:
                elements.remove(p)
                mapping.pop(p["source_key"], None)
            elements.append(el)
            by_sid[sid] = el
            for n in names:
                rows_by_source[n]["target"] = sid
                rows_by_source[n]["target_guid"] = gid
        for h in hosts:
            host = by_sid[h["host"]]
            mn, mx = op.aabb_of(host["members"], self.objects)
            host.setdefault("openings", []).append({"filler": h["filler"], "rect": h["rect"], "nax": h["nax"],
                                                    "nrange": (mn[h["nax"]], mx[h["nax"]]), "overlap_m3": h["overlap_m3"]})
        self.merges, self.hosts = merges, hosts
        # assemblies
        assemblies = {}
        for el in elements:
            a = el["assembly"]
            if not a:
                continue
            skey = "ASSEMBLY:" + a
            if skey not in mapping:
                m = re.match(r"TRUSS-(\d+)$", a)
                sid = f"{prefix}-TRUSS-T{int(m.group(1)) + 1:02d}" if m else f"{prefix}-ASM-{a}"
                mapping[skey] = {"source_key": skey, "stable_id": sid, "global_id": guid_for(sid, ns),
                                 "ifc_class": "IfcRoof" if a == "ROOF" else (
                                     "IfcCurtainWall" if a.endswith("CURTAIN-WALL") else (
                                         "IfcStair" if a.startswith("STAIR-") or a == "SPIRAL-STAIR" else "IfcElementAssembly"))}
            asm = assemblies.setdefault(a, dict(mapping[skey], key=a, children=[], storey=el["storey"]))
            asm["children"].append(el["stable_id"])
            if el["storey"] < asm["storey"]:
                asm["storey"] = el["storey"]
        self.mapping = mapping
        return rows, elements, assemblies, n_fit

    def load_mapping(self):
        if not self.mapping_path.exists():
            return {}
        with open(self.mapping_path, encoding="utf-8", newline="") as fh:
            return {r["source_key"]: r for r in csv.DictReader(fh)}

    def save_mapping(self):
        with open(self.mapping_path, "w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=["source_key", "stable_id", "global_id", "ifc_class"])
            w.writeheader()
            for k in sorted(self.mapping):
                w.writerow({f: self.mapping[k][f] for f in w.fieldnames})


def summarise(rows, elements, assemblies):
    disp = Counter(r["disposition"] or "TO_MIGRATE" for r in rows)
    by_cls = Counter(e["ifc_class"] for e in elements)
    by_phase = Counter(e["phase"] for e in elements)
    kinds = Counter(r["_fit"]["kind"] for r in rows if r.get("_fit"))
    return {"generated": dt.datetime.now().isoformat(timespec="seconds"), "source_objects": len(rows),
            "provisional_dispositions": dict(disp), "target_elements": len(elements),
            "assemblies": len(assemblies), "elements_by_class": dict(by_cls.most_common()),
            "elements_by_phase": dict(sorted(by_phase.items())), "geometry_kinds": dict(kinds)}
