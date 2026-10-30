from pathlib import Path
import csv
import datetime
import hashlib
import html
import json
import os
import urllib.parse

JOB = Path(__file__).resolve().parent
BASE = JOB.parents[2]
ROOT_JOB = BASE / 'components/reconciliation/in-situ-folder-refresh-and-context-review-2026-10-23'
LAVA_IDS = ['BSI-7357A558C9E8', 'BSI-791ADD96D660', 'BSI-2246CBC9C94E']
EXPECTED_INDIVIDUAL = {'BSI-C41824131174', 'BSI-04D6E8690F30'}


def read(path):
    return json.loads(path.read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    tmp.replace(path)


def dropbox_urls(path):
    return {
        'image_url': 'https://www.dropbox.com/preview' + urllib.parse.quote(path, safe='/'),
        'folder_url': 'https://www.dropbox.com/home' + urllib.parse.quote(str(Path(path).parent), safe='/'),
    }


now = datetime.datetime.now(datetime.timezone.utc).isoformat()
pointer_path = BASE / 'current-master.json'
pointer = read(pointer_path)
register_path = BASE / pointer['register']
assert digest(register_path) == pointer['register_sha256']
register = read(register_path)
options = {row['product_id']: row for row in register['options']}
csv_path = BASE / pointer['current_missing_picture_lists']['individual_image_gaps']
with csv_path.open(encoding='utf-8-sig', newline='') as stream:
    current_queue = list(csv.DictReader(stream))
assert {row['option_id'] for row in current_queue} == EXPECTED_INDIVIDUAL, 'Individual queue changed; review before regeneration'

sources = {row['id']: row for row in read(JOB / 'image-queue-live-source-metadata.json')['records']}
root_queue = read(ROOT_JOB / 'photo-review-queue.json')
root_acanthus = next(row for row in root_queue if row.get('option_id') == 'BSI-C41824131174' and row.get('role') == 'Individual')
backup = root_acanthus['source_reference']
assert backup['file_id'] == 'id:cnqzTNngPVsAAAAAAA6LRw'
individual = []
for original in current_queue:
    row = dict(original)
    row['published_source_preserved'] = dict(original)
    if row['option_id'] == 'BSI-C41824131174':
        row.update({key: value for key, value in backup.items() if key != 'name'})
        row['reference_file_name'] = backup['name']
        row.update(dropbox_urls(sources[backup['file_id']]['path_display']))
        row['review_status'] = 'OPEN_COMPLETE_INDIVIDUAL_IMAGE_REVIEW'
        row['review_owner_thread'] = '01a144ab-1a7c-7223-a403-73a4d53d70ff'
        row['next_action'] = 'Complete individual image remains open in the master session. This working link is the historical detail reference, using the verified backup copy.'
        row['reference_kind'] = 'Detail reference; backup file ID is distinct from historical original.'
    else:
        row.update(dropbox_urls(sources[row['file_id']]['path_display']))
        row['review_status'] = 'DEFERRED_LEGACY_IDENTITY'
        row['next_action'] = 'Leave historical FFL1/FFS2 identity binding deferred. Current Frozen Fish default remains 70 cm high by 15 cm wide.'
        row['reference_kind'] = 'Existing reference; identity binding remains deferred.'
    individual.append(row)
    assert row['name'] == options[row['option_id']]['name'], 'Product name changed during reference refresh'
individual.sort(key=lambda row: row['review_status'] == 'DEFERRED_LEGACY_IDENTITY')

approval_path = ROOT_JOB / 'lava-white-pool-owner-approval.json'
approval = read(approval_path)
seal = read(ROOT_JOB / 'lava-white-pool-owner-approval-seal.json')
assert digest(approval_path) == seal['sha256']
assert {row['product_id'] for row in approval['targets']} == set(LAVA_IDS)
assert approval['source_file_id'] == 'id:cnqzTNngPVsAAAAAAA6VpQ'
native = read(JOB / 'lava-white-pool-live-verification.json')
pool = native['metadata']['file']
root_meta = read(ROOT_JOB / 'new-scene-metadata.json')[pool['id']]['file']
assert all(pool[key] == root_meta[key] for key in ('id', 'rev', 'size', 'path_display'))
download = next(row for row in read(ROOT_JOB / 'new-scene-download-verification.json')['files'] if row['file_id'] == pool['id'])
original_path = Path(download['local_original'])
data = original_path.read_bytes()
dropbox_hash = hashlib.sha256(b''.join(hashlib.sha256(data[i:i + 4194304]).digest() for i in range(0, len(data), 4194304))).hexdigest()
assert digest(original_path) == download['sha256']
assert dropbox_hash == download['content_hash'] and len(data) == pool['size']
pool.update(dropbox_urls(pool['path_display']))
pool.update({'folder_id': 'id:cnqzTNngPVsAAAAAAA6VpA', 'sha256': download['sha256'], 'content_hash': dropbox_hash, 'local_original': str(original_path)})

lava = []
for pid, position in zip(LAVA_IDS, ['LEFT', 'CENTRE', 'RIGHT']):
    option = options[pid]
    imported = option.get('photo_coverage', {}).get('in_situ') == 'Available' and pool['id'] in json.dumps(option)
    lava.append({'product_id': pid, 'name': option['name'], 'member_position': position, 'approved_role': 'In situ', 'approved_scene_file_id': pool['id'], 'owner_approved': True, 'approval_imported_in_published_master': imported, 'published_coverage': option.get('photo_coverage'), 'local_review_status': 'APPROVED_AND_PUBLISHED' if imported else 'OWNER_APPROVED_AWAITING_MASTER_PUBLICATION'})

report = {
    'schema': 'boldstone.individual-queue-and-lava-context-readback.v1',
    'recorded_utc': now,
    'source_master': {'pointer_path': str(pointer_path), 'pointer_sha256': digest(pointer_path), 'published_utc': pointer.get('recorded_utc'), 'register': str(register_path), 'register_sha256': digest(register_path), 'option_count': len(options)},
    'source_individual_queue': {'path': str(csv_path), 'sha256': digest(csv_path)},
    'individual_queue': individual,
    'individual_summary': {'total_entries': 2, 'active_complete_individual_image_reviews': 1, 'deferred_identity_checks': 1},
    'published_sandstone_role_approval_readback': [{'product_id': a['product_id'], 'decision_id': a['decision_id'], 'imported': a['decision_id'] in json.dumps(options[a['product_id']])} for a in [read(p) for p in sorted(JOB.glob('lava-moon-*-sandstone-owner-image-role-approval.json'))]],
    'lava_white_in_situ_reviews': lava,
    'pool_scene': pool,
    'pool_owner_approval': {'path': str(approval_path), 'sha256': digest(approval_path), 'decision_id': approval['decision_id'], 'owner_source': approval['source_owner_event'], 'raw_transcript_line_sha256': 'ccbce15e1aa933319c04180afab5d06212e8fc4e69095be0dc507e6680bca847'},
    'independent_visual_review': {'comparison_file_id': 'id:cnqzTNngPVsAAAAAAAylMA', 'mapping_basis': 'The central complete three-panel arrangement in the pool-room scene shows panel 1 at left, panel 2 with the curled spiral at centre, and panel 3 with the outer curved edge at right.', 'scope': 'Approved room depiction used as in-situ reference for the three existing White options. Repeated arrangements do not create additional catalogue options or prove stock.', 'creation_origin': 'Unverified; no claim of an authenticated camera photograph or real installed casts.', 'image_pixels_edited': False},
    'remote_writes': 0,
    'canonical_master_writes_by_this_lane': 0,
    'duplicate_owner_questions': 0,
}
assert all(x['imported'] for x in report['published_sandstone_role_approval_readback'])
assert digest(pointer_path) == report['source_master']['pointer_sha256'], 'Master pointer changed during readback'
save(JOB / 'individual-queue-and-lava-context-refresh.json', report)

esc = html.escape
individual_rows = ''.join('<tr><td>' + esc(row['name']) + '</td><td>' + esc(row['next_action']) + '</td><td><a href="' + esc(row['image_url'], quote=True) + '">Image reference</a> · <a href="' + esc(row['folder_url'], quote=True) + '">Containing folder</a></td></tr>' for row in individual)
lava_rows = ''.join('<tr><td>' + esc(row['name']) + '</td><td>' + esc(row['member_position'].title()) + '</td><td>' + ('Published in master' if row['approval_imported_in_published_master'] else 'Approved; master publication pending') + '</td></tr>' for row in lava)
scene_relative = urllib.parse.quote(os.path.relpath(original_path, JOB), safe='/')
page = '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Individual image queue and Lava Moon installation review</title><style>body{font:17px/1.5 system-ui,sans-serif;max-width:1120px;margin:36px auto;padding:0 22px;color:#202722;background:#faf9f5}h1,h2{line-height:1.2}table{width:100%;border-collapse:collapse;background:white}td,th{padding:12px;text-align:left;border:1px solid #d6dbd5;vertical-align:top}a{color:#135b51}img{display:block;width:100%;height:auto;margin:20px 0}small{color:#526258}.note{padding:14px;background:#e9f0ec;border-left:4px solid #397f69}</style><h1>Image review refresh</h1><p><small>Checked ' + esc(now) + '. Published register: ' + esc(pointer.get('recorded_utc', '')) + '.</small></p><h2>Remaining individual-image queue</h2><p>One complete-image review remains open, plus one deferred identity check.</p><table><thead><tr><th>Option</th><th>Next action</th><th>Verified reference links</th></tr></thead><tbody>' + individual_rows + '</tbody></table><h2>Lava Moon White installation reference</h2><p class="note">The owner approved this pool-room scene for all three White panels. Its creation origin remains unverified. It is retained as a room depiction; repeated arrangements do not add products or establish stock.</p><p><a href="' + esc(pool['image_url'], quote=True) + '">Dropbox image</a> · <a href="' + esc(pool['folder_url'], quote=True) + '">Containing folder</a></p><img src="' + esc(scene_relative, quote=True) + '" alt="Approved pool-room depiction with Lava Moon White panels"><table><thead><tr><th>Option</th><th>Position in central triptych</th><th>Review status</th></tr></thead><tbody>' + lava_rows + '</tbody></table><p><a href="individual-queue-and-lava-context-refresh.json">Evidence and source records</a></p></html>'
html_path = JOB / 'individual-queue-and-lava-context-refresh.html'
html_path.write_text(page)
assert len(individual) == 2 and len(lava) == 3
assert all(row['image_url'] in page and row['folder_url'] in page for row in individual)
assert pool['image_url'] in page and original_path.exists()

state_path = JOB / 'review-state.json'
state = read(state_path)
state['recorded_utc'] = now
state['latest_individual_queue_refresh'] = {'path': str(JOB / 'individual-queue-and-lava-context-refresh.json'), 'sha256': digest(JOB / 'individual-queue-and-lava-context-refresh.json'), 'report_html': str(html_path), 'individual_queue_entries': 2, 'active_image_reviews': 1, 'deferred_identity_checks': 1, 'source_master_register': str(register_path), 'checked_utc': now}
state['current_batch_review_status'] = 'ALL_TEN_PRIOR_IMAGE_DECISIONS_IMPORTED_IN_CURRENT_MASTER'
for row in state['allocated_current_batch']:
    if row['product_id'] in {'BSI-725A77437026', 'BSI-D7C2FC84A86B', 'BSI-63B177B06578'}:
        row['decision_status'] = 'OWNER_APPROVED_COMBINED_REFERENCES_IMPORTED_IN_MASTER'
        row['image_role_decision']['master_import_readback'] = {'recorded_utc': now, 'register': str(register_path), 'register_sha256': digest(register_path), 'decision_id_join_verified': True}
state['latest_image_role_approval_batch']['master_import_status'] = 'IMPORTED'
state['next_review'] = {'scope': 'Lava Moon 1-3 White in-situ reference', 'product_ids': LAVA_IDS, 'status': 'OWNER_APPROVED_AND_PUBLISHED' if all(x['approval_imported_in_published_master'] for x in lava) else 'OWNER_APPROVED_IN_MASTER_SESSION_PUBLICATION_PENDING', 'pool_file_id': pool['id'], 'approval_packet': str(approval_path), 'approval_packet_sha256': digest(approval_path), 'creation_origin_unverified': True, 'duplicate_question_needed': False, 'readback_report': str(JOB / 'individual-queue-and-lava-context-refresh.json')}
save(state_path, state)
save(JOB / 'individual-queue-and-lava-context-refresh-verification.json', {'recorded_utc': now, 'status': 'PASS', 'json_sha256': digest(JOB / 'individual-queue-and-lava-context-refresh.json'), 'html_sha256': digest(html_path), 'individual_entries': 2, 'approved_lava_in_situ_options': 3, 'published_lava_in_situ_options': sum(x['approval_imported_in_published_master'] for x in lava), 'checked_master_unchanged_during_read': True, 'pool_native_revision_matches_root_download': True, 'pool_sha256_and_dropbox_content_hash_match': True, 'all_rendered_links_present': True})
print(json.dumps({'status': 'PASS', 'review_html': str(html_path), 'individual_queue_entries': 2, 'approved_lava_in_situ_options': 3, 'published_lava_in_situ_options': sum(x['approval_imported_in_published_master'] for x in lava), 'source_register': str(register_path)}, indent=2))
