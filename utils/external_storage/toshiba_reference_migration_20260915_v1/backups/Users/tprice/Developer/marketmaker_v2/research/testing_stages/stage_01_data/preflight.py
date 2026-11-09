"""Resolve inputs using code and metadata, without opening raw minute prices.

Standard adapters must have import-safe modules. Constructors may import their
pure rule dependencies; they must not read prices, call brokers or run main().
Readiness is metadata evidence only. The stage replayer remains responsible for
complete source consumption, economic hashes, causal tests and accounting.
"""
from __future__ import annotations

import csv
from datetime import datetime, timezone
import math
from pathlib import Path
from zoneinfo import ZoneInfo

from research.testing_stages import source
from research.testing_stages.common import sha
from research.testing_stages.models import ALIASES
from research.testing_stages.catalog import SuiteAdapter, match, selected
from research.testing_stages.configuration import CLASSES, metadata, path, problem

CLOCKS = {
    'daily': ('after_completed_regular_session', 'next_regular_session_open'),
    'minute': ('after_completed_minute', 'next_calendar_minute_open'),
}


def canonical(value):
    if str(value) in ALIASES:
        return str(value)
    item = match(value)
    return item['alias'] if item else str(path(value).resolve())


def source_metadata(contract, cache):
    """Stat the full declared file set and read only the preparation checkpoint."""
    issues, changed, missing, present = [], [], [], set()
    for item in contract['files']:
        try:
            actual = source.file_stat(item['path'])
            if actual != {k: item[k] for k in actual}:
                changed.append(item['path'])
            else:
                present.add(item['symbol'])
        except OSError:
            missing.append(item['path'])
    if changed or missing:
        issues.append(problem('SOURCE_SNAPSHOT_UNAVAILABLE', f'{len(changed)} changed files; {len(missing)} missing files.'))
    if contract.get('discovery_errors') or contract.get('errors'):
        issues.append(problem('SOURCE_DISCOVERY_INCOMPLETE', contract.get('discovery_errors') or contract.get('errors')))
    checkpoint_path = Path(cache) / contract['contract_id'] / 'PREPARE.json'
    checkpoint = None
    checkpoint_error = None
    try:
        if checkpoint_path.exists():
            checkpoint = metadata(checkpoint_path)
            if (checkpoint['contract_id'] != contract['contract_id']
                    or not set(checkpoint['completed']) <= set(contract['symbols'])
                    or len(checkpoint['completed']) != len(set(checkpoint['completed']))):
                raise ValueError('checkpoint contract/symbol identity differs')
            if checkpoint.get('status') == 'ALL_SOURCE_FILES_CONSUMED' and (
                    set(checkpoint['completed']) != set(contract['symbols']) or checkpoint.get('failures')):
                raise ValueError('completed checkpoint does not contain the whole declared symbol grid')
    except (OSError, ValueError, KeyError) as error:
        checkpoint_error = str(error)
        checkpoint = None
    completed = set((checkpoint or {}).get('completed', []))
    missing_partitions = []
    # File presence is useful for readiness, but it is not hash or row validation.
    for symbol in sorted(completed):
        if not all((checkpoint_path.parent / (symbol + suffix)).is_file() for suffix in ('.json', '.bin', '.summary.npz')):
            missing_partitions.append(symbol)
    return {
        'contract_id': contract['contract_id'], 'start': contract['start'], 'end': contract['end'],
        'cutoff_utc': contract['cutoff_utc'], 'symbol_count': len(contract['symbols']),
        'session_count': len(contract['days']), 'file_count': len(contract['files']),
        'declared_bytes': sum(x['bytes'] for x in contract['files']),
        'symbols_without_current_bound_files': sorted(set(contract['symbols']) - present),
        'changed_files': changed, 'missing_files': missing,
        'checkpoint': {'path': str(checkpoint_path), 'reported_status': (checkpoint or {}).get('status', 'NOT_AVAILABLE'),
                       'completed_symbols': sorted(completed), 'failures': (checkpoint or {}).get('failures', []),
                       'missing_partition_files': missing_partitions, 'error': checkpoint_error},
        'coverage_rate': 'NOT_MEASURED', 'listing_and_PIT_exceptions': 'NOT_ESTABLISHED',
        'full_source_consumption_verified': False, 'raw_price_bytes_read_by_metadata_inspector': 0,
        'cache_bytes_verified': False, 'issues': issues,
    }


