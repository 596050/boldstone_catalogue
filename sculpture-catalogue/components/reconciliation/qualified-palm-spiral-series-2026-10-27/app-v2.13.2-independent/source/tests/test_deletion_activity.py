from copy import deepcopy
from unittest.mock import patch
import json
import threading
import unittest

import test_background_jobs as background_fixtures
from test_deletions import TARGET, KEEPER
from deletion_activity import DeletionBusy


class DeletionActivityTests(unittest.TestCase):
    setUp = background_fixtures.BackgroundJobTests.setUp
    tearDown = background_fixtures.BackgroundJobTests.tearDown
    batch = background_fixtures.BackgroundJobTests.batch
    plans = background_fixtures.BackgroundJobTests.plans
    confirmation = background_fixtures.BackgroundJobTests.confirmation

    def prepare(self, fid=TARGET, keeper=None):
        return self.manager.prepare({'asset_id': fid, 'reason': 'duplicate' if keeper else 'unwanted', 'keeper_id': keeper or ''})

    def queue(self, review):
        return self.jobs.enqueue_deletion({'operation_id': review['operation_id'], 'confirm_file_id': review['file']['id'], 'confirmed': True})

    def test_busy_preflight_prevents_redundant_native_inspection(self):
        job = self.queue(self.prepare())
        with patch.object(self.manager, 'runner', side_effect=AssertionError('No redundant native inspection')):
            with self.assertRaises(DeletionBusy) as caught:
                self.prepare()
        self.assertEqual(caught.exception.details['busy_files'][0]['job_id'], job['id'])
        self.assertEqual(self.jobs.snapshot()['deletion_activity'][TARGET]['state'], 'queued')

    def test_atomic_mixed_selection_queues_only_free_file_and_duplicate_http_is_idempotent(self):
        batch = self.batch(); body = self.confirmation(batch)
        first = self.queue(self.prepare())
        second = self.jobs.enqueue_deletion(body, True)
        self.assertEqual([f['id'] for f in second['files']], [KEEPER])
        self.assertEqual(second['skipped'][0]['job_id'], first['id'])
        self.assertEqual(self.jobs.enqueue_deletion(body, True)['id'], second['id'])
        self.jobs.step(); self.jobs.step(); self.jobs.step()
        self.assertEqual([c[0] for c in self.client.calls], [TARGET, KEEPER])
        self.assertEqual(self.jobs.get(second['id'])['state'], 'completed')

    def test_unknown_result_reserves_only_its_file_and_other_jobs_continue(self):
        batch=self.batch();job=self.jobs.enqueue_deletion(self.confirmation(batch),True);real=self.manager.runner
        def fail_one(request):
            if request['action']=='execute' and request['binding']['id']==TARGET:raise TimeoutError()
            return real(request)
        self.manager.runner=fail_one;self.jobs.step()
        states=self.jobs.deletion_activity()
        self.assertEqual(states[TARGET]['state'],'uncertain');self.assertEqual(states[KEEPER]['state'],'deleted')
        self.manager.runner=real
        other=self.queue(self.prepare(self.third));self.assertTrue(self.jobs.step())
        self.assertEqual(self.jobs.get(other['id'])['state'],'completed')
        self.assertEqual(self.client.calls,[(KEEPER,'a1'),(self.third,'a1')])
        with self.assertRaises(DeletionBusy):self.prepare(TARGET)
        self.client.gone.add(TARGET)
        self.assertEqual(self.jobs.check(job['id'])['state'],'completed')
        self.assertEqual(self.client.calls,[(KEEPER,'a1'),(self.third,'a1')])

    def test_failed_preconditions_release_only_the_rejected_original(self):
        batch=self.batch();job=self.jobs.enqueue_deletion(self.confirmation(batch),True)
        self.client.files[TARGET].rev='changed';self.jobs.step()
        self.assertEqual(self.jobs.get(job['id'])['state'],'needs_review')
        self.assertEqual(self.jobs.deletion_activity()[KEEPER]['state'],'deleted')
        self.assertNotIn(TARGET,self.jobs.deletion_activity())
        other=self.queue(self.prepare(TARGET));self.jobs.step()
        self.assertEqual(self.jobs.get(other['id'])['state'],'completed')
        self.assertEqual(self.client.calls,[(KEEPER,'a1'),(TARGET,'changed')])

    def test_keeper_cannot_be_queued_for_deletion_until_its_job_finishes(self):
        keeper_review = self.prepare(KEEPER)
        job = self.queue(self.prepare(TARGET, KEEPER))
        self.assertEqual(self.jobs.deletion_activity()[KEEPER]['kind'], 'keeper')
        with self.assertRaises(DeletionBusy): self.queue(keeper_review)
        self.jobs.step()
        self.assertEqual(self.jobs.get(job['id'])['state'], 'completed')
        self.assertNotIn(KEEPER, self.jobs.deletion_activity())
        self.queue(self.prepare(KEEPER))

    def test_queued_deletion_cannot_be_selected_as_keeper_even_from_older_review(self):
        duplicate = self.prepare(TARGET, KEEPER)
        self.queue(self.prepare(KEEPER))
        with self.assertRaisesRegex(DeletionBusy, 'keeper'): self.prepare(TARGET, KEEPER)
        with self.assertRaisesRegex(DeletionBusy, 'keeper'): self.queue(duplicate)
        self.assertEqual(self.client.calls, [])

    def test_cancel_releases_target_and_keeper_and_does_not_delete(self):
        job = self.queue(self.prepare(TARGET, KEEPER))
        self.jobs.cancel(job['id'])
        self.assertEqual(self.jobs.deletion_activity(), {})
        self.queue(self.prepare(KEEPER))
        self.assertEqual(self.client.calls, [])

    def test_alias_of_busy_original_cannot_be_double_queued(self):
        self.cat.canonical_assets = {TARGET: TARGET, KEEPER: TARGET}
        self.cat.duplicate_members = {TARGET: [TARGET, KEEPER]}
        self.queue(self.prepare())
        with self.assertRaises(DeletionBusy): self.prepare(KEEPER)

    def test_mixed_selection_rollback_keeps_original_review_and_confirmation(self):
        batch = self.batch(); body = self.confirmation(batch)
        self.queue(self.prepare())
        before = deepcopy(self.manager.batch(batch['batch_id']))
        with patch.object(self.jobs, 'insert', side_effect=RuntimeError('full disk')):
            with self.assertRaises(RuntimeError): self.jobs.enqueue_deletion(body, True)
        self.assertEqual(self.manager.batch(batch['batch_id']), before)
        for oid in batch['operation_ids']:
            self.assertNotIn('queue_confirmed_at', self.manager.job(oid)['payload'])

    def test_filtering_does_not_weaken_exact_confirmation(self):
        batch = self.batch(); body = self.confirmation(batch)
        self.queue(self.prepare())
        with self.assertRaises(ValueError):
            self.jobs.enqueue_deletion({**body, 'confirm_files': body['confirm_files'][1:]}, True)
        with self.assertRaises(ValueError): self.jobs.enqueue_deletion({**body, 'confirmed': False}, True)
        self.assertEqual(self.client.calls, [])

    def test_two_concurrent_submissions_reserve_file_once(self):
        reviews = [self.prepare(), self.prepare()]; results = []; barrier = threading.Barrier(2)
        def submit(p):
            barrier.wait()
            try: results.append(self.queue(p)['state'])
            except DeletionBusy: results.append('busy')
        threads = [threading.Thread(target=submit, args=(p,)) for p in reviews]
        for t in threads: t.start()
        for t in threads: t.join(3)
        self.assertEqual(sorted(results), ['busy', 'queued'])
        self.jobs.step(); self.assertEqual(len(self.client.calls), 1)

    def test_readback_updates_completed_batch_progress_without_repeating_delete(self):
        batch = self.manager.prepare_batch({'operation_ids': [self.prepare()['operation_id']]})
        job = self.jobs.enqueue_deletion(self.confirmation(batch), True)
        real = self.manager.runner
        self.manager.runner = lambda r: (_ for _ in ()).throw(TimeoutError()) if r['action'] == 'execute' else real(r)
        self.jobs.step(); self.client.gone.add(TARGET); self.manager.runner = real
        checked = self.jobs.check(job['id'])
        self.assertEqual(checked['state'], 'completed')
        self.assertEqual(checked['progress']['state'], 'deleted')
        self.assertEqual(checked['progress']['results'][0]['state'], 'deleted')
        self.assertEqual(self.client.calls, [])


if __name__ == '__main__': unittest.main()
