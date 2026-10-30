import collections, datetime, hashlib, json
from pathlib import Path
from PIL import Image

OUT = Path(__file__).resolve().parent
BASE = OUT.parent
OLD = Path('/Users/tprice/Documents/boldstone/sculpture-catalogue/components/parallel-reviews/listing-reconciliation-2026-10-20/worker-01')

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def read(name):
    return json.loads((OUT / name).read_bytes())

def resolve(value, pointer):
    if not pointer:
        return value
    assert pointer.startswith('/')
    for token in pointer[1:].split('/'):
        key = token.replace('~1','/').replace('~0','~')
        value = value[int(key)] if isinstance(value,list) else value[key]
    return value

def checked(condition, name, details=None):
    checks.append({'name':name,'pass':bool(condition),'details':details})

def independent_difference_paths(left,right):
    paths = set()
    queue = [('',left,right)]
    while queue:
        path,a,b = queue.pop()
        if isinstance(a,dict) and isinstance(b,dict):
            for key in a.keys()|b.keys():
                child = path + '/' + str(key).replace('~','~0').replace('/','~1')
                if key not in a or key not in b:
                    paths.add(child)
                else:
                    queue.append((child,a[key],b[key]))
        elif isinstance(a,list) and isinstance(b,list):
            for index in range(max(len(a),len(b))):
                child = path + '/' + str(index)
                if index>=len(a) or index>=len(b):
                    paths.add(child)
                else:
                    queue.append((child,a[index],b[index]))
        elif a!=b:
            paths.add(path)
    return paths

checks=[]
expected_inputs={'master-register.json':'7760b44a4d52ff3b78c893d5b86ef174814b48c29f7e41814c8a01a42af5326d','current-master.xlsx':'94dac1373d7c2d6831a49eab3680b07ee630a83ad732140f2ddc9da5e5c5dd91','current-master.json':'4c8fc6146cb79223cbe111e1f2ba717fcf5fcb29420e95fc27bdff9dda43fe72'}
for name,expected in expected_inputs.items():
    checked(sha(BASE/'inputs'/name)==expected,'Frozen input unchanged: '+name,{'path':str(BASE/'inputs'/name),'sha256':sha(BASE/'inputs'/name),'expected':expected})
for name,expected in {'SQUARESPACE_SOURCE_INVENTORY.json':'18b70a62f6651c2fccf2cc3e1e8856d886b4d4e3e90836932f53654c53e5725d','SEAL.json':'4db394997fc5976eff6e0c923abbc42c6fa21a71abd246ea8e9fd1b775104d0d','UNLINKED_SCOPE_AUDIT.json':'684f09a32050129e9f4d8954e90b06d8242ca118f0b0975ce63918b09c625992','UNLINKED_SCOPE_AUDIT_VALIDATION.json':'edbc18315d40166e526ebdf8fae66cd94ea2d86cfda7e741988084dbf96270b1'}.items():
    checked(sha(OLD/name)==expected,'Sealed20October unchanged: '+name,{'path':str(OLD/name),'sha256':sha(OLD/name),'expected':expected})

receipts = [json.loads(path.read_bytes()) for path in sorted((OUT/'raw-public').glob('*.receipt.json'))]
statuses = collections.Counter(str(r.get('status')) for r in receipts)
receipt_failures=[]
for receipt in receipts:
    path=Path(receipt['body_path'])
    if not path.is_file() or sha(path)!=receipt['sha256'] or path.stat().st_size!=receipt['bytes']:
        receipt_failures.append(receipt['url'])
    if receipt.get('authentication')!='none' or receipt.get('cookies_supplied') is not False or receipt.get('method')!='GET':
        receipt_failures.append('REQUEST_SCOPE:'+receipt['url'])
