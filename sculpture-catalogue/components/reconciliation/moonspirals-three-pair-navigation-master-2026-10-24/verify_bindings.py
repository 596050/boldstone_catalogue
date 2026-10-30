"""Scoped deep comparison of catalogue, native references and existing owner policies."""
import copy,hashlib,json
from pathlib import Path
from datetime import datetime,timezone
H=Path(__file__).resolve().parent;B=H.parents[2]
read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
m=read(H/'input-manifest.json');g=read(H/'canonical-master-register.json');old=read(m['master_register']['snapshot']);a=read(H/'image-coverage-current.json');olda=read(m['audit']['snapshot']);assets=read(H/'current-assets.json');oldassets=read(m['report_assets']['snapshot']);native=read(H/'current-native-reference-map.json');oldnative=read(m['native_map']['snapshot']);wall=read(H/'wall-circle-history-observations.json')['rows'];proj=read(H/'projection-index.json');moves=proj['changed_native_objects'];issues=[];checks=0
def check(ok,label):
 global checks
 checks+=1
 if not ok:issues.append(label)
check(set(moves)=={'id:cnqzTNngPVsAAAAAAAucCw','id:cnqzTNngPVsAAAAAAAuR4Q','id:cnqzTNngPVsAAAAAAAuigw'},'Exactly3 approved unselected file paths')
check(set(wall)=={'BSI-D5A939264C82','BSI-65520F070145'},'Exactly2 saved primary history observations')
restored=copy.deepcopy(g)
for x,y in zip(restored['options'],old['options']):
 if x['product_id']in wall:
  check(x['current_primary_navigation']['previous_navigation_observation']==y['current_primary_navigation'],'Prior primary observation retained '+x['product_id']);x['current_primary_navigation']=copy.deepcopy(y['current_primary_navigation'])
 check(x==y,'Entire option including all6 field objects/selection/identity/policy unchanged '+x['product_id'])
allowed={'latest_moonspirals_pair_native_navigation_import','latest_wall_circle_exact_history_observation','current_primary_navigation_health','latest_active_photo_source_review','latest_image_coverage_audit'}
for key in set(restored)|set(old):
 if key not in allowed:check(restored.get(key)==old.get(key),'All unrelated top-level register data '+key)
check(g['summary']==old['summary']and len(g['active_option_ids'])==188 and len(g['options'])==189 and len(g['components'])==112,'188 active/189 retained/112 component ID records preserved')
check(sha(H/'working-design-group-projection.json')==m['working_groups']['sha256'],'110 working design groups and both owner edges unchanged')
for i,(x,y)in enumerate(zip(a['coverage'],olda['coverage'])):
 z=copy.deepcopy(x)
 if x['option_id']in wall:z['individual']['current_native_navigation']=copy.deepcopy(y['individual']['current_native_navigation'])
 check(z==y,'Coverage roles/counts/source selections unchanged '+x['option_id'])
z=copy.deepcopy(a);z['coverage']=olda['coverage'];z['current_primary_navigation_health']=copy.deepcopy(olda['current_primary_navigation_health']);check(z==olda,'Audit changes limited to2 navigation annotations and current health pointer; all counts/statuses/holds retained')
check(a['current_primary_navigation_health']==g['current_primary_navigation_health']and a['current_primary_navigation_health']['sha256']==sha(H/'current-primary-navigation-health.json'),'Audit and register current health pointers bind exact same current health bytes')
check(set(assets)==set(oldassets),'Asset set unchanged')
for ident,x in assets.items():
 y=oldassets[ident]
 if ident not in moves:check(x==y,'Unmoved asset exact '+ident);continue
 o=moves[ident];z=copy.deepcopy(x)
 for key in ['path','display_path','folder_path','folder_id','image_url','folder_url','modified_time','historical_same_id_navigation']:
  if key in y:z[key]=copy.deepcopy(y[key])
  else:z.pop(key,None)
 check(z==y,'Moved asset changes limited to current navigation '+ident)
 check(x['folder_id']==o['current_parent_id']and x['display_path']==o['current_path']and x['name']==y['name']and x['bytes']==y['bytes'],'Moved asset ID/name/bytes and actual parent '+ident)
check(set(native['current_objects'])==set(oldnative['current_objects']),'Native map no new file/folder records')
for ident,x in native['current_objects'].items():
 if ident not in moves:check(x==oldnative['current_objects'][ident],'Unmoved native object exact '+ident)
 else:
  z=copy.deepcopy(x);y=oldnative['current_objects'][ident]
  for key in ['path','display_path','parent_id','current_navigation_source']:
   if key in y:z[key]=y[key]
   else:z.pop(key,None)
  check(z==y,'Moved native object exact outside navigation '+ident)
check(native['verified_path_change_history'][:-1]==oldnative['verified_path_change_history'],'Previous native navigation history immutable')
for key in set(native)|set(oldnative):
 if key not in ['status','current_objects','old_path_to_id','verified_path_change_history']:check(native.get(key)==oldnative.get(key),'Native unrelated property '+key)
for key,val in oldnative['old_path_to_id'].items():check(native['old_path_to_id'][key]==val,'Old path alias preserved '+key)
for ident,o in moves.items():check(native['old_path_to_id'][o['old_path'].casefold()]==native['old_path_to_id'][o['current_path'].casefold()]==ident,'Both paths retain stable file ID '+ident)
for ident,obs in wall.items():
 check(obs['deletion_observed_in_exact_id_history']and not obs['current_primary_verified']and not obs['replacement_selected']and not obs['restored_to_dropbox']and obs['owner_hold_preserved'],'Deleted history does not restore or release hold '+ident)
 check(obs['existing_local_historical_original']['dropbox_content_hash']==obs['latest_available_revision']['content_hash'],'Historical bytes match available revision '+ident)
for key,name in [('report_reviews','photo-review-queue.json'),('review_state','guided-owner-review-state.json'),('pending','pending-followups.json'),('photo_source','photo-source-review.json'),('physical_audit','physical-source-audit.json'),('originals','original-verification.json')]:check(sha(H/name)==m[key]['sha256'],'Retained exact source/physical/owner file '+name)
for key,x in m.items():check(sha(x['path'])==sha(x['snapshot'])==x['sha256'],'Frozen input '+key)
check(read(H/'source-evidence-verification.json')['status']=='PASS','All sealed native/current-history packets checked')
plan=read(H/'workbook-edit-plan.json');check(not plan['native_link_changes']and not plan['actual_parent_cells'],'No selected workbook Dropbox link or parent changed;3 files unselected')
check(len(plan['cell_changes'])==9 and len(plan['row_heights'])==4 and not plan['table_appends'],'Nine displayed text edits and4 readability row heights only')
result={'status':'FAIL'if issues else'PASS','recorded_utc':datetime.now(timezone.utc).isoformat(),'checks':checks,'issues':issues,'workbook_sha256':sha(H/'master-workbook.pending'),'register_sha256':sha(H/'canonical-master-register.json'),'audit_sha256':sha(H/'image-coverage-current.json'),'selected_reference_changes':0,'new_physical_verifications':0,'native_or_platform_writes':0,'retained_component_id_records':112,'working_design_groups':110}
(H/'native-binding-verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
if issues:raise SystemExit(1)
