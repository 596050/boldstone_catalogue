"""The Docker testing adapter must preserve explicit native resource requests."""
import argparse
import json
from pathlib import Path
import sys

import pytest

from research_workflows.execution import run as adapter


def invoked(monkeypatch, tmp_path, arguments):
    work = tmp_path / "work"
    entry = work / "blobs/capsule/repo/research/testing_stages/testing.py"
    entry.parent.mkdir(parents=True)
    entry.write_text("# The subprocess call is captured before execution.\n")
    job = {"id": "stages", "kind": "testing", "inputs": {}, "outputs": {},
           "args": arguments, "testing": {"repository": "repo", "through": "07"}}
    request = {"job": job, "resources": {"cpus": 2, "memory_mb": 4096},
               "workflow_sha256": "a" * 64}
    (work / "blobs/job.json").write_text(json.dumps(request))
    captured = []
    monkeypatch.chdir(work)
    monkeypatch.setattr(adapter.subprocess, "call", lambda command, **kw: captured.append(command) or 0)
    assert adapter.main() == 0
    assert len(captured) == 1 and captured[0][:3] == [sys.executable, "-B", str(entry)]
    parser = argparse.ArgumentParser()
    parser.add_argument("command")
    for name in ("cpu-limit", "memory-limit-gb", "worker-memory-gb", "threads-per-worker", "min-free-gb"):
        parser.add_argument("--" + name, type=float)
    for name in ("workflow", "data-refresh", "cache-mode", "through", "output"):
        parser.add_argument("--" + name)
    return parser.parse_args(captured[0][3:]), work


@pytest.mark.parametrize("form", ["separate", "equals"])
def test_explicit_resource_arguments_reach_native_cli(monkeypatch, tmp_path, form):
    declared = {"cpu-limit": "1", "memory-limit-gb": "3.5", "worker-memory-gb": "2",
                "threads-per-worker": "1", "min-free-gb": "7"}
    args = [item for key, value in declared.items()
            for item in (["--" + key, value] if form == "separate" else ["--" + key + "=" + value])]
    observed, _ = invoked(monkeypatch, tmp_path, args)
    for key, value in declared.items():
        assert getattr(observed, key.replace("-", "_")) == float(value)


def test_resource_defaults_remain_available_for_unspecified_values(monkeypatch, tmp_path):
    observed, _ = invoked(monkeypatch, tmp_path, ["--memory-limit-gb", "3.5"])
    assert observed.memory_limit_gb == 3.5
    assert observed.cpu_limit == 2 and observed.worker_memory_gb == 1
    assert observed.threads_per_worker == 1 and observed.min_free_gb == .01


def test_resource_precedence_does_not_replace_workflow_owned_arguments(monkeypatch, tmp_path):
    observed, work = invoked(monkeypatch, tmp_path, [
        "--output", "/different", "--through", "00", "--cache-mode", "reuse",
        "--data-refresh", "network", "--workflow", "diagnostic"])
    assert observed.output == str(work / "artifacts/testing")
    assert observed.through == "07" and observed.workflow == "research"
    assert observed.data_refresh == "pinned" and observed.cache_mode == "off"
