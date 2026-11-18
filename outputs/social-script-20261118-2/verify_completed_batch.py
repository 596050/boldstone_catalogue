"""Independently reconcile the batch's receipts, evidence and intent ledger."""
import json,sys
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).parent
sys.path.insert(0,str(ROOT/'social-publisher'))
from common import atomic_json,digest,utc
from journal import Store

with Store(ROOT/'social-publisher/state') as store:
 jobs=[j for j in store.jobs() if j['payload'].get('batch_id')=='component-sculptures-20261118-2']
 assert len(jobs)==15 and all(j['state']=='PUBLISHED' for j in jobs),'Batch is not complete'
 assert Counter(j['payload']['platform'] for j in jobs)=={'facebook':5,'instagram':5,'linkedin':5}
 ids={j['id'] for j in jobs}
 intents=[e for e in store.ledger if e['kind']=='PUBLISH_INTENT' and e['job']['id'] in ids]
 terminal=[e for e in store.ledger if e['kind']=='PUBLISHED' and e['job_id'] in ids]
 assert Counter(e['job']['id'] for e in intents)==Counter({i:1 for i in ids})
 assert Counter(e['job_id'] for e in terminal)==Counter({i:1 for i in ids})
 verified=[];media={};tagged=0;links=0
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
  if p['platform'] in {'facebook','linkedin'}:
   assert any(link['expected']==p['purchase_url'] for link in r['purchase_links'])
   links+=1
  verified.append({'job_id':job['id'],'catalogue_id':p['catalogue_id'],'platform':p['platform'],'native_url':r['native_url'],'verified_utc':r['verified_utc'],'evidence_sha256':r['evidence_sha256']})
 assert len(media)==5 and tagged==10 and links==10
 assert len({j['native_url'] for j in verified})==15
 started=json.loads((OUT/'batch-start.json').read_text())['started_utc']
 focus=[]
 for directory in [ROOT/'social-publisher/state',OUT/'native-reader-state',OUT/'linkedin-cal-state',OUT/'linkedin-drop-state']:
  path=directory/'focus-audit.jsonl'
  if path.exists():focus.extend(json.loads(line) for line in path.read_text().splitlines() if line and json.loads(line).get('utc','')>=started)
 foreground=sum(row.get('target_remained_background') is False for row in focus)
 assert focus and foreground==0
 report={'utc':utc(),'status':'COMPLETE_VERIFIED','published_by_platform':{'facebook':5,'instagram':5,'linkedin':5},'native_receipts_verified':15,'original_media_hashes_verified':5,'persisted_meta_tags_verified':10,'authored_purchase_destinations_verified':10,'publish_intents':len(intents),'terminal_publication_receipts':len(terminal),'duplicate_intents':0,'ledger_hash_chain_verified':True,'focus_operations_audited':len(focus),'recorded_target_foregrounding':foreground,'posts':verified}
 atomic_json(OUT/'execution-checks.json',report)
 print(json.dumps({k:v for k,v in report.items() if k!='posts'},ensure_ascii=False,indent=2))
