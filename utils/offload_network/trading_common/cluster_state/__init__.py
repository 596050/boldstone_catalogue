"""cluster_state — track in-flight work + recover from common failures.

Sibling to ``trading_common.data_storage``. While data_storage governs the
artifacts at rest on the external drive, cluster_state governs the WORK
producing them — what's running, where, with what dependencies, and what
to do when something diverges from expectation.

See ``TEMP_CURRENT_WORK.md`` (sections "Cluster State Tracking" and
"Self-Repair and Recovery") for the design.
"""
from .schema import Alert, JobEvent, Severity
from .ledger import append_event, append_alert, read_recent_alerts
from .reconcile import reconcile_once, detect_stale_running, detect_wrapper_dead
from .recover import (
    reclassify_running_jobs,
    reclassify_wrapper_state,
    disk_pressure_collect,
    chunks_cleanup_recover,
    recollect_delta,
    restore_source_dir,
    recover_summary,
    Recovery,
)

__all__ = [
    "Alert", "JobEvent", "Severity",
    "append_event", "append_alert", "read_recent_alerts",
    "reconcile_once", "detect_stale_running", "detect_wrapper_dead",
    "reclassify_running_jobs", "reclassify_wrapper_state",
    "disk_pressure_collect", "chunks_cleanup_recover",
    "recollect_delta", "restore_source_dir",
    "recover_summary", "Recovery",
]
