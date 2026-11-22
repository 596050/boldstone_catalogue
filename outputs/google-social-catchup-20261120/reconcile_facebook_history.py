"""Reconcile observed public Facebook history without claiming unavailable content."""
import collections,json,re,sqlite3,sys
from pathlib import Path
OUT=Path(__file__).parent;ROOT=OUT.parents[1];sys.path.insert(0,str(ROOT/'social-publisher'))
from common import atomic_json,digest,utc

def load(name):return json.loads((OUT/name).read_text())
def proof(row):
 for prefix in ['evidence','visual_review','poster','cover']:
  path=row.get(prefix+'_path');sha=row.get(prefix+'_sha256')
  if path and sha:assert digest(Path(path).read_bytes())==sha,(path,'evidence changed')
def reference(name):
 p=OUT/name;return {'path':str(p.resolve()),'sha256':digest(p.read_bytes())}

photos=load('facebook-photo-parent-reconciliation.json');photo_progress=load('facebook-native-photo-history-progress.json')
assert len(photos['rows'])==499 and photos['unresolved_photo_count']==0 and photos['all_album_parent_links_read']
assert photo_progress['status']=='COLLECTION_CYCLE_COMPLETE' and photo_progress['returned_photo_id']==photo_progress['first_photo_id']
for row in photos['rows']:proof(row)
reels=load('facebook-reel-reconciliation.json')['reels']+load('facebook-older-reel-review-decisions.json')['reels']
assert len(reels)==18 and len({r['reel_url'].rstrip('/') for r in reels})==18
for row in reels:
 proof(row)
 if row['decision']=='COVERED_BY_EXISTING_REEL_STILL_PLAN':
  assert row['reel_url'].rstrip('/').endswith('/572917628343641')
  row['google_post_keys']=['INSTAGRAM-ARCHIVE-CtKq5zGIKCQ-still']
  row['adaptation']='Explicit reel still and original Instagram video permalink; neither native player nor public embed exposed a downloadable original video'
  row['video_source_readback']=reference('facebook-572917628343641-native-video-settled.json')

days=load('facebook-older-date-records.json');ending=load('facebook-older-date-progress.json')
assert len(days)==31 and ending['status']=='EXPLICIT_NATIVE_NO_POSTS_BEFORE_CURSOR'
supplemental=[];unavailable=[]
reel_by_url={r['reel_url'].rstrip('/'):r for r in reels}
for day in days:
 proof(day)
 for url in day['unmatched_urls']:
  if url=='https://www.facebook.com/reel':continue # navigation tab, not a source post
  if url in reel_by_url:continue
  if url.endswith('/videos/493152895538695'):
   assert 'Experiments with rusted textures' in day['native_text']
   supplemental.append({'source_url':url,'day':day['day'],'decision':'COVERED_SCULPTURE_VIDEO','google_post_keys':['INSTAGRAM-ARCHIVE-VIDEO-CZnFSE4I0nw-part-'+str(i) for i in range(1,4)],'evidence_path':day['evidence_path'],'evidence_sha256':day['evidence_sha256']})
  elif "This content isn't available at the moment" in day['native_text']:
   unavailable.append({'source_url':url,'day':day['day'],'decision':'SOURCE_UNAVAILABLE','reason':'Native Facebook shared post explicitly reports unavailable content; no sculpture content can be identified or safely copied','evidence_path':day['evidence_path'],'evidence_sha256':day['evidence_sha256']})
  else:raise AssertionError(('Unreviewed native source',day['day'],url))
assert len(supplemental)==1 and len(unavailable)==2

db=sqlite3.connect('file:'+str(ROOT/'social-publisher/state/outbox.sqlite3')+'?mode=ro',uri=True)
states={key:state for key,state in db.execute("SELECT post_key,state FROM jobs WHERE channel_key='google_business_profile:15009857378722117958'")};db.close()
mapped=[r for r in photos['rows'] if not r['excluded']]+[r for r in reels if r.get('google_post_keys')]+supplemental
keys=sorted({k for r in mapped for k in r['google_post_keys']})
waiting=[{'post_key':k,'state':states.get(k,'PREPARED')} for k in keys if states.get(k)!='PUBLISHED']
result={'utc':utc(),'status':'AVAILABLE_SOURCE_HISTORY_RECONCILED','native_photos_reviewed':499,'sculpture_photos_mapped':346,'non_sculpture_photos_excluded':153,'native_reels_reviewed':18,'sculpture_reels_mapped':sum(bool(r.get('google_post_keys')) for r in reels),'non_sculpture_reels_excluded':sum(r['decision']=='EXCLUDE_NON_SCULPTURE' for r in reels),'additional_classic_video_posts_mapped':1,'older_native_publication_days_read':31,'older_boundary_status':ending['status'],'unavailable_shared_posts':unavailable,'unavailable_source_count':len(unavailable),'reels':reels,'supplemental_video_sources':supplemental,'google_post_keys':keys,'google_counterparts_verified':len(keys)-len(waiting),'google_counterparts_waiting':waiting,'all_identified_counterparts_published':not waiting,'source_inventory_limits':['The first 10-reel grid was supplemented by native date filters; a stalled background grid alone was not treated as complete.','The date cursor reads publication days; the independently completed 499-photo archive and 2026 native export supply same-day photo posts. Unavailable shared posts cannot be classified.'],'references':[reference(n) for n in ['history-audit.json','facebook-photo-parent-reconciliation.json','facebook-native-photo-history-progress.json','facebook-reel-reconciliation.json','facebook-older-reel-review-decisions.json','facebook-older-date-records.json','facebook-older-date-progress.json']]}
atomic_json(OUT/'facebook-all-history-reconciliation.json',result)
print(json.dumps({k:v for k,v in result.items() if k not in ['reels','supplemental_video_sources','references','google_post_keys','google_counterparts_waiting','unavailable_shared_posts']},ensure_ascii=False))
