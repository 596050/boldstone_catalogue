"""Tests for the retry + idempotency layer over the remote transport.

These tests do NOT touch a real remote — they monkey-patch the bottom
``remote_run`` and ``subprocess.run`` callers to simulate flaky SSH and
already-extracted workdirs.
"""
from __future__ import annotations

import pathlib
import subprocess
import sys
import unittest
from unittest import mock

# Allow running with: python -m unittest v2.tests.test_retry_idempotency
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent))

from v2 import transport, launcher  # noqa: E402
from v2.manifest import SealError  # noqa: E402


def _cp(rc: int, stdout: str = "", stderr: str = "") -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=[], returncode=rc, stdout=stdout, stderr=stderr)


class TestIsTransientSshFailure(unittest.TestCase):
    def test_rc_255_is_transient(self):
        self.assertTrue(transport._is_transient_ssh_failure(255, ""))

    def test_rc_1_with_command_error_is_not_transient(self):
        # rc=1 from PowerShell error — caller should NOT retry this.
        self.assertFalse(transport._is_transient_ssh_failure(1, "ItemNotFoundException"))

    def test_connection_reset_stderr_is_transient(self):
        self.assertTrue(transport._is_transient_ssh_failure(0, "Connection reset by peer"))
        self.assertTrue(transport._is_transient_ssh_failure(1, "Connection timed out\nfoo"))

    def test_kex_failure_is_transient(self):
        # Real-world mux race signature
        self.assertTrue(transport._is_transient_ssh_failure(255, "kex_exchange_identification: ..."))

    def test_zero_rc_clean_stderr_is_not_transient(self):
        self.assertFalse(transport._is_transient_ssh_failure(0, ""))


class TestRemoteRunRetrying(unittest.TestCase):
    """Verify the retry policy in remote_run_retrying without touching ssh."""

    def setUp(self):
        # Patch the time.sleep used inside _retrying so tests don't actually
        # wait for the exponential backoff (1s + 2s + 4s).
        self._sleep_patch = mock.patch.object(transport.time, "sleep")
        self._sleep_patch.start()

    def tearDown(self):
        self._sleep_patch.stop()

    def test_succeeds_on_first_try(self):
        with mock.patch.object(transport, "remote_run", return_value=_cp(0, "ok")) as rr:
            r = transport.remote_run_retrying(
                host_alias="fake", powershell_script="$x=1", label="t"
            )
        self.assertEqual(r.returncode, 0)
        self.assertEqual(rr.call_count, 1)

    def test_retries_then_succeeds_on_rc_255(self):
        # First two: rc=255 (ssh exit). Third: success.
        seq = [_cp(255, "", "Connection reset"), _cp(255, "", "ssh: connect to host"), _cp(0, "ok")]
        with mock.patch.object(transport, "remote_run", side_effect=seq) as rr:
            r = transport.remote_run_retrying(
                host_alias="fake", powershell_script="$x=1", label="t"
            )
        self.assertEqual(r.returncode, 0)
        self.assertEqual(rr.call_count, 3)

    def test_retries_on_timeout_then_succeeds(self):
        seq = [
            subprocess.TimeoutExpired(cmd="ssh", timeout=30),
            _cp(0, "ok"),
        ]
        with mock.patch.object(transport, "remote_run", side_effect=seq) as rr:
            r = transport.remote_run_retrying(
                host_alias="fake", powershell_script="$x=1", label="t",
            )
        self.assertEqual(r.returncode, 0)
        self.assertEqual(rr.call_count, 2)

    def test_does_not_retry_real_command_error(self):
        # rc=1 with non-transient stderr → return as-is, no retry.
        cp = _cp(1, "", "ItemNotFoundException: file not found")
        with mock.patch.object(transport, "remote_run", return_value=cp) as rr:
            r = transport.remote_run_retrying(
                host_alias="fake", powershell_script="$x=1", label="t",
            )
        self.assertEqual(r.returncode, 1)
        self.assertEqual(rr.call_count, 1, "should NOT retry a real command error")

    def test_raises_after_max_transient_failures(self):
        # All 3 attempts fail with transient errors.
        cp = _cp(255, "", "kex_exchange_identification: read: Connection reset")
        with mock.patch.object(transport, "remote_run", return_value=cp):
            with self.assertRaises(SealError) as ctx:
                transport.remote_run_retrying(
                    host_alias="fake", powershell_script="$x=1", label="t-final",
                )
        self.assertIn("t-final", str(ctx.exception))
        self.assertIn("transport errors", str(ctx.exception))


