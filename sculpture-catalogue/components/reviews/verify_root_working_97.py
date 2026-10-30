"""Saved-model readback for the legacy normalisation, independent of projection."""
import copy,json,subprocess,sys
from datetime import datetime,timezone
from import_root_working_97 import ROOT,HERE,SOURCE,PATHS,read,write,sha,at,FIELDS

r=read(HERE/'import-receipt.json');old=read(HERE/'before-import.json');cur={k:read(v) for k,v in PATHS.items()};u,p,cp,c=(cur[k] for k in ['user','progress','walkthrough','component']);prep=read(SOURCE/'ROOT97_PREPARED.json');restored=copy.deepcopy(p);checks={}
for x in r['scopes']:
 key=x['component_id']+'|'+x['size_finish_variant_id'];node=at(p,x['model_locator']);prior=at(old['progress'],x['model_locator']);d=read(ROOT/x['approval_record']);active=node['accepted_working_specifications'];back=at(restored,x['model_locator']);back.clear();back.update(copy.deepcopy(prior))
 tests={
 'raw_source_identity_offer_and_owner_subfields_retained':all(node.get(k)==prior.get(k) for k in ['specification_proposals','specifications','specification_review_items','available','dimensions_available','weight_available','material_available','fixing_available','platform_mapping','primary_image_id','primary_file_id','primary_folder_id','component_id','maker_panel_code','canonical_name','identity_confirmed','user_face_dimensions_cm','owner_face_dimension_decision','user_weight_kg','owner_weight_decision','owner_material_decision','owner_fixing_type_decision']),
 'six_exact_prepared_displays_IDs_and_basis':set(active)==set(FIELDS) and node['approved_proposal_ids']==d['approved_proposal_ids'] and all(active[k]['display']==d['specifications'][k]['display'] and active[k].get('basis')==d['specifications'][k].get('basis') for k in FIELDS),
 'standing_working_not_new_reply_or_measurement':node['all_six_working_specification_fields_accepted'] and node['owner_answer_for_this_scope'] is None and d['new_individual_owner_reply_events']==0 and all(x['owner_approved'] and not x['physical_value_verified'] for x in active.values()) and not node['physical_specs_verified'] and not node['actual_stock_verified'],
 'current_native_IDs_and_containing_folder':node['current_dropbox_reference']['file_path'].rsplit('/',1)[0]==node['current_dropbox_reference']['folder_path'] and node['current_dropbox_reference']['file_id']==d['current_reference']['file_id'] and node['current_dropbox_reference']['folder_id']==d['current_reference']['folder_id'],
 'bounded_photo_gap_and_scope_no_cast_certification':p['current_component_photograph_gaps'][x['photo_gap_id']]['model_locator']==x['model_locator'] and 'elsewhere unknown' in p['current_component_photograph_gaps'][x['photo_gap_id']]['missing'] and not node['photo_coverage']['exact_physical_cast_identity_verified'],
 'exact_new_decision_once':sum(z.get('decision_id')==d['decision_id'] for z in u[x['ledger']])==1,
 }
 checks.update({key+':'+k:v for k,v in tests.items()})
