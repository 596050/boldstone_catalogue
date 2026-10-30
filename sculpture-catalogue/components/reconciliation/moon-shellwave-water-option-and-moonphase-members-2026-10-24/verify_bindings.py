"""Independent data/role/queue verification for the two exact owner decisions."""
import copy,csv,hashlib,json,subprocess
from pathlib import Path
from datetime import datetime,timezone
H=Path(__file__).resolve().parent;B=H.parents[2];read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();g=read(H/'canonical-master-register.json');old=read(H/'inputs/master_register.before');a=read(H/'image-coverage-current.json');before=read(H/'inputs/audit.before');m=read(H/'input-manifest.json');p=read(H/'projection-index.json');proposal=read(m['product_proposal']['snapshot']);members=read(m['member_decision']['snapshot']);oid=p['new_option_id'];issues=[];checks=0
def check(ok,label):
 global checks
 checks+=1
 if not ok:issues.append(label)
check(len(g['options'])==189 and len(g['active_option_ids'])==188 and len(g['components'])==112,'188 active189 retained112 existing identities')
check(g['active_option_ids']==old['active_option_ids']+[oid]and g['retired_option_ids']==old['retired_option_ids'],'Only new option appended; retired record retained')
check([o['product_id']for o in g['options'][:-1]]==[o['product_id']for o in old['options']],'All previous IDs and option order unchanged')
for o,b in zip(g['options'][:-1],old['options']):
 z=copy.deepcopy(o)
 if o['product_id']in p['member_option_ids']:z['confirmed_arrangement_ids']=b['confirmed_arrangement_ids'];check(o['confirmed_arrangement_ids']==b['confirmed_arrangement_ids']+[members['reference_id']],'Exact Moonphase reverse membership '+o['product_id'])
 check(z==b,'Entire earlier option preserved outside four membership arrays '+o['product_id'])
check(a['coverage'][:-1]==before['coverage']and a['missing_pictures'][:-1]==before['missing_pictures']and a['identity_review']==before['identity_review'],'Every prior coverage/task/identity row byte-equivalent in data')
o=g['options'][-1];check(o['canonical_key']==proposal['proposed_canonical_key']and oid=='BSI-'+hashlib.sha256(o['canonical_key'].encode()).hexdigest()[:12].upper(),'New ID deterministically assigned to exact canonical key')
check(len({x['canonical_key']for x in g['options']})==189 and len({x['product_id']for x in g['options']})==189,'No duplicate ID or option key')
check(o['canonical_component_id']==o['canonical_design_id']=='BC-MSW-MOON','Water build under existing design2')
for field,v in proposal['working_fields'].items():check(o['master_fields'][field]['display']==v['display']and o['master_fields'][field]['physical_verification']==0,'Exact qualified working value '+field)
check(o['selling_details']['estimated_price']==750 and o['selling_details']['price_status']=='estimate'and o['selling_details']['lead_time_min_weeks']==1 and o['selling_details']['lead_time_max_weeks']==2,'750 estimate and1–2week owner supply policy')
check('Pump, basin, pipework and installation'in o['selling_details']['included_or_excluded_scope'],'Panel-only price scope preserved')
check(not o['physical_specifications_verified']and not o['platform_publication_performed']and not o.get('owner_accepted_listing_references'),'No physical, platform or standalone-image approval invented')
for c,b in zip(g['components'],old['components']):
 z=copy.deepcopy(c)
 if c['component_id']=='BC-MSW-MOON':
  check(c['option_ids']==b['option_ids']+[oid]and c['option_count']==3,'Component2 adds one build option');z['option_ids']=b['option_ids'];z['option_names']=b['option_names'];z['retained_names']=b['retained_names'];z['option_count']=b['option_count']
 check(z==b,'Every prior component field preserved '+c['component_id'])
