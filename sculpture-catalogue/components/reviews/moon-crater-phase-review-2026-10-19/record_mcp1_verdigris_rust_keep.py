"""Keep the named MCP1 coloured reference, with all specifications still pending."""
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
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    tmp.replace(path)


def main():
    output = HERE / 'mcp1-verdigris-rust/identity-approval.json'
    assert not output.exists()
    paths = {'user': REVIEWS / 'user_classifications.json', 'progress': REVIEWS / 'specification_review_progress.json',
        'walkthrough': REVIEWS / 'walkthrough_checkpoint.json', 'component': ROOT / 'components/checkpoint.json', 'root': ROOT / 'checkpoint.json'}
    docs = {k: read(p) for k, p in paths.items()}; before = copy.deepcopy(docs)
    hashes = {k: sha(p) for k, p in paths.items()}
    u, p, cp, c = (docs[k] for k in ['user', 'progress', 'walkthrough', 'component'])
    vid = 'MCP1-VERDIGRIS-RUST'
    assert cp['current_component_id'] == 'BC-MCP-1' and cp['current_size_finish_variant_id'] == vid
    assert not cp['current_answer_recorded'] and docs['root']['current_component_review'] == c
    card_path = ROOT / cp['current_review_record']; card = read(card_path)
    assert card['proposed_name'] == 'Moon Crater Phase 1 — Verdigris and Rust (MCP1)'
    parent = p['reviews']['BC-MCP-1']; target = parent['size_finish_variants'][vid]
    assert not target['identity_confirmed']
    assert not any(x.get('component_id') == 'BC-MCP-1' and x.get('size_finish_variant_id') == vid for x in u['size_finish_variant_decisions'])
    protected_paths = [card_path, HERE / 'mcp1-white/component-review.json', HERE / 'mcp1-white/identity-approval.json',
        ROOT / 'components/evidence/component_register.json', ROOT / cp['register_workbook']]
    protected = {str(x): sha(x) for x in protected_paths}
    fresh = read(HERE / 'mcp1-verdigris-rust/keep-current-reference.json')
    metadata = {x['requested_id']: x['result'] for x in fresh['metadata']}
    f, fol = metadata[card['primary_image_id']]['file'], metadata[card['primary_folder_id']]['folder']
    old = next(x['file'] for x in read(HERE / 'selected-metadata.json')['entries'] if x['requested_id'] == f['id'])
    assert all(f[k] == old[k] for k in ['id', 'rev', 'size', 'path_display'])
    assert f['path_display'].rsplit('/', 1)[0] == fol['path_display']
    now = datetime.now(timezone.utc).isoformat()
    scope = ('Keep the name and depicted MCP1 Verdigris/Rust identity only. All six conditional specification groups '
        'remain unapproved, including25x25x6cm,4kg, substrate/finish chemistry, rear pairing/hardware/load,150GBP '
        'price and availability. This does not approve an exact public photograph/platform match, a Shopify handle, '
        'physical cast/mould inventory, authenticated installation or Rust-quartet member position.')
    decision = {'schema_version': 1, 'decision_id': 'BC-MCP-1:' + vid + ':identity:keep',
        'recorded_utc': now, 'component_id': 'BC-MCP-1', 'size_finish_variant_id': vid,
        'canonical_name': card['proposed_name'], 'confirmed_name': card['proposed_name'],
        'review_number': 71, 'family_review_number': 2, 'action': 'keep',
        'user_statement': 'Keep “Moon Crater Phase 1 — Verdigris and Rust (MCP1)”',
        'status': 'USER CONFIRMED FINISH NAME AND DEPICTED INDIVIDUAL IDENTITY ONLY',
        'identity_confirmed': True, 'scope': scope, 'specifications_approved': False,
        'proposals_approved': False, 'approved_proposal_ids': [], 'physical_specs_verified': False,
        'physical_manufacture_confirmed': False, 'confirmed_fields': ['Individual finish name', 'Depicted MCP1component identity'],
        'not_confirmed': [x['field'] for x in card['specification_review_items']] + ['Front/rear pairing', 'Exact platform offer/photo binding', 'Physical cast/mould inventory'],
        'proposal_source': rel(card_path), 'proposal_source_sha256': sha(card_path),
        'primary_file_id': f['id'], 'evidence_file_id': f['id'], 'primary_folder_id': fol['id'],
        'evidence_file_ids': [f['id']], 'containing_folder_ids': [fol['id']],
        'current_dropbox_reference': {'file_id': f['id'], 'folder_id': fol['id'],
            'file_path': f['path_display'], 'folder_path': fol['path_display'], 'rev': f['rev'], 'bytes': f['size'],
            'checked_utc': fresh['checked_utc'], 'changed_since_owner_card': False,
            'image_url': card['primary_image_link'], 'folder_url': card['primary_folder_link']},
        'image_link': card['primary_image_link'], 'folder_link': card['primary_folder_link'],
        'remote_files_changed': False, 'live_platform_records_changed': False,
        'workbook_status': 'Unchanged; name/identity saved in local review overlay for later export.'}
    write(HERE / 'mcp1-verdigris-rust/before-identity-keep.json', {'recorded_utc': now,
        'files': {rel(paths[k]): v for k, v in before.items()}, 'protected_sha256': protected})
    write(output, decision)
    u['size_finish_variant_decisions'].append(decision | {'approval_record': rel(output)})
    u['identity_confirmation_counts'] = identity_counts(u)
    target.update({'identity_confirmed': True, 'canonical_name': card['proposed_name'],
        'identity_confirmed_utc': now, 'identity_approval': rel(output),
        'specification_review_status': 'FINISH NAME KEPT; SIX GROUPS, REAR PAIRING AND EXACT PLATFORM MATCH PENDING',
        'gaps': [x for x in target['gaps'] if x != 'Owner Verdigris and Rust finish name and depicted MCP1identity']})
    target['platform_mapping']['dropbox_sculpture_level']['status'] = 'OWNER CONFIRMED DEPICTED MCP1FINISH IDENTITY; EXACT PUBLIC PHOTO/CAST BINDING UNRESOLVED'
    parent['pending_size_finish_variants'] = []
    cp['pending_specification_reviews'].append({'component_id': 'BC-MCP-1', 'size_finish_variant_id': vid,
        'canonical_name': card['proposed_name'], 'identity_approved': True, 'specifications_approved': False,
        'pending_fields': [x['field'] for x in card['specification_review_items']], 'review_record': rel(card_path),
        'identity_approval': rel(output), 'image_link': card['primary_image_link'], 'folder_link': card['primary_folder_link'], 'scope': scope})
    family = p['family_review_progress']['Moon Crater Phase 1']
    assert family['review_reference_cards_answered'] == 1 and family['review_reference_total'] == 2
    family.update({'review_reference_cards_answered': 2, 'status': 'KNOWN_INDIVIDUAL_REFERENCE_NAMES_REVIEWED_SPECIFICATIONS_AND_RUST_ATTRIBUTION_PENDING',
        'updated_utc': now, 'last_identity_approval': rel(output), 'first_pass_reference_review_complete': True,
        'specifications_complete': False, 'physical_specs_verified': False})
    family_path = HERE / 'mcp1-known-reference-first-pass.json'
    write(family_path, family | {'component_ids': ['BC-MCP-1'],
        'scope': 'Two known individual finish references named; all12specification groups unapproved. Rust-quartet attribution, other Moon Crater designs, physical cast/mould totals and exact offers remain pending.',
        'approved_name_records': [rel(HERE / 'mcp1-white/identity-approval.json'), rel(output)],
        'next_review': cp['next_review_after_keep'], 'workbook_contains_this_first_pass': False})
    family['first_pass_record'] = rel(family_path)
    state = 'MCP1White and Verdigris/Rust names kept;12specification groups pending; MCP2next'
    cp.update({'current_answer_recorded': True, 'state': state, 'answer_state': scope,
        'last_identity_approval': rel(output), 'last_size_finish_variant_identity_approval': rel(output),
        'last_completed_size_finish_variant_id': vid, 'family_first_pass_complete': True,
        'last_completed_family_first_pass': rel(family_path), 'updated_utc': now})
    c['interactive_review_state'].update({'state': state, 'last_identity_approval': rel(output),
        'explicit_size_finish_variant_names_confirmed': u['identity_confirmation_counts']['explicit_size_finish_variant_names'],
        'last_completed_size_finish_variant_id': vid, 'specification_proposals_approved': False})
    c.update({'last_identity_approval': rel(output), 'last_completed_family_first_pass': rel(family_path), 'updated_utc': now})
    u['updated_utc'] = p['updated_utc'] = now
    docs['root']['current_component_review'] = copy.deepcopy(c); docs['root']['updated_utc'] = now
    assert u['identity_confirmation_counts'] == before['user']['identity_confirmation_counts'] | {
        'explicit_size_finish_variant_names': before['user']['identity_confirmation_counts']['explicit_size_finish_variant_names'] + 1}
    assert specification_counts(u) == specification_counts(before['user'])
    for k, value in before['user'].items():
        if k not in ['size_finish_variant_decisions', 'identity_confirmation_counts', 'updated_utc']:
            assert u[k] == value, k
    assert u['size_finish_variant_decisions'][:-1] == before['user']['size_finish_variant_decisions']
    assert all(p['reviews'][k] == value for k, value in before['progress']['reviews'].items() if k != 'BC-MCP-1')
    assert target['specification_proposals'] == before['progress']['reviews']['BC-MCP-1']['size_finish_variants'][vid]['specification_proposals']
    assert parent['pending_arrangement_component_review'] == before['progress']['reviews']['BC-MCP-1']['pending_arrangement_component_review']
    for k in ['parallel_import_queue', 'parallel_owner_reviews', 'parallel_evidence_flags', 'next_serialized_parallel_import']:
        assert cp[k] == before['walkthrough'][k]
    assert cp['pending_specification_reviews'][:-1] == before['walkthrough']['pending_specification_reviews']
    assert all(sha(path) == hashes[k] for k, path in paths.items())
    assert all(sha(Path(path)) == digest for path, digest in protected.items())
    for k, path in paths.items():
        write(path, docs[k]); assert read(path) == docs[k]
    event = {'event_id': decision['decision_id'], 'event': 'SIZE_FINISH_NAME_AND_DEPICTED_IDENTITY_KEPT',
        'recorded_utc': now, 'component_id': 'BC-MCP-1', 'identity_approval': rel(output), 'new_specification_approval_inferred': False}
    for path in [REVIEWS / 'identity_review_journal.jsonl', ROOT / 'review_journal.jsonl']:
        with path.open('a') as f:
            f.write(json.dumps(event, ensure_ascii=False) + '\n')
    result = {'status': 'PASS', 'kept_name': card['proposed_name'], 'all_six_groups_unapproved': True,
        'MCP1known_reference_names_answered': '2 of 2;12specification groups pending',
        'rear_pairing_Rust_positions_platform_matches_and_photo_gaps_pending': True,
        'identity_counts': u['identity_confirmation_counts'], 'accepted_specification_groups': specification_counts(u)['proposal_groups'],
        'prior_reviews_queues_reservations_model_workbook_and_source_cards_preserved': True,
        'checkpoint_copies_match': read(paths['root'])['current_component_review'] == read(paths['component'])}
    write(HERE / 'mcp1-verdigris-rust/identity-keep-readback.json', result)
    print(json.dumps(result))


if __name__ == '__main__':
    main()
