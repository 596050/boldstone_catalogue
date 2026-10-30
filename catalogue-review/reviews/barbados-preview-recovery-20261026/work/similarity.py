"""Read-only, asynchronous visual ordering of the currently filtered gallery.

Feature prints never participate in byte deduplication, identities, or exports.
Only server-owned cached image paths are handed to the local Vision worker.
"""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import hashlib
import json
import platform
import subprocess
import threading


class Similarity:
    def __init__(self, root):
        self.root = Path(root) / 'similarity-v1'
        self.root.mkdir(parents=True, exist_ok=True)
        self.source = Path(__file__).with_name('similarity_worker.swift')
        self.version = hashlib.sha256(self.source.read_bytes() + platform.mac_ver()[0].encode()).hexdigest()
        self.binary = self.root / ('vision-' + self.version[:16])
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='image-similarity')
        self.jobs = {}
        self.lock = threading.Lock()

    def start(self, body, view):
        groups = body.get('groups')
        if (not isinstance(groups, list) or not groups or len(groups) > 20000
                or any(not isinstance(g, list) or not g for g in groups)):
            raise ValueError('Choose image groups to sort.')
        ids = [aid for group in groups for aid in group]
        if (len(ids) > 20000 or any(not isinstance(a, str) for a in ids)
                or len(set(ids)) != len(ids)):
            raise ValueError('Choose unique image IDs, up to 20,000 at a time.')
        if type(body.get('reverse', False)) is not bool:
            raise ValueError('Invalid similarity direction.')
        cat = view.cat
        entries = {}
        for aid in ids:
            if aid not in cat.assets or view.cid(aid) != aid or aid in view.deleted:
                raise ValueError('An image changed or is no longer available. Refresh this gallery.')
            asset = cat.assets[aid]
            selected = getattr(cat, 'preview_paths', {}).get(aid) or cat.paths.get(aid, (None, ''))[0]
            path, stamp = None, None
            if selected:
                try:
                    candidate = Path(selected)
                    stat = candidate.stat()
                    if candidate.is_file():
                        path = str(candidate)
                        stamp = [stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns]
                except OSError:
                    pass
            fingerprint = [self.version, path, stamp, asset.get('original', {}).get('dropbox_content_hash'),
                           asset.get('original', {}).get('sha256')]
            key = hashlib.sha256(json.dumps(fingerprint).encode()).hexdigest()
            entries[aid] = {'id': aid, 'key': key, 'path': path}
        request = {'groups': [[entries[a] for a in group] for group in groups],
                   'reverse': body.get('reverse', False)}
        key = hashlib.sha256(json.dumps(request, sort_keys=True).encode()).hexdigest()
        with self.lock:
            if key not in self.jobs or self.jobs[key].get('state') == 'error':
                self.jobs[key] = {'job_id': key, 'state': 'queued', 'total': len(ids)}
                self.executor.submit(self._run, key, request)
            return dict(self.jobs[key])

    def status(self, key):
        with self.lock:
            if key not in self.jobs:
                raise KeyError('Unknown similarity job. Apply the sort again.')
            value = dict(self.jobs[key])
        if value['state'] == 'running':
            try:
                value.update(json.loads((self.root / (key + '.status.json')).read_text()))
            except (OSError, ValueError):
                pass
        return value

    def _run(self, key, request):
        result = self.root / (key + '.result.json')
        try:
            with self.lock:
                self.jobs[key]['state'] = 'running'
            if result.exists():
                value = json.loads(result.read_text())
            else:
                if not self.binary.exists():
                    subprocess.run(['/usr/bin/swiftc', '-O', str(self.source), '-o', str(self.binary)],
                                   capture_output=True, check=True, timeout=120)
                request.update(cache=str(self.root / 'features'), result=str(result),
                               status=str(self.root / (key + '.status.json')))
                path = self.root / (key + '.request.json')
                path.write_text(json.dumps(request))
                subprocess.run([str(self.binary), str(path)], capture_output=True, check=True, timeout=1800)
                value = json.loads(result.read_text())
            expected = [item['id'] for group in request['groups'] for item in group]
            if len(value['order']) != len(expected) or set(value['order']) != set(expected):
                result.unlink(missing_ok=True)
                raise ValueError('Incomplete similarity result')
            with self.lock:
                self.jobs[key].update(value, state='ready')
        except Exception:
            with self.lock:
                self.jobs[key].update(state='error', error='Local image similarity could not finish. Other sorts are available; apply the sort again to retry.')
