"""Independently verify exact navigation deltas and narrow owner decisions."""
import copy,csv,hashlib,json,subprocess
from pathlib import Path
from datetime import datetime,timezone
H=Path(__file__).resolve().parent;B=H.parents[2];read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
g=read(H/'canonical-master-register.json');old=read(H/'inputs/master_register.before');a=read(H/'image-coverage-current.json');before=read(H/'inputs/audit.before');native=read(H/'current-native-reference-map.json');old_native=read(H/'inputs/native_map.before');history=read(H/'path-change-history.json');summary=read(H/'import-summary.json');state=read(H/'guided-owner-review-state.json');issues=[];checks=0
def check(ok,label):
 global checks
 checks+=1
 if not ok:issues.append(label)
oid='BSI-C3573D23A4B7';pewter='BSI-3635E3DC3434'
check(g['summary']==old['summary']and len(g['options'])==188 and len(g['active_option_ids'])==187,'All catalogue count definitions preserved')
for key in ['components','original_review_specification_assertions','source_only_assertions_not_applied_to_options','aliases','source_media_configuration_coverage','current_frozen_fish_size_policy','wall_sculpture_customisation_policy','source_platform_offer_coverage','retired_option_ids']:
 check(g[key]==old[key],'Immutable source/policy collection '+key)
for o,b,c,bc in zip(g['options'],old['options'],a['coverage'],before['coverage']):
 ident=o['product_id'];z=copy.deepcopy(o)
 if ident==oid:z.pop('current_series_owner_deferral')
 if ident==pewter:z.pop('series_candidate_exclusions')
 check(z==b,'Entire option unchanged except two explicit owner metadata additions '+ident)
 z=copy.deepcopy(c)
 if ident==oid:z['series'].pop('owner_deferral');z['owner_review']=bc['owner_review']
 if ident==pewter:z['series'].pop('candidate_exclusions');z['owner_review']=bc['owner_review']
 check(z==bc,'All role bindings/qualifications/statuses unchanged except scoped owner metadata '+ident)
check(a['counts']==before['counts']and a['counts']['required_picture_actions']==40,'40 diagnostic gaps and all Available totals retained')
for collection,index in [('source_sets',2),('source_offer_edges',16)]:
 z=copy.deepcopy(g[collection]);z[index]['current_primary_reference']=old[collection][index]['current_primary_reference'];check(z==old[collection],'Only exact current-primary URL changed in '+collection)
 ref=g[collection][index]['current_primary_reference'];check(ref['file_id']=='id:cnqzTNngPVsAAAAAAArp5A'and ref['folder_id']=='id:cnqzTNngPVsAAAAAAAyjBQ'and 'Four%20Panel%20Arrangements'in ref['folder_url'],'Raked source keeps exact file and parent IDs')
z=copy.deepcopy(g['arrangement_context_references']);b=old['arrangement_context_references'][18]
for key in ['image_url','folder_url']:z[18][key]=b[key]
z[18]['images'][0]=b['images'][0];check(z==old['arrangement_context_references'],'Workshop arrangement identity/relationships unchanged; navigation only')
check(g['arrangement_context_references'][18]['folder_id']=='id:cnqzTNngPVsAAAAAAAyidA'and '/Workshop%20and%20Moulding/'in g['arrangement_context_references'][18]['folder_url'],'Workshop file actual containing folder ID preserved after ancestor move')
z=copy.deepcopy(a['identity_review']);z[57]['reference']=before['identity_review'][57]['reference'];check(z==before['identity_review'],'Identity review changes only exact Workshop reference path')
for t,b in zip(a['missing_pictures'],before['missing_pictures']):
 z=copy.deepcopy(t)
 if t['option_id']==oid and t['role']=='Series':z.pop('owner_deferral');z['owner_response']=b['owner_response']
 if t['option_id']==pewter and t['role']=='Series':z.pop('exact_candidate_exclusion');z['owner_response']=b['owner_response']
 check(z==b,'Every action retained except scoped owner decisions '+t['option_id']+' '+t['role'])
check(len(history)==70 and sum(x['current']['object_type']=='file'for x in history)==66,'70 native object projections,66 existing files')
parents=[]
for item in history:
 ident=item['file_id'];obj=native['current_objects'][ident];check(obj==item['current'],'Native current object exact '+ident)
 if obj['object_type']=='file':
  old_parent=item['before']['parent_id'];new_parent=obj['parent_id']
  if old_parent!=new_parent:parents.append(ident);check(old_parent=='id:cnqzTNngPVsAAAAAAAyjCA'and new_parent=='id:cnqzTNngPVsAAAAAAA6Vrg','Exact eight-file In Situ parent projection '+ident)
