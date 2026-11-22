"""Independently reconcile native Google receipts, source coverage and durable intents."""
import collections,json,re,sqlite3,sys,time
from pathlib import Path
OUT=Path(__file__).parent;ROOT=OUT.parents[1];sys.path.insert(0,str(ROOT/'social-publisher'))
from common import Hold,atomic_json,digest,utc
from google_business import record_identity,saved_details,rejected_revision_context,observed_revision_context,norm
from journal import Store
from google_public import public_evidence_checks

db=sqlite3.connect('file:'+str(ROOT/'social-publisher/state/outbox.sqlite3')+'?mode=ro',uri=True)
jobs={r[0]:{'id':r[0],'post_key':r[1],'state':r[2],'payload':json.loads(r[3]),'receipt':json.loads(r[4]) if r[4] else None} for r in db.execute("SELECT id,post_key,state,payload,receipt FROM jobs WHERE channel_key='google_business_profile:15009857378722117958'")};db.close()
bykey={r['post_key']:r for r in jobs.values()};bycatalogue={r['payload']['catalogue_id']:r for r in jobs.values() if r['state']=='PUBLISHED'}
ledger=Store.__new__(Store);ledger.ledger_path=ROOT/'social-publisher/state/intent-ledger.jsonl'
for _ in range(20):
 try:events=ledger.read_ledger();break
 except Hold as error:
  if error.code!='LEDGER_TORN_WRITE':raise
  time.sleep(.1)
else:raise RuntimeError('Ledger was being appended; retry the read-only audit')
intents=collections.Counter(e['job']['id'] for e in events if e['kind']=='PUBLISH_INTENT')
published=collections.Counter(e['job_id'] for e in events if e['kind']=='PUBLISHED')
prepared=[];pending_native_records=[]
for file in sorted(OUT.glob('history-*/prepared-posts.json')):
 if (file.parent/'delivery-prepared-posts.json').exists():file=file.parent/'delivery-prepared-posts.json'
 prepared.extend(json.loads(file.read_text()))
coverage=json.loads((OUT/'coverage-inventory.json').read_text())['sculptures'];checks=[];native_ids=set();waiting=[]
def check(job):
 p=job['payload'];receipt=job['receipt'];path=Path(receipt['evidence_path']);assert digest(path.read_bytes())==receipt['evidence_sha256']
 proof=json.loads(path.read_text());context={**p['profile_snapshot'],**p,'id':job['id']};context=observed_revision_context(rejected_revision_context(context,path.parent.parent),proof['published_caption']['text']);kind='video' if p.get('media_type')=='video/mp4' else 'photo'
 if receipt.get('caption_resolution_evidence_path'):
  resolution_path=Path(receipt['caption_resolution_evidence_path']);assert digest(resolution_path.read_bytes())==receipt['caption_resolution_evidence_sha256']
  resolution=json.loads(resolution_path.read_text());assert resolution['job_id']==job['id'] and resolution['selected_post_id']==receipt['google_post_id'] and resolution['expected_destination']==p['purchase_url']
  assert sum(r['expected_destination_matched'] for r in resolution['candidates'])==1
 if proof.get('verification_method')=='google_public_detail_and_decoded_native_media':
  identity,media=public_evidence_checks(proof,context,receipt['google_post_id'])
  detail={'purchase_links':identity['purchase_links'],kind:media}
 else:
  identity=record_identity(proof['published_inventory'],proof['published_caption'],proof['published_status'],context)
  detail=saved_details(proof['saved_post'],{'checks':[{kind:proof[kind],**({'image':True} if kind=='photo' else {})}]},context)
 assert identity['post_id']==receipt['google_post_id'] and identity['location_id']==receipt['google_location_id']
 assert receipt['native_url']==proof['url']
 assert identity['post_id'] not in native_ids;native_ids.add(identity['post_id'])
 assert detail['purchase_links'][0]['native_link']==p['purchase_url']
 assert digest(Path(p['media_path']).read_bytes())==p['media_sha256']==receipt['media_sha256']
 assert intents[job['id']]==1 and published[job['id']]==1
 checks.append({'job_id':job['id'],'post_key':job['post_key'],'google_post_id':identity['post_id'],'native_status':identity['status'],'media_kind':kind,'caption_media_and_action_checked':True,'evidence_path':str(path),'evidence_sha256':receipt['evidence_sha256'],'publish_intents':intents[job['id']]})
