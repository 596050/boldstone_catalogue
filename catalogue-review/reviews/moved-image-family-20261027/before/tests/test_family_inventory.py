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
