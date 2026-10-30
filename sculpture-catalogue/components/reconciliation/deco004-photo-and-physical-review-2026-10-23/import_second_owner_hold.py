"""Import the second received context-only owner hold before freezing publication."""
import copy,hashlib,json,shutil
from pathlib import Path
from datetime import datetime,timezone
H=Path(__file__).resolve().parent;B=H.parents[2]
read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
m=read(H/'input-manifest.json');p=B/'components/parallel-reviews/terminal-guided-context-20261023T205215Z/two-leaves-pewter-owner-deferral.json';dest=H/'inputs/owner_two_leaves_pewter_deferral.before';shutil.copy2(p,dest);m['owner_two_leaves_pewter_deferral']={'path':str(p),'snapshot':str(dest),'sha256':sha(p)};d=read(dest);oid=d['option_id'];assert oid=='BSI-449C4421ABD0'and not d['photo_gap_closed']
events=[]
for line in Path(d['source']['transcript']).open():
 if d['source']['timestamp']in line:
  z=json.loads(line)
  if z.get('payload',{}).get('id')==d['source']['message_id']:events.append(z)
assert len(events)==1 and events[0]['payload']['role']=='user'and d['owner_text']in[z.get('text')for z in events[0]['payload']['content']]
event={**d,'canonical_applied':True,'applied_utc':datetime.now(timezone.utc).isoformat(),'source_receipt':str(p),'source_sha256':sha(p)};note='Owner deferred this context photograph on 23 October 2026: "ignore it for the time being". Gap remains open until owner resumes.'
g=read(H/'canonical-master-register.json');a=read(H/'image-coverage-current.json');q=read(H/'photo-review-queue.json');s=read(H/'guided-owner-review-state.json');photo=read(H/'photo-source-review.json')
o=next(x for x in g['options']if x['product_id']==oid);assert 'current_context_owner_deferral'not in o;o['current_context_owner_deferral']=event;c=next(x for x in a['coverage']if x['option_id']==oid);c['in_situ']['owner_deferral']=event;c['owner_review']=(c.get('owner_review','')+'\n'+note).strip()
for t in a['missing_pictures']:
 if t['option_id']==oid and t['role']=='In situ':t['owner_response']=note;t['owner_deferral']=event
for t in q:
 if t['option_id']==oid and t['role']=='In situ':t['owner_deferral']=event;t['next_action']='Hold this context request until the owner resumes.'
assert oid in s['queues']['in_situ'];s['queues']['in_situ'].remove(oid);s['owner_held_context_reviews'].append(event);s['latest_completed_scope'].update(active_in_situ_reviewed=12,new_context_deferrals=2,held_context_cases=10)
g['latest_owner_context_deferral_import']={'status':'TWO_CONTEXT_ONLY_OWNER_HOLDS_IMPORTED','events':[read(H/'owner-context-deferral-import.json'),event],'active_context_requests':12,'held_context_cases':10,'photo_gaps_closed':0}
g['latest_active_photo_source_review'].update(active_context_requests=12,held_context_cases=10,active_roles=29)
match=[x for x in photo['requests']if x['option_id']==oid and x['role']=='Display/context'];assert len(match)==1;match[0].update(review_state='OWNER_DEFERRED_GAP_RETAINED',owner_deferral=event);photo['requests']=[x for x in photo['requests']if x not in match];photo['held_requests'].extend(match);photo.update(status='31_ROLES_REVIEWED_29_ACTIVE_AFTER_TWO_SCOPED_OWNER_DEFERRALS',role_counts={'Display/context':12,'Series':17},held_context_cases=10)
for name,x in [('input-manifest.json',m),('canonical-master-register.json',g),('image-coverage-current.json',a),('photo-review-queue.json',q),('guided-owner-review-state.json',s),('photo-source-review.json',photo),('owner-context-deferral-imports.json',[read(H/'owner-context-deferral-import.json'),event])]:write(H/name,x)
e=read(H/'evidence-manifest.json')
for name in ['photo-source-review.json','owner-context-deferral-imports.json']:e[str(H/name)]={'sha256':sha(H/name)}
write(H/'evidence-manifest.json',e);print(json.dumps({'status':'PASS','active_context':12,'held_context':10,'series':17,'roles_closed':0}))
