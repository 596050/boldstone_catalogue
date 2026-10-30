"""Independent exact-source, typed-scope, counter and idempotency readback."""
import copy,json,sys,subprocess
from datetime import datetime,timezone
from import_bulk_working_95_96 import ROOT,PATHS,CONFIG,at,read,sha,write,FIELDS
batch=int(sys.argv[1]);here=ROOT/f'components/reviews/parallel-import-2026-10-19-batch{batch}';r=read(here/'import-receipt.json');old=read(here/'before-import.json');cur={k:read(v) for k,v in PATHS.items()};u,p,cp,c=(cur[k] for k in ['user','progress','walkthrough','component']);restored=copy.deepcopy(p);checks={}
for x in r['scopes']:
 key=x['component_id']+'|'+x['size_finish_variant_id'];node=at(p,x['model_locator']);prior=at(old['progress'],x['model_locator']);decision=read(ROOT/x['approval_record']);back=at(restored,x['model_locator']);back.clear();back.update(copy.deepcopy(prior));active=node['accepted_working_specifications']
 checks.update({key+':'+k:v for k,v in {
  'source_proposals_and_prior_identity_platform_reference_fields_unchanged':all(node.get(k)==prior.get(k) for k in ['specification_proposals','specifications','canonical_name','identity_confirmed','primary_image_id','reference_image_id','primary_folder_id','primary_file_ids','containing_folder_ids','platform_mapping','historical_name_keep_bindings','source_depicted_identities_kept','current_display_number_provenance']),
  'preexisting_source_specification_dictionary_preserved':not prior.get('source_specifications_retained') or node['source_specifications_retained']==prior['source_specifications_retained'],
  'six_working_groups_not_actual_measurements_or_stock':node['all_six_working_specification_fields_accepted'] and set(active)==set(FIELDS) and len(set(node['approved_proposal_ids']))==6 and all(v['owner_approved'] and not v['physical_value_verified'] for v in active.values()) and not node['physical_specs_verified'] and not node['actual_stock_verified'],
  'source_values_displays_and_exact_proposal_IDs_retained':all(active[k]['display']==decision['specifications'][k]['display'] and active[k].get('source_values')==decision['specifications'][k].get('source_values') for k in FIELDS) and node['approved_proposal_ids']==decision['approved_proposal_ids'],
  'no_synthetic_owner_reply_or_new_policy':decision['owner_answer_for_this_scope'] is None and decision['new_individual_owner_reply_events']==0 and decision['working_acceptance_basis']=='DERIVED_FROM_STANDING_OWNER_POLICY' and 'authoritative_user_evidence' not in decision,
  'stable_selected_reference_binding':node['current_dropbox_reference']['file_path'].rsplit('/',1)[0]==node['current_dropbox_reference']['folder_path'] and node['current_dropbox_reference']['file_id']==(decision.get('selected_reference_file_id') or decision.get('reference_file_id') or decision['primary_file_id']),
  'photo_gap_exact_scope_not_global_absence':p['current_component_photograph_gaps'][x['photo_gap_id']]['model_locator']==x['model_locator'] and 'elsewhere unknown' in p['current_component_photograph_gaps'][x['photo_gap_id']]['missing'] and not node['photo_coverage']['exact_physical_cast_identity_verified'],
  'active_scope_does_not_repeat_working_approval_question':'Working values accepted' in node['scope'] and 'Physical measurements' in node['scope'],
 }.items()})
