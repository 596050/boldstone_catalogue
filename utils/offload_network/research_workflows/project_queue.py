"""Durable source outbox, reconnect/reconciliation and origin-aware result return.

The source owns research identities and destinations. A worker owns its execution
queue. A network timeout never transfers execution ownership to another worker.
"""

import errno
import http.client
import json
import os
import random
import shutil
import sqlite3
import time
import urllib.error
import uuid
from contextlib import ExitStack, contextmanager
from pathlib import Path
from datetime import datetime, timezone

from lib.file_lock import file_lock

from .client import Client, verify_collection
from .common import atomic, canonical, digest, hash_id, load, no_links, sha, sync_directory
from .project_storage import Project, StorageUnavailable
from .publication import publish
from .spec import TERMINAL, identity, output_plan, selected_ports, validate


class ProjectQueue:
    def __init__(self, config):
        self.project = Project(config)
        self.root = self.project.state
        self.root.mkdir(parents=True, exist_ok=True)
        no_links(self.root / "queue.sqlite3", self.root)
        self.db = sqlite3.connect(self.root / "queue.sqlite3", timeout=30, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        # The small database lives on the source disk, never on exFAT/network storage.
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.execute("""CREATE TABLE IF NOT EXISTS requests (
            id TEXT PRIMARY KEY, binding TEXT NOT NULL, spec TEXT NOT NULL,
            worker TEXT NOT NULL, objects TEXT NOT NULL, created REAL NOT NULL,
            phase TEXT NOT NULL DEFAULT 'queued', next_at REAL NOT NULL DEFAULT 0,
            failures INTEGER NOT NULL DEFAULT 0, attention INTEGER NOT NULL DEFAULT 0,
            error TEXT, delivery TEXT, last_status TEXT, publications TEXT)
        """)
        self.db.execute("""CREATE TABLE IF NOT EXISTS partial_deliveries (
            workflow TEXT NOT NULL, digest TEXT NOT NULL, delivery TEXT NOT NULL,
            state TEXT NOT NULL DEFAULT 'collecting', created REAL NOT NULL,
            PRIMARY KEY(workflow,digest))
        """)
        sync_directory(self.root)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.db.close()

    def _row(self, workflow):
        row = self.db.execute("SELECT * FROM requests WHERE id=?", (workflow,)).fetchone()
        if row is None:
            raise KeyError(workflow)
        return dict(row)

    def _update(self, workflow, **values):
        allowed = {
            "phase",
            "next_at",
            "failures",
            "attention",
            "error",
            "delivery",
            "last_status",
            "publications",
        }
        if not set(values) <= allowed:
            raise ValueError("invalid source queue update")
        self.db.execute(
            "UPDATE requests SET " + ",".join(key + "=?" for key in values) + " WHERE id=?",
            [*values.values(), workflow],
        )

    def status(self):
        return [
            {
                "workflow_id": row["id"],
                "phase": row["phase"],
                "state": "needs_attention" if row["attention"] else row["phase"],
                "worker": json.loads(row["worker"])["id"],
                "error": row["error"],
                "transport_failures": row["failures"],
                "next_attempt_at": row["next_at"],
                "delivery_sha256": row["delivery"],
                "publications": json.loads(row["publications"] or "[]"),
            }
            for row in self.db.execute("SELECT * FROM requests ORDER BY created,id")
        ]

    def enqueue(self, plan, worker, origins):
        self.project.require_active_worker(worker)
        plan = Path(plan)
        spec = validate(load(plan / "WORKFLOW.json"))
        if (
            load(plan / "PLAN_RECEIPT.json")["workflow_sha256"] != identity(spec)
            or load(plan / "OUTPUT_PLAN.json") != output_plan(spec)
            or ("batch" in spec and load(plan / "BATCH_PLAN.json") != spec["batch"])
        ):
            raise ValueError("compiled plan identity changed")
        policy = spec["return_policy"]
        required_returns = {
            j["id"] + ".research_evidence"
            for j in spec["jobs"]
            if j["kind"] in {"testing", "testing_stage"}
        }
        if policy["profile"] != "full_results" or required_returns - set(selected_ports(spec)):
            raise ValueError(
                "project records require full_results with every native research_evidence port"
            )
        binding = self.project.binding(spec, origins)
        worker = self.project.worker(worker)
        required = {job["capsule"] for job in spec["jobs"]}
        required.update(
            ref["object_sha256"]
            for job in spec["jobs"]
            for ref in job["inputs"].values()
            if ref["mode"] == "bundle"
        )
        with self._retain_outbox_during_enqueue(required):
            return self._enqueue_retained(plan, spec, worker, binding, required)

    def _enqueue_retained(self, plan, spec, worker, binding, required):
        key = spec["submission_id"]
        # Toshiba verify/copy/fsync/sha of shared outbox archives must not hold
        # queue.lock. Concurrent researchers enqueue while a slow bulk object
        # is staged or re-hashed; the lock covers only identity, pending-limit,
        # a cheap stat fingerprint, and the SQLite insert.
        cache = self._stage_source_outbox(plan, required)
        bulk = self.project.bulk()
        fingerprints = {}
        for ident in sorted(required):
            target = no_links(cache / (ident + ".tar.gz"), bulk)
            if not target.is_file() or target.is_symlink() or sha(target) != ident:
                raise ValueError(
                    "compiled plan lacks the exact bundled capsule/input: " + ident
                )
            stat = target.stat()
            fingerprints[ident] = (stat.st_ino, stat.st_size, stat.st_mtime_ns)
        with file_lock(self.root / "queue.lock", timeout=0):
            old = self.db.execute("SELECT * FROM requests WHERE id=?", (key,)).fetchone()
            if old:
                if (
                    json.loads(old["binding"]) != binding
                    or json.loads(old["spec"]) != spec
                    or json.loads(old["worker"]) != worker
                ):
                    raise ValueError("submission already has another origin, worker or workflow")
                return self._row(key)
            pending = self.db.execute(
                "SELECT COUNT(*) FROM requests WHERE phase!='completed'"
            ).fetchone()[0]
            if pending >= self.project.recovery["max_pending"]:
                raise StorageUnavailable("source queue pending-workflow limit exhausted")
            for ident in sorted(required):
                target = no_links(cache / (ident + ".tar.gz"), bulk)
                if not target.is_file() or target.is_symlink():
                    raise ValueError(
                        "compiled plan lacks the exact bundled capsule/input: " + ident
                    )
                stat = target.stat()
                if (stat.st_ino, stat.st_size, stat.st_mtime_ns) != fingerprints[ident]:
                    raise ValueError("outbox object changed after identity check: " + ident)
            receipt = {
                "binding": binding,
                "worker": worker,
                "workflow": spec,
                "objects": sorted(required),
                "plan_receipt": load(plan / "PLAN_RECEIPT.json"),
            }
            # All source paths/code may disappear after this local commit succeeds.
            metadata = self.root / "submissions" / key / "ENQUEUED.json"
            if metadata.exists() and load(metadata) != receipt:
                raise ValueError("incomplete enqueue belongs to different work")
            atomic(metadata, receipt)
            self.db.execute(
                "INSERT INTO requests(id,binding,spec,worker,objects,created) VALUES (?,?,?,?,?,?)",
                (
                    key,
                    canonical(binding),
                    canonical(spec),
                    canonical(worker),
                    canonical(sorted(required)),
                    time.time(),
                ),
            )
            return self._row(key)

    @contextmanager
    def _retain_outbox_during_enqueue(self, required):
        """Pin inputs before staging, until source commit or abandoned enqueue.

        Registration and cleanup share queue.lock. The unique ownership lock
        spans bulk I/O, but cleanup only probes it without waiting. OS release
        makes a dead source reclaimable without guessing from a PID or clock.
        """
        token = uuid.uuid4().hex
        record = no_links(self.root / "outbox-enqueues" / (token + ".json"), self.root)
        lock = no_links(self.root / "outbox-enqueue-locks" / (token + ".lock"), self.root)
        objects = sorted(hash_id(ident) for ident in required)
        with file_lock(lock, timeout=0):
            try:
                with file_lock(self.root / "queue.lock", timeout=0):
                    atomic(record, {"schema": "marketmaker.outbox_enqueue.v1", "objects": objects})
                yield
            finally:
                # Missing after interrupted registration is harmless. A stale
                # record after a crash is reclaimable once this lock releases.
                no_links(record, self.root).unlink(missing_ok=True)

    def _active_outbox_references(self):
        """Read/reclaim enqueue references while the caller owns queue.lock."""
        directory = no_links(self.root / "outbox-enqueues", self.root)
        active = set()
        for record in sorted(directory.glob("*.json")):
            no_links(record, self.root)
            token = record.stem
            if len(token) != 32 or any(c not in "0123456789abcdef" for c in token):
                raise ValueError("invalid outbox enqueue reference name")
            try:
                value = load(record)
            except FileNotFoundError:
                continue  # Its owner finished after the directory enumeration.
            if (not isinstance(value, dict) or set(value) != {"schema", "objects"}
                    or value["schema"] != "marketmaker.outbox_enqueue.v1"
                    or not isinstance(value["objects"], list)):
                raise ValueError("invalid outbox enqueue reference")
            objects = [hash_id(ident) for ident in value["objects"]]
            if objects != sorted(set(objects)):
                raise ValueError("outbox enqueue references must be sorted and unique")
            lock = no_links(self.root / "outbox-enqueue-locks" / (token + ".lock"), self.root)
            with ExitStack() as owner:
                try:
                    owner.enter_context(file_lock(lock, timeout=0))
                except TimeoutError:
                    active.update(objects)
                    continue
                # No live owner. Do not resume its enqueue or discard archives
                # here; normal cleanup still needs verified retained objects.
                record.unlink(missing_ok=True)
        return active

    def _stage_source_outbox(self, plan, required):
        """Copy required archives into the shared outbox without queue.lock."""
        plan = Path(plan)
        bulk = self.project.capacity()
        cache = no_links(bulk / "outbox", bulk)
        cache.mkdir(exist_ok=True)
        for ident in sorted(required):
            hash_id(ident)
            source, target = plan / "objects" / (ident + ".tar.gz"), cache / (ident + ".tar.gz")
            no_links(target, bulk)
            if target.exists():
                if sha(target) != ident:
                    raise ValueError("retained outbox object changed")
                continue
            if not source.exists() and (bulk / "objects" / ident).is_dir():
                from .client import verify_object

                verify_object(
                    bulk / "objects" / ident,
                    ident,
                    max_bytes=self.project.storage["max_collection_mb"] << 20,
                )
                source = bulk / "objects" / ident / "archive.tar.gz"
            if source.is_symlink() or not source.is_file() or sha(source) != ident:
                raise ValueError(
                    "compiled plan lacks the exact bundled capsule/input: " + ident
                )
            self.project.capacity(source.stat().st_size + (1 << 20))
            # Concurrent enqueues may stage the same immutable object. Each
            # owns its partial file; failed/interrupted copies remain inspectable.
            part = no_links(cache / (ident + "." + uuid.uuid4().hex + ".copying"), bulk)
            with source.open("rb") as incoming, part.open("xb") as output:
                shutil.copyfileobj(incoming, output, 1 << 20)
                output.flush()
                os.fsync(output.fileno())
            if sha(part) != ident:
                raise ValueError("outbox copy changed during staging")
            lock = no_links(self.root / "outbox-locks" / (ident + ".lock"), self.root)
            published = False
            # Only first publication changes the target inode. Bulk copy, hash
            # and fsync stay outside both this object lock and queue.lock.
            with file_lock(lock):
                no_links(target, bulk)
                if not target.exists():
                    os.replace(part, target)
                    published = True
            if target.is_symlink() or not target.is_file() or sha(target) != ident:
                raise ValueError("retained outbox object changed")
            sync_directory(cache)
            if not published:
                # Another copier won publication. Remove only our verified
                # duplicate, never its target or another attempt's partial.
                part.unlink()
        return cache

    def retry(self, workflow):
        """Clear a repaired transport/storage problem; never change execution identity."""
        with self._sync_lock(workflow):
            with file_lock(self.root / "queue.lock", timeout=0):
                self._row(workflow)
                self._update(workflow, attention=0, failures=0, error=None, next_at=0)

    def enqueue_receipt(self, plan, worker, origins, *, output=None, lock_timeout=0):
        """Normal enqueue plus a portable receipt, with bounded ownership-lock retry.

        No queue row surgery, new worker, alternate admission path or automatic
        retry of integrity/storage errors. Re-export does not rewrite old evidence.
        """
        from .common import positive

        if lock_timeout != 0:
            positive(lock_timeout, 3600, integer=False)
        elif type(lock_timeout) not in (int, float):
            raise ValueError("invalid enqueue lock timeout")
        with ExitStack() as stack:
            if output is not None:
                output = Path(output).absolute()
                no_links(output, output.parent)
                lock = no_links(output.with_name(output.name + ".lock"), output.parent)
                stack.enter_context(file_lock(lock, timeout=0))
                if output.exists():
                    # Conflicting exports must fail before enqueuing anything.
                    spec = validate(load(Path(plan) / "WORKFLOW.json"))
                    try:
                        existing = self._enqueue_receipt(self._row(spec["submission_id"]))
                    except KeyError as error:
                        raise ValueError("enqueue receipt exists without a matching queue acknowledgement") from error
                    if load(output) != existing:
                        raise ValueError("enqueue receipt destination belongs to different work")
            expected_lock = "lock held: " + str(self.root / "queue.lock")
            started = time.monotonic()
            while True:
                try:
                    row = self.enqueue(plan, worker, origins)
                    break
                except TimeoutError as error:
                    if str(error) != expected_lock or time.monotonic() - started >= lock_timeout:
                        raise
                    time.sleep(min(.25, max(0, lock_timeout - (time.monotonic() - started))))
            receipt = self._enqueue_receipt(row)
            if output is not None:
                if output.exists():
                    if load(output) != receipt:
                        raise ValueError("enqueue receipt destination belongs to different work")
                else:
                    atomic(output, receipt)
            return receipt

    def _enqueue_receipt(self, row):
        spec, binding = json.loads(row["spec"]), json.loads(row["binding"])
        return {"schema": "marketmaker.project_enqueue_receipt.v1", "project_id": self.project.id,
                   "workflow_id": row["id"], "workflow_sha256": identity(spec),
                   "worker": json.loads(row["worker"])["id"], "origins": binding["origins"],
                   "created_at_utc": datetime.fromtimestamp(row["created"], timezone.utc).isoformat(),
                   "queue_acknowledged": True, "objects": json.loads(row["objects"]),
                   "execution_claim": "Source queue acknowledgement only; consult current status for admission and execution.",
                   "performance_qualification": "NOT_ESTABLISHED"}

    def _sync_lock(self, workflow):
        # One source synchronizer owns each workflow across network waits. Other
        # workflows and readers need not wait for that remote machine. Hash the
        # key rather than allowing database text to choose a filesystem path.
        path = no_links(self.root / "sync-locks" / (digest(workflow) + ".lock"), self.root)
        return file_lock(path, timeout=0)

    def _check_status(self, row, status):
        if status["workflow_id"] != row["id"] or status["workflow_sha256"] != digest(
            json.loads(row["spec"])
        ):
            raise ValueError("remote queue identity differs from the frozen source request")

    def _context(self, row, *, read_only=False):
        """Validate immutable enqueue state and the relevant storage capacity.

        The per-workflow lock protects the row. Status polling writes only local
        metadata; it must not scan or require the bulk evidence disk. A new
        admission or interrupted retry still checks full capacity, and collection/
        publication callers own the shared storage lock and check full capacity
        at their actual write boundaries. No observation is a byte reservation.
        """
        project = self.project
        if read_only:
            project.local_capacity()
            bulk = None
        else:
            bulk = project.capacity()
        frozen = load(self.root / "submissions" / row["id"] / "ENQUEUED.json")
        for key, field in (
            ("binding", "binding"),
            ("worker", "worker"),
            ("workflow", "spec"),
            ("objects", "objects"),
        ):
            if frozen[key] != json.loads(row[field]):
                raise ValueError("source queue differs from its enqueue receipt")
        profile = json.loads(row["worker"])
        client = Client(
            profile["url"],
            Path(profile["token_file"]).read_text().strip(),
            timeout=project.recovery["request_timeout_seconds"],
        )
        spec, binding = json.loads(row["spec"]), json.loads(row["binding"])
        if binding != project.binding(spec, binding["origins"]):
            raise ValueError("source project/origin configuration changed since enqueue")
        return bulk, client, spec, binding

    def _poll_remote(self, row, bulk, client, spec):
        """Network-only reconciliation, protected by the workflow ownership lock.

        Outbox objects are immutable and retained while any request is pending.
        No collection, shared-object mutation or outbox deletion happens here.
        SQLite commits the known-admission fence before any subsequent network
        request, including one whose response could be lost.
        """
        project = self.project
        key, phase = row["id"], row["phase"]
        if self._partial_pending(key):
            return  # Finish the exact retained snapshot before observing a newer one.
        if phase in {"queued", "remote"}:
            try:
                status = client.workflow_status(key)
            except urllib.error.HTTPError as exc:
                if exc.code != 404:
                    raise
                if phase == "remote":
                    raise ValueError(
                        "admitted workflow disappeared; restore worker state, do not silently rerun"
                    ) from exc
                # A genuinely new remote admission needs bulk storage.
                # Keep the original live quota, mount and reserve checks before
                # any upload/POST; an already admitted workflow only needs GET.
                bulk = project.capacity()
                for ident in json.loads(row["objects"]):
                    client.upload(bulk / "outbox" / (ident + ".tar.gz"), identity=ident)
                status = client.request("/v2/workflows", spec)
            self._check_status(row, status)
            self._update(key, phase="remote", last_status=canonical(status))
            limits = {j["id"]: j["max_attempts"] for j in spec["jobs"]}
            if project.recovery["resume_interrupted"] and any(
                n["state"] == "interrupted" and n["attempt"] < limits[n["id"]]
                for n in status["nodes"]
            ):
                # A retry starts new execution, not read-only reconciliation.
                # Preserve the same quota/mount/reserve fence as new admission.
                project.capacity()
                # Worker fences and confirms the old process/container is stopped.
                status = client.request("/v2/workflows/" + key + "/resume", {})
                self._check_status(row, status)
                self._update(key, last_status=canonical(status))
            if not status["terminal"]:
                if project.recovery.get("collect_completed_nodes", False):
                    self._pin_partial(row, client, status)
                return
            delivery = client.request("/v2/workflows/" + key + "/delivery")
            self._check_status(row, delivery["manifest"]["status"])
            if (
                digest(delivery["manifest"]) != delivery["delivery_sha256"]
                or not delivery["manifest"]["final"]
            ):
                raise ValueError("invalid final delivery identity")
            self._update(key, phase="collecting", delivery=delivery["delivery_sha256"])

    @staticmethod
    def _frontier(status):
        return sorted((n for n in status["nodes"] if n["state"] in TERMINAL), key=lambda n: n["id"])

    def _partial_pending(self, key):
        value = self.db.execute("SELECT * FROM partial_deliveries WHERE workflow=? AND state!='published' ORDER BY created,digest LIMIT 1", (key,)).fetchone()
        return dict(value) if value else None

    def _pin_partial(self, row, client, status):
        frontier = self._frontier(status)
        if not frontier:
            return
        previous = self.db.execute("SELECT delivery FROM partial_deliveries WHERE workflow=? ORDER BY created DESC,digest DESC LIMIT 1", (row["id"],)).fetchone()
        if previous and self._frontier(json.loads(previous[0])["manifest"]["status"]) == frontier:
            return  # Changes to a running sibling do not duplicate finished evidence.
        delivery = client.request("/v2/workflows/" + row["id"] + "/snapshot")
        self._check_status(row, delivery["manifest"]["status"])
        if (digest(delivery["manifest"]) != delivery["delivery_sha256"]
                or delivery["manifest"]["workflow"] != json.loads(row["spec"])):
            raise ValueError("invalid partial delivery identity")
        # The workflow can finish between status and snapshot. Retain that exact
        # immutable snapshot too; final publication/ACK still uses the normal path.
        self.db.execute("INSERT OR IGNORE INTO partial_deliveries(workflow,digest,delivery,created) VALUES (?,?,?,?)",
            (row["id"], delivery["delivery_sha256"], canonical(delivery), time.time()))

    def _process_partial(self, row):
        pending = self._partial_pending(row["id"])
        if not pending:
            return
        bulk, client, spec, binding = self._context(row)
        delivery = json.loads(pending["delivery"])
        self._check_status(row, delivery["manifest"]["status"])
        if digest(delivery["manifest"]) != pending["digest"] or delivery["manifest"]["workflow"] != spec:
            raise ValueError("retained partial delivery changed")
        destination = no_links(bulk/"collections"/row["id"]/hash_id(pending["digest"]), bulk)
        client.collect(row["id"], destination, partial=True, expected_delivery=delivery,
            max_bytes=self.project.storage["max_collection_mb"] << 20, shared_objects=True,
            acknowledge=False, capacity_guard=self.project.capacity)
        paths = publish(self.project, destination, binding, completed_only=True)
        previous = json.loads(self._row(row["id"])["publications"] or "[]")
        self._update(row["id"], publications=canonical(sorted(set(previous+paths))))
        self.db.execute("UPDATE partial_deliveries SET state='published' WHERE workflow=? AND digest=?",
            (row["id"], pending["digest"]))
        # No partial ACK, outbox release or completion. Remote artifacts may still
        # be required by dependent jobs, and their origin records remain immutable.

    def _process(self, row):
        """Shared storage, publication and ACK remain globally serialized."""
        bulk, client, spec, binding = self._context(row)
        project = self.project
        key, phase = row["id"], row["phase"]
        if phase not in {"collecting", "publishing", "awaiting_ack"}:
            raise ValueError("collection requires reconciled remote completion")
        destination = no_links(bulk / "collections" / key / hash_id(row["delivery"]), bulk)
        if phase == "collecting":
            client.collect(
                key,
                destination,
                max_bytes=project.storage["max_collection_mb"] << 20,
                shared_objects=True,
                acknowledge=False,
                capacity_guard=project.capacity,
            )
            phase = "publishing"
            self._update(key, phase=phase)
        receipt = verify_collection(
            destination, max_bytes=project.storage["max_collection_mb"] << 20
        )
        if (
            receipt["delivery_sha256"] != row["delivery"]
            or load(destination / "DELIVERY.json")["manifest"]["workflow"] != spec
        ):
            raise ValueError("returned delivery differs from the frozen source identity")
        if phase in {"publishing", "awaiting_ack"}:
            paths = publish(project, destination, binding)
            previous = json.loads(self._row(key)["publications"] or "[]")
            self._update(key, phase="awaiting_ack", publications=canonical(sorted(set(previous+paths))))
            # Both central evidence AND every origin record exist before the ACK.
            client.request("/v2/workflows/" + key + "/ack", {"delivery_sha256": row["delivery"]})
        return bulk

    def _collection_lock(self):
        # Existing deployments retain their original lock until all source
        # processes have been upgraded and an idle configuration transition
        # explicitly enables the separate shared-storage lock. Per-workflow
        # ownership still spans the entire return and acknowledgement.
        separate = self.project.recovery.get('collection_lock_scope', 'queue') == 'separate'
        return file_lock(self.root / ('collection.lock' if separate else 'queue.lock'), timeout=0)

    def _releasable_outbox(self, completing):
        """Snapshot eligible identities while the caller owns queue.lock."""
        active_enqueues = self._active_outbox_references()
        rows = self.db.execute("SELECT id,objects,phase FROM requests").fetchall()
        live = {
            obj
            for row in rows
            if row["phase"] != "completed" and row["id"] != completing
            for obj in json.loads(row["objects"])
        }
        done = {
            obj
            for row in rows
            if row["phase"] == "completed" or row["id"] == completing
            for obj in json.loads(row["objects"])
        }
        return done - live - active_enqueues

    @staticmethod
    def _outbox_fingerprint(path, bulk):
        stat = no_links(path, bulk).stat()
        return (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns,
                stat.st_ctime_ns, stat.st_mode)

    def _release_outbox(self, bulk, *, completing):
        """Verify redundant archives without blocking unrelated source work.

        The workflow ownership lock still spans publication, ACK and cleanup.
        An object lock fences concurrent cleanup/staging. Registration and the
        final reference/fingerprint check share queue.lock, so an enqueue that
        arrives during verification retains its archive. Canonical objects are
        immutable; check their archive and manifest again before removing only
        the redundant outbox copy. No completion is recorded on verification
        failure, and a crash leaves the usual awaiting_ack retry state.
        """
        if not self.project.storage["release_outbox"]:
            return
        from .client import verify_object

        with file_lock(self.root / "queue.lock", timeout=0):
            eligible = self._releasable_outbox(completing)
        for ident in sorted(eligible):
            lock = no_links(self.root / "outbox-locks" / (ident + ".lock"), self.root)
            with file_lock(lock):
                archive = no_links(bulk / "outbox" / (ident + ".tar.gz"), bulk)
                retained = no_links(bulk / "objects" / ident, bulk)
                with file_lock(self.root / "queue.lock", timeout=0):
                    if ident not in self._releasable_outbox(completing) or not archive.exists():
                        continue
                    if not retained.exists():
                        # include_inputs=false: retain the only source-owned frozen copy.
                        continue
                    paths = (archive, retained / "archive.tar.gz", retained / "OBJECT.json")
                    before = [self._outbox_fingerprint(path, bulk) for path in paths]
                # Only this redundant source upload copy; retain the verified full object.
                verify_object(
                    retained,
                    ident,
                    max_bytes=self.project.storage["max_collection_mb"] << 20,
                )
                if sha(archive) != ident:
                    raise ValueError("outbox copy identity changed; refusing cleanup")
                with file_lock(self.root / "queue.lock", timeout=0):
                    if ident not in self._releasable_outbox(completing):
                        continue
                    if [self._outbox_fingerprint(path, bulk) for path in paths] != before:
                        raise ValueError("outbox or retained object changed during verification; refusing cleanup")
                    archive.unlink()
                    sync_directory(archive.parent)

    def sync(self, *, now=False, workflows=None):
        """One durable pass, optionally scoped to explicit existing workflows.

        Selection does not change queue order, identities, backoff or ownership.
        It lets a supervised watcher service an independent worker without first
        entering an unrelated long admission. Validate the whole selector before
        any reconciliation, so a typo cannot partially process the requested set.
        """
        selected = None
        if workflows is not None:
            if (not isinstance(workflows, (list, tuple)) or any(type(key) is not str for key in workflows)
                    or len(set(workflows)) != len(workflows)):
                raise ValueError("workflow selection must be a unique list or tuple of existing IDs")
            selected = set(workflows)
            for key in workflows:
                self._row(key)
        pending = list(self.db.execute("SELECT id FROM requests WHERE phase!='completed' ORDER BY created,id"))
        for row in pending:
            if selected is not None and row["id"] not in selected:
                continue
            with ExitStack() as locks:
                try:
                    locks.enter_context(self._sync_lock(row["id"]))
                except TimeoutError:
                    continue  # Another source process owns this exact workflow.
                try:
                    row = self._row(row["id"])
                    if row["phase"] == "completed" or row["attention"] or (not now and row["next_at"] > time.time()):
                        continue
                    if row["phase"] in {"queued", "remote"}:
                        # Validate local metadata/identities without walking the
                        # historical evidence store on every status poll. New
                        # admission and all write paths retain full capacity
                        # checks; no shared write lock is held for network I/O.
                        context = self._context(row, read_only=True)
                        self._poll_remote(row, *context[:3])
                        row = self._row(row["id"])
                    if self._partial_pending(row["id"]):
                        with ExitStack() as local:
                            try:
                                local.enter_context(self._collection_lock())
                            except TimeoutError:
                                continue
                            self._process_partial(self._row(row["id"]))
                    if row["phase"] not in {"queued", "remote"}:
                        with ExitStack() as local:
                            try:
                                local.enter_context(self._collection_lock())
                            except TimeoutError:
                                continue  # Reconcile this exact collection next pass.
                            bulk = self._process(self._row(row["id"]))
                        # Slow archive verification must not keep queue.lock.
                        # The per-workflow lock still owns this exact return.
                        self._release_outbox(bulk, completing=row["id"])
                        with file_lock(self.root / "queue.lock", timeout=0):
                            self._update(row["id"], phase="completed", error=None, failures=0, next_at=0)
                    current = self._row(row["id"])
                    if current["phase"] != "completed":
                        self._update(
                            row["id"],
                            failures=0,
                            error=None,
                            next_at=time.time() + self.project.recovery["poll_seconds"],
                        )
                except Exception as exc:
                    transient = isinstance(
                        exc,
                        (
                            StorageUnavailable,
                            urllib.error.URLError,
                            TimeoutError,
                            ConnectionError,
                            http.client.IncompleteRead,
                        ),
                    )
                    if isinstance(exc, urllib.error.HTTPError):
                        transient = exc.code in {408, 429, 500, 502, 503, 504, 507}
                    if isinstance(exc, OSError) and exc.errno in {
                        errno.ENOSPC,
                        errno.EIO,
                        errno.ENODEV,
                    }:
                        transient = True
                    failures = row["failures"] + 1
                    delay = min(
                        self.project.recovery["backoff_max_seconds"],
                        self.project.recovery["backoff_initial_seconds"]
                        * 2 ** min(failures - 1, 16),
                    )
                    delay *= random.uniform(0.8, 1)
                    # No exception URL/body/token is persisted in local research records.
                    error = (
                        f"HTTP {exc.code}"
                        if isinstance(exc, urllib.error.HTTPError)
                        else type(exc).__name__ + ": " + str(exc)[:500]
                    )
                    self._update(
                        row["id"],
                        failures=failures,
                        attention=not transient,
                        error=error,
                        next_at=time.time() + delay,
                    )
        return self.status()
