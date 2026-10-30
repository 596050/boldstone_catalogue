"""Install tested worker recovery only when native changes and checks are idle."""
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
import fcntl
import hashlib
import json
import os
import signal
import sqlite3
import subprocess
import sys
import time
import urllib.request

out = Path(__file__).resolve().parent
app = out.parent.parent
runtime = Path('/Users/tprice/Library/Application Support/BoldstoneReview')
database = runtime / 'reviews.sqlite3'
tables = ('reviews', 'events', 'deletion_jobs', 'deletion_batches', 'background_jobs', 'deletion_reviews')



def read(endpoint):
    return json.load(urllib.request.urlopen('http://127.0.0.1:8767/api/' + endpoint, timeout=12))


def no_native_work():
    jobs = read('jobs')
    if jobs.get('active_count') or jobs.get('reservation') or (jobs.get('filename_job') or {}).get('state') == 'running' or any(
        j['state'] in ('queued', 'running', 'uncertain') for j in jobs['jobs']
    ):
        raise RuntimeError('Native work is active. Restart deferred.')


def snapshot():
    with closing(sqlite3.connect('file:' + str(database) + '?mode=ro', uri=True)) as db:
        db.execute('BEGIN')
        return {table: {'count': len(rows), 'sha256': hashlib.sha256(
                    json.dumps(rows, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()}
                for table in tables
                for rows in [db.execute('SELECT * FROM ' + table + ' ORDER BY rowid').fetchall()]}


if '--apply' not in sys.argv:
    raise SystemExit('Pass --apply to install the tested recovery fix.')
no_native_work()
old_health = read('health')
assert old_health['version'] == '2.14.2', old_health
with (runtime / 'native-jobs/writer.lock').open('a') as writer, \
     (runtime / 'deletion-review-reader.lock').open('a') as reader:
    fcntl.flock(writer, fcntl.LOCK_EX | fcntl.LOCK_NB)
    fcntl.flock(reader, fcntl.LOCK_EX | fcntl.LOCK_NB)
    no_native_work()
    pid = int((runtime / 'server.pid').read_text())
    command = subprocess.check_output(['ps', '-p', str(pid), '-o', 'command='], text=True).strip()
    assert command.endswith(str(app / 'server.py')), command
    backup = out / 'reviews-before-restart.sqlite3'
    assert not backup.exists(), 'Refusing to overwrite the recovery backup'
    with closing(sqlite3.connect('file:' + str(database) + '?mode=ro', uri=True)) as src, \
         closing(sqlite3.connect(backup)) as dst:
        assert src.execute('PRAGMA quick_check').fetchone()[0] == 'ok'
        src.backup(dst)
    os.kill(pid, signal.SIGINT)
    for attempt in range(60):
        if subprocess.run(['ps', '-p', str(pid), '-o', 'pid='], capture_output=True).returncode != 0:
            break
        time.sleep(.2)
    else:
        raise RuntimeError('Old server did not exit gracefully. No replacement started.')
    before = snapshot()
    with (runtime / 'server.log').open('ab') as log:
        process = subprocess.Popen([sys.executable, str(app / 'server.py')], cwd=app,
                                   stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True)
    (runtime / 'server.pid').write_text(str(process.pid) + '\n')
    for attempt in range(100):
        try:
            health = read('health')
            if health.get('version') == '2.14.3':
                break
        except (OSError, ValueError):
            pass
        if process.poll() is not None:
            raise RuntimeError('New server stopped; inspect its log.')
        time.sleep(.2)
    else:
        raise RuntimeError('New health response did not arrive.')
    after = snapshot()
    receipt = {'checked_utc': datetime.now(timezone.utc).isoformat(), 'old_pid': pid,
               'new_pid': process.pid, 'old_health': old_health, 'health': health,
               'before': before, 'after': after,
               'preserved': {t: before[t] == after[t] for t in tables},
               'writer_and_reader_leases_held_during_restart': True}
    (out / 'restart-receipt.json').write_text(json.dumps(receipt, indent=2))
    print(json.dumps({'health': health, 'preserved': receipt['preserved'], 'new_pid': process.pid}))
    assert all(receipt['preserved'].values()), 'Saved data changed during restart; inspect receipt.'
