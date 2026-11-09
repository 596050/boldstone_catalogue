"""Filesystem-only simulation of the sealed offload lifecycle.

The simulator exercises the real v2 seal and remote runner while replacing
SSH/rsync with explicit controller, inbox, job, outbox, and result directories.
It is safe to run on one machine and models workers labelled Windows, Linux,
or macOS without claiming to emulate their kernels.
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tarfile
import time
import traceback
import uuid
from datetime import datetime, timezone
from typing import Optional

from v2.manifest import HostSpec, ResultSpec, SealedBlob, SealedManifest
from v2.result import _safe_extract
from v2.seal import build_seal, extract_seal, verify_seal
from lib.file_lock import file_lock
from lib.process_tree import clean_environment, run_tree


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _sha256(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _atomic_json(path: pathlib.Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f".{uuid.uuid4().hex}.tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str))
    os.replace(temporary, path)


@dataclasses.dataclass(frozen=True)
class SourceRequest:
    """One requested file or directory from a configured source root."""

    source: str
    path: str
    rel_path: str
    name: str = "source"


@dataclasses.dataclass
class JobRequest:
    entrypoint: str
    worker: str
    args: list[str] = dataclasses.field(default_factory=list)
    metadata: dict = dataclasses.field(default_factory=dict)
    sources: list[SourceRequest] = dataclasses.field(default_factory=list)
    env: dict = dataclasses.field(default_factory=dict)
    include_patterns: list[str] = dataclasses.field(
        default_factory=lambda: ["*.json", "*.log", "artifacts/**"]
    )
    timeout_s: float = 30.0
    job_id: str = ""

    def __post_init__(self) -> None:
        if not self.job_id:
            self.job_id = f"sim-{uuid.uuid4().hex[:12]}"


class SimulatedNetwork:
    """Durable local queue using the production seal and runner formats."""

    def __init__(
        self,
        root: pathlib.Path | str,
        *,
        workers: dict[str, str],
        sources: dict[str, pathlib.Path | str],
    ) -> None:
        self.root = pathlib.Path(root).resolve()
        self.workers = dict(workers)
        self.sources = {name: pathlib.Path(path).resolve() for name, path in sources.items()}
        self.controller = self.root / "controller"
        for child in ("queue/pending", "queue/running", "queue/completed",
                      "queue/failed", "bundles", "results", "receipts"):
            (self.controller / child).mkdir(parents=True, exist_ok=True)
        for worker, os_name in self.workers.items():
            if os_name not in {"windows", "linux", "macos"}:
                raise ValueError(f"unsupported simulated OS label: {os_name}")
            for child in ("inbox", "jobs", "outbox"):
                (self.root / "hosts" / worker / child).mkdir(parents=True, exist_ok=True)
        for source, path in self.sources.items():
            if not path.exists():
                raise FileNotFoundError(f"configured source {source!r} does not exist: {path}")
        self.recover()
        _atomic_json(self.root / "network.json", {
            "created_at": _now(), "workers": self.workers,
            "sources": {k: str(v) for k, v in self.sources.items()},
        })

    def enqueue(self, request: JobRequest) -> str:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{3,79}", request.job_id):
            raise ValueError("invalid job ID")
        if request.timeout_s <= 0:
            raise ValueError("timeout must be positive")
        if request.worker not in self.workers:
            raise ValueError(f"unknown worker {request.worker!r}")
        entrypoint = pathlib.Path(request.entrypoint).resolve()
        if not entrypoint.is_file():
            raise FileNotFoundError(f"entrypoint does not exist: {entrypoint}")
        payload = dataclasses.asdict(request)
        payload["entrypoint"] = str(entrypoint)
        payload["enqueued_at"] = _now()
        payload["state"] = "pending"
        with file_lock(self.controller / "queue.lock"):
            if any((self.controller / "queue" / state / f"{request.job_id}.json").exists()
                   for state in ("pending", "running", "completed", "failed")):
                raise ValueError(f"job ID already exists: {request.job_id}")
            payload["sequence"] = time.time_ns()
            try:
                manifest = self._seal_request(request)
                payload["sealed_manifest"] = manifest.to_dict()
            except Exception as exc:
                payload["admission_error"] = {"type": type(exc).__name__, "message": str(exc)}
            _atomic_json(self.controller / "queue/pending" / f"{request.job_id}.json", payload)
        return request.job_id

    def process_next(self, worker: Optional[str] = None) -> Optional[dict]:
        claim = None
        with file_lock(self.controller / "queue.lock"):
            pending = [(p, json.loads(p.read_text()))
                       for p in (self.controller / "queue/pending").glob("*.json")]
            pending.sort(key=lambda item: (item[1].get("sequence", 0), item[1].get("enqueued_at", "")))
            for queue_path, raw in pending:
                if worker is not None and raw["worker"] != worker:
                    continue
                claim = file_lock(self.controller / "claims" / (queue_path.stem + ".lock"), timeout=0)
                claim.__enter__()
                running_path = self.controller / "queue/running" / queue_path.name
                os.replace(queue_path, running_path)
                break
        if claim is None:
            return None
        try:
            fields = {f.name for f in dataclasses.fields(JobRequest)}
            raw = {k: v for k, v in raw.items() if k in fields}
            raw["sources"] = [SourceRequest(**item) for item in raw.get("sources", [])]
            return self._execute(JobRequest(**raw), running_path)
        finally:
            claim.__exit__(None, None, None)

    def recover(self):
        """Record abandoned claims as interrupted; never silently replay a job."""
        with file_lock(self.controller / "queue.lock"):
            for path in (self.controller / "queue/running").glob("*.json"):
                try:
                    with file_lock(self.controller / "claims" / (path.stem + ".lock"), timeout=0):
                        raw = json.loads(path.read_text())
                        receipt = self.controller / "receipts" / path.name
                        if not receipt.exists():
                            _atomic_json(receipt, {"job_id": raw["job_id"], "status": "failed",
                                "error": {"type": "Interrupted", "message": "previous controller stopped"},
                                "finished_at": _now()})
                        raw.update(state="failed", receipt=str(receipt))
                        _atomic_json(self.controller / "queue/failed" / path.name, raw)
                        path.unlink()
                except TimeoutError:
                    continue

    def _seal_request(self, request):
        worker_root = self.root / "hosts" / request.worker
        manifest = SealedManifest(
            job_id=request.job_id, task_type="simulated-generic",
            metadata={**request.metadata, "simulated_worker_os": self.workers[request.worker]},
            host=HostSpec(ssh_alias=request.worker, remote_workdir=str(worker_root / "jobs"),
                          platform=self.workers[request.worker], python_executable=sys.executable),
            blobs=[SealedBlob(name="entrypoint", local_src=request.entrypoint,
                              rel_path="code/entrypoint.py")]
                  + [self._source_blob(s) for s in request.sources],
            entrypoint_rel="code/entrypoint.py", run_args=request.args, env=request.env,
            result=ResultSpec(local_dir=str(self.controller / "results" / request.job_id),
                              include_patterns=request.include_patterns))
        build_seal(manifest, out_dir=self.controller / "bundles")
        verify_seal(manifest.seal_path_local, expected_sha256=manifest.seal_sha256)
        return manifest

    def drain(self) -> list[dict]:
        envelopes = []
        while True:
            envelope = self.process_next()
            if envelope is None:
                return envelopes
            envelopes.append(envelope)

    def _source_blob(self, item: SourceRequest) -> SealedBlob:
        if item.source not in self.sources:
            raise KeyError(f"source {item.source!r} is not configured")
        root = self.sources[item.source]
        candidate = (root / item.path).resolve()
        try:
            candidate.relative_to(root)
        except ValueError as exc:
            raise ValueError(f"source request escapes root: {item.path!r}") from exc
        if not candidate.exists():
            raise FileNotFoundError(
                f"source {item.source!r} has no requested path {item.path!r}"
            )
        return SealedBlob(
            name=item.name,
            local_src=str(candidate),
            rel_path=item.rel_path,
            is_dir=candidate.is_dir(),
        )

    def _execute(self, request: JobRequest, running_path: pathlib.Path) -> dict:
        started = time.monotonic()
        stages: list[dict] = []
        worker_root = self.root / "hosts" / request.worker
        job_dir = worker_root / "jobs" / request.job_id
        result_dir = self.controller / "results" / request.job_id
        receipt_path = self.controller / "receipts" / f"{request.job_id}.json"
        envelope = {
            "job_id": request.job_id,
            "worker": request.worker,
            "worker_os": self.workers[request.worker],
            "metadata": request.metadata,
            "status": "failed",
            "exit_code": None,
            "error": None,
            "stages": stages,
            "created_at": _now(),
        }

        def stage(name: str, **details: object) -> None:
            stages.append({"name": name, "at": _now(), **details})

        try:
            record = json.loads(running_path.read_text())
            if record.get("admission_error"):
                envelope["error"] = {**record["admission_error"], "stage": "admission"}
                raise RuntimeError(record["admission_error"]["message"])
            if "sealed_manifest" not in record:
                raise RuntimeError("legacy unsealed queue request; resubmit with a new identity")
            manifest = SealedManifest.from_dict(record["sealed_manifest"])
            seal = pathlib.Path(manifest.seal_path_local)
            verify_seal(seal, expected_sha256=manifest.seal_sha256)
            stage("sealed", sha256=manifest.seal_sha256, size_bytes=seal.stat().st_size)

            inbox_seal = worker_root / "inbox" / seal.name
            shutil.copy2(seal, inbox_seal)
            stage("transferred_to_worker", sha256=_sha256(inbox_seal))
            job_dir.mkdir(parents=True, exist_ok=False)
            extract_seal(inbox_seal, out_dir=job_dir)
            stage("isolated", workdir=str(job_dir))

            command = [sys.executable, str(job_dir / "runner.py"), str(job_dir / "manifest.json")]
            try:
                completed = run_tree(command, cwd=job_dir, timeout=request.timeout_s,
                                     env=clean_environment())
                envelope["exit_code"] = completed.returncode
            except subprocess.TimeoutExpired:
                envelope["error"] = {
                    "type": "TimeoutExpired",
                    "message": f"job exceeded {request.timeout_s}s",
                    "stage": "running",
                }
                stage("timed_out", timeout_s=request.timeout_s)
                raise

            status_path = job_dir / "status.json"
            status = json.loads(status_path.read_text()) if status_path.exists() else {}
            envelope["remote_status"] = status
            stage("runner_finished", phase=status.get("phase"), exit_code=envelope["exit_code"])

            archive_name = status.get("result_archive")
            if not archive_name:
                raise RuntimeError(f"runner did not produce a result archive: {status}")
            remote_archive = pathlib.Path(archive_name)
            outbox_archive = worker_root / "outbox" / remote_archive.name
            shutil.copy2(remote_archive, outbox_archive)
            controller_archive = self.controller / "results" / remote_archive.name
            controller_archive.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(outbox_archive, controller_archive)
            result_dir.mkdir(parents=True, exist_ok=True)
            n_files = _safe_extract(controller_archive, result_dir)
            stage("result_returned", sha256=_sha256(controller_archive), n_files=n_files)
            envelope["result"] = {
                "archive": str(controller_archive),
                "directory": str(result_dir),
                "sha256": _sha256(controller_archive),
                "n_files": n_files,
            }
            if envelope["exit_code"] == 0 and status.get("phase") == "exited":
                envelope["status"] = "succeeded"
            else:
                envelope["error"] = {
                    "type": "RemoteJobError",
                    "message": f"remote exit code {envelope['exit_code']}",
                    "stage": "entrypoint",
                }
        except subprocess.TimeoutExpired:
            pass
        except Exception as exc:
            envelope["error"] = envelope["error"] or {
                "type": type(exc).__name__, "message": str(exc),
                "stage": stages[-1]["name"] if stages else "prepare",
                "traceback": traceback.format_exc(),
            }
        finally:
            envelope["elapsed_s"] = round(time.monotonic() - started, 3)
            envelope["finished_at"] = _now()
            terminal = "completed" if envelope["status"] == "succeeded" else "failed"
            _atomic_json(receipt_path, envelope)
            terminal_path = self.controller / "queue" / terminal / running_path.name
            queue_record = json.loads(running_path.read_text())
            queue_record.update({"state": terminal, "receipt": str(receipt_path)})
            _atomic_json(terminal_path, queue_record)
            running_path.unlink()
        return envelope


def initialise_demo(root: pathlib.Path | str) -> SimulatedNetwork:
    """Create the requested three-host directory topology."""
    root = pathlib.Path(root).resolve()
    source_root = root / "configured_sources" / "market_data"
    source_root.mkdir(parents=True, exist_ok=True)
    return SimulatedNetwork(
        root,
        workers={"windows-01": "windows", "linux-01": "linux", "mac-01": "macos"},
        sources={"market-data": source_root},
    )
