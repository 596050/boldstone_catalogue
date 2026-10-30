"""Import an owner-named group and an individual source's partial face-size instruction."""
import copy
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REVIEWS = ROOT / 'components/reviews'
read = lambda p: json.loads(p.read_text())
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
rel = lambda p: str(p.relative_to(ROOT))


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.tmp')
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    temp.replace(path)


def apply(batch):
    groups = {
        21: {'folder': 'oval-white-confirmation-import-20261019', 'sha': '1285aac9e052020e17114899360c11e79ba2a8708736c8adad3c9fe2a9ac0cd7',
             'seal': '0c942f28e82d5c5383b2ffa41e4a0ef4a2219fb4e55cff7c2b855ab6aa2b4b56', 'source_count': 32,
             'review_suffix': '/oval-white-name-check/REVIEW.json', 'key': 'FINGERPRINT-OVAL-WHITE-G156007',
             'file_id': 'id:cnqzTNngPVsAAAAAAAyhDQ', 'image_suffix': '__007.png'},
        23: {'folder': 'wavy-verdigris-confirmation-import-20261019', 'sha': 'f2cc2492b33105b5190032864139e34c67eb2770a8314f407dccd373e7b8a864',
             'seal': '66abd27bdc7f91b78922d31a173aa7043c9980f952332bec06426514ae6c669d', 'source_count': 33,
             'review_suffix': '/wavy-verdigris-name-check/REVIEW.json', 'key': 'FINGERPRINT-WAVY-VERDIGRIS-G158036',
             'file_id': 'id:cnqzTNngPVsAAAAAAAyhWA', 'image_suffix': '__036.png'},
        25: {'folder': 'double-curl-verdigris-manufacture-import-20261019', 'sha': '4aeb8bdc9c1d7110a4567e51526093c1b6c531ea0f82b746bbe5199c4bfabfd5',
             'seal': 'ae166915ce82aefc0a45c4dfb99d7f934f148489d901266c0a0d4b4730387607', 'source_count': 30,
             'review_suffix': '/double-curl-verdigris-name-check/REVIEW.json', 'key': 'FINGERPRINT-DOUBLE-CURL-VERDIGRIS-G158013',
             'file_id': 'id:cnqzTNngPVsAAAAAAAyhUg', 'image_suffix': '__013.png', 'manufacture_only': True},
        28: {'folder': 'four-panel-verdigris-manufacture-import-20261019', 'sha': 'b0766d74d3a84cb98f95909dfb744d7602ef60202b6906f4e77ccb2e4e8252e5',
             'seal': 'c0bf09749fc0bd037e7a7efe6a75f215502b11b41c330d88ef4f9f2a187847fe', 'source_count': 30,
             'review_suffix': '/four-panel-verdigris-name-check/REVIEW.json', 'key': 'FINGERPRINT-FOUR-PANEL-VERDIGRIS-G158026',
             'file_id': 'id:cnqzTNngPVsAAAAAAAyhTA', 'image_suffix': '__026.png', 'manufacture_only': True,
             'production_literal': 'Yes, physically made', 'visual_suffix': '/four-panel-verdigris-production-check/GROUPED_SOURCE_VISUAL_REVIEW.json'},
        32: {'folder': 'three-panel-verdigris-manufacture-import-20261019', 'sha': '20262f867dcf7b78c0f0ead7763507783b54b11f33a1caa94b25348569cb45ce',
             'seal': 'e97fd39e711268a11fe30ebeb50c9e181a8616fd8ceef81272c01ca998337970', 'source_count': 31,
             'review_suffix': '/three-panel-verdigris-name-check/REVIEW.json', 'key': 'FINGERPRINT-THREE-PANEL-VERDIGRIS-G160006',
             'file_id': 'id:cnqzTNngPVsAAAAAAAyhPA', 'image_suffix': '__006.png', 'manufacture_only': True,
             'production_literal': 'Yes, physically made', 'visual_suffix': '/three-panel-verdigris-production-check/GROUPED_SOURCE_VISUAL_REVIEW.json',
             'exact_file_AI_declaration': True},
        37: {'folder': 'four-panel-row-verdigris-manufacture-import-20261019', 'sha': '5d24ead382f220fc929be4915e28b360754ccbea04a49183eda9603c0236c445',
             'seal': 'b0809180b733311ae95f411a1dc81c2eed16c54273074e08e7485ed507df8ab1', 'source_count': 31,
             'review_suffix': '/four-panel-row-verdigris-name-check/REVIEW.json', 'key': 'FINGERPRINT-FOUR-PANEL-ROW-VERDIGRIS-G160005',
             'file_id': 'id:cnqzTNngPVsAAAAAAAyhPg', 'image_suffix': '__005.png', 'manufacture_only': True,
             'production_literal': 'Yes, physically made', 'visual_suffix': '/four-panel-row-verdigris-production-check/GROUPED_SOURCE_VISUAL_REVIEW.json',
             'exact_file_AI_declaration': True},
        42: {'folder': 'asymmetric-spiral-verdigris-manufacture-import-20261019', 'sha': '3a8509c472ab8950b151f193c3c3f1f284a8b3300f9a85565fee235f1f4cba0c',
             'seal': '614d136e39e25507f050cab82610e8e77000fa466368bb007ccd8ddae154f79b', 'source_count': 31,
             'review_suffix': '/asymmetric-spiral-verdigris-name-check/REVIEW.json', 'key': 'FINGERPRINT-ASYMMETRIC-SPIRAL-VERDIGRIS-G160003',
             'file_id': 'id:cnqzTNngPVsAAAAAAAyhQQ', 'image_suffix': '__003.png', 'manufacture_only': True,
             'production_literal': 'Yes physically made', 'visual_suffix': '/asymmetric-spiral-verdigris-production-check/GROUPED_SOURCE_VISUAL_REVIEW.json',
             'exact_file_AI_declaration': True},
        46: {'folder': 'looped-ridge-verdigris-manufacture-import-20261019', 'sha': 'c99b19bc4f6b5831432dbd6e33a4b599e8b5ee82fdd5fdaf661ecb7bc91129ff',
             'seal': 'eedc6e1a1808f9da5c5c73ecf6647bddfbf2e07411bf6f277750098c0ec1b712', 'source_count': 32,
             'review_suffix': '/looped-ridge-verdigris-name-check/REVIEW.json', 'key': 'FINGERPRINT-LOOPED-RIDGE-VERDIGRIS-G158032',
             'file_id': 'id:cnqzTNngPVsAAAAAAAyhVQ', 'image_suffix': '__032.png', 'manufacture_only': True,
             'production_literal': 'Yes, physically made', 'visual_suffix': '/looped-ridge-verdigris-production-check/GROUPED_SOURCE_VISUAL_REVIEW.json',
             'exact_file_AI_declaration': True}
    }
    group = groups.get(batch)
    here = REVIEWS / f'parallel-import-2026-10-19-batch{batch}'
    paths = {'user': REVIEWS / 'user_classifications.json', 'progress': REVIEWS / 'specification_review_progress.json',
             'walkthrough': REVIEWS / 'walkthrough_checkpoint.json', 'component': ROOT / 'components/checkpoint.json',
             'root': ROOT / 'checkpoint.json'}
    docs = {key: read(path) for key, path in paths.items()}
    if (here / 'import-receipt.json').exists():
        receipt = read(here / 'import-receipt.json')
        assert receipt['source_design_key'] in docs['progress']['source_design_reviews']
        for ledger, did in receipt['decision_ids'].items():
            assert sum(x['decision_id'] == did for x in docs['user'][ledger]) == 1
        print(json.dumps({'batch': batch, 'status': 'ALREADY_IMPORTED_IDEMPOTENT_NO_WRITE'}))
        return
    folder = ROOT / ('components/parallel-reviews/fingerprint-unresolved-groups-2026-10-19/' + group['folder']
                     if group else 'components/parallel-reviews/soundwave-2026-10-19/owner-face-dimensions-80x60')
    package_path = folder / 'IMPORT_PACKAGE.json'
    expected = (group['sha'] if group else
                '7c737b14495eb8e1dd4571f1983a6a7bfc343b7cff305ca5c129d20ff6bedef3')
    assert sha(package_path) == expected
    package, files, snapshots = read(package_path), [], {}

    def freeze(path, digest, source=None, suffix=None):
        path = Path(path)
        assert sha(path) == digest
        target = here / 'sources' / (digest + (suffix or path.suffix))
        target.parent.mkdir(exist_ok=True)
        if target.exists(): assert sha(target) == digest
        else: target.write_bytes(path.read_bytes())
        files.append({'source': str(source or path), 'snapshot': rel(target), 'sha256': digest, 'bytes': target.stat().st_size})
        snapshots[str(source or path)] = rel(target)
        return rel(target)

    freeze(package_path, expected)
    original_verification = None
    if group:
        seal_path = folder / 'SEALED_PACKAGE_MANIFEST.json'
        assert sha(seal_path) == group['seal']
        freeze(seal_path, sha(seal_path))
        for item in read(seal_path)['files']: freeze(item['path'], item['sha256'])
        manifest = read(Path(package['frozen_sources']['path']))
        assert len(manifest['files']) == group['source_count']
        for item in manifest['files']: freeze(item['frozen_path'], item['sha256'], item['source_path'])
        name = None if group.get('manufacture_only') else read(ROOT / snapshots[package['owner_name_approvals'][0]['decision']['path']])
        production = read(ROOT / snapshots[package['owner_production_confirmations'][0]['decision']['path']])
        review_path = next(x['snapshot'] for x in files if x['source'].endswith(group['review_suffix']))
        review = read(ROOT / review_path)
        owners = [production['owner_evidence']] + ([name['owner_evidence']] if name else [])
        preview = freeze(review['cached_primary_preview']['path'], review['cached_primary_preview']['sha256'])
        key, fid, folder_id = group['key'], group['file_id'], review['primary_folder']['id']
        source_head = review['primary_image']
        if batch in [23, 25, 28, 32, 37, 42, 46]:
            visual_suffix = group.get('visual_suffix') or ('/wavy-verdigris-production-check/GROUPED_SOURCE_VISUAL_REVIEW.json' if batch == 23 else '/double-curl-verdigris-production-check/GROUPED_SOURCE_VISUAL_REVIEW.json')
            visual_path = next(x['snapshot'] for x in files if x['source'].endswith(visual_suffix))
            visual = read(ROOT / visual_path)
            original = Path(visual['cached_original']['path'])
            assert sha(original) == visual['cached_original']['sha256']
            assert original.stat().st_size == source_head['size']
            content = original.read_bytes()
            assert content.startswith(b'\x89PNG\r\n\x1a\n')
            block_hashes = b''.join(hashlib.sha256(content[i:i + 4 * 1024 * 1024]).digest() for i in range(0, len(content), 4 * 1024 * 1024))
            assert hashlib.sha256(block_hashes).hexdigest() == source_head['content_hash']
            if batch == 23 or group.get('exact_file_AI_declaration'): assert b'trainedAlgorithmicMedia' in content and b'BytePlus_ModelArk' in content
            original_verification = {'original_snapshot': freeze(original, sha(original), suffix='.png'),
                'sha256': sha(original), 'dropbox_content_hash': source_head['content_hash'],
                'embedded_AI_creation_declaration_present': True if batch == 23 or group.get('exact_file_AI_declaration') else None, 'embedded_signature_verified': False,
                'source_origin_evidence': visual['source_origin_evidence'],
                'scope': 'Cached original bytes and native revision verified; declaration presence does not authenticate a physical object or client installation.'}
    else:
        freeze(package['manifest']['path'], package['manifest']['sha256'])
        for item in read(Path(package['manifest']['path']))['files']: freeze(item['path'], item['sha256'])
        dimension = read(ROOT / snapshots[package['decision']['path']])
        owners = [read(ROOT / snapshots[package['owner_evidence']['path']])]
        review_path = next(x['snapshot'] for x in files if x['source'].endswith('/before-dimensions/REVIEW.json'))
        review = read(ROOT / review_path)
        source_receipt_path = folder.parent / 'evidence/current-source-receipt.json'
        freeze(source_receipt_path, sha(source_receipt_path))
        source_receipt = read(source_receipt_path)
        original = Path(source_receipt['local_original'])
        assert sha(original) == source_receipt['sha256'] == '2521d4d9178a83d3f4c6096dcddc9bdd9d660307cf2f5ab12096b167af9e0c92'
        assert original.stat().st_size == 3079361
        preview = freeze(original, sha(original))
        key, fid, folder_id = 'SOUNDWAVE-WHITE-G310003', 'id:cnqzTNngPVsAAAAAAAylhg', 'id:cnqzTNngPVsAAAAAAAyjEA'
        source_head = source_receipt['file_head']
    targets = {x['line']: x for x in owners}
    verified, last = [], None
    with Path(owners[0]['transcript']).open('rb') as stream:
        for number, raw in enumerate(stream, 1):
            if number > max(targets): break
            item = json.loads(raw)
            payload = item.get('payload', {})
            if number == 1: assert payload['id'] == package['source_owner_session']
            if item.get('type') != 'response_item' or payload.get('type') != 'message': continue
            text = '\n'.join(x.get('text', '') for x in payload.get('content', []) if x.get('type') in ['input_text', 'output_text', 'text'])
            actual = {'transcript': owners[0]['transcript'], 'line': number, 'timestamp': item['timestamp'],
                      'role': payload['role'], 'text': text, 'text_sha256': hashlib.sha256(text.encode()).hexdigest(),
                      'raw_line_sha256': hashlib.sha256(raw).hexdigest()}
            if payload['role'] == 'assistant' and payload.get('phase') == 'final_answer' and text.strip(): last = actual
            if number in targets:
                e = targets[number]
                assert payload['role'] == 'user' and text == e['text'] and item['timestamp'] == e['timestamp']
                assert actual['text_sha256'] == e.get('text_sha256_utf8', e.get('text_sha256'))
                assert last and (group['image_suffix'] if group else '__003.png') in last['text']
                verified.extend([last, actual])
    assert len(verified) == (4 if group and not group.get('manufacture_only') else 2)
    heads = read(here / 'current-reference-check.json')
    head = next(x['file'] for x in heads['metadata'] if x.get('file'))
    parent = next(x['folder'] for x in heads['metadata'] if x.get('folder'))
    assert all(head[k] == source_head[k] for k in ['id', 'rev', 'size', 'path_display'])
    assert head['id'] == fid and parent['id'] == folder_id and head['path_display'].rsplit('/', 1)[0] == parent['path_display']
    before, hashes = copy.deepcopy(docs), {key: sha(path) for key, path in paths.items()}
    user, progress, cp, component = (docs[key] for key in ['user', 'progress', 'walkthrough', 'component'])
    assert docs['root']['current_component_review'] == component
    assert key not in progress.get('source_design_reviews', {}) and fid not in progress['asset_assignment_overrides']
    protected = {str(path): sha(path) for path in [ROOT / 'components/evidence/component_register.json',
        ROOT / cp['register_workbook'], ROOT / cp['current_review_record'], ROOT.parent / 'Boldstone_Wall_Sculptures_Matched_All_Fields_2026-10-15.xlsx']}
    now = datetime.now(timezone.utc).isoformat()
    links = review['browser_links'] if group else {'image': review['image_url'], 'folder': review['folder_url']}
    record = {'source_design_key': key, 'source_asset_id': fid, 'source_folder_id': folder_id,
              'source_path_display': head['path_display'], 'source_folder_path_display': parent['path_display'],
              'image_link': links['image'], 'folder_link': links['folder'], 'source_file_revision': head['rev'],
              'source_file_bytes': head['size'], 'current_reference_check': rel(here / 'current-reference-check.json'),
              'source_review_snapshot': review_path, 'root_viewed_reference_snapshot': preview,
              'source_image_authenticated_as_original_photo': False, 'physical_specs_verified': False,
              'component_ids': [], 'new_registered_BC_component_ids': [], 'specification_fields_fully_approved': [],
              'all_six_complete_specification_groups_pending': True, 'owner_estimates_accepted': False,
              'specifications': copy.deepcopy(review['specifications']), 'imported_utc': now,
              'source_package_sha256': expected, 'existing_squarespace_shopify_match_confirmed': False}
    decision_ids = {}
    if group:
        assert owners[0]['text'] == group.get('production_literal', 'physically made')
        if name: assert owners[1]['text'] == 'Keep “' + name['approved_name'] + '”'
        record.update({'record_kind': ('OWNER_NAMED_GROUP_SOURCE' if name else 'GROUP_SOURCE_NAME_PENDING') + ';MEMBER_IDENTIFICATION_DEFERRED_BY_OWNER',
            'canonical_source_name': name['approved_name'] if name else package['candidate_label_not_approved'], 'identity_confirmed': bool(name),
            'owner_stated_design_physically_made': True, 'physical_production_independently_verified': False,
            'component_members_status': 'DEFERRED_BY_OWNER_GROUP_PHOTO_POLICY',
            'component_member_identification_required_for_current_review': False,
            'group_photo_scope_record': progress['group_photo_review_policy']['approval_record']})
        if original_verification:
            record.update({'source_AI_creation_declaration_preserved': batch == 23 or group.get('exact_file_AI_declaration', False), 'embedded_signature_verified': False,
                           'source_origin_evidence': original_verification['source_origin_evidence'],
                           'root_original_verification': original_verification})
        if group.get('manufacture_only'):
            assert package['owner_name_approvals'] == [] and package['owner_estimates_accepted'] is False
            record.update({'proposed_name': package['candidate_label_not_approved'], 'catalogue_name_explicitly_approved': False,
                           'active_owner_question': review['question'], 'exact_file_AI_declaration_established': group.get('exact_file_AI_declaration', False),
                           'case_level_partial_AI_resolution_preserved': True})
        decisions = [('design_production_confirmation_decisions', production, verified[1])]
        if name: decisions.insert(0, ('source_design_name_decisions', name, verified[-1]))
        for ledger, source, evidence in decisions:
            decision = copy.deepcopy(source) | {'source_design_key': key, 'authoritative_user_evidence': evidence,
                'imported_utc': now, 'approval_record': rel(here / (ledger + '.json'))}
            user.setdefault(ledger, []).append(decision);decision_ids[ledger] = decision['decision_id']
            write(here / (ledger + '.json'), decision)
    else:
        assert owners[0]['text'] == 'use 80 × 60 cm' and dimension['face_dimensions_cm'] == [80, 60]
        record.update({'record_kind': 'INDIVIDUAL_WHOLE_SOURCE_REVIEW_PENDING_NAME', 'proposed_name': 'Soundwave — White',
            'canonical_source_name': 'Soundwave — White', 'identity_confirmed': False,
            'owner_stated_face_dimensions_cm_in_stated_order': [80, 60], 'face_dimensions_state': 'OWNER_STATED',
            'active_owner_question': 'Keep “Soundwave — White” for this complete sculpture?',
            'historical_brochure_face_cm': [60, 60], 'historical_source_applicability_unconfirmed': True,
            'missing_photographs': review['missing_photographs'], 'owner_stated_design_physically_made': False,
            'production_existence_state': 'NOT_CONFIRMED_BY_THIS_DIMENSION_INSTRUCTION'})
        record['specifications']['dimensions'] = {'display': '80 × 60 cm face — owner-stated; approximately 6 cm depth — unapproved estimate',
            'status': 'OWNER_STATED_FACE_ONLY;DEPTH_UNAPPROVED', 'face_dimensions_cm_in_stated_order': [80, 60],
            'depth_proposal_cm': 6, 'depth_owner_approved': False, 'independently_measured': False}
        decision = copy.deepcopy(dimension) | {'decision_id': 'UGR-G310:OWNER-FACE-SIZE:LINE25316',
            'source_design_key': key, 'authoritative_user_evidence': verified[-1], 'preceding_question_evidence': verified[0],
            'imported_utc': now, 'approval_record': rel(here / 'source-face-dimension-decision.json')}
        user.setdefault('source_dimension_decisions', []).append(decision)
        decision_ids['source_dimension_decisions'] = decision['decision_id']
        record['owner_face_dimension_record'] = decision['approval_record']
        write(here / 'source-face-dimension-decision.json', decision)
    progress.setdefault('source_design_reviews', {})[key] = record
    progress['asset_assignment_overrides'][fid] = {'source_design_key': key, 'file_id': fid, 'folder_id': folder_id,
        'component_ids': [], 'family': 'Fingerprint' if group else 'Soundwave',
        'assignment_status': ('OWNER_MANUFACTURE_CONFIRMED_GROUP_REFERENCE;NAME_PENDING' if group.get('manufacture_only') else 'OWNER_NAMED_GROUP_REFERENCE') if group else 'WHOLE_SOURCE_REVIEW;OWNER_FACE_SIZE_ONLY;NAME_PENDING',
        'exact_component_or_stock_count_verified': False, 'review_record': rel(here / 'source-design-review.json')}
    summary = {'batch': batch, 'recorded_utc': now, 'receipt': rel(here / 'import-receipt.json'), 'source_design_key': key,
        'new_source_name_approvals': 1 if group and not group.get('manufacture_only') else 0,
        'new_source_production_confirmations': 1 if group else 0, 'new_source_face_dimension_instructions': 1 if batch == 22 else 0,
        'new_registered_BC_component_ids': [], 'new_full_specification_approvals': 0, 'owner_estimates_accepted': False,
        'main_Concave_MCP4_question_preserved': True, 'group_photo_policy_and_G050_preserved': True,
        'root_new_private_original_downloads': 0, 'remote_mutations': 0, 'workbook_export_pending': True}
    cp['parallel_import_queue'].append({'scope_kind': ('SOURCE_MANUFACTURE_ONLY;NAME_PENDING' if group.get('manufacture_only') else 'SOURCE_NAME_EXISTENCE') if group else 'SOURCE_PARTIAL_FACE_DIMENSIONS',
        'receipt': rel(package_path), 'receipt_sha256': expected, 'approval_imported': True, 'import_receipt': summary['receipt'],
        'status': 'APPLIED_EXACT_OWNER_SCOPE;ACTUAL_SPECIFICATIONS_INCOMPLETE'})
    component['parallel_import_queue'] = copy.deepcopy(cp['parallel_import_queue'])
    for target in [cp, component]: target['last_parallel_import'] = copy.deepcopy(summary);target['updated_utc'] = now
    for field in ['next_serialized_parallel_import', 'completed_serialized_parallel_import']:
        cp[field] = {'status': 'APPLIED_AND_VERIFIED', 'receipt': summary['receipt'], 'completed_utc': now}
    progress['latest_parallel_import'] = copy.deepcopy(summary)
    user['updated_utc'] = progress['updated_utc'] = now
    docs['root']['current_component_review'] = copy.deepcopy(component);docs['root']['updated_utc'] = now
    assert progress['reviews'] == before['progress']['reviews']
    assert all(cp[k] == v for k, v in before['walkthrough'].items() if k.startswith('current_'))
    assert cp['deferred_reviews'] == before['walkthrough']['deferred_reviews']
    assert all(sha(paths[k]) == v for k, v in hashes.items())
    assert all(sha(Path(k)) == v for k, v in protected.items())
    write(here / 'before-import.json', before)
    write(here / 'source-manifest.json', {'source_package': rel(package_path), 'source_package_sha256': expected,
        'files': files, 'verified_messages': verified, 'root_new_private_original_downloads': 0})
    write(here / 'source-design-review.json', record)
    for name, path in paths.items(): write(path, docs[name])
    write(here / 'import-receipt.json', {'status': 'APPLIED;INDEPENDENT_READBACK_REQUIRED', 'source_design_key': key,
        'decision_ids': decision_ids, 'summary': summary, 'protected_sha256': protected,
        'shared_after_sha256': {k: sha(path) for k, path in paths.items()}})
    print(json.dumps({'batch': batch, 'status': 'APPLIED;INDEPENDENT_READBACK_REQUIRED', 'frozen_references': len(files)}))


if __name__ == '__main__':
    for batch in ([int(x) for x in sys.argv[1:]] if len(sys.argv) > 1 else [21, 22]):
        apply(batch)
