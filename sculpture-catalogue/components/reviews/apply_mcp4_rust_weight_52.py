"""Record the exact owner weight answer and prepare one material/finish question."""
import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from import_source_followups_24_25 import canonical_messages

ROOT = Path(__file__).resolve().parents[2]
HERE = ROOT / 'components/reviews/parallel-import-2026-10-19-batch52'
REVIEW = ROOT / 'components/reviews/concave-to-mcp4-consolidation-2026-10-19/verdigris-rust-review'
read = lambda path: json.loads(Path(path).read_text())
sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
rel = lambda path: str(Path(path).relative_to(ROOT))
def write(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.tmp'); temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n'); temp.replace(path)

paths = {'user': ROOT / 'components/reviews/user_classifications.json', 'progress': ROOT / 'components/reviews/specification_review_progress.json', 'walkthrough': ROOT / 'components/reviews/walkthrough_checkpoint.json', 'component': ROOT / 'components/checkpoint.json', 'root': ROOT / 'checkpoint.json'}
docs = {key: read(path) for key, path in paths.items()}
cid, vid = 'BC-MCP-4', 'MCP4-VERDIGRIS-RUST'
did = cid + ':' + vid + ':OWNER-WEIGHT:LINE19523'
if (HERE / 'import-receipt.json').exists():
    assert sum(item.get('decision_id') == did for item in docs['user'].get('weight_decisions', [])) == 1
    print(json.dumps({'batch': 52, 'status': 'ALREADY_IMPORTED_IDEMPOTENT_NO_WRITE'})); raise SystemExit
