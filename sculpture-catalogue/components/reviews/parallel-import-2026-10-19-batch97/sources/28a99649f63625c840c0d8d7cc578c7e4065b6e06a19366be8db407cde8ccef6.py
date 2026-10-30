"""Prepare source-qualified working fields; never overwrite source dictionaries."""
import copy,json,hashlib
from pathlib import Path
from datetime import datetime,timezone
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
read=lambda p:json.loads(p.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
p=read(ROOT/'components/reviews/specification_review_progress.json');u=read(ROOT/'components/reviews/user_classifications.json');model=read(ROOT/'components/evidence/component_register.json');components={x['component_id']:x for x in model['components']};selected={x['scope']:x for x in read(HERE/'CACHED_IMAGE_CHECK.json')['selected']}
fields=['dimensions','weight','material_finish','fixing','individual_price','availability'];cards=[]
def spec(display,basis,status='WORKING_VALUES_UNDER_STANDING_POLICY;SOURCE_LABELS_AND_UNKNOWNS_RETAINED'):
 return dict(display=display,basis=basis,status=status,owner_approved=True,physical_value_verified=False)
def card(cid,scope,values,note):
 node=p['reviews'][cid] if scope=='BASE' else p['reviews'][cid]['size_finish_variants'][scope];name=node.get('canonical_name') or node.get('individual_listing_name') or components[cid]['name'];assert node['identity_confirmed'];assert len(values)==6
 original=copy.deepcopy(node);specs={f:spec(*v) if isinstance(v,tuple) else spec(v,'Existing exact-scope source values retained; current cast not measured.') for f,v in zip(fields,values)}
 if scope=='MCP4-VERDIGRIS-RUST':
  for f in ['individual_price','availability']:specs[f]=copy.deepcopy(node['accepted_working_specifications'][f]);specs[f]['physical_value_verified']=False
  ids=[x['proposal_id'] for x in node['specification_proposals']]
 else:ids=[(x['proposal_id'] if scope!='BASE' else '') for x in node.get('specification_proposals',[])] or [cid+':WORKING:'+f.upper() for f in fields]
 assert len(ids)==6 and len(set(ids))==6
 for f,i in zip(fields,ids):specs[f]['proposal_id']=i
 cards.append(dict(component_id=cid,scope=scope,canonical_name=name,decision_id='ROOT97:'+cid+':'+scope+':WORKING_SPECIFICATIONS',source_node_snapshot=original,source_specification_proposals_retained=copy.deepcopy(node.get('specification_proposals')),specifications=specs,approved_proposal_ids=ids,current_reference=selected[cid+'|'+scope],scope_note=note,owner_answer_for_this_scope=None,new_individual_owner_reply_events=0,physical_specs_verified=False,actual_stock_verified=False))

n=p['reviews']['BC-ICARUS'];a=n['available']
card('BC-ICARUS','BASE',[
 ('Panel 200 × 100 × 5 cm; framework 186 × 86 × 6.5 cm; face 15 mm; framework metal 4 mm — dated source claims, current artwork unmeasured','Single artwork panel and separate support framework dimensions retained; no total uniform-solid-volume mass inferred.'),
 ('Approximately 60 kg — native/public source approximation; current artwork unweighed','Retain 60 kg native source, distinct from superseded older 80 kg note. No packed, electrical or support load inferred.'),
 ('Bath Stone Jesmonite AC730 — listing stated; product gypsum wording conflicts with the dated manufacturer cementitious classification','Retain both source descriptions as a material-class conflict. No recipe, current cast formulation or fire/weather rating certified.'),
 ('Source describes stainless-steel French-cleat framework, powder-coated white RAL 9010; offered fixing choice: keyhole or French cleat; hardware/load/wall suitability unverified','Owner87 is a catalogue choice. Existing source framework is separate; alternative keyhole engineering for this large artwork remains unconfirmed.'),
 ('£3,500 per single artwork — 16 October 2026 source snapshot; current quote unconfirmed','Whole single artwork offer O061. No panel/framework price allocation or current source refresh claimed.'),
 ('Made to order in Bath/England; historical 6–8 week estimate observed 16 October 2026; current stock, capacity and lead time unconfirmed','Historical source policy retained. Optional concealed LED electrical specification, care and packed dimensions remain unresolved.')
], 'Existing single Icarus artwork; panel/framework/optional LED distinctions retained. All source measurements and material claims remain source qualified.')
for cid,dimensions,weight,price,offer in [('BC-AC-FULL','50 × 30 × 6 cm','8 kg',175,'O076'),('BC-AC-FLOWER','30 × 30 × 6 cm','4 kg',175,'O077')]:
 card(cid,'BASE',[
  (dimensions+' — native White listing claim; current cast unmeasured','Exact White source '+offer+'. Older brochure versions and Gold finish records remain distinct.'),
  ('Approximately '+weight+' per White panel — native source; current cast unweighed','Do not transfer this White weight to Gold or other finishes; no arrangement mass divided.'),
  ('Plaster with smooth contoured White relief — native description; exact substrate recipe/coating and cast applicability unverified','Source '+offer+' applies to the White offer. No recipe or outdoor durability certificate inferred from the photograph.'),
  ('Recessed rear fixing — native description; offered choice: keyhole or French cleat; current hardware, number and load unknown','Preserve source recessed-fixing statement and owner87 offered choices separately. No new installed-hardware certification.'),
  ('£175 per White sculpture — dated 16 October 2026 source price; current offer unconfirmed','Source '+offer+' is one White artwork. Acanthus Full Gold O071 £250 source/working Gold record is not the White price.'),
  ('Made to order / enquiry — working proposal; current stock, reproducibility and lead time unknown','Owner says designs were made; this does not establish present inventory or current production capacity.')
 ], 'Existing White component scope; Gold and other finishes remain separate. Current single-White source offer retained; no new product or name inferred.')
for cid in ['BC-BR-1','BC-BR-2']:
 src=components[cid]
 card(cid,'BASE',[
  ('50 × 25 × 8 cm native per White panel; historical maker side depth 5–7 cm — source conflict, current cast unmeasured','O029 BM-2P-50.50 is a pair offer; these face/side claims explicitly apply to each component. No pair dimension divided.'),
  ('Maker 6–8 kg calculated per White panel; 2025 trade 6 kg each and named retail 7 kg each — separate source versions; current cast unweighed','Maker and draft source values are per component, independent of the pair export mass. Do not average them or divide a set weight.'),
  ('White marble stone finish; historical Jesmonite AC730 maker specification — current cast chemistry and coating unverified','Historical White source only. No transfer of Gold finish, gold-leaf content or Gold working price.'),
  ('Historical single small stainless-steel fixing, centre rear/top third; offered choice: keyhole or French cleat; actual hardware/count/load unverified','Historical maker arrangement alignment is not a current back photograph or load test.'),
  ('£250 per White component — new uncosted working proposal. Separate 2025 individual references: £248.50 older standard; £156 trade; £312.50 named retail','Rounded from the older individual White standard, not divided from O029 pair price. Trade p5 and named retail p1 per-piece figures are retained as distinct dated source versions; current individual offer, VAT and delivery unknown.'),
  ('Made to order / enquiry — working proposal; stock, mould condition and lead time unknown','Historical pair availability does not verify separate current component stock or a live individual listing.')
 ], 'Existing White Brancusi component; pair SKU BM-2P-50.50 remains a two-panel source offer. No Gold approval transfer or set-price/weight division.'+(' Selected Brancusi2 primary is a cached derivative; native-original bytes remain unverified for that selected image.' if cid=='BC-BR-2' else ''))
for cid in ['AM-S1','AM-S2','AM-L1','AM-L2']:
 n=p['reviews'][cid];small=cid.startswith('AM-S');price=300 if small else 1500
 card(cid,'BASE',[
  (n['dimensions_available'],'Preserve native, maker and 2025 versions separately; these are individual component dimensions, not a division of pair size.'),
  (n['weight_available'],'Individually sourced per-panel estimates; native pair 16 kg small / 45 kg large remain separate and are not divided.'),
  (n['material_available'],'Historical size-specific AC730 White standard retained; pictured cast substrate/finish recipe not independently certified.'),
  (n['fixing_available']+' Offered choice: keyhole or French cleat; current hardware and load unverified.','Source small one-fixing and large two-LARGE-fixing instructions remain size specific. Owner87 does not certify actual counts, attachment or rating.'),
  (f'£{price:,} per individual '+('small' if small else 'large')+' panel — new uncosted working proposal; exact individual offer unknown','Small £300 is a broad design-price comparison with the dated Brancusi 50 × 25 cm £248.50 individual standard. Large £1,500 is a broad comparison with Icarus £3,500 at 2 m² (0.72 m² face suggests about £1,260 before an uncosted design allowance). Neither proposal divides the small £520 / large £2,880 native pair or 2025 arrangement prices.'),
  ('Made to order / enquiry — working proposal; individual stock, reproduction capacity and lead time unconfirmed','Original individual price/availability were empty. No pair Unlimited/InStock value, finite stock count or root MCP4 one-week policy transferred.')
 ], 'Existing individual Ammonite size/member scope '+cid+'; component identity '+n['component_id']+' and '+n['maker_panel_code']+' retained. Pair-only dimensions, weights and prices remain outside individual specifications; source conflicts retained.')
for scope in ['MCP4-SILVER-BRONZE-25','MCP4-VERDIGRIS-25','MCP4-VERDIGRIS-RUST']:
 n=p['reviews']['BC-MCP-4']['size_finish_variants'][scope];values=[]
 for x in n['specification_proposals']:
  text=x['display'];basis=x.get('basis','Exact finish source retained; current cast not independently measured.')
  if x['field']=='Individual retail price' and scope=='MCP4-SILVER-BRONZE-25':text='£350 per panel — dated public listing reference; current exact offer unconfirmed. Second native price 80.33 has unencoded currency and remains unresolved.'
  if x['field']=='Individual retail price' and scope=='MCP4-VERDIGRIS-25':text='£120 per panel — working proposal; native 40 (unencoded currency) and cached public £120 source versions remain unresolved.'
  if x['field']=='Fixing':basis+=' Earlier visible rear/hanger references are source claims; exact selected-front/back pairing, current installed count and load remain unconfirmed. Owner87 offers keyhole or French cleat.'
  values.append((text,basis))
 card('BC-MCP-4',scope,values,'Exact consolidated finish only. Existing Silver/Bronze and Verdigris photo groups remain combined under owner-approved finish identities. Root Verdigris/Rust owner4kg, plaster composite/faux finish, keyhole type, £175/MTO/Unlimited/one-week policy remain finish specific; actual fixing count remains unknown.')
bar=p['reviews']['BC-BAR-WAVE'];bar_ids=next(x['approved_proposal_ids'] for x in u['specification_decisions'] if x['component_id']=='BC-BAR-WAVE' and len(x.get('approved_proposal_ids',[]))==6);assert len(set(bar_ids))==6
recovery={f:dict(copy.deepcopy(x),owner_approved=True,physical_value_verified=False,proposal_id=bar_ids[i]) for i,(f,x) in enumerate(zip(fields,bar['specification_review_items']))}
out=dict(status='PREPARED;ROOT_IMPORT97_PENDING',prepared_utc=datetime.now(timezone.utc).isoformat(),source_last_import_at_preparation=p['latest_parallel_import']['batch'],standing_policy_id=p['working_specification_acceptance_policy']['policy_id'],cards=cards,existing_Barbados_display_recovery=dict(component_id='BC-BAR-WAVE',scope='BASE',source_node_snapshot=copy.deepcopy(bar),specifications=recovery,new_approval_events=0),reference_dispositions={'BC-MCP-4|BASE':dict(disposition='FAMILY_FINISH_REFERENCE_HEADER',description='Canonical design heading. Use MCP4-WHITE and the separately scoped consolidated finish reviews; no additional White sculpture or duplicate six-field approval created.'),'BC-PORTMAN-1|BASE':dict(disposition='GROUP_POSITION_REFERENCE_NO_NEW_SALE_UNIT',description='Existing courtyard left-position name/context retained. No object-specific size/construction or additional distinct mould/sale unit established. Group-photo component identification remains deferred under owner instruction; no mass, price or additional product invented from the scene.')},new_individual_owner_replies=0,new_owner_policy_events=0,new_physical_or_identity_counts=0,remote_mutations=0,new_private_original_downloads=0)
assert len(cards)==12
(HERE/'ROOT97_PREPARED.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print(json.dumps(dict(status=out['status'],cards=len(cards),existing_display_recovery=1,reference_dispositions=2,new_replies=0,new_remote_writes=0)))
