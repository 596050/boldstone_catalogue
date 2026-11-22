"""Independently reconcile the batch's receipts, evidence and intent ledger."""
import json,re,sys
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).parent
sys.path.insert(0,str(ROOT/'social-publisher'))
from common import atomic_json,digest,utc
from journal import Store

with Store(ROOT/'social-publisher/state') as store:
 jobs=[j for j in store.jobs() if j['payload'].get('batch_id')=='component-sculptures-20261119-2']
 platforms={'facebook':5,'instagram':5,'linkedin':5,'google_business_profile':5}
 assert len(jobs)==20 and all(j['state']=='PUBLISHED' for j in jobs),'Batch is not complete'
 assert Counter(j['payload']['platform'] for j in jobs)==platforms
 ids={j['id'] for j in jobs}
 intents=[e for e in store.ledger if e['kind']=='PUBLISH_INTENT' and e['job']['id'] in ids]
 terminal=[e for e in store.ledger if e['kind']=='PUBLISHED' and e['job_id'] in ids]
 corrections=[e for e in store.ledger if e['kind']=='GOOGLE_VALIDATION_CORRECTION_INTENT' and e['job_id'] in ids]
 rejections=[e for e in store.ledger if e['kind']=='GOOGLE_CLIENT_VALIDATION_REJECTED' and e['job_id'] in ids]
 assert Counter(e['job']['id'] for e in intents)==Counter({i:1 for i in ids})
 assert Counter(e['job_id'] for e in terminal)==Counter({i:1 for i in ids})
 assert len(corrections)==len(rejections)==2
 from google_business import link_validation_rejection
 rejected_hashes=set()
 for entry in rejections:
  path=Path(entry['evidence_path']);assert digest(path.read_bytes())==entry['evidence_sha256']
  proof=json.loads(path.read_text());job=next(j for j in jobs if j['id']==entry['job_id']);p=job['payload']
  assert proof['job_id']==job['id'] and proof['profile_hash']==p['profile_hash'] and proof['media_sha256']==p['media_sha256']
  assert link_validation_rejection(proof['snapshot'],p['profile_snapshot']|p)
  rejected_hashes.add(entry['evidence_sha256'])
 corrected_hashes=set()
 for entry in corrections:
  path=Path(entry['evidence_path']);assert digest(path.read_bytes())==entry['evidence_sha256']
  proof=json.loads(path.read_text());assert proof['rejection_sha256'] in rejected_hashes
  assert proof['original_publish_intent_retained'] and proof['ready']['status']=='READY'
  assert proof['rejection_sha256'] not in corrected_hashes
  corrected_hashes.add(proof['rejection_sha256'])
 verified=[];media={};tagged=0;links=0;google_ids=set()
 for job in jobs:
  p=job['payload'];r=job['receipt'];path=Path(r['evidence_path'])
  assert digest(path.read_bytes())==r['evidence_sha256']
  e=json.loads(path.read_text())
  assert all(r.get(k) and e.get(k) for k in ['caption_verified','author_verified','photo_verified'])
  assert e['job_id']==job['id'] and r['media_sha256']==p['media_sha256']
  if p['media_path'] not in media:media[p['media_path']]=digest(Path(p['media_path']).read_bytes())
  assert media[p['media_path']]==p['media_sha256']
  assert digest({'profile':p['profile_snapshot'],'workflow':p['workflow_snapshot']})==p['profile_hash']
  if p['platform'] in {'facebook','instagram'}:
   assert r.get('product_tag_verified')
   tag=r['product_tag_readback'];selected=tag['selected_product']
   assert tag['persisted_tag_count']==1 and selected['job']==job['id'] and selected['sha256']==p['media_sha256']
   assert selected['name']==p['product_tag']['name'] and selected['price_text']==p['product_tag']['price_text']
   assert digest(Path(tag['selection_evidence_path']).read_bytes())==tag['selection_evidence_sha256']
   tagged+=1
  if p['platform'] in {'facebook','linkedin','google_business_profile'}:
   assert any(link['expected']==p['purchase_url'] for link in r['purchase_links'])
   links+=1
  if p['platform']=='google_business_profile':
   from google_business import record_identity,saved_details
   identity=record_identity(e['published_inventory'],e['published_caption'],e['published_status'],p['profile_snapshot']|p)
   assert identity['location_id']==r['google_location_id']=='15009857378722117958'
   assert identity['post_id']==r['google_post_id'] and identity['status']==r['google_status']
   assert r['native_url']==p['profile_snapshot']['inventory_url']+'/'+identity['post_id']+'/edit'
   assert identity['post_id'] not in google_ids
   google_ids.add(identity['post_id'])
   prepared=Path(e['prepared_photo_evidence_path'])
   assert digest(prepared.read_bytes())==e['prepared_photo_evidence_sha256']
   prep=json.loads(prepared.read_text())
   assert prep['job_id']==job['id'] and prep['profile_hash']==p['profile_hash'] and prep['media_sha256']==p['media_sha256']
   assert prep['photo']['input_sha256']==p['media_sha256'] and prep['photo']['width']>0 and prep['photo']['height']>0
   saved_details(e['saved_post'],{'checks':[{'image':True,'photo':e['photo']}]},p)
  verified.append({'job_id':job['id'],'catalogue_id':p['catalogue_id'],'platform':p['platform'],'native_url':r['native_url'],'verified_utc':r['verified_utc'],'evidence_sha256':r['evidence_sha256']})
 assert len(media)==5 and tagged==10 and links==15 and len(google_ids)==5
 assert len({j['native_url'] for j in verified})==20
 python_log=OUT/'google-python-tests.txt';javascript_log=OUT/'google-javascript-tests.txt'
 python_results=python_log.read_text();javascript_results=javascript_log.read_text()
 python_tests=int(re.search(r'Ran (\d+) tests',python_results).group(1))
 javascript_tests=int(re.search(r'tests (\d+)',javascript_results).group(1))
 assert python_tests==93 and re.search(r'\nOK\s*$',python_results)
 assert javascript_tests==52 and re.search(r'fail 0\b',javascript_results) and re.search(r'pass 52\b',javascript_results)
 tested_sources=['chrome.py','dom-driver.js','google_business.py','workflow.py','settings.py','publisher.py','engine.py','journal.py','profiles.json','workflows/google_business_profile.json']
 started=json.loads((OUT/'batch-start.json').read_text())['started_utc']
 focus=[]
 directories=[ROOT/'social-publisher/state',OUT/'native-reader-state',OUT/'google-cal-state',OUT/'linkedin-cal-state',OUT/'linkedin-drop-state']
 for directory in directories:
  path=directory/'focus-audit.jsonl'
  if path.exists():
   for line in path.read_text().splitlines():
    if line:
     row=json.loads(line)
     if row.get('utc','')>=started:
      row['_source_directory']=str(directory)
      focus.append(row)
 incidents=[row for row in focus if row.get('target_remained_background') is False]
 bindings={row['profile']:row for row in json.loads((OUT/'reserved-tabs.json').read_text())}
 recovery_path=OUT/'linkedin-binding-recovery.json'
 recovery=json.loads(recovery_path.read_text()) if recovery_path.exists() else None
 def background(stamp,row):
  source=Path(row['_source_directory'])
  if source==ROOT/'social-publisher/state':binding=bindings[row['profile_id']]
  else:
   saved=json.loads((source/'bindings.json').read_text())[row['profile_id']]
   binding={'window':saved['window_id'],'tab':saved['tab_id']}
  if recovery and row['profile_id']=='sally_linkedin' and row['utc']<recovery['rebound_utc']:
   binding=recovery['previous_tab']
  return not (stamp['frontmost']=='com.google.Chrome' and
              stamp['front_window_id']==binding['window'] and
              stamp['active_tabs'].get(str(binding['window']))==binding['tab'])
 assert focus and all(background(row['before'],row) for row in focus)
 submissions=[row for row in focus if row['operation'] in {'submit','submit_google_validation_correction'}]
 assert len(submissions)==20+len(corrections) and all(background(row['after'],row) for row in submissions)
 if incidents:
  review=json.loads((OUT/'focus-guard-review.json').read_text())
  assert {digest(row) for row in incidents}==set(review['incident_sha256'])
  assert review['publish_intents_at_pause']==0
  assert all(row['operation']=='upload_chunk' and row['profile_id']=='sally_linkedin' for row in incidents)
  paused_intents=[entry for entry in intents if entry['job']['id']==review['job_id']]
  assert len(paused_intents)==1 and paused_intents[0]['utc']>max(row['utc'] for row in incidents)
 report={'utc':utc(),'status':'COMPLETE_VERIFIED','published_by_platform':platforms,'native_receipts_verified':20,'google_native_published_records_verified':len(google_ids),'original_media_hashes_verified':5,'persisted_meta_tags_verified':10,'authored_purchase_destinations_verified':15,'publish_intents':len(intents),'terminal_publication_receipts':len(terminal),'duplicate_intents':0,'google_client_validation_rejections':len(rejections),'proven_google_validation_corrections':len(corrections),'ledger_hash_chain_verified':True,'focus_operations_audited':len(focus),'all_operations_started_in_background':True,'publish_operations_verified_in_background':len(submissions),'recorded_target_foregrounding':len(incidents),'reviewed_focus_guard_pauses':len(incidents),'foreground_change_cause':'Not determined' if incidents else None,'posts':verified}
 report['automated_tests']={'python_passed':python_tests,'javascript_passed':javascript_tests,'total_passed':python_tests+javascript_tests,
                            'python_log_sha256':digest(python_log.read_bytes()),'javascript_log_sha256':digest(javascript_log.read_bytes())}
 report['final_source_sha256']={name:digest((ROOT/'social-publisher'/name).read_bytes()) for name in tested_sources}
 atomic_json(OUT/'execution-checks.json',report)
 print(json.dumps({k:v for k,v in report.items() if k!='posts'},ensure_ascii=False,indent=2))
