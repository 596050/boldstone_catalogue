#!/usr/bin/env python3
"""One reviewed Dropbox file deletion, pinned to identity, revision and sharing.

Called by the local application using its existing Keychain grant. Input is JSON
on stdin. There is no permanent-delete, directory-delete or bulk-delete route.
"""
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import argparse
import hashlib
import json
import sys

from fetch_original import OriginalError, check_metadata


def stamp():
    return datetime.now(timezone.utc).isoformat()


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def missing(error):
    value = getattr(error, 'error', None)
    return bool(value and getattr(value, 'is_path', lambda: False)() and
                getattr(value.get_path(), 'is_not_found', lambda: False)())


def inspect_file(client, binding, root_path):
    metadata = client.files_get_metadata(binding['id'], include_media_info=True,
                                         include_has_explicit_shared_members=True)
    if not getattr(metadata, 'rev', None):
        raise OriginalError('Only an individual image file can be deleted; folders are not allowed.')
    check_metadata(metadata, binding['id'], binding['content_hash'], binding['bytes'], root_path)
    links, cursor = [], None
    while True:
        result = (client.sharing_list_shared_links(cursor=cursor) if cursor else
                  client.sharing_list_shared_links(path=metadata.path_lower, direct_only=False))
        for link in result.links:
            permissions = getattr(link, 'link_permissions', None)
            links.append({'url': link.url, 'path': getattr(link, 'path_lower', None),
                          'name': getattr(link, 'name', ''),
                          'visibility': str(getattr(permissions, 'resolved_visibility', 'unknown')),
                          'access_level': str(getattr(permissions, 'link_access_level', 'unknown')),
                          'direct': getattr(link, 'path_lower', None) == metadata.path_lower})
        if not result.has_more:
            break
        if not result.cursor or result.cursor == cursor or len(links) > 1000:
            raise OriginalError('Sharing information was incomplete. Nothing was deleted.')
        cursor = result.cursor
    links.sort(key=lambda x: (x['url'], x['path'] or ''))
    shared = getattr(metadata, 'sharing_info', None)
    sharing = {'links': links, 'explicit_members': bool(getattr(metadata, 'has_explicit_shared_members', False)),
               'parent_shared_folder_id': getattr(shared, 'parent_shared_folder_id', None)}
    modified = getattr(metadata, 'server_modified', None)
    return {'id': metadata.id, 'name': metadata.name, 'path': metadata.path_display,
            'revision': metadata.rev, 'content_hash': metadata.content_hash, 'bytes': metadata.size,
            'type': 'file', 'modified': modified.isoformat() if modified else None,
            'sharing': sharing, 'sharing_fingerprint': fingerprint(sharing), 'checked_utc': stamp()}


def same_file(current, reviewed):
    keys = ('id', 'path', 'revision', 'content_hash', 'bytes', 'sharing_fingerprint')
    if any(current.get(k) != reviewed.get(k) for k in keys):
        raise OriginalError('This file, its location or sharing changed after review. Review it again before deleting.')


def verify_absent(client, file_id):
    try:
        metadata = client.files_get_metadata(file_id)
    except Exception as exc:
        if missing(exc):
            return {'state': 'deleted', 'verified_absent': True, 'checked_utc': stamp()}
        return {'state': 'uncertain', 'verified_absent': False,
                'message': 'Dropbox could not be checked. Do not repeat the deletion; check its status.', 'checked_utc': stamp()}
    return {'state': 'present', 'verified_absent': False,
            'current_revision': getattr(metadata, 'rev', None), 'checked_utc': stamp()}


def execute(client, reviewed, binding, root_path, keeper=None):
    current = inspect_file(client, binding, root_path)
    same_file(current, reviewed)
    if keeper:
        # A duplicate's keeper must still exist at the reviewed version.
        same_file(inspect_file(client, {'id': keeper['id'], 'content_hash': keeper['content_hash'],
                                        'bytes': keeper['bytes']}, root_path), keeper)
        if keeper['id'] == reviewed['id']:
            raise OriginalError('The file to keep cannot be the file to delete.')
    try:
        result = client.files_delete_v2(reviewed['id'], parent_rev=reviewed['revision'])
    except Exception:
        # A transport failure may happen after Dropbox committed. Never repeat
        # a destructive call automatically or report that the file is intact.
        status = verify_absent(client, reviewed['id'])
        if status['state'] != 'deleted':
            status.update(state='uncertain', message='The deletion response was not confirmed. Check status before any retry.')
        return status
    metadata = result.metadata
    if getattr(metadata, 'id', None) != reviewed['id'] or getattr(metadata, 'rev', None) != reviewed['revision']:
        return {'state': 'uncertain', 'verified_absent': False, 'message': 'Dropbox returned an unexpected deletion receipt.'}
    status = verify_absent(client, reviewed['id'])
    status['delete_response_confirmed'] = True
    if status['state'] == 'present':
        status.update(state='uncertain', message='Dropbox acknowledged deletion but the file is present on readback. Check status.')
    return status


@contextmanager
def connection(project):
    sys.path.insert(0, str(Path(project) / 'image-processing'))
    import authorize
    from dropbox import Dropbox
    from dropbox.common import PathRoot
    try:
        raw = authorize.keychain_backend().get_password(authorize.SERVICE, authorize.CREDENTIAL_ACCOUNT)
        grant = json.loads(raw) if raw else {}
    except Exception:
        raise OriginalError('The existing Dropbox authorization could not be read from macOS Keychain.') from None
    if grant.get('app_key') != authorize.APP_KEY or not grant.get('refresh_token'):
        raise OriginalError('The image-processing Dropbox app is not authorized on this Mac.')
    required = {'account_info.read', 'files.metadata.read', 'files.content.write', 'sharing.read'}
    if not required.issubset(set(grant.get('scopes', []))):
        raise OriginalError('The saved Dropbox grant does not include the required file-write and sharing scopes.')
    with Dropbox(app_key=authorize.APP_KEY, oauth2_refresh_token=grant['refresh_token'], timeout=25,
                 max_retries_on_error=0, max_retries_on_rate_limit=0) as client:
        account = client.users_get_current_account()
        rooted = client.with_path_root(PathRoot.namespace_id(authorize.NAMESPACE_ID))
        folder = rooted.files_get_metadata(authorize.ROOT_ID)
        authorize.verify_identity(account, folder, grant.get('account_id'))
        yield rooted, authorize.ROOT_PATH


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--project', type=Path, required=True)
    args = parser.parse_args()
    try:
        request = json.load(sys.stdin)
        with connection(args.project) as (client, root_path):
            if request['action'] == 'inspect':
                result = {'file': inspect_file(client, request['binding'], root_path)}
                if request.get('keeper_binding'):
                    result['keeper'] = inspect_file(client, request['keeper_binding'], root_path)
            elif request['action'] == 'execute':
                result = execute(client, request['reviewed'], request['binding'], root_path, request.get('keeper'))
            elif request['action'] == 'check':
                result = verify_absent(client, request['file_id'])
            else:
                raise OriginalError('Unknown deletion action.')
        print(json.dumps(result))
        return 0
    except OriginalError as exc:
        print(json.dumps({'error': str(exc), 'state': 'rejected', 'delete_attempted': False}))
        return 1
    except Exception:
        print(json.dumps({'error': 'Dropbox could not complete this check. No deletion was confirmed; check the operation status before retrying.'}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