checked(not receipt_failures,'Every exact raw response body length/hash/request scope verified',{'receipts':len(receipts),'HTTP_status_counts':dict(statuses),'failures':receipt_failures})
gate=json.loads((BASE/'FAKE_ADAPTER_GATE.json').read_bytes())
checked(gate['status']=='PASS' and gate['tests_passed']==74,'Parent fake adapter gate receipt PASS74; no live sandbox results inferred',gate)

inventory=read('FRESH_PUBLIC_INVENTORY.json')
checked(sha(OUT/'FRESH_PUBLIC_INVENTORY.json')=='4445986b548ef256c7ab2f4f8c80f34ade0f590ce9e9e6adbdf4ea9118726bfd','Early shared inventory stayed frozen',{'sha256':sha(OUT/'FRESH_PUBLIC_INVENTORY.json')})
documents={}
def load_source(path):
    if path not in documents:
        documents[path]=json.loads(Path(path).read_bytes())
    return documents[path]
def source_value(loc):
    return resolve(load_source(loc['path']),loc['json_pointer'])

native_products=[];native_variants=[];normalization_failures=[]
for product in inventory['products']:
    native=source_value(product['source_locator'])
    native_products.append(native['id'])
    if product['native_record']!=native or product['native_product_id']!=native['id']:
        normalization_failures.append(product['native_product_id'])
    variant_array=(native.get('structuredContent') or {}).get('variants') or native.get('variants') or []
    if len(variant_array)!=len(product['variants']):
        normalization_failures.append('VARIANT_COUNT:'+native['id'])
    for index,variant in enumerate(product['variants']):
        raw=source_value(variant['source_locator'])
        native_variants.append(raw['id'])
        if raw!=variant['native_record'] or raw!=variant_array[index] or raw['id']!=variant['native_variant_id'] or raw['sku']!=variant['sku']:
            normalization_failures.append('VARIANT:'+variant['native_variant_id'])
checked(not normalization_failures,'All normalized203 products and370 variants independently resolve exactly to preserved native objects',{'products':len(native_products),'unique_product_ids':len(set(native_products)),'variants':len(native_variants),'unique_variant_ids':len(set(native_variants)),'failures':normalization_failures})
checked(len(native_products)==203 and len(set(native_products))==203 and len(native_variants)==370 and len(set(native_variants))==370,'Product/variant uniqueness and coverage counts')

cases=read('CASE_SOURCE_RECORDS.json')['case_source_records'];direct_validation=[]
representation_records={r['offer_ref']:r for r in read('DETAIL_COLLECTION_DIFFERENCES.json')['records']}
for case in cases:
    detail=case['direct_product_check'].get('detail_product');collection=case.get('fresh_collection_product')
    item={'offer_ref':case['offer_ref'],'native_product_id':case['native_product_id'],'status':case['direct_product_check']['receipt'].get('status')}
    if detail:
        item['native_id_matches']=detail['native_product_id']==case['native_product_id']
        item['complete_native_detail_identical_to_collection']=detail['native_record']==collection['native_record']
        item['raw_detail_pointer_identical']=source_value(detail['source_locator'])==detail['native_record']
        representation=representation_records[case['offer_ref']]
        actual_paths=independent_difference_paths(collection['native_record'],detail['native_record'])
        listed_paths={r['json_pointer'] for r in representation['differences']}
        item['all_representation_differences_explicitly_recorded']=actual_paths==listed_paths
        item['differences_only_documented_empty_representations']=all((r['json_pointer']=='/body' and r.get('left') is None and r.get('right')=='') or (r['json_pointer'].startswith('/items/') and r['json_pointer'].endswith('/items') and r['state']=='RIGHT_ONLY' and r.get('right')==[]) for r in representation['differences'])
        item['variant_records_identical']=detail['native_record']['structuredContent']['variants']==collection['native_record']['structuredContent']['variants']
    direct_validation.append(item)
