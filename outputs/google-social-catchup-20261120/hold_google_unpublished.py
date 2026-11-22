"""Preserve a verified server-side Pending/Rejected record and release its owned form."""
import json,re,sys
from pathlib import Path
OUT=Path(__file__).parent;ROOT=OUT.parents[1];sys.path.insert(0,str(ROOT/'social-publisher'))
from common import atomic_json,digest,utc,Hold,read_json
from settings import Settings
from google_fast import GoogleFastChrome
from google_business import GoogleBusinessProfile,saved_details,saved_text_action,norm
from journal import Store
from workflow import Workflow,render
def hold_unpublished(store,settings,chrome,job_id):
 state=ROOT/'social-publisher/state'
 job=store.get(job_id);c=Workflow(settings,chrome,state).context(job);assert store.has_intent(job_id) and job['state']!='PUBLISHED'
 recipe=settings.workflow(settings.profile(c['profile_id']));kind='video' if c.get('media_type')=='video/mp4' else 'photo';guard=render(recipe['google_'+kind],c);reader='verification';chrome.navigate(reader,c['inventory_url'],job_id,recovery=True)
 row=[{'selector':'div.J7elmb','contains':c['caption']}]
 adapter=GoogleBusinessProfile(Workflow(settings,chrome,chrome.directory));resolution={}
 try:adapter.find_inventory_record(reader,row)
 except Hold as error:
  if error.code!='AMBIGUOUS_CONTROL':raise
  post_id,resolution=adapter.resolve_caption_record(reader,c,recipe)
  row=[{'selector':'div.J7elmb:has(div[data-post-name="accounts/-/locations/'+c['location_id']+'/localPosts/'+post_id+'"])'}]
  adapter.find_inventory_record(reader,row)
 snap=chrome.call(reader,{'op':'snapshot','scope':row,'includeHTML':True});caption=chrome.call(reader,{'op':'snapshot','scope':[{'selector':'div.XNfYrb','text':c['caption'],'within':row[0]}]});status=chrome.call(reader,{'op':'snapshot','scope':[{'selector':'div.WeJbRc','within':row[0]}]})
 assert norm(caption['text'])==norm(c['caption'])
 ids=set(re.findall(r'data-post-name="accounts/-/locations/(\d+)/localPosts/(\d+)"',snap['html']));assert len(ids)==1
 location,post_id=next(iter(ids));assert location==c['location_id'];native=c['inventory_url']+'/'+post_id+'/edit'
 native_published=norm(status['text']).startswith('Published')
 if native_published and kind!='video':
  from engine import Engine
  Engine(store,Workflow(settings,chrome,chrome.directory),settings.policy).reconcile(job_id,native_url=native)
  return None
 assert native_published or norm(status['text']) in {'Pending','Rejected','Not approved','Processing'}
 folder=OUT/'platform-unpublished-evidence';folder.mkdir(exist_ok=True)
 chrome.navigate(reader,native,job_id,recovery=True);processing=None
 try:
  media=chrome.confirm_upload_preview(reader,guard,c);saved=chrome.call(reader,{'op':'snapshot','fullDocument':True,'includeHTML':True});checked=saved_details(saved,media,c)
  if native_published:
   from engine import Engine
   Engine(store,Workflow(settings,chrome,chrome.directory),settings.policy).reconcile(job_id,native_url=native)
   return None
 except Hold as error:
  if kind!='video' or not (native_published or norm(status['text'])=='Pending') or error.code!='UPLOAD_PREVIEW_NOT_CONFIRMED':raise
  # Google can save a Pending video post while its editor has no decoded
  # media yet. This is a processing hold, never a published-media receipt.
  saved=chrome.call(reader,{'op':'snapshot','fullDocument':True,'includeHTML':True});checked=saved_text_action(saved,c)
  assert not saved['videos'] and not any(x['name'] in {'Delete photo','Delete video'} for x in saved['controls'])
  photo_locator=read_json(ROOT/'social-publisher/workflows/google_business_profile.json')['google_photo']['locator']
  assert not chrome.call(reader,{'op':'exists','locator':photo_locator})['exists']
  from urllib.parse import urlparse
  import urllib.request
  posters=re.findall(r'background-image: url\((https://[^)]+)\)',snap['html']);assert len(posters)==1 and (urlparse(posters[0]).hostname or '').endswith('.googleusercontent.com')
  with urllib.request.urlopen(urllib.request.Request(posters[0],headers={'User-Agent':'Mozilla/5.0'}),timeout=30) as response:raw=response.read(1_000_001)
  # This exact native grey processing spinner was visually inspected. A
  # different poster requires inspection and cannot satisfy this fallback.
  assert digest(raw)=='870b42cdfb69749d117b5cdc133c822d7108cc650605e98982f51eb0d66241df'
  poster=folder/(job_id+'-native-processing-placeholder.jpg');poster.write_bytes(raw)
  prepared_path=chrome.directory/'evidence'/(job_id+'-google-video.json');prepared=read_json(prepared_path)
  assert prepared['job_id']==job_id and prepared['profile_hash']==c['profile_hash'] and prepared['media_sha256']==c['media_sha256'] and prepared['video']['input_sha256']==c['media_sha256']
  processing={'native_processing_placeholder_url':posters[0],'native_processing_placeholder_path':str(poster.resolve()),'native_processing_placeholder_sha256':digest(raw),'prepared_video_path':str(prepared_path.resolve()),'prepared_video_sha256':digest(prepared_path.read_bytes()),'loaded_saved_video_verified':False,'caption_action_and_native_pending_record_verified':True}
 proof={'utc':utc(),'job_id':job_id,'native_url':native,'location_id':location,'post_id':post_id,'native_status':norm(status['text']),'published':False,'record':{'snapshot':snap,'caption':caption,'status':status},'saved_editor':saved,'media_kind':kind,'loaded_media':checked.get(kind),'purchase_links':checked['purchase_links'],'media_sha256':c['media_sha256'],'original_publish_intent_retained':True,**resolution,**({'video_processing':processing} if processing else {})}
 path=folder/(job_id+'-'+digest(proof)[:12]+'.json');atomic_json(path,proof)
 chrome.navigate(reader,c['inventory_url'],job_id,recovery=True)
 writer=c['profile_id'];b=chrome.bindings[writer];assert b['job_id']==job_id
 if b['url']==c['compose_url']:
  chrome.confirm_upload_preview(writer,guard,c)
  if processing:
   uploaded=chrome.call(writer,{'op':'upload_status','job':job_id,'mediaSha256':c['media_sha256']});assert uploaded.get('committed') and uploaded.get('sha256')==c['media_sha256']
  chrome.call(writer,{'op':'assert','checks':[{'locator':[{'selector':'textarea[maxlength="1500"]'}],'text':c['caption']},{'locator':[{'selector':'input[type=url]'}],'text':c['purchase_url']}]})
  atomic_json(folder/(job_id+'-local-form-before-release.json'),chrome.call(writer,{'op':'snapshot','fullDocument':True}))
  chrome.call(writer,{'op':'click','locator':[{'selector':'main div[data-file-id] button','name':'Delete '+kind}]})
  for selector in ['textarea[maxlength="1500"]','input[type=url]']:chrome.call(writer,{'op':'set_text','locator':[{'selector':selector}],'value':''})
  clean=chrome.call(writer,{'op':'clean_state',**recipe['clean_state']});assert clean['clean'];atomic_json(folder/(job_id+'-local-form-after-release.json'),clean)
 else:assert b['url']==c['inventory_url']
 chrome.checkpoint(writer,0,dirty=False);chrome.navigate(writer,c['inventory_url'],job_id,recovery=True)
 registry=OUT/'platform-publication-holds.json';data=json.loads(registry.read_text()) if registry.exists() else {'holds':[]}
 reason='Native '+proof['native_status']+'; Google video processing placeholder verified, saved caption and action inspected; loaded saved video is not yet available; not fully verified; reconcile only' if processing else 'Native '+proof['native_status']+'; exact saved description, original '+kind+' and action inspected; reconcile only'
 hold={'job_id':job_id,'post_key':job['post_key'],'native_post_id':post_id,'native_url':native,'native_status':proof['native_status'],'reason':reason,'proof_path':str(path.resolve()),'proof_sha256':digest(path.read_bytes())}
 data['holds']=[h for h in data['holds'] if h['job_id']!=job_id]+[hold];data['utc']=utc()
 store.event('GOOGLE_UNPUBLISHED_RECORD_HELD',job_id=job_id,evidence_path=str(path.resolve()),evidence_sha256=digest(path.read_bytes()),native_url=native,native_status=proof['native_status'])
 atomic_json(registry,data);store.export();store.backup();print(json.dumps(hold),flush=True)
 return hold

if __name__=='__main__':
 settings=Settings();state=ROOT/'social-publisher/state';chrome=GoogleFastChrome(settings,state)
 with Store(state) as store:hold_unpublished(store,settings,chrome,sys.argv[1])
