"""Record one owner dimension confirmation and prepare the next weight-only question."""
import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from import_source_followups_24_25 import canonical_messages

ROOT = Path(__file__).resolve().parents[2]
HERE = ROOT / 'components/reviews/parallel-import-2026-10-19-batch49'
REVIEW = ROOT / 'components/reviews/concave-to-mcp4-consolidation-2026-10-19/verdigris-rust-review'
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
rel = lambda p: str(Path(p).relative_to(ROOT))
def write(path, value):
    path = Path(path); path.parent.mkdir(exist_ok=True, parents=True); temp = path.with_name(path.name + '.tmp'); temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n'); temp.replace(path)

paths = {'user': ROOT / 'components/reviews/user_classifications.json', 'progress': ROOT / 'components/reviews/specification_review_progress.json', 'walkthrough': ROOT / 'components/reviews/walkthrough_checkpoint.json', 'component': ROOT / 'components/checkpoint.json', 'root': ROOT / 'checkpoint.json'}
docs = {k: read(v) for k, v in paths.items()}; cid, vid = 'BC-MCP-4', 'MCP4-VERDIGRIS-RUST'
did = cid + ':' + vid + ':OWNER-DIMENSIONS:LINE19184'
if (HERE / 'import-receipt.json').exists():
    assert sum(x.get('decision_id') == did for x in docs['user']['dimension_decisions']) == 1
    print(json.dumps({'batch': 49, 'status': 'ALREADY_IMPORTED_IDEMPOTENT_NO_WRITE'})); raise SystemExit
