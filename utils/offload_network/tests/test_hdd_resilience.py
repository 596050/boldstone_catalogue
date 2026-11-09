"""Tests for the 2026-06-06 HDD resilience layer:
  lib/hdd_health.py — pre-flight probe (mount, write, space, UUID)
  lib/op_journal.py — durable per-operation journal

These cover the failure modes the user explicitly asked for:
  "ensure any interactions with the external hard drive are highly
   resilient to failures and can recover and keep state of what is
   happening and how to repair and resume"
"""
from __future__ import annotations

import json
import pathlib
import sys
import time

import pytest

_HERE = pathlib.Path(__file__).resolve().parent.parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from lib import hdd_health
from lib import op_journal


# ---- hdd_health -----------------------------------------------------------

def test_probe_missing_mount(tmp_path, monkeypatch):
    """A nonexistent mount point → not mounted, not ok."""
    hdd_health.invalidate_cache()
    fake = tmp_path / "nope" / "does" / "not" / "exist"
    r = hdd_health.probe_hdd(mount=fake, force=True)
    assert r["mounted"] is False
    assert r["ok"] is False
    assert any("does not exist" in e for e in r["errors"])


def test_probe_existing_dir(tmp_path):
    """A real local dir IS mounted + writable + has free space."""
    hdd_health.invalidate_cache()
    monkey_sentinel = tmp_path / ".probe"
    import lib.hdd_health as h
    h._SENTINEL_DIR = monkey_sentinel  # redirect probe writes here
    r = h.probe_hdd(mount=tmp_path, force=True)
    assert r["mounted"]
    assert r["writable"] is True
    assert r["free_bytes"] > 0
    assert r["ok"]


def test_probe_caches_results(tmp_path, monkeypatch):
    """Two probes within TTL_S return identical dicts (cached)."""
    hdd_health.invalidate_cache()
    monkeypatch.setattr(hdd_health, "_SENTINEL_DIR", tmp_path / ".probe")
    r1 = hdd_health.probe_hdd(mount=tmp_path, force=True)
    r2 = hdd_health.probe_hdd(mount=tmp_path)
    assert r1["checked_at"] == r2["checked_at"], "second call should hit cache"


def test_probe_invalidate(tmp_path, monkeypatch):
    hdd_health.invalidate_cache()
    monkeypatch.setattr(hdd_health, "_SENTINEL_DIR", tmp_path / ".probe")
    r1 = hdd_health.probe_hdd(mount=tmp_path, force=True)
    hdd_health.invalidate_cache()
    r2 = hdd_health.probe_hdd(mount=tmp_path)
    assert r2["checked_at"] >= r1["checked_at"]


def test_require_hdd_raises_on_missing(tmp_path):
    hdd_health.invalidate_cache()
    fake = tmp_path / "missing"
    with pytest.raises(hdd_health.HDDError):
        hdd_health.require_hdd(mount=fake)


def test_require_hdd_passes_on_existing(tmp_path, monkeypatch):
    hdd_health.invalidate_cache()
    monkeypatch.setattr(hdd_health, "_SENTINEL_DIR", tmp_path / ".probe")
    r = hdd_health.require_hdd(mount=tmp_path)
    assert r["ok"]


def test_required_free_bytes_enforced(tmp_path, monkeypatch):
    """A huge required_free_bytes triggers an error."""
    hdd_health.invalidate_cache()
    monkeypatch.setattr(hdd_health, "_SENTINEL_DIR", tmp_path / ".probe")
    # Pass an absurdly large requirement
    r = hdd_health.probe_hdd(mount=tmp_path,
                              required_free_bytes=10**18,  # 1 EB
                              force=True)
    assert not r["ok"]
    assert any("insufficient" in e for e in r["errors"])


def test_wait_for_mount_succeeds_immediately(tmp_path, monkeypatch):
    monkeypatch.setattr(hdd_health, "_SENTINEL_DIR", tmp_path / ".probe")
    hdd_health.invalidate_cache()
    ok = hdd_health.wait_for_mount(mount=tmp_path, timeout_s=2, poll_s=0.2)
    assert ok


def test_wait_for_mount_times_out(tmp_path):
    hdd_health.invalidate_cache()
    fake = tmp_path / "still_not_there"
    t0 = time.time()
    ok = hdd_health.wait_for_mount(mount=fake, timeout_s=1, poll_s=0.2)
    elapsed = time.time() - t0
    assert not ok
    assert elapsed >= 0.8


