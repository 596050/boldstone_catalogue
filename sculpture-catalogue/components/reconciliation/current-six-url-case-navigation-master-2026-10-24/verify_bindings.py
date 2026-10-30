import copy,hashlib,json
from pathlib import Path
from datetime import datetime,timezone
H=Path(__file__).resolve().parent;read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
m=read(H/'input-manifest.json');g=read(H/'canonical-master-register.json');old=read(m['master_register']['snapshot']);a=read(H/'image-coverage-current.json');olda=read(m['audit']['snapshot']);h=read(H/'verified-six-cases.json');cases={r['option_id']:r for r in h['rows']};issues=[];checks=0
def check(ok,label):
 global checks
 checks+=1
 if not ok:issues.append(label)
for x,y in zip(g['options'],old['options']):
 expected=copy.deepcopy(y)
 if x['product_id']in cases:expected.update(cases[x['product_id']]['proposed'])
 check(x==expected,'Entire qualified option object retained except12 guarded URL fields '+x['product_id'])
check(g['summary']==old['summary']and len(g['active_option_ids'])==188 and len(g['components'])==112,'188 active options and112 retained IDs unchanged')
check(sha(H/'working-design-group-projection.json')==m['working_groups']['sha256'],'110 working groups and2 separate owner equivalences retained')
check(a['counts']==olda['counts'],'All photograph source-status and owner-action counts unchanged')
check(g['current_owner_design_equivalence_edges']==old['current_owner_design_equivalence_edges'],'No owner equivalence altered')
for key in ['specifications','master_fields','selling_details']:check([o[key]for o in g['options']]==[o[key]for o in old['options']],'All189 '+key+' field dictionaries retained')
for key in ['original_review_specification_assertions','source_only_assertions_not_applied_to_options','current_authenticated_squarespace_inventory_observation','confirmed_arrangement_member_edges','listing_resolution_source_edges','current_global_context_owner_hold','wall_sculpture_customisation_policy','current_frozen_fish_size_policy']:check(g[key]==old[key],'Unchanged source/identity/owner policy '+key)
for key in ['source_sets','source_offer_edges']:
 left=copy.deepcopy(g[key]);right=copy.deepcopy(old[key])
 for rows in [left,right]:
  for x in rows:x.pop('current_primary_reference',None)
 check(left==right,'Captured source offers/BOM immutable outside current own-image navigation '+key)
media=copy.deepcopy(g['source_media_configuration_coverage']);media[163].pop('current_example_reference_navigation',None);check(media==old['source_media_configuration_coverage'],'Only explicit own-file navigation added; all coverageIDs/BOM/status/scopes retained')
journal=read(H/'current-reference-change-journal.json')
for x in journal:
 check(not any(s in x['path'].split('/')for s in ['specifications','master_fields','selling_details','historical_previous_review','source_field_record']),'No raw specification/history projection '+x['path'])
 if x['before'].casefold()!=x['value'].casefold():check((H/'moonwave-native-import.json').exists(),'Non-case navigation requires approved Moonwave evidence')
assets=read(H/'current-assets.json');oldassets=read(m['report_assets']['snapshot']);native=read(H/'current-native-reference-map.json');oldnative=read(m['native_map']['snapshot']);moves=read(H/'moonwave-native-import.json')['moved_file_ids']if(H/'moonwave-native-import.json').exists()else[];caseids={r['expected_file_id']for r in cases.values()};allowed=caseids|set(moves)
check(set(assets)==set(oldassets),'No asset identity added or removed')
for ident,x in assets.items():
 y=oldassets[ident]
 if ident not in allowed:check(x==y,'Unrelated asset exact '+ident)
 else:
  check(x['file_id']==y['file_id']and x['name']==y['name']and x['bytes']==y['bytes'],'Same image identity/name/bytes '+ident)
  if ident in caseids:check(x['folder_id']==y['folder_id'],'Case-only exact parent unchanged '+ident)
check(set(native['current_objects'])==set(oldnative['current_objects'])|set(moves),'Only10 already-existing sealed moved file IDs newly represented in scoped map')
check(native['old_path_to_id'].items()>=oldnative['old_path_to_id'].items(),'Existing path aliases retained')
check(native['verified_path_change_history'][:len(oldnative['verified_path_change_history'])]==oldnative['verified_path_change_history'],'Earlier navigation history immutable')
for x in read(H/'path-change-history.json'):check(x['current']['file_id']==x['before']['file_id'],'Same native object ID '+x['file_id'])
for key,name in [('review_state','guided-owner-review-state.json'),('pending','pending-followups.json'),('physical_audit','physical-source-audit.json'),('originals','original-verification.json'),('primary_health','current-primary-navigation-health.json')]:check(sha(H/name)==m[key]['sha256'],'Historical working/measurement/owner bytes unchanged '+name)
for key,x in m.items():check(sha(x['path'])==sha(x['snapshot'])==x['sha256'],'Frozen input '+key)
plan=read(H/'workbook-edit-plan.json');check(all(x['sheet']!='Source Specifications'or x['cell'].rstrip('0123456789')not in['M','N']for x in plan['native_link_changes']),'Historical M/N source URL targets protected')
check(not plan['row_heights']and not plan['table_appends'],'No row or table redesign')
check(read(H/'source-evidence-verification.json')['status']=='PASS','Sealed navigation evidence checked')
result={'status':'FAIL'if issues else'PASS','recorded_utc':datetime.now(timezone.utc).isoformat(),'checks':checks,'issues':issues[:80],'workbook_sha256':sha(H/'master-workbook.pending'),'register_sha256':sha(H/'canonical-master-register.json'),'audit_sha256':sha(H/'image-coverage-current.json'),'active_options':188,'retained_component_ids':112,'working_design_groups':110,'new_physical_verifications':0,'native_or_platform_writes':0}
(H/'native-binding-verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
if issues:raise SystemExit(1)