before, guards = copy.deepcopy(docs), {k: sha(v) for k, v in paths.items()}
u, p, cp, c = (docs[k] for k in ['user', 'progress', 'walkthrough', 'component'])
assert docs['root']['current_component_review'] == c and cp['current_question_id'] == 'MCP4-VERDIGRIS-RUST-DIMENSIONS-01' and not cp['current_answer_recorded']
card_path = ROOT / cp['current_review_record']; card = read(card_path)
assert sha(card_path) == read(REVIEW / 'dimension-preparation-receipt.json')['card_sha256']
evidence = read(HERE / 'owner-answer-evidence.json')
messages = canonical_messages([evidence['preceding_assistant'], evidence['owner']], '01a144ab-1a7c-7223-a403-73a4d53d70ff')
assert [x['line'] for x in messages] == [19166, 19184]
assert messages[-1]['text'] == 'Yes: Is this panel 25 × 25 cm and approximately 6 cm deep'
assert '__003.png' in messages[0]['text'] and 'approximately 6 cm deep' in messages[0]['text']
node = p['reviews'][cid]['size_finish_variants'][vid]; assert node['identity_confirmed'] and not node['proposals_approved']
assert len(node['specification_proposals']) == 6 and node['specification_proposals'][0]['proposal_id'] == 'MCP4-VERDIGRIS-RUST-DIMENSIONS'
heads = read(HERE / 'current-reference-check.json')['metadata']; head = next(x['file'] for x in heads if x.get('file')); folder = next(x['folder'] for x in heads if x.get('folder'))
ref = node['current_dropbox_reference']
assert all(head[k] == ref[v] for k, v in [('id', 'file_id'), ('rev', 'file_revision'), ('size', 'file_bytes'), ('path_display', 'file_path')])
assert folder['id'] == ref['folder_id'] and folder['path_display'] == ref['folder_path']
protected = {str(path): sha(path) for path in [card_path, ROOT / cp['register_workbook'], ROOT / 'components/evidence/component_register.json', ROOT.parent / 'Boldstone_Wall_Sculptures_Matched_All_Fields_2026-10-15.xlsx']}
now = datetime.now(timezone.utc).isoformat(); approval = rel(HERE / 'owner-dimensions.json')
decision = {'schema': 'boldstone.owner-dimensions.v1', 'decision_id': did, 'recorded_utc': now, 'component_id': cid, 'size_finish_variant_id': vid, 'canonical_name': node['canonical_name'], 'scope_kind': 'COMPLETE_DIMENSION_INSTRUCTION', 'confirmed_dimensions_cm': {'height': 25, 'width': 25, 'depth': 6}, 'depth_qualifier': 'approximately', 'depth_is_exact': False, 'physical_specs_verified': False, 'independently_measured': False, 'status': 'OWNER_CONFIRMED_FACE_AND_APPROXIMATE_DEPTH;NOT_INDEPENDENTLY_MEASURED', 'user_statement': messages[-1]['text'], 'authoritative_user_evidence': messages[-1], 'preceding_assistant_card_evidence': messages[0], 'primary_file_id': head['id'], 'primary_folder_id': folder['id'], 'image_link': ref['image_url'], 'folder_link': ref['folder_url'], 'scope': '25 ×25 cm face and approximately6 cm depth for the pictured MCP4 Verdigris and Rust source003 panel. No extension to another finish, size or physical cast. Other five specification fields remain unapproved.', 'approval_record': approval, 'prior_dimension_proposal': copy.deepcopy(node['specification_proposals'][0]), 'new_full_specification_approvals': 0, 'new_remote_mutations_or_original_downloads': 0}
u['dimension_decisions'].append(decision)
total = len(u['dimension_decisions']); complete = sum(x.get('scope_kind') == 'COMPLETE_DIMENSION_INSTRUCTION' for x in u['dimension_decisions'])
u['dimension_confirmation_counts'] = {'components': len({x['component_id'] for x in u['dimension_decisions']}), 'face_size_decisions': total - complete, 'complete_dimension_instruction_decisions': complete, 'individual_dimension_decisions': total}
proposal = node['specification_proposals'][0]
proposal.update({'display': '25 × 25 cm face; approximately 6 cm depth — owner-confirmed, not independently measured', 'value': {'height_cm': 25, 'width_cm': 25, 'overall_depth_cm': 6, 'depth_qualifier': 'approximately'}, 'status': decision['status'], 'owner_confirmed': True, 'owner_approved': False, 'owner_dimension_confirmation': approval, 'basis': 'Exact owner answer to the dimensions-only source003 question. Depth remains approximate. This does not approve the other five specification fields.'})
node.update({'owner_confirmed_dimensions_cm': decision['confirmed_dimensions_cm'], 'owner_confirmed_depth_qualifier': 'approximately', 'owner_dimension_confirmation': approval, 'specification_status_display': 'Dimensions owner-confirmed; five specification groups pending', 'specification_review_status': 'OWNER_CONFIRMED_FACE_AND_APPROX_DEPTH;OTHER_FIVE_FIELDS_PENDING', 'scope': 'Name and pictured source003 dimensions are owner-confirmed:25 ×25 cm face with approximately6 cm depth. Not independently measured. Weight, material, fixing, individual price and availability proposals remain unapproved; manufacture, exact platform match and stock remain unverified.'})
p['pending_specification_checks']['MCP4-VERDIGRIS-RUST-DIMENSIONS-01'].update({'owner_answer_recorded': True, 'approval_record': approval})
for item in cp['pending_specification_reviews']:
    if item.get('component_id') == cid and item.get('size_finish_variant_id') == vid:
        item.update({'dimensions_owner_confirmed': True, 'dimension_approval': approval, 'pending_fields': [x['field'] for x in node['specification_proposals'][1:]]})
