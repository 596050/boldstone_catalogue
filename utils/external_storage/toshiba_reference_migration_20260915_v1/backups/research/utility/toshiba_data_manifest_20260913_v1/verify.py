"""Independent reconciliation of retained entries, traversal and source copies."""
import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
import gzip
import hashlib
import io
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUN = HERE / 'run_03'


def rows(path):
    with gzip.open(path, 'rt') as f:
        for line in f:
            yield json.loads(line)


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


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
    identity = json.loads((RUN / 'SOURCE_IDENTITY.json').read_text())
    assert summary['identity_unchanged'] and not summary['exception'] and not summary['pending_directories']
    assert identity['scanner_sha256'] == sha(HERE / 'scan.py')
    assert identity['bulk_reader_sha256'] == sha(HERE / 'bulk_metadata.py')
    for name, expected in summary['files'].items():
        assert expected['sha256'] == sha(RUN / name), name
        assert expected['bytes'] == (RUN / name).stat().st_size, name
    paths = set()
    child_counts = Counter()
    totals = Counter()
    directory_paths = {'.'}
    catalog_receipts = json.loads((catalog_dir / 'RECEIPTS.json').read_text())
    catalog_paths = {r['external_path'] for r in catalog_receipts}
    observed_catalogs = {}
    macro_payloads = {}
    direct_totals = defaultdict(Counter)
    categories = defaultdict(Counter)
    iq_totals = defaultdict(Counter)
    iq_extensions = defaultdict(Counter)
    iq_symbols = defaultdict(set)
    for name in ['FILES.jsonl.gz', 'DIRECTORIES.jsonl.gz', 'OTHER_ENTRIES.jsonl.gz']:
        for r in rows(RUN / name):
            p = r['path']
            assert p not in paths, p
            assert not p.startswith('/') and '..' not in p.split('/'), p
            paths.add(p)
            child_counts[p.rsplit('/', 1)[0] if '/' in p else '.'] += 1
            totals['entries'] += 1
            if r['kind'] == 'directory':
                totals['directories'] += 1; directory_paths.add(p)
            elif r['kind'] == 'file':
                totals['files'] += 1; totals['file_bytes'] += r['bytes']
                totals['zero_byte_files'] += r['bytes'] == 0
                totals['partial_or_temporary_files'] += r['partial_download_or_temporary_name']
                increment = {'files': 1, 'bytes': r['bytes'],
                             'zero_byte_files': int(r['bytes'] == 0),
                             'partial_or_temporary_files': int(r['partial_download_or_temporary_name'])}
                parent = p.rsplit('/', 1)[0] if '/' in p else '.'
                direct_totals[parent].update(increment)
                categories[r['category']].update(increment)
                parts = p.split('/')
                if p.startswith('marketmaker/iqfeed_archive/') and len(parts) >= 4:
                    family = '/'.join(parts[:3])
                    iq_totals[family].update({'files': 1, 'bytes': r['bytes']})
                    iq_extensions[family][Path(p).suffix.lower()] += 1
                    name = parts[-1]
                    if name.endswith('.csv') and not name.startswith('.') and '__' not in name:
                        iq_symbols[family].add(name[:-4])
                if p in catalog_paths:
                    observed_catalogs[p] = r
                if p.startswith('macroeconomics/'):
                    macro_payloads[p] = {k: r[k] for k in ('bytes', 'mtime_ns', 'inode')}
            else:
                totals[r['kind']] += 1
    for k, v in totals.items():
        assert summary['totals'][k] == v, (k, v, summary['totals'].get(k))
    reads = list(rows(RUN / 'DIRECTORY_READS.jsonl.gz'))
    assert {r['path'] for r in reads} == directory_paths
    assert len(reads) == len(directory_paths)
    for r in reads:
        assert child_counts[r['path']] == r['entries_read'], r['path']
    errors = list(rows(RUN / 'ERRORS.jsonl.gz'))
    assert len(errors) == summary['totals']['errors']
    exclusions = json.loads((RUN / 'EXCLUSIONS.json').read_text())
    assert exclusions['filesystem_errors'] == errors
    assert exclusions['unattempted_directories'] == []
    assert exclusions['atomic_snapshot'] == summary['atomic_snapshot']
    # Reconcile exported indexes independently, by propagating direct children
    # upwards rather than the builder's file-to-all-ancestors accumulation.
    aggregate = {p: direct_totals[p].copy() for p in directory_paths}
    for p in sorted(directory_paths - {'.'}, key=lambda x: x.count('/'), reverse=True):
        parent = p.rsplit('/', 1)[0] if '/' in p else '.'
        aggregate[parent].update(aggregate[p])
    index_rows = list(rows(RUN / 'DIRECTORY_SUMMARY.jsonl.gz'))
    assert len(index_rows) == len(directory_paths)
    indexed = {r['path']: r for r in index_rows}
    assert set(indexed) == directory_paths
    read_index = {r['path']: r for r in reads}
    for p, row in indexed.items():
        for key in ('files', 'bytes', 'zero_byte_files', 'partial_or_temporary_files'):
            assert row[key] == aggregate[p][key], (p, key)
        assert row['traversal_status'] == read_index[p]['status'], p
        assert row['changed_during_listing'] == read_index[p]['changed_during_listing'], p
        expected_errors = sorted({e['path'] for e in errors
                                  if p == '.' or e['path'] == p or e['path'].startswith(p + '/')})
        assert sorted(row.get('errors_in_subtree', [])) == expected_errors, p
    top = json.loads((RUN / 'DIRECTORY_INDEX.json').read_text())
    assert top == [indexed[p] for p in sorted(indexed) if p != '.' and p.count('/') < 3]
    catalog = json.loads((RUN / 'CATALOG_SUMMARY.json').read_text())
    assert catalog['files'] == totals['files'] and catalog['file_bytes'] == totals['file_bytes']
    assert catalog['directories_including_root'] == len(directory_paths)
    assert catalog['categories'] == {k: dict(v) for k, v in categories.items()}
    for row in catalog['priority_roots']:
        assert row == indexed[row['path']], row['path']
    iq = json.loads((RUN / 'IQFEED_DATASETS.json').read_text())
    assert set(iq['datasets']) == set(iq_totals)
    for p, row in iq['datasets'].items():
        assert row['files'] == iq_totals[p]['files'] and row['bytes'] == iq_totals[p]['bytes'], p
        assert row['file_extensions'] == dict(iq_extensions[p]), p
        assert row['symbols_from_filenames'] == sorted(iq_symbols[p]), p
        assert row['symbol_name_count'] == len(iq_symbols[p]), p
    assert iq['other_iqfeed_named_directories'] == [indexed[p] for p in sorted(indexed)
        if 'iqfeed' in p.lower() and p.count('/') <= 4 and not p.startswith('marketmaker/iqfeed_archive')]
    bindings = json.loads((RUN / 'SOURCE_CATALOG_BINDING.json').read_text())
    for binding in bindings:
        assert binding['matches_census_size_and_mtime'], binding['external_path']
    assert set(observed_catalogs) == catalog_paths
    source_contents = {}
    for receipt in catalog_receipts:
        assert 'error' not in receipt
        observed = observed_catalogs[receipt['external_path']]
        assert observed['bytes'] == receipt['bytes']
        assert observed['mtime_ns'] == receipt['source_mtime_ns']
        p = catalog_dir / Path(receipt['local_path']).name
        assert sha(p) == receipt['compressed_sha256']
        content = gzip.decompress(p.read_bytes())
        assert len(content) == receipt['bytes']
        assert hashlib.sha256(content).hexdigest() == receipt['source_sha256']
        assert receipt['stable_during_copy']
        source_contents[receipt['external_path']] = content
    states, presence = Counter(), Counter()
    source_jobs = csv.DictReader(io.StringIO(source_contents['macroeconomics/metadata/MANIFEST.csv'].decode()))
    for job, original_job in zip(rows(RUN / 'MACRO_ACQUISITIONS.jsonl.gz'), source_jobs, strict=True):
        assert job['source_fields'] == original_job
        assert job['source_hash_rechecked'] is False
        assert [p['path'] for p in job['payloads']] == [
            'macroeconomics/' + original_job[k] for k in ('raw_file', 'csv_file') if original_job[k]]
        states[job['source_fields']['status']] += 1
        for payload in job['payloads']:
            observed = macro_payloads.get(payload['path'])
            status = 'present_in_census' if observed else 'not_found_in_census'
            assert payload['status'] == status
            assert payload['observed'] == observed
            presence[status] += 1
    macro = json.loads((RUN / 'MACRO_DATASETS.json').read_text())
    assert dict(states) == macro['job_status_counts_recounted']
    assert dict(presence) == macro['payload_reference_presence']
    assert macro['economic_series'] == list(csv.DictReader(io.StringIO(
        source_contents['macroeconomics/economic_releases/metadata/SERIES_INDEX.csv'].decode())))
    for key in ('older_macro_archive_providers', 'employment_and_yield_extensions',
                'related_research_artifact_directories'):
        for row in macro[key]:
            assert all(row[k] == v for k, v in indexed[row['path']].items()), row['path']
    verified_files = list(summary['files']) + [
        'SUMMARY.json', 'SOURCE_IDENTITY.json', 'DIRECTORY_SUMMARY.jsonl.gz',
        'DIRECTORY_INDEX.json', 'CATALOG_SUMMARY.json', 'IQFEED_DATASETS.json',
        'MACRO_DATASETS.json', 'MACRO_ACQUISITIONS.jsonl.gz', 'EXCLUSIONS.json',
        'METADATA_CATALOG_PATHS.json', 'SOURCE_CATALOG_BINDING.json']
    result = {'status': 'PASS_WITH_RECORDED_FILESYSTEM_EXCLUSIONS' if errors else 'PASS',
              'verified_at_utc': datetime.now(timezone.utc).isoformat(),
              'verifier_sha256': sha(Path(__file__)),
              'artifact_sha256': {name: sha(RUN / name) for name in verified_files},
              'source_catalog_sha256': {p.relative_to(HERE).as_posix(): sha(p)
                  for p in sorted(catalog_dir.iterdir()) if p.is_file()},
              'counts_recomputed': dict(totals), 'unique_paths': len(paths),
              'directory_reads_reconciled': len(reads), 'filesystem_exclusions': errors,
              'directory_summaries_reconciled': len(indexed),
              'iqfeed_families_reconciled': len(iq_totals),
              'macro_acquisitions_compared_to_source_catalog': sum(states.values()),
              'source_catalogs_reconciled_to_census': len(observed_catalogs),
              'macro_acquisition_states_recounted': dict(states),
              'macro_payload_references_reconciled': dict(presence),
              'scope': 'Artifact hashes, unique paths, complete directory scheduling, entry counts, logical byte totals, directory and IQFeed indexes, macro acquisition records and retained source catalogue bytes. Not source payload integrity or gap-free data.'}
    (RUN / 'VERIFICATION.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'filesystem_exclusions'}, indent=2))


if __name__ == '__main__':
    main()
