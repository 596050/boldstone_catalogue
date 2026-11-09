"""Workflow acceptance tests. Synthetic inputs only; no real research is launched."""

import io
import json
import os
import tarfile
import threading
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from pathlib import Path
from urllib.error import HTTPError

import pytest

from offload_service.core import CapacityError, Conflict, Worker
from offload_service.http_api import Server
from research_workflows.capsule import research_selection, snapshot
from research_workflows.client import Client, verify_collection, verify_object
from research_workflows.common import atomic, load, parse, sha
from research_workflows.objects import ObjectStore, pack
from research_workflows.output_manifest import validate_ports
from research_workflows.planner import plan
from research_workflows.resolver import resolve
from research_workflows.simulation import configuration, fixture, run, workflow
from research_workflows.spec import SCHEMA, selected_ports, validate
from research_workflows.worker import WorkflowWorker

TOKEN = "s" * 43


@pytest.fixture
def worker(tmp_path):
    with WorkflowWorker(
        tmp_path / "worker",
        [],
        backend="trusted-local",
        workflow_config=configuration(),
        concurrency=2,
        min_free_mb=0,
    ) as value:
        yield value


@pytest.fixture
def api(worker):
    server = Server(("127.0.0.1", 0), worker, TOKEN)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield Client(f"http://127.0.0.1:{server.server_port}", TOKEN)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        assert not thread.is_alive()


def compiled(tmp_path, worker, *, edit=None):
    code, data = fixture(tmp_path)
    ref = worker.workflows.objects.register_dataset("data", "one", data)
    request = workflow(code, data, ref)
    if edit:
        edit(request)
    target = tmp_path / "compiled"
    plan(request, target)
    for path in (target / "objects").glob("*.tar.gz"):
        store = worker.workflows.objects
        ident = sha(path)
        state = store.begin(ident, path.stat().st_size)
        if state["state"] != "committed":
            store.append(ident, 0, path.read_bytes())
            store.commit(ident)
    return load(target / "WORKFLOW.json"), target


def drive(worker, submission="synthetic-offload", limit=40):
    """Deterministic scheduler simulation, still using real isolated subprocesses."""
    for _ in range(limit):
        worker.workflows.tick()
        status = worker.workflows.status(submission)
        if status["terminal"]:
            return status
        worker.process_next()
    pytest.fail("workflow did not finish: " + json.dumps(status))


def basic():
    return {
        "schema": SCHEMA,
        "submission_id": "unit",
        "jobs": [
            {
                "id": "one",
                "kind": "producer",
                "runtime": "python",
                "capsule": "a" * 64,
                "entrypoint": "main.py",
                "outputs": {"value": {"type": "json", "path": "artifacts/value.json"}},
            }
        ],
    }


def test_preflight_restores_compacted_runtime_before_submission(tmp_path, worker):
    from research_workflows.compressed import compact_object

    spec, _ = compiled(tmp_path, worker)
    _, profiles, _ = worker.workflows.preflight(spec)
    identity = next(iter(profiles.values()))["runner_object"]
    store = worker.workflows.objects
    root, _ = store.get(identity)
    compact_object(root, identity, max_bytes=store.max_bytes)
    assert not (root / "data").exists()
    _, restored, _ = worker.workflows.preflight(spec)
    assert {row["runner_object"] for row in restored.values()} == {identity}
    assert (root / "data/run.py").is_file()
    worker.workflows.submit(spec)
    assert drive(worker)["state"] == "completed"


def test_preflight_rejects_damaged_runtime_before_submission(tmp_path, worker):
    spec, _ = compiled(tmp_path, worker)
    _, profiles, _ = worker.workflows.preflight(spec)
    identity = next(iter(profiles.values()))["runner_object"]
    root, _ = worker.workflows.objects.get(identity)
    (root / "data/run.py").write_text("damaged execution helper")
    with pytest.raises(ValueError, match="inventory|manifest"):
        worker.workflows.preflight(spec)


def test_normalization_and_output_dependency_closure():
    raw = basic()
    raw["jobs"][0]["outputs"]["ledger"] = {
        "type": "tree",
        "path": "artifacts/ledger",
        "delivery": "remote",
    }
    raw["jobs"][0]["outputs"]["value"]["requires"] = ["one.ledger"]
    spec = validate(raw)
    assert validate(spec) == spec
    assert selected_ports(spec) == ["one.ledger", "one.value"]
    spec["return_policy"] = {"profile": "summary_and_refs", "ports": []}
    assert selected_ports(validate(spec)) == ["one.value"]
    spec["return_policy"] = {"profile": "selected", "ports": ["one.value"]}
    assert selected_ports(validate(spec)) == ["one.ledger", "one.value"]


@pytest.mark.parametrize(
    "change",
    [
        lambda r: r.update(unknown=True),
        lambda r: r["jobs"].append(deepcopy(r["jobs"][0])),
        lambda r: r["jobs"][0].update(depends_on=["one"]),
        lambda r: r["jobs"][0].update(depends_on=["missing"]),
        lambda r: r["jobs"][0].update(entrypoint="../escape.py"),
        lambda r: r["jobs"][0].update(entrypoint="C:\\escape.py"),
        lambda r: r["jobs"][0].update(entrypoint="CON.py"),
        lambda r: r["jobs"][0].update(resources={"memory_mb": True}),
        lambda r: r["jobs"][0].update(resources={"cpus": float("nan")}),
        lambda r: r["jobs"][0].update(condition="all_terminal"),
        lambda r: r["jobs"][0].update(args=["{input.unknown}"]),
        lambda r: r["jobs"][0]["outputs"]["value"].update(path="result.json"),
        lambda r: r["jobs"][0]["outputs"]["value"].update(requires=["one.value"]),
        lambda r: r["jobs"][0].update(inputs={"data": {"mode": "bundle", "path": "/private/data"}}),
    ],
)
def test_invalid_manifests_fail_closed(change):
    request = basic()
    change(request)
    with pytest.raises((ValueError, TypeError)):
        validate(request)


