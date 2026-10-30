import json
import hashlib
from pathlib import Path
from datetime import datetime, timezone

W = Path(__file__).resolve().parent
A = json.loads((W / 'assignment.json').read_text())
ASSETS = {x['id']: x for x in A['assets']}
GROUPS = {x['group_ref']: x for x in A['groups']}
OFFERS = {x['offer_ref']: x for x in A['platform_records']}
VIS = json.loads((W / 'visual_review_candidates.json').read_text())
V = {x['review_id']: x for x in VIS}
CR = {x['review_id']: x for x in json.loads((W / 'visual_cr_all.json').read_text())}
FFS = {x['review_id']: x for x in json.loads((W / 'visual_ffs_all.json').read_text())}
DOC = {x['label']: x for x in A['document_sources']}
RETAIL = 'retail-2025:pages1-3; dated estimated white-marble made-to-order standard, not current or other finishes'
BROCHURE_A = 'brochure-2016-inside-a:page1, labelled Coral Spiral photograph'

# Values here are advisory review text. They never update the shared register.
MANUAL = {
 'BC-CORAL': {
  'primary':'G056-1',
  'identity':'Complete approximately square rough-textured relief; branching nested spiral/ripple ridges. The geometry matches the labelled Coral Spiral photograph in the 2016 brochure.',
  'dimensions':('55 × 55 cm face: dated 2016 brochure design claim; depth unrecorded.', 'Propose 55 × 55 cm as the dated design size. WORKING GUESS for depth: about 5–7 cm, using related relief templates; measure this cast before adopting.', 'dated_caption_plus_working_guess'),
  'weight':('No individual Coral Spiral weight found.', 'WORKING GUESS: about 10–14 kg for a 55 × 55 cm mineral-composite version, anchored to the 2025 55 × 55 cm standard estimate of 12 kg. Different backing, hollowing or substrate could change this materially.', 'working_guess_only'),
  'material_finish':('White/off-white rough stone-like appearance in the reviewed image; chemistry unestablished.', 'WORKING GUESS: cast mineral composite with an aggregate-rich white finish; Jesmonite AC730 is a possible studio-standard analogue, not an identified material for this object.', 'visual_appearance_plus_working_guess'),
  'fixing':('Rear fixing and wall interface not shown or documented for this component.', 'WORKING GUESS for review wording: concealed cast-in rear fixing, subject to maker confirmation of type, number, position and wall attachment. No load rating can be proposed from these views.', 'working_guess_only'),
  'individual_price':('No linked individual offer or current Coral Spiral price.', 'WORKING GUESS for owner discussion: around GBP 550–650 in standard white, using the dated 2025 55 × 55 cm reference of GBP 562.36 as an analogy. This is not a quote or an approved price.', 'working_guess_only'),
  'availability':('No physical stock or current sale decision established.', 'Proposed owner-choice wording: “Made to order — enquire”, if the maker confirms this design is still producible. Do not assign stock, lead time or orderability from photographs.', 'unknown_owner_decision'),
  'conflicts':['The snapshot summary says no component dimensions established; the separately checked 2016 caption supplies a 55 × 55 cm design-level face size. It does not establish depth or the dimensions of every photographed cast.'],
  'extra_refs':[BROCHURE_A,RETAIL],
 },
 'BC-CR-SPIRAL': {
  'primary':'C28',
  'identity':'One complete square textured spiral panel reviewed in the expanded local selection C28; distinguish continuous spiral CRS1 from concentric cup-ring CRS2.',
  'dimensions':('Maker row 26: approximately 30 × 30 cm, side 5–7 cm; dated standard white template.', 'Propose 30 × 30 × 5–7 cm only for the matching historical CRS1 white AC730 version; confirm exact photographed version.', 'dated_maker_claim'),
  'weight':('Maker row 26 calculates 3–5 kg each; 2025 30 × 30 cm retail table estimates 5.5 kg each.', 'Use 3–5 kg as the maker-template estimate while showing 5.5 kg as a conflicting later retail estimate. Weigh the actual cast; do not silently select one value.', 'conflicting_dated_estimates'),
  'material_finish':('Maker row 26 specifies White Marble Stone Finish Jesmonite AC730 for the standard template; photographs show weathered/coloured appearances.', 'Propose Jesmonite AC730 / white marble stone finish only for that template. WORKING GUESS: the reviewed textured cast belongs to this design family; its weathering/colour does not establish its chemistry.', 'dated_maker_claim_finish_scope'),
  'fixing':('Maker row 26: one small stainless-steel fixing, centred on the back in the top third, aligned consistently across the series.', 'Propose this as a historical fixing instruction; verify that the reviewed cast has it and confirm wall hardware. No load rating is supplied.', 'dated_maker_instruction'),
  'individual_price':('2025 estimated white standard: GBP 182.05 each at 30 × 30 cm; no linked current standalone platform offer.', 'WORKING GUESS for a current review seed: about GBP 180–230 each in standard white, pending owner pricing; use GBP 182.05 only as a dated reference.', 'dated_reference_plus_working_guess'),
  'availability':('Historical white standard is made to order; current mould condition, stock and sale decision unknown.', 'Propose “Made to order — enquire” only after maker confirmation; paver photographs do not establish current walking-surface suitability.', 'dated_general_policy_not_stock'),
  'conflicts':['Register rollup omits dimensions even though row 26 states 300 × 300 mm with a 50–70 mm side.','Maker estimate 3–5 kg conflicts with the 2025 table estimate of 5.5 kg.','Most isolated Spiral White representatives are close-up crops; C28 is the reviewed complete single panel. Appearance under the White folder varies and is not chemical finish evidence.'],
  'extra_refs':[RETAIL],
 },
 'BC-CR-RING': {
  'primary':None,
  'identity':'Concentric cup-ring panel is distinct from the continuous spiral in reviewed two-panel arrangements. The sole isolated Cup Ring White image is a close-up crop; no complete single-component photo was identified among all 29 cached family assets.',
  'dimensions':('Maker row 27: approximately 30 × 30 cm, side 5–7 cm; dated standard white template.', 'Propose 30 × 30 × 5–7 cm only for the matching historical CRS2 white AC730 version; exact cast remains unmeasured.', 'dated_maker_claim'),
  'weight':('Maker row 27 calculates 3–5 kg each; 2025 30 × 30 cm retail table estimates 5.5 kg each.', 'Retain both dated estimates until this panel is weighed separately.', 'conflicting_dated_estimates'),
  'material_finish':('Maker row 27 specifies White Marble Stone Finish Jesmonite AC730 for the historical standard.', 'Propose that material only for the matching standard version; WORKING GUESS for other photographed versions: mineral composite with applied/aged finish, composition unconfirmed.', 'dated_maker_claim_finish_scope'),
  'fixing':('Maker row 27: one small stainless-steel fixing at centre back in top third, consistently positioned within series.', 'Propose as a historical instruction, subject to rear inspection and wall-hardware confirmation; no load rating supplied.', 'dated_maker_instruction'),
  'individual_price':('2025 estimated white standard: GBP 182.05 each at 30 × 30 cm; no linked current standalone offer.', 'WORKING GUESS: GBP 180–230 each in standard white for owner discussion; no price inferred by dividing a pair.', 'dated_reference_plus_working_guess'),
  'availability':('Current stock and production readiness unknown; historical white standard made to order.', 'Propose “Made to order — enquire” if the maker confirms current mould and sale status.', 'dated_general_policy_not_stock'),
  'conflicts':['Register rollup omits the explicit 30 × 30 cm maker dimensions.','Maker 3–5 kg estimate versus later retail 5.5 kg estimate.','Complete Cup Ring panels exist in arrangements, but isolated source G062 is cropped. Arrangement photos remain context, not a certified single-product primary.'],
  'extra_refs':[RETAIL],
  'ready':False,
 },
 'BC-DDR-WAVE': {
  'primary':'G069-1',
  'identity':'Complete long white relief with flowing parallel wave channels. Maker DDR1 and DDR3 are repeated/rotated positions of the wave form; they are not automatically two distinct designs.',
  'dimensions':('Native two-piece offer O013 says 100 × 22 × 6 cm per part. Maker rows 61/63 say approximately 100 × 22 cm, side 5–7 cm.', 'Propose 100 × 22 × about 6 cm for the matching white template, retaining maker side range 5–7 cm; confirm orientation and cast.', 'dated_native_and_maker_claims'),
  'weight':('Maker rows 61/63 calculate 8–10 kg each; 2025 table estimates 10 kg each. O013 20 kg belongs to the pair.', 'Use approximately 8–10 kg per matching standard component as a historical estimate; no per-piece weight is derived from 20 kg set weight.', 'dated_individual_estimates'),
  'material_finish':('Historical standard: White Marble Stone Finish Jesmonite AC730. O013 describes white marble stone finish; verdigris photos are separate appearance versions.', 'Propose the AC730 white template for the reviewed white candidate only after cast/version confirmation. WORKING GUESS for green variants: applied patina on cast composite, not solid bronze.', 'dated_maker_claim_finish_scope'),
  'fixing':('Maker rows 61/63: one small stainless-steel fixing in centre back top third, aligned with series.', 'Retain as historical instruction; verify actual panel and orientation. Rotating the relief may require a different fixing position; no load rating supplied.', 'dated_maker_instruction'),
  'individual_price':('2025 white 100 × 22 cm reference GBP 432.41 each; O013 GBP 880 is for two parts.', 'WORKING GUESS: about GBP 430–500 for a standard-white individual panel, subject to owner quote. Do not divide the GBP 880 offer as sourced individual pricing.', 'dated_reference_plus_working_guess'),
  'availability':('No current individual stock or standalone sale status established.', 'Propose individual made-to-order enquiry if maker confirms sale separately; existing O013 is an arrangement offer.', 'unknown_owner_decision'),
  'conflicts':['DDR1/DDR3 are mould repetition/rotated positions; avoid duplicate product identities.','Native depth 6 cm versus maker side range 5–7 cm are different levels of precision, not a verified measurement.','Pair weight/price remain at offer level.'],
  'extra_refs':[RETAIL],
 },
 'BC-DDR-SPIRAL': {
  'primary':'G067-1',
  'identity':'Complete long white relief with two spiral centres and flowing channels; maker code DDR2 distinguishes it from the straight wave form.',
  'dimensions':('O013 says 100 × 22 × 6 cm per part; maker row 62 approximately 100 × 22 cm, side 5–7 cm.', 'Propose 100 × 22 × about 6 cm for the matching white template, preserving side range 5–7 cm pending measurement.', 'dated_native_and_maker_claims'),
  'weight':('Maker row 62 calculates 8–10 kg each; 2025 table estimates 10 kg each. O013 20 kg is the two-part set.', 'Use 8–10 kg as a historical single-template estimate; weigh current cast separately.', 'dated_individual_estimates'),
  'material_finish':('Maker row 62: White Marble Stone Finish Jesmonite AC730; native O013 white finish. Green appearance is another version.', 'Propose this historical white material only after cast/version confirmation; green finish chemistry remains unestablished.', 'dated_maker_claim_finish_scope'),
  'fixing':('Maker row 62: one small stainless-steel fixing, centre back top third, aligned across series.', 'Historical template only; confirm actual panel and intended vertical/horizontal orientation. No wall hardware or load rating established.', 'dated_maker_instruction'),
  'individual_price':('2025 white 100 × 22 cm reference GBP 432.41 each; O013 GBP 880 is the pair.', 'WORKING GUESS: about GBP 430–500 per standard-white panel for owner pricing review; no division of set price used.', 'dated_reference_plus_working_guess'),
  'availability':('No current individual stock or sale decision established.', 'Propose made-to-order enquiry for an individual DDR2 if maker confirms this sales unit.', 'unknown_owner_decision'),
  'conflicts':['O013 is a pair; neither its price nor total weight is assigned to DDR2.','Photographs in vertical and horizontal settings do not prove the same fixing arrangement or size.'],
  'extra_refs':[RETAIL],
 },
 'BC-DP-PALM1': {
  'primary':'G073-1',
  'identity':'Complete upright palm panel with opposing curved frond channels meeting near the lower centre. Internal Palm 1 maps to platform title Palm Form Two (O054), so names/numbers must not be conflated.',
  'dimensions':('O027: 45 × 40 × 6 cm each; O054/O055/O056: 40 × 45 × 6 cm each. The 30 × 30 cm O020 image shows Two Leaves plus Spiral, not this Palm panel.', 'Propose versioned sizes 45 × 40 × 6 cm and 40 × 45 × 6 cm; confirm whether orientation ordering or distinct versions explains them. Do not automatically assign 30 × 30 cm to Palm 1.', 'conflicting_or_versioned_native_claims'),
  'weight':('No confirmed current individual Palm 1 weight. 2025 Grecian Palms 45 × 40 cm table estimates 8 kg each.', 'WORKING GUESS: roughly 7–9 kg for the corresponding large mineral-composite version, using the explicitly each-piece 8 kg reference. This is not a share of O027/O055 set weight.', 'dated_analogy_plus_working_guess'),
  'material_finish':('O054 and recent Palm Form arrangements claim gypsum composite, stone finish; O027 says white marble stone finish. No manufacturing row establishes AC730 for this design.', 'Propose “gypsum composite, stone finish” only for the native O054 version, pending object applicability; do not substitute AC730 across sources.', 'native_offer_claim_finish_scope'),
  'fixing':('O054 says ready to hang; no object-specific fixing drawing, count or load record found.', 'WORKING GUESS: concealed rear fixing; ask maker to identify fixing type/position and wall interface. “Ready to hang” is not a load rating.', 'generic_offer_claim_plus_working_guess'),
  'individual_price':('Cached O054 standalone Palm Form Two: GBP 600. 2025 Grecian Palms reference: GBP 345.28 each at 45 × 40 cm.', 'Use GBP 600 only as the dated linked offer price, subject to maker confirmation of current version and price. Keep the lower 2025 reference visible; arrangement prices do not price this member.', 'dated_native_price_version_conflict'),
  'availability':('O054 export/public cache is an offer record; physical stock and current readiness unconfirmed.', 'Propose “Enquire / made to order” for owner decision; do not turn Unlimited or InStock metadata into inventory.', 'cached_offer_not_physical_stock'),
  'conflicts':['Palm 1 is Palm Form Two on O054; Palm 2 is Palm Form One on O053.','Register rollup includes 30 × 30 cm in this family, but O020 BOM has Two Leaves plus Spiral, so that small size lacks a component-specific Palm 1 link.','45 × 40 cm and 40 × 45 cm need version/orientation confirmation.','2025 GBP 345.28 is a dated white-standard reference, not the GBP 600 native single offer.'],
  'extra_refs':[RETAIL],
 },
 'BC-DP-PALM2': {
  'primary':'G074-1',
  'identity':'Complete palm panel with curved frond channels sweeping from the lower left; distinct from Palm 1. Internal Palm 2 maps to platform Palm Form One (O053).',
  'dimensions':('O027: 45 × 40 × 6 cm each; O053/O055: 40 × 45 × 6 cm each. 30 × 30 cm lacks a component-specific Palm 2 BOM link.', 'Propose versioned 45 × 40 × 6 cm / 40 × 45 × 6 cm until maker confirms orientation versus a distinct size. The reviewed image has no calibrated scale.', 'conflicting_or_versioned_native_claims'),
  'weight':('No confirmed current individual Palm 2 weight; 2025 Grecian Palms 45 × 40 cm reference estimates 8 kg each.', 'WORKING GUESS: roughly 7–9 kg for that large mineral-composite version; weigh actual cast. Do not divide arrangement weights.', 'dated_analogy_plus_working_guess'),
  'material_finish':('O053 claims gypsum composite, stone finish; O027 white marble stone finish. No component manufacturing row certifies AC730.', 'Propose gypsum composite / stone finish only for the linked O053 version, subject to maker confirmation.', 'native_offer_claim_finish_scope'),
  'fixing':('O053 says ready to hang; exact fixing type, quantity, position and load rating not established.', 'WORKING GUESS: concealed rear fixing, to be specified by maker with the appropriate wall attachment.', 'generic_offer_claim_plus_working_guess'),
  'individual_price':('Cached O053 standalone Palm Form One: GBP 600; 2025 Grecian Palms reference GBP 345.28 each at 45 × 40 cm.', 'Use the linked GBP 600 only as a dated offer claim requiring price/version confirmation; do not use set prices for this member.', 'dated_native_price_version_conflict'),
  'availability':('Offer visibility/stock flags do not verify physical stock, current mould readiness or sale decision.', 'Propose “Enquire / made to order” only after owner selects availability wording.', 'cached_offer_not_physical_stock'),
  'conflicts':['Palm 2 maps to platform Palm Form One, not Palm Form Two.','Small 30 × 30 cm family source O020 is a Two Leaves-plus-Spiral arrangement, not a confirmed Palm 2 size.','45 × 40 and 40 × 45 cm are not silently merged.'],
  'extra_refs':[RETAIL],
 },
 'BC-DP-SPIRAL': {
  'primary':'G080-1',
  'identity':'Complete broad smooth spiral panel. O046 Golden Spiral and O047 Timeless Spiral share geometry but have different sizes/finishes; other offers sell the spiral in arrangements.',
  'dimensions':('O046 gold: 30 × 30 × 5 cm. O020 white arrangement: 30 × 30 × 6 cm each. O047 white: 45 × 40 × 5 cm. O027: 45 × 40 × 6 cm each. O055/O056: 40 × 45 × 6 cm each.', 'Propose separate size/finish variants instead of one canonical number; select the actual cast/version before approval.', 'multiple_native_versions'),
  'weight':('O046 single-item export: 6 kg; O047 single-item export: 10 kg. 2025 Grecian Spiral 45 × 40 cm table estimates 8 kg.', 'Retain 6 kg for O046 and 10 kg for O047 as native claims, plus 8 kg dated reference. Do not apply one version to all white/gold images.', 'conflicting_or_versioned_dated_claims'),
  'material_finish':('O046 describes gold leaf; O047 white marble stone finish; recent Palm Form arrangement descriptions say gypsum composite / stone finish.', 'Propose “white marble stone finish; substrate to confirm” for the reviewed white primary. Gold leaf appearance/version remains separate; no claim of solid gold or universal AC730.', 'native_offer_claim_finish_scope'),
  'fixing':('Exact object-specific fixing not found; recent arrangements say ready to hang.', 'WORKING GUESS: concealed rear fixing for each separate panel; ask maker for type, number, positions and wall hardware. No load rating established.', 'working_guess_only'),
  'individual_price':('Cached O046 Golden Spiral GBP 250; O047 Timeless Spiral GBP 500. 2025 Grecian Spiral standard GBP 345.28 each. O055/O056 prices are arrangements.', 'Use size/finish-linked dated individual offers as review seeds: GBP 250 small gold / GBP 500 large white. Current price requires owner decision; no set-price allocation.', 'dated_native_prices_multiple_versions'),
  'availability':('Historical/native offers exist; no current physical stock or per-version readiness verified.', 'Propose made-to-order enquiry for each chosen size/finish, subject to maker confirmation.', 'cached_offer_not_physical_stock'),
  'conflicts':['30 × 30 versus 45 × 40 versus 40 × 45 cm; depth 5 versus 6 cm.','Native 6/10 kg values and 2025 8 kg estimate have different version/date scopes.','GBP 250/500 individual prices must not be replaced by fractions of arrangement offers.'],
  'extra_refs':[RETAIL],
 },
 'BC-DP-LEAVES': {
  'primary':'G084-1',
  'identity':'Complete square-like quarter-arc/two-leaf panel, distinct from Palm 1 and Palm 2. O020 title says Palm but its reviewed photograph and BOM show Two Leaves plus Spiral.',
  'dimensions':('O020 says 30 × 30 × 6 cm each part. Generic 45 × 40 cm family references are not a direct calibrated link to this Two Leaves cast.', 'Propose 30 × 30 × 6 cm as the linked dated O020 component claim. WORKING GUESS: a larger companion variant might exist, but keep its size unassigned until maker evidence identifies it.', 'dated_native_component_claim'),
  'weight':('O020 12 kg is the pair; no individual Two Leaves weight is established.', 'WORKING GUESS: approximately 4–6 kg for a 30 × 30 × 6 cm mineral-composite version, using related small reliefs. This is an analogy, not 12 kg divided by two.', 'working_guess_only'),
  'material_finish':('O020 describes white marble stone finish; no object-specific substrate identified.', 'WORKING GUESS: cast mineral composite with white stone finish; ask maker whether gypsum, AC730 or another binder applies.', 'visible_native_finish_plus_working_guess'),
  'fixing':('No component-specific fixing record; front view does not show the back.', 'WORKING GUESS: concealed rear fixing; type, number, location and wall hardware require maker confirmation, with no inferred load rating.', 'working_guess_only'),
  'individual_price':('No linked standalone Two Leaves offer. O020 GBP 480 is for the pair.', 'WORKING GUESS: GBP 180–260 for a standard-white 30 × 30 cm individual panel, using dated small-relief references rather than halving GBP 480. Owner must price it.', 'working_guess_only'),
  'availability':('No individual current stock or sale decision established.', 'Propose individual made-to-order enquiry if maker confirms the design can be supplied separately.', 'unknown_owner_decision'),
  'conflicts':['The O020 Palm title conflicts with its Two Leaves primary image; retain the visual BOM mapping and expose the title mismatch.','The mixed pewter G137 image places this smaller panel beside Egyptian Palm; it does not make them one family or establish its substrate.','Pair weight and price are not member values.'],
 },
 'BC-DECO-1': {
  'primary':'G088-1',
  'identity':'Complete long terracotta-effect panel with large alternating folded wave planes. Keep coloured Decowaves separate from the historical white Frozen Decowaves until mould equivalence is confirmed.',
  'dimensions':('O050 terracotta single: 90 × 15 × 9 cm. O060 verdigris pair: 90 × 15 × 8 cm each panel.', 'Propose two dated finish/version claims: terracotta depth 9 cm, verdigris depth 8 cm. Measure exact cast before combining variants.', 'multiple_native_versions'),
  'weight':('O050 terracotta single: approximately 6 kg. O060 approximately 14 kg is the total coloured pair.', 'Use approximately 6 kg only for the linked terracotta single claim. WORKING GUESS for a verdigris member: roughly 6–9 kg by nearby individual templates; not 14 kg divided by two.', 'native_individual_claim_plus_working_guess'),
  'material_finish':('O050 claims gypsum composite with terracotta surface effect. O060 describes cast composite with hand-applied verdigris patina.', 'Propose those exact offer-specific claims for matching versions; visible verdigris does not establish bronze construction or exterior performance.', 'native_offer_claim_finish_scope'),
  'fixing':('O050 terracotta single: ready to hang with keyhole fixing, vertical orientation. O060 only says ready to hang.', 'Propose keyhole fixing for O050 only after cast match; WORKING GUESS for verdigris: concealed rear fixing, type unconfirmed. No load rating supplied.', 'native_specific_claim_plus_working_guess'),
  'individual_price':('Cached O050 terracotta single GBP 48.44. O060 GBP 600 is the coloured pair.', 'Flag GBP 48.44 for owner review as an unusually low linked individual offer, without correcting it automatically. WORKING GUESS for a newly priced standard-size coloured member: GBP 280–350, using the dated white 90 × 15 cm reference GBP 281.97 plus unpriced finish difference; not a division of GBP 600.', 'dated_native_anomaly_plus_working_guess'),
  'availability':('Cached O050/O060 offer flags are not physical stock; current sale decision unverified.', 'Propose “Enquire / made to order” per finish if owner confirms. No stock quantity or lead time inferred.', 'cached_offer_not_physical_stock'),
  'conflicts':['Terracotta 9 cm versus verdigris 8 cm depth; keep version scopes.','Terracotta single approximately 6 kg versus coloured-pair total approximately 14 kg; no automatic per-panel allocation.','GBP 48.44 is a source anomaly to confirm, not an approved market price.','Coloured Decowaves and white Frozen Decowaves have similar family titles but are not silently merged.'],
  'extra_refs':[RETAIL],
 },
}

