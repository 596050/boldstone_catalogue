"""Independent bounded-change readback of standing-policy Leaf acceptances."""
import copy,json,subprocess,sys
from datetime import datetime,timezone
from import_leaf_policy_working_82_83 import ROOT,PATHS,CONFIG,FIELDS,target,read,sha,write
batch=int(sys.argv[1]);cfg=CONFIG[batch];here=ROOT/f'components/reviews/parallel-import-2026-10-19-batch{batch}';old=read(here/'before-import.json');cur={k:read(v) for k,v in PATHS.items()};receipt=read(here/'import-receipt.json');u,p,cp,c=(cur[k] for k in ['user','progress','walkthrough','component']);restored=copy.deepcopy(p);checks={}
for item in receipt['scopes']:
 cid,vid=item['component_id'],item['size_finish_variant_id'];node,kind=target(p,cid,vid);prior,_=target(old['progress'],cid,vid);decision=read(ROOT/item['approval_record']);r,_=target(restored,cid,vid);r.clear();r.update(copy.deepcopy(prior))
 checks.update({vid+':'+k:v for k,v in {
  'source_six_and_historical_dictionaries_unchanged':node['specification_proposals']==prior['specification_proposals']==decision['source_specification_proposals_retained'] and node['source_specifications_retained']==decision['source_specifications_retained'],
  'six_working_values_accepted_not_measured_or_stock_certified':node['all_six_working_specification_fields_accepted'] and len(node['approved_proposal_ids'])==len(set(node['approved_proposal_ids']))==6 and set(node['accepted_working_specifications'])==set(FIELDS) and all(x['owner_approved'] and not x['physical_value_verified'] for x in node['accepted_working_specifications'].values()) and not node['physical_specs_verified'] and not node['actual_stock_verified'],
  'canonical_policy_not_individual_owner_reply':node['working_acceptance_basis']=='DERIVED_FROM_STANDING_OWNER_POLICY' and node['standing_working_approval_policy_id']==p['working_specification_acceptance_policy']['policy_id'] and decision['owner_answer_for_this_scope'] is None and decision['new_individual_owner_reply_events']==0 and 'authoritative_user_evidence' not in decision,
  'name_platform_primary_and_all_other_finish_ids_unchanged':all(node[k]==prior[k] for k in ['canonical_name','identity_confirmed','primary_image_id','primary_folder_id','platform_mapping']),
  'fresh_exact_file_folder_binding':node['current_dropbox_reference']['file_id']==node['primary_image_id'] and node['current_dropbox_reference']['folder_id']==node['primary_folder_id'] and node['current_dropbox_reference']['file_path'].rsplit('/',1)[0]==node['current_dropbox_reference']['folder_path'],
  'scoped_gap_not_unqualified_absence':p['current_component_photograph_gaps'][vid]['review_scope']==kind and 'elsewhere unknown' in p['current_component_photograph_gaps'][vid]['missing'] and not node['photo_coverage']['exact_physical_cast_identity_verified'] and node['photo_coverage']['installation_provenance']=='UNCONFIRMED',
  'MCP4_stock_and_lead_not_transferred':'owner_stated_stock_policy' not in node and 'owner_stated_lead_time_weeks' not in node and ('unknown' in node['accepted_working_specifications']['availability']['display'] or 'unconfirmed' in node['accepted_working_specifications']['availability']['display']),
  'no_repeat_owner_question':not p['pending_specification_checks'][vid+'-WORKING-SPECS-01']['owner_answer_recorded'] and not p['pending_specification_checks'][vid+'-WORKING-SPECS-01']['individual_owner_reply_required'],
 }.items()})
