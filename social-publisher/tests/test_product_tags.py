import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from common import Hold,atomic_json
from settings import Settings
from workflow import Workflow


class NativeReader:
    def __init__(self):
        self.calls=[]
        self.bindings={'verification':{'url':'https://business.facebook.com/latest/composer/?business_content_id=45'}}
    def navigate(self,*args,**kwargs):self.calls.append(('navigate',args))
    def bound(self,name):return self.bindings[name],{}
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


class PublishedRows(unittest.TestCase):
    def setUp(self):
        self.settings=Settings()
        self.context={**self.settings.profile('boldstone_instagram'),'id':'job',
                      'title':'White relief','caption':'Every authored line\nwith the exact destination'}
        self.recovery={'search':[{'selector':'input','name':'Search by ID or caption'}],
                       'row':[{'selector':'[role=row]','contains':self.context['caption']}]}
        self.reader=NativeReader()
        self.reader.bindings['verification']['url']=self.context['inventory_url']
        self.events=[]
        self.snapshots=0
    def call(self,name,request):
        self.events.append(request)
        if request['op']=='exists':return {'exists':True}
        if request['op']=='snapshot':
            self.snapshots+=1
            if self.snapshots==1:raise Hold('CONTROL_MISSING','Row replaced during filtering')
            return {'controls':[{'name':'Select item with ID 45'}]}
        return {'ok':True}
    def test_replaced_row_retries_only_the_complete_caption_read(self):
        self.reader.call=self.call
        with patch('workflow.time.sleep'):
            result=Workflow(self.settings,self.reader,Path('.')).meta_published_row(self.context,self.recovery)
        self.assertEqual(result['controls'][0]['name'],'Select item with ID 45')
        self.assertEqual(self.snapshots,2)
        self.assertTrue(all(e['scope']==self.recovery['row'] for e in self.events if e['op']=='snapshot'))
        self.assertNotIn('set_text',[e['op'] for e in self.events])
        self.assertEqual(self.reader.calls,[])
    def test_ambiguous_row_does_not_retry_or_broaden_the_caption(self):
        def ambiguous(name,request):
            self.events.append(request)
            if request['op']=='snapshot':raise Hold('AMBIGUOUS_CONTROL')
            return {'exists':True}
        self.reader.call=ambiguous
        with self.assertRaises(Hold) as result:
            Workflow(self.settings,self.reader,Path('.')).meta_published_row(self.context,self.recovery)
        self.assertEqual(result.exception.code,'AMBIGUOUS_CONTROL')
        self.assertEqual(sum(e['op']=='snapshot' for e in self.events),1)
    def test_different_filter_is_updated_once_before_reading(self):
        self.snapshots=1
        def different(name,request):
            if request['op']=='assert':raise Hold('TEXT_READBACK_CHANGED')
            return self.call(name,request)
        self.reader.call=different
        Workflow(self.settings,self.reader,Path('.')).meta_published_row(self.context,self.recovery)
        self.assertEqual([e['value'] for e in self.events if e['op']=='set_text'],['White relief'])
    def test_missing_row_has_a_bounded_wait(self):
        def missing(name,request):
            if request['op']=='snapshot':raise Hold('CONTROL_MISSING')
            return {'exists':True}
        self.reader.call=missing
        with patch('workflow.time.monotonic',side_effect=[0,0,31]):
            with self.assertRaises(Hold) as result:
                Workflow(self.settings,self.reader,Path('.')).meta_published_row(self.context,self.recovery)
        self.assertEqual(result.exception.code,'CONTROL_MISSING')


if __name__=='__main__':unittest.main()
