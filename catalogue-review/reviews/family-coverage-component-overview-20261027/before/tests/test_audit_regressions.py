import unittest

import test_dropbox_sync as fixture
from dropbox_sync import ROOT_PATH, apply_inventory, link
from projection import Projection
from review_coverage import product_coverage


class AuditRegressions(unittest.TestCase):
    setUp = fixture.OverlayTests.setUp
    tearDown = fixture.OverlayTests.tearDown
    file = fixture.OverlayTests.file

    def test_existing_image_move_updates_its_library_family(self):
        destination = ROOT_PATH + '/Ammonite/Ammonite White'
        self.state['records']['id:destination'] = {
            'id': 'id:destination', 'kind': 'folder', 'path': destination, 'name': 'Ammonite White'}
        self.state['records']['id:old']['path'] = destination + '/old.jpg'
        cat = apply_inventory(self.base, self.state, self.root)
        self.assertEqual(cat.assets['id:old']['family'], 'Ammonite')
        self.assertEqual(cat.assets['id:old']['folder_url'], link(destination))
        self.assertEqual(self.base.assets['id:old']['family'], 'Acanthus')
        # Moving a source photo does not merge product identities or approve uses.
        self.assertEqual(cat.products['white']['family'], 'Acanthus')
        self.assertEqual(Projection(cat, []).decision('image', 'white', 'id:old'), {})

    def test_unchanged_family_folder_preserves_existing_label(self):
        self.base.products['white']['family'] = 'Acanthus canonical spelling'
        cat = apply_inventory(self.base, self.state, self.root)
        self.assertEqual(cat.assets['id:old']['family'], 'Acanthus')

    def test_family_move_uses_destination_product_folder_not_old_related_edge(self):
        destination = ROOT_PATH + '/Moon Crater/White'
        self.base.products['moon'] = {**self.base.products['white'], 'id': 'moon', 'family': 'Mooncrater',
                                      'folder_url': link(destination), 'primary_id': None}
        self.state['records']['id:destination'] = {
            'id': 'id:destination', 'kind': 'folder', 'path': destination, 'name': 'White'}
        self.state['records']['id:old']['path'] = destination + '/old.jpg'
        cat = apply_inventory(self.base, self.state, self.root)
        self.assertEqual(cat.assets['id:old']['family'], 'Mooncrater')
        self.assertEqual(cat.products['white']['family'], 'Acanthus')

    def test_removed_images_are_separate_from_retained_total(self):
        cat = apply_inventory(self.base, self.state, self.root)
        rows = [
            {'kind': 'assignment', 'product_id': 'white', 'item_id': 'id:old', 'version': 1,
             'data': {'state': 'removed'}},
            {'kind': 'image', 'product_id': 'white', 'item_id': 'id:old', 'version': 1,
             'data': {'decision': 'reviewed', 'uses': ['listing'], 'primary': True}},
        ]
        view = Projection(cat, rows)
        counts = product_coverage(view, cat.products['white'])['counts']
        self.assertEqual(counts, {'total': 1, 'sculpture': 1, 'related': 0, 'removed': 1})
        self.assertEqual(view.decision('image', 'white', 'id:old')['uses'], ['listing'])


if __name__ == '__main__':
    unittest.main()
