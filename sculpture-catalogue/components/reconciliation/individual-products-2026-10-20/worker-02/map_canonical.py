from pathlib import Path
from collections import Counter
from datetime import datetime,timezone
import json,hashlib
W=Path(__file__).resolve().parent;ROOT=W.parent
A=json.load(open(W/'coverage_map.json'));REG=json.load(open(W/'register.snapshot.json'));PROG=json.load(open(W/'progress.snapshot.json'))
GP=ROOT/'canonical-products.json';gb=GP.read_bytes();G=json.loads(gb);(W/'canonical-products.snapshot.json').write_bytes(gb)
S={r['source_scope']:r for r in G['scope_reconciliation']}
PROD={p['product_id']:p for p in G['products']};CAND={c['candidate_id']:c for c in G['source_candidates']};REF={r['reference_id']:r for r in G['references']}
def uniq(x):return list(dict.fromkeys(x))
def targets(keys,kind=None):
 ids=uniq(t for k in keys if k in S for t in S[k]['targets'])
 return [i for i in ids if kind is None or (kind=='products' and i in PROD) or (kind=='candidates' and i in CAND) or (kind=='references' and i in REF)]
def descriptor(ids):
 return [{'target_id':i,'record_type':('INDIVIDUAL_WORKING_CATALOGUE_PRODUCT' if i in PROD else 'SOURCE_CANDIDATE' if i in CAND else 'REFERENCE'),'name':(PROD.get(i) or CAND.get(i) or REF.get(i) or {}).get('name',''),'canonical_key':(PROD.get(i) or {}).get('canonical_key')} for i in ids]
