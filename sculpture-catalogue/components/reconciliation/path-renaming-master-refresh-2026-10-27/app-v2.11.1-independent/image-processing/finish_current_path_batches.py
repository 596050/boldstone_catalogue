#!/usr/bin/env python3
"""Continue a filename manifest in disjoint native batches with full readbacks."""
from __future__ import annotations
import argparse
import fcntl
import json
from pathlib import Path, PurePosixPath
import sys
import time
from types import SimpleNamespace

from renumber_current_paths import (PROJECT, IMMUTABLE, WALL, WORKSHOP, save, sha, now,
                                    encode_file, read_folder, validate_result)


class ReadAPI:
    def __init__(self, client): self.client = client
    def read(self, method, *args, **kwargs): return getattr(self.client, method)(*args, **kwargs)
    def metadata(self, path): return self.read('files_get_metadata', path)


def inventory(client, manifest):
    from check_bmp_retirement import census
    wall = census(ReadAPI(client))
    workshop = []
    for group in manifest['groups']:
        parent = group['parent']
        if parent['path'].startswith(WORKSHOP+'/'):
            workshop.append(parent)
            workshop.extend(read_folder(client, parent).values())
    return {'recorded_utc': now(), 'wall': wall,
            'workshop': {'entries': workshop, 'pagination_exhausted': True}}


def candidates(manifest, snapshot):
    rows = snapshot['wall']['entries'] + snapshot['workshop']['entries']
    current = {r['id']: r for r in rows}
    parents = {}
    for row in rows:
        if row['kind'] == 'file': parents.setdefault(row['parent_id'], {})[row['id']] = row
    moves, deferred, done = [], [], 0
    for group in manifest['groups']:
        parent = group['parent']; expected = {r['id']: r for r in group['files']}
        actual = parents.get(parent['id'], {})
        reason = None
        folder = current.get(parent['id'])
        if not folder or folder['path'].casefold() != parent['path'].casefold() or folder['name'] != parent['name']:
            reason = 'parent_changed'
        elif set(actual) != set(expected): reason = 'membership_changed'
        else:
            for fid, old in expected.items():
                new = actual[fid]
                if any(old.get(k) != new.get(k) for k in IMMUTABLE):
                    reason = 'content_or_access_changed'; break
                allowed = {old['path'].casefold(), old['new_path'].casefold()}
                if old.get('temporary_path'): allowed.add(old['temporary_path'].casefold())
                if new['path'].casefold() not in allowed:
                    reason = 'unexpected_external_name'; break
        if reason:
            deferred.append({'parent_id': parent['id'], 'path': parent['path'], 'reason': reason,
                             'absent': sorted(set(expected)-set(actual)), 'added': sorted(set(actual)-set(expected))})
            continue
        occupied = {r['path'].casefold(): fid for fid, r in actual.items()}
        for fid, old in expected.items():
            new = actual[fid]
            if new['path'].casefold() == old['new_path'].casefold() and new['name'] == old['new_name']:
                done += 1; continue
            if old['new_path'].casefold() not in occupied:
                destination = old['new_path']
            elif old.get('temporary_path') and new['path'].casefold() != old['temporary_path'].casefold():
                destination = old['temporary_path']
            else:
                continue  # A dependency moves in this wave; revisit after readback.
            if destination.casefold() in occupied:
                raise ValueError('An unexpected file occupies a temporary target')
            moves.append({'id': fid, 'from_path': new['path'], 'to_path': destination,
                          'source': new, 'parent': parent, 'final': destination == old['new_path']})
    # Complete outstanding temporary names first; then process native folder/name order.
    moves.sort(key=lambda m: ('boldstone-rename-' not in PurePosixPath(m['from_path']).name,
                              m['parent']['path'].casefold(), m['to_path'].casefold()))
    if len({m['to_path'].casefold() for m in moves}) != len(moves):
        raise ValueError('Ready destinations collide')
    return moves, deferred, done


def wait_job(client, job):
    start = time.monotonic(); last_report = start
    while True:
        status = client.files_move_batch_check_v2(job)
        if status.is_complete(): return status.get_complete()
        if not status.is_in_progress(): raise RuntimeError('Unexpected native job state')
        if time.monotonic()-last_report >= 45:
            print(f'Native batch pending for {round(time.monotonic()-start)} seconds; no replacement submission.', flush=True)
            last_report = time.monotonic()
        time.sleep(2)


