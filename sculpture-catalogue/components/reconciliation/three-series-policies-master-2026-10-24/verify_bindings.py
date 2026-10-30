"""Independently check that only the three precise Series policies changed."""
import copy,csv,hashlib,json,subprocess
from pathlib import Path
from datetime import datetime,timezone
H=Path(__file__).resolve().parent;B=H.parents[2];read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();g=read(H/'canonical-master-register.json');old=read(H/'inputs/master_register.before');a=read(H/'image-coverage-current.json');before=read(H/'inputs/audit.before');m=read(H/'input-manifest.json');ids=set(read(H/'projection-index.json')['option_ids']);issues=[];checks=0
def check(ok,label):
 global checks
 checks+=1
 if not ok:issues.append(label)
check(g['summary']==old['summary']and len(g['active_option_ids'])==188 and len(g['options'])==189 and len(g['components'])==112,'Current188 active189 retained112 identities unchanged')
for key in ['components','active_option_ids','retired_option_ids','arrangement_context_references','confirmed_arrangement_member_edges','original_review_specification_assertions','source_sets','source_offer_edges','aliases','current_frozen_fish_size_policy','wall_sculpture_customisation_policy','source_platform_offer_coverage','current_structure_discovery_scope','current_wall_sculpture_inclusion_policy']:check(g[key]==old[key],'Preserved current source, membership or policy '+key)
for o,b,c,bc in zip(g['options'],old['options'],a['coverage'],before['coverage']):
 oid=o['product_id'];z=copy.deepcopy(o)
 if oid in ids:
  event=z.pop('current_series_optionality_policy');check(event['option_id']==oid and event['source_sha256']==sha(event['source_receipt']),'Exact owner source '+oid);z['photo_coverage']['series']=b['photo_coverage']['series'];review=z['current_photo_task_review'];check(review['historical_policy_superseded_roles'][-1]['before']==b['current_photo_task_review']['roles']['series'],'Prior role history exact '+oid);review['roles']['series']=b['current_photo_task_review']['roles']['series']
  if 'historical_policy_superseded_roles'in b['current_photo_task_review']:review['historical_policy_superseded_roles']=b['current_photo_task_review']['historical_policy_superseded_roles']
  else:review.pop('historical_policy_superseded_roles')
 check(z==b,'Every option field preserved outside exact Series policy '+oid)
 z=copy.deepcopy(c)
 if oid in ids:
  check(c['series']['status']=='Optional / no fixed set'and c['series']['reference']is None and not c['series_required'],'Optional requirement without new photograph '+oid);check(c['historical_series_requirement_revisions'][-1]['prior_series']==bc['series'],'Exact prior Series coverage retained '+oid);z.pop('historical_series_requirement_revisions');z['series']=bc['series'];z['series_required']=bc['series_required'];z['owner_review']=bc['owner_review']
 check(z==bc,'All primary/context source bindings and full role data retained '+oid)
check(next(o for o in g['options']if o['product_id']=='BSI-C3AA3700F7DA')==next(o for o in old['options']if o['product_id']=='BSI-C3AA3700F7DA'),'New water-build product entirely unchanged by policy import')
for t,b in zip(a['missing_pictures'],before['missing_pictures']):
 z=copy.deepcopy(t)
 if t['option_id']in ids and t['role']=='Series':
  check(t['historical_owner_policy_actions'][0]['before']==b,'Prior exact capture task retained '+t['option_id']);z.pop('historical_owner_policy_actions');z.pop('owner_series_policy')
  for k in ['action_type','status','action','owner_response','terminal_review_state','qualification']:z[k]=b[k]
 check(z==b,'All unrelated photograph tasks retained '+t['option_id']+' '+t['role'])
expected=copy.deepcopy(before['counts']);expected['series_statuses']['No verified image']-=3;expected['series_statuses']['Optional / no fixed set']+=3;expected['series_required_options']-=3;expected['actions_by_type']['Find / capture']-=3;expected['actions_by_type']['Optional image']+=3;expected['required_picture_actions']-=3;check(a['counts']==expected,'Only three current requirement classifications change aggregates')
gold=next(o for o in g['options']if o['product_id']=='BSI-0922347CC6AE')['current_series_optionality_policy'];check(gold['owner_text']=='At the moment, yes'and'revisit'in gold['temporal_qualification'].lower(),'Gold current/at-the-moment condition retained')
for file,key in [('current-native-reference-map.json','native_map'),('current-assets.json','report_assets'),('pending-followups.json','pending')]:check(sha(H/file)==m[key]['sha256'],'Native identities/assets/pending proposals byte-identical '+file)
state=read(H/'guided-owner-review-state.json');check(len(state['queues']['series'])==12 and len(state['queues']['individual'])==1 and len(state['held_in_situ_ids'])==22 and state['held_series_ids']==['BSI-C3573D23A4B7'],'Current queue12Series+1individual with all holds preserved');rows=[json.loads(s)for s in subprocess.check_output(['python3',str(H/'guided_review.py'),'--list'],text=True).splitlines()if s];check(len(rows)==13 and sum(r['role']=='Series'for r in rows)==12,'Actual terminal reader emits exactly13 active source cases')
rep=read(H/'report-verification.json');out=Path(rep['output_directory'])
for file,num in [('Active_Series_Photographs_Required_12.csv',12),('Missing_Pictures_Required.csv',37),('Missing_Series_Images.csv',13),('Optional_Series_Images.csv',58),('Physical_Verification_Input_188_Options.csv',188)]:
 with(out/file).open(encoding='utf-8-sig',newline='')as f:rs=list(csv.DictReader(f))
 check(len(rs)==num,'Current derived list population '+file)
for x in rep['pages']+rep['csv_files']+rep['thumbnail_files']:check(sha(x['path'])==x['sha256'],'Current report bytes '+Path(x['path']).name)
for key,x in m.items():check(sha(x['path'])==sha(x['snapshot'])==x['sha256'],'Frozen source CAS '+key)
r={'status':'FAIL'if issues else'PASS','recorded_utc':datetime.now(timezone.utc).isoformat(),'checks':checks,'issues':issues,'workbook_sha256':sha(H/'master-workbook.pending'),'register_sha256':sha(H/'canonical-master-register.json'),'audit_sha256':sha(H/'image-coverage-current.json'),'current_options':188,'retained_options':189,'active_series':12,'active_individual_source_cases':1,'held_series':1,'held_context':22,'required_picture_actions':37,'new_owner_optional_policies':3,'new_photo_bindings':0,'new_physical_verifications':0,'native_or_platform_writes':0};(H/'native-binding-verification.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:r[k]for k in ['status','checks','issues']}));raise SystemExit(bool(issues))
