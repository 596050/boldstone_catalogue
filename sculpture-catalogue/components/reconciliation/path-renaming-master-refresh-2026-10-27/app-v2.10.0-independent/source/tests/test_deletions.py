from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from delete_dropbox import inspect_file, execute, verify_absent, validate_review
from fetch_original import OriginalError
from deletions import Deletions, NativeRejected
from projection import Projection
from store import Conflict
from exports import create_export
import test_live_review

ROOT = '/BOLDSTONE MASTER/Products/01 Wall Sculptures'
TARGET, KEEPER = 'id:target', 'id:keeper'


class Missing(Exception):
    error = SimpleNamespace(is_path=lambda: True, get_path=lambda: SimpleNamespace(is_not_found=lambda: True))


class FakeDropbox:
    def __init__(self):
        self.calls, self.gone = [], set()
        self.files = {fid: SimpleNamespace(id=fid, name=fid[3:]+'.jpg', rev='a1', content_hash='a'*64, size=68,
                     path_display=ROOT+'/Test/'+fid[3:]+'.jpg', path_lower=(ROOT+'/Test/'+fid[3:]+'.jpg').lower(),
                     server_modified=datetime.now(timezone.utc), has_explicit_shared_members=False)
                      for fid in (TARGET, KEEPER)}
        self.links = []
        self.after_delete_error = False

    def files_get_metadata(self, fid, **kwargs):
        if fid in self.gone:
            raise Missing()
        return self.files[fid]

    def sharing_list_shared_links(self, **kwargs):
        return SimpleNamespace(links=self.links, has_more=False)

    def files_delete_v2(self, fid, parent_rev):
        self.calls.append((fid,parent_rev))
        if parent_rev != self.files[fid].rev:
            raise ValueError('revision mismatch')
        self.gone.add(fid)
        if self.after_delete_error:
            raise TimeoutError('response lost after commit')
        return SimpleNamespace(metadata=self.files[fid])


class NativeDeletionTests(unittest.TestCase):
    def setUp(self):
        self.client = FakeDropbox()
        self.binding = {'id': TARGET, 'content_hash': 'a'*64, 'bytes': 68}
        self.reviewed = inspect_file(self.client, self.binding, ROOT)

    def test_exact_file_revision_only_and_absence_readback(self):
        result = execute(self.client,self.reviewed,self.binding,ROOT)
        self.assertTrue(result['verified_absent'])
        self.assertEqual(self.client.calls,[(TARGET,'a1')])
        self.assertNotIn(KEEPER,self.client.gone)

    def test_changed_revision_path_or_sharing_does_not_delete(self):
        for field,value in [('rev','a2'),('path_display',ROOT+'/moved.jpg')]:
            before=getattr(self.client.files[TARGET],field)
            setattr(self.client.files[TARGET],field,value)
            with self.assertRaises(OriginalError):execute(self.client,self.reviewed,self.binding,ROOT)
            setattr(self.client.files[TARGET],field,before)
        self.client.links=[SimpleNamespace(url='https://www.dropbox.com/new',name='new',path_lower='/shared')]
        with self.assertRaises(OriginalError):execute(self.client,self.reviewed,self.binding,ROOT)
        self.assertEqual(self.client.calls,[])

    def test_folder_or_file_outside_root_rejected(self):
        self.client.files[TARGET].rev=None
        with self.assertRaises(OriginalError):inspect_file(self.client,self.binding,ROOT)
        self.client.files[TARGET].rev='a1'
        self.client.files[TARGET].path_display='/Unrelated/test.jpg'
        with self.assertRaises(OriginalError):inspect_file(self.client,self.binding,ROOT)
        self.assertEqual(self.client.calls,[])

    def test_keeper_change_rejects_duplicate_deletion(self):
        keeper=inspect_file(self.client,{'id':KEEPER,'content_hash':'a'*64,'bytes':68},ROOT)
        self.client.files[KEEPER].rev='changed'
        with self.assertRaises(OriginalError):execute(self.client,self.reviewed,self.binding,ROOT,keeper)
        self.assertEqual(self.client.calls,[])

    def test_lost_response_never_retries_and_reads_back_absence(self):
        self.client.after_delete_error=True
        result=execute(self.client,self.reviewed,self.binding,ROOT)
        self.assertEqual(result['state'],'deleted')
        self.assertEqual(len(self.client.calls),1)

    def test_failed_readback_is_not_called_deleted(self):
        def unavailable(*args,**kwargs):raise TimeoutError()
        self.client.files_get_metadata=unavailable
        result=verify_absent(self.client,TARGET)
        self.assertEqual(result['state'],'uncertain')
        self.assertFalse(result['verified_absent'])


