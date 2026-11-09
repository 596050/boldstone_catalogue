"""Create a complete conservative relocation plan from a file-level census.

Unclassified material is retained. No content deduplication or cache deletion.
Source-specific directory layouts are retained under their destination roots.
"""
from collections import Counter, defaultdict
import gzip
import hashlib
import json
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
UUID = '087E2AA1-5151-322D-8C09-9852ECD979B5'
MOUNT = '/Volumes/Toshiba 2TB'


def make_plan(census):
    actions = {}
    def add(source, target, category, basis):
        if source in actions and actions[source]['target'] != target:
            raise ValueError('Conflicting source routing: ' + source)
        actions[source] = {'source': source, 'target': target, 'category': category, 'basis': basis}

    add('marketmaker/iqfeed_archive', 'raw_price_data/iqfeed_archive', 'price_source_bundle', 'IQFeed raw protocol and daily/minute/tick archive with original receipts')
    add('macroeconomics/economic_releases', 'other_data/macroeconomics/economic_releases', 'non_price_source', 'Official release calendars, original responses and vintages')
    add('macroeconomics', 'raw_price_data/iqfeed_macro_market', 'price_source_bundle', 'IQFeed commodities, currencies, treasuries, rates and market proxies; economic releases extracted separately')
    add('marketmaker/macro_archive', 'other_data/non_price_provider_archive', 'non_price_source', 'FRED, EIA, SEC, Treasury, CFTC, FINRA, GDELT and other provider archives')
    actions['marketmaker/macro_archive']['sample_limit'] = 0

    top_data = set()
    top_v2 = set()
    top_marketmaker = set()
    price_candidates = set()
    direct_ibkr_files = []
    all_files = 0
    with gzip.open(census / 'FILES.jsonl.gz', 'rt') as f:
        for line in f:
            r = json.loads(line); path = r['path']; parts = path.split('/')
            all_files += 1
            if parts[0] == 'marketmaker' and len(parts) >= 2:
                top_marketmaker.add(parts[1])
            if path.startswith('marketmaker/data/') and len(parts) >= 3:
                top_data.add(parts[2])
            if parts[0] == 'marketmaker_v2' and len(parts) >= 2:
                top_v2.add(parts[1])
            if path.startswith('marketmaker/data/ibkr/') and len(parts) == 4:
                direct_ibkr_files.append(path)
            # Explicit wire-price captures and acquisition directories hidden in research.
            if path.startswith(('marketmaker/data/research/', 'marketmaker/research_runtime_offload/')):
                for i, part in enumerate(parts[:-1]):
                    if part in {'iqfeed', 'raw_daily'}:
                        price_candidates.add('/'.join(parts[:i+1])); break
                    if part == 'raw' and any(key in path.lower() for key in (
                            'iqfeed', 'max_history_exact_clock', 'carry96_stock_only_max_history',
                            'iex_rli_stock', 'iqfeed_l2_mbp_mbo')):
                        price_candidates.add('/'.join(parts[:i+1])); break
            if path.startswith('marketmaker/research/') and '.pcap' in parts[-1].lower():
                price_candidates.add('/'.join(parts[:3]))

    # Include zero-byte files and empty directories from the same fresh census.
    with gzip.open(census / 'DIRECTORIES.jsonl.gz', 'rt') as f:
        for line in f:
            parts = json.loads(line)['path'].split('/')
            if parts[0] == 'marketmaker' and len(parts) == 2: top_marketmaker.add(parts[1])
            if parts[:2] == ['marketmaker', 'data'] and len(parts) == 3: top_data.add(parts[2])
            if parts[0] == 'marketmaker_v2' and len(parts) == 2: top_v2.add(parts[1])

    for path in sorted(price_candidates):
        add(path, 'raw_price_data/recovered_project_sources/' + path, 'price_source_bundle',
            'Explicit IQFeed/raw-daily acquisition subtree or IEX packet capture; supporting records retained')
    for name in top_data:
        source = 'marketmaker/data/' + name
        price = name in {'ibkr', 'ibkr_adr_home_fx_bbo_v1', 'ig', 'yahoo', 'raw', 'iqfeed_downloads_v2'}
        add(source, ('raw_price_data/' if price else 'other_data/') + name,
            'legacy_price_and_broker_bundle' if price else 'retained_other_data',
            'Original data namespace retained; specific non-price subtrees routed separately')
    add('marketmaker/data/raw/non_price', 'other_data/raw/non_price', 'non_price_source', 'Explicit non-price acquisition root')
    add('marketmaker/data/ibkr/exogenous/weather_hourly_forecast', 'other_data/non_price_legacy/weather_hourly_forecast', 'non_price_source', 'Weather forecasts and their metadata')
    add('marketmaker/data/ibkr/exogenous/hourly_forward_snapshot', 'other_data/non_price_legacy/hourly_forward_snapshot', 'retained_other_data', 'Mixed exogenous forward snapshot retained separately')

    # Raw price tables remain in their dataset directories. The loose legacy
    # directory files are diagnostics, reports, positioning series and archives.
    for path in direct_ibkr_files:
        name = path.rsplit('/', 1)[1]
        if name == '.DS_Store': continue
        if name in {'_archived_dormant_dirs_20260709.tar.gz', '_archived_zero_reference_dirs_20260725.tar.gz'}:
            add(path, 'raw_price_data/embedded_source_archives/' + name, 'price_source_bundle',
                'Tar member inventory confirmed price tables and tick probes; mixed bundle retained intact')
        else:
            add(path, 'other_data/legacy_ibkr_files/' + name, 'retained_legacy_file',
                'Loose legacy reports/source containers retained individually; no deletion based on filename')

    source_updates = 'marketmaker/data/research/testing_stages/source_updates'
    add(source_updates, 'raw_price_data/price_views/source_updates', 'price_source_views',
        'Versioned source updates and formatted price materializations; not counted as unique raw observations')
    hybrid = 'marketmaker_v2/frozen_ig_pair_20260907/hybrid_price_data_20260908_01'
    add(hybrid, 'raw_price_data/price_views/hybrid_price_data_20260908_01', 'price_source_views',
        'Producer/verifier binary price representations retained separately from vendor wire data')
    for name in top_v2:
        add('marketmaker_v2/' + name, 'other_data/retained_marketmaker_v2/' + name,
            'retained_project_data', 'Preserve every remaining research record, cache, model and source container; original root left in place')
    for name in top_marketmaker - {'data', 'iqfeed_archive', 'macro_archive'}:
        add('marketmaker/' + name, 'other_data/retained_marketmaker/' + name,
            'retained_project_data', 'Preserve all remaining project material, including hidden files and original identity records')

    # Ignore optional directories not present in the census; no expected source
    # may be silently ignored by the executor after the plan has been frozen.
    observed = set()
    for name in ['FILES.jsonl.gz', 'DIRECTORIES.jsonl.gz', 'OTHER_ENTRIES.jsonl.gz']:
        with gzip.open(census / name, 'rt') as f:
            for line in f:
                path = json.loads(line)['path']
                if path in actions: observed.add(path)
    actions = {k: v for k, v in actions.items() if k in observed}
    # Child extractions precede parent moves. No target path can overwrite another.
    ordered = sorted(actions.values(), key=lambda x: (-x['source'].count('/'), x['source']))
    targets = [x['target'].casefold() for x in ordered]
    if len(targets) != len(set(targets)): raise ValueError('Destination name collision')
    return {'schema': 'toshiba.organization.plan.v1', 'volume_uuid': UUID,
            'census': str(census.relative_to(REPO)), 'initial_file_records': all_files,
            'source_census_atomic': False, 'actions': ordered,
            'delete_policy': 'Only rmdir on verified empty marketmaker directories; marketmaker_v2 root remains',
            'payload_deletions': [], 'unknown_material_policy': 'Preserve with original relative path and disclose classification limits'}


