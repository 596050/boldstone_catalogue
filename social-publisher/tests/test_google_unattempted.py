import copy,sys,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from common import Hold,atomic_json,digest
from google_business import GoogleBusinessProfile,unattempted_document,unattempted_reconciliation_base
from journal import Store
class OriginalDocumentChecks(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.directory=Path(self.temp.name);(self.directory/'evidence').mkdir()
  self.c={'id':'one','profile_id':'fixture','platform':'google_business_profile','profile_hash':'profile','media_type':'video/mp4','media_sha256':'a'*64,'caption':'Archive film','location_id':'123','compose_url':'https://www.google.com/local/business/123/promote/updates/add','inventory_url':'https://www.google.com/local/business/123/promote/updates'}
  self.upload={'same_job':True,'committed':True,'sha256':'a'*64,'document_job':'one','document_url':self.c['compose_url'],'submission_marker':None}
  self.media={'src':'blob:https://www.google.com/original-document','input_sha256':'a'*64,'width':720,'height':720,'duration':20,'media_type':'video/mp4'}
  self.prepared={'job_id':'one','profile_hash':'profile','media_sha256':'a'*64,'video':self.media};self.ready={'checks':[{'video':self.media}]}
  atomic_json(self.directory/'evidence/one-google-video.json',self.prepared)
 def test_the_intact_original_blob_and_absent_marker_prove_no_click_in_this_document(self):
  self.assertTrue(unattempted_document(self.upload,self.prepared,self.ready,self.c)['submission_marker_absent'])
 def test_clicked_reloaded_foreign_and_uncommitted_documents_cannot_resume(self):
  for field,value in [('submission_marker','attempted'),('document_job','other'),('same_job',False),('committed',False),('sha256','b'*64),('document_url',self.c['inventory_url'])]:
   with self.assertRaises(Hold):unattempted_document({**self.upload,field:value},self.prepared,self.ready,self.c)
  ready=copy.deepcopy(self.ready);ready['checks'][0]['video']['src']='blob:https://www.google.com/new-document'
  with self.assertRaises(Hold):unattempted_document(self.upload,self.prepared,ready,self.c)
 def test_another_prepared_job_profile_or_input_hash_cannot_resume(self):
  for field,value in [('job_id','other'),('profile_hash','other'),('media_sha256','b'*64)]:
   with self.assertRaises(Hold):unattempted_document(self.upload,{**self.prepared,field:value},self.ready,self.c)
 def adapter(self,present,more=False):
  self.events=[];self.submissions=[];self.state=[]
  def call(name,r):
   if r['op']=='upload_status':return self.upload
   if r['op']=='ready':return self.ready
   if r['op']=='probe':return {'googlePostRecordNames':['accounts/-/locations/123/localPosts/456']}
   if r['op']=='exists':return {'exists':more if r['locator'][0].get('name')=='More posts' else present}
   if r['op']=='snapshot':return {'text':'Your posts'}
   raise AssertionError(r['op'])
  chrome=SimpleNamespace(bound=lambda *a,**k:({'job_id':'one','url':self.c['compose_url'],'profile_hash':'profile'},{}),call=call,navigate=lambda *a,**k:None)
  settings=SimpleNamespace(profile=lambda _: {},workflow=lambda _: {'readback':{'row_selector':'.record'},'submit':[{'selector':'button','name':'Post'}]},policy={})
  workflow=SimpleNamespace(chrome=chrome,directory=self.directory,settings=settings,context=lambda _:self.c,guards=lambda *a:[],wait=lambda *a,**k:None,submit=lambda _:self.submissions.append('first actual Post'))
  adapter=GoogleBusinessProfile(workflow)
  def find(*a):
   if not present:raise Hold('CONTROL_MISSING')
  adapter.find_inventory_record=find
  event={'kind':'PUBLISH_INTENT','job':{'id':'one'},'sha256':'f'*64}
  store=SimpleNamespace(has_intent=lambda _:True,ledger=[event],event=lambda kind,**kw:self.events.append((kind,kw)),change=lambda *a:self.state.append(a),export=lambda:None,backup=lambda:None)
  return adapter,store,{'id':'one','state':'OUTCOME_UNKNOWN'}
 def test_an_existing_native_record_blocks_the_resume_before_any_publication(self):
  adapter,store,job=self.adapter(True)
  with self.assertRaises(Hold) as caught:adapter.resume_unattempted(store,job)
  self.assertEqual(caught.exception.code,'GOOGLE_POST_ALREADY_PRESENT');self.assertFalse(self.events);self.assertFalse(self.submissions)
 def test_resume_keeps_one_original_intent_and_records_its_proof_before_the_first_click(self):
  adapter,store,job=self.adapter(False)
  with patch('engine.Engine.reconcile',return_value={'verified':True}):adapter.resume_unattempted(store,job)
  self.assertEqual(self.submissions,['first actual Post']);self.assertEqual([kind for kind,_ in self.events],['GOOGLE_UNATTEMPTED_SUBMISSION_RESUME_INTENT']);self.assertEqual(sum(e['kind']=='PUBLISH_INTENT' for e in store.ledger),1)
  self.assertTrue((self.directory/'evidence/one-unattempted-document-resume.json').exists())
 def test_unclicked_document_does_not_claim_a_partial_inventory_is_complete(self):
  import json
  adapter,store,job=self.adapter(False,more=True)
  with patch('engine.Engine.reconcile',return_value={'verified':True}):adapter.resume_unattempted(store,job)
  proof=json.loads((self.directory/'evidence/one-unattempted-document-resume.json').read_text())
  self.assertEqual(self.submissions,['first actual Post']);self.assertTrue(proof['inventory_more_posts_control_present']);self.assertTrue(proof['loaded_inventory_caption_absent']);self.assertNotIn('inventory_exhausted',proof)
  self.assertNotIn('inventory_caption_absent',proof)
 def test_an_unloaded_inventory_cannot_resume_the_original_document(self):
  adapter,store,job=self.adapter(False);original=adapter.chrome.call
  adapter.chrome.call=lambda name,r:{'googlePostRecordNames':[]} if r['op']=='probe' else original(name,r)
  with patch('google_business.time.monotonic',side_effect=[0,31]):
   with self.assertRaises(Hold) as caught:adapter.resume_unattempted(store,job)
  self.assertEqual(caught.exception.code,'GOOGLE_INVENTORY_NOT_LOADED');self.assertFalse(self.events);self.assertFalse(self.submissions)
 def verification_budget_proof(self,base=12,original_hash=None):
  ledger=Store.__new__(Store);ledger.directory=self.directory;ledger.ledger_path=self.directory/'intent-ledger.jsonl';ledger.ledger=[]
  intent=ledger.event('PUBLISH_INTENT',job={'id':'one'})
  path=self.directory/'evidence/one-unattempted-document-resume.json'
  atomic_json(path,{'job_id':'one','profile_hash':'profile','media_sha256':'a'*64,'native_url':self.c['compose_url'],'original_publish_intent_sha256':original_hash or intent['sha256'],'verification_attempts_before_resume':base})
  ledger.event('GOOGLE_UNATTEMPTED_SUBMISSION_RESUME_INTENT',job_id='one',evidence_path=str(path.resolve()),evidence_sha256=digest(path.read_bytes()))
  return path
 def test_only_a_ledger_bound_first_click_proof_creates_a_new_readback_budget(self):
  self.assertEqual(unattempted_reconciliation_base(self.c,self.directory),0)
  self.verification_budget_proof();self.assertEqual(unattempted_reconciliation_base(self.c,self.directory),12)
 def test_a_changed_resume_proof_cannot_extend_its_verification_budget(self):
  import json
  path=self.verification_budget_proof();proof=json.loads(path.read_text());proof['verification_attempts_before_resume']=999;atomic_json(path,proof)
  with self.assertRaises(Hold):unattempted_reconciliation_base(self.c,self.directory)
 def test_a_resume_without_its_original_intent_cannot_create_a_readback_budget(self):
  self.verification_budget_proof(original_hash='f'*64)
  with self.assertRaises(Hold):unattempted_reconciliation_base(self.c,self.directory)
 def test_video_evidence_can_use_the_same_bound_main_intent_ledger(self):
  runtime=self.directory/'runtime';state=runtime/'state';state.mkdir(parents=True);video=self.directory/'video';(video/'evidence').mkdir(parents=True)
  ledger=Store.__new__(Store);ledger.directory=state;ledger.ledger_path=state/'intent-ledger.jsonl';ledger.ledger=[];intent=ledger.event('PUBLISH_INTENT',job={'id':'one'})
  path=video/'evidence/one-unattempted-document-resume.json';atomic_json(path,{'job_id':'one','profile_hash':'profile','media_sha256':'a'*64,'native_url':self.c['compose_url'],'original_publish_intent_sha256':intent['sha256'],'intent_ledger_path':str(ledger.ledger_path.resolve()),'verification_attempts_before_resume':9})
  ledger.event('GOOGLE_UNATTEMPTED_SUBMISSION_RESUME_INTENT',job_id='one',evidence_path=str(path.resolve()),evidence_sha256=digest(path.read_bytes()))
  with patch('common.ROOT',runtime):self.assertEqual(unattempted_reconciliation_base(self.c,video),9)
if __name__=='__main__':unittest.main()
