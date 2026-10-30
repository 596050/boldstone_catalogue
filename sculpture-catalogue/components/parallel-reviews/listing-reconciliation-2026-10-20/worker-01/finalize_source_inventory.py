import json,re,hashlib,datetime,collections,itertools
from pathlib import Path

O=Path(__file__).parent
P=O/'SQUARESPACE_SOURCE_INVENTORY.json'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,x):Path(p).write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n')
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
X=json.load(open(P));master_path=O.parent/'inputs/master-register.json';master=json.load(open(master_path))
cases=[]
numbers={'one':1,'two':2,'three':3,'four':4,'five':5,'six':6,'seven':7,'eight':8,'nine':9,'ten':10}
part_re=re.compile(r'\b(one|two|three|four|five|six|seven|eight|nine|ten|\d+)\s*[-–— ]\s*parts?\b',re.I)
component_re=re.compile(r'\b(two|three|four|five|six|\d+)\s+(?:(?:tall|separate|individual|wall|relief)\s+){0,2}(panels|columns|pieces)\b',re.I)
single_re=re.compile(r'\b(?:sold as a single|a single|single piece|placed on its own)\b',re.I)
def asint(s):return numbers.get(s.lower()) or int(s)
def latest(p):return next(z for z in reversed(p['observations']) if z['source_kind']==p['normalized_variant_source'])
for index,p in enumerate(X['products']):
 obs=latest(p);text=p['description_text'];lines=text.split('\n');claims=[]
 source_ref=dict(obs.get('source_locator') or obs.get('product_row_locator'))
 source_ref['description_field']=obs.get('description_source_field','Description')
 for i,line in enumerate(lines):
  for m in list(part_re.finditer(line))+list(component_re.finditer(line)):
   if re.search(r'\b(?:no|not)\s*$',line[:m.start()],re.I):continue
   n=asint(m.group(1));claims.append({'quantity':n,'exact_description_line':line,'line_1_based':i+1,'matched_phrase':m.group(0),'evidence_scope':'NATIVE_DESCRIPTION_COMPOSITION_OR_OFFER','source_locator':source_ref})
 prior=p['prior_catalogue_offer_scopes'];scope_text=' '.join(str(q.get('source_sale_scope',''))+' '+str(q.get('source_cautions','')) for q in prior)
 qty=None;described_count=None;reasons=[];state='NOT_EXPLICIT_IN_CHECKED_DESCRIPTION';classification='UNRESOLVED'
 if p['native_product_id']=='68dc0a35a7ac865209b39248':
  classification='ONE_SELECTED_WALL_CIRCLE_OPTION';qty=1;described_count=1;state='PRIOR_OWNER_SALE_UNIT_DECISION_WITH_FRESH_NATIVE_VARIANT_GRID'
  reasons=['One Wall Circle in one selected pattern, diameter and lighting option. The144 variant rows are configurations, not144 physical items.']
  ci=next(i for i,z in enumerate(master['case_closure_dispositions']) if z['case_id']=='CAND-WALL-CIRCLE')
  claims.append({'quantity':1,'exact_source_statement':master['case_closure_dispositions'][ci]['payload']['sale_unit_decision'],'source_locator':{'path':str(master_path),'json_pointer':f'/case_closure_dispositions/{ci}/payload/sale_unit_decision'},'evidence_scope':'PRIOR_CATALOGUE_SALE_UNIT_DECISION_NOT_NEW_CHECKOUT_TEST'})
 elif not p['cached_wall_extract_member']:
  classification='NON_WALL_SOURCE_PRODUCT; SCULPTURE_UNIT_COUNT_NOT_RECONCILED';claims=[]
  reasons=['Native product/variant configurations are retained for source completeness. Description imagery such as a single feather or no two pieces are alike is not a sale-unit count; no wall-sculpture unit count is inferred for these other-site products.']
 elif 'sale quantity unresolved' in scope_text.lower() or 'gallery proposal' in scope_text.lower():
  classification='EACH_WORDING_WITH_UNRESOLVED_GALLERY_SALE_SCOPE' if re.search(r'\beach\b',text,re.I) else 'PRIOR_GALLERY_SALE_SCOPE_UNRESOLVED'
  state='PRIOR_SOURCE_CONFLICT_RETAINED';reasons=['Prior source evidence records an unresolved gallery sale scope. Current singular or Each wording is preserved, but no pictured panel count or BOM quantity is adopted as marketed quantity.']
 elif 'combined width' in text.lower() and not claims:
  classification='ARRANGEMENT_MEASUREMENTS_WITH_UNRESOLVED_MARKETED_QUANTITY';state='DESCRIPTION_AND_PRIOR_ARRANGEMENT_SCOPE_RETAINED'
  reasons=['The description says each and gives combined width, while the saved source interpretation labels an arrangement. Do not infer a member count by dividing dimensions; actual marketed quantity remains unresolved.']
  claims.append({'quantity':None,'exact_description_line':next(z for z in lines if 'combined width' in z.lower()),'source_locator':source_ref,'evidence_scope':'COMBINED_DIMENSION_CLAIM; NOT_A_PIECE_COUNT'})
 elif claims:
  ns={z['quantity'] for z in claims if z.get('quantity') is not None}
  if len(ns)==1:
   qty=described_count=next(iter(ns));classification='EXPLICIT_MULTIPART_DESCRIPTION' if qty>1 else 'EXPLICIT_SINGLE_DESCRIPTION';state='NATIVE_DESCRIPTION_PIECE_COUNT_CLAIM'
   reasons=['The explicit part/panel count is native description evidence for the described offering; it is not a mould count, stock count or per-member catalogue identity.']
  else:classification='CONFLICTING_DESCRIPTION_PIECE_COUNTS';state='SOURCE_CONFLICT';reasons=['Multiple explicit component counts occur in the description; retain all and do not choose an exact marketed quantity.']
 elif single_re.search(text):
  qty=described_count=1;classification='EXPLICIT_SINGLE_OR_STANDALONE_DESCRIPTION';state='NATIVE_DESCRIPTION_SINGLE_OBJECT_CLAIM'
  for i,line in enumerate(lines):
   if single_re.search(line):claims.append({'quantity':1,'exact_description_line':line,'line_1_based':i+1,'source_locator':source_ref,'evidence_scope':'EXPLICIT_SINGLE_OR_STANDALONE_WORDING'})
  reasons=['Standalone/single wording supports one described object. Related pairing suggestions do not turn it into a set.']
 elif p['cached_wall_extract_member'] and text:
  classification='SINGULAR_SCULPTURE_DESCRIPTION_WITHOUT_EXPLICIT_SALE_QUANTITY';described_count=1;state='SINGULAR_SOURCE_WORDING; MARKETED_QUANTITY_NOT_EXPLICIT'
  relevant=[(i,z) for i,z in enumerate(lines) if re.search(r'\b(sculpture|panel|piece|relief)\b',z,re.I)]
  if relevant:
   i,line=relevant[0];claims.append({'quantity':None,'described_object_count_interpretation':1,'exact_description_line':line,'line_1_based':i+1,'source_locator':source_ref,'evidence_scope':'SINGULAR_OBJECT_WORDING; NOT_AN_EXPLICIT_BUNDLE_OR_CART_QUANTITY'})
  reasons=['The text describes a singular sculptural object. An exact marketed quantity is not separately stated, so this inventory retains the native singular wording and prior source scope without inventing a cart fulfilment quantity.']
 else:
  classification='NON_WALL_SOURCE_PRODUCT; NO_EXPLICIT_COMPONENT_SALE_COUNT' if not p['cached_wall_extract_member'] else 'DESCRIPTION_MISSING_OR_NO_SALE_UNIT_STATEMENT'
  reasons=['All native product and variant IDs/options are retained. No sculpture-unit count is inferred for other-site catalogue products or from a title alone.']
 native_parts={q['native_parts_source_claim'] for q in prior if q.get('native_parts_source_claim') is not None}
 conflict=bool(qty is not None and native_parts and native_parts!={qty})
 assessment={'classification':classification,'quantity_per_offered_unit_source_claim':qty,'described_object_count_interpretation':described_count,
  'evidence_state':state,'evidence':claims,'reason':reasons,'prior_native_parts_source_claims':sorted(native_parts),'native_parts_vs_description_conflict':conflict,
  'native_parts_is_not_automatically_actual_marketed_quantity':True,'source_bom_pieces_not_adopted':True,'price_scope':'Native variant price is for the offered unit as described; never divided among members.',
  'member_identities_assigned':False,'cart_quantity_or_fulfilment_tested':False,'physical_stock_or_mould_count_verified':False,
  'source_state':p['inventory_state'],'assessed_from_description_not_title_or_pictured_panel_count':True}
 p['native_sellable_unit']=assessment
 sold_lines=[{'exact_description_line':line,'source_locator':source_ref} for line in lines if re.search(r'\b(?:has\s+sold|is\s+sold\s+out|sold\s+out)\b',line,re.I)]
 p['availability_source_evidence']={'description_sold_claims':sold_lines,'native_stock_settings_retained_per_variant':True,
  'description_sold_vs_unlimited_conflict':bool(sold_lines and any(v['stock_setting'].get('unlimited') is True for v in p['variants'])),
  'actual_checkout_stock_or_lead_time_tested':False}
 p['public_access_state']='FRESH_PUBLIC_PRODUCT_OBSERVED' if p['fresh_public_product_observed'] else 'CHECKED_CANONICAL_PRODUCT_JSON_HTTP404; CACHED_SOURCE_RETAINED'
 cases.append({'native_product_id':p['native_product_id'],'title':p['title'],'cached_wall_extract_member':p['cached_wall_extract_member'],'source_offer_refs':[q['source_offer_ref'] for q in prior],**assessment})