from remaining_specs import DATA, add_first_ten_sources
MANUAL.update(DATA)
add_first_ten_sources(MANUAL)

FIELD_WORDS = {
 'dimensions': ['dimension','length','width','height','each component','cast description'],
 'weight': ['weight'],
 'material_finish': ['material','finish','manufacturing description'],
 'fixing': ['fixing','mounting'],
 'individual_price': ['price','retail reference'],
 'availability': ['stock','visible','availability','published','status','production','options'],
}

def claim_refs(cid, field=None):
    out = []
    for x in A['claims']:
        if x['component_id'] != cid:
            continue
        if field and not any(k in x['field'].lower() for k in FIELD_WORDS[field]):
            continue
        ref = x['source_ref']
        if ref not in out:
            out.append(ref)
    return out

def picture(rid, usage='alternate'):
    if rid in V:
        v = V[rid]
        a = ASSETS[v['file_id']]
        ref = v['group_ref']
        contact = v['contact_sheet']
    elif rid in CR:
        a = CR[rid]
        ref = next((g['group_ref'] for g in A['groups'] if g['id'] == a['folder_id']),None)
        contact = str(W / f"visual-cr-all-{(int(rid[1:])-1)//15+1:02d}.jpg")
    else:
        a = FFS[rid]
        ref = 'G172'
        contact = str(W / f"visual-ffs-all-{(int(rid[1:])-1)//15+1:02d}.jpg")
    return {
      'file_id':a['id'],'folder_id':a['folder_id'],'preview_path':a['thumb'],
      'source_path_dated':a['path'],'group_ref':ref,'review_id':rid,
      'reviewed_locally':True,'contact_sheet':contact,'usage':usage,
      'limits':'Cached thumbnail/contact-sheet review only; exact current metadata/link verification is reserved to the parent. No installation provenance or physical specification certified.'
    }

