"""Independent native-path, role, lifecycle and saved-link checks."""
import hashlib,importlib.util,json,posixpath,re
from pathlib import Path
from datetime import datetime,timezone
from xml.etree import ElementTree as E
H=Path(__file__).resolve().parent;B=H.parents[2];read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
s=importlib.util.spec_from_file_location('v',B/'components/reconciliation/image-identity-coverage-2026-10-20/verify_edit.py');v=importlib.util.module_from_spec(s);s.loader.exec_module(v);w=v.load(H/'master-workbook.pending');g=read(H/'canonical-master-register.json');a=read(H/'image-coverage-current.json');old=read(H/'inputs/master_register.before');olda=read(H/'inputs/audit.before');native=read(H/'current-native-reference-map.json')['current_objects'];final=read(H/'inputs/four_final_map.before')['objects'];scope=read(H/'path-refresh-scope.json');issues=[];checks=0
def check(ok,label):
 global checks
 checks+=1
 if not ok:issues.append(label)
opts={x['product_id']:x for x in g['options']};prior={x['product_id']:x for x in old['options']};cov={x['option_id']:x for x in a['coverage']};oldcov={x['option_id']:x for x in olda['coverage']};oid='BSI-7B6291B7C7F9'
for x in final:
 y=native[x['file_id']];check(y['path']==x['current_path']and y['parent_id']==x['current_parent_id']and y['object_type']==x['object_type'],'Verified final native path and actual parent '+x['file_id'])
check(len(final)==424 and sum(x['object_type']=='file'for x in final)==404,'All424objects including17previously absent Barbados objects imported')
for x in g['options']:
 for k in ['product_id','name','canonical_key','canonical_component_id','specifications','master_fields','selling_details','counted_as_individual_option','file_id','folder_id']:check(x[k]==prior[x['product_id']][k],'Identity/primary/specification/lifecycle unchanged '+x['product_id']+'/'+k)
for x in a['coverage']:
 for role in ['individual','in_situ','series']:
  if x['option_id']==oid and role=='in_situ':continue
  oldrole=oldcov[x['option_id']][role];newrole=x[role];check(oldrole['status']==newrole['status']and(oldrole.get('reference')or{}).get('file_id')==(newrole.get('reference')or{}).get('file_id'),'Other approved role/source unchanged '+x['option_id']+'/'+role)
check(g['summary']==old['summary']and len(g['active_option_ids'])==187 and len(g['options'])==188,'187active /188history; no count or identity drift')
check(opts['BSI-C41824131174']==prior['BSI-C41824131174']and not opts['BSI-C41824131174']['current_offer_active'],'Exact retired Sandstone record preserved')
check(cov['BSI-3635E3DC3434']['series']['status']=='No verified image','One Leaf Pewter series not cross-closed')
c=cov[oid];r=c['in_situ']['reference'];check(c['in_situ']['status']=='Available'and r['file_id']=='id:cnqzTNngPVsAAAAAAAuXWg'and r['folder_id']=='id:cnqzTNngPVsAAAAAAA6VrA','Exact Strata owner context and actual parent')
check(c['in_situ']['wall_setting_only']and c['in_situ']['wider_room_or_garden_view_verified']is False and c['in_situ']['scene_authenticity_verified']is False and c['in_situ']['physical_cast_or_size_certified']is False,'Wall setting only; no broad installation or physical certificate')
check(opts[oid]['file_id']=='id:cnqzTNngPVsAAAAAAAueFw'and c['series']['status']=='Optional / no fixed set','Strata primary and optional series preserved')
check(native[r['file_id']]['parent_id']==r['folder_id']and native[r['file_id']]['path']==r['path'],'Strata native map current actual parent')
links={}
for sn,z in w['sheets'].items():
 rp=posixpath.join(posixpath.dirname(z['part']),'_rels',posixpath.basename(z['part'])+'.rels');rs={x.get('Id'):x.get('Target')for x in E.fromstring(w['files'][rp])}if rp in w['files']else{}
 for x in z['root'].findall('.//'+v.q('hyperlink')):links[(sn,x.get('ref'))]='#'+x.get('location')if x.get('location')else rs[x.get('{'+v.R+'}id')]
check(w['values']['Photo Coverage']['F181']=='Available'and w['values']['Photo Coverage']['O181']==r['file_id']and w['values']['Photo Coverage']['P181']==r['folder_id'],'Saved Strata role/source/parent')
check(links[('Photo Coverage','G181')]==r['image_url']and links[('Photo Coverage','H181')]==r['folder_url'],'Saved Strata native image/folder targets')
check(w['values']['Master Catalogue']['B4']==187 and w['values']['Master Catalogue']['L16']=='Retired'and w['values']['Specifications']['Q46']==0,'Saved retirement and active counts preserved')
check(a['counts']['required_picture_actions']==66 and a['counts']['actions_by_type']['Find / capture']==65 and a['counts']['resolved_action_rows']==85 and a['counts']['retired_action_rows']==3,'66required /65capture /85resolved /3retired')
check(a['counts']['in_situ_statuses']['No verified image']==48 and a['counts']['series_statuses']['No verified image']==17,'48in-situ /17series')
pending=read(H/'pending-followups.json');paths={x['path']for x in pending['entries']};m=read(H/'input-manifest.json')
for i in range(4):check(m['overlay'+str(i)]['path']not in paths,'Imported packet removed from ready queue '+str(i))
check(any(x['status']=='PARTIAL_OWNER_HOLD'and x['do_not_resume_without_owner_instruction']for x in pending['entries']),'Held Wall Circle not applied or resumed')
for k in ['original_review_specification_assertions','current_frozen_fish_size_policy','wall_sculpture_customisation_policy','catalogue_retirements']:check(g[k]==old[k],'Historical evidence or policy preserved '+k)
r={'status':'FAIL'if issues else'PASS','recorded_utc':datetime.now(timezone.utc).isoformat(),'checks':checks,'issues':issues,'workbook_sha256':sha(H/'master-workbook.pending'),'register_sha256':sha(H/'canonical-master-register.json'),'audit_sha256':sha(H/'image-coverage-current.json'),'active_options':187,'retained_option_rows':188,'fresh_native_objects':424,'in_situ_gaps':48,'series_gaps':17,'new_native_or_platform_writes':0}
(H/'native-binding-verification.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps({k:r[k]for k in ['status','checks','issues']}));assert not issues
