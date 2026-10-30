"""Verify exact source projection and one owner exception without new photo claims."""
import collections,copy,csv,hashlib,json,subprocess
from pathlib import Path
from datetime import datetime,timezone
H=Path(__file__).resolve().parent;B=H.parents[2];read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
g=read(H/'canonical-master-register.json');old=read(H/'inputs/master_register.before');a=read(H/'image-coverage-current.json');before=read(H/'inputs/audit.before');m=read(H/'input-manifest.json');proj=read(H/'projection-index.json');oid='BSI-C3AA3700F7DA';issues=[];checks=0
def check(ok,label):
 global checks
 checks+=1
 if not ok:issues.append(label)
check(len(g['active_option_ids'])==188 and len(g['options'])==189 and len(g['components'])==112,'188active189retained112identities')
for k in ['summary','count_definition','components','active_option_ids','retired_option_ids','arrangement_context_references','confirmed_arrangement_member_edges','source_sets','source_offer_edges','aliases','original_review_specification_assertions','listing_resolution_native_action_drafts','current_frozen_fish_size_policy','wall_sculpture_customisation_policy','current_structure_discovery_scope','current_wall_sculpture_inclusion_policy']:check(g[k]==old[k],'Preserved source/identity/native history '+k)
for o,b in zip(g['options'],old['options']):
 z=copy.deepcopy(o)
 if o['product_id']==oid:
  e=z.pop('owner_accepted_listing_references');check(e['technical_individual_status_retained']=='Group only'and not e['separate_full_image_verified']and e['references'][0]['target_member_position']is None,'Qualified whole group without standalone/member-position claim')
 check(z==b,'Full canonical option data retained '+o['product_id'])
newkeys={'six_working_fields','six_working_fields_sha256','six_working_fields_hash_scheme','working_field_projection_source','physical_specs_verified','publication_performed'}
for e,b in zip(g['current_listing_resolution_details']['entries'],old['current_listing_resolution_details']['entries']):
 z=copy.deepcopy(e)
 if e['product_id']in proj['draft_option_ids']:
  d=z['draft_listing'];o=next(o for o in g['options']if o['product_id']==e['product_id']);check(d['six_working_fields']==o['master_fields'],'All6 full qualified field objects exact '+e['product_id']);check(not d['physical_specs_verified']and not d['publication_performed'],'No physical/native readiness added '+e['product_id'])
  for k in newkeys:d.pop(k)
 check(z==b,'Exact original draft scaffold, conditions and source fields retained '+e['product_id'])
full=[e for e in g['current_listing_resolution_details']['entries']if e['product_id']in g['active_option_ids']and(e.get('draft_listing')or{}).get('six_working_fields')];check(len(full)==101,'101complete local individual drafts,606fieldgroups')
for x in g['current_existing_listing_copy_projections']['entries']:
 o=next(o for o in g['options']if o['product_id']==x['option_id']);check(x['current_working_fields']==o['master_fields']and x['copy_values']=={k:v['display']for k,v in o['master_fields'].items()},'Current six-field copy exact '+x['option_id']);check(not x['executable_now']and not x['native_tuple_is_fresh_verified']and not x['platform_mutation_authorized'],'No native mutation or fresh target match '+x['option_id'])
for c,b in zip(a['coverage'],before['coverage']):
 z=copy.deepcopy(c)
 if c['option_id']==oid:
  for k in ['owner_review_disposition','owner_acceptance','separate_individual_capture_required']:z['individual'].pop(k)
  z['notes']=b['notes'];z['owner_review']=b['owner_review'];check(c['individual']['status']=='Group only'and not c['individual']['complete_standalone_image']and c['individual']['exact_member_position']is None,'Technical coverage staysGroupOnly')
 check(z==b,'All role bindings, source metadata and existing qualifications retained '+c['option_id'])
for t,b in zip(a['missing_pictures'],before['missing_pictures']):
 z=copy.deepcopy(t)
 if t['option_id']==oid and t['role']=='Individual':
  check(z.pop('historical_before_owner_listing_reference_acceptance')==b,'Exact old separate capture task retained');z.pop('owner_listing_reference_acceptance')
  for k in ['status','action','owner_response','qualification']:z[k]=b[k]
 check(z==b,'Unrelated task unchanged '+t['option_id']+' '+t['role'])
