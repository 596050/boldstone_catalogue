from pathlib import Path
from collections import Counter, defaultdict
from datetime import datetime,timezone
import json,re,hashlib
W=Path(__file__).resolve().parent
R=json.load(open(W/'register.snapshot.json'));F=json.load(open(W/'refresh.snapshot.json'));P=json.load(open(W/'progress.snapshot.json'));U=json.load(open(W/'classifications.snapshot.json'))
REV={r[0]+'|'+r[1]:r for r in F['reviews']}
SP=defaultdict(dict)
for r in F['specifications']:SP[r[0]+'|'+r[1]][r[3]]=r
COMP={c['component_id']:c for c in R['components']}
GROUPS={g['group_ref']:g for g in R['groups']}; GF={g['id']:g for g in R['groups']}
ASSETS={a['id']:a for a in R['assets']};ASSETS.update({a['id']:a for a in F['asset_updates']})
UP={o['offer_ref']:o for o in F['platform_updates']}
OFFERS={o['offer_ref']:UP.get(o['offer_ref'],o) for o in R['platform_records']}
BOM=defaultdict(list)
for b in R['bom']:BOM[b['offer_ref']].append(b)

def split(s):return [x.strip() for x in (s or '').splitlines() if x.strip()]
def uniq(xs):return list(dict.fromkeys(xs))
def canon(cid):
 if cid in P['canonical_component_consolidations']:return P['canonical_component_consolidations'][cid]['canonical_component_id']
 if cid in P['current_catalogue_overlays']['Moonphases']['source_component_to_current_design']:return P['current_catalogue_overlays']['Moonphases']['source_component_to_current_design'][cid]
 for d in U['component_identity_relationship_decisions']:
  if d.get('component_id')==cid and d.get('canonical_component_id') and d['canonical_component_id']!=cid:return d['canonical_component_id']
 return cid

def scope_ref(k):
 r=REV[k]
 return {'key':k,'component_id':r[0],'scope_id':r[1],'display_name':r[2],'review_kind':r[3],'name_state':r[4],'specification_state':r[5],'primary_file_id':r[9],'primary_folder_id':r[10],'dimensions':SP[k].get('Dimensions / depth',['']*5)[4],'material_finish':SP[k].get('Material / finish',['']*5)[4],'notes':r[11]}

def finish(s):
 s=s.lower().replace('grey','gray')
 if any(t in s for t in ['unspecified','mixed','assorted']):return 'unknown'
 words=set(re.findall(r'white|black|blue|green|gold|bronze|copper|verdigris|rust|silver|pewter|terracotta|sandstone|beige|brown',s))
 return '+'.join(sorted(words)) or 'unknown'

def candidates_for_cid(cid):
 cc=canon(cid); out=[k for k,r in REV.items() if r[0] in {cid,cc}]
 if cid=='BC-AM-1':out +=['AM-S1|BASE','AM-L1|BASE']
 if cid=='BC-AM-2':out +=['AM-S2|BASE','AM-L2|BASE']
 if cid=='BC-DR-WAVE3':out+=['BC-DR-WAVE1|DR1-WHITE']
 return uniq(k for k in out if k in REV)

