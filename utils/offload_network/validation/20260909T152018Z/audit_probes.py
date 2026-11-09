"""Independent local validation probes; never contacts a worker or Cloudflare."""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import threading
import time
from unittest.mock import patch

parser = argparse.ArgumentParser()
parser.add_argument("--source", type=Path, required=True)
parser.add_argument("--out", type=Path, required=True)
args = parser.parse_args()
SOURCE = args.source.resolve()
OUT = args.out.resolve()
OUT.mkdir(parents=True, exist_ok=False)
sys.path.insert(0, str(SOURCE))
from simulator import JobRequest, SimulatedNetwork, SourceRequest
from v2 import launcher, result, seal, submit
from v2.manifest import HostSpec, ResultSpec, SealedBlob, SealedManifest
from trading_common.data_storage import external_queue

records = []
identities = {}
for path in sorted(SOURCE.rglob("*.py")):
    if not {".venv", "__pycache__", "simulated_network"}.intersection(path.parts):
        identities[path.relative_to(SOURCE).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
(OUT / "SOURCE_MANIFEST.json").write_text(json.dumps(identities, indent=2, sort_keys=True))


def probe(name, callback):
    root = OUT / name
    root.mkdir()
    try:
        record = {"name": name, "observed": callback(root)}
    except Exception as exc:
        record = {"name": name, "probe_error": f"{type(exc).__name__}: {exc}"}
    records.append(record)
    print(json.dumps(record, default=str), flush=True)


def network(root):
    data = root / "source"
    data.mkdir()
    (data / "input.txt").write_text("original")
    return SimulatedNetwork(root / "network", workers={"worker": "macos"}, sources={"data": data})


def script(root, text):
    path = root / "job.py"
    path.write_text(text)
    return path


def fifo(root):
    net = network(root)
    path = script(root, "pass\n")
    net.enqueue(JobRequest(str(path), "worker", job_id="zz-first"))
    net.enqueue(JobRequest(str(path), "worker", job_id="aa-second"))
    got = net.process_next()
    return {"enqueued_first": "zz-first", "executed_first": got["job_id"], "fifo": got["job_id"] == "zz-first"}


def duplicate(root):
    net = network(root)
    path = script(root, "pass\n")
    net.enqueue(JobRequest(str(path), "worker", job_id="same-job", args=["first"]))
    net.enqueue(JobRequest(str(path), "worker", job_id="same-job", args=["replacement"]))
    record = json.loads((net.controller / "queue/pending/same-job.json").read_text())
    return {"duplicate_rejected": False, "pending_records": len(list((net.controller / "queue/pending").glob("*.json"))),
            "stored_args": record["args"]}


def unpinned_data(root):
    net = network(root)
    path = script(root, "import pathlib\npathlib.Path('result.json').write_text(pathlib.Path('blobs/data/input.txt').read_text())\n")
    net.enqueue(JobRequest(str(path), "worker", sources=[SourceRequest("data", "input.txt", "data/input.txt")]))
    (root / "source/input.txt").write_text("changed-after-enqueue")
    envelope = net.process_next()
    delivered = (Path(envelope["result"]["directory"]) / "result.json").read_text()
    return {"queue_status": envelope["status"], "enqueued_bytes": "original", "executed_bytes": delivered,
            "immutable_at_enqueue": delivered == "original"}


def restart_running(root):
    net = network(root)
    path = script(root, "pass\n")
    jid = net.enqueue(JobRequest(str(path), "worker"))
    with patch.object(net, "_execute", side_effect=SystemExit("simulated controller interruption after claim")):
        try:
            net.process_next()
        except SystemExit:
            pass
    restarted = SimulatedNetwork(net.root, workers=net.workers, sources=net.sources)
    return {"job_id": jid, "running_records_after_restart": len(list((net.controller / "queue/running").glob("*.json"))),
            "resumed_job": restarted.process_next(), "receipt_exists": (net.controller / "receipts" / f"{jid}.json").exists()}


def concurrent_claim(root):
    net = network(root)
    path = script(root, "pass\n")
    net.enqueue(JobRequest(str(path), "worker"))
    barrier = threading.Barrier(2)
    original_replace = os.replace

    def interleave(src, dst):
        if Path(src).parent.name == "pending":
            barrier.wait(timeout=3)
        return original_replace(src, dst)

    def process():
        try:
            return net.process_next()
        except Exception as exc:
            return {"error": type(exc).__name__}

    with patch("simulator.os.replace", side_effect=interleave), patch.object(net, "_execute", return_value={"claimed": True}):
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(lambda _: process(), range(2)))
    return {"two_consumers_same_pending_job": outcomes}


def timeout_child(root):
    net = network(root)
    marker = root / "late-child-write.txt"
    child = f"import pathlib,time; time.sleep(1); pathlib.Path({str(marker)!r}).write_text('child-survived')"
    path = script(root, f"import subprocess,sys,time\nsubprocess.Popen([sys.executable,'-c',{child!r}], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)\ntime.sleep(10)\n")
    net.enqueue(JobRequest(str(path), "worker", timeout_s=0.4))
    envelope = net.process_next()
    time.sleep(1.2)  # Child is bounded and exits itself after writing only this fixture.
    return {"queue_status": envelope["status"], "error_type": envelope["error"]["type"],
            "descendant_wrote_after_timeout": marker.exists()}


