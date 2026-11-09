import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from meta_posting import Blocked,Journal,bounded,check_url,preflight,publish_once,reconcile

URL='https://business.facebook.com/latest/composer/?business_id=2380586078685156&asset_id=103781478537396'

class PostingSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        media=self.root/'image.png';media.write_bytes(b'reviewed-test-media')
        self.item=dict(catalogue_id='BSI-TEST',sku='TEST-SKU',caption='A reviewed sculpture caption.',title='Test sculpture',media_path=str(media),sha256=hashlib.sha256(media.read_bytes()).hexdigest())
        self.profile=dict(catalogue_id='BSI-TEST',sku='TEST-SKU',duplicate_search_verified_utc='2026-11-08T00:00:00Z',duplicate_search_result='NO_MATCH',tag_selector='[data-reviewed-tag]',tag_text='Exact selected product',media_selector='[data-reviewed-media]')
        self.journal=Journal(self.root/'journal.jsonl')
    def tearDown(self):self.temp.cleanup()
    def test_wrong_account_refused(self):
        with self.assertRaises(Blocked):check_url(URL.replace('103781478537396','111'))
        with self.assertRaises(Blocked):check_url(URL.replace('business.facebook.com','example.com'))
    def test_outer_timeout_does_not_retry(self):
        calls=[]
        def timeout(*a,**k):calls.append(a);raise subprocess.TimeoutExpired('osascript',9)
        with self.assertRaises(Blocked):bounded(['osascript'],run=timeout)
        self.assertEqual(len(calls),1)
    def test_permission_prompt_blocks_before_browser(self):
        def output(*a,**k):return subprocess.CompletedProcess(a,0,json.dumps(dict(frontmost='com.apple.UserNotificationCenter',accessibilityTrusted=False)),'')
        with self.assertRaisesRegex(Blocked,'permission prompt'):preflight(run=output)
    def test_missing_duplicate_check_blocks(self):
        self.profile.pop('duplicate_search_verified_utc')
        with self.assertRaises(Blocked):publish_once(self.item,URL,self.profile,self.journal,execute=lambda *a: self.fail('browser action'),permission_check=lambda:None)
        self.assertFalse(self.journal.path.exists())
    def test_uncertain_publish_is_never_retried(self):
        calls=[]
        def action(url,op,args):
            calls.append(op)
            if op=='publish':raise Blocked('lost response')
            return dict(status='READY_READBACK',tagText='Exact selected product')
        with self.assertRaises(Blocked):publish_once(self.item,URL,self.profile,self.journal,execute=action,permission_check=lambda:None)
        saved=[json.loads(s) for s in self.journal.path.read_text().splitlines()]
        self.assertEqual([x['kind'] for x in saved],['PUBLISH_INTENT','UNCERTAIN_NEEDS_RECONCILIATION'])
        with self.assertRaises(Blocked):publish_once(self.item,URL,self.profile,self.journal,execute=action,permission_check=lambda:None)
        self.assertEqual(calls,['verifyReady','publish'])
    def test_successful_click_still_requires_native_post_readback(self):
        def action(url,op,args):return dict(status='READY_READBACK' if op=='verifyReady' else 'PUBLISH_CLICKED_UNCONFIRMED',tagText='Exact selected product')
        result=publish_once(self.item,URL,self.profile,self.journal,execute=action,permission_check=lambda:None)
        self.assertEqual(result['status'],'NEEDS_NATIVE_POST_ID_AND_PERMALINK_READBACK')
        self.assertNotIn('"kind": "PUBLISHED"',self.journal.path.read_text())
        permalink='https://www.instagram.com/p/EXAMPLE123/'
        with self.assertRaises(Blocked):reconcile(self.item,URL,permalink,self.journal,execute=lambda *a:dict(text='Different caption',instagramLinks=[dict(href=permalink)]))
        result=reconcile(self.item,URL,permalink,self.journal,execute=lambda *a:dict(text=self.item['caption'],instagramLinks=[dict(href=permalink)]))
        self.assertEqual(result['status'],'PUBLISHED_NATIVE_READBACK')
        with self.journal.locked():
            with self.assertRaises(Blocked):self.journal.may_publish(result.get('item_hash',hashlib.sha256((self.item['catalogue_id']+'\n'+self.item['caption']+'\n'+self.item['sha256']).encode()).hexdigest()))
    def test_changed_media_blocks(self):
        Path(self.item['media_path']).write_bytes(b'changed')
        with self.assertRaises(Blocked):publish_once(self.item,URL,self.profile,self.journal,permission_check=lambda:None)

if __name__=='__main__':unittest.main()
