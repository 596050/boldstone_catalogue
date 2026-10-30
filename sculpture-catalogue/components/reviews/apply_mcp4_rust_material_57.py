"""Record the owner's material/finish correction for one exact MCP4 Rust panel."""
import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from import_source_followups_24_25 import canonical_messages

ROOT = Path(__file__).resolve().parents[2]
HERE = ROOT / 'components/reviews/parallel-import-2026-10-19-batch57'
REVIEW = ROOT / 'components/reviews/concave-to-mcp4-consolidation-2026-10-19/verdigris-rust-review'
read = lambda path: json.loads(Path(path).read_text())
sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
rel = lambda path: str(Path(path).relative_to(ROOT))
def write(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.tmp'); temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n'); temp.replace(path)

paths = {'user': ROOT / 'components/reviews/user_classifications.json', 'progress': ROOT / 'components/reviews/specification_review_progress.json', 'walkthrough': ROOT / 'components/reviews/walkthrough_checkpoint.json', 'component': ROOT / 'components/checkpoint.json', 'root': ROOT / 'checkpoint.json'}
docs = {key: read(path) for key, path in paths.items()}; cid, vid = 'BC-MCP-4', 'MCP4-VERDIGRIS-RUST'; did = cid + ':' + vid + ':OWNER-MATERIAL-FINISH:LINE19995'
if (HERE / 'import-receipt.json').exists():
    assert sum(item.get('decision_id') == did for item in docs['user']['material_detail_decisions']) == 1
    print(json.dumps({'batch': 57, 'status': 'ALREADY_IMPORTED_IDEMPOTENT_NO_WRITE'})); raise SystemExit
