"""Bounded, concurrent IQFeed acquisition for the original 96-stock hybrids.

Old sources and model evidence remain immutable. Daily files are refreshed over
their entire history (split-adjusted data); minute updates explicitly overlap the
old tail. The raw response vintage, missing observations and OHLC defects are kept.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import csv
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT))
from utils.external_storage.hetzner import storage_box as sb
from research.testing_stages.stage_01_data.iqfeed_refresh import Lookup, HEADERS, row_day, consistent_ohlc
from research.testing_stages.stage_01_data.source import schedule

STAGING = ROOT / 'utils/offload_network/.source-state/frozen96_iqfeed_refresh_20260922_v1'


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(4 * 1024**2), b''):
            h.update(b)
    return h.hexdigest()


def capacity():
    if shutil.disk_usage(STAGING).free < 3 * 1024**3:
        raise RuntimeError('Local free-space reserve below 3 GiB; acquisition stopped')


def acquire(job, lookup, end):
    symbol, cadence, kind, begin = job
    directory = STAGING / kind
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / (symbol + ('.txt' if cadence == 'daily' else '.csv'))
    receipt = directory / (symbol + '.receipt.json')
    if receipt.exists():
        prior = json.loads(receipt.read_text())
        if prior.get('requested_end') == end and prior.get('status') in ('UPDATED', 'NO_PROVIDER_DATA', 'PROVIDER_TAIL_GAP'):
            if sha(path) == prior['sha256']:
                return prior
            raise RuntimeError('Retained refresh receipt hash mismatch')
    record = dict(symbol=symbol, cadence=cadence, kind=kind, requested_begin=begin, requested_end=end,
                  path=str(path), source='IQFeed protocol 6.2', bar_label='begin' if cadence == 'minute' else 'daily',
                  timezone='America/New_York', requested_at_utc=sb.now(), status='REQUESTING')
    entry = dict(symbol=symbol, cadence=cadence)
    for attempt in range(1, 3):
        temp = path.with_suffix(path.suffix + '.partial')
        count = bad = 0; first = last = previous = None
        try:
            capacity()
            with temp.open('w') as f:
                f.write(HEADERS[cadence] + '\n')
                for line in lookup.rows(entry, begin, end):
                    day = row_day(line, cadence)
                    key = day if cadence == 'daily' else line.split(',', 1)[0]
                    if not begin <= day <= end or previous is not None and key <= previous:
                        raise ValueError('Out-of-window or non-increasing IQFeed observation')
                    f.write(line + '\n'); previous = key
                    count += 1; bad += not consistent_ohlc(line, cadence)
                    first = first or day; last = day
                    if count % 4096 == 0:
                        capacity()
                        if f.tell() > 256 * 1024**2:
                            raise RuntimeError('Per-request staging limit exceeded')
                f.flush(); os.fsync(f.fileno())
            os.replace(temp, path)
            record.update(status=('NO_PROVIDER_DATA' if count == 0 else 'UPDATED' if last == end else 'PROVIDER_TAIL_GAP'),
                          received_rows=count, inconsistent_ohlc_rows=bad, first=first, last=last,
                          sha256=sha(path), bytes=path.stat().st_size, attempts=attempt,
                          observed_at_utc=sb.now(), raw_response_preserved=True)
            break
        except Exception as exc:
            record.update(status='ERROR', error=repr(exc), attempts=attempt, observed_at_utc=sb.now())
            if attempt < 2:
                time.sleep(2)
        finally:
            temp.unlink(missing_ok=True)
    sb.write_json(receipt, record)
    return record


def main():
    STAGING.mkdir(parents=True, exist_ok=True)
    capacity()
    plan_path = HERE / 'REFRESH_PLAN.json'
    if plan_path.exists():
        plan = json.loads(plan_path.read_text())
    else:
        frozen_path = ROOT / 'research/candidates/directional_forecasting/full_history_shadow_vote_hybrid_20260922_v2/run_01/FREEZE.json'
        frozen = json.loads(frozen_path.read_text())
        symbols = sorted(Path(x['path']).stem for x in frozen['daily_raw'])
        assert len(symbols) == len(set(symbols)) == 96
        _, days, _ = schedule()
        plan = dict(created_at=sb.now(), end=days[-1], symbols=symbols, workers=4,
                    daily_begin='1990-01-01', minute_begin='2026-09-11', staging=str(STAGING),
                    original_freeze_sha256=sha(frozen_path),
                    strategy_parameters_changed=False, source_deletions=0, overwrite_sources=False,
                    staging_policy='Bounded acquisition buffer with 3 GiB free-space reserve; remote archive required before completion',
                    halt_policy='Existing IQFeed data-only start script; global broker halt retained')
        sb.write_json(plan_path, plan)
    lookup = Lookup(timeout=45)
    jobs = []
    for symbol in plan['symbols']:
        jobs.extend([(symbol,'daily','daily',plan['daily_begin']), (symbol,'minute','minute_tail',plan['minute_begin'])])
    state = dict(started_at=sb.now(), status='RUNNING', plan=plan, total_requests=len(jobs)+1, entries=[])
    sb.write_json(HERE / 'REFRESH.json', state)
    with ThreadPoolExecutor(max_workers=4) as pool:
        work = [pool.submit(acquire, j, lookup, plan['end']) for j in jobs]
        # The exact historical execution gap is an independent provider request.
        work.append(pool.submit(acquire, ('SLB','minute','slb_2008_gap','2008-11-28'), lookup, '2008-12-10'))
        for future in as_completed(work):
            row = future.result(); state['entries'].append(row)
            state.update(updated_at=sb.now(), completed_requests=len(state['entries']))
            sb.write_json(HERE / 'REFRESH.json', state)
            print(json.dumps({k:row.get(k) for k in ('symbol','kind','status','received_rows','last','error')}),flush=True)
    errors = [x for x in state['entries'] if x['status'] == 'ERROR']
    tails = [x for x in state['entries'] if x['kind'] != 'slb_2008_gap' and x['status'] != 'UPDATED']
    state.update(status='COMPLETE' if not errors and not tails else 'PARTIAL', finished_at=sb.now(),
                 error_count=len(errors), incomplete_current_sources=len(tails),
                 files=sum(x.get('bytes',0)>0 for x in state['entries']), bytes=sum(x.get('bytes',0) for x in state['entries']),
                 statistical_confirmation=False)
    sb.write_json(HERE / 'REFRESH.json', state)
    print(json.dumps({k:v for k,v in state.items() if k not in ('entries','plan')},indent=2))


if __name__ == '__main__':
    main()
