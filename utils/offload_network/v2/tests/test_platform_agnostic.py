from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import tarfile
import tempfile
from unittest import mock

import pytest

HERE = pathlib.Path(__file__).resolve().parent
ORCH = HERE.parents[1]
if str(ORCH) not in sys.path:
    sys.path.insert(0, str(ORCH))

from v2 import launcher, transport
from v2 import submit
from v2.defaults import prestaged_cache_root, remote_workdir_default
from v2.fleet_adapter import _build_generic_manifest
from v2.manifest import HostSpec, ResultSpec, SealError, SealedBlob, SealedManifest
from v2.seal import build_seal, extract_seal


@pytest.mark.parametrize("platform", ["windows", "linux", "macos"])
def test_host_platform_contract(platform):
    host = HostSpec("worker", "/srv/offload", platform=platform)
    host.validate()


def test_unknown_platform_fails_closed():
    with pytest.raises(SealError, match="HostSpec.platform"):
        HostSpec("worker", "/srv/offload", platform="solaris").validate()


@pytest.mark.parametrize("platform", ["linux", "macos"])
def test_posix_defaults_are_posix_paths(platform, monkeypatch):
    monkeypatch.delenv("V2_REMOTE_WORKDIR", raising=False)
    monkeypatch.delenv("V2_PRESTAGED_CACHE_ROOT", raising=False)
    assert remote_workdir_default({"platform": platform}) == "/var/tmp/offload/jobs"
    assert prestaged_cache_root({"platform": platform}) == "/var/tmp/offload/prestaged_caches"


@pytest.mark.parametrize("platform", ["linux", "macos"])
def test_generic_manifest_uses_python3_for_posix(tmp_path, platform):
    with mock.patch("v2.fleet_adapter._standard_code_blobs", return_value=[]):
        manifest = _build_generic_manifest(
            job_id=1, workflow="probe", module="example.module", pass_args=[],
            host_alias="worker", remote_workdir="/srv/offload", rsync_path=None,
            host_repo="/srv/repo", host_results_root=None, extra_blobs=[],
            bundle_out_dir=tmp_path, host_platform=platform,
        )
    assert manifest.host.platform == platform
    assert manifest.host.python_executable == "python3"


def test_windows_manifest_schema_remains_backward_compatible():
    manifest = SealedManifest(
        job_id="job-windows-compatible",
        host=HostSpec("worker", "C:/sealed/jobs"),
        blobs=[SealedBlob("entrypoint", __file__, "code/job.py")],
        entrypoint_rel="code/job.py",
        result=ResultSpec(local_dir="results"),
    )
    assert "platform" not in manifest.to_dict()["host"]
    assert SealedManifest.from_dict(manifest.to_dict()).host.platform == "windows"


@pytest.mark.skipif(sys.platform == "win32", reason="requires a POSIX shell")
@pytest.mark.parametrize("platform", ["linux", "macos"])
def test_posix_bootstrap_real_local_round_trip(tmp_path, platform):
    entrypoint = tmp_path / "job.py"
    entrypoint.write_text(
        "import json,pathlib,sys\n"
        "pathlib.Path('result.json').write_text(json.dumps({'platform':sys.argv[1]}))\n"
    )
    manifest = SealedManifest(
        job_id=f"job-posix-{platform}",
        host=HostSpec("worker", "/srv/offload", platform=platform,
                      python_executable=sys.executable),
        blobs=[SealedBlob("entrypoint", str(entrypoint), "code/job.py")],
        entrypoint_rel="code/job.py",
        run_args=[platform],
        result=ResultSpec(local_dir=str(tmp_path / "results")),
    )
    seal = build_seal(manifest, out_dir=tmp_path / "bundles")
    extracted = tmp_path / "remote" / manifest.job_id
    extract_seal(seal, extracted)
    mode = (extracted / "bootstrap.sh").stat().st_mode
    assert mode & 0o111

    completed = subprocess.run(
        ["sh", "bootstrap.sh"], cwd=extracted, capture_output=True, text=True, timeout=10
    )
    assert completed.returncode == 0
    status = json.loads((extracted / "status.json").read_text())
    assert status["phase"] == "exited"
    assert status["exit_code"] == 0
    archive = pathlib.Path(status["result_archive"])
    with tarfile.open(archive, "r:gz") as result_tar:
        result = json.load(result_tar.extractfile("result.json"))
    assert result == {"platform": platform}


def test_remote_run_posix_uses_stdin_and_quotes_arguments():
    completed = subprocess.CompletedProcess([], 0, "ok", "")
    dangerous = "/srv/jobs/a path/$(touch should-not-run)"
    with mock.patch.object(transport.subprocess, "run", return_value=completed) as run:
        got = transport.remote_run_posix(
            host_alias="linux-worker",
            script='printf "%s" "$1"',
            args=[dangerous],
            timeout=17,
        )
    assert got is completed
    command = run.call_args.args[0]
    assert command[-2] == "linux-worker"
    assert command[-1].startswith("sh -s -- ")
    assert "'$(touch should-not-run)'" not in command[-1]
    assert "'/srv/jobs/a path/$(touch should-not-run)'" in command[-1]
    assert run.call_args.kwargs["input"] == 'printf "%s" "$1"'
    assert run.call_args.kwargs["timeout"] == 17


