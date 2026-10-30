"""Freeze the published release and import the owner's context-only global hold."""
import copy,hashlib,importlib.util,json,posixpath,shutil
from pathlib import Path
from datetime import datetime,timezone
from xml.etree import ElementTree as E
H=Path(__file__).resolve().parent;B=H.parents[2];OUT=B/'outputs'/H.name
read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();now=lambda:datetime.now(timezone.utc).isoformat()
def write(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
assert not(H/'input-manifest.json').exists(),'Already prepared'
(H/'inputs').mkdir(parents=True);OUT.mkdir(parents=True,exist_ok=True)
p=read(B/'current-master.json');OLD=(B/p['register']).parent;oldout=(B/p['current_image_review_links']['all_links']).parent
source=B/'components/parallel-reviews/terminal-guided-context-20261023T205215Z'
files={'pointer':B/'current-master.json','master_workbook':B/p['workbook'],'master_register':B/p['register'],'audit':OLD/'image-coverage-current.json','native_map':OLD/'current-native-reference-map.json','report_assets':OLD/'current-assets.json','report_reviews':OLD/'photo-review-queue.json','review_state':OLD/'guided-owner-review-state.json','pending':OLD/'pending-followups.json','review_progress':B/'components/reviews/specification_review_progress.json','component_checkpoint':B/'components/checkpoint.json','root_checkpoint':B/'checkpoint.json','source_report_verification':OLD/'report-verification.json','source_count_summary':oldout/'current-count-summary.json','source_photo_requests':oldout/'remaining-photograph-requests.json','owner_policy':source/'all-missing-in-situ-owner-deferral.json','batch_handoff':source/'batch-handoff.json','post_release_followups':OLD/'post-publication-followups.json'}
m={}
for key,path in files.items():
 snap=H/'inputs'/(key+'.before');shutil.copy2(path,snap);m[key]={'path':str(path),'snapshot':str(snap),'sha256':sha(path)}
write(H/'input-manifest.json',m)
d=read(m['owner_policy']['snapshot']);batch=read(m['batch_handoff']['snapshot'])
assert batch['owner_policy_sha256']==m['owner_policy']['sha256']and d['role']=='In situ'and d['photo_gaps_closed']==0
assert d['current_register_sha256']==p['register_sha256']==sha(B/p['register'])and d['current_workbook_sha256']==p['workbook_sha256']==sha(B/p['workbook'])
events=[]
for line in Path(d['source']['transcript']).open():
 if d['source']['timestamp']in line:
  event=json.loads(line)
  if event.get('payload',{}).get('id')==d['source']['message_id']:events.append(event)
assert len(events)==1 and events[0]['payload']['role']=='user'and d['owner_text']in[x.get('text')for x in events[0]['payload']['content']]
for item in batch['per_item_owner_receipts']:assert sha(item['path'])==item['sha256']
g=read(m['master_register']['snapshot']);a=read(m['audit']['snapshot']);state=read(m['review_state']['snapshot']);reviews=read(m['report_reviews']['snapshot']);pending=read(m['pending']['snapshot'])
held=set(d['all_held_option_ids']);new=set(d['newly_held_current_option_ids'])
missing={x['option_id']for x in a['missing_pictures']if x['role']=='In situ'and x['status']=='Open'}
assert held==missing and len(held)==22 and new==set(state['queues']['in_situ'])and len(new)==12
note='Owner hold: all missing in situ/display photographs are deferred until the owner resumes. The image gap remains open; separate series requests stay active.'
event={**d,'canonical_applied':True,'applied_utc':now(),'source_receipt':m['owner_policy']['path'],'source_sha256':m['owner_policy']['sha256']}
for o in g['options']:
 if o['product_id']in held:o['current_global_context_owner_hold']=event
for c in a['coverage']:
 if c['option_id']in held:c['in_situ']['global_owner_deferral']=event;c['owner_review']=(c.get('owner_review','')+'\n'+note).strip()
for t in a['missing_pictures']:
 if t['role']=='In situ'and t['option_id']in held:t['global_owner_deferral']=event;t['owner_response']=(t.get('owner_response','')+'\n'+note).strip()
for t in reviews:
 if t['role']=='In situ'and t['option_id']in held:t['global_owner_deferral']=event;t['next_action']='Owner held: do not prompt for this context photograph until the owner resumes.'
state.update(queues={**state['queues'],'in_situ':[]},held_in_situ_ids=sorted(held),global_context_owner_hold=event,status='ALL_MISSING_CONTEXT_REQUESTS_OWNER_HELD_SERIES_ACTIVE',current_phase='series',current_role='Series',pending_question=None,missing_source_task='17 separate series requests remain active. All22 missing context requests are owner-held; no context prompts until resumed.',updated_utc=now())
state['latest_completed_scope'].update(active_in_situ_reviewed=0,held_context_cases=22,series_reviewed=17,all_context_prompts_suppressed=True)
g['current_global_context_owner_hold']=event;g.setdefault('owner_context_review_event_history',[]).extend(batch['per_item_owner_receipts'])
g['latest_image_coverage_audit'].update(path=str(H/'image-coverage-current.json'),audit=str((H/'image-coverage-current.json').relative_to(B)),recorded_utc=now(),status='COVERAGE_GAPS_UNCHANGED_GLOBAL_CONTEXT_PROMPTS_HELD')
for key,name in [('verification','saved-file-verification.json'),('native_binding_verification','native-binding-verification.json'),('visual_verification','visual-verification.json')]:g['latest_image_coverage_audit'][key]=str((H/name).relative_to(B));g['latest_image_coverage_audit'].pop(key+'_sha256',None)
g['latest_image_coverage_audit'].pop('audit_sha256',None)
post=read(m['post_release_followups']['snapshot']);holdentries=[x for x in post['entries']if x['kind']=='OWNER_CONTEXT_DEFERRAL_NEXT_IMPORT'];nativeentries=[x for x in post['entries']if x['kind']!='OWNER_CONTEXT_DEFERRAL_NEXT_IMPORT']
pending.setdefault('imported_post_release_hold_history',[]).extend([{**x,'applied_as_historical_owner_hold':True,'global_hold_supersedes_prompting':True}for x in holdentries]);pending['entries'].extend(nativeentries);pending['status']='GLOBAL_CONTEXT_HOLD_IMPORTED_LATER_COMPLETED_NATIVE_NAVIGATION_QUEUED'
photo=read(OLD/'photo-source-review.json');context=[x for x in photo['requests']if x['role']=='Display/context'];assert len(context)==12
for x in context:x.update(review_state='OWNER_GLOBAL_CONTEXT_HOLD_GAP_RETAINED',global_owner_deferral=event)
photo['held_requests'].extend(context);photo['requests']=[x for x in photo['requests']if x['role']=='Series'];photo.update(status='GLOBAL_CONTEXT_HOLD_17_SEPARATE_SERIES_REQUESTS_ACTIVE',role_counts={'Display/context':0,'Series':17},held_context_cases=22,global_context_owner_hold=event)
write(H/'photo-source-review.json',photo)
g['latest_active_photo_source_review'].update(path=str(H/'photo-source-review.json'),sha256=sha(H/'photo-source-review.json'),active_context_roles=0,active_context_requests=0,active_roles=17,held_context_cases=22,series_requests=17,active_series_roles=17,source_inventory_reused_without_new_native_search=True)
summary={'status':'GLOBAL_CONTEXT_ONLY_OWNER_HOLD_IMPORTED','recorded_utc':now(),'owner_policy':m['owner_policy']['path'],'owner_policy_sha256':m['owner_policy']['sha256'],'held_context_option_ids':sorted(held),'newly_held_context_option_ids':sorted(new),'active_context':0,'held_context':22,'active_series':17,'photograph_gaps_closed':0,'physical_fields_changed':0,'primary_images_changed':0,'individual_and_series_role_bindings_changed':0,'new_native_paths_imported':0,'native_or_platform_writes':0}
g['latest_global_context_hold_import']=summary
for name,value in [('canonical-master-register.json',g),('image-coverage-current.json',a),('photo-review-queue.json',reviews),('guided-owner-review-state.json',state),('pending-followups.json',pending),('global-context-hold-import.json',summary),('global-owner-context-hold.json',event)]:write(H/name,value)
for name in ['current-native-reference-map.json','current-assets.json','physical-source-audit.json','original-verification.json','guided_review.py','author_workbook.mjs','verify_workbook.py']:shutil.copy2(OLD/name,H/name)
modules=H/'node_modules'
if not modules.exists():modules.symlink_to(Path('/Users/tprice/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules'),target_is_directory=True)
write(H/'source-evidence-verification.json',{'status':'PASS','owner_global_hold_transcript_verified':True,'owner_policy_sha256':m['owner_policy']['sha256'],'historical_per_item_owner_receipts_verified':len(batch['per_item_owner_receipts']),'previous_source_original_verification_retained':True,'new_physical_verifications':0,'new_native_or_platform_writes':0})
write(H/'evidence-manifest.json',{str(H/name):{'sha256':sha(H/name)}for name in ['global-owner-context-hold.json','global-context-hold-import.json','source-evidence-verification.json','photo-source-review.json','physical-source-audit.json','original-verification.json']})
# Author only owner-review notes and current summary/navigation cells.
spec=importlib.util.spec_from_file_location('native_reader',B/'components/reconciliation/image-identity-coverage-2026-10-20/verify_edit.py');v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v);w=v.load(H/'inputs/master_workbook.before');changes={};links={}
def protected(sn,c):return sn=='Fingerprint History'or sn=='Source Specifications'and c.rstrip('0123456789')in ['M','N']or sn=='Moonphases and Dune'and c.rstrip('0123456789')=='I'
def setcell(sn,c,value):
 assert c not in w['formulas'][sn]
 if w['values'][sn].get(c,'')!=value:changes[(sn,c)]={'sheet':sn,'cell':c,'before':w['values'][sn].get(c,''),'value':value}
