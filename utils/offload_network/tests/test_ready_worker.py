"""Readiness regressions. Docker cases are opt-in and use synthetic files only."""

import concurrent.futures
import dataclasses
import http.client
import io
import json
import os
import subprocess
import sys
import tarfile
import threading
import time
from unittest import mock
from urllib.error import HTTPError

import pytest

from offload_service.client import Client
from offload_service.core import CapacityError, Conflict, Template, Worker
from offload_service.http_api import Server
from simulator import JobRequest, SimulatedNetwork
from v2 import launcher, result, seal, submit, transport
from v2.manifest import HostSpec, ResultSpec, SealError, SealedBlob, SealedManifest, sha256_of_file

TOKEN = "x" * 43


@pytest.fixture
def template(tmp_path):
    code = tmp_path / "code"
    code.mkdir()
    (code / "helper.py").write_text("FACTOR = 2\n")
    script = code / "main.py"
    script.write_text(
        "import pathlib,json,sys,helper\n"
        "value = int(pathlib.Path('blobs/data/value.txt').read_text())\n"
        "pathlib.Path('result.json').write_text(json.dumps({'value':value*helper.FACTOR,'args':sys.argv[1:]}))\n"
    )
    data = tmp_path / "value.txt"
    data.write_text("7")
    return Template(
        "test-job", script, code_dir=code, data=((data, "data/value.txt"),), timeout_s=15
    )


@pytest.fixture
def worker(tmp_path, template):
    with Worker(tmp_path / "store", [template], backend="trusted-local", min_free_mb=0) as worker:
        yield worker


@pytest.fixture
def api(worker):
    server = Server(("127.0.0.1", 0), worker, TOKEN)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    client = Client(f"http://127.0.0.1:{server.server_port}", TOKEN)
    try:
        yield client, server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_http_round_trip_snapshot_idempotence_and_ack(api, worker, template, tmp_path):
    client, _ = api
    accepted = client.submit("test-job", job_id="zz-first", args=["hello"])
    assert accepted["state"] == "queued"
    assert client.submit("test-job", job_id="zz-first", args=["hello"]) == accepted
    with pytest.raises(HTTPError) as conflict:
        client.submit("test-job", job_id="zz-first", args=["different"])
    assert conflict.value.code == 409
    template.data[0][0].write_text("99")
    template.entrypoint.write_text("raise RuntimeError('must not execute changed code')")
    worker.start()
    finished = client.wait("zz-first", deadline=15)
    assert finished["state"] == "succeeded", finished
    output = client.download("zz-first", tmp_path / "returned")
    assert json.loads((output / "result.json").read_text()) == {"value": 14, "args": ["hello"]}
    status = client.request("/v1/jobs/zz-first")
    assert status["acknowledged_sha256"] == status["receipt"]["result_sha256"]
    assert worker.result("zz-first")[0].exists()  # ACK is not deletion
    assert client.download("zz-first", output) == output  # lost-ACK retry is safe


def test_auth_missing_wrong_duplicate_and_large_body(api):
    client, server = api
    for values in ([], ["Bearer " + "y" * 43], ["Bearer " + TOKEN] * 2):
        conn = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
        conn.putrequest("GET", "/v1/health")
        for value in values:
            conn.putheader("Authorization", value)
        conn.endheaders()
        assert conn.getresponse().status == 401
        conn.close()
    assert client.request("/v1/health")["ready"]
    with pytest.raises(HTTPError) as response:
        client.submit("test-job", metadata={"oversized": "a" * 66000})
    assert response.value.code == 400


def test_fifo_and_concurrent_claims(worker):
    for job_id in ("zz-first", "aa-second", "mm-third"):
        worker.submit({"job_id": job_id, "template": "test-job"})
    assert worker.process_next()["job_id"] == "zz-first"
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        claimed = list(pool.map(lambda _: worker.process_next(), range(4)))
    assert sorted(x["job_id"] for x in claimed if x) == ["aa-second", "mm-third"]
    assert all(x["state"] == "succeeded" for x in claimed if x)


