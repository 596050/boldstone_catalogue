"""Final graph audit bound to frozen review and worker-02 source coverage bytes."""
import json
import hashlib
from pathlib import Path
from collections import Counter,defaultdict
from datetime import datetime,timezone

W=Path(__file__).resolve().parent
R=W.parent
ROOT=Path('/Users/tprice/Documents/boldstone/sculpture-catalogue')

# Reuse the independently prepared raw assertion/owner-scope tests, while keeping
# the earlier preliminary readback file intact.
core_path=W/'verify_canonical.py'
code=core_path.read_text().replace("W/'canonical-readback.json'","W/'canonical-final-readback-base.json'")
namespace={'__file__':str(core_path),'__name__':'__independent_final_core__'}
exec(compile(code,str(core_path),'exec'),namespace)
core=json.loads((W/'canonical-final-readback-base.json').read_text())

cp=R/'canonical-products.json';cb=cp.read_bytes();c=json.loads(cb)
input_manifest=json.loads((R/'input-manifest.json').read_text())
coverage_manifest_path=R/'source-coverage-manifest.json'
coverage_manifest_bytes=coverage_manifest_path.read_bytes()
coverage_manifest=json.loads(coverage_manifest_bytes)
x=json.loads((R/'inputs/refresh-data.json').read_text())
p=json.loads((R/'inputs/specification_review_progress.json').read_text())
u=json.loads((R/'inputs/user_classifications.json').read_text())
model=json.loads((R/'inputs/component_register.json').read_text())
frozen_offers=json.loads((R/'inputs/source_offer_coverage.json').read_text())
frozen_configs=json.loads((R/'inputs/source_configuration_coverage.json').read_text())
frozen_queue=json.loads((R/'inputs/named_appearance_source_queue.json').read_text())
checks={};errors=[]
def check(name,value,detail=None):
 checks[name]=bool(value)
 if not value:errors.append({'check':name,'detail':detail})
check('core_owner_scope_counts_assertion_and_group_tests_pass',core['status'].startswith('PASS'),core['errors'])
check('core_audit_bound_to_same_canonical_bytes',core['canonical_sha256']==hashlib.sha256(cb).hexdigest())

products=c['products'];product_ids={z['product_id'] for z in products};prods={z['product_id']:z for z in products}
refs={z['reference_id']:z for z in c['references']};candidates={z['candidate_id']:z for z in c['source_candidates']};additional={z['candidate_id']:z for z in c['additional_source_candidates']}
all_ids=product_ids|set(refs)|set(candidates)|set(additional)
reference_aliases=c.get('reference_aliases',{})
alias_errors=[]
for old,record in reference_aliases.items():
 seen=set();current=old
 while current in reference_aliases:
  if current in seen:
   alias_errors.append({'alias':old,'reason':'cycle','chain':sorted(seen)});break
  seen.add(current);current=reference_aliases[current]['target_reference_id']
 else:
  if current not in refs:alias_errors.append({'alias':old,'reason':'missing final reference','target':current})
 if old in all_ids:alias_errors.append({'alias':old,'reason':'alias shadows a current graph record'})
check('reference_aliases_resolve_to_existing_references_without_cycles_or_shadowing',not alias_errors,alias_errors)
check('only_expected_legacy_G050_reference_alias',reference_aliases=={'REF-BC-MIX-SPIRALS':{'target_reference_id':'REF-G050','reason':'The historical stacked-spiral source position belongs to the same owner-deferred G050 collection. Preserve the old reference key without creating another collection record.'}})
all_ids|=set(reference_aliases)
scope_map={z['source_scope']:z for z in c['scope_reconciliation']}
scope_products={s:z for z in products for s in z['source_scopes']}

accepted_indices=[]
for z in products:
 for field,body in z['specifications'].items():accepted_indices.extend(a['source_row_index'] for a in body['assertions'])
nonapplied=c['source_only_assertions_not_applied_to_products']
nonapplied_indices=[z['source_row_index'] for z in nonapplied]
check('accepted_and_noninherited_source_rows_are_disjoint',not set(accepted_indices)&set(nonapplied_indices))
check('all_1668_raw_source_rows_retained_exactly_once',len(accepted_indices)+len(nonapplied_indices)==len(x['specifications']) and Counter(accepted_indices+nonapplied_indices)==Counter(range(len(x['specifications']))))
bad_nonapplied=[]
for a in nonapplied:
 row=x['specifications'][a['source_row_index']]
 if a['original_row']!=row or a['source_scope']!='|'.join(row[:2]):bad_nonapplied.append(a['source_row_index'])