# Reviewed source-to-current-scope links. These carry only their stated source evidence; this audit upgrades no exact platform match.
M={
1:['BC-WALL-CIRCLE|BASE'],2:['BC-DR-SPIRAL|DR-SPIRAL-GOLD'],3:['BC-MCP-4|MCP4-SILVER-BRONZE-25'],4:['BC-DR-WAVE1|DR-WAVES-VERDIGRIS'],5:['BC-MCP-3|MCP3-VERDIGRIS-RUST'],6:['BC-MCP-4|MCP4-VERDIGRIS-25','BC-MCP-4|MCP4-VERDIGRIS-RUST'],7:['BC-MCP-1|MCP1-VERDIGRIS-RUST'],8:['BC-MCP-2|MCP2-VERDIGRIS-RUST'],9:['BC-DR-SPIRAL|DR-SPIRAL-VERDIGRIS'],
10:['MOONPHASE-CURRENT-1|MOONPHASE-CURRENT-1:WHITE','MOONPHASE-CURRENT-2|MOONPHASE-CURRENT-2:WHITE','MOONPHASE-CURRENT-3|MOONPHASE-CURRENT-3:WHITE'],11:['BC-MCP-4|MCP4-VERDIGRIS-25'],12:['BC-SEAWEED-SMOOTH|BASE'],13:['BC-DDR-WAVE|DDR-WAVE-WHITE','BC-DDR-SPIRAL|DDR-SPIRAL-WHITE'],14:['BC-FOUNTAIN-EG|FOUNTAIN-EG-WHITE'],15:['BC-MCP-4|MCP4-WHITE','BC-MOON-WATER|MOONWATER-WHITE'],16:['BC-MOONWAVE|MOONWAVE-WHITE'],17:['BC-RW-WAVE|RAKED-SPIRAL2-WHITE','BC-RW-SPIRAL3|RAKED-SPIRAL3-WHITE','BC-RW-SPIRAL1|RAKED-SPIRAL1-WHITE'],18:['AM-L1|BASE','AM-L2|BASE'],19:['BC-ECHO-1|ECHO-1-WHITE','BC-ECHO-2|ECHO-2-WHITE'],20:['BC-DP-LEAVES|BASE','BC-DP-SPIRAL|DP-SPIRAL-WHITE-45x40'],21:['BC-MSW-MOON|MSW-HALF-MOON-WHITE'],22:['BC-FOLD-2|FOLD-2-WHITE'],23:['BC-FOLD-3|FOLD-3-WHITE'],24:['BC-FDW-1|FDW-1-WHITE','BC-FDW-2|FDW-2-WHITE'],25:['BC-FDW-1|FDW-1-WHITE','BC-FDW-2|FDW-2-WHITE'],26:['BC-SEAWEED-ROUGH|BASE'],27:['BC-DP-PALM1|BASE','BC-DP-PALM2|BASE','BC-DP-SPIRAL|DP-SPIRAL-WHITE-45x40'],28:['BC-LEAF-FORM|LEAF-FORM-LF1-WHITE','BC-LEAF-FORM|LEAF-FORM-LF2-WHITE'],29:['BC-BR-1|BASE','BC-BR-2|BASE'],30:['MOONPHASE-CURRENT-1|MOONPHASE-CURRENT-1:WHITE','MOONPHASE-CURRENT-2|MOONPHASE-CURRENT-2:WHITE','MOONPHASE-CURRENT-3|MOONPHASE-CURRENT-3:WHITE','MOONPHASE-CURRENT-4|MOONPHASE-CURRENT-4:WHITE'],31:['MOONPHASE-CURRENT-1|MOONPHASE-CURRENT-1:WHITE','MOONPHASE-CURRENT-2|MOONPHASE-CURRENT-2:WHITE','MOONPHASE-CURRENT-3|MOONPHASE-CURRENT-3:WHITE'],32:['BC-MSW-MOON|MSW-HALF-MOON-WHITE','BC-MSW-SPIRAL|MSW-SHELLWAVE-WHITE'],33:['BC-MSW-MOON|MSW-HALF-MOON-WHITE','BC-MSW-SPIRAL|MSW-SHELLWAVE-WHITE'],34:['BC-BONE-1|BASE','BC-BONE-2|BASE'],35:['BC-SF-1|SF1-WHITE','BC-SF-2|WT2-WHITE'],36:['BC-SM-SPIRAL|SM1-WHITE'],37:['BC-LEAF-GROWTH|LEAF-GROWTH-WHITE'],38:['BC-DR-WAVE1|DR-WAVES-VERDIGRIS'],39:['BC-DR-SPIRAL|DR-SPIRAL-GOLD'],40:['BC-MS-2|MS2-WHITE'],41:['BC-EG-1|EG-1-WHITE','BC-EG-2|EG-2-WHITE'],42:['BC-EG-1|EG-1-GOLD-LEAF'],43:['BC-MFW-1|MFW-LEFT-WHITE','BC-MFW-2|MFW-RIGHT-WHITE'],44:['BC-WBMS-MOON|WBMS1-WHITE','BC-WBMS-WAVE|WBMS2-WHITE'],45:['BC-FOLD-1|FOLD-1-WHITE'],46:['BC-DP-SPIRAL|DP-SPIRAL-GOLD-45x40'],47:['BC-DP-SPIRAL|DP-SPIRAL-WHITE-45x40'],48:['AM-S1|BASE','AM-S2|BASE'],49:['BC-FFS-2|FFS2-TERRACOTTA'],50:['BC-DECO-1|DECO-1-TERRACOTTA'],51:['BC-DR-WAVE1|DR-WAVES-RUST'],52:['BC-DR-SPIRAL|DR-SPIRAL-COPPER'],53:['BC-DP-PALM2|BASE'],54:['BC-DP-PALM1|BASE'],55:['BC-DP-PALM1|BASE','BC-DP-PALM2|BASE','BC-DP-SPIRAL|DP-SPIRAL-WHITE-45x40'],56:['BC-DP-PALM1|BASE','BC-DP-SPIRAL|DP-SPIRAL-WHITE-45x40'],57:['BC-ECHO-1|ECHO-1-WHITE','BC-ECHO-2|ECHO-2-WHITE'],58:['BC-LEAF-FORM|LEAF-FORM-LF1-WHITE'],59:['BC-MOON-WATER|MOONWATER-WHITE'],60:['BC-DECO-1|DECO-1-VERDIGRIS','BC-DECO-2|DECO-2-VERDIGRIS'],61:['BC-ICARUS|BASE'],62:['BC-STRATA|ST1-VERDIGRIS'],63:['BC-FFS-2|FFS2-VERDIGRIS'],64:['BC-MCP-4|MCP4-SILVER-BRONZE-25'],65:['MOONPHASE-CURRENT-1|MOONPHASE-CURRENT-1:WHITE'],66:['BC-RUST-PANEL|BASE'],67:['BC-DR-WAVE1|DR-WAVES-RUST'],68:['BC-DR-SPIRAL|DR-SPIRAL-RUST'],69:['BC-AC-TWO|AC-TWO-BRONZE'],70:['MOONPHASE-CURRENT-4|MOONPHASE-CURRENT-4:SILVER'],71:['BC-AC-FULL|AC-FULL-GOLD-LEAF'],72:['BC-ECHO-1|ECHO-1-VERDIGRIS','BC-ECHO-2|ECHO-2-VERDIGRIS'],73:['BC-AZURE|AZURE-BLUE-WHITE'],74:['MOONPHASE-CURRENT-2|MOONPHASE-CURRENT-2:WHITE'],75:['MOONPHASE-CURRENT-3|MOONPHASE-CURRENT-3:WHITE'],76:['BC-AC-FULL|BASE'],77:['BC-AC-FLOWER|BASE'],78:['BC-BAR-WAVE|BASE'],79:['BC-BONE-WATER|BASE'],80:['BC-BR-TOTEM|BASE']}
M={f'O{k:03d}':v for k,v in M.items()};M['SH-DRAFT']=['BC-FFS-1|FFS1-WHITE','BC-FFS-2|FFS2-WHITE','BC-FFS-3|FFS3-WHITE']
assert set(M)==set(OFFERS)
assert all(k in REV for keys in M.values() for k in keys)
NOTES={
'O001':['Wall Circle is a family/pattern/lighting source offer with custom pattern/size options. Current278 table has only pending BASE, not resolved individual pattern/build/size sale units. Preserve source-only candidates; do not count one family header as every pattern.'],
'O006':['Exact source photograph is unresolved. Title copper/verdigris does not choose between the current Verdigris and Verdigris/Rust finish scopes. Design-level/source candidate only.'],
'O007':['Exact source photograph is unresolved; do not certify the proposed MCP1 geometry or apply the Verdigris/Rust working scope to this offer without evidence.'],
'O008':['Current photo binding explicitly assigns the image to MCP2-VERDIGRIS-RUST despite the native Blue title. It does not reverify the account SKU or prove the same physical cast.'],
'O010':['Native sale text says each while gallery proposes three phases. Sale quantity remains unresolved; keep gallery membership separate from a certified set offer.'],
'O015':['Title/SKU and50×50 claim indicate Concave Moon; confirmed hero photo depicts Moon Water Catcher. Intended BOM is provisional. Owner MCP4 consolidation does not transfer this50×50 source claim or resolve the photograph/title conflict.'],
'O018':['Large Ammonite pair: use current AM-L1/AM-L2 scopes, not source BC-AM base labels or Small variants.'],
'O020':['Two Leaves plus Spiral source pair claims30×30×6 each. Deco Two Leaves current BASE retains30×30; Timeless Spiral current White scope is45×40×5. A30cm White Spiral source-size candidate is not separately reviewed; actual production-version identity remains unresolved. Do not create a new canonical size solely from the source claim.'],
'O021':['Two casts/arrangement positions use the same Half Moon design rotated; no second individual design from repeat position.'],
'O025':['Three casts include FDW1 rotated as FDW3; two underlying design scopes, not three independent products.'],
'O027':['Source45×40 dimensions and current Palm40×45 wording may be axis/orientation order; retain dimensions per member rather than add a new size without evidence.'],
'O028':['LF1/LF2 are documented opposite orientations of one mould. Two current layout scopes may be sale/hanging options, not two source moulds.'],
'O030':['Five photographed pieces map to four current public designs; both plain-moon source positions use current Moonphase Four. Preserve five-piece set quantity without creating a fifth current public design.'],
'O032':['Triptych title/source supports three members; a four-panel alternative in gallery is context. Repeated Half Moon orientations are not additional designs.'],
'O034':['Bone Spiral narrow/wide each have only pending BASE records in latest278 review. Preserve both separately as source-supported individual-product candidates with gaps; pair price/weight must not be divided into sourced values.'],
'O038':['Plain-wave photograph is supported; exact historical DR1 versus DR3 mould allocation remains provisional. Owner same-design decision applies reviewed references, not a manufactured-mould census.'],
'O039':['35×20×5 source Gold Dune Ripple versus current approximately35×21×6 working scope is a size/depth applicability issue; source claims are retained, not proof of another physical product.'],
'O040':['Hero sale unit is one Moonspiral Two; alternate two-panel gallery works are not sold under this single offer.'],
'O042':['Historical native description says SOLD and offers similar work by enquiry. Platform InStock/Unlimited is not a physical stock audit.'],
'O045':['Design is source-confirmed but exact hero file was not located; no exact source-file match is created by this audit.'],
'O046':['Native/SKU30×30×5 Golden Spiral source claim differs from owner-confirmed current45×40×5 Gold scope. Owner says same dimensions as Timeless Spiral. Keep old30cm offer as unresolved source-version data; do not count an additional30cm product as owner accepted.'],
'O048':['Small Ammonite pair: use AM-S1/AM-S2 scopes, not Large variants.52×25 source version and owner working52×26 or related draft measurements remain scoped source assertions.'],
'O049':['Strong terracotta design candidate; shared reverse image with another design is not exact-specimen proof.'],
'O053':['Native Palm Form One maps to historical BC-DP-PALM2/current Palm Form One — White; preserve current naming crosswalk.'],
'O054':['Native Palm Form Two maps to historical BC-DP-PALM1/current Palm Form Two — White; preserve current naming crosswalk.'],
'O055':['Three-part arrangement; source40×45×6 each is not an additional single product. Spiral current45×40×5 differs in orientation/depth claims; retain source-version limits.'],
'O056':['Two-part arrangement; source40×45×6 each is not a whole-size allocation or a separate Spiral product identity.'],
'O057':['White pair photograph; source text and SKU do not establish clear pair sale quantity. Individual Echo1/2 White scopes exist; sale unit unresolved.'],
'O058':['Source single claims40×20×6, while current LF1 White scope35×35 retains that conflict. No separately reviewed40×20 size. Exact image link alone does not prove the rectangular version exists as another canonical product.'],
'O059':['Source50cm diameter×8 and gypsum wording differs from rectangular maker/current working51×48, side5–7cm. Copy/version applicability is unresolved; no second physical size inferred.'],
'O060':['Title Two Frozen Decowaves points to coloured Decowaves1+2 Verdigris source; do not merge with White Frozen Decowave1/2 solely by title.'],
'O064':['Former Concave Silver/Bronze and current MCP4 Silver/Bronze are one owner-consolidated finish reference. Two source offers/photographs are not two products.'],
'O070':['Current Moonphase Four Silver is present. Historical MP1/MP5 maker orientation is unresolved, but owner public design Four naming is established; do not reopen obsolete five-design public numbering.'],
'O072':['Pair description and combined weight, but principal selected fronts show one member. Individual Echo1/2 Verdigris scopes exist; exact pair completeness remains an evidence gap. Never copy8kg combined to each.'],
'O073':['One Azure panel is sale unit. Different panel in paired room scene remains background/unallocated; do not count it as sold or matched.'],
'O079':['Source55×55×7 claim differs from owner-kept80wide×60high working version; no distinct reviewed55cm product. Retain source-only size candidate pending intended-offer/version reconciliation.'],
'SH-DRAFT':['Historical blank-SKU/description triptych image with zero/unfilled price/weight. Three individual White scopes exist, but no current single/set listing or stock is inferred.']}
flags_by_offer={
'O001':['SOURCE_ONLY_FAMILY_CATALOGUE_NO_INDIVIDUAL_VARIANT_SCOPE'],
'O006':['EXACT_IMAGE_AND_FINISH_UNRESOLVED'], 'O007':['EXACT_IMAGE_AND_FINISH_UNRESOLVED'],
'O008':['TITLE_FINISH_DIFFERS_FROM_REVIEWED_PHOTO'], 'O010':['SALE_QUANTITY_UNRESOLVED'],
'O015':['TITLE_PHOTO_IDENTITY_CONFLICT','SOURCE_SIZE_NOT_CANONICAL_VARIANT_PROOF'],
'O020':['SOURCE_SIZE_NOT_SEPARATELY_SCOPED'], 'O034':['INDIVIDUAL_MEMBERS_PENDING_BASE_ONLY'],
'O038':['HISTORICAL_MEMBER_IDENTITY_UNRESOLVED'], 'O039':['SOURCE_SIZE_DEPTH_VERSION_CONFLICT'],
'O042':['HISTORICAL_SOLD_STATEMENT'], 'O045':['EXACT_IMAGE_UNRESOLVED'],
'O046':['OWNER_CURRENT_SIZE_DIFFERS_FROM_NATIVE_SOURCE','NO_ADDITIONAL_OWNER_ACCEPTED_30CM_PRODUCT'],
'O049':['EXACT_SPECIMEN_UNRESOLVED'], 'O055':['SOURCE_DIMENSION_ORDER_DEPTH_DIFFERENCE'],
'O056':['SOURCE_DIMENSION_ORDER_DEPTH_DIFFERENCE'], 'O057':['SALE_QUANTITY_UNRESOLVED'],
'O058':['SOURCE_SIZE_NOT_SEPARATELY_SCOPED'], 'O059':['SOURCE_FORM_SIZE_MATERIAL_VERSION_CONFLICT'],
'O060':['TITLE_FAMILY_DIFFERS_FROM_PHOTO'], 'O070':['HISTORICAL_MAKER_ORIENTATION_UNRESOLVED'],
'O072':['PAIR_COMPLETENESS_UNRESOLVED'], 'O073':['SECOND_SCENE_PANEL_UNALLOCATED_NOT_SALE_UNIT'],
'O079':['SOURCE_SIZE_NOT_SEPARATELY_SCOPED'],'SH-DRAFT':['HISTORICAL_DRAFT_NOT_CURRENT_OFFER']}
OF=[]
for ref,o in OFFERS.items():
 keys=M[ref];b=BOM[ref];flags=flags_by_offer.get(ref,[]).copy();kind=o['sale_unit_state']
 if ref=='SH-DRAFT':state='HISTORICAL_DRAFT_MEMBER_SCOPES_PRESENT'
 elif ref=='O001':state='SOURCE_ONLY_FAMILY_OR_PRODUCT_CANDIDATE'
 elif ref in ['O006','O007','O015']:state='CANDIDATE_SCOPES_PRESENT_EXACT_IDENTITY_OR_FINISH_UNRESOLVED'
 elif kind=='Gallery proposal; sale quantity unresolved':state='MEMBER_SCOPES_PRESENT_SALE_UNIT_UNRESOLVED'
 elif kind=='Sale arrangement components':state='SET_OFFER_MEMBER_SCOPES_PRESENT'
 elif ref in ['O046','O058','O059','O079']:state='CURRENT_SCOPE_PRESENT_NATIVE_VERSION_UNRESOLVED'
 else:state='CURRENT_REVIEW_SCOPE_PRESENT_SOURCE_MATCH_LIMITS_RETAINED'
 sameimage=[x for x,y in OFFERS.items() if x!=ref and y.get('image_file_id') and y.get('image_file_id')==o.get('image_file_id')]
 samekeys=[x for x,k in M.items() if x!=ref and set(k)==set(keys)]
 g=GF.get(o.get('image_folder_id',''))
 OF.append({'offer_ref':ref,'platform':o.get('platform'),'source_title':o['title'],'source_sku':o.get('sku'),'squarespace_id':o.get('sq_id'),'shopify_handle':o.get('sh_handle'),'source_url':o.get('source_url'),'source_sale_scope':kind,'native_parts':o.get('native_parts'),'source_each_cm':o.get('source_each_cm'),'source_overall_cm':o.get('source_overall_cm'),'source_set_weight_kg':o.get('source_set_weight_kg'),'source_image_file_id':o.get('image_file_id'),'source_image_folder_id':o.get('image_folder_id'),'baseline_source_group':g['group_ref'] if g else None,'baseline_group_name':g['name'] if g else None,'recorded_mapping_state':o.get('image_state'),'source_cautions':o.get('cautions'),'bom_rows':b,'candidate_current_review_scope_keys':keys,'candidate_scope_details':[scope_ref(k) for k in keys],'coverage_state':state,'flags':flags,'same_source_image_offers':sameimage,'same_current_scope_offer_candidates':samekeys,'audit_notes':NOTES.get(ref,[]),'exact_match_upgraded_by_this_audit':False,'source_offer_is_not_additional_canonical_product':True,'source_unit_limits':'Preserve source offer as evidence. Set price, whole mass and total dimensions do not become individual facts by division. Multiple offers mapped to one reviewed design/finish do not create multiple products.','current_live_account_stock_or_specimen_verified':False})

