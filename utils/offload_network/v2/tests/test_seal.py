"""End-to-end seal build/verify/extract test.

Does not require any remote — purely local round-trip.
"""
from __future__ import annotations

import json
import pathlib
import sys
import tarfile
import tempfile
import unittest

# Allow running with: python -m unittest v2.tests.test_seal
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent))

from v2.manifest import (  # noqa: E402
    SealedManifest, SealedBlob, HostSpec, ResultSpec, SealError,
)
from v2.seal import build_seal, verify_seal, extract_seal  # noqa: E402


def _make_test_blobs(tmp: pathlib.Path) -> list[SealedBlob]:
    """Create a tiny code blob (Python script) and a fake cache blob."""
    code_dir = tmp / "code"
    code_dir.mkdir()
    (code_dir / "driver.py").write_text(
        'import json, sys, pathlib\n'
        'p = pathlib.Path.cwd() / "result.json"\n'
        'p.write_text(json.dumps({"hello": "from sealed", "argv": sys.argv}))\n'
    )
    cache = tmp / "cache.bin"
    cache.write_bytes(b"\x42" * 4096)  # 4 KB dummy cache
    return [
        SealedBlob(name="driver", local_src=str(code_dir / "driver.py"), rel_path="driver.py"),
        SealedBlob(name="cache",  local_src=str(cache), rel_path="data/cache.bin"),
    ]


