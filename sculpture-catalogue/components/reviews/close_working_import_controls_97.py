"""Align import queues to verified imports before the workbook capture."""
import copy,json
from datetime import datetime,timezone
from import_bulk_working_95_96 import ROOT,PATHS,read,write,sha

docs={k:read(v) for k,v in PATHS.items()};u,p,cp,c=(docs[k] for k in ['user','progress','walkthrough','component']);now=datetime.now(timezone.utc).isoformat();before=copy.deepcopy(docs)
queuepath=ROOT/'components/reviews/pending-sealed-owner-imports-2026-10-19.json';queue=read(queuepath)
for b in range(92,98):
 h=ROOT/f'components/reviews/parallel-import-2026-10-19-batch{b}';r=read(h/'import-receipt.json');qa=read(h/'independent-readback.json');assert qa['status']=='PASS';summary=r['summary']
 old=next((x for x in queue['imports'] if x.get('import_batch')==b),None)
 if old is None:
  imp=next(x for x in cp['parallel_import_queue'] if x.get('import_receipt')==str((h/'import-receipt.json').relative_to(ROOT)))
  old=dict(package=imp['receipt'],sha256=imp['receipt_sha256'],import_batch=b);queue['imports'].append(old)
 old.update(status='IMPORTED_VERIFIED;WORKBOOK97_PENDING',import_receipt=str((h/'import-receipt.json').relative_to(ROOT)),scope=summary['scope_kind'],independent_readback=str((h/'independent-readback.json').relative_to(ROOT)))
 for x in cp.get('next_reserved_policy_batches',[]):
  if x['batch']==b:x.update(status='IMPORTED_VERIFIED;WORKBOOK97_PENDING',import_receipt=old['import_receipt'])
 for x in r['scopes']:
  cid,scope=x['component_id'],x['size_finish_variant_id'];loc=x.get('model_locator') or ['reviews',cid,('build_variants' if x['review_scope']=='BUILD' else 'size_finish_variants'),scope]
  existing=next((z for z in cp['parallel_working_specification_reviews'] if z.get('component_id')==cid and z.get('size_finish_variant_id')==scope),None)
  if existing is None:
   existing=dict(component_id=cid,size_finish_variant_id=scope,review_id=x['decision_id']);cp['parallel_working_specification_reviews'].append(existing)
  existing.update(model_locator=loc,scope_kind=x['review_scope'],working_approval_import_batch=b,import_receipt=old['import_receipt'],status='STANDING_POLICY_SIX_WORKING_FIELDS_IMPORTED;NO_INDIVIDUAL_REPLY;ACTUAL_VALUES_PENDING',owner_answer_recorded=False,standing_policy_acceptance_recorded=True,workbook_export_pending=True)
queue['updated_utc']=now;write(queuepath,queue)
weightpath=ROOT/cp['pending_owner_weight_instruction'];weight=read(weightpath);weight.update(status='POLICY90_IMPORTED_AND_INCLUDED_IN_WORKBOOK91;SUBSEQUENT_WORKING_VIEWS_PENDING97',workbook_export_through_batch=91,workbook_sha256=p['latest_workbook_export']['workbook_sha256']);write(weightpath,weight)
for target in [cp,c]:
 target['pending_owner_weight_instruction_status']='POLICY90_IMPORTED_AND_INCLUDED91;SUBSEQUENT_VIEWS_PENDING97'
 target['all_remaining_working_review_state']=dict(status='ALL_ALLOCATED_WORKING_REVIEWS_IMPORTED_VERIFIED;WORKBOOK97_PENDING',allocation='components/reviews/parallel-allocation-2026-10-20-all-remaining.json',allocated_scope_count=111,six_field_working_scopes=109,reference_disposition_scopes=2,final_individually_buyable_count=None,all_actual_specifications_complete=False,repeat_working_approval_questions_required=False)
c['parallel_working_specification_reviews']=copy.deepcopy(cp['parallel_working_specification_reviews']);c['next_reserved_policy_batches']=copy.deepcopy(cp['next_reserved_policy_batches']);cp['updated_utc']=c['updated_utc']=docs['root']['updated_utc']=now;docs['root']['current_component_review']=copy.deepcopy(c)
assert p==before['progress'] and u==before['user'] and all(cp[k]==v for k,v in before['walkthrough'].items() if k.startswith('current_'))
for k in ['walkthrough','component','root']:write(PATHS[k],docs[k])
write(ROOT/'components/reviews/parallel-import-2026-10-19-batch97/control-alignment.json',dict(status='PASS',aligned_batches=list(range(92,98)),new_approval_events=0,current_owner_fields_unchanged=True,registry_scopes=len(cp['parallel_working_specification_reviews']),shared_after_sha256={k:sha(v) for k,v in PATHS.items()}))
print(json.dumps(dict(status='PASS',aligned_batches=list(range(92,98)),registry_scopes=len(cp['parallel_working_specification_reviews']))))
