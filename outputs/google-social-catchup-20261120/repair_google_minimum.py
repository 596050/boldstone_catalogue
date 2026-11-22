"""Replace only unsubmitted media preparations rejected by Google's pixel limit."""
import copy,json,subprocess,sys
from pathlib import Path
from PIL import Image
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).parent
sys.path.insert(0,str(ROOT/'social-publisher'))
from common import Hold,atomic_json,digest,read_json,utc
from google_fast import GoogleFastChrome
from journal import Store
from settings import Settings

settings=Settings();changes=[];batches=[]
for part in ['history-2026-part1','history-2026-part2']:
 folder=OUT/part;original=read_json(folder/'manifest.json');delivery=copy.deepcopy(original)
 old_jobs={j['post_key']:j for j in settings.jobs(folder/'manifest.json')}
 prepared=read_json(folder/'prepared-posts.json');prepared_map={r['google_post_key']:r for r in prepared}
 for post in delivery['posts']:
  image=Path(post['media_path']);w,h=Image.open(image).size
  if w>=400 and h>=300:continue
  old_key=post['post_key'];old=old_jobs[old_key];new_key=old_key+'-google-size-v2'
  copies=OUT/'google-delivery-media';copies.mkdir(exist_ok=True);target=copies/(old_key+'.png')
  if not target.exists():
   option='--resampleWidth' if 400/w>=300/h else '--resampleHeight';size='400' if option=='--resampleWidth' else '300'
   subprocess.run(['/usr/bin/sips','-s','format','png',option,size,str(image),'--out',str(target)],check=True,capture_output=True)
  nw,nh=Image.open(target).size
  assert nw>=400 and nh>=300 and abs(nw/nh-w/h)<.01 and target.stat().st_size<=5_000_000
  post.update(post_key=new_key,media_path=str(target.resolve()),sha256=digest(target.read_bytes()))
  row=prepared_map[old_key];row.update(original_frozen_post_key=old_key,google_post_key=new_key,delivery_media_path=str(target.resolve()),delivery_sha256=post['sha256'],delivery_dimensions=[nw,nh])
  changes.append({'folder':folder,'old_job':old,'new_post_key':new_key,'source_media_path':str(image),'source_sha256':old['payload']['media_sha256'],
                  'delivery_media_path':str(target.resolve()),'delivery_sha256':post['sha256'],'original_dimensions':[w,h],'delivery_dimensions':[nw,nh]})
 amended=folder/'delivery-manifest.json'
 if amended.exists():assert read_json(amended)==delivery
 else:atomic_json(amended,delivery)
 if not (folder/'delivery-prepared-posts.json').exists():atomic_json(folder/'delivery-prepared-posts.json',prepared)
 batches.append((folder,settings.jobs(amended)))
new_jobs={j['post_key']:j for folder,jobs in batches for j in jobs}
with Store(ROOT/'social-publisher/state') as store:
 for item in changes:
  old=item['old_job'];new=new_jobs[item['new_post_key']];assert not store.has_intent(old['id'])
  proof=item['folder']/('minimum-size-replacement-'+old['id']+'.json')
  if not proof.exists():atomic_json(proof,{'utc':utc(),'original_job_id':old['id'],'replacement_job_id':new['id'],
    'original_manifest_sha256':digest((item['folder']/'manifest.json').read_bytes()),'delivery_manifest_sha256':digest((item['folder']/'delivery-manifest.json').read_bytes()),
    'source_media_path':item['source_media_path'],'source_sha256':item['source_sha256'],'delivery_media_path':item['delivery_media_path'],'delivery_sha256':item['delivery_sha256'],
    'original_dimensions':item['original_dimensions'],'delivery_dimensions':item['delivery_dimensions'],
    'method':'proportional PNG size copy using sips; source retained, no crop','native_requirement':'at least 400 x 300 pixels',
    'native_rejection_evidence':str(OUT/'history-embedded-shells-upload-held.json'),'native_rejection_sha256':digest((OUT/'history-embedded-shells-upload-held.json').read_bytes())})
  store.enqueue([old],state='BLOCKED')
  if not any(e['kind']=='PREPARATION_SUPERSEDED' and e['job']['id']==old['id'] for e in store.ledger):store.supersede_preparation(old['id'],new['id'],proof)
 for folder,jobs in batches:store.enqueue(jobs)
 store.export();store.backup()
 held='66d52ec1cc05ccdbcdc194859940dcdf';job=store.get(held);p=job['payload'];assert not store.has_intent(held)
 chrome=GoogleFastChrome(settings,ROOT/'social-publisher/state');name=p['profile_id'];binding=chrome.bindings[name]
 if binding.get('job_id')==held and binding['url']==settings.profile(name)['compose_url']:
  snap=chrome.call(name,{'op':'snapshot','fullDocument':True,'includeHTML':True})
  assert 'Images must be at least 400 × 300 pixels in size.' in snap['text']
  fields=[e for e in snap['editors'] if e['tag']=='TEXTAREA'];assert len(fields)==1 and fields[0]['value']==p['caption']
  assert [e['value'] for e in snap['inputs'] if 'type="url"' in e['html']]==[p['purchase_url']]
  assert not chrome.call(name,{'op':'exists','locator':[{'selector':'main div[data-file-id] svg[role=img] image'}]})['exists']
  atomic_json(OUT/'minimum-size-rejected-draft-before-release.json',{'utc':utc(),'job_id':held,'publish_intents':0,'snapshot':snap})
  chrome.call(name,{'op':'click','locator':[{'selector':'button','name':'OK'}]})
  chrome.call(name,{'op':'set_text','locator':[{'selector':'textarea[maxlength="1500"]'}],'value':''})
  chrome.call(name,{'op':'set_text','locator':[{'selector':'input[type=url]'}],'value':''})
  chrome.call(name,{'op':'assert','checks':[{'locator':[{'selector':'textarea[maxlength="1500"]'}],'text':''}]})
  clean=chrome.call(name,{'op':'snapshot','fullDocument':True})
  atomic_json(OUT/'minimum-size-rejected-draft-after-release.json',{'utc':utc(),'job_id':held,'snapshot':clean,'reason':'Exact rejected upload, no preview, no Publish intent; original source and replacement preparation retained'})
  chrome.checkpoint(name,0,dirty=False);chrome.navigate(name,settings.profile(name)['inventory_url'],held,recovery=True)
print(json.dumps({'proportional_size_copies':len(changes),'unsubmitted_preparations_durably_superseded':len(changes),'original_manifests_preserved':True,'publish_clicks_in_repair':0}))
