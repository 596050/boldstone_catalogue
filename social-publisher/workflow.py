"""Configurable platform workflows with exact UI guards and native readbacks."""
import html
import re
import time
import urllib.request
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from common import Hold, atomic_json, digest, utc
from chrome import VERIFICATION


def render(value, context):
    if isinstance(value, str) and value.startswith('$'):
        result = context
        for key in value[1:].split('.'):
            if not isinstance(result, dict) or key not in result:
                raise Hold('WORKFLOW_VARIABLE', value)
            result = result[key]
        return result
    if isinstance(value, list):
        return [render(v, context) for v in value]
    if isinstance(value, dict):
        return {k: render(v, context) for k, v in value.items()}
    return value


class Workflow:
    def __init__(self, settings, chrome, directory):
        self.settings, self.chrome = settings, chrome
        self.directory = Path(directory)

    def context(self, job):
        p = job['payload']
        profile = self.settings.profile(p['profile_id'])
        if self.settings.fingerprint(p['profile_id']) != p['profile_hash']:
            raise Hold('PROFILE_CHANGED', 'Queued account details or workflow changed; inspect and explicitly adopt the change before submission')
        if digest(Path(p['media_path']).read_bytes()) != p['media_sha256']:
            raise Hold('MEDIA_HASH_CHANGED')
        return {**profile, **p, 'id': job['id'], 'job': job['id'], 'mediaSha256': p['media_sha256']}

    @staticmethod
    def enabled_steps(steps, context):
        for step in steps:
            if step.get('when') and not context.get(step['when']):
                continue
            yield render({k: v for k, v in step.items() if k != 'when'}, context)

    def wait(self, profile_id, locator, timeout=20):
        deadline = time.monotonic() + timeout
        while True:
            result = self.chrome.call(profile_id, {'op': 'exists', 'locator': locator})
            if result['exists']:
                return
            if time.monotonic() >= deadline:
                raise Hold('CONTROL_MISSING', 'The expected interface did not become ready', retryable=True)
            time.sleep(0.25)

    def guards(self, recipe, context):
        return list(self.enabled_steps(recipe['ready'], context))

    def prepare(self, job):
        c = self.context(job)
        name = c['profile_id']
        recipe = self.settings.workflow(self.settings.profile(name))
        self.chrome.bound(VERIFICATION, mutation=True)  # required before any possible submission
        binding = self.chrome.begin(name, job['id'], c['compose_url'])
        steps = list(self.enabled_steps(recipe.get('prepare', []), c))
        for index, step in enumerate(steps):
            if index < binding.get('step', 0):
                continue
            if step.get('if_exists') and not self.chrome.call(name, {'op': 'exists', 'locator': step['locator']})['exists']:
                self.chrome.checkpoint(name, index + 1)
                continue
            if step.get('unless') and self.chrome.call(name, {'op': 'exists', 'locator': step['unless']})['exists']:
                self.chrome.checkpoint(name, index + 1)
                continue
            op = step['op']
            if op == 'wait':
                self.wait(name, step['locator'])
            elif op == 'upload':
                self.chrome.upload(name, c, step['locator'])
            elif op in {'set_text', 'set_checked', 'click', 'assert'}:
                args = {k: v for k, v in step.items() if k not in {'unless', 'dirty', 'if_exists'}}
                self.chrome.call(name, args)
            else:
                raise Hold('WORKFLOW_OPERATION', op)
            self.chrome.checkpoint(name, index + 1, dirty=step.get('dirty', True))
        request = {'op': 'ready', 'job': job['id'], 'mediaSha256': c['media_sha256'],
                   'checks': self.guards(recipe, c), 'submit': render(recipe['submit'], c)}
        ready = self.chrome.call(name, request)
        atomic_json(self.directory / 'evidence' / (job['id'] + '-ready.json'), {'utc': utc(), 'job_id': job['id'], 'ready': ready})
        return ready

    def submit(self, job):
        c = self.context(job)
        self.chrome.bound(VERIFICATION, mutation=True)
        recipe = self.settings.workflow(self.settings.profile(c['profile_id']))
        # All caption, account, image and product-tag guards execute again in the
        # same JS turn as the one allowed click. No intervening unguarded action.
        return self.chrome.call(c['profile_id'], {'op': 'submit', 'job': job['id'], 'mediaSha256': c['media_sha256'],
                                                'checks': self.guards(recipe, c), 'submit': render(recipe['submit'], c)})

    @staticmethod
    def unwrap_link(url):
        u = urlparse(url)
        if u.hostname in {'l.facebook.com', 'lm.facebook.com', 'l.instagram.com'}:
            return parse_qs(u.query).get('u', [url])[0]
        return url

    def purchase_links(self, job, links):
        expected = re.findall(r'https?://[^\s<>]+', job['payload']['caption'])
        if job['payload'].get('purchase_url') and not (job['payload']['platform'] == 'instagram' and job['payload'].get('product_tag')) and job['payload']['purchase_url'] not in expected:
            expected.append(job['payload']['purchase_url'])
        observed = {self.unwrap_link(url) for url in links}
        verified = []
        for url in expected:
            if url in observed:
                verified.append({'expected': url, 'native_link': url})
                continue
            found = None
            for short in sorted(observed):
                u = urlparse(short)
                if u.scheme != 'https' or u.hostname != 'lnkd.in' or u.username or u.password:
                    continue
                # Public LinkedIn landing page; never send browser credentials.
                request = urllib.request.Request(short, headers={'User-Agent': 'Mozilla/5.0'})
                try:
                    with urllib.request.urlopen(request, timeout=8) as response:
                        if urlparse(response.url).hostname not in {'lnkd.in', 'www.linkedin.com', 'linkedin.com'}:
                            continue
                        body = response.read(2_000_000).decode('utf-8')
                except (OSError, ValueError):
                    continue
                destinations = re.findall(r'data-tracking-control-name="external_url_click"[^>]*href="([^"]+)"', html.unescape(body))
                if url in destinations:
                    found = {'expected': url, 'native_link': short, 'landing_sha256': digest(body.encode('utf-8'))}
                    break
            if found is None:
                raise Hold('NATIVE_PURCHASE_LINK_MISMATCH', 'The published purchase destination is not verified', retryable=True)
            verified.append(found)
        return verified

    def native_url(self, name, url, recipe):
        p = self.settings.profile(name)
        self.settings.check_url(p, url)
        if not re.fullmatch(recipe['native_url_pattern'], url):
            raise Hold('NATIVE_PERMALINK_INVALID', url)

    def verify(self, job, native_url=None):
        c = self.context(job)
        name = c['profile_id']
        recipe = self.settings.workflow(self.settings.profile(name))
        composer = self.chrome.sync_after_submit(name)
        reader = VERIFICATION
        b, _ = self.chrome.bound(reader)
        if native_url is None:
            if re.fullmatch(recipe['native_url_pattern'], composer['url']):
                native_url = composer['url']
            else:
                discovery = render(recipe['discover'], c)
                result = self.chrome.call(name, {'op': 'discover', 'pattern': recipe['native_url_pattern'], **discovery})
                native_url = result['url']
                if not native_url and recipe.get('recovery'):
                    recovery = render(recipe['recovery'], c)
                    self.settings.check_url(self.settings.profile(name), recovery.get('url', c['inventory_url']))
                    self.chrome.navigate(reader, recovery.get('url', c['inventory_url']), job['id'], recovery=True)
                    for step in recovery.get('steps', []):
                        if step['op'] == 'wait':
                            self.wait(reader, step['locator'])
                        elif step['op'] in {'set_text', 'click', 'assert'}:
                            self.chrome.call(reader, step)
                        else:
                            raise Hold('RECOVERY_OPERATION_INVALID')
                    result = self.chrome.call(reader, {'op': 'discover', 'pattern': recipe['native_url_pattern'], **recovery['discover']})
                    native_url = result['url']
        if not native_url:
            raise Hold('NATIVE_POST_NOT_FOUND', 'Inspect the platform’s Published inventory and run reconcile with its exact native URL')
        self.native_url(name, native_url, recipe)
        if b['url'] != native_url:
            self.chrome.navigate(reader, native_url, job['id'], recovery=True)
        spec = render({k: v for k, v in recipe['readback'].items() if k != 'tag_checks'}, c)
        for step in spec.get('expand', []):
            if self.chrome.call(reader, {'op': 'exists', 'locator': step})['exists']:
                self.chrome.call(reader, {'op': 'click', 'locator': step})
        deadline = time.monotonic() + 20
        while True:
            try:
                evidence = self.chrome.call(reader, {'op': 'readback', 'caption': c['caption'], 'root': spec['root'],
                                                  'author': spec['author'], 'photoSelector': spec['photo_selector'], 'captionSelectors': spec['caption_selectors']})
                break
            except Hold as error:
                if not error.retryable or time.monotonic() >= deadline:
                    raise
                time.sleep(0.3)
        links = self.purchase_links(job, evidence['links'])
        if c.get('product_tag'):
            for locator in spec.get('tag_expand', []):
                if self.chrome.call(reader, {'op': 'exists', 'locator': locator})['exists']:
                    self.chrome.call(reader, {'op': 'click', 'locator': locator})
            checks = recipe['readback'].get('tag_checks')
            if not checks:
                raise Hold('NATIVE_PRODUCT_TAG_CHECK_MISSING')
            evidence['product_tag_readback'] = self.chrome.call(reader, {'op': 'assert', 'checks': render(checks, c)})
        # A stale composer is never navigated away from. That could trigger a
        # browser-wide beforeunload dialog even from a background tab.
        try:
            for step in render(recipe.get('cleanup', []), c):
                if self.chrome.call(name, {'op': 'exists', 'locator': step['locator']})['exists']:
                    self.chrome.call(name, step)
            clean = self.chrome.call(name, {'op': 'clean_state', **render(recipe['clean_state'], c)})
            if clean['clean']:
                self.chrome.checkpoint(name, 0, dirty=False)
            else:
                evidence['composer_warning'] = 'Native post verified; stale composer retained for inspection'
        except Hold as error:
            evidence['composer_warning'] = str(error)
        evidence.update(job_id=job['id'], profile_hash=c['profile_hash'], verified_utc=utc(), purchase_links=links)
        evidence_path = self.directory / 'evidence' / (job['id'] + '-native-' + digest(evidence)[:12] + '.json')
        atomic_json(evidence_path, evidence)
        self.chrome.checkpoint(reader, 0, dirty=False)
        return {'native_url': native_url, 'caption_verified': True, 'author_verified': True, 'photo_verified': True,
                'media_sha256': c['media_sha256'], 'purchase_links': links, 'verified_utc': utc(),
                'evidence_path': str(evidence_path.resolve()), 'evidence_sha256': digest(evidence_path.read_bytes())}

