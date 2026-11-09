"""Timing is bounded observation, not a changed quota policy or result identity."""
from concurrent.futures import ThreadPoolExecutor
import json
from types import SimpleNamespace

import pytest

from research_workflows import operation_timing as timing
from research_workflows import project_storage
from research_workflows import publication
from research_workflows import cli


def test_disabled_timing_reads_no_clock_and_keeps_no_rows(monkeypatch):
    def forbidden():
        raise AssertionError('no timing clock should run')
    monkeypatch.setattr(timing, '_clock', forbidden)
    with timing.phase('unobserved', additional_bytes=17) as details:
        details['stored_bytes'] = 19
    assert timing._active.get() is None


def test_nested_phases_have_exact_parentage_and_overlapping_intervals(monkeypatch):
    ticks = iter(range(10))
    monkeypatch.setattr(timing, '_clock', lambda: next(ticks))
    with timing.collect() as report:
        with timing.phase('parent', additional_bytes=17) as details:
            details['stored_bytes'] = 19
            with timing.phase('child'):
                pass
    assert report['status'] == 'COMPLETED' and report['elapsed_seconds'] == 5
    assert [(r['phase'], r['parent_index'], r['elapsed_seconds']) for r in report['phases']] == [
        ('parent', None, 3), ('child', 0, 1)]
    assert report['phases'][0]['details'] == {'additional_bytes': 17, 'stored_bytes': 19}
    assert report['dropped_phases'] == 0


def test_exception_identity_and_context_restoration_are_preserved():
    error = OSError('generated diagnostic failure')
    with pytest.raises(OSError) as caught:
        with timing.collect() as report:
            with timing.phase('failing'):
                raise error
    assert caught.value is error
    assert report['status'] == report['phases'][0]['status'] == 'FAILED'
    assert report['phases'][0]['exception_type'] == 'OSError'
    assert timing._active.get() is timing._parent.get() is None


def test_nested_collectors_and_threads_do_not_mix_observations():
    with timing.collect() as outer:
        with timing.phase('outer'):
            with timing.collect() as inner:
                with timing.phase('inner'):
                    pass
            with timing.phase('after-inner'):
                pass
    assert [r['phase'] for r in outer['phases']] == ['outer', 'after-inner']
    assert [r['parent_index'] for r in outer['phases']] == [None, 0]
    assert [r['phase'] for r in inner['phases']] == ['inner']
    assert inner['phases'][0]['parent_index'] is None
    def worker(label):
        with timing.collect() as report:
            with timing.phase(label):
                pass
        return report
    with ThreadPoolExecutor(max_workers=2) as pool:
        a, b = pool.map(worker, ('A', 'B'))
    assert [r['phase'] for r in a['phases']] == ['A']
    assert [r['phase'] for r in b['phases']] == ['B']


def test_trace_limit_is_explicit_without_skipping_operations():
    done = []
    with timing.collect(max_phases=2) as report:
        for i in range(7):
            with timing.phase('call'):
                done.append(i)
    assert done == list(range(7))
    assert len(report['phases']) == 2 and report['dropped_phases'] == 5


@pytest.mark.parametrize('value', [True, 0, -1, 1.5, 100001])
def test_invalid_trace_limits(value):
    with pytest.raises(ValueError):
        with timing.collect(max_phases=value):
            pass


def project(tmp_path, monkeypatch, *, used=40, free=10 << 20):
    instance = object.__new__(project_storage.Project)
    instance.storage = {'max_store_mb': 2, 'min_free_mb': 1}
    calls = []
    monkeypatch.setattr(instance, 'bulk', lambda: tmp_path)
    monkeypatch.setattr(instance, 'local_capacity', lambda: calls.append('local'))
    monkeypatch.setattr(project_storage, 'live_tree_bytes', lambda root: calls.append('scan') or used)
    monkeypatch.setattr(project_storage.shutil, 'disk_usage', lambda root: SimpleNamespace(free=free))
    return instance, calls


