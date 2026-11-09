"""Publish a verified census report and atomically select it for offline queries."""
import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--run-id', required=True)
    args = ap.parse_args()
    if Path(args.run_id).name != args.run_id:
        raise SystemExit('run-id must be a directory name')
    run = HERE / args.run_id
    read = lambda name: json.loads((run / name).read_text())
    verification = read('VERIFICATION.json')
    if verification['status'] not in ('PASS', 'PASS_WITH_RECORDED_FILESYSTEM_EXCLUSIONS'):
        raise SystemExit('The census has not passed verification')
    if verification['verifier_sha256'] != sha(HERE / 'verify.py'):
        raise SystemExit('The verifier changed after verification')
    for name, expected in verification['artifact_sha256'].items():
        if sha(run / name) != expected:
            raise SystemExit(f'Artifact changed after verification: {name}')
    for name, expected in verification['source_catalog_sha256'].items():
        if sha(HERE / name) != expected:
            raise SystemExit(f'Source catalogue copy changed after verification: {name}')
    summary, catalog, iq, macro, exclusions = [read(name) for name in (
        'SUMMARY.json', 'CATALOG_SUMMARY.json', 'IQFEED_DATASETS.json',
        'MACRO_DATASETS.json', 'EXCLUSIONS.json')]
    with gzip.open(run / 'DIRECTORY_SUMMARY.jsonl.gz', 'rt') as f:
        dirs = {r['path']: r for r in map(json.loads, f)}
    if summary['exception'] or summary['pending_directories'] or not summary['identity_unchanged']:
        raise SystemExit('The census is incomplete or its device identity changed')
    before = (HERE / 'README.md').read_bytes()
    identity = read('SOURCE_IDENTITY.json')['storage_identity']
    link = lambda label, name: f'[{label}]({args.run_id}/{name})'
    report_date = datetime.fromisoformat(summary['finished_at_utc'])
    lines = [
        f'# Toshiba data manifest — {report_date.day} {report_date:%B %Y}', '',
        f"The latest verified census is **{args.run_id}**: **{summary['totals']['files']:,} files**, "
        f"**{summary['totals']['directories']:,} directories** below the volume root, and "
        f"**{summary['totals']['file_bytes']:,} logical bytes** "
        f"({summary['totals']['file_bytes'] / 10**12:.3f} TB decimal).",
        f"It read `/Volumes/Toshiba 2TB` from **{summary['started_at_utc']}** to "
        f"**{summary['finished_at_utc']}**. Every reachable directory was attempted. "
        'This is a live, non-atomic census; it cannot include subsequent filesystem changes.', '',
        f"The registered volume UUID `{identity['volume_uuid']}` and storage identity "
        f"(USB serial `{identity['usb_serial']}`) matched before and after the scan. The manifest process only read "
        'the Toshiba; its outputs are in this repository. Other jobs could write during the scan.', '',
        '## Files to use', '',
        '- ' + link('Full file manifest', 'FILES.jsonl.gz') + ': one JSON record per file, including hidden, '
        'empty and partial files. Paths are relative to the mount. Records retain logical size, '
        'modification/change times in epoch nanoseconds, observation time, device and inode.',
        '- ' + link('Directory summary', 'DIRECTORY_SUMMARY.jsonl.gz') + ' and ' +
        link('directory index', 'DIRECTORY_INDEX.json') + ': counts, logical sizes and read errors.',
        '- ' + link('IQFeed datasets and filename symbol lists', 'IQFEED_DATASETS.json') + '.',
        '- ' + link('Macroeconomic datasets', 'MACRO_DATASETS.json') + ' and ' +
        link('individual acquisition records', 'MACRO_ACQUISITIONS.jsonl.gz') + '.',
        '- ' + link('Exclusions', 'EXCLUSIONS.json') + ', ' + link('scan summary and hashes', 'SUMMARY.json') +
        ', and ' + link('independent verification', 'VERIFICATION.json') + '.', '',
        'The following filename-based categories partition the observed files. They include associated '
        'metadata and research artifacts; they are not counts of unique source observations.', '',
        '| Category | Files | Logical GB |', '| --- | ---: | ---: |',
    ]
    for name, row in sorted(catalog['categories'].items()):
        lines.append(f"| `{name}` | {row['files']:,} | {row['bytes'] / 10**9:.3f} |")
    lines += ['', '## IQFeed coverage', '',
        f"The main `marketmaker/iqfeed_archive` tree contains **{dirs['marketmaker/iqfeed_archive']['files']:,} "
        f"files** and **{dirs['marketmaker/iqfeed_archive']['bytes'] / 10**9:.3f} logical GB**. "
        'Its family counts include metadata where present. Plain CSV filename stems do not certify '
        'ticker identity, valid rows or continuous date coverage.', '',
        '| Archive family | Files | Logical GB | Plain CSV filename stems |',
        '| --- | ---: | ---: | ---: |']
    for name, row in iq['datasets'].items():
        lines.append(f"| `{name.rsplit('/', 1)[-1]}` | {row['files']:,} | "
                     f"{row['bytes'] / 10**9:.3f} | {row['symbol_name_count']:,} |")
    direct_files = dirs['marketmaker/iqfeed_archive']['files'] - sum(r['files'] for r in iq['datasets'].values())
    direct_bytes = dirs['marketmaker/iqfeed_archive']['bytes'] - sum(r['bytes'] for r in iq['datasets'].values())
    lines += [f'| Files directly in the archive root | {direct_files:,} | {direct_bytes / 10**9:.6f} | — |', '']
    frozen = dirs['marketmaker/data/ibkr/iqfeed_192_daily']
    lines += [f"The separate frozen daily source `marketmaker/data/ibkr/iqfeed_192_daily` contains "
        f"**{frozen['files']:,} files**, totalling **{frozen['bytes']:,} bytes**. "
        'Other IQFeed-named source, replay and research directories are listed in the IQFeed index. '
        'Different paths do not establish independent canonical datasets.', '',
        '## Macroeconomic coverage', '', '| Root | Files | Logical GB |', '| --- | ---: | ---: |']
    for name in ('macroeconomics', 'marketmaker/macro_archive'):
        row = dirs[name]
        lines.append(f"| `{name}` | {row['files']:,} | {row['bytes'] / 10**9:.3f} |")
    lines += ['', 'The IQFeed macro source catalogue includes commodities, Treasury futures, Fed Funds/SOFR '
        'futures, published rates, currencies, volatility and market breadth. Configured instruments '
        'are not necessarily acquired instruments. Retained acquisition outcomes are:', '',
        '| Acquisition status | Jobs |', '| --- | ---: |']
    for name, count in macro['job_status_counts_recounted'].items():
        lines.append(f'| `{name}` | {count:,} |')
    present = macro['payload_reference_presence'].get('present_in_census', 0)
    missing = macro['payload_reference_presence'].get('not_found_in_census', 0)
    lines += ['', f"**{present:,} payload references were present** and **{missing:,} were missing** in the census. "
        f"All **{catalog['source_catalogs']} source catalogues** were freshly copied, SHA-256 hashed, "
        'checked for stability while copied and reconciled to the census size and modification time. '
        'Their compressed copies are in ' + link('source_catalogs/', 'source_catalogs/') + '. '
        'Acquisition payload checksums remain historical declarations; large payloads were not rehashed.', '',
        'The original economic-release catalogue declares the following series and observation endpoints. '
        'These are source dates, not file timestamps or a new certification of historical release availability.', '',
        '| Series | Description | Frequency | Adjustment | First observation | Last observation |',
        '| --- | --- | --- | --- | --- | --- |']
    for row in macro['economic_series']:
        lines.append('| ' + ' | '.join('`' + row[k] + '`' if k == 'series_id' else row[k]
            for k in ('series_id', 'description', 'frequency', 'adjustment', 'first_observation', 'last_observation')) + ' |')
    lines += ['', 'Employment and yield extensions also present:', '',
        '| Series directory | Files | Logical bytes |', '| --- | ---: | ---: |']
    for row in macro['employment_and_yield_extensions']:
        lines.append(f"| `{row['series_from_directory_name']}` | {row['files']:,} | {row['bytes']:,} |")
    lines += ['', 'The archive retains ALFRED vintage evidence and separate source/local clocks. '
        'Vintage-interval rows are not unique observations. Consensus expectations and certified intraday '
        'release/calendar completeness remain unavailable as described in the preserved source status.', '',
        'The older macro archive is included at file level:', '',
        '| Provider directory | Files | Logical GB |', '| --- | ---: | ---: |']
    for row in macro['older_macro_archive_providers']:
        lines.append(f"| `{row['path'].rsplit('/', 1)[-1]}` | {row['files']:,} | {row['bytes'] / 10**9:.3f} |")
    lines += ['', '## Other areas included', '',
        'All reachable file trees are included: IBKR/IG/Yahoo data, ADR/home-market/FX quotes, research '
        'inputs and results, retained models and execution evidence, runtime files, downloads, caches '
        'and sparsebundle bands. The following selected trees do not overlap with one another; '
        'the detailed directory index also contains parents and their children.', '',
        '| Other directory | Files | Logical GB |', '| --- | ---: | ---: |']
    for name in ('marketmaker/data', 'marketmaker/research', 'marketmaker/research_runtime_offload',
                 'marketmaker/recoverable_build_caches', 'marketmaker_v2'):
        if name in dirs:
            row = dirs[name]
            lines.append(f"| `{name}` | {row['files']:,} | {row['bytes'] / 10**9:.3f} |")
    lines += ['', '## What is left out or not verified', '']
    for err in exclusions['filesystem_errors']:
        lines.append(f"- Contents below `{err['path']}`: `{err['error_type']}` during `{err['operation']}`. "
                     'The entry is recorded, but its interior files and size are unknown.')
    lines += [
        '- Members inside ZIP/TAR/other containers and filesystems inside disk images or sparsebundles. '
        'The containers and accessible band files themselves are included.',
        '- Internal tables, workbook sheets and array variables inside databases, workbooks and binary datasets.',
        '- Extended attributes, ACLs, resource forks, deleted/unallocated data, other devices and link targets.',
        '- Full payload checksums, row-level validity, interior date/bar completeness and independent '
        'economic interpretation outside the retained catalogues. This is not a complete backup or trading-input certification.',
        '- Physical allocation is generally unmeasured. `allocated_bytes: null` means unknown. '
        'Logical sizes are not occupied filesystem space or potential cleanup savings.', '',
        f"The census retains **{summary['totals']['zero_byte_files']:,} zero-byte files** and "
        f"**{summary['totals']['partial_or_temporary_files']:,} files with incomplete/temporary names**. "
        'These classifications do not establish that files are disposable. '
        f"**{summary['totals']['directories_changed_during_listing']:,} directories** were observed changing "
        'during their own listing. The entire volume was not frozen.', '',
    ]
    if (run / 'CHANGES_SUMMARY.json').exists():
        changes = read('CHANGES_SUMMARY.json')
        lines += ['## Changes from the previous census', '',
            f"Compared with `{changes['previous']}`, the file metadata comparison found:", '',
            '| Observation | Files |', '| --- | ---: |']
        for name, count in changes['counts'].items():
            lines.append(f'| `{name}` | {count:,} |')
        lines += ['', changes['qualification'], '', link('Comparison and bound manifest hashes', 'CHANGES_SUMMARY.json') + '.', '']
    lines += ['## Search without Toshiba connected', '', 'Run from the repository root:', '', '```bash',
        'python3 research/utility/toshiba_data_manifest_20260913_v1/query.py --prefix marketmaker/iqfeed_archive/minute/ --summary',
        'python3 research/utility/toshiba_data_manifest_20260913_v1/query.py --contains /DGS10/ --limit 5',
        'python3 research/utility/toshiba_data_manifest_20260913_v1/query.py --directories --prefix marketmaker/macro_archive/',
        '```', '', f'`LATEST.json` selects `{args.run_id}`. Use `--run-id run_04` or `--run-id run_03` for retained earlier censuses.', '',
        f"Independent verification re-read all manifest streams, checked their hashes and all "
        f"**{verification['unique_paths']:,} unique entry paths**, reconciled every directory's child counts "
        'and logical byte totals, checked the directory/IQFeed indexes, and compared macro acquisition records '
        'with the preserved source catalogue. It passed with the recorded filesystem exclusions.', '']
    report = '\n'.join(lines)
    (run / 'REPORT.md').write_text(report.replace(f']({args.run_id}/', ']('))
    if (HERE / 'README.md').read_bytes() != before:
        raise SystemExit('README changed concurrently; per-run report retained, latest pointer not changed')
    (run / 'README_BEFORE_PUBLICATION.md').write_bytes(before)
    (HERE / 'README.md').write_text(report)
    latest = {'schema': 'marketmaker.external_file_manifest.latest.v1', 'run_id': args.run_id,
        'scan_started_at_utc': summary['started_at_utc'], 'scan_finished_at_utc': summary['finished_at_utc'],
        'published_at_utc': datetime.now(timezone.utc).isoformat(), 'verification_status': verification['status'],
        'manifest_sha256': sha(run / 'FILES.jsonl.gz'), 'summary_sha256': sha(run / 'SUMMARY.json'),
        'verification_sha256': sha(run / 'VERIFICATION.json'), 'report_sha256': sha(HERE / 'README.md'),
        'atomic_snapshot': False}
    temp = HERE / 'LATEST.json.tmp'
    temp.write_text(json.dumps(latest, indent=2) + '\n')
    os.replace(temp, HERE / 'LATEST.json')
    print(json.dumps(latest, indent=2))


if __name__ == '__main__':
    main()
