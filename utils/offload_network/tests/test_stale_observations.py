"""An unavailable worker must not inflate live execution counts."""
from copy import deepcopy

import pytest

from research_workflows.observations import job_view


@pytest.mark.parametrize('state', ['running', 'queued', 'waiting', 'awaiting_admission'])
def test_stale_active_state_is_unobserved_and_original_is_preserved(state):
    node = {'state': state, 'node_id': 'models', 'wait_reasons': []}
    original = deepcopy(node)
    result = job_view(node, stale=True, source='source_queue_last_known', worker_available=False)
    assert result['state'] == 'unobserved'
    assert result['last_known_state'] == state
    assert result['wait_reasons'] == ['worker_unavailable']
    assert node == original


@pytest.mark.parametrize('state', ['succeeded', 'failed', 'cancelled', 'interrupted', 'blocked_dependency'])
def test_retained_terminal_state_remains_a_fact(state):
    result = job_view({'state': state}, stale=True, source='worker', worker_available=False)
    assert result['state'] == state
    assert 'last_known_state' not in result


def test_fresh_authenticated_running_job_remains_running():
    result = job_view({'state': 'running'}, stale=False, source='worker', worker_available=True)
    assert result['state'] == 'running'
    assert result['stale'] is False


def test_expired_observation_requires_refresh_even_if_previous_contact_succeeded():
    result = job_view({'state': 'running'}, stale=True, source='worker', worker_available=True)
    assert result['state'] == 'unobserved'
    assert result['wait_reasons'] == ['fresh_observation_required']


def test_retirement_preserves_worker_binding_but_refuses_new_work(tmp_path):
    import json
    from pathlib import Path
    from research_workflows.project_storage import Project
    (tmp_path / 'research').mkdir()
    value = json.loads((Path(__file__).parents[1] / 'research_workflows/project.json').read_text())
    value['project_root'] = str(tmp_path)
    value['workers'] = {'local': {'url': 'http://127.0.0.1:12345', 'token_file': str(tmp_path / 'token')}}
    config = tmp_path / 'project.json'
    config.write_text(json.dumps(value))
    before = Project(config).worker('local')
    value = json.loads(config.read_text())
    value['workers']['local']['retired_reason'] = 'all historical requests returned; temporary worker closed'
    config.write_text(json.dumps(value))
    after = Project(config)
    assert after.worker('local') == before
    with pytest.raises(ValueError, match='worker is retired'):
        after.require_active_worker('local')