before = copy.deepcopy(docs); guards = {key: sha(path) for key, path in paths.items()}
u, p, cp, c = (docs[key] for key in ['user', 'progress', 'walkthrough', 'component'])
assert docs['root']['current_component_review'] == c and cp['current_question_id'] == 'MCP4-VERDIGRIS-RUST-WEIGHT-01' and not cp['current_answer_recorded']
card_path = ROOT / cp['current_review_record']; card = read(card_path)
evidence = read(HERE / 'owner-answer-evidence.json')
messages = canonical_messages([evidence['preceding_assistant'], evidence['owner']], '01a144ab-1a7c-7223-a403-73a4d53d70ff')
assert [item['line'] for item in messages] == [19516, 19523] and messages[-1]['text'] == '4 kg'
assert '__003.png' in messages[0]['text'] and 'approximately 4 kg' in messages[0]['text']
node = p['reviews'][cid]['size_finish_variants'][vid]; ref = node['current_dropbox_reference']
assert ref == card['current_dropbox_reference'] and ref['file_id'] == 'id:cnqzTNngPVsAAAAAAAylRA' and ref['folder_id'] == 'id:cnqzTNngPVsAAAAAAAyipA'
assert node['identity_confirmed'] and node['owner_confirmed_dimensions_cm'] == {'height': 25, 'width': 25, 'depth': 6}
assert node['specification_proposals'][1]['proposal_id'] == 'MCP4-VERDIGRIS-RUST-WEIGHT'
protected = {str(path): sha(path) for path in [card_path, ROOT / cp['register_workbook'], ROOT / 'components/evidence/component_register.json', ROOT.parent / 'Boldstone_Wall_Sculptures_Matched_All_Fields_2026-10-15.xlsx']}
now = datetime.now(timezone.utc).isoformat(); approval = rel(HERE / 'owner-weight.json')
decision = {'schema': 'boldstone.owner-weight.v1', 'decision_id': did, 'recorded_utc': now, 'component_id': cid, 'size_finish_variant_id': vid, 'canonical_name': node['canonical_name'], 'scope_kind': 'INDIVIDUAL_DRY_WEIGHT_INSTRUCTION', 'owner_stated_weight_kg': 4, 'weight_basis': 'dry weight from the preceding exact-panel question', 'measurement_method': 'UNCONFIRMED', 'actual_measured_weight_kg': None, 'independently_weighed': False, 'physical_specs_verified': False, 'prior_estimated_range_approved': False, 'status': 'OWNER_STATED_DRY_WEIGHT;WEIGHING_METHOD_UNCONFIRMED;NOT_INDEPENDENTLY_WEIGHED', 'user_statement': messages[-1]['text'], 'authoritative_user_evidence': messages[-1], 'preceding_assistant_card_evidence': messages[0], 'primary_file_id': ref['file_id'], 'primary_folder_id': ref['folder_id'], 'image_link': ref['image_url'], 'folder_link': ref['folder_url'], 'scope': 'Owner states4kg for this exact MCP4 Verdigris and Rust source003 panel. Dry-weight context retained. No measurement method or confirmation of the earlier3–5kg estimate range inferred. Material, fixing, price and availability remain pending. Other finish weights unchanged.', 'approval_record': approval, 'prior_weight_proposal': copy.deepcopy(node['specification_proposals'][1]), 'new_full_specification_approvals': 0}
u.setdefault('weight_decisions', []).append(decision)
u['weight_confirmation_counts'] = {'components': len({item['component_id'] for item in u['weight_decisions']}), 'individual_weight_decisions': len(u['weight_decisions']), 'counts_scope': 'Scoped owner weight statements, separate from whole-specification approvals and physical stock counts.'}
node['specification_proposals'][1].update({'display': '4 kg dry — owner-stated; weighing method unconfirmed', 'value': {'weight_kg': 4, 'basis': 'dry'}, 'status': decision['status'], 'owner_confirmed': True, 'owner_approved': False, 'owner_weight_confirmation': approval, 'basis': 'Exact owner reply4kg to the dry-weight-only source003 question. Retain4kg as owner-stated; no independent weighing or approval of the prior3–5kg range. Other four pending fields are unchanged.'})
node.update({'owner_stated_weight_kg': 4, 'owner_weight_confirmation': approval, 'actual_measured_weight_kg': None, 'weight_measurement_method': 'UNCONFIRMED', 'specification_status_display': 'Dimensions and weight owner-stated; four specification groups pending', 'specification_review_status': 'OWNER_CONFIRMED_FACE_AND_APPROX_DEPTH;OWNER_STATED_DRY_WEIGHT;OTHER_FOUR_FIELDS_PENDING', 'scope': 'Name and source003 face25×25cm and approximately6cm depth are owner-confirmed. Dry weight4kg is owner-stated; weighing method unconfirmed. Material, fixing, individual price and availability remain pending. Manufacture is covered by the catalogue-wide owner statement51; exact platform match and current stock remain unconfirmed.'})
p['pending_specification_checks']['MCP4-VERDIGRIS-RUST-WEIGHT-01'].update({'owner_answer_recorded': True, 'approval_record': approval})
for item in cp['pending_specification_reviews']:
    if item.get('component_id') == cid and item.get('size_finish_variant_id') == vid:
        item.update({'weight_owner_stated': True, 'weight_approval': approval, 'pending_fields': [proposal['field'] for proposal in node['specification_proposals'][2:]]})