def test_restart_retains_pending_and_terminalizes_abandoned_claim(tmp_path, template):
    root = tmp_path / "store"
    with Worker(root, [template], backend="trusted-local", min_free_mb=0) as one:
        one.submit({"job_id": "first-job", "template": "test-job"})
        one.submit({"job_id": "second-job", "template": "test-job"})
        assert one._claim()[0] == "first-job"  # crash before execution
        with pytest.raises(TimeoutError):
            Worker(root, [template], backend="trusted-local", min_free_mb=0)
    with Worker(root, [template], backend="trusted-local", min_free_mb=0) as two:
        assert two.status("first-job")["state"] == "interrupted"
        assert two.process_next()["job_id"] == "second-job"


@pytest.mark.parametrize("phase", ["preparing", "running"])
def test_restart_preserves_cancellation_instead_of_making_it_retryable(tmp_path, template, phase):
    root = tmp_path / "store"
    with Worker(root, [template], backend="trusted-local", min_free_mb=0) as one:
        one.submit({"job_id": "cancelled-claim", "template": "test-job"})
        one.submit({"job_id": "other-queued", "template": "test-job"})
        claimed, attempt, _ = one._claim()
        assert claimed == "cancelled-claim"
        one.cancel(claimed)
        with one.transaction() as db:
            db.execute("UPDATE jobs SET state=? WHERE id=?", (phase, claimed))
    with Worker(root, [template], backend="trusted-local", min_free_mb=0) as two:
        status = two.status(claimed)
        assert status["cancel_requested"] and status["state"] == "cancelled"
        assert status["receipt"]["attempt"] == attempt
        assert two.process_next()["job_id"] == "other-queued"
        assert two.process_next() is None


@pytest.mark.parametrize("stopping", [False, True])
def test_cancel_after_preparation_never_launches_a_subprocess(worker, monkeypatch, stopping):
    worker.submit({"job_id": "cancel-prelaunch", "template": "test-job"})
    def prepare(work, payload):
        worker.cancel("cancel-prelaunch")
        if stopping:
            worker.stop.set()
    monkeypatch.setattr(worker, "prepare_extra_inputs", prepare)
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: pytest.fail("cancelled work was launched"))
    status = worker.process_next()
    assert status["state"] == "cancelled"


def test_cancellation_timeout_and_capacity(worker, template):
    template.entrypoint.write_text("import time\ntime.sleep(30)\n")
    worker.max_pending = 1
    worker.submit({"job_id": "cancel-job", "template": "test-job"})
    with pytest.raises(CapacityError):
        worker.submit({"job_id": "extra-job", "template": "test-job"})
    worker.start()
    deadline = time.monotonic() + 5
    while worker.status("cancel-job")["state"] != "running" and time.monotonic() < deadline:
        time.sleep(0.05)
    worker.cancel("cancel-job")
    while worker.status("cancel-job")["state"] == "running" and time.monotonic() < deadline:
        time.sleep(0.05)
    assert worker.status("cancel-job")["state"] == "cancelled"


def test_failure_result_retained_and_bad_ack_rejected(worker, template):
    template.entrypoint.write_text("raise RuntimeError('expected failure')\n")
    worker.submit({"job_id": "failed-job", "template": "test-job"})
    status = worker.process_next()
    assert status["state"] == "failed"
    assert status["receipt"]["exit_code"] == 73
    assert worker.result("failed-job")[0].exists()
    with pytest.raises(Conflict):
        worker.acknowledge("failed-job", "0" * 64)


def test_direct_declared_dependencies_are_importable(worker):
    worker.submit({"job_id": "imports-job", "template": "test-job"})
    status = worker.process_next()
    assert status["state"] == "succeeded", status


