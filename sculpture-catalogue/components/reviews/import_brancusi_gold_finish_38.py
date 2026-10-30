"""Import the selected Brancusi Gold name, retaining thumbnail-only evidence limits."""
import copy
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from import_source_followups_24_25 import canonical_messages

ROOT = Path(__file__).resolve().parents[2]
BATCH = int(sys.argv[1]) if len(sys.argv) > 1 else 38
CONFIG = {
    38: {'cid': 'BC-BR-1', 'vid': 'BR-1-GOLD-LEAF', 'name': 'Brancusi 1 — Gold Leaf', 'folder': 'one-gold-leaf',
         'sha': 'eb3faab5756194d7d13f9f91631926e66b1d9416773c78d039ea93b8581c866c', 'lines': [26266, 26306],
         'fid': 'id:cnqzTNngPVsAAAAAAAyjwQ', 'folder_id': 'id:cnqzTNngPVsAAAAAAAyjbA', 'suffix': '__008.png'},
    40: {'cid': 'BC-BR-2', 'vid': 'BR-2-GOLD-LEAF', 'name': 'Brancusi 2 — Gold Leaf', 'folder': 'two-gold-leaf',
         'sha': '0ebd1a416bf27dc45d0703291e2267be573a9235a384bd1234fa5106d3afee4e', 'lines': [26367, 26391],
         'fid': 'id:cnqzTNngPVsAAAAAAAyjvw', 'folder_id': 'id:cnqzTNngPVsAAAAAAAyjbw', 'suffix': '__011.png'}
}[BATCH]
HERE = ROOT / f'components/reviews/parallel-import-2026-10-19-batch{BATCH}'
FOLDER = ROOT / ('components/parallel-reviews/brancusi-gold-finishes-2026-10-19/' + CONFIG['folder'] + '/owner-name-keep')
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
rel = lambda p: str(Path(p).relative_to(ROOT))


def write(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.tmp'); temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n'); temp.replace(path)


