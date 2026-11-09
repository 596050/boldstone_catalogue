"""Durable DAG coordinator in the existing exclusively-owned worker SQLite store."""

import hashlib
import json
import shutil
import tempfile
import threading
import time
from contextlib import contextmanager
from pathlib import Path

from offload_service.core import CapacityError, Conflict
from v2.result import _safe_extract
from v2.safe_archive import expansion_budget

from .common import atomic, canonical, digest, hash_id, load, name
from .objects import ObjectStore
from .output_manifest import native_summary, validate_ports
from .spec import RESOURCE_KEYS, TERMINAL, identity, output_plan, selected_ports, validate


class Coordinator:
    def __init__(self, worker, config):
        self.worker = worker
        self.root = worker.root / "workflows"
        self.root.mkdir(exist_ok=True, mode=0o700)
        self.objects = ObjectStore(
            self.root,
            **{
                key: config[key]
                for key in ("max_object_mb", "max_store_mb", "min_free_mb")
                if key in config
            },
        )
        from .data_references import DataSources

        self.data_sources = DataSources(self.objects, config.get("data_sources", {}))
        self.guard = threading.RLock()
        # Exactly one tick may reconcile/prepare nodes. Slow byte verification
        # and output packing must not own the separate HTTP control-plane lock.
        self.tick_guard = threading.Lock()
        self.admission_locks = {}
        self.stop = threading.Event()
        self.thread = None
        with worker.db_lock:
            worker.db.executescript("""
                CREATE TABLE IF NOT EXISTS workflows (
                    id TEXT PRIMARY KEY, identity TEXT NOT NULL, spec TEXT NOT NULL,
                    profiles TEXT NOT NULL, created REAL NOT NULL, cancelled INTEGER DEFAULT 0);
                CREATE TABLE IF NOT EXISTS workflow_nodes (
                    workflow TEXT NOT NULL, id TEXT NOT NULL, state TEXT NOT NULL,
                    attempt INTEGER NOT NULL DEFAULT 1, job_id TEXT,
                    manifest TEXT, error TEXT,
                    PRIMARY KEY(workflow,id));
                CREATE TABLE IF NOT EXISTS workflow_attempts (
                    workflow TEXT NOT NULL, node TEXT NOT NULL, attempt INTEGER NOT NULL,
                    job_id TEXT NOT NULL, state TEXT NOT NULL, manifest TEXT, error TEXT,
                    PRIMARY KEY(workflow,node,attempt));
                CREATE TABLE IF NOT EXISTS workflow_deliveries (
                    workflow TEXT NOT NULL, digest TEXT NOT NULL, manifest TEXT NOT NULL,
                    acknowledged REAL, PRIMARY KEY(workflow,digest));
                CREATE TABLE IF NOT EXISTS workflow_revocations (
                    workflow TEXT PRIMARY KEY, identity TEXT NOT NULL, created REAL NOT NULL);
            """)

    def capabilities(self):
        return {
            "schema": "marketmaker.workflow_capabilities.v1",
            "backend": self.worker.backend,
            "workflow_schema": "marketmaker.research_offload_workflow.v1",
            "object_schemas": ['marketmaker.offload_object.v1', 'marketmaker.offload_object.v2'],
            "deduplicated_outputs": True,
            "input_modes": ["bundle", "dataset_ref", "artifact_ref", "data_ref"],
            "data_reference_sources": {key: {"type": value["type"]}
                                       for key, value in self.data_sources.profiles.items()},
            "data_reference_acquisition": "worker_before_admission_pinned_sealed_objects",
            "independent_candidate_batches": True,
            "multi_model_run_batches": True,
            "comparison_policy": "explicit_per_run_candidate_and_benchmark_roles",
            "dynamic_data_policy": "declared_offline_producers_only",
            "python_environment_bundles": True,
            "portable_input_documents": True,
            "workflow_input_budget_preflight": True,
            "durable_admission_revocation": True,
            "max_workflow_nodes": 128,
            "max_parallel_jobs": self.worker.concurrency,
            "scheduling": "ready_nodes_within_worker_slots_and_aggregate_resource_limits",
            "cross_worker_dag_scheduling": False,
            "capacity": self.worker.capacity,
            "runtimes": {
                name: {
                    "image_id": self.worker.images.get(t.name),
                    **{key: getattr(t, key) for key in RESOURCE_KEYS},
                    "max_input_mb": t.max_input_mb,
                }
                for name, t in self.worker.profiles.items()
            },
            "trusted_local_is_sandbox": False,
            "multi_tenant": False,
        }

    def _profiles(self, spec):
        bound = {}
        from .capsule import snapshot

        with tempfile.TemporaryDirectory(prefix=".runner-", dir=self.root) as temporary:
            selected = Path(temporary) / "code"
            snapshot(
                Path(__file__).parent / "execution", selected,
                include=["run.py", "stage_runner.py", "environment.py", "portable.py"]
            )
            runner_object = self.objects.ingest(selected)
        for job in spec["jobs"]:
            profile = self.worker.profiles.get(job["runtime"])
            if profile is None:
                raise ValueError("unknown approved runtime: " + job["runtime"])
            resources = {key: getattr(profile, key) for key in RESOURCE_KEYS}
            for key, value in job["resources"].items():
                if value > resources[key]:
                    raise ValueError("requested resource exceeds approved runtime")
                resources[key] = value
            if resources["max_output_mb"] > resources["max_work_mb"]:
                raise ValueError("output budget exceeds scratch budget")
            bound[job["id"]] = {
                "template": profile.name,
                "resources": resources,
                "max_input_mb": profile.max_input_mb,
                "runner_object": runner_object,
                "image_id": self.worker.images.get(profile.name),
            }
        return bound

    def preflight(self, raw):
        spec = validate(raw)
        bound = self._profiles(spec)
        inputs = {}
        verified = {}
        resolutions = {}

        def checked(ident):
            # This one admission verifies every distinct object completely.
            # The cache never survives this call; attempts reverify their mounts.
            if ident not in verified:
                verified[ident] = self.objects.get(ident)
            return verified[ident]

        # The runtime is an execution input too. Idempotent ingest can find a
        # compacted completed-store copy; verify/restore it before admission.
        for profile in bound.values():
            checked(profile["runner_object"])

        for job in spec["jobs"]:
            root, manifest = checked(job["capsule"])
            expected = (
                job["entrypoint"]
                if job["kind"] in {"producer", "report"}
                else job["testing"]["repository"] + "/research/testing_stages/testing.py"
            )
            if expected not in manifest["files"]:
                raise ValueError("capsule entrypoint missing: " + expected)
            if job["kind"] == "testing_stage" and self.worker.backend != "docker":
                raise ValueError("portable testing checkpoints require Docker")
            refs = {}
            for port, source in job["inputs"].items():
                if source["mode"] == "bundle":
                    checked(source["object_sha256"])
                    refs[port] = source["object_sha256"]
                elif source["mode"] == "data_ref":
                    ref_key = digest(source)
                    if ref_key not in resolutions:
                        resolutions[ref_key] = self.data_sources.resolve(source)
                    bound[job["id"]].setdefault("data_references", {})[port] = resolutions[ref_key]
                    checked(source["object_sha256"])
                    refs[port] = source["object_sha256"]
                elif source["mode"] == "dataset_ref":
                    ident = self.objects.dataset_identity(
                        source["dataset_id"], source["version"], source["object_sha256"]
                    )
                    checked(ident)
                    refs[port] = source["object_sha256"]
                else:
                    refs[port] = {"producer": source["job"], "port": source["output"]}
            inputs[job["id"]] = refs
        from .input_budget import preflight as input_budget

        budget = input_budget(spec,
            {ident: sum(row["bytes"] for row in manifest["files"].values())
             for ident, (_, manifest) in verified.items()},
            {key: {"max_input_mb": profile.max_input_mb, "max_output_mb": profile.max_output_mb}
             for key, profile in self.worker.profiles.items()})
        rejected = [row["job"] for row in budget["jobs"] if row["status"] == "DEFINITE_INPUT_BUDGET_REJECTION"]
        if rejected:
            raise ValueError("workflow inputs exceed approved runtime input limit before producer execution: " + ", ".join(rejected))
        return (
            spec,
            bound,
            {
                "status": "INPUTS_VERIFIED",
                "workflow_sha256": identity(spec),
                "inputs": inputs,
                "profiles": bound,
                "input_budget": budget,
                "output_plan": output_plan(spec),
                "scientific_preflight": "NOT_RUN",
                "plugin_code_executed": False,
            },
        )

    @contextmanager
    def _admission(self, key):
        with self.guard:
            if key not in self.admission_locks and len(self.admission_locks) >= self.worker.max_pending:
                raise CapacityError("concurrent admission capacity exhausted")
            entry = self.admission_locks.setdefault(key, [threading.Lock(), 0])
            entry[1] += 1
        try:
            with entry[0]:
                yield
        finally:
            with self.guard:
                entry[1] -= 1
                if not entry[1]:
                    del self.admission_locks[key]

    def submit(self, raw):
        # Resolve idempotency before looking at mutable operator configuration.
        spec = validate(raw)
        ident = identity(spec)
        # A slow new dataset must not hold the DAG's control-plane lock. Calls
        # for the same submission remain fenced, including lost-reply retries.
        with self._admission(spec["submission_id"]):
            with self.worker.db_lock:
                self._check_revocation(self.worker.db, spec["submission_id"], ident)
                old = self.worker.db.execute(
                    "SELECT identity FROM workflows WHERE id=?", (spec["submission_id"],)
                ).fetchone()
            if old:
                if old[0] != ident:
                    raise Conflict("submission ID already has a different workflow")
                return self.status(spec["submission_id"]), False
            try:
                spec, bound, _ = self.preflight(spec)
            except KeyError as error:
                raise ValueError(
                    "workflow input is not a committed object or registered dataset: " + str(error)
                ) from error
            # This observational scan makes no reservation. Object commits have
            # their own capacity gate; the node count is checked transactionally
            # below. Do not block other workflows' snapshots during slow I/O.
            self.objects.capacity()
            with self.guard:
                with self.worker.transaction() as db:
                    # Revocation can commit while input verification is still
                    # running. Check in this transaction before publishing nodes.
                    self._check_revocation(db, spec["submission_id"], ident)
                    pending = db.execute(
                        "SELECT COUNT(*) FROM workflow_nodes WHERE state NOT IN "
                        "('succeeded','failed','interrupted','cancelled','blocked_dependency')"
                    ).fetchone()[0]
                    if pending + len(spec["jobs"]) > self.worker.max_pending:
                        raise CapacityError("workflow pending-node capacity exhausted")
                    db.execute(
                        "INSERT INTO workflows(id,identity,spec,profiles,created) VALUES (?,?,?,?,?)",
                        (spec["submission_id"], ident, canonical(spec), canonical(bound), time.time()),
                    )
                    for job in spec["jobs"]:
                        db.execute(
                            "INSERT INTO workflow_nodes(workflow,id,state) VALUES (?,?,'waiting')",
                            (spec["submission_id"], job["id"]),
                        )
                return self.status(spec["submission_id"]), True

    @staticmethod
    def _check_revocation(db, workflow, ident):
        row = db.execute(
            "SELECT identity FROM workflow_revocations WHERE workflow=?", (workflow,)
        ).fetchone()
        if row:
            if row[0] != ident:
                raise Conflict("revoked submission ID belongs to a different workflow")
            raise Conflict("workflow admission has been revoked")

    def revocation(self, workflow):
        name(workflow)
        with self.worker.db_lock:
            row = self.worker.db.execute(
                "SELECT identity,created FROM workflow_revocations WHERE workflow=?", (workflow,)
            ).fetchone()
        if row is None:
            raise KeyError(workflow)
        return {
            "schema": "marketmaker.offload_workflow_revocation.v1",
            "workflow_id": workflow,
            "workflow_sha256": row[0],
            "revoked_at": row[1],
            "admission_revoked": True,
            "execution_stopped": "NOT_ESTABLISHED_BY_REVOCATION",
        }

    def revoke(self, workflow, expected_identity):
        """Reserve an exact ID against late admission, including after restart."""
        name(workflow)
        hash_id(expected_identity)
        # Do not acquire the per-workflow admission lock: verification can hold
        # it for hours. Only the short commit transaction must serialize here.
        with self.guard:
            with self.worker.transaction() as db:
                existing = db.execute("SELECT identity FROM workflows WHERE id=?", (workflow,)).fetchone()
                revoked = db.execute(
                    "SELECT identity FROM workflow_revocations WHERE workflow=?", (workflow,)
                ).fetchone()
                if any(row is not None and row[0] != expected_identity for row in (existing, revoked)):
                    raise Conflict("submission ID belongs to a different workflow")
                db.execute(
                    "INSERT OR IGNORE INTO workflow_revocations(workflow,identity,created) VALUES (?,?,?)",
                    (workflow, expected_identity, time.time()),
                )
            # A matching workflow might have committed immediately before this
            # transaction. Its ordinary cancellation path still needs to run.
            status = self.cancel(workflow) if existing is not None else None
            return {"revocation": self.revocation(workflow), "workflow": status}

    def _row(self, workflow):
        name(workflow)
        with self.worker.db_lock:
            row = self.worker.db.execute(
                "SELECT * FROM workflows WHERE id=?", (workflow,)
            ).fetchone()
            if not row:
                raise KeyError(workflow)
            nodes = self.worker.db.execute(
                "SELECT * FROM workflow_nodes WHERE workflow=? ORDER BY id", (workflow,)
            ).fetchall()
        return dict(row), [dict(node) for node in nodes]

    def status(self, workflow):
        row, nodes = self._row(workflow)
        states = {node["state"] for node in nodes}
        complete = states <= TERMINAL
        state = (
            ("completed" if states == {"succeeded"} else "completed_with_errors")
            if complete
            else "running"
        )
        observations = {}
        # Read stored phase transitions only. Status polling must never hash
        # inputs, touch a container, or refresh an execution observation's time.
        with self.worker.db_lock:
            for node in nodes:
                if node["job_id"]:
                    receipt = self.worker.db.execute("SELECT receipt FROM jobs WHERE id=?",
                                                     (node["job_id"],)).fetchone()
                    if receipt and receipt[0]:
                        observation = json.loads(receipt[0]).get("worker_phase")
                        if observation:
                            observations[node["id"]] = observation
        return {
            "schema": "marketmaker.offload_workflow_status.v1",
            "workflow_id": workflow,
            "workflow_sha256": row["identity"],
            "state": state,
            "terminal": complete,
            "nodes": [
                {
                    **{k: n[k] for k in ("id", "state", "attempt", "job_id", "error")},
                    "outputs": json.loads(n["manifest"]) if n["manifest"] else None,
                    **({"worker_phase": observations[n["id"]]} if n["id"] in observations else {}),
                }
                for n in nodes
            ],
            "performance_qualification": "NOT_ESTABLISHED",
        }

    def cancel(self, workflow):
        with self.guard:
            self._row(workflow)
            with self.worker.transaction() as db:
                db.execute("UPDATE workflows SET cancelled=1 WHERE id=?", (workflow,))
            _, nodes = self._row(workflow)
            for node in nodes:
                if node["state"] not in TERMINAL:
                    if node["job_id"]:
                        try:
                            self.worker.cancel(node["job_id"])
                        except KeyError:
                            # Recovery window: intended ID recorded, job never
                            # admitted. Durable cancellation must still win.
                            self._set(workflow, node["id"], "cancelled", error="workflow cancelled")
                    else:
                        self._set(workflow, node["id"], "cancelled", error="workflow cancelled")
            return self.status(workflow)

    def resume(self, workflow):
        """Explicitly retry only reconciled interrupted attempts, never semantic failure."""
        with self.guard:
            row, nodes = self._row(workflow)
            if row["cancelled"]:
                raise Conflict("cancelled workflows require a new submission")
            specs = {j["id"]: j for j in json.loads(row["spec"])["jobs"]}
            retried = False
            for node in nodes:
                if (
                    node["state"] != "interrupted"
                    or node["attempt"] >= specs[node["id"]]["max_attempts"]
                ):
                    continue
                old = self.worker.status(node["job_id"])
                if old["state"] != "interrupted" or old.get("receipt", {}).get("termination_error"):
                    raise Conflict("previous attempt has not been reconciled as stopped")
                with self.worker.transaction() as db:
                    db.execute(
                        "UPDATE workflow_nodes SET state='waiting',attempt=attempt+1,job_id=NULL,"
                        "manifest=NULL,error=NULL WHERE workflow=? AND id=?",
                        (workflow, node["id"]),
                    )
                retried = True
            if retried:
                with self.worker.transaction() as db:
                    db.execute(
                        "UPDATE workflow_nodes SET state='waiting',error=NULL WHERE workflow=? "
                        "AND state='blocked_dependency' AND job_id IS NULL",
                        (workflow,),
                    )
            return self.status(workflow)

    def _set(self, workflow, node, state, *, manifest=None, error=None):
        with self.worker.transaction() as db:
            encoded = canonical(manifest) if manifest is not None else None
            db.execute(
                "UPDATE workflow_nodes SET state=?,manifest=?,error=? WHERE workflow=? AND id=?",
                (state, encoded, error, workflow, node),
            )
            db.execute(
                "UPDATE workflow_attempts SET state=?,manifest=?,error=? WHERE workflow=? AND node=? "
                "AND attempt=(SELECT attempt FROM workflow_nodes WHERE workflow=? AND id=?)",
                (state, encoded, error, workflow, node, workflow, node),
            )

    def _dispatch(self, row, job, node, all_nodes):
        from .worker import MountedTemplate

        profiles = json.loads(row["profiles"])
        bound = profiles[job["id"]]
        job_id = (
            "wf-"
            + hashlib.sha256(f"{row['id']}/{job['id']}/{node['attempt']}".encode()).hexdigest()[:40]
        )
        inputs = {}
        for port, ref in job["inputs"].items():
            if ref["mode"] == "artifact_ref":
                parent = all_nodes[ref["job"]]
                manifest = json.loads(parent["manifest"] or "{}")
                published = manifest.get("ports", {}).get(ref["output"], {})
                if published.get("status") != "VERIFIED":
                    raise ValueError("upstream output is unavailable")
                inputs[port] = published["object_sha256"]
            else:
                inputs[port] = ref["object_sha256"]
        request = {
            "workflow_sha256": row["identity"],
            "job": job,
            "inputs": inputs,
            "capsule": job["capsule"],
            "image_id": bound["image_id"],
            "resources": bound["resources"],
            "runner_object": bound["runner_object"],
            "dependencies": {
                key: {
                    "state": all_nodes[key]["state"],
                    "attempt": all_nodes[key]["attempt"],
                    "error": all_nodes[key]["error"],
                    "ports": json.loads(all_nodes[key]["manifest"] or "{}").get("ports", {}),
                }
                for key in job["depends_on"]
            },
        }
        launch = self.root / "launch" / job_id
        launch.mkdir(parents=True, exist_ok=True)
        config = launch / "job.json"
        if config.exists() and load(config) != request:
            raise Conflict("persisted launch differs from frozen workflow")
        if not config.exists():
            atomic(config, request)
        mounts = [{"object_sha256": job["capsule"], "target": "capsule"}]
        mounts += [
            {"object_sha256": ident, "target": "inputs/" + port} for port, ident in inputs.items()
        ]
        data = [(config, "job.json")]
        total_inputs = 0
        for mount in mounts:
            # This is a capacity estimate, not a new content trust boundary.
            # Full checks remain at admission, before execution, and afterwards.
            total_inputs += self.objects.declared_size(mount["object_sha256"])
        if total_inputs > bound["max_input_mb"] * (1 << 20):
            raise ValueError("resolved inputs exceed approved runtime input limit")
        runtime = self.objects.get(bound["runner_object"])[0] / "data"
        template = MountedTemplate(
            name=bound["template"],
            entrypoint=runtime / "run.py",
            code_dir=runtime,
            data=tuple(data),
            image=bound["image_id"] or "simulation",
            max_input_mb=bound["max_input_mb"],
            mounts=tuple(mounts),
            **bound["resources"],
        )
        with self.guard:
            latest, records = self._row(row["id"])
            current = {n["id"]: n for n in records}
            actual = current[job["id"]]
            if actual["state"] in TERMINAL or actual["attempt"] != node["attempt"]:
                return
            if latest["cancelled"]:
                # Cancellation can arrive while hashing, including recovery of
                # an intended ID never committed to the worker job queue.
                if actual["job_id"]:
                    try:
                        self.worker.cancel(actual["job_id"])
                    except KeyError:
                        self._set(row["id"], job["id"], "cancelled", error="workflow cancelled")
                else:
                    self._set(row["id"], job["id"], "cancelled", error="workflow cancelled")
                return
            if any(any(current[key][field] != all_nodes[key][field]
                       for field in ("state", "attempt", "manifest")) for key in job["depends_on"]):
                return  # An explicit resume changed a parent; re-resolve next tick.
            with self.worker.transaction() as db:
                db.execute(
                    "UPDATE workflow_nodes SET state='dispatching',job_id=? WHERE workflow=? AND id=?",
                    (job_id, row["id"], job["id"]),
                )
                db.execute(
                    "INSERT OR IGNORE INTO workflow_attempts(workflow,node,attempt,job_id,state) "
                    "VALUES (?,?,?,?,'dispatching')",
                    (row["id"], job["id"], node["attempt"], job_id),
                )

        def admission_check(db):
            # Called only while the worker owns its DB transaction. Never take
            # self.guard here: all control operations acquire guard before DB.
            # This fences cancellation even if it arrived before the intended
            # job ID existed, and rejects a parent changed by explicit resume.
            latest = db.execute("SELECT identity,cancelled FROM workflows WHERE id=?", (row["id"],)).fetchone()
            if latest is None or latest["identity"] != row["identity"] or latest["cancelled"]:
                return False
            current = {n["id"]: n for n in db.execute(
                "SELECT id,state,attempt,job_id,manifest FROM workflow_nodes WHERE workflow=?", (row["id"],))}
            actual = current.get(job["id"])
            return bool(actual is not None and actual["state"] not in TERMINAL
                and actual["attempt"] == node["attempt"] and actual["job_id"] == job_id
                and all(key in current and all(current[key][field] == all_nodes[key][field]
                    for field in ("state", "attempt", "manifest")) for key in job["depends_on"]))

        execution, _ = self.worker.submit(
            {
                "job_id": job_id,
                "template": template.name,
                "metadata": {
                    "workflow_sha256": row["identity"],
                    "workflow_image_id": bound["image_id"],
                },
            },
            template_override=template,
            admission_check=admission_check,
        )
        with self.guard:
            _, records = self._row(row["id"])
            actual = next(n for n in records if n["id"] == job["id"])
            if (actual["state"] not in TERMINAL and actual["attempt"] == node["attempt"]
                    and actual["job_id"] == job_id):
                # Terminal worker results still need their verified output
                # envelope. Do not hide them by marking the DAG node terminal.
                self._set(row["id"], job["id"],
                    "verifying" if execution["state"] in TERMINAL else execution["state"])

    def _publish(self, row, job, node, execution):
        bound = json.loads(row["profiles"])[job["id"]]
        envelope = {
            "schema": "marketmaker.offload_output_manifest.v1",
            "workflow_sha256": row["identity"],
            "node_id": job["id"],
            "attempt": node["attempt"],
            "job_id": node["job_id"],
            "output_plan_sha256": digest(output_plan(json.loads(row["spec"]))),
            "execution": execution,
            "ports": {},
            "output_status": "NOT_PRODUCED",
            "performance_qualification": "NOT_ESTABLISHED",
        }
        launch = load(self.root / "launch" / node["job_id"] / "job.json")
        envelope.update(
            capsule_sha256=job["capsule"],
            input_objects=launch["inputs"],
            runner_object_sha256=bound["runner_object"],
            resources=bound["resources"],
            dependencies=launch["dependencies"],
        )
        if bound.get("data_references"):
            envelope["data_references"] = bound["data_references"]
        state, error = execution["state"], None
        try:
            if not (execution.get("receipt") or {}).get("result_sha256"):
                error = (execution.get("receipt") or {}).get("error", "no result archive")
            else:
                archive, _ = self.worker.result(node["job_id"])
                expanded, members = expansion_budget(
                    archive, max_bytes=bound["resources"]["max_output_mb"] * (1 << 20)
                )
                # A tiny producer return must not reserve three copies of a
                # model's maximum output allowance. Each object ingest still
                # checks its own real storage use and preserves the free reserve.
                self.objects.capacity(expanded * 3)
                with tempfile.TemporaryDirectory(prefix=".publish-", dir=self.root) as temp:
                    root = Path(temp) / "result"
                    _safe_extract(
                        archive, root, max_bytes=expanded, max_members=members
                    )
                    ports = validate_ports(
                        root, job, max_bytes=bound["resources"]["max_output_mb"] * (1 << 20)
                    )
                    try:
                        envelope["native_result"] = native_summary(root, job)
                        if (envelope["native_result"] or {}).get(
                            "status"
                        ) == "STOPPED_AT_GATE" and state == "succeeded":
                            state = "failed"
                            error = "native gates stopped despite a zero process exit code"
                        errors = [
                            p["error"] for p in ports.values() if p["status"] == "OUTPUT_INVALID"
                        ]
                        if errors:
                            raise ValueError("; ".join(errors))
                        envelope["output_status"] = "VERIFIED"
                    except (ValueError, OSError, KeyError, TypeError) as exc:
                        envelope["output_status"] = "OUTPUT_INVALID"
                        error = str(exc)
                        if state == "succeeded":
                            state = "failed"
                    for port, details in ports.items():
                        if details["status"] != "VERIFIED":
                            envelope["ports"][port] = details
                            continue
                        path = root / details["path"]
                        if path.is_file():
                            source = Path(temp) / ("port-" + port)
                            source.mkdir()
                            shutil.copyfile(path, source / path.name)
                        else:
                            source = path
                        ident = self.objects.ingest(source, deduplicate=True)
                        envelope["ports"][port] = {k: v for k, v in details.items() if k != "files"}
                        envelope["ports"][port].update(
                            object_sha256=ident, file_count=len(details["files"])
                        )
                    # A bounded diagnostic archive is retained even for invalid outputs.
                    diagnostics = Path(temp) / "diagnostics"
                    diagnostics.mkdir()
                    for filename in ("status.json", "WORKFLOW_EXECUTION.json", "run.log"):
                        path = root / filename
                        if path.is_file() and path.stat().st_size <= 4 << 20:
                            shutil.copyfile(path, diagnostics / filename)
                    atomic(diagnostics / "EXECUTION_RECEIPT.json", execution)
                    envelope["diagnostics_object"] = self.objects.ingest(diagnostics, deduplicate=True)
        except CapacityError:
            # Publication can be retried without recomputing the job.
            raise
        except Exception as exc:
            envelope["output_status"] = "OUTPUT_INVALID"
            error = str(exc)
            if state == "succeeded":
                state = "failed"
        self._set(row["id"], job["id"], state, manifest=envelope, error=error)

    def tick(self):
        with self.tick_guard:
            with self.worker.db_lock:
                terminal = tuple(sorted(TERMINAL))
                placeholders = ",".join("?" for _ in terminal)
                workflows = self.worker.db.execute(
                    "SELECT w.id FROM workflows w WHERE EXISTS ("
                    "SELECT 1 FROM workflow_nodes n WHERE n.workflow=w.id "
                    f"AND n.state NOT IN ({placeholders})) ORDER BY w.created",
                    terminal,
                ).fetchall()
            for (workflow,) in workflows:
                _, records = self._row(workflow)
                for record in records:
                    # Terminal receipts are read by status/delivery and by active
                    # dependants, not repeatedly by idle reconciliation. Explicit
                    # resume changes their state and makes the next tick eligible.
                    if record["state"] not in TERMINAL:
                        self._tick_node(workflow, record["id"])

    def _tick_node(self, workflow, key):
        execution = None
        with self.guard:
            row, records = self._row(workflow)
            nodes = {n["id"]: n for n in records}
            node = nodes[key]
            if node["state"] in TERMINAL:
                return
            job = next(j for j in json.loads(row["spec"])["jobs"] if j["id"] == key)
            if node["job_id"]:
                try:
                    execution = self.worker.status(node["job_id"])
                except KeyError:
                    pass  # Recover intended ID not yet committed to the job queue.
                if execution and execution["state"] not in TERMINAL:
                    self._set(workflow, key, execution["state"])
                    return
            elif row["cancelled"]:
                self._set(workflow, key, "cancelled", error="workflow cancelled")
                return
            else:
                dependencies = [nodes[d] for d in job["depends_on"]]
                if not all(d["state"] in TERMINAL for d in dependencies):
                    return
                if job["condition"] != "all_terminal" and any(d["state"] != "succeeded" for d in dependencies):
                    self._set(workflow, key, "blocked_dependency", error="required upstream job did not qualify")
                    return
        # Hash checks and packing can take minutes for real market inputs.
        # tick_guard prevents duplicate preparation; guard stays available to
        # cancellation, new admission, resume and immutable delivery snapshots.
        if execution:
            try:
                self._publish(row, job, node, execution)
            except CapacityError:
                with self.guard:
                    self._set(workflow, key, "verifying", error="output storage capacity exhausted")
        else:
            try:
                self._dispatch(row, job, node, nodes)
            except CapacityError:
                pass
            except Exception as exc:
                with self.guard:
                    latest, records = self._row(workflow)
                    current = next(n for n in records if n["id"] == key)
                    if current["attempt"] == node["attempt"] and current["state"] not in TERMINAL:
                        self._set(workflow, key, "cancelled" if latest["cancelled"] else "failed", error=str(exc))

    def delivery(self, workflow, *, partial=False):
        with self.guard:
            row, _ = self._row(workflow)
            status = self.status(workflow)
            if not status["terminal"] and not partial:
                raise Conflict("workflow is not terminal; use status for partial results")
            spec = json.loads(row["spec"])
            selected = selected_ports(spec)
            objects = {}
            remote = {}
            for node in status["nodes"]:
                manifest = node["outputs"] or {}
                diagnostic = manifest.get("diagnostics_object")
                if diagnostic:
                    objects[node["id"] + ".__diagnostics__"] = diagnostic
                for port, entry in manifest.get("ports", {}).items():
                    if entry.get("object_sha256"):
                        key = node["id"] + "." + port
                        (objects if key in selected else remote)[key] = entry["object_sha256"]
            if spec["return_policy"]["include_inputs"]:
                for job in spec["jobs"]:
                    objects[job["id"] + ".__capsule__"] = job["capsule"]
                    for port, ref in job["inputs"].items():
                        if ref["mode"] != "artifact_ref":
                            objects[job["id"] + ".__input_" + port + "__"] = ref["object_sha256"]
                for node in status["nodes"]:
                    for port, ident in (node["outputs"] or {}).get("input_objects", {}).items():
                        objects[node["id"] + ".__input_" + port + "__"] = ident
            missing_local = sorted(set(spec["return_policy"]["require_local"]) - set(objects))
            with self.worker.db_lock:
                history = self.worker.db.execute(
                    "SELECT node,attempt,job_id,state,manifest,error FROM workflow_attempts "
                    "WHERE workflow=? ORDER BY node,attempt", (workflow,),
                ).fetchall()
            attempts = []
            current_attempt = {n["id"]: n["attempt"] for n in status["nodes"]}
            for attempt in history:
                value = dict(attempt)
                envelope = json.loads(value.pop("manifest") or "null")
                value["outputs"] = envelope
                attempts.append(value)
                if value["attempt"] == current_attempt[value["node"]] or not envelope:
                    continue
                prefix = value["node"] + ".__attempt_" + str(value["attempt"]) + "_"
                if envelope.get("diagnostics_object"):
                    objects[prefix + "diagnostics__"] = envelope["diagnostics_object"]
                for port, entry in envelope.get("ports", {}).items():
                    if entry.get("object_sha256"):
                        (objects if value["node"] + "." + port in selected else remote)[
                            prefix + port + "__"] = entry["object_sha256"]
                if spec["return_policy"]["include_inputs"]:
                    for port, ident in envelope.get("input_objects", {}).items():
                        objects[prefix + "input_" + port + "__"] = ident
            delivery = {
                "schema": "marketmaker.offload_delivery.v1",
                "workflow": spec,
                "output_plan": output_plan(spec),
                "status": status,
                "attempts": attempts,
                "objects": objects,
                "remote_only": remote,
                "required_local_missing": missing_local,
                "final": status["terminal"],
                "required_inputs_available_locally": "NOT_CHECKED",
                "automatic_delete": False,
            }
            ident = digest(delivery)
            with self.worker.transaction() as db:
                db.execute(
                    "INSERT OR IGNORE INTO workflow_deliveries(workflow,digest,manifest) VALUES (?,?,?)",
                    (workflow, ident, canonical(delivery)),
                )
            return {"delivery_sha256": ident, "manifest": delivery}

    def acknowledge(self, workflow, ident):
        from .common import hash_id

        name(workflow)
        hash_id(ident)
        with self.worker.transaction() as db:
            cursor = db.execute(
                "UPDATE workflow_deliveries SET acknowledged=? WHERE workflow=? AND digest=?",
                (time.time(), workflow, ident),
            )
            if cursor.rowcount != 1:
                raise Conflict("unknown delivery manifest")
        return {"delivery_sha256": ident, "acknowledged": True, "deleted": False}

    def start(self):
        if self.thread:
            return

        def loop():
            try:
                while not self.stop.is_set() and not self.worker.stop.is_set():
                    self.tick()
                    self.stop.wait(0.1)
            except Exception as exc:
                atomic(
                    self.root / "COORDINATOR_ERROR.json",
                    {"error": str(exc), "type": type(exc).__name__, "at": time.time()},
                )
                self.worker.stop.set()

        self.thread = threading.Thread(
            target=loop, name="research-workflow-coordinator", daemon=True
        )
        self.thread.start()

    def close(self):
        self.stop.set()
        if self.thread:
            self.thread.join(timeout=30)
            if self.thread.is_alive():
                raise RuntimeError("workflow coordinator has not stopped")