def platform_mapping(cid):
    out=[]
    seen=set()
    for b in A['bom']:
        if b['component_id']!=cid:continue
        if b['offer_ref'] in seen:continue
        seen.add(b['offer_ref'])
        member_rows=[z for z in A['bom'] if z['offer_ref']==b['offer_ref'] and z['component_id']==cid]
        p=OFFERS[b['offer_ref']]
        one=p['sale_unit_state']=='Sale component' and len([z for z in A['bom'] if z['offer_ref']==b['offer_ref']])==1
        out.append({
          'offer_ref':b['offer_ref'],'platform':p['platform'],'sq_id':p['sq_id'],'shopify_handle':p['sh_handle'],
          'sku':p['sku'],'title':p['title'],'source_url':p['source_url'],'source_row':p['source_row'],
          'mapping_state':b['mapping_state'],'mapping_cautions':b['cautions'] or p['cautions'],
          'sale_unit_state':p['sale_unit_state'],'quantity_of_component_in_offer':sum(int(z['quantity']) for z in member_rows),
          'bom_positions':[{'bom_id':z['bom_id'],'position':z['position'],'quantity':z['quantity'],'orientation':z.get('orientation')} for z in member_rows],
          'standalone_component_offer':one,
          'native_offer_price':p['native_price'],'native_currency':p.get('native_currency'),
          'cached_public_price':p.get('public_price'),'cached_public_currency':p.get('public_currency'),
          'cached_public_availability':p.get('public_availability'),'native_stock_flag':p.get('stock'),
          'image_file_id':p['image_file_id'],'image_state':p['image_state'],
          'limits':'Dated assignment/native-export mapping, not a new live page check or an exact physical-cast identity. Prices/weights of arrangements remain offer-level. Inventory flags do not establish stock.'
        })
    return out