def test_graph_cycle_and_undeclared_artifact_dependency():
    raw = basic()
    second = deepcopy(raw["jobs"][0])
    second.update(id="two", depends_on=["one"])
    raw["jobs"].append(second)
    raw["jobs"][0]["depends_on"] = ["two"]
    with pytest.raises(ValueError, match="cycle"):
        validate(raw)
    raw["jobs"][0]["depends_on"] = []
    raw["jobs"][0]["inputs"] = {
        "upstream": {"mode": "artifact_ref", "job": "two", "output": "value"}
    }
    with pytest.raises(ValueError, match="explicit dependency"):
        validate(raw)


def test_json_rejects_duplicate_and_nonfinite_values():
    for text in ('{"x":1,"x":2}', '{"x":NaN}', '{"x":Infinity}'):
        with pytest.raises(ValueError):
            parse(text)


def test_deterministic_objects_resume_and_immutable_datasets(tmp_path):
    source = tmp_path / "input"
    source.mkdir()
    (source / "values.bin").write_bytes(bytes(range(255)))
    one, two = tmp_path / "one.tar.gz", tmp_path / "two.tar.gz"
    assert pack(source, one) == pack(source, two)
    store = ObjectStore(tmp_path / "store", max_object_mb=1, max_store_mb=8, min_free_mb=1)
    ident, data = sha(one), one.read_bytes()
    store.begin(ident, len(data))
    store.append(ident, 0, data[:40])
    assert store.append(ident, 0, data[:40])["offset"] == 40
    with pytest.raises(Conflict):
        store.append(ident, 0, b"different")
    with pytest.raises(Conflict):
        store.append(ident, 80, b"wrong offset")
    with pytest.raises(ValueError, match="incomplete"):
        store.commit(ident)
    assert store.begin(ident, len(data))["offset"] == 40
    store.append(ident, 40, data[40:])
    assert store.commit(ident)["state"] == "committed"
    assert store.commit(ident)["state"] == "committed"
    assert store.register_dataset("values", "v1", source)["object_sha256"] == ident
    (source / "values.bin").write_bytes(b"changed")
    assert (store.dataset("values", "v1", ident)[0] / "data/values.bin").read_bytes() == bytes(
        range(255)
    )
    with pytest.raises(Conflict):
        store.register_dataset("values", "v1", source)
    with pytest.raises(ValueError, match="mismatch"):
        store.dataset("values", "v1", "0" * 64)


def test_committed_status_and_begin_do_not_rehash_or_authorize_tampered_tree(tmp_path):
    source = tmp_path / "input"
    source.mkdir()
    (source / "values.bin").write_bytes(bytes(range(255)))
    archive = tmp_path / "one.tar.gz"
    packed = pack(source, archive)
    store = ObjectStore(tmp_path / "store", max_object_mb=1, max_store_mb=8, min_free_mb=1)
    ident, data = packed["object_sha256"], archive.read_bytes()
    store.begin(ident, len(data))
    store.append(ident, 0, data)
    assert store.commit(ident)["state"] == "committed"
    status = store.status(ident)
    assert status["state"] == "committed"
    assert status["bytes"] == len(data)
    assert status["manifest"] == packed["content_manifest"]
    root, manifest = store.get(ident)
    assert manifest == packed["content_manifest"]
    target = root / "data" / "values.bin"
    original = target.read_bytes()
    target.write_bytes(b"\xff" * len(original))
    again = store.status(ident)
    assert again["state"] == "committed"
    assert again["bytes"] == status["bytes"]
    assert again["manifest"] == packed["content_manifest"]
    assert store.begin(ident, len(data))["state"] == "committed"
    with pytest.raises(ValueError):
        store.get(ident)


def test_local_admission_timeout_covers_multi_gib_objects_and_cannot_exceed_deadline():
    from research_workflows.local import admission_timeout, store_limits

    small = admission_timeout(900, 256)
    large = admission_timeout(86400, 12288)
    assert 300 <= small <= 900
    assert large >= 7200
    assert large <= 86400
    assert admission_timeout(60, 12288) == 60
    compact = store_limits(256)
    full = store_limits(12288)
    assert compact["workflow_max_store_mb"] == 4096
    assert full["workflow_max_store_mb"] >= 24576
    assert full["worker_max_store_mb"] >= full["workflow_max_store_mb"]


def test_client_honors_explicit_request_timeout():
    from http.server import BaseHTTPRequestHandler, HTTPServer
    import threading
    import time as time_mod

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            time_mod.sleep(1)
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'{"ok": true}')

        def log_message(self, *_args):
            return

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        fast = Client(f"http://127.0.0.1:{server.server_port}", TOKEN, timeout=0.05)
        with pytest.raises(OSError):
            fast.request("/v1/health")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_unregistered_dataset_ref_is_bad_request_not_unknown_job(api, tmp_path, worker):
    spec, _compiled = compiled(tmp_path, worker)
    for job in spec["jobs"]:
        for source in job.get("inputs", {}).values():
            if source.get("mode") == "bundle":
                source.update(mode="dataset_ref", dataset_id="missing", version="v1")
    with pytest.raises(HTTPError) as exc:
        api.request("/v2/workflows", spec)
    assert exc.value.code == 400
    assert b"unknown job" not in exc.value.read()


