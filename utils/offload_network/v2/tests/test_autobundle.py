"""Unit tests for v2/autobundle.py — spec → SealedManifest translation."""
from __future__ import annotations

import json
import pathlib
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent))

from v2.spec import JobSpec, SpecError  # noqa: E402
from v2.autobundle import (  # noqa: E402
    build_manifest_from_spec, ResolvedUpstream, expected_remote_workdir,
)


def _hosts() -> dict:
    return {
        "cdec": {
            "type": "ssh",
            "ssh_alias": "cdec",
            "repo": "C:/Users/kenne/Downloads/fleet-offload",
            "rsync_path": "C:/msys64/usr/bin/rsync.exe",
            "has_libemd": True,
            "cores": 24,
        },
        "scan-new": {
            "type": "ssh",
            "ssh_alias": "scan-new",
            "user": "kenne",
            "repo": "C:/Users/kenne/Downloads/fleet-offload",
            "rsync_path": "C:/msys64/usr/bin/rsync.exe",
            "has_libemd": True,
            "cores": 128,
        },
        "kenne": {
            "type": "ssh",
            "ssh_alias": "kenne",
            "user": "Kenneth",
            "repo": "C:/Users/Kenneth/Downloads/fleet-offload",
            "rsync_path": "C:/Users/Kenneth/msys64/usr/bin/rsync.exe",
            "has_libemd": True,
            "cores": 128,
        },
    }


