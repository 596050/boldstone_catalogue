"""Independent saved-state verification of the exact owner finish-equivalence answer."""
import copy
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = ROOT / 'components/reviews/parallel-import-2026-10-19-batch43'
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
paths = {'user': ROOT / 'components/reviews/user_classifications.json', 'progress': ROOT / 'components/reviews/specification_review_progress.json', 'walkthrough': ROOT / 'components/reviews/walkthrough_checkpoint.json', 'component': ROOT / 'components/checkpoint.json', 'root': ROOT / 'checkpoint.json'}
old, receipt = read(HERE / 'before-import.json'), read(HERE / 'import-receipt.json')
cur = {k: read(v) for k, v in paths.items()}
u, p, cp, c = (cur[k] for k in ['user', 'progress', 'walkthrough', 'component'])
cid, vid, src = 'BC-MCP-4', 'MCP4-VERDIGRIS-25', 'MCP4-VERDIGRIS'
node = p['reviews'][cid]['size_finish_variants'][vid]
prior = old['progress']['reviews'][cid]['size_finish_variants'][vid]
decision = read(HERE / 'finish-reference-equivalence-approval.json')
refs = node['reference_files']
checks = {f'previous_user_{k}_unchanged': u[k] == v for k, v in old['user'].items() if k not in ['updated_utc', 'finish_reference_equivalence_decisions']}
checks.update({'one_exact_new_finish_equivalence': u['finish_reference_equivalence_decisions'][:-1] == old['user']['finish_reference_equivalence_decisions'] and u['finish_reference_equivalence_decisions'][-1] == decision,
    'exact_owner_answer_and_prior_card': decision['authoritative_user_evidence']['line'] == 18425 and decision['preceding_review_card_evidence']['line'] == 18408,
    'one_canonical_finish_and_native_alias': src not in p['reviews'][cid]['size_finish_variants'] and p['canonical_variant_aliases'][cid + '|' + src]['canonical_variant_id'] == vid,
    'native_pending_relationship_removed': all(x['variant_id'] != src for x in p['reviews'][cid]['pending_size_finish_variants']),
    '15_unique_stable_file_IDs_four_folders': len(refs) == len({x['file_id'] for x in refs}) == 15 and len(set(node['reference_folder_ids'])) == 4,
    'seven_context_files_explicit': len(node['photo_coverage']['contextual_file_ids']) == 7 and node['photo_coverage']['contextual_images_available'] is True,
    'context_provenance_unconfirmed_and_not_stock': node['photo_coverage']['installation_provenance'] == 'UNCONFIRMED' and node['photo_coverage']['context_images_count_is_physical_stock'] is False,
    'all_six_specifications_unchanged_unaccepted': node['specification_proposals'] == prior['specification_proposals'] and len(node['specification_proposals']) == 6 and node['proposals_approved'] is False,
    'exact_platform_mapping_unchanged': node['platform_mapping'] == prior['platform_mapping'],
    'all_other_component_reviews_unchanged': all(p['reviews'][k] == v for k, v in old['progress']['reviews'].items() if k != cid),
    'all_other_MCP4_finishes_unchanged': all(p['reviews'][cid]['size_finish_variants'][k] == v for k, v in old['progress']['reviews'][cid]['size_finish_variants'].items() if k != vid),
    'source_design_reviews_unchanged': p['source_design_reviews'] == old['progress']['source_design_reviews'],
    'root_answer_recorded_with_canonical_finish': cp['current_answer_recorded'] and cp['current_finish_reference_equivalence_answer_recorded'] and cp['current_size_finish_variant_id'] == vid,
    'root_mirror_and_legacy_counts_unchanged': cur['root']['current_component_review'] == c and c['counts'] == old['component']['counts'],
    'no_spec_name_component_stock_original_or_remote_upgrade': decision['new_name_approvals'] == decision['new_specification_approvals'] == decision['remote_mutations'] == decision['new_original_downloads'] == 0 and decision['new_registered_BC_component_ids'] == [] and not decision['physical_cast_mould_stock_merge'],
    'protected_inputs_unchanged': all(sha(path) == v for path, v in receipt['protected_sha256'].items()),
    'saved_shared_hashes_match': all(sha(paths[k]) == v for k, v in receipt['shared_after_sha256'].items())})
live = read(ROOT / 'components/reviews/concave-to-mcp4-consolidation-2026-10-19/verdigris-finish-comparison/owner-answer-live-listings.json')
entries = {x['file_id']: (g, x) for g in live['groups'] for x in g['listing']['entries']}
checks['four_complete_current_listings'] = len(live['groups']) == 4 and all(not g['listing']['has_more'] and not g['listing']['cursor'] for g in live['groups'])
checks['all15_names_sizes_paths_parents_exact'] = set(entries) == {x['file_id'] for x in refs} and all(x['folder_id'] == entries[x['file_id']][0]['folder']['id'] and x['path_display'] == entries[x['file_id']][1]['path_display'] and x['name'] == entries[x['file_id']][1]['name'] and x['bytes'] == entries[x['file_id']][1]['file']['size'] for x in refs)
checks['all15_assignments_to_canonical_finish'] = all(p['asset_assignment_overrides'][x['file_id']]['canonical_size_finish_variant_id'] == vid and p['asset_assignment_overrides'][x['file_id']]['component_ids'] == [cid] for x in refs)
checks['all4_folder_assignments_to_canonical_finish'] = all(p['catalogue_group_overrides'][g]['canonical_size_finish_variant_id'] == vid for g in ['G216', 'G217', 'G052', 'G053'])
checks['frozen_source_bytes_match'] = all(sha(ROOT / x['snapshot']) == x['sha256'] for x in read(HERE / 'source-manifest.json')['files'])
guards = {k: sha(v) for k, v in paths.items()}
repeat = subprocess.run(['python3', str(ROOT / 'components/reviews/apply_mcp4_verdigris_finish_equivalence_43.py')], capture_output=True, text=True, check=True)
checks['idempotent_repeat_NO_WRITE'] = 'ALREADY_IMPORTED_IDEMPOTENT_NO_WRITE' in repeat.stdout and all(sha(paths[k]) == v for k, v in guards.items())
assert all(checks.values()), [k for k, v in checks.items() if not v]
out = {'status': 'PASS', 'checked_utc': datetime.now(timezone.utc).isoformat(), 'checks': {k: 'PASS' for k in checks}, 'check_count': len(checks), 'import_receipt_sha256': sha(HERE / 'import-receipt.json')}
(HERE / 'independent-readback.json').write_text(json.dumps(out, indent=2) + '\n')
event = {'event_id': 'BATCH43:MCP4:VERDIGRIS:FINISH-EQUIVALENCE', 'recorded_utc': out['checked_utc'], 'batch': 43, 'owner_finish_equivalence_decisions': 1, 'specification_approvals': 0, 'receipt': str((HERE / 'import-receipt.json').relative_to(ROOT)), 'independent_readback_sha256': sha(HERE / 'independent-readback.json')}
for path in [ROOT / 'components/reviews/identity_review_journal.jsonl', ROOT / 'review_journal.jsonl']:
    if not any(json.loads(line).get('event_id') == event['event_id'] for line in path.read_text().splitlines() if line.strip()):
        with path.open('a') as stream: stream.write(json.dumps(event) + '\n')
print(json.dumps({'batch': 43, 'status': 'PASS', 'checks': len(checks), 'readback_sha256': sha(HERE / 'independent-readback.json')}))
