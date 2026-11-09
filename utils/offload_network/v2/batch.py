"""Batch executor — run a DAG of v2 job specs with host affinity +
parallelism caps + restart-on-failure handling.

Reads a batch.json (parsed by v2.spec.BatchSpec.from_path), expands its
jobs into topological layers, dispatches each layer in parallel up to
the policy limits, records (job → resolved_host) so downstream jobs with
host.affinity land on the same machine.

State is persisted to a JSON state file so a partial batch can be
resumed after a Mac reboot or operator Ctrl-C: completed jobs are
skipped, in-flight jobs become "interrupted" and are eligible to retry,
the remaining DAG just continues.

Why this lives in v2/ rather than fleet/: the DAG executor is specific
to the v2 transport (it dispatches via v2.submit.submit_one) and uses
v2.autobundle.build_manifest_from_spec. fleet.py's general management
commands (status, jobs, kill) work uniformly across v2 jobs without
needing batch-awareness.
"""
from __future__ import annotations

import concurrent.futures as cf
import datetime as dt
import json
import os
import pathlib
import shutil
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field, asdict
from typing import Callable, Optional

from .spec import BatchSpec, JobSpec, SpecError, topological_layers
from .autobundle import (
    build_manifest_from_spec, expected_remote_workdir, ResolvedUpstream,
)
from .defaults import remote_workdir_default
from fleet.paths import v2_bundles_root


# ---------------------------------------------------------------------------
# Per-job state (persisted)
# ---------------------------------------------------------------------------

@dataclass
class JobState:
    name: str
    # pending | running | pulling_outputs | succeeded | failed | skipped | interrupted | retry_backoff
    status: str = "pending"
    host: Optional[str] = None
    v2_job_id: Optional[str] = None
    remote_workdir: Optional[str] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    exit_code: Optional[int] = None
    last_error: Optional[str] = None
    attempts: int = 0
    bundle_dir_local: Optional[str] = None
    # Errors encountered while copying output files to declared destinations.
    # Job still counts as "succeeded" — operator decides if these matter.
    # Each entry: {src, dst, error}.
    post_pull_errors: list = field(default_factory=list)
    # Wall-clock of the most recent "I am alive" tick from the running job.
    # Stale heartbeat (> heartbeat_threshold_seconds) on a "running" job means
    # the orchestrator probably crashed — flagged by `v2 batch doctor`.
    heartbeat_at: Optional[str] = None
    # Optional latest JSON progress event copied from a small remote JSONL file
    # declared in JobSpec.metadata["progress_path"].
    progress: Optional[dict] = None
    # True if this job was submitted with keep_remote_workdir=True because
    # a downstream job references it via remote_refs. Set to False after
    # the deferred cleanup pass removes the workdir (so resumed batches
    # don't double-delete or skip the post-batch sweep).
    kept_for_refs: bool = False
    # True if this job was kept alive so outputs.pull could fetch files
    # directly from the remote workdir outside the sealed result archive.
    kept_for_outputs: bool = False

    def is_terminal(self) -> bool:
        return self.status in ("succeeded", "failed", "skipped")


_ACTIVE_STATUSES = {"running", "pulling_outputs"}

# A "running" job whose REMOTE build-progress heartbeat (progress.heartbeat_utc,
# emitted per chunk by run_full_regen) is older than this is a stalled build —
# even while the orchestrator keeps the outer heartbeat_at warm. Conservative
# (2h) so a slow-but-healthy chunk is never mistaken for a stall.
_DEFAULT_PROGRESS_HEARTBEAT_THRESHOLD_S = 7200


@dataclass
class BatchState:
    batch: str
    started_at: str
    finished_at: Optional[str] = None
    jobs: dict[str, JobState] = field(default_factory=dict)
    policy: dict = field(default_factory=dict)
    state_path: Optional[str] = None  # echo for diagnostics

    def to_dict(self) -> dict:
        return {
            "batch": self.batch,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "policy": self.policy,
            "state_path": self.state_path,
            "jobs": {k: asdict(v) for k, v in self.jobs.items()},
        }

    @classmethod
    def from_dict(cls, d: dict) -> "BatchState":
        bs = cls(
            batch=d["batch"],
            started_at=d["started_at"],
            finished_at=d.get("finished_at"),
            policy=d.get("policy", {}),
            state_path=d.get("state_path"),
        )
        for name, jd in d.get("jobs", {}).items():
            bs.jobs[name] = JobState(**jd)
        return bs


# ---------------------------------------------------------------------------
# Policy helpers
# ---------------------------------------------------------------------------

def _default_policy() -> dict:
    return {
        "max_parallel_per_host": 2,
        "max_parallel_total": 8,
        # "skip_dependents" | "stop_batch" | "retry_N" (eg "retry_3" or "retry_3x").
        # Default to 2 attempts + backoff so transient infra blips are retried
        # without requiring an explicit resume command from operators.
        "on_failure": "retry_2",
        # Backoff between retry attempts. Defaults to 30s, 2min, 5min, 10min...
        # capped at the longest entry. Operator can override:
        # "retry_backoff_seconds": [10, 30, 60]
        "retry_backoff_seconds": [30, 120, 300, 600],
        "host_pool": None,                  # None = all libemd hosts; else list
        # Per-host overrides for the max_parallel_per_host cap, eg.
        # {"cdec": 4, "kenne": 1}. Hosts not in this dict use the global cap.
        "per_host_overrides": {},
        # Heartbeat tick (seconds) for running jobs. A doctor scan flags any
        # "running" job whose heartbeat is older than `heartbeat_threshold_s`
        # (default = 5× heartbeat_interval_s).
        "heartbeat_interval_s": 30,
        "heartbeat_threshold_s": 150,
        # Remote build-progress stall threshold. A running job whose
        # progress.heartbeat_utc is older than this is treated as a stalled
        # build by doctor + auto-recover (the outer heartbeat_at can't see it).
        "progress_heartbeat_threshold_s": _DEFAULT_PROGRESS_HEARTBEAT_THRESHOLD_S,
        # If True (default), any stale/invalid heartbeat on startup marks a
        # running/pulling_outputs job as interrupted so resume can re-run it.
        "auto_recover_stale": True,
        # If False, the batch-level heartbeat ticker doesn't start (useful for
        # tests and short-lived dry runs).
        "heartbeat_enabled": True,
    }


