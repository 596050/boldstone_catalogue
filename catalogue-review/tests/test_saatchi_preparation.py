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

    def test_verified_published_record_survives_preparation_reruns(self):
        row = self.receipt()
        row.update(status='PUBLISHED_NATIVE_READBACK_VERIFIED',
                   verified_visibility='Published',
                   public_url='https://www.saatchiart.com/en-gb/art/Sculpture-Test/1/14379999/view',
                   publication_evidence='evidence/published-overview.txt',
                   verified_utc='2026-11-05T18:00:00+00:00')
        first = self.load([row])
        self.assertEqual(first['BOLD-TEST'], '14379999')
        self.assertEqual(first, module.native_artwork_bindings(self.path))

    def test_published_label_without_matching_readback_cannot_create_binding(self):
        valid = dict(self.receipt(), status='PUBLISHED_NATIVE_READBACK_VERIFIED',
                     verified_visibility='Published',
                     public_url='https://www.saatchiart.com/en-gb/art/Sculpture-Test/1/14379999/view',
                     publication_evidence='evidence/published-overview.txt',
                     verified_utc='2026-11-05T18:00:00+00:00')
        for patch in ({'verified_visibility': 'Draft'}, {'publication_evidence': ''},
                      {'verified_utc': ''}, {'public_url': None}, {'public_url': []},
                      {'public_url': 'https://example.com/14379999/view'},
                      {'public_url': 'https://www.saatchiart.com/art/14378888/view'}):
            with self.subTest(patch=patch), self.assertRaisesRegex(ValueError, 'unverified'):
                self.load([{**valid, **patch}])

    def test_malformed_receipts_fail_closed(self):
        for rows in ({'sku': 'BOLD-TEST'}, [None], [{'sku': 'BOLD-TEST'}]):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                self.load(rows)


class CrateRequirementTests(unittest.TestCase):
    def test_exact_twelve_inches_requires_crate(self):
        self.assertIs(module.crate_required([30.48, 20, 5], 1), True)

    def test_exact_five_pounds_requires_crate(self):
        self.assertIs(module.crate_required([20, 20, 5], 2.26796185), True)

    def test_known_trigger_does_not_need_other_measurements(self):
        self.assertIs(module.crate_required([], 3), True)
        self.assertIs(module.crate_required([40], None), True)

    def test_missing_measurements_cannot_approve_box(self):
        for dimensions, weight in [([], None), ([], 1), ([20, 20, 5], None), ([20], 1)]:
            with self.subTest(dimensions=dimensions, weight=weight):
                self.assertIsNone(module.crate_required(dimensions, weight))
        self.assertIs(module.crate_required([20, 20, 5], 1), False)

    def test_invalid_measurements_are_not_treated_as_small(self):
        for value in [0, -1, float('nan'), float('inf'), True, '20']:
            with self.subTest(value=value), self.assertRaises(ValueError):
                module.crate_required([value, 20, 5], 1)


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
