"""Durable native-operation outbox. One writer, independent of browser lifetime."""
from contextlib import contextmanager
from pathlib import Path
import fcntl
import json
import hashlib
import subprocess
import sqlite3
import threading
import time
import uuid

from organisation import plan, NeedsChoice, NoMoveRequired, apply_location
from organisation_scope import external_reference, OUTSIDE_MESSAGE, REFERENCE_NOTICE
from store import Conflict, now
from deletion_activity import activity, DeletionBusy
from filename_progress import FilenameProgress
from live_review import SourceConflict

ACTIVE = ('queued', 'running')


class BackgroundJobs:
    def __init__(self, app, runner=None):
        self.app, self.store = app, app.store
        self.filename_progress = FilenameProgress(self.store.root)
        self.root = self.store.root / 'native-jobs'
        self.root.mkdir(parents=True, exist_ok=True)
        self.runner = runner or self.run_organisation
        self.wake = threading.Event(); self.stopping = threading.Event(); self.thread = None
        self.lifecycle_lock = threading.Lock()
        self.restart_count = 0
        self.worker_error = ''
        self.worker_retry_at = None
        with self.store.connect() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS background_jobs(
                id TEXT PRIMARY KEY, kind TEXT NOT NULL, state TEXT NOT NULL,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                payload TEXT NOT NULL, result TEXT NOT NULL)''')
            db.execute('''CREATE TABLE IF NOT EXISTS background_job_dismissals(
                job_id TEXT PRIMARY KEY, dismissed_at TEXT NOT NULL, job_updated_at TEXT NOT NULL)''')
        self.store.review_hook = self.review_changed
        self.app.deletions.activity = self.deletion_activity
        self.app.deletions.status_hook = self.reconcile_deletion_status
        self.overlay_locations(app.catalogue)

    def deletion_activity(self, db=None):
        if db is not None:
            return activity(db, self.app.catalogue)
        with self.store.connect() as connection:
            return activity(connection, self.app.catalogue)

    def overlay_locations(self, cat, checked_at=None):
        checked_at = checked_at or cat.source.get('live_dropbox', {}).get('checked_utc', '')
        with self.store.connect() as db:
            rows = db.execute("SELECT result FROM background_jobs WHERE kind='organise' AND state='completed' ORDER BY updated_at").fetchall()
        for row in rows:
            result = json.loads(row['result'])
            if result.get('checked_utc', '') > checked_at:
                apply_location(cat, result)

    def apply_verified_location(self, result):
        # A recovered child receipt can predate a subsequent external move.
        # Keep the newer native scan (or newer completed job) in that case.
        with self.app.catalogue_lock:
            cat = self.app.catalogue
            asset = cat.assets.get((result.get('file') or {}).get('id'), {})
            newest = max(cat.source.get('live_dropbox', {}).get('checked_utc', ''),
                         asset.get('provenance', {}).get('organisation_verified_at') or '')
            if result.get('checked_utc', '') >= newest:
                apply_location(cat, result)

    def insert(self, db, ident, kind, payload):
        db.execute('INSERT INTO background_jobs VALUES(?,?,?,?,?,?,?)',
                   (ident, kind, 'queued', now(), now(), json.dumps(payload), '{}'))
        self.wake.set()

    def unverified_move(self, job):
        return ((self.root / job['id'] / 'move-intent.json').exists()
                and job['result'].get('native_rejected') is not True)

    def supersede_organisation(self, db, replacement_id):
        """Replace older, unsubmitted plans for the same original, atomically."""
        replacement = db.execute('SELECT rowid,* FROM background_jobs WHERE id=?', (replacement_id,)).fetchone()
        if not replacement or replacement['kind'] != 'organise':
            return
        aid = json.loads(replacement['payload']).get('asset_id')
        if not aid:
            return
        rows = db.execute("SELECT * FROM background_jobs WHERE kind='organise' AND state IN ('queued','needs_review') AND rowid<?",
                          (replacement['rowid'],)).fetchall()
        for raw in rows:
            job = self.unpack(raw)
            if job['payload'].get('asset_id') != aid or self.unverified_move(job):
                continue
            db.execute("UPDATE background_jobs SET state='superseded',updated_at=?,result=? WHERE id=?",
                       (now(), json.dumps({**job['result'], 'replacement_job_id': replacement_id}), job['id']))

    def review_changed(self, db, after, before, event_id):
        kind, aid = after['kind'], after['item_id']
        if not aid.startswith('id:'):
            return
        old, data = before.get('data', {}), after['data']
        relevant = (kind == 'asset' and 'types' in data and data.get('types') != old.get('types') or
                    kind == 'assignment' and data != old)
        if not relevant:
            return
        if external_reference(self.app.catalogue.assets.get(aid, {})):
            return
        # All changes in one component form coalesce into one final intention.
        ident = 'organise-' + str(event_id)
        self.insert(db, ident, 'organise', {'asset_id': aid, 'event_id': event_id})
        self.supersede_organisation(db, ident)

    def enqueue_deletion(self, body, batch=False):
        key = ('delete-batch-' + str(body.get('batch_id'))) if batch else 'delete-' + str(body.get('operation_id'))
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            old = db.execute('SELECT * FROM background_jobs WHERE id=?', (key,)).fetchone()
            if old:
                # Validate the confirmation even on a duplicate request.
                payload = json.loads(old['payload'])
                if body != payload.get('submitted_body', payload['body']):
                    raise ValueError('This confirmation does not match the existing background job.')
                return self.public(dict(old))
            target_jobs = ([self.app.deletions.job(j) for j in self.app.deletions.batch(body.get('batch_id'))['payload']['operation_ids']]
                           if batch else [self.app.deletions.job(body.get('operation_id'))])
            current = self.deletion_activity(db)
            skipped = [current[j['file_id']] for j in target_jobs if j['file_id'] in current]
            skip_ids = {j['file_id'] for j in target_jobs if j['file_id'] in current}
            if skipped and (not batch or len(skip_ids) == len(target_jobs)):
                raise DeletionBusy(skipped)
            for job in target_jobs:
                if job['file_id'] in skip_ids:
                    continue
                keeper = job['payload'].get('keeper_binding')
                if keeper and current.get(keeper['id'], {}).get('kind') == 'delete':
                    raise DeletionBusy([current[keeper['id']]], 'The chosen keeper already has a deletion job. Choose another keeper or use Unwanted image.')
            jobs = self.app.deletions.confirm_for_queue(body, batch, db, skip_ids)
            effective = {**body, 'confirm_files': [{'id': j['file_id'], 'revision': j['payload']['file']['revision']} for j in jobs]} if batch else body
            self.insert(db, key, 'delete_batch' if batch else 'delete',
                        {'body': effective, 'submitted_body': body, 'skipped': skipped, 'asset_ids': [j['file_id'] for j in jobs],
                         'label': f'Delete {len(jobs)} reviewed file' + ('s' if len(jobs) != 1 else ''),
                         'files': [{'id': j['file_id'], 'name': j['payload']['file']['name']} for j in jobs]})
        return self.get(key)

    @staticmethod
    def unpack(row):
        return {**dict(row), 'payload': json.loads(row['payload']), 'result': json.loads(row['result'])}

    def public(self, row):
        value = self.unpack(row)
        payload, result = value['payload'], value['result']
        out = {k: value[k] for k in ('id', 'kind', 'state', 'created_at', 'updated_at')}
        out.update(label=payload.get('label', 'Organise Dropbox image'),
                   asset_id=payload.get('asset_id'), files=payload.get('files', []), result=result,
                   skipped=payload.get('skipped', []))
        if value['kind'] == 'organise':
            asset = self.app.catalogue.assets.get(payload.get('asset_id'))
            if asset:
                out['image'] = {k: asset.get(k) for k in ('id', 'name', 'url', 'folder_url')}
                if not payload.get('label'):
                    out['label'] = asset.get('name') or out['label']
        # Deleted assets can retain an older catalogue snapshot. Names in a
        # deletion receipt come from its native review, never that stale copy.
        out['files'] = [{**f, 'reviewed_name': f.get('reviewed_name', f['name'])} for f in out['files']]
        if value['kind'] == 'delete_batch':
            status = self.app.deletions.batch_status(payload['body'])
            out['progress'] = status
        elif value['kind'] == 'delete':
            job = self.app.deletions.job(payload['body']['operation_id'])
            out['progress'] = {'state': job['state'], 'results': [{'operation_id': job['id'], 'file_id': job['file_id'], 'state': job['state'], **job['result']}]}
        for member in out.get('progress', {}).get('results', []):
            resolved = result.get('resolved_by', {}).get(member.get('operation_id'))
            if resolved:
                receipt = self.app.deletions.job(resolved)
                if receipt['file_id'] == member['file_id'] and receipt['state'] in ('deleted', 'already_absent') and receipt['result'].get('verified_absent'):
                    identity = {k: member[k] for k in ('operation_id', 'file_id')}
                    member.clear()
                    member.update(**receipt['result'], **identity, resolved_by_operation_id=resolved)
        progress = out.get('progress', {}).get('results', [])
        # Per-file checks can finish outside this outbox's Check result route.
        # Never let an old parent heading contradict those verified receipts.
        if value['state'] in ('uncertain', 'needs_review') and progress:
            if all(r.get('state') in ('deleted', 'already_absent') for r in progress):
                out['state'] = 'completed'
            elif any(r.get('state') == 'present' for r in progress) and not any(r.get('state') in ('uncertain', 'executing') for r in progress):
                out['state'] = 'needs_review'
        out['message'] = result.get('message', '')
        # Earlier versions queued tagging on workshop references as impossible
        # moves. Classify only this precise pre-write refusal, retaining the
        # original receipt. Never hide an uncertain or submitted native move.
        if (value['kind'] == 'organise' and value['state'] == 'needs_review'
                and result.get('message') == OUTSIDE_MESSAGE
                and not (self.root / value['id'] / 'move-intent.json').exists()
                and external_reference(self.app.catalogue.assets.get(payload.get('asset_id'), {}))):
            out.update(state='not_required', message=REFERENCE_NOTICE)
        if out['state'] == 'completed':
            out['message'] = ''
        out['can_resume_rename'] = (value['state'] == 'needs_review' and value['kind'] in ('delete', 'delete_batch') and
            any(r.get('state') == 'rejected' and r.get('delete_attempted') is False
                and r.get('message') == 'This file, its location or sharing changed after review. Review it again before deleting.'
                for r in out.get('progress', {}).get('results', [])))
        out['can_review_remaining'] = (value['state'] not in ACTIVE and value['kind'] in ('delete', 'delete_batch') and
            any(r.get('state') in ('rejected', 'prepared', 'not_started', 'present')
                for r in out.get('progress', {}).get('results', [])))
        out['can_dismiss'] = self.dismissible(out)
        out['dismissed_at'] = value.get('dismissed_at')
        return out

    def dismissible(self, job):
        if job['state'] not in ('completed', 'needs_review', 'cancelled', 'superseded', 'not_required'):
            return False
        if any(r.get('state') in ('executing', 'uncertain') for r in job.get('progress', {}).get('results', [])):
            return False
        if (job['kind'] == 'organise' and job['state'] == 'needs_review'
                and (self.root / job['id'] / 'move-intent.json').exists()
                and not job['result'].get('native_rejected')):
            return False
        return True

    def dismiss(self, ident, expected_updated_at, restore=False):
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT * FROM background_jobs WHERE id=?', (ident,)).fetchone()
            if not row:
                raise ValueError('Unknown background job.')
            if row['updated_at'] != expected_updated_at:
                raise Conflict('This job changed. Refresh Jobs before clearing it.')
            if restore:
                db.execute('DELETE FROM background_job_dismissals WHERE job_id=?', (ident,))
            else:
                job = self.public(row)
                if not job['can_dismiss']:
                    raise Conflict('Running jobs and unverified results must remain visible. Check the result first.')
                db.execute('INSERT OR REPLACE INTO background_job_dismissals VALUES(?,?,?)',
                           (ident, now(), row['updated_at']))
        return {'job_id': ident, 'dismissed': not restore}

    def clear_finished(self):
        """Clear known finished rows from the display; retain every receipt."""
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            rows = db.execute("""SELECT j.* FROM background_jobs j LEFT JOIN background_job_dismissals d
                ON d.job_id=j.id AND d.job_updated_at=j.updated_at
                WHERE j.state IN ('completed','cancelled','superseded','needs_review','not_required') AND d.job_id IS NULL""").fetchall()
            cleared = 0
            for row in rows:
                job = self.public(row)
                if job['state'] in ('completed', 'cancelled', 'superseded', 'not_required') and job['can_dismiss']:
                    db.execute('INSERT OR REPLACE INTO background_job_dismissals VALUES(?,?,?)',
                               (row['id'], now(), row['updated_at']))
                    cleared += 1
        return {'cleared': cleared}

    def reconcile_deletion_status(self, operation_id):
        """Keep completed/checked child receipts and their parent in agreement."""
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            checked = db.execute('SELECT file_id FROM deletion_jobs WHERE id=?', (operation_id,)).fetchone()
            rows = db.execute("SELECT * FROM background_jobs WHERE kind IN ('delete','delete_batch') AND state IN ('uncertain','needs_review')").fetchall()
            for raw in rows:
                row = self.unpack(raw); body = row['payload']['body']
                if row['kind'] == 'delete_batch':
                    batch = db.execute('SELECT payload FROM deletion_batches WHERE id=?', (body['batch_id'],)).fetchone()
                    ids = json.loads(batch['payload'])['operation_ids']
                else:
                    ids = [body['operation_id']]
                jobs = [db.execute('SELECT id,file_id,state FROM deletion_jobs WHERE id=?', (oid,)).fetchone() for oid in ids]
                if operation_id not in ids and not any(j['file_id'] == checked['file_id'] for j in jobs):
                    continue
                members, resolved_by = [], dict(row['result'].get('resolved_by', {}))
                for member in jobs:
                    state = member['state']
                    latest = db.execute("SELECT data FROM reviews WHERE kind='deletion' AND product_id='' AND item_id=?", (member['file_id'],)).fetchone()
                    latest = json.loads(latest['data']) if latest else {}
                    if state not in ('deleted', 'already_absent') and latest.get('state') in ('deleted', 'already_absent') and latest.get('result', {}).get('verified_absent'):
                        # A later, separately confirmed operation finished the
                        # same stable file ID. Keep the original attempt intact.
                        state = latest['state']; resolved_by[member['id']] = latest['operation_id']
                    members.append(state)
                state = ('completed' if all(s in ('deleted', 'already_absent') for s in members) else
                         'uncertain' if any(s in ('uncertain', 'executing') for s in members) else 'needs_review')
                message = ('' if state == 'completed' else
                           'Some results still need checking. No deletion was repeated.' if state == 'uncertain' else
                           'Use Review remaining files to check current versions before confirming another deletion.')
                db.execute('UPDATE background_jobs SET state=?,updated_at=?,result=? WHERE id=?',
                           (state, now(), json.dumps({**row['result'], 'message': message, 'resolved_by': resolved_by}), row['id']))

    def review_remaining(self, ident):
        with self.store.connect() as db:
            raw = db.execute('SELECT * FROM background_jobs WHERE id=?', (ident,)).fetchone()
        if not raw:
            raise ValueError('Unknown background job.')
        row = self.unpack(raw)
        if row['kind'] not in ('delete', 'delete_batch') or row['state'] in ACTIVE:
            raise Conflict('Wait for this deletion job to finish before reviewing remaining files.')
        body = row['payload']['body']
        ids = (self.app.deletions.batch(body['batch_id'])['payload']['operation_ids']
               if row['kind'] == 'delete_batch' else [body['operation_id']])
        choices = []
        for oid in ids:
            job = self.app.deletions.job(oid); p = job['payload']
            resolved = row['result'].get('resolved_by', {}).get(oid)
            if resolved:
                receipt = self.app.deletions.job(resolved)
                if receipt['file_id'] == job['file_id'] and receipt['state'] in ('deleted', 'already_absent') and receipt['result'].get('verified_absent'):
                    continue
            if (job['state'] == 'prepared' or job['state'] == 'rejected' and job['result'].get('delete_attempted') is False or
                    job['state'] == 'present' and job['result'].get('presence_verified') is True):
                choices.append({'asset_id': job['file_id'], 'reason': p['reason'],
                                'keeper_id': (p.get('keeper_binding') or {}).get('id', '')})
        if not choices:
            raise Conflict('No files are ready for another review. Check any uncertain results separately.')
        key = hashlib.sha256(json.dumps(['fresh-v2', ident, choices], sort_keys=True).encode()).hexdigest()[:32]
        return self.app.deletion_reviews.start_review({'request_id': 'remaining-' + key, 'entries': choices,
                                                       'force_refresh': True})

    def get(self, ident):
        if self.thread is not None:
            self.start()
        with self.store.connect() as db:
            row = db.execute('SELECT * FROM background_jobs WHERE id=?', (ident,)).fetchone()
        if not row:
            raise ValueError('Unknown background job.')
        return self.public(row)

    def reservation(self):
        file = self.store.root / 'native-writer-reservation.json'
        if not file.exists():
            return None
        try:
            value = json.loads(file.read_text())
            return value if value.get('active') else None
        except (OSError, ValueError):
            return {'active': True, 'label': 'Dropbox writer reservation', 'reason': 'The native writer reservation could not be read; jobs remain queued.'}

    def snapshot(self, include_dismissed=False):
        if self.thread is not None:
            self.start()
        with self.store.connect() as db:
            # Uncertain jobs hold the writer too: cancelling newer jobs must
            # never hide the Check result action behind the history limit.
            query = '''SELECT j.*,d.dismissed_at FROM background_jobs j LEFT JOIN background_job_dismissals d
                       ON d.job_id=j.id AND d.job_updated_at=j.updated_at'''
            rows = db.execute(query + " WHERE j.state IN ('queued','running','uncertain') ORDER BY j.created_at").fetchall()
            rows += db.execute(query + " WHERE j.state='needs_review' AND d.job_id IS NULL ORDER BY j.updated_at DESC").fetchall()
            rows += db.execute(query + " WHERE j.state IN ('completed','cancelled','not_required') AND d.job_id IS NULL ORDER BY j.updated_at DESC LIMIT 80").fetchall()
            dismissed_count = db.execute('''SELECT COUNT(*) FROM background_jobs j JOIN background_job_dismissals d
                ON d.job_id=j.id AND d.job_updated_at=j.updated_at''').fetchone()[0]
            if include_dismissed:
                rows += db.execute(query + " WHERE d.job_id IS NOT NULL AND j.state NOT IN ('queued','running','uncertain') ORDER BY d.dismissed_at DESC LIMIT 80").fetchall()
        reservation = self.reservation()
        if not reservation and any(r['state'] == 'uncertain' and r['kind'] == 'organise' for r in rows):
            reservation = {'label': 'Check an interrupted Dropbox job', 'reason': 'Queued changes wait until its previous result is checked. Use Check result below.'}
        reviews = self.app.deletion_reviews.snapshot() if hasattr(self.app, 'deletion_reviews') else []
        return {'jobs': reviews + [self.public(r) for r in rows], 'reservation': reservation,
                'worker': self.worker_status(),
                'dismissed_count': dismissed_count, 'showing_dismissed': include_dismissed,
                'filename_job': self.filename_progress.read(),
                'deletion_activity': self.deletion_activity(),
                'active_count': sum(r['state'] in ACTIVE for r in [*rows, *reviews]),
                'while_running': 'Jobs continue while this local app server is running. Closing a dialog or browser tab does not cancel them.'}

    def mark(self, ident, state, result):
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('UPDATE background_jobs SET state=?,updated_at=?,result=? WHERE id=?',
                       (state, now(), json.dumps(result), ident))
            if state == 'needs_review':
                old = db.execute('SELECT rowid,* FROM background_jobs WHERE id=?', (ident,)).fetchone()
                if old and old['kind'] == 'organise':
                    aid = json.loads(old['payload']).get('asset_id')
                    # A new choice can arrive while the old plan is running.
                    # Finishing that old failure must not restore its warning.
                    for later in db.execute("SELECT * FROM background_jobs WHERE kind='organise' AND rowid>? ORDER BY rowid DESC",
                                            (old['rowid'],)).fetchall():
                        if json.loads(later['payload']).get('asset_id') == aid:
                            self.supersede_organisation(db, later['id'])
                            break

    @contextmanager
    def writer(self):
        # One OS lock across every local app instance. Child-process leases
        # prevent a restarted parent overtaking an outstanding native call.
        with (self.root / 'writer.lock').open('a+') as stream:
            try:
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                yield False
                return
            try:
                self.writer_fd = stream.fileno()
                yield True
            finally:
                self.writer_fd = None

    def run_organisation(self, payload, directory):
        python = self.app.catalogue.project / 'application/.venv/bin/python'
        command = [str(python), str(Path(__file__).with_name('organise_dropbox.py')),
                   '--project', str(self.app.catalogue.project), '--journal', str(directory)]
        process = subprocess.run(command, input=json.dumps(payload), text=True, capture_output=True,
                                 timeout=180, pass_fds=(self.writer_fd,) if self.writer_fd is not None else ())
        if process.returncode:
            raise ValueError('Dropbox organisation stopped without a confirmed result.')
        return json.loads(process.stdout)

    def recover_running(self):
        with self.store.connect() as db:
            rows = db.execute("SELECT * FROM background_jobs WHERE state='running'").fetchall()
        for row in rows:
            # Never replay a possibly submitted mutation on restart. Recovery
            # is read-only and explicit through the job's Check result action.
            self.mark(row['id'], 'uncertain', {'message': 'The app restarted during this job. Check its result; no native action was repeated.'})

    def step(self):
        if self.stopping.is_set() or self.reservation():
            return False
        with self.writer() as acquired:
            if not acquired or self.stopping.is_set():
                return False
            self.recover_running()
            with self.store.connect() as db:
                # Unknown moves can affect destination allocation. An unknown
                # deletion only reserves its own original and keeper; other
                # independent files can continue under this same writer lease.
                if db.execute("SELECT 1 FROM background_jobs WHERE state='uncertain' AND kind='organise' LIMIT 1").fetchone():
                    return False
            with self.store.connect() as db:
                db.execute('BEGIN IMMEDIATE')
                row = db.execute("SELECT * FROM background_jobs WHERE state='queued' ORDER BY created_at,id LIMIT 1").fetchone()
                if not row:
                    return False
                db.execute("UPDATE background_jobs SET state='running',updated_at=? WHERE id=?", (now(), row['id']))
            job = self.unpack(row); payload = job['payload']; ident = job['id']
            self.clear_worker_error()
            try:
                if hasattr(self.app, 'refresh_source'):
                    self.app.refresh_source()
                if job['kind'] == 'organise':
                    with self.app.catalogue_lock:
                        proposed = plan(self.app.projection(), payload['asset_id'])
                    directory = self.root / ident
                    directory.mkdir(exist_ok=True)
                    (directory / 'plan.json').write_text(json.dumps(proposed, indent=2))
                    with self.store.connect() as db:
                        db.execute('UPDATE background_jobs SET payload=? WHERE id=?', (json.dumps({**payload, 'label': proposed['label'], 'plan': proposed}), ident))
                    result = self.runner(proposed, directory)
                    state = result.get('state', 'uncertain')
                    if state == 'completed':
                        self.apply_verified_location(result)
                else:
                    # Child inherits writer lease even if the server exits.
                    self.app.deletions.writer_fd = self.writer_fd
                    result = (self.app.deletions.execute_batch if job['kind'] == 'delete_batch' else self.app.deletions.execute)(payload['body'])
                    unknown = result['state'] in ('uncertain', 'executing') or any(
                        r.get('state') in ('uncertain', 'executing') for r in result.get('results', []))
                    state = ('completed' if result['state'] in ('deleted', 'already_absent', 'completed') else
                             'uncertain' if unknown else 'needs_review')
                self.mark(ident, state, result)
            except NoMoveRequired as error:
                self.mark(ident, 'not_required', {'message': str(error), 'native_attempted': False})
            except (NeedsChoice, Conflict, SourceConflict) as error:
                self.mark(ident, 'needs_review', {'message': str(error)})
            except ValueError as error:
                submitted = (self.root / ident / 'move-intent.json').exists()
                self.mark(ident, 'uncertain' if submitted else 'needs_review', {'message': str(error)})
            except Exception:
                self.mark(ident, 'uncertain', {'message': 'The result could not be confirmed. No native action will be repeated automatically.'})
            finally:
                self.app.deletions.writer_fd = None
                self.app.sync.request()
            return True

    def check(self, ident):
        job = self.get(ident)
        if job['state'] != 'uncertain':
            return job
        with self.writer() as acquired:
            if not acquired or self.reservation():
                raise Conflict('A native Dropbox job is still active. Wait for its result before checking.')
            with self.store.connect() as db:
                row = self.unpack(db.execute('SELECT * FROM background_jobs WHERE id=?', (ident,)).fetchone())
            p = row['payload']
            if row['kind'] == 'organise':
                directory = self.root / ident
                if not (directory / 'move-intent.json').exists():
                    self.mark(ident, 'needs_review', {'message': 'No image-move submission was recorded. Save the image types or components again to plan a fresh job.'})
                else:
                    result = self.runner(p['plan'], directory) # submitted-intent path only reads back
                    self.mark(ident, result['state'], result)
                    if result['state'] == 'completed':
                        self.apply_verified_location(result)
            else:
                ids = (self.app.deletions.batch(p['body']['batch_id'])['payload']['operation_ids']
                       if row['kind'] == 'delete_batch' else [p['body']['operation_id']])
                for oid in ids:
                    self.app.deletions.check({'operation_id': oid})
                # Read the durable receipts, including later confirmed jobs
                # resolving an earlier member. Do not overwrite those links
                # with this older batch's original attempt states.
                self.reconcile_deletion_status(ids[0])
        self.app.sync.request()
        return self.get(ident)

    def check_deletion(self, operation_id):
        # History checks use the same cross-process lease as job checks. A
        # surviving native child may still be finishing after a server restart.
        with self.writer() as acquired:
            if not acquired or self.reservation():
                raise Conflict('A native Dropbox job is still active. Wait for its result before checking.')
            result = self.app.deletions.check({'operation_id': operation_id})
        self.app.sync.request()
        return result

    def cancel(self, ident):
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT state FROM background_jobs WHERE id=?', (ident,)).fetchone()
            if not row or row['state'] != 'queued':
                raise Conflict('Only a job that has not started can be cancelled.')
            db.execute("UPDATE background_jobs SET state='cancelled',updated_at=?,result=? WHERE id=?",
                       (now(), json.dumps({'message': 'Cancelled before starting. No native request was sent by this job.'}), ident))
        return self.get(ident)

    def resume_rename(self, ident):
        from deletion_recovery import resume_verified_rename
        return resume_verified_rename(self, ident)

    def replan(self, ident):
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT * FROM background_jobs WHERE id=?', (ident,)).fetchone()
            # A lost HTTP response or a second click retrieves the existing
            # successor; it never creates another native operation.
            if row and row['kind'] == 'organise' and row['state'] == 'superseded':
                aid = json.loads(row['payload']).get('asset_id')
                visited = set()
                while row['state'] == 'superseded' and row['id'] not in visited:
                    visited.add(row['id'])
                    successor = json.loads(row['result']).get('replacement_job_id')
                    row = db.execute('SELECT * FROM background_jobs WHERE id=?', (successor,)).fetchone()
                    if not row or row['kind'] != 'organise' or json.loads(row['payload']).get('asset_id') != aid:
                        raise Conflict('The replacement job could not be found. Refresh Jobs before planning again.')
                if row['state'] == 'superseded':
                    raise Conflict('The replacement job history needs checking. Refresh Jobs before planning again.')
                return self.public(row)
            if not row or row['kind'] != 'organise' or row['state'] not in ('needs_review', 'cancelled'):
                raise Conflict('Check an uncertain result before making a fresh plan.')
            if self.public(row)['state'] == 'not_required':
                return self.public(row)
            if self.unverified_move(self.unpack(row)):
                raise Conflict('Check this unverified move before making a fresh plan.')
            aid = json.loads(row['payload'])['asset_id']
            # Validate that current choices now give a concrete destination.
            no_move = None
            try:
                proposed = plan(self.app.projection(), aid)
            except NoMoveRequired as error:
                no_move = str(error)
                proposed = {'label': self.app.catalogue.assets[aid].get('name', aid)}
            for pending in db.execute("SELECT * FROM background_jobs WHERE kind='organise' AND state IN ('queued','running','uncertain')"):
                if json.loads(pending['payload']).get('asset_id') == aid:
                    raise Conflict('This image already has an active organisation job.')
            new_id = 'organise-' + uuid.uuid4().hex
            self.insert(db, new_id, 'organise', {'asset_id': aid, 'label': proposed['label'], 'replanned_from': ident})
            if no_move:
                db.execute("UPDATE background_jobs SET state='not_required',result=? WHERE id=?",
                           (json.dumps({'message': no_move, 'native_attempted': False}), new_id))
            self.supersede_organisation(db, new_id)
            db.execute("UPDATE background_jobs SET state='superseded',updated_at=?,result=? WHERE id=?",
                       (now(), json.dumps({**json.loads(row['result']), 'replacement_job_id': new_id}), ident))
        return self.get(new_id)

    def start(self):
        with self.lifecycle_lock:
            if self.stopping.is_set() or (self.thread and self.thread.is_alive()):
                return
            if self.thread is not None:
                self.restart_count += 1
            self.thread = threading.Thread(target=self.loop, name='native-file-jobs', daemon=True)
            self.thread.start()

    def worker_status(self):
        with self.lifecycle_lock:
            alive = bool(self.thread and self.thread.is_alive())
            state = ('stopped' if self.stopping.is_set() else 'retrying' if self.worker_error else
                     'running' if alive else 'not_started')
            return {'alive': alive, 'state': state, 'error': self.worker_error,
                    'retry_at': self.worker_retry_at, 'restart_count': self.restart_count}

    def clear_worker_error(self):
        with self.lifecycle_lock:
            self.worker_error = ''
            self.worker_retry_at = None

    def loop(self):
        failures = 0
        while not self.stopping.is_set():
            delay = 2
            try:
                worked = self.step()
                failures = 0
                self.clear_worker_error()
                if worked:
                    continue
            except Exception as error:
                failures += 1
                delay = min(30, 2 ** min(failures, 5))
                # Keep the queue and report local storage failures without
                # exposing arbitrary child/SDK exception bodies. Recovery
                # marks interrupted mutations uncertain; it never repeats them.
                detail = str(error) if isinstance(error, sqlite3.Error) else 'Local worker failure'
                with self.lifecycle_lock:
                    self.worker_error = f'{type(error).__name__}: {detail}'[:500]
                    self.worker_retry_at = time.time() + delay
            self.wake.wait(delay); self.wake.clear()

    def stop(self):
        self.stopping.set(); self.wake.set()