# Every baseline configuration is mapped independently; unknown/mixed appearances are retained as candidates, never made into extra variants automatically.
CF=[]
for c in R['configurations']:
 cid=c['component_id'];cc=canon(cid);keys=candidates_for_cid(cid);files=set(split(c['example_file_ids']));solo=set(split(c['solo_folder_ids']));allfolders=set(split(c['all_folder_ids']));tok=finish(c['finish_appearance'])
 direct=[k for k in keys if REV[k][9] and REV[k][9] in files]
 folders=[k for k in keys if REV[k][10] and REV[k][10] in solo]
 named=[]
 for k in keys:
  rr=REV[k];t=finish(rr[2]+' '+rr[1]);ft=set(tok.split('+'));tt=set(t.split('+'))
  if rr[1]!='BASE' and tok!='unknown' and (tok==t or ft=={'gold'} and 'gold' in tt or ft=={'white','gold'} and tt=={'gold'}):named.append(k)
 base=[k for k in keys if REV[k][1]=='BASE']
 picked=uniq(direct+folders+named)
 alias=False;notes=[];flags=[]
 if cid.startswith('BC-MP-'):
  picked=[k for k in picked if k.startswith(cc+'|')]
  notes.append('Historical maker/source numbering mapped to current owner four-design catalogue aliases; physical mould/cast lineage not merged.')
 if cid=='BC-CONCAVE':
  vid={'Silver appearance':'MCP4-SILVER-BRONZE-25','Verdigris':'MCP4-VERDIGRIS-25','White':'MCP4-WHITE'}.get(c['finish_appearance'])
  if vid:picked=['BC-MCP-4|'+vid]
  alias=True;notes.append('Former Concave reference is canonical MCP4. Finish-equivalence and original scoped approvals retained; no extra Concave product.')
 if cid=='BC-MCP-4' and c['finish_appearance'] in ['Silver appearance','Verdigris']:
  picked=['BC-MCP-4|'+({'Silver appearance':'MCP4-SILVER-BRONZE-25','Verdigris':'MCP4-VERDIGRIS-25'}[c['finish_appearance']])]
  notes.append('Owner-confirmed MCP4 finish-equivalence crosswalk resolves Silver versus Silver/Bronze and Verdigris reference groups.')
 if cid in ['BC-MLAVA-WALL-1','BC-MLAVA-WALL-2']:
  picked=[cc+'|'+('MLAVA-1-WHITE' if cc=='BC-MLAVA-1' else 'MLAVA-2-WHITE')];alias=True
  notes.append('Owner identified wall pair as standalone Moonshell Lava1+2; historical wall-position IDs are references, not extra products.')
 if cid.startswith('BC-LUCIANO-'):
  picked=[k for k in keys if k.startswith(cc+'|')];alias=True
  notes.append('Owner identifies Luciano as Lava Moon design. These cropped/detail references do not identify a unique finish or confer whole-screen dimensions on a single panel.')
 if cid=='BC-DR-WAVE3':
  picked=['BC-DR-WAVE1|DR1-WHITE'];alias=True
  notes.append('Owner says the reviewed DR3-labelled photograph and prior DR1 reference are the same depicted design. Preserve historical source row lineage; no global physical-mould claim.')
 if cid in ['BC-AM-1','BC-AM-2']:
  picked=['AM-S'+('1' if cid.endswith('1') else '2')+'|BASE','AM-L'+('1' if cid.endswith('1') else '2')+'|BASE']
  notes.append('Baseline White configuration spans Small and Large sources; current size-specific Ammonite individual scopes exist. Do not collapse sizes or set offers.')
 if cid in ['BC-CR-RING','BC-CR-SPIRAL'] and c['finish_appearance']=='Brown paver':
  picked=[];flags.append('BROWN_PAVER_CONTEXT_NOT_A_REVIEWED_FINISH');notes.append('Brown-paver group is arrangement/context evidence; no isolated individual or accepted Brown finish scope established.')
 # Sole BASE can be a legitimate existing White/product working scope, or a pending source-only candidate.
 if not picked and base and len(keys)==len(base):picked=base
 namedpicked=[k for k in picked if REV[k][1]!='BASE']
 baseworking=[k for k in picked if REV[k][1]=='BASE' and ('Owner kept' in REV[k][4] or 'working' in REV[k][5].lower())]
 if alias:status='ALIAS_OR_POSITION_REFERENCE_NOT_AN_ADDITIONAL_PRODUCT'
 elif tok=='unknown':
  status='MIXED_UNKNOWN_REFERENCE_CANDIDATE_PARTIAL_SCOPE' if picked else 'MIXED_UNKNOWN_REFERENCE_CANDIDATE_UNREVIEWED'
  flags.append('UNKNOWN_OR_MIXED_FINISH_NOT_AUTO_DISTINCT_PRODUCT')
 elif cid in ['BC-MCP-1','BC-MCP-2','BC-MCP-3','BC-MCP-4'] and c['finish_appearance']=='Rust effect':
  picked=base;status='UNREVIEWED_NAMED_FINISH_SOURCE_CANDIDATE';flags.append('RUST_ARRANGEMENT_REFERENCE_NOT_EQUAL_TO_REVIEWED_VERDIGRIS_RUST')
  notes.append('Current named scopes include White and Verdigris/Rust variants, but no distinct pure-Rust finish scope was found. Shared set photos do not prove a new individual finish or automatic equivalence.')
 elif cid=='BC-FFL-1':
  status='SOURCE_ONLY_INDIVIDUAL_PRODUCT_CANDIDATE';picked=base;flags+=['NO_REVIEWED_COMPLETE_INDIVIDUAL_PHOTO','OWNER_NAME_SPECIFICATION_SCOPE_PENDING']
  notes.append('Manufacturer describes100×22 individual FFL1 and repeat casts; retain source-only individual candidate even without mapped current offer or photo.')
 elif cid in ['BC-BONE-1','BC-BONE-2','BC-CR-RING'] and not baseworking and not namedpicked:
  status='SOURCE_ONLY_INDIVIDUAL_PRODUCT_CANDIDATE';picked=base;flags.append('OWNER_NAME_SPECIFICATION_SCOPE_PENDING')
 elif namedpicked:status='CURRENT_NAMED_SCOPE_PRESENT'
 elif baseworking:status='CURRENT_BASE_WORKING_SCOPE_PRESENT'
 elif picked:status='BASE_SOURCE_CANDIDATE_ONLY'
 else:status='UNREVIEWED_NAMED_FINISH_SOURCE_CANDIDATE';flags.append('NO_MATCHING_CURRENT_FINISH_SCOPE_FOUND')
 if not solo:flags.append('NO_BASELINE_ISOLATED_FRONT_FOLDER')
 if cid=='BC-WALL-CIRCLE':status='MIXED_UNKNOWN_FAMILY_CATALOGUE_CANDIDATE';flags.append('PATTERNS_BUILDS_SIZES_REQUIRE_INDIVIDUAL_SCOPE')
 if cid=='BC-CR-RING':notes.append('Maker CRS2 individual source/price evidence is present in preserved sources; BASE currently points at an arrangement and does not establish a reviewed isolated White front.')
 if cid=='BC-DR-SPIRAL' and c['finish_appearance']=='Verdigris and rust':notes.append('Arrangement-only rust/verdigris source does not select among current Bronze/Verdigris, Copper/Verdigris and Rust individual scopes. Retain as a candidate.')
 if cid=='BC-AC-TWO' and c['finish_appearance'] in ['Marbled green and white','Pewter appearance']:flags.append('BASELINE_NAMED_FINISH_NOT_IN_CURRENT_REVIEW_SCOPES')
 sourceoffers=[o for o,b in BOM.items() if any(v['component_id']==cid for v in b)]
 CF.append({'configuration_id':c['configuration_id'],'source_component_id':cid,'source_component_name':c['component_name'],'family':c['family'],'baseline_finish_appearance':c['finish_appearance'],'source_size_options':c['size_options'],'individual_front_state':c['individual_front'],'baseline_solo_folder_ids':split(c['solo_folder_ids']),'baseline_context_folder_ids':split(c['context_folder_ids']),'baseline_series_folder_ids':split(c['series_folder_ids']),'example_file_ids':split(c['example_file_ids']),'canonical_component_candidate':cc,'current_candidate_scope_keys':uniq(picked),'component_related_scope_keys':keys,'coverage_state':status,'flags':uniq(flags),'source_offer_refs':sourceoffers,'notes':notes,'distinct_product_created':False,'finish_name_or_chemical_composition_inferred':False,'physical_cast_or_mould_merge_inferred':False})

