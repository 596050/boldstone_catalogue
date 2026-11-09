"""Config-driven scenario tests for the v2 manifest builders.

Each subdirectory of v2/tests/scenarios/ that contains a scenario.json
becomes one test case automatically. Add a new workflow scenario by:

  1. Create v2/tests/scenarios/<name>/scenario.json (see _runner.py docstring
     + scenarios/README.md for the schema)
  2. Run the suite once with UPDATE_GOLDEN=1 to write the initial
     expected_manifest.json
  3. Eyeball the generated golden, commit both files

No Python test code to touch.

Run modes:
  - default                       — CHECK against committed goldens
  - UPDATE_GOLDEN=1 pytest        — rewrite goldens after intentional API change
  - V2_LIVE_TESTS=1 pytest        — additionally run `live: true` scenarios
                                    on a real remote and diff result summary
"""
from __future__ import annotations

import pathlib
import sys
import unittest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent))

# Import the runner from the scenarios/ subpackage.
sys.path.insert(0, str(HERE / "scenarios"))
import _runner as runner  # noqa: E402


# These retained upstream fixtures reference model data/code outside the
# transferred generic utility. They remain as provenance examples but are not
# standalone tests in marketmaker_v2.
PROJECT_COUPLED_SCENARIOS = {
    "spec_cache_naturalgas",
    "spec_diagnostics_naturalgas_30m",
    "spec_replay_naturalgas_30m",
}


def setUpModule():
    # Guarantee the gitignored Windows libemd.dll exists for the suite so the
    # autobundler includes the libemd blobs the goldens expect (hermetic on
    # non-Windows dev/CI checkouts). No-op if a real DLL exists or in live mode.
    runner.install_libemd_stub()


def tearDownModule():
    runner.remove_libemd_stub()


def _make_test(scenario_dir: pathlib.Path):
    """Generate one unittest method bound to a single scenario.

    Each scenario becomes a separately-named test so failures point at
    the specific config that broke, not a generic "scenarios failed".

    The test runs in two phases:
      1. Unit-level manifest check (always)
      2. Live-remote end-to-end (only if V2_LIVE_TESTS=1 AND scenario.live=true)

    Phase 2 actually pushes the seal, runs the job, pulls the result, and
    diffs the result summary against expected_summary.json.
    """
    def test(self):
        if scenario_dir.name in PROJECT_COUPLED_SCENARIOS:
            self.skipTest("retained upstream fixture requires non-generic famous-model inputs")
        # Phase 1: manifest check
        result = runner.run_scenario_check(scenario_dir)
        if result is None:
            pass  # pass; fall through to phase 2
        elif runner.in_update_mode():
            pass  # never fail in update mode
        elif "golden didn't exist" in result:
            self.fail(
                f"FIRST RUN for {scenario_dir.name}:\n{result}\n"
                f"Inspect {scenario_dir.name}/expected_manifest.json and re-run."
            )
        else:
            self.fail(
                f"Manifest drift for scenario {scenario_dir.name!r}:\n\n{result}\n\n"
                f"If this drift is INTENTIONAL, re-run with UPDATE_GOLDEN=1 "
                f"and commit the updated expected_manifest.json."
            )

        # Phase 2: live mode (silent skip unless V2_LIVE_TESTS=1 + live:true)
        live_result = runner.run_scenario_live(scenario_dir)
        if live_result is None:
            return
        self.fail(
            f"Live-remote diff for scenario {scenario_dir.name!r}:\n\n"
            f"{live_result}\n\nIf intentional, re-run with V2_LIVE_TESTS=1 "
            f"UPDATE_GOLDEN=1 and commit the updated expected_summary.json."
        )

    test.__name__ = f"test_{scenario_dir.name}"
    test.__doc__ = f"Scenario: {scenario_dir.name}"
    return test


# Build a unittest.TestCase subclass with one method per discovered scenario.
class ScenarioTests(unittest.TestCase):
    """Auto-generated tests, one per v2/tests/scenarios/<name>/ directory."""
    pass


_scenarios = runner.discover_scenarios()
if not _scenarios:
    # Give a useful failure if the scenarios dir is empty rather than
    # silently passing zero tests.
    def test_no_scenarios_defined(self):
        self.fail(
            f"No scenarios found under {runner.HERE}. "
            f"Add a directory with scenario.json + expected_manifest.json "
            f"(see scenarios/README.md)."
        )
    ScenarioTests.test_no_scenarios_defined = test_no_scenarios_defined
else:
    for sd in _scenarios:
        setattr(ScenarioTests, f"test_{sd.name}", _make_test(sd))


if __name__ == "__main__":
    unittest.main()
