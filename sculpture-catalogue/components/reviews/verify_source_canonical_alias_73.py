"""Independent readback of exact-source canonical naming; no specification acceptance."""
import copy
import json
import subprocess
import sys
from datetime import datetime, timezone
from import_source_canonical_alias_73 import ROOT, HERE, PATHS, KEY, SOURCES, NAME, ALIAS, read, sha, write

old = read(HERE / 'before-import.json'); cur = {k: read(v) for k, v in PATHS.items()}
receipt = read(HERE / 'import-receipt.json'); decision = read(HERE / 'canonical-name-decision.json')
u, p, cp, c = (cur[k] for k in ['user', 'progress', 'walkthrough', 'component'])
nodes = copy.deepcopy(p['source_design_reviews'])
for key in SOURCES:
    for field in ['canonical_display_name', 'retained_source_name_aliases', 'source_image_name_consolidation_record']: nodes[key].pop(field)
    nodes[key]['duplicate_source_image_evidence'] = old['progress']['source_design_reviews'][key]['duplicate_source_image_evidence']
checks = {f'prior_user_{key}_preserved': u[key] == value for key, value in old['user'].items() if key != 'updated_utc'}
checks.update({
 'exactly_one_canonical_owner_event': len(u['source_image_canonical_name_decisions']) == 1 and u['source_image_canonical_name_decisions'][0]['decision_id'] == decision['decision_id'],
 'all_historical_source_decisions_and_counts_preserved': len(u['source_design_name_decisions']) == 19 and sum(x['source_design_key'].startswith('FINGERPRINT-') for x in u['source_design_name_decisions']) == 18 and len(u['design_production_confirmation_decisions']) == 11 and u['specification_approval_counts']['proposal_groups'] == 112,
 'source_nodes_unchanged_except_canonical_overlay': nodes == old['progress']['source_design_reviews'],
 'all_base_finish_reviews_and_source_claims_preserved': p['reviews'] == old['progress']['reviews'] and p['catalogue_alias_reviews'] == old['progress']['catalogue_alias_reviews'],
 'source_names_and_conflicting_unaccepted_drafts_preserved': all(p['source_design_reviews'][k]['canonical_source_name'] == old['progress']['source_design_reviews'][k]['canonical_source_name'] and p['source_design_reviews'][k]['specifications'] == old['progress']['source_design_reviews'][k]['specifications'] and not p['source_design_reviews'][k]['owner_estimates_accepted'] for k in SOURCES),
 'both_exact_sources_canonical_and_alias_recorded': all(p['source_design_reviews'][k]['canonical_display_name'] == NAME and p['source_design_reviews'][k]['retained_source_name_aliases'] == [ALIAS] for k in SOURCES),
 'pending_canonical_question_answered_only': not p['duplicate_source_image_reviews'][KEY]['canonical_name_decision_pending'] and p['duplicate_source_image_reviews'][KEY]['source_specification_conflicts_pending'] and next(x for x in cp['pending_source_name_consolidations'] if x['relationship_key'] == KEY)['owner_answer_recorded'],
 'owner_exact_choice_and_alias_context_distinguished': decision['verified_owner_evidence']['text'] == 'Use “Fingerprint — Rough Concentric Panels (Verdigris)”' and not decision['owner_alias_phrase_separately_repeated'] and decision['verified_owner_evidence']['immediately_preceding_assistant']['line'] == 18469,
 'physical_mould_stock_or_file_merge_not_inferred': not decision['physical_component_equivalence_confirmed'] and not decision['physical_stock_count_established'] and c['counts'] == old['component']['counts'] and not p['duplicate_source_image_reviews'][KEY]['physical_sculpture_or_stock_count_inferred'],
 'root_question_and_other_allocations_preserved': all(cp[k] == v for k, v in old['walkthrough'].items() if k.startswith('current_')) and cp['parallel_working_specification_reviews'] == old['walkthrough']['parallel_working_specification_reviews'],
 'root_current_question_still_keyhole_count_unknown': cp['current_question_id'] == 'MCP4-VERDIGRIS-RUST-FIXING-COUNT-01' and not cp['current_answer_recorded'],
 'group_member_and_manufacture_policies_unchanged': all(p[k] == old['progress'][k] for k in ['physical_manufacture_review_policy', 'group_photo_review_policy', 'current_component_photograph_gaps', 'asset_assignment_overrides', 'catalogue_group_overrides']),
 'root_component_mirror_exact': cur['root']['current_component_review'] == c,
 'shared_hashes_match': all(sha(PATHS[k]) == v for k, v in receipt['shared_after_sha256'].items()),
 'frozen_source_hashes_match': all(sha(ROOT / x['snapshot']) == x['sha256'] for x in read(HERE / 'source-manifest.json')['files']),
 'immutable_workbook_and_sources_unchanged': all(sha(path) == v for path, v in receipt['protected_sha256'].items()),
 'no_download_or_remote_mutation': receipt['summary']['root_new_private_original_downloads'] == receipt['summary']['remote_mutations'] == 0,
})
guards = {k: sha(v) for k, v in PATHS.items()}
repeat = subprocess.run([sys.executable, str(ROOT / 'components/reviews/import_source_canonical_alias_73.py')], capture_output=True, text=True, check=True)
checks['idempotent_repeat_NO_WRITE'] = 'ALREADY_IMPORTED_IDEMPOTENT_NO_WRITE' in repeat.stdout and all(sha(PATHS[k]) == v for k, v in guards.items())
assert all(checks.values()), [k for k, v in checks.items() if not v]
write(HERE / 'independent-readback.json', {'status': 'PASS', 'checked_utc': datetime.now(timezone.utc).isoformat(), 'check_count': len(checks), 'checks': {k: 'PASS' for k in checks}, 'import_receipt_sha256': sha(HERE / 'import-receipt.json')})
event = {'event_id': decision['decision_id'], 'event': 'EXACT_SOURCE_CANONICAL_NAME_SELECTION', 'batch': 73, 'new_specification_approvals': 0, 'new_physical_counts': 0, 'readback_sha256': sha(HERE / 'independent-readback.json')}
for path in [ROOT / 'components/reviews/identity_review_journal.jsonl', ROOT / 'review_journal.jsonl']:
    if not any(json.loads(line).get('event_id') == event['event_id'] for line in path.read_text().splitlines() if line.strip()):
        with path.open('a') as stream: stream.write(json.dumps(event) + '\n')
print(json.dumps({'batch': 73, 'status': 'PASS', 'checks': len(checks), 'readback_sha256': sha(HERE / 'independent-readback.json')}))
