"""Independent exact-scope readback and single standing-policy audit."""
import copy,json,subprocess,sys
from datetime import datetime,timezone
from import_fountain_working_and_policy_80_81 import ROOT,PATHS,CONFIG,target,read,sha,write
batch=int(sys.argv[1]);cfg=CONFIG[batch];here=ROOT/f'components/reviews/parallel-import-2026-10-19-batch{batch}';old=read(here/'before-import.json');cur={k:read(v) for k,v in PATHS.items()};receipt=read(here/'import-receipt.json');decision=read(here/'working-specification-approval.json');u,p,cp,c=(cur[k] for k in ['user','progress','walkthrough','component']);node=target(p,cfg);prior=target(old['progress'],cfg);restored=copy.deepcopy(p['reviews'])
if batch==80:restored[cfg['cid']]['size_finish_variants'][cfg['vid']]=prior
else:restored[cfg['cid']]=prior
checks={f'prior_user_{k}_preserved':u[k]==v for k,v in old['user'].items() if k not in ['updated_utc','size_finish_variant_specification_decisions','specification_approval_counts','working_specification_acceptance_policy_decisions']}
checks.update({
 'one_exact_six_field_approval_added':u['size_finish_variant_specification_decisions'][:-1]==old['user']['size_finish_variant_specification_decisions'] and u['size_finish_variant_specification_decisions'][-1]['decision_id']==decision['decision_id'] and len(node['approved_proposal_ids'])==len(set(node['approved_proposal_ids']))==6,
 'six_unique_working_groups_added':u['specification_approval_counts']['proposal_groups']==c['interactive_review_state']['approved_proposal_groups']==cfg['count'] and cfg['count']==old['user']['specification_approval_counts']['proposal_groups']+6,
 'active_working_flags_not_physical_certification':node['all_six_working_specification_fields_accepted'] and all(x['owner_approved'] and not x['physical_value_verified'] for x in node['accepted_working_specifications'].values()) and not node['physical_specs_verified'] and not node['actual_stock_verified'] and node['fully_confirmed_specification_groups']==[],
 'original_six_and_prepared_source_dictionaries_retained':node['specification_proposals']==prior['specification_proposals']==decision['source_specification_proposals_retained'] and node['source_specifications_retained']==decision['source_specifications_retained'],
 'all_other_components_finishes_and_White15kg_unchanged':restored==old['progress']['reviews'] and p['reviews']['BC-FOUNTAIN-EG']['owner_stated_weight_kg']==15,
 'exact_owner_message_and_last_nonblank_card_verified':decision['authoritative_user_evidence']['line']==cfg['owner'] and decision['verified_review_card_evidence']['line']==cfg['card'] and decision['authoritative_user_evidence']['immediately_preceding_assistant']['line']==cfg['card'],
 'root175_unlimited_one_week_preserved_only_its_finish':p['reviews']['BC-MCP-4']['size_finish_variants']['MCP4-VERDIGRIS-RUST']['owner_stated_lead_time_weeks']==1 and 'owner_stated_stock_policy' not in node and 'owner_stated_lead_time_weeks' not in node and ('unknown' in node['accepted_working_specifications']['availability']['display'] or 'unconfirmed' in node['accepted_working_specifications']['availability']['display']),
 'scope_platform_mapping_not_promoted':node['platform_mapping']==prior['platform_mapping'] and 'not transferred' in node['scope'],
 'one_canonical_policy_with_both_exact_owner_inputs':len(u['working_specification_acceptance_policy_decisions'])==1 and p['working_specification_acceptance_policy']['policy_id'].endswith('LINE18928') and p['working_specification_acceptance_policy']['corroborating_owner_instructions'][0]['verified_user_evidence']['line']==29180,
 'no_repeat_working_questions_and_no_fabricated_replies':not cp['repeat_working_specification_confirmation_questions_required'] and not c['repeat_working_specification_confirmation_questions_required'] and p['working_specification_acceptance_policy']['no_individual_owner_replies_fabricated'] and p['working_specification_acceptance_policy']['future_applications_require_scoped_evidence'],
 'no_physical_stock_scene_or_unknown_certification_by_policy':not p['working_specification_acceptance_policy']['actual_stock_or_scene_provenance_certified'] and not p['working_specification_acceptance_policy']['unknown_values_filled'] and not p['working_specification_acceptance_policy']['remote_mutation_or_publication_authority_added'],
 'policy_mirrors_exact':p['working_specification_acceptance_policy']==cp['working_specification_acceptance_policy']==c['working_specification_acceptance_policy']==u['working_specification_acceptance_policy_decisions'][0],
 'context_limits_no_same_cast_or_client_claim':not node['photo_coverage']['individual_wider_room_established'] and not node['photo_coverage']['exact_physical_cast_identity_verified'] and node['photo_coverage']['installation_provenance']=='UNCONFIRMED',
 'one_new_scoped_gap_all_old_gaps_unchanged':{k:v for k,v in p['current_component_photograph_gaps'].items() if k!=cfg['vid']}==old['progress']['current_component_photograph_gaps'] and 'elsewhere unknown' in p['current_component_photograph_gaps'][cfg['vid']]['missing'],
 'root_commercial_answer_and_unknown_count_preserved':all(cp[k]==v for k,v in old['walkthrough'].items() if k.startswith('current_')) and cp['current_answer_recorded'] and not cp['current_fixing_count_answer_recorded'],
 'physical_counts_and_other_policies_unchanged':c['counts']==old['component']['counts'] and all(p[k]==old['progress'][k] for k in ['physical_manufacture_review_policy','group_photo_review_policy','duplicate_source_image_reviews','source_design_reviews','source_only_gap_reviews']),
 'root_component_mirror_exact':cur['root']['current_component_review']==c,
 'saved_shared_hashes_match':all(sha(PATHS[k])==v for k,v in receipt['shared_after_sha256'].items()),
 'all_frozen_sources_and_current_metadata_hashes_match':all(sha(ROOT/x['snapshot'])==x['sha256'] for x in read(here/'source-manifest.json')['files']),
 'published_workbook_and_protected_sources_unchanged':all(sha(path)==v for path,v in receipt['protected_sha256'].items()),
 'no_private_downloads_or_remote_writes':receipt['summary']['root_new_private_original_downloads']==receipt['summary']['remote_mutations']==0})
