"""I/O measurements must preserve bytes and respect explicit scratch limits."""
import hashlib

import pytest

from research_workflows.io_probe import main, run


def options(**changes):
    return {'rows': 1024, 'rounds': 2, 'buffers': [8192, 1048576],
            'max_bytes': 8 << 20, **changes}


def test_byte_identity_raw_write_accounting_and_alternated_order(tmp_path):
    report = run(tmp_path / 'trials', **options())
    assert report['status'] == 'BYTE_IDENTICAL'
    assert [t['buffer'] for t in report['trials']] == [8192, 1048576, 1048576, 8192]
    for trial in report['trials']:
        data = (tmp_path / 'trials' / trial['path']).read_bytes()
        assert hashlib.sha256(data).hexdigest() == report['payload_sha256']
        assert sum(w['written'] for w in trial['raw_writes']) == len(data) == trial['bytes']
        assert trial['raw_write_calls'] == len(trial['raw_writes'])
    assert report['medians']['8192']['raw_write_calls'] > report['medians']['1048576']['raw_write_calls']
    assert report['trial_files_retained'] is True
    assert report['performance_qualification'] == 'NOT_ESTABLISHED'


@pytest.mark.parametrize('changes', [
    {'rows': True}, {'rows': 0}, {'rows': 8193}, {'rounds': 0}, {'rounds': 9},
    {'buffers': [8192]}, {'buffers': [8192, 8192]}, {'buffers': [8192, 1]},
    {'buffers': [8192, True]}, {'max_bytes': 1}, {'max_bytes': 65 << 20}])
def test_invalid_or_over_budget_probe_does_not_create_scratch(tmp_path, changes):
    with pytest.raises(ValueError):
        run(tmp_path / 'trials', **options(**changes))
    assert not (tmp_path / 'trials').exists()


def test_existing_trial_directory_and_report_are_not_overwritten(tmp_path):
    scratch = tmp_path / 'existing'
    scratch.mkdir()
    with pytest.raises(FileExistsError):
        run(scratch, **options())
    result = tmp_path / 'REPORT.json'
    result.write_text('retained')
    with pytest.raises(FileExistsError):
        main(['--directory', str(tmp_path / 'new'), '--output', str(result),
              '--rows', '8', '--rounds', '1', '--buffer-bytes', 'default', '1048576',
              '--max-bytes', str(1 << 20)])
    assert result.read_text() == 'retained' and not (tmp_path / 'new').exists()
