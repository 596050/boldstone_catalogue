"""fleet — staged refactor of the legacy utils/offload_network/fleet.py.

The legacy fleet.py (~1100 lines) bundles every subcommand into one module.
This package is a P0/P1 refactor that incrementally pulls out:

  - state.py    : atomic ~/.fleet/state.json IO with fcntl lockfile
                  + schema validation (FleetJob dataclass + validate())
  - paths.py    : env-driven external path resolution (no hardcoded /Volumes/...)
  - commands/   : per-subcommand modules (planned: status, sync, run_job,
                  collect, kill, clean, rollup_summary)

INVARIANT: while this refactor is in flight, the legacy fleet.py must stay
working. New modules here are additive; nothing in fleet.py is touched until
each command has parity tests in tests/. Once a command is moved, fleet.py
will be reduced to a thin shim that imports from this package.
"""
from .state import (
    FleetJob, FleetState,
    load_state, save_state, mutate_state,
    validate_state, StateError,
    WorkStatus,
)
from .paths import (
    data_root, external_base, repo_root,
    DEFAULT_INTO, VALID_INTO,
    scopes_root, fleet_dir, fleet_state_file, fleet_state_lock_file,
    v2_bundles_root, network_cache_path, remote_state_audit_path,
    fleet_logs_dir, op_journal_dir, orchestrator_dir,
)

__all__ = [
    "FleetJob", "FleetState",
    "load_state", "save_state", "mutate_state",
    "validate_state", "StateError",
    "WorkStatus",
    "data_root", "external_base", "repo_root",
    "DEFAULT_INTO", "VALID_INTO",
    "scopes_root", "fleet_dir", "fleet_state_file", "fleet_state_lock_file",
    "v2_bundles_root", "network_cache_path", "remote_state_audit_path",
    "fleet_logs_dir", "op_journal_dir", "orchestrator_dir",
]
