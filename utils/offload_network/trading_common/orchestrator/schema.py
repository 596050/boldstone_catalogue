"""Dataclasses for the orchestrator catalog.

Three core entities (WorkItem, Artifact, Host) + enums for the categorical
fields. dataclasses (NOT slotted, Py3.9 compat) so they JSON-serialise via
dataclasses.asdict().
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional


class WorkType(str, Enum):
    """Every kind of work the cluster does."""
    PIPELINE_RUN     = "pipeline_run"     # random_windows_pipeline produces .mat files
    COLLECT          = "collect"          # rsync remote outputs → external HDD
    SYNC             = "sync"             # rsync local repo → remote host
    MIGRATION        = "migration"        # rsync remote workspace → archive then delete
    BUILD            = "build"            # compile libemd / install toolchain
    DOWNLOAD         = "download"         # IQFeed historical pull
    REPLAY           = "replay"           # cache_replay_experiments.py against existing .mat
    VALIDATION       = "validation"       # paper-trade / cross-cohort audit
    CLEANUP          = "cleanup"          # chunks / temp / stale dirs delete
    DISK_RECOVER     = "disk_recover"     # cluster_state.recover.disk_pressure
    UNKNOWN          = "unknown"


# P3 fix from REFACTOR_PLAN.md (2026-06-05 round 3): unify WorkStatus with
# the canonical fleet.state.WorkStatus so the orchestrator catalog can
# import live state.json records without crashing on statuses unique to
# the fleet side (e.g. WRAPPER_DEAD_PIPELINE_UNKNOWN, KILLED).
#
# fleet.state is the source of truth — it owns ~/.fleet/state.json + the
# lockfile and is the only place a NEW status can be added without
# silently breaking downstream consumers.
import pathlib as _pathlib
import sys as _sys
_OFFLOAD_DIR = _pathlib.Path(__file__).resolve().parents[2]
if str(_OFFLOAD_DIR) not in _sys.path:
    _sys.path.insert(0, str(_OFFLOAD_DIR))
from fleet.state import WorkStatus  # noqa: E402, F401  (re-export)


class ArtifactType(str, Enum):
    """Every kind of data the cluster owns."""
    SOURCE_DATA       = "source_data"        # AA2_IQKollect, *_UOA-EMD, raw IQFeed downloads
    COHORT_OUTPUT     = "cohort_output"      # random_windows_*/  containing .mat files
    MAT_FILE          = "mat_file"           # individual per-window .mat
    LOG               = "log"                # pipeline logs, scheduled-task logs
    SUMMARY           = "summary"            # summary.json, summary_batch*.json
    ARCHIVE_SNAPSHOT  = "archive_snapshot"   # offload-XXX, validation-XXX preserved snapshots
    SCRATCH           = "scratch"            # *_chunks/, .rsync-partial/ — safe to delete
    REPO_CLONE        = "repo_clone"         # fleet-offload/ code tree on a remote
    CACHE_REPLAY      = "cache_replay"       # c_emd/results/ig_trading/cache_replay/*
    UNKNOWN           = "unknown"


class StorageTier(str, Enum):
    """Where the artifact physically lives."""
    HOT_REMOTE   = "hot_remote"     # on a producer's local disk (kenne, cdec, scan-xeon, scan-new)
    HOT_LOCAL    = "hot_local"      # on Mac (orchestrator) — usually code, state, logs
    WARM_EXT     = "warm_ext"       # external HDD live_data/ tree
    ARCHIVE_EXT  = "archive_ext"    # external HDD archive/ tree
    GONE         = "gone"           # known to have existed, since deleted


@dataclass
class Host:
    """A machine in the cluster. Mostly derived from hosts.json but extended
    with observable state."""
    alias: str
    ssh_alias: str
    user: str
    repo_path: str                              # e.g. C:/Users/Kenneth/Downloads/fleet-offload
    type: str = "ssh"                           # 'ssh' | 'local'
    has_libemd: bool = False
    has_iqfeed: bool = False
    cores: int = 0
    ram_gb: float = 0.0
    # observed at last probe
    last_probe_at: Optional[str] = None
    cpu_pct: float = 0.0
    disk_free_gb: float = 0.0
    proc_count: int = 0
    status: str = "unknown"                     # 'active' | 'pending-tailscale' | 'unreachable'

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class WorkItem:
    """A unit of work — a pipeline run, a collect, a migration, anything that
    the cluster does. Maps roughly 1:1 to a row in ~/.fleet/state.json plus
    other event sources (auto_collect_watcher cycles, migrations, builds).
    """
    id: str                                     # globally unique (e.g. 'pipeline_run-26' or 'migration-kenne-offload20260601')
    work_type: WorkType
    host: str                                   # alias of executing host
    status: WorkStatus
    created_at: str                             # ISO8601
    cohort: Optional[str] = None                # for pipeline_run / collect
    fleet_job_id: Optional[int] = None          # link back to state.json job
    parent_id: Optional[str] = None             # for chains (collect chains, migration batches)
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    command: Optional[str] = None               # the actual command/wrapper invoked
    inputs: list = field(default_factory=list)  # list of artifact ids consumed
    outputs: list = field(default_factory=list) # list of artifact ids produced
    retry_count: int = 0
    last_error: Optional[str] = None
    notes: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        d["work_type"] = self.work_type.value
        d["status"] = self.status.value
        return d


@dataclass
class Artifact:
    """A piece of data on disk somewhere. Source data, pipeline output,
    archive snapshot, log file, etc."""
    id: str                                     # globally unique (e.g. 'cohort:random_windows_bonds_dxy_nk_seed200_20260603')
    artifact_type: ArtifactType
    storage_tier: StorageTier
    host: Optional[str]                         # which host (or 'external' for HDD)
    path: str                                   # full path on host
    size_bytes: int = 0
    file_count: int = 0
    cohort_name: Optional[str] = None           # for COHORT_OUTPUT
    produced_by: Optional[str] = None           # workitem id that produced it
    last_observed_at: Optional[str] = None
    notes: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        d["artifact_type"] = self.artifact_type.value
        d["storage_tier"] = self.storage_tier.value
        return d


@dataclass
class Event:
    """An append-only record of a state change."""
    ts: str
    kind: str                                   # 'workitem_created' | 'workitem_status_change' | 'artifact_observed' | 'artifact_deleted' | ...
    payload: dict

    def to_dict(self) -> dict:
        return asdict(self)
