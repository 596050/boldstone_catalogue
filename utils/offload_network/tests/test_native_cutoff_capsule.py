"""Fresh generic capsules retain cutoff policy without frozen-model imports."""
from pathlib import Path
import subprocess
import sys

from research_workflows.capsule import research_selection, snapshot


def test_fresh_generic_capsule_has_lightweight_unchanged_cutoff_policy(tmp_path):
    repo = Path(__file__).resolve().parents[3]
    capsule = tmp_path / "capsule"
    snapshot(repo, capsule, include=research_selection(repo), resolve_code_links=True)
    assert not (capsule / "research/conjectures").exists()
    script = """
import sys
from types import SimpleNamespace
sys.path.insert(0, sys.argv[1])
from research.testing_stages.runtime import experiment
from research.testing_stages.stage_00_contracts.full_origin_cutoff import refuse_inherited_cutoff
assert 'research.testing_stages.comparison' not in sys.modules
assert 'research.conjectures' not in sys.modules
for start in ('2007-01-01', '2007-01-03'):
    for end in (None, 'latest', '2026-09-09', '2026-09-10'):
        refusal = refuse_inherited_cutoff(SimpleNamespace(
            purpose='compare', start=start, end=end, max_seconds=10))
        assert refusal['stop_subsection'] == 'inherited_replay_cutoff'
        assert refusal['performance_qualification'] == 'NOT_ESTABLISHED'
        assert refusal['max_seconds'] == 10
        assert refuse_inherited_cutoff(SimpleNamespace(
            purpose='compare', start=start, end=end, max_seconds=None)) is None
assert refuse_inherited_cutoff(SimpleNamespace(
    purpose='compare', start='2007-01-03', end='2007-07-06', max_seconds=10)) is None
assert refuse_inherited_cutoff(SimpleNamespace(
    purpose='validate', start='2007-01-03', end='2026-09-10', max_seconds=10)) is None
"""
    result = subprocess.run([sys.executable, "-I", "-B", "-c", script, str(capsule)],
        cwd=tmp_path, text=True, capture_output=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr


def test_fresh_generic_comparison_does_not_require_a_frozen_threshold_contract(tmp_path):
    repo = Path(__file__).resolve().parents[3]
    capsule = tmp_path / "capsule"
    snapshot(repo, capsule, include=research_selection(repo), resolve_code_links=True)
    assert not (capsule / "research/conjectures").exists()
    script = """
import sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from research.testing_stages.common import digest
from research.testing_stages.stage_06_comparison.gate import stock_subsection_record
from research.testing_stages.stage_06_comparison.frozen_pair_subsections import compare_reports
unavailable = stock_subsection_record({}, Path(sys.argv[2]))
assert unavailable['status'] == 'NOT_EVALUABLE'
assert unavailable['scored'] is False
assert unavailable['performance_qualification'] == 'NOT_ESTABLISHED'
assert 'research.conjectures' not in sys.modules
# An actual frozen-pair calculation must still require its real contract.
# Missing optional dependencies are not replaced by defaults or a PASS.
domain = {'symbols': ['A'], 'costs_bps': [0, 20, 40],
          'parent_measurement_contract_id': 'synthetic', 'capital_reference': 10000}
domain['contract_id'] = digest(domain)
period = {'start': '2007-01-03', 'end': '2007-01-03', 'sessions': 1}
report = {'schema': 'marketmaker.symbol_metrics.v1', 'symbols': ['A'],
          'measurement': domain, 'periods': [dict(period, id='full'), dict(period, id='2007')],
          'rows': []}
try:
    compare_reports({role: report for role in ('candidate', 'base', 'crash90_v1')})
except ModuleNotFoundError as error:
    assert error.name == 'research.conjectures'
else:
    raise AssertionError('frozen calculation must not bypass its missing contract')
"""
    result = subprocess.run([sys.executable, "-I", "-B", "-c", script, str(capsule), str(tmp_path)],
        cwd=tmp_path, text=True, capture_output=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