def route(path, index):
    source = path
    while source:
        action = index.get(source)
        if action:
            return action['target'] + path[len(source):], action
        source = source.rpartition('/')[0]
    return path, None


def main():
    census = Path(sys.argv[1]).resolve()
    plan = make_plan(census)
    index = {action['source']: action for action in plan['actions']}
    counts = defaultdict(Counter)
    unrouted = []
    with gzip.open(census / 'FILES.jsonl.gz', 'rt') as f, gzip.open(HERE / 'PLANNED_FILES.jsonl.gz', 'wt', compresslevel=3) as out:
        for line in f:
            row = json.loads(line); target, action = route(row['path'], index)
            if row['path'].startswith(('marketmaker/', 'marketmaker_v2/', 'macroeconomics/')):
                if action is None: unrouted.append(row['path'])
                else:
                    counts[action['category']]['files'] += 1
                    counts[action['category']]['bytes'] += row['bytes']
                out.write(json.dumps({'source': row['path'], 'target': target,
                                      'category': action['category'] if action else 'UNROUTED',
                                      'bytes': row['bytes'], 'mtime_ns': row['mtime_ns'], 'inode': row['inode']}, separators=(',', ':')) + '\n')
    plan['category_counts_before_repairs'] = dict(counts)
    plan['unrouted_files'] = unrouted
    if unrouted: raise RuntimeError(f'{len(unrouted)} files are not assigned a preserved destination')
    (HERE / 'PLAN.json').write_text(json.dumps(plan, indent=2) + '\n')
    print(json.dumps({'actions': len(plan['actions']), 'unrouted': len(unrouted), 'categories': counts}, indent=2))


if __name__ == '__main__': main()