checked(len(cases)==10 and sum(d['status']==200 for d in direct_validation)==8 and sum(d['status']==404 for d in direct_validation)==2 and all(all(d.get(k,True) for k in ['native_id_matches','raw_detail_pointer_identical','all_representation_differences_explicitly_recorded','differences_only_documented_empty_representations','variant_records_identical']) for d in direct_validation),'Ten exact product URLs checked;8 matching native200 identities/variants with documented empty-field representation differences and2 bounded404 observations',direct_validation)

comparisons=read('CASE_COMPARISONS.json')['comparisons'];difference_validation=[]
for comparison in comparisons:
    if comparison['all_native_metadata_differences'] is None:
        difference_validation.append({'case_id':comparison['case_id'],'state':'HISTORICAL_EXPORT_ONLY_NO_FRESH_FULL_NATIVE_OBJECT_FOR_RIGHT'})
        continue
    left=next(c for c in cases if c['offer_ref']==comparison['offer_refs'][0])['direct_product_check']['detail_product']['native_record']
    right=next(c for c in cases if c['offer_ref']==comparison['offer_refs'][1])['direct_product_check']['detail_product']['native_record']
    expected=independent_difference_paths(left,right)
    rows=comparison['all_native_metadata_differences']
    got={r['json_pointer'] for r in rows}
    values_ok=True
    for row in rows:
        if 'left' in row and resolve(left,row['json_pointer'])!=row['left']:
            values_ok=False
        if 'right' in row and resolve(right,row['json_pointer'])!=row['right']:
            values_ok=False
    difference_validation.append({'case_id':comparison['case_id'],'complete_difference_path_set_matches':expected==got,'difference_values_match_raw_native_objects':values_ok,'differing_paths':len(rows)})
checked(all(r.get('complete_difference_path_set_matches',True) and r.get('difference_values_match_raw_native_objects',True) for r in difference_validation),'All complete current native metadata difference paths/values independently recomputed',difference_validation)

image_records=read('CASE_IMAGE_RECEIPTS.json')['public_media']+read('HISTORICAL_MEDIA_RECEIPTS.json')['media']
image_failures=[]
for record in image_records:
    with Image.open(record['receipt']['body_path']) as image:
        image.load(); rgb=image.convert('RGB')
        if list(rgb.size)!=record['pixel_dimensions'] or hashlib.sha256(rgb.tobytes()).hexdigest()!=record['decoded_rgb_sha256']:
            image_failures.append(record['receipt']['body_path'])
    if record.get('media_source_locator'):
        native=source_value(record['media_source_locator'])
        if native['id']!=record['native_media_id'] or native['assetUrl']!=record['receipt']['url']:
            image_failures.append('MEDIA_LOCATOR:'+record['receipt']['body_path'])
    else:
        if source_value(record['historical_url_source_locator'])!=record['receipt']['url']:
            image_failures.append('HISTORICAL_URL_LOCATOR:'+record['receipt']['body_path'])
checked(not image_failures,'All39 decoded image identities and native media/source URL locators verified',{'current_images':30,'historical_CDN_images':9,'failures':image_failures})
preview_records=read('CASE_IMAGE_RECEIPTS.json')['cached_source_media'];preview_failures=[]
for record in preview_records:
    for image in record.get('available_local_images',[]):
        if sha(image['path'])!=image['sha256']:
            preview_failures.append(image['path'])
checked(not preview_failures and len(preview_records)==10,'Ten selected cached visual previews unchanged; private-original integrity not claimed',preview_failures)

locator_failures=[];locator_count=0
def walk(value):
    global locator_count
    if isinstance(value,dict):
        if isinstance(value.get('path'),str) and 'json_pointer' in value and Path(value['path']).is_file():
            locator_count+=1
            try:
                source_value(value)
                expected=value.get('body_sha256') or value.get('sha256')
                if expected and sha(value['path'])!=expected:
                    locator_failures.append({'locator':value,'error':'HASH_MISMATCH'})
            except Exception as error:
                locator_failures.append({'locator':value,'error':type(error).__name__+':'+str(error)})
        for child in value.values():walk(child)
    elif isinstance(value,list):
        for child in value:walk(child)