class TestRemotePathExists(unittest.TestCase):
    def test_yes(self):
        with mock.patch.object(transport, "remote_run_retrying",
                               return_value=_cp(0, "YES\r\n")):
            self.assertTrue(transport.remote_path_exists("fake", "C:/x"))

    def test_no(self):
        with mock.patch.object(transport, "remote_run_retrying",
                               return_value=_cp(0, "NO\r\n")):
            self.assertFalse(transport.remote_path_exists("fake", "C:/x"))

    def test_treats_transport_failure_as_missing(self):
        # If the network is so dead we can't even check, the safe answer is
        # "doesn't exist" — caller will then push/extract, which is wasteful
        # but never destructive.
        with mock.patch.object(transport, "remote_run_retrying",
                               side_effect=SealError("net dead")):
            self.assertFalse(transport.remote_path_exists("fake", "C:/x"))


class TestRemoteFileSize(unittest.TestCase):
    def test_returns_int(self):
        with mock.patch.object(transport, "remote_run_retrying",
                               return_value=_cp(0, "2278622118\r\n")):
            self.assertEqual(transport.remote_file_size("fake", "C:/x"), 2278622118)

    def test_returns_none_when_missing(self):
        # PowerShell snippet returns empty string for missing files.
        with mock.patch.object(transport, "remote_run_retrying",
                               return_value=_cp(0, "")):
            self.assertIsNone(transport.remote_file_size("fake", "C:/x"))

    def test_returns_none_on_garbage(self):
        with mock.patch.object(transport, "remote_run_retrying",
                               return_value=_cp(0, "not a number")):
            self.assertIsNone(transport.remote_file_size("fake", "C:/x"))


class TestPushSealIdempotency(unittest.TestCase):
    """Verify push_seal skips the rsync when the remote already has the
    same-size file, and pushes when sizes differ or remote is missing."""

    def setUp(self):
        import tempfile
        self.tmpdir = pathlib.Path(tempfile.mkdtemp(prefix="v2_t_"))
        self.seal = self.tmpdir / "v2-job-foo.tar.gz"
        self.seal.write_bytes(b"x" * 1024)
        self._hash_patch = mock.patch.object(transport, "remote_file_sha256",
                                            return_value=transport.sha256_of_file(self.seal))
        self._hash_patch.start()
        self._sleep_patch = mock.patch.object(transport.time, "sleep")
        self._sleep_patch.start()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)
        self._sleep_patch.stop()

        self._hash_patch.stop()

    def test_skips_when_remote_size_and_hash_match(self):
        with mock.patch.object(transport, "remote_run_retrying",
                               return_value=_cp(0, "")) as rr, \
             mock.patch.object(transport, "remote_file_size",
                               return_value=1024) as rfs, \
             mock.patch.object(transport, "_retrying") as rsync_call:
            out = transport.push_seal(
                seal_path_local=self.seal,
                host_alias="fake",
                remote_workdir="C:/sealed/jobs",
            )
        self.assertEqual(out, "C:/sealed/jobs/v2-job-foo.tar.gz")
        rfs.assert_called_once()
        rsync_call.assert_not_called()  # only size AND content hash allow reuse
        # mkdir still happens (idempotent + cheap)
        self.assertEqual(rr.call_count, 1)

    def test_pushes_when_remote_missing(self):
        with mock.patch.object(transport, "remote_run_retrying",
                               return_value=_cp(0, "")), \
             mock.patch.object(transport, "remote_file_size", return_value=None), \
             mock.patch.object(transport, "_retrying") as rsync_call:
            transport.push_seal(
                seal_path_local=self.seal,
                host_alias="fake",
                remote_workdir="C:/sealed/jobs",
            )
        rsync_call.assert_called_once()

    def test_pushes_when_size_differs(self):
        # Different size = different content (eg. partial prior upload).
        with mock.patch.object(transport, "remote_run_retrying",
                               return_value=_cp(0, "")), \
             mock.patch.object(transport, "remote_file_size", return_value=512), \
             mock.patch.object(transport, "_retrying") as rsync_call:
            transport.push_seal(
                seal_path_local=self.seal,
                host_alias="fake",
                remote_workdir="C:/sealed/jobs",
            )
        rsync_call.assert_called_once()

    def test_force_pushes_even_when_size_matches(self):
        with mock.patch.object(transport, "remote_run_retrying",
                               return_value=_cp(0, "")), \
             mock.patch.object(transport, "remote_file_size", return_value=1024), \
             mock.patch.object(transport, "_retrying") as rsync_call:
            transport.push_seal(
                seal_path_local=self.seal,
                host_alias="fake",
                remote_workdir="C:/sealed/jobs",
                force=True,
            )
        rsync_call.assert_called_once()


