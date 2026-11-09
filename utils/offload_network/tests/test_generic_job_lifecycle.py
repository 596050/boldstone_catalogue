"""Generic lifecycle contracts, using synthetic files and an offline pure wheel."""

import json
import os
import subprocess
import sys
import zipfile
from copy import deepcopy
from pathlib import Path

import pytest

from research_workflows import input_bundle, python_runtime
from research_workflows.cli import main, parser
from research_workflows.common import atomic, capture_file, inventory, load, sha
from research_workflows.execution.portable import materialize, replace_paths
from research_workflows.input_budget import preflight
from research_workflows.planner import plan
from research_workflows.project_queue import ProjectQueue
from research_workflows.spec import identity, validate
from tests.test_project_return import freeze, project
from tests.test_python_environment import current_target, write_bundle
from tests.test_research_workflows import api, basic, compiled, drive, worker


def wheel_request(directory, *, target=None, payload="VALUE = 7\n"):
    directory.mkdir(parents=True, exist_ok=True)
    wheel = directory / "demo_pkg-1.2.3-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("demo_pkg/__init__.py", payload)
        archive.writestr("demo_pkg-1.2.3.dist-info/METADATA",
                         "Metadata-Version: 2.1\nName: demo-pkg\nVersion: 1.2.3\n")
        archive.writestr("demo_pkg-1.2.3.dist-info/WHEEL",
                         "Wheel-Version: 1.0\nGenerator: synthetic-test\nRoot-Is-Purelib: true\nTag: py3-none-any\n")
        archive.writestr("demo_pkg-1.2.3.dist-info/RECORD", "")
    return {"schema": python_runtime.REQUEST_SCHEMA, "target": target or current_target(),
            "requirements": {"demo-pkg": "1.2.3"}, "imports": ["demo_pkg"],
            "wheels": [{"path": str(wheel), "sha256": sha(wheel)}],
            "max_bytes": 8 << 20, "min_free_bytes": 0}


def input_request(directory):
    directory.mkdir(parents=True, exist_ok=True)
    payload = directory / "observations.bin"
    payload.write_bytes(b"\x00\x01\xffdo not transform\n")
    document = directory / "original.json"
    atomic(document, {"path": "/old/raw", "rows": [1.25, None, -4, 0],
                      "clock": "2020-01-02T03:04:05Z", "identity": {"/old/raw": sha(payload)}})
    return {"schema": input_bundle.REQUEST_SCHEMA,
            "files": {"raw/observations.bin": {"path": str(payload), "sha256": sha(payload)},
                      "original.json": {"path": str(document), "sha256": sha(document)}},
            "documents": {"INPUTS.json": {"source": "original.json", "paths": {"/old/raw": "raw/observations.bin"}}},
            "max_bytes": 1 << 20, "min_free_bytes": 0}


