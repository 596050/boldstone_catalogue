"""Verifies fcntl LOCK_EX semantics — the P0 fix for the watcher race.

Without the lock, the auto_collect_watcher running every 5 min would race
manual fleet collect invocations. With LOCK_EX held by the mutator, the
second mutator must wait (or time out).
"""
import multiprocessing
import time

import pytest

from fleet.state import mutate_state, load_state, save_state, StateError


def _hold_lock_for_seconds(fleet_dir_path, seconds, acquired_event=None):
    """Worker: opens an EXCLUSIVE mutator and holds it for ``seconds``.

    Signals ``acquired_event`` (if given) AFTER the lock is actually held, so
    the parent can wait for real acquisition instead of guessing with a sleep.
    """
    import os
    os.environ["FLEET_DIR"] = str(fleet_dir_path)
    import importlib, fleet.state
    importlib.reload(fleet.state)
    with fleet.state.mutate_state() as state:
        state["jobs"].append({"id": 999, "host": "test", "status": "running"})
        if acquired_event is not None:
            acquired_event.set()  # lock is now held — safe for the parent to race it
        time.sleep(seconds)


def test_lock_blocks_concurrent_mutator(isolated_fleet_dir):
    """Process A holds LOCK_EX; process B's mutate_state() with a short
    timeout must raise StateError."""
    fleet_dir = isolated_fleet_dir
    save_state({"jobs": []})

    # Hold the lock for a generous window and signal the parent the instant it
    # is acquired. macOS spawn-multiprocessing + importlib.reload can take well
    # over the old fixed 0.3s "let holder acquire" sleep under CPU load, which
    # made this test flaky (parent acquired uncontended -> DID NOT RAISE). The
    # event makes acquisition deterministic regardless of load.
    acquired = multiprocessing.Event()
    holder = multiprocessing.Process(target=_hold_lock_for_seconds,
                                     args=(fleet_dir, 3.0, acquired))
    holder.start()
    assert acquired.wait(timeout=15.0), "holder process failed to acquire the lock"

    try:
        # The holder definitely holds the lock now, so our mutator must time out.
        with pytest.raises(StateError, match="could not acquire state.lock"):
            with mutate_state(timeout_sec=0.5) as state:
                state["jobs"].append({"id": 1, "host": "x", "status": "running"})
    finally:
        holder.join(timeout=10.0)


def _worker_append_id(fleet_dir_path, jid):
    """Module-level worker (must be picklable for multiprocessing spawn on macOS)."""
    import os, time
    os.environ["FLEET_DIR"] = str(fleet_dir_path)
    from fleet.state import mutate_state
    with mutate_state(timeout_sec=5.0) as state:
        state["jobs"].append({"id": jid, "host": f"h{jid}", "status": "running"})


def test_concurrent_mutators_serialize(isolated_fleet_dir):
    """Two processes each appending one job — both must succeed (given enough
    timeout) and final state must contain BOTH jobs (no lost update under
    the lock)."""
    save_state({"jobs": []})

    p1 = multiprocessing.Process(target=_worker_append_id,
                                 args=(isolated_fleet_dir, 1))
    p2 = multiprocessing.Process(target=_worker_append_id,
                                 args=(isolated_fleet_dir, 2))
    p1.start()
    p2.start()
    p1.join(timeout=10.0)
    p2.join(timeout=10.0)

    final = load_state()
    ids = sorted(j["id"] for j in final["jobs"])
    assert ids == [1, 2], f"lost update: final ids={ids}"


def test_lock_released_on_exception(isolated_fleet_dir):
    """If the with-block raises, the mutator must (a) NOT save the partial
    mutation (transactional rollback) and (b) release the lock so the next
    mutator can acquire it."""
    save_state({"jobs": []})

    class _Boom(Exception):
        pass

    # First mutator raises mid-block
    try:
        with mutate_state() as state:
            state["jobs"].append({"id": 1, "host": "x", "status": "running"})
            raise _Boom("simulated error inside mutator")
    except _Boom:
        pass

    # Partial mutation was rolled back (job 1 NOT saved)
    assert load_state() == {"jobs": []}, "exception must roll back partial mutation"

    # Lock was released, so a second mutator can acquire it without blocking
    with mutate_state(timeout_sec=2.0) as state:
        state["jobs"].append({"id": 2, "host": "y", "status": "running"})
    assert [j["id"] for j in load_state()["jobs"]] == [2]
