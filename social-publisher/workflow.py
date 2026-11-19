"""Configurable platform workflows with exact UI guards and native readbacks."""
import html
import re
import time
import urllib.request
from pathlib import Path
from urllib.parse import parse_qs, parse_qsl, unquote, urlencode, urlparse, urlunparse

from common import Hold, atomic_json, digest, read_json, utc
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

    def wait_for_post_link(self, profile_id, locator, pattern, timeout=10):
        """Retry only native-link reads during a known publication redirect."""
        deadline=time.monotonic()+timeout
        while True:
            self.chrome.sync_after_submit(profile_id)
            try:
                if self.chrome.call(profile_id,{'op':'exists','locator':locator})['exists']:
                    url=self.chrome.call(profile_id,{'op':'discover','pattern':pattern,'roots':locator})['url']
                    if url:return url
            except Hold as error:
                if error.code!='TAB_NAVIGATED_EXTERNALLY' or time.monotonic()>=deadline:
                    raise
                # sync_after_submit on the next iteration accepts only the
                # configured post routes and the inspected canonical feed.
                continue
            if time.monotonic()>=deadline:raise Hold('CONTROL_MISSING','The native success link did not appear',retryable=True)
            time.sleep(.25)

    def guards(self, recipe, context):
        return list(self.enabled_steps(recipe['ready'], context))

    def photo_alt(self, profile_id, step):
        if not self.chrome.call(profile_id, {'op': 'exists', 'locator': step['panel']})['exists']:
            self.chrome.call(profile_id, {'op': 'click', 'locator': step['open']})
        if not self.chrome.call(profile_id, {'op': 'exists', 'locator': step['field']})['exists']:
            self.chrome.call(profile_id, {'op': 'click', 'locator': step['tab']})
        self.wait(profile_id, step['field'])
        check = {'locator': step['field'], 'text': step['value']}
        changed = False
        try:
            self.chrome.call(profile_id, {'op': 'assert', 'checks': [check]})
        except Hold as error:
            if error.code != 'TEXT_READBACK_CHANGED':
                raise
            changed = True
            self.chrome.call(profile_id, {'op': 'set_text', 'locator': step['field'], 'value': step['value']})
            self.chrome.call(profile_id, {'op': 'assert', 'checks': [check]})
        self.chrome.call(profile_id, {'op': 'click', 'locator': step['apply'] if changed else step['cancel']})
        deadline = time.monotonic() + 10
        while self.chrome.call(profile_id, {'op': 'exists', 'locator': step['panel']})['exists']:
            if time.monotonic() >= deadline:
                raise Hold('PHOTO_EDITOR_STILL_OPEN', retryable=True)
            time.sleep(0.25)
        return {'value': step['value'], 'changed': changed, 'editor_closed': True}

    def set_checked(self, profile_id, locator, value, timeout=5, confirmation=None):
        # Meta can leave a requested confirmation at zero opacity in an
        # inactive window. Its exact radio choices and resulting switch state
        # remain usable without activating or repainting that window.
        confirmation_root = [{k:v for k,v in spec.items() if k!='painted'} for spec in confirmation['root']] if confirmation else None
        pending = confirmation and self.chrome.call(profile_id, {'op': 'exists', 'locator': confirmation_root})['exists']
        if not pending:
            try:
                self.chrome.call(profile_id, {'op': 'set_checked', 'locator': locator, 'value': value})
            except Hold as error:
                # Poll the replacement node without repeating its earlier click.
                if error.code != 'CHECKBOX_READBACK_FAILED':
                    raise
        deadline = time.monotonic() + timeout
        while True:
            if confirmation and self.chrome.call(profile_id, {'op': 'exists', 'locator': confirmation_root})['exists']:
                self.chrome.call(profile_id, {'op': 'assert', 'checks': confirmation['checks']})
                self.chrome.call(profile_id, {'op': 'click', 'locator': confirmation['confirm']})
            try:
                return self.chrome.call(profile_id, {'op': 'assert', 'checks': [{'locator': locator, 'checked': value}]})
            except Hold as error:
                if error.code not in {'WRONG_SELECTED_ACCOUNT', 'CONTROL_MISSING'} or time.monotonic() >= deadline:
                    raise
                time.sleep(0.25)

    def wait_absent(self, profile_id, locator, timeout=10):
        deadline=time.monotonic()+timeout
        while self.chrome.call(profile_id, {'op':'exists','locator':locator})['exists']:
            if time.monotonic()>=deadline:
                raise Hold('UNFINISHED_DIALOG', retryable=True)
            time.sleep(.25)

    def product_tag(self, profile_id, context, step):
        """Save one exact product, reopen it, and attest its persisted UI value."""
        search = step['search']
        # Instagram's native crop editor returns to a product-only picker.
        # Its search field is a separate popover; selection is still attested
        # inside the exact tagging dialog before any publication is allowed.
        if context.get('platform') == 'instagram' and any(
                locator.get('selector') == 'input[role=combobox]' and
                locator.get('name') == 'Which product or collection would you like to tag?'
                for locator in search):
            search = search + [{'selector': 'input[role=combobox][aria-autocomplete=list]',
                                'name': 'Which product would you like to tag?'}]
        if not self.chrome.call(profile_id, {'op':'exists','locator':step['panel']})['exists']:
            self.chrome.call(profile_id, {'op':'click','locator':step['open']})
            self.wait(profile_id, step['panel'])
        self.chrome.call(profile_id, {'op':'click','locator':step['tab']})
        if not self.chrome.call(profile_id, {'op':'exists','locator':step['heading']})['exists']:
            self.chrome.call(profile_id, {'op':'click_photo_point','locator':step['photo'],'target':step['point_target'],'x':.5,'y':.5,'checks':[{'locator':step['tab']}]})
            self.wait(profile_id, search)
            self.chrome.call(profile_id, {'op':'set_text','locator':search,'value':context['product_tag']['name'],'focus':True,'typeahead':True})
            self.wait(profile_id, step['choice'])
            self.chrome.call(profile_id, {'op':'click','locator':step['choice'],'method':'mouse'})
            self.wait(profile_id, step['heading'])
        self.chrome.call(profile_id, {'op':'click','locator':step['save']})
        self.wait_absent(profile_id, step['panel'])
        self.chrome.call(profile_id, {'op':'click','locator':step['open']})
        self.wait(profile_id, step['heading'])
        proof=self.chrome.call(profile_id, {'op':'attest_product_tag','tag':context['product_tag'],'job':context['id'],'mediaSha256':context['media_sha256'],'panel':step['panel'],'heading':step['heading'],'markers':step['markers']})
        self.chrome.call(profile_id, {'op':'click','locator':step['cancel']})
        self.wait_absent(profile_id, step['panel'])
        self.chrome.call(profile_id, {'op':'assert','checks':[{'locator':step['badge'],'text':'1','tag_receipt':context['product_tag']}],'job':context['id'],'mediaSha256':context['media_sha256']})
        atomic_json(self.directory/'evidence'/(context['id']+'-product-tag.json'), {'utc':utc(),'job_id':context['id'],**proof})
        return proof

    def meta_published_row(self, context, recovery, timeout=30):
        """Read one exact caption despite Meta replacing filtered table rows."""
        reader = VERIFICATION
        binding, _ = self.chrome.bound(reader)
        if binding['url'] != context['inventory_url']:
            self.chrome.navigate(reader, context['inventory_url'], context['id'], recovery=True)
        self.wait(reader, recovery['search'])
        try:
            self.chrome.call(reader, {'op':'assert', 'checks':[{
                'locator':recovery['search'], 'text':context['title']} ]})
        except Hold as error:
            if error.code != 'TEXT_READBACK_CHANGED':
                raise
            self.chrome.call(reader, {'op':'set_text', 'locator':recovery['search'], 'value':context['title']})
        deadline = time.monotonic() + timeout
        while True:
            try:
                return self.chrome.call(reader, {'op':'snapshot', 'scope':recovery['row']})
            except Hold as error:
                if error.code != 'CONTROL_MISSING' or time.monotonic() >= deadline:
                    raise
                time.sleep(.25)

    def verify_product_tag(self, context, recipe):
        """Correlate the exact saved product with the published post's tag count.

        Meta disables photo editing after publication. Its published editor
        exposes the persisted association count, while the exact product and
        price are attested by saving and reopening the draft before submission.
        """
        recovery=render(recipe['readback']['tag_recovery'],context)
        reader=VERIFICATION
        proof_path=self.directory/'evidence'/(context['id']+'-product-tag.json')
        proof=read_json(proof_path)
        selected=proof.get('product_tag',{})
        expected={'job':context['id'],'sha256':context['media_sha256'],**context['product_tag']}
        if any(selected.get(k)!=v for k,v in expected.items()) or not selected.get('persisted_editor_readback'):
            raise Hold('PRODUCT_TAG_RECEIPT_MISSING')
        row=self.meta_published_row(context,recovery)
        ids=[re.fullmatch(r'Select item with ID (\d+)',control['name']) for control in row['controls']]
        ids=[m.group(1) for m in ids if m]
        if len(ids)!=1:raise Hold('NATIVE_PRODUCT_POST_AMBIGUOUS')
        post_id=ids[0]
        self.chrome.call(reader,{'op':'click','locator':recovery['menu']})
        self.chrome.call(reader,{'op':'click','locator':recovery['manage']})
        self.chrome.call(reader,{'op':'click','locator':recovery['edit']})
        self.chrome.sync_expected_navigation(reader,recovery['edit_url_pattern'].replace('{post_id}',post_id))
        self.wait(reader,recovery['caption'])
        checks=render(recipe['readback']['tag_checks'],context)
        native=self.chrome.call(reader,{'op':'assert','checks':checks})
        result={'method':'Meta published editor tag count correlated with exact saved product UI',
                'native_post_id':post_id,'native_editor_url':self.chrome.bindings[reader]['url'],
                'persisted_tag_count':1,'selected_product':selected,'native_checks':native,
                'selection_evidence_path':str(proof_path.resolve()),'selection_evidence_sha256':digest(proof_path.read_bytes())}
        self.chrome.call(reader,{'op':'click','locator':recovery['cancel']})
        self.wait(reader,recovery['leave'])
        # This reader has made no edits, and the exact published caption was
        # checked above. Only its inspection form is being closed.
        self.chrome.call(reader,{'op':'assert','checks':checks})
        self.chrome.call(reader,{'op':'click','locator':recovery['discard']})
        self.chrome.sync_expected_navigation(reader,recovery['inventory_pattern'])
        return result

    def meta_permalink(self, context, recipe):
        """Read the permalink from the exact published row, avoiding grid cache."""
        reader=VERIFICATION
        recovery=render(recipe['readback']['tag_recovery'],context)
        row=self.meta_published_row(context,recovery)
        ids=[re.fullmatch(r'Select item with ID (\d+)',control['name']) for control in row['controls']]
        ids=[m.group(1) for m in ids if m]
        if len(ids)!=1:raise Hold('AMBIGUOUS_NATIVE_POST')
        leaf=[{'selector':"[role=row] td[aria-colindex='2'] div.x1vvvo52.x1fvot60.xh8yej3",'text':context['caption'],'within':recovery['row'][0]}]
        self.chrome.call(reader,{'op':'click','locator':leaf})
        self.chrome.sync_expected_navigation(reader,r'https://business\.facebook\.com/latest/insights/object_insights/\?content_id='+ids[0]+r'&nav_ref=bizweb_published_posts_table')
        anchor=[{'selector':'a[href]','name':'View Post on '+context['platform'].title()}]
        self.wait(reader,anchor)
        snap=self.chrome.call(reader,{'op':'snapshot','scope':anchor})
        links=snap.get('links',[])
        # A scoped anchor is not included among its own descendants.
        if not links:
            snap=self.chrome.call(reader,{'op':'snapshot','fullDocument':True})
            links=[link for link in snap.get('links',[]) if link['text']=='View Post on '+context['platform'].title()]
        if len(links)!=1:raise Hold('AMBIGUOUS_NATIVE_POST')
        url=self.canonical_native_url(context['platform'],self.unwrap_link(links[0]['href']))
        self.native_url(context['profile_id'],url,recipe)
        return url

    def prepare(self, job):
        c = self.context(job)
        name = c['profile_id']
        recipe = self.settings.workflow(self.settings.profile(name))
        if self.settings.policy.get('require_meta_product_tags') and c['platform'] in {'facebook', 'instagram'} and not c.get('product_tag'):
            raise Hold('PRODUCT_TAG_REQUIRED', 'The retained delivery has no Commerce product association; repair its manifest before publishing')
        if c.get('product_tag') and (not any(g.get('purpose') == 'tag' and g.get('when') == 'product_tag' for g in recipe['ready']) or not recipe['readback'].get('tag_checks')):
            raise Hold('PRODUCT_TAG_UNSUPPORTED', 'Selected-tag and native-tag readbacks are both required before this adapter can publish a shopping post')
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
                upload_guards = [g for g in self.guards(recipe, c) if g.get('purpose') in {'account', 'destination', 'audience', 'story', 'boost', 'schedule'}]
                self.chrome.upload(name, c, step['locator'], method=step.get('method', 'input'),
                                   preview=step.get('preview'), guards=upload_guards)
            elif op == 'set_checked':
                self.set_checked(name, step['locator'], step['value'], confirmation=step.get('confirmation'))
            elif op == 'photo_alt':
                result = self.photo_alt(name, step)
                atomic_json(self.directory / 'evidence' / (job['id'] + '-alt.json'), {'utc': utc(), 'job_id': job['id'], **result})
            elif op == 'product_tag':
                self.product_tag(name, c, step)
            elif op in {'set_text', 'click', 'assert', 'prepare_upload'}:
                args = {k: v for k, v in step.items() if k not in {'unless', 'dirty', 'if_exists'}}
                self.chrome.call(name, args)
            else:
                raise Hold('WORKFLOW_OPERATION', op)
            self.chrome.checkpoint(name, index + 1, dirty=step.get('dirty', True))
        request = {'op': 'ready', 'job': job['id'], 'mediaSha256': c['media_sha256'],
                   'checks': self.guards(recipe, c), 'submit': render(recipe['submit'], c)}
        ready = self.chrome.call(name, request)
        atomic_json(self.directory / 'evidence' / (job['id'] + '-ready.json'), {'utc': utc(), 'job_id': job['id'], 'ready': ready})
        if c['platform']=='google_business_profile':
            photos=[check['photo'] for check in ready['checks'] if check.get('photo')]
            if len(photos)!=1:raise Hold('GOOGLE_PREPARED_PHOTO_RECEIPT_MISSING')
            atomic_json(self.directory/'evidence'/(job['id']+'-google-photo.json'),
                        {'utc':utc(),'job_id':job['id'],'profile_hash':c['profile_hash'],
                         'media_sha256':c['media_sha256'],'photo':photos[0]})
        return ready

    def close(self):
        self.chrome.close()

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
        if u.scheme == 'https' and u.hostname in {'www.linkedin.com', 'linkedin.com'} and u.path == '/safety/go/':
            return parse_qs(u.query).get('url', [url])[0]
        if u.hostname in {'l.facebook.com', 'lm.facebook.com', 'l.instagram.com'}:
            destination = parse_qs(u.query).get('u', [url])[0]
            parsed = urlparse(destination)
            # Meta appends its click ID to the authored destination. Preserve
            # every authored path and campaign parameter when comparing it.
            query = [(k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True) if k != 'fbclid']
            return urlunparse(parsed._replace(query=urlencode(query)))
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

    @staticmethod
    def canonical_native_url(platform, url):
        if platform == 'facebook' and url.startswith('https://facebook.com/'):
            return 'https://www.facebook.com/' + url[len('https://facebook.com/'):]
        return url

    def finish_composer(self, name, recipe, context, timeout=30):
        deadline = time.monotonic() + timeout
        while True:
            self.chrome.sync_after_submit(name)
            self.chrome.call(name, {'op': 'claim'})
            for step in render(recipe.get('cleanup', []), context):
                if self.chrome.call(name, {'op': 'exists', 'locator': step['locator']})['exists']:
                    self.chrome.call(name, step)
                    self.chrome.sync_after_submit(name)
                    self.chrome.call(name, {'op': 'claim'})
            clean = self.chrome.call(name, {'op': 'clean_state', **render(recipe['clean_state'], context)})
            if clean['clean']:
                self.chrome.checkpoint(name, 0, dirty=False)
                return True
            if time.monotonic() >= deadline:
                return False
            time.sleep(0.5)

    def verify(self, job, native_url=None):
        c = self.context(job)
        if c['platform']=='google_business_profile':
            from google_business import GoogleBusinessProfile
            return GoogleBusinessProfile(self).verify(job,native_url)
        name = c['profile_id']
        recipe = self.settings.workflow(self.settings.profile(name))
        composer = self.chrome.sync_after_submit(name)
        reader = VERIFICATION
        b, _ = self.chrome.bound(reader)
        if native_url is None and c['platform']=='linkedin':
            # LinkedIn's current success notification exposes its native link
            # outside alert/status roles. The generic feed can lag behind it.
            anchor=[{'selector':'a[href]','name':'View post'}]
            try:
                native_url=self.wait_for_post_link(name,anchor,recipe['native_url_pattern'])
            except Hold as error:
                if error.code!='CONTROL_MISSING':raise
        if native_url is None and c['platform']=='instagram' and c.get('product_tag') and recipe['readback'].get('tag_recovery'):
            native_url=self.meta_permalink(c,recipe)
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
                        navigation_pattern = step.get('navigation_pattern')
                        step = {k: v for k, v in step.items() if k != 'navigation_pattern'}
                        if step['op'] == 'wait':
                            self.wait(reader, step['locator'])
                        elif step['op'] in {'set_text', 'click', 'assert'}:
                            self.chrome.call(reader, step)
                        else:
                            raise Hold('RECOVERY_OPERATION_INVALID')
                        if navigation_pattern:
                            self.chrome.sync_expected_navigation(reader, navigation_pattern)
                    result = self.chrome.call(reader, {'op': 'discover', 'pattern': recipe['native_url_pattern'], **recovery['discover']})
                    native_url = result['url']
        if not native_url:
            raise Hold('NATIVE_POST_NOT_FOUND', 'Inspect the platform’s Published inventory and run reconcile with its exact native URL')
        native_url = self.canonical_native_url(c['platform'], native_url)
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
                                                  'author': spec['author'], 'photoSelector': spec['photo_selector'], 'captionSelectors': spec['caption_selectors'],
                                                  **({'linkedinPhotoAlt':c['alt_text']} if c['platform']=='linkedin' else {})})
                break
            except Hold as error:
                if not error.retryable or time.monotonic() >= deadline:
                    raise
                time.sleep(0.3)
        links = self.purchase_links(job, evidence['links'])
        if c.get('product_tag'):
            if spec.get('tag_recovery'):
                evidence['product_tag_readback']=self.verify_product_tag(c,recipe)
            else:
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
            if not self.finish_composer(name, recipe, c):
                evidence['composer_warning'] = 'Native post verified; stale composer retained for inspection'
        except Hold as error:
            evidence['composer_warning'] = str(error)
        evidence.update(job_id=job['id'], profile_hash=c['profile_hash'], verified_utc=utc(), purchase_links=links)
        evidence_path = self.directory / 'evidence' / (job['id'] + '-native-' + digest(evidence)[:12] + '.json')
        atomic_json(evidence_path, evidence)
        self.chrome.checkpoint(reader, 0, dirty=False)
        return {'native_url': native_url, 'caption_verified': True, 'author_verified': True, 'photo_verified': True,
                'media_sha256': c['media_sha256'], 'purchase_links': links, 'verified_utc': utc(),
                **({'product_tag_verified':True,'product_tag_readback':evidence['product_tag_readback']} if c.get('product_tag') else {}),
                'evidence_path': str(evidence_path.resolve()), 'evidence_sha256': digest(evidence_path.read_bytes())}

