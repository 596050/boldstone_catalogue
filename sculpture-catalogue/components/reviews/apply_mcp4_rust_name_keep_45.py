"""Record the exact owner name Keep; preserve every unapproved specification."""
import copy
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from import_source_followups_24_25 import canonical_messages

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'components/scripts'))
from review_decision_counts import identity_counts
HERE = ROOT / 'components/reviews/parallel-import-2026-10-19-batch45'
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
rel = lambda p: str(Path(p).relative_to(ROOT))
def write(path, value):
    path = Path(path); path.parent.mkdir(exist_ok=True, parents=True); temp = path.with_name(path.name + '.tmp'); temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n'); temp.replace(path)

paths = {'user': ROOT / 'components/reviews/user_classifications.json', 'progress': ROOT / 'components/reviews/specification_review_progress.json', 'walkthrough': ROOT / 'components/reviews/walkthrough_checkpoint.json', 'component': ROOT / 'components/checkpoint.json', 'root': ROOT / 'checkpoint.json'}
docs = {k: read(v) for k, v in paths.items()}
cid, vid, name = 'BC-MCP-4', 'MCP4-VERDIGRIS-RUST', 'Moon Crater Phase 4 — Verdigris and Rust'
did = cid + ':' + vid + ':identity:keep'
if (HERE / 'import-receipt.json').exists():
    assert sum(x['decision_id'] == did for x in docs['user']['size_finish_variant_decisions']) == 1 and docs['progress']['reviews'][cid]['size_finish_variants'][vid]['identity_confirmed']
    print(json.dumps({'batch': 45, 'status': 'ALREADY_IMPORTED_IDEMPOTENT_NO_WRITE'})); raise SystemExit
