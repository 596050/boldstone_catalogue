"""End-to-end submit for one or many sealed jobs.

Lifecycle per job:
  build_seal   →  push_seal   →  launch  →  poll  →  pull_result  →  cleanup

The submit_one function is synchronous (blocks until result pulled).
submit_many runs many submit_one calls in a thread pool with a
configurable per-host concurrency cap.
"""
from __future__ import annotations

import concurrent.futures
import pathlib
import time
from typing import Optional, Callable

from .manifest import SealedManifest, SealError, SealStatus
from .seal import build_seal
from .transport import push_seal, remote_remove
from .launcher import launch, read_remote_status
from .result import fetch_and_unpack


def submit_one(
    manifest: SealedManifest,
    *,
    bundle_out_dir: pathlib.Path | str,
    poll_interval_s: float = 15.0,
    deadline_s: Optional[float] = None,
    keep_remote_workdir: bool = False,
    on_state_change: Optional[Callable[[SealedManifest, str, dict], None]] = None,
) -> dict:
    """Build, push, launch, poll, pull, optionally cleanup. Returns a
    summary dict with timings + result info."""
    started = time.monotonic()
    timings: dict = {"started_at": time.time(), "elapsed_clock": "time.monotonic"}

    def _emit(stage: str, info: dict) -> None:
        if on_state_change:
            try:
                on_state_change(manifest, stage, info)
            except Exception:
                pass

    # Track artifacts, but only authorize cleanup after verified local retention.
    # Failed status, deadlines and interrupted transfers preserve remote evidence.
    seal_path: Optional[pathlib.Path] = None
    remote_seal_path: Optional[str] = None
    launch_info: Optional[dict] = None
    result_retained = False

    def _cleanup_remote() -> None:
        if keep_remote_workdir or not result_retained:
            return  # deliberately kept (e.g. referenced outputs); GC'd elsewhere
        ct0 = time.monotonic()
        if launch_info is not None:
            try:
                remote_remove(
                    host_alias=manifest.host.ssh_alias,
                    remote_path=launch_info["workdir"],
                    platform=manifest.host.platform,
                )
            except Exception:
                pass
        if remote_seal_path is not None and seal_path is not None:
            try:
                seal_remote_dir = manifest.host.remote_workdir.rstrip("/\\")
                remote_remove(host_alias=manifest.host.ssh_alias,
                              remote_path=f"{seal_remote_dir}/{seal_path.name}",
                              platform=manifest.host.platform)
            except Exception:
                pass
        timings["cleanup_s"] = round(time.monotonic() - ct0, 1)

    try:
        # 1. Build
        t0 = time.monotonic()
        seal_path = build_seal(manifest, out_dir=bundle_out_dir)
        timings["build_s"] = round(time.monotonic() - t0, 1)
        _emit("sealed", {"seal_path": str(seal_path), "size_bytes": manifest.seal_size_bytes})

        # 2. Push
        t0 = time.monotonic()
        remote_seal_path = push_seal(
            seal_path_local=seal_path,
            host_alias=manifest.host.ssh_alias,
            remote_workdir=manifest.host.remote_workdir,
            rsync_path=manifest.host.rsync_path,
            platform=manifest.host.platform,
        )
        timings["push_s"] = round(time.monotonic() - t0, 1)
        manifest.status = SealStatus.PUSHED
        _emit("pushed", {"remote_seal_path": remote_seal_path})

        # 3. Launch
        t0 = time.monotonic()
        launch_info = launch(manifest, seal_remote_path=remote_seal_path)
        timings["launch_s"] = round(time.monotonic() - t0, 1)
        _emit("running", launch_info)

        # 4. Poll
        t0 = time.monotonic()
        status: Optional[dict] = None
        while True:
            if deadline_s is not None and (time.monotonic() - started) > deadline_s:
                raise SealError(f"submit_one: job {manifest.job_id} exceeded deadline {deadline_s}s")
            status = read_remote_status(
                manifest.host.ssh_alias, launch_info["status_path"],
                platform=manifest.host.platform,
            )
            if status:
                phase = status.get("phase", "")
                if phase in ("exited", "exited_pack_failed", "failed"):
                    break
            time.sleep(poll_interval_s)
        timings["poll_s"] = round(time.monotonic() - t0, 1)
        timings["remote_elapsed_s"] = status.get("elapsed_s") if status else None
        timings["remote_elapsed_clock"] = status.get("elapsed_clock") if status else None
        _emit("finished", {"status": status})

        if status.get("phase") == "failed":
            manifest.status = SealStatus.FAILED
            manifest.last_error = status.get("error")
            return {"manifest": manifest, "timings": timings, "status": status, "result": None}

        # 5. Pull + extract
        t0 = time.monotonic()
        result_info = fetch_and_unpack(
            manifest,
            workdir_remote=launch_info["workdir"],
            pull_into=pathlib.Path(bundle_out_dir) / "results",
            remote_status=status,
        )
        result_retained = True
        timings["pull_s"] = round(time.monotonic() - t0, 1)
        _emit("pulled", result_info)

        timings["total_s"] = round(time.monotonic() - started, 1)
        return {
            "manifest": manifest,
            "timings": timings,
            "status": status,
            "result": result_info,
        }
    finally:
        # Never discard the only result/evidence on timeout or failed retrieval.
        _cleanup_remote()


def submit_many(
    manifests: list[SealedManifest],
    *,
    bundle_out_dir: pathlib.Path | str,
    max_workers: int = 8,
    max_parallel_per_host: int = 2,
    poll_interval_s: float = 15.0,
    deadline_s: Optional[float] = None,
    keep_remote_workdir: bool = False,
    on_state_change: Optional[Callable[[SealedManifest, str, dict], None]] = None,
) -> list[dict]:
    """Submit many sealed jobs in parallel with a per-host throttle.

    Returns a list of submit_one result dicts (one per manifest, in the
    same order as input).  Submit errors are captured per-job and never
    cancel the rest of the batch."""
    import threading
    per_host_sem: dict[str, threading.Semaphore] = {}
    lock = threading.Lock()

    def _semaphore_for(host: str) -> threading.Semaphore:
        with lock:
            if host not in per_host_sem:
                per_host_sem[host] = threading.Semaphore(max_parallel_per_host)
            return per_host_sem[host]

    def _run(m: SealedManifest) -> dict:
        sem = _semaphore_for(m.host.ssh_alias)
        sem.acquire()
        try:
            return submit_one(
                m,
                bundle_out_dir=bundle_out_dir,
                poll_interval_s=poll_interval_s,
                deadline_s=deadline_s,
                keep_remote_workdir=keep_remote_workdir,
                on_state_change=on_state_change,
            )
        except Exception as e:
            return {"manifest": m, "error": f"{type(e).__name__}: {e}"}
        finally:
            sem.release()

    results: list[dict] = [None] * len(manifests)  # type: ignore
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(_run, m): i for i, m in enumerate(manifests)}
        for fut in concurrent.futures.as_completed(futures):
            i = futures[fut]
            try:
                results[i] = fut.result()
            except Exception as e:
                results[i] = {"manifest": manifests[i], "error": f"{type(e).__name__}: {e}"}
    return results
