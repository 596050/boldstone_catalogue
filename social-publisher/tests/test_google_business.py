import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from common import Hold
from google_business import record_identity,saved_details
from settings import Settings


class GoogleNativeChecks(unittest.TestCase):
    def setUp(self):
        self.context={'location_id':'123','caption':'Sculpture - White\n\nA new relief.',
                      'media_sha256':'a'*64,'purchase_url':'https://boldstonesculpture.com/buy/p/sculpture'}
        self.row={'html':'<div data-post-name="accounts/-/locations/123/localPosts/456"></div>',
                  'text':self.context['caption']+'\nBuy\nPublished just now'}
        self.caption={'text':self.context['caption']}
        self.status={'text':'Published just now'}
        self.detail={'editors':[{'tag':'TEXTAREA','html':'<textarea maxlength="1500">','value':self.context['caption']}],
                     'inputs':[{'html':'<input type="url">','value':self.context['purchase_url']}],
                     'controls':[{'tag':'BUTTON','name':'Buy'}]}
        self.photo={'checks':[{'image':True,'photo':{'input_sha256':'a'*64,'width':1254,'height':1254}}]}

    def test_published_record_is_bound_to_exact_location_post_and_caption(self):
        self.assertEqual(record_identity(self.row,self.caption,self.status,self.context)['post_id'],'456')

    def test_another_location_or_ambiguous_record_is_rejected(self):
        for html in [self.row['html'].replace('/123/','/999/'),self.row['html']*2]:
            with self.assertRaises(Hold):record_identity(dict(self.row,html=html),self.caption,self.status,self.context)

    def test_pending_status_cannot_be_replaced_by_published_words_in_caption(self):
        self.row['text']='Published today\n'+self.context['caption']
        with self.assertRaises(Hold) as caught:record_identity(self.row,self.caption,{'text':'Pending'},self.context)
        self.assertEqual(caught.exception.code,'GOOGLE_POST_PENDING_OR_REJECTED')

    def test_missing_published_status_and_caption_mismatches_are_held(self):
        with self.assertRaises(Hold):record_identity(self.row,{'text':'Different post'},self.status,self.context)
        with self.assertRaises(Hold):record_identity(self.row,self.caption,{'text':'Uploaded'},self.context)

    def test_saved_buy_destination_and_loaded_photo_are_verified(self):
        self.assertEqual(saved_details(self.detail,self.photo,self.context)['purchase_links'][0]['expected'],self.context['purchase_url'])

    def test_wrong_saved_destination_missing_button_or_changed_description_are_held(self):
        for key,value in [('inputs',[{'html':'<input type="url">','value':'https://example.com/'}]),('controls',[]),('editors',[])]:
            detail=copy.deepcopy(self.detail);detail[key]=value
            with self.assertRaises(Hold):saved_details(detail,self.photo,self.context)

    def test_missing_duplicate_unloaded_and_cross_job_photo_proofs_are_held(self):
        for photo in [{'checks':[]},{'checks':self.photo['checks']*2},{'checks':[{'image':True,'photo':{'input_sha256':'b'*64,'width':1254,'height':1254}}]},{'checks':[{'image':True,'photo':{'input_sha256':'a'*64,'width':0,'height':1254}}]}]:
            with self.assertRaises(Hold):saved_details(self.detail,photo,self.context)

    def test_google_navigation_never_adopts_another_profile_or_search_page(self):
        profile={'platform':'google_business_profile','location_id':'123','allowed_hosts':['www.google.com']}
        Settings.check_url(profile,'https://www.google.com/local/business/123/promote/updates/456/edit')
        for url in ['https://www.google.com/local/business/999/promote/updates','https://www.google.com/search?q=Boldstone']:
            with self.assertRaises(Hold):Settings.check_url(profile,url)


if __name__=='__main__':unittest.main()