class TestBuildManifestFromSpec(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix="ab_t_"))
        # Make a fake bundle source that exists on disk so the autobundler
        # is happy: a real directory with a file inside.
        (self.tmp / "fakebundle").mkdir()
        (self.tmp / "fakebundle" / "a.py").write_text("# fake\n")
        (self.tmp / "config.json").write_text("{}")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _build(self, **kw):
        defaults = dict(
            job_id=1,
            bundle_out_dir=self.tmp,
            hosts=_hosts(),
            roots={},
            upstream_state={},
        )
        defaults.update(kw)
        spec_dict = kw.pop("spec_dict", self._minimal_spec_dict())
        return build_manifest_from_spec(
            JobSpec.from_dict(spec_dict),
            **{k: v for k, v in defaults.items() if k != "spec_dict"},
        )

    def _minimal_spec_dict(self) -> dict:
        return {
            "name": "test_job",
            "phase": "test",
            "host": {"alias": "cdec"},
            "entry": {"kind": "module", "path": "trading_common"},
            "args": [],
            "inputs": {
                "bundle": [{"src": str(self.tmp / "fakebundle"),
                            "as": "code/fakebundle"}],
                "remote_refs": [],
            },
            "outputs": {"pull": []},
            "deps": [],
        }

    # --- basic structure ---

    def test_module_entry_routes_to_generic_driver(self):
        m, _ = self._build()
        self.assertEqual(m.entrypoint_rel, "code/generic.py")
        self.assertEqual(m.run_args[:2], ["--module", "trading_common"])

    def test_script_entry_routes_to_script_arg(self):
        sd = self._minimal_spec_dict()
        sd["entry"] = {"kind": "script", "path": str(self.tmp / "fakebundle" / "a.py")}
        m, _ = self._build(spec_dict=sd)
        # Generic driver invoked with --script + the path relative to code/
        self.assertEqual(m.run_args[0], "--script")
        self.assertTrue(m.run_args[1].endswith("a.py"))

    def test_explicit_host_alias_resolves(self):
        m, _ = self._build()
        self.assertEqual(m.host.ssh_alias, "cdec")
        self.assertEqual(m.host.rsync_path, "C:/msys64/usr/bin/rsync.exe")

    def test_no_host_alias_picks_from_pool(self):
        sd = self._minimal_spec_dict()
        sd["host"] = {}
        m, _ = self._build(spec_dict=sd)
        # Picks the highest-core host (kenne or scan-new at 128 cores)
        self.assertIn(m.host.ssh_alias, ("kenne", "scan-new"))

    def test_kenne_host_uses_kenneth_rsync_path(self):
        sd = self._minimal_spec_dict()
        sd["host"] = {"alias": "kenne"}
        m, _ = self._build(spec_dict=sd)
        self.assertEqual(m.host.ssh_alias, "kenne")
        self.assertEqual(m.host.rsync_path, "C:/Users/Kenneth/msys64/usr/bin/rsync.exe")

    # --- bundle resolution ---

    def test_bundle_entry_creates_blob(self):
        m, _ = self._build()
        names = [b.name for b in m.blobs]
        self.assertIn("driver", names)
        # User-bundle entries get auto-named bundle_<i>_<basename>
        self.assertTrue(any("fakebundle" in n for n in names),
                        f"expected a fakebundle blob, got {names}")

    def test_bundle_entry_with_var_interpolates_into_args(self):
        sd = self._minimal_spec_dict()
        sd["inputs"]["bundle"].append({
            "src": str(self.tmp / "config.json"),
            "as": "config/conf.json",
            "var": "config_file",
        })
        sd["args"] = ["--config", "{{config_file}}"]
        m, _ = self._build(spec_dict=sd)
        # The bundle path resolves to blobs/<as_> as seen by the driver
        # (which runs cwd=workdir).
        import shlex
        i = m.run_args.index("--pass-args-shlex")
        pa = shlex.split(m.run_args[i + 1])
        self.assertEqual(pa, ["--config", "blobs/config/conf.json"])

    def test_bundle_entry_missing_src_rejected(self):
        sd = self._minimal_spec_dict()
        sd["inputs"]["bundle"][0]["src"] = "/nonexistent/path/foo"
        with self.assertRaises(SpecError):
            self._build(spec_dict=sd)

    # --- remote_ref resolution ---

    def test_remote_ref_resolves_via_upstream_state(self):
        # j_up completed; downstream j2 references j_up's cache output
        sd = self._minimal_spec_dict()
        sd["name"] = "j2"
        sd["deps"] = ["j_up"]
        sd["host"] = {"affinity": "j_up"}
        sd["args"] = ["--cache", "{{cache_path}}"]
        sd["inputs"]["remote_refs"] = [{
            "from": "j_up",
            "remote_path": "outputs/cache.mat",
            "var": "cache_path",
        }]
        m, _ = self._build(
            spec_dict=sd,
            upstream_state={
                "j_up": ResolvedUpstream(
                    name="j_up",
                    host_alias="cdec",
                    remote_workdir="C:/sealed/jobs/v2-spec-7-j_up-cdec",
                    v2_job_id="v2-spec-7-j_up-cdec",
                    bundle_dir_local=pathlib.Path("/tmp/fake"),
                ),
            },
        )
        import shlex
        i = m.run_args.index("--pass-args-shlex")
        pa = shlex.split(m.run_args[i + 1])
        self.assertEqual(pa, ["--cache",
            "C:/sealed/jobs/v2-spec-7-j_up-cdec/outputs/cache.mat"])

    def test_affinity_picks_upstream_host(self):
        sd = self._minimal_spec_dict()
        sd["name"] = "j2"
        sd["deps"] = ["j_up"]
        sd["host"] = {"affinity": "j_up"}
        m, _ = self._build(
            spec_dict=sd,
            upstream_state={
                "j_up": ResolvedUpstream(
                    name="j_up", host_alias="scan-new",
                    remote_workdir="x", v2_job_id="y",
                    bundle_dir_local=pathlib.Path("/tmp"),
                ),
            },
        )
        self.assertEqual(m.host.ssh_alias, "scan-new")

    def test_affinity_without_upstream_state_rejected(self):
        sd = self._minimal_spec_dict()
        sd["name"] = "j2"
        sd["deps"] = ["j_up"]
        sd["host"] = {"affinity": "j_up"}
        with self.assertRaises(SpecError) as ctx:
            self._build(spec_dict=sd, upstream_state={})
        self.assertIn("affinity", str(ctx.exception).lower())

    # --- env interpolation ---

    def test_env_var_interpolation(self):
        sd = self._minimal_spec_dict()
        sd["env"] = {"WORK_ROOT": "C:/sealed/jobs/{{job_id}}/work"}
        m, _ = self._build(spec_dict=sd, job_id=42)
        self.assertEqual(m.env["WORK_ROOT"], "C:/sealed/jobs/42/work")

    def test_env_gets_default_pythonioencoding(self):
        m, _ = self._build()
        self.assertEqual(m.env.get("PYTHONIOENCODING"), "utf-8")

    # --- metadata ---

    def test_metadata_records_spec_name_and_phase(self):
        sd = self._minimal_spec_dict()
        sd["phase"] = "cache"
        sd["name"] = "cache.naturalgas"
        m, _ = self._build(spec_dict=sd)
        self.assertEqual(m.metadata["spec_name"], "cache.naturalgas")
        self.assertEqual(m.metadata["spec_phase"], "cache")
        self.assertEqual(m.metadata["task_type"], "spec_v2_cache")

    def test_user_metadata_passes_through(self):
        sd = self._minimal_spec_dict()
        sd["metadata"] = {"instrument": "naturalgas", "cadence": "30m"}
        m, _ = self._build(spec_dict=sd)
        self.assertEqual(m.metadata["instrument"], "naturalgas")
        self.assertEqual(m.metadata["cadence"], "30m")

    # --- outputs ---

    def test_outputs_spec_returned_alongside_manifest(self):
        sd = self._minimal_spec_dict()
        sd["outputs"]["pull"] = [
            {"remote": "outputs/cache/*.mat", "to": "/tmp/dest/"},
        ]
        m, outs = self._build(spec_dict=sd)
        self.assertEqual(len(outs.pull), 1)
        self.assertEqual(outs.pull[0].remote, "outputs/cache/*.mat")

    def test_cache_result_archive_excludes_large_cache_outputs(self):
        sd = self._minimal_spec_dict()
        sd["phase"] = "cache"
        sd["metadata"] = {"phase_subkind": "cache_build"}
        m, _ = self._build(spec_dict=sd)
        self.assertIn("outputs/cache/**", m.result.exclude_patterns)
        self.assertNotIn("outputs/**", m.result.include_patterns)
        self.assertLessEqual(m.result.max_size_mb, 512)

    # --- helpers ---

    def test_expected_remote_workdir_format(self):
        m, _ = self._build()
        wd = expected_remote_workdir(m)
        self.assertTrue(wd.startswith("C:/sealed/jobs/"))
        self.assertTrue(wd.endswith(m.job_id))


