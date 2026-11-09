"""orchestrator — stateful catalog of work + artifacts across the cluster.

Sibling to ``trading_common.cluster_state``. While cluster_state is REACTIVE
(detect divergence, recover from failures), this is PROACTIVE: a persistent
record of every kind of work the cluster does and every data artifact those
work items produce or consume.

Design principles:
1. **Layer above existing systems, don't replace.** Reads ~/.fleet/state.json
   (fleet.py jobs), scripts/offload_orchestration/hosts.json (host inventory),
   and remote disk probes. Does NOT write to those files; only its own state.
2. **Append-only event log.** All state changes write to ``events.jsonl``
   first; the materialised view in ``workitems.json`` / ``artifacts.json`` is
   reconstructed from events on read. Crash-safe.
3. **JSON, not SQLite.** Matches existing patterns (state.json, alerts.jsonl)
   and avoids a new dependency. Indexing is in-memory at read time — fine for
   the cluster's scale (~5 hosts, ~100 work items, ~thousands of artifacts).
4. **Inventory probes are cached.** Cross-host disk scans are expensive
   (~minutes); cache for $TTL and refresh on demand.

Storage layout (under $HOME/.fleet/orchestrator/):
    events.jsonl          — append-only event log (every state mutation)
    workitems.json        — materialised view of WorkItem records
    artifacts.json        — materialised view of Artifact records
    inventory/<host>.json — per-host disk inventory snapshots
    snapshots/<ts>.json   — periodic full-state snapshots (for debugging)
"""
from .schema import (
    WorkItem, Artifact, Host, WorkType, WorkStatus, ArtifactType,
    StorageTier,
)
from .store import (
    OrchestratorStore, get_store,
    record_event, materialise_view,
)
from .inventory import (
    probe_host_inventory, refresh_inventory, load_inventory,
)
from .lineage import (
    artifacts_for_workitem, workitems_producing_artifact, trace_lineage,
)

__all__ = [
    "WorkItem", "Artifact", "Host", "WorkType", "WorkStatus",
    "ArtifactType", "StorageTier",
    "OrchestratorStore", "get_store", "record_event", "materialise_view",
    "probe_host_inventory", "refresh_inventory", "load_inventory",
    "artifacts_for_workitem", "workitems_producing_artifact", "trace_lineage",
]