before, guards = copy.deepcopy(docs), {k: sha(v) for k, v in paths.items()}
u, p, cp, c = (docs[k] for k in ['user', 'progress', 'walkthrough', 'component'])
assert docs['root']['current_component_review'] == c and cp['current_question_id'] == 'MCP4-VERDIGRIS-RUST-NAME-01' and not cp['current_answer_recorded']
card_path = ROOT / cp['current_review_record']; card = read(card_path)
assert sha(card_path) == read(card_path.parent / 'preparation-receipt.json')['card_sha256']
evidence = read(HERE / 'owner-answer-evidence.json')
messages = canonical_messages([evidence['preceding_assistant'], evidence['owner']], '01a144ab-1a7c-7223-a403-73a4d53d70ff')
assert [x['line'] for x in messages] == [18764, 18782] and messages[-1]['text'] == 'Keep “' + name + '”' and '__003.png' in messages[0]['text']
node = p['reviews'][cid]['size_finish_variants'][vid]; assert not node['identity_confirmed'] and len(node['specification_proposals']) == 6 and node['proposals_approved'] is False
heads = read(HERE / 'current-reference-check.json')['metadata']; head = next(x['file'] for x in heads if x.get('file')); folder = next(x['folder'] for x in heads if x.get('folder'))
ref = node['current_dropbox_reference']
assert all(head[k] == ref[v] for k, v in [('id', 'file_id'), ('path_display', 'file_path'), ('size', 'file_bytes'), ('rev', 'file_revision')])
assert folder['id'] == ref['folder_id'] and folder['path_display'] == ref['folder_path'] == head['path_display'].rsplit('/', 1)[0]
protected = {str(path): sha(path) for path in [card_path, ROOT / cp['register_workbook'], ROOT / 'components/evidence/component_register.json', ROOT.parent / 'Boldstone_Wall_Sculptures_Matched_All_Fields_2026-10-15.xlsx']}
now = datetime.now(timezone.utc).isoformat(); approval = rel(HERE / 'identity-approval.json')
scope = 'Owner kept the name and depicted Verdigris and Rust finish identity for the selected complete source003 panel. All six specification proposals remain unaccepted; no measured size, material, fixing rating, price, manufacture, mould/stock or exact Squarespace/Shopify match approved. Context remains a plain-wall presentation, with scene provenance unconfirmed.'
decision = {'schema': 'boldstone.finish-name-approval.v1', 'decision_id': did, 'recorded_utc': now, 'component_id': cid, 'size_finish_variant_id': vid, 'canonical_name': name, 'confirmed_name': name, 'identity_confirmed': True, 'name_approved': True, 'action': 'keep name and depicted finish identity', 'user_statement': messages[-1]['text'], 'scope': scope, 'authoritative_user_evidence': messages[-1], 'preceding_review_card_evidence': messages[0], 'primary_file_id': head['id'], 'primary_folder_id': folder['id'], 'image_link': ref['image_url'], 'folder_link': ref['folder_url'], 'approval_record': approval, 'proposals_approved': False, 'specifications_approved': False, 'approved_proposal_ids': [], 'physical_specs_verified': False, 'new_specification_approvals': 0, 'new_BC_ids': [], 'original_bytes_verified_now': False, 'remote_mutations': 0}
u['size_finish_variant_decisions'].append(decision); u['identity_confirmation_counts'] = identity_counts(u)
assert u['identity_confirmation_counts']['explicit_size_finish_variant_names'] == before['user']['identity_confirmation_counts']['explicit_size_finish_variant_names'] + 1
old_ids = {x['component_id'] for ledger in ['decisions', 'size_finish_variant_decisions', 'build_variant_decisions', 'build_variant_identity_decisions', 'component_layout_identity_decisions'] for x in before['user'].get(ledger, [])}
assert u['identity_confirmation_counts']['components_with_any_identity_scope'] == before['user']['identity_confirmation_counts']['components_with_any_identity_scope'] + (cid not in old_ids)
decision['canonical_component_already_exists'] = True
decision['legacy_ID_count_scope'] = 'First name-ledger entry for canonical BC-MCP-4 may increase overlapping ID count; former BC-CONCAVE remains historical. No new design or physical sculpture is created.'
node.update({'canonical_name': name, 'identity_confirmed': True, 'identity_confirmed_utc': now, 'identity_approval': approval, 'specification_review_status': 'NAME KEPT; ALL SIX SPECIFICATION PROPOSALS REMAIN UNAPPROVED', 'scope': scope})
for pending in p['reviews'][cid]['pending_size_finish_variants']:
    if pending['variant_id'] == vid: pending.update({'review_status': 'NAME AND FINISH IDENTITY KEPT; SIX SPECIFICATIONS PENDING', 'identity_approval': approval})
