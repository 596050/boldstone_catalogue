"""Stage a per-image finish relationship question without creating another catalogue item."""
import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
REVIEWS = ROOT / 'components/reviews'
read = lambda p: json.loads(p.read_text())
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
rel = lambda p: str(p.relative_to(ROOT))


def write(path, value):
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    temporary.replace(path)


def main():
    card_path = HERE / 'component-review.json'
    assert not card_path.exists(), 'Already frozen'
    paths = {'walkthrough': REVIEWS / 'walkthrough_checkpoint.json', 'progress': REVIEWS / 'specification_review_progress.json',
        'component': ROOT / 'components/checkpoint.json', 'root': ROOT / 'checkpoint.json'}
    docs = {key: read(path) for key, path in paths.items()}
    before = copy.deepcopy(docs)
    hashes = {key: sha(path) for key, path in paths.items()}
    cp, progress, component = (docs[key] for key in ['walkthrough', 'progress', 'component'])
    variant = 'FOUNTAIN-EG-DARK-REFERENCE-RELATIONSHIP'
    assert cp['current_component_id'] == 'BC-FOUNTAIN-EG'
    assert cp['current_size_finish_variant_id'] == 'FOUNTAIN-EG-BRONZE-VERDIGRIS' and cp['current_answer_recorded']
    assert cp['next_review_after_keep']['variant_id'] == variant
    assert docs['root']['current_component_review'] == component
    source_path, keep_path = HERE.parent / 'component-review.json', HERE.parent / 'identity-approval.json'
    source, keep = read(source_path), read(keep_path)
    assert keep['confirmed_name'] == 'Fountain Palm Egyptian — Bronze and Verdigris' and not keep['specifications_approved']
    assert len(source['specification_review_items']) == 6 and all(not x['owner_approved'] for x in source['specification_review_items'])
    meta = read(HERE / 'reference-metadata-check.json')
    current = {x['request_id']: x for x in meta['metadata']}
    previous_meta_path = HERE.parent / 'metadata-links.json'
    previous = read(previous_meta_path)
    old = {x['request_id']: x for x in previous['metadata']}
    blue_id, dark_id, folder_id = source['primary_image_id'], source['darker_indoor_reference_id'], source['primary_folder_id']
    for file_id in [blue_id, dark_id]:
        assert all(current[file_id]['file'][key] == old[file_id]['file'][key] for key in ['id', 'name', 'path_display', 'rev', 'size'])
    assert current[folder_id]['folder']['path_display'] == old[folder_id]['folder']['path_display']
    receipts_path = HERE.parent / 'download-receipts.json'
    receipts = read(receipts_path)
    originals = []
    for file_id in [blue_id, dark_id]:
        metadata = current[file_id]['file']
        receipt = next(x for x in receipts if Path(x['local_path']).name == metadata['name'])
        path = Path(receipt['local_path'])
        data = path.read_bytes()
        assert len(data) == metadata['size'] == receipt['size'] and sha(path) == receipt['sha256']
        chunk_hash = hashlib.sha256(b''.join(hashlib.sha256(data[i:i+4194304]).digest() for i in range(0, len(data), 4194304))).hexdigest()
        assert chunk_hash == receipt['content_hash']
        originals.append({'file_id': file_id, 'local_path': str(path), 'sha256': sha(path), 'bytes': len(data),
                          'dropbox_chunk_hash': chunk_hash, 'current_rev': metadata['rev'], 'visually_inspected_this_turn': True})
    now = datetime.now(timezone.utc).isoformat()
    links = {x['file_name']: x for x in previous['previews']}
    next_review = copy.deepcopy(cp['family_review_order'][-1])
    assert next_review['component_id'] == 'BC-FOUNTAIN-MED'
    question = 'Should the darker indoor panel remain under Fountain Palm Egyptian — Bronze and Verdigris as another photograph of this finish, or be catalogued as a separate finish?'
    card = {'schema_version': 1, 'prepared_utc': now, 'component_id': 'BC-FOUNTAIN-EG', 'review_number': 53,
        'family': 'Fountain Palm', 'family_review_number': 3, 'family_review_total': 4,
        'family_total_scope': 'Four reference reviews/questions; not a physical sculpture or distinct-design count.',
        'size_finish_variant_id': variant, 'review_decision_mode': 'DEPICTED_REFERENCE_FINISH_RELATIONSHIP',
        'does_not_create_component_or_finish_record': True, 'display_name': 'Fountain Palm Egyptian — darker indoor reference comparison',
        'existing_kept_variant_id': 'FOUNTAIN-EG-BRONZE-VERDIGRIS', 'existing_kept_name': keep['confirmed_name'],
        'existing_name_approval': rel(keep_path), 'existing_name_approval_sha256': sha(keep_path),
        'primary_image_id': dark_id, 'primary_folder_id': folder_id,
        'primary_image_link': source['darker_indoor_reference_link'], 'primary_folder_link': source['primary_folder_link'],
        'comparison_image_id': blue_id, 'comparison_image_link': source['primary_image_link'],
        'blue_outdoor_reference_id': source['outdoor_display_image_id'],
        'blue_outdoor_reference_link': source['outdoor_display_image_link'],
        'dark_display_reference_id': source['darker_display_reference_id'],
        'dark_display_reference_link': source['darker_display_reference_link'],
        'question': question,
        'scope': 'Compare exact blue001 and dark002 references. Their dense fan/channel relief appears the same design, but photographs alone do not determine whether lighting, patination treatment/stage or different casts explain the darker appearance. Owner has approved only the selected blue-reference name. No same physical cast, unique mould, whole-folder mapping or new saleable finish is established.',
        'observations': ['Both references show a tall rectangular dense fan/channel relief.',
            'Blue001 is photographed against a light wall with a relatively blue-green overall surface.',
            'Dark002 is photographed on a warm indoor board and has a charcoal/metallic appearance with localized pale turquoise marks.',
            'This is an appearance comparison, not a calibrated colour measurement or manufacture history.'],
        'metadata_checked_utc': meta['checked_utc'], 'reference_refresh': rel(HERE / 'reference-metadata-check.json'),
        'reused_originals_verified': originals,
        'prior_complete_folder_audit': rel(previous_meta_path), 'prior_folder_audit_files': 83,
        'folder_census_repeated_this_turn': False,
        'six_proposal_reference': rel(source_path), 'six_proposal_reference_sha256': sha(source_path),
        'specification_review_items': copy.deepcopy(source['specification_review_items']),
        'specification_scope': 'Carry the six unapproved blue-reference proposals for context only. Applicability to dark002 is pending; no new specification proposal IDs or approvals are created.',
        'platform_mapping': copy.deepcopy(source['platform_mapping']),
        'photo_coverage': {'dark_indoor_display_available': True, 'dark_rear_image_established': False,
            'dark_colour_series_established': False, 'actual_client_installation_provenance_confirmed': False,
            'same_finish_or_physical_cast_as_blue_reference_confirmed': False},
        'relationship_answer_recorded': False, 'specifications_approved': False, 'physical_specs_verified': False,
        'next_review_after_answer': next_review, 'remote_files_changed': False, 'live_platform_records_changed': False}
    write(card_path, card)
    protected_paths = [REVIEWS / 'user_classifications.json', source_path, keep_path,
        HERE.parent.parent / 'identity-approval.json', HERE.parent.parent / 'component-review.json',
        ROOT / 'components/evidence/component_register.json', ROOT / cp['register_workbook'], card_path]
    protected = {str(path): sha(path) for path in protected_paths}
    write(HERE / 'before-stage-review.json', {'recorded_utc': now,
        'files': {rel(paths[key]): value for key, value in before.items()}, 'protected_sha256': protected})
    parent = progress['reviews']['BC-FOUNTAIN-EG']
    assert parent['canonical_name'] == 'Fountain Palm Egyptian — White'
    assert parent['size_finish_variants']['FOUNTAIN-EG-BRONZE-VERDIGRIS']['identity_confirmed']
    parent.setdefault('reference_relationship_reviews', {})[variant] = {
        'review_record': rel(card_path), 'relationship_answer_recorded': False,
        'reference_file_ids': [blue_id, dark_id], 'folder_id': folder_id,
        'does_not_create_component_or_finish_record': True, 'question': question}
    progress['updated_utc'] = now
    state = 'Awaiting blue-versus-darker Fountain Palm Egyptian finish relationship; no additional sculpture created'
    cp.update({'current_size_finish_variant_id': variant, 'proposed_name': card['display_name'],
        'state': state, 'current_review_record': rel(card_path), 'current_family_review_number': 3,
        'current_family_review_total': 4, 'current_answer_recorded': False,
        'current_identity_relationship_answer_recorded': False, 'current_identity_relationship_approval': None,
        'current_specification_answer_recorded': False, 'current_dimension_answer_recorded': False,
        'current_partial_specification_answer_recorded': False, 'current_dimension_approval': None,
        'current_owner_face_dimensions_cm': None, 'working_version_user_approved': False,
        'review_decision_mode': card['review_decision_mode'], 'question_scope': card['scope'],
        'answer_state': 'Selected blue-reference name kept. Darker reference relationship unanswered; all six proposals remain unapproved.',
        'primary_image': {'file_id': dark_id, 'name': current[dark_id]['file']['name'],
            'path_display': current[dark_id]['file']['path_display'], 'copy_link_url': card['primary_image_link'],
            'open_in_dropbox_url': links[dark_id]['open_in_dropbox_url']},
        'containing_folder': {'folder_id': folder_id, 'name': current[folder_id]['folder']['name'],
            'path_display': current[folder_id]['folder']['path_display'], 'copy_link_url': card['primary_folder_link'],
            'open_in_dropbox_url': links[folder_id]['open_in_dropbox_url']},
        'family_review_evidence': card['reference_refresh'], 'metadata_checked_utc': meta['checked_utc'],
        'next_review_after_keep': next_review, 'displayed_identity_evidence_file_ids': [dark_id, blue_id],
        'displayed_identity_evidence_folder_ids': [folder_id],
        'current_component_source_notes': [question] + [x['display'] for x in card['specification_review_items']], 'updated_utc': now})
    component['interactive_review_state'].update({'current_size_finish_variant_id': variant,
        'current_name': card['display_name'], 'state': state, 'active_family': 'Fountain Palm',
        'family_review_number': 3, 'family_review_total': 4,
        'current_identity_relationship_answer_recorded': False, 'specification_proposals_approved': False,
        'working_version_user_approved': False, 'review_decision_mode': card['review_decision_mode']})
    component['current_component_review_record'] = rel(card_path)
    component['updated_utc'] = now
    docs['root']['current_component_review'] = copy.deepcopy(component)
    docs['root']['updated_utc'] = now
    assert all(parent[key] == value for key, value in before['progress']['reviews']['BC-FOUNTAIN-EG'].items())
    assert all(progress['reviews'][key] == value for key, value in before['progress']['reviews'].items() if key != 'BC-FOUNTAIN-EG')
    assert cp['pending_specification_reviews'] == before['walkthrough']['pending_specification_reviews']
    assert cp['parallel_import_queue'] == before['walkthrough']['parallel_import_queue']
    assert cp['parallel_owner_reviews'] == before['walkthrough']['parallel_owner_reviews']
    assert all(sha(path) == hashes[key] for key, path in paths.items()), 'Shared writer collision'
    assert all(sha(Path(path)) == digest for path, digest in protected.items())
    for key, path in paths.items():
        write(path, docs[key])
        assert read(path) == docs[key]
    result = {'status': 'PASS', 'current_relationship_review': variant, 'family_reference': '3 of 4',
        'same_current_file_ids_revisions_sizes': True, 'two_originals_rehashed_and_viewed': True,
        'new_component_or_finish_records': 0, 'new_specification_proposal_ids_or_approvals': 0,
        'white_and_blue_approved_names_preserved': True, 'ledger_model_workbook_prior_reviews_unchanged': True,
        'checkpoint_copies_match': read(paths['root'])['current_component_review'] == read(paths['component'])}
    write(HERE / 'review-validation.json', result)
    print(json.dumps(result))


if __name__ == '__main__':
    main()
