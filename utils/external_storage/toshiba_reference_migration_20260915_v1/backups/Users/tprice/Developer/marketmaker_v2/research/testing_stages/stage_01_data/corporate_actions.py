"""Acquire and replay provider event bytes; never infer no events from no reply.

This is current-vintage economic reference data, not historical publication
evidence. Full price axes remain explicit. Only successfully decoded requested
identities have event coverage; holding an uncovered security is prohibited.
Yahoo dividend amounts use the latest split basis. Convert them back to the
share basis on the ex-date, retaining provider precision (do not round to cents).
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import sys
import time
from urllib.parse import urlencode, quote
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

sys.dont_write_bytecode = True
ROOT = next(p for p in Path(__file__).resolve().parents if p.name == 'testing_stages').parents[1]
sys.path.insert(0, str(ROOT))
from research.testing_stages.common import atomic_json, lock, sha
from research.testing_stages.models import Adapter

HERE = next(p for p in Path(__file__).resolve().parents if p.name == 'testing_stages')
SCHEMA = 'marketmaker.stage1.corporate_actions.v2'
ET = ZoneInfo('America/New_York')
# A ticker alone does not bind a security through a reuse. Do not silently map
# current GOLD (Gold.com) to historical GOLD (Barrick) or splice these issuers.
UNRESOLVED_IDENTITIES = {'GOLD': 'Historical Barrick/current GOLD ticker reuse; PIT identity unresolved.'}


def stamp():
    return datetime.now(timezone.utc).isoformat()


def day_of(event):
    return datetime.fromtimestamp(int(event['date']), ET).date().isoformat()


def decode(raw, symbol, start, end):
    payload = json.loads(raw, parse_float=Decimal)
    chart = payload['chart']
    if chart.get('error') or not chart.get('result') or len(chart['result']) != 1:
        raise ValueError('provider error or missing/ambiguous result: ' + str(chart.get('error')))
    result = chart['result'][0]
    meta = result['meta']
    expected = symbol.replace('.', '-')
    if (meta['symbol'] != expected or meta['currency'] != 'USD'
            or meta['instrumentType'] != 'EQUITY' or meta.get('exchangeTimezoneName') != 'America/New_York'):
        raise ValueError('provider symbol/currency/instrument/timezone identity does not match request')
    if symbol in UNRESOLVED_IDENTITIES:
        raise ValueError(UNRESOLVED_IDENTITIES[symbol])
    groups = result.get('events', {})
    if set(groups) - {'dividends', 'splits'}:
        raise ValueError('unsupported event category: ' + str(set(groups) - {'dividends', 'splits'}))
    splits = []
    for event in groups.get('splits', {}).values():
        ratio = Decimal(str(event['numerator'])) / Decimal(str(event['denominator']))
        if not ratio.is_finite() or ratio <= 0:
            raise ValueError('invalid split ratio')
        splits.append((day_of(event), ratio))
    events = [{'day': day, 'symbol': symbol, 'kind': 'split', 'ratio': float(ratio)}
              for day, ratio in splits if start <= day <= end]
    for event in groups.get('dividends', {}).values():
        day = day_of(event)
        amount = Decimal(str(event['amount']))
        if not amount.is_finite() or amount <= 0:
            raise ValueError('invalid dividend amount')
        factor = Decimal(1)
        for split_day, ratio in splits:
            if split_day > day:
                factor *= ratio
        if start <= day <= end:
            events.append({'day': day, 'symbol': symbol, 'kind': 'dividend',
                'cash_per_share': float(amount * factor), 'provider_adjusted_amount': str(amount),
                'subsequent_split_multiplier': str(factor),
                'amount_precision': 'PROVIDER_DECIMAL_PRECISION_RETAINED_NOT_ISSUER_EXACT'})
    events.sort(key=lambda e: (e['day'], e['symbol'], 0 if e['kind'] == 'split' else 1))
    if len({(e['day'], e['symbol'], e['kind']) for e in events}) != len(events):
        raise ValueError('ambiguous duplicate events')
    return events, {k: meta.get(k) for k in ('symbol', 'shortName', 'longName', 'currency',
        'instrumentType', 'exchangeName', 'exchangeTimezoneName', 'firstTradeDate', 'regularMarketTime')}


def fetch(symbol, start, end, directory):
    # Request through receipt day, even when the scored cutoff is earlier, so
    # split adjustment after the scored cutoff is reversed too.
    period1 = int(datetime.fromisoformat(start).replace(tzinfo=timezone.utc).timestamp())
    period2 = int((datetime.now(timezone.utc) + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0).timestamp())
    params = {'period1': period1, 'period2': period2, 'interval': '1mo',
              'events': 'div,splits', 'includeAdjustedClose': 'true'}
    url = 'https://query2.finance.yahoo.com/v8/finance/chart/' + quote(symbol.replace('.', '-'), safe='') + '?' + urlencode(params)
    receipt_path = directory / (symbol + '.receipt.json')
    if receipt_path.exists():
        receipt = json.loads(receipt_path.read_text())
        if receipt['start'] != start or receipt['end'] != end:
            raise ValueError('request window changed; use a new acquisition directory')
        if receipt.get('raw_path') and sha(receipt['raw_path']) != receipt['raw_sha256']:
            raise ValueError('retained provider bytes changed')
        return receipt
    receipt = {'symbol': symbol, 'start': start, 'end': end, 'request_url': url,
               'requested_at_utc': stamp(), 'attempts': [], 'status': 'UNAVAILABLE'}
    for attempt in range(3):
        try:
            with urlopen(Request(url, headers={'User-Agent': 'Mozilla/5.0'}), timeout=25) as response:
                raw = response.read(16 * 1024**2 + 1)
                if len(raw) > 16 * 1024**2:
                    raise ValueError('provider response exceeds size bound')
                receipt['http_status'] = response.status
            raw_path = directory / (symbol + '.json')
            with raw_path.open('xb') as stream:
                stream.write(raw)
            receipt.update(raw_path=str(raw_path), raw_sha256=hashlib.sha256(raw).hexdigest(),
                           bytes=len(raw), received_at_utc=stamp())
            try:
                events, identity = decode(raw, symbol, start, end)
                receipt.update(status='RESPONSE_DECODED', event_count=len(events), provider_identity=identity)
            except (ValueError, KeyError, TypeError) as error:
                receipt.update(status='RESPONSE_UNRESOLVED', error=str(error))
            break
        except Exception as error:
            receipt['attempts'].append({'at_utc': stamp(), 'error': str(error), 'type': type(error).__name__})
            if attempt < 2:
                time.sleep(1 + attempt)
    # The external drive is exFAT (no hardlinks); caller holds one writer lock.
    atomic_json(receipt_path, receipt, replace=True)
    return receipt


def build(contract, receipts):
    coverage, events, sources, failures = {}, [], [], {}
    for receipt in sorted(receipts, key=lambda r: r['symbol']):
        symbol = receipt['symbol']
        if receipt['status'] != 'RESPONSE_DECODED':
            failures[symbol] = receipt.get('error', receipt['attempts'])
            continue
        p = Path(receipt['raw_path'])
        if sha(p) != receipt['raw_sha256']:
            raise ValueError('corporate-action raw hash mismatch: ' + symbol)
        parsed, identity = decode(p.read_bytes(), symbol, contract['start'], contract['end'])
        if any(e['day'] not in contract['days'] for e in parsed):
            failures[symbol] = 'OFF_EXCHANGE_CALENDAR_EVENT: explicit calendar/event interpretation required'
            continue
        events += parsed
        coverage[symbol] = {'status': 'PROVIDER_FULL_WINDOW_RESPONSE', 'start': contract['start'],
            'end': contract['end'], 'request_url': receipt['request_url'],
            'received_at_utc': receipt['received_at_utc'], 'provider_identity': identity,
            'raw_sha256': receipt['raw_sha256'], 'completeness': 'PROVIDER_RESPONSE_NOT_ISSUER_CERTIFIED',
            'historical_PIT_availability': 'NOT_ESTABLISHED'}
        sources.append({'symbol': symbol, 'path': str(p), 'sha256': receipt['raw_sha256']})
    return {'schema': SCHEMA, 'source_contract_id': contract['contract_id'],
        **{k: contract[k] for k in ('start', 'end', 'symbols')}, 'currency': 'USD',
        'coverage': coverage, 'unresolved': failures, 'source_references': sources,
        'events': sorted(events, key=lambda e: (e['day'], e['symbol'], 0 if e['kind'] == 'split' else 1)),
        'scope': 'Complete shared price axis; economic events only for explicitly covered identities. '
            'Every held identity must be covered. Missing responses are not zero-event histories.',
        'dividend_basis': 'Latest-split-adjusted provider amounts reversed by all subsequent reported splits; '
            'provider precision retained. Current-vintage ex-date economic accrual, not publication-time features.',
        'limitations': ['Issuer/PIT identity and completeness NOT_ESTABLISHED',
            'Spinoffs, mergers and noncash distributions are not supplied by this event interface',
            'These references cannot certify full price consumption, native execution or prospective acceptance']}


def replay(ledger, contract):
    if (ledger.get('schema') != SCHEMA or ledger.get('source_contract_id') != contract['contract_id']
            or any(ledger.get(k) != contract[k] for k in ('start', 'end', 'symbols'))
            or ledger.get('currency') != 'USD'):
        raise ValueError('corporate-action schema/source/currency/axes mismatch')
    actual, covered = [], set()
    for ref in ledger['source_references']:
        symbol = ref['symbol']
        if symbol in covered or symbol not in contract['symbols'] or sha(ref['path']) != ref['sha256']:
            raise ValueError('duplicate/outside-axis/changed corporate-action evidence')
        parsed, identity = decode(Path(ref['path']).read_bytes(), symbol, contract['start'], contract['end'])
        row = ledger['coverage'][symbol]
        if (row['raw_sha256'] != ref['sha256'] or row['provider_identity'] != identity
                or row['start'] != contract['start'] or row['end'] != contract['end']):
            raise ValueError('corporate-action coverage not reproduced from bound raw bytes')
        actual += parsed
        covered.add(symbol)
    actual.sort(key=lambda e: (e['day'], e['symbol'], 0 if e['kind'] == 'split' else 1))
    if (actual != ledger['events'] or covered != set(ledger['coverage'])
            or any(e['day'] not in contract['days'] for e in actual)):
        raise ValueError('derived events or coverage differ from independent raw replay')
    by_day = {}
    for e in actual:
        by_day.setdefault(e['day'], []).append(e)
    return {'events_by_day': by_day, 'covered_symbols': sorted(covered)}