def link(sn,c,label,target):setcell(sn,c,label);links[(sn,c)]={'sheet':sn,'cell':c,'label':label,'target':target}
for sn,z in w['sheets'].items():
 rp=posixpath.join(posixpath.dirname(z['part']),'_rels',posixpath.basename(z['part'])+'.rels');rr={x.get('Id'):x.get('Target')for x in E.fromstring(w['files'][rp])}
 for x in z['root'].findall('.//'+v.q('hyperlink')):
  c=x.get('ref');u='#'+x.get('location')if x.get('location')else rr[x.get('{'+v.R+'}id')]
  if not protected(sn,c):u=u.replace(str(oldout),str(OUT))
  links[(sn,c)]={'sheet':sn,'cell':c,'label':w['values'][sn].get(c,''),'target':u}
for i,c in enumerate(a['coverage'],10):
 if c['option_id']in held:setcell('Photo Coverage','U'+str(i),c['owner_review'])
for i,t in enumerate(a['missing_pictures'],10):
 if t['role']=='In situ'and t['option_id']in held:setcell('Missing Pictures','M'+str(i),t['owner_response'])
link('Master Catalogue','A3','187 active options;112 working component identities. All22 missing context photographs are owner-held.17 separate series requests remain active. Existing identities, photographs, specifications and estimates are retained.',str(OUT/'remaining-photograph-requests.html'))
link('Photo Coverage','A3','177 complete individual,165 context and116 series references. All22 missing in situ/display requests are on owner hold;0 active context requests.17 series requests remain active. Frozen Fish legacy identity remains deferred.',str(OUT/'remaining-photograph-requests.html'))
link('Missing Pictures','A3','40 diagnostic image gaps remain:22 owner-held context,17 active series and one deferred individual identity. Held context gaps remain open; no context prompts until the owner resumes.',str(OUT/'index.html'))
for key,x in changes.items():
 if key in links:links[key]['label']=x['value']
