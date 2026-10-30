"""A current native folder must supersede stale family labels after a move."""
from copy import deepcopy
from types import SimpleNamespace
import unittest

import test_dropbox_sync as fixture
from dropbox_sync import ROOT_PATH, apply_inventory, link
from family_inventory import belongs_to_family, family_inventory
from projection import Projection
from server import Application


class CurrentFamilyFilterTests(unittest.TestCase):
    def setUp(self):
        self.inventory = {
            'family_paths': {'Acanthus': [(ROOT_PATH + '/Acanthus').casefold()],
                             'Fan Folds': [(ROOT_PATH + '/Fold Unfold').casefold()]},
            'folders': [{'name': 'Deco Palm and Spiral', 'path': ROOT_PATH + '/Deco Palm and Spiral'},
                        {'name': 'Fold Unfold', 'path': ROOT_PATH + '/Fold Unfold'}]}

    def test_current_native_path_wins_over_old_family(self):
        asset = {'source': 'Dropbox', 'family': 'Deco Palm and Spiral',
                 'provenance': {'path': ROOT_PATH + '/Acanthus/White/moved.png'}}
        self.assertFalse(belongs_to_family(asset, 'Deco Palm and Spiral', self.inventory))
        self.assertTrue(belongs_to_family(asset, 'Acanthus', self.inventory))

    def test_current_folder_url_wins_without_provenance_path(self):
        asset = {'source': 'Dropbox', 'family': 'Deco Palm and Spiral',
                 'folder_url': link(ROOT_PATH + '/Acanthus/White')}
        self.assertFalse(belongs_to_family(asset, 'Deco Palm and Spiral', self.inventory))
        self.assertTrue(belongs_to_family(asset, 'Acanthus', self.inventory))

    def test_current_path_keeps_registered_alias_and_native_folder(self):
        asset = {'source': 'Dropbox', 'family': 'Acanthus',
                 'provenance': {'path': 'ns:202238505/' + ROOT_PATH + '/fold unfold/White/file.png'}}
        self.assertTrue(belongs_to_family(asset, 'Fan Folds', self.inventory))
        self.assertTrue(belongs_to_family(asset, 'Fold Unfold', self.inventory))
        self.assertFalse(belongs_to_family(asset, 'Acanthus', self.inventory))

    def test_native_family_without_full_inventory_still_matches_exact_folder_name(self):
        asset = {'source': 'Dropbox', 'family': 'Old',
                 'provenance': {'path': ROOT_PATH + '/New/White/file.png'}}
        self.assertTrue(belongs_to_family(asset, 'New', {'folders': [], 'family_paths': {}}))
        self.assertFalse(belongs_to_family(asset, 'Old', {'folders': [], 'family_paths': {}}))

    def test_platform_and_unlocated_history_keep_family_fallback(self):
        for asset in ({'source': 'Shopify', 'family': 'Acanthus'},
                      {'source': 'Dropbox', 'family': 'Acanthus'}):
            self.assertTrue(belongs_to_family(asset, 'Acanthus', self.inventory))
            self.assertFalse(belongs_to_family(asset, 'Fan Folds', self.inventory))