def isolation(root):
    net = network(root)
    marker = net.controller / "synthetic-private-marker.txt"
    marker.write_text("synthetic-only")
    path = script(root,
        f"import json,os,pathlib\npathlib.Path('result.json').write_text(json.dumps({{'can_read_outside_job': pathlib.Path({str(marker)!r}).read_text() == 'synthetic-only', 'inherits_controller_environment': os.environ.get('OFFLOAD_AUDIT_SYNTHETIC') == 'marker-only'}}))\n")
    net.enqueue(JobRequest(str(path), "worker"))
    with patch.dict(os.environ, {"OFFLOAD_AUDIT_SYNTHETIC": "marker-only"}):
        envelope = net.process_next()
    return json.loads((Path(envelope["result"]["directory"]) / "result.json").read_text())


def make_manifest(root, body="pass\n", **kwargs):
    path = script(root, body)
    return SealedManifest(job_id="audit-job", host=HostSpec("synthetic", str(root / "remote"), platform="macos"),
                          blobs=[SealedBlob("entry", str(path), "code/job.py")], entrypoint_rel="code/job.py",
                          result=ResultSpec(local_dir=str(root / "results")), **kwargs)


def declared_import(root):
    manifest = make_manifest(root, "import offload_unique_audit_helper\n", extra_pythonpath=["blobs/code"])
    helper = root / "offload_unique_audit_helper.py"
    helper.write_text("VALUE=123\n")
    manifest.blobs.append(SealedBlob("helper", str(helper), "code/offload_unique_audit_helper.py"))
    archive = seal.build_seal(manifest, out_dir=root / "bundles")
    remote = root / "remote-job"
    seal.extract_seal(archive, remote)
    completed = subprocess.run([sys.executable, str(remote / "runner.py"), str(remote / "manifest.json")], cwd=remote, timeout=5)
    log = (remote / "run.log").read_text()
    return {"exit_code": completed.returncode, "declared_extra_pythonpath": manifest.extra_pythonpath,
            "module_not_found": "ModuleNotFoundError: No module named 'offload_unique_audit_helper'" in log}


def packed_status(root):
    net = network(root)
    path = script(root, "import pathlib\npathlib.Path('result.json').write_text('{}')\n")
    net.enqueue(JobRequest(str(path), "worker"))
    envelope = net.process_next()
    returned = json.loads((Path(envelope["result"]["directory"]) / "status.json").read_text())
    return {"receipt_status": envelope["status"], "remote_phase": envelope["remote_status"]["phase"],
            "packed_status_phase": returned["phase"], "packed_exit_code": returned.get("exit_code")}


def pull_failure_cleanup(root):
    manifest = make_manifest(root)
    removed = []
    with patch.object(submit, "push_seal", return_value="/synthetic/remote/seal.tar.gz"), \
         patch.object(submit, "launch", return_value={"workdir": "/synthetic/remote/job", "status_path": "/synthetic/remote/job/status.json"}), \
         patch.object(submit, "read_remote_status", return_value={"phase": "exited", "exit_code": 0}), \
         patch.object(submit, "fetch_and_unpack", side_effect=OSError("synthetic result transfer interrupted")), \
         patch.object(submit, "remote_remove", side_effect=lambda **kw: removed.append(kw["remote_path"])):
        try:
            submit.submit_one(manifest, bundle_out_dir=root / "bundles", poll_interval_s=0)
        except OSError:
            pass
    return {"result_transfer_failed": True, "remote_paths_requested_for_deletion": removed,
            "actual_remote_operations": 0}


def sqlite_recovery(root):
    db = root / "queue.sqlite"
    conn = external_queue.connect(db)
    for name in ("first", "second"):
        external_queue.enqueue_task(conn, traffic_log=None, name=name, command=[sys.executable, "-c", "pass"], lane="test", priority=1)
    first = external_queue.acquire_task(conn, traffic_log=None, worker_id="disconnected-worker", lane="test")
    conn.close()
    conn = external_queue.connect(db)
    second = external_queue.acquire_task(conn, traffic_log=None, worker_id="replacement-worker", lane="test")
    counts = external_queue.queue_status(conn)["counts"]
    conn.close()
    return {"first_claimed": first["id"], "replacement_can_claim": second is not None, "counts": counts}


def partial_extract(root):
    with patch.object(launcher, "remote_path_exists", return_value=True), \
         patch.object(launcher, "remote_run_posix_retrying") as command:
        performed = launcher.extract_seal_remote("synthetic", seal_remote_path="/synthetic/job.tar.gz", workdir="/synthetic/job", archive_format="tar.gz", platform="macos")
    return {"only_manifest_exists": True, "extraction_performed": performed, "remote_commands": command.call_count}


for name, callback in [
    ("fifo", fifo), ("duplicate", duplicate), ("queued_data_identity", unpinned_data),
    ("queue_restart", restart_running), ("queue_concurrent_claim", concurrent_claim),
    ("timeout_descendant", timeout_child), ("isolation_boundary", isolation),
    ("declared_dependency_import", declared_import), ("result_terminal_status", packed_status),
    ("result_transfer_failure_cleanup", pull_failure_cleanup), ("sqlite_recovery", sqlite_recovery),
    ("partial_extract_resume", partial_extract),
]:
    probe(name, callback)
(OUT / "PROBES.json").write_text(json.dumps(records, indent=2, default=str))
