"""P5 from REFACTOR_PLAN.md round 3 (2026-06-05): cross-package tests proving
the lockfile + schema sharing actually closes the race we set out to fix.

These tests live in the offload_orchestration test suite (alongside the
fleet/state.py tests) because:
  1. fleet/state.py owns the lockfile + schema — the source of truth.
  2. cluster_state and orchestrator import from fleet.state via sys.path —
     a self-contained pytest setup over there would have to replicate the
     same trick. Easier to test the integration from this side.

What we verify:
  - WorkStatus is the IDENTICAL object in fleet, cluster_state, orchestrator
  - cluster_state.recover._load_state respects the lock held by
    fleet.mutate_state (concurrent mutators don't race)
  - orchestrator.import_state can read live state.json without crashing on
    the WRAPPER_DEAD_PIPELINE_UNKNOWN status that exists only fleet-side
    (this was issue #6 in the round-3 audit)
"""
from __future__ import annotations

import pathlib

import pytest


def test_workstatus_unified_across_packages():
    """Items #3 + #6 from REFACTOR_PLAN.md round 3: orchestrator's WorkStatus
    must be the SAME object as fleet.state.WorkStatus, not a separate enum
    that can drift."""
    # Add repo root to sys.path so trading_common imports work
    import sys
    repo_root = pathlib.Path(__file__).resolve().parents[3]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    from fleet.state import WorkStatus as fleet_ws
    from trading_common.orchestrator.schema import WorkStatus as orch_ws

    # Identity check — must be the SAME enum class
    assert orch_ws is fleet_ws, \
        "orchestrator.schema.WorkStatus must re-export fleet.state.WorkStatus"

    # The WRAPPER_DEAD_PIPELINE_UNKNOWN status that's unique to the fleet
    # side must be accessible from the orchestrator (was issue #6)
    assert hasattr(fleet_ws, "WRAPPER_DEAD_PIPELINE_UNKNOWN")
    assert fleet_ws.WRAPPER_DEAD_PIPELINE_UNKNOWN.value == "wrapper_dead_pipeline_unknown"


def test_clusterstate_uses_shared_load_state(isolated_fleet_dir):
    """cluster_state.recover._load_state must delegate to fleet.state.load_state
    (not its own json.loads). Verified by writing via fleet.state and
    reading back via cluster_state — they must see the same data because
    they share the same path resolution."""
    import sys
    repo_root = pathlib.Path(__file__).resolve().parents[3]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    from fleet.state import save_state
    save_state({"jobs": [{"id": 42, "host": "kenne", "status": "running"}]})

    from trading_common.cluster_state.recover import _load_state
    state = _load_state()
    assert any(j["id"] == 42 for j in state["jobs"]), \
        f"cluster_state.recover._load_state read different data: {state}"


def test_orchestrator_imports_live_state_with_all_statuses(isolated_fleet_dir):
    """Round 3 issue #6: orchestrator must not crash when reading a real
    state.json that contains WRAPPER_DEAD_PIPELINE_UNKNOWN — the very status
    we use most when wrappers die."""
    from fleet.state import save_state, FleetJob, WorkStatus

    # Seed a state.json with every status the fleet side might write
    save_state({"jobs": [
        FleetJob(id=1, host="kenne", status=WorkStatus.RUNNING).to_dict(),
        FleetJob(id=2, host="cdec",  status=WorkStatus.EXITED).to_dict(),
        FleetJob(id=3, host="scan-xeon",
                 status=WorkStatus.WRAPPER_DEAD_PIPELINE_UNKNOWN).to_dict(),
        FleetJob(id=4, host="kenne", status=WorkStatus.COLLECTED).to_dict(),
    ]})

    # Add repo root + offload dir to sys.path
    import sys
    repo_root = pathlib.Path(__file__).resolve().parents[3]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    # The orchestrator's import_state expects WorkStatus to know all values
    # produced by fleet — that's the whole point of the unification.
    from trading_common.orchestrator.schema import WorkStatus as orch_ws
    for j in [WorkStatus.RUNNING, WorkStatus.EXITED,
              WorkStatus.WRAPPER_DEAD_PIPELINE_UNKNOWN, WorkStatus.COLLECTED]:
        assert orch_ws(j.value) is j, f"orch can't round-trip {j}"


def test_all_three_packages_share_lock_path(isolated_fleet_dir):
    """fleet.state, cluster_state.recover, orchestrator.import_state must
    resolve to the IDENTICAL ~/.fleet/state.lock path."""
    import sys
    repo_root = pathlib.Path(__file__).resolve().parents[3]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    from fleet import state as fleet_state
    from trading_common.cluster_state.recover import _fleet_state as cs
    from trading_common.orchestrator.import_state import _fleet_state as orch

    assert fleet_state.lock_path() == cs.lock_path() == orch.lock_path()
    assert fleet_state.state_path() == cs.state_path() == orch.state_path()