def main():
    paths = {'user': ROOT / 'components/reviews/user_classifications.json', 'progress': ROOT / 'components/reviews/specification_review_progress.json',
        'walkthrough': ROOT / 'components/reviews/walkthrough_checkpoint.json', 'component': ROOT / 'components/checkpoint.json', 'root': ROOT / 'checkpoint.json'}
    docs = {k: read(p) for k, p in paths.items()}; cid, vid = CONFIG['cid'], CONFIG['vid']
    if (HERE / 'import-receipt.json').exists():
        assert docs['progress']['reviews'][cid]['size_finish_variants'][vid]['identity_confirmed']
        assert sum(x.get('component_id') == cid and x.get('size_finish_variant_id') == vid for x in docs['user']['size_finish_variant_decisions']) == 1
        print(json.dumps({'batch': BATCH, 'status': 'ALREADY_IMPORTED_IDEMPOTENT_NO_WRITE'})); return
    package_path = FOLDER / 'IMPORT_PACKAGE.json'; digest = CONFIG['sha']
    assert sha(package_path) == digest
    package = read(package_path); frozen = []
    def freeze(path, expected):
        path = Path(path); assert sha(path) == expected
        dest = HERE / 'sources' / (expected + path.suffix); dest.parent.mkdir(exist_ok=True)
        if dest.exists(): assert sha(dest) == expected
        else: dest.write_bytes(path.read_bytes())
        frozen.append({'source': str(path), 'snapshot': rel(dest), 'sha256': expected, 'bytes': dest.stat().st_size})
        return rel(dest)
    freeze(package_path, digest); freeze(package['manifest']['path'], package['manifest']['sha256'])
    manifest = read(package['manifest']['path']); assert len(manifest['files']) == 10
    for item in manifest['files']: freeze(FOLDER / item['path'], item['sha256'])
    verified = canonical_messages([read(package['preceding_card']['path']), read(package['owner_evidence']['path'])], package['source_owner_session'])
    assert [x['line'] for x in verified] == CONFIG['lines']
    assert verified[-1]['text'] == 'Keep “' + CONFIG['name'] + '”' and verified[-1]['immediately_preceding_assistant']['line'] == CONFIG['lines'][0]
    assert CONFIG['suffix'] in verified[0]['text']
    decision = read(package['decision']['path']); review = read(FOLDER / 'before-keep/REVIEW.json'); source = read(FOLDER / 'before-keep/SOURCE_SNAPSHOT.json')
    assert decision['identity_confirmed'] and not decision['specifications_approved'] and not decision['owner_estimates_accepted']
    assert review['specifications'] == decision['source_specifications_retained'] and len(review['specifications']) == 6
    assert all(v['owner_approved'] is False for v in review['specifications'].values())
    thumb = source['cached_thumbnail']; assert sha(thumb['path']) == thumb['sha256'] and Path(thumb['path']).stat().st_size == thumb['bytes']
    assert thumb['original_bytes_checked'] is False and thumb['thumbnail_hash_is_not_original_hash']
    assert source['selected_asset']['id'] == CONFIG['fid']
    preview = freeze(thumb['path'], thumb['sha256'])
    heads = read(HERE / 'current-reference-check.json'); metadata = heads['metadata']
    file = next(x['file'] for x in metadata if x.get('file', {}).get('id') == CONFIG['fid'])
    folder = next(x['folder'] for x in metadata if x.get('folder', {}).get('id') == CONFIG['folder_id'])
    assert all(file[k] == review['current_reference']['file'][k] for k in ['id', 'name', 'rev', 'size', 'path_display'])
    assert file['size'] == source['selected_asset']['bytes'] and file['path_display'].rsplit('/', 1)[0] == folder['path_display']
    before = copy.deepcopy(docs); guards = {k: sha(p) for k, p in paths.items()}
    u, p, cp, c, root = (docs[k] for k in ['user', 'progress', 'walkthrough', 'component', 'root'])
    assert root['current_component_review'] == c and cid not in p['reviews']
    prior = next(x for x in u['decisions'] if x.get('decision_id') == cid + ':identity:keep')
    model = read(ROOT / 'components/evidence/component_register.json'); component = next(x for x in model['components'] if x['component_id'] == cid)
    assert prior['identity_status'] == 'USER CONFIRMED' and prior['proposed_name_at_review'] == component['name']
    white = next(x['file'] for x in metadata if x.get('file', {}).get('id') == prior['evidence_file_id'])
    whitefolder = next(x['folder'] for x in metadata if x.get('folder', {}).get('id') == prior['containing_folder_id'])
    assert white['path_display'].rsplit('/', 1)[0] == whitefolder['path_display']
    protected = {str(x): sha(x) for x in [ROOT / 'components/evidence/component_register.json', ROOT / cp['register_workbook'], ROOT / cp['current_review_record'], ROOT.parent / 'Boldstone_Wall_Sculptures_Matched_All_Fields_2026-10-15.xlsx']}
    now = datetime.now(timezone.utc).isoformat()
    parent = {'component_id': cid, 'canonical_name': prior['proposed_name_at_review'], 'identity_confirmed': True,
        'identity_approval': rel(HERE / 'existing-parent-identity.json'), 'prior_identity_decision_id': prior['decision_id'],
        'primary_image_id': white['id'], 'primary_folder_id': whitefolder['id'], 'specifications_approved': False,
        'proposals_approved': False, 'physical_specs_verified': False, 'specification_proposals': [],
        'scope': 'Existing 17October component-design name Keep represented in the review overlay. Historical per-piece White source claims remain unverified for each cast and do not approve Gold specifications. No new parent identity decision or physical count.',
        'review_record': rel(HERE / 'existing-parent-identity.json'), 'size_finish_variants': {}}
    decision.update({'authoritative_user_evidence': verified[-1], 'preceding_review_card_evidence': verified[0], 'approval_record': rel(HERE / 'identity-approval.json'), 'imported_utc': now})
    u['size_finish_variant_decisions'].append(decision)
    review_snapshot = next(x['snapshot'] for x in frozen if x['source'].endswith('/before-keep/REVIEW.json'))
    node = {'component_id': cid, 'size_finish_variant_id': vid, 'canonical_name': decision['canonical_name'], 'proposed_name': decision['canonical_name'],
        'identity_confirmed': True, 'identity_approval': decision['approval_record'], 'specifications_approved': False, 'proposals_approved': False,
        'owner_estimates_accepted': False, 'physical_specs_verified': False, 'approved_proposal_ids': [], 'fully_confirmed_specification_groups': [],
        'specification_proposals': copy.deepcopy(review['specifications']), 'primary_image_id': file['id'], 'primary_folder_id': folder['id'],
        'current_dropbox_reference': {'file_id': file['id'], 'folder_id': folder['id'], 'file_path': file['path_display'], 'folder_path': folder['path_display'],
             'file_revision': file['rev'], 'file_bytes': file['size'], 'image_url': review['image_url'], 'folder_url': review['folder_url'], 'checked_utc': heads['checked_utc']},
        'scope': decision['scope'], 'review_record': rel(HERE / 'component-review.json'), 'source_review_snapshot': review_snapshot,
        'source_offer_refs': [], 'related_offer_refs': ['O029'], 'existing_platform_match_confirmed': False,
        'platform_mapping': {'status': 'EXACT_INDIVIDUAL_GOLD_OFFER_UNCONFIRMED', 'related_white_arrangement_offer_ref': 'O029', 'scope': review['platform_mapping']},
        'missing_photographs': review['missing_photographs'], 'source_photo_originality_authenticated': False, 'owner_manufacture_confirmed': False,
        'root_verified_cached_thumbnail': {'snapshot': preview, 'sha256': thumb['sha256'], 'bytes': thumb['bytes'], 'is_original_byte_hash': False,
             'original_bytes_verified': False, 'original_content_hash_from_baseline': source['selected_asset']['content_hash'], 'new_original_download': False}, 'imported_utc': now}
    parent['size_finish_variants'][vid] = node; p['reviews'][cid] = parent
    p['asset_assignment_overrides'][file['id']] = {'file_id': file['id'], 'folder_id': folder['id'], 'component_ids': [cid], 'size_finish_variant_ids': [vid],
        'exact_file_only': True, 'whole_folder_identity_approved': False, 'review_record': node['review_record'],
        'assignment_status': 'OWNER_KEPT_SELECTED_GOLD_FINISH;CACHED_THUMBNAIL_ONLY;PHYSICAL_CAST_AND_SPECS_UNVERIFIED'}
    sys.path.insert(0, str(ROOT / 'components/scripts'))
    from review_decision_counts import identity_counts
    u['identity_confirmation_counts'] = identity_counts(u)
    assert u['identity_confirmation_counts']['explicit_size_finish_variant_names'] == before['user']['identity_confirmation_counts']['explicit_size_finish_variant_names'] + 1
    assert u['identity_confirmation_counts']['components_with_any_identity_scope'] == before['user']['identity_confirmation_counts']['components_with_any_identity_scope']
    summary = {'batch': BATCH, 'recorded_utc': now, 'receipt': rel(HERE / 'import-receipt.json'), 'component_id': cid, 'size_finish_variant_id': vid,
        'new_finish_name_approvals': 1, 'new_parent_identity_approvals': 0, 'new_registered_BC_component_ids': [], 'new_full_specification_approvals': 0,
        'root_new_private_original_downloads': 0, 'remote_mutations': 0, 'workbook_export_pending': True}
    cp['parallel_import_queue'].append({'scope_kind': 'EXISTING_COMPONENT_GOLD_FINISH_NAME_ONLY', 'receipt': rel(package_path), 'receipt_sha256': digest,
        'approval_imported': True, 'import_receipt': summary['receipt'], 'status': 'EXACT_NAME_APPLIED;SIX_PROPOSALS_UNACCEPTED;THUMBNAIL_ONLY'})
    c['parallel_import_queue'] = copy.deepcopy(cp['parallel_import_queue'])
    for target in [cp, c]: target['last_parallel_import'] = copy.deepcopy(summary)
    p['latest_parallel_import'] = copy.deepcopy(summary)
    for target in docs.values(): target['updated_utc'] = now
    root['current_component_review'] = copy.deepcopy(c)
    assert all(cp[k] == v for k, v in before['walkthrough'].items() if k.startswith('current_'))
    assert u['decisions'] == before['user']['decisions'] and u['specification_decisions'] == before['user']['specification_decisions']
    assert all(sha(paths[k]) == v for k, v in guards.items()) and all(sha(Path(k)) == v for k, v in protected.items())
    write(HERE / 'before-import.json', before); write(HERE / 'existing-parent-identity.json', {'prior_owner_decision': prior, 'current_review_overlay': parent | {'size_finish_variants': {}}, 'new_owner_approval': False})
    write(HERE / 'identity-approval.json', decision); write(HERE / 'component-review.json', node); write(HERE / 'source-manifest.json', {'files': frozen, 'verified_messages': verified, 'source_package_sha256': digest})
    for k, path in paths.items(): write(path, docs[k])
    write(HERE / 'import-receipt.json', {'status': 'APPLIED;INDEPENDENT_READBACK_REQUIRED', 'summary': summary, 'protected_sha256': protected, 'shared_after_sha256': {k: sha(v) for k, v in paths.items()}})
    print(json.dumps({'batch': BATCH, 'status': 'APPLIED;INDEPENDENT_READBACK_REQUIRED', 'new_finish_names': 1, 'new_parent_name_approvals': 0, 'new_specification_approvals': 0, 'frozen_files': len(frozen)}))


if __name__ == '__main__': main()
