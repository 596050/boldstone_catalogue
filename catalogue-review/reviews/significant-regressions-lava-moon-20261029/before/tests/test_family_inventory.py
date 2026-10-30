from pathlib import Path
from types import SimpleNamespace as NS
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from family_inventory import family_inventory, belongs_to_family, root_folder, ROOT


class FamilyInventoryTests(unittest.TestCase):
    def setUp(self):
        self.cat = NS(source={}, products={
            'one': {'family': 'Fan Folds', 'folder_url': 'https://www.dropbox.com/home'+ROOT.replace(' ', '%20')+'/Fold%20Unfold/White'}},
            native_root_folders=[{'id': 'folder1', 'name': 'Fold Unfold', 'path': ROOT+'/Fold Unfold'},
                                 {'id': 'folder2', 'name': 'Collection Together', 'path': ROOT+'/Collection Together'}],
            assets={}, canonical_assets={})

    def test_folder_count_and_component_count_are_distinct(self):
        result = family_inventory(self.cat)
        self.assertEqual(result['registered_family_count'], 1)
        self.assertEqual(result['dropbox_folder_count'], 2)
        self.assertEqual([f['name'] for f in result['image_only_folders']], ['Collection Together'])
        self.assertEqual(result['folders'][1]['registered_families'], ['Fan Folds'])

    def test_supported_alias_and_case_match_without_fuzzy_finish_matching(self):
        asset={'family':'Fold Unfold','provenance':{'path':'ns:202238505/'+ROOT+'/fold unfold/Gold/p.jpg'}}
        inventory=family_inventory(self.cat)
        self.assertTrue(belongs_to_family(asset,'Fan Folds',inventory))
        self.assertTrue(belongs_to_family(asset,'Fold Unfold',inventory))
        self.assertFalse(belongs_to_family(asset,'Fan',inventory))
        self.assertFalse(belongs_to_family(asset,'Collection Together',inventory))

    def test_external_folder_and_root_prefix_collision_do_not_count(self):
        self.assertEqual(root_folder(ROOT+' Backup/Fold Unfold/p.jpg'), '')
        self.assertEqual(root_folder('/Other/Fold Unfold/p.jpg'), '')

    def test_tombstones_unavailable_and_exact_duplicates_do_not_inflate_images(self):
        self.cat.assets={k:{'source':'Dropbox','provenance':{'path':ROOT+'/Fold Unfold/p.jpg'},
                            'source_unavailable':k=='missing'} for k in ['one','alias','deleted','missing']}
        self.cat.canonical_assets={'alias':'one'}
        self.assertEqual(family_inventory(self.cat, {'deleted'})['folders'][1]['image_count'],1)

    def test_no_verified_inventory_does_not_claim_a_native_folder_count(self):
        del self.cat.native_root_folders
        self.assertIsNone(family_inventory(self.cat)['dropbox_folder_count'])


class NativeFolderNavigationTests(unittest.TestCase):
    def setUp(self):
        self.root = ROOT + '/Frozen Fish'
        self.cat = NS(source={}, products={
            'old-one': {'family': 'Frozen Fish', 'folder_url': 'https://www.dropbox.com/home' + self.root + '/Frozen Fish White In Situ'},
            'old-three': {'family': 'Frozen Fish', 'folder_url': 'https://www.dropbox.com/home' + self.root + '/Frozen Fish White In Situ'}},
            native_root_folders=[{'id': 'root', 'name': 'Frozen Fish', 'path': self.root}],
            native_folders=[], assets={}, canonical_assets={})
        for i, name in enumerate(['White', 'White In Situ', 'Terracotta', 'Verdigris']):
            self.cat.native_folders.append({'id': 'folder'+str(i), 'name': 'Frozen Fish '+name,
                'path': self.root+'/Frozen Fish '+name})
        self.cat.assets = {str(i): {'source': 'Dropbox', 'provenance': {'path': f['path']+'/photo.jpg'}}
                           for i, f in enumerate(self.cat.native_folders)}

    def folders(self):
        return family_inventory(self.cat)['family_folders']['Frozen Fish']

    def test_four_native_folders_are_not_six_historical_product_names(self):
        self.assertEqual(len(self.folders()), 4)
        self.assertEqual({f['name'] for f in self.folders()}, {'Frozen Fish '+x for x in ['White', 'White In Situ', 'Terracotta', 'Verdigris']})
        self.assertTrue(all(f['image_count'] == 1 for f in self.folders()))

    def test_same_folder_id_follows_rename_and_stale_name_disappears(self):
        f = self.cat.native_folders[0]
        f.update(name='New White', path=self.root+'/New White')
        self.cat.assets['0']['provenance']['path']=f['path']+'/photo.jpg'
        rows={r['id']:r for r in self.folders()}
        self.assertEqual(rows['folder0']['name'], 'New White')
        self.assertIn('/New%20White', rows['folder0']['url'])
        self.assertNotIn('Frozen Fish White', [r['name'] for r in rows.values()])

    def test_deleted_folder_does_not_return_from_saved_product_links(self):
        self.cat.native_folders.pop(1)
        self.assertEqual(len(self.folders()), 3)
        self.assertNotIn('Frozen Fish White In Situ', [r['name'] for r in self.folders()])
        self.assertEqual(len(self.cat.products), 2)

    def test_empty_folder_is_present_without_invented_images(self):
        self.cat.assets.pop('2')
        self.assertEqual(next(r for r in self.folders() if r['id']=='folder2')['image_count'], 0)

    def test_nested_folder_uses_boundary_and_relative_label(self):
        path=self.root+'/Frozen Fish White/Detail'
        self.cat.native_folders.append({'id':'detail','name':'Detail','path':path})
        self.cat.assets['detail']={'source':'Dropbox','provenance':{'path':path+'/photo.jpg'}}
        rows={r['id']:r for r in self.folders()}
        self.assertEqual(rows['folder0']['image_count'], 2)
        self.assertEqual(rows['folder0']['direct_image_count'], 1)
        self.assertEqual(rows['folder1']['image_count'], 1)
        self.assertEqual(rows['detail']['relative_name'], 'Frozen Fish White/Detail')

    def test_tombstones_platform_and_missing_images_do_not_inflate_counts(self):
        self.cat.assets['0']['source_unavailable']=True
        self.cat.assets['platform']={'source':'Squarespace','provenance':{'path':self.cat.native_folders[1]['path']+'/p.jpg'}}
        rows=family_inventory(self.cat, {'1'})['family_folders']['Frozen Fish']
        self.assertEqual(sum(r['image_count'] for r in rows), 2)

    def test_alias_family_has_native_folders_without_fuzzy_matching(self):
        for p in self.cat.products.values():p['family']='Saved name'
        result=family_inventory(self.cat)['family_folders']
        self.assertEqual(len(result['Saved name']),4)
        self.assertNotIn('Fish',result)
