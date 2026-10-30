"""Read back the exact owner-scope correction and all source/physical no-op boundaries."""
import copy,csv,hashlib,json,subprocess
from pathlib import Path
from datetime import datetime,timezone
H=Path(__file__).resolve().parent;B=H.parents[2]
read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
m=read(H/'input-manifest.json');g=read(H/'canonical-master-register.json');old=read(m['master_register']['snapshot']);a=read(H/'image-coverage-current.json');before=read(m['audit']['snapshot']);changes=read(H/'authorized-current-field-changes.json');checks={}
def resolve(root,path):
 x=root
 for k in path.strip('/').split('/'):x=x[int(k)]if isinstance(x,list)else x[k]
 return x
def rollback(root,rows):
 for item in reversed(rows):
  keys=item['path'].strip('/').split('/');x=root
  for k in keys[:-1]:x=x[int(k)]if isinstance(x,list)else x[k]
  k=int(keys[-1])if isinstance(x,list)else keys[-1]
  assert x[k]==item['current'],item['path']
  if item['existed_before']:x[k]=copy.deepcopy(item['before'])
  else:del x[k]
z=copy.deepcopy(g);rollback(z,[x for x in changes if x['group']=='register']);z.pop('latest_leaf_form_owner_depiction_import');z['latest_active_photo_source_review']=old['latest_active_photo_source_review'];z['latest_image_coverage_audit']=old['latest_image_coverage_audit'];checks['whole_register_only_scoped_changes']=z==old
z=copy.deepcopy(a);rollback(z,[x for x in changes if x['group']=='audit']);checks['whole_audit_only_scoped_changes']=z==before
checks['counts_unchanged']=g['summary']==old['summary']and len(g['active_option_ids'])==188 and len(g['options'])==189 and len(g['components'])==112 and a['counts']==before['counts']
checks['all_six_fields_unchanged']=all(o['master_fields']==b['master_fields']and o['specifications']==b['specifications']and o['selling_details']==b['selling_details']for o,b in zip(g['options'],old['options']))
for coll in ['source_sets','source_offer_edges']:
 i=10 if coll=='source_sets'else 27;checks[coll+'_raw_offer_and_bom']=g[coll][i]['source_offer']==old[coll][i]['source_offer']and g[coll][i]['members']==old[coll][i]['members']
checks['raw_source_assertions_immutable']=g['original_review_specification_assertions']==old['original_review_specification_assertions']
checks['Gold_option_and_edge_unchanged']=next(x for x in g['options']if x['product_id']=='BSI-096BA2E00517')==next(x for x in old['options']if x['product_id']=='BSI-096BA2E00517')and g['current_listing_match_evidence']['edges'][156]==old['current_listing_match_evidence']['edges'][156]and g['source_media_configuration_coverage'][111]==old['source_media_configuration_coverage'][111]
checks['O058_unchanged']=next(x for x in g['source_offer_edges']if x['offer_ref']=='O058')==next(x for x in old['source_offer_edges']if x['offer_ref']=='O058')
o=g['options'][100];record=o['current_owner_depiction_correction'];decision=record['current_interpretation'];checks['exact_owner_scope']=o['product_id']==decision['existing_individual_option_id']=='BSI-6581D83760F1'and o['canonical_component_id']==decision['existing_design_id']=='BC-LEAF-FORM'and record['image_reference']['file_id']=='id:cnqzTNngPVsAAAAAAArqDQ'and decision['unique_designs_depicted']==1 and decision['depicted_display_occurrences']==2 and decision['new_design_or_option_count_increment']==0
checks['no_quantity_or_platform_upgrade']=not record['native_offer_sale_quantity_verified']and not record['physical_cast_quantity_verified']and not record['photo_production_method_verified']and not record['new_platform_or_physical_match']
checks['incorrect_current_quantity_statement_replaced']='set quantity remains two'not in g['current_listing_match_evidence']['edges'][158]['special_join_limits'][0]and 'pack quantity is unconfirmed'in g['current_listing_match_evidence']['edges'][158]['special_join_limits'][0]
row=a['coverage'][100];prior=before['coverage'][100];checks['roles_same_exact_series_ref']=row['individual']==prior['individual']and row['in_situ']==prior['in_situ']and row['series']['status']==prior['series']['status']and row['series']['reference']==prior['series']['reference']
checks['capture_policy_mirrors']=g['current_individual_photo_capture_policy']==a['current_individual_photo_capture_policy']==old['current_individual_photo_capture_policy']
checks['review_state_and_holds_unchanged']=read(H/'guided-owner-review-state.json')==read(m['review_state']['snapshot'])and read(H/'photo-review-queue.json')==read(m['report_reviews']['snapshot'])
checks['runtime_no_photo_prompts']=not subprocess.check_output(['python3',str(H/'guided_review.py'),'--list'],text=True).strip()
checks['native_map_unchanged']=sha(H/'current-native-reference-map.json')==m['native_map']['sha256']
assets=read(H/'current-assets.json');oldassets=read(m['report_assets']['snapshot']);repairs=read(H/'auxiliary-current-asset-navigation-repairs.json');z=copy.deepcopy(assets)
for x in repairs:assert z[x['file_id']][x['field']]==x['current'];z[x['file_id']][x['field']]=x['before']
checks['only_two_leaf_auxiliary_paths']=len(repairs)==2 and {x['file_id']for x in repairs}=={'id:cnqzTNngPVsAAAAAAArqDQ'}and {x['field']for x in repairs}=={'display_path','folder_path'}and z==oldassets
checks['physical_ledger_188_752_unchanged']=sha(H/'physical-source-audit.json')==sha(Path(m['master_register']['path']).parent/'physical-source-audit.json')and len(read(H/'physical-source-audit.json')['field_rows'])==752
rep=read(H/'report-verification.json');checks['reports_bound']=rep['register_sha256']==sha(H/'canonical-master-register.json')and rep['audit_sha256']==sha(H/'image-coverage-current.json')and all(sha(x['path'])==x['sha256']for x in rep['pages']+rep['csv_files']+rep['thumbnail_files'])
checks['frozen_sources']=all(sha(x['path'])==sha(x['snapshot'])==x['sha256']for x in m.values())
checks['exact_owner_receipt']=sha(record['source_receipt'])==record['source_sha256']=='f0a76f4899318dc114c609103d82b0fc10e04722c53d96d13aa73b9e7344367d'
r={'status':'PASS'if all(checks.values())else'FAIL','recorded_utc':datetime.now(timezone.utc).isoformat(),'checks':len(checks),'check_results':checks,'issues':[k for k,v in checks.items()if not v],'workbook_sha256':sha(H/'master-workbook.pending'),'register_sha256':sha(H/'canonical-master-register.json'),'audit_sha256':sha(H/'image-coverage-current.json'),'new_design_or_option_increment':0,'new_photo_bindings':0,'new_physical_verifications':0,'native_or_platform_writes':0};(H/'native-binding-verification.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps({k:r[k]for k in ['status','checks','issues']}));raise SystemExit(bool(r['issues']))