class TestAffinityHostFailover(unittest.TestCase):
    """Tests for the probe_affinity_host=True path — if the upstream's
    host is unreachable, the job migrates to a pool pick AND its
    remote_refs swap to fallback_local blobs."""

    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix="ab_failover_"))
        # A real local file we can bundle as the fallback
        self.local_cache = self.tmp / "cache_local.mat"
        self.local_cache.write_bytes(b"x" * 2048)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _spec(self) -> JobSpec:
        return JobSpec.from_dict({
            "name": "downstream",
            "phase": "replay",
            "host": {"affinity": "upstream_cache"},
            "entry": {"kind": "module", "path": "trading_common"},
            "args": ["--cache", "{{cache_path}}"],
            "inputs": {
                "bundle": [],
                "remote_refs": [{
                    "from": "upstream_cache",
                    "remote_path": "outputs/cache.mat",
                    "var": "cache_path",
                    "fallback": "bundle_from_local",
                    "fallback_local": str(self.local_cache),
                }],
            },
            "outputs": {"pull": []},
            "deps": ["upstream_cache"],
        })

    def _upstream(self) -> dict:
        return {
            "upstream_cache": ResolvedUpstream(
                name="upstream_cache",
                host_alias="cdec",       # cdec will be "down" in failover test
                remote_workdir="C:/sealed/jobs/v2-spec-1-upstream_cache-cdec",
                v2_job_id="v2-spec-1-upstream_cache-cdec",
                bundle_dir_local=pathlib.Path("/tmp"),
            ),
        }

    def test_affinity_alive_no_failover(self):
        """probe_affinity_host=True + host responds → pinned to upstream's host,
        remote_ref resolves to remote path (no failover)."""
        from unittest import mock
        from v2 import autobundle
        with mock.patch.object(autobundle, "_is_host_reachable", return_value=True):
            m, _ = autobundle.build_manifest_from_spec(
                self._spec(),
                job_id=2,
                bundle_out_dir=self.tmp,
                hosts=_hosts(),
                upstream_state=self._upstream(),
                probe_affinity_host=True,
            )
        self.assertEqual(m.host.ssh_alias, "cdec")
        self.assertFalse(m.metadata.get("affinity_failed_over"))
        import shlex
        i = m.run_args.index("--pass-args-shlex")
        pa = shlex.split(m.run_args[i + 1])
        self.assertTrue(pa[pa.index("--cache") + 1].startswith("C:/sealed/jobs/"))

    def test_affinity_dead_falls_back_to_local_bundle(self):
        """probe_affinity_host=True + host UNreachable + fallback=bundle_from_local
        → migrate to a pool pick AND ship the local cache as a blob."""
        from unittest import mock
        from v2 import autobundle
        with mock.patch.object(autobundle, "_is_host_reachable", return_value=False):
            m, _ = autobundle.build_manifest_from_spec(
                self._spec(),
                job_id=2,
                bundle_out_dir=self.tmp,
                hosts=_hosts(),
                upstream_state=self._upstream(),
                probe_affinity_host=True,
            )
        # Migrated off cdec to another pool member
        self.assertNotEqual(m.host.ssh_alias, "cdec")
        self.assertTrue(m.metadata.get("affinity_failed_over"))
        # Fallback blob is in the seal
        names = [b.name for b in m.blobs]
        self.assertTrue(any("fallback_" in n for n in names),
                        f"expected a fallback_<...> blob, got {names}")
        # --cache now points at the bundle-internal path
        import shlex
        i = m.run_args.index("--pass-args-shlex")
        pa = shlex.split(m.run_args[i + 1])
        self.assertTrue(pa[pa.index("--cache") + 1].startswith("blobs/fallback/"))

    def test_no_probe_skips_liveness_check_entirely(self):
        """probe_affinity_host=False (default) → pin to affinity host without
        any SSH probe, even if the host is dead."""
        from unittest import mock
        from v2 import autobundle
        # Even if the host is dead, with probe_off we pin anyway.
        with mock.patch.object(autobundle, "_is_host_reachable",
                               side_effect=AssertionError("should not be probed")):
            m, _ = autobundle.build_manifest_from_spec(
                self._spec(),
                job_id=2,
                bundle_out_dir=self.tmp,
                hosts=_hosts(),
                upstream_state=self._upstream(),
                probe_affinity_host=False,
            )
        self.assertEqual(m.host.ssh_alias, "cdec")
        self.assertFalse(m.metadata.get("affinity_failed_over"))


