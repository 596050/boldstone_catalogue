from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
import json
import sqlite3
import sys
import threading
import time
import unittest
sys.path[:0]=[str(Path(__file__).resolve().parents[1]),str(Path(__file__).resolve().parent)]
import test_background_jobs as fixtures
from test_deletions import TARGET, KEEPER
from deletion_reviews import DeletionReviews
from deletions import NativeUnavailable
from delete_dropbox import read_failure, execute, inspect_file
from store import Conflict
from live_review import SourceConflict


class ResilientReviewTests(unittest.TestCase):
    def tearDown(self):
        self.reviews.stop()
        if self.reviews.thread:
            self.reviews.thread.join(5)
            self.assertFalse(self.reviews.thread.is_alive())
        fixtures.BackgroundJobTests.tearDown(self)

    def setUp(self):
        fixtures.BackgroundJobTests.setUp(self)
        self.reviews=DeletionReviews(self.app);self.app.deletion_reviews=self.reviews

    def start(self, ids=None, ident='review-test-123456'):
        return self.reviews.start_review({'request_id':ident,'entries':[{'asset_id':i,'reason':'unwanted','keeper_id':''} for i in (ids or [TARGET,KEEPER,self.third])]})

    def finish(self):
        for _ in range(6):
            if not self.reviews.step():break

    def release_retries(self, ident):
        row=self.reviews.row(ident)
        for e in row['payload']['entries']:e['next_attempt_at']=0
        row['payload']['cooldown_until']=0;self.reviews.write(row)

    def wait_for_checks(self, ident):
        deadline=time.monotonic()+5
        while time.monotonic()<deadline:
            row=self.reviews.row(ident)
            if row['state'] not in ('queued','running'):
                return row
            time.sleep(.01)
        self.fail('Saved read-only checks did not resume')

    def dead_worker(self):
        old=threading.Thread(target=lambda:None)
        old.start();old.join()
        self.reviews.thread=old
        return old

    def test_start_replaces_a_dead_worker_and_finishes_the_existing_selection(self):
        job=self.start()
        self.reviews.inspect_one(job['id'],0)
        saved=self.reviews.row(job['id'])['payload']['entries'][0]
        self.dead_worker();self.reviews.start()
        result=self.wait_for_checks(job['id'])
        self.assertEqual(result['state'],'review_ready')
        self.assertEqual(result['payload']['entries'][0],saved)
        self.assertEqual(self.client.calls,[])

    def test_error_logging_failure_cannot_kill_the_read_worker(self):
        waits=0
        def wake(_):
            nonlocal waits
            waits+=1
            if waits==2:self.reviews.stop()
        with patch.object(self.reviews,'step',side_effect=[sqlite3.OperationalError('disk I/O error'),False]) as step, \
             patch.object(self.reviews.wake,'wait',side_effect=wake), \
             patch('traceback.print_exc',side_effect=OSError('Log disk unavailable')):
            self.reviews.loop()
        self.assertEqual(step.call_count,2)
        self.assertEqual(self.client.calls,[])

    def test_status_poll_recovers_a_dead_worker_only_once(self):
        job=self.start()
        self.dead_worker()
        with ThreadPoolExecutor(max_workers=12) as readers:
            responses=list(readers.map(lambda _:self.reviews.get(job['id']),range(12)))
        result=self.wait_for_checks(job['id'])
        self.assertEqual(result['state'],'review_ready')
        self.assertTrue(all(r['worker']['alive'] for r in responses))
        self.assertEqual(self.reviews.worker_status()['restart_count'],1)
        self.assertTrue(all(e['attempts']==1 for e in result['payload']['entries']))
        self.assertEqual(self.client.calls,[])

    def test_stopped_service_cannot_be_restarted_by_status_or_start(self):
        job=self.start();old=self.dead_worker();self.reviews.stop()
        self.reviews.start();status=self.reviews.get(job['id'])
        self.assertIs(self.reviews.thread,old)
        self.assertEqual(status['worker']['state'],'stopped')
        self.assertEqual(status['counts']['pending'],3)
        self.assertEqual(self.client.calls,[])

    def test_local_failure_is_reported_until_a_successful_pass(self):
        job=self.start();seen=[]
        def wake(_):
            seen.append(self.reviews.get(job['id']))
            if len(seen)==2:self.reviews.stop()
        with patch.object(self.reviews,'step',side_effect=[sqlite3.OperationalError('disk I/O error'),False]), \
             patch.object(self.reviews.wake,'wait',side_effect=wake),patch('traceback.print_exc'):
            self.reviews.loop()
        self.assertEqual(seen[0]['worker']['state'],'retrying')
        self.assertIn('disk I/O error',seen[0]['worker']['error'])
        self.assertEqual(seen[1]['worker']['error'],'')
        self.assertEqual(seen[0]['counts']['pending'],3)
        self.assertEqual(self.client.calls,[])

    def test_queue_is_durable_idempotent_and_cannot_delete(self):
        a=self.start();b=self.start();self.assertEqual(a['id'],b['id']);self.assertEqual(self.client.calls,[])
        with self.assertRaises(Conflict):self.start([TARGET],a['id'])
        replacement=DeletionReviews(self.app);replacement.step()
        r=replacement.get(a['id'],True)
        self.assertEqual(r['counts']['ready'],3);self.assertEqual(self.client.calls,[])
        self.assertTrue(all(e['plan']['expires_at']>time.time()+86000 for e in r['entries']))

    def test_181_files_one_failure_three_workers_preserves_180_results(self):
        ids=[]
        for index in range(181):
            fid='id:large'+str(index);ids.append(fid)
            self.cat.assets[fid]={**deepcopy(self.cat.assets[TARGET]),'id':fid,'name':str(index)+'.jpg'}
            self.cat.edges['A'][fid]=deepcopy(self.cat.edges['A'][TARGET])
            native=deepcopy(self.client.files[TARGET]);native.id=fid;native.name=str(index)+'.jpg'
            native.path_display='/BOLDSTONE MASTER/Products/01 Wall Sculptures/Test/'+native.name;native.path_lower=native.path_display.lower();self.client.files[fid]=native
        original=self.manager.runner;lock=threading.Lock();inflight=0;peak=0;counts={}
        def flaky(request):
            nonlocal inflight,peak
            fid=request['binding']['id']
            with lock:inflight+=1;peak=max(peak,inflight);counts[fid]=counts.get(fid,0)+1
            try:
                time.sleep(.002)
                if fid==ids[52]:raise NativeUnavailable('Temporary read failure',True)
                return original(request)
            finally:
                with lock:inflight-=1
        self.manager.runner=flaky;job=self.start(ids)
        for _ in range(3):self.reviews.step();self.release_retries(job['id'])
        result=self.reviews.get(job['id'],True)
        self.assertEqual(result['counts']['ready'],180);self.assertEqual(result['counts']['failed'],1)
        self.assertEqual(counts[ids[52]],3);self.assertTrue(all(counts[fid]==1 for fid in ids if fid!=ids[52]))
        self.assertGreater(peak,1);self.assertLessEqual(peak,3);self.assertEqual(self.client.calls,[])
        self.assertEqual(len(self.reviews.plan(job['id'])['files']),180)

    def test_retry_only_failed_preserves_ready_plans_and_detaches_old_unconfirmed_batch(self):
        original=self.manager.runner;calls=[]
        def fail(request):
            calls.append(request['binding']['id'])
            if request['binding']['id']==KEEPER:raise ValueError('Permission unavailable')
            return original(request)
        self.manager.runner=fail;job=self.start();self.finish();first=self.reviews.get(job['id'],True)
        ready={e['asset_id']:e['operation_id'] for e in first['entries'] if e['state']=='ready'}
        old=self.reviews.plan(job['id']);self.assertEqual(len(old['files']),2)
        self.manager.runner=original;self.reviews.retry(job['id']);self.finish();new=self.reviews.get(job['id'],True)
        self.assertEqual(new['counts']['ready'],3)
        self.assertEqual({e['asset_id']:e['operation_id'] for e in new['entries'] if e['asset_id'] in ready},ready)
        self.assertEqual(self.manager.batch(old['batch_id'])['state'],'superseded')
        self.assertEqual(len(self.reviews.plan(job['id'])['files']),3);self.assertEqual(self.client.calls,[])

    def test_retry_failed_after_partial_submission_never_requeues_submitted_files(self):
        original=self.manager.runner
        self.manager.runner=lambda r: (_ for _ in ()).throw(ValueError('Cannot read')) if r['binding']['id']==KEEPER else original(r)
        job=self.start();self.finish();p=self.reviews.plan(job['id'])
        queued=self.jobs.enqueue_deletion({'batch_id':p['batch_id'],'confirm_files':p['files'],'confirmed':True},True)
        self.reviews.submitted(p['batch_id']);self.manager.runner=original;self.jobs.step()
        self.reviews.retry(job['id']);self.finish();new=self.reviews.plan(job['id'])
        self.assertEqual([f['id'] for f in new['files']],[KEEPER])
        self.assertEqual({c[0] for c in self.client.calls},{TARGET,self.third})
        self.assertEqual(self.jobs.get(queued['id'])['state'],'completed')

    def test_old_ready_plans_are_reused_after_a_browser_failure(self):
        prepared=self.manager.prepare({'asset_id':TARGET,'reason':'unwanted'})
        original=self.manager.runner;calls=[]
        def counted(r):calls.append(r['binding']['id']);return original(r)
        self.manager.runner=counted;j=self.start([TARGET,KEEPER]);self.finish()
        entries=self.reviews.get(j['id'])['entries']
        self.assertEqual(entries[0]['operation_id'],prepared['operation_id']);self.assertEqual(calls,[KEEPER])

    def test_restart_rechecks_only_interrupted_reads(self):
        j=self.start();self.reviews.inspect_one(j['id'],0)
        row=self.reviews.row(j['id']);row['payload']['entries'][1]['state']='checking';self.reviews.write(row)
        original=self.manager.runner;calls=[]
        def counted(r):calls.append(r['binding']['id']);return original(r)
        self.manager.runner=counted;replacement=DeletionReviews(self.app);replacement.step()
        self.assertEqual(replacement.get(j['id'])['counts']['ready'],3);self.assertCountEqual(calls,[KEEPER,self.third])
        self.assertEqual(self.client.calls,[])

    def test_close_or_cancel_preserves_finished_checks_and_resume_finishes_pending(self):
        j=self.start();self.reviews.inspect_one(j['id'],0);self.reviews.cancel(j['id'])
        self.assertFalse(self.reviews.step());self.assertEqual(self.reviews.get(j['id'])['counts']['ready'],1)
        self.assertIn(j['id'],[x['id'] for x in self.reviews.snapshot()])
        self.reviews.retry(j['id']);self.finish();self.assertEqual(self.reviews.get(j['id'])['counts']['ready'],3)

    def test_context_change_before_final_plan_is_isolated_to_that_file(self):
        j=self.start();self.finish()
        self.store.save('image','A',TARGET,{'decision':'reviewed','uses':['advertising']},0,self.cat.source['register_sha256'],{})
        p=self.reviews.plan(j['id'])
        self.assertNotIn(TARGET,[f['id'] for f in p['files']]);self.assertEqual(len(p['files']),2)
        self.assertEqual(self.reviews.get(j['id'])['counts']['failed'],1);self.assertEqual(self.client.calls,[])

    def test_confirmation_uses_one_current_catalogue_view_for_all_members(self):
        j=self.start();self.finish()
        with patch.object(self.manager,'validation_view',wraps=self.manager.validation_view) as snapshot:
            p=self.reviews.plan(j['id'])
        self.assertEqual(len(p['files']),3)
        self.assertEqual(snapshot.call_count,1)
        self.assertEqual(self.client.calls,[])

    def test_busy_and_missing_files_do_not_block_independent_read_checks(self):
        p=self.manager.prepare({'asset_id':TARGET,'reason':'unwanted'})
        self.jobs.enqueue_deletion({'operation_id':p['operation_id'],'confirm_file_id':TARGET,'confirmed':True})
        self.client.gone.add(KEEPER);j=self.start();self.finish();r=self.reviews.get(j['id'],True)
        self.assertEqual(r['counts']['skipped'],1);self.assertEqual(r['counts']['ready'],2)
        self.assertEqual(next(e for e in r['entries'] if e['asset_id']==KEEPER)['plan']['file']['availability'],'missing')
        self.assertEqual(self.client.calls,[])

    def test_read_queue_works_while_native_writer_is_reserved(self):
        (self.store.root/'native-writer-reservation.json').write_text(json.dumps({'active':True}))
        j=self.start()
        with self.jobs.writer() as lease:
            self.assertTrue(lease);self.reviews.step()
        self.assertEqual(self.reviews.get(j['id'])['counts']['ready'],3)

    def test_selected_keeper_and_duplicate_aliases_rejected_before_reads(self):
        with self.assertRaisesRegex(ValueError,'keepers'):
            self.reviews.start_review({'request_id':'test-keeper-123','entries':[{'asset_id':TARGET,'reason':'duplicate','keeper_id':KEEPER},{'asset_id':KEEPER,'reason':'unwanted'}]})
        self.cat.canonical_assets={TARGET:TARGET,KEEPER:TARGET}
        with self.assertRaisesRegex(ValueError,'only once'):self.start()
        self.assertEqual(self.client.calls,[])

    def test_read_failures_are_classified_without_leaking_sdk_details(self):
        r=read_failure(TimeoutError('token=secret'));self.assertTrue(r['retryable']);self.assertFalse(r['delete_attempted']);self.assertNotIn('secret',r['error'])
        self.assertFalse(read_failure(ValueError('credential'))['retryable'])
        RateLimitError=type('RateLimitError',(Exception,),{'backoff':17})
        r=read_failure(RateLimitError());self.assertEqual(r['retry_after'],17);self.assertTrue(r['retryable'])

    def test_rate_limit_cooldown_prevents_issuing_more_reads_until_due(self):
        j=self.start();calls=[]
        def limited(r):calls.append(r);raise NativeUnavailable('Rate limited',True,60)
        self.manager.runner=limited
        with patch('deletion_reviews.time.time',return_value=1000):
            self.reviews.inspect_one(j['id'],0)
            self.assertFalse(self.reviews.step());self.assertEqual(len(calls),1)
        with patch('deletion_reviews.time.time',return_value=1061):
            self.assertTrue(self.reviews.step())

    def test_native_validation_failure_records_no_submission_and_continues(self):
        p=self.manager.prepare({'asset_id':TARGET,'reason':'unwanted'});original=self.client.files_get_metadata
        self.client.files_get_metadata=lambda *a,**kw:(_ for _ in ()).throw(TimeoutError())
        result=execute(self.client,p['file'],p['binding'],'/BOLDSTONE MASTER')
        self.assertEqual(result['state'],'check_failed');self.assertFalse(result['delete_attempted']);self.assertEqual(self.client.calls,[])
        self.client.files_get_metadata=original

    def test_cached_confirmation_with_new_context_is_rebuilt_for_the_valid_subset(self):
        j=self.start();self.finish();old=self.reviews.plan(j['id'])
        self.store.save('image','A',TARGET,{'decision':'reviewed','uses':['listing']},0,self.cat.source['register_sha256'],{})
        new=self.reviews.plan(j['id'])
        self.assertNotEqual(old['batch_id'],new['batch_id']);self.assertEqual(len(new['files']),2)
        self.assertNotIn(TARGET,[f['id'] for f in new['files']]);self.assertEqual(self.manager.batch(old['batch_id'])['state'],'superseded')

    def test_remaining_review_excludes_successes_and_is_idempotent(self):
        j=self.start();self.finish();p=self.reviews.plan(j['id'])
        queued=self.jobs.enqueue_deletion({'batch_id':p['batch_id'],'confirm_files':p['files'],'confirmed':True},True)
        self.client.files[TARGET].rev='changed';self.jobs.step()
        review=self.jobs.review_remaining(queued['id'])
        self.assertEqual([e['asset_id'] for e in review['entries']],[TARGET])
        self.assertEqual(self.jobs.review_remaining(queued['id'])['id'],review['id'])
        self.assertTrue(self.jobs.get(queued['id'])['can_review_remaining'])
        self.assertEqual({c[0] for c in self.client.calls},{KEEPER,self.third})

    def test_execution_retries_only_certified_unsubmitted_read_failures(self):
        p=self.manager.prepare({'asset_id':TARGET,'reason':'unwanted'});original=self.manager.runner;attempts=[]
        def flaky(r):
            attempts.append(r['action'])
            if len(attempts)<3:raise NativeUnavailable('Temporary read failed',True)
            return original(r)
        self.manager.runner=flaky
        with patch('deletions.time.sleep'):
            result=self.manager.execute({'operation_id':p['operation_id'],'confirm_file_id':TARGET,'confirmed':True})
        self.assertEqual(result['state'],'deleted');self.assertEqual(len(attempts),3);self.assertEqual(self.client.calls,[(TARGET,'a1')])

    def test_unknown_execution_transport_failure_is_never_retried(self):
        p=self.manager.prepare({'asset_id':TARGET,'reason':'unwanted'});attempts=[]
        def unknown(r):attempts.append(r);raise TimeoutError('Unknown mutation outcome')
        self.manager.runner=unknown
        result=self.manager.execute({'operation_id':p['operation_id'],'confirm_file_id':TARGET,'confirmed':True})
        self.assertEqual(result['state'],'uncertain');self.assertEqual(len(attempts),1)

    def test_publisher_change_before_queued_job_is_unattempted_and_reviewable(self):
        j=self.start();self.finish();p=self.reviews.plan(j['id'])
        queued=self.jobs.enqueue_deletion({'batch_id':p['batch_id'],'confirm_files':p['files'],'confirmed':True},True)
        with patch('deletions.check_sources',side_effect=SourceConflict('Catalogue publication changed')):
            self.jobs.step()
        self.assertEqual(self.jobs.get(queued['id'])['state'],'needs_review')
        self.assertEqual(self.client.calls,[])
        self.assertEqual(len(self.jobs.review_remaining(queued['id'])['entries']),3)

    def test_publisher_change_between_files_does_not_claim_unsubmitted_deletes(self):
        j=self.start();self.finish();p=self.reviews.plan(j['id'])
        queued=self.jobs.enqueue_deletion({'batch_id':p['batch_id'],'confirm_files':p['files'],'confirmed':True},True)
        # Structural validation and first member pass. The next two reads
        # detect a changed publisher source before making any native request.
        with patch('deletions.check_sources',side_effect=[None,None,SourceConflict('New source'),SourceConflict('New source')]):
            self.jobs.step()
        result=self.jobs.get(queued['id'])
        self.assertEqual(result['state'],'needs_review')
        self.assertEqual(self.client.calls,[(TARGET,'a1')])
        self.assertTrue(all(r['state']=='rejected' and r['delete_attempted'] is False for r in result['progress']['results'][1:]))

    def test_transient_local_storage_error_retries_read_without_losing_other_checks(self):
        original=self.manager.runner;calls=[]
        def unavailable(request):
            calls.append(request['binding']['id'])
            if request['binding']['id']==TARGET and calls.count(TARGET)==1:
                raise sqlite3.OperationalError('disk I/O error')
            return original(request)
        self.manager.runner=unavailable;job=self.start();self.reviews.step()
        first=self.reviews.get(job['id'],True)
        self.assertEqual(first['counts']['pending'],1);self.assertEqual(first['counts']['ready'],2)
        ready={e['asset_id']:e['operation_id'] for e in first['entries'] if e['state']=='ready'}
        failed=next(e for e in first['entries'] if e['asset_id']==TARGET)
        self.assertIn('local catalogue storage',failed['error']);self.assertTrue(failed['retryable'])
        self.release_retries(job['id']);self.finish()
        final=self.reviews.get(job['id'],True);self.assertEqual(final['counts']['ready'],3)
        self.assertEqual(calls.count(TARGET),2)
        self.assertTrue(all(e['operation_id']==ready[e['asset_id']] for e in final['entries'] if e['asset_id'] in ready))
        self.assertEqual(self.client.calls,[])

    def test_terminal_provider_diagnostics_survive_reload_without_private_payloads(self):
        def unavailable(request):
            raise NativeUnavailable('Dropbox is temporarily unavailable.',True,0,
                                    {'error_code':'ReadTimeout','http_status':503,'request_id':'request-safe-123',
                                     'response_body':'token=private','authorization':'private'})
        self.manager.runner=unavailable;job=self.start([TARGET])
        for _ in range(3):self.reviews.step();self.release_retries(job['id'])
        entry=DeletionReviews(self.app).get(job['id'])['entries'][0]
        self.assertEqual(entry['state'],'failed');self.assertEqual(entry['attempts'],3)
        self.assertEqual(entry['error_details'],{'error_code':'ReadTimeout','http_status':503,'request_id':'request-safe-123'})
        self.assertNotIn('private',json.dumps(entry));self.assertEqual(self.client.calls,[])

    def test_invalid_provider_diagnostics_are_not_saved_and_retry_success_clears_them(self):
        original=self.manager.runner
        def unavailable(request):
            raise NativeUnavailable('Temporary read error',True,0,
                                    {'error_code':'token=private','http_status':'private','request_id':'secret=private'})
        self.manager.runner=unavailable;job=self.start([TARGET]);self.reviews.step()
        entry=self.reviews.get(job['id'])['entries'][0]
        self.assertNotIn('private',json.dumps(entry));self.assertEqual(entry['error_details'],{'error_code':'NativeUnavailable'})
        self.manager.runner=original;self.release_retries(job['id']);self.finish()
        entry=self.reviews.get(job['id'])['entries'][0]
        self.assertEqual(entry['state'],'ready');self.assertEqual(entry.get('error_details'),{})
        self.assertEqual(self.client.calls,[])

    def test_nontransient_storage_error_is_not_retried_automatically(self):
        self.manager.runner=lambda request:(_ for _ in ()).throw(sqlite3.OperationalError('no such table: broken'))
        job=self.start([TARGET]);self.reviews.step()
        entry=self.reviews.get(job['id'])['entries'][0]
        self.assertEqual(entry['state'],'failed');self.assertFalse(entry['retryable']);self.assertEqual(entry['attempts'],1)
        self.assertEqual(self.client.calls,[])

    def test_persistent_temporary_storage_failure_has_bounded_attempts(self):
        def unavailable(request):
            error=sqlite3.OperationalError('Localized storage error')
            error.sqlite_errorcode=sqlite3.SQLITE_IOERR | (3 << 8)
            raise error
        self.manager.runner=unavailable;job=self.start([TARGET])
        for _ in range(5):self.reviews.step();self.release_retries(job['id'])
        entry=self.reviews.get(job['id'])['entries'][0]
        self.assertEqual(entry['state'],'failed');self.assertEqual(entry['attempts'],3)
        self.assertTrue(entry['retryable']);self.assertIn('local catalogue storage',entry['error'])
        self.assertEqual(self.client.calls,[])

    def test_retry_after_partial_confirmation_rebuilds_batch_without_submitting_deletion(self):
        original=self.manager.runner
        def unavailable(request):
            if request['binding']['id']==KEEPER:raise NativeUnavailable('Temporary read failure',True)
            return original(request)
        self.manager.runner=unavailable;job=self.start([TARGET,KEEPER])
        for _ in range(3):self.reviews.step();self.release_retries(job['id'])
        first=self.reviews.plan(job['id']);self.assertEqual([f['id'] for f in first['files']],[TARGET])
        first_operation=self.reviews.get(job['id'])['entries'][0]['operation_id']
        self.manager.runner=original;self.reviews.retry(job['id']);self.finish()
        second=self.reviews.plan(job['id'])
        self.assertNotEqual(first['batch_id'],second['batch_id'])
        self.assertEqual({f['id'] for f in second['files']},{TARGET,KEEPER})
        self.assertEqual(self.reviews.get(job['id'])['entries'][0]['operation_id'],first_operation)
        self.assertEqual(self.manager.batch(first['batch_id'])['state'],'superseded')
        self.assertEqual(self.manager.batch(second['batch_id'])['state'],'prepared')
        self.assertEqual(self.client.calls,[])

    def test_uncertain_move_still_holds_the_writer(self):
        with self.store.connect() as db:
            self.jobs.insert(db,'uncertain-move','organise',{'asset_id':TARGET})
        self.jobs.mark('uncertain-move','uncertain',{'message':'Unknown move outcome'})
        p=self.manager.prepare({'asset_id':KEEPER,'reason':'unwanted'})
        self.jobs.enqueue_deletion({'operation_id':p['operation_id'],'confirm_file_id':KEEPER,'confirmed':True})
        self.assertFalse(self.jobs.step());self.assertIsNotNone(self.jobs.snapshot()['reservation']);self.assertEqual(self.client.calls,[])

if __name__=='__main__':unittest.main()
