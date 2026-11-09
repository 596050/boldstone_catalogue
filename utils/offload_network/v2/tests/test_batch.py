"""Unit tests for v2/batch.py — DAG executor with mocked submit.

Tests cover:
  - Topological order (later layers wait for earlier layers)
  - Host affinity (job with affinity=X lands on the same host X ran on)
  - Per-host parallelism cap (max_parallel_per_host)
  - Failure modes (skip_dependents vs stop_batch)
  - State persistence + resume after interruption
"""
from __future__ import annotations

import json
import pathlib
import sys
import tempfile
import threading
import time
import types
import unittest
from unittest import mock

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent))

from v2.spec import JobSpec, BatchSpec  # noqa: E402
from v2.batch import BatchExecutor, BatchState  # noqa: E402


# ---- helpers --------------------------------------------------------------

def _hosts() -> dict:
    return {
        "cdec":     {"type": "ssh", "ssh_alias": "cdec", "repo": "C:/u/cdec",
                     "rsync_path": "rsync", "has_libemd": True, "cores": 24},
        "scan-new": {"type": "ssh", "ssh_alias": "scan-new", "repo": "C:/u/scan",
                     "rsync_path": "rsync", "has_libemd": True, "cores": 128},
    }


def _job(name: str, *, deps=None, host_alias="cdec", affinity=None,
         exists_path: pathlib.Path = None, metadata=None) -> JobSpec:
    """Build a minimal JobSpec that the autobundler will accept."""
    bundle = []
    if exists_path is not None:
        bundle.append({"src": str(exists_path), "as": "code/x"})
    host_dict = {}
    if affinity:
        host_dict["affinity"] = affinity
    elif host_alias:
        host_dict["alias"] = host_alias
    d = {
        "name": name,
        "phase": "test",
        "host": host_dict,
        "entry": {"kind": "module", "path": "trading_common"},
        "args": [],
        "inputs": {"bundle": bundle, "remote_refs": []},
        "outputs": {"pull": []},
        "deps": deps or [],
        "metadata": metadata or {},
    }
    return JobSpec.from_dict(d)


def _batch(jobs, **policy_overrides) -> BatchSpec:
    bs = BatchSpec(
        batch="test_batch",
        jobs=jobs,
        roots={},
        policy={"max_parallel_per_host": 4, "max_parallel_total": 8,
                "on_failure": "skip_dependents", **policy_overrides},
    )
    bs.validate()
    return bs


class _SubmitRecorder:
    """Fake submit_fn that records call order + lets tests force outcomes."""
    def __init__(self):
        self.calls: list[tuple[str, str]] = []  # (job_name, host)
        self.lock = threading.Lock()
        # Map job_name → exit_code (default 0); set to non-zero for failures.
        self.exit_codes: dict[str, int] = {}
        # Per-host inflight counter to verify max_parallel_per_host
        self.inflight: dict[str, int] = {}
        self.max_inflight_per_host: dict[str, int] = {}
        # Optional delay (s) to make parallelism races observable
        self.delay_s: float = 0.0

    def __call__(self, manifest, bundle_dir):
        host = manifest.host.ssh_alias
        spec_name = manifest.metadata.get("spec_name", "?")
        with self.lock:
            self.calls.append((spec_name, host))
            self.inflight[host] = self.inflight.get(host, 0) + 1
            self.max_inflight_per_host[host] = max(
                self.max_inflight_per_host.get(host, 0), self.inflight[host]
            )
        if self.delay_s:
            time.sleep(self.delay_s)
        rc = self.exit_codes.get(spec_name, 0)
        with self.lock:
            self.inflight[host] -= 1
        return {
            "status": {
                "phase": "exited", "exit_code": rc,
                "error": None if rc == 0 else f"forced rc={rc}",
            },
            "result": {},
            "manifest": manifest,
        }


# ---- TESTS ----------------------------------------------------------------

class _FleetDirIsolation:
    """Mixin: redirect $FLEET_DIR to a tmpdir so tests don't clobber the
    user's real ~/.fleet/state.json. Mirrors the isolated_fleet_dir
    pytest fixture in tests/conftest.py but works for unittest.TestCase."""
    def _isolate_fleet_dir(self):
        import os
        self._isolated_fleet_dir = pathlib.Path(tempfile.mkdtemp(prefix="fl_"))
        self._saved_fleet_dir = os.environ.get("FLEET_DIR")
        os.environ["FLEET_DIR"] = str(self._isolated_fleet_dir)
        # Seed state.json with the default shape so fleet.load_state succeeds
        (self._isolated_fleet_dir / "state.json").write_text(
            json.dumps({"next_job_id": 1, "jobs": []})
        )

    def _restore_fleet_dir(self):
        import os
        if self._saved_fleet_dir is None:
            os.environ.pop("FLEET_DIR", None)
        else:
            os.environ["FLEET_DIR"] = self._saved_fleet_dir
        import shutil
        shutil.rmtree(self._isolated_fleet_dir, ignore_errors=True)


