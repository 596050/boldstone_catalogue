#!/usr/bin/env python3
"""Independent semantic/source readback; no writes outside this directory."""
from pathlib import Path
from datetime import datetime,timezone
from collections import Counter
from itertools import product
import hashlib,json,csv,re,copy
O=Path(__file__).resolve().parent;B=O.parents[1];CAT=B.parents[2]
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(Path(p).read_text())
def ptr(o,s):
 for v in s.lstrip('/').split('/') if s else []:o=o[int(v)] if isinstance(o,list) else o[v.replace('~1','/').replace('~0','~')]
 return o
checks=[];errors=[];warnings=[]
def check(name,result,detail=None):
 d={'check':name,'pass':bool(result)}
 if detail is not None:d['detail']=detail
 checks.append(d)
 if not result:errors.append(d)
def ref(p):return {'path':str(p),'sha256':sha(p),'bytes':Path(p).stat().st_size}
files=['LISTING_RESOLUTION.json','OPTION_RESOLUTIONS_106.json','NEW_SOURCE_LINKS.json','NATIVE_ACTION_DRAFTS.json','IMPORT_PLAN.json','RESOLUTION_REVIEW.csv','FOUR_LISTING_CORRECTIONS.json','HISTORICAL_REFERENCE_RESOLUTIONS.json']
initial={n:ref(B/n) for n in files};m=load(B/'inputs/master-register.json');l=load(B/files[0]);q=load(B/files[1]);new=load(B/files[2]);actions=load(B/files[3]);plan=load(B/files[4]);cor=load(B/'FOUR_LISTING_CORRECTIONS.json');historical=load(B/'HISTORICAL_REFERENCE_RESOLUTIONS.json');f=load(B/'worker-01/FRESH_PUBLIC_INVENTORY.json');w=load(B/'worker-03/WALL_CIRCLE_CROSSWALK.json');w2=load(B/'worker-02/OPTION_RESOLUTIONS.json');groups=load(B/'worker-02/DRAFT_LISTING_GROUPS.json');hpath=Path('/Users/tprice/Documents/boldstone/sculpture-catalogue/components/parallel-reviews/listing-reconciliation-2026-10-20/worker-02/shopify_variants.json');h=load(hpath)
ms={x['product_id']:x for x in m['options']};qs={x['product_id']:x for x in q['entries']};os={x['product_id']:x for x in l['option_overlays']};ws={x['product_id']:x for x in w['entries']};w2s={x['product_id'] if 'product_id' in x else x['option_id']:x for x in w2['entries']};products={x['native_product_id']:x for x in f['products']};native={(p['native_product_id'],v['native_variant_id']):v for p in f['products'] for v in p['variants']}
check('frozen master SHA exact',sha(B/'inputs/master-register.json')=='7760b44a4d52ff3b78c893d5b86ef174814b48c29f7e41814c8a01a42af5326d')
check('fresh inventory SHA exact',sha(B/'worker-01/FRESH_PUBLIC_INVENTORY.json')=='4445986b548ef256c7ab2f4f8c80f34ade0f590ce9e9e6adbdf4ea9118726bfd')
check('184 distinct immutable catalogue IDs',len(ms)==184 and len(m['options'])==184)
check('1104 original field groups complete',sum(len(x['master_fields']) for x in m['options'])==1104 and all(len(x['master_fields'])==6 for x in m['options']))
prior_states={'NO_SUPPORTED_INDIVIDUAL_ASSOCIATION_IN_CHECKED_SOURCES','RELATED_FAMILY_ONLY_NO_INDIVIDUAL_MATCH','WALL_CIRCLE_FAMILY_ONLY_EXACT_VARIANT_UNRESOLVED','GALLERY_OR_DRAFT_CONTEXT_SALE_UNIT_UNRESOLVED','INDIVIDUAL_LISTING_CANDIDATE_SCOPE_UNRESOLVED'}
expected106={x['product_id'] for x in m['options'] if x['current_listing_reconciliation']['overall_disposition'] in prior_states}
check('all106 assigned IDs exactly once',len(expected106)==len(qs)==len(q['entries'])==106 and set(qs)==expected106)
check('all184 overlay IDs exactly once',len(os)==len(l['option_overlays'])==184 and set(os)==set(ms))
check('old81 offers262 evidence165 issues immutable and retained by source epoch',len(m['current_listing_source_links']['offers'])==81 and len(m['current_listing_match_evidence']['edges'])==262 and len(m['current_listing_issues']['issues'])==165 and new['historical_262_edges_deleted_or_rewritten'] is False and new['source_offer_count_increment']==new['native_or_catalogue_record_count_increment']==0)
for pid,x in os.items():
 s=ms[pid];check(pid+' overlay immutable key/name/family',x['canonical_key']==s['canonical_key'] and x['name']==s['name'] and x['family']==s['family']);check(pid+' reviewed flag exact106 membership',x['reviewed_in_assigned_106']==(pid in expected106));check(pid+' no accepted working change or physical certification',x['accepted_working_fields_changed'] is False and x['exact_current_physical_or_all_six_field_configuration_certified'] is False)
 check(pid+' no specification field replacement in overlay',not any(k in x for k in ['master_fields','specifications','name_proposal','sale_unit']))
 if pid in qs:
  z=qs[pid];check(pid+' overlay disposition/source links match106 row',x['current_source_resolution_disposition']==z['source_resolution_disposition'] and x['new_supported_source_matches']==z['supported_source_matches'] and x['conditional_native_tuple']==z['conditional_native_tuple'])