check('all_624_noninherited_rows_equal_frozen_originals',len(nonapplied)==624 and not bad_nonapplied,bad_nonapplied)

frozen_integrity=[]
for item in coverage_manifest['files']:
 src,snap=Path(item['source']),Path(item['snapshot'])
 sh,fh=hashlib.sha256(src.read_bytes()).hexdigest(),hashlib.sha256(snap.read_bytes()).hexdigest()
 frozen_integrity.append({'source':str(src),'snapshot':str(snap),'expected_sha256':item['sha256'],'source_sha256':sh,'snapshot_sha256':fh,'frozen_snapshot_matches_manifest':fh==item['sha256'],'current_worker_source_matches_capture':sh==item['sha256']})
check('all_five_frozen_worker02_snapshots_match_manifest',all(a['frozen_snapshot_matches_manifest'] for a in frozen_integrity))
check('four_authoritative_worker02_coverage_sources_unchanged_since_capture',all(a['current_worker_source_matches_capture'] for a in frozen_integrity if not a['source'].endswith('/validation.json')))
check('frozen_source_coverage_validation_passed',coverage_manifest['source_validation_result']=='PASS_ALL_SOURCE_ROWS_AND_TARGET_REFERENCES')

graph_offers={z['offer_ref']:z for z in c['source_offer_coverage']};fo={z['offer_ref']:z for z in frozen_offers}
graph_configs={z['configuration_id']:z for z in c['source_configuration_coverage']};fc={z['configuration_id']:z for z in frozen_configs}
model_offers={z['offer_ref']:z for z in model['platform_records']};model_configs={z['configuration_id']:z for z in model['configurations']}
check('all_81_original_offers_accounted_for_once',len(graph_offers)==len(c['source_offer_coverage'])==len(model_offers)==81 and set(graph_offers)==set(fo)==set(model_offers))
check('all_199_original_configurations_accounted_for_once',len(graph_configs)==len(c['source_configuration_coverage'])==len(model_configs)==199 and set(graph_configs)==set(fc)==set(model_configs))
worker_differences=[]
for kind,left,right in [('offer',fo,graph_offers),('configuration',fc,graph_configs)]:
 for key,source in left.items():
  for field,value in source.items():
   if right[key].get(field)!=value:worker_differences.append({'kind':kind,'key':key,'field':field})
check('every_frozen_worker02_field_retained_without_change',not worker_differences,worker_differences)

original_offer_differences=[]
offer_projection={'platform':'platform','source_title':'title','source_sku':'sku','squarespace_id':'sq_id','shopify_handle':'sh_handle','source_url':'source_url','native_parts':'native_parts','source_each_cm':'source_each_cm','source_overall_cm':'source_overall_cm','source_set_weight_kg':'source_set_weight_kg'}
for key,source in model_offers.items():
 for dest,origin in offer_projection.items():
  if graph_offers[key].get(dest)!=source.get(origin):original_offer_differences.append({'key':key,'field':dest,'original':source.get(origin),'graph':graph_offers[key].get(dest)})
check('offer_identity_and_component_set_values_match_original_source',not original_offer_differences,original_offer_differences[:20])
original_config_differences=[]
config_projection={'source_component_id':'component_id','source_component_name':'component_name','family':'family','baseline_finish_appearance':'finish_appearance','source_size_options':'size_options'}
for key,source in model_configs.items():
 for dest,origin in config_projection.items():
  if graph_configs[key].get(dest)!=source.get(origin):original_config_differences.append({'key':key,'field':dest,'original':source.get(origin),'graph':graph_configs[key].get(dest)})
check('configuration_identity_finish_and_size_labels_match_original_source',not original_config_differences,original_config_differences[:20])

