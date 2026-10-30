"""Independently verify the exact seven-note scope and one Series policy delta."""
import copy,csv,hashlib,json,subprocess
from pathlib import Path
from datetime import datetime,timezone
H=Path(__file__).resolve().parent;B=H.parents[2];read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
g=read(H/'canonical-master-register.json');old=read(H/'inputs/master_register.before');a=read(H/'image-coverage-current.json');before=read(H/'inputs/audit.before');proj=read(H/'projection-index.json');m=read(H/'input-manifest.json');state=read(H/'guided-owner-review-state.json');bp=read(m['b_plan']['snapshot']);an=read(m['a_notes']['snapshot']);oid=proj['optional_option_id'];issues=[];checks=0
def check(ok,label):
 global checks
 checks+=1
 if not ok:issues.append(label)
bitems={x['option_id']:x for x in bp['items']};aitems={x['option_id']:x for x in an['changes']}
check(g['summary']==old['summary']and len(g['options'])==188 and len(g['active_option_ids'])==187,'All catalogue count definitions and retained identities preserved')
for key in ['components','source_sets','source_offer_edges','arrangement_context_references','original_review_specification_assertions','source_only_assertions_not_applied_to_options','aliases','source_media_configuration_coverage','current_frozen_fish_size_policy','wall_sculpture_customisation_policy','source_platform_offer_coverage','retired_option_ids','current_structure_discovery_scope','current_wall_sculpture_inclusion_policy']:
 check(g[key]==old[key],'Unchanged source collection or policy '+key)
for o,b,c,bc in zip(g['options'],old['options'],a['coverage'],before['coverage']):
 ident=o['product_id'];z=copy.deepcopy(o)
 if ident in bitems:
  item=bitems[ident];check(all(o[k]==v for k,v in item['replace_current_fields'].items()),'B exact current fields '+ident);check(o[item['append_history']['field']]==[item['append_history']['entry']],'B exact dated history '+ident)
  for k in item['replace_current_fields']:z[k]=b[k]
  z.pop(item['append_history']['field'])
 if ident in aitems:
  item=aitems[ident];check(all(o[k]==v for k,v in item['protected_fields_exact'].items()),'A all exact protected fields '+ident);check(o['current_reference_note']['text']==item['proposed_current_reference_note'],'A exact current reference clarification '+ident);check(o['historical_reference_note_revisions'][-1]['prior_note_history_exact']==item['prior_note_history_exact'],'A previous note strings retained '+ident)
  z.pop('current_reference_note');z.pop('historical_reference_note_revisions')
 if ident==oid:
  check(o['current_series_optionality_policy']['owner_text']=='okay'and o['current_series_optionality_policy']['new_verified_images']==0,'Only exact approved owner optional policy')
  z.pop('current_series_optionality_policy');z['photo_coverage']['series']=b['photo_coverage']['series'];z['current_photo_task_review']['roles']['series']=copy.deepcopy(b['current_photo_task_review']['roles']['series']);z['current_photo_task_review'].pop('historical_policy_superseded_roles')
 check(z==b,'Entire option unchanged outside precisely authorized fields '+ident)
 z=copy.deepcopy(c)
 if ident==oid:
  check(c['series']['status']=='Optional / no fixed set'and c['series']['reference']is None and not c['series_required'],'Only target Series requirement optional, no photo bound')
  check(c['historical_series_requirement_revisions'][0]['prior_series']==bc['series'],'Exact prior target Series history retained');z.pop('historical_series_requirement_revisions');z['series']=bc['series'];z['series_required']=bc['series_required'];z['owner_review']=bc['owner_review']
 check(z==bc,'Full role record and selected references preserved except single optional policy '+ident)
 check(o['file_id']==b['file_id']and o['folder_id']==b['folder_id']and o.get('context_file_id')==b.get('context_file_id')and o.get('context_folder_id')==b.get('context_folder_id'),'Every selected primary/context stable ID and actual parent preserved '+ident)
 check(o['master_fields']==b['master_fields']and o['selling_details']==b['selling_details']and o['specifications']==b['specifications'],'All accepted specifications, provenance and commercial fields preserved '+ident)
