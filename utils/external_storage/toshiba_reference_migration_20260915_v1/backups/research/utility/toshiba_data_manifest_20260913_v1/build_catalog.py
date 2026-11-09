"""Build compact, source-labelled indexes from the completed live file census."""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import csv
import gzip
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re

HERE = Path(__file__).resolve().parent
RUN = HERE / 'run_03'


def read_rows(path):
    with gzip.open(path, 'rt') as f:
        for line in f:
            yield json.loads(line)


def write(path, obj):
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + '\n')


def fresh_group():
    return {'files': 0, 'bytes': 0, 'zero_byte_files': 0, 'partial_or_temporary_files': 0}


def main():
    global RUN
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--run-id', default='run_03')
    args = ap.parse_args()
    if Path(args.run_id).name != args.run_id:
        raise SystemExit('run-id must be a directory name')
    RUN = HERE / args.run_id
    catalog_dir = RUN / 'source_catalogs'
    if not catalog_dir.is_dir():
        catalog_dir = HERE / 'source_catalogs'
    summary = json.loads((RUN / 'SUMMARY.json').read_text())
    if summary['exception'] or summary['pending_directories'] or not summary['identity_unchanged']:
        raise SystemExit('Census did not reach a valid final state')
    directories = {r['path']: fresh_group() for r in read_rows(RUN / 'DIRECTORIES.jsonl.gz')}
    directories['.'] = fresh_group()
    categories = defaultdict(fresh_group)
    suffixes = Counter()
    focus_files = {}
    all_paths = set()
    largest = []
    total_rows = 0
    main_roots = ['marketmaker/iqfeed_archive', 'macroeconomics', 'marketmaker/macro_archive']
    iq_catalog = defaultdict(lambda: {'files': 0, 'bytes': 0, 'symbols_from_filenames': set(), 'file_extensions': Counter()})
    metadata_candidates = []
    for row in read_rows(RUN / 'FILES.jsonl.gz'):
        path = row['path']
        if path in all_paths:
            raise ValueError(f'Duplicate file path: {path}')
        if PurePosixPath(path).is_absolute() or '..' in PurePosixPath(path).parts:
            raise ValueError(f'Unsafe manifest path: {path}')
        all_paths.add(path)
        total_rows += 1
        parts = path.split('/')
        suffixes[PurePosixPath(path).suffix.lower() or '(none)'] += 1
        increments = {'files': 1, 'bytes': row['bytes'], 'zero_byte_files': int(row['bytes'] == 0),
                      'partial_or_temporary_files': int(row['partial_download_or_temporary_name'])}
        group = categories[row['category']]
        for k, v in increments.items():
            group[k] += v
        for depth in range(len(parts)):
            parent = '/'.join(parts[:depth]) or '.'
            if parent not in directories:
                raise ValueError(f'File lacks a recorded parent: {path}')
            for k, v in increments.items():
                directories[parent][k] += v
        if path.startswith('macroeconomics/'):
            focus_files[path] = {k: row[k] for k in ('bytes', 'mtime_ns', 'inode')}
        if path.startswith('marketmaker/iqfeed_archive/'):
            root = '/'.join(parts[:3])
            if len(parts) >= 4:
                iq_catalog[root]['files'] += 1
                iq_catalog[root]['bytes'] += row['bytes']
                iq_catalog[root]['file_extensions'][PurePosixPath(path).suffix.lower()] += 1
                name = parts[-1]
                if name.endswith('.csv') and not name.startswith('.') and '__' not in name:
                    iq_catalog[root]['symbols_from_filenames'].add(name[:-4])
        if len(largest) < 30 or row['bytes'] > largest[-1]['bytes']:
            largest.append({'path': path, 'bytes': row['bytes']})
            largest = sorted(largest, key=lambda r: (-r['bytes'], r['path']))[:30]
        if row['category'] != 'other' and re.search(r'(manifest|archive|status|series.index|freshness|receipt|checkpoint)', parts[-1], re.I):
            metadata_candidates.append({'path': path, 'bytes': row['bytes']})
    assert total_rows == summary['totals']['files']
    assert directories['.']['bytes'] == summary['totals']['file_bytes']
    errors = list(read_rows(RUN / 'ERRORS.jsonl.gz'))
    reads = list(read_rows(RUN / 'DIRECTORY_READS.jsonl.gz'))
    attempted = {r['path'] for r in reads}
    assert len(attempted) == len(reads), 'Duplicate directory visits'
    unattempted = sorted(set(directories) - attempted)
    if unattempted:
        raise ValueError(f'Unattempted directories: {unattempted[:5]}')
    for r in reads:
        directories[r['path']]['traversal_status'] = r['status']
        directories[r['path']]['changed_during_listing'] = r['changed_during_listing']
    for err in errors:
        parts = err['path'].split('/')
        for depth in range(len(parts) + 1):
            parent = '/'.join(parts[:depth]) or '.'
            if parent in directories:
                directories[parent].setdefault('errors_in_subtree', []).append(err['path'])
    with gzip.open(RUN / 'DIRECTORY_SUMMARY.jsonl.gz', 'wt') as f:
        for path, group in sorted(directories.items()):
            f.write(json.dumps({'path': path, **group}, separators=(',', ':')) + '\n')
    top = [{'path': p, **g} for p, g in sorted(directories.items())
           if p.count('/') < 3 and p != '.']
    write(RUN / 'DIRECTORY_INDEX.json', top)
    write(RUN / 'METADATA_CATALOG_PATHS.json', metadata_candidates)
    for v in iq_catalog.values():
        v['symbols_from_filenames'] = sorted(v['symbols_from_filenames'])
        v['symbol_name_count'] = len(v['symbols_from_filenames'])
    write(RUN / 'IQFEED_DATASETS.json', {
        'source': 'Current file census', 'symbol_method': 'Plain .csv filenames, not provider identity or interior coverage verification',
        'datasets': dict(sorted(iq_catalog.items())),
        'other_iqfeed_named_directories': [{'path': p, **v} for p, v in sorted(directories.items())
             if 'iqfeed' in p.lower() and p.count('/') <= 4 and not p.startswith('marketmaker/iqfeed_archive')],
    })
    receipts = json.loads((catalog_dir / 'RECEIPTS.json').read_text())
    sources = {}
    for receipt in receipts:
        if 'error' in receipt:
            continue
        local = catalog_dir / Path(receipt['local_path']).name
        content = gzip.decompress(local.read_bytes())
        assert hashlib.sha256(content).hexdigest() == receipt['source_sha256']
        census = focus_files.get(receipt['external_path'])
        receipt['matches_census_size_and_mtime'] = bool(census and census['bytes'] == receipt['bytes']
                 and census['mtime_ns'] == receipt['source_mtime_ns'])
        if receipt['external_path'].endswith('.json'):
            sources[receipt['external_path']] = json.loads(content)
        elif receipt['external_path'].endswith('.csv'):
            sources[receipt['external_path']] = list(csv.DictReader(io.StringIO(content.decode())))
    write(RUN / 'SOURCE_CATALOG_BINDING.json', receipts)
    jobs = sources['macroeconomics/metadata/MANIFEST.csv']
    states = Counter()
    presence = Counter()
    family_stats = defaultdict(lambda: {'jobs': 0, 'declared_rows': 0, 'statuses': Counter(), 'first': None, 'last': None})
    with gzip.open(RUN / 'MACRO_ACQUISITIONS.jsonl.gz', 'wt') as out:
        for job in jobs:
            states[job['status']] += 1
            row = {'source_catalog': 'macroeconomics/metadata/MANIFEST.csv',
                   'source_fields': job, 'payloads': [], 'source_hash_rechecked': False}
            for field in ('raw_file', 'csv_file'):
                rel = job[field]
                if not rel:
                    continue
                path = 'macroeconomics/' + rel
                found = focus_files.get(path)
                key = 'present_in_census' if found else 'not_found_in_census'
                presence[key] += 1
                row['payloads'].append({'path': path, 'status': key, 'observed': found,
                     'declared_sha256': job.get(field.replace('_file', '_sha256')),
                     'hash_status': 'HISTORICAL_CATALOG_VALUE_NOT_PAYLOAD_REHASH'})
            rel = job.get('csv_file') or job.get('raw_file') or ''
            family = '/'.join(rel.split('/')[:3]) if rel.startswith('iqfeed/') else (rel.split('/')[0] or 'no_payload_path')
            group = family_stats[family]
            group['jobs'] += 1; group['statuses'][job['status']] += 1
            group['declared_rows'] += int(job['rows'] or 0)
            if job['first']:
                group['first'] = min(group['first'] or job['first'], job['first'])
            if job['last']:
                group['last'] = max(group['last'] or job['last'], job['last'])
            out.write(json.dumps(row, separators=(',', ':')) + '\n')
    macro = {
        'source_catalog_read_at_utc': [r['observed_at_utc'] for r in receipts],
        'archive': sources['macroeconomics/metadata/ARCHIVE.json'],
        'historical_collector_status': sources['macroeconomics/metadata/STATUS.json'],
        'job_status_counts_recounted': dict(states), 'payload_reference_presence': dict(presence),
        'families': dict(sorted(family_stats.items())),
        'economic_series': sources['macroeconomics/economic_releases/metadata/SERIES_INDEX.csv'],
        'economic_release_status': sources['macroeconomics/economic_releases/metadata/STATUS.json'],
        'economic_archive': sources['macroeconomics/economic_releases/metadata/ARCHIVE.json'],
        'consensus_access': sources['macroeconomics/economic_releases/consensus/ACCESS_STATUS.json'],
        'policy_expectations_access': sources['macroeconomics/economic_releases/policy_expectations/ACCESS_STATUS.json'],
        'economic_release_job_states': dict(Counter(j['state'] for j in sources['macroeconomics/economic_releases/metadata/MANIFEST.json'])),
        'older_macro_archive_providers': [{'path': p, **g} for p, g in sorted(directories.items())
             if p.startswith('marketmaker/macro_archive/') and p.count('/') == 2],
        'employment_and_yield_extensions': [{'path': p, 'series_from_directory_name': p.split('/')[-1], **g}
             for p, g in sorted(directories.items())
             if p.startswith('macroeconomics/economic_releases/extensions/employment_yields_20260912_v1/')
             and p.count('/') == 4],
        'related_research_artifact_directories': [{'path': p, **g} for p, g in sorted(directories.items())
             if p.startswith('marketmaker/data/research/artifacts/') and p.count('/') == 4
             and re.search(r'(macro|employment|cpi|interest_rate|rate_volatility)', p, re.I)],
        'coverage_qualification': 'Rows, dates and checksums are source-catalog declarations. Presence and sizes are reconciled to the new live census. No full payload or interior temporal-completeness audit.',
    }
    write(RUN / 'MACRO_DATASETS.json', macro)
    write(RUN / 'EXCLUSIONS.json', {
        'filesystem_errors': errors, 'unattempted_directories': unattempted,
        'scope': 'All reachable files, including other data, research outputs and cache files, are in FILES.jsonl.gz.',
        'not_expanded': ['Members inside ZIP, TAR and other containers', 'Filesystems inside disk images and sparsebundles',
                         'Tables, sheets and array variables inside databases, workbooks and binary datasets'],
        'not_read_or_certified': ['Full payload hashes', 'Interior bar or observation completeness',
                                 'Point-in-time availability, announcement clocks and data semantics outside the retained source catalogues',
                                 'Extended attributes, ACLs and resource fork contents', 'Deleted or unallocated space'],
        'atomic_snapshot': False, 'other_devices_and_symlink_targets_followed': False,
        'physical_allocation': 'Not generally measured; file bytes are logical lengths.',
    })
    write(RUN / 'CATALOG_SUMMARY.json', {
        'created_at_utc': datetime.now(timezone.utc).isoformat(), 'files': total_rows,
        'file_bytes': directories['.']['bytes'], 'directories_including_root': len(directories),
        'categories': dict(categories), 'suffixes': dict(suffixes), 'largest_files': largest,
        'priority_roots': [{'path': p, **directories[p]} for p in main_roots],
        'errors': errors, 'source_catalogs': len(receipts),
    })
    print(json.dumps({'files': total_rows, 'bytes': directories['.']['bytes'], 'directories': len(directories),
                     'macro_jobs': len(jobs), 'errors': len(errors)}, indent=2))


if __name__ == '__main__':
    main()
