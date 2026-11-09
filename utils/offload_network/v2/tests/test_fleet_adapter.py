"""Tests for v2/fleet_adapter.py — the bridge between fleet.py `run` and
the v2 sealed-bundle transport.

The adapter has two interesting paths: (1) manifest construction from the
v1-style ``fleet run`` args, and (2) detached-spawn + state.json
registration. We unit-test (1) directly and (2) by mocking subprocess.Popen.
"""
from __future__ import annotations

import json
import pathlib
import sys
import unittest
from types import SimpleNamespace
from unittest import mock

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent))

from v2 import fleet_adapter  # noqa: E402
from v2.manifest import SealedManifest, ResultSpec, HostSpec  # noqa: E402


class TestBuildRandomWindowsManifest(unittest.TestCase):
    """The manifest must declare the right blobs / entrypoint / run-args
    so the driver receives exactly what the v1 ssh-launched pipeline
    would have received."""

    def setUp(self):
        import tempfile
        self.bundle_dir = pathlib.Path(tempfile.mkdtemp(prefix="v2_t_"))

    def tearDown(self):
        import shutil
        shutil.rmtree(self.bundle_dir, ignore_errors=True)

    def _build(self, **kw):
        defaults = dict(
            job_id=42,
            cohort="new10",
            host_alias="cdec",
            remote_workdir="C:/sealed/jobs",
            rsync_path="C:/msys64/usr/bin/rsync.exe",
            pipeline_args="--seed 1100 --windows-per-instrument 8",
            host_repo="C:/Users/kenne/Downloads/fleet-offload",
            host_results_root="C:/Users/kenne/Downloads/fleet-offload/c_emd/results",
            bundle_out_dir=self.bundle_dir,
        )
        defaults.update(kw)
        return fleet_adapter._build_random_windows_manifest(**defaults)

    def test_manifest_validates(self):
        m = self._build()
        m.validate()  # raises on missing/bad fields
        self.assertEqual(m.host.ssh_alias, "cdec")
        self.assertEqual(m.entrypoint_rel, "code/random_windows.py")

    def test_job_id_encodes_cohort_and_host(self):
        m = self._build()
        self.assertIn("rw", m.job_id)
        self.assertIn("new10", m.job_id)
        self.assertIn("cdec", m.job_id)
        self.assertIn("42", m.job_id)

    def test_blobs_include_required_packages(self):
        m = self._build()
        names = {b.name for b in m.blobs}
        # The driver imports from these — all must ship in the seal.
        # c_emd is split (root __init__.py + python/) so we skip the 15 GB
        # c_emd/results/ tree. See _standard_code_blobs in fleet_adapter.
        self.assertEqual(names, {
            "driver", "trading_common",
            "c_emd_root_init", "c_emd_python",
            "uoa_emd_lib", "uoa_emd_scripts",
        })

    def test_driver_blob_points_at_random_windows_py(self):
        m = self._build()
        driver = next(b for b in m.blobs if b.name == "driver")
        self.assertTrue(driver.local_src.endswith("v2/drivers/random_windows.py"))
        self.assertFalse(driver.is_dir)
        self.assertEqual(driver.rel_path, "code/random_windows.py")

    def test_code_blobs_are_dirs(self):
        m = self._build()
        # trading_common, c_emd_python, uoa_emd_lib bundle whole subtrees.
        # c_emd_root_init is the single c_emd/__init__.py file (NOT a dir).
        for name in ("trading_common", "c_emd_python", "uoa_emd_lib"):
            b = next(x for x in m.blobs if x.name == name)
            self.assertTrue(b.is_dir, f"{name} must be a dir blob")
        root_init = next(x for x in m.blobs if x.name == "c_emd_root_init")
        self.assertFalse(root_init.is_dir, "c_emd_root_init is a single file")

    def test_run_args_pass_cohort_and_out_dir(self):
        m = self._build()
        # The driver expects --cohort and --out-dir at minimum.
        self.assertIn("--cohort", m.run_args)
        self.assertIn("new10", m.run_args)
        self.assertIn("--out-dir", m.run_args)
        self.assertIn("outputs", m.run_args)

    def test_pipeline_args_string_is_passed_through(self):
        m = self._build(pipeline_args="--seed 99 --batches 2")
        self.assertIn("--pipeline-args", m.run_args)
        idx = m.run_args.index("--pipeline-args")
        # The next arg is the full unparsed pipeline-args string.
        self.assertIn("--seed 99", m.run_args[idx + 1])

    def test_empty_pipeline_args_omits_flag(self):
        m = self._build(pipeline_args="")
        self.assertNotIn("--pipeline-args", m.run_args)

    def test_host_results_root_is_passed_when_set(self):
        m = self._build(host_results_root="X:/somewhere/c_emd/results")
        self.assertIn("--host-results-root", m.run_args)
        idx = m.run_args.index("--host-results-root")
        self.assertEqual(m.run_args[idx + 1], "X:/somewhere/c_emd/results")

    def test_host_results_root_omitted_when_unset(self):
        m = self._build(host_results_root=None)
        self.assertNotIn("--host-results-root", m.run_args)

    def test_result_spec_pulls_outputs_and_logs(self):
        m = self._build()
        patterns = set(m.result.include_patterns)
        # The driver writes report.json into outputs/, but the runner
        # writes run.log + status.json + bootstrap.log at the workdir
        # root — all must be in the pull set.
        self.assertIn("outputs/**", patterns)
        self.assertIn("report.json", patterns)
        self.assertIn("status.json", patterns)
        self.assertIn("run.log", patterns)
        self.assertIn("bootstrap.log", patterns)

    def test_metadata_records_cohort_and_via(self):
        m = self._build()
        self.assertEqual(m.metadata["cohort"], "new10")
        self.assertEqual(m.metadata["via"], "v2")
        self.assertEqual(m.metadata["task_type"], "random_windows_pipeline_v2")
        self.assertEqual(m.metadata["fleet_job_id"], 42)

    def test_env_propagates_utf8(self):
        m = self._build()
        # The driver prints unicode (paths, etc.); without PYTHONIOENCODING
        # the bootstrap on Windows can mangle output.
        self.assertEqual(m.env.get("PYTHONIOENCODING"), "utf-8")


