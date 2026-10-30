"""Independent readback of the weight-only import and preserved domains."""
import json, subprocess, sys
from datetime import datetime, timezone
from import_weight_policy_90 import ROOT, PATHS, HERE, SOURCE, read, sha, write, specification_counts
old=read(HERE/'before-import.json');cur={k:read(v) for k,v in PATHS.items()};r=read(HERE/'import-receipt.json');u,p,cp,c=(cur[k] for k in ['user','progress','walkthrough','component']);policy=p['global_approximate_weight_policy'];out=p['weight_review_output_overlays'];ests=u['conditional_weight_estimate_decisions'];rec=u['weight_display_recovery_records'];checks={
 'one_canonical_owner_policy_event':len(u['global_approximate_weight_policy_decisions'])==1 and u['global_approximate_weight_policy_decisions'][0]==policy and policy==cp['global_approximate_weight_policy']==c['global_approximate_weight_policy'],
 'canonical_owner_evidence_not_individual_replies':policy['policy_id'].endswith('LINE30053') and not policy['per_sculpture_owner_reply_created'] and not policy['physical_weights_measured_or_verified_by_this_policy'] and not policy['other_five_specification_fields_approved_by_this_policy'],
 'all_review_nodes_raw_six_source_dictionaries_and_other_fields_unchanged':p['reviews']==old['progress']['reviews'],
 'all_other_progress_domains_unchanged':all(p[k]==v for k,v in old['progress'].items() if k not in ['updated_utc','latest_parallel_import']),
 'all_existing_owner_ledgers_unchanged':all(u[k]==v for k,v in old['user'].items() if k!='updated_utc'),
 'no_six_field_count_increase':specification_counts(u)==u['specification_approval_counts']==old['user']['specification_approval_counts'] and c['interactive_review_state']==old['component']['interactive_review_state'],
 'nine_conditionals_seven_recoveries_214_current_numeric_48_references':len(ests)==9 and len(rec)==7 and len(out['scoped_overrides'])==16 and len(out['existing_numeric_scopes'])==214 and len(out['reference_dispositions'])==48,
 'all_278_scopes_unique_not_physical_count':len(set(out['scoped_overrides'])|set(out['existing_numeric_scopes'])|set(out['reference_dispositions']))==278 and out['counts_are_overlapping_review_scopes_not_unique_sculptures'],
 'no_set_mass_division':not policy['whole_set_weights_divided_into_components'] and all(not x['entire_set_mass_divided'] for x in ests) and all(not x.get('pair_weight_divided',False) for x in rec),
 'estimates_not_measured_material_or_construction_certificates':all(not x['actual_weight_measured'] and not x['physical_specs_verified'] and not x['assumed_material_identified_as_actual'] and not x['assumed_construction_independently_verified'] for x in ests),
 'no_individual_reply_or_other_five_field_change':all(x['individual_owner_reply'] is None and not x['new_individual_owner_reply'] and not x['other_five_fields_changed'] for x in ests),
 'current_later_working_scope_values_take_precedence':out['retain_current_scope_values_from_later_imports'],
 'owner_specific_weights_unchanged':p['reviews']['BC-MCP-4']['size_finish_variants']['MCP4-VERDIGRIS-RUST']==old['progress']['reviews']['BC-MCP-4']['size_finish_variants']['MCP4-VERDIGRIS-RUST'],
 'physical_counts_platforms_aliases_groups_preserved':c['counts']==old['component']['counts'] and all(p[k]==old['progress'][k] for k in ['canonical_component_consolidations','catalogue_design_aliases','offer_photo_bindings','arrangement_component_bindings','group_photo_review_policy','source_only_gap_reviews']),
 'root_current_answer_and_keyhole_count_preserved':all(cp[k]==v for k,v in old['walkthrough'].items() if k.startswith('current_')) and cp['current_answer_recorded'] and not cp['current_fixing_count_answer_recorded'],
 'root_component_mirror_exact':cur['root']['current_component_review']==c,
 'all_frozen_source_bytes_match':all(sha(ROOT/x['snapshot'])==x['sha256'] for x in read(HERE/'source-manifest.json')['files']),
 'protected_workbook_and_original_sources_match':all(sha(path)==v for path,v in r['protected_sha256'].items()),
 'shared_saved_bytes_match_receipt':all(sha(PATHS[k])==v for k,v in r['shared_after_sha256'].items()),
 'no_remote_mutations_or_new_downloads':r['summary']['remote_mutations']==r['summary']['root_new_private_original_downloads']==0,
 'canonical_standing_and_fixing_policies_not_replayed':u['working_specification_acceptance_policy_decisions']==old['user']['working_specification_acceptance_policy_decisions'] and u['global_fixing_choice_policy_decisions']==old['user']['global_fixing_choice_policy_decisions'],
 '48_reference_rows_no_fabricated_numeric_masses':all(x['reference_only'] and x['numeric_mass_assigned'] is None for x in out['reference_dispositions'].values()),
 'seven_recovered_values_not_new_estimates':all(x['existing_value_recovered_not_new_estimate'] for x in rec),
 'family_weight_kept_family_scoped':'BC-WALL-CIRCLE|BASE' in out['reference_dispositions'] and out['family_reference'] is not None,
}
chelsea=next(x for x in ests if x['component_id']=='BC-CHELSEA');knight=next(x for x in ests if x['component_id']=='BC-KNIGHT');bar=next(x for x in rec if x['component_id']=='BC-BAR-WAVE');glens=[x for x in ests if x['component_id'].startswith('BC-GLEN-')]
checks.update({
 'Chelsea_BASE_only_superseded25kg_not_reused':chelsea['scope']=='BASE' and chelsea['nominal_estimated_dry_artwork_kg']==100 and chelsea['working_range_kg']==[75,140] and 'source002' in chelsea['display'] and out['reference_dispositions']['BC-CHELSEA|SOURCE-G233002']['numeric_mass_assigned'] is None,
 'Knightsbridge_literal50cm_open_shell_not_solid_mass':knight['working_range_kg']==[60,180] and any('50cm is overall' in x for x in knight['assumptions']) and any('3m²' in x for x in knight['assumptions']) and 'No50mm' in knight['method'],
 'Gleneagles_four_individual35cm_models_no_group_division':len(glens)==4 and all(x['nominal_estimated_dry_artwork_kg']==5 and x['working_range_kg']==[3,8] for x in glens),
 'Barbados_existing83kg_source_unit_retained':'83 kg' in bar['display'] and bar['scope']=='BASE',
 'Chelsea_old_ID_access_failure_and_new_path_ID_candidate_explicit':len(out['current_native_metadata_exceptions'])==1 and out['current_native_metadata_exceptions'][0]['current_path_file_id']=='id:cnqzTNngPVsAAAAAAA53Gw' and not out['current_native_metadata_exceptions'][0]['exact_photograph_correspondence_reverified'],
})
guards={k:sha(v) for k,v in PATHS.items()};repeat=subprocess.run([sys.executable,str(ROOT/'components/reviews/import_weight_policy_90.py')],capture_output=True,text=True,check=True);checks['idempotent_repeat_no_shared_write']='ALREADY_IMPORTED_IDEMPOTENT_NO_WRITE' in repeat.stdout and all(sha(PATHS[k])==v for k,v in guards.items())
assert all(checks.values()),[k for k,v in checks.items() if not v]
write(HERE/'independent-readback.json',dict(status='PASS',checked_utc=datetime.now(timezone.utc).isoformat(),check_count=len(checks),checks={k:'PASS' for k in checks},import_receipt_sha256=sha(HERE/'import-receipt.json')))
event=dict(event_id=policy['policy_id'],event='ONE_GLOBAL_APPROXIMATE_WEIGHT_POLICY',batch=90,new_global_owner_policy_events=1,new_individual_owner_replies=0,new_six_field_acceptances=0,new_physical_counts=0,readback_sha256=sha(HERE/'independent-readback.json'))
for path in [ROOT/'components/reviews/identity_review_journal.jsonl',ROOT/'review_journal.jsonl']:
 if not any(json.loads(line).get('event_id')==event['event_id'] for line in path.read_text().splitlines() if line.strip()):
  with path.open('a') as f:f.write(json.dumps(event)+'\n')
print(json.dumps(dict(batch=90,status='PASS',checks=len(checks),readback_sha256=sha(HERE/'independent-readback.json'))))