all_bom=[b for o in c['source_offer_coverage'] for b in o['bom_rows']]
orig_bom={z['bom_id']:z for z in model['bom']};copied_bom={z['bom_id']:z for z in all_bom}
check('all_122_original_BOM_rows_preserved_exactly_once',len(all_bom)==len(copied_bom)==len(orig_bom)==122 and copied_bom==orig_bom)
offer_states=Counter(z['canonical_graph_coverage_state'] for z in c['source_offer_coverage'])
config_states=Counter(z['canonical_graph_coverage_state'] for z in c['source_configuration_coverage'])
check('offer_state_totals_64_supported_14_pending_2_candidate_1_historical',offer_states==Counter({'SUPPORTED_CURRENT_TARGETS_WITH_SOURCE_MATCH_LIMITS':64,'COVERED_FAMILY_EXACT_SOURCE_SCOPE_PENDING':14,'SOURCE_CANDIDATE_ONLY':2,'REFERENCE_ONLY_HISTORICAL_DRAFT':1}))
check('configuration_state_totals_161_supported_26_pending_6_reference_6_candidate',config_states==Counter({'EXACT_CURRENT_SCOPE_SUPPORTED':161,'COVERED_FAMILY_EXACT_SCOPE_PENDING':26,'REFERENCE_ONLY':6,'SOURCE_CANDIDATE_ONLY':6}))

dangling=[]
def audit_ids(value,path):
 if isinstance(value,dict):
  for k,v in value.items():audit_ids(v,path+[k])
 elif isinstance(value,list):
  for i,v in enumerate(value):audit_ids(v,path+[str(i)])
 elif isinstance(value,str) and value.startswith(('BSI-','REF-','CAND-','FINISH-')) and len(value.split())==1 and value not in all_ids:dangling.append({'path':'.'.join(path),'target':value})
for key in ['scope_reconciliation','historical_alias_reconciliation','references','source_offer_coverage','source_configuration_coverage','additional_source_candidates']:audit_ids(c[key],[key])
check('all_graph_and_coverage_target_IDs_resolve',not dangling,dangling)
check('all_exact_offer_and_configuration_targets_are_existing_products',all(t in product_ids for z in c['source_offer_coverage']+c['source_configuration_coverage'] for t in z.get('exact_supported_target_ids',[])))

unresolved_cases={z['configuration_id']:z for z in frozen_queue['cases'] if z['audit_state']=='SOURCE_CANDIDATE_IDENTITY_OR_FINISH_PENDING'}
add_sources={q:z for z in c['additional_source_candidates'] for q in z['source_configuration_ids']}
check('nine_named_appearance_candidates_equal_frozen_unresolved_cases',len(unresolved_cases)==len(c['additional_source_candidates'])==9 and set(add_sources)==set(unresolved_cases))
appearance_errors=[]
for key,source in unresolved_cases.items():
 z=add_sources[key]
 if z['source_file_ids']!=source['source_file_ids'] or z['counted_as_working_product'] is not False or z['record_type']!='UNRESOLVED_SOURCE_APPEARANCE_NOT_AN_ADDITIONAL_PRODUCT':appearance_errors.append(key)
check('unresolved_appearance_sources_retained_without_creating_products',not appearance_errors,appearance_errors)
resolved_cases=[z for z in frozen_queue['cases'] if z['audit_state']=='RESOLVED_TO_EXISTING_REVIEWED_PRODUCT_AND_CONTEXT']
check('resolved_G098_legacy_mixed_finish_not_reopened_as_new_candidate',len(resolved_cases)==1 and resolved_cases[0]['configuration_id']=='CFG-7D395F33C3' and 'CFG-7D395F33C3' not in add_sources)
g098=graph_configs['CFG-7D395F33C3'];rust_scope='BC-DR-SPIRAL|DR-SPIRAL-RUST'
check('G098_Spiral_targets_existing_Rust_scope_not_new_VerdigrisRust_product',g098['exact_supported_target_ids']==[scope_products[rust_scope]['product_id']])

