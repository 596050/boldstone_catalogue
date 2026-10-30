"""Apply seven scoped current-note corrections and one approved Series policy."""
import copy,hashlib,json,shutil
from pathlib import Path
from datetime import datetime,timezone
H=Path(__file__).resolve().parent;B=H.parents[2];OUT=B/'outputs'/H.name
read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();now=lambda:datetime.now(timezone.utc).isoformat()
jsha=lambda x:hashlib.sha256(json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def write(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
assert not(H/'import-summary.json').exists(),'Import already prepared'
(H/'inputs').mkdir(exist_ok=True);OUT.mkdir(parents=True,exist_ok=True)
p=read(B/'current-master.json');OLD=(B/p['register']).parent;oldout=(B/p['current_image_review_links']['all_links']).parent
assert p['register_sha256']=='707f2b7dd33fbe96623aa2b9ee72315064d3aaab5d69b3ff12172a0c7b23c895'
A=B/'components/parallel-reviews/current-note-corrections-20261023T220427Z';R=B/'components/parallel-reviews/series-terminal-walkthrough-20261023T212756Z';C=B/'components/parallel-reviews/existing-garden-room-review-20261023T215744Z/current-summary-patch'
files={'pointer':B/'current-master.json','master_workbook':B/p['workbook'],'master_register':B/p['register'],'audit':OLD/'image-coverage-current.json','native_map':OLD/'current-native-reference-map.json','report_assets':OLD/'current-assets.json','report_reviews':OLD/'photo-review-queue.json','review_state':OLD/'guided-owner-review-state.json','pending':OLD/'pending-followups.json','review_progress':B/'components/reviews/specification_review_progress.json','component_checkpoint':B/'components/checkpoint.json','root_checkpoint':B/'checkpoint.json','source_report_verification':OLD/'report-verification.json','source_count_summary':oldout/'current-count-summary.json','source_photo_requests':oldout/'remaining-photograph-requests.json','a_notes':A/'current-note-correction-addendum.json','a_seal':A/'sealed-handoff.json','b_plan':C/'patch-plan.json','b_rehearsal':C/'verification-receipt.json','owner_batch':R/'sealed-owner-decisions-batch02.json','optional_receipt':R/'dune-partial-owner-approved-series-optional.json','optional_proposal':R/'dune-partial-series-optionality-proposal.json'}
m={}
for key,path in files.items():
 snap=H/'inputs'/(key+'.before');shutil.copy2(path,snap);m[key]={'path':str(path),'snapshot':str(snap),'sha256':sha(path)}
write(H/'input-manifest.json',m)
expected={'a_notes':'d11de935a345f205abb5c92795faf6aa8cf174951444d3f74416fe9413017343','a_seal':'08166fcd1e176d7b68b83f82b91e3b67d024c3308632df10732282beedeccb8f','b_plan':'6b2311764716872cf3d0d2dce4be888cc781e18603a229db0baf13822dd5b0e8','owner_batch':'33f111e007e440dc9ab9d18f07588bf2bffb405c0faebf945c023df70f4903d5','optional_receipt':'a5f62c092ce628dab2245a8e05a7aacf5d41af3f41089c30aa13c1b3f2f5c5a8','optional_proposal':'2010b2776aa20ebdfb16c4709e01c0bfeb99748bd1299cf7895015a2276cb232'}
for key,value in expected.items():assert m[key]['sha256']==value,key
an=read(m['a_notes']['snapshot']);bp=read(m['b_plan']['snapshot']);event=read(m['optional_receipt']['snapshot']);seal=read(m['a_seal']['snapshot']);batch=read(m['owner_batch']['snapshot'])
evidence={}
for item in seal['files']+batch['receipts']+bp['source_native_evidence']:
 assert sha(item['path'])==item['sha256'],item['path'];evidence[item['path']]={'sha256':item['sha256']}
assert event['owner_text']=='okay'and event['approved_proposal_sha256']==m['optional_proposal']['sha256']and event['new_verified_images']==0
g=read(m['master_register']['snapshot']);a=read(m['audit']['snapshot']);old=copy.deepcopy(g);before=copy.deepcopy(a);opts={o['product_id']:o for o in g['options']};coverage={c['option_id']:c for c in a['coverage']}
for item in bp['items']:
 o=opts[item['option_id']];guard=item['guards'];assert jsha(o)==item['option_sha256_before'];assert all(o[k]==v for k,v in guard['context_fields'].items());assert coverage[item['option_id']]['in_situ']==guard['coverage_in_situ']and o['photo_coverage']==guard['option_photo_coverage']
 h=item['append_history'];assert h['field']not in o;o.update(copy.deepcopy(item['replace_current_fields']));o[h['field']]=[copy.deepcopy(h['entry'])]
for item in an['changes']:
 o=opts[item['option_id']]
 assert all(o[k]==v for k,v in item['protected_fields_exact'].items()),item['option_id']
 assert o['file_id']==item['expected_selected_file_id']and o['context_file_id']==item['expected_context_file_id']and o['context_folder_id']==item['expected_context_folder_id']
 assert not o.get('current_reference_note')
 o.setdefault('historical_reference_note_revisions',[]).append({'recorded_utc':now(),'prior_note_history_exact':copy.deepcopy(item['prior_note_history_exact']),'source_packet':m['a_notes']['path'],'source_sha256':m['a_notes']['sha256']})
 o['current_reference_note']={'recorded_utc':now(),'text':item['proposed_current_reference_note'],'selected_file_id':item['expected_selected_file_id'],'context_file_id':item['expected_context_file_id'],'role':'Individual'if item['option_id']=='BSI-1E0C826D896E'else'In situ','source_packet':m['a_notes']['path'],'source_sha256':m['a_notes']['sha256'],'new_role_binding':False,'physical_verification_added':False}
oid=event['option_id'];assert oid=='BSI-6405184B86EB';o=opts[oid];c=coverage[oid]
assert o['file_id']==event['individual_primary_retained']and o['folder_id']==event['folder_retained']and c['series']['status']=='No verified image'and c['series']['reference']is None and c['series_required']is True
policy={**copy.deepcopy(event),'source_receipt':m['optional_receipt']['path'],'source_sha256':m['optional_receipt']['sha256'],'canonical_applied':True,'applied_utc':now()}
text='Owner approved Series optional for this individually sold panel with no fixed matched set. The exact-finish group photograph remains unverified. No image is added or matched; individual and accepted in situ references are retained.'
o['current_series_optionality_policy']=policy;o['photo_coverage']['series']='Optional / no fixed set'
role=o['current_photo_task_review']['roles']['series'];o['current_photo_task_review'].setdefault('historical_policy_superseded_roles',[]).append({'recorded_utc':now(),'role':'series','before':copy.deepcopy(role),'owner_policy':policy})
role.update(state='OWNER_APPROVED_SERIES_OPTIONAL_NO_FIXED_SET',finding=text,next_action='No mandatory Series photograph for this option. Any later group reference remains optional and requires its own exact identity/finish check.',owner_policy=policy)
c.setdefault('historical_series_requirement_revisions',[]).append({'recorded_utc':now(),'prior_series':copy.deepcopy(c['series']),'prior_series_required':True,'prior_owner_review':c['owner_review']})
c['series'].update(status='Optional / no fixed set',basis=text,terminal_review_state='OWNER_APPROVED_SERIES_OPTIONAL_NO_FIXED_SET',owner_policy=policy);c['series_required']=False;c['owner_review']=(c['owner_review']+'\n'+text).strip()
actions=[t for t in a['missing_pictures']if t['option_id']==oid and t['role']=='Series'];assert len(actions)==1;t=actions[0];prior=copy.deepcopy(t)
t['historical_owner_policy_actions']=[{'recorded_utc':now(),'before':prior,'owner_policy':policy}];t.update(action_type='Optional image',status='Optional',action='Optional: show this individually sold panel in a group if useful; no fixed matched set requires a Series photograph.',owner_response=text,terminal_review_state='OWNER_APPROVED_SERIES_OPTIONAL_NO_FIXED_SET',owner_series_policy=policy)
t['qualification']+='\n'+text
reviews=read(m['report_reviews']['snapshot']);matches=[x for x in reviews if x['option_id']==oid and x['role']=='Series'];assert len(matches)==1;rv=matches[0];rv['historical_owner_policy_review']=copy.deepcopy(rv);rv.update(review_state='OWNER_APPROVED_SERIES_OPTIONAL_NO_FIXED_SET',next_action=role['next_action'],finding=text,owner_series_policy=policy)
state=read(m['review_state']['snapshot']);assert oid in state['queues']['series'];state.setdefault('historical_queue_snapshots',[]).append({'recorded_utc':now(),'before_series_queue':copy.deepcopy(state['queues']['series']),'reason':'One owner-approved Series optionality policy'})
state['queues']['series'].remove(oid);state.setdefault('owner_approved_optional_series_reviews',[]).append(policy);state.update(updated_utc=now(),missing_source_task='15 active Series requests; Dune2 Copper Series held. All22 missing context requests held. Copper and Partial Verdigris Series optional by owner policy.')
photo=read(OLD/'photo-source-review.json');matched=[x for x in photo['requests']if x['option_id']==oid and x['role']=='Series'];assert len(matched)==1;photo['requests']=[x for x in photo['requests']if x not in matched];photo.setdefault('owner_optional_series_requests',[]).append({'previous_request':matched[0],'owner_policy':policy});photo.update(status='15_SERIES_ACTIVE_ONE_SERIES_HELD_ALL22_CONTEXT_HELD',role_counts={'Display/context':0,'Series':15},owner_optional_series_policies=1)
assert len(photo['requests'])==15 and len(state['queues']['series'])==15
# Dated terminal-pass counters stay historical. Only current role/action aggregates change.
a['counts']['series_statuses']['Optional / no fixed set']+=1;a['counts']['series_statuses']['No verified image']-=1;a['counts']['series_required_options']-=1;a['counts']['actions_by_type']['Find / capture']-=1;a['counts']['actions_by_type']['Optional image']+=1;a['counts']['required_picture_actions']-=1
summary={'status':'CURRENT_NOTES_AND_ONE_OWNER_SERIES_POLICY_IMPORTED','recorded_utc':now(),'current_descriptions_updated':5,'current_statuses_aligned_to_existing_available_role':4,'dated_current_reference_notes_appended':2,'owner_series_requirements_made_optional':1,'current_option_ids_affected':[x['option_id']for x in bp['items']]+[x['option_id']for x in an['changes']]+[oid],'photograph_role_bindings_added':0,'photograph_gaps_verified_closed':0,'native_paths_changed':0,'primary_images_changed':0,'new_physical_verifications':0,'accepted_specifications_changed':0,'active_context':0,'held_context':22,'active_series':15,'held_series':1,'required_picture_actions':39,'input_packets':{k:{'path':m[k]['path'],'sha256':m[k]['sha256']}for k in ['a_notes','b_plan','owner_batch']}}
g['latest_current_note_finalization_import']=summary;g.setdefault('imported_series_owner_review_packets',[]).append({'path':m['owner_batch']['path'],'sha256':m['owner_batch']['sha256'],'optional_series_policies':[policy],'image_roles_closed':0});g['latest_active_photo_source_review'].update(path=str(H/'photo-source-review.json'),sha256=sha(OLD/'photo-source-review.json'),active_series_roles=15,series_requests=15,active_roles=15,owner_optional_series_policies=1)
write(H/'photo-source-review.json',photo);g['latest_active_photo_source_review']['sha256']=sha(H/'photo-source-review.json')
g['latest_image_coverage_audit'].update(path=str(H/'image-coverage-current.json'),audit=str((H/'image-coverage-current.json').relative_to(B)),counts=copy.deepcopy(a['counts']),recorded_utc=now(),status='CURRENT_NOTES_CORRECTED_ONE_OWNER_SERIES_POLICY_OPTIONAL')
for key,name in [('verification','saved-file-verification.json'),('native_binding_verification','native-binding-verification.json'),('visual_verification','visual-verification.json')]:g['latest_image_coverage_audit'][key]=str((H/name).relative_to(B));g['latest_image_coverage_audit'].pop(key+'_sha256',None)
g['latest_image_coverage_audit'].pop('audit_sha256',None)
for name,value in [('canonical-master-register.json',g),('image-coverage-current.json',a),('photo-review-queue.json',reviews),('guided-owner-review-state.json',state),('import-summary.json',summary),('owner-series-optionality-import.json',policy)]:write(H/name,value)
for name in ['current-native-reference-map.json','current-assets.json','pending-followups.json','physical-source-audit.json','guided_review.py','author_workbook.mjs','verify_workbook.py','original-verification.json']:shutil.copy2(OLD/name,H/name)
write(H/'source-evidence-verification.json',{'status':'PASS','frozen_note_targets':7,'precise_owner_optional_policy':1,'new_native_queries':0,'new_physical_verifications':0,'native_or_platform_writes':0})
write(H/'evidence-manifest.json',evidence)
write(H/'projection-index.json',{'old_output':str(oldout),'new_output':str(OUT),'a_option_ids':[x['option_id']for x in an['changes']],'b_option_ids':bp['exact_target_option_ids'],'optional_option_id':oid})
if not(H/'node_modules').exists():(H/'node_modules').symlink_to('/Users/tprice/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules',target_is_directory=True)
print(json.dumps(summary))