class MovedFamilySyncTests(unittest.TestCase):
    setUp = fixture.OverlayTests.setUp
    tearDown = fixture.OverlayTests.tearDown
    file = fixture.OverlayTests.file

    def test_already_updated_path_does_not_preserve_stale_family(self):
        # A publisher already refreshed the path but retained the pre-move label.
        self.base.assets['id:old']['family'] = 'Deco Palm and Spiral'
        before = deepcopy(self.base.assets)
        cat = apply_inventory(self.base, self.state, self.root)
        self.assertEqual(cat.assets['id:old']['family'], 'Acanthus')
        self.assertEqual(self.base.assets, before)

    def test_stale_source_label_is_repaired_on_every_inventory_refresh(self):
        self.base.assets['id:old']['family'] = 'Deco Palm and Spiral'
        first = apply_inventory(self.base, self.state, self.root)
        self.state['generation'] += 1
        second = apply_inventory(self.base, self.state, self.root)
        self.assertEqual(first.assets['id:old']['family'], 'Acanthus')
        self.assertEqual(second.assets['id:old']['family'], 'Acanthus')

    def test_folder_alias_is_supported_by_products_not_broad_gallery_edges(self):
        self.base.products['white']['family'] = 'Acanthus Canonical'
        self.base.products['gold']['family'] = 'Acanthus Canonical'
        self.base.assets['id:old']['family'] = 'Acanthus Canonical'
        self.base.products['unrelated'] = {**self.base.products['gold'], 'id': 'unrelated',
            'family': 'Deco Palm and Spiral', 'folder_url': link(ROOT_PATH + '/Deco Palm and Spiral/White')}
        self.base.edges['unrelated']['id:old'] = {
            'asset_id': 'id:old', 'uses': [], 'qualifications': [], 'association_ids': [], 'tier': 'related'}
        cat = apply_inventory(self.base, self.state, self.root)
        self.assertEqual(cat.assets['id:old']['family'], 'Acanthus Canonical')
        self.assertEqual(cat.assets['id:new']['family'], 'Acanthus Canonical')
        self.assertNotIn('id:new', cat.edges['unrelated'])

    def test_saved_component_uses_primary_and_shared_tags_survive_family_correction(self):
        self.base.assets['id:old']['family'] = 'Deco Palm and Spiral'
        rows = [
            {'kind': 'image', 'product_id': 'white', 'item_id': 'id:old', 'version': 2,
             'data': {'decision': 'reviewed', 'uses': ['listing', 'advertising'], 'primary': True}},
            {'kind': 'asset', 'product_id': '', 'item_id': 'id:old', 'version': 1,
             'data': {'types': ['product'], 'tags': ['keep-this']}},
            {'kind': 'assignment', 'product_id': 'gold', 'item_id': 'id:old', 'version': 1,
             'data': {'state': 'removed'}}]
        before = deepcopy(rows)
        cat = apply_inventory(self.base, self.state, self.root)
        view = Projection(cat, rows)
        self.assertEqual(view.decision('image', 'white', 'id:old'), rows[0]['data'])
        self.assertEqual(view.asset('id:old')['types'], ['product'])
        self.assertEqual(view.decision('asset', '', 'id:old')['tags'], ['keep-this'])
        self.assertNotIn('id:old', view.edges['gold'])
        self.assertEqual(rows, before)

    def test_library_does_not_reintroduce_stale_family_through_duplicate_member(self):
        self.state['records']['id:new']['content_hash'] = 'a' * 64
        cat = apply_inventory(self.base, self.state, self.root)
        cat.assets['id:new']['family'] = 'Deco Palm and Spiral'
        app = Application.__new__(Application)
        app.catalogue = cat
        app.store = SimpleNamespace(all=lambda: [])
        self.assertEqual(len(app.library('Acanthus')['images']), 1)
        self.assertEqual(app.library('Deco Palm and Spiral')['images'], [])

    def test_identical_files_actually_in_two_native_folders_remain_in_both(self):
        self.state['records']['id:new']['content_hash'] = 'a' * 64
        destination = ROOT_PATH + '/Deco Palm and Spiral/White'
        self.state['records']['id:destination'] = {
            'id': 'id:destination', 'kind': 'folder', 'path': destination, 'name': 'White'}
        self.state['records']['id:new']['path'] = destination + '/new.png'
        cat = apply_inventory(self.base, self.state, self.root)
        app = Application.__new__(Application)
        app.catalogue = cat
        app.store = SimpleNamespace(all=lambda: [])
        self.assertEqual(len(app.library('Acanthus')['images']), 1)
        self.assertEqual(len(app.library('Deco Palm and Spiral')['images']), 1)


if __name__ == '__main__':
    unittest.main()
