from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch
import json
import sys
import threading
import unittest
import urllib.request
import urllib.error
from http.server import ThreadingHTTPServer
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from background_jobs import BackgroundJobs
from projection import Projection
from store import Conflict
import test_deletions as deletion_fixtures
from test_deletions import TARGET, KEEPER
from test_organisation import products, SINGLE, GROUP, OrganiseDropbox
from organise_dropbox import organise
from organisation import plan
from component_reviews import save_components
from component_links import payload


class BackgroundJobTests(unittest.TestCase):
    tearDown = deletion_fixtures.DeletionBatchTests.tearDown

    def setUp(self):
        deletion_fixtures.DeletionBatchTests.setUp(self)
        self.app=NS(catalogue=self.cat,store=self.store,catalogue_lock=threading.RLock(),deletions=self.manager,
                    sync=NS(request=lambda:None))
        self.app.projection=lambda:Projection(self.app.catalogue,self.store.all())
        self.jobs=BackgroundJobs(self.app,runner=lambda *_:self.fail('Unexpected live organisation call'))
        self.app.jobs=self.jobs

    def batch(self):return deletion_fixtures.DeletionBatchTests.batch(self)
    def plans(self,ids=(TARGET,KEEPER)):return deletion_fixtures.DeletionBatchTests.plans(self,ids)
    def confirmation(self,batch):return deletion_fixtures.DeletionBatchTests.confirmation(self,batch)

    def enqueue(self):
        batch=self.batch();body=self.confirmation(batch)
        return self.jobs.enqueue_deletion(body,True),body

    def test_confirmation_returns_before_native_work_and_duplicate_http_cannot_repeat(self):
        job,body=self.enqueue()
        self.assertEqual(job['state'],'queued');self.assertEqual(self.client.calls,[])
        self.assertEqual(self.jobs.enqueue_deletion(body,True)['id'],job['id'])
        self.jobs.step()
        self.assertEqual(self.jobs.get(job['id'])['state'],'completed')
        self.assertEqual(len(self.client.calls),2)
        self.jobs.enqueue_deletion(body,True);self.jobs.step()
        self.assertEqual(len(self.client.calls),2)

    def test_new_review_cannot_enqueue_same_original_while_queued(self):
        job,_=self.enqueue()
        with self.assertRaisesRegex(Conflict,'already'):
            self.manager.prepare({'asset_id':TARGET,'reason':'unwanted'})
        self.assertEqual(self.client.calls,[])

    def test_confirmation_expiry_is_checked_at_enqueue_not_after_queue_wait(self):
        job,_=self.enqueue()
        with patch('deletions.time.time',return_value=9999999999):self.jobs.step()
        self.assertEqual(self.jobs.get(job['id'])['state'],'completed')

    def test_native_changed_revision_after_queue_does_not_block_other_files(self):
        job,_=self.enqueue();self.client.files[TARGET].rev='changed'
        self.jobs.step()
        result=self.jobs.get(job['id'])
        self.assertEqual(result['state'],'needs_review');self.assertEqual(self.client.calls,[(KEEPER,'a1')])
        self.assertEqual(result['progress']['results'][1]['state'],'deleted')
        self.assertNotIn(TARGET,self.client.gone)

    def test_new_catalogue_use_after_queue_does_not_delete_stale_review(self):
        job,_=self.enqueue()
        self.store.save('image','A',TARGET,{'decision':'reviewed','uses':['advertising']},0,self.cat.source['register_sha256'],{})
        self.jobs.step()
        self.assertEqual(self.jobs.get(job['id'])['state'],'needs_review');self.assertEqual(self.client.calls,[(KEEPER,'a1')])

    def test_browser_closed_queued_job_survives_new_service_instance(self):
        job,_=self.enqueue()
        replacement=BackgroundJobs(self.app)
        replacement.step()
        self.assertEqual(replacement.get(job['id'])['state'],'completed');self.assertEqual(len(self.client.calls),2)

    def test_namespace_reservation_and_another_worker_block_without_losing_queue(self):
        job,_=self.enqueue();reservation=self.store.root/'native-writer-reservation.json'
        reservation.write_text(json.dumps({'active':True,'label':'Renaming'}))
        self.assertFalse(self.jobs.step());self.assertEqual(self.client.calls,[])
        reservation.unlink()
        other=BackgroundJobs(self.app)
        with self.jobs.writer() as acquired:
            self.assertTrue(acquired);self.assertFalse(other.step())
        other.step();self.assertEqual(len(self.client.calls),2)

    def test_running_job_recovery_never_replays_deletion(self):
        job,_=self.enqueue();self.jobs.mark(job['id'],'running',{})
        replacement=BackgroundJobs(self.app);replacement.step()
        self.assertEqual(replacement.get(job['id'])['state'],'uncertain')
        self.assertEqual(self.client.calls,[])
        checked=replacement.check(job['id'])
        self.assertEqual(checked['state'],'needs_review');self.assertEqual(self.client.calls,[])

    def test_running_child_does_not_hold_catalogue_lock_and_saved_reviews_continue(self):
        job,_=self.enqueue();original=self.manager.runner;entered=threading.Event();release=threading.Event()
        def slow(request):
            if request['action']=='execute':entered.set();release.wait(3)
            return original(request)
        self.manager.runner=slow
        thread=threading.Thread(target=self.jobs.step);thread.start()
        try:
            self.assertTrue(entered.wait(1))
            self.assertTrue(self.app.catalogue_lock.acquire(timeout=.1))
            self.app.catalogue_lock.release()
            self.store.save('product','B','',{'decision':'include'},0,self.cat.source['register_sha256'],{})
            self.assertEqual(self.jobs.get(job['id'])['state'],'running')
        finally:release.set();thread.join(4)
        self.assertEqual(self.jobs.get(job['id'])['state'],'completed')

    def test_job_confirmation_and_outbox_rollback_together(self):
        batch=self.batch()
        with patch.object(self.jobs,'insert',side_effect=RuntimeError('disk full')):
            with self.assertRaises(RuntimeError):self.jobs.enqueue_deletion(self.confirmation(batch),True)
        self.assertEqual(self.jobs.snapshot()['jobs'],[])
        for oid in batch['operation_ids']:
            self.assertNotIn('queue_confirmed_at',self.manager.job(oid)['payload'])

    def organisation_fixture(self):
        self.cat.products=products();self.cat.edges={pid:{TARGET:{'tier':'folder' if pid in ('L1','L2') else 'related'}} for pid in self.cat.products}
        self.cat.assets[TARGET].update(family='Ammonite',provenance={'path':SINGLE+'/old_013.JPG'},name='old_013.JPG',types=['product'],
                                     folder_url='https://www.dropbox.com/home'+SINGLE,original={'dropbox_content_hash':'a'*64,'bytes':68})
        self.native=OrganiseDropbox();self.jobs.runner=lambda body,directory:organise(self.native,body,directory)

    def type_save(self,types,version=0):
        self.store.save('asset','',TARGET,{'types':types,'tags':['retained'],'rights':'owned'},version,self.cat.source['register_sha256'],{})

    def test_atomic_type_save_and_job_coalesce_to_last_choice(self):
        self.organisation_fixture();self.type_save(['product','in_situ']);self.type_save(['product'],1)
        jobs=self.jobs.snapshot()['jobs'];self.assertEqual(len(jobs),1)
        self.jobs.step();self.assertEqual(len(self.native.moves),1)
        self.assertNotIn('In Situ',self.native.moves[0][1]);self.assertEqual(self.store.get('asset','',TARGET)['data']['tags'],['retained'])

    def test_review_rollback_has_no_ghost_native_job(self):
        self.organisation_fixture()
        with patch.object(self.jobs,'insert',side_effect=RuntimeError('outbox full')):
            with self.assertRaises(RuntimeError):self.type_save(['in_situ'])
        self.assertEqual(self.store.get('asset','',TARGET)['version'],0)
        self.assertEqual(self.jobs.snapshot()['jobs'],[])

    def test_shared_group_one_move_and_component_use_preservation(self):
        self.organisation_fixture();self.type_save(['product','group','in_situ'])
        before=deepcopy(self.cat.edges)
        self.jobs.step();job=self.jobs.snapshot()['jobs'][0]
        self.assertEqual(job['state'],'completed');self.assertEqual(len(self.native.moves),1)
        self.assertTrue(self.native.moves[0][1].startswith(GROUP+'/'))
        self.assertEqual(self.cat.edges,before);self.assertEqual(len(self.native.files),2)
        self.assertEqual(self.app.catalogue.assets[TARGET]['provenance']['path'],self.native.moves[0][1])

    def test_changed_components_reuse_original_no_duplicate_copy_or_folder_rename(self):
        self.organisation_fixture();self.type_save(['in_situ']);self.jobs.step()
        view=self.app.projection();row=next(r for r in payload(view,TARGET)['rows'] if r['product_id']=='L2')
        row.update(shown=False,listing=False,advertising=False)
        save_components(self.app,{'asset_id':TARGET,'content_hash':'a'*64,'rows':[row]})
        self.jobs.step()
        self.assertEqual(len(self.native.moves),2)
        self.assertIn('/Ammonite Large 1 White In Situ/',self.native.moves[-1][1])
        self.assertIn(GROUP,self.native.folders);self.assertEqual(len(self.native.files),2)

    def test_missing_components_becomes_visible_needs_review_without_native_call(self):
        self.organisation_fixture();self.cat.edges={pid:{} for pid in self.cat.products};self.type_save(['in_situ'])
        self.jobs.step();job=self.jobs.snapshot()['jobs'][0]
        self.assertEqual(job['state'],'needs_review');self.assertIn('component',job['message'])
        self.assertEqual(self.native.moves,[]);self.assertEqual(self.native.creates,[])

    def test_stale_sync_overlay_cannot_revert_verified_path_but_new_scan_can(self):
        self.organisation_fixture();old=deepcopy(self.cat);self.type_save(['in_situ']);self.jobs.step()
        self.jobs.overlay_locations(old,'2000-01-01')
        self.assertEqual(old.assets[TARGET]['provenance']['path'],self.native.moves[0][1])
        old.assets[TARGET]['provenance']['path']='later external path'
        self.jobs.overlay_locations(old,'9999-01-01')
        self.assertEqual(old.assets[TARGET]['provenance']['path'],'later external path')

    def test_many_completed_jobs_cannot_hide_old_active_jobs(self):
        job,_=self.enqueue()
        with self.store.connect() as db:
            for i in range(100):
                self.jobs.insert(db,'test'+str(i),'organise',{'asset_id':'id:dummy'})
                db.execute("UPDATE background_jobs SET state='completed' WHERE id=?",('test'+str(i),))
        self.assertIn(job['id'],[j['id'] for j in self.jobs.snapshot()['jobs']])
        self.jobs.mark(job['id'],'uncertain',{})
        with self.store.connect() as db:
            db.execute("UPDATE background_jobs SET updated_at='2000-01-01' WHERE id=?",(job['id'],))
        snapshot=self.jobs.snapshot()
        self.assertIn(job['id'],[j['id'] for j in snapshot['jobs']])
        self.assertIsNone(snapshot['reservation'])

    def test_successful_move_readback_immediately_refreshes_catalogue_location(self):
        self.organisation_fixture();self.type_save(['in_situ']);real=self.jobs.runner
        def lost_result(body,directory):
            real(body,directory)
            return {'state':'uncertain','message':'Response lost after move'}
        self.jobs.runner=lost_result
        self.jobs.step();job=self.jobs.snapshot()['jobs'][0]
        self.assertEqual(job['state'],'uncertain')
        self.assertEqual(self.cat.assets[TARGET]['provenance']['path'],SINGLE+'/old_013.JPG')
        self.jobs.runner=real
        checked=self.jobs.check(job['id'])
        self.assertEqual(checked['state'],'completed')
        self.assertEqual(self.cat.assets[TARGET]['provenance']['path'],self.native.moves[0][1])
        self.assertEqual(len(self.native.moves),1)

    def test_old_completed_child_receipt_cannot_revert_later_external_move(self):
        self.organisation_fixture();self.type_save(['in_situ']);real=self.jobs.runner
        def lost_result(body,directory):
            real(body,directory)
            return {'state':'uncertain','message':'Response lost after move'}
        self.jobs.runner=lost_result;self.jobs.step();job=self.jobs.snapshot()['jobs'][0]
        self.cat.source['live_dropbox']={'checked_utc':'9999-01-01'}
        self.cat.assets[TARGET]['provenance']['path']=SINGLE+'/later-external-name.JPG'
        self.jobs.runner=real
        self.assertEqual(self.jobs.check(job['id'])['state'],'completed')
        self.assertEqual(self.cat.assets[TARGET]['provenance']['path'],SINGLE+'/later-external-name.JPG')
        self.assertEqual(len(self.native.moves),1)

    def test_listing_and_advertising_purposes_do_not_change_native_location(self):
        self.organisation_fixture()
        self.store.save('image','L1',TARGET,{'decision':'reviewed','uses':['listing','advertising']},0,self.cat.source['register_sha256'],{})
        self.assertEqual(self.jobs.snapshot()['jobs'],[])
        self.assertEqual(self.native.moves,[])

    def test_cancel_queued_job_sends_nothing_and_running_job_cannot_be_cancelled(self):
        job,_=self.enqueue();self.jobs.cancel(job['id']);self.jobs.step()
        self.assertEqual(self.client.calls,[]);self.assertEqual(self.jobs.get(job['id'])['state'],'cancelled')
        self.jobs.mark(job['id'],'running',{})
        with self.assertRaises(Conflict):self.jobs.cancel(job['id'])

    def test_replan_uses_current_choices_but_never_retries_unknown_submission(self):
        self.organisation_fixture();self.cat.edges={pid:{} for pid in self.cat.products};self.type_save(['in_situ'])
        self.jobs.step();job=self.jobs.snapshot()['jobs'][0];self.assertEqual(job['state'],'needs_review')
        self.cat.edges['L1']={TARGET:{'tier':'folder'}}
        new=self.jobs.replan(job['id']);self.jobs.step();self.assertEqual(self.jobs.get(new['id'])['state'],'completed')
        self.jobs.mark(job['id'],'uncertain',{})
        with self.assertRaises(Conflict):self.jobs.replan(job['id'])

    def test_component_change_during_move_runs_after_first_verified_receipt(self):
        self.organisation_fixture();self.type_save(['in_situ']);original=self.jobs.runner
        entered=threading.Event();release=threading.Event()
        def slow(body,directory):entered.set();release.wait(3);return original(body,directory)
        self.jobs.runner=slow
        thread=threading.Thread(target=self.jobs.step);thread.start()
        try:
            self.assertTrue(entered.wait(1))
            row=next(r for r in payload(self.app.projection(),TARGET)['rows'] if r['product_id']=='L2')
            row.update(shown=False,listing=False,advertising=False)
            save_components(self.app,{'asset_id':TARGET,'content_hash':'a'*64,'rows':[row]})
        finally:release.set();thread.join(4)
        self.jobs.step()
        self.assertEqual(len(self.native.moves),2)
        self.assertIn('/Ammonite Large 1 White In Situ/',self.native.moves[-1][1])
        self.assertEqual(len(self.native.files),2)

    def test_unconfirmed_deletion_readback_allows_fresh_review_without_retry(self):
        job,_=self.enqueue();real=self.manager.runner
        self.manager.runner=lambda request: (_ for _ in ()).throw(TimeoutError()) if request['action']=='execute' else real(request)
        self.jobs.step()
        self.assertEqual(self.jobs.get(job['id'])['state'],'uncertain')
        checked=self.jobs.check(job['id'])
        self.assertEqual(checked['state'],'needs_review');self.assertTrue(checked['can_review_remaining']);self.assertEqual(self.client.calls,[])
        self.assertFalse(self.jobs.step())

    def test_http_returns_202_and_health_and_jobs_remain_available_during_deletion(self):
        from server import Handler
        self.app.token='test-review-token-12345678901234567890'
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler);server.app=self.app;server.daemon_threads=True
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        base='http://127.0.0.1:'+str(server.server_port)
        entered=threading.Event();release=threading.Event();real=self.manager.runner
        def blocked(request):
            if request['action']=='execute':entered.set();release.wait(3)
            return real(request)
        self.manager.runner=blocked
        body=self.confirmation(self.batch())
        def request(route,data=None,token=None):
            req=urllib.request.Request(base+route,data=json.dumps(data).encode() if data is not None else None,
                headers={'Content-Type':'application/json','X-Review-Token':token or self.app.token,'Origin':base})
            with urllib.request.urlopen(req,timeout=1) as response:return response.status,json.load(response)
        worker=None
        try:
            with self.assertRaises(urllib.error.HTTPError) as e:request('/api/deletions/execute-batch',body,'bad')
            self.assertEqual(e.exception.code,403)
            status,queued=request('/api/deletions/execute-batch',body)
            self.assertEqual(status,202);self.assertEqual(queued['state'],'queued');self.assertEqual(self.client.calls,[])
            worker=threading.Thread(target=self.jobs.step);worker.start();self.assertTrue(entered.wait(1))
            self.assertEqual(request('/api/health')[1]['status'],'ok')
            self.assertEqual(request('/api/jobs')[1]['jobs'][0]['state'],'running')
            self.assertEqual(request('/api/deletions/execute-batch',body)[1]['id'],queued['id'])
        finally:
            release.set()
            if worker:worker.join(4)
            server.shutdown();server.server_close();thread.join(1)
        self.assertEqual(len(self.client.calls),2)


