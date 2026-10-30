"""Durable, read-only deletion reviews. No method here can delete a file."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext
from pathlib import Path
import fcntl
import json
import math
import re
import secrets
import threading
import time

from deletion_activity import DeletionBusy
from deletions import NativeUnavailable
from store import Conflict, now


class DeletionReviews:
    workers = 3
    max_attempts = 3

    def __init__(self, app):
        self.app, self.store = app, app.store
        self.lock = threading.RLock()
        self.lifecycle_lock = threading.Lock()
        self.wake, self.stopping = threading.Event(), threading.Event()
        self.thread = None
        self.restart_count = 0
        self.worker_error = ''
        self.worker_retry_at = None
        with self.store.connect() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS deletion_reviews(
                id TEXT PRIMARY KEY, state TEXT NOT NULL, created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL, payload TEXT NOT NULL)''')
            db.execute('''CREATE TABLE IF NOT EXISTS deletion_review_throttle(
                app TEXT PRIMARY KEY, until REAL NOT NULL)''')
            # Adopt existing deadlines on upgrade, including stopped reviews.
            # All current deletion-review workers use this same Dropbox app.
            deadline = max((self.valid_delay(json.loads(r['payload']).get('cooldown_until'))
                            for r in db.execute('SELECT payload FROM deletion_reviews')), default=0)
            db.execute('''INSERT INTO deletion_review_throttle VALUES('image-processing',?)
                          ON CONFLICT(app) DO UPDATE SET until=MAX(until,excluded.until)''', (deadline,))

    @staticmethod
    def valid_delay(value):
        try:
            value = float(value or 0)
            return max(0, value) if math.isfinite(value) else 0
        except (TypeError, ValueError, OverflowError):
            return 0

    def cooldown_until(self):
        with self.store.connect() as db:
            return db.execute("SELECT until FROM deletion_review_throttle WHERE app='image-processing'").fetchone()['until']

    def extend_cooldown(self, deadline):
        with self.store.connect() as db:
            db.execute("UPDATE deletion_review_throttle SET until=MAX(until,?) WHERE app='image-processing'", (deadline,))

    def row(self, ident, db=None):
        with self.store.connect() if db is None else nullcontext(db) as db:
            row = db.execute('SELECT * FROM deletion_reviews WHERE id=?', (ident,)).fetchone()
        if not row:
            raise ValueError('Unknown deletion review.')
        return {**dict(row), 'payload': json.loads(row['payload'])}

    def write(self, row, db=None):
        row['updated_at'] = now()
        with self.store.connect() if db is None else nullcontext(db) as db:
            db.execute('UPDATE deletion_reviews SET state=?,updated_at=?,payload=? WHERE id=?',
                       (row['state'], row['updated_at'], json.dumps(row['payload']), row['id']))

    def start_review(self, body):
        ident, entries = body.get('request_id', ''), body.get('entries')
        if not re.fullmatch(r'[A-Za-z0-9_-]{12,100}', ident) or not isinstance(entries, list) or not 0 < len(entries) <= 500:
            raise ValueError('Choose between 1 and 500 files and provide a review request ID.')
        choices = []
        cat = self.app.catalogue
        for item in entries:
            if not isinstance(item, dict):
                raise ValueError('Invalid selected file.')
            aid, reason, keeper = item.get('asset_id'), item.get('reason'), item.get('keeper_id') or ''
            asset = cat.assets.get(aid, {})
            if not isinstance(aid, str) or not aid.startswith('id:') or asset.get('source') != 'Dropbox':
                raise ValueError('Only known Dropbox originals can be reviewed.')
            if reason not in ('unwanted', 'duplicate') or (reason == 'duplicate' and not keeper):
                raise ValueError('Choose a reason and a keeper for each duplicate.')
            if reason == 'unwanted':
                keeper = ''
            choices.append({'asset_id': aid, 'reason': reason, 'keeper_id': keeper})
        ids = {e['asset_id'] for e in choices}
        canonical = getattr(cat, 'canonical_assets', {})
        targets = {canonical.get(aid, aid) for aid in ids}
        if len(ids) != len(choices) or len(targets) != len(choices):
            raise ValueError('Select each original or exact-byte image group only once.')
        if any(e['keeper_id'] and canonical.get(e['keeper_id'], e['keeper_id']) in targets for e in choices):
            raise ValueError('Selected files cannot be keepers.')
        with self.lock, self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            existing = db.execute('SELECT payload FROM deletion_reviews WHERE id=?', (ident,)).fetchone()
            if existing:
                if json.loads(existing['payload'])['choices'] != choices:
                    raise Conflict('This review request ID belongs to another selection.')
            else:
                payload = {'choices': choices, 'entries': [{**e, 'name': cat.assets[e['asset_id']]['name'],
                           'state': 'pending', 'attempts': 0, 'error': '', 'operation_id': None} for e in choices],
                           'batch_id': None, 'previous_batches': [], 'force_refresh': body.get('force_refresh') is True}
                db.execute('INSERT INTO deletion_reviews VALUES(?,?,?,?,?)',
                           (ident, 'queued', now(), now(), json.dumps(payload)))
        self.wake.set()
        return self.get(ident)

    def get(self, ident, plans=False):
        # Requests can revive a previously started worker. Do not implicitly
        # start services constructed for isolated tests or maintenance tools.
        if self.thread is not None:
            self.start()
        row = self.row(ident); p = row['payload']; entries = []
        for e in p['entries']:
            item = dict(e)
            if plans:
                asset = self.app.catalogue.assets.get(e['asset_id'], {})
                item['image'] = {key: asset.get(key) for key in ('id', 'name', 'source', 'url', 'folder_url',
                                'original', 'local_preview', 'representation')}
                if e.get('operation_id') and e['state'] == 'ready':
                    job = self.app.deletions.job(e['operation_id'])
                    item['plan'] = {'operation_id': job['id'], **job['payload']}
            entries.append(item)
        counts = {s: sum(e['state'] == s for e in entries) for s in ('pending', 'checking', 'ready', 'failed', 'skipped', 'submitted')}
        retry_at, wait_reason = None, None
        if row['state'] in ('queued', 'running') and counts['pending']:
            cooldown = max(self.cooldown_until(), self.valid_delay(p.get('cooldown_until')))
            due = min(self.valid_delay(e.get('next_attempt_at')) for e in entries if e['state'] == 'pending')
            if max(cooldown, due) > time.time():
                retry_at = max(cooldown, due)
                wait_reason = 'dropbox_cooldown' if cooldown > time.time() else 'read_retry'
        return {'id': ident, 'kind': 'delete_review', 'state': row['state'],
                'created_at': row['created_at'], 'updated_at': row['updated_at'],
                'label': f"Review {len(entries)} selected files", 'entries': entries, 'counts': counts,
                'total': len(entries), 'checked': counts['ready'] + counts['failed'] + counts['skipped'] + counts['submitted'],
                'batch_id': p.get('batch_id'), 'files': [], 'message': '', 'read_only': True,
                'retry_at': retry_at, 'wait_reason': wait_reason,
                'worker': self.worker_status() if row['state'] in ('queued', 'running') else None}

    def snapshot(self):
        with self.store.connect() as db:
            rows = db.execute("SELECT id FROM deletion_reviews WHERE state IN ('queued','running','review_ready','review_attention') ORDER BY created_at DESC").fetchall()
            rows += db.execute("SELECT id FROM deletion_reviews WHERE state='cancelled' ORDER BY updated_at DESC LIMIT 10").fetchall()
        return [self.get(r['id']) for r in rows]

    def recompute(self, row):
        states = {e['state'] for e in row['payload']['entries']}
        row['state'] = ('running' if states & {'pending', 'checking'} else
                        'review_attention' if 'failed' in states else
                        'submitted' if states <= {'submitted', 'skipped'} else 'review_ready')

    def submitted(self, batch_id):
        with self.lock:
            for job in self.snapshot():
                row = self.row(job['id'])
                if row['payload'].get('batch_id') != batch_id:
                    continue
                ids = set(self.app.deletions.batch(batch_id)['payload']['operation_ids'])
                for e in row['payload']['entries']:
                    if e.get('operation_id') in ids:
                        e['state'] = 'submitted'
                self.recompute(row); self.write(row)

    def reusable(self, entry):
        with self.store.connect() as db:
            rows = db.execute("SELECT id,payload FROM deletion_jobs WHERE file_id=? AND state='prepared' ORDER BY created_at DESC LIMIT 8",
                              (entry['asset_id'],)).fetchall()
        for row in rows:
            p = json.loads(row['payload'])
            if p.get('batch_id') or p.get('queue_confirmed_at') or p['expires_at'] < time.time() + 60:
                continue
            if p['reason'] != entry['reason'] or (p.get('keeper_binding') or {}).get('id', '') != entry['keeper_id']:
                continue
            try:
                self.app.deletions.validate_batch([self.app.deletions.job(row['id'])])
            except (ValueError, Conflict):
                continue
            return row['id']

    def inspect_one(self, ident, index):
        with self.lock:
            row = self.row(ident); e = row['payload']['entries'][index]
            if (self.stopping.is_set() or row['state'] == 'cancelled' or e['state'] != 'pending' or
                    max(self.cooldown_until(), self.valid_delay(row['payload'].get('cooldown_until')),
                        self.valid_delay(e.get('next_attempt_at'))) > time.time()):
                return
            e.update(state='checking', error='', attempts=e.get('attempts', 0) + 1)
            row['state'] = 'running'; self.write(row); entry = dict(e)
        change = {}; cooldown = 0
        try:
            busy = self.app.jobs.deletion_activity().get(entry['asset_id'])
            if busy:
                raise DeletionBusy([busy])
            oid = None if row['payload'].get('force_refresh') else self.reusable(entry)
            if not oid:
                plan = self.app.deletions.prepare(entry)
                oid = plan['operation_id']
            change = {'state': 'ready', 'operation_id': oid, 'error': '', 'retryable': False}
        except DeletionBusy as error:
            change = {'state': 'skipped', 'error': str(error), 'busy_files': error.details['busy_files']}
        except Exception as error:
            retryable = isinstance(error, (TimeoutError, ConnectionError)) or bool(getattr(error, 'retryable', False))
            again = retryable and entry['attempts'] < self.max_attempts
            provider_delay = self.valid_delay(getattr(error, 'retry_after', 0))
            delay = max(2 ** entry['attempts'], provider_delay)
            if provider_delay:
                cooldown = time.time() + delay
            change = {'state': 'pending' if again else 'failed', 'error': str(error), 'retryable': retryable,
                      'next_attempt_at': time.time() + delay}
        with self.lock:
            if cooldown:
                # Persist before another queued worker can start. Cancelling,
                # retrying or creating a review cannot bypass this deadline.
                self.extend_cooldown(cooldown)
            row = self.row(ident)
            row['payload']['entries'][index].update(change)
            if cooldown:
                row['payload']['cooldown_until'] = max(row['payload'].get('cooldown_until', 0), cooldown)
            if row['state'] != 'cancelled':
                self.recompute(row)
            self.write(row)

    def detach_batch(self, row, db=None):
        bid = row['payload'].get('batch_id')
        if not bid:
            return
        own_transaction = db is None
        with self.store.connect() if own_transaction else nullcontext(db) as db:
            if own_transaction:
                db.execute('BEGIN IMMEDIATE')
            batch = self.app.deletions.batch(bid, db=db)
            jobs = [self.app.deletions.job(oid, db=db) for oid in batch['payload']['operation_ids']]
            if batch['state'] == 'prepared' and not any(j['payload'].get('queue_confirmed_at') for j in jobs):
                for job in jobs:
                    p = dict(job['payload']); p.pop('batch_id', None)
                    db.execute('UPDATE deletion_jobs SET payload=? WHERE id=?', (json.dumps(p), job['id']))
                db.execute("UPDATE deletion_batches SET state='superseded' WHERE id=?", (bid,))
        row['payload']['previous_batches'].append(bid)
        row['payload']['batch_id'] = None

    def retry(self, ident):
        with self.lock, self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = self.row(ident, db=db)
            if row['state'] in ('queued', 'running'):
                return self.get(ident)
            self.detach_batch(row, db=db)
            busy = self.app.jobs.deletion_activity(db)
            for e in row['payload']['entries']:
                if e['asset_id'] in busy:
                    e.update(state='skipped', busy_files=[busy[e['asset_id']]])
                elif e['state'] in ('failed', 'pending', 'skipped'):
                    e.update(state='pending', attempts=0, error='', operation_id=None, next_attempt_at=0)
            self.recompute(row); self.write(row, db=db)
        self.wake.set()
        return self.get(ident)

    def plan(self, ident):
        with self.lock:
            row = self.row(ident)
            if row['state'] in ('queued', 'running', 'cancelled'):
                raise Conflict('Wait for these read-only checks to finish or resume this review.')
            # A large selection shares one current catalogue view. Rebuilding
            # and hashing the entire gallery for each file stalls confirmation.
            # The HTTP handler holds the catalogue lock across this operation;
            # execution still checks each original immediately before deletion.
            view = self.app.deletions.validation_view()
            # Batch membership and the saved review pointer commit together.
            # A local write failure must not strand otherwise usable checks.
            prepared = None
            with self.store.connect() as db:
                db.execute('BEGIN IMMEDIATE')
                row = self.row(ident, db=db)
                if row['payload'].get('batch_id'):
                    b = self.app.deletions.batch(row['payload']['batch_id'], db=db)
                    if b['state'] == 'prepared':
                        jobs = [self.app.deletions.job(oid, db=db) for oid in b['payload']['operation_ids']]
                        if any(j['payload'].get('queue_confirmed_at') for j in jobs):
                            return {'batch_id': b['id'], **b['payload']}
                        try:
                            self.app.deletions.validate_batch(jobs, view=view)
                            busy = self.app.jobs.deletion_activity(db)
                            if any(j['file_id'] in busy for j in jobs):
                                raise Conflict('A reviewed file already has another job.')
                        except (ValueError, Conflict):
                            self.detach_batch(row, db=db)
                        else:
                            return {'batch_id': b['id'], **b['payload']}
                    elif b['state'] == 'superseded':
                        # Older versions could commit a retry's detach before
                        # saving this pointer. Recover that local partial save;
                        # per-file validation below still rejects confirmed jobs.
                        self.detach_batch(row, db=db)
                    else:
                        raise Conflict('This selection already has a deletion job. Check Jobs.')
                busy = self.app.jobs.deletion_activity(db); ids = []
                for e in row['payload']['entries']:
                    if e['state'] != 'ready':
                        continue
                    if e['asset_id'] in busy:
                        e.update(state='skipped', busy_files=[busy[e['asset_id']]])
                        continue
                    try:
                        job = self.app.deletions.job(e['operation_id'], db=db)
                        self.app.deletions.validate_batch([job], view=view)
                        if job['payload'].get('queue_confirmed_at'):
                            raise Conflict('This check was already confirmed. Check Jobs or retry to prepare a new review.')
                    except (ValueError, Conflict) as error:
                        e.update(state='failed', error=str(error), retryable=False)
                    else:
                        if job['payload'].get('batch_id'):
                            # Two read reviews can reuse the same unconfirmed
                            # check. Give this review independent membership,
                            # preserving the pinned file and original expiry.
                            # Never copy confirmation or change the other batch.
                            payload = {k: v for k, v in job['payload'].items() if k != 'batch_id'}
                            payload['copied_from_operation_id'] = job['id']
                            e['operation_id'] = secrets.token_urlsafe(24)
                            db.execute('INSERT INTO deletion_jobs VALUES(?,?,?,?,?,?)',
                                       (e['operation_id'], job['file_id'], 'prepared', now(), json.dumps(payload), '{}'))
                        ids.append(e['operation_id'])
                self.recompute(row)
                if ids:
                    prepared = self.app.deletions.prepare_batch({'operation_ids': ids}, view=view, db=db)
                    row['payload']['batch_id'] = prepared['batch_id']
                self.write(row, db=db)
            if not prepared:
                raise Conflict('No checked files are ready. Retry the failed checks or choose another selection.')
            return prepared

    def cancel(self, ident):
        with self.lock:
            row = self.row(ident)
            row['state'] = 'cancelled'; self.write(row)
        return self.get(ident)

    def recover(self):
        with self.lock, self.store.connect() as db:
            for raw in db.execute("SELECT * FROM deletion_reviews WHERE state IN ('queued','running')").fetchall():
                row = {**dict(raw), 'payload': json.loads(raw['payload'])}
                for e in row['payload']['entries']:
                    if e['state'] == 'checking':
                        e.update(state='pending', next_attempt_at=0)
                self.recompute(row); self.write(row)

    def step(self):
        if self.stopping.is_set() or self.cooldown_until() > time.time():
            return False
        # Separate from the native writer lease: these operations only read.
        with (self.store.root / 'deletion-review-reader.lock').open('a+') as lease:
            try:
                fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return False
            self.recover()
            work = []
            for job in reversed(self.snapshot()):
                if job['state'] not in ('queued', 'running'):
                    continue
                if self.row(job['id'])['payload'].get('cooldown_until', 0) > time.time():
                    continue
                for index, e in enumerate(job['entries']):
                    if e['state'] == 'pending' and e.get('next_attempt_at', 0) <= time.time():
                        work.append((job['id'], index))
                if work:
                    break
            if not work:
                return False
            self.clear_worker_error()
            with ThreadPoolExecutor(max_workers=self.workers, thread_name_prefix='deletion-review-read') as pool:
                futures = [pool.submit(self.inspect_one, *item) for item in work]
                for future in futures:
                    future.result()
            return True

    def start(self):
        with self.lifecycle_lock:
            if self.stopping.is_set() or (self.thread and self.thread.is_alive()):
                return
            if self.thread is not None:
                self.restart_count += 1
            self.thread = threading.Thread(target=self.loop, name='deletion-review-queue', daemon=True)
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
            delay = 1
            try:
                worked = self.step()
                failures = 0
                self.clear_worker_error()
                if worked:
                    continue
            except Exception as error:
                failures += 1
                delay = min(30, 2 ** min(failures - 1, 5))
                with self.lifecycle_lock:
                    self.worker_error = f'{type(error).__name__}: {error}'[:500]
                    self.worker_retry_at = time.time() + delay
                import traceback
                # A storage outage can break both SQLite and the log stream.
                # Logging must never turn a recoverable read failure into a
                # dead queue. The error remains available in job status.
                try:
                    traceback.print_exc()
                except Exception:
                    pass
            self.wake.wait(delay); self.wake.clear()

    def stop(self):
        self.stopping.set(); self.wake.set()
