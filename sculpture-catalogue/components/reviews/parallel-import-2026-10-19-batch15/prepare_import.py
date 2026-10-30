"""Verify the Moon Water Catcher and Moonwave owner Keeps and prepare scoped import inputs."""
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
read = lambda p: json.loads(p.read_text())
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
rel = lambda p: str(p.relative_to(ROOT))


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def intake():
    assert not (HERE / 'source-intake.json').exists()
    source = ROOT / 'components/parallel-reviews/moonwater-moonwave-2026-10-19/owner-name-import-20261019'
    package_path = source / 'IMPORT_PACKAGE.json'
    seal_path = source / 'SEALED_PACKAGE_MANIFEST.json'
    assert sha(package_path) == 'ba8c1864cfa15acb6c3183d44ea1225dcbcada840eaa92d18df3451c7d364587'
    assert sha(seal_path) == 'bddec11885190f1c3712e619ec426e99010eed74acf03e93976ca18a1b3c1452'
    package, seal = read(package_path), read(seal_path)
    assert package['owner_name_approval_count'] == 2 and not package['owner_specification_approvals']
    assert package['all_six_specification_groups_pending_for_each'] and package['owner_weight_estimate_acceptance_count'] == 0
    files = {}

    def freeze(path, digest, original=None):
        path = Path(path)
        assert sha(path) == digest
        key = str(Path(original or path).resolve())
        dest = HERE / 'sources' / (digest + path.suffix)
        dest.parent.mkdir(exist_ok=True)
        if dest.exists():
            assert sha(dest) == digest
        else:
            dest.write_bytes(path.read_bytes())
        files[key] = {'source': key, 'snapshot': rel(dest), 'sha256': digest, 'bytes': dest.stat().st_size}

    freeze(package_path, sha(package_path))
    freeze(seal_path, sha(seal_path))
    for item in seal['files']:
        freeze(item['path'], item['sha256'])
    frozen = read(Path(package['frozen_sources']['path']))
    assert len(frozen['files']) == 31
    for item in frozen['files']:
        freeze(item['frozen_path'], item['sha256'], item['source_path'])
    evidence = read(Path(package['exact_owner_transcript']['path']))
    expected = {x['line']: x for x in evidence['messages']}
    messages = []
    with Path(next(iter(expected.values()))['transcript']).open('rb') as stream:
        assert json.loads(next(stream))['payload']['id'] == package['source_owner_session']
        for number, raw in enumerate(stream, 2):
            if number > max(expected):
                break
            if number not in expected:
                continue
            e, actual = expected[number], json.loads(raw)
            payload = actual['payload']
            text = '\n'.join(x.get('text', '') for x in payload['content'] if x.get('type') in ['input_text', 'text'])
            assert payload['role'] == 'user' and text == e['text'] and actual['timestamp'] == e['timestamp']
            assert hashlib.sha256(text.encode()).hexdigest() == e['text_sha256_utf8']
            messages.append(dict(e, text_sha256=e['text_sha256_utf8'], raw_line_sha256=hashlib.sha256(raw).hexdigest()))
    assert len(messages) == 2
    refs = {}
    for item in package['owner_name_approvals']:
        review = read(ROOT / files[item['frozen_review']['path']]['snapshot'])
        owner = read(ROOT / files[item['decision']['path']]['snapshot'])
        assert owner['review_card_sha256'] == item['frozen_card']['sha256']
        assert owner['review_json_sha256'] == item['frozen_review']['sha256']
        assert not owner['specification_fields_approved'] and not owner['source_numerical_estimate_owner_accepted']
        assert review['proposed_name'] == owner['approved_name'] == item['approved_name']
        assert len(review['specifications']) == 6 and review['all_six_specification_fields_pending']
        for kind, key in [('file', 'primary_image'), ('folder', 'primary_folder')]:
            entry = review[key]
            refs[entry['id']] = {'kind': kind, 'expected': entry}
    result = {'source_package': rel(package_path), 'source_package_sha256': sha(package_path),
              'package_snapshot': files[str(package_path)]['snapshot'], 'files': list(files.values()),
              'verified_messages': messages, 'current_reference_targets': refs}
    write(HERE / 'source-intake.json', result)
    print(json.dumps({'status': 'PASS_INTAKE', 'frozen_sources': len(files), 'exact_owner_messages': 2, 'current_heads_required': len(refs)}))