# ---- op_journal -----------------------------------------------------------

@pytest.fixture()
def journal(tmp_path, monkeypatch):
    """Redirect JOURNAL_DIR to a fresh tmp dir per test."""
    monkeypatch.setattr(op_journal, "JOURNAL_DIR", tmp_path / "op_journal")
    return op_journal


def test_journal_lifecycle(journal):
    op_id = journal.start_op("collect", job_id="42", host="kenne",
                              source="kenne:C:/foo", dest="/Volumes/.../foo",
                              expected_bytes=1_000_000)
    rec = journal.get_op(op_id)
    assert rec.state == "planned"
    assert rec.host == "kenne"
    journal.update_op(op_id, state="copying", progress_bytes=500_000)
    assert journal.get_op(op_id).state == "copying"
    journal.finish_op(op_id, state="done")
    assert journal.get_op(op_id).state == "done"


def test_list_incomplete_filters(journal):
    a = journal.start_op("collect", job_id="1", host="h", source="s", dest="d")
    b = journal.start_op("collect", job_id="2", host="h", source="s", dest="d")
    journal.finish_op(b, state="done")
    incomplete = journal.list_incomplete()
    assert len(incomplete) == 1
    assert incomplete[0].op_id == a


def test_journal_terminal_states_block_re_finish(journal):
    op_id = journal.start_op("collect", job_id="1", host="h",
                              source="s", dest="d")
    journal.finish_op(op_id, state="failed", error="rsync rc=23")
    with pytest.raises(ValueError):
        journal.finish_op(op_id, state="planned")


def test_journal_corruption_doesnt_break_list(journal, tmp_path):
    """A corrupt JSON file in the dir surfaces as an entry, not a crash."""
    a = journal.start_op("collect", job_id="1", host="h", source="s", dest="d")
    # Inject a bad file
    bad = journal.JOURNAL_DIR / "broken.json"
    bad.write_text("{not valid json")
    out = journal.list_incomplete()
    assert any(r.op_id == "broken" for r in out)
    assert any(r.op_id == a for r in out)


def test_journal_attempts_appended(journal):
    op_id = journal.start_op("collect", job_id="1", host="h",
                              source="s", dest="d")
    journal.update_op(op_id,
                       attempt={"ts": "t0", "action": "rsync", "rc": 23, "note": "transient"})
    journal.update_op(op_id,
                       attempt={"ts": "t1", "action": "rsync", "rc": 0, "note": "ok"})
    rec = journal.get_op(op_id)
    assert len(rec.attempts) == 2
    assert rec.attempts[0]["rc"] == 23
    assert rec.attempts[1]["rc"] == 0


def test_journal_unknown_state_rejected(journal):
    op_id = journal.start_op("collect", job_id="1", host="h",
                              source="s", dest="d")
    with pytest.raises(ValueError):
        journal.update_op(op_id, state="not_a_real_state")


def test_journal_context_manager_success(journal):
    """journal_op context manager auto-finishes on clean exit."""
    captured: list[str] = []
    with journal.journal_op("collect", job_id="1", host="h",
                             source="s", dest="d") as op_id:
        captured.append(op_id)
    rec = journal.get_op(captured[0])
    assert rec.state == "done"


def test_journal_context_manager_exception_marks_failed(journal):
    """journal_op context manager marks failed on exception."""
    with pytest.raises(RuntimeError):
        with journal.journal_op("collect", job_id="1", host="h",
                                 source="s", dest="d") as op_id:
            captured_id = op_id
            raise RuntimeError("boom")
    rec = journal.get_op(captured_id)
    assert rec.state == "failed"
    assert "boom" in (rec.last_error or "")


def test_journal_purge_old(journal, tmp_path):
    """purge_old removes only terminal entries past the cutoff."""
    a = journal.start_op("collect", job_id="1", host="h", source="s", dest="d")
    journal.finish_op(a, state="done")
    b = journal.start_op("collect", job_id="2", host="h", source="s", dest="d")
    # Make a's file appear ancient
    a_path = journal.JOURNAL_DIR / f"{a}.json"
    import os
    old_t = time.time() - 999 * 86400
    os.utime(a_path, (old_t, old_t))
    n = journal.purge_old(max_age_days=30)
    assert n == 1
    assert not a_path.exists()
    # b is non-terminal — should NEVER be purged
    assert journal.get_op(b) is not None
