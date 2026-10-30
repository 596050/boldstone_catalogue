"""Record keyhole fixing type without inferring its number or hardware."""
import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from import_source_followups_24_25 import canonical_messages

ROOT = Path(__file__).resolve().parents[2]
HERE = ROOT / 'components/reviews/parallel-import-2026-10-19-batch61'
REVIEW = ROOT / 'components/reviews/concave-to-mcp4-consolidation-2026-10-19/verdigris-rust-review'
read = lambda path: json.loads(Path(path).read_text())
sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
rel = lambda path: str(Path(path).relative_to(ROOT))
def write(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.tmp'); temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n'); temp.replace(path)

paths = {'user': ROOT / 'components/reviews/user_classifications.json', 'progress': ROOT / 'components/reviews/specification_review_progress.json', 'walkthrough': ROOT / 'components/reviews/walkthrough_checkpoint.json', 'component': ROOT / 'components/checkpoint.json', 'root': ROOT / 'checkpoint.json'}
docs = {key: read(path) for key, path in paths.items()}; cid, vid = 'BC-MCP-4', 'MCP4-VERDIGRIS-RUST'; did = cid + ':' + vid + ':OWNER-KEYHOLE-FIXING-TYPE:LINE20173'
if (HERE / 'import-receipt.json').exists():
    assert sum(item.get('decision_id') == did for item in docs['user']['fixing_detail_decisions']) == 1
    print(json.dumps({'batch': 61, 'status': 'ALREADY_IMPORTED_IDEMPOTENT_NO_WRITE'})); raise SystemExit
