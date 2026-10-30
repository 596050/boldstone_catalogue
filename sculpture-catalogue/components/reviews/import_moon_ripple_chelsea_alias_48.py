"""Consolidate one exact source under an existing catalogue design, with scoped specs."""
import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from import_source_followups_24_25 import canonical_messages

ROOT = Path(__file__).resolve().parents[2]
HERE = ROOT / 'components/reviews/parallel-import-2026-10-19-batch48'
SOURCE = ROOT / 'components/parallel-reviews/moon-ripple-chelsea-source-2026-10-19/owner-consolidation'
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
rel = lambda p: str(Path(p).relative_to(ROOT))
def write(path, value):
    path = Path(path); path.parent.mkdir(exist_ok=True, parents=True); temp = path.with_name(path.name + '.tmp'); temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n'); temp.replace(path)

paths = {'user': ROOT / 'components/reviews/user_classifications.json', 'progress': ROOT / 'components/reviews/specification_review_progress.json', 'walkthrough': ROOT / 'components/reviews/walkthrough_checkpoint.json', 'component': ROOT / 'components/checkpoint.json', 'root': ROOT / 'checkpoint.json'}
docs = {k: read(v) for k, v in paths.items()}; cid, sid = 'BC-CHELSEA', 'SOURCE-G233002'
if (HERE / 'import-receipt.json').exists():
    assert docs['progress']['source_identity_consolidations'][sid]['canonical_component_id'] == cid
    print(json.dumps({'batch': 48, 'status': 'ALREADY_IMPORTED_IDEMPOTENT_NO_WRITE'})); raise SystemExit
before, guards = copy.deepcopy(docs), {k: sha(v) for k, v in paths.items()}
package_path = SOURCE / 'IMPORT_PACKAGE.json'; digest = '2a382cdf408898e7b10ec7747af27f47631cee9ba6674cf230c25518221916e3'
assert sha(package_path) == digest
package = read(package_path); frozen = []
def freeze(path, expected):
    path = Path(path); assert sha(path) == expected
    dest = HERE / 'sources' / (expected + path.suffix); dest.parent.mkdir(exist_ok=True); dest.write_bytes(path.read_bytes())
    frozen.append({'source': str(path), 'snapshot': rel(dest), 'sha256': expected, 'bytes': dest.stat().st_size})
    return rel(dest)
freeze(package_path, digest); freeze(package['manifest']['path'], package['manifest']['sha256'])
for name, expected in read(package['manifest']['path'])['files'].items(): freeze(SOURCE / name, expected)
decision = read(package['decision']['path']); review = read(SOURCE / 'REVIEW_BEFORE_ANSWER.json')
evidence = [decision['preceding_assistant_card_evidence'], decision['authoritative_user_evidence']]
messages = canonical_messages([x | {'transcript': x['transcript_path']} for x in evidence], package['source_owner_session'])
assert [x['line'] for x in messages] == [26869, 26876] and messages[-1]['text'] == 'Yes is, they should be consolidated'
assert 'moon-ripple-white__002.png' in messages[0]['text'] and 'chelsea-moonwave-white__001.png' in messages[0]['text']
heads = read(HERE / 'current-reference-check.json')['metadata']
for old in decision['current_references']:
    new = next(x['file'] for x in heads if x.get('file', {}).get('id') == old['id'])
    assert all(new[k] == old[k] for k in ['id', 'name', 'size', 'rev', 'path_display'])
for old in [decision['primary_folder_id'], decision['comparison_folder_id']]: assert any(x.get('folder', {}).get('id') == old for x in heads)
for source in review['cached_image_verification'].values():
    assert Path(source['path']).stat().st_size == source['bytes']; freeze(source['path'], source['sha256'])
freeze(HERE / 'current-reference-check.json', sha(HERE / 'current-reference-check.json'))
u, p, cp, c = (docs[k] for k in ['user', 'progress', 'walkthrough', 'component'])
assert docs['root']['current_component_review'] == c and cp['current_question_id'] == 'MCP4-VERDIGRIS-RUST-DIMENSIONS-01' and not cp['current_answer_recorded']
parent = p['reviews'][cid]; assert parent['identity_confirmed'] and parent['canonical_name'] == 'Chelsea Moonwave'
now = datetime.now(timezone.utc).isoformat(); approval = rel(HERE / 'owner-source-consolidation.json')
decision.update({'shared_master_import_performed': True, 'shared_imported_utc': now, 'approval_record': approval, 'verified_authoritative_user': messages[-1]})
u.setdefault('source_identity_consolidation_decisions', []).append(decision)
source = next(x['file'] for x in heads if x.get('file', {}).get('id') == decision['primary_file_id'])
folder = next(x['folder'] for x in heads if x.get('folder', {}).get('id') == decision['primary_folder_id'])
proposals = []
for index, item in enumerate(review['specification_review_items']):
    proposals.append({'proposal_id': sid + '-SPEC-' + str(index + 1), 'field': item['field'], 'display': item['detail'], 'status': 'UNAPPROVED_SOURCE_SPECIFICATION;CHELSEA250x100_NOT_INHERITED', 'owner_approved': False, 'basis': 'Exact G233002 source-specific proposal. Owner confirmed design/name only; no size, mass, material, fixing, price or availability transfer from the older Chelsea reference.'})
