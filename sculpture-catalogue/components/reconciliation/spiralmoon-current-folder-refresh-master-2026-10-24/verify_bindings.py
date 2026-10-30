"""Check the entire saved data scope against the frozen navigation-only baseline."""
import copy,csv,hashlib,json,subprocess
from pathlib import Path
from datetime import datetime,timezone
H=Path(__file__).resolve().parent;B=H.parents[2]
read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
g=read(H/'canonical-master-register.json');old=read(H/'inputs/master_register.before');a=read(H/'image-coverage-current.json');before=read(H/'inputs/audit.before');m=read(H/'input-manifest.json');proj=read(H/'projection-index.json');nav=set(proj['current_reference_fields']);issues=[];checks=0
def check(ok,label):
 global checks
 checks+=1
 if not ok:issues.append(label)
def diff(x,y,path=''):
 if type(x)!=type(y):return[path]
 if isinstance(x,dict):
  if x.keys()!=y.keys():return[path+'/@keys']
  return[p for k in x for p in diff(x[k],y[k],path+'/'+str(k))]
 if isinstance(x,list):
  if len(x)!=len(y):return[path+'/@length']
  return[p for i,(v,z)in enumerate(zip(x,y))for p in diff(v,z,path+'/'+str(i))]
 return[]if x==y else[path]
z=copy.deepcopy(g);z.pop('latest_spiralmoon_native_navigation_import');z['latest_active_photo_source_review']=old['latest_active_photo_source_review'];z['latest_image_coverage_audit']=old['latest_image_coverage_audit']
changes=diff(z,old);check(all(p.lstrip('/')in nav for p in changes),'Whole canonical register: only declared current navigation and dated import metadata changed')
check(all(p.lstrip('/')in nav for p in diff(a,before,'/audit')),'Whole coverage audit: only declared navigation changed')
check(g['summary']==old['summary']and len(g['active_option_ids'])==188 and len(g['options'])==189 and len(g['components'])==112,'188 active,189 retained,112 component identities unchanged')
for o,b in zip(g['options'],old['options']):
 check(o['master_fields']==b['master_fields']and o['specifications']==b['specifications']and o['selling_details']==b['selling_details'],'All six working and historical specification objects unchanged '+o['product_id'])
 check(all(o.get(k)==b.get(k)for k in ['file_id','context_file_id','series_file_id','confirmed_arrangement_ids','canonical_component_id','canonical_key','sale_unit','physical_specifications_verified']),'Selected file identities, role bindings, sale unit and physical status unchanged '+o['product_id'])
check(a['counts']==before['counts'],'Every photograph requirement counter unchanged')
check(g['current_individual_photo_capture_policy']==a['current_individual_photo_capture_policy']==old['current_individual_photo_capture_policy'],'Current capture policy mirrors exact')
overlay=read(m['spiralmoon_overlay']['snapshot']);allids={x['file_id']for x in overlay['objects']};rootid=overlay['preserved_scope_roots'][0]['file_id'];native=read(H/'current-native-reference-map.json');oldnative=read(m['native_map']['snapshot']);assets=read(H/'current-assets.json');oldassets=read(m['report_assets']['snapshot']);changed=proj['changed_native_objects']
check({k:v for k,v in native['current_objects'].items()if k not in allids|{rootid}}=={k:v for k,v in oldnative['current_objects'].items()if k not in allids|{rootid}},'All unrelated native map objects identical')
check(set(assets)==set(oldassets),'No image source identifier added or removed')
check(len(changed)==27 and all(o['object_type']=='file'and o['old_parent_id']=='id:cnqzTNngPVsAAAAAAAyjDQ'and o['current_parent_id']=='id:cnqzTNngPVsAAAAAAAyjFg'for o in changed.values()),'Exactly27 approved same-ID file paths and actual parent changes')
repairs=read(H/'auxiliary-current-asset-navigation-repairs.json');repairids={x['file_id']for x in repairs}
check(len(repairs)==4 and repairids=={'id:cnqzTNngPVsAAAAAAA51Dg','id:cnqzTNngPVsAAAAAAA52wA'},'Exactly four inherited auxiliary path fields repaired from sealed scope')
for i,v in oldassets.items():
 if i not in changed:
  expected=copy.deepcopy(v)
  for x in repairs:
   if x['file_id']==i:check(expected.get(x['field'])==x['before'],'Auxiliary source field exact '+i+' '+x['field']);expected[x['field']]=x['current']
  check(assets[i]==expected,'Unrelated asset or exact scoped auxiliary navigation repair '+i)
 else:
  cur=assets[i];obj=changed[i];check(cur['path']=='ns:202238505/'+obj['current_path']and cur['folder_id']==obj['current_parent_id']and cur['name']==v['name']and cur['bytes']==v['bytes'],'Exact current asset path/parent and stable original '+i)