before = copy.deepcopy(docs); guards = {key: sha(path) for key, path in paths.items()}
u, p, cp, c = (docs[key] for key in ['user', 'progress', 'walkthrough', 'component'])
assert docs['root']['current_component_review'] == c and cp['current_question_id'] == 'MCP4-VERDIGRIS-RUST-MATERIAL-01' and not cp['current_answer_recorded']
card_path = ROOT / cp['current_review_record']; card = read(card_path); evidence = read(HERE / 'owner-answer-evidence.json')
messages = canonical_messages([evidence['preceding_assistant'], evidence['owner']], '01a144ab-1a7c-7223-a403-73a4d53d70ff')
assert [item['line'] for item in messages] == [19988, 19995] and messages[-1]['text'] == 'plaster composite with a faux verdigris and rust' and '__003.png' in messages[0]['text']
node = p['reviews'][cid]['size_finish_variants'][vid]; ref = node['current_dropbox_reference']; assert ref == card['current_dropbox_reference']
heads = read(HERE / 'current-reference-check.json')['metadata']; head = next(item['file'] for item in heads if item.get('file')); parent = next(item['folder'] for item in heads if item.get('folder'))
assert all(head[key] == ref[target] for key, target in [('id', 'file_id'), ('rev', 'file_revision'), ('size', 'file_bytes'), ('path_display', 'file_path')]) and parent['id'] == ref['folder_id']
assert node['specification_proposals'][2]['proposal_id'] == 'MCP4-VERDIGRIS-RUST-MATERIAL'
protected = {str(path): sha(path) for path in [card_path, ROOT / cp['register_workbook'], ROOT / 'components/evidence/component_register.json', ROOT.parent / 'Boldstone_Wall_Sculptures_Matched_All_Fields_2026-10-15.xlsx']}
now = datetime.now(timezone.utc).isoformat(); approval = rel(HERE / 'owner-material-finish.json')
decision = {'schema': 'boldstone.owner-material-finish-description.v1', 'decision_id': did, 'recorded_utc': now, 'component_id': cid, 'size_finish_variant_id': vid, 'canonical_name': node['canonical_name'], 'scope_kind': 'EXACT_PANEL_MATERIAL_AND_FINISH_DESCRIPTION', 'base_material_description': 'Plaster composite', 'surface_finish_description': 'Faux verdigris and rust finish', 'sand_content_confirmed': False, 'formulation_filler_reinforcement_and_sealer': 'UNCONFIRMED', 'complete_material_group_approved': False, 'physical_specs_verified': False, 'independently_material_verified': False, 'status': 'OWNER_STATED_PLASTER_COMPOSITE_AND_FAUX_VERDIGRIS_RUST_FINISH;FORMULATION_UNCONFIRMED', 'user_statement': messages[-1]['text'], 'authoritative_user_evidence': messages[-1], 'preceding_assistant_card_evidence': messages[0], 'primary_file_id': ref['file_id'], 'primary_folder_id': ref['folder_id'], 'image_link': ref['image_url'], 'folder_link': ref['folder_url'], 'scope': 'Owner corrects the material to plaster composite and states a faux verdigris/rust finish for this source003 panel. Replace the prior sand/plaster description; do not infer a sand-free formulation or any filler, metal content, reinforcement or sealer. Fixing, individual price and availability remain pending. No transfer to another finish.', 'approval_record': approval, 'prior_material_proposal': copy.deepcopy(node['specification_proposals'][2]), 'new_full_specification_approvals': 0}
u['material_detail_decisions'].append(decision)
node['specification_proposals'][2].update({'display': 'Plaster composite with a faux verdigris and rust finish — owner-stated; formulation and coating details unconfirmed', 'value': {'base_material': 'Plaster composite', 'surface_finish': 'Faux verdigris and rust finish'}, 'status': decision['status'], 'owner_confirmed': True, 'owner_approved': False, 'owner_material_confirmation': approval, 'basis': 'Exact owner correction for source003. Binder formulation, filler composition, metal content, reinforcement and sealer remain unknown. No fixing, price or availability approval.'})
node.update({'owner_stated_base_material': 'Plaster composite', 'owner_stated_surface_finish': 'Faux verdigris and rust finish', 'owner_material_confirmation': approval, 'material_formulation_verified': False, 'specification_status_display': 'Dimensions, weight and material/finish owner-stated; three specification groups pending', 'specification_review_status': 'OWNER_DIMENSIONS_WEIGHT_AND_MATERIAL_DESCRIPTION_RECORDED;FIXING_PRICE_AVAILABILITY_PENDING', 'scope': 'Name and source003 face25×25cm with approximately6cm depth are owner-confirmed. Dry weight4kg and plaster composite with faux verdigris/rust finish are owner-stated. Weighing method, formulation and coating details remain unverified. Fixing, individual price and availability are pending. Owner-wide manufacture statement51 retained; exact platform match and current stock remain unconfirmed.'})
p['pending_specification_checks']['MCP4-VERDIGRIS-RUST-MATERIAL-01'].update({'owner_answer_recorded': True, 'approval_record': approval})
for item in cp['pending_specification_reviews']:
    if item.get('component_id') == cid and item.get('size_finish_variant_id') == vid:
        item.update({'material_finish_owner_stated': True, 'material_approval': approval, 'pending_fields': [proposal['field'] for proposal in node['specification_proposals'][3:]]})
