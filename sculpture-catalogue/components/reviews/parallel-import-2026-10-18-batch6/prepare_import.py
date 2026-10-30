"""Freeze a sealed package and independently verify exact owner evidence and revision chains."""
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PEER = ROOT / 'components/parallel-reviews/panel-plant-raked-2026-10-18'
PACKAGE = PEER / 'IMPORT_PACKAGE.json'
EXPECTED_PACKAGE = 'c92fcd8f372d5d8c0552414ed16082bfa561bd9e0ccee57a746a3147e30d6b49'
OWNER = '01a13fe6-495b-7253-b923-31823b4cbca8'
read = lambda p: json.loads(p.read_text())
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
rel = lambda p: str(p.relative_to(ROOT))


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def main():
    output = HERE / 'source-manifest.json'
    assert not output.exists(), 'Already prepared'
    assert sha(PACKAGE) == EXPECTED_PACKAGE
    package = read(PACKAGE)
    assert package['owner_session'] == OWNER and package['status'] == 'READY_FOR_MAIN_OWNER_IMPORT'
    assert package['kept_working_card_count'] == 9 and package['fully_confirmed_specification_item_count'] == 0
    assert package['partially_confirmed_specification_item_count'] == 6
    cp = read(ROOT / 'components/reviews/walkthrough_checkpoint.json')
    for cid in package['component_ids']:
        lane = next(x for x in cp['parallel_owner_reviews'] if x['component_id'] == cid)
        assert lane['owner_session'] == OWNER
    expected = {}
    for artifact in package['root_artifacts'] + [a for item in package['items'] for a in item['artifacts']]:
        path = Path(artifact['path'])
        if path in expected:
            assert expected[path] == artifact['sha256']
        expected[path] = artifact['sha256']
    for path, digest in package['referenced_image_hashes'].items():
        path = Path(path)
        if path in expected:
            assert expected[path] == digest
        expected[path] = digest
    assert all(sha(path) == digest for path, digest in expected.items())
    assert sha(Path(package['coordinator_acknowledgement'])) == package['coordinator_acknowledgement_sha256']
    assert sha(Path(package['source_snapshot_path'])) == package['source_snapshot_sha256']
    assert read(Path(package['batch_validation_path']))['result'] == 'PASS'
    expected[PACKAGE] = EXPECTED_PACKAGE
    source_map = {}
    for path, digest in expected.items():
        try:
            suffix = path.relative_to(PEER)
            dest = HERE / 'sources/panel-plant-raked-2026-10-18' / suffix
        except ValueError:
            dest = HERE / 'sources/external' / (digest + '-' + path.name)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dest)
        assert sha(dest) == digest
        source_map[str(path)] = {'snapshot': rel(dest), 'sha256': digest, 'bytes': path.stat().st_size}
    owner_refs = []
    normalized = []
    for item in package['items']:
        approval_path, working_path = Path(item['approval_path']), Path(item['working_entry_path'])
        approval, working = read(approval_path), read(working_path)
        assert sha(approval_path) == item['approval_sha256'] and sha(working_path) == item['working_entry_sha256']
        assert approval['owner_session'] == OWNER and approval['name_and_visual_identity_kept']
        assert not approval['specifications_explicitly_confirmed'] and not approval['fully_confirmed_specification_groups']
        validation = read(Path(item['validation_path']))
        assert sha(Path(item['validation_path'])) == item['validation_sha256'] and validation['result'] == 'PASS'
        assert validation['working_entry_sha256'] == sha(working_path)
        original_validation = read(Path(item['original_keep_validation_path']))
        before = working_path.parent / 'component-review.before-keep.json'
        assert sha(before) == original_validation['before_copy_sha256']
        assert original_validation['approval_sha256'] == sha(approval_path)
        old_ids = [x['proposal_id'] for x in read(before)['specification_review_items']]
        assert old_ids == [x['proposal_id'] for x in working['specification_review_items']] and len(old_ids) == 6
        assert all(not x['owner_confirmed'] for x in working['specification_review_items'])
        for correction in item['post_keep_corrections']:
            assert sha(Path(correction['path'])) == correction['sha256']
            correction_data = read(Path(correction['path']))
            candidates = [p for p in working_path.parent.glob('*.json') if sha(p) == correction_data['before_sha256']]
            assert candidates and correction_data['before_sha256'] == original_validation['working_entry_sha256']
            previous = read(candidates[0])
            assert [x for x in previous['specification_review_items'] if x['group'] != 'dimensions_and_depth'] == [x for x in working['specification_review_items'] if x['group'] != 'dimensions_and_depth']
        owner_refs.append(approval['source_user_statement'])
        primary, folder = working['primary_image'], working['containing_folder']
        normalized.append({'source_decision_id': item['decision_id'], 'component_id': item['component_id'],
            'variant_id': item['configuration_key'], 'review_id': item['review_id'], 'name': item['working_name'],
            'review_number': working['review_number'], 'receipt': source_map[str(approval_path)]['snapshot'],
            'receipt_sha256': sha(approval_path), 'current_review': source_map[str(working_path)]['snapshot'],
            'current_review_sha256': sha(working_path), 'before_keep_review': source_map[str(before)]['snapshot'],
            'before_keep_review_sha256': sha(before), 'source_owner_statement': approval['source_user_statement'],
            'primary': primary, 'folder': folder, 'partial_groups': item['partially_confirmed_specification_groups'],
            'post_keep_corrections': item['post_keep_corrections']})
    correction_names = ['panel-curves-patina/owner-correction-001.json',
        'panel-curves-beige-process/owner-role-confirmation-001.json', 'raked-dimensions-owner-confirmation-001.json']
    correction_refs = []
    for name in correction_names:
        path = PEER / name
        data = read(path)
        owner_refs.append(data['source_user_statement'])
        correction_refs.append({'receipt': source_map[str(path)]['snapshot'], 'sha256': sha(path),
            'source_decision_id': data.get('correction_id', data.get('confirmation_id')),
            'source_owner_statement': data['source_user_statement']})
    transcript = Path(owner_refs[0]['transcript_path'])
    assert all(Path(x['transcript_path']) == transcript for x in owner_refs)
    transcript_rows = {}
    session = None
    wanted = {x['line'] for x in owner_refs} | {x['preceding_review_card']['line'] for x in owner_refs}
    for number, line in enumerate(transcript.open(), 1):
        if number not in wanted and session is not None:
            continue
        obj = json.loads(line)
        if obj.get('type') == 'session_meta':
            session = obj['payload']['id']
        if number in wanted:
            payload = obj['payload']
            assert obj['type'] == 'response_item' and payload['type'] == 'message'
            text = '\n'.join(x.get('text', '') for x in payload.get('content', []) if isinstance(x, dict))
            transcript_rows[number] = {'role': payload['role'], 'timestamp': obj['timestamp'], 'text': text,
                'sha256': hashlib.sha256(text.encode()).hexdigest()}
    assert session == OWNER
    for source in owner_refs:
        actual, preceding = transcript_rows[source['line']], source['preceding_review_card']
        assert actual['role'] == 'user' and actual['text'] == source['text'] and actual['sha256'] == source['text_sha256']
        assert actual['timestamp'] == source['timestamp']
        card = transcript_rows[preceding['line']]
        assert card['role'] == 'assistant' and card['text'] == preceding['text'] and card['sha256'] == preceding['text_sha256']
    refs = {}
    for item in normalized:
        primary, folder = item['primary'], item['folder']
        refs[primary['file_id']] = {'type': 'file', 'rev': primary['rev'], 'bytes': primary['bytes']}
        refs[folder['file_id']] = {'type': 'folder', 'path_display': folder['path_display']}
    flag = read(PEER / 'raked-spiral-1-white/photo-assignment-discrepancy.json')
    image = flag['fresh_original_rechecked']
    refs[image['id']] = {'type': 'file', 'rev': image['rev'], 'bytes': image['size']}
    refs[flag['folder_id']] = {'type': 'folder', 'path_display': image['path_display'].rsplit('/', 1)[0]}
    manifest = {'status': 'PREPARED_OWNER_TRANSCRIPTS_AND_SOURCE_HASHES_VERIFIED',
        'prepared_utc': datetime.now(timezone.utc).isoformat(), 'owner_session': OWNER,
        'source_package': source_map[str(PACKAGE)]['snapshot'], 'source_package_sha256': EXPECTED_PACKAGE,
        'source_files': source_map, 'source_item_count': 9, 'source_correction_receipt_count': 3,
        'authoritative_messages_verified': len(transcript_rows), 'items': normalized, 'corrections': correction_refs,
        'reference_requests': refs, 'all_specification_groups': 54, 'partially_confirmed_groups': 6,
        'fully_confirmed_groups': 0, 'current_owner_review_not_changed': True}
    write(output, manifest)
    print(json.dumps({'status': manifest['status'], 'frozen_files': len(source_map),
        'verified_owner_and_preceding_card_messages': len(transcript_rows), 'name_receipts': 9,
        'other_owner_receipts': 3, 'reference_ids_to_refresh': len(refs), 'post_keep_correction_chains': 2}))


if __name__ == '__main__':
    main()
