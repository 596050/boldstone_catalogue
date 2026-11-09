"""Tests for the generic v2 driver + the v1 deprecation surface added in
the v1 → v2 migration session.

- Generic driver: manifest builders that target the generic driver produce
  valid SealedManifests pointing at v2/drivers/generic.py with the right
  module + pass-args.

- Deprecation warning: v1.cmd_sync/cmd_run/cmd_collect emit one stderr
  notice per process, silenceable via FLEET_SUPPRESS_V1_WARN.
"""
from __future__ import annotations

import io
import os
import pathlib
import sys
import unittest
from contextlib import redirect_stderr
from types import SimpleNamespace
from unittest import mock

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent))

from v2 import fleet_adapter  # noqa: E402
from v2.manifest import SealedManifest  # noqa: E402


# ---------------------------------------------------------------------------
# Generic-driver manifest builders
# ---------------------------------------------------------------------------

class TestBuildGenericManifest(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.bundle = pathlib.Path(tempfile.mkdtemp(prefix="v2_gen_"))

    def tearDown(self):
        import shutil
        shutil.rmtree(self.bundle, ignore_errors=True)

    def _build(self, **kw):
        defaults = dict(
            job_id=42,
            workflow="example",
            module="trading_common.some_module",
            pass_args=["--foo", "bar"],
            host_alias="cdec",
            remote_workdir="C:/sealed/jobs",
            rsync_path="C:/msys64/usr/bin/rsync.exe",
            host_repo="C:/Users/kenne/Downloads/fleet-offload",
            host_results_root=None,
            extra_blobs=[],
            bundle_out_dir=self.bundle,
        )
        defaults.update(kw)
        return fleet_adapter._build_generic_manifest(**defaults)

    def test_entrypoint_is_generic_driver(self):
        m = self._build()
        self.assertEqual(m.entrypoint_rel, "code/generic.py")
        driver = next(b for b in m.blobs if b.name == "driver")
        self.assertTrue(driver.local_src.endswith("v2/drivers/generic.py"))

    def test_standard_code_blobs_present(self):
        m = self._build()
        names = {b.name for b in m.blobs}
        self.assertIn("trading_common", names)
        # c_emd is split into root __init__.py + python/ subdir so we don't
        # ship the 15 GB c_emd/results/ tree. See _standard_code_blobs.
        self.assertIn("c_emd_root_init", names)
        self.assertIn("c_emd_python", names)
        self.assertIn("uoa_emd_lib", names)
        self.assertIn("driver", names)

    def test_extra_blobs_are_appended(self):
        from v2.manifest import SealedBlob
        cache = SealedBlob(name="cache", local_src=str(self.bundle / "fake.mat"),
                           rel_path="data/cache.mat", is_dir=False)
        (self.bundle / "fake.mat").write_bytes(b"x" * 64)
        m = self._build(extra_blobs=[cache])
        names = {b.name for b in m.blobs}
        self.assertIn("cache", names)
        # driver + (trading_common, c_emd_root_init, c_emd_python, uoa_emd_lib)
        # + cache + optional libemd DLL copies (only present if the Windows
        # DLL is built locally — checked-in for prod builds; absent on CI).
        from v2.fleet_adapter import _LIBEMD_WIN_DLL, _EMD_CACHE_GEN_EXE
        # base 6 (driver + 4 code blobs + cache); +2 libemd DLL copies if the
        # Windows DLL is built locally; +1 emd_cache_gen_exe if the Windows native
        # exe is built locally (the v3 engine promotion ships it so remote hosts
        # can use --engine exe/auto).
        expected = 6 + (2 if _LIBEMD_WIN_DLL.is_file() else 0) + (1 if _EMD_CACHE_GEN_EXE.is_file() else 0)
        self.assertEqual(len(m.blobs), expected)

    def test_run_args_carry_module_and_pass_args(self):
        m = self._build(pass_args=["--instrument", "msft", "--seed", "42"])
        self.assertEqual(m.run_args[0], "--module")
        self.assertEqual(m.run_args[1], "trading_common.some_module")
        # pass_args are shlex-quoted into a single arg-string
        self.assertIn("--pass-args-shlex", m.run_args)
        idx = m.run_args.index("--pass-args-shlex")
        joined = m.run_args[idx + 1]
        # shlex.join preserves the args losslessly
        import shlex
        self.assertEqual(shlex.split(joined),
                         ["--instrument", "msft", "--seed", "42"])

    def test_no_pass_args_means_no_shlex_arg(self):
        m = self._build(pass_args=[])
        self.assertNotIn("--pass-args-shlex", m.run_args)

    def test_host_results_root_passes_through_when_set(self):
        m = self._build(host_results_root="X:/path")
        self.assertIn("--host-results-root", m.run_args)
        i = m.run_args.index("--host-results-root")
        self.assertEqual(m.run_args[i + 1], "X:/path")

    def test_metadata_records_workflow_and_module(self):
        m = self._build(workflow="emd-cache-replay", module="x.y.z")
        self.assertEqual(m.metadata["task_type"], "emd-cache-replay_v2")
        self.assertEqual(m.metadata["module"], "x.y.z")
        self.assertEqual(m.metadata["via"], "v2")

    def test_job_id_safe_for_paths(self):
        m = self._build(workflow="weird/name with space")
        # No slashes or spaces in the resulting job_id (would break workdir paths)
        self.assertNotIn("/", m.job_id)
        self.assertNotIn(" ", m.job_id)


# ---------------------------------------------------------------------------
# Workflow-specific manifest builders that delegate to _build_generic_manifest
# ---------------------------------------------------------------------------

class TestEmdCacheReplayManifest(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.bundle = pathlib.Path(tempfile.mkdtemp(prefix="v2_emd_"))
        self.cache = self.bundle / "fake_cache.mat"
        self.cache.write_bytes(b"x" * 1024)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.bundle, ignore_errors=True)

    def _build(self, **kw):
        defaults = dict(
            job_id=7,
            instrument="microsoft_260117_1000_aa2",
            cache_path=str(self.cache),
            cadence_rows=30,
            extra_args=["--trade-cost=-0.000125"],
            host_alias="cdec",
            remote_workdir="C:/sealed/jobs",
            rsync_path="C:/msys64/usr/bin/rsync.exe",
            host_repo="C:/Users/kenne/Downloads/fleet-offload",
            bundle_out_dir=self.bundle,
        )
        defaults.update(kw)
        return fleet_adapter._build_emd_cache_replay_manifest(**defaults)

    def test_validates(self):
        m = self._build()
        m.validate()

    def test_targets_emd_cache_replay_module(self):
        m = self._build()
        self.assertEqual(m.metadata["module"],
                         "trading_common.strategy_testing.emd_cache_replay")

    def test_bundles_cache_blob_at_data_path(self):
        m = self._build()
        cache_blob = next(b for b in m.blobs if b.name == "cache")
        self.assertEqual(cache_blob.rel_path, "data/cache.mat")

    def test_pass_args_route_outputs_under_outputs_dir(self):
        m = self._build()
        # Decode the shlex'd pass-args to inspect
        import shlex
        i = m.run_args.index("--pass-args-shlex")
        pa = shlex.split(m.run_args[i + 1])
        self.assertIn("--instrument", pa)
        self.assertIn("microsoft_260117_1000_aa2", pa)
        # --cache points at the bundle-internal path
        ci = pa.index("--cache")
        self.assertEqual(pa[ci + 1], "blobs/data/cache.mat")
        # --out under outputs/ for v2 collection
        oi = pa.index("--out")
        self.assertTrue(pa[oi + 1].startswith("outputs/"))


class TestIgTradingManifest(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.bundle = pathlib.Path(tempfile.mkdtemp(prefix="v2_ig_"))

    def tearDown(self):
        import shutil
        shutil.rmtree(self.bundle, ignore_errors=True)

    def _build(self, **kw):
        defaults = dict(
            job_id=11,
            submodule="offload_replay_status",
            extra_args=["--all"],
            host_alias="kenne",
            remote_workdir="C:/sealed/jobs",
            rsync_path="C:/Users/Kenneth/msys64/usr/bin/rsync.exe",
            host_repo="C:/Users/Kenneth/Downloads/fleet-offload",
            bundle_out_dir=self.bundle,
        )
        defaults.update(kw)
        return fleet_adapter._build_ig_trading_manifest(**defaults)

    def test_module_path_includes_submodule(self):
        m = self._build()
        self.assertEqual(
            m.metadata["module"],
            "c_emd.python.ig_trading.offload_replay_status",
        )

    def test_no_extra_blobs_for_code_only_workflow(self):
        m = self._build()
        names = {b.name for b in m.blobs}
        # driver + 4 standard code blobs, optionally + libemd DLL copies, no caches
        expected = {"driver", "trading_common", "c_emd_root_init",
                    "c_emd_python", "uoa_emd_lib"}
        from v2.fleet_adapter import _LIBEMD_WIN_DLL, _EMD_CACHE_GEN_EXE
        if _LIBEMD_WIN_DLL.is_file():
            expected.add("libemd_dll")
            expected.add("libemd_dll_c_emd_build")
        if _EMD_CACHE_GEN_EXE.is_file():
            expected.add("emd_cache_gen_exe")  # v3 engine promotion ships the native exe to the fleet
        self.assertEqual(names, expected)

    def test_host_results_root_defaults_to_host_repo_results(self):
        """ig_trading workflows read from the host's c_emd/results tree."""
        m = self._build()
        self.assertIn("--host-results-root", m.run_args)
        i = m.run_args.index("--host-results-root")
        self.assertEqual(
            m.run_args[i + 1],
            "C:/Users/Kenneth/Downloads/fleet-offload/c_emd/results",
        )

    def test_submodule_swap_changes_module_and_job_id(self):
        a = self._build(submodule="replay_coverage_status")
        b = self._build(submodule="current_best_pipeline_inventory", job_id=12)
        self.assertNotEqual(a.metadata["module"], b.metadata["module"])
        self.assertNotEqual(a.job_id, b.job_id)


# v1 deprecation tests + the --via flag test were removed when v1 was
# archived (2026-06-07). v1.fleet_v1_commands no longer exists, the
# --via flag is gone, and `fleet run` always routes to v2.


# ---------------------------------------------------------------------------
# fleet.py `run` subcommand routes to v2 unconditionally
# ---------------------------------------------------------------------------

class TestFleetRunIsV2(unittest.TestCase):
    def test_fleet_run_calls_submit_random_windows_via_v2(self):
        """`fleet run --cohort X` should call submit_random_windows_via_v2
        with the parsed args — no --via flag, no v1 fallback."""
        import importlib.util
        orch_root = pathlib.Path(__file__).resolve().parent.parent.parent
        spec = importlib.util.spec_from_file_location(
            "_fleet_for_run_test", orch_root / "fleet.py"
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        captured = {}

        def fake_run(args, hosts):
            captured["cohort"] = args.cohort
            captured["hosts_seen"] = hosts
            return 0

        from v2 import fleet_adapter as fa
        with mock.patch.object(mod, "load_hosts", return_value={"mac": {}}), \
             mock.patch.object(sys, "argv",
                               ["fleet.py", "run", "--cohort", "test_cohort"]), \
             mock.patch.object(fa, "submit_random_windows_via_v2",
                               side_effect=fake_run):
            rc = mod.main()
        self.assertEqual(rc, 0)
        self.assertEqual(captured.get("cohort"), "test_cohort")


if __name__ == "__main__":
    unittest.main()