for pid,x in qs.items():
 s=ms[pid];check(pid+' six complete accepted fields copied faithfully',x['accepted_working_fields']==s['master_fields'] and len(x['accepted_working_fields'])==6);check(pid+' no physical/admin/live absence promotion',all(x[k] is False for k in ['accepted_working_fields_changed','physical_configuration_verified','authenticated_admin_inventory_verified','proven_live_absent']))
 src=x['source_ref'];val=ptr(load(src['path']),src['json_pointer']);check(pid+' source pointer exact same option',val.get('product_id',val.get('option_id'))==pid)
 if pid in ws:
  z=ws[pid];check(pid+' WC conditional lookup exact worker record',x['conditional_native_tuple']==z['current_working_configuration_assignment']['existing_native_variant_candidate']);check(pid+' WC patterns and all8 source tuples exact',x['pattern_assignment']==z['pattern_assignment'] and x['all_eight_offered_tuples']==z['offered_configuration_coverage']);check(pid+' WC custom draft exact and null-ID scoped',x['custom_unlisted_pattern_draft']==z['custom_unlisted_draft_scope']);check(pid+' WC logical/physical split preserved',x['conditional_tuple_semantics']==z['logical_offered_variant_assignment']);check(pid+' no new listing draft under WC',x['draft_listing'] is None)
 else:
  z=w2s[pid];check(pid+' nonWC source matches copied faithfully',x['supported_source_matches']==z['new_supported_native_matches']);d=x['draft_listing']
  if x['source_supported_individual_record_added']:check(pid+' positive existing records have no new listing draft',d is None)
  elif d:
   check(pid+' draft six fields full source/master equality',d['six_working_fields']==s['master_fields']);check(pid+' draft component design scope exact',d['canonical_option_id']==pid and d['canonical_component_id']==s['canonical_component_id'] and d['canonical_design_id']==s['canonical_design_id']);check(pid+' draft creation not executed or authorized',d['publication_performed'] is False and d['creation_is_not_authorized_or_performed_by_this_packet'] is True and d['current_native_target'] is None)
