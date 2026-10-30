from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import test_deletions as fixtures
from delete_dropbox import CATALOGUE_ROOT, inspect_file, execute
from fetch_original import OriginalError
from projection import Projection

TARGET, KEEPER = fixtures.TARGET, fixtures.KEEPER


class NativeScopeTests(unittest.TestCase):
    setUp = fixtures.NativeDeletionTests.setUp

    def test_workshop_file_can_be_reviewed_and_deleted_within_catalogue_root(self):
        m = self.client.files[TARGET]
        m.path_display = CATALOGUE_ROOT + '/Products/Workshop and Moulding/Barbados/photo.jpg'
        m.path_lower = m.path_display.lower()
        reviewed = inspect_file(self.client, self.binding, CATALOGUE_ROOT)
        self.assertEqual(self.client.calls, [])
        result = execute(self.client, reviewed, self.binding, CATALOGUE_ROOT)
        self.assertEqual(result['state'], 'deleted')
        self.assertEqual(self.client.calls, [(TARGET, 'a1')])

    def test_similarly_named_root_and_non_image_are_rejected(self):
        self.client.files[TARGET].path_display = '/BOLDSTONE MASTER Backup/photo.jpg'
        with self.assertRaises(OriginalError):inspect_file(self.client, self.binding, CATALOGUE_ROOT)
        self.client.files[TARGET].path_display = CATALOGUE_ROOT + '/document.txt'
        self.client.files[TARGET].name = 'document.txt'
        with self.assertRaises(OriginalError):inspect_file(self.client, self.binding, CATALOGUE_ROOT)
        self.assertEqual(self.client.calls, [])

    def test_mismatched_identity_or_bytes_are_rejected(self):
        for field, value in [('id', KEEPER), ('size', 69), ('content_hash', 'b'*64)]:
            old = getattr(self.client.files[TARGET], field)
            setattr(self.client.files[TARGET], field, value)
            with self.assertRaises(OriginalError):inspect_file(self.client, self.binding, CATALOGUE_ROOT)
            setattr(self.client.files[TARGET], field, old)
        self.assertEqual(self.client.calls, [])

    def test_absence_is_distinct_from_lookup_failure(self):
        self.client.gone.add(TARGET)
        missing_file = inspect_file(self.client, self.binding, CATALOGUE_ROOT, allow_missing=True)
        self.assertEqual(missing_file['availability'], 'missing')
        self.assertIsNone(missing_file['revision'])
        def denied(*args, **kwargs):raise PermissionError('access denied')
        self.client.files_get_metadata = denied
        with self.assertRaises(PermissionError):inspect_file(self.client, self.binding, CATALOGUE_ROOT, allow_missing=True)
        self.assertEqual(self.client.calls, [])

    def test_missing_target_does_not_require_a_native_delete(self):
        self.client.gone.add(TARGET)
        result = execute(self.client, self.reviewed, self.binding, CATALOGUE_ROOT)
        self.assertEqual(result['state'], 'already_absent')
        self.assertTrue(result['verified_absent'])
        self.assertFalse(result['delete_attempted'])
        self.assertEqual(self.client.calls, [])

    def test_file_returning_after_absence_review_requires_new_review(self):
        self.client.gone.add(TARGET)
        reviewed = inspect_file(self.client, self.binding, CATALOGUE_ROOT, allow_missing=True)
        self.client.gone.remove(TARGET)
        with self.assertRaisesRegex(OriginalError, 'present again'):
            execute(self.client, reviewed, self.binding, CATALOGUE_ROOT)
        self.assertEqual(self.client.calls, [])


class UnavailableJobTests(unittest.TestCase):
    setUp = fixtures.DeletionJobTests.setUp
    tearDown = fixtures.DeletionJobTests.tearDown
    confirm = fixtures.DeletionJobTests.confirm

    def test_no_local_preview_or_original_metadata_does_not_block_native_review(self):
        self.cat.assets[TARGET]['original'] = {}
        self.cat.assets[TARGET]['local_preview'] = False
        self.cat.paths.pop(TARGET)
        plan = self.manager.prepare({'asset_id': TARGET, 'reason': 'unwanted'})
        self.assertEqual(plan['binding']['bytes'], 68)
        self.assertEqual(plan['binding']['content_hash'], 'a'*64)
        self.assertEqual(self.client.calls, [])
        result = self.manager.execute(self.confirm(plan))
        self.assertEqual(result['state'], 'deleted')

    def test_missing_entry_removal_is_confirmed_audited_and_not_native_deletion(self):
        self.client.gone.add(TARGET)
        plan = self.manager.prepare({'asset_id': TARGET, 'reason': 'unwanted'})
        self.assertEqual(plan['file']['availability'], 'missing')
        self.assertIn(TARGET, [a['id'] for a in Projection(self.cat, self.store.all()).library()])
        with self.assertRaises(ValueError):self.manager.execute({**self.confirm(plan), 'confirmed': False})
        result = self.manager.execute(self.confirm(plan))
        self.assertEqual(result['state'], 'already_absent')
        self.assertFalse(result['delete_attempted'])
        self.assertEqual(self.client.calls, [])
        self.assertNotIn(TARGET, [a['id'] for a in Projection(self.cat, self.store.all()).library()])
        self.assertEqual(self.manager.history()[0]['state'], 'already_absent')
        self.assertEqual(self.manager.execute(self.confirm(plan))['state'], 'already_absent')
        self.assertEqual(self.client.calls, [])

    def test_outside_live_inventory_keeps_affected_sculptures_in_review(self):
        self.cat.assets[TARGET]['source_unavailable'] = True
        self.client.gone.add(TARGET)
        plan = self.manager.prepare({'asset_id': TARGET, 'reason': 'unwanted'})
        self.assertEqual({r['id'] for r in plan['context']['products']}, {'A', 'B'})
        self.assertEqual(self.manager.execute(self.confirm(plan))['state'], 'already_absent')
        self.assertEqual(self.client.calls, [])

    def test_missing_keeper_is_not_accepted_for_duplicate_deletion(self):
        self.client.gone.add(KEEPER)
        with self.assertRaises(fixtures.Missing):
            self.manager.prepare({'asset_id': TARGET, 'reason': 'duplicate', 'keeper_id': KEEPER})
        self.assertEqual(self.client.calls, [])


class MixedBatchTests(unittest.TestCase):
    setUp = fixtures.DeletionBatchTests.setUp
    tearDown = fixtures.DeletionBatchTests.tearDown
    plans = fixtures.DeletionBatchTests.plans
    batch = fixtures.DeletionBatchTests.batch
    confirmation = fixtures.DeletionBatchTests.confirmation

    def test_mixed_missing_and_present_batch_continues_without_deleting_missing_target(self):
        self.client.gone.add(TARGET)
        batch = self.batch()
        self.assertIsNone(batch['files'][0]['revision'])
        result = self.manager.execute_batch(self.confirmation(batch))
        self.assertEqual(result['state'], 'completed')
        self.assertEqual([r['state'] for r in result['results']], ['already_absent', 'deleted'])
        self.assertEqual(self.client.calls, [(KEEPER, 'a1')])
        self.assertNotIn(TARGET, [a['id'] for a in Projection(self.cat, self.store.all()).library()])
        self.manager.execute_batch(self.confirmation(batch))
        self.assertEqual(self.client.calls, [(KEEPER, 'a1')])


if __name__ == '__main__':unittest.main()
