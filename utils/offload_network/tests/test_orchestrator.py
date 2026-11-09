"""Durable scheduling, live monitoring and real source/worker reconciliation."""
import json
from pathlib import Path
import threading
import time
import urllib.error
import urllib.request

import pytest

from lib.file_lock import file_lock
from research_workflows.common import atomic, load, sha
from research_workflows.monitor import Monitor
from research_workflows.orchestrator import Orchestrator, run
from research_workflows.planner import plan
from research_workflows.prepared_queue import list_scheduled, reset, schedule, service
from research_workflows.project_queue import ProjectQueue
from research_workflows.project_storage import Project, StorageUnavailable
from research_workflows.queue_view import describe
from tests.test_parallel_workflows import request
from tests.test_project_return import project, api, worker, freeze


def test_schedule_survives_original_plan_loss_and_storage_wait(tmp_path, project, worker, monkeypatch):
    config, origins = project
    spec, compiled = freeze(tmp_path, worker)
    original = Project.capacity
    def full(*args, **kwargs):
        raise StorageUnavailable('fixture bulk disk full')
    monkeypatch.setattr(Project, 'capacity', full)
    first = schedule(config, compiled, 'local', origins)
    assert first['state'] == 'waiting_for_admission' and first['original_plan_needed'] is False
    assert schedule(config, compiled, 'local', origins)['state'] == 'waiting_for_admission'
    compiled.rename(tmp_path / 'original-plan-removed')
    waiting = service(config, spec['submission_id'])
    assert waiting['state'] == 'waiting_for_storage'
    with ProjectQueue(config) as queue:
        assert queue.status() == []
    monkeypatch.setattr(Project, 'capacity', original)
    reset(config, spec['submission_id'])
    assert service(config, spec['submission_id'])['state'] == 'enqueued'
    with ProjectQueue(config) as queue:
        assert len(queue.status()) == 1
        assert json.loads(queue._row(spec['submission_id'])['spec']) == spec


def test_tampered_pending_plan_is_not_admitted(tmp_path, project, worker):
    config, origins = project
    spec, compiled = freeze(tmp_path, worker)
    schedule(config, compiled, 'local', origins)
    retained = Path(list_scheduled(Project(config))[0]['retained_plan'])
    archive = next((retained / 'objects').glob('*.tar.gz'))
    archive.write_bytes(b'changed')
    assert service(config, spec['submission_id'])['state'] == 'needs_attention'
    with ProjectQueue(config) as queue:
        assert queue.status() == []


def test_scheduling_respects_local_budget_without_bulk_access(tmp_path, project, worker, monkeypatch):
    config, origins = project
    _, compiled = freeze(tmp_path, worker)
    settings = load(config); settings['storage']['max_local_state_mb'] = 1
    atomic(config, settings)
    state = Project(config).state
    state.mkdir(parents=True, exist_ok=True)
    (state / 'existing-metadata.bin').write_bytes(b'x' * (900 << 10))
    with pytest.raises(StorageUnavailable, match='local queue capacity|metadata capacity'):
        schedule(config, compiled, 'local', origins)
    assert list_scheduled(Project(config)) == []


def test_cancel_pending_preserves_plan_and_prevents_admission(tmp_path, project, worker):
    config, origins = project
    spec, compiled = freeze(tmp_path, worker)
    schedule(config, compiled, 'local', origins)
    pending = list_scheduled(Project(config))[0]
    before = sha(Path(pending['retained_plan']) / 'WORKFLOW.json')
    assert reset(config, spec['submission_id'], cancel=True)['state'] == 'cancelled'
    assert service(config, spec['submission_id'])['state'] == 'cancelled'
    assert sha(Path(pending['retained_plan']) / 'WORKFLOW.json') == before
    with ProjectQueue(config) as queue:
        assert queue.status() == []


def test_duplicate_scheduled_identity_is_rejected(tmp_path, project, worker):
    config, origins = project
    _, compiled = freeze(tmp_path, worker)
    schedule(config, compiled, 'local', origins)
    changed = {key: values[:1] for key, values in origins.items()}
    with pytest.raises(ValueError, match='different sealed content'):
        schedule(config, compiled, 'local', changed)


