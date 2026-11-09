"""A local research run must honor explicitly declared job and storage budgets."""
from copy import deepcopy
import json

import pytest

from research_workflows import local


@pytest.mark.parametrize('limits', [[], {'image': 'other'}, {'cpus': True}, {'memory_mb': 1.5},
                                   {'timeout_s': float('nan')}, {'max_work_mb': 0}, {'cpus': 10485761}])
def test_bad_resources_fail_before_starting_worker_or_creating_directory(tmp_path, limits):
    output = tmp_path / 'worker'
    with pytest.raises(ValueError):
        local.run(tmp_path / 'plan', output, image='test-image', runtime_resources=limits)
    assert not output.exists()


@pytest.mark.parametrize('override,reserve,object_limit', [(None, 256, 256),
    ({'timeout_s': 7200, 'memory_mb': 2048, 'max_input_mb': 1024, 'max_output_mb': 256, 'max_work_mb': 1024}, 4096, 1024)])
def test_explicit_limits_and_aggregate_capacity_reach_worker_config(monkeypatch, tmp_path, override, reserve, object_limit):
    original = deepcopy(override)
    plan = tmp_path / 'plan'; plan.mkdir()
    (plan / 'WORKFLOW.json').write_text(json.dumps({'jobs': [{'runtime': 'python'}]}))
    def stop_before_worker(*args, **kwargs):
        raise RuntimeError('configuration captured without starting Docker')
    monkeypatch.setattr(local.subprocess, 'Popen', stop_before_worker)
    output = tmp_path / 'worker'
    with pytest.raises(RuntimeError, match='configuration captured'):
        local.run(tmp_path / 'plan', output, image='test-image', concurrency=2,
                  runtime_resources=override, min_free_mb=reserve, max_object_mb=object_limit)
    config = json.loads((output / 'worker.json').read_text())
    profile = config['workflows']['runtimes']['python']
    assert profile['timeout_s'] == (7200 if override else 300)
    assert profile['memory_mb'] == (2048 if override else 1024)
    assert config['min_free_mb'] == config['workflows']['min_free_mb'] == reserve
    assert config['workflows']['max_object_mb'] == object_limit
    assert config['workflows']['input_transport'] == 'bind'
    for key in ('cpus', 'memory_mb', 'pids', 'max_work_mb'):
        assert config['workflows']['capacity'][key] == profile[key] * 2
    assert override == original


@pytest.mark.parametrize('requested', [['python'], ['math', 'python']])
def test_runtime_mismatch_fails_before_worker_start_or_input_upload(monkeypatch, tmp_path, requested):
    plan = tmp_path / 'plan'; plan.mkdir()
    (plan / 'WORKFLOW.json').write_text(json.dumps({'jobs': [{'runtime': value} for value in requested]}))
    def unexpected_start(*args, **kwargs):
        pytest.fail('an incompatible plan must not start a worker or upload inputs')
    monkeypatch.setattr(local.subprocess, 'Popen', unexpected_start)
    output = tmp_path / 'worker'
    with pytest.raises(ValueError, match='local worker runtime math cannot run requested runtimes: python'):
        local.run(plan, output, image='test-image', runtime='math')
    assert not output.exists()


def test_aggregate_limit_and_storage_reserve_are_validated_before_mutation(tmp_path):
    for options in ({'runtime_resources': {'memory_mb': 6000000}, 'concurrency': 2}, {'min_free_mb': True}):
        output = tmp_path / 'worker'
        with pytest.raises(ValueError): local.run(tmp_path / 'plan', output, image='test-image', **options)
        assert not output.exists()


@pytest.mark.parametrize('limit', [True, 0, -1, 1.5, float('nan'), float('inf'), 1048577])
def test_invalid_object_limit_fails_before_creating_worker(tmp_path, limit):
    output = tmp_path / 'worker'
    with pytest.raises(ValueError):
        local.run(tmp_path / 'plan', output, image='test-image', max_object_mb=limit)
    assert not output.exists()


def test_cli_passes_explicit_runtime_limits_and_reserve(monkeypatch, tmp_path, capsys):
    from research_workflows.cli import main
    limits = tmp_path / 'limits.json'
    limits.write_text('{"timeout_s":7200,"memory_mb":2048}')
    seen = {}
    def run(*args, **kwargs):
        seen.update(kwargs)
        return {'status': 'TEST_CAPTURE'}
    monkeypatch.setattr(local, 'run', run)
    assert main(['local', '--plan', str(tmp_path / 'plan'), '--dir', str(tmp_path / 'worker'),
                 '--image', 'test-image', '--runtime-resources', str(limits), '--min-free-mb', '4096',
                 '--max-object-mb', '1024', '--max-return-mb', '4096', '--input-transport', 'docker-volume']) == 0
    assert seen['runtime_resources'] == {'timeout_s': 7200, 'memory_mb': 2048}
    assert seen['min_free_mb'] == 4096
    assert seen['max_object_mb'] == 1024
    assert seen['max_return_mb'] == 4096
    assert seen['input_transport'] == 'docker-volume'
    assert 'TEST_CAPTURE' in capsys.readouterr().out


@pytest.mark.parametrize('limit', [True, 0, -1, 1.5, float('nan'), float('inf'), 1048577])
def test_invalid_return_limit_fails_before_creating_worker(tmp_path, limit):
    output = tmp_path / 'worker'
    with pytest.raises(ValueError):
        local.run(tmp_path / 'plan', output, image='test-image', max_return_mb=limit)
    assert not output.exists()


@pytest.mark.parametrize('transport', ['', True, None, 'tmpfs', []])
def test_invalid_input_transport_does_not_create_worker(tmp_path, transport):
    output = tmp_path / 'worker'
    with pytest.raises(ValueError, match='input_transport'):
        local.run(tmp_path / 'plan', output, image='test-image', input_transport=transport)
    assert not output.exists()