ledgers=['specification_decisions','build_variant_decisions','size_finish_variant_specification_decisions'];checks.update({
 'all_other_review_alias_and_source_nodes_unchanged':all(restored[k]==old['progress'][k] for k in ['reviews','catalogue_alias_reviews','source_design_reviews']),
 'all_existing_owner_ledger_entries_retained':all(u.get(k,[])[:len(old['user'].get(k,[]))]==old['user'].get(k,[]) for k in ledgers),
 'all_other_owner_records_unchanged':all(u[k]==v for k,v in old['user'].items() if k not in ledgers+['updated_utc','specification_approval_counts']),
 'scoped_counter_delta_without_replaying_prior_groups':u['specification_approval_counts']['proposal_groups']-old['user']['specification_approval_counts']['proposal_groups']==CONFIG[batch]['delta'] and c['interactive_review_state']['approved_proposal_groups']==u['specification_approval_counts']['proposal_groups'],
 'exact_new_decision_count':sum(len(u.get(k,[]))-len(old['user'].get(k,[])) for k in ledgers)==CONFIG[batch]['scopes'],
 'canonical_policies_not_replayed':all(cur[k].get(name)==old[k].get(name) for k in ['user','progress','walkthrough','component'] for name in ['working_specification_acceptance_policy','working_specification_acceptance_policy_decisions','global_fixing_choice_policy','global_fixing_choice_policy_decisions','global_approximate_weight_policy','global_approximate_weight_policy_decisions']),
 'physical_counts_platform_bindings_and_other_domains_unchanged':c['counts']==old['component']['counts'] and all(p[k]==old['progress'][k] for k in ['offer_photo_bindings','arrangement_component_bindings','canonical_component_consolidations','canonical_variant_aliases','catalogue_design_aliases','group_photo_review_policy','weight_review_output_overlays']),
 'root_question_answer_and_unknown_fixing_count_preserved':all(cp[k]==v for k,v in old['walkthrough'].items() if k.startswith('current_')) and cp['current_answer_recorded'] and not cp['current_fixing_count_answer_recorded'],
 'root_component_mirror_exact':cur['root']['current_component_review']==c,
 'prior_photo_gap_records_unchanged':all(p['current_component_photograph_gaps'][k]==v for k,v in old['progress']['current_component_photograph_gaps'].items()),
 'saved_master_hashes_match_receipt':all(sha(PATHS[k])==v for k,v in r['shared_after_sha256'].items()),
 'all_frozen_source_bytes_match':all(sha(ROOT/z['snapshot'])==z['sha256'] for z in read(here/'source-manifest.json')['files']),
 'published91_and_original_sources_preserved':all(sha(path)==v for path,v in r['protected_sha256'].items()),
 'zero_new_owner_replies_policies_or_remote_writes':all(r['summary'][k]==0 for k in ['new_owner_policy_events','new_individual_owner_reply_events','root_new_private_original_downloads','remote_mutations']),
})
if batch==95:
 aliases=[at(p,x['model_locator']) for x in r['scopes'] if x['review_scope']=='CATALOGUE_ALIAS'];checks['all8_aliases_keep10_historical_bundles_separate']=len(aliases)==8 and sum(len(x['historical_name_keep_bindings']) for x in aliases)==10
 checks['nine_exact_prior_approved_IDs_not_counted_again']=r['summary']['resulting_working_fields']==336 and r['summary']['new_accepted_working_proposal_groups']==327
 checks['selected_native_and_derivative_limits_not_erased']=sum(x['native_hash_verified_from_cache'] for x in read(here/'parent-media-hash-check.json')['selected_media'])==44
else:
 azure=next(at(p,x['model_locator']) for x in r['scopes'] if x['component_id']=='BC-AZURE');checks['Azure_net_guess_separate_from_shipping15kg']=all(t in azure['accepted_working_specifications']['weight']['display'] for t in ['7','4','10','15']) and 'shipping' in azure['accepted_working_specifications']['weight']['display'].lower()
 checks['typed40_scope_mix_retained']=sorted(x['review_scope'] for x in r['scopes']).count('BASE')==8 and sum(x['review_scope']=='BUILD' for x in r['scopes'])==5 and sum(x['review_scope']=='COMPONENT_LAYOUT' for x in r['scopes'])==2 and sum(x['review_scope']=='WHOLE_SOURCE' for x in r['scopes'])==1
guards={k:sha(v) for k,v in PATHS.items()};replay=subprocess.run([sys.executable,str(ROOT/'components/reviews/import_bulk_working_95_96.py'),str(batch)],capture_output=True,text=True,check=True);checks['idempotent_repeat_no_write']='ALREADY_IMPORTED_IDEMPOTENT_NO_WRITE' in replay.stdout and all(sha(PATHS[k])==v for k,v in guards.items());assert all(checks.values()),[k for k,v in checks.items() if not v]
write(here/'independent-readback.json',dict(status='PASS',checked_utc=datetime.now(timezone.utc).isoformat(),check_count=len(checks),checks={k:'PASS' for k in checks},import_receipt_sha256=sha(here/'import-receipt.json')))
for x in r['scopes']:
 event=dict(event_id=x['decision_id'],event='TYPED_EXISTING_SCOPE_WORKING_FIELDS_UNDER_CANONICAL_POLICY',batch=batch,new_owner_reply_events=0,new_policy_events=0,new_physical_counts=0,readback_sha256=sha(here/'independent-readback.json'))
 for path in [ROOT/'components/reviews/identity_review_journal.jsonl',ROOT/'review_journal.jsonl']:
  if not any(json.loads(line).get('event_id')==event['event_id'] for line in path.read_text().splitlines() if line.strip()):
   with path.open('a') as f:f.write(json.dumps(event)+'\n')
print(json.dumps(dict(batch=batch,status='PASS',checks=len(checks),new_working_groups=CONFIG[batch]['delta'])))