class TestBatchExecutorDispatch(_FleetDirIsolation, unittest.TestCase):
    def setUp(self):
        self._isolate_fleet_dir()
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix="batch_t_"))
        # Each test needs at least one existing path for the bundle entry
        self.fakebundle = self.tmp / "fake"
        self.fakebundle.mkdir()
        (self.fakebundle / "a.py").write_text("# fake\n")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)
        self._restore_fleet_dir()

    def _exec(self, batch_spec: BatchSpec, **kw) -> tuple[BatchExecutor, _SubmitRecorder]:
        rec = _SubmitRecorder()
        ex = BatchExecutor(
            batch_spec, _hosts(),
            state_path=self.tmp / "state.json",
            bundle_out_root=self.tmp / "bundles",
            submit_fn=rec, **kw,
        )
        return ex, rec

    def test_two_jobs_no_deps_run_in_parallel(self):
        a = _job("a", exists_path=self.fakebundle)
        b = _job("b", exists_path=self.fakebundle)
        ex, rec = self._exec(_batch([a, b]))
        ex.run()
        # Both ran, both succeeded
        self.assertEqual(len(rec.calls), 2)
        self.assertEqual({n for n, _ in rec.calls}, {"a", "b"})
        self.assertEqual(ex.status_summary(), {"succeeded": 2})

    def test_diamond_topological_order(self):
        # a → b, a → c, b+c → d
        a = _job("a", exists_path=self.fakebundle)
        b = _job("b", deps=["a"], exists_path=self.fakebundle)
        c = _job("c", deps=["a"], exists_path=self.fakebundle)
        d = _job("d", deps=["b", "c"], exists_path=self.fakebundle)
        ex, rec = self._exec(_batch([a, b, c, d]))
        ex.run()
        # Verify "a" ran before "b"/"c"/"d", and "d" ran after "b"+"c"
        order = [n for n, _ in rec.calls]
        self.assertLess(order.index("a"), order.index("b"))
        self.assertLess(order.index("a"), order.index("c"))
        self.assertLess(order.index("b"), order.index("d"))
        self.assertLess(order.index("c"), order.index("d"))
        self.assertEqual(ex.status_summary(), {"succeeded": 4})

    def test_host_affinity_pins_to_upstream_host(self):
        a = _job("a", host_alias="scan-new", exists_path=self.fakebundle)
        # b has affinity to a, NOT an explicit host alias
        b = _job("b", deps=["a"], host_alias=None, affinity="a",
                 exists_path=self.fakebundle)
        ex, rec = self._exec(_batch([a, b]))
        ex.run()
        # Both calls happened on scan-new (b inherited from a)
        for name, host in rec.calls:
            self.assertEqual(host, "scan-new", f"{name} should have landed on scan-new")

    def test_max_parallel_per_host_throttle(self):
        # 5 jobs, all pinned to cdec, max_parallel_per_host=2 → max_inflight=2
        jobs = [_job(f"j{i}", host_alias="cdec",
                     exists_path=self.fakebundle) for i in range(5)]
        ex, rec = self._exec(_batch(jobs, max_parallel_per_host=2,
                                     max_parallel_total=8))
        rec.delay_s = 0.05  # give the throttle time to take effect
        ex.run()
        self.assertEqual(ex.status_summary(), {"succeeded": 5})
        self.assertLessEqual(rec.max_inflight_per_host["cdec"], 2,
                             f"max-per-host violated: {rec.max_inflight_per_host}")

    def test_skip_dependents_on_failure(self):
        a = _job("a", exists_path=self.fakebundle)
        b = _job("b", deps=["a"], exists_path=self.fakebundle)
        c = _job("c", deps=["b"], exists_path=self.fakebundle)
        ex, rec = self._exec(_batch([a, b, c]))
        rec.exit_codes["a"] = 1  # force a to fail
        ex.run()
        # a failed; b and c skipped because their upstream failed
        statuses = {n: ex.state.jobs[n].status for n in ("a", "b", "c")}
        self.assertEqual(statuses["a"], "failed")
        self.assertEqual(statuses["b"], "skipped")
        self.assertEqual(statuses["c"], "skipped")
        # rec.calls only contains a (b + c never got submitted)
        self.assertEqual({n for n, _ in rec.calls}, {"a"})

    def test_stop_batch_halts_all_subsequent_layers(self):
        a = _job("a", exists_path=self.fakebundle)
        b = _job("b", exists_path=self.fakebundle)  # parallel to a
        c = _job("c", deps=["a", "b"], exists_path=self.fakebundle)
        ex, rec = self._exec(_batch([a, b, c], on_failure="stop_batch"))
        rec.exit_codes["a"] = 5
        ex.run()
        # a failed; b may have succeeded (parallel); c skipped (layer 2 never started)
        self.assertEqual(ex.state.jobs["a"].status, "failed")
        self.assertEqual(ex.state.jobs["c"].status, "skipped")

    def test_dry_run_marks_all_succeeded_without_calling_submit(self):
        a = _job("a", exists_path=self.fakebundle)
        b = _job("b", deps=["a"], exists_path=self.fakebundle)
        ex, rec = self._exec(_batch([a, b]), dry_run=True)
        ex.run()
        self.assertEqual(len(rec.calls), 0)
        self.assertEqual(ex.status_summary(), {"succeeded": 2})

    def test_outputs_pull_keeps_workdir_and_direct_rsyncs_missing_archive_output(self):
        spec = JobSpec.from_dict({
            "name": "cache.oil",
            "phase": "cache",
            "host": {"alias": "cdec"},
            "entry": {"kind": "module", "path": "trading_common"},
            "args": [],
            "inputs": {
                "bundle": [{"src": str(self.fakebundle), "as": "code/x"}],
                "remote_refs": [],
            },
            "outputs": {
                "pull": [{"remote": "cache/oil_live_emd_cache.mat",
                          "to": str(self.tmp / "dest") + "/"}],
            },
            "deps": [],
            "metadata": {"phase_subkind": "cache_build"},
        })
        keeps = []

        def submit_ok(manifest, bundle_dir, *, keep_remote_workdir=False):
            keeps.append(keep_remote_workdir)
            return {"status": {"phase": "exited", "exit_code": 0}, "result": {}}

        ex = BatchExecutor(
            _batch([spec]), _hosts(),
            state_path=self.tmp / "state.json",
            bundle_out_root=self.tmp / "bundles",
            submit_fn=submit_ok,
        )
        def fake_pull_path(**kwargs):
            dst = pathlib.Path(kwargs["local_dest"]) / "oil_live_emd_cache.mat"
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(b"x" * 3)

        with mock.patch("v2.transport.pull_path", side_effect=fake_pull_path) as pull_path, \
             mock.patch("v2.transport.remote_file_size", return_value=3), \
             mock.patch("v2.transport.remote_remove"):
            ex.run()

        self.assertEqual(keeps, [True])
        self.assertEqual(ex.state.jobs["cache.oil"].status, "succeeded")
        self.assertFalse(ex.state.jobs["cache.oil"].kept_for_outputs)
        self.assertEqual(ex.state.jobs["cache.oil"].post_pull_errors, [])
        self.assertEqual(pull_path.call_count, 1)
        kwargs = pull_path.call_args.kwargs
        self.assertTrue(kwargs["remote_path"].endswith(
            "/outputs/cache/oil_live_emd_cache.mat"
        ))
        self.assertEqual(kwargs["local_dest"], self.tmp / "dest")


