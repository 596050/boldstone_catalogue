"""Accept the owner's six Gold1 working values without certifying actual specifications."""
import copy
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from import_source_followups_24_25 import canonical_messages

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'components/scripts'))
from review_decision_counts import specification_counts
BATCH = int(sys.argv[1]) if len(sys.argv) > 1 else 56
assert BATCH in [56, 59]
HERE = ROOT / f'components/reviews/parallel-import-2026-10-19-batch{BATCH}'
SOURCE = ROOT / ('components/parallel-reviews/brancusi-gold-finishes-2026-10-19/' + ('one' if BATCH == 56 else 'two') + '-gold-leaf/working-specification-review/owner-working-specs-keep')
read = lambda path: json.loads(Path(path).read_text())
sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
rel = lambda path: str(Path(path).relative_to(ROOT))
def write(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.tmp'); temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n'); temp.replace(path)

paths = {'user': ROOT / 'components/reviews/user_classifications.json', 'progress': ROOT / 'components/reviews/specification_review_progress.json', 'walkthrough': ROOT / 'components/reviews/walkthrough_checkpoint.json', 'component': ROOT / 'components/checkpoint.json', 'root': ROOT / 'checkpoint.json'}
docs = {key: read(path) for key, path in paths.items()}; number = 1 if BATCH == 56 else 2; cid, vid = f'BC-BR-{number}', f'BR-{number}-GOLD-LEAF'; other_cid = 'BC-BR-2' if number == 1 else 'BC-BR-1'
if (HERE / 'import-receipt.json').exists():
    assert docs['progress']['reviews'][cid]['size_finish_variants'][vid]['owner_estimates_accepted']
    print(json.dumps({'batch': BATCH, 'status': 'ALREADY_IMPORTED_IDEMPOTENT_NO_WRITE'})); raise SystemExit
package_path = SOURCE / 'IMPORT_PACKAGE.json'; digest = '2e1db6f6c2a4864651e8e1808614156bc39187cfc213401b48e512d4f4a72d56' if BATCH == 56 else 'e1ff5c027c4bc2ac29ca9b0774b4503ea9890b6bf7c947b7ae24d5032e199075'
assert sha(package_path) == digest
package = read(package_path); files = []
for item in [{'path': str(package_path), 'sha256': digest}, package['manifest'], *read(package['manifest']['path'])['files']]:
    path = Path(item['path']); assert sha(path) == item['sha256']
    dest = HERE / 'sources' / (item['sha256'] + path.suffix); dest.parent.mkdir(parents=True, exist_ok=True); dest.write_bytes(path.read_bytes()); files.append({'source': str(path), 'snapshot': rel(dest), 'sha256': item['sha256']})
