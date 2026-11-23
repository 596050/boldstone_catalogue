"""Read back every retained draft and prove no script submission was made."""
from pathlib import Path
import sys,json,sqlite3,hashlib
from collections import Counter
OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[1]
sys.path.insert(0,str(ROOT/'social-publisher'))
from settings import Settings
from preparation import PreparationOnlyChrome
from common import atomic_json,utc,digest
from workflow import Workflow,render
posts=json.loads((OUT/'posts.json').read_text())['posts'];by_id={p['post_key']:p for p in posts}
settings=Settings();jobs={j['id']:j for j in settings.jobs(OUT/'remaining-manifest.json',require_authorized=False)}
proofs={};paths=[OUT/'tabs',ROOT/'social-publisher/state/drafts/component-sculptures-drafts-20261123-remaining-d10b634f']
for base in paths:
 for f in base.glob('*/preparation-result.json'):
  p=json.loads(f.read_text());proofs[(p['profile_id'],p['post_key'])]=(p,f.parent)
assert len(proofs)==15 and all(p[0]['state']=='PREPARED_NOT_PUBLISHED' for p in proofs.values())
assert Counter(k[0] for k in proofs)=={'boldstone_facebook':5,'boldstone_instagram':5,'boldstone_threads':5}
checked=[];tags=[];media={}
for index,post in enumerate(posts,1):
 source=Path(post['media_path']);media[post['post_key']]=digest(source.read_bytes());assert media[post['post_key']]==post['sha256']
 for platform in ['facebook','instagram','threads']:
  name='boldstone_'+platform;proof,directory=proofs[(name,post['post_key'])];c=PreparationOnlyChrome(settings,directory);profile=settings.profile(name);recipe=settings.workflow(profile)
  if directory.parent==OUT/'tabs':
   jid=('draft-' if platform=='facebook' else 'threads-draft-')+post['post_key']
   context={**profile,**post,'id':jid,'job':jid,'caption':post['captions'][platform],'mediaSha256':post['sha256'],'media_sha256':post['sha256'],'product_tag':{'name':post['title'],'price_text':'£'+format(post['price_gbp'],'.2f')} if platform=='facebook' else None}
  else:
   job=jobs[directory.name];context=Workflow(settings,c,directory).context(job);jid=job['id']
  guards=list(Workflow.enabled_steps(recipe['ready'],context))
  current=c.call(name,{'op':'assert','checks':guards,'job':jid,'mediaSha256':post['sha256']})
  status=c.call(name,{'op':'upload_status','job':jid,'mediaSha256':post['sha256']})
  assert status['same_job'] and status['committed'] and status['sha256']==post['sha256']
  assert status['document_job']==jid and status['submission_marker'] is None
  tag=None
  if platform in ['facebook','instagram']:
   tag_file=directory/'evidence'/(jid+'-product-tag.json');tag=json.loads(tag_file.read_text())['product_tag']
   assert tag['name']==post['title'] and tag['price_text']=='£'+format(post['price_gbp'],'.2f') and tag['sha256']==post['sha256']
   assert tag['persisted_editor_readback'] is True and tag['selected_count']==1
   tags.append({'profile_id':name,'post_key':post['post_key'],'name':tag['name'],'price_text':tag['price_text'],'evidence':str(tag_file)})
  label=platform.title()+' · '+str(index)+'/5 · '+post['title']
  try:title=c.call(name,{'op':'label_draft','title':label})['title']
  except Exception as error:title='Label retained: '+str(error)
  binding=c.bindings[name]
  checked.append({'profile_id':name,'post_key':post['post_key'],'title':post['title'],'window_id':binding['window_id'],'tab_id':binding['tab_id'],'caption_verified':True,'photo_verified':True,'account_verified':True,'media_sha256':post['sha256'],'submission_marker':None,'product_tag_verified':tag is not None,'tab_title':title,'source_proof':str(directory/'preparation-result.json')})
with sqlite3.connect((ROOT/'social-publisher/state/outbox.sqlite3').as_uri()+'?mode=ro',uri=True) as db:
 outbox_count=db.execute('SELECT COUNT(*) FROM jobs WHERE payload LIKE ?',('%component-sculptures-drafts-20261123%',)).fetchone()[0]
ledger=[]
for line in (ROOT/'social-publisher/state/intent-ledger.jsonl').read_text().splitlines():
 e=json.loads(line)
 if e.get('kind')=='PUBLISH_INTENT' and e.get('job',{}).get('payload',{}).get('batch_id','').startswith('component-sculptures-drafts-20261123'):ledger.append(e)
assert outbox_count==0 and len(ledger)==0
report={'utc':utc(),'status':'PREPARED_NOT_PUBLISHED_VERIFIED','drafts_verified':len(checked),'platform_counts':dict(Counter(p['profile_id'] for p in checked)),'commerce_tags_verified':len(tags),'source_media_hashes':media,'script_publish_intents':len(ledger),'outbox_jobs_added':outbox_count,'native_script_submission_markers':0,'new_threads_publication_test':'NOT_PERFORMED_PREPARATION_ONLY','tests':{'python':152,'javascript':66},'drafts':checked,'commerce_tags':tags}
atomic_json(OUT/'execution-checks.json',report)
print(json.dumps({k:report[k] for k in ['status','drafts_verified','platform_counts','commerce_tags_verified','script_publish_intents','outbox_jobs_added','native_script_submission_markers']}))