bar=p['reviews']['BC-BAR-WAVE'];barold=old['progress']['reviews']['BC-BAR-WAVE'];back=restored['reviews']['BC-BAR-WAVE'];back.clear();back.update(copy.deepcopy(barold));back=restored['reviews']['BC-PORTMAN-1'];back.clear();back.update(copy.deepcopy(old['progress']['reviews']['BC-PORTMAN-1']))
checks.update({
 'all_other_review_alias_and_source_nodes_unchanged':all(restored[k]==old['progress'][k] for k in ['reviews','catalogue_alias_reviews','source_design_reviews']),
 'Barbados_preexisting_six_IDs_no_new_approval':bar['specification_review_items']==barold['specification_review_items'] and [bar['accepted_working_specifications'][f]['proposal_id'] for f in FIELDS]==['BARWAVE-DIMENSIONS','BARWAVE-WEIGHT','BARWAVE-MATERIAL','BARWAVE-FIXING','BARWAVE-PRICE','BARWAVE-AVAILABILITY'] and not any(x.get('component_id')=='BC-BAR-WAVE' for x in u['specification_decisions'][len(old['user']['specification_decisions']):]),
 'exact_70_new_groups_total1045':u['specification_approval_counts']['proposal_groups']==1045 and old['user']['specification_approval_counts']['proposal_groups']==975 and c['interactive_review_state']['approved_proposal_groups']==1045,
 'all_prior_ledger_entries_preserved':all(u[k][:len(old['user'].get(k,[]))]==old['user'].get(k,[]) for k in ['specification_decisions','build_variant_decisions','size_finish_variant_specification_decisions']),
 'exact_twelve_new_decisions':sum(len(u.get(k,[]))-len(old['user'].get(k,[])) for k in ['specification_decisions','build_variant_decisions','size_finish_variant_specification_decisions'])==12,
 'all_other_owner_records_unchanged':all(u[k]==v for k,v in old['user'].items() if k not in ['specification_decisions','size_finish_variant_specification_decisions','updated_utc','specification_approval_counts']),
 'policies_not_replayed':all(cur[k].get(name)==old[k].get(name) for k in ['user','progress','walkthrough','component'] for name in ['working_specification_acceptance_policy','working_specification_acceptance_policy_decisions','global_fixing_choice_policy','global_fixing_choice_policy_decisions','global_approximate_weight_policy','global_approximate_weight_policy_decisions']),
 'physical_counts_and_platform_evidence_unchanged':c['counts']==old['component']['counts'] and all(p[k]==old['progress'][k] for k in ['offer_photo_bindings','arrangement_component_bindings','canonical_component_consolidations','canonical_variant_aliases','catalogue_design_aliases','group_photo_review_policy','weight_review_output_overlays']),
 'owner_current_answers_and_unknown_fixing_count_preserved':all(cp[k]==v for k,v in old['walkthrough'].items() if k.startswith('current_')) and cp['current_answer_recorded'] and not cp['current_fixing_count_answer_recorded'],
 'root_component_mirror_exact':cur['root']['current_component_review']==c,
 'published91_and_source_bytes_retained':all(sha(path)==digest for path,digest in r['protected_sha256'].items()),
 'frozen_preparation_media_and_independent_critique':all(sha(ROOT/x['snapshot'])==x['sha256'] for x in read(HERE/'source-manifest.json')['files']),
 'saved_master_hashes_match_receipt':all(sha(PATHS[k])==v for k,v in r['shared_after_sha256'].items()),
 'root_eight_comparison_plates_actually_seen':read(HERE/'parent-visual-inspection.json')['all_eight_comparison_plates_actually_inspected'],
 'two_reference_dispositions_no_new_sale_unit':set(p['working_review_reference_dispositions'])=={'BC-MCP-4|BASE','BC-PORTMAN-1|BASE'} and not p['reviews']['BC-PORTMAN-1'].get('all_six_working_specification_fields_accepted') and not p['reviews']['BC-MCP-4'].get('all_six_working_specification_fields_accepted'),
})
vr=p['reviews']['BC-MCP-4']['size_finish_variants']['MCP4-VERDIGRIS-RUST'];vrold=old['progress']['reviews']['BC-MCP-4']['size_finish_variants']['MCP4-VERDIGRIS-RUST'];a=vr['accepted_working_specifications'];checks['root_Verdigris_Rust_commercial_owner_values_retained']=all(a[f]['display']==vrold['accepted_working_specifications'][f]['display'] for f in ['individual_price','availability']) and '175' in a['individual_price']['display'] and '4' in a['weight']['display'] and all(t in a['availability']['display'].lower() for t in ['unlimited','1 week'])
checks['per_panel_uncosted_Ammonite_prices_not_pair_division']=all(('uncosted' in p['reviews'][cid]['accepted_working_specifications']['individual_price']['display'] and 'Neither proposal divides' in p['reviews'][cid]['accepted_working_specifications']['individual_price']['basis']) for cid in ['AM-S1','AM-S2','AM-L1','AM-L2'])
checks['Brancusi_White_not_Gold_and_set_not_divided']=all('£250' in p['reviews'][cid]['accepted_working_specifications']['individual_price']['display'] and '£312.50' in p['reviews'][cid]['accepted_working_specifications']['individual_price']['display'] and 'not divided' in p['reviews'][cid]['accepted_working_specifications']['individual_price']['basis'] for cid in ['BC-BR-1','BC-BR-2'])
guards={k:sha(v) for k,v in PATHS.items()};replay=subprocess.run([sys.executable,str(ROOT/'components/reviews/import_root_working_97.py')],check=True,capture_output=True,text=True);checks['idempotent_replay_no_write']='ALREADY_IMPORTED_IDEMPOTENT_NO_WRITE' in replay.stdout and all(sha(PATHS[k])==v for k,v in guards.items())
assert all(checks.values()),[k for k,v in checks.items() if not v]
write(HERE/'independent-readback.json',dict(status='PASS',checked_utc=datetime.now(timezone.utc).isoformat(),check_count=len(checks),checks={k:'PASS' for k in checks},import_receipt_sha256=sha(HERE/'import-receipt.json')))
for x in r['scopes']:
 event=dict(event_id=x['decision_id'],event='EXISTING_COMPONENT_WORKING_NORMALIZATION',batch=97,new_owner_reply_events=0,new_policy_events=0,new_physical_counts=0,readback_sha256=sha(HERE/'independent-readback.json'))
 for path in [ROOT/'components/reviews/identity_review_journal.jsonl',ROOT/'review_journal.jsonl']:
  if not any(json.loads(line).get('event_id')==event['event_id'] for line in path.read_text().splitlines() if line.strip()):
   with path.open('a') as f:f.write(json.dumps(event)+'\n')
print(json.dumps(dict(batch=97,status='PASS',checks=len(checks),new_working_groups=70,total_groups=1045)))
