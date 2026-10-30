"""A Dropbox move changes folder defaults, while explicit decisions survive."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import test_dropbox_sync as fixture
from dropbox_sync import apply_inventory, link
from projection import Projection
from component_links import shown


class FolderMoveMembershipTests(unittest.TestCase):
    setUp = fixture.OverlayTests.setUp
    tearDown = fixture.OverlayTests.tearDown
    file = fixture.OverlayTests.file

    def move_candidate(self):
        asset = deepcopy(self.base.assets['id:old'])
        asset.update(id='id:new', name='new.png')
        asset['original']['dropbox_content_hash'] = 'b' * 64
        self.base.assets['id:new'] = asset
        self.base.edges['white']['id:new'] = {
            'asset_id': 'id:new', 'uses': ['primary_folder'],
            'qualifications': ['FOLDER_CANDIDATE_REQUIRES_VISUAL_REVIEW'],
            'association_ids': ['old-association'], 'tier': 'folder'}
        self.state['records']['id:new'].update(
            path=self.gold + '/new.png', folder_id='id:gold')

    def test_moved_folder_candidate_follows_new_component_not_old_finish(self):
        self.move_candidate()
        before = deepcopy(self.base.edges)
        cat = apply_inventory(self.base, self.state, self.root)
        view = Projection(cat, [])
        self.assertFalse(shown(view, 'white', 'id:new'))
        self.assertTrue(shown(view, 'gold', 'id:new'))
        self.assertEqual(cat.edges['white']['id:new']['tier'], 'related')
        self.assertEqual(cat.edges['white']['id:new']['association_ids'], ['old-association'])
        self.assertEqual(self.base.edges, before)

    def test_manual_attachment_and_listing_approval_survive_folder_move(self):
        self.move_candidate()
        cat = apply_inventory(self.base, self.state, self.root)
        for kind, data in [('assignment', {'state': 'attached'}),
                           ('image', {'decision': 'reviewed', 'uses': ['listing']})]:
            with self.subTest(kind=kind):
                view = Projection(cat, [{'kind': kind, 'product_id': 'white',
                    'item_id': 'id:new', 'version': 1, 'data': data}])
                self.assertTrue(shown(view, 'white', 'id:new'))

    def test_accepted_source_reference_survives_folder_move(self):
        self.move_candidate()
        self.base.edges['white']['id:new'].update(tier='accepted', uses=['selected_context_reference'])
        view = Projection(apply_inventory(self.base, self.state, self.root), [])
        self.assertTrue(shown(view, 'white', 'id:new'))

    def test_same_folder_id_rename_keeps_candidate_membership(self):
        self.move_candidate()
        renamed = self.white + ' Renamed'
        self.state['records']['id:white']['path'] = renamed
        for aid in ['id:old', 'id:new']:
            self.state['records'][aid].update(path=renamed + '/' + self.state['records'][aid]['name'], folder_id='id:white')
        cat = apply_inventory(self.base, self.state, self.root)
        self.assertTrue(shown(Projection(cat, []), 'white', 'id:new'))
        self.assertEqual(cat.products['white']['folder_url'], link(renamed))

    def test_returning_to_original_folder_restores_default_without_review_write(self):
        self.move_candidate()
        apply_inventory(self.base, self.state, self.root)
        self.state['records']['id:new'].update(path=self.white + '/new.png', folder_id='id:white')
        cat = apply_inventory(self.base, self.state, self.root)
        self.assertEqual(cat.edges['white']['id:new']['tier'], 'folder')

    def test_context_only_folder_stays_in_library_without_component_defaults(self):
        self.base.family_library_only_folder_ids = {'id:white'}
        cat = apply_inventory(self.base, self.state, self.root)
        view = Projection(cat, [])
        self.assertIn('id:old', {a['id'] for a in view.library()})
        self.assertFalse(shown(view, 'white', 'id:old'))
        self.assertNotIn('id:old', view.edges['white'])
        self.assertIn('id:old', cat.edges['white'])  # Source evidence retained.

    def test_context_only_default_allows_explicit_component_attachment(self):
        self.base.family_library_only_folder_ids = {'id:white'}
        cat = apply_inventory(self.base, self.state, self.root)
        view = Projection(cat, [{'kind': 'assignment', 'product_id': 'white',
            'item_id': 'id:old', 'version': 1, 'data': {'state': 'attached'}}])
        self.assertTrue(shown(view, 'white', 'id:old'))
        self.assertEqual(view.edges['white']['id:old']['tier'], 'manual')

    def test_moving_out_of_context_only_folder_restores_destination_defaults(self):
        self.base.family_library_only_folder_ids = {'id:white'}
        self.move_candidate()
        cat = apply_inventory(self.base, self.state, self.root)
        view = Projection(cat, [])
        self.assertTrue(shown(view, 'gold', 'id:new'))
        self.assertIn('id:new', view.edges['gold'])


if __name__ == '__main__':
    unittest.main()
