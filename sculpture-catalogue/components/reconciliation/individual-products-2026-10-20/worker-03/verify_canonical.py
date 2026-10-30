"""Independent canonical readback using source row bytes and owner-scoped audit sets."""
import json
import hashlib
from pathlib import Path
from collections import Counter,defaultdict
from datetime import datetime,timezone

W=Path(__file__).resolve().parent
R=W.parent
ROOT=Path('/Users/tprice/Documents/boldstone/sculpture-catalogue')
cp=R/'canonical-products.json';canonical_bytes=cp.read_bytes();c=json.loads(canonical_bytes)
x=json.loads((R/'inputs/refresh-data.json').read_text())
p=json.loads((R/'inputs/specification_review_progress.json').read_text())
u=json.loads((R/'inputs/user_classifications.json').read_text())
manifest=json.loads((R/'input-manifest.json').read_text())
audited=json.loads((W/'scope-coverage.json').read_text())
kept={'|'.join([s['component_id'],s['scope']]) for s in audited if s['kept_name_or_catalogue_alias']}
fields={'Dimensions / depth','Weight','Material / finish','Fixing','Individual price','Availability'}
checks={};errors=[];warnings=[]
def check(name,value,detail=None):
 checks[name]=bool(value)
 if not value:errors.append({'check':name,'detail':detail})
products=c['products'];prods={z['product_id']:z for z in products};scope_to_product=defaultdict(list)
for z in products:
 for scope in z['source_scopes']:scope_to_product[scope].append(z['product_id'])
check('unique_product_ids',len(prods)==len(products))
check('product_source_scopes_equal_independent_kept_name_alias_set',set(scope_to_product)==kept,{'missing':sorted(kept-set(scope_to_product)),'extra':sorted(set(scope_to_product)-kept)})
check('every_kept_scope_has_exactly_one_product',all(len(v)==1 for v in scope_to_product.values()))
merged=[z for z in products if len(z['source_scopes'])>1]
leaf_scopes={'BC-LEAF-FORM|LEAF-FORM-LF1-WHITE','BC-LEAF-FORM|LEAF-FORM-LF2-WHITE'}
check('only_leaf_form_white_orientation_merge',len(merged)==1 and set(merged[0]['source_scopes'])==leaf_scopes)
check('leaf_orientation_options_preserved',len(merged)==1 and set(merged[0]['orientation_options'])=={'LF1','LF2'})
check('product_count_follows_unique_independent_kept_scopes_minus_one_orientation',len(products)==len(kept)-1)
check('all_products_have_exactly_six_named_fields',all(set(z['specifications'])==fields for z in products))
check('all_product_fields_have_display_and_source_assertion',all(v.get('display') and v.get('assertions') for z in products for v in z['specifications'].values()))
check('working_field_count',sum(len(z['specifications']) for z in products)==6*(len(kept)-1))

expected={i:r for i,r in enumerate(x['specifications']) if '|'.join(r[:2]) in kept}
actual=defaultdict(list);field_by_index={}
for z in products:
 for field,v in z['specifications'].items():
  for a in v['assertions']:
   actual[a['source_row_index']].append((z['product_id'],field,a));field_by_index[a['source_row_index']]=field
check('accepted_scope_source_assertion_index_set_preserved_exactly',set(expected)==set(actual),{'missing':sorted(set(expected)-set(actual)),'extra':sorted(set(actual)-set(expected))})
check('all_1044_expected_source_assertions_preserved_once',len(expected)==len(kept)*6 and sum(map(len,actual.values()))==len(expected) and all(len(a)==1 for a in actual.values()))
row_errors=[]
projection={'source_title':2,'display':4,'state':5,'basis':6,'image_url':7,'folder_url':8,'file_id':9,'folder_id':10,'proposal_id':11}
for i,r in expected.items():
 if len(actual.get(i,[]))!=1:continue
 pid,field,a=actual[i][0]
 if a['source_scope']!='|'.join(r[:2]) or field!=r[3]:row_errors.append({'index':i,'reason':'scope/field changed'})
 for key,col in projection.items():
  if a.get(key)!=r[col]:row_errors.append({'index':i,'field':r[3],'property':key,'source':r[col],'canonical':a.get(key)})
