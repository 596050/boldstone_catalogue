"""Read the owned public Facebook All Photos collection, including its earlier boundary."""
import json,re,sys,time,urllib.request
from pathlib import Path
from urllib.parse import urlparse,parse_qs
from PIL import Image
OUT=Path(__file__).parent;ROOT=OUT.parents[1];sys.path[:0]=[str(ROOT/'social-publisher'),str(OUT)]
from source_chrome import SourceChrome
from google_fast import GoogleFastChrome
from settings import Settings
from common import atomic_json,digest,utc,Hold
def canonical(url):
 p=urlparse(url)
 if p.path in ['/photo.php','/photo/']:return 'facebook-photo:'+parse_qs(p.query).get('fbid',[''])[0]
 return 'https://www.facebook.com'+p.path.rstrip('/')
known={canonical(r['Permalink']) for r in json.loads((OUT/'meta-facebook-2026-rows.json').read_text())}
c=SourceChrome(Settings(),OUT/'instagram-source-reader-state');name='verification'
file=OUT/'facebook-native-photo-history.json';rows=json.loads(file.read_text()) if file.exists() else [];seen={r['photo_id'] for r in rows}
evidence=OUT/'facebook-native-photo-evidence';evidence.mkdir(exist_ok=True)
receipts_file=OUT/'facebook-unmatched-photo-receipts.json';receipts=json.loads(receipts_file.read_text()) if receipts_file.exists() else []
first=rows[0]['photo_id'] if rows else None;last_image=None;advanced=False
while len(rows)<5000:
 snap=c.call(name,{'op':'source_facebook_photo'})
 if advanced and snap['photo_id'] in seen:
  atomic_json(OUT/'facebook-native-photo-history-progress.json',{'utc':utc(),'status':'COLLECTION_CYCLE_COMPLETE','photos_read':len(rows),'returned_photo_id':snap['photo_id'],'first_photo_id':first,'photos_unmatched_to_2026_export':sum(not r['in_2026_export'] for r in rows)});print('COLLECTION_CYCLE_COMPLETE',len(rows),flush=True);break
 if snap['photo_id'] not in seen:
  if snap['caption_collapsed']:
   GoogleFastChrome.call(c,name,{'op':'click','locator':[{'selector':'div.xyinxu5 [role=button]','name':'See more'}]});snap=c.call(name,{'op':'source_facebook_photo'})
  key=canonical(snap['date']['href']);record={**snap,'utc':utc(),'in_2026_export':key in known,'canonical_parent':key}
  proof=evidence/(snap['photo_id']+'-'+digest(snap)[:12]+'.json');atomic_json(proof,record);record.update(evidence_path=str(proof.resolve()),evidence_sha256=digest(proof.read_bytes()))
  if key not in known:
   photo=snap['photo'];assert (urlparse(photo['src']).hostname or '').endswith('.fbcdn.net')
   request=urllib.request.Request(photo['src'],headers={'User-Agent':'Mozilla/5.0','Referer':snap['url']})
   with urllib.request.urlopen(request,timeout=30) as response:raw=response.read(30_000_001)
   assert len(raw)<=30_000_000
   path=OUT/'history-media'/('facebook-native-'+snap['photo_id']+'.jpg');path.write_bytes(raw)
   with Image.open(path) as image:image.verify()
   w,h=Image.open(path).size
   receipt={'utc':utc(),'status':'SOURCE_PHOTO_VERIFIED','source_key':digest('facebook-history:'+key),'photo_id':snap['photo_id'],'caption':snap['caption'].removesuffix(' See less'),'sources':[{'platform':'facebook','post_id':snap['photo_id'],'url':snap['url'],'post_type':'Photos','publish_time':snap['date']['text']}],'media_path':str(path.resolve()),'sha256':digest(raw),'bytes':len(raw),'width':w,'height':h,'evidence_path':str(proof.resolve()),'evidence_sha256':record['evidence_sha256'],'native_parent':key}
   receipts.append(receipt);atomic_json(receipts_file,receipts)
  rows.append(record);seen.add(snap['photo_id']);first=first or snap['photo_id'];atomic_json(file,rows)
  atomic_json(OUT/'facebook-native-photo-history-progress.json',{'utc':utc(),'status':'IN_PROGRESS','photos_read':len(rows),'photos_unmatched_to_2026_export':sum(not r['in_2026_export'] for r in rows),'current_date':snap['date']['text']})
  print(json.dumps({'photos_read':len(rows),'photo_id':snap['photo_id'],'date':snap['date']['text'],'known_2026_parent':key in known,'caption':snap['caption'][:95]}),flush=True)
 if not snap['next_available']:
  atomic_json(OUT/'facebook-native-photo-history-progress.json',{'utc':utc(),'status':'COLLECTION_END_COMPLETE','photos_read':len(rows),'photos_unmatched_to_2026_export':sum(not r['in_2026_export'] for r in rows),'last_photo_id':snap['photo_id']});print('COLLECTION_END_COMPLETE',len(rows),flush=True);break
 previous=snap['photo_id'];last_image=snap['photo']['src']
 GoogleFastChrome.call(c,name,{'op':'click','locator':[{'selector':'[role=button]','name':'Next photo'}]})
 deadline=time.monotonic()+20
 while True:
  binding=c.bindings[name];state=c.state_for(binding);_,tab=c.find(state,binding['window_id'],binding['tab_id']);url=urlparse(tab['url']);q=parse_qs(url.query)
  assert url.hostname=='www.facebook.com' and url.path in ['/photo.php','/photo/'] and q.get('set')==['pb.100067801382847.-2207520000']
  if q.get('fbid',[previous])[0]!=previous and not tab['loading']:
   c.sync_expected_navigation(name,re.escape(tab['url']))
   try:
    updated=c.call(name,{'op':'source_facebook_photo'})
    if updated['photo']['src']!=last_image:break
   except Hold as error:
    if error.code not in {'PHOTO_NOT_LOADED','SOURCE_PHOTO_AUTHOR_REQUIRED','SOURCE_PHOTO_DATE_REQUIRED'}:raise
  if time.monotonic()>deadline:raise RuntimeError('Native Next photo did not complete; retain this exact checkpoint')
  time.sleep(.2)
 advanced=True
else:raise RuntimeError('Collection audit bound reached; not complete')