class TestBatchExecutorResume(_FleetDirIsolation, unittest.TestCase):
    def setUp(self):
        self._isolate_fleet_dir()
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix="batch_r_"))
        self.fakebundle = self.tmp / "fake"
        self.fakebundle.mkdir()
        (self.fakebundle / "a.py").write_text("# fake\n")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)
        self._restore_fleet_dir()

    def test_resume_skips_succeeded_and_reruns_interrupted(self):
        # First run: a fails (we want to retry it)
        a = _job("a", exists_path=self.fakebundle)
        b = _job("b", deps=["a"], exists_path=self.fakebundle)
        bs = _batch([a, b])
        rec1 = _SubmitRecorder()
        rec1.exit_codes["a"] = 1
        ex1 = BatchExecutor(
            bs, _hosts(),
            state_path=self.tmp / "state.json",
            bundle_out_root=self.tmp / "bundles",
            submit_fn=rec1,
        )
        ex1.run()
        self.assertEqual(ex1.state.jobs["a"].status, "failed")
        self.assertEqual(ex1.state.jobs["b"].status, "skipped")
        # Hand-edit state: pretend operator wants to retry a
        st = json.loads((self.tmp / "state.json").read_text())
        st["jobs"]["a"]["status"] = "interrupted"
        st["jobs"]["b"]["status"] = "pending"  # let it try again too
        (self.tmp / "state.json").write_text(json.dumps(st))
        # Second run: this time a succeeds → b should also run
        rec2 = _SubmitRecorder()
        ex2 = BatchExecutor(
            bs, _hosts(),
            state_path=self.tmp / "state.json",
            bundle_out_root=self.tmp / "bundles",
            submit_fn=rec2,
        )
        ex2.run()
        self.assertEqual({n: ex2.state.jobs[n].status for n in ("a", "b")},
                         {"a": "succeeded", "b": "succeeded"})
        # Both ran again (a was interrupted, b was pending)
        self.assertEqual({n for n, _ in rec2.calls}, {"a", "b"})
        # The interrupted attempt was rolled back so 'a' actually re-ran under
        # the max_attempts=1 (skip_dependents) budget: attempts reflects the
        # single successful resume attempt, not the prior (uncompleted) one.
        self.assertEqual(ex2.state.jobs["a"].attempts, 1)