crosswalk={'owner_canonical_component_consolidations':P['canonical_component_consolidations'],'owner_canonical_variant_aliases':P['canonical_variant_aliases'],'moonphases_current_design_aliases':[{k:v.get(k) for k in ['catalogue_design_key','current_display_name','current_public_code','geometry','historical_component_ids','historical_maker_codes','current_number_is_verbatim_owner_instruction','physical_mould_or_stock_merge_authorized']} for v in P['catalogue_design_aliases'].values()],'historical_source_component_to_finish_aliases':P['historical_source_component_to_catalogue_aliases'],'documented_mould_orientation_options':R['aliases'],'scoped_owner_component_relationships':[{k:v.get(k) for k in ['decision_id','component_id','canonical_component_id','relationship','scope','same_actual_cast_or_mould_confirmed']} for v in U['component_identity_relationship_decisions']],'working_reference_dispositions':P['working_review_reference_dispositions'],'limits':'Owner catalogue-name/finish equivalence and documented orientation reuse do not authorize physical-cast merges or make different size/finish source assertions automatically equal. Each retained source offer and BOM position remains traceable.'}

preserve=[]
for cid in ['BC-BONE-1','BC-BONE-2','BC-FFL-1','BC-WALL-CIRCLE','BC-CR-RING']:
 c=COMP[cid]
 preserve.append({'component_id':cid,'name':c['name'],'current_base_scope_present':cid+'|BASE' in REV,'review_state':REV[cid+'|BASE'][4:6] if cid+'|BASE' in REV else None,'source_offer_refs':[o for o,b in BOM.items() if any(v['component_id']==cid for v in b)],'maker_rows':c.get('maker_rows'),'source_codes':c.get('source_codes'),'source_dimensions':c.get('dimensions_available'),'source_price_reference':c.get('historic_individual_price'),'treatment':'Retain as source-supported individual/product-family candidate with explicit identity/photograph/specification gaps; do not silently drop because no kept finish scope exists.'})

