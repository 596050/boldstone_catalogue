import importlib.util
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'prepare_chairish_catalogue.py'
spec = importlib.util.spec_from_file_location('prepare_chairish_catalogue', SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ChairishPreparationTests(unittest.TestCase):
    def test_explicit_made_to_order_keeps_production_time_for_parcels(self):
        for text in ('Made to order', 'Made to order; unlimited order availability'):
            result = module.chairish_fulfilment(text, True)
            self.assertEqual(result['dispatch_working_days'], 10)
            self.assertEqual(result['period_made'], 'NOT_MADE')
            self.assertEqual(result['lead_time'], 'W2')

    def test_ready_or_unknown_availability_does_not_invent_production_facts(self):
        for text in ('Ready to dispatch', '', 'Not made to order'):
            result = module.chairish_fulfilment(text, True)
            self.assertEqual(result['dispatch_working_days'], 3)
            self.assertIsNone(result['period_made'])
            self.assertIsNone(result['lead_time'])
        self.assertEqual(module.chairish_fulfilment('', False)['dispatch_working_days'], 10)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.receipts = self.root / 'receipts.json'

    def bindings(self, rows):
        self.receipts.write_text(json.dumps(rows))
        return module.native_bindings(self.receipts)

    def test_interrupted_readback_preserves_known_native_id(self):
        rows = [{'sku': 'BOLD-A', 'id': '37950000', 'state': 'CREATED_PENDING_READBACK'}]
        self.assertEqual(self.bindings(rows), {'BOLD-A': '37950000'})
        self.assertEqual(module.native_bindings(self.receipts), {'BOLD-A': '37950000'})

    def test_explicit_axes_do_not_follow_text_order(self):
        d = module.chairish_dimensions('80 cm wide × 60 cm high × 5–8 cm deep')
        self.assertEqual(d['values'], {'width': '31.50', 'height': '23.62', 'depth': '3.15'})
        self.assertEqual(d['missing_axes'], [])
        self.assertTrue(d['uses_catalogue_upper_range'])

    def test_rectangular_unlabelled_axes_are_not_guessed(self):
        d = module.chairish_dimensions('Panel 200 × 100 × 5 cm; support framework 186 × 86 × 6.5 cm')
        self.assertEqual(d['values'], {'depth': '1.97'})
        self.assertEqual(d['missing_axes'], ['width', 'height'])

    def orientation_fixture(self):
        photo = self.root / 'photo.jpg'
        photo.write_bytes(b'reviewed photo fixture')
        digest = hashlib.sha256(photo.read_bytes()).hexdigest()
        record = {'sku': 'BOLD-A', 'catalogue_id': 'BSI-A', 'photos': [{'id': 'photo:A'}]}
        plan = module.chairish_dimensions('50 × 30 × 6 cm')
        review = {'sku': 'BOLD-A', 'catalogue_id': 'BSI-A', 'dimensions': plan['source'],
                  'status': 'ORIENTATION_REVIEWED', 'photo_id': 'photo:A', 'photo_sha256': digest,
                  'face_cm': {'width': 50, 'height': 30}, 'reviewed_utc': '2026-11-01',
                  'observation': 'Full face is clearly wider than tall.'}
        assets = [{'id': 'photo:A', 'sha256': digest, 'path': str(photo)}]
        return record, plan, review, assets

    def test_reviewed_orientation_preserves_measurements_and_depth(self):
        record, plan, review, assets = self.orientation_fixture()
        result = module.reviewed_orientation_dimensions(record, plan, review, assets)
        self.assertEqual(result['values'], {'width': '19.69', 'height': '11.81', 'depth': '2.36'})
        self.assertEqual(result['missing_axes'], [])
        self.assertEqual(plan['values'], {'depth': '2.36'})
        self.assertEqual(result['orientation_review']['photo_id'], 'photo:A')

    def test_orientation_review_stops_when_evidence_changes(self):
        for change in ('sku', 'catalogue_id', 'dimensions', 'photo_id', 'photo_sha256'):
            record, plan, review, assets = self.orientation_fixture()
            review[change] += '-changed'
            with self.subTest(change=change), self.assertRaises(ValueError):
                module.reviewed_orientation_dimensions(record, plan, review, assets)
        record, plan, review, assets = self.orientation_fixture()
        Path(assets[0]['path']).write_bytes(b'changed photo')
        with self.assertRaisesRegex(ValueError, 'Changed orientation photo bytes'):
            module.reviewed_orientation_dimensions(record, plan, review, assets)

    def test_orientation_cannot_invent_measurements_or_replace_explicit_axis(self):
        for face in ({'width': 60, 'height': 30}, {'width': 'NaN', 'height': 30},
                     {'width': 50}, {'width': 50, 'height': 30, 'depth': 6}):
            record, plan, review, assets = self.orientation_fixture()
            review['face_cm'] = face
            with self.subTest(face=face), self.assertRaises(ValueError):
                module.reviewed_orientation_dimensions(record, plan, review, assets)
        record, plan, review, assets = self.orientation_fixture()
        plan['values']['width'] = '11.81'
        with self.assertRaisesRegex(ValueError, 'conflicts with a labelled axis'):
            module.reviewed_orientation_dimensions(record, plan, review, assets)

    def test_ambiguous_or_removed_photo_cannot_assign_axes(self):
        record, plan, review, assets = self.orientation_fixture()
        review['status'] = 'NEEDS_ORIENTATION_CONFIRMATION'
        self.assertEqual(module.reviewed_orientation_dimensions(record, plan, review, assets), plan)
        review['status'] = 'ORIENTATION_REVIEWED'
        record['photos'] = []
        with self.assertRaisesRegex(ValueError, 'Stale orientation photo'):
            module.reviewed_orientation_dimensions(record, plan, review, assets)

    def test_square_panel_uses_single_component_not_arrangement(self):
        d = module.chairish_dimensions('35 × 35 cm per panel; approximately 6 cm deep; four-panel arrangement 70 × 70 cm')
        self.assertEqual(d['values'], {'width': '13.78', 'height': '13.78', 'depth': '2.36'})

    def test_basin_square_is_footprint_not_vertical_height(self):
        d = module.chairish_dimensions('45–60 cm square; 10–18 cm overall height')
        self.assertEqual(d['values'], {'width': '23.62', 'depth': '23.62', 'height': '7.09'})

    def test_diameter_and_fractional_depth(self):
        d = module.chairish_dimensions('50 cm diameter × 2.5 cm deep')
        self.assertEqual(d['values'], {'width': '19.69', 'height': '19.69', 'depth': '0.98'})

    def test_duplicate_or_shared_native_binding_stops_preparation(self):
        for rows in ([{'sku': 'A', 'id': '1'}, {'sku': 'A', 'id': '2'}],
                     [{'sku': 'A', 'id': '1'}, {'sku': 'B', 'id': '1'}]):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                self.bindings(rows)

    def test_malformed_receipts_are_not_treated_as_no_uploads(self):
        for rows in ({}, [None], [{'sku': 'A'}], [{'sku': 'A', 'id': '/create'}]):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                self.bindings(rows)

    def test_unapproved_image_host_is_rejected_before_network(self):
        with patch.object(module, 'urlopen') as request:
            result = module.checked_download((1, {'id': 'x', 'url': 'https://example.com/photo'}, self.root))
        request.assert_not_called()
        self.assertIn('Unexpected image host', result['error'])
        self.assertFalse(list(self.root.iterdir()))

    def test_download_failure_remains_explicit_without_fake_photo(self):
        photo = {'id': 'id:test', 'url': 'https://images.squarespace-cdn.com/test.jpg'}
        with patch.object(module, 'urlopen', side_effect=TimeoutError('timed out')):
            result = module.checked_download((1, photo, self.root))
        self.assertEqual(result['id'], photo['id'])
        self.assertIn('timed out', result['error'])
        self.assertNotIn('path', result)

    def test_rejected_small_photo_is_retained_as_explicit_gap(self):
        photos = [{'id': 'small', 'role': 'in_situ', 'dimensions': [272, 400]},
                  {'id': 'boundary', 'role': 'primary', 'dimensions': [575, 575]}]
        accepted, excluded = module.partition_upload_assets(photos)
        self.assertEqual([p['id'] for p in accepted], ['boundary'])
        self.assertEqual(excluded[0]['id'], 'small')
        self.assertEqual(excluded[0]['exclusion_reason'], 'BELOW_NATIVE_UPLOAD_MINIMUM')
        self.assertEqual(len(photos), 2)

    def test_later_eligible_photo_fills_slot_without_exceeding_cap(self):
        photos = [{'id': str(n), 'dimensions': [800, 800]} for n in range(21)]
        photos[1]['dimensions'] = [272, 400]
        accepted, excluded, overflow = module.choose_upload_assets(photos)
        self.assertEqual(len(accepted), 18)
        self.assertEqual([p['id'] for p in excluded], ['1'])
        self.assertEqual(accepted[-1]['id'], '18')
        self.assertEqual([p['id'] for p in overflow], ['19', '20'])

    def test_large_portrait_requests_bounded_cdn_rendition(self):
        from PIL import Image
        blobs = []
        for size in ((1500, 3000), (750, 1500)):
            stream = io.BytesIO()
            Image.new('RGB', size, 'white').save(stream, format='JPEG')
            blobs.append(stream.getvalue())
        photo = {'id': 'id:test', 'url': 'https://images.squarespace-cdn.com/test.jpg'}
        with patch.object(module, 'urlopen', side_effect=[io.BytesIO(b) for b in blobs]) as request:
            result = module.download_photo((1, photo, self.root))
        self.assertIn('format=1000w', request.call_args_list[1].args[0])
        self.assertEqual(result['source_dimensions'], [1500, 3000])
        self.assertEqual(result['dimensions'], [750, 1500])
        self.assertEqual(Path(result['path']).read_bytes(), blobs[1])


if __name__ == '__main__':
    unittest.main()
