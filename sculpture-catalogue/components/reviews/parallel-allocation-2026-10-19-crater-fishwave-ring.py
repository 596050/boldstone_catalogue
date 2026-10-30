"""Extend the existing explicitly authorised isolated review lane; root keeps shared writes."""
import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REVIEWS = ROOT / 'components/reviews'
OUT = ROOT / 'components/parallel-reviews/crater-fishwave-ring-2026-10-19'
OWNER = '01a13fe6-495b-7253-b923-31823b4cbca8'
TRANSCRIPT = Path('/Users/tprice/.codex/sessions/2026/10/15/rollout-2026-10-15T15-10-19-' + OWNER + '.jsonl')
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
    assert not ack.exists()
    paths = {'walkthrough': REVIEWS / 'walkthrough_checkpoint.json',
             'component': ROOT / 'components/checkpoint.json', 'root': ROOT / 'checkpoint.json'}
    docs = {k: read(p) for k, p in paths.items()}
    before = copy.deepcopy(docs)
    hashes = {k: sha(p) for k, p in paths.items()}
    cp, c = docs['walkthrough'], docs['component']
    assert docs['root']['current_component_review'] == c
    assert cp['current_component_id'] == 'BC-MCP-1'
    ids = ['BC-CRATER-WIDE', 'BC-MFW-1', 'BC-MFW-2', 'BC-MOON-RING', 'BC-MOON-CRATER']
    assert not any(x['component_id'] in ids for x in cp['parallel_owner_reviews'])
    progress = read(REVIEWS / 'specification_review_progress.json')
    assert not any(cid in progress['reviews'] for cid in ids)
    model = read(ROOT / 'components/evidence/component_register.json')
    entries = {x['component_id']: x for x in model['components']}
    groups = sorted({g for cid in ids for g in entries[cid]['group_refs']})
    assert groups == ['G225', 'G226', 'G227', 'G228', 'G229', 'G230', 'G235', 'G236']
    lines = TRANSCRIPT.read_text().splitlines()
    assert any(json.loads(x).get('type') == 'session_meta' and
               json.loads(x)['payload']['id'] == OWNER for x in lines[:5])
    owner = json.loads(lines[22424 - 1])
    payload = owner['payload']
    text = '\n'.join(x.get('text', '') for x in payload.get('content', []) if x.get('type') in ['input_text', 'text'])
    assert owner['type'] == 'response_item' and payload['role'] == 'user' and text == 'Keep going'
    assert payload['id'] == 'msg_01a15312-5659-77e0-b1a6-9dea0f0b7d49'
    now = datetime.now(timezone.utc).isoformat()
    protected_paths = [REVIEWS / 'user_classifications.json', REVIEWS / 'specification_review_progress.json',
        ROOT / 'components/evidence/component_register.json', ROOT / cp['register_workbook'],
        ROOT / cp['current_review_record'], ROOT / cp['last_identity_approval']]
    protected = {str(p): sha(p) for p in protected_paths}
    record = {'schema': 'boldstone.coordinator-allocation.v1', 'recorded_utc': now,
        'owner_session': OWNER, 'status': 'ALLOCATED_START_NOW_IN_ISOLATED_LANE',
        'component_ids': ids, 'review_numbers': list(range(75, 80)), 'group_refs': groups,
        'component_groups': {cid: entries[cid]['group_refs'] for cid in ids},
        'source_owner_instruction': {'transcript': str(TRANSCRIPT), 'line': 22424,
            'timestamp': owner['timestamp'], 'message_id': payload['id'], 'role': 'user',
            'text': text, 'text_sha256': hashlib.sha256(text.encode()).hexdigest()},
        'isolated_output_directory': rel(OUT), 'main_shared_master_writer': 'root walkthrough',
        'shared_master_writes_allowed': False, 'remote_mutations_allowed': False,
        'main_reserved_component_ids': ['BC-MCP-1', 'BC-MCP-2', 'BC-MCP-3', 'BC-MCP-4'],
        'other_lane_reserved_component_ids': ['BC-KNIGHT', 'BC-LAVA-1', 'BC-LAVA-2', 'BC-LAVA-3'],
        'prior_batch7_import_dependency': False,
        'instructions': [
            'Continue the existing owner-led review lane, one identity at a time with direct Dropbox image and containing-folder links plus all six scoped proposals.',
            'Read source/model evidence; write only this isolated directory. Freeze the exact pre-answer card and owner statement for each decision; retain stable folder and file IDs.',
            'Do not infer dimensions, weight or price by dividing set values; distinguish component, finish, arrangement and adapted water-feature builds.',
            'Mooncrater bowl/water-feature references are not automatically wall sculptures; establish the depicted sale unit and supporting/fixing requirements.',
            'Keep all unconfirmed specifications and picture/provenance gaps explicit. No inventory, platform publication or remote editing is authorised.',
            'Seal an idempotent, hash-bound import package for root after this batch. Preserve the prior Moon/Shellwave sealed package unchanged.'
        ]}
    write(OUT / 'before-allocation.json', {'recorded_utc': now,
        'files': {rel(paths[k]): v for k, v in before.items()}, 'protected_sha256': protected})
    write(ack, record)
    for cid, number in zip(ids, range(75, 80)):
        cp['parallel_owner_reviews'].append({'component_id': cid, 'review_number': number,
            'owner_session': OWNER, 'coordinator_acknowledgement': rel(ack),
            'coordinator_acknowledgement_sha256': sha(ack), 'isolated_review_directory': rel(OUT),
            'group_refs': entries[cid]['group_refs'], 'status': 'EXCLUSIVE ISOLATED REVIEW ALLOCATED; ROOT IMPORT REQUIRED',
            'approval_inferred': False, 'master_writer_remains_this_walkthrough': True, 'acknowledged_utc': now})
    reservation = {'component_ids': record['main_reserved_component_ids'], 'global_reviews': [71, 72, 73, 74],
        'status': 'MAIN MOON CRATER PHASE FAMILY; ALL INDIVIDUAL FINISHES AND ARRANGEMENT ATTRIBUTIONS'}
    cp['main_family_review_reservation'] = copy.deepcopy(reservation)
    cp['after_main_family_next_unclaimed'] = {'component_id': 'BC-MP-1', 'review_number': 80}
    cp['updated_utc'] = now
    c.update({'parallel_owner_reviews': copy.deepcopy(cp['parallel_owner_reviews']),
        'main_family_review_reservation': copy.deepcopy(reservation),
        'after_main_family_next_unclaimed': copy.deepcopy(cp['after_main_family_next_unclaimed']), 'updated_utc': now})
    docs['root']['current_component_review'] = copy.deepcopy(c)
    docs['root']['updated_utc'] = now
    for key, value in before['walkthrough'].items():
        if key.startswith('current_') or key in ['pending_specification_reviews', 'parallel_import_queue', 'next_serialized_parallel_import']:
            assert cp[key] == value, key
    assert all(sha(p) == hashes[k] for k, p in paths.items())
    assert all(sha(Path(p)) == digest for p, digest in protected.items())
    for k, p in paths.items():
        write(p, docs[k])
        assert read(p) == docs[k]
    result = {'status': 'PASS', 'acknowledgement': rel(ack), 'sha256': sha(ack),
        'components': ids, 'main_question_and_pending_import_preserved': True,
        'root_component_checkpoint_match': read(paths['root'])['current_component_review'] == read(paths['component'])}
    write(OUT / 'coordinator-allocation-readback.json', result)
    event = {'event_id': 'crater-fishwave-ring:allocation:2026-10-19', 'event': 'EXISTING_AUTHORISED_LANE_EXTENDED',
        'recorded_utc': now, 'acknowledgement': rel(ack), 'component_ids': ids, 'no_new_agent_spawned': True}
    for p in [REVIEWS / 'identity_review_journal.jsonl', ROOT / 'review_journal.jsonl']:
        with p.open('a') as f:
            f.write(json.dumps(event, ensure_ascii=False) + '\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
