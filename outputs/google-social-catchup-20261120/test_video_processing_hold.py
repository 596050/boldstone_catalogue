"""Guard tests for retaining a native processing record without claiming publication."""
import contextlib,copy,io,json,sys,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
OUT=Path(__file__).parent;sys.path[:0]=[str(OUT),str(OUT.parents[1]/'social-publisher')]
import hold_google_unpublished as module
from common import Hold,atomic_json,digest
PLACEHOLDER=(OUT/'google-apollo-native-pending-card-poster.jpg').read_bytes()
class ProcessingHoldChecks(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.folder=Path(self.temp.name);(self.folder/'evidence').mkdir()
  self.c={'id':'one','profile_id':'writer','profile_hash':'profile','media_type':'video/mp4','media_sha256':'a'*64,'caption':'Archive sculpture film','purchase_url':'https://boldstonesculpture.com/','button_label':'Learn more','location_id':'123','inventory_url':'https://www.google.com/local/business/123/promote/updates','compose_url':'https://www.google.com/local/business/123/promote/updates/add'}
  c=self.c;self.clicks=[];self.events=[];self.status='Pending';self.other_photo=False;self.url=c['purchase_url'];self.upload_hash='a'*64
  self.job={'id':'one','state':'OUTCOME_UNKNOWN','post_key':'film'}
  self.store=SimpleNamespace(get=lambda _:self.job,has_intent=lambda _:True,event=lambda kind,**kwargs:self.events.append((kind,kwargs)),export=lambda:None,backup=lambda:None)
  self.recipe={'google_video':{'locator':[{'selector':'main video'}],'video':True,'duration':3,'width':720,'height':1280},'clean_state':{}}
  self.settings=SimpleNamespace(workflow=lambda _:self.recipe,profile=lambda _:{})
  self.chrome=SimpleNamespace(directory=self.folder,bindings={'writer':{'job_id':'one','url':c['compose_url'],'dirty':True},'verification':{'url':c['inventory_url']}},navigate=self.navigate,call=self.call,checkpoint=lambda *a,**k:None,confirm_upload_preview=self.preview)
  atomic_json(self.folder/'evidence/one-google-video.json',{'job_id':'one','profile_hash':'profile','media_sha256':'a'*64,'video':{'input_sha256':'a'*64,'duration':3,'width':720,'height':1280}})
 def navigate(self,name,url,*args,**kwargs):self.chrome.bindings[name]['url']=url
 def preview(self,name,*args):
  if name=='verification':raise Hold('UPLOAD_PREVIEW_NOT_CONFIRMED')
  return {'loaded':True}
 def call(self,name,r):
  op=r['op']
  if op=='snapshot':
   scope=r.get('scope',[{}])[0].get('selector','')
   if scope=='div.J7elmb':return {'text':self.c['caption'],'html':'<div data-post-name="accounts/-/locations/123/localPosts/456" style="background-image: url(https://lh3.googleusercontent.com/p/processing)"></div>'}
   if scope=='div.XNfYrb':return {'text':self.c['caption']}
   if scope=='div.WeJbRc':return {'text':self.status}
   return {'editors':[{'tag':'TEXTAREA','html':'<textarea maxlength="1500">','value':self.c['caption']}],'inputs':[{'html':'<input type="url">','value':self.url}],'controls':[{'tag':'BUTTON','name':'Learn more'}],'videos':[]}
  if op=='exists':return {'exists':True if r['locator'][0].get('selector')=='div.J7elmb' else self.other_photo}
  if op=='upload_status':return {'committed':True,'sha256':self.upload_hash}
  if op=='click':self.clicks.append(r['locator'][0]['name']);return {'ok':True}
  if op=='clean_state':return {'clean':True}
  if op in {'assert','set_text'}:return {'ok':True}
  raise AssertionError(op)
 def run_hold(self,raw=PLACEHOLDER):
  with patch.object(module,'OUT',self.folder),patch.object(module,'Workflow',lambda *args:SimpleNamespace(context=lambda _:self.c,chrome=self.chrome,directory=self.folder,wait=lambda *a,**k:None)),patch('urllib.request.urlopen',return_value=io.BytesIO(raw)),contextlib.redirect_stdout(io.StringIO()):
   return module.hold_unpublished(self.store,self.settings,self.chrome,'one')
 def test_video_only_recipe_can_hold_pending_record_without_loaded_media_or_publication_claim(self):
  hold=self.run_hold();proof=json.loads(Path(hold['proof_path']).read_text())
  self.assertEqual(self.clicks,['Delete video']);self.assertFalse(proof['published']);self.assertFalse(proof['video_processing']['loaded_saved_video_verified']);self.assertIsNone(proof['loaded_media']);self.assertEqual(self.job['state'],'OUTCOME_UNKNOWN')
  self.assertEqual(hold['native_post_id'],'456');self.assertEqual(digest(Path(hold['proof_path']).read_bytes()),hold['proof_sha256']);self.assertFalse(any(k=='PUBLISHED' for k,_ in self.events))
 def test_published_caption_with_processing_placeholder_still_cannot_claim_verified_video(self):
  self.status='Published 10 minutes ago';hold=self.run_hold();self.assertIn('not fully verified',hold['reason']);self.assertEqual(self.job['state'],'OUTCOME_UNKNOWN')
 def test_unknown_placeholder_cannot_release_the_original_upload(self):
  with self.assertRaises(AssertionError):self.run_hold(b'not the inspected processing image')
  self.assertFalse(self.clicks)
 def test_different_saved_action_or_existing_photo_cannot_release_the_video_form(self):
  self.url='https://example.com/'
  with self.assertRaises(Hold):self.run_hold()
  self.assertFalse(self.clicks);self.url=self.c['purchase_url'];self.other_photo=True
  with self.assertRaises(AssertionError):self.run_hold()
  self.assertFalse(self.clicks)
 def test_an_original_upload_hash_mismatch_cannot_release_the_form(self):
  self.upload_hash='b'*64
  with self.assertRaises(AssertionError):self.run_hold()
  self.assertFalse(self.clicks)
if __name__=='__main__':unittest.main()
