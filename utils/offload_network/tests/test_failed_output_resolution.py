"""Verified producer failures must not instruct users to retrieve nonexistent data."""
import pytest

from research_workflows.common import atomic, digest, load
from research_workflows.resolver import resolve


def retained(directory, state='failed', error='TimeoutError: job exceeded 600 seconds', *, remote=False):
    workflow = {'schema': 'marketmaker.research_offload_workflow.v1',
                'submission_id': 'fixture-resolution', 'workflow': 'research', 'jobs': []}
    manifest = {'workflow': workflow, 'objects': {}, 'final': True,
        'remote_only': {'checks.checks': 'a'*64} if remote else {}, 'required_local_missing': [],
        'output_plan': {'jobs': {'checks': {'checks': {'type': 'tree', 'path': 'artifacts/checks'}}}},
        'status': {'workflow_id': 'fixture-resolution', 'state': 'completed_with_errors',
                   'nodes': [{'id': 'checks', 'state': state, 'error': error,
                              'outputs': {'output_status': 'VERIFIED' if remote else 'NOT_PRODUCED'}}]}}
    identity = digest(manifest)
    atomic(directory/'DELIVERY.json', {'manifest': manifest, 'delivery_sha256': identity})
    atomic(directory/'INDEX.json', {})
    atomic(directory/'COLLECTION_RECEIPT.json', {
        'delivery_sha256': identity, 'collected_objects': [], 'workflow_id': 'fixture-resolution',
        'final': True, 'workflow_state': 'completed_with_errors',
        'remote_only': manifest['remote_only'], 'required_local_missing': []})


@pytest.mark.parametrize('state,error', [
    ('failed', 'TimeoutError: job exceeded 600 seconds'),
    ('cancelled', 'explicit cancellation before execution'),
    ('interrupted', 'worker lost before output publication'),
    ('blocked_dependency', 'a required upstream producer failed'),
])
def test_unproduced_terminal_output_reports_verified_cause(tmp_path, state, error):
    retained(tmp_path, state, error)
    with pytest.raises(ValueError, match='OUTPUT_NOT_PRODUCED') as caught:
        resolve(tmp_path, 'checks.checks')
    assert state in str(caught.value) and error in str(caught.value)
    assert 'retrieve' not in str(caught.value)


def test_produced_remote_output_remains_a_retrieval_requirement(tmp_path):
    retained(tmp_path, remote=True)
    with pytest.raises(ValueError, match='BLOCKED_DATA.*retrieve'):
        resolve(tmp_path, 'checks.checks')


def test_unverified_failure_cannot_replace_collection_integrity_error(tmp_path):
    retained(tmp_path)
    path = tmp_path/'DELIVERY.json'
    value = load(path)
    value['manifest']['status']['nodes'][0]['error'] = 'unverified replacement cause'
    atomic(path, value)
    with pytest.raises(ValueError, match='collection identity changed'):
        resolve(tmp_path, 'checks.checks')


def test_undeclared_port_is_not_attributed_to_producer_failure(tmp_path):
    retained(tmp_path)
    with pytest.raises(ValueError, match='BLOCKED_DATA'):
        resolve(tmp_path, 'checks.unrequested')
