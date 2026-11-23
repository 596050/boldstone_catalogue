"""Authenticated loopback transport for the optional Chrome photo helper.

Only Python can enqueue approved local files. HTTP callers can claim an existing
request, read that request's exact hashed image, and return a bounded receipt.
The helper cannot enqueue files, navigate tabs, or request a publish action.
"""
import base64
import contextlib
import fcntl
import hmac
import http.client
import json
import os
import re
import secrets
import shutil
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from common import ROOT, Hold, atomic_json, canonical, digest, read_json, utc

VERSION = '1.0.0'
HOSTS = {'business.facebook.com', 'www.linkedin.com'}
ID = re.compile(r'^[a-f0-9]{32}$')


def config_for(directory):
    path = Path(directory) / 'upload-helper.json'
    if not path.is_file():
        raise Hold('UPLOAD_HELPER_NOT_CONFIGURED', 'Build the local Chrome helper, then load the reviewed bundle before using background photo upload')
    config = read_json(path)
    if config.get('version') != VERSION or not re.fullmatch(r'[a-p]{32}', config.get('extension_id', '')) or not re.fullmatch(r'[a-f0-9]{64}', config.get('token', '')):
        raise Hold('UPLOAD_HELPER_CONFIG_INVALID')
    if not 1024 <= config.get('port', 0) <= 65535:
        raise Hold('UPLOAD_HELPER_CONFIG_INVALID')
    return config


