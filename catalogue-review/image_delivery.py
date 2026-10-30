"""Bounded thumbnail storage and read-only, diskless original delivery.

Only the server may create a specification, from a known catalogue asset. The
SDK runs in the existing private Python environment; credentials never enter
the HTTP process, command line, browser or thumbnail cache.
"""
from contextlib import contextmanager
from pathlib import Path
import hashlib
import json
import os
import subprocess
import threading
import time
import uuid


class ImageUnavailable(Exception):
    pass


class ThumbnailCache:
    def __init__(self, root, limit=256 * 1024 * 1024):
        self.root = Path(root) / 'image-thumbnails'
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.limit = limit
        self.lock = threading.RLock()
        self.prune()

    def path(self, key):
        return self.root / (hashlib.sha256(key.encode()).hexdigest() + '.jpg')

    def get(self, key):
        with self.lock:
            path = self.path(key)
            try:
                data = path.read_bytes()
                if not data.startswith(b'\xff\xd8\xff') or len(data) > 4_000_000:
                    path.unlink(missing_ok=True)
                    return None
                path.touch()
                return data
            except FileNotFoundError:
                return None

    def put(self, key, data):
        if not data.startswith(b'\xff\xd8\xff') or len(data) > 4_000_000:
            raise ImageUnavailable('The thumbnail response was not a supported image.')
        with self.lock:
            if len(data) > self.limit:
                return  # Usable for this request, but too large for this cache.
            path = self.path(key)
            temporary = path.with_suffix('.' + uuid.uuid4().hex + '.tmp')
            try:
                with temporary.open('xb') as stream:
                    os.chmod(temporary, 0o600)
                    stream.write(data)
                temporary.replace(path)
                self.prune()
            finally:
                temporary.unlink(missing_ok=True)

    def prune(self):
        with self.lock:
            rows = [(p.stat().st_mtime_ns, p.stat().st_size, p) for p in self.root.glob('*.jpg') if not p.is_symlink()]
            size = sum(row[1] for row in rows)
            for _, length, path in sorted(rows):
                if size <= self.limit:
                    break
                path.unlink(missing_ok=True)
                size -= length


class ImageDelivery:
    def __init__(self, project, root, cache_limit=256 * 1024 * 1024):
        self.project = Path(project)
        self.cache = ThumbnailCache(root, cache_limit)
        self.slots = threading.BoundedSemaphore(3)
        self.lock = threading.RLock()
        self.pending = {}
        self.failures = {}

    @staticmethod
    def key(spec):
        # Also separate local preview revisions and native files with equal
        # contents. A failure/deletion of one ID cannot poison another ID.
        return json.dumps({k: spec.get(k) for k in ('id', 'hash', 'bytes', 'local_stamp')}, sort_keys=True)

    @contextmanager
    def worker(self, spec, action):
        if not self.slots.acquire(timeout=30):
            raise ImageUnavailable('Images are still loading. Try again shortly.')
        process = timer = None
        try:
            python = self.project / 'application/.venv/bin/python'
            if not python.is_file():
                raise ImageUnavailable('The existing Dropbox image runtime is unavailable.')
            process = subprocess.Popen([str(python), str(Path(__file__).with_name('image_delivery_worker.py')),
                                        '--project', str(self.project), '--action', action],
                                       stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            timer = threading.Timer(100, process.kill)
            timer.daemon = True
            timer.start()
            process.stdin.write(json.dumps(spec).encode())
            process.stdin.close()
            line = process.stdout.readline(4096)
            try:
                header = json.loads(line)
            except (ValueError, UnicodeDecodeError):
                raise ImageUnavailable('Dropbox could not load this image. Try again or open its source link.') from None
            if (header.get('error') or header.get('mime') not in ('image/jpeg', 'image/png', 'image/gif', 'image/webp', 'image/bmp', 'image/avif')
                    or type(header.get('bytes')) is not int or not 0 < header['bytes'] < 150_000_000):
                raise ImageUnavailable('Dropbox could not load this image. Try again or open its source link.')
            yield header, process.stdout
            if process.wait(timeout=5):
                raise ImageUnavailable('Dropbox did not finish loading this image.')
        finally:
            if timer:
                timer.cancel()
            if process:
                if process.poll() is None:
                    process.kill()
                process.wait()
                process.stdout.close()
                if not process.stdin.closed:
                    process.stdin.close()
            self.slots.release()

    def thumbnail(self, spec):
        key = self.key(spec)
        cached = self.cache.get(key)
        if cached is not None:
            return cached
        with self.lock:
            cached = self.cache.get(key)
            if cached is not None:
                return cached
            if self.failures.get(key, 0) > time.monotonic():
                raise ImageUnavailable('This image is temporarily unavailable. Try again shortly.')
            event = self.pending.get(key)
            owner = event is None
            if owner:
                event = self.pending[key] = threading.Event()
        if not owner:
            if not event.wait(105):
                raise ImageUnavailable('This image is still loading. Try again shortly.')
            cached = self.cache.get(key)
            if cached is None:
                raise ImageUnavailable('This image could not be loaded. Try again shortly.')
            return cached
        try:
            with self.worker(spec, 'thumbnail') as (header, stream):
                if header['mime'] != 'image/jpeg' or header['bytes'] > 4_000_000:
                    raise ImageUnavailable('The thumbnail response was too large.')
                data = stream.read(header['bytes'] + 1)
                if len(data) != header['bytes']:
                    raise ImageUnavailable('The thumbnail download was incomplete.')
            self.cache.put(key, data)
            return data
        except Exception:
            with self.lock:
                now = time.monotonic()
                self.failures = {k: until for k, until in self.failures.items() if until > now}
                self.failures[key] = now + 30
            raise
        finally:
            with self.lock:
                self.pending.pop(key, None)
                event.set()
