from collections import defaultdict
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import json
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from catalogue import Catalogue
from dropbox_sync import ROOT_PATH,ROOT_ID,apply_inventory,link,read_inventory,in_situ_folder
from dropbox_sync_worker import OriginalError,apply_entries,collect,atomic_json
from media import enrich
from projection import Projection
from review_coverage import product_coverage


def page(entries,cursor,more=False):return SimpleNamespace(entries=entries,cursor=cursor,has_more=more)

class CursorTests(unittest.TestCase):
    def test_all_pages_including_empty_page_before_commit(self):
        row={'id':'id:new','kind':'file','name':'new.png','path':ROOT_PATH+'/new.png'}
        class Client:
            def files_list_folder(self,*args,**kwargs):return page([],'a',True)
            def files_list_folder_continue(self,c):return page([row],'b')
        records,cursor,scan=collect(Client(),{},ROOT_PATH,ROOT_ID,encode=lambda x:x)
        self.assertIn('id:new',records);self.assertEqual(cursor,'b');self.assertEqual(scan['pages'],2)
        self.assertFalse(scan['has_more'])

    def test_partial_failure_does_not_change_committed_cursor_or_entries(self):
        prior={'cursor':'saved','records':{'id:old':{'id':'id:old','kind':'file','path':ROOT_PATH+'/old.jpg'}}}
        before=deepcopy(prior)
        class Client:
            def files_list_folder_continue(self,c):
                if c=='saved':return page([{'kind':'deleted','path':ROOT_PATH+'/old.jpg'}],'halfway',True)
                raise OSError('offline')
        with self.assertRaises(OSError):collect(Client(),prior,ROOT_PATH,ROOT_ID,encode=lambda x:x)
        self.assertEqual(prior,before)

    def test_expired_cursor_rebuilds_inventory(self):
        class Reset(Exception):error=SimpleNamespace(is_reset=lambda:True)
        class Client:
            def files_list_folder_continue(self,c):raise Reset()
            def files_list_folder(self,*a,**kw):return page([],'reset-cursor')
        records,cursor,scan=collect(Client(),{'cursor':'expired','records':{'old':{}}},ROOT_PATH,ROOT_ID,encode=lambda x:x)
        self.assertEqual(set(records),{ROOT_ID});self.assertEqual(cursor,'reset-cursor');self.assertTrue(scan['cursor_reset'])

    def test_non_reset_error_does_not_turn_into_empty_library(self):
        class Client:
            def files_list_folder_continue(self,c):raise OSError('unavailable')
        with self.assertRaises(OSError):collect(Client(),{'cursor':'saved'},ROOT_PATH,ROOT_ID)

    def test_scope_boundary_is_not_a_prefix_match(self):
        with self.assertRaises(OriginalError):apply_entries({},[{'kind':'deleted','path':ROOT_PATH+' Backup/White'}],ROOT_PATH)

    def test_same_id_folder_rename_moves_children_and_deletion_removes_descendants(self):
        records={'folder':{'id':'folder','kind':'folder','path':ROOT_PATH+'/Old'},
                 'file':{'id':'file','kind':'file','path':ROOT_PATH+'/Old/x.png'}}
        apply_entries(records,[{'id':'folder','kind':'folder','path':ROOT_PATH+'/New'}],ROOT_PATH)
        self.assertEqual(records['file']['path'],ROOT_PATH+'/New/x.png')
        apply_entries(records,[{'kind':'deleted','path':ROOT_PATH+'/New'}],ROOT_PATH)
        self.assertEqual(records,{})

    def test_atomic_json_and_corrupt_inventory_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'inventory.json';atomic_json(path,{'old':True});atomic_json(path,{'new':True})
            self.assertEqual(json.loads(path.read_text()),{'new':True});self.assertEqual(path.stat().st_mode&0o777,0o600)
            with self.assertRaises(ValueError):read_inventory(path)


class OverlayTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.white=ROOT_PATH+'/Acanthus/White';self.gold=ROOT_PATH+'/Acanthus/Gold'
        self.base=Catalogue.__new__(Catalogue);b=self.base
        b.project=self.root;b.source={'register_sha256':'same-register','gallery_sha256':'same-gallery'}
        b.products={pid:{'id':pid,'name':pid,'family':'Acanthus','folder_url':link(folder),'primary_id':'id:old' if pid=='white' else None,'fields':[{'key':'Weight','value':'6 kg'}]}
                    for pid,folder in [('white',self.white),('gold',self.gold)]}
        b.products['white']['image_url']=link(self.white+'/old.jpg','preview')
        b.assets={};b.paths={};b.preview_paths={};b.edges=defaultdict(dict)
        b._asset('id:old','old.jpg','Dropbox','Acanthus',link(self.white+'/old.jpg','preview'),link(self.white),'id:white','individual',
                 'CURRENT_NATIVE_FILE_AND_ACTUAL_PARENT_VERIFIED',[],{'path':self.white+'/old.jpg'})
        b.assets['id:old']['original']={'dropbox_content_hash':'a'*64,'bytes':100}
        b.edges['white']['id:old']={'asset_id':'id:old','uses':['selected_primary'],'qualifications':[],'association_ids':[],'tier':'accepted'}
        enrich(b,self.root)
        self.state={'generation':1,'checked_utc':'now','signature':'snapshot','image_count':2,'new_image_count':1,'media':{},'retired':{},
                    'snapshot_path':str(self.root/'snapshot.json'),'snapshot_sha256':'sha',
                    'records':{ROOT_ID:{'id':ROOT_ID,'kind':'folder','name':'Wall Sculptures','path':ROOT_PATH},
                     'id:white':{'id':'id:white','kind':'folder','path':self.white,'name':'White'},
                     'id:gold':{'id':'id:gold','kind':'folder','path':self.gold,'name':'Gold'},
                     'id:old':self.file('id:old','old.jpg','a'*64),
                     'id:new':self.file('id:new','new.png','b'*64)}}

    def file(self,fid,name,h):
        return {'id':fid,'name':name,'kind':'file','path':self.white+'/'+name,'rev':'rev1','content_hash':h,'bytes':100,'modified':'now','folder_id':'id:white'}

    def tearDown(self):self.temp.cleanup()

    def test_new_image_attaches_by_folder_without_role_or_listing_approval(self):
        before=deepcopy(self.base.products)
        cat=apply_inventory(self.base,self.state,self.root);view=Projection(cat,[])
        self.assertIn('id:new',view.edges['white']);self.assertNotIn('id:new',view.edges['gold'])
        self.assertEqual(cat.assets['id:new']['types'],[])
        self.assertEqual(view.decision('image','white','id:new'),{})
        self.assertEqual(cat.products['white']['primary_id'],'id:old')
        self.assertEqual(cat.products,before);self.assertNotIn('id:new',self.base.assets)
        self.assertEqual(cat.source['register_sha256'],'same-register')

    def test_manual_removal_and_saved_tags_survive_every_refresh(self):
        cat=apply_inventory(self.base,self.state,self.root)
        rows=[{'kind':'assignment','product_id':'white','item_id':'id:new','version':1,'data':{'state':'removed'}},
              {'kind':'asset','product_id':'','item_id':'id:new','version':1,'data':{'tags':['advertising'],'types':['in_situ']}}]
        view=Projection(cat,deepcopy(rows))
        self.assertNotIn('id:new',view.edges['white']);self.assertIn('id:new',view.removed['white'])
        self.assertEqual(view.decision('asset','','id:new')['tags'],['advertising'])
        self.assertEqual(rows[0]['data'],{'state':'removed'})

    def test_identical_new_bytes_are_deduplicated(self):
        self.state['records']['id:new']['content_hash']='a'*64
        cat=apply_inventory(self.base,self.state,self.root);view=Projection(cat,[])
        self.assertEqual(len(view.images('white')),1)
        self.assertEqual(set(view.member_ids(view.cid('id:old'))),{'id:old','id:new'})

    def test_deleted_id_stays_suppressed_but_live_reupload_can_be_reviewed(self):
        del self.state['records']['id:old'];self.state['records']['id:new']['content_hash']='a'*64
        cat=apply_inventory(self.base,self.state,self.root)
        rows=[{'kind':'deletion','product_id':'','item_id':'id:old','version':1,'data':{'state':'deleted'}}]
        view=Projection(cat,rows)
        self.assertNotIn('id:old',view.edges['white']);self.assertIn('id:new',view.edges['white'])
        self.assertEqual(rows[0]['data']['state'],'deleted')

    def test_unmapped_new_finish_is_only_a_related_candidate(self):
        path=ROOT_PATH+'/Acanthus/Blue';self.state['records']['blue']={'id':'blue','kind':'folder','name':'Blue','path':path}
        self.state['records']['id:new']['path']=path+'/new.png'
        cat=apply_inventory(self.base,self.state,self.root)
        self.assertEqual(cat.edges['white']['id:new']['tier'],'related')
        self.assertEqual(cat.edges['gold']['id:new']['tier'],'related')

    def test_changed_original_never_reuses_old_preview_or_listing_approval(self):
        old=Path(self.root/'old.jpg');old.write_bytes(b'old-image')
        self.base.paths['id:old']=(old,'cached source')
        self.state['records']['id:old']['content_hash']='c'*64
        cat=apply_inventory(self.base,self.state,self.root)
        self.assertNotIn('id:old',cat.paths)
        record={'kind':'image','product_id':'white','item_id':'id:old','version':1,
                'data':{'decision':'reviewed','uses':['listing'],'primary':True},
                'original':{'asset':{'original':{'dropbox_content_hash':'a'*64}}}}
        view=Projection(cat,[record]);self.assertEqual(view.decision('image','white','id:old')['uses'],[])
        self.assertEqual(record['data']['uses'],['listing'])
        record['data']['reviewed_content_hash']='c'*64
        self.assertEqual(Projection(cat,[record]).decision('image','white','id:old')['uses'],['listing'])

    def test_retired_import_retains_review_identity_without_displaying_image(self):
        self.state['retired']['id:new']=self.state['records'].pop('id:new')
        cat=apply_inventory(self.base,self.state,self.root)
        self.assertIn('id:new',cat.assets)
        self.assertNotIn('id:new',{a['id'] for a in Projection(cat,[]).library()})

    def test_stable_folder_rename_keeps_product_association(self):
        new=self.white+' Renamed';self.state['records']['id:white']['path']=new
        for fid in ['id:old','id:new']:self.state['records'][fid]['path']=new+'/'+self.state['records'][fid]['name']
        cat=apply_inventory(self.base,self.state,self.root)
        self.assertIn('id:new',cat.edges['white']);self.assertEqual(cat.assets['id:new']['folder_id'],'id:white')
        self.assertEqual(cat.assets['id:new']['folder_url'],link(new))
        self.assertEqual(cat.products['white']['folder_url'],link(new))
        self.assertEqual(cat.products['white']['image_url'],link(new+'/old.jpg','preview'))

    def situ_folder(self,path=None):
        path=path or self.white+' In Situ'
        self.state['records']['id:situ']={'id':'id:situ','kind':'folder','path':path,'name':Path(path).name}
        self.state['records']['id:new']['path']=path+'/new.png'
        return path

    def test_in_situ_sibling_is_visible_under_exact_product_and_counts_without_listing_approval(self):
        path=self.situ_folder()
        cat=apply_inventory(self.base,self.state,self.root);view=Projection(cat,[])
        self.assertEqual(cat.assets['id:new']['types'],['in_situ'])
        self.assertEqual(cat.edges['white']['id:new']['tier'],'folder')
        self.assertNotIn('id:new',cat.edges['gold'])
        self.assertEqual(cat.assets['id:new']['folder_type_evidence'][0]['folder_url'],link(path))
        self.assertEqual(view.decision('image','white','id:new'),{})
        result=product_coverage(view,cat.products['white'])
        self.assertEqual(result['in_situ']['count'],1);self.assertEqual(result['in_situ']['listing_count'],0)

    def test_explicit_type_override_and_removed_assignment_win_over_folder_defaults(self):
        self.situ_folder();cat=apply_inventory(self.base,self.state,self.root)
        for types in [[],['detail'],['in_situ','group']]:
            rows=[{'kind':'asset','product_id':'','item_id':'id:new','version':1,'data':{'types':types,'tags':['keep-me']}}]
            view=Projection(cat,rows)
            self.assertEqual(view.decision('asset','','id:new')['types'],types)
            self.assertEqual(product_coverage(view,cat.products['white'])['in_situ']['count'],int('in_situ' in types))
            rows.append({'kind':'assignment','product_id':'white','item_id':'id:new','version':1,'data':{'state':'removed'}})
            self.assertEqual(product_coverage(Projection(cat,rows),cat.products['white'])['in_situ']['count'],0)

    def test_folder_rename_and_file_move_refresh_inferred_type(self):
        path=self.situ_folder();first=apply_inventory(self.base,self.state,self.root)
        self.assertIn('in_situ',first.assets['id:new']['types'])
        self.state['records']['id:new']['path']=self.white+'/new.png'
        self.assertNotIn('in_situ',apply_inventory(self.base,self.state,self.root).assets['id:new']['types'])
        self.state['records']['id:new']['path']=path+'/new.png'
        renamed=ROOT_PATH+'/Acanthus/White References'
        apply_entries(self.state['records'],[{'id':'id:situ','kind':'folder','path':renamed,'name':'White References'}],ROOT_PATH)
        self.assertNotIn('in_situ',apply_inventory(self.base,self.state,self.root).assets['id:new']['types'])

    def test_unmatched_or_ambiguous_stem_has_type_but_no_exact_product_assignment(self):
        self.situ_folder(ROOT_PATH+'/Acanthus/White and Gold In Situ')
        cat=apply_inventory(self.base,self.state,self.root)
        self.assertEqual(cat.assets['id:new']['types'],['in_situ'])
        self.assertEqual(cat.edges['white']['id:new']['tier'],'related')
        self.situ_folder();self.base.products['gold']['folder_url']=link(self.white)
        cat=apply_inventory(self.base,self.state,self.root)
        self.assertEqual(cat.edges['white']['id:new']['tier'],'related')
        self.assertEqual(cat.edges['gold']['id:new']['tier'],'related')

    def test_nested_role_folder_and_case_variants_keep_exact_stem(self):
        for suffix in [' In Situ',' IN-SITU',' in_situ']:
            context=in_situ_folder(self.white+suffix+'/More photos')
            self.assertEqual(context['product_path'],self.white)
        path=self.situ_folder(self.white+'/In Situ')
        nested=path+'/More photos'
        self.state['records']['id:nested']={'id':'id:nested','kind':'folder','path':nested,'name':'More photos'}
        self.state['records']['id:new']['path']=nested+'/new.png'
        cat=apply_inventory(self.base,self.state,self.root)
        self.assertEqual(cat.edges['white']['id:new']['tier'],'folder')
        self.assertEqual(cat.assets['id:new']['folder_type_evidence'][0]['folder_id'],'id:situ')

    def test_existing_related_image_is_promoted_after_matching_role_folder_move(self):
        self.situ_folder()
        self.base.edges['white']['id:new']={'asset_id':'id:new','tier':'related','uses':[], 'qualifications':[],'association_ids':[]}
        self.base.assets['id:new']=deepcopy(self.base.assets['id:old']);self.base.assets['id:new']['id']='id:new'
        cat=apply_inventory(self.base,self.state,self.root)
        self.assertEqual(cat.edges['white']['id:new']['tier'],'folder')

    def test_role_folder_match_survives_product_folder_prefix_rename(self):
        new=self.white+' Renamed'
        self.state['records']['id:white']['path']=new
        self.state['records']['id:old']['path']=new+'/old.jpg'
        self.situ_folder(new+' In Situ')
        cat=apply_inventory(self.base,self.state,self.root)
        self.assertEqual(cat.edges['white']['id:new']['tier'],'folder')


if __name__=='__main__':unittest.main()