class TestExtractSealRemoteIdempotency(unittest.TestCase):
    def test_skips_only_after_verified_marker_acknowledgement(self):
        with mock.patch.object(launcher, "remote_path_exists",
                               return_value=True) as rpe, \
             mock.patch.object(launcher, "remote_run_retrying", return_value=_cp(0, "REUSED")) as rr:
            ran = launcher.extract_seal_remote(
                "fake",
                seal_remote_path="C:/sealed/jobs/foo.tar.gz",
                workdir="C:/sealed/jobs/foo",
                archive_format="tar.gz",
                expected_sha256="a" * 64,
            )
        self.assertFalse(ran, "extract should report it was skipped")
        rpe.assert_not_called()
        rr.assert_called_once()  # hash/marker checked on every attempt

    def test_extracts_when_manifest_missing(self):
        with mock.patch.object(launcher, "remote_path_exists",
                               return_value=False), \
             mock.patch.object(launcher, "remote_run_retrying",
                               return_value=_cp(0, "EXTRACTED")) as rr:
            ran = launcher.extract_seal_remote(
                "fake",
                seal_remote_path="C:/sealed/jobs/foo.tar.gz",
                workdir="C:/sealed/jobs/foo",
                archive_format="tar.gz",
                expected_sha256="a" * 64,
            )
        self.assertTrue(ran)
        rr.assert_called_once()

    def test_force_still_requires_verified_extraction(self):
        with mock.patch.object(launcher, "remote_path_exists",
                               return_value=True) as rpe, \
             mock.patch.object(launcher, "remote_run_retrying",
                               return_value=_cp(0, "EXTRACTED")) as rr:
            ran = launcher.extract_seal_remote(
                "fake",
                seal_remote_path="C:/sealed/jobs/foo.tar.gz",
                workdir="C:/sealed/jobs/foo",
                archive_format="tar.gz",
                expected_sha256="a" * 64,
                force=True,
            )
        self.assertTrue(ran)
        rpe.assert_not_called()  # force skips the check
        rr.assert_called_once()


class TestSpawnBootstrapIdempotency(unittest.TestCase):
    def test_skips_when_status_already_present(self):
        # If status.json exists, a runner has been (or is being) launched
        # already. Spawning a SECOND runner would race the first one.
        with mock.patch.object(launcher, "remote_path_exists",
                               return_value=True) as rpe, \
             mock.patch.object(launcher, "remote_run_retrying") as rr:
            pid = launcher.spawn_bootstrap("fake", "C:/sealed/jobs/foo")
        self.assertIsNone(pid)
        rpe.assert_called_once()
        rr.assert_not_called()  # critical: do NOT spawn

    def test_spawns_when_status_absent(self):
        with mock.patch.object(launcher, "remote_path_exists",
                               return_value=False), \
             mock.patch.object(launcher, "remote_run_retrying",
                               return_value=_cp(0, "PID=12345\r\n")) as rr:
            pid = launcher.spawn_bootstrap("fake", "C:/sealed/jobs/foo")
        self.assertEqual(pid, 12345)
        rr.assert_called_once()

    def test_force_spawns_even_with_status(self):
        with mock.patch.object(launcher, "remote_path_exists",
                               return_value=True) as rpe, \
             mock.patch.object(launcher, "remote_run_retrying",
                               return_value=_cp(0, "PID=99999\r\n")) as rr:
            pid = launcher.spawn_bootstrap("fake", "C:/sealed/jobs/foo", force=True)
        self.assertEqual(pid, 99999)
        rpe.assert_not_called()
        rr.assert_called_once()


if __name__ == "__main__":
    unittest.main()
