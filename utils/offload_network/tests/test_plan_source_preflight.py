"""Static source/output conflicts must fail before any expensive object capture."""
from copy import deepcopy

import pytest

from research_workflows import planner


@pytest.mark.parametrize('location', ['capsule', 'input'])
def test_late_source_containment_conflict_precedes_all_snapshots(monkeypatch, tmp_path, location):
    early = tmp_path / 'early'; early.mkdir()
    broad = tmp_path / 'broad'; broad.mkdir()
    job = {'id': 'first', 'kind': 'producer', 'runtime': 'python',
           'capsule': {'source': str(early)}, 'entrypoint': 'main.py',
           'outputs': {'value': {'type': 'json', 'path': 'artifacts/value.json'}}}
    later = {**job, 'id': 'later', 'capsule': 'a'*64}
    if location == 'capsule': later['capsule'] = {'source': str(broad), 'include': ['main.py']}
    else: later['inputs'] = {'data': {'mode': 'bundle', 'source': str(broad), 'include': ['data.bin']}}
    request = {'schema': 'marketmaker.research_offload_workflow.v1', 'submission_id': 'static-check',
               'jobs': [job, later]}
    original = deepcopy(request)
    def no_snapshot(*args, **kwargs):
        pytest.fail('static invalid selection reached expensive snapshot')
    monkeypatch.setattr(planner, 'snapshot', no_snapshot)
    output = broad / 'plan'
    with pytest.raises(ValueError, match='plan output cannot be inside'):
        planner.plan(request, output)
    assert not output.exists()
    assert request == original


@pytest.mark.parametrize('relative', ['sources', 'unused/../sources'])
def test_relative_selection_is_resolved_before_snapshot(monkeypatch, tmp_path, relative):
    def no_snapshot(*args, **kwargs):
        pytest.fail('relative containment reached snapshot')
    monkeypatch.setattr(planner, 'snapshot', no_snapshot)
    request = {'schema': 'marketmaker.research_offload_workflow.v1', 'submission_id': 'relative-check',
               'jobs': [{'capsule': {'source': relative}}]}
    with pytest.raises(ValueError, match='plan output cannot be inside'):
        planner.plan(request, tmp_path / 'sources/plan', base=tmp_path)
    assert not (tmp_path / 'sources').exists()


def test_missing_artifact_dependency_is_rejected_before_capture(monkeypatch, tmp_path):
    def no_snapshot(*args, **kwargs):
        pytest.fail('invalid workflow reached expensive snapshot')
    monkeypatch.setattr(planner, 'snapshot', no_snapshot)
    producer = {'id': 'producer', 'kind': 'producer', 'runtime': 'python',
        'capsule': {'source': str(tmp_path / 'source')}, 'entrypoint': 'main.py',
        'outputs': {'value': {'type': 'json', 'path': 'artifacts/value.json'}}}
    consumer = {**producer, 'id': 'consumer', 'inputs': {
        'upstream': {'mode': 'artifact_ref', 'job': 'producer', 'output': 'value'}}}
    request = {'schema': 'marketmaker.research_offload_workflow.v1',
        'submission_id': 'dependency-check', 'jobs': [producer, consumer]}
    with pytest.raises(ValueError, match='explicit dependency'):
        planner.plan(request, tmp_path / 'plan')
    assert not (tmp_path / 'plan').exists()


@pytest.mark.parametrize('identical', [True, False])
def test_checkpoint_capsule_identity_is_decided_from_captured_bytes(tmp_path, identical):
    from research_workflows.common import load
    for name, content in [('one', 'same'), ('two', 'same' if identical else 'different')]:
        source = tmp_path / name; source.mkdir(); (source / 'main.py').write_text(content)
    first = {'id': 'first', 'kind': 'testing_stage', 'runtime': 'python',
        'capsule': {'source': str(tmp_path / 'one')},
        'testing': {'through': 'metrics', 'stop_after': 'models'}}
    second = {'id': 'second', 'kind': 'testing_stage', 'runtime': 'python',
        'capsule': {'source': str(tmp_path / 'two')}, 'depends_on': ['first'],
        'testing': {'through': 'metrics', 'stop_after': 'metrics', 'resume_input': 'checkpoint'},
        'inputs': {'checkpoint': {'mode': 'artifact_ref', 'job': 'first', 'output': 'checkpoint'}}}
    request = {'schema': 'marketmaker.research_offload_workflow.v1',
        'submission_id': 'content-check', 'jobs': [first, second]}
    if identical:
        planner.plan(request, tmp_path / 'plan')
        jobs = load(tmp_path / 'plan/WORKFLOW.json')['jobs']
        assert jobs[0]['capsule'] == jobs[1]['capsule'] != '0'*64
    else:
        with pytest.raises(ValueError, match='preserve identity'):
            planner.plan(request, tmp_path / 'plan')
        assert not (tmp_path / 'plan/WORKFLOW.json').exists()