def test_capacity_records_exact_inputs_without_replacing_live_checks(tmp_path, monkeypatch):
    instance, calls = project(tmp_path, monkeypatch)
    with timing.collect() as report:
        assert instance.capacity(123) == tmp_path
        assert instance.capacity(0) == tmp_path
    assert calls == ['scan', 'local', 'scan', 'local']
    roots = [r for r in report['phases'] if r['phase'] == 'storage.capacity']
    assert len(roots) == 2
    assert roots[0]['details'] == {'additional_bytes': 123, 'stored_bytes': 40,
        'free_bytes': 10 << 20, 'store_limit_bytes': 2 << 20,
        'required_free_bytes': (1 << 20) + 123}
    assert [r['phase'] for r in report['phases']].count('storage.scan_bulk_tree') == 2


@pytest.mark.parametrize('used,free', [(3 << 20, 10 << 20), (40, 0)])
def test_capacity_rejection_is_identical_with_and_without_timing(tmp_path, monkeypatch, used, free):
    instance, calls = project(tmp_path, monkeypatch, used=used, free=free)
    with pytest.raises(project_storage.StorageUnavailable) as plain:
        instance.capacity(123)
    with pytest.raises(project_storage.StorageUnavailable) as measured:
        with timing.collect() as report:
            instance.capacity(123)
    assert str(plain.value) == str(measured.value)
    assert calls == ['scan', 'scan']
    assert report['status'] == report['phases'][0]['status'] == 'FAILED'


def test_report_retains_failure_and_refuses_existing_or_late_output(tmp_path):
    path = tmp_path / 'failure.json'
    error = RuntimeError('original')
    with pytest.raises(RuntimeError) as caught:
        with timing.record_to(path, 'operation'):
            raise error
    assert caught.value is error
    assert json.loads(path.read_text())['status'] == 'FAILED'
    with pytest.raises(FileExistsError):
        with timing.record_to(path, 'must-not-run'):
            pytest.fail('existing report must block before the operation')
    late = tmp_path / 'late.json'
    with pytest.raises(RuntimeError, match='operation completed but timing report'):
        with timing.record_to(late, 'succeeded'):
            late.write_text('concurrent owner')
    assert late.read_text() == 'concurrent owner'
    failed = tmp_path / 'late-failed.json'
    with pytest.raises(RuntimeError) as caught:
        with timing.record_to(failed, 'failed'):
            failed.write_text('another owner')
            raise error
    assert caught.value is error and failed.read_text() == 'another owner'


def test_cli_profile_preserves_publication_result_and_default_output(tmp_path, monkeypatch, capsys):
    origins = tmp_path / 'origins.json'; origins.write_text('{}')
    monkeypatch.setattr(project_storage, 'Project', lambda path: object())
    def publish(*args):
        with timing.phase('generated.publication'):
            return {'jobs_executed': 0, 'immutable_result': 'same'}
    monkeypatch.setattr(publication, 'import_collection', publish)
    argv = ['publish', '--config', str(tmp_path / 'unused'), '--result', str(tmp_path), '--origins', str(origins)]
    assert cli.main(argv) == 0
    plain = capsys.readouterr().out
    output = tmp_path / 'TIMING.json'
    assert cli.main([*argv, '--timing-output', str(output)]) == 0
    assert capsys.readouterr().out == plain
    report = json.loads(output.read_text())
    assert report['status'] == 'COMPLETED'
    assert [r['phase'] for r in report['phases']] == ['publication.import_collection', 'generated.publication']
    before = output.read_bytes()
    assert cli.main([*argv, '--timing-output', str(output)]) == 2
    assert output.read_bytes() == before


def test_cli_failure_is_still_an_error_and_has_separate_timing(tmp_path, monkeypatch, capsys):
    origins = tmp_path / 'origins.json'; origins.write_text('{}')
    monkeypatch.setattr(project_storage, 'Project', lambda path: object())
    def fail(*args):
        raise project_storage.StorageUnavailable('generated reserve exhaustion')
    monkeypatch.setattr(publication, 'import_collection', fail)
    output = tmp_path / 'TIMING.json'
    assert cli.main(['publish', '--config', str(tmp_path / 'unused'), '--result', str(tmp_path),
        '--origins', str(origins), '--timing-output', str(output)]) == 2
    assert json.loads(capsys.readouterr().err)['reason'] == 'generated reserve exhaustion'
    report = json.loads(output.read_text())
    assert report['status'] == 'FAILED' and report['exception_type'] == 'StorageUnavailable'
