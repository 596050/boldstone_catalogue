"""Freeze Knight/Lava evidence and verify exact owner turns before scoped import."""
import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
REVIEWS = ROOT / 'components/reviews'
PEER = ROOT / 'components/parallel-reviews/knight-lava-2026-10-18'
EXPECTED = '6590c3d61f843632f7b740df129c70bc587e76c0e20dbb1e359f104237fa73e2'
read = lambda p: json.loads(p.read_text())
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
rel = lambda p: str(p.relative_to(ROOT))


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    temp.replace(path)


def main():
    manifest_path = HERE / 'source-manifest.json'
    assert not manifest_path.exists()
    package_path = PEER / 'IMPORT_PACKAGE.json'
    assert sha(package_path) == sha(HERE / 'received-package.source.json') == EXPECTED
    package = read(package_path)
    index_path = Path(package['file_manifest']); index = read(index_path)
    assert sha(index_path) == package['file_manifest_sha256']
    assert index['member_count'] == len(index['members']) == package['sealed_file_member_count'] == 230
    frozen = {}

    def freeze(path, digest=None, size=None):
        path = Path(path).resolve(); assert path.is_relative_to(PEER)
        raw = path.read_bytes(); actual = hashlib.sha256(raw).hexdigest()
        assert digest is None or actual == digest, str(path)
        assert size is None or len(raw) == size, str(path)
        if str(path) not in frozen:
            target = HERE / 'sources/knight-lava-2026-10-18' / path.relative_to(PEER)
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                assert target.read_bytes() == raw
            else:
                target.write_bytes(raw)
            frozen[str(path)] = {'source': str(path), 'snapshot': rel(target), 'sha256': actual, 'bytes': len(raw)}
        return frozen[str(path)]['snapshot']

    for member in index['members']:
        freeze(PEER / member['relative_path'], member['sha256'], member['bytes'])
    freeze(package_path, EXPECTED); freeze(index_path, package['file_manifest_sha256'])
    evidence_path = Path(package['owner_transcript_evidence'])
    assert sha(evidence_path) == package['owner_transcript_evidence_sha256']
    evidence = read(evidence_path); freeze(evidence_path)
    assert evidence['matched_distinct_user_statements'] == 13 and evidence['missing_distinct_user_statements'] == 0
    transcript = Path(evidence['source_transcript']); lines = transcript.read_bytes().splitlines(keepends=True)
    assert any(json.loads(s).get('type') == 'session_meta' and
        json.loads(s)['payload']['id'] == package['owner_session'] for s in lines[:5])
    previous = None; image_card = None; owner_turns = {}
    for number, raw in enumerate(lines, 1):
        obj = json.loads(raw); payload = obj.get('payload', {})
        if obj.get('type') != 'response_item' or payload.get('type') != 'message':
            continue
        text = '\n'.join(x.get('text', '') for x in payload.get('content', [])
            if isinstance(x, dict) and x.get('type') in ['input_text', 'output_text', 'text'])
        if payload.get('role') == 'assistant' and payload.get('phase') == 'final_answer' and text:
            previous = {'line': number, 'timestamp': obj['timestamp'], 'message_id': payload.get('id'),
                'text': text, 'text_sha256': hashlib.sha256(text.encode()).hexdigest()}
            if 'dropbox.com' in text:
                image_card = previous
        elif payload.get('role') == 'user':
            owner_turns[number] = {'transcript': str(transcript), 'session_id': package['owner_session'],
                'line': number, 'timestamp': obj['timestamp'], 'message_id': payload.get('id'),
                'role': 'user', 'text': text, 'text_sha256': hashlib.sha256(text.encode()).hexdigest(),
                'raw_line_sha256': hashlib.sha256(raw).hexdigest(),
                'preceding_assistant_card': previous, 'preceding_component_image_card': image_card}
    verified = []
    for item in evidence['entries']:
        assert item['verified'] and len(item['exact_user_message_matches']) == 1
        expected = item['exact_user_message_matches'][0]; actual = owner_turns[expected['line']]
        assert actual['text'] == item['user_statement']
        assert actual['timestamp'] == expected['timestamp']
        assert actual['raw_line_sha256'] == expected['raw_line_sha256']
        assert actual['text_sha256'] == expected['user_text_sha256']
        assert actual['preceding_assistant_card'] and actual['preceding_component_image_card']
        verified.append(actual | {'source_receipt_snapshots': [freeze(p) for p in item['receipt_paths']]})
    assert len(verified) == 13 and len({x['line'] for x in verified}) == 13
    by_text = {x['text']: x for x in verified}
    by_hash = {}
    for item in frozen.values():
        by_hash.setdefault(item['sha256'], []).append(item['snapshot'])
    names = []
    refs = {x['request_id']: x for x in read(HERE / 'current-reference-check.json')['metadata']}
    for entry in package['entries']:
        approval_path = Path(entry['identity_receipt']); approval = read(approval_path)
        assert sha(approval_path) == entry['identity_receipt_sha256']
        assert approval['canonical_name'] == entry['canonical_name'] and approval['component_id'] == entry['component_id']
        assert approval['user_statement'] == entry['user_statement'] and approval['user_statement'] in by_text
        context = by_text[approval['user_statement']]['preceding_component_image_card']['text']
        assert entry['canonical_name'] in context and 'dropbox.com' in context
        pre_hash = approval['source_review_sha256_before_answer']
        assert pre_hash in by_hash, (entry['canonical_name'], pre_hash)
        file, folder = refs[entry['reference_file_id']]['file'], refs[entry['reference_folder_id']]['folder']
        assert file['path_display'].rsplit('/', 1)[0] == folder['path_display']
        names.append({'component_id': entry['component_id'], 'variant_id': entry['variant_id'],
            'name': entry['canonical_name'], 'source_decision_id': approval['decision_id'],
            'identity_receipt_snapshot': freeze(approval_path), 'identity_receipt_sha256': entry['identity_receipt_sha256'],
            'pre_answer_review_sha256': pre_hash, 'matching_pre_answer_snapshots': by_hash[pre_hash],
            'latest_review_snapshot': freeze(entry['review_file'], entry['review_sha256']),
            'owner_evidence_line': by_text[approval['user_statement']]['line'],
            'current_file_id': file['id'], 'current_folder_id': folder['id'],
            'source_vs_current_rev_and_content_binding': 'PENDING_NORMALIZATION_OF_SOURCE_METADATA_AND_IMAGE_RECEIPTS'})
    paths = {'walkthrough': REVIEWS / 'walkthrough_checkpoint.json', 'component': ROOT / 'components/checkpoint.json',
        'root': ROOT / 'checkpoint.json'}
    docs = {k: read(p) for k, p in paths.items()}; before = copy.deepcopy(docs)
    hashes = {k: sha(p) for k, p in paths.items()}
    cp, c = docs['walkthrough'], docs['component']
    assert cp['current_component_id'] == 'BC-MCP-2' and cp['current_size_finish_variant_id'] == 'MCP2-BLUE-SPLASHES'
    assert not cp['current_answer_recorded'] and docs['root']['current_component_review'] == c
    protected_paths = [REVIEWS / 'user_classifications.json', REVIEWS / 'specification_review_progress.json',
        ROOT / 'components/evidence/component_register.json', ROOT / cp['register_workbook'],
        ROOT / cp['current_review_record'], ROOT / cp['last_identity_approval']]
    protected = {str(p): sha(p) for p in protected_paths}
    now = datetime.now(timezone.utc).isoformat()
    write(HERE / 'before-source-verification-queue-update.json', {'recorded_utc': now,
        'files': {rel(paths[k]): v for k, v in before.items()}, 'protected_sha256': protected})
    user = read(REVIEWS / 'user_classifications.json')
    existing = {x.get('source_decision_id') for values in user.values() if isinstance(values, list)
        for x in values if isinstance(x, dict)}
    for item in names:
        item['source_decision_already_in_shared_ledger'] = item['source_decision_id'] in existing
    manifest = {'schema_version': 1, 'prepared_utc': now, 'status': 'FROZEN_OWNER_TURNS_VERIFIED_NOT_IMPORTED',
        'source_package': rel(package_path), 'source_package_sha256': EXPECTED, 'files': list(frozen.values()),
        'sealed_member_hashes_verified': 230, 'owner_turns': verified, 'exact_owner_user_messages_verified': 13,
        'preceding_assistant_and_last_image_cards_extracted': 13, 'named_entries': names,
        'current_metadata': rel(HERE / 'current-reference-check.json'), 'current_metadata_ids': 6,
        'approval_imported': False, 'new_owner_fact_or_specification_approval_inferred': False,
        'remaining_work': ['Verify current rev/byte/hash bindings against frozen source image receipts',
            'Normalize exact name versus owner face-size, French-cleat TYPE and conditional105kg scopes',
            'Deduplicate Knight name/dimensions already imported',
            'Apply six Lava variant identities and only their explicitly confirmed/accepted fields',
            'Independent shared-master readback'], 'physical_specs_verified': False}
    write(manifest_path, manifest)
    queue = next(x for x in cp['parallel_import_queue'] if x['receipt'] == rel(package_path))
    assert not queue['approval_imported']
    queue.update({'status': '230SOURCE_MEMBERS_FROZEN;13EXACT_OWNER_TURNS_VERIFIED;6CURRENT_IDS_FETCHED;SCOPED_IMPORT_PENDING',
        'source_manifest': rel(manifest_path), 'source_manifest_sha256': sha(manifest_path),
        'owner_user_messages_verified': 13, 'source_verification_utc': now})
    cp['next_serialized_parallel_import'].update({'status': 'FROZEN_OWNER_TURNS_VERIFIED_PENDING_SCOPED_IMPORT',
        'source_manifest': rel(manifest_path), 'source_verification_utc': now})
    cp['updated_utc'] = now
    c.update({'parallel_import_queue': copy.deepcopy(cp['parallel_import_queue']), 'updated_utc': now})
    docs['root']['current_component_review'] = copy.deepcopy(c); docs['root']['updated_utc'] = now
    assert all(cp[k] == value for k, value in before['walkthrough'].items()
        if k.startswith('current_') or k in ['proposed_name', 'question_scope', 'next_review_after_keep', 'pending_specification_reviews'])
    assert all(sha(path) == hashes[k] for k, path in paths.items())
    assert all(sha(Path(path)) == digest for path, digest in protected.items())
    for key, path in paths.items():
        write(path, docs[key]); assert read(path) == docs[key]
    result = {'status': 'PASS_SOURCE_VERIFICATION_ONLY_NOT_IMPORTED', 'frozen_files': len(frozen),
        'sealed_members_verified': 230, 'exact_owner_turns_verified': 13, 'named_entries': len(names),
        'already_imported_source_decisions': sum(x['source_decision_already_in_shared_ledger'] for x in names),
        'current_metadata_ids_fetched': 6, 'current_Blue_question_and_ledger_preserved': True,
        'new_specification_approvals': 0, 'root_component_checkpoint_match': read(paths['root'])['current_component_review'] == read(paths['component'])}
    write(HERE / 'source-verification-readback.json', result)
    event = {'event_id': 'parallel-import:batch8:source-verification:2026-10-19',
        'event': 'SEALED_SOURCE_FROZEN_AND_OWNER_TURNS_VERIFIED_NOT_IMPORTED', 'recorded_utc': now,
        'source_manifest': rel(manifest_path), 'approval_imported': False, 'current_MCP2_Blue_question_preserved': True}
    for path in [REVIEWS / 'identity_review_journal.jsonl', ROOT / 'review_journal.jsonl']:
        with path.open('a') as f:
            f.write(json.dumps(event, ensure_ascii=False) + '\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
