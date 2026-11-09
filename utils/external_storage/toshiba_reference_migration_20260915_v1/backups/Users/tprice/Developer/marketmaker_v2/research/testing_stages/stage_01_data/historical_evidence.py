"""Validate supplied historical availability/identity metadata against price axes.

File hashes certify retained bytes, not when a vendor published them. Even a
complete supplied clock ledger is labelled declared evidence, not independent
proof that nobody had future information. Missing evidence never changes prices.
"""
import json
from pathlib import Path
from datetime import datetime
import numpy as np

from research.testing_stages.common import sha

SCHEMA = 'marketmaker.historical_source_evidence.v1'


def timestamp(value):
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if result.tzinfo is None:
        raise ValueError('historical availability timestamps need explicit timezones')
    return result


def reference(value, base, bindings):
    if not isinstance(value, dict) or set(value) != {'path', 'sha256'}:
        raise ValueError('historical evidence reference needs path and sha256')
    path = Path(value['path'])
    path = (base / path).resolve() if not path.is_absolute() else path.resolve()
    if sha(path) != value['sha256']:
        raise ValueError('historical evidence bytes changed: ' + str(path))
    bindings[str(path)] = value['sha256']
    return path


def inspect(path, jobs, *, require=False):
    bindings = {}
    domains = {j['description'].get('measurement_contract', {}).get('domain') for j in jobs}
    if path is None and not require and domains == {'prediction'}:
        return {'status': 'NOT_APPLICABLE', 'sources': [],
                'boundary': 'Trading price vintage and security membership checks do not apply to this prediction-domain contract.'}, bindings
    if path is None:
        if require:
            raise ValueError('point-in-time evidence required but no --source-evidence supplied')
        return {'status': 'HISTORICAL_AVAILABILITY_NOT_ESTABLISHED', 'sources': [],
                'universe': 'Declared trading roster; historical membership is not inferred.',
                'boundary': 'Causal prefix checks do not establish historical source vintages or publication times.'}, bindings
    path = Path(path).resolve(); bindings[str(path)] = sha(path)
    spec = json.loads(path.read_text())
    if not isinstance(spec, dict) or spec.get('schema') != SCHEMA or set(spec) != {'schema', 'sources'} or not isinstance(spec['sources'], list) or not spec['sources']:
        raise ValueError('invalid historical source evidence manifest')
    declared = {p: h for j in jobs for p, h in j['description']['bindings'].items()}
    rows = []; seen = set()
    for source in spec['sources']:
        if set(source) - {'prices', 'vintage', 'observations', 'security_history', 'corporate_actions'} or not {'prices', 'vintage'} <= set(source):
            raise ValueError('invalid historical source evidence fields')
        p = reference(source['prices'], path.parent, bindings)
        if str(p) in seen or declared.get(str(p)) != bindings[str(p)]:
            raise ValueError('historical evidence must name a unique bound model/source input')
        seen.add(str(p))
        if source['vintage'] not in ('current_vintage', 'point_in_time', 'unknown'):
            raise ValueError('historical vintage must be current_vintage, point_in_time or unknown')
        row = {'source': str(p), 'vintage': source['vintage'], 'availability': 'NOT_ESTABLISHED',
               'security_identity': 'NOT_ESTABLISHED', 'membership': 'NOT_ESTABLISHED',
               'corporate_actions': source.get('corporate_actions', 'NOT_ESTABLISHED')}
        rows.append(row)
        if 'observations' not in source:
            if source['vintage'] == 'point_in_time':
                raise ValueError('point-in-time claim needs complete observation availability records')
            continue
        if p.suffix != '.npz':
            raise ValueError('historical clock binding currently accepts explicit NPZ price panels')
        with np.load(p, allow_pickle=False) as data:
            days, symbols = tuple(map(str, data['days'])), tuple(map(str, data['symbols']))
            prices = data['close'] if 'close' in data else data['values'][:, :, 3]
        if prices.shape != (len(days), len(symbols)) or len(set(days)) != len(days) or len(set(symbols)) != len(symbols):
            raise ValueError('historical price axes must be unique and aligned')
        dindex = {s: i for i, s in enumerate(days)}; sindex = {s: i for i, s in enumerate(symbols)}
        seen_coordinates = set(); security_ids = {}; observations = reference(source['observations'], path.parent, bindings)
        for line in observations.read_text().splitlines():
            r = json.loads(line)
            if set(r) != {'day', 'symbol', 'price', 'event_at', 'available_at', 'used_at', 'security_id', 'vintage_at'}:
                raise ValueError('observation evidence needs exact price, security, event, vintage, availability and usage clocks')
            coordinate = (dindex[r['day']], sindex[r['symbol']])
            if coordinate in seen_coordinates or not np.isfinite(prices[coordinate]) or prices[coordinate] <= 0 or r['price'] != float(prices[coordinate]):
                raise ValueError('historical observation is duplicated, missing or differs from bound raw price')
            seen_coordinates.add(coordinate)
            event, available, used, vintage = [timestamp(r[k]) for k in ('event_at', 'available_at', 'used_at', 'vintage_at')]
            if event.date().isoformat() != r['day'] or used.date().isoformat() != r['day'] or not event <= available <= used or not event <= vintage <= used:
                raise ValueError('historical observation was not available at its declared usage clock')
            if not isinstance(r['security_id'], str) or not r['security_id']:
                raise ValueError('historical observations need a stable security identity')
            security_ids[coordinate] = r['security_id']
        observed = int((np.isfinite(prices) & (prices > 0)).sum())
        if len(seen_coordinates) != observed:
            raise ValueError('historical clock evidence must cover every observed source coordinate')
        row.update(availability='DECLARED_CLOCKS_VALIDATED', observed_coordinates=observed,
                   missing_coordinates=int(prices.size-observed), start=days[0], end=days[-1])
        if 'security_history' in source:
            h = reference(source['security_history'], path.parent, bindings)
            records = json.loads(h.read_text())
            if not isinstance(records, list):
                raise ValueError('security history must be a list of dated identities and memberships')
            by_symbol = {}
            for r in records:
                if set(r) != {'symbol', 'security_id', 'start', 'end', 'member', 'available_at'} or type(r['member']) is not bool:
                    raise ValueError('security history needs dated identity, membership and publication')
                if r['symbol'] not in sindex or r['start'] > r['end'] or timestamp(r['available_at']).date().isoformat() > r['start']:
                    raise ValueError('security membership is unknown or published after its effective start')
                by_symbol.setdefault(r['symbol'], []).append(r)
            nonmembers = 0
            for i, j in seen_coordinates:
                matches = [r for r in by_symbol.get(symbols[j], []) if r['start'] <= days[i] <= r['end']]
                if len(matches) != 1 or matches[0]['security_id'] != security_ids[(i, j)]:
                    raise ValueError('security history is incomplete, overlaps or changes identity without evidence')
                nonmembers += not matches[0]['member']
            row.update(security_identity='DECLARED_HISTORY_VALIDATED', membership='DECLARED_HISTORY_VALIDATED',
                       observed_nonmember_coordinates=nonmembers)
        if source['vintage'] == 'point_in_time' and row['security_identity'] != 'DECLARED_HISTORY_VALIDATED':
            raise ValueError('point-in-time claim needs complete security identity history')
    qualified = all(r['vintage'] == 'point_in_time' and r['availability'] == 'DECLARED_CLOCKS_VALIDATED' and
                    r['security_identity'] == 'DECLARED_HISTORY_VALIDATED' for r in rows)
    # Strict source coverage includes both signal and extra feature panels.
    required_panels = {str(Path(v['path']).resolve()) for j in jobs for k, v in
        j['description'].get('model_scope', {}).items() if k in ('signal_panel', 'feature_panel') and isinstance(v, dict)}
    if require and (not qualified or not required_panels or not required_panels <= seen):
        raise ValueError('required historical evidence does not cover every signal/feature panel with validated point-in-time declarations')
    return {'status': ('DECLARED_PIT_EVIDENCE_VALIDATED' if required_panels and required_panels <= seen
                       else 'PARTIAL_DECLARED_EVIDENCE') if qualified else 'HISTORICAL_LIMITATIONS_RETAINED',
            'sources': rows, 'uncovered_required_panels': sorted(required_panels-seen),
            'boundary': 'Supplied provenance is checked against retained prices and clocks; independent vendor publication proof and undisclosed access are not certified. No source or roster was changed.'}, bindings