class TestPerHostQuotaOverride(_FleetDirIsolation, unittest.TestCase):
    """Tests for policy.per_host_overrides giving specific hosts a
    higher/lower in-flight cap than the global max_parallel_per_host."""

    def setUp(self):
        self._isolate_fleet_dir()
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix="quota_t_"))
        self.fakebundle = self.tmp / "fake"
        self.fakebundle.mkdir()
        (self.fakebundle / "a.py").write_text("# fake\n")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)
        self._restore_fleet_dir()

    def test_per_host_override_caps_busy_host_lower(self):
        # 4 jobs pinned to "cdec" with override cap=1 should run sequentially
        # despite max_parallel_per_host=4. max_inflight on cdec must stay 1.
        jobs = [_job(f"j{i}", host_alias="cdec",
                     exists_path=self.fakebundle) for i in range(4)]
        bs = _batch(jobs, max_parallel_per_host=4, max_parallel_total=8,
                    per_host_overrides={"cdec": 1})
        rec = _SubmitRecorder()
        ex = BatchExecutor(
            bs, _hosts(),
            state_path=self.tmp / "state.json",
            bundle_out_root=self.tmp / "bundles",
            submit_fn=rec,
        )
        rec.delay_s = 0.05
        ex.run()
        self.assertEqual(ex.status_summary(), {"succeeded": 4})
        self.assertLessEqual(rec.max_inflight_per_host["cdec"], 1,
                             f"override violated: {rec.max_inflight_per_host}")

    def test_per_host_override_lets_specific_host_go_higher(self):
        # 6 jobs pinned to "cdec" with override cap=6 should run all at once
        # despite global max_parallel_per_host=2.
        jobs = [_job(f"j{i}", host_alias="cdec",
                     exists_path=self.fakebundle) for i in range(6)]
        bs = _batch(jobs, max_parallel_per_host=2, max_parallel_total=10,
                    per_host_overrides={"cdec": 6})
        rec = _SubmitRecorder()
        ex = BatchExecutor(
            bs, _hosts(),
            state_path=self.tmp / "state.json",
            bundle_out_root=self.tmp / "bundles",
            submit_fn=rec,
        )
        rec.delay_s = 0.1
        ex.run()
        self.assertEqual(rec.max_inflight_per_host["cdec"], 6,
                         f"expected cdec inflight=6, got {rec.max_inflight_per_host}")


class TestRetryPolicy(_FleetDirIsolation, unittest.TestCase):
    """Tests for policy.on_failure='retry_N' + retry_backoff_seconds."""

    def setUp(self):
        self._isolate_fleet_dir()
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix="retry_t_"))
        self.fakebundle = self.tmp / "fake"
        self.fakebundle.mkdir()
        (self.fakebundle / "a.py").write_text("# fake\n")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)
        self._restore_fleet_dir()

    def _exec(self, batch_spec, **kw):
        rec = _SubmitRecorder()
        ex = BatchExecutor(
            batch_spec, _hosts(),
            state_path=self.tmp / "state.json",
            bundle_out_root=self.tmp / "bundles",
            submit_fn=rec, **kw,
        )
        return ex, rec

    def test_retry_3_retries_until_success(self):
        """Failure on attempt 1, success on attempt 2 → final status=succeeded."""
        a = _job("a", exists_path=self.fakebundle)
        bs = _batch([a], on_failure="retry_3",
                    retry_backoff_seconds=[0])  # no actual sleep in tests
        ex, rec = self._exec(bs)
        # Recorder fails the first call, succeeds the rest.
        call_count = {"n": 0}
        original = rec.__call__
        def flaky(manifest, bundle_dir):
            call_count["n"] += 1
            r = original(manifest, bundle_dir)
            if call_count["n"] == 1:
                r["status"]["exit_code"] = 5
                r["status"]["error"] = "forced first-attempt failure"
            return r
        ex._submit_fn = flaky
        ex.run()
        self.assertEqual(ex.state.jobs["a"].status, "succeeded")
        self.assertEqual(ex.state.jobs["a"].attempts, 2)
        self.assertEqual(call_count["n"], 2)

    def test_retry_3_exhausts_then_marks_failed(self):
        """All 3 attempts fail → final status=failed, attempts=3."""
        a = _job("a", exists_path=self.fakebundle)
        bs = _batch([a], on_failure="retry_3", retry_backoff_seconds=[0])
        ex, rec = self._exec(bs)
        rec.exit_codes["a"] = 7  # always fail
        ex.run()
        self.assertEqual(ex.state.jobs["a"].status, "failed")
        self.assertEqual(ex.state.jobs["a"].attempts, 3)
        # Recorder was called 3 times
        self.assertEqual(len([c for c in rec.calls if c[0] == "a"]), 3)

    def test_no_retry_when_policy_is_skip_dependents(self):
        """on_failure=skip_dependents (default) → no retry, fail on first."""
        a = _job("a", exists_path=self.fakebundle)
        bs = _batch([a])  # default on_failure=skip_dependents
        ex, rec = self._exec(bs)
        rec.exit_codes["a"] = 1
        ex.run()
        self.assertEqual(ex.state.jobs["a"].status, "failed")
        self.assertEqual(ex.state.jobs["a"].attempts, 1)

    def test_retry_after_submit_raises(self):
        """If submit raises (eg. SSH dies), retry still triggers."""
        a = _job("a", exists_path=self.fakebundle)
        bs = _batch([a], on_failure="retry_3", retry_backoff_seconds=[0])
        ex, _ = self._exec(bs)
        n = {"i": 0}
        def raising_then_ok(manifest, bundle_dir):
            n["i"] += 1
            if n["i"] == 1:
                raise RuntimeError("simulated SSH failure")
            return {"status": {"phase": "exited", "exit_code": 0}, "result": {}}
        ex._submit_fn = raising_then_ok
        ex.run()
        self.assertEqual(ex.state.jobs["a"].status, "succeeded")
        self.assertEqual(ex.state.jobs["a"].attempts, 2)


