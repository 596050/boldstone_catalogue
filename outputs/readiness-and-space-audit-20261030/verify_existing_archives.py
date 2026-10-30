"""Read-only byte-for-byte verification of existing test export ZIPs."""
from pathlib import Path
import gzip
import hashlib
import json
import zipfile

ROOT = Path('/Users/tprice/Documents/boldstone')
OUT = Path(__file__).resolve().parent
files = json.load(gzip.open(OUT / 'file-inventory.json.gz', 'rt'))
required = set(json.loads((OUT / 'live-app-required-files.json').read_text()))
opened = {r['path'] for r in json.loads((OUT / 'open-files.json').read_text())}

def sha(stream):
    h = hashlib.sha256()
    for block in iter(lambda: stream.read(2 * 1024 * 1024), b''):
        h.update(block)
    return h.hexdigest()

results = []
for row in files:
    path = ROOT / row['path']
    if not row['path'].startswith('catalogue-review/reviews/') or path.suffix != '.zip':
        continue
    folder = path.with_suffix('')
    if not folder.is_dir():
        continue
    members = {str(p.relative_to(folder)): p for p in folder.rglob('*') if p.is_file()}
    errors = []
    with zipfile.ZipFile(path) as archive:
        names = [n for n in archive.namelist() if not n.endswith('/')]
        if set(names) != set(members) or len(names) != len(set(names)):
            errors.append('File sets differ')
        for name, original in members.items():
            if str(original) in required | opened:
                errors.append('Active dependency: ' + name)
            if original.is_symlink():
                errors.append('Symlink: ' + name)
            if name not in names:
                continue
            with original.open('rb') as stream, archive.open(name) as stored:
                if sha(stream) != sha(stored):
                    errors.append('Bytes differ: ' + name)
    results.append({'directory': str(folder.relative_to(ROOT)), 'archive': str(path.relative_to(ROOT)),
                    'status': 'PASS_BYTE_IDENTICAL_ARCHIVE' if not errors else 'NEEDS_REVIEW',
                    'files': len(members),
                    'allocated_bytes': sum(p.stat().st_blocks * 512 for p in members.values()),
                    'archive_bytes': path.stat().st_size, 'errors': errors})
summary = {'status': 'READ_ONLY_NO_DELETION', 'verified_directories': sum(r['status'].startswith('PASS') for r in results),
           'allocated_candidate_bytes': sum(r['allocated_bytes'] for r in results if r['status'].startswith('PASS')),
           'results': results,
           'qualification': 'Retain the existing verified ZIPs. Only extracted historical test exports are candidates. Restore from ZIP to reopen old export paths. Allocation is not guaranteed private APFS storage.'}
(OUT / 'verified-test-export-candidates.json').write_text(json.dumps(summary, indent=2))
print(json.dumps(summary, indent=2))
