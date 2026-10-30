"""Import one owner weight policy and scoped weight-only display overlays."""
import copy, hashlib, json, sys
from pathlib import Path
from datetime import datetime, timezone
from import_moonphase_silver_working_specs_62 import ROOT, PATHS, read, sha, rel, write, specification_counts

HERE=ROOT/'components/reviews/parallel-import-2026-10-19-batch90'
SOURCE=ROOT/'components/parallel-reviews/all-sculptures-weight-policy-2026-10-20'
PACKAGE_SHA='12d0554c351cf0037497241984cd2e69186404a2e508bd334dcee3e1d4e85e64'

def main():
 docs={k:read(v) for k,v in PATHS.items()};u,p,cp,c=(docs[k] for k in ['user','progress','walkthrough','component'])
 if (HERE/'import-receipt.json').exists():
  assert p['global_approximate_weight_policy']['policy_id'].endswith('LINE30053') and len(u['global_approximate_weight_policy_decisions'])==1
  print(json.dumps(dict(batch=90,status='ALREADY_IMPORTED_IDEMPOTENT_NO_WRITE')));return
 before=copy.deepcopy(docs);guards={k:sha(v) for k,v in PATHS.items()};assert cp['last_parallel_import']['batch']==89 and docs['root']['current_component_review']==c
 frozen=[];seen=set();historical=[]
 def freeze(path,digest):
  path=Path(path)
  if str(path).startswith(('ns:','id:','https:','/BOLDSTONE MASTER/')):return
  if path in PATHS.values():historical.append(dict(path=str(path),historical_sha256=digest));return
  assert sha(path)==digest,str(path)
  if (str(path),digest) in seen:return
  seen.add((str(path),digest));dest=HERE/'sources'/(digest+path.suffix);dest.parent.mkdir(parents=True,exist_ok=True)
  if dest.exists():assert sha(dest)==digest
  else:dest.write_bytes(path.read_bytes())
  frozen.append(dict(source=str(path),snapshot=rel(dest),sha256=digest))
  if path.suffix=='.json' and '/source-snapshots/' not in str(path):refs(read(path))
 def refs(value):
  if isinstance(value,dict):
   if isinstance(value.get('path'),str) and isinstance(value.get('sha256'),str):freeze(value['path'],value['sha256'])
   for v in value.values():refs(v)
  elif isinstance(value,list):
   for v in value:refs(v)
 package=SOURCE/'IMPORT_PACKAGE.json';freeze(package,PACKAGE_SHA);pkg=read(package)
 manifest=SOURCE/'SEALED_MANIFEST.json';freeze(manifest,sha(manifest))
 files=read(manifest)['files']
 if isinstance(files,dict):
  for name,digest in files.items():freeze(SOURCE/name,digest)
 else:refs(files)
 for name in ['current-reference-check.json','parent-image-check.json']:freeze(HERE/name,sha(HERE/name))
 policy=read(pkg['policy']['path']);ev=policy['authoritative_user_evidence'];raw=Path(ev['transcript']).read_bytes().splitlines(keepends=True)[ev['line']-1];assert hashlib.sha256(raw).hexdigest()==ev['raw_line_sha256']
 event=json.loads(raw);assert event['type']=='response_item' and event['payload']['role']=='user';text=''.join(x.get('text','') for x in event['payload']['content']);assert text==policy['user_statement']==ev['text']
 assert hashlib.sha256(text.encode()).hexdigest()==ev['text_sha256'];assert not u.get('global_approximate_weight_policy_decisions') and not p.get('global_approximate_weight_policy')
 estimates=read(pkg['new_estimates']['path'])['items'];recoveries=read(pkg['display_recoveries']['path'])['items'];overlays=read(pkg['proposed_weight_overlays']['path']);assert len(estimates)==9 and len(recoveries)==7 and len(overlays['rows'])==278
 overrides={};dispositions={};existing=[]
 for x in overlays['rows']:
  key=x['component_id']+'|'+x['scope']
  if x['disposition']=='EXISTING_SCOPED_APPROXIMATION_ACCEPTED':existing.append(key)
  elif x['disposition'] in ['NEW_CONDITIONAL_ESTIMATE_PREPARED','EXISTING_ESTIMATE_DISPLAY_RECOVERY']:overrides[key]=copy.deepcopy(x)
  else:dispositions[key]=copy.deepcopy(x)
 assert len(overrides)==16 and len(dispositions)==48 and len(existing)==214 and len(set(existing)|set(overrides)|set(dispositions))==278
 for x in estimates:assert not x['actual_weight_measured'] and not x['physical_specs_verified'] and not x['entire_set_mass_divided'] and not x['other_five_fields_changed'] and x['individual_owner_reply'] is None
 assert all(x['existing_value_recovered_not_new_estimate'] and not x.get('pair_weight_divided',False) for x in recoveries)
 now=datetime.now(timezone.utc).isoformat();approval=rel(HERE/'global-approximate-weight-policy.json');policy.update(approval_record=approval,root_verified_utc=now,shared_master_import_performed=True,working_acceptance_basis='ONE_GLOBAL_OWNER_INSTRUCTION;NOT_INDIVIDUAL_REPLIES')
 u.setdefault('global_approximate_weight_policy_decisions',[]).append(copy.deepcopy(policy));u.setdefault('conditional_weight_estimate_decisions',[]).extend(copy.deepcopy(estimates));u.setdefault('weight_display_recovery_records',[]).extend(copy.deepcopy(recoveries))
 for doc in [p,cp,c]:doc['global_approximate_weight_policy']=copy.deepcopy(policy)
 p['weight_review_output_overlays']=dict(policy_id=policy['policy_id'],approval_record=approval,source_package=rel(package),source_package_sha256=PACKAGE_SHA,scoped_overrides=overrides,reference_dispositions=dispositions,existing_numeric_scopes=existing,source_review_scope_count=278,new_conditional_estimates=9,recovered_existing_displays=7,counts_are_overlapping_review_scopes_not_unique_sculptures=True,retain_current_scope_values_from_later_imports=True,other_five_fields_changed=False,family_reference=read(pkg['coverage']['path'])['additional_family_catalogue_source'],current_native_metadata_exceptions=read(HERE/'current-reference-check.json')['current_native_file_access_exceptions'])
 for doc in [cp,c]:
  pending=doc.get('pending_owner_weight_instruction')
  if isinstance(pending,dict):pending.update(status='APPLIED_AS_WEIGHT_POLICY90;WORKBOOK_EXPORT_PENDING',policy_record=approval)
 summary=dict(batch=90,recorded_utc=now,receipt=rel(HERE/'import-receipt.json'),scope_kind='ONE_GLOBAL_WORKING_WEIGHT_POLICY_WITH_SCOPED_ESTIMATES_AND_SOURCE_DISPLAY_RECOVERIES',new_owner_policy_events=1,new_individual_owner_reply_events=0,new_accepted_working_proposal_groups=0,new_six_field_acceptances=0,new_conditional_weight_estimates=9,existing_weight_display_recoveries=7,existing_numeric_weight_scopes=214,reference_or_deferred_weight_scopes=48,new_physically_verified_specification_groups=0,new_name_approvals=0,new_registered_BC_component_ids=[],root_new_private_original_downloads=0,remote_mutations=0,workbook_export_pending=True)
 cp['parallel_import_queue'].append(dict(scope_kind=summary['scope_kind'],receipt=rel(package),receipt_sha256=PACKAGE_SHA,approval_imported=True,evidence_imported=True,import_receipt=summary['receipt'],status='ONE_WEIGHT_POLICY;9_CONDITIONAL_ESTIMATES;7_EXISTING_DISPLAY_RECOVERIES'));c['parallel_import_queue']=copy.deepcopy(cp['parallel_import_queue'])
 for doc,key in [(p,'latest_parallel_import'),(cp,'last_parallel_import'),(c,'last_parallel_import')]:doc[key]=copy.deepcopy(summary)
 for doc in docs.values():doc['updated_utc']=now
 docs['root']['current_component_review']=copy.deepcopy(c)
 assert p['reviews']==before['progress']['reviews'] and u['specification_approval_counts']==specification_counts(u)==before['user']['specification_approval_counts']
 assert all(cp[k]==v for k,v in before['walkthrough'].items() if k.startswith('current_')) and all(sha(PATHS[k])==v for k,v in guards.items())
 protected={str(path):sha(path) for path in [ROOT/cp['register_workbook'],ROOT/'components/evidence/component_register.json',ROOT.parent/'Boldstone_Wall_Sculptures_Matched_All_Fields_2026-10-15.xlsx']}
 write(HERE/'before-import.json',before);write(ROOT/approval,policy);write(HERE/'source-manifest.json',dict(files=frozen,historical_mutable_references=historical,root_verified_owner_evidence=True,selected_cached_images_visually_inspected=6,new_private_original_downloads=0))
 for k,path in PATHS.items():write(path,docs[k])
 write(HERE/'import-receipt.json',dict(status='APPLIED;INDEPENDENT_READBACK_REQUIRED',summary=summary,policy_id=policy['policy_id'],protected_sha256=protected,shared_after_sha256={k:sha(v) for k,v in PATHS.items()}));print(json.dumps(dict(batch=90,status='APPLIED',new_policy=1,conditional_estimates=9,source_display_recoveries=7,new_six_field_acceptances=0)))

if __name__=='__main__':main()