@pytest.mark.parametrize("platform", ["linux", "macos"])
def test_posix_remote_lifecycle_commands(platform):
    ok = subprocess.CompletedProcess([], 0, "EXTRACTED\nPID=4321\n", "")
    with mock.patch.object(launcher, "remote_run_posix_retrying", return_value=ok) as remote, \
         mock.patch.object(launcher, "remote_path_exists", return_value=False) as exists:
        launcher.ensure_remote_dir("host", "/srv/jobs with spaces", platform=platform)
        extracted = launcher.extract_seal_remote(
            "host", seal_remote_path="/srv/inbox/job.tar.gz",
            workdir="/srv/jobs/job-1", archive_format="tar.gz", platform=platform,
            expected_sha256="a" * 64,
        )
        pid = launcher.spawn_bootstrap(
            "host", "/srv/jobs/job-1", platform=platform
        )
    assert extracted is True
    assert pid == 4321
    assert remote.call_count == 3
    assert all(call.kwargs["args"] for call in remote.call_args_list)
    assert exists.call_count == 1
    assert all(call.kwargs["platform"] == platform for call in exists.call_args_list)
    assert "nohup sh ./bootstrap.sh" in remote.call_args_list[2].kwargs["script"]


@pytest.mark.parametrize("platform", ["linux", "macos"])
def test_posix_status_read_and_malformed_retry(platform):
    good = subprocess.CompletedProcess([], 0, '{"phase":"exited","exit_code":0}', "")
    bad = subprocess.CompletedProcess([], 0, '{partial', "")
    with mock.patch.object(launcher, "remote_run_posix_retrying", side_effect=[bad, good]):
        assert launcher.read_remote_status("host", "/srv/job/status.json", platform=platform) is None
        assert launcher.read_remote_status("host", "/srv/job/status.json", platform=platform) == {
            "phase": "exited", "exit_code": 0,
        }


@pytest.mark.parametrize("platform", ["linux", "macos"])
def test_posix_path_size_promotion_and_cleanup(platform):
    yes = subprocess.CompletedProcess([], 0, "YES", "")
    size = subprocess.CompletedProcess([], 0, "123\n", "")
    ok = subprocess.CompletedProcess([], 0, "", "")
    with mock.patch.object(
        transport, "remote_run_posix_retrying", side_effect=[yes, size, ok, ok]
    ) as remote:
        assert transport.remote_path_exists("host", "/srv/a b/file", platform=platform)
        assert transport.remote_file_size("host", "/srv/a b/file", platform=platform) == 123
        transport._promote_remote_partial(
            host_alias="host", partial_path="/srv/a b/file.partial",
            final_path="/srv/a b/file", platform=platform,
        )
        transport.remote_remove(
            host_alias="host", remote_path="/srv/jobs/job-1", platform=platform,
        )
    assert remote.call_count == 4
    assert remote.call_args_list[-1].kwargs["args"] == ["/srv/jobs/job-1"]


def test_posix_cleanup_still_refuses_shallow_target():
    with pytest.raises(SealError, match="unsafe shallow"):
        transport.remote_remove(host_alias="host", remote_path="/srv", platform="linux")


@pytest.mark.parametrize("platform", ["linux", "macos"])
def test_submit_lifecycle_propagates_platform_to_every_remote_boundary(tmp_path, platform):
    entrypoint = tmp_path / "job.py"
    entrypoint.write_text("pass\n")
    seal = tmp_path / "job-platform.tar.gz"
    seal.write_bytes(b"seal")
    manifest = SealedManifest(
        job_id=f"job-submit-{platform}",
        host=HostSpec("worker", "/srv/offload", platform=platform),
        blobs=[SealedBlob("entrypoint", str(entrypoint), "code/job.py")],
        entrypoint_rel="code/job.py",
        result=ResultSpec(local_dir=str(tmp_path / "result")),
    )
    terminal = {"phase": "exited", "exit_code": 0, "elapsed_s": 0.1}
    with mock.patch.object(submit, "build_seal", return_value=seal), \
         mock.patch.object(submit, "push_seal", return_value="/srv/offload/job.tar.gz") as push, \
         mock.patch.object(submit, "launch", return_value={
             "workdir": "/srv/offload/job-submit", "status_path": "/srv/offload/job-submit/status.json"
         }), \
         mock.patch.object(submit, "read_remote_status", return_value=terminal) as status, \
         mock.patch.object(submit, "fetch_and_unpack", return_value={"n_files": 1}), \
         mock.patch.object(submit, "remote_remove") as remove:
        result = submit.submit_one(
            manifest, bundle_out_dir=tmp_path / "bundles", poll_interval_s=0,
        )
    assert result["status"] == terminal
    assert push.call_args.kwargs["platform"] == platform
    assert status.call_args.kwargs["platform"] == platform
    assert remove.call_count == 2
    assert all(call.kwargs["platform"] == platform for call in remove.call_args_list)