def _parse_retry_max(on_failure: str) -> int:
    """Extract the N from 'retry_N' or 'retry_Nx' policy — meaning N TOTAL
    attempts including the initial one. Returns 1 (just the initial
    attempt, no retry) for non-retry policies."""
    if not isinstance(on_failure, str) or not on_failure.startswith("retry_"):
        return 1
    digits = "".join(c for c in on_failure[len("retry_"):] if c.isdigit())
    return max(1, int(digits)) if digits else 1


def _resolve_policy(p: dict) -> dict:
    out = _default_policy()
    out.update(p or {})
    return out


def _now_iso() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def _needs_direct_output_pull(j: JobSpec) -> bool:
    """True for jobs whose large outputs are intentionally excluded from
    the sealed result archive and must be pulled from the remote workdir."""
    subkind = str(j.metadata.get("phase_subkind") or "")
    return j.phase == "cache" or subkind in {"cache_build", "cache_stage"}


# ---------------------------------------------------------------------------
# Executor
# ---------------------------------------------------------------------------

class BatchExecutor:
    """Run a BatchSpec to completion (or report-only in dry-run mode).

    Construction:
        ex = BatchExecutor(spec, hosts, state_path=..., dry_run=False)

    Lifecycle:
        ex.run()                  # blocking; returns BatchState
        ex.state                  # accessor for current state

    Behaviour:
      - Walks topological layers; within a layer, dispatches in parallel
        subject to policy caps.
      - Records host resolution after each job (for affinity lookups).
      - On failure: applies on_failure policy.
      - Persists state to a JSON file after every status transition.

    Tests inject `submit_fn` to mock the actual v2 submit so DAG/affinity
    logic can be exercised without touching a remote.
    """

    def __init__(
        self,
        spec: BatchSpec,
        hosts: dict,
        *,
        state_path: pathlib.Path | str | None = None,
        bundle_out_root: pathlib.Path | str | None = None,
        dry_run: bool = False,
        submit_fn: Optional[Callable] = None,
        on_state_change: Optional[Callable[[BatchState], None]] = None,
    ):
        self.spec = spec
        self.hosts = hosts
        self.dry_run = dry_run
        self.policy = _resolve_policy(spec.policy)
        self.bundle_out_root = pathlib.Path(
            bundle_out_root or (v2_bundles_root() / "batches")
        )
        self.bundle_out_root.mkdir(parents=True, exist_ok=True)
        self.state_path = pathlib.Path(state_path) if state_path else (
            self.bundle_out_root / f"batch_{spec.batch}_state.json"
        )
        # mkdir -p the state file's parent so the atomic-rename write
        # has somewhere to land. Otherwise: FileNotFoundError on the .tmp.
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self._on_state_change = on_state_change
        # submit_fn: override for tests; default is v2.submit.submit_one
        self._submit_fn = submit_fn or self._real_submit
        self._jobs_by_name = {job.name: job for job in spec.jobs}
        # Per-host semaphores enforce max_parallel_per_host
        self._host_sems: dict[str, threading.Semaphore] = {}
        self._sem_lock = threading.Lock()
        # Per-job locks so concurrent updates to JobState (from worker threads)
        # serialise. Re-entrant so _save_state can be called from inside a
        # held lock without deadlocking.
        self._state_lock = threading.RLock()
        # _next_job_id reads + mutates ~/.fleet/state.json — fcntl is
        # per-process so two threads in the same process can both grab
        # the same job_id. This in-process lock serialises them.
        self._job_id_lock = threading.Lock()
        # Initialise or resume state
        if self.state_path.exists():
            try:
                raw = self.state_path.read_text()
                if not raw.strip():
                    raise ValueError("state file is empty")
                self.state = BatchState.from_dict(json.loads(raw))
            except (json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
                raise SpecError(
                    f"state file {self.state_path} is corrupted: "
                    f"{type(e).__name__}: {e}\n"
                    f"Rebuild it from the per-bundle artifacts:\n"
                    f"  python3 -m v2 batch rebuild-state {spec.job_source_paths[0].parent.parent}/batch.json "
                    f"--state-file {self.state_path}"
                )
            # Any active entries from a prior crash → "interrupted"
            for j in self.state.jobs.values():
                if j.status in _ACTIVE_STATUSES:
                    j.status = "interrupted"
        else:
            self.state = BatchState(
                batch=spec.batch,
                started_at=_now_iso(),
                policy=self.policy,
                state_path=str(self.state_path),
            )
        # Seed any new jobs that aren't in state
        for j in spec.jobs:
            if j.name not in self.state.jobs:
                self.state.jobs[j.name] = JobState(name=j.name)
        if self.policy.get("auto_recover_stale", True):
            self._recover_stale_jobs()
        # Compute reverse-reference map: upstream_name → set of downstream
        # job names that reference it via remote_refs OR host.affinity.
        # Used by Fix-1 to defer remote-workdir cleanup until every
        # referencer has finished (so the cache stays available for them).
        self._referenced_by: dict[str, set[str]] = {}
        for j in spec.jobs:
            refs = {r.from_ for r in j.inputs.remote_refs}
            if j.host.affinity:
                refs.add(j.host.affinity)
            for upstream in refs:
                self._referenced_by.setdefault(upstream, set()).add(j.name)
        self._save_state()

    # ----- Public lifecycle -----

    def run(self) -> BatchState:
        """Execute the batch. Returns the final state."""
        hb = None
        if self.policy.get("heartbeat_enabled", True) and not self.dry_run:
            hb = _Heartbeat(self, self.policy.get("heartbeat_interval_s", 30))
            hb.start()
        try:
            return self._run_inner()
        finally:
            if hb is not None:
                hb.stop()

    def _run_inner(self) -> BatchState:
        layers = topological_layers(self.spec.jobs)
        for li, layer in enumerate(layers):
            # Filter: skip jobs that are already terminal AND haven't been
            # marked for retry (their state file already records success).
            actionable = [
                j for j in layer
                if not self.state.jobs[j.name].is_terminal()
                or self.state.jobs[j.name].status == "interrupted"
            ]
            if not actionable:
                continue
            # Mark skipped any job whose deps failed OR were themselves
            # skipped (cascade is transitive: a → b skipped → c skipped).
            cascaded = [
                j for j in actionable
                if any(self.state.jobs[d].status in ("failed", "skipped")
                       for d in j.deps if d in self.state.jobs)
            ]
            for j in cascaded:
                with self._state_lock:
                    self.state.jobs[j.name].status = "skipped"
                    self.state.jobs[j.name].last_error = "upstream failed"
                    self.state.jobs[j.name].finished_at = _now_iso()
            self._save_state()
            runnable = [j for j in actionable if j not in cascaded]
            self._run_layer(runnable, layer_index=li)
            # If policy is stop_batch and anything failed in this layer, halt.
            if self.policy["on_failure"] == "stop_batch":
                fails = [j for j in runnable
                         if self.state.jobs[j.name].status == "failed"]
                if fails:
                    self._mark_remaining_skipped(layers[li + 1:])
                    break
        self.state.finished_at = _now_iso()
        self._save_state()
        # Fix-1: every kept_for_refs upstream whose downstreams are now
        # all terminal can have its remote workdir purged. Runs after the
        # batch finishes so that interrupted/retried downstreams still
        # see their upstream cache.
        if not self.dry_run:
            self._cleanup_kept_workdirs()
        return self.state

    def _cleanup_kept_workdirs(self) -> None:
        """Remove remote workdirs that were kept alive (Fix-1) because
        downstream jobs in this batch reference them via remote_refs.

        Only purges when every referencer is in a terminal state — a
        partially-completed batch keeps the upstream so the operator can
        `resume` and the downstream cache hits don't have to be rebuilt.
        """
        from .transport import remote_remove
        for upstream_name, referencers in self._referenced_by.items():
            up = self.state.jobs.get(upstream_name)
            if not up or up.status != "succeeded" or not up.remote_workdir:
                continue
            if not up.kept_for_refs:
                # Wasn't kept in the first place (e.g. resumed batch
                # where this upstream ran before Fix-1 plumbing).
                continue
            # Only clean up if EVERY referencer has finished. If any are
            # still pending/running/retry_backoff we keep the workdir.
            unfinished = [
                r for r in referencers
                if r in self.state.jobs
                and self.state.jobs[r].status not in ("succeeded", "failed", "skipped")
            ]
            if unfinished:
                continue
            if up.post_pull_errors:
                # Preserve the only known remote copy for manual recovery.
                continue
            try:
                self._cleanup_remote_job_artifacts(up)
                with self._state_lock:
                    up.kept_for_refs = False
            except Exception as e:
                with self._state_lock:
                    up.last_error = (
                        f"deferred cleanup failed: {type(e).__name__}: {e}"
                    )
        self._save_state()

    def _cleanup_remote_job_artifacts(self, js: JobState) -> None:
        """Best-effort cleanup for one submitted job's remote workdir + seal."""
        from .transport import remote_remove
        if not js.host or not js.remote_workdir:
            return
        remote_remove(host_alias=js.host, remote_path=js.remote_workdir)
        parent = js.remote_workdir.rstrip("/\\").rsplit("/", 1)[0]
        if js.v2_job_id and parent:
            remote_remove(
                host_alias=js.host,
                remote_path=f"{parent}/{js.v2_job_id}.tar.gz",
            )

    def status_summary(self) -> dict[str, int]:
        """Quick (status → count) summary."""
        out: dict[str, int] = {}
        for j in self.state.jobs.values():
            out[j.status] = out.get(j.status, 0) + 1
        return out

    # ----- Per-layer dispatch -----

    def _run_layer(self, jobs: list[JobSpec], *, layer_index: int) -> None:
        """Dispatch all jobs in the layer, respecting parallelism caps."""
        max_total = self.policy["max_parallel_total"]
        with cf.ThreadPoolExecutor(max_workers=max(1, max_total)) as ex:
            futures = {ex.submit(self._run_one, j): j for j in jobs}
            for fut in cf.as_completed(futures):
                j = futures[fut]
                try:
                    fut.result()
                except Exception as e:
                    with self._state_lock:
                        self.state.jobs[j.name].status = "failed"
                        self.state.jobs[j.name].last_error = f"{type(e).__name__}: {e}"
                        self.state.jobs[j.name].finished_at = _now_iso()
                    self._save_state()

    def _host_semaphore(self, host_alias: str) -> threading.Semaphore:
        """Return (creating on first call) the in-flight semaphore for a
        host. Cap defaults to policy.max_parallel_per_host but can be
        overridden per-host via policy.per_host_overrides[<alias>].

        Example policy:
            "max_parallel_per_host": 2,
            "per_host_overrides": {"cdec": 4, "kenne": 1}
        → cdec runs 4 in-flight, kenne runs 1, every other host runs 2.
        """
        with self._sem_lock:
            sem = self._host_sems.get(host_alias)
            if sem is None:
                cap = self.policy.get("per_host_overrides", {}).get(
                    host_alias, self.policy["max_parallel_per_host"]
                )
                sem = threading.Semaphore(max(1, int(cap)))
                self._host_sems[host_alias] = sem
            return sem

    def _run_one(self, j: JobSpec) -> None:
        """Single-job lifecycle with retry. Loops _run_one_attempt up to
        the policy-defined max, sleeping for retry_backoff_seconds between
        attempts. Each attempt gets a fresh job_id + workdir + manifest so
        v2's spawn-skip-if-status-exists idempotency doesn't short-circuit
        the retry by re-reading a prior attempt's stale status.json."""
        max_attempts = _parse_retry_max(self.policy["on_failure"])
        backoff = self.policy["retry_backoff_seconds"]
        last_rc: int = 1
        # Preserve prior attempts if this job was interrupted on resume — but
        # an 'interrupted' job's most recent attempt never COMPLETED (mid-run
        # crash, SSH drop, or an operator forcing a retry by relabelling a
        # failed job). That attempt was counted at launch (see attempts += 1 in
        # _run_one_attempt) but produced no terminal rc, so it must NOT consume
        # the retry budget. Roll it back so the job is re-run; otherwise a job
        # that used its whole budget and was then interrupted would be marked
        # failed on resume without ever running again — and 'interrupted'
        # canonically means "eligible to retry" (module docstring +
        # diagnose_batch). This is the single chokepoint covering every resume
        # path: auto-recover-stale, rebuild-state-from-disk, and operator
        # hand-edits to the state file.
        with self._state_lock:
            js = self.state.jobs[j.name]
            if js.status == "interrupted" and js.attempts > 0:
                js.attempts -= 1
            start_attempt = js.attempts
        if start_attempt >= max_attempts:
            with self._state_lock:
                js = self.state.jobs[j.name]
                js.status = "failed"
                if js.last_error is None:
                    js.last_error = (
                        f"already at retry limit ({max_attempts}) before this attempt"
                    )
                js.finished_at = _now_iso()
            self._save_state()
            return
        for attempt_idx in range(start_attempt, max_attempts):
            if attempt_idx > 0:
                # Sleep before the retry — clamp index at last backoff entry.
                delay = backoff[min(attempt_idx - 1, len(backoff) - 1)]
                with self._state_lock:
                    self.state.jobs[j.name].status = "retry_backoff"
                    self.state.jobs[j.name].last_error = (
                        f"attempt {attempt_idx + 1}/{max_attempts} failed with rc={last_rc}, "
                        f"sleeping {delay}s before attempt {attempt_idx + 1}"
                    )
                self._save_state()
                time.sleep(delay)
            last_rc = self._run_one_attempt(j, attempt_idx=attempt_idx)
            if last_rc == 0:
                return  # succeeded
        # All attempts failed — JobState already records failed from
        # the final attempt. Notify callback if configured.
        if self._on_state_change:
            try:
                self._on_state_change(self.state)
            except Exception:
                pass

    def _recover_stale_jobs(self) -> None:
        """Convert stale active jobs to interrupted so resume re-runs them.

        This keeps the user workflow "submit|resume until done" even after an
        operator Ctrl-C, SSH drop, or stale heartbeat.
        """
        if not self.policy.get("heartbeat_enabled", True):
            return
        threshold_s = self.policy.get("heartbeat_threshold_s", 150)
        prog_threshold_s = self.policy.get(
            "progress_heartbeat_threshold_s", _DEFAULT_PROGRESS_HEARTBEAT_THRESHOLD_S)
        now = dt.datetime.now()
        now_utc = dt.datetime.now(dt.timezone.utc)
        changed = False
        for js in self.state.jobs.values():
            if js.status not in _ACTIVE_STATUSES:
                continue
            stale = False
            reason = ""
            if not js.heartbeat_at:
                stale = True
                reason = "no heartbeat_at recorded"
            else:
                try:
                    hb = dt.datetime.fromisoformat(js.heartbeat_at)
                except ValueError:
                    stale = True
                    reason = f"invalid heartbeat_at: {js.heartbeat_at!r}"
                else:
                    age_s = (now - hb).total_seconds()
                    if age_s > threshold_s:
                        stale = True
                        reason = f"heartbeat stale by {int(age_s)}s"
            if not stale:
                prog_age = _progress_heartbeat_age_s(js.progress, now_utc)
                if prog_age is not None and prog_age > prog_threshold_s:
                    stale = True
                    reason = f"build progress stale by {int(prog_age)}s"
            if stale:
                js.status = "interrupted"
                js.finished_at = _now_iso()
                js.last_error = (
                    f"auto-recovered stale active status on resume: {reason}"
                )
                changed = True
        if changed:
            self._save_state()

    def _run_one_attempt(self, j: JobSpec, *, attempt_idx: int) -> int:
        """One attempt: resolve host → autobundle → submit → record state.
        Returns the rc (0 = success, !=0 = failure)."""
        upstream = self._collect_upstream(j)
        job_id = self._next_job_id()
        bundle_dir = self.bundle_out_root / f"job_{job_id}_{_safe(j.name)}"
        if attempt_idx > 0:
            # Tag retry attempts so the operator can see them on disk
            bundle_dir = self.bundle_out_root / (
                f"job_{job_id}_{_safe(j.name)}_attempt{attempt_idx + 1}"
            )
        bundle_dir.mkdir(parents=True, exist_ok=True)
        try:
            manifest, outputs_spec = build_manifest_from_spec(
                j, job_id=job_id,
                bundle_out_dir=bundle_dir,
                hosts=self.hosts,
                roots=self.spec.roots,
                upstream_state=upstream,
                # Probe affinity host on retries — first attempt assumes the
                # host is alive (cheaper); if that attempt fails it might be
                # because the host died, so probe on attempt 2+ and fall over
                # to fallback_local if needed.
                probe_affinity_host=(attempt_idx > 0)
                                     and self.policy.get("probe_affinity_on_retry", True),
                # Restrict the picker (for jobs with no alias / no affinity)
                # to policy.host_pool. Operator-set aliases + affinity still
                # win — the pool only constrains the pool-pick fallback.
                host_pool=self.policy.get("host_pool"),
            )
        except Exception as e:
            with self._state_lock:
                js = self.state.jobs[j.name]
                js.attempts += 1
                js.status = "failed"
                js.last_error = f"autobundle failed: {type(e).__name__}: {e}"
                js.finished_at = _now_iso()
            self._save_state()
            return 1
        host_alias = manifest.host.ssh_alias
        sem = self._host_semaphore(host_alias)
        sem.acquire()
        try:
            with self._state_lock:
                js = self.state.jobs[j.name]
                js.status = "running"
                js.host = host_alias
                js.v2_job_id = manifest.job_id
                js.remote_workdir = expected_remote_workdir(manifest)
                js.bundle_dir_local = str(bundle_dir)
                js.started_at = _now_iso()
                js.attempts += 1
            self._save_state()

            if self.dry_run:
                with self._state_lock:
                    self.state.jobs[j.name].status = "succeeded"
                    self.state.jobs[j.name].exit_code = 0
                    self.state.jobs[j.name].finished_at = _now_iso()
                self._save_state()
                return 0

            try:
                # Keep the remote workdir alive if another job references
                # it, or if outputs.pull needs direct rsync for artifacts
                # excluded from the standard sealed result tarball.
                should_keep_for_refs = bool(self._referenced_by.get(j.name))
                should_keep_for_outputs = bool(
                    outputs_spec and outputs_spec.pull and _needs_direct_output_pull(j)
                )
                should_keep = should_keep_for_refs or should_keep_for_outputs
                if should_keep_for_refs or should_keep_for_outputs:
                    with self._state_lock:
                        self.state.jobs[j.name].kept_for_refs = should_keep_for_refs
                        self.state.jobs[j.name].kept_for_outputs = should_keep_for_outputs
                try:
                    result = self._submit_fn(manifest, bundle_dir,
                                              keep_remote_workdir=should_keep)
                except TypeError:
                    # Backward-compat for mocks/test submit_fns that don't
                    # take the kwarg. Fall back to the legacy 2-arg signature.
                    result = self._submit_fn(manifest, bundle_dir)
            except Exception as e:
                with self._state_lock:
                    js = self.state.jobs[j.name]
                    js.status = "failed"
                    js.exit_code = 1
                    js.last_error = f"submit raised: {type(e).__name__}: {e}"
                    js.finished_at = _now_iso()
                self._save_state()
                return 1
            status = (result.get("status") or {}) if isinstance(result, dict) else {}
            rc = status.get("exit_code", 1)
            needs_post_pull = bool(rc == 0 and outputs_spec and outputs_spec.pull)
            with self._state_lock:
                js = self.state.jobs[j.name]
                js.exit_code = rc
                js.status = "pulling_outputs" if needs_post_pull else (
                    "succeeded" if rc == 0 else "failed"
                )
                js.last_error = None if rc == 0 else (
                    status.get("error") or f"submit returned rc={rc}"
                )
                js.finished_at = None if needs_post_pull else _now_iso()
            self._save_state()
            if needs_post_pull:
                self._post_pull(j, outputs_spec, bundle_dir, manifest)
                with self._state_lock:
                    js = self.state.jobs[j.name]
                    js.status = "succeeded"
                    js.finished_at = _now_iso()
                self._save_state()
                with self._state_lock:
                    js = self.state.jobs[j.name]
                    can_cleanup_outputs_copy = (
                        js.kept_for_outputs
                        and not js.kept_for_refs
                        and not js.post_pull_errors
                    )
                if can_cleanup_outputs_copy:
                    try:
                        self._cleanup_remote_job_artifacts(self.state.jobs[j.name])
                        with self._state_lock:
                            self.state.jobs[j.name].kept_for_outputs = False
                        self._save_state()
                    except Exception as e:
                        with self._state_lock:
                            self.state.jobs[j.name].last_error = (
                                f"post-pull cleanup failed: {type(e).__name__}: {e}"
                            )
                        self._save_state()
            return rc
        finally:
            sem.release()

    def _collect_upstream(self, j: JobSpec) -> dict[str, ResolvedUpstream]:
        """Build the upstream_state for one job from current BatchState."""
        out: dict[str, ResolvedUpstream] = {}
        for dep_name in set(j.deps) | ({j.host.affinity} if j.host.affinity else set()):
            js = self.state.jobs.get(dep_name)
            if not js or js.status != "succeeded":
                continue
            out[dep_name] = ResolvedUpstream(
                name=dep_name,
                host_alias=js.host or "",
                remote_workdir=js.remote_workdir or "",
                v2_job_id=js.v2_job_id or "",
                bundle_dir_local=pathlib.Path(js.bundle_dir_local or "."),
            )
        return out

    def _post_pull(
        self,
        spec: JobSpec,
        outputs_spec,
        bundle_dir: pathlib.Path,
        manifest,
    ) -> None:
        """After submit_one's standard result-pull, copy the user-declared
        files from <bundle_dir>/pulled/<v2_job_id>/outputs/<remote> to
        their declared `to:` paths.

        Per-file errors are appended to JobState.post_pull_errors so they
        surface in `batch status` rather than disappearing silently. The
        job still counts as "succeeded" — partial output is usually
        better than re-running an hours-long job, and the operator can
        re-copy the missing files manually from the bundle dir.

        Large binary outputs (.mat files in particular — EMD caches that
        downstream jobs depend on) are copied via .partial + atomic
        rename. If the operator kills mid-copy, no half-written .mat
        file is left to fool a downstream cache-presence check.
        """
        import glob as _glob
        from .spec import _resolve_vars
        pulled_root = bundle_dir / "pulled" / manifest.job_id / "outputs"
        for p in outputs_spec.pull:
            remote_glob = p.remote.lstrip("/")
            try:
                to = _resolve_vars(p.to, self.spec.roots)
            except Exception as e:
                self._record_post_pull_error(
                    spec.name, p.remote, p.to, f"$VAR resolution: {e}"
                )
                continue
            to_path = pathlib.Path(to)
            matches = (
                _glob.glob(str(pulled_root / remote_glob))
                if pulled_root.exists() else []
            )
            if p.to.endswith("/") or to_path.is_dir():
                try:
                    to_path.mkdir(parents=True, exist_ok=True)
                except Exception as e:
                    self._record_post_pull_error(
                        spec.name, p.remote, p.to, f"mkdir: {e}"
                    )
                    continue
                if matches:
                    for src in matches:
                        dst = to_path / pathlib.Path(src).name
                        self._safe_copy(spec.name, p.remote, src, dst)
                else:
                    self._direct_pull_output(spec.name, p.remote, manifest, to_path)
            else:
                try:
                    to_path.parent.mkdir(parents=True, exist_ok=True)
                except Exception as e:
                    self._record_post_pull_error(
                        spec.name, p.remote, p.to, f"mkdir parent: {e}"
                    )
                    continue
                if matches:
                    self._safe_copy(spec.name, p.remote, matches[0], to_path)
                else:
                    self._direct_pull_output(spec.name, p.remote, manifest, to_path)

    def _direct_pull_output(self, job_name: str, remote: str, manifest,
                            local_dest: pathlib.Path) -> None:
        """Pull one declared output directly from the remote workdir.

        This is the large-artifact path: cache .mat files are excluded
        from the sealed result tar and fetched here via resumable rsync.
        """
        remote_abs = (
            f"{expected_remote_workdir(manifest).rstrip('/')}/outputs/"
            f"{remote.lstrip('/')}"
        )
        is_glob = any(c in remote for c in "*?[")
        remote_size = None
        try:
            from .transport import pull_path, remote_file_size
            if not is_glob:
                remote_size = remote_file_size(
                    manifest.host.ssh_alias,
                    remote_abs,
                    timeout=60,
                )
            pull_path(
                host_alias=manifest.host.ssh_alias,
                remote_path=remote_abs,
                local_dest=local_dest,
                rsync_path=manifest.host.rsync_path,
                timeout=7200,
            )
        except Exception as e:
            self._record_post_pull_error(
                job_name, remote, str(local_dest),
                f"direct rsync: {type(e).__name__}: {e}",
            )
            return

        if is_glob:
            return

        pulled_path = local_dest
        if local_dest.is_dir():
            pulled_path = local_dest / pathlib.PurePosixPath(
                remote.replace("\\", "/")
            ).name
        if not pulled_path.exists():
            self._record_post_pull_error(
                job_name, remote, str(pulled_path),
                "direct rsync verification: missing local output",
            )
            return
        if remote_size is not None and pulled_path.stat().st_size != remote_size:
            self._record_post_pull_error(
                job_name, remote, str(pulled_path),
                "direct rsync verification: size mismatch "
                f"local={pulled_path.stat().st_size} remote={remote_size}",
            )

    def _safe_copy(self, job_name: str, remote: str, src: str | pathlib.Path,
                   dst: pathlib.Path) -> None:
        """Atomic copy with .partial rename for files that downstream jobs
        gate on (anything ≥10 MB OR any .mat — EMD caches). For small files
        a direct copy is fine; the .partial dance just adds disk churn.
        """
        try:
            src_p = pathlib.Path(src)
            use_partial = (
                str(dst).endswith(".mat")
                or src_p.stat().st_size > 10 * 1024 * 1024
            )
            if use_partial:
                tmp = dst.with_suffix(dst.suffix + ".partial")
                shutil.copy2(src_p, tmp)
                os.replace(tmp, dst)
            else:
                shutil.copy2(src_p, dst)
        except Exception as e:
            self._record_post_pull_error(job_name, remote, str(dst),
                                         f"copy: {type(e).__name__}: {e}")

    def _record_post_pull_error(self, job_name: str, remote: str,
                                dst: str, error: str) -> None:
        with self._state_lock:
            self.state.jobs[job_name].post_pull_errors.append({
                "remote": remote, "dst": dst, "error": error,
                "at": _now_iso(),
            })
        self._save_state()

    def _read_job_progress(self, job_name: str) -> dict | None:
        spec = self._jobs_by_name.get(job_name)
        js = self.state.jobs.get(job_name)
        if spec is None or js is None or not js.host or not js.remote_workdir:
            return None
        progress_rel = spec.metadata.get("progress_path")
        if not progress_rel:
            return None
        progress_text = str(progress_rel).replace("\\", "/")
        first_part = progress_text.split("/", 1)[0]
        is_absolute = progress_text.startswith("/") or (
            len(first_part) == 2 and first_part[1] == ":"
        )
        if is_absolute:
            remote_path = progress_text
            remote_paths = [remote_path]
        else:
            base = js.remote_workdir.rstrip("/\\")
            rel = progress_text.lstrip("/\\")
            remote_path = (
                f"{base}/"
                f"{rel}"
            )
            remote_paths = [
                remote_path,
                f"{base}/blobs/code/{rel}",
            ]
        remote_path = remote_path.replace("\\", "/")
        path_entries = []
        for candidate in remote_paths:
            safe_candidate = candidate.replace("\\", "/").replace("'", "''")
            path_entries.append(f"'{safe_candidate}'")
        path_list = ", ".join(path_entries)
        ps = (
            f"$paths = @({path_list}); "
            "foreach ($p in $paths) { "
            "if (Test-Path -LiteralPath $p) { "
            "Write-Output \"__V2_PROGRESS_PATH__=$p\"; "
            "Get-Content -LiteralPath $p -Tail 1 -ErrorAction SilentlyContinue; "
            "break "
            "} "
            "}"
        )
        try:
            from .transport import remote_run
            result = remote_run(host_alias=js.host, powershell_script=ps, timeout=8)
        except Exception:
            return None
        if result.returncode != 0:
            return None
        actual_remote_path = remote_path
        for line in (result.stdout or "").splitlines():
            line = line.strip()
            if line.startswith("__V2_PROGRESS_PATH__="):
                actual_remote_path = line.split("=", 1)[1].strip() or remote_path
        for line in reversed((result.stdout or "").splitlines()):
            line = line.strip()
            if not line or line.startswith("__V2_PROGRESS_PATH__="):
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                payload.setdefault("remote_progress_path", actual_remote_path)
                return payload
        return None

    def _mark_remaining_skipped(self, remaining_layers: list[list[JobSpec]]) -> None:
        for layer in remaining_layers:
            for j in layer:
                js = self.state.jobs[j.name]
                if not js.is_terminal():
                    js.status = "skipped"
                    js.last_error = "batch stopped early"
                    js.finished_at = _now_iso()
        self._save_state()

    # ----- Misc -----

    def _next_job_id(self) -> int:
        """Pull a fleet job_id from ~/.fleet/state.json (shared registry).

        Wrapped in an in-process lock so two threads in the same process
        don't grab the same id (fcntl is per-process, so the cross-
        package state.py lock doesn't protect intra-process callers).
        """
        with self._job_id_lock:
            sys.path.insert(0, str(_orchestration_root()))
            try:
                from fleet import load_state, save_state
                st = load_state()
                jid = st["next_job_id"]
                st["next_job_id"] = jid + 1
                save_state(st)
                return jid
            except Exception:
                # Fallback: monotonic counter in state file (only used when fleet
                # state.json is unreachable, eg. in unit tests).
                if "_local_job_counter" not in self.state.policy:
                    self.state.policy["_local_job_counter"] = 1
                jid = self.state.policy["_local_job_counter"]
                self.state.policy["_local_job_counter"] = jid + 1
                return jid

    def _real_submit(self, manifest, bundle_dir: pathlib.Path,
                     *, keep_remote_workdir: bool = False) -> dict:
        """Default submit: dispatch via v2.submit.submit_one (blocking).

        ``keep_remote_workdir`` is forwarded to submit_one — set by
        _run_one_attempt when a downstream job will rsync from this
        upstream's remote workdir. The batch executor handles deferred
        cleanup via _cleanup_kept_workdirs() after the batch finishes.
        """
        from .submit import submit_one
        return submit_one(
            manifest,
            bundle_out_dir=bundle_dir,
            keep_remote_workdir=keep_remote_workdir,
        )

    def _save_state(self) -> None:
        """Atomic write to state_path. Lock-protected: two worker threads
        racing on the same .tmp filename → one's os.replace fails with
        ENOENT (the other already moved the file). Holding _state_lock
        serialises the write + rename pair."""
        with self._state_lock:
            tmp = self.state_path.with_suffix(self.state_path.suffix + ".tmp")
            tmp.write_text(json.dumps(self.state.to_dict(), indent=2, default=str))
            os.replace(tmp, self.state_path)


# ---------------------------------------------------------------------------
# Heartbeat ticker — background thread that bumps heartbeat_at on running
# jobs every N seconds. Lets `v2 batch doctor` distinguish "still running"
# from "the orchestrator died and these are ghosts".
# ---------------------------------------------------------------------------

class _Heartbeat:
    """A daemon thread that periodically writes a wall-clock tick to
    every "running" JobState. Stops cleanly when ``stop()`` is called or
    the BatchExecutor exits its run() context."""

    def __init__(self, executor: "BatchExecutor", interval_s: int):
        self._exec = executor
        self._interval_s = max(5, int(interval_s))
        self._stop = threading.Event()
        self._thread = threading.Thread(
            target=self._loop, daemon=True, name="v2_heartbeat",
        )

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=self._interval_s + 5)

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                touched = False
                now = _now_iso()
                active_names: list[str] = []
                with self._exec._state_lock:
                    for name, js in self._exec.state.jobs.items():
                        if js.status in _ACTIVE_STATUSES:
                            js.heartbeat_at = now
                            active_names.append(name)
                            touched = True
                progress_updates: dict[str, dict] = {}
                for name in active_names:
                    progress = self._exec._read_job_progress(name)
                    if progress:
                        progress_updates[name] = progress
                if progress_updates:
                    with self._exec._state_lock:
                        for name, progress in progress_updates.items():
                            js = self._exec.state.jobs.get(name)
                            if js and js.status in _ACTIVE_STATUSES:
                                js.progress = progress
                                touched = True
                if touched:
                    self._exec._save_state()
            except Exception:
                # Heartbeat errors are non-fatal; don't crash the batch.
                pass
            # Sleep is interruptible so stop() returns promptly.
            self._stop.wait(self._interval_s)