for obj in overlay['objects']:
 cur=native['current_objects'][obj['file_id']];check(cur['path']=='ns:202238505/'+obj['current_path']and cur['parent_id']==obj['current_parent_id'],'Scoped native object '+obj['file_id'])
 if obj['object_type']=='file'and obj['file_id']in assets:
  asset=assets[obj['file_id']];check(asset['display_path']==obj['current_path']and asset['folder_path']=='ns:202238505/'+obj['current_path'].rsplit('/',1)[0],'All scoped auxiliary current paths exact '+obj['file_id'])
o=next(o for o in g['options']if o['product_id']=='BSI-10BFED6B265B');check(o['file_id']=='id:cnqzTNngPVsAAAAAAAuXEw'and o['folder_id']=='id:cnqzTNngPVsAAAAAAAyjFg'and '/Spiralmoon%201%20White%20In%20Situ/'in o['image_url']and o['folder_url'].endswith('Spiralmoon%201%20White%20In%20Situ'),'Selected011.JPG same file and actual new containing folder')
check(o['context_file_id']=='id:cnqzTNngPVsAAAAAAArqFA'and o['context_folder_id']=='id:cnqzTNngPVsAAAAAAAyjFg','Existing selected context remains unchanged')
state=read(H/'guided-owner-review-state.json');check(state==read(m['review_state']['snapshot']),'Owner review state and all holds unchanged')
source=read(H/'photo-source-review.json');check(source['requests']==[]and source['role_counts']=={'Individual':0,'Display/context':0,'Series':0},'No active source requests resurrected')
rows=subprocess.check_output(['python3',str(H/'guided_review.py'),'--list'],text=True);check(not rows.strip(),'Actual terminal reader emits no active question')
rep=read(H/'report-verification.json');out=Path(rep['output_directory']);oldout=Path(read(m['source_report_verification']['snapshot'])['output_directory'])
allowed_cols={'image_url','folder_url','individual_image','containing_folder','folder_id'}
for f in rep['csv_files']:
 p=Path(f['path'])
 with p.open(encoding='utf-8-sig',newline='')as h:cur=list(csv.DictReader(h))
 with(oldout/p.name).open(encoding='utf-8-sig',newline='')as h:prior=list(csv.DictReader(h))
 check(len(cur)==len(prior),'CSV population preserved '+p.name)
 for j,(row,b)in enumerate(zip(cur,prior)):
  edits={k for k in row if row[k]!=b[k]};check(not edits or b.get('file_id')in changed and edits<=allowed_cols,'CSV only same-file current navigation '+p.name+' '+str(j))
for file,num in [('Active_Series_Photographs_Required_0.csv',0),('Missing_Pictures_Required.csv',24),('Missing_Series_Images.csv',1),('Optional_Series_Images.csv',70),('Physical_Verification_Input_188_Options.csv',188),('Current_Individual_Options_188.csv',188)]:
 with(out/file).open(encoding='utf-8-sig',newline='')as h:check(len(list(csv.DictReader(h)))==num,'Current exported list '+file)
for x in rep['pages']+rep['csv_files']+rep['thumbnail_files']:check(sha(x['path'])==x['sha256'],'Report bytes '+Path(x['path']).name)
for key,x in m.items():check(sha(x['path'])==sha(x['snapshot'])==x['sha256'],'Frozen source '+key)
r={'status':'FAIL'if issues else'PASS','recorded_utc':datetime.now(timezone.utc).isoformat(),'checks':checks,'issues':issues,'workbook_sha256':sha(H/'master-workbook.pending'),'register_sha256':sha(H/'canonical-master-register.json'),'audit_sha256':sha(H/'image-coverage-current.json'),'current_options':188,'retained_options':189,'active_photograph_requests':0,'held_series':1,'held_context':22,'required_picture_actions':24,'current_file_paths':27,'actual_file_parent_changes':27,'new_photo_bindings':0,'new_physical_verifications':0,'native_or_platform_writes':0};(H/'native-binding-verification.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps({k:r[k]for k in ['status','checks','issues']}));raise SystemExit(bool(issues))
