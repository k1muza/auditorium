#!/usr/bin/env bash
# Full re-migration pipeline (Git Bash). Safe: new build folder, hash-guarded publish, read-only source.
#   bash scripts/run_pipeline.sh            # plan -> build -> quantify -> publish -> validate -> renders -> gallery
set -euo pipefail
cd "$(dirname "$0")/.."
PY=.venv/Scripts/python
BL="/c/Program Files/Blender Foundation/Blender 5.2/blender.exe"
export BLENDER_USER_RESOURCES="$(cygpath -w "$LOCALAPPDATA/SouthgateBIM/blender_user")"
log() { echo "[$(date +%H:%M:%S)] $*"; }
log plan;      $PY scripts/migrate/plan_migration.py > work/plan/last_plan_stdout.json
log build;     $PY scripts/migrate/build_ifc.py --name full > work/build_full.log 2>&1
B=$(ls -d work/builds/*_full | tail -1)
log "quantify $B"; $PY scripts/export/extract_quantities.py --in "$B/southgate.ifc" --out "$B/southgate_qto.ifc"
CUR=NONE; [ -f bim/southgate.ifc ] && CUR=$(sha256sum bim/southgate.ifc | cut -d' ' -f1)
log "publish (replacing $CUR)"; $PY scripts/migrate/build_ifc.py --publish --expected-current-sha256 "$CUR"
log validate;  $PY -I scripts/validate/validate_ifc.py bim/southgate.ifc --out reports/audits/ifc_validation.json > work/validate.log 2>&1
log "stale check"; $PY scripts/export/extract_quantities.py --in bim/southgate.ifc --check > work/stale_check.json || true
log render-inputs; $PY scripts/export/export_render_inputs.py
log render-source; "$BL" -b --factory-startup source/snapshot/southgate_source_snapshot_20261107.blend --python-exit-code 1 --python scripts/export/render_views.py -- --mode source --out renders/comparisons --root "$(pwd -W)" > work/render_source.log 2>&1
log render-ifc; "$BL" -b --python-exit-code 1 --python scripts/export/render_views.py -- --mode ifc --ifc "$(pwd -W)/bim/southgate.ifc" --out renders/comparisons --root "$(pwd -W)" > work/render_ifc.log 2>&1
log gallery;   $PY scripts/export/make_gallery.py > work/gallery.log
log done