if __name__=='__main__':unittest.main()


class JobDismissalTests(unittest.TestCase):
    setUp=BackgroundJobTests.setUp
    tearDown=BackgroundJobTests.tearDown
    organisation_fixture=BackgroundJobTests.organisation_fixture
    type_save=BackgroundJobTests.type_save
    enqueue=BackgroundJobTests.enqueue
    batch=BackgroundJobTests.batch
    confirmation=BackgroundJobTests.confirmation
    plans=BackgroundJobTests.plans
    def test_dismiss_preserves_failure_receipt_and_survives_restart(self):
        self.organisation_fixture();self.cat.edges={pid:{} for pid in self.cat.products};self.type_save(['in_situ'])
        self.jobs.step();job=self.jobs.snapshot()['jobs'][0]
        self.assertTrue(job['can_dismiss']);before=self.jobs.get(job['id'])
        self.jobs.dismiss(job['id'],job['updated_at'])
        self.assertEqual(self.jobs.snapshot()['jobs'],[])
        self.assertEqual(self.jobs.snapshot()['dismissed_count'],1)
        old=self.jobs.snapshot(include_dismissed=True)['jobs'][0]
        self.assertTrue(old['dismissed_at']);self.assertEqual(old['result'],before['result'])
        replacement=BackgroundJobs(self.app)
        self.assertEqual(replacement.snapshot()['jobs'],[])
        replacement.dismiss(job['id'],job['updated_at'],restore=True)
        self.assertEqual(len(replacement.snapshot()['jobs']),1)
        self.assertEqual(self.native.moves,[])

    def test_running_uncertain_and_stale_jobs_cannot_be_hidden(self):
        job,_=self.enqueue()
        for state in ('queued','running','uncertain'):
            self.jobs.mark(job['id'],state,{})
            current=self.jobs.get(job['id'])
            with self.assertRaises(Conflict):self.jobs.dismiss(job['id'],current['updated_at'])
        self.jobs.mark(job['id'],'needs_review',{})
        with self.assertRaises(Conflict):self.jobs.dismiss(job['id'],job['updated_at'])
        self.assertEqual(self.jobs.snapshot()['dismissed_count'],0)

    def test_clear_finished_keeps_problem_jobs_and_native_reservations(self):
        first,_=self.enqueue();self.jobs.step()
        with self.store.connect() as db:self.jobs.insert(db,'problem','organise',{'asset_id':TARGET})
        self.jobs.mark('problem','needs_review',{'message':'Anchor unresolved'})
        before=self.jobs.deletion_activity()
        self.jobs.clear_finished();snapshot=self.jobs.snapshot()
        self.assertEqual([j['id'] for j in snapshot['jobs']],['problem'])
        self.assertEqual(self.jobs.deletion_activity(),before)
        self.assertEqual(self.jobs.get(first['id'])['state'],'completed')

    def test_new_job_result_reappears_after_dismissal(self):
        with self.store.connect() as db:self.jobs.insert(db,'problem','organise',{'asset_id':TARGET})
        self.jobs.mark('problem','needs_review',{'message':'Old problem'})
        job=self.jobs.get('problem');self.jobs.dismiss('problem',job['updated_at'])
        self.jobs.mark('problem','uncertain',{'message':'New unresolved result'})
        self.assertEqual(self.jobs.snapshot()['jobs'][0]['state'],'uncertain')
        self.assertEqual(self.jobs.snapshot()['dismissed_count'],0)

    def test_attention_not_lost_behind_eighty_recent_completed_jobs(self):
        with self.store.connect() as db:self.jobs.insert(db,'old-problem','organise',{'asset_id':TARGET})
        self.jobs.mark('old-problem','needs_review',{'message':'Still needs attention'})
        for n in range(85):
            with self.store.connect() as db:self.jobs.insert(db,'done-'+str(n),'organise',{'asset_id':TARGET})
            self.jobs.mark('done-'+str(n),'completed',{})
        self.assertIn('old-problem',[j['id'] for j in self.jobs.snapshot()['jobs']])