def test_admission_rejects_host_paths_images_and_environment(api):
    client, _ = api
    for key, value in [
        ("entrypoint", "/etc/passwd"),
        ("image", "arbitrary-image"),
        ("env", {"TOKEN": "override"}),
        ("sources", ["/private"]),
    ]:
        with pytest.raises(HTTPError) as error:
            client.request(
                "/v1/jobs", {"job_id": "bad-request", "template": "test-job", key: value}
            )
        assert error.value.code == 400


def test_corrupt_seal_fails_before_execution(worker):
    status, _ = worker.submit({"job_id": "corrupt-seal", "template": "test-job"})
    archive = worker.root / "bundles" / "corrupt-seal.tar.gz"
    with archive.open("ab") as stream:
        stream.write(b"corruption")
    status = worker.process_next()
    assert status["state"] == "failed"
    assert "sha mismatch" in status["receipt"]["error"]
    assert not status["receipt"].get("result_sha256")


def test_queued_cancel_is_terminal_with_receipt(worker):
    worker.submit({"job_id": "cancel-before", "template": "test-job"})
    status = worker.cancel("cancel-before")
    assert status["state"] == "cancelled"
    assert status["receipt"]["state"] == "cancelled"
    assert worker.process_next() is None


def test_extraction_refuses_symlink_destination(tmp_path):
    if os.name == "nt":
        pytest.skip("symlink creation requires Windows developer privileges")
    outside = tmp_path / "outside"
    outside.mkdir()
    destination = tmp_path / "link"
    destination.symlink_to(outside, target_is_directory=True)
    archive = tmp_path / "result.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        tar.addfile(tarfile.TarInfo("proof.txt"), io.BytesIO(b""))
    with pytest.raises(SealError, match="symlink"):
        result._safe_extract(archive, destination)
    assert not list(outside.iterdir())


def test_same_size_different_seal_hash_transfers_again(tmp_path):
    path = tmp_path / "seal.tar.gz"
    path.write_bytes(b"content")
    digest = sha256_of_file(path)
    with (
        mock.patch.object(transport, "_mkdir_remote"),
        mock.patch.object(transport, "remote_file_size", return_value=7),
        mock.patch.object(transport, "remote_file_sha256", side_effect=["0" * 64, digest]),
        mock.patch.object(transport, "_ssh_args", return_value=["ssh"]),
        mock.patch.object(transport, "_retrying") as push,
    ):
        transport.push_seal(seal_path_local=path, host_alias="fake", remote_workdir="/jobs")
        push.assert_called_once()
        assert "--checksum" in push.call_args.args[0]


def test_simulator_snapshot_fifo_duplicates_and_recovery(tmp_path):
    script = tmp_path / "job.py"
    script.write_text("import pathlib\npathlib.Path('result.json').write_text('{}')\n")
    root = tmp_path / "simulation"
    network = SimulatedNetwork(root, workers={"test": "linux"}, sources={})
    for job_id in ("zz-first", "aa-next"):
        network.enqueue(JobRequest(str(script), "test", job_id=job_id))
    with pytest.raises(ValueError, match="already exists"):
        network.enqueue(JobRequest(str(script), "test", job_id="zz-first"))
    script.write_text("raise RuntimeError('changed')")
    first = network.process_next()
    assert first["job_id"] == "zz-first" and first["status"] == "succeeded"
    with mock.patch.object(network, "_execute", side_effect=SystemExit("interrupted")):
        with pytest.raises(SystemExit):
            network.process_next()
    replacement = SimulatedNetwork(root, workers={"test": "linux"}, sources={})
    receipt = json.loads((replacement.controller / "receipts" / "aa-next.json").read_text())
    assert receipt["error"]["type"] == "Interrupted"
    assert replacement.process_next() is None


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="POSIX process group regression; Docker tests cover namespace termination",
)
def test_timeout_stops_descendant_and_cleans_environment(tmp_path, monkeypatch):
    script = tmp_path / "child.py"
    marker = tmp_path / "should-not-appear"
    child = f"import time,pathlib;time.sleep(1);pathlib.Path({str(marker)!r}).write_text('bad')"
    script.write_text(
        "import subprocess,sys,time,os\n"
        "assert 'AUDIT_ONLY_SECRET' not in os.environ\n"
        f"subprocess.Popen([sys.executable,'-c',{child!r}])\ntime.sleep(5)\n"
    )
    monkeypatch.setenv("AUDIT_ONLY_SECRET", "synthetic")
    network = SimulatedNetwork(tmp_path / "network", workers={"test": "linux"}, sources={})
    network.enqueue(JobRequest(str(script), "test", timeout_s=0.3))
    assert network.process_next()["error"]["type"] == "TimeoutExpired"
    time.sleep(1.1)
    assert not marker.exists()


