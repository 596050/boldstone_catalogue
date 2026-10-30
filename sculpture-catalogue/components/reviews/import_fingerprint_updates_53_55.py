"""Import sealed exact group decisions while preserving the owner-wide policy."""
import copy
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from import_source_followups_24_25 import canonical_messages

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'components/parallel-reviews/fingerprint-unresolved-groups-2026-10-19'
read = lambda path: json.loads(Path(path).read_text())
sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
rel = lambda path: str(Path(path).relative_to(ROOT))
CONFIG = {
    69: {'folder': 'rough-concentric-verdigris-name-import-20261020', 'package': '8f1da49f85f5c8421a66e65e5c486ab12f201fa9b4fb47dddd0c6b545df8cf4b', 'seal': '39073abaf7256b09747b73a9de715ee9591d1ab33ff23d90a4812a3cf9c294f1', 'key': 'FINGERPRINT-ROUGH-CONCENTRIC-VERDIGRIS-G160001', 'suffix': 'rough-concentric-verdigris-name-check/REVIEW.json', 'line': 18126, 'card': 18119, 'image': '__001.png'},
    66: {'folder': 'offset-spiral-verdigris-name-import-20261020', 'package': 'aa5ee2776c5b597cd911cf72a284f7affa1f6e5487b020b3b6485fab1cdd48f2', 'seal': '05739881ea9a8faa08b5999fbe56db7588a83688e79654c66ddf5ac35b56cee0', 'key': 'FINGERPRINT-OFFSET-SPIRAL-VERDIGRIS-G158022', 'suffix': 'offset-spiral-verdigris-name-check/REVIEW.json', 'line': 18000, 'card': 17993, 'image': '__022.png'},
    65: {'folder': 'oval-rings-curls-verdigris-name-import-20261020', 'package': 'a52f9250543a27eed62f8c01e292401125d299068f02d28d485bb92dd5b7e2f1', 'seal': '5b88ee104a830ae5e5b0e14e0b00798c65f33248cd413a9e7a851d9908be1f46', 'key': 'FINGERPRINT-OVAL-RINGS-CURLS-VERDIGRIS-G158018', 'suffix': 'oval-rings-curls-verdigris-name-check/REVIEW.json', 'line': 17910, 'card': 17868, 'image': '__018.png'},
    63: {'folder': 'twin-spirals-verdigris-name-import-20261019', 'package': '6f6851fd2207e89c743dec32bce71f10fe05695f168b36be1637d0a188600f30', 'seal': '80c1b22d52710bad237959233ebecf1fb8532795ef12930a960f8da835a958ea', 'key': 'FINGERPRINT-TWIN-SPIRALS-VERDIGRIS-G158019', 'suffix': 'twin-spirals-verdigris-name-check/REVIEW.json', 'line': 17798, 'card': 17769, 'image': '__019.png'},
    60: {'folder': 'oval-rings-verdigris-name-import-20261019', 'package': '4b0ac39c1ad300a79de6df4f714f91eb908d621b089a08a6ed284661f50f8440', 'seal': 'dea6669d9df286ed989f1ff190b3a9d204f6050782a3d4f413d4fe982b2f53f8', 'key': 'FINGERPRINT-OVAL-RINGS-VERDIGRIS-G158017', 'suffix': 'oval-rings-verdigris-name-check/REVIEW.json', 'line': 17697, 'card': 17668, 'image': '__017.png', 'owner_literal': 'yes: Keep “Fingerprint — Oval Rings (Verdigris)”'},
    58: {'folder': 'multiple-spiral-verdigris-name-import-20261019', 'package': 'cd795ef98af9e0e08fc71a96c9e524dab30856090672cae27cae498e2a793436', 'seal': 'eb389fe2c404851bcb757284e971cb82a812d3c0c42f8ff5531fa958b486f661', 'key': 'FINGERPRINT-MULTIPLE-SPIRAL-VERDIGRIS-G158020', 'suffix': 'multiple-spiral-verdigris-name-check/REVIEW.json', 'line': 17599, 'card': 17592, 'image': '__020.png'},
    53: {'folder': 'fine-ridge-verdigris-manufacture-import-20261019', 'package': '0f2d400826346c241cdc7b81ea51154410bdb058156aac9fdfcc7e0f7a5faf08', 'seal': '8e3d24bcdd66295f09ce0b5ee673161eb7f83b1fad80fd57d481a955d4f3329e', 'key': 'FINGERPRINT-FINE-RIDGE-VERDIGRIS-G158004', 'suffix': 'fine-ridge-verdigris-name-check/REVIEW.json', 'production_only': True, 'line': 17344, 'card': 17337, 'image': '__004.png'},
    54: {'folder': 'fine-ridge-verdigris-name-import-20261019', 'package': 'ad72bec109d33ebcb007db1e425ec41d3e0757e4d7d06d188eea8dadd76e1187', 'seal': 'a92c22c222c3f7c1850d4b59c883bb769e108b2b7c21106593f60269a5436a51', 'key': 'FINGERPRINT-FINE-RIDGE-VERDIGRIS-G158004', 'suffix': 'fine-ridge-verdigris-name-check/REVIEW.json', 'line': 17439, 'card': 17424, 'image': '__004.png'},
    55: {'folder': 'diagonal-spiral-verdigris-name-import-20261019', 'package': 'c04757ee7d252edb8328c9b052e6e1ea8f508dcfa20b5d93d03dd37524fb5ca0', 'seal': '60615903368b0470640096b69fb0dd6bc35c2d729f0cbf3916ecaa6594beea1d', 'key': 'FINGERPRINT-DIAGONAL-SPIRAL-VERDIGRIS-G158034', 'suffix': 'diagonal-spiral-verdigris-name-check/REVIEW.json', 'line': 17516, 'card': 17509, 'image': '__034.png', 'exact_ai': True},
}
def write(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.tmp'); temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n'); temp.replace(path)

