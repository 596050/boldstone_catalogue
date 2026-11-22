import copy
import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from common import Hold,digest
from google_business import GoogleBusinessProfile,link_validation_rejection,record_identity,saved_details,saved_text_action,rejected_revision_context,observed_revision_context
from common import atomic_json,canonical
from workflow import Workflow
from settings import Settings


class GoogleNativeChecks(unittest.TestCase):
    def setUp(self):
        self.context={'location_id':'123','caption':'Sculpture - White\n\nA new relief.',
                      'media_sha256':'a'*64,'purchase_url':'https://boldstonesculpture.com/buy/p/sculpture'}
        self.row={'html':'<div data-post-name="accounts/-/locations/123/localPosts/456"></div>',
                  'text':self.context['caption']+'\nBuy\nPublished just now'}
        self.caption={'text':self.context['caption']}
        self.status={'text':'Published just now'}
        self.detail={'editors':[{'tag':'TEXTAREA','html':'<textarea maxlength="1500">','value':self.context['caption']}],
                     'inputs':[{'html':'<input type="url">','value':self.context['purchase_url']}],
                     'controls':[{'tag':'BUTTON','name':'Buy'}]}
        self.photo={'checks':[{'image':True,'photo':{'input_sha256':'a'*64,'width':1254,'height':1254}}]}

    def test_published_record_is_bound_to_exact_location_post_and_caption(self):
        self.assertEqual(record_identity(self.row,self.caption,self.status,self.context)['post_id'],'456')
        self.assertEqual(record_identity(dict(self.row,html=self.row['html']*3),self.caption,self.status,self.context)['post_id'],'456')

    def test_another_location_or_ambiguous_record_is_rejected(self):
        for html in [self.row['html'].replace('/123/','/999/'),self.row['html']+self.row['html'].replace('/456','/789')]:
            with self.assertRaises(Hold):record_identity(dict(self.row,html=html),self.caption,self.status,self.context)

    def test_pending_status_cannot_be_replaced_by_published_words_in_caption(self):
        self.row['text']='Published today\n'+self.context['caption']
        with self.assertRaises(Hold) as caught:record_identity(self.row,self.caption,{'text':'Pending'},self.context)
        self.assertEqual(caught.exception.code,'GOOGLE_POST_PENDING_OR_REJECTED')

    def test_missing_published_status_and_caption_mismatches_are_held(self):
        with self.assertRaises(Hold):record_identity(self.row,{'text':'Different post'},self.status,self.context)
        with self.assertRaises(Hold):record_identity(self.row,self.caption,{'text':'Uploaded'},self.context)

    def test_saved_buy_destination_and_loaded_photo_are_verified(self):
        self.assertEqual(saved_details(self.detail,self.photo,self.context)['purchase_links'][0]['expected'],self.context['purchase_url'])

    def test_saved_text_action_for_a_processing_hold_cannot_replace_loaded_media(self):
        checked=saved_text_action(self.detail,self.context)
        self.assertEqual(checked['purchase_links'][0]['native_link'],self.context['purchase_url'])
        self.assertFalse(any(key in checked for key in ['photo','video','photo_verified','video_verified']))
        with self.assertRaises(Hold):saved_details(self.detail,{'checks':[checked]},self.context)

    def test_saved_video_requires_its_loaded_clip_duration_aspect_and_input_hash(self):
        context={**self.context,'media_type':'video/mp4','video_duration':3.033333,'video_width':720,'video_height':1280}
        video={'checks':[{'video':{'input_sha256':'a'*64,'media_type':'video/mp4','width':720,'height':1280,'duration':3.033333}}]}
        self.assertEqual(saved_details(self.detail,video,context)['video']['duration'],3.033333)
        for field,value in [('duration',10),('width',1280),('input_sha256','b'*64),('media_type','image/jpeg')]:
            changed=copy.deepcopy(video);changed['checks'][0]['video'][field]=value
            with self.assertRaises(Hold):saved_details(self.detail,changed,context)
        with self.assertRaises(Hold):saved_details(self.detail,self.photo,context)

    def test_mp4_requires_a_video_workflow_and_bounded_verified_metadata(self):
        root=Path(__file__).resolve().parents[1];base=json.loads((root/'profiles.json').read_text())
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory);media=folder/'clip.mp4';media.write_bytes(b'\0\0\0\x18ftypmp42fixture')
            profile=copy.deepcopy(base['profiles']['boldstone_google_business_profile']);recipe=json.loads((root/profile['workflow']).read_text())
            guard={'purpose':'video','locator':[{'selector':'main video'}],'video':True,'duration':'$video_duration','width':'$video_width','height':'$video_height'}
            recipe['google_video']=guard;recipe['ready']=[guard if g.get('purpose')=='photo' else g for g in recipe['ready']]
            profile['workflow']='video-workflow.json';(folder/profile['workflow']).write_text(json.dumps(recipe))
            config=folder/'profiles.json';config.write_text(json.dumps({'schema_version':1,'policy':base['policy'],'profiles':{'boldstone_google_business_profile':profile}}))
            manifest=folder/'manifest.json';post={'post_key':'clip','title':'Archive film','alt_text':'Archive film','media_path':str(media),'sha256':digest(media.read_bytes()),'video':{'duration':10,'width':720,'height':720},'targets':{'boldstone_google_business_profile':{'caption':'Archive sculpture film','purchase_url':'https://boldstonesculpture.com/','button_label':'Learn more'}}}
            data={'schema_version':1,'batch_id':'video-fixture','publish_authorized':True,'posts':[post]};manifest.write_text(json.dumps(data))
            self.assertEqual(Settings(config).jobs(manifest)[0]['payload']['media_type'],'video/mp4')
            with self.assertRaises(Hold):Settings().jobs(manifest)
            for metadata in [{'duration':31,'width':720,'height':720},{'duration':10,'width':320,'height':720},{'duration':True,'width':720,'height':720}]:
                post['video']=metadata;manifest.write_text(json.dumps(data))
                with self.assertRaises(Hold):Settings(config).jobs(manifest)

    def test_project_posts_require_the_exact_saved_learn_more_button(self):
        context={**self.context,'button_label':'Learn more','purchase_url':'https://boldstonesculpture.com/'}
        detail=copy.deepcopy(self.detail);detail['inputs'][0]['value']=context['purchase_url']
        with self.assertRaises(Hold):saved_details(detail,self.photo,context)
        detail['controls']=[{'tag':'BUTTON','name':'Learn more'}]
        checked=saved_details(detail,self.photo,context)
        self.assertEqual(checked['purchase_links'][0]['method'],'saved native Learn more button destination')

    def test_wrong_saved_destination_missing_button_or_changed_description_are_held(self):
        for key,value in [('inputs',[{'html':'<input type="url">','value':'https://example.com/'}]),('controls',[]),('editors',[])]:
            detail=copy.deepcopy(self.detail);detail[key]=value
            with self.assertRaises(Hold):saved_details(detail,self.photo,self.context)

    def test_missing_duplicate_unloaded_and_cross_job_photo_proofs_are_held(self):
        for photo in [{'checks':[]},{'checks':self.photo['checks']*2},{'checks':[{'image':True,'photo':{'input_sha256':'b'*64,'width':1254,'height':1254}}]},{'checks':[{'image':True,'photo':{'input_sha256':'a'*64,'width':0,'height':1254}}]}]:
            with self.assertRaises(Hold):saved_details(self.detail,photo,self.context)

    def test_google_navigation_never_adopts_another_profile_or_search_page(self):
        profile={'platform':'google_business_profile','location_id':'123','allowed_hosts':['www.google.com']}
        Settings.check_url(profile,'https://www.google.com/local/business/123/promote/updates/456/edit')
        for url in ['https://www.google.com/local/business/999/promote/updates','https://www.google.com/search?q=Boldstone']:
            with self.assertRaises(Hold):Settings.check_url(profile,url)

    def test_only_an_exact_native_link_validation_rejection_is_accepted(self):
        context={**self.context,'compose_url':'https://www.google.com/local/business/123/promote/updates/add'}
        rejected={**self.detail,'url':context['compose_url'],'text':'A link is required for this button',
                  'inputs':[{'html':'<input type="url" aria-invalid="true">','value':context['purchase_url']}]}
        self.assertTrue(link_validation_rejection(rejected,context))
        for key,value in [('text','Still loading'),('url',context['compose_url'].replace('/123/','/999/')),('inputs',[]),('editors',[]),('controls',[])]:
            self.assertFalse(link_validation_rejection(dict(rejected,**{key:value}),context))
        rejected['inputs'][0]['html']='<input type="url" aria-invalid="false">'
        self.assertFalse(link_validation_rejection(rejected,context))

    def test_correction_requires_an_existing_uncertain_intent(self):
        context={**self.context,'profile_id':'fixture','platform':'google_business_profile'}
        adapter=GoogleBusinessProfile(SimpleNamespace(chrome=None,directory=Path('.'),context=lambda job:context))
        for state,intent in [('PUBLISHED',True),('QUEUED',False),('OUTCOME_UNKNOWN',False)]:
            store=SimpleNamespace(has_intent=lambda job_id:intent,ledger=[])
            with self.assertRaises(Hold) as caught:adapter.correct_link_validation(store,{'id':'one','state':state},Path('unused'))
            self.assertEqual(caught.exception.code,'GOOGLE_VALIDATION_CORRECTION_NOT_ALLOWED')

    def test_the_bounded_correction_limit_can_never_be_replayed(self):
        context={**self.context,'profile_id':'fixture','platform':'google_business_profile'}
        adapter=GoogleBusinessProfile(SimpleNamespace(chrome=None,directory=Path('.'),context=lambda job:context))
        store=SimpleNamespace(has_intent=lambda job_id:True,ledger=[{'kind':'GOOGLE_VALIDATION_CORRECTION_INTENT','job_id':'one'}]*2)
        with self.assertRaises(Hold) as caught:adapter.correct_link_validation(store,{'id':'one','state':'OUTCOME_UNKNOWN'},Path('unused'))
        self.assertEqual(caught.exception.code,'SUBMISSION_ALREADY_ATTEMPTED')

    def test_correction_rejects_unrelated_or_unproven_evidence(self):
        context={**self.context,'profile_id':'fixture','profile_hash':'hash','platform':'google_business_profile'}
        adapter=GoogleBusinessProfile(SimpleNamespace(chrome=None,directory=Path('.'),context=lambda job:context))
        store=SimpleNamespace(has_intent=lambda job_id:True,ledger=[])
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'rejection.json';path.write_text(json.dumps({'job_id':'other','snapshot':{}}))
            with self.assertRaises(Hold) as caught:adapter.correct_link_validation(store,{'id':'one','state':'OUTCOME_UNKNOWN'},path)
            self.assertEqual(caught.exception.code,'GOOGLE_VALIDATION_REJECTION_NOT_PROVEN')

    def test_verification_refreshes_an_inventory_already_at_the_same_url(self):
        context={**self.context,'profile_id':'fixture','id':'one','compose_url':'https://www.google.com/local/business/123/promote/updates/add',
                 'inventory_url':'https://www.google.com/local/business/123/promote/updates'}
        navigations=[]
        def navigate(*args,**kwargs):
            navigations.append(args);raise RuntimeError('refresh reached')
        chrome=SimpleNamespace(call=lambda *args:{},navigate=navigate,bound=lambda *args:({'url':context['inventory_url']},{}))
        settings=SimpleNamespace(profile=lambda name:{},workflow=lambda profile:{},check_url=lambda *args:None)
        adapter=GoogleBusinessProfile(SimpleNamespace(chrome=chrome,directory=Path('.'),context=lambda job:context,settings=settings))
        with self.assertRaisesRegex(RuntimeError,'refresh reached'):adapter.verify({'id':'one'})
        self.assertEqual(navigations[0][1],context['inventory_url'])

    def test_old_rejection_evidence_cannot_correct_a_form_without_a_live_error(self):
        context={**self.context,'profile_id':'fixture','profile_hash':'hash','platform':'google_business_profile',
                 'compose_url':'https://www.google.com/local/business/123/promote/updates/add'}
        rejected={**self.detail,'url':context['compose_url'],'text':'A link is required for this button',
                  'inputs':[{'html':'<input type="url" aria-invalid="true">','value':context['purchase_url']}]}
        chrome=SimpleNamespace(bound=lambda *args,**kwargs:({'job_id':'one','url':context['compose_url']},{}),call=lambda *args:{})
        settings=SimpleNamespace(profile=lambda name:{},workflow=lambda profile:{})
        adapter=GoogleBusinessProfile(SimpleNamespace(chrome=chrome,directory=Path('.'),context=lambda job:context,settings=settings))
        store=SimpleNamespace(has_intent=lambda job_id:True,ledger=[])
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'rejection.json';path.write_text(json.dumps({'job_id':'one','profile_hash':'hash','media_sha256':context['media_sha256'],'snapshot':rejected}))
            with self.assertRaises(Hold) as caught:adapter.correct_link_validation(store,{'id':'one','state':'OUTCOME_UNKNOWN'},path)
            self.assertEqual(caught.exception.code,'GOOGLE_VALIDATION_REJECTION_NOT_LIVE')

    def test_the_same_rejection_evidence_is_never_corrected_twice(self):
        context={**self.context,'profile_id':'fixture','profile_hash':'hash','platform':'google_business_profile'}
        adapter=GoogleBusinessProfile(SimpleNamespace(chrome=None,directory=Path('.'),context=lambda job:context))
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'rejection.json';path.write_text('{}')
            proof=Path(directory)/'correction.json';proof.write_text(json.dumps({'rejection_sha256':digest(path.read_bytes())}))
            store=SimpleNamespace(has_intent=lambda job_id:True,ledger=[{'kind':'GOOGLE_VALIDATION_CORRECTION_INTENT','job_id':'one',
                                  'evidence_path':str(proof),'evidence_sha256':digest(proof.read_bytes())}])
            with self.assertRaises(Hold) as caught:adapter.correct_link_validation(store,{'id':'one','state':'OUTCOME_UNKNOWN'},path)
            self.assertEqual(caught.exception.code,'SUBMISSION_ALREADY_ATTEMPTED')