def test_legacy_queue_requires_confirmed_stop_before_recovery(tmp_path):
    from trading_common.data_storage.external_queue import (
        connect,
        enqueue_task,
        acquire_task,
        recover_task,
    )

    path = tmp_path / "queue.sqlite"
    conn = connect(path)
    for name in ("first", "second"):
        enqueue_task(
            conn, traffic_log=None, name=name, command=["echo", name], lane="data", priority=0
        )
    task = acquire_task(conn, traffic_log=None, worker_id="old", lane="data")
    with pytest.raises(ValueError, match="confirm"):
        recover_task(conn, db_path=path, task_id=task["id"], confirmed_stopped=False)
    recover_task(conn, db_path=path, task_id=task["id"], confirmed_stopped=True)
    assert acquire_task(conn, traffic_log=None, worker_id="new", lane="data")["name"] == "second"
    conn.close()


def test_zstandard_seal_round_trip(tmp_path, template):
    pytest.importorskip("zstandard")
    manifest = SealedManifest(
        job_id="zstd-job",
        host=HostSpec("fake", "/jobs"),
        blobs=[SealedBlob("entrypoint", str(template.entrypoint), "entry.py")],
        entrypoint_rel="entry.py",
        result=ResultSpec(local_dir="results"),
        archive_format="tar.zst",
    )
    archive = seal.build_seal(manifest, out_dir=tmp_path / "bundles")
    assert seal.verify_seal(archive, expected_sha256=manifest.seal_sha256).job_id == "zstd-job"
    seal.extract_seal(archive, tmp_path / "extracted")
    assert (
        tmp_path / "extracted" / "blobs" / "entry.py"
    ).read_bytes() == template.entrypoint.read_bytes()


@pytest.mark.parametrize(
    "member_name,kind",
    [
        ("../escape", "file"),
        ("/absolute", "file"),
        ("C:/drive", "file"),
        ("dir\\..\\escape", "file"),
        ("link", "symlink"),
        ("hard", "hardlink"),
        ("fifo", "fifo"),
        ("NUL", "file"),
        ("a:stream", "file"),
    ],
)
def test_archive_policy_on_all_supported_pythons(tmp_path, member_name, kind):
    archive = tmp_path / "bad.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        member = tarfile.TarInfo(member_name)
        member.type = {
            "file": tarfile.REGTYPE,
            "symlink": tarfile.SYMTYPE,
            "hardlink": tarfile.LNKTYPE,
            "fifo": tarfile.FIFOTYPE,
        }[kind]
        member.linkname = "../outside"
        tar.addfile(member, io.BytesIO(b""))
    with pytest.raises(SealError):
        result._safe_extract(archive, tmp_path / "result")
    with tarfile.open(archive) as tar, pytest.raises(SealError):
        seal._safe_extract_tar(tar, tmp_path / "seal")


def test_duplicate_and_oversized_archives_fail(tmp_path):
    archive = tmp_path / "duplicate.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        for _ in range(2):
            member = tarfile.TarInfo("file.txt")
            member.size = 1
            tar.addfile(member, io.BytesIO(b"x"))
    with pytest.raises(SealError, match="duplicate"):
        result._safe_extract(archive, tmp_path / "out")
    with pytest.raises(SealError, match="limits"):
        result._safe_extract(archive, tmp_path / "small", max_bytes=0)


