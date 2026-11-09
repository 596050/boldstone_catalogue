"""Worker-owned templates, immutable admission, durable claims and receipts.

One process holds the store lock, with multiple execution threads. SQLite
transactions provide FIFO admission/claim and attempt fencing. On restart,
old containers are stopped before their jobs become terminal 'interrupted'.
Jobs are never automatically replayed: callers use a new ID for an explicit retry.
"""

from __future__ import annotations

import contextlib
import dataclasses
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from pathlib import Path

from lib.file_lock import file_lock
from lib.live_files import live_tree_bytes
from lib.process_tree import clean_environment, stop_tree
from v2.manifest import HostSpec, ResultSpec, SealedBlob, SealedManifest, sha256_of_file
from v2.result import _safe_extract
from v2.seal import build_seal, extract_seal, verify_seal

TERMINAL = {"succeeded", "failed", "cancelled", "interrupted"}
ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{3,79}\Z")


class Conflict(ValueError):
    pass


class CapacityError(ValueError):
    pass


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def atomic_json(path, value):
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    with temporary.open("x", encoding="utf-8") as stream:
        stream.write(canonical(value))
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


@dataclasses.dataclass(frozen=True)
class Template:
    name: str
    entrypoint: Path
    code_dir: Path | None = None
    data: tuple = ()  # (operator-owned source path, relative bundle path)
    image: str = "python:3.12-slim"
    env: dict = dataclasses.field(default_factory=dict)
    timeout_s: float = 300
    memory_mb: int = 512
    cpus: float = 1.0
    pids: int = 64
    max_output_mb: int = 64
    max_work_mb: int = 256
    max_input_mb: int = 1024

    @classmethod
    def load(cls, name, raw, base):
        allowed = {f.name for f in dataclasses.fields(cls)} - {"name"}
        if set(raw) - allowed:
            raise ValueError(f"unknown template fields: {set(raw) - allowed}")
        raw = dict(raw)
        for key in ("entrypoint", "code_dir"):
            if raw.get(key):
                raw[key] = (base / raw[key]).resolve()
        raw["data"] = tuple(
            ((base / d["path"]).resolve(), d["rel_path"]) for d in raw.get("data", [])
        )
        result = cls(name=name, **raw)
        if not ID.fullmatch(name) or not result.entrypoint.is_file():
            raise ValueError(f"invalid template or missing entrypoint: {name}")
        if any(not p.exists() for p, _ in result.data):
            raise ValueError(f"missing configured data for {name}")
        if result.code_dir and not result.code_dir.is_dir():
            raise ValueError(f"missing code directory for {name}")
        limits = (
            result.timeout_s,
            result.memory_mb,
            result.cpus,
            result.pids,
            result.max_output_mb,
            result.max_work_mb,
            result.max_input_mb,
        )
        if any(not isinstance(x, (int, float)) or not 0 < x < 1e9 for x in limits):
            raise ValueError("template limits must be finite and positive")
        for key in ("memory_mb", "pids", "max_output_mb", "max_work_mb", "max_input_mb"):
            if type(getattr(result, key)) is not int:
                raise ValueError(f"{key} must be a positive integer")
        if not isinstance(result.env, dict) or any(
            not isinstance(k, str) or not isinstance(v, str) or not k or "=" in k or "\0" in k + v
            for k, v in result.env.items()
        ):
            raise ValueError("template env must contain valid string keys and values")
        return result