def test_worker_live_api_and_storage_reason(worker, api):
    live = api.request('/v2/queue')
    assert live['schema'] == 'marketmaker.live_worker_queue.v1' and live['jobs'] == []
    rows = [{'id': str(i), 'state': state, 'attempt': str(i) if state == 'running' else None,
             'created': 1, 'updated': 1, 'receipt': None,
             'payload': json.dumps({'inputs': [{'size_bytes': 1024}], 'template': {'max_work_mb': 16, 'cpus': 1}})}
            for i, state in enumerate(['running', 'queued'])]
    value = describe(rows, [], capacity={'cpus': 1}, slots=1, free_bytes=1, min_free_mb=8)
    pending = value['jobs'][1]
    assert set(pending['wait_reasons']) == {'storage', 'execution_slots', 'cpus'}
    assert pending['required_free_bytes'] == (40 << 20) + 6144
    assert rows[1]['attempt'] is None


def test_monitor_is_responsive_during_slow_observation(project, monkeypatch):
    config, _ = project
    orchestrator = Orchestrator(config, poll_seconds=.1)
    held, entered = threading.Event(), threading.Event()
    def slow(_):
        entered.set(); held.wait(5)
        return {'worker': 'local', 'available': True, 'observed_at': time.time(), 'jobs': []}
    monkeypatch.setattr(orchestrator, 'observe_worker', slow)
    monitor = Monitor(('127.0.0.1', 0), orchestrator)
    thread = threading.Thread(target=monitor.serve_forever, daemon=True); thread.start()
    try:
        started = time.monotonic(); orchestrator.tick()
        assert time.monotonic() - started < 1
        assert entered.wait(2)
        url = f'http://127.0.0.1:{monitor.server_port}'
        started = time.monotonic()
        with urllib.request.urlopen(url + '/api/queue', timeout=1) as response:
            assert json.load(response)['schema'] == 'marketmaker.live_research_queue.v1'
        assert time.monotonic() - started < 1
        with urllib.request.urlopen(url, timeout=1) as response:
            assert "frame-ancestors 'none'" in response.headers['Content-Security-Policy']
        for headers in ({'Host': 'untrusted.example'}, {'Origin': 'https://untrusted.example'}):
            with pytest.raises(urllib.error.HTTPError) as error:
                urllib.request.urlopen(urllib.request.Request(url + '/api/queue', headers=headers), timeout=1)
            assert error.value.code == 403
    finally:
        held.set(); monitor.shutdown(); monitor.server_close(); thread.join(5); orchestrator.close()


def test_second_coordinator_cannot_overwrite_live_status(project):
    config, _ = project
    orchestrator = Orchestrator(config)
    marker = {'state': 'running', 'owner': 'retained'}
    atomic(orchestrator.root / 'status.json', marker)
    try:
        with file_lock(orchestrator.root / 'owner.lock', timeout=0):
            with pytest.raises(TimeoutError):
                run(config, port=0)
        assert load(orchestrator.root / 'status.json') == marker
    finally:
        orchestrator.close(write_status=False)


def test_orchestrator_discovers_jobs_executes_and_returns_to_origins(tmp_path, project, worker, record_property):
    config, initial_origins = project
    settings = load(config)
    settings['recovery'].update(poll_seconds=.1, backoff_initial_seconds=.1, backoff_max_seconds=1)
    atomic(config, settings)
    compiled = tmp_path / 'orchestration-plan'
    spec = plan(request(tmp_path / 'orchestration-source', 'orchestration-live', delay='.7'), compiled)
    origins = {key: initial_origins['report'] for key in ('alpha', 'beta', 'gamma', 'compare')}
    orchestrator = Orchestrator(config, poll_seconds=.1)
    observed = set()
    worker.start()
    try:
        orchestrator.tick()  # Start the coordinator before any new job is queued.
        schedule(config, compiled, 'local', origins)
        compiled.rename(tmp_path / 'withdrawn-plan')
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            view = orchestrator.tick()
            observed.update(job['state'] for w in view['workflows'] for job in w['jobs'])
            if view['workflows'] and all(w['phase'] == 'completed' for w in view['workflows']):
                break
            time.sleep(.1)
        else:
            pytest.fail(json.dumps(orchestrator.snapshot(), default=str))
        assert len(view['workflows'][0]['publications']) == 4
        assert 'running' in observed and 'succeeded' in observed
        assert all(node['attempt'] == 1 for node in worker.workflows.status('orchestration-live')['nodes'])
        assert worker.db.execute('SELECT count(*) FROM jobs').fetchone()[0] == 4
        record_property('observed_states', sorted(observed))
        record_property('published_origins', view['workflows'][0]['publications'])
    finally:
        orchestrator.close()