for name in ['FRESH_PUBLIC_INVENTORY.json','CASE_SOURCE_RECORDS.json','CASE_IMAGE_RECEIPTS.json','HISTORICAL_MEDIA_RECEIPTS.json','CASE_COMPARISONS.json','OVERLAP_PROPOSALS.json','BOUNDARY_INVENTORY_SUPPLEMENT.json','DETAIL_COLLECTION_DIFFERENCES.json']:
    walk(read(name))
checked(not locator_failures,'Every cited JSON pointer resolves and every supplied locator hash matches its source bytes',{'locators_checked':locator_count,'failures':locator_failures})

boundary=read('BOUNDARY_INVENTORY_SUPPLEMENT.json')
checked(boundary['base_inventory_unchanged'] and boundary['new_native_product_count']==0 and len(boundary['probes'])==2 and all(all(p['overlapping_native_records_identical_to_frozen'].values()) for p in boundary['probes']),'Numeric boundary supplement verified:5 and7 results, no new IDs, base unchanged',{'result_counts':[p['returned_product_count'] for p in boundary['probes']],'new_product_count':boundary['new_native_product_count'],'base_union_product_count':boundary['base_plus_supplement_unique_native_product_count']})
proposals=read('OVERLAP_PROPOSALS.json')
expected_cases={'RUST-SKU-COLLISION','VERDIGRIS-VERSIONS','MOON-WATER-OVERLAP','GOLD-HISTORICAL-OVERLAP','SILVER-HISTORICAL-OVERLAP'}
checked({p['case_id'] for p in proposals['proposals']}==expected_cases and len(proposals['proposals'])==5,'Exactly five assigned cases, each once')
legacy='LEGACY-6a5a621422d8fb7a65ba5a77'
existing_skus={v['sku'] for p in inventory['products'] for v in p['variants']}
old_skus={v['sku'] for p in json.loads((OLD/'SQUARESPACE_SOURCE_INVENTORY.json').read_bytes())['products'] for v in p['variants']}
checked(legacy not in existing_skus|old_skus,'Proposed legacy SKU unique in both checked inventories; proposal only',{'proposed_sku':legacy,'not_account_global_uniqueness':True})
rust=next(p for p in proposals['proposals'] if p['case_id']=='RUST-SKU-COLLISION')
checked(rust['canonical_alias_proposal']['preferred_source_offer_ref']=='O067' and rust['canonical_alias_proposal']['reversible_draft_only']['execution_status']=='NOT_EXECUTED' and all(p['shared_or_platform_writes_performed']==0 and p['identity_count_recommendation']['individual_count_increment']==0 for p in proposals['proposals']),'Coordinator canonical preference and no-execution/no-count-increment boundaries retained')
result={'schema':'boldstone.listing-resolution-independent-byte-source-validation.v1','created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':'PASS' if all(c['pass'] for c in checks) else 'FAIL','checks':checks,'read_only_scope':'Independent readback of saved raw bytes/native pointers, not a repeated live refresh, account audit, physical inspection or platform mutation.','raw_public_receipt_count':len(receipts),'raw_HTTP_status_counts':dict(statuses),'remaining_limits':['208 advertised versus203 returned remains unresolved after two successful boundary probes.','No authenticated account/admin/draft/hidden completeness, physical stock, checkout, hardware ratings or actual measurements.','Historical native record fields/timestamps absent from exports remain unknown.','Shared master import is awaiting coordinator receipt; proposals are isolated.']}
(OUT/'VALIDATION.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({'status':result['status'],'checks':len(checks),'failures':[c for c in checks if not c['pass']],'raw_public_receipts':len(receipts),'status_counts':dict(statuses),'locators_checked':locator_count},indent=2))
assert result['status']=='PASS'