positives=[x for x in q['entries'] if x['source_supported_individual_record_added']];drafts=[x['draft_listing'] for x in q['entries'] if x['draft_listing'] and x['draft_listing'].get('proposed_sku')];conditionals=[x for x in q['entries'] if x['conditional_native_tuple']];custom=[x['custom_unlisted_pattern_draft'] for x in q['entries'] if x.get('custom_unlisted_pattern_draft')]
check('two new positive options exact IDs', {x['product_id'] for x in positives}=={'BSI-09C1A55D460D','BSI-46F6DB226213'})
check('four conditional WC lookups and three custom null-ID scopes',len(conditionals)==4 and len(custom)==3 and all(d['native_variant_id'] is None and d['native_sku'] is None and d['proposed_new_native_variant'] is False and d['canonical_count_delta']==0 for d in custom))
check('97 draftSKUs76 product groups',len(drafts)==97 and len({d['proposed_product_group_id'] for d in drafts})==76)
check('draft97 match exact child groups', {d['canonical_option_id'] for d in drafts}=={v['canonical_option_id'] for z in groups['groups'] for v in z['variants']})
skus={d['proposed_sku'].strip().casefold() for d in drafts};ss_skus={v['sku'].strip().casefold() for p in f['products'] for v in p['variants'] if v['sku']};sh_skus={v['sku_raw'].strip().casefold() for v in h if v['sku_raw']};source_skus={o['source_sku'].strip().casefold() for o in m['current_listing_source_links']['offers'] if o['source_sku']}
check('97 proposed SKUs internally unique',len(skus)==97);check('no draftSKU collision with current publicSS historicalSH or original81offer SKUs',not(skus & (ss_skus|sh_skus|source_skus)))
check('source current presence47 vs prior45 exact overlay counts',sum(x['source_supported_individual_record_present'] for x in os.values())==47 and sum(s['current_listing_reconciliation']['overall_disposition'] in {'INDIVIDUAL_SOURCE_RECORD_LINKED','EXISTING_INDIVIDUAL_DESIGN_WITH_CONFIGURATION_CONFLICT'} for s in ms.values())==45)
check('scope dispositions agree computed',dict(Counter(x['source_resolution_disposition'] for x in q['entries']))==q['counts']['source_resolution_dispositions'])
check('counts do not report creations writes or live absence',all(q['counts'][k]==0 for k in ['accepted_working_fields_changed','exact_physical_or_all_six_field_configurations_certified','authenticated_admin_inventories_verified','proven_live_absences','native_products_or_variants_created','native_SKUs_created_or_changed']) and l['counts']['platform_writes']==l['counts']['shared_master_writes_by_this_lane']==0)
# Direct native tuple readbacks, independent of child output.
for edge in new['edges']:
 mt=edge['match'];pid=edge['option_id'];check(edge['evidence_edge_id']+' scoped existing option',pid in {x['product_id'] for x in positives} and edge['canonical_key']==ms[pid]['canonical_key']);check(edge['evidence_edge_id']+' no cast/allfields certification',edge['exact_current_physical_or_all_six_field_configuration_certified'] is False and mt['physical_configuration_verified'] is False and edge['native_or_catalogue_record_created'] is False)
 check(edge['evidence_edge_id']+' matches106 and parent overlay',mt in qs[pid]['supported_source_matches'] and mt in os[pid]['new_supported_source_matches'])
 if mt['platform']=='Squarespace':
  v=native.get((mt['native_product_id'],mt['native_variant_id']));check(edge['evidence_edge_id']+' exact native product variant SKU attributes',v is not None and v['sku']==mt['sku_raw'] and v['option_attributes']==mt['option_attributes']);check(edge['evidence_edge_id']+' exact current raw price stock',v['price']==mt['native_price'] and v['stock_setting']==mt['native_stock_setting']);src=mt['source_locator'];raw=ptr(load(src['path']),src['json_pointer']);check(edge['evidence_edge_id']+' raw tuple exact and source hash',sha(src['path'])==src['body_sha256'] and raw==v['native_record']);check(edge['evidence_edge_id']+' public nonadmin scope retained','NO_AUTHENTICATED_ADMIN' in mt['presence_scope'])
 else:
  sv=ptr(load(mt['source_inventory_ref']['path']),mt['source_inventory_ref']['json_pointer']);check(edge['evidence_edge_id']+' historical Shopify exact handle SKU tuple',sv['handle']==mt['handle'] and sv['sku_raw']==mt['sku_raw'] and sv['option_tuple']==mt['option_tuple']);check(edge['evidence_edge_id']+' no invented Shopify numeric IDs/current state',mt['numeric_product_id'] is None and mt['numeric_variant_id'] is None and mt['current_live_inventory_verified'] is False)
  loc=mt['source_row'];found=None;lastline=1
  with Path(loc['path']).open(newline='') as hfile:
   reader=csv.DictReader(hfile)
   for rowno,row in enumerate(reader,start=2):
    start=lastline+1;end=reader.line_num;lastline=end
    if rowno==loc['logical_row_including_header']:found=(row,start,end);break
  check(edge['evidence_edge_id']+' actual Shopify CSV row exact',found is not None and found[0]['Handle']==mt['handle'] and found[0]['Variant SKU']==mt['sku_raw'] and found[1]==loc['physical_line_start'] and found[2]==loc['physical_line_end'])
