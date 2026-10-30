from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from media import MediaCache, dimensions, enrich
from projection import Projection
from server import Application
from store import Conflict, ReviewStore, validate
from exports import create_export
from fetch_original import check_metadata, OriginalError
import test_review


class ImageToolsTests(unittest.TestCase):
    setUp = test_review.ReviewTests.setUp
    tearDown = test_review.ReviewTests.tearDown
    save = test_review.ReviewTests.save

    def enrich_fixture(self, platform_preview=False):
        h = MediaCache(self.root).inspect(self.image, hashes=True)
        asset = self.cat.assets['image']
        asset.update(inventory_status='CURRENT_NATIVE_FILE_AND_ACTUAL_PARENT_VERIFIED',
                     original={'bytes': h['bytes'], 'dropbox_content_hash': h['dropbox_content_hash']},
                     local_preview=True)
        self.cat.assets['platform'] = {**deepcopy(asset), 'id': 'platform', 'source': 'Shopify', 'original': {}}
        self.cat.paths['platform'] = (self.image, 'cached preview' if platform_preview else 'cached source')
        self.cat.edges['A']['platform'] = {'uses': ['Related Shopify gallery'], 'qualifications': ['Unconfirmed finish'], 'tier': 'related'}
        enrich(self.cat, self.root / 'cache')
        return h

    def test_native_byte_hash_and_header_size(self):
        h = self.enrich_fixture()
        self.assertEqual(dimensions(self.image), [1, 1])
        self.assertEqual(h['dropbox_content_hash'], hashlib.sha256(hashlib.sha256(self.image.read_bytes()).digest()).hexdigest())
        self.assertNotEqual(h['dropbox_content_hash'], h['sha256'])
        self.assertEqual(self.cat.assets['image']['original']['dimensions'], [1, 1])
        self.assertTrue(self.cat.assets['image']['original']['locally_verified'])

    def test_dropbox_wins_without_losing_associations_or_provenance(self):
        self.enrich_fixture()
        view = Projection(self.cat, [])
        self.assertEqual(self.cat.canonical_assets['platform'], 'image')
        self.assertEqual(len(view.images('A')), 1)
        self.assertEqual(len(view.library()), 1)
        self.assertEqual(view.images('A')[0]['association']['source_asset_ids'], ['image', 'platform'])
        self.assertIn('Unconfirmed finish', view.images('A')[0]['association']['qualifications'])
        self.assertIn('platform', self.cat.edges['A'])
        self.assertEqual(len(view.images('A')[0]['duplicates']), 2)

    def test_thumbnail_equality_does_not_claim_original_identity(self):
        self.enrich_fixture(platform_preview=True)
        # Same thumbnail bytes, different originals: no dedupe and no original size.
        self.cat.assets['image']['original']['dropbox_content_hash'] = 'a' * 64
        self.cat.paths['image'] = (self.image, 'cached preview')
        enrich(self.cat, self.root / 'cache')
        self.assertEqual(self.cat.canonical_assets['platform'], 'platform')
        self.assertIsNone(self.cat.assets['image']['original']['dimensions'])
        self.assertEqual(self.cat.assets['image']['cached_file']['dimensions'], [1, 1])

    def test_content_hash_crosses_four_megabyte_boundary(self):
        path = self.root / 'blocks.bin'
        a, b = b'a' * (4 * 1024 * 1024), b'last block'
        path.write_bytes(a + b)
        h = MediaCache(self.root).inspect(path, hashes=True)
        self.assertEqual(h['dropbox_content_hash'], hashlib.sha256(hashlib.sha256(a).digest() + hashlib.sha256(b).digest()).hexdigest())

    def test_conflicting_duplicate_reviews_retained_and_withheld(self):
        self.enrich_fixture()
        self.save('image', 'A', 'image', {'decision': 'reviewed', 'uses': ['listing'], 'primary': True})
        self.save('image', 'A', 'platform', {'decision': 'exclude'})
        self.save('asset', '', 'image', {'types': ['product'], 'tags': ['garden'], 'rights': 'owned'})
        self.save('asset', '', 'platform', {'types': ['in_situ'], 'tags': ['campaign'], 'rights': 'restricted'})
        view = Projection(self.cat, self.store.all())
        self.assertTrue(view.record('image', 'A', 'image')['duplicate_conflicts'])
        self.assertEqual(view.decision('image', 'A', 'image')['uses'], [])
        self.assertEqual(view.decision('asset', '', 'image')['rights'], 'restricted')
        self.assertEqual(set(view.decision('asset', '', 'image')['tags']), {'garden', 'campaign'})
        result = create_export(self.cat, self.store, True)
        bundle = json.loads((Path(result['path']) / 'review-decisions.json').read_text())
        self.assertEqual(len(bundle['reviews']), 4)
        self.assertFalse((Path(result['path']) / 'media').exists())
        versions = view.record('image', 'A', 'image')['member_versions']
        self.store.save('image', 'A', 'image', {'decision': 'reviewed', 'uses': ['advertising']}, 1, 'source1', {}, versions)
        self.assertFalse(Projection(self.cat, self.store.all()).record('image', 'A', 'image')['duplicate_conflicts'])
        self.assertEqual(self.store.get('image', 'A', 'platform')['version'], 2)
        with self.assertRaises(Conflict):
            self.store.save('image', 'A', 'image', {'decision': 'exclude'}, 2, 'source1', {}, versions)

    def app_fixture(self):
        app = Application.__new__(Application)
        app.catalogue, app.store = self.cat, self.store
        return app

    def test_move_copy_undo_preserves_files_and_per_title_choices(self):
        self.enrich_fixture()
        self.cat.edges['B'] = {}
        self.save('image', 'A', 'image', {'decision': 'reviewed', 'uses': ['advertising']})
        app = self.app_fixture()
        body = {'mode': 'move', 'asset_ids': ['image'], 'from_product_id': 'A', 'to_product_id': 'B',
                'versions': {'A': {'image': 0}, 'B': {'image': 0}}}
        before = self.image.read_bytes()
        result = app.assign(body)
        self.assertNotIn('image', app.projection().edges['A'])
        self.assertIn('image', app.projection().edges['B'])
        self.assertEqual(self.store.get('image', 'A', 'image')['data']['uses'], ['advertising'])
        self.assertEqual(self.store.get('image', 'B', 'image')['version'], 0)
        exported = create_export(self.cat, self.store, True)
        self.assertFalse((Path(exported['path']) / 'media').exists())
        self.assertIn('removed', (Path(exported['path']) / 'image-decisions-and-tags.csv').read_text())
        self.store.undo_assignment(result['operation_id'], 'source1')
        self.assertIn('image', app.projection().edges['A'])
        self.assertNotIn('image', app.projection().edges['B'])
        body['mode'] = 'copy'
        body['versions']['B']['image'] = 2
        app.assign(body)
        self.assertIn('image', app.projection().edges['A'])
        self.assertIn('image', app.projection().edges['B'])
        self.assertEqual(self.image.read_bytes(), before)

    def test_move_is_atomic_on_stale_destination(self):
        self.enrich_fixture()
        app = self.app_fixture()
        body = {'mode': 'move', 'asset_ids': ['image'], 'from_product_id': 'A', 'to_product_id': 'B',
                'versions': {'A': {'image': 0}, 'B': {'image': 1}}}
        with self.assertRaises(Conflict):
            app.assign(body)
        self.assertEqual(self.store.get('assignment', 'A', 'image')['version'], 0)
        self.assertIn('image', app.projection().edges['A'])

    def test_successive_moves_can_be_undone_in_reverse_order(self):
        self.enrich_fixture()
        self.cat.edges['B'] = {}
        app = self.app_fixture()
        first = app.assign({'mode': 'move', 'asset_ids': ['image'], 'from_product_id': 'A', 'to_product_id': 'B',
                            'versions': {'A': {'image': 0}, 'B': {'image': 0}}})
        second = app.assign({'mode': 'move', 'asset_ids': ['image'], 'from_product_id': 'B', 'to_product_id': 'A',
                             'versions': {'A': {'image': 1}, 'B': {'image': 1}}})
        with self.assertRaises(Conflict):
            self.store.undo_assignment(first['operation_id'], 'source1')
        self.store.undo_assignment(second['operation_id'], 'source1')
        self.store.undo_assignment(first['operation_id'], 'source1')
        self.assertIn('image', app.projection().edges['A'])
        self.assertNotIn('image', app.projection().edges['B'])

    def test_source_review_inherited_and_deduped_exported_once(self):
        self.enrich_fixture()
        self.save('image', 'A', 'platform', {'decision': 'reviewed', 'uses': ['advertising']})
        view = Projection(self.cat, self.store.all())
        self.assertEqual(view.decision('image', 'A', 'image')['uses'], ['advertising'])
        result = create_export(self.cat, self.store, True)
        root = Path(result['path'])
        self.assertEqual(len(list((root / 'media/advertising').rglob('*.png'))), 1)
        self.assertIn('platform', (root / 'exact-byte-duplicates.csv').read_text())

    def test_type_tags_are_multi_select_and_durable(self):
        self.save('asset', '', 'image', {'types': ['product', 'in_situ', 'group'], 'tags': ['autumn']})
        again = ReviewStore(self.store.root)
        self.assertEqual(again.get('asset', '', 'image')['data']['types'], ['product', 'in_situ', 'group'])
        with self.assertRaises(ValueError):
            validate('asset', {'types': ['delete_all']})

    def test_original_fetch_rejects_changed_bytes_id_or_scope(self):
        valid = {'id': 'id:known', 'content_hash': 'a' * 64, 'size': 100,
                 'path_display': '/BOLDSTONE MASTER/Products/01 Wall Sculptures/Test/image.png'}
        root = '/BOLDSTONE MASTER/Products/01 Wall Sculptures'
        check_metadata(SimpleNamespace(**valid), 'id:known', 'a' * 64, 100, root)
        for patch in ({'id': 'id:other'}, {'content_hash': 'b' * 64}, {'size': 101}, {'path_display': '/Other/image.png'}):
            with self.assertRaises(OriginalError):
                check_metadata(SimpleNamespace(**{**valid, **patch}), 'id:known', 'a' * 64, 100, root)


if __name__ == '__main__':
    unittest.main()
