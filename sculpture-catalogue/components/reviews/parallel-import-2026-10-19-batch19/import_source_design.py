"""Import exact source-name and production-existence answers, without sale units."""
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

KEY = 'FINGERPRINT-SEGMENTED-WHITE-G156002'
FILE_ID = 'id:cnqzTNngPVsAAAAAAAyhOA'
FOLDER_ID = 'id:cnqzTNngPVsAAAAAAAyhIA'
PACKAGE_SHA = 'ff4b5a24d86746528f9288391607acb937174f3d0f1ceba8bfcd24b4732eb451'
read = lambda p: json.loads(p.read_text())
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
rel = lambda p: str(p.relative_to(ROOT))


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    temp.replace(path)


def main():
    paths = {'user': REVIEWS / 'user_classifications.json',
             'progress': REVIEWS / 'specification_review_progress.json',
             'walkthrough': REVIEWS / 'walkthrough_checkpoint.json',
             'component': ROOT / 'components/checkpoint.json', 'root': ROOT / 'checkpoint.json'}
    docs = {key: read(path) for key, path in paths.items()}
    receipt_path = HERE / 'import-receipt.json'
    if receipt_path.exists():
        receipt = read(receipt_path)
        for ledger, decision_id in receipt['decision_ids'].items():
            assert sum(x['decision_id'] == decision_id for x in docs['user'][ledger]) == 1
        assert docs['progress']['source_design_reviews'][KEY]['source_asset_id'] == FILE_ID
        assert docs['progress']['pending_component_decompositions'][KEY]['status'] == 'COMPONENT_MEMBERS_PENDING'
        assert docs['root']['current_component_review'] == docs['component']
        print(json.dumps({'status': 'ALREADY_IMPORTED_IDEMPOTENT_NO_WRITE', 'batch': 19}))
        return

    manifest = read(HERE / 'source-manifest.json')
    assert manifest['source_package_sha256'] == PACKAGE_SHA
    assert sha(ROOT / manifest['source_package']) == sha(ROOT / manifest['package_snapshot']) == PACKAGE_SHA
    for item in manifest['files']:
        frozen = ROOT / item['snapshot']
        assert sha(frozen) == item['sha256'] and frozen.stat().st_size == item['bytes']
    package = read(ROOT / manifest['package_snapshot'])
    name = read(ROOT / manifest['name_receipt_snapshot'])
    production = read(ROOT / manifest['production_receipt_snapshot'])
    review = read(ROOT / manifest['review_snapshot'])
    assert package['owner_name_approval_count'] == package['owner_production_confirmation_count'] == 1
    assert package['new_BC_component_ids'] == package['owner_specification_approvals'] == []
    assert package['reference_asset_id'] == name['reference_image']['id'] == production['reference_image']['id'] == FILE_ID
    assert name['approved_name'] == 'Fingerprint — Segmented Arrangement (White)'
    assert production['owner_confirms_design_physically_made'] is True
    assert name['specification_fields_fully_approved'] == production['specification_fields_fully_approved'] == []
    frozen_hashes = {x['sha256'] for x in manifest['files']}
    for item in [name, production]:
        assert item['review_card_sha256'] in frozen_hashes and item['review_json_sha256'] in frozen_hashes
    expected = {x['line']: x for x in manifest['verified_messages']}
    assert set(expected) == {15696, 15719, 15823, 15858}
    with Path(next(iter(expected.values()))['transcript']).open('rb') as stream:
        assert json.loads(next(stream))['payload']['id'] == package['source_owner_session']
        for number, raw in enumerate(stream, 2):
            if number > max(expected):
                break
            if number not in expected:
                continue
            evidence, actual = expected[number], json.loads(raw)
            payload = actual['payload']
            text = '\n'.join(x.get('text', '') for x in payload['content']
                             if x.get('type') in ['input_text', 'output_text', 'text'])
            assert payload['role'] == evidence['role'] and text == evidence['text']
            assert actual['timestamp'] == evidence['timestamp']
            assert hashlib.sha256(text.encode()).hexdigest() == evidence['text_sha256']
            assert hashlib.sha256(raw).hexdigest() == evidence['raw_line_sha256']
    assert expected[15719]['text'] == 'Yes physically made and estiamte all the values'
    assert expected[15858]['text'] == 'Keep “Fingerprint — Segmented Arrangement (White)”'
    assert review['browser_links']['image'] in expected[15696]['text']
    assert review['browser_links']['image'] in expected[15823]['text']
    heads = read(HERE / 'current-reference-check.json')
    file_head = next(x['file'] for x in heads['metadata'] if x['metadata_type'] == 'file')
    folder_head = next(x['folder'] for x in heads['metadata'] if x['metadata_type'] == 'folder')
    for field in ['id', 'rev', 'size', 'path_display']:
        assert file_head[field] == name['reference_image'][field]
    assert folder_head['id'] == name['reference_folder']['id'] == FOLDER_ID
    assert folder_head['path_display'] == name['reference_folder']['path_display']
    assert file_head['path_display'].rsplit('/', 1)[0] == folder_head['path_display']
    assert sha(ROOT / manifest['preview_snapshot']) == manifest['preview_sha256']

    before = copy.deepcopy(docs)
    hashes = {key: sha(path) for key, path in paths.items()}
    user, progress, cp, component = (docs[key] for key in ['user', 'progress', 'walkthrough', 'component'])
    assert docs['root']['current_component_review'] == component
    assert cp['current_component_id'] == 'BC-MCP-4' and cp['current_answer_recorded'] is False
    assert KEY not in progress.get('source_design_reviews', {})
    assert FILE_ID not in progress.get('asset_assignment_overrides', {})
    protected_paths = [ROOT / 'components/evidence/component_register.json', ROOT / cp['register_workbook'],
                       ROOT / cp['current_review_record'],
                       ROOT.parent / 'Boldstone_Wall_Sculptures_Matched_All_Fields_2026-10-15.xlsx']
    protected = {str(path): sha(path) for path in protected_paths}
    now = datetime.now(timezone.utc).isoformat()
    visual_path = HERE / 'root-visual-review.json'
    name_path, production_path = HERE / 'source-name-decision.json', HERE / 'production-existence-decision.json'
    scope = {'source_design_key': KEY, 'group_ref': 'G156', 'allocation_review_id': 'UGR-G156',
             'source_asset_id': FILE_ID, 'source_folder_id': FOLDER_ID,
             'source_path_display': file_head['path_display'], 'source_folder_path_display': folder_head['path_display'],
             'image_link': review['browser_links']['image'], 'folder_link': review['browser_links']['folder'],
             'source_owner_session': package['source_owner_session'], 'imported_utc': now,
             'source_package_sha256': PACKAGE_SHA, 'root_visual_review': rel(visual_path),
             'source_image_authenticated_as_original_photo': False, 'physical_specs_verified': False,
             'component_ids': [], 'component_members_status': 'COMPONENT_MEMBERS_PENDING',
             'new_sale_unit_mould_or_stock_count': False, 'new_full_specification_approval': False,
             'workbook_export_pending': True, 'remote_mutations': 0}
    name_record = copy.deepcopy(scope) | {
        'decision_id': name['decision_id'], 'approved_name': name['approved_name'],
        'recorded_utc': expected[15858]['timestamp'], 'authoritative_user_evidence': expected[15858],
        'preceding_question_evidence': expected[15823], 'approval_scope': name['approval_scope'],
        'source_receipt_snapshot': manifest['name_receipt_snapshot'], 'approval_record': rel(name_path)}
    production_record = copy.deepcopy(scope) | {
        'decision_id': production['decision_id'], 'owner_stated_design_physically_made': True,
        'recorded_utc': expected[15719]['timestamp'], 'authoritative_user_evidence': expected[15719],
        'preceding_question_evidence': expected[15696], 'confirmation_scope': production['confirmation_scope'],
        'current_stock_and_leadtime_confirmed': False, 'physical_production_independently_verified': False,
        'source_receipt_snapshot': manifest['production_receipt_snapshot'], 'approval_record': rel(production_path)}
    production_record['estimate_all_six_specification_groups_requested'] = True
    production_record['estimates_owner_accepted'] = False
    user.setdefault('source_design_name_decisions', []).append(name_record)
    user.setdefault('design_production_confirmation_decisions', []).append(production_record)
    design = copy.deepcopy(scope) | {
        'record_kind': 'OWNER_NAMED_SOURCE_GEOMETRY;COMPONENT_DECOMPOSITION_PENDING',
        'status': 'SOURCE_NAME_KEPT;OWNER_STATED_DESIGN_MADE;INDIVIDUAL_COMPONENTS_AND_SPECS_PENDING',
        'canonical_source_name': name['approved_name'], 'name_approval_record': rel(name_path),
        'production_existence_record': rel(production_path), 'owner_stated_design_physically_made': True,
        'physical_production_independently_verified': False,
        'source_file_revision': file_head['rev'], 'source_file_bytes': file_head['size'],
        'source_content_hash_from_frozen_native_record': package['reference_content_hash'],
        'current_reference_check': rel(HERE / 'current-reference-check.json'),
        'current_reference_verification_scope': 'File ID/revision/size/path and containing-folder ID/path; cached preview viewed. Original PNG not newly downloaded or root byte-verified.',
        'specifications': copy.deepcopy(review['specifications']), 'specification_fields_fully_approved': [],
        'all_six_complete_specification_groups_pending': True,
        'prior_concentric_dimensions_and_weight_not_transferred': True,
        'working_estimates_snapshot': manifest['working_estimates_snapshot'],
        'weight_calculation_snapshot': manifest['weight_calculation_snapshot'],
        'public_references_snapshot': manifest['public_references_snapshot'],
        'owner_estimates_accepted': False,
        'specification_scope': 'Proposals for whole arrangement and unallocated section ranges only. No actual individual component specification established.',
        'existing_squarespace_shopify_match_confirmed': False}
    progress.setdefault('source_design_reviews', {})[KEY] = design
    pending = {'source_design_key': KEY, 'status': 'COMPONENT_MEMBERS_PENDING', 'source_asset_id': FILE_ID,
               'source_folder_id': FOLDER_ID, 'source_name': name['approved_name'],
               'image_link': scope['image_link'], 'folder_link': scope['folder_link'],
               'depicted_panel_positions': [], 'depicted_panel_position_count': None,
               'depicted_geometry': 'Irregular segmented arrangement; no component count certified.',
               'unique_component_design_count': None, 'individual_sale_unit_count': None, 'physical_stock_count': None,
               'required_before_individual_listings': [
                   'Identify individual sections only if component review is resumed.',
                   'Resolve distinct versus repeated or rotated designs; confirm each component name.',
                   'Create component records only after verification, with separately scoped specifications and offers.',
                   'Find individual front/rear references and authenticated context or series images.'],
               'set_dimensions_weight_and_price_must_not_be_divided': True,
               'owner_name_record': rel(name_path), 'production_existence_record': rel(production_path)}
    progress.setdefault('pending_component_decompositions', {})[KEY] = pending
    progress['asset_assignment_overrides'][FILE_ID] = {
        'family': 'Fingerprint', 'group_ref': 'G156', 'source_design_key': KEY,
        'file_id': FILE_ID, 'folder_id': FOLDER_ID, 'component_ids': [],
        'excluded_concentric_component_ids_for_this_file_only': ['BC-FP-LEFT', 'BC-FP-RIGHT'],
        'assignment_status': 'OWNER_NAMED_SEGMENTED_SOURCE_DESIGN;INDIVIDUAL_MEMBERS_PENDING',
        'scope': 'Exact file only. Baseline broad folder associations are insufficient for this segmented depiction; other G156 images and prior concentric decisions retain their exact scopes.',
        'name_approval_record': rel(name_path), 'root_visual_review': rel(visual_path),
        'exact_component_and_sale_unit_confirmed': False, 'physical_specs_verified': False}
    summary = {'batch': 19, 'recorded_utc': now, 'receipt': rel(receipt_path), 'source_design_key': KEY,
               'new_source_design_names': 1, 'new_owner_stated_design_existence_confirmations': 1,
               'new_component_ids': [], 'new_individual_sale_units': 0, 'new_full_specification_approvals': 0,
               'complete_specification_groups_pending': 6, 'availability_design_existence_only_owner_confirmed': True,
               'requested_provisional_specification_groups_retained': 6, 'owner_estimates_accepted': False,
               'component_decomposition_pending': True, 'main_Concave_MCP4_question_preserved': True,
               'G050_deferral_preserved': True, 'workbook_export_pending': True,
               'new_private_original_downloads': 0, 'remote_mutations': 0,
               'counts_scope': 'Source name/existence records excluded from legacy component/finish counters; no physical sculpture or stock count established.'}
    cp['parallel_import_queue'].append({'scope_kind': 'SOURCE_NAME_AND_OWNER_STATED_PRODUCTION_EXISTENCE',
        'receipt': manifest['source_package'], 'receipt_sha256': PACKAGE_SHA,
        'status': 'APPLIED_EXACT_SOURCE_SCOPE;INDIVIDUAL_COMPONENTS_PENDING', 'approval_imported': True,
        'source_manifest': rel(HERE / 'source-manifest.json'), 'import_receipt': rel(receipt_path)})
    component['parallel_import_queue'] = copy.deepcopy(cp['parallel_import_queue'])
    for target in [cp, component]:
        target.setdefault('pending_component_decompositions', {})[KEY] = copy.deepcopy(pending)
        target['last_parallel_import'] = copy.deepcopy(summary)
        target['updated_utc'] = now
    completed = {'status': 'APPLIED_AND_VERIFIED', 'receipt': rel(receipt_path),
                 'source_package': manifest['source_package'], 'completed_utc': now}
    cp['next_serialized_parallel_import'] = copy.deepcopy(completed)
    cp['completed_serialized_parallel_import'] = copy.deepcopy(completed)
    component.setdefault('family_review_supplements', {})[KEY] = {
        'summary': copy.deepcopy(summary), 'source_design_review_key': KEY,
        'name_record': rel(name_path), 'production_existence_record': rel(production_path)}
    progress['latest_parallel_import'] = copy.deepcopy(summary)
    user['updated_utc'] = progress['updated_utc'] = now
    docs['root']['current_component_review'] = copy.deepcopy(component)
    docs['root']['updated_utc'] = now

    assert identity_counts(user) == before['user']['identity_confirmation_counts']
    assert specification_counts(user) == before['user']['specification_approval_counts']
    assert all((user[key][:len(value)] == value if key in ['source_design_name_decisions', 'design_production_confirmation_decisions'] else user[key] == value)
               for key, value in before['user'].items() if key != 'updated_utc')
    assert progress['reviews'] == before['progress']['reviews']
    assert all(progress['asset_assignment_overrides'][key] == value
               for key, value in before['progress']['asset_assignment_overrides'].items())
    assert all(cp[key] == value for key, value in before['walkthrough'].items() if key.startswith('current_'))
    assert cp['deferred_reviews'] == before['walkthrough']['deferred_reviews']
    assert cp['parallel_group_reviews'] == before['walkthrough']['parallel_group_reviews']
    assert all(sha(paths[key]) == digest for key, digest in hashes.items()), 'Concurrent shared write'
    assert all(sha(Path(path)) == digest for path, digest in protected.items())
    write(HERE / 'before-import.json', before)
    write(visual_path, {'reviewed_utc': now, 'root_reviewer': 'main_single_writer',
          'preview_snapshot': manifest['preview_snapshot'], 'preview_sha256': manifest['preview_sha256'],
          'source_asset_id': FILE_ID, 'source_folder_id': FOLDER_ID,
          'observed': 'White landscape relief with flowing wavy ridges, divided by irregular branching gaps into sections against a stone wall.',
          'depicted_panel_positions': None, 'distinct_versus_repeated_rotated_designs_confirmed': False,
          'image_authenticity_or_client_installation_verified': False,
          'scope': 'Cached 480 x 480 preview viewed and SHA256 verified; fresh native ID/revision/size/path checked. No new original PNG download or full-family root image audit.',
          'current_reference_check': rel(HERE / 'current-reference-check.json')})
    write(name_path, name_record)
    write(production_path, production_record)
    for key, path in paths.items():
        write(path, docs[key])
    decision_ids = {'source_design_name_decisions': name['decision_id'],
                    'design_production_confirmation_decisions': production['decision_id']}
    write(receipt_path, {'status': 'APPLIED;INDEPENDENT_READBACK_REQUIRED', 'summary': summary,
          'decision_ids': decision_ids, 'source_manifest_sha256': sha(HERE / 'source-manifest.json'),
          'root_visual_review_sha256': sha(visual_path),
          'approval_record_sha256': {rel(path): sha(path) for path in [name_path, production_path]},
          'protected_sha256': protected, 'shared_after_sha256': {key: sha(path) for key, path in paths.items()}})
    print(json.dumps({'status': 'APPLIED;INDEPENDENT_READBACK_REQUIRED', 'summary': summary}))


if __name__ == '__main__':
    main()