visual={
'CFG-F9E6B70398':{'source_groups':['G013'],'files':['id:cnqzTNngPVsAAAAAAAt_jw','id:cnqzTNngPVsAAAAAAAt_SA'],'visual_findings':'Viewed cached source001: tight marbled green/white surface crop with no complete relief silhouette. Source group is Cropped detail, no owner allocation override or per-finish identity decision recovered. Retain a surface-reference candidate, not a new Acanthus Two Leaves finish product.','result':'DETAIL_REFERENCE_IDENTITY_UNRESOLVED'},
'CFG-615FA0A6B1':{'source_groups':['G015'],'files':['id:cnqzTNngPVsAAAAAAAuQPA'],'visual_findings':'Viewed cached sole source: metallic gray/bronze broad curved-band detail, no complete outer panel. Existing Acanthus One Leaf Left Pewter Keep applies to different exact reference fileAufFw and its back-right target; no evidence equates this cropped G015 source with that kept finish.','result':'DETAIL_REFERENCE_IDENTITY_UNRESOLVED'},
'CFG-837B6C4244':{'source_groups':['G137'],'files':['id:cnqzTNngPVsAAAAAAAt-ZA'],'visual_findings':'Viewed sole source: tall left palm plus smaller right square arc panel. Existing source decision case12 documents Palm Forms and Silver Pewter effect from maker portfolios, but explicitly leaves Egyptian/Deco numbered alias mapping undocumented. Thus resolve the finish at source-group level while keeping exact individual identity unallocated.','basis_refs':['interior-exterior-projects:p1','metal-effects-2025:p1','prior-visual:case12'],'result':'SOURCE_GROUP_FINISH_DOCUMENTED_INDIVIDUAL_ALIAS_UNRESOLVED'},
'CFG-D8CA2AC5E9':{'source_groups':['G137'],'files':['id:cnqzTNngPVsAAAAAAAt-ZA'],'visual_findings':'Same exact two-panel source as Egyptian/Palm candidate. Silver Pewter surface name is documented for Palm Forms; right square member is not proved to be current Deco Two Leaves White design or its accepted Pewter equivalent. Do not map this to White BASE as if finish were covered.','basis_refs':['interior-exterior-projects:p1','metal-effects-2025:p1','prior-visual:case12'],'result':'SOURCE_GROUP_FINISH_DOCUMENTED_INDIVIDUAL_ALIAS_UNRESOLVED'},
'CFG-741F99704E':{'source_groups':['G140'],'files':['id:cnqzTNngPVsAAAAAAAylBQ','id:cnqzTNngPVsAAAAAAAylBA'],'visual_findings':'Viewed room and closer pair scenes. Existing source decision case13 identifies a two-palms family depiction but no formal per-panel mould numbers or record binding actual gold leaf to this particular pair. Golden Palm single offer O042 does not automatically cover a second gold panel in the scene. Retain as scene/individual-alias candidate, not a verified Egyptian Palm Two Gold product.','basis_refs':['public:golden-palm-wall-sculpture','public:two-palms-wall-sculpture','prior-visual:case13'],'result':'SCENE_REFERENCE_INDIVIDUAL_FINISH_AND_ALIAS_UNRESOLVED'},
'CFG-7D395F33C3':{'source_groups':['G098'],'files':['id:cnqzTNngPVsAAAAAAAuQFg','id:cnqzTNngPVsAAAAAAAsSmg'],'visual_findings':'Viewed both exact baseline examples and the kept Rust Spiral frontygCg. AuQFg shows a turquoise/rust wave on the left and separate brown/rust spiral on the right; AsSmg shows the rust spiral above the wave. The current Rust Spiral and Verdigris/Rust Waves reviews already allocate their respective members in the same G098 display referenceAsS6Q. Verdigris and rust is a legacy arrangement label, not evidence for an additional mixed-finish Spiral. Map the Spiral configuration to the existing Rust scope; retain the Wave as context only, without assigning a common physical cast or transferring specifications.','basis_refs':['components/reviews/specification_review_progress.json:reviews.BC-DR-SPIRAL.size_finish_variants.DR-SPIRAL-RUST','components/reviews/specification_review_progress.json:reviews.BC-DR-WAVE1.size_finish_variants.DR-WAVES-VERDIGRIS-RUST','components/reviews/dune-ripple-spiral-review-2026-10-17/rust/component-review.json:series_image_id/series_position/photo_coverage','components/reviews/dune-ripple-waves-dr1-review-2026-10-17/verdigris-rust/component-review.json:photo_coverage','components/reviews/dune-ripple-waves-dr1-review-2026-10-17/rust/mixed-series-review-index.json'],'result':'RESOLVED_LEGACY_ARRANGEMENT_LABEL_TO_EXISTING_SCOPES'}}
for row in A['baseline_configuration_coverage']:
 cid=row['source_component_id'];cfg=row['configuration_id'];status=row['coverage_state'];keys=row['current_candidate_scope_keys']
 if cfg=='CFG-7D395F33C3':
  row['bounded_local_visual_and_existing_review_check']=visual[cfg]
  row['coverage_state']='CURRENT_NAMED_SCOPE_PRESENT'
  row['current_candidate_scope_keys']=['BC-DR-SPIRAL|DR-SPIRAL-RUST'];keys=row['current_candidate_scope_keys']
  row['flags']=uniq(row['flags']+['LEGACY_ARRANGEMENT_FINISH_AGGREGATION_RESOLVED','CONTEXT_WAVE_IS_SEPARATE_EXISTING_DESIGN','SOURCE_REFERENCE_NOT_VERIFIED_EXTRA_PRODUCT'])
  row['notes']=[n for n in row['notes'] if not n.startswith('Arrangement-only rust/verdigris source does not select')]
  row['notes']=uniq(row['notes']+['Existing reviewed Rust Spiral and Verdigris/Rust Waves display roles resolve the legacy group label: Spiral is Rust; the separate Wave supplies the verdigris/rust part of the arrangement label. No additional Spiral finish is established.'])
 elif cfg in visual:
  row['bounded_local_visual_and_existing_review_check']=visual[cfg]
  row['coverage_state']='COVERED_FAMILY_EXACT_INDIVIDUAL_SCOPE_PENDING'
  row['current_candidate_scope_keys']=[];keys=[]
  row['flags']=uniq(row['flags']+['SOURCE_REFERENCE_NOT_VERIFIED_EXTRA_PRODUCT'])
 if cfg=='CFG-5DA926E103':
  row['notes']=uniq(row['notes']+['ShellB2 BASE and kept water child use exactly sameylqA primary/G306 source. G306 is only baseline group; no maker row or standalone offer. No documentary support for an extra standard-White wall build; map existing source to water child only.'])
  row['current_candidate_scope_keys']=['BC-SHELL-B2|SHELL-B2-WATER-WHITE'];keys=row['current_candidate_scope_keys'];row['coverage_state']='CURRENT_NAMED_SCOPE_PRESENT'
  row['flags']=uniq(row['flags']+['NO_SEPARATE_STANDARD_BUILD_EVIDENCE'])
 # A BASE source heading never automatically supplies an exact finish/build target.
 keys=row['current_candidate_scope_keys'];supported=[]
 if row['coverage_state'] in ['CURRENT_NAMED_SCOPE_PRESENT','CURRENT_BASE_WORKING_SCOPE_PRESENT']:
  supported=targets(keys,'products')
 elif row['coverage_state']=='ALIAS_OR_POSITION_REFERENCE_NOT_AN_ADDITIONAL_PRODUCT' and not cid.startswith('BC-LUCIANO-'):
  supported=targets(keys,'products')
 related=targets(row['component_related_scope_keys'],'products')
 row['exact_supported_target_ids']=supported
 row['exact_supported_target_basis']='Existing current review scope/source identity and finish crosswalk only; not exact physical-cast, current account listing or measured specification certification.' if supported else 'No exact individual product target established at this source configuration scope.'
 row['covered_family_product_ids']=uniq(related+supported)
 row['source_candidate_target_ids']=targets(row['component_related_scope_keys'],'candidates')
 row['reference_target_ids']=targets(row['component_related_scope_keys'],'references')
 if cfg=='CFG-7D395F33C3':
  row['context_member_scope_keys']=['BC-DR-WAVE1|DR-WAVES-VERDIGRIS-RUST']
  row['context_only_target_ids']=targets(row['context_member_scope_keys'],'products')
  row['context_member_is_not_the_source_configuration_product']=True
 if cid in ['BC-MLAVA-WALL-1','BC-MLAVA-WALL-2']:
  row['combined_arrangement_reference_id']='REF-MLAVA-1-PLUS-2-WHITE'
  row['reference_target_ids']=uniq(row['reference_target_ids']+['REF-MLAVA-1-PLUS-2-WHITE'])
  row['reference_specification_inheritance']=False
 # Never let a generic header's all-child target list masquerade as exact finish coverage.
 if not supported and not row['source_candidate_target_ids'] and row['reference_target_ids'] and not related:
  row['canonical_graph_coverage_state']='REFERENCE_ONLY'
 elif supported:
  row['canonical_graph_coverage_state']='EXACT_CURRENT_SCOPE_SUPPORTED'
 elif row['source_candidate_target_ids'] and not related:
  row['canonical_graph_coverage_state']='SOURCE_CANDIDATE_ONLY'
 elif related:
  row['canonical_graph_coverage_state']='COVERED_FAMILY_EXACT_SCOPE_PENDING'
 else:row['canonical_graph_coverage_state']='UNRESOLVED_SOURCE_REFERENCE'
 row['target_details']=descriptor(uniq(supported+row['source_candidate_target_ids']+row['reference_target_ids']))

