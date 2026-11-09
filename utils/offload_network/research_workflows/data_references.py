"""Resolve declared immutable data from operator-approved storage before admission.

Jobs name a source, relative object key, exact archive size and SHA-256. Only
the worker operator supplies endpoints, filesystem roots and credentials.
The fetched format is the existing sealed offload object, not executable code.
"""

from contextlib import contextmanager
from datetime import datetime, timezone
from http.client import IncompleteRead
import os
from pathlib import Path
import ssl
import stat
import threading
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import HTTPRedirectHandler, HTTPSHandler, ProxyHandler, Request, build_opener

from offload_service.core import CapacityError

from .common import atomic, canonical, digest, fields, hash_id, load, name, no_links, positive, rel
from .objects import CHUNK, pack


class DataUnavailable(CapacityError):
    """Retriable acquisition failure; no workflow has been admitted."""


def key(value):
    value = rel(value)
    if '%' in value or any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise ValueError('data keys must not contain percent escapes or control characters')
    return value


def validate_reference(value):
    fields(value, {'mode', 'source', 'key', 'object_sha256', 'archive_bytes', 'version_id'},
           {'mode', 'source', 'key', 'object_sha256', 'archive_bytes'})
    if value['mode'] != 'data_ref':
        raise ValueError('expected data_ref input')
    name(value['source'])
    key(value['key'])
    hash_id(value['object_sha256'])
    positive(value['archive_bytes'], 1 << 40)
    if 'version_id' in value and (not isinstance(value['version_id'], str)
            or not 1 <= len(value['version_id']) <= 1024
            or any(ord(c) < 32 for c in value['version_id'])):
        raise ValueError('invalid pinned S3 version_id')
    return value


def _https_url(value):
    if not isinstance(value, str) or any(ord(c) < 33 for c in value):
        raise ValueError('source endpoint must be an HTTPS URL')
    parsed = urlsplit(value)
    if (parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password
            or parsed.query or parsed.fragment or '\\' in value):
        raise ValueError('source endpoint must be HTTPS without credentials, query or fragment')
    parsed.port  # Reject malformed ports before any network request.
    return value


def source_profiles(raw):
    if not isinstance(raw, dict) or len(raw) > 64:
        raise ValueError('data_sources must be an object with at most 64 approved sources')
    result = {}
    for ident, original in raw.items():
        name(ident)
        if not isinstance(original, dict):
            raise ValueError('data source profile must be an object')
        source = dict(original)
        kind = source.get('type')
        allowed = {
            'filesystem': {'root'},
            'https': {'base_url', 'bearer_token_file', 'ca_file'},
            's3': {'bucket', 'prefix', 'profile_name', 'region_name', 'endpoint_url', 'ca_file'},
        }
        if kind not in allowed:
            raise ValueError('data source type must be filesystem, https or s3')
        required = {'filesystem': 'root', 'https': 'base_url', 's3': 'bucket'}[kind]
        fields(source, {'type', 'timeout_s'} | allowed[kind], {'type', required})
        source.setdefault('timeout_s', 60)
        positive(source['timeout_s'], 86400, integer=False)
        for field in ('root', 'bearer_token_file', 'ca_file'):
            if field in source and (not isinstance(source[field], str) or not Path(source[field]).is_absolute()):
                raise ValueError('operator source paths must be absolute')
        for field in ('base_url', 'endpoint_url'):
            if field in source:
                _https_url(source[field])
        for field in ('bucket', 'profile_name', 'region_name'):
            if field in source and (not isinstance(source[field], str) or not source[field]
                    or any(ord(c) < 33 for c in source[field])):
                raise ValueError('invalid operator S3 configuration')
        if kind == 's3':
            # A bucket, not an ARN/access-point URL; jobs cannot select accounts.
            if any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789.-' for c in source['bucket']):
                raise ValueError('S3 source requires a bucket name')
            prefix = source.get('prefix', '')
            if not isinstance(prefix, str):
                raise ValueError('S3 prefix must be a relative string key')
            if prefix:
                key(prefix.rstrip('/'))
            source['prefix'] = prefix.rstrip('/')
        result[ident] = source
    return result


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise ValueError('data source redirects are not allowed')