def test_submit_cli_forwards_request_timeout_to_client():
    from research_workflows.cli import parser

    args = parser().parse_args(
        ["submit", "--plan", "plan", "--url", "http://127.0.0.1:9", "--token-file", "t",
         "--request-timeout", "7200"]
    )
    assert args.request_timeout == 7200
    default = parser().parse_args(
        ["submit", "--plan", "plan", "--url", "http://127.0.0.1:9", "--token-file", "t"]
    )
    assert default.request_timeout == 30


@pytest.mark.parametrize(
    "member,kind", [("../escape", "file"), ("data/link", "link"), ("data/hard", "hard")]
)
def test_archive_safety(tmp_path, member, kind):
    path = tmp_path / "bad.tar.gz"
    with tarfile.open(path, "w:gz") as tar:
        entry = tarfile.TarInfo(member)
        if kind in {"link", "hard"}:
            entry.type = tarfile.SYMTYPE if kind == "link" else tarfile.LNKTYPE
            entry.linkname = "outside"
        tar.addfile(entry, io.BytesIO(b""))
    store = ObjectStore(tmp_path / "store", max_object_mb=1, max_store_mb=8, min_free_mb=1)
    ident = sha(path)
    store.begin(ident, path.stat().st_size)
    store.append(ident, 0, path.read_bytes())
    with pytest.raises(ValueError, match="unsafe"):
        store.commit(ident)
    assert not store.directory(ident).exists()
    assert not (tmp_path / "escape").exists()


@pytest.mark.skipif(os.name == "nt", reason="symlink creation requires developer privileges")
def test_snapshot_links_explicit_only_and_no_directory_escape(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "real.py").write_text("x=1\n")
    (source / "alias.py").symlink_to("real.py")
    with pytest.raises(ValueError, match="explicitly"):
        snapshot(source, tmp_path / "rejected")
    record = snapshot(source, tmp_path / "copied", resolve_code_links=True)
    assert record["materialized_code_aliases"] == {"alias.py": "real.py"}
    assert not (tmp_path / "copied/alias.py").is_symlink()
    (source / "outside").symlink_to(tmp_path / "copied", target_is_directory=True)
    with pytest.raises(ValueError, match="directory symlinks"):
        snapshot(source, tmp_path / "escaped", include=["outside/real.py"])


def test_static_plan_does_not_import_code_or_acquire_data(tmp_path):
    code, data = fixture(tmp_path)
    (code / "job.py").write_text("raise RuntimeError('planning must never execute this')\n")
    raw = workflow(
        code, data, {"dataset_id": "unavailable", "version": "v1", "object_sha256": "a" * 64}
    )
    receipt = plan(raw, tmp_path / "plan")
    assert receipt["plugin_code_executed"] is False and receipt["data_acquired"] is False
    assert receipt["scientific_preflight"] == "NOT_RUN"


def test_single_file_snapshot_inside_common_parent_is_supported(tmp_path):
    source = tmp_path / "one.py"
    source.write_text("x=1\n")
    snapshot(source, tmp_path / "capsule")
    assert (tmp_path / "capsule/one.py").read_bytes() == source.read_bytes()


def test_shipped_example_executes_with_verified_return(api, worker, tmp_path):
    from research_workflows.planner import from_file

    request = Path(__file__).resolve().parents[1] / "research_workflows/examples/request.json"
    from_file(request, tmp_path / "planned")
    accepted = api.submit_plan(tmp_path / "planned")
    assert drive(worker, accepted["workflow_id"])["state"] == "completed"
    api.collect(accepted["workflow_id"], tmp_path / "returned")
    assert load(resolve(tmp_path / "returned", "report.reports", "RESULT.json"))["sum"] == 10


def test_testing_adapter_owns_controls_and_checkpoint_must_advance():
    raw = basic()
    first = raw["jobs"][0]
    first.update(kind="testing_stage", testing={"through": "metrics", "stop_after": "models"})
    first.pop("entrypoint")
    first.pop("outputs")
    second = deepcopy(first)
    second.update(
        id="two",
        depends_on=["one"],
        testing={"through": "metrics", "stop_after": "metrics", "resume_input": "checkpoint"},
        inputs={"checkpoint": {"mode": "artifact_ref", "job": "one", "output": "checkpoint"}},
    )
    raw["jobs"].append(second)
    normalized = validate(raw)
    assert validate(normalized) == normalized
    for flag in ("--output", "--workflow=deployment", "--data-refresh", "--cache-mode"):
        invalid = deepcopy(raw)
        invalid["jobs"][0]["args"] = [flag]
        with pytest.raises(ValueError, match="owned"):
            validate(invalid)
    invalid = deepcopy(raw)
    invalid["jobs"][1]["testing"]["stop_after"] = "models"
    with pytest.raises(ValueError, match="advance"):
        validate(invalid)


