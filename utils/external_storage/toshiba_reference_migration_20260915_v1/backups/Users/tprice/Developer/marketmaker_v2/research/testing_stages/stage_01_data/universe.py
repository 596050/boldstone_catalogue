"""Stage 0 selections ahead of the unchanged stage 1 evaluator.

Reuses stage1's existing declared-selection contracts and the retained S&P 500
Toshiba comparison. This adds reproducible tags/counts, shared input publication
and command routing; it introduces no price, metric or acceptance evaluator.
Subset results remain exploratory comparisons, never full-archive qualification.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys

from research.testing_stages import configuration, preflight, runner, source
from research.testing_stages.common import (
    ROOT, atomic_json, digest, input_path, lock, safe_output, sha,
)
from research.testing_stages.catalog import SuiteAdapter, selected
from research.testing_stages.models import Adapter

HERE = next(p for p in Path(__file__).resolve().parents if p.name == 'testing_stages')
INPUTS = HERE / 'inputs/universe'
TOSHIBA = Path('/Volumes/Toshiba 2TB/marketmaker_v2')
DEFAULT_SOURCE = input_path(HERE / 'stage1_full_minute_v1/runs/frozen_ig_pair_toshiba_20260907/inputs')
DEFAULT_TEMPLATE = runner.HERE / 'configs/frozen_ig_pair_v1.json'
SP500 = ROOT / ('research/all_research_candidates_not_harness_frameworks/'
    'frozen_ig_sp500_toshiba_20260907_v1/SP500_SELECTION.json')
SEED = 960907


def reference(path):
    p = configuration.path(path).resolve()
    return {'path': str(p), 'sha256': sha(p)}


def read_reference(ref):
    p = configuration.path(ref['path'])
    if sha(p) != ref['sha256']:
        raise ValueError('Bound universe input changed: ' + str(p))
    return configuration.metadata(p)


def symbols(values):
    if (not isinstance(values, (list, tuple)) or not values
            or any(not isinstance(s, str) or not s or s.strip() != s
                   or Path(s).name != s or s in ('.', '..') or '\x00' in s for s in values)
            or len(values) != len(set(values))):
        raise ValueError('A roster needs nonempty, unique, valid stock symbols')
    return sorted(values)


def builtins():
    base = Adapter('carry96')
    initial = symbols(base.native)
    if len(initial) != 96:
        raise ValueError('The retained initialuncorr96 source no longer contains 96 stocks')
    return {
        'initialuncorr96': {
            'label': 'initialuncorr96: retained frozen 96-stock roster',
            'symbols': initial, 'source': reference(base.signal_spec.__file__),
            'membership_evidence': 'Retained signal roster; this tag does not assert current decorrelation or historical index membership.',
        },
        'sp500': {**read_reference(reference(SP500)), 'source': reference(SP500)},
    }


def ordered_population(population, initial, seed=SEED):
    """Nested prefixes; no price, coverage or performance-dependent selection."""
    def rank(symbol):
        return hashlib.sha256(f'universe_screening_v1:{seed}:{symbol}'.encode()).hexdigest(), symbol
    population = set(population)
    first = population & set(initial)
    return sorted(first, key=rank) + sorted(population - first, key=rank)


def choose(parent, tag, count, seed, roster_file=None, rosters=None):
    rosters = builtins() if rosters is None else rosters
    tag = (tag or 'all').casefold()
    if tag.isdecimal():
        if count is not None:
            raise ValueError('Use a numeric --universe or --stock-count, not both')
        count, tag = int(tag), 'all'
    if roster_file:
        ref = reference(roster_file)
        roster = read_reference(ref)
        roster = {**roster, 'source': ref}
        tag = str(roster.get('tag', 'custom'))
    elif tag == 'all':
        if count is None:
            return None
        roster = {'label': 'complete archive', 'symbols': parent['symbols']}
    elif tag in rosters:
        roster = deepcopy(rosters[tag])
    else:
        raise ValueError('Unknown universe. Use initialuncorr96, sp500, all, a positive number, or --universe-file PATH')
    population = symbols(roster['symbols'])
    if not isinstance(roster.get('label'), str) or not roster['label'].strip():
        raise ValueError('A roster needs a nonempty label')
    if count is not None:
        if count < 1 or count > len(population):
            raise ValueError(f'Stock count must be between 1 and {len(population)}; no silent truncation')
        population = ordered_population(population, rosters['initialuncorr96']['symbols'], seed)[:count]
    return {
        'schema': 'marketmaker.stage0.stock_roster.v1',
        'tag': tag, 'label': roster['label'] + (f' / fixed {count}-stock prefix' if count is not None else ''),
        'symbols': sorted(population),
        'selection_method': 'retained roster' if count is None else 'initial96 first, then SHA256(seed,symbol); nested prefixes',
        'selection_seed': seed if count is not None else None,
        'source': roster.get('source'),
        'initial_order_source': rosters['initialuncorr96']['source'] if count is not None else None,
        'membership_evidence': roster.get('membership_evidence', 'Static selection; historical membership/PIT NOT_ESTABLISHED'),
    }


def publish(kind, value):
    """Identical inputs share paths and therefore the same prepared price cache."""
    directory = INPUTS / kind / digest(value)
    path = directory / (kind.upper() + '.json')
    with lock(directory):
        if path.exists():
            if configuration.metadata(path) != value:
                raise ValueError('Published universe input changed: ' + str(path))
        else:
            atomic_json(path, value)
    return path


def full_parent(contract_path):
    ref = reference(contract_path)
    contract = source.validate_contract(read_reference(ref))
    if contract.get('selection'):
        ref = contract['selection']['parent_contract']
        contract = source.validate_contract(read_reference(ref))
    return ref, contract


def full_ledger(path, parent):
    if not path:
        return None, None
    ref = reference(path)
    seen = set()
    while True:
        if ref['sha256'] in seen:
            raise ValueError('Cyclic corporate-action parent references')
        seen.add(ref['sha256'])
        value = read_reference(ref)
        if value.get('source_contract_id') == parent['contract_id']:
            if any(value.get(k) != parent[k] for k in ('start', 'end', 'symbols')):
                raise ValueError('Corporate-action source axes do not match the full parent')
            return ref, value
        ref = value.get('selection_parent_ledger')
        if not ref:
            raise ValueError('Supply --corporate-actions matching the full parent source contract; an incomplete subset ledger cannot be expanded')


def selected_ledger(parent_ref, ledger, contract):
    keep = set(contract['symbols'])
    value = deepcopy(ledger)
    value.update(source_contract_id=contract['contract_id'], symbols=contract['symbols'],
                 selection_parent_ledger=parent_ref)
    value['coverage'] = {k: v for k, v in ledger['coverage'].items() if k in keep}
    value['unresolved'] = {k: v for k, v in ledger.get('unresolved', {}).items() if k in keep}
    value['events'] = [e for e in ledger['events'] if e['symbol'] in keep]
    value['source_references'] = [r for r in ledger['source_references'] if r['symbol'] in keep]
    return value


def context_symbols(config, args):
    requests = [b['model'] for b in config['required_benchmarks']]
    peers = list(config.get('extra_peers', [])) + args.models + args.extra_models
    requests += selected(peers, args.suite) if peers or args.suite else []
    required, failures = set(), {}
    explicit = args.models + args.extra_models
    if args.adapter and len(explicit) != 1:
        raise ValueError('--adapter requires exactly one explicit model')
    for model in dict.fromkeys(requests):
        try:
            key = preflight.canonical(model)
            override = args.adapter if args.adapter and key == preflight.canonical(explicit[0]) else config.get('adapters', {}).get(key)
            if any(preflight.canonical(b['model']) == key for b in config['required_benchmarks']):
                override = None
            adapter = SuiteAdapter(key, override)
            for values in (getattr(adapter, 'native', None), getattr(adapter, 'superset', None),
                           adapter.spec.get('required_symbols'), adapter.spec.get('symbols')):
                if values:
                    required.update(symbols(values))
        except (ValueError, OSError, ImportError, KeyError, TypeError) as error:
            # Keep this request in stage1's comparison as an explicit failed column.
            failures[str(model)] = str(error)
    return sorted(required), failures


def parser():
    p = runner.parser()
    sub = next(a for a in p._actions if isinstance(a, argparse._SubParsersAction))
    for name in ('preflight', 'backtest', 'run', 'signals'):
        q = sub.choices[name]
        # Preserve whether the caller supplied a config, including argparse's
        # accepted abbreviations. Legacy calls are delegated with their argv.
        q._option_string_actions['--config'].default = None
        group = q.add_mutually_exclusive_group()
        group.add_argument('--universe', metavar='TAG_OR_COUNT',
            help='initialuncorr96, sp500, all, or a positive count; retains full 2007-to-cutoff minute history')
        group.add_argument('--universe-file', type=Path, help='JSON roster with label and unique symbols; optional tag')
        q.add_argument('--stock-count', type=runner.positive_int, help='fixed nested prefix within the selected universe')
        q.add_argument('--selection-seed', type=int, default=SEED, help='deterministic stock ordering only; default 960907')
    sub.add_parser('screen', parents=[sub.choices['run']], add_help=False,
        help='optional stage 0: initialuncorr96 by default, using the same minute evaluator',
        description='Screen candidates on a declared stock subset before expanding the universe.')
    sub.add_parser('universes', help='list retained stock selections and count semantics')
    return p


def configured(args, explicit_config):
    template = configuration.path(args.config) if explicit_config else DEFAULT_TEMPLATE
    config = deepcopy(configuration.metadata(template))
    if not explicit_config:
        config['source'].update(contract=str(DEFAULT_SOURCE / 'SOURCE_CONTRACT.json'),
            archive_roots=['/Volumes/Toshiba 2TB/marketmaker/iqfeed_archive'],
            cache=str(TOSHIBA / 'recoverable_build_caches/universe_screening_v1'))
        config['economics']['corporate_actions'] = str(DEFAULT_SOURCE / 'CORPORATE_ACTIONS.json')
    if (args.archive_root or args.cutoff) and not args.contract:
        raise ValueError('Universe selection needs a frozen --contract and matching corporate actions; use discover to bind a new cutoff first')
    if args.contract:
        config['source']['contract'] = str(configuration.path(args.contract))
    if args.cache:
        config['source']['cache'] = str(args.cache.resolve())
    for key in ('capital', 'unit_notional', 'funding_annual', 'currency', 'seed', 'corporate_actions', 'fx', 'missing_data_policy'):
        value = getattr(args, key, None)
        if value is not None:
            config['economics'][key] = str(configuration.path(value)) if key in ('corporate_actions', 'fx') else value
    if args.missing_data_policy is not None:
        config['metric_contract']['definitions'] = configuration.definitions.for_policy(args.missing_data_policy)
    config['universe_template'] = reference(template)
    return config


def prepare(args, config, roster, parent_ref, parent):
    context, failures = context_symbols(config, args)
    if roster is None:
        contract, contract_path = parent, Path(parent_ref['path'])
        config['source'].pop('selection', None)
        config['source']['universe'] = 'COMPLETE_SHARED_ARCHIVE_UNION'
    else:
        if config['objective']['scope'] != 'STAGE1_COMPARISON':
            raise ValueError('A subset is an exploratory comparison; it cannot use the full-conjecture objective')
        roster_path = publish('roster', roster)
        contract = source.selected_contract(parent_ref, reference(roster_path), context)
        contract_path = publish('contract', contract)
        config['source'].update(universe='DECLARED_SELECTION_DIAGNOSTIC', selection=reference(roster_path))
    ledger_ref, ledger = full_ledger(config['economics'].get('corporate_actions'), parent)
    if ledger is not None:
        ledger_path = Path(ledger_ref['path']) if roster is None else publish('corporate_actions', selected_ledger(ledger_ref, ledger, contract))
        config['economics']['corporate_actions'] = str(ledger_path)
    config['source'].update(contract=str(contract_path), archive_roots=parent['roots'], cutoff=None)
    config['config_id'] = 'universe_screening_v1.' + contract['contract_id'][:20]
    config['universe_request'] = {
        'stage': 'STAGE0_SCREENING' if args.command == 'screen' else 'EXPLICIT_UNIVERSE',
        'tag': args.universe or ('custom' if args.universe_file else 'all'),
        'stock_count': args.stock_count, 'selection_seed': args.selection_seed,
        'selected_stock_count': len(source.evaluation_symbols(contract)),
        'context_stock_count': len(contract.get('selection', {}).get('context_symbols', [])),
        'context_resolution_failures': failures, 'parent_source': parent_ref,
        'selection_code': reference(Path(__file__)),
        'scope': 'EXPLORATORY_SUBSET_COMPARISON_NOT_FULL_ARCHIVE_QUALIFICATION' if roster else 'FULL_PARENT_SOURCE',
        'advancement': 'Review the common comparison table, then request a larger universe in a new run. No automatic promotion.',
    }
    return config, contract


def stage_command(args, config_path, output, ledger_dir):
    command = 'run' if args.command == 'screen' else args.command
    values = [command, *args.models]
    for model in args.extra_models:
        values += ['--model', model]
    values += ['--config', str(config_path), '--output', str(output),
               '--model-workers', str(args.model_workers), '--ledger-dir', str(ledger_dir), '--comparison-table']
    if getattr(args, 'source_workers', None) is not None:
        values += ['--source-workers', str(args.source_workers)]
    for name in ('adapter', 'suite', 'reuse_cache'):
        value = getattr(args, name, None)
        if value is not None:
            values += ['--' + name.replace('_', '-'), str(value)]
    for name in ('prepared_only', 'package_checks', 'verify', 'incremental_comparison'):
        if getattr(args, name, False):
            values.append('--' + name.replace('_', '-'))
    stages = getattr(args, 'stages', None)
    if args.command == 'screen' and not stages:
        stages = ['preflight', 'backtest', 'verify']
    if stages:
        values += ['--stages', *stages]
    return values


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    args = parser().parse_args(argv)
    if args.command == 'universes':
        rosters = builtins()
        for tag, roster in rosters.items():
            print(f'{tag}: {len(roster["symbols"])} stocks; {roster["label"]}')
        print('all: every stock in the full source contract')
        print('N: exactly N stocks; nested deterministic prefixes with the initial 96 first')
        print('--stock-count N: prefix within a tag; --universe-file PATH: custom JSON roster')
        return 0
    active = args.command == 'screen' or getattr(args, 'universe', None) is not None or getattr(args, 'stock_count', None) is not None or getattr(args, 'universe_file', None) is not None
    if not active:
        return runner.main(argv)
    if args.command == 'screen' and args.universe is None and args.universe_file is None:
        args.universe = 'initialuncorr96' if args.stock_count is None else 'all'
    output = safe_output(args.output or HERE / 'runs' / (
        datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ') + '_' + str(os.getpid()))).resolve()
    if ROOT / 'research' not in output.parents:
        raise ValueError('Retain output under this repository research directory')
    with lock(output):
        if any(p.name != 'RUN.lock' for p in output.iterdir()):
            raise FileExistsError('Preserve this attempt; choose a new --output')
        try:
            config = configured(args, args.config is not None)
            parent_ref, parent = full_parent(config['source']['contract'])
            if args.cutoff and args.cutoff != parent['cutoff_utc']:
                raise ValueError('--cutoff differs from the bound contract; supply matching frozen inputs')
            if args.archive_root and sorted(args.archive_root) != sorted(parent['roots']):
                raise ValueError('--archive-root differs from the bound source contract')
            roster = choose(parent, args.universe, args.stock_count, args.selection_seed, args.universe_file)
            config, contract = prepare(args, config, roster, parent_ref, parent)
            config_path = output / 'UNIVERSE_CONFIG.json'
            atomic_json(config_path, config)
            ledger_dir = args.ledger_dir or TOSHIBA / 'universe_screening_v1/ledgers' / digest(str(output))[:24]
            command = stage_command(args, config_path, output, ledger_dir)
            atomic_json(output / 'UNIVERSE_REQUEST.json', {
                'requested_command': argv, 'stage1_command': command,
                'source_contract_id': contract['contract_id'], 'configuration': reference(config_path),
                **config['universe_request'],
            })
        except Exception as error:
            atomic_json(output / 'UNIVERSE_FAILURE.json', {'error': str(error),
                'type': type(error).__name__, 'requested_command': argv,
                'performance_qualification': 'NOT_ESTABLISHED'})
            print(str(error), file=sys.stderr)
            return 2
    print(f'Universe: {config["universe_request"]["selected_stock_count"]} stocks; '
          f'{contract["start"]} through {contract["end"]}; 60-second bars.\nOutput: {output}', flush=True)
    return runner.main(command)
