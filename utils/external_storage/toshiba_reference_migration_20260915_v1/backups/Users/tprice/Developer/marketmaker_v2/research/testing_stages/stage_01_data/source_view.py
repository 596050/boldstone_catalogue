"""Full-source partitions and exact sparse evaluation of statically flat columns.

Every source file is parsed and hashed. Every eligible record contributes to
the full-grid coverage/abstention denominators and feature construction. Model
accounting need only read the declared eligible columns: all other holdings are
checked to be identically zero. This avoids millions of unnecessary disk seeks.
"""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor, as_completed
from copy import deepcopy
from functools import lru_cache
import json
import os
from pathlib import Path
import time

import numpy as np
from research.testing_stages import source
from research.testing_stages.common import atomic_json, digest, lock, save_arrays, sha
from research.testing_stages.models import Panel


DEFAULT_SOURCE_WORKERS = 4
DAY_WINDOW_SESSIONS = 64
DAY_WINDOW_MEMORY_LIMIT = 512 * 1024**2


def prefetch_partition_metadata(book, symbols):
    """Warm directory attributes before the unchanged per-partition guards.

    VirtioFS can service a directory listing with attributes much faster than
    many expired individual lookups. These values are deliberately not used as
    proof or substituted for window_rows' before/after checks. Limit discovery
    to a small prepared directory; broad caches retain the existing path.
    """
    if (not hasattr(book, 'partition_snapshots') or len(symbols) < 2
            or getattr(book, '_partition_metadata_prefetch', True) is False):
        return
    names = {symbol + '.bin' for symbol in symbols}
    limit = max(64, 4 * len(names))
    try:
        with os.scandir(book.cache) as entries:
            for count, entry in enumerate(entries):
                if count >= limit:
                    book._partition_metadata_prefetch = False
                    return
                if entry.name in names:
                    entry.stat(follow_symlinks=True)
    except OSError:
        # An optional prefetch never replaces the authoritative read or guard.
        # Missing/changed requested files still fail through window_rows.
        book._partition_metadata_prefetch = False


def window_rows(book, index, column):
    """Read the same day offsets through a bounded, read-only memory window.

    This only coalesces disk reads. The caller still constructs exactly the
    original requested-day frame; cached later rows are never model inputs.
    Existing full-byte, partition-snapshot and independent raw-source checks
    remain in place. A changed partition also invalidates a cached window.
    """
    symbol, day = book.symbols[column], book.days[index]
    meta = book.meta[column]
    offset, count = meta['days'].get(day, (0, 0))
    if not count:
        return np.empty(0, dtype=source.RECORD)
    block = index // DAY_WINDOW_SESSIONS
    if getattr(book, '_day_window_block', None) != block:
        book._day_window_block = block
        book._day_window_rows = {}
        book._day_window_bytes = 0
    path = book.cache / (symbol + '.bin')
    current = source.file_stat(path)
    cached = book._day_window_rows.get(column)
    if cached is not None:
        first, rows, expected = cached
        if current != expected:
            raise ValueError('prepared minute partition changed: ' + symbol)
        selected = rows[offset - first:offset - first + count]
        if offset < first or len(selected) != count:
            raise ValueError('source day offsets changed during cached read: ' + symbol)
        return selected
    start = block * DAY_WINDOW_SESSIONS
    spans = [meta['days'][d] for d in book.days[start:start + DAY_WINDOW_SESSIONS]
             if d in meta['days'] and meta['days'][d][1]]
    first = min(o for o, n in spans)
    last = max(o + n for o, n in spans)
    nbytes = (last - first) * source.RECORD.itemsize
    retain = book._day_window_bytes + nbytes <= DAY_WINDOW_MEMORY_LIMIT
    if not retain:
        first, last = offset, offset + count
    with path.open('rb') as handle:
        handle.seek(first * source.RECORD.itemsize)
        rows = np.fromfile(handle, dtype=source.RECORD, count=last - first)
    if len(rows) != last - first:
        raise ValueError('source partition ended early')
    if source.file_stat(path) != current:
        raise ValueError('prepared minute partition changed: ' + symbol)
    rows.flags.writeable = False
    if retain:
        book._day_window_rows[column] = (first, rows, current)
        book._day_window_bytes += rows.nbytes
    return rows[offset - first:offset - first + count]


