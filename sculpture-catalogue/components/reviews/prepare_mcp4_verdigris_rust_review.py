"""Prepare one pending finish review without approving names, specs or manufacture."""
import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[2]
HERE = ROOT / 'components/reviews/concave-to-mcp4-consolidation-2026-10-19/verdigris-rust-review'
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
rel = lambda p: str(Path(p).relative_to(ROOT))
def write(path, value):
    path = Path(path); temp = path.with_name(path.name + '.tmp'); temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n'); temp.replace(path)

paths = {'user': ROOT / 'components/reviews/user_classifications.json', 'progress': ROOT / 'components/reviews/specification_review_progress.json', 'walkthrough': ROOT / 'components/reviews/walkthrough_checkpoint.json', 'component': ROOT / 'components/checkpoint.json', 'root': ROOT / 'checkpoint.json'}
docs = {k: read(v) for k, v in paths.items()}
if (HERE / 'preparation-receipt.json').exists():
    assert docs['walkthrough']['current_question_id'] == 'MCP4-VERDIGRIS-RUST-NAME-01'
    print(json.dumps({'status': 'ALREADY_PREPARED_IDEMPOTENT_NO_WRITE'})); raise SystemExit
before = copy.deepcopy(docs); guards = {k: sha(v) for k, v in paths.items()}
p, cp, c = (docs[k] for k in ['progress', 'walkthrough', 'component'])
assert cp['current_answer_recorded'] and cp['current_size_finish_variant_id'] == 'MCP4-VERDIGRIS-25'
head = read(HERE / 'current-reference-check.json'); image, folder, listing = head['file'], head['folder'], head['listing']
assert image['id'] == 'id:cnqzTNngPVsAAAAAAAylRA' and folder['id'] == 'id:cnqzTNngPVsAAAAAAAyipA'
assert len(listing['entries']) == 3 and not listing['has_more'] and not listing['cursor']
model = read(ROOT / 'components/evidence/component_register.json'); assets = {x['id']: x for x in model['assets']}
cached = []
for entry in listing['entries']:
    asset = assets[entry['file_id']]
    thumb = Path('/Users/tprice/Library/Application Support/BoldstoneImageConsistency/review-20261015T223009Z/thumbnails') / (asset['content_hash'] + '.jpg')
    assert thumb.exists() and entry['name'] == asset['name']
    cached.append({'file_id': entry['file_id'], 'folder_id': folder['id'], 'current_name': entry['name'], 'current_path': entry['path_display'], 'current_bytes': entry['file']['size'], 'thumbnail': str(thumb), 'thumbnail_sha256': sha(thumb), 'original_bytes_checked_now': False})
cid, vid, name = 'BC-MCP-4', 'MCP4-VERDIGRIS-RUST', 'Moon Crater Phase 4 — Verdigris and Rust'
question = 'Keep “' + name + '” for this pictured finish?'
ref = {'file_id': image['id'], 'folder_id': folder['id'], 'file_path': image['path_display'], 'folder_path': folder['path_display'], 'file_revision': image['rev'], 'file_bytes': image['size'], 'checked_utc': head['checked_utc'], 'image_url': 'https://www.dropbox.com/home' + quote(folder['path_display'], safe='/') + '?preview=' + quote(image['name']), 'folder_url': 'https://www.dropbox.com/home' + quote(folder['path_display'], safe='/')}
details = [
    ('DIMENSIONS', 'Individual dimensions', '25 × 25 × approximately 6 cm — proposal, not measured', 'Visual comparison with other MCP4 25 cm reviews only. No scale or exact-finish measurement establishes these dimensions.'),
    ('WEIGHT', 'Individual dry weight', 'Approximately 4 kg dry; estimated 3–5 kg — conditional guess', 'Comparison with a proposed 25 cm MCP4 panel. Actual mass depends on unconfirmed size, thickness, substrate and reinforcement; no weighing evidence.'),
    ('MATERIAL', 'Material and finish', 'Sand/plaster composite with faux verdigris and rust finish — guess', 'Related MCP4 source descriptions and surface appearance support a working hypothesis only. Binder, copper/iron content, reinforcement and sealer are unknown.'),
    ('FIXING', 'Fixing', 'One concealed rear hanging point — proposal; hardware and load capacity unknown', 'A related Verdigris reference shows one rear recess. No reverse of this Rust finish is available in this three-file packet; no fixing transfer or load rating confirmed.'),
    ('PRICE', 'Individual retail price', '£175 per panel — new discussion proposal, not an observed current offer', 'Owner-check proposal for a 25 cm panel. Related-finish prices conflict; no current exact-finish Squarespace or Shopify offer confirmed.'),
    ('AVAILABILITY', 'Availability', 'Made to order — proposal; stock and lead time unknown', 'Proposed catalogue policy only; images do not establish manufacture, stock, production capacity or lead time.')]
