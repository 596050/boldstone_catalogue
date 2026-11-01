import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'prepare_saatchi_catalogue.py'
spec = importlib.util.spec_from_file_location('prepare_saatchi_catalogue', SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class NativeBindingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'receipts.json'

    def load(self, rows):
        self.path.write_text(json.dumps(rows))
        return module.native_artwork_bindings(self.path)

    def receipt(self, sku='BOLD-TEST', native_id='14379999'):
        return {'sku': sku, 'artwork_id': native_id,
                'status': 'DRAFT_PRIMARY_ONLY_NOT_PUBLISHED'}

    def test_new_saved_draft_survives_preparation_reruns(self):
        first = self.load([self.receipt()])
        second = module.native_artwork_bindings(self.path)
        self.assertEqual(first, second)
        self.assertEqual(second['BOLD-TEST'], '14379999')
        self.assertEqual(second['SQ0717348'], '14226583')

    def test_same_sku_cannot_rebind_existing_native_record(self):
        with self.assertRaisesRegex(ValueError, 'Conflicting'):
            self.load([self.receipt('SQ0717348')])

    def test_same_native_record_cannot_belong_to_two_skus(self):
        with self.assertRaisesRegex(ValueError, 'multiple SKUs'):
            self.load([self.receipt(), self.receipt('BOLD-OTHER')])

    def test_interrupted_creation_is_not_treated_as_saved(self):
        row = self.receipt()
        row['status'] = 'IN_PROGRESS'
        with self.assertRaisesRegex(ValueError, 'unverified'):
            self.load([row])

    def test_malformed_receipts_fail_closed(self):
        for rows in ({'sku': 'BOLD-TEST'}, [None], [{'sku': 'BOLD-TEST'}]):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                self.load(rows)


class ChannelPrimaryTests(unittest.TestCase):
    def setUp(self):
        self.record = {'sku': 'BOLD-TEST'}
        self.photos = [
            {'id': 'id:small', 'role': 'primary', 'header_check': {'status': 'NEEDS_ATTENTION'}},
            {'id': 'id:full', 'role': 'listing', 'header_check': {'status': 'PASS_IMAGE_HEADER_CHECK'}},
        ]
        self.reviewed = [{'sku': 'BOLD-TEST', 'status': 'READY_FOR_CHANNEL_DRAFT',
                          'photo': {'photo_id': 'id:full'}}]

    def test_reviewed_alternative_does_not_reorder_catalogue(self):
        before = json.dumps(self.photos)
        chosen = module.channel_primary_selection(self.record, self.photos, [], self.reviewed)
        self.assertEqual(chosen['photo_id'], 'id:full')
        self.assertEqual(chosen['status'], 'READY_IMAGE')
        self.assertEqual(json.dumps(self.photos), before)

    def test_saved_channel_primary_survives_regeneration(self):
        receipt = [{'sku': 'BOLD-TEST', 'primary_photo_id': 'id:full'}]
        chosen = module.channel_primary_selection(self.record, self.photos, receipt, [])
        self.assertEqual(chosen['photo_id'], 'id:full')
        self.assertEqual(chosen['status'], 'READY_IMAGE')

    def test_removed_or_reclassified_saved_photo_requires_review(self):
        receipt = [{'sku': 'BOLD-TEST', 'primary_photo_id': 'id:full'}]
        for photos in (self.photos[:1], [self.photos[0], {**self.photos[1], 'role': 'in_situ'}]):
            with self.subTest(photos=photos):
                chosen = module.channel_primary_selection(self.record, photos, receipt, [])
                self.assertEqual(chosen['photo_id'], 'id:full')
                self.assertEqual(chosen['status'], 'NEEDS_IMAGE_REVIEW')

    def test_unreviewed_alternative_cannot_be_promoted(self):
        self.reviewed[0]['status'] = 'VERIFIED_FILE_FOR_VISUAL_REVIEW'
        with self.assertRaisesRegex(ValueError, 'Unreviewed'):
            module.channel_primary_selection(self.record, self.photos, [], self.reviewed)


if __name__ == '__main__':
    unittest.main()
