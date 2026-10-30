"""Append the bounded register-only correction to the completed book audit."""
from pathlib import Path
import collections, datetime, hashlib, json

Q=Path(__file__).resolve().parent; F=Q/'frozen-inputs'; C=Q/'current-state-correction'
H=Path('/Users/tprice/Documents/boldstone/sculpture-catalogue/components/reconciliation/owner-identity-decisions-master-2026-10-25')
read=lambda p:json.loads(Path(p).read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
counts=collections.Counter(); failures=[]
def check(ok,category,context=''):
    counts[category]+=1
    if not ok:failures.append({'category':category,'context':str(context)[:1200]})

prior=read(Q/'candidate-independent-readback.json')
superseded={'current_FFL1_disposition_not_stale','current_FFL1_unbound_flag_explicitly_photo_only'}
check(len(prior['failures'])==2 and {x['category'] for x in prior['failures']}==superseded,'only_two_recorded_findings_require_addendum')
add=read(C/'current-state-alignment-addendum.json')
check(sha(C/'current-state-alignment-addendum.json')=='ecd59a64c63b83b625f82dfe5abf3a0a194ffe17386dfc6f59e4109f48434d1b','explicit_addendum_hash')
check(sha(C/'canonical-master-register.json')==add['after_register_sha256']=='83e9dc5ae1e576a75afbaf8acffb0f37e2885ab72170946b8cc0b3a105158f90','explicit_corrected_register_hash')
check(sha(C/'register-before-current-state-alignment.json')==sha(F/'canonical-master-register.json')==add['before_register_sha256'],'exact_prior_frozen_register_bound')
check(sha(F/'master-workbook.pending')==sha(H/'master-workbook.pending')==add['unchanged_workbook_sha256']==prior['candidate_workbook_sha256'],'exact_workbook_unchanged_no_book_rerun')
check(sha(H/'workbook-edit-plan.json')==prior['frozen_edit_plan_sha256'],'current_frozen_plan_unchanged')
check(sha(H/'canonical-master-register.json')==add['after_register_sha256'],'current_candidate_matches_checked_corrected_register')
before=read(F/'canonical-master-register.json');after=read(C/'canonical-master-register.json')
check([k for k in set(before)|set(after) if before.get(k)!=after.get(k)]==['options'],'only_options_container_changed')
old={x['product_id']:x for x in before['options']};new={x['product_id']:x for x in after['options']};pid='BSI-04D6E8690F30'
check(set(old)==set(new) and len(new)==189,'retained_option_set_identical')
check({k for k in old if old[k]!=new[k]}=={pid},'only_FFL1_current_state_changed')
for k in old:
    if k!=pid:check(old[k]==new[k],'other_188_full_option_objects_identical',k)
    check(old[k]['master_fields']==new[k]['master_fields'],'all_1134_working_field_objects_identical_by_option',k)
check(sum(len(x['master_fields']) for x in new.values())==1134,'all_1134_field_objects_count')
allowed={'image_role','owner_identity_resolution_history','unbound_primary_photo_reference','current_listing_reconciliation','current_photo_task_review','remaining_evidence_gaps','readiness_note','current_listing_resolution','current_legacy_identity_disposition','unbound_identity'}
delta={k for k in set(old[pid])|set(new[pid]) if old[pid].get(k)!=new[pid].get(k)}
check(delta==allowed,'exact_10_current_state_metadata_keys',sorted(delta))
check({k:v for k,v in old[pid].items() if k not in allowed}=={k:v for k,v in new[pid].items() if k not in allowed},'all_other_FFL1_fields_identical')
item=new[pid];legacy=item['current_legacy_identity_disposition']
check(legacy['same_as_FFS2_not_assumed'] is False and legacy['same_as_FFS2_owner_confirmed'] is True and legacy['status']=='OWNER_CONFIRMED_SAME_RELIEF_DESIGN','FFL1_active_design_disposition_resolved')
check(legacy['owner_decision_id']=='LEGACY-FFL1-FFS2-RELIEF' and legacy['current_face_cm']=={'height':70,'width':15} and legacy['separate_standard_100x22_not_current'] is True,'identity_answer_and_current_size_scopes_separate')
check(item['unbound_identity'] is False and item['unbound_primary_photo_reference'] is True,'design_resolved_photo_still_unbound')
history=item['owner_identity_resolution_history']
check(all(history[k]==v for k,v in old[pid]['owner_identity_resolution_history'].items()),'all_prior_identity_history_preserved')
archived=history['current_state_before_owner_identity']
check(archived.get('current_legacy_identity_disposition')==old[pid]['current_legacy_identity_disposition'] and archived.get('unbound_identity') is True,'former_disposition_and_unbound_flag_preserved_as_history')
for k in ['file_id','folder_id','image_url','folder_url','context_file_id','context_folder_id','context_image_url','context_folder_url']:
    check(item.get(k)==old[pid].get(k),'no_selected_photo_or_folder_promotion_in_addendum',k)
check(item['file_id']==item['image_url']=='' and item['photo_coverage']['individual']=='Shared design reference','FFL1_design_reference_without_primary_selection')
for branch in ['current_listing_resolution','current_listing_reconciliation']:
    check('Owner confirms FFL1 and FFS2 share the relief' in item[branch]['next_action'] and 'before any additional variant' in item[branch]['next_action'],'current_listing_next_action_aligned',branch)
check(item['current_photo_task_review']['roles']['individual']['state']=='OWNER_DESIGN_RELATIONSHIP_RESOLVED','individual_photo_task_no_repeat_identity_question')
check(item['current_photo_task_review']['roles']['in_situ']['state']=='OWNER_CONTEXT_HOLD_RETAINED','FFL1_context_hold_retained')
for k in ['in_situ','series']:check(item['photo_coverage'][k]==old[pid]['photo_coverage'][k],'existing_photo_policy_unchanged',k)
check('Do not repeat the resolved FFL1/FFS2 relief question' in item['remaining_evidence_gaps'],'current_remaining_evidence_excludes_resolved_question')
check(sha(C/'image-coverage-current.json')==sha(F/'image-coverage-current.json')==sha(H/'image-coverage-current.json'),'coverage_audit_unchanged_by_addendum')
saved=read(C/'saved-workbook-verification.json')
check(saved['status']=='PASS' and not saved['failures'] and saved['register_sha256']==add['after_register_sha256'] and saved['workbook_sha256']==prior['candidate_workbook_sha256'],'new_terminal_provider_readback_binds_final_bytes')
for p,h in read(Q/'frozen-input-manifest.json')['protected_published_files'].items():check(sha(p)==h,'all_10_published_baseline_files_still_unchanged',p)
check(sha(H/'canonical-master-register.json')==add['after_register_sha256'] and sha(H/'master-workbook.pending')==add['unchanged_workbook_sha256'],'candidate_hashes_unchanged_at_end')

result={'status':'PASS' if not failures else 'FAIL','checked_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
 'candidate_workbook_sha256':prior['candidate_workbook_sha256'],'candidate_register_sha256':add['after_register_sha256'],'frozen_edit_plan_sha256':prior['frozen_edit_plan_sha256'],
 'prior_checks_reused_passed':prior['checks_passed'],'addendum_checks_passed':sum(counts.values())-len(failures),'checks_passed':prior['checks_passed']+sum(counts.values())-len(failures),'check_categories':dict(counts),'failures':failures,
 'prior_two_findings_resolved_by_exact_addendum':True,'original_failed_readbacks_retained':True,
 'owner_decisions':4,'display_renames':2,'active_options':188,'retained_component_IDs':112,'working_design_groups':110,
 'workbook_authored_cell_changes':95,'calculated_cache_changes':8,'artifact_tool_value_reads':103,'native_hyperlinks_with_same_targets':12206,'hyperlink_labels_synchronized_to_planned_values':3,'scoped_previews_visually_reviewed':5,
 'baseline_to_final_working_fields':{'wording_only':3,'all_other_full_objects_identical':1131,'all_1134_unchanged_by_final_metadata_addendum':True},
 'context_deferrals':22,'series_deferrals':1,'FFL1_selected_primary_promoted':False,'native_Excel_runtime_evaluated':False,
 'scope':'Bounded independent exact-answer, identity/current-state and95/8 workbook delta QA. No full gallery rerun; final register correction checked separately against frozen854c. No provider or canonical files edited.',
 'live_calls':0,'native_writes':0,'canonical_writes':0,'owner_questions_reissued':0}
(Q/'final-candidate-independent-readback.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:result[k] for k in ['status','checks_passed','addendum_checks_passed','failures','candidate_register_sha256','candidate_workbook_sha256']}))
