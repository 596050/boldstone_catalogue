"""Freeze the sealed Moon/Shellwave source and verify four exact owner replies."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PEERS = ROOT / 'components/parallel-reviews'
SOURCE = PEERS / 'moon-shellwave-2026-10-18/IMPORT_PACKAGE.json'
EXPECTED = '992aa30440a96f8cf8afacf0ba9fd0e141dd89eed42f7c9236fed68b96d7cebe'
read = lambda p: json.loads(p.read_text())
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
rel = lambda p: str(p.relative_to(ROOT))


def write(p, j):
    p.parent.mkdir(parents=True, exist_ok=True)
    t = p.with_name(p.name + '.tmp')
    t.write_text(json.dumps(j, ensure_ascii=False, indent=2) + '\n')
    t.replace(p)


def main():
    assert not (HERE / 'source-manifest.json').exists()
    assert sha(SOURCE) == sha(HERE / 'received-package.source.json') == EXPECTED
    package = read(SOURCE)
    assert len(package['items']) == 4 and package['wholly_unconfirmed_specification_item_count'] == 24
    assert package['partially_confirmed_specification_item_count'] == 0
    assert package['fully_confirmed_specification_item_count'] == 0
    assert package['shared_master_writes_by_this_session'] is False and package['remote_mutations'] == 0
    files = {}

    def freeze(path, digest=None, size=None):
        path = Path(path).resolve()
        raw = path.read_bytes()
        actual = hashlib.sha256(raw).hexdigest()
        assert digest is None or actual == digest, str(path)
        assert size is None or len(raw) == size, str(path)
        if str(path) not in files:
            dest = (HERE / 'sources' / path.relative_to(PEERS)) if path.is_relative_to(PEERS) else (
                HERE / 'sources/external-media' / (actual + path.suffix))
            dest.parent.mkdir(parents=True, exist_ok=True)
            if dest.exists():
                assert dest.read_bytes() == raw
            else:
                dest.write_bytes(raw)
            files[str(path)] = {'source': str(path), 'snapshot': rel(dest), 'sha256': actual, 'bytes': len(raw)}
        return files[str(path)]['snapshot']

    freeze(SOURCE, EXPECTED)
    for item in package['items']:
        for artifact in item['artifacts']:
            freeze(artifact['path'], artifact['sha256'], artifact.get('bytes'))
    for artifact in package['root_artifacts']:
        freeze(artifact['path'], artifact['sha256'], artifact.get('bytes'))
    for path, digest in package['referenced_image_hashes'].items():
        freeze(path, digest)
    assert sha(Path(package['coordinator_acknowledgement'])) == package['coordinator_acknowledgement_sha256']
    assert sha(Path(package['source_snapshot_path'])) == package['source_snapshot_sha256']
    assert sha(Path(package['batch_validation_path'])) == package['batch_validation_sha256']
    normalized = []
    for item in package['items']:
        approval_path, working_path = Path(item['approval_path']), Path(item['working_entry_path'])
        assert sha(approval_path) == item['approval_sha256'] and sha(working_path) == item['working_entry_sha256']
        a, w = read(approval_path), read(working_path)
        before_path = approval_path.parent / 'component-review.before-keep.json'
        before = read(before_path)
        assert sha(before_path) == a['source_review_sha256']
        assert sha(approval_path.parent / 'review-card.txt') == a['source_card_sha256']
        assert not item['post_keep_corrections'] and not item['owner_confirmed_fields']
        assert not a['specifications_explicitly_confirmed'] and not a['fully_confirmed_specification_groups']
        assert a['name_and_visual_identity_kept'] and not a['physical_specs_verified']
        assert a['decision_id'] == item['decision_id'] and a['component_id'] == item['component_id']
        assert w['component_id'] == before['component_id'] == a['component_id']
        assert w['configuration_key'] == before['configuration_key'] == item['configuration_key']
        assert w['working_name'] == before['working_name'] == a['working_name'] == item['working_name']
        assert len(before['specification_review_items']) == len(w['specification_review_items']) == 6
        assert [x['proposal_id'] for x in before['specification_review_items']] == [x['proposal_id'] for x in w['specification_review_items']]
        evidence = a['source_user_statement']
        transcript = Path(evidence['transcript_path'])
        lines = transcript.read_text().splitlines()
        assert any(json.loads(s).get('type') == 'session_meta' and
            json.loads(s)['payload']['id'] == a['owner_session'] for s in lines[:5])

        def message(number, role, text, digest):
            obj = json.loads(lines[number - 1])
            payload = obj['payload']
            actual = '\n'.join(z.get('text', '') for z in payload.get('content', [])
                if isinstance(z, dict) and z.get('type') in ['input_text', 'output_text', 'text'])
            assert obj['type'] == 'response_item' and payload['type'] == 'message' and payload['role'] == role
            assert actual == text and hashlib.sha256(actual.encode()).hexdigest() == digest
            return {'transcript_path': str(transcript), 'line': number, 'role': role,
                'timestamp': obj['timestamp'], 'message_id': payload.get('id'),
                'text': actual, 'text_sha256': digest}

        owner = message(evidence['line'], 'user', evidence['text'], evidence['text_sha256'])
        preceding = evidence['preceding_review_card']
        card_message = message(preceding['line'], 'assistant', preceding['text'], preceding['text_sha256'])
        assert owner['timestamp'] == evidence['timestamp'] and card_message['timestamp'] == preceding['timestamp']
        assert owner['text'] == 'Keep “' + item['working_name'] + '”'
        assert preceding['line'] < evidence['line']
        intervening_final = []
        for number in range(preceding['line'] + 1, evidence['line']):
            obj = json.loads(lines[number - 1]); payload = obj.get('payload', {})
            if obj.get('type') == 'response_item' and payload.get('type') == 'message' and payload.get('role') == 'assistant' and payload.get('phase') == 'final_answer':
                intervening_final.append(number)
        assert not intervening_final
        primary, folder = before['primary_image'], before['containing_folder']
        assert primary['url'] in card_message['text'] and folder['url'] in card_message['text']
        assert item['working_name'] in card_message['text'] and a['exact_review_question'] in card_message['text']
        assert before['primary_image'] == w['primary_image'] and before['containing_folder'] == w['containing_folder']
        build = item['configuration_key'] == 'MSW-SHELLWAVE-WHITE-WATER-FEATURE'
        if build:
            assert a['identity_scope'] == 'INDIVIDUAL_UPPER_PANEL_WITHIN_WATER_FEATURE_ARRANGEMENT'
            assert a['arrangement_scope']['whole_arrangement_approved'] is False
            assert 'upper horizontal panel' in card_message['text']
        normalized.append({'component_id': item['component_id'], 'variant_id': item['configuration_key'],
            'scope_kind': 'build_variant' if build else 'size_finish_variant',
            'name': item['working_name'], 'source_decision_id': item['decision_id'],
            'source_receipt': rel(approval_path), 'receipt_snapshot': freeze(approval_path),
            'receipt_sha256': item['approval_sha256'], 'pre_answer_review': freeze(before_path),
            'pre_answer_review_sha256': sha(before_path), 'working_entry': freeze(working_path),
            'working_entry_sha256': item['working_entry_sha256'],
            'primary_expected': primary, 'folder_expected': folder,
            'review_number': w['review_number'], 'owner_session': a['owner_session'],
            'authoritative_owner_evidence': owner, 'preceding_review_card_evidence': card_message})
    now = datetime.now(timezone.utc).isoformat()
    manifest = {'schema_version': 1, 'created_utc': now, 'source_package': rel(SOURCE),
        'source_package_sha256': EXPECTED, 'scope': package['scope'], 'files': list(files.values()),
        'decisions': normalized, 'owner_user_messages_verified': 4, 'preceding_assistant_cards_verified': 4,
        'new_specification_approvals': 0, 'wholly_unconfirmed_specification_groups': 24,
        'import_constraints': package['import_constraints'], 'outstanding_followups': package['outstanding_followups'],
        'primary_images_independently_viewed': 4, 'source_full_family_census_is_peer_snapshot': True,
        'root_current_reference_check_scope': 'Four reviewed primary files and their four containing folders only',
        'remote_mutations': 0, 'shared_master_writes': False}
    write(HERE / 'source-manifest.json', manifest)
    print(json.dumps({'status': 'PASS_FROZEN_READY_FOR_IMPORT', 'source_files': len(files),
        'owner_replies_verified': 4, 'assistant_cards_verified': 4, 'finish_names': 3, 'build_names': 1,
        'specification_approvals': 0}))


if __name__ == '__main__':
    main()
