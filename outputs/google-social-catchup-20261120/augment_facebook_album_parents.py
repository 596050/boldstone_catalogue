"""Read only public View Post links for the complete native photo collection."""
import json,re,sys,time
from pathlib import Path
OUT=Path(__file__).parent;ROOT=OUT.parents[1];sys.path[:0]=[str(ROOT/'social-publisher'),str(OUT)]
from source_chrome import SourceChrome
from google_fast import GoogleFastChrome
from settings import Settings
from common import atomic_json,digest,utc,Hold
c=SourceChrome(Settings(),OUT/'instagram-source-reader-state');name='verification'
rows=json.loads((OUT/'facebook-native-photo-history.json').read_text());known={r['photo_id'] for r in rows}
f=OUT/'facebook-native-photo-parent-records.json';records=json.loads(f.read_text()) if f.exists() else []
seen={r['photo_id'] for r in records};start=records[-1]['url'] if records else rows[0]['url'];c.navigate(name,start,recovery=True)
advanced=False
while True:
 snap=c.call(name,{'op':'source_facebook_photo'})
 if advanced and snap['photo_id'] in seen:break
 assert snap['photo_id'] in known
 if snap['photo_id'] not in seen:
  proof=OUT/'facebook-native-photo-evidence'/(snap['photo_id']+'-parent-'+digest(snap)[:12]+'.json');atomic_json(proof,snap)
  records.append({**snap,'evidence_path':str(proof.resolve()),'evidence_sha256':digest(proof.read_bytes())});seen.add(snap['photo_id']);atomic_json(f,records)
  print(json.dumps({'read':len(records),'photo_id':snap['photo_id'],'parent':snap['parent_post_url']}),flush=True)
 if not snap['next_available']:break
 previous=snap['photo_id'];oldsrc=snap['photo']['src'];GoogleFastChrome.call(c,name,{'op':'click','locator':[{'selector':'[role=button]','name':'Next photo'}]})
 deadline=time.monotonic()+20
 while True:
  b=c.bindings[name];_,tab=c.find(c.state_for(b),b['window_id'],b['tab_id'])
  if 'fbid='+previous not in tab['url'] and not tab['loading']:
   c.sync_expected_navigation(name,re.escape(tab['url']))
   try:
    updated=c.call(name,{'op':'source_facebook_photo'})
    if updated['photo']['src']!=oldsrc:break
   except Hold as e:
    if e.code not in {'PHOTO_NOT_LOADED','SOURCE_PHOTO_AUTHOR_REQUIRED','SOURCE_PHOTO_DATE_REQUIRED'}:raise
  if time.monotonic()>deadline:raise RuntimeError('Owned Next photo needs inspection')
  time.sleep(.2)
 advanced=True
assert seen==known,(len(seen),len(known))
atomic_json(OUT/'facebook-native-photo-parent-completion.json',{'utc':utc(),'status':'ALL_499_NATIVE_PHOTO_PARENTS_READ','photos':len(records),'parents':len({r['parent_post_url'] for r in records if r['parent_post_url']}),'records_sha256':digest(f.read_bytes())})
