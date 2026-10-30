from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from pathlib import Path
import json
import sqlite3
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from catalogue import digest
import live_review
from live_review import SourceConflict, effective_document, prepare, read_prepared, writer_lock
from store import ReviewStore
import test_review


class LiveReviewTests(unittest.TestCase):
    tearDown = test_review.ReviewTests.tearDown

    def setUp(self):
        test_review.ReviewTests.setUp(self)
        self.cat.project = self.root
        base = self.root / 'sculpture-catalogue'
        base.mkdir()
        register, gallery = base / 'register.json', base / 'complete-image-platform-register.sqlite'
        register.write_text('{"snapshot":1}')
        gallery.write_bytes(b'fixture-gallery-1')
        self.cat.source = {'register': str(register), 'gallery_database': str(gallery),
                           'register_sha256': digest(register), 'gallery_sha256': digest(gallery)}
        (base / 'current-master.json').write_text(json.dumps({
            'register': register.name, 'register_sha256': digest(register),
            'current_published_gallery_projection': {'path': 'index.html'}}))
        self.output = self.root / 'prepared'
        self.cat.products['A']['primary_id'] = 'image'

    def save(self, kind, pid, item, value, version=0, source_hash=None):
        from store import validate
        return self.store.save(kind, pid, item, validate(kind, value), version,
                               source_hash or self.cat.source['register_sha256'], {'source': 'original'})

    def test_excluding_primary_keeps_original_and_other_product(self):
        self.save('image', 'A', 'image', {'decision': 'reviewed', 'uses': ['listing'], 'primary': True})
        self.save('image', 'B', 'image', {'decision': 'reviewed', 'uses': ['listing'], 'primary': True})
        self.save('image', 'A', 'image', {'decision': 'exclude', 'uses': ['listing'], 'primary': True}, 1)
        original = self.image.read_bytes()
        prepare(self.cat, self.store, self.output)
        doc, manifest = read_prepared(self.output, self.cat.source)
        a, b = doc['products']['A'], doc['products']['B']
        self.assertEqual(a['source_reference_primary_id'], 'image')
        self.assertIsNone(a['effective_primary_id'])
        self.assertEqual(a['selected_listing_image_ids'], [])
        self.assertEqual(a['images']['image']['eligible_uses'], [])
        self.assertEqual(b['effective_primary_id'], 'image')
        self.assertEqual(self.image.read_bytes(), original)
        self.assertFalse(manifest['authoritative'])
        self.save('image', 'A', 'image', {'decision': 'reviewed', 'uses': ['advertising']}, 2)
        prepare(self.cat, self.store, self.output)
        doc, _ = read_prepared(self.output, self.cat.source)
        self.assertEqual(doc['products']['A']['images']['image']['eligible_uses'], ['advertising'])

    def test_estimated_edit_and_omission_retain_evidence(self):
        self.save('field', 'A', 'Weight', {'decision': 'edit', 'value': '7 kg', 'certainty': 'estimate'})
        self.save('field', 'B', 'Weight', {'decision': 'exclude'})
        doc = effective_document(self.cat, self.store.snapshot())
        weight = doc['products']['A']['fields']['Weight']
        self.assertEqual(weight['effective_value'], '7 kg')
        self.assertEqual(weight['certainty'], 'estimate')
        self.assertEqual(weight['original']['value'], '6 kg — estimate')
        self.assertEqual(weight['source_qualification'], 'Not weighed')
        self.assertIsNone(doc['products']['B']['fields']['Weight']['effective_value'])
        self.assertEqual(doc['products']['B']['fields']['Weight']['original']['value'], '6 kg — estimate')

    def test_move_preserves_audit_but_not_destination_use_approval(self):
        self.cat.edges['B'] = {}
        self.save('image', 'A', 'image', {'decision': 'reviewed', 'uses': ['listing'], 'primary': True})
        result = self.store.assign([
            {'product_id': pid, 'asset_id': 'image', 'version': 0,
             'data': {'state': state, 'from_product_id': 'A', 'to_product_id': 'B'}}
            for pid, state in [('A', 'removed'), ('B', 'attached')]],
            self.cat.source['register_sha256'], 'Move A to B')
        doc = effective_document(self.cat, self.store.snapshot())
        self.assertEqual(doc['products']['A']['images']['image']['eligible_uses'], [])
        self.assertEqual(doc['products']['B']['images']['image']['eligible_uses'], [])
        self.assertIsNone(doc['products']['A']['effective_primary_id'])
        self.assertEqual(doc['review_snapshot']['operations'][0]['id'], result['operation_id'])
        self.store.undo_assignment(result['operation_id'], self.cat.source['register_sha256'])
        doc = effective_document(self.cat, self.store.snapshot())
        self.assertEqual(doc['products']['A']['effective_primary_id'], 'image')
        self.assertNotIn('image', doc['products']['B']['images'])

    def test_conflicting_aliases_are_retained_but_withheld(self):
        self.cat.assets['platform'] = {**deepcopy(self.cat.assets['image']), 'id': 'platform', 'source': 'Shopify'}
        self.cat.canonical_assets = {'image': 'image', 'platform': 'image'}
        self.cat.duplicate_members = {'image': ['image', 'platform']}
        self.save('image', 'A', 'image', {'decision': 'reviewed', 'uses': ['listing'], 'primary': True})
        self.save('image', 'A', 'platform', {'decision': 'exclude'})
        self.save('asset', '', 'image', {'types': ['product'], 'tags': ['garden'], 'rights': 'owned'})
        self.save('asset', '', 'platform', {'types': ['in_situ'], 'tags': ['autumn'], 'rights': 'restricted'})
        doc = effective_document(self.cat, self.store.snapshot())
        self.assertEqual(list(doc['assets']), ['image'])
        self.assertIn('platform', doc['assets']['image']['aliases'])
        self.assertEqual(set(doc['assets']['image']['effective']['types']), {'product', 'in_situ'})
        self.assertEqual(doc['products']['A']['selected_listing_image_ids'], [])
        self.assertTrue(doc['products']['A']['images']['image']['withheld_reasons'])

    def test_source_change_and_stale_review_leave_previous_generation(self):
        prepare(self.cat, self.store, self.output)
        previous = (self.output / 'current.json').read_bytes()
        self.save('field', 'A', 'Weight', {'decision': 'edit', 'value': '8 kg'}, source_hash='old-register')
        with self.assertRaises(SourceConflict):
            prepare(self.cat, self.store, self.output)
        self.assertEqual((self.output / 'current.json').read_bytes(), previous)
        self.assertEqual(json.loads((self.output / 'status.json').read_text())['status'], 'conflict')
        Path(self.cat.source['register']).write_text('changed')
        with self.assertRaises(SourceConflict):
            prepare(self.cat, self.store, self.output)
        self.assertEqual((self.output / 'current.json').read_bytes(), previous)

    def test_pointer_change_with_intact_old_source_is_rejected(self):
        path = self.root / 'sculpture-catalogue/current-master.json'
        pointer = json.loads(path.read_text())
        pointer['register_sha256'] = 'different-published-source'
        path.write_text(json.dumps(pointer))
        with self.assertRaises(SourceConflict):
            prepare(self.cat, self.store, self.output)
        self.assertFalse((self.output / 'current.json').exists())

    def test_commit_failure_keeps_valid_previous_and_retry_is_idempotent(self):
        prepare(self.cat, self.store, self.output)
        previous = (self.output / 'current.json').read_bytes()
        self.save('image', 'A', 'image', {'decision': 'exclude'})
        real = live_review.write_atomic
        def fail_pointer(path, data):
            if path.name == 'current.json':
                raise OSError('simulated interrupted commit')
            return real(path, data)
        with patch.object(live_review, 'write_atomic', fail_pointer), self.assertRaises(OSError):
            prepare(self.cat, self.store, self.output)
        self.assertEqual((self.output / 'current.json').read_bytes(), previous)
        self.assertEqual(read_prepared(self.output, self.cat.source)[1]['event_cutoff'], 0)
        first = prepare(self.cat, self.store, self.output)
        committed = (self.output / 'current.json').read_bytes()
        second = prepare(self.cat, self.store, self.output)
        self.assertEqual(first['generation'], second['generation'])
        self.assertEqual((self.output / 'current.json').read_bytes(), committed)
        self.assertEqual(len(list((self.output / 'generations').iterdir())), 2)

    def test_source_change_during_build_never_advances_pointer(self):
        prepare(self.cat, self.store, self.output)
        previous = (self.output / 'current.json').read_bytes()
        real = live_review.effective_document
        def drift(cat, snap):
            data = real(cat, snap)
            Path(cat.source['gallery_database']).write_bytes(b'changed during projection')
            return data
        with patch.object(live_review, 'effective_document', drift), self.assertRaises(SourceConflict):
            prepare(self.cat, self.store, self.output)
        self.assertEqual((self.output / 'current.json').read_bytes(), previous)

    def test_writer_lock_rejects_competing_publisher(self):
        with writer_lock(self.output):
            with self.assertRaises(SourceConflict):
                prepare(self.cat, self.store, self.output)
        self.assertFalse((self.output / 'current.json').exists())

    def test_reader_rejects_changed_bytes_or_different_base(self):
        status = prepare(self.cat, self.store, self.output)
        with self.assertRaises(SourceConflict):
            read_prepared(self.output, {**self.cat.source, 'gallery_sha256': 'different'})
        path = self.output / 'generations' / status['generation'] / 'data.json'
        path.write_text('{}')
        with self.assertRaises(ValueError):
            read_prepared(self.output, self.cat.source)

    def test_snapshot_is_consistent_while_new_events_commit(self):
        def change():
            for n in range(1, 26):
                self.save('product', 'A', '', {'decision': 'include', 'notes': str(n)}, n - 1)
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(change)
            for _ in range(30):
                snapshot = self.store.snapshot()
                if snapshot['reviews']:
                    r = snapshot['reviews'][0]
                    self.assertEqual(r['version'], snapshot['event_cutoff'])
                    self.assertEqual(int(r['data']['notes']), snapshot['event_cutoff'])
            future.result()
        self.assertEqual(self.store.snapshot()['event_cutoff'], 25)


if __name__ == '__main__':
    unittest.main()
