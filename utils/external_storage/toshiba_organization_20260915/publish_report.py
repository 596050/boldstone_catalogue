"""Create the final readable catalog and a verified on-drive evidence bundle."""
from collections import Counter, defaultdict
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import tarfile
from organize import HERE, MOUNT, REPO, atomic_json, utc, validate_volume


def sha(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def main():
    validate_volume()
    result = json.loads((HERE / 'reconciliation/RESULT.json').read_text())
    ready = json.loads((HERE / 'DELETION_READINESS.json').read_text())
    maintenance = json.loads((HERE / 'CHECKPOINT_MAINTENANCE.json').read_text()) if (HERE / 'CHECKPOINT_MAINTENANCE.json').exists() else {}
    if result['status'] != 'PASS' or not ready['marketmaker_removed']:
        raise RuntimeError('Final report requires completed reconciliation and authorized empty-root cleanup')
    catalog = defaultdict(Counter)
    for root in ['raw_price_data', 'other_data']:
        with gzip.open(HERE / 'reconciliation' / (root + '.jsonl.gz'), 'rt') as f:
            for line in f:
                row = json.loads(line)
                if row['kind'] != 'file': continue
                key = root + '/' + row['relative'].split('/')[0]
                catalog[key]['files'] += 1
                catalog[key]['bytes'] += row['bytes']
    atomic_json(HERE / 'FINAL_CATALOG.json', {'at_utc': utc(), 'folders': catalog,
        'scope': 'Filesystem files before this migration-evidence bundle was added; no cross-source deduplication'})
    lines = [
        '# Toshiba data organization completed', '',
        f"Verified preservation of **{result['preserved_files_at_move']:,} files / {result['preserved_logical_bytes_at_move']:,} logical bytes**.", '',
        '`/Volumes/Toshiba 2TB/marketmaker` was removed using empty-directory removal only. '
        '`/Volumes/Toshiba 2TB/marketmaker_v2` remains in place; '
        + ('it is empty and ready for removal.' if ready['marketmaker_v2_ready_for_empty_directory_removal'] else 'remaining entries are listed in DELETION_READINESS.json.'), '',
        '**No payload files were deleted.** Local repositories under `/Users/tprice/Developer` remain in place.', '',
        '## Data folders', '', '| Folder | Files | Logical GB |', '| --- | ---: | ---: |',
    ]
    for name, counts in sorted(catalog.items(), key=lambda item: (-item[1]['bytes'], item[0])):
        lines.append(f"| `{name}` | {counts['files']:,} | {counts['bytes']/1e9:.6f} |")
    lines += [
        '', 'Price views and retained project caches may duplicate observations in the raw archives. '
        'Folder totals are non-overlapping physical files, not counts of unique observations.', '',
        '## Preservation evidence', '',
        f"All {result['verified_moves']:,} planned moves have before/after receipts. Final independent traversal found "
        f"{result['missing_final_files']} missing files and {result['missing_final_directories']} missing directories; "
        f"{result['files_changed_after_move']} files changed after their move inventories. "
        f"{result['content_samples_verified']:,} selected content checksums matched.", '',
        f"The original live census differs from the immediate move inventories by "
        f"{result['files_added_before_move']} added files and {result['files_changed_before_move']} changed files; "
        f"{result['missing_initial_files']} original files were missing. See `reconciliation/` for the exact differences.", '',
        result['verification_scope'], '',
        'Archives and disk images remain intact. Their interiors were not all independently enumerated. '
        'OS-managed `.Spotlight-V100` and `.Trashes` were inaccessible and untouched; system folders and manuals remain at the drive root.', '',
        '## Finding original paths', '',
        '`data_paths.json` contains the current physical locations and the exact original-to-current `path_relocations` map. '
        '`PLANNED_FILES.jsonl.gz` and the per-move receipts retain file-level paths. Historical receipt bytes were not rewritten.', '',
        'Use `utils.data_paths.resolve_relocated_path(old_path, require_exists=True)` to resolve an original Toshiba path. '
        'Legacy code that opens literal old paths needs this explicit mapping before it runs.', '',
        '## Concurrent replay incident', '',
        'One active price replay failed when its source directory moved between file reads. Its failure log and partial local outputs were preserved; '
        'no source payload was deleted. The mover was corrected to retain a fence for the full lifetime of an observed reader process. '
        'The original replay remains incomplete, with 87 surviving output files separately hashed in place. '
        'A replacement replay added explicit relocation handling and checkpoints. '
        f"Storage maintenance retained its verified checkpoint at session {maintenance.get('checkpoint', {}).get('stop', 'unknown')}. "
        f"Replacement replay maintenance status: `{maintenance.get('state', 'not recorded')}`. "
        'See `LIVE_READER_INCIDENT.json`, `INTERRUPTED_REPLAY_OUTPUTS.json` and `CHECKPOINT_MAINTENANCE.json`; '
        'no research result is claimed by this storage operation.', '',
        '## Runtime checks and remaining limitations', '',
        'All 981 registered dataset directories were checked against their pre-move availability; no new missing paths were found. '
        'The 29 pre-existing registry status mismatches remain recorded, and the unused `testing_minute_cache` location was absent both before and after. '
        'Frozen specification bytes and their literal price-directory declarations were verified. Standalone imports require the legacy '
        '`ib_gateway` package, which is unavailable in the direct repository import environment; this check does not establish complete runtime readiness. '
        'See `LIVE_PATH_VERIFICATION.json`.', '',
        'The worker-image supervisor was restored with its backing-image path translated. The archived image currently refuses a normal remount '
        'with `Resource temporarily unavailable`; its files remain preserved. No forced detach, filesystem repair, replacement image or lock-file deletion '
        'was used to bypass that failure. See `WORKER_GUARD_STATUS_AFTER.json` and `WORKER_IMAGE_ATTACH_VERBOSE.log`.', '',
        '## Capacity and backup', '',
        f"Drive free space before publishing this evidence bundle: {shutil.disk_usage(MOUNT).free:,} bytes. "
        'Organization retains caches and duplicates, so it does not materially reclaim capacity. '
        'No Hetzner upload or independently restored backup was performed by this operation.', '',
        'The on-drive migration folder contains this report, the final registry, and a compressed copy of the local organization records. '
        'The evidence bundle is metadata and scripts, not a backup of the price payloads.', '',
    ]
    report = HERE / 'FINAL_REPORT.md'
    report.write_text('\n'.join(lines))
    bundle = HERE.parent / 'toshiba_organization_20260915_records.tar.gz'
    if bundle.exists():
        raise FileExistsError('Evidence bundle already exists; retain it and choose a new publication version')
    with tarfile.open(bundle, 'x:gz') as tar:
        tar.add(HERE, arcname=HERE.name, recursive=True)
    destination = MOUNT / 'other_data/migration/toshiba_organization_20260915'
    destination.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(MOUNT).free < bundle.stat().st_size + 64 * 1024**2:
        raise RuntimeError('Insufficient reserve for on-drive metadata bundle; local records remain intact')
    published = []
    for source, name in [(bundle, bundle.name), (report, 'README.md'), (REPO / 'data_paths.json', 'data_paths.json')]:
        target = destination / name
        with source.open('rb') as src, target.open('xb') as dst:
            shutil.copyfileobj(src, dst, length=1024**2)
            dst.flush(); os.fsync(dst.fileno())
        expected = sha(source)
        if sha(target) != expected:
            raise RuntimeError('Published evidence copy failed full SHA256 verification')
        published.append({'source': str(source), 'destination': str(target), 'bytes': source.stat().st_size, 'sha256': expected})
    publication = {'at_utc': utc(), 'status': 'PUBLISHED_AND_FULL_HASH_VERIFIED', 'files': published,
                   'free_external_bytes': shutil.disk_usage(MOUNT).free}
    atomic_json(HERE / 'PUBLICATION.json', publication)
    atomic_json(destination / 'PUBLICATION.json', publication)
    print(json.dumps(publication, indent=2), flush=True)


if __name__ == '__main__': main()
