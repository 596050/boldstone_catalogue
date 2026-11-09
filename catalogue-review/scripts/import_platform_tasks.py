#!/usr/bin/env python3
"""Validate and atomically install dated channel evidence into the local app.

No product decisions, platform listings or catalogue records are changed.
The evidence producer owns its observations; this importer binds them to the
fresh app fields and complete image selections, so subsequent edits go stale.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import tempfile
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from platform_tasks import SCHEMA, fingerprints, validate_snapshot


def bind(evidence, specifications, coverage):
    products = {p['id']: p for p in specifications['products']}
    if set(evidence['products']) - set(products):
        raise ValueError('Evidence names components absent from the active catalogue')
    snapshot = {**evidence, 'schema': SCHEMA,
                'bound_at': datetime.now(timezone.utc).isoformat(),
                'catalogue_revision': specifications['revision'], 'products': {}}
    for pid, entry in evidence['products'].items():
        snapshot['products'][pid] = {**entry,
            'fingerprints': entry.get('fingerprints') or fingerprints(products[pid], coverage['products'][pid])}
    return validate_snapshot(snapshot)


def install(snapshot, target):
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, name = tempfile.mkstemp(prefix='.platform-tasks-', suffix='.json', dir=target.parent)
    try:
        with os.fdopen(fd, 'w') as f:
            json.dump(snapshot, f, ensure_ascii=False, separators=(',', ':'))
            f.write('\n'); f.flush(); os.fsync(f.fileno())
        Path(name).replace(target)
    finally:
        Path(name).unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('evidence', type=Path)
    parser.add_argument('--base-url', default='http://127.0.0.1:8767')
    parser.add_argument('--install', action='store_true')
    parser.add_argument('--target', type=Path, default=Path.home()/'Library/Application Support/BoldstoneReview/platform-tasks.json')
    args = parser.parse_args()
    if args.base_url != 'http://127.0.0.1:8767':
        raise ValueError('Only the local catalogue app is supported')
    def get(path):
        with urllib.request.urlopen(args.base_url+path, timeout=30) as r:
            return json.load(r)
    evidence = json.loads(args.evidence.read_text())
    specs, coverage = get('/api/specifications'), get('/api/coverage')
    snapshot = bind(evidence, specs, coverage)
    if get('/api/specifications')['revision'] != specs['revision']:
        raise RuntimeError('Catalogue changed while binding evidence; regenerate it')
    if args.install:
        install(snapshot, args.target)
    print(json.dumps({'status':'installed' if args.install else 'validated',
                      'products':len(snapshot['products']), 'target':str(args.target) if args.install else None}))


if __name__ == '__main__':
    main()
