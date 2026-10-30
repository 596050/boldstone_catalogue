"""Bound publication87 to nine scopes, two owner facts and one offered-choice overlay."""
import hashlib,json
from datetime import datetime,timezone
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2];read=lambda p:json.loads(p.read_text())
baseline='080536aa2867b5c3b330176eebf3f2c522ea827d6c05acd78a2750c4d07c2c79';old=read(HERE/'history'/baseline/'refresh-data.json');new=read(HERE/'refresh-data.json');model=read(ROOT/'components/evidence/component_register.json')
scopes={('BC-MCP-1','MCP1-WHITE'),('BC-MCP-1','MCP1-VERDIGRIS-RUST'),('BC-MCP-2','MCP2-WHITE'),('BC-MCP-2','MCP2-BLUE-SPLASHES'),('BC-MCP-2','MCP2-VERDIGRIS-RUST'),('BC-MCP-3','MCP3-WHITE'),('BC-MCP-3','MCP3-VERDIGRIS-RUST'),('BC-EMBED-SHELLS','EMBED-SHELLS-WHITE'),('BC-FACET-MOUND','FACET-MOUND-GOLD-LEAF')};checks={};deltas={}
for key,fn in [('reviews',lambda x:tuple(x[:2])),('specifications',lambda x:(*x[:2],x[3]))]:
 a={fn(x):x for x in old[key]};b={fn(x):x for x in new[key]};checks[key+'_stable_scope_keys_preserved']=a.keys()==b.keys();diff={k:[i for i,(x,y) in enumerate(zip(a[k],b[k])) if x!=y] for k in a if a[k]!=b[k]};deltas[key]=[{'key':k,'columns':v} for k,v in diff.items()]
 if key=='reviews':checks['exact_nine_existing_review_scopes_only']=set(diff)==scopes;checks['names_ids_platform_and_primary_ids_unchanged']=all(not(set(v)&{0,1,2,3,4,6,9,10}) for v in diff.values())
 else:
  expected={(cid,vid,f) for cid,vid in scopes for f in ['Dimensions / depth','Weight','Material / finish','Fixing','Individual price','Availability']}|{k for k in a if k[2]=='Fixing'};checks['exact323_specification_rows_from54_fields_plus278_fixing_choices']=set(diff)==expected and len(diff)==323
  checks['all_other_old_fixing_changes_only_choice_display_state_basis']=all(v==[4,5,6] for k,v in diff.items() if k[2]=='Fixing' and k[:2] not in scopes)
  overlays={tuple(x['key']):x for x in new['fixing_choice_overlays']};checks['every_older_installed_fixing_detail_preserved_before_choice_overlay']=len(overlays)==278 and all(all(a[(*k,'Fixing')][i]==overlays[k][field] for i,field in [(4,'before_detail'),(5,'before_state'),(6,'before_basis')]) for k in overlays if k not in scopes)
  checks['root_MCP4_first_three_owner_fact_fields_unchanged']=all(('BC-MCP-4','MCP4-VERDIGRIS-RUST',f) not in diff for f in ['Dimensions / depth','Weight','Material / finish'])
  checks['root_MCP4_price_stock_and_one_week_unchanged']=all(('BC-MCP-4','MCP4-VERDIGRIS-RUST',f) not in diff for f in ['Individual price','Availability'])
for key in ['name_updates','groups','group_updates','catalogue_alias_rows','platform_source_counts','identity_confirmation_counts','dimension_confirmation_counts']:
 checks[key+'_unchanged']=old[key]==new[key]
a={x['values'][0]:x for x in old['additional_photograph_gaps']};b={x['values'][0]:x for x in new['additional_photograph_gaps']};checks['all_prior_gap_rows_unchanged']=all(a[k]==b[k] for k in a);checks['nine_new_exact_scope_gaps']=set(b)-set(a)=={vid for cid,vid in scopes}
heads={}
for batch in [84,85]:
 for item in read(ROOT/f'components/reviews/parallel-import-2026-10-19-batch{batch}/current-reference-check.json')['metadata']:
  h=item[item['metadata_type']];heads[h['id']]=h
primary={row[9] for row in new['reviews'] if tuple(row[:2]) in scopes};base_assets={x['id']:x for x in model['assets']};oa=base_assets|{x['id']:x for x in old['asset_updates']};na=base_assets|{x['id']:x for x in new['asset_updates']};asset_diff={k:[f for f in oa[k] if oa[k][f]!=na[k][f]] for k in oa if oa[k]!=na[k]};checks['only_verified_nine_primary_paths_updated']=set(asset_diff)==primary and all(set(fields)<={'path','name'} for fields in asset_diff.values()) and all(na[k]['path']==heads[k]['path_display'] and na[k]['name']==heads[k]['name'] for k in asset_diff)
base_offers={x['offer_ref']:x for x in model['platform_records']};op=base_offers|{x['offer_ref']:x for x in old['platform_updates']};np=base_offers|{x['offer_ref']:x for x in new['platform_updates']};platform_diff={k:[f for f in op[k] if op[k][f]!=np[k][f]] for k in op if op[k]!=np[k]};checks['no_platform_record_or_photo_match_promotion_only_verified_paths']=all(fields==['image_path'] and np[k]['image_file_id'] in primary and np[k]['image_path']==heads[np[k]['image_file_id']]['path_display'] for k,fields in platform_diff.items())
checks['working_groups186_to240_only']=old['specification_approval_counts']['proposal_groups']==186 and new['specification_approval_counts']['proposal_groups']==240
checks['photo_gap130_to139_only']=old['baseline_photo_gaps']+len(a)==130 and new['baseline_photo_gaps']+len(b)==139
checks['single_global_offered_choice_not_hardware_certification']=not old.get('global_fixing_choice_policy') and new['global_fixing_choice_policy']['policy_id'].endswith('LINE29769') and new['global_fixing_choice_policy']['choice_mode']=='CHOOSE_ONE_FOR_THE_SCULPTURE' and not new['global_fixing_choice_policy']['actual_installed_options_on_every_existing_cast_confirmed']
checks['standing_working_policy_not_replayed']=old['working_specification_acceptance_policy']==new['working_specification_acceptance_policy']
checks['seven_captured_sources_still_current']=all(hashlib.sha256(Path(x['source']).read_bytes()).hexdigest()==x['sha256'] for x in new['source_files'] if x.get('snapshot'))
assert all(checks.values()),[k for k,v in checks.items() if not v]
out={'status':'PASS','checked_utc':datetime.now(timezone.utc).isoformat(),'baseline_workbook_sha256':baseline,'included_import_batch':87,'check_count':len(checks),'checks':{k:'PASS' for k in checks},'bounded_row_deltas':deltas,'verified_asset_path_changes':asset_diff,'platform_path_changes':platform_diff,'no_new_physical_or_individual_listing_count':True,'remote_mutations':0};(HERE/'view-scope-readback-batch87.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'status':'PASS','checks':len(checks),'review_scopes_changed':len(deltas['reviews']),'specification_rows_changed':len(deltas['specifications']),'new_gap_rows':9}))
