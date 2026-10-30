"""Import six Lava position/finish names and the owner's precisely scoped instructions."""
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
read = lambda path: json.loads(path.read_text())
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
rel = lambda path: str(path.relative_to(ROOT))


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    temp.replace(path)


def main():
    receipt_path = HERE / 'import-receipt.json'; manifest = read(HERE / 'source-manifest.json')
    paths = {'user': REVIEWS / 'user_classifications.json', 'progress': REVIEWS / 'specification_review_progress.json',
        'walkthrough': REVIEWS / 'walkthrough_checkpoint.json', 'component': ROOT / 'components/checkpoint.json', 'root': ROOT / 'checkpoint.json'}
    docs = {k: read(path) for k, path in paths.items()}
    if receipt_path.exists():
        ids = [x.get('source_decision_id') for values in docs['user'].values() if isinstance(values, list) for x in values if isinstance(x, dict)]
        assert all(ids.count(x['source_decision_id']) == 1 for x in manifest['named_entries'])
        print(json.dumps({'status': 'ALREADY_IMPORTED_IDEMPOTENT_NO_WRITE', 'six_Lava_names_and_existing_Knight_each_once': True})); return
    sources = {x['source']: x for x in manifest['files']}
    for entry in manifest['files']:
        path = ROOT / entry['snapshot']; assert sha(path) == entry['sha256'] and path.stat().st_size == entry['bytes']
    package = read(HERE / 'received-package.source.json')
    assert sha(HERE / 'received-package.source.json') == manifest['source_package_sha256']
    snap = lambda source: sources[str(Path(source).resolve())]['snapshot']
    get = lambda source: read(ROOT / snap(source))
    shared_path = next(x['path'] for x in package['field_receipts'] if x['path'].endswith('/owner-all-lava-shared-specifications-2026-10-19.json'))
    shared = get(shared_path)
    assert shared['individual_panel_dimensions'] == {'width_cm': 80, 'height_cm': 240, 'depth_cm': None}
    assert shared['conditional_working_weight_kg_per_panel'] == 105 and shared['average_material_thickness_mm'] == 30
    assert shared['conditional_calculated_weight_range_kg'] == [101, 107] and shared['conditional_weight_owner_approved']
    assert not shared['actual_mass_independently_measured'] and not shared['material_or_finish_chemistry_approved']
    assert not shared['physical_specs_verified'] and shared['fixing_type'] == 'French cleat fixings'
    assert all(shared[k] is None for k in ['fixing_count', 'fixing_material', 'fixing_dimensions', 'fixing_positions', 'wall_anchors', 'tested_load_rating'])
    assert not shared['individual_price_approved'] and not shared['availability_or_stock_approved_by_this_message']
    assert sources[shared['source_weight_proposal']]['sha256'] == shared['source_weight_proposal_sha256']
    assert sources[shared['source_average_thickness_receipt']]['sha256'] == shared['source_average_thickness_receipt_sha256']
    turns = {x['text']: x for x in manifest['owner_turns']}; owner = turns[shared['user_statement']]
    prior_text = owner['preceding_assistant_card']['text']
    assert all(x in prior_text for x in ['105', '30', '80', '240'])
    assert 'french cleat' in owner['text'].lower() and 'all Lava Moon panels' in owner['text']
    thickness_turn = turns['30 mm']; assert 'average cast-material thickness' in thickness_turn['preceding_assistant_card']['text']
    volume = 0.8 * 2.4 * 0.03; calculated_range = [volume * 1745, volume * 1850]
    assert [round(x) for x in calculated_range] == [101, 107]
    policy_path = next(x['path'] for x in package['field_receipts'] if x['path'].endswith('/owner-lava-separate-sale-policy.json'))
    policy = get(policy_path); assert policy['sale_unit']['quantity'] == 1 and not policy['production_confirmed'] and not policy['stock_confirmed']
    arrangement_source = next(x['source'] for x in manifest['files'] if x['source'].endswith('/owner-lava-arrangement-dimensions.json'))
    arrangement = get(arrangement_source)
    assert arrangement['arrangement_dimensions'] == {'height_cm': 240, 'width_cm': 240, 'depth_cm': None}
    metadata_doc = read(HERE / 'current-reference-check.json'); metadata = {x['request_id']: x for x in metadata_doc['metadata']}
    originals = read(HERE / 'current-original-download-receipts.json')
    original_map = {x['id']: x for x in originals['entries']}; assert len(original_map) == 3
    for entry in originals['entries']:
        raw = Path(entry['local_path']).read_bytes()
        assert sha(Path(entry['local_path'])) == entry['sha256'] and len(raw) == entry['size']
        assert hashlib.sha256(b''.join(hashlib.sha256(raw[i:i+4194304]).digest() for i in range(0, len(raw), 4194304))).hexdigest() == entry['content_hash']
    before = copy.deepcopy(docs); hashes = {k: sha(path) for k, path in paths.items()}
    u, p, cp, c = (docs[k] for k in ['user', 'progress', 'walkthrough', 'component'])
    assert docs['root']['current_component_review'] == c
    assert cp['current_component_id'] == 'BC-MCP-2' and cp['current_size_finish_variant_id'] == 'MCP2-VERDIGRIS-RUST' and not cp['current_answer_recorded']
    cids = {'BC-LAVA-1', 'BC-LAVA-2', 'BC-LAVA-3'}
    assert not any(cid in p['reviews'] for cid in cids)
    protected = {str(path): sha(path) for path in [ROOT / 'components/evidence/component_register.json', ROOT / cp['register_workbook'],
        ROOT / cp['current_review_record'], ROOT / cp['last_identity_approval'],
        ROOT / 'components/reviews/moon-crater-phase-review-2026-10-19/mcp2-verdigris-rust/public-offer-photo-binding.json']}
    now = datetime.now(timezone.utc).isoformat(); outputs = []; imported = []; skipped = []
    existing_ids = {x.get('source_decision_id') for values in u.values() if isinstance(values, list) for x in values if isinstance(x, dict)}

    def save(suffix, value, ledger=None):
        path = HERE / 'decisions' / suffix; assert not path.exists()
        outputs.append((path, value))
        if ledger:
            u.setdefault(ledger, []).append(value | {'approval_record': rel(path)})
        return rel(path)

    shared_record = {'schema_version': 1, 'decision_id': shared['decision_id'] + ':shared-register-import',
        'source_decision_id': shared['decision_id'], 'source_owner_session': shared['owner_session'],
        'recorded_utc': owner['timestamp'], 'imported_utc': now, 'user_statement': shared['user_statement'],
        'source_receipt_snapshot': snap(shared_path), 'source_receipt_sha256': sources[shared_path]['sha256'],
        'authoritative_user_evidence': owner, 'owner_face_dimensions_cm': {'width': 80, 'height': 240, 'depth': None},
        'accepted_conditional_weight_kg': 105, 'weight_assumptions': {'average_material_thickness_mm': 30,
            'assumed_density_kg_m3': [1745, 1850], 'model_volume_m3': volume, 'model_mass_range_kg': calculated_range,
            'rounded_model_range_kg': [101, 107], 'frames_hardware_and_packaging_excluded': True},
        'owner_fixing_type': 'French cleat fixings', 'depth_or_actual_thickness_measured': False,
        'actual_material_or_mass_verified': False, 'fixing_engineering_confirmed': False,
        'price_stock_or_production_confirmed': False, 'physical_specs_verified': False}
    assert shared_record['source_decision_id'] not in existing_ids
    shared_approval = save('LAVA/shared-owner-instruction.json', shared_record, 'shared_specification_instructions')
    for entry in manifest['named_entries']:
        card = read(ROOT / entry['latest_review_snapshot']); source = read(ROOT / entry['identity_receipt_snapshot'])
        if entry['source_decision_already_in_shared_ledger']:
            assert entry['component_id'] == 'BC-KNIGHT'
            prior = [x for x in u['size_finish_variant_decisions'] if x.get('source_decision_id') == entry['source_decision_id']]
            assert len(prior) == 1 and prior[0]['canonical_name'] == entry['name']
            dimension_source = get(next(x['path'] for x in package['field_receipts'] if x['path'].endswith('/knightsbridge-white/owner-dimensions.json')))
            assert sum(x.get('source_decision_id') == dimension_source['decision_id'] for x in u['dimension_decisions']) == 1
            skipped.append({'component_id': 'BC-KNIGHT', 'name_and_dimension_receipts_previously_imported': True}); continue
        cid, vid = entry['component_id'], entry['variant_id']; assert cid in cids and entry['source_decision_id'] not in existing_ids
        image = card.get('primary_image') or card['reference_image']; folder = card['containing_folder']
        file, fol = metadata[image['id']]['file'], metadata[folder['id']]['folder']; raw = original_map[file['id']]
        assert file['rev'] == image['rev'] and file['size'] == image['size'] and file['path_display'] == image['path']
        assert fol['path_display'] == folder['path'] and file['path_display'].rsplit('/', 1)[0] == fol['path_display']
        assert raw['content_hash'] == image['content_hash'] and raw['source_rev'] == file['rev']
        assert card['primary_image'] is None and not card['complete_isolated_primary_available']
        ref = {'file_id': file['id'], 'folder_id': fol['id'], 'file_path': file['path_display'], 'folder_path': fol['path_display'],
            'rev': file['rev'], 'bytes': file['size'], 'sha256': raw['sha256'], 'dropbox_content_hash': raw['content_hash'],
            'checked_utc': originals['checked_utc'], 'image_url': card['image_url'], 'folder_url': card['folder_url'],
            'scope': source['identity_scope'], 'isolated_individual_image': False, 'changed_since_source_card': False}
        base = {'schema_version': 1, 'component_id': cid, 'size_finish_variant_id': vid, 'canonical_name': entry['name'],
            'imported_utc': now, 'review_number': card['review_number'], 'source_owner_session': shared['owner_session'],
            'reference_file_id': file['id'], 'primary_file_id': None, 'primary_folder_id': fol['id'],
            'image_link': card['image_url'], 'folder_link': card['folder_url'], 'current_dropbox_reference': ref,
            'physical_specs_verified': False, 'physical_manufacture_confirmed': False, 'workbook_status': 'Unchanged; local review overlay for later export.'}
        identity = base | {'decision_id': cid + ':' + vid + ':identity:keep', 'source_decision_id': entry['source_decision_id'],
            'recorded_utc': turns[source['user_statement']]['timestamp'], 'user_statement': source['user_statement'],
            'confirmed_name': entry['name'], 'identity_confirmed': True, 'specifications_approved': False,
            'proposals_approved': False, 'approved_proposal_ids': [], 'scope': source['identity_scope'],
            'source_receipt_snapshot': entry['identity_receipt_snapshot'], 'source_receipt_sha256': entry['identity_receipt_sha256'],
            'proposal_source': entry['matching_pre_answer_snapshots'][0], 'proposal_source_sha256': entry['pre_answer_review_sha256'],
            'latest_corrected_review_snapshot': entry['latest_review_snapshot'], 'authoritative_user_evidence': turns[source['user_statement']],
            'status': 'OWNER CONFIRMED NAMED DEPICTED POSITION AND FINISH ONLY; EXPLICIT FIELD INSTRUCTIONS RECORDED SEPARATELY'}
        identity_path = save(cid + '/' + vid + '/identity-approval.json', identity, 'size_finish_variant_decisions')
        proposals = copy.deepcopy(card['specification_review_items']); assert len(proposals) == 6
        for item in proposals:
            item['display'] = item.get('displayed_detail', item.get('display')); item['physical_specs_verified'] = False
            item['owner_confirmed_subfields'] = []
        by_field = {x['field']: x for x in proposals}
        assert set(by_field) == {'dimensions', 'weight', 'material_finish', 'fixing', 'individual_price', 'availability'}
        assert [x['proposal_id'] for x in proposals if x['owner_approved']] == [by_field['weight']['proposal_id']]
        assert by_field['weight']['proposal_mass_kg'] == 105 and by_field['weight']['conditional_estimate_owner_approved']
        assert by_field['dimensions']['owner_approved_dimension_values'] == {'individual_panel_width_cm': 80, 'individual_panel_height_cm': 240}
        by_field['dimensions']['owner_confirmed_subfields'] = ['width', 'height']; by_field['fixing']['owner_confirmed_subfields'] = ['fixing_type']
        by_field['weight'].update({'working_proposal_accepted': True, 'actual_mass_established': False})
        sandstone = vid.endswith('SANDSTONE')
        if sandstone:
            by_field['availability']['owner_confirmed_subfields'] = ['individual_sale_unit_policy']
        confirmed = {'height': 240, 'width': 80, 'depth': None}
        common = base | {'recorded_utc': owner['timestamp'], 'user_statement': shared['user_statement'],
            'source_instruction_decision_id': shared['decision_id'], 'source_receipt_snapshot': snap(shared_path),
            'source_receipt_sha256': sources[shared_path]['sha256'], 'authoritative_user_evidence': owner,
            'shared_instruction_approval': shared_approval}
        dim = common | {'decision_id': cid + ':' + vid + ':face:80W240H:owner-stated',
            'source_decision_id': shared['decision_id'] + ':' + vid + ':face', 'scope_kind': 'INDIVIDUAL_FACE_SIZE',
            'confirmed_dimensions_cm': confirmed, 'status': 'OWNER FACE DIMENSIONS ONLY; DEPTH UNCONFIRMED',
            'scope': '80 cm wide and240 cm high for this named position/finish. Thirty millimetres is the weight-model average material assumption, not maximum projection or independently measured depth.'}
        dim_path = save(cid + '/' + vid + '/owner-face-dimensions.json', dim, 'dimension_decisions')
        weight = common | {'decision_id': cid + ':' + vid + ':conditional-weight:105kg:accept',
            'source_decision_id': shared['decision_id'] + ':' + vid + ':conditional-weight',
            'approved_proposal_ids': [by_field['weight']['proposal_id']], 'approved_specification_items': [copy.deepcopy(by_field['weight'])],
            'accepted_conditional_weight_kg': 105, 'assumptions': shared_record['weight_assumptions'],
            'proposals_approved': False, 'specifications_approved': False, 'partial_field_approval_only': True,
            'actual_mass_established': False, 'status': 'CONDITIONAL WORKING WEIGHT ACCEPTED; ACTUAL MASS AND MATERIAL UNVERIFIED'}
        weight_path = save(cid + '/' + vid + '/conditional-weight-approval.json', weight, 'size_finish_variant_specification_decisions')
        fixing = common | {'decision_id': cid + ':' + vid + ':French-cleat-type:owner-stated',
            'source_decision_id': shared['decision_id'] + ':' + vid + ':fixing-type', 'confirmed_fixing_type': 'French cleat fixings',
            'scope_kind': 'FIXING_TYPE_ONLY', 'complete_fixing_group_approved': False,
            'fixing_count': None, 'fixing_material': None, 'fixing_dimensions': None, 'fixing_positions': None, 'anchors': None, 'tested_load_rating': None}
        fixing_path = save(cid + '/' + vid + '/fixing-type-approval.json', fixing, 'fixing_detail_decisions')
        partials = [x['proposal_id'] for x in proposals if x['owner_confirmed_subfields']]
        target = {'canonical_name': entry['name'], 'size_finish_variant_id': vid, 'identity_confirmed': True,
            'identity_approval': identity_path, 'review_record': entry['latest_review_snapshot'], 'pre_answer_review_record': entry['matching_pre_answer_snapshots'][0],
            'specification_proposals': proposals, 'specifications_approved': False, 'proposals_approved': False, 'physical_specs_verified': False,
            'scope': source['identity_scope'], 'primary_image_id': None, 'reference_image_id': file['id'], 'primary_folder_id': fol['id'],
            'current_dropbox_reference': ref, 'individual_photo_missing': True, 'reference_component_complete_in_context': card['reference_component_complete_in_context'],
            'scene_origin_authenticated': card['scene_origin_authenticated'], 'unique_mould_identity_confirmed': False,
            'owner_face_dimensions_cm': confirmed, 'dimension_approval': dim_path,
            'accepted_conditional_weight_proposal_kg': 105, 'conditional_weight_approval': weight_path, 'actual_weight_kg': None,
            'weight_model_assumptions': shared_record['weight_assumptions'], 'average_material_thickness_is_measured_depth': False,
            'owner_fixing_type': 'French cleat fixings', 'fixing_detail_approval': fixing_path,
            'individual_sale_unit_owner_approved': sandstone, 'sale_unit_quantity': 1,
            'sale_policy_source': snap(policy_path) if sandstone else None,
            'current_production_stock_and_lead_time_verified': False, 'actual_material_verified': False,
            'partially_confirmed_proposal_ids': partials, 'platform_mapping': copy.deepcopy(card['platform_mapping']),
            'exact_standalone_platform_offer_confirmed': False, 'image_gap_assessment_snapshot': snap(card['image_gap_assessment']),
            'missing_photographs': ['Isolated individual component front', 'Rear fixing close-up', 'Calibrated side/depth view'],
            'source_review_snapshot': entry['latest_review_snapshot'], 'workbook_contains_import': False}
        parent = p['reviews'].setdefault(cid, {'identity_confirmed': False, 'specifications_approved': False,
            'physical_specs_verified': False, 'scope': 'Scoped named position/finish references; unique mould identity and physical stock unverified.'})
        assert vid not in parent.setdefault('size_finish_variants', {}); parent['size_finish_variants'][vid] = target
        cp['pending_specification_reviews'].append({'component_id': cid, 'size_finish_variant_id': vid, 'canonical_name': entry['name'],
            'identity_approved': True, 'specifications_approved': False, 'accepted_conditional_proposal_ids': weight['approved_proposal_ids'],
            'pending_fields': [x['field'] for x in proposals if x['field'] != 'weight'], 'partially_confirmed_proposal_ids': partials,
            'actual_weight_confirmation_pending': True, 'actual_depth_and_material_confirmation_pending': True,
            'review_record': entry['latest_review_snapshot'], 'identity_approval': identity_path, 'image_link': card['image_url'], 'folder_link': card['folder_url'],
            'scope': 'Face dimensions80W×240Hcm, conditional105kg estimate and French-cleat type accepted only to stated limits; other details remain pending.'})
        imported.append({'component_id': cid, 'size_finish_variant_id': vid, 'name': entry['name'], 'identity_approval': identity_path,
            'face_dimension_approval': dim_path, 'conditional_weight_approval': weight_path, 'fixing_type_approval': fixing_path,
            'source_decision_id': entry['source_decision_id'], 'partial_groups': len(partials)})
    assert len(imported) == 6 and len(skipped) == 1 and sum(x['partial_groups'] for x in imported) == 15
    policy_record = {'schema_version': 1, 'decision_id': policy['decision_id'] + ':shared-register-import',
        'source_decision_id': policy['decision_id'], 'source_owner_session': policy['owner_session'], 'recorded_utc': turns[policy['user_statement']]['timestamp'],
        'imported_utc': now, 'user_statement': policy['user_statement'], 'source_receipt_snapshot': snap(policy_path),
        'source_receipt_sha256': sources[policy_path]['sha256'], 'authoritative_user_evidence': turns[policy['user_statement']],
        'component_ids': policy['component_ids'], 'size_finish_variant_ids': policy['variant_ids'], 'sale_unit': policy['sale_unit'],
        'scope': policy['scope'], 'physical_specs_verified': False, 'production_or_stock_confirmed': False, 'live_listing_created': False}
    policy_approval = save('LAVA/individual-Sandstone-sale-policy.json', policy_record, 'individual_sale_policy_decisions')
    arrangement_record = {'schema_version': 1, 'decision_id': arrangement['decision_id'] + ':arrangement-face:owner-stated',
        'source_decision_id': arrangement['decision_id'], 'recorded_utc': turns[arrangement['user_statement']]['timestamp'], 'imported_utc': now,
        'user_statement': arrangement['user_statement'], 'source_owner_session': shared['owner_session'],
        'source_receipt_snapshot': snap(arrangement_source), 'source_receipt_sha256': sources[arrangement_source]['sha256'],
        'authoritative_user_evidence': turns[arrangement['user_statement']], 'component_ids': arrangement['component_ids'],
        'size_finish_variant_ids': arrangement['variant_ids'], 'scope_kind': 'WHOLE_ARRANGEMENT_FACE_SIZE',
        'confirmed_arrangement_dimensions_cm': {'height': 240, 'width': 240, 'depth': None},
        'reference_file_id': arrangement['reference_file_id'], 'primary_folder_id': arrangement['reference_folder_id'],
        'scope': 'Owner recollection for the selected three-panel Sandstone arrangement, not a separately measured component or White arrangement.',
        'physical_specs_verified': False, 'source_individual_height_limit_superseded_by_shared_instruction': shared_approval}
    arrangement_approval = save('LAVA/Sandstone-arrangement-face-dimensions.json', arrangement_record, 'arrangement_dimension_decisions')
    u['identity_confirmation_counts'] = identity_counts(u); u['specification_approval_counts'] = specification_counts(u)
    u['dimension_confirmation_counts'] = {'components': len({x['component_id'] for x in u['dimension_decisions']}),
        'face_size_decisions': sum(x.get('scope_kind') != 'COMPLETE_DIMENSION_INSTRUCTION' for x in u['dimension_decisions']),
        'complete_dimension_instruction_decisions': sum(x.get('scope_kind') == 'COMPLETE_DIMENSION_INSTRUCTION' for x in u['dimension_decisions']),
        'individual_dimension_decisions': len(u['dimension_decisions'])}
    assert u['identity_confirmation_counts'] == before['user']['identity_confirmation_counts'] | {
        'explicit_size_finish_variant_names': before['user']['identity_confirmation_counts']['explicit_size_finish_variant_names'] + 6,
        'components_with_any_identity_scope': before['user']['identity_confirmation_counts']['components_with_any_identity_scope'] + 3}
    assert u['specification_approval_counts']['proposal_groups'] == before['user']['specification_approval_counts']['proposal_groups'] + 6
    assert u['specification_approval_counts']['size_finish_variant_approvals'] == before['user']['specification_approval_counts']['size_finish_variant_approvals']
    assert u['dimension_confirmation_counts']['individual_dimension_decisions'] == before['user']['dimension_confirmation_counts']['individual_dimension_decisions'] + 6
    summary = {'recorded_utc': now, 'receipt': rel(receipt_path), 'component_ids': sorted(cids), 'new_finish_identity_receipts': 6,
        'previously_imported_Knight_name_and_dimension_skipped': True, 'owner_face_dimension_scopes': 6,
        'accepted_conditional_weight_groups': 6, 'accepted_weight_kg_each': 105, 'French_cleat_type_scopes': 6,
        'Sandstone_individual_sale_policy_receipts': 1, 'Sandstone_arrangement_face_receipts': 1,
        'new_complete_six_group_approvals': 0, 'Lava_partial_groups_remaining': 15, 'Lava_wholly_unanswered_groups': 15,
        'actual_mass_material_depth_hardware_engineering_and_stock_unverified': True,
        'current_MCP2_Verdigris_Rust_question_preserved': True, 'workbook_export_pending': True}
    supplement = {'import_receipt': rel(receipt_path), 'source_manifest': rel(HERE / 'source-manifest.json'),
        'source_package_sha256': manifest['source_package_sha256'], 'source_field_scope': shared_approval,
        'individual_sale_policy': policy_approval, 'Sandstone_arrangement_face_dimensions': arrangement_approval,
        'reference_names_answered': 6, 'reference_total_is_sculpture_count': False, 'specifications_complete': False,
        'physical_specs_verified': False, 'source_media_coverage': copy.deepcopy(package['photo_review_coverage']),
        'root_current_originals_independently_hash_verified_and_viewed': 3, 'whole_family_live_reaudit_claimed': False,
        'all_six_individual_component_front_photos_missing': True, 'unique_cast_mould_and_White_manufacture_unverified': True}
    p['family_review_progress']['Lava Moon'] = supplement | {'status': 'KNOWN_POSITION_FINISH_NAMES_IMPORTED; PARTIAL_FIELDS_AND_CONDITIONAL_WEIGHTS_PRESERVED'}
    c['family_review_supplements']['Lava Moon'] = copy.deepcopy(supplement)
    for entry in cp['parallel_import_queue']:
        if entry['receipt'] == manifest['source_package']:
            assert not entry['approval_imported']; entry.update({'approval_imported': True,
                'status': 'IMPORTED_EXACT_SCOPES;SIX_NAMES_FACE_SIZES_CONDITIONAL_WEIGHTS_FIXING_TYPES;GAPS_RETAINED',
                'import_receipt': rel(receipt_path), 'imported_utc': now})
    for entry in cp['parallel_owner_reviews']:
        if entry['component_id'] in cids:
            entry.update({'status': 'SEALED OWNER NAMES AND PRECISE FIELD SCOPES IMPORTED; PHYSICAL AND PHOTO GAPS RETAINED', 'import_receipt': rel(receipt_path)})
    cp['last_parallel_import'] = copy.deepcopy(summary)
    cp['next_serialized_parallel_import'].update({'status': 'APPLIED_AND_VERIFIED', 'receipt': rel(receipt_path), 'completed_utc': now})
    cp['completed_serialized_parallel_import'] = copy.deepcopy(cp['next_serialized_parallel_import']); cp['updated_utc'] = now
    p['latest_parallel_import'] = copy.deepcopy(summary)
    c.update({'parallel_import_queue': copy.deepcopy(cp['parallel_import_queue']), 'parallel_owner_reviews': copy.deepcopy(cp['parallel_owner_reviews']),
        'last_parallel_import': copy.deepcopy(summary), 'updated_utc': now})
    counts = u['identity_confirmation_counts']
    c['interactive_review_state'].update({'explicit_identity_confirmations': counts['component_designs'],
        'explicit_size_finish_variant_names_confirmed': counts['explicit_size_finish_variant_names'], 'components_with_any_identity_scope': counts['components_with_any_identity_scope']})
    u['updated_utc'] = p['updated_utc'] = now
    docs['root']['current_component_review'] = copy.deepcopy(c); docs['root']['updated_utc'] = now
    for key, value in before['walkthrough'].items():
        if key.startswith('current_') or key in ['proposed_name', 'question_scope', 'answer_state', 'next_review_after_keep']:
            assert cp[key] == value, key
    for key, value in before['user'].items():
        if isinstance(value, list): assert u[key][:len(value)] == value, key
    assert all(p['reviews'][key] == value for key, value in before['progress']['reviews'].items())
    assert p['offer_photo_bindings'] == before['progress']['offer_photo_bindings']
    assert all(sha(path) == hashes[k] for k, path in paths.items()) and all(sha(Path(path)) == digest for path, digest in protected.items())
    write(HERE / 'before-import.json', {'recorded_utc': now, 'files': {rel(paths[k]): value for k, value in before.items()}, 'protected_sha256': protected})
    for path, value in outputs: write(path, value)
    for k, path in paths.items(): write(path, docs[k]); assert read(path) == docs[k]
    result = {'status': 'APPLIED_AND_VERIFIED', **summary, 'imported': imported, 'skipped': skipped,
        'counts': {'identity': counts, 'specifications': u['specification_approval_counts'], 'dimensions': u['dimension_confirmation_counts']},
        'source_files_frozen': len(manifest['files']), 'exact_owner_turns_verified': 13, 'current_originals_hash_verified_and_viewed': 3,
        'protected_sha256': protected, 'physical_specs_verified': False, 'remote_files_changed': False, 'live_platform_records_changed': False}
    write(receipt_path, result)
    event = {'event_id': 'parallel-import:batch8:2026-10-19', 'event': 'OWNER_LAVA_NAMES_AND_PRECISE_FIELDS_IMPORTED',
        'recorded_utc': now, 'import_receipt': rel(receipt_path), 'new_names': 6, 'new_conditional_weight_groups': 6,
        'complete_specification_approval_inferred': False, 'current_MCP2_Verdigris_Rust_question_preserved': True}
    for path in [REVIEWS / 'identity_review_journal.jsonl', ROOT / 'review_journal.jsonl']:
        with path.open('a') as f: f.write(json.dumps(event, ensure_ascii=False) + '\n')
    print(json.dumps({'status': result['status'], **summary, 'counts': result['counts']}))


if __name__ == '__main__':
    main()