def _progress_heartbeat_age_s(progress, now_utc):
    """Age (seconds) of the REMOTE build's own progress heartbeat
    (``progress['heartbeat_utc']`` — an aware-UTC ISO timestamp emitted per
    chunk by run_full_regen). Returns None when absent/unparseable.

    This is the signal the outer ``heartbeat_at`` masks: the orchestrator's
    ticker keeps bumping heartbeat_at long after the remote build froze, so a
    stalled build is only visible through the progress heartbeat."""
    if not isinstance(progress, dict):
        return None
    raw = progress.get("heartbeat_utc")
    if not raw:
        return None
    try:
        ts = dt.datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=dt.timezone.utc)
    return (now_utc - ts).total_seconds()


def diagnose_batch(state_path: pathlib.Path | str) -> dict:
    """Scan a batch state file for stale-heartbeat jobs. Returns a report
    {"alive": [...], "ghosts": [...], "summary": {...}}.

    A "ghost" is an active JobState whose heartbeat_at is older than the
    policy's heartbeat_threshold_s. Almost always means
    the Mac orchestrator died and the state file was left stale.

    Operator action on a ghost: edit the state file to flip its status
    to "interrupted", then `v2 batch resume` to retry.
    """
    state_path = pathlib.Path(state_path)
    if not state_path.is_file():
        return {"error": f"state file not found: {state_path}"}
    bs = BatchState.from_dict(json.loads(state_path.read_text()))
    threshold_s = (bs.policy or {}).get("heartbeat_threshold_s", 150)
    prog_threshold_s = (bs.policy or {}).get(
        "progress_heartbeat_threshold_s", _DEFAULT_PROGRESS_HEARTBEAT_THRESHOLD_S)
    now = dt.datetime.now()
    now_utc = dt.datetime.now(dt.timezone.utc)
    alive: list[dict] = []
    ghosts: list[dict] = []
    for j in bs.jobs.values():
        if j.status not in _ACTIVE_STATUSES:
            continue
        reasons: list[str] = []
        age_s: float | None = None
        if not j.heartbeat_at:
            reasons.append("no heartbeat_at recorded")
        else:
            try:
                hb = dt.datetime.fromisoformat(j.heartbeat_at)
            except ValueError:
                reasons.append(f"invalid heartbeat_at: {j.heartbeat_at!r}")
            else:
                age_s = (now - hb).total_seconds()
                if age_s > threshold_s:
                    reasons.append(f"heartbeat stale by {int(age_s)}s")
        # Remote build-progress heartbeat: catches a frozen build the warm
        # outer heartbeat_at would otherwise hide.
        prog_age = _progress_heartbeat_age_s(j.progress, now_utc)
        if prog_age is not None and prog_age > prog_threshold_s:
            reasons.append(f"build progress stale by {int(prog_age)}s")
        if reasons:
            entry = {"name": j.name, "host": j.host,
                     "reason": "; ".join(reasons), "started_at": j.started_at}
            if j.heartbeat_at:
                entry["heartbeat_at"] = j.heartbeat_at
            ghosts.append(entry)
        else:
            entry = {"name": j.name, "host": j.host}
            if age_s is not None:
                entry["heartbeat_age_s"] = int(age_s)
            alive.append(entry)
    return {
        "state_file": str(state_path),
        "batch": bs.batch,
        "threshold_s": threshold_s,
        "progress_threshold_s": prog_threshold_s,
        "summary": {"alive": len(alive), "ghosts": len(ghosts)},
        "alive": alive,
        "ghosts": ghosts,
    }


