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
import math
import re
import sys

from fetch_original import OriginalError

CATALOGUE_ROOT = '/BOLDSTONE MASTER'
IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.tif', '.tiff', '.heic', '.heif', '.avif'}


def failure_details(error):
    """Safe diagnostics only: never persist exception strings or response bodies."""
    name = type(error).__name__
    details = {'error_code': name}
    request_id = getattr(error, 'request_id', None)
    if isinstance(request_id, str) and re.fullmatch(r'[A-Za-z0-9_-]{1,128}', request_id):
        details['request_id'] = request_id
    code = getattr(error, 'status_code', None)
    if type(code) is int and 100 <= code <= 599:
        details['http_status'] = code
    try:
        delay = float(getattr(error, 'backoff', None) or 0)
    except (TypeError, ValueError, OverflowError):
        delay = 0
    details['retry_after'] = max(0, delay) if math.isfinite(delay) else 0
    return details


def read_failure(error):
    """A failed read does not imply that a delete request was submitted."""
    details = failure_details(error)
    name = details['error_code']
    retryable = isinstance(error, (TimeoutError, ConnectionError)) or name in (
        'ReadTimeout', 'ConnectTimeout', 'ConnectionError', 'Timeout',
        'InternalServerError', 'RateLimitError', 'ChunkedEncodingError')
    return {'error': ('Dropbox is temporarily unavailable. This file can be checked again.' if retryable else
                      'Dropbox could not complete this read-only check (' + name + ').'),
            'state': 'check_failed', 'delete_attempted': False, 'retryable': retryable,
            **details}


def stamp():
    return datetime.now(timezone.utc).isoformat()


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def missing(error):
    value = getattr(error, 'error', None)
    return bool(value and getattr(value, 'is_path', lambda: False)() and
                getattr(value.get_path(), 'is_not_found', lambda: False)())


def inspect_file(client, binding, root_path, allow_missing=False):
    if not re.fullmatch(r'id:[A-Za-z0-9_-]+', binding.get('id', '')):
        raise OriginalError('A known Dropbox file ID is required.')
    try:
        metadata = client.files_get_metadata(binding['id'], include_media_info=True,
                                             include_has_explicit_shared_members=True)
    except Exception as error:
        if not allow_missing or not missing(error):
            raise
        return {'id': binding['id'], 'name': binding.get('name') or binding['id'],
                'path': binding.get('path') or 'Last recorded location unavailable',
                'revision': None, 'content_hash': binding.get('content_hash'), 'bytes': binding.get('bytes'),
                'type': 'missing', 'availability': 'missing', 'verified_absent': True,
                'modified': None, 'sharing': {'links': [], 'explicit_members': False, 'parent_shared_folder_id': None},
                'sharing_fingerprint': None, 'checked_utc': stamp()}
    if not getattr(metadata, 'rev', None):
        raise OriginalError('Only an individual image file can be deleted; folders are not allowed.')
    if metadata.id != binding['id']:
        raise OriginalError('Dropbox returned a different file identity.')
    path = getattr(metadata, 'path_display', '') or ''
    if not path.casefold().startswith(root_path.casefold().rstrip('/') + '/'):
        raise OriginalError('This file is outside the supported BOLDSTONE MASTER catalogue. Nothing was deleted.')
    if Path(metadata.name).suffix.lower() not in IMAGE_EXTENSIONS:
        raise OriginalError('Only a catalogue image file can be deleted here.')
    if not re.fullmatch('[a-f0-9]{64}', getattr(metadata, 'content_hash', '') or '') or metadata.size < 0:
        raise OriginalError('Dropbox did not return complete file metadata.')
    if ((binding.get('content_hash') and metadata.content_hash != binding['content_hash']) or
            (binding.get('bytes') is not None and metadata.size != binding['bytes'])):
        raise OriginalError('This original changed since the catalogue snapshot. Refresh its source record before deleting.')
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
            'type': 'file', 'availability': 'present', 'modified': modified.isoformat() if modified else None,
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
                'presence_verified': False, 'check_error': failure_details(exc),
                'message': 'Dropbox could not be checked. Use Check result again; no deletion was repeated.', 'checked_utc': stamp()}
    if getattr(metadata, 'id', None) != file_id or not getattr(metadata, 'rev', None):
        return {'state': 'uncertain', 'verified_absent': False, 'presence_verified': False,
                'message': 'Dropbox returned an unexpected file identity. No deletion was repeated.', 'checked_utc': stamp()}
    return {'state': 'present', 'verified_absent': False,
            'presence_verified': True,
            'current_revision': getattr(metadata, 'rev', None), 'checked_utc': stamp()}


