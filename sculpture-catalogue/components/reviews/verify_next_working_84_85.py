"""Independent scope-preservation, evidence and idempotency readback."""
import copy,json,subprocess,sys
from datetime import datetime,timezone
from import_next_working_84_85 import ROOT,PATHS,CONFIG,FIELDS,target,read,sha,write
batch=int(sys.argv[1]);cfg=CONFIG[batch];here=ROOT/f'components/reviews/parallel-import-2026-10-19-batch{batch}';old=read(here/'before-import.json');cur={k:read(v) for k,v in PATHS.items()};receipt=read(here/'import-receipt.json');u,p,cp,c=(cur[k] for k in ['user','progress','walkthrough','component']);restored=copy.deepcopy(p);checks={}
for item in receipt['scopes']:
 cid,vid=item['component_id'],item['size_finish_variant_id'];node,kind=target(p,cid,vid);prior,_=target(old['progress'],cid,vid);decision=read(ROOT/item['approval_record']);r,_=target(restored,cid,vid);r.clear();r.update(copy.deepcopy(prior))
 checks.update({vid+':'+k:v for k,v in {
  'source_six_and_historical_dictionaries_unchanged':node['specification_proposals']==prior['specification_proposals']==decision.get('source_current_specification_proposals_retained',decision['source_specification_proposals_retained']) and node['source_specifications_retained']==decision['source_specifications_retained'],
  'six_working_values_not_measurements_or_stock':node['all_six_working_specification_fields_accepted'] and len(node['approved_proposal_ids'])==len(set(node['approved_proposal_ids']))==6 and set(node['accepted_working_specifications'])==set(FIELDS) and all(x['owner_approved'] and not x['physical_value_verified'] for x in node['accepted_working_specifications'].values()) and not node['physical_specs_verified'] and not node['actual_stock_verified'],
  'canonical_policy_not_individual_owner_reply':node['working_acceptance_basis']=='DERIVED_FROM_STANDING_OWNER_POLICY' and node['standing_working_approval_policy_id']==p['working_specification_acceptance_policy']['policy_id'] and decision['owner_answer_for_this_scope'] is None and decision['new_individual_owner_reply_events']==0 and 'authoritative_user_evidence' not in decision,
  'names_platform_and_primary_stable_ids_unchanged':all(node[k]==prior[k] for k in ['canonical_name','identity_confirmed','primary_image_id','primary_folder_id','platform_mapping']),
  'fresh_exact_file_folder_binding':node['current_dropbox_reference']['file_id']==node['primary_image_id'] and node['current_dropbox_reference']['folder_id']==node['primary_folder_id'] and node['current_dropbox_reference']['file_path'].rsplit('/',1)[0]==node['current_dropbox_reference']['folder_path'],
  'scoped_gap_not_global_absence_or_cast_certification':p['current_component_photograph_gaps'][vid]['review_scope']==kind and 'elsewhere unknown' in p['current_component_photograph_gaps'][vid]['missing'].lower() and not node['photo_coverage']['exact_physical_cast_identity_verified'] and node['photo_coverage']['installation_provenance']=='UNCONFIRMED',
  'MCP4_owner_weight_stock_and_lead_not_transferred':'owner_stated_stock_policy' not in node and 'owner_stated_lead_time_weeks' not in node and 'owner_stated_weight_kg' not in node and ('unknown' in node['accepted_working_specifications']['availability']['display'] or 'unconfirmed' in node['accepted_working_specifications']['availability']['display']),
  'no_repeated_owner_question_or_stale_unapproved_price':not p['pending_specification_checks'][vid+'-WORKING-SPECS-01']['owner_answer_recorded'] and not p['pending_specification_checks'][vid+'-WORKING-SPECS-01']['individual_owner_reply_required'] and 'unapproved' not in node['accepted_working_specifications']['individual_price']['display'].lower(),
 }.items()})
