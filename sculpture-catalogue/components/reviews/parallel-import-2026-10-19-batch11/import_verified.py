"""Import current Moonphases aliases while retaining all historical source Keeps."""
import copy
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
REVIEWS = ROOT / 'components/reviews'
sys.path.insert(0, str(ROOT / 'components/scripts'))
from review_decision_counts import identity_counts, specification_counts


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rel(path):
    return str(path.relative_to(ROOT))


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    tmp.replace(path)


def main():
    manifest = read(HERE / 'source-manifest.json')
    package = read(ROOT / manifest['package_snapshot'])
    paths = {'user': REVIEWS / 'user_classifications.json',
             'progress': REVIEWS / 'specification_review_progress.json',
             'walkthrough': REVIEWS / 'walkthrough_checkpoint.json',
             'component': ROOT / 'components/checkpoint.json', 'root': ROOT / 'checkpoint.json'}
    docs = {key: read(path) for key, path in paths.items()}
    receipt_path = HERE / 'import-receipt.json'
    if receipt_path.exists():
        receipt = read(receipt_path)
        for ledger, ids in receipt['new_ledger_decision_ids'].items():
            actual = [x['decision_id'] for x in docs['user'][ledger]]
            assert all(actual.count(key) == 1 for key in ids)
        assert docs['root']['current_component_review'] == docs['component']
        print(json.dumps({'status': 'ALREADY_IMPORTED_IDEMPOTENT_NO_WRITE', 'batch': 11}))
        return

    for entry in manifest['files']:
        path = ROOT / entry['snapshot']
        assert sha(path) == entry['sha256'] and path.stat().st_size == entry['bytes']
    messages = {x['line']: x for x in manifest['verified_messages']}
    with Path(next(iter(messages.values()))['transcript']).open('rb') as stream:
        assert json.loads(next(stream))['payload']['id'] == package['source_owner_session']
        verified = set()
        for number, raw in enumerate(stream, 2):
            if number > max(messages):
                break
            if number not in messages:
                continue
            expected = messages[number]
            actual = json.loads(raw)
            text = '\n'.join(x.get('text', '') for x in actual['payload']['content']
                             if x.get('type') in ['input_text', 'output_text', 'text'])
            assert actual['payload']['role'] == expected['role']
            assert text == expected['text'] and actual['timestamp'] == expected['timestamp']
            assert hashlib.sha256(raw).hexdigest() == expected['raw_line_sha256']
            verified.add(number)
    assert len(verified) == 15
    heads = read(HERE / 'current-reference-check.json')
    originals = read(HERE / 'current-original-receipts.json')
    assert heads['status'] == originals['status'] == 'PASS'
    assert len(heads['heads']) == 21 and len(originals['entries']) == 11
    assert (HERE / 'root-reviewed-all-selected-originals.jpg').is_file()
    head_by_id = {x['id']: x['metadata'] for x in heads['heads']}
    originals_by_id = {x['id']: x for x in originals['entries']}
    for original in originals['entries']:
        assert sha(ROOT / original['local_path']) == original['sha256']

    before = copy.deepcopy(docs)
    hashes = {key: sha(path) for key, path in paths.items()}
    user, progress, cp, component = (docs[x] for x in ['user', 'progress', 'walkthrough', 'component'])
    assert docs['root']['current_component_review'] == component
    assert cp['current_component_id'] == 'BC-MCP-4' and not cp['current_answer_recorded']
    assert cp['review_decision_mode'] == 'DEPICTED_DESIGN_ALIAS_RELATIONSHIP_ONLY'
    assert cp['parallel_import_holds']['Moonphases']['old_five_design_import_allowed'] is False
    protected_paths = [ROOT / 'components/evidence/component_register.json', ROOT / cp['register_workbook'],
                       ROOT / cp['current_review_record'], ROOT / cp['last_identity_approval'],
                       REVIEWS / 'concave-moon-review-2026-10-17/specification-approval.json',
                       ROOT.parent / 'Boldstone_Wall_Sculptures_Matched_All_Fields_2026-10-15.xlsx']
    protected = {str(path): sha(path) for path in protected_paths}
    now = datetime.now(timezone.utc).isoformat()
    outputs, ledger_ids = [], {}

    def save(name, value, ledger=None):
        path = HERE / 'decisions' / name
        assert not path.exists()
        outputs.append((path, value))
        if ledger:
            assert not any(x.get('decision_id') == value['decision_id'] for x in user.get(ledger, []))
            user.setdefault(ledger, []).append(copy.deepcopy(value) | {'approval_record': rel(path)})
            ledger_ids.setdefault(ledger, []).append(value['decision_id'])
        return rel(path)

    def reference(review):
        image = review['primary_image']
        folder = review.get('primary_folder', review.get('folder'))
        current_image, current_folder = head_by_id[image['id']], head_by_id[folder['id']]
        original = originals_by_id[image['id']]
        assert current_image['rev'] == image['rev'] and current_image['size'] == image['size']
        assert current_image['path_display'].rsplit('/', 1)[0].casefold() == current_folder['path_display'].casefold()
        return {'file_id': image['id'], 'folder_id': folder['id'],
                'file_path': current_image['path_display'], 'folder_path': current_folder['path_display'],
                'rev': image['rev'], 'bytes': original['size'], 'sha256': original['sha256'],
                'dropbox_content_hash': original['content_hash'], 'checked_utc': heads['checked_utc'],
                'image_link': 'https://www.dropbox.com/preview' + quote(current_image['path_display'], safe='/'),
                'folder_link': 'https://www.dropbox.com/home' + quote(current_folder['path_display'], safe='/'),
                'link_type': 'Account path link; browser opening not independently tested',
                'same_reviewed_file_id_rev_size_and_content_hash': True}

    grouped, source_records = {}, []
    for item in manifest['source_decisions']:
        binding = item['binding']
        review = read(ROOT / item['review_snapshot'])
        owner = read(ROOT / item['owner_snapshot'])
        assert owner['approved_name'] == binding['historical_name'] and not owner['specification_fields_approved']
        ref = reference(review)
        source = {'decision_id': 'MOONPHASES:SOURCE-KEEP:' + binding['deduplication_key'],
                  'historical_component_id': binding['historical_component_id'],
                  'historical_review_id': binding['historical_review_id'], 'historical_kept_name': binding['historical_name'],
                  'current_catalogue_design_key': binding['catalogue_design_key'], 'current_variant_key': binding['variant_key'],
                  'current_display_name': binding['current_name'], 'source_owner_session': package['source_owner_session'],
                  'source_owner_evidence': copy.deepcopy(binding['source_owner_evidence']),
                  'current_alias_scope': binding['current_alias_scope'], 'depicted_component_position': binding['depicted_component_position'],
                  'source_review_snapshot': item['review_snapshot'], 'source_owner_snapshot': item['owner_snapshot'],
                  'source_card_snapshot': item['card_snapshot'], 'current_dropbox_reference': ref,
                  'historical_specification_proposals': copy.deepcopy(review['specifications']),
                  'full_source_review_preserved': True, 'all_six_specifications_approved': False,
                  'physical_cast_mould_stock_equivalence_confirmed': False, 'imported_utc': now}
        source_path = save('source-keeps/' + binding['historical_review_id'] + '.json', source,
                           'catalogue_historical_name_keep_bindings')
        source['binding_record'] = source_path
        source_records.append(source)
        grouped.setdefault(binding['variant_key'], []).append(source)
    assert len(source_records) == 10 and len(grouped) == 8

    design_records = []
    for design in package['current_design_crosswalk']:
        key = design['catalogue_design_key']
        record = copy.deepcopy(design) | {'decision_id': key + ':CURRENT-DISPLAY-ALIAS', 'family': 'Moonphases',
                 'status': 'CATALOGUE_ALIAS_REGISTERED;HISTORICAL_SOURCE_IDS_RETAINED',
                 'owner_four_design_structure_confirmed': True,
                 'current_number_is_verbatim_owner_instruction': key == 'MOONPHASE-CURRENT-4',
                 'source_owner_correction': copy.deepcopy(package['owner_numbering_correction']),
                 'new_registered_BC_component_id': False, 'physical_mould_or_stock_count_verified': False,
                 'specifications_approved': False, 'imported_utc': now}
        record['approval_record'] = save('design-aliases/' + key + '.json', record, 'catalogue_design_alias_decisions')
        design_records.append(record)

    alias_records = {}
    for key, sources in grouped.items():
        names = {x['current_display_name'] for x in sources}
        assert len(names) == 1 and next(iter(names)) == package['unique_current_finish_variant_names_from_keeps'][key]
        name = next(iter(names))
        record = {'schema_version': 1, 'decision_id': key + ':CURRENT-NAME-ALIAS', 'catalogue_variant_key': key,
                  'catalogue_design_key': sources[0]['current_catalogue_design_key'], 'canonical_name': name,
                  'status': 'SOURCE_DEPICTED_NAME_KEEPS_RETAINED_UNDER_CURRENT_FOUR_DESIGN_CROSSWALK',
                  'historical_name_keep_bindings': copy.deepcopy(sources), 'source_keep_count': len(sources),
                  'current_display_number_provenance': next(x['numbering_basis'] for x in design_records
                                                           if x['catalogue_design_key'] == sources[0]['current_catalogue_design_key']),
                  'source_depicted_identities_kept': True, 'blanket_owner_numbering_approval_inferred': False,
                  'source_specification_proposals_preserved_separately': True,
                  'specification_fields_status': {field: 'PENDING' for field in sources[0]['historical_specification_proposals']},
                  'all_six_specifications_approved': False, 'physical_specs_verified': False,
                  'new_registered_BC_component_id': False, 'physical_stock_or_mould_merge': False,
                  'primary_file_ids': list(dict.fromkeys(x['current_dropbox_reference']['file_id'] for x in sources)),
                  'containing_folder_ids': list(dict.fromkeys(x['current_dropbox_reference']['folder_id'] for x in sources)),
                  'source_owner_session': package['source_owner_session'], 'imported_utc': now}
        approval = save('finish-aliases/' + key.replace(':', '__') + '.json', record, 'catalogue_finish_alias_decisions')
        alias_records[key] = record | {'approval_record': approval}

    weight = read(ROOT / manifest['weight_receipt_snapshot'])
    key = package['conditional_weight_acceptance']['current_variant_key']
    assert key == 'MOONPHASE-CURRENT-1:WHITE-WITH-BORDER' and weight['component_id'] == 'BC-MP-2'
    proposal_id = key + ':WEIGHT-CONDITIONAL-6KG-RANGE4TO9'
    weight_record = {'schema_version': 1, 'decision_id': key + ':CONDITIONAL-WEIGHT-ACCEPTANCE',
                    'source_decision_id': key + ':OWNER-OKAY-LINE13898', 'component_id': 'BC-MP-2',
                    'size_finish_variant_id': key, 'catalogue_design_key': 'MOONPHASE-CURRENT-1',
                    'canonical_name': package['conditional_weight_acceptance']['current_name'],
                    'source_owner_session': package['source_owner_session'], 'authoritative_user_evidence': messages[13898],
                    'preceding_assistant_estimate': messages[13889], 'recorded_utc': messages[13898]['timestamp'],
                    'source_receipt_snapshot': manifest['weight_receipt_snapshot'],
                    'source_receipt_sha256': sha(ROOT / manifest['weight_receipt_snapshot']),
                    'approved_proposal_ids': [proposal_id], 'approved_fields': ['conditional_planning_weight_estimate'],
                    'accepted_nominal_estimated_kg': 6, 'accepted_rough_working_range_kg': [4, 9],
                    'scope': weight['approval_scope'], 'model_assumptions_are_owner_dimensions_or_material': False,
                    'actual_weight_measured': False, 'physical_specs_verified': False, 'specifications_approved': False,
                    'proposals_approved': False, 'other_five_specification_fields_approved': False,
                    'must_not_attach_to_nested_current_Moonphase_Two': True, 'imported_utc': now}
    weight_path = save('conditional-curl-border-weight.json', weight_record, 'size_finish_variant_specification_decisions')
    alias_records[key]['conditional_weight_estimate_acceptance'] = weight_record | {'approval_record': weight_path}
    alias_records[key]['specification_fields_status']['weight'] = 'CONDITIONAL_PLANNING_ESTIMATE_ACCEPTED;ACTUAL_WEIGHT_PENDING'

    addendum = read(ROOT / manifest['arrangement_addendum_snapshot'])
    arrangement_review = read(ROOT / manifest['arrangement_review_snapshot'])
    owner = addendum['owner_decision']
    aid = arrangement_review['review_id']
    arrangement = {'schema_version': 1, 'decision_id': aid + ':NAME-KEEP', 'arrangement_id': aid,
                   'canonical_name': addendum['approved_name'], 'record_kind': 'ARRANGEMENT_NAME_ONLY',
                   'authoritative_user_evidence': messages[14751], 'source_owner_session': package['source_owner_session'],
                   'recorded_utc': messages[14751]['timestamp'], 'imported_utc': now, 'name_identity_confirmed': True,
                   'approval_scope': owner['approval_scope'], 'current_dropbox_reference': reference(arrangement_review),
                   'source_review_snapshot': manifest['arrangement_review_snapshot'],
                   'source_addendum_snapshot': manifest['arrangement_addendum_snapshot'],
                   'primary_image_design_sequence_left_to_right': arrangement_review['primary_current_design_sequence_left_to_right'],
                   'alternate_image_design_sequence_left_to_right': arrangement_review['alternate_current_design_sequence_left_to_right'],
                   'alternate_image_source': copy.deepcopy(arrangement_review['alternate_context_image']),
                   'depicted_panels_per_reference': 5, 'unique_catalogue_designs_depicted': 4,
                   'layout_is_asset_specific_not_a_verified_physical_BOM': True,
                   'physical_unique_cast_mould_or_stock_count_verified': False,
                   'specification_proposals': copy.deepcopy(arrangement_review['specifications']),
                   'all_six_fields_pending': True, 'specifications_approved': False, 'physical_specs_verified': False,
                   'thirty_kg_estimate_owner_accepted': False, 'whole_set_dimensions_are_owner_measurements': False,
                   'scene_origin_and_plumbing_verified': False, 'new_individual_product_created': False}
    arrangement_path = save('arrangements/' + aid + '.json', arrangement, 'arrangement_name_decisions')

    progress.setdefault('catalogue_design_aliases', {}).update({x['catalogue_design_key']: x for x in design_records})
    progress.setdefault('catalogue_alias_reviews', {}).update(alias_records)
    progress.setdefault('historical_source_component_to_catalogue_aliases', {}).update({
        cid: sorted({x['current_variant_key'] for x in source_records if x['historical_component_id'] == cid})
        for cid in package['historical_component_to_current_design']})
    progress.setdefault('arrangement_reviews', {})[aid] = arrangement | {'approval_record': arrangement_path}
    alias_counts = {'catalogue_design_aliases': 4, 'catalogue_finish_construction_aliases': 8,
                    'retained_historical_name_keep_bindings': 10, 'arrangement_name_keeps': 1,
                    'is_physical_sculpture_mould_or_stock_count': False,
                    'not_added_to_overlapping_legacy_identity_scope_counts': True}
    user.setdefault('catalogue_alias_confirmation_counts', {})['Moonphases'] = copy.deepcopy(alias_counts)
    user['identity_confirmation_counts'] = identity_counts(user)
    user['specification_approval_counts'] = specification_counts(user)
    assert user['identity_confirmation_counts'] == before['user']['identity_confirmation_counts']
    expected_spec_counts = copy.deepcopy(before['user']['specification_approval_counts'])
    expected_spec_counts['size_finish_variant_proposal_groups'] += 1
    expected_spec_counts['proposal_groups'] += 1
    assert user['specification_approval_counts'] == expected_spec_counts
    assert user['dimension_confirmation_counts'] == before['user']['dimension_confirmation_counts']
    summary = {'batch': 11, 'recorded_utc': now, 'receipt': rel(receipt_path), 'family': 'Moonphases',
               'current_design_aliases': 4, 'finish_construction_aliases': 8, 'historical_name_keep_bindings': 10,
               'arrangement_name_keeps': 1, 'new_conditional_weight_estimate_acceptances': 1,
               'new_complete_specification_approvals': 0, 'new_Silver_name_keep': False,
               'source_component_ids_preserved': sorted(package['historical_component_to_current_design']),
               'physical_sculpture_mould_stock_count_verified': False, 'new_BC_component_ids_created': False,
               'main_Concave_MCP4_question_preserved': True, 'old_five_public_names_still_forbidden': True,
               'root_current_heads_verified': 21, 'root_selected_originals_hash_checked_and_viewed': 11,
               'whole_family_root_live_reaudit_claimed': False, 'workbook_export_pending': True, 'remote_mutations': 0}
    for target in [cp, component]:
        hold = target['parallel_import_holds']['Moonphases']
        hold.update({'status': 'CURRENT_FOUR_DESIGN_ALIASES_AND_EXACT_KEEPS_IMPORTED;OLD_FIVE_PUBLIC_NAMES_FORBIDDEN',
                     'legacy_name_receipt_import_pending': False, 'canonical_keep_import_pending': False,
                     'canonical_keep_import_receipt': rel(receipt_path), 'catalogue_alias_mapping_applied': True,
                     'old_five_design_import_allowed': False,
                     'remaining_scope': 'Other specification, provenance, physical cast/mould/stock and asset exceptions remain pending.'})
        for flag in target.get('parallel_evidence_flags', []):
            if flag.get('flag_id') == hold['flag_id']:
                flag.update({'status': hold['status'], 'canonical_keep_import_receipt': rel(receipt_path),
                             'catalogue_alias_mapping_applied': True, 'remaining_scope': hold['remaining_scope']})
        for allocation in target['parallel_owner_reviews']:
            if allocation['component_id'] in package['historical_component_to_current_design']:
                allocation.update({'status': 'CURRENT_FOUR_DESIGN_ALIASES_IMPORTED;HISTORICAL_SOURCE_IDS_AND_GAPS_RETAINED',
                                   'import_receipt': rel(receipt_path), 'public_design_count': 4})
        target['last_parallel_import'] = copy.deepcopy(summary)
        target['updated_utc'] = now
    overlay = progress['current_catalogue_overlays']['Moonphases']
    overlay.update({'legacy_keep_receipts_pending_canonical_import': False, 'canonical_keep_import_receipt': rel(receipt_path),
                    'catalogue_alias_counts': copy.deepcopy(alias_counts),
                    'application_scope': 'Four current design aliases, eight finish/construction aliases and ten original Keeps retained. One conditional curl-border weight acceptance; arrangement name separately imported. Historical BC IDs, source-specific specifications and physical lineage preserved.'})
    component.setdefault('current_catalogue_overlays', {})['Moonphases'] = copy.deepcopy(overlay)
    supplement = {'summary': summary, 'source_manifest': rel(HERE / 'source-manifest.json'),
                  'source_package_sha256': manifest['source_package_sha256'],
                  'full_first_pass_source_evidence': copy.deepcopy(package['first_pass_family']),
                  'already_reviewed_75_asset_crosswalk': copy.deepcopy(package['already_reviewed_75_asset_crosswalk']),
                  'unaccepted_nested_border_weight_proposal': copy.deepcopy(package['unaccepted_nested_border_proposal']),
                  'Silver_evidence_only_no_new_Keep': copy.deepcopy(package['Silver']),
                  'source_scope_rule': 'Peer first-pass coverage is not a fresh root 298-file audit. All original source claims and unresolved exceptions retained.',
                  'historical_five_mould_source_assertion_retained': True}
    progress.setdefault('parallel_family_evidence', {})['Moonphases'] = copy.deepcopy(supplement)
    progress.setdefault('family_review_progress', {})['Moonphases'] = {
        'status': 'FOUR_DESIGN_CURRENT_ALIAS_KEEPS_IMPORTED;PHYSICAL_SPECIFICATIONS_AND_PHOTO_EXCEPTIONS_PENDING',
        'specifications_complete': False, 'physical_specs_verified': False, 'supplement': copy.deepcopy(supplement)}
    component.setdefault('family_review_supplements', {})['Moonphases'] = copy.deepcopy(supplement)
    queue = next(x for x in cp['parallel_import_queue'] if x['receipt'] == manifest['source_package'])
    assert queue['receipt_sha256'] == manifest['source_package_sha256'] and not queue['approval_imported']
    queue.update({'status': 'APPLIED_AND_VERIFIED_CURRENT_FOUR_DESIGN_ALIASES;EXACT_SCOPES_RETAINED',
                  'approval_imported': True, 'import_receipt': rel(receipt_path), 'imported_utc': now,
                  'old_five_public_name_import_performed': False, 'arrangement_addendum_imported': True})
    component['parallel_import_queue'] = copy.deepcopy(cp['parallel_import_queue'])
    component['interactive_review_state']['approved_proposal_groups'] = user['specification_approval_counts']['proposal_groups']
    component['catalogue_alias_confirmation_counts'] = copy.deepcopy(user['catalogue_alias_confirmation_counts'])
    cp['last_parallel_import'] = progress['latest_parallel_import'] = copy.deepcopy(summary)
    cp['next_serialized_parallel_import'] = cp['completed_serialized_parallel_import'] = {
        'status': 'APPLIED_AND_VERIFIED', 'receipt': rel(receipt_path), 'completed_utc': now}
    user['updated_utc'] = progress['updated_utc'] = now
    docs['root']['current_component_review'] = copy.deepcopy(component)
    docs['root']['updated_utc'] = now

    for key, value in before['walkthrough'].items():
        if key.startswith('current_') or key in ['proposed_name', 'answer_state', 'question_scope',
                                                'next_review_after_keep', 'after_main_family_next_unclaimed']:
            assert cp[key] == value, key
    for key, value in before['user'].items():
        if isinstance(value, list):
            assert user[key][:len(value)] == value, key
    assert progress['reviews'] == before['progress']['reviews']
    for key in ['asset_assignment_overrides', 'catalogue_group_overrides']:
        assert progress.get(key) == before['progress'].get(key)
    assert not any(':SILVER' in key for key in alias_records)
    assert all(sha(Path(path)) == digest for path, digest in protected.items())
    assert all(sha(paths[key]) == digest for key, digest in hashes.items()), 'Concurrent shared write'
    write(HERE / 'before-import.json', before)
    for path, value in outputs:
        write(path, value)
    for key, path in paths.items():
        write(path, docs[key])
    receipt = {'status': 'APPLIED;INDEPENDENT_READBACK_REQUIRED', 'summary': summary,
               'source_manifest_sha256': sha(HERE / 'source-manifest.json'), 'new_ledger_decision_ids': ledger_ids,
               'decision_files': {rel(path): sha(path) for path, _ in outputs},
               'shared_before_sha256': hashes, 'shared_after_sha256': {key: sha(path) for key, path in paths.items()},
               'protected_source_sha256': protected, 'identity_counts_before_after_unchanged': True,
               'specification_counts_after': user['specification_approval_counts'],
               'legacy_interactive_group_counter_refreshed_from': before['component']['interactive_review_state']['approved_proposal_groups'],
               'legacy_interactive_group_counter_refreshed_to': user['specification_approval_counts']['proposal_groups'],
               'main_question_preserved': True, 'remote_mutations': 0}
    write(receipt_path, receipt)
    print(json.dumps({'status': receipt['status'], 'summary': summary, 'decision_files': len(outputs),
                      'specification_proposal_groups': user['specification_approval_counts']['proposal_groups']}))


if __name__ == '__main__':
    main()
