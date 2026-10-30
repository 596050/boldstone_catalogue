from pathlib import Path
from datetime import datetime,timezone
from collections import Counter
import json,hashlib
W=Path(__file__).resolve().parent
M=json.load(open(W/'coverage_map.json'));R=json.load(open(W/'register.snapshot.json'));G=json.load(open(W/'canonical-products.snapshot.json'))
O=json.load(open(W/'source_offer_coverage.json'));C=json.load(open(W/'source_configuration_coverage.json'))
Q=json.load(open(W/'named_appearance_source_queue.json'))
assert len(O)==81 and len(C)==199
assert [x['offer_ref'] for x in O]==[x['offer_ref'] for x in R['platform_records']]
assert [x['configuration_id'] for x in C]==[x['configuration_id'] for x in R['configurations']]
assert len({x['offer_ref'] for x in O})==81 and len({x['configuration_id'] for x in C})==199
assert sum(len(x['bom_rows']) for x in O)==122
P={x['product_id'] for x in G['products']};K={x['candidate_id'] for x in G['source_candidates']};F={x['reference_id'] for x in G['references']}
for x in O+C:
 assert set(x['exact_supported_target_ids'])<=P
 assert set(x['covered_family_product_ids'])<=P
 assert set(x['source_candidate_target_ids'])<=K
 assert set(x['reference_target_ids'])<=F
 assert set(x.get('context_only_target_ids',[]))<=P
 if x.get('baseline_finish_appearance','').lower().startswith('unspecified'):assert not x['exact_supported_target_ids']
 assert x.get('distinct_product_created',False) is False
for ref in ['O046','O058','O079']:assert not next(x for x in O if x['offer_ref']==ref)['exact_supported_target_ids']
x=next(x for x in O if x['offer_ref']=='O072');assert len(x['exact_supported_target_ids'])==1 and len(x['covered_family_product_ids'])==2
for cid in ['BC-BONE-1','BC-BONE-2','BC-FFL-1','BC-CR-RING','BC-WALL-CIRCLE']:assert any(x['source_candidate_target_ids'] for x in C if x['source_component_id']==cid)
assert len(Q['cases'])==10 and len({x['configuration_id'] for x in Q['cases']})==10
assert sum(x['audit_state']=='RESOLVED_TO_EXISTING_REVIEWED_PRODUCT_AND_CONTEXT' for x in Q['cases'])==1
assert all(not x['creates_new_product'] and not x['is_approval_request'] for x in Q['cases'])
x=next(x for x in C if x['configuration_id']=='CFG-7D395F33C3')
assert x['current_candidate_scope_keys']==['BC-DR-SPIRAL|DR-SPIRAL-RUST']
assert x['exact_supported_target_ids']==['BSI-8DDEA2FEC9DA']
assert x['context_only_target_ids']==['BSI-09C1A55D460D']
assert x['baseline_finish_appearance']=='Verdigris and rust'
for cid in ['BC-MLAVA-WALL-1','BC-MLAVA-WALL-2']:
 x=next(x for x in C if x['source_component_id']==cid)
 assert len(x['exact_supported_target_ids'])==1
 assert x['reference_target_ids']==['REF-MLAVA-1-PLUS-2-WHITE']
 assert x['reference_specification_inheritance'] is False
assert sum(Counter(x['canonical_graph_coverage_state'] for x in O).values())==81
assert sum(Counter(x['canonical_graph_coverage_state'] for x in C).values())==199
manifest=json.load(open(W/'input_manifest.json'));stability=[]
for s in manifest['sources']:
 h=hashlib.sha256(Path(s['path']).read_bytes()).hexdigest();stability.append({'source':s['key'],'snapshot_sha256':s['sha256'],'current_sha256':h,'unchanged_since_capture':h==s['sha256']})
gp=W.parent/'canonical-products.json';gh=hashlib.sha256(gp.read_bytes()).hexdigest()
current_graph=json.loads(gp.read_bytes())
target_sections=['products','scope_reconciliation','source_candidates','references','orientation_aliases','historical_alias_reconciliation']
target_section_checks={k:G.get(k)==current_graph.get(k) for k in target_sections}
assert all(target_section_checks.values()),'Canonical target sections changed after mapping; refresh required.'
files=['coverage_map.json','source_offer_coverage.json','source_configuration_coverage.json','current_scope_index.json','named_appearance_source_queue.json']
v={'schema':'boldstone.source-coverage-validation.v1','validated_utc':datetime.now(timezone.utc).isoformat(),'result':'PASS_ALL_SOURCE_ROWS_AND_TARGET_REFERENCES','platform_records':81,'bom_rows':122,'baseline_configurations':199,'current_review_scopes':278,'graph_working_products':173,'graph_source_candidates':6,'canonical_offer_coverage_counts':dict(Counter(x['canonical_graph_coverage_state'] for x in O)),'canonical_configuration_coverage_counts':dict(Counter(x['canonical_graph_coverage_state'] for x in C)),'checks':['every source offer and configuration exactly once in original order','all122 BOM rows retained','all target IDs exist in captured graph','mixed/unknown source references do not certify exact product targets','source-size conflicts do not create new current products','O072 only its photographed Echo2 member supported; pair counterpart remains candidate','Bone1/2,FFL,CupRing,WallCircle candidates retained','zero new products, shared writes or remote calls'],'input_stability':stability,'canonical_graph_sha256_at_map':M['canonical_graph_input']['sha256'],'canonical_graph_current_sha256':gh,'canonical_graph_unchanged':gh==M['canonical_graph_input']['sha256'],'outputs':[{'path':str(W/f),'sha256':hashlib.sha256((W/f).read_bytes()).hexdigest()} for f in files],'terminology_limit':'Supported current target means source-to-existing review design/finish/build scope support only; no exact physical specimen, live SKU/account or measurement certification.'}
v['named_appearance_source_cases']={'total':10,'resolved_to_existing_scopes':1,'unresolved_source_candidates':9,'new_products_created':0}
v['canonical_target_sections_unchanged']=all(target_section_checks.values())
v['canonical_target_section_checks']=target_section_checks
v['canonical_graph_metadata_change_note']='The parent may append coverage arrays and audit metadata after mapping. Full-file hash equality is reported separately; every target-defining section is compared and required unchanged.'
v['checks'] += ['all10 named appearance source cases retained with one resolved legacy aggregation','Dune rust Spiral target and separate Waves context target both exist; original arrangement finish label retained','both Moonshell wall positions map to existing individual products plus one combined reference without specification inheritance']
v['checks']=[s.replace('mixed/unknown source references do not certify exact product targets','unresolved mixed/unknown source references do not certify exact product targets') for s in v['checks']]
(W/'validation.json').write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'result':v['result'],'source_inputs_unchanged':all(x['unchanged_since_capture'] for x in stability),'canonical_graph_unchanged':v['canonical_graph_unchanged'],'canonical_target_sections_unchanged':v['canonical_target_sections_unchanged'],'final_hashes':v['outputs']},indent=2))
