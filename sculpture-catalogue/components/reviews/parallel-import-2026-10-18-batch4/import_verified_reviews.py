"""Import eighteen names and one conditional weight, with no broader approval."""
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


def main():
    receipt_path = HERE / 'import-receipt.json'
    assert not receipt_path.exists(), 'Already applied; do not duplicate'
    manifest = read(HERE / 'source-manifest.json')
    assert len(manifest['decisions']) == 19
    for f in manifest['files']:
        assert sha(ROOT / f['snapshot']) == f['sha256']
    metadata = read(HERE / 'current-reference-check.json')
    current = {x['request_id']: x for x in metadata['metadata']}
    live = {}
    for d in manifest['decisions']:
        f, fol = current[d['evidence_file_id']]['file'], current[d['folder_id']]['folder']
        e, ef = d['primary_expected'], d['folder_expected']
        assert f['id'] == d['evidence_file_id'] and fol['id'] == d['folder_id']
        assert f['rev'] == e['rev'] and f['size'] == e.get('size', e.get('bytes'))
        assert f['path_display'] == e.get('path_display', e.get('path'))
        assert fol['path_display'] == ef.get('path_display', ef.get('path'))
        assert f['path_display'].rsplit('/', 1)[0] == fol['path_display']
        live[d['source_decision_id']] = {'file_id': f['id'], 'folder_id': fol['id'], 'file_path': f['path_display'],
            'folder_path': fol['path_display'], 'rev': f['rev'], 'bytes': f['size'], 'image_url': d['image_url'],
            'folder_url': d['folder_url'], 'checked_utc': metadata['checked_utc'], 'changed_since_owner_card': False,
            'image_scope': 'Depicted member in pair/series reference only' if d['reference_only'] else 'Owner-reviewed image; original evidence limits retained'}
    paths = {'user': REVIEWS / 'user_classifications.json', 'progress': REVIEWS / 'specification_review_progress.json',
        'walkthrough': REVIEWS / 'walkthrough_checkpoint.json', 'component': ROOT / 'components/checkpoint.json', 'root': ROOT / 'checkpoint.json'}
    docs = {k: read(p) for k, p in paths.items()}
    before = copy.deepcopy(docs)
    digests = {k: sha(p) for k, p in paths.items()}
    u, progress, cp, component = (docs[k] for k in ['user', 'progress', 'walkthrough', 'component'])
    assert cp['current_component_id'] == 'BC-DR-WAVE3' and cp['current_answer_recorded'] and cp['family_first_pass_complete']
    assert docs['root']['current_component_review'] == component
    old_specs = specification_counts(u)
    protected_paths = [ROOT / 'components/evidence/component_register.json', ROOT / cp['register_workbook'],
        ROOT / cp['current_review_record'], ROOT / cp['current_identity_relationship_approval']]
    protected = {str(x): sha(x) for x in protected_paths}
    now = datetime.now(timezone.utc).isoformat()
    write(HERE / 'before-import.json', {'recorded_utc': now, 'files': {rel(paths[k]): v for k, v in before.items()}, 'protected_sha256': protected})
    existing = {x.get('source_decision_id') for values in u.values() if isinstance(values, list) for x in values if isinstance(x, dict)}
    imported = []
    for d in manifest['decisions']:
        assert d['source_decision_id'] not in existing
        cid, vid, kind = d['component_id'], d['variant_id'], d['kind']
        source = read(ROOT / d['receipt'])
        card = read(ROOT / d['review_snapshot'])
        ref = live[d['source_decision_id']]
        parent = progress['reviews'].setdefault(cid, {'identity_confirmed': False, 'specifications_approved': False,
            'physical_specs_verified': False, 'scope': 'Scoped size/finish or depicted member decisions; no whole-family specification approval.'})
        dest = HERE / 'decisions' / cid / vid
        common = {'schema_version': 1, 'component_id': cid, 'size_finish_variant_id': vid, 'canonical_name': d['name'],
            'recorded_utc': d['recorded_utc'], 'imported_utc': now, 'review_number': d['review_number'],
            'user_statement': d['statement'], 'source_owner_session': d['owner_session'], 'source_decision_id': d['source_decision_id'],
            'source_receipt_snapshot': d['receipt'], 'source_receipt_sha256': d['source_receipt_sha256'],
            'proposal_source': d['review_snapshot'], 'proposal_source_sha256': d['pre_answer_review_sha256'],
            'authoritative_user_evidence': d['authoritative_user_evidence'], 'current_dropbox_reference': ref,
            'primary_file_id': None if d['reference_only'] else ref['file_id'],
            'reference_file_id': ref['file_id'] if d['reference_only'] else None,
            'primary_folder_id': ref['folder_id'], 'image_link': ref['image_url'], 'folder_link': ref['folder_url'],
            'physical_specs_verified': False, 'physical_manufacture_confirmed': False,
            'workbook_status': 'Unchanged; local review overlay only'}
        if kind == 'conditional_variant_weight_proposal':
            target = parent['size_finish_variants'][vid]
            ids = source['approved_proposal_ids']
            assert ids == ['BC-FP-LEFT-WHITE-WEIGHT'] and not source['all_specifications_approved']
            matched = [x for x in target['specification_proposals'] if x['proposal_id'] in ids]
            assert len(matched) == 1
            for item in matched:
                item.update({'owner_approved': True, 'working_proposal_accepted': True, 'physical_specs_verified': False,
                    'approval_scope': 'Conditional approximately6kg estimate only; not a measured weight or confirmation of construction assumptions'})
            decision = common | {'decision_id': f'{cid}:{vid}:conditional-weight:accept',
                'status': 'CONDITIONAL SINGLE WORKING WEIGHT ACCEPTED; PHYSICAL MASS UNKNOWN',
                'scope': source['scope'], 'approved_proposal_ids': ids, 'approved_specification_items': copy.deepcopy(matched),
                'approved_details': {'working_weight_kg': 6, 'assumptions': source['assumptions_retained']},
                'proposals_approved': False, 'specifications_approved': False, 'partial_field_approval_only': True,
                'actual_mass_established': False, 'retained_limits': source['weight_basis']}
            output = dest / 'conditional-weight-approval.json'
            write(output, decision)
            u.setdefault('size_finish_variant_specification_decisions', []).append(decision | {'approval_record': rel(output)})
            target.update({'accepted_conditional_weight_proposal_kg': 6, 'conditional_weight_approval': rel(output),
                'actual_weight_kg': None, 'white_face_dimensions_owner_confirmed': False,
                'specifications_approved': False, 'proposals_approved': False})
            pending = [x for x in cp['pending_specification_reviews'] if x.get('component_id') == cid and x.get('size_finish_variant_id') == vid]
            assert len(pending) == 1
            pending[0].update({'accepted_conditional_proposal_ids': ids,
                'pending_fields': [x.get('field', x.get('group')) for x in target['specification_proposals'] if x['proposal_id'] not in ids],
                'actual_weight_confirmation_pending': True})
        else:
            target = parent.setdefault('size_finish_variants', {}).setdefault(vid, {})
            assert not target, (cid, vid)
            items = copy.deepcopy(card['specification_review_items'])
            for x in items:
                x.update({'display': x.get('display', x.get('displayed_detail', x.get('proposal', ''))),
                    'owner_approved': False, 'physical_specs_verified': False})
            scope = source.get('identity_scope', source.get('scope_note', source.get('scope', 'Name and depicted identity only')))
            decision = common | {'decision_id': f'{cid}:{vid}:identity:keep', 'confirmed_name': d['name'],
                'status': 'USER CONFIRMED DEPICTED NAME AND IDENTITY ONLY', 'identity_confirmed': True,
                'scope': scope, 'specifications_approved': False, 'proposals_approved': False, 'approved_proposal_ids': []}
            output = dest / 'identity-approval.json'
            write(output, decision)
            u.setdefault('size_finish_variant_decisions', []).append(decision | {'approval_record': rel(output)})
            target.update({'identity_confirmed': True, 'canonical_name': d['name'], 'size_finish_variant_id': vid,
                'identity_approval': rel(output), 'review_record': d['review_snapshot'], 'reviewed_utc': now,
                'specification_proposals': items, 'specifications_approved': False, 'proposals_approved': False,
                'physical_specs_verified': False, 'scope': scope, 'primary_image_id': decision['primary_file_id'],
                'reference_image_id': decision['reference_file_id'], 'primary_folder_id': ref['folder_id'],
                'current_dropbox_reference': ref, 'platform_mapping': copy.deepcopy(card.get('platform_mapping', card.get('platform_evidence', {}))),
                'missing_photographs': copy.deepcopy(card.get('missing_photographs', [])),
                'individual_photo_missing': d['reference_only'], 'source_conflicts': copy.deepcopy(card.get('source_conflicts', [])),
                'photo_selection_review': copy.deepcopy(card.get('photo_selection_review', source.get('photo_selection_review', {}))),
                'complete_source_review_snapshot': d['review_snapshot'], 'workbook_contains_import': False})
            cp['pending_specification_reviews'].append({'component_id': cid, 'size_finish_variant_id': vid,
                'canonical_name': d['name'], 'identity_approved': True, 'specifications_approved': False,
                'pending_fields': [x.get('field', x.get('group')) for x in items], 'review_record': d['review_snapshot'],
                'identity_approval': rel(output), 'image_link': ref['image_url'], 'folder_link': ref['folder_url'], 'scope': scope})
        imported.append({'component_id': cid, 'size_finish_variant_id': vid, 'kind': kind, 'name': d['name'],
            'approval': rel(output), 'source_receipt': d['source_receipt'], 'source_decision_id': d['source_decision_id']})
    u['identity_confirmation_counts'] = identity_counts(u)
    u['specification_approval_counts'] = specification_counts(u)
    specs = u['specification_approval_counts']
    assert specs['proposal_groups'] == old_specs['proposal_groups'] + 1 == 62
    assert specs['size_finish_variant_approvals'] == old_specs['size_finish_variant_approvals']
    assert specs['component_proposal_groups'] == old_specs['component_proposal_groups']
    assert u['dimension_confirmation_counts'] == before['user']['dimension_confirmation_counts']
    assert u['identity_confirmation_counts']['explicit_size_finish_variant_names'] == before['user']['identity_confirmation_counts']['explicit_size_finish_variant_names'] + 18
    u['updated_utc'] = progress['updated_utc'] = now
    consumed = {x['source_receipt'] for x in manifest['decisions'] + manifest['previously_imported_decisions_skipped']}
    consumed |= {x['source'] for x in manifest['packages']}
    for package in manifest['packages']:
        if not any(x['receipt'] == package['source'] for x in cp['parallel_import_queue']):
            cp['parallel_import_queue'].append({'component_id': None, 'variant_id': None, 'scope_kind': 'REVIEW_IMPORT_PACKAGE',
                'receipt': package['source'], 'receipt_sha256': package['sha256'], 'approval_imported': False, 'recorded_utc': now})
    for x in cp['parallel_import_queue']:
        if x['receipt'] in consumed and not x.get('approval_imported'):
            x.update({'approval_imported': True, 'status': 'IMPORTED WITH EXACT VERIFIED SCOPE; WORKBOOK EXPORT PENDING',
                'import_receipt': rel(receipt_path), 'imported_utc': now})
    cids = sorted({x['component_id'] for x in manifest['decisions']})
    for x in cp['parallel_owner_reviews']:
        if x['component_id'] in cids:
            x.update({'status': 'SEALED FIRST-PASS ANSWERS IMPORTED; SPECIFICATIONS AND PHOTO GAPS RETAINED', 'import_receipt': rel(receipt_path)})
    summary = {'recorded_utc': now, 'receipt': rel(receipt_path), 'component_ids': cids,
        'identity_receipts': 18, 'conditional_single_weight_receipts': 1, 'previously_imported_skipped': 2,
        'new_full_six_group_approvals': 0, 'new_accepted_conditional_proposal_groups': 1,
        'current_DR1_DR3_relationship_answer_preserved': True, 'workbook_export_pending': True}
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
        'explicit_component_layout_names': counts['explicit_component_layout_names'],
        'components_with_any_identity_scope': counts['components_with_any_identity_scope']})
    docs['root']['current_component_review'] = copy.deepcopy(component)
    docs['root']['updated_utc'] = now
    for key, value in before['walkthrough'].items():
        if key.startswith('current_'):
            assert cp[key] == value, key
    for key, value in before['user'].items():
        if isinstance(value, list):
            assert u[key][:len(value)] == value, key
    assert progress['depicted_reference_identity_groups'] == before['progress']['depicted_reference_identity_groups']
    assert all(sha(path) == digests[k] for k, path in paths.items()), 'Shared writer collision'
    assert all(sha(Path(path)) == digest for path, digest in protected.items())
    for key, path in paths.items():
        write(path, docs[key])
        assert read(path) == docs[key]
    assert read(paths['root'])['current_component_review'] == read(paths['component'])
    write(HERE / 'verified-current-references.json', {'checked_utc': metadata['checked_utc'], 'decisions': live})
    result = {'status': 'APPLIED_AND_VERIFIED', **summary, 'imported': imported,
        'counts': {'identity': counts, 'specification': specs}, 'protected_sha256': protected,
        'baseline_model_workbook_and_current_review_unchanged': True, 'physical_specs_verified': False,
        'remote_files_changed': False, 'live_platform_records_changed': False}
    write(receipt_path, result)
    event = {'event_id': 'parallel-import:bounded-batch4:2026-10-18', 'event': 'VERIFIED_OWNER_RECEIPTS_IMPORTED',
        'recorded_utc': now, 'import_receipt': rel(receipt_path), 'identity_receipts': 18,
        'conditional_weight_only': 1, 'full_specification_approval_inferred': False, 'current_DR_same_design_answer_preserved': True}
    for path in [REVIEWS / 'identity_review_journal.jsonl', ROOT / 'review_journal.jsonl']:
        with path.open('a') as f:
            f.write(json.dumps(event, ensure_ascii=False) + '\n')
    print(json.dumps({'status': result['status'], **summary, 'counts': result['counts']}))


if __name__ == '__main__':
    main()