@lru_cache(maxsize=4)
def prior_source(path):
    value = json.loads(path.read_text())
    content = dict(value); expected = content.pop('contract_id')
    if digest(content) != expected:
        raise ValueError('predecessor source contract changed')
    return value


def reuse_partition(contract, symbol, cache, predecessor=None):
    """Reuse only complete equal source file sets with a uniform clock transform.

    Old mixed-clock merged partitions cannot be repaired by shifting: reparse
    those raw files. A uniform +1 minute change on complete, untrimmed files is
    exact; boundary-crossing or changed source files also require a raw reparse.
    The independent verifier deliberately disables reuse.
    """
    if predecessor is None:
        return None
    predecessor = Path(predecessor)
    p = predecessor / (symbol + '.json')
    if not p.exists():
        return None
    prior = prior_source(predecessor / 'SOURCE_CONTRACT.json')
    if any(prior[k] != contract[k] for k in ('start', 'end')):
        return None
    old = sorted((x for x in prior['files'] if x['symbol'] == symbol), key=lambda x: x['path'])
    new = sorted((x for x in contract['files'] if x['symbol'] == symbol), key=lambda x: x['path'])
    if not old or len(old) != len(new):
        return None
    shifts = set()
    for a, b in zip(old, new):
        if {k: v for k, v in a.items() if k != 'bar_label'} != {k: v for k, v in b.items() if k != 'bar_label'}:
            return None
        if source.file_stat(b['path']) != {k: b[k] for k in source.file_stat(b['path'])}:
            raise ValueError('raw source changed since discovery: ' + b['path'])
        shifts.add((1 if a['bar_label'] == 'end' else 0) - (1 if b['bar_label'] == 'end' else 0))
    if len(shifts) != 1:
        return None
    meta = json.loads(p.read_text()); shift = shifts.pop()
    if any(r['outside_frozen_window_rows'] for r in meta['raw_files']):
        return None
    binary = predecessor / (symbol + '.bin')
    if sha(binary) != meta['cache_sha256']:
        raise ValueError('predecessor cache hash changed: ' + symbol)
    records = np.fromfile(binary, dtype=source.RECORD)
    if len(records) != meta['rows']:
        raise ValueError('predecessor cache length changed')
    records['minute'] += shift
    if len(records) and (records['minute'][0] < np.datetime64(contract['start'], 'm').astype('i8')
                        or records['minute'][-1] >= np.datetime64(contract['end'], 'm').astype('i8') + 1440):
        return None
    result = deepcopy(meta); result['contract_id'] = contract['contract_id']
    for r in result['raw_files']:
        r['bar_label'] = next(x['bar_label'] for x in new if x['path'] == r['path'])
    destination = cache / (symbol + '.bin')
    temporary = destination.with_suffix('.reuse.tmp')
    with temporary.open('wb') as f:
        records.tofile(f); f.flush(); os.fsync(f.fileno())
    os.replace(temporary, destination)
    result['cache_sha256'] = sha(destination)
    days, offsets, counts = np.unique(records['minute'] // 1440, return_index=True, return_counts=True)
    result['days'] = {str(np.datetime64(int(d), 'D')): [int(o), int(n)] for d, o, n in zip(days, offsets, counts)}
    result['first'] = str(np.datetime64(int(records['minute'][0]), 'm')) if len(records) else None
    result['last'] = str(np.datetime64(int(records['minute'][-1]), 'm')) if len(records) else None
    result['cache_reuse'] = {'metadata': str(p), 'metadata_sha256': sha(p),
        'prior_contract_id': prior['contract_id'], 'uniform_minute_shift': shift,
        'raw_file_set_and_stats_identical': True, 'prior_raw_rows_outside_window': 0,
        'raw_bytes_reparsed_in_this_prepare': 0, 'full_source_byte_replay_pending': True}
    atomic_json(cache / (symbol + '.json'), result, replace=True)
    return result


def summarize(records, contract):
    n = len(contract['days'])
    day_axis = np.asarray(contract['days'], dtype='datetime64[D]').astype('i8')
    record_days = records['minute'] // 1440
    ix = np.searchsorted(day_axis, record_days)
    on_grid = (ix < n) & (day_axis[np.minimum(ix, n - 1)] == record_days)
    r = records[on_grid]; ix = ix[on_grid]
    minute = r['minute'] % 1440
    ends = np.asarray([int(c[:2]) * 60 + int(c[3:5]) for c in contract['session_closes_et']])
    regular = (minute >= 570) & (minute < ends[ix])
    valid = (r['flag'] == 0) & np.isfinite(r['values']).all(axis=1)
    def counts(mask):
        return np.bincount(ix[mask], minlength=n).astype('i8')
    stats = {'observed': counts(np.ones(len(r), dtype=bool)), 'valid': counts(valid),
        'extended': counts(~regular), 'invalid': counts((r['flag'] & source.INVALID) != 0),
        'conflicting': counts((r['flag'] & source.CONFLICT) != 0),
        'off_calendar': int(len(records) - len(r))}
    first = np.full(n, 570, dtype='i8'); last = ends.copy()
    np.minimum.at(first, ix, minute); np.maximum.at(last, ix, minute + 1)
    stats.update(first=first, last=last)
    features = np.full((n, 5), np.nan)
    rr, ii = r[regular], ix[regular]
    if len(rr):
        days, offsets, cnt = np.unique(ii, return_index=True, return_counts=True)
        valid_count = counts(regular & valid)
        complete = (cnt == ends[days] - 570) & (valid_count[days] == cnt)
        x = rr['values']
        values = np.column_stack((x[offsets, 0], np.maximum.reduceat(x[:, 1], offsets),
            np.minimum.reduceat(x[:, 2], offsets), x[offsets + cnt - 1, 3],
            np.add.reduceat(x[:, 4], offsets)))
        features[days[complete]] = values[complete]
    return stats, features


def partition(contract, symbol, cache, *, reuse=True, predecessor=None):
    metadata = cache / (symbol + '.json')
    if metadata.exists():
        meta = json.loads(metadata.read_text())
        if meta['contract_id'] != contract['contract_id'] or sha(cache / (symbol + '.bin')) != meta['cache_sha256']:
            raise ValueError('prepared partition identity/hash changed: ' + symbol)
        for item in (f for f in contract['files'] if f['symbol'] == symbol):
            if source.file_stat(item['path']) != {k: item[k] for k in source.file_stat(item['path'])}:
                raise ValueError('raw source changed since discovery: ' + item['path'])
    else:
        meta = reuse_partition(contract, symbol, cache, predecessor) if reuse else None
        if meta is None:
            meta = source.prepare_symbol(contract, symbol, cache)
    summary = cache / (symbol + '.summary.npz')
    if not summary.exists():
        raw = np.memmap(cache / (symbol + '.bin'), dtype=source.RECORD, mode='r') if meta['rows'] else np.empty(0, source.RECORD)
        stats, features = summarize(raw, contract)
        save_arrays(summary, **stats, features=features)
        del raw
    elif not meta.get('summary_sha256'):
        # Recover an interrupted summary write by recomputing it from the
        # hash-checked partition, never by adopting unknown summary contents.
        raw = np.memmap(cache / (symbol + '.bin'), dtype=source.RECORD, mode='r') if meta['rows'] else np.empty(0, source.RECORD)
        stats, features = summarize(raw, contract)
        with np.load(summary, allow_pickle=False) as retained:
            for key, value in {**stats, 'features': features}.items():
                if not np.array_equal(retained[key], value, equal_nan=True):
                    raise ValueError('orphaned summary does not match source: ' + symbol)
    if meta.get('summary_sha256') and meta['summary_sha256'] != sha(summary):
        raise ValueError('source summary changed: ' + symbol)
    meta['summary_sha256'] = sha(summary)
    atomic_json(metadata, meta, replace=True)
    return meta


def prepare(contract, cache_base, journal=print, *, reuse=True, predecessor=None,
            workers=DEFAULT_SOURCE_WORKERS):
    if not isinstance(workers, int) or isinstance(workers, bool) or workers < 1:
        raise ValueError('source-workers must be a positive integer')
    source.validate_contract(contract)
    cache = Path(cache_base) / contract['contract_id']
    with lock(cache):
        atomic_json(cache / 'SOURCE_CONTRACT.json', contract, replace=True)
        started = time.monotonic(); completed, failures, consumed = [], [], 0
        sizes = {s: sum(f['bytes'] for f in contract['files'] if f['symbol'] == s) for s in contract['symbols']}
        total = sum(sizes.values())
        # A bounded parser pool limits RAM and drive pressure. Independent
        # completed partitions have disjoint output paths; only this owner writes
        # the shared checkpoint. An interrupted preparation is resumable.
        journal({'state': 'STARTING_SOURCE_PREPARATION', 'source_workers': workers,
                 'completed_symbols': 0, 'total_symbols': len(contract['symbols'])})
        with ThreadPoolExecutor(max_workers=workers) as pool:
            tasks = {pool.submit(partition, contract, s, cache, reuse=reuse, predecessor=predecessor): s for s in contract['symbols']}
            for task in as_completed(tasks):
                symbol = tasks[task]
                try:
                    task.result(); completed.append(symbol); consumed += sizes[symbol]
                except Exception as error:
                    failures.append({'symbol': symbol, 'type': type(error).__name__, 'error': str(error)})
                elapsed = time.monotonic() - started
                state = {'contract_id': contract['contract_id'], 'completed': sorted(completed),
                    'source_workers': workers,
                    'failures': failures, 'status': 'RUNNING', 'processed_source_bytes': consumed,
                    'total_source_bytes': total, 'elapsed_seconds': elapsed,
                    'estimated_remaining_seconds': elapsed * (total - consumed) / consumed if consumed else None}
                atomic_json(cache / 'PREPARE.json', state, replace=True)
                journal({'state': 'PREPARING_SOURCE', 'symbol': symbol,
                    'source_workers': workers,
                    'completed_symbols': len(completed), 'total_symbols': len(contract['symbols']),
                    'failed_symbols': len(failures), 'processed_source_bytes': consumed,
                    'total_source_bytes': total, 'estimated_remaining_seconds': state['estimated_remaining_seconds']})
        state['status'] = 'SOURCE_READ_FAILED' if failures else 'ALL_SOURCE_FILES_CONSUMED'
        atomic_json(cache / 'PREPARE.json', state, replace=True)
        if failures:
            raise ValueError('source preparation failed; inspect ' + str(cache / 'PREPARE.json'))
    return cache


class Book:
    def __init__(self, contract, cache, *, verify=True):
        self.contract = source.validate_contract(contract)
        self.cache = Path(cache)
        self.symbols, self.days = contract['symbols'], contract['days']
        evaluated = set(source.evaluation_symbols(contract))
        self.meta = []
        n = len(self.days)
        self.stats = {k: np.zeros(n, dtype='i8') for k in ('observed', 'valid', 'extended', 'invalid', 'conflicting')}
        self.first = np.full(n, 570, dtype='i8')
        self.last = np.asarray([int(c[:2]) * 60 + int(c[3:5]) for c in contract['session_closes_et']])
        self.features = np.full((n, len(self.symbols), 5), np.nan)
        self.off_calendar = 0
        self.summary_bindings = {}
        for j, symbol in enumerate(self.symbols):
            m = json.loads((self.cache / (symbol + '.json')).read_text())
            binary = self.cache / (symbol + '.bin')
            if (m['contract_id'] != contract['contract_id'] or binary.stat().st_size != m['rows'] * source.RECORD.itemsize
                    or (verify and sha(binary) != m['cache_sha256'])):
                raise ValueError('source cache identity/bytes changed: ' + symbol)
            self.meta.append(m)
            p = self.cache / (symbol + '.summary.npz')
            if sha(p) != m['summary_sha256']:
                raise ValueError('derived source summary changed: ' + symbol)
            with np.load(p, allow_pickle=False) as s:
                for k in self.stats:
                    if symbol in evaluated:
                        self.stats[k] += s[k]
                if symbol in evaluated:
                    self.first = np.minimum(self.first, s['first']); self.last = np.maximum(self.last, s['last'])
                    self.off_calendar += int(s['off_calendar'])
                self.features[:, j] = s['features']
            self.summary_bindings[symbol] = sha(p)

    def rows(self, column, day):
        metadata = self.meta[column]
        offset, count = metadata['days'].get(day, (0, 0))
        with (self.cache / (self.symbols[column] + '.bin')).open('rb') as handle:
            handle.seek(offset * source.RECORD.itemsize)
            rows = np.fromfile(handle, dtype=source.RECORD, count=count)
        if len(rows) != count:
            raise ValueError('source partition ended during signal read')
        return rows

    def daily_panel(self):
        return Panel(tuple(self.days), tuple(self.symbols), self.features, tuple(self.contract['session_closes_et']))

    def day(self, index, symbols):
        prefetch_partition_metadata(self, symbols)
        day = self.days[index]
        base = np.datetime64(day, 'm').astype('i8')
        first, last = int(self.first[index]), int(self.last[index])
        values = np.full((last - first, len(symbols), 5), np.nan)
        observations = np.zeros((last - first, len(symbols)), dtype='u4')
        flags = np.zeros_like(observations, dtype='u1')
        for j, symbol in enumerate(symbols):
            rows = window_rows(self, index, self.symbols.index(symbol))
            if not len(rows):
                continue
            idx = rows['minute'] - base - first
            values[idx, j] = rows['values']; observations[idx, j] = rows['copies']; flags[idx, j] = rows['flag']
        close = self.contract['session_closes_et'][index]
        end = int(close[:2]) * 60 + int(close[3:5])
        minute = np.arange(first, last)
        expected = np.broadcast_to(((minute >= 570) & (minute < end))[:, None], flags.shape).copy()
        expected |= observations != 0
        return {'day': day, 'clock_et': (base + minute).astype('datetime64[m]'), 'values': values,
            'flags': flags, 'observations': observations, 'expected': expected,
            'open_index': 570 - first, 'close_index': end - 1 - first}

    def consumption(self):
        regular = sum(int(c[:2]) * 60 + int(c[3:5]) - 570 for c in self.contract['session_closes_et'])
        observed, expected = int(self.stats['valid'].sum()), regular * len(source.evaluation_symbols(self.contract)) + int(self.stats['extended'].sum())
        return {'expected': expected, 'observed_expected': observed,
            **({'selection': self.contract['selection']} if self.contract.get('selection') else {}),
            'observed_coordinates': int(self.stats['observed'].sum()), 'invalid': int(self.stats['invalid'].sum()),
            'conflicting': int(self.stats['conflicting'].sum()), 'off_calendar_coordinates': self.off_calendar,
            'full_source_consumed': True, 'price_floor_qualification': 'NOT_ESTABLISHED',
            'partitions': {m['symbol']: {'cache_sha256': m['cache_sha256'],
                'raw_files': m['raw_files'], 'summary_sha256': self.summary_bindings[m['symbol']]} for m in self.meta},
            'method': 'All source bytes parsed/hash-bound; every calendar record used in full-grid '
                'coverage, feature and opportunity aggregates. Statically zero holdings outside '
                'each adapter eligibility have analytically zero cash/return contribution.'}
