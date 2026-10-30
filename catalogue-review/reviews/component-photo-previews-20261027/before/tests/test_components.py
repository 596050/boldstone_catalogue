from copy import deepcopy
from pathlib import Path
from urllib.parse import quote
from types import SimpleNamespace
import csv
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from component_links import match_group, payload
from component_reviews import save_components
from projection import Projection
from server import Application
from store import Conflict
from exports import create_export
import test_review


class ComponentTests(unittest.TestCase):
    setUpBase = test_review.ReviewTests.setUp
    tearDown = test_review.ReviewTests.tearDown
    save = test_review.ReviewTests.save

    def setUp(self):
        self.setUpBase()
        template = self.cat.products['A']
        names = {'L1': 'Ammonite Large 1 White', 'L2': 'Ammonite Large 2 White',
                 'S1': 'Ammonite Small 1 White', 'S2': 'Ammonite Small 2 White',
                 'B1': 'Ammonite Large 1 Bronze', 'B2': 'Ammonite Large 2 Bronze'}
        self.names = names
        self.cat.products = {pid: {**deepcopy(template), 'id': pid, 'name': name, 'family': 'Ammonite',
                                  'folder_url': 'https://www.dropbox.com/home/' + quote(name)} for pid, name in names.items()}
        self.cat.edges = {pid: {'image': {'tier': 'related'}} for pid in names}
        self.cat.assets['image'].update(family='Ammonite', folder_url='https://www.dropbox.com/home/'+quote('Ammonite Large 1 and Ammonite Large 2 White In Situ'),
                                       types=['in_situ'], original={'dropbox_content_hash': 'hash1', 'bytes': 123}, live_synced=True)
        self.app = Application.__new__(Application)
        self.app.store = self.store
        self.app.catalogue = self.cat

    def view(self): return Projection(self.cat, self.store.all())
    def choices(self): return payload(self.view(), 'image')
    def submit(self, rows, content_hash='hash1'):
        return save_components(self.app, {'asset_id': 'image', 'content_hash': content_hash, 'rows': rows})

    def test_exact_group_keeps_sizes_finishes_and_numbers_distinct(self):
        anchors = {name.casefold(): {pid} for pid, name in self.names.items()}
        anchors['ammonite large 20 white'] = {'L20'}
        self.assertEqual(match_group('Ammonite Large 1 and Ammonite Large 2 White In Situ', anchors), ['L1', 'L2'])
        self.assertEqual(match_group('Ammonite Small 1 and Ammonite Small 2 White', anchors), ['S1', 'S2'])
        self.assertEqual(match_group('Ammonite Large 1 White and Ammonite Large 2 Bronze', anchors), ['B2', 'L1'])
        self.assertEqual(match_group('Ammonite Large 1 and Others White', anchors), [])
        self.assertEqual(match_group('Ammonite Large White Together', anchors), [])

    def test_ambiguous_anchors_and_individual_names_with_and_are_not_split(self):
        anchors = {'acanthus and moon white': {'A'}, 'soundwave white': {'B'}}
        self.assertEqual(match_group('Acanthus and Moon White', anchors), [])
        self.assertEqual(match_group('Acanthus and Moon White and Soundwave White', anchors), ['A', 'B'])
        anchors['soundwave white'].add('C')
        self.assertEqual(match_group('Acanthus and Moon White and Soundwave White', anchors), [])

    def test_group_defaults_show_under_both_components_without_approving_listing(self):
        image = self.view().asset('image')
        self.assertEqual(set(image['component_ids']), {'L1', 'L2'})
        self.assertEqual(image['types'], ['in_situ', 'group'])
        self.assertEqual(self.view().edges['S1']['image']['tier'], 'related')
        self.assertEqual(self.store.all(), [])
        self.assertFalse(any(row['listing'] for row in self.choices()['rows']))

    def test_manual_removal_and_exclusion_survive_defaults_and_refresh(self):
        self.store.save('assignment', 'L1', 'image', {'state': 'removed'}, 0, 'source1', {})
        self.save('image', 'L2', 'image', {'decision': 'exclude'})
        self.assertEqual(self.view().asset('image')['component_ids'], ['L2'])
        rows = {r['product_id']: r for r in self.choices()['rows']}
        self.assertTrue(rows['L1']['removed'])
        self.assertFalse(rows['L1']['shown'])
        self.assertTrue(rows['L2']['excluded'])
        self.assertFalse(rows['L2']['listing'])

    def test_listing_and_ads_independent_per_component_and_exported(self):
        self.save('image', 'L1', 'image', {'decision': 'reviewed', 'uses': ['social'], 'caption': 'Keep caption', 'order': 7})
        self.save('asset', '', 'image', {'tags': ['garden'], 'types': ['in_situ', 'group'], 'rights': 'owned'})
        rows = [r for r in self.choices()['rows'] if r['product_id'] in ('L1', 'L2')]
        for row in rows: row.update(listing=True, advertising=row['product_id']=='L1')
        self.submit(rows)
        left = self.view().decision('image', 'L1', 'image')
        self.assertEqual(set(left['uses']), {'listing', 'advertising', 'social'})
        self.assertEqual(left['caption'], 'Keep caption')
        self.assertEqual(left['order'], 7)
        self.assertEqual(self.view().decision('image', 'L2', 'image')['uses'], ['listing'])
        self.assertEqual(self.view().decision('asset', '', 'image')['tags'], ['garden'])
        root = Path(create_export(self.cat, self.store)['path'])
        with (root/'image-decisions-and-tags.csv').open(encoding='utf-8-sig') as f:
            exported={(r['product_id'],r['use']) for r in csv.DictReader(f)}
        self.assertEqual(exported, {('L1','listing'),('L1','advertising'),('L1','social'),('L2','listing')})

    def test_unchecking_one_component_clears_its_uses_only(self):
        rows = [r for r in self.choices()['rows'] if r['shown']]
        for r in rows: r.update(listing=True,advertising=True)
        self.submit(rows)
        row = next(r for r in self.choices()['rows'] if r['product_id']=='L1')
        row.update(shown=False,listing=False,advertising=False)
        self.submit([row])
        self.assertEqual(self.view().asset('image')['component_ids'], ['L2'])
        self.assertEqual(self.view().decision('image', 'L1', 'image')['uses'], [])
        self.assertEqual(set(self.view().decision('image', 'L2', 'image')['uses']), {'listing','advertising'})

    def test_saved_exclusion_changes_only_when_explicit_use_selected(self):
        self.save('image', 'L1', 'image', {'decision': 'exclude', 'notes': 'Detail shot'})
        row = next(r for r in self.choices()['rows'] if r['product_id']=='L1')
        self.submit([row])
        self.assertEqual(self.view().decision('image', 'L1', 'image')['decision'], 'exclude')
        row.update(listing=True)
        self.submit([row])
        choice=self.view().decision('image', 'L1', 'image')
        self.assertEqual(choice['uses'], ['listing'])
        self.assertEqual(choice['notes'], 'Detail shot')

    def test_concurrent_edit_rolls_back_whole_multi_component_save(self):
        rows = [r for r in self.choices()['rows'] if r['shown']]
        for r in rows: r['listing']=True
        self.save('image', 'L2', 'image', {'decision':'reviewed','uses':['reference']})
        before=self.store.all()
        with self.assertRaises(Conflict):self.submit(rows)
        self.assertEqual(before,self.store.all())

    def test_changed_or_deleted_image_rejected(self):
        rows=[r for r in self.choices()['rows'] if r['shown']]
        with self.assertRaises(Conflict):self.submit(rows,content_hash='old')
        self.cat.assets['image']['source_unavailable']=True
        with self.assertRaises(ValueError):self.submit(rows)
        self.assertEqual(self.store.all(),[])

    def test_clearing_listing_does_not_hide_an_explicitly_shown_related_image(self):
        self.cat.assets['image']['folder_url']='https://www.dropbox.com/home/Unclassified'
        self.save('image', 'L1', 'image', {'decision':'reviewed','uses':['listing']})
        row=next(r for r in self.choices()['rows'] if r['product_id']=='L1')
        self.assertTrue(row['shown'])
        row['listing']=False
        self.submit([row])
        self.assertTrue(next(r for r in self.choices()['rows'] if r['product_id']=='L1')['shown'])
        self.assertEqual(self.view().edges['L1']['image']['tier'],'manual')

    def test_group_alias_contributes_defaults_without_duplicate_display(self):
        self.cat.assets['alias']=deepcopy(self.cat.assets['image'])
        self.cat.assets['alias']['id']='alias'
        self.cat.assets['image']['folder_url']='https://www.dropbox.com/home/Unclassified'
        self.cat.canonical_assets={'image':'image','alias':'image'}
        self.cat.duplicate_members={'image':['image','alias'],'alias':['image','alias']}
        self.assertEqual(self.view().asset('image')['default_component_ids'],['L1','L2'])
        self.assertEqual(len(self.view().library()),1)

    def test_store_transaction_rejects_a_late_alias_conflict_before_any_write(self):
        changes=[]
        for pid in ('L1','L2'):
            changes.append({'kind':'image','product_id':pid,'item_id':'image','data':{'decision':'reviewed','uses':['listing']},
                            'version':0,'member_versions':{'image':0},'original':{}})
        self.save('image','L2','image',{'decision':'exclude'})
        with self.assertRaises(Conflict):self.store.save_component_reviews(changes,'source1')
        self.assertEqual(self.store.get('image','L1','image')['version'],0)

if __name__=='__main__':unittest.main()
