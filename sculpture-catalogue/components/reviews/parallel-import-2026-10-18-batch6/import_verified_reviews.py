"""Import nine identities and three scoped owner corrections without completing any six-field record."""
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
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    temp.replace(path)


def main():
    manifest = read(HERE / 'source-manifest.json')
    reference_check = read(HERE / 'current-reference-check.json')
    assert reference_check['status'] == 'PASS'
    live = {x['request_id']: x for x in reference_check['metadata']}
    for value in manifest['source_files'].values():
        assert sha(ROOT / value['snapshot']) == value['sha256']
    receipt_path = HERE / 'import-receipt.json'
    paths = {'user': REVIEWS / 'user_classifications.json', 'progress': REVIEWS / 'specification_review_progress.json',
        'walkthrough': REVIEWS / 'walkthrough_checkpoint.json', 'component': ROOT / 'components/checkpoint.json', 'root': ROOT / 'checkpoint.json'}
    docs = {key: read(path) for key, path in paths.items()}
    user, progress, cp, component = (docs[key] for key in ['user', 'progress', 'walkthrough', 'component'])
    if receipt_path.exists():
        receipt = read(receipt_path)
        assert receipt['source_package_sha256'] == manifest['source_package_sha256']
        ids = {x.get('decision_id') for values in user.values() if isinstance(values, list) for x in values if isinstance(x, dict)}
        assert all(x['decision_id'] in ids for x in receipt['outputs'])
        print(json.dumps({'status': 'ALREADY_IMPORTED_IDEMPOTENT_READBACK_PASS', 'decision_records': len(receipt['outputs'])}))
        return
    before = copy.deepcopy(docs)
    hashes = {key: sha(path) for key, path in paths.items()}
    assert docs['root']['current_component_review'] == component
    assert cp['current_component_id'] == 'BC-LEAF-CURVE' and not cp['current_answer_recorded']
    existing_source_ids = {x.get('source_decision_id') for values in user.values() if isinstance(values, list) for x in values if isinstance(x, dict)}
    assert not any(x['source_decision_id'] in existing_source_ids for x in manifest['items'] + manifest['corrections'])
    protected = {str(path): sha(path) for path in [ROOT / 'components/evidence/component_register.json',
        ROOT / cp['register_workbook'], ROOT / cp['current_review_record'], ROOT / cp['last_identity_approval']]}
    now = datetime.now(timezone.utc).isoformat()
    write(HERE / 'before-import.json', {'recorded_utc': now,
        'files': {rel(paths[key]): value for key, value in before.items()}, 'protected_sha256': protected})
    outputs, targets = [], {}

    def save(filename, decision, list_name):
        path = HERE / 'decisions' / filename
        assert not any(x.get('decision_id') == decision['decision_id'] for x in user.get(list_name, []))
        write(path, decision)
        user.setdefault(list_name, []).append(decision | {'approval_record': rel(path)})
        outputs.append({'decision_id': decision['decision_id'], 'kind': list_name,
            'source_decision_id': decision['source_decision_id'], 'approval_record': rel(path)})
        return rel(path)

    def provenance(source, path, digest):
        return {'schema_version': 1, 'source_owner_session': manifest['owner_session'],
            'source_decision_id': source.get('decision_id', source.get('correction_id', source.get('confirmation_id'))),
            'recorded_utc': source['recorded_utc'], 'imported_utc': now,
            'user_statement': source['source_user_statement']['text'],
            'authoritative_user_evidence': copy.deepcopy(source['source_user_statement']),
            'source_receipt_snapshot': path, 'source_receipt_sha256': digest,
            'specifications_approved': False, 'physical_specs_verified': False,
            'workbook_status': 'Unchanged; verified local review overlay import only',
            'remote_files_changed': False, 'live_platform_records_changed': False}

    for item in manifest['items']:
        source, card = read(ROOT / item['receipt']), read(ROOT / item['current_review'])
        cid, vid = item['component_id'], item['variant_id']
        parent = progress['reviews'].setdefault(cid, {'identity_confirmed': False, 'specifications_approved': False,
            'physical_specs_verified': False, 'scope': 'Names approved per depicted finish/position, with unresolved physical specifications.'})
        variants = parent.setdefault('size_finish_variants', {})
        assert vid not in variants
        primary, folder = item['primary'], item['folder']
        assert live[primary['file_id']]['file']['rev'] == primary['rev']
        complete = bool(primary.get('shows_complete_single_component'))
        proposals = copy.deepcopy(card['specification_review_items'])
        for spec in proposals:
            spec.update({'field': spec['group'], 'display': spec['proposal'], 'owner_approved': False,
                'physical_specs_verified': False})
        decision = provenance(source, item['receipt'], item['receipt_sha256']) | {
            'decision_id': f'{cid}:{vid}:identity:keep', 'component_id': cid, 'size_finish_variant_id': vid,
            'canonical_name': item['name'], 'confirmed_name': item['name'], 'identity_confirmed': True,
            'status': 'OWNER CONFIRMED DEPICTED NAME AND FINISH/POSITION IDENTITY ONLY',
            'scope': source.get('identity_scope', source.get('scope_note', 'Name and depicted identity only; preserve all existing uncertainties.')),
            'proposals_approved': False, 'approved_proposal_ids': [], 'new_specification_facts_from_named_keep': False,
            'proposal_source': item['before_keep_review'], 'proposal_source_sha256': item['before_keep_review_sha256'],
            'latest_review_source': item['current_review'], 'latest_review_source_sha256': item['current_review_sha256'],
            'primary_file_id': primary['file_id'] if complete else None, 'reference_file_id': primary['file_id'],
            'primary_folder_id': folder['file_id'], 'image_link': primary['url'], 'folder_link': folder['url'],
            'current_dropbox_reference': copy.deepcopy(live[primary['file_id']]['file']),
            'same_physical_cast_or_mould_confirmed': False}
        approval = save(f'{cid}/{vid}/identity-approval.json', decision, 'size_finish_variant_decisions')
        target = {'size_finish_variant_id': vid, 'canonical_name': item['name'], 'identity_confirmed': True,
            'identity_approval': approval, 'review_record': item['current_review'],
            'complete_source_review_snapshot': item['current_review'], 'specification_proposals': proposals,
            'specifications_approved': False, 'physical_specs_verified': False, 'proposals_approved': False,
            'primary_image_id': primary['file_id'] if complete else None, 'reference_image_id': primary['file_id'],
            'primary_folder_id': folder['file_id'], 'primary_image_details': copy.deepcopy(primary),
            'current_dropbox_reference': copy.deepcopy(live[primary['file_id']]['file']),
            'image_link': primary['url'], 'folder_link': folder['url'], 'individual_photo_missing': not complete,
            'platform_mapping': copy.deepcopy(card.get('platform_evidence', {})),
            'photo_coverage': copy.deepcopy(card.get('photo_selection_review', {})),
            'context_images': copy.deepcopy(card.get('context_images', [])), 'series_images': copy.deepcopy(card.get('series_images', [])),
            'source_conflicts': copy.deepcopy(card.get('source_conflicts', [])),
            'missing_photographs': copy.deepcopy(card.get('missing_photographs', [])),
            'missing_specifications': copy.deepcopy(card.get('missing_specifications', [])),
            'production_status': copy.deepcopy(card.get('production_status')),
            'owner_confirmed_fields': copy.deepcopy(card.get('owner_confirmed_fields', [])),
            'dimension_relationship': copy.deepcopy(card.get('dimension_relationship')),
            'partially_confirmed_specification_groups': copy.deepcopy(item['partial_groups']),
            'fully_confirmed_specification_groups': [], 'maker_code_crosswalk': copy.deepcopy(card.get('maker_code_crosswalk')),
            'photo_assignment_discrepancy': copy.deepcopy(card.get('photo_assignment_discrepancy')),
            'workbook_contains_import': False, 'physical_manufacture_independently_verified': False}
        variants[vid] = targets[item['review_id']] = target
        cp['pending_specification_reviews'].append({'component_id': cid, 'size_finish_variant_id': vid,
            'canonical_name': item['name'], 'identity_approved': True, 'specifications_approved': False,
            'pending_fields': [x['group'] for x in proposals], 'partially_confirmed_specification_groups': item['partial_groups'],
            'review_record': item['current_review'], 'identity_approval': approval,
            'image_link': primary['url'], 'folder_link': folder['url'], 'individual_photo_missing': not complete})
    for correction in manifest['corrections']:
        source = read(ROOT / correction['receipt'])
        base = provenance(source, correction['receipt'], correction['sha256'])
        if 'Gold leaf' in str(source.get('confirmed_fields', [])):
            cid, vid = 'BC-PANEL-CURVES', 'PANEL-CURVES-MULTICOLOUR-PATINA'
            target = targets['PANEL-CURVES-MULTICOLOUR-PATINA-01']
            common = base | {'component_id': cid, 'size_finish_variant_id': vid, 'canonical_name': target['canonical_name'],
                'reference_file_id': target['reference_image_id'], 'primary_folder_id': target['primary_folder_id'],
                'image_link': target['image_link'], 'folder_link': target['folder_link'], 'scope': source['scope_note']}
            dimension = common | {'decision_id': f'{cid}:{vid}:face:owner-stated:25x25',
                'scope_kind': 'INDIVIDUAL_FACE_SIZE', 'status': 'OWNER CONFIRMED FACE SIZE ONLY; DEPTH PENDING',
                'confirmed_dimensions_cm': {'height': 25, 'width': 25, 'depth': None},
                'unit_interpretation': 'Centimetres carried from the preceding owner card; not independently measured.'}
            dimension_path = save(f'{cid}/{vid}/face-dimension-approval.json', dimension, 'dimension_decisions')
            finish = common | {'decision_id': f'{cid}:{vid}:surface-finish-texture:owner-stated',
                'confirmed_surface_finish': 'Gold leaf', 'confirmed_surface_texture': 'Rough textured surface',
                'actual_substrate': None, 'leaf_composition_purity': None, 'sealer': None,
                'complete_material_group_approved': False}
            finish_path = save(f'{cid}/{vid}/surface-detail-approval.json', finish, 'material_detail_decisions')
            target.update({'owner_face_dimensions_cm': dimension['confirmed_dimensions_cm'], 'dimension_approval': dimension_path,
                'owner_surface_finish': 'Gold leaf', 'owner_surface_texture': 'Rough textured surface', 'material_detail_approval': finish_path})
            for spec in target['specification_proposals']:
                if spec['group'] == 'dimensions_and_depth':
                    spec['owner_confirmed_subfields'] = ['height', 'width']
                if spec['group'] == 'material_and_finish':
                    spec['owner_confirmed_subfields'] = ['surface_finish', 'surface_texture']
        elif source.get('production_role') == 'FINISHED_SCULPTURE':
            cid, vid = 'BC-PANEL-CURVES', 'PANEL-CURVES-BEIGE-PROCESS'
            target = targets['PANEL-CURVES-BEIGE-PROCESS-01']
            decision = base | {'decision_id': f'{cid}:{vid}:production-role:finished-sculpture:owner-stated',
                'component_id': cid, 'size_finish_variant_id': vid, 'production_role': 'FINISHED_SCULPTURE',
                'scope': source['scope_note'], 'reference_file_id': target['reference_image_id'],
                'primary_folder_id': target['primary_folder_id'], 'image_link': target['image_link'], 'folder_link': target['folder_link']}
            approval = save(f'{cid}/{vid}/production-role-approval.json', decision, 'production_role_decisions')
            target.update({'owner_production_role': 'FINISHED_SCULPTURE', 'production_role_approval': approval})
        else:
            assert source['confirmation_id'] == 'RAKED-SHARED-DIMENSIONS-001'
            decision = base | {'decision_id': source['confirmation_id'], 'reference_review_id': source['reference_review_id'],
                'reference_component_id': source['reference_component_id'], 'reference_variant_id': source['reference_configuration_key'],
                'targets': copy.deepcopy(source['targets']), 'working_reference_values': copy.deepcopy(source['working_reference_values']),
                'relationship': 'SAME_DIMENSIONS_AS_REFERENCE', 'relationship_owner_confirmed': True,
                'numeric_dimensions_owner_confirmed': False, 'physical_measurement_verified': False,
                'other_specifications_transferred': False, 'scope': source['interpretation'],
                'applies_to_Beige1_or_Beige3': False}
            approval = save('RAKED/shared-dimension-relationship-approval.json', decision, 'dimension_relationship_decisions')
            for key in [source['reference_review_id']] + [x['review_id'] for x in source['targets']]:
                target = targets[key]
                target['dimension_relationship_approval'] = approval
                target['numeric_dimensions_owner_confirmed'] = False
    flag_path = HERE / 'g286-003-independent-binding-review.json'
    flag_source_path = next(ROOT / x['snapshot'] for path, x in manifest['source_files'].items() if path.endswith('/photo-assignment-discrepancy.json'))
    flag_source = read(flag_source_path)
    file_id = flag_source['fresh_original_rechecked']['id']
    binding = {'status': 'INDEPENDENTLY VISUALLY VERIFIED FOR EXACT FILE003 ONLY', 'checked_utc': now,
        'file_id': file_id, 'folder_id': flag_source['folder_id'], 'current_metadata': live[file_id]['file'],
        'source_flag_snapshot': rel(flag_source_path), 'source_flag_sha256': sha(flag_source_path),
        'component_bindings': [{'component_id': 'BC-RW-WAVE', 'variant_id': 'RAKED-SPIRAL2-WHITE', 'position': 'Left'},
            {'component_id': 'BC-RW-SPIRAL3', 'variant_id': 'RAKED-SPIRAL3-WHITE', 'position': 'Right'}],
        'comparison_reference_ids': ['id:cnqzTNngPVsAAAAAAAylKw', 'id:cnqzTNngPVsAAAAAAAylLA', 'id:cnqzTNngPVsAAAAAAAylLQ'],
        'finding': 'Exact brick-wall003 shows the wave on left and the Spiral3 relief on right. Right spiral geometry matches Spiral3 solo and differs from the separately kept Spiral1 solo.',
        'scope': 'Per-file depicted-design binding only, not same cast/mould confirmation. No entire-folder remapping, owner approval, physical specification or client-installation provenance inferred.',
        'G286_001_002_status': 'Details remain unclassified', 'G286_004_014_status': 'Reported repeated pairing remains pending independent per-file review',
        'baseline_register_changed': False, 'remote_files_changed': False}
    write(flag_path, binding)
    progress.setdefault('asset_assignment_overrides', {})[file_id] = {'review_record': rel(flag_path),
        'component_bindings': binding['component_bindings'], 'scope': binding['scope'], 'recorded_utc': now}
    for flag in cp['parallel_evidence_flags']:
        if flag['flag_id'] == 'RAKED:G286:PAIR003-014:REPORTED-DESIGN-MISASSIGNMENT':
            flag.update({'status': 'PARTIALLY RECONCILED: EXACT003 VERIFIED; OTHER FILES PENDING',
                'independent_review': rel(flag_path), 'verified_file_ids': [file_id],
                'remaining_scope': 'G286001–002 details and004–014 per-file assignments pending; no whole-folder change.'})
    old_identity = copy.deepcopy(user['identity_confirmation_counts'])
    user['identity_confirmation_counts'] = identity_counts(user)
    user['specification_approval_counts'] = specification_counts(user)
    user['dimension_confirmation_counts'] = {'components': len({x['component_id'] for x in user['dimension_decisions']}),
        'face_size_decisions': sum(x.get('scope_kind') != 'COMPLETE_DIMENSION_INSTRUCTION' for x in user['dimension_decisions']),
        'complete_dimension_instruction_decisions': sum(x.get('scope_kind') == 'COMPLETE_DIMENSION_INSTRUCTION' for x in user['dimension_decisions']),
        'individual_dimension_decisions': len(user['dimension_decisions'])}
    expected_identity = old_identity | {'explicit_size_finish_variant_names': old_identity['explicit_size_finish_variant_names'] + 9,
        'components_with_any_identity_scope': old_identity['components_with_any_identity_scope'] + 5}
    assert user['identity_confirmation_counts'] == expected_identity
    assert user['specification_approval_counts'] == before['user']['specification_approval_counts']
    assert user['dimension_confirmation_counts']['individual_dimension_decisions'] == before['user']['dimension_confirmation_counts']['individual_dimension_decisions'] + 1
    assert len(outputs) == 13 and sum(len(x['specification_proposals']) for x in targets.values()) == 54
    assert all(not x['owner_approved'] for target in targets.values() for x in target['specification_proposals'])
    assert sum(len(x['partially_confirmed_specification_groups']) for x in targets.values()) == 6
    summary = {'recorded_utc': now, 'receipt': rel(receipt_path), 'source_package_sha256': manifest['source_package_sha256'],
        'name_receipts': 9, 'gold_face_decisions': 1, 'gold_surface_detail_decisions': 1,
        'finished_sculpture_role_decisions': 1, 'dimension_equality_relationships': 1,
        'relationship_targets': 3, 'full_specification_group_approvals': 0,
        'partly_confirmed_groups_retained': 6, 'all_groups_still_incomplete': 54,
        'current_Leaf_Curve_question_preserved': True, 'workbook_export_pending': True}
    cp['parallel_import_queue'].append({'package_id': 'PANEL-PLANT-RAKED:2026-10-18',
        'receipt': manifest['source_package'], 'source_package_sha256': manifest['source_package_sha256'],
        'status': 'SEALED PACKAGE IMPORTED WITH EXACT OWNER SCOPE', 'approval_imported': True,
        'import_receipt': rel(receipt_path), 'imported_utc': now})
    for lane in cp['parallel_owner_reviews']:
        if lane['component_id'] in [x['component_id'] for x in manifest['items']]:
            lane.update({'status': 'SEALED FIRST-PASS NAMES AND SCOPED CORRECTIONS IMPORTED; SPECIFICATION GAPS RETAINED',
                'import_receipt': rel(receipt_path)})
    cp['last_parallel_import'] = summary
    cp['completed_serialized_parallel_import'] = {'status': 'APPLIED_AND_VERIFIED', 'receipt': rel(receipt_path),
        'completed_utc': now, 'scope': 'Sealed reserved98–102 only; Leaf Curve review preserved'}
    cp['updated_utc'] = user['updated_utc'] = progress['updated_utc'] = now
    progress['latest_parallel_import'] = rel(receipt_path)
    component.update({'parallel_import_queue': copy.deepcopy(cp['parallel_import_queue']),
        'parallel_owner_reviews': copy.deepcopy(cp['parallel_owner_reviews']),
        'parallel_evidence_flags': copy.deepcopy(cp['parallel_evidence_flags']), 'last_parallel_import': summary, 'updated_utc': now})
    counts = user['identity_confirmation_counts']
    component['interactive_review_state'].update({'explicit_identity_confirmations': counts['component_designs'],
        'explicit_size_finish_variant_names_confirmed': counts['explicit_size_finish_variant_names'],
        'components_with_any_identity_scope': counts['components_with_any_identity_scope']})
    docs['root']['current_component_review'] = copy.deepcopy(component)
    docs['root']['updated_utc'] = now
    assert all(cp[key] == value for key, value in before['walkthrough'].items() if key.startswith('current_'))
    assert cp['next_review_after_keep'] == before['walkthrough']['next_review_after_keep']
    assert all(progress['reviews'][key] == value for key, value in before['progress']['reviews'].items())
    for key, value in before['user'].items():
        if isinstance(value, list):
            assert user[key][:len(value)] == value
    assert all(sha(path) == hashes[key] for key, path in paths.items()), 'Shared writer collision'
    assert all(sha(Path(path)) == digest for path, digest in protected.items())
    for key, path in paths.items():
        write(path, docs[key])
        assert read(path) == docs[key]
    receipt = {'status': 'APPLIED_AND_VERIFIED', 'imported_utc': now,
        'source_package_sha256': manifest['source_package_sha256'], 'manifest': rel(HERE / 'source-manifest.json'),
        'summary': summary, 'outputs': outputs, 'counts_after': {'identity': user['identity_confirmation_counts'],
            'specification': user['specification_approval_counts'], 'dimensions': user['dimension_confirmation_counts']},
        'protected_sha256': protected, 'checkpoint_copies_match': read(paths['root'])['current_component_review'] == read(paths['component'])}
    write(receipt_path, receipt)
    event = {'event': 'VERIFIED_PARALLEL_PACKAGE_IMPORTED', 'recorded_utc': now,
        'receipt': rel(receipt_path), 'source_package_sha256': manifest['source_package_sha256'], 'decision_count': len(outputs)}
    for path in [REVIEWS / 'identity_review_journal.jsonl', ROOT / 'review_journal.jsonl']:
        with path.open('a') as stream:
            stream.write(json.dumps(event, ensure_ascii=False) + '\n')
    print(json.dumps({'status': receipt['status'], 'decision_records': len(outputs),
        'finish_names': counts['explicit_size_finish_variant_names'], 'components_with_identity_scope': counts['components_with_any_identity_scope'],
        'accepted_specification_groups_unchanged': user['specification_approval_counts']['proposal_groups'], 'Leaf_Curve_question_preserved': True}))


if __name__ == '__main__':
    main()
