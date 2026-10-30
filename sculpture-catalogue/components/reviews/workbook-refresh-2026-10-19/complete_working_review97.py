"""Close the working review queue and retain an additive staging correction."""
import copy,json,hashlib,shutil
from pathlib import Path
from datetime import datetime,timezone

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(path,value):
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_name(path.name+'.tmp');tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n');tmp.replace(path)
paths={'p':ROOT/'components/reviews/specification_review_progress.json','u':ROOT/'components/reviews/user_classifications.json','cp':ROOT/'components/reviews/walkthrough_checkpoint.json','c':ROOT/'components/checkpoint.json','root':ROOT/'checkpoint.json'}
docs={k:read(v) for k,v in paths.items()};before=copy.deepcopy(docs);p,u,cp,c=(docs[k] for k in ['p','u','cp','c']);s=p['latest_workbook_export'];digest=s['workbook_sha256'];history=HERE/'history'/digest;now=datetime.now(timezone.utc).isoformat();assert s['included_owner_review_imports_through_batch']==97 and sha(ROOT/s['workbook'])==digest
queuepath=ROOT/'components/reviews/pending-sealed-owner-imports-2026-10-19.json';queue=read(queuepath);priorqueue=copy.deepcopy(queue);new=[];by={};duplicates=[]
for index,item in enumerate(queue['imports']):
 # One package can legitimately support different imports (for example an
 # owner fixing correction followed by the global fixing policy). Consolidate
 # only duplicate staging rows for the same allocated/imported batch.
 key=(item['package'],item.get('import_batch') or item.get('allocated_import_batch'))
 if key not in by:by[key]=len(new);new.append(copy.deepcopy(item))
 else:
  kept=new[by[key]];assert kept['sha256']==item['sha256'];duplicates.append(dict(package=item['package'],batch=key[1],staging_source_index=index,prior_status=kept['status']))
  if item.get('import_batch') is not None:kept.update(copy.deepcopy(item))
assert len(duplicates)==3 and all(x.get('import_batch') and x['status']=='IMPORTED_AND_INCLUDED_IN_WORKBOOK' and x['workbook_export_through_batch']==97 for x in new)
queue['imports']=new;queue['updated_utc']=now
correction=dict(status='PASS_STAGING_ONLY_CORRECTION',checked_utc=now,workbook_sha256=digest,reason='Three old sealed preparation rows92-94 lacked import_batch and were duplicated by the imported rows. They were already imported and included in the workbook. Current staging rows now combine each exact package/hash without changing decisions or workbook bytes.',duplicate_rows_consolidated=duplicates,staging_rows_before=len(priorqueue['imports']),staging_rows_after=len(new),pending_evidence_not_imported=[],new_approval_events=0,new_policy_events=0,new_remote_writes=0,prior_final_readback_retained_immutably=True)
write(history/'staging-before-control-correction.json',priorqueue);write(queuepath,queue);write(HERE/'staging-control-correction-batch97.json',correction);write(history/'staging-control-correction.json',correction)
allocation=read(ROOT/'components/reviews/parallel-allocation-2026-10-20-all-remaining.json');allocated={x['key'] for b in allocation['batches'].values() for x in b['scopes']};locators={}
for b in range(95,98):
 for x in read(ROOT/f'components/reviews/parallel-import-2026-10-19-batch{b}/import-receipt.json')['scopes']:locators[x['component_id']+'|'+x['size_finish_variant_id']]=x['model_locator']
locators['BC-BAR-WAVE|BASE']=['reviews','BC-BAR-WAVE'];checks={};working=[];references=[]
for key in sorted(allocated):
 if key in p['working_review_reference_dispositions']:
  checks['allocated_reference:'+key]=True;references.append(key);continue
 node=p
 for part in locators[key]:node=node[part]
 checks['allocated_six_working_fields:'+key]=node['all_six_working_specification_fields_accepted'] and len(node['accepted_working_specifications'])==6 and not node.get('physical_specs_verified') and all(not x.get('physical_value_verified') for x in node['accepted_working_specifications'].values());working.append(key)