# DR3 photo correspondence is distinct from the still-unreviewed maker DR3.
dr3=p['reviews']['BC-DR-WAVE3'];dr3map=scope_map['BC-DR-WAVE3|DR3-WHITE']
target_scope=dr3['canonical_depicted_component_id']+'|DR1-WHITE'
check('DR3_selected_image_alias_uses_existing_owner_relationship',dr3['depicted_identity_resolved'] is True and dr3['separate_saleable_design_from_selected_reference'] is False and target_scope in scope_products)
check('DR3_WHITE_targets_DR1_without_inheriting_specs',dr3map['disposition']=='SELECTED_IMAGE_REFERENCE_ALIAS' and dr3map['targets']==[scope_products[target_scope]['product_id']] and dr3map['specification_assertions_inherited'] is False)
dr3candidate=next(z for z in c['source_candidates'] if z['component_id']=='BC-DR-WAVE3')
check('separate_maker_DR3_candidate_preserved_without_selected_photo_alias_confusion',dr3candidate['source_scopes']==['BC-DR-WAVE3|BASE'] and scope_map['BC-DR-WAVE3|BASE']['targets']==[dr3candidate['candidate_id']])
check('DR3_WHITE_six_original_assertions_retained_only_in_noninherited_partition',len([a for a in nonapplied if a['source_scope']=='BC-DR-WAVE3|DR3-WHITE'])==6 and not any(a['source_scope']=='BC-DR-WAVE3|DR3-WHITE' for z in products for f in z['specifications'].values() for a in f['assertions']))

# Resolve Moonshell members from the frozen owner ledger, while retaining the
# distinction between named membership and model-derived displayed position.
member_decisions=[u['component_identity_relationship_decisions'][i] for i in [2,3]]
member_ids=[]
for d in member_decisions:
 source=d['component_id']+'|BASE';destination=d['canonical_component_id']+'|'+d['canonical_size_finish_variant_id'];member_ids.append(scope_products[destination]['product_id'])
 z=scope_map[source]
 check('Moonshell_member_scope_matches_owner_ledger:'+source,z['disposition']=='RESOLVED_ARRANGEMENT_POSITION_REFERENCE' and z['targets']==[scope_products[destination]['product_id']] and z['specification_assertions_inherited'] is False)
 check('Moonshell_source_assertions_not_applied:'+source,len([a for a in nonapplied if a['source_scope']==source])==6 and not any(a['source_scope']==source for q in products for f in q['specifications'].values() for a in f['assertions']))
 check('Moonshell_owner_confirmation_does_not_claim_physical_cast_or_mould:'+source,d['owner_combined_membership_confirmed'] is True and d['position_owner_stated'] is False and d['same_physical_cast_confirmed'] is False and d['same_mould_confirmed'] is False)
mr=refs['REF-MLAVA-1-PLUS-2-WHITE'];membership=u['arrangement_membership_decisions'][0]
check('one_combined_Moonshell_reference_matches_owner_membership_without_extra_product',membership['arrangement_id']=='MLAVA-1-PLUS-2-WHITE' and mr['member_product_ids']==member_ids and mr['counted_as_working_product'] is False and mr['record_type']=='OWNER_CONFIRMED_COMBINED_ARRANGEMENT_REFERENCE')
check('old_unresolved_Moonshell_position_refs_removed_from_graph','REF-BC-MLAVA-WALL-1' not in refs and 'REF-BC-MLAVA-WALL-2' not in refs)

evidence_checks=[]
dr3record=ROOT/dr3['relationship_approval'];drecord=json.loads(dr3record.read_text())
evidences=[]
for label,node in [('DR3_selected_image',drecord),('Moonshell_membership',membership)]:
 d=node.get('authoritative_user_evidence') or node.get('owner_evidence')
 if label=='DR3_selected_image' and not d:
  # Exact quoted-text lookup in the three known owner transcripts recovered this
  # missing locator; it is audit evidence, not a new approval or source edit.
  d={'transcript':'/Users/tprice/.codex/sessions/2026/10/16/rollout-2026-10-16T13-23-46-01a144ab-1a7c-7223-a403-73a4d53d70ff.jsonl','line':9352,'text':node['user_statement'],'locator_recovered_by_exact_user_text_search':True}
 if not d or not d.get('line'):
  evidence_checks.append({'label':label,'status':'NO_TRANSCRIPT_LOCATOR_IN_RECORD','record':str(dr3record) if label.startswith('DR3') else 'user_classifications.arrangement_membership_decisions[0]'});continue
 transcript=d.get('transcript') or d.get('transcript_path');line=None
 with open(transcript,'rb') as stream:
  for n,raw in enumerate(stream,1):
   if n==d['line']:line=raw;break
 payload=json.loads(line)['payload'];text='\n'.join(t['text'] for t in payload.get('content',[]) if isinstance(t,dict) and isinstance(t.get('text'),str)) if isinstance(payload.get('content'),list) else payload.get('message',payload.get('text',''))
 okay=payload.get('role','user' if payload.get('type')=='user_message' else None)=='user' and text==d.get('text',text)
 evidence_checks.append({'label':label,'transcript':transcript,'line':d['line'],'status':'PASS' if okay else 'FAIL','text':text})
 check('exact_owner_transcript_supports_'+label,okay)

