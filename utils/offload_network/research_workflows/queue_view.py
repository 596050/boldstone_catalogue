"""Small read-only worker queue observations; no artifact walks or job claims."""
from contextlib import closing
import json
import shutil
import sqlite3
import time
from pathlib import Path
from urllib.parse import urlsplit

from .common import load, no_links


def describe(rows, nodes, *, capacity, slots, free_bytes, min_free_mb):
    running = [row for row in rows if row['state'] == 'running']
    payloads = {row['id']: json.loads(row['payload'] or '{}') for row in rows}
    def storage(payload):
        return 3 * sum(item.get('size_bytes') or 0 for item in payload.get('inputs', [])) + (payload.get('template', {}).get('max_work_mb', 0) << 20)
    reserved = sum(storage(payloads[row['id']]) for row in running)
    used = {key: sum(payloads[row['id']].get('template', {}).get(key, 0) for row in running) for key in capacity}
    by_job = {node['job_id']: node for node in nodes if node['job_id']}
    jobs = []
    for row in rows:
        node = by_job.get(row['id'], {})
        payload = payloads[row['id']]
        template = payload.get('template', {})
        required = (min_free_mb << 20) + reserved + storage(payload)
        reasons = []
        if row['state'] == 'queued':
            if free_bytes is None:
                reasons.append('storage_unavailable')
            elif free_bytes < required:
                reasons.append('storage')
            if len(running) >= slots:
                reasons.append('execution_slots')
            reasons.extend(key for key, limit in capacity.items() if used[key] + template.get(key, 0) > limit)
        receipt = json.loads(row.get('receipt') or '{}')
        phase = receipt.get('worker_phase')
        phase = (phase if isinstance(phase, dict) and phase.get('job_id') == row['id']
                 and phase.get('attempt') == row['attempt'] else None)
        jobs.append({
            'job_id': row['id'], 'workflow_id': node.get('workflow'), 'node_id': node.get('id'),
            'state': row['state'], 'node_state': node.get('state'), 'attempt': row['attempt'],
            'created_at': row['created'], 'updated_at': row['updated'],
            'resources': {key: template.get(key) for key in ('cpus', 'memory_mb', 'pids', 'max_work_mb', 'timeout_s')},
            'wait_reasons': reasons, 'required_free_bytes': required if row['state'] == 'queued' else None,
            'free_shortfall_bytes': max(0, required - free_bytes) if row['state'] == 'queued' and free_bytes is not None else None,
            'exit_code': receipt.get('exit_code'), 'error': receipt.get('error') or node.get('error'),
            **({'worker_phase': phase} if phase else {}),
        })
    for node in nodes:
        if not node['job_id']:
            jobs.append({'workflow_id': node['workflow'], 'node_id': node['id'], 'job_id': None,
                         'state': node['state'], 'node_state': node['state'], 'attempt': node['attempt'],
                         'wait_reasons': ['dependencies_or_admission'] if node['state'] == 'pending' else [],
                         'error': node['error']})
    return {'schema': 'marketmaker.live_worker_queue.v1', 'observed_at': time.time(),
            'jobs': jobs, 'execution_slots': slots, 'running_jobs': len(running),
            'capacity': capacity, 'resources_reserved': used, 'free_bytes': free_bytes,
            'minimum_free_bytes': min_free_mb << 20, 'execution_storage_reserved_bytes': reserved,
            'storage_observation_is_reservation': False}


def read_rows(db):
    rows = [dict(row) for row in db.execute('SELECT id,state,attempt,created,updated,payload,receipt FROM jobs ORDER BY sequence')]
    nodes = [dict(row) for row in db.execute('SELECT workflow,id,state,attempt,job_id,error FROM workflow_nodes ORDER BY workflow,id')]
    return rows, nodes


def snapshot(worker):
    try:
        free = shutil.disk_usage(worker.root).free
    except OSError:
        free = None
    with worker.db_lock:
        rows, nodes = read_rows(worker.db)
    return describe(rows, nodes, capacity=worker.capacity, slots=worker.concurrency,
                    free_bytes=free, min_free_mb=worker.min_free_mb)


def local_snapshot(config, profile):
    """Explicit local compatibility adapter for workers predating /v2/queue.

    Caller authenticates to the worker first. The supplied configuration must
    match its loopback endpoint and token; no worker DB is ever opened writable.
    This observation does not assert a particular controller startup code hash.
    """
    config = Path(config).resolve(strict=True)
    raw = load(config)
    url = urlsplit(profile['url'])
    if url.hostname not in {'localhost', '127.0.0.1', '::1'} or url.port != raw['port']:
        raise ValueError('local worker configuration does not match the loopback endpoint')
    token_path = (config.parent / raw['token_file']).resolve(strict=True)
    if token_path.read_text().strip() != Path(profile['token_file']).read_text().strip():
        raise ValueError('local worker credentials differ from the configured endpoint')
    state = (config.parent / raw['root']).resolve(strict=True)
    database = no_links(state / 'jobs.sqlite3', state)
    try:
        free = shutil.disk_usage(state).free
    except OSError:
        free = None
    # A sqlite connection context only finishes its transaction; it does not
    # close the connection. Repeated fallback polls must release their handles.
    with closing(sqlite3.connect(database.as_uri() + '?mode=ro', uri=True, timeout=2)) as db:
        db.row_factory = sqlite3.Row
        db.execute('BEGIN')
        rows, nodes = read_rows(db)
    value = describe(rows, nodes, capacity=raw['workflows']['capacity'], slots=raw['concurrency'],
                     free_bytes=free, min_free_mb=raw['min_free_mb'])
    value['observation_source'] = 'explicit_local_read_only_database_and_authenticated_health'
    value['startup_controller_identity'] = 'NOT_ASSERTED'
    return value
