"""Reconcile only this batch's receipts, media and background action records."""
from pathlib import Path
from collections import Counter
import json,hashlib,sqlite3,sys
OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[1];sys.path.insert(0,str(ROOT/'social-publisher'))
from settings import Settings
from common import atomic_json,read_json,utc,digest
settings=Settings();jobs=settings.jobs(OUT/'publish-manifest.json')
publication=read_json(OUT/'publication-results.json')['results'];byid={r['id']:r for r in publication}
assert len(byid)==10 and set(byid)=={j['id'] for j in jobs}
ledger=[json.loads(line) for line in (ROOT/'social-publisher/state/intent-ledger.jsonl').read_text().splitlines()]
intents=Counter(e['job']['id'] for e in ledger if e['kind']=='PUBLISH_INTENT')
verified=[];platform_holds=[]
with sqlite3.connect((ROOT/'social-publisher/state/outbox.sqlite3').as_uri()+'?mode=ro',uri=True) as db:
 for job in jobs:
  r=byid[job['id']];assert r['state'] in {'PUBLISHED','OUTCOME_UNKNOWN'};assert intents[job['id']]==1
  assert db.execute('select state from jobs where id=?',(job['id'],)).fetchone()[0]==r['state']
  if r['state']=='OUTCOME_UNKNOWN':
   assert r['profile_id']=='boldstone_google_business_profile'
   hold=r['native_pending_record'];proof_path=Path(hold['proof_path']);proof=read_json(proof_path)
   assert digest(proof_path.read_bytes())==hold['proof_sha256'] and proof['job_id']==job['id'] and proof['native_status']=='Pending' and proof['published'] is False
   assert proof['media_sha256']==job['payload']['media_sha256'] and proof['loaded_media'] and proof['purchase_links'][0]['expected']==job['payload']['purchase_url']
   platform_holds.append({'job_id':job['id'],'post_key':job['post_key'],'title':r['title'],'native_status':'Pending','native_url':hold['native_url'],'proof_path':str(proof_path)})
   continue
  receipt=r['receipt'];assert all(receipt[k] is True for k in ['author_verified','caption_verified','photo_verified'])
  assert receipt['media_sha256']==job['payload']['media_sha256']
  evidence=Path(receipt['evidence_path']);assert hashlib.sha256(evidence.read_bytes()).hexdigest()==receipt['evidence_sha256']
  assert any(link['expected']==job['payload']['purchase_url'] for link in receipt['purchase_links'])
  verified.append({'id':job['id'],'profile_id':r['profile_id'],'post_key':r['post_key'],'native_url':receipt['native_url'],'native_evidence_sha256':receipt['evidence_sha256']})
 draftdata=read_json(OUT/'native-draft-results.json');drafts=draftdata['drafts'];assert len(drafts)==10
 assert Counter(r['profile_id'] for r in drafts)=={'boldstone_facebook':5,'boldstone_threads':5}
 for draft in drafts:
  assert draft['state'].startswith('PREPARED_')
  assert draft['publish_clicks']==0 and draft['publish_intents_written_by_this_worker']==0
  assert db.execute('select id from jobs where id=?',(draft['id'],)).fetchone() is None
  assert intents[draft['id']]==0
  assert draft['upload']['committed'] and draft['upload']['sha256']==draft['media_sha256']
  if draft['profile_id']=='boldstone_facebook':
   assert draft['product_tag_verified'] and draft['product_tag']['selected_count']==1 and draft['product_tag']['persisted_editor_readback']
   checks=draft['ready']['checks'];assert any(c['text']=='Boldstone Sculpture and boldstonesculpture' for c in checks)
  snap=read_json(Path(draft['native_snapshot_path']));assert 'Draft' in snap['title']
  if draft['profile_id']=='boldstone_facebook':
   switches={c['name']:c['checked'] for c in snap['controls'] if c.get('type')=='checkbox'}
   assert switches['Share to Facebook story'] is True and switches['Set date and time'] is False
   assert switches.get('Boost',False) is False
 for post in read_json(OUT/'posts.json')['posts']:
  assert hashlib.sha256(Path(post['media_path']).read_bytes()).hexdigest()==post['media_sha256']

baseline=read_json(OUT/'focus-baseline.json')['utc'];audits=[]
for path in [ROOT/'social-publisher/state/focus-audit.jsonl',*OUT.rglob('focus-audit.jsonl')]:
 for line in path.read_text().splitlines():
  row=json.loads(line)
  if row['utc']>=baseline:audits.append((path,row))
def stamp(row):return {k:row.get(k) for k in ['frontmost','front_window_id','active_tabs']}
assert all(row.get('target_remained_background',True) for _,row in audits)
task_ids={v['tab_id'] for v in read_json(OUT/'browser-state/bindings.json').values()}|{r['tab_id'] for r in drafts}
changed=[]
for path,row in audits:
 if stamp(row['before'])!=stamp(row['after']):
  after=row['after'];active=after.get('active_tabs',{}).get(str(after.get('front_window_id')))
  assert active not in task_ids
  changed.append({'utc':row['utc'],'operation':row['operation'],'profile_id':row['profile_id'],'task_tab_selected':False})
tagging=read_json(OUT/'combined-destination-tagging-inspection.json');assert 'Product tags that you add will appear in the placements you have selected.' in tagging['text']
background={'utc':utc(),'native_mutation_audits':len(audits),'foreground_task_tabs_observed':0,'all_instrumented_targets_remained_background':True,'user_focus_changes_observed':changed,'screenshot_available':False,'screenshot_limitation':'The Chrome page attachment service requires a network policy; native DOM readback and saved receipts were used.','audit_files':sorted({str(path.resolve()) for path,_ in audits})}
atomic_json(OUT/'background-audit.json',background)
recommendations=read_json(OUT/'additional-platforms.json')['platforms'];assert len(recommendations)==5
result={'utc':utc(),'verified_publications':verified,'platform_holds':platform_holds,'published_by_profile':dict(Counter(r['profile_id'] for r in publication if r['state']=='PUBLISHED')),'submitted_targets':10,'new_publish_intents':10,'publish_intents_per_job':1,'draft_composers':10,'draft_platform_deliveries':15,'draft_publications':0,'draft_review_states':dict(Counter(r['state'] for r in drafts)),'shopping_tag_placement_statement_verified':True,'additional_platform_recommendations':5,'additional_platform_publications':0,'background':{'native_mutation_audits':len(audits),'foreground_task_tabs_observed':0},'validation':'PASSED_WITH_PLATFORM_REVIEW_PENDING' if platform_holds else 'PASSED'}
atomic_json(OUT/'final-audit.json',result)
print(json.dumps(result,ensure_ascii=False),flush=True)