def make(cid):
    c=next(x for x in A['components'] if x['component_id']==cid)
    m=MANUAL[cid]
    primary=m['primary']
    if primary:
        p=picture(primary,'primary')
        p.update(shows_complete_single_component=True,selection_reason=m['identity'])
    else:
        p={'file_id':None,'folder_id':None,'preview_path':None,'shows_complete_single_component':False,
           'selection_reason':m['identity']}
    related=[v for v in VIS if v['group_ref'] in c['group_refs'] and v['group_ref'] not in m.get('exclude_groups',[])]
    alts=[];context=[];series=[]
    for v in related:
        if v['review_id']==primary:continue
        if v['role']=='Single component image':
            alts.append(picture(v['review_id'],'alternate/detail candidate'))
        elif 'Context' in v['role']:
            context.append(picture(v['review_id'],'context; installation provenance unconfirmed'))
        else:
            series.append(picture(v['review_id'],'arrangement/context only; may be a close-up'))
    for rid in m.get('extra_series',[]):
        pic=picture(rid,'complete triptych/context; not an isolated component primary')
        pic['shows_complete_single_component']=False
        pic['visual_review_notes']='Three whole small panels visible; source-key left position is provisional component linkage. No single panel is isolated.'
        series.append(pic)
    specs={}
    for f in FIELD_WORDS:
        display,proposal,state=m[f]
        refs=claim_refs(cid,f)
        if m.get('extra_refs'):
            refs+=m['extra_refs']
        refs+=['worker-01 local visual review: '+(primary or 'no complete single-component image established')]
        specs[f]={'display':display,'proposal':proposal,'evidence_state':state,'basis_refs':list(dict.fromkeys(refs)),
                  'requires_owner_check':True,
                  'limits':'Proposal for owner review only. No physical verification, current stock, lead time, load rating, product approval or exact cast-to-offer match is asserted. A working guess is not a sourced specification.'}
    missing=[s.strip() for s in c['missing_specification_fields'].split(';') if s.strip()]
    missing+=['Confirm applicability to the selected image/cast and chosen finish/size.','Current individual sale decision and price approval.','Parent to attach current stable-ID metadata and existing links centrally.']
    if not primary:missing+=['Complete isolated full-view photograph; reviewed single-folder image is a crop.']
    return {
      'component_id':cid,'proposed_name':c['name'],'family':c['family'],
      'identity_evidence':[{'state':'local_visual_review_proposal','observation':m['identity']},
                           {'state':'preserved_snapshot_classification','value':c['identity_status'],'notes':c['notes'],'maker_rows':c['maker_rows'],'source_codes':c['source_codes']}],
      'source_refs':[{'source_snapshot':A['source_snapshot'],'component_id':cid,'group_refs':c['group_refs']},
                     *[{'source_ref':r} for r in m.get('extra_refs',[])]],
      'dated_supplements':m.get('dated_supplements',[]),
      'primary_example':p,'alternate_examples':alts[:8],'context_images':context,'series_images':series,
      'specifications':specs,'source_conflicts':m.get('conflicts',[]),'missing_evidence':missing,
      'platform_mapping':platform_mapping(cid),'review_ready':m.get('ready',bool(primary)),
      'handoff_notes':['Advisory packet for the interactive owner walkthrough; review_ready means usable for discussion, never listing publication or owner approval.',
                       'No user answers, shared checkpoint/register/workbook, Dropbox content or platform state were changed.',
                       'Keep historical/source values, appearance observations and WORKING GUESS proposals distinct. No set price or set weight was allocated to a member.',
                       'All six specification fields require owner checking; unknown stock and fixing capacity remain unknown.']
    }

