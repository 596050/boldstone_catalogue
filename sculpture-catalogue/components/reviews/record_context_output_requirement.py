"""Retain the owner's final-output requirement and the verified existing workbook fields."""
import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from import_source_followups_24_25 import canonical_messages

ROOT = Path(__file__).resolve().parents[2]
HERE = ROOT / 'components/reviews/context-output-requirement-2026-10-19'
SOURCE = ROOT / 'components/parallel-reviews/brancusi-gold-finishes-2026-10-19/context-output-requirement'
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
rel = lambda p: str(Path(p).relative_to(ROOT))
def write(path, value):
    path = Path(path); path.parent.mkdir(exist_ok=True, parents=True); temp = path.with_name(path.name + '.tmp'); temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n'); temp.replace(path)

paths = {'progress': ROOT / 'components/reviews/specification_review_progress.json', 'walkthrough': ROOT / 'components/reviews/walkthrough_checkpoint.json', 'component': ROOT / 'components/checkpoint.json', 'root': ROOT / 'checkpoint.json'}
docs = {k: read(v) for k, v in paths.items()}
if (HERE / 'recording-receipt.json').exists():
    assert 'CONTEXT-IMAGE-OUTPUT-OWNER-LINE26576' in docs['progress']['catalogue_output_requirements']
    print(json.dumps({'status': 'ALREADY_RECORDED_IDEMPOTENT_NO_WRITE'})); raise SystemExit
before, guards = copy.deepcopy(docs), {k: sha(v) for k, v in paths.items()}
package_path = SOURCE / 'IMPORT_PACKAGE.json'
assert sha(package_path) == 'a4822eed9aa7afe3a0a8a148d4330d0ea99020c7038e4b64a88d98acb2280243'
package = read(package_path); frozen = []
for path, digest in [(package_path, sha(package_path)), *[(Path(package[k]['path']), package[k]['sha256']) for k in ['owner_instruction', 'proposed_context_values', 'existing_workbook_readback']]]:
    assert sha(path) == digest
    target = HERE / 'sources' / (digest + '.json'); target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(path.read_bytes())
    frozen.append({'source': str(path), 'snapshot': rel(target), 'sha256': digest})
instruction = read(package['owner_instruction']['path'])
evidence = [instruction['preceding_assistant_evidence'], instruction['authoritative_user_evidence']]
evidence = [x | {'transcript': x['transcript_path']} for x in evidence]
verified = canonical_messages(evidence, instruction['source_owner_session'])
assert [x['line'] for x in verified] == [26558, 26576] and verified[-1]['text'] == 'Okay, make sure these are marked in the ultimate output, I need to know which have contextual images of sculptures. Move on otherwise'
p, cp, c = (docs[k] for k in ['progress', 'walkthrough', 'component'])
assert docs['root']['current_component_review'] == c and not cp['current_answer_recorded']
user_path = ROOT / 'components/reviews/user_classifications.json'; user_sha = sha(user_path)
book = p['latest_workbook_export']; assert sha(ROOT / book['workbook']) == book['workbook_sha256']
qa = read(ROOT / book['validation'])
assert qa['status'] == qa['visual_verification'] == 'PASS' and qa['checks']['context_columns_visible_for_every_scope'] == 'PASS' and qa['checks']['unknown_context_not_asserted_absent'] == 'PASS' and qa['checks']['Gold_context_types_and_links_saved'] == 'PASS'
now = datetime.now(timezone.utc).isoformat(); key = 'CONTEXT-IMAGE-OUTPUT-OWNER-LINE26576'
record = {'requirement_id': key, 'recorded_utc': now, 'owner_instruction_snapshot': frozen[1]['snapshot'], 'authoritative_user_evidence': verified[-1], 'scope': instruction['required_output'], 'unknown_is_not_absent': True, 'approval_scope': instruction['approval_scope'], 'current_workbook_fields': ['Current Reviews!N: context status', 'Current Reviews!O: context type and limitations', 'Current Reviews!P: example image', 'Current Reviews!Q: containing folder'], 'workbook': book['workbook'], 'workbook_sha256': book['workbook_sha256'], 'status': 'OUTPUT_FIELDS_AVAILABLE;CONTINUE_PER_SCOPE_CONTEXT_REVIEW', 'all_sculpture_context_reviews_complete': False, 'record': rel(HERE / 'owner-output-requirement.json')}
p.setdefault('catalogue_output_requirements', {})[key] = record
for doc in [cp, c]: doc.setdefault('catalogue_output_requirements', {})[key] = record['record']
for doc in docs.values(): doc['updated_utc'] = now
docs['root']['current_component_review'] = copy.deepcopy(c)
assert p['reviews'] == before['progress']['reviews'] and p['source_design_reviews'] == before['progress']['source_design_reviews'] and p['latest_workbook_export'] == before['progress']['latest_workbook_export']
assert all(cp[k] == v for k, v in before['walkthrough'].items() if k.startswith('current_')) and c['counts'] == before['component']['counts']
assert all(sha(paths[k]) == v for k, v in guards.items()) and sha(user_path) == user_sha
write(HERE / 'owner-output-requirement.json', record); write(HERE / 'source-manifest.json', {'files': frozen, 'verified_messages': verified})
for k, path in paths.items(): write(path, docs[k])
checks = {'root_mirror': read(paths['root'])['current_component_review'] == read(paths['component']), 'current_question_unchanged': all(read(paths['walkthrough'])[k] == v for k, v in before['walkthrough'].items() if k.startswith('current_')), 'user_ledger_byte_identical': sha(user_path) == user_sha, 'workbook_byte_identical': sha(ROOT / book['workbook']) == book['workbook_sha256'], 'frozen_source_hashes': all(sha(ROOT / x['snapshot']) == x['sha256'] for x in frozen), 'all_six_Gold_specs_and_other_reviews_unchanged': read(paths['progress'])['reviews'] == before['progress']['reviews']}
assert all(checks.values())
write(HERE / 'recording-receipt.json', {'status': 'RECORDED_AND_READ_BACK', 'requirement_id': key, 'checks': checks, 'new_identity_spec_or_manufacture_approvals': 0, 'new_remote_writes_or_original_downloads': 0, 'workbook_export_required': False, 'reason': 'The already verified workbook has explicit fields; no cell data changed by recording this policy.'})
print(json.dumps({'status': 'RECORDED_AND_READ_BACK', 'checks': len(checks), 'current_question_preserved': True, 'workbook_sha256': book['workbook_sha256']}))
