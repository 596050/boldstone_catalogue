from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace as NS
import json
import unittest
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from organisation import folder_for_components, NeedsChoice, plan, slug
from component_links import match_group
from organise_dropbox import organise
from dropbox_sync import ROOT_PATH, link
from test_deletions import FakeDropbox, Missing, TARGET, KEEPER

FAMILY = ROOT_PATH + '/Ammonite'
SINGLE = FAMILY + '/Ammonite Large 1 White'
GROUP = FAMILY + '/Ammonite Large 1 and Ammonite Large 2 White In Situ'


def products():
    return {pid: {'id': pid, 'name': name, 'family': 'Ammonite', 'folder_url': link(FAMILY + '/' + name)}
            for pid, name in [('L1','Ammonite Large 1 White'), ('L2','Ammonite Large 2 White'),
                              ('S1','Ammonite Small 1 White'), ('B1','Ammonite Large 1 Bronze')]}


class FolderPolicyTests(unittest.TestCase):
    def test_single_and_exact_group_no_size_or_finish_leak(self):
        p = products()
        self.assertEqual(folder_for_components(p, ['L1'], ['in_situ']), SINGLE + ' In Situ')
        self.assertEqual(folder_for_components(p, ['L2','L1'], ['group','product','in_situ']), GROUP)
        self.assertEqual(folder_for_components(p, ['L1','L2'], ['in_situ']), GROUP)
        self.assertNotIn('Small', GROUP)
        self.assertEqual(folder_for_components(p, ['L1','B1'], ['in_situ']),
            FAMILY + '/Ammonite Large 1 Bronze and Ammonite Large 1 White In Situ')

    def test_role_removal_and_multiple_tags_use_one_folder(self):
        self.assertEqual(folder_for_components(products(), ['L1'], ['product','group']), SINGLE)
        self.assertEqual(folder_for_components(products(), ['L1'], []), SINGLE)
        self.assertEqual(folder_for_components(products(), ['L1'], ['detail','in_situ','workshop']), SINGLE + ' In Situ')
        self.assertEqual(folder_for_components(products(), ['L1'], ['detail']), SINGLE + ' Details')

    def test_ambiguous_anchors_and_unknown_components_do_not_guess(self):
        p=products();p['D']=deepcopy(p['L1'])
        for ids in ([], ['unknown'], ['L1'], ['L1','D']):
            with self.subTest(ids=ids),self.assertRaises(NeedsChoice):folder_for_components(p,ids,['in_situ'])

    def test_cross_family_unverified_and_path_injection_rejected(self):
        p=products();p['X']={'folder_url':link(ROOT_PATH+'/Other/Other White')}
        for ids in (['X','L1'],):
            with self.assertRaises(NeedsChoice):folder_for_components(p,ids,['in_situ'])
        for path in ('https://example.org/A',link(ROOT_PATH+'/Ammonite'),link(ROOT_PATH+'/Ammonite/a/b')):
            p['X']['folder_url']=path
            with self.assertRaises(NeedsChoice):folder_for_components(p,['X'],['in_situ'])

    def test_names_with_and_are_not_split_into_imaginary_components(self):
        p={'A':{'folder_url':link(FAMILY+'/Acanthus and Moon White')},
           'B':{'folder_url':link(FAMILY+'/Soundwave White')}}
        self.assertEqual(folder_for_components(p,['A'],['in_situ']),FAMILY+'/Acanthus and Moon White In Situ')
        self.assertEqual(folder_for_components(p,['B','A'],['in_situ']),FAMILY+'/Acanthus and Moon and Soundwave White In Situ')

    def test_ampersands_match_filename_pass_and_group_roles_preserve_membership(self):
        self.assertEqual(slug('Spiralfish Wave & Tide'),'spiralfish-wave-and-tide')
        p=products();anchors={x['name'].casefold():{pid} for pid,x in p.items()}
        for role in ('Rear','Workshop','Details','In Situ'):
            self.assertEqual(match_group('Ammonite Large 1 and Ammonite Large 2 White '+role,anchors),['L1','L2'])


