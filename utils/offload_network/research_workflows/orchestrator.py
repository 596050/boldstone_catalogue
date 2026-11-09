"""Continuous source reconciliation plus independently refreshed worker status.

The existing source queue owns immutable submissions and return paths. Workers
own execution claims. This coordinator starts bounded source-service processes,
not strategy processes, and never moves an admitted workflow to another worker.
"""
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import threading
import time
import urllib.error

from lib.file_lock import file_lock
from .client import Client
from .common import atomic, load, no_links, sha
from .prepared_queue import list_scheduled
from .project_queue import ProjectQueue
from .project_storage import Project
from .queue_view import local_snapshot
from .observations import job_view


class Orchestrator:
    def __init__(self, config, *, poll_seconds=3, transfers=2, observers=4,
                 request_timeout=3, local_workers=None):
        if not 0.1 <= poll_seconds <= 300 or not 1 <= transfers <= 16 or not 1 <= observers <= 16 or not 0.1 <= request_timeout <= 30:
            raise ValueError('invalid bounded orchestrator timing or concurrency')
        self.config = Path(config).resolve(strict=True)
        self.project = Project(self.config)
        self.root = no_links(self.project.state / 'orchestrator', self.project.root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.poll_seconds, self.transfers, self.request_timeout = poll_seconds, transfers, request_timeout
        self.local_workers = local_workers or {}
        if set(self.local_workers) - set(self.project.workers):
            raise ValueError('local worker mapping contains an unconfigured worker')
        self.pool = ThreadPoolExecutor(max_workers=observers, thread_name_prefix='offload-observer')
        self.observations, self.polls, self.processes, self.last_serviced = {}, {}, {}, {}
        self.stop = threading.Event()
        self.guard = threading.Lock()
        self.view = {'schema': 'marketmaker.live_research_queue.v1', 'state': 'starting', 'workflows': [], 'workers': []}
        self.started_at = time.time()
        self.process_errors = []

    def observe_worker(self, key):
        profile = self.project.worker(key)
        client = Client(profile['url'], Path(profile['token_file']).read_text().strip(), timeout=self.request_timeout)
        health = client.request('/v1/health')
        if health.get('ready') is not True:
            raise ValueError('worker reports not ready')
        try:
            result = client.request('/v2/queue')
            if result.get('schema') != 'marketmaker.live_worker_queue.v1':
                raise ValueError('worker queue schema differs')
            result['observation_source'] = 'authenticated_worker_queue_api'
        except urllib.error.HTTPError as exc:
            if exc.code != 404:
                raise
            if key not in self.local_workers:
                result = {'jobs': [], 'observed_at': time.time(), 'monitor_upgrade_required': True,
                          'observation_source': 'authenticated_health_only', 'error': 'Worker predates the live queue API; configure an explicit local adapter or update that worker.'}
            else:
                result = local_snapshot(self.local_workers[key], profile)
        return {**result, 'worker': key, 'url': profile['url'], 'health': health,
                'available': True, 'last_contact_at': time.time()}

    def observe_storage(self):
        result = {'observed_at': time.time(), 'host_free_bytes': shutil.disk_usage(self.project.root).free,
                  'host_minimum_free_bytes': self.project.storage['local_min_free_mb'] << 20,
                  'bulk_minimum_free_bytes': self.project.storage['min_free_mb'] << 20}
        try:
            bulk = self.project.bulk(create=False)
            result.update(bulk_free_bytes=shutil.disk_usage(bulk).free, bulk_path=str(bulk))
        except Exception as exc:
            result.update(bulk_free_bytes=None, error=type(exc).__name__)
        return result

    def _start_task(self, kind, workflow):
        command = [sys.executable, '-B', '-m', 'research_workflows',
                   'sync' if kind == 'sync' else 'admit-scheduled', '--config', str(self.config), '--workflow', workflow]
        env = dict(os.environ)
        env['PYTHONDONTWRITEBYTECODE'] = '1'
        env['PYTHONPATH'] = str(Path(__file__).resolve().parents[1]) + os.pathsep + env.get('PYTHONPATH', '')
        # All durable status/errors belong in the queues. Subprocess output must
        # neither block on an unread pipe nor accumulate unbounded logs.
        child = subprocess.Popen(command, cwd=self.project.root, env=env, stdin=subprocess.DEVNULL,
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.processes[(kind, workflow)] = child
        self.last_serviced[(kind, workflow)] = time.monotonic()

    def tick(self):
        """Never wait on remote I/O or an in-progress transfer to refresh status."""
        now = time.time()
        for key, child in list(self.processes.items()):
            code = child.poll()
            if code is not None:
                if code:
                    self.process_errors.append({'kind': key[0], 'workflow_id': key[1], 'exit_code': code, 'at': now})
                    self.process_errors = self.process_errors[-32:]
                del self.processes[key]
        for key, future in list(self.polls.items()):
            if future.done():
                try:
                    self.observations[key] = future.result()
                except Exception as exc:
                    old = self.observations.get(key, {})
                    self.observations[key] = {**old, 'worker': key, 'available': False,
                                              'last_error_at': now, 'error': type(exc).__name__}
                del self.polls[key]
        active_workers = [key for key, profile in self.project.workers.items() if not profile.get('retired_reason')]
        for key in [*active_workers, '@storage']:
            if key not in self.polls:
                self.polls[key] = self.pool.submit(self.observe_storage if key == '@storage' else self.observe_worker, *([] if key == '@storage' else [key]))
        with ProjectQueue(self.config) as queue:
            workflows = queue.status()
            records = {row['id']: dict(row) for row in queue.db.execute('SELECT id,spec,binding,last_status,created FROM requests')}
        scheduled = list_scheduled(self.project)
        due = [('sync', row['workflow_id']) for row in workflows
               if row['phase'] != 'completed' and row['state'] != 'needs_attention'
               and row['next_attempt_at'] <= now and row['worker'] in active_workers
               and self.observations.get(row['worker'], {}).get('available') is not False]
        due += [('schedule', row['workflow_id']) for row in scheduled if row['state'] not in {'enqueued', 'needs_attention', 'cancelled'} and row.get('next_at', 0) <= now]
        # Round-robin service avoids a held legacy synchronizer starving later
        # workflows. The source's per-workflow locks still fence all owners.
        for key in sorted(due, key=lambda key: self.last_serviced.get(key, 0)):
            if len(self.processes) >= self.transfers or self.stop.is_set():
                break
            if key not in self.processes:
                self._start_task(*key)
        worker_views = []
        worker_jobs = {}
        for key in self.project.workers:
            worker = dict(self.observations.get(key, {'worker': key, 'available': False, 'error': 'First observation pending'}))
            retired = self.project.workers[key].get('retired_reason')
            if retired:
                worker = {'worker': key, 'available': False, 'retired': True,
                          'retired_reason': retired, 'jobs': [], 'observed_at': now}
            worker['age_seconds'] = now - worker['observed_at'] if worker.get('observed_at') else None
            worker['stale'] = not retired and (not worker.get('available') or worker['age_seconds'] is None or worker['age_seconds'] > max(10, self.poll_seconds * 3))
            worker_views.append(worker)
            for job in worker.get('jobs', []):
                if job.get('workflow_id') and job.get('node_id'):
                    worker_jobs[(key, job['workflow_id'], job['node_id'])] = (job, worker['stale'])
        for row in workflows:
            record = records[row['workflow_id']]
            spec, binding = json.loads(record['spec']), json.loads(record['binding'])
            cached = {node['id']: node for node in json.loads(record['last_status'] or '{}').get('nodes', [])}
            row.update(created_at=record['created'], origins=binding['origins'], jobs=[])
            for job in spec['jobs']:
                live = worker_jobs.get((row['worker'], row['workflow_id'], job['id']))
                node = dict(live[0]) if live else {'node_id': job['id'], 'state': cached.get(job['id'], {}).get('state', 'awaiting_admission'), 'job_id': cached.get(job['id'], {}).get('job_id'), 'wait_reasons': []}
                node.update(kind=job['kind'], depends_on=job['depends_on'])
                node = job_view(node, stale=live[1] if live else row['phase'] != 'completed',
                                source='worker' if live else 'source_queue_last_known',
                                worker_available=self.observations.get(row['worker'], {}).get('available'))
                row['jobs'].append(node)
        known = {row['workflow_id'] for row in workflows}
        for row in scheduled:
            if row['workflow_id'] not in known:
                workflows.append({**row, 'phase': row['state'], 'jobs': [{**job, 'node_id': job['id'], 'state': row['state'], 'wait_reasons': [row['state']], 'stale': False} for job in row['jobs']]})
        storage = dict(self.observations.get('@storage', {}))
        storage['age_seconds'] = now - storage['observed_at'] if storage.get('observed_at') else None
        storage['stale'] = storage.get('available') is False or storage['age_seconds'] is None or storage['age_seconds'] > max(10, self.poll_seconds * 3)
        value = {'schema': 'marketmaker.live_research_queue.v1', 'state': 'running', 'pid': os.getpid(),
                 'updated_at': now, 'started_at': self.started_at, 'project_id': self.project.id,
                 'poll_seconds': self.poll_seconds, 'transfer_concurrency': self.transfers,
                 'active_source_tasks': [{'kind': key[0], 'workflow_id': key[1], 'pid': child.pid} for key, child in self.processes.items()],
                 'source_task_errors': self.process_errors, 'workers': worker_views, 'workflows': workflows,
                 'storage': storage,
                 'workflow_counts': dict(Counter(row['state'] for row in workflows)),
                 'job_counts': dict(Counter(job['state'] for row in workflows for job in row['jobs'])),
                 'execution_owner': 'original_worker', 'performance_qualification': 'NOT_ESTABLISHED'}
        atomic(self.root / 'status.json', value)
        with self.guard:
            self.view = value
        return value

    def snapshot(self):
        with self.guard:
            return {**self.view, 'snapshot_age_seconds': time.time() - self.view.get('updated_at', self.started_at)}

    def close(self, *, write_status=True):
        self.stop.set()
        # Only our source-service children stop. Remote executions remain owned
        # by their worker and are reconciled after reconnect, including a lost
        # admission/ACK response. Never signal unrelated syncs or worker PIDs.
        for child in self.processes.values():
            if child.poll() is None:
                child.terminate()
        for child in self.processes.values():
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill(); child.wait(timeout=5)
        self.processes.clear()
        self.pool.shutdown(wait=True, cancel_futures=True)
        with self.guard:
            self.view = {**self.view, 'state': 'stopped', 'stopped_at': time.time()}
        if write_status:
            atomic(self.root / 'status.json', self.view)


def run(config, *, host='127.0.0.1', port=8766, **kwargs):
    from .monitor import Monitor

    orchestrator = Orchestrator(config, **kwargs)
    owned = False
    try:
        with file_lock(orchestrator.root / 'owner.lock', timeout=0):
            owned = True
            monitor = Monitor((host, port), orchestrator)
            thread = threading.Thread(target=monitor.serve_forever, name='offload-monitor', daemon=True)
            thread.start()
            previous = {}
            for signum in (signal.SIGINT, signal.SIGTERM):
                previous[signum] = signal.signal(signum, lambda *_: orchestrator.stop.set())
            try:
                modules = sorted(Path(__file__).parent.glob('*.py'))
                atomic(orchestrator.root / 'SERVICE.json', {'pid': os.getpid(), 'started_at': time.time(),
                       'url': f'http://{host}:{monitor.server_port}', 'config': str(orchestrator.config),
                       'config_sha256': sha(orchestrator.config), 'controller_bindings': {p.name: sha(p) for p in modules}})
                print(json.dumps({'pid': os.getpid(), 'monitor': f'http://{host}:{monitor.server_port}',
                                  'project': orchestrator.project.id}), flush=True)
                while not orchestrator.stop.is_set():
                    try:
                        orchestrator.tick()
                    except Exception as exc:
                        # A source metadata failure must remain visible without
                        # cancelling remote work or stopping the read-only UI.
                        with orchestrator.guard:
                            orchestrator.view = {**orchestrator.view, 'state': 'degraded',
                                                 'coordinator_error': type(exc).__name__ + ': ' + str(exc)[:300]}
                    orchestrator.stop.wait(orchestrator.poll_seconds)
            finally:
                monitor.shutdown(); monitor.server_close(); thread.join(timeout=5)
                for signum, handler in previous.items():
                    signal.signal(signum, handler)
    finally:
        orchestrator.close(write_status=owned)