n=cfg['scopes'];checks.update({
 'exact_scoped_acceptances_and_unique_working_groups_added':len(u['size_finish_variant_specification_decisions'])==len(old['user']['size_finish_variant_specification_decisions'])+n and u['size_finish_variant_specification_decisions'][:-n]==old['user']['size_finish_variant_specification_decisions'] and u['specification_approval_counts']['proposal_groups']==c['interactive_review_state']['approved_proposal_groups']==cfg['count'] and cfg['count']==old['user']['specification_approval_counts']['proposal_groups']+6*n,
 'single_canonical_policy_unchanged':u['working_specification_acceptance_policy_decisions']==old['user']['working_specification_acceptance_policy_decisions'] and len(u['working_specification_acceptance_policy_decisions'])==1 and p['working_specification_acceptance_policy']==old['progress']['working_specification_acceptance_policy']==cp['working_specification_acceptance_policy']==c['working_specification_acceptance_policy'],
 'all_other_review_nodes_and_fields_unchanged':restored['reviews']==old['progress']['reviews'],
 'all_prior_photo_gaps_preserved':{k:v for k,v in p['current_component_photograph_gaps'].items() if k not in {x['size_finish_variant_id'] for x in receipt['scopes']}}==old['progress']['current_component_photograph_gaps'],
 'all_other_owner_records_unchanged':all(u[k]==v for k,v in old['user'].items() if k not in ['updated_utc','size_finish_variant_specification_decisions','specification_approval_counts']),
 'physical_counts_and_unresolved_designs_unchanged':c['counts']==old['component']['counts'] and all(p[k]==old['progress'][k] for k in ['physical_manufacture_review_policy','group_photo_review_policy','duplicate_source_image_reviews','source_design_reviews','source_only_gap_reviews']),
 'root_answer_and_unknown_keyhole_count_preserved':all(cp[k]==v for k,v in old['walkthrough'].items() if k.startswith('current_')) and cp['current_answer_recorded'] and not cp['current_fixing_count_answer_recorded'] and p['reviews']['BC-MCP-4']['size_finish_variants']['MCP4-VERDIGRIS-RUST']['owner_stated_lead_time_weeks']==1,
 'no_repeat_working_questions':not cp['repeat_working_specification_confirmation_questions_required'],
 'root_component_mirror_exact':cur['root']['current_component_review']==c,
 'saved_shared_hashes_match':all(sha(PATHS[k])==v for k,v in receipt['shared_after_sha256'].items()),
 'all_frozen_sources_and_metadata_hashes_match':all(sha(ROOT/x['snapshot'])==x['sha256'] for x in read(here/'source-manifest.json')['files']),
 'published_workbook_and_original_source_protected':all(sha(path)==v for path,v in receipt['protected_sha256'].items()),
 'zero_downloads_remote_writes_owner_replies_and_new_policies':all(receipt['summary'][k]==0 for k in ['root_new_private_original_downloads','remote_mutations','new_owner_policy_events','new_individual_owner_reply_events']),
})
if batch==84:
 white=[target(p,f'BC-MCP-{i}',f'MCP{i}-WHITE')[0] for i in [1,2,3]]
 checks['White_maker_trade_retail_weights_separate']=all(all(term in node['accepted_working_specifications']['weight']['display'] for term in ['2–4kg','trade4kg','retail5kg','unweighed']) for node in white)
 checks['White_shared_series_context_retained_without_physical_count']=all(node['photo_coverage']['contextual_file_ids']==['id:cnqzTNngPVsAAAAAAAugDQ'] for node in white)
 checks['Blue_price_not_exact_offer_and_rear_unseen']='exact Blue offer unconfirmed' in target(p,'BC-MCP-2','MCP2-BLUE-SPLASHES')[0]['accepted_working_specifications']['individual_price']['display'] and 'rear unseen' in target(p,'BC-MCP-2','MCP2-BLUE-SPLASHES')[0]['accepted_working_specifications']['fixing']['display']
 checks['two_current_CDN_associations_unverified_historical_matches_retained']=all(target(p,f'BC-MCP-{i}',f'MCP{i}-VERDIGRIS-RUST')[0]['current_public_image_association_verified'] is False and '19October' in target(p,f'BC-MCP-{i}',f'MCP{i}-VERDIGRIS-RUST')[0]['photo_coverage']['contextual_source_description'] for i in [2,3])
else:
 e=target(p,'BC-EMBED-SHELLS','EMBED-SHELLS-WHITE')[0];f=target(p,'BC-FACET-MOUND','FACET-MOUND-GOLD-LEAF')[0]
 checks['Embedded_owner70x15_overrides100x25_guess_without_overwriting_source']='70 H × 15 W cm — owner-stated' in e['accepted_working_specifications']['dimensions']['display'] and '100' not in e['accepted_working_specifications']['dimensions']['display'] and e['specification_proposals']==target(old['progress'],'BC-EMBED-SHELLS','EMBED-SHELLS-WHITE')[0]['specification_proposals']
 checks['Embedded_smaller_size_revised_weight_and_price_scenarios']='4–6kg' in e['accepted_working_specifications']['weight']['display'] and '£250–£350' in e['accepted_working_specifications']['individual_price']['display']
 checks['Faceted_all_estimates_and_recipe_unknown_retained']='planning guess' in f['accepted_working_specifications']['dimensions']['display'] and '6–10kg' in f['accepted_working_specifications']['weight']['display'] and 'binder and metal unknown' in f['accepted_working_specifications']['material_finish']['display']
 checks['both_room_presentations_not_installation_certificates']=all(node['photo_coverage']['individual_wider_room_established'] and not node['photo_coverage']['rear_reference_established'] for node in [e,f])
guards={k:sha(v) for k,v in PATHS.items()};repeat=subprocess.run([sys.executable,str(ROOT/'components/reviews/import_next_working_84_85.py'),str(batch)],capture_output=True,text=True,check=True);checks['idempotent_repeat_NO_WRITE']='ALREADY_IMPORTED_IDEMPOTENT_NO_WRITE' in repeat.stdout and all(sha(PATHS[k])==v for k,v in guards.items());assert all(checks.values()),[k for k,v in checks.items() if not v]
write(here/'independent-readback.json',{'status':'PASS','checked_utc':datetime.now(timezone.utc).isoformat(),'check_count':len(checks),'checks':{k:'PASS' for k in checks},'import_receipt_sha256':sha(here/'import-receipt.json')})
for item in receipt['scopes']:
 event={'event_id':item['decision_id'],'event':'SIX_WORKING_FIELDS_UNDER_EXISTING_OWNER_POLICY','batch':batch,'new_owner_reply_events':0,'new_policy_events':0,'new_physical_counts':0,'readback_sha256':sha(here/'independent-readback.json')}
 for path in [ROOT/'components/reviews/identity_review_journal.jsonl',ROOT/'review_journal.jsonl']:
  if not any(json.loads(line).get('event_id')==event['event_id'] for line in path.read_text().splitlines() if line.strip()):
   with path.open('a') as stream:stream.write(json.dumps(event)+'\n')
print(json.dumps({'batch':batch,'status':'PASS','checks':len(checks),'readback_sha256':sha(here/'independent-readback.json')}))
