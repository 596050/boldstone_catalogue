"""Rebase seven exact owner photo requirements onto the verified Riyadh release."""
import copy,hashlib,json,shutil
from pathlib import Path
from datetime import datetime,timezone
H=Path(__file__).resolve().parent;B=H.parents[2];OUT=B/'outputs'/H.name
read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();now=lambda:datetime.now(timezone.utc).isoformat()
def write(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
assert not(H/'import-summary.json').exists();(H/'inputs').mkdir(exist_ok=True);OUT.mkdir(parents=True,exist_ok=True)
p=read(B/'current-master.json');OLD=(B/p['register']).parent;oldout=Path(read(OLD/'report-verification.json')['output_directory'])
assert p['register_sha256']=='05b5c2dc85d9952cbccfa6bd86dddbc7e404f822e948635936ef96e571239b0e'
batches=[B/'components/parallel-reviews'/x for x in ['moon-crater-two-series-owner-policy-20261023T234551Z/sealed-later-series-policy-batch-03.json','acanthus-one-leaf-pewter-series-policy-20261023T235035Z/sealed-b-next-series-policy-batch04.json']]
assert [sha(x)for x in batches]==['4a66f5b30ff049e2ad75e9b5d16e4660f4034ad0f7c320c435864b04fe05c29a','083525299d2715b1311c5762a1922910f79b1079b6d7e65f13ef086e597ad1ce']
policies=[e for path in batches for e in read(path)['decisions']];assert len(policies)==len({x['option_id']for x in policies})==7
files={'pointer':B/'current-master.json','master_workbook':B/p['workbook'],'master_register':B/p['register'],'audit':OLD/'image-coverage-current.json','native_map':OLD/'current-native-reference-map.json','report_assets':OLD/'current-assets.json','report_reviews':OLD/'photo-review-queue.json','review_state':OLD/'guided-owner-review-state.json','pending':OLD/'pending-followups.json','review_progress':B/'components/reviews/specification_review_progress.json','component_checkpoint':B/'components/checkpoint.json','root_checkpoint':B/'checkpoint.json','source_report_verification':OLD/'report-verification.json','source_count_summary':oldout/'current-count-summary.json','source_photo_requests':oldout/'remaining-photograph-requests.json'}
for i,path in enumerate(batches):files['owner_batch_'+str(i)]=path
for i,e in enumerate(policies):assert sha(e['path'])==e['sha256'];files['policy_'+str(i)]=Path(e['path'])
m={}
for key,path in files.items():
 snap=H/'inputs'/(key+'.before');shutil.copy2(path,snap);m[key]={'path':str(path),'snapshot':str(snap),'sha256':sha(path)}
write(H/'input-manifest.json',m);write(H/'WORK_STATE.json',{'status':'FROZEN_SEVEN_EXACT_PHOTO_POLICIES','remaining_MCP4_Verdigris_Rust':'Owner question pending; excluded from this freeze','plan':['Apply seven scoped photo requirements','Preserve all navigation and specifications','Author, verify, refresh reports and publish']})
g=read(m['master_register']['snapshot']);a=read(m['audit']['snapshot']);reviews=read(m['report_reviews']['snapshot']);state=read(m['review_state']['snapshot']);photo=read(OLD/'photo-source-review.json');opts={o['product_id']:o for o in g['options']};cov={c['option_id']:c for c in a['coverage']};events=[];prior_required_flags=0
for item in policies:
 e=read(item['path']);oid=e['option_id'];o=opts[oid];c=cov[oid]
 assert c['series']['status']=='No verified image'and not o.get('current_series_optionality_policy')
 assert c['series']['reference']is None or (c['series']['reference']['file_id']=='Unbound'and not c['series']['reference'].get('image_url'))
 prior_required_flags+=bool(c['series_required'])
 assert o['file_id']==e['primary_reference']['file_id']and o['folder_id']==e['primary_reference']['folder_id']
 event={**e,'source_receipt':item['path'],'source_sha256':item['sha256'],'canonical_applied':True,'applied_utc':now()};events.append(event)
 text='Owner made this exact option’s group/series photograph optional. Existing individual sale and family/arrangement associations remain. This does not confirm that no companion set exists. Exact group photograph remains unverified.'
 o['current_series_optionality_policy']=event;o['photo_coverage']['series']='Optional / no fixed set';review=o['current_photo_task_review']['roles']['series']
 o['current_photo_task_review'].setdefault('historical_policy_superseded_roles',[]).append({'recorded_utc':now(),'role':'series','before':copy.deepcopy(review),'owner_policy':event})
 review.update(state='OWNER_APPROVED_SERIES_PHOTOGRAPH_OPTIONAL',finding=text,next_action='No mandatory group/series photograph under this exact owner decision. Retain all existing family/arrangement associations.',owner_policy=event)
 c.setdefault('historical_series_requirement_revisions',[]).append({'recorded_utc':now(),'prior_series':copy.deepcopy(c['series']),'prior_series_required':c['series_required'],'prior_owner_review':c['owner_review']})
 c['series'].update(status='Optional / no fixed set',basis=text,terminal_review_state='OWNER_APPROVED_SERIES_PHOTOGRAPH_OPTIONAL',owner_policy=event);c['series_required']=False;c['owner_review']=(c['owner_review']+'\n'+text).strip()
 task=next(t for t in a['missing_pictures']if t['option_id']==oid and t['role']=='Series');before=copy.deepcopy(task)
 task.setdefault('historical_owner_policy_actions',[]).append({'recorded_utc':now(),'before':before,'owner_policy':event})
 task.update(action_type='Optional image',status='Optional',action='Group/series photograph optional under the owner decision for this exact option.',owner_response=text,terminal_review_state='OWNER_APPROVED_SERIES_PHOTOGRAPH_OPTIONAL',owner_series_policy=event);task['qualification']+='\n'+text
 for rv in reviews:
  if rv['option_id']==oid and rv['role']=='Series':rv['historical_owner_policy_review']=copy.deepcopy(rv);rv.update(review_state='OWNER_APPROVED_SERIES_PHOTOGRAPH_OPTIONAL',next_action=review['next_action'],finding=text,owner_series_policy=event)
 assert oid in state['queues']['series'];state['queues']['series'].remove(oid)
 matched=[r for r in photo['requests']if r['option_id']==oid and r['role']=='Series'];assert len(matched)==1
 photo['requests']=[r for r in photo['requests']if r not in matched];photo.setdefault('owner_optional_series_requests',[]).append({'previous_request':matched[0],'owner_policy':event})
c=a['counts'];c['series_statuses']['No verified image']-=7;c['series_statuses']['Optional / no fixed set']+=7;c['series_required_options']-=prior_required_flags;c['actions_by_type']['Find / capture']-=7;c['actions_by_type']['Optional image']+=7;c['required_picture_actions']-=7
assert c['series_required_options']==sum(bool(x['series_required'])for x in a['coverage']if x['option_id']in g['active_option_ids'])
state.setdefault('owner_approved_optional_series_reviews',[]).extend(events);state.update(updated_utc=now(),missing_source_task='One active Series-photo requirement and one individual water-build photograph;22 context and one other Series requirement held. Frozen Fish legacy identity deferred.')
photo.update(status='ONE_SERIES_AND_ONE_INDIVIDUAL_ACTIVE_CONTEXT_HELD',role_counts={'Individual':1,'Display/context':0,'Series':1})
summary={'status':'SEVEN_EXACT_OWNER_SERIES_PHOTO_POLICIES_IMPORTED','recorded_utc':now(),'option_ids':[e['option_id']for e in events],'new_series_requirements_made_optional':7,'current_options':188,'retained_options':189,'component_identities':112,'required_picture_actions':26,'active_series':1,'held_series':1,'active_individual_source_cases':1,'held_context':22,'optional_series':69,'new_photo_bindings':0,'new_verified_group_photos':0,'new_physical_verifications':0,'new_native_paths':0,'native_or_platform_writes':0,'series_photo_optional_does_not_remove_companion_associations':True}
g['latest_seven_series_photo_policy_import']=summary
g.setdefault('imported_series_owner_review_packets',[]).extend({'path':str(path),'sha256':sha(path),'optional_series_policies':[e for e in events if any(e['option_id']==r['option_id']for r in read(path)['decisions'])],'new_verified_photos':0}for path in batches)
g['latest_active_photo_source_review'].update(path=str(H/'photo-source-review.json'),active_roles=2,active_series_roles=1,series_requests=1,active_individual_roles=1)
write(H/'photo-source-review.json',photo);g['latest_active_photo_source_review']['sha256']=sha(H/'photo-source-review.json')
g['latest_image_coverage_audit'].update(path=str(H/'image-coverage-current.json'),audit=str((H/'image-coverage-current.json').relative_to(B)),counts=copy.deepcopy(c),recorded_utc=now(),status='SEVEN_EXACT_SERIES_PHOTO_REQUIREMENTS_OPTIONAL')
for key,file in [('verification','saved-file-verification.json'),('native_binding_verification','native-binding-verification.json'),('visual_verification','visual-verification.json')]:g['latest_image_coverage_audit'][key]=str((H/file).relative_to(B));g['latest_image_coverage_audit'].pop(key+'_sha256',None)
g['latest_image_coverage_audit'].pop('audit_sha256',None)
for file,value in [('canonical-master-register.json',g),('image-coverage-current.json',a),('photo-review-queue.json',reviews),('guided-owner-review-state.json',state),('import-summary.json',summary),('imported-owner-series-policies.json',events)]:write(H/file,value)
for file in ['current-native-reference-map.json','current-assets.json','pending-followups.json','physical-source-audit.json','guided_review.py','verify_workbook.py','original-verification.json','working-entry-owner-provenance-sidecar.json']:shutil.copy2(OLD/file,H/file)
write(H/'source-evidence-verification.json',{'status':'PASS','exact_owner_policy_receipts':7,'new_native_calls':0,'new_physical_verifications':0})
write(H/'evidence-manifest.json',{e['source_receipt']:{'sha256':e['source_sha256']}for e in events})
write(H/'projection-index.json',{'old_output':str(oldout),'new_output':str(OUT),'option_ids':summary['option_ids'],'changed_native_objects':{},'current_reference_fields':[]})
if not(H/'node_modules').exists():(H/'node_modules').symlink_to('/Users/tprice/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules',target_is_directory=True)
print(json.dumps(summary))