def test_result_transfer_failure_never_cleans_remote(tmp_path):
    manifest = SealedManifest(job_id="retained-job", host=HostSpec("fake", "/jobs"))
    with (
        mock.patch.object(submit, "build_seal", return_value=tmp_path / "seal.tar.gz"),
        mock.patch.object(submit, "push_seal", return_value="/jobs/seal.tar.gz"),
        mock.patch.object(
            submit,
            "launch",
            return_value={"workdir": "/jobs/test", "status_path": "/jobs/test/status.json"},
        ),
        mock.patch.object(
            submit, "read_remote_status", return_value={"phase": "exited", "exit_code": 0}
        ),
        mock.patch.object(submit, "fetch_and_unpack", side_effect=OSError("download interrupted")),
        mock.patch.object(submit, "remote_remove") as remove,
    ):
        with pytest.raises(OSError):
            submit.submit_one(manifest, bundle_out_dir=tmp_path)
        remove.assert_not_called()


@pytest.mark.skipif(
    sys.platform == "win32", reason="real POSIX shell; Windows path has separate command tests"
)
def test_verified_remote_extract_real_posix_and_partial_resume(tmp_path, template):
    manifest = SealedManifest(
        job_id="extract-job",
        host=HostSpec("fake", "/jobs"),
        blobs=[SealedBlob("entrypoint", str(template.entrypoint), "entry.py")],
        entrypoint_rel="entry.py",
        result=ResultSpec(local_dir="results"),
    )
    archive = seal.build_seal(manifest, out_dir=tmp_path / "bundles")
    destination = tmp_path / "remote with spaces"
    destination.mkdir()
    (destination / "manifest.json").write_text("{}")

    def local_remote(**kwargs):
        return subprocess.run(
            ["sh", "-s", "--", *kwargs["args"]],
            input=kwargs["script"],
            capture_output=True,
            text=True,
            timeout=15,
        )

    with mock.patch.object(launcher, "remote_run_posix_retrying", side_effect=local_remote):
        options = dict(
            seal_remote_path=str(archive),
            workdir=str(destination),
            archive_format="tar.gz",
            platform="linux",
            python_executable=sys.executable,
            expected_sha256=manifest.seal_sha256,
        )
        assert launcher.extract_seal_remote("fake", **options)
        assert not launcher.extract_seal_remote("fake", **options)
        assert (destination / "runner.py").exists()
        options["expected_sha256"] = "0" * 64
        with pytest.raises(SealError, match="mismatch"):
            launcher.extract_seal_remote("fake", **options)


@pytest.mark.skipif(
    os.environ.get("OFFLOAD_TEST_DOCKER") != "1", reason="opt-in real Docker isolation test"
)
def test_real_docker_sandbox_and_result(tmp_path, template, monkeypatch):
    marker = tmp_path / "outside-secret.txt"
    marker.write_text("synthetic-controller-only")
    monkeypatch.setenv("OFFLOAD_SYNTHETIC_SECRET", "must-not-inherit")
    template.entrypoint.write_text(
        "import pathlib,json,os,socket,helper\n"
        f"outside = pathlib.Path({str(marker)!r}).exists()\n"
        "readonly = False\n"
        "try: pathlib.Path('blobs/data/value.txt').write_text('bad')\n"
        "except OSError: readonly = True\n"
        "network = False\n"
        "try: socket.create_connection(('1.1.1.1',443),timeout=0.5); network=True\n"
        "except OSError: pass\n"
        "pathlib.Path('result.json').write_text(json.dumps({'outside':outside,'secret':os.getenv('OFFLOAD_SYNTHETIC_SECRET'),"
        "'readonly':readonly,'network':network,'dependency':helper.FACTOR}))\n"
    )
    with Worker(tmp_path / "docker-store", [template], min_free_mb=0) as worker:
        worker.submit({"job_id": "sandbox-job", "template": "test-job"})
        status = worker.process_next()
        assert status["state"] == "succeeded", status
        archive, _ = worker.result("sandbox-job")
        with tarfile.open(archive) as tar:
            observed = json.load(tar.extractfile("result.json"))
        assert observed == {
            "outside": False,
            "secret": None,
            "readonly": True,
            "network": False,
            "dependency": 2,
        }


