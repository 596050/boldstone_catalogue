"""Idle history must not consume reconciliation reads or block resumed work."""
from copy import deepcopy

import pytest

from tests.test_research_workflows import worker as worker_fixture, compiled, drive

worker = worker_fixture


def test_idle_completed_dag_does_not_load_terminal_receipts(tmp_path, worker, monkeypatch):
    spec, _ = compiled(tmp_path, worker)
    key = spec['submission_id']
    worker.workflows.submit(spec)
    before = drive(worker, key)
    assert before['state'] == 'completed'
    delivery = worker.workflows.delivery(key)
    original = worker.workflows._row

    def forbidden(workflow):
        raise AssertionError('idle reconciliation loaded a terminal workflow')

    with monkeypatch.context() as patch:
        patch.setattr(worker.workflows, '_row', forbidden)
        worker.workflows.tick()
        worker.workflows.tick()
    assert worker.workflows.status(key) == before
    assert worker.workflows.delivery(key) == delivery
    assert original(key)[1]


def test_active_dag_uses_terminal_parents_without_revisiting_completed_dag(tmp_path, worker, monkeypatch):
    spec, _ = compiled(tmp_path, worker)
    old = spec['submission_id']
    worker.workflows.submit(spec)
    assert drive(worker, old)['state'] == 'completed'
    active = deepcopy(spec); active['submission_id'] = 'active-with-completed-history'
    worker.workflows.submit(active)
    original = worker.workflows._row
    reads = []

    def checked(key):
        assert key != old, 'completed history leaked into active reconciliation'
        reads.append(key)
        return original(key)

    monkeypatch.setattr(worker.workflows, '_row', checked)
    result = drive(worker, active['submission_id'])
    assert result['state'] == 'completed'
    assert reads and set(reads) == {active['submission_id']}
    assert all(n['outputs']['output_status'] == 'VERIFIED' for n in result['nodes'])


@pytest.mark.parametrize('attempt_limit', [1, 2])
def test_explicit_resume_reactivates_terminal_workflow_and_keeps_attempts(tmp_path, worker, monkeypatch, attempt_limit):
    def limits(request):
        for job in request['jobs']:
            job['max_attempts'] = attempt_limit

    spec, _ = compiled(tmp_path, worker, edit=limits)
    key = spec['submission_id']
    worker.workflows.submit(spec)
    worker.workflows.tick()
    # A stopped, unclaimed job provides a controlled interrupted-worker receipt.
    # This fixture does not interrupt any real process or alter live research.
    with worker.transaction() as db:
        jobs = db.execute("SELECT id FROM jobs WHERE state='queued'").fetchall()
        assert jobs
        for (job_id,) in jobs:
            db.execute("UPDATE jobs SET state='interrupted',receipt=? WHERE id=?",
                       ('{"error":"controlled stopped attempt","exit_code":null}', job_id))
    terminal = drive(worker, key)
    assert terminal['terminal'] and any(n['state'] == 'interrupted' for n in terminal['nodes'])
    attempts = [tuple(row) for row in worker.db.execute(
        'SELECT node,attempt,state,manifest FROM workflow_attempts WHERE workflow=? ORDER BY node,attempt', (key,))]
    assert attempts
    with monkeypatch.context() as patch:
        patch.setattr(worker.workflows, '_row', lambda _: (_ for _ in ()).throw(AssertionError('terminal tick read')))
        worker.workflows.tick()
    resumed = worker.workflows.resume(key)
    if attempt_limit == 1:
        assert resumed == terminal
        return
    assert not resumed['terminal']
    final = drive(worker, key)
    assert final['state'] == 'completed'
    assert any(n['attempt'] == 2 for n in final['nodes'])
    after = {tuple(row[:2]): tuple(row) for row in worker.db.execute(
        'SELECT node,attempt,state,manifest FROM workflow_attempts WHERE workflow=? ORDER BY node,attempt', (key,))}
    assert all(after[tuple(row[:2])] == row for row in attempts)