decision = read(package['decision']['path']); assert sha(package['decision']['path']) == ('040685d103960c2fd716fafe5fa44e7e67ee2a623189650dbf66dd335d5d8073' if BATCH == 56 else '36273933ae9b0b3a7512d5b9e8231be4076d7248a994f9f5c1325d77eb3107fe')
messages = canonical_messages([item | {'transcript': item['transcript_path']} for item in [decision['preceding_review_card_evidence'], decision['authoritative_user_evidence']]], package['source_owner_session'])
assert [item['line'] for item in messages] == ([27301, 27308] if BATCH == 56 else [27665, 27672])
assert messages[-1]['text'] == ('Keep these six working specifications for Brancusi 1 — Gold Leaf, with the estimates still labelled' if BATCH == 56 else 'yes')
assert ('__008.png' if BATCH == 56 else '__011.png') in messages[0]['text'] and f'Brancusi {number} — Gold Leaf' in messages[0]['text'] and 'with the estimates still labelled' in messages[0]['text']
before = copy.deepcopy(docs); guards = {key: sha(path) for key, path in paths.items()}
u, p, cp, c = (docs[key] for key in ['user', 'progress', 'walkthrough', 'component']); node = p['reviews'][cid]['size_finish_variants'][vid]
assert docs['root']['current_component_review'] == c and node['identity_confirmed'] and not node['proposals_approved']
assert node['specification_proposals'] == decision['source_specifications_retained'] == read(decision['source_review_before_answer']['path'])['specifications']
assert all(not item['owner_approved'] for item in node['specification_proposals'].values())
heads = read(HERE / 'current-reference-check.json')['metadata']; head = next(item['file'] for item in heads if item.get('file')); parent = next(item['folder'] for item in heads if item.get('folder')); ref = node['current_dropbox_reference']
assert all(head[key] == ref[target] for key, target in [('id', 'file_id'), ('rev', 'file_revision'), ('size', 'file_bytes'), ('path_display', 'file_path')]) and parent['id'] == ref['folder_id']
protected = {str(path): sha(path) for path in [ROOT / cp['register_workbook'], ROOT / cp['current_review_record'], ROOT / 'components/evidence/component_register.json', ROOT.parent / 'Boldstone_Wall_Sculptures_Matched_All_Fields_2026-10-15.xlsx']}
now = datetime.now(timezone.utc).isoformat(); approval = rel(HERE / 'working-specification-approval.json')
fields = list(decision['approved_field_groups']); assert len(fields) == 6 and set(fields) == set(node['specification_proposals'])
source_ids = copy.deepcopy(decision['approved_proposal_ids']); scoped_ids = [vid + ':' + field.upper() for field in fields]
decision.update({'imported_utc': now, 'approval_record': approval, 'source_approved_proposal_ids': source_ids, 'approved_proposal_ids': scoped_ids, 'authoritative_user_evidence': messages[-1], 'verified_review_card_evidence': messages[0], 'shared_master_import_performed': True})
assert not any(item.get('decision_id') == decision['decision_id'] for item in u['size_finish_variant_specification_decisions'])
u['size_finish_variant_specification_decisions'].append(decision); u['specification_approval_counts'] = specification_counts(u)
assert u['specification_approval_counts']['proposal_groups'] == before['user']['specification_approval_counts']['proposal_groups'] + 6 == (76 if BATCH == 56 else 82)
assert u['specification_approval_counts']['size_finish_variant_approvals'] == before['user']['specification_approval_counts']['size_finish_variant_approvals'] + 1
node.update({'specifications_approved': True, 'proposals_approved': True, 'owner_estimates_accepted': True, 'approved_proposal_ids': scoped_ids, 'specification_approval': approval, 'working_specifications_approval_scope': 'EXACT_FINISH_ALL_SIX_WORKING_VALUES', 'all_six_working_specification_fields_accepted': True, 'physical_specs_verified': False, 'fully_confirmed_specification_groups': [], 'source_specification_proposals_retained_unchanged': True, 'accepted_working_specifications': copy.deepcopy(decision['specifications']), 'specification_status_display': 'Six working specifications accepted; estimates and unknowns retained', 'scope': f'Owner kept all six Gold{number} working specifications with estimate, guess and proposal labels retained. Original source proposal dictionaries unchanged; acceptance is recorded as an exact-finish overlay. Actual Gold substrate, leaf type, measured dimensions/weight, fixing/load rating, current offer, stock and lead time remain unverified. Prior name and context-image limitations retained. No transfer to the other Brancusi component, White panels or a diptych.'})
p.setdefault('pending_specification_checks', {})[vid + '-WORKING-SPECS-01'] = {'owner_answer_recorded': True, 'approval_record': approval, 'working_values_accepted': True, 'actual_specification_fields_pending': fields, 'physical_specs_verified': False}
c['interactive_review_state']['approved_proposal_groups'] = u['specification_approval_counts']['proposal_groups']
summary = {'batch': BATCH, 'recorded_utc': now, 'receipt': rel(HERE / 'import-receipt.json'), 'scope_kind': f'EXACT_GOLD{number}_FINISH_SIX_WORKING_SPECIFICATIONS', 'component_id': cid, 'size_finish_variant_id': vid, 'new_working_specification_approvals': 1, 'new_accepted_working_proposal_groups': 6, 'new_physically_verified_specification_groups': 0, 'new_name_approvals': 0, 'new_owner_policy_events': 0, 'new_registered_BC_component_ids': [], 'root_new_private_original_downloads': 0, 'remote_mutations': 0, 'workbook_export_pending': True}
cp['parallel_import_queue'].append({'scope_kind': summary['scope_kind'], 'receipt': rel(package_path), 'receipt_sha256': digest, 'approval_imported': True, 'import_receipt': summary['receipt'], 'status': 'SIX_WORKING_VALUES_KEPT;ESTIMATES_UNKNOWN_DETAILS_RETAINED;ACTUAL_SPECIFICATIONS_UNVERIFIED'})
c['parallel_import_queue'] = copy.deepcopy(cp['parallel_import_queue'])
for target, key in [(p, 'latest_parallel_import'), (cp, 'last_parallel_import'), (c, 'last_parallel_import')]: target[key] = copy.deepcopy(summary)
for doc in docs.values(): doc['updated_utc'] = now
docs['root']['current_component_review'] = copy.deepcopy(c)
assert node['specification_proposals'] == before['progress']['reviews'][cid]['size_finish_variants'][vid]['specification_proposals']
assert node['photo_coverage'] == before['progress']['reviews'][cid]['size_finish_variants'][vid]['photo_coverage'] and p['reviews'][other_cid] == before['progress']['reviews'][other_cid]
assert all(cp[key] == value for key, value in before['walkthrough'].items() if key.startswith('current_')) and all(sha(paths[key]) == value for key, value in guards.items()) and all(sha(path) == value for path, value in protected.items())
write(HERE / 'before-import.json', before); write(HERE / 'working-specification-approval.json', decision); write(HERE / 'accepted-working-review.json', node); write(HERE / 'source-manifest.json', {'files': files, 'verified_messages': messages})
for key, path in paths.items(): write(path, docs[key])
write(HERE / 'import-receipt.json', {'status': 'APPLIED;INDEPENDENT_READBACK_REQUIRED', 'summary': summary, 'decision_id': decision['decision_id'], 'protected_sha256': protected, 'shared_after_sha256': {key: sha(path) for key, path in paths.items()}})
print(json.dumps({'batch': BATCH, 'status': 'APPLIED', 'accepted_working_proposal_groups': u['specification_approval_counts']['proposal_groups'], 'other_Brancusi_component_unchanged': True, 'actual_specs_verified': False, 'root_active_question_preserved': True}))
