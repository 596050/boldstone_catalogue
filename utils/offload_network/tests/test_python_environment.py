"""Drive shipped python_environment spec, isolated helper, and run.py wiring."""
from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest

from research_workflows import batch
from research_workflows.python_runtime import validate as validate_runtime_request
from research_workflows.spec import SCHEMA, validate

HERE = Path(__file__).resolve().parents[1]
HELPER = HERE / "research_workflows/execution/environment.py"


def workflow():
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
                "inputs": {"runtime": {"mode": "bundle", "object_sha256": "b" * 64}},
                "python_environment": {"input": "runtime"},
                "outputs": {"value": {"type": "json", "path": "artifacts/value.json"}},
            }
        ],
    }


def digest_tree(directory):
    observed = {}
    for path in sorted(directory.rglob("*")):
        if path.is_file():
            observed[path.relative_to(directory).as_posix()] = {
                "bytes": path.stat().st_size,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
    return observed


def current_target():
    implementation = platform.python_implementation()
    return {
        "python": f"{sys.version_info.major}.{sys.version_info.minor}",
        "implementation": "cp" if implementation == "CPython" else implementation,
        "abi": "cp" + "".join(str(sys.version_info[i]) for i in range(2)),
        "platforms": ["any"],
        "system": platform.system(),
        "machine": platform.machine(),
    }


def write_bundle(root, *, target=None, mutate=None):
    site = root / "site-packages"
    package = site / "demo_pkg"
    dist = site / "demo_pkg-1.2.3.dist-info"
    package.mkdir(parents=True)
    dist.mkdir()
    (package / "__init__.py").write_text("value = 1\n")
    (dist / "METADATA").write_text("Metadata-Version: 2.1\nName: demo_pkg\nVersion: 1.2.3\n")
    (dist / "INSTALLER").write_text("pip\n")
    record = {
        "schema": "marketmaker.python_runtime_bundle.v1",
        "target": target or current_target(),
        "requirements": {"demo_pkg": "1.2.3"},
        "imports": ["demo_pkg"],
        "site": "site-packages",
        "files": digest_tree(site),
    }
    if mutate:
        mutate(record, site)
    (root / "PYTHON_RUNTIME.json").write_text(json.dumps(record, sort_keys=True))
    return root


def test_spec_injects_runtime_validation_output_and_rejects_invalid_bindings():
    spec = validate(workflow())
    port = spec["jobs"][0]["outputs"]["runtime_validation"]
    assert port["path"] == "artifacts/runtime/VALIDATION.json"
    assert port["schema"] == "marketmaker.job_runtime_validation.v1"
    assert port["type"] == "json"
    missing = workflow()
    missing["jobs"][0]["python_environment"] = {"input": "absent"}
    with pytest.raises(ValueError, match="declared input"):
        validate(missing)
    overlap = workflow()
    overlap["jobs"][0]["portable_inputs"] = ["runtime"]
    with pytest.raises(ValueError, match="relocated document"):
        validate(overlap)
    assert "python_environment" in batch.OPTIONS


def test_runtime_request_validate_rejects_ranges_and_accepts_exact_wheels():
    request = {
        "schema": "marketmaker.python_runtime_request.v1",
        "target": current_target(),
        "requirements": {"demo_pkg": "1.2.3"},
        "wheels": [{"path": "demo_pkg-1.2.3-py3-none-any.whl", "sha256": "c" * 64}],
        "imports": ["demo_pkg"],
        "max_bytes": 1 << 20,
        "min_free_bytes": 0,
    }
    assert validate_runtime_request(deepcopy(request))["requirements"]["demo_pkg"] == "1.2.3"
    bad = deepcopy(request)
    bad["requirements"]["demo_pkg"] = ">=1.2"
    with pytest.raises(ValueError, match="exact versions"):
        validate_runtime_request(bad)


def test_isolated_environment_helper_passes_and_fails_on_shipped_bytes(tmp_path):
    from research_workflows.execution.environment import verify

    bundle = write_bundle(tmp_path / "ok")
    passed = verify(bundle)
    assert passed["status"] == "PASS"
    assert passed["requirements"]["demo-pkg"] == "1.2.3"
    assert "demo_pkg" in passed["imports"]

    mismatched = write_bundle(tmp_path / "bad")
    (mismatched / "site-packages/demo_pkg/__init__.py").write_text("value = 2\n")
    with pytest.raises(ValueError, match="runtime files differ"):
        verify(mismatched)

    output = tmp_path / "validation.json"
    completed = subprocess.run(
        [sys.executable, "-I", "-B", str(HELPER), str(mismatched), str(output)],
        cwd=tmp_path, capture_output=True, text=True,
    )
    assert completed.returncode == 2
    record = json.loads(output.read_text())
    assert record["schema"] == "marketmaker.job_runtime_validation.v1"
    assert record["status"] == "FAIL"
    assert "runtime files differ" in record["error"]


def _job_tree(tmp_path, bundle, *, validation_ok=True):
    work = tmp_path / "work"
    capsule = work / "blobs/capsule"
    code = work / "blobs/code"
    runtime = work / "blobs/inputs/runtime"
    capsule.mkdir(parents=True)
    code.mkdir(parents=True)
    shutil.copyfile(HELPER, code / "environment.py")
    if validation_ok:
        write_bundle(runtime)
    else:
        runtime.mkdir(parents=True)
        (runtime / "PYTHON_RUNTIME.json").write_text(json.dumps({
            "schema": "not-a-runtime", "site": "site-packages",
        }))
    (capsule / "main.py").write_text(
        "import os, pathlib, sys\n"
        "pathlib.Path(sys.argv[1]).write_text(os.environ.get('PYTHONPATH', ''))\n"
    )
    spec = validate(workflow())
    job = spec["jobs"][0]
    job["args"] = ["{output.marker}"]
    job["outputs"]["marker"] = {"type": "file", "path": "artifacts/marker.txt"}
    (work / "blobs").mkdir(exist_ok=True)
    (work / "blobs/job.json").write_text(json.dumps({
        "job": job, "resources": {"cpus": 1, "memory_mb": 512},
        "workflow_sha256": "d" * 64,
    }))
    return work


def test_run_wires_pythonpath_after_validation_and_records_validation_failure(tmp_path, monkeypatch):
    from research_workflows.execution import run as runner

    success = _job_tree(tmp_path / "pass", None, validation_ok=True)
    monkeypatch.chdir(success)
    assert runner.main() == 0
    marker = (success / "artifacts/marker.txt").read_text()
    site = str((success / "blobs/inputs/runtime/site-packages").resolve())
    capsule = str((success / "blobs/capsule").resolve())
    assert marker.split(os.pathsep)[0] == site
    assert capsule in marker.split(os.pathsep)
    validation = json.loads((success / "artifacts/runtime/VALIDATION.json").read_text())
    assert validation["status"] == "PASS"
    execution = json.loads((success / "WORKFLOW_EXECUTION.json").read_text())
    assert execution["native_exit_code"] == 0
    assert execution.get("status") != "RUNTIME_VALIDATION_FAILED"

    failure = _job_tree(tmp_path / "fail", None, validation_ok=False)
    monkeypatch.chdir(failure)
    code = runner.main()
    assert code != 0
    record = json.loads((failure / "WORKFLOW_EXECUTION.json").read_text())
    assert record["status"] == "RUNTIME_VALIDATION_FAILED"
    assert record["native_exit_code"] is None
    assert record["validation_exit_code"] == code
    assert not (failure / "artifacts/marker.txt").exists()
    failed = json.loads((failure / "artifacts/runtime/VALIDATION.json").read_text())
    assert failed["status"] == "FAIL"