def test_checkpoint_encoding_is_json_only(tmp_path):
    import argparse
    import importlib.util

    script = Path(__file__).resolve().parents[1] / "research_workflows/execution/stage_runner.py"
    spec = importlib.util.spec_from_file_location("offload_checkpoint_fixture", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    value = {
        "args": argparse.Namespace(output=Path("/work/artifacts/testing")),
        "receipts": [1, True, None],
    }
    decoded = module.decode(module.encode(value))
    assert vars(decoded["args"]) == vars(value["args"])
    with pytest.raises(ValueError, match="unsupported"):
        module.encode(object())
    with pytest.raises(ValueError, match="unsupported"):
        module.decode(["pickle", "not-executable"])
    invalid = tmp_path / "invalid.json"
    invalid.write_text('{"x":1,"x":2}')
    with pytest.raises(ValueError, match="duplicate"):
        module.read(invalid)


def test_http_resume_auth_limits_and_no_template_bypass(api, worker, tmp_path):
    _, data = fixture(tmp_path)
    path = tmp_path / "input.tar.gz"
    pack(data, path)
    ident, payload = sha(path), path.read_bytes()
    prefix = "/v2/objects/" + ident
    api.request(prefix + "/begin", {"bytes": len(payload)})
    api.request(prefix + "/chunks/0", data=payload[:25], method="PUT")
    assert api.upload(path) == ident
    returned = tmp_path / "downloads"
    returned.mkdir()
    (returned / (ident + ".part")).write_bytes(payload[:25])
    target = api.download_object(ident, returned)
    verify_object(target, ident)
    assert not (returned / (ident + ".part")).exists()
    for path, body in [
        ("/v1/jobs", {"template": "workflow-python", "job_id": "bypass"}),
        (prefix + "/begin", {"bytes": 999999999999}),
    ]:
        with pytest.raises(HTTPError) as error:
            api.request(path, body)
        assert error.value.code == 400
    with pytest.raises(HTTPError) as error:
        Client(api.url, "wrong" * 9).request("/v2/capabilities")
    assert error.value.code == 401
    with pytest.raises(HTTPError) as error:
        api.open(prefix + "/archive", headers={"Range": "bytes=999999999-"})
    assert error.value.code == 416
    assert api.request("/v1/templates")["templates"] == []


def test_opt_in_disabled_on_original_worker(tmp_path):
    with Worker(tmp_path / "legacy", [], backend="trusted-local", min_free_mb=0) as worker:
        assert not hasattr(worker, "workflows")


def test_full_dag_simulation_cleans_its_state():
    result = run()
    assert result["status"] == "PASS" and result["nodes_completed"] == 4
    assert result["temporary_state_removed"] and result["worker_and_http_threads_stopped"]
    assert not result["os_isolation_tested"]


def test_collection_tampering_and_budget_never_acknowledge(api, worker, tmp_path):
    spec, _ = compiled(tmp_path, worker)
    worker.workflows.submit(spec)
    assert drive(worker)["state"] == "completed"
    with pytest.raises(ValueError, match="budget"):
        api.collect(spec["submission_id"], tmp_path / "small", max_bytes=1)
    with worker.db_lock:
        assert (
            worker.db.execute(
                "SELECT COUNT(*) FROM workflow_deliveries WHERE acknowledged IS NOT NULL"
            ).fetchone()[0]
            == 0
        )
    destination = tmp_path / "returned"
    receipt = api.collect(spec["submission_id"], destination)
    assert receipt["automatic_delete"] is False
    index = load(destination / "INDEX.json")
    (destination / index["report.evidence"] / "metrics.csv").write_text("tampered\n")
    with pytest.raises(ValueError, match="manifest"):
        verify_collection(destination)
    with pytest.raises(ValueError, match="manifest"):
        api.collect(spec["submission_id"], destination)
    with pytest.raises(Conflict):
        worker.workflows.acknowledge(spec["submission_id"], "a" * 64)


def test_partial_output_and_independent_failure_branches(worker, tmp_path):
    def edit(raw):
        raw["jobs"][0]["outputs"]["missing"] = {"path": "artifacts/absent.csv", "type": "csv"}
        report = raw["jobs"][-1]
        report.update(
            kind="report",
            condition="all_terminal",
            inputs={"left": {"mode": "bundle", "source": str(tmp_path / "data")}},
        )
        report["args"] = [
            "report",
            "{input.left}/values.json",
            "{input.left}/values.json",
            "{output.evidence}",
        ]

    spec, _ = compiled(tmp_path, worker, edit=edit)
    worker.workflows.submit(spec)
    status = drive(worker)
    nodes = {n["id"]: n for n in status["nodes"]}
    assert {k: n["state"] for k, n in nodes.items()} == {
        "bundle": "failed",
        "generated": "blocked_dependency",
        "remote": "succeeded",
        "report": "succeeded",
    }
    assert nodes["bundle"]["outputs"]["ports"]["values"]["status"] == "VERIFIED"
    assert nodes["bundle"]["outputs"]["ports"]["missing"]["status"] == "OUTPUT_INVALID"
    assert nodes["bundle"]["outputs"]["diagnostics_object"]
    assert worker.workflows.resume(spec["submission_id"])[
        "terminal"
    ]  # no retry of semantic failure


def test_restart_and_explicit_interrupted_retry_keep_previous_attempt(tmp_path):
    config = configuration()
    root = tmp_path / "worker"
    with WorkflowWorker(
        root, [], backend="trusted-local", workflow_config=config, min_free_mb=0
    ) as one:
        spec, _ = compiled(tmp_path, one, edit=lambda raw: raw["jobs"][0].update(max_attempts=2))
        one.workflows.submit(spec)
        one.workflows.tick()
        job, _, _ = one._claim()  # simulate loss after durable claim, before any process exists
    with WorkflowWorker(
        root, [], backend="trusted-local", workflow_config=config, min_free_mb=0
    ) as two:
        assert two.status(job)["state"] == "interrupted"
        assert drive(two)["state"] == "completed_with_errors"
        two.workflows.resume(spec["submission_id"])
        assert drive(two)["state"] == "completed"
        assert two.status(job)["state"] == "interrupted"
        with two.db_lock:
            attempts = two.db.execute(
                "SELECT state FROM workflow_attempts WHERE node='bundle' ORDER BY attempt"
            ).fetchall()
        assert [a[0] for a in attempts] == ["interrupted", "succeeded"]


def test_storage_claim_retains_future_growth_until_running_job_finishes(tmp_path):
    """An empty workspace has not consumed the running job's output allowance."""
    config = configuration()
    with WorkflowWorker(
        tmp_path / "worker", [], backend="trusted-local", workflow_config=config,
        concurrency=2, min_free_mb=100,
    ) as worker:
        running = {"inputs": [{"size_bytes": 0}], "template": {"max_work_mb": 200}}
        queued = {"inputs": [{"size_bytes": 0}], "template": {"max_work_mb": 50}}
        attempt = "offload-running-models"
        (worker.root / "work" / attempt).mkdir(parents=True)
        with worker.transaction() as db:
            db.execute(
                "INSERT INTO jobs(id,request,state,created,updated,attempt,cancel,payload) "
                "VALUES (?,?,?,0,0,?,0,?)",
                ("running-models", "{}", "running", attempt, json.dumps(running)),
            )
            db.execute(
                "INSERT INTO jobs(id,request,state,created,updated,attempt,cancel,payload) "
                "VALUES (?,?,?,1,1,NULL,0,?)",
                ("queued-probe", "{}", "queued", json.dumps(queued)),
            )
            # The running job may still write 200 MiB. Its directory existing
            # does not justify dropping that future growth from admission.
            assert worker._storage_claim_allowed(db, queued, 180 << 20) is False
            assert worker._storage_claim_allowed(db, queued, 149 << 20) is False
            assert worker._storage_claim_allowed(db, queued, (350 << 20) - 1) is False
            assert worker._storage_claim_allowed(db, queued, 350 << 20) is True
            db.execute("UPDATE jobs SET state='succeeded' WHERE id='running-models'")
            assert worker._storage_claim_allowed(db, queued, 150 << 20) is True


def test_dispatch_crash_window_and_atomic_resource_admission(worker, tmp_path, monkeypatch):
    spec, _ = compiled(tmp_path, worker)
    worker.workflows.submit(spec)
    submit = worker.submit
    monkeypatch.setattr(
        worker, "submit", lambda *a, **k: (_ for _ in ()).throw(CapacityError("queue busy"))
    )
    worker.workflows.tick()
    assert not worker.db.execute("SELECT * FROM jobs").fetchall()
    monkeypatch.setattr(worker, "submit", submit)
    worker.workflows.tick()
    worker.capacity["cpus"] = 1
    with ThreadPoolExecutor(max_workers=4) as pool:
        claims = list(pool.map(lambda _: worker._claim(), range(4)))
    assert len([c for c in claims if c]) == 1
    assert worker.db.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 2


def test_cancel_and_poll_timeout_are_distinct(api, worker, tmp_path):
    spec, _ = compiled(tmp_path, worker)
    worker.workflows.submit(spec)
    with pytest.raises(TimeoutError, match="not cancelled"):
        api.wait_workflow(spec["submission_id"], deadline=0.01, interval=0.01)
    assert not worker.workflows.status(spec["submission_id"])["terminal"]
    api.request("/v2/workflows/" + spec["submission_id"] + "/cancel", {})
    assert {n["state"] for n in api.workflow_status(spec["submission_id"])["nodes"]} == {
        "cancelled"
    }
    with pytest.raises(Conflict):
        worker.workflows.resume(spec["submission_id"])


def test_output_types_and_retained_negative_evidence(tmp_path):
    root = tmp_path / "artifacts"
    root.mkdir()
    (root / "valid.csv").write_text("label,value\nsynthetic,1\n")
    (root / "bad.json").write_text('{"schema":"wrong"}')
    outputs = {
        "good": {"path": "artifacts/valid.csv", "type": "csv", "required": True, "rows": 1},
        "bad": {
            "path": "artifacts/bad.json",
            "type": "json",
            "schema": "expected",
            "required": True,
        },
    }
    ports = validate_ports(tmp_path, {"outputs": outputs}, max_bytes=10000)
    assert ports["good"]["status"] == "VERIFIED" and ports["bad"]["status"] == "OUTPUT_INVALID"


def test_partial_collection_and_required_local_exports(api, worker, tmp_path):
    def edit(raw):
        raw["return_policy"] = {
            "profile": "selected",
            "ports": ["report.evidence"],
            "include_inputs": True,
            "require_local": ["report.evidence"],
        }

    spec, _ = compiled(tmp_path, worker, edit=edit)
    worker.workflows.submit(spec)
    partial = api.collect(spec["submission_id"], tmp_path / "partial", partial=True)
    assert partial["final"] is False and partial["required_local_missing"] == ["report.evidence"]
    with pytest.raises(ValueError, match="partial snapshot"):
        api.collect(spec["submission_id"], tmp_path / "partial")
    with pytest.raises(ValueError, match="BLOCKED_DATA"):
        resolve(tmp_path / "partial", "report.evidence")
    assert drive(worker)["state"] == "completed"
    final = api.collect(spec["submission_id"], tmp_path / "final")
    assert final["final"] and final["required_inputs_available_locally"]
    assert final["required_local_missing"] == []
    assert resolve(tmp_path / "final", "report.evidence", "ledger.bin").read_bytes() == bytes(
        [2, 3, 5]
    )
    with pytest.raises(ValueError, match="unsafe"):
        resolve(tmp_path / "final", "report.evidence", "../outside")
    bad = deepcopy(spec)
    bad["return_policy"] = {"profile": "summary_and_refs", "require_local": ["report.evidence"]}
    with pytest.raises(ValueError, match="local continuation"):
        validate(bad)


def test_object_hash_mismatch_and_archive_bomb(tmp_path):
    store = ObjectStore(tmp_path / "store", max_object_mb=1, max_store_mb=8, min_free_mb=1)
    store.begin("a" * 64, 4)
    store.append("a" * 64, 0, b"bad!")
    with pytest.raises(ValueError, match="corrupt"):
        store.commit("a" * 64)
    path = tmp_path / "oversized.tar.gz"
    with tarfile.open(path, "w:gz") as tar:
        entry = tarfile.TarInfo("data/oversized")
        entry.size = 2 << 20
        tar.addfile(entry, io.BytesIO(b"0" * entry.size))
    ident = sha(path)
    store.begin(ident, path.stat().st_size)
    store.append(ident, 0, path.read_bytes())
    with pytest.raises(ValueError, match="extraction limits"):
        store.commit(ident)


@pytest.mark.skipif(os.environ.get("OFFLOAD_TEST_DOCKER") != "1", reason="opt-in Docker test")
def test_docker_dag():
    result = run(docker=True)
    assert result["status"] == "PASS" and result["os_isolation_tested"]
    assert result["temporary_state_removed"] and result["worker_and_http_threads_stopped"]


def test_workflow_and_large_resumable_object_through_authenticated_gateway(worker, tmp_path):
    import asyncio
    import random

    pytest.importorskip("aiohttp")
    from aiohttp import web

    from external_machine_connect.cloudflare.connect import create_app

    async def exercise():
        server = Server(("127.0.0.1", 0), worker, TOKEN)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        app = create_app(
            f"http://127.0.0.1:{server.server_port}", TOKEN, auth_header="X-Offload-Token"
        )
        runner = web.AppRunner(app, access_log=None)
        try:
            await runner.setup()
            site = web.TCPSite(runner, "127.0.0.1", 0)
            await site.start()
            client = Client(f"http://127.0.0.1:{runner.addresses[0][1]}", TOKEN)
            data = tmp_path / "large-object"
            data.mkdir()
            (data / "data.bin").write_bytes(random.Random(902).randbytes((4 << 20) + 1024))
            archive = tmp_path / "large.tar.gz"
            pack(data, archive)
            assert archive.stat().st_size > 4 << 20
            ident = await asyncio.to_thread(client.upload, archive)
            downloads = tmp_path / "downloads"
            downloads.mkdir()
            (downloads / (ident + ".part")).write_bytes(archive.read_bytes()[:123])
            target = await asyncio.to_thread(client.download_object, ident, downloads)
            assert (target / "data/data.bin").read_bytes() == (data / "data.bin").read_bytes()
            _, directory = compiled(tmp_path, worker)
            status = await asyncio.to_thread(client.submit_plan, directory)
            worker.start()
            finished = await asyncio.to_thread(
                client.wait_workflow, status["workflow_id"], deadline=30
            )
            assert finished["state"] == "completed"
            receipt = await asyncio.to_thread(
                client.collect, status["workflow_id"], tmp_path / "returned"
            )
            assert receipt["final"]
        finally:
            await runner.cleanup()
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    asyncio.run(exercise())


@pytest.mark.skipif(
    not os.environ.get("OFFLOAD_RESEARCH_TEST_IMAGE"), reason="needs prebuilt research test image"
)
@pytest.mark.parametrize(
    "mode,through,adverse",
    [
        ("bundle", "metrics", False),
        ("dataset_ref", "statistics", False),
        ("artifact_ref", "statistics", True),
    ],
)
@pytest.mark.parametrize("input_transport", ["bind", "docker-volume"])
def test_native_whole_capsule_and_portable_stage_checkpoint_parity(
    tmp_path, mode, through, adverse, input_transport
):
    repo = Path(__file__).resolve().parents[3]
    if not (repo / "research/testing_stages/testing.py").is_file():
        pytest.skip("native research source is not in this checkout")
    capsule = tmp_path / "capsule"
    capsule.mkdir()
    snapshot(repo, capsule / "repo", include=research_selection(repo), resolve_code_links=True)
    data = tmp_path / "input"
    data.mkdir()
    for key, prediction in (
        ("candidate", "no" if adverse else "yes"),
        ("benchmark", "yes" if adverse else "no"),
    ):
        (data / (key + ".py")).write_text(
            "TESTING_MODEL={'api_version':1,'model_id':" + repr(key) + "}\n"
            "def predict(observation, context):\n    return " + repr(prediction) + "\n"
        )
    (data / "data.jsonl").write_text(
        "".join(
            json.dumps({"input": n, "target": "yes" if n % 10 else "no"}) + "\n" for n in range(100)
        )
    )
    args = [
        "--model",
        "{input.data}/candidate.py",
        "--benchmark",
        "{input.data}/benchmark.py",
        "--data",
        "{input.data}/data.jsonl",
        "--seeds",
        "0",
        "1",
        "--checks",
        "--no-early-stop",
    ]
    if through == "statistics":
        atomic(
            data / "criteria.json",
            {
                "schema": "marketmaker.generic_criteria.v1",
                "contract_id": "synthetic_only",
                "metrics": {
                    "accuracy": {
                        "rule": "ideal_gap",
                        "direction": "higher",
                        "ideal": 1,
                        "amount": "1/2",
                    }
                },
            },
        )
        atomic(
            data / "statistics.json",
            {
                "schema": "marketmaker.statistical_comparison_config.v1",
                "dependence": "independent_cases",
                "block_length": 1,
                "hac_lags": 0,
                "replications": 199,
                "seed": 94,
                "min_observations": 60,
            },
        )
        args += [
            "--criteria",
            "{input.data}/criteria.json",
            "--statistics-config",
            "{input.data}/statistics.json",
        ]
    node = {
        "id": "whole",
        "kind": "testing",
        "runtime": "python",
        "capsule": {"source": str(capsule)},
        "testing": {"through": through},
        "inputs": {"data": {"mode": "bundle", "source": str(data)}},
        "args": args,
    }
    first = deepcopy(node)
    first.update(
        id="first", kind="testing_stage", testing={"through": through, "stop_after": "models"}
    )
    second = deepcopy(node)
    second.update(
        id="second",
        kind="testing_stage",
        depends_on=["first"],
        testing={"through": through, "stop_after": through, "resume_input": "checkpoint"},
    )
    second["inputs"]["checkpoint"] = {
        "mode": "artifact_ref",
        "job": "first",
        "output": "checkpoint",
    }
    config = configuration(os.environ["OFFLOAD_RESEARCH_TEST_IMAGE"])
    config["input_transport"] = input_transport
    config["runtimes"]["python"].update(
        timeout_s=180, memory_mb=1024, max_work_mb=256, max_output_mb=64
    )
    config["capacity"].update(memory_mb=2048, max_work_mb=512)
    config.update(max_object_mb=64, max_store_mb=2048)
    destination = tmp_path / "compiled"
    jobs = [node, first, second]
    if mode == "artifact_ref":
        (capsule / "prepare.py").write_text(
            "import shutil,sys\nshutil.copytree(sys.argv[1],sys.argv[2])\n"
        )
        producer = {
            "id": "prepare",
            "kind": "producer",
            "runtime": "python",
            "capsule": {"source": str(capsule)},
            "entrypoint": "prepare.py",
            "args": ["{input.original}", "{output.prepared}"],
            "inputs": {"original": {"mode": "bundle", "source": str(data)}},
            "outputs": {
                "prepared": {"path": "artifacts/prepared", "type": "tree", "delivery": "remote"}
            },
        }
        for job in jobs:
            job["inputs"]["data"] = {"mode": "artifact_ref", "job": "prepare", "output": "prepared"}
            job.setdefault("depends_on", []).append("prepare")
        jobs.insert(0, producer)
    with WorkflowWorker(
        tmp_path / "worker", [], backend="docker", workflow_config=config, min_free_mb=0
    ) as worker:
        if mode == "dataset_ref":
            remote = worker.workflows.objects.register_dataset("synthetic-research", "v1", data)
            for job in jobs:
                job["inputs"]["data"] = {"mode": "dataset_ref", **remote}
        plan(
            {
                "schema": SCHEMA,
                "submission_id": "native-parity",
                "jobs": jobs,
                "return_policy": {"include_inputs": True},
            },
            destination,
        )
        for archive in (destination / "objects").glob("*.tar.gz"):
            store = worker.workflows.objects
            ident = sha(archive)
            store.begin(ident, archive.stat().st_size)
            payload = archive.read_bytes()
            from research_workflows.objects import CHUNK

            for offset in range(0, len(payload), CHUNK):
                store.append(ident, offset, payload[offset : offset + CHUNK])
            store.commit(ident)
        worker.workflows.submit(load(destination / "WORKFLOW.json"))
        status = drive(worker, "native-parity")
        nodes = {n["id"]: n for n in status["nodes"]}
        diagnostics = []
        for entry in nodes.values():
            manifest = entry["outputs"] or {}
            ident = manifest.get("diagnostics_object")
            if ident:
                log = store.get(ident)[0] / "data/run.log"
                if log.exists():
                    diagnostics.append(log.read_text()[-12000:])
        assert status["state"] == "completed", json.dumps(status) + "\n" + "\n".join(diagnostics)

        def evidence(key):
            return (
                store.get(nodes[key]["outputs"]["ports"]["research_evidence"]["object_sha256"])[0]
                / "data"
            )

        whole, split, start = evidence("whole"), evidence("second"), evidence("first")
        assert load(start / "RESULT.json")["status"] == "CHECKPOINTED"
        for folder in ("stage_00_contracts", "stage_01_data", "stage_02_models"):
            assert (start / folder / "GATE.json").read_bytes() == (
                split / folder / "GATE.json"
            ).read_bytes()

        def metrics(root):
            native = load(root / "stage_04_replay/evaluation/RESULT.json")
            return {
                k: {"evaluation": v["evaluation"], "reproduction": v["reproduction"]["status"]}
                for k, v in native["models"].items()
            }

        assert metrics(whole) == metrics(split)
        assert len(metrics(whole)) == 4
        assert load(split / "RESULT.json")["status"] == "REQUESTED_GATES_PASSED"
        assert (split / "METRICS_COMPARISON.csv").is_file()
        assert list(split.rglob("observations_*.jsonl"))
        if through == "statistics":
            assert load(split / "RESULT.json")["statistical_verdict"] == (
                "FAILED" if adverse else "SUPPORTED"
            )
            assert (
                load(whole / "RESULT.json")["statistical_verdict"]
                == load(split / "RESULT.json")["statistical_verdict"]
            )
            assert (split / "comparison.csv").is_file()
        server = Server(("127.0.0.1", 0), worker, TOKEN)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            client = Client(f"http://127.0.0.1:{server.server_port}", TOKEN)
            returned = tmp_path / "returned"
            receipt = client.collect("native-parity", returned)
            assert receipt["required_inputs_available_locally"]
            assert resolve(
                returned,
                "second.research_evidence",
                native_path="/work/artifacts/testing/RESULT.json",
            ).is_file()
            # New worker consumes a returned checkpoint, code and data. No path
            # back into the original worker's store is supplied to it.
            continuation = deepcopy(load(destination / "WORKFLOW.json")["jobs"][-1])
            continuation.update(
                id="continued",
                depends_on=[],
                capsule={"source": str(resolve(returned, "second.__capsule__"))},
            )
            continuation["inputs"] = {
                "data": {
                    "mode": "bundle",
                    "source": str(resolve(returned, "second.__input_data__")),
                },
                "checkpoint": {
                    "mode": "bundle",
                    "source": str(resolve(returned, "first.checkpoint")),
                },
            }
            followup = tmp_path / "followup"
            plan(
                {
                    "schema": SCHEMA,
                    "submission_id": "returned-continuation",
                    "jobs": [continuation],
                },
                followup,
            )
            with WorkflowWorker(
                tmp_path / "fresh-worker",
                [],
                backend="docker",
                workflow_config=config,
                min_free_mb=0,
            ) as fresh:
                for path in (followup / "objects").glob("*.tar.gz"):
                    obj = sha(path)
                    fresh.workflows.objects.begin(obj, path.stat().st_size)
                    raw = path.read_bytes()
                    for offset in range(0, len(raw), CHUNK):
                        fresh.workflows.objects.append(obj, offset, raw[offset : offset + CHUNK])
                    fresh.workflows.objects.commit(obj)
                fresh.workflows.submit(load(followup / "WORKFLOW.json"))
                resumed = drive(fresh, "returned-continuation")
                assert resumed["state"] == "completed", resumed
                output_id = resumed["nodes"][0]["outputs"]["ports"]["research_evidence"][
                    "object_sha256"
                ]
                resumed_tree = fresh.workflows.objects.get(output_id)[0] / "data"
                assert metrics(resumed_tree) == metrics(whole)
                assert (resumed_tree / "stage_02_models/GATE.json").read_bytes() == (
                    start / "stage_02_models/GATE.json"
                ).read_bytes()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


@pytest.mark.skipif(
    os.environ.get("OFFLOAD_TEST_DOCKER") != "1", reason="opt-in Docker safety test"
)
def test_docker_denies_undeclared_access_and_enforces_limits(tmp_path):
    import subprocess

    code = tmp_path / "code"
    code.mkdir()
    data = tmp_path / "input"
    data.mkdir()
    (data / "immutable.txt").write_text("synthetic immutable data")
    marker = tmp_path / "host-secret-marker"
    marker.write_text("synthetic marker, not credentials")
    program = """import json,os,pathlib,socket,subprocess,sys,time
mode=sys.argv[1]
if mode=='timeout': time.sleep(30)
if mode=='memory':
    blocks=[]
    while True: blocks.append(bytearray(4*1024*1024))
if mode=='output': pathlib.Path(sys.argv[2]).write_bytes(b'0'*(4*1024*1024))
if mode=='boundary':
    for forbidden in (sys.argv[3], '/var/run/docker.sock', '/root/.ssh/id_rsa', '/work/blobs/inputs/undeclared'):
        try: pathlib.Path(forbidden).read_bytes()
        except OSError: pass
        else: raise RuntimeError('unexpected host/credential access')
    try: pathlib.Path(sys.argv[4]).write_text('mutation')
    except OSError: pass
    else: raise RuntimeError('immutable input was writable')
    try:
        with socket.create_connection(('1.1.1.1',443),timeout=.2): pass
    except OSError: pass
    else: raise RuntimeError('unexpected network access')
    children=[]
    try:
        for _ in range(64): children.append(subprocess.Popen([sys.executable,'-c','import time; time.sleep(5)']))
    except OSError: limited=True
    else: limited=False
    finally:
        for child in children: child.terminate()
        for child in children: child.wait()
    assert limited, 'PID limit did not constrain children'
    pathlib.Path(sys.argv[2]).write_text(json.dumps({'schema':'synthetic.boundary.v1','verified':True}))
"""
    (code / "main.py").write_text(program)
    jobs = []
    for mode in ("boundary", "timeout", "memory", "output"):
        limits = {"pids": 16}
        if mode == "timeout":
            limits["timeout_s"] = 1
        if mode == "memory":
            limits["memory_mb"] = 128
        if mode == "output":
            limits.update(max_work_mb=1, max_output_mb=1)
        jobs.append(
            {
                "id": mode,
                "kind": "producer",
                "runtime": "python",
                "capsule": {"source": str(code)},
                "entrypoint": "main.py",
                "inputs": {"data": {"mode": "bundle", "source": str(data)}},
                "args": [mode, "{output.result}", str(marker), "{input.data}/immutable.txt"],
                "resources": limits,
                "outputs": {
                    "result": {
                        "path": "artifacts/result.json",
                        "type": "json",
                        "schema": "synthetic.boundary.v1",
                    }
                },
            }
        )
    planned = tmp_path / "plan"
    plan({"schema": SCHEMA, "submission_id": "limits", "jobs": jobs}, planned)
    with WorkflowWorker(
        tmp_path / "worker", [], backend="docker", workflow_config=configuration(), min_free_mb=0
    ) as worker:
        for path in (planned / "objects").glob("*.tar.gz"):
            ident = sha(path)
            store = worker.workflows.objects
            store.begin(ident, path.stat().st_size)
            store.append(ident, 0, path.read_bytes())
            store.commit(ident)
        worker.workflows.submit(load(planned / "WORKFLOW.json"))
        status = drive(worker, "limits")
        assert {n["id"]: n["state"] for n in status["nodes"]} == {
            "boundary": "succeeded",
            "timeout": "failed",
            "memory": "failed",
            "output": "failed",
        }, status
        for node in status["nodes"]:
            execution = node["outputs"]["execution"]
            attempt = execution["receipt"]["attempt"]
            assert (
                subprocess.run(
                    ["docker", "container", "inspect", attempt], capture_output=True
                ).returncode
                != 0
            )
    assert marker.read_text() == "synthetic marker, not credentials"
    assert (data / "immutable.txt").read_text() == "synthetic immutable data"
