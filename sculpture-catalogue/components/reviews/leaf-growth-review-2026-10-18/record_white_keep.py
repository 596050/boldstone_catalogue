"""Save the White name/identity only; retain all six specification checks."""
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
from review_decision_counts import identity_counts
read = lambda p: json.loads(p.read_text())
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
rel = lambda p: str(p.relative_to(ROOT))


def write(path, value):
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    tmp.replace(path)


def main():
    output = HERE / 'identity-approval.json'
    assert not output.exists(), 'White identity already kept'
    paths = {'user': REVIEWS / 'user_classifications.json', 'progress': REVIEWS / 'specification_review_progress.json',
        'walkthrough': REVIEWS / 'walkthrough_checkpoint.json', 'component': ROOT / 'components/checkpoint.json',
        'root': ROOT / 'checkpoint.json'}
    docs = {key: read(path) for key, path in paths.items()}
    before = copy.deepcopy(docs)
    hashes = {key: sha(path) for key, path in paths.items()}
    u, p, cp, c = (docs[key] for key in ['user', 'progress', 'walkthrough', 'component'])
    assert cp['current_component_id'] == 'BC-LEAF-GROWTH' and not cp['current_answer_recorded']
    assert cp['current_size_finish_variant_id'] == 'LEAF-GROWTH-WHITE'
    assert docs['root']['current_component_review'] == c
    card_path = ROOT / cp['current_review_record']
    card = read(card_path)
    assert card['proposed_name'] == 'Leaf Growth — White (Magnolia Leaves)'
    assert card['identity_decision_destination'] == 'decisions'
    target = p['reviews']['BC-LEAF-GROWTH']
    assert not target['identity_confirmed'] and not any(x['component_id'] == 'BC-LEAF-GROWTH' for x in u['decisions'])
    protected_paths = [card_path, ROOT / 'components/evidence/component_register.json', ROOT / cp['register_workbook'],
        ROOT / cp['last_identity_approval'], ROOT / cp['last_completed_family_first_pass']]
    protected = {str(path): sha(path) for path in protected_paths}
    fresh = read(HERE / 'white-keep-gold-refresh.json')
    file = next(x['result']['file'] for x in fresh['metadata'] if x['requested_id'] == card['primary_image_id'])
    old = next(x['file'] for x in read(HERE / 'selected-metadata.json')['entries'] if x['requested_id'] == file['id'])
    assert all(file[key] == old[key] for key in ['id', 'rev', 'size', 'path_display'])
    now = datetime.now(timezone.utc).isoformat()
    scope = ('Keep the individual White Leaf Growth/Magnolia Leaves name and depicted one-panel identity only. '
        'All six source/proposal groups remain unapproved.100×30×6cm remains an unmeasured listing claim; '
        '18kgShopify versus12kghistorical mass remains unresolved. Actual binder, rear hardware,800GBPprice adoption, '
        'physical stock, production, current mould inventory and Gold-finish offer/specifications are not confirmed.')
    decision = {'schema_version': 1, 'decision_id': 'BC-LEAF-GROWTH:identity:keep', 'recorded_utc': now,
        'component_id': 'BC-LEAF-GROWTH', 'size_finish_variant_id': 'LEAF-GROWTH-WHITE',
        'canonical_name': card['proposed_name'], 'confirmed_name': card['proposed_name'], 'review_number': 68,
        'family_review_number': 1, 'action': 'keep', 'user_statement': 'Keep “Leaf Growth — White (Magnolia Leaves)”',
        'status': 'USER CONFIRMED NAME AND DEPICTED INDIVIDUAL IDENTITY ONLY', 'identity_confirmed': True,
        'scope': scope, 'confirmed_fields': ['Individual component name', 'Depicted White one-panel identity'],
        'not_confirmed': [x['field'] for x in card['specification_review_items']] + ['Physical cast/mould inventory',
            'Exact physical cast equivalence between photographs', 'Gold finish identity/specifications/offer'],
        'specifications_approved': False, 'proposals_approved': False, 'approved_proposal_ids': [],
        'physical_specs_verified': False, 'physical_manufacture_confirmed': False,
        'proposal_source': rel(card_path), 'proposal_source_sha256': sha(card_path),
        'primary_file_id': file['id'], 'evidence_file_id': file['id'], 'primary_folder_id': card['primary_folder_id'],
        'evidence_file_ids': [file['id']], 'containing_folder_ids': [card['primary_folder_id']],
        'current_dropbox_reference': {'file_id': file['id'], 'folder_id': card['primary_folder_id'],
            'file_path': file['path_display'], 'rev': file['rev'], 'bytes': file['size'],
            'checked_utc': fresh['checked_utc'], 'changed_since_owner_card': False,
            'image_url': card['primary_image_link'], 'folder_url': card['primary_folder_link']},
        'image_link': card['primary_image_link'], 'folder_link': card['primary_folder_link'],
        'remote_files_changed': False, 'live_platform_records_changed': False,
        'workbook_status': 'Unchanged; owner name/identity saved in review overlay for later export.'}
    write(HERE / 'before-identity-keep.json', {'recorded_utc': now,
        'files': {rel(paths[key]): value for key, value in before.items()}, 'protected_sha256': protected})
    write(output, decision)
    u['decisions'].append(decision | {'approval_record': rel(output)})
    u['identity_confirmation_counts'] = identity_counts(u)
    target.update({'identity_confirmed': True, 'canonical_name': card['proposed_name'], 'identity_confirmed_utc': now,
        'identity_approval': rel(output), 'specification_review_status': 'WHITE NAME KEPT; ALL SIX GROUPS PENDING;18kgVERSUS12kgUNRESOLVED',
        'gaps': [x for x in target['gaps'] if x != 'Owner White name and depicted identity']})
    assert not any(x['component_id'] == 'BC-LEAF-GROWTH' for x in cp['pending_specification_reviews'])
    cp['pending_specification_reviews'].append({'component_id': 'BC-LEAF-GROWTH',
        'size_finish_variant_id': 'LEAF-GROWTH-WHITE', 'canonical_name': card['proposed_name'],
        'identity_approved': True, 'specifications_approved': False,
        'pending_fields': [x['field'] for x in card['specification_review_items']], 'review_record': rel(card_path),
        'identity_approval': rel(output), 'image_link': card['primary_image_link'], 'folder_link': card['primary_folder_link'], 'scope': scope})
    family = p['family_review_progress']['Leaf Growth']
    assert family['review_reference_cards_answered'] == 0 and family['review_reference_total'] == 2
    family.update({'review_reference_cards_answered': 1, 'updated_utc': now,
        'last_identity_approval': rel(output), 'specifications_complete': False})
    state = 'Leaf Growth White name kept; six groups pending; White and Gold Leaf detail reference next'
    cp.update({'current_answer_recorded': True, 'state': state, 'answer_state': scope,
        'last_identity_approval': rel(output), 'updated_utc': now})
    c['interactive_review_state'].update({'state': state,
        'explicit_identity_confirmations': u['identity_confirmation_counts']['component_designs'],
        'components_with_any_identity_scope': u['identity_confirmation_counts']['components_with_any_identity_scope'],
        'last_identity_approval': rel(output), 'specification_proposals_approved': False})
    c.update({'last_identity_approval': rel(output), 'updated_utc': now})
    u['updated_utc'] = p['updated_utc'] = now
    docs['root']['current_component_review'] = copy.deepcopy(c)
    docs['root']['updated_utc'] = now
    assert u['identity_confirmation_counts'] == before['user']['identity_confirmation_counts'] | {
        'component_designs': 44, 'components_with_any_identity_scope': 84}
    for key in before['user']:
        if key not in ['decisions', 'identity_confirmation_counts', 'updated_utc']:
            assert u[key] == before['user'][key], key
    assert u['decisions'][:-1] == before['user']['decisions']
    assert all(p['reviews'][key] == value for key, value in before['progress']['reviews'].items() if key != 'BC-LEAF-GROWTH')
    assert not any(x['owner_approved'] for x in target['specification_proposals'])
    for key in ['parallel_import_queue', 'parallel_owner_reviews', 'parallel_evidence_flags']:
        assert cp[key] == before['walkthrough'][key]
    assert cp['pending_specification_reviews'][:-1] == before['walkthrough']['pending_specification_reviews']
    assert all(sha(path) == hashes[key] for key, path in paths.items()), 'Shared writer collision'
    assert all(sha(Path(path)) == digest for path, digest in protected.items())
    for key, path in paths.items():
        write(path, docs[key])
        assert read(path) == docs[key]
    event = {'event_id': decision['decision_id'], 'event': 'COMPONENT_NAME_AND_DEPICTED_IDENTITY_KEPT',
        'recorded_utc': now, 'component_id': 'BC-LEAF-GROWTH', 'identity_approval': rel(output),
        'new_specification_approval_inferred': False}
    for path in [REVIEWS / 'identity_review_journal.jsonl', ROOT / 'review_journal.jsonl']:
        with path.open('a') as f:
            f.write(json.dumps(event, ensure_ascii=False) + '\n')
    result = {'status': 'PASS', 'kept_name': card['proposed_name'], 'all_six_groups_unapproved': True,
        'source_weight_conflict_preserved': True, 'family_reference_answers': '1 of 2',
        'baseline_model_workbook_previous_approvals_imports_and_reservations_preserved': True,
        'checkpoint_copies_match': read(paths['root'])['current_component_review'] == read(paths['component'])}
    write(HERE / 'identity-keep-readback.json', result)
    print(json.dumps(result))


if __name__ == '__main__':
    main()
