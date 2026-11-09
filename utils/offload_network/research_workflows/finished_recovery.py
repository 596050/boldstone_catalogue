"""Explicit recovery of already-exited Docker attempts after controller loss."""
import json
import os
from datetime import datetime
from pathlib import Path

from lib.live_files import live_tree_bytes
from offload_service.core import ID, TERMINAL, CapacityError
from v2.seal import verify_seal

from .common import atomic, load, no_links, sha


def recovery_ids(value):
    if (not isinstance(value, list) or len(value) > 128
            or any(not isinstance(v, str) or not ID.fullmatch(v) for v in value)
            or len(set(value)) != len(value)):
        raise ValueError("recover_completed requires unique explicit worker job IDs")
    return frozenset(value)


def pending(worker, requested):
    if worker.backend != "docker":
        raise ValueError("completed-attempt recovery requires Docker exit evidence")
    rows = [dict(r) for r in worker.db.execute("SELECT * FROM jobs WHERE state IN ('preparing','running')")]
    if any(r['id'] not in requested for r in rows):
        raise ValueError("unselected unresolved jobs require separate inspection")
    for identity in requested:
        row = worker.db.execute("SELECT state FROM jobs WHERE id=?", (identity,)).fetchone()
        if row is None:
            raise ValueError("unknown completed-recovery job ID")
        if row[0] not in TERMINAL | {'running'}:
            raise ValueError('completed recovery cannot start queued or unprepared jobs')
    if any(r['state'] != 'running' or not r['attempt'] or r['cancel'] for r in rows):
        raise ValueError("only uncancelled running records can recover completed results")
    return rows


def check_container(root, row, payload, container):
    """Require the exact stopped attempt, image, command, mounts and limits."""
    state, config, host = container['State'], container['Config'], container['HostConfig']
    work = root / 'work' / row['attempt']
    uid = f'{os.getuid()}:{os.getgid()}' if os.name != 'nt' else '1000:1000'
    limits = payload['template']
    if (container['Name'] != '/' + row['attempt'] or container['Image'] != payload['image_id']
            or container['RestartCount'] != 0 or state['Status'] != 'exited'
            or state['Running'] or state['Paused'] or state['Restarting'] or state['Dead']
            or state['OOMKilled'] or type(state['ExitCode']) is not int
            or config['Entrypoint'] != ['python']
            or config['Cmd'] != ['-I', '/work/runner.py', '/work/manifest.json']
            or config['WorkingDir'] != '/work' or config['User'] != uid
            or host['NetworkMode'] != 'none' or not host['ReadonlyRootfs'] or host['Privileged']
            or host.get('CapAdd') or host['CapDrop'] != ['ALL']
            or 'no-new-privileges' not in host['SecurityOpt']
            or host['Memory'] != limits['memory_mb'] << 20
            or host['MemorySwap'] != limits['memory_mb'] << 20
            or host['NanoCpus'] != round(limits['cpus'] * 1e9)
            or host['PidsLimit'] != limits['pids']):
        raise ValueError('completed container identity, lifetime, isolation or limits differ')
    mounts = {m['Destination']: m for m in container['Mounts']}
    if len(mounts) != len(container['Mounts']):
        raise ValueError('duplicate completed container mounts')
    for destination, source, writable in (('/work', work, True), ('/work/blobs', work / 'blobs', False)):
        mount = mounts.get(destination, {})
        if mount.get('Type') != 'bind' or Path(mount.get('Source', '')).resolve() != source.resolve() or mount.get('RW') is not writable:
            raise ValueError('completed container belongs to another workspace')
    references = payload.get('workflow_mounts', [])
    expected = {'/work', '/work/blobs'} | {'/work/blobs/' + m['target'] for m in references}
    if set(mounts) != expected or any(mounts['/work/blobs/' + m['target']]['RW'] for m in references):
        raise ValueError('completed workflow input mounts differ')
    if payload.get('workflow_input_transport', 'bind') == 'docker-volume' and references:
        transport = load(root / 'workflow_input_transports' / row['attempt'] / 'TRANSPORT.json')
        if transport['attempt'] != row['attempt'] or transport['status'] != 'VERIFIED' or transport['owned_volumes_removed']:
            raise ValueError('original volume verification receipt is unavailable')
        volumes = {(item['object_sha256'], target): row['attempt'] + '-input-' + str(i)
                   for i, item in enumerate(transport['objects'])
                   for target in item.get('targets', [item['target']])}
        for reference in references:
            mount = mounts['/work/blobs/' + reference['target']]
            if mount['Type'] != 'volume' or mount['Name'] != volumes.get((reference['object_sha256'], reference['target'])):
                raise ValueError('completed input volume identity differs')
    else:
        for reference in references:
            mount = mounts['/work/blobs/' + reference['target']]
            source = root / 'workflows/objects' / reference['object_sha256'] / 'data'
            if mount['Type'] != 'bind' or Path(mount.get('Source', '')).resolve() != source.resolve():
                raise ValueError('completed bound input identity differs')
    start, end = (datetime.fromisoformat(state[k].replace('Z', '+00:00')) for k in ('StartedAt', 'FinishedAt'))
    if not 0 <= (end - start).total_seconds() <= limits['timeout_s']:
        raise ValueError('completed container exceeded its declared runtime limit')
    return state['ExitCode']