check('every_assertion_value_state_basis_ID_and_link_matches_source',not row_errors,row_errors[:25])

review_by_scope={'|'.join(r[:2]):r for r in x['reviews']}
mapping=c['scope_reconciliation'];map_by_scope={z['source_scope']:z for z in mapping}
check('exact_all_278_current_scope_mappings',len(mapping)==len(review_by_scope)==len(map_by_scope) and set(map_by_scope)==set(review_by_scope))
targets=set(prods)|{z['reference_id'] for z in c['references']}|{z['candidate_id'] for z in c['source_candidates']}
check('all_current_and_historical_targets_exist',all(t in targets for z in mapping+c['historical_alias_reconciliation'] for t in z['targets']))
for scope,pids in scope_to_product.items():
 check('accepted_scope_target:'+scope,map_by_scope[scope]['targets']==pids)
expected_hist={
 'BC-CONCAVE|CM-WHITE-25':'BC-MCP-4|MCP4-WHITE',
 'BC-CONCAVE|CM-SILVER-25':'BC-MCP-4|MCP4-SILVER-BRONZE-25',
 'BC-CONCAVE|CM-VERDIGRIS-25':'BC-MCP-4|MCP4-VERDIGRIS-25',
 'BC-MCP-4|MCP4-SILVER':'BC-MCP-4|MCP4-SILVER-BRONZE-25',
 'BC-MCP-4|MCP4-VERDIGRIS':'BC-MCP-4|MCP4-VERDIGRIS-25',
}
hist={z['source_scope']:z for z in c['historical_alias_reconciliation']}
hist_finishes={k:v for k,v in hist.items() if v['disposition']=='HISTORICAL_FINISH_ALIAS'}
check('five_historical_finish_aliases_exact',set(hist_finishes)==set(expected_hist))
check('historical_aliases_target_correct_current_finish_without_inheritance',all(hist[k]['targets']==scope_to_product[v] and hist[k]['specification_assertions_inherited'] is False for k,v in expected_hist.items()))
design_alias=hist.get('BC-CONCAVE|BASE')
if design_alias:
 mcp4_targets={z['product_id'] for z in products if z['canonical_design_id']=='BC-MCP-4'}
 check('additional_Concave_design_header_alias_is_not_a_sixth_finish_or_extra_product',design_alias['disposition']=='HISTORICAL_DESIGN_ALIAS' and set(design_alias['targets'])==mcp4_targets and design_alias['specification_assertions_inherited'] is False)
check('historical_aliases_have_no_unreviewed_extra_scope',set(hist)<=set(expected_hist)|{'BC-CONCAVE|BASE'})

group_rows={r[0]:r for r in x['groups']}
grouprefs=[r for r in c['references'] if r['record_type']=='ARRANGEMENT_OR_COLLECTION_REFERENCE']
group_sources=defaultdict(list)
for r in grouprefs:
 for key in r['source_reference_ids']:
  if key in group_rows:group_sources[key].append(r)
check('all_22_group_sources_mapped_once',set(group_sources)==set(group_rows) and all(len(v)==1 for v in group_sources.values()))
check('21_canonical_group_references_after_one_known_image_alias',len(grouprefs)==len(group_rows)-1)
dup_pair={'FINGERPRINT-OFFSET-SPIRAL-VERDIGRIS-G158022','FINGERPRINT-ROUGH-CONCENTRIC-VERDIGRIS-G160001'}
multi=[r for r in grouprefs if len([key for key in r['source_reference_ids'] if key in group_rows])>1]
check('only_offset_rough_group_merge',len(multi)==1 and set(multi[0]['source_reference_ids'])==dup_pair)
check('group_merge_keeps_two_source_specifications_and_images',len(multi)==1 and len(multi[0]['specifications'])==2 and len(multi[0]['images'])==2)
group_errors=[]
for key,row in group_rows.items():
 r=group_sources[key][0];ss=next((z for z in r['specifications'] if z['source']==key),None)
 if not ss or ss['display']!=row[4] or ss['state']!=row[5]:group_errors.append(key)