arr=next(x for x in g['arrangement_context_references']if x['reference_id']==members['reference_id']);oldarr=next(x for x in old['arrangement_context_references']if x['reference_id']==members['reference_id']);z=copy.deepcopy(arr);z.pop('historical_member_identification');z.pop('owner_member_confirmation');z['confirmed_member_option_ids']=oldarr['confirmed_member_option_ids'];z['component_identification']=oldarr['component_identification'];check(z==oldarr,'Arrangement changes only confirmed membership metadata')
check(g['confirmed_arrangement_member_edges']==old['confirmed_arrangement_member_edges']+members['proposed_member_edges'],'Exactly four owner-confirmed member edges appended')
for key in ['original_review_specification_assertions','source_only_assertions_not_applied_to_options','source_sets','source_offer_edges','aliases','source_media_configuration_coverage','current_frozen_fish_size_policy','wall_sculpture_customisation_policy','source_platform_offer_coverage','current_structure_discovery_scope','current_wall_sculpture_inclusion_policy']:check(g[key]==old[key],'Original source/policy preserved '+key)
c=a['coverage'][-1];check(c['individual']['status']=='Group only'and c['in_situ']['status']==c['series']['status']=='Available','New roles retain technical GroupOnly and qualified scene/series source')
for role in ['individual','in_situ','series']:check(c[role]['reference']['file_id']=='id:cnqzTNngPVsAAAAAAAubvA'and c[role]['reference']['folder_id']=='id:cnqzTNngPVsAAAAAAAyinQ'and c[role]['exact_member_position']is None,'Exact unchanged whole-source reference and no member pixel binding '+role)
expected=copy.deepcopy(before['counts']);expected.update(individual_options=188)
for key in ['action_rows','active_action_rows','required_picture_actions','technical_individual_reference_gaps','outstanding_individual_image_or_identity_actions','separate_individual_photographs_required','retained_option_coverage_rows','series_required_options']:expected[key]+=1
expected['individual_statuses']['Group only']+=1;expected['in_situ_statuses']['Available']+=1;expected['series_statuses']['Available']+=1;expected['actions_by_role']['Individual']+=1;expected['actions_by_type']['Find / capture']+=1
check(a['counts']==expected,'Exact count increments; no earlier gap closed or owner exception copied')
for name,key in [('current-native-reference-map.json','native_map'),('current-assets.json','report_assets'),('pending-followups.json','pending')]:check(sha(H/name)==m[key]['sha256'],'Native map/assets/pending proposals immutable '+name)
state=read(H/'guided-owner-review-state.json');check(state['queues']['individual']==[oid]and len(state['queues']['series'])==15 and len(state['held_in_situ_ids'])==22 and state['held_series_ids']==['BSI-C3573D23A4B7'],'Current queues and all holds retained')
rows=[json.loads(s)for s in subprocess.check_output(['python3',str(H/'guided_review.py'),'--list'],text=True).splitlines()if s];check(len(rows)==16 and sum(x['role']=='Individual'for x in rows)==1 and sum(x['role']=='Series'for x in rows)==15,'Actual terminal output16 active source cases without sending a question')
rep=read(H/'report-verification.json');out=Path(rep['output_directory'])
for file,num in [('Current_Individual_Options_188.csv',188),('Specification_Verification_Checklist_1128_Fields.csv',1128),('Physical_Verification_Input_188_Options.csv',188),('Current_Selling_Details_188.csv',188),('Missing_Pictures_Required.csv',40),('Missing_Individual_Images.csv',2),('Separate_Individual_Photographs_Required_1.csv',1)]:
 with(out/file).open(encoding='utf-8-sig',newline='')as f:rs=list(csv.DictReader(f))
 check(len(rs)==num,'Current CSV population '+file)
 if file.startswith('Physical_Verification_Input'):check(all(not r['actual_width_cm']and not r['actual_height_cm']and not r['actual_maximum_depth_cm']and not r['bare_panel_measured_weight_kg']for r in rs),'Actual physical input cells remain blank; no photograph-derived measurement')
for item in rep['pages']+rep['csv_files']+rep['thumbnail_files']:check(sha(item['path'])==item['sha256'],'Current report bytes '+Path(item['path']).name)
for key,item in m.items():check(sha(item['path'])==sha(item['snapshot'])==item['sha256'],'Frozen inputs CAS '+key)
result={'status':'FAIL'if issues else'PASS','recorded_utc':datetime.now(timezone.utc).isoformat(),'checks':checks,'issues':issues,'workbook_sha256':sha(H/'master-workbook.pending'),'register_sha256':sha(H/'canonical-master-register.json'),'audit_sha256':sha(H/'image-coverage-current.json'),'current_options':188,'retained_options':189,'components':112,'new_option_id':oid,'new_designs':0,'new_physical_verifications':0,'new_individual_source_cases':1,'confirmed_existing_member_edges_added':4,'existing_image_roles_changed':0,'active_context':0,'held_context':22,'active_series':15,'held_series':1,'native_or_platform_writes':0};(H/'native-binding-verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:result[k]for k in ['status','checks','issues']}));raise SystemExit(bool(issues))
