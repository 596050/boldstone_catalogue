"""One-off, audited source binding update for the exact White/Black retirement."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import json
import os
import sys

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[2]
sys.path.insert(0, str(PROJECT / 'catalogue-review'))
from store import ReviewStore

sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
read = lambda p: json.loads(Path(p).read_text())


def run(data_dir, apply=False, staged_qa=False):
    delta = read(PROJECT / 'sculpture-catalogue/components/reconciliation/acanthus-white-black-retirement-2026-10-26/SOURCE_READY_FOR_APP_REBASE.json')
    retired = delta['option_id']
    assert retired == 'BSI-B0D0CCA7E318'
    old, new = read(delta['old_register_path']), read(delta['new_register_path'])
    assert sha(delta['old_register_path']) == delta['old_register_sha256']
    assert sha(delta['new_register_path']) == delta['new_register_sha256']
    assert set(old['active_option_ids']) - set(new['active_option_ids']) == {retired}
    assert not set(new['active_option_ids']) - set(old['active_option_ids'])
    before = {p['product_id']: p for p in old['options']}
    after = {p['product_id']: p for p in new['options']}
    assert len(new['active_option_ids']) == 187
    assert all(before[pid] == after[pid] for pid in new['active_option_ids'])
    assert old['original_review_specification_assertions'] == new['original_review_specification_assertions']
    assert sha(delta['unchanged_gallery_database']) == delta['unchanged_gallery_sha256']
    pointer = read(PROJECT / 'sculpture-catalogue/current-master.json')
    if apply and not staged_qa:
        assert pointer['register_sha256'] == delta['new_register_sha256'], 'New catalogue must be published first'
        gallery = (PROJECT / 'sculpture-catalogue' / pointer['current_published_gallery_projection']['path']).parent / 'complete-image-platform-register.sqlite'
        assert sha(gallery) == delta['unchanged_gallery_sha256']
        pid_path = Path(data_dir) / 'server.pid'
        if pid_path.exists():
            try:
                os.kill(int(pid_path.read_text()), 0)
            except ProcessLookupError:
                pass
            else:
                raise RuntimeError('Stop production server before the atomic rebase')
    if staged_qa:
        assert Path(data_dir).resolve() == HERE / 'qa-state', 'QA mode only accepts this isolated copy'
    store = ReviewStore(data_dir)
    snapshot = store.snapshot()
    old_hash, new_hash = delta['old_register_sha256'], delta['new_register_sha256']
    keys = lambda r: (r['kind'], r['product_id'], r['item_id'])
    retained = [r for r in snapshot['reviews'] if r['product_id'] not in new['active_option_ids'] and r['product_id'] not in ('', '__library__')]
    candidates = [r for r in snapshot['reviews'] if r not in retained]
    assert all(r['source_hash'] in (old_hash, new_hash) for r in candidates), 'Unexpected review source needs separate reconciliation'
    rows = [r for r in candidates if r['source_hash'] == old_hash]
    result = {'at': datetime.now(timezone.utc).isoformat(), 'apply': apply, 'staged_qa': staged_qa,
              'retired_product': retired, 'old_source_hash': old_hash, 'new_source_hash': new_hash,
              'unchanged_active_options': 187, 'reviews_to_rebind': len(rows), 'historical_rows_preserved': len(retained),
              'event_cutoff_before': snapshot['event_cutoff'], 'data_directory': str(data_dir)}
    if apply:
        store.backup(HERE / ('qa-before-rebase.sqlite3' if staged_qa else 'before-retirement-rebase.sqlite3'))
        with store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            assert db.execute('SELECT COALESCE(MAX(id),0) FROM events').fetchone()[0] == snapshot['event_cutoff'], 'A concurrent review was saved; retry from a fresh snapshot'
            for row in rows:
                store._write(db, row['kind'], row['product_id'], row['item_id'], row['data'], row['version'],
                             new_hash, row['original'], row)
        later = store.snapshot()
        a = {keys(r): r for r in later['reviews']}
        assert len(a) == len(snapshot['reviews'])
        changed = {keys(r) for r in rows}
        for row in snapshot['reviews']:
            current = a[keys(row)]
            assert current['data'] == row['data'] and current['original'] == row['original']
            if keys(row) in changed:
                assert current['version'] == row['version'] and current['source_hash'] == new_hash
            else:
                assert current == row
        result.update(event_cutoff_after=later['event_cutoff'], all_review_values_preserved=True, review_versions_preserved=True,
                      changed_keys=[list(keys(r)) for r in rows], historical_keys=[list(keys(r)) for r in retained])
    name = ('qa-' if staged_qa else '') + ('retirement-rebase.json' if apply else 'retirement-rebase-plan.json')
    (HERE / name).write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('changed_keys','historical_keys')}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--staged-qa', action='store_true')
    args = parser.parse_args()
    run(HERE / 'qa-state' if args.staged_qa else Path.home() / 'Library/Application Support/BoldstoneReview', args.apply, args.staged_qa)
