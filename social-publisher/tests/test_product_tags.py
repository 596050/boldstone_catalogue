import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from common import Hold,atomic_json
from settings import Settings
from workflow import Workflow


class NativeReader:
    def __init__(self):
        self.calls=[]
        self.bindings={'verification':{'url':'https://business.facebook.com/latest/composer/?business_content_id=45'}}
    def navigate(self,*args,**kwargs):self.calls.append(('navigate',args))
    def sync_expected_navigation(self,*args):self.calls.append(('sync',args))
    def call(self,name,request):
        self.calls.append((request['op'],request))
        if request['op']=='exists':return {'exists':True}
        if request['op']=='snapshot':return {'controls':[{'name':'Select item with ID 45'}]}
        if request['op']=='assert':raise Hold('TEXT_READBACK_CHANGED','The published product count is zero')
        return {'ok':True}


class ProductTags(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.directory=Path(self.temp.name)
        self.settings=Settings();self.reader=NativeReader()
        self.context={**self.settings.profile('boldstone_instagram'),'profile_id':'boldstone_instagram',
                      'id':'job-one','media_sha256':'a'*64,'caption':'One exact caption','title':'White relief',
                      'product_tag':{'name':'White relief','price_text':'£34.20'}}
        self.recipe=self.settings.workflow(self.settings.profile('boldstone_instagram'))
    def tearDown(self):self.temp.cleanup()
    def proof(self,price='£34.20'):
        atomic_json(self.directory/'evidence/job-one-product-tag.json',{'product_tag':{
            'job':'job-one','sha256':'a'*64,'name':'White relief','price_text':price,
            'persisted_editor_readback':True}})
    def test_different_product_price_is_rejected_before_native_navigation(self):
        self.proof('£44.20')
        with self.assertRaises(Hold) as result:
            Workflow(self.settings,self.reader,self.directory).verify_product_tag(self.context,self.recipe)
        self.assertEqual(result.exception.code,'PRODUCT_TAG_RECEIPT_MISSING')
        self.assertEqual(self.reader.calls,[])
    def test_zero_persisted_tags_cannot_be_reported_as_success(self):
        self.proof()
        with self.assertRaises(Hold) as result:
            Workflow(self.settings,self.reader,self.directory).verify_product_tag(self.context,self.recipe)
        self.assertEqual(result.exception.code,'TEXT_READBACK_CHANGED')
        labels=[spec.get('name') for op,request in self.reader.calls if op=='click' for spec in request['locator']]
        self.assertNotIn('Publish',labels)
        self.assertNotIn('Discard Changes',labels)


if __name__=='__main__':unittest.main()