def standard_metadata(config, contract):
    econ = config['economics']
    result = {'corporate_actions': {'status': 'MISSING', 'split_input': 'MISSING', 'dividend_input': 'MISSING'},
              'fx': {'status': 'MISSING' if econ['currency'] == 'GBP' else 'NOT_REQUIRED'},
              'independent_completeness': 'NOT_ESTABLISHED'}
    if econ.get('corporate_actions'):
        p = path(econ['corporate_actions'])
        try:
            ledger = metadata(p)
            if (ledger.get('schema') != 'marketmaker.stage1.corporate_actions.v1'
                    or any(ledger.get(k) != contract[k] for k in ('start', 'end', 'symbols'))
                    or ledger.get('currency') != econ['currency'] or not ledger.get('source_references')
                    or not isinstance(ledger.get('events'), list)):
                raise ValueError('split/dividend ledger must bind the exact full source axes, currency and source references')
            refs = []
            for ref in ledger['source_references']:
                raw = Path(ref['path'])
                raw = raw if raw.is_absolute() else p.parent / raw
                if not raw.is_file() or len(ref.get('sha256', '')) != 64:
                    raise ValueError('corporate-action source reference is missing or invalid: ' + str(raw))
                refs.append({'path': str(raw.resolve()), 'expected_sha256': ref['sha256'], 'hash_verified': False})
            seen = set()
            days, symbols = set(contract['days']), set(contract['symbols'])
            for event in ledger['events']:
                kind = event['kind']
                key = event['day'], event['symbol'], kind
                if key in seen or kind not in ('split', 'dividend') or key[0] not in days or key[1] not in symbols:
                    raise ValueError('duplicate, unsupported or off-grid corporate action')
                seen.add(key)
                amount = float(event['ratio'] if kind == 'split' else event['cash_per_share'])
                if not math.isfinite(amount) or amount <= 0:
                    raise ValueError('corporate-action amount must be finite and positive')
            result['corporate_actions'] = {'status': 'STRUCTURE_READY_HASH_REPLAY_PENDING', 'path': str(p), 'sha256': sha(p),
                'split_input': 'LEDGER_DECLARED_COMPLETENESS_UNVERIFIED', 'dividend_input': 'LEDGER_DECLARED_COMPLETENESS_UNVERIFIED',
                'event_count': len(ledger['events']), 'source_references': refs}
        except (OSError, ValueError, KeyError, TypeError) as error:
            result['corporate_actions'] = {'status': 'INVALID', 'error': str(error), 'split_input': 'UNRESOLVED', 'dividend_input': 'UNRESOLVED'}
    if econ.get('fx'):
        p = path(econ['fx'])
        try:
            if econ['currency'] != 'GBP':
                raise ValueError('FX input only supported for USD-to-GBP evaluation')
            if p.stat().st_size > 32 * 1024**2:
                raise ValueError('FX metadata exceeds preflight read limit')
            with p.open(newline='') as f:
                reader = csv.DictReader(f)
                if set(reader.fieldnames or []) != {'date', 'usd_to_gbp', 'available_at_utc'}:
                    raise ValueError('FX requires date, usd_to_gbp, available_at_utc')
                rows = list(reader)
            if [r['date'] for r in rows] != contract['days']:
                raise ValueError('FX must cover exactly the ordered source sessions')
            for row in rows:
                rate = float(row['usd_to_gbp'])
                available = datetime.fromisoformat(row['available_at_utc'].replace('Z', '+00:00'))
                midnight = datetime.fromisoformat(row['date']).replace(tzinfo=ZoneInfo('America/New_York'))
                if not math.isfinite(rate) or rate <= 0 or available.tzinfo is None or available > midnight:
                    raise ValueError('FX rate must be positive and available by local session midnight')
            result['fx'] = {'status': 'STRUCTURE_READY_HASH_REPLAY_PENDING', 'path': str(p), 'sha256': sha(p)}
        except (OSError, ValueError, KeyError, TypeError) as error:
            result['fx'] = {'status': 'INVALID', 'error': str(error)}
    return result


