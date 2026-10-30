"""Durable native-operation outbox. One writer, independent of browser lifetime."""
from contextlib import contextmanager
from pathlib import Path
import fcntl
import json
import subprocess
import threading
import time
import uuid

from organisation import plan, NeedsChoice, apply_location
from store import Conflict, now
from deletion_activity import activity, DeletionBusy

ACTIVE = ('queued', 'running')


class BackgroundJobs:
    def __init__(self, app, runner=None):
        self.app, self.store = app, app.store
        self.root = self.store.root / 'native-jobs'
        self.root.mkdir(parents=True, exist_ok=True)
        self.runner = runner or self.run_organisation
        self.wake = threading.Event(); self.stopping = threading.Event(); self.thread = None
        with self.store.connect() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS background_jobs(
                id TEXT PRIMARY KEY, kind TEXT NOT NULL, state TEXT NOT NULL,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                payload TEXT NOT NULL, result TEXT NOT NULL)''')
        self.store.review_hook = self.review_changed
        self.app.deletions.activity = self.deletion_activity
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

    def review_changed(self, db, after, before, event_id):
        kind, aid = after['kind'], after['item_id']
        if not aid.startswith('id:'):
            return
        old, data = before.get('data', {}), after['data']
        relevant = (kind == 'asset' and 'types' in data and data.get('types') != old.get('types') or
                    kind == 'assignment' and data != old)
        if not relevant:
            return
        # All changes in one component form coalesce into one final intention.
        for row in db.execute("SELECT id,payload FROM background_jobs WHERE kind='organise' AND state='queued'").fetchall():
            if json.loads(row['payload']).get('asset_id') == aid:
                db.execute("UPDATE background_jobs SET state='superseded',updated_at=? WHERE id=?", (now(), row['id']))
        self.insert(db, 'organise-' + str(event_id), 'organise', {'asset_id': aid, 'event_id': event_id})

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
        if value['kind'] == 'delete_batch':
            status = self.app.deletions.batch_status(payload['body'])
            out['progress'] = status
        elif value['kind'] == 'delete':
            job = self.app.deletions.job(payload['body']['operation_id'])
            out['progress'] = {'state': job['state'], 'results': [{'file_id': job['file_id'], 'state': job['state'], **job['result']}]}
        out['message'] = result.get('message', '')
        return out

    def get(self, ident):
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

    def snapshot(self):
        with self.store.connect() as db:
            # Uncertain jobs hold the writer too: cancelling newer jobs must
            # never hide the Check result action behind the history limit.
            rows = db.execute("SELECT * FROM background_jobs WHERE state IN ('queued','running','uncertain') ORDER BY created_at").fetchall()
            rows += db.execute("SELECT * FROM background_jobs WHERE state NOT IN ('queued','running','uncertain','superseded') ORDER BY updated_at DESC LIMIT 80").fetchall()
        reservation = self.reservation()
        if not reservation and any(r['state'] == 'uncertain' for r in rows):
            reservation = {'label': 'Check an interrupted Dropbox job', 'reason': 'Queued changes wait until its previous result is checked. Use Check result below.'}
        return {'jobs': [self.public(r) for r in rows], 'reservation': reservation,
                'deletion_activity': self.deletion_activity(),
                'active_count': sum(r['state'] in ACTIVE for r in rows),
                'while_running': 'Jobs continue while this local app server is running. Closing a dialog or browser tab does not cancel them.'}

    def mark(self, ident, state, result):
        with self.store.connect() as db:
            db.execute('UPDATE background_jobs SET state=?,updated_at=?,result=? WHERE id=?',
                       (state, now(), json.dumps(result), ident))

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
        if self.reservation():
            return False
        with self.writer() as acquired:
            if not acquired:
                return False
            self.recover_running()
            with self.store.connect() as db:
                if db.execute("SELECT 1 FROM background_jobs WHERE state='uncertain' LIMIT 1").fetchone():
                    return False
            with self.store.connect() as db:
                db.execute('BEGIN IMMEDIATE')
                row = db.execute("SELECT * FROM background_jobs WHERE state='queued' ORDER BY created_at,id LIMIT 1").fetchone()
                if not row:
                    return False
                db.execute("UPDATE background_jobs SET state='running',updated_at=? WHERE id=?", (now(), row['id']))
            job = self.unpack(row); payload = job['payload']; ident = job['id']
            try:
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
            except (NeedsChoice, Conflict) as error:
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
                results = [self.app.deletions.check({'operation_id': oid}) for oid in ids]
                good = all(x['state'] in ('deleted', 'already_absent') for x in results)
                unknown = any(x['state'] in ('executing', 'uncertain') for x in results)
                self.mark(ident, 'completed' if good else 'uncertain' if unknown else 'needs_review', {'results': results,
                    'message': '' if good else 'The submitted deletion is still unconfirmed. No retry was sent.' if unknown else 'Only started files were checked. Unattempted files require a new deletion review.'})
        self.app.sync.request()
        return self.get(ident)

    def cancel(self, ident):
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT state FROM background_jobs WHERE id=?', (ident,)).fetchone()
            if not row or row['state'] != 'queued':
                raise Conflict('Only a job that has not started can be cancelled.')
            db.execute("UPDATE background_jobs SET state='cancelled',updated_at=?,result=? WHERE id=?",
                       (now(), json.dumps({'message': 'Cancelled before starting. No native request was sent by this job.'}), ident))
        return self.get(ident)

    def replan(self, ident):
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT * FROM background_jobs WHERE id=?', (ident,)).fetchone()
            if not row or row['kind'] != 'organise' or row['state'] not in ('needs_review', 'cancelled'):
                raise Conflict('Check an uncertain result before making a fresh plan.')
            aid = json.loads(row['payload'])['asset_id']
            # Validate that current choices now give a concrete destination.
            proposed = plan(self.app.projection(), aid)
            for pending in db.execute("SELECT * FROM background_jobs WHERE kind='organise' AND state IN ('queued','running','uncertain')"):
                if json.loads(pending['payload']).get('asset_id') == aid:
                    raise Conflict('This image already has an active organisation job.')
            new_id = 'organise-' + uuid.uuid4().hex
            self.insert(db, new_id, 'organise', {'asset_id': aid, 'label': proposed['label'], 'replanned_from': ident})
        return self.get(new_id)

    def start(self):
        if self.thread:
            return
        self.thread = threading.Thread(target=self.loop, name='native-file-jobs', daemon=True)
        self.thread.start()

    def loop(self):
        while not self.stopping.is_set():
            try:
                if self.step():
                    continue
            except Exception:
                # A database outage cannot drop the committed queue.
                pass
            self.wake.wait(2); self.wake.clear()

    def stop(self):
        self.stopping.set(); self.wake.set()
