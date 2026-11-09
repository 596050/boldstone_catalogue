"""Retain fresh read-only copies of the known economic source catalogues."""
import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]


def sha(content):
    return hashlib.sha256(content).hexdigest()


def metadata(st):
    return st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--run-id', required=True)
    args = ap.parse_args()
    if Path(args.run_id).name != args.run_id:
        raise SystemExit('run-id must be a directory name')
    run = HERE / args.run_id
    identity = json.loads((run / 'SOURCE_IDENTITY.json').read_text())
    root = Path(identity['mount'])
    if not os.path.ismount(root) or root.stat().st_dev != identity['device']:
        raise SystemExit('The source mount changed')
    out = run / 'source_catalogs'
    out.mkdir(exist_ok=False)
    paths = [r['external_path'] for r in json.loads((HERE / 'source_catalogs/RECEIPTS.json').read_text())]
    receipts = []
    for rel in paths:
        if Path(rel).is_absolute() or '..' in Path(rel).parts:
            raise ValueError('Unsafe source path')
        source = root / rel
        row = {'external_path': rel, 'observed_at_utc': datetime.now(timezone.utc).isoformat()}
        try:
            before = source.stat()
            if before.st_size > 64 * 1024 * 1024:
                raise ValueError('Catalogue exceeds the 64 MiB metadata-copy bound')
            with source.open('rb') as f:
                content = f.read(64 * 1024 * 1024 + 1)
                after_fd = os.fstat(f.fileno())
            after = source.stat()
            stable = metadata(before) == metadata(after_fd) == metadata(after) and len(content) == before.st_size
            target = out / (rel.replace('/', '__') + '.gz')
            compressed = gzip.compress(content, mtime=0)
            target.write_bytes(compressed)
            row.update(local_path=target.relative_to(REPO).as_posix(), bytes=len(content),
                       source_sha256=sha(content), compressed_sha256=sha(compressed),
                       source_mtime_ns=before.st_mtime_ns, source_inode=before.st_ino,
                       stable_during_copy=stable)
            if not stable:
                row['error'] = 'Source changed during read; retained copy is not admitted as stable'
        except (OSError, ValueError) as exc:
            row['error'] = f'{type(exc).__name__}: {exc}'
        receipts.append(row)
        (out / 'RECEIPTS.json').write_text(json.dumps(receipts, indent=2) + '\n')
        print(json.dumps(row), flush=True)
    if any('error' in r for r in receipts):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