class TestRewriteJson(unittest.TestCase):
    """Fix-4: cache-config path-rewriting in autobundle."""

    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix="ab_rw_"))
        (self.tmp / "fakebundle").mkdir()
        (self.tmp / "fakebundle" / "a.py").write_text("# fake\n")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _build(self, spec_dict):
        return build_manifest_from_spec(
            JobSpec.from_dict(spec_dict),
            job_id=1,
            bundle_out_dir=self.tmp,
            hosts=_hosts(),
            roots={},
            upstream_state={},
        )

    def _config_file(self, content: dict) -> pathlib.Path:
        p = self.tmp / "cache_config.json"
        p.write_text(json.dumps(content))
        return p

    def _spec(self, rewrite_rules):
        cfg = self._config_file({
            "data": {"tick_archive": "/Volumes/Untitled/raw/ng.csv"},
            "output": {"work_dir": "/Users/tomprice/work"},
        })
        return {
            "name": "cache_test",
            "phase": "cache",
            "host": {"alias": "cdec"},
            "entry": {"kind": "module", "path": "trading_common"},
            "args": ["--config", "{{config_file}}"],
            "inputs": {
                "bundle": [
                    {"src": str(self.tmp / "fakebundle"),
                     "as": "code/fakebundle"},
                    {"src": str(cfg),
                     "as": "config/cache.json",
                     "var": "config_file",
                     "rewrite_json": rewrite_rules},
                ],
                "remote_refs": [],
            },
            "outputs": {"pull": []},
            "deps": [],
        }

    def test_rewrite_literal_string(self):
        m, _ = self._build(self._spec([
            {"path": "data.tick_archive", "value": "blobs/data/ng.csv"},
        ]))
        # Find the rewritten config blob's on-disk file and verify the JSON
        cfg_blob = next(b for b in m.blobs if b.rel_path.endswith("config/cache.json"))
        on_disk = json.loads(pathlib.Path(cfg_blob.local_src).read_text())
        self.assertEqual(on_disk["data"]["tick_archive"], "blobs/data/ng.csv")
        # Unrelated paths are untouched
        self.assertEqual(on_disk["output"]["work_dir"], "/Users/tomprice/work")

    def test_rewrite_with_var_interpolation(self):
        # Reference {{job_id}} in the rewrite value
        m, _ = self._build(self._spec([
            {"path": "output.work_dir",
             "value": "C:/sealed/jobs/{{job_id}}/work"},
        ]))
        cfg_blob = next(b for b in m.blobs if b.rel_path.endswith("config/cache.json"))
        on_disk = json.loads(pathlib.Path(cfg_blob.local_src).read_text())
        self.assertEqual(on_disk["output"]["work_dir"], "C:/sealed/jobs/1/work")

    def test_rewrite_creates_missing_intermediate_dicts(self):
        m, _ = self._build(self._spec([
            {"path": "new.nested.field", "value": "added"},
        ]))
        cfg_blob = next(b for b in m.blobs if b.rel_path.endswith("config/cache.json"))
        on_disk = json.loads(pathlib.Path(cfg_blob.local_src).read_text())
        self.assertEqual(on_disk["new"]["nested"]["field"], "added")

    def test_rewrite_rule_validation(self):
        spec_dict = self._spec([{"missing_path_key": "x", "value": "y"}])
        with self.assertRaises(SpecError):
            self._build(spec_dict)

    def test_rewrite_requires_json_source(self):
        # rewrite_json on a non-JSON source file → SpecError
        not_json = self.tmp / "blob.bin"
        not_json.write_bytes(b"\x00\x01\x02")
        spec_dict = self._spec([{"path": "x", "value": "y"}])
        spec_dict["inputs"]["bundle"][1]["src"] = str(not_json)
        with self.assertRaises(SpecError):
            self._build(spec_dict)

    def test_rewrite_pointing_at_another_bundle_var(self):
        # rewrite value uses {{other_var}} from a sibling bundle entry
        cfg = self._config_file({"x": "placeholder"})
        spec_dict = {
            "name": "cache_test2",
            "phase": "cache",
            "host": {"alias": "cdec"},
            "entry": {"kind": "module", "path": "trading_common"},
            "args": [],
            "inputs": {
                "bundle": [
                    {"src": str(self.tmp / "fakebundle"),
                     "as": "code/fakebundle"},
                    {"src": str(self.tmp / "fakebundle" / "a.py"),
                     "as": "blobs/extra.py",
                     "var": "extra"},
                    {"src": str(cfg), "as": "config/c.json", "var": "cfg",
                     "rewrite_json": [
                         {"path": "x", "value": "use {{extra}}"},
                     ]},
                ],
                "remote_refs": [],
            },
            "outputs": {"pull": []},
            "deps": [],
        }
        m, _ = self._build(spec_dict)
        cfg_blob = next(b for b in m.blobs if b.rel_path.endswith("config/c.json"))
        on_disk = json.loads(pathlib.Path(cfg_blob.local_src).read_text())
        self.assertEqual(on_disk["x"], "use blobs/extra.py")


if __name__ == "__main__":
    unittest.main()
