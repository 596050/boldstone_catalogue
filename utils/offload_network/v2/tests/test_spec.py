"""Unit tests for v2/spec.py — schema validation, dep cycle detection,
$VAR resolution, glob expansion."""
from __future__ import annotations

import json
import pathlib
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent))

from v2.spec import (  # noqa: E402
    JobSpec, BatchSpec, SpecError, topological_layers,
    EntrySpec, BundleEntry, RemoteRef, InputsSpec, OutputsSpec, OutputPull, HostSpec,
)


def _min_job(**kw) -> dict:
    """A minimal-valid job spec dict (entry as script for simplicity)."""
    base = {
        "name": "j1",
        "entry": {"kind": "script", "path": "scripts/echo.py"},
        "args": [],
        "inputs": {"bundle": [], "remote_refs": []},
        "outputs": {"pull": []},
        "deps": [],
    }
    base.update(kw)
    return base


# ---- JobSpec schema ----

class TestJobSpecLoad(unittest.TestCase):
    def test_minimum_valid_loads(self):
        j = JobSpec.from_dict(_min_job())
        j.validate()
        self.assertEqual(j.name, "j1")
        self.assertEqual(j.entry.kind, "script")

    def test_missing_name_rejected(self):
        with self.assertRaises(KeyError):
            JobSpec.from_dict({"entry": {"kind": "module", "path": "x"}})

    def test_bad_entry_kind_rejected(self):
        j = JobSpec.from_dict(_min_job(entry={"kind": "binary", "path": "/bin/ls"}))
        with self.assertRaises(SpecError):
            j.validate()

    def test_module_with_slashes_rejected(self):
        j = JobSpec.from_dict(_min_job(entry={"kind": "module", "path": "some/file.py"}))
        with self.assertRaises(SpecError):
            j.validate()

    def test_host_alias_and_affinity_mutually_exclusive(self):
        j = JobSpec.from_dict(_min_job(host={"alias": "cdec", "affinity": "j0"}))
        with self.assertRaises(SpecError):
            j.validate()

    def test_affinity_requires_corresponding_dep(self):
        # When loaded by BatchSpec, affinity requires the same name in deps.
        # JobSpec alone doesn't check (BatchSpec does).
        j = JobSpec.from_dict(_min_job(host={"affinity": "j0"}, deps=[]))
        j.validate()  # JobSpec.validate doesn't catch this; BatchSpec does.

    def test_bundle_entry_with_absolute_as_rejected(self):
        bad = _min_job(inputs={
            "bundle": [{"src": "x", "as": "/abs/path"}],
            "remote_refs": [],
        })
        with self.assertRaises(SpecError):
            JobSpec.from_dict(bad).validate()

    def test_duplicate_var_across_bundle_and_remote_refs_rejected(self):
        bad = _min_job(inputs={
            "bundle": [{"src": "x", "as": "code/x", "var": "shared"}],
            "remote_refs": [{"from": "j0", "remote_path": "out.txt", "var": "shared"}],
        }, deps=["j0"])
        with self.assertRaises(SpecError):
            JobSpec.from_dict(bad).validate()


# ---- BatchSpec validation ----

class TestBatchSpecValidation(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix="batch_t_"))

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write_job(self, name: str, **overrides):
        p = self.tmp / f"{name}.json"
        d = _min_job(name=name, **overrides)
        p.write_text(json.dumps(d))
        return p

    def _write_batch(self, jobs: list[pathlib.Path], **overrides):
        bp = self.tmp / "batch.json"
        bd = {
            "batch": "test_batch",
            "jobs": [j.name for j in jobs],
            "roots": {},
            **overrides,
        }
        bp.write_text(json.dumps(bd))
        return bp

    def test_two_jobs_no_deps(self):
        a = self._write_job("a")
        b = self._write_job("b")
        bp = self._write_batch([a, b])
        bs = BatchSpec.from_path(bp)
        self.assertEqual(len(bs.jobs), 2)
        layers = topological_layers(bs.jobs)
        self.assertEqual(len(layers), 1)
        self.assertEqual({j.name for j in layers[0]}, {"a", "b"})

    def test_simple_dep(self):
        a = self._write_job("a")
        b = self._write_job("b", deps=["a"])
        bs = BatchSpec.from_path(self._write_batch([a, b]))
        layers = topological_layers(bs.jobs)
        self.assertEqual(len(layers), 2)
        self.assertEqual([j.name for j in layers[0]], ["a"])
        self.assertEqual([j.name for j in layers[1]], ["b"])

    def test_unknown_dep_rejected(self):
        a = self._write_job("a", deps=["nope"])
        with self.assertRaises(SpecError) as ctx:
            BatchSpec.from_path(self._write_batch([a]))
        self.assertIn("nope", str(ctx.exception))

    def test_dep_cycle_rejected(self):
        a = self._write_job("a", deps=["b"])
        b = self._write_job("b", deps=["a"])
        with self.assertRaises(SpecError) as ctx:
            BatchSpec.from_path(self._write_batch([a, b]))
        self.assertIn("cycle", str(ctx.exception).lower())

    def test_duplicate_job_names_rejected(self):
        a1 = self._write_job("a")
        # Same name, different file
        a2 = self.tmp / "a_copy.json"
        a2.write_text(json.dumps(_min_job(name="a")))
        bp = self._write_batch([a1, a2])
        with self.assertRaises(SpecError) as ctx:
            BatchSpec.from_path(bp)
        self.assertIn("duplicate", str(ctx.exception).lower())

    def test_affinity_without_dep_rejected(self):
        a = self._write_job("a")
        b = self._write_job("b", host={"affinity": "a"}, deps=[])
        with self.assertRaises(SpecError) as ctx:
            BatchSpec.from_path(self._write_batch([a, b]))
        self.assertIn("requires a corresponding entry in deps", str(ctx.exception))

    def test_glob_expansion(self):
        self._write_job("cache_a", phase="cache")
        self._write_job("cache_b", phase="cache")
        self._write_job("replay_x", deps=[])
        bp = self.tmp / "batch.json"
        bp.write_text(json.dumps({
            "batch": "glob_test",
            "jobs": ["cache_*.json"],
            "roots": {},
        }))
        bs = BatchSpec.from_path(bp)
        self.assertEqual({j.name for j in bs.jobs}, {"cache_a", "cache_b"})

    def test_root_var_substitution_in_roots(self):
        bp = self.tmp / "batch.json"
        a = self._write_job("a")
        bp.write_text(json.dumps({
            "batch": "vars",
            "roots": {"BASE": "/foo", "CHILD": "$BASE/bar"},
            "jobs": [a.name],
        }))
        bs = BatchSpec.from_path(bp)
        self.assertEqual(bs.roots["CHILD"], "/foo/bar")


# ---- topological_layers ----

class TestTopologicalLayers(unittest.TestCase):
    def test_diamond(self):
        # a → b, a → c, b+c → d (3 layers)
        jobs = [
            JobSpec.from_dict(_min_job(name="a")),
            JobSpec.from_dict(_min_job(name="b", deps=["a"])),
            JobSpec.from_dict(_min_job(name="c", deps=["a"])),
            JobSpec.from_dict(_min_job(name="d", deps=["b", "c"])),
        ]
        layers = topological_layers(jobs)
        self.assertEqual([[j.name for j in L] for L in layers],
                         [["a"], ["b", "c"], ["d"]])


if __name__ == "__main__":
    unittest.main()
