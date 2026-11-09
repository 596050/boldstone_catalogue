"""Real local Restic round trips plus isolated Hetzner/SSH protocol tests.

Run: python3 -m unittest discover -s utils/external_storage/hetzner/tests -v
No credentials, external drive, Hetzner account or paid resources are used.
"""

import base64
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
from unittest.mock import Mock, patch

SCRIPT = Path(__file__).resolve().parents[1] / "storage_box.py"
spec = importlib.util.spec_from_file_location("storage_box", SCRIPT)
sb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sb)


class Temporary(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="storagebox tests ")
        self.root = Path(self.tmp.name).resolve()
        self.addCleanup(self.tmp.cleanup)
        self.config = self.root / "configuration with spaces"
        self.profile = sb.Profile(self.config / "trial")

    def cli(self, *args, ok=True, env=None):
        result = subprocess.run([sys.executable, str(SCRIPT), "--config-dir", str(self.config),
                                 "--profile", "trial", *map(str, args)],
                                capture_output=True, text=True, timeout=90, env=env)
        if ok:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        return result


@unittest.skipUnless(shutil.which("restic"), "Install Restic to run real backup/recovery tests")
class ResticTests(Temporary):
    def setUp(self):
        super().setUp()
        self.archive = self.root / "encrypted repository"
        self.profile.data = {"schema": 1, "repository": str(self.archive),
                             "password_file": "restic-password"}
        sb.private_write(self.profile.path("password_file"), "synthetic-test-secret\n")
        self.profile.save()
        env = {k: v for k, v in os.environ.items() if not k.startswith("RESTIC_")}
        env.update(RESTIC_REPOSITORY=str(self.archive),
                   RESTIC_PASSWORD_FILE=str(self.profile.path("password_file")))
        init = subprocess.run(["restic", "--no-cache", "init"], env=env, capture_output=True, text=True)
        self.assertEqual(init.returncode, 0, init.stderr)
        self.repo = sb.Repository(self.profile)
        self.repo.bind()
        self.source = self.root / "raw data ü"
        self.source.mkdir()

    def completed(self):
        return self.repo.snapshots(sb.COMPLETE)

    def test_completion_waits_for_another_shared_repository_lock(self):
        (self.source / "price.csv").write_bytes(b"price,42\n")
        held = subprocess.Popen(self.repo.base + ["backup", "--stdin", "--stdin-filename", "held-reader"],
                                env=self.repo.env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        held.stdin.write(b"synthetic lock-holder contents\n")
        held.stdin.flush()
        uploader = None
        try:
            deadline = time.monotonic() + 20
            while not list((self.archive / "locks").iterdir()):
                self.assertIsNone(held.poll())
                self.assertLess(time.monotonic(), deadline)
                time.sleep(0.1)
            uploader = subprocess.Popen([sys.executable, str(SCRIPT), "--config-dir", str(self.config),
                "--profile", "trial", "upload", str(self.source), "--group", "lock-regression"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            deadline = time.monotonic() + 30
            while not list((self.archive / "snapshots").iterdir()):
                self.assertIsNone(uploader.poll())
                self.assertLess(time.monotonic(), deadline)
                time.sleep(0.1)
            time.sleep(3)
            self.assertIsNone(uploader.poll(), "Completion should wait while the other shared lock is held")
            held.stdin.close()
            self.assertEqual(held.wait(timeout=30), 0, held.stderr.read().decode())
            stdout, stderr = uploader.communicate(timeout=45)
            self.assertEqual(uploader.returncode, 0, stdout + stderr)
            self.assertEqual(len(self.completed()), 1)
        finally:
            for process in (held, uploader):
                if process is not None:
                    if process.poll() is None:
                        process.terminate()
                        process.wait(timeout=10)
                    for pipe in (process.stdin, process.stdout, process.stderr):
                        if pipe is not None and not pipe.closed:
                            pipe.close()

    def test_versions_selective_restore_dedup_resume_and_full_check(self):
        original = b"raw price,2026-09-14,123.45\n"
        data = self.source / "prices.csv"
        data.write_bytes(original)
        stamp = data.stat()
        (self.source / "empty").write_bytes(b"")
        (self.source / ".hidden").write_bytes(b"hidden bytes\x00\xff")
        (self.source / "link").symlink_to("prices.csv")
        nested = self.source / "macro releases"
        nested.mkdir()
        (nested / "revisions.json").write_bytes(b'{"vintage":"2026-09-14","value":3.2}')
        loose = self.root / "individual file.bin"
        loose.write_bytes(bytes(range(256)))
        self.cli("upload", self.source, loose, "--group", "raw")
        first = self.completed()[0]["id"]
        packs = set(self.archive.glob("data/*/*"))
        # Same byte count and mtime: --force must still observe the changed content.
        data.write_bytes(original.replace(b"123.45", b"987.65"))
        os.utime(data, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
        self.cli("upload", self.source, loose, "--group", "raw")
        second = self.repo.resolve("latest", "raw")
        self.assertNotEqual(first, second)
        self.assertTrue(packs.issubset(set(self.archive.glob("data/*/*"))))
        def data_blobs():
            return {line for line in self.repo.successful(["list", "blobs"], capture=True).splitlines()
                    if line.startswith("data ")}
        before = data_blobs()
        self.assertTrue(before)
        self.cli("upload", self.source, loose, "--group", "raw")
        self.assertEqual(before, data_blobs(), "Unchanged file content should deduplicate, independently of directory metadata")
        before_snapshots = len(self.completed())
        self.cli("upload", self.source, loose, "--group", "raw", "--dry-run")
        self.assertEqual(len(self.completed()), before_snapshots)
        self.assertIn("prices.csv", self.cli("ls", first).stdout)
        # Remove ONLY disposable synthetic originals before recovering them.
        shutil.rmtree(self.source)
        loose.unlink()
        target = self.root / "recovered old"
        self.cli("recover", first, "--target", target, "--dry-run")
        self.assertFalse(target.exists())
        self.cli("recover", first, "--target", target)
        recovered_root = target / self.source.relative_to(self.source.anchor)
        self.assertEqual((recovered_root / "prices.csv").read_bytes(), original)
        self.assertEqual((recovered_root / ".hidden").read_bytes(), b"hidden bytes\x00\xff")
        self.assertEqual((recovered_root / "empty").stat().st_size, 0)
        self.assertTrue((recovered_root / "link").is_symlink())
        self.assertEqual((target / loose.relative_to(loose.anchor)).read_bytes(), bytes(range(256)))
        self.cli("recover", first, "--target", target, ok=False)
        # Resume repairs damaged restored bytes, despite an already completed receipt.
        (recovered_root / "prices.csv").write_bytes(b"broken")
        self.cli("recover", first, "--target", target, "--resume")
        self.assertEqual((recovered_root / "prices.csv").read_bytes(), original)
        self.cli("recover", second, "--target", target, "--resume", ok=False)
        flat = self.root / "recovered subtree"
        self.cli("recover", second, "--target", flat, "--subtree", self.source,
                 "--include", "/prices.csv")
        self.assertEqual((flat / "prices.csv").read_bytes(), original.replace(b"123.45", b"987.65"))
        self.assertEqual(set(p.name for p in flat.iterdir()), {"prices.csv"})
        self.cli("verify", "--read-data")
        for file in self.profile.directory.rglob("*.json"):
            self.assertNotIn("synthetic-test-secret", file.read_text())
        if os.name != "nt":
            self.assertEqual(stat.S_IMODE(self.profile.path("password_file").stat().st_mode), 0o600)

    def test_real_incomplete_backup_is_retained_and_never_selected(self):
        if os.name == "nt" or (hasattr(os, "geteuid") and os.geteuid() == 0):
            self.skipTest("Unreadable file test requires a non-root POSIX user")
        (self.source / "good").write_bytes(b"good")
        bad = self.source / "unreadable"
        bad.write_bytes(b"temporarily unreadable")
        bad.chmod(0)
        try:
            result = self.cli("upload", self.source, ok=False)
        finally:
            bad.chmod(0o600)
        self.assertIn("exit 3", result.stderr)
        self.assertEqual(self.completed(), [])
        partial = self.repo.snapshots(sb.PENDING)
        self.assertEqual(len(partial), 1)
        self.cli("recover", "latest", "--target", self.root / "must not restore", ok=False)
        self.cli("upload", self.source)
        self.assertEqual(len(self.completed()), 1)
        self.assertEqual(len(self.repo.snapshots()), 2)

    def test_wrong_password_wrong_identity_and_inherited_environment(self):
        (self.source / "file").write_bytes(b"data")
        env = dict(os.environ, RESTIC_REPOSITORY="/must/not/be/used", RESTIC_PASSWORD="wrong",
                   RESTIC_PASSWORD_COMMAND="false", RESTIC_REPOSITORY_FILE="/no/such/file")
        self.cli("upload", self.source, env=env)
        self.profile.data["repository_id"] = "0" * 64
        self.profile.save()
        self.assertIn("identity differs", self.cli("status", ok=False).stderr)
        self.profile.data.pop("repository_id")
        self.profile.save()
        sb.private_write(self.profile.path("password_file"), "wrong password\n")
        self.assertIn("exit 12", self.cli("status", ok=False).stderr)

    def test_corrupt_remote_pack_is_detected(self):
        (self.source / "random.bin").write_bytes(os.urandom(65536))
        self.cli("upload", self.source)
        pack = next(self.archive.glob("data/*/*"))
        pack.chmod(0o600)
        with pack.open("r+b") as stream:
            byte = stream.read(1)
            stream.seek(0)
            stream.write(bytes([byte[0] ^ 0xFF]))
        self.cli("verify", "--read-data", ok=False)

    def test_missing_sources_secret_overlap_mount_and_restore_guards(self):
        self.cli("upload", self.root / "absent", ok=False)
        self.cli("upload", self.root, ok=False)
        self.cli("upload", self.source, "--require-mount", self.root / "unmounted", ok=False)
        (self.source / "file").write_text("data")
        self.cli("upload", self.source)
        target = self.root / "nonempty"
        target.mkdir()
        (target / "existing").write_text("keep me")
        self.cli("recover", "--target", target, ok=False)
        self.assertEqual((target / "existing").read_text(), "keep me")
        alias = self.root / "alias"
        alias.symlink_to(target, target_is_directory=True)
        self.cli("recover", "--target", alias / "new", ok=False)
        self.cli("recover", "--target", self.profile.directory / "restore", ok=False)
        missing = self.root / "unmatched selection"
        self.cli("recover", "--target", missing, "--include", "/no-such-path", "--dry-run", ok=False)
        self.assertFalse(missing.exists())
        self.cli("recover", "--target", missing, "--include", "/no-such-path", ok=False)


class ProtocolTests(Temporary):
    def args(self, *args):
        return sb.parser().parse_args(list(args))

    @unittest.skipUnless(shutil.which("restic"), "Restic is required for option-parser regression")
    def test_real_restic_accepts_remote_ssh_options_with_nested_quotes(self):
        profile = sb.Profile(self.root / 'configuration, with "quotes"' / "remote")
        profile.data = {"schema": 1, "repository": "sftp://u123@u123.your-storagebox.de:23/raw-v1",
                        "host": "u123.your-storagebox.de", "username": "u123",
                        "password_file": "restic-password", "identity_file": "id_ed25519",
                        "known_hosts_file": "known_hosts"}
        sb.private_write(profile.path("password_file"), "synthetic-parser-test-password\n")
        repo = sb.Repository(profile)
        # Exercise the installed Restic flag parser without making a connection.
        result = repo.run(["--help"], capture=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        encoded = repo.base[repo.base.index("-o") + 1]
        legacy = next(sb.csv.reader([encoded]))[0]
        broken = list(repo.base)
        broken[broken.index("-o") + 1] = legacy
        result = subprocess.run(broken + ["--help"], env=repo.env, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0, "Regression fixture must reproduce the original parser failure")

    def test_preview_has_no_local_or_remote_side_effects(self):
        api = Mock()
        with contextlib.redirect_stdout(io.StringIO()):
            sb.setup(self.profile, self.args("setup"), api)
        self.assertFalse(self.config.exists())
        self.assertEqual(api.mock_calls, [])

    def test_api_pagination_and_no_retry_of_ambiguous_order(self):
        api = sb.Hetzner("sensitive-token")
        api.request = Mock(side_effect=[
            {"storage_boxes": [{"id": 1}], "meta": {"pagination": {"next_page": 2}}},
            {"storage_boxes": [{"id": 2}], "meta": {"pagination": {"next_page": None}}}])
        self.assertEqual(api.all("storage_boxes"), [{"id": 1}, {"id": 2}])
        api = sb.Hetzner("sensitive-token")
        api.opener.open = Mock(side_effect=urllib.error.URLError("secret-from-response"))
        with self.assertRaises(sb.Error) as raised:
            api.request("POST", "/storage_boxes", {"password": "secret-password"})
        self.assertEqual(api.opener.open.call_count, 1)
        self.assertNotIn("secret", str(raised.exception))
        self.assertNotIn("sensitive-token", str(raised.exception))
        self.assertIsNone(sb.NoRedirect().redirect_request(None, None, 302, "", {}, "https://other.example"))

    def test_create_payload_and_retry_reuses_exact_box(self):
        api = Mock()
        box = {"id": 123, "name": "market-data", "storage_box_type": {"name": "bx21"},
               "location": {"name": "fsn1"}, "status": "active", "server": "u123.your-storagebox.de",
               "username": "u123", "access_settings": {"ssh_enabled": True, "reachable_externally": True}}
        plan = {"name": "bx21", "size": 5_000_000_000_000,
                "prices": [{"location": "fsn1", "price_monthly": {"net": "10.90"}}]}
        api.all.side_effect = lambda resource, **kw: [] if resource == "storage_boxes" else [plan]
        calls = []

        def request(method, path, body=None):
            calls.append((method, path, body))
            if method == "POST":
                return {"storage_box": box, "action": {"id": 4, "status": "running"}}
            return {"storage_box": box}

        api.request.side_effect = request
        # Real key generation; all network and Restic remote access replaced in this test.
        with patch.object(sb, "pin_host"), patch.object(sb.Repository, "bind") as bind, contextlib.redirect_stdout(io.StringIO()):
            def bind_id(**kwargs):
                self.profile.data["repository_id"] = "1" * 64
                self.profile.save()
            bind.side_effect = bind_id
            sb.setup(self.profile, self.args("setup", "--apply"), api)
            sb.setup(self.profile, self.args("setup", "--apply"), api)
        orders = [body for method, path, body in calls if method == "POST" and path == "/storage_boxes"]
        self.assertEqual(len(orders), 1)
        self.assertGreaterEqual(len(orders[0]["password"]), 12)
        self.assertTrue(orders[0]["ssh_keys"][0].startswith("ssh-ed25519 "))
        self.assertEqual(orders[0]["storage_box_type"], "bx21")
        self.assertTrue(orders[0]["access_settings"]["ssh_enabled"])
        self.assertNotIn(orders[0]["password"], self.profile.file.read_text())
        self.assertEqual(self.profile.data["box_id"], 123)

    def test_mismatched_existing_box_never_orders(self):
        api = Mock()
        api.all.return_value = [{"id": 77, "name": "market-data", "storage_box_type": {"name": "bx11"},
                                 "location": {"name": "fsn1"}}]
        with self.assertRaisesRegex(sb.Error, "differs"):
            sb.setup(self.profile, self.args("setup", "--apply"), api)
        api.request.assert_not_called()

    def test_host_fingerprint_is_verified_before_writing_known_hosts(self):
        self.profile.data = {"host": "u123.your-storagebox.de", "known_hosts_file": "known_hosts"}
        key = base64.b64encode(b"a synthetic public wire key").decode()
        scanned = subprocess.CompletedProcess([], 0, stdout=f"[u123.your-storagebox.de]:23 ssh-ed25519 {key}\n", stderr="")
        with patch.object(sb.subprocess, "run", return_value=scanned):
            with self.assertRaisesRegex(sb.Error, "fingerprint"):
                sb.pin_host(self.profile)
            self.assertFalse(self.profile.path("known_hosts_file").exists())
            fingerprint = "SHA256:" + base64.b64encode(hashlib.sha256(b"a synthetic public wire key").digest()).decode().rstrip("=")
            with patch.object(sb, "HOST_FINGERPRINT", fingerprint):
                sb.pin_host(self.profile)
            self.assertIn("[u123.your-storagebox.de]:23", self.profile.path("known_hosts_file").read_text())

    def test_lock_released_on_exception(self):
        with self.assertRaises(RuntimeError):
            with sb.locked(self.profile.directory):
                with self.assertRaises(sb.Error):
                    with sb.locked(self.profile.directory):
                        pass
                raise RuntimeError("simulated crash")
        with sb.locked(self.profile.directory):
            pass

    def test_connect_retry_preserves_the_explicit_repository_identity(self):
        key, password = self.root / "existing-key", self.root / "existing-password"
        key.write_text("synthetic-private-key")
        password.write_text("synthetic-repository-password")
        arguments = ["connect", "--host", "u123.your-storagebox.de", "--username", "u123",
                     "--identity-file", str(key), "--password-file", str(password)]
        with patch.object(sb, "pin_host", side_effect=sb.Error("temporary network outage")):
            with self.assertRaises(sb.Error):
                sb.connect(self.profile, self.args(*arguments))
        self.assertIsNone(self.profile.data["repository_id"])
        expected = "c" * 64
        with patch.object(sb, "pin_host"), patch.object(sb.Repository, "bind"), contextlib.redirect_stdout(io.StringIO()):
            sb.connect(self.profile, self.args(*arguments, "--repository-id", expected))
        self.assertEqual(self.profile.data["repository_id"], expected)

    def test_action_error_and_saved_box_id_survive_failed_setup(self):
        api = sb.Hetzner("synthetic-token")
        with self.assertRaisesRegex(sb.Error, "did not succeed"):
            api.wait({"id": 7, "status": "error"})
        api = Mock()
        api.all.side_effect = lambda resource, **kw: [] if resource == "storage_boxes" else [
            {"name": "bx21", "size": 5_000_000_000_000, "prices": [{"location": "fsn1"}]}]
        api.request.return_value = {"storage_box": {"id": 321}, "action": {"id": 8, "status": "running"}}
        api.wait.side_effect = sb.Error("temporary provisioning failure")
        with contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(sb.Error, "provisioning"):
                sb.setup(self.profile, self.args("setup", "--apply"), api)
        self.assertEqual(sb.Profile(self.profile.directory).data["box_id"], 321)


@unittest.skipUnless(shutil.which("restic") and Path("/usr/libexec/sftp-server").is_file(),
                     "Local OpenSSH SFTP server required for transport test")
class SFTPTests(Temporary):
    def test_real_sftp_relative_repository_round_trip_with_spaces(self):
        remote_home = self.root / "SFTP home with spaces"
        remote_home.mkdir()
        self.profile.data = {"schema": 1, "repository": "sftp://test@unused.invalid:23/raw-v1",
                             "password_file": "restic-password"}
        sb.private_write(self.profile.path("password_file"), "synthetic-sftp-secret\n")
        self.profile.save()
        repo = sb.Repository(self.profile)
        # Run the actual OpenSSH SFTP server over local pipes; no SSH/network endpoint.
        repo.base += ["-o", "sftp.command=" + shlex.join(["/usr/libexec/sftp-server", "-d", str(remote_home)])]
        with contextlib.redirect_stdout(io.StringIO()):
            repo.bind(initialize=True)
            self.assertTrue((remote_home / "raw-v1" / "config").is_file())
            source = self.root / "SFTP source"
            source.mkdir()
            original = os.urandom(8192)
            (source / "raw.bin").write_bytes(original)
            sb.upload(repo, sb.parser().parse_args(["upload", str(source)]))
            snapshot = repo.resolve("latest")
            shutil.rmtree(source)
            target = self.root / "SFTP recovered"
            sb.recover(repo, sb.parser().parse_args(["recover", snapshot, "--subtree", str(source), "--target", str(target)]))
            self.assertEqual((target / "raw.bin").read_bytes(), original)
            repo.successful(["check", "--read-data"])


if __name__ == "__main__":
    unittest.main()
