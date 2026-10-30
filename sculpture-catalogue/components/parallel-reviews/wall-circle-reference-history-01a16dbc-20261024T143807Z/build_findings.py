"""Bind two deleted-ID histories to unchanged catalogue references and local originals."""
import hashlib
import html
import json
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import quote
from PIL import Image
from boldstone.hashing import hash_file

H = Path(__file__).resolve().parent
B = H.parents[2]
ROOT = B.parent
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
esc = lambda s: html.escape(str(s), quote=True)
write = lambda p, obj: Path(p).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n')
assert not (H / 'sealed-findings.json').exists(), 'Sealed lane is immutable'
live = read(H / 'live-receipts.json')
account = live['account']['structuredContent']
assert account['root_namespace_id'] == account['home_namespace_id'] == '202238505'
pointer_bytes = (B / 'current-master.json').read_bytes()
pointer = json.loads(pointer_bytes)
register_path = B / pointer['register']
assert sha(register_path) == pointer['register_sha256']
register = read(register_path)
source = ROOT / 'reports/dropbox-wall-circle-finish-names-review-2026-10-23/download-receipts.json'
downloads = read(source)
hold_path = ROOT / 'reports/dropbox-wall-circle-finish-names-and-scene-split-2026-10-23/owner-hold.json'
hold = read(hold_path)
assert hold['no_further_native_mutations'] and hold['no_restoration_copying_or_backup_fallback']
source_hashes = {str(p): sha(p) for p in [source, hold_path, H / 'live-receipts.json', register_path]}
rows = []
for label, oid, fileid, folderid in [
    ('yellow-grey', 'BSI-65520F070145', 'id:cnqzTNngPVsAAAAAAAr1IQ', 'id:cnqzTNngPVsAAAAAAA53CQ'),
    ('terracotta', 'BSI-D5A939264C82', 'id:cnqzTNngPVsAAAAAAAs9QA', 'id:cnqzTNngPVsAAAAAAA5RBw')]:
    option = next(o for o in register['options'] if o['product_id'] == oid)
    assert option['file_id'] == fileid and option['folder_id'] == folderid
    folder = live['observations']['folder-' + label]['response']['structuredContent']['folder']
    history = live['observations']['history-' + label]['response']['structuredContent']
    listing = live['observations']['list-' + label]['response']['structuredContent']
    assert folder['id'] == folderid and history['is_deleted'] is True and history['server_deleted']
    assert history['has_more'] is False and listing['has_more'] is False
    assert all(x['file_id'] == fileid for x in history['entries'])
    latest = history['entries'][0]
    selected = folder['path_display'] + '/' + latest['name']
    assert latest['path_display'] == selected
    assert all(x['file_id'] != fileid and x['path_display'] != selected for x in listing['entries'])
    original = next(x for x in downloads['entries'] if x['file_id'] == fileid)
    local = Path(original['local_path'])
    data = local.read_bytes()
    local_sha = hashlib.sha256(data).hexdigest()
    local_dbhash = hash_file(local)
    assert len(data) == original['size'] == latest['size']
    assert local_sha == original['sha256']
    assert local_dbhash == original['dropbox_content_hash'] == latest['content_hash']
    with Image.open(local) as image:
        image.load()
        decoded = {'format': image.format, 'mode': image.mode, 'dimensions': list(image.size), 'full_decode_passed': True}
    assert decoded['format'] == 'PNG'
    current = []
    for child in listing['entries']:
        assert Path(child['path_display']).parent.as_posix() == folder['path_display']
        current.append({'file_id': child['file_id'], 'name': child['name'], 'size': child['file'].get('size', 0),
                        'image_url': option['folder_url'] + '?preview=' + quote(child['name'], safe=''),
                        'folder_url': option['folder_url'],
                        'role': 'CURRENT_FOLDER_FILE_NOT_SELECTED_AS_REPLACEMENT'})
    rows.append({'option_id': oid, 'name': option['name'], 'file_id': fileid, 'folder_id': folderid,
                 'saved_image_url': option['image_url'], 'folder_url': option['folder_url'],
                 'new_evidence_status': 'SAVED_PRIMARY_ID_MARKED_DELETED_IN_AVAILABLE_DROPBOX_HISTORY',
                 'server_deleted_utc': history['server_deleted'], 'latest_available_revision': latest,
                 'available_revision_count': len(history['entries']), 'history_response_has_more': False,
                 'history_scope': 'Available history for the exact stable file ID. No universal history, actor, reason or retention guarantee inferred.',
                 'direct_folder_listing_complete': True, 'saved_id_and_path_absent_from_direct_folder': True,
                 'current_folder_files': current,
                 'existing_local_original': {'path': str(local), 'size': len(data), 'sha256': local_sha,
                                             'dropbox_content_hash': local_dbhash,
                                             'matches_latest_available_remote_revision_size_and_content_hash': True,
                                             'backup_independence_or_restoration_tested': False, **decoded},
                 'canonical_option_guard': option, 'replacement_selected': False,
                 'restored_to_dropbox': False, 'identity_or_photo_hold_released': False})