scope = 'Owner confirmed Moon Ripple source002 as the same Chelsea Moonwave design and requested one canonical catalogue identity. Moon Ripple — White remains a legacy source alias, not a separate sculpture listing. Both source images/folders retained. Source-specific six specifications remain unapproved; prior Chelsea250×100 face measurement does not establish this reference size or physical-cast identity.'
node = {'component_id': cid, 'source_reference_id': sid, 'canonical_name': 'Chelsea Moonwave (Moon Ripple source002)', 'identity_confirmed': True, 'identity_decision_display': 'Owner confirmed same-design source alias', 'identity_approval': approval, 'proposals_approved': False, 'physical_specs_verified': False, 'existing_platform_match_confirmed': False, 'primary_image_id': source['id'], 'primary_folder_id': folder['id'], 'current_dropbox_reference': {'file_id': source['id'], 'folder_id': folder['id'], 'file_path': source['path_display'], 'folder_path': folder['path_display'], 'file_revision': source['rev'], 'file_bytes': source['size'], 'image_url': decision['links']['primary_image'], 'folder_url': decision['links']['primary_folder']}, 'comparison_reference': {'file_id': decision['comparison_file_id'], 'folder_id': decision['comparison_folder_id'], 'image_url': decision['links']['comparison_image'], 'folder_url': decision['links']['comparison_folder']}, 'specification_proposals': proposals, 'scope': scope, 'review_record': rel(HERE / 'source-reference-review.json'), 'photo_coverage': {'contextual_source_status': 'Candidate context: exact association pending', 'contextual_source_description': decision['context_coverage']['basis'], 'contextual_file_ids': decision['context_coverage']['selected_file_ids'], 'installation_provenance': 'UNCONFIRMED', 'garden_context_exact_source_association_confirmed': False}}
parent.setdefault('source_reference_reviews', {})[sid] = node
p.setdefault('source_identity_consolidations', {})[sid] = decision
p['asset_assignment_overrides'][source['id']] = p['asset_assignment_overrides'].get(source['id'], {}) | {'file_id': source['id'], 'folder_id': folder['id'], 'component_ids': [cid], 'canonical_component_id': cid, 'canonical_source_name': 'Chelsea Moonwave', 'legacy_source_label': 'Moon Ripple — White', 'source_identity_consolidation': approval, 'assignment_status': 'OWNER_CONFIRMED_EXACT_SOURCE002_CHELSEA_DESIGN_ALIAS;SIZE_CAST_SPECIFICATIONS_UNCONFIRMED'}
p['catalogue_group_overrides']['G233'] = p['catalogue_group_overrides'].get('G233', {}) | {'current_family': 'Moon Ripple', 'current_name': folder['name'], 'current_folder_id': folder['id'], 'current_folder_path': folder['path_display'], 'file_count': 2, 'role': 'Legacy source alias for Chelsea Moonwave', 'component_ids': [cid], 'source_identity_consolidation_record': approval, 'assignment_status': 'Owner confirmed source002 as Chelsea Moonwave (BC-CHELSEA). Moon Ripple is a legacy source label; no separate sculpture listing. Other folder members, exact size/cast and specifications remain separately unverified.'}
summary = {'batch': 48, 'recorded_utc': now, 'receipt': rel(HERE / 'import-receipt.json'), 'scope_kind': 'SOURCE_IDENTITY_CATALOGUE_CONSOLIDATION', 'canonical_component_id': cid, 'source_reference_id': sid, 'new_source_identity_relationships': 1, 'new_finish_name_approvals': 0, 'new_full_specification_approvals': 0, 'new_registered_BC_component_ids': [], 'root_new_private_original_downloads': 0, 'remote_mutations': 0, 'workbook_export_pending': True}
cp['parallel_import_queue'].append({'scope_kind': summary['scope_kind'], 'receipt': rel(package_path), 'receipt_sha256': digest, 'approval_imported': True, 'import_receipt': summary['receipt'], 'status': 'SOURCE_ALIAS_CONSOLIDATED;SIX_SPECIFICATIONS_UNAPPROVED'})
c['parallel_import_queue'] = copy.deepcopy(cp['parallel_import_queue'])
for target, key in [(p, 'latest_parallel_import'), (cp, 'last_parallel_import'), (c, 'last_parallel_import')]: target[key] = copy.deepcopy(summary)
for doc in docs.values(): doc['updated_utc'] = now
docs['root']['current_component_review'] = copy.deepcopy(c)
assert {k: v for k, v in parent.items() if k != 'source_reference_reviews'} == before['progress']['reviews'][cid]
assert u['identity_confirmation_counts'] == before['user']['identity_confirmation_counts'] and u['specification_approval_counts'] == before['user']['specification_approval_counts']
assert all(cp[k] == v for k, v in before['walkthrough'].items() if k.startswith('current_'))
assert all(sha(paths[k]) == v for k, v in guards.items())
write(HERE / 'before-import.json', before); write(HERE / 'owner-source-consolidation.json', decision); write(HERE / 'source-reference-review.json', node); write(HERE / 'source-manifest.json', {'files': frozen, 'verified_messages': messages})
for k, path in paths.items(): write(path, docs[k])
write(HERE / 'import-receipt.json', {'status': 'APPLIED;INDEPENDENT_READBACK_REQUIRED', 'summary': summary, 'shared_after_sha256': {k: sha(v) for k, v in paths.items()}})
print(json.dumps({'batch': 48, 'status': 'APPLIED', 'new_designs_or_spec_approvals': 0, 'canonical_component': cid, 'source_alias': sid}))