class TestManifest(unittest.TestCase):
    def test_validate_ok(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = pathlib.Path(td)
            blobs = _make_test_blobs(tmp)
            m = SealedManifest(
                host=HostSpec(ssh_alias="fake", remote_workdir="C:/test"),
                blobs=blobs,
                entrypoint_rel="driver.py",
                result=ResultSpec(local_dir=str(tmp / "result")),
            )
            m.validate()  # should not raise
            self.assertTrue(m.job_id)

    def test_validate_bad_entrypoint(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = pathlib.Path(td)
            blobs = _make_test_blobs(tmp)
            m = SealedManifest(
                host=HostSpec(ssh_alias="fake", remote_workdir="C:/test"),
                blobs=blobs,
                entrypoint_rel="nonexistent.py",  # not declared as a blob
                result=ResultSpec(local_dir=str(tmp / "result")),
            )
            with self.assertRaises(SealError):
                m.validate()

    def test_json_roundtrip(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = pathlib.Path(td)
            blobs = _make_test_blobs(tmp)
            m = SealedManifest(
                host=HostSpec(ssh_alias="fake", remote_workdir="C:/test"),
                blobs=blobs,
                entrypoint_rel="driver.py",
                result=ResultSpec(local_dir=str(tmp / "result")),
            )
            s = m.to_json()
            m2 = SealedManifest.from_json(s)
            self.assertEqual(m.job_id, m2.job_id)
            self.assertEqual(m.entrypoint_rel, m2.entrypoint_rel)
            self.assertEqual(len(m.blobs), len(m2.blobs))


class TestSealRoundTrip(unittest.TestCase):
    def test_build_and_verify_targz(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = pathlib.Path(td)
            blobs = _make_test_blobs(tmp)
            m = SealedManifest(
                host=HostSpec(ssh_alias="fake", remote_workdir="C:/test"),
                blobs=blobs,
                entrypoint_rel="driver.py",
                result=ResultSpec(local_dir=str(tmp / "result")),
                archive_format="tar.gz",
            )
            out = tmp / "out"
            seal_path = build_seal(m, out_dir=out)
            self.assertTrue(seal_path.exists())
            self.assertTrue(seal_path.name.endswith(".tar.gz"))
            self.assertIsNotNone(m.seal_sha256)
            self.assertTrue(m.seal_size_bytes and m.seal_size_bytes > 0)
            # Every blob has a sha now
            for b in m.blobs:
                self.assertIsNotNone(b.sha256)
                self.assertIsNotNone(b.size_bytes)
            # Verify
            m_back = verify_seal(seal_path, expected_sha256=m.seal_sha256)
            self.assertEqual(m_back.job_id, m.job_id)
            for b1, b2 in zip(m.blobs, m_back.blobs):
                self.assertEqual(b1.sha256, b2.sha256)
                self.assertEqual(b1.size_bytes, b2.size_bytes)

    def test_extract_layout(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = pathlib.Path(td)
            blobs = _make_test_blobs(tmp)
            m = SealedManifest(
                host=HostSpec(ssh_alias="fake", remote_workdir="C:/test"),
                blobs=blobs,
                entrypoint_rel="driver.py",
                result=ResultSpec(local_dir=str(tmp / "result")),
                archive_format="tar.gz",
            )
            out = tmp / "out"
            seal_path = build_seal(m, out_dir=out)
            extract_dir = tmp / "extracted"
            extract_seal(seal_path, extract_dir)
            # Required files present
            self.assertTrue((extract_dir / "manifest.json").is_file())
            self.assertTrue((extract_dir / "bootstrap.cmd").is_file())
            self.assertTrue((extract_dir / "runner.py").is_file())
            self.assertTrue((extract_dir / "blobs" / "driver.py").is_file())
            self.assertTrue((extract_dir / "blobs" / "data" / "cache.bin").is_file())
            # Manifest from disk matches
            disk_mani = json.loads((extract_dir / "manifest.json").read_text())
            self.assertEqual(disk_mani["job_id"], m.job_id)
            self.assertEqual(disk_mani["entrypoint_rel"], "driver.py")

    def test_seal_resists_tampering(self):
        """Modifying the seal bytes should be detectable via sha mismatch."""
        with tempfile.TemporaryDirectory() as td:
            tmp = pathlib.Path(td)
            blobs = _make_test_blobs(tmp)
            m = SealedManifest(
                host=HostSpec(ssh_alias="fake", remote_workdir="C:/test"),
                blobs=blobs,
                entrypoint_rel="driver.py",
                result=ResultSpec(local_dir=str(tmp / "result")),
                archive_format="tar.gz",
            )
            seal_path = build_seal(m, out_dir=tmp / "out")
            # Tamper one byte
            data = bytearray(seal_path.read_bytes())
            mid = len(data) // 2
            data[mid] ^= 0xFF
            seal_path.write_bytes(bytes(data))
            with self.assertRaises(SealError):
                verify_seal(seal_path, expected_sha256=m.seal_sha256)


class TestRunnerEndToEnd(unittest.TestCase):
    """Run runner.py against an extracted seal locally (no SSH).

    Verifies: extract → run entrypoint → produce result.json → pack
    result archive → final status.json with exit_code=0 and result
    archive path.
    """

    def test_local_run(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = pathlib.Path(td)
            blobs = _make_test_blobs(tmp)
            m = SealedManifest(
                host=HostSpec(ssh_alias="fake", remote_workdir="C:/test"),
                blobs=blobs,
                entrypoint_rel="driver.py",
                run_args=["arg1", "arg2"],
                result=ResultSpec(
                    local_dir=str(tmp / "result"),
                    include_patterns=["result.json", "status.json", "run.log"],
                ),
                archive_format="tar.gz",
            )
            seal_path = build_seal(m, out_dir=tmp / "out")
            extract_dir = tmp / "workdir"
            extract_seal(seal_path, extract_dir)
            # Run the runner from the extracted dir
            import subprocess
            r = subprocess.run(
                [sys.executable, str(extract_dir / "runner.py"),
                  str(extract_dir / "manifest.json")],
                capture_output=True, text=True, cwd=str(extract_dir),
            )
            status = json.loads((extract_dir / "status.json").read_text())
            self.assertEqual(status["phase"], "exited", msg=f"stderr={r.stderr}\nstdout={r.stdout}")
            self.assertEqual(status["exit_code"], 0)
            self.assertTrue(status["result_archive"])
            result_arc = pathlib.Path(status["result_archive"])
            self.assertTrue(result_arc.is_file())
            # Result archive should contain result.json (written by driver.py)
            with tarfile.open(str(result_arc), "r:gz") as t:
                names = t.getnames()
            self.assertIn("result.json", names)


if __name__ == "__main__":
    unittest.main()