class OrganiseDropbox(FakeDropbox):
    def __init__(self):
        super().__init__()
        self.folders={p:NS(id='id:folder'+str(i),name=p.split('/')[-1],path_display=p,path_lower=p.lower())
                      for i,p in enumerate((FAMILY,SINGLE))}
        self.files[TARGET].name='old_013.JPG';self.files[TARGET].path_display=SINGLE+'/old_013.JPG'
        self.files[TARGET].path_lower=self.files[TARGET].path_display.lower()
        self.moves=[];self.creates=[];self.extra=[];self.pages=[];self.lost_move=False;self.reject_move=False
        self.create_race=False;self.block_folder=False

    def files_get_metadata(self,path,**kwargs):
        if path in self.gone:raise Missing()
        for item in [*self.files.values(),*self.folders.values(),*self.extra]:
            if path==item.id or path.casefold()==item.path_display.casefold():return deepcopy(item)
        raise Missing()

    def files_create_folder_v2(self,path,autorename):
        self.creates.append((path,autorename))
        if self.block_folder:raise PermissionError()
        self.folders[path]=NS(id='id:newfolder'+str(len(self.folders)),name=path.split('/')[-1],path_display=path,path_lower=path.lower())
        if self.create_race:raise TimeoutError()
        return NS(metadata=self.folders[path])

    def files_list_folder(self,path,**kwargs):
        folder=self.files_get_metadata(path)
        entries=[deepcopy(e) for e in [*self.files.values(),*self.extra] if str(Path(e.path_display).parent).lower()==folder.path_display.lower()]
        if self.pages:self.remaining=entries[1:];return NS(entries=entries[:1],has_more=True,cursor='page1')
        return NS(entries=entries,has_more=False)

    def files_list_folder_continue(self,cursor):
        return NS(entries=self.remaining,has_more=False)

    def files_move_v2(self,fid,dest,autorename,allow_ownership_transfer):
        self.moves.append((fid,dest,autorename,allow_ownership_transfer))
        if self.reject_move:raise TimeoutError()
        if any(x.path_display.casefold()==dest.casefold() for x in [*self.files.values(),*self.extra]):raise ValueError('conflict')
        f=self.files[fid];f.name=Path(dest).name;f.path_display=dest;f.path_lower=dest.lower()
        if self.lost_move:raise TimeoutError()
        return NS(metadata=deepcopy(f))

    def sharing_get_shared_link_metadata(self,url):
        return deepcopy(self.files[TARGET])