checks.update({
 '111_allocated_scopes_109_working_and2_references':len(allocated)==111 and len(working)==109 and len(references)==2,
 'all_staging_packages_imported_and_included':not [x for x in queue['imports'] if not x.get('import_batch') or x['workbook_export_through_batch']!=97],
 'same_verified_workbook_bytes_and4703links':sha(ROOT/s['workbook'])==digest and s['native_hyperlinks']==4703,
 'accepted_group_count1045_not_physical_listing_count':u['specification_approval_counts']['proposal_groups']==1045 and s['final_individual_listing_count'] is None and not s['all_actual_specifications_complete'],
 'current_root_MCP4_answers_and_unknown_count_retained':cp['current_answer_recorded'] and cp['current_price_answer_recorded'] and cp['current_availability_answer_recorded'] and not cp['current_fixing_count_answer_recorded'],
 'each_canonical_policy_recorded_only_once':all(len(u[k])==1 for k in ['working_specification_acceptance_policy_decisions','global_fixing_choice_policy_decisions','global_approximate_weight_policy_decisions']),
 'all93_preview_hashes_match_actual_inspection':all(sha(ROOT/x['path'])==x['sha256'] for x in read(HERE/'model-preview-inspection-batch97.json')['final_previews']) and read(HERE/'model-preview-inspection-batch97.json')['final_preview_count']==93,
 'saved_file_and_scope_preservation_checks_passed':read(HERE/'independent-file-verification.json')['status']=='PASS' and read(HERE/'view-scope-readback-batch97.json')['status']=='PASS',
 'prior91_publication_preserved':sha(HERE/'published-snapshots/89c628442d2740db92064f7c66e203c965fabd59b7bcb00e0360971ffacc7c98.xlsx.snapshot')=='89c628442d2740db92064f7c66e203c965fabd59b7bcb00e0360971ffacc7c98',
 'all_working_registry_rows_included_through97':all(x.get('included_in_workbook_through_batch')==97 and not x.get('workbook_export_pending') for x in cp['parallel_working_specification_reviews']),
})
assert all(checks.values()),[k for k,v in checks.items() if not v]
final=read(HERE/'final-readback-batch97.json');final.update(status='PASS_COMPLETED_WORKING_REVIEW_AND_CORRECTED_STAGING_READBACK',checked_utc=now,prior_final_readback_sha256=sha(history/'final-readback-batch97.json'),pending_evidence_not_imported=[],staging_control_correction='components/reviews/workbook-refresh-2026-10-19/staging-control-correction-batch97.json',closure_check_count=len(checks),closure_checks={k:'PASS' for k in checks},completed_allocated_working_scopes=working,reference_dispositions=references)
path=HERE/'final-readback-batch97-completed.json';write(path,final);write(history/'final-readback-batch97-completed.json',final)
completion=dict(status=final['status'],receipt=str(path.relative_to(ROOT)),receipt_sha256=sha(path),workbook_sha256=digest,all_allocated_working_reviews_complete=True,pending_imports=0,final_individual_listing_count=None,all_actual_specifications_complete=False)
for doc in [cp,c]:doc['final_working_review_completion']=copy.deepcopy(completion);doc['updated_utc']=now
docs['root']['current_component_review']=copy.deepcopy(c);docs['root']['updated_utc']=now
assert p==before['p'] and u==before['u'] and all(cp[k]==v for k,v in before['cp'].items() if k.startswith('current_')) and c['counts']==before['c']['counts']
for key in ['cp','c','root']:write(paths[key],docs[key])
write(HERE/'final-checkpoint-readback-batch97.json',dict(status='PASS',completion=completion,shared_after_sha256={k:sha(v) for k,v in paths.items()},root_component_mirror_exact=read(paths['root'])['current_component_review']==read(paths['c']),source_decisions_and_workbook_bytes_unchanged=True))
shutil.copy2(HERE/'final-checkpoint-readback-batch97.json',history/'final-checkpoint-readback-batch97.json')
print(json.dumps(dict(status='PASS_COMPLETED',workbook_sha256=digest,closure_checks=len(checks),pending_imports=0,allocated_working=109,references=2,physical_listing_count='UNVERIFIED')))
