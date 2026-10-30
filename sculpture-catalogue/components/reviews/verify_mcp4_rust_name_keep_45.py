"""Independent saved-record audit for one name-only owner answer."""
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = ROOT / 'components/reviews/parallel-import-2026-10-19-batch45'
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
paths = {'user': ROOT / 'components/reviews/user_classifications.json', 'progress': ROOT / 'components/reviews/specification_review_progress.json', 'walkthrough': ROOT / 'components/reviews/walkthrough_checkpoint.json', 'component': ROOT / 'components/checkpoint.json', 'root': ROOT / 'checkpoint.json'}
old, receipt = read(HERE / 'before-import.json'), read(HERE / 'import-receipt.json')
cur = {k: read(v) for k, v in paths.items()}; u, p, cp = (cur[k] for k in ['user', 'progress', 'walkthrough'])
cid, vid = 'BC-MCP-4', 'MCP4-VERDIGRIS-RUST'
node = p['reviews'][cid]['size_finish_variants'][vid]; prior = old['progress']['reviews'][cid]['size_finish_variants'][vid]
decision = read(HERE / 'identity-approval.json')
checks = {f'prior_user_{k}_unchanged': u[k] == v for k, v in old['user'].items() if k not in ['updated_utc', 'size_finish_variant_decisions', 'identity_confirmation_counts']}
checks.update({'one_exact_new_finish_name_decision': u['size_finish_variant_decisions'][:-1] == old['user']['size_finish_variant_decisions'] and u['size_finish_variant_decisions'][-1] == decision,
    'exact_authoritative_owner_and_card': decision['authoritative_user_evidence']['line'] == 18782 and decision['preceding_review_card_evidence']['line'] == 18764 and decision['user_statement'] == 'Keep “Moon Crater Phase 4 — Verdigris and Rust”',
    'name_kept_exact_selected_file_and_folder': node['identity_confirmed'] and node['canonical_name'] == 'Moon Crater Phase 4 — Verdigris and Rust' and decision['primary_file_id'] == 'id:cnqzTNngPVsAAAAAAAylRA' and decision['primary_folder_id'] == 'id:cnqzTNngPVsAAAAAAAyipA',
    'all_six_specification_proposals_byte_identical': node['specification_proposals'] == prior['specification_proposals'] and len(node['specification_proposals']) == 6,
    'all_six_unapproved_no_physical_verification': node['proposals_approved'] is False and not node['physical_specs_verified'] and all(x['owner_approved'] is False for x in node['specification_proposals']),
    'context_photo_scope_unchanged': node['photo_coverage'] == prior['photo_coverage'],
    'exact_platform_state_unchanged': node['existing_platform_match_confirmed'] == prior['existing_platform_match_confirmed'] is False,
    'all_other_component_reviews_unchanged': all(p['reviews'][k] == v for k, v in old['progress']['reviews'].items() if k != cid),
    'all_other_MCP4_finish_reviews_unchanged': all(p['reviews'][cid]['size_finish_variants'][k] == v for k, v in old['progress']['reviews'][cid]['size_finish_variants'].items() if k != vid),
    'source_design_reviews_unchanged': p['source_design_reviews'] == old['progress']['source_design_reviews'],
    'same_registered_component_ID_set': set(p['reviews']) == set(old['progress']['reviews']) and receipt['summary']['new_registered_BC_component_ids'] == [],
    'alias_count_does_not_assert_new_design': decision['canonical_component_already_exists'] and 'former BC-CONCAVE remains historical' in decision['legacy_ID_count_scope'],
    'four_MCP4_finish_names_kept': len(p['reviews'][cid]['size_finish_variants']) == 4 and all(x['identity_confirmed'] for x in p['reviews'][cid]['size_finish_variants'].values()),
    'root_current_name_answer_saved': cp['current_answer_recorded'] and cp['current_question_id'] == 'MCP4-VERDIGRIS-RUST-NAME-01',
    'root_mirror_exact_and_legacy_counts_unchanged': cur['root']['current_component_review'] == cur['component'] and cur['component']['counts'] == old['component']['counts'],
    'no_new_specs_downloads_or_remote_writes': receipt['summary']['new_full_specification_approvals'] == receipt['summary']['root_new_private_original_downloads'] == receipt['summary']['remote_mutations'] == 0,
    'protected_source_model_workbook_card_unchanged': all(sha(path) == digest for path, digest in receipt['protected_sha256'].items()),
    'all_frozen_evidence_hashes': all(sha(ROOT / x['snapshot']) == x['sha256'] for x in read(HERE / 'source-manifest.json')['files']),
    'shared_saved_hashes_match_receipt': all(sha(paths[k]) == digest for k, digest in receipt['shared_after_sha256'].items())})
guards = {k: sha(v) for k, v in paths.items()}
repeat = subprocess.run(['python3', str(ROOT / 'components/reviews/apply_mcp4_rust_name_keep_45.py')], capture_output=True, text=True, check=True)
checks['repeat_import_NO_WRITE'] = 'ALREADY_IMPORTED_IDEMPOTENT_NO_WRITE' in repeat.stdout and all(sha(paths[k]) == digest for k, digest in guards.items())
assert all(checks.values()), [k for k, v in checks.items() if not v]
out = {'status': 'PASS', 'checked_utc': datetime.now(timezone.utc).isoformat(), 'check_count': len(checks), 'checks': {k: 'PASS' for k in checks}, 'import_receipt_sha256': sha(HERE / 'import-receipt.json')}
(HERE / 'independent-readback.json').write_text(json.dumps(out, indent=2) + '\n')
event = {'event_id': decision['decision_id'], 'event': 'OWNER_KEPT_MCP4_RUST_NAME_ONLY', 'batch': 45, 'new_specification_approvals': 0, 'approval': decision['approval_record'], 'readback_sha256': sha(HERE / 'independent-readback.json')}
for path in [ROOT / 'components/reviews/identity_review_journal.jsonl', ROOT / 'review_journal.jsonl']:
    if not any(json.loads(line).get('event_id') == event['event_id'] for line in path.read_text().splitlines() if line.strip()):
        with path.open('a') as stream: stream.write(json.dumps(event) + '\n')
print(json.dumps({'batch': 45, 'status': 'PASS', 'checks': len(checks), 'readback_sha256': sha(HERE / 'independent-readback.json')}))
