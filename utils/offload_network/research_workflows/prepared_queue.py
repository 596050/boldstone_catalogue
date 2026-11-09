"""Bounded durable scheduling before bulk storage permits normal enqueue.

Only already compiled plans are accepted. Their exact metadata and bundled
archives are retained locally before reporting scheduled; original paths can
then disappear. No candidate code is imported, executed, or re-packaged here.
"""
import json
import os
import shutil
import tempfile
import time
from pathlib import Path

from lib.file_lock import file_lock
from lib.live_files import live_tree_bytes
from .common import atomic, load, name, no_links, sha, sync_directory
from .project_queue import ProjectQueue
from .project_storage import Project, StorageUnavailable
from .spec import identity, output_plan, selected_ports, validate


def plan_files(plan):
    plan = Path(plan).resolve(strict=True)
    spec = validate(load(plan / 'WORKFLOW.json'))
    metadata = ['WORKFLOW.json', 'OUTPUT_PLAN.json', 'PLAN_RECEIPT.json']
    if load(plan / 'PLAN_RECEIPT.json')['workflow_sha256'] != identity(spec) or load(plan / 'OUTPUT_PLAN.json') != output_plan(spec):
        raise ValueError('compiled plan identity differs')
    if 'batch' in spec:
        if load(plan / 'BATCH_PLAN.json') != spec['batch']:
            raise ValueError('compiled batch identity differs')
        metadata.append('BATCH_PLAN.json')
    required = {job['capsule'] for job in spec['jobs']}
    required.update(ref['object_sha256'] for job in spec['jobs'] for ref in job['inputs'].values() if ref['mode'] == 'bundle')
    files = {}
    for relative in [*metadata, *('objects/' + key + '.tar.gz' for key in sorted(required))]:
        path = no_links(plan / relative, plan)
        value = {'bytes': path.stat().st_size, 'sha256': sha(path)}
        if relative.startswith('objects/') and value['sha256'] != Path(relative).name.removesuffix('.tar.gz'):
            raise ValueError('compiled object archive changed')
        files[relative] = value
    required_ports = {job['id'] + '.research_evidence' for job in spec['jobs'] if job['kind'] in {'testing', 'testing_stage'}}
    if spec['return_policy']['profile'] != 'full_results' or required_ports - set(selected_ports(spec)):
        raise ValueError('scheduled research requires full results and all native evidence')
    return spec, files


def root(project):
    return no_links(project.state / 'scheduled', project.root)


def list_scheduled(project):
    rows = []
    for path in sorted(root(project).glob('*/SCHEDULED.json')):
        no_links(path, project.root)
        receipt = load(path)
        state_path = path.parent / 'STATE.json'
        state = load(state_path) if state_path.exists() else {'state': 'waiting_for_admission', 'next_at': 0}
        rows.append({**state, 'workflow_id': receipt['workflow_id'], 'worker': receipt['worker'],
                     'created_at': receipt['created_at'], 'origins': receipt['origins'],
                     'jobs': receipt['jobs'], 'retained_plan': str(path.parent / 'plan')})
    return rows