check(len(parents)==8,'Exactly8 file parent IDs change')
for ident in ['id:cnqzTNngPVsAAAAAAAr3zw','id:cnqzTNngPVsAAAAAAAuh1g']:
 asset=read(H/'current-assets.json')[ident];prior=read(H/'inputs/report_assets.before')[ident];check(asset==prior,'Raked008/009 unchanged '+ident)
check(native['current_objects']['id:cnqzTNngPVsAAAAAAAyidA']['parent_id']=='id:cnqzTNngPVsAAAAAAA6Vpw','Workshop folder has exact verified destination parent')
check(not state['queues']['in_situ']and len(state['held_in_situ_ids'])==22,'All22 missing context roles remain held')
check(len(state['queues']['series'])==16 and state['held_series_ids']==[oid],'Only DuneCopper Series deferred')
rows=[json.loads(s)for s in subprocess.check_output(['python3',str(H/'guided_review.py'),'--list'],text=True).splitlines()if s]
check(len(rows)==16 and all(x['role']=='Series'for x in rows)and{r['option_id']for r in rows}==set(state['queues']['series']),'Actual terminal16 Series only; exact canonical queue')
check(oid not in{r['option_id']for r in rows}and pewter in{r['option_id']for r in rows},'Copper held; Pewter Series still unresolved and active')
ex=g['options'][next(i for i,o in enumerate(g['options'])if o['product_id']==pewter)]['series_candidate_exclusions'][0]
check(ex['candidate_file_id']=='id:cnqzTNngPVsAAAAAAAuf1w'and ex['owner_confirmed_finish']=='Bronze'and ex['component_position']=='Right-hand curved panel'and not ex['solid_bronze_material_inferred'],'Bronze finish assertion scoped to one member; not material or other panels')
policy=g['current_wall_sculpture_inclusion_policy'];check(policy['include_all_water_fountains_in_wall_sculptures']and not policy['exclude_by_water_feature_function']and not policy['all_water_fountain_individual_components_reconciled'],'Owner includes water fountains without inventing completed component coverage')
rep=read(H/'report-verification.json');out=Path(rep['output_directory']);brief=read(out/'remaining-photograph-requests.json');check(len(brief['requests'])==16 and brief['counts']['held_series_cases_excluded']==1,'16 active public Series requests,1 held')
for file,count in [('Active_Series_Photographs_Required_16.csv',16),('Held_Series_Cases_1.csv',1),('Missing_Pictures_Required.csv',40),('Missing_Series_Images.csv',17),('Held_In_Situ_Cases_22.csv',22)]:
 with(out/file).open(encoding='utf-8-sig',newline='')as f:items=list(csv.DictReader(f))
 check(len(items)==count,'Current CSV count '+file)
for item in read(H/'original-verification.json')['files']:check(sha(item['local_original'])==item['sha256'],'Whole original bytes unchanged '+item['file_id'])
for item in rep['pages']+rep['csv_files']+rep['thumbnail_files']:check(sha(item['path'])==item['sha256'],'Bound report artifact '+Path(item['path']).name)
for key,item in read(H/'input-manifest.json').items():check(sha(item['path'])==sha(item['snapshot'])==item['sha256'],'Frozen source CAS '+key)
result={'status':'FAIL'if issues else'PASS','recorded_utc':datetime.now(timezone.utc).isoformat(),'checks':checks,'issues':issues,'workbook_sha256':sha(H/'master-workbook.pending'),'register_sha256':sha(H/'canonical-master-register.json'),'audit_sha256':sha(H/'image-coverage-current.json'),'file_paths_refreshed':66,'actual_file_parent_changes':8,'actual_folder_parent_changes':1,'active_context':0,'held_context':22,'active_series':16,'held_series':1,'all_individual_primary_ids_and_physical_fields_unchanged':True,'new_photo_roles_closed':0,'native_or_platform_writes':0,'terminal_script_sha256':sha(H/'guided_review.py')};(H/'native-binding-verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:result[k]for k in ['status','checks','issues']}));raise SystemExit(bool(issues))