check('three additive edges on two options',len(new['edges'])==3 and len({e['evidence_edge_id'] for e in new['edges']})==3 and len({e['option_id'] for e in new['edges']})==2)
for z in conditionals:
 t=z['conditional_native_tuple'];v=native[(t['native_product_id'],t['native_variant_id'])];check(z['product_id']+' native WC tuple exact current50RGB',v['sku']==t['sku'] and v['option_attributes']=={'Pattern':t['pattern'],'Diameter Size':'50cm/19.7in','Lighting':'RGB Color Light'})
# All seven request bodies must be inert and narrowly scoped.
check('seven distinct nonexecuting request drafts',len(actions['actions'])==actions['request_drafts']==7 and len({x['action_id'] for x in actions['actions']})==7)
for x in actions['actions']:
 req=x['request_draft'];check(x['action_id']+' nonexecuting',req['executable_now'] is False and x['execution_status']=='NOT_EXECUTED');check(x['action_id']+' no inventory shipping price writes',not(set(req['body']) & {'price','priceMoney','salePrice','stock','qtyInStock','unlimited','weight','height','width','len','length','shipping','inventory'}))
 if x['action_type']=='EXISTING_PRODUCT_COPY_CORRECTION_DRAFT':
  check(x['action_id']+' copy-only body',set(req['body'])=={'name','description'} and x['inventory_and_shipping_measurements_action']=='NO_CHANGE' and x['native_sku_action']=='RETAIN');nid=x['native_identity'];v=native.get((nid['product_id'],nid['variant_id']));check(x['action_id']+' native copy target SKU exact',v is not None and v['sku']==nid['sku'] and req['path']=='/v2/commerce/products/'+nid['product_id'])
 elif x['action_type']=='EXISTING_VARIANT_SKU_CORRECTION_DRAFT':
  nid=x['native_identity'];v=native[(nid['native_product_id'],nid['native_variant_id'])];check('Rust collision targets only legacyO051',nid=={'native_product_id':'6a5a621422d8fb7a65ba5a77','native_variant_id':'ea0b690f-a56b-4c92-9f71-89d093e47a56'} and v['sku']==x['before_sku']=='EBAY-188654649217' and x['canonical_offer_retaining_original_sku']=='O067');newsku=x['proposed_sku'];check('Rust proposed legacy SKU unique bounded scope',newsku=='LEGACY-6a5a621422d8fb7a65ba5a77' and newsku.casefold() not in ss_skus|sh_skus|skus and req['body']=={'sku':{'present':True,'value':newsku}})
 else:check(x['action_id']+' visibility reversible draft only',x['action_type']=='REVERSIBLE_PRODUCT_VISIBILITY_QUARANTINE_DRAFT' and req['body']=={'isVisible':{'present':True,'value':False}} and x['url_access_or_checkout_disabled_claimed'] is False)
