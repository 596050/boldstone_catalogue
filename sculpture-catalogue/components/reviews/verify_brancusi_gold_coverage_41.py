"""Independent saved-record readback for the scoped, non-owner photo audit."""
import copy
import hashlib
import json
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = ROOT / 'components/reviews/parallel-import-2026-10-19-batch41'
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
paths = {'user': ROOT / 'components/reviews/user_classifications.json', 'progress': ROOT / 'components/reviews/specification_review_progress.json',
         'walkthrough': ROOT / 'components/reviews/walkthrough_checkpoint.json', 'component': ROOT / 'components/checkpoint.json', 'root': ROOT / 'checkpoint.json'}
before, receipt = read(HERE / 'before-import.json'), read(HERE / 'import-receipt.json')
docs = {k: read(v) for k, v in paths.items()}
p, cp = docs['progress'], docs['walkthrough']
checks = {}
checks['saved_shared_hashes_match_import_receipt'] = all(sha(paths[k]) == v for k, v in receipt['shared_after_sha256'].items())
checks['protected_inputs_and_question_unchanged'] = all(sha(k) == v for k, v in receipt['protected_sha256'].items())
checks['owner_ledger_byte_identical'] = docs['user'] == before['user'] and sha(paths['user']) == receipt['protected_sha256'][str(paths['user'])]
checks['all_root_current_question_fields_unchanged'] = all(cp[k] == v for k, v in before['walkthrough'].items() if k.startswith('current_'))
checks['Verdigris_question_unanswered'] = not cp['current_answer_recorded'] and cp['current_size_finish_variant_id'] == 'MCP4-VERDIGRIS'
checks['root_mirror_exact'] = docs['root']['current_component_review'] == docs['component']
checks['asset_assignments_unchanged'] = p['asset_assignment_overrides'] == before['progress']['asset_assignment_overrides']
checks['source_design_reviews_unchanged'] = p['source_design_reviews'] == before['progress']['source_design_reviews']
reviews = copy.deepcopy(p['reviews'])
for n in [1, 2]:
    cid, vid = f'BC-BR-{n}', f'BR-{n}-GOLD-LEAF'
    current = reviews[cid]['size_finish_variants'][vid]
    prior = before['progress']['reviews'][cid]['size_finish_variants'][vid]
    checks[vid + '_six_specs_identical_unapproved'] = current['specification_proposals'] == prior['specification_proposals'] and len(current['specification_proposals']) == 6 and current['proposals_approved'] is False
    checks[vid + '_identity_and_primary_unchanged'] = all(current[k] == prior[k] for k in ['canonical_name', 'identity_confirmed', 'primary_image_id'])
    checks[vid + '_scope_is_cached_six_folders'] = 'Six allocated Gold folders,68 cached thumbnails' in current['photo_coverage']['source_scope'] and current['photo_coverage']['original_bytes_verified_now'] is False
    gap = p['current_component_photograph_gaps'][vid]
    checks[vid + '_scoped_missing_photos_recorded'] = all(s in gap['missing'] for s in ['Rear/fixing', 'calibrated side/profile', 'full-component wide-room']) and 'not a whole-library absence claim' in gap['evidence']
    for key in ['photo_coverage', 'photo_coverage_summary', 'photo_coverage_review']: current.pop(key)
    current['missing_photographs'] = copy.deepcopy(prior.get('missing_photographs', []))