def normalize():
    assert not (HERE / 'source-manifest.json').exists()
    intake = read(HERE / 'source-intake.json')
    package = read(ROOT / intake['package_snapshot'])
    files = {x['source']: x for x in intake['files']}
    originals = read(HERE / 'current-original-receipts.json')
    assert originals['status'] == 'PASS' and len(originals['entries']) == 2
    original_by_id = {x['id']: x for x in originals['entries']}
    decisions, new_files = [], []
    fields = ['dimensions_and_depth', 'weight', 'material', 'fixing', 'individual_price', 'availability']
    for item in package['owner_name_approvals']:
        review_source = files[item['frozen_review']['path']]
        owner_source = files[item['decision']['path']]
        card_source = files[item['frozen_card']['path']]
        review = read(ROOT / review_source['snapshot'])
        owner = read(ROOT / owner_source['snapshot'])
        text = (ROOT / card_source['snapshot']).read_text()
        rows = []
        for line in text.splitlines():
            if line.lstrip().startswith('|') and not set(line.replace('|', '').replace('-', '').replace(':', '').strip()) == set():
                cells = line.strip().strip('|').split('|', 1)
                if len(cells) == 2 and cells[0].strip().lower() not in ['specification', 'field']:
                    rows.append([x.strip() for x in cells])
        assert len(rows) == 6, (item['component_id'], rows)
        proposals = [dict(group=group, field=title, display=display, proposal=display,
                          complete_original_source_specification=source_value, owner_approved=False,
                          physical_specs_verified=False)
                     for group, (title, display), source_value in zip(fields, rows, review['specifications'].values())]
        normalized_owner = dict(owner, fully_confirmed_specification_groups=[], identity_scope='Depicted individual component / White name only', scope_note=owner['approval_scope'])
        supplement_path = files[review['source_review']['path']]['snapshot'] if 'source_review' in review else None
        supplement = read(ROOT / supplement_path) if supplement_path else {}
        mapping = review.get('platform_mapping', {'source_mapping': supplement.get('mapping'),
                     'source_public_offer': supplement.get('current_public_offer'),
                     'source_review_snapshot': supplement_path, 'owner_name_scope_only': True})
        scene_origin = review.get('scene_origin', supplement.get('scene_origin'))
        normalized_card = {'specification_review_items': proposals, 'platform_mapping': mapping,
                           'photo_selection_review': {'source_media_review': review['media_review'], 'primary_selection_change': review.get('primary_selection_change')}, 'production_status': None,
                           'missing_photographs': {'source_media_review': review['media_review'], 'source_photo_gaps': review.get('photo_gaps'), 'source_scene_origin': scene_origin, 'all_original_limits_retained': True},
                           'missing_specifications': [x['field'] for x in proposals], 'complete_source_review': review_source['snapshot']}
        name = item['review_id']
        receipt_path = HERE / 'normalized' / (name + '-owner.json')
        card_path = HERE / 'normalized' / (name + '-working.json')
        for path, value in [(receipt_path, normalized_owner), (card_path, normalized_card)]:
            write(path, value)
            new_files.append({'source': str(path), 'snapshot': rel(path), 'sha256': sha(path), 'bytes': path.stat().st_size})
        image = dict(review['primary_image'])
        folder = dict(review['primary_folder'])
        image['path'] = image.get('path', image.get('path_display'))
        folder['path'] = folder.get('path', folder.get('path_display'))
        original = original_by_id[image['id']]
        image_url = 'https://www.dropbox.com/preview' + quote(image['path'], safe='/')
        folder_url = 'https://www.dropbox.com/home' + quote(folder['path'], safe='/')
        decisions.append({'component_id': item['component_id'], 'variant_id': item['review_id'].removesuffix('-01'),
                          'name': item['approved_name'], 'scope_kind': 'size_finish_variant', 'owner_session': package['source_owner_session'],
                          'source_decision_id': item['review_id'] + ':OWNER-KEEP-LINE' + str(item['owner_evidence']['line']),
                          'authoritative_owner_evidence': next(x for x in intake['verified_messages'] if x['line'] == item['owner_evidence']['line']),
                          'preceding_review_card_evidence': {'card_snapshot': card_source['snapshot'], 'card_sha256': card_source['sha256'],
                                                           'binding': 'Exact frozen card and review hashes recorded in owner receipt'},
                          'receipt_snapshot': rel(receipt_path), 'receipt_sha256': sha(receipt_path),
                          'pre_answer_review': review_source['snapshot'], 'pre_answer_review_sha256': review_source['sha256'],
                          'working_entry': rel(card_path), 'working_entry_sha256': sha(card_path),
                          'primary_expected': {'file_id': image['id'], 'path_display': image['path'], 'rev': image['rev'], 'size': image['size'],
                                               'sha256': original['sha256'], 'content_hash': original['content_hash'], 'open_in_dropbox_url': image_url},
                          'folder_expected': {'folder_id': folder['id'], 'path_display': folder['path'], 'open_in_dropbox_url': folder_url},
                          'image_url': image_url, 'folder_url': folder_url, 'review_number': item['global_review'], 'owner_confirmed_fields': []})
    result = {'family': 'Moon Water Catcher / Moonwave', 'files': intake['files'] + new_files, 'decisions': decisions,
              'verified_messages': intake['verified_messages'], 'source_package': intake['source_package'],
              'source_package_sha256': intake['source_package_sha256'], 'source_package_snapshot': intake['package_snapshot'],
              'arrangements': [], 'position_resolution_snapshots': [],
              'import_constraints': ['Two quoted component names only; no numerical estimate or six-field approval.',
                                     'Preserve maker, local draft, archive and live offer conflicts independently.'],
              'outstanding_followups': {'source_conflicts': package['source_conflicts_retained'], 'full_peer_first_pass': package['family_first_pass']}}
    write(HERE / 'source-manifest.json', result)
    print(json.dumps({'status': 'PASS_NORMALIZED', 'decisions': len(decisions), 'root_source_records': len(result['files'])}))


if __name__ == '__main__':
    {'intake': intake, 'normalize': normalize}[sys.argv[1]]()