def schedule(config, plan, worker, origins):
    with ProjectQueue(config) as queue:
        project = queue.project
        project.require_active_worker(worker)
        spec, files = plan_files(plan)
        binding = project.binding(spec, origins)
        profile = project.worker(worker)
        key = name(spec['submission_id'])
        directory = root(project) / key
        with file_lock(root(project) / 'schedule.lock', timeout=0), file_lock(queue.root / 'queue.lock', timeout=0):
            existing = queue.db.execute('SELECT spec,binding,worker FROM requests WHERE id=?', (key,)).fetchone()
            if existing:
                if [json.loads(value) for value in existing] != [spec, binding, profile]:
                    raise ValueError('workflow already queued with a different identity')
                return {'workflow_id': key, 'state': 'already_enqueued'}
            intent = {'schema': 'marketmaker.scheduled_research_plan.v1', 'workflow_id': key,
                      'workflow_sha256': identity(spec), 'worker': worker, 'worker_binding': profile,
                      'binding': binding, 'origins': binding['origins'], 'files': files,
                      'jobs': [{'id': j['id'], 'kind': j['kind'], 'depends_on': j['depends_on']} for j in spec['jobs']]}
            if directory.exists():
                old = load(directory / 'SCHEDULED.json')
                if {k: v for k, v in old.items() if k != 'created_at'} != intent:
                    raise ValueError('scheduled workflow already has different sealed content')
                return {'workflow_id': key, 'state': load(directory / 'STATE.json')['state']}
            pending = queue.db.execute("SELECT count(*) FROM requests WHERE phase!='completed'").fetchone()[0]
            pending += sum(row['state'] not in {'enqueued', 'cancelled'} for row in list_scheduled(project))
            if pending >= project.recovery['max_pending']:
                raise StorageUnavailable('scheduled and enqueued workflow limit exhausted')
            project.local_capacity()
            additional = sum(value['bytes'] for value in files.values()) + (256 << 10)
            if live_tree_bytes(project.state) + additional > project.storage['max_local_state_mb'] << 20:
                raise StorageUnavailable('sealed plan exceeds bounded local queue capacity; register large datasets separately')
            if shutil.disk_usage(project.root).free < additional + (project.storage['local_min_free_mb'] << 20):
                raise StorageUnavailable('sealed plan would consume the local free-space reserve')
            root(project).mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(prefix='.scheduling-', dir=root(project)) as temporary:
                target = Path(temporary) / 'retained'
                for relative, expected in files.items():
                    source = no_links(Path(plan).resolve() / relative, Path(plan).resolve())
                    copied = target / 'plan' / relative
                    copied.parent.mkdir(parents=True, exist_ok=True)
                    with source.open('rb') as incoming, copied.open('xb') as outgoing:
                        shutil.copyfileobj(incoming, outgoing, 1 << 20)
                        outgoing.flush(); os.fsync(outgoing.fileno())
                    if copied.stat().st_size != expected['bytes'] or sha(copied) != expected['sha256'] or sha(source) != expected['sha256']:
                        raise ValueError('plan changed during durable scheduling')
                intent['created_at'] = time.time()
                atomic(target / 'SCHEDULED.json', intent)
                atomic(target / 'STATE.json', {'state': 'waiting_for_admission', 'next_at': 0, 'updated_at': time.time()})
                os.replace(target, directory)
                sync_directory(directory.parent)
            return {'workflow_id': key, 'state': 'waiting_for_admission', 'retained_bytes': additional,
                    'original_plan_needed': False}


def service(config, workflow):
    project = Project(config)
    directory = no_links(root(project) / name(workflow), project.root)
    with file_lock(directory / 'service.lock', timeout=0):
        state = load(directory / 'STATE.json')
        if state['state'] in {'enqueued', 'cancelled', 'needs_attention'} or state.get('next_at', 0) > time.time():
            return state
        receipt = load(directory / 'SCHEDULED.json')
        try:
            spec, files = plan_files(directory / 'plan')
            if files != receipt['files'] or identity(spec) != receipt['workflow_sha256']:
                raise ValueError('retained scheduled plan changed')
            if project.worker(receipt['worker']) != receipt['worker_binding'] or project.binding(spec, receipt['origins']) != receipt['binding']:
                raise ValueError('scheduled source or worker binding changed')
            with ProjectQueue(config) as queue:
                queue.enqueue(directory / 'plan', receipt['worker'], receipt['origins'])
            state = {'state': 'enqueued', 'next_at': 0, 'updated_at': time.time()}
        except (StorageUnavailable, TimeoutError) as exc:
            state = {'state': 'waiting_for_storage' if isinstance(exc, StorageUnavailable) else 'waiting_for_admission',
                     'error': str(exc), 'next_at': time.time() + project.recovery['poll_seconds'], 'updated_at': time.time()}
        except Exception as exc:
            state = {'state': 'needs_attention', 'error': type(exc).__name__ + ': ' + str(exc)[:300],
                     'next_at': 0, 'updated_at': time.time()}
        atomic(directory / 'STATE.json', state)
        return state


def reset(config, workflow, *, cancel=False):
    project = Project(config)
    directory = no_links(root(project) / name(workflow), project.root)
    with file_lock(directory / 'service.lock', timeout=0), ProjectQueue(config) as queue, file_lock(project.state / 'queue.lock', timeout=0):
        load(directory / 'SCHEDULED.json')
        if queue.db.execute('SELECT 1 FROM requests WHERE id=?', (workflow,)).fetchone():
            raise ValueError('workflow is already enqueued; use its normal worker cancel or retry-transfer operation')
        state = {'state': 'cancelled' if cancel else 'waiting_for_admission', 'next_at': 0, 'updated_at': time.time()}
        atomic(directory / 'STATE.json', state)
        return state
