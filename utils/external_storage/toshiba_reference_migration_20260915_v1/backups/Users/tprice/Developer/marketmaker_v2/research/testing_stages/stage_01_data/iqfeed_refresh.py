"""Authentic IQFeed refreshes with recoverable, atomic raw-file replacement.

Reuses the project's protocol-6.2 history socket and daily CSV convention.
Daily history is replaced as one adjustment vintage; minute overlaps are merged
by timestamp; tick days are replaced whole, preserving every distinct trade.
No response, timeout, malformed response or lost history can erase a source.
"""
from contextlib import contextmanager
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta, timezone
from itertools import groupby
from zoneinfo import ZoneInfo
import csv
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import socket
import threading
import time
import uuid

SCHEMA = 'marketmaker.iqfeed_refresh.v1'
HEADERS = {
    'daily': '"Date","Time","Open","High","Low","Close","Volume"',
    'minute': 'datetime,high,low,open,close,cum_volume,period_volume,oi',
    'tick': 'datetime,last,last_size,total_volume,bid,ask,tick_id,basis,market_center,conditions,aggressor,day_code',
}


def sha(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def copy_bytes(source, destination, *, resource_policy=None):
    # macOS fcopyfile preallocates through ftruncate. On the external exFAT
    # source volume that syscall stalled other writes for several minutes.
    # Stream the same bytes without that platform-specific preallocation.
    with Path(source).open('rb') as src, Path(destination).open('xb') as dst:
        from research.testing_stages.runtime import resources
        while block := src.read(4 * 1024**2):
            resources.storage(destination, resource_policy or {}, additional=len(block))
            dst.write(block)


def atomic_json(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name('.' + path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        with temp.open('x') as f:
            json.dump(value, f, indent=2, sort_keys=True); f.write('\n'); f.flush(); os.fsync(f.fileno())
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def snapshot(path):
    if not path.exists():
        return None
    s = path.stat()
    return (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns)


@contextmanager
def file_lock(path):
    """Kernel ownership, never delete another process's apparently old lock."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a+') as f:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise RuntimeError('SOURCE_REFRESH_LOCKED: ' + str(path)) from error
        try:
            f.seek(0); f.truncate(); json.dump({'pid': os.getpid()}, f); f.flush()
            yield
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def external_paths(paths):
    from utils.data_paths import ensure_external_storage, load_data_paths
    ensure_external_storage()
    mount = Path(load_data_paths()['external_storage']['mount_point'])
    for path in map(Path, paths):
        relative = path.absolute().relative_to(mount)
        current = mount
        for part in relative.parts:
            current /= part
            if current.is_symlink():
                raise ValueError('raw refresh path traverses a symlink: ' + str(current))


def row_day(line, cadence):
    value = line.split(',', 1)[0].strip('"')
    return (datetime.strptime(value, '%m/%d/%Y').date().isoformat()
            if cadence == 'daily' else date.fromisoformat(value[:10]).isoformat())


def endpoints(path, cadence):
    """Read just the endpoints; every existing row is checked before replacement."""
    if not path.exists() or path.stat().st_size == 0:
        return None, None
    with path.open('rb') as f:
        f.readline(); first = f.readline().decode('ascii').strip()
        if not first:
            return None, None
        f.seek(max(0, path.stat().st_size - 16384))
        lines = [x for x in f.read().decode('ascii').splitlines() if x.strip()]
    return row_day(first, cadence), row_day(lines[-1], cadence)


def numeric(value, *, positive=False, integer=False):
    v = float(value)
    if not math.isfinite(v) or (v <= 0 if positive else v < 0) or (integer and not v.is_integer()):
        raise ValueError('invalid IQFeed numeric field')
    return v


def normalize(fields, cadence):
    while fields and fields[-1] == '':
        fields.pop()
    expected = {'daily': 7, 'minute': 8, 'tick': 12}[cadence]
    if len(fields) != expected:
        raise ValueError(f'IQFeed {cadence} expected {expected} fields, received {len(fields)}')
    if cadence == 'tick':
        datetime.fromisoformat(fields[0])
        numeric(fields[1], positive=True)
        for i in (2, 3, 6):
            numeric(fields[i], integer=True)
        for i in (4, 5):
            numeric(fields[i])
    else:
        if cadence == 'daily':
            date.fromisoformat(fields[0])
        else:
            stamp = datetime.fromisoformat(fields[0])
            if stamp.second or stamp.microsecond:
                raise ValueError('minute timestamp is not minute aligned')
        high, low, open_, close = [numeric(v, positive=True) for v in fields[1:5]]
        # Preserve authentic but inconsistent provider observations. They are
        # counted in the receipt and become invalid/missing derived bars; raw
        # prices are never adjusted to make high/low agree with open/close.
        for v in fields[5:]:
            numeric(v, integer=True)
        if cadence == 'daily':
            return ','.join([date.fromisoformat(fields[0]).strftime('%m/%d/%Y'),
                             '0000', fields[3], fields[1], fields[2], fields[4], fields[5]])
    return ','.join(fields)


def consistent_ohlc(line, cadence):
    if cadence == 'tick':
        return True
    fields = line.split(',')
    open_, high, low, close = (map(float, fields[2:6]) if cadence == 'daily' else
                              (float(fields[3]), float(fields[1]), float(fields[2]), float(fields[4])))
    return low <= min(open_, close, high) and high >= max(open_, close)


class Lookup:
    def __init__(self, host='127.0.0.1', port=9100, timeout=120):
        self.host, self.port, self.timeout = host, int(port), float(timeout)
        self._rate_lock = threading.Lock()
        self._last_request = 0.0

    def rows(self, entry, begin, end):
        with self._rate_lock:
            time.sleep(max(0, .025 - (time.monotonic() - self._last_request)))
            self._last_request = time.monotonic()
        symbol, cadence = entry['symbol'], entry['cadence']
        request = 'TS' + uuid.uuid4().hex[:20]
        b, e = begin.replace('-', ''), end.replace('-', '')
        if cadence == 'daily':
            command = f'HDT,{symbol},{b},{e},,1,{request},5000'
        elif cadence == 'minute':
            # Explicit beginning labels, matching the retained raw minute archive.
            command = f'HIT,{symbol},60,{b} 000000,{e} 235959,,,,1,{request},5000,s,1'
        else:
            command = f'HTT,{symbol},{b} 000000,{e} 235959,,,,1,{request},5000'
        with socket.create_connection((self.host, self.port), timeout=self.timeout) as sock:
            sock.settimeout(self.timeout)
            with sock.makefile('rb') as reader:
                sock.sendall(b'S,SET PROTOCOL,6.2\r\n')
                if reader.readline().decode('ascii').strip() != 'S,CURRENT PROTOCOL,6.2':
                    raise ValueError('IQFeed protocol handshake failed')
                sock.sendall((command + '\r\n').encode('ascii'))
                while True:
                    raw = reader.readline()
                    if not raw:
                        raise ConnectionError('IQFeed closed before ENDMSG')
                    fields = next(csv.reader([raw.decode('ascii').strip()]))
                    if not fields or fields[0] != request:
                        raise ValueError('unexpected IQFeed request ID or system response')
                    fields = fields[1:]
                    if fields and fields[0] == '!ENDMSG!':
                        break
                    if fields and fields[0] in ('E', '!ERROR!', '!NO_DATA!'):
                        if any('!NO_DATA!' in x for x in fields):
                            continue
                        raise ValueError('IQFeed response error: ' + ','.join(fields))
                    if fields and fields[0] in ('LH', 'TH'):
                        fields = fields[1:]
                    yield normalize(fields, cadence)


def checked_rows(path, cadence, offset=None):
    with path.open() as f:
        if offset is None:
            header = f.readline().strip()
            if not header.lower().startswith(('"date"', 'datetime')):
                raise ValueError('unrecognized raw source header: ' + str(path))
        else:
            f.seek(offset)
        previous = None
        for line in f:
            if not line.strip():
                continue
            day = row_day(line, cadence)
            key = day if cadence == 'daily' else line.split(',', 1)[0]
            if previous is not None and (key < previous or (cadence != 'tick' and key == previous)):
                raise ValueError('unordered/duplicate raw source coordinates: ' + str(path))
            previous = key
            yield key, line.rstrip('\r\n')


def copy_minute_prefix(path, out, day, block_size=4 * 1024**2):
    """Copy the old byte prefix exactly, stopping at its last day's first row.

    Full source parsing belongs to data preparation. Refresh only merges the
    overlap; no previous observation is interpreted, adjusted or discarded.
    The marker always exists because ``day`` came from this file's last row.
    """
    marker = b'\n' + day.encode('ascii') + b' '
    pending = b''; written = 0
    with path.open('rb') as f:
        while True:
            chunk = f.read(block_size)
            if not chunk:
                raise ValueError('minute tail marker absent or source changed')
            pending += chunk
            at = pending.find(marker)
            if at >= 0:
                out.write(pending[:at + 1])
                return written + at + 1
            keep = len(marker) - 1
            count = max(0, len(pending) - keep)
            out.write(pending[:count]); written += count; pending = pending[count:]


def replacement(entry, downloaded, destination, resource_policy=None):
    """Retain old minute rows absent from the new response; new observed keys win."""
    cadence = entry['cadence']; path = Path(entry['path'])
    old = checked_rows(path, cadence) if path.exists() else iter(())
    new = checked_rows(downloaded, cadence)
    if cadence == 'daily':
        old_days = {k for k, _ in old}
        new_days = {k for k, _ in new}
        if not old_days <= new_days:
            raise ValueError('IQFeed daily replacement would lose existing history')
        copy_bytes(downloaded, destination, resource_policy=resource_policy)
        return
    if cadence == 'tick':
        # Check containment as a multiset within each timestamp. A later full-day
        # response may add trades, but cannot erase any previously saved event.
        # Neither timestamp deduplication nor set equality preserves multiplicity.
        groups = iter(groupby(new, key=lambda row: row[0]))
        b = next(groups, None)
        for stamp, rows in groupby(old, key=lambda row: row[0]):
            counts = Counter(line for _, line in rows)
            if stamp[:10] != entry['day']:
                raise ValueError('tick replacement path contains a different day')
            while b is not None and b[0] < stamp:
                b = next(groups, None)
            available = Counter(line for _, line in b[1]) if b is not None and b[0] == stamp else Counter()
            if counts - available:
                raise ValueError('TICK_HISTORY_LOSS: provider reply omits or changes retained trades; original preserved')
            b = next(groups, None)
        copy_bytes(downloaded, destination, resource_policy=resource_policy)
        return
    with destination.open('xb') as out:
        last_day = endpoints(path, cadence)[1] if path.exists() else None
        if last_day:
            offset = copy_minute_prefix(path, out, last_day)
            old = checked_rows(path, cadence, offset)
        else:
            out.write((HEADERS[cadence] + '\n').encode('ascii'))
        a, b = next(old, None), next(new, None)
        while a is not None or b is not None:
            if b is None or (a is not None and a[0] < b[0]):
                out.write((a[1] + '\n').encode('ascii')); a = next(old, None)
            else:
                out.write((b[1] + '\n').encode('ascii'))
                if a is not None and a[0] == b[0]:
                    a = next(old, None)
                b = next(new, None)


def tick_day_closed(day, now=None):
    """A full calendar-day HTT request is not final at the equity market close."""
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise ValueError('tick freshness clock must have a timezone')
    cutoff = datetime.combine(date.fromisoformat(day) + timedelta(days=1), datetime.min.time(),
                              ZoneInfo('America/New_York')) + timedelta(minutes=10)
    return current >= cutoff


def refresh_entry(entry, end, versions, lookup, resource_policy=None, *, now=None):
    from research.testing_stages.runtime import resources
    resource_policy = resource_policy or {}
    path = Path(entry['path']); cadence = entry['cadence']
    path.parent.mkdir(parents=True, exist_ok=True)
    state_path = path.with_name('.' + path.name + '.freshness.json')
    with file_lock(path.with_name('.' + path.name + '.refresh.lock')):
        before = snapshot(path)
        first, last = endpoints(path, cadence)
        prior = json.loads(state_path.read_text()) if state_path.exists() else {}
        if cadence == 'tick' and (end != entry['day'] or first and (first != entry['day'] or last != entry['day'])):
            raise ValueError('tick partition contains or requests a different day')
        if last and last >= end:
            digest = sha(path)
            covered = (prior.get('requested_end', '') >= end and prior.get('sha256') == digest)
            current = (covered and prior.get('tick_day_closed') is True) if cadence == 'tick' else (
                cadence == 'daily' or last > end or covered)
            if current:
                return {'symbol': entry['symbol'], 'cadence': cadence, 'path': str(path),
                        'status': 'CURRENT', 'first': first, 'last': last, 'sha256': digest,
                        **({'day': entry['day'], 'tick_day_closed': True} if cadence == 'tick' else {})}
        begin = (entry['day'] if cadence == 'tick' else
                 (min(first, entry.get('history_start', first)) if first and cadence == 'daily' else
                  last or entry.get('history_start', '2007-01-03')))
        token = uuid.uuid4().hex
        downloaded = path.with_name('.' + path.name + '.' + token + '.download')
        prepared = path.with_name('.' + path.name + '.' + token + '.replacement')
        count = 0; inconsistent = 0; latest = None; previous = None
        request_clock = now or datetime.now(timezone.utc)
        requested_at = request_clock.isoformat()
        closed_tick_day = tick_day_closed(entry['day'], request_clock) if cadence == 'tick' else None
        try:
            resources.storage(path, resource_policy, additional=(path.stat().st_size * 2 if path.exists() else 0))
            resources.storage(versions, resource_policy)
            with downloaded.open('x') as f:
                f.write(HEADERS[cadence] + '\n')
                for line in lookup.rows(entry, begin, end):
                    day = row_day(line, cadence)
                    key = day if cadence == 'daily' else line.split(',', 1)[0]
                    if not begin <= day <= end or (previous is not None and
                            (key < previous or (cadence != 'tick' and key == previous))):
                        raise ValueError('IQFeed response outside requested range or unordered/duplicate')
                    f.write(line + '\n'); previous = key; latest = day; count += 1
                    if count % 4096 == 0:
                        resources.storage(downloaded, resource_policy)
                    inconsistent += not consistent_ohlc(line, cadence)
                f.flush(); os.fsync(f.fileno())
            if not count:
                # An empty reply is still an observation of an exact request.
                # Bind the retained source across its hash read as on the
                # nonempty path; another writer must not supply a new vintage
                # under endpoints observed before this request.
                if snapshot(path) != before:
                    raise ValueError('raw source changed while refresh was in flight')
                retained_hash = sha(path) if path.exists() else None
                if snapshot(path) != before:
                    raise ValueError('raw source changed while verifying the empty response')
                return {'symbol': entry['symbol'], 'cadence': cadence, 'path': str(path),
                        'status': 'NO_PROVIDER_DATA', 'requested_begin': begin,
                        'requested_end': end, 'last': last, 'received_rows': 0,
                        'requested_at_utc': requested_at,
                        'observed_at_utc': datetime.now(timezone.utc).isoformat(),
                        'sha256': retained_hash, 'raw_changed': False}
            replacement(entry, downloaded, prepared, resource_policy=resource_policy)
            resources.storage(path, resource_policy)
            if snapshot(path) != before:
                raise ValueError('raw source changed while refresh was in flight')
            old_hash = sha(path) if path.exists() else None
            backup = Path(versions) / (old_hash + path.suffix) if old_hash else None
            if backup:
                backup.parent.mkdir(parents=True, exist_ok=True)
                if not backup.exists():
                    tmp = backup.with_name(backup.name + '.' + token)
                    copy_bytes(path, tmp, resource_policy=resource_policy)
                    if sha(tmp) != old_hash:
                        raise ValueError('raw backup did not reproduce previous bytes')
                    os.replace(tmp, backup)
                elif sha(backup) != old_hash:
                    raise ValueError('existing raw version is corrupt')
            if snapshot(path) != before:
                raise ValueError('raw source changed before publication')
            with prepared.open('rb') as f:
                os.fsync(f.fileno())
            new_hash = sha(prepared)
            if path.exists():
                shutil.copymode(path, prepared)
            os.replace(prepared, path)
            first, last = endpoints(path, cadence)
            record = {'symbol': entry['symbol'], 'cadence': cadence, 'path': str(path),
                'status': 'UPDATED' if latest == end else 'PROVIDER_TAIL_GAP', 'requested_begin': begin,
                'requested_end': end, 'received_rows': count, 'inconsistent_ohlc_rows': inconsistent,
                'first': first, 'last': last,
                'previous_sha256': old_hash, 'sha256': new_hash, 'previous_version': str(backup) if backup else None,
                'raw_changed': old_hash != new_hash, 'requested_at_utc': requested_at,
                'observed_at_utc': datetime.now(timezone.utc).isoformat()}
            if cadence == 'tick':
                record.update(day=entry['day'], tick_day_closed=closed_tick_day,
                              raw_stat=list(snapshot(path)), retention_policy='cumulative_day_partitions_no_expiry')
            atomic_json(state_path, record)
            return record
        finally:
            downloaded.unlink(missing_ok=True); prepared.unlink(missing_ok=True)


def validate_entries(entries):
    paths = set()
    for e in entries:
        if e['cadence'] not in HEADERS or not re.fullmatch(r'[A-Z0-9][A-Z0-9.\-@#^]{0,31}', e['symbol']):
            raise ValueError('unsupported cadence or unsafe IQFeed symbol')
        p = Path(e['path'])
        if not p.is_absolute() or p in paths or '..' in p.parts:
            raise ValueError('raw paths must be absolute and unique')
        paths.add(p)
        if e['cadence'] == 'tick':
            date.fromisoformat(e['day'])
        if 'history_start' in e:
            date.fromisoformat(e['history_start'])


def refresh(manifest, end, output, *, lookup=None, verify_paths=external_paths, workers=1, resource_policy=None, now=None):
    if manifest.get('schema') != SCHEMA or not 1 <= workers <= 4:
        raise ValueError('invalid IQFeed refresh manifest or worker count')
    date.fromisoformat(end)
    entries = manifest['entries']; validate_entries(entries)
    if resource_policy:
        workers = min(workers, resource_policy['iqfeed_workers'], resource_policy['io_workers'])
    if any(e.get('day', end) > end for e in entries):
        raise ValueError('a source request extends beyond the declared end')
    output = Path(output); versions = Path(manifest['versions'])
    verify_paths([versions, *(e['path'] for e in entries)])
    output.mkdir(parents=True, exist_ok=True)
    implementation = output / 'REFRESH_IMPLEMENTATION.py'
    if implementation.exists() and sha(implementation) != sha(__file__):
        raise ValueError('use a fresh refresh output for changed implementation')
    if not implementation.exists():
        shutil.copyfile(__file__, implementation)
    report = {'schema': 'marketmaker.iqfeed_refresh_receipt.v1', 'requested_end': end,
              'request_manifest': manifest, 'implementation_sha256': sha(implementation),
              'implementation_path': str(implementation), 'protocol': '6.2',
              'entries': [], 'status': 'RUNNING', 'total_entries': len(entries),
              'workers': workers, 'execution_resources': resource_policy or {}}
    lookup = lookup or Lookup(**manifest.get('connection', {}))
    with file_lock(versions / 'REFRESH.lock'):
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(refresh_entry, e, e.get('day', end), versions, lookup, resource_policy, now=now): e for e in entries}
            for future in as_completed(futures):
                entry = futures[future]
                try:
                    result = future.result()
                except Exception as error:
                    result = {**entry, 'status': 'FAILED', 'reason': str(error)}
                report['entries'].append(result)
                atomic_json(output / 'REFRESH.json', report)
                print(json.dumps({'completed': len(report['entries']), 'total': len(entries),
                                  'symbol': entry['symbol'], 'cadence': entry['cadence'],
                                  'day': entry.get('day'), 'path': entry['path'], 'status': result['status']}), flush=True)
        report['entries'].sort(key=lambda e: (e['cadence'], e['symbol'], e['path']))
        statuses = {r['status'] for r in report['entries']}
        report['status'] = ('FAILED' if 'FAILED' in statuses else
            'COMPLETE_WITH_SOURCE_GAPS' if statuses & {'NO_PROVIDER_DATA', 'PROVIDER_TAIL_GAP'} else 'COMPLETE')
        atomic_json(output / 'REFRESH.json', report)
    if report['status'] == 'FAILED':
        raise ValueError('IQFEED_REFRESH_FAILED: inspect ' + str(output / 'REFRESH.json'))
    return report
