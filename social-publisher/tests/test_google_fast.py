import copy,json,subprocess,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from chrome import Chrome
from common import Hold,atomic_json
from google_fast import GoogleFastChrome
from settings import Settings

class GoogleFastChecks(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.directory=Path(self.temp.name)
  self.settings=Settings();self.url=self.settings.profile('boldstone_google_business_profile')['compose_url']
  self.binding={'window_id':1,'tab_id':2,'url':self.url,'owner':'owner','profile_hash':self.settings.fingerprint('boldstone_google_business_profile')}
  atomic_json(self.directory/'bindings.json',{'boldstone_google_business_profile':self.binding})
  self.stamp={'frontmost':'com.apple.Terminal','front_window_id':9,'active_tabs':{'1':2},'tab_url':self.url}
  self.envelope={'result_json':json.dumps({'ok':True,'claimed':True}),'before':self.stamp,'after':self.stamp}
  self.calls=[]
  def execute(args,**kwargs):
   self.calls.append(args)
   return SimpleNamespace(returncode=0,stdout=json.dumps(self.envelope),stderr='')
  self.chrome=GoogleFastChrome(self.settings,self.directory,execute=execute)

 def test_post_and_validation_corrections_always_use_the_standard_publishing_guard(self):
  with patch.object(Chrome,'call',return_value={'standard':True}) as original:
   for op in ['submit','submit_google_validation_correction','submit_google_rejected_revision']:
    self.assertTrue(self.chrome.call('boldstone_google_business_profile',{'op':op})['standard'])
   self.assertEqual(original.call_count,3)
  self.assertFalse(self.calls)

 def test_preparation_carries_an_owned_exact_url_and_records_its_native_audit(self):
  self.assertTrue(self.chrome.call('boldstone_google_business_profile',{'op':'claim'})['claimed'])
  self.assertEqual(len(self.calls),1);self.assertTrue(self.calls[0][1].endswith('google-fast.applescript'))
  self.assertEqual(self.calls[0][2:5],['1','2',self.url])
  rows=[json.loads(line) for line in (self.directory/'focus-audit.jsonl').read_text().splitlines()]
  self.assertTrue(rows[0]['target_remained_background']);self.assertEqual(rows[0]['operation'],'claim')
  self.assertFalse(list(self.directory.glob('.google-dom-*.js')))

 def test_readonly_inspection_keeps_the_standard_exact_url_and_normal_window_check(self):
  with patch.object(self.chrome,'evaluate',return_value={'ok':True}) as evaluate:
   self.chrome.call('boldstone_google_business_profile',{'op':'snapshot'})
   self.assertTrue(evaluate.call_args.kwargs['readonly']);self.assertEqual(evaluate.call_args.args[0],self.binding)
  self.assertFalse(self.calls)

 def test_non_google_routes_fall_back_without_using_the_compact_bridge(self):
  self.chrome.bindings['boldstone_google_business_profile']['url']='https://www.google.com/search?q=Boldstone'
  with patch.object(Chrome,'call',return_value={'standard':True}) as original:
   self.assertTrue(self.chrome.call('boldstone_google_business_profile',{'op':'claim'})['standard'])
   original.assert_called_once()
  self.assertFalse(self.calls)

 def test_a_foreground_change_is_recorded_and_holds_the_owned_draft(self):
  self.envelope['after']={**self.stamp,'frontmost':'com.google.Chrome','front_window_id':1}
  with self.assertRaises(Hold) as caught:self.chrome.call('boldstone_google_business_profile',{'op':'claim'})
  self.assertEqual(caught.exception.code,'FOCUS_CHANGED_PAUSED')
  self.assertFalse(json.loads((self.directory/'focus-audit.jsonl').read_text())['target_remained_background'])

 def test_native_refusal_is_not_retried(self):
  self.chrome.execute=lambda *args,**kwargs:SimpleNamespace(returncode=1,stdout='',stderr='FOREGROUND_TAB_PAUSED')
  with self.assertRaises(Hold) as caught:self.chrome.call('boldstone_google_business_profile',{'op':'claim'})
  self.assertEqual(caught.exception.code,'FOREGROUND_TAB_PAUSED')

 def test_missing_native_audit_fields_cannot_report_success(self):
  self.envelope['after']={**self.stamp,'active_tabs':{}}
  with self.assertRaises(Hold) as caught:self.chrome.call('boldstone_google_business_profile',{'op':'claim'})
  self.assertEqual(caught.exception.code,'DOM_RESPONSE_INVALID')

 def test_native_decimal_id_strings_are_normalized_without_losing_the_target(self):
  self.envelope['before']={**self.stamp,'front_window_id':'9','active_tabs':{'1':'2'}}
  self.envelope['after']={**self.stamp,'front_window_id':'9','active_tabs':{'1':'2'}}
  self.assertTrue(self.chrome.call('boldstone_google_business_profile',{'op':'claim'})['claimed'])

 def test_native_dom_errors_still_record_the_focus_audit(self):
  self.envelope['result_json']=json.dumps({'ok':False,'code':'CONTROL_MISSING'})
  with self.assertRaises(Hold) as caught:self.chrome.call('boldstone_google_business_profile',{'op':'claim'})
  self.assertEqual(caught.exception.code,'CONTROL_MISSING');self.assertTrue(caught.exception.retryable)
  self.assertTrue((self.directory/'focus-audit.jsonl').exists())

if __name__=='__main__':unittest.main()
