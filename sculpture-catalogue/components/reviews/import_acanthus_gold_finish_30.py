"""Register the selected Gold finish Keep without extending the earlier White approval."""
import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

from import_source_followups_24_25 import canonical_messages

ROOT = Path(__file__).resolve().parents[2]
HERE = ROOT / 'components/reviews/parallel-import-2026-10-19-batch30'
FOLDER = ROOT / 'components/parallel-reviews/acanthus-gold-finish-2026-10-19/owner-name-keep'
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
rel = lambda p: str(Path(p).relative_to(ROOT))


def write(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n'); temp.replace(path)


def main():
    paths = {'user': ROOT / 'components/reviews/user_classifications.json', 'progress': ROOT / 'components/reviews/specification_review_progress.json',
        'walkthrough': ROOT / 'components/reviews/walkthrough_checkpoint.json', 'component': ROOT / 'components/checkpoint.json', 'root': ROOT / 'checkpoint.json'}
    docs = {k: read(p) for k, p in paths.items()}; cid, vid = 'BC-AC-FULL', 'AC-FULL-GOLD-LEAF'
    if (HERE / 'import-receipt.json').exists():
        assert docs['progress']['reviews'][cid]['size_finish_variants'][vid]['identity_confirmed']
        assert sum(x.get('component_id') == cid and x.get('size_finish_variant_id') == vid for x in docs['user']['size_finish_variant_decisions']) == 1
        print(json.dumps({'batch': 30, 'status': 'ALREADY_IMPORTED_IDEMPOTENT_NO_WRITE'})); return
    package_path = FOLDER / 'IMPORT_PACKAGE.json'; digest = '5098ff03f862c876cd0f6388be2ac02008ab1f053fd8a0651c4ce1a4618b6a90'
    assert sha(package_path) == digest
    package = read(package_path); frozen = []

    def freeze(path, expected):
        path = Path(path); assert sha(path) == expected
        dest = HERE / 'sources' / (expected + path.suffix); dest.parent.mkdir(exist_ok=True)
        if dest.exists(): assert sha(dest) == expected
        else: dest.write_bytes(path.read_bytes())
        item = {'source': str(path), 'snapshot': rel(dest), 'sha256': expected, 'bytes': dest.stat().st_size}; frozen.append(item)
        return rel(dest)

    freeze(package_path, digest); freeze(package['manifest']['path'], package['manifest']['sha256'])
    manifest = read(package['manifest']['path']); assert len(manifest['files']) == 10
    for item in manifest['files']: freeze(FOLDER / item['path'], item['sha256'])
    owner, card = read(package['owner_evidence']['path']), read(package['preceding_card']['path'])
    verified = canonical_messages([card, owner], package['source_owner_session'])
    assert [x['line'] for x in verified] == [25796, 25803]
    assert verified[-1]['text'] == 'Keep “Acanthus and Moon — Gold Leaf”' and '__001.jpg' in verified[0]['text']
    decision = read(package['decision']['path']); review = read(FOLDER / 'before-keep/REVIEW.json')
    assert decision['identity_confirmed'] and not decision['specifications_approved'] and not decision['owner_estimates_accepted']
    assert review['specifications'] == decision['source_specifications_retained']
    source = read(FOLDER / 'before-keep/SOURCE_SNAPSHOT.json'); original = source['cached_original']; content = Path(original['path']).read_bytes()
    assert hashlib.sha256(content).hexdigest() == original['sha256']
    blocks = b''.join(hashlib.sha256(content[i:i + 4194304]).digest() for i in range(0, len(content), 4194304))
    assert hashlib.sha256(blocks).hexdigest() == original['dropbox_content_hash'] == source['selected_asset']['content_hash']
    preview = freeze(original['path'], original['sha256'])
    heads = read(HERE / 'current-reference-check.json')['metadata']; file = next(x['file'] for x in heads if x.get('file')); folder = next(x['folder'] for x in heads if x.get('folder'))
    previous = review['current_reference']['file']
    assert all(file[k] == previous[k] for k in ['id', 'rev', 'size', 'path_display']) and len(content) == file['size']
    assert file['id'] == decision['primary_file_id'] == 'id:cnqzTNngPVsAAAAAAAygIA' and folder['id'] == decision['folder_id'] == 'id:cnqzTNngPVsAAAAAAAygGQ'
    before = copy.deepcopy(docs); guards = {k: sha(p) for k, p in paths.items()}
    user, progress, cp, component, root = (docs[k] for k in ['user', 'progress', 'walkthrough', 'component', 'root'])
    assert root['current_component_review'] == component
    parent = progress['reviews'][cid]; assert vid not in parent.get('size_finish_variants', {})
    protected = {str(p): sha(p) for p in [ROOT / 'components/evidence/component_register.json', ROOT / cp['register_workbook'],
        ROOT / cp['current_review_record'], ROOT.parent / 'Boldstone_Wall_Sculptures_Matched_All_Fields_2026-10-15.xlsx']}
    now = datetime.now(timezone.utc).isoformat()
    decision.update({'authoritative_user_evidence': verified[-1], 'preceding_review_card_evidence': verified[0],
                     'approval_record': rel(HERE / 'identity-approval.json'), 'imported_utc': now})
    user['size_finish_variant_decisions'].append(decision)
    review_snapshot = next(x['snapshot'] for x in frozen if x['source'].endswith('/before-keep/REVIEW.json'))
    ref = {'file_id': file['id'], 'folder_id': folder['id'], 'file_path': file['path_display'], 'folder_path': folder['path_display'],
           'file_revision': file['rev'], 'file_bytes': file['size'], 'image_url': review['image_url'], 'folder_url': review['folder_url'],
           'checked_utc': read(HERE / 'current-reference-check.json')['checked_utc']}
    node = {'component_id': cid, 'size_finish_variant_id': vid, 'canonical_name': decision['canonical_name'],
        'proposed_name': decision['canonical_name'], 'identity_confirmed': True, 'identity_approval': decision['approval_record'],
        'specifications_approved': False, 'proposals_approved': False, 'owner_estimates_accepted': False, 'physical_specs_verified': False,
        'approved_proposal_ids': [], 'fully_confirmed_specification_groups': [], 'specification_proposals': copy.deepcopy(review['specifications']),
        'primary_image_id': file['id'], 'primary_folder_id': folder['id'], 'current_dropbox_reference': ref,
        'scope': decision['scope'], 'review_record': rel(HERE / 'component-review.json'), 'source_review_snapshot': review_snapshot,
        'source_offer_refs': ['O071'], 'existing_platform_match_confirmed': False,
        'platform_mapping': {'status': 'SOURCE_GOLD_LISTING_REFERENCE_ONLY;EXACT_CAST_AND_SHOPIFY_MATCH_UNCONFIRMED',
            'source_offer_ref': 'O071', 'public_listing_url': review['public_listing_url'], 'scope': review['platform_mapping']},
        'missing_photographs': review['missing_photographs'], 'source_photo_originality_authenticated': False,
        'owner_manufacture_confirmed': False, 'root_verified_cached_original': {'snapshot': preview, 'sha256': original['sha256'],
             'dropbox_content_hash': original['dropbox_content_hash'], 'new_original_download': False}, 'imported_utc': now}
    parent.setdefault('size_finish_variants', {})[vid] = node
    progress['asset_assignment_overrides'][file['id']] = {'file_id': file['id'], 'folder_id': folder['id'], 'component_ids': [cid],
        'size_finish_variant_ids': [vid], 'exact_file_only': True, 'whole_folder_identity_approved': False,
        'review_record': node['review_record'], 'assignment_status': 'OWNER_KEPT_SELECTED_GOLD_FINISH;OTHER_IMAGES_AND_PHYSICAL_CAST_IDENTITY_UNCONFIRMED'}
    import sys
    sys.path.insert(0, str(ROOT / 'components/scripts'))
    from review_decision_counts import identity_counts
    user['identity_confirmation_counts'] = identity_counts(user)
    assert user['identity_confirmation_counts']['explicit_size_finish_variant_names'] == before['user']['identity_confirmation_counts']['explicit_size_finish_variant_names'] + 1
    assert user['identity_confirmation_counts']['components_with_any_identity_scope'] == before['user']['identity_confirmation_counts']['components_with_any_identity_scope']
    summary = {'batch': 30, 'recorded_utc': now, 'receipt': rel(HERE / 'import-receipt.json'), 'component_id': cid,
        'size_finish_variant_id': vid, 'new_finish_name_approvals': 1, 'new_registered_BC_component_ids': [],
        'new_full_specification_approvals': 0, 'prior_White_review_preserved': True, 'workbook_export_pending': True,
        'root_new_private_original_downloads': 0, 'remote_mutations': 0}
    cp['parallel_import_queue'].append({'scope_kind': 'EXISTING_COMPONENT_GOLD_FINISH_NAME_ONLY', 'receipt': rel(package_path),
        'receipt_sha256': digest, 'approval_imported': True, 'import_receipt': summary['receipt'], 'status': 'OWNER_NAME_APPLIED;SIX_SPEC_GROUPS_UNAPPROVED'})
    component['parallel_import_queue'] = copy.deepcopy(cp['parallel_import_queue'])
    for target in [cp, component]: target['last_parallel_import'] = copy.deepcopy(summary)
    progress['latest_parallel_import'] = copy.deepcopy(summary)
    for target in docs.values(): target['updated_utc'] = now
    root['current_component_review'] = copy.deepcopy(component)
    assert all(cp[k] == v for k, v in before['walkthrough'].items() if k.startswith('current_'))
    assert user['specification_decisions'] == before['user']['specification_decisions'] and component['counts'] == before['component']['counts']
    assert all(sha(paths[k]) == v for k, v in guards.items()) and all(sha(Path(k)) == v for k, v in protected.items())
    write(HERE / 'before-import.json', before); write(HERE / 'identity-approval.json', decision); write(HERE / 'component-review.json', node)
    write(HERE / 'source-manifest.json', {'files': frozen, 'verified_messages': verified, 'source_package_sha256': digest})
    for k, p in paths.items(): write(p, docs[k])
    write(HERE / 'import-receipt.json', {'status': 'APPLIED;INDEPENDENT_READBACK_REQUIRED', 'summary': summary,
        'protected_sha256': protected, 'shared_after_sha256': {k: sha(p) for k, p in paths.items()}})
    print(json.dumps({'batch': 30, 'status': 'APPLIED;INDEPENDENT_READBACK_REQUIRED', 'frozen_files': len(frozen), 'new_finish_names': 1, 'new_specification_approvals': 0}))


if __name__ == '__main__': main()
