"""Durable, reviewed per-file deletion jobs and global source tombstones."""
from pathlib import Path
import json
import secrets
import subprocess
import threading
import time

from delete_dropbox import fingerprint
from live_review import check_sources
from projection import Projection
from store import Conflict, now


class NativeRejected(ValueError):
    pass


class Deletions:
    def __init__(self, cat, store, runner=None):
        self.cat, self.store, self.runner = cat, store, runner or self.run_native
        self.lock = threading.Lock()
        with store.connect() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS deletion_jobs(
                id TEXT PRIMARY KEY, file_id TEXT NOT NULL, state TEXT NOT NULL,
                created_at TEXT NOT NULL, payload TEXT NOT NULL, result TEXT NOT NULL)''')
            db.execute('''CREATE TABLE IF NOT EXISTS deletion_batches(
                id TEXT PRIMARY KEY, state TEXT NOT NULL, created_at TEXT NOT NULL,
                payload TEXT NOT NULL, result TEXT NOT NULL)''')

    def run_native(self, request):
        python = self.cat.project / 'application/.venv/bin/python'
        if not python.is_file():
            raise ValueError('The existing Dropbox runtime is unavailable.')
        process = subprocess.run([str(python), str(Path(__file__).with_name('delete_dropbox.py')),
                                  '--project', str(self.cat.project)], input=json.dumps(request),
                                 text=True, capture_output=True, timeout=150,
                                 pass_fds=(self.writer_fd,) if getattr(self, 'writer_fd', None) is not None else ())
        try:
            result = json.loads(process.stdout)
        except ValueError:
            raise ValueError('Dropbox did not return a readable receipt. Check operation status before retrying.') from None
        if process.returncode or result.get('error'):
            if result.get('state') == 'rejected' and result.get('delete_attempted') is False:
                raise NativeRejected(result.get('error', 'The file no longer matches its deletion review.'))
            raise ValueError(result.get('error', 'Dropbox check failed.'))
        return result

    def binding(self, aid, view):
        asset = self.cat.assets.get(aid, {})
        original = asset.get('original', {})
        tombstone = view.deleted.get(view.cid(aid), {}).get('data', {}).get('state')
        if (asset.get('source') != 'Dropbox' or not aid.startswith('id:') or
            tombstone in ('executing', 'uncertain', 'deleted', 'already_absent')):
            raise ValueError('Choose a known Dropbox original image. For a previous deletion, check Deletion history.')
        path = (asset.get('provenance', {}).get('path') or '').removeprefix('ns:202238505/')
        return {'id': aid, 'content_hash': original.get('dropbox_content_hash'), 'bytes': original.get('bytes'),
                'name': asset.get('name', aid), 'path': path}

    def context(self, aid, view):
        canonical = view.cid(aid)
        products = []
        for pid in self.cat.products:
            if (canonical not in view.edges[pid] and canonical not in view.removed[pid]
                    and canonical not in view.deleted_associations[pid]):
                continue
            name = view.decision('field', pid, 'Name')
            products.append({'id': pid, 'name': name.get('value') if name.get('decision') == 'edit' else self.cat.products[pid]['name'],
                             'choice': view.record('image', pid, canonical),
                             'assignment': view.record('assignment', pid, canonical),
                             'source_primary': view.cid(self.cat.products[pid].get('primary_id')) == canonical})
        return {'products': products, 'aliases': view.member_ids(canonical),
                'shared_review': view.record('asset', '', canonical)}

    def prepare(self, body):
        check_sources(self.cat)
        view = Projection(self.cat, self.store.all())
        aid, keeper = body.get('asset_id', ''), body.get('keeper_id', '')
        if body.get('reason') not in ('duplicate', 'unwanted'):
            raise ValueError('Choose why this file should be deleted.')
        if body['reason'] == 'duplicate' and not keeper:
            raise ValueError('Choose the Dropbox image to keep for this duplicate.')
        if aid == keeper:
            raise ValueError('Choose a different image to keep.')
        if keeper and view.cid(aid) == view.cid(keeper):
            raise ValueError('These byte-identical files are grouped as one image. Deleting one while keeping another member is not supported here; review their files in Dropbox.')
        binding = self.binding(aid, view)
        keeper_binding = self.binding(keeper, view) if keeper else None
        native = self.runner({'action': 'inspect', 'binding': binding, 'keeper_binding': keeper_binding})
        # Missing local metadata/preview is not a reason to block review. Pin
        # current native bytes when present, before showing the confirmation.
        if native['file'].get('availability') != 'missing':
            binding.update(content_hash=native['file']['content_hash'], bytes=native['file']['bytes'])
        if keeper_binding:
            keeper_binding.update(content_hash=native['keeper']['content_hash'], bytes=native['keeper']['bytes'])
        context = self.context(aid, view)
        job_id = secrets.token_urlsafe(24)
        payload = {**native, 'binding': binding, 'keeper_binding': keeper_binding,
                   'reason': body['reason'], 'context': context, 'context_hash': fingerprint(context),
                   'source': self.cat.source, 'expires_at': time.time() + 600,
                   'dimensions': self.cat.assets[aid].get('original', {}).get('dimensions'),
                   'keeper_dimensions': self.cat.assets[keeper].get('original', {}).get('dimensions') if keeper else None}
        with self.store.connect() as db:
            db.execute('INSERT INTO deletion_jobs VALUES(?,?,?,?,?,?)',
                       (job_id, aid, 'prepared', now(), json.dumps(payload), '{}'))
        return {'operation_id': job_id, **payload}

    def job(self, job_id):
        with self.store.connect() as db:
            row = db.execute('SELECT * FROM deletion_jobs WHERE id=?', (job_id,)).fetchone()
        if not row:
            raise ValueError('Unknown deletion review. Open the file review again.')
        return {**dict(row), 'payload': json.loads(row['payload']), 'result': json.loads(row['result'])}

    def validate_batch(self, jobs):
        check_sources(self.cat)
        view = Projection(self.cat, self.store.all())
        targets = [view.cid(j['file_id']) for j in jobs]
        if len(set(targets)) != len(targets):
            raise ValueError('Choose each Dropbox image only once; duplicate files or display groups cannot share a deletion batch.')
        for job in jobs:
            p = job['payload']
            if job['state'] != 'prepared' or (not p.get('queue_confirmed_at') and time.time() > p['expires_at']):
                raise Conflict('A selected deletion review is no longer available. Review the selected files again.')
            self.binding(job['file_id'], view)
            keeper = p.get('keeper_binding')
            if keeper:
                if view.cid(keeper['id']) in targets:
                    raise ValueError('An image chosen to keep is also selected for deletion. Remove it from the selection.')
                self.binding(keeper['id'], view)
            if fingerprint(self.context(job['file_id'], view)) != p['context_hash']:
                raise Conflict('A selected image’s catalogue use changed. Review the selected files again.')

    def prepare_batch(self, body):
        ids = body.get('operation_ids')
        if not isinstance(ids, list) or not ids or any(not isinstance(j, str) for j in ids) or len(set(ids)) != len(ids):
            raise ValueError('Provide the unique deletion reviews for all selected files.')
        jobs = [self.job(j) for j in ids]
        self.validate_batch(jobs)
        if any(j['payload'].get('batch_id') for j in jobs):
            raise Conflict('These files already belong to a batch review. Prepare a new review.')
        batch_id = secrets.token_urlsafe(24)
        payload = {'operation_ids': ids,
                   'files': [{'id': j['file_id'], 'revision': j['payload']['file']['revision']} for j in jobs],
                   'source': self.cat.source, 'expires_at': min(j['payload']['expires_at'] for j in jobs)}
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            for job in jobs:
                current = db.execute('SELECT state,payload FROM deletion_jobs WHERE id=?', (job['id'],)).fetchone()
                if current['state'] != 'prepared' or json.loads(current['payload']).get('batch_id'):
                    raise Conflict('A selected deletion review changed. Prepare a new review.')
                db.execute('UPDATE deletion_jobs SET payload=? WHERE id=?',
                           (json.dumps({**job['payload'], 'batch_id': batch_id}), job['id']))
            db.execute('INSERT INTO deletion_batches VALUES(?,?,?,?,?)',
                       (batch_id, 'prepared', now(), json.dumps(payload), '{}'))
        return {'batch_id': batch_id, **payload}

    def batch(self, batch_id):
        with self.store.connect() as db:
            row = db.execute('SELECT * FROM deletion_batches WHERE id=?', (batch_id,)).fetchone()
        if not row:
            raise ValueError('Unknown selected-file deletion review.')
        return {**dict(row), 'payload': json.loads(row['payload']), 'result': json.loads(row['result'])}

    def batch_status(self, body):
        batch = self.batch(body.get('batch_id'))
        return {'batch_id': batch['id'], 'state': batch['state'], **batch['result']}

    def confirm_for_queue(self, body, batch=False, db=None):
        """Bind confirmation now; a queue wait does not expire that consent.

        Revision, sharing and catalogue-use checks still run at execution.
        The caller commits these confirmations and the outbox job together.
        """
        parent = self.batch(body.get('batch_id')) if batch else self.job(body.get('operation_id'))
        p = parent['payload']
        if body.get('confirmed') is not True:
            raise ValueError('Confirm the reviewed files before queueing deletion.')
        if (batch and body.get('confirm_files') != p['files']) or (not batch and body.get('confirm_file_id') != parent['file_id']):
            raise ValueError('Confirm the exact reviewed file IDs and revisions.')
        if parent['state'] != 'prepared':
            raise Conflict('This deletion already started. Check its existing job.')
        if not batch and p.get('batch_id'):
            raise ValueError('Confirm all files in this batch together.')
        jobs = [self.job(j) for j in p['operation_ids']] if batch else [parent]
        self.validate_batch(jobs)
        for job in jobs:
            payload = {**job['payload'], 'queue_confirmed_at': now()}
            current = db.execute('SELECT state,payload FROM deletion_jobs WHERE id=?', (job['id'],)).fetchone()
            if current['state'] != 'prepared' or json.loads(current['payload']).get('queue_confirmed_at'):
                raise Conflict('This file is already confirmed in another background job.')
            db.execute('UPDATE deletion_jobs SET payload=? WHERE id=?', (json.dumps(payload), job['id']))
        return jobs

    def execute_batch(self, body):
        batch = self.batch(body.get('batch_id'))
        p = batch['payload']
        if body.get('confirmed') is not True or body.get('confirm_files') != p['files']:
            raise ValueError('Confirm the complete reviewed file-ID and revision list before deleting.')
        if batch['state'] != 'prepared':
            return self.batch_status({'batch_id': batch['id']})
        jobs = [self.job(j) for j in p['operation_ids']]
        self.validate_batch(jobs)
        results = [{'operation_id': j['id'], 'file_id': j['file_id'], 'state': 'not_started'} for j in jobs]
        result = {'confirmation_at': now(), 'confirmed_files': p['files'], 'results': results}
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            current = db.execute('SELECT state FROM deletion_batches WHERE id=?', (batch['id'],)).fetchone()
            if current['state'] != 'prepared':
                raise Conflict('This batch already started. Check its results; do not repeat it.')
            db.execute("UPDATE deletion_batches SET state='executing',result=? WHERE id=?", (json.dumps(result), batch['id']))
        for index, job in enumerate(jobs):
            results[index]['state'] = 'executing'
            with self.store.connect() as db:
                db.execute('UPDATE deletion_batches SET result=? WHERE id=?', (json.dumps(result), batch['id']))
            try:
                item = self.execute({'operation_id': job['id'], 'confirm_file_id': job['file_id'],
                                     'confirmed': True, 'batch_id': batch['id']})
            except (ValueError, Conflict) as exc:
                item = {'state': 'rejected', 'message': str(exc), 'delete_attempted': False}
            except Exception:
                item = {'state': 'uncertain', 'message': 'The result is unconfirmed. Check Deletion history; remaining files were not attempted.'}
            results[index].update(item)
            with self.store.connect() as db:
                db.execute('UPDATE deletion_batches SET result=? WHERE id=?', (json.dumps(result), batch['id']))
            if item.get('state') not in ('deleted', 'already_absent'):
                break
        state = ('deleted' if all(r['state'] == 'deleted' for r in results) else
                 'completed' if all(r['state'] in ('deleted', 'already_absent') for r in results) else 'partial')
        with self.store.connect() as db:
            db.execute('UPDATE deletion_batches SET state=?,result=? WHERE id=?', (state, json.dumps(result), batch['id']))
        return {'batch_id': batch['id'], 'state': state, **result}

    def mark(self, db, job, state, result):
        db.execute('UPDATE deletion_jobs SET state=?,result=? WHERE id=?', (state, json.dumps(result), job['id']))
        old = self.store.unpack(db.execute("SELECT * FROM reviews WHERE kind='deletion' AND product_id='' AND item_id=?", (job['file_id'],)).fetchone())
        data = {'state': state, 'operation_id': job['id'], 'result': result,
                'reviewed_file': job['payload']['file'], 'reason': job['payload']['reason']}
        self.store._write(db, 'deletion', '', job['file_id'], data, old['version'] + 1,
                          self.cat.source['register_sha256'], old.get('original', job['payload']), old)

    def execute(self, body):
        if not self.lock.acquire(blocking=False):
            raise Conflict('Another deletion is being checked. Wait for its result.')
        try:
            job = self.job(body.get('operation_id'))
            p = job['payload']
            if p.get('batch_id'):
                batch = self.batch(p['batch_id'])
                if body.get('batch_id') != batch['id'] or batch['state'] != 'executing':
                    raise ValueError('Confirm all files in this batch together before deleting.')
            if body.get('confirm_file_id') != job['file_id'] or body.get('confirmed') is not True:
                raise ValueError('Confirm the exact reviewed Dropbox file before deleting.')
            if job['state'] != 'prepared':
                return {'operation_id': job['id'], 'state': job['state'], **job['result']}
            if not p.get('queue_confirmed_at') and time.time() > p['expires_at']:
                raise Conflict('This deletion review expired. Review the current file again.')
            check_sources(self.cat)
            view = Projection(self.cat, self.store.all())
            self.binding(job['file_id'], view)
            if p.get('keeper_binding'):
                if view.cid(job['file_id']) == view.cid(p['keeper_binding']['id']):
                    raise Conflict('The chosen keeper is now in the same grouped image. Nothing was deleted; review these duplicate files in Dropbox.')
                self.binding(p['keeper_binding']['id'], view)
            if fingerprint(self.context(job['file_id'], view)) != p['context_hash']:
                raise Conflict('This image’s catalogue use changed. Review the affected sculptures again.')
            with self.store.connect() as db:
                db.execute('BEGIN IMMEDIATE')
                current = db.execute('SELECT state FROM deletion_jobs WHERE id=?', (job['id'],)).fetchone()
                if current['state'] != 'prepared' or db.execute(
                    "SELECT 1 FROM deletion_jobs WHERE file_id=? AND state IN ('executing','uncertain','deleted','already_absent') AND id!=?",
                    (job['file_id'], job['id'])).fetchone():
                    raise Conflict('This file already has a deletion in progress or completed. Check its status.')
                self.mark(db, job, 'executing', {'confirmation_at': now(), 'confirmed_file_id': job['file_id']})
            try:
                result = self.runner({'action': 'execute', 'binding': p['binding'],
                                      'reviewed': p['file'], 'keeper': p.get('keeper')})
                state = result['state'] if result.get('state') in ('deleted', 'already_absent') and result.get('verified_absent') else 'uncertain'
            except NativeRejected as exc:
                result = {'message': str(exc), 'delete_attempted': False}
                state = 'rejected'
            except Exception:
                result = {'message': 'The result is unconfirmed. Use Check status; the app will not repeat the deletion.'}
                state = 'uncertain'
            result.update(state=state, confirmation_at=now(), confirmed_file_id=job['file_id'])
            with self.store.connect() as db:
                db.execute('BEGIN IMMEDIATE')
                self.mark(db, job, state, result)
            return {'operation_id': job['id'], **result}
        finally:
            self.lock.release()

    def check(self, body):
        if not self.lock.acquire(blocking=False):
            raise Conflict('A deletion is still running. Wait before checking its status.')
        try:
            job = self.job(body.get('operation_id'))
            if job['state'] not in ('executing', 'uncertain'):
                return {'operation_id': job['id'], 'state': job['state'], **job['result']}
            result = self.runner({'action': 'check', 'file_id': job['file_id']})
            state = 'deleted' if result.get('state') == 'deleted' and result.get('verified_absent') else 'uncertain'
            if state == 'deleted' and job['payload']['file'].get('availability') == 'missing':
                state = 'already_absent'
                result.update(delete_attempted=False, message='Already absent from Dropbox; leftover app entry removed.')
            if result.get('state') == 'present':
                result['message'] = 'The file is present in Dropbox. This job will not retry. Resolve the original request before trying again.'
            result['state'] = state
            with self.store.connect() as db:
                db.execute('BEGIN IMMEDIATE')
                self.mark(db, job, state, result)
            return {'operation_id': job['id'], **result}
        finally:
            self.lock.release()

    def history(self):
        with self.store.connect() as db:
            rows = db.execute("SELECT * FROM deletion_jobs WHERE state!='prepared' ORDER BY created_at DESC LIMIT 100").fetchall()
        return [{'operation_id': r['id'], 'file_id': r['file_id'], 'state': r['state'],
                 'created_at': r['created_at'], 'file': json.loads(r['payload'])['file'],
                 'batch_id': json.loads(r['payload']).get('batch_id'),
                 'result': json.loads(r['result'])} for r in rows]
