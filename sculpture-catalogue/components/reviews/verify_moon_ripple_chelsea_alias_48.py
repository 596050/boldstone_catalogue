"""Independent readback of exact-source alias and preserved specification scopes."""
import copy
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = ROOT / 'components/reviews/parallel-import-2026-10-19-batch48'
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
paths = {'user': ROOT / 'components/reviews/user_classifications.json', 'progress': ROOT / 'components/reviews/specification_review_progress.json', 'walkthrough': ROOT / 'components/reviews/walkthrough_checkpoint.json', 'component': ROOT / 'components/checkpoint.json', 'root': ROOT / 'checkpoint.json'}
old, receipt = read(HERE / 'before-import.json'), read(HERE / 'import-receipt.json'); cur = {k: read(v) for k, v in paths.items()}
u, p, cp = (cur[k] for k in ['user', 'progress', 'walkthrough']); node = p['reviews']['BC-CHELSEA']['source_reference_reviews']['SOURCE-G233002']
decision = read(HERE / 'owner-source-consolidation.json')
checks = {f'prior_user_{k}_unchanged': u[k] == v for k, v in old['user'].items() if k != 'updated_utc'}
checks.update({'one_new_exact_source_relationship': len(u['source_identity_consolidation_decisions']) == 1 and u['source_identity_consolidation_decisions'][0] == decision,
    'exact_owner_and_comparison_card': decision['verified_authoritative_user']['line'] == 26876 and decision['preceding_assistant_card_evidence']['line'] == 26869,
    'existing_canonical_component_and_source_alias': decision['canonical_component_id'] == 'BC-CHELSEA' and decision['canonical_name'] == 'Chelsea Moonwave' and decision['retain_as_legacy_source_alias'] == 'Moon Ripple — White',
    'all_six_source_spec_groups_pending': len(node['specification_proposals']) == 6 and all(x['owner_approved'] is False and 'UNAPPROVED' in x['status'] for x in node['specification_proposals']) and not node['proposals_approved'],
    'Chelsea250x100_not_transferred_to_source': decision['chelsea_250x100_inherited_by_this_source'] is False and all('CHELSEA250x100_NOT_INHERITED' in x['status'] for x in node['specification_proposals']),
    'prior_Chelsea_owner_specs_and_fields_unchanged': {k: v for k, v in p['reviews']['BC-CHELSEA'].items() if k != 'source_reference_reviews'} == old['progress']['reviews']['BC-CHELSEA'],
    'all_other_component_reviews_unchanged': all(p['reviews'][k] == v for k, v in old['progress']['reviews'].items() if k != 'BC-CHELSEA'),
    'source_design_reviews_unchanged': p['source_design_reviews'] == old['progress']['source_design_reviews'],
    'same_registered_design_ID_set_and_counts': set(p['reviews']) == set(old['progress']['reviews']) and cur['component']['counts'] == old['component']['counts'] and receipt['summary']['new_registered_BC_component_ids'] == [],
    'only_selected_source_asset_upgraded': all(p['asset_assignment_overrides'][k] == v for k, v in old['progress']['asset_assignment_overrides'].items() if k != decision['primary_file_id']) and p['asset_assignment_overrides'][decision['primary_file_id']]['component_ids'] == ['BC-CHELSEA'],
    'related_context_remains_provisional': decision['group_context_associations_upgraded'] is False and node['photo_coverage']['garden_context_exact_source_association_confirmed'] is False and node['photo_coverage']['contextual_source_status'] == 'Candidate context: exact association pending',
    'G234_related_context_group_unchanged': p['catalogue_group_overrides'].get('G234') == old['progress']['catalogue_group_overrides'].get('G234'),
    'both_image_and_folder_references_retained': all(decision['links'][k] for k in ['primary_image', 'primary_folder', 'comparison_image', 'comparison_folder']) and node['comparison_reference']['file_id'] == 'id:cnqzTNngPVsAAAAAAA53Gw',
    'root_current_dimension_question_unchanged': all(cp[k] == v for k, v in old['walkthrough'].items() if k.startswith('current_')) and cp['current_question_id'] == 'MCP4-VERDIGRIS-RUST-DIMENSIONS-01' and not cp['current_answer_recorded'],
    'root_component_mirror_exact': cur['root']['current_component_review'] == cur['component'],
    'source_model_original_input_immutable': sha(ROOT / 'components/evidence/component_register.json') == 'ba65d17e6182ba6b89f30400d2f0236bc22a1478c29fb39be4d362a48d24fb61' and sha(ROOT.parent / 'Boldstone_Wall_Sculptures_Matched_All_Fields_2026-10-15.xlsx') == '7e6911a88ea9c9fd3214bdf860e24d6ad72ee755302efd6a9acc4db85c52c5c9',
    'published_workbook_not_changed_by_import': sha(ROOT / p['latest_workbook_export']['workbook']) == p['latest_workbook_export']['workbook_sha256'],
    'all_frozen_source_bytes_and_sizes_match': all(sha(ROOT / x['snapshot']) == x['sha256'] and (ROOT / x['snapshot']).stat().st_size == x['bytes'] for x in read(HERE / 'source-manifest.json')['files']),
    'saved_shared_hashes_match_import': all(sha(paths[k]) == v for k, v in receipt['shared_after_sha256'].items()),
    'zero_specs_original_downloads_and_remote_writes': receipt['summary']['new_full_specification_approvals'] == receipt['summary']['root_new_private_original_downloads'] == receipt['summary']['remote_mutations'] == 0})
guards = {k: sha(v) for k, v in paths.items()}
repeat = subprocess.run(['python3', str(ROOT / 'components/reviews/import_moon_ripple_chelsea_alias_48.py')], capture_output=True, text=True, check=True)
checks['repeat_import_NO_WRITE'] = 'ALREADY_IMPORTED_IDEMPOTENT_NO_WRITE' in repeat.stdout and all(sha(paths[k]) == v for k, v in guards.items())
assert all(checks.values()), [k for k, v in checks.items() if not v]
out = {'status': 'PASS', 'checked_utc': datetime.now(timezone.utc).isoformat(), 'checks': {k: 'PASS' for k in checks}, 'check_count': len(checks), 'import_receipt_sha256': sha(HERE / 'import-receipt.json')}
(HERE / 'independent-readback.json').write_text(json.dumps(out, indent=2) + '\n')
event = {'event_id': decision['decision_id'], 'batch': 48, 'event': 'OWNER_EXACT_SOURCE_CATALOGUE_ALIAS_CONSOLIDATED', 'new_specification_approvals': 0, 'approval': decision['approval_record'], 'readback_sha256': sha(HERE / 'independent-readback.json')}
for path in [ROOT / 'components/reviews/identity_review_journal.jsonl', ROOT / 'review_journal.jsonl']:
    if not any(json.loads(line).get('event_id') == event['event_id'] for line in path.read_text().splitlines() if line.strip()):
        with path.open('a') as stream: stream.write(json.dumps(event) + '\n')
print(json.dumps({'batch': 48, 'status': 'PASS', 'checks': len(checks), 'readback_sha256': sha(HERE / 'independent-readback.json')}))
