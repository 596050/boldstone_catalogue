"""Unit tests for v2/template.py — workload.json → per-job spec emission.

Covers:
  - cache phase emits cache.* specs for non-skipped instruments
  - skip_cache_for instruments get cache_stage specs (NOT skipped) — Fix-2
  - cache_args/cache_stage_args/replay_args/diagnostics_args flow into
    every spec of their phase — Fix-3
"""
from __future__ import annotations

import json
import pathlib
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent))

from v2.template import generate_batch  # noqa: E402


def _write_workload(path: pathlib.Path, extra: dict | None = None) -> pathlib.Path:
    """Minimal workload.json. `extra` merges into the base dict."""
    base = {
        "name": "test_workload",
        "roots": {"RUN": "/tmp/run", "REPLAY": "/tmp/replay",
                  "CACHE_ROOT": "/tmp/caches"},
        "instruments": [
            {"key": "oil",    "id": "oil_X"},
            {"key": "amazon", "id": "amazon_Y"},
        ],
        "cadences": [{"key": "30m", "rows": 30}],
        "phases": ["cache", "replay", "diagnostics"],
        "skip_cache_for": ["amazon"],
        "host_pool": ["cdec", "scan-new"],
    }
    if extra:
        base.update(extra)
    path.write_text(json.dumps(base))
    return path


class TestCacheStageEmission(unittest.TestCase):
    """Fix-2: instruments in skip_cache_for should emit a cache_stage
    spec instead of being silently dropped from the batch."""

    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix="tpl_t_"))
        self.workload = _write_workload(self.tmp / "workload.json")
        self.out = self.tmp / "out"

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_cache_stage_emitted_for_skip_cache_for_instruments(self):
        summary = generate_batch(self.workload, self.out)
        # cache.oil is a full build; cache.amazon is a cache_stage
        oil = json.loads((self.out / "jobs" / "cache.oil.json").read_text())
        amz = json.loads((self.out / "jobs" / "cache.amazon.json").read_text())
        self.assertEqual(oil["metadata"]["phase_subkind"], "cache_build")
        self.assertEqual(amz["metadata"]["phase_subkind"], "cache_stage")
        self.assertEqual(amz["inputs"]["bundle"], [])
        self.assertIn(
            "C:/sealed/prestaged_caches/test_workload/amazon_Y/amazon_Y_live_emd_cache.mat",
            amz["args"],
        )
        # The summary records cache_stage as its own counter
        self.assertEqual(summary["n_per_phase"]["cache"], 1)
        self.assertEqual(summary["n_per_phase"]["cache_stage"], 1)

    def test_cache_stage_spec_names_match_replay_dep(self):
        # Replay's `deps: ["cache.<INST_KEY>"]` must resolve regardless of
        # whether the upstream is a real cache build or a cache_stage.
        generate_batch(self.workload, self.out)
        amz_cache = json.loads((self.out / "jobs" / "cache.amazon.json").read_text())
        amz_replay = json.loads(
            (self.out / "jobs" / "replay.amazon.30m.json").read_text())
        self.assertEqual(amz_cache["name"], "cache.amazon")
        self.assertEqual(amz_replay["deps"], ["cache.amazon"])
        self.assertEqual(amz_replay["host"]["affinity"], "cache.amazon")

    def test_cache_stage_gets_pool_host_assignment(self):
        # cache_stage jobs participate in the same round-robin host
        # distribution as full cache builds.
        generate_batch(self.workload, self.out)
        amz = json.loads((self.out / "jobs" / "cache.amazon.json").read_text())
        # amazon is index 1 in the instruments list → host_pool[1 % 2] = "scan-new"
        self.assertEqual(amz["host"]["alias"], "scan-new")


class TestExtraArgsPlumbing(unittest.TestCase):
    """Fix-3: workload-level cache_args / replay_args / diagnostics_args /
    cache_stage_args append to each generated spec's args list."""

    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix="tpl_xa_"))
        self.out = self.tmp / "out"

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_replay_args_appended_to_every_replay_spec(self):
        wl = _write_workload(self.tmp / "wl.json", extra={
            "replay_args": ["--cost", "0.0005", "--seed", "42"],
        })
        generate_batch(wl, self.out)
        for inst_key in ("oil", "amazon"):
            spec = json.loads(
                (self.out / "jobs" / f"replay.{inst_key}.30m.json").read_text())
            self.assertIn("--cost", spec["args"])
            self.assertIn("0.0005", spec["args"])
            self.assertIn("--seed", spec["args"])
            self.assertIn("42", spec["args"])

    def test_cache_args_appended_to_real_cache_builds_only(self):
        wl = _write_workload(self.tmp / "wl.json", extra={
            "cache_args": ["--force-rebuild"],
            "cache_stage_args": ["--verify-sha"],
        })
        generate_batch(wl, self.out)
        # oil → real cache build → gets cache_args
        oil = json.loads((self.out / "jobs" / "cache.oil.json").read_text())
        self.assertIn("--force-rebuild", oil["args"])
        self.assertNotIn("--verify-sha", oil["args"])
        # amazon → cache_stage → gets cache_stage_args
        amz = json.loads((self.out / "jobs" / "cache.amazon.json").read_text())
        self.assertIn("--verify-sha", amz["args"])
        self.assertNotIn("--force-rebuild", amz["args"])

    def test_diagnostics_args_appended(self):
        wl = _write_workload(self.tmp / "wl.json", extra={
            "diagnostics_args": ["--write-json"],
        })
        generate_batch(wl, self.out)
        diag = json.loads(
            (self.out / "jobs" / "diagnostics.oil.30m.json").read_text())
        self.assertIn("--write-json", diag["args"])

    def test_no_extra_args_leaves_template_args_intact(self):
        # Sanity: workload without *_args sections doesn't pollute the args.
        wl = _write_workload(self.tmp / "wl.json")
        generate_batch(wl, self.out)
        oil = json.loads((self.out / "jobs" / "replay.oil.30m.json").read_text())
        # Template args should be preserved (--name + --instrument + ...)
        self.assertIn("--instrument", oil["args"])


if __name__ == "__main__":
    unittest.main()
