"""Read-only check of identities, exact policies, navigation and current reports."""
import copy,csv,hashlib,json,subprocess
from pathlib import Path
from datetime import datetime,timezone
H=Path(__file__).resolve().parent;B=H.parents[2]
read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
g=read(H/'canonical-master-register.json');old=read(H/'inputs/master_register.before');a=read(H/'image-coverage-current.json');before=read(H/'inputs/audit.before');m=read(H/'input-manifest.json');proj=read(H/'projection-index.json');ids=set(proj['option_ids']);issues=[];checks=0
def check(ok,label):
 global checks
 checks+=1
 if not ok:issues.append(label)
navpaths=set(proj['current_reference_fields'])
def diff(x,y,path=''):
 if type(x)!=type(y):return [path]
 if isinstance(x,dict):
  if x.keys()!=y.keys():return [path+'/@keys']
  return [p for k in x for p in diff(x[k],y[k],path+'/'+str(k))]
 if isinstance(x,list):
  if len(x)!=len(y):return [path+'/@length']
  return [p for i,(v,z)in enumerate(zip(x,y))for p in diff(v,z,path+'/'+str(i))]
 return []if x==y else[path]
check(g['summary']==old['summary']and len(g['active_option_ids'])==188 and len(g['options'])==189 and len(g['components'])==112,'188 active189 retained112 identities unchanged')
check(g['count_definition']==old['count_definition'] and '189'in g['count_definition']and'188'in g['count_definition'],'Current count definition preserved')
for key in ['components','active_option_ids','retired_option_ids','arrangement_context_references','confirmed_arrangement_member_edges','original_review_specification_assertions','source_sets','source_offer_edges','aliases','current_frozen_fish_size_policy','wall_sculpture_customisation_policy','source_platform_offer_coverage','current_structure_discovery_scope','current_wall_sculpture_inclusion_policy']:
 check(not any(p.lstrip('/')not in navpaths for p in diff(g[key],old[key],'/'+key)),'Source membership and policies preserved '+key)
for i,(o,b,c,bc)in enumerate(zip(g['options'],old['options'],a['coverage'],before['coverage'])):
 oid=o['product_id'];z=copy.deepcopy(o)
 if oid in ids:
  e=z.pop('current_series_optionality_policy');check(e['option_id']==oid and e['source_sha256']==sha(e['source_receipt']),'Exact owner receipt '+oid)
  z['photo_coverage']['series']=b['photo_coverage']['series'];rv=z['current_photo_task_review'];check(rv['historical_policy_superseded_roles'][-1]['before']==b['current_photo_task_review']['roles']['series'],'Original role history '+oid);rv['roles']['series']=b['current_photo_task_review']['roles']['series']
  if 'historical_policy_superseded_roles'in b['current_photo_task_review']:rv['historical_policy_superseded_roles']=b['current_photo_task_review']['historical_policy_superseded_roles']
  else:rv.pop('historical_policy_superseded_roles')
 changes=diff(z,b,'/options/'+str(i));check(all(p.lstrip('/')in navpaths for p in changes),'Only authorized Series policy or current navigation '+oid)
 check(o['master_fields']==b['master_fields']and o['specifications']==b['specifications']and o['selling_details']==b['selling_details'],'All physical/commercial/source fields intact '+oid)
 check(all(o.get(k)==b.get(k)for k in ['file_id','folder_id','context_file_id','series_file_id','series_folder_id','confirmed_arrangement_ids','canonical_component_id','sale_unit']),'Every existing identity/role/arrangement binding intact '+oid)
 z=copy.deepcopy(c)
 if oid in ids:
  check(c['series']['status']=='Optional / no fixed set'and c['series']['reference']is None and not c['series_required'],'Optional requirement without new photo '+oid)
  check(c['historical_series_requirement_revisions'][-1]['prior_series']==bc['series'],'Prior Series coverage retained '+oid)
  z.pop('historical_series_requirement_revisions');z['series']=bc['series'];z['series_required']=bc['series_required'];z['owner_review']=bc['owner_review']
 check(all(p.lstrip('/')in navpaths for p in diff(z,bc,'/audit/coverage/'+str(i))),'Every coverage role and qualification retained '+oid)
for i,(t,b)in enumerate(zip(a['missing_pictures'],before['missing_pictures'])):
 z=copy.deepcopy(t)
 if t['option_id']in ids and t['role']=='Series':
  check(t['historical_owner_policy_actions'][-1]['before']==b,'Prior capture task retained '+t['option_id']);z.pop('historical_owner_policy_actions');z.pop('owner_series_policy')
  for k in ['action_type','status','action','owner_response','terminal_review_state','qualification']:z[k]=b[k]
 check(all(p.lstrip('/')in navpaths for p in diff(z,b,'/audit/missing_pictures/'+str(i))),'Unrelated task state preserved '+t['option_id']+' '+t['role'])
