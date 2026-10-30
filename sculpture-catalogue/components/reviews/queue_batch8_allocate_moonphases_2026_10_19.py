"""Queue the next sealed package and continue the existing authorised Moonphases lane."""
import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REVIEWS = ROOT / 'components/reviews'
OUT = ROOT / 'components/parallel-reviews/moonphases-2026-10-19'
RECEIVER = REVIEWS / 'parallel-import-2026-10-19-batch8'
OWNER = '01a13fbf-1cbc-7511-8416-cf339051083e'
SOURCE = ROOT / 'components/parallel-reviews/knight-lava-2026-10-18/IMPORT_PACKAGE.json'
EXPECTED = '6590c3d61f843632f7b740df129c70bc587e76c0e20dbb1e359f104237fa73e2'
read = lambda p: json.loads(p.read_text())
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
rel = lambda p: str(p.relative_to(ROOT))


def write(p, j):
    p.parent.mkdir(parents=True, exist_ok=True)
    t = p.with_name(p.name + '.tmp')
    t.write_text(json.dumps(j, ensure_ascii=False, indent=2) + '\n')
    t.replace(p)


def main():
    ack = OUT / 'COORDINATOR_ACKNOWLEDGEMENT.json'
    assert not ack.exists() and not (RECEIVER / 'received-package.source.json').exists()
    assert sha(SOURCE) == EXPECTED
    package = read(SOURCE)
    assert package['owner_session'] == OWNER and len(package['entries']) == 7
    ids = ['BC-MP-1', 'BC-MP-2', 'BC-MP-3', 'BC-MP-4', 'BC-MP-5']
    paths = {'walkthrough': REVIEWS / 'walkthrough_checkpoint.json',
             'component': ROOT / 'components/checkpoint.json', 'root': ROOT / 'checkpoint.json'}
    docs = {k: read(p) for k, p in paths.items()}
    before = copy.deepcopy(docs)
    hashes = {k: sha(p) for k, p in paths.items()}
    cp, c = docs['walkthrough'], docs['component']
    assert docs['root']['current_component_review'] == c
    assert cp['current_component_id'] == 'BC-MCP-1' and cp['current_size_finish_variant_id'] == 'MCP1-VERDIGRIS-RUST'
    assert not cp['current_answer_recorded']
    assert not any(x['component_id'] in ids for x in cp['parallel_owner_reviews'])
    assert not any(x['receipt'] == rel(SOURCE) for x in cp['parallel_import_queue'])
    progress = read(REVIEWS / 'specification_review_progress.json')
    assert not any(cid in progress['reviews'] for cid in ids)
    model = read(ROOT / 'components/evidence/component_register.json')
    entries = {x['component_id']: x for x in model['components']}
    groups = sorted({g for cid in ids for g in entries[cid]['group_refs']})
    assert groups == ['G' + str(n) for n in range(237, 259) if n != 246]
    backs = next(g for g in model['groups'] if g['group_ref'] == 'G246')
    assert backs['family'] == 'Moonphases' and not backs['component_ids']
    assert backs['id'] == 'id:cnqzTNngPVsAAAAAAAyi6Q'
    groups = sorted(groups + ['G246'])
    transcript = Path('/Users/tprice/.codex/sessions/2026/10/15/rollout-2026-10-15T14-27-31-' + OWNER + '.jsonl')
    lines = transcript.read_text().splitlines()
    assert any(json.loads(s).get('type') == 'session_meta' and json.loads(s)['payload']['id'] == OWNER for s in lines[:5])
    obj = json.loads(lines[13363 - 1]); payload = obj['payload']
    text = '\n'.join(x.get('text', '') for x in payload.get('content', []) if x.get('type') in ['input_text', 'text'])
    assert obj['type'] == 'response_item' and payload['role'] == 'user' and text == 'Go on to the next sculptures'
    assert payload['id'] == 'msg_01a1531c-401c-7070-941a-ce7785caf031'
    protected_paths = [REVIEWS / 'user_classifications.json', REVIEWS / 'specification_review_progress.json',
        ROOT / 'components/evidence/component_register.json', ROOT / cp['register_workbook'],
        ROOT / cp['current_review_record'], ROOT / cp['last_identity_approval']]
    protected = {str(p): sha(p) for p in protected_paths}
    now = datetime.now(timezone.utc).isoformat()
    write(OUT / 'before-allocation-and-queue.json', {'recorded_utc': now,
        'files': {rel(paths[k]): v for k, v in before.items()}, 'protected_sha256': protected})
    RECEIVER.mkdir(parents=True, exist_ok=True)
    (RECEIVER / 'received-package.source.json').write_bytes(SOURCE.read_bytes())
    assert sha(RECEIVER / 'received-package.source.json') == EXPECTED
    received = {'schema_version': 1, 'recorded_utc': now, 'status': 'RECEIVED_NOT_IMPORTED',
        'source_package': rel(SOURCE), 'source_package_sha256': EXPECTED,
        'frozen_received_package': rel(RECEIVER / 'received-package.source.json'),
        'source_owner_session': OWNER, 'hash_verification_only': True,
        'reported_named_entries': 7, 'reported_owner_transcript_lines': 13,
        'pending_checks': ['Full artifact freeze/hash audit', 'Exact owner reply and pre-answer-card verification',
            'Current stable file/folder references', 'Deduplicate already imported Knight scope',
            'Import precisely scoped all-Lava dimensions, conditional weights and fixing type without transferring assumptions',
            'Independent shared-master readback'], 'approval_imported': False,
        'new_owner_fact_or_specification_approval_inferred': False,
        'current_MCP1_review_preserved': True, 'workbook_unchanged': True}
    write(RECEIVER / 'received-package-readback.json', received)
    cp['parallel_import_queue'].append({'package_id': 'KNIGHT-LAVA:2026-10-19:SEALED',
        'scope_kind': 'SEALED_REVIEW_IMPORT_PACKAGE', 'receipt': rel(SOURCE), 'receipt_sha256': EXPECTED,
        'frozen_package_snapshot': rel(RECEIVER / 'received-package.source.json'), 'source_owner_session': OWNER,
        'status': 'SEALED PACKAGE RECEIVED; HASH VERIFIED ONLY; EXACT OWNER AND CURRENT-REFERENCE CHECKS PENDING',
        'approval_imported': False, 'recorded_utc': now, 'new_specification_approval_inferred': False})
    cp['next_serialized_parallel_import'] = {'status': 'QUEUED_PENDING_VERIFICATION',
        'source_package': rel(SOURCE), 'source_package_sha256': EXPECTED,
        'receiver': rel(RECEIVER), 'current_main_review_must_be_preserved': True, 'recorded_utc': now}
    record = {'schema': 'boldstone.coordinator-allocation.v1', 'recorded_utc': now,
        'owner_session': OWNER, 'status': 'ALLOCATED_START_NOW_IN_ISOLATED_LANE',
        'component_ids': ids, 'review_numbers': list(range(80, 85)), 'group_refs': groups,
        'component_groups': {cid: entries[cid]['group_refs'] for cid in ids},
        'unassigned_evidence_groups': {'G246': 'Moonphase Panel Backs; no numbered front or finish bound. Investigate pairing without transferring hardware to all five components.'},
        'isolated_output_directory': rel(OUT), 'main_shared_master_writer': 'root walkthrough',
        'shared_master_writes_allowed': False, 'remote_mutations_allowed': False,
        'source_owner_instruction': {'transcript': str(transcript), 'line': 13363,
            'timestamp': obj['timestamp'], 'message_id': payload['id'], 'role': 'user', 'text': text,
            'text_sha256': hashlib.sha256(text.encode()).hexdigest()},
        'main_reserved_component_ids': ['BC-MCP-1', 'BC-MCP-2', 'BC-MCP-3', 'BC-MCP-4'],
        'other_lane_reserved_component_ids': ['BC-CRATER-WIDE', 'BC-MFW-1', 'BC-MFW-2', 'BC-MOON-RING', 'BC-MOON-CRATER'],
        'prior_batch8_import_dependency': False,
        'instructions': ['Continue only this isolated lane; one identity question at a time with Dropbox example and containing-folder links and all six labelled proposals.',
            'Cover all finishes, individual components and exact arrangement positions in G237–G258. Resolve maker MP codes separately from Dropbox folder numbering.',
            'Keep source claims, owner confirmations, image observations and estimates separate; do not divide set values or treat rotated images as additional moulds.',
            'Freeze each exact pre-answer card and owner reply with stable Dropbox file/folder IDs and hashes. Seal an idempotent root-import package after the block.',
            'Preserve sealed Knight/Lava source unchanged. No shared checkpoint/register/workbook writes and no remote mutations or publication.']}
    write(ack, record)
    for cid, number in zip(ids, range(80, 85)):
        cp['parallel_owner_reviews'].append({'component_id': cid, 'review_number': number,
            'owner_session': OWNER, 'coordinator_acknowledgement': rel(ack),
            'coordinator_acknowledgement_sha256': sha(ack), 'isolated_review_directory': rel(OUT),
            'group_refs': entries[cid]['group_refs'], 'status': 'EXCLUSIVE ISOLATED REVIEW ALLOCATED; ROOT IMPORT REQUIRED',
            'approval_inferred': False, 'master_writer_remains_this_walkthrough': True, 'acknowledged_utc': now})
    cp['after_main_family_next_unclaimed'] = {'component_id': 'BC-LAVA-CORNER', 'review_number': 85}
    cp['updated_utc'] = now
    c.update({'parallel_owner_reviews': copy.deepcopy(cp['parallel_owner_reviews']),
        'parallel_import_queue': copy.deepcopy(cp['parallel_import_queue']),
        'after_main_family_next_unclaimed': copy.deepcopy(cp['after_main_family_next_unclaimed']), 'updated_utc': now})
    docs['root']['current_component_review'] = copy.deepcopy(c); docs['root']['updated_utc'] = now
    for key, value in before['walkthrough'].items():
        if key.startswith('current_') or key in ['proposed_name', 'answer_state', 'question_scope',
            'next_review_after_keep', 'pending_specification_reviews', 'last_parallel_import', 'completed_serialized_parallel_import']:
            assert cp[key] == value, key
    assert all(sha(p) == hashes[k] for k, p in paths.items())
    assert all(sha(Path(p)) == digest for p, digest in protected.items())
    for k, path in paths.items():
        write(path, docs[k]); assert read(path) == docs[k]
    result = {'status': 'PASS', 'acknowledgement': rel(ack), 'sha256': sha(ack),
        'new_allocation': ids, 'batch8_status': 'RECEIVED_NOT_IMPORTED',
        'current_MCP1question_all_prior_approvals_and_batch7_import_preserved': True,
        'root_component_checkpoint_match': read(paths['root'])['current_component_review'] == read(paths['component'])}
    write(OUT / 'coordinator-allocation-readback.json', result)
    event = {'event_id': 'moonphases:allocation-and-batch8-queue:2026-10-19',
        'event': 'EXISTING_AUTHORISED_LANE_EXTENDED_AND_SEALED_PACKAGE_QUEUED_NOT_IMPORTED',
        'recorded_utc': now, 'acknowledgement': rel(ack), 'package_receipt': rel(RECEIVER / 'received-package-readback.json'),
        'new_owner_fact_or_specification_approval_inferred': False, 'no_new_agent_spawned': True}
    for path in [REVIEWS / 'identity_review_journal.jsonl', ROOT / 'review_journal.jsonl']:
        with path.open('a') as f:
            f.write(json.dumps(event, ensure_ascii=False) + '\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
