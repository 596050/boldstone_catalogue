"""Immutable input failures identify their cause without accepting changed bytes."""
import json

import pytest

from research_workflows.common import inventory, verify_tree


def test_added_bytecode_missing_and_same_size_changed_source_are_distinguished(tmp_path):
    (tmp_path / 'model.py').write_text('old')
    (tmp_path / 'removed.csv').write_text('source')
    expected = inventory(tmp_path)
    (tmp_path / 'model.py').write_text('new')
    (tmp_path / 'removed.csv').unlink()
    (tmp_path / '__pycache__').mkdir()
    (tmp_path / '__pycache__/model.pyc').write_bytes(b'bytecode')
    with pytest.raises(ValueError, match='file tree differs from its immutable manifest') as error:
        verify_tree(tmp_path, expected)
    detail = json.loads(str(error.value).split('; ', 1)[1])
    assert str(tmp_path) in str(error.value)
    assert detail == {
        'added': {'count': 1, 'paths': ['__pycache__/model.pyc']},
        'missing': {'count': 1, 'paths': ['removed.csv']},
        'changed': {'count': 1, 'paths': ['model.py']},
    }


def test_diagnostics_bound_samples_but_count_every_difference(tmp_path):
    (tmp_path / 'source').write_bytes(b'original')
    expected = inventory(tmp_path)
    for i in range(23):
        (tmp_path / f'extra_{i:03d}').touch()
    with pytest.raises(ValueError) as error:
        verify_tree(tmp_path, expected)
    detail = json.loads(str(error.value).split('; ', 1)[1])
    assert detail == {'added': {'count': 23, 'paths': [f'extra_{i:03d}' for i in range(5)]}}


def test_unchanged_manifest_and_original_inventory_limits_still_apply(tmp_path):
    (tmp_path / 'source').write_bytes(b'original')
    expected = inventory(tmp_path)
    assert verify_tree(tmp_path, expected) is None
    with pytest.raises(ValueError, match='file tree exceeds its size/count budget'):
        verify_tree(tmp_path, expected, max_bytes=1)


@pytest.mark.parametrize('expected', [None, []])
def test_malformed_manifest_keeps_a_controlled_rejection(tmp_path, expected):
    with pytest.raises(ValueError, match='invalid file table'):
        verify_tree(tmp_path, expected)