check(a['counts']==before['counts'],'All current photo requirement counts unchanged')
for oid in ['BSI-096BA2E00517','BSI-6E9202BEAD51']:
 o=next(o for o in g['options']if o['product_id']==oid);check(o['current_series_optionality_policy']['fixed_companion_set_existence_confirmed']is False and 'does not confirm'in o['current_photo_task_review']['roles']['series']['finding'],'Photo optional does not infer absent companion set '+oid)
o=next(o for o in g['options']if o['product_id']=='BSI-0D80125C0E35');check('remain possible'in o['current_photo_task_review']['roles']['series']['finding'],'Verdigris individual sale retains optional combinations')
oldnative=read(m['native_map']['snapshot']);native=read(H/'current-native-reference-map.json');oldassets=read(m['report_assets']['snapshot']);assets=read(H/'current-assets.json');overlay=read(m['battersea_overlay']['snapshot']);allids={x['file_id']for x in overlay['objects']};rootid=overlay['preserved_scope_roots'][0]['file_id']
check({k:v for k,v in native['current_objects'].items()if k not in allids|{rootid}}=={k:v for k,v in oldnative['current_objects'].items()if k not in allids|{rootid}},'All unrelated native map objects identical')
check(set(assets)==set(oldassets),'No new image asset or source identifier')
changed=proj['changed_native_objects'];filechanges={i for i,o in changed.items()if o['object_type']=='file'}
check(len(filechanges)==7 and sum(changed[i]['old_parent_id']!=changed[i]['current_parent_id']for i in filechanges)==7,'7 file paths7 actual parents')
for i,v in oldassets.items():
 if i not in filechanges:check(assets[i]==v,'Unrelated asset unchanged '+i)
 else:
  n=assets[i];o=changed[i];check(n['path']=='ns:202238505/'+o['current_path'] and n['folder_id']==o['current_parent_id'] and n['name']==v['name']and n['bytes']==v['bytes'],'Exact current path/parent and stable original '+i)
for o in overlay['objects']:
 n=native['current_objects'][o['file_id']];check(n['path']=='ns:202238505/'+o['current_path']and n['parent_id']==o['current_parent_id'],'Scoped native object exact '+o['file_id'])
state=read(H/'guided-owner-review-state.json');check(len(state['queues']['series'])==0 and len(state['queues']['individual'])==1 and len(state['held_in_situ_ids'])==22 and state['held_series_ids']==['BSI-C3573D23A4B7'],'0Series+1individual with all holds retained')
rows=[json.loads(s)for s in subprocess.check_output(['python3',str(H/'guided_review.py'),'--list'],text=True).splitlines()if s];check(len(rows)==1 and sum(r['role']=='Series'for r in rows)==0,'Actual terminal reader emits1 active source cases')
rep=read(H/'report-verification.json');out=Path(rep['output_directory'])
for file,num in [('Active_Series_Photographs_Required_0.csv',0),('Missing_Pictures_Required.csv',25),('Missing_Series_Images.csv',1),('Optional_Series_Images.csv',70),('Physical_Verification_Input_188_Options.csv',188),('Current_Individual_Options_188.csv',188)]:
 with(out/file).open(encoding='utf-8-sig',newline='')as f:rs=list(csv.DictReader(f))
 check(len(rs)==num,'Current exported list population '+file)
count=read(out/'current-count-summary.json');check(count['current_option_list']['rows']==188 and sha(count['current_option_list']['path'])==count['current_option_list']['sha256'],'Current count CSV pointer refreshed')
for x in rep['pages']+rep['csv_files']+rep['thumbnail_files']:check(sha(x['path'])==x['sha256'],'Current report bytes '+Path(x['path']).name)
for key,x in m.items():check(sha(x['path'])==sha(x['snapshot'])==x['sha256'],'Frozen input '+key)
r={'status':'FAIL'if issues else'PASS','recorded_utc':datetime.now(timezone.utc).isoformat(),'checks':checks,'issues':issues,'workbook_sha256':sha(H/'master-workbook.pending'),'register_sha256':sha(H/'canonical-master-register.json'),'audit_sha256':sha(H/'image-coverage-current.json'),'current_options':188,'retained_options':189,'active_series':0,'active_individual_source_cases':1,'held_series':1,'held_context':22,'required_picture_actions':25,'new_owner_optional_policies':0,'current_file_paths':7,'actual_file_parent_changes':7,'new_photo_bindings':0,'new_physical_verifications':0,'native_or_platform_writes':0}
(H/'native-binding-verification.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:r[k]for k in ['status','checks','issues']}));raise SystemExit(bool(issues))