before = copy.deepcopy(docs); guards = {key: sha(path) for key, path in paths.items()}
u, p, cp, c = (docs[key] for key in ['user', 'progress', 'walkthrough', 'component'])
assert docs['root']['current_component_review'] == c and cp['current_question_id'] == 'MCP4-VERDIGRIS-RUST-FIXING-01' and not cp['current_answer_recorded']
card_path = ROOT / cp['current_review_record']; card = read(card_path); evidence = read(HERE / 'owner-answer-evidence.json')
messages = canonical_messages([evidence['preceding_assistant'], evidence['owner']], '01a144ab-1a7c-7223-a403-73a4d53d70ff')
assert [item['line'] for item in messages] == [20138, 20173] and messages[-1]['text'] == 'keyhold fixing' and '__003.png' in messages[0]['text']
node = p['reviews'][cid]['size_finish_variants'][vid]; ref = node['current_dropbox_reference']; assert ref == card['current_dropbox_reference']
heads = read(HERE / 'current-reference-check.json')['metadata']; head = next(item['file'] for item in heads if item.get('file')); parent = next(item['folder'] for item in heads if item.get('folder'))
assert all(head[key] == ref[target] for key, target in [('id', 'file_id'), ('rev', 'file_revision'), ('size', 'file_bytes'), ('path_display', 'file_path')]) and parent['id'] == ref['folder_id']
assert node['specification_proposals'][3]['proposal_id'] == 'MCP4-VERDIGRIS-RUST-FIXING'
protected = {str(path): sha(path) for path in [card_path, ROOT / cp['register_workbook'], ROOT / 'components/evidence/component_register.json', ROOT.parent / 'Boldstone_Wall_Sculptures_Matched_All_Fields_2026-10-15.xlsx']}
now = datetime.now(timezone.utc).isoformat(); approval = rel(HERE / 'owner-fixing-type.json')
decision = {'schema': 'boldstone.owner-fixing-type.v1', 'decision_id': did, 'recorded_utc': now, 'component_id': cid, 'size_finish_variant_id': vid, 'canonical_name': node['canonical_name'], 'scope_kind': 'EXACT_PANEL_FIXING_TYPE_ONLY', 'user_statement': messages[-1]['text'], 'normalized_fixing_description': 'Keyhole fixing', 'normalization_note': 'The contextual spelling keyhold is interpreted as keyhole; exact original owner text retained.', 'confirmed_fixing_type': 'Keyhole', 'number_of_fixing_points': None, 'hardware_material_positions_attachment_and_load_capacity': 'UNCONFIRMED', 'complete_fixing_group_approved': False, 'physical_specs_verified': False, 'actual_fixing_hardware_or_load_rating_verified': False, 'status': 'OWNER_STATED_KEYHOLE_FIXING_TYPE;COUNT_HARDWARE_AND_LOAD_UNCONFIRMED', 'authoritative_user_evidence': messages[-1], 'preceding_assistant_card_evidence': messages[0], 'primary_file_id': ref['file_id'], 'primary_folder_id': ref['folder_id'], 'image_link': ref['image_url'], 'folder_link': ref['folder_url'], 'scope': 'Owner specifies keyhole fixing for exact Rust source003. Type only: do not infer the previously proposed count of one, concealed layout, metal, attachment or load rating. Count and hardware details remain pending alongside price and availability. No other finish inherits this statement.', 'approval_record': approval, 'prior_fixing_proposal': copy.deepcopy(node['specification_proposals'][3]), 'new_full_specification_approvals': 0}
u['fixing_detail_decisions'].append(decision)
node['specification_proposals'][3].update({'display': 'Keyhole fixing — owner-stated; number, hardware and load capacity unconfirmed', 'value': {'fixing_type': 'Keyhole', 'fixing_point_count': None}, 'status': decision['status'], 'owner_confirmed': True, 'owner_approved': False, 'owner_fixing_type_confirmation': approval, 'basis': 'Exact owner reply keyhold fixing interpreted contextually as keyhole fixing. Number, positions, hardware material, attachment and load capacity remain unconfirmed. No price or availability approval.'})
node.update({'owner_stated_fixing_type': 'Keyhole fixing', 'owner_fixing_type_confirmation': approval, 'owner_stated_fixing_point_count': None, 'fixing_hardware_or_load_rating_verified': False, 'specification_status_display': 'Keyhole fixing type owner-stated; fixing details, price and availability pending', 'specification_review_status': 'OWNER_DIMENSIONS_WEIGHT_MATERIAL_AND_KEYHOLE_TYPE_RECORDED;FIXING_DETAILS_PRICE_AVAILABILITY_PENDING', 'scope': 'Name,25×25cm face and approximately6cm depth are owner-confirmed;4kg dry weight, plaster composite with faux verdigris/rust finish and keyhole fixing type are owner-stated. Keyhole count, hardware, attachment/load rating, material formulation and weighing method remain unverified. Fixing details, price and availability remain pending. Owner-wide manufacture statement51 retained; exact platform match and current stock remain unconfirmed.'})
p['pending_specification_checks']['MCP4-VERDIGRIS-RUST-FIXING-01'].update({'owner_answer_recorded': True, 'approval_record': approval, 'answer_scope': 'KEYHOLE_TYPE_ONLY;COUNT_UNCONFIRMED'})
for item in cp['pending_specification_reviews']:
    if item.get('component_id') == cid and item.get('size_finish_variant_id') == vid:
        item.update({'fixing_type_owner_stated': True, 'fixing_type_approval': approval, 'fixing_details_pending': ['Number and positions', 'Hardware and attachment', 'Load capacity'], 'pending_fields': ['Fixing details', 'Individual retail price', 'Availability']})
