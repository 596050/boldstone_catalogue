from pathlib import Path
from copy import deepcopy
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import test_review
from projection import Projection
from component_overview import component_overview


class ComponentOverviewTests(unittest.TestCase):
    tearDown = test_review.ReviewTests.tearDown
    save = test_review.ReviewTests.save

    def setUp(self):
        test_review.ReviewTests.setUp(self)
        self.cat.products['A'].update(id='A', primary_id='image')
        for pid in self.cat.edges:
            self.cat.edges[pid]['image']={'tier':'accepted','uses':[]}
        self.cat.assets['image']['types']=['product']

    def overview(self):
        return component_overview(Projection(self.cat,self.store.all()),'A')

    def test_source_reference_is_not_automatically_primary_listing(self):
        result=self.overview()
        self.assertIsNone(result['primary_id'])
        self.assertEqual(result['source_reference_id'],'image')
        self.assertEqual(result['product']['fields'][0]['value'],'6 kg - estimate')

    def test_shared_types_and_component_listing_ads_are_independent(self):
        self.save('image','A','image',{'decision':'reviewed','uses':['listing','advertising'],'primary':True})
        self.save('image','B','image',{'decision':'exclude'})
        self.save('asset','','image',{'types':['product','in_situ']})
        result=self.overview()
        self.assertEqual(result['primary_id'],'image')
        self.assertEqual(result['in_situ_ids'],['image'])
        self.assertEqual(result['images'][0]['selected_uses'],['listing','advertising'])

    def test_related_and_removed_or_deleted_images_cannot_be_primary(self):
        self.cat.assets['related']={**deepcopy(self.cat.assets['image']),'id':'related'}
        self.cat.edges['A']['related']={'tier':'related','uses':[]}
        result=self.overview()
        self.assertEqual([a['id'] for a in result['related_images']],['related'])
        rows=[{'kind':'assignment','product_id':'A','item_id':'image','version':1,'data':{'state':'removed'}}]
        self.assertEqual(component_overview(Projection(self.cat,rows),'A')['images'],[])

    def test_exclusion_retains_visible_reference_but_not_listing_or_situ(self):
        self.save('asset','','image',{'types':['in_situ']})
        self.save('image','A','image',{'decision':'exclude'})
        result=self.overview()
        self.assertEqual(len(result['images']),1)
        self.assertTrue(result['images'][0]['excluded'])
        self.assertIsNone(result['primary_id']);self.assertEqual(result['in_situ_ids'],[])

    def test_restricted_or_edit_requested_primary_is_labelled_withheld(self):
        self.save('image','A','image',{'decision':'reviewed','uses':['listing'],'primary':True,'edit_notes':'Remove background'})
        self.save('asset','','image',{'rights':'restricted'})
        result=self.overview()
        self.assertIsNone(result['primary_id'])
        self.assertEqual(len(result['images'][0]['withheld_reasons']),2)

    def test_read_only_overview_preserves_reviews_and_unknown_product_fails(self):
        self.save('field','A','Weight',{'decision':'edit','value':'8 kg'})
        before=self.store.all();result=self.overview()
        self.assertEqual(result['product']['fields'][0]['value'],'8 kg')
        self.assertEqual(self.store.all(),before)
        with self.assertRaises(KeyError):component_overview(Projection(self.cat,before),'missing')
