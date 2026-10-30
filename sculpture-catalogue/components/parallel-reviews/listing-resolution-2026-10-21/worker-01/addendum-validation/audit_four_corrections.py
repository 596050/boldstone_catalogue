import datetime, hashlib, json, re
from pathlib import Path

OUT=Path(__file__).resolve().parent
WORKER=OUT.parent
BASE=WORKER.parent

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def read(path):
    return json.loads(Path(path).read_bytes())

def canon(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()

def ptr(value,pointer):
    for token in pointer.split('/')[1:]:
        token=token.replace('~1','/').replace('~0','~')
        value=value[int(token)] if isinstance(value,list) else value[token]
    return value

checks=[]
def check(name,condition,details=None):
    checks.append({'name':name,'status':'PASS' if condition else 'FAIL','details':details})

correction_path=OUT/'FOUR_LISTING_CORRECTIONS.reviewed.json'
corrections=read(correction_path)
inventory=read(WORKER/'FRESH_PUBLIC_INVENTORY.json')
master_path=BASE/'inputs/master-register.json'
master=read(master_path)
rebase_path=BASE/'inputs/rebase-step07/master-register.json'
rebased=read(rebase_path)
options={o['product_id']:(i,o) for i,o in enumerate(master['options'])}
new_options={o['product_id']:(i,o) for i,o in enumerate(rebased['options'])}
native_by={p['native_product_id']:(i,p) for i,p in enumerate(inventory['products'])}
official=read(OUT/'OFFICIAL_API_EVIDENCE.json')

expected={
 'BSI-1E0C826D896E':{'offer':'O079','native':'6aa67715c20cf7004257259d','variant':'b532bf3e-8a34-4310-b3ba-b1934b212521','sku':'BWS-1-55.55','size':{'width_cm':80,'height_cm':60,'projection_cm_range':[5,8],'projection_scope':'Historical maker estimate; unmeasured'},'price':'1100.00','weight_markers':['15','20'],'size_markers':['80','60','5–8']},
 'BSI-DB7FBD3E1323':{'offer':'O046','native':'6a555aba1b9743318cc70c44','variant':'7cca80be-1c9c-42dd-8e37-8e0e8d592ce7','sku':'GS-1-30.30','size':{'recorded_dimension_order_cm':[45,40,5],'new_height_width_assignment':False},'price':'250.00','weight_markers':['10','8–12'],'size_markers':['45','40','5']},
 'BSI-6581D83760F1':{'offer':'O058','native':'6a610229b545114fe3886be2','variant':'ce22aac4-578d-4586-9ec8-4937dcddaaf7','sku':'LF-1-40.20','size':{'nominal_face_cm':[35,35],'nominal_depth_cm':6,'historical_side_depth_cm_range':[5,7],'measured':False},'price':'350.00','weight_markers':['6–8'],'size_markers':['35','35','6']},
 'BSI-70C7029C1DB1':{'offer':'O059','native':'6a6102307b54f252fe00210b','variant':'9d8c0d63-87c6-400e-8a85-51e4208271b3','sku':'MWTR-1-50','size':{'height_cm_approx':51,'width_cm_approx':48,'side_depth_cm_range':[5,7],'scope':'Historical maker-stated working version; panel unmeasured'},'price':None,'weight_markers':['10–12'],'size_markers':['51','48','5–7']}}

check('Audited parent snapshot exact bytes remain current',sha(correction_path)==sha(BASE/'FOUR_LISTING_CORRECTIONS.json'),{'audited_sha256':sha(correction_path),'parent_current_sha256':sha(BASE/'FOUR_LISTING_CORRECTIONS.json')})
check('Frozen master and rebased master exact expected identities',sha(master_path)=='7760b44a4d52ff3b78c893d5b86ef174814b48c29f7e41814c8a01a42af5326d' and sha(rebase_path)=='f19ed82f8c382cb944bc9f8e5669eb797e6ccf23c995a702268a734fe0410878')
changed_fields=[pid for pid,(_,o) in options.items() if pid not in new_options or o.get('master_fields')!=new_options[pid][1].get('master_fields')]
check('All184 master_fields dictionaries and1104 accepted fields unchanged across step07 rebase',len(options)==len(new_options)==184 and set(options)==set(new_options) and not changed_fields and sum(len(o['master_fields']) for _,o in options.values())==1104,{'changed_product_ids':changed_fields,'original_master_fields_sha256':canon({k:v[1]['master_fields'] for k,v in options.items()}),'rebased_master_fields_sha256':canon({k:v[1]['master_fields'] for k,v in new_options.items()})})
check('Exactly four requested catalogue IDs and offers once',len(corrections['records'])==4 and {r['product_id'] for r in corrections['records']}==set(expected))
check('Official saved product-update example supports exact method/path and wrappers',official['method']=='POST' and official['path_template']=='/v2/commerce/products/{productId}' and official['selected_example_body_fields']=={'name':{'present':True,'value':'value'},'description':{'present':True,'value':'value'}} and bool(official['partial_update_evidence_locators']),{'source':str(OUT/'OFFICIAL_API_EVIDENCE.json'),'source_sha256':sha(OUT/'OFFICIAL_API_EVIDENCE.json'),'official_url':official['url'],'live_reads_by_this_addendum':0})

record_results=[]
for index,record in enumerate(corrections['records']):
    pid=record['product_id'];rule=expected[pid];oi,option=options[pid];ni,native=native_by[rule['native']]
    variant=next(v for v in native['variants'] if v['native_variant_id']==rule['variant'])
    identity=record['native_record_identity'];body_draft=record['native_product_partial_update_draft'];body=body_draft['body'];fields=record['proposed_public_specification_fields']
    edge=next(e for e in master['source_offer_edges'] if e['offer_ref']==rule['offer'])
    native_source=ptr(read(native['source_locator']['path']),native['source_locator']['json_pointer'])
    raw_variant=ptr(read(variant['source_locator']['path']),variant['source_locator']['json_pointer'])
    spec_master={k:v['display'] for k,v in option['master_fields'].items()}
    actual_display={k:v['display'] for k,v in option['specifications'].items()}
    before=record['native_before'];selected_before=before['variant']
    before_matches=all(selected_before[k]==variant[k] for k in selected_before) and before['title']==native['title'] and before['description_html']==native['description_html'] and before['description_text']==native['description_text'] and before['timestamps']==native['timestamps']
    product_tuple=(identity['product_id'],identity['variant_id'],identity['sku'],identity['url'])
    source_tuple=(native['native_product_id'],variant['native_variant_id'],variant['sku'],native['url'])
    tuple_ok=product_tuple==source_tuple and identity['product_id']==edge['source_offer']['sq_id'] and variant['sku']==rule['sku'] and native_source['id']==rule['native'] and raw_variant['id']==rule['variant'] and raw_variant['sku']==rule['sku']
    check(record['name']+': exact product/variant/SKU/URL tuple and offer binding',tuple_ok,{'offer':rule['offer'],'tuple':product_tuple,'raw_product_pointer':native['source_locator'],'raw_variant_pointer':variant['source_locator']})
    check(record['name']+': complete native before snapshot matches frozen inventory',before_matches)
    check(record['name']+': six accepted working values exactly retained',record['accepted_working_specifications']==spec_master==actual_display and record['accepted_specifications_changed'] is False and record['canonical_key']==option['canonical_key'],{'master_option_pointer':'/options/'+str(oi),'master_fields_sha256':canon(option['master_fields'])})
    check(record['name']+': correction targets accepted size/weight/finish scope',record['proposed_standard_size']==rule['size'] and all(s in fields['Dimensions'] for s in rule['size_markers']) and all(s in fields['Approximate weight'] for s in rule['weight_markers']) and bool(fields['Finish']) and record['canonical_offer_proposal']==rule['offer'],{'proposed_standard_size':record['proposed_standard_size'],'weight_copy':fields['Approximate weight'],'finish_copy':fields['Finish']})
    check(record['name']+': retain native SKU verbatim as legacy identifier',record['native_sku_policy']['value']==rule['sku'] and record['native_sku_policy']['prior_sku_aliases_retained'] is True and record['native_sku_policy']['sku_digits_are_not_dimensions'] is True and record['native_sku_policy']['canonical_working_option_id']==pid)
    check(record['name']+': partial-update body uses only supported name/description wrappers',body_draft['method']=='POST' and body_draft['path']=='/v2/commerce/products/'+rule['native'] and set(body)=={'name','description'} and body['name']=={'present':True,'value':record['proposed_listing_title']} and body['description']=={'present':True,'value':record['proposed_review_description_html']} and body_draft['executable_now'] is False)
    encoded=json.dumps(body,ensure_ascii=False)
    forbidden=['shippingMeasurements','qtyInStock','unlimited','stock','pricing','basePrice','salePrice','imageIds','images','variants','sku']
    check(record['name']+': no shipping/stock/price/ID/image/variant payload overwrite',record['shipping_measurements_policy']['action']=='NO_CHANGE' and not any('"'+key+'"' in encoded for key in forbidden),{'body_keys':list(body),'shipping_policy':record['shipping_measurements_policy']})
    public=body['description']['value']
    no_binder=not any(word in public.casefold() for word in ['jesmonite','ac730','gypsum','plaster','100%','pure gold','solid gold'])
    no_stock=not any(word in public.casefold() for word in ['in stock','stock available','ready to ship','unlimited stock','measured','certified','load rating'])
    check(record['name']+': public draft avoids unsupported binder/stock/hardware certification',no_binder and no_stock and 'Keyhole fixing or French cleat' in fields['Fixing options'] and record['physical_specifications_certified'] is False and record['exact_current_native_configuration_verified'] is False)
    policy=record['commercial_policy_proposal']
    if rule['price'] is not None:
        price_ok=policy['mode']=='ACCEPTED_WORKING_ASK' and policy['currency']=='GBP' and policy['value']==rule['price'] and float(policy['value'])>0 and policy['value']==variant['price']['priceMoney']['value']
    else:
        price_ok=policy['mode']=='PROPOSE_PRICE_ON_ENQUIRY' and policy['value'] is None and policy['zero_price_proposed'] is False and policy['retained_native_ask']=='800.00' and policy['retained_local_draft']=='599.69' and fields['Price']=='Price on enquiry.' and any('matching purchase/enquiry flow' in text for text in record['specific_limits'])
    check(record['name']+': working commercial policy does not create zero price or silently replace sources',price_ok,policy)
    record_results.append({'case_id':record['case_id'],'product_id':pid,'offer_ref':rule['offer'],'native_tuple':{'product_id':identity['product_id'],'variant_id':identity['variant_id'],'sku':identity['sku'],'url':identity['url']},'master_fields_preserved':record['accepted_working_specifications']==spec_master,'native_before_exact':before_matches,'partial_body_schema_supported':True,'shipping_stock_pricing_fields_in_body':False,'execution_readiness':'NOT_EXECUTABLE_AUTHENTICATED_BEFORE_STATE_AND_GROUPED_COMMERCIAL_FLOW_PRECONDITIONS_PENDING','correction_source_pointer':'/records/'+str(index),'master_option_pointer':'/options/'+str(oi),'native_inventory_pointer':'/products/'+str(ni)})

overlap=read(WORKER/'OVERLAP_PROPOSALS.json')
rust=next(p for p in overlap['proposals'] if p['case_id']=='RUST-SKU-COLLISION')
moon=next(p for p in overlap['proposals'] if p['case_id']=='MOON-WATER-OVERLAP')
rust_policy=rust['canonical_alias_proposal'];moon_policy=moon['canonical_alias_proposal']
check('Sealed overlap retains O067 canonical/O051 reversible legacy draft',rust_policy['preferred_source_offer_ref']=='O067' and rust_policy['preferred_native_product_id']=='6aa01aad7f3077314dd71e8c' and rust_policy['preferred_native_variant_id']=='ca0fa776-e58d-41a3-b11b-ce9a64f458e4' and rust_policy['preferred_sku_retained']=='EBAY-188654649217' and rust_policy['alias_source_offer_ref']=='O051' and rust_policy['reversible_draft_only']['proposed_unique_legacy_sku']=='LEGACY-6a5a621422d8fb7a65ba5a77' and rust_policy['reversible_draft_only']['original_sku_alias_retained']=='EBAY-188654649217' and rust_policy['reversible_draft_only']['execution_status']=='NOT_EXECUTED' and rust_policy['reversible_draft_only']['url_access_or_checkout_disabled_claimed'] is False)
check('Sealed overlap retains O059 primary/O015 unresolved identity-conflict quarantine',moon_policy['preferred_source_offer_ref']=='O059' and moon_policy['related_conflicting_source_offer_ref']=='O015' and 'identity-conflict quarantine' in moon_policy['recommended_mapping_correction'] and 'without guessing' in moon_policy['recommended_mapping_correction'] and 'Do not collapse' in moon_policy['recommended_mapping_correction'])
seal=read(WORKER/'SEAL.json');changed=[]
for artifact in seal['artifacts']:
    path=WORKER/artifact['relative_path']
    if not path.is_file() or sha(path)!=artifact['sha256'] or path.stat().st_size!=artifact['bytes']:
        changed.append(artifact['relative_path'])
check('All135 prior sealed artifacts unchanged; addendum is separate',len(seal['artifacts'])==135 and not changed and sha(WORKER/'SEAL.json')=='2857ab78390ab280ee520cd3f6a3196fa6d7794be70915248056804cfdce3b81',{'changed_artifacts':changed,'sealed_artifact_count':len(seal['artifacts'])})
check('Correction proposals are explicitly not platform/shared writes',corrections['platform_writes']==0 and corrections['shared_master_writes']==0 and all(r['native_product_partial_update_draft']['executable_now'] is False for r in corrections['records']))
check('Parent correction bytes stayed unchanged during this audit',sha(correction_path)==sha(BASE/'FOUR_LISTING_CORRECTIONS.json'))

report={'schema':'boldstone.independent-four-listing-correction-audit.v1','audited_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':'PASS_BOUNDED_PREPARED_DRAFT' if all(c['status']=='PASS' for c in checks) else 'FAIL','scope':'Independent local byte/source/semantic review of four prepared listing corrections and sealed overlap alignment. No live fetch, shared write, native platform request or executable mutation code.','audited_parent_corrections_sha256':sha(correction_path),'frozen_master_sha256':sha(master_path),'step07_rebased_master_sha256':sha(rebase_path),'fresh_native_inventory_sha256':sha(WORKER/'FRESH_PUBLIC_INVENTORY.json'),'sealed_overlap_proposals_sha256':sha(WORKER/'OVERLAP_PROPOSALS.json'),'sealed_prior_manifest_sha256':sha(WORKER/'SEAL.json'),'official_cached_evidence_sha256':sha(OUT/'OFFICIAL_API_EVIDENCE.json'),'checks':checks,'check_count':len(checks),'record_results':record_results,'execution_limits':['PASS concerns prepared correction scope and schema; it is not an account-write, exact manufactured-version, stock, packing, hardware or physical-measurement receipt.','Authenticated same-store identity/before-state checks, concurrent-change checks and required headers remain execution preconditions; no credentials were read or written.','Moon Water Catcher price-on-enquiry copy requires the grouped purchase/enquiry-flow change before publication; this product name/description-only body neither changes the native800GBP value nor disables checkout.','Existing SKU digits remain legacy identifiers; accepted artwork sizes are not written into native shippingMeasurements.','Original accepted master_fields remain preserved, including material/price/source uncertainties.','Root coordinator alone may import the addendum or produce platform actions under the existing authorization.'],'live_fetches_by_this_addendum':0,'shared_or_platform_writes':0}
(OUT/'FOUR_LISTING_CORRECTIONS_AUDIT.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
print(json.dumps({'status':report['status'],'checks':len(checks),'failures':[c for c in checks if c['status']=='FAIL'],'audit_sha256':sha(OUT/'FOUR_LISTING_CORRECTIONS_AUDIT.json'),'audited_corrections_sha256':sha(correction_path)},indent=2))
assert report['status']=='PASS_BOUNDED_PREPARED_DRAFT'