def validate_review(client, reviewed, binding, root_path, keeper=None, rename_runtime=None):
    current = inspect_file(client, binding, root_path, allow_missing=True)
    if current.get('availability') == 'missing':
        return {'file': current, 'rename_reconciliation': None}
    if reviewed.get('availability') == 'missing':
        raise OriginalError('This file is present again. Review the current file before deleting it.')
    reconciliation = None
    try:
        same_file(current, reviewed)
    except OriginalError:
        if not rename_runtime:
            raise
        from rename_reconciliation import verified_rename
        try:
            reconciliation = verified_rename(rename_runtime, reviewed, current)
        except (OSError, ValueError, KeyError, TypeError):
            raise OriginalError('This file changed beyond a verified filename-only rename. Review it again before deleting.') from None
    if keeper:
        # A duplicate's keeper must still exist at the reviewed version.
        same_file(inspect_file(client, {'id': keeper['id'], 'content_hash': keeper['content_hash'],
                                        'bytes': keeper['bytes']}, root_path), keeper)
        if keeper['id'] == reviewed['id']:
            raise OriginalError('The file to keep cannot be the file to delete.')
    return {'file': current, 'rename_reconciliation': reconciliation}


def execute(client, reviewed, binding, root_path, keeper=None, rename_runtime=None):
    try:
        validation = validate_review(client, reviewed, binding, root_path, keeper, rename_runtime)
    except OriginalError:
        raise
    except Exception as error:
        # These calls are reads. A failure here cannot be a submitted delete.
        return read_failure(error)
    current = validation['file']
    if current.get('availability') == 'missing':
        return {'state': 'already_absent', 'verified_absent': True, 'delete_attempted': False,
                'checked_utc': stamp(), 'message': 'Already absent from Dropbox; the leftover app entry was removed. No deletion request was sent.'}
    audit = {'rename_reconciliation': validation['rename_reconciliation']} if validation['rename_reconciliation'] else {}
    try:
        result = client.files_delete_v2(current['id'], parent_rev=current['revision'])
    except Exception as error:
        # A transport failure may happen after Dropbox committed. Never repeat
        # a destructive call automatically or report that the file is intact.
        status = verify_absent(client, reviewed['id'])
        if status['state'] != 'deleted':
            status.update(state='uncertain', message='The deletion response was not confirmed. Check status before any retry.')
        status.update(delete_attempted=True, delete_error=failure_details(error))
        return {**status, **audit}
    metadata = result.metadata
    if getattr(metadata, 'id', None) != current['id'] or getattr(metadata, 'rev', None) != current['revision']:
        return {'state': 'uncertain', 'verified_absent': False, 'delete_attempted': True,
                'message': 'Dropbox returned an unexpected deletion receipt.', **audit}
    status = verify_absent(client, reviewed['id'])
    status.update(delete_response_confirmed=True, delete_attempted=True)
    if status['state'] == 'present':
        status.update(state='uncertain', message='Dropbox acknowledged deletion but the file is present on readback. Check status.')
    return {**status, **audit}


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
        # The server admits only stable image IDs already in the catalogue.
        # Workshop references are under BOLDSTONE MASTER but outside Wall
        # Sculptures. Account/namespace and the existing anchor stay verified.
        yield rooted, CATALOGUE_ROOT


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--project', type=Path, required=True)
    args = parser.parse_args()
    executing = False
    try:
        request = json.load(sys.stdin)
        with connection(args.project) as (client, root_path):
            if request['action'] == 'inspect':
                result = {'file': inspect_file(client, request['binding'], root_path, allow_missing=True)}
                if request.get('keeper_binding'):
                    result['keeper'] = inspect_file(client, request['keeper_binding'], root_path)
            elif request['action'] == 'execute':
                executing = True
                result = execute(client, request['reviewed'], request['binding'], root_path,
                                 request.get('keeper'), request.get('rename_runtime'))
            elif request['action'] == 'validate':
                result = validate_review(client, request['reviewed'], request['binding'], root_path,
                                         request.get('keeper'), request.get('rename_runtime'))
            elif request['action'] == 'check':
                result = verify_absent(client, request['file_id'])
            else:
                raise OriginalError('Unknown deletion action.')
        print(json.dumps(result))
        return 0
    except OriginalError as exc:
        print(json.dumps({'error': str(exc), 'state': 'rejected', 'delete_attempted': False}))
        return 1
    except Exception as error:
        # Connection / identity checks happen before execute can submit a
        # mutation. execute itself catches every post-submission exception.
        print(json.dumps({'error': 'The deletion result is unconfirmed. Check its status before any retry.',
                          'state': 'uncertain'} if executing else read_failure(error)))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