class DeletionJobTests(unittest.TestCase):
    tearDown=test_live_review.LiveReviewTests.tearDown

    def setUp(self):
        test_live_review.LiveReviewTests.setUp(self)
        image=self.cat.assets.pop('image')
        self.cat.assets={fid:{**deepcopy(image),'id':fid,'name':fid[3:]+'.jpg',
                             'original':{'bytes':68,'dropbox_content_hash':'a'*64,'dimensions':[1,1]}}
                         for fid in (TARGET,KEEPER)}
        self.cat.paths={fid:(self.image,'cached source') for fid in (TARGET,KEEPER)}
        self.cat.edges={pid:{fid:{'uses':[],'qualifications':[],'tier':'accepted'} for fid in (TARGET,KEEPER)} for pid in ('A','B')}
        self.cat.products['A']['primary_id']=TARGET
        self.client=FakeDropbox()
        def runner(request):
            action=request['action']
            if action=='inspect':
                result={'file':inspect_file(self.client,request['binding'],ROOT,allow_missing=True)}
                if request.get('keeper_binding'):result['keeper']=inspect_file(self.client,request['keeper_binding'],ROOT)
                return result
            if action in ('execute','validate'):
                try:return (execute if action=='execute' else validate_review)(
                    self.client,request['reviewed'],request['binding'],ROOT,request.get('keeper'),request.get('rename_runtime'))
                except OriginalError as exc:raise NativeRejected(str(exc)) from exc
            return verify_absent(self.client,request['file_id'])
        self.manager=Deletions(self.cat,self.store,runner)

    def plan(self):
        return self.manager.prepare({'asset_id':TARGET,'keeper_id':KEEPER,'reason':'duplicate'})

    def confirm(self,plan):
        return {'operation_id':plan['operation_id'],'confirm_file_id':TARGET,'confirmed':True}

    def test_preparation_does_not_delete_and_exact_confirmation_is_required(self):
        plan=self.plan()
        self.assertEqual(self.client.calls,[])
        for bad in ({'confirmed':False},{'confirm_file_id':KEEPER}):
            with self.assertRaises(ValueError):self.manager.execute({**self.confirm(plan),**bad})
        self.assertEqual(self.client.calls,[])

    def test_deleted_native_file_hidden_globally_and_export_withholds_cache(self):
        for pid in ('A','B','__library__'):
            self.store.save('image',pid,TARGET,{'decision':'reviewed','uses':['advertising'],'primary':False},0,self.cat.source['register_sha256'],{})
        original=self.image.read_bytes()
        plan=self.plan();result=self.manager.execute(self.confirm(plan))
        self.assertEqual(result['state'],'deleted')
        view=Projection(self.cat,self.store.all())
        for pid in ('A','B'):self.assertNotIn(TARGET,view.edges[pid])
        self.assertNotIn(TARGET,[a['id'] for a in view.library()])
        self.assertIn(KEEPER,[a['id'] for a in view.library()])
        self.assertEqual(self.image.read_bytes(),original)
        exported=create_export(self.cat,self.store,True)
        self.assertFalse((Path(exported['path'])/'media').exists())
        self.assertIn('deleted_or_pending_verification',(Path(exported['path'])/'image-decisions-and-tags.csv').read_text())
        self.assertEqual(self.store.get('image','A',TARGET)['version'],1)
        # Retried HTTP requests return the existing receipt, never delete twice.
        self.manager.execute(self.confirm(plan))
        self.assertEqual(len(self.client.calls),1)

    def test_changed_catalogue_use_rejects_stale_review(self):
        plan=self.plan()
        self.store.save('image','B',TARGET,{'decision':'reviewed','uses':['listing'],'primary':True},0,self.cat.source['register_sha256'],{})
        with self.assertRaises(Conflict):self.manager.execute(self.confirm(plan))
        self.assertEqual(self.client.calls,[])

    def test_native_precondition_rejection_keeps_file_visible(self):
        plan=self.plan();self.client.files[TARGET].rev='changed'
        result=self.manager.execute(self.confirm(plan))
        self.assertEqual(result['state'],'rejected')
        self.assertIn(TARGET,Projection(self.cat,self.store.all()).edges['A'])
        self.assertEqual(self.client.calls,[])

    def test_timeout_persists_uncertainty_and_check_never_repeats_delete(self):
        plan=self.plan();real=self.manager.runner
        def timeout(request):
            if request['action']=='execute':raise TimeoutError()
            return real(request)
        self.manager.runner=timeout
        result=self.manager.execute(self.confirm(plan))
        self.assertEqual(result['state'],'uncertain')
        self.assertNotIn(TARGET,Projection(self.cat,self.store.all()).edges['A'])
        again=Deletions(self.cat,self.store,real)
        again.execute(self.confirm(plan))
        again.check({'operation_id':plan['operation_id']})
        self.assertEqual(self.client.calls,[])

    def test_identical_platform_alias_not_deleted_or_reintroduced(self):
        self.cat.assets['platform']={**deepcopy(self.cat.assets[TARGET]),'id':'platform','source':'Shopify'}
        self.cat.edges['A']['platform']={'uses':[],'qualifications':[],'tier':'related'}
        self.cat.canonical_assets={'platform':TARGET,TARGET:TARGET,KEEPER:KEEPER}
        self.cat.duplicate_members={TARGET:[TARGET,'platform'],KEEPER:[KEEPER]}
        plan=self.plan();self.manager.execute(self.confirm(plan))
        view=Projection(self.cat,self.store.all())
        self.assertEqual([a['id'] for a in view.images('A')],[KEEPER])
        self.assertIn('platform',self.cat.assets)
        self.assertEqual(self.client.calls,[(TARGET,'a1')])

    def test_keeper_in_same_exact_byte_group_is_rejected_before_native_checks(self):
        self.cat.canonical_assets={TARGET:TARGET,KEEPER:TARGET}
        self.cat.duplicate_members={TARGET:[TARGET,KEEPER]}
        def forbidden(request):self.fail('A same-group keeper must be rejected before any native request')
        self.manager.runner=forbidden
        with self.assertRaisesRegex(ValueError,'byte-identical'):
            self.plan()
        self.assertEqual(self.client.calls,[])
        self.assertIn(KEEPER,Projection(self.cat,self.store.all()).member_ids(TARGET))
        self.assertFalse(self.store.get('deletion','',TARGET)['version'])

    def test_keeper_group_change_after_review_cannot_hide_the_keeper(self):
        plan=self.plan()
        self.cat.canonical_assets={TARGET:TARGET,KEEPER:TARGET}
        self.cat.duplicate_members={TARGET:[TARGET,KEEPER]}
        with self.assertRaisesRegex(Conflict,'same grouped image'):
            self.manager.execute(self.confirm(plan))
        self.assertEqual(self.client.calls,[])
        self.assertEqual(self.client.gone,set())
        self.assertFalse(Projection(self.cat,self.store.all()).deleted)
        self.assertEqual(self.manager.job(plan['operation_id'])['state'],'prepared')