def test_offline_runtime_builder_and_cli(tmp_path):
    request = wheel_request(tmp_path / "wheel")
    source = tmp_path / "runtime-request.json"
    atomic(source, request)
    destination = tmp_path / "runtime"
    assert main(["prepare-runtime", "--request", str(source), "--out", str(destination)]) == 0
    record = load(destination / "PYTHON_RUNTIME.json")
    assert record["status"] == "PREPARED_NOT_WORKER_VALIDATED"
    assert not record["global_packages_changed"] and not record["worker_configuration_changed"]
    assert inventory(destination / "site-packages") == record["files"]
    helper = Path(python_runtime.__file__).parent / "execution/environment.py"
    output = tmp_path / "checked.json"
    result = subprocess.run([sys.executable, "-I", "-B", str(helper), str(destination), str(output)],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert load(output)["requirements"] == {"demo-pkg": "1.2.3"}
    with pytest.raises(FileExistsError):
        python_runtime.prepare(request, destination)


def test_runtime_rejects_tamper_expansion_and_incompatible_target_before_payload(tmp_path):
    request = wheel_request(tmp_path / "wheel", payload="VALUE = '" + "x" * (2 << 20) + "'\n")
    request["max_bytes"] = 1 << 20
    with pytest.raises(ValueError, match="expansion"):
        python_runtime.prepare(request, tmp_path / "too-big")
    assert not (tmp_path / "too-big").exists()
    request["wheels"][0]["sha256"] = "a" * 64
    with pytest.raises(ValueError, match="declared bytes"):
        python_runtime.prepare(request, tmp_path / "bad-hash")
    from research_workflows.execution.environment import verify
    target = current_target()
    target["machine"] = "different_cpu"
    root = write_bundle(tmp_path / "foreign", target=target)
    with pytest.raises(ValueError, match="interpreter/platform"):
        verify(root)
    target["machine"] = current_target()["machine"]
    target["abi"] = "cp999"
    atomic(root / "PYTHON_RUNTIME.json", {**load(root / "PYTHON_RUNTIME.json"), "target": target})
    with pytest.raises(ValueError, match="interpreter/platform"):
        verify(root)


def test_capture_is_bounded_and_never_overwrites(tmp_path):
    source = tmp_path / "source"
    source.write_bytes(b"unchanged")
    with pytest.raises(ValueError, match="bounded"):
        capture_file(source, tmp_path / "out", expected_sha256=sha(source), max_bytes=2)
    capture_file(source, tmp_path / "out", expected_sha256=sha(source), max_bytes=9)
    with pytest.raises(FileExistsError):
        capture_file(source, tmp_path / "out", expected_sha256=sha(source), max_bytes=9)
    assert source.read_bytes() == (tmp_path / "out").read_bytes()


def test_portable_input_preserves_raw_values_clocks_and_hashes(tmp_path):
    request = input_request(tmp_path / "source")
    source_inventory = inventory(tmp_path / "source")
    bundle = tmp_path / "bundle"
    input_bundle.prepare(request, bundle)
    before = inventory(bundle)
    output = materialize(bundle, tmp_path / "relocated")
    original, moved = load(bundle / "files/original.json"), load(output / "INPUTS.json")
    path = str(bundle / "files/raw/observations.bin")
    assert moved == {**original, "path": path, "identity": {path: sha(Path(path))}}
    assert load(output / "RELOCATION.json")["payload_bytes_modified"] is False
    assert inventory(bundle) == before and inventory(tmp_path / "source") == source_inventory
    with pytest.raises(FileExistsError):
        materialize(bundle, output)
    (bundle / "files/raw/observations.bin").write_bytes(b"changed")
    with pytest.raises(ValueError, match="bytes differ"):
        materialize(bundle, tmp_path / "tampered")
    assert not (tmp_path / "tampered").exists()


@pytest.mark.parametrize("collision", ["RELOCATION.json", "relocation.JSON", "INPUTS.json/child", "../escape"])
def test_portable_input_rejects_ambiguous_outputs(tmp_path, collision):
    request = input_request(tmp_path / "source")
    request["documents"][collision] = deepcopy(request["documents"]["INPUTS.json"])
    with pytest.raises(ValueError):
        input_bundle.prepare(request, tmp_path / "bundle")
    assert not (tmp_path / "bundle").exists()


def test_path_replacement_rejects_missing_mappings_and_key_collision():
    with pytest.raises(ValueError, match="not found"):
        replace_paths({"path": "old"}, {"absent": "new"})
    with pytest.raises(ValueError, match="duplicate JSON"):
        replace_paths({"old": 1, "new": 2}, {"old": "new"})


def generic_request(tmp_path, *, target=None):
    runtime = tmp_path / "runtime"
    python_runtime.prepare(wheel_request(tmp_path / "wheels", target=target), runtime)
    data = tmp_path / "portable"
    input_bundle.prepare(input_request(tmp_path / "source"), data)
    code = tmp_path / "code"
    code.mkdir()
    (code / "main.py").write_text(
        "import json, pathlib, subprocess, sys\n"
        "import demo_pkg\n"
        "document = json.loads(pathlib.Path(sys.argv[1]).read_text())\n"
        "child = subprocess.check_output([sys.executable, '-B', '-c', 'import demo_pkg; print(demo_pkg.VALUE)'], text=True)\n"
        "result = {'value': demo_pkg.VALUE, 'child': int(child), 'rows': document['rows'],\n"
        "          'clock': document['clock'], 'payload_hex': pathlib.Path(document['path']).read_bytes().hex()}\n"
        "pathlib.Path(sys.argv[2]).write_text(json.dumps(result))\n")
    job = {"id": "generic", "kind": "producer", "runtime": "python", "capsule": {"source": str(code)},
           "entrypoint": "main.py", "args": ["{input.observations}/INPUTS.json", "{output.result}"],
           "inputs": {"libraries": {"mode": "bundle", "source": str(runtime), "include": ["PYTHON_RUNTIME.json", "site-packages"]},
                      "observations": {"mode": "bundle", "source": str(data), "include": ["PORTABLE_INPUT.json", "files"]}},
           "python_environment": {"input": "libraries"}, "portable_inputs": ["observations"],
           "outputs": {"result": {"type": "json", "path": "artifacts/result.json"}}}
    return {"schema": "marketmaker.research_offload_workflow.v1", "submission_id": "generic-lifecycle", "jobs": [job]}


def test_shared_runner_uses_runtime_and_portable_input_for_any_job(tmp_path, worker):
    request = generic_request(tmp_path)
    target = tmp_path / "plan"
    plan(request, target, max_object_mb=16)
    for path in (target / "objects").glob("*.tar.gz"):
        store = worker.workflows.objects
        ident = sha(path)
        store.begin(ident, path.stat().st_size)
        store.append(ident, 0, path.read_bytes())
        store.commit(ident)
    spec = load(target / "WORKFLOW.json")
    worker.workflows.submit(spec)
    status = drive(worker, "generic-lifecycle")
    assert status["state"] == "completed", status
    work = next((worker.root / "work").iterdir())
    result = load(work / "artifacts/result.json")
    assert result["value"] == result["child"] == 7
    assert result["rows"] == [1.25, None, -4, 0]
    assert load(work / "artifacts/runtime/VALIDATION.json")["status"] == "PASS"
    assert load(work / "artifacts/inputs/observations/RELOCATION.json")["payload_bytes_modified"] is False


def test_legacy_job_identity_and_automatic_budget_preflight(tmp_path, worker):
    before = validate(basic())
    assert "python_environment" not in before["jobs"][0] and "portable_inputs" not in before["jobs"][0]
    assert identity(validate(before)) == identity(before)
    spec, _ = compiled(tmp_path, worker)
    _, _, receipt = worker.workflows.preflight(spec)
    assert receipt["input_budget"]["jobs"]
    # Force a known lower bound above the operator cap before ANY producer runs.
    from dataclasses import replace
    padded = tmp_path / "large-input"
    padded.mkdir()
    (padded / "bytes").write_bytes(b"x" * (600 << 10))
    ref = {"mode": "bundle", "object_sha256": worker.workflows.objects.ingest(padded)}
    spec["jobs"][0]["inputs"].update(first=ref, second=ref)
    for key, profile in worker.profiles.items():
        worker.profiles[key] = replace(profile, max_input_mb=1)
    with pytest.raises(ValueError, match="before producer execution"):
        worker.workflows.submit(spec)
    assert worker.db.execute("SELECT COUNT(*) FROM workflows").fetchone()[0] == 0
    assert worker.db.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 0


def test_batches_inherit_generic_inputs_and_checkpoint_identity_binds_activation():
    from research_workflows.batch import expand
    from research_workflows.execution.stage_runner import scientific_identity
    from tests.test_research_run_batches import request
    raw = request()
    raw["defaults"].update(inputs={"runtime": {"mode": "bundle", "object_sha256": "b" * 64},
                                  "data": {"mode": "bundle", "object_sha256": "c" * 64}},
                           python_environment={"input": "runtime"}, portable_inputs=["data"])
    spec = validate(expand(raw))
    assert len(spec["jobs"]) == 4
    assert all(job["python_environment"] == {"input": "runtime"} and job["portable_inputs"] == ["data"]
               for job in spec["jobs"])
    checkpoint = {"capsule": "a" * 64, "image_id": "image", "inputs": {"runtime": "b" * 64, "data": "c" * 64},
                  "resources": {}, "runner_object": "d" * 64, "job": spec["jobs"][0]}
    bound = scientific_identity(checkpoint)
    del checkpoint["job"]["portable_inputs"]
    assert scientific_identity(checkpoint) != bound
    bound = scientific_identity(checkpoint)
    del checkpoint["job"]["python_environment"]
    assert scientific_identity(checkpoint) != bound


def test_dataset_budget_counts_each_alias_without_false_artifact_rejection():
    from tests.test_input_budget import workflow
    spec = workflow()
    spec["jobs"][1]["inputs"]["market"]["mode"] = "dataset_ref"
    rows = preflight(spec, {"code": 1, "source": 4 << 20},
                     {"python": {"max_input_mb": 10, "max_output_mb": 64}})["jobs"]
    assert rows[1]["known_logical_input_bytes"] == 1 + (8 << 20)
    assert rows[1]["status"] == "UNRESOLVED_ARTIFACT_UPPER_BOUND"


def test_enqueue_receipt_is_immutable_and_conflicts_fail_before_enqueue(tmp_path, worker, project):
    config, origins = project
    _, target = freeze(tmp_path, worker)
    output = tmp_path / "ENQUEUED.json"
    with ProjectQueue(config) as queue:
        output.write_text('{}')
        with pytest.raises(ValueError, match="without a matching"):
            queue.enqueue_receipt(target, "local", origins, output=output)
        assert queue.db.execute("SELECT COUNT(*) FROM requests").fetchone()[0] == 0
        output.rename(tmp_path / "unrelated.json")
        receipt = queue.enqueue_receipt(target, "local", origins, output=output, lock_timeout=.1)
        stamp = output.stat().st_mtime_ns
        assert receipt["queue_acknowledged"] and receipt["performance_qualification"] == "NOT_ESTABLISHED"
        assert receipt == queue.enqueue_receipt(target, "local", origins, output=output)
        assert output.stat().st_mtime_ns == stamp and "token" not in json.dumps(receipt)
        args = parser().parse_args(["enqueue", "--config", str(config), "--plan", str(target),
                                    "--worker", "local", "--origins", "origins.json", "--receipt", str(output)])
        assert args.receipt == output and args.lock_timeout == 0


def test_enqueue_retry_is_bounded_and_only_for_its_ownership_lock(tmp_path, worker, project, monkeypatch):
    config, origins = project
    _, target = freeze(tmp_path, worker)
    with ProjectQueue(config) as queue:
        original, attempts = queue.enqueue, []
        def busy(*args):
            attempts.append(1)
            if len(attempts) == 1:
                raise TimeoutError("lock held: " + str(queue.root / "queue.lock"))
            return original(*args)
        monkeypatch.setattr(queue, "enqueue", busy)
        assert queue.enqueue_receipt(target, "local", origins, lock_timeout=1)["queue_acknowledged"]
        assert len(attempts) == 2
        def other_lock(*args):
            raise TimeoutError("lock held: unrelated")
        monkeypatch.setattr(queue, "enqueue", other_lock)
        with pytest.raises(TimeoutError, match="unrelated"):
            queue.enqueue_receipt(target, "local", origins, lock_timeout=1)


@pytest.mark.skipif(not os.environ.get("OFFLOAD_GENERIC_DOCKER_IMAGE"), reason="opt-in real Docker generic lifecycle")
def test_generic_lifecycle_real_docker_and_recoverable_retention(tmp_path):
    from research_workflows.local import run
    from research_workflows.retention import retain, restore, SCHEMA
    image = os.environ["OFFLOAD_GENERIC_DOCKER_IMAGE"]
    inspected = json.loads(subprocess.check_output(["docker", "image", "inspect", image], text=True))[0]
    assert image.startswith("sha256:"), "pin an already available immutable image; do not pull"
    version = subprocess.check_output(["docker", "run", "--rm", "--network=none", "--memory=128m", "--cpus=1",
                                       image, "python", "-I", "-B", "-c",
                                       "import sys; print(str(sys.version_info.major)+'.'+str(sys.version_info.minor))"], text=True).strip()
    target = {"python": version, "implementation": "cp", "abi": "cp" + version.replace(".", ""),
              "platforms": ["any"], "system": "Linux", "machine": inspected["Architecture"]}
    request = generic_request(tmp_path, target=target)
    plan(request, tmp_path / "plan", max_object_mb=16)
    record = run(tmp_path / "plan", tmp_path / "local", image=image, deadline=120, concurrency=1,
                 disconnected_seconds=0, min_free_mb=4096, max_object_mb=16,
                 runtime_resources={"cpus": 1, "memory_mb": 512, "max_input_mb": 16,
                                    "max_work_mb": 32, "max_output_mb": 8, "timeout_s": 30})
    assert record["status"] == "COLLECTED_AND_VERIFIED" and record["worker_stopped"]
    work = next((tmp_path / "local/state/work").iterdir())
    files = inventory(work)
    assert load(work / "artifacts/result.json")["child"] == 7
    request = {"schema": SCHEMA, "local_run": str(tmp_path / "local/LOCAL_RUN.json"),
               "work_attempts": [work.name], "objects": [], "max_bytes": 16 << 20, "min_free_bytes": 4096 << 20}
    assert retain(request)["status"] == "INSPECTED_NOT_EXECUTED"
    completed = retain(request, tmp_path / "retained", execute=True)
    assert not work.exists() and completed["status"] == "COMPLETED"
    restored = restore(tmp_path / "retained", work.name, tmp_path / "restored", max_bytes=16 << 20)
    assert inventory(restored["directory"]) == files
    assert retain(request, tmp_path / "retained", execute=True) == completed
