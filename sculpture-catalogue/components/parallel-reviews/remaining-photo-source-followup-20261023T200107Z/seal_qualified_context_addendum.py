import datetime
import hashlib
import json
from pathlib import Path
from urllib.parse import quote

J = Path(__file__).parent
B = J.parents[2]
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
now = datetime.datetime.now(datetime.timezone.utc).isoformat()
pointer = read(B / 'current-master.json')
register_path = B / pointer['register']
reg = {x['product_id']: x for x in read(register_path)['options']}
coverage = {x['option_id']: x for x in read(register_path.with_name('image-coverage-current.json'))['coverage']}
metadata = {x['id']: x['data']['file'] for x in read(J / 'qualified-context-recheck-metadata.json')['entries']}
parents = {x['id']: x['data']['folder'] for x in read(J / 'qualified-context-recheck-parents.json')['entries']}
originals = {x['file_id']: x for x in read(J / 'qualified-context-recheck-originals.json')['sources']}
lists = read(J / 'current-family-listings.json')['option_listings']
prior = {x['option_id']: x for x in read(J / 'context-photograph-requests.json')['requests']}
cache = {x['option_id']: x for x in read(J.parent / 'remaining-insitu-review-20261023T190856Z/primary-cache-index.json')}
transcript = Path('/Users/tprice/.codex/sessions/2026/10/15/rollout-2026-10-15T15-10-19-01a13fe6-495b-7253-b923-31823b4cbca8.jsonl')
with transcript.open('rb') as f:
    raw = next(line for i, line in enumerate(f, 1) if i == 43587)