summary={'platform_records':len(OF),'baseline_bom_rows':sum(len(v) for v in BOM.values()),'all_platform_records_have_bom':all(BOM[o] for o in OFFERS),'source_offer_sale_scope_counts':dict(Counter(o['source_sale_scope'] for o in OF)),'platform_coverage_states':dict(Counter(o['coverage_state'] for o in OF)),'baseline_configurations':len(CF),'current_review_scopes':len(REV),'baseline_configuration_coverage_states':dict(Counter(c['coverage_state'] for c in CF)),'named_finish_source_candidates_without_current_named_scope':[c['configuration_id'] for c in CF if c['coverage_state']=='UNREVIEWED_NAMED_FINISH_SOURCE_CANDIDATE'],'source_only_individual_candidates':[c['configuration_id'] for c in CF if c['coverage_state']=='SOURCE_ONLY_INDIVIDUAL_PRODUCT_CANDIDATE'],'exact_matches_newly_certified':0,'new_products_or_variants_created':0,'shared_writes':0,'remote_calls':0}
result={'schema':'boldstone.individual-product-coverage-audit.v1','worker_number':2,'captured_inputs':json.load(open(W/'input_manifest.json')),'prepared_utc':datetime.now(timezone.utc).isoformat(),'refresh_as_of_utc':F['as_of_utc'],'review_progress_updated_utc':P['updated_utc'],'scope':'All81 cached platform records,122 baseline BOM rows and199 baseline configurations versus278 latest exported review scopes, with current owner naming/finish/orientation overlays. Source coverage is not certification of current account listings, physical stock or exact specimen identity.','summary':summary,'platform_coverage':OF,'baseline_configuration_coverage':CF,'canonical_crosswalks':crosswalk,'source_only_candidates_to_preserve':preserve,'rules':['Platform offers are source records, not canonical product counts.','Set offers preserve member multiplicities and whole-set prices/mass; no per-panel source quantities derived by division.','BASE, source alias, layout, build and finish review rows can overlap one sellable design;278 is a review-scope count.','Unknown/mixed/assorted colour configurations remain unreviewed reference candidates; they are not automatically additional products.','Owner current dimensions can supersede working catalogue dimensions without erasing conflicting historical offer-size assertions. Unresolved source sizes are not newly approved products.','The universal owner manufacture statement is retained as owner evidence; this audit creates no additional named products, measured specifications or stock counts.','All outputs and snapshots confined to worker-02; no shared or remote mutations.']}
(W/'coverage_map.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
(W/'current_scope_index.json').write_text(json.dumps([scope_ref(k) for k in REV],ensure_ascii=False,indent=2)+'\n')
print(json.dumps(summary,ensure_ascii=False,indent=2))
print('FINISH GAPS')
for c in CF:
 if c['coverage_state'] in ['UNREVIEWED_NAMED_FINISH_SOURCE_CANDIDATE','BASE_SOURCE_CANDIDATE_ONLY']:
  print(c['configuration_id'],c['source_component_id'],c['baseline_finish_appearance'],c['coverage_state'],c['current_candidate_scope_keys'])