def run(root, limit):
    sys.path.insert(0, str(PROJECT/'catalogue-review'))
    from delete_dropbox import connection
    from dropbox.files import RelocationPath
    from dropbox.exceptions import RateLimitError
    manifest = json.loads((root/'manifest.json').read_text()); digest = sha(root/'manifest.json')
    with (root/'writer.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX|fcntl.LOCK_NB)
        with connection(PROJECT) as (client, _):
            sequence = 0
            while True:
                sequence += 1; home = root/'bulk-operations'/f'{sequence:03d}'
                if (home/'verified.json').exists(): continue
                if (home/'intent.json').exists():
                    intent = json.loads((home/'intent.json').read_text())
                    assert intent['manifest_sha256'] == digest
                    moves = intent['moves']; deferred = intent['deferred']
                    if (home/'terminal.json').exists():
                        receipt = json.loads((home/'terminal.json').read_text())['results']
                        result = None
                    elif (home/'submission.json').exists():
                        state = json.loads((home/'submission.json').read_text())
                        if not state.get('async_job_id'):
                            raise RuntimeError('Unknown or rejected submission needs reconciliation before another write')
                        result = wait_job(client, state['async_job_id'])
                    else: raise RuntimeError('Uncertain submission cannot be automatically repeated')
                else:
                    if (root/'hold-new-batches.json').exists():
                        save(root/'held-before-next-batch.json',{'at':now(),'next_batch':sequence,
                             'reason':json.loads((root/'hold-new-batches.json').read_text()),
                             'all_prior_batches_verified':True})
                        print('All submitted batches reconciled. Further submissions held for app/native job coordination.',flush=True)
                        return
                    before = inventory(client, manifest)
                    moves, deferred, done = candidates(manifest, before)
                    save(home/'before.json', before, immutable=True)
                    print(f'Full readback: {done}/{manifest["counts"]["files"]} planned names correct; {len(moves)} ready; {len(deferred)} externally changed folders.', flush=True)
                    if not moves:
                        save(root/'batch-pass-complete.json', {'at':now(), 'manifest_sha256':digest,
                             'correct_names':done,'deferred':deferred,'last_readback':str(home/'before.json'),
                             'last_readback_sha256':sha(home/'before.json')}, immutable=True)
                        return
                    moves = moves[:limit]
                    save(home/'intent.json', {'at':now(),'manifest_sha256':digest,'moves':moves,
                         'deferred':deferred,'before_sha256':sha(home/'before.json')}, immutable=True)
                    try:
                        launch = client.files_move_batch_v2([RelocationPath(from_path=m['id'],to_path=m['to_path']) for m in moves],
                                                           autorename=False,allow_ownership_transfer=False)
                    except Exception as error:
                        save(home/'submission.json', {'at':now(),'error_type':type(error).__name__,
                             'explicit_rejection':isinstance(error,RateLimitError)}, immutable=True)
                        raise
                    if launch.is_async_job_id():
                        save(home/'submission.json', {'at':now(),'async_job_id':launch.get_async_job_id()}, immutable=True)
                        result = wait_job(client, launch.get_async_job_id())
                    elif launch.is_complete(): result = launch.get_complete()
                    else: raise RuntimeError('Unexpected batch launch')
                if result is not None:
                    if len(result.entries) != len(moves): raise ValueError('Native result count differs')
                    receipt = []
                    for move, entry in zip(moves,result.entries):
                        receipt.extend(validate_result(SimpleNamespace(entries=[entry]),[move],
                                                       {move['id']:move['source']},move['parent']))
                    save(home/'terminal.json', {'at':now(),'results':receipt}, immutable=True)
                after = inventory(client,manifest)
                rows = {r['id']:r for r in after['wall']['entries']+after['workshop']['entries']}
                for move, result_row in zip(moves,receipt):
                    current = rows.get(move['id'])
                    if result_row['state'] == 'success':
                        if not current or current['path'].casefold() != move['to_path'].casefold() or current['name'] != PurePosixPath(move['to_path']).name:
                            raise ValueError('Independent destination readback differs')
                    elif result_row.get('error') != "RelocationBatchErrorEntry('too_many_write_operations', None)":
                        raise RuntimeError(f'Native rename failed: {result_row}')
                    else:
                        if not current or any(current.get(k)!=move['source'].get(k) for k in (*IMMUTABLE,'rev','name','path')):
                            raise ValueError('Explicitly rejected file no longer has its preflight state')
                    if any(current.get(k)!=move['source'].get(k) for k in IMMUTABLE):
                        raise ValueError('Independent content, parent or sharing readback differs')
                save(home/'after.json',after,immutable=True)
                save(home/'verified.json',{'at':now(),'manifest_sha256':digest,'success':sum(x['state']=='success' for x in receipt),
                     'rejected':sum(x['state']!='success' for x in receipt),'after_sha256':sha(home/'after.json')},immutable=True)
                print(f'Batch {sequence} independently verified: {sum(x["state"]=="success" for x in receipt)} moves.',flush=True)
                if any(x['state']!='success' for x in receipt): time.sleep(30)


if __name__ == '__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--apply',action='store_true');parser.add_argument('--batch-size',type=int,default=500)
    args=parser.parse_args()
    if not args.apply: raise SystemExit('--apply required')
    if not 1<=args.batch_size<=1000: raise SystemExit('Batch size must be 1..1000')
    run(args.root,args.batch_size)