qid = 'MCP4-VERDIGRIS-RUST-FIXING-01'; fixing_path = REVIEW / 'fixing-check.json'
fixing_card = {'schema': 'boldstone.scoped-fixing-review.v1', 'prepared_utc': now, 'question_id': qid, 'component_id': cid, 'size_finish_variant_id': vid, 'canonical_name': node['canonical_name'], 'identity_already_kept': True, 'owner_stated_material': decision['base_material_description'], 'owner_stated_finish': decision['surface_finish_description'], 'material_approval': approval, 'proposal': copy.deepcopy(node['specification_proposals'][3]), 'owner_question': 'Does this panel have one concealed rear hanging point, or a different fixing?', 'current_dropbox_reference': copy.deepcopy(ref), 'photo_coverage': copy.deepcopy(node['photo_coverage']), 'owner_answer_recorded': False, 'actual_fixing_hardware_or_load_rating_verified': False, 'scope': 'Fixing type/count only: one concealed rear hanging point is an unapproved proposal from a related finish. No rear image for this Rust panel established in the reviewed folder. Hardware, attachment and load capacity remain unknown; price and availability remain pending.'}
p['pending_specification_checks'][qid] = {'review_record': rel(fixing_path), 'owner_answer_recorded': False, 'material_approval': approval}
cp.update({'current_question_id': qid, 'current_review_record': rel(fixing_path), 'current_answer_recorded': False, 'current_material_answer_recorded': True, 'current_material_approval': approval, 'current_owner_base_material': decision['base_material_description'], 'current_owner_surface_finish': decision['surface_finish_description'], 'current_fixing_answer_recorded': False, 'current_specification_answer_recorded': False, 'current_partial_specification_answer_recorded': True, 'last_material_decision': approval, 'current_component_source_notes': [proposal['display'] for proposal in node['specification_proposals']], 'review_decision_mode': 'FIXING_TYPE_AND_COUNT_ONLY', 'state': 'MCP4_RUST_OWNER_DIMENSIONS_WEIGHT_MATERIAL_RECORDED;AWAITING_FIXING', 'question_scope': fixing_card['scope'], 'answer_state': 'Dimensions,4kg and material/finish recorded; current fixing question remains unanswered.'})
c['interactive_review_state'].update({'current_question_id': qid, 'current_material_answer_recorded': True, 'current_owner_base_material': decision['base_material_description'], 'current_owner_surface_finish': decision['surface_finish_description'], 'last_material_decision': approval, 'review_decision_mode': cp['review_decision_mode'], 'state': cp['state']})
c['next_work'][0] = 'MCP4 Rust:25×25cm and approximately6cm depth confirmed; dry weight4kg and plaster composite with faux verdigris/rust finish owner-stated. Check fixing, then individual price and availability.'
summary = {'batch': 57, 'recorded_utc': now, 'receipt': rel(HERE / 'import-receipt.json'), 'scope_kind': 'MAIN_OWNER_MATERIAL_FINISH_DESCRIPTION', 'component_id': cid, 'size_finish_variant_id': vid, 'new_owner_material_finish_instructions': 1, 'new_full_specification_approvals': 0, 'new_finish_name_approvals': 0, 'new_registered_BC_component_ids': [], 'root_new_private_original_downloads': 0, 'remote_mutations': 0, 'workbook_export_pending': True}
cp['parallel_import_queue'].append({'scope_kind': summary['scope_kind'], 'receipt': approval, 'approval_imported': True, 'import_receipt': summary['receipt'], 'status': 'OWNER_MATERIAL_DESCRIPTION_RECORDED;THREE_FIELDS_PENDING'})
c['parallel_import_queue'] = copy.deepcopy(cp['parallel_import_queue'])
for target, key in [(p, 'latest_parallel_import'), (cp, 'last_parallel_import'), (c, 'last_parallel_import')]: target[key] = copy.deepcopy(summary)
p['latest_main_owner_review'] = copy.deepcopy(summary)
for doc in docs.values(): doc['updated_utc'] = now
docs['root']['current_component_review'] = copy.deepcopy(c)
assert all(node['specification_proposals'][index] == before['progress']['reviews'][cid]['size_finish_variants'][vid]['specification_proposals'][index] for index in [0, 1, 3, 4, 5])
assert all(u[key] == before['user'][key] for key in ['specification_approval_counts', 'identity_confirmation_counts', 'dimension_confirmation_counts'])
assert all(sha(paths[key]) == value for key, value in guards.items()) and all(sha(path) == value for path, value in protected.items())
write(HERE / 'before-import.json', before); write(HERE / 'owner-material-finish.json', decision); write(fixing_path, fixing_card)
files = []
for source in [card_path, HERE / 'owner-answer-evidence.json', HERE / 'current-reference-check.json']:
    dest = HERE / 'sources' / (sha(source) + '.json'); dest.parent.mkdir(exist_ok=True); dest.write_bytes(source.read_bytes()); files.append({'source': str(source), 'snapshot': rel(dest), 'sha256': sha(dest)})
write(HERE / 'source-manifest.json', {'files': files, 'verified_messages': messages})
for key, path in paths.items(): write(path, docs[key])
write(HERE / 'import-receipt.json', {'status': 'APPLIED;INDEPENDENT_READBACK_REQUIRED', 'summary': summary, 'protected_sha256': protected, 'shared_after_sha256': {key: sha(path) for key, path in paths.items()}})
print(json.dumps({'batch': 57, 'status': 'APPLIED', 'owner_stated_material': 'Plaster composite with a faux verdigris and rust finish', 'three_fields_pending': True, 'current_fixing_question_unanswered': True}))
