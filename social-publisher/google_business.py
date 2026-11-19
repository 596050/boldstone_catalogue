"""Google Business Profile native records, without replaying a submission.

Google's standalone manager renders uploaded photographs as SVG images. Its
published inventory supplies the stable location/post IDs and public status;
the saved editor independently supplies the description, photograph and button.
"""
import re
import time
from pathlib import Path
from urllib.parse import urlparse

from common import Hold, atomic_json, digest, read_json, utc
from chrome import VERIFICATION


def norm(value):
    return ' '.join(str(value or '').replace('\u200b', '').replace('\ufeff', '').split())


def record_identity(snapshot, caption_snapshot, status_snapshot, context):
    if norm(caption_snapshot.get('text')) != norm(context['caption']):
        raise Hold('NATIVE_CAPTION_MISMATCH', retryable=True)
    records = re.findall(r'data-post-name="accounts/-/locations/(\d+)/localPosts/(\d+)"', snapshot.get('html', ''))
    if len(records) != 1:
        raise Hold('GOOGLE_POST_ID_AMBIGUOUS')
    location, post_id = records[0]
    if location != context['location_id']:
        raise Hold('WRONG_GOOGLE_BUSINESS_PROFILE')
    lines = [norm(line) for line in status_snapshot.get('text', '').splitlines()]
    if any(re.match(r'^(Pending|Not approved|Rejected|Processing)(?:\b|$)', line, re.I) for line in lines):
        raise Hold('GOOGLE_POST_PENDING_OR_REJECTED', 'Google has not marked this post Published; retain its intent and check its status again', retryable=True)
    status = next((line for line in lines if re.match(r'^Published\b', line)), None)
    if not status:
        raise Hold('GOOGLE_POST_NOT_PUBLISHED', retryable=True)
    return {'location_id': location, 'post_id': post_id, 'status': status}


def saved_details(snapshot, photo_proof, context):
    descriptions = [item for item in snapshot.get('editors', []) if item.get('tag') == 'TEXTAREA' and 'maxlength="1500"' in item.get('html', '')]
    if len(descriptions) != 1 or norm(descriptions[0].get('value')) != norm(context['caption']):
        raise Hold('NATIVE_CAPTION_MISMATCH')
    destinations = [item.get('value') for item in snapshot.get('inputs', []) if 'type="url"' in item.get('html', '')]
    if destinations != [context['purchase_url']]:
        raise Hold('NATIVE_PURCHASE_LINK_MISMATCH')
    if not any(item.get('tag') == 'BUTTON' and item.get('name') == 'Buy' for item in snapshot.get('controls', [])):
        raise Hold('GOOGLE_BUY_BUTTON_MISSING')
    photos = [item['photo'] for item in photo_proof.get('checks', []) if item.get('image') and item.get('photo')]
    if len(photos) != 1 or photos[0].get('input_sha256') != context['media_sha256'] or photos[0].get('width', 0) <= 0 or photos[0].get('height', 0) <= 0:
        raise Hold('NATIVE_PHOTO_MISMATCH')
    return {'photo': photos[0], 'purchase_links': [{'expected': context['purchase_url'], 'native_link': destinations[0], 'method': 'saved native Buy button destination'}]}


