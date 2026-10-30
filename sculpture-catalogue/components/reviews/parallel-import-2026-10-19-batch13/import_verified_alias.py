"""Resolve owner-confirmed Luciano alias and three historical position references."""
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
read = lambda p: json.loads(p.read_text())
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
rel = lambda p: str(p.relative_to(ROOT))


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    tmp.replace(path)


def main():
    intake = read(HERE / 'source-intake.json')
    alias = read(ROOT / intake['alias_snapshot'])
    package = read(ROOT / intake['source_package_snapshot'])
    paths = {'user': REVIEWS / 'user_classifications.json', 'progress': REVIEWS / 'specification_review_progress.json',
             'walkthrough': REVIEWS / 'walkthrough_checkpoint.json', 'component': ROOT / 'components/checkpoint.json',
             'root': ROOT / 'checkpoint.json'}
    docs = {key: read(path) for key, path in paths.items()}
    receipt_path = HERE / 'import-receipt.json'
    if receipt_path.exists():
        receipt = read(receipt_path)
        for ledger, ids in receipt['new_ledger_decision_ids'].items():
            actual = [x.get('decision_id') for x in docs['user'][ledger]]
            assert all(actual.count(value) == 1 for value in ids)
        assert docs['root']['current_component_review'] == docs['component']
        print(json.dumps({'status': 'ALREADY_IMPORTED_IDEMPOTENT_NO_WRITE', 'batch': 13}))
        return
    for source in intake['files']:
        assert sha(ROOT / source['snapshot']) == source['sha256']
    originals = read(HERE / 'current-original-receipts.json')
    heads = read(HERE / 'current-reference-check.json')
    assert originals['status'] == heads['status'] == 'PASS' and len(originals['entries']) == 2
    for original in originals['entries']:
        assert sha(ROOT / original['local_path']) == original['sha256']
    assert (HERE / 'root-rendered-project-page.png').is_file()
    assert package['new_identity_Keeps'] == package['new_specification_approvals'] == 0
    owner = next(x for x in intake['verified_messages'] if x['role'] == 'user')
    assert owner['text'] == alias['owner_statement']
    before = copy.deepcopy(docs)
    hashes = {key: sha(path) for key, path in paths.items()}
    user, progress, cp, component = (docs[key] for key in ['user', 'progress', 'walkthrough', 'component'])
    assert docs['root']['current_component_review'] == component
    assert cp['current_component_id'] == 'BC-MCP-4' and not cp['current_answer_recorded']
    protected = {str(path): sha(path) for path in [ROOT / 'components/evidence/component_register.json',
                 ROOT / cp['register_workbook'], ROOT / cp['current_review_record'], ROOT / cp['last_identity_approval'],
                 ROOT.parent / 'Boldstone_Wall_Sculptures_Matched_All_Fields_2026-10-15.xlsx']}
    now = datetime.now(timezone.utc).isoformat()
    outputs, ledger_ids = [], {}

    def save(name, value, ledger):
        path = HERE / 'decisions' / name
        assert not path.exists()
        assert not any(x.get('decision_id') == value['decision_id'] for x in user.get(ledger, []))
        outputs.append((path, value))
        user.setdefault(ledger, []).append(copy.deepcopy(value) | {'approval_record': rel(path)})
        ledger_ids.setdefault(ledger, []).append(value['decision_id'])
        return rel(path)

    metadata = {x['request_id']: x.get('file', x.get('folder')) for x in heads['metadata']}
    verified_originals = {x['id']: x for x in originals['entries']}
    refs = []
    for fid, item in intake['current_reference_targets'].items():
        if item['kind'] != 'file':
            continue
        current = metadata[fid]
        folder = next(value for key, value in metadata.items()
                      if intake['current_reference_targets'][key]['kind'] == 'folder'
                      and current['path_display'].rsplit('/', 1)[0] == value['path_display'])
        original = verified_originals[fid]
        refs.append({'file_id': fid, 'folder_id': folder['id'], 'file_path': current['path_display'],
                     'folder_path': folder['path_display'], 'rev': current['rev'], 'bytes': current['size'],
                     'sha256': original['sha256'], 'dropbox_content_hash': original['content_hash'],
                     'checked_utc': heads['checked_utc'],
                     'image_link': 'https://www.dropbox.com/preview' + quote(current['path_display'], safe='/'),
                     'folder_link': 'https://www.dropbox.com/home' + quote(folder['path_display'], safe='/'),
                     'scope': 'Complete historical three-part project / arrangement reference; not an isolated component.'})

    family = {'schema_version': 1, 'decision_id': alias['decision_id'], 'canonical_family': 'Lava Moon',
              'historical_alias': 'Luciano Moonshell Lava', 'recorded_utc': owner['timestamp'], 'imported_utc': now,
              'source_owner_session': package['source_owner_session'], 'authoritative_user_evidence': owner,
              'owner_confirmed_family_project_design_equivalence': True,
              'scope': 'Owner confirms the two names identify the same design. Historical project-position references follow the visually matched same displayed orientation; individual finish, physical casts, moulds and specifications remain separate.',
              'source_alias_snapshot': intake['alias_snapshot'], 'source_package_sha256': intake['source_package_sha256'],
              'current_dropbox_references': refs, 'new_identity_Keeps': 0, 'new_specification_approvals': 0,
              'same_physical_cast_or_mould_confirmed': False, 'physical_specs_verified': False,
              'current_name_retained': 'Lava Moon', 'historical_document_title_retained': True,
              'remote_mutations': 0, 'workbook_export_pending': True}
    family_path = save('family-alias.json', family, 'family_identity_alias_decisions')
    progress.setdefault('catalogue_family_aliases', {})['Luciano Moonshell Lava'] = family | {'approval_record': family_path}
    resolutions = []
    for position in alias['position_references']:
        cid, canonical = position['source_component_id'], position['canonical_component_id']
        assert cid not in progress['reviews'] and canonical in progress['reviews']
        record = {'schema_version': 1, 'decision_id': cid + ':HISTORICAL-POSITION-REFERENCE:' + canonical,
                  'component_id': cid, 'canonical_component_id': canonical,
                  'canonical_size_finish_variant_id': None, 'position': position['position'],
                  'relationship': position['relationship'], 'status': 'RESOLVED_REFERENCE_NO_ADDITIONAL_PRODUCT',
                  'authoritative_user_evidence': owner, 'family_alias_approval': family_path,
                  'owner_family_design_equivalence_confirmed': True, 'position_owner_stated': False,
                  'position_basis': 'Root inspected the historical project PDF and current Lava Moon Sandstone In Situ002: matching upper-left installed view, two panel joints, frame, lights and orientation. Component links are displayed-position references only.',
                  'current_dropbox_references': refs, 'individual_finish_assigned_by_this_correction': None,
                  'new_independent_product_created': False, 'new_identity_Keep': False,
                  'same_physical_cast_or_mould_confirmed': False, 'specifications_approved': False,
                  'approved_proposal_ids': [], 'physical_specs_verified': False, 'source_alias_snapshot': intake['alias_snapshot'],
                  'recorded_utc': owner['timestamp'], 'imported_utc': now}
        path = save(cid + '-reference.json', record, 'component_identity_relationship_decisions')
        progress['reviews'][cid] = {'status': record['status'], 'canonical_component_id': canonical,
                                   'canonical_size_finish_variant_id': None, 'relationship_approval': path,
                                   'identity_confirmed': False, 'new_independent_product_created': False,
                                   'specifications_approved': False, 'specification_proposals': [],
                                   'physical_specs_verified': False, 'historical_alias': 'Luciano Moonshell Lava',
                                   'source_specification_guesses_status': 'WITHDRAWN_AS_DUPLICATE_REVIEW;DATED_SOURCE_ARCHIVE_RETAINED',
                                   'source_archive_manifest': rel(HERE / 'source-intake.json')}
        resolutions.append({'source_component_id': cid, 'canonical_component_id': canonical, 'approval_record': path})
    pdf_id = alias['historical_project_source']['file_id']
    progress.setdefault('historical_document_design_bindings', {})[pdf_id] = {
        'file_id': pdf_id, 'canonical_family': 'Lava Moon', 'family_alias_approval': family_path,
        'historical_project_source': copy.deepcopy(alias['historical_project_source']),
        'whole_screen_dimensions_source_only_cm': [215, 180], 'individual_dimensions_from_this_source_cm': None,
        'material_claim_scope': 'Dated January2006 whole-project fibrous cement / silver sand surface claim only.',
        'current_individual_finish_material_weight_or_size_assigned': False,
        'source_document_bytes_and_location_changed': False}
    summary = {'batch': 13, 'recorded_utc': now, 'receipt': rel(receipt_path), 'canonical_family': 'Lava Moon',
               'historical_alias': 'Luciano Moonshell Lava', 'owner_confirmed_family_aliases': 1,
               'resolved_historical_position_references': 3, 'new_independent_products': 0,
               'new_identity_Keeps': 0, 'new_specification_approvals': 0, 'current_Lava_specifications_preserved': True,
               'historical_whole_screen_dimensions_kept_separate': True, 'individual_finish_from_latest_owner_message': None,
               'root_refreshed_heads': 4, 'root_originals_hash_checked': 2,
               'main_Concave_MCP4_question_preserved': True, 'workbook_export_pending': True, 'remote_mutations': 0}
    supplement = {'summary': summary, 'family_alias_approval': family_path, 'position_references': resolutions,
                  'source_intake': rel(HERE / 'source-intake.json'),
                  'G262_remains_family_only_no_exact_component_or_finish': True}
    progress.setdefault('family_review_progress', {})['Luciano Moonshell Lava'] = {
        'status': 'DUPLICATE_FAMILY_PROJECT_ALIAS_RESOLVED_TO_LAVA_MOON;NO_ADDITIONAL_PRODUCT', 'supplement': supplement}
    progress.setdefault('current_catalogue_overlays', {})['Luciano Moonshell Lava'] = copy.deepcopy(supplement)
    component.setdefault('current_catalogue_overlays', {})['Luciano Moonshell Lava'] = copy.deepcopy(supplement)
    component.setdefault('family_review_supplements', {})['Luciano / Lava Moon alias'] = copy.deepcopy(supplement)
    for allocation in cp['parallel_owner_reviews']:
        if allocation['component_id'] in package['source_component_ids']:
            allocation.update({'status': 'OWNER_FAMILY_ALIAS_AND_VISUAL_POSITION_REFERENCE_RESOLVED;NO_ADDITIONAL_PRODUCT',
                               'import_receipt': rel(receipt_path), 'canonical_component_id': next(
                                   x['canonical_component_id'] for x in resolutions if x['source_component_id'] == allocation['component_id'])})
    component['parallel_owner_reviews'] = copy.deepcopy(cp['parallel_owner_reviews'])
    queue = {'scope_kind': 'SEALED_OWNER_FAMILY_ALIAS_AND_PROJECT_POSITION_REFERENCES',
             'receipt': intake['source_package'], 'receipt_sha256': intake['source_package_sha256'],
             'status': 'APPLIED_AND_VERIFIED;NO_NEW_KEEPS_OR_SPECS', 'approval_imported': True,
             'import_receipt': rel(receipt_path), 'imported_utc': now}
    assert not any(x['receipt'] == queue['receipt'] for x in cp['parallel_import_queue'])
    cp['parallel_import_queue'].append(queue)
    component['parallel_import_queue'] = copy.deepcopy(cp['parallel_import_queue'])
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
    for key, value in before['user'].items():
        if isinstance(value, list):
            assert user[key][:len(value)] == value
    assert all(progress['reviews'][key] == value for key, value in before['progress']['reviews'].items())
    assert all(progress.get(key) == before['progress'].get(key) for key in ['asset_assignment_overrides', 'catalogue_group_overrides'])
    assert all(cp[key] == value for key, value in before['walkthrough'].items() if key.startswith('current_'))
    assert all(sha(path) == hashes[key] for key, path in paths.items()), 'Concurrent shared write'
    assert all(sha(Path(path)) == digest for path, digest in protected.items())
    write(HERE / 'before-import.json', before)
    for path, value in outputs:
        write(path, value)
    for key, path in paths.items():
        write(path, docs[key])
    receipt = {'status': 'APPLIED;INDEPENDENT_READBACK_REQUIRED', 'summary': summary,
               'new_ledger_decision_ids': ledger_ids, 'decision_files': {rel(path): sha(path) for path, _ in outputs},
               'protected_sha256': protected, 'shared_before_sha256': hashes,
               'shared_after_sha256': {key: sha(path) for key, path in paths.items()}, 'remote_mutations': 0}
    write(receipt_path, receipt)
    print(json.dumps({'status': receipt['status'], 'summary': summary}))


if __name__ == '__main__':
    main()
