from __future__ import annotations

import json
import pathlib
import sys
import threading
import time

import pytest

ORCH_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ORCH_ROOT) not in sys.path:
    sys.path.insert(0, str(ORCH_ROOT))

from simulator import JobRequest, SimulatedNetwork, SourceRequest


@pytest.fixture
def network(tmp_path):
    source = tmp_path / "configured_sources" / "prices"
    source.mkdir(parents=True)
    (source / "bars.csv").write_text("symbol,close\nABC,123.45\n")
    return SimulatedNetwork(
        tmp_path / "simulated_network",
        workers={"windows-01": "windows", "linux-01": "linux", "mac-01": "macos"},
        sources={"prices": source},
    )


def _script(tmp_path, body, name="job.py"):
    path = tmp_path / name
    path.write_text(body)
    return path


def test_success_source_request_result_metadata_and_topology(network, tmp_path):
    script = _script(tmp_path, """
import csv, json, pathlib, sys
source = pathlib.Path('blobs/data/bars.csv')
row = next(csv.DictReader(source.open()))
pathlib.Path('result.json').write_text(json.dumps({'value': float(row['close']), 'args': sys.argv[1:]}))
pathlib.Path('artifacts').mkdir()
pathlib.Path('artifacts/proof.txt').write_text('isolated')
""")
    job_id = network.enqueue(JobRequest(
        entrypoint=str(script), worker="windows-01", args=["alpha", "beta"],
        metadata={"request_id": "request-7", "purpose": "source-round-trip"},
        sources=[SourceRequest("prices", "bars.csv", "data/bars.csv", "bars")],
    ))
    envelope = network.process_next()

    assert envelope["status"] == "succeeded"
    assert envelope["worker_os"] == "windows"
    assert envelope["metadata"]["request_id"] == "request-7"
    assert [s["name"] for s in envelope["stages"]] == [
        "sealed", "transferred_to_worker", "isolated", "runner_finished", "result_returned"
    ]
    result = json.loads((pathlib.Path(envelope["result"]["directory"]) / "result.json").read_text())
    assert result == {"value": 123.45, "args": ["alpha", "beta"]}
    assert (network.root / "hosts/windows-01/inbox").is_dir()
    assert (network.root / "hosts/linux-01/jobs").is_dir()
    assert (network.root / "hosts/mac-01/outbox").is_dir()
    assert not list((network.controller / "queue/running").iterdir())
    assert (network.controller / "queue/completed" / f"{job_id}.json").is_file()
    receipt = json.loads((network.controller / "receipts" / f"{job_id}.json").read_text())
    assert receipt["result"]["sha256"] == envelope["result"]["sha256"]


def test_remote_exception_returns_logs_status_and_error_envelope(network, tmp_path):
    script = _script(tmp_path, "raise RuntimeError('remote boom')\n")
    job_id = network.enqueue(JobRequest(
        entrypoint=str(script), worker="linux-01", metadata={"correlation": "c-9"}
    ))
    envelope = network.process_next()

    assert envelope["status"] == "failed"
    assert envelope["exit_code"] == 73
    assert envelope["error"]["type"] == "RemoteJobError"
    assert envelope["remote_status"]["phase"] == "exited"
    assert envelope["remote_status"]["exit_code"] == 73
    run_log = pathlib.Path(envelope["result"]["directory"]) / "run.log"
    assert "RuntimeError: remote boom" in run_log.read_text()
    assert (network.controller / "queue/failed" / f"{job_id}.json").is_file()


def test_timeout_is_terminal_and_queue_is_released(network, tmp_path):
    script = _script(tmp_path, "import time\ntime.sleep(5)\n")
    job_id = network.enqueue(JobRequest(
        entrypoint=str(script), worker="mac-01", timeout_s=0.15
    ))
    envelope = network.process_next()

    assert envelope["status"] == "failed"
    assert envelope["error"]["type"] == "TimeoutExpired"
    assert any(stage["name"] == "timed_out" for stage in envelope["stages"])
    assert not list((network.controller / "queue/running").iterdir())
    assert (network.controller / "queue/failed" / f"{job_id}.json").is_file()


@pytest.mark.parametrize("bad_path", ["missing.csv", "../outside.csv"])
def test_missing_or_escaping_source_fails_closed(network, tmp_path, bad_path):
    script = _script(tmp_path, "pass\n", f"{bad_path.replace('/', '_')}.py")
    job_id = network.enqueue(JobRequest(
        entrypoint=str(script), worker="linux-01",
        sources=[SourceRequest("prices", bad_path, "data/input.csv")],
    ))
    envelope = network.process_next()
    assert envelope["status"] == "failed"
    assert envelope["error"]["type"] in {"FileNotFoundError", "ValueError"}
    assert (network.controller / "queue/failed" / f"{job_id}.json").is_file()


def test_unknown_worker_and_source_are_rejected(network, tmp_path):
    script = _script(tmp_path, "pass\n")
    with pytest.raises(ValueError, match="unknown worker"):
        network.enqueue(JobRequest(entrypoint=str(script), worker="solaris-01"))
    job_id = network.enqueue(JobRequest(
        entrypoint=str(script), worker="linux-01",
        sources=[SourceRequest("not-configured", "x", "data/x")],
    ))
    envelope = network.process_next()
    assert envelope["status"] == "failed"
    assert envelope["error"]["type"] == "KeyError"
    assert (network.controller / "queue/failed" / f"{job_id}.json").exists()


def test_queue_filtering_fifo_and_job_isolation(network, tmp_path):
    script = _script(tmp_path, """
import json, pathlib, sys
pathlib.Path('result.json').write_text(json.dumps({'token': sys.argv[1], 'cwd': str(pathlib.Path.cwd())}))
""")
    first = network.enqueue(JobRequest(entrypoint=str(script), worker="windows-01", args=["first"]))
    second = network.enqueue(JobRequest(entrypoint=str(script), worker="linux-01", args=["second"]))
    linux = network.process_next("linux-01")
    windows = network.process_next("windows-01")
    assert linux["job_id"] == second
    assert windows["job_id"] == first
    a = json.loads((pathlib.Path(linux["result"]["directory"]) / "result.json").read_text())
    b = json.loads((pathlib.Path(windows["result"]["directory"]) / "result.json").read_text())
    assert a["token"] == "second" and b["token"] == "first"
    assert a["cwd"] != b["cwd"]
    assert network.process_next() is None


def test_result_include_exclude_rules(network, tmp_path):
    script = _script(tmp_path, """
import pathlib
pathlib.Path('keep.json').write_text('{}')
pathlib.Path('discard.tmp').write_text('no')
pathlib.Path('secret.bin').write_bytes(b'no')
""")
    network.enqueue(JobRequest(entrypoint=str(script), worker="mac-01"))
    envelope = network.process_next()
    result_dir = pathlib.Path(envelope["result"]["directory"])
    assert (result_dir / "keep.json").exists()
    assert not (result_dir / "discard.tmp").exists()
    assert not (result_dir / "secret.bin").exists()


def test_atomic_queue_records_have_no_temporary_files(network, tmp_path):
    script = _script(tmp_path, "import pathlib\npathlib.Path('result.json').write_text('{}')\n")
    for worker in network.workers:
        network.enqueue(JobRequest(entrypoint=str(script), worker=worker))
    assert len(network.drain()) == 3
    assert not list(network.root.rglob("*.tmp"))
    assert len(list((network.controller / "queue/completed").glob("*.json"))) == 3
