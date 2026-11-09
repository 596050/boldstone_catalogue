"""Discover, bind and consume the union of the external equity minute files.

Source files remain read-only. A resumable binary cache is disposable: each
partition is bound to complete raw-file SHA256s and byte counts. Missing bars,
invalid rows and conflicting copies remain explicit; no prices are filled.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from research.testing_stages.common import (FIELDS, FLOOR, ROOT, HERE, atomic_json, digest, input_path, load_module,
                     lock, safe_output, sha)

ET = ZoneInfo('America/New_York')
RAW_COLUMNS = ['datetime', 'high', 'low', 'open', 'close', 'cum_volume', 'period_volume', 'oi']
RECORD = np.dtype([('minute', '<i8'), ('values', '<f8', (5,)),
                   ('flag', 'u1'), ('copies', '<u4')])
INVALID, CONFLICT = 1, 2
DEFAULT_SOURCE_IDS = ('iqfeed_equity_minute_archive',)


def schedule(cutoff=None):
    now = datetime.now(timezone.utc) if cutoff is None else datetime.fromisoformat(cutoff.replace('Z', '+00:00'))
    if now.tzinfo is None:
        raise ValueError('cutoff requires an explicit UTC offset')
    if now > datetime.now(timezone.utc) + timedelta(seconds=5):
        raise ValueError('cutoff is in the future')
    clock = load_module(ROOT / 'research/us_equity_session_close_clock_20260905_v2/session_clock.py')
    days, closes, *_ = clock.build_schedule('2007-01-01', now.astimezone(ET).date().isoformat())
    keep = [datetime.fromisoformat(str(d) + 'T' + str(c)).replace(tzinfo=ET) <= now
            for d, c in zip(days, closes)]
    days, closes = days[keep], closes[keep]
    if not len(days):
        raise ValueError('no completed exchange session since 2007 at cutoff')
    return now.astimezone(timezone.utc).isoformat(), days.tolist(), closes.tolist()


def file_stat(path):
    s = Path(path).stat()
    return {'bytes': s.st_size, 'mtime_ns': s.st_mtime_ns, 'device': s.st_dev, 'inode': s.st_ino}


def discover(roots=None, cutoff=None):
    cutoff, days, closes = schedule(cutoff)
    registry_reference = None
    if roots is None:
        from research.testing_stages.stage_01_data.registry import locations
        resolved, registry_reference = locations(DEFAULT_SOURCE_IDS)
        roots = list(resolved.values())
    roots = list(map(Path, roots))
    baseline = json.loads(FLOOR.read_text())['baseline_universe']['symbols']
    files, scans, errors, seen, found_symbols = [], [], [], set(), set()
    for root in roots:
        if not root.is_dir():
            errors.append({'path': str(root), 'error': 'ARCHIVE_ROOT_UNAVAILABLE'})
            continue
        # Read only the documented equity collections. Do not mistake futures,
        # daily files, temporary collector blocks or tick archives for stocks.
        directories = [(root / 'minute', 'begin', 'legacy_equity_archive')]
        for p in sorted(root.iterdir()):
            if p.is_dir() and (p.name.startswith('us_primary_listed_minute_book_')
                               or p.name.startswith('sp500_lifetime_minute_book_')):
                directories.extend((p / part, 'begin', p.name) for part in ('minute', 'tails'))
        for directory, label, collection in directories:
            if not directory.is_dir():
                continue
            count = 0
            for p in sorted(directory.glob('*.csv')):
                if p.name.startswith('.'):
                    continue
                found_symbols.add(p.stem.upper())
                try:
                    stat = file_stat(p)
                except OSError as e:
                    errors.append({'path': str(p), 'error': str(e)}); continue
                identity = (stat['device'], stat['inode'])
                if identity in seen:
                    continue
                seen.add(identity)
                files.append({'path': str(p.absolute()), 'symbol': p.stem.upper(),
                              'bar_label': label, 'timezone': 'America/New_York',
                              'collection': collection, **stat})
                count += 1
            scans.append({'directory': str(directory), 'file_count': count})
    symbols = sorted(set(baseline) | found_symbols)
    result = {'schema': 'marketmaker.stage1.minute_source_contract.v1',
              'cutoff_utc': cutoff, 'start': '2007-01-01', 'end': days[-1],
              'days': days, 'session_closes_et': closes, 'symbols': symbols,
              'baseline_symbols': baseline, 'files': files, 'directories': scans,
              'discovery_errors': errors, 'roots': list(map(str, roots)),
              'policy': {'path': str(FLOOR), 'sha256': sha(FLOOR)},
              'path_registry': registry_reference,
              'bar_seconds': 60, 'price_currency': 'USD',
              'calendar_scope': 'XNYS regular sessions; every observed extended-hours bar also retained',
              'expected_grid': 'every baseline and added stock on every regular-session minute; no inferred listing exceptions',
              'bar_clock_authority': 'Beginning labels: retained default/explicit-label protocol probes agree for these collectors',
              'clock_evidence': [{'path': str(HERE / 'inputs/frozen_ig_pair_20260907' / name),
                                  'sha256': sha(HERE / 'inputs/frozen_ig_pair_20260907' / name)}
                                 for name in ('CLOCK_PROBE.json', 'CLOCK_DEFAULT_PROBE.json')],
              'historical_receipt_clocks': 'NOT_ESTABLISHED',
              'security_lifecycle_and_PIT': 'NOT_ESTABLISHED',
              'corporate_action_completeness': 'NOT_ESTABLISHED',
              'qualification': 'NOT_ESTABLISHED',
              'source_hashes_status': 'PENDING_COMPLETE_READ_IN_PREPARE'}
    result['contract_id'] = digest(result)
    return result


def selected_contract(parent_reference, selection_reference, context_symbols=()):
    """Bind a user-requested diagnostic roster without altering the full floor.

    Retain every parent file for the selected stocks and required signal context,
    including overlaps and failed/missing stocks. Context affects signals only.
    A static roster is not historical point-in-time index membership.
    """
    def read(reference):
        p = input_path(reference['path'])
        if sha(p) != reference['sha256']:
            raise ValueError('selection input hash changed: ' + str(p))
        return json.loads(p.read_text())
    parent = read(parent_reference)
    if parent.get('selection'):
        raise ValueError('selection parent must be the full shared source contract')
    validate_contract(parent)
    roster = read(selection_reference)
    selected = roster['symbols']
    if (not selected or selected != sorted(set(selected))
            or any(not isinstance(s, str) or Path(s).name != s or s in ('.', '..')
                   or '\x00' in s for s in selected)):
        raise ValueError('selection requires a nonempty sorted unique symbol list')
    context = sorted(set(context_symbols) - set(selected))
    if not set(context) <= set(parent['symbols']):
        raise ValueError('signal context is absent from the full source contract')
    symbols = sorted(set(selected) | set(context))
    result = {**parent, 'schema': 'marketmaker.stage1.minute_source_selection.v1',
        'symbols': symbols,
        'baseline_symbols': sorted(set(parent['baseline_symbols']) & set(symbols)),
        'files': [f for f in parent['files'] if f['symbol'] in symbols],
        'selection': {'reference': selection_reference, 'parent_contract': parent_reference,
            'label': roster['label'], 'symbols': selected, 'context_symbols': context,
            'scope': 'STATIC_ROSTER_DIAGNOSTIC_NOT_FULL_ARCHIVE_QUALIFICATION',
            'membership_evidence': roster.get('membership_evidence', 'NOT_ESTABLISHED')},
        'expected_grid': 'Every selected stock on every regular minute plus observed extended bars; '
            'signal-only context is consumed but excluded from portfolio/coverage denominators.',
        'qualification': 'NOT_ESTABLISHED'}
    result.pop('contract_id', None)
    result['contract_id'] = digest(result)
    return result


def evaluation_symbols(contract):
    return contract.get('selection', {}).get('symbols', contract['symbols'])


def validate_contract(contract):
    c = dict(contract); identity = c.pop('contract_id')
    if digest(c) != identity:
        raise ValueError('source contract digest mismatch')
    if c.get('schema') == 'marketmaker.stage1.minute_source_selection.v1':
        selection = c['selection']
        expected = selected_contract(selection['parent_contract'], selection['reference'],
                                     selection['context_symbols'])
        if expected != contract:
            raise ValueError('selection changed source files, dates, context or roster')
        return contract
    if (c['schema'] != 'marketmaker.stage1.minute_source_contract.v1'
            or c['start'] != '2007-01-01' or c['bar_seconds'] != 60
            or not set(json.loads(FLOOR.read_text())['baseline_universe']['symbols']) <= set(c['symbols'])
            or c['symbols'] != sorted(set(c['symbols']))
            or any(Path(s).name != s or s in ('.', '..') or '\x00' in s for s in c['symbols'])
            or c['days'] != sorted(set(c['days'])) or c['end'] != c['days'][-1]
            or c['policy']['sha256'] != sha(FLOOR)
            or any(f['symbol'] not in c['symbols'] for f in c['files'])):
        raise ValueError('invalid or narrowed minute source contract')
    _, days, closes = schedule(c['cutoff_utc'])
    if days != c['days'] or closes != c['session_closes_et']:
        raise ValueError('source calendar does not match the frozen cutoff')
    return contract


class HashReader(io.RawIOBase):
    def __init__(self, handle):
        self.handle, self.count, self.hasher = handle, 0, hashlib.sha256()
        self.pending, self.lines, self.data_rows = b'', 0, 0

    def readable(self):
        return True

    def readinto(self, buffer):
        n = self.handle.readinto(buffer)
        if n:
            self.hasher.update(memoryview(buffer)[:n]); self.count += n
            lines = (self.pending + bytes(memoryview(buffer)[:n])).split(b'\n')
            self.pending = lines.pop()
            for line in lines:
                self.validate_line(line)
        return n

    def validate_line(self, line):
        self.lines += 1
        if self.lines == 1 or not line.strip():
            return  # Header is checked explicitly by read_file.
        line = line.rstrip(b'\r')
        commas = line.count(b',')
        if commas != 7 and not (commas == 8 and line.endswith(b',')):
            raise ValueError('invalid raw minute field count at source line ' + str(self.lines))
        self.data_rows += 1

    def finish(self):
        if self.pending:
            self.validate_line(self.pending); self.pending = b''


def read_file(item, start, end, cutoff_utc, chunksize=200_000):
    """Yield parsed chunks, then a hash receipt. Every raw byte is consumed."""
    p = Path(item['path'])
    if file_stat(p) != {k: item[k] for k in file_stat(p)}:
        raise ValueError('source changed since discovery: ' + str(p))
    previous = None; rows = 0; excluded = 0
    with p.open('rb') as raw:
        reader = HashReader(raw)
        buffered = io.BufferedReader(reader, 1 << 20)
        header = buffered.readline().decode('utf-8-sig').strip().rstrip(',').split(',')
        if header != RAW_COLUMNS:
            raise ValueError('unknown minute CSV header: ' + str(p))
        first_line = buffered.peek(4096).split(b'\n', 1)[0].rstrip(b'\r')
        width = len(first_line.split(b',')) if first_line else 8
        if width not in (8, 9):
            raise ValueError('unsupported minute row width: ' + str(p))
        names = RAW_COLUMNS + (['trailing'] if width == 9 else [])
        frames = pd.read_csv(buffered, header=None, names=names, index_col=False,
                             dtype={'datetime': str}, chunksize=chunksize)
        for frame in frames:
            if width == 9 and frame['trailing'].notna().any():
                raise ValueError('unexpected nonempty ninth minute field: ' + str(p))
            stamps = pd.to_datetime(frame['datetime'], format='%Y-%m-%d %H:%M:%S', errors='raise')
            if (stamps.dt.second != 0).any():
                raise ValueError('non-minute timestamp: ' + str(p))
            local = stamps.to_numpy().astype('datetime64[m]').astype(np.int64)
            if item['bar_label'] == 'end':
                local -= 1
            elif item['bar_label'] != 'begin':
                raise ValueError('unknown timestamp label')
            if len(local) and (np.any(np.diff(local) < 0) or previous is not None and local[0] < previous):
                raise ValueError('source timestamps reverse: ' + str(p))
            if len(local):
                previous = local[-1]
            values = frame[['open', 'high', 'low', 'close', 'period_volume']].to_numpy(dtype=float)
            op, hi, lo, cl, vol = values.T
            valid = (np.isfinite(values).all(axis=1) & (lo > 0) & (hi >= lo)
                     & (op >= lo) & (op <= hi) & (cl >= lo) & (cl <= hi) & (vol >= 0)
                     & ~np.isin(values[:, :4], [19999., 99999., 999999.]).any(axis=1))
            # Invalid clocks (including ambiguous DST folds) require source
            # repair; never select a timezone fold by observed price outcomes.
            utc_end = (pd.DatetimeIndex(local.astype('datetime64[m]')).tz_localize(
                item['timezone'], ambiguous='raise', nonexistent='raise') + pd.Timedelta(minutes=1)).tz_convert('UTC')
            eligible = ((local >= np.datetime64(start, 'm').astype(np.int64))
                        & (local < (np.datetime64(end, 'D') + 1).astype('datetime64[m]').astype(np.int64))
                        & (utc_end <= pd.Timestamp(cutoff_utc)))
            a = np.empty(int(np.sum(eligible)), dtype=RECORD)
            a['minute'] = local[eligible]; a['values'] = values[eligible]
            a['flag'] = np.where(valid[eligible], 0, INVALID); a['copies'] = 1
            rows += len(frame); excluded += int(np.sum(~eligible))
            yield a
        reader.finish()
        if rows != reader.data_rows:
            raise ValueError('CSV parser did not account for every raw observation line: ' + str(p))
        if file_stat(p) != {k: item[k] for k in file_stat(p)} or reader.count != item['bytes']:
            raise ValueError('source changed or was not fully consumed: ' + str(p))
        yield {'path': str(p), 'sha256': reader.hasher.hexdigest(), 'bytes_consumed': reader.count,
               'rows_parsed': rows, 'outside_frozen_window_rows': excluded, 'bar_label': item['bar_label']}


def merge_records(parts):
    """Equal copies collapse; all disagreeing coordinates retain a NaN mark."""
    if not parts:
        return np.empty(0, RECORD)
    a = np.concatenate(parts)
    order = np.argsort(a['minute'], kind='stable'); a = a[order]
    minute, first, inverse, count = np.unique(a['minute'], return_index=True, return_inverse=True, return_counts=True)
    out = a[first].copy(); out['copies'] = count
    flags = np.zeros(len(minute), 'u1'); np.bitwise_or.at(flags, inverse, a['flag'])
    for field in range(5):
        low = np.full(len(minute), np.inf); high = np.full(len(minute), -np.inf)
        col = a['values'][:, field]
        np.minimum.at(low, inverse, col); np.maximum.at(high, inverse, col)
        flags[(count > 1) & (low != high)] |= CONFLICT
    out['flag'] = flags
    out['values'][flags != 0] = np.nan
    return out


def prepare_symbol(contract, symbol, directory):
    items = [i for i in contract['files'] if i['symbol'] == symbol]
    receipts, parts = [], []
    for item in items:
        for chunk in read_file(item, contract['start'], contract['end'], contract['cutoff_utc']):
            if isinstance(chunk, dict):
                receipts.append(chunk)
            else:
                parts.append(chunk)
    records = merge_records(parts)
    destination = directory / (symbol + '.bin')
    tmp = directory / (symbol + '.bin.tmp')
    with tmp.open('wb') as f:
        records.tofile(f); f.flush(); os.fsync(f.fileno())
    os.replace(tmp, destination)
    dates = records['minute'] // 1440
    days, offsets, counts = np.unique(dates, return_index=True, return_counts=True)
    meta = {'symbol': symbol, 'contract_id': contract['contract_id'], 'raw_files': receipts,
            'cache_sha256': sha(destination), 'rows': len(records),
            'invalid_coordinates': int(np.sum((records['flag'] & INVALID) != 0)),
            'conflicting_coordinates': int(np.sum((records['flag'] & CONFLICT) != 0)),
            'duplicate_observations': int(np.sum(records['copies'].astype(np.int64) - 1)),
            'days': {str(np.datetime64(int(d), 'D')): [int(o), int(n)] for d, o, n in zip(days, offsets, counts)},
            'first': str(np.datetime64(int(records['minute'][0]), 'm')) if len(records) else None,
            'last': str(np.datetime64(int(records['minute'][-1]), 'm')) if len(records) else None}
    atomic_json(directory / (symbol + '.json'), meta, replace=True)
    return meta


def prepare(contract, cache, progress=print):
    validate_contract(contract)
    cache = safe_output(cache) / contract['contract_id']
    with lock(cache):
        atomic_json(cache / 'SOURCE_CONTRACT.json', contract, replace=True)
        failures, completed = [], []
        for n, symbol in enumerate(contract['symbols']):
            path = cache / (symbol + '.json')
            try:
                if path.exists():
                    meta = json.loads(path.read_text())
                    if meta['contract_id'] != contract['contract_id'] or sha(cache / (symbol + '.bin')) != meta['cache_sha256']:
                        raise ValueError('cached partition changed')
                    for item in (x for x in contract['files'] if x['symbol'] == symbol):
                        if file_stat(item['path']) != {k: item[k] for k in file_stat(item['path'])}:
                            raise ValueError('raw file changed since frozen discovery')
                else:
                    # Leave the active collector's reserve intact. Peak per-
                    # symbol temporary arrays are in RAM; binary cache is new.
                    from utils.data_paths import load_data_paths
                    mount = Path(load_data_paths()['external_storage']['mount_point'])
                    reserve = 200 * 1024**3 if cache.is_relative_to(mount) else 1 * 1024**3
                    if shutil.disk_usage(cache).free < reserve:
                        raise OSError('source cache free-space reserve reached')
                    meta = prepare_symbol(contract, symbol, cache)
                completed.append(symbol)
            except (ValueError, OSError, pd.errors.ParserError) as e:
                failures.append({'symbol': symbol, 'type': type(e).__name__, 'error': str(e)})
            atomic_json(cache / 'PREPARE.json', {'contract_id': contract['contract_id'],
                        'completed': completed, 'failures': failures,
                        'status': 'RUNNING' if n + 1 < len(contract['symbols']) else
                        ('SOURCE_READ_FAILED' if failures else 'ALL_SOURCE_FILES_CONSUMED')}, replace=True)
            progress(f'prepare {n + 1}/{len(contract["symbols"])} {symbol}: ' + ('FAILED' if failures and failures[-1]['symbol'] == symbol else 'read and bound'))
        if failures:
            raise ValueError('source preparation failed; see ' + str(cache / 'PREPARE.json'))
    return cache


class Book:
    """Read a full day of all stocks with bounded memory and file handles."""
    def __init__(self, contract, cache, *, verify=True):
        self.contract = validate_contract(contract)
        self.cache = Path(cache)
        self.symbols, self.days = contract['symbols'], contract['days']
        self.meta = []
        for symbol in self.symbols:
            m = json.loads((self.cache / (symbol + '.json')).read_text())
            if m['contract_id'] != contract['contract_id']:
                raise ValueError('cache contract mismatch')
            if verify and sha(self.cache / (symbol + '.bin')) != m['cache_sha256']:
                raise ValueError('cache hash mismatch: ' + symbol)
            if (self.cache / (symbol + '.bin')).stat().st_size != m['rows'] * RECORD.itemsize:
                raise ValueError('cache length mismatch: ' + symbol)
            self.meta.append(m)

    def rows(self, column, day):
        offset, count = self.meta[column]['days'].get(day, [0, 0])
        if not count:
            return np.empty(0, RECORD)
        with (self.cache / (self.symbols[column] + '.bin')).open('rb') as f:
            f.seek(offset * RECORD.itemsize)
            a = np.fromfile(f, dtype=RECORD, count=count)
        if len(a) != count:
            raise ValueError('cache ended during session read')
        return a

    def day(self, index):
        day = self.days[index]; base = np.datetime64(day, 'm').astype(np.int64)
        rows = [self.rows(j, day) for j in range(len(self.symbols))]
        close = self.contract['session_closes_et'][index]
        close_minute = int(close[:2]) * 60 + int(close[3:5])
        starts = [int(r['minute'][0] - base) for r in rows if len(r)]
        ends = [int(r['minute'][-1] - base) + 1 for r in rows if len(r)]
        first, last = min([570] + starts), max([close_minute] + ends)
        clock = np.arange(base + first, base + last).astype('datetime64[m]')
        values = np.full((len(clock), len(self.symbols), 5), np.nan)
        flags = np.zeros((len(clock), len(self.symbols)), dtype='u1')
        counts = np.zeros_like(flags, dtype='<u4')
        for j, r in enumerate(rows):
            ix = r['minute'] - (base + first)
            values[ix, j] = r['values']; flags[ix, j] = r['flag']; counts[ix, j] = r['copies']
        expected = np.broadcast_to(((np.arange(first, last) >= 570) &
                                   (np.arange(first, last) < close_minute))[:, None], flags.shape).copy()
        # Extended prints enter the actual source/mark path. Absence outside
        # regular hours is not an asserted nontrading/lifecycle exemption.
        expected |= counts != 0
        return {'day': day, 'clock_et': clock, 'values': values, 'flags': flags,
                'observations': counts, 'expected': expected,
                'open_index': 570 - first, 'close_index': close_minute - 1 - first}

    def daily_panel(self):
        """Only features: all economics still read every minute via day()."""
        from research.testing_stages.models import Panel
        a = np.full((len(self.days), len(self.symbols), 5), np.nan)
        for j in range(len(self.symbols)):
            if not self.meta[j]['rows']:
                continue
            records = np.memmap(self.cache / (self.symbols[j] + '.bin'), dtype=RECORD, mode='r')
            for i, day in enumerate(self.days):
                offset, count = self.meta[j]['days'].get(day, [0, 0])
                r = records[offset:offset + count]
                minute = r['minute'] % 1440
                close = self.contract['session_closes_et'][i]
                end = int(close[:2]) * 60 + int(close[3:5])
                r = r[(minute >= 570) & (minute < end)]
                if (len(r) != end - 570 or np.any(r['flag'])
                        or not np.isfinite(r['values']).all()):
                    continue  # Entire incomplete feature remains unknown.
                x = r['values']
                a[i, j] = [x[0, 0], x[:, 1].max(), x[:, 2].min(), x[-1, 3], x[:, 4].sum()]
            del records
        return Panel(tuple(self.days), tuple(self.symbols), a, tuple(self.contract['session_closes_et']))
