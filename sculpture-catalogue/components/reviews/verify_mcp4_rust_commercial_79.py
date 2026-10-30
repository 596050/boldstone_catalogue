"""Independent exact-finish readback of owner commercial details."""
import copy,json,subprocess,sys
from datetime import datetime,timezone
from import_mcp4_rust_commercial_79 import ROOT,HERE,PATHS,CID,VID,QID,read,sha,write
old=read(HERE/'before-import.json');cur={k:read(v) for k,v in PATHS.items()};receipt=read(HERE/'import-receipt.json');decision=read(HERE/'owner-commercial-details.json');u,p,cp,c=(cur[k] for k in ['user','progress','walkthrough','component']);n=p['reviews'][CID]['size_finish_variants'][VID];prior=old['progress']['reviews'][CID]['size_finish_variants'][VID];restored=copy.deepcopy(p['reviews']);restored[CID]['size_finish_variants'][VID]=prior
checks={f'prior_user_{k}_preserved':u[k]==v for k,v in old['user'].items() if k not in ['updated_utc','size_finish_variant_specification_decisions','specification_approval_counts']}
checks.update({
 'one_two_field_approval_added':u['size_finish_variant_specification_decisions'][:-1]==old['user']['size_finish_variant_specification_decisions'] and u['size_finish_variant_specification_decisions'][-1]['decision_id']==decision['decision_id'] and len(decision['approved_proposal_ids'])==2,
 'working_count_increases_by_two_only':u['specification_approval_counts']['proposal_groups']==c['interactive_review_state']['approved_proposal_groups']==138,
 'price175_per_individual_panel_working':n['accepted_working_specifications']['individual_price']['amount']==175 and n['accepted_working_specifications']['individual_price']['sale_unit']=='One individual panel' and 'owner-accepted working price' in n['accepted_working_specifications']['individual_price']['display'],
 'MTO_unlimited_stock_one_week_owner_details':n['owner_stated_sale_status']=='Made to order' and n['owner_stated_stock_policy']=='Unlimited' and n['owner_stated_lead_time_weeks']==1 and n['accepted_working_specifications']['availability']['lead_time_weeks']==1,
 'no_unknown_stock_or_lead_in_active_display':'stock and lead time unknown' not in n['accepted_working_specifications']['availability']['display'] and 'stock: unlimited; lead time: 1 week' in n['accepted_working_specifications']['availability']['display'],
 'no_infinite_on_hand_or_live_platform_claim':n['actual_physical_stock_quantity'] is None and not n['actual_stock_verified'] and not n['existing_platform_match_confirmed'] and not decision['platform_inventory_settings_changed'],
 'original_proposals_and_four_owner_facts_preserved':n['specification_proposals']==prior['specification_proposals'] and all(n[k]==prior[k] for k in ['owner_confirmed_dimensions_cm','owner_confirmed_depth_qualifier','owner_stated_weight_kg','owner_stated_base_material','owner_stated_surface_finish','owner_stated_fixing_type','owner_stated_fixing_point_count']),
 'no_name_whole_six_or_independent_verification':not decision['all_six_owner_specification_fields_accepted'] and not n['proposals_approved'] and not n['physical_specs_verified'],
 'keyhole_count_stays_unknown':n['owner_stated_fixing_point_count'] is None and not cp['current_fixing_count_answer_recorded'],
 'all_other_reviews_and_finishes_unchanged':restored==old['progress']['reviews'],
 'root_question_answered_same_exact_finish':cp['current_question_id']==QID and cp['current_answer_recorded'] and cp['current_price_answer_recorded'] and cp['current_availability_answer_recorded'] and cp['current_owner_stock_policy']=='Unlimited' and cp['current_owner_lead_time_weeks']==1,
 'literal_owner_evidence_and_preceding_finish_verified':decision['authoritative_user_evidence']['line']==22292 and decision['authoritative_user_evidence']['immediately_preceding_assistant']['line']==22285 and 'stock  is unlimited and lead time is 1 week' in decision['user_statement'],
 'photo_ids_counts_and_other_policies_unchanged':c['counts']==old['component']['counts'] and n['primary_image_id']==prior['primary_image_id'] and n['current_dropbox_reference']==prior['current_dropbox_reference'] and all(p[k]==old['progress'][k] for k in ['current_component_photograph_gaps','group_photo_review_policy','physical_manufacture_review_policy','duplicate_source_image_reviews','source_design_reviews']),
 'root_component_mirror_exact':cur['root']['current_component_review']==c,
 'saved_shared_hashes_match':all(sha(PATHS[k])==v for k,v in receipt['shared_after_sha256'].items()),
 'source_snapshots_match':all(sha(ROOT/x['snapshot'])==x['sha256'] for x in read(HERE/'source-manifest.json')['files']),
 'published_book_and_protected_sources_unchanged':all(sha(path)==v for path,v in receipt['protected_sha256'].items()),
 'no_remote_writes_or_private_downloads':receipt['summary']['remote_mutations']==receipt['summary']['root_new_private_original_downloads']==0})
guards={k:sha(v) for k,v in PATHS.items()};repeat=subprocess.run([sys.executable,str(ROOT/'components/reviews/import_mcp4_rust_commercial_79.py')],capture_output=True,text=True,check=True);checks['idempotent_repeat_NO_WRITE']='ALREADY_IMPORTED_IDEMPOTENT_NO_WRITE' in repeat.stdout and all(sha(PATHS[k])==v for k,v in guards.items())
assert all(checks.values()),[k for k,v in checks.items() if not v]
write(HERE/'independent-readback.json',{'status':'PASS','checked_utc':datetime.now(timezone.utc).isoformat(),'check_count':len(checks),'checks':{k:'PASS' for k in checks},'import_receipt_sha256':sha(HERE/'import-receipt.json')})
event={'event_id':decision['decision_id'],'event':'MCP4_RUST_PRICE_MTO_UNLIMITED_STOCK_ONE_WEEK_RECORDED','batch':79,'new_working_field_groups':2,'new_physical_counts':0,'readback_sha256':sha(HERE/'independent-readback.json')}
for path in [ROOT/'components/reviews/identity_review_journal.jsonl',ROOT/'review_journal.jsonl']:
 if not any(json.loads(line).get('event_id')==event['event_id'] for line in path.read_text().splitlines() if line.strip()):
  with path.open('a') as stream:stream.write(json.dumps(event)+'\n')
print(json.dumps({'batch':79,'status':'PASS','checks':len(checks),'readback_sha256':sha(HERE/'independent-readback.json')}))
