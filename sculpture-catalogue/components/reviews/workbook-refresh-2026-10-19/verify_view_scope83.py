"""Bound the complete export delta against the archived publication78 by stable keys."""
import hashlib,json
from datetime import datetime,timezone
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
read=lambda p:json.loads(p.read_text())
old=read(HERE/'history/1fcee854f267cec1230c2d729989a5485ebc7d6d59c0ad1ea506de8a55291d17/refresh-data.json');new=read(HERE/'refresh-data.json');model=read(ROOT/'components/evidence/component_register.json')
scopes={('BC-FOUNTAIN-EG','FOUNTAIN-EG-BRONZE-VERDIGRIS'),('BC-FOUNTAIN-MED','FOUNTAIN-MED-WHITE'),('BC-LEAF-CURVE','LEAF-CURVE-WHITE-GOLD'),('BC-LEAF-GROWTH','LEAF-GROWTH-WHITE'),('BC-LEAF-GROWTH','LEAF-GROWTH-WHITE-GOLD'),('BC-LEAF-FORM','LEAF-FORM-LF1-WHITE'),('BC-LEAF-FORM','LEAF-FORM-LF2-WHITE'),('BC-LEAF-FORM','LEAF-FORM-GOLD')};rust=('BC-MCP-4','MCP4-VERDIGRIS-RUST')
checks={};deltas={}
for key,fn in [('reviews',lambda x:tuple(x[:2])),('specifications',lambda x:(*x[:2],x[3]))]:
 a={fn(x):x for x in old[key]};b={fn(x):x for x in new[key]};checks[key+'_stable_scope_keys_preserved']=a.keys()==b.keys();diff={k:[i for i,(x,y) in enumerate(zip(a[k],b[k])) if x!=y] for k in a if a[k]!=b[k]};deltas[key]=[{'key':k,'columns':v} for k,v in diff.items()]
 if key=='reviews':checks['exact_nine_review_scopes_only']=set(diff)==scopes|{rust};checks['names_ids_platform_and_primary_ids_unchanged']=all(not(set(v)&{0,1,2,3,4,6,9,10}) for v in diff.values())
 else:
  expected={(cid,vid,field) for cid,vid in scopes for field in ['Dimensions / depth','Weight','Material / finish','Fixing','Individual price','Availability']}|{(*rust,'Individual price'),(*rust,'Availability'),('BC-AC-TWO','AC-TWO-WHITE-BLACK','Individual price')}
  checks['exact51_specification_rows_changed']=set(diff)==expected and len(diff)==51;checks['original_first_four_Rust_fields_unchanged']=all(k not in diff for k in [(*rust,f) for f in ['Dimensions / depth','Weight','Material / finish','Fixing']]);checks['WhiteBlack_price_basis_only']=diff[('BC-AC-TWO','AC-TWO-WHITE-BLACK','Individual price')]==[6]
for k in ['name_updates','groups','group_updates','catalogue_alias_rows','platform_source_counts','identity_confirmation_counts','dimension_confirmation_counts']:
 checks[k+'_unchanged']=old[k]==new[k]
a={x['values'][0]:x for x in old['additional_photograph_gaps']};b={x['values'][0]:x for x in new['additional_photograph_gaps']};checks['all_prior_gap_records_preserved']=all(a[k]==b[k] for k in a);checks['exact_eight_new_scoped_gap_rows']=set(b)-set(a)=={vid for cid,vid in scopes}
heads={}
for batch in [80,81,82,83]:
 for item in read(ROOT/f'components/reviews/parallel-import-2026-10-19-batch{batch}/current-reference-check.json')['metadata']:
  head=item[item['metadata_type']];heads[head['id']]=head
primary={row[9] for row in new['reviews'] if tuple(row[:2]) in scopes}
base_assets={x['id']:x for x in model['assets']};oa=base_assets|{x['id']:x for x in old['asset_updates']};na=base_assets|{x['id']:x for x in new['asset_updates']};asset_delta={k:[field for field in oa[k] if oa[k][field]!=na[k][field]] for k in oa if oa[k]!=na[k]};checks['only_eight_verified_primary_asset_paths_updated']=set(asset_delta)==primary and all(set(fields)<={'path','name'} for fields in asset_delta.values()) and all(na[k]['path']==heads[k]['path_display'] and na[k]['name']==heads[k]['name'] for k in asset_delta)
base_offers={x['offer_ref']:x for x in model['platform_records']};op=base_offers|{x['offer_ref']:x for x in old['platform_updates']};np=base_offers|{x['offer_ref']:x for x in new['platform_updates']};platform_delta={k:[field for field in op[k] if op[k][field]!=np[k][field]] for k in op if op[k]!=np[k]};checks['one_offer_path_current_normalisation_no_platform_match_promotion']=platform_delta=={'O058':['image_path']} and np['O058']['image_path']==heads['id:cnqzTNngPVsAAAAAAAs6hg']['path_display']
checks['working_count136_to186_only']=old['specification_approval_counts']['proposal_groups']==136 and new['specification_approval_counts']['proposal_groups']==186
checks['photo_gap122_to130_only']=old['baseline_photo_gaps']+len(a)==122 and new['baseline_photo_gaps']+len(b)==130
checks['single_policy_with_unknowns_unfilled']=new['working_specification_acceptance_policy']['policy_id'].endswith('LINE18928') and not new['working_specification_acceptance_policy']['unknown_values_filled']
checks['captured_seven_shared_sources_still_current']=all(hashlib.sha256(Path(x['source']).read_bytes()).hexdigest()==x['sha256'] for x in new['source_files'] if x.get('snapshot'))
assert all(checks.values()),[k for k,v in checks.items() if not v]
out={'status':'PASS','checked_utc':datetime.now(timezone.utc).isoformat(),'baseline_workbook_sha256':'1fcee854f267cec1230c2d729989a5485ebc7d6d59c0ad1ea506de8a55291d17','included_import_batch':83,'check_count':len(checks),'checks':{k:'PASS' for k in checks},'bounded_row_deltas':deltas,'asset_path_deltas':asset_delta,'platform_path_delta':platform_delta,'no_new_actual_physical_or_listing_count':True,'new_remote_writes':0}
(HERE/'view-scope-readback-batch83.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'status':'PASS','checks':len(checks),'changed_review_scopes':len(deltas['reviews']),'changed_specification_rows':len(deltas['specifications']),'verified_asset_paths':len(asset_delta)}))
