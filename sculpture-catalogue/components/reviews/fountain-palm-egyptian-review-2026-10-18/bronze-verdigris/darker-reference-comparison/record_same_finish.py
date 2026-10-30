"""Record owner's same-finish classification for two exact references, not cast equivalence."""
import copy
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
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
    output = HERE / 'owner-same-finish-decision.json'
    assert not output.exists(), 'Already recorded'
    paths = {'user': REVIEWS / 'user_classifications.json', 'progress': REVIEWS / 'specification_review_progress.json',
        'walkthrough': REVIEWS / 'walkthrough_checkpoint.json', 'component': ROOT / 'components/checkpoint.json',
        'root': ROOT / 'checkpoint.json'}
    docs = {key: read(path) for key, path in paths.items()}
    before = copy.deepcopy(docs)
    hashes = {key: sha(path) for key, path in paths.items()}
    user, progress, cp, component = (docs[key] for key in ['user', 'progress', 'walkthrough', 'component'])
    relationship_id = 'FOUNTAIN-EG-DARK-REFERENCE-RELATIONSHIP'
    finish_id = 'FOUNTAIN-EG-BRONZE-VERDIGRIS'
    assert cp['current_component_id'] == 'BC-FOUNTAIN-EG' and cp['current_size_finish_variant_id'] == relationship_id
    assert not cp['current_answer_recorded'] and docs['root']['current_component_review'] == component
    card_path = ROOT / cp['current_review_record']
    assert card_path == HERE / 'component-review.json'
    card = read(card_path)
    keep_path = ROOT / card['existing_name_approval']
    protected = {str(path): sha(path) for path in [card_path, keep_path,
        HERE.parent / 'component-review.json', HERE.parent.parent / 'identity-approval.json',
        ROOT / 'components/evidence/component_register.json', ROOT / cp['register_workbook']]}
    parent = progress['reviews']['BC-FOUNTAIN-EG']
    variant = parent['size_finish_variants'][finish_id]
    assert variant['canonical_name'] == 'Fountain Palm Egyptian — Bronze and Verdigris' and variant['identity_confirmed']
    assert not parent['reference_relationship_reviews'][relationship_id]['relationship_answer_recorded']
    now = datetime.now(timezone.utc).isoformat()
    decision = {'schema_version': 1,
        'decision_id': 'BC-FOUNTAIN-EG:001-002:SAME-DEPICTED-FINISH:2026-10-18', 'recorded_utc': now,
        'user_statement': 'Yes, the darker indoor photograph belong to this same Bronze and Verdigris finish',
        'preceding_question': card['question'], 'status': 'OWNER CONFIRMED SAME DEPICTED FINISH',
        'relationship': 'SAME_DEPICTED_FINISH', 'component_id': 'BC-FOUNTAIN-EG',
        'canonical_component_id': 'BC-FOUNTAIN-EG', 'canonical_size_finish_variant_id': finish_id,
        'retained_name': card['existing_kept_name'], 'review_record': rel(card_path),
        'review_record_sha256': sha(card_path), 'prior_identity_approval': rel(keep_path),
        'prior_identity_approval_sha256': sha(keep_path),
        'reference_images': [
            {'file_id': card['comparison_image_id'], 'folder_id': card['primary_folder_id'],
             'image_link': card['comparison_image_link'], 'folder_link': card['primary_folder_link']},
            {'file_id': card['primary_image_id'], 'folder_id': card['primary_folder_id'],
             'image_link': card['primary_image_link'], 'folder_link': card['primary_folder_link']}],
        'metadata_check': card['reference_refresh'], 'metadata_checked_utc': card['metadata_checked_utc'],
        'scope': 'The two exact blue001 and darker indoor002 references belong to the same Bronze and Verdigris finish classification. Keep one finish identity for these references. No new finish or component is created.',
        'counting_scope': 'Two reviewed photographs grouped under one existing finish; no physical stock count inferred.',
        'applies_to_entire_folder': False, 'other_dark_folder_images_automatically_confirmed': False,
        'new_name_approval': False, 'same_physical_cast_confirmed': False, 'same_mould_confirmed': False,
        'lighting_as_explanation_confirmed': False, 'finish_recipe_confirmed': False,
        'specifications_approved': False, 'approved_proposal_ids': [], 'physical_specs_verified': False,
        'workbook_contains_this_decision': False, 'remote_files_changed': False, 'live_platform_records_changed': False}
    assert not any(x.get('decision_id') == decision['decision_id'] for x in user['component_identity_relationship_decisions'])
    write(HERE / 'before-same-finish-decision.json', {'recorded_utc': now,
        'files': {rel(paths[key]): value for key, value in before.items()}, 'protected_sha256': protected})
    write(output, decision)
    user['component_identity_relationship_decisions'].append(decision | {'approval_record': rel(output)})
    relationship = parent['reference_relationship_reviews'][relationship_id]
    relationship.update({'relationship_answer_recorded': True, 'relationship': decision['relationship'],
        'approval_record': rel(output), 'recorded_utc': now})
    variant['reference_relationship_approval'] = rel(output)
    variant.pop('unresolved_reference_relationship')
    variant['photo_coverage'].update({'darker_indoor_reference_same_finish_or_cast_confirmed': True,
        'darker_indoor_reference_same_finish_confirmed': True,
        'darker_indoor_reference_same_physical_cast_confirmed': False,
        'owner_finish_classification_applies_to_file_ids': [card['comparison_image_id'], card['primary_image_id']],
        'owner_finish_classification_record': rel(output)})
    variant['gaps'] = ['Exact physical cast/mould equivalence and installation provenance' if x ==
        'Blue-versus-dark reference relationship, exact physical cast/mould equivalence and installation provenance' else x
        for x in variant['gaps']]
    variant['specification_review_status'] = 'NAME KEPT; BLUE001 AND DARK002 SAME FINISH CONFIRMED; SIX GUESSES PENDING'
    parent['pending_size_finish_variants'][0]['review_status'] = 'NAME AND TWO-REFERENCE FINISH GROUPING KEPT; SIX GUESSES PENDING'
    group_id = 'FOUNTAIN-EG-BRONZE-VERDIGRIS-REVIEWED-REFERENCES'
    progress.setdefault('depicted_reference_finish_groups', {})[group_id] = {
        'component_id': 'BC-FOUNTAIN-EG', 'size_finish_variant_id': finish_id,
        'canonical_name': card['existing_kept_name'], 'reference_images': decision['reference_images'],
        'owner_relationship_approval': rel(output), 'reviewed_reference_count': 2,
        'reviewed_finish_classifications': 1, 'same_physical_cast_confirmed': False,
        'applies_to_entire_folder': False, 'new_catalogue_record_created': False}
    progress['family_review_progress']['Fountain Palm'].update({'updated_utc': now,
        'review_reference_cards_answered': 3, 'last_relationship_approval': rel(output), 'specifications_complete': False})
    state = 'Blue001 and darker indoor002 grouped under Fountain Palm Egyptian Bronze and Verdigris; Mediterranean White next'
    cp.update({'current_answer_recorded': True, 'current_identity_relationship_answer_recorded': True,
        'current_identity_relationship_approval': rel(output), 'last_identity_relationship_approval': rel(output),
        'canonical_depicted_name': card['existing_kept_name'], 'current_separate_saleable_design': False,
        'state': state, 'answer_state': decision['scope'], 'updated_utc': now})
    component['interactive_review_state'].update({'state': state,
        'current_identity_relationship_answer_recorded': True, 'canonical_depicted_name': card['existing_kept_name'],
        'current_separate_saleable_design': False})
    component['last_identity_relationship_decision'] = rel(output)
    user['updated_utc'] = progress['updated_utc'] = component['updated_utc'] = now
    docs['root']['current_component_review'] = copy.deepcopy(component)
    docs['root']['updated_utc'] = now
    assert identity_counts(user) == before['user']['identity_confirmation_counts'] == user['identity_confirmation_counts']
    assert specification_counts(user) == before['user']['specification_approval_counts'] == user['specification_approval_counts']
    assert user['dimension_confirmation_counts'] == before['user']['dimension_confirmation_counts']
    assert variant['specification_proposals'] == before['progress']['reviews']['BC-FOUNTAIN-EG']['size_finish_variants'][finish_id]['specification_proposals']
    assert not variant['specifications_approved'] and not variant['physical_specs_verified']
    assert all(parent[key] == value for key, value in before['progress']['reviews']['BC-FOUNTAIN-EG'].items()
        if key not in ['reference_relationship_reviews', 'size_finish_variants', 'pending_size_finish_variants'])
    for key, value in before['user'].items():
        if isinstance(value, list):
            assert user[key][:len(value)] == value
    for key in ['parallel_import_queue', 'parallel_owner_reviews', 'pending_specification_reviews', 'parallel_evidence_flags']:
        assert cp[key] == before['walkthrough'][key]
    assert all(sha(path) == hashes[key] for key, path in paths.items()), 'Shared writer collision'
    assert all(sha(Path(path)) == digest for path, digest in protected.items())
    for key, path in paths.items():
        write(path, docs[key])
        assert read(path) == docs[key]
    event = {'event_id': decision['decision_id'], 'event': 'OWNER_SAME_DEPICTED_FINISH_CONFIRMED',
        'recorded_utc': now, 'component_id': 'BC-FOUNTAIN-EG', 'approval_record': rel(output),
        'new_name_or_specification_approval': False, 'new_component_or_finish_record': False}
    for path in [REVIEWS / 'identity_review_journal.jsonl', ROOT / 'review_journal.jsonl']:
        with path.open('a') as stream:
            stream.write(json.dumps(event, ensure_ascii=False) + '\n')
    result = {'status': 'PASS', 'two_references_one_existing_finish': True,
        'six_guesses_and_name_dimension_counts_unchanged': True, 'physical_cast_equivalence_not_inferred': True,
        'no_whole_folder_assignment': True, 'baseline_model_workbook_prior_cards_unchanged': True,
        'checkpoint_copies_match': read(paths['root'])['current_component_review'] == read(paths['component'])}
    write(HERE / 'same-finish-readback.json', result)
    print(json.dumps(result))


if __name__ == '__main__':
    main()
