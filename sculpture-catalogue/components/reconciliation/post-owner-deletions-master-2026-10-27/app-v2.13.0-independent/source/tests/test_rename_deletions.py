from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
import hashlib
import json
import tempfile
import unittest

from test_deletions import FakeDropbox, TARGET, KEEPER, ROOT
import test_background_jobs as background_fixtures
from delete_dropbox import inspect_file, execute, validate_review
from fetch_original import OriginalError
from rename_reconciliation import verified_rename
from store import Conflict


def save_json(path, value):
    path.write_text(json.dumps(value))
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rename_fixture(root, client, fid=TARGET):
    """Make an independent before/after evidence chain, using fake files only."""
    meta = client.files[fid]
    before = {'id': fid, 'name': meta.name, 'path': meta.path_display, 'rev': meta.rev,
              'content_hash': meta.content_hash, 'size': meta.size, 'parent_id': 'id:folder'}
    meta.name = 'renamed-' + meta.name
    meta.path_display = str(Path(meta.path_display).with_name(meta.name))
    meta.path_lower = meta.path_display.lower()
    meta.rev = 'a2'
    after = {**before, 'name': meta.name, 'path': meta.path_display, 'rev': meta.rev,
             'renamed': True, 'source_path_before': before['path'], 'source_name_before': before['name']}
    manifest, proof, readback = root/'manifest.json', root/'verification.json', root/'readback.json'
    manifest_hash = save_json(manifest, {'groups': [{'files': [before]}]})
    proof_hash = save_json(proof, {'status': 'PASS', 'errors': [], 'manifest': str(manifest), 'manifest_sha256': manifest_hash})
    digest = save_json(readback, {'namespace_id': '202238505', 'verification': str(proof),
                               'verification_sha256': proof_hash, 'files': [after]})
    save_json(root/'filename-readback.json', {'path': str(readback), 'sha256': digest})
    return before, after


class RenameProofTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name); self.client = FakeDropbox()
        self.binding = {'id': TARGET, 'content_hash': 'a'*64, 'bytes': 68}
        self.reviewed = inspect_file(self.client, self.binding, ROOT)
        self.before, self.after = rename_fixture(self.root, self.client)
        self.current = inspect_file(self.client, self.binding, ROOT)

    def rewrite_chain(self, *, manifest=None, proof=None, readback=None):
        m = manifest or json.loads((self.root/'manifest.json').read_text())
        p = proof or json.loads((self.root/'verification.json').read_text())
        r = readback or json.loads((self.root/'readback.json').read_text())
        p['manifest_sha256'] = save_json(self.root/'manifest.json', m)
        r['verification_sha256'] = save_json(self.root/'verification.json', p)
        save_json(self.root/'filename-readback.json', {'path': str(self.root/'readback.json'),
                  'sha256': save_json(self.root/'readback.json', r)})

    def test_validation_is_read_only_and_execution_uses_current_conditional_revision(self):
        result = validate_review(self.client, self.reviewed, self.binding, ROOT, rename_runtime=self.root)
        self.assertEqual(self.client.calls, [])
        self.assertEqual(result['rename_reconciliation']['reviewed_revision'], 'a1')
        result = execute(self.client, self.reviewed, self.binding, ROOT, rename_runtime=self.root)
        self.assertEqual(result['state'], 'deleted')
        self.assertEqual(self.client.calls, [(TARGET, 'a2')])
        self.assertEqual(result['rename_reconciliation']['current_name'], 'renamed-target.jpg')

    def test_original_review_alone_never_accepts_a_different_revision(self):
        with self.assertRaises(OriginalError):
            execute(self.client, self.reviewed, self.binding, ROOT)
        self.assertEqual(self.client.calls, [])

    def test_changed_content_size_parent_revision_and_sharing_reject(self):
        for key, value in [('content_hash', 'b'*64), ('size', 69), ('rev', 'a3'),
                           ('path_display', ROOT+'/Another/renamed-target.jpg')]:
            with self.subTest(key=key):
                old = getattr(self.client.files[TARGET], key)
                setattr(self.client.files[TARGET], key, value)
                with self.assertRaises(OriginalError):
                    execute(self.client, self.reviewed, self.binding, ROOT, rename_runtime=self.root)
                setattr(self.client.files[TARGET], key, old)
        from types import SimpleNamespace
        self.client.links = [SimpleNamespace(url='https://www.dropbox.com/new', name='new', path_lower='/shared')]
        with self.assertRaises(OriginalError):
            execute(self.client, self.reviewed, self.binding, ROOT, rename_runtime=self.root)
        self.assertEqual(self.client.calls, [])

    def test_tampered_readback_verification_and_manifest_each_reject(self):
        for filename in ('readback.json', 'verification.json', 'manifest.json'):
            with self.subTest(filename=filename):
                path = self.root/filename; raw = path.read_bytes(); path.write_bytes(raw+b' ')
                with self.assertRaises(ValueError): verified_rename(self.root, self.reviewed, self.current)
                path.write_bytes(raw)

    def test_wrong_namespace_failed_verification_or_ambiguous_id_reject(self):
        original = {p.name: p.read_bytes() for p in self.root.iterdir()}
        cases = [dict(readback={'namespace_id': 'wrong'}),
                 dict(proof={'status': 'FAIL'}), dict(proof={'errors': ['unverified']}),
                 dict(readback={'files': [self.after, self.after]}),
                 dict(readback={'files': [{**self.after, 'parent_id': 'id:another'}]}),
                 dict(manifest={'groups': [{'files': [{**self.before, 'rev': 'not-reviewed'}]}]})]
        for changes in cases:
            with self.subTest(changes=changes):
                args = {k: {**json.loads((self.root/({'proof':'verification'}.get(k,k)+'.json')).read_text()), **v}
                        for k,v in changes.items()}
                self.rewrite_chain(**args)
                with self.assertRaises(ValueError): verified_rename(self.root, self.reviewed, self.current)
                for name, raw in original.items(): (self.root/name).write_bytes(raw)

    def test_keeper_change_still_rejects_even_when_target_rename_is_proven(self):
        keeper = inspect_file(self.client, {'id': KEEPER}, ROOT)
        self.client.files[KEEPER].rev = 'changed'
        with self.assertRaises(OriginalError):
            execute(self.client, self.reviewed, self.binding, ROOT, keeper, self.root)
        self.assertEqual(self.client.calls, [])

    def test_lost_native_response_keeps_rename_audit_and_never_resubmits(self):
        self.client.after_delete_error = True
        result = execute(self.client, self.reviewed, self.binding, ROOT, rename_runtime=self.root)
        self.assertEqual(result['state'], 'deleted'); self.assertTrue(result['delete_attempted'])
        self.assertIn('rename_reconciliation', result); self.assertEqual(len(self.client.calls), 1)

    def test_missing_or_restored_image_does_not_receive_rename_authority(self):
        self.client.gone.add(TARGET)
        result = validate_review(self.client, self.reviewed, self.binding, ROOT, rename_runtime=self.root)
        self.assertIsNone(result['rename_reconciliation'])
        self.client.gone.clear()
        with self.assertRaises(OriginalError):
            execute(self.client, {**self.reviewed, 'availability':'missing'}, self.binding, ROOT, rename_runtime=self.root)
        self.assertEqual(self.client.calls, [])