unresolved={'O006','O007','O015','O046','O058','O059','O079','O039'}
for o in A['platform_coverage']:
 ref=o['offer_ref'];keys=o['candidate_current_review_scope_keys'];candidate=targets(keys,'products');supported=candidate.copy()
 if ref in unresolved:supported=[]
 if ref=='O072':
  supported=[i for i in supported if PROD[i]['canonical_design_id']=='BC-ECHO-2']
 if ref in ['O020','O055','O056']:
  supported=[i for i in supported if PROD[i]['canonical_design_id']!='BC-DP-SPIRAL']
 if ref in ['O010','O057']:supported=[] # gallery membership exists; single/set sale unit is not settled.
 if ref=='SH-DRAFT':supported=[]
 o['exact_supported_target_ids']=supported
 o['exact_supported_target_basis']='Supported source design/finish review scope; does not upgrade exact specimen/account SKU or accept conflicting source specifications.' if supported else 'Current design/family or member scopes are present, but exact offered identity/version/sale unit remains pending, or source is historical only.'
 o['covered_family_product_ids']=candidate
 o['source_candidate_target_ids']=targets(keys,'candidates')
 o['reference_target_ids']=targets(keys,'references')
 if ref=='SH-DRAFT':state='REFERENCE_ONLY_HISTORICAL_DRAFT'
 elif o['source_candidate_target_ids'] and not candidate:state='SOURCE_CANDIDATE_ONLY'
 elif supported and len(supported)==len(candidate):state='SUPPORTED_CURRENT_TARGETS_WITH_SOURCE_MATCH_LIMITS'
 elif candidate:state='COVERED_FAMILY_EXACT_SOURCE_SCOPE_PENDING'
 else:state='UNRESOLVED_SOURCE_REFERENCE'
 o['canonical_graph_coverage_state']=state
 o['target_details']=descriptor(uniq(supported+o['source_candidate_target_ids']+o['reference_target_ids']))
 o['source_offer_exact_specimen_or_live_account_match_certified']=False

