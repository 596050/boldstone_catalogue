"""Snapshot admission must use the same declared allowance as object packing."""
from pathlib import Path

import pytest

from research_workflows import capsule, planner


def test_snapshot_forwards_explicit_budget_to_final_inventory(monkeypatch, tmp_path):
    source = tmp_path / 'source'; source.mkdir()
    (source / 'part.bin').write_bytes(b'data')
    original = capsule.inventory
    def bounded_inventory(root, *, max_bytes=1, max_files=1):
        # A deliberately small fallback exercises the old omitted-limit bug
        # without allocating a multi-GiB test file.
        return original(root, max_bytes=max_bytes, max_files=max_files)
    monkeypatch.setattr(capsule, 'inventory', bounded_inventory)
    result = capsule.snapshot(source, tmp_path / 'copy', max_bytes=4, max_files=1)
    assert result['files']['part.bin']['bytes'] == 4


@pytest.mark.parametrize('limits', [{'max_bytes': 7}, {'max_files': 1}])
def test_late_oversize_or_excess_file_fails_before_any_copy(monkeypatch, tmp_path, limits):
    source = tmp_path / 'source'; source.mkdir()
    for name in ('early.bin', 'late.bin'):
        (source / name).write_bytes(b'data')
    def forbidden(*args, **kwargs):
        pytest.fail('known over-budget selection reached copying or hashing')
    monkeypatch.setattr(capsule.shutil, 'copyfile', forbidden)
    monkeypatch.setattr(capsule, 'sha', forbidden)
    with pytest.raises(ValueError, match='before copying'):
        capsule.snapshot(source, tmp_path / 'copy', **limits)
    assert not (tmp_path / 'copy').exists()


def test_overlapping_selected_paths_do_not_double_count_budget(tmp_path):
    source = tmp_path / 'source'; source.mkdir()
    (source / 'part.bin').write_bytes(b'data')
    result = capsule.snapshot(source, tmp_path / 'copy',
        include=['part.bin', 'part.bin'], max_bytes=4, max_files=1)
    assert list(result['files']) == ['part.bin']


def test_planner_uses_declared_budget_for_code_and_data(monkeypatch, tmp_path):
    source = tmp_path / 'source'; source.mkdir()
    (source / 'main.py').write_text('pass\n')
    data = tmp_path / 'data'; data.mkdir(); (data / 'part.bin').write_bytes(b'data')
    budgets = []
    original = planner.snapshot
    def observed(*args, **kwargs):
        budgets.append(kwargs.get('max_bytes'))
        return original(*args, **kwargs)
    monkeypatch.setattr(planner, 'snapshot', observed)
    request = {'schema': 'marketmaker.research_offload_workflow.v1', 'submission_id': 'budget-check',
        'jobs': [{'id': 'job', 'kind': 'producer', 'runtime': 'python',
            'capsule': {'source': str(source)}, 'entrypoint': 'main.py',
            'inputs': {'data': {'mode': 'bundle', 'source': str(data)}},
            'outputs': {'result': {'type': 'json', 'path': 'artifacts/result.json'}}}]}
    planner.plan(request, tmp_path / 'plan', max_object_mb=12288)
    assert budgets == [12288 << 20, 12288 << 20]
