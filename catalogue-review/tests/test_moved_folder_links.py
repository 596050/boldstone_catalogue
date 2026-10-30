"""Deleted/merged folders follow retained photos without inventing membership."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import test_dropbox_sync as fixture
from component_links import group_defaults
from dropbox_sync import ROOT_PATH, apply_inventory, link
from organisation import NeedsChoice, folder_for_components
from projection import Projection


class MovedFolderLinkTests(unittest.TestCase):
    setUp = fixture.OverlayTests.setUp
    tearDown = fixture.OverlayTests.tearDown
    file = fixture.OverlayTests.file

    def merge_folder(self):
        self.destination = ROOT_PATH + '/Acanthus/White In Situ'
        self.state['records'].pop('id:white')
        self.state['records']['id:merged'] = {
            'id': 'id:merged', 'kind': 'folder', 'path': self.destination, 'name': 'White In Situ'}
        for aid in ('id:old', 'id:new'):
            self.state['records'][aid].update(
                path=self.destination + '/' + self.state['records'][aid]['name'], folder_id='id:merged')

    def test_removed_folder_link_follows_same_file_id_into_merged_folder(self):
        before = deepcopy(self.base.products)
        self.merge_folder()
        cat = apply_inventory(self.base, self.state, self.root)
        p = cat.products['white']
        self.assertEqual(p['folder_url'], link(self.destination))
        self.assertTrue(p['folder_link_only'])
        self.assertEqual(p['folder_link_recovery']['source_url'], link(self.white))
        self.assertEqual(p['folder_link_recovery']['file_ids'], ['id:old'])
        self.assertEqual(p['folder_link_recovery']['folder_id'], 'id:merged')
        self.assertEqual(self.base.products, before)
        self.assertEqual(cat.products['white']['primary_id'], 'id:old')
        self.assertEqual(cat.edges['white']['id:old'], self.base.edges['white']['id:old'])
        self.assertIn('in_situ', cat.assets['id:old']['types'])

    def test_merged_navigation_link_does_not_assign_every_new_photo(self):
        self.merge_folder()
        cat = apply_inventory(self.base, self.state, self.root)
        self.assertEqual(cat.edges['white']['id:new']['tier'], 'related')
        rows = [{'kind': 'assignment', 'product_id': 'white', 'item_id': 'id:old',
                 'version': 1, 'data': {'state': 'removed'}}]
        self.assertNotIn('id:old', Projection(cat, rows).edges['white'])

    def test_recovered_navigation_folder_cannot_authorize_a_native_move(self):
        self.merge_folder()
        cat = apply_inventory(self.base, self.state, self.root)
        with self.assertRaises(NeedsChoice):
            folder_for_components(cat.products, ['white'], ['in_situ'])
        self.assertEqual(folder_for_components(cat.products, ['gold'], []), self.gold)

    def test_recovered_navigation_folder_is_not_a_group_identity_anchor(self):
        self.merge_folder()
        cat = apply_inventory(self.base, self.state, self.root)
        cat.assets['id:group'] = {
            'id': 'id:group', 'source': 'Dropbox', 'family': 'Acanthus',
            'folder_url': link(ROOT_PATH + '/Acanthus/White and Gold')}
        self.assertNotIn('id:group', group_defaults(cat))

    def test_existing_folder_is_retained_when_only_its_photo_moves(self):
        self.merge_folder()
        self.state['records']['id:white'] = {
            'id': 'id:white', 'kind': 'folder', 'path': self.white, 'name': 'White'}
        p = apply_inventory(self.base, self.state, self.root).products['white']
        self.assertEqual(p['folder_url'], link(self.white))
        self.assertFalse(p.get('folder_link_only'))

    def test_same_name_replacement_file_does_not_establish_folder_recovery(self):
        self.merge_folder()
        self.state['records'].pop('id:old')
        p = apply_inventory(self.base, self.state, self.root).products['white']
        self.assertEqual(p['folder_url'], '')
        self.assertEqual(p['folder_link_recovery']['status'], 'unresolved')
        self.assertEqual(p['folder_link_recovery']['file_ids'], [])

    def test_split_destinations_do_not_choose_an_arbitrary_folder(self):
        self.merge_folder()
        other = deepcopy(self.base.assets['id:old'])
        other['id'] = 'id:other'
        self.base.assets['id:other'] = other
        self.state['records']['id:other'] = self.file('id:other', 'other.jpg', 'c' * 64)
        self.state['records']['id:other'].update(path=self.gold + '/other.jpg', folder_id='id:gold')
        p = apply_inventory(self.base, self.state, self.root).products['white']
        self.assertEqual(p['folder_url'], '')
        self.assertEqual(p['folder_link_recovery']['status'], 'unresolved')
        self.assertEqual(len(p['folder_link_recovery']['current_folder_urls']), 2)

    def test_next_scan_tracks_a_second_move_without_using_old_fallback_as_anchor(self):
        self.merge_folder()
        first = apply_inventory(self.base, self.state, self.root)
        second_path = ROOT_PATH + '/Acanthus/Workshop'
        self.state['records']['id:merged']['path'] = second_path
        for aid in ('id:old', 'id:new'):
            self.state['records'][aid]['path'] = second_path + '/' + self.state['records'][aid]['name']
        second = apply_inventory(self.base, self.state, self.root)
        self.assertEqual(second.products['white']['folder_url'], link(second_path))
        self.assertEqual(first.products['white']['folder_url'], link(self.destination))
        self.assertEqual(second.edges['white']['id:new']['tier'], 'related')


if __name__ == '__main__':
    unittest.main()