qid = 'MCP4-VERDIGRIS-RUST-MATERIAL-01'; material_path = REVIEW / 'material-finish-check.json'
material_card = {'schema': 'boldstone.scoped-material-finish-review.v1', 'prepared_utc': now, 'question_id': qid, 'component_id': cid, 'size_finish_variant_id': vid, 'canonical_name': node['canonical_name'], 'identity_already_kept': True, 'dimensions_owner_confirmed': copy.deepcopy(node['owner_confirmed_dimensions_cm']), 'depth_qualifier': 'approximately', 'owner_stated_dry_weight_kg': 4, 'weight_approval': approval, 'proposal': copy.deepcopy(node['specification_proposals'][2]), 'owner_question': 'Is the material a sand/plaster composite with a faux verdigris and rust finish, or should this proposal be corrected?', 'current_dropbox_reference': copy.deepcopy(ref), 'photo_coverage': copy.deepcopy(node['photo_coverage']), 'owner_answer_recorded': False, 'actual_material_verified': False, 'scope': 'Material/finish only: an unapproved working proposal. Binder, metal content, reinforcement and sealer remain unknown. No fixing, price, availability or other-finish approval.'}
p['pending_specification_checks'][qid] = {'review_record': rel(material_path), 'owner_answer_recorded': False, 'weight_approval': approval}
cp.update({'current_question_id': qid, 'current_review_record': rel(material_path), 'current_answer_recorded': False, 'current_weight_answer_recorded': True, 'current_weight_approval': approval, 'current_owner_dry_weight_kg': 4, 'current_weight_measurement_method': 'UNCONFIRMED', 'current_material_answer_recorded': False, 'current_specification_answer_recorded': False, 'current_partial_specification_answer_recorded': True, 'last_weight_decision': approval, 'current_component_source_notes': [proposal['display'] for proposal in node['specification_proposals']], 'review_decision_mode': 'MATERIAL_FINISH_ONLY', 'state': 'MCP4_RUST_OWNER_DIMENSIONS_AND_WEIGHT_RECORDED;AWAITING_MATERIAL_FINISH', 'question_scope': material_card['scope'], 'answer_state': 'Dimensions and4kg weight recorded; current material/finish question remains unanswered.'})
c['interactive_review_state'].update({'current_question_id': qid, 'current_weight_answer_recorded': True, 'current_owner_dry_weight_kg': 4, 'current_weight_measurement_method': 'UNCONFIRMED', 'last_weight_decision': approval, 'review_decision_mode': cp['review_decision_mode'], 'state': cp['state']})
c['next_work'][0] = 'MCP4 Rust dimensions25×25cm and approximately6cm depth confirmed; dry weight4kg owner-stated. Check material/finish, then fixing, individual price and availability.'
summary = {'batch': 52, 'recorded_utc': now, 'receipt': rel(HERE / 'import-receipt.json'), 'scope_kind': 'MAIN_OWNER_DRY_WEIGHT_ONLY', 'component_id': cid, 'size_finish_variant_id': vid, 'new_owner_weight_instructions': 1, 'new_full_specification_approvals': 0, 'new_finish_name_approvals': 0, 'new_registered_BC_component_ids': [], 'root_new_private_original_downloads': 0, 'remote_mutations': 0, 'workbook_export_pending': True}
cp['parallel_import_queue'].append({'scope_kind': summary['scope_kind'], 'receipt': approval, 'approval_imported': True, 'import_receipt': summary['receipt'], 'status': 'OWNER_WEIGHT4KG_RECORDED;OTHER_FOUR_FIELDS_PENDING'})
c['parallel_import_queue'] = copy.deepcopy(cp['parallel_import_queue'])
for target, key in [(p, 'latest_parallel_import'), (cp, 'last_parallel_import'), (c, 'last_parallel_import')]: target[key] = copy.deepcopy(summary)
p['latest_main_owner_review'] = copy.deepcopy(summary)
for doc in docs.values(): doc['updated_utc'] = now
docs['root']['current_component_review'] = copy.deepcopy(c)
assert [item for index, item in enumerate(node['specification_proposals']) if index != 1] == [item for index, item in enumerate(before['progress']['reviews'][cid]['size_finish_variants'][vid]['specification_proposals']) if index != 1]
assert all(u[key] == before['user'][key] for key in ['specification_approval_counts', 'identity_confirmation_counts', 'dimension_confirmation_counts'])
assert all(sha(paths[key]) == value for key, value in guards.items()) and all(sha(path) == value for path, value in protected.items())
write(HERE / 'before-import.json', before); write(HERE / 'owner-weight.json', decision); write(material_path, material_card)
frozen = []
for source in [card_path, HERE / 'owner-answer-evidence.json']:
    dest = HERE / 'sources' / (sha(source) + '.json'); dest.parent.mkdir(exist_ok=True); dest.write_bytes(source.read_bytes()); frozen.append({'source': str(source), 'snapshot': rel(dest), 'sha256': sha(dest)})
write(HERE / 'source-manifest.json', {'files': frozen, 'verified_messages': messages})
for key, path in paths.items(): write(path, docs[key])
write(HERE / 'import-receipt.json', {'status': 'APPLIED;INDEPENDENT_READBACK_REQUIRED', 'summary': summary, 'protected_sha256': protected, 'shared_after_sha256': {key: sha(path) for key, path in paths.items()}})
print(json.dumps({'batch': 52, 'status': 'APPLIED', 'owner_stated_dry_weight_kg': 4, 'four_other_fields_pending': True, 'current_material_question_unanswered': True}))
