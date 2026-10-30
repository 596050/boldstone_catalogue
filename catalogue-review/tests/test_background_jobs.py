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
        self.assertFalse(self.jobs.get(job['id'])['can_resume_rename'])

    def test_filename_change_rejection_alone_offers_verified_rename_recovery(self):
        job,_=self.enqueue();self.client.files[TARGET].rev='changed'
        self.jobs.step()
        self.assertFalse(self.jobs.get(job['id'])['can_resume_rename'])
        # Legacy jobs rejected by the old exact-path check can still offer the
        # recovery route; that route requires a verified rename journal.
        oid=self.jobs.get(job['id'])['progress']['results'][0]['operation_id']
        with self.store.connect() as db:
            db.execute('UPDATE deletion_jobs SET result=? WHERE id=?',(json.dumps({
                'delete_attempted':False,'message':'This file, its location or sharing changed after review. Review it again before deleting.'}),oid))
        self.assertTrue(self.jobs.get(job['id'])['can_resume_rename'])

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

    def test_clear_finished_is_idempotent_for_no_move_required_and_completed_jobs(self):
        for ident,state in [('reference','not_required'),('done','completed')]:
            with self.store.connect() as db:self.jobs.insert(db,ident,'organise',{'asset_id':TARGET})
            self.jobs.mark(ident,state,{'message':'Saved without moving','native_attempted':False})
        self.assertEqual(len(self.jobs.snapshot()['jobs']),2)
        self.assertEqual(self.jobs.clear_finished()['cleared'],2)
        self.assertEqual(self.jobs.clear_finished()['cleared'],0)
        self.assertEqual(self.jobs.snapshot()['jobs'],[])
        self.assertEqual(self.jobs.snapshot(include_dismissed=True)['dismissed_count'],2)
        self.assertEqual(self.client.calls,[])

    def test_detaching_all_components_retains_library_reference_without_native_call(self):
        self.organisation_fixture()
        for pid in ('L1','L2'):
            self.store.save('assignment',pid,TARGET,{'state':'removed'},0,self.cat.source['register_sha256'],{})
        self.jobs.step()
        job=self.jobs.snapshot()['jobs'][0]
        self.assertEqual(job['state'],'not_required')
        self.assertFalse(job['result']['native_attempted'])
        self.assertIn('library reference',job['message'])
        self.assertTrue(job['can_dismiss']);self.assertEqual(self.native.moves,[])
        self.assertFalse(any(TARGET in edges for edges in self.app.projection().edges.values() if edges.get(TARGET,{}).get('tier')!='related'))

    def test_shared_finish_folder_role_move_keeps_associations_and_listing_choices(self):
        self.organisation_fixture()
        self.cat.products['L2']['folder_url']=self.cat.products['L1']['folder_url']
        self.store.save('image','L1',TARGET,{'decision':'reviewed','uses':['advertising','listing']},0,self.cat.source['register_sha256'],{})
        before=deepcopy(self.cat.edges)
        self.type_save(['product','in_situ'])
        self.jobs.step()
        self.assertEqual(self.jobs.snapshot()['jobs'][0]['state'],'completed')
        self.assertEqual(len(self.native.moves),1)
        self.assertTrue(self.native.moves[0][1].startswith(SINGLE+' In Situ/'))
        self.assertEqual(self.cat.edges,before)
        self.assertEqual(self.store.get('image','L1',TARGET)['data']['uses'],['advertising','listing'])

    def test_replan_historical_all_removed_job_closes_it_without_calling_dropbox(self):
        self.organisation_fixture();self.store.review_hook=None
        for pid in ('L1','L2'):
            self.store.save('assignment',pid,TARGET,{'state':'removed'},0,self.cat.source['register_sha256'],{})
        with self.store.connect() as db:self.jobs.insert(db,'old-detach','organise',{'asset_id':TARGET})
        self.jobs.mark('old-detach','needs_review',{'message':'Choose components'})
        job=self.jobs.replan('old-detach')
        self.assertEqual(job['state'],'not_required')
        self.assertEqual(self.jobs.replan('old-detach')['id'],job['id'])
        self.assertEqual(self.jobs.get('old-detach')['state'],'superseded')
        self.assertFalse(self.jobs.step());self.assertEqual(self.native.moves,[])

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