class NativeOrganisationTests(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory();self.directory=Path(self.temp.name)/'job';self.client=OrganiseDropbox()
        self.request={'binding':{'id':TARGET,'content_hash':'a'*64,'bytes':68,'path':SINGLE+'/old_013.JPG'},'destination_folder':GROUP}

    def tearDown(self):self.temp.cleanup()
    def run_job(self):return organise(self.client,self.request,self.directory)

    def test_create_and_move_single_original_verify_name_bytes_id_and_links(self):
        self.client.links=[NS(url='https://www.dropbox.com/scl/fi/stable/old_013.JPG',path_lower=self.request['binding']['path'].lower(),name='old_013.JPG')]
        result=self.run_job()
        self.assertEqual(result['state'],'completed');self.assertEqual(result['file']['id'],TARGET)
        self.assertEqual(result['file']['content_hash'],'a'*64);self.assertEqual(result['file']['bytes'],68)
        self.assertEqual(result['file']['path'],GROUP+'/ammonite__ammonite-large-1-and-ammonite-large-2-white-in-situ__001.JPG')
        self.assertEqual(len(result['direct_links_verified']),1)
        self.assertEqual(len(self.client.files),2);self.assertEqual(self.client.creates,[(GROUP,False)])
        self.assertEqual(self.client.moves[0][2:],(False,False))

    def test_idempotent_completed_job_and_new_job_same_destination(self):
        first=self.run_job();self.assertEqual(self.run_job(),first)
        self.assertEqual(len(self.client.moves),1)
        self.request['binding']['path']=first['file']['path'];self.directory=Path(self.temp.name)/'again'
        result=self.run_job();self.assertFalse(result['moved']);self.assertEqual(len(self.client.moves),1)

    def test_existing_case_insensitive_folder_reused_without_duplicates(self):
        value=self.client.folders[SINGLE];self.client.folders[GROUP]=NS(id='id:existing',path_display=GROUP,name=Path(GROUP).name)
        self.request['destination_folder']=GROUP.lower().replace('/boldstone master/products/01 wall sculptures','/BOLDSTONE MASTER/Products/01 Wall Sculptures')
        self.run_job();self.assertFalse(self.client.creates);self.assertEqual(len(self.client.moves),1)

    def test_complete_pagination_and_number_collisions_across_extensions(self):
        prefix='ammonite__ammonite-large-1-and-ammonite-large-2-white-in-situ__'
        self.client.extra=[NS(id='id:e'+str(i),name=prefix+f'{i:03d}'+ext,path_display=GROUP+'/'+prefix+f'{i:03d}'+ext)
                           for i,ext in [(1,'.png'),(2,'.jpg'),(4,'.JPG')]]
        self.client.pages=True
        result=self.run_job();self.assertTrue(result['file']['name'].endswith('__003.JPG'))
        self.assertEqual([e.id for e in self.client.extra],['id:e1','id:e2','id:e4'])

    def test_lost_move_response_is_read_back_once_without_resubmission(self):
        self.client.lost_move=True
        self.assertEqual(self.run_job()['state'],'completed');self.run_job()
        self.assertEqual(len(self.client.moves),1)

    def test_uncertain_move_is_never_repeated_even_after_restart(self):
        self.client.reject_move=True
        self.assertEqual(self.run_job()['state'],'uncertain')
        self.client.reject_move=False
        self.assertEqual(self.run_job()['state'],'uncertain');self.assertEqual(len(self.client.moves),1)

    def test_restart_after_commit_before_receipt_recovers_by_readback(self):
        first=self.run_job();(self.directory/'result.json').unlink()
        recovered=self.run_job();self.assertTrue(recovered['recovered_by_readback'])
        self.assertEqual(recovered['file']['path'],first['file']['path']);self.assertEqual(len(self.client.moves),1)

    def test_folder_creation_race_or_lost_response_reuses_exact_folder(self):
        self.client.create_race=True
        self.assertEqual(self.run_job()['state'],'completed');self.assertEqual(len(self.client.creates),1)

    def test_failed_folder_creation_leaves_original_intact(self):
        self.client.block_folder=True
        with self.assertRaises(ValueError):self.run_job()
        self.assertEqual(self.client.moves,[]);self.assertEqual(self.client.files[TARGET].name,'old_013.JPG')

    def test_changed_bytes_path_missing_file_or_outside_root_never_moves(self):
        for change in ('bytes','path','missing','outside'):
            with self.subTest(change=change):
                self.client=OrganiseDropbox();self.directory=Path(self.temp.name)/change
                if change=='bytes':self.client.files[TARGET].size=999
                if change=='path':self.client.files[TARGET].path_display=SINGLE+'/new.jpg'
                if change=='missing':self.client.gone.add(TARGET)
                if change=='outside':self.client.files[TARGET].path_display='/Outside/test.jpg'
                with self.assertRaises(Exception):self.run_job()
                self.assertEqual(self.client.moves,[]);self.assertEqual(self.client.creates,[])

    def test_file_at_destination_folder_path_never_overwritten(self):
        self.client.files[KEEPER].path_display=GROUP
        with self.assertRaises(ValueError):self.run_job()
        self.assertEqual(self.client.moves,[])

    def test_invalid_target_depth_and_traversal_rejected(self):
        for dest in ('/Other/A',ROOT_PATH+'/A',ROOT_PATH+'/A/../B',ROOT_PATH+'/A/B/C'):
            with self.subTest(dest=dest):
                self.request['destination_folder']=dest
                with self.assertRaises(ValueError):self.run_job()
        self.assertEqual(self.client.moves,[])

    def test_destination_upload_race_is_not_overwritten_and_new_plan_chooses_free_number(self):
        actual=self.client.files_move_v2
        class Rejected(Exception):
            error=NS(is_to=lambda:True,get_to=lambda:NS(is_conflict=lambda:True))
        def collision(fid,dest,**kwargs):
            self.client.extra.append(NS(id='id:upload',name=Path(dest).name,path_display=dest))
            raise Rejected()
        self.client.files_move_v2=collision
        result=self.run_job();self.assertEqual(result['state'],'needs_review');self.assertTrue(result['native_rejected'])
        self.assertEqual(self.client.files[TARGET].name,'old_013.JPG')
        self.client.files_move_v2=actual;self.directory=Path(self.temp.name)/'fresh-review'
        result=self.run_job();self.assertTrue(result['file']['name'].endswith('__002.JPG'))
        self.assertEqual(self.client.extra[0].id,'id:upload')

    def test_source_change_between_listing_and_submission_is_not_moved(self):
        original=self.client.files_list_folder
        def changed(*a,**k):
            result=original(*a,**k);self.client.files[TARGET].rev='changed';return result
        self.client.files_list_folder=changed
        with self.assertRaisesRegex(ValueError,'changed during planning'):self.run_job()
        self.assertEqual(self.client.moves,[])


if __name__=='__main__':unittest.main()