weight_qid = 'MCP4-VERDIGRIS-RUST-WEIGHT-01'
weight_card = {'schema': 'boldstone.scoped-weight-review.v1', 'prepared_utc': now, 'question_id': weight_qid, 'component_id': cid, 'size_finish_variant_id': vid, 'canonical_name': node['canonical_name'], 'identity_already_kept': True, 'dimensions_owner_confirmed': decision['confirmed_dimensions_cm'], 'depth_qualifier': 'approximately', 'dimension_approval': approval, 'proposal': copy.deepcopy(node['specification_proposals'][1]), 'owner_question': 'Keep approximately4 kg dry weight, with a working range of3–5 kg, as an unweighed estimate for this panel, or should it be corrected?', 'current_dropbox_reference': ref, 'owner_answer_recorded': False, 'actual_measured_weight_kg': None, 'scope': 'Working dry-weight estimate only. No material, fixing, price or availability approval; no measured weight or manufacture inferred.'}
weight_path = REVIEW / 'weight-check.json'
p['pending_specification_checks'][weight_qid] = {'review_record': rel(weight_path), 'owner_answer_recorded': False, 'dimension_approval': approval}
cp.update({'current_question_id': weight_qid, 'current_review_record': rel(weight_path), 'current_answer_recorded': False, 'current_dimension_answer_recorded': True, 'current_dimension_approval': approval, 'current_partial_specification_answer_recorded': True, 'current_owner_face_dimensions_cm': [25, 25], 'current_owner_depth_cm': 6, 'current_owner_depth_qualifier': 'approximately', 'current_specification_answer_recorded': False, 'last_dimension_decision': approval, 'current_component_source_notes': [x['display'] for x in node['specification_proposals']], 'review_decision_mode': 'WORKING_DRY_WEIGHT_ONLY', 'state': 'MCP4_RUST_DIMENSIONS_RECORDED;AWAITING_WORKING_WEIGHT_CHECK', 'question_scope': weight_card['scope'], 'answer_state': 'Dimensions saved as owner-confirmed; current weight question remains unanswered.'})
c['interactive_review_state'].update({'current_question_id': weight_qid, 'current_dimension_answer_recorded': True, 'current_owner_face_dimensions_cm': [25, 25], 'current_owner_depth_cm': 6, 'current_owner_depth_qualifier': 'approximately', 'last_dimension_decision': approval, 'review_decision_mode': cp['review_decision_mode'], 'state': cp['state']})
c['next_work'][0] = 'MCP4 Rust dimensions are owner-confirmed at25×25 cm and approximately6 cm depth. Check its unweighed4 kg working estimate next, then material, fixing, price and availability.'
summary = {'batch': 49, 'recorded_utc': now, 'receipt': rel(HERE / 'import-receipt.json'), 'scope_kind': 'MAIN_OWNER_DIMENSIONS_ONLY', 'component_id': cid, 'size_finish_variant_id': vid, 'new_owner_dimension_instructions': 1, 'new_full_specification_approvals': 0, 'new_finish_name_approvals': 0, 'new_registered_BC_component_ids': [], 'root_new_private_original_downloads': 0, 'remote_mutations': 0, 'workbook_export_pending': True}
cp['parallel_import_queue'].append({'scope_kind': summary['scope_kind'], 'receipt': approval, 'approval_imported': True, 'import_receipt': summary['receipt'], 'status': 'OWNER_FACE_AND_APPROX_DEPTH_RECORDED;OTHER_FIVE_FIELDS_PENDING'})
c['parallel_import_queue'] = copy.deepcopy(cp['parallel_import_queue'])
for target, key in [(p, 'latest_parallel_import'), (cp, 'last_parallel_import'), (c, 'last_parallel_import')]: target[key] = copy.deepcopy(summary)
p['latest_main_owner_review'] = copy.deepcopy(summary)
for doc in docs.values(): doc['updated_utc'] = now
docs['root']['current_component_review'] = copy.deepcopy(c)
assert node['specification_proposals'][1:] == before['progress']['reviews'][cid]['size_finish_variants'][vid]['specification_proposals'][1:]
assert u['specification_approval_counts'] == before['user']['specification_approval_counts'] and u['identity_confirmation_counts'] == before['user']['identity_confirmation_counts']
assert all(sha(paths[k]) == v for k, v in guards.items()) and all(sha(path) == v for path, v in protected.items())
write(HERE / 'before-import.json', before); write(HERE / 'owner-dimensions.json', decision); write(weight_path, weight_card)
frozen = []
for source in [card_path, HERE / 'owner-answer-evidence.json', HERE / 'current-reference-check.json']:
    dest = HERE / 'sources' / (sha(source) + '.json'); dest.parent.mkdir(exist_ok=True); dest.write_bytes(source.read_bytes()); frozen.append({'source': str(source), 'snapshot': rel(dest), 'sha256': sha(dest)})
write(HERE / 'source-manifest.json', {'files': frozen, 'verified_messages': messages})
for k, path in paths.items(): write(path, docs[k])
write(HERE / 'import-receipt.json', {'status': 'APPLIED;INDEPENDENT_READBACK_REQUIRED', 'summary': summary, 'protected_sha256': protected, 'shared_after_sha256': {k: sha(v) for k, v in paths.items()}})
print(json.dumps({'batch': 49, 'status': 'APPLIED', 'owner_dimensions_cm': [25, 25, 6], 'depth_qualifier': 'approximately', 'other_five_fields_unchanged': True, 'current_weight_question_unanswered': True}))
