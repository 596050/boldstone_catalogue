"""Prepare a sealed finish-name decision under an existing component."""
import argparse
import copy
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
read = lambda p: json.loads(p.read_text())
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
rel = lambda p: str(p.relative_to(ROOT))


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')


def prepare(batch, source, package_sha, variant, owner_line):
    out = ROOT / f'components/reviews/parallel-import-2026-10-19-batch{batch}'
    assert not (out / 'source-manifest.json').exists()
    package_path = ROOT / source / 'IMPORT_PACKAGE.json'
    assert sha(package_path) == package_sha
    package = read(package_path)
    files = {}

    def freeze(path, digest):
        path = Path(path)
        assert sha(path) == digest
        dest = out / 'sources' / (digest + path.suffix)
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            assert sha(dest) == digest
        else:
            dest.write_bytes(path.read_bytes())
        files[str(path)] = {'source': str(path), 'snapshot': rel(dest), 'sha256': digest, 'bytes': dest.stat().st_size}
        return rel(dest)

    freeze(package_path, package_sha)
    freeze(package['manifest']['path'], package['manifest']['sha256'])
    manifest = read(Path(package['manifest']['path']))
    for item in manifest['files']:
        assert Path(item['path']).stat().st_size == item['bytes']
        freeze(item['path'], item['sha256'])
    for key in ['fresh_source_receipt', 'visual_comparison']:
        freeze(package[key]['path'], package[key]['sha256'])
    approval = read(ROOT / files[package['decision']['path']]['snapshot'])
    owner = read(ROOT / files[package['owner_evidence']['path']]['snapshot'])
    preceding = read(ROOT / files[package['preceding_card']['path']]['snapshot'])
    expected = {x['line']: x for x in [owner, preceding]}
    verified = []
    with Path(owner['transcript']).open('rb') as stream:
        assert json.loads(next(stream))['payload']['id'] == package['owner_session']
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
            verified.append(copy.deepcopy(e) | {'verified_raw_line_sha256': hashlib.sha256(raw).hexdigest()})
    assert len(verified) == 2 and owner['line'] == owner_line
    assert approval['approved_finish_label'] in owner['text']
    assert approval['owner_name_finish_approved'] and approval['new_specification_approvals'] == 0
    assert approval['new_component_identity_Keeps'] == 0
    review_source = next(x['path'] for x in manifest['files'] if x['path'].endswith('/before-approval/REVIEW.json'))
    review_snapshot = files[review_source]['snapshot']
    assert sha(ROOT / review_snapshot) == approval['source_review_sha256']
    review = read(ROOT / review_snapshot)
    fresh = read(ROOT / files[package['fresh_source_receipt']['path']]['snapshot'])
    old_heads = {x['file']['id']: x['file'] for x in fresh['heads'] if x['metadata_type'] == 'file'}
    current = read(out / 'current-reference-check.json')
    heads = {x['request_id']: x.get('file', x.get('folder')) for x in current['metadata']}
    folder = heads[approval['folder_id']]
    originals = []
    for key in ['primary_image', 'overview_image']:
        image = review[key]
        actual, prior = heads[image['id']], old_heads[image['id']]
        assert actual['id'] == image['id'] and actual['size'] == prior['size'] == image['size']
        assert actual['rev'] == prior['rev'] and actual['path_display'] == prior['path_display'] == image['path_display']
        assert actual['path_display'].rsplit('/', 1)[0] == folder['path_display']
        snapshot = freeze(image['local_path'], image['sha256'])
        originals.append({'id': image['id'], 'snapshot': snapshot, 'sha256': image['sha256'], 'role': key,
                          'rev': actual['rev'], 'size': actual['size'], 'content_hash': image['content_hash']})
    cid = approval['component_id']
    parent = read(ROOT / 'components/reviews/specification_review_progress.json')['reviews'][cid]
    white = ROOT / parent['specification_approval']
    assert sha(white) == review['prior_approved_white']['approval_snapshot_sha256']
    freeze(white, sha(white))
    prior_approval_hashes = {str(white): sha(white)}
    for prior in parent.get('size_finish_variants', {}).values():
        path = ROOT / prior['identity_approval']
        freeze(path, sha(path))
        prior_approval_hashes[str(path)] = sha(path)
    field_order = [('dimensions', 'Dimensions/depth', 'dimensions_and_depth'), ('weight', 'Weight', 'weight'),
                   ('material_finish', 'Material', 'material'), ('fixings', 'Fixing', 'fixing'),
                   ('individual_price', 'Individual price', 'individual_price'), ('availability', 'Availability', 'availability')]
    proposals = []
    for source_key, label, group in field_order:
        value = review['proposed_specifications_for_this_finish'][source_key]
        assert value['status'].startswith('UNAPPROVED')
        proposals.append({'group': group, 'field': label, 'display': value['display'], 'proposal': value['display'],
                          'source_evidence_state': value['status'], 'owner_approved': False, 'physical_specs_verified': False})
    receipt = copy.deepcopy(approval) | {'fully_confirmed_specification_groups': [],
        'identity_scope': f"Existing {cid} design; owner-named {approval['approved_finish_label']} appearance/finish for {approval['target_position']}. No material chemistry or other-object approval.",
        'scope_note': approval['scope'] + ' Prior finish specification approvals do not approve this finish. ' + approval['material_scope']}
    card = {'specification_review_items': proposals, 'platform_mapping': {'status': 'UNCONFIRMED',
                'existing_component_platform_match_confirmed': parent['existing_platform_match_confirmed'],
                'no_platform_match_created_by_finish_name': True},
            'photo_selection_review': {'detail_primary_only': True, 'target_position': approval['target_position'],
                'source_comparison_snapshot': files[package['visual_comparison']['path']]['snapshot'],
                'same_physical_cast_across_images_confirmed': False}, 'production_status': None,
            'missing_photographs': {'source_missing': review['missing_photos'],
                'in_situ_and_matching_finish_series': 'Not established in this reviewed packet; broader availability unverified.'},
            'missing_specifications': [x['field'] for x in proposals], 'complete_pre_answer_review': review_snapshot}
    owner_path, card_path = out / 'normalized/owner.json', out / 'normalized/working.json'
    for path, value in [(owner_path, receipt), (card_path, card)]:
        write(path, value)
        files[str(path)] = {'source': str(path), 'snapshot': rel(path), 'sha256': sha(path), 'bytes': path.stat().st_size}
    detail, overview = review['primary_image'], review['overview_image']
    primary, overview_head = heads[detail['id']], heads[overview['id']]
    scope = f"Primary {detail['name']} is a detail crop. Named target: {approval['target_position']}. Same physical cast across photographs remains unverified; other objects are excluded."
    decision = {'component_id': cid, 'variant_id': variant, 'name': approval['approved_name'], 'scope_kind': 'size_finish_variant',
        'owner_session': package['owner_session'], 'source_decision_id': approval['review_id'] + ':' + variant + ':OWNER-LINE' + str(owner_line),
        'authoritative_owner_evidence': owner, 'preceding_review_card_evidence': preceding,
        'receipt_snapshot': rel(owner_path), 'receipt_sha256': sha(owner_path), 'pre_answer_review': review_snapshot,
        'pre_answer_review_sha256': sha(ROOT / review_snapshot), 'working_entry': rel(card_path), 'working_entry_sha256': sha(card_path),
        'primary_expected': {'file_id': detail['id'], 'path_display': primary['path_display'], 'rev': primary['rev'], 'size': primary['size'],
            'sha256': detail['sha256'], 'content_hash': detail['content_hash'], 'open_in_dropbox_url': review['image_url'], 'selection_reason': scope},
        'folder_expected': {'folder_id': folder['id'], 'path_display': folder['path_display'], 'open_in_dropbox_url': review['folder_url']},
        'image_url': review['image_url'], 'folder_url': review['folder_url'], 'review_number': None, 'owner_confirmed_fields': [],
        'depicted_component_position': approval['target_position'], 'photo_reference_scope': scope,
        'additional_source_references': [{'file_id': overview['id'], 'folder_id': folder['id'], 'file_path': overview_head['path_display'],
            'rev': overview_head['rev'], 'bytes': overview_head['size'], 'sha256': overview['sha256'], 'dropbox_content_hash': overview['content_hash'],
            'image_link': review['overview_url'], 'role': 'Workshop overview; named target only', 'same_physical_cast_as_detail_confirmed': False}]}
    result = {'family': 'Acanthus / G010 supplemental finishes', 'source_package': rel(package_path), 'source_package_sha256': package_sha,
        'source_package_snapshot': files[str(package_path)]['snapshot'], 'files': list(files.values()), 'decisions': [decision],
        'verified_messages': verified, 'arrangements': [], 'position_resolution_snapshots': [], 'allow_existing_component_ids': [cid],
        'expected_new_identity_scope_components': 0, 'prior_finish_approval_hashes': prior_approval_hashes,
        'import_constraints': ['Owner finish name only under existing design; no new component, stock, mould or six-field approval.',
            'Preserve prior approvals and exact detail/overview position scope; no whole-folder assignment or same-cast certification.'],
        'outstanding_followups': {'other_G010_objects': 'Unconfirmed context only; no approval inferred.',
            'G072': 'Separate allocated mixed-group review.', 'photo_gaps': review['missing_photos']}}
    write(out / 'source-manifest.json', result)
    write(out / 'source-original-receipts.json', {'status': 'PASS', 'entries': originals, 'root_fresh_metadata_heads': 3,
          'new_private_downloads': 0, 'peer_originals_reused_by_verified_hashes': True})
    print(json.dumps({'status': 'PASS', 'batch': batch, 'source_records': len(files), 'exact_messages': len(verified), 'new_specification_approvals': 0}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--batch', type=int, required=True)
    parser.add_argument('--source', required=True)
    parser.add_argument('--package-sha', required=True)
    parser.add_argument('--variant', required=True)
    parser.add_argument('--owner-line', type=int, required=True)
    args = parser.parse_args()
    prepare(args.batch, args.source, args.package_sha, args.variant, args.owner_line)