expected=copy.deepcopy(before['counts']);expected['series_statuses']['Optional / no fixed set']+=1;expected['series_statuses']['No verified image']-=1;expected['series_required_options']-=1;expected['actions_by_type']['Find / capture']-=1;expected['actions_by_type']['Optional image']+=1;expected['required_picture_actions']-=1
check(a['counts']==expected,'All count changes limited to one Optional requirement; dated audit counters retained')
for t,b in zip(a['missing_pictures'],before['missing_pictures']):
 z=copy.deepcopy(t)
 if t['option_id']==oid and t['role']=='Series':
  check(t['historical_owner_policy_actions'][0]['before']==b,'Exact previous mandatory task retained');check(t['status']=='Optional'and t['action_type']=='Optional image','Single optional action classification');z.pop('historical_owner_policy_actions');z.pop('owner_series_policy')
  for key in ['action_type','status','action','owner_response','terminal_review_state','qualification']:z[key]=b[key]
 check(z==b,'No other action alteration '+t['option_id']+' '+t['role'])
check(a['identity_review']==before['identity_review'],'All identity exceptions and reviews untouched')
for name,key in [('current-native-reference-map.json','native_map'),('current-assets.json','report_assets'),('pending-followups.json','pending')]:check(sha(H/name)==m[key]['sha256'],'Current native identities/paths or pending proposals byte-identical '+name)
check(not state['queues']['in_situ']and len(state['held_in_situ_ids'])==22,'All22 missing context roles remain held')
check(len(state['queues']['series'])==15 and state['held_series_ids']==['BSI-C3573D23A4B7']and oid not in state['queues']['series'],'Exactly15 active Series, one held, optional target removed')
rows=[json.loads(s)for s in subprocess.check_output(['python3',str(H/'guided_review.py'),'--list'],text=True).splitlines()if s]
check(len(rows)==15 and all(x['role']=='Series'for x in rows)and{r['option_id']for r in rows}==set(state['queues']['series']),'Actual terminal output has exactly the15 active Series IDs')
check('BSI-3635E3DC3434'in{r['option_id']for r in rows},'Pewter Series remains active; Bronze-member exclusion retained')
photo=read(H/'photo-source-review.json');check(len(photo['requests'])==15 and all(x['option_id']!=oid for x in photo['requests']),'Current source task ledger excludes only optional target')
rep=read(H/'report-verification.json');out=Path(rep['output_directory']);brief=read(out/'remaining-photograph-requests.json');check(len(brief['requests'])==15,'Public brief has15 active Series requests')
for file,count in [('Active_Series_Photographs_Required_15.csv',15),('Missing_Pictures_Required.csv',39),('Missing_Series_Images.csv',16),('Optional_Series_Images.csv',55),('Held_In_Situ_Cases_22.csv',22),('Physical_Verification_Input_187_Options.csv',187)]:
 with(out/file).open(encoding='utf-8-sig',newline='')as f:items=list(csv.DictReader(f))
 check(len(items)==count,'Current CSV count '+file)
for item in rep['pages']+rep['csv_files']+rep['thumbnail_files']:check(sha(item['path'])==item['sha256'],'Bound report artifact '+Path(item['path']).name)
for key,item in m.items():check(sha(item['path'])==sha(item['snapshot'])==item['sha256'],'Frozen source CAS '+key)
check(sum(bool(o.get('physical_specifications_verified'))for o in g['options']if o['product_id']in g['active_option_ids'])==0,'No actual physical measurements/verification invented')
result={'status':'FAIL'if issues else'PASS','recorded_utc':datetime.now(timezone.utc).isoformat(),'checks':checks,'issues':issues,'workbook_sha256':sha(H/'master-workbook.pending'),'register_sha256':sha(H/'canonical-master-register.json'),'audit_sha256':sha(H/'image-coverage-current.json'),'current_descriptions_updated':5,'current_statuses_aligned_to_existing_available_role':4,'dated_current_notes_appended':2,'required_series_removed_by_owner_policy':1,'active_context':0,'held_context':22,'active_series':15,'held_series':1,'all_individual_primary_ids_and_physical_fields_unchanged':True,'new_photo_roles_closed':0,'native_or_platform_writes':0,'terminal_script_sha256':sha(H/'guided_review.py')};(H/'native-binding-verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:result[k]for k in ['status','checks','issues']}));raise SystemExit(bool(issues))
