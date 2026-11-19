"""Validate immutable job manifests and editable platform/account settings."""
import mimetypes
import re
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from common import ROOT, Hold, digest, read_json


class Settings:
    def __init__(self, path=None):
        self.path = Path(path or ROOT / 'profiles.json').resolve()
        self.data = read_json(self.path)
        self.config_sha256 = digest(self.data)
        if self.data.get('schema_version') != 1:
            raise Hold('CONFIG_VERSION', 'Expected profiles schema_version 1')
        self.profiles = self.data['profiles']
        self.policy = self.data['policy']
        if self.policy.get('create_tabs') is not False or self.policy.get('require_background_tab') is not True:
            raise Hold('FOCUS_POLICY', 'This runner requires reserved background tabs and create_tabs=false')
        channels = []
        for name, p in self.profiles.items():
            for key in ['platform', 'channel_key', 'account_name', 'allowed_hosts', 'compose_url', 'inventory_url', 'workflow']:
                if not p.get(key):
                    raise Hold('CONFIG_INCOMPLETE', name + ': ' + key)
            if not re.fullmatch(r'[a-z][a-z0-9_-]*', name):
                raise Hold('PROFILE_NAME', name)
            for key in ['compose_url', 'inventory_url']:
                self.check_url(p, p[key])
            self.workflow(p)
            channels.append(p['channel_key'])
        if len(channels) != len(set(channels)):
            raise Hold('DUPLICATE_CHANNEL', 'Each profile must have a distinct stable channel_key')

    def profile(self, name):
        self.check_current()
        if name not in self.profiles:
            raise Hold('UNKNOWN_PROFILE', name)
        return self.profiles[name]

    def check_current(self):
        try:
            current = digest(read_json(self.path))
        except (OSError, ValueError):
            raise Hold('CONFIG_UNAVAILABLE', 'The account configuration is unavailable or incomplete')
        if current != self.config_sha256:
            raise Hold('CONFIG_CHANGED', 'The account configuration changed during this run; reload before continuing')

    def workflow(self, profile):
        path = (self.path.parent / profile['workflow']).resolve()
        if not path.is_relative_to(self.path.parent):
            raise Hold('WORKFLOW_PATH', 'Workflows must be inside the configuration directory')
        recipe = read_json(path)
        if recipe.get('schema_version') != 1:
            raise Hold('WORKFLOW_VERSION')
        if not recipe.get('ready') or not recipe.get('readback') or not recipe.get('submit') or not recipe.get('clean_state'):
            raise Hold('WORKFLOW_INCOMPLETE', str(path))
        if not recipe['readback'].get('caption_selectors'):
            raise Hold('CAPTION_SCOPE_MISSING', 'Native readback needs the post caption scope, excluding comments')
        guards = recipe['ready']
        if not any(g.get('purpose') == 'account' for g in guards) or not any(g.get('purpose') == 'caption' and g.get('text') == '$caption' for g in guards) or not any(g.get('purpose') == 'photo' and g.get('image') is True for g in guards):
            raise Hold('WORKFLOW_GUARDS_MISSING', 'Every workflow needs account, complete caption and photograph guards')
        return recipe

    def fingerprint(self, name):
        p = self.profile(name)
        return digest({'profile': p, 'workflow': self.workflow(p)})

    @staticmethod
    def check_url(profile, url, allow_blank=False):
        if allow_blank and url == 'about:blank':
            return
        u = urlparse(url)
        if u.scheme != 'https' or u.hostname not in profile['allowed_hosts'] or u.username or u.password or u.port not in (None, 443):
            raise Hold('WRONG_DESTINATION', 'URL is outside the configured HTTPS origins')
        if profile.get('platform')=='google_business_profile':
            location_id=profile.get('location_id','')
            if not re.fullmatch(r'\d+',location_id):
                raise Hold('GOOGLE_PROFILE_CONFIG','A verified numeric location_id is required')
            if u.hostname!='www.google.com' or not u.path.startswith('/local/business/'+location_id+'/'):
                raise Hold('WRONG_GOOGLE_BUSINESS_PROFILE','The native URL belongs to a different Google Business Profile')
        # Account IDs must match even if the visible name happens to match.
        if u.hostname == 'business.facebook.com':
            q = parse_qs(u.query)
            for key in ['business_id', 'asset_id']:
                wanted = profile.get(key)
                if wanted and q.get(key) != [wanted]:
                    raise Hold('WRONG_META_ACCOUNT', key + ' differs from the configured destination')
        if re.search(r'/(?:checkpoint|challenge|login|accounts/login|authwall)(?:/|$)', u.path):
            raise Hold('ACCOUNT_ACTION_REQUIRED', 'The platform requires account access to be restored')

    def jobs(self, manifest_path):
        path = Path(manifest_path).resolve()
        m = read_json(path)
        if not isinstance(m, dict) or m.get('schema_version') != 1 or not m.get('batch_id') or not isinstance(m.get('posts'), list) or not m['posts']:
            raise Hold('MANIFEST_SCHEMA', 'Expected schema_version, batch_id and a nonempty posts list')
        if m.get('publish_authorized') is not True:
            raise Hold('MANIFEST_NOT_AUTHORIZED', 'Set publish_authorized=true only for the exact batch you intend to publish')
        result = []
        seen_keys, seen_content = set(), set()
        for post in m['posts']:
            if post.get('publications') or str(post.get('status', '')).startswith(('PUBLISHED', 'COMPLETE')):
                raise Hold('ALREADY_PUBLISHED_MANIFEST', 'Import historical receipts; do not enqueue this post')
            if not post.get('post_key') or not post.get('title') or not post.get('alt_text') or not post.get('targets'):
                raise Hold('POST_INCOMPLETE', 'Each post needs post_key, title, alt_text and targets')
            media = Path(post['media_path']).expanduser()
            if not media.is_absolute():
                media = path.parent / media
            media = media.resolve()
            if not media.is_file():
                raise Hold('MEDIA_MISSING', str(media))
            sha = digest(media.read_bytes())
            if sha != post.get('sha256'):
                raise Hold('MEDIA_HASH_CHANGED', post['title'])
            mime = mimetypes.guess_type(str(media))[0]
            if mime not in ['image/png', 'image/jpeg'] or media.stat().st_size > self.policy['max_media_bytes']:
                raise Hold('MEDIA_FORMAT', 'Use a PNG or JPEG within max_media_bytes')
            for name, target in post['targets'].items():
                p = self.profile(name)
                if media.stat().st_size>p.get('max_media_bytes',self.policy['max_media_bytes']):
                    raise Hold('MEDIA_FORMAT','The photo exceeds this platform profile\u2019s media size limit')
                if p['platform']=='google_business_profile':
                    destination=urlparse(target.get('purchase_url') or '')
                    hosts=p.get('purchase_allowed_hosts') or [urlparse(p.get('website_url','')).hostname]
                    if destination.scheme!='https' or destination.hostname not in hosts or destination.username or destination.password:
                        raise Hold('GOOGLE_PURCHASE_URL_REQUIRED','Google posts require an exact HTTPS product button destination on a configured purchase host')
                caption = target.get('caption', '')
                if not isinstance(caption, str) or not caption.strip() or len(caption) > p.get('caption_limit', 60000):
                    raise Hold('CAPTION_INVALID', name)
                if self.policy.get('require_meta_product_tags') and p['platform'] in {'facebook', 'instagram'} and not target.get('product_tag'):
                    raise Hold('PRODUCT_TAG_REQUIRED', 'Meta publications require the exact Commerce product and price; caption links and bio links do not satisfy this requirement')
                if 'product tag' in caption.lower() and not target.get('product_tag'):
                    raise Hold('PRODUCT_TAG_REQUIRED', 'The caption promises a product tag; supply the exact native tag and price')
                if target.get('product_tag'):
                    tag = target['product_tag']
                    if not tag.get('name') or not tag.get('price_text'):
                        raise Hold('PRODUCT_TAG_INCOMPLETE')
                    recipe = self.workflow(p)
                    if not any(g.get('purpose') == 'tag' and g.get('when') == 'product_tag' for g in recipe['ready']) or not recipe['readback'].get('tag_checks'):
                        raise Hold('PRODUCT_TAG_UNSUPPORTED', 'This adapter needs both selected-tag and native-tag checks')
                channel = p['channel_key']
                key = (channel, str(post['post_key']))
                content = digest({'caption': caption, 'media_sha256': sha})
                if key in seen_keys or (channel, content) in seen_content:
                    raise Hold('DUPLICATE_IN_MANIFEST', name + ': ' + post['post_key'])
                seen_keys.add(key)
                seen_content.add((channel, content))
                payload = {'batch_id': m['batch_id'], 'post_key': str(post['post_key']), 'title': post['title'],
                           'catalogue_id': post.get('catalogue_id', post['post_key']), 'sku': post.get('sku'),
                           'media_path': str(media), 'media_sha256': sha, 'media_type': mime,
                           'alt_text': post['alt_text'], 'caption': caption, 'product_tag': target.get('product_tag'),
                           'profile_id': name, 'profile_hash': self.fingerprint(name), 'channel_key': channel,
                           'profile_snapshot': p, 'workflow_snapshot': self.workflow(p),
                           'platform': p['platform'], 'purchase_url': target.get('purchase_url'),
                           'manifest_path': str(path)}
                result.append({'id': digest([channel, post['post_key']])[:32], 'channel_key': channel,
                               'post_key': str(post['post_key']), 'content_hash': content, 'payload': payload})
        return result

