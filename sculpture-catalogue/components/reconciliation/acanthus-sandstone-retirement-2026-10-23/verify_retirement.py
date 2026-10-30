"""Independent lifecycle, saved-native, history and active-export checks."""
import csv,hashlib,importlib.util,json,re
from pathlib import Path
from datetime import datetime,timezone
H=Path(__file__).resolve().parent;B=H.parents[2];read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
s=importlib.util.spec_from_file_location('v',B/'components/reconciliation/image-identity-coverage-2026-10-20/verify_edit.py');v=importlib.util.module_from_spec(s);s.loader.exec_module(v);w=v.load(H/'master-workbook.pending');g=read(H/'canonical-master-register.json');a=read(H/'image-coverage-current.json');old=read(H/'inputs/master_register.before');olda=read(H/'inputs/audit.before');oid='BSI-C41824131174';issues=[];checks=0
def check(ok,label):
 global checks
 checks+=1
 if not ok:issues.append(label)
opts={x['product_id']:x for x in g['options']};prior={x['product_id']:x for x in old['options']};cov={x['option_id']:x for x in a['coverage']};priorcov={x['option_id']:x for x in olda['coverage']};o=opts[oid]
check(len(g['options'])==188 and len(g['active_option_ids'])==187 and g['retired_option_ids']==[oid],'188retained /187active /one exact retired option')
check(o['catalogue_status']=='Retired'and o['counted_as_individual_option']is False and o['current_offer_active']is False and o['current_measurement_required']is False,'Retired and no active offer or measurement')
for x in g['options']:
 if x['product_id']!=oid:check(x==prior[x['product_id']],'Unrelated option preserved in full '+x['product_id'])
 for key in ['product_id','name','canonical_key','canonical_component_id','specifications','master_fields','selling_details','file_id','folder_id','image_url','folder_url']:check(x[key]==prior[x['product_id']][key],'Historical identity/specification/source preserved '+x['product_id']+'/'+key)
for c in g['components']:
 before=next(x for x in old['components']if x['component_id']==c['component_id'])
 if c['component_id']!='BC-AC-ONE':check(c==before,'Unrelated component preserved '+c['component_id'])
 else:check(c['option_count']==2 and oid not in c['option_ids']and c['retired_option_ids']==[oid]and c['historical_option_members_before_retirement']['option_ids']==before['option_ids'],'One Leaf component active finishes and history')
check(read(H/'retired-option-history.json')['complete_option_before_retirement']==prior[oid],'Full original option retained in retirement history')
for key in ['original_review_specification_assertions','source_platform_offer_coverage','source_offer_edges','current_frozen_fish_size_policy','wall_sculpture_customisation_policy']:check(g[key]==old[key],'Unchanged history/policy '+key)
for k,c in cov.items():
 if k!=oid:check(c==priorcov[k],'Unrelated photograph coverage unchanged '+k)
for x,y in zip(a['missing_pictures'],olda['missing_pictures']):
 if x['option_id']!=oid:check(x==y,'Unrelated photograph action unchanged '+x['option_id']+'/'+x['role'])
 else:check(x['status']=='Retired / not applicable'and x['resolution_kind']=='OWNER_RETIRED_NOT_A_PHOTO_RESOLUTION','Retired action is not counted as a found photograph '+x['role'])
check(all(cov[oid][r]['status']=='Retired / not applicable'for r in ['individual','in_situ','series']),'All three retired photo roles inactive')
counts=a['counts'];check((counts['individual_options'],counts['required_picture_actions'],counts['actions_by_type']['Find / capture'],counts['resolved_action_rows'],counts['retired_action_rows'])==(187,67,66,84,3),'Active and historical action totals')
check(counts['in_situ_statuses']['No verified image']==49 and counts['series_statuses']['No verified image']==17 and counts['separate_individual_photographs_required']==0,'49in-situ /17series /zero separate-photo capture requests')
check(cov['BSI-3635E3DC3434']['series']['status']=='No verified image','Pewter series not falsely closed')
for sheet,cell,expected in [('Master Catalogue','B4',187),('Master Catalogue','K16',0),('Master Catalogue','L16','Retired'),('Photo Coverage','B5',10),('Missing Pictures','B4',66),('Draft Listings','B4',100),('Draft Listings','Q12','Retired — do not create'),('Selling Details','D16','Retired — no longer exists')]:check(w['values'][sheet][cell]==expected,'Saved lifecycle result '+sheet+'!'+cell)
for row in range(46,52):check(w['values']['Specifications']['D'+str(row)]==v.load(H/'inputs/master_workbook.before')['values']['Specifications']['D'+str(row)]and w['values']['Specifications']['Q'+str(row)]==0,'Historical display retained and active usability disabled '+str(row))
for row in [13,39,163]:check(w['values']['Missing Pictures']['N'+str(row)]=='Retired / not applicable','Saved retired photo action '+str(row))
out=B/'outputs'/H.name
for filename,rows in [('Current_Individual_Options_187.csv',187),('Current_Selling_Details_187.csv',187),('Physical_Verification_Input_187_Options.csv',187),('Specification_Verification_Checklist_1122_Fields.csv',1122),('Missing_Pictures_Required.csv',67),('Missing_In_Situ_Images.csv',49),('Missing_Series_Images.csv',17),('Separate_Individual_Photographs_Required_0.csv',0)]:
 with(out/filename).open(encoding='utf-8-sig',newline='')as f:records=list(csv.DictReader(f))
 check(len(records)==rows and not any(x.get('option_id')==oid for x in records),'No retired option in active export '+filename)
check(sha(H/'current-native-reference-map.json')==read(H/'input-manifest.json')['native_map']['sha256'],'Native IDs and current paths unchanged')
r={'status':'FAIL'if issues else'PASS','recorded_utc':datetime.now(timezone.utc).isoformat(),'checks':checks,'issues':issues,'workbook_sha256':sha(H/'master-workbook.pending'),'register_sha256':sha(H/'canonical-master-register.json'),'audit_sha256':sha(H/'image-coverage-current.json'),'active_option_count':187,'retained_option_count':188,'retired_photo_tasks':3,'new_photographs_found':0,'new_physical_verifications':0,'native_or_platform_writes':0}
(H/'native-binding-verification.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps({k:r[k]for k in ['status','checks','issues']}));assert not issues
