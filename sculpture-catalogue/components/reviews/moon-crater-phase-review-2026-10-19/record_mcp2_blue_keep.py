"""Save the owner's Blue Splashes identity; retain six unapproved specification groups."""
import copy
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
REVIEWS = ROOT / 'components/reviews'
sys.path.insert(0, str(ROOT / 'components/scripts'))
from review_decision_counts import identity_counts, specification_counts
read = lambda p: json.loads(p.read_text())
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
rel = lambda p: str(p.relative_to(ROOT))


def write(path, value):
    temp = path.with_name(path.name + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    temp.replace(path)


def main():
    output = HERE / 'mcp2-blue-splashes/identity-approval.json'
    assert not output.exists()
    paths = {'user': REVIEWS / 'user_classifications.json', 'progress': REVIEWS / 'specification_review_progress.json',
        'walkthrough': REVIEWS / 'walkthrough_checkpoint.json', 'component': ROOT / 'components/checkpoint.json', 'root': ROOT / 'checkpoint.json'}
    docs = {k: read(path) for k, path in paths.items()}; before = copy.deepcopy(docs)
    hashes = {k: sha(path) for k, path in paths.items()}
    u, p, cp, c = (docs[k] for k in ['user', 'progress', 'walkthrough', 'component'])
    cid, vid = 'BC-MCP-2', 'MCP2-BLUE-SPLASHES'
    assert cp['current_component_id'] == cid and cp['current_size_finish_variant_id'] == vid
    assert not cp['current_answer_recorded'] and docs['root']['current_component_review'] == c
    card_path = ROOT / cp['current_review_record']; card = read(card_path)
    assert card['proposed_name'] == 'Moon Crater Phase 2 — Blue Splashes (MCP2)'
    parent = p['reviews'][cid]; target = parent['size_finish_variants'][vid]
    assert parent['identity_confirmed'] and not target['identity_confirmed']
    assert not any(x.get('component_id') == cid and x.get('size_finish_variant_id') == vid for x in u['size_finish_variant_decisions'])
    protected = {str(path): sha(path) for path in [card_path, HERE / 'mcp2-white/component-review.json',
        HERE / 'mcp2-white/identity-approval.json', ROOT / 'components/evidence/component_register.json', ROOT / cp['register_workbook']]}
    fresh = read(HERE / 'mcp2-blue-splashes/keep-current-reference.json')
    metadata = {x['requested_id']: x['result'] for x in fresh['entries']}
    file, folder = metadata[card['primary_image_id']]['file'], metadata[card['primary_folder_id']]['folder']
    old = next(x['file'] for x in read(HERE / 'mcp2-blue-splashes/selected-metadata.json')['entries'] if x['requested_id'] == file['id'])
    assert all(file[k] == old[k] for k in ['id', 'rev', 'size', 'path_display'])
    assert file['path_display'].rsplit('/', 1)[0] == folder['path_display']
    now = datetime.now(timezone.utc).isoformat()
    scope = ('Keep the Blue Splashes name and depicted individual MCP2identity only. All six conditional groups '
        'remain unapproved:25x25x6cm,4kg, material/paint/sealer, rear fixing/load,350GBPprice and availability. '
        'The related SquarespaceBlue-title record depicts Verdigris/Rust in its source capture; exact Blue offer, '
        'Shopify handle, physical cast/mould, stock and installation/series/rear image coverage remain unresolved.')
    decision = {'schema_version': 1, 'decision_id': cid + ':' + vid + ':identity:keep', 'recorded_utc': now,
        'component_id': cid, 'size_finish_variant_id': vid, 'canonical_name': card['proposed_name'],
        'confirmed_name': card['proposed_name'], 'review_number': 72, 'family_review_number': 2,
        'action': 'keep', 'user_statement': 'Keep “Moon Crater Phase 2 — Blue Splashes (MCP2)”',
        'status': 'USER CONFIRMED FINISH NAME AND DEPICTED INDIVIDUAL IDENTITY ONLY', 'identity_confirmed': True,
        'scope': scope, 'confirmed_fields': ['Individual finish name', 'Depicted MCP2component identity'],
        'not_confirmed': [x['field'] for x in card['specification_review_items']] + ['Exact Blue platform offer', 'Physical cast/mould inventory'],
        'specifications_approved': False, 'proposals_approved': False, 'approved_proposal_ids': [],
        'physical_specs_verified': False, 'physical_manufacture_confirmed': False,
        'proposal_source': rel(card_path), 'proposal_source_sha256': sha(card_path),
        'primary_file_id': file['id'], 'evidence_file_id': file['id'], 'primary_folder_id': folder['id'],
        'evidence_file_ids': [file['id']], 'containing_folder_ids': [folder['id']],
        'current_dropbox_reference': {'file_id': file['id'], 'folder_id': folder['id'],
            'file_path': file['path_display'], 'folder_path': folder['path_display'], 'rev': file['rev'], 'bytes': file['size'],
            'checked_utc': fresh['checked_utc'], 'changed_since_owner_card': False,
            'image_url': card['primary_image_link'], 'folder_url': card['primary_folder_link']},
        'image_link': card['primary_image_link'], 'folder_link': card['primary_folder_link'],
        'remote_files_changed': False, 'live_platform_records_changed': False,
        'workbook_status': 'Unchanged; scoped name/identity saved in local review overlay for later export.'}
    write(HERE / 'mcp2-blue-splashes/before-identity-keep.json', {'recorded_utc': now,
        'files': {rel(paths[k]): value for k, value in before.items()}, 'protected_sha256': protected})
    write(output, decision)
    u['size_finish_variant_decisions'].append(decision | {'approval_record': rel(output)})
    u['identity_confirmation_counts'] = identity_counts(u)
    target.update({'identity_confirmed': True, 'canonical_name': card['proposed_name'], 'identity_confirmed_utc': now,
        'identity_approval': rel(output), 'specification_review_status': 'NAME KEPT; ALL SIX GROUPS AND EXACT BLUE PLATFORM MATCH PENDING',
        'gaps': [x for x in target['gaps'] if x != 'Owner Blue Splashes name and depicted MCP2identity']})
    target['platform_mapping']['dropbox_sculpture_level']['status'] = 'OWNER CONFIRMED DEPICTED MCP2BLUE IDENTITY; PHYSICAL CAST AND EXACT PLATFORM OFFER UNVERIFIED'
    parent['pending_size_finish_variants'] = [x for x in parent['pending_size_finish_variants'] if x['variant_id'] != vid]
    cp['pending_specification_reviews'].append({'component_id': cid, 'size_finish_variant_id': vid,
        'canonical_name': card['proposed_name'], 'identity_approved': True, 'specifications_approved': False,
        'pending_fields': [x['field'] for x in card['specification_review_items']], 'review_record': rel(card_path),
        'identity_approval': rel(output), 'image_link': card['primary_image_link'], 'folder_link': card['primary_folder_link'], 'scope': scope})
    family = p['family_review_progress']['Moon Crater Phase 2']
    assert family['review_reference_cards_answered'] == 1 and family['review_reference_total'] == 3
    family.update({'review_reference_cards_answered': 2, 'updated_utc': now, 'last_identity_approval': rel(output),
        'specifications_complete': False, 'first_pass_reference_review_complete': False})
    state = 'MCP2Blue Splashes name kept; all six groups pending; Verdigris/Rust next'
    cp.update({'current_answer_recorded': True, 'state': state, 'answer_state': scope, 'last_identity_approval': rel(output),
        'last_size_finish_variant_identity_approval': rel(output), 'last_completed_size_finish_variant_id': vid, 'updated_utc': now})
    c['interactive_review_state'].update({'state': state, 'last_identity_approval': rel(output),
        'explicit_size_finish_variant_names_confirmed': u['identity_confirmation_counts']['explicit_size_finish_variant_names'],
        'last_completed_size_finish_variant_id': vid, 'specification_proposals_approved': False})
    c.update({'last_identity_approval': rel(output), 'updated_utc': now})
    u['updated_utc'] = p['updated_utc'] = now
    docs['root']['current_component_review'] = copy.deepcopy(c); docs['root']['updated_utc'] = now
    assert u['identity_confirmation_counts'] == before['user']['identity_confirmation_counts'] | {
        'explicit_size_finish_variant_names': before['user']['identity_confirmation_counts']['explicit_size_finish_variant_names'] + 1}
    assert specification_counts(u) == specification_counts(before['user'])
    for k, value in before['user'].items():
        if k not in ['size_finish_variant_decisions', 'identity_confirmation_counts', 'updated_utc']:
            assert u[k] == value, k
    assert u['size_finish_variant_decisions'][:-1] == before['user']['size_finish_variant_decisions']
    assert all(p['reviews'][k] == value for k, value in before['progress']['reviews'].items() if k != cid)
    assert target['specification_proposals'] == before['progress']['reviews'][cid]['size_finish_variants'][vid]['specification_proposals']
    for k in ['parallel_import_queue', 'parallel_owner_reviews', 'parallel_evidence_flags', 'next_serialized_parallel_import']:
        assert cp[k] == before['walkthrough'][k]
    assert cp['pending_specification_reviews'][:-1] == before['walkthrough']['pending_specification_reviews']
    assert all(sha(path) == hashes[k] for k, path in paths.items())
    assert all(sha(Path(path)) == digest for path, digest in protected.items())
    for k, path in paths.items():
        write(path, docs[k]); assert read(path) == docs[k]
    event = {'event_id': decision['decision_id'], 'event': 'SIZE_FINISH_NAME_AND_DEPICTED_IDENTITY_KEPT',
        'recorded_utc': now, 'component_id': cid, 'identity_approval': rel(output), 'new_specification_approval_inferred': False}
    for path in [REVIEWS / 'identity_review_journal.jsonl', ROOT / 'review_journal.jsonl']:
        with path.open('a') as f:
            f.write(json.dumps(event, ensure_ascii=False) + '\n')
    result = {'status': 'PASS', 'kept_name': card['proposed_name'], 'all_six_groups_unapproved': True,
        'family_reference_answers': '2 of 3known individual finish folders', 'source_offer_mismatch_and_photo_gaps_preserved': True,
        'identity_counts': u['identity_confirmation_counts'], 'accepted_specification_groups': specification_counts(u)['proposal_groups'],
        'prior_approvals_queues_reservations_model_workbook_and_source_cards_preserved': True,
        'checkpoint_copies_match': read(paths['root'])['current_component_review'] == read(paths['component'])}
    write(HERE / 'mcp2-blue-splashes/identity-keep-readback.json', result); print(json.dumps(result))


if __name__ == '__main__':
    main()
