#!/usr/bin/env python3
"""In-place, stable-ID filename normalization from a fresh scoped inventory.

No upload, deletion, directory creation, or sharing mutation is available here.
Plans and per-request journals live outside the project. Write calls require
--apply; an uncertain submission is never blindly retried.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import csv
import fcntl
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import sys
import time
import unicodedata

PROJECT = Path(__file__).resolve().parent.parent
WALL = '/BOLDSTONE MASTER/Products/01 Wall Sculptures'
WORKSHOP = '/BOLDSTONE MASTER/Products/Workshop and Moulding'
IMMUTABLE = ('id', 'parent_id', 'size', 'content_hash', 'client_modified',
             'has_explicit_shared_members', 'sharing_info_present', 'read_only',
             'parent_shared_folder_id', 'file_lock_present')


def now():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value, immutable=False):
    from authorize import private_json
    path = Path(path)
    if immutable and path.exists():
        if json.loads(path.read_text()) != value:
            raise ValueError(f'Immutable evidence already exists: {path}')
        return
    private_json(path, value)


def slug(text):
    value = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode().lower()
    value = re.sub('[^a-z0-9]+', '-', value.replace('&', ' and ')).strip('-')
    if not value:
        raise ValueError('Empty normalized folder name')
    return value


def ordering(row, prefix):
    stem = PurePosixPath(row['name']).stem
    numbered = re.fullmatch(r'(.+)__(\d+)', stem)
    # Keep the current folder's numbered series first. Older prefixes from
    # moves follow, preserving their own series; unnumbered additions are last.
    if numbered and numbered.group(1) + '__' == prefix:
        return (0, '', int(numbered.group(2)), row['name'].casefold(), row['id'])
    if numbered:
        return (1, numbered.group(1).casefold(), int(numbered.group(2)), row['name'].casefold(), row['id'])
    return (2, row['name'].casefold(), 0, row['name'], row['id'])


def plan(entries, run_id):
    folders = {r['id']: r for r in entries if r['kind'] == 'folder'}
    grouped = defaultdict(list)
    ids, paths = set(), set()
    for row in entries:
        if row['id'] in ids or row['path'].casefold() in paths:
            raise ValueError('Duplicate ID or path in input')
        ids.add(row['id']); paths.add(row['path'].casefold())
        if row['kind'] == 'file':
            grouped[row['parent_id']].append(row)
    result = []
    for fid, rows in sorted(grouped.items(), key=lambda item: folders[item[0]]['path'].casefold()):
        parent = folders[fid]
        p = PurePosixPath(parent['path'])
        if parent['path'].startswith(WALL + '/'):
            if len(p.relative_to(WALL).parts) != 2:
                raise ValueError('Unexpected Wall Sculptures folder depth')
        elif parent['path'].startswith(WORKSHOP + '/'):
            if len(p.relative_to(WORKSHOP).parts) != 1:
                raise ValueError('Unexpected workshop folder depth')
        else:
            raise ValueError('Folder is outside the explicitly inventoried scope')
        prefix = slug(p.parent.name) + '__' + slug(p.name) + '__'
        planned, occupied = [], {r['path'].casefold(): r['id'] for r in rows}
        for seq, row in enumerate(sorted(rows, key=lambda r: ordering(r, prefix)), 1):
            if str(PurePosixPath(row['path']).parent).casefold() != parent['path'].casefold():
                raise ValueError('Parent identity/path mismatch')
            if not row.get('rev') or not row.get('content_hash') or row.get('read_only') or row.get('file_lock_present'):
                raise ValueError('Missing integrity evidence or non-writable file')
            name = f'{prefix}{seq:03d}{PurePosixPath(row["name"]).suffix}'
            if len(name.encode('utf-8')) > 255:
                raise ValueError('Filename exceeds portable filename limit')
            planned.append({**row, 'sequence': seq, 'new_name': name,
                            'new_path': str(p / name), 'changed': name != row['name']})
        if len({r['new_path'].casefold() for r in planned}) != len(planned):
            raise ValueError('Duplicate destinations')
        changed = [r for r in planned if r['changed']]
        needs_stage = any(r['new_path'].casefold() in occupied for r in changed)
        stages = []
        if needs_stage:
            for r in changed:
                token = hashlib.sha256(r['id'].encode()).hexdigest()[:24]
                r['temporary_path'] = str(p / f'boldstone-rename-{run_id}-{token}{PurePosixPath(r["name"]).suffix}')
                if r['temporary_path'].casefold() in occupied:
                    raise ValueError('Temporary path already exists')
            stages.append([{'id': r['id'], 'from_path': r['path'], 'to_path': r['temporary_path']} for r in changed])
        if changed:
            stages.append([{'id': r['id'], 'from_path': r.get('temporary_path', r['path']), 'to_path': r['new_path']} for r in changed])
        steps = []
        for phase, stage in enumerate(stages, 1):
            for start in range(0, len(stage), 100):
                steps.append({'phase': phase, 'moves': stage[start:start + 100]})
        result.append({'parent': parent, 'prefix': prefix, 'files': planned, 'steps': steps})
    return result


def prepare(root, run_id='20261026'):
    sources = [root / 'native-before.json', root / 'workshop-before.json']
    entries = [e for p in sources for e in json.loads(p.read_text())['entries']]
    groups = plan(entries, run_id)
    counts = {'files': sum(len(g['files']) for g in groups),
              'renames': sum(r['changed'] for g in groups for r in g['files']),
              'folders': len(groups), 'changed_folders': sum(bool(g['steps']) for g in groups),
              'requests': sum(len(g['steps']) for g in groups),
              'temporary_renames': sum('temporary_path' in r for g in groups for r in g['files'])}
    document = {'schema': 'boldstone-current-path-renumber-v1', 'created_at': now(),
                'authority': 'User requested renaming all current files according to their current location and order.',
                'scope': ['Entire verified Wall Sculptures subtree', 'Seven retained catalogue workshop-reference folders'],
                'ordering': 'Current numbered prefix, then old numbered prefixes in name order, then unnumbered names; contiguous 001 per containing folder.',
                'effects': 'Filename-only moves; IDs, bytes, parent folders, extensions and sharing are retained.',
                'sources': [{'path': str(p), 'sha256': sha(p)} for p in sources],
                'counts': counts, 'groups': groups}
    save(root / 'manifest.json', document, immutable=True)
    with (root / 'rename-manifest.csv').open('x', newline='') as stream:
        fields = ['id', 'parent_id', 'path', 'new_path', 'sequence', 'changed', 'size', 'content_hash', 'rev']
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction='ignore')
        writer.writeheader(); writer.writerows(r for g in groups for r in g['files'])
    os.chmod(root / 'rename-manifest.csv', 0o600)
    print(json.dumps(counts, indent=2), flush=True)


def encode_file(item, parent):
    from dropbox.files import FileMetadata
    from check_bmp_retirement import sharing_flags
    from convert_bmps import head
    if not isinstance(item, FileMetadata):
        raise ValueError('Unexpected child folder or deleted entry')
    if str(PurePosixPath(item.path_lower).parent) != parent['path'].casefold():
        raise ValueError('File moved outside its reviewed parent')
    return {'kind': 'file', **head(item), **sharing_flags(item), 'name': item.name,
            'parent_id': parent['id'], 'path': parent['path'] + '/' + item.name}


def read_folder(client, parent):
    from dropbox.files import FolderMetadata
    native = client.files_get_metadata(parent['id'])
    if not isinstance(native, FolderMetadata) or native.path_display.casefold() != parent['path'].casefold() or native.name != parent['name']:
        raise ValueError('Reviewed parent folder has changed')
    if (native.sharing_info is not None) != parent.get('sharing_info_present', False):
        raise ValueError('Parent sharing has changed')
    found = {}
    cursors = set()
    page = client.files_list_folder(parent['id'], limit=2000, include_has_explicit_shared_members=True)
    while True:
        for item in page.entries:
            row = encode_file(item, parent)
            if row['id'] in found:
                raise ValueError('Duplicate native ID during parent listing')
            found[row['id']] = row
        if not page.has_more:
            return found
        if not isinstance(page.cursor, str) or not page.cursor or page.cursor in cursors:
            raise ValueError('Incomplete parent-folder pagination')
        cursors.add(page.cursor)
        page = client.files_list_folder_continue(page.cursor)


def compare(expected, actual, paths, revisions=None):
    if set(expected) != set(actual):
        raise ValueError(f'Folder membership changed: added={sorted(set(actual)-set(expected))}, absent={sorted(set(expected)-set(actual))}')
    for fid, old in expected.items():
        new = actual[fid]
        for key in IMMUTABLE:
            if old.get(key) != new.get(key):
                raise ValueError(f'File integrity, parent or sharing changed: {fid}: {key}')
        if new['path'].casefold() != paths[fid].casefold() or new['name'] != PurePosixPath(paths[fid]).name:
            raise ValueError(f'File name/path changed unexpectedly: {fid}')
        if revisions is not None and new['rev'] != revisions[fid]:
            raise ValueError(f'Revision changed since last verified state: {fid}')


def poll(client, job):
    deadline = time.monotonic() + 600
    while time.monotonic() < deadline:
        status = client.files_move_batch_check_v2(job)
        if status.is_complete():
            return status.get_complete()
        if not status.is_in_progress():
            raise RuntimeError('Unexpected asynchronous job state')
        time.sleep(2)
    raise RuntimeError('Job remains pending; resume by polling its saved ID')


def validate_result(result, moves, expected, parent):
    if len(result.entries) != len(moves):
        raise ValueError('Batch result count mismatch')
    receipt = []
    for move, entry in zip(moves, result.entries):
        if not entry.is_success():
            receipt.append({'id': move['id'], 'state': 'failed', 'error': str(entry.get_failure())})
            continue
        item = entry.get_success()
        # SDK returns RelocationResult in some routes, FileMetadata in v2.
        item = getattr(item, 'metadata', item)
        row = encode_file(item, parent)
        before = expected[move['id']]
        if row['id'] != move['id'] or row['name'] != PurePosixPath(move['to_path']).name or row['path'].casefold() != move['to_path'].casefold():
            raise ValueError('Native mutation returned a different ID or destination')
        if row['content_hash'] != before['content_hash'] or row['size'] != before['size']:
            raise ValueError('Native mutation returned different image content')
        receipt.append({'id': row['id'], 'state': 'success', 'file': row})
    return receipt


def individual_step(client, moves, home, actual):
    """Use the tested paced executor; resume only receipted or rejected calls."""
    import convert_bmps as worker
    from retire_bmps import RetirementBudget
    from rename_from_paths import move_individuals
    from dropbox.exceptions import ApiError
    worker.BUDGET = RetirementBudget()
    class API:
        def __init__(self): self.client = client
        def read(self, method, *args, **kwargs): return getattr(client, method)(*args, **kwargs)
        def metadata(self, path):
            try: return client.files_get_metadata(path)
            except ApiError as error:
                if error.error.is_path() and error.error.get_path().is_not_found(): return None
                raise
    completed = {}
    directory = home/'individual'
    for intent_path in directory.rglob('file-*-intent.json') if directory.exists() else []:
        if '-retry-' in intent_path.name: continue
        prefix = intent_path.name.removesuffix('-intent.json')
        receipt_path = intent_path.with_name(prefix+'-receipt.json')
        request = json.loads(intent_path.read_text())['request']
        if receipt_path.exists():
            row = json.loads(receipt_path.read_text())['metadata']
            if row['id'] != request['from_path'] or row['path'].casefold() != request['to_path'].casefold():
                raise ValueError('Saved individual receipt does not match its intent')
            completed[row['id']] = {'id': row['id'], 'state':'success', 'file':row}
        else:
            errors = list(intent_path.parent.glob(prefix+'*-error.json'))
            if not errors or any(json.loads(p.read_text()).get('http_status') != 429 for p in errors):
                raise RuntimeError(f'Uncertain individual call requires read-only reconciliation: {intent_path}')
    remaining = [m for m in moves if m['id'] not in completed]
    if remaining:
        attempt = directory/f'attempt-{len(list(directory.glob("attempt-*")))+1:03d}'
        rows = [{'source': actual[m['id']], 'parent_id': actual[m['id']]['parent_id'],
                 'destination_path': m['to_path'], 'destination_name': PurePosixPath(m['to_path']).name} for m in remaining]
        records = move_individuals(API(), rows, attempt)
        completed.update({r['source_id']:{'id':r['source_id'], 'state':r['tag'], 'file':r['metadata']} for r in records})
    return [completed[m['id']] for m in moves]


def apply(root, individual=False, defer_groups=()):
    sys.path.insert(0, str(PROJECT / 'catalogue-review'))
    from delete_dropbox import connection
    from dropbox.files import RelocationPath
    from dropbox.exceptions import RateLimitError
    manifest = json.loads((root / 'manifest.json').read_text())
    manifest_hash = sha(root / 'manifest.json')
    with (root / 'writer.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with connection(PROJECT) as (client, _):
            total = 0
            deferred = []
            for index, group in enumerate(manifest['groups'], 1):
                if not group['steps']:
                    continue
                directory = root / 'operations' / f'{index:04d}'
                if (directory / 'complete.json').exists():
                    total += sum(r['changed'] for r in group['files'])
                    continue
                if group['parent']['id'] in defer_groups:
                    deferred.append(group['parent']['id'])
                    print(f'Deferred known pending job: {group["parent"]["name"]}', flush=True)
                    continue
                expected = {r['id']: r for r in group['files']}
                paths = {fid: r['path'] for fid, r in expected.items()}
                revisions = {fid: r['rev'] for fid, r in expected.items()}
                skip_group = False
                for step_no, step in enumerate(group['steps'], 1):
                    home = directory / f'{step_no:03d}'
                    individual_receipt = None
                    if (home / 'verified.json').exists():
                        done = json.loads((home / 'verified.json').read_text())
                        if done['manifest_sha256'] != manifest_hash:
                            raise ValueError('Receipt belongs to another manifest')
                        paths = {fid: r['path'] for fid, r in done['files'].items()}
                        revisions = {fid: r['rev'] for fid, r in done['files'].items()}
                        continue
                    resumed = (home / 'intent.json').exists()
                    if resumed:
                        state = json.loads((home / 'submission.json').read_text()) if (home / 'submission.json').exists() else {}
                        if state.get('async_job_id'):
                            result = poll(client, state['async_job_id'])
                        elif state.get('mode') == 'individual':
                            # Successful single-file receipts establish the mixed
                            # current state. Only explicitly rejected requests or
                            # requests never submitted may be tried in a new epoch.
                            for receipt_path in (home/'individual').rglob('file-*-receipt.json'):
                                r = json.loads(receipt_path.read_text())['metadata']
                                paths[r['id']] = r['path']; revisions[r['id']] = r['rev']
                            actual = read_folder(client, group['parent'])
                            compare(expected, actual, paths, revisions)
                            individual_receipt = individual_step(client, step['moves'], home, actual)
                        else:
                            raise RuntimeError(f'Uncertain or failed prior submission requires read-only reconciliation: {home}')
                    else:
                        try:
                            actual = read_folder(client, group['parent'])
                            compare(expected, actual, paths, revisions)
                        except ValueError as error:
                            if step_no != 1:
                                raise
                            save(directory / f'stale-preflight-{time.time_ns()}.json',
                                 {'at': now(), 'reason': str(error), 'parent_id': group['parent']['id'],
                                  'native_writes_for_this_group': 0}, immutable=True)
                            deferred.append(group['parent']['id']); skip_group = True
                            print(f'Folder changed during this run; fresh follow-up plan required: {group["parent"]["name"]}', flush=True)
                            break
                        save(home / 'intent.json', {'at': now(), 'manifest_sha256': manifest_hash,
                             'parent': group['parent'], 'moves': step['moves'], 'preflight': actual}, immutable=True)
                        if individual:
                            save(home / 'submission.json', {'at': now(), 'mode': 'individual', 'workers': 1})
                            individual_receipt = individual_step(client, step['moves'], home, actual)
                        else:
                            result = submit_batch(client, step, home, expected, group, paths, revisions)
                    receipt = individual_receipt if individual_receipt is not None else validate_result(result, step['moves'], expected, group['parent'])
                    save(home / 'terminal.json', {'at': now(), 'results': receipt}, immutable=True)
                    if any(r['state'] != 'success' for r in receipt):
                        raise RuntimeError(f'Partial batch failure; inspect {home}')
                    for move in step['moves']:
                        paths[move['id']] = move['to_path']
                    current = read_folder(client, group['parent'])
                    compare(expected, current, paths)
                    revisions = {fid: r['rev'] for fid, r in current.items()}
                    save(home / 'verified.json', {'at': now(), 'manifest_sha256': manifest_hash, 'files': current}, immutable=True)
                if skip_group:
                    continue
                save(directory / 'complete.json', {'at': now(), 'manifest_sha256': manifest_hash,
                     'parent_id': group['parent']['id'], 'renamed': sum(r['changed'] for r in group['files'])}, immutable=True)
                total += sum(r['changed'] for r in group['files'])
                print(f'Verified {total}/{manifest["counts"]["renames"]} renames: {group["parent"]["name"]}', flush=True)
            if deferred:
                save(root / 'execution-partial.json', {'at': now(), 'manifest_sha256': manifest_hash,
                     'verified_renames': total, 'deferred_parent_ids': deferred, 'state': 'OTHER_GROUPS_EXECUTED_PENDING_DEFERRED_GROUPS'})
            else:
                save(root / 'execution-complete.json', {'at': now(), 'manifest_sha256': manifest_hash,
                     'verified_renames': total, 'state': 'EXECUTION_VERIFIED_PER_FOLDER_PENDING_FULL_CENSUS'}, immutable=True)


def submit_batch(client, step, home, expected, group, paths, revisions):
    from dropbox.files import RelocationPath
    from dropbox.exceptions import RateLimitError
    while True:
        try:
            launch = client.files_move_batch_v2(
                [RelocationPath(from_path=m['id'], to_path=m['to_path']) for m in step['moves']],
                autorename=False, allow_ownership_transfer=False)
            break
        except RateLimitError as exc:
            delay = max(1, getattr(exc, 'backoff', None) or 60)
            save(home / 'rate-rejection.json', {'at': now(), 'retry_after': delay})
            print(f'Explicit rate rejection; waiting {delay}s before a fresh preflight', flush=True)
            time.sleep(delay)
            compare(expected, read_folder(client, group['parent']), paths, revisions)
        except Exception as exc:
            save(home / 'submission.json', {'at': now(), 'state': 'UNCERTAIN_OR_REJECTED', 'error_type': type(exc).__name__})
            raise
    if launch.is_async_job_id():
        job = launch.get_async_job_id()
        save(home / 'submission.json', {'at': now(), 'async_job_id': job})
        result = poll(client, job)
    elif launch.is_complete():
        result = launch.get_complete()
    else:
        raise RuntimeError('Unexpected move launch state')
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--individual', action='store_true', help='Use paced synchronous moves rather than asynchronous batches')
    parser.add_argument('--defer-group', action='append', default=[], help='Temporarily leave an explicitly named parent with an already pending native job')
    args = parser.parse_args()
    if args.apply:
        apply(args.root, individual=args.individual, defer_groups=args.defer_group)
    else:
        prepare(args.root)


if __name__ == '__main__':
    main()
