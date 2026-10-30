"""Freeze a bounded receipt batch and independently recover owner reply context."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
REVIEWS = ROOT / 'components/reviews'
PEERS = ROOT / 'components/parallel-reviews'
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


def write(p, d):
    p.parent.mkdir(parents=True, exist_ok=True)
    t = p.with_name(p.name + '.tmp')
    t.write_text(json.dumps(d, ensure_ascii=False, indent=2) + '\n')
    t.replace(p)


def text_content(payload):
    return '\n'.join(c.get('text', '') for c in payload.get('content', []) if isinstance(c, dict))


def main():
    if (HERE / 'source-manifest.json').exists():
        m = read(HERE / 'source-manifest.json')
        print(json.dumps({'status': 'FROZEN_BATCH_ALREADY_PREPARED', 'decisions': len(m['decisions'])}))
        return
    now = datetime.now(timezone.utc).isoformat()
    cp = read(REVIEWS / 'walkthrough_checkpoint.json')
    assert cp['current_component_id'] == 'BC-FDW-2' and cp['current_answer_recorded']
    pending = [x for x in cp['parallel_import_queue'] if not x.get('approval_imported')]
    additional = [
        'components/parallel-reviews/egyptian-2026-10-17/palm-three-white/identity-approval.json',
        'components/parallel-reviews/shellmoon-2026-10-17/islington-white/review-approval.json',
    ]
    for f in additional:
        p = ROOT / f
        if p.exists() and not any(x['receipt'] == f for x in pending):
            d = read(p)
            pending.append({'component_id': d['component_id'], 'receipt': f, 'receipt_sha256': sha(p), 'approval_imported': False, 'recorded_utc': now, 'status': 'RECEIVED; BOUNDED BATCH2 VERIFICATION PENDING'})
    receipts, packages = {}, []
    for entry in pending:
        p = (ROOT / entry['receipt']).resolve()
        assert p.is_relative_to(PEERS.resolve())
        if entry.get('receipt_sha256'):
            assert sha(p) == entry['receipt_sha256'], str(p)
        d = read(p)
        if p.name != 'IMPORT_PACKAGE.json':
            receipts[str(p)] = p
            continue
        packages.append({'queue_entry': entry, 'source': str(p), 'sha256': sha(p), 'package': d})
        for child in d.get('entries', d.get('identity_only_receipts', [])):
            p2 = Path(child.get('approval_receipt', child.get('approval_record', child.get('receipt', ''))))
            assert p2.is_absolute() and p2.resolve().is_relative_to(PEERS.resolve())
            expected = child.get('approval_receipt_sha256', child.get('approval_sha256', child.get('receipt_sha256')))
            if expected:
                assert sha(p2) == expected, str(p2)
            receipts[str(p2)] = p2
    normalized, files = [], []

    def freeze(p):
        target = HERE / 'sources' / p.relative_to(PEERS)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            assert sha(p) == sha(target)
        else:
            target.write_bytes(p.read_bytes())
        digest = sha(target)
        assert sha(p) == digest
        files.append({'source': str(p), 'snapshot': rel(target), 'sha256': digest})
        return rel(target)

    for p in receipts.values():
        d = read(p)
        cid = d['component_id']
        assert cid in cp['review_order']
        statement = d.get('user_statement', d.get('source_user_statement'))
        if isinstance(statement, dict):
            statement = statement['text']
        assert isinstance(statement, str) and statement
        owner = d['owner_session']
        assert owner in TRANSCRIPTS
        if p.name == 'dimension-approval.json':
            for key in ['reference_review_file', 'source_review_file']:
                source = Path(d[key])
                digest_key = key.replace('_file', '_sha256')
                assert sha(source) == d[digest_key]
                freeze(source)
            normalized.append({'kind': 'variant_dimensions', 'component_id': cid, 'variant_id': d['corrected_variant_id'], 'name': d['proposed_name'], 'statement': statement, 'owner_session': owner, 'receipt': freeze(p), 'source_receipt': rel(p), 'source_receipt_sha256': sha(p), 'source_decision_id': d['decision_id'], 'primary_file_id': d['primary_file_id'], 'primary_folder_id': d['primary_folder_id'], 'dimensions_cm': d['confirmed_dimensions_cm'], 'recorded_utc': d['recorded_utc']})
            continue
        if (p.parent / 'pre-identity-approval-component-review.json').exists():
            before = p.parent / 'pre-identity-approval-component-review.json'
        elif (p.parent / 'pre-owner-approval-component-review.json').exists():
            before = p.parent / 'pre-owner-approval-component-review.json'
        else:
            before = p.parent / 'component-review.before-keep.json'
        v = read(before)
        assert v['component_id'] == cid
        expected = d.get('source_review_sha256_before_answer', d.get('source_review_sha256_before_approval'))
        if expected:
            assert sha(before) == expected, str(before)
        primary, folder = v['primary_image'], v['containing_folder']
        iid = primary.get('id', primary.get('file_id'))
        fid = folder.get('id', folder.get('file_id'))
        assert iid and fid
        assert d.get('primary_file_id', iid) == iid and d.get('primary_folder_id', fid) == fid
        name = d.get('canonical_name', d.get('working_name'))
        assert name == v.get('proposed_name', v.get('working_name'))
        items = v['specification_review_items']
        assert len(items) == 6 and len({i['proposal_id'] for i in items}) == 6
        full = p.name == 'owner-approval.json'
        if full:
            assert cid == 'BC-DP-SPIRAL' and d['variant_id'] == 'DP-SPIRAL-GOLD-45x40'
            assert 'and the remaining working details' in statement
            assert d['proposals_approved'] and len(d['approved_proposal_ids']) == 6
        else:
            assert statement.startswith('Keep “') and 'working details' not in statement
            assert not d.get('specifications_explicitly_confirmed', False)
            assert not d.get('proposals_approved', False)
        configuration = d.get('configuration_key', v.get('configuration_key'))
        variant = d.get('variant_id', v.get('variant_id'))
        kind = 'build_configuration_identity' if configuration else ('size_finish_variant_identity' if variant else 'component_identity')
        freeze(p.parent / 'component-review.json')
        for name2 in ['Approval_Presentation.md', 'working-entry.json', 'Current_Metadata.json', 'live-reference-check.json', 'download-receipts.json', 'download-receipt.json']:
            source = p.parent / name2
            if source.exists():
                if name2 == 'Approval_Presentation.md' and d.get('approval_presentation_sha256'):
                    assert sha(source) == d['approval_presentation_sha256']
                freeze(source)
        normalized.append({'kind': kind, 'component_id': cid, 'variant_id': variant, 'build_variant_id': configuration, 'review_number': cp['review_order'].index(cid) + 1, 'name': name, 'statement': statement, 'owner_session': owner, 'receipt': freeze(p), 'source_receipt': rel(p), 'source_receipt_sha256': sha(p), 'source_decision_id': d['decision_id'], 'review_snapshot': freeze(before), 'pre_answer_review_sha256': sha(before), 'pre_answer_hash_in_receipt': bool(expected), 'primary_file_id': iid, 'primary_folder_id': fid, 'primary_expected': primary, 'folder_expected': folder, 'image_url': v.get('image_url', primary.get('url')), 'folder_url': v.get('folder_url', folder.get('url')), 'specifications_approved': full, 'approved_proposal_ids': d.get('approved_proposal_ids', []) if full else [], 'recorded_utc': d['recorded_utc']})
    for package in packages:
        freeze(Path(package['source']))
    # Authoritative roles, not quoted strings in tool or agent messages.
    by_owner = {}
    for owner, path in TRANSCRIPTS.items():
        wanted = {d['statement'] for d in normalized if d['owner_session'] == owner}
        found, prior_assistant = {}, None
        session_id = None
        for n, line in enumerate(path.open(), 1):
            obj = json.loads(line)
            if obj.get('type') == 'session_meta':
                session_id = obj['payload']['id']
            payload = obj.get('payload', {})
            if obj.get('type') != 'response_item' or payload.get('type') != 'message':
                continue
            text = text_content(payload)
            if payload.get('role') == 'assistant' and payload.get('phase') == 'final_answer' and 'dropbox.com' in text:
                prior_assistant = {'line': n, 'timestamp': obj.get('timestamp'), 'text': text, 'sha256': hashlib.sha256(text.encode()).hexdigest()}
            if payload.get('role') == 'user' and text in wanted:
                assert text not in found, 'Ambiguous duplicate owner reply: ' + text
                assert prior_assistant is not None
                found[text] = {'transcript_path': str(path), 'session_id': owner, 'line': n, 'timestamp': obj.get('timestamp'), 'user_statement': text, 'text_sha256': hashlib.sha256(text.encode()).hexdigest(), 'preceding_assistant_card': prior_assistant}
        assert session_id == owner
        assert set(found) == wanted, 'Missing exact authoritative statements: ' + repr(wanted - set(found))
        by_owner[owner] = found
    for d in normalized:
        e = by_owner[d['owner_session']][d['statement']]
        card = e['preceding_assistant_card']['text']
        assert 'dropbox.com' in card, d['name']
        assert d['name'] in card, d['name']
        if d['kind'] != 'variant_dimensions':
            assert d['image_url'] in card, 'Displayed primary link mismatch: ' + d['name']
        d['authoritative_user_evidence'] = e
    unique = {(d['kind'], d['component_id'], d.get('variant_id'), d.get('build_variant_id')) for d in normalized}
    assert len(unique) == len(normalized)
    manifest = {'schema_version': 1, 'cutoff_utc': now, 'scope': 'Bounded queue snapshot after FDW2 identity Keep; later owner receipts wait for another batch. Package overlaps deduplicated by actual receipt.', 'decisions': normalized, 'queue_entries': pending, 'files': files, 'approval_inferred': False, 'remote_files_changed': False}
    write(HERE / 'source-manifest.json', manifest)
    primary_requests = sorted({d[k] for d in normalized for k in ['primary_file_id', 'primary_folder_id']})
    write(HERE / 'metadata-requests.json', primary_requests)
    write(HERE / 'authoritative-owner-cards.json', [{'kind':d['kind'],'component_id':d['component_id'],'name':d['name'],'statement':d['statement'],'evidence':d['authoritative_user_evidence']} for d in normalized])
    print(json.dumps({'status':'FROZEN_PENDING_LIVE_REFERENCE_CHECK', 'decisions':len(normalized), 'identity_receipts':sum(d['kind']!='variant_dimensions' for d in normalized),'metadata_requests':len(primary_requests),'source_files':len(files)},ensure_ascii=False))
    for d in normalized:
        print(d['kind'], d['name'], 'owner_line', d['authoritative_user_evidence']['line'])


if __name__ == '__main__':
    main()