checks['all_other_review_fields_and_components_unchanged'] = reviews == before['progress']['reviews']
live = read(HERE / 'current-reference-check.json')
groups = {g['group_ref']: g for g in live['groups']}
checks['six_complete_current_listings'] = len(groups) == 6 and all(not g['listing']['has_more'] and not g['listing']['cursor'] for g in groups.values())
checks['Gold1_context31_Gold2_context0'] = len(groups['G035']['listing']['entries']) == 31 and len(groups['G039']['listing']['entries']) == 0
obs = read(HERE / 'file-observations.json')
entries = {x['file_id']: (g, x) for g in groups.values() for x in g['listing']['entries']}
checks['68_unique_IDs_match_complete_listings'] = len(obs) == len(entries) == 68 and {x['file_id'] for x in obs} == set(entries)
checks['all_ID_names_sizes_parents_match_live_metadata'] = all(x['name'] == entries[x['file_id']][1]['name'] and x['current_bytes'] == entries[x['file_id']][1]['file']['size'] and x['folder_id'] == entries[x['file_id']][0]['folder']['id'] and x['current_path_display'] == entries[x['file_id']][1]['path_display'] for x in obs)
checks['cached_thumbnail_hashes_and_sizes_match'] = all(sha(x['thumbnail_path']) == x['thumbnail_sha256'] and Path(x['thumbnail_path']).stat().st_size == x['thumbnail_bytes'] for x in obs)
checks['no_original_verification_manufacture_stock_or_member_assignment'] = all(x['original_content_hashed_now'] is False and not x.get('physical_manufacture_confirmed') and x.get('physical_stock_count') is None and not x.get('individual_component_assignment') and not x.get('individual_component_decomposition_performed') for x in obs)
checks['31_crop_context_and10_family_context_observations'] = Counter(x['role'] for x in obs)['ROOM_PRESENTATION_OF_RECTANGULAR_DETAIL'] == 31 and sum(x['role'] in ['FAMILY_SERIES_CONTEXT', 'FAMILY_ROOM_CONTEXT'] for x in obs) == 10
checks['frozen_evidence_bytes_verified'] = all(sha(ROOT / x['snapshot']) == x['sha256'] and (ROOT / x['snapshot']).stat().st_size == x['bytes'] for x in read(HERE / 'source-manifest.json')['files'])
item = cp['parallel_import_queue'][-1]
checks['queue_is_evidence_without_owner_approval'] = item['evidence_imported'] is True and item['approval_imported'] is False
checks['summary_zero_decisions_downloads_and_remote_writes'] = all(receipt['summary'][k] == 0 for k in ['new_owner_decisions', 'new_finish_name_approvals', 'new_full_specification_approvals', 'root_new_private_original_downloads', 'remote_mutations'])
guards = {k: sha(v) for k, v in paths.items()}
run = subprocess.run(['python3', str(ROOT / 'components/reviews/import_brancusi_gold_coverage_41.py')], capture_output=True, text=True, check=True)
checks['idempotent_repeat_NO_WRITE'] = 'ALREADY_IMPORTED_IDEMPOTENT_NO_WRITE' in run.stdout and all(sha(paths[k]) == v for k, v in guards.items())
assert all(checks.values()), [k for k, v in checks.items() if not v]
result = {'status': 'PASS', 'checked_utc': datetime.now(timezone.utc).isoformat(), 'batch': 41, 'checks': {k: 'PASS' for k in checks}, 'check_count': len(checks), 'import_receipt_sha256': sha(HERE / 'import-receipt.json')}
(HERE / 'independent-readback.json').write_text(json.dumps(result, indent=2) + '\n')
event = {'event_id': 'BATCH41:BRANCUSI-GOLD:CACHED-PHOTO-COVERAGE', 'recorded_utc': result['checked_utc'], 'scope': 'DERIVED_CACHED_PHOTO_COVERAGE', 'owner_decisions': 0, 'specification_approvals': 0, 'receipt': str((HERE / 'import-receipt.json').relative_to(ROOT)), 'independent_readback_sha256': sha(HERE / 'independent-readback.json')}
for path in [ROOT / 'components/reviews/identity_review_journal.jsonl', ROOT / 'review_journal.jsonl']:
    if not any(json.loads(line).get('event_id') == event['event_id'] for line in path.read_text().splitlines() if line.strip()):
        with path.open('a') as stream: stream.write(json.dumps(event) + '\n')
print(json.dumps({'batch': 41, 'status': 'PASS', 'checks': len(checks), 'readback_sha256': sha(HERE / 'independent-readback.json')}))
