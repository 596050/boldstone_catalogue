"""SQLite outbox plus an independent, fsynced intent ledger and verified backups.

The ledger is written BEFORE a publish click. Restoring an older SQLite backup
cannot erase a submission intent or allow an automatic second click.
"""
import fcntl
import json
import os
import sqlite3
from pathlib import Path

from common import Hold, atomic_json, canonical, digest, read_json, sync_directory, utc

PENDING_INTENT = {'SUBMITTING', 'VERIFYING', 'OUTCOME_UNKNOWN'}


class Store:
    def __init__(self, directory):
        self.directory = Path(directory).resolve()
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.directory, 0o700)
        self.lock = (self.directory / 'runner.lock').open('a')
        try:
            fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            self.lock.close()
            raise Hold('RUNNER_ALREADY_ACTIVE', 'Another process owns this publisher state')
        self.db = None
        try:
            self.ledger_path = self.directory / 'intent-ledger.jsonl'
            self.ledger = self.read_ledger()
            self.db = sqlite3.connect(str(self.directory / 'outbox.sqlite3'), timeout=2)
            self.db.row_factory = sqlite3.Row
            self.db.execute('PRAGMA synchronous=FULL')
            self.db.execute('PRAGMA journal_mode=DELETE')
            if self.db.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
                raise Hold('DB_INTEGRITY', 'Use recover-db with a verified backup; preserve the intent ledger')
            self.db.executescript('''
                CREATE TABLE IF NOT EXISTS jobs (
                  id TEXT PRIMARY KEY, channel_key TEXT NOT NULL, post_key TEXT NOT NULL,
                  content_hash TEXT NOT NULL, payload TEXT NOT NULL, state TEXT NOT NULL,
                  attempts INTEGER NOT NULL DEFAULT 0, next_attempt REAL NOT NULL DEFAULT 0,
                  last_error TEXT, receipt TEXT, created_utc TEXT NOT NULL, updated_utc TEXT NOT NULL,
                  UNIQUE(channel_key, post_key), UNIQUE(channel_key, content_hash));
            ''')
            columns = {r[1] for r in self.db.execute('PRAGMA table_info(jobs)')}
            if 'verify_attempts' not in columns:
                self.db.execute('ALTER TABLE jobs ADD COLUMN verify_attempts INTEGER NOT NULL DEFAULT 0')
            self.recover_ledger()
            # Preparation is reversible. Submission is not automatically replayed.
            self.db.execute("UPDATE jobs SET state='QUEUED' WHERE state IN ('PREPARING','READY')")
            self.db.execute("UPDATE jobs SET state='OUTCOME_UNKNOWN' WHERE state IN ('SUBMITTING','VERIFYING')")
            self.db.commit()
        except Exception:
            self.close()
            raise

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def close(self):
        if self.db is not None:
            self.db.close()
            self.db = None
        if not self.lock.closed:
            self.lock.close()

    def read_ledger(self):
        result, previous = [], '0' * 64
        if not self.ledger_path.exists():
            return result
        raw = self.ledger_path.read_bytes()
        if raw and not raw.endswith(b'\n'):
            raise Hold('LEDGER_TORN_WRITE', 'Preserve the ledger; an incomplete intent must not be discarded')
        for line in raw.splitlines():
            try:
                row = json.loads(line)
                checksum = row.pop('sha256')
                if row['previous_sha256'] != previous or digest(row) != checksum:
                    raise ValueError('hash chain')
            except (ValueError, KeyError, TypeError):
                raise Hold('LEDGER_INTEGRITY', 'The intent ledger does not pass its hash-chain check')
            row['sha256'] = checksum
            result.append(row)
            previous = checksum
        return result

    def event(self, kind, **data):
        row = {'kind': kind, 'utc': utc(), 'previous_sha256': self.ledger[-1]['sha256'] if self.ledger else '0' * 64, **data}
        row['sha256'] = digest(row)
        with self.ledger_path.open('ab') as stream:
            stream.write((canonical(row) + '\n').encode('utf-8'))
            stream.flush()
            os.fsync(stream.fileno())
        sync_directory(self.directory)
        self.ledger.append(row)
        return row

    @staticmethod
    def decode(row):
        if row is None:
            return None
        row = dict(row)
        row['payload'] = json.loads(row['payload'])
        row['receipt'] = json.loads(row['receipt']) if row['receipt'] else None
        return row

    def get(self, job_id):
        result = self.decode(self.db.execute('SELECT * FROM jobs WHERE id=?', (job_id,)).fetchone())
        if result is None:
            raise Hold('JOB_NOT_FOUND', job_id)
        return result

    def jobs(self):
        return [self.decode(row) for row in self.db.execute('SELECT * FROM jobs ORDER BY created_utc,id')]

    def enqueue(self, jobs, state='QUEUED', receipts=None):
        inserted = 0
        with self.db:
            for job in jobs:
                old = self.db.execute('SELECT * FROM jobs WHERE (channel_key=? AND post_key=?) OR (channel_key=? AND content_hash=?)',
                                      (job['channel_key'], job['post_key'], job['channel_key'], job['content_hash'])).fetchone()
                if old:
                    if old['content_hash'] != job['content_hash']:
                        raise Hold('EXISTING_PRODUCT_GUARD', job['post_key'] + ' already has a delivery record for this account')
                    continue
                receipt = receipts.get(job['id']) if receipts else None
                self.db.execute('INSERT INTO jobs(id,channel_key,post_key,content_hash,payload,state,receipt,created_utc,updated_utc) VALUES(?,?,?,?,?,?,?,?,?)',
                                (job['id'], job['channel_key'], job['post_key'], job['content_hash'], canonical(job['payload']), state,
                                 canonical(receipt) if receipt else None, utc(), utc()))
                inserted += 1
        return inserted

    def change(self, job_id, state, error=None, next_attempt=0, increment=False):
        old = self.get(job_id)
        if old['state'] in PENDING_INTENT and state not in PENDING_INTENT | {'PUBLISHED'}:
            raise Hold('INTENT_CANNOT_BE_RESET', 'Reconcile the native post; never reset an uncertain submission')
        if old['state'] in {'PUBLISHED', 'HISTORICAL_VERIFIED'} and state != old['state']:
            raise Hold('TERMINAL_DELIVERY', 'A confirmed delivery cannot be requeued')
        with self.db:
            self.db.execute('UPDATE jobs SET state=?,last_error=?,next_attempt=?,attempts=attempts+?,updated_utc=? WHERE id=?',
                            (state, error, next_attempt, int(increment), utc(), job_id))

    def has_intent(self, job_id):
        return any(e['kind'] == 'PUBLISH_INTENT' and e['job']['id'] == job_id for e in self.ledger)

    def verification_attempt(self, job_id):
        with self.db:
            self.db.execute('UPDATE jobs SET verify_attempts=verify_attempts+1 WHERE id=?', (job_id,))
        return self.get(job_id)['verify_attempts']

    def intent(self, job_id):
        job = self.get(job_id)
        if self.has_intent(job_id) or job['state'] != 'READY':
            raise Hold('SUBMISSION_ALREADY_ATTEMPTED', job_id)
        self.event('PUBLISH_INTENT', job={k: job[k] for k in ['id', 'channel_key', 'post_key', 'content_hash', 'payload']})
        self.change(job_id, 'SUBMITTING')

    def published(self, job_id, receipt):
        if not self.has_intent(job_id):
            raise Hold('MISSING_INTENT')
        if not all(receipt.get(k) for k in ['native_url', 'caption_verified', 'author_verified', 'photo_verified', 'evidence_path', 'evidence_sha256']):
            raise Hold('RECEIPT_INCOMPLETE')
        if digest(Path(receipt['evidence_path']).read_bytes()) != receipt['evidence_sha256']:
            raise Hold('EVIDENCE_CHANGED')
        self.event('PUBLISHED', job_id=job_id, receipt=receipt)
        with self.db:
            self.db.execute("UPDATE jobs SET state='PUBLISHED',receipt=?,last_error=NULL,updated_utc=? WHERE id=?", (canonical(receipt), utc(), job_id))

    def recover_ledger(self):
        for event in self.ledger:
            if event['kind'] == 'PUBLISH_INTENT':
                job = event['job']
                self.enqueue([job], state='OUTCOME_UNKNOWN')
                old = self.get(job['id'])
                if old['state'] not in {'PUBLISHED', 'HISTORICAL_VERIFIED', 'OUTCOME_UNKNOWN'}:
                    self.change(job['id'], 'OUTCOME_UNKNOWN', 'Recovered a durable publish intent; reconcile only')
            elif event['kind'] == 'PUBLISHED':
                r = event['receipt']
                evidence = Path(r['evidence_path'])
                if not evidence.is_file() or digest(evidence.read_bytes()) != r['evidence_sha256']:
                    raise Hold('EVIDENCE_MISSING', 'Do not restore a delivery without its verified evidence')
                self.db.execute("UPDATE jobs SET state='PUBLISHED',receipt=?,last_error=NULL WHERE id=?", (canonical(r), event['job_id']))
            elif event['kind'] == 'HISTORICAL_VERIFIED':
                self.enqueue([event['job']], state='HISTORICAL_VERIFIED', receipts={event['job']['id']: event['receipt']})
        self.db.commit()

    def import_history(self, job, receipt):
        old = self.db.execute('SELECT id FROM jobs WHERE channel_key=? AND post_key=?', (job['channel_key'], job['post_key'])).fetchone()
        if old:
            existing = self.get(old['id'])
            if existing['state'] not in {'PUBLISHED', 'HISTORICAL_VERIFIED'}:
                raise Hold('HISTORY_CONFLICT', 'A queued or uncertain job already exists for this account and product')
            return 0
        self.event('HISTORICAL_VERIFIED', job=job, receipt=receipt)
        return self.enqueue([job], state='HISTORICAL_VERIFIED', receipts={job['id']: receipt})

    def export(self):
        rows = self.jobs()
        counts = {}
        for row in rows:
            counts[row['state']] = counts.get(row['state'], 0) + 1
        report = {'utc': utc(), 'counts': counts, 'jobs': rows,
                  'complete': bool(rows) and all(r['state'] in {'PUBLISHED', 'HISTORICAL_VERIFIED'} for r in rows)}
        atomic_json(self.directory / 'status.json', report)
        return report

    def backup(self):
        destination = self.directory / 'outbox-backup.sqlite3'
        temporary = self.directory / '.outbox-backup.tmp'
        with sqlite3.connect(str(temporary)) as copy:
            self.db.backup(copy)
            if copy.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
                raise Hold('BACKUP_INTEGRITY')
        with temporary.open('rb') as stream:
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
        sync_directory(self.directory)
        return destination

