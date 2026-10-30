"""Freeze five completed packages and verify owner turns against session transcripts."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PEERS = ROOT / 'components/parallel-reviews'
REVIEWS = ROOT / 'components/reviews'
PACKAGES = {
    'fp-panels-2026-10-17': '10988ca03fb9329d4d2ba98f1c1307783c41fe0915c1c51ff36a33123dcc5487',
    'spiralmoon-2026-10-17': '37766f259f1e083dd9478400938732c9d6d67aa0287ab5fa474af64fbc29cc75',
    'frozenfish-2026-10-18': '476ebce9cbe497db90ba4bf273dca8b3b1e4e7d8709a480ecbd0de07c1e5d6a1',
    'strata-textures-2026-10-18': '815be04df630c12278e1e823b7d553483886794ceae15bfe8e0d90a0e8770493',
    'azure-wave-moonshadow-2026-10-18': '8af8dcfe68857cf175212d8b244456ee9695066f1b06b0e3f1de5c3a774de981',
}
TRANSCRIPTS = {
    '01a13fbf-1cbc-7511-8416-cf339051083e': Path('/Users/tprice/.codex/sessions/2026/10/15/rollout-2026-10-15T14-27-31-01a13fbf-1cbc-7511-8416-cf339051083e.jsonl'),
    '01a13fe6-495b-7253-b923-31823b4cbca8': Path('/Users/tprice/.codex/sessions/2026/10/15/rollout-2026-10-15T15-10-19-01a13fe6-495b-7253-b923-31823b4cbca8.jsonl'),
}
read = lambda p: json.loads(p.read_text())
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
rel = lambda p: str(p.relative_to(ROOT))


def write(p, v):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(v, ensure_ascii=False, indent=2) + '\n')


def main():
    assert not (HERE / 'source-manifest.json').exists(), 'Already frozen'
    cp = read(REVIEWS / 'walkthrough_checkpoint.json')
    user = read(REVIEWS / 'user_classifications.json')
    assert cp['current_component_id'] == 'BC-DR-WAVE3' and cp['current_answer_recorded'] and cp['family_first_pass_complete']
    existing = {x.get('source_decision_id') for values in user.values() if isinstance(values, list) for x in values if isinstance(x, dict)}
    files, artifacts, receipts, packages, skipped = {}, {}, {}, [], []
    now = datetime.now(timezone.utc).isoformat()

    def freeze(p):
        p = p.resolve()
        assert p.is_relative_to(PEERS)
        target = HERE / 'sources' / p.relative_to(PEERS)
        if target.exists():
            assert sha(target) == sha(p), str(p)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(p.read_bytes())
        files[str(p)] = {'source': str(p), 'snapshot': rel(target), 'sha256': sha(target)}
        return rel(target)

    for slug, expected in PACKAGES.items():
        path = PEERS / slug / 'IMPORT_PACKAGE.json'
        assert sha(path) == expected, str(path)
        package = read(path)
        packages.append({'source': rel(path), 'snapshot': freeze(path), 'sha256': expected})
        for entry in package.get('entries', package.get('items', [])):
            receipt = Path(entry.get('identity_receipt', entry.get('approval_path')))
            digest = entry.get('identity_receipt_sha256', entry.get('approval_sha256'))
            assert sha(receipt) == digest, str(receipt)
            receipts[str(receipt)] = receipt
            for ap, ak in [('review_file', 'review_sha256'), ('working_entry_path', 'working_entry_sha256'), ('presentation', 'presentation_sha256')]:
                if entry.get(ap):
                    assert sha(Path(entry[ap])) == entry[ak], entry[ap]
                    freeze(Path(entry[ap]))
            for artifact in entry.get('artifacts', []) + entry.get('evidence_files', []):
                ap = Path(artifact['path'])
                assert sha(ap) == artifact['sha256'], str(ap)
                artifacts[str(ap)] = artifact
                if ap.suffix.lower() in ['.json', '.md', '.txt']:
                    freeze(ap)
        for field in package.get('field_receipts', []):
            path = Path(field['path'])
            assert sha(path) == field['sha256']
            receipts[str(path)] = path

    owner_messages = {}
    for owner, transcript in TRANSCRIPTS.items():
        previous, image_card, users, session = None, None, [], None
        for number, line in enumerate(transcript.open(), 1):
            obj = json.loads(line)
            if obj.get('type') == 'session_meta':
                session = obj['payload']['id']
            payload = obj.get('payload', {})
            if obj.get('type') != 'response_item' or payload.get('type') != 'message':
                continue
            text = '\n'.join(x.get('text', '') for x in payload.get('content', []) if isinstance(x, dict))
            if payload.get('role') == 'assistant' and payload.get('phase') == 'final_answer' and text:
                previous = {'line': number, 'timestamp': obj.get('timestamp'), 'text': text, 'sha256': hashlib.sha256(text.encode()).hexdigest()}
                if 'dropbox.com' in text:
                    image_card = previous
            elif payload.get('role') == 'user':
                users.append({'transcript_path': str(transcript), 'session_id': owner, 'line': number,
                    'timestamp': obj.get('timestamp'), 'user_statement': text, 'text_sha256': hashlib.sha256(text.encode()).hexdigest(),
                    'preceding_assistant_card': previous, 'preceding_component_image_card': image_card})
        assert session == owner
        owner_messages[owner] = users

    normalized = []
    for path in receipts.values():
        d = read(path)
        receipt_snapshot = freeze(path)
        if d['decision_id'] in existing:
            skipped.append({'source_receipt': rel(path), 'source_decision_id': d['decision_id'], 'reason': 'Previously imported exact decision'})
            continue
        cid, owner = d['component_id'], d['owner_session']
        name = d.get('canonical_name', d.get('working_name', d.get('proposed_name')))
        source_user = d.get('source_user_statement')
        statement = d.get('user_statement', source_user.get('text') if isinstance(source_user, dict) else source_user)
        variant = d.get('variant_id', d.get('configuration_key'))
        kind = 'conditional_variant_weight_proposal' if path.name == 'owner-weight-proposal-approval.json' else 'depicted_design_finish_identity'
        expected = d.get('source_review_sha256_before_answer', d.get('source_review_sha256_before_approval'))
        candidates = [p for p in path.parent.glob('*.json') if p.name != path.name and ('pre-' in p.name or 'before-' in p.name)]
        if expected:
            candidates = [p for p in candidates if sha(p) == expected]
        else:
            candidates = [p for p in candidates if p.name == 'component-review.before-keep.json']
        assert len(candidates) == 1, (str(path), expected, [str(x) for x in candidates])
        snapshot = candidates[0]
        v = read(snapshot)
        assert v['component_id'] == cid and name == v.get('proposed_name', v.get('working_name'))
        primary = v.get('primary_image') or v.get('reference_image')
        folder = v['containing_folder']
        reference_only = v.get('primary_image') is None
        iid, fid = primary.get('id', primary.get('file_id')), folder.get('id', folder.get('file_id'))
        assert iid and fid
        image_url = v.get('image_url', primary.get('url'))
        folder_url = v.get('folder_url', folder.get('url'))
        options = [u for u in owner_messages[owner] if u['user_statement'] == statement and u['preceding_assistant_card']]
        if isinstance(source_user, dict):
            options = [u for u in options if u['timestamp'] == source_user['timestamp'] and u['line'] == source_user['line']]
        elif statement.lower() == 'yes':
            question = d.get('preceding_assistant_question')
            if question:
                options = [u for u in options if question in u['preceding_assistant_card']['text']]
            else:
                options = [u for u in options if '6 kg' in u['preceding_assistant_card']['text'] and '2 cm' in u['preceding_assistant_card']['text'] and u['preceding_component_image_card'] and name in u['preceding_component_image_card']['text']]
        assert len(options) == 1, (str(path), statement, len(options))
        evidence = options[0]
        context = evidence['preceding_assistant_card']['text']
        if kind == 'conditional_variant_weight_proposal':
            assert d['accepted_working_weight_kg'] == 6 and not d['actual_mass_established']
            assert cid == 'BC-FP-LEFT' and variant == 'FP-LEFT-WHITE'
            assert name in evidence['preceding_component_image_card']['text'] and image_url in evidence['preceding_component_image_card']['text']
        else:
            assert 'dropbox.com' in context, (str(path), evidence)
            assert name in context and image_url in context
            assert statement.startswith('Keep “') or statement.lower() == 'yes'
            assert not d.get('specifications_explicitly_confirmed', False) and not d.get('specifications_approved', False)
            assert not d.get('approved_specification_proposal_ids_by_this_answer', [])
        assert len(v['specification_review_items']) == 6
        for filename in ['Approval_Presentation.md', 'Current_Metadata.json', 'download-receipts.json', 'download-receipt.json', 'Weight_Research_Proposal.json']:
            f = path.parent / filename
            if f.exists():
                freeze(f)
        normalized.append({'kind': kind, 'component_id': cid, 'variant_id': variant, 'name': name,
            'statement': statement, 'owner_session': owner, 'source_decision_id': d['decision_id'],
            'receipt': receipt_snapshot, 'source_receipt': rel(path), 'source_receipt_sha256': sha(path),
            'recorded_utc': d['recorded_utc'], 'review_number': cp['review_order'].index(cid) + 1,
            'review_snapshot': freeze(snapshot), 'pre_answer_review_sha256': sha(snapshot), 'pre_answer_hash_in_receipt': bool(expected),
            'evidence_file_id': iid, 'folder_id': fid, 'primary_expected': primary, 'folder_expected': folder,
            'reference_only': reference_only, 'image_url': image_url, 'folder_url': folder_url,
            'authoritative_user_evidence': evidence})
    assert len(normalized) == 19 and len(skipped) == 2
    assert len({x['source_decision_id'] for x in normalized}) == len(normalized)
    manifest = {'schema_version': 1, 'cutoff_utc': now, 'packages': packages,
        'scope': 'Five sealed packages after Dune first-pass completion. Ongoing Gleneagles and Panel/Plant/Raked reviews excluded.',
        'decisions': normalized, 'previously_imported_decisions_skipped': skipped, 'files': list(files.values()),
        'evidence_artifact_sha256': list(artifacts.values()), 'approval_inferred': False,
        'current_main_relationship_decision': cp['current_identity_relationship_approval'], 'remote_files_changed': False}
    write(HERE / 'source-manifest.json', manifest)
    write(HERE / 'metadata-requests.json', sorted({d[k] for d in normalized for k in ['evidence_file_id', 'folder_id']}))
    print(json.dumps({'status': 'FROZEN_PENDING_CURRENT_REFERENCE_CHECK', 'decisions': len(normalized),
        'names': sum(x['kind'] != 'conditional_variant_weight_proposal' for x in normalized), 'partial_weight': 1,
        'already_imported_skipped': len(skipped), 'snapshots': len(files), 'artifact_hashes_verified': len(artifacts)}))
    for d in normalized:
        print(d['kind'], d['name'], 'owner_line', d['authoritative_user_evidence']['line'],
              'question_tail', d['authoritative_user_evidence']['preceding_assistant_card']['text'].split('<oai-mem-citation>')[0][-220:])


if __name__ == '__main__':
    main()
