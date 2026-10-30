"""Record the owner's MCP1 White identity without approving specifications."""
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
    output = HERE / 'mcp1-white/identity-approval.json'
    assert not output.exists(), 'MCP1 White identity already recorded'
    paths = {'user': REVIEWS / 'user_classifications.json',
             'progress': REVIEWS / 'specification_review_progress.json',
             'walkthrough': REVIEWS / 'walkthrough_checkpoint.json',
             'component': ROOT / 'components/checkpoint.json', 'root': ROOT / 'checkpoint.json'}
    docs = {key: read(path) for key, path in paths.items()}
    before = copy.deepcopy(docs)
    digests = {key: sha(path) for key, path in paths.items()}
    u, p, cp, c = (docs[key] for key in ['user', 'progress', 'walkthrough', 'component'])
    assert cp['current_component_id'] == 'BC-MCP-1'
    assert cp['current_size_finish_variant_id'] == 'MCP1-WHITE' and not cp['current_answer_recorded']
    assert docs['root']['current_component_review'] == c
    card_path = ROOT / cp['current_review_record']
    card = read(card_path)
    assert card['proposed_name'] == 'Moon Crater Phase 1 — White (MCP1)'
    assert card['identity_decision_destination'] == 'decisions'
    target = p['reviews']['BC-MCP-1']
    assert not target['identity_confirmed']
    assert not any(x['component_id'] == 'BC-MCP-1' for x in u['decisions'])
    protected_paths = [card_path, ROOT / 'components/evidence/component_register.json',
                       ROOT / cp['register_workbook'], ROOT / cp['last_identity_approval']]
    protected = {str(path): sha(path) for path in protected_paths}
    fresh = read(HERE / 'owner-keep-current-reference.json')['metadata']
    metadata = {x['requested_id']: x['result'] for x in fresh['entries']}
    file, folder = metadata[card['primary_image_id']]['file'], metadata[card['primary_folder_id']]['folder']
    old = next(x['file'] for x in read(HERE / 'selected-metadata.json')['entries']
               if x['requested_id'] == file['id'])
    assert all(file[key] == old[key] for key in ['id', 'rev', 'size', 'path_display'])
    assert file['path_display'].rsplit('/', 1)[0] == folder['path_display']
    now = datetime.now(timezone.utc).isoformat()
    scope = ('Keep the individual White MCP1 panel name and depicted design only. All six specification '
             'groups remain unapproved: historical 25 x 25 cm / 4–6 cm depth, separate maker 2–4 kg, '
             'trade 4 kg and retail 5 kg estimates, actual material, White rear hardware/load, current '
             'individual price and availability. Exact White platform offer, physical cast/mould inventory, '
             'clean-image provenance and Rust-quartet member attribution remain unresolved.')
    decision = {'schema_version': 1, 'decision_id': 'BC-MCP-1:identity:keep',
        'recorded_utc': now, 'component_id': 'BC-MCP-1', 'size_finish_variant_id': 'MCP1-WHITE',
        'canonical_name': card['proposed_name'], 'confirmed_name': card['proposed_name'],
        'review_number': 71, 'family_review_number': 1, 'action': 'keep',
        'user_statement': 'Keep “Moon Crater Phase 1 — White (MCP1)”',
        'status': 'USER CONFIRMED NAME AND DEPICTED INDIVIDUAL IDENTITY ONLY',
        'identity_confirmed': True, 'scope': scope,
        'confirmed_fields': ['Individual component name', 'Depicted White MCP1 design identity'],
        'not_confirmed': [x['field'] for x in card['specification_review_items']] +
            ['Physical cast/mould inventory', 'Exact White platform offer', 'Rust-quartet member attribution'],
        'specifications_approved': False, 'proposals_approved': False, 'approved_proposal_ids': [],
        'physical_specs_verified': False, 'physical_manufacture_confirmed': False,
        'proposal_source': rel(card_path), 'proposal_source_sha256': sha(card_path),
        'primary_file_id': file['id'], 'evidence_file_id': file['id'],
        'primary_folder_id': folder['id'], 'evidence_file_ids': [file['id']],
        'containing_folder_ids': [folder['id']],
        'current_dropbox_reference': {'file_id': file['id'], 'folder_id': folder['id'],
            'file_path': file['path_display'], 'folder_path': folder['path_display'],
            'rev': file['rev'], 'bytes': file['size'], 'checked_utc': fresh['checked_utc'],
            'changed_since_owner_card': False, 'image_url': card['primary_image_link'],
            'folder_url': card['primary_folder_link']},
        'image_link': card['primary_image_link'], 'folder_link': card['primary_folder_link'],
        'remote_files_changed': False, 'live_platform_records_changed': False,
        'workbook_status': 'Unchanged; name and identity saved in local review overlay for later export.'}
    write(HERE / 'mcp1-white/before-identity-keep.json', {'recorded_utc': now,
        'files': {rel(paths[key]): value for key, value in before.items()}, 'protected_sha256': protected})
    write(output, decision)
    u['decisions'].append(decision | {'approval_record': rel(output)})
    u['identity_confirmation_counts'] = identity_counts(u)
    target.update({'identity_confirmed': True, 'canonical_name': card['proposed_name'],
        'identity_confirmed_utc': now, 'identity_approval': rel(output),
        'specification_review_status': 'WHITE NAME KEPT; ALL SIX GROUPS PENDING; WEIGHT SOURCES RETAINED',
        'gaps': [x for x in target['gaps'] if x != 'Owner White MCP1name and depicted identity']})
    target['platform_mapping']['dropbox_component_level']['status'] = (
        'OWNER CONFIRMED DEPICTED WHITE MCP1 IDENTITY; LABELLED SOURCE AND EXACT027 SERIES BINDING RETAINED')
    assert not any(x.get('component_id') == 'BC-MCP-1' for x in cp['pending_specification_reviews'])
    cp['pending_specification_reviews'].append({'component_id': 'BC-MCP-1',
        'size_finish_variant_id': 'MCP1-WHITE', 'canonical_name': card['proposed_name'],
        'identity_approved': True, 'specifications_approved': False,
        'pending_fields': [x['field'] for x in card['specification_review_items']],
        'review_record': rel(card_path), 'identity_approval': rel(output),
        'image_link': card['primary_image_link'], 'folder_link': card['primary_folder_link'], 'scope': scope})
    family = p['family_review_progress']['Moon Crater Phase 1']
    assert family['review_reference_cards_answered'] == 0 and family['review_reference_total'] == 2
    family.update({'review_reference_cards_answered': 1, 'updated_utc': now,
                   'last_identity_approval': rel(output), 'specifications_complete': False})
    state = 'MCP1 White name kept; six specification groups pending; Verdigris and Rust next'
    cp.update({'current_answer_recorded': True, 'state': state, 'answer_state': scope,
               'last_identity_approval': rel(output), 'updated_utc': now})
    counts = u['identity_confirmation_counts']
    c['interactive_review_state'].update({'state': state, 'last_identity_approval': rel(output),
        'explicit_identity_confirmations': counts['component_designs'],
        'components_with_any_identity_scope': counts['components_with_any_identity_scope'],
        'specification_proposals_approved': False})
    c.update({'last_identity_approval': rel(output), 'updated_utc': now})
    u['updated_utc'] = p['updated_utc'] = now
    docs['root']['current_component_review'] = copy.deepcopy(c)
    docs['root']['updated_utc'] = now
    expected = before['user']['identity_confirmation_counts'] | {
        'component_designs': before['user']['identity_confirmation_counts']['component_designs'] + 1,
        'components_with_any_identity_scope': before['user']['identity_confirmation_counts']['components_with_any_identity_scope'] + 1}
    assert counts == expected
    assert specification_counts(u) == specification_counts(before['user'])
    for key in before['user']:
        if key not in ['decisions', 'identity_confirmation_counts', 'updated_utc']:
            assert u[key] == before['user'][key], key
    assert u['decisions'][:-1] == before['user']['decisions']
    assert all(p['reviews'][key] == value for key, value in before['progress']['reviews'].items()
               if key != 'BC-MCP-1')
    assert target['specification_proposals'] == before['progress']['reviews']['BC-MCP-1']['specification_proposals']
    assert target['pending_arrangement_component_review'] == before['progress']['reviews']['BC-MCP-1']['pending_arrangement_component_review']
    for key in ['parallel_import_queue', 'parallel_owner_reviews', 'parallel_evidence_flags', 'next_serialized_parallel_import']:
        assert cp[key] == before['walkthrough'][key]
    assert cp['pending_specification_reviews'][:-1] == before['walkthrough']['pending_specification_reviews']
    assert all(sha(path) == digests[key] for key, path in paths.items()), 'Shared writer collision'
    assert all(sha(Path(path)) == digest for path, digest in protected.items())
    for key, path in paths.items():
        write(path, docs[key])
        assert read(path) == docs[key]
    event = {'event_id': decision['decision_id'], 'event': 'COMPONENT_NAME_AND_DEPICTED_IDENTITY_KEPT',
        'recorded_utc': now, 'component_id': 'BC-MCP-1', 'identity_approval': rel(output),
        'new_specification_approval_inferred': False}
    for path in [REVIEWS / 'identity_review_journal.jsonl', ROOT / 'review_journal.jsonl']:
        with path.open('a') as f:
            f.write(json.dumps(event, ensure_ascii=False) + '\n')
    result = {'status': 'PASS', 'kept_name': card['proposed_name'],
        'all_six_groups_unapproved': True, 'weight_sources_and_unresolved_arrangements_preserved': True,
        'family_reference_answers': '1 of 2', 'identity_counts': counts,
        'specification_counts': specification_counts(u),
        'prior_reviews_imports_queues_reservations_model_and_workbook_preserved': True,
        'checkpoint_copies_match': read(paths['root'])['current_component_review'] == read(paths['component'])}
    write(HERE / 'mcp1-white/identity-keep-readback.json', result)
    print(json.dumps(result))


if __name__ == '__main__':
    main()