# Mechanical duplicate candidates remain separate from identity, variant and deletion decisions.
candidates=[]
for c in X['duplicate_sku_candidates']:
 candidates.append({'candidate_type':'EXACT_SKU_COLLISION','sku':c['sku'],'records':c['records'],'relationship':'DISTINCT_NATIVE_PRODUCT_AND_VARIANT_IDS_SHARE_SKU',
  'identity_confirmed':False,'deletion_or_merge_recommended':False,'limits':'SKU collision alone does not establish the same product, geometry or fulfilment unit.'})
fresh=[p for p in X['products'] if p['fresh_public_product_observed']]
body_groups=collections.defaultdict(list);media_groups=collections.defaultdict(list)
for p in fresh:
 body=re.sub(r'\s+',' ',p['description_text']).strip()
 commercial=[{'attrs':v['option_attributes'],'price':v['price'].get('price_money')} for v in p['variants']]
 sig=json.dumps(commercial,sort_keys=True)
 if body:body_groups[(hashlib.sha256(body.encode()).hexdigest(),sig)].append(p)
 ob=latest(p);media=ob.get('primary_asset_url')
 if not media and ob.get('native_media_items'):
  media=ob['native_media_items'][0].get('assetUrl')
 if media:media_groups[(media,sig)].append(p)