class GoogleBusinessProfile:
    def __init__(self, workflow):
        self.workflow = workflow
        self.chrome = workflow.chrome
        self.directory = workflow.directory

    def verify(self, job, native_url=None):
        c = self.workflow.context(job)
        profile = self.workflow.settings.profile(c['profile_id'])
        recipe = self.workflow.settings.workflow(profile)
        reader = VERIFICATION
        self.workflow.settings.check_url(profile, c['inventory_url'])
        binding, _ = self.chrome.bound(reader)
        if binding['url'] != c['inventory_url']:
            self.chrome.navigate(reader, c['inventory_url'], job['id'], recovery=True)
        row = [{'selector': recipe['readback']['row_selector'], 'contains': c['caption']}]
        self.workflow.wait(reader, row, timeout=30)
        snapshot = self.chrome.call(reader, {'op': 'snapshot', 'scope': row, 'includeHTML': True})
        caption = self.chrome.call(reader, {'op': 'snapshot', 'scope': [{'selector': selector, 'text': c['caption']} for selector in recipe['readback']['caption_selectors']]})
        status = self.chrome.call(reader, {'op': 'snapshot', 'scope': [{'selector': recipe['readback']['status_selector'], 'within': {'selector': recipe['readback']['row_selector'], 'contains': c['caption']}}]})
        atomic_json(self.directory/'evidence'/(job['id']+'-google-record.json'), {'utc': utc(), 'job_id': job['id'], 'snapshot': snapshot, 'caption': caption, 'status':status})
        identity = record_identity(snapshot, caption, status, c)
        editor_url = c['inventory_url']+'/'+identity['post_id']+'/edit'
        self.workflow.settings.check_url(profile, editor_url)
        if native_url is not None and native_url != editor_url:
            raise Hold('NATIVE_PERMALINK_INVALID')
        # Full navigation is deliberate: the embedded manager's SPA links can
        # otherwise depend on a parent Google Search frame that is not present.
        self.chrome.navigate(reader, editor_url, job['id'], recovery=True)
        self.workflow.wait(reader, [{'selector': 'textarea[maxlength="1500"]'}], timeout=30)
        photo = self.chrome.confirm_upload_preview(reader, recipe['google_photo'], c)
        detail = self.chrome.call(reader, {'op': 'snapshot', 'fullDocument': True})
        checked = saved_details(detail, photo, c)
        prepared_path = self.directory/'evidence'/(job['id']+'-google-photo.json')
        prepared = read_json(prepared_path)
        if prepared.get('job_id') != job['id'] or prepared.get('media_sha256') != c['media_sha256'] or prepared.get('profile_hash') != c['profile_hash']:
            raise Hold('GOOGLE_PREPARED_PHOTO_RECEIPT_MISSING')
        evidence = {'job_id': job['id'], 'profile_hash': c['profile_hash'], 'verified_utc': utc(),
                    'url': editor_url, 'native_record': identity, 'caption_verified': True,
                    'author_verified': True, 'photo_verified': True,
                    'account_verification_method': 'exact managed Google Business Profile location and native post IDs',
                    'account_name': c['account_name'], 'published_inventory': snapshot,
                    'published_caption': caption, 'published_status':status, 'saved_post': detail,
                    'photo': checked['photo'], 'purchase_links': checked['purchase_links'],
                    'prepared_photo_evidence_path': str(prepared_path.resolve()),
                    'prepared_photo_evidence_sha256': digest(prepared_path.read_bytes())}
        # This form was inspected without changing any field. It is safe to
        # navigate the read-only inspection tab back to its native inventory.
        try:
            self.chrome.navigate(reader, c['inventory_url'], job['id'], recovery=True)
            self.chrome.checkpoint(reader, 0, dirty=False)
        except Hold as error:
            evidence['inspection_warning'] = str(error)
        # A standalone Google composer can retain its values after publishing.
        # Only release a retained form after the independent published record
        # matches those exact values; unexpected user edits stay protected.
        try:
            self.chrome.sync_after_submit(c['profile_id'])
            current = self.chrome.call(c['profile_id'], {'op': 'snapshot', 'fullDocument': True})
            fields = [e for e in current.get('editors', []) if e.get('tag') == 'TEXTAREA']
            if fields:
                if len(fields) != 1 or norm(fields[0].get('value')) != norm(c['caption']):
                    raise Hold('DRAFT_NEEDS_INSPECTION')
                self.chrome.call(c['profile_id'], {'op': 'assert', 'checks': [{'locator': [{'selector': 'input[type=url]'}], 'text': c['purchase_url']}]})
            self.chrome.checkpoint(c['profile_id'], 0, dirty=False)
            self.chrome.navigate(c['profile_id'], c['inventory_url'], job['id'], recovery=True)
        except Hold as error:
            evidence['composer_warning'] = str(error)
        path = self.directory/'evidence'/(job['id']+'-native-'+digest(evidence)[:12]+'.json')
        atomic_json(path, evidence)
        return {'native_url': editor_url, 'native_url_kind': 'Google Business Profile published post record',
                'google_location_id': identity['location_id'], 'google_post_id': identity['post_id'],
                'google_status': identity['status'], 'caption_verified': True, 'author_verified': True,
                'photo_verified': True, 'media_sha256': c['media_sha256'],
                'purchase_links': checked['purchase_links'], 'verified_utc': evidence['verified_utc'],
                'evidence_path': str(path.resolve()), 'evidence_sha256': digest(path.read_bytes())}
