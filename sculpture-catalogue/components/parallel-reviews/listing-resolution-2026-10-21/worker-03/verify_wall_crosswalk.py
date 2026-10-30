#!/usr/bin/env python3
"""Independent readback against frozen originals and fresh native raw rows."""
from pathlib import Path
from datetime import datetime,timezone
from itertools import product
import hashlib,json
from PIL import Image
O=Path(__file__).resolve().parent;B=O.parent
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
r=lambda p:json.loads(Path(p).read_text())
def ref(p):return {'path':str(p),'sha256':sha(p)}
def dbh(p):
 out=hashlib.sha256()
 with Path(p).open('rb') as f:
  while True:
   q=f.read(4*1024*1024)
   if not q:break
   out.update(hashlib.sha256(q).digest())
 return out.hexdigest()
M=B/'inputs/master-register.json';F=B/'worker-01/FRESH_PUBLIC_INVENTORY.json';C=O/'WALL_CIRCLE_CROSSWALK.json';A=O/'WALL_CIRCLE_OUTCOMES.json';P=O/'PAIRWISE_PATTERN_REVIEW.json';G=O/'NATIVE_WALL_CIRCLE_GRID.json';L=O/'LOCAL_INPUTS.json';R=O/'NATIVE_GALLERY_ASSET_RECEIPTS.json'
checks=[]
def check(name,val):
 checks.append({'check':name,'pass':bool(val)})
 if not val:raise AssertionError(name)
check('frozen master exact SHA',sha(M)=='7760b44a4d52ff3b78c893d5b86ef174814b48c29f7e41814c8a01a42af5326d')
check('fresh public inventory exact SHA',sha(F)=='4445986b548ef256c7ab2f4f8c80f34ade0f590ce9e9e6adbdf4ea9118726bfd')
m=r(M);f=r(F);c=r(C);a=r(A);p=r(P);grid=r(G);loc=r(L);receipt=r(R);entries={x['review_id']:x for x in c['entries']};native=next(x for x in f['products'] if x['native_product_id']=='68dc0a35a7ac865209b39248');nvs={x['native_variant_id']:x['native_record'] for x in native['variants']};gov={x['variant_id']:x for x in m['wall_circle_native_options']};gridvs={x['native_variant_id']:x for x in grid['rows']}
check('all seven distinct visual records',set(entries)=={'WC-01','WC-02','WC-03','WC-04','WC-05','WC-06','WC-07'} and len(c['entries'])==7)
expected={'WC-01':('Cracked Malachite','8d2b5f4c-baf8-40d4-bd47-b19f5c2898c6','SQ1000026'),'WC-02':('Tropical Shards','e30d88d0-cba0-4f41-91e4-2ce53674f092','SQ1000002'),'WC-04':('Terra Cotta Shatter','39d2370c-db99-4442-a175-9c6d6ba52e0b','SQ1000066'),'WC-05':('Ochre Veins','3751bb3e-a4a1-4f06-ac06-5fa2a9f1e007','SQ1000106')}
size={'18.5cm/7.28in','36cm/14.17in','50cm/19.7in','100cm/39.37in'};lights={'No Light','RGB Color Light'}
check('all 144 fresh and frozen variant IDs retained',len(nvs)==len(gov)==len(gridvs)==144 and set(nvs)==set(gov)==set(gridvs))
patterns={x['attributes']['Pattern'] for x in nvs.values()};check('complete native 18 x 4 x 2 tuples',len(patterns)==18 and {(x['attributes']['Pattern'],x['attributes']['Diameter Size'],x['attributes']['Lighting']) for x in nvs.values()}==set(product(patterns,size,lights)))
check('unique 144 source SKUs',len({x['sku'] for x in nvs.values()})==144)
raws={}
for v in native['variants']:
 s=v['source_locator'];path=Path(s['path']);check('raw source SHA '+path.name,sha(path)==s['body_sha256'])
 if str(path) not in raws:raws[str(path)]=r(path)
 x=raws[str(path)]
 for token in s['json_pointer'].strip('/').split('/'):x=x[int(token)] if isinstance(x,list) else x[token]
 check('native raw variant '+v['native_variant_id'],x==v['native_record'])
