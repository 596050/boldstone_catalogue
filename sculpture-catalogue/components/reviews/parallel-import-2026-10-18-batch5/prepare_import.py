"""Freeze the completed Gleneagles package and two already-received Knightsbridge answers."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PEERS = ROOT / 'components/parallel-reviews'
REVIEWS = ROOT / 'components/reviews'
OWNER = '01a13fbf-1cbc-7511-8416-cf339051083e'
TRANSCRIPT = Path('/Users/tprice/.codex/sessions/2026/10/15/rollout-2026-10-15T14-27-31-01a13fbf-1cbc-7511-8416-cf339051083e.jsonl')
read = lambda p: json.loads(p.read_text())
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
rel = lambda p: str(p.relative_to(ROOT))


def write(p, value):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def main():
    assert not (HERE / 'source-manifest.json').exists(), 'Already frozen'
    cp = read(REVIEWS / 'walkthrough_checkpoint.json')
    assert cp['current_component_id'] == 'BC-FACET-MOUND' and cp['current_answer_recorded']
    assert cp['next_review_after_keep']['component_id'] == 'BC-FOUNTAIN-EG'
    package_path = PEERS / 'gleneagles-2026-10-18/IMPORT_PACKAGE.json'
    assert sha(package_path) == 'ae6140635c46ea63f2b8e1daab7efa53eaa71a44df5912193f70f1e425440100'
    package = read(package_path)
    files, artifacts, receipt_paths = {}, {}, {}

    def freeze(p):
        p = p.resolve()
        assert p.is_relative_to(PEERS)
        target = HERE / 'sources' / p.relative_to(PEERS)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            assert sha(target) == sha(p)
        else:
            target.write_bytes(p.read_bytes())
        files[str(p)] = {'source': str(p), 'snapshot': rel(target), 'sha256': sha(target)}
        return rel(target)

    freeze(package_path)
    for entry in package['entries']:
        p = Path(entry['identity_receipt'])
        assert sha(p) == entry['identity_receipt_sha256']
        receipt_paths[str(p)] = p
        for key, digest in [('review_file', 'review_sha256'), ('presentation', 'presentation_sha256')]:
            assert sha(Path(entry[key])) == entry[digest]
            freeze(Path(entry[key]))
        for f in entry.get('evidence_files', []):
            p = Path(f['path'])
            assert sha(p) == f['sha256']
            artifacts[str(p)] = f
            if p.suffix.lower() in ['.json', '.md', '.txt']:
                freeze(p)
    for field in package['field_receipts']:
        p = Path(field['path'])
        assert sha(p) == field['sha256']
        receipt_paths[str(p)] = p
    pending_queue = [x for x in cp['parallel_import_queue'] if not x.get('approval_imported')]
    for entry in pending_queue:
        p = ROOT / entry['receipt']
        assert sha(p) == entry['receipt_sha256']
        if p != package_path:
            receipt_paths[str(p)] = p
    assert len(receipt_paths) == 8
    previous, image_card, users, session = None, None, [], None
    for number, line in enumerate(TRANSCRIPT.open(), 1):
        obj = json.loads(line)
        payload = obj.get('payload', {})
        if obj.get('type') == 'session_meta':
            session = payload['id']
        if obj.get('type') != 'response_item' or payload.get('type') != 'message':
            continue
        text = '\n'.join(x.get('text', '') for x in payload.get('content', []) if isinstance(x, dict))
        if payload.get('role') == 'assistant' and payload.get('phase') == 'final_answer' and text:
            previous = {'line': number, 'timestamp': obj.get('timestamp'), 'text': text, 'sha256': hashlib.sha256(text.encode()).hexdigest()}
            if 'dropbox.com' in text:
                image_card = previous
        elif payload.get('role') == 'user':
            users.append({'transcript_path': str(TRANSCRIPT), 'session_id': OWNER, 'line': number, 'timestamp': obj.get('timestamp'),
                'user_statement': text, 'text_sha256': hashlib.sha256(text.encode()).hexdigest(),
                'preceding_assistant_card': previous, 'preceding_component_image_card': image_card})
    assert session == OWNER
    normalized = []
    for path in receipt_paths.values():
        d = read(path)
        assert d['owner_session'] == OWNER
        expected = d.get('source_review_sha256_before_answer', d.get('source_review_sha256_before_instruction'))
        search_root = PEERS / 'gleneagles-2026-10-18' if 'gleneagles-2026-10-18' in path.parts else path.parent
        candidates = [p for p in search_root.rglob('*.json') if ('pre-' in p.name or 'before-' in p.name) and sha(p) == expected]
        assert len(candidates) == 1, (str(path), expected)
        snapshot = candidates[0]
        v = read(snapshot)
        primary = v.get('primary_image') or v.get('reference_image')
        folder = v['containing_folder']
        iid, fid = primary.get('id', primary.get('file_id')), folder.get('id', folder.get('file_id'))
        image_url, folder_url = v.get('image_url', primary.get('url')), v.get('folder_url', folder.get('url'))
        found = [x for x in users if x['user_statement'] == d['user_statement']]
        assert len(found) == 1 and found[0]['preceding_assistant_card']
        evidence = found[0]
        context = evidence['preceding_assistant_card']['text']
        image_context = evidence['preceding_component_image_card']['text']
        assert image_url in context or image_url in image_context, (str(path), evidence['line'])
        if path.name == 'identity-approval.json':
            kind = 'depicted_position_identity'
            name = d['canonical_name']
            assert d['user_statement'].startswith('Keep “') and name in context
            assert not d.get('specifications_approved') and not d.get('approved_proposal_ids')
        elif path.name == 'owner-face-dimensions.json':
            kind, name = 'gleneagles_four_face_and_overall_dimensions', 'Gleneagles four white panels'
            assert 'four individual panels 35 x 35' in d['user_statement'] and len(d['components']) == 4
        elif path.name == 'owner-keyhole-fixings.json':
            kind, name = 'gleneagles_four_fixing_types', 'Gleneagles four white panels'
            assert d['fixing_type'] == 'keyhole' and 'Gleneagles' in context
        else:
            assert path.name == 'owner-dimensions.json' and d['component_id'] == 'BC-KNIGHT'
            kind, name = 'knightsbridge_complete_dimension_instruction', 'Knightsbridge Fountain — White'
            assert d['user_statement'] == '1metre squared by 50cm deep' and 'fountain block' in context
            assert d['dimensions_cm'] == [100, 100, 50]
        for filename in ['Current_Metadata.json', 'Approval_Presentation.md', 'download-receipts.json', 'download-receipt.json']:
            p = path.parent / filename
            if p.exists():
                freeze(p)
        normalized.append({'kind': kind, 'component_id': d.get('component_id'), 'variant_id': d.get('variant_id'),
            'name': name, 'statement': d['user_statement'], 'owner_session': OWNER, 'source_decision_id': d['decision_id'],
            'receipt': freeze(path), 'source_receipt': rel(path), 'source_receipt_sha256': sha(path), 'recorded_utc': d['recorded_utc'],
            'review_snapshot': freeze(snapshot), 'pre_answer_review_sha256': sha(snapshot), 'evidence_file_id': iid,
            'folder_id': fid, 'primary_expected': primary, 'folder_expected': folder, 'reference_only': v.get('primary_image') is None,
            'image_url': image_url, 'folder_url': folder_url, 'authoritative_user_evidence': evidence})
    assert len({x['source_decision_id'] for x in normalized}) == 8
    assert sum(x['kind'] == 'depicted_position_identity' for x in normalized) == 5
    manifest = {'schema_version': 1, 'cutoff_utc': datetime.now(timezone.utc).isoformat(),
        'scope': 'One sealed Gleneagles package plus two already-queued Knightsbridge answers. Ongoing Lava and Panel/Plant/Raked packages excluded; their evidence flag remains separate.',
        'packages': [{'source': rel(package_path), 'snapshot': freeze(package_path), 'sha256': sha(package_path)}],
        'decisions': normalized, 'files': list(files.values()), 'evidence_artifact_sha256': list(artifacts.values()),
        'queue_entries': pending_queue, 'approval_inferred': False, 'remote_files_changed': False}
    write(HERE / 'source-manifest.json', manifest)
    write(HERE / 'metadata-requests.json', sorted({d[k] for d in normalized for k in ['evidence_file_id', 'folder_id']}))
    print(json.dumps({'status': 'FROZEN_PENDING_CURRENT_REFERENCE_CHECK', 'source_receipts': 8, 'name_only': 5,
        'all_four_partial_face_and_fixing_instructions': 2, 'complete_Knight_dimension_instruction': 1, 'snapshots': len(files)}))
    for d in normalized:
        print(d['kind'], d['name'], 'owner_line', d['authoritative_user_evidence']['line'])


if __name__ == '__main__':
    main()