class DeletionBatchTests(unittest.TestCase):
    tearDown=DeletionJobTests.tearDown

    def setUp(self):
        DeletionJobTests.setUp(self)
        self.third='id:third'
        self.cat.assets[self.third]={**deepcopy(self.cat.assets[TARGET]),'id':self.third,'name':'third.jpg'}
        self.cat.paths[self.third]=self.cat.paths[TARGET]
        for pid in ('A','B'):
            self.cat.edges[pid][self.third]=deepcopy(self.cat.edges[pid][TARGET])
        native=deepcopy(self.client.files[TARGET])
        native.id=self.third;native.name='third.jpg'
        native.path_display=ROOT+'/Test/third.jpg';native.path_lower=native.path_display.lower()
        self.client.files[self.third]=native

    def plans(self,ids=(TARGET,KEEPER)):
        return [self.manager.prepare({'asset_id':fid,'reason':'unwanted'}) for fid in ids]

    def batch(self,plans=None):
        return self.manager.prepare_batch({'operation_ids':[p['operation_id'] for p in (plans or self.plans())]})

    def confirmation(self,batch):
        return {'batch_id':batch['batch_id'],'confirm_files':batch['files'],'confirmed':True}

    def test_exact_complete_confirmation_and_no_single_job_bypass(self):
        batch=self.batch()
        for bad in ({'confirmed':False},{'confirm_files':batch['files'][:1]},
                    {'confirm_files':list(reversed(batch['files']))},
                    {'confirm_files':[{'id':TARGET,'revision':'wrong'},batch['files'][1]]}):
            with self.assertRaises(ValueError):
                self.manager.execute_batch({**self.confirmation(batch),**bad})
        with self.assertRaisesRegex(ValueError,'batch together'):
            self.manager.execute({'operation_id':batch['operation_ids'][0],'confirm_file_id':TARGET,'confirmed':True})
        self.assertEqual(self.client.calls,[])

    def test_batch_retains_exact_membership_and_repeated_requests_do_not_delete_again(self):
        batch=self.batch();result=self.manager.execute_batch(self.confirmation(batch))
        self.assertEqual(result['state'],'deleted')
        self.assertEqual(self.client.calls,[(TARGET,'a1'),(KEEPER,'a1')])
        self.assertNotIn(self.third,self.client.gone)
        for job in self.manager.history():self.assertEqual(job['batch_id'],batch['batch_id'])
        again=Deletions(self.cat,self.store,self.manager.runner)
        self.assertEqual(again.batch(batch['batch_id'])['payload']['files'],batch['files'])
        self.assertEqual(again.execute_batch(self.confirmation(batch))['state'],'deleted')
        self.assertEqual(len(self.client.calls),2)

    def test_repeated_file_or_display_group_and_platform_targets_are_rejected(self):
        plans=self.plans()
        with self.assertRaises(ValueError):self.batch([plans[0],plans[0]])
        duplicate=self.manager.prepare({'asset_id':TARGET,'reason':'unwanted'})
        with self.assertRaisesRegex(ValueError,'only once'):self.batch([plans[0],duplicate])
        self.cat.canonical_assets={TARGET:TARGET,KEEPER:TARGET,self.third:self.third}
        self.cat.duplicate_members={TARGET:[TARGET,KEEPER],self.third:[self.third]}
        with self.assertRaisesRegex(ValueError,'only once'):self.batch(plans)
        self.cat.assets['platform']={**deepcopy(self.cat.assets[TARGET]),'id':'platform','source':'Shopify'}
        with self.assertRaisesRegex(ValueError,'Dropbox original'):
            self.manager.prepare({'asset_id':'platform','reason':'unwanted'})
        self.assertEqual(self.client.calls,[])

    def test_keeper_cannot_be_a_selected_target_or_its_alias(self):
        target=self.manager.prepare({'asset_id':TARGET,'reason':'duplicate','keeper_id':KEEPER})
        selected_keeper=self.plans([KEEPER])[0]
        with self.assertRaisesRegex(ValueError,'also selected'):self.batch([target,selected_keeper])
        other=self.plans([self.third])[0]
        self.cat.canonical_assets={TARGET:TARGET,KEEPER:KEEPER,self.third:KEEPER}
        self.cat.duplicate_members={TARGET:[TARGET],KEEPER:[KEEPER,self.third]}
        with self.assertRaisesRegex(ValueError,'also selected'):self.batch([target,other])
        self.assertEqual(self.client.calls,[])

    def test_later_catalogue_change_blocks_entire_batch_before_any_deletion(self):
        batch=self.batch()
        self.store.save('image','B',KEEPER,{'decision':'reviewed','uses':['listing']},0,self.cat.source['register_sha256'],{})
        with self.assertRaisesRegex(Conflict,'catalogue use changed'):
            self.manager.execute_batch(self.confirmation(batch))
        self.assertEqual(self.client.calls,[])
        self.assertEqual(self.manager.batch(batch['batch_id'])['state'],'prepared')

    def test_uncertainty_stops_remaining_files_and_status_read_never_retries(self):
        batch=self.batch(self.plans([TARGET,KEEPER,self.third]));real=self.manager.runner
        def timeout(request):
            if request['action']=='execute' and request['binding']['id']==KEEPER:raise TimeoutError()
            return real(request)
        self.manager.runner=timeout
        result=self.manager.execute_batch(self.confirmation(batch))
        self.assertEqual(result['state'],'partial')
        self.assertEqual([r['state'] for r in result['results']],['deleted','uncertain','not_started'])
        self.assertEqual(self.client.calls,[(TARGET,'a1')])
        again=Deletions(self.cat,self.store,real)
        self.assertEqual(again.batch_status({'batch_id':batch['batch_id']})['results'],result['results'])
        again.execute_batch(self.confirmation(batch))
        self.assertEqual(self.client.calls,[(TARGET,'a1')])
        self.assertEqual(again.job(batch['operation_ids'][2])['state'],'prepared')

    def test_native_rejection_stops_remaining_files(self):
        batch=self.batch(self.plans([TARGET,KEEPER,self.third]))
        self.client.files[KEEPER].rev='changed'
        result=self.manager.execute_batch(self.confirmation(batch))
        self.assertEqual([r['state'] for r in result['results']],['deleted','rejected','not_started'])
        self.assertEqual(self.client.calls,[(TARGET,'a1')])
        self.assertNotIn(self.third,self.client.gone)

    def test_concurrent_repeat_returns_progress_without_starting_a_second_run(self):
        import threading
        from concurrent.futures import ThreadPoolExecutor
        batch=self.batch();real=self.manager.runner;entered=threading.Event();release=threading.Event()
        def wait(request):
            if request['action']=='execute' and request['binding']['id']==TARGET:
                entered.set();release.wait(5)
            return real(request)
        self.manager.runner=wait
        with ThreadPoolExecutor(max_workers=1) as pool:
            future=pool.submit(self.manager.execute_batch,self.confirmation(batch))
            try:
                self.assertTrue(entered.wait(5))
                self.assertEqual(self.manager.execute_batch(self.confirmation(batch))['state'],'executing')
                self.assertEqual(self.client.calls,[])
            finally:release.set()
            self.assertEqual(future.result(timeout=10)['state'],'deleted')
        self.assertEqual(self.client.calls,[(TARGET,'a1'),(KEEPER,'a1')])


if __name__=='__main__':unittest.main()