checks.update({
 'three_exact_acceptances_and18_working_groups_added':len(u['size_finish_variant_specification_decisions'])==len(old['user']['size_finish_variant_specification_decisions'])+3 and u['size_finish_variant_specification_decisions'][:-3]==old['user']['size_finish_variant_specification_decisions'] and u['specification_approval_counts']['proposal_groups']==c['interactive_review_state']['approved_proposal_groups']==cfg['count'],
 'single_canonical_policy_unchanged':u['working_specification_acceptance_policy_decisions']==old['user']['working_specification_acceptance_policy_decisions'] and len(u['working_specification_acceptance_policy_decisions'])==1 and p['working_specification_acceptance_policy']==old['progress']['working_specification_acceptance_policy']==cp['working_specification_acceptance_policy']==c['working_specification_acceptance_policy'],
 'all_other_review_nodes_unchanged':restored['reviews']==old['progress']['reviews'],
 'all_prior_photograph_gaps_unchanged':{k:v for k,v in p['current_component_photograph_gaps'].items() if k not in {x['size_finish_variant_id'] for x in receipt['scopes']}}==old['progress']['current_component_photograph_gaps'],
 'all_other_owner_records_unchanged':all(u[k]==v for k,v in old['user'].items() if k not in ['updated_utc','size_finish_variant_specification_decisions','specification_approval_counts']),
 'physical_counts_and_unresolved_designs_unchanged':c['counts']==old['component']['counts'] and all(p[k]==old['progress'][k] for k in ['physical_manufacture_review_policy','group_photo_review_policy','duplicate_source_image_reviews','source_design_reviews','source_only_gap_reviews']),
 'root_commercial_answer_and_unknown_keyhole_count_preserved':all(cp[k]==v for k,v in old['walkthrough'].items() if k.startswith('current_')) and cp['current_answer_recorded'] and not cp['current_fixing_count_answer_recorded'] and p['reviews']['BC-MCP-4']['size_finish_variants']['MCP4-VERDIGRIS-RUST']['owner_stated_lead_time_weeks']==1,
 'no_repeat_working_questions':not cp['repeat_working_specification_confirmation_questions_required'],
 'root_component_mirror_exact':cur['root']['current_component_review']==c,
 'saved_shared_hashes_match':all(sha(PATHS[k])==v for k,v in receipt['shared_after_sha256'].items()),
 'all_frozen_sources_and_metadata_hashes_match':all(sha(ROOT/x['snapshot'])==x['sha256'] for x in read(here/'source-manifest.json')['files']),
 'published_workbook_and_sources_unchanged':all(sha(path)==v for path,v in receipt['protected_sha256'].items()),
 'zero_downloads_remote_writes_owner_replies_and_policy_events':all(receipt['summary'][k]==0 for k in ['root_new_private_original_downloads','remote_mutations','new_owner_policy_events','new_individual_owner_reply_events']),
})
if batch==82:
 curve=target(p,'BC-LEAF-CURVE','LEAF-CURVE-WHITE-GOLD')[0];white=target(p,'BC-LEAF-GROWTH','LEAF-GROWTH-WHITE')[0];gold=target(p,'BC-LEAF-GROWTH','LEAF-GROWTH-WHITE-GOLD')[0]
 checks['Curve_scale_weight_price_remain_guesses_or_range']='guess' in curve['accepted_working_specifications']['dimensions']['display'] and 'conditional' in curve['accepted_working_specifications']['weight']['display'] and '£250–£350' in curve['accepted_working_specifications']['individual_price']['display']
 checks['Growth_White18vs12_conflict_not_averaged']='18kg' in white['accepted_working_specifications']['weight']['display'] and '12kg' in white['accepted_working_specifications']['weight']['display'] and 'unresolved' in white['accepted_working_specifications']['weight']['display']
 checks['Growth_Gold_conditional_and_detail_only']='conditional' in gold['accepted_working_specifications']['dimensions']['display'] and not gold['photo_coverage']['contextual_images_available'] and not gold['photo_coverage']['contextual_file_ids'] and 'cropped' in p['current_component_photograph_gaps']['LEAF-GROWTH-WHITE-GOLD']['front'].lower()
 checks['accepted_prices_do_not_say_owner_adoption_pending']=all('owner adoption pending' not in target(p,x['component_id'],x['size_finish_variant_id'])[0]['accepted_working_specifications']['individual_price']['display'] for x in receipt['scopes'])
else:
 checks['White_positions_not_new_BC_components']=all(target(p,'BC-LEAF-FORM',vid)[1]=='COMPONENT_LAYOUT' for vid in ['LEAF-FORM-LF1-WHITE','LEAF-FORM-LF2-WHITE']) and c['counts']==old['component']['counts']
 checks['LF1_primary_is050_not_LF2_clean001']=target(p,'BC-LEAF-FORM','LEAF-FORM-LF1-WHITE')[0]['primary_image_id']=='id:cnqzTNngPVsAAAAAAAs6hg' and target(p,'BC-LEAF-FORM','LEAF-FORM-LF2-WHITE')[0]['primary_image_id']=='id:cnqzTNngPVsAAAAAAAylMg'
 checks['White_exhibition_and_Gold_room_context_separate']=all('indoor exhibition' in target(p,'BC-LEAF-FORM',vid)[0]['photo_coverage']['contextual_source_status'] for vid in ['LEAF-FORM-LF1-WHITE','LEAF-FORM-LF2-WHITE']) and target(p,'BC-LEAF-FORM','LEAF-FORM-GOLD')[0]['photo_coverage']['contextual_file_ids']==['id:cnqzTNngPVsAAAAAAAuROg']
guards={k:sha(v) for k,v in PATHS.items()};repeat=subprocess.run([sys.executable,str(ROOT/'components/reviews/import_leaf_policy_working_82_83.py'),str(batch)],capture_output=True,text=True,check=True);checks['idempotent_repeat_NO_WRITE']='ALREADY_IMPORTED_IDEMPOTENT_NO_WRITE' in repeat.stdout and all(sha(PATHS[k])==v for k,v in guards.items())
assert all(checks.values()),[k for k,v in checks.items() if not v]
write(here/'independent-readback.json',{'status':'PASS','checked_utc':datetime.now(timezone.utc).isoformat(),'check_count':len(checks),'checks':{k:'PASS' for k in checks},'import_receipt_sha256':sha(here/'import-receipt.json')})
for item in receipt['scopes']:
 event={'event_id':item['decision_id'],'event':'SIX_WORKING_FIELDS_UNDER_EXISTING_OWNER_POLICY','batch':batch,'new_owner_reply_events':0,'new_policy_events':0,'new_physical_counts':0,'readback_sha256':sha(here/'independent-readback.json')}
 for path in [ROOT/'components/reviews/identity_review_journal.jsonl',ROOT/'review_journal.jsonl']:
  if not any(json.loads(line).get('event_id')==event['event_id'] for line in path.read_text().splitlines() if line.strip()):
   with path.open('a') as stream:stream.write(json.dumps(event)+'\n')
print(json.dumps({'batch':batch,'status':'PASS','checks':len(checks),'readback_sha256':sha(here/'independent-readback.json')}))