class OrganisationRecoveryTests(unittest.TestCase):
    setUp = BackgroundJobTests.setUp
    tearDown = BackgroundJobTests.tearDown
    organisation_fixture = BackgroundJobTests.organisation_fixture
    type_save = BackgroundJobTests.type_save

    def stopped_move(self):
        self.organisation_fixture()
        self.cat.edges = {pid: {} for pid in self.cat.products}
        self.type_save(['in_situ'])
        self.jobs.step()
        return self.jobs.snapshot()['jobs'][0]

    def attach_component(self):
        row = next(r for r in payload(self.app.projection(), TARGET)['rows'] if r['product_id'] == 'L1')
        row.update(shown=True, listing=False, advertising=False)
        save_components(self.app, {'asset_id': TARGET, 'content_hash': 'a' * 64, 'rows': [row]})

    def test_correcting_components_replaces_stopped_warning_and_preserves_receipt(self):
        old = self.stopped_move()
        self.attach_component()
        queued = self.jobs.snapshot()['jobs']
        self.assertEqual(len(queued), 1)
        replaced = self.jobs.get(old['id'])
        self.assertEqual(replaced['state'], 'superseded')
        self.assertEqual(replaced['result']['message'], old['message'])
        self.assertEqual(replaced['result']['replacement_job_id'], queued[0]['id'])
        self.jobs.step()
        self.assertEqual(len(self.native.moves), 1)
        self.assertEqual(self.jobs.snapshot()['jobs'][0]['state'], 'completed')

    def test_late_failure_is_replaced_by_choices_saved_while_old_job_was_running(self):
        self.organisation_fixture(); self.type_save(['in_situ'])
        old = self.jobs.snapshot()['jobs'][0]
        def stopped_during_new_choice(*_):
            self.type_save(['detail'], 1)
            raise ValueError('The old destination could not be prepared.')
        self.jobs.runner = stopped_during_new_choice
        self.jobs.step()
        jobs = self.jobs.snapshot()['jobs']
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]['state'], 'queued')
        self.assertEqual(self.jobs.get(old['id'])['state'], 'superseded')
        self.assertEqual(self.native.moves, [])

    def test_unknown_move_intent_is_preserved_and_cannot_be_replanned(self):
        old = self.stopped_move()
        directory = self.jobs.root / old['id']; directory.mkdir(exist_ok=True)
        (directory / 'move-intent.json').write_text('{}')
        self.cat.edges['L1'] = {TARGET: {'tier': 'folder'}}
        with self.assertRaisesRegex(Conflict, 'unverified|uncertain|Check'):
            self.jobs.replan(old['id'])
        self.type_save(['detail'], 1)
        self.assertEqual(self.jobs.get(old['id'])['state'], 'needs_review')

    def test_explicitly_rejected_move_can_be_replaced_but_other_assets_stay(self):
        old = self.stopped_move()
        directory = self.jobs.root / old['id']; directory.mkdir(exist_ok=True)
        (directory / 'move-intent.json').write_text('{}')
        self.jobs.mark(old['id'], 'needs_review', {'native_rejected': True, 'message': 'Destination conflict'})
        with self.store.connect() as db:
            self.jobs.insert(db, 'other-image', 'organise', {'asset_id': KEEPER})
        self.jobs.mark('other-image', 'needs_review', {'message': 'Other image needs a component'})
        self.type_save(['detail'], 1)
        self.assertEqual(self.jobs.get(old['id'])['state'], 'superseded')
        self.assertEqual(self.jobs.get('other-image')['state'], 'needs_review')

    def test_failed_save_keeps_old_warning_and_does_not_add_a_job(self):
        old = self.stopped_move()
        with patch.object(self.jobs, 'insert', side_effect=RuntimeError('outbox full')):
            with self.assertRaises(RuntimeError): self.type_save(['detail'], 1)
        self.assertEqual(self.jobs.get(old['id'])['state'], 'needs_review')
        self.assertEqual(self.store.get('asset', '', TARGET)['version'], 1)
        self.assertEqual(len(self.jobs.snapshot()['jobs']), 1)

    def test_uncertain_move_stays_visible_and_holds_new_moves(self):
        old = self.stopped_move()
        self.jobs.mark(old['id'], 'uncertain', {'message': 'Move outcome unknown'})
        self.type_save(['detail'], 1)
        self.assertEqual(self.jobs.get(old['id'])['state'], 'uncertain')
        self.assertFalse(self.jobs.step())
        self.assertEqual(self.native.moves, [])
        self.assertIsNotNone(self.jobs.snapshot()['reservation'])

    def test_corrupt_replacement_chain_cannot_target_another_original(self):
        old = self.stopped_move()
        with self.store.connect() as db:
            self.jobs.insert(db, 'other-original', 'organise', {'asset_id': KEEPER})
        self.jobs.mark(old['id'], 'superseded', {'replacement_job_id': 'other-original'})
        with self.assertRaises(Conflict): self.jobs.replan(old['id'])
        self.jobs.mark(old['id'], 'superseded', {'replacement_job_id': old['id']})
        with self.assertRaises(Conflict): self.jobs.replan(old['id'])
        self.assertEqual(self.native.moves, [])

    def test_repeated_replan_returns_existing_replacement_without_another_move(self):
        old = self.stopped_move()
        self.cat.edges['L1'] = {TARGET: {'tier': 'folder'}}
        first = self.jobs.replan(old['id'])
        again = self.jobs.replan(old['id'])
        self.assertEqual(first['id'], again['id'])
        self.jobs.step()
        self.assertEqual(self.jobs.replan(old['id'])['state'], 'completed')
        self.assertEqual(len(self.native.moves), 1)

    def test_repeated_replan_follows_coalesced_choices_to_the_final_job(self):
        old = self.stopped_move()
        self.cat.edges['L1'] = {TARGET: {'tier': 'folder'}}
        first = self.jobs.replan(old['id'])
        self.type_save(['detail'], 1)
        latest = self.jobs.replan(old['id'])
        self.assertNotEqual(first['id'], latest['id'])
        self.assertEqual(latest['state'], 'queued')
        self.jobs.step()
        self.assertIn(' Details/', self.native.moves[0][1])
        self.assertEqual(len(self.native.moves), 1)

    def test_stopped_planning_job_identifies_the_original_and_its_current_links(self):
        old = self.stopped_move()
        self.assertEqual(old['label'], 'old_013.JPG')
        self.assertEqual(old['image']['id'], TARGET)
        self.assertEqual(old['image']['folder_url'], self.cat.assets[TARGET]['folder_url'])
        self.assertEqual(old['image']['url'], self.cat.assets[TARGET]['url'])
