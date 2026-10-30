"""Record selected blue-reference name only; keep darker-reference relationship open."""
import copy
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
REVIEWS = ROOT / 'components/reviews'
sys.path.insert(0, str(ROOT / 'components/scripts'))
from review_decision_counts import identity_counts, specification_counts

read = lambda p: json.loads(p.read_text())
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
rel = lambda p: str(p.relative_to(ROOT))


def write(path, value):
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    temporary.replace(path)


def main():
    output = HERE / 'identity-approval.json'
    assert not output.exists(), 'Already kept'
    paths = {'user': REVIEWS / 'user_classifications.json', 'progress': REVIEWS / 'specification_review_progress.json',
             'walkthrough': REVIEWS / 'walkthrough_checkpoint.json', 'component': ROOT / 'components/checkpoint.json',
             'root': ROOT / 'checkpoint.json'}
    docs = {key: read(path) for key, path in paths.items()}
    before = copy.deepcopy(docs)
    hashes = {key: sha(path) for key, path in paths.items()}
    u, p, cp, component = (docs[key] for key in ['user', 'progress', 'walkthrough', 'component'])
    variant = 'FOUNTAIN-EG-BRONZE-VERDIGRIS'
    decision_id = f'BC-FOUNTAIN-EG:{variant}:identity:keep'
    assert cp['current_component_id'] == 'BC-FOUNTAIN-EG'
    assert cp['current_size_finish_variant_id'] == variant and not cp['current_answer_recorded']
    assert docs['root']['current_component_review'] == component
    assert not any(x.get('decision_id') == decision_id for x in u['size_finish_variant_decisions'])
    card_path = ROOT / cp['current_review_record']
    card = read(card_path)
    assert card_path == HERE / 'component-review.json'
    assert card['proposed_name'] == 'Fountain Palm Egyptian — Bronze and Verdigris'
    parent = p['reviews']['BC-FOUNTAIN-EG']
    target = parent['size_finish_variants'][variant]
    assert parent['canonical_name'] == 'Fountain Palm Egyptian — White' and not target['identity_confirmed']
    assert len(target['specification_proposals']) == 6 and all(not x['owner_approved'] for x in target['specification_proposals'])
    protected_paths = [card_path, ROOT / 'components/evidence/component_register.json', ROOT / cp['register_workbook'],
                       HERE.parent / 'identity-approval.json', HERE.parent / 'component-review.json']
    protected = {str(path): sha(path) for path in protected_paths}
    now = datetime.now(timezone.utc).isoformat()
    decision = {'schema_version': 1, 'decision_id': decision_id, 'recorded_utc': now,
        'component_id': 'BC-FOUNTAIN-EG', 'size_finish_variant_id': variant,
        'canonical_design_name': 'Fountain Palm Egyptian', 'confirmed_name': card['proposed_name'],
        'review_number': 53, 'family_review_number': 2, 'action': 'keep name and depicted individual variant identity',
        'user_statement': 'Keep “Fountain Palm Egyptian — Bronze and Verdigris”',
        'status': 'USER CONFIRMED NAME AND SELECTED DEPICTED IDENTITY ONLY',
        'scope': 'Selected blue-toned001 reference name and identity only. Six proposals, exact coloured platform offer, physical manufacture, cast/mould identity and blue-versus-darker reference relationship remain unapproved. No whole-folder equivalence or additional sculpture is inferred.',
        'confirmed_fields': ['variant name', 'selected depicted individual variant identity'],
        'not_confirmed': [x['field'] for x in card['specification_review_items']] +
            ['Exact coloured platform offer and shared SKU', 'Blue-versus-darker reference finish/cast relationship',
             'Physical stock, manufacture and unique mould identity', 'Installation provenance and coloured series photograph'],
        'identity_confirmed': True, 'proposals_approved': False, 'specifications_approved': False,
        'approved_proposal_ids': [], 'physical_specs_verified': False, 'physical_manufacture_confirmed': False,
        'proposal_source': rel(card_path), 'proposal_source_sha256': sha(card_path),
        'primary_file_id': card['primary_image_id'], 'primary_folder_id': card['primary_folder_id'],
        'image_link': card['primary_image_link'], 'folder_link': card['primary_folder_link'],
        'remote_files_changed': False, 'live_platform_records_changed': False,
        'workbook_status': 'Unchanged; owner decision saved in review overlay for later export.'}
    write(HERE / 'before-identity-keep.json', {'recorded_utc': now,
        'files': {rel(paths[key]): value for key, value in before.items()}, 'protected_sha256': protected})
    write(output, decision)
    u['size_finish_variant_decisions'].append(decision | {'approval_record': rel(output)})
    u['identity_confirmation_counts'] = identity_counts(u)
    target.update({'identity_confirmed': True, 'canonical_name': card['proposed_name'],
        'identity_confirmed_utc': now, 'identity_approval': rel(output),
        'specification_review_status': 'SELECTED BLUE-REFERENCE NAME KEPT; SIX GUESSES AND DARKER RELATIONSHIP PENDING',
        'gaps': [x for x in target['gaps'] if x != 'Owner selected blue-reference name/identity']})
    parent['pending_size_finish_variants'][0]['review_status'] = 'NAME KEPT; SIX GUESSES PENDING; DARKER REFERENCE RELATIONSHIP NEXT'
    assert not any(x.get('size_finish_variant_id') == variant for x in cp['pending_specification_reviews'])
    cp['pending_specification_reviews'].append({'component_id': 'BC-FOUNTAIN-EG', 'size_finish_variant_id': variant,
        'canonical_name': card['proposed_name'], 'identity_approved': True, 'specifications_approved': False,
        'pending_fields': [x['field'] for x in card['specification_review_items']], 'review_record': rel(card_path),
        'identity_approval': rel(output), 'image_link': card['primary_image_link'],
        'folder_link': card['primary_folder_link'], 'scope': decision['scope']})
    p['family_review_progress']['Fountain Palm'].update({'updated_utc': now, 'review_reference_cards_answered': 2,
        'review_reference_total': 4, 'last_identity_approval': rel(output), 'specifications_complete': False})
    state = 'Fountain Palm Egyptian Bronze and Verdigris name kept; six guesses pending; darker-reference relationship next'
    cp.update({'current_answer_recorded': True, 'state': state, 'answer_state': decision['scope'],
        'last_identity_approval': rel(output), 'last_size_finish_variant_identity_approval': rel(output),
        'last_completed_size_finish_variant_id': variant, 'family_first_pass_complete': False, 'updated_utc': now})
    component['interactive_review_state'].update({'state': state,
        'explicit_size_finish_variant_names_confirmed': u['identity_confirmation_counts']['explicit_size_finish_variant_names'],
        'components_with_any_identity_scope': u['identity_confirmation_counts']['components_with_any_identity_scope'],
        'last_identity_approval': rel(output), 'last_completed_size_finish_variant_id': variant,
        'active_family': 'Fountain Palm', 'approved_proposal_groups': u['specification_approval_counts']['proposal_groups']})
    component['last_identity_approval'] = rel(output)
    component['updated_utc'] = p['updated_utc'] = u['updated_utc'] = now
    docs['root']['current_component_review'] = copy.deepcopy(component)
    docs['root']['updated_utc'] = now
    expected_counts = copy.deepcopy(before['user']['identity_confirmation_counts'])
    expected_counts['explicit_size_finish_variant_names'] += 1
    assert u['identity_confirmation_counts'] == expected_counts
    assert u['specification_approval_counts'] == before['user']['specification_approval_counts'] == specification_counts(u)
    assert u['dimension_confirmation_counts'] == before['user']['dimension_confirmation_counts']
    assert target['specification_proposals'] == before['progress']['reviews']['BC-FOUNTAIN-EG']['size_finish_variants'][variant]['specification_proposals']
    assert all(parent[key] == value for key, value in before['progress']['reviews']['BC-FOUNTAIN-EG'].items()
               if key not in ['size_finish_variants', 'pending_size_finish_variants'])
    for key, value in before['user'].items():
        if isinstance(value, list):
            assert u[key][:len(value)] == value
    assert cp['parallel_import_queue'] == before['walkthrough']['parallel_import_queue']
    assert cp['parallel_owner_reviews'] == before['walkthrough']['parallel_owner_reviews']
    assert all(sha(path) == hashes[key] for key, path in paths.items()), 'Shared writer collision'
    assert all(sha(Path(path)) == digest for path, digest in protected.items())
    for key, path in paths.items():
        write(path, docs[key])
        assert read(path) == docs[key]
    event = {'event_id': decision_id, 'event': 'SIZE_FINISH_VARIANT_NAME_AND_SELECTED_IDENTITY_KEPT',
        'recorded_utc': now, 'component_id': 'BC-FOUNTAIN-EG', 'size_finish_variant_id': variant,
        'identity_approval': rel(output), 'new_specification_approval_inferred': False,
        'darker_reference_relationship_answer_inferred': False}
    for path in [REVIEWS / 'identity_review_journal.jsonl', ROOT / 'review_journal.jsonl']:
        with path.open('a') as stream:
            stream.write(json.dumps(event, ensure_ascii=False) + '\n')
    result = {'status': 'PASS', 'kept_name': card['proposed_name'], 'six_specification_guesses_unapproved': True,
        'finish_name_count': u['identity_confirmation_counts']['explicit_size_finish_variant_names'],
        'accepted_proposal_group_count_unchanged': u['specification_approval_counts']['proposal_groups'],
        'white_parent_and_six_coloured_proposals_preserved': True, 'darker_relationship_unanswered': True,
        'baseline_model_workbook_prior_cards_unchanged': True, 'queues_reservations_preserved': True,
        'checkpoint_copies_match': read(paths['root'])['current_component_review'] == read(paths['component'])}
    write(HERE / 'identity-keep-readback.json', result)
    print(json.dumps(result))


if __name__ == '__main__':
    main()