check('all_original_source_files_still_match_frozen_manifest',all(hashlib.sha256(Path(a['source']).read_bytes()).hexdigest()==a['sha256'] and hashlib.sha256(Path(a['snapshot']).read_bytes()).hexdigest()==a['sha256'] for a in input_manifest['sources']))
check('final_canonical_bytes_unchanged_during_audit',hashlib.sha256(cp.read_bytes()).hexdigest()==hashlib.sha256(cb).hexdigest())
check('source_coverage_manifest_unchanged_during_audit',coverage_manifest_path.read_bytes()==coverage_manifest_bytes)

caveats=[a for a in core['content_caveats'] if a['code']!='SOURCE_CONFIGURATION_AND_OFFER_COVERAGE_PENDING']
caveats.append({'code':'FULL_SOURCE_ACCOUNTING_IS_NOT_FULL_EXACT_MATCH_RESOLUTION','detail':'All81 offers and199 configurations are accounted for, with14 offer scopes and26 configuration scopes pending exact source applicability,6 source-candidate records and9 named appearance candidates preserved. No extra products or stock inferred.'})
if any(not a['current_worker_source_matches_capture'] for a in frozen_integrity):
 caveats.append({'code':'DERIVED_VALIDATION_RECEIPT_REFRESHED_AFTER_FREEZE','detail':'The current worker02 validation.json was refreshed after capture. Its immutable snapshot still matches the manifest; all four authoritative coverage/queue arrays match their captured bytes. The frozen receipt remains historical validation evidence.'})
report={'schema':'boldstone.independent-final-canonical-bound-readback.v1','worker_number':3,'audited_utc':datetime.now(timezone.utc).isoformat(),'status':'PASS_FINAL_GRAPH_BOUND_TO_FROZEN_SOURCES_WITH_LABELLED_UNKNOWNS' if not errors else 'FAIL','canonical_path':str(cp),'canonical_sha256':hashlib.sha256(cb).hexdigest(),'canonical_bytes':len(cb),'source_coverage_manifest_sha256':hashlib.sha256(coverage_manifest_bytes).hexdigest(),'core_readback':str(W/'canonical-final-readback-base.json'),'counts':{'working_products':len(products),'accepted_source_scopes':len(scope_products),'field_groups':sum(len(z['specifications']) for z in products),'accepted_source_assertions':len(accepted_indices),'noninherited_source_assertions':len(nonapplied),'all_retained_review_assertions':len(accepted_indices)+len(nonapplied),'source_offers':len(graph_offers),'source_configurations':len(graph_configs),'BOM_rows':len(all_bom),'additional_named_appearance_candidates':len(additional),'source_candidate_records':len(candidates),'references_total':len(refs),'original_group_sources':len(x['groups']),'canonical_group_references':sum(z['record_type']=='ARRANGEMENT_OR_COLLECTION_REFERENCE' for z in refs.values()),'historical_aliases':len(c['historical_alias_reconciliation'])},'offer_coverage_states':dict(offer_states),'configuration_coverage_states':dict(config_states),'checks':checks,'errors':errors,'frozen_worker02_source_integrity':frozen_integrity,'additional_owner_transcript_checks':evidence_checks,'content_caveats':caveats,'limits':'Catalogue records and scoped working assertions are verified. Physical measurements, current stock, casting/mould identity, installed hardware, live account listing status, image authenticity and unresolved source matches remain separately qualified. Workbook artifact verification is outside this JSON readback.','central_edits':0,'remote_reads':0,'remote_mutations':0}
(W/'canonical-final-bound-readback.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'status':report['status'],'counts':report['counts'],'errors':errors,'canonical_sha256':report['canonical_sha256'],'policy_evidence':evidence_checks},ensure_ascii=False,indent=2))