finding = {'schema': 'boldstone.wall-circle-history-and-local-original-readback.v1',
           'recorded_utc': datetime.now(timezone.utc).isoformat(), 'status': 'VERIFIED_READ_ONLY_SOURCE_FINDINGS',
           'source_register': str(register_path), 'source_register_sha256': pointer['register_sha256'],
           'source_pointer_observed_sha256': hashlib.sha256(pointer_bytes).hexdigest(),
           'source_files_sha256': source_hashes, 'rows': rows,
           'scope': 'Two exact saved primary IDs only. No alternate role binding or canonical edits. The original Wall Circle hold remains.',
           'deletion_actor': None, 'deletion_reason': None, 'native_or_platform_writes': 0,
           'offline_fake_adapter_tests': {'passed': 74, 'duration_seconds': 8.68},
           'live_reads': {'account': 1, 'folder_metadata': 2, 'stable_id_revision_histories': 2, 'complete_direct_folder_listings': 2,
                          'binary_downloads': 0, 'live_sandbox_integration_tested': False},
           'local_originals_rehashed_and_fully_decoded': 2,
           'independent_backup_protection_or_restoration_demonstrated': False}
write(H / 'findings.json', finding)
cards = []
for row in rows:
    local = row['existing_local_original']
    current = ''.join('<li><a href="' + esc(x['image_url']) + '">' + esc(x['name']) + '</a></li>' for x in row['current_folder_files'])
    cards.append('<article id="' + esc(row['option_id']) + '"><h2>' + esc(row['name']) + '</h2><p>Dropbox history marks the saved primary ID deleted at ' + esc(row['server_deleted_utc']) + '. The containing folder still exists.</p><p><a href="' + esc(local['path']) + '">Open the existing local original</a> · <a href="' + esc(row['folder_url']) + '">Open the current Dropbox folder</a></p><p>The local original was fully decoded and freshly checked against its saved SHA-256 and the latest available Dropbox revision’s size and content hash. This is local readability, not an independently protected backup or a remote restoration.</p><p>Files currently present in the folder, with no replacement selected:</p><ul>' + current + '</ul><p>Available revision entries: ' + str(row['available_revision_count']) + '. Last available revision: ' + esc(row['latest_available_revision']['rev']) + '.</p><p><small>Saved file ID: ' + esc(row['file_id']) + '<br>Folder ID: ' + esc(row['folder_id']) + '<br>Local SHA-256: ' + esc(local['sha256']) + '</small></p></article>')
text = '<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Wall Circle reference history</title><style>body{font:17px/1.5 Arial,sans-serif;max-width:1000px;margin:40px auto;padding:0 24px;color:#222}article{border-top:1px solid #ccc;margin-top:28px;padding-top:18px}h1{font-size:30px}h2{font-size:22px}a{color:#15549b}small{overflow-wrap:anywhere}li{margin:9px 0}</style></head><body><h1>Wall Circle reference history</h1><p>Two saved primary references are marked deleted in Dropbox’s available file history. Both original images remain readable in the existing local review downloads. No file was restored, copied, uploaded or selected as a replacement. The owner’s Wall Circle hold remains.</p><p>The history responses do not identify a deletion actor or reason. Current catalogue specifications, sale options and photograph roles are unchanged.</p>' + ''.join(cards) + '</body></html>'
class Links(HTMLParser):
    def handle_starttag(self, tag, attrs):
        url = dict(attrs).get('href', '') if tag == 'a' else ''
        if url and not url.startswith('https:'):
            assert Path(url).is_file(), url
Links().feed(text)
(H / 'review.html').write_text(text)
assert all(sha(path) == digest for path, digest in source_hashes.items())
manifest = [{'path': str(H / name), 'sha256': sha(H / name)} for name in ['live-receipts.json', 'findings.json', 'review.html', 'build_findings.py']]
seal = {'status': 'SEALED_VERIFIED_READ_ONLY_FINDINGS', 'recorded_utc': datetime.now(timezone.utc).isoformat(),
        'files': manifest, 'option_ids': [x['option_id'] for x in rows], 'same_owner_holds_retained': True,
        'shared_master_writes': 0, 'native_writes': 0, 'root_publication_owner': '01a144ab-1a7c-7223-a403-73a4d53d70ff'}
write(H / 'sealed-findings.json', seal)
print(json.dumps({'status': seal['status'], 'deleted_primary_references': 2, 'local_originals_verified': 2,
                  'current_folder_files': sum(len(x['current_folder_files']) for x in rows),
                  'seal_sha256': sha(H / 'sealed-findings.json'), 'review': str(H / 'review.html')}))