check('Rust existing current collision exactly two public variants',[(p['native_product_id'],v['native_variant_id']) for p in f['products'] for v in p['variants'] if v['sku']=='EBAY-188654649217']==[('6a5a621422d8fb7a65ba5a77','ea0b690f-a56b-4c92-9f71-89d093e47a56'),('6aa01aad7f3077314dd71e8c','ca0fa776-e58d-41a3-b11b-ce9a64f458e4')] or {(p['native_product_id'],v['native_variant_id']) for p in f['products'] for v in p['variants'] if v['sku']=='EBAY-188654649217'}=={('6a5a621422d8fb7a65ba5a77','ea0b690f-a56b-4c92-9f71-89d093e47a56'),('6aa01aad7f3077314dd71e8c','ca0fa776-e58d-41a3-b11b-ce9a64f458e4')})
check('four accepted specification records preserved',len(cor['records'])==4 and all(x['accepted_working_specifications']=={k:v['display'] for k,v in ms[x['product_id']]['master_fields'].items()} and x['accepted_specifications_changed'] is False and x['physical_specifications_certified'] is False for x in cor['records']))
prices={x['canonical_key']:x['commercial_policy_proposal'] for x in cor['records']};check('three accepted working asks1100 250350 kept',prices['BC-BONE-WATER|BASE']['value']=='1100.00' and prices['BC-DP-SPIRAL|DP-SPIRAL-GOLD-45x40']['value']=='250.00' and prices['BC-LEAF-FORM|LEAF-FORM-LF1-WHITE']['value']=='350.00');check('MWC enquiry draft preserves800 and599.69, no zero conversion',prices['BC-MOON-WATER|MOONWATER-WHITE']=={'mode':'PROPOSE_PRICE_ON_ENQUIRY','currency':'GBP','value':None,'retained_native_ask':'800.00','retained_local_draft':'599.69','zero_price_proposed':False})
check('O004 generic and O038 bright options distinct preserved',os['BSI-59530C6155C2']['source_supported_individual_record_present'] is True and os['BSI-09C1A55D460D']['source_supported_individual_record_present'] is True and os['BSI-59530C6155C2']['canonical_key']!=os['BSI-09C1A55D460D']['canonical_key'])
check('O009 prior generic positive retained no reallocation',os['BSI-4536FDCA0DA9']['source_supported_individual_record_present'] is True and os['BSI-4536FDCA0DA9']['prior_native_binding_downgraded'] is False and 'GENERIC_VERDIGRIS_GALLERY_RETAINED' in os['BSI-4536FDCA0DA9']['source_photo_binding_review'])
check('import rules retain source history and sole writer boundary',plan['sole_writer_thread']=='01a144ab-1a7c-7223-a403-73a4d53d70ff' and plan['native_execution_authority_or_access_granted_by_import'] is False and plan['shared_master_written_by_A_lane'] is False)
# CSV is a display of the same184 stable rows, not an additional count.
with (B/'RESOLUTION_REVIEW.csv').open(newline='') as file:csvrows=list(csv.DictReader(file))
check('CSV184 distinct stable rows',len(csvrows)==184 and len({x['product_id'] for x in csvrows})==184 and {x['product_id'] for x in csvrows}==set(ms))
for x in csvrows:
 z=os[x['product_id']];t=z['conditional_native_tuple'] or {};check(x['product_id']+' CSV semantic identity/status/tuple/limits',all(x[k]==str(z[k]) for k in ['canonical_key','name','prior_overall_disposition','current_source_resolution_disposition','source_supported_individual_record_present','reviewed_in_assigned_106','exact_current_physical_or_all_six_field_configuration_certified','next_action']) and x['conditional_native_variant_id']==t.get('native_variant_id','') and x['conditional_native_SKU']==t.get('sku',''))
# Check every concrete file/hash/pointer in payloads; resolve one explicitly preserved historical epoch.
refseen={};hashcache={};jsoncache={};historic_used=[]
def localpath(s):
 p=Path(s);return p if p.is_absolute() else CAT/p
for record in historical['resolutions']:
 hp=Path(record['historical_snapshot']['path']);check('dated historical source exact recovered bytes',sha(hp)==record['expected_historical_sha256']==record['historical_snapshot']['sha256'] and sha(record['historical_source_snapshot'])==sha(hp) and record['owner_values_changed'] is False)
def scan(o,origin,where=''):
 if isinstance(o,dict):
  if isinstance(o.get('path'),str) and ('sha256' in o or 'body_sha256' in o):
   path=localpath(o['path']);want=o.get('sha256',o.get('body_sha256'));k=(str(path),want,o.get('json_pointer'))
   if k not in refseen:
    valhash=sha(path) if path.exists() else None;resolved=path
    if valhash!=want:
     rr=next((h for h in historical['resolutions'] if h['original_path']==o['path'] and h['expected_historical_sha256']==want),None)
     if rr:resolved=Path(rr['historical_snapshot']['path']);valhash=sha(resolved);historic_used.append({'original_ref':o,'resolved_snapshot':str(resolved)})
    ok=valhash==want;check('reference exact hash '+str(path),ok,{'origin':str(origin),'pointer':where,'resolved_path':str(resolved)})
    if 'bytes' in o:check('reference exact bytes '+str(path),resolved.exists() and resolved.stat().st_size==o['bytes'])
    if ok and o.get('json_pointer'):
     try:
      key=str(resolved)
      if key not in jsoncache:jsoncache[key]=load(resolved)
      value=ptr(jsoncache[key],o['json_pointer']);check('reference exact JSON pointer '+str(path)+o['json_pointer'],True)
     except Exception as ex:check('reference exact JSON pointer '+str(path)+o['json_pointer'],False,str(ex))
    refseen[k]={'path':str(path),'expected_sha256':want,'observed_sha256':valhash,'json_pointer':o.get('json_pointer'),'resolved_path':str(resolved),'origin':str(origin)}
  for k,v in o.items():scan(v,origin,where+'/'+str(k))
 elif isinstance(o,list):
  for i,v in enumerate(o):scan(v,origin,where+'/'+str(i))
