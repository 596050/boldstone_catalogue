"""Resume confirmed, unattempted deletions after a verified filename pass.

Never reset an old operation. Preserve its rejection and original confirmation;
commit linked replacement operations and their outbox entry in one transaction.
"""
import json

from delete_dropbox import fingerprint
from live_review import check_sources
from projection import Projection
from store import Conflict, now


def remaining_jobs(service, row):
    manager = service.app.deletions
    body = row['payload']['body']
    if body.get('confirmed') is not True:
        raise Conflict('This deletion has no prior confirmation.')
    if row['kind'] == 'delete_batch':
        batch = manager.batch(body['batch_id'])
        if body.get('confirm_files') != batch['payload']['files']:
            raise Conflict('The original deletion confirmation changed.')
        jobs = [manager.job(oid) for oid in batch['payload']['operation_ids']]
    else:
        jobs = [manager.job(body['operation_id'])]
        if body.get('confirm_file_id') != jobs[0]['file_id']:
            raise Conflict('The original file confirmation changed.')
    remaining = [j for j in jobs if j['state'] not in ('deleted', 'already_absent')]
    if not remaining or not any(j['state'] == 'rejected' for j in remaining):
        raise Conflict('There is no rejected, unattempted deletion to reconcile.')
    for job in remaining:
        if not job['payload'].get('queue_confirmed_at') or not (
                job['state'] == 'prepared' and not job['result'] or
                job['state'] == 'rejected' and job['result'].get('delete_attempted') is False):
            raise Conflict('An operation may already have reached Dropbox. Check its result; it cannot be resumed.')
    return remaining


def check_context(service, jobs):
    manager = service.app.deletions
    check_sources(manager.cat)
    view = Projection(manager.cat, service.store.all())
    for job in jobs:
        manager.binding(job['file_id'], view)
        keeper = job['payload'].get('keeper_binding')
        if keeper:
            manager.binding(keeper['id'], view)
            if view.cid(keeper['id']) == view.cid(job['file_id']):
                raise Conflict('The retained image is now grouped with the deletion target.')
        if fingerprint(manager.context(job['file_id'], view)) != job['payload']['context_hash']:
            raise Conflict('This image\u2019s catalogue use changed. Review the affected sculptures again.')


def resume_verified_rename(service, ident):
    with service.store.connect() as db:
        raw = db.execute('SELECT * FROM background_jobs WHERE id=?', (ident,)).fetchone()
    if not raw:
        raise ValueError('Unknown background job.')
    original = service.unpack(raw)
    replacement = original['result'].get('replaced_by')
    if original['state'] == 'superseded' and replacement:
        return service.get(replacement)  # Lost HTTP response: no second queue entry.
    if original['kind'] not in ('delete', 'delete_batch') or original['state'] != 'needs_review':
        raise Conflict('Only a rejected deletion can be reconciled with a verified rename.')
    with service.writer() as acquired:
        if not acquired or service.reservation():
            raise Conflict('Wait for the current Dropbox writer before checking this rename.')
        with service.store.connect() as db:
            if db.execute("SELECT 1 FROM background_jobs WHERE state='uncertain' LIMIT 1").fetchone():
                raise Conflict('Check the interrupted Dropbox job before resuming another deletion.')
        jobs = remaining_jobs(service, original)
        with service.app.catalogue_lock:
            check_context(service, jobs)
        validations = []
        for job in jobs:
            p = job['payload']
            validation = service.app.deletions.runner({'action': 'validate', 'binding': p['binding'],
                'reviewed': p['file'], 'keeper': p.get('keeper'), 'rename_runtime': str(service.store.root)})
            if job['state'] == 'rejected' and not validation.get('rename_reconciliation'):
                raise Conflict('The rejection was not caused solely by a verified filename change. Review this file again.')
            validations.append(validation)
        new_ident = 'rename-recovery-' + ident
        with service.app.catalogue_lock, service.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            current = service.unpack(db.execute('SELECT * FROM background_jobs WHERE id=?', (ident,)).fetchone())
            if current != original or remaining_jobs(service, current) != jobs:
                raise Conflict('This job changed while its rename was checked.')
            check_context(service, jobs)
            active = service.deletion_activity(db)
            for job in jobs:
                keeper = job['payload'].get('keeper_binding')
                if job['file_id'] in active or keeper and active.get(keeper['id'], {}).get('kind') == 'delete':
                    raise Conflict('One of these files now belongs to another deletion job. Check Jobs.')
            batch_id = 'rename-' + original['payload']['body']['batch_id'] if original['kind'] == 'delete_batch' else None
            operation_ids, confirmed_files, files = [], [], []
            for job, validation in zip(jobs, validations):
                oid = 'rename-' + job['id']
                p = {**job['payload'], 'resumed_from': job['id'], 'rename_validation': validation}
                if batch_id:
                    p['batch_id'] = batch_id
                db.execute('INSERT INTO deletion_jobs VALUES(?,?,?,?,?,?)',
                           (oid, job['file_id'], 'prepared', now(), json.dumps(p), '{}'))
                operation_ids.append(oid)
                confirmed_files.append({'id': job['file_id'], 'revision': p['file']['revision']})
                files.append({'id': job['file_id'], 'name': validation['file']['name'], 'reviewed_name': p['file']['name']})
            if batch_id:
                batch_payload = {'operation_ids': operation_ids, 'files': confirmed_files,
                                 'source': jobs[0]['payload']['source'],
                                 'expires_at': min(j['payload']['expires_at'] for j in jobs),
                                 'resumed_from': original['payload']['body']['batch_id']}
                db.execute('INSERT INTO deletion_batches VALUES(?,?,?,?,?)',
                           (batch_id, 'prepared', now(), json.dumps(batch_payload), '{}'))
                body = {'batch_id': batch_id, 'confirm_files': confirmed_files, 'confirmed': True}
            else:
                body = {'operation_id': operation_ids[0], 'confirm_file_id': jobs[0]['file_id'], 'confirmed': True}
            service.insert(db, new_ident, original['kind'], {'body': body, 'asset_ids': [j['file_id'] for j in jobs],
                'files': files, 'resumed_from': ident,
                'label': f'Delete {len(jobs)} reviewed file' + ('s' if len(jobs) != 1 else '')})
            db.execute("UPDATE background_jobs SET state='superseded',updated_at=?,result=? WHERE id=?",
                       (now(), json.dumps({**original['result'], 'replaced_by': new_ident,
                        'message': 'Original confirmation retained; resumed after verifying the filename-only change.'}), ident))
        return service.get(new_ident)
