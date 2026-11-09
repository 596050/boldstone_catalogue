"""Point-in-time feature streams, separate from the common trading population.

Closest prior: the daily-minute shared-source manifest. This extension routes
additional, mixed-cadence inputs by model identity and exposes only published
observations. It never writes or fills a source. Plugins remain trusted code.
"""
from bisect import bisect_right
from copy import deepcopy
import csv
from datetime import datetime, timezone
import json
import math
from pathlib import Path

from research.testing_stages.common import digest, sha

SCHEMA = 'marketmaker.model_inputs.v1'


def clock(value):
    stamp = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    if stamp.tzinfo is None:
        raise ValueError('input availability clocks require an explicit timezone')
    return stamp.astimezone(timezone.utc)


class Inputs:
    def __init__(self, path=None):
        self.streams, self.bindings, self.summary = {}, {}, {}
        if path is None:
            self.identity = digest({})
            return
        path = Path(path).resolve()
        value = json.loads(path.read_text())
        if set(value) != {'schema', 'streams'} or value['schema'] != SCHEMA or not isinstance(value['streams'], list):
            raise ValueError('model input manifest needs schema and streams')
        self.bindings[str(path)] = sha(path)
        for item in value['streams']:
            required = {'name', 'path', 'format', 'cadence', 'symbols'}
            if not required <= set(item) or set(item) - required - {'max_observations'}:
                raise ValueError('feature stream needs name/path/format/cadence/symbols; optional max_observations')
            name = item['name']
            if not isinstance(name, str) or not name or name in self.streams:
                raise ValueError('feature stream names must be unique')
            if not isinstance(item['cadence'], str) or not item['cadence']:
                raise ValueError('feature cadence must be explicit')
            symbols = item['symbols']
            if not isinstance(symbols, list) or not symbols or len(symbols) != len(set(symbols)):
                raise ValueError('feature symbols must be an explicit unique list')
            limit = item.get('max_observations')
            if limit is not None and (type(limit) is not int or limit < 1):
                raise ValueError('max_observations must be positive or omitted')
            source = (path.parent / item['path']).resolve()
            if item['format'] == 'jsonl':
                rows = [json.loads(line) for line in source.read_text().splitlines() if line.strip()]
            elif item['format'] == 'csv':
                with source.open(newline='') as handle:
                    rows = list(csv.DictReader(handle))
            else:
                raise ValueError('feature format must be csv or jsonl')
            seen, parsed = set(), []
            for row in rows:
                if set(row) != {'symbol', 'observed_at', 'available_at', 'value'}:
                    raise ValueError('feature row needs symbol, observed_at, available_at and value')
                observed, available = clock(row['observed_at']), clock(row['available_at'])
                if row['symbol'] not in symbols or available < observed:
                    raise ValueError('undeclared feature symbol or availability before observation/bar completion')
                identity = (row['symbol'], observed, available)
                if identity in seen:
                    raise ValueError('duplicate or conflicting feature revision at the same availability clock')
                seen.add(identity)
                raw = row['value']
                number = None if raw is None or raw == '' else float(raw)
                if number is not None and not math.isfinite(number):
                    raise ValueError('feature value must be finite or explicitly missing')
                parsed.append((available, {**row, 'value': number}))
            parsed.sort(key=lambda r: (r[0], r[1]['symbol'], r[1]['observed_at']))
            self.streams[name] = (tuple(p[0] for p in parsed), tuple(p[1] for p in parsed), limit)
            self.bindings[str(source)] = sha(source)
            self.summary[name] = {**item, 'path': str(source), 'sha256': sha(source), 'rows': len(rows),
                'missing_values': sum(r['value'] is None for _, r in parsed),
                'first_available': parsed[0][0].isoformat() if parsed else None,
                'last_available': parsed[-1][0].isoformat() if parsed else None}
        self.identity = digest({'streams': self.summary, 'bindings': self.bindings})

    def at(self, at):
        at = clock(at)
        result = {}
        for name, (clocks, rows, limit) in self.streams.items():
            stop = bisect_right(clocks, at)
            result[name] = tuple(deepcopy(rows[max(0, stop - limit) if limit else 0:stop]))
        return result

    def assert_unchanged(self):
        for path, expected in self.bindings.items():
            if sha(path) != expected:
                raise ValueError('feature source changed: ' + path)