class TestHeartbeatAndDoctor(_FleetDirIsolation, unittest.TestCase):
    """Tests for the heartbeat ticker + diagnose_batch ghost detector."""

    def setUp(self):
        self._isolate_fleet_dir()
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix="hb_t_"))
        self.fakebundle = self.tmp / "fake"
        self.fakebundle.mkdir()
        (self.fakebundle / "a.py").write_text("# fake\n")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)
        self._restore_fleet_dir()

    def test_doctor_flags_stale_heartbeat_as_ghost(self):
        from v2.batch import diagnose_batch
        # Hand-craft a state file with one running job that has a stale heartbeat
        sp = self.tmp / "state.json"
        import datetime
        old = (datetime.datetime.now() - datetime.timedelta(minutes=10)).isoformat(timespec="seconds")
        sp.write_text(json.dumps({
            "batch": "t",
            "started_at": old,
            "policy": {"heartbeat_threshold_s": 60},
            "jobs": {
                "a": {"name": "a", "status": "running", "host": "cdec",
                      "heartbeat_at": old, "attempts": 1,
                      "post_pull_errors": []},
                "b": {"name": "b", "status": "succeeded", "host": "cdec",
                      "attempts": 1, "post_pull_errors": []},
            },
        }))
        report = diagnose_batch(sp)
        self.assertEqual(report["summary"]["alive"], 0)
        self.assertEqual(report["summary"]["ghosts"], 1)
        self.assertEqual(report["ghosts"][0]["name"], "a")
        self.assertIn("stale", report["ghosts"][0]["reason"])

    def test_doctor_marks_fresh_heartbeat_alive(self):
        from v2.batch import diagnose_batch
        sp = self.tmp / "state.json"
        import datetime
        now = datetime.datetime.now().isoformat(timespec="seconds")
        sp.write_text(json.dumps({
            "batch": "t",
            "started_at": now,
            "policy": {"heartbeat_threshold_s": 60},
            "jobs": {
                "a": {"name": "a", "status": "running", "host": "cdec",
                      "heartbeat_at": now, "attempts": 1,
                      "post_pull_errors": []},
            },
        }))
        report = diagnose_batch(sp)
        self.assertEqual(report["summary"]["alive"], 1)
        self.assertEqual(report["summary"]["ghosts"], 0)

    def test_doctor_flags_stalled_build_progress_as_ghost(self):
        # Outer heartbeat FRESH (the orchestrator is alive and ticking) but the
        # remote build's own progress heartbeat is frozen — the mid-build stall
        # the old heartbeat_at-only detector missed for two days.
        from v2.batch import diagnose_batch
        import datetime
        sp = self.tmp / "state.json"
        now = datetime.datetime.now().isoformat(timespec="seconds")
        stale_utc = (datetime.datetime.now(datetime.timezone.utc)
                     - datetime.timedelta(hours=3)).isoformat(timespec="seconds")
        sp.write_text(json.dumps({
            "batch": "t",
            "started_at": now,
            "policy": {"heartbeat_threshold_s": 150,
                       "progress_heartbeat_threshold_s": 7200},
            "jobs": {
                "a": {"name": "a", "status": "running", "host": "kenne",
                      "heartbeat_at": now, "attempts": 1, "post_pull_errors": [],
                      "progress": {"heartbeat_utc": stale_utc, "stage": "chunks",
                                   "completed_chunks": 20, "total_chunks": 320}},
            },
        }))
        report = diagnose_batch(sp)
        self.assertEqual(report["summary"]["ghosts"], 1)
        self.assertEqual(report["ghosts"][0]["name"], "a")
        self.assertIn("build progress stale", report["ghosts"][0]["reason"])

    def test_doctor_keeps_fresh_build_progress_alive(self):
        # No false positives: a slow-but-healthy build whose progress heartbeat
        # is recent stays "alive" even with chunks still in flight.
        from v2.batch import diagnose_batch
        import datetime
        sp = self.tmp / "state.json"
        now = datetime.datetime.now().isoformat(timespec="seconds")
        fresh_utc = datetime.datetime.now(
            datetime.timezone.utc).isoformat(timespec="seconds")
        sp.write_text(json.dumps({
            "batch": "t",
            "started_at": now,
            "policy": {"heartbeat_threshold_s": 150,
                       "progress_heartbeat_threshold_s": 7200},
            "jobs": {
                "a": {"name": "a", "status": "running", "host": "kenne",
                      "heartbeat_at": now, "attempts": 1, "post_pull_errors": [],
                      "progress": {"heartbeat_utc": fresh_utc, "stage": "chunks"}},
            },
        }))
        report = diagnose_batch(sp)
        self.assertEqual(report["summary"]["alive"], 1)
        self.assertEqual(report["summary"]["ghosts"], 0)

    def test_recover_stale_jobs_interrupts_stalled_build_progress(self):
        # On resume, a job whose build progress is frozen (outer heartbeat
        # fresh) must be marked interrupted so the batch re-runs it.
        import datetime
        job = _job("a", exists_path=self.fakebundle,
                   metadata={"progress_path": "outputs/cache/p.jsonl"})
        ex = BatchExecutor(
            _batch([job]), _hosts(),
            state_path=self.tmp / "state.json",
            bundle_out_root=self.tmp / "bundles",
            submit_fn=_SubmitRecorder(), dry_run=True,
        )
        now_naive = datetime.datetime.now().isoformat(timespec="seconds")
        stale_utc = (datetime.datetime.now(datetime.timezone.utc)
                     - datetime.timedelta(hours=3)).isoformat(timespec="seconds")
        ex.policy["progress_heartbeat_threshold_s"] = 7200
        with ex._state_lock:
            js = ex.state.jobs["a"]
            js.status = "running"
            js.host = "kenne"
            js.heartbeat_at = now_naive          # outer FRESH
            js.progress = {"heartbeat_utc": stale_utc, "stage": "chunks"}
        ex._recover_stale_jobs()
        self.assertEqual(ex.state.jobs["a"].status, "interrupted")
        self.assertIn("build progress stale",
                      ex.state.jobs["a"].last_error or "")

    def test_declared_remote_progress_is_copied_into_job_state(self):
        job = _job(
            "a",
            exists_path=self.fakebundle,
            metadata={"progress_path": "outputs/cache/cache_generation_progress.jsonl"},
        )
        ex = BatchExecutor(
            _batch([job]),
            _hosts(),
            state_path=self.tmp / "state.json",
            bundle_out_root=self.tmp / "bundles",
            submit_fn=_SubmitRecorder(),
            dry_run=True,
        )
        with ex._state_lock:
            js = ex.state.jobs["a"]
            js.status = "running"
            js.host = "cdec"
            js.remote_workdir = "C:/sealed/jobs/v2-spec-unit"

        remote_calls = []

        def fake_remote_run(**kwargs):
            remote_calls.append(kwargs)
            return types.SimpleNamespace(
                returncode=0,
                stdout='{"completed_chunks":4,"total_chunks":10,"percent":40.0}\n',
                stderr="",
            )

        with mock.patch("v2.transport.remote_run", side_effect=fake_remote_run):
            progress = ex._read_job_progress("a")

        self.assertEqual(remote_calls[0]["host_alias"], "cdec")
        self.assertIn(
            "C:/sealed/jobs/v2-spec-unit/outputs/cache/cache_generation_progress.jsonl",
            remote_calls[0]["powershell_script"],
        )
        self.assertEqual(progress["completed_chunks"], 4)
        self.assertEqual(progress["total_chunks"], 10)
        self.assertEqual(
            progress["remote_progress_path"],
            "C:/sealed/jobs/v2-spec-unit/outputs/cache/cache_generation_progress.jsonl",
        )

    def test_declared_remote_progress_falls_back_to_blobs_code_path(self):
        job = _job(
            "a",
            exists_path=self.fakebundle,
            metadata={"progress_path": "outputs/cache/cache_generation_progress.jsonl"},
        )
        ex = BatchExecutor(
            _batch([job]),
            _hosts(),
            state_path=self.tmp / "state.json",
            bundle_out_root=self.tmp / "bundles",
            submit_fn=_SubmitRecorder(),
            dry_run=True,
        )
        with ex._state_lock:
            js = ex.state.jobs["a"]
            js.status = "running"
            js.host = "scan-new"
            js.remote_workdir = "C:/sealed/jobs/v2-spec-unit"

        fallback = (
            "C:/sealed/jobs/v2-spec-unit/blobs/code/"
            "outputs/cache/cache_generation_progress.jsonl"
        )

        def fake_remote_run(**kwargs):
            self.assertIn(
                "C:/sealed/jobs/v2-spec-unit/blobs/code/outputs/cache/cache_generation_progress.jsonl",
                kwargs["powershell_script"],
            )
            return types.SimpleNamespace(
                returncode=0,
                stdout=(
                    f"__V2_PROGRESS_PATH__={fallback}\n"
                    '{"completed_chunks":1,"total_chunks":4,"percent":25.0}\n'
                ),
                stderr="",
            )

        with mock.patch("v2.transport.remote_run", side_effect=fake_remote_run):
            progress = ex._read_job_progress("a")

        self.assertEqual(progress["completed_chunks"], 1)
        self.assertEqual(progress["remote_progress_path"], fallback)

    def test_doctor_flags_missing_heartbeat_as_ghost(self):
        from v2.batch import diagnose_batch
        sp = self.tmp / "state.json"
        sp.write_text(json.dumps({
            "batch": "t",
            "started_at": "2026-06-07T00:00:00",
            "policy": {"heartbeat_threshold_s": 60},
            "jobs": {
                "a": {"name": "a", "status": "running", "host": "cdec",
                      "heartbeat_at": None, "attempts": 1,
                      "post_pull_errors": []},
            },
        }))
        report = diagnose_batch(sp)
        self.assertEqual(report["summary"]["ghosts"], 1)
        self.assertIn("no heartbeat_at", report["ghosts"][0]["reason"])


