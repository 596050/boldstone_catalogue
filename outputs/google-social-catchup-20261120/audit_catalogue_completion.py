"""Independently check every catalogue receipt, source hash and durable intent."""
import collections,json,sqlite3,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).parent
sys.path.insert(0,str(ROOT/'social-publisher'))
from common import Hold,atomic_json,digest,read_json,utc
from google_business import record_identity,saved_details
from journal import Store

coverage=read_json(OUT/'coverage-inventory.json')['sculptures'];db=sqlite3.connect('file:'+str(ROOT/'social-publisher/state/outbox.sqlite3')+'?mode=ro',uri=True)
jobs={json.loads(p)['catalogue_id']:{'id':i,'payload':json.loads(p),'state':s,'receipt':json.loads(r)} for i,p,s,r in db.execute("SELECT id,payload,state,receipt FROM jobs WHERE channel_key='google_business_profile:15009857378722117958' AND state='PUBLISHED'")};db.close()
reader=Store.__new__(Store);reader.ledger_path=ROOT/'social-publisher/state/intent-ledger.jsonl'
for _ in range(10):
 try:events=reader.read_ledger();break
 except Hold as error:
  if error.code!='LEDGER_TORN_WRITE':raise
  time.sleep(.1)
else:raise RuntimeError('Ledger was being written; audit again when the writer is idle')
intents=collections.Counter(e['job']['id'] for e in events if e['kind']=='PUBLISH_INTENT')
published=collections.Counter(e['job_id'] for e in events if e['kind']=='PUBLISHED')
post_ids=set();checks=[]
for row in coverage:
 job=jobs[row['catalogue_id']];p=job['payload'];receipt=job['receipt'];path=Path(receipt['evidence_path'])
 assert digest(path.read_bytes())==receipt['evidence_sha256']
 proof=read_json(path);context={**p['profile_snapshot'],**p}
 native=record_identity(proof['published_inventory'],proof['published_caption'],proof['published_status'],context)
 detail=saved_details(proof['saved_post'],{'checks':[{'image':True,'photo':proof['photo']}]},context)
 assert native['post_id']==receipt['google_post_id'] and native['location_id']==receipt['google_location_id']
 assert native['post_id'] not in post_ids;post_ids.add(native['post_id'])
 assert digest(Path(p['media_path']).read_bytes())==p['media_sha256']==receipt['media_sha256']
 assert intents[job['id']]==1 and published[job['id']]==1
 assert detail['purchase_links'][0]['native_link']==p['purchase_url']
 checks.append({'catalogue_id':row['catalogue_id'],'title':row['title'],'job_id':job['id'],'google_post_id':native['post_id'],
                'native_published_status':native['status'],'description_photo_and_buy_destination_verified':True,'publish_intents':intents[job['id']],
                'published_ledger_records':published[job['id']],'evidence_path':str(path),'evidence_sha256':receipt['evidence_sha256']})
prepared=read_json(OUT/'prepared-posts.json')
for row in prepared:
 # Source/delivery fields are frozen in the original preparation record.
 for path_key,sha_key in [('original_media_path','original_sha256'),('media_path','sha256')]:
  assert digest(Path(row[path_key]).read_bytes())==row[sha_key]
assert len(prepared)==59
assert len(checks)==64 and len(post_ids)==64
result={'utc':utc(),'scope':'64 catalogue sculptures confirmed published to Meta before this request','status':'ALL_64_NATIVE_GOOGLE_RECORDS_VERIFIED',
        'new_google_posts':59,'already_google_before_request':5,'unique_google_post_ids':len(post_ids),'durable_intents_each':1,'repeated_publish_intents':0,
        'original_and_delivery_media_hashes_checked':True,'broader_sculpture_history_status':'IN_PROGRESS','checks':checks}
atomic_json(OUT/'catalogue-independent-audit.json',result);print(json.dumps({k:v for k,v in result.items() if k!='checks'}))