A['canonical_graph_input']={'path':str(GP),'snapshot_path':str(W/'canonical-products.snapshot.json'),'sha256':hashlib.sha256(gb).hexdigest(),'created_utc':G['created_utc'],'products':len(G['products']),'source_candidates':len(G['source_candidates']),'references':len(G['references']),'coverage_definition':'exact_supported_target_ids means the existing current design/finish/build review record is supported by the stated source relationship. It does not certify current account SKU, physical cast or agreement of every source specification. covered_family_product_ids is deliberately broader and not a match.'}
A['bounded_resolution_notes']={'pewter_green_gold_candidates':[v for k,v in visual.items() if k!='CFG-7D395F33C3'],'dune_legacy_arrangement_resolution':visual['CFG-7D395F33C3'],'shell_b2_standard_build_check':{'baseline_configuration_id':'CFG-5DA926E103','source_group':'G306','source_file_id':'id:cnqzTNngPVsAAAAAAAylqA','source_folder_id':'id:cnqzTNngPVsAAAAAAAyjEg','conclusion':'Generic BASE and water child are the same documented source. Baseline component has no maker rows, offers or other standard group; no missing separate standard build is established. BSM1 and Islington independently retain separate standard and water records.'},'unknown_and_mixed_policy':'No new products or variants are counted from folder labels, unknown/mixed configurations, detail crops or styled scenes. Existing owner source decisions, group deferrals and per-file limits are preserved.'}
A['summary'].update({'canonical_working_products':len(G['products']),'canonical_graph_candidates':len(G['source_candidates']),'canonical_offer_coverage_counts':dict(Counter(o['canonical_graph_coverage_state'] for o in A['platform_coverage'])),'canonical_configuration_coverage_counts':dict(Counter(c['canonical_graph_coverage_state'] for c in A['baseline_configuration_coverage'])),'baseline_configuration_coverage_states':dict(Counter(c['coverage_state'] for c in A['baseline_configuration_coverage'])),'bounded_visual_reference_checks':len(visual)})
A['summary']['named_finish_source_candidates_without_current_named_scope']=[c['configuration_id'] for c in A['baseline_configuration_coverage'] if c['coverage_state']=='UNREVIEWED_NAMED_FINISH_SOURCE_CANDIDATE']
A['summary']['unresolved_exact_individual_source_scope_candidates']=[c['configuration_id'] for c in A['baseline_configuration_coverage'] if c['canonical_graph_coverage_state'] in ['COVERED_FAMILY_EXACT_SCOPE_PENDING','UNRESOLVED_SOURCE_REFERENCE']]
A['prepared_utc']=datetime.now(timezone.utc).isoformat()
queue_ids=['CFG-F9E6B70398','CFG-615FA0A6B1','CFG-837B6C4244','CFG-741F99704E','CFG-862A5C541F','CFG-99FCC64095','CFG-F2CBD96996','CFG-19FF96CC5A','CFG-D8CA2AC5E9','CFG-7D395F33C3']
queue=[]
for cfg in queue_ids:
 c=next(c for c in A['baseline_configuration_coverage'] if c['configuration_id']==cfg)
 groups=[r for r in REG['groups'] if r['id'] in c['baseline_series_folder_ids']+c['baseline_solo_folder_ids']+c['baseline_context_folder_ids']]
 resolved=cfg=='CFG-7D395F33C3'
 queue.append({'configuration_id':cfg,'source_component_id':c['source_component_id'],'source_component_name':c['source_component_name'],'baseline_finish_appearance_retained':c['baseline_finish_appearance'],'source_group_refs':[r['group_ref'] for r in groups],'source_folder_ids':uniq(c['baseline_series_folder_ids']+c['baseline_solo_folder_ids']+c['baseline_context_folder_ids']),'source_file_ids':c['example_file_ids'],'source_refs':['components/evidence/component_register.json:configurations.'+cfg]+['components/evidence/component_register.json:groups.'+r['group_ref'] for r in groups],'audit_state':'RESOLVED_TO_EXISTING_REVIEWED_PRODUCT_AND_CONTEXT' if resolved else 'SOURCE_CANDIDATE_IDENTITY_OR_FINISH_PENDING','exact_supported_target_ids':c['exact_supported_target_ids'],'context_only_target_ids':c.get('context_only_target_ids',[]),'findings':c.get('bounded_local_visual_and_existing_review_check',{'result':'ARRANGEMENT_FINISH_EQUIVALENCE_UNCONFIRMED','visual_findings':'Prior arrangement reviews and present allocation overrides do not establish a separate pure-Rust individual or equivalence to the kept Verdigris/Rust finish. Preserve the source group and current review relation as candidates only.'}),'remaining_information_needed':[] if resolved else (['Exact member-to-current-design allocation; do not repeat the already documented source-group Silver Pewter finish question.'] if cfg in ['CFG-837B6C4244','CFG-D8CA2AC5E9'] else ['A complete allocated individual reference or an existing explicit identity/finish decision tying this exact source to a current scope.']),'creates_new_product':False,'is_approval_request':False})