class TestSubmitRandomWindowsViaV2Dispatch(unittest.TestCase):
    """End-to-end of the adapter's spawn+state-record path with subprocess
    mocked. Verifies the contract with state.json (next_job_id increments,
    job recorded with via='v2', wrapper_pid set) without actually running
    a remote job."""

    def setUp(self):
        import tempfile
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix="v2_t_"))
        self.fake_state = {"next_job_id": 7, "jobs": []}

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _run(self):
        hosts = {
            "cdec": {
                "type": "ssh",
                "ssh_alias": "cdec",
                "repo": "C:/Users/kenne/Downloads/fleet-offload",
                "rsync_path": "C:/msys64/usr/bin/rsync.exe",
                "has_libemd": True,
                "cores": 24,
                "results_root": "c_emd/results",
            },
        }
        args = SimpleNamespace(
            cohort="new10",
            host="cdec",
            out_subdir=None,
            into="live_data",
            pipeline_args="--seed 1100",
        )
        # Patch the heavyweight bits: subprocess.Popen returns a fake
        # process with PID 99999. load_state / save_state hit the fake dict.
        fake_proc = mock.MagicMock()
        fake_proc.pid = 99999
        with mock.patch.object(fleet_adapter.subprocess, "Popen",
                               return_value=fake_proc) as popen, \
             mock.patch.object(fleet_adapter, "_bundle_state_for_fleet",
                               return_value=(self.tmp, self.tmp / "logs")), \
             mock.patch("fleet.load_state", return_value=self.fake_state), \
             mock.patch("fleet.save_state",
                        side_effect=lambda s: self.fake_state.update(s)) as save:
            (self.tmp / "logs").mkdir(parents=True, exist_ok=True)
            rc = fleet_adapter.submit_random_windows_via_v2(args, hosts)
            return rc, popen, save

    def test_returns_zero_on_successful_spawn(self):
        rc, _, _ = self._run()
        self.assertEqual(rc, 0)

    def test_increments_next_job_id(self):
        self._run()
        self.assertEqual(self.fake_state["next_job_id"], 8, "next_job_id must increment")

    def test_records_job_with_via_v2(self):
        self._run()
        self.assertEqual(len(self.fake_state["jobs"]), 1)
        j = self.fake_state["jobs"][0]
        self.assertEqual(j["id"], 7)
        self.assertEqual(j["cohort"], "new10")
        self.assertEqual(j["host"], "cdec")
        self.assertEqual(j["via"], "v2")
        self.assertEqual(j["status"], "running")
        self.assertEqual(j["wrapper_pid"], 99999)
        # v2-specific fields the v1 cmd_run wouldn't write
        self.assertIn("v2_manifest", j)
        self.assertIn("v2_bundle_dir", j)
        self.assertIn("v2_job_id", j)
        self.assertTrue(j["v2_job_id"].startswith("v2-rw-7-new10-"))

    def test_writes_manifest_json_for_child(self):
        """The detached child reads the manifest from disk — it must
        actually be written before the spawn returns."""
        self._run()
        j = self.fake_state["jobs"][0]
        manifest_path = pathlib.Path(j["v2_manifest"])
        self.assertTrue(manifest_path.is_file(),
                        f"manifest.json missing at {manifest_path}")
        # And it must be valid JSON with the expected job_id
        m = json.loads(manifest_path.read_text())
        self.assertEqual(m["job_id"], j["v2_job_id"])
        self.assertEqual(m["metadata"]["cohort"], "new10")

    def test_spawn_uses_python_module_v2_submit(self):
        _, popen, _ = self._run()
        cmd = popen.call_args[0][0]
        self.assertIn("-m", cmd)
        self.assertIn("v2", cmd)
        self.assertIn("submit", cmd)
        # Manifest path argument is the second positional after "submit"
        i = cmd.index("submit")
        self.assertTrue(cmd[i + 1].endswith("manifest.json"))

    def test_rejects_local_host(self):
        hosts = {"mac": {"type": "local", "repo": "/tmp", "has_libemd": True, "cores": 12}}
        args = SimpleNamespace(
            cohort="new10", host="mac", out_subdir=None,
            into="live_data", pipeline_args=None,
        )
        with mock.patch.object(fleet_adapter, "_bundle_state_for_fleet",
                               return_value=(self.tmp, self.tmp / "logs")):
            (self.tmp / "logs").mkdir(parents=True, exist_ok=True)
            rc = fleet_adapter.submit_random_windows_via_v2(args, hosts)
        self.assertEqual(rc, 1)
        self.assertEqual(len(self.fake_state["jobs"]), 0)


