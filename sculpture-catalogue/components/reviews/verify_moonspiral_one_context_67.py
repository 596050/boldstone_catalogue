"""Independently verify context-only changes and all pending specification scopes."""
import copy
import json
import subprocess
from datetime import datetime, timezone
from import_moonspiral_one_context_67 import ROOT, HERE, PATHS, CID, VID, read, sha, write

old = read(HERE / 'before-import.json'); cur = {key: read(path) for key, path in PATHS.items()}; receipt = read(HERE / 'import-receipt.json'); p, cp = cur['progress'], cur['walkthrough']; node = p['reviews'][CID]['size_finish_variants'][VID]; prior = old['progress']['reviews'][CID]['size_finish_variants'][VID]
reviews = copy.deepcopy(p['reviews']); reviews[CID]['size_finish_variants'][VID] = prior
gaps = copy.deepcopy(p['current_component_photograph_gaps']); new_gap = gaps.pop(VID)
checks = {f'prior_user_{key}_unchanged': cur['user'][key] == value for key, value in old['user'].items()}
checks.update({
    'user_file_byte_identical': sha(PATHS['user']) == receipt['shared_after_sha256']['user'],
    'only_node_context_fields_changed': all(node[key] == value for key, value in prior.items() if key not in ['photo_coverage', 'context_output_review']) and set(node)-set(prior) <= {'photo_coverage', 'context_output_review'},
    'six_original_specifications_unaccepted': len(node['specification_proposals']) == 6 and node['specification_proposals'] == prior['specification_proposals'] and not node['proposals_approved'] and not node['physical_specs_verified'],
    'all_other_component_scopes_unchanged': reviews == old['progress']['reviews'],
    'all_aliases_source_groups_overrides_policies_unchanged': all(p[key] == old['progress'][key] for key in ['catalogue_alias_reviews','catalogue_design_aliases','source_design_reviews','asset_assignment_overrides','catalogue_group_overrides','group_photo_review_policy','physical_manufacture_review_policy']),
    'individual_and_shared_context_distinguished': node['photo_coverage']['on_wall'] and node['photo_coverage']['family_wider_room_context'] and not node['photo_coverage']['individual_wider_room_established'] and node['photo_coverage']['contextual_source_status'] == 'Available: on-wall and shared family room context',
    'shared_room_and_individual_source_IDs_bound': node['photo_coverage']['contextual_file_ids'] == ['id:cnqzTNngPVsAAAAAAAuc3w','id:cnqzTNngPVsAAAAAAAuYPQ'] and node['photo_coverage']['shared_family_context_folder_id'] == 'id:cnqzTNngPVsAAAAAAAyi8w' and node['photo_coverage']['individual_context_folder_id'] == 'id:cnqzTNngPVsAAAAAAAyi8g',
    'thumbnail_only_and_scene_limits_explicit': node['photo_coverage']['root_evidence_kind'] == 'THUMBNAILS_AND_CONTACT_SHEET_ONLY' and not node['photo_coverage']['original_bytes_rehashed_this_context_review'] and not node['photo_coverage']['exact_physical_cast_identity_verified'] and node['photo_coverage']['installation_provenance'] == 'UNCONFIRMED',
    'exactly_one_scoped_photo_gap_row': gaps == old['progress']['current_component_photograph_gaps'] and new_gap['component_id'] == CID and new_gap['size_finish_variant_id'] == VID and 'shared family context' in new_gap['room'] and 'dedicated individual' in new_gap['missing'],
    'working_approval_counts_unchanged': cur['user']['specification_approval_counts'] == old['user']['specification_approval_counts'] and cur['component']['interactive_review_state'] == old['component']['interactive_review_state'],
    'root_current_question_preserved': cp['current_question_id'] == 'MCP4-VERDIGRIS-RUST-FIXING-COUNT-01' and not cp['current_answer_recorded'] and all(cp[key] == value for key, value in old['walkthrough'].items() if key.startswith('current_')),
    'pending_Moonspiral_spec_review_allocation_preserved': cp['parallel_working_specification_reviews'] == old['walkthrough']['parallel_working_specification_reviews'],
    'physical_counts_unchanged': cur['component']['counts'] == old['component']['counts'],
    'root_component_mirror_exact': cur['root']['current_component_review'] == cur['component'],
    'frozen_source_hashes_match': all(sha(ROOT / item['snapshot']) == item['sha256'] for item in read(HERE / 'source-manifest.json')['files']),
    'saved_shared_hashes_match': all(sha(PATHS[key]) == value for key, value in receipt['shared_after_sha256'].items()),
    'protected_sources_and_workbook_unchanged': all(sha(path) == value for path, value in receipt['protected_sha256'].items()),
    'no_downloads_or_remote_mutations': receipt['summary']['root_new_private_original_downloads'] == receipt['summary']['remote_mutations'] == 0,
})
guards = {key: sha(path) for key, path in PATHS.items()}; repeat = subprocess.run(['python3',str(ROOT / 'components/reviews/import_moonspiral_one_context_67.py')],capture_output=True,text=True,check=True)
checks['idempotent_repeat_NO_WRITE'] = 'ALREADY_IMPORTED_IDEMPOTENT_NO_WRITE' in repeat.stdout and all(sha(PATHS[key]) == value for key, value in guards.items())
assert all(checks.values()),[key for key,value in checks.items() if not value]
write(HERE / 'independent-readback.json',{'status':'PASS','checked_utc':datetime.now(timezone.utc).isoformat(),'check_count':len(checks),'checks':{key:'PASS' for key in checks},'import_receipt_sha256':sha(HERE / 'import-receipt.json')})
event={'event_id':'MS1-WHITE:CONTEXT-ONLY:IMPORT67','event':'DERIVED_MOONSPIRAL_ONE_CONTEXT_ONLY','batch':67,'owner_approval_inferred':False,'new_specification_approvals':0,'readback_sha256':sha(HERE / 'independent-readback.json')}
for path in [ROOT / 'components/reviews/identity_review_journal.jsonl',ROOT / 'review_journal.jsonl']:
    if not any(json.loads(line).get('event_id')==event['event_id'] for line in path.read_text().splitlines() if line.strip()):
        with path.open('a') as stream:stream.write(json.dumps(event)+'\n')
print(json.dumps({'batch':67,'status':'PASS','checks':len(checks),'readback_sha256':sha(HERE / 'independent-readback.json')}))