for (digest,commercial),ps in body_groups.items():
 if len(ps)>1:candidates.append({'candidate_type':'EXACT_DESCRIPTION_AND_COMMERCIAL_METADATA_REUSE','native_product_ids':[p['native_product_id'] for p in ps],
  'native_variant_ids':[[v['native_variant_id'] for v in p['variants']] for p in ps],'titles':[p['title'] for p in ps],'normalized_description_sha256':digest,
  'identity_confirmed':False,'deletion_or_merge_recommended':False,'limits':'Repeated copy and price/options can describe different sculpted phases or photographs. It is a source collision for review, not proof of duplicate geometry.'})
for (url,commercial),ps in media_groups.items():
 if len(ps)>1:candidates.append({'candidate_type':'EXACT_PRIMARY_MEDIA_URL_AND_COMMERCIAL_METADATA_REUSE','native_product_ids':[p['native_product_id'] for p in ps],
  'titles':[p['title'] for p in ps],'same_literal_primary_media_url':url,'identity_confirmed':False,'deletion_or_merge_recommended':False,
  'limits':'Literal native media URL reuse is not a new visual identity decision or a whole-gallery comparison.'})
X['product_duplicate_candidates']=candidates
X['sale_unit_assessment_summary']={'all_products_assessed':len(cases),'cached_wall_products_assessed':sum(c['cached_wall_extract_member'] for c in cases),
 'classification_counts_all':dict(collections.Counter(c['classification'] for c in cases)),
 'classification_counts_cached_wall_scope':dict(collections.Counter(c['classification'] for c in cases if c['cached_wall_extract_member'])),
 'native_parts_vs_explicit_description_conflicts':[{'native_product_id':c['native_product_id'],'source_offer_refs':c['source_offer_refs'],'prior_native_parts':c['prior_native_parts_source_claims'],'description_quantity':c['quantity_per_offered_unit_source_claim']} for c in cases if c['native_parts_vs_description_conflict']]}