for name in files:
 if name.endswith('.json'):scan(load(B/name),B/name)
scan(load(l['overlap_and_collision_cases']['path']),Path(l['overlap_and_collision_cases']['path']))
check('owner authority exact local text SHA',sha(B/'OWNER_INSTRUCTION.json')==l['owner_instruction']['sha256'])
owner=load(B/'OWNER_INSTRUCTION.json');check('owner instruction exact message text hash',hashlib.sha256(owner['text'].encode()).hexdigest()==owner['text_sha256'])
line=None
with Path(owner['transcript']).open() as fp:
 for i,x in enumerate(fp,start=1):
  if i==owner['line']:line=x;break
check('owner original transcript line exact bytes',line is not None and hashlib.sha256(line.rstrip('\n').encode()).hexdigest()==owner['raw_line_sha256'] or line is not None and hashlib.sha256(line.encode()).hexdigest()==owner['raw_line_sha256'])
if line:check('owner exact user content appears in line',owner['text'] in json.dumps(json.loads(line),ensure_ascii=False) or owner['text'] in '\n'.join(c.get('text','') for c in json.loads(line).get('payload',{}).get('content',[]) if isinstance(c,dict)))
check('all parent bytes stable during readback',all(sha(B/n)==x['sha256'] for n,x in initial.items()))
check('master frozen unchanged at audit end',sha(B/'inputs/master-register.json')=='7760b44a4d52ff3b78c893d5b86ef174814b48c29f7e41814c8a01a42af5326d')
counts={'assigned_options':106,'all_overlay_options':184,'accepted_field_groups':1104,'accepted106_field_groups':636,'new_source_options':len(positives),'new_source_record_edges':len(new['edges']),'conditional_WC_working_tuples':len(conditionals),'custom_null_ID_scopes':len(custom),'draft_SKUs':len(drafts),'draft_groups':len({d['proposed_product_group_id'] for d in drafts}),'native_requests':len(actions['actions']),'native_products_created':0,'native_writes':0,'live_absence_certifications':0,'exact_file_hash_pointer_refs':len(refseen),'dated_epoch_resolutions_used':len(historic_used)}
report={'schema':'boldstone.independent-combined-listing-resolution-audit.v1','recorded_utc':datetime.now(timezone.utc).isoformat(),'status':'PASS_PREPARED_PACKET_WITH_BOUNDED_SOURCE_QUALIFICATIONS' if not errors else 'FAIL','checks_passed':sum(x['pass'] for x in checks),'checks_total':len(checks),'errors':errors,'warnings':warnings,'counts':counts,'parent_artifact_bindings':list(initial.values()),'source_reference_checks':list(refseen.values()),'historical_resolution_checks':historic_used,'checks':checks,'boundaries':['This verifies the prepared local packet, not a completed import or native execution. Root01a144ab remains sole writer; no after-master or workbook is asserted to exist.','The unchanged frozen master has184 options1104 fields; all copied106 scopes636 fields and four correction views compare equal. After-import equality remains the sole writer\'s required check.','Current public inventory203 products370 variants is a bounded anonymous observation with208 advertised discrepancy; authenticated admin completeness is unverified. Shopify136 products160 variants is a historical export; numeric IDs absent remain null.','Four WC pattern attributions are visual/working and source tuple lookups are exact; no photographed size, RGB build or physical cast certification.','97 variant drafts76 groups plus3 custom WC scopes are not100 native creations or proven live absences. Seven request objects are nonexecuting and do not change stock/shipping values.','Old81 source offers262 evidence edges165 issues remain immutable source history; three new edges are additive.','One inherited Chelsea dated reference resolves to exact recovered historical bytes; accepted assertions were not rewritten.'],'source_originals_modified_by_auditor':False,'platform_or_live_reads_by_auditor':0,'shared_writes_by_auditor':0}
(O/'COMBINED_AUDIT.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'status':report['status'],'checks':len(checks),'errors':errors,'counts':counts,'report_sha256':sha(O/'COMBINED_AUDIT.json'),'parent_hashes':{n:x['sha256'] for n,x in initial.items()}},indent=2))