def build_helper(directory, port=8768):
    directory = Path(directory).resolve()
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    config_path = directory / 'upload-helper.json'
    if config_path.exists():
        config = config_for(directory)
        if config['port'] != port:
            raise Hold('UPLOAD_HELPER_PORT_CHANGED', 'Retain the existing helper connection or explicitly pair a new installation')
    else:
        # Only the public key is retained; it stabilises the extension ID.
        generated = subprocess.run(['/usr/bin/openssl', 'genrsa', '2048'], capture_output=True, check=True, timeout=20)
        public = subprocess.run(['/usr/bin/openssl', 'rsa', '-pubout', '-outform', 'DER'], input=generated.stdout, capture_output=True, check=True, timeout=10).stdout
        extension_id = digest(public)[:32].translate(str.maketrans('0123456789abcdef', 'abcdefghijklmnop'))
        config = {'version': VERSION, 'port': port, 'extension_id': extension_id,
                  'public_key': base64.b64encode(public).decode('ascii'), 'token': secrets.token_hex(32)}
        atomic_json(config_path, config)
    target = directory / 'chrome-uploader-extension'
    target.mkdir(exist_ok=True, mode=0o700)
    source = ROOT / 'browser-helper'
    for name in ['page-upload.js', 'service-worker.js', 'popup.html', 'popup.js']:
        shutil.copyfile(source / name, target / name)
    manifest = read_json(source / 'manifest.json')
    manifest['key'] = config['public_key']
    atomic_json(target / 'manifest.json', manifest)
    connection = {'baseURL': 'http://127.0.0.1:' + str(port), 'token': config['token']}
    private = target / 'bridge-config.js'
    fd = os.open(str(private), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as stream:
        stream.write('export const BRIDGE = ' + canonical(connection) + ';\n')
        stream.flush()
        os.fsync(stream.fileno())
    review = {'built_utc': utc(), 'extension_id': config['extension_id'], 'bundle': str(target),
              'version': VERSION, 'permissions': manifest['permissions'], 'host_permissions': manifest['host_permissions'],
              'installed': False, 'installation_requires_confirmation': True,
              'source_sha256': {name: digest((target / name).read_bytes()) for name in ['page-upload.js', 'service-worker.js', 'popup.html', 'popup.js', 'manifest.json', 'bridge-config.js']}}
    atomic_json(directory / 'upload-helper-review.json', review)
    return review


class UploadQueue:
    def __init__(self, directory, now=time.time):
        self.directory = Path(directory).resolve()
        self.requests = self.directory / 'upload-requests'
        self.requests.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.now = now
        self.thread_lock = threading.RLock()

    @contextlib.contextmanager
    def locked(self):
        with self.thread_lock:
            with (self.directory / 'upload-queue.lock').open('a') as lock:
                fcntl.flock(lock, fcntl.LOCK_EX)
                yield

    def path(self, request_id):
        if not isinstance(request_id, str) or not ID.fullmatch(request_id):
            raise Hold('UPLOAD_REQUEST_ID_INVALID')
        return self.requests / (request_id + '.json')

    def load(self, request_id):
        try:
            value = read_json(self.path(request_id))
        except (OSError, ValueError):
            raise Hold('UPLOAD_REQUEST_UNAVAILABLE')
        if value.get('request_id') != request_id:
            raise Hold('UPLOAD_REQUEST_INVALID')
        return value

    def submit(self, job, binding, trigger, guards):
        path = Path(job['media_path']).resolve()
        if not path.is_file() or digest(path.read_bytes()) != job['media_sha256']:
            raise Hold('MEDIA_HASH_CHANGED')
        u = urlparse(binding['url'])
        if u.scheme != 'https' or u.hostname not in HOSTS or u.username or u.password or u.port not in (None, 443):
            raise Hold('WRONG_DESTINATION')
        if u.hostname == 'business.facebook.com':
            query = parse_qs(u.query)
            if query.get('business_id') != [job['business_id']] or query.get('asset_id') != [job['asset_id']]:
                raise Hold('WRONG_META_ACCOUNT')
        if not any(g.get('purpose') == 'account' for g in guards):
            raise Hold('UPLOAD_ACCOUNT_GUARD_MISSING')
        request_id = digest([job['id'], job['media_sha256'], binding['window_id'], binding['tab_id'], binding['owner'], binding['url']])[:32]
        public = {'request_id': request_id, 'job_id': job['id'], 'profile_id': job['profile_id'],
                  'window_id': binding['window_id'], 'tab_id': binding['tab_id'], 'owner': binding['owner'],
                  'expected_url': binding['url'], 'trigger': trigger, 'guards': guards,
                  'sha256': job['media_sha256'], 'name': path.name, 'size': path.stat().st_size,
                  'mime_type': job['media_type'], 'timeout_ms': 12000}
        value = {'request_id': request_id, 'status': 'PENDING', 'created_utc': utc(),
                 'expires_at': self.now() + 180, 'media_path': str(path), 'public': public}
        with self.locked():
            if self.path(request_id).exists():
                old = self.load(request_id)
                unstarted = (old['status'] == 'FAILED' and
                             old.get('result', {}).get('phase') == 'NOT_STARTED' and
                             (old.get('result', {}).get('code') in {'UPLOAD_CONTROL_MISSING', 'FILE_INPUT_NOT_CREATED', 'UPLOAD_CONTROL_REQUIRED'} or
                              (old.get('result', {}).get('code') == 'HELPER_ERROR' and
                               old.get('result', {}).get('detail') == 'FOREGROUND_TAB_PAUSED')))
                old_scope = {k: v for k, v in old['public'].items() if k != 'trigger'}
                new_scope = {k: v for k, v in public.items() if k != 'trigger'}
                if (old_scope != new_scope or old['media_path'] != str(path) or
                        (old['public'] != public and not unstarted)):
                    raise Hold('UPLOAD_REQUEST_CHANGED')
                # A request that was never claimed has no possible file events.
                # An explicit later preparation may requeue only that case.
                if not unstarted and (old['status'] not in {'EXPIRED', 'CANCELLED'} or old.get('lease')):
                    return old
                if unstarted:
                    value['previous_attempts'] = old.get('previous_attempts', []) + [
                        {k: old[k] for k in ('status', 'lease', 'result', 'public') if k in old}]
            atomic_json(self.path(request_id), value)
        return value

    def cancel(self, request_id):
        with self.locked():
            value = self.load(request_id)
            if value['status'] == 'PENDING':
                value['status'] = 'CANCELLED'
            elif value['status'] == 'RUNNING':
                value['status'] = 'OUTCOME_UNKNOWN'
            else:
                return
            atomic_json(self.path(request_id), value)

    def next(self):
        with self.locked():
            for path in sorted(self.requests.glob('*.json'), key=lambda p: p.stat().st_mtime):
                value = self.load(path.stem)
                if value['status'] == 'RUNNING' and value['lease_expires_at'] <= self.now():
                    value['status'] = 'OUTCOME_UNKNOWN'
                    atomic_json(path, value)
                if value['status'] == 'PENDING' and value['expires_at'] <= self.now():
                    value['status'] = 'EXPIRED'
                    atomic_json(path, value)
                if value['status'] == 'PENDING':
                    return {'request_id': value['request_id']}
        return None

    def claim(self, request_id):
        with self.locked():
            value = self.load(request_id)
            if value['status'] != 'PENDING' or value['expires_at'] <= self.now():
                raise Hold('UPLOAD_NOT_CLAIMABLE')
            value.update(status='RUNNING', lease=secrets.token_hex(16), lease_expires_at=self.now() + 45)
            atomic_json(self.path(request_id), value)
            return {**value['public'], 'lease': value['lease'], 'expires_at': value['lease_expires_at']}

    def media(self, request_id, lease):
        with self.locked():
            value = self.load(request_id)
            if value['status'] != 'RUNNING' or value['lease_expires_at'] <= self.now() or not hmac.compare_digest(value.get('lease', ''), lease or ''):
                raise Hold('UPLOAD_LEASE_INVALID')
            data = Path(value['media_path']).read_bytes()
            if len(data) != value['public']['size'] or digest(data) != value['public']['sha256']:
                raise Hold('MEDIA_HASH_CHANGED')
            return data, value['public']['mime_type']

    def complete(self, request_id, lease, result):
        with self.locked():
            value = self.load(request_id)
            if not isinstance(result, dict) or not isinstance(lease, str) or not hmac.compare_digest(value.get('lease', ''), lease):
                raise Hold('UPLOAD_LEASE_INVALID')
            if value['status'] in {'DONE', 'FAILED'}:
                if value.get('result') == result:
                    return value
                raise Hold('UPLOAD_RECEIPT_CHANGED')
            if value['status'] not in {'RUNNING', 'OUTCOME_UNKNOWN'}:
                raise Hold('UPLOAD_NOT_RUNNING')
            if result.get('request_id') != request_id or result.get('sha256') != value['public']['sha256']:
                raise Hold('UPLOAD_RECEIPT_INVALID')
            if result.get('ok') is True:
                if result.get('phase') != 'FILE_EVENTS_DISPATCHED' or result.get('method') != 'chrome-main-world-file-input' or result.get('size') != value['public']['size'] or result.get('name') != value['public']['name']:
                    raise Hold('UPLOAD_RECEIPT_INVALID')
                state = 'DONE'
            else:
                state = 'FAILED' if result.get('phase') == 'NOT_STARTED' else 'OUTCOME_UNKNOWN'
            value.update(status=state, result=result, completed_utc=utc())
            atomic_json(self.path(request_id), value)
            return value


class UploadServer:
    def __init__(self, directory, config=None, port=None):
        self.directory = Path(directory).resolve()
        self.config = config or config_for(directory)
        self.queue = UploadQueue(directory)
        self.origin = 'chrome-extension://' + self.config['extension_id']
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def authenticate(self):
                if self.headers.get('Host') != '127.0.0.1:' + str(outer.port):
                    raise Hold('WRONG_HOST')
                origin = self.headers.get('Origin')
                if origin is not None and origin != outer.origin:
                    raise Hold('WRONG_ORIGIN')
                wanted = 'Bearer ' + outer.config['token']
                if not hmac.compare_digest(self.headers.get('Authorization', ''), wanted):
                    raise Hold('UNAUTHORIZED')

            def respond(self, status, payload, mime='application/json'):
                data = payload if isinstance(payload, bytes) else canonical(payload).encode('utf-8')
                self.send_response(status)
                self.send_header('Content-Type', mime)
                self.send_header('Content-Length', str(len(data)))
                self.send_header('Cache-Control', 'no-store')
                self.send_header('X-Content-Type-Options', 'nosniff')
                if self.headers.get('Origin') == outer.origin:
                    self.send_header('Access-Control-Allow-Origin', outer.origin)
                    self.send_header('Vary', 'Origin')
                self.end_headers()
                self.wfile.write(data)

            def do_OPTIONS(self):
                if self.headers.get('Host') != '127.0.0.1:' + str(outer.port) or self.headers.get('Origin') != outer.origin:
                    self.respond(403, {'code': 'WRONG_ORIGIN'})
                    return
                self.send_response(204)
                self.send_header('Access-Control-Allow-Origin', outer.origin)
                self.send_header('Access-Control-Allow-Methods', 'GET, POST')
                self.send_header('Access-Control-Allow-Headers', 'Authorization, Content-Type, X-Upload-Lease')
                self.end_headers()

            def do_GET(self):
                try:
                    self.authenticate()
                    if self.path == '/health':
                        health = {'version': VERSION, 'extension_id': outer.config['extension_id'], 'bind': '127.0.0.1', 'publish_actions': False}
                        hello = outer.directory / 'upload-helper-health.json'
                        if hello.exists():
                            health['helper'] = read_json(hello)
                        self.respond(200, health)
                    elif self.path == '/next':
                        self.respond(200, {'next': outer.queue.next()})
                    elif self.path.startswith('/media/'):
                        data, mime = outer.queue.media(self.path[7:], self.headers.get('X-Upload-Lease', ''))
                        self.respond(200, data, mime)
                    else:
                        self.respond(404, {'code': 'NOT_FOUND'})
                except Hold as error:
                    self.respond(403 if error.code in {'UNAUTHORIZED', 'WRONG_HOST', 'WRONG_ORIGIN'} else 409, {'code': error.code})
                except (OSError, ValueError):
                    self.respond(409, {'code': 'UPLOAD_STATE_INVALID'})

            def do_POST(self):
                try:
                    self.authenticate()
                    size = int(self.headers.get('Content-Length', '0'))
                    if not 0 < size <= 16384 or self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
                        raise Hold('REQUEST_BODY_INVALID')
                    body = json.loads(self.rfile.read(size))
                    if not isinstance(body, dict):
                        raise Hold('REQUEST_BODY_INVALID')
                    if self.path == '/hello':
                        if body.get('extension_id') != outer.config['extension_id'] or body.get('version') != VERSION:
                            raise Hold('HELPER_IDENTITY_INVALID')
                        atomic_json(outer.directory / 'upload-helper-health.json', {'seen_utc': utc(), 'version': VERSION, 'extension_id': body['extension_id']})
                        self.respond(200, {'ok': True})
                    elif self.path.startswith('/claim/'):
                        if body.get('version') != VERSION:
                            raise Hold('HELPER_VERSION_INVALID')
                        self.respond(200, outer.queue.claim(self.path[7:]))
                    elif self.path.startswith('/result/'):
                        result = outer.queue.complete(self.path[8:], self.headers.get('X-Upload-Lease', ''), body)
                        self.respond(200, {'ok': True, 'status': result['status']})
                    else:
                        self.respond(404, {'code': 'NOT_FOUND'})
                except Hold as error:
                    self.respond(403 if error.code in {'UNAUTHORIZED', 'WRONG_HOST', 'WRONG_ORIGIN'} else 409, {'code': error.code})
                except (OSError, ValueError, TypeError):
                    self.respond(400, {'code': 'REQUEST_BODY_INVALID'})

        self.http = ThreadingHTTPServer(('127.0.0.1', self.config['port'] if port is None else port), Handler)
        self.http.daemon_threads = True
        self.port = self.http.server_address[1]
        self.thread = None

    def start(self):
        self.thread = threading.Thread(target=self.http.serve_forever, kwargs={'poll_interval': 0.1}, daemon=True)
        self.thread.start()
        return self

    def close(self):
        if self.thread is not None:
            self.http.shutdown()
            self.thread.join(timeout=2)
            self.thread = None
        self.http.server_close()

    def __enter__(self):
        return self.start()

    def __exit__(self, *args):
        self.close()


class UploadClient:
    def __init__(self, directory):
        self.directory = Path(directory).resolve()
        self.config = config_for(directory)
        self.queue = UploadQueue(directory)
        self.server = None
        self.active_requests = set()

    def health(self):
        # Direct loopback only: no environment proxy or redirect can receive the token.
        connection = http.client.HTTPConnection('127.0.0.1', self.config['port'], timeout=2)
        try:
            connection.request('GET', '/health', headers={'Authorization': 'Bearer ' + self.config['token']})
            response = connection.getresponse()
            if response.status != 200:
                raise Hold('UPLOAD_HELPER_PORT_IN_USE', 'The configured port did not return the authenticated local bridge')
            result = json.loads(response.read(16385))
        finally:
            connection.close()
        if not isinstance(result, dict):
            raise Hold('UPLOAD_HELPER_IDENTITY_MISMATCH')
        if result.get('version') != VERSION or result.get('extension_id') != self.config['extension_id']:
            raise Hold('UPLOAD_HELPER_IDENTITY_MISMATCH')
        return result

    def ensure_server(self):
        try:
            return self.health()
        except ConnectionRefusedError:
            try:
                self.server = UploadServer(self.directory, self.config).start()
            except OSError:
                raise Hold('UPLOAD_HELPER_PORT_IN_USE')
            return self.health()
        except (OSError, http.client.HTTPException, ValueError):
            raise Hold('UPLOAD_HELPER_UNREACHABLE', 'The existing bridge could not be verified; it was not replaced')

    def upload(self, job, binding, trigger, guards, timeout=90):
        self.ensure_server()
        value = self.queue.submit(job, binding, trigger, guards)
        self.active_requests.add(value['request_id'])
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self.queue.next()  # expire a lost lease without issuing another one
            value = self.queue.load(value['request_id'])
            if value['status'] == 'DONE':
                return value['result']
            if value['status'] in {'FAILED', 'OUTCOME_UNKNOWN', 'EXPIRED', 'CANCELLED'}:
                raise Hold('UPLOAD_HELPER_' + value['status'], canonical(value.get('result', {'code': value['status']})))
            time.sleep(0.2)
        raise Hold('UPLOAD_HELPER_NOT_CONNECTED', 'No verified upload receipt arrived. Load the prepared helper in the existing Chrome profile; no Publish action was attempted')

    def close(self):
        for request_id in self.active_requests:
            self.queue.cancel(request_id)
        self.active_requests.clear()
        if self.server is not None:
            self.server.close()
            self.server = None
