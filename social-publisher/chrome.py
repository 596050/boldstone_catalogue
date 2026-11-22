"""Bounded Apple events into explicitly reserved tabs of the normal Chrome app."""
import base64
import json
import os
import subprocess
import tempfile
import time
import uuid
from pathlib import Path

from common import ROOT, Hold, atomic_json, canonical, digest, read_json, utc
from settings import Settings

READONLY = {'probe', 'snapshot', 'exists', 'assert', 'discover', 'readback', 'upload_status', 'clean_state', 'source_grid', 'source_modal','source_facebook_photo'}
VERIFICATION = 'verification'


class Chrome:
    def __init__(self, settings, directory, execute=subprocess.run):
        self.settings = settings
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.bindings_path = self.directory / 'bindings.json'
        self.bindings = read_json(self.bindings_path) if self.bindings_path.exists() else {}
        self.execute = execute
        self.driver = (ROOT / 'dom-driver.js').read_text(encoding='utf-8')
        self.upload_client = None

    def apple(self, args):
        try:
            p = self.execute(['/usr/bin/osascript', str(ROOT / 'chrome.applescript')] + [str(a) for a in args],
                             capture_output=True, text=True, timeout=8, check=False)
        except subprocess.TimeoutExpired:
            raise Hold('APPLE_EVENT_TIMEOUT', 'The background operation timed out', retryable=True)
        if p.returncode:
            message = p.stderr.strip()[-1200:]
            if '-1743' in message or 'JavaScript from Apple Events' in message or 'not authorized' in message:
                raise Hold('APPLE_EVENT_PERMISSION', message)
            for code in ['TAB_NAVIGATED_EXTERNALLY', 'FOREGROUND_TAB_PAUSED', 'NORMAL_PROFILE_REQUIRED', 'CHROME_NOT_RUNNING']:
                if code in message:
                    raise Hold(code, message)
            raise Hold('APPLE_EVENT_REFUSED', message, retryable=True)
        return p.stdout.strip()

    def inventory(self):
        value = json.loads(self.apple(['inventory']))
        return self.normalize_inventory(value)

    def state_for(self, binding):
        value = json.loads(self.apple(['tab-state', binding['window_id'], binding['tab_id']]))
        return self.normalize_inventory(value)

    @staticmethod
    def normalize_inventory(value):
        if not isinstance(value.get('windows'), list):
            raise Hold('INVENTORY_INVALID')
        for w in value['windows']:
            w['window_id'], w['active_tab_id'] = int(w['window_id']), int(w['active_tab_id'])
            for t in w['tabs']:
                t['tab_id'] = int(t['tab_id'])
        return value

    def profile(self, name):
        if name == VERIFICATION:
            return {'allowed_hosts': sorted({h for p in self.settings.profiles.values() for h in p['allowed_hosts']})}
        return self.settings.profile(name)

    def profile_hash(self, name):
        return digest({'role': VERIFICATION, **self.profile(name)}) if name == VERIFICATION else self.settings.fingerprint(name)

    @staticmethod
    def find(inventory, window_id, tab_id):
        for w in inventory['windows']:
            if w['window_id'] == int(window_id):
                for t in w['tabs']:
                    if t['tab_id'] == int(tab_id):
                        if w['mode'] != 'normal':
                            raise Hold('NORMAL_PROFILE_REQUIRED')
                        return w, t
        raise Hold('RESERVED_TAB_MISSING', 'Reserve and bind a replacement background tab; this runner never opens or activates one')

    @staticmethod
    def focus_stamp(inventory):
        return {'frontmost': inventory['frontmost'],
                'front_window_id': inventory['windows'][0]['window_id'] if inventory['windows'] else None,
                'active_tabs': {str(w['window_id']): w['active_tab_id'] for w in inventory['windows']}}

    @staticmethod
    def target_foreground(inventory, binding):
        windows = inventory['windows']
        return bool(inventory['frontmost'] == 'com.google.Chrome' and windows and
                    windows[0]['window_id'] == binding['window_id'] and windows[0]['active_tab_id'] == binding['tab_id'])

    def bound(self, name, mutation=False):
        self.settings.check_current()
        if name not in self.bindings:
            raise Hold('RESERVED_TAB_NOT_BOUND', 'Use bind --profile ' + name + ' with an explicitly reserved background tab')
        b = self.bindings[name]
        state = self.state_for(b)
        w, tab = self.find(state, b['window_id'], b['tab_id'])
        if tab['url'] != b['url']:
            if b.get('pending_url') == tab['url']:
                b['url'] = tab['url']
                b.pop('pending_url', None)
                self.save_bindings()
            else:
                raise Hold('TAB_NAVIGATED_EXTERNALLY', 'The reserved tab changed outside the runner; inspect it before rebinding')
        Settings.check_url(self.profile(name), tab['url'], allow_blank=True)
        if mutation and state['frontmost'] == 'com.google.Chrome' and state['windows'][0]['window_id'] == w['window_id'] and w['active_tab_id'] == tab['tab_id']:
            raise Hold('FOREGROUND_TAB_PAUSED', 'The user is using the reserved tab; resume when it is in the background')
        return b, state

    def save_bindings(self):
        atomic_json(self.bindings_path, self.bindings)

    def adopt_profile(self, name):
        binding, _ = self.bound(name, mutation=True)
        self.call(name, {'op': 'claim'})
        binding.update(profile_hash=self.profile_hash(name), step=0)
        self.save_bindings()

    def bind(self, name, window_id, tab_id):
        p = self.profile(name)
        inventory = self.state_for({'window_id': int(window_id), 'tab_id': int(tab_id)})
        w, tab = self.find(inventory, window_id, tab_id)
        Settings.check_url(p, tab['url'], allow_blank=True)
        if any(v['tab_id'] == int(tab_id) and k != name for k, v in self.bindings.items()):
            raise Hold('TAB_ALREADY_BOUND', 'Each platform profile gets its own reserved tab')
        if inventory['frontmost'] == 'com.google.Chrome' and inventory['windows'][0]['window_id'] == w['window_id'] and w['active_tab_id'] == tab['tab_id']:
            raise Hold('FOREGROUND_TAB_PAUSED', 'Switch back to your own tab before binding this reserved tab')
        self.bindings[name] = {'window_id': int(window_id), 'tab_id': int(tab_id), 'url': tab['url'], 'owner': uuid.uuid4().hex,
                               'profile_hash': self.profile_hash(name), 'job_id': None, 'step': 0}
        self.save_bindings()
        return self.bindings[name]

    def evaluate(self, binding, request, readonly=True):
        request = {'expectedURL': binding['url'], 'owner': binding['owner'], **request}
        fd, path = tempfile.mkstemp(prefix='.dom-', suffix='.js', dir=str(self.directory))
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                stream.write(self.driver + '(' + canonical(request) + ')')
            output = self.apple(['inspect' if readonly else 'execute', binding['window_id'], binding['tab_id'], binding['url'], path])
        finally:
            os.unlink(path)
        try:
            result = json.loads(output)
        except (ValueError, TypeError):
            raise Hold('DOM_RESPONSE_INVALID', 'Chrome did not return a JSON result', retryable=True)
        if not result.get('ok'):
            code = result.get('code', 'DOM_ERROR')
            retryable = code in {'CONTROL_MISSING', 'PHOTO_NOT_LOADED','VIDEO_NOT_LOADED', 'SUBMIT_DISABLED', 'CONTROL_DISABLED', 'NATIVE_CAPTION_MISMATCH', 'NATIVE_PHOTO_MISMATCH'}
            raise Hold(code, result.get('detail', code), retryable=retryable)
        return result

    def call(self, name, request):
        readonly = request['op'] in READONLY
        b, before = self.bound(name, mutation=not readonly)
        try:
            return self.evaluate(b, request, readonly=readonly)
        finally:
            if not readonly:
                after = self.state_for(b)
                changed = self.focus_stamp(before) != self.focus_stamp(after)
                # Never restore focus: a concurrent user change belongs to the user.
                audit = {'utc': utc(), 'profile_id': name, 'operation': request['op'], 'unchanged': not changed,
                         'before': self.focus_stamp(before), 'after': self.focus_stamp(after),
                         'target_remained_background': not self.target_foreground(after, b)}
                with (self.directory / 'focus-audit.jsonl').open('a', encoding='utf-8') as stream:
                    stream.write(canonical(audit) + '\n')
                if self.target_foreground(after, b):
                    raise Hold('FOCUS_CHANGED_PAUSED', 'The reserved tab became foreground; inspect and resume after it is in the background')

    def navigate(self, name, url, job_id=None, recovery=False):
        p = self.profile(name)
        Settings.check_url(p, url)
        b, before = self.bound(name, mutation=True)
        if b.get('dirty'):
            raise Hold('DRAFT_NEEDS_INSPECTION', 'An unfinished owned composer is retained; inspect it instead of discarding it automatically')
        # Chrome's native `set URL of tab` activates its window on this Mac.
        # Ordinary in-page navigation preserves the inactive window instead.
        self.call(name, {'op': 'claim'})
        b['pending_url'] = url
        self.save_bindings()
        result = self.call(name, {'op': 'navigate', 'url': url})
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            state = self.state_for(b)
            _, tab = self.find(state, b['window_id'], b['tab_id'])
            if self.target_foreground(state, b):
                raise Hold('FOCUS_CHANGED_PAUSED')
            canonical_feed = url=='https://www.linkedin.com/feed/' and tab['url']=='https://www.linkedin.com/feed/foryou/'
            if not tab['loading'] and (tab['url'] == url or canonical_feed):
                Settings.check_url(p, tab['url'])
                b.update(url=tab['url'], job_id=job_id, step=0, dirty=False)
                b.pop('pending_url', None)
                self.save_bindings()
                self.call(name, {'op': 'claim'})
                return result
            time.sleep(0.3)
        raise Hold('NAVIGATION_TIMEOUT', 'The owned tab is still loading; inspect it before rebinding', retryable=True)

    def sync_after_submit(self, name):
        """Read an expected platform redirect, never adopt an arbitrary user URL."""
        if name not in self.bindings:
            raise Hold('RESERVED_TAB_NOT_BOUND')
        b = self.bindings[name]
        inventory = self.state_for(b)
        _, tab = self.find(inventory, b['window_id'], b['tab_id'])
        if tab['url'] != b['url']:
            from urllib.parse import urlparse
            profile = self.profile(name)
            Settings.check_url(profile, tab['url'])
            path=urlparse(tab['url']).path
            canonical_feed = profile.get('platform')=='linkedin' and path=='/feed/foryou/' and '/feed/' in profile.get('post_submit_paths',[])
            if path not in profile.get('post_submit_paths', []) and not canonical_feed:
                raise Hold('TAB_NAVIGATED_EXTERNALLY', 'Unexpected navigation after submission; inspect before rebinding')
            b['url'] = tab['url']
            self.save_bindings()
        return b

    def sync_expected_navigation(self, name, pattern, timeout=20):
        """Adopt only a calibrated navigation caused by the preceding UI action."""
        import re
        binding = self.bindings[name]
        deadline = time.monotonic() + timeout
        while True:
            state = self.state_for(binding)
            _, tab = self.find(state, binding['window_id'], binding['tab_id'])
            if self.target_foreground(state, binding):
                raise Hold('FOCUS_CHANGED_PAUSED')
            if not tab['loading'] and re.fullmatch(pattern, tab['url']):
                Settings.check_url(self.profile(name), tab['url'])
                binding['url'] = tab['url']
                self.save_bindings()
                self.call(name, {'op': 'claim'})
                return binding
            if time.monotonic() >= deadline:
                raise Hold('RECOVERY_NAVIGATION_TIMEOUT', 'The expected native inventory detail did not open', retryable=True)
            time.sleep(0.3)

    def begin(self, name, job_id, url):
        b, _ = self.bound(name, mutation=True)
        if b['profile_hash'] != self.settings.fingerprint(name):
            raise Hold('BOUND_PROFILE_CHANGED', 'Inspect the new account and bind its reserved tab again')
        if b.get('job_id') != job_id:
            self.navigate(name, url, job_id)
        else:
            self.call(name, {'op': 'claim'})
        self.call(name, {'op': 'begin_job', 'job': job_id})
        return self.bindings[name]

    def checkpoint(self, name, step, dirty=True):
        self.bindings[name].update(step=step, dirty=dirty)
        self.save_bindings()

    def upload(self, name, job, locator, method='input', preview=None, guards=None):
        data = Path(job['media_path']).read_bytes()
        if digest(data) != job['media_sha256']:
            raise Hold('MEDIA_HASH_CHANGED')
        common = {'job': job['id'], 'mediaSha256': job['media_sha256'], 'checks': guards or []}
        if guards:
            self.call(name, {'op':'assert','checks':guards})
        status = self.call(name, {'op': 'upload_status', **common})
        if status.get('committed') and status.get('sha256') == job['media_sha256'] and (method != 'helper' or status.get('method') == 'helper'):
            if preview:
                self.confirm_upload_preview(name,preview,job)
            return status
        if method == 'helper':
            if not preview:
                raise Hold('UPLOAD_PREVIEW_GUARD_MISSING')
            from upload_bridge import UploadClient
            if self.upload_client is None:
                self.upload_client = UploadClient(self.directory)
            binding, before = self.bound(name, mutation=True)
            result = self.upload_client.upload(job, binding, locator, guards or [])
            atomic_json(self.directory / 'evidence' / (job['id'] + '-upload.json'),
                        {'utc': utc(), 'job_id': job['id'], 'input_receipt': result, 'preview_confirmed': False})
            deadline = time.monotonic() + 30
            while True:
                try:
                    adopted = self.call(name, {'op': 'adopt_upload', 'receipt': result, 'preview': preview, **common})
                    break
                except Hold as error:
                    if error.code not in {'CONTROL_MISSING', 'PHOTO_NOT_LOADED'} or time.monotonic() >= deadline:
                        raise
                    time.sleep(0.5)
            after = self.state_for(binding)
            unchanged = self.focus_stamp(before) == self.focus_stamp(after)
            with (self.directory / 'focus-audit.jsonl').open('a', encoding='utf-8') as stream:
                stream.write(canonical({'utc': utc(), 'profile_id': name, 'operation': 'helper_upload', 'unchanged': unchanged,
                                        'before': self.focus_stamp(before), 'after': self.focus_stamp(after)}) + '\n')
            if self.target_foreground(after, binding):
                raise Hold('FOCUS_CHANGED_PAUSED', 'The reserved tab became foreground during upload; its draft is retained')
            atomic_json(self.directory / 'evidence' / (job['id'] + '-upload.json'),
                        {'utc': utc(), 'job_id': job['id'], 'input_receipt': result, 'preview_confirmed': True, 'preview': adopted})
            return adopted
        if method not in {'input', 'drop'}:
            raise Hold('UPLOAD_METHOD_INVALID')
        self.call(name, {'op': 'upload_begin', 'locator': locator, 'name': Path(job['media_path']).name,
                         'type': job['media_type'], 'size': len(data), 'method': method, **common})
        chunks = [data[i:i + 384 * 1024] for i in range(0, len(data), 384 * 1024)]
        for i, chunk in enumerate(chunks):
            self.call(name, {'op': 'upload_chunk', 'index': i, 'data': base64.b64encode(chunk).decode('ascii'), **common})
        self.call(name, {'op': 'upload_finish', 'chunks': len(chunks), **common})
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            status = self.call(name, {'op': 'upload_status', **common})
            if status.get('status') == 'HASH_VERIFIED':
                result = self.call(name, {'op': 'upload_commit', **common})
                if method == 'drop':
                    self.call(name, {'op': 'upload_drop', 'phase': 'over', **common})
                    result = self.call(name, {'op': 'upload_drop', 'phase': 'drop', **common})
                if preview:
                    evidence=self.confirm_upload_preview(name,preview,job)
                    result.update(status='PHOTO_PREVIEW_CONFIRMED',preview_confirmed=True,sha256=job['media_sha256'])
                    atomic_json(self.directory/'evidence'/(job['id']+'-upload.json'),{'utc':utc(),'job_id':job['id'],'method':method,'sha256':job['media_sha256'],'preview_confirmed':True,'preview':evidence})
                return result
            if status.get('status') != 'HASHING':
                raise Hold('UPLOAD_HASH_FAILED')
            time.sleep(0.2)
        raise Hold('UPLOAD_HASH_TIMEOUT', retryable=True)

    def confirm_upload_preview(self,name,preview,job=None):
        check=preview if isinstance(preview,dict) and 'locator' in preview else {'locator':preview,'image':True}
        context={'job':job['id'],'mediaSha256':job['media_sha256']} if job else {}
        deadline=time.monotonic()+30
        while True:
            try:
                if check.get('svg_image'):
                    if not job:raise Hold('PHOTO_CONTEXT_MISSING')
                    self.call(name,{'op':'probe_svg_photo','locator':check['locator'],**context})
                return self.call(name,{'op':'assert','checks':[check],**context})
            except Hold as error:
                if error.code not in {'CONTROL_MISSING','PHOTO_NOT_LOADED','VIDEO_NOT_LOADED'}:
                    raise
                if time.monotonic()>=deadline:
                    raise Hold('UPLOAD_PREVIEW_NOT_CONFIRMED','File events were dispatched but no loaded photo was confirmed; inspect this draft without uploading again')
                time.sleep(.3)

    def close(self):
        if self.upload_client is not None:
            self.upload_client.close()
            self.upload_client = None