expected=copy.deepcopy(before['counts'])
for k,delta in [('required_picture_actions',-1),('resolved_action_rows',1),('active_action_rows',-1),('outstanding_individual_image_or_identity_actions',-1),('separate_individual_photographs_required',-1),('owner_accepted_group_or_combined_reference_exceptions',1)]:expected[k]+=delta
expected['actions_by_type']['Find / capture']-=1;expected['actions_by_role']['Individual']-=1;check(a['counts']==expected,'Only exact capture/owner-exception aggregate delta')
active=[t for t in a['missing_pictures']if t['status']in ['Open','Optional']];check(a['counts']['actions_by_role']==dict(collections.Counter(t['role']for t in active)),'Role counters derived from current task rows');check(len(active)==94 and len([t for t in active if t['status']=='Open'])==24,'94active rows include24required+70optional')
check(a['current_individual_photo_capture_policy']==g['current_individual_photo_capture_policy'],'Both current capture policy projections exact')
r=g['current_individual_photo_capture_policy']['current_requirements'];check(r['individual_gaps']==1 and r['separate_individual_images_required']==0 and r['scoped_accepted_group_or_combined_exceptions']==10 and oid in r['scoped_owner_exception_option_ids'],'Current capture requirements/exception IDs aligned')
r=a['individual_capture_queue_counts'];check(r['individual_gaps']==1 and r['separate_photographs_required']==0 and r['scoped_accepted_group_or_combined_exceptions']==10 and r['technical_individual_gaps']==11,'Coverage capture queue counters aligned')
state=read(H/'guided-owner-review-state.json');check(state['queues']['individual']==state['queues']['series']==state['queues']['in_situ']==[] and len(state['held_in_situ_ids'])==22 and state['held_series_ids']==['BSI-C3573D23A4B7']and state['deferred_individual_ids']==['BSI-04D6E8690F30'],'All active photo queues empty; all holds retained');check(oid in state['no_repeat_individual_prompt_option_ids'],'No repeat individual prompt')
rows=subprocess.check_output(['python3',str(H/'guided_review.py'),'--list'],text=True).splitlines();check(not rows,'Actual terminal emits no active photograph request')
photo=read(H/'photo-source-review.json');check(photo['requests']==[]and photo['role_counts']=={'Individual':0,'Display/context':0,'Series':0}and photo['owner_optional_series_policies']==16,'Current source-review scalar/list consistency')
for f,k in [('current-native-reference-map.json','native_map'),('current-assets.json','report_assets'),('pending-followups.json','pending')]:check(sha(H/f)==m[k]['sha256'],'Native source assets or pending state byte-identical '+f)
rep=read(H/'report-verification.json');out=Path(rep['output_directory'])
for name,num in [('Missing_Pictures_Required.csv',24),('Missing_Individual_Images.csv',1),('Resolved_Image_Associations.csv',113),('Owner_Accepted_Qualified_Listing_References.csv',10),('Separate_Individual_Photographs_Required_0.csv',0),('Physical_Verification_Input_188_Options.csv',188)]:
 with(out/name).open(encoding='utf-8-sig',newline='')as f:rs=list(csv.DictReader(f))
 check(len(rs)==num,'Export count '+name)
for x in rep['pages']+rep['csv_files']+rep['thumbnail_files']:check(sha(x['path'])==x['sha256'],'Report bytes '+Path(x['path']).name)
for k,x in m.items():check(sha(x['path'])==sha(x['snapshot'])==x['sha256'],'Frozen input '+k)
result={'status':'FAIL'if issues else'PASS','recorded_utc':datetime.now(timezone.utc).isoformat(),'checks':checks,'issues':issues,'workbook_sha256':sha(H/'master-workbook.pending'),'register_sha256':sha(H/'canonical-master-register.json'),'audit_sha256':sha(H/'image-coverage-current.json'),'current_options':188,'retained_options':189,'current_complete_individual_drafts':101,'current_embedded_working_field_groups':606,'active_photograph_requests':0,'qualified_owner_exceptions':10,'complete_individual_photographs':177,'new_complete_photographs':0,'new_physical_verifications':0,'native_or_platform_writes':0}
(H/'native-binding-verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:result[k]for k in ['status','checks','issues']}));raise SystemExit(bool(issues))
