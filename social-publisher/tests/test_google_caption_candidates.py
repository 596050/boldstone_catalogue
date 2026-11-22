import sys,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from common import Hold
from google_business import GoogleBusinessProfile
class CandidateChecks(unittest.TestCase):
 def adapter(self,matched):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.directory=Path(self.temp.name);(self.directory/'evidence').mkdir();self.ops=[];self.post=None
  context={'id':'one','caption':'Archive sculpture','profile_hash':'profile','location_id':'123','inventory_url':'https://www.google.com/local/business/123/promote/updates','purchase_url':'https://boldstonesculpture.com/?utm_content=one','button_label':'Learn more'}
  def navigate(reader,url,*args,**kw):self.post=url.rsplit('/',2)[1]
  def call(reader,r):
   self.ops.append(r['op'])
   if r['op']=='probe':return {'googlePostCards':[{'caption':context['caption'],'record_names':['accounts/-/locations/123/localPosts/'+p]} for p in ['456','789']]}
   if r['op']=='snapshot':return {'editors':[{'tag':'TEXTAREA','html':'<textarea maxlength="1500">','value':context['caption']}],'inputs':[{'html':'<input type="url">','value':context['purchase_url'] if self.post in matched else 'https://boldstonesculpture.com/?utm_content=other'}],'controls':[{'tag':'BUTTON','name':'Learn more'}]}
   raise AssertionError(r['op'])
  workflow=SimpleNamespace(directory=self.directory,chrome=SimpleNamespace(call=call,navigate=navigate),wait=lambda *a,**kw:None)
  return GoogleBusinessProfile(workflow),context
 def test_equal_captions_select_only_the_exact_saved_destination(self):
  adapter,c=self.adapter({'789'});post,proof=adapter.resolve_caption_record('verification',c,{})
  self.assertEqual(post,'789');self.assertTrue(Path(proof['caption_resolution_evidence_path']).exists());self.assertEqual(set(self.ops),{'probe','snapshot'})
 def test_two_matching_records_or_no_matching_record_remain_ambiguous(self):
  for matched in [set(),{'456','789'}]:
   adapter,c=self.adapter(matched)
   with self.assertRaises(Hold) as caught:adapter.resolve_caption_record('verification',c,{})
   self.assertEqual(caught.exception.code,'GOOGLE_NATIVE_DESTINATION_AMBIGUOUS')
if __name__=='__main__':unittest.main()