p['current_component_photograph_gaps'][vid]['canonical_name'] = name
p.setdefault('catalogue_family_review_status', {})['Moon Crater Phase 4'] = {'finish_names_kept': ['MCP4-WHITE', 'MCP4-SILVER-BRONZE-25', 'MCP4-VERDIGRIS-25', vid], 'finish_names_first_pass_complete': True, 'all_actual_specifications_complete': False, 'root_consolidation': 'components/reviews/concave-to-mcp4-consolidation-2026-10-19/canonical-consolidation.json'}
p['latest_size_finish_variant_identity_approval'] = approval
p['asset_assignment_overrides'][head['id']].update({'size_finish_variant_ids': [vid], 'canonical_size_finish_variant_id': vid, 'identity_approval': approval, 'assignment_status': 'OWNER_KEPT_MCP4_VERDIGRIS_RUST_SELECTED_DEPICTED_FINISH;SIX_SPECIFICATIONS_UNAPPROVED'})
cp['pending_specification_reviews'].append({'component_id': cid, 'size_finish_variant_id': vid, 'canonical_name': name, 'identity_approved': True, 'specifications_approved': False, 'pending_fields': [x['field'] for x in node['specification_proposals']], 'review_record': rel(card_path), 'identity_approval': approval, 'image_link': ref['image_url'], 'folder_link': ref['folder_url']})
cp.update({'current_answer_recorded': True, 'current_specification_answer_recorded': False, 'last_completed_size_finish_variant_id': vid, 'last_size_finish_variant_identity_approval': approval, 'last_identity_approval': approval, 'proposed_name': name, 'state': 'MCP4_FOUR_FINISH_NAMES_KEPT;SPECIFICATION_CHECKS_PENDING', 'answer_state': scope})
c['interactive_review_state'].update({'current_name': name, 'state': cp['state'], 'last_completed_size_finish_variant_id': vid, 'last_identity_approval': approval, 'explicit_size_finish_variant_names_confirmed': u['identity_confirmation_counts']['explicit_size_finish_variant_names'], 'components_with_any_identity_scope': u['identity_confirmation_counts']['components_with_any_identity_scope'], 'specification_proposals_approved': False})
c['next_work'][0] = 'Four MCP4 finish names are kept. Verify the pending coloured-finish dimensions/depth, weight, material, fixing, price and availability at their exact scopes.'
c['next_work'][4] = 'Use114 scoped photo-gap records with image and folder links; preserve context types and distinguish unreviewed coverage from absence.'
summary = {'batch': 45, 'recorded_utc': now, 'receipt': rel(HERE / 'import-receipt.json'), 'scope_kind': 'MAIN_OWNER_FINISH_NAME_ONLY', 'component_id': cid, 'size_finish_variant_id': vid, 'new_finish_name_approvals': 1, 'new_full_specification_approvals': 0, 'new_registered_BC_component_ids': [], 'root_new_private_original_downloads': 0, 'remote_mutations': 0, 'workbook_export_pending': True}
cp['parallel_import_queue'].append({'scope_kind': summary['scope_kind'], 'receipt': approval, 'approval_imported': True, 'import_receipt': summary['receipt'], 'status': 'NAME_AND_DEPICTED_FINISH_KEPT;SIX_SPECIFICATIONS_PENDING'})
c['parallel_import_queue'] = copy.deepcopy(cp['parallel_import_queue'])
for doc, key in [(p, 'latest_parallel_import'), (cp, 'last_parallel_import'), (c, 'last_parallel_import')]: doc[key] = copy.deepcopy(summary)
p['latest_main_owner_review'] = copy.deepcopy(summary)
for doc in docs.values(): doc['updated_utc'] = now
docs['root']['current_component_review'] = copy.deepcopy(c)
assert node['specification_proposals'] == before['progress']['reviews'][cid]['size_finish_variants'][vid]['specification_proposals']
assert u['specification_approval_counts'] == before['user']['specification_approval_counts'] and c['counts'] == before['component']['counts']
assert all(sha(paths[k]) == v for k, v in guards.items()) and all(sha(path) == v for path, v in protected.items())
write(HERE / 'before-import.json', before); write(HERE / 'identity-approval.json', decision); write(HERE / 'confirmed-finish-review.json', node)
files = []
for source in [card_path, HERE / 'owner-answer-evidence.json', HERE / 'current-reference-check.json']:
    dest = HERE / 'sources' / (sha(source) + '.json'); dest.parent.mkdir(exist_ok=True); dest.write_bytes(source.read_bytes()); files.append({'source': str(source), 'snapshot': rel(dest), 'sha256': sha(dest)})
write(HERE / 'source-manifest.json', {'files': files, 'verified_messages': messages})
for k, path in paths.items(): write(path, docs[k])
write(HERE / 'import-receipt.json', {'status': 'APPLIED;INDEPENDENT_READBACK_REQUIRED', 'summary': summary, 'protected_sha256': protected, 'shared_after_sha256': {k: sha(v) for k, v in paths.items()}})
print(json.dumps({'batch': 45, 'status': 'APPLIED', 'new_finish_names': 1, 'new_specification_approvals': 0, 'all_four_MCP4_finish_names_kept': True}))