class RenameRecoveryTests(unittest.TestCase):
    setUp = background_fixtures.BackgroundJobTests.setUp
    tearDown = background_fixtures.BackgroundJobTests.tearDown
    plans = background_fixtures.BackgroundJobTests.plans
    batch = background_fixtures.BackgroundJobTests.batch
    confirmation = background_fixtures.BackgroundJobTests.confirmation
    enqueue = background_fixtures.BackgroundJobTests.enqueue

    def rejected(self, fid=TARGET):
        job, body = self.enqueue()
        # Reproduce the old app's rejection before the verification exists.
        before, after = rename_fixture(self.store.root, self.client, fid)
        pointer = self.store.root/'filename-readback.json'; data = pointer.read_bytes(); pointer.unlink()
        self.jobs.step(); pointer.write_bytes(data)
        self.assertEqual(self.jobs.get(job['id'])['state'], 'needs_review')
        return job, body

    def test_future_queued_delete_survives_verified_rename_without_fresh_confirmation(self):
        job, _ = self.enqueue(); rename_fixture(self.store.root, self.client)
        self.jobs.step()
        result = self.jobs.get(job['id'])
        self.assertEqual(result['state'], 'completed')
        self.assertEqual(self.client.calls, [(TARGET,'a2'), (KEEPER,'a1')])
        self.assertEqual(result['progress']['results'][0]['rename_reconciliation']['current_revision'], 'a2')

    def test_recovery_is_linked_atomic_and_idempotent_preserving_original_review(self):
        job, _ = self.rejected()
        oid = self.jobs.get(job['id'])['progress']['results'][0]['operation_id']
        old = self.manager.job(oid)
        new = self.jobs.resume_rename(job['id'])
        self.assertEqual(new['state'], 'queued'); self.assertEqual(self.client.calls, [(KEEPER,'a1')])
        self.assertEqual(self.manager.job(oid), old)
        clone = self.manager.job('rename-'+oid)
        self.assertEqual(clone['payload']['file'], old['payload']['file'])
        self.assertEqual(clone['payload']['queue_confirmed_at'], old['payload']['queue_confirmed_at'])
        self.assertEqual(self.jobs.resume_rename(job['id'])['id'], new['id'])
        with patch('deletions.time.time', return_value=9999999999): self.jobs.step()
        self.assertEqual(self.jobs.get(new['id'])['state'], 'completed')
        self.assertEqual(self.jobs.resume_rename(job['id'])['id'], new['id'])
        self.assertFalse(self.jobs.step()); self.assertEqual(len(self.client.calls), 2)

    def test_completed_batch_members_are_never_repeated(self):
        job, _ = self.rejected(KEEPER)
        self.assertEqual(self.client.calls, [(TARGET,'a1')])
        new = self.jobs.resume_rename(job['id'])
        self.assertEqual([f['id'] for f in new['files']], [KEEPER])
        self.jobs.step(); self.assertEqual(self.client.calls, [(TARGET,'a1'), (KEEPER,'a2')])

    def test_recovery_cannot_reset_an_uncertain_or_attempted_operation(self):
        job, _ = self.rejected()
        oid = self.jobs.get(job['id'])['progress']['results'][0]['operation_id']
        for state, result in [('uncertain',{}), ('rejected',{'delete_attempted':True})]:
            with self.store.connect() as db:
                db.execute('UPDATE deletion_jobs SET state=?,result=? WHERE id=?', (state,json.dumps(result),oid))
            with self.assertRaises(Conflict): self.jobs.resume_rename(job['id'])
        self.assertEqual(self.client.calls, [(KEEPER,'a1')])

    def test_changed_context_during_native_validation_rolls_back_recovery(self):
        job, _ = self.rejected(); runner = self.manager.runner
        def race(request):
            result = runner(request)
            if request['action'] == 'validate' and request['binding']['id'] == TARGET:
                self.store.save('image','A',TARGET,{'decision':'reviewed','uses':['listing']},0,self.cat.source['register_sha256'],{})
            return result
        self.manager.runner = race
        with self.assertRaisesRegex(Conflict, 'catalogue use'): self.jobs.resume_rename(job['id'])
        self.assertEqual(self.jobs.get(job['id'])['state'], 'needs_review')
        self.assertEqual(self.client.calls, [(KEEPER,'a1')])

    def test_failed_outbox_commit_rolls_back_replacement_operations_and_old_state(self):
        job, _ = self.rejected()
        with self.store.connect() as db: count = db.execute('SELECT COUNT(*) FROM deletion_jobs').fetchone()[0]
        with patch.object(self.jobs, 'insert', side_effect=RuntimeError('disk full')):
            with self.assertRaises(RuntimeError): self.jobs.resume_rename(job['id'])
        with self.store.connect() as db: self.assertEqual(db.execute('SELECT COUNT(*) FROM deletion_jobs').fetchone()[0], count)
        self.assertEqual(self.jobs.get(job['id'])['state'], 'needs_review')
        self.assertEqual(self.client.calls, [(KEEPER,'a1')])

    def test_change_after_recovery_queue_is_checked_again_at_execution(self):
        job, _ = self.rejected(); new = self.jobs.resume_rename(job['id'])
        self.client.files[TARGET].rev = 'a3'; self.jobs.step()
        self.assertEqual(self.jobs.get(new['id'])['state'], 'needs_review')
        self.assertEqual(self.client.calls, [(KEEPER,'a1')])

    def test_unconfirmed_review_and_cancelled_job_cannot_be_resumed(self):
        job, _ = self.rejected()
        oid = self.jobs.get(job['id'])['progress']['results'][0]['operation_id']
        p = self.manager.job(oid)['payload']; del p['queue_confirmed_at']
        with self.store.connect() as db: db.execute('UPDATE deletion_jobs SET payload=? WHERE id=?', (json.dumps(p),oid))
        with self.assertRaises(Conflict): self.jobs.resume_rename(job['id'])
        self.jobs.mark(job['id'], 'cancelled', {})
        with self.assertRaises(Conflict): self.jobs.resume_rename(job['id'])
        self.assertEqual(self.client.calls, [(KEEPER,'a1')])

    def test_single_job_recovers_without_a_batch_and_history_is_preserved(self):
        review = self.manager.prepare({'asset_id': TARGET, 'reason': 'unwanted'})
        job = self.jobs.enqueue_deletion({'operation_id': review['operation_id'], 'confirm_file_id': TARGET, 'confirmed': True})
        rename_fixture(self.store.root, self.client)
        pointer = self.store.root/'filename-readback.json'; raw = pointer.read_bytes(); pointer.unlink()
        self.jobs.step(); pointer.write_bytes(raw)
        new = self.jobs.resume_rename(job['id']); self.jobs.step()
        self.assertEqual(self.jobs.get(new['id'])['state'], 'completed')
        self.assertEqual(self.client.calls, [(TARGET,'a2')])
        self.assertEqual(self.manager.job(review['operation_id'])['state'], 'rejected')

    def test_unattempted_batch_member_failure_remains_visible_in_progress(self):
        job, _ = self.enqueue(); real = self.manager.runner
        def change_second(request):
            result = real(request)
            if request['action'] == 'execute' and request['binding']['id'] == TARGET:
                self.store.save('image','B',KEEPER,{'decision':'reviewed','uses':['listing']},0,self.cat.source['register_sha256'],{})
            return result
        self.manager.runner = change_second; self.jobs.step()
        result = self.jobs.get(job['id'])['progress']['results'][1]
        self.assertEqual(result['state'], 'rejected')
        self.assertIn('catalogue use changed', result['message'])
        self.assertIs(result['delete_attempted'], False)
        self.assertEqual(self.client.calls, [(TARGET,'a1')])

    def test_check_retains_attempt_identity_and_rename_audit_after_lost_readback(self):
        job, _ = self.enqueue(); rename_fixture(self.store.root, self.client); runner = self.manager.runner
        def lost_readback(request):
            result = runner(request)
            if request['action'] == 'execute' and request['binding']['id'] == TARGET:
                result.update(state='uncertain', verified_absent=False, message='Readback unavailable')
            return result
        self.manager.runner = lost_readback; self.jobs.step()
        oid = self.jobs.get(job['id'])['progress']['results'][0]['operation_id']
        original = self.manager.job(oid)['result']
        self.manager.runner = runner; result = self.manager.check({'operation_id': oid})
        self.assertEqual(result['state'], 'deleted')
        self.assertTrue(result['delete_attempted'])
        self.assertEqual(result['confirmation_at'], original['confirmation_at'])
        self.assertEqual(result['rename_reconciliation'], original['rename_reconciliation'])
        self.assertNotIn('message', result)
        self.assertEqual(self.client.calls, [(TARGET,'a2'),(KEEPER,'a1')])

    def test_other_active_deletion_blocks_recovery_without_repeating_any_action(self):
        job, _ = self.rejected()
        review = self.manager.prepare({'asset_id': TARGET, 'reason': 'unwanted'})
        self.jobs.enqueue_deletion({'operation_id': review['operation_id'], 'confirm_file_id': TARGET, 'confirmed': True})
        with self.assertRaisesRegex(Conflict, 'another deletion'): self.jobs.resume_rename(job['id'])
        self.assertEqual(self.client.calls, [(KEEPER,'a1')])

    def test_history_filename_comes_from_native_review_not_stale_catalogue(self):
        job, _ = self.enqueue()
        self.cat.assets[TARGET]['name'] = 'stale-name.jpg'
        self.assertEqual(self.jobs.get(job['id'])['files'][0]['name'], 'target.jpg')
