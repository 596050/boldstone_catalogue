import copy,sys,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from common import Hold,atomic_json,digest
from google_public import public_record,native_media_checks,GooglePublicReadback

class PublicRecordChecks(unittest.TestCase):
 def setUp(self):
  self.c={'caption':'An archive sculpture film.','account_name':'Boldstone','location_id':'123','profile_hash':'profile','button_label':'Learn more','purchase_url':'https://boldstonesculpture.com/?utm_content=film-1','media_type':'video/mp4','media_sha256':'a'*64,'video_duration':3.033333,'video_width':720,'video_height':1280}
  self.cal={'feature_id':'0x1:0x2'}
  self.article={'url':'https://www.google.com/search?q=Boldstone#lpstate=pid:456','html':'<article data-feature-id="0x1:0x2" data-post-id="456">','text':'Boldstone\nAn archive sculpture film.\nLearn more','links':[{'text':'Learn more','href':self.c['purchase_url']}]}
  self.caption={'text':self.c['caption']};self.author={'text':'Boldstone'}
 def check(self):return public_record(self.article,self.caption,self.author,self.c,'456',self.cal)
 def test_exact_public_article_caption_author_and_destination_are_required(self):
  self.assertEqual(self.check()['post_id'],'456')
 def test_a_changed_fragment_does_not_make_the_previous_article_the_requested_post(self):
  self.article['html']='<article data-feature-id="0x1:0x2" data-post-id="999">'
  with self.assertRaises(Hold):self.check()
 def test_a_different_business_feature_is_rejected(self):
  self.article['html']='<article data-feature-id="0x9:0x9" data-post-id="456">'
  with self.assertRaises(Hold):self.check()
 def test_wrong_author_or_caption_never_passes(self):
  self.author['text']='Other business'
  with self.assertRaises(Hold):self.check()
  self.author['text']='Boldstone';self.caption['text']='Another film'
  with self.assertRaises(Hold):self.check()
 def test_pending_or_owner_only_records_do_not_pass(self):
  for label in ['Pending','Rejected','Not approved','Only visible to you']:
   self.article['text']='Boldstone\nAn archive sculpture film.\n'+label
   with self.assertRaises(Hold):self.check()
 def test_missing_or_changed_action_destination_does_not_pass(self):
  self.article['links'][0]['href']='https://boldstonesculpture.com/?utm_content=film-2'
  with self.assertRaises(Hold):self.check()
  self.article['links']=[]
  with self.assertRaises(Hold):self.check()
 def test_a_loading_dialog_is_not_a_post(self):
  self.article['html']='<div role="dialog">Loading…</div>'
  with self.assertRaises(Hold):self.check()
 def test_native_video_hash_metadata_and_full_decode_are_all_required(self):
  with tempfile.TemporaryDirectory() as directory:
   path=Path(directory)/'observed.mp4';path.write_bytes(b'native fixture bytes')
   m={'path':str(path),'url':'https://lh3.googleusercontent.com/geougc/movie','native_sha256':digest(path.read_bytes()),'input_sha256':'a'*64,'complete_movie_decode_exit_code':0,'decode_errors':'','metadata':{'streams':[{'codec_type':'video','width':720,'height':1280,'duration':'3.033333'}]}}
   self.assertAlmostEqual(native_media_checks(m,self.c)['duration'],3.033333)
   for field,value in [('native_sha256','b'*64),('input_sha256','b'*64),('complete_movie_decode_exit_code',1),('decode_errors','decode failure')]:
    with self.assertRaises(Hold):native_media_checks({**m,field:value},self.c)
   for key,value in [('width',1280),('duration','12.0')]:
    bad=copy.deepcopy(m);bad['metadata']['streams'][0][key]=value
    with self.assertRaises(Hold):native_media_checks(bad,self.c)
 def test_calibration_is_bound_to_the_profile_and_unchanged_native_evidence(self):
  with tempfile.TemporaryDirectory() as directory:
   folder=Path(directory);ref=folder/'source.json';ref.write_text('native evidence');cal=folder/'calibration.json'
   data={'location_id':'123','profile_hashes':['profile'],'public_base_url':'https://www.google.com/search?q=Boldstone&stick=observed','references':[{'path':str(ref),'sha256':digest(ref.read_bytes())}]};atomic_json(cal,data)
   adapter=GooglePublicReadback(SimpleNamespace(chrome=None,directory=folder),cal,'456')
   self.assertEqual(adapter.calibration(self.c)['location_id'],'123')
   with self.assertRaises(Hold):adapter.calibration({**self.c,'profile_hash':'changed'})
   ref.write_text('changed evidence')
   with self.assertRaises(Hold):adapter.calibration(self.c)

if __name__=='__main__':unittest.main()
