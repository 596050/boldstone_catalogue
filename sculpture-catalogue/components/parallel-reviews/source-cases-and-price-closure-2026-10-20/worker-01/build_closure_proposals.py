import json, hashlib, datetime
from urllib.parse import quote
from pathlib import Path

OUT=Path(__file__).parent
TASK=OUT.parent
IN=TASK/'inputs'
COMP=TASK.parent.parent
E=Path('/Users/tprice/Library/Application Support/BoldstoneImageConsistency/product-evidence-resolution-20261016T201618Z')
REG=json.load(open(IN/'component_register.json'))
CAN=json.load(open(IN/'canonical-products.json'))
CLASS=json.load(open(IN/'user_classifications.json'))
PROG=json.load(open(IN/'specification_review_progress.json'))
SHEET=json.load(open(E/'Manufacturing_Sheet_Extract.json'))
LABEL=json.load(open(E/'Manufacturing_Labelled_References.json'))
VIS=json.load(open(OUT/'visual-review-manifest.json'))
REFS={}
def esc(v): return str(v).replace('~','~0').replace('/','~1')
def source(rid,path,pointer='',**extra):
 p=Path(path)
 obj={'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),**extra}
 if pointer:
  v=json.load(open(p))
  for q in pointer.lstrip('/').split('/'):
   q=q.replace('~1','/').replace('~0','~')
   v=v[int(q)] if isinstance(v,list) else v[q]
  obj['json_pointer']=pointer
  obj['value_excerpt']=str(v)[:1200]
 REFS[rid]=obj
 return rid
def maker(rid,row,field):
 i=next(i for i,z in enumerate(SHEET) if z['row']==row)
 key=next(k for k in SHEET[i]['values'] if k.startswith(field))
 return source(rid,E/'Manufacturing_Sheet_Extract.json',f'/{i}/values/{esc(key)}',sheet='Sheet1',row=row,field=key)
def image_source(rid,row):
 i=next(i for i,z in enumerate(LABEL) if z['row']==row)
 source(rid,E/'Manufacturing_Labelled_References.json',f'/{i}',sheet_row=row)
 pic=LABEL[i]['picture']['path']
 source(rid+'-image',pic,role='DATED_MAKER_ILLUSTRATION',sheet_row=row)
 return rid
def asset(rid,file_id):
 i=next(i for i,a in enumerate(REG['assets']) if a['id']==file_id)
 source(rid,IN/'component_register.json',f'/assets/{i}')
 return REG['assets'][i]
def candidate(rid,cid):
 i=next(i for i,a in enumerate(CAN['source_candidates']) if a['component_id']==cid)
 source(rid,IN/'canonical-products.json',f'/source_candidates/{i}')
 return CAN['source_candidates'][i]
def field(display,proposal,state,refs,limits,accept=True):
 return {'display':display,'proposal':proposal,'evidence_state':state,'basis_refs':refs,
  'working_acceptance':'OWNER_AUTHORIZED_WORKING_ACCEPTANCE_UNDER_STANDING_POLICY' if accept else 'SOURCE_ASSERTION_RETAINED_NOT_APPLIED_TO_EXISTING_PRODUCT',
  'requires_repeat_owner_approval':False,'physical_verification_performed':False,'limits':limits}
def primary_from_asset(a,complete,why):
 vs=[v for z in VIS['cases'].values() for v in z['views'] if a['id'] in v['equivalent_asset_ids']]
 v=vs[0]
 return {'file_id':a['id'],'folder_id':a['folder_id'],'preview_path':v['path'],
  'shows_complete_single_component':complete,'selection_reason':why,
  'cache_kind':v['cache_kind'],'matches_saved_native_bytes_and_hash':v['matches_saved_native_bytes_and_hash'],
  'camera_or_render_provenance_confirmed':False,'source_ref':next(k for k,z in REFS.items() if z.get('json_pointer') and z.get('value_excerpt','').find(a['id'])>=0 and k.startswith('asset-'))}
def cached_browser_links(a):
 path=a['path'].split('//',1)[1].lstrip('/')
 parent=path.rsplit('/',1)[0]
 folder_url='https://www.dropbox.com/home/'+quote(parent,safe='/')
 return {'file_id':a['id'],'folder_id':a['folder_id'],'image_url':folder_url+'?preview='+quote(a['name'],safe=''),
  'folder_url':folder_url,'link_evidence_state':'DERIVED_FROM_CACHED_PATH; NOT_A_NEW_SHARED_LINK; NOT_LIVE_OPEN_TESTED',
  'path_source':'Frozen component_register asset; parent must bind current metadata separately'}

working=source('owner-working-policy',IN/'user_classifications.json','/working_specification_acceptance_policy_decisions/0')
made=source('owner-manufacture-policy',IN/'user_classifications.json','/manufacture_policy_decisions/0')
fix=source('owner-fixing-policy',IN/'user_classifications.json','/global_fixing_choice_policy_decisions/0')
weight=source('owner-approximate-weight-policy',IN/'user_classifications.json','/global_approximate_weight_policy_decisions/0')
instruction=source('owner-current-task',TASK/'owner-instruction.json','/text')
source('bone-owner-folder-split',IN/'user_classifications.json','/structure_changes/0')
source('bone1-owner-keep',IN/'user_classifications.json','/decisions/2')
source('bone2-owner-keep',IN/'user_classifications.json','/decisions/3')

for code,row in [('bone',91),('cup',27),('fish',73),('dr3',56),('dr1',54),('dr-trio',51)]:
 for short,prefix in [('code','Product Code A'),('mould','SIZE A                        '),('cast','SIZE A                          '),('fixing','Instructions on number'),('description','Description of whole piece in Standard Size A'),('weight','Approximate Weight of each piece in Standard Size A')]:
  maker(code+'-'+short,row,prefix)
 image_source(code+'-illustration',row)
for short,prefix in [('code','Product Code B'),('mould','SIZE B                        '),('cast','SIZE B                  '),('description','Description of whole piece in Standard Size B'),('weight','Approximate Weight of each piece in Standard Size B')]:
 maker('fish-long-'+short,73,prefix)
source('fish-shared-source-picture',E/'Manufacturing_Image_Anchors.json')
source('fish-shared-source-picture-A',E/'Manufacturing_Image_Anchors.json','/shapes/46')
source('fish-shared-source-picture-B',E/'Manufacturing_Image_Anchors.json','/shapes/147')
maker('fish-long-trio-one-mould',70,'SIZE B                        ')
maker('fish-long-pair-one-mould',71,'SIZE B                        ')
PRICE=COMP/'evidence/price-source-review-2026-10-17'
source('cup-individual-trade-2025',PRICE/'trade_price_rows.json','/20',pdf=str(Path('/Users/tprice/Documents/boldstone/price list draft documents/SCULPTURE TRADE PRICE List 2025.docx (1).pdf')),page=3,section='Cupring & Spiral',member_label='2',table_row=7,visually_reviewed=True,preview_path=str(COMP/'parallel-preparation/20261017T164751Z/worker-01/draft-trade-p03.jpg'))
source('cup-pair-trade-2025',PRICE/'trade_price_rows.json','/18')
source('fish-long-individual-trade-2025',PRICE/'trade_price_rows.json','/75',pdf=str(Path('/Users/tprice/Documents/boldstone/price list draft documents/SCULPTURE TRADE PRICE List 2025.docx (1).pdf')),page=11,section='Frozen Fish Long',table_row=3,visually_reviewed=True,preview_path=str(COMP/'parallel-preparation/20261017T164751Z/worker-01/draft-trade-p11.jpg'))
source('bone-pair-trade-2025',PRICE/'trade_price_rows.json','/85',page=13,unit='whole two-part arrangement; never allocate to members')
source('fish-long-retail-2025',Path('/Users/tprice/Documents/boldstone/price list draft documents/Retail PRICE List 2025.docx.pdf'),page=2,section='100cm x 22cm; Frozen Fish Long; quantity1',visually_reviewed=True,preview_path=str(COMP/'parallel-preparation/20261017T164751Z/worker-01/draft-retail-p02.jpg'))
source('trade-pdf',Path('/Users/tprice/Documents/boldstone/price list draft documents/SCULPTURE TRADE PRICE List 2025.docx (1).pdf'),pages_reviewed=[3,11])

entries=[]
for n,cid,fileid in [(1,'BC-BONE-1','id:cnqzTNngPVsAAAAAAA53EA'),(2,'BC-BONE-2','id:cnqzTNngPVsAAAAAAA53EQ')]:
 cand=candidate(f'candidate-bone{n}',cid)
 a=asset(f'asset-bone{n}',fileid)
 full=primary_from_asset(a,True,'Owner-kept individual reference shows all four outer edges and one complete component. Supplied image camera/render origin remains unconfirmed.')
 width=30 if n==1 else 55
 conflicts=[{'issue':'Different historical approximate weights','details':f'Frozen candidate says brochure {8.5 if n==1 else 15} kg; maker row91 calculates 10–12 kg each. Trade2025 records 8 kg &12 kg for the two parts without an independently established per-code binding. Retain each claim; do not average, divide or call them weighed.',
  'basis_refs':[f'candidate-bone{n}','bone-weight','bone-pair-trade-2025']},
 {'issue':'Historical fixing instructions disagree in scope','details':'Generic row91 fixing field says two fixings, but whole-piece description specifies one for55×30 and two for55×55. Current owner instruction offers keyhole or French cleat and does not certify installed hardware.',
  'basis_refs':['bone-fixing','bone-description',fix]},
 {'issue':'Set offers are not individual prices','details':'Existing pair offer and2025 pair price remain arrangement evidence; no pair price or exported pair mass is divided into a member amount.','basis_refs':['bone-pair-trade-2025',f'candidate-bone{n}']}]
 e={'component_id':cid,'source_scope':cid+'|BASE','proposed_name':cand['name'],'family':'Bone Spiral',
  'closure':'IDENTIFIED_INDIVIDUAL_ENQUIRY_PRODUCT','identity_state':'OWNER_KEPT_SINGLE_COMPONENT',
  'identity_evidence':{'owner_name_kept':True,'owner_keep_refs':[f'bone{n}-owner-keep'],'source_refs':['bone-mould','bone-cast','bone-illustration','bone-owner-folder-split'],
   'visual_finding':f'The {"narrow concave outer-turn" if n==1 else "square spiral-centre"} component in the current complete reference matches the corresponding BS{n} piece in the dated maker pair. BS1 and BS2 are explicitly two different moulds, not two orientations of one mould.'},
  'sale_unit':{'kind':'ONE_INDIVIDUAL_COMPONENT','quantity':1,'pair_mandatory':False,'basis_refs':[f'bone{n}-owner-keep','bone-cast',instruction]},
  'count_eligibility':{'identified_individual_component':True,'countable_individual_component_units':1,'catalogue_product_record_recommended':True,
   'not_excluded_for_missing_six_fields_or_price':True,'physical_stock_quantity':None,'physical_mould_inventory_count':None},
  'primary_example':full,'alternate_examples':[],'context_images':[],'series_images':[],
  'specifications':{
   'dimensions':field(f'Approximately55 H ×{width} W ×5–7 D cm — maker standard; unmeasured',{'height_cm':55,'width_cm':width,'depth_cm_range':[5,7]},'DATED_MAKER_DESIGN_STANDARD',['bone-cast','bone-description',working],'Actual cast and maximum projection unmeasured; no division of the85cm pair width.'),
   'weight':field('Approximately10–12 kg each — calculated maker estimate; conflicting dated claims retained',{'estimated_kg_range':[10,12],'weighed':False},'DATED_CALCULATED_ESTIMATE_ACCEPTED_AS_WORKING',['bone-weight',weight,working],'Does not resolve the brochure/trade conflicts or certify an actual mass.'),
   'material_finish':field('Jesmonite AC730, White Marble Stone Finish — historical standard; current cast recipe unverified',{'material':'Jesmonite AC730','finish':'White Marble Stone Finish'},'DATED_MAKER_STANDARD',['bone-description',working],'Source standard applies to this working White enquiry record only; image appearance does not establish actual binder/coating.'),
   'fixing':field('Choice of keyhole fixing or French cleat — owner instruction',{'options':['KEYHOLE','FRENCH_CLEAT'],'choose':1,'fitted_hardware':None,'load_rating':None},'OWNER_REQUESTED_CATALOGUE_CHOICE',[fix,'bone-fixing','bone-description'],'Historical narrow/wide fixing counts retained separately; attachment, count and capacity of actual hardware unknown.'),
   'individual_price':field('Price on enquiry — one component',{'currency':'GBP','amount':None,'price_on_enquiry':True,'quantity':1},'AUTHORIZED_WORKING_COMMERCIAL_POLICY',[instruction,working,'bone-pair-trade-2025'],'No currently confirmed individual money amount; set price not apportioned.'),
   'availability':field('Enquiry / made to order — working policy; stock and lead time unknown',{'enquiry':True,'made_to_order_proposal':True,'stock_quantity':None,'lead_time':None},'AUTHORIZED_WORKING_COMMERCIAL_POLICY',[instruction,working,made],'Universal owner manufacture statement is retained; present stock, capacity and lead time are not established.')},
  'source_conflicts':conflicts,'missing_evidence':['Actual measured dimensions and weight if a verified sales sheet is required','Actual rear/fixing details and load capacity','Current individual monetary price, stock and lead time','Camera/render provenance of supplied current individual reference'],
  'platform_mapping':{'existing_pair_offer_only':True,'individual_exact_match_confirmed':False,'action':'No platform write; use enquiry record locally'},
  'readiness':{'identity_and_count':True,'six_working_fields_prepared':True,'working_policy_authority_applies':True,'measured_specification_sheet':False,'confirmed_fixed_retail_price':False,'buy_now_publication':False},
  'handoff_notes':['Promote from source-candidate status for identity/count; keep owner-kept name and complete current reference.','Do not demand another keep or another six-field affirmative reply.','Apply only via the sole final-register writer; no shared imports performed by this lane.']}
 if n==2:
  altv=VIS['cases']['bone']['views'][13]
  alta=asset('asset-bone2-legacy-single',altv['asset_id'])
  e['alternate_examples'].append(primary_from_asset(alta,True,'Historical complete wide component mounted alone; visibly matches source BS2. This is a photographed reference, not a new mould or additional sale unit.'))
 pairv=VIS['cases']['bone']['views'][9]
 paira=asset('asset-bone-pair',pairv['asset_id'])
 e['series_images'].append({'file_id':paira['id'],'folder_id':paira['folder_id'],'preview_path':pairv['path'],'shows_complete_single_component':False,'role':'TWO_COMPONENT_PAIR_CONTEXT','basis_ref':'asset-bone-pair'})
 entries.append(e)

cand=candidate('candidate-cup','BC-CR-RING')
a=asset('asset-cup-crop','id:cnqzTNngPVsAAAAAAAt_3g')
pair=asset('asset-cup-pair','id:cnqzTNngPVsAAAAAAA5zqA')
pairv=next(v for v in VIS['cases']['cup']['views'] if pair['id'] in v['equivalent_asset_ids'])
source('cup-historical-deferral',COMP/'reviews/cup-ring-image-gap-2026-10-17/deferred-review.json')
source('cup-pair-cached-metadata',COMP/'reviews/cup-ring-image-gap-2026-10-17/metadata-links.json','/family_listing/entries/19')
source('cup-pair-folder-cached-metadata',COMP/'reviews/cup-ring-image-gap-2026-10-17/metadata-links.json','/family_listing/entries/12')
source('cup-crop-cached-metadata',COMP/'reviews/cup-ring-image-gap-2026-10-17/metadata-links.json','/family_listing/entries/6')
source('cup-crop-folder-cached-metadata',COMP/'reviews/cup-ring-image-gap-2026-10-17/metadata-links.json','/family_listing/entries/5')
entries.append({'component_id':'BC-CR-RING','source_scope':'BC-CR-RING|BASE','proposed_name':'Cup Ring (CRS2) — White standard','family':'Cup Ring and Spiral',
 'closure':'SOURCE_SUPPORTED_INDIVIDUAL_ENQUIRY_PRODUCT_WITH_IMAGE_GAP','identity_state':'SOURCE_LABEL_AND_GEOMETRY_SUPPORTED; NO_NEW_OWNER_NAME_KEEP_CLAIMED',
 'identity_evidence':{'owner_name_kept':False,'source_refs':['cup-code','cup-mould','cup-cast','cup-illustration','cup-individual-trade-2025','asset-cup-pair','asset-cup-crop'],
  'visual_finding':'Maker picture011 shows one complete square ring relief with concentric closed rings and no spiral centre. This geometry matches the complete right panel in native White pair photo007 and the isolated Cup Ring crop. The visible closed ring differs from the separately documented spiral. Identity is established through the labelled geometry and one-cast source row, not through the folder title.'},
 'sale_unit':{'kind':'ONE_INDIVIDUAL_COMPONENT','quantity':1,'pair_mandatory':False,'basis_refs':['cup-cast','cup-description','cup-individual-trade-2025']},
 'count_eligibility':{'identified_source_individual_component':True,'countable_individual_component_units':1,'catalogue_product_record_recommended':True,'owner_name_keep_recorded':False,'physical_stock_quantity':None,'physical_mould_inventory_count':None},
 'primary_example':{'file_id':None,'folder_id':None,'preview_path':next(z['picture']['path'] for z in LABEL if z['row']==27),'shows_complete_single_component':True,
  'selection_reason':'Existing maker-labelled picture011 is the available complete isolated design reference. It is small, dated and has no currently bound individual Dropbox asset. Do not represent it as a newly verified current product photograph.','role':'DATED_MAKER_ILLUSTRATION','basis_refs':['cup-illustration','cup-illustration-image']},
 'alternate_examples':[primary_from_asset(a,False,'Isolated Ring image is a detail crop; outer edges are missing. It supports geometry only and must not be presented as a complete product photo.')],
 'native_reference_links':{'complete_pair_context':cached_browser_links(pair),'isolated_detail_crop':cached_browser_links(a)},
 'maker_label_to_native_proof':{
  'maker_label_locator':'Manufacturing_Labelled_References.json#/10; row27; CRS2-30x30; picture011',
  'individual_unit_locator':'Manufacturing_Sheet_Extract.json#/25/values; row27; one mould/one cast/one30×30cm piece',
  'native_pair_file_id':pair['id'],'native_pair_folder_id':pair['folder_id'],'component_position':'right as pictured',
  'native_image_visual_locator':'visual-review-manifest.json#/cases/cup/views/12; cup-full-01.jpg tile8',
  'visual_correspondence':'Both show a complete square tile with a circular central depression surrounded by a closed raised ring and successive outer circular arcs running into the square corners. The adjacent left panel is a continuous spiral, while CRS2 has no spiral endpoint. The isolated crop repeats the closed centre/rings but omits the outer boundary.',
  'evidence_type':'REVIEWED_LABELLED_GEOMETRY_CORRESPONDENCE; NOT_FILENAME_INFERENCE; NOT_EXACT_PIXEL_IDENTITY',
  'basis_refs':['cup-illustration','cup-illustration-image','cup-cast','asset-cup-pair','asset-cup-crop','cup-pair-cached-metadata','cup-pair-folder-cached-metadata']},
 'context_images':[],'series_images':[{'file_id':pair['id'],'folder_id':pair['folder_id'],'preview_path':pairv['path'],'shows_complete_single_component':False,'component_position':'right as pictured','role':'COMPLETE_RING_VISIBLE_WITH_SPIRAL_CONTEXT','basis_ref':'asset-cup-pair'}],
 'specifications':{
  'dimensions':field('Approximately30 H ×30 W ×5–7 D cm — maker standard; unmeasured',{'height_cm':30,'width_cm':30,'depth_cm_range':[5,7]},'DATED_MAKER_STANDARD',['cup-cast','cup-description','cup-individual-trade-2025',working],'Image crop is not a scale reference; source is design level, not a measured current cast.'),
  'weight':field('Approximately3–5 kg — calculated maker estimate; dated2025 trade row says5.5 kg',{'estimated_kg_range':[3,5],'alternative_dated_claim_kg':5.5},'DATED_CALCULATED_ESTIMATE_ACCEPTED_AS_WORKING',['cup-weight','cup-individual-trade-2025',weight],'Actual cast unweighed; do not silently harmonize3–5 and5.5kg.'),
  'material_finish':field('Jesmonite AC730, White Marble Stone Finish — historical standard',{'material':'Jesmonite AC730','finish':'White Marble Stone Finish'},'DATED_MAKER_STANDARD',['cup-description',working],'Does not determine the material of the Paver Brown finish or every pictured cast.'),
  'fixing':field('Choice of keyhole fixing or French cleat — owner instruction',{'options':['KEYHOLE','FRENCH_CLEAT'],'choose':1,'fitted_hardware':None,'load_rating':None},'OWNER_REQUESTED_CATALOGUE_CHOICE',[fix,'cup-fixing'],'Maker historically describes one small stainless rear fixing; actual installed hardware and capacity unverified.'),
  'individual_price':field('Price on enquiry — one Cup Ring',{'currency':'GBP','amount':None,'price_on_enquiry':True,'quantity':1},'AUTHORIZED_WORKING_COMMERCIAL_POLICY',[instruction,working,'cup-individual-trade-2025'],'2025£112 is a dated individual trade price, not a current retail price. Pair£224 is not divided or imported.'),
  'availability':field('Enquiry / made to order — working policy; stock and lead time unknown',{'enquiry':True,'made_to_order_proposal':True,'stock_quantity':None,'lead_time':None},'AUTHORIZED_WORKING_COMMERCIAL_POLICY',[instruction,working,made],'Manufacture policy does not establish current stock, reproducibility or delivery timing.')},
 'source_conflicts':[{'issue':'Weight','details':'Maker calculated3–5kg each;2025 individually illustrated trade row5.5kg. Both retained.','basis_refs':['cup-weight','cup-individual-trade-2025']},
  {'issue':'Historical crop deferral','details':'Original deferred review remains immutable. Current proposal resolves the single-design/sale-unit question through maker/reference evidence; the missing complete current isolated photo remains open.','basis_refs':['cup-historical-deferral','cup-illustration','asset-cup-crop']}],
 'missing_evidence':['A complete isolated current Ring photograph with all outer edges and stable file/folder identity','Cast-specific measurements/rear-fixing details if verified sales sheet required','Current confirmed retail amount, stock and lead time'],
 'platform_mapping':{'individual_exact_match_confirmed':False,'action':'Source-supported enquiry record only; no platform write'},
 'readiness':{'identity_and_count_source_supported':True,'six_working_fields_prepared':True,'current_complete_individual_dropbox_photo_bound':False,'confirmed_fixed_retail_price':False,'buy_now_publication':False},
 'handoff_notes':['One source-supported Ring product; do not count the surrounding pair again or introduce a Paver Brown product from a crop alone.','No additional owner name or identity event is asserted.','Retain the old deferred-image record and its date; record this as a new source-case conclusion.']})

cand=candidate('candidate-fish','BC-FFL-1')
source('fish-prior-gap',COMP/'reviews/parallel-import-2026-10-19-batch74/frozen-fish-long-evidence.json')
entries.append({'component_id':'BC-FFL-1','source_scope':'BC-FFL-1|BASE','proposed_name':'Frozen Fish Long (FFL1) —100×22 cm White standard','family':'Frozen Fish',
 'closure':'SOURCE_SUPPORTED_INDIVIDUAL_SIZE_OPTION_ENQUIRY_RECORD','identity_state':'DOCUMENTED_INDIVIDUAL_LONG_OPTION; EXACT_CURRENT_IMAGE_UNBOUND',
 'identity_evidence':{'owner_name_kept':False,'source_refs':['fish-long-code','fish-long-mould','fish-long-cast','fish-long-description','fish-long-individual-trade-2025','fish-long-retail-2025'],
  'visual_finding':'The maker illustration shows the complete solo Frozen Fish relief, but the same picture045 is anchored to both the70×15 Size A and100×22 Size B columns. Review of83 cached full family assets does not establish which exact current asset is Long. Complete individual photos, short-series arrangements and close-ups cannot be assigned100×22 from aspect ratio, fin count, filenames or uncalibrated surroundings.'},
 'sale_unit':{'kind':'ONE_INDIVIDUAL_LONG_PANEL','quantity':1,'triptych_mandatory':False,'basis_refs':['fish-long-cast','fish-long-description','fish-long-individual-trade-2025','fish-long-retail-2025']},
 'relationship_to_short_design':{'documented_source_row_association':'Frozen Fish Solo row73 pairs FFS2-70x15 Size A with FFL1-100x22 Size B in the larger-size column',
  'source_associated_short_code':'FFS2-70x15','relationship':'ASSOCIATED_LARGER_SOLO_SIZE_OPTION; NOT_PROVEN_GEOMETRY_ALIAS',
  'same_geometry_confirmed':False,'distinct_geometry_confirmed':False,'same_mould_confirmed':False,'current_exact_FFS2_image_or_product_alias_assigned':False,
  'image_evidence_limit':'Identical picture045 is reused at /shapes/46 and /shapes/147, so the two illustrations cannot independently prove either identical geometry or a new geometry. Larger triptych/diptych rows explicitly repeat FFL1; they are configurations of this option, not3/2 new identities.',
  'basis_refs':['fish-code','fish-long-code','fish-mould','fish-long-mould','fish-shared-source-picture-A','fish-shared-source-picture-B','fish-long-trio-one-mould','fish-long-pair-one-mould']},
 'count_eligibility':{'documented_individual_size_option':True,'countable_source_design_size_records':1,'catalogue_product_record_recommended':True,'new_distinct_geometry_design_count':'NOT_ESTABLISHED','physical_stock_quantity':None,'physical_mould_inventory_count':None,
  'scope_note':'Eligible as a documented one-panel100×22 enquiry option. Do not add a new independently depicted shape or multiply it by the three-piece display. If the final count is of component designs irrespective of size, retain this as a size option without claiming an extra geometry.'},
 'primary_example':{'file_id':None,'folder_id':None,'preview_path':None,'shows_complete_single_component':False,'selection_reason':'No exact size-specific current Long image binding established. Leave the primary image null rather than assign a70cm or ambiguous source photo.'},
 'alternate_examples':[],'context_images':[],'series_images':[{'file_id':None,'folder_id':None,'preview_path':next(z['picture']['path'] for z in LABEL if z['row']==73),'shows_complete_single_component':True,'role':'SHARED_SIZE_A_B_MAKER_DESIGN_ILLUSTRATION_NOT_SIZE_SPECIFIC','basis_refs':['fish-illustration','fish-shared-source-picture-A','fish-shared-source-picture-B']}],
 'specifications':{
  'dimensions':field('Approximately100 H ×22 W ×5–7 D cm — documented Long option; actual cast unmeasured',{'height_cm':100,'width_cm':22,'depth_cm_range':[5,7]},'DATED_MAKER_SIZE_B_STANDARD',['fish-long-cast','fish-long-description','fish-long-individual-trade-2025',working],'No current photograph is certified100×22; keep70×15 Size A separate.'),
  'weight':field('Approximately8–10 kg each — calculated Long estimate;2025 trade/retail rows say10 kg',{'estimated_kg_range':[8,10],'dated_trade_and_retail_kg':10},'DATED_LONG_ESTIMATE_ACCEPTED_AS_WORKING',['fish-long-weight','fish-long-individual-trade-2025','fish-long-retail-2025',weight],'No weighing performed; short Frozen Fish weights and triptych totals are not imported.'),
  'material_finish':field('Jesmonite AC730, White Marble Stone Finish — historical Long standard',{'material':'Jesmonite AC730','finish':'White Marble Stone Finish'},'DATED_MAKER_SIZE_B_STANDARD',['fish-long-description',working],'No transfer of terracotta or verdigris binder/finish claims to Long.'),
  'fixing':field('Choice of keyhole fixing or French cleat — owner instruction',{'options':['KEYHOLE','FRENCH_CLEAT'],'choose':1,'fitted_hardware':None,'load_rating':None},'OWNER_REQUESTED_CATALOGUE_CHOICE',[fix,'fish-fixing'],'Historical shared row describes one small stainless rear fixing; exact actual attachment and load remain unknown.'),
  'individual_price':field('Price on enquiry — one Long panel',{'currency':'GBP','amount':None,'price_on_enquiry':True,'quantity':1},'AUTHORIZED_WORKING_COMMERCIAL_POLICY',[instruction,working,'fish-long-individual-trade-2025','fish-long-retail-2025'],'Dated2025£275 trade and£550 retail are preserved source claims. Neither is asserted current or assigned to short/coloured products.'),
  'availability':field('Enquiry / made to order — working policy; stock and lead time unknown',{'enquiry':True,'made_to_order_proposal':True,'stock_quantity':None,'lead_time':None},'AUTHORIZED_WORKING_COMMERCIAL_POLICY',[instruction,working,made],'Do not repeat a manufacture question. Universal manufacture does not identify the photographed size or establish stock.')},
 'source_conflicts':[{'issue':'Shared illustration is not a scale binding','details':'Picture045 used for both sizes. Existing Short/current file mappings remain separate; no exact native Long file or folder inferred.','basis_refs':['fish-illustration','fish-shared-source-picture','fish-prior-gap']},
  {'issue':'Dated price versions','details':'The frozen component retains older£432.41 retail; later named2025 retail says£550 and trade£275 for100×22. Current amount remains enquiry.','basis_refs':['candidate-fish','fish-long-retail-2025','fish-long-individual-trade-2025']}],
 'missing_evidence':['For a current product photograph: a labelled or measured100×22 cast/shoot record linked to a complete image and stable file/folder ID, or an unequivocally Long-only source illustration','Actual cast measurements, rear attachment and verified load data if required','Current confirmed retail amount, stock and lead time'],
 'platform_mapping':{'individual_exact_match_confirmed':False,'file_id':None,'folder_id':None,'action':'No linkage to short/coloured offers; no platform write'},
 'readiness':{'documented_identity_and_individual_sale_unit':True,'six_working_fields_prepared':True,'exact_current_individual_image_bound':False,'new_geometry_proven':False,'confirmed_fixed_retail_price':False,'buy_now_publication':False},
 'handoff_notes':['Close the sale-unit question as a source-supported individual size-option enquiry record. Keep the exact current photographic identity gap explicit.','The owner all-manufactured statement removes any repeat manufacture question; it does not supply an image ID.','No live search needed to support the bounded enquiry closure. A future image binding must cite independent scale/label evidence.']})

candidate('candidate-dr3','BC-DR-WAVE3')
d=asset('asset-dr3-selected-016','id:cnqzTNngPVsAAAAAAA50IA')
asset('asset-dr1-selected-001','id:cnqzTNngPVsAAAAAAAykwg')
source('dr-owner-image-alias',IN/'user_classifications.json','/component_identity_relationship_decisions/0')
source('dr-owner-image-alias-receipt',COMP/'reviews/dune-ripple-waves-dr3-review-2026-10-18/owner-same-design-decision.json')
ti=next(i for i,x in enumerate(CAN['products']) if x['canonical_key']=='BC-DR-WAVE1|DR1-WHITE')
source('dr-existing-target',IN/'canonical-products.json',f'/products/{ti}')
target=CAN['products'][ti]
six=CAN['source_candidates'][next(i for i,x in enumerate(CAN['source_candidates']) if x['component_id']=='BC-DR-WAVE3')]['source_specifications']['BC-DR-WAVE3|BASE']
display_keys={'Dimensions / depth':'dimensions','Weight':'weight','Material / finish':'material_finish','Fixing':'fixing','Individual price':'individual_price','Availability':'availability'}
specs={}
for row in six:
 key=display_keys[row[3]]
 specs[key]=field(row[4],None,'HISTORICAL_DR3_ASSERTION_NOT_APPLIED_TO_TARGET',['candidate-dr3'],
  'This is a preserved source-only assertion. It is not a new DR1 specification acceptance, a second product or a certified physical fact.',accept=False)
entries.append({'component_id':'BC-DR-WAVE3','source_scope':'BC-DR-WAVE3|BASE','proposed_name':'Historical Dune Ripple3 (DR3) source-code reference','family':'Dune Ripple',
 'closure':'SOURCE_ILLUSTRATION_REFERENCE_TO_EXISTING_PRODUCT; HISTORICAL_CODE_CONFLICT_RETAINED','identity_state':'SELECTED_IMAGE_ALIAS_RESOLVED; WHOLE_MOULD_CODE_EQUIVALENCE_UNRESOLVED',
 'identity_evidence':{'owner_name_kept_for_new_dr3_product':False,'source_refs':['dr3-illustration','dr3-illustration-image','asset-dr3-selected-016','dr-owner-image-alias','dr-owner-image-alias-receipt','dr-existing-target'],
  'visual_finding':'Maker row56 labelled picture043 and native selected016 show the same photographed relief view: the outer contour, wide channels, individual surface marks and wood-background lines correspond. The owner already confirmed016 and001 as one depicted design retained under DR1-WHITE. This visual source correspondence is a new evidence assessment, not an invented owner code-equivalence decision.',
  'counterevidence_retained':'Maker row51 explicitly says three different moulds DR1/DR2/DR3. Row54 picture041 has different narrow-channel geometry from row56 picture043. The historical allocation of codes to all current designs remains unresolved.'},
 'sale_unit':{'kind':'NO_NEW_SEPARATE_SALE_UNIT_FROM_SELECTED_IMAGE','historical_source_cast_quantity':1,'basis_refs':['dr3-cast','dr-owner-image-alias']},
 'count_eligibility':{'additional_product_from_selected_image':False,'new_product_record_recommendation':False,'countable_additional_units':0,'physical_stock_quantity':None,'whole_historical_source_component_alias_asserted':False},
 'target_reference':{'canonical_key':target['canonical_key'],'product_id':target['product_id'],'relationship':'IMAGE_REFERENCE_ALIAS / DATED_SOURCE_ILLUSTRATION_CORRESPONDENCE','source_image_scope_only':True,'all_source_claims_not_inherited':True},
 'primary_example':primary_from_asset(d,True,'Already owner-aliased selected016. Retain as an additional complete image reference on the existing DR1-WHITE product, not as the primary of a new DR3 product.'),
 'alternate_examples':[{'file_id':None,'folder_id':None,'preview_path':next(z['picture']['path'] for z in LABEL if z['row']==56),'shows_complete_single_component':True,'role':'DATED_MAKER_DR3_LABELLED_ILLUSTRATION','basis_refs':['dr3-illustration','dr3-illustration-image']}],
 'context_images':[],'series_images':[],'specifications':specs,
 'source_conflicts':[{'issue':'Historical mould list versus owner current-image alias','details':'Source mould codes remain separate assertions; selected016 is already the same depicted design as001. Do not create a second product, silently rename existing DR1 toDR3 or declare historical DR1/DR3 same mould.','basis_refs':['dr-trio-mould','dr1-illustration','dr3-illustration','dr-owner-image-alias']},
  {'issue':'DR3 is not DDR3','details':'No DDR1/DDR3 orientation statement is applied to Dune Ripple DR3.','basis_refs':['dr3-code','dr-trio-mould']}],
 'missing_evidence':['A verified crosswalk of maker picture041/043 and their different historical mould codes to current retained identities, if a complete historical mould inventory is required','A distinct uncounted complete design with evidence independent of already-aliased016 before any extra product is added'],
 'platform_mapping':{'inherits_target_platform_match':False,'action':'Retain source/reference relation only; do not copy unapproved historical DR3 fields into existing DR1'},
 'readiness':{'image_alias_closed':True,'extra_current_product_supported':False,'whole_code_allocation_closed':False,'six_source_only_assertions_retained':6,'buy_now_publication':False},
 'handoff_notes':['Keep BC-DR-WAVE3|DR3-WHITE selected-image alias to existing DR1-WHITE.','BASE is a historical source-code conflict/reference, not another countable current product solely from the labelled illustration.','All six source assertions remain quarantined; no transfer to DR1, no blanket same-mould conclusion, and no adjustment of accepted DR1 values.']})

observations={
 'bone':'All30 cached full assets reviewed via three full contact sheets. Two complete owner-kept component references match the maker two-part geometry; numerous rotated and repeated/arranged views add no units. Supplied individual camera/render origin unconfirmed.',
 'cup':'All16 cached full assets reviewed via two full contact sheets, plus maker picture011. Complete Ring visible in paired views; isolated Ring current image is a crop. No invented isolated photograph.',
 'dr':'All39 cached full assets reviewed via four full contact sheets, plus source pictures041/042/043/triptych020 and selected001 thumbnail. Selected016 matches row56 source pictured view and remains owner-aliased toDR1. Two historical geometries and code-allocation conflict retained.',
 'fish':'All83 cached full assets reviewed via seven full contact sheets, plus maker picture045 and relevant trio/diptych illustrations. No size-specific native Long binding established. No dimensions inferred from aspect, fin count, can, wall blocks or camera perspective.'}
for k,z in VIS['cases'].items():
 z['review_state']='ALL_CACHED_FULL_IMAGES_VISUALLY_REVIEWED'
 z['reviewed_full_sheets']=sorted({v['full_contact_sheet'] for v in z['views'] if v['cache_kind']=='FULL'})
 z['observation']=observations[k]
 z['thumbnail_only_asset_reviews_claimed_for_this_turn']=False
VIS['maker_review_state']='TARGET_MAKER_CONTACT_SHEET_REVIEWED; picture043 also individually enlarged'
VIS['review_method']='Human-visible tools.view_image on contact sheets built from cached full bytes; saved native metadata hashes checked locally. No new live checks and no image generation.'
(OUT/'visual-review-manifest.json').write_text(json.dumps(VIS,indent=2)+'\n')

result={'schema':'boldstone.isolated-source-case-closure-proposals.v1','worker_number':1,
 'created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'final_register_writer':'01a144ab-1a7c-7223-a403-73a4d53d70ff',
 'scope':'Five individual source cases only: Bone1/Bone2/FFL1/CRS2/historicalDR3. WallCircle excluded and owned by B. Pricing four-case lane separate.',
 'authority_and_boundaries':{'current_owner_instruction_ref':instruction,'standing_working_policy_ref':working,'manufacture_ref':made,'fixing_ref':fix,'approximate_weight_ref':weight,
  'new_owner_name_events_claimed':0,'new_owner_identity_relationship_events_claimed':0,'repeat_keep_requests_required':False,'physical_verification_performed':False,
  'shared_writes':0,'remote_reads':0,'remote_writes':0,'publication_performed':False,'workbook_created':False,'historical_sources_modified':False},
 'counting_recommendations':{'bone_owner_kept_individual_components':2,'cup_ring_source_supported_individual_component':1,'frozen_fish_documented_individual_size_option':1,'new_historical_dr3_product_from_016':0,
  'proposed_enquiry_product_records':4,'new_distinct_ffl_geometry_established':False,'physical_stock_count':None,
  'limit':'These are local record recommendations, not a global catalogue total. Size-option records and unique component geometry counts must be reported separately.'},
 'entries':entries,'source_refs':REFS,'visual_review_manifest':str(OUT/'visual-review-manifest.json'),
 'native_read_request':{'required_for_proposed_sale_unit_closures':False,'requested_queries':[],
  'remaining_specific_image_gap':'FFL100×22 currently has no known exact image ID; CRS2 needs a complete isolated current photo. A labelled/measured shoot-to-stable-ID record would close those gaps; do not invent IDs.'},
 'arrangement_deferral_preserved':True,
 'handoff_notes':['Main writer may adopt the four enquiry-record proposals without treating absent current prices as an identity/count exclusion.','Current exact photo gaps, source conflicts, installed hardware and stock remain explicit.','Do not split deferred groups, count context arrangements or imply universal manufacture verifies every pictured object.','This worker performed no live reads; fake-adapter gate is a parent responsibility before any subsequent live API use.']}
(OUT/'closure-proposals.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')

# Bounded validation: source references and exact scope, not implementation-mirroring tests.
issues=[]
assert len(entries)==5
assert {e['component_id'] for e in entries}=={'BC-BONE-1','BC-BONE-2','BC-FFL-1','BC-CR-RING','BC-DR-WAVE3'}
for e in entries:
 if set(e['specifications'])!={'dimensions','weight','material_finish','fixing','individual_price','availability'}:issues.append(e['component_id']+' six keys')
 for v in e['specifications'].values():
  for q in v['basis_refs']:
   if q not in REFS:issues.append('unknown ref '+q)
 if e['primary_example'].get('file_id') and not e['primary_example'].get('matches_saved_native_bytes_and_hash'):issues.append('primary native mismatch '+e['component_id'])
source_input_manifest=json.load(open(TASK/'input-manifest.json'))
hash_checks=[]
for x in source_input_manifest['inputs']:
 p=Path(x['snapshot']);actual=hashlib.sha256(p.read_bytes()).hexdigest()
 hash_checks.append({'path':str(p),'expected':x['sha256'],'actual':actual,'pass':actual==x['sha256']})
 if actual!=x['sha256']:issues.append('input drift '+str(p))
stats={k:{q:z[q] for q in ['asset_count','cached_full_asset_count','saved_native_bytes_match_count','distinct_cached_image_count']} for k,z in VIS['cases'].items()}
validation={'status':'PASS' if not issues else 'FAIL','issues':issues,'entries':5,'six_field_groups':30,'source_refs':len(REFS),'source_hash_checks':hash_checks,
 'cached_image_stats':stats,'cached_full_assets_visually_reviewed':sum(z['cached_full_asset_count'] for z in VIS['cases'].values()),
 'saved_native_byte_matches':sum(z['saved_native_bytes_match_count'] for z in VIS['cases'].values()),'shared_writes':0,'remote_reads':0,'remote_writes':0,'wall_circle_excluded':True,
 'sources_unchanged_on_this_local_read':True,'output_sha256':hashlib.sha256((OUT/'closure-proposals.json').read_bytes()).hexdigest()}
(OUT/'validation.json').write_text(json.dumps(validation,indent=2)+'\n')
print(json.dumps({'status':validation['status'],'entries':len(entries),'source_refs':len(REFS),'cached_full_reviewed':validation['cached_full_assets_visually_reviewed'],'native_matches':validation['saved_native_byte_matches'],'output':str(OUT/'closure-proposals.json')},indent=2))