def run(loaded, contract, cache, requested=(), suite=None, prepared_only=False):
    config = loaded['configuration']
    shared = source_metadata(contract, cache)
    selection = contract.get('selection')
    if (bool(selection) != (config['source'].get('universe') == 'DECLARED_SELECTION_DIAGNOSTIC')
            or (selection and config['source'].get('selection') != selection['reference'])):
        shared['issues'].append(problem('SELECTION_CONFIG_MISMATCH',
            'The source selection must be explicitly bound by the shared diagnostic configuration.'))
    if selection:
        shared['selection'] = selection
        shared['evaluation_symbol_count'] = len(selection['symbols'])
        shared['signal_context_symbol_count'] = len(selection['context_symbols'])
    from research.testing_stages.economics import economic_metadata
    economics = economic_metadata(config, contract)
    entries = [{'request_id': b['id'], 'role': 'REQUIRED_BENCHMARK', **b} for b in loaded['benchmarks']]
    keys = {canonical(b['model']) for b in entries}
    peers = config.get('extra_peers', [])
    values = selected(list(peers) + list(requested), suite) if peers or requested or suite else []
    for value in values:
        key = canonical(value)
        if key not in keys:
            entries.append({'request_id': str(value), 'role': 'REQUESTED_MODEL', 'model': value,
                            'requested_evidence_class': None, 'identity_files': []})
            keys.add(key)
    rows, adapters = [], {}
    seen_ids = set()
    for entry in entries:
        issues = list(entry.get('configuration_issues', [])) + loaded['issues'] + shared['issues']
        row = {k: entry[k] for k in ('request_id', 'role', 'model', 'requested_evidence_class')}
        row.update(model_id=str(entry['model']), evidence_class=entry.get('available_evidence_class', 'UNRESOLVED'),
                   issues=issues, evidence_gaps=['PREFLIGHT_IS_NOT_SOURCE_CONSUMPTION_OR_PERFORMANCE_PROOF'])
        try:
            for ref in entry['identity_files']:
                if sha(path(ref['path'])) != ref['sha256']:
                    raise ValueError('required model identity file changed: ' + ref['path'])
            if entry['model'] == 'payoff_router':
                raise ValueError('PAYOFF_ROUTER_MINUTE_ADAPTER_UNAVAILABLE: ' + entry['unsupported_reason'])
            from research.testing_stages.adapters import EconomicAdapter
            ledger = config['economics'].get('corporate_actions')
            override = config.get('adapters', {}).get(canonical(entry['model']))
            if override and entry['role'] == 'REQUIRED_BENCHMARK':
                issues.append(problem('REQUIRED_COMPARATOR_ADAPTER_OVERRIDE',
                    'A custom wrapper cannot replace the required comparator identity; test it as a separate candidate file.'))
                override = None
            a = EconomicAdapter(canonical(entry['model']), path(ledger) if ledger else None, override)
            a.set_selection(selection)
            row['model_id'], row['identity'] = a.model_id, a.identity()
            spec = a.spec
            actual = 'NATIVE_EXECUTION' if a.kind == 'plugin' else 'MINUTE_RULE_TRANSPORT'
            # A plugin wrapping a historical/frozen rule must declare the transport.
            actual = spec.get('evidence_class', actual)
            row['evidence_class'] = actual
            row['classification_basis'] = ('DECLARED_STANDARD_MODEL_IMPLEMENTATION_NOT_EXECUTION_VERIFICATION'
                                           if a.kind == 'plugin' else 'RETAINED_RULE_IN_SHARED_MINUTE_SIMULATION')
            if actual not in CLASSES or actual == 'HISTORICAL_ROWS':
                issues.append(problem('UNSUPPORTED_EVIDENCE_CLASS', 'Historical rows cannot be scored as new causal minute actions.'))
            if a.kind != 'plugin' and actual != 'MINUTE_RULE_TRANSPORT':
                issues.append(problem('EVIDENCE_CLASS_MISMATCH', 'The installed frozen/book adapter is a minute-rule transport.'))
            if entry['requested_evidence_class'] and actual != entry['requested_evidence_class']:
                issues.append(problem('EVIDENCE_CLASS_MISMATCH', f'Requested {entry["requested_evidence_class"]}; installed {actual}.'))
            mode = spec['mode']
            decision, execution = CLOCKS[mode]
            row['clocks_and_units'] = {'mode': mode, 'decision_clock': spec.get('decision_clock', decision),
                                       'execution_clock': spec.get('execution_clock', execution), 'units': spec['units'],
                                       'clock_defaults_from': 'stage1_full_minute_v1 protocol',
                                       'native_broker_execution_verified': False}
            if row['clocks_and_units']['decision_clock'] != decision or row['clocks_and_units']['execution_clock'] != execution:
                issues.append(problem('UNSUPPORTED_CLOCK', 'Declared clock differs from the next-open/next-minute evaluator.'))
            if spec.get('price_currency', 'USD') != 'USD' or spec.get('currency', config['economics']['currency']) != config['economics']['currency']:
                issues.append(problem('UNSUPPORTED_UNITS_OR_CURRENCY', 'Model monetary units do not match the shared USD-price/evaluation-currency settings.'))
            native = getattr(a, 'superset', None) or getattr(a, 'native', None) or spec.get('required_symbols') or contract['symbols']
            native = set(native)
            completed = set(shared['checkpoint']['completed_symbols'])
            row['coverage'] = {'required_signal_symbol_count': len(native),
                'required_symbols_outside_shared_universe': sorted(native - set(contract['symbols'])),
                'required_symbols_without_bound_files': sorted(native & set(shared['symbols_without_current_bound_files'])),
                'checkpoint_completed_signal_symbols': len(native & completed),
                'checkpoint_incomplete_signal_symbols': sorted(native - completed),
                'full_shared_universe_retained': not bool(selection), 'usable_minute_coverage': 'NOT_MEASURED'}
            if selection:
                row['evidence_gaps'].append('STATIC_ROSTER_SELECTION_NOT_HISTORICAL_MEMBERSHIP_OR_FULL_ARCHIVE_PROOF')
            if row['coverage']['required_symbols_outside_shared_universe']:
                issues.append(problem('REQUIRED_SIGNAL_SYMBOLS_MISSING', row['coverage']['required_symbols_outside_shared_universe']))
            if row['coverage']['required_symbols_without_bound_files']:
                row['evidence_gaps'].append('REQUIRED_SIGNAL_SYMBOLS_HAVE_NO_BOUND_PRICE_FILES')
            holds = spec.get('holds_overnight', True if mode == 'daily' else 'UNKNOWN')
            if holds not in (True, False, 'UNKNOWN'):
                issues.append(problem('INVALID_OVERNIGHT_DECLARATION', 'holds_overnight must be a boolean; omit it if unknown.'))
            row['required_inputs'] = {'splits': 'REQUIRED' if holds is True else 'REQUIRED_IF_HOLDINGS_CROSS_SESSIONS',
                'dividends': 'REQUIRED' if holds is True else 'REQUIRED_IF_HOLDINGS_CROSS_SESSIONS',
                'fx': 'REQUIRED' if config['economics']['currency'] == 'GBP' else 'NOT_REQUIRED',
                'holdings_declaration_verified': False}
            if economics['corporate_actions']['status'] in ('MISSING', 'INVALID'):
                if holds is True or economics['corporate_actions']['status'] == 'INVALID':
                    issues.append(problem('SPLIT_DIVIDEND_INPUT_UNAVAILABLE', economics['corporate_actions'].get('error', 'Full-period split/dividend ledger missing for an overnight model.')))
                else:
                    row['evidence_gaps'].append('SPLIT_DIVIDEND_LEDGER_REQUIRED_IF_ANY_POSITION_CROSSES_SESSIONS')
            row['evidence_gaps'] += ['CORPORATE_ACTION_COMPLETENESS_NOT_ESTABLISHED', 'CAUSALITY_AND_NATIVE_EXECUTION_NOT_VERIFIED']
            if a.model_id in seen_ids:
                issues.append(problem('DUPLICATE_MODEL_ID', a.model_id))
            seen_ids.add(a.model_id)
            adapters[entry['model']] = a
        except Exception as error:
            issues.append(problem('ADAPTER_OR_IDENTITY_UNAVAILABLE', error))
        row.setdefault('required_inputs', {'splits': 'UNRESOLVED_ADAPTER_REQUIREMENTS',
                                          'dividends': 'UNRESOLVED_ADAPTER_REQUIREMENTS',
                                          'fx': 'REQUIRED' if config['economics']['currency'] == 'GBP' else 'NOT_REQUIRED'})
        row['available_inputs'] = {k: v['status'] for k, v in economics.items() if isinstance(v, dict)}
        if economics['fx']['status'] in ('MISSING', 'INVALID'):
            issues.append(problem('FX_INPUT_UNAVAILABLE', economics['fx'].get('error', 'GBP requires a full-session USD-to-GBP source with availability clocks.')))
        if prepared_only and (shared['checkpoint']['reported_status'] != 'ALL_SOURCE_FILES_CONSUMED'
                              or shared['checkpoint']['missing_partition_files'] or shared['checkpoint']['error']):
            issues.append(problem('PREPARED_CHECKPOINT_UNAVAILABLE', 'Requested prepared-only source is unavailable; preparation remains an ordinary development option.'))
        row['readiness'] = 'INPUTS_MISSING_OR_UNSUPPORTED' if issues else 'READY_FOR_REPLAY_WITH_EVIDENCE_GAPS'
        rows.append(row)
    unresolved = [r['request_id'] for r in rows if r['role'] == 'REQUIRED_BENCHMARK' and r['issues']]
    full = config['objective']['scope'] == 'FULL_CONJECTURE'
    record = {'schema': 'marketmaker.testing_preflight.v1', 'created_at_utc': datetime.now(timezone.utc).isoformat(),
        'configuration': loaded, 'resolved_source_contract_id': contract['contract_id'], 'cache': str(cache),
        'source': shared, 'economic_inputs': economics, 'models': rows,
        'readiness': 'INPUTS_MISSING_OR_UNSUPPORTED' if any(r['issues'] for r in rows) else 'READY_FOR_REPLAY_WITH_EVIDENCE_GAPS',
        'required_comparators_unresolved': unresolved,
        'claim': {'status': 'UNRESOLVED', 'objective': config['objective'],
                  'missing_stages': ['FULL_412_ROW_20_GATE_ISSUER', 'JOINT_PREDICTIVE_EVALUATOR', 'CANONICAL_PIT_AND_PROSPECTIVE_EVIDENCE'] if full else [],
                  'full_source_consumption_verified': False, 'performance_qualification': 'NOT_ESTABLISHED'},
        'development_allowed': True, 'evidence_boundary': 'Readiness does not verify raw/cache bytes, full source consumption, causal predictions, native broker execution or performance.'}

    covered = set(record['economic_inputs']['corporate_actions'].get('covered_symbols', []))
    for row in record['models']:
        a = adapters.get(row['model'])
        if not a:
            continue
        if config['economics']['currency'] != 'USD' or config['economics'].get('fx'):
            row['issues'].append(problem('UNSUPPORTED_ECONOMIC_INTERFACE',
                'The configured cash-event evaluator supports USD; GBP/FX cash-event replay is not implemented.'))
        if a.spec['mode'] != 'daily':
            row['issues'].append({'code': 'UNSUPPORTED_EXECUTION_INTERFACE',
                'message': 'The configured process evaluator supports daily targets on minute prices; native minute callbacks require the strict streaming interface.'})
        try:
            required = {s for s, yes in zip(contract['symbols'], a.eligible(contract['symbols'])) if yes}
        except ValueError as error:
            row['issues'].append(problem('REQUIRED_SIGNAL_SYMBOLS_MISSING', error))
            required = set(getattr(a, 'native', ()) or a.spec.get('symbols', ()))
        row['corporate_action_coverage'] = {'covered': sorted(required & covered),
            'unresolved': sorted(required - covered), 'runtime_check': 'EVERY_HELD_SECURITY_MUST_BE_COVERED'}
        if required - covered:
            row['evidence_gaps'].append('ECONOMIC_IDENTITY_UNRESOLVED: ' + ','.join(sorted(required - covered)))
        if a.kind == 'crash90':
            from research.testing_stages.identity import reconcile
            try:
                row['research_side_frozen_identity'] = reconcile()
            except (OSError, ValueError) as error:
                row['issues'].append(problem('FROZEN_IDENTITY_UNAVAILABLE', error))
        if row['issues']:
            row['readiness'] = 'INPUTS_MISSING_OR_UNSUPPORTED'
    if any(r['issues'] for r in record['models']):
        record['readiness'] = 'INPUTS_MISSING_OR_UNSUPPORTED'
    record['required_comparators_unresolved'] = [r['request_id'] for r in rows if r['role'] == 'REQUIRED_BENCHMARK' and r['issues']]
    from research.testing_stages import measurement
    from research.testing_stages.definitions import for_policy
    record['measurement_contract'] = measurement.stage1(contract, config['economics'],
        for_policy(config['economics'].get('missing_data_policy', 'strict')), economics)
    return record, adapters
