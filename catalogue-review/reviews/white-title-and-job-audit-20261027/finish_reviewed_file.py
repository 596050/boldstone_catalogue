"""One bounded recovery of the owner's already-confirmed, still-present file."""
import argparse
import fcntl
import json
import os
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[2]
RUNTIME = Path.home() / 'Library/Application Support/BoldstoneReview'
sys.path.insert(0, str(PROJECT / 'catalogue-review'))
from catalogue import Catalogue
from delete_dropbox import connection, execute, fingerprint, stamp, validate_review
from deletions import Deletions
from dropbox_sync import apply_inventory, read_inventory
from dropbox_sync_worker import atomic_json
from projection import Projection
from store import ReviewStore

JOB = 'delete-batch-VNqi2p5ReF03IQFvoLJz_GTy-iTOy9Hl'
OP = 'LXlMXXmEe2S3fqCTXAHq07iflfVgSP5W'
FILE = 'id:cnqzTNngPVsAAAAAAAuhQA'


def save_new(name, data):
    path = HERE / name
    with path.open('x') as stream:
        os.chmod(path, 0o600)
        json.dump(data, stream, indent=2)
        stream.flush()
        os.fsync(stream.fileno())


def reviewed_context():
    with sqlite3.connect('file:' + str(RUNTIME / 'reviews.sqlite3') + '?mode=ro', uri=True) as db:
        db.row_factory = sqlite3.Row
        job = db.execute('SELECT * FROM background_jobs WHERE id=?', (JOB,)).fetchone()
        op = db.execute('SELECT * FROM deletion_jobs WHERE id=?', (OP,)).fetchone()
        assert job['state'] == 'uncertain' and op['state'] == 'uncertain'
        body = json.loads(job['payload'])['body']
        p = json.loads(op['payload'])
        assert body['confirmed'] is True and p['queue_confirmed_at']
        assert {'id': FILE, 'revision': p['file']['revision']} in body['confirm_files']
        assert p['reason'] == 'unwanted' and not p.get('keeper_binding')
        assert op['file_id'] == p['file']['id'] == FILE
        reviews = [ReviewStore.unpack(row) for row in db.execute('SELECT * FROM reviews')]
    cat = Catalogue(PROJECT, RUNTIME)
    cat = apply_inventory(cat, read_inventory(RUNTIME / 'dropbox-sync/inventory.json'), RUNTIME)
    view = Projection(cat, reviews)
    current = Deletions.context(None, FILE, view)
    assert fingerprint(current) == p['context_hash'], 'The reviewed uses changed; do not retry.'
    return p


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    if not args.apply:
        p = reviewed_context()
        with connection(PROJECT) as (client, root):
            native = validate_review(client, p['file'], p['binding'], root)
        save_new('last-file-recovery-review.json', {'at': stamp(), 'operation_id': OP,
                 'batch_job': JOB, 'prior_confirmation_at': p['queue_confirmed_at'],
                 'context_unchanged': True, 'native': native})
        print(json.dumps({'status': 'review_verified', 'file_id': FILE,
                          'availability': native['file']['availability']}))
        return
    assert (HERE / 'last-file-recovery-review.json').exists()
    assert not (HERE / 'last-file-recovery-intent.json').exists(), 'Do not repeat this recovery.'
    with (RUNTIME / 'native-jobs/writer.lock').open('a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        reservation = RUNTIME / 'native-writer-reservation.json'
        previous = reservation.read_bytes() if reservation.exists() else None
        assert not previous or not json.loads(previous).get('active'), 'Another writer is reserved.'
        atomic_json(reservation, {'active': True, 'label': 'Finishing one reviewed deletion',
                    'reason': 'Checking and completing the unchanged final file from the confirmed 84-file batch.',
                    'owner': str(HERE), 'at': stamp()})
        try:
            p = reviewed_context()
            with connection(PROJECT) as (client, root):
                native = validate_review(client, p['file'], p['binding'], root)
                save_new('last-file-recovery-intent.json', {'at': stamp(), 'operation_id': OP,
                         'batch_job': JOB, 'confirmed_file': p['file'], 'current': native['file'],
                         'authority': 'Original exact-file confirmation retained; one explicit recovery after repeated unchanged-present readback.',
                         'uses_unchanged': True, 'prior_confirmation_at': p['queue_confirmed_at']})
                result = execute(client, p['file'], p['binding'], root)
                save_new('last-file-recovery-result.json', {'operation_id': OP, 'file_id': FILE, **result})
                print(json.dumps(result))
        finally:
            if previous is None:
                reservation.unlink(missing_ok=True)
            else:
                reservation.write_bytes(previous)


if __name__ == '__main__':
    main()