def save(filename, ids):
    entries=[make(cid) for cid in ids]
    out={'worker_number':1,'entries':entries,
         'counts':{'assigned':len(A['component_ids']),'prepared':len(entries),
                   'review_ready_for_discussion':sum(x['review_ready'] for x in entries),
                   'complete_single_component_primaries':sum(x['primary_example']['shows_complete_single_component'] for x in entries),
                   'physical_specs_verified':0,'owner_approvals':0,'remote_calls':0,'shared_file_writes':0},
         'validation_notes':['Writes are confined to worker-01. Cached sources remain unchanged. No Dropbox API/tool calls were made.',
                             'The parent reports 74 fake adapter tests passed before its central live metadata read; this worker performed no live read or sandbox test.',
                             'Every primary marked complete was visually reviewed from cached thumbnails/contact sheets. Alternate/detail/series roles do not certify completeness.',
                             'Source values are dated/cached unless explicitly described as a worker visual observation. No current stock, exact physical-cast match or fixing load rating is inferred.',
                             'review_ready is discussion readiness only. All six fields retain requires_owner_check=true. Shared approval/checkpoint/register/workbook ownership remains with interactive session 01a144ab-1a7c-7223-a403-73a4d53d70ff.',
                             'Assignment SHA256: '+hashlib.sha256((W/'assignment.json').read_bytes()).hexdigest()],
         'prepared_utc':datetime.now(timezone.utc).isoformat()}
    (W/filename).write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
    print(filename, out['counts'])

if __name__=='__main__':
    available=[x for x in A['component_ids'] if x in MANUAL]
    save('packets.partial.json',available[:10])
    if len(available)==len(A['component_ids']):save('packets.json',A['component_ids'])