@pytest.mark.skipif(
    os.environ.get("OFFLOAD_TEST_DOCKER") != "1", reason="opt-in real Docker timeout/recovery test"
)
@pytest.mark.parametrize("cancel_before_restart", [False, True])
def test_real_docker_timeout_and_crash_reconciliation(tmp_path, template, cancel_before_restart):
    template.entrypoint.write_text(
        "import subprocess,sys,time\nsubprocess.Popen([sys.executable,'-c','import time; time.sleep(60)'])\ntime.sleep(60)\n"
    )
    template = dataclasses.replace(template, timeout_s=0.5)
    root = tmp_path / "docker-store"
    with Worker(root, [template], min_free_mb=0) as worker:
        worker.submit({"job_id": "timeout-job", "template": "test-job"})
        status = worker.process_next()
        assert status["state"] == "failed", status.get("receipt")
        assert "TimeoutError" in status["receipt"]["error"]
        attempt = status["receipt"]["attempt"]
        assert subprocess.run(["docker", "inspect", attempt], capture_output=True).returncode != 0
        worker.submit({"job_id": "orphan-job", "template": "test-job"})
        job_id, attempt, payload = worker._claim()
        subprocess.run(
            [
                "docker",
                "run",
                "-d",
                "--name",
                attempt,
                "--network=none",
                payload["image_id"],
                "sleep",
                "60",
            ],
            check=True,
            capture_output=True,
        )
        if cancel_before_restart:
            worker.cancel(job_id)
    with Worker(root, [template], min_free_mb=0) as replacement:
        assert replacement.status(job_id)["state"] == ("cancelled" if cancel_before_restart else "interrupted")
        assert subprocess.run(["docker", "inspect", attempt], capture_output=True).returncode != 0


@pytest.mark.skipif(
    os.environ.get("OFFLOAD_TEST_DOCKER") != "1", reason="opt-in real Docker and HTTP gateway test"
)
def test_docker_job_through_authenticated_cloudflare_gateway(tmp_path, template):
    import asyncio

    pytest.importorskip("aiohttp")
    from aiohttp import web
    from external_machine_connect.cloudflare.connect import create_app

    async def exercise():
        with Worker(tmp_path / "gateway-worker", [template], min_free_mb=0) as worker:
            server = Server(("127.0.0.1", 0), worker, TOKEN)
            server_thread = threading.Thread(target=server.serve_forever, daemon=True)
            server_thread.start()
            worker.start()
            app = create_app(
                f"http://127.0.0.1:{server.server_port}", TOKEN, auth_header="X-Offload-Token"
            )
            runner = web.AppRunner(app, access_log=None)
            try:
                await runner.setup()
                site = web.TCPSite(runner, "127.0.0.1", 0)
                await site.start()
                client = Client(f"http://127.0.0.1:{runner.addresses[0][1]}", TOKEN)
                accepted = await asyncio.to_thread(client.submit, "test-job", job_id="gateway-job")
                assert accepted["job_id"] == "gateway-job"
                finished = await asyncio.to_thread(client.wait, "gateway-job", deadline=30)
                assert finished["state"] == "succeeded", finished
                output = await asyncio.to_thread(
                    client.download, "gateway-job", tmp_path / "gateway-result"
                )
                assert json.loads((output / "result.json").read_text())["value"] == 14
                assert worker.status("gateway-job")["acknowledged_sha256"]
            finally:
                await runner.cleanup()
                server.shutdown()
                server.server_close()
                server_thread.join(timeout=5)

    asyncio.run(exercise())