class Worker:
    def __init__(
        self,
        root,
        templates,
        *,
        backend="docker",
        concurrency=1,
        max_pending=100,
        min_free_mb=1024,
        max_store_mb=10240,
    ):
        if backend not in {"docker", "trusted-local"}:
            raise ValueError("backend must be docker or trusted-local")
        if backend == "docker" and os.name != "nt" and os.geteuid() == 0:
            raise ValueError("run the worker under a non-root OS account with Docker access")
        if (
            type(concurrency) is not int
            or not 1 <= concurrency <= 32
            or type(max_pending) is not int
            or max_pending < 1
            or type(min_free_mb) is not int
            or min_free_mb < 0
            or type(max_store_mb) is not int
            or max_store_mb <= 0
        ):
            raise ValueError("invalid concurrency or queue capacity")
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        if "," in str(self.root):
            raise ValueError("worker root may not contain commas (Docker mount syntax)")
        self.lock = file_lock(self.root / "worker.lock", timeout=0)
        self.lock.__enter__()
        self.templates = {t.name: t for t in templates}
        self.backend = backend
        self.concurrency, self.max_pending = concurrency, max_pending
        self.min_free_mb, self.max_store_mb = min_free_mb, max_store_mb
        self.stop = threading.Event()
        self.wake = threading.Event()
        self.threads = []
        self.admission = threading.Lock()
        self.db_lock = threading.RLock()
        self.images = {}
        self.closed = False
        self.worker_instance = uuid.uuid4().hex
        try:
            self.db = sqlite3.connect(
                self.root / "jobs.sqlite3",
                timeout=30,
                isolation_level=None,
                check_same_thread=False,
            )
            self.db.row_factory = sqlite3.Row
            self.db.execute("PRAGMA journal_mode=WAL")
            self.db.execute("PRAGMA synchronous=FULL")
            self.db.executescript("""
                CREATE TABLE IF NOT EXISTS jobs (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    id TEXT UNIQUE NOT NULL, request TEXT NOT NULL, state TEXT NOT NULL,
                    created REAL NOT NULL, updated REAL NOT NULL,
                    attempt TEXT, cancel INTEGER NOT NULL DEFAULT 0,
                    payload TEXT, receipt TEXT, acknowledged TEXT);
                CREATE INDEX IF NOT EXISTS jobs_state ON jobs(state, sequence);
                CREATE UNIQUE INDEX IF NOT EXISTS jobs_portable_id ON jobs(lower(id));
            """)
            for name in ("bundles", "work", "results", "receipts"):
                (self.root / name).mkdir(exist_ok=True)
            if backend == "docker":
                self._docker("info", "--format", "{{.OSType}}", expected="linux")
                for t in templates:
                    # Resolve tags once. Admission persists immutable image IDs;
                    # docker create --pull=never cannot silently fetch a replacement.
                    reference = t.image
                    # Docker's containerd image store may require canonical Hub
                    # names for inspect even when run accepts short names.
                    if "/" not in reference and not reference.startswith("sha256:"):
                        reference = "docker.io/library/" + reference
                    image = self._docker("image", "inspect", "--format", "{{.Id}}", reference)
                    if not re.fullmatch(r"sha256:[0-9a-f]{64}", image):
                        raise ValueError(f"invalid Docker image identity: {t.name}")
                    self.images[t.name] = image
            self._recover()
        except BaseException:
            if hasattr(self, "db"):
                self.db.close()
            self.lock.__exit__(None, None, None)
            raise

    def _docker(self, *args, expected=None):
        result = subprocess.run(["docker", *args], capture_output=True, text=True, timeout=60)
        if result.returncode or (expected and result.stdout.strip() != expected):
            raise RuntimeError(f"Docker operation failed ({args[0]}): {result.stderr[:500]}")
        return result.stdout.strip()

    def _remove_container(self, name):
        if not re.fullmatch(r"offload-[0-9a-f]{32}", name):
            raise ValueError("invalid persisted container attempt name")
        # No global prune/kill: only this persisted, unpredictable attempt name.
        result = subprocess.run(
            ["docker", "container", "rm", "--force", name],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode and "No such container" not in result.stderr:
            raise RuntimeError("could not stop previous job container; recovery blocked")

    def _resolve_timed_out_create(self, attempt, payload):
        """Observe the owned workload before releasing an uncertain create.

        Killing the Docker client does not establish that its daemon request
        stopped. A missing-container reply cannot permit volume cleanup: the
        pending create can subsequently recreate those names with empty inputs.
        Keep the attempt reserved until its matching workload is observable.
        """
        if not re.fullmatch(r"offload-[0-9a-f]{32}", attempt):
            raise ValueError("invalid persisted container attempt name")
        found = json.loads(self._docker("container", "inspect", attempt))
        if not isinstance(found, list) or len(found) != 1 or not isinstance(found[0], dict):
            raise RuntimeError("timed-out Docker create remains unresolved")
        item = found[0]
        config = item.get("Config") or {}
        work = self.root / "work" / attempt
        mounts = item.get("Mounts") or []
        if (not re.fullmatch(r"[0-9a-f]{64}", item.get("Id", ""))
                or item.get("Name") != "/" + attempt
                or item.get("Image") != payload["image_id"]
                or config.get("Entrypoint") != ["python"]
                or config.get("Cmd") != ["-I", "/work/runner.py", "/work/manifest.json"]
                or config.get("WorkingDir") != "/work"
                or not any(m.get("Destination") == "/work" and m.get("Type") == "bind"
                           and m.get("Source") == str(work) and m.get("RW") is True
                           for m in mounts)):
            raise RuntimeError("timed-out Docker create does not match the owned workload")
        return {"container_id": item["Id"], "observed_at": time.time(),
                "state": item.get("State"), "workload_started_by_recovery": False}

    @contextlib.contextmanager
    def transaction(self):
        with self.db_lock:
            self.db.execute("BEGIN IMMEDIATE")
            try:
                yield self.db
            except BaseException:
                self.db.execute("ROLLBACK")
                raise
            else:
                self.db.execute("COMMIT")

    def _recover(self):
        rows = self.db.execute(
            "SELECT * FROM jobs WHERE state IN ('preparing','running')"
        ).fetchall()
        for row in rows:
            payload = json.loads(row["payload"] or "{}")
            previous = json.loads(row["receipt"] or "{}")
            recovered_create = None
            if row["attempt"] and payload.get("backend") == "docker":
                if previous.get("docker_create_uncertain"):
                    resolution = previous.get("docker_create_resolution")
                    if resolution is None:
                        resolution = self._resolve_timed_out_create(row["attempt"], payload)
                        # Removal itself can time out after succeeding. Retain
                        # the positive observation first so another recovery
                        # can accept absence without repeating an unresolved
                        # creation probe or releasing inputs prematurely.
                        with self.transaction() as db:
                            db.execute(
                                "UPDATE jobs SET receipt=?,updated=? WHERE id=? AND attempt=? AND state='running'",
                                (canonical({**previous, "docker_create_resolution": resolution}),
                                 time.time(), row["id"], row["attempt"]),
                            )
                    recovered_create = {"previous_receipt": previous, "resolution": resolution,
                                        "new_execution": False}
                self._remove_container(row["attempt"])
            self._finish(
                row["id"],
                row["attempt"],
                "cancelled" if row["cancel"] else "interrupted",
                {"error": "cancellation retained across worker restart" if row["cancel"]
                    else "worker restarted; not automatically replayed",
                 # Reconciliation changes lifecycle state, not the observed
                 # cause of the unresolved execution. Keep that prior receipt
                 # nested so its old termination error is not a current claim
                 # that cleanup remains unconfirmed after successful recovery.
                 "restart_recovery": {"previous_state": row["state"],
                                      "previous_receipt": previous,
                                      "new_execution": False},
                 **({"docker_create_recovery": recovered_create} if recovered_create else {})},
            )

    def submit(self, request, *, template_override=None, admission_check=None):
        if not isinstance(request, dict) or set(request) - {
            "job_id",
            "template",
            "args",
            "metadata",
        }:
            raise ValueError("allowed job fields: job_id, template, args, metadata")
        job_id = request.get("job_id")
        if not isinstance(job_id, str) or not ID.fullmatch(job_id):
            raise ValueError("job_id must be 4-80 letters, digits, hyphens or underscores")
        args = request.get("args", [])
        if (
            not isinstance(args, list)
            or len(args) > 256
            or any(not isinstance(a, str) or len(a) > 8192 or "\0" in a for a in args)
        ):
            raise ValueError("invalid job arguments")
        if not isinstance(request.get("metadata", {}), dict):
            raise ValueError("metadata must be an object")
        text = canonical(
            {
                "job_id": job_id,
                "template": request.get("template"),
                "args": args,
                "metadata": request.get("metadata", {}),
            }
        )
        if len(text.encode()) > 65536:
            raise ValueError("job request exceeds 64 KiB")
        if admission_check is not None and not callable(admission_check):
            raise ValueError("internal admission check must be callable")
        # Serialize snapshots and capacity admission. Status/polling still proceeds.
        with self.admission:
            if self.stop.is_set():
                raise CapacityError("worker is shutting down")
            with self.db_lock:
                old = self.db.execute(
                    "SELECT request FROM jobs WHERE lower(id)=lower(?)", (job_id,)
                ).fetchone()
            if old:
                if old[0] != text:
                    raise Conflict("job_id already belongs to a different request")
                return self.status(job_id), False
            # Live filesystem accounting can stall on a slow drive. It never
            # authorizes byte reuse and must not own the status/cancellation DB
            # lock. self.admission still serializes new job reservations.
            used = live_tree_bytes(self.root)
            if shutil.disk_usage(self.root).free < self.min_free_mb * (
                1 << 20
            ) or used >= self.max_store_mb * (1 << 20):
                raise CapacityError(
                    "worker storage capacity reached; retain/export or archive old jobs"
                )
            with self.transaction() as db:
                # This is an in-process, metadata-only predicate. It runs in
                # the same transaction as reservation and the later runnable
                # transition; HTTP callers cannot supply code or this keyword.
                if admission_check is not None and admission_check(db) is not True:
                    raise Conflict("workflow admission fence changed before preparation")
                # An in-process workflow coordinator may supply a frozen template.
                # HTTP callers cannot populate this keyword or select host mounts.
                template = template_override or self.templates.get(request.get("template"))
                if template is None:
                    raise ValueError("unknown configured template")
                count = db.execute(
                    "SELECT COUNT(*) FROM jobs WHERE state NOT IN ('succeeded','failed','cancelled','interrupted')"
                ).fetchone()[0]
                if count >= self.max_pending:
                    raise CapacityError("queue is full")
                now = time.time()
                db.execute(
                    "INSERT INTO jobs(id,request,state,created,updated) VALUES (?,?,'preparing',?,?)",
                    (job_id, text, now, now),
                )
            try:
                payload = self._prepare(job_id, template, args, request.get("metadata", {}))
                with self.transaction() as db:
                    fenced = admission_check is not None and admission_check(db) is not True
                    if fenced:
                        db.execute("UPDATE jobs SET cancel=1 WHERE id=?", (job_id,))
                    db.execute(
                        "UPDATE jobs SET payload=?,state='queued',updated=? WHERE id=?",
                        (canonical(payload), time.time(), job_id),
                    )
                    if db.execute("SELECT cancel FROM jobs WHERE id=?", (job_id,)).fetchone()[0]:
                        self._finish(
                            job_id,
                            None,
                            "cancelled",
                            {"error": "workflow admission fence changed during preparation"
                             if fenced else "cancelled during preparation"},
                            db=db,
                        )
            except Exception as exc:
                with self.transaction() as db:
                    cancelled = db.execute("SELECT cancel FROM jobs WHERE id=?", (job_id,)).fetchone()[0]
                    self._finish(
                        job_id, None, "cancelled" if cancelled else "failed",
                        {"error": f"admission failed: {type(exc).__name__}: {exc}"}, db=db,
                    )
            self.wake.set()
            return self.status(job_id), True

    def _prepare(self, job_id, template, args, metadata):
        blobs = [SealedBlob("entrypoint", str(template.entrypoint), "entrypoint.py")]
        if template.code_dir:
            blobs.append(SealedBlob("code", str(template.code_dir), "code", is_dir=True))
        for index, (path, rel) in enumerate(template.data):
            blobs.append(SealedBlob(f"data-{index}", str(path), rel, is_dir=path.is_dir()))
        input_bytes = 0
        for blob in blobs:
            source = Path(blob.local_src)
            input_bytes += (
                sum(p.stat().st_size for p in source.rglob("*") if p.is_file())
                if blob.is_dir
                else source.stat().st_size
            )
        if input_bytes > template.max_input_mb * (1 << 20):
            raise CapacityError("configured inputs exceed template max_input_mb")
        if shutil.disk_usage(self.root).free < 3 * input_bytes + self.min_free_mb * (1 << 20):
            raise CapacityError("insufficient space to snapshot, seal and verify configured inputs")
        manifest = SealedManifest(
            job_id=job_id,
            task_type="http-template",
            metadata=metadata,
            host=HostSpec("local-worker", "/work", platform="linux"),
            blobs=blobs,
            entrypoint_rel="entrypoint.py",
            extra_pythonpath=["blobs/code"] if template.code_dir else [],
            run_args=args,
            env=template.env,
            result=ResultSpec(local_dir="controller-owned", max_size_mb=template.max_output_mb),
        )
        seal = build_seal(manifest, out_dir=self.root / "bundles")
        verify_seal(seal, expected_sha256=manifest.seal_sha256)
        payload = {
            "seal": seal.name,
            "seal_sha256": manifest.seal_sha256,
            "backend": self.backend,
            "template": dataclasses.asdict(template),
            "image_id": self.images.get(template.name),
            "inputs": [
                {"path": b.rel_path, "sha256": b.sha256, "size_bytes": b.size_bytes}
                for b in manifest.blobs
            ],
        }
        # Paths are provenance only; execution never reads the original inputs again.
        return json.loads(json.dumps(payload, default=str))

    def status(self, job_id):
        with self.db_lock:
            row = self.db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        if row is None:
            raise KeyError(job_id)
        payload = json.loads(row["payload"] or "{}")
        return {
            "job_id": row["id"],
            "sequence": row["sequence"],
            "state": row["state"],
            "created_at": row["created"],
            "updated_at": row["updated"],
            "cancel_requested": bool(row["cancel"]),
            "acknowledged_sha256": row["acknowledged"],
            "seal_sha256": payload.get("seal_sha256"),
            "image_id": payload.get("image_id"),
            "inputs": payload.get("inputs", []),
            "receipt": json.loads(row["receipt"]) if row["receipt"] else None,
        }

    def _record_phase(self, job_id, attempt, phase):
        from .observations import transition

        with self.transaction() as db:
            row = db.execute("SELECT attempt,state,receipt FROM jobs WHERE id=?", (job_id,)).fetchone()
            if row is None or row["attempt"] != attempt or row["state"] != "running":
                return  # An old attempt cannot freshen a replacement or terminal job.
            receipt = json.loads(row["receipt"] or "{}")
            previous = receipt.get("worker_phase")
            current = transition(previous, job_id=job_id, attempt=attempt,
                                 worker_instance=self.worker_instance, phase=phase)
            if current == previous:
                return
            receipt["worker_phase"] = current
            db.execute("UPDATE jobs SET receipt=?,updated=? WHERE id=? AND attempt=?",
                       (canonical(receipt), current["updated_at"], job_id, attempt))

    def cancel(self, job_id):
        with self.transaction() as db:
            row = db.execute("SELECT state FROM jobs WHERE id=?", (job_id,)).fetchone()
            if row is None:
                raise KeyError(job_id)
            if row[0] not in TERMINAL:
                db.execute("UPDATE jobs SET cancel=1,updated=? WHERE id=?", (time.time(), job_id))
                if row[0] == "queued":
                    self._finish(
                        job_id, None, "cancelled", {"error": "cancelled before execution"}, db=db
                    )
        self.wake.set()
        return self.status(job_id)

    def result(self, job_id):
        status = self.status(job_id)
        receipt = status.get("receipt") or {}
        if not receipt.get("result_sha256"):
            raise Conflict("no retained result is available")
        path = self.root / "results" / f"{job_id}.tar.gz"
        if not path.is_file() or sha256_of_file(path) != receipt["result_sha256"]:
            raise Conflict("retained result failed integrity verification")
        return path, receipt["result_sha256"]

    def acknowledge(self, job_id, digest):
        _, expected = self.result(job_id)
        if digest != expected:
            raise Conflict("acknowledgement does not match retained result")
        with self.transaction() as db:
            db.execute(
                "UPDATE jobs SET acknowledged=?,updated=? WHERE id=?", (digest, time.time(), job_id)
            )
        # ACK records verified delivery. It never triggers automatic deletion.
        return self.status(job_id)

    @staticmethod
    def _execution_storage_bytes(payload):
        # Keep the existing execution contract: three staging copies of the
        # sealed bundle inputs plus the declared writable work allowance.
        # Read-only workflow mounts are not additional extracted bundle copies.
        inputs = sum(item.get("size_bytes") or 0 for item in payload["inputs"])
        return 3 * inputs + payload["template"]["max_work_mb"] * (1 << 20)

    def _storage_claim_allowed(self, db, payload, free_bytes):
        # Called inside the claim transaction. Conservatively retain each
        # running claim's whole allowance until it finishes. Creating an empty
        # workspace does not allocate its future output allowance; free space
        # reflects bytes written so far, not the remaining declared writes.
        # No filesystem observation occurs while holding the database lock.
        reserved = sum(
            self._execution_storage_bytes(json.loads(row[0]))
            for row in db.execute("SELECT payload FROM jobs WHERE state='running'")
        )
        required = (self.min_free_mb << 20) + reserved + self._execution_storage_bytes(payload)
        return free_bytes >= required

    def _defer_unstarted_for_storage(self, job_id, attempt, free_bytes, required):
        with self.transaction() as db:
            row = db.execute("SELECT attempt,state,cancel FROM jobs WHERE id=?", (job_id,)).fetchone()
            if row is None or row[0] != attempt or row[1] != "running":
                return  # A stale observer cannot requeue a replacement attempt.
            work = self.root / "work" / attempt
            if work.exists() or work.is_symlink():
                raise RuntimeError("cannot defer an attempt with an existing workspace")
            receipt = {
                "execution_started": False,
                "unstarted_attempt": attempt,
                "storage_wait": {"free_bytes": free_bytes, "required_free_bytes": required},
            }
            if row[2] or self.stop.is_set():
                self._finish(job_id, attempt, "cancelled" if row[2] else "interrupted",
                             {**receipt, "error": "cancellation requested" if row[2] else "worker stopping"},
                             db=db)
                return
            receipt.update(job_id=job_id, state="queued", deferred_at=time.time())
            retained = self.root / "storage_waits"
            retained.mkdir(exist_ok=True)
            atomic_json(retained / (attempt + ".json"), receipt)
            db.execute(
                "UPDATE jobs SET state='queued',attempt=NULL,receipt=?,updated=? "
                "WHERE id=? AND attempt=? AND state='running'",
                (canonical(receipt), time.time(), job_id, attempt),
            )

    def _claim(self):
        if self.stop.is_set():
            return None
        free_bytes = shutil.disk_usage(self.root).free
        with self.transaction() as db:
            if self.stop.is_set():
                return None
            row = db.execute(
                "SELECT * FROM jobs WHERE state='queued' ORDER BY sequence LIMIT 1"
            ).fetchone()
            if row is None:
                return None
            payload = json.loads(row["payload"])
            if not self._storage_claim_allowed(db, payload, free_bytes):
                return None
            attempt = "offload-" + uuid.uuid4().hex
            db.execute(
                "UPDATE jobs SET state='running',attempt=?,updated=? WHERE id=? AND state='queued'",
                (attempt, time.time(), row["id"]),
            )
            return row["id"], attempt, payload

    def _finish(self, job_id, attempt, state, receipt, *, db=None):
        receipt = {
            **receipt,
            "job_id": job_id,
            "attempt": attempt,
            "state": state,
            "finished_at": time.time(),
        }

        def write(connection):
            # Fence stale attempts; no earlier runner can finish a replacement.
            row = connection.execute(
                "SELECT attempt,state,receipt FROM jobs WHERE id=?", (job_id,)
            ).fetchone()
            if row is None or row[0] != attempt or row[1] in TERMINAL:
                return
            retained = dict(receipt)
            previous = json.loads(row[2] or "{}").get("worker_phase")
            if previous:
                from .observations import transition

                retained["worker_phase"] = transition(previous, job_id=job_id, attempt=attempt,
                    worker_instance=self.worker_instance, phase="TERMINAL")
                retained["worker_phase"]["terminal_state"] = state
            atomic_json(self.root / "receipts" / f"{job_id}.json", retained)
            connection.execute(
                "UPDATE jobs SET state=?,receipt=?,updated=? WHERE id=? AND attempt IS ?",
                (state, canonical(retained), time.time(), job_id, attempt),
            )

        if db is not None:
            write(db)
        else:
            with self.transaction() as connection:
                write(connection)

    def docker_command(self, work, attempt, payload):
        t = payload["template"]
        uid = str(os.getuid()) + ":" + str(os.getgid()) if os.name != "nt" else "1000:1000"
        # The store, socket, home and credentials are never mounted. Input bytes
        # are read-only; only this attempt's private working directory is writable.
        return [
            "docker",
            "container",
            "create",
            "--name",
            attempt,
            "--pull=never",
            "--network=none",
            "--read-only",
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges",
            "--user",
            uid,
            "--init",
            "--memory",
            f"{int(t['memory_mb'])}m",
            "--memory-swap",
            f"{int(t['memory_mb'])}m",
            "--cpus",
            str(t["cpus"]),
            "--pids-limit",
            str(int(t["pids"])),
            "--ulimit",
            f"fsize={int(t['max_work_mb']) * (1 << 20)}",
            "--log-driver=none",
            "--tmpfs",
            "/tmp:rw,nosuid,nodev,size=64m,mode=1777",
            "--mount",
            f"type=bind,source={work},target=/work",
            "--mount",
            f"type=bind,source={work / 'blobs'},target=/work/blobs,readonly",
            "--workdir",
            "/work",
            "--env",
            "PYTHONDONTWRITEBYTECODE=1",
            "--env",
            "PYTHONNOUSERSITE=1",
            "--env",
            "PYTHONUNBUFFERED=1",
            "--entrypoint",
            "python",
            payload["image_id"],
            "-I",
            "/work/runner.py",
            "/work/manifest.json",
        ]

    def _execute(self, job_id, attempt, payload):
        work = self.root / "work" / attempt
        state, receipt, proc = "failed", {}, None
        t = payload["template"]

        # Free space can fall after the durable claim. This branch precedes
        # workspace creation and all process/container work. Keep the same
        # admitted request queued, with a fenced receipt for the unused claim,
        # instead of publishing a failed model result. Cancellation still wins.
        required = (self.min_free_mb << 20) + self._execution_storage_bytes(payload)
        free_bytes = shutil.disk_usage(self.root).free
        if free_bytes < required:
            self._defer_unstarted_for_storage(job_id, attempt, free_bytes, required)
            return

        def check_cancellation():
            nonlocal state
            cancelled = self.status(job_id)["cancel_requested"]
            if self.stop.is_set() or cancelled:
                # A durable cancellation must not become an interrupted,
                # automatically retryable attempt when shutdown happens too.
                state = "cancelled" if cancelled else "interrupted"
                raise RuntimeError("cancellation requested" if cancelled else "worker stopping")

        try:
            check_cancellation()
            self._record_phase(job_id, attempt, "PREPARING_INPUTS")
            seal = self.root / "bundles" / payload["seal"]
            verify_seal(seal, expected_sha256=payload["seal_sha256"])
            work.mkdir(mode=0o700)
            extract_seal(seal, work)
            self.prepare_extra_inputs(work, payload)
            check_cancellation()
            if payload["backend"] == "docker":
                self._record_phase(job_id, attempt, "VERIFYING_INPUTS_BEFORE_EXECUTION")
                cmd = self.docker_command(work, attempt, payload)
                check_cancellation()  # mount verification may have been slow
                self._record_phase(job_id, attempt, "CREATING_CONTAINER")
                try:
                    self._docker(*cmd[1:])
                except subprocess.TimeoutExpired:
                    receipt["docker_create_uncertain"] = True
                    raise
                cmd = ["docker", "container", "start", "--attach", attempt]
            else:
                cmd = [sys.executable, "-I", str(work / "runner.py"), str(work / "manifest.json")]
            flags = (
                {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
                if os.name == "nt"
                else {"start_new_session": True}
            )
            with (work / "supervisor.log").open("wb") as log:
                process_env = (
                    os.environ.copy() if payload["backend"] == "docker" else clean_environment()
                )
                check_cancellation()
                proc = subprocess.Popen(
                    cmd,
                    cwd=work,
                    env=process_env,
                    stdin=subprocess.DEVNULL,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    **flags,
                )
                started = time.monotonic()
                self._record_phase(job_id, attempt, "SUPERVISING_EXECUTION")
                while proc.poll() is None:
                    check_cancellation()
                    if time.monotonic() - started > t["timeout_s"]:
                        raise TimeoutError(f"job exceeded {t['timeout_s']} seconds")
                    size = live_tree_bytes(work, exclude_root_dirs={"blobs"})
                    if size > t["max_work_mb"] * (1 << 20):
                        raise RuntimeError("job exceeded working-output limit")
                    self.stop.wait(0.1)
            exit_code = proc.returncode
            self._record_phase(job_id, attempt, "STOPPING_EXECUTION")
            if payload["backend"] == "docker":
                self._remove_container(attempt)
            else:
                stop_tree(proc)
            proc = None
            state, receipt = self._collect_completed_result(job_id, payload, work, exit_code)
        except Exception as exc:
            receipt["error"] = f"{type(exc).__name__}: {exc}"
        finally:
            # Stop the boundary BEFORE releasing a slot or publishing completion.
            stopped = True
            try:
                if payload["backend"] == "docker":
                    if receipt.get("docker_create_uncertain"):
                        receipt["docker_create_resolution"] = self._resolve_timed_out_create(attempt, payload)
                    self._remove_container(attempt)
                    if proc is not None:
                        # The workload's entire namespace is gone. Reap the
                        # attached CLI, which is not the workload process tree.
                        try:
                            proc.wait(timeout=15)
                        except subprocess.TimeoutExpired:
                            proc.kill()
                            proc.wait(timeout=5)
                elif proc is not None:
                    stop_tree(proc)
            except Exception as exc:
                self.stop.set()  # fail closed if termination cannot be confirmed
                receipt["termination_error"] = str(exc)
                stopped = False  # leave running for startup reconciliation
            receipt.update(
                seal_sha256=payload["seal_sha256"],
                image_id=payload.get("image_id"),
                backend=payload["backend"],
                inputs=payload["inputs"],
            )
            if stopped:
                self._finish(job_id, attempt, state, receipt)
            else:
                self._record_phase(job_id, attempt, "TERMINATION_UNCONFIRMED")
                with self.transaction() as db:
                    previous = db.execute("SELECT receipt FROM jobs WHERE id=? AND attempt=?",
                                          (job_id, attempt)).fetchone()
                    observation = json.loads(previous[0] or "{}").get("worker_phase") if previous else None
                    if observation:
                        receipt["worker_phase"] = observation
                    db.execute(
                        "UPDATE jobs SET receipt=?,updated=? WHERE id=? AND attempt=?",
                        (canonical(receipt), time.time(), job_id, attempt),
                    )

    def _collect_completed_result(self, job_id, payload, work, exit_code, *, recovery=False):
        """Common byte/identity verification after confirmed workload exit.

        Recovery uses a fresh bounded extraction directory and never replaces a
        conflicting retained result. It does not itself authorize a job finish.
        """
        self._record_phase(job_id, work.name, "VERIFYING_INPUTS_AFTER_EXECUTION")
        self.verify_extra_inputs(payload)
        self._record_phase(job_id, work.name, "VERIFYING_RESULT")
        if any(p.is_symlink() for p in work.rglob("*")):
            raise RuntimeError("job workspace contains a symlink; refusing host-side result access")
        remote = json.loads((work / "status.json").read_text())
        if remote.get("job_id") != job_id or remote.get("phase") != "exited":
            raise RuntimeError("runner did not return a completed result")
        archive = work / f"{job_id}.result.tar.gz"
        digest = sha256_of_file(archive)
        if digest != remote.get("result_sha256"):
            raise RuntimeError("runner result SHA-256 mismatch")
        limit = payload["template"]["max_output_mb"] * (1 << 20)
        with contextlib.ExitStack() as stack:
            verified = work / "verified-result"
            if recovery:
                from v2.safe_archive import expansion_budget

                expanded, _ = expansion_budget(archive, max_bytes=limit)
                additional = expanded + archive.stat().st_size
                if (live_tree_bytes(self.root) + additional > self.max_store_mb * (1 << 20)
                        or shutil.disk_usage(self.root).free < (self.min_free_mb << 20) + additional):
                    raise CapacityError("completed-result recovery storage budget exhausted")
                directory = Path(stack.enter_context(tempfile.TemporaryDirectory(
                    prefix=".completed-recovery-", dir=self.root / "results")))
                verified = directory / "verified"
            _safe_extract(archive, verified, max_bytes=limit)
            execution = json.loads((verified / "status.json").read_text())
            if (execution.get("job_id") != job_id or execution.get("phase") != "exited"
                    or execution.get("exit_code") != exit_code):
                raise RuntimeError("result execution identity mismatch")
            target = self.root / "results" / f"{job_id}.tar.gz"
            if recovery and target.exists() and sha256_of_file(target) != digest:
                raise Conflict("retained result conflicts with completed recovery")
            temporary = directory / "result.tar.gz" if recovery else target.with_suffix(".partial")
            with archive.open("rb") as source, temporary.open("xb") as output:
                shutil.copyfileobj(source, output)
                output.flush()
                os.fsync(output.fileno())
            if sha256_of_file(temporary) != digest or sha256_of_file(archive) != digest:
                raise RuntimeError("retained result copy failed verification")
            os.replace(temporary, target)
        return ("succeeded" if exit_code == 0 else "failed"), {
            "exit_code": exit_code, "execution": execution,
            "result_sha256": digest, "result_bytes": target.stat().st_size,
        }

    def process_next(self):
        claim = self._claim()
        if claim:
            self._execute(*claim)
            return self.status(claim[0])
        return None

    def prepare_extra_inputs(self, work, payload):
        """Extension hook; base template jobs have no extra mounts."""

    def verify_extra_inputs(self, payload):
        """Extension hook called after the entire workload boundary stops."""

    def start(self):
        if self.threads:
            return

        def loop():
            try:
                while not self.stop.is_set():
                    if self.process_next() is None:
                        self.wake.wait(0.2)
                        self.wake.clear()
            except Exception:
                self.stop.set()  # database/I/O failures must not silently lose a worker thread
                self.wake.set()

        for index in range(self.concurrency):
            thread = threading.Thread(target=loop, name=f"offload-{index}", daemon=True)
            thread.start()
            self.threads.append(thread)

    def close(self):
        if self.closed:
            return
        self.stop.set()
        self.wake.set()
        for thread in self.threads:
            thread.join(timeout=75)
            if thread.is_alive():
                raise RuntimeError("worker has not stopped; store lock retained")
        with self.admission, self.db_lock:
            self.db.close()
            self.lock.__exit__(None, None, None)
            self.closed = True

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