class TestStateFileRecovery(_FleetDirIsolation, unittest.TestCase):
    """Tests for the corruption-detection + rebuild path."""

    def setUp(self):
        self._isolate_fleet_dir()
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix="recov_t_"))
        self.fakebundle = self.tmp / "fake"
        self.fakebundle.mkdir()
        (self.fakebundle / "a.py").write_text("# fake\n")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)
        self._restore_fleet_dir()

    def _batch_path(self) -> pathlib.Path:
        # Write a real batch.json so BatchSpec.from_path can be called
        a = self.tmp / "a.json"
        a.write_text(json.dumps({
            "name": "a", "entry": {"kind": "module", "path": "trading_common"},
            "host": {"alias": "cdec"}, "args": [],
            "inputs": {"bundle": [{"src": str(self.fakebundle), "as": "code/x"}],
                       "remote_refs": []},
            "outputs": {"pull": []}, "deps": [],
        }))
        bp = self.tmp / "batch.json"
        bp.write_text(json.dumps({
            "batch": "tt",
            "roots": {},
            "jobs": [a.name],
        }))
        return bp

    def test_corrupt_state_file_gives_helpful_error(self):
        from v2.spec import BatchSpec, SpecError
        bp = self._batch_path()
        sp = self.tmp / "state.json"
        sp.write_text("{this is not valid json")
        bs = BatchSpec.from_path(bp)
        with self.assertRaises(SpecError) as ctx:
            BatchExecutor(bs, _hosts(), state_path=sp,
                          bundle_out_root=self.tmp / "bundles")
        msg = str(ctx.exception)
        self.assertIn("corrupted", msg)
        self.assertIn("rebuild-state", msg)

    def test_rebuild_state_from_disk_finds_succeeded_jobs(self):
        from v2.batch import _rebuild_state_from_disk
        # Simulate a completed bundle: bundle dir with manifest + pulled status
        bundle_root = self.tmp / "bundles"
        bd = bundle_root / "job_1_a"
        bd.mkdir(parents=True)
        v2_id = "v2-spec-1-a-cdec"
        (bd / "manifest.json").write_text(json.dumps({"job_id": v2_id}))
        pulled = bd / "pulled" / v2_id
        pulled.mkdir(parents=True)
        (pulled / "status.json").write_text(json.dumps({
            "phase": "exited", "exit_code": 0,
        }))
        rebuilt = _rebuild_state_from_disk(self._batch_path(),
                                            bundle_out_root=bundle_root)
        self.assertEqual(rebuilt["jobs"]["a"]["status"], "succeeded")
        self.assertEqual(rebuilt["jobs"]["a"]["exit_code"], 0)

    def test_rebuild_state_marks_missing_pulled_as_interrupted(self):
        from v2.batch import _rebuild_state_from_disk
        bundle_root = self.tmp / "bundles"
        bd = bundle_root / "job_1_a"
        bd.mkdir(parents=True)
        (bd / "manifest.json").write_text(json.dumps({"job_id": "v2-x"}))
        # No pulled/ dir → interrupted
        rebuilt = _rebuild_state_from_disk(self._batch_path(),
                                            bundle_out_root=bundle_root)
        self.assertEqual(rebuilt["jobs"]["a"]["status"], "interrupted")

    def test_list_batches_returns_one_row_per_state_file(self):
        from v2.batch import list_batches
        root = self.tmp / "stash"
        root.mkdir()
        # Two state files
        for n in ("alpha", "beta"):
            (root / f"{n}_state.json").write_text(json.dumps({
                "batch": n, "started_at": "2026-06-07T00:00:00",
                "finished_at": None, "policy": {}, "jobs": {
                    "j1": {"name": "j1", "status": "succeeded",
                           "attempts": 1, "post_pull_errors": []},
                },
            }))
        rows = list_batches(root)
        self.assertEqual({r["batch"] for r in rows}, {"alpha", "beta"})
        self.assertEqual(rows[0]["status_counts"], {"succeeded": 1})