class DataSources:
    def __init__(self, store, profiles):
        self.store = store
        self.profiles = source_profiles(profiles)
        # One acquisition at a time bounds temporary disk use. This does not
        # hold the worker database or scheduler/status control-plane locks.
        self.lock = threading.Lock()

    @contextmanager
    def _open(self, source, reference, offset):
        kind, size = source['type'], reference['archive_bytes']
        if 'version_id' in reference and kind != 's3':
            raise ValueError('version_id is only valid for an S3 source')
        if kind == 'filesystem':
            root = Path(source['root'])
            path = no_links(root / reference['key'], root)
            if not stat.S_ISREG(path.lstat().st_mode):
                raise ValueError('referenced archive must be a regular file')
            flags = os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0)
            with os.fdopen(os.open(path, flags), 'rb') as stream:
                info = os.fstat(stream.fileno())
                if not stat.S_ISREG(info.st_mode) or info.st_size != size:
                    raise ValueError('referenced archive is not a regular file of the pinned size')
                stream.seek(offset)
                yield stream, offset
            return
        if kind == 'https':
            url = source['base_url'].rstrip('/') + '/' + quote(reference['key'], safe='/')
            headers = {'Accept-Encoding': 'identity'}
            if 'bearer_token_file' in source:
                token_path = Path(source['bearer_token_file'])
                info = token_path.stat()
                if (not stat.S_ISREG(info.st_mode) or info.st_size > 8192
                        or (os.name != 'nt' and info.st_mode & 0o077)):
                    raise ValueError('source credential file must be private and bounded')
                token = token_path.read_text().strip()
                if not token or any(ord(c) < 33 or ord(c) > 126 for c in token):
                    raise ValueError('invalid source bearer credential')
                headers['Authorization'] = 'Bearer ' + token
            if offset:
                headers['Range'] = f'bytes={offset}-'
            context = ssl.create_default_context(cafile=source.get('ca_file'))
            opener = build_opener(ProxyHandler({}), _NoRedirect(), HTTPSHandler(context=context))
            with opener.open(Request(url, headers=headers), timeout=source['timeout_s']) as response:
                start = offset if response.status == 206 else 0
                if response.status not in (200, 206) or (response.status == 206 and
                        response.headers.get('Content-Range') != f'bytes {offset}-{size - 1}/{size}'):
                    raise ValueError('unexpected data response status or range')
                encoding = response.headers.get('Content-Encoding', 'identity')
                length = response.headers.get('Content-Length')
                if encoding != 'identity' or (length is not None and int(length) != size - start):
                    raise ValueError('data response encoding or size differs from the pinned archive')
                # A server ignoring Range may replay the prefix. ObjectStore
                # checks repeated chunks byte-for-byte rather than appending it.
                yield response, start
            return
        try:
            import boto3
            from botocore.config import Config
            from botocore.exceptions import BotoCoreError, ClientError
        except ImportError:
            raise ValueError('S3 data sources require the offload package s3 extra') from None
        request = {'Bucket': source['bucket'], 'Key': '/'.join(filter(None, [source['prefix'], reference['key']]))}
        if offset:
            request['Range'] = f'bytes={offset}-'
        if 'version_id' in reference:
            request['VersionId'] = reference['version_id']
        client = None
        try:
            client = boto3.Session(profile_name=source.get('profile_name')).client(
                's3', region_name=source.get('region_name'), endpoint_url=source.get('endpoint_url'),
                verify=source.get('ca_file', True),
                config=Config(connect_timeout=source['timeout_s'], read_timeout=source['timeout_s'],
                              retries={'max_attempts': 0}),
            )
            response = client.get_object(**request)
            with response['Body'] as stream:
                if response.get('ContentLength') != size - offset or (offset and
                        response.get('ContentRange') != f'bytes {offset}-{size - 1}/{size}'):
                    raise ValueError('S3 object size or range differs from the pinned archive')
                if 'version_id' in reference and response.get('VersionId') != reference['version_id']:
                    raise ValueError('S3 object version differs')
                yield stream, offset
        except ClientError as error:
            status = error.response.get('ResponseMetadata', {}).get('HTTPStatusCode')
            if status in (401, 403):
                raise ValueError('S3 data source authentication failed') from None
            raise DataUnavailable('S3 data source unavailable; retry acquisition') from None
        except BotoCoreError:
            raise DataUnavailable('S3 data acquisition interrupted; retry acquisition') from None
        finally:
            if client is not None:
                client.close()

    def resolve(self, reference):
        validate_reference(reference)
        ident, source_id, size = reference['object_sha256'], reference['source'], reference['archive_bytes']
        if source_id not in self.profiles:
            raise ValueError('unconfigured data source: ' + source_id)
        source = self.profiles[source_id]
        if 'version_id' in reference and source['type'] != 's3':
            raise ValueError('version_id is only valid for an S3 source')
        if size > self.store.max_bytes:
            raise ValueError('referenced archive exceeds worker object limit')
        if not self.lock.acquire(timeout=source['timeout_s']):
            raise DataUnavailable('data acquisition busy; retry admission')
        try:
            state = self.store.begin(ident, size)
            cached = state['state'] == 'committed'
            contacted = False
            if not cached:
                try:
                    # A retained complete prefix is rechecked, never replaced
                    # silently if its expected hash is wrong.
                    if state['offset'] < size:
                        contacted = True
                        with self._open(source, reference, state['offset']) as (stream, offset):
                            while True:
                                limit = min(CHUNK, size - offset + 1)
                                if offset < state['offset']:
                                    limit = min(limit, state['offset'] - offset)
                                block = stream.read(limit)
                                if not block:
                                    break
                                if offset + len(block) > size:
                                    raise ValueError('data source exceeded pinned archive size')
                                self.store.append(ident, offset, block)
                                offset += len(block)
                            if offset != size:
                                raise DataUnavailable('referenced archive is truncated; retry acquisition')
                    self.store.commit(ident)
                except HTTPError as error:
                    if error.code in (401, 403):
                        raise ValueError('HTTPS data source authentication failed') from None
                    raise DataUnavailable(f'HTTPS data source returned {error.code}; retry acquisition') from None
                except URLError as error:
                    if isinstance(error.reason, ssl.SSLError):
                        raise ValueError('HTTPS data source TLS verification failed') from None
                    raise DataUnavailable('HTTPS data source unavailable; retry acquisition') from None
                except PermissionError:
                    raise ValueError('data source access denied') from None
                except (OSError, IncompleteRead):
                    raise DataUnavailable('data source unavailable; retry acquisition') from None
            self.store.get(ident)  # Full archive AND file-manifest verification, also on cache hits.
            receipt = {
                'schema': 'marketmaker.data_reference_resolution.v1',
                'reference': reference, 'provider': source['type'],
                'cache_hit': cached, 'location_accessed': contacted,
                'verification': 'ARCHIVE_AND_FILE_MANIFESTS_VERIFIED',
                'at_utc': datetime.now(timezone.utc).isoformat(),
            }
            # Contains declared names/keys, never endpoint credentials or host paths.
            retained = self.store.root / 'data-reference-receipts' / (digest(reference) + '.json')
            if retained.exists():
                if load(retained).get('reference') != reference:
                    raise ValueError('retained data reference receipt differs')
            else:
                self.store.capacity(2 * len(canonical(receipt).encode()))
                atomic(retained, receipt)
            return receipt
        finally:
            self.lock.release()


def prepare_reference(directory, destination, *, source, object_key, max_bytes=1 << 30):
    """Create a portable raw-file snapshot and job reference; never publish it."""
    name(source)
    key(object_key)
    directory, destination = Path(directory).resolve(), Path(destination).resolve()
    if destination == directory or destination.is_relative_to(directory):
        raise ValueError('reference output must not be inside its source directory')
    destination.mkdir(parents=True, exist_ok=False)
    packed = pack(directory, destination / 'object.tar.gz', max_bytes=max_bytes)
    reference = validate_reference({
        'mode': 'data_ref', 'source': source, 'key': object_key,
        'object_sha256': packed['object_sha256'], 'archive_bytes': packed['archive_bytes'],
    })
    atomic(destination / 'DATA_REF.json', reference)
    atomic(destination / 'OBJECT.json', packed['content_manifest'])
    return reference