for rid,e in entries.items():
 original=next(x for x in m['options'] if x['product_id']==e['product_id']);check(rid+' canonical name/file/folder preserved',e['retained_name']==original['name'] and e['source_file_id']==original['file_id'] and e['source_folder_id']==original['folder_id'])
 check(rid+' all 6 authoritative master_fields preserved',e['current_working_configuration_assignment']['master_fields_preserved']==original['master_fields'] and len(original['master_fields'])==6)
 check(rid+' no counts or fabricated ID increment',e['canonical_option_count_delta']==e['native_variant_count_delta']==e['new_native_ids_created']==0)
 check(rid+' specimen verification not inferred',e['logical_offered_variant_assignment']['physical_specimen_configuration_verified'] is False and e['pattern_assignment']['same_physical_piece_verified'] is False and e['current_working_configuration_assignment']['photographed_diameter_measured'] is False)
 if rid in expected:
  pattern,vid,sku=expected[rid];actual=nvs[vid];attrs=actual['attributes'];check(rid+' exact current 50cm RGB ID/SKU attributes',actual['sku']==sku and attrs['Pattern'].split('  ')[0]==pattern and attrs['Diameter Size']=='50cm/19.7in' and attrs['Lighting']=='RGB Color Light')
  assigned=e['logical_offered_variant_assignment'];check(rid+' deterministic lookup provided',assigned['native_variant_id']==vid and assigned['native_sku']==sku and assigned['native_attributes']==attrs and assigned['exact_native_row_lookup_verified'] is True)
  rows=e['offered_configuration_coverage']['variants'];check(rid+' all 8 exact offered tuples',len(rows)==8 and {(v['diameter_option'],v['lighting_option']) for v in rows}==set(product(size,lights)) and {v['native_variant_id'] for v in rows}=={v['id'] for v in nvs.values() if v['attributes']['Pattern']==attrs['Pattern']})
  check(rid+' price consistent with retained £600 working selection',actual['priceMoney']=={'currency':'GBP','value':'600.00'})
  check(rid+' visual working alias is not owner/native declared',e['pattern_assignment']['state']=='CONDITIONAL_VISUAL_PATTERN_DESIGN_LINK' and e['pattern_assignment']['formal_owner_native_pattern_declaration_found'] is False)
  check(rid+' circular native gallery composition receipt',e['circular_gallery_correspondence']['same_depicted_circular_fragment_composition_visually_confirmed'] is True)
 else:
  check(rid+' unsupported pattern has no numeric native invention',e['pattern_assignment']['pattern_short_name'] is None and e['logical_offered_variant_assignment']['native_variant_id'] is None and e['logical_offered_variant_assignment']['native_sku'] is None and e['offered_configuration_coverage']['variants']==[])
  d=e['custom_unlisted_draft_scope'];check(rid+' reviewable custom/unlisted draft retains existing record',d['scope_type']=='REVIEWABLE_CUSTOM_OR_UNLISTED_PATTERN_DRAFT' and d['existing_product_id']==e['product_id'] and d['native_variant_id'] is None and d['proposed_new_native_variant'] is False and d['canonical_count_delta']==0 and d['publication_ready'] is False and d['working_fields']==original['master_fields'])
check('all126 unique comparison pairs',len(p['entries'])==126 and len({(x['review_id'],x['native_pattern']) for x in p['entries']})==126 and {x['review_id'] for x in p['entries']}==set(entries) and {x['native_pattern'] for x in p['entries']}==patterns)
check('exactly four conditional comparisons',sum(x['state']=='CONDITIONAL_VISUAL_PATTERN_DESIGN_LINK' for x in p['entries'])==4)
check('zero falsely asserted byte/pixel equalities',not any(x['byte_equal'] or x['decoded_rgba_pixels_equal'] or x['exact_geometric_transform_to_swatch_established'] for x in p['entries']))
for v in loc['visual_records']+loc['native_patterns']:
 check('immutable local bytes '+v.get('review_id',v.get('short_name')),sha(v['local_path'])==v['sha256'] and dbh(v['local_path'])==v['dropbox_content_hash'])
for v in receipt['reads']:check('fresh gallery immutable bytes '+v['native_media_id'],sha(v['path'])==v['sha256'] and v['status']==200)
check('live reads separated from fake gate',receipt['fake_adapter_gate']['reported']['status']=='PASS' and receipt['fake_adapter_gate']['reported']['tests_passed']==74 and receipt['count']==4 and receipt['collection_reads']==receipt['dropbox_calls']==receipt['remote_mutations']==receipt['shared_writes']==0 and receipt['live_sandbox_tests_run'] is False)
check('compact and full 7 outcome records agree',[(x['review_id'],x['logical_offered_variant_assignment']) for x in a['entries']]==[(x['review_id'],x['logical_offered_variant_assignment']) for x in c['entries']])
check('all source/input hashes remain bound',all(sha(x['path'])==x['sha256'] for x in c['inputs']))
report={'schema':'boldstone.wall-circle-final-independent-readback.v1','status':'PASS_WITH_STATED_IDENTITY_LIMITS','recorded_utc':datetime.now(timezone.utc).isoformat(),'checks_passed':len(checks),'checks':checks,'artifact_bindings':[ref(x) for x in [M,F,C,A,P,G,L,R,O/'VALIDATION.json']],'scope_result':{'seven_outcomes':7,'conditional_working_pattern_assignments':4,'exact_native_working_50cm_rgb_tuple_lookups':4,'unresolved_among18_with_custom_unlisted_drafts':3,'offered_variants_grid_verified':144,'pattern_size_light_tuples':144,'new_variants':0,'shared_edits':0},'semantic_boundary':'The source lookup for the 50cm/RGB working selection is exact; the pattern assignment is visual/working. This does not verify the actual pictured diameter, RGB build, same physical piece, chemistry, safety, stock or installation provenance.','cached_image_time_boundary':'18 native swatches are 17 October cached binaries with IDs/URLs verified against 21 October raw native rows; four circular gallery images were freshly read. No stale-source claim is promoted to a 21 October byte observation.'}
(O/'FINAL_READBACK.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'status':report['status'],'checks_passed':len(checks),'receipt_sha256':sha(O/'FINAL_READBACK.json'),'artifact_bindings':report['artifact_bindings']},indent=2))