for row in coverage:check(bycatalogue[row['catalogue_id']])
source_mapping=collections.defaultdict(list)
for row in prepared:
 for path_key,sha_key in [('media_path','sha256'),('delivery_media_path','delivery_sha256'),('original_media_path','original_sha256')]:
  if row.get(path_key) and row.get(sha_key):assert digest(Path(row[path_key]).read_bytes())==row[sha_key]
 if row.get('evidence_path'):assert digest(Path(row['evidence_path']).read_bytes())==row['evidence_sha256']
 key=row['google_post_key'];job=bykey.get(key)
 if not job or job['state']!='PUBLISHED':
  waiting.append({'post_key':key,'state':job['state'] if job else 'PREPARED'})
  if job:
   directory=OUT/'google-video-state' if job['payload'].get('media_type')=='video/mp4' else ROOT/'social-publisher/state'
   path=directory/'evidence'/(job['id']+'-google-record.json')
   if path.exists():
    record=json.loads(path.read_text());ids=set(re.findall(r'data-post-name="accounts/-/locations/(\d+)/localPosts/(\d+)"',record['snapshot'].get('html','')))
    assert len(ids)==1 and next(iter(ids))[0]==job['payload']['profile_snapshot']['location_id'] and intents[job['id']]==1
    context=rejected_revision_context({**job['payload']['profile_snapshot'],**job['payload'],'id':job['id']},directory)
    assert record['job_id']==job['id'] and norm(record['caption']['text']) in {norm(context['caption']),norm(context.get('caption_before_revision',context['caption']))}
    location,post_id=next(iter(ids));pending_native_records.append({'job_id':job['id'],'post_key':key,'google_location_id':location,'google_post_id':post_id,'last_native_status':record['status']['text'],'evidence_path':str(path.resolve()),'evidence_sha256':digest(path.read_bytes())})
  continue
 check(job);source_mapping[row['source_key']].append(job['id'])
retired=[e for e in events if e['kind']=='PREPARATION_SUPERSEDED' and str(OUT) in e['evidence_path']]
for e in retired:assert intents[e['job']['id']]==0 and jobs[e['job']['id']]['state']=='BLOCKED'
assert len(retired)==4
groups=json.loads((OUT/'history-audit.json').read_text())['groups'];decisions={r['source_key']:r for r in json.loads((OUT/'history-review-decisions-2026.json').read_text())['decisions']}
sources=[]
for group in groups:
 decision=decisions[group['source_key']]['decision'];mapped=[]
 if decision=='COVERED_CATALOGUE':mapped=[bycatalogue[k]['id'] for k in group['catalogue_matches']]
 elif decision=='INCLUDE_SCULPTURE':mapped=source_mapping[group['source_key']]
 sources.append({'source_key':group['source_key'],'sources':group['sources'],'decision':decision,'google_job_ids':mapped,'covered':bool(mapped) if decision in {'COVERED_CATALOGUE','INCLUDE_SCULPTURE'} else None})
for row in json.loads((OUT/'history-review-decisions-legacy.json').read_text())['decisions']:
 decision=row['decision'];mapped=source_mapping[row['legacy_caption_key']] if decision=='COVERED_2026' else source_mapping[row['source_key']]
 sources.append({'source_key':row['source_key'],'sources':row['sources'],'decision':decision,'google_job_ids':mapped,'covered':bool(mapped) if decision in {'INCLUDE_SCULPTURE','COVERED_2026'} else None})
missing=[r['source_key'] for r in sources if r['covered'] is False]
facebook=json.loads((OUT/'facebook-all-history-reconciliation.json').read_text()) if (OUT/'facebook-all-history-reconciliation.json').exists() else {'status':'IN_PROGRESS'}
available_complete=not waiting and not missing and facebook['status']=='AVAILABLE_SOURCE_HISTORY_RECONCILED' and facebook.get('all_identified_counterparts_published',False)
complete=available_complete and facebook.get('unavailable_source_count',1)==0
result={'utc':utc(),'status':'ALL_AVAILABLE_IDENTIFIED_SCULPTURE_POSTS_VERIFIED' if available_complete else 'IN_PROGRESS','available_history_complete':available_complete,'full_history_complete':complete,'catalogue_sculptures':64,'older_google_posts_prepared':len(prepared),'native_google_posts_verified':len(checks),'native_google_post_ids_unique':len(native_ids),'new_google_posts_verified':len(checks)-5,'already_present_google_posts':5,'waiting':waiting,'source_groups_without_verified_google':missing,'retired_preparations':len(retired),'retired_publish_intents':0,'repeated_publish_intents':0,'all_saved_media_caption_action_and_status_checks_passed':True,'facebook_full_history':facebook,'checks':checks,'source_coverage':sources}
pending_ids={r['google_post_id'] for r in pending_native_records};assert len(pending_ids)==len(pending_native_records) and not pending_ids&native_ids
result.update(all_identified_available_posts_submitted=len(pending_native_records)==len(waiting),native_google_records_known=len(native_ids|pending_ids),pending_native_record_count=len(pending_native_records),native_video_posts_verified=sum(r['media_kind']=='video' for r in checks),pending_native_records=pending_native_records)
atomic_json(OUT/'full-history-audit.json',result)
print(json.dumps({k:v for k,v in result.items() if k not in {'checks','source_coverage','waiting','facebook_full_history','source_groups_without_verified_google','pending_native_records'}},ensure_ascii=False))
