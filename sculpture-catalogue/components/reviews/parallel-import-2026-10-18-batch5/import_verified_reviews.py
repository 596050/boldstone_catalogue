"""Apply eight verified owner receipts, keeping partial Gleneagles instructions partial."""
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


def write(p, value):
    p.parent.mkdir(parents=True, exist_ok=True)
    t = p.with_name(p.name + '.tmp')
    t.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    t.replace(p)


def subset(old, new):
    if isinstance(old, dict):
        for key, value in old.items():
            assert key in new
            subset(value, new[key])
    else:
        assert old == new


def main():
    receipt_path = HERE / 'import-receipt.json'
    assert not receipt_path.exists(), 'Already applied'
    manifest = read(HERE / 'source-manifest.json')
    assert len(manifest['decisions']) == 8
    for f in manifest['files']:
        assert sha(ROOT / f['snapshot']) == f['sha256']
    metadata = read(HERE / 'current-reference-check.json')
    refs = {x['request_id']: x for x in metadata['metadata']}
    live = {}
    for d in manifest['decisions']:
        f, folder = refs[d['evidence_file_id']]['file'], refs[d['folder_id']]['folder']
        old, old_folder = d['primary_expected'], d['folder_expected']
        assert f['rev'] == old['rev'] and f['size'] == old.get('size', old.get('bytes'))
        assert f['path_display'] == old.get('path', old.get('path_display'))
        assert folder['path_display'] == old_folder.get('path', old_folder.get('path_display'))
        assert f['path_display'].rsplit('/', 1)[0] == folder['path_display']
        live[d['source_decision_id']] = {'file_id': f['id'], 'folder_id': folder['id'], 'file_path': f['path_display'],
            'folder_path': folder['path_display'], 'rev': f['rev'], 'bytes': f['size'], 'image_url': d['image_url'],
            'folder_url': d['folder_url'], 'checked_utc': metadata['checked_utc'], 'changed_since_owner_card': False,
            'scope': 'Owner-reviewed group/position or project reference; isolated front and physical manufacture retain source limits'}
    paths = {'user': REVIEWS / 'user_classifications.json', 'progress': REVIEWS / 'specification_review_progress.json',
        'walkthrough': REVIEWS / 'walkthrough_checkpoint.json', 'component': ROOT / 'components/checkpoint.json', 'root': ROOT / 'checkpoint.json'}
    docs = {k: read(p) for k, p in paths.items()}
    before = copy.deepcopy(docs)
    hashes = {k: sha(p) for k, p in paths.items()}
    u, progress, cp, component = (docs[k] for k in ['user', 'progress', 'walkthrough', 'component'])
    assert cp['current_component_id'] == 'BC-FACET-MOUND' and cp['current_answer_recorded']
    assert cp['next_serialized_parallel_import']['trigger'] == 'AFTER_FACETED_MOUND_FIRST_PASS_BEFORE_MAIN_REVIEW53'
    assert docs['root']['current_component_review'] == component
    old_spec_counts = specification_counts(u)
    existing = {x.get('source_decision_id') for values in u.values() if isinstance(values, list) for x in values if isinstance(x, dict)}
    assert not any(d['source_decision_id'] in existing for d in manifest['decisions'])
    protected = {str(p): sha(p) for p in [ROOT / 'components/evidence/component_register.json', ROOT / cp['register_workbook'],
        ROOT / cp['current_review_record'], ROOT / cp['last_identity_approval']]}
    now = datetime.now(timezone.utc).isoformat()
    write(HERE / 'before-import.json', {'recorded_utc': now, 'files': {rel(paths[k]): v for k, v in before.items()}, 'protected_sha256': protected})
    outputs = []

    def common(d):
        ref = live[d['source_decision_id']]
        return {'schema_version': 1, 'recorded_utc': d['recorded_utc'], 'imported_utc': now,
            'user_statement': d['statement'], 'source_owner_session': d['owner_session'], 'source_decision_id': d['source_decision_id'],
            'source_receipt_snapshot': d['receipt'], 'source_receipt_sha256': d['source_receipt_sha256'],
            'proposal_source': d['review_snapshot'], 'proposal_source_sha256': d['pre_answer_review_sha256'],
            'authoritative_user_evidence': d['authoritative_user_evidence'], 'current_dropbox_reference': ref,
            'primary_file_id': None, 'reference_file_id': ref['file_id'], 'primary_folder_id': ref['folder_id'],
            'image_link': ref['image_url'], 'folder_link': ref['folder_url'], 'physical_specs_verified': False,
            'workbook_status': 'Unchanged; local review overlay only'}

    def save(filename, decision, list_name):
        path = HERE / 'decisions' / filename
        assert not any(x.get('decision_id') == decision['decision_id'] for x in u.get(list_name, []))
        write(path, decision)
        u.setdefault(list_name, []).append(decision | {'approval_record': rel(path)})
        outputs.append({'decision_id': decision['decision_id'], 'component_id': decision.get('component_id'),
            'kind': list_name, 'approval': rel(path), 'source_decision_id': decision['source_decision_id']})
        return rel(path)

    def pending(cid, vid):
        values = [x for x in cp['pending_specification_reviews'] if x['component_id'] == cid and x.get('size_finish_variant_id') == vid]
        assert len(values) == 1
        return values[0]

    for d in sorted(manifest['decisions'], key=lambda x: x['kind'] != 'depicted_position_identity'):
        source, card = read(ROOT / d['receipt']), read(ROOT / d['review_snapshot'])
        kind, base = d['kind'], common(d)
        if kind == 'depicted_position_identity':
            cid, vid = d['component_id'], d['variant_id']
            parent = progress['reviews'].setdefault(cid, {'identity_confirmed': False, 'specifications_approved': False,
                'physical_specs_verified': False, 'scope': 'Individually named depicted position/finish, retaining reference-only and physical specification limits.'})
            target = parent.setdefault('size_finish_variants', {}).setdefault(vid, {})
            assert not target
            items = copy.deepcopy(card['specification_review_items'])
            assert len(items) == 6
            for item in items:
                item.update({'display': item.get('display', item.get('displayed_detail', item.get('proposal', ''))),
                    'owner_approved': False, 'physical_specs_verified': False})
            decision = base | {'decision_id': f'{cid}:{vid}:identity:keep', 'component_id': cid,
                'size_finish_variant_id': vid, 'canonical_name': d['name'], 'confirmed_name': d['name'],
                'identity_confirmed': True, 'status': 'USER CONFIRMED DEPICTED NAME/POSITION ONLY',
                'scope': source.get('identity_scope', source.get('scope', 'Depicted name and position only; no complete specification approval')),
                'specifications_approved': False, 'proposals_approved': False, 'approved_proposal_ids': [],
                'physical_manufacture_confirmed': False, 'unique_mould_identity_confirmed': False}
            approval = save(f'{cid}/{vid}/identity-approval.json', decision, 'size_finish_variant_decisions')
            target.update({'size_finish_variant_id': vid, 'canonical_name': d['name'], 'identity_confirmed': True,
                'identity_approval': approval, 'review_record': d['review_snapshot'], 'specification_proposals': items,
                'specifications_approved': False, 'proposals_approved': False, 'physical_specs_verified': False,
                'primary_image_id': None, 'reference_image_id': d['evidence_file_id'], 'primary_folder_id': d['folder_id'],
                'current_dropbox_reference': base['current_dropbox_reference'], 'individual_photo_missing': True,
                'platform_mapping': copy.deepcopy(card.get('platform_mapping', {})), 'source_conflicts': copy.deepcopy(card.get('source_conflicts', [])),
                'complete_source_review_snapshot': d['review_snapshot'], 'scope': decision['scope'], 'workbook_contains_import': False})
            cp['pending_specification_reviews'].append({'component_id': cid, 'size_finish_variant_id': vid,
                'canonical_name': d['name'], 'identity_approved': True, 'specifications_approved': False,
                'pending_fields': [x.get('field', x.get('group')) for x in items], 'review_record': d['review_snapshot'],
                'identity_approval': approval, 'image_link': base['image_link'], 'folder_link': base['folder_link']})
        elif kind == 'gleneagles_four_face_and_overall_dimensions':
            for member in source['components']:
                cid, vid = member['component_id'], member['variant_id']
                target = progress['reviews'][cid]['size_finish_variants'][vid]
                face = {'height': 35, 'width': 35, 'depth': None}
                decision = base | {'decision_id': f'{cid}:{vid}:face:owner-stated:35x35', 'component_id': cid,
                    'size_finish_variant_id': vid, 'canonical_name': target['canonical_name'], 'confirmed_dimensions_cm': face,
                    'status': 'OWNER STATED FACE SIZE; DEPTH PENDING', 'scope_kind': 'INDIVIDUAL_FACE_SIZE',
                    'unit_interpretation': source['unit_basis'], 'scope': source['scope'],
                    'specifications_approved': False, 'physical_measurement_independently_verified': False}
                approval = save(f'{cid}/{vid}/face-dimension-approval.json', decision, 'dimension_decisions')
                target.update({'owner_face_dimensions_cm': face, 'dimension_approval': approval})
                item = next(x for x in target['specification_proposals'] if x['proposal_id'].endswith('-DIMENSIONS'))
                item.update({'display': '35×35cm face — owner instructed; depth unconfirmed', 'owner_approved': False,
                    'owner_confirmed_subfields': ['height', 'width'], 'dimension_group_complete': False})
                pending(cid, vid).update({'owner_face_dimensions_cm': face, 'dimension_approval': approval, 'depth_pending': True})
            arrangement = base | {'decision_id': 'GLENEAGLES:FOUR-WHITE:OVERALL:70x70:owner-stated',
                'family': 'Gleneagles Vine and Tendril', 'component_ids': [x['component_id'] for x in source['components']],
                'status': 'OWNER STATED WHOLE ARRANGEMENT FACE SIZE', 'overall_dimensions_cm': source['overall'],
                'scope': 'Overall70×70cmowner instruction only; no component depth, mounting gaps or physical measurement inferred.',
                'specifications_approved': False}
            save('GLENEAGLES/overall-dimension-approval.json', arrangement, 'arrangement_dimension_decisions')
        elif kind == 'gleneagles_four_fixing_types':
            for member in source['components']:
                cid, vid = member['component_id'], member['variant_id']
                target = progress['reviews'][cid]['size_finish_variants'][vid]
                decision = base | {'decision_id': f'{cid}:{vid}:fixing-type:keyhole:owner-stated', 'component_id': cid,
                    'size_finish_variant_id': vid, 'canonical_name': target['canonical_name'], 'fixing_type': 'keyhole',
                    'count_per_panel': None, 'hardware_material': None, 'position': None, 'load_rating': None,
                    'status': 'OWNER STATED FIXING TYPE ONLY', 'scope': source['scope_basis'], 'specifications_approved': False,
                    'complete_fixing_group_approved': False, 'physical_hardware_independently_verified': False}
                approval = save(f'{cid}/{vid}/fixing-type-approval.json', decision, 'fixing_detail_decisions')
                target.update({'owner_fixing_type': 'keyhole', 'fixing_detail_approval': approval})
                item = next(x for x in target['specification_proposals'] if x['proposal_id'].endswith('-FIXING'))
                item.update({'display': 'Keyhole fixings — owner-stated type; count, position, material and rated load unknown',
                    'owner_approved': False, 'owner_confirmed_subfields': ['fixing_type'], 'fixing_group_complete': False})
                pending(cid, vid).update({'owner_fixing_type': 'keyhole', 'fixing_detail_approval': approval, 'fixing_group_complete': False})
        else:
            assert kind == 'knightsbridge_complete_dimension_instruction'
            cid, vid = 'BC-KNIGHT', 'KNIGHT-WHITE'
            target = progress['reviews'][cid]['size_finish_variants'][vid]
            decision = base | {'decision_id': f'{cid}:{vid}:dimensions:owner-stated:100x100x50', 'component_id': cid,
                'size_finish_variant_id': vid, 'canonical_name': target['canonical_name'],
                'status': 'OWNER STATED COMPLETE CATALOGUE DIMENSION INSTRUCTION; AXES CONTEXTUAL',
                'scope_kind': 'COMPLETE_DIMENSION_INSTRUCTION', 'owner_dimensions_cm': [100, 100, 50],
                'confirmed_dimensions_cm': {'square_side_a': 100, 'square_side_b': 100, 'depth': 50},
                'dimension_order': source['dimension_order'], 'axis_interpretation': source['normalization_basis'],
                'axis_interpretation_is_independent_measurement': False,
                'scope': 'Owner1metre squared by50cmdeep instruction for the square project fountain block. Retain footprint/body interpretation from that context; no transfer to upright wall panels, engineering drawing or measured physical object.',
                'specifications_approved': False, 'physical_measurement_independently_verified': False}
            approval = save(f'{cid}/{vid}/dimension-approval.json', decision, 'dimension_decisions')
            item = next(x for x in target['specification_proposals'] if x['proposal_id'] == 'BC-KNIGHT-WHITE-DIMENSIONS')
            item.update({'owner_approved': True, 'owner_confirmed': True, 'physical_specs_verified': False,
                'display': '100×100cm square fountain block ×50cm body depth — owner instruction; not independently measured',
                'approval_scope': decision['scope']})
            spec = decision | {'decision_id': f'{cid}:{vid}:dimension-proposal:owner-accepted',
                'approved_proposal_ids': ['BC-KNIGHT-WHITE-DIMENSIONS'], 'approved_specification_items': [copy.deepcopy(item)],
                'proposals_approved': False, 'specifications_approved': False, 'single_group_only': True,
                'approved_details': {'owner_dimensions_cm': [100, 100, 50], 'dimension_order': source['dimension_order']}}
            spec_approval = save(f'{cid}/{vid}/dimension-group-approval.json', spec, 'size_finish_variant_specification_decisions')
            target.update({'owner_dimensions_cm': [100, 100, 50], 'dimension_order': source['dimension_order'],
                'dimension_approval': approval, 'dimension_group_approval': spec_approval,
                'specifications_approved': False, 'proposals_approved': False})
            pending(cid, vid).update({'owner_dimensions_cm': [100, 100, 50], 'dimension_approval': approval,
                'accepted_proposal_ids': ['BC-KNIGHT-WHITE-DIMENSIONS'],
                'pending_fields': [x.get('field', x.get('group')) for x in target['specification_proposals'] if x['proposal_id'] != 'BC-KNIGHT-WHITE-DIMENSIONS']})
    assert len(outputs) == 16
    u['identity_confirmation_counts'] = identity_counts(u)
    u['specification_approval_counts'] = specification_counts(u)
    u['dimension_confirmation_counts'] = {'components': len({x['component_id'] for x in u['dimension_decisions']}),
        'face_size_decisions': sum(x.get('scope_kind') != 'COMPLETE_DIMENSION_INSTRUCTION' for x in u['dimension_decisions']),
        'complete_dimension_instruction_decisions': sum(x.get('scope_kind') == 'COMPLETE_DIMENSION_INSTRUCTION' for x in u['dimension_decisions']),
        'individual_dimension_decisions': len(u['dimension_decisions'])}
    assert u['dimension_confirmation_counts'] == {'components': 13, 'face_size_decisions': 12, 'complete_dimension_instruction_decisions': 1, 'individual_dimension_decisions': 13}
    assert u['specification_approval_counts']['proposal_groups'] == old_spec_counts['proposal_groups'] + 1 == 63
    assert u['specification_approval_counts']['size_finish_variant_approvals'] == old_spec_counts['size_finish_variant_approvals']
    assert u['identity_confirmation_counts']['explicit_size_finish_variant_names'] == 61
    assert len(u['fixing_detail_decisions']) == 4 and len(u['arrangement_dimension_decisions']) == 1
    u['updated_utc'] = progress['updated_utc'] = now
    progress['latest_parallel_import'] = rel(receipt_path)
    consumed = {x['receipt'] for x in manifest['queue_entries']}
    for x in cp['parallel_import_queue']:
        if x['receipt'] in consumed:
            x.update({'approval_imported': True, 'status': 'IMPORTED WITH EXACT VERIFIED SCOPE; WORKBOOK EXPORT PENDING',
                'import_receipt': rel(receipt_path), 'imported_utc': now})
    for lane in cp['parallel_owner_reviews']:
        if lane['component_id'].startswith('BC-GLEN-'):
            lane.update({'status': 'SEALED FIRST-PASS NAMES AND PARTIAL INSTRUCTIONS IMPORTED; ALL24GROUPS RETAIN GAPS', 'import_receipt': rel(receipt_path)})
        elif lane['component_id'] == 'BC-KNIGHT':
            lane.update({'status': 'RECEIVED NAME AND DIMENSION INSTRUCTION IMPORTED; LANE PACKAGE STILL IN PROGRESS', 'import_receipt': rel(receipt_path)})
    summary = {'recorded_utc': now, 'receipt': rel(receipt_path), 'source_owner_receipts': 8, 'new_name_receipts': 5,
        'Gleneagles_individual_faces': 4, 'Gleneagles_partial_fixing_types': 4, 'Gleneagles_overall_face_instruction': 1,
        'Knight_complete_dimension_instruction': 1, 'new_full_six_group_approvals': 0,
        'new_accepted_single_proposal_groups': 1, 'current_Faceted_Mound_answer_preserved': True, 'workbook_export_pending': True}
    cp['last_parallel_import'] = summary
    cp['next_serialized_parallel_import'].update({'status': 'APPLIED_AND_VERIFIED', 'receipt': rel(receipt_path),
        'completed_utc': now, 'bounded_queue_cutoff_utc': manifest['cutoff_utc']})
    cp['completed_serialized_parallel_import'] = copy.deepcopy(cp['next_serialized_parallel_import'])
    cp['next_review_after_keep']['requires_pending_parallel_import'] = False
    cp['updated_utc'] = now
    component.update({'parallel_import_queue': copy.deepcopy(cp['parallel_import_queue']),
        'parallel_owner_reviews': copy.deepcopy(cp['parallel_owner_reviews']), 'last_parallel_import': summary, 'updated_utc': now})
    counts = u['identity_confirmation_counts']
    component['interactive_review_state'].update({'explicit_identity_confirmations': counts['component_designs'],
        'explicit_size_finish_variant_names_confirmed': counts['explicit_size_finish_variant_names'],
        'components_with_any_identity_scope': counts['components_with_any_identity_scope']})
    docs['root']['current_component_review'] = copy.deepcopy(component)
    docs['root']['updated_utc'] = now
    for key, value in before['walkthrough'].items():
        if key.startswith('current_'):
            assert cp[key] == value
    for key, values in before['user'].items():
        if isinstance(values, list):
            assert u[key][:len(values)] == values
    subset(before['progress']['reviews'], progress['reviews'])
    assert cp.get('parallel_evidence_flags') == before['walkthrough'].get('parallel_evidence_flags')
    assert all(sha(path) == hashes[key] for key, path in paths.items()), 'Shared writer collision'
    assert all(sha(Path(path)) == digest for path, digest in protected.items())
    for key, path in paths.items():
        write(path, docs[key])
        assert read(path) == docs[key]
    assert read(paths['root'])['current_component_review'] == read(paths['component'])
    write(HERE / 'verified-current-references.json', {'checked_utc': metadata['checked_utc'], 'receipts': live})
    receipt = {'status': 'APPLIED_AND_VERIFIED', **summary, 'imported': outputs, 'protected_sha256': protected,
        'counts': {'identity': counts, 'specification': u['specification_approval_counts'], 'dimensions': u['dimension_confirmation_counts']},
        'baseline_model_workbook_unchanged': True, 'physical_specs_verified': False, 'remote_files_changed': False, 'live_platform_records_changed': False}
    write(receipt_path, receipt)
    event = {'event_id': 'parallel-import:bounded-batch5:2026-10-18', 'event': 'VERIFIED_OWNER_RECEIPTS_IMPORTED',
        'recorded_utc': now, 'import_receipt': rel(receipt_path), 'source_owner_receipts': 8,
        'new_names': 5, 'partial_face_and_fixing_instructions_preserved': True, 'new_full_six_group_approvals': 0}
    for path in [REVIEWS / 'identity_review_journal.jsonl', ROOT / 'review_journal.jsonl']:
        with path.open('a') as f:
            f.write(json.dumps(event, ensure_ascii=False) + '\n')
    print(json.dumps({'status': receipt['status'], **summary, 'counts': receipt['counts']}))


if __name__ == '__main__':
    main()
