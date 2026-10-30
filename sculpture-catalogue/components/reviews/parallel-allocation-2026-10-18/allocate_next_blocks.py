"""Reserve two disjoint existing review lanes under verified owner instructions."""
import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
read = lambda p: json.loads(p.read_text())
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
rel = lambda p: str(p.relative_to(ROOT))


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    temporary.replace(path)


def authorization(session, transcript, needle):
    found, verified = None, False
    for number, line in enumerate(Path(transcript).open(), 1):
        event = json.loads(line)
        payload = event.get('payload', {})
        if event['type'] == 'session_meta':
            verified = payload.get('id') == session
        if event['type'] == 'response_item' and payload.get('role') == 'user':
            text = '\n'.join(x.get('text', '') for x in payload.get('content', []))
            if needle in text:
                found = {'owner_session': session, 'transcript': transcript, 'line': number,
                    'timestamp': event['timestamp'], 'message_id': payload.get('id'), 'role': 'user',
                    'text': text, 'text_sha256': hashlib.sha256(text.encode()).hexdigest()}
    assert verified and found
    return found


def main():
    assert not (HERE / 'allocation-readback.json').exists(), 'Allocation already recorded'
    paths = {name: ROOT / file for name, file in {
        'walkthrough': 'components/reviews/walkthrough_checkpoint.json',
        'component': 'components/checkpoint.json', 'root': 'checkpoint.json'}.items()}
    docs = {name: read(path) for name, path in paths.items()}
    hashes = {name: sha(path) for name, path in paths.items()}
    cp, component, master = (docs[name] for name in ['walkthrough', 'component', 'root'])
    assert master['current_component_review'] == component
    assert cp['parallel_owner_reviews'] == component['parallel_owner_reviews']
    assert cp['parallel_import_queue'] == component['parallel_import_queue']
    assert cp['current_size_finish_variant_id'] == 'DR-SPIRAL-GOLD' and cp['current_answer_recorded']
    model = read(ROOT / 'components/evidence/component_register.json')
    by_id = {x['component_id']: x for x in model['components']}
    a, b = '01a13fbf-1cbc-7511-8416-cf339051083e', '01a13fe6-495b-7253-b923-31823b4cbca8'
    proof = [authorization(a,
        '/Users/tprice/.codex/sessions/2026/10/15/rollout-2026-10-15T14-27-31-01a13fbf-1cbc-7511-8416-cf339051083e.jsonl',
        'Do whatever is required to continue:'), authorization(b,
        '/Users/tprice/.codex/sessions/2026/10/15/rollout-2026-10-15T15-10-19-01a13fe6-495b-7253-b923-31823b4cbca8.jsonl',
        'Do this: This batch’s reviews are finished.')]
    protected_paths = [ROOT / 'components/evidence/component_register.json',
        ROOT / 'components/reviews/user_classifications.json', ROOT / 'components/reviews/specification_review_progress.json',
        ROOT / cp['current_review_record'], ROOT / cp['last_identity_approval'], ROOT / cp['register_workbook'],
        ROOT.parent / 'Boldstone_Wall_Sculptures_Matched_All_Fields_2026-10-15.xlsx']
    protected = {str(path): sha(path) for path in protected_paths}
    before = copy.deepcopy(docs)
    now = datetime.now(timezone.utc).isoformat()
    write(HERE / 'before-allocation.json', {'recorded_utc': now, 'files': {rel(paths[k]): v for k, v in before.items()},
        'protected_sha256': protected})
    write(HERE / 'verified-owner-instructions.json', {'recorded_utc': now, 'instructions': proof})
    blocks = [
        (a, ['BC-GLEN-1', 'BC-GLEN-2', 'BC-GLEN-3', 'BC-GLEN-4'], 'gleneagles-2026-10-18'),
        (b, ['BC-AZURE', 'BC-WBMS-WAVE', 'BC-WBMS-MOON'], 'azure-wave-moonshadow-2026-10-18')]
    old_reservations = {x['component_id'] for x in cp['parallel_owner_reviews']}
    new_ids = [cid for _, ids, _ in blocks for cid in ids]
    assert len(set(new_ids)) == len(new_ids) == 7 and not old_reservations.intersection(new_ids)
    assert not set(new_ids).intersection(['BC-DR-WAVE1', 'BC-DR-SPIRAL', 'BC-DR-WAVE3', 'BC-MIX-SPIRALS'])
    for owner, ids, directory in blocks:
        acknowledgement = ROOT / 'components/parallel-reviews' / directory / 'COORDINATOR_ACKNOWLEDGEMENT.json'
        assert not acknowledgement.exists()
        reservations = [{'component_id': cid, 'review_number': cp['review_order'].index(cid) + 1,
            'owner_session': owner, 'coordinator_acknowledgement': rel(acknowledgement),
            'isolated_review_directory': rel(acknowledgement.parent),
            'status': 'RESERVED FOR EXISTING PARALLEL LANE; OWNER AUTHORIZED CONTINUATION',
            'start_trigger': 'Immediately after prior lane package sealing; no dependency on Dune Ripple owner answers or shared import',
            'approval_inferred': False, 'acknowledged_utc': now} for cid in ids]
        groups = sorted({g for cid in ids for g in by_id[cid]['group_refs']})
        scope = ('All finishes/sizes for the reserved component IDs only. One component/finish question at a time, '
            'with Dropbox image/folder stable IDs and all six source-or-guess specification fields. '
            'Arrangement-only references must state the component position and retain missing isolated-photo gaps. '
            'Do not divide set dimensions, mass or prices or infer mould/manufacture/stock from pictures or named Keeps. '
            'Main remains sole shared writer/importer; isolated immutable receipts; no remote or shared mutations. '
            'BC-MIX-SPIRALS123 and DuneRipple36–38 are excluded.')
        write(acknowledgement, {'recorded_utc': now, 'reservation': reservations, 'group_refs': groups,
            'scope': scope, 'authorization_evidence': rel(HERE / 'verified-owner-instructions.json')})
        cp['parallel_owner_reviews'] += reservations
    packages = [
        ('components/parallel-reviews/frozenfish-2026-10-18/IMPORT_PACKAGE.json',
         '476ebce9cbe497db90ba4bf273dca8b3b1e4e7d8709a480ecbd0de07c1e5d6a1'),
        ('components/parallel-reviews/strata-textures-2026-10-18/IMPORT_PACKAGE.json',
         '815be04df630c12278e1e823b7d553483886794ceae15bfe8e0d90a0e8770493')]
    for path, expected in packages:
        assert sha(ROOT / path) == expected
        assert not any(x.get('receipt') == path for x in cp['parallel_import_queue'])
        cp['parallel_import_queue'].append({'component_id': None, 'variant_id': None,
            'scope_kind': 'REVIEW_IMPORT_PACKAGE', 'receipt': path, 'receipt_sha256': expected,
            'status': 'SEALED PACKAGE RECEIVED; PENDING NEXT BOUNDED INDEPENDENT IMPORT',
            'approval_imported': False, 'recorded_utc': now,
            'scope': 'Package SHA verified only. Exact transcript/source/current-reference checks and idempotent import remain pending. '
                'Five name-only decisions and30pending groups reported per package; no new specification approvals or physical verification inferred.'})
    cp['updated_utc'] = now
    component['parallel_owner_reviews'] = copy.deepcopy(cp['parallel_owner_reviews'])
    component['parallel_import_queue'] = copy.deepcopy(cp['parallel_import_queue'])
    component['updated_utc'] = now
    master['current_component_review'] = copy.deepcopy(component)
    master['updated_utc'] = now
    for key, value in before['walkthrough'].items():
        if key not in ['parallel_owner_reviews', 'parallel_import_queue', 'updated_utc']:
            assert cp[key] == value
    assert all(sha(path) == hashes[name] for name, path in paths.items()), 'Shared writer collision'
    for name, path in paths.items():
        write(path, docs[name])
        assert read(path) == docs[name]
    assert all(sha(Path(path)) == value for path, value in protected.items())
    assert read(paths['root'])['current_component_review'] == read(paths['component'])
    result = {'status': 'PASS', 'recorded_utc': now, 'new_reserved_component_ids': new_ids,
        'new_queued_packages': [x[0] for x in packages], 'shared_owner_decisions_or_specs_imported': 0,
        'active_gold_question_and_answer_preserved': True, 'ledger_progress_model_and_workbooks_preserved': True,
        'single_shared_writer_preserved': True, 'no_remote_mutations': True}
    write(HERE / 'allocation-readback.json', result)
    print(json.dumps(result))


if __name__ == '__main__':
    main()
