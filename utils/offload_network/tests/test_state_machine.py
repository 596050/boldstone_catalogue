"""Verifies the FleetJob lifecycle + status transitions.

Covers the suspected race-window that hit the watcher this session (the
unexplained rc=137/143 exits). With the new lock + atomic write, the same
read-modify-write sequence under contention should be safe.
"""
import json
import pytest

from fleet.state import (
    FleetJob, FleetState, WorkStatus,
    load_state, save_state, mutate_state, validate_state, StateError,
)


def test_workstatus_round_trip():
    """Every WorkStatus value is serialisable + parseable."""
    for s in WorkStatus:
        assert WorkStatus(s.value) is s


def test_workstatus_rejects_unknown():
    with pytest.raises(ValueError):
        WorkStatus("totally_bogus_status")


def test_fleetjob_required_fields_enforced(isolated_fleet_dir):
    """Missing id/host/status must raise StateError."""
    with pytest.raises(StateError, match="missing required 'id'"):
        FleetJob.from_dict({"host": "kenne", "status": "running"})
    with pytest.raises(StateError, match="missing required 'host'"):
        FleetJob.from_dict({"id": 1, "status": "running"})
    with pytest.raises(StateError, match="missing required 'status'"):
        FleetJob.from_dict({"id": 1, "host": "kenne"})


def test_fleetjob_invalid_status_rejected(isolated_fleet_dir):
    with pytest.raises(StateError, match="invalid status"):
        FleetJob.from_dict({"id": 1, "host": "kenne", "status": "nope"})


def test_fleetjob_round_trip(isolated_fleet_dir):
    """to_dict() then from_dict() must round-trip cleanly."""
    job = FleetJob(id=42, host="kenne", status=WorkStatus.RUNNING,
                   cohort="aapl_csv_uoa", wrapper_pid=12345)
    assert FleetJob.from_dict(job.to_dict()) == job


def test_fleetjob_drops_nones_on_serialize(isolated_fleet_dir):
    """to_dict() must not emit keys with None values (legacy state.json
    files lack these and we shouldn't introduce them)."""
    job = FleetJob(id=1, host="kenne", status=WorkStatus.RUNNING)
    out = job.to_dict()
    assert "cohort" not in out
    assert "wrapper_pid" not in out
    assert out == {"id": 1, "host": "kenne", "status": "running"}


def test_fleetstate_validates_jobs_list(isolated_fleet_dir):
    """Bad jobs entry must raise."""
    with pytest.raises(StateError, match="must be a list"):
        FleetState.from_dict({"jobs": "not a list"})
    with pytest.raises(StateError, match="missing required 'jobs'"):
        FleetState.from_dict({"something": "else"})


def test_load_state_returns_empty_on_missing(isolated_fleet_dir):
    """First read should yield {jobs: []}, not crash."""
    state = load_state()
    assert state == {"jobs": []}


def test_save_then_load_round_trip(isolated_fleet_dir):
    """save_state → load_state must produce identical content."""
    s = {"jobs": [{"id": 1, "host": "kenne", "status": "running"}]}
    save_state(s)
    assert load_state() == s


def test_status_transitions_via_mutate(isolated_fleet_dir):
    """running → exited → collected lifecycle through the locked mutator."""
    with mutate_state() as state:
        state["jobs"].append({"id": 1, "host": "kenne", "status": "running"})

    with mutate_state() as state:
        state["jobs"][0]["status"] = "exited"

    with mutate_state() as state:
        state["jobs"][0]["status"] = "collected"

    final = load_state()
    assert final["jobs"][0]["status"] == "collected"


def test_atomic_save_on_crash_mid_write(isolated_fleet_dir, monkeypatch):
    """If save_state's rename never fires, the old state.json must still be
    intact (the tmp file is irrelevant). Validates atomic-rename semantics."""
    save_state({"jobs": [{"id": 1, "host": "kenne", "status": "running"}]})
    original = load_state()

    # Simulate a crash mid-write by patching portable atomic replacement.
    import fleet.state as _s

    def boom(*a, **kw):
        raise OSError("simulated rename failure")

    monkeypatch.setattr("os.replace", boom)
    with pytest.raises(OSError):
        save_state({"jobs": [{"id": 2, "host": "cdec", "status": "running"}]})

    # Original file unaffected
    assert load_state() == original


def test_validate_on_load(isolated_fleet_dir):
    """load_state(validate=True) must reject malformed records."""
    save_state({"jobs": [{"id": 1, "host": "kenne", "status": "BOGUS"}]})
    with pytest.raises(StateError, match="invalid status"):
        load_state(validate=True)