def finish(worker, rows):
    checked = []
    for row in rows:
        payload = json.loads(row['payload'])
        if payload['backend'] != 'docker':
            raise ValueError('completed recovery cannot infer local-process termination')
        container = json.loads(worker._docker('inspect', row['attempt']))
        if len(container) != 1:
            raise ValueError('completed container is not unique')
        exit_code = check_container(worker.root, row, payload, container[0])
        work = no_links(worker.root / 'work' / row['attempt'], worker.root)
        verify_seal(worker.root / 'bundles' / payload['seal'], expected_sha256=payload['seal_sha256'])
        if live_tree_bytes(work, exclude_root_dirs={'blobs'}) > payload['template']['max_work_mb'] << 20:
            raise CapacityError('completed attempt exceeded its original work budget')
        checked.append((row, payload, container[0], exit_code, work))
    for row, payload, container, exit_code, work in checked:
        recovery = worker.root / 'recoveries' / row['attempt']
        recovery.mkdir(parents=True, exist_ok=True)
        intent = {'schema': 'marketmaker.completed_attempt_recovery.v1',
            'job_id': row['id'], 'attempt': row['attempt'], 'previous_receipt': json.loads(row['receipt'] or '{}'),
            'container_id': container['Id'], 'container_state': container['State'],
            'image_id': payload['image_id'], 'seal_sha256': payload['seal_sha256'],
            'new_execution': False, 'native_runner_status_sha256': sha(work / 'status.json')}
        if (recovery / 'INTENT.json').exists() and load(recovery / 'INTENT.json') != intent:
            raise ValueError('completed recovery intent changed')
        atomic(recovery / 'INTENT.json', intent)
        state, receipt = worker._collect_completed_result(row['id'], payload, work, exit_code, recovery=True)
        # No terminal receipt or free slot is published before cleanup succeeds.
        worker._remove_container(row['attempt'])
        receipt.update(backend='docker', image_id=payload['image_id'], inputs=payload['inputs'],
                       seal_sha256=payload['seal_sha256'], recovered_completion=intent)
        receipt['recovery_implementation_sha256'] = {
            'finished_recovery.py': sha(Path(__file__)),
            'worker.py': sha(Path(__file__).with_name('worker.py')),
            'core.py': sha(Path(__file__).parents[1] / 'offload_service/core.py'),
        }
        worker._finish(row['id'], row['attempt'], state, receipt)
        atomic(recovery / 'COMPLETED.json', {**intent, 'state': state,
               'result_sha256': receipt['result_sha256'], 'container_termination_confirmed': True})