def apply(batch):
    cfg = CONFIG[batch]; here = ROOT / f'components/reviews/parallel-import-2026-10-19-batch{batch}'
    paths = {'user': ROOT / 'components/reviews/user_classifications.json', 'progress': ROOT / 'components/reviews/specification_review_progress.json', 'walkthrough': ROOT / 'components/reviews/walkthrough_checkpoint.json', 'component': ROOT / 'components/checkpoint.json', 'root': ROOT / 'checkpoint.json'}
    docs = {key: read(path) for key, path in paths.items()}; key = cfg['key']
    if (here / 'import-receipt.json').exists():
        receipt = read(here / 'import-receipt.json')
        assert sum(item.get('decision_id') == receipt['decision_id'] for item in docs['user'][receipt['ledger']]) == 1
        print(json.dumps({'batch': batch, 'status': 'ALREADY_IMPORTED_IDEMPOTENT_NO_WRITE'})); return
    folder = BASE / cfg['folder']; package_path = folder / 'IMPORT_PACKAGE.json'; seal_path = folder / 'SEALED_PACKAGE_MANIFEST.json'
    assert sha(package_path) == cfg['package'] and sha(seal_path) == cfg['seal']
    package = read(package_path); files = []; snapshots = {}
    def freeze(path, digest, source=None, suffix=None):
        path = Path(path); source = str(source or path)
        assert sha(path) == digest
        dest = here / 'sources' / (digest + (suffix or path.suffix)); dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists(): assert sha(dest) == digest
        else: dest.write_bytes(path.read_bytes())
        if source not in snapshots: files.append({'source': source, 'snapshot': rel(dest), 'sha256': digest})
        snapshots[source] = rel(dest); return rel(dest)
    freeze(package_path, cfg['package']); freeze(seal_path, cfg['seal'])
    for item in read(seal_path)['files']: freeze(item['path'], item['sha256'])
    for item in read(package['frozen_sources']['path'])['files']: freeze(item['frozen_path'], item['sha256'], item['source_path'])
    review_snapshot = next(value for source, value in snapshots.items() if source.endswith(cfg['suffix'])); review = read(ROOT / review_snapshot)
    messages = canonical_messages(read(package['exact_owner_transcript']['path'])['messages'], package['source_owner_session'])
    assert messages[-1]['line'] == cfg['line'] and messages[-1]['immediately_preceding_assistant']['line'] == cfg['card'] and cfg['image'] in messages[0]['text']
    production = cfg.get('production_only', False)
    decision_ref = package['owner_production_confirmations' if production else 'owner_name_approvals'][0]['decision']
    decision = read(ROOT / snapshots[decision_ref['path']]); assert sha(ROOT / snapshots[decision_ref['path']]) == decision_ref['sha256']
    assert messages[-1]['text'] == ('yes: physically made' if production else cfg.get('owner_literal', 'Keep “' + package['approved_source_name'] + '”'))
    heads = read(here / 'current-reference-check.json')['metadata']; head = next(item['file'] for item in heads if item.get('file')); parent = next(item['folder'] for item in heads if item.get('folder'))
    assert all(head[field] == review['primary_image'][field] for field in ['id', 'rev', 'size', 'path_display']) and parent['id'] == review['primary_folder']['id']
    assert head['id'] == package['reference_asset_id'] and head['path_display'].rsplit('/', 1)[0] == parent['path_display']
    before = copy.deepcopy(docs); guards = {name: sha(path) for name, path in paths.items()}
    u, p, cp, c = (docs[name] for name in ['user', 'progress', 'walkthrough', 'component']); assert docs['root']['current_component_review'] == c
    assert p['physical_manufacture_review_policy']['owner_confirms_all_sculpture_designs_physically_made'] and not p['physical_manufacture_review_policy']['repeat_per_source_manufacture_questions_required']
    protected = {str(path): sha(path) for path in [ROOT / cp['register_workbook'], ROOT / cp['current_review_record'], ROOT / 'components/evidence/component_register.json', ROOT.parent / 'Boldstone_Wall_Sculptures_Matched_All_Fields_2026-10-15.xlsx']}
    now = datetime.now(timezone.utc).isoformat(); ledger = 'design_production_confirmation_decisions' if production else 'source_design_name_decisions'
    approval = rel(here / ('source-production-decision.json' if production else 'source-name-decision.json'))
    decision.update({'source_design_key': key, 'authoritative_user_evidence': messages[-1], 'verified_original_question': messages[0], 'approval_record': approval, 'imported_utc': now})
    assert not any(item.get('decision_id') == decision['decision_id'] for item in u.get(ledger, [])); u.setdefault(ledger, []).append(decision)
    if batch == 54:
        node = p['source_design_reviews'][key]; assert not node['identity_confirmed'] and node['specifications'] == review['specifications']
    else:
        assert key not in p.get('source_design_reviews', {}) and head['id'] not in p['asset_assignment_overrides']
        preview = freeze(review['cached_primary_preview']['path'], review['cached_primary_preview']['sha256'])
        visual = read(ROOT / next(value for source, value in snapshots.items() if source.endswith('GROUPED_SOURCE_VISUAL_REVIEW.json')))
        original = Path(visual['cached_original']['path']); content = original.read_bytes(); assert sha(original) == visual['cached_original']['sha256'] and len(content) == head['size']
        blocks = b''.join(hashlib.sha256(content[index:index + 4194304]).digest() for index in range(0, len(content), 4194304)); assert hashlib.sha256(blocks).hexdigest() == package['reference_content_hash']
        if cfg.get('exact_ai'): assert b'trainedAlgorithmicMedia' in content and b'BytePlus_ModelArk' in content
        original_snapshot = freeze(original, sha(original), suffix='.png')
        node = {'source_design_key': key, 'source_asset_id': head['id'], 'source_folder_id': parent['id'], 'source_path_display': head['path_display'], 'source_folder_path_display': parent['path_display'], 'image_link': review['browser_links']['image'], 'folder_link': review['browser_links']['folder'], 'source_file_revision': head['rev'], 'source_file_bytes': head['size'], 'current_reference_check': rel(here / 'current-reference-check.json'), 'source_review_snapshot': review_snapshot, 'root_viewed_reference_snapshot': preview, 'source_image_authenticated_as_original_photo': False, 'physical_specs_verified': False, 'component_ids': [], 'new_registered_BC_component_ids': [], 'specification_fields_fully_approved': [], 'all_six_complete_specification_groups_pending': True, 'owner_estimates_accepted': False, 'specifications': copy.deepcopy(review['specifications']), 'imported_utc': now, 'source_package_sha256': cfg['package'], 'existing_squarespace_shopify_match_confirmed': False, 'owner_stated_design_physically_made': True, 'physical_production_independently_verified': False, 'component_members_status': 'DEFERRED_BY_OWNER_GROUP_PHOTO_POLICY', 'component_member_identification_required_for_current_review': False, 'group_photo_scope_record': p['group_photo_review_policy']['approval_record'], 'source_AI_creation_declaration_preserved': cfg.get('exact_ai', False), 'exact_file_AI_declaration_established': cfg.get('exact_ai', False), 'case_level_partial_AI_resolution_preserved': not cfg.get('exact_ai', False), 'embedded_signature_verified': False, 'source_origin_evidence': visual['source_origin_evidence'], 'root_original_verification': {'original_snapshot': original_snapshot, 'sha256': sha(original), 'dropbox_content_hash': package['reference_content_hash'], 'embedded_AI_creation_declaration_present': True if cfg.get('exact_ai') else None, 'embedded_signature_verified': False, 'source_origin_evidence': visual['source_origin_evidence'], 'new_original_download': False}}
        p.setdefault('source_design_reviews', {})[key] = node
        p['asset_assignment_overrides'][head['id']] = {'source_design_key': key, 'file_id': head['id'], 'folder_id': parent['id'], 'component_ids': [], 'family': 'Fingerprint', 'exact_component_or_stock_count_verified': False, 'review_record': rel(here / 'source-design-review.json')}
    if production:
        node.update({'record_kind': 'GROUP_SOURCE_NAME_PENDING;MEMBER_IDENTIFICATION_DEFERRED_BY_OWNER', 'canonical_source_name': package['candidate_label_not_approved'], 'proposed_name': package['candidate_label_not_approved'], 'identity_confirmed': False, 'catalogue_name_explicitly_approved': False, 'active_owner_question': review['question'], 'owner_production_approval': approval})
    else:
        node.update({'record_kind': 'OWNER_NAMED_GROUP_SOURCE;MEMBER_IDENTIFICATION_DEFERRED_BY_OWNER', 'canonical_source_name': package['approved_source_name'], 'canonical_name': package['approved_source_name'], 'identity_confirmed': True, 'catalogue_name_explicitly_approved': True, 'owner_name_approval': approval, 'active_owner_question': None, 'source_name_question_answered': True})
    if not production and batch != 54: node.update({'manufacture_evidence_basis': 'OWNER_UNIVERSAL_STATEMENT_LINE17365', 'owner_wide_manufacture_policy': p['physical_manufacture_review_policy']['approval_record'], 'no_source_specific_manufacture_decision_created': True})
    if batch == 69:
        node['original_Fingerprint_model_relationship'] = package['original_Fingerprint_model_relationship']
        node['original_40cm_dimensions_inherited'] = False
    p['asset_assignment_overrides'][head['id']]['assignment_status'] = 'OWNER_MANUFACTURE_CONFIRMED_GROUP_REFERENCE;NAME_PENDING' if production else 'OWNER_NAMED_GROUP_REFERENCE;SIX_SPECIFICATION_ESTIMATES_UNAPPROVED'
    summary = {'batch': batch, 'recorded_utc': now, 'receipt': rel(here / 'import-receipt.json'), 'source_design_key': key, 'new_source_name_approvals': 0 if production else 1, 'new_source_production_confirmations': 1 if production else 0, 'new_owner_policy_events': 0, 'new_full_specification_approvals': 0, 'new_registered_BC_component_ids': [], 'root_new_private_original_downloads': 0, 'remote_mutations': 0, 'workbook_export_pending': True}
    cp['parallel_import_queue'].append({'scope_kind': 'EXACT_GROUP_MANUFACTURE_ONLY' if production else 'EXACT_GROUP_NAME_ONLY;NO_MANUFACTURE_OR_POLICY_REPLAY', 'receipt': rel(package_path), 'receipt_sha256': cfg['package'], 'approval_imported': True, 'import_receipt': summary['receipt'], 'status': 'APPLIED_EXACT_OWNER_SCOPE;SIX_ESTIMATES_UNAPPROVED'})
    c['parallel_import_queue'] = copy.deepcopy(cp['parallel_import_queue'])
    for target, name in [(p, 'latest_parallel_import'), (cp, 'last_parallel_import'), (c, 'last_parallel_import')]: target[name] = copy.deepcopy(summary)
    for doc in docs.values(): doc['updated_utc'] = now
    docs['root']['current_component_review'] = copy.deepcopy(c)
    assert p['reviews'] == before['progress']['reviews'] and p['physical_manufacture_review_policy'] == before['progress']['physical_manufacture_review_policy']
    assert all(cp[name] == value for name, value in before['walkthrough'].items() if name.startswith('current_'))
    assert all(sha(paths[name]) == value for name, value in guards.items()) and all(sha(path) == value for path, value in protected.items())
    write(here / 'before-import.json', before); write(here / 'source-design-review.json', node); write(here / Path(approval).name, decision); write(here / 'source-manifest.json', {'files': files, 'verified_messages': messages})
    for name, path in paths.items(): write(path, docs[name])
    write(here / 'import-receipt.json', {'status': 'APPLIED;INDEPENDENT_READBACK_REQUIRED', 'summary': summary, 'source_design_key': key, 'ledger': ledger, 'decision_id': decision['decision_id'], 'protected_sha256': protected, 'shared_after_sha256': {name: sha(path) for name, path in paths.items()}})
    print(json.dumps({'batch': batch, 'status': 'APPLIED', 'source_design_key': key, 'new_policy_events': 0, 'six_estimates_approved': False}))

if __name__ == '__main__': apply(int(sys.argv[1]))
