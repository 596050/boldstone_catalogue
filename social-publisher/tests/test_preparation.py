import copy
import json
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from common import Hold,atomic_json,digest
from journal import Store
from preparation import PreparationOnlyChrome,prepare_manifest
from settings import Settings
from workflow import Workflow
from publisher import main

class DraftChrome(PreparationOnlyChrome):
    binds=[]
    def __init__(self,settings,directory):
        self.bindings={};self.directory=Path(directory);self.directory.mkdir(parents=True,exist_ok=True)
    def bind(self,role,window_id,tab_id):
        self.binds.append((role,tab_id));self.bindings[role]={'window_id':window_id,'tab_id':tab_id}
    def close(self):pass

class DraftWorkflow:
    prepared=[]
    def __init__(self,settings,chrome,directory):self.chrome=chrome
    def prepare(self,job):self.prepared.append(job['id']);return {'ok':True,'submitLabel':'Post'}

class PreparationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.settings=Settings();self.media=self.root/'photo.png';self.media.write_bytes(b'fixture-original')
        self.manifest=self.root/'batch.json';self.plan=self.root/'tabs.json';self.state=self.root/'state'
        self.source={'schema_version':1,'batch_id':'draft-fixture','publish_authorized':False,'posts':[
            {'post_key':'BSI-A','title':'Relief A','alt_text':'Pale relief','media_path':str(self.media),
             'sha256':digest(self.media.read_bytes()),'targets':{'boldstone_threads':{'caption':'Relief A'}}}]}
        self.tabs={'schema_version':1,'verification':{'window_id':1,'tab_id':90},'bindings':[
            {'profile_id':'boldstone_threads','post_key':'BSI-A','window_id':1,'tab_id':10}]}
        atomic_json(self.manifest,self.source);atomic_json(self.plan,self.tabs)
        DraftChrome.binds=[];DraftWorkflow.prepared=[]
    def prepare(self,store,workflow=DraftWorkflow):
        return prepare_manifest(self.settings,store,self.state,self.manifest,self.plan,
                                chrome_factory=DraftChrome,workflow_factory=workflow)
    def test_unapproved_manifest_prepares_without_outbox_or_intent_and_publish_stays_blocked(self):
        with self.assertRaisesRegex(Hold,'publish_authorized'):self.settings.jobs(self.manifest)
        with Store(self.state) as store:
            result=self.prepare(store)
            self.assertEqual(result['prepared'],1);self.assertEqual(store.jobs(),[]);self.assertEqual(store.ledger,[])
            self.assertEqual(result['publish_intents_written'],0)
        with Store(self.state) as store:self.assertEqual(store.jobs(),[])
        self.assertFalse(json.loads(self.manifest.read_text())['publish_authorized'])
    def test_prepare_transport_blocks_both_submit_and_direct_publication_clicks(self):
        c=DraftChrome(self.settings,self.root/'chrome')
        for request in [{'op':'submit'},{'op':'submit_google_validation_correction'},
                        {'op':'click','locator':[{'selector':'button','name':'Post'}]},
                        {'op':'click','locator':{'selector':'[role=button]','name':'Publish'}}]:
            with self.subTest(request=request),self.assertRaisesRegex(Hold,'cannot'):c.call('boldstone_threads',request)
    def test_authorized_manifest_still_cannot_publish_in_preparation_mode(self):
        self.source['publish_authorized']=True;atomic_json(self.manifest,self.source)
        with Store(self.state) as store:
            result=self.prepare(store)
            self.assertTrue(result['complete']);self.assertEqual(store.ledger,[]);self.assertEqual(store.jobs(),[])
    def test_run_prepare_only_dispatches_without_entering_the_publishing_engine(self):
        with patch('preparation.prepare_manifest',return_value={'complete':True,'publish_clicks':0}) as prepare,patch('publisher.Engine') as engine:
            result,code=main(['--state',str(self.state),'run','--prepare-only','--manifest',str(self.manifest),'--tabs',str(self.plan)])
            self.assertEqual(code,0);self.assertEqual(result['publish_clicks'],0)
            prepare.assert_called_once();engine.assert_not_called()
    def test_buggy_workflow_cannot_publish_and_is_reported_held(self):
        class BadWorkflow(DraftWorkflow):
            def prepare(self,job):return self.chrome.call('boldstone_threads',{'op':'submit'})
        with Store(self.state) as store:
            result=self.prepare(store,BadWorkflow)
            self.assertEqual(result['held'],1);self.assertEqual(result['drafts'][0]['code'],'PREPARATION_ONLY')
            self.assertEqual(store.ledger,[]);self.assertEqual(store.jobs(),[])
    def test_reused_tab_is_rejected_before_any_draft_is_changed(self):
        second=copy.deepcopy(self.source['posts'][0]);second['post_key']='BSI-B';second['targets']['boldstone_threads']['caption']='Relief B'
        self.source['posts'].append(second);self.tabs['bindings'].append({**self.tabs['bindings'][0],'post_key':'BSI-B'})
        atomic_json(self.manifest,self.source);atomic_json(self.plan,self.tabs)
        with Store(self.state) as store,self.assertRaisesRegex(Hold,'own reserved tab'):self.prepare(store)
        self.assertEqual(DraftChrome.binds,[]);self.assertEqual(DraftWorkflow.prepared,[])
    def test_existing_outbox_intent_is_never_reprepared(self):
        jobs=self.settings.jobs(self.manifest,require_authorized=False)
        with Store(self.state) as store:
            store.enqueue(jobs);store.change(jobs[0]['id'],'READY');store.intent(jobs[0]['id'])
            with self.assertRaisesRegex(Hold,'existing delivery'):self.prepare(store)
            self.assertEqual(len(store.ledger),1);self.assertEqual(store.get(jobs[0]['id'])['state'],'SUBMITTING')
        self.assertEqual(DraftWorkflow.prepared,[])
    def test_prepare_still_checks_media_hash_and_threads_limit(self):
        self.media.write_bytes(b'changed')
        with self.assertRaises(Hold):self.settings.jobs(self.manifest,require_authorized=False)
        self.source['posts'][0]['sha256']=digest(self.media.read_bytes());self.source['posts'][0]['targets']['boldstone_threads']['caption']='x'*501
        atomic_json(self.manifest,self.source)
        with self.assertRaises(Hold):self.settings.jobs(self.manifest,require_authorized=False)
    def test_preexisting_unowned_draft_is_not_navigated_or_overwritten(self):
        class OccupiedChrome(DraftChrome):
            def bind(self,role,window_id,tab_id):
                super().bind(role,window_id,tab_id)
                self.bindings[role]['url']='https://www.threads.com/'
            def call(self,name,request):
                if request['op']!='clean_state':raise AssertionError('Unexpected browser write')
                return {'clean':False}
        with Store(self.state) as store:
            result=prepare_manifest(self.settings,store,self.state,self.manifest,self.plan,
                                    chrome_factory=OccupiedChrome,workflow_factory=DraftWorkflow)
        self.assertEqual(result['drafts'][0]['code'],'EXISTING_DRAFT_RETAINED')
        self.assertEqual(DraftWorkflow.prepared,[])
    def test_async_editor_paste_is_not_repeated(self):
        class AsyncEditor:
            writes=0;reads=0
            def call(self,name,request):
                if request['op']=='set_text':self.writes+=1;raise Hold('EDITOR_READBACK_FAILED')
                self.reads+=1
                if self.reads==1:raise Hold('TEXT_READBACK_CHANGED')
                return {'ok':True}
        chrome=AsyncEditor();w=Workflow(self.settings,chrome,self.root)
        self.assertTrue(w.set_text('boldstone_threads',{'op':'set_text','locator':[{'selector':'#editor'}],'value':'Text'},True)['ok'])
        self.assertEqual(chrome.writes,1);self.assertEqual(chrome.reads,2)

if __name__=='__main__':unittest.main()
