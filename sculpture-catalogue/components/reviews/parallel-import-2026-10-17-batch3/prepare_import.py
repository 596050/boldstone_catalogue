"""Freeze the bounded post-wave review queue and independently verify owner text."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PEERS = ROOT / 'components/parallel-reviews'
REVIEWS = ROOT / 'components/reviews'
TRANSCRIPTS = {
    '01a13fbf-1cbc-7511-8416-cf339051083e': Path('/Users/tprice/.codex/sessions/2026/10/15/rollout-2026-10-15T14-27-31-01a13fbf-1cbc-7511-8416-cf339051083e.jsonl'),
    '01a13fe6-495b-7253-b923-31823b4cbca8': Path('/Users/tprice/.codex/sessions/2026/10/15/rollout-2026-10-15T15-10-19-01a13fe6-495b-7253-b923-31823b4cbca8.jsonl'),
}


def read(p):
    return json.loads(p.read_text())


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def rel(p):
    return str(p.relative_to(ROOT))


def write(p, value):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def content(payload):
    return '\n'.join(x.get('text', '') for x in payload.get('content', []) if isinstance(x, dict))


def main():
    if (HERE / 'source-manifest.json').exists():
        print('ALREADY_FROZEN')
        return
    now = datetime.now(timezone.utc).isoformat()
    cp = read(REVIEWS / 'walkthrough_checkpoint.json')
    user = read(REVIEWS / 'user_classifications.json')
    assert cp['current_size_finish_variant_id'] == 'DR-WAVES-BLUE-VERDIGRIS' and cp['current_answer_recorded']
    pending = [x for x in cp['parallel_import_queue'] if not x.get('approval_imported')]
    existing = {x.get('source_decision_id') for values in user.values() if isinstance(values, list)
                for x in values if isinstance(x, dict) and x.get('source_decision_id')}
    receipts, files, skipped = {}, {}, []

    def freeze(p):
        p = p.resolve()
        assert p.is_relative_to(PEERS.resolve())
        target = HERE / 'sources' / p.relative_to(PEERS)
        if target.exists():
            assert sha(target) == sha(p), str(p)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(p.read_bytes())
        files[str(p)] = {'source': str(p), 'snapshot': rel(target), 'sha256': sha(target)}
        return rel(target)

    for entry in pending:
        p = (ROOT / entry['receipt']).resolve()
        assert sha(p) == entry['receipt_sha256'], str(p)
        d = read(p)
        if 'PACKAGE' in p.name:
            freeze(p)
            children = d.get('entries', d.get('identity_only_receipts', d.get('items', [])))
            assert children
            for child in children:
                value = next((child[k] for k in ['approval_receipt', 'approval_path', 'approval_record', 'receipt'] if child.get(k)), None)
                assert value
                p2 = Path(value)
                if not p2.is_absolute():
                    p2 = ROOT / p2
                expected = next((child[k] for k in ['approval_receipt_sha256', 'approval_sha256', 'receipt_sha256'] if child.get(k)), None)
                assert expected and sha(p2) == expected, str(p2)
                receipts[str(p2.resolve())] = p2.resolve()
        else:
            receipts[str(p)] = p
    normalized = []
    for p in receipts.values():
        d = read(p)
        if d['decision_id'] in existing:
            skipped.append({'source_receipt': rel(p), 'source_decision_id': d['decision_id'], 'reason': 'Previously imported exact decision'})
            freeze(p)
            continue
        cid = d['component_id']
        assert cid in cp['review_order']
        statement = d.get('user_statement', d.get('source_user_statement'))
        if isinstance(statement, dict):
            statement = statement['text']
        assert statement.startswith('Keep “'), str(p)
        owner = d['owner_session']
        assert owner in TRANSCRIPTS
        snapshot = next((p.parent / name for name in ['pre-identity-approval-component-review.json',
            'pre-owner-response-component-review.json', 'pre-owner-approval-component-review.json',
            'component-review.before-keep.json'] if (p.parent / name).exists()), None)
        assert snapshot
        v = read(snapshot)
        assert v['component_id'] == cid
        expected = d.get('source_review_sha256_before_answer', d.get('source_review_sha256_before_approval'))
        if expected:
            assert sha(snapshot) == expected, str(snapshot)
        name = d.get('canonical_name', d.get('working_name'))
        assert name == v.get('proposed_name', v.get('working_name'))
        reference_only = v.get('primary_image') is None
        primary = v.get('primary_image') or v.get('reference_image')
        folder = v['containing_folder']
        iid = primary.get('id', primary.get('file_id'))
        fid = folder.get('id', folder.get('file_id'))
        assert iid and fid
        if not reference_only:
            assert d.get('primary_file_id', iid) == iid
        else:
            assert d.get('reference_file_id', iid) == iid and d.get('primary_file_id') is None
        variant = d.get('variant_id', v.get('variant_id'))
        configuration = d.get('configuration_key', v.get('configuration_key'))
        if p.name == 'owner-face-dimensions.json':
            kind = 'variant_face_dimensions'
            assert cid == 'BC-FP-LEFT' and d['dimensions_cm'] == {'height': 40, 'width': 40, 'depth': None}
        else:
            assert not d.get('specifications_explicitly_confirmed', False)
            assert not d.get('specifications_approved', False) and not d.get('proposals_approved', False)
            assert not d.get('approved_proposal_ids', [])
            assert len(v['specification_review_items']) == 6
            if cid == 'BC-SPICE':
                kind, variant = 'component_layout_identity', configuration
            elif cid in ['BC-SF-1', 'BC-SF-2']:
                kind, variant = 'size_finish_variant_identity', configuration
            elif reference_only:
                kind = 'depicted_design_finish_identity'
            elif configuration:
                kind = 'build_configuration_identity'
            else:
                kind = 'size_finish_variant_identity' if variant else 'component_identity'
        for filename in ['component-review.json', 'Approval_Presentation.md', 'working-entry.json',
                         'Current_Metadata.json', 'download-receipts.json', 'download-receipt.json']:
            f = p.parent / filename
            if f.exists():
                if filename == 'Approval_Presentation.md' and d.get('approval_presentation_sha256'):
                    assert sha(f) == d['approval_presentation_sha256']
                freeze(f)
        normalized.append({'kind': kind, 'component_id': cid, 'variant_id': variant,
            'build_variant_id': configuration if kind == 'build_configuration_identity' else None,
            'component_layout_id': configuration if kind == 'component_layout_identity' else None,
            'name': name, 'statement': statement, 'owner_session': owner,
            'receipt': freeze(p), 'source_receipt': rel(p), 'source_receipt_sha256': sha(p),
            'source_decision_id': d['decision_id'], 'recorded_utc': d['recorded_utc'],
            'review_number': cp['review_order'].index(cid) + 1,
            'review_snapshot': freeze(snapshot), 'pre_answer_review_sha256': sha(snapshot),
            'pre_answer_hash_in_receipt': bool(expected), 'evidence_file_id': iid, 'folder_id': fid,
            'primary_expected': primary, 'folder_expected': folder, 'reference_only': reference_only,
            'image_url': v.get('image_url', primary.get('url')), 'folder_url': v.get('folder_url', folder.get('url')),
            'dimensions_cm': d.get('dimensions_cm') if kind == 'variant_face_dimensions' else None,
            'unit_interpretation': d.get('unit_interpretation')})
    assert len({x['source_decision_id'] for x in normalized}) == len(normalized)
    evidence = {}
    for owner, transcript in TRANSCRIPTS.items():
        wanted = {d['statement'] for d in normalized if d['owner_session'] == owner}
        found, previous, session = {}, None, None
        for number, line in enumerate(transcript.open(), 1):
            obj = json.loads(line)
            if obj.get('type') == 'session_meta':
                session = obj['payload']['id']
            payload = obj.get('payload', {})
            if obj.get('type') != 'response_item' or payload.get('type') != 'message':
                continue
            text = content(payload)
            if payload.get('role') == 'assistant' and payload.get('phase') == 'final_answer' and 'dropbox.com' in text:
                previous = {'line': number, 'timestamp': obj.get('timestamp'), 'text': text,
                            'sha256': hashlib.sha256(text.encode()).hexdigest()}
            if payload.get('role') == 'user' and text in wanted:
                assert text not in found and previous is not None
                found[text] = {'transcript_path': str(transcript), 'session_id': owner, 'line': number,
                    'timestamp': obj.get('timestamp'), 'user_statement': text,
                    'text_sha256': hashlib.sha256(text.encode()).hexdigest(), 'preceding_assistant_card': previous}
        assert session == owner and set(found) == wanted
        evidence[owner] = found
    for d in normalized:
        e = evidence[d['owner_session']][d['statement']]
        text = e['preceding_assistant_card']['text']
        assert d['name'] in text and d['image_url'] in text
        if d['reference_only']:
            assert 'Pair reference' in text and 'design' in text
        d['authoritative_user_evidence'] = e
    manifest = {'schema_version': 1, 'cutoff_utc': now,
        'scope': 'Fixed pending queue after Blue Verdigris and Bronze Keep. Later FP white/weight/right answers remain outside this bounded batch.',
        'decisions': normalized, 'previously_imported_decisions_skipped': skipped,
        'queue_entries': pending, 'files': list(files.values()), 'approval_inferred': False, 'remote_files_changed': False}
    write(HERE / 'source-manifest.json', manifest)
    requests = sorted({d[k] for d in normalized for k in ['evidence_file_id', 'folder_id']})
    write(HERE / 'metadata-requests.json', requests)
    write(HERE / 'authoritative-owner-cards.json', [{'kind': d['kind'], 'name': d['name'],
        'statement': d['statement'], 'evidence': d['authoritative_user_evidence']} for d in normalized])
    print(json.dumps({'status': 'FROZEN_PENDING_CURRENT_REFERENCE_CHECK', 'decisions': len(normalized),
        'previously_imported_skipped': len(skipped), 'metadata_requests': len(requests), 'files': len(files)}))
    for d in normalized:
        print(d['kind'], d['name'], 'owner_line', d['authoritative_user_evidence']['line'])


if __name__ == '__main__':
    main()
