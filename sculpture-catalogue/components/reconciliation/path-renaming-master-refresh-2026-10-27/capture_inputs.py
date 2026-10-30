"""Capture an immutable catalogue publication cut; read-only app/Dropbox access."""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import sqlite3
import urllib.request

HERE = Path(__file__).resolve().parent
BASE = HERE.parents[2]
ROOT = BASE.parent
sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
read = lambda path: json.loads(Path(path).read_text())
now = datetime.now(timezone.utc)
cut = HERE / 'inputs' / now.strftime('%Y%m%dT%H%M%S%fZ')
cut.mkdir(parents=True)
manifest = {'recorded_utc': now.isoformat(), 'input_directory': str(cut), 'sources': {}}


def capture(key, path, name=None):
    path = Path(path).resolve()
    target = cut / (name or path.name)
    target.write_bytes(path.read_bytes())
    manifest['sources'][key] = {'path': str(path), 'snapshot': str(target), 'sha256': sha(target)}
    return read(target) if target.suffix == '.json' else target


pointer_path = BASE / 'current-master.json'
pointer_sha = sha(pointer_path)
pointer = capture('pointer', pointer_path)
assert pointer_sha == manifest['sources']['pointer']['sha256']
register = capture('register', BASE / pointer['register'], 'register.json')
assert manifest['sources']['register']['sha256'] == pointer['register_sha256']
capture('core_workbook', BASE / pointer['workbook'], 'core-source.xlsx')
capture('comprehensive_workbook', BASE / pointer['preferred_review_workbook'], 'unified-source.xlsx')
for key, path in [('specification_control', BASE / 'components/reviews/specification_review_progress.json'),
                  ('component_checkpoint', BASE / 'components/checkpoint.json'),
                  ('root_checkpoint', BASE / 'checkpoint.json')]:
    value = capture(key, path, key + '.json')
    assert value['current_master_catalogue'] == pointer
native_root = Path('/Users/tprice/BoldstoneMigration/path-renaming-20261026')
completion = capture('native_completion', native_root / 'completion.json', 'native-completion.json')
assert completion['state'] == 'completed'
verification = capture('native_verification', completion['verification'], 'native-verification.json')
assert manifest['sources']['native_verification']['sha256'] == completion['verification_sha256']
assert verification['status'] == 'PASS' and not verification['errors']
completed_paths = capture('completed_filename_paths', completion['current_filename_paths'], 'completed-filename-paths.json')
assert manifest['sources']['completed_filename_paths']['sha256'] == completion['current_filename_paths_sha256']
capture('completed_native_census', verification['native_final'], 'completed-native-census.json')
with urllib.request.urlopen('http://127.0.0.1:8767/api/bootstrap', timeout=30) as response:
    bootstrap = json.load(response)
assert bootstrap['source']['register_sha256'] == pointer['register_sha256']
live_native = bootstrap['source']['live_dropbox']
native = capture('current_wall_census', live_native['path'], 'current-wall-census.json')
assert manifest['sources']['current_wall_census']['sha256'] == live_native['sha256']
manifest['wall_census'] = live_native
capture('source_gallery', bootstrap['source']['gallery_database'], 'source-gallery.sqlite')
assert manifest['sources']['source_gallery']['sha256'] == bootstrap['source']['gallery_sha256']
database = Path.home() / 'Library/Application Support/BoldstoneReview/reviews.sqlite3'
backup = cut / 'app-review-cut.sqlite3'
source = sqlite3.connect(database.as_uri() + '?mode=ro', uri=True)
target = sqlite3.connect(backup)
try:
    source.backup(target)
finally:
    target.close()
    source.close()
manifest['sources']['app_review_cut'] = {'path': str(database), 'snapshot': str(backup), 'sha256': sha(backup)}
connection = sqlite3.connect(backup.as_uri() + '?mode=ro', uri=True)
connection.row_factory = sqlite3.Row
try:
    reviews = [dict(row) for row in connection.execute('SELECT * FROM reviews ORDER BY kind,product_id,item_id')]
    event_cutoff = connection.execute('SELECT MAX(id) FROM events').fetchone()[0]
finally:
    connection.close()
for row in reviews:
    row['data'] = json.loads(row['data'])
active = set(register['active_option_ids'])
approved = [row for row in reviews if row['kind'] == 'image' and row['product_id'] in active
            and row['data'].get('primary') is True and row['data'].get('decision') == 'reviewed'
            and 'listing' in row['data'].get('uses', [])]
assert len({row['product_id'] for row in approved}) == len(approved), 'Multiple explicit Primary choices need review'
deleted = {row['item_id']: {'state': row['data']['state'], 'result': row['data']['result'],
                           'review_version': row['version'], 'review_updated_at': row['updated_at']}
           for row in reviews if row['kind'] == 'deletion' and row['data'].get('state') == 'deleted'
           and row['data'].get('result', {}).get('verified_absent') is True}
all_current = dict(native['records'])
completed = {row['id']: row for row in completed_paths['files']}
for fid, row in completed.items():
    if '/Products/Workshop and Moulding/' in row['path']:
        all_current[fid] = {'id': fid, 'kind': 'file', 'path': row['path'], 'name': row['name'],
                            'folder_id': row['parent_id'], 'bytes': row['size'],
                            'content_hash': row['content_hash'], 'rev': row['rev'], 'modified': row['server_modified']}
current_files = {fid: row for fid, row in all_current.items() if row['kind'] == 'file' and fid not in deleted}
subsequent_absences = sorted(set(completed) - set(current_files))
unexplained = [fid for fid in subsequent_absences if fid not in deleted]
manifest.update(review_rows=len(reviews), review_event_cutoff=event_cutoff,
                recorded_primary_choices=len(approved), verified_deletion_tombstones=len(deleted),
                current_audited_files=len(current_files),
                subsequent_verified_deletions=len(subsequent_absences) - len(unexplained),
                subsequent_absences_without_app_deletion_receipts=unexplained,
                new_files_after_filename_pass=sorted(set(current_files) - set(completed)),
                baseline_pointer_sha256=pointer_sha)
(cut / 'recorded-primary-choices.json').write_text(json.dumps(approved, indent=2) + '\n')
(cut / 'verified-deletion-tombstones.json').write_text(json.dumps(deleted, indent=2) + '\n')
(cut / 'current-audited-files.json').write_text(json.dumps(current_files, indent=2) + '\n')
assert sha(pointer_path) == pointer_sha
assert not unexplained, 'Current source absences require individual reconciliation'
(cut / 'input-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
(HERE / 'input-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
(HERE / 'publication-plan.json').write_text(json.dumps({
    'status': 'INPUTS_CAPTURED_PUBLICATION_NOT_STARTED', 'snapshot': str(cut),
    'steps': ['Prepare current register and preserved source-gallery projection',
              'Author both existing workbook views and current image index',
              'Independently verify source preservation, native references and saved workbook links',
              'Publish controls and master pointer with rollback guards',
              'Coordinate source-only app rebase and verify retained decisions'],
    'shared_publication_native_or_app_runtime_writes': 0,
}, indent=2) + '\n')
print(json.dumps({key: manifest[key] for key in ['input_directory','review_rows','review_event_cutoff',
    'recorded_primary_choices','verified_deletion_tombstones','current_audited_files',
    'subsequent_verified_deletions','new_files_after_filename_pass']}, indent=2))
