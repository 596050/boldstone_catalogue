"""Re-read timed-out directories and retain a separate complete planning census."""
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import organize

HERE = Path(__file__).resolve().parent
ORIGINAL = HERE.parents[2] / 'research/utility/toshiba_data_manifest_20260913_v1/run_07_pre_organization_20260915'


def main():
    organize.validate_volume()
    errors = [json.loads(line) for line in gzip.open(ORIGINAL / 'ERRORS.jsonl.gz', 'rt')]
    paths = sorted({e['path'] for e in errors if e['path'].startswith(('marketmaker/', 'marketmaker_v2/', 'macroeconomics/'))})
    repairs = []
    for path in paths:
        name = hashlib.sha256(path.encode()).hexdigest()[:20]
        output = HERE / 'repairs' / (name + '.jsonl.gz')
        print(json.dumps({'repairing': path, 'at_utc': organize.utc()}), flush=True)
        result = organize.inventory(organize.safe_path(path), output, sample_limit=0)
        record = {'source': path, **result}
        organize.atomic_json(output.with_suffix('.summary.json'), record)
        repairs.append(record)
        organize.atomic_json(HERE / 'REPAIRS.json', repairs)
    out = HERE / 'census_repaired'
    out.mkdir(exist_ok=True)
    counts = {'file': 0, 'directory': 0, 'bytes': 0, 'zero_byte_files': 0}
    streams = {k: gzip.open(out / n, 'wt', compresslevel=3) for k, n in {
        'file': 'FILES.jsonl.gz', 'directory': 'DIRECTORIES.jsonl.gz', 'other': 'OTHER_ENTRIES.jsonl.gz'}.items()}
    def emit(row):
        kind = row['kind']
        streams[kind if kind in streams else 'other'].write(json.dumps(row, separators=(',', ':')) + '\n')
        if kind in counts: counts[kind] += 1
        if kind == 'file':
            counts['bytes'] += row['bytes']
            counts['zero_byte_files'] += row['bytes'] == 0
    try:
        for filename in ['FILES.jsonl.gz', 'DIRECTORIES.jsonl.gz', 'OTHER_ENTRIES.jsonl.gz']:
            with gzip.open(ORIGINAL / filename, 'rt') as f:
                for line in f:
                    row = json.loads(line)
                    # Keep the original root-directory entry; replace all descendants.
                    if any(row['path'].startswith(p + '/') for p in paths): continue
                    emit(row)
        for repair in repairs:
            with gzip.open(repair['inventory'], 'rt') as f:
                for line in f:
                    row = json.loads(line)
                    result = {'path': repair['source'] + '/' + row['relative'], 'kind': row['kind'],
                              'bytes': row.get('bytes', 0), 'mtime_ns': row.get('mtime_ns'),
                              'ctime_ns': None, 'inode': row.get('inode'), 'observed_at_utc': repair['at_utc'],
                              'metadata_method': 'getattrlistbulk_no_empty_file_id_normalization',
                              'repair_receipt': str(Path(repair['inventory']).relative_to(HERE)),
                              'payload_hash_status': 'NOT_READ_BY_METADATA_CENSUS'}
                    if 'link_target' in row: result['link_target'] = row['link_target']
                    emit(result)
    finally:
        for f in streams.values(): f.close()
    shutil.copyfile(ORIGINAL / 'SOURCE_IDENTITY.json', out / 'SOURCE_IDENTITY.json')
    summary = {'status': 'COMPLETE_FOR_AUTHORIZED_TREES', 'at_utc': organize.utc(), 'counts': counts,
               'atomic_snapshot': False, 'original_census': str(ORIGINAL), 'repaired_directories': paths,
               'unreadable_system_directories': ['.Spotlight-V100', '.Trashes'],
               'container_interiors_enumerated': False, 'full_payload_hashes_computed': False}
    organize.atomic_json(out / 'SUMMARY.json', summary)
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == '__main__': main()
