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

    def test_stale_displayed_content_rejects_purposes_and_tags_without_writes(self):
        displayed_hash = self.enrich_fixture()['dropbox_content_hash']
        self.cat.assets['image']['original']['dropbox_content_hash'] = 'b' * 64
        app = self.app_fixture()
        for kind, pid, values in [('image', 'A', {'decision': 'reviewed', 'uses': ['listing'], 'primary': True}),
                                  ('asset', '', {'types': ['in_situ'], 'tags': ['garden']})]:
            with self.subTest(kind=kind):
                with self.assertRaisesRegex(Conflict, 'image changed'):
                    app.save({'kind': kind, 'product_id': pid, 'item_id': 'image', 'version': 0,
                              'expected_content_hash': displayed_hash, 'data': values})
                self.assertEqual(self.store.all(), [])
                self.assertEqual(self.store.history(), [])

    def test_unknown_displayed_content_cannot_approve_newly_known_bytes(self):
        self.enrich_fixture()
        with self.assertRaisesRegex(Conflict, 'image changed'):
            self.app_fixture().save({'kind': 'image', 'product_id': 'A', 'item_id': 'image',
                                    'version': 0, 'expected_content_hash': None,
                                    'data': {'decision': 'reviewed', 'uses': ['listing']}})
        self.assertEqual(self.store.all(), [])

    def test_current_content_can_be_reviewed_after_a_filename_change(self):
        displayed_hash = self.enrich_fixture()['dropbox_content_hash']
        self.cat.assets['image']['name'] = 'panel__white-in-situ__001.png'
        self.cat.assets['image']['live_synced'] = True
        app = self.app_fixture()
        image = app.save({'kind': 'image', 'product_id': 'A', 'item_id': 'image', 'version': 0,
                          'expected_content_hash': displayed_hash,
                          'data': {'decision': 'reviewed', 'uses': ['listing', 'advertising']}})
        asset = app.save({'kind': 'asset', 'product_id': '', 'item_id': 'image', 'version': 0,
                          'expected_content_hash': displayed_hash, 'data': {'types': ['product']}})
        self.assertEqual(image['data']['reviewed_content_hash'], displayed_hash)
        self.assertEqual(image['data']['uses'], ['listing', 'advertising'])
        self.assertEqual(asset['data']['types'], ['product'])
        self.assertEqual(len(self.store.history()), 2)

    def test_platform_original_sha256_is_checked_when_dropbox_hash_is_unavailable(self):
        self.cat.assets['image']['original'] = {'sha256': 'a' * 64}
        app = self.app_fixture()
        body = {'kind': 'asset', 'product_id': '', 'item_id': 'image', 'version': 0,
                'expected_content_hash': 'b' * 64, 'data': {'types': ['product']}}
        with self.assertRaisesRegex(Conflict, 'image changed'):
            app.save(body)
        body['expected_content_hash'] = 'a' * 64
        self.assertEqual(app.save(body)['data']['types'], ['product'])

    def test_retired_product_url_explains_removal_without_showing_another_product(self):
        self.cat.retired_product_ids = {'retired'}
        with self.assertRaisesRegex(KeyError, 'removed from the active catalogue'):
            self.app_fixture().product('retired')

    def test_family_gallery_includes_unassigned_and_group_images_without_merging_products(self):
        self.enrich_fixture()
        self.cat.assets['image']['family'] = 'Ammonite'
        self.cat.assets['platform']['family'] = 'Historical label'
        self.cat.assets['group'] = {**deepcopy(self.cat.assets['image']), 'id': 'group', 'role': 'group_context'}
        self.cat.canonical_assets['group'] = 'group'
        self.cat.duplicate_members['group'] = ['group']
        self.cat.assets['other'] = {**deepcopy(self.cat.assets['image']), 'id': 'other', 'family': 'Acanthus'}
        self.cat.canonical_assets['other'] = 'other'
        self.cat.duplicate_members['other'] = ['other']
        before = deepcopy(self.cat.edges)
        result = self.app_fixture().library('Ammonite')
        self.assertEqual({a['id'] for a in result['images']}, {'image', 'group'})
        self.assertEqual(self.cat.edges, before)
        self.assertEqual(next(a for a in result['images'] if a['id'] == 'group')['product_ids'], [])
        # A retained alias can find the canonical Dropbox copy, without displaying it twice.
        self.assertEqual([a['id'] for a in self.app_fixture().library('Historical label')['images']], ['image'])
        self.assertEqual(self.app_fixture().library('Unknown')['images'], [])

    def test_card_type_save_preserves_shared_metadata_and_independent_image_purposes(self):
        self.enrich_fixture()
        self.save('image', 'A', 'image', {'decision': 'reviewed', 'uses': ['listing', 'advertising'], 'primary': True})
        self.save('asset', '', 'image', {'types': ['product'], 'tags': ['garden'], 'rights': 'owned', 'notes': 'Retain notes', 'collection': 'Autumn'})
        app = self.app_fixture()
        image_before = deepcopy(self.store.get('image', 'A', 'image'))
        record = app.projection().record('asset', '', 'image')
        app.save({'kind': 'asset', 'product_id': '', 'item_id': 'image', 'version': record['version'],
                  'member_versions': record['member_versions'], 'data': {**record['data'], 'types': ['product', 'in_situ', 'group']}})
        view = app.projection()
        self.assertEqual(view.decision('asset', '', 'image')['types'], ['product', 'in_situ', 'group'])
        self.assertEqual(view.decision('asset', '', 'image')['tags'], ['garden'])
        self.assertEqual(view.decision('asset', '', 'image')['notes'], 'Retain notes')
        self.assertEqual(view.decision('asset', '', 'image')['rights'], 'owned')
        self.assertEqual(view.decision('asset', '', 'image')['collection'], 'Autumn')
        self.assertEqual(self.store.get('image', 'A', 'image'), image_before)
        self.assertEqual(view.decision('asset', '', view.images('B')[0]['id'])['types'], ['product', 'in_situ', 'group'])

    def test_live_image_purposes_can_be_saved_repeatedly_from_returned_record(self):
        expected_hash = self.enrich_fixture()['dropbox_content_hash']
        self.cat.assets['image']['live_synced'] = True
        app = self.app_fixture()
        record = {'version': 0, 'data': {'decision': 'reviewed', 'uses': ['reference'],
                                       'notes': 'Keep this composition', 'primary': False}}
        uses = {'reference'}
        # Same round trip as Listing twice, then Listing + Ads, then each off.
        for version, purpose in enumerate(('listing', 'listing', 'listing', 'advertising',
                                           'listing', 'advertising'), 1):
            uses.symmetric_difference_update({purpose})
            body = {'kind': 'image', 'product_id': 'A', 'item_id': 'image',
                    'version': record['version'], 'member_versions': record.get('member_versions'),
                    'data': {**record['data'], 'uses': sorted(uses)}}
            submitted = deepcopy(body)
            record = app.save(body)
            self.assertEqual(record['version'], version)
            self.assertEqual(set(record['data']['uses']), uses)
            self.assertEqual(record['data']['reviewed_content_hash'], expected_hash)
            self.assertEqual(record['data']['notes'], 'Keep this composition')
            self.assertFalse(record.get('duplicate_conflicts'))
            self.assertEqual(body, submitted)
        self.assertEqual(record['data']['uses'], ['reference'])
        self.assertEqual(ReviewStore(self.store.root).get('image', 'A', 'image')['data'], record['data'])

    def test_echoed_image_hash_is_server_owned_and_unknown_fields_still_rejected(self):
        expected_hash = self.enrich_fixture()['dropbox_content_hash']
        self.cat.assets['image']['live_synced'] = True
        app = self.app_fixture()
        body = {'kind': 'image', 'product_id': 'A', 'item_id': 'image', 'version': 0,
                'data': {'decision': 'reviewed', 'uses': ['listing', 'advertising'],
                         'reviewed_content_hash': 'not-the-current-native-hash'}}
        record = app.save(body)
        self.assertEqual(record['data']['reviewed_content_hash'], expected_hash)
        with self.assertRaises(Conflict):
            app.save(body)
        body['version'] = record['version']
        body['member_versions'] = record['member_versions']
        body['data']['unexpected_field'] = 'still invalid'
        with self.assertRaisesRegex(ValueError, 'Unknown review field'):
            app.save(body)
        self.assertEqual(self.store.get('image', 'A', 'image')['version'], 1)
        with self.assertRaisesRegex(ValueError, 'Unknown review field'):
            app.save({'kind': 'asset', 'product_id': '', 'item_id': 'image', 'version': 0,
                      'data': {'reviewed_content_hash': expected_hash}})

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