class _KeepRecordingSubmit:
    """Like _SubmitRecorder but ALSO records keep_remote_workdir per call,
    and emits realistic remote_workdir/v2_job_id so the deferred-cleanup
    pass has something to operate on."""
    def __init__(self):
        self.calls: list[dict] = []
        self.lock = threading.Lock()

    def __call__(self, manifest, bundle_dir, *, keep_remote_workdir=False):
        with self.lock:
            self.calls.append({
                "name": manifest.metadata.get("spec_name"),
                "host": manifest.host.ssh_alias,
                "keep": keep_remote_workdir,
            })
        return {
            "status": {"phase": "exited", "exit_code": 0, "error": None},
            "result": {},
            "manifest": manifest,
        }


class TestKeepRemoteWorkdir(_FleetDirIsolation, unittest.TestCase):
    """Fix-1: jobs referenced by downstream remote_refs / affinity must
    submit with keep_remote_workdir=True, and a post-batch cleanup pass
    must purge those workdirs once every referencer is terminal."""

    def setUp(self):
        self._isolate_fleet_dir()
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix="krw_t_"))
        self.fakebundle = self.tmp / "fake"
        self.fakebundle.mkdir()
        (self.fakebundle / "a.py").write_text("# fake\n")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)
        self._restore_fleet_dir()

    def _job_with_remote_ref(self, name, *, deps, ref_from):
        d = {
            "name": name,
            "phase": "test",
            "host": {"affinity": ref_from},
            "entry": {"kind": "module", "path": "trading_common"},
            "args": ["--c", "{{cache}}"],
            "inputs": {
                "bundle": [{"src": str(self.fakebundle), "as": "code/x"}],
                "remote_refs": [{"from": ref_from,
                                 "remote_path": "outputs/cache.mat",
                                 "var": "cache"}],
            },
            "outputs": {"pull": []},
            "deps": deps,
        }
        return JobSpec.from_dict(d)

    def test_referenced_upstream_submitted_with_keep_true(self):
        a = _job("a", host_alias="cdec", exists_path=self.fakebundle)
        b = self._job_with_remote_ref("b", deps=["a"], ref_from="a")
        rec = _KeepRecordingSubmit()
        ex = BatchExecutor(
            _batch([a, b]), _hosts(),
            state_path=self.tmp / "state.json",
            bundle_out_root=self.tmp / "bundles",
            submit_fn=rec,
        )
        # Don't actually remote_remove during cleanup — mock it out.
        from unittest import mock
        with mock.patch("v2.batch.remote_remove" if False
                        else "v2.transport.remote_remove") as rm:
            ex.run()
        rm.assert_called()  # Cleanup pass ran
        # 'a' is referenced by 'b' → submitted with keep=True
        a_call = next(c for c in rec.calls if c["name"] == "a")
        self.assertTrue(a_call["keep"], "upstream 'a' should have keep_remote_workdir=True")
        # 'b' is referenced by nobody → submitted with keep=False
        b_call = next(c for c in rec.calls if c["name"] == "b")
        self.assertFalse(b_call["keep"], "leaf 'b' should NOT keep its workdir")

    def test_unreferenced_jobs_use_default_keep_false(self):
        # Two independent jobs, neither referencing the other.
        a = _job("a", host_alias="cdec", exists_path=self.fakebundle)
        b = _job("b", host_alias="cdec", exists_path=self.fakebundle)
        rec = _KeepRecordingSubmit()
        ex = BatchExecutor(
            _batch([a, b]), _hosts(),
            state_path=self.tmp / "state.json",
            bundle_out_root=self.tmp / "bundles",
            submit_fn=rec,
        )
        from unittest import mock
        with mock.patch("v2.transport.remote_remove"):
            ex.run()
        for c in rec.calls:
            self.assertFalse(c["keep"], f"{c['name']} should NOT keep workdir")

    def test_cleanup_skips_when_referencer_still_running(self):
        # If a downstream is still 'pending' at cleanup time (e.g. failed
        # before launching, leaving its dependents pending), the upstream's
        # workdir should NOT be purged so a resume can reuse it.
        a = _job("a", host_alias="cdec", exists_path=self.fakebundle)
        b = self._job_with_remote_ref("b", deps=["a"], ref_from="a")
        rec = _KeepRecordingSubmit()
        ex = BatchExecutor(
            _batch([a, b]), _hosts(),
            state_path=self.tmp / "state.json",
            bundle_out_root=self.tmp / "bundles",
            submit_fn=rec,
        )
        # Mark 'b' as 'running' AFTER it actually completes — simulating
        # the orchestrator crashing mid-batch. We do this by patching the
        # cleanup pass to see 'b' as still-running.
        from unittest import mock
        with mock.patch("v2.transport.remote_remove") as rm:
            # Run normally → both succeed
            ex.run()
            # First cleanup pass already ran. Manually mark 'b' as pending
            # and call cleanup again — 'a' should stay since 'b' isn't terminal.
            ex.state.jobs["b"].status = "pending"
            # Restore 'a'.kept_for_refs so cleanup considers it
            ex.state.jobs["a"].kept_for_refs = True
            rm.reset_mock()
            ex._cleanup_kept_workdirs()
            rm.assert_not_called()

    def test_kept_for_refs_state_field_persisted(self):
        a = _job("a", host_alias="cdec", exists_path=self.fakebundle)
        b = self._job_with_remote_ref("b", deps=["a"], ref_from="a")
        rec = _KeepRecordingSubmit()
        ex = BatchExecutor(
            _batch([a, b]), _hosts(),
            state_path=self.tmp / "state.json",
            bundle_out_root=self.tmp / "bundles",
            submit_fn=rec,
        )
        from unittest import mock
        with mock.patch("v2.transport.remote_remove"):
            ex.run()
        # After cleanup, kept_for_refs is flipped back to False
        self.assertFalse(ex.state.jobs["a"].kept_for_refs)
        # And the persisted state reflects it
        persisted = json.loads((self.tmp / "state.json").read_text())
        self.assertFalse(persisted["jobs"]["a"]["kept_for_refs"])


if __name__ == "__main__":
    unittest.main()
