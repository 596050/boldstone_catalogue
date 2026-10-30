"""Record the owner's catalogue-wide manufacture statement without per-item approvals."""
import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from import_source_followups_24_25 import canonical_messages

ROOT = Path(__file__).resolve().parents[2]
HERE = ROOT / 'components/reviews/parallel-import-2026-10-19-batch51'
SOURCE = ROOT / 'components/parallel-reviews/fingerprint-unresolved-groups-2026-10-19/all-sculptures-made-policy-import-20261019'
read = lambda path: json.loads(Path(path).read_text())
sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
rel = lambda path: str(Path(path).relative_to(ROOT))
def write(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.tmp'); temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n'); temp.replace(path)

paths = {'user': ROOT / 'components/reviews/user_classifications.json', 'progress': ROOT / 'components/reviews/specification_review_progress.json', 'walkthrough': ROOT / 'components/reviews/walkthrough_checkpoint.json', 'component': ROOT / 'components/checkpoint.json', 'root': ROOT / 'checkpoint.json'}
docs = {key: read(path) for key, path in paths.items()}
if (HERE / 'import-receipt.json').exists():
    assert docs['progress']['physical_manufacture_review_policy']['owner_confirms_all_sculpture_designs_physically_made']
    print(json.dumps({'batch': 51, 'status': 'ALREADY_IMPORTED_IDEMPOTENT_NO_WRITE'})); raise SystemExit
before = copy.deepcopy(docs); guards = {key: sha(path) for key, path in paths.items()}
package_path = SOURCE / 'IMPORT_PACKAGE.json'; package_sha = 'ad340cd8f3d8a1300f2676f7479cad978737bf790168708606dd18abb12e8954'
seal_path = SOURCE / 'SEALED_PACKAGE_MANIFEST.json'; seal_sha = 'b60b724108dfdcac36df4c5e6d8c6d1ca10b4c969972652dea008f24f0a524fe'
assert sha(package_path) == package_sha and sha(seal_path) == seal_sha
package = read(package_path); frozen = []
for item in [{'path': str(package_path), 'sha256': package_sha}, {'path': str(seal_path), 'sha256': seal_sha}, *read(seal_path)['files']]:
    source = Path(item['path']); assert sha(source) == item['sha256']
    dest = HERE / 'sources' / (item['sha256'] + source.suffix); dest.parent.mkdir(parents=True, exist_ok=True); dest.write_bytes(source.read_bytes())
    frozen.append({'source': str(source), 'snapshot': rel(dest), 'sha256': item['sha256']})
policy = read(SOURCE / 'frozen-source/OWNER_ALL_SCULPTURES_MADE_POLICY_20261019.json')
owner = canonical_messages([package['owner_evidence']], package['source_owner_session'])[0]
assert owner['line'] == 17365 and owner['text'] == 'consider all sculptures physically made'
assert policy['repeat_per_source_manufacture_questions_required'] is False and policy['specification_estimates_not_approved'] is True
now = datetime.now(timezone.utc).isoformat(); record = rel(HERE / 'owner-policy.json')
policy.update({'imported_utc': now, 'approval_record': record, 'shared_master_import_performed': True, 'verified_authoritative_user': owner})
u, p, cp, c = (docs[key] for key in ['user', 'progress', 'walkthrough', 'component'])
u.setdefault('manufacture_policy_decisions', []).append(copy.deepcopy(policy))
p['physical_manufacture_review_policy'] = copy.deepcopy(policy)
for target in [cp, c]:
    target['physical_manufacture_review_policy'] = {'approval_record': record, 'owner_confirms_all_sculpture_designs_physically_made': True, 'evidence_level': 'OWNER_STATED_UNIVERSAL_MANUFACTURE', 'repeat_per_source_manufacture_questions_required': False, 'pending_manufacture_questions_superseded_by_policy': True, 'name_specification_image_provenance_and_stock_reviews_still_separate': True}
summary = {'batch': 51, 'recorded_utc': now, 'receipt': rel(HERE / 'import-receipt.json'), 'scope_kind': 'OWNER_UNIVERSAL_MANUFACTURE_STATEMENT', 'new_owner_policy_events': 1, 'new_per_source_confirmation_records': 0, 'new_name_approvals': 0, 'new_full_specification_approvals': 0, 'new_registered_BC_component_ids': [], 'root_new_private_original_downloads': 0, 'remote_mutations': 0, 'workbook_export_pending': True}
cp['parallel_import_queue'].append({'scope_kind': summary['scope_kind'], 'receipt': rel(package_path), 'receipt_sha256': package_sha, 'evidence_imported': True, 'import_receipt': summary['receipt'], 'status': 'OWNER_STATES_ALL_SCULPTURES_MADE;STOP_MANUFACTURE_QUESTIONS;OTHER_REVIEWS_SEPARATE'})
c['parallel_import_queue'] = copy.deepcopy(cp['parallel_import_queue'])
for target, key in [(p, 'latest_parallel_import'), (cp, 'last_parallel_import'), (c, 'last_parallel_import')]: target[key] = copy.deepcopy(summary)
for target in docs.values(): target['updated_utc'] = now
docs['root']['current_component_review'] = copy.deepcopy(c)
assert all(p[key] == before['progress'][key] for key in ['reviews', 'catalogue_alias_reviews', 'source_design_reviews', 'catalogue_design_aliases'])
assert all(u[key] == before['user'][key] for key in ['identity_confirmation_counts', 'dimension_confirmation_counts', 'specification_approval_counts'])
assert all(cp[key] == value for key, value in before['walkthrough'].items() if key.startswith('current_'))
assert all(sha(paths[key]) == value for key, value in guards.items())
write(HERE / 'before-import.json', before); write(HERE / 'owner-policy.json', policy); write(HERE / 'source-manifest.json', {'files': frozen, 'verified_owner': owner})
for key, path in paths.items(): write(path, docs[key])
write(HERE / 'import-receipt.json', {'status': 'APPLIED;INDEPENDENT_READBACK_REQUIRED', 'summary': summary, 'shared_after_sha256': {key: sha(path) for key, path in paths.items()}})
print(json.dumps({'batch': 51, 'status': 'APPLIED', 'repeat_manufacture_questions_required': False, 'new_name_or_specification_approvals': 0, 'root_weight_question_preserved': True}))