if batch==80:
 checks['current_Bronze_acceptance_is_standing_instruction_applied_to_exact_card']=node['working_acceptance_basis']=='OWNER_STANDING_INSTRUCTION_APPLIED_TO_CURRENT_CARD' and decision['authoritative_user_evidence']['text']=='answer affirmative to all questions fo this nature' and receipt['summary']['new_owner_policy_events']==1
 checks['Bronze15kg_remains_estimate_not_White_owner_value']='guess' in node['accepted_working_specifications']['weight']['display'] and 'owner_stated_weight_kg' not in node
 checks['historical83_review_not_claimed_new_census']='Prior83-file review is dated18October' in node['photo_coverage']['contextual_source_description']
else:
 checks['Med_direct_keep_and_no_duplicate_policy_event']=node['working_acceptance_basis']=='OWNER_DIRECT_EXPLICIT_KEEP' and 'Keep these six working specifications for Fountain Palm Mediterranean' in decision['user_statement'] and receipt['summary']['new_owner_policy_events']==0 and u['working_specification_acceptance_policy_decisions']==old['user']['working_specification_acceptance_policy_decisions']
 checks['Med9_views_and3_originals_bound_scope']='nine cached depictions' in node['photo_coverage']['contextual_source_description'] and 'shared family garden display' in p['current_component_photograph_gaps'][cfg['vid']]['room']
guards={k:sha(v) for k,v in PATHS.items()};repeat=subprocess.run([sys.executable,str(ROOT/'components/reviews/import_fountain_working_and_policy_80_81.py'),str(batch)],capture_output=True,text=True,check=True);checks['idempotent_repeat_NO_WRITE']='ALREADY_IMPORTED_IDEMPOTENT_NO_WRITE' in repeat.stdout and all(sha(PATHS[k])==v for k,v in guards.items())
assert all(checks.values()),[k for k,v in checks.items() if not v]
write(here/'independent-readback.json',{'status':'PASS','checked_utc':datetime.now(timezone.utc).isoformat(),'check_count':len(checks),'checks':{k:'PASS' for k in checks},'import_receipt_sha256':sha(here/'import-receipt.json')})
event={'event_id':decision['decision_id'],'event':'EXACT_FOUNTAIN_SIX_WORKING_FIELDS_AND_SCOPED_CONTEXT','batch':batch,'new_canonical_policy_events':1 if batch==80 else 0,'new_physical_counts':0,'readback_sha256':sha(here/'independent-readback.json')}
for path in [ROOT/'components/reviews/identity_review_journal.jsonl',ROOT/'review_journal.jsonl']:
 if not any(json.loads(line).get('event_id')==event['event_id'] for line in path.read_text().splitlines() if line.strip()):
  with path.open('a') as stream:stream.write(json.dumps(event)+'\n')
print(json.dumps({'batch':batch,'status':'PASS','checks':len(checks),'readback_sha256':sha(here/'independent-readback.json')}))
