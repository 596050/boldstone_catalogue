#!/usr/bin/env python3
"""Execute the owner's scoped wording change, preserving identities and bytes."""
from pathlib import Path, PurePosixPath
import argparse
import fcntl
import json
import os
import re
import sys
import urllib.request

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[2]
sys.path.insert(0, str(PROJECT / 'catalogue-review'))
from delete_dropbox import connection, missing, stamp
from dropbox_sync_worker import encode_entry, atomic_json

FAMILY = '/BOLDSTONE MASTER/Products/01 Wall Sculptures/Deco Palm and Spiral'
RUNTIME = Path.home() / 'Library/Application Support/BoldstoneReview'
PATTERN = re.compile(r'two[ -]leaves[ -]1\b', re.I)

def save_new(name, value):
    path = HERE / name
    with path.open('x') as stream:
        os.chmod(path, 0o600)
        json.dump(value, stream, indent=2, ensure_ascii=False)
        stream.flush()
        os.fsync(stream.fileno())

def listing(client):
    page = client.files_list_folder(FAMILY, recursive=True, include_deleted=False, limit=2000)
    rows = [encode_entry(x) for x in page.entries]
    cursors = set()
    while page.has_more:
        assert page.cursor and page.cursor not in cursors, 'Incomplete listing'
        cursors.add(page.cursor)
        page = client.files_list_folder_continue(page.cursor)
        rows.extend(encode_entry(x) for x in page.entries)
    assert len({x['id'] for x in rows}) == len(rows)
    assert all(x['path'] == FAMILY or x['path'].startswith(FAMILY + '/') for x in rows)
    rows = [x for x in rows if x['path'] != FAMILY]
    return {x['id']: x for x in rows}

def new_path(path):
    return path.replace('Two Leaves 1', 'Acanthus Two Leaves').replace('two-leaves-1', 'acanthus-two-leaves')

def verify_content(a, b):
    assert a['id'] == b['id'] and a['kind'] == b['kind']
    if a['kind'] == 'file':
        assert a['content_hash'] == b['content_hash'] and a['bytes'] == b['bytes'], 'Contents changed'

def prepare(client):
    rows = listing(client)
    connector = json.loads((HERE / 'connector-plan.json').read_text())
    expected = {r['id'] for r in connector['entries']}
    selected = {fid: r for fid, r in rows.items() if PATTERN.search(r['name'])}
    assert set(selected) == expected, 'The requested rename membership changed'
    moves = []
    occupied = {r['path'].casefold(): fid for fid, r in rows.items()}
    for fid, row in selected.items():
        target = new_path(row['path'])
        assert target != row['path'] and target.startswith(FAMILY + '/')
        assert len(PurePosixPath(target).name.encode()) <= 255
        assert occupied.get(target.casefold(), fid) == fid, 'Destination collision'
        moves.append({'id': fid, 'kind': row['kind'], 'source': row['path'], 'destination': target})
    assert len({m['destination'].casefold() for m in moves}) == len(moves)
    moves.sort(key=lambda m: (m['kind'] != 'folder', m['source'].casefold()))
    plan = {'namespace_id': '202238505', 'root': FAMILY, 'at': stamp(), 'before': rows, 'moves': moves}
    save_new('native-plan.json', plan)
    print(json.dumps({'state': 'planned', 'folders': sum(m['kind'] == 'folder' for m in moves),
                      'files': sum(m['kind'] == 'file' for m in moves), 'inventory_entries': len(rows)}), flush=True)

def apply(client):
    plan = json.loads((HERE / 'native-plan.json').read_text())
    assert plan['root'] == FAMILY and plan['namespace_id'] == '202238505'
    lock_path = RUNTIME / 'native-jobs/writer.lock'
    with lock_path.open('a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        reservation = RUNTIME / 'native-writer-reservation.json'
        old = reservation.read_bytes() if reservation.exists() else None
        assert not old or not json.loads(old).get('active'), 'Another native writer is reserved'
        jobs = json.load(urllib.request.urlopen('http://127.0.0.1:8767/api/jobs', timeout=10))
        assert jobs['active_count'] == 0, 'Existing jobs must finish first'
        atomic_json(reservation, {'active': True, 'label': 'Acanthus Two Leaves names',
                                 'reason': 'Renaming the two reviewed folders and 27 files; queued jobs will continue afterwards.',
                                 'owner': str(HERE), 'at': stamp()})
        try:
            current = listing(client)
            assert set(current) == set(plan['before']), 'Family membership changed before rename'
            for fid, before in plan['before'].items():
                verify_content(before, current[fid])
                assert current[fid]['path'] == before['path'], 'A path changed before rename'
            folders = [m for m in plan['moves'] if m['kind'] == 'folder']
            for i, move in enumerate(plan['moves'], 1):
                before = plan['before'][move['id']]
                observed = encode_entry(client.files_get_metadata(move['id']))
                verify_content(before, observed)
                source = move['source']
                if move['kind'] == 'file':
                    for folder in folders:
                        if source.startswith(folder['source'] + '/'):
                            source = folder['destination'] + source[len(folder['source']):]
                assert observed['path'] == source, 'File location changed during rename'
                try:
                    client.files_get_metadata(move['destination'])
                except Exception as exc:
                    if not missing(exc):
                        raise
                else:
                    raise ValueError('Destination exists; refusing overwrite')
                save_new(f'{i:02d}-intent.json', {'move': move, 'observed': observed, 'at': stamp()})
                try:
                    client.files_move_v2(move['id'], move['destination'], autorename=False, allow_ownership_transfer=False)
                except Exception:
                    # A lost response is checked once, never blindly resubmitted.
                    check = encode_entry(client.files_get_metadata(move['id']))
                    if check['path'] != move['destination']:
                        raise RuntimeError('Move not confirmed; stop without repeating it') from None
                after = encode_entry(client.files_get_metadata(move['id']))
                verify_content(before, after)
                assert after['path'] == move['destination']
                save_new(f'{i:02d}-receipt.json', {'before': before, 'after': after, 'at': stamp()})
                print(json.dumps({'completed': i, 'total': len(plan['moves']), 'kind': move['kind'], 'name': after['name']}), flush=True)
            final = listing(client)
            assert set(final) == set(plan['before']), 'Inventory identities changed'
            for fid, before in plan['before'].items():
                verify_content(before, final[fid])
                assert final[fid]['path'] == new_path(before['path'])
            assert not any(PATTERN.search(r['path']) for r in final.values())
            save_new('verification.json', {'status': 'PASS', 'at': stamp(), 'namespace_id': '202238505',
                'folders_renamed': len(folders), 'files_renamed': len(plan['moves']) - len(folders),
                'all_file_hashes_and_sizes_unchanged': True, 'all_ids_preserved': True, 'after': final})
            print(json.dumps({'state': 'verified', 'entries': len(final), 'remaining_old_names': 0}), flush=True)
        finally:
            value = json.loads(reservation.read_text())
            if value.get('owner') == str(HERE):
                if old is None:
                    reservation.unlink()
                else:
                    atomic_json(reservation, json.loads(old))

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['plan', 'apply'])
    args = parser.parse_args()
    with connection(PROJECT) as (client, _):
        (prepare if args.mode == 'plan' else apply)(client)