# ---------------------------------------------------------------------------
# State-file recovery + cross-batch listing
# ---------------------------------------------------------------------------

def _rebuild_state_from_disk(batch_path: pathlib.Path,
                              *,
                              bundle_out_root: pathlib.Path | None = None) -> dict:
    """Rebuild a batch's state.json by scanning the per-bundle pulled/
    dirs. Each job that has a pulled/<v2_job_id>/status.json with
    exit_code=0 is marked "succeeded"; non-zero exit_code → "failed";
    anything missing → "pending".

    Returned dict has the same shape as BatchState.to_dict() and can be
    written straight to disk as a fresh state file. Operator can then
    `batch resume` to retry the non-succeeded jobs.
    """
    bs = BatchSpec.from_path(batch_path)
    bundle_out_root = pathlib.Path(
        bundle_out_root or (v2_bundles_root() / "batches")
    )

    rebuilt: dict[str, dict] = {}
    counts: dict[str, int] = {}
    for j in bs.jobs:
        # Look for any bundle dir that ends with this job's _safe name.
        # Multiple may exist (retries); take the most-recent one.
        safe = _safe(j.name)
        candidates = sorted(
            bundle_out_root.glob(f"job_*_{safe}*"),
            key=lambda p: p.stat().st_mtime, reverse=True,
        )
        if not candidates:
            rebuilt[j.name] = {"name": j.name, "status": "pending",
                               "attempts": 0, "post_pull_errors": []}
            counts["pending"] = counts.get("pending", 0) + 1
            continue
        bd = candidates[0]
        # The v2_job_id lives in <bd>/manifest.json
        mf = bd / "manifest.json"
        if not mf.is_file():
            rebuilt[j.name] = {"name": j.name, "status": "pending",
                               "attempts": 0,
                               "last_error": f"no manifest.json in {bd}",
                               "post_pull_errors": []}
            counts["pending"] = counts.get("pending", 0) + 1
            continue
        try:
            mn = json.loads(mf.read_text())
            v2_id = mn["job_id"]
            # Extract the host the job ran on so downstream jobs with
            # affinity to this job can re-resolve their target.
            host = (mn.get("host") or {}).get("ssh_alias")
            # Remote workdir for remote_ref lookups by downstream jobs.
            base = remote_workdir_default(mn.get("host") or {})
            remote_workdir = f"{base}/{v2_id}"
        except Exception as e:
            rebuilt[j.name] = {"name": j.name, "status": "pending",
                               "attempts": 0,
                               "last_error": f"bad manifest: {e}",
                               "post_pull_errors": []}
            counts["pending"] = counts.get("pending", 0) + 1
            continue
        pulled_status = bd / "pulled" / v2_id / "status.json"
        if not pulled_status.is_file():
            rebuilt[j.name] = {"name": j.name, "status": "interrupted",
                               "attempts": 1, "bundle_dir_local": str(bd),
                               "v2_job_id": v2_id,
                               "host": host,
                               "remote_workdir": remote_workdir,
                               "post_pull_errors": [],
                               "last_error": "no pulled status.json — likely interrupted"}
            counts["interrupted"] = counts.get("interrupted", 0) + 1
            continue
        try:
            st = json.loads(pulled_status.read_text())
            rc = st.get("exit_code", 1)
        except Exception:
            rc = 1
        status = "succeeded" if rc == 0 else "failed"
        rebuilt[j.name] = {
            "name": j.name, "status": status, "exit_code": rc,
            "attempts": 1, "bundle_dir_local": str(bd),
            "v2_job_id": v2_id,
            "host": host,
            "remote_workdir": remote_workdir,
            "post_pull_errors": [],
        }
        counts[status] = counts.get(status, 0) + 1

    return {
        "batch": bs.batch,
        "started_at": _now_iso(),
        "finished_at": None,
        "policy": bs.policy,
        "state_path": None,
        "jobs": rebuilt,
        "status_counts": counts,
    }


