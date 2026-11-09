"""fleet/paths.py — env-driven external path resolution.

Eliminates the hardcoded /Volumes/Untitled/offload_data/ that bled across
fleet.py + offload_pipeline.sh. Single source of truth:

    FAMOUS_MODEL_DATA_ROOT (env var)  →  data_root()
        default: /Volumes/Untitled/offload_data

Layout after the 2026-06-05 external HDD reorg (see README_STRUCTURE.md on
the drive):

    DATA_ROOT/research_data/c_emd/window_replays/<cohort>/    ← cohorts go HERE now
    DATA_ROOT/live_data/c_emd/results/ig_trading/             ← live signals only
    DATA_ROOT/archive/                                        ← snapshots
    DATA_ROOT/quarantine/                                     ← failed/partial

The ``--into`` flag values map to:
    research_data  ← canonical (post-reorg)
    live_data      ← legacy alias, redirected to research_data (back-compat)
    external       ← legacy non-tracked path
"""
from __future__ import annotations

import os
import pathlib

DEFAULT_INTO = "research_data"
VALID_INTO = ("research_data", "live_data", "external")
STATE_ROOT_ENV = "FAMOUS_MODEL_STATE_ROOT"
FLEET_DIR_ENV = "FLEET_DIR"
FLEET_LOGS_ENV = "FLEET_LOGS"


def data_root() -> pathlib.Path:
    """Resolve the external HDD root via env (default = /Volumes/Untitled/offload_data)."""
    raw = (os.environ.get("FAMOUS_MODEL_DATA_ROOT")
           or os.environ.get("EXTERNAL_DRIVE")
           or "/Volumes/Untitled/offload_data")
    return pathlib.Path(raw)


def repo_root() -> pathlib.Path:
    """Path to the fleet-offload repo (this file lives at utils/offload_network/fleet/paths.py)."""
    return pathlib.Path(__file__).resolve().parents[3]


def scopes_root() -> pathlib.Path:
    """Root under this repo for local orchestration state."""
    return pathlib.Path(
        os.environ.get(STATE_ROOT_ENV, repo_root() / "states" / "scopes")
    )


def fleet_dir() -> pathlib.Path:
    """Directory that holds shared orchestration state (same role as ~/.fleet historically)."""
    return pathlib.Path(os.environ.get(FLEET_DIR_ENV, str(scopes_root())))


def fleet_state_file() -> pathlib.Path:
    """Absolute path to state.json."""
    return fleet_dir() / "state.json"


def fleet_state_lock_file() -> pathlib.Path:
    """Absolute path to state.lock."""
    return fleet_dir() / "state.lock"


def v2_bundles_root() -> pathlib.Path:
    """Default root for sealed-bundle outputs and batch state files."""
    return fleet_dir() / "v2_bundles"


def network_cache_path() -> pathlib.Path:
    """Absolute path for cached host reachability metadata."""
    return fleet_dir() / "network_cache.json"


def remote_state_audit_path() -> pathlib.Path:
    """Absolute path for remote_state_audit.py cache file."""
    return fleet_dir() / "remote_state_audit.json"


def fleet_logs_dir() -> pathlib.Path:
    """Absolute path for orchestration logs."""
    return pathlib.Path(os.environ.get(FLEET_LOGS_ENV, str(fleet_dir() / "logs")))


def op_journal_dir() -> pathlib.Path:
    """Absolute path for operation journals (resumable write/recover flow)."""
    return fleet_dir() / "op_journal"


def orchestrator_dir() -> pathlib.Path:
    """Absolute path for trading_common.orchestrator persistence."""
    return fleet_dir() / "orchestrator"


def external_base(into: str = DEFAULT_INTO) -> pathlib.Path:
    """Return the external base directory for a given --into flag value.

    ``research_data`` and ``live_data`` both resolve to the post-reorg
    canonical location (research_data/c_emd/window_replays/) so legacy
    state.json entries continue to find their destination.
    """
    root = data_root()
    if into in ("research_data", "live_data"):
        return root / "research_data" / "c_emd" / "window_replays"
    if into == "external":
        return root / "c_emd" / "results"
    raise ValueError(
        f"--into must be one of {VALID_INTO!r}, got {into!r}"
    )