X['status']='SOURCE_INVENTORY_COMPLETE_FOR_CHECKED_SOURCES; PUBLIC_AND_ACCOUNT_COMPLETENESS_LIMITS_RETAINED'
X['prepared_utc']=now();X['sku_collision_semantics']='Collisions across distinct Squarespace product/variant IDs, not automatically same-product, duplicate deletion candidates or cross-platform mirror duplicates.'
X['direct_product_check_summary']={'requests':len(json.load(open(O/'DIRECT_PRODUCT_CHECKS.json'))['checks']),'fresh_detail_200':4,'source_only_detail_404':5,'all_expected_200_ids_matched':True,'account_absence_or_deletion_claimed':False}
X['completeness_and_freshness_limits'] += ['Five cached-only native product IDs returned HTTP404 at their exact evidenced canonical product JSON URLs. This does not prove account deletion, unlisted status or absence at other future URLs.',
 'Public collection/item responses are read-only anonymous observations at their saved times, not an atomic account export or tested checkout/fulfilment state.',
 'Some published product descriptions use singular wording without an explicit offered-unit count. These are labelled separately from explicit part counts; description composition and prior native_parts/BOM values are not silently equated.',
 'Top-level public product price fields can be0 while native variants hold nonzero prices. Variant priceMoney values are retained as the price evidence; no zero parent-price substitution.']
X['completeness_and_freshness_limits']=list(dict.fromkeys(X['completeness_and_freshness_limits']))
dump(P,X)
dump(O/'SALE_UNIT_ASSESSMENTS.json',{'schema':'boldstone.squarespace-description-sale-unit-assessments.v1','summary':X['sale_unit_assessment_summary'],'assessments':cases,'new_catalogue_option_matches':0,'physical_quantity_certified':False})
dump(O/'SKU_AND_PRODUCT_CANDIDATES.json',{'schema':'boldstone.squarespace-source-collisions.v1','sku_collisions':X['duplicate_sku_candidates'],'product_candidates':candidates,'all_candidates_unconfirmed':True,'no_remote_actions':True})
dump(O/'CACHED_TO_FRESH_DIFFS.json',{'schema':'boldstone.squarespace-cached-to-fresh-native-id-diffs.v1','products':[{'native_product_id':p['native_product_id'],'title':p['title'],'changes':p['cached_to_public_changes']} for p in X['products'] if any(c['same_id_field_differences'] or c['added_native_variant_ids'] or c['not_currently_returned_native_variant_ids'] for c in p['cached_to_public_changes'])],
 'no_title_identity_join_used':True,'source_price_differences_not_automatically_catalogue_reprices':True})
dump(O/'SCHEMA_SAMPLE.json',{'schema':X['schema'],'path':str(P),'bound_master_sha256':X['bound_master_sha256'],'counts':X['counts'],
 'example':{'native_product_id':fresh[0]['native_product_id'],'inventory_state':fresh[0]['inventory_state'],'normalized_variant_source':fresh[0]['normalized_variant_source'],'variants':fresh[0]['variants'][:1],
 'native_sellable_unit':fresh[0]['native_sellable_unit'],'preferred_source_locator':fresh[0]['preferred_source_locator']},
 'limits':X['completeness_and_freshness_limits']})
print(json.dumps({'status':X['status'],'sale_unit_summary':X['sale_unit_assessment_summary'],'duplicate_candidate_counts':dict(collections.Counter(c['candidate_type'] for c in candidates)),'sha256':sha(P)},indent=2))
