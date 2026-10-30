from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from component_photos import component_photos
from projection import Projection
from review_coverage import coverage
from specifications import specification_overview


class ComponentPhotoTests(unittest.TestCase):
    def setUp(self):
        self.cat = SimpleNamespace(
            source={'register_sha256': 'source'}, paths={},
            products={pid: {'id': pid, 'name': pid, 'family': 'Panels', 'fields': [],
                            'primary_id': 'photo0'} for pid in ['A', 'B']},
            assets={}, edges={'A': {}, 'B': {}})
        for index in range(9):
            aid = 'photo' + str(index)
            self.cat.assets[aid] = {'id': aid, 'name': aid + '.jpg', 'source': 'Dropbox',
                                    'types': ['product', 'in_situ'], 'local_preview': True,
                                    'original': {'dropbox_content_hash': 'hash' + str(index), 'bytes': 100}}
            self.cat.edges['A'][aid] = {'tier': 'accepted'}
            self.cat.edges['B'][aid] = {'tier': 'accepted'}
        self.rows = []

    def choice(self, aid, **changes):
        value = {'decision': 'reviewed', 'uses': ['listing'], 'primary': False, **changes}
        self.rows.append({'kind': 'image', 'product_id': 'A', 'item_id': aid, 'data': value, 'version': 1})

    def view(self):
        return Projection(self.cat, self.rows)

    def test_listing_preview_is_bounded_primary_first_and_ordered(self):
        for index in range(8):
            self.choice('photo' + str(index), order=8-index, primary=index == 5)
        result = coverage(self.view(), include_photos=True)['products']['A']
        self.assertEqual(result['primary_listing']['status'], 'set')
        self.assertEqual(result['photos']['listing']['count'], 8)
        self.assertEqual([a['id'] for a in result['photos']['listing']['images']],
                         ['photo5', 'photo7', 'photo6', 'photo4', 'photo3', 'photo2'])
        self.assertEqual(result['photos']['in_situ']['count'], 9)
        self.assertEqual(len(result['photos']['in_situ']['images']), 6)
        self.assertEqual(result['photos']['in_situ']['count'], result['in_situ']['count'])

    def test_shared_scene_can_be_listing_and_situ_but_choices_stay_per_component(self):
        self.choice('photo0', primary=True, uses=['listing', 'advertising'])
        result = coverage(self.view(), include_photos=True)['products']
        self.assertEqual(result['A']['photos']['listing']['count'], 1)
        self.assertEqual(result['A']['photos']['listing']['images'][0]['id'], 'photo0')
        self.assertEqual(result['B']['photos']['listing']['count'], 0)
        self.assertEqual(result['B']['primary_listing']['status'], 'missing')
        self.assertEqual(result['A']['in_situ']['image_ids'], result['B']['in_situ']['image_ids'])

    def test_source_primary_and_ads_only_are_not_listing_selections(self):
        self.choice('photo0', uses=['advertising'])
        result = component_photos(self.view(), 'A')
        self.assertEqual(result['primary_listing']['status'], 'missing')
        self.assertEqual(result['listing_ids'], [])

    def test_removed_deleted_excluded_and_related_do_not_fill_preview_or_primary(self):
        for aid in ['photo0', 'photo1', 'photo2']:
            self.choice(aid, primary=aid == 'photo0')
        self.rows.extend([
            {'kind': 'deletion', 'product_id': '', 'item_id': 'photo0', 'version': 1, 'data': {'state': 'deleted'}},
            {'kind': 'assignment', 'product_id': 'A', 'item_id': 'photo1', 'version': 1, 'data': {'state': 'removed'}}])
        self.rows[2]['data'] = {'decision': 'exclude'}
        self.cat.edges['A']['photo3'] = {'tier': 'related'}
        result = coverage(self.view(), include_photos=True)['products']['A']
        self.assertEqual(result['photos']['listing']['count'], 0)
        self.assertEqual(result['primary_listing']['status'], 'missing')
        self.assertEqual(result['in_situ']['count'], 5)
        self.assertEqual([a['id'] for a in result['photos']['in_situ']['images']],
                         ['photo4', 'photo5', 'photo6', 'photo7', 'photo8'])

    def test_blocked_primary_is_needs_review_but_listing_selection_still_visible(self):
        self.choice('photo0', primary=True, edit_notes='Needs crop')
        self.rows.append({'kind': 'asset', 'product_id': '', 'item_id': 'photo0', 'version': 1,
                          'data': {'rights': 'restricted'}})
        result = coverage(self.view(), include_photos=True)['products']['A']
        self.assertEqual(result['primary_listing']['status'], 'needs_review')
        self.assertIsNone(result['primary_listing']['image_id'])
        self.assertEqual(result['photos']['listing']['count'], 1)
        self.assertEqual(len(result['photos']['listing']['images'][0]['withheld_reasons']), 2)

    def test_conflicting_primaries_never_show_primary_set(self):
        self.choice('photo0', primary=True)
        self.choice('photo1', primary=True, edit_notes='Crop')
        result = component_photos(self.view(), 'A')
        self.assertTrue(result['primary_conflict'])
        self.assertEqual(result['primary_listing']['status'], 'needs_review')
        self.assertIsNone(result['primary_id'])
        self.assertFalse(any(a['primary_eligible'] for a in result['images']))

    def test_changed_bytes_invalidates_primary_including_related_candidate(self):
        self.choice('photo0', primary=True, reviewed_content_hash='older')
        self.cat.assets['photo0']['live_synced'] = True
        self.cat.edges['A']['photo0']['tier'] = 'related'
        result = component_photos(self.view(), 'A')
        self.assertEqual(result['primary_listing']['status'], 'needs_review')
        self.assertIsNone(result['primary_id'])
        self.assertEqual(result['listing_ids'], [])

    def test_byte_duplicates_are_one_preview_and_conflicts_are_not_green(self):
        self.cat.canonical_assets = {'photo1': 'photo0'}
        self.cat.duplicate_members = {'photo0': ['photo0', 'photo1']}
        self.choice('photo0', primary=True)
        self.choice('photo1', primary=True)
        self.assertEqual(coverage(self.view(), True)['products']['A']['photos']['listing']['count'], 1)
        self.rows[1]['data'] = {'decision': 'exclude'}
        self.assertEqual(coverage(self.view())['products']['A']['primary_listing']['status'], 'needs_review')

    def test_card_revision_refreshes_with_uses_tags_primary_and_changed_preview_bytes(self):
        def snapshot():
            view = self.view()
            photos = {pid: p['photos'] for pid, p in coverage(view, True)['products'].items()}
            return specification_overview(self.cat, view.reviews, photos)
        first = snapshot()
        self.choice('photo0', primary=True)
        second = snapshot()
        self.assertNotEqual(first['revision'], second['revision'])
        self.assertEqual(second['revision'], snapshot()['revision'])
        self.rows.append({'kind': 'asset', 'product_id': '', 'item_id': 'photo0', 'version': 1,
                          'data': {'types': ['product']}})
        third = snapshot()
        self.assertNotEqual(second['revision'], third['revision'])
        self.cat.assets['photo0']['original']['dropbox_content_hash'] = 'newbytes'
        self.assertNotEqual(third['revision'], snapshot()['revision'])

    def test_read_only_cards_keep_the_coverage_target_and_records_intact(self):
        self.choice('photo0', primary=True)
        self.cat.assets['photo8']['source'] = 'Squarespace'
        before = deepcopy((self.cat.assets, self.cat.products, self.rows))
        result = coverage(self.view(), True)['products']['A']
        self.assertEqual(result['photos']['in_situ']['count'], 8)
        self.assertEqual((self.cat.assets, self.cat.products, self.rows), before)


if __name__ == '__main__':
    unittest.main()
