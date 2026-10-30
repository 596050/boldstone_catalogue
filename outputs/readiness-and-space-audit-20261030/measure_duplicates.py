"""Read-only, byte-exact duplicate audit. Does not remove or replace files."""
from pathlib import Path
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import gzip
import hashlib
import json
import time

ROOT = Path('/Users/tprice/Documents/boldstone')
OUT = Path(__file__).resolve().parent
files = json.load(gzip.open(OUT / 'file-inventory.json.gz', 'rt'))
sizes = Counter(f['bytes'] for f in files if f['bytes'] >= 65536)
candidates = [f for f in files if f['bytes'] >= 65536 and sizes[f['bytes']] > 1]
required = set(json.loads((OUT / 'live-app-required-files.json').read_text()))

def check(row):
    path = ROOT / row['path']
    before = path.stat()
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(2 * 1024 * 1024), b''):
            h.update(chunk)
    after = path.stat()
    if (before.st_size, before.st_mtime_ns, before.st_ino) != (after.st_size, after.st_mtime_ns, after.st_ino):
        return {'path': row['path'], 'error': 'Changed during read'}
    return {**row, 'sha256': h.hexdigest(), 'app_required': str(path) in required}

groups = defaultdict(list)
errors = []
last = time.monotonic()
with ThreadPoolExecutor(max_workers=2) as pool:
    futures = [pool.submit(check, f) for f in candidates]
    for i, future in enumerate(as_completed(futures), 1):
        try:
            row = future.result()
        except OSError as e:
            errors.append(str(e))
            continue
        if 'error' in row:
            errors.append(row)
        else:
            groups[(row['bytes'], row['sha256'])].append(row)
        if time.monotonic() - last > 15:
            print(f'Hashed {i}/{len(candidates)} candidate files', flush=True)
            last = time.monotonic()

duplicates = []
for (size, digest), rows in groups.items():
    if len(rows) < 2:
        continue
    # A proposed keeper for reporting only. Paths may still be referenced by
    # historical reports; this is not a permission or instruction to delete.
    rows.sort(key=lambda r: (not r['app_required'], '/inputs/' in r['path'], r['path'].endswith('.before'), len(r['path']), r['path']))
    duplicates.append({'sha256': digest, 'bytes_each': size, 'files': rows,
                       'duplicate_allocated_bytes': sum(r['allocated'] for r in rows[1:])})
duplicates.sort(key=lambda g: g['duplicate_allocated_bytes'], reverse=True)
with gzip.open(OUT / 'exact-duplicates.json.gz', 'wt') as stream:
    json.dump(duplicates, stream, separators=(',', ':'))
summary = {'status': 'READ_ONLY', 'candidate_files_hashed': len(candidates),
           'groups': len(duplicates), 'duplicate_files': sum(len(g['files']) - 1 for g in duplicates),
           'duplicate_allocated_bytes': sum(g['duplicate_allocated_bytes'] for g in duplicates),
           'errors': errors,
           'qualification': 'Allocated blocks include possible APFS shared extents. Duplicate paths may be used by historical reports. No deletion or deduplication was applied.'}
(OUT / 'duplicates-summary.json').write_text(json.dumps(summary, indent=2))
print(json.dumps(summary), flush=True)