expected={('Photo Coverage','B4'):177,('Photo Coverage','B5'):10,('Photo Coverage','D4'):165,('Photo Coverage','F4'):116,('Missing Pictures','B4'):39,('Missing Pictures','D4'):1,('Missing Pictures','F4'):54,('Master Catalogue','H4'):186,('Master Catalogue','B4'):187,('Master Catalogue','F4'):187}
plan={'cell_changes':list(changes.values()),'formula_changes':[{'sheet':sn,'cell':c,'before':w['formulas'][sn][c],'formula':w['formulas'][sn][c],'expected':value}for(sn,c),value in expected.items()],'value_blocks':[{'sheet':x['sheet'],'range':x['cell'],'values':[[x['value']]]}for x in changes.values()],'formula_blocks':[],'hyperlinks':list(links.values()),'row_heights':[],'table_appends':[],'new_sheets':{},'target_rows':[],'expected_original_sheet_count':len(w['sheets']),'expected_formula_count':sum(map(len,w['formulas'].values())),'summary_expected':[{'sheet':sn,'cell':c,'value':value}for(sn,c),value in expected.items()],'baseline_ranges':[['Photo Coverage','A2:V5','baseline-current-coverage'],['Photo Coverage','U15:V15','baseline-pewter-review']],'preview_ranges':[['Photo Coverage','A2:V5','01-context-hold-summary'],['Photo Coverage','U15:V15','02-pewter-context-held-series-active'],['Missing Pictures','L37:N37','03-owner-context-hold-note'],['Master Catalogue','A1:Y3','04-master-context-hold-summary']]}
write(H/'workbook-edit-plan.json',plan);write(H/'expected-edit.json',{'sheets':{},'hyperlinks':plan['hyperlinks'],'formulas':[]})
builder=(H/'author_workbook.mjs').read_text().replace('DECO004_NAVIGATION_AND_PHYSICAL_SOURCE_REVIEW_EXPORTED','GLOBAL_CONTEXT_OWNER_HOLD_MASTER_EXPORTED');(H/'author_workbook.mjs').write_text(builder)
verifier=(H/'verify_workbook.py').read_text().replace('Deco004 actual containing parent refreshed for three existing contexts; same-ID scene navigation retained for Timeless003,002/003 identity holds preserved. One scoped context deferral;187 physical source records audited without specification upgrades.','Global context-only owner hold applied to22 unresolved context roles. All identities, native references, specifications, individual and series role bindings are preserved;17 series requests remain active.');(H/'verify_workbook.py').write_text(verifier)
print(json.dumps({'status':'PREPARED','active_context':0,'held_context':22,'series':17,'cell_changes':len(changes),'new_native_path_imports':0,'new_physical_verifications':0}))
