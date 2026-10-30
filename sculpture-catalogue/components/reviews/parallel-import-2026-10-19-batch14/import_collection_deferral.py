"""Record an owner collection-only deferral without creating a component Keep."""
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
    paths = {'user': REVIEWS / 'user_classifications.json', 'progress': REVIEWS / 'specification_review_progress.json',
             'walkthrough': REVIEWS / 'walkthrough_checkpoint.json', 'component': ROOT / 'components/checkpoint.json',
             'root': ROOT / 'checkpoint.json'}
    docs = {key: read(path) for key, path in paths.items()}
    receipt_path = HERE / 'import-receipt.json'
    if receipt_path.exists():
        receipt = read(receipt_path)
        assert sum(x['decision_id'] == receipt['decision_id'] for x in docs['user']['collection_scope_decisions']) == 1
        assert docs['root']['current_component_review'] == docs['component']
        print(json.dumps({'status': 'ALREADY_IMPORTED_IDEMPOTENT_NO_WRITE', 'batch': 14}))
        return
    source = ROOT / 'components/parallel-reviews/mixed-workshop-spiral-2026-10-19/collection-only-decision'
    package_path = source / 'IMPORT_PACKAGE.json'
    assert sha(package_path) == 'fe516acc0f8a77b6620f138980e007fba4027556516dbcd5c416f82d76144248'
    package = read(package_path)
    files = []

    def freeze(path, digest):
        path = Path(path)
        assert sha(path) == digest
        dest = HERE / 'sources' / (digest + path.suffix)
        dest.parent.mkdir(exist_ok=True)
        if dest.exists():
            assert sha(dest) == digest
        else:
            dest.write_bytes(path.read_bytes())
        files.append({'source': str(path), 'snapshot': rel(dest), 'sha256': digest, 'bytes': dest.stat().st_size})
        return rel(dest)

    freeze(package_path, sha(package_path))
    freeze(package['manifest']['path'], package['manifest']['sha256'])
    manifest = read(Path(package['manifest']['path']))
    assert len(manifest['files']) == 7
    for item in manifest['files']:
        freeze(item['path'], item['sha256'])
    snapshots = {x['source']: x['snapshot'] for x in files}
    decision = read(ROOT / snapshots[package['decision']['path']])
    owner = read(ROOT / snapshots[package['owner_evidence']['path']])
    preceding = read(ROOT / snapshots[package['preceding_review']['path']])
    expected = {x['line']: x for x in [owner, preceding]}
    verified = []
    with Path(owner['transcript']).open('rb') as stream:
        assert json.loads(next(stream))['payload']['id'] == package['source_owner_session']
        for number, raw in enumerate(stream, 2):
            if number > max(expected):
                break
            if number not in expected:
                continue
            e, actual = expected[number], json.loads(raw)
            payload = actual['payload']
            text = '\n'.join(x.get('text', '') for x in payload['content'] if x.get('type') in ['input_text', 'output_text', 'text'])
            assert payload['role'] == e['role'] and text == e['text'] and actual['timestamp'] == e['timestamp']
            assert hashlib.sha256(text.encode()).hexdigest() == e['text_sha256']
            assert e['raw_line_sha256'] in [hashlib.sha256(raw).hexdigest(), hashlib.sha256(raw.rstrip(b'\r\n')).hexdigest()]
            verified.append(copy.deepcopy(e) | {'verified_raw_line_sha256_with_LF': hashlib.sha256(raw).hexdigest()})
    assert len(verified) == 2 and owner['line'] == 24427
    assert package['new_identity_Keeps'] == package['new_specification_approvals'] == 0
    heads = read(HERE / 'current-reference-check.json')
    folder = next(x['folder'] for x in heads['metadata'] if x['metadata_type'] == 'folder')
    assert folder['id'] == decision['folder_id'] == 'id:cnqzTNngPVsAAAAAAA51KA'
    assert folder['path_display'] == '/' + decision['folder_path'].split('//', 1)[1].lstrip('/')
    candidate_image = next(x['file'] for x in heads['metadata'] if x['metadata_type'] == 'file')
    cid = 'BC-MIX-SPIRALS'
    before = copy.deepcopy(docs)
    hashes = {key: sha(path) for key, path in paths.items()}
    user, progress, cp, component = (docs[key] for key in ['user', 'progress', 'walkthrough', 'component'])
    assert docs['root']['current_component_review'] == component
    assert cp['current_component_id'] == 'BC-MCP-4' and not cp['current_answer_recorded']
    assert cid not in progress['reviews']
    protected = {str(path): sha(path) for path in [ROOT / 'components/evidence/component_register.json',
                 ROOT / cp['register_workbook'], ROOT / cp['current_review_record'],
                 ROOT.parent / 'Boldstone_Wall_Sculptures_Matched_All_Fields_2026-10-15.xlsx']}
    now = datetime.now(timezone.utc).isoformat()
    decision_id = 'G050:OWNER-COLLECTION-ONLY:' + owner['timestamp']
    record = {'schema_version': 1, 'decision_id': decision_id, 'group_ref': 'G050', 'component_id': cid,
              'review_number': 123, 'scope': 'Owner folder-level collection treatment and temporary individual-review/specification deferral.',
              'classification': 'MIXED_SCULPTURE_COLLECTION_REFERENCE', 'collection_label': 'Collection of sculptures',
              'existing_folder_name': folder['name'], 'folder_id': folder['id'], 'folder_path': folder['path_display'],
              'deferred_candidate_reference_file_id': candidate_image['id'],
              'reference_file_scope': 'Historical individual-proposal context only; identity and specifications deferred.',
              'folder_link': decision['folder_url'], 'authoritative_user_evidence': owner,
              'source_owner_session': package['source_owner_session'], 'recorded_utc': owner['timestamp'], 'imported_utc': now,
              'individual_identity_status': 'UNRESOLVED;DEFERRED_BY_OWNER', 'individual_identity_confirmed': False,
              'specification_status': 'ALL_SIX_FIELDS_DEFERRED_BY_OWNER_UNAPPROVED',
              'deferred_fields': ['Dimensions/depth', 'Weight', 'Material', 'Fixing', 'Individual price', 'Availability'],
              'parallel_active_question_closed': True, 'resume_policy': decision['next_action'],
              'new_identity_Keep': False, 'new_component_sale_unit_mould_or_stock_count': False,
              'new_specification_approval': False, 'physical_specs_verified': False, 'folder_rename_requested': False,
              'source_pre_answer_card_and_guesses_retained_as_history': True,
              'source_package_sha256': sha(package_path), 'source_decision_snapshot': snapshots[package['decision']['path']],
              'other_established_component_decisions_preserved': True, 'remote_mutations': 0}
    approval_path = HERE / 'collection-scope-decision.json'
    user.setdefault('collection_scope_decisions', []).append(copy.deepcopy(record) | {'approval_record': rel(approval_path)})
    override = progress.setdefault('catalogue_group_overrides', {}).setdefault('G050', {})
    override.update({'owner_collection_scope': 'MIXED_SCULPTURE_COLLECTION_REFERENCE', 'folder_id': folder['id'],
                     'folder_path': folder['path_display'], 'owner_scope_approval': rel(approval_path),
                     'deferred_component_proposal_ids': [cid], 'resume_individual_review_only_on_owner_request': True,
                     'existing_established_component_associations_preserved': True,
                     'uniform_single_sculpture_specification_scope': False})
    progress['reviews'][cid] = {'status': 'COLLECTION_ONLY;INDIVIDUAL_IDENTITY_AND_SPECIFICATIONS_DEFERRED_BY_OWNER',
                               'review_number': 123, 'group_ref': 'G050', 'owner_collection_scope_approval': rel(approval_path),
                               'identity_confirmed': False, 'specifications_approved': False, 'physical_specs_verified': False,
                               'new_independent_product_created': False, 'specification_proposals': [],
                               'historical_unapproved_proposals_source': rel(HERE / 'source-manifest.json'),
                               'active_owner_question': None, 'resume_policy': decision['next_action']}
    progress.setdefault('collection_review_progress', {})['G050'] = copy.deepcopy(record)
    cp['deferred_reviews'].append({'component_id': cid, 'original_review_number': 123,
                                    'reason': 'Owner requested collection-only treatment and no specification work for now.',
                                    'identity_confirmed': False, 'specifications_approved': False,
                                    'approval_record': rel(approval_path), 'deferred_utc': owner['timestamp'],
                                    'resume_only_on_owner_request_for_this_collection': True})
    for allocation in cp['parallel_owner_reviews']:
        if allocation['component_id'] == cid:
            allocation.update({'status': 'CLOSED_COLLECTION_ONLY;INDIVIDUAL_IDENTITY_AND_SPECS_DEFERRED_BY_OWNER',
                               'owner_collection_scope_approval': rel(approval_path), 'import_receipt': rel(receipt_path),
                               'active_owner_question': None, 'new_identity_Keep': False})
    component['parallel_owner_reviews'] = copy.deepcopy(cp['parallel_owner_reviews'])
    deferred_ids = component['interactive_review_state']['deferred_component_ids']
    if cid not in deferred_ids:
        deferred_ids.append(cid)
    summary = {'batch': 14, 'recorded_utc': now, 'receipt': rel(receipt_path), 'group_ref': 'G050',
               'owner_collection_scope_recorded': True, 'deferred_component_id': cid, 'deferred_review_number': 123,
               'parallel_question_closed': True, 'new_identity_Keeps': 0, 'new_specification_approvals': 0,
               'new_sale_unit_mould_or_stock_count': False, 'main_Concave_MCP4_question_preserved': True,
               'existing_components_preserved': True, 'remote_mutations': 0, 'workbook_export_pending': True}
    cp['parallel_import_queue'].append({'scope_kind': 'OWNER_COLLECTION_ONLY_AND_SPECIFICATION_DEFERRAL',
        'receipt': rel(package_path), 'receipt_sha256': sha(package_path), 'approval_imported': True,
        'status': 'APPLIED_AND_VERIFIED;NO_NEW_KEEP_OR_SPEC_APPROVAL', 'import_receipt': rel(receipt_path)})
    component['parallel_import_queue'] = copy.deepcopy(cp['parallel_import_queue'])
    component.setdefault('family_review_supplements', {})['Mixed Sculptures Unclassified / G050'] = {
        'summary': summary, 'scope_decision': rel(approval_path)}
    for target in [cp, component]:
        target['last_parallel_import'] = copy.deepcopy(summary)
        target['updated_utc'] = now
    cp['next_serialized_parallel_import'] = cp['completed_serialized_parallel_import'] = {
        'status': 'APPLIED_AND_VERIFIED', 'receipt': rel(receipt_path), 'completed_utc': now}
    progress['latest_parallel_import'] = copy.deepcopy(summary)
    user['updated_utc'] = progress['updated_utc'] = now
    docs['root']['current_component_review'] = copy.deepcopy(component)
    docs['root']['updated_utc'] = now
    assert identity_counts(user) == before['user']['identity_confirmation_counts']
    assert specification_counts(user) == before['user']['specification_approval_counts']
    assert user['dimension_confirmation_counts'] == before['user']['dimension_confirmation_counts']
    assert all(user[key][:len(value)] == value for key, value in before['user'].items() if isinstance(value, list))
    assert all(progress['reviews'][key] == value for key, value in before['progress']['reviews'].items())
    assert all(cp[key] == value for key, value in before['walkthrough'].items() if key.startswith('current_'))
    assert all(sha(paths[key]) == digest for key, digest in hashes.items()), 'Concurrent shared write'
    assert all(sha(Path(path)) == digest for path, digest in protected.items())
    write(HERE / 'before-import.json', before)
    write(HERE / 'source-manifest.json', {'files': files, 'verified_messages': verified,
          'source_package': rel(package_path), 'source_package_sha256': sha(package_path)})
    write(approval_path, record)
    for key, path in paths.items():
        write(path, docs[key])
    write(receipt_path, {'status': 'APPLIED;INDEPENDENT_READBACK_REQUIRED', 'decision_id': decision_id,
          'summary': summary, 'approval_record_sha256': sha(approval_path), 'protected_sha256': protected,
          'shared_after_sha256': {key: sha(path) for key, path in paths.items()}})
    print(json.dumps({'status': 'APPLIED;INDEPENDENT_READBACK_REQUIRED', 'summary': summary}))


if __name__ == '__main__':
    main()
