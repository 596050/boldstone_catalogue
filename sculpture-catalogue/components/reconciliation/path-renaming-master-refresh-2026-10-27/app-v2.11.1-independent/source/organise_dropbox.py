#!/usr/bin/env python3
"""Create/reuse an exact role folder and move one stable original without copying.

Each native intent is durable before submission. A lost response is read back;
it is never blindly retried. No folder is renamed or removed by this worker.
"""
from pathlib import Path, PurePosixPath
import argparse
import json
import re
import sys

from delete_dropbox import connection, inspect_file, missing, stamp
from dropbox_sync import ROOT_PATH
from organisation import slug


def save(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as f:
        json.dump(value, f, indent=2)
        f.flush()
        import os
        os.fsync(f.fileno())


def all_entries(client, path):
    result = client.files_list_folder(path, recursive=False, include_deleted=False)
    entries = list(result.entries); cursors = set()
    while result.has_more:
        if not result.cursor or result.cursor in cursors:
            raise ValueError('Dropbox returned an incomplete destination folder listing.')
        cursors.add(result.cursor)
        result = client.files_list_folder_continue(result.cursor)
        entries.extend(result.entries)
    return entries


def get_or_none(client, path):
    try:
        return client.files_get_metadata(path)
    except Exception as e:
        if missing(e):
            return None
        raise


def validate_folder(value, path):
    if not value or getattr(value, 'rev', None) or not getattr(value, 'id', None):
        raise ValueError('The destination is not a Dropbox folder.')
    if (getattr(value, 'path_display', '') or '').casefold() != path.casefold():
        raise ValueError('Dropbox returned a different destination folder.')


def verify_links(client, before):
    checked = []
    for link in before['sharing']['links']:
        if not link.get('direct'):
            continue
        value = client.sharing_get_shared_link_metadata(link['url'])
        if getattr(value, 'id', None) != before['id']:
            raise ValueError('An existing direct image link did not resolve to the original file.')
        checked.append(link['url'])
    return checked


def explicitly_rejected(error):
    if getattr(error, 'status_code', None) == 429:
        return True
    value = getattr(error, 'error', None)
    if value and getattr(value, 'is_to', lambda: False)():
        target = value.get_to()
        return any(getattr(target, 'is_' + tag, lambda: False)() for tag in
                   ('conflict', 'no_write_permission', 'insufficient_space', 'disallowed_name', 'too_many_write_operations'))
    return False


def organise(client, request, journal):
    journal = Path(journal); journal.mkdir(parents=True, exist_ok=True)
    if (journal / 'result.json').exists():
        return json.loads((journal / 'result.json').read_text())
    target = request['destination_folder']
    parts = PurePosixPath(target).parts
    root_parts = PurePosixPath(ROOT_PATH).parts
    if parts[:len(root_parts)] != root_parts or len(parts) != len(root_parts) + 2 or any(p in ('.', '..') for p in target.split('/')):
        raise ValueError('Choose one component folder directly inside a verified Wall Sculptures family.')
    before = inspect_file(client, request['binding'], ROOT_PATH)
    if (journal / 'move-intent.json').exists():
        intent = json.loads((journal / 'move-intent.json').read_text())
        if before['path'].casefold() != intent['destination'].casefold():
            return {'state': 'uncertain', 'message': 'A previous move was submitted. Its destination is not verified; no move was repeated.'}
        folder = client.files_get_metadata(target)
        validate_folder(folder, target)
        result = {'state': 'completed', 'file': {**before, 'folder_id': folder.id},
                  'checked_utc': stamp(), 'recovered_by_readback': True,
                  'direct_links_verified': verify_links(client, intent['before'])}
        save(journal / 'result.json', result)
        return result
    if before['path'].casefold() != request['binding']['path'].casefold():
        raise ValueError('The original moved outside this job. Refresh its location before organising it.')
    family_path = str(PurePosixPath(target).parent)
    validate_folder(client.files_get_metadata(family_path), family_path)
    folder = get_or_none(client, target)
    if folder is None:
        save(journal / 'folder-intent.json', {'path': target, 'at': stamp()})
        try:
            client.files_create_folder_v2(target, autorename=False)
        except Exception:
            # A conflict/transport error can mean the exact folder now exists.
            # Read it back; never use an automatically suffixed folder.
            folder = get_or_none(client, target)
            if folder is None:
                raise ValueError('Folder creation was not confirmed. No image move was attempted.') from None
        folder = client.files_get_metadata(target)
    validate_folder(folder, target)
    target = folder.path_display
    prefix = slug(PurePosixPath(target).parent.name) + '__' + slug(PurePosixPath(target).name) + '__'
    ext = PurePosixPath(before['name']).suffix
    if len((prefix + '001' + ext).encode()) > 255:
        raise ValueError('The path-derived filename is too long. Choose shorter component folder names.')
    entries = all_entries(client, folder.id)
    occupied = {e.name.casefold() for e in entries if e.id != before['id']}
    pattern = re.compile(re.escape(prefix) + r'(\d{3,})' + re.escape(ext) + r'$', re.I)
    already = str(PurePosixPath(before['path']).parent).casefold() == target.casefold() and pattern.fullmatch(before['name'])
    # Preserve a correct name in the same folder. Adding/removing a role never
    # rewrites unrelated images just to close a numerical gap.
    if already:
        destination = before['path']
    else:
        number = 1
        used_numbers = {int(m.group(1)) for e in entries if e.id != before['id']
                        if (m := re.match(re.escape(prefix) + r'(\d{3,})\.[^.]+$', e.name, re.I))}
        while number in used_numbers or (prefix + f'{number:03d}' + ext).casefold() in occupied:
            number += 1
        destination = target + '/' + prefix + f'{number:03d}' + ext
    intent = {'before': before, 'destination': destination, 'destination_folder_id': folder.id, 'at': stamp()}
    if destination != before['path']:
        # Recheck native metadata immediately before mutation (no overwrite).
        current = inspect_file(client, request['binding'], ROOT_PATH)
        if any(current[k] != before[k] for k in ('id', 'revision', 'path', 'content_hash', 'bytes', 'sharing_fingerprint')):
            raise ValueError('The original changed during planning; no move was submitted.')
        save(journal / 'move-intent.json', intent)
        try:
            client.files_move_v2(before['id'], destination, autorename=False, allow_ownership_transfer=False)
        except Exception as error:
            current = inspect_file(client, request['binding'], ROOT_PATH)
            if current['path'].casefold() != destination.casefold():
                if explicitly_rejected(error) and all(current[k] == before[k] for k in
                        ('id', 'revision', 'path', 'content_hash', 'bytes', 'sharing_fingerprint')):
                    result = {'state': 'needs_review', 'native_rejected': True, 'checked_utc': stamp(),
                              'message': 'Dropbox rejected this destination or was busy. The original is unchanged. Use Plan again for a fresh destination check.'}
                    save(journal / 'result.json', result)
                    return result
                return {'state': 'uncertain', 'message': 'Dropbox did not confirm the move. No retry was sent; check the job.'}
    current = inspect_file(client, request['binding'], ROOT_PATH)
    if current['path'].casefold() != destination.casefold() or current['name'] != PurePosixPath(destination).name:
        return {'state': 'uncertain', 'message': 'Destination readback differs. No further changes were attempted.'}
    validate_folder(client.files_get_metadata(folder.id), target)
    result = {'state': 'completed', 'file': {**current, 'folder_id': folder.id},
              'previous_path': before['path'], 'moved': current['path'] != before['path'],
              'checked_utc': stamp(), 'direct_links_verified': verify_links(client, before)}
    save(journal / 'result.json', result)
    return result


def main():
    p = argparse.ArgumentParser(); p.add_argument('--project', type=Path, required=True)
    p.add_argument('--journal', type=Path, required=True); args = p.parse_args()
    try:
        request = json.load(sys.stdin)
        with connection(args.project) as (client, _):
            result = organise(client, request, args.journal)
    except Exception as e:
        result = {'state': 'uncertain' if (args.journal / 'move-intent.json').exists() else 'needs_review',
                  'message': str(e) if isinstance(e, ValueError) else 'Dropbox organisation could not be verified. No automatic move retry was sent.'}
    print(json.dumps(result))


if __name__ == '__main__':
    main()
