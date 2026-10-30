"""Apply exactly verified names and one face-size statement; leave all guesses open."""
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


def read(p):
    return json.loads(p.read_text())


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def rel(p):
    return str(p.relative_to(ROOT))


def write(p, value):
    p.parent.mkdir(parents=True, exist_ok=True)
    t = p.with_name(p.name + '.tmp')
    t.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    t.replace(p)


def unchanged_subset(old, new):
    if isinstance(old, dict):
        for k, value in old.items():
            assert k in new
            unchanged_subset(value, new[k])
    else:
        assert old == new


def main():
    receipt_path = HERE / 'import-receipt.json'
    if receipt_path.exists():
        assert read(receipt_path)['status'] == 'APPLIED_AND_VERIFIED'
        print('ALREADY_APPLIED')
        return
    manifest = read(HERE / 'source-manifest.json')
    assert len(manifest['decisions']) == 14
    for f in manifest['files']:
        assert sha(ROOT / f['snapshot']) == f['sha256']
    metadata = read(HERE / 'current-reference-check.json')
    current = {x['request_id']: x for x in metadata['metadata']}
    verified = {}
    for d in manifest['decisions']:
        file, folder = current[d['evidence_file_id']]['file'], current[d['folder_id']]['folder']
        e, ef = d['primary_expected'], d['folder_expected']
        assert file['id'] == d['evidence_file_id'] and folder['id'] == d['folder_id']
        assert file['rev'] == e['rev'] and file['size'] == e.get('size', e.get('bytes'))
        assert file['path_display'] == e.get('path', e.get('path_display'))
        assert folder['path_display'] == ef.get('path', ef.get('path_display'))
        assert file['path_display'].rsplit('/', 1)[0] == folder['path_display']
        verified[d['source_decision_id']] = {'file_id': file['id'], 'folder_id': folder['id'],
            'file_path': file['path_display'], 'folder_path': folder['path_display'], 'rev': file['rev'],
            'bytes': file['size'], 'image_url': d['image_url'], 'folder_url': d['folder_url'],
            'checked_utc': metadata['checked_utc'], 'changed_since_owner_card': False,
            'image_scope': 'Pair reference; left depicted design only' if d['reference_only'] else 'Owner-reviewed primary; completeness/provenance retain source limits'}
    paths = {'user': REVIEWS / 'user_classifications.json', 'progress': REVIEWS / 'specification_review_progress.json',
             'walkthrough': REVIEWS / 'walkthrough_checkpoint.json', 'component': ROOT / 'components/checkpoint.json', 'root': ROOT / 'checkpoint.json'}
    docs = {k: read(p) for k, p in paths.items()}
    user, progress, cp, component = (docs[k] for k in ['user', 'progress', 'walkthrough', 'component'])
    assert cp['current_size_finish_variant_id'] == 'DR-WAVES-BLUE-VERDIGRIS' and cp['current_answer_recorded']
    assert docs['root']['current_component_review'] == component
    now = datetime.now(timezone.utc).isoformat()
    active_keys = [k for k in cp if k.startswith('current_')] + ['state', 'answer_state', 'question_scope', 'proposed_name',
        'primary_image', 'containing_folder', 'next_review_after_keep', 'active_family', 'family_review_order', 'last_identity_approval']
    active = {k: copy.deepcopy(cp[k]) for k in active_keys}
    old_lists = {k: copy.deepcopy(v) for k, v in user.items() if isinstance(v, list)}
    old_reviews = copy.deepcopy(progress['reviews'])
    old_specs = copy.deepcopy(user['specification_approval_counts'])
    shared_hashes = {k: sha(p) for k, p in paths.items()}
    protected_paths = [ROOT / 'components/evidence/component_register.json', ROOT / cp['register_workbook'],
                       ROOT / cp['current_review_record'], ROOT / cp['last_identity_approval']]
    protected = {str(p): sha(p) for p in protected_paths}
    write(HERE / 'before-import.json', {'recorded_utc': now, 'files': {rel(paths[k]): v for k, v in docs.items()},
          'protected_sha256': protected, 'shared_before_sha256': shared_hashes})
    imported = []
    for d in manifest['decisions']:
        kind, cid, variant = d['kind'], d['component_id'], d.get('variant_id')
        live = verified[d['source_decision_id']]
        parent = progress['reviews'].setdefault(cid, {'identity_confirmed': False, 'specifications_approved': False,
            'physical_specs_verified': False, 'scope': 'Parent unchanged; each reviewed design/finish/build is scoped separately.'})
        slug = d.get('component_layout_id') or d.get('build_variant_id') or variant or 'component'
        dest = HERE / 'decisions' / cid / slug
        if kind == 'variant_face_dimensions':
            decision_id = f'{cid}:{variant}:dimensions:owner-stated'
            decision = {'schema_version': 1, 'decision_id': decision_id, 'component_id': cid,
                'size_finish_variant_id': variant, 'canonical_name': d['name'], 'recorded_utc': d['recorded_utc'],
                'imported_utc': now, 'user_statement': d['statement'], 'source_decision_id': d['source_decision_id'],
                'source_owner_session': d['owner_session'], 'status': 'OWNER STATED FACE SIZE; UNIT INTERPRETED FROM CATALOGUE CONTEXT',
                'confirmed_dimensions_cm': d['dimensions_cm'], 'unit_interpretation': d['unit_interpretation'],
                'scope': 'Left Verdigris depicted design face only. Depth, White/right sizes, manufacture, mould and actual measurement remain unconfirmed.',
                'physical_specs_verified': False, 'physical_manufacture_confirmed': False,
                'primary_file_id': None, 'reference_file_id': live['file_id'], 'primary_folder_id': live['folder_id'],
                'current_dropbox_reference': live, 'image_link': live['image_url'], 'folder_link': live['folder_url'],
                'source_receipt_snapshot': d['receipt'], 'authoritative_user_evidence': d['authoritative_user_evidence']}
            output = dest / 'dimension-approval.json'
            assert not any(x['decision_id'] == decision_id for x in user['dimension_decisions'])
            write(output, decision)
            user['dimension_decisions'].append(decision | {'approval_record': rel(output)})
            parent['size_finish_variants'][variant].update({'owner_face_dimensions_cm': d['dimensions_cm'],
                'dimension_approval': rel(output), 'dimension_unit_interpretation': d['unit_interpretation']})
        else:
            v = read(ROOT / d['review_snapshot'])
            if kind == 'component_layout_identity':
                list_name, group, key_field = 'component_layout_identity_decisions', 'component_layouts', 'component_layout_id'
                key = d['component_layout_id']
            elif kind == 'build_configuration_identity':
                list_name, group, key_field = 'build_variant_identity_decisions', 'build_variants', 'build_variant_id'
                key = d['build_variant_id']
            else:
                assert kind in ['size_finish_variant_identity', 'depicted_design_finish_identity']
                list_name, group, key_field, key = 'size_finish_variant_decisions', 'size_finish_variants', 'size_finish_variant_id', variant
            decision_id = f'{cid}:{key}:identity:keep'
            target_list = user.setdefault(list_name, [])
            assert not any(x['decision_id'] == decision_id for x in target_list)
            target = parent.setdefault(group, {}).setdefault(key, {})
            assert not target, (cid, key)
            items = copy.deepcopy(v['specification_review_items'])
            for item in items:
                item.update({'display': item.get('display', item.get('displayed_detail', item.get('proposal', ''))),
                             'owner_approved': False, 'physical_specs_verified': False})
            scope = 'Depicted design from explicitly labelled pair reference; no complete isolated primary or physical manufacture established.' if d['reference_only'] else 'Only this owner-reviewed depicted name/design/finish/build. Six specifications, manufacture, mould equivalence, stock and exact platform matching retain their source limits.'
            decision = {'schema_version': 1, 'decision_id': decision_id, 'component_id': cid, key_field: key,
                'canonical_name': d['name'], 'confirmed_name': d['name'], 'recorded_utc': d['recorded_utc'], 'imported_utc': now,
                'review_number': d['review_number'], 'status': 'USER CONFIRMED DEPICTED NAME AND IDENTITY ONLY',
                'identity_confirmed': True, 'user_statement': d['statement'], 'source_owner_session': d['owner_session'],
                'source_decision_id': d['source_decision_id'], 'scope': scope, 'specifications_approved': False,
                'proposals_approved': False, 'approved_proposal_ids': [], 'physical_specs_verified': False,
                'physical_manufacture_confirmed': False, 'primary_file_id': None if d['reference_only'] else live['file_id'],
                'reference_file_id': live['file_id'] if d['reference_only'] else None, 'evidence_file_id': live['file_id'],
                'primary_folder_id': live['folder_id'], 'current_dropbox_reference': live,
                'image_link': live['image_url'], 'folder_link': live['folder_url'], 'source_receipt_snapshot': d['receipt'],
                'proposal_source': d['review_snapshot'], 'proposal_source_sha256': d['pre_answer_review_sha256'],
                'source_receipt_sha256': d['source_receipt_sha256'], 'authoritative_user_evidence': d['authoritative_user_evidence'],
                'workbook_status': 'Unchanged; local review overlay only'}
            if kind == 'component_layout_identity':
                decision.update({'individual_component_record_required': True,
                    'source_parent_bucket': cid, 'scope_kind': 'INDIVIDUAL COMPONENT LAYOUT; NOT A BUILD OPTION',
                    'catalogue_component_id_reconciliation_pending': True})
            output = dest / 'identity-approval.json'
            write(output, decision)
            target_list.append(decision | {'approval_record': rel(output)})
            target.update({'identity_confirmed': True, 'canonical_name': d['name'], key_field: key,
                'identity_approval': rel(output), 'review_record': d['review_snapshot'], 'reviewed_utc': now,
                'specification_proposals': items, 'specifications_approved': False, 'proposals_approved': False,
                'physical_specs_verified': False, 'scope': scope, 'primary_image_id': decision['primary_file_id'],
                'reference_image_id': decision['reference_file_id'], 'primary_folder_id': live['folder_id'],
                'current_dropbox_reference': live, 'platform_mapping': copy.deepcopy(v.get('platform_mapping', v.get('platform_evidence', {}))),
                'missing_photographs': copy.deepcopy(v.get('missing_photographs', [])),
                'source_conflicts': copy.deepcopy(v.get('source_conflicts', [])), 'source_scope_snapshot': d['review_snapshot'],
                'individual_photo_missing': bool(d['reference_only']) or 'Bronze' in d['name'],
                'unresolved_alternative_images': copy.deepcopy(v.get('unresolved_alternative_images', [])),
                'photo_selection_review': copy.deepcopy(v.get('photo_selection_review', {})),
                'individual_identity_review': copy.deepcopy(v.get('individual_identity_review', {})),
                'workbook_contains_import': False})
            cp['pending_specification_reviews'].append({'component_id': cid, key_field: key, 'canonical_name': d['name'],
                'identity_approved': True, 'specifications_approved': False, 'pending_fields': [x.get('field', x.get('group')) for x in items],
                'review_record': d['review_snapshot'], 'identity_approval': rel(output), 'image_link': live['image_url'],
                'folder_link': live['folder_url'], 'scope': scope})
        imported.append({'component_id': cid, 'kind': kind, 'name': d['name'], 'approval': rel(output),
                         'source_receipt': d['source_receipt'], 'source_decision_id': d['source_decision_id']})
    assert len(user['component_layout_identity_decisions']) == 2
    assert {x['component_layout_id'] for x in user['component_layout_identity_decisions']} == {'SPICE-PANEL-1-WHITE', 'SPICE-PANEL-2-WHITE'}
    user['identity_confirmation_counts'] = identity_counts(user)
    user['specification_approval_counts'] = specification_counts(user)
    assert user['specification_approval_counts'] == old_specs
    user['dimension_confirmation_counts'] = {'components': len({x['component_id'] for x in user['dimension_decisions']}),
                                           'face_size_decisions': len(user['dimension_decisions'])}
    user['updated_utc'] = progress['updated_utc'] = now
    progress['latest_parallel_import'] = rel(receipt_path)
    consumed = {x['receipt'] for x in manifest['queue_entries']}
    for x in cp['parallel_import_queue']:
        if x['receipt'] in consumed:
            x.update({'approval_imported': True, 'status': 'IMPORTED WITH EXACT VERIFIED SCOPE; WORKBOOK EXPORT PENDING',
                      'import_receipt': rel(receipt_path), 'imported_utc': now})
    cids = sorted({x['component_id'] for x in manifest['decisions']})
    for lane in cp['parallel_owner_reviews']:
        if lane['component_id'] in cids:
            lane.update({'status': 'RECEIVED OWNER ANSWERS IMPORTED; OTHER VARIANTS AND SPECIFICATION GAPS MAY REMAIN',
                         'import_receipt': rel(receipt_path)})
    summary = {'recorded_utc': now, 'receipt': rel(receipt_path), 'component_ids': cids, 'identity_receipts': 13,
               'dimension_receipts': 1, 'new_specification_group_approvals': 0, 'active_review_preserved': True,
               'distinct_spice_component_layouts_preserved': 2, 'workbook_export_pending': True}
    cp['last_parallel_import'] = summary
    cp['next_serialized_parallel_import'].update({'status': 'APPLIED_AND_VERIFIED', 'receipt': rel(receipt_path),
        'completed_utc': now, 'bounded_queue_cutoff_utc': manifest['cutoff_utc']})
    cp['completed_serialized_parallel_import'] = copy.deepcopy(cp['next_serialized_parallel_import'])
    cp['updated_utc'] = now
    component.update({'parallel_import_queue': copy.deepcopy(cp['parallel_import_queue']),
        'parallel_owner_reviews': copy.deepcopy(cp['parallel_owner_reviews']), 'last_parallel_import': summary, 'updated_utc': now})
    counts = user['identity_confirmation_counts']
    component['interactive_review_state'].update({'explicit_identity_confirmations': counts['component_designs'],
        'explicit_size_finish_variant_names_confirmed': counts['explicit_size_finish_variant_names'],
        'explicit_build_variant_names': len(user.get('build_variant_identity_decisions', [])),
        'explicit_component_layout_names': counts['explicit_component_layout_names'],
        'components_with_any_identity_scope': counts['components_with_any_identity_scope']})
    docs['root']['current_component_review'] = copy.deepcopy(component)
    assert {k: cp[k] for k in active_keys} == active
    for k, old in old_lists.items():
        assert user[k][:len(old)] == old
    unchanged_subset(old_reviews, progress['reviews'])
    assert all(sha(p) == shared_hashes[k] for k, p in paths.items()), 'Shared writer collision'
    assert all(sha(Path(p)) == digest for p, digest in protected.items())
    for k, p in paths.items():
        write(p, docs[k])
        assert read(p) == docs[k]
    write(HERE / 'verified-current-references.json', {'checked_utc': metadata['checked_utc'], 'decisions': verified})
    receipt = {'status': 'APPLIED_AND_VERIFIED', **summary, 'imported': imported,
        'counts': {'identity': counts, 'specification': user['specification_approval_counts'], 'dimensions': user['dimension_confirmation_counts']},
        'protected_sha256': protected, 'source_model_workbook_unchanged': True, 'physical_specs_verified': False,
        'remote_files_changed': False, 'live_platform_records_changed': False}
    write(receipt_path, receipt)
    event = {'event_id': 'parallel-import:bounded-batch3:2026-10-17', 'event': 'VERIFIED_OWNER_RECEIPTS_IMPORTED',
             'recorded_utc': now, 'import_receipt': rel(receipt_path), 'identity_receipts': 13, 'dimension_receipts': 1,
             'specification_approval_inferred': False, 'current_component_id': 'BC-DR-WAVE1', 'current_answer_changed': False}
    for p in [REVIEWS / 'identity_review_journal.jsonl', ROOT / 'review_journal.jsonl']:
        with p.open('a') as f:
            f.write(json.dumps(event, ensure_ascii=False) + '\n')
    print(json.dumps(receipt['counts'], ensure_ascii=False))


if __name__ == '__main__':
    main()
