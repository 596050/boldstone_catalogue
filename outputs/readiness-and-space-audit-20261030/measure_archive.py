"""Measure lossless compression of historical review databases without writing archives."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import gzip
import hashlib
import json
import time
import zlib

ROOT = Path('/Users/tprice/Documents/boldstone')
OUT = Path(__file__).resolve().parent
files = json.load(gzip.open(OUT / 'file-inventory.json.gz', 'rt'))
required = set(json.loads((OUT / 'live-app-required-files.json').read_text()))
opened = {r['path'] for r in json.loads((OUT / 'open-files.json').read_text())}
rows = [f for f in files if f['path'].endswith('.sqlite3') and str(ROOT / f['path']) not in required | opened]

def measure(row):
    p = ROOT / row['path']
    before = p.stat()
    compressor = zlib.compressobj(level=6, wbits=31)
    n = 0
    h = hashlib.sha256()
    with p.open('rb') as stream:
        for block in iter(lambda: stream.read(2 * 1024 * 1024), b''):
            h.update(block)
            n += len(compressor.compress(block))
    n += len(compressor.flush())
    after = p.stat()
    if (before.st_size, before.st_mtime_ns, before.st_ino) != (after.st_size, after.st_mtime_ns, after.st_ino):
        return {**row, 'error': 'Changed during measurement'}
    return {**row, 'sha256': h.hexdigest(), 'gzip_bytes': n, 'potential_byte_reduction': row['allocated'] - ((n + 4095) // 4096 * 4096)}

results = []
last = time.monotonic()
with ThreadPoolExecutor(max_workers=2) as pool:
    for future in as_completed([pool.submit(measure, r) for r in rows]):
        results.append(future.result())
        if time.monotonic() - last > 15:
            print(f'Measured {len(results)}/{len(rows)} historical database copies', flush=True)
            last = time.monotonic()
good = [r for r in results if 'error' not in r]
summary = {'status': 'READ_ONLY_COMPRESSION_MEASUREMENT', 'files': len(good),
           'allocated_bytes': sum(r['allocated'] for r in good),
           'compressed_bytes': sum(r['gzip_bytes'] for r in good),
           'potential_byte_reduction': sum(r['potential_byte_reduction'] for r in good),
           'errors': [r for r in results if 'error' in r],
           'qualification': 'Historical copies only; active app database lives outside this directory. No archive created or original removed. Restore verification and link-preserving access are required before retirement. This overlaps the duplicate total and must not be added to it.'}
(OUT / 'database-archive-candidates.json').write_text(json.dumps(results, indent=2))
(OUT / 'database-archive-summary.json').write_text(json.dumps(summary, indent=2))
print(json.dumps(summary), flush=True)