event = json.loads(raw)
assert event['payload']['role'] == 'user'
owner_text = event['payload']['content'][0]['text']
assert owner_text.startswith('Do these: 1. Main session: finish the bordered Moonphase folder corrections.')
(J / 'owner-instruction-event.jsonl').write_bytes(raw)
policy = J.parent / 'installation-review-coordination-20261023T192240Z/owner-instruction-evidence.json'
independent = J.parent / 'remaining-photo-sources-and-bordered-import-20261023T200049Z/independent-workshop-garden-context-review.json'
assert sha(independent) == 'b05a50c511356e55f6252e89d648d1c43fd51caf30231b394eb31b12ec861220'
authority = {'recorded_utc': now, 'authority_type': 'OWNER_AUTHORIZED_REVIEWER_SELECTION', 'owner_instruction': {'transcript': str(transcript), 'line': 43587, 'timestamp': event['timestamp'], 'raw_event_no_newline_sha256': hashlib.sha256(raw.rstrip(b'\n')).hexdigest(), 'saved_event': str(J / 'owner-instruction-event.jsonl'), 'saved_event_sha256': sha(J / 'owner-instruction-event.jsonl'), 'text': owner_text}, 'accepted_display_policy': {'path': str(policy), 'sha256': sha(policy)}, 'interpretation': 'Apply the accepted labelled display-reference convention to an identifiable whole panel in a workshop or garden setting. Minor foliage overlap is explicitly retained as a limitation. Neither role claims a permanent installation, source authenticity, physical measurements or a personal per-image Use image answer.'}
(J / 'qualified-context-authority.json').write_text(json.dumps(authority, ensure_ascii=False, indent=2) + '\n')
cases = [
    ('BSI-207102CFD25C', 'Workshop/tabletop context', 'The entire current primary panel is within the frame on protective cloth, with brushes and temporary supports/handles visible around it. This is a workshop/tabletop context reference. It does not establish an installed position, approved fixing hardware, measured dimensions or actual current stock. The same exact current source remains the individual primary.'),
    ('BSI-2418C8B43415', 'Garden-ground display — minor foliage overlap', 'The complete identifiable Textured Gold Leaf Panel Curves sculpture is framed against surrounding garden foliage. A leaf crosses a small part of the lower-right edge; that overlap is explicitly retained. This is a garden-ground display reference, not a verified installed or mounted position. No photographic origin, actual dimensions, fitted hardware or current stock is certified.'),
]
decisions = []
checks = []
for seq, (oid, label, basis) in enumerate(cases, 1):
    option = reg[oid]
    fid, folder_id = option['file_id'], option['folder_id']
    source, meta, folder = originals[fid], metadata[fid], parents[folder_id]
    assert sha(source['local_original_path']) == source['sha256'] == sha(cache[oid]['paths']['full'])
    assert source['size'] == meta['size'] and source['rev'] == meta['rev']
    assert str(Path(meta['path_display']).parent).casefold() == folder['path_display'].casefold()
    matching = [x for x in lists if x['id'] == folder_id]
    assert len(matching) == 1 and all(not p['has_more'] for p in matching[0]['pages'])
    listed = [e for p in matching[0]['pages'] for e in p['entries'] if e['file_id'] == fid]
    assert len(listed) == 1 and listed[0]['file']['size'] == source['size']
    assert coverage[oid]['in_situ']['status'] == 'No verified image'
    ref = {'file_id': fid, 'folder_id': folder_id, 'name': meta['name'], 'path': listed[0]['path'], 'path_display': meta['path_display'], 'rev': meta['rev'], 'size': source['size'], 'content_hash': source['dropbox_content_hash'], 'sha256': source['sha256'], 'dimensions': source['dimensions'], 'image_url': 'https://www.dropbox.com/home' + quote(folder['path_display'], safe='/') + '?preview=' + quote(meta['name'], safe=''), 'folder_url': 'https://www.dropbox.com/home' + quote(folder['path_display'], safe='/'), 'review_label': label, 'native_reference_status': 'CURRENT_MASTER_FILE_AND_ACTUAL_PARENT_VERIFIED', 'whole_original_only': True, 'scene_authenticity_verified': False, 'physical_cast_or_size_certified': False}
    decisions.append({'decision_id': f'REVIEWER-WORKSHOP-GARDEN-20261023-{seq:02d}', 'product_id': oid, 'name': option['name'], 'role': 'In situ', 'status_before': 'No verified image', 'status_after': 'Available', 'decision_kind': 'REVIEWER_SELECTED_QUALIFIED_DISPLAY_REFERENCE', 'explicit_owner_image_role_approval': False, 'reviewer_selected_reference': True, 'owner_directed_editorial_completion': True, 'personal_owner_Use_image_answer': False, 'reference': ref, 'basis': basis, 'display_qualification': label, 'source_qualified_visual_binding': True, 'scene_authenticity_verified': False, 'wider_room_or_garden_view_verified': False, 'physical_cast_or_size_certified': False, 'existing_individual_reference': coverage[oid]['individual']['reference'], 'individual_primary_file_id_to_preserve': fid, 'series_policy_to_preserve': coverage[oid]['series'], 'private_source_original_path': source['local_original_path'], 'pixels_edited': False, 'baseline_option_semantic_sha256': hashlib.sha256(json.dumps(option, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest(), 'superseded_prior_negative': prior[oid], 'reason_for_reassessment': 'The prior context exclusion was too narrow under the accepted qualified-display convention. Retain the original negative as history and disclose the workshop/garden limitation; no new physical or identity assertion is made.'})
    checks.append({'option_id': oid, 'file_id': fid, 'actual_parent_id': folder_id, 'fresh_original_equals_whole_cached_original_independently_viewed': True, 'whole_original_sha256': source['sha256'], 'dropbox_content_hash_verified': True, 'actual_current_parent_and_complete_membership_verified': True, 'primary_and_series_preserved': True})
preflight = {'recorded_utc': now, 'status': 'PASS_TWO_CURRENT_SOURCE_BINDINGS_AND_WHOLE_ORIGINALS', 'checks': checks, 'independent_visual_review': {'path': str(independent), 'sha256': sha(independent)}, 'no_native_or_platform_writes': True}
(J / 'qualified-context-source-preflight.json').write_text(json.dumps(preflight, ensure_ascii=False, indent=2) + '\n')
packet = {'schema': 'boldstone.reviewer-qualified-display-decisions.v1', 'recorded_utc': now, 'status': 'READY_FOR_ROOT_IMPORT', 'authority': {'path': str(J / 'qualified-context-authority.json'), 'sha256': sha(J / 'qualified-context-authority.json')}, 'source_preflight': {'path': str(J / 'qualified-context-source-preflight.json'), 'sha256': sha(J / 'qualified-context-source-preflight.json')}, 'baseline_register': {'path': str(register_path), 'sha256': sha(register_path)}, 'decisions': decisions, 'expected_scope_delta': {'additional_qualified_context_roles': 2, 'after_bordered_two_plus_this_addendum': {'active_options': 187, 'active_context_gaps': 14, 'held_context_gaps': 8, 'all_in_situ_gaps': 22, 'series_gaps': 17, 'required_actions_including_deferred_identity': 40}}, 'preserve': ['All individual primaries', 'All series roles', 'All physical and selling fields', 'All held cases', 'Deferred Frozen Fish identity'], 'scope_exclusions': ['Pewter and other unresolved exact-source requests', 'Any new physical or per-image personal approval claims'], 'canonical_or_workbook_writes_by_this_lane': 0, 'native_or_platform_writes': 0}
(J / 'qualified-workshop-garden-decisions.json').write_text(json.dumps(packet, ensure_ascii=False, indent=2) + '\n')
remaining = read(J / 'context-photograph-requests.json')
remaining['historical_superseded_request_packet'] = {'path': str(J / 'context-photograph-requests.json'), 'sha256': sha(J / 'context-photograph-requests.json')}
remaining['recorded_utc'] = now
remaining['status'] = 'THIRTEEN_CONTEXT_REQUESTS_REMAIN_AFTER_TWO_PREPARED_QUALIFIED_REFERENCES'
remaining['requests'] = [x for x in remaining['requests'] if x['option_id'] not in {d['product_id'] for d in decisions}]
remaining['request_count'] = len(remaining['requests'])
remaining['new_qualified_matches'] = 2
remaining['qualified_context_addendum'] = {'path': str(J / 'qualified-workshop-garden-decisions.json'), 'sha256': sha(J / 'qualified-workshop-garden-decisions.json')}
assert remaining['request_count'] == 13
(J / 'context-photograph-requests-after-qualified-recheck.json').write_text(json.dumps(remaining, ensure_ascii=False, indent=2) + '\n')
seal = {'recorded_utc': now, 'status': 'SEALED_TWO_ROLE_QUALIFIED_CONTEXT_ADDENDUM', 'decisions': str(J / 'qualified-workshop-garden-decisions.json'), 'decisions_sha256': sha(J / 'qualified-workshop-garden-decisions.json'), 'source_preflight_sha256': sha(J / 'qualified-context-source-preflight.json'), 'authority_sha256': sha(J / 'qualified-context-authority.json'), 'independent_review_sha256': sha(independent), 'preserved_prior_negative_packet_sha256': sha(J / 'context-photograph-requests.json'), 'remaining_B_context_requests': 13}
(J / 'qualified-context-packet-seal.json').write_text(json.dumps(seal, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(seal))
