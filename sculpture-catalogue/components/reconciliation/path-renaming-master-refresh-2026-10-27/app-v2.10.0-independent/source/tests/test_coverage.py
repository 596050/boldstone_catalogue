from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from projection import Projection
from review_coverage import coverage, plain_white_evidence


class CoverageTests(unittest.TestCase):
    def setUp(self):
        self.cat=SimpleNamespace(products={
            'A':{'id':'A','name':'Acanthus and Moon','family':'Acanthus','component_id':'C1','folder_url':'https://www.dropbox.com/home/Acanthus%20and%20Moon%20White'},
            'B':{'id':'B','name':'Acanthus and Moon — Gold Leaf','family':'Acanthus','component_id':'C1'},
            'C':{'id':'C','name':'Two Leaves — Blue and White','family':'Acanthus','component_id':'C2'},
            'D':{'id':'D','name':'Unresolved option','family':'Acanthus','component_id':None}},
            assets={},edges={pid:{} for pid in ['A','B','C','D']},component_names={'C1':'Acanthus and Moon','C2':'Two Leaves'})
        for aid,types,source,tier in [('situ1',['in_situ'],'Dropbox','accepted'),('situ2',['in_situ','group'],'Dropbox','folder'),('candidate',['in_situ'],'Dropbox','related'),('platform',['in_situ'],'Squarespace','accepted'),('product',['product'],'Dropbox','folder')]:
            self.cat.assets[aid]={'id':aid,'name':aid,'source':source,'types':types,'original':{'bytes':10,'dropbox_content_hash':'x'}}
            self.cat.edges['A'][aid]={'tier':tier}
        self.reviews=[]

    def add(self,kind,pid,aid,data):
        self.reviews.append({'kind':kind,'product_id':pid,'item_id':aid,'data':data,'version':1})

    def result(self):return coverage(Projection(self.cat,self.reviews))

    def test_two_in_situ_requires_assigned_nonexcluded_dropbox_images(self):
        p=self.result()['products']['A']
        self.assertEqual(p['in_situ']['count'],2)
        self.assertEqual(p['in_situ']['missing'],0)
        self.assertEqual(p['counts'],{'total':5,'sculpture':4,'related':1,'removed':0})
        self.assertEqual(p['individual']['count'],1)
        self.add('image','A','situ1',{'decision':'exclude','uses':[]})
        self.assertEqual(self.result()['products']['A']['in_situ']['missing'],1)

    def test_exact_byte_aliases_deletion_and_removed_assignments_do_not_inflate_coverage(self):
        self.cat.assets['alias']=deepcopy(self.cat.assets['situ1']);self.cat.assets['alias']['id']='alias'
        self.cat.edges['A']['alias']={'tier':'accepted'}
        self.cat.canonical_assets={'alias':'situ1'};self.cat.duplicate_members={'situ1':['situ1','alias']}
        self.assertEqual(self.result()['products']['A']['in_situ']['count'],2)
        self.add('deletion','','situ1',{'state':'deleted'})
        self.add('assignment','A','situ2',{'state':'removed'})
        p=self.result()['products']['A']
        self.assertEqual(p['in_situ']['count'],0)
        self.assertEqual(p['counts']['removed'],1)

    def test_user_tags_and_candidate_approval_refresh_coverage(self):
        self.add('asset','','situ1',{'types':['detail']})
        self.assertEqual(self.result()['products']['A']['in_situ']['count'],1)
        self.add('image','A','candidate',{'decision':'reviewed','uses':['listing']})
        p=self.result()['products']['A']
        self.assertEqual(p['in_situ']['count'],2)
        self.assertEqual(p['in_situ']['listing_count'],1)
        self.assertEqual(p['counts']['related'],0)

    def test_plain_white_is_separate_from_mixed_finishes_and_title_omissions(self):
        family=self.result()['families']['Acanthus']
        self.assertEqual(family['white_entries_missing'],1)
        self.assertEqual(family['white_titles_missing'],1)
        self.assertEqual(plain_white_evidence({},'Acanthus and Moon White'),'named_white')
        self.assertEqual(family['component_count'],2)
        self.assertEqual(family['unresolved_component_ids'],['D'])
        self.assertEqual(plain_white_evidence({'folder_url':'https://www.dropbox.com/home/White'},'Panel — White and Black'),None)
        self.assertEqual(plain_white_evidence({'folder_url':'https://www.dropbox.com/home/Panel%20White'},'Panel — Bronze'),None)
        self.assertEqual(plain_white_evidence({'folder_url':'https://www.dropbox.com/home/Panel%20Blue%20and%20White'},'Panel'),None)
        self.add('field','A','Name',{'decision':'edit','value':'Acanthus and Moon — White'})
        self.assertEqual(self.result()['families']['Acanthus']['white_titles_missing'],0)

    def test_white_entry_without_individual_image_is_separately_reported(self):
        self.add('image','A','product',{'decision':'exclude'})
        family=self.result()['families']['Acanthus']
        self.assertEqual(family['white_individual_gaps'],1)
        self.assertEqual(family['white_entries_missing'],1)

    def test_excluded_product_does_not_create_installation_requirement(self):
        before=self.result()['families']['Acanthus']['in_situ_gaps']
        self.add('product','B','',{'decision':'exclude'})
        self.assertEqual(self.result()['families']['Acanthus']['in_situ_gaps'],before-1)
        self.add('product','A','',{'decision':'exclude'})
        self.assertEqual(self.result()['families']['Acanthus']['components'][0]['status'],'white_entry_excluded')

    def test_confirmed_design_group_prevents_false_missing_white_without_merging_options(self):
        self.cat.products['B']['component_id']='RETAINED-OTHER-NAME'
        self.cat.working_design_groups={pid:{'working_design_group_id':'C1','grouping_basis':'Existing owner-confirmed relief-design equivalence only'} for pid in ['A','B']}
        family=self.result()['families']['Acanthus']
        self.assertEqual(family['component_count'],3)
        self.assertEqual(family['design_group_count'],2)
        self.assertEqual(family['option_count'],4)
        self.assertEqual(family['white_entries_missing'],1)
        group=family['components'][0]
        self.assertEqual(group['product_ids'],['A','B'])
        self.assertEqual(group['white_product_ids'],['A'])
        self.assertEqual(group['retained_component_ids'],['C1','RETAINED-OTHER-NAME'])
        self.assertEqual(self.result()['products']['B']['in_situ']['count'],0)


if __name__=='__main__':unittest.main()