check('every_group_body_and_pending_state_preserved',not group_errors,group_errors)
check('no_group_reference_counted_as_individual',all(r.get('counted_as_working_product') is False for r in grouprefs))
for gid in ['FINGERPRINT-WAVY-WHITE-G156001','FINGERPRINT-SEGMENTED-WHITE-G156002']:
 d=next(z for z in u['source_design_name_decisions'] if z.get('source_design_key')==gid);r=group_sources[gid][0]
 check('existing_name_receipt_corrects_group_display:'+gid,r['name']==d['approved_name'] and r['name_status'].startswith('Owner kept source name') and 'deferred' in r['component_identification'])
arr=group_sources['MOONPHASE-WATER-FEATURE-WHITE-01'][0]
check('Moonphase_water_feature_is_reference_only',arr.get('counted_as_working_product') is False and not any('MOONPHASE-WATER-FEATURE-WHITE-01' in z['source_scopes'] for z in products))
check('Soundwave_whole_source_is_working_product',len(scope_to_product['UGR-G310|SOUNDWAVE-WHITE-G310003'])==1 and not any('SOUNDWAVE-WHITE-G310003' in z['source_reference_ids'] for z in grouprefs))

candidate_ids={z['component_id'] for z in c['source_candidates']}
check('six_expected_candidate_records',candidate_ids=={'BC-BONE-1','BC-BONE-2','BC-FFL-1','BC-CR-RING','BC-DR-WAVE3','BC-WALL-CIRCLE'})
check('candidates_not_counted_as_working_products',all(z['counted_as_working_product'] is False for z in c['source_candidates']))
check('WallCircle_remains_option_family_not_144_products',next(z for z in c['source_candidates'] if z['component_id']=='BC-WALL-CIRCLE')['record_type']=='OPTION_FAMILY_CANDIDATE' and not any(z['canonical_design_id']=='BC-WALL-CIRCLE' for z in products))
candidate_errors=[]
for z in c['source_candidates']:
 for scope,rows in z['source_specifications'].items():
  expected_rows=[r for r in x['specifications'] if '|'.join(r[:2])==scope]
  if rows!=expected_rows:candidate_errors.append(scope)
check('candidate_source_fields_unchanged',not candidate_errors,candidate_errors)

source_integrity=[]
for f in manifest['sources']:
 origin=Path(f['source']);snap=Path(f['snapshot']);oh=hashlib.sha256(origin.read_bytes()).hexdigest();sh=hashlib.sha256(snap.read_bytes()).hexdigest()
 source_integrity.append({'source':str(origin),'snapshot':str(snap),'recorded_sha256':f['sha256'],'current_source_sha256':oh,'snapshot_sha256':sh,'original_and_snapshot_match_recorded_hash':oh==sh==f['sha256']})
check('all_six_source_originals_and_snapshots_unchanged',all(z['original_and_snapshot_match_recorded_hash'] for z in source_integrity))
baseline=Path(manifest['baseline_workbook']);check('baseline_workbook_unchanged',hashlib.sha256(baseline.read_bytes()).hexdigest()==manifest['baseline_workbook_sha256'])
check('no_product_physical_or_publication_certification_added',all(z['physical_specifications_verified'] is False and z['platform_publication_performed'] is False for z in products))

# Content checks outside simple count mirroring.
chelsea=prods[scope_to_product['BC-CHELSEA|BASE'][0]]
check('Chelsea_prior_price_caveat_not_stripped','retained in history' in chelsea['specifications']['Individual price']['display'] and 'reconfirm price' in chelsea['specifications']['Individual price']['display'])
warnings.append({'code':'CHELSEA_PRICE_IS_HISTORICAL_NOT_CURRENT_WORKING_ASK','product_id':chelsea['product_id'],'scope':'BC-CHELSEA|BASE','detail':'The £1,100 proposal remains historical after the owner corrected the face to250×100cm. Canonical wording preserves that caveat, but working_accepted=true must not be presented as confirmation of an applicable current £1,100 asking price.'})
quote_only=[z['product_id'] for z in products if not any(ch.isdigit() for ch in z['specifications']['Individual price']['display'])]
warnings.append({'code':'QUOTE_ONLY_IS_POLICY_NOT_NUMERICAL_PRICE','count':len(quote_only),'product_ids':quote_only,'detail':'Kept working records intentionally retain quote/enquiry-only price policies. They have field bodies but no numerical asking price.'})

