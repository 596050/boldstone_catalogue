"""Read all retained records and verify the v2 projection without review writes."""
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import sqlite3
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from catalogue import Catalogue, digest
from projection import Projection


project = Path(__file__).resolve().parents[2]
data = Path.home() / 'Library/Application Support/BoldstoneReview'
cat = Catalogue(project, data)
view = Projection(cat, [])
checks = 0


def check(yes, message):
    global checks
    if not yes:
        raise AssertionError(message)
    checks += 1


def file_identity(path):
    outer = hashlib.sha256()
    with Path(path).open('rb') as f:
        while True:
            block = f.read(4194304)
            if not block:
                break
            outer.update(hashlib.sha256(block).digest())
    return outer.hexdigest()


for pid, edges in cat.edges.items():
    projected = view.edges[pid]
    restored = {aid for edge in projected.values() for aid in edge['source_asset_ids']}
    check(restored == set(edges), 'An original product/image relationship was lost')
    for aid, edge in edges.items():
        canonical = cat.canonical_assets[aid]
        check(canonical in projected, 'A source image disappeared')
        for qualification in edge.get('qualifications', []):
            check(qualification in projected[canonical]['qualifications'], 'A source qualification was lost')
for group in cat.duplicate_groups:
    members = group['member_ids']
    if any(cat.assets[x]['source'] == 'Dropbox' for x in members):
        check(cat.assets[group['canonical_id']]['source'] == 'Dropbox', 'Dropbox was not preferred')
    for aid in members:
        asset = cat.assets[aid]
        if asset['source'] != 'Dropbox':
            check(file_identity(cat.paths[aid][0]) == group['hash'], 'A platform copy has unequal bytes')
        else:
            check(asset['original']['dropbox_content_hash'] == group['hash'], 'Dropbox hash differs')
check(len(view.library()) == len(cat.assets) - cat.source['dedupe']['hidden_records'], 'Wrong unique library count')
current = [a for a in cat.assets.values() if a['source'] == 'Dropbox' and a['inventory_status'] == 'CURRENT_NATIVE_FILE_AND_ACTUAL_PARENT_VERIFIED']
for a in current:
    check(a['original'].get('bytes', 0) > 0, 'A current original has no size')
    check(a['local_preview'], 'A current original has no preview')
    if a['original']['dimensions']:
        check(a['original']['dimension_basis'] != 'Original pixel dimensions not available locally', 'Unqualified original dimensions')
check(digest(cat.source['register']) == cat.source['register_sha256'], 'Canonical register changed')
check(digest(cat.source['gallery_database']) == cat.source['gallery_sha256'], 'Source gallery changed')
with sqlite3.connect('file:' + str(data / 'reviews.sqlite3') + '?mode=ro', uri=True) as db:
    review_count = db.execute('select count(*) from reviews').fetchone()[0]
report = {'status': 'PASS', 'checked_utc': datetime.now(timezone.utc).isoformat(), 'checks': checks,
          'products': len(cat.products), 'source_records': len(cat.assets), 'unique_images': len(view.library()),
          'current_dropbox_files': len(current), 'current_dropbox_files_with_original_bytes': len(current),
          'current_dropbox_files_with_original_dimensions': sum(bool(a['original']['dimensions']) for a in current),
          'raw_associations_preserved': sum(len(x) for x in cat.edges.values()),
          'deduplicated_associations': sum(len(x) for x in view.edges.values()),
          'dedupe': cat.source['dedupe'], 'source_counts': dict(Counter(a['source'] for a in cat.assets.values())),
          'real_review_records': review_count, 'review_writes': 0, 'source': cat.source}
out = Path.home() / 'Library/Application Support/BoldstoneReview-QA-v2-20261025/qa/catalogue-v2-audit.json'
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(report, indent=2))
print(json.dumps(report))