qid = 'MCP4-VERDIGRIS-RUST-FIXING-COUNT-01'; count_path = REVIEW / 'fixing-count-check.json'
count_card = {'schema': 'boldstone.scoped-fixing-count-review.v1', 'prepared_utc': now, 'question_id': qid, 'component_id': cid, 'size_finish_variant_id': vid, 'canonical_name': node['canonical_name'], 'identity_already_kept': True, 'owner_stated_fixing_type': 'Keyhole', 'fixing_type_approval': approval, 'proposed_fixing_point_count': 1, 'proposal_owner_approved': False, 'owner_question': 'Is there one keyhole fixing point on this panel, or how many?', 'current_dropbox_reference': copy.deepcopy(ref), 'photo_coverage': copy.deepcopy(node['photo_coverage']), 'owner_answer_recorded': False, 'actual_fixing_hardware_or_load_rating_verified': False, 'scope': 'Keyhole fixing count only. One point remains a proposal; the owner has confirmed the fixing type only. No hardware, attachment/load rating, price or availability approval.'}
p['pending_specification_checks'][qid] = {'review_record': rel(count_path), 'owner_answer_recorded': False, 'fixing_type_approval': approval}
cp.update({'current_question_id': qid, 'current_review_record': rel(count_path), 'current_answer_recorded': False, 'current_fixing_answer_recorded': True, 'current_fixing_type_answer_recorded': True, 'current_fixing_type_approval': approval, 'current_owner_fixing_type': 'Keyhole', 'current_fixing_count_answer_recorded': False, 'current_specification_answer_recorded': False, 'current_partial_specification_answer_recorded': True, 'last_fixing_detail_decision': approval, 'current_component_source_notes': [proposal['display'] for proposal in node['specification_proposals']], 'review_decision_mode': 'FIXING_COUNT_ONLY', 'state': 'MCP4_RUST_KEYHOLE_TYPE_RECORDED;AWAITING_KEYHOLE_COUNT', 'question_scope': count_card['scope'], 'answer_state': 'Owner keyhole fixing type saved; current fixing-count question remains unanswered.'})
c['interactive_review_state'].update({'current_question_id': qid, 'current_fixing_type_answer_recorded': True, 'current_owner_fixing_type': 'Keyhole', 'last_fixing_detail_decision': approval, 'review_decision_mode': cp['review_decision_mode'], 'state': cp['state']})
c['next_work'][0] = 'MCP4 Rust owner dimensions,4kg, plaster-composite faux finish and keyhole fixing type recorded. Check keyhole count and hardware details, then individual price and availability.'
summary = {'batch': 61, 'recorded_utc': now, 'receipt': rel(HERE / 'import-receipt.json'), 'scope_kind': 'MAIN_OWNER_KEYHOLE_FIXING_TYPE_ONLY', 'component_id': cid, 'size_finish_variant_id': vid, 'new_owner_fixing_type_instructions': 1, 'new_full_specification_approvals': 0, 'new_finish_name_approvals': 0, 'new_registered_BC_component_ids': [], 'root_new_private_original_downloads': 0, 'remote_mutations': 0, 'workbook_export_pending': True}
cp['parallel_import_queue'].append({'scope_kind': summary['scope_kind'], 'receipt': approval, 'approval_imported': True, 'import_receipt': summary['receipt'], 'status': 'KEYHOLE_TYPE_RECORDED;COUNT_HARDWARE_PRICE_AVAILABILITY_PENDING'})
c['parallel_import_queue'] = copy.deepcopy(cp['parallel_import_queue'])
for target, key in [(p, 'latest_parallel_import'), (cp, 'last_parallel_import'), (c, 'last_parallel_import')]: target[key] = copy.deepcopy(summary)
p['latest_main_owner_review'] = copy.deepcopy(summary)
for doc in docs.values(): doc['updated_utc'] = now
docs['root']['current_component_review'] = copy.deepcopy(c)
assert all(node['specification_proposals'][index] == before['progress']['reviews'][cid]['size_finish_variants'][vid]['specification_proposals'][index] for index in [0, 1, 2, 4, 5])
assert all(u[key] == before['user'][key] for key in ['specification_approval_counts', 'identity_confirmation_counts', 'dimension_confirmation_counts'])
assert all(sha(paths[key]) == value for key, value in guards.items()) and all(sha(path) == value for path, value in protected.items())
write(HERE / 'before-import.json', before); write(HERE / 'owner-fixing-type.json', decision); write(count_path, count_card)
files = []
for source in [card_path, HERE / 'owner-answer-evidence.json', HERE / 'current-reference-check.json']:
    dest = HERE / 'sources' / (sha(source) + '.json'); dest.parent.mkdir(exist_ok=True); dest.write_bytes(source.read_bytes()); files.append({'source': str(source), 'snapshot': rel(dest), 'sha256': sha(dest)})
write(HERE / 'source-manifest.json', {'files': files, 'verified_messages': messages})
for key, path in paths.items(): write(path, docs[key])
write(HERE / 'import-receipt.json', {'status': 'APPLIED;INDEPENDENT_READBACK_REQUIRED', 'summary': summary, 'protected_sha256': protected, 'shared_after_sha256': {key: sha(path) for key, path in paths.items()}})
print(json.dumps({'batch': 61, 'status': 'APPLIED', 'owner_stated_fixing_type': 'Keyhole', 'fixing_point_count': None, 'current_count_question_unanswered': True}))