# Inspect the questioned BSM2 BASE mapping against original evidence, not only names.
model=json.loads((ROOT/'components/evidence/component_register.json').read_text())
shell=next(z for z in model['components'] if z['component_id']=='BC-SHELL-B2')
gmap={z['group_ref']:z for z in model['groups']}
check('ShellB2_original_evidence_only_water_feature_group',shell['group_refs']==['G306'] and 'Water Feature' in gmap['G306']['name'])
check('ShellB2_BASE_targets_same_kept_water_build_without_new_standard_product',map_by_scope['BC-SHELL-B2|BASE']['targets']==scope_to_product['BC-SHELL-B2|SHELL-B2-WATER-WHITE'] and map_by_scope['BC-SHELL-B2|BASE']['specification_assertions_inherited'] is False)
check('BSM1_keeps_distinct_standard_and_water_build_records',scope_to_product['BC-SHELL-B1|BASE']!=scope_to_product['BC-SHELL-B1|BSM1-WATER-WHITE'])
check('Islington_keeps_distinct_standard_and_water_build_records',scope_to_product['BC-SHELL-I|ISM1-STANDARD-WHITE']!=scope_to_product['BC-SHELL-I|ISM1-WATER-WHITE'])

if not c.get('source_offer_coverage') or not c.get('source_configuration_coverage'):
 warnings.append({'code':'SOURCE_CONFIGURATION_AND_OFFER_COVERAGE_PENDING','detail':'This preliminary canonical JSON has empty source_offer_coverage and source_configuration_coverage arrays. Do not infer full baseline offer/finish coverage from the278review-scope reconciliation alone. Agent02 is auditing the complete source universe.'})
check('canonical_not_changed_during_readback',hashlib.sha256(cp.read_bytes()).hexdigest()==hashlib.sha256(canonical_bytes).hexdigest())

result={'schema':'boldstone.independent-canonical-readback.v1','worker_number':3,'audited_utc':datetime.now(timezone.utc).isoformat(),'canonical_path':str(cp),'canonical_sha256':hashlib.sha256(canonical_bytes).hexdigest(),'canonical_bytes':len(canonical_bytes),'status':'PASS_COUNTS_ASSERTION_RETENTION_AND_REFERENCES_WITH_CONTENT_CAVEATS' if not errors else 'FAIL','counts':{'independently_kept_source_scopes':len(kept),'working_products':len(products),'field_groups':sum(len(z['specifications']) for z in products),'exact_source_assertions':sum(map(len,actual.values())),'current_scope_mappings':len(mapping),'historical_finish_alias_mappings':len(hist_finishes),'historical_design_header_aliases':len(hist)-len(hist_finishes),'source_group_rows':len(group_rows),'canonical_group_references':len(grouprefs),'additional_source_position_collection_references':len(c['references'])-len(grouprefs),'candidates':len(c['source_candidates']),'quote_only_products':len(quote_only)},'checks':checks,'errors':errors,'content_caveats':warnings,'source_integrity':source_integrity,'scope_definition_limits':'Product counts are working design/finish/size/build catalogue records. They are not physical cast, mould or stock counts. An accepted source assertion may intentionally retain unknowns or an enquiry policy.','no_central_edits':True,'remote_reads':0,'remote_mutations':0}
(W/'canonical-readback.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'status':result['status'],'counts':result['counts'],'errors':errors,'caveats':[z['code'] for z in warnings],'sha256':result['canonical_sha256']},ensure_ascii=False,indent=2))
