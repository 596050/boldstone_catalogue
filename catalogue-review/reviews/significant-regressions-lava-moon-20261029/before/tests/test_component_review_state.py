"""Pending image purposes must never become component or move approvals."""
import unittest
from urllib.parse import quote

import test_components
from dropbox_sync import ROOT_PATH
from organisation import plan


class ComponentReviewStateTests(unittest.TestCase):
    setUp = test_components.ComponentTests.setUp
    tearDown = test_components.ComponentTests.tearDown
    setUpBase = test_components.ComponentTests.setUpBase
    save = test_components.ComponentTests.save
    view = test_components.ComponentTests.view
    choices = test_components.ComponentTests.choices
    submit = test_components.ComponentTests.submit

    def pending(self, pid='S1', uses=None):
        self.save('image', pid, 'image', {'decision': 'pending',
                  'uses': uses if uses is not None else ['listing'], 'notes': 'Still checking identity'})

    def test_pending_listing_does_not_assign_an_unconfirmed_component(self):
        self.pending()
        self.assertEqual(set(self.view().asset('image')['component_ids']), {'L1', 'L2'})
        row = next(r for r in self.choices()['rows'] if r['product_id'] == 'S1')
        self.assertFalse(row['shown'])
        self.assertFalse(row['listing'])

    def test_pending_listing_does_not_change_automatic_dropbox_destination(self):
        for product in self.cat.products.values():
            product['folder_url'] = 'https://www.dropbox.com/home' + quote(ROOT_PATH + '/Ammonite/' + product['name'])
        asset = self.cat.assets.pop('image')
        asset['id'] = 'id:target'
        self.cat.assets['id:target'] = asset
        for edges in self.cat.edges.values():
            edges['id:target'] = edges.pop('image')
        asset['provenance'] = {'path': ROOT_PATH + '/Ammonite/Ammonite Large 1 and Ammonite Large 2 White In Situ/photo.jpg'}
        self.save('image', 'S1', 'id:target', {'decision': 'pending', 'uses': ['listing']})
        destination = plan(self.view(), 'id:target')
        self.assertEqual(set(destination['component_ids']), {'L1', 'L2'})
        self.assertNotIn('Small', destination['destination_folder'])

    def test_show_only_preserves_pending_draft_without_approving_it(self):
        self.pending(uses=['listing', 'social'])
        before = self.view().record('image', 'S1', 'image')
        row = next(r for r in self.choices()['rows'] if r['product_id'] == 'S1')
        row.update(shown=True, listing=False, advertising=False)
        self.submit([row])
        after = self.view().record('image', 'S1', 'image')
        self.assertEqual(after, before)
        self.assertIn('S1', self.view().asset('image')['component_ids'])

    def test_selecting_ads_does_not_approve_unreviewed_listing_or_social_drafts(self):
        self.pending(uses=['listing', 'advertising', 'social'])
        row = next(r for r in self.choices()['rows'] if r['product_id'] == 'S1')
        row.update(shown=True, listing=False, advertising=True)
        self.submit([row])
        choice = self.view().decision('image', 'S1', 'image')
        self.assertEqual(choice['uses'], ['advertising'])
        self.assertEqual(choice['decision'], 'reviewed')
        self.assertEqual(choice['notes'], 'Still checking identity')

    def test_reviewed_listing_still_assigns_a_related_component(self):
        self.save('image', 'S1', 'image', {'decision': 'reviewed', 'uses': ['listing']})
        self.assertIn('S1', self.view().asset('image')['component_ids'])

    def test_explicit_ads_choice_preserves_other_already_reviewed_uses(self):
        self.save('image', 'L1', 'image', {'decision': 'reviewed', 'uses': ['listing', 'social', 'reference']})
        row = next(r for r in self.choices()['rows'] if r['product_id'] == 'L1')
        row['advertising'] = True
        self.submit([row])
        self.assertEqual(set(self.view().decision('image', 'L1', 'image')['uses']),
                         {'listing', 'advertising', 'social', 'reference'})

    def test_overview_primary_replaces_old_primary_but_keeps_listing_and_ads(self):
        from copy import deepcopy
        from component_links import component_row
        old = deepcopy(self.cat.assets['image']);old['id']='old'
        self.cat.assets['old']=old;self.cat.edges['L1']['old']={'tier':'accepted'}
        self.save('image','L1','old',{'decision':'reviewed','uses':['listing','advertising'],'primary':True})
        self.save('image','L2','image',{'decision':'reviewed','uses':['listing'],'primary':True})
        row=component_row(self.view(),'L1','image');row.update(primary=True,shown=True,listing=True,advertising=True)
        self.submit([row])
        self.assertTrue(self.view().decision('image','L1','image')['primary'])
        old_choice=self.view().decision('image','L1','old')
        self.assertFalse(old_choice['primary']);self.assertEqual(set(old_choice['uses']),{'listing','advertising'})
        self.assertTrue(self.view().decision('image','L2','image')['primary'])

    def test_primary_conflict_is_atomic_and_preserves_previous_primary(self):
        from component_links import component_row
        from store import Conflict
        row=component_row(self.view(),'S1','image');row.update(shown=True,listing=True,primary=True)
        self.save('image','S1','image',{'decision':'reviewed','uses':['advertising'],'notes':'newer'})
        before=self.store.all()
        with self.assertRaises(Conflict):self.submit([row])
        self.assertEqual(self.store.all(),before)

    def test_association_off_clears_primary_and_readd_does_not_restore_listing(self):
        from component_links import component_row
        self.save('image','L1','image',{'decision':'reviewed','uses':['listing','advertising'],'primary':True})
        row=component_row(self.view(),'L1','image');row.update(shown=False,listing=False,advertising=False,primary=False)
        self.submit([row])
        self.assertNotIn('L1',self.view().asset('image')['component_ids'])
        row=component_row(self.view(),'L1','image');row['shown']=True;self.submit([row])
        choice=self.view().decision('image','L1','image');self.assertEqual(choice['uses'],[]);self.assertFalse(choice['primary'])

    def test_primary_requires_explicit_listing_and_changed_bytes_reject_all(self):
        from component_links import component_row
        from store import Conflict
        row=component_row(self.view(),'L1','image');row['primary']=True
        with self.assertRaises(ValueError):self.submit([row])
        row['listing']=True
        with self.assertRaises(Conflict):self.submit([row],content_hash='old bytes')
        self.assertEqual(self.store.all(),[])

    def test_legacy_chooser_can_remove_listing_from_primary_without_sending_primary(self):
        self.save('image','L1','image',{'decision':'reviewed','uses':['listing'],'primary':True})
        row=next(r for r in self.choices()['rows'] if r['product_id']=='L1')
        self.assertNotIn('primary',row);row['listing']=False;self.submit([row])
        self.assertFalse(self.view().decision('image','L1','image')['primary'])