def list_batches(root: pathlib.Path) -> list[dict]:
    """Walk a dir for batch state files; return a row per discovered batch.

    Each row: {batch, started_at, finished_at, state_path, status_counts}.
    """
    out: list[dict] = []
    if not root.is_dir():
        return out
    for sp in sorted(root.glob("*_state.json")):
        try:
            bs = BatchState.from_dict(json.loads(sp.read_text()))
        except Exception:
            continue
        counts: dict[str, int] = {}
        for j in bs.jobs.values():
            counts[j.status] = counts.get(j.status, 0) + 1
        out.append({
            "batch": bs.batch,
            "started_at": bs.started_at,
            "finished_at": bs.finished_at,
            "state_path": str(sp),
            "status_counts": counts,
        })
    return out


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _orchestration_root() -> pathlib.Path:
    """utils/offload_network/ — where fleet.py lives."""
    return pathlib.Path(__file__).resolve().parent.parent


def _safe(s: str) -> str:
    """Strip path-unsafe chars from a job name."""
    return "".join(c if c.isalnum() or c in "-_." else "_" for c in s)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def submit_batch(
    batch_path: str | pathlib.Path,
    hosts: dict,
    *,
    state_path: str | pathlib.Path | None = None,
    bundle_out_root: str | pathlib.Path | None = None,
    dry_run: bool = False,
) -> BatchState:
    """Convenience wrapper: load a batch.json, run it to completion."""
    bs = BatchSpec.from_path(batch_path)
    ex = BatchExecutor(
        bs, hosts,
        state_path=state_path,
        bundle_out_root=bundle_out_root,
        dry_run=dry_run,
    )
    return ex.run()
