#!/usr/bin/env bash
set -euo pipefail
export PYTHONPATH=.

RUN_DIR="model_research/runs/retro_last_week_cutoff_v2_batch_20260607T165907Z_scanxeon"
BATCH="${RUN_DIR}/batch.json"
STATE="${RUN_DIR}/state.json"
OIL_STATE="model_research/runs/current_live_emd_cache_refresh_20260608T130000Z_oil_retry/state.json"

python3 -m scripts.offload_orchestration.v2 batch submit "$BATCH" --dry-run
python3 -m scripts.offload_orchestration.v2 batch prestage-cache-stage "$BATCH" --dry-run
python3 -m scripts.offload_orchestration.v2 batch resume "$BATCH" --state-file "$STATE" --dry-run
python3 -m scripts.offload_orchestration.v2 batch status "$STATE"
python3 -m scripts.offload_orchestration.v2 batch doctor "$STATE"
python3 -m scripts.offload_orchestration.v2 batch jobs "$STATE"
python3 -m scripts.offload_orchestration.v2 batch list --root states/scopes/v2_bundles/batches
python3 -m scripts.offload_orchestration.v2 batch rebuild-state "$BATCH" --state-file /tmp/rebuilt_state.json

python3 -m trading_common.cluster_state reconcile
python3 -m trading_common.cluster_state recover-stale --max-jobs 1
python3 -m trading_common.cluster_state recover-disk-pressure --host scan-new
python3 -m trading_common.cluster_state recover-delta 1
python3 -m trading_common.cluster_state recover-source --host cdec AA2_IQKollect
python3 -m trading_common.cluster_state alerts

python3 utils/offload_network/fleet.py status
python3 utils/offload_network/fleet.py jobs
python3 utils/offload_network/fleet.py ops --state done --all
python3 utils/offload_network/fleet.py clean cdec --age 365d
python3 utils/offload_network/fleet.py rollup-summary 1 || true
