"""Install the tested gallery fix only while native work is idle."""
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
    return json.load(urllib.request.urlopen('http://127.0.0.1:8767/api/' + endpoint, timeout=4))


def idle():
    jobs = read('jobs')
    if jobs.get('active_count') or jobs.get('reservation') or any(
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


def backup(name):
    path = out / name
    if path.exists():
        raise RuntimeError('Refusing to overwrite backup: ' + str(path))
    with closing(sqlite3.connect('file:' + str(database) + '?mode=ro', uri=True)) as src:
        with closing(sqlite3.connect(path)) as dst:
            src.backup(dst)


if '--apply' not in sys.argv:
    raise SystemExit('Pass --apply to install the tested version.')
idle()
old_health = read('health')
assert old_health['version'] == '2.13.5', old_health
with (runtime / 'native-jobs/writer.lock').open('a') as lease:
    fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
    idle()
    pid = int((runtime / 'server.pid').read_text())
    command = subprocess.check_output(['ps', '-p', str(pid), '-o', 'command='], text=True).strip()
    assert command.endswith(str(app / 'server.py')), command
    backup('reviews-before-restart.sqlite3')
    os.kill(pid, signal.SIGINT)
    for attempt in range(60):
        running = subprocess.run(['ps', '-p', str(pid), '-o', 'pid='], capture_output=True).returncode == 0
        if not running:
            break
        time.sleep(.2)
    else:
        raise RuntimeError('Old server did not exit gracefully. No replacement started.')
    before = snapshot()
    backup('reviews-after-stop.sqlite3')
    with (runtime / 'server.log').open('ab') as log:
        process = subprocess.Popen([sys.executable, str(app / 'server.py')], cwd=app,
                                   stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True)
    (runtime / 'server.pid').write_text(str(process.pid) + '\n')
    for attempt in range(100):
        try:
            health = read('health')
            if health.get('version') == '2.13.6':
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
               'writer_lease_held_during_restart': True}
    (out / 'restart-receipt.json').write_text(json.dumps(receipt, indent=2))
    print(json.dumps({'health': health, 'preserved': receipt['preserved'], 'new_pid': process.pid}))
    assert all(receipt['preserved'].values()), 'Review data changed during restart; inspect receipt.'
