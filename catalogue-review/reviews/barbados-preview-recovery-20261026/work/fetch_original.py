#!/usr/bin/env python3
"""Read one pinned Dropbox original using the existing macOS Keychain grant.

Run with the project's existing application/.venv Python (Dropbox SDK/keyring).
Never prints credentials, changes Dropbox files, or accepts arbitrary URLs.
"""
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
import argparse
import json
import os
import re
import sys
import uuid

from media import MediaCache


class OriginalError(Exception):
    pass


def check_metadata(metadata, file_id, content_hash, expected_bytes, root_path):
    if getattr(metadata, 'id', None) != file_id:
        raise OriginalError('Dropbox returned a different file identity; the original was not accepted.')
    if getattr(metadata, 'content_hash', None) != content_hash or getattr(metadata, 'size', None) != expected_bytes:
        raise OriginalError('The Dropbox original has changed since this catalogue snapshot. Refresh its source record before using it.')
    path = getattr(metadata, 'path_display', '') or ''
    if not path.casefold().startswith(root_path.casefold().rstrip('/') + '/'):
        raise OriginalError('This file is outside the verified Wall Sculptures root.')
    if not 0 < expected_bytes < 150_000_000:
        raise OriginalError('This original exceeds the local viewer size limit.')


def fetch(project, root, file_id, content_hash, expected_bytes):
    if not file_id.startswith('id:') or not re.fullmatch('[a-f0-9]{64}', content_hash):
        raise OriginalError('A known Dropbox file ID and content hash are required.')
    sys.path.insert(0, str(Path(project) / 'image-processing'))
    import authorize
    from dropbox import Dropbox
    from dropbox.common import PathRoot
    # Reading the existing grant never starts a new authorization flow.
    try:
        raw = authorize.keychain_backend().get_password(authorize.SERVICE, authorize.CREDENTIAL_ACCOUNT)
        grant = json.loads(raw) if raw else {}
    except Exception:
        raise OriginalError('The existing Dropbox authorization could not be read from macOS Keychain.') from None
    if grant.get('app_key') != authorize.APP_KEY or not grant.get('refresh_token'):
        raise OriginalError('The image-processing Dropbox app is not authorized on this Mac.')
    directory = Path(root) / 'originals'
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    target = directory / (content_hash + '.image')
    temporary = directory / (content_hash + '.' + uuid.uuid4().hex + '.tmp')
    try:
        with Dropbox(app_key=authorize.APP_KEY, oauth2_refresh_token=grant['refresh_token'], timeout=25,
                     max_retries_on_error=0, max_retries_on_rate_limit=0) as client:
            account = client.users_get_current_account()
            rooted = client.with_path_root(PathRoot.namespace_id(authorize.NAMESPACE_ID))
            folder = rooted.files_get_metadata(authorize.ROOT_ID)
            authorize.verify_identity(account, folder, grant.get('account_id'))
            metadata = rooted.files_get_metadata(file_id, include_media_info=True)
            check_metadata(metadata, file_id, content_hash, expected_bytes, authorize.ROOT_PATH)
            # Recheck the download response identity/hash/size below; a concurrent
            # revision change cannot bypass the pinned original-byte guard.
            metadata, response = rooted.files_download(file_id)
            with closing(response):
                check_metadata(metadata, file_id, content_hash, expected_bytes, authorize.ROOT_PATH)
                length = 0
                with temporary.open('xb') as output:
                    os.chmod(temporary, 0o600)
                    for block in response.iter_content(chunk_size=1024 * 1024):
                        length += len(block)
                        if length > expected_bytes:
                            raise OriginalError('Downloaded bytes exceeded the pinned original size.')
                        output.write(block)
        info = MediaCache(root).inspect(temporary, hashes=True)
        if info['bytes'] != expected_bytes or info['dropbox_content_hash'] != content_hash:
            raise OriginalError('The downloaded image failed original-byte verification.')
        temporary.replace(target)
        result = {k: info[k] for k in ('bytes', 'dimensions', 'sha256', 'dropbox_content_hash')}
        result.update(file_id=file_id, path=str(target), original_path=metadata.path_display,
                      checked_utc=datetime.now(timezone.utc).isoformat(), dropbox_mutations=0)
        (directory / (content_hash + '.json')).write_text(json.dumps(result, indent=2))
        return result
    finally:
        temporary.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--project', required=True, type=Path)
    parser.add_argument('--data-dir', required=True, type=Path)
    parser.add_argument('--file-id', required=True)
    parser.add_argument('--content-hash', required=True)
    parser.add_argument('--bytes', required=True, type=int)
    args = parser.parse_args()
    try:
        result = fetch(args.project, args.data_dir, args.file_id, args.content_hash, args.bytes)
        print(json.dumps(result))
    except OriginalError as error:
        print(json.dumps({'error': str(error)}))
        return 1
    except Exception:
        # SDK/keyring exceptions may contain account or request details. Do not log them.
        print(json.dumps({'error': 'Original lookup failed. Check the existing Dropbox connection and try again; saved reviews are unchanged.'}))
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
