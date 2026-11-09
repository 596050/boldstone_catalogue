"""Bootstrap the orchestrator catalog from existing ~/.fleet/state.json.

The fleet.py-managed job state is the authoritative record of pipeline_run
and collect work items. This module reads state.json once and emits the
corresponding workitem_create + workitem_status + artifact_observe events
so the orchestrator catalog is initialised with everything fleet already
knows about.

Idempotent: each workitem id is deterministic (e.g. 'fleet-job-26'); replay
into a non-empty store will overwrite the latest status only.
"""
from __future__ import annotations

import datetime as _dt
import json
import pathlib

from .schema import WorkType, WorkStatus, ArtifactType, StorageTier
from .store import OrchestratorStore, get_store

# Priority 2 from REFACTOR_PLAN.md (2026-06-05): delegate state.json read
# to fleet/state.py so we share the LOCK_SH with fleet.py + watcher mutations
# and pick up schema-validated records consistently.
import sys as _sys
_REPO_ROOT_FOR_FLEET = pathlib.Path(__file__).resolve().parents[2]
_OFFLOAD_DIR = _REPO_ROOT_FOR_FLEET
if str(_OFFLOAD_DIR) not in _sys.path:
    _sys.path.insert(0, str(_OFFLOAD_DIR))
from fleet.paths import fleet_state_file
from fleet import state as _fleet_state  # noqa: E402


_STATUS_MAP = {
    "running":   WorkStatus.RUNNING,
    "exited":    WorkStatus.EXITED,
    "collected": WorkStatus.COLLECTED,
    "killed":    WorkStatus.CANCELLED,
    "failed":    WorkStatus.FAILED,
    "pending":   WorkStatus.PENDING,
}


def import_fleet_jobs(store: OrchestratorStore | None = None) -> dict:
    """Read ~/.fleet/state.json and emit workitem events."""
    store = store or get_store()
    if not fleet_state_file().exists():
        return {"imported": 0, "error": "state.json not found"}
    s = _fleet_state.load_state()
    count = 0
    for j in s.get("jobs", []):
        wid = f"fleet-job-{j['id']}"
        status = _STATUS_MAP.get(j.get("status", "unknown"), WorkStatus.PENDING)
        # The job is fundamentally a pipeline_run (random_windows_pipeline produces .mat)
        # Collect events are separate workitems we don't import here.
        store.submit_workitem(
            id=wid,
            work_type=WorkType.PIPELINE_RUN,
            host=j.get("host", "unknown"),
            cohort=j.get("cohort"),
            fleet_job_id=j["id"],
            command=" ".join([
                "fleet.py run-job", j.get("host", ""),
                j.get("cohort", ""),
                j.get("pipeline_args", "") or "",
            ]).strip(),
            notes=(j.get("notes") or "") or f"remote_out={j.get('remote_out','')}",
        )
        store.update_status(wid, status)
        # If a cohort dir was produced (status=exited/collected), record an artifact
        if status in (WorkStatus.EXITED, WorkStatus.COLLECTED) and j.get("remote_out"):
            base = (j["remote_out"] or "").rstrip("/\\").split("/")[-1].split("\\")[-1]
            tier = (StorageTier.WARM_EXT if status == WorkStatus.COLLECTED
                    else StorageTier.HOT_REMOTE)
            host_for_artifact = "external" if status == WorkStatus.COLLECTED else j.get("host", "unknown")
            store.observe_artifact(
                id=f"cohort:{base}@{host_for_artifact}",
                artifact_type=ArtifactType.COHORT_OUTPUT,
                storage_tier=tier,
                host=host_for_artifact,
                path=(j.get("external_dest") if status == WorkStatus.COLLECTED
                      else j["remote_out"]),
                cohort_name=base,
                produced_by=wid,
            )
        count += 1
    return {"imported": count, "error": None}