class RejectedRecordRevisionChecks(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.directory=Path(self.temp.name);(self.directory/'evidence').mkdir()
        self.context={'id':'one','profile_hash':'profile','media_sha256':'a'*64,'caption':'Original sculpture caption','location_id':'123','inventory_url':'https://www.google.com/local/business/123/promote/updates'}
        self.proof={'job_id':'one','profile_hash':'profile','media_sha256':'a'*64,'original_caption':self.context['caption'],'location_id':'123','post_id':'456','native_url':self.context['inventory_url']+'/456/edit','revised_caption':'Revised sculpture caption','verification_attempts_before_revision':8,'rejected_record':{'snapshot':{'html':'<div data-post-name="accounts/-/locations/123/localPosts/456"></div>'},'caption':{'text':self.context['caption']},'status':{'text':'Rejected'}}}
        self.path=self.directory/'evidence/one-google-rejected-revision.json'

    def write_proof(self,events=1):
        atomic_json(self.path,self.proof);previous='0'*64;lines=[]
        for _ in range(events):
            row={'kind':'GOOGLE_REJECTED_REVISION_INTENT','utc':'fixture','previous_sha256':previous,'job_id':'one','evidence_path':str(self.path.resolve()),'evidence_sha256':digest(self.path.read_bytes())}
            row['sha256']=digest(row);previous=row['sha256'];lines.append(canonical(row))
        (self.directory/'intent-ledger.jsonl').write_text('\n'.join(lines)+('\n' if lines else ''))

    def test_no_revision_keeps_the_original_caption_and_retry_epoch(self):
        self.assertEqual(rejected_revision_context(self.context,self.directory),self.context)
        workflow=SimpleNamespace(context=lambda job:self.context,directory=self.directory)
        self.assertEqual(Workflow.reconciliation_epoch(workflow,{'payload':{'platform':'google_business_profile'}}),0)

    def test_durable_revision_is_bound_to_same_location_record_photo_and_original_caption(self):
        self.write_proof();result=rejected_revision_context(self.context,self.directory)
        self.assertEqual(result['caption'],self.proof['revised_caption']);self.assertEqual(result['native_revision_url'],self.proof['native_url'])
        self.assertEqual(self.context['caption'],'Original sculpture caption')
        workflow=SimpleNamespace(context=lambda job:self.context,directory=self.directory)
        self.assertEqual(Workflow.reconciliation_epoch(workflow,{'payload':{'platform':'google_business_profile'}}),8)
        for key,value in [('profile_hash','other'),('media_sha256','b'*64),('caption','Another original'),('location_id','999')]:
            with self.assertRaises(Hold):rejected_revision_context({**self.context,key:value},self.directory)

    def test_missing_duplicate_changed_or_nonrejected_proof_is_held(self):
        for events in [0,2]:
            self.write_proof(events)
            with self.assertRaises(Hold):rejected_revision_context(self.context,self.directory)
        self.write_proof();self.path.write_text(self.path.read_text()+' ')
        with self.assertRaises(Hold):rejected_revision_context(self.context,self.directory)
        self.proof['rejected_record']['status']['text']='Pending';self.write_proof()
        with self.assertRaises(Hold):rejected_revision_context(self.context,self.directory)

    def test_readback_distinguishes_an_applied_edit_from_an_approved_original_caption(self):
        self.write_proof();context=rejected_revision_context(self.context,self.directory)
        revised=observed_revision_context(context,self.proof['revised_caption']);self.assertTrue(revised['caption_revision_applied'])
        original=observed_revision_context(context,self.context['caption']);self.assertFalse(original['caption_revision_applied']);self.assertEqual(original['caption'],self.context['caption'])
        with self.assertRaises(Hold):observed_revision_context(context,'Unrelated edited content')


class GoogleInventoryPaginationChecks(unittest.TestCase):
    def adapter(self,target_page=2,stalled=False):
        self.page=0;self.operations=[];row=[{'selector':'#target'}]
        def call(name,request):
            self.operations.append(request['op'])
            if request['op']=='exists':return {'exists':self.page>=target_page if request['locator']==row else self.page<3}
            if request['op']=='probe':return {'googlePostRecordNames':['accounts/-/locations/123/localPosts/'+str(self.page)]}
            if request['op']=='click':
                if not stalled:self.page+=1
                return {'ok':True}
            raise AssertionError(request['op'])
        def wait(name,locator,**kwargs):
            if locator==row and self.page<target_page:raise Hold('CONTROL_MISSING')
        return GoogleBusinessProfile(SimpleNamespace(chrome=SimpleNamespace(call=call),directory=Path('.'),wait=wait)),row

    def test_older_native_records_are_found_through_more_posts_without_publication_actions(self):
        adapter,row=self.adapter();adapter.find_inventory_record('verification',row)
        self.assertEqual(self.page,2);self.assertEqual(self.operations.count('click'),2);self.assertFalse(any(op in self.operations for op in ['submit','set_text','upload_begin']))

    def test_missing_record_at_the_native_end_remains_unconfirmed(self):
        adapter,row=self.adapter(target_page=4)
        with self.assertRaises(Hold):adapter.find_inventory_record('verification',row)
        self.assertEqual(self.page,3)

    def test_a_more_posts_click_without_new_native_ids_is_not_assumed_successful(self):
        adapter,row=self.adapter(stalled=True)
        with patch('google_business.time.monotonic',side_effect=range(100)),patch('google_business.time.sleep'):
            with self.assertRaises(Hold) as caught:adapter.find_inventory_record('verification',row)
        self.assertEqual(caught.exception.code,'GOOGLE_INVENTORY_PAGE_NOT_LOADED');self.assertEqual(self.operations.count('click'),1)


class GoogleManifestChecks(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        root=Path(self.temp.name);(root/'workflows').mkdir()
        shutil.copyfile(Path(__file__).resolve().parents[1]/'workflows/google_business_profile.json',root/'workflows/google_business_profile.json')
        self.media=root/'fixture.png';self.media.write_bytes(b'fixture image')
        base='https://www.google.com/local/business/123/promote/updates'
        profile={'platform':'google_business_profile','channel_key':'google_business_profile:123','account_name':'Boldstone',
                 'location_id':'123','business_path':'/local/business/123/','allowed_hosts':['www.google.com'],
                 'website_url':'https://boldstonesculpture.com','compose_url':base+'/add','inventory_url':base,
                 'workflow':'workflows/google_business_profile.json','caption_limit':1500,'max_media_bytes':64}
        config={'schema_version':1,'profiles':{'fixture':profile},'policy':{'create_tabs':False,'require_background_tab':True,'max_media_bytes':1024,'require_meta_product_tags':True}}
        config_path=root/'profiles.json';config_path.write_text(json.dumps(config));self.settings=Settings(config_path)
        self.source={'schema_version':1,'batch_id':'fixture','publish_authorized':True,'posts':[{'post_key':'one','title':'Sculpture - White','alt_text':'A sculpture.',
                     'media_path':str(self.media),'sha256':hashlib.sha256(self.media.read_bytes()).hexdigest(),
                     'targets':{'fixture':{'caption':'A new sculpture.','purchase_url':'https://boldstonesculpture.com/buy/p/sculpture'}}}]}
        self.path=root/'manifest.json'

    def jobs(self):
        self.path.write_text(json.dumps(self.source));return self.settings.jobs(self.path)

    def test_google_manifest_requires_a_configured_https_product_destination(self):
        self.assertEqual(len(self.jobs()),1)
        for value in [None,'https://example.com/product','javascript:alert(1)']:
            self.source['posts'][0]['targets']['fixture']['purchase_url']=value
            with self.assertRaises(Hold) as caught:self.jobs()
            self.assertEqual(caught.exception.code,'GOOGLE_PURCHASE_URL_REQUIRED')

    def test_profile_media_limit_is_enforced_before_enqueue(self):
        self.media.write_bytes(b'x'*65);self.source['posts'][0]['sha256']=hashlib.sha256(self.media.read_bytes()).hexdigest()
        with self.assertRaises(Hold) as caught:self.jobs()
        self.assertEqual(caught.exception.code,'MEDIA_FORMAT')

    def test_google_button_defaults_to_buy_and_preserves_learn_more(self):
        self.assertEqual(self.jobs()[0]['payload']['button_label'],'Buy')
        target=self.source['posts'][0]['targets']['fixture']
        target.update(button_label='Learn more',purchase_url='https://boldstonesculpture.com/')
        self.assertEqual(self.jobs()[0]['payload']['button_label'],'Learn more')
        target['button_label']='Call now'
        with self.assertRaises(Hold) as caught:self.jobs()
        self.assertEqual(caught.exception.code,'GOOGLE_BUTTON_UNSUPPORTED')


if __name__=='__main__':unittest.main()