class TestSubmitGenericViaV2Dispatch(unittest.TestCase):
    """`fleet generic` end-to-end: arbitrary module/args go through
    _build_generic_manifest + the shared spawn helper, no per-workflow
    builder needed."""

    def setUp(self):
        import tempfile
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix="v2_gen_t_"))
        self.fake_state = {"next_job_id": 11, "jobs": []}
        # Extra-blob source file the adapter will try to bundle
        self.extra_src = self.tmp / "config.json"
        self.extra_src.write_text("{}")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _hosts(self):
        return {
            "cdec": {
                "type": "ssh", "ssh_alias": "cdec",
                "repo": "C:/Users/kenne/Downloads/fleet-offload",
                "rsync_path": "C:/msys64/usr/bin/rsync.exe",
                "has_libemd": True, "cores": 24,
                "results_root": "c_emd/results",
            },
        }

    def _run(self, **arg_overrides):
        from types import SimpleNamespace
        args = SimpleNamespace(
            module="trading_common.tools.smoke",
            host="cdec",
            workflow=None,
            into="live_data",
            blob=[],
            env=[],
            host_results_root=None,
            pass_args=["--seed", "42"],
        )
        for k, v in arg_overrides.items():
            setattr(args, k, v)
        fake_proc = mock.MagicMock()
        fake_proc.pid = 88888
        with mock.patch.object(fleet_adapter.subprocess, "Popen",
                               return_value=fake_proc) as popen, \
             mock.patch.object(fleet_adapter, "_bundle_state_for_fleet",
                               return_value=(self.tmp, self.tmp / "logs")), \
             mock.patch("fleet.load_state", return_value=self.fake_state), \
             mock.patch("fleet.save_state",
                        side_effect=lambda s: self.fake_state.update(s)):
            (self.tmp / "logs").mkdir(parents=True, exist_ok=True)
            rc = fleet_adapter.submit_generic_via_v2(args, self._hosts())
            return rc, popen

    def test_returns_zero_on_successful_spawn(self):
        rc, _ = self._run()
        self.assertEqual(rc, 0)

    def test_workflow_defaults_to_module_leaf(self):
        self._run()
        j = self.fake_state["jobs"][0]
        # cohort recorded by the spawn helper uses cohort_label="generic_<workflow>"
        self.assertEqual(j["cohort"], "generic_smoke")
        self.assertTrue(j["v2_job_id"].startswith("v2-smoke-11-cdec"))

    def test_explicit_workflow_overrides_default(self):
        self._run(workflow="probe_a")
        j = self.fake_state["jobs"][0]
        self.assertEqual(j["cohort"], "generic_probe_a")

    def test_pass_args_reach_the_manifest(self):
        self._run()
        j = self.fake_state["jobs"][0]
        m = json.loads(pathlib.Path(j["v2_manifest"]).read_text())
        # The generic driver gets "--module M --pass-args-shlex 'shlex_joined'"
        self.assertIn("--module", m["run_args"])
        self.assertIn("trading_common.tools.smoke", m["run_args"])
        i = m["run_args"].index("--pass-args-shlex")
        import shlex as _shlex
        self.assertEqual(_shlex.split(m["run_args"][i + 1]),
                         ["--seed", "42"])

    def test_extra_blob_lands_in_manifest(self):
        self._run(blob=[f"{self.extra_src}=config/conf.json"])
        j = self.fake_state["jobs"][0]
        m = json.loads(pathlib.Path(j["v2_manifest"]).read_text())
        names = [b["name"] for b in m["blobs"]]
        self.assertTrue(any("config.json" in n for n in names),
                        f"extra blob missing from manifest blobs: {names}")
        # And the blob's rel_path inside the seal matches the as_path we passed
        cfg_blob = next(b for b in m["blobs"] if "config.json" in b["name"])
        self.assertEqual(cfg_blob["rel_path"], "config/conf.json")

    def test_env_override_lands_in_manifest(self):
        self._run(env=["PYTHONHASHSEED=0", "LOG_LEVEL=debug"])
        j = self.fake_state["jobs"][0]
        m = json.loads(pathlib.Path(j["v2_manifest"]).read_text())
        self.assertEqual(m["env"]["PYTHONHASHSEED"], "0")
        self.assertEqual(m["env"]["LOG_LEVEL"], "debug")
        # Default env still present
        self.assertEqual(m["env"]["PYTHONIOENCODING"], "utf-8")

    def test_malformed_blob_returns_error(self):
        rc, _ = self._run(blob=["no_equals_sign"])
        self.assertEqual(rc, 1)
        self.assertEqual(len(self.fake_state["jobs"]), 0)

    def test_missing_blob_src_returns_error(self):
        rc, _ = self._run(blob=["/does/not/exist=foo/bar"])
        self.assertEqual(rc, 1)
        self.assertEqual(len(self.fake_state["jobs"]), 0)

    def test_rejects_local_host(self):
        hosts = {"mac": {"type": "local", "repo": "/tmp",
                          "has_libemd": True, "cores": 12}}
        from types import SimpleNamespace
        args = SimpleNamespace(
            module="trading_common.tools.smoke", host="mac",
            workflow=None, into="live_data", blob=[], env=[],
            host_results_root=None, pass_args=[],
        )
        with mock.patch.object(fleet_adapter, "_bundle_state_for_fleet",
                               return_value=(self.tmp, self.tmp / "logs")):
            (self.tmp / "logs").mkdir(parents=True, exist_ok=True)
            rc = fleet_adapter.submit_generic_via_v2(args, hosts)
        self.assertEqual(rc, 1)

    def test_auto_picks_host_when_unset(self):
        from types import SimpleNamespace
        # Two hosts; picker should pick scan-new (more cores)
        hosts = {
            "cdec":     {"type": "ssh", "ssh_alias": "cdec", "repo": "C:/u/cdec",
                         "rsync_path": "rsync", "has_libemd": True, "cores": 24},
            "scan-new": {"type": "ssh", "ssh_alias": "scan-new", "repo": "C:/u/scan",
                         "rsync_path": "rsync", "has_libemd": True, "cores": 128},
        }
        args = SimpleNamespace(
            module="trading_common.tools.smoke", host=None,
            workflow=None, into="live_data", blob=[], env=[],
            host_results_root=None, pass_args=[],
        )
        fake_proc = mock.MagicMock()
        fake_proc.pid = 77777
        with mock.patch.object(fleet_adapter.subprocess, "Popen",
                               return_value=fake_proc), \
             mock.patch.object(fleet_adapter, "_bundle_state_for_fleet",
                               return_value=(self.tmp, self.tmp / "logs")), \
             mock.patch("fleet.load_state", return_value=self.fake_state), \
             mock.patch("fleet.save_state",
                        side_effect=lambda s: self.fake_state.update(s)):
            (self.tmp / "logs").mkdir(parents=True, exist_ok=True)
            rc = fleet_adapter.submit_generic_via_v2(args, hosts)
        self.assertEqual(rc, 0)
        self.assertEqual(self.fake_state["jobs"][0]["host"], "scan-new")


if __name__ == "__main__":
    unittest.main()
