"""Check the global hold changes prompting only, preserving all catalogue evidence."""
import copy,csv,hashlib,json,subprocess
from pathlib import Path
from datetime import datetime,timezone
H=Path(__file__).resolve().parent;B=H.parents[2]
read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
g=read(H/'canonical-master-register.json');old=read(H/'inputs/master_register.before');a=read(H/'image-coverage-current.json');before=read(H/'inputs/audit.before');state=read(H/'guided-owner-review-state.json');event=read(H/'global-owner-context-hold.json');held=set(event['all_held_option_ids']);issues=[];checks=0
def check(ok,label):
 global checks
 checks+=1
 if not ok:issues.append(label)
check(len(held)==22 and not state['queues']['in_situ']and set(state['held_in_situ_ids'])==held,'All22 missing context cases held;0 active')
check(state['queues']['series']==read(H/'inputs/review_state.before')['queues']['series']and len(state['queues']['series'])==17,'All17 separate series requests unchanged')
check(g['summary']==old['summary']and len(g['options'])==188 and len(g['active_option_ids'])==187,'187 active188 retained count and definitions preserved')
for key in ['components','original_review_specification_assertions','source_only_assertions_not_applied_to_options','source_sets','aliases','source_offer_edges','source_media_configuration_coverage','current_frozen_fish_size_policy','wall_sculpture_customisation_policy','source_platform_offer_coverage','retired_option_ids']:
 check(g[key]==old[key],'Immutable source/policy '+key)
for o,b,c,bc in zip(g['options'],old['options'],a['coverage'],before['coverage']):
 oid=o['product_id'];check(oid==b['product_id']==c['option_id']==bc['option_id'],'Stable option row '+oid)
 z=copy.deepcopy(o)
 if oid in held:check(z.pop('current_global_context_owner_hold')['source_sha256']==event['source_sha256'],'Correct global hold authority '+oid)
 check(z==b,'All existing option identity/specifications/native refs/primary preserved '+oid)
 z=copy.deepcopy(c)
 if oid in held:z['in_situ'].pop('global_owner_deferral');z['owner_review']=bc['owner_review']
 check(z==bc,'All coverage bindings/statuses unchanged except context hold metadata '+oid)
 check(c['individual']==bc['individual']and c['series']==bc['series'],'Individual and series role unchanged '+oid)
check(a['counts']==before['counts']and a['counts']['required_picture_actions']==40,'40 diagnostic gaps and all role totals unchanged')
for t,b in zip(a['missing_pictures'],before['missing_pictures']):
 z=copy.deepcopy(t)
 if t['role']=='In situ'and t['option_id']in held:z.pop('global_owner_deferral');z['owner_response']=b['owner_response']
 check(z==b,'Action unchanged except scoped context hold '+t['option_id']+' '+t['role'])
for name,key in [('current-native-reference-map.json','native_map'),('current-assets.json','report_assets')]:check(sha(H/name)==read(H/'input-manifest.json')[key]['sha256'],'Native metadata byte-identical; no new path projection '+name)
runtime=subprocess.run(['python3',str(H/'guided_review.py'),'--list'],check=True,capture_output=True,text=True);rows=[json.loads(x)for x in runtime.stdout.splitlines()if x]
check(len(rows)==17 and all(x['role']=='Series'for x in rows),'Actual terminal emits17 Series and no context prompts')
check({x['option_id']for x in rows}==set(state['queues']['series']),'Actual terminal matches canonical series queue exactly')
opts={o['product_id']:o for o in g['options']}
for row in rows:
 o=opts[row['option_id']];check(all(row[k]==o[z]for k,z in [('image','image_url'),('folder','folder_url'),('file_id','file_id'),('folder_id','folder_id')]),'Terminal uses exact current primary and actual parent '+row['option_id'])
check(any(x['option_id']=='BSI-3635E3DC3434'for x in rows),'Pewter series remains active while context is held')
report=read(H/'report-verification.json');out=Path(report['output_directory']);brief=read(out/'remaining-photograph-requests.json')
check(brief['counts']['display_context']==0 and brief['counts']['series']==17 and brief['counts']['held_context_cases_excluded']==22,'Public request brief active/held counts correct')
check(len(brief['requests'])==17 and all(x['missing_roles']==['Series']for x in brief['requests']),'Public capture brief is series-only')
for name,count in [('Active_In_Situ_Photographs_Required_0.csv',0),('Held_In_Situ_Cases_22.csv',22),('Missing_Pictures_Required.csv',40),('Missing_Series_Images.csv',17)]:
 with (out/name).open(encoding='utf-8-sig',newline='')as f:rs=list(csv.DictReader(f))
 check(len(rs)==count,'CSV current counts '+name)
 if count==22:check({x['option_id']for x in rs}==held,'Held CSV has exact22 owner-held IDs')
sourceout=Path(read(H/'inputs/source_report_verification.before')['output_directory'])
check(sha(out/'Physical_Verification_Input_187_Options.csv')==sha(sourceout/'Physical_Verification_Input_187_Options.csv'),'No physical measurement input changed')
check(sha(out/'Current_Individual_Options_187.csv')==sha(sourceout/'Current_Individual_Options_187.csv'),'Individual catalogue CSV values preserved')
for item in report['pages']+report['csv_files']+report['thumbnail_files']:check(sha(item['path'])==item['sha256'],'Bound review artifact '+Path(item['path']).name)
for item in read(H/'input-manifest.json').values():check(sha(item['path'])==sha(item['snapshot'])==item['sha256'],'Frozen input unchanged '+Path(item['path']).name)
result={'status':'FAIL'if issues else'PASS','recorded_utc':datetime.now(timezone.utc).isoformat(),'checks':checks,'issues':issues,'workbook_sha256':sha(H/'master-workbook.pending'),'register_sha256':sha(H/'canonical-master-register.json'),'audit_sha256':sha(H/'image-coverage-current.json'),'active_context':0,'held_context':22,'series':17,'gaps_closed':0,'all_individual_and_series_bindings_unchanged':True,'all_physical_fields_unchanged':True,'actual_terminal_script_sha256':sha(H/'guided_review.py'),'actual_terminal_rows':len(rows),'new_native_or_platform_writes':0}
(H/'native-binding-verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:result[k]for k in ['status','checks','issues','actual_terminal_rows']}));raise SystemExit(bool(issues))