Q={'schema':'boldstone.named-appearance-source-information-queue.v1','prepared_utc':A['prepared_utc'],'source_case_count':len(queue),'resolved_existing_scope_cases':1,'unresolved_source_candidate_cases':9,'new_products_or_variants_created':0,'policy':'These are source-evidence cases, not ten extra products or ten unanswered owner questions. The one resolved legacy Dune aggregation is retained to prevent reopening. Source-group finish documentation is preserved separately from individual design allocation.','cases':queue}
A['summary']['named_appearance_source_information_cases']=10
A['summary']['named_appearance_cases_resolved_existing_scopes']=1
A['summary']['named_appearance_cases_pending']=9
A['named_appearance_information_queue']={'path':str(W/'named_appearance_source_queue.json'),'total_cases':10,'resolved_to_existing_scopes':1,'source_candidates_pending':9}
(W/'named_appearance_source_queue.json').write_text(json.dumps(Q,ensure_ascii=False,indent=2)+'\n')
(W/'coverage_map.json').write_text(json.dumps(A,ensure_ascii=False,indent=2)+'\n')
(W/'source_offer_coverage.json').write_text(json.dumps(A['platform_coverage'],ensure_ascii=False,indent=2)+'\n')
(W/'source_configuration_coverage.json').write_text(json.dumps(A['baseline_configuration_coverage'],ensure_ascii=False,indent=2)+'\n')
print(json.dumps(A['summary'],ensure_ascii=False,indent=2))