proposals = [{'proposal_id': vid + '-' + key, 'field': field, 'display': display, 'status': 'UNAPPROVED_WORKING_PROPOSAL;NOT_PHYSICALLY_VERIFIED', 'basis': basis, 'owner_approved': False} for key, field, display, basis in details]
scope = 'Only the selected complete Rust/Verdigris depiction and two matching close views were reviewed through cached thumbnails. No new original-byte verification. Name and all six proposals are pending; no manufacture, physical-cast, stock or exact platform match inferred. No rear, calibrated profile, wider-room or series image established within this three-file folder.'
coverage = {'full_component': True, 'on_wall': True, 'wider_room': False, 'series_arrangement': False, 'rear': False, 'calibrated_profile': False, 'contextual_images_available': True, 'context_image_type': 'On-wall presentation only; wider room and series not established in this folder', 'contextual_file_ids': [image['id']], 'installation_provenance': 'UNCONFIRMED', 'review_scope': 'Three cached thumbnails in the complete current G218 listing; no whole-library absence claim', 'physical_stock_count_inferred': False}
now = datetime.now(timezone.utc).isoformat()
node = {'component_id': cid, 'size_finish_variant_id': vid, 'proposed_name': name, 'identity_confirmed': False, 'proposals_approved': False, 'physical_specs_verified': False, 'existing_platform_match_confirmed': False, 'primary_image_id': image['id'], 'primary_folder_id': folder['id'], 'current_dropbox_reference': ref, 'specification_proposals': proposals, 'photo_coverage': coverage, 'scope': scope, 'review_record': rel(HERE / 'component-review.json'), 'reviewed_utc': now, 'missing_photographs': ['Rear/fixing', 'Calibrated profile/measurement', 'Full-component wider-room image', 'Series image if applicable']}
card = copy.deepcopy(node) | {'question_id': 'MCP4-VERDIGRIS-RUST-NAME-01', 'owner_question': question, 'owner_answer_recorded': False, 'cached_media': cached, 'review_decision_mode': 'NAME_AND_DEPICTED_FINISH_ONLY', 'six_specifications_approved_by_name_keep': False}
p['reviews'][cid]['size_finish_variants'][vid] = node
p.setdefault('current_component_photograph_gaps', {})[vid] = {'component_id': cid, 'size_finish_variant_id': vid, 'canonical_name': name + ' (name pending)', 'finish': 'Verdigris and Rust', 'front': 'Complete front/on-wall depiction available in source003; source001/002 are close views.', 'room': 'On-wall presentation available; full-component wider-room view not established in this folder.', 'series': 'Series/group context not established in this folder; optional if no series is intended.', 'evidence': 'Three cached thumbnails and complete current G218 listing; scene provenance unconfirmed. Not a whole-library absence claim.', 'missing': 'Rear/fixing, calibrated side/profile, full-component wider-room and applicable series imagery remain unestablished.', 'review_record': node['review_record']}
cp.update({'current_size_finish_variant_id': vid, 'current_question_id': card['question_id'], 'current_review_record': node['review_record'], 'current_answer_recorded': False, 'current_specification_answer_recorded': False, 'current_finish_reference_equivalence_answer_recorded': False, 'current_finish_reference_equivalence_approval': None, 'current_component_source_notes': [x['display'] for x in proposals], 'state': 'AWAITING_MCP4_VERDIGRIS_RUST_NAME;ALL6_FIELDS_PENDING', 'answer_state': 'Verdigris finish equivalence is saved; Rust/Verdigris name and specifications remain pending.'})
c['interactive_review_state'].update({'current_size_finish_variant_id': vid, 'current_question_id': card['question_id'], 'current_name': name, 'state': cp['state'], 'review_decision_mode': card['review_decision_mode'], 'specification_proposals_approved': False, 'current_finish_reference_equivalence_answer_recorded': False})
c['next_work'][0] = 'Review the pictured MCP4 Verdigris and Rust finish name, with six unaccepted single-panel proposals and explicit contextual-image coverage.'
for k, doc in docs.items():
    if k != 'user': doc['updated_utc'] = now
docs['root']['current_component_review'] = copy.deepcopy(c)
assert docs['user'] == before['user'] and c['counts'] == before['component']['counts']
assert p['reviews'][cid]['size_finish_variants']['MCP4-VERDIGRIS-25'] == before['progress']['reviews'][cid]['size_finish_variants']['MCP4-VERDIGRIS-25']
assert all(sha(paths[k]) == v for k, v in guards.items())
write(HERE / 'before-preparation.json', before); write(HERE / 'component-review.json', card)
for k, path in paths.items():
    if k != 'user': write(path, docs[k])
write(HERE / 'preparation-receipt.json', {'status': 'PREPARED_NAME_AND_SPECS_PENDING', 'question_id': card['question_id'], 'owner_decisions': 0, 'spec_approvals': 0, 'new_BC_ids': [], 'private_original_downloads': 0, 'remote_writes': 0, 'card_sha256': sha(HERE / 'component-review.json'), 'user_ledger_sha256': guards['user']})
assert read(paths['root'])['current_component_review'] == read(paths['component']) and not read(paths['walkthrough'])['current_answer_recorded'] and sha(paths['user']) == guards['user']
print(json.dumps({'status': 'PREPARED_AND_READ_BACK', 'question_id': card['question_id'], 'spec_groups': 6, 'contextual_image_type': coverage['context_image_type']}))
