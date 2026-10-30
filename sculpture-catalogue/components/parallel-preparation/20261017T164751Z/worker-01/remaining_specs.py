from copy import deepcopy

OLD = 'retail-2025:dated estimated each-piece white-marble standard and conditions'
TRADE = '/Users/tprice/Documents/boldstone/price list draft documents/SCULPTURE TRADE PRICE List 2025.docx (1).pdf'
RETAIL_DRAFT = '/Users/tprice/Documents/boldstone/price list draft documents/Retail PRICE List 2025.docx.pdf'
MFG = '/Users/tprice/Library/Application Support/BoldstoneImageConsistency/product-evidence-resolution-20261016T201618Z/Manufacturing_Labelled_References.json'

def fact(display, proposal, state='dated_source_claim_requires_applicability_check'):
    return display, proposal, state

def guess(display, proposal):
    return display, 'WORKING GUESS: '+proposal, 'working_guess_only'

UNKNOWN_AV = fact('No current physical stock, production readiness or individual sale decision established.',
                  'Propose “Made to order — enquire” only if the owner confirms current production and sale status; no stock quantity or lead time assigned.',
                  'unknown_owner_decision')
UNKNOWN_FIX = guess('No component-specific rear fixing record or load information found.',
                    'a concealed rear fixing is a plausible catalogue planning assumption. Maker must identify type, number, position, wall attachment and suitability; no capacity inferred.')

DATA = {}

DATA['BC-DECO-2'] = {
 'primary':'G091-1',
 'identity':'Complete verdigris-coloured long panel with multiple curled/folded relief sections; distinguish it from Decowaves 1 and from the historical white Frozen Decowaves references. G090-2 is a rear view, not a second front design.',
 'dimensions':fact('O060 describes 90 × 15 × 8 cm for each verdigris panel. No separately linked terracotta Decowaves 2 dimensions.', 'Propose 90 × 15 × 8 cm only for the linked verdigris version. WORKING GUESS for terracotta: a similar 90 × 15 cm face, with depth to measure; do not transfer O050 Decowaves 1 depth as a fact.'),
 'weight':guess('O060 approximately 14 kg is the pair total; no individual Decowaves 2 weight established.', 'roughly 6–9 kg for a similarly sized mineral-composite member, using neighbouring individual templates. This is not 14 kg divided by two.'),
 'material_finish':fact('O060 claims cast composite with a hand-applied verdigris patina. Terracotta images include a white-backed rear view; binder chemistry remains unconfirmed.', 'Use the cast-composite/verdigris wording only for the linked offer version. WORKING GUESS for terracotta: pigmented/applied surface effect over cast composite; no solid copper/bronze or universal AC730 claim.'),
 'fixing':fact('O060 says ready to hang without type, count or load detail. Rear G090-2 does not establish an installation specification.', 'WORKING GUESS: concealed rear fixing; maker must confirm actual panel fitting and wall hardware. No load rating supplied.'),
 'individual_price':guess('No linked standalone Decowaves 2 price. O060 GBP 600 is the pair.', 'GBP 300–400 as an owner-discussion seed for a standard-size coloured individual, informed by white 90 × 15 cm dated retail references of GBP 281.97 / draft GBP 337.50; finish pricing is unconfirmed. No set price allocated.'),
 'availability':UNKNOWN_AV,
 'conflicts':['White Frozen Decowaves and coloured Decowaves remain separate geometry/version records until maker confirmation.','O060 total 14 kg and GBP 600 belong to the pair; no source gives those values for this member.','Terracotta single O050 is Decowaves 1, so its 9 cm depth, 6 kg and GBP 48.44 do not become Decowaves 2 facts.'],
 'extra_refs':[OLD, RETAIL_DRAFT+':page2, Frozen Deco Waves white-standard analogy only'],
}

for cid, primary, rows, form in [
 ('BC-FDW-1','G094-1','78/80','simple alternating broad curved wave folds; FDW1 and rotated FDW3 positions'),
 ('BC-FDW-2','G095-1','79','curl/scroll and fluted arc panel FDW2'),
]:
 DATA[cid]={
  'primary':primary,
  'identity':'Complete white long relief with '+form+'. Maker reference images were checked locally; arrangement count is distinct from design count.',
  'dimensions':fact('Native O024/O025: 90 × 15 × 8 cm each part; maker rows '+rows+': approximately 90 × 15 cm, side 5–7 cm.', 'Propose 90 × 15 cm face with versioned depth: native 8 cm versus maker side 5–7 cm. Measure the actual cast; do not silently harmonise.'),
  'weight':fact('Maker template calculates 8–10 kg each. Earlier and named draft 2025 retail references estimate 8 kg each. Native 16/24 kg are arrangement weights.', 'Retain 8–10 kg as the historical individual template range and 8 kg as a dated table estimate; weigh the selected cast. No set-weight division.'),
  'material_finish':fact('Maker rows '+rows+' specify White Marble Stone Finish Jesmonite AC730 for the standard; native arrangement describes white marble stone finish.', 'Propose AC730 / white marble stone finish only for the matching historical standard; coloured Decowaves are separately scoped.'),
  'fixing':fact('Maker instruction: one small stainless-steel fixing at centre back in top third, aligned across series.', 'Use as a historical template only. Confirm actual cast and orientation, especially a rotated repeat; no wall hardware or load rating established.'),
  'individual_price':fact('Earlier 2025 white reference GBP 281.97 each; draft trade individual row GBP 168; named draft retail GBP 337.50 each. O024/O025 GBP 800/1,200 are arrangements.', 'WORKING GUESS: GBP 330–400 per standard-white individual for current owner discussion, anchored to the named draft retail reference. Owner must choose current price and whether sold separately.'),
  'availability':UNKNOWN_AV,
  'conflicts':['Native depth 8 cm differs from maker side range 5–7 cm.','Maker calculated 8–10 kg and dated table 8 kg remain estimates, not measured weight.','Trade GBP 168, earlier estimated retail GBP 281.97 and named draft retail GBP 337.50 are dated price classes/versions, not current approved retail.'],
  'extra_refs':[OLD,TRADE+(':page8, individual Frozen Deco Waves row1' if cid.endswith('1') else ':page9, individual Frozen Deco Waves row2'),RETAIL_DRAFT+':page2, Frozen Deco Waves each-piece row',MFG+':rows'+rows],
 }
 if cid.endswith('1'):
  DATA[cid]['conflicts'].append('FDW3 is a rotated/repeated position of FDW1 in the retained component model; the three-piece arrangement does not prove three distinct mould designs.')

DATA['BC-DR-WAVE1']={
 'primary':'G118-1',
 'identity':'Complete white plain-wave panel, associated with DR1 by the snapshot and compared with labelled maker row 54. DR1 and DR3 are different moulds; a generic waves photo or coloured offer does not automatically establish one-to-one mould identity.',
 'dimensions':fact('Maker DR1: approximately 35 × 20 cm, side 5–7 cm. O038: 35 × 20 × 6 cm. Recent coloured native offers: 35 × 21 × 6 cm.', 'Propose separate standard 35 × 20 cm and coloured 35 × 21 cm source versions, with depth subject to actual cast confirmation.'),
 'weight':fact('Maker calculates 3–5 kg each; O038 individual export claims 5 kg. Earlier retail estimates 4.5 kg; named retail draft 5 kg.', 'Use the historical 3–5 kg range and retain the 4.5/5 kg dated estimates. Different coloured substrates/finishes and exact DR1/DR3 allocation need confirmation.'),
 'material_finish':fact('Historical white DR1: Jesmonite AC730 / white marble stone finish. Coloured offers describe plaster/sand and faux rust-on-iron or faux verdigris/copper surface effects.', 'Do not apply AC730 to all coloured photographs or interpret metallic wording as solid metal. Propose each material/finish only after matching the exact version.'),
 'fixing':fact('Maker DR1 instruction: one small stainless-steel fixing in centre back top third.', 'Historical template only; confirm exact coloured panel and rear attachment before carrying this into its listing. No load rating established.'),
 'individual_price':fact('Cached individual offers: O004 GBP 45; O038 GBP 250; O051 GBP 35.33; O067 GBP 65.33. White references: earlier retail GBP 146.09, trade draft GBP 87, named retail draft GBP 175.', 'Retain price/version anomalies for owner review. WORKING GUESS for a newly priced standard-white member: GBP 170–220. Do not overwrite low coloured prices or exact mould uncertainty automatically.'),
 'availability':fact('O038 description says SOLD and invites a similar commission; cached offer flags elsewhere include InStock/Unlimited.', 'Use sold-versus-enquire wording only after owner confirms the exact source object and current status. Flags do not verify stock.', 'conflicting_cached_sale_signals'),
 'conflicts':['DR1 and DR3 are separately labelled maker moulds; coloured plain-wave allocation remains provisional.','35 × 20 cm historical versus 35 × 21 cm coloured native sizes.','O038 SOLD text versus cached purchase/stock metadata; do not silently call it available.','Low exported prices GBP 35.33/45/65.33 differ from GBP 250 and dated white price references; no automatic correction.'],
 'extra_refs':[OLD,TRADE+':page4, Dune Ripple individual plain-wave row1',RETAIL_DRAFT+':page1, Dune Ripple each-piece row',MFG+':rows54/56'],
}

DATA['BC-DR-SPIRAL']={
 'primary':'G111-1',
 'identity':'Complete white DR2 panel with two small curls among flowing vertical ridges, compared with labelled maker row 55. Bronze Verdigris G099 shows this spiral panel alone despite its plural group title.',
 'dimensions':fact('Maker DR2: approximately 35 × 20 cm, side 5–7 cm. O039 gold: 35 × 20 × 5 cm. Recent coloured offers: 35 × 21 × 6 cm.', 'Propose separate historical and coloured size/finish versions; do not replace O039 gold size with a different offer’s dimensions.'),
 'weight':fact('Maker DR2 calculates 3–5 kg each; O039 individual export 5 kg. Earlier retail estimates 4.5 kg; named retail draft 5 kg.', 'Keep these as dated individual claims; actual selected white or metallic cast must be weighed. Raw unitless Squarespace fields are not promoted to kilograms.'),
 'material_finish':fact('Maker white standard: AC730 / white marble stone finish. O002 says plaster/natural materials with hand-leafed gold; O052 says plaster, sand, copper surface effect; rust/verdigris offers describe other applied effects.', 'Use version-specific wording after owner confirmation. Do not infer solid gold, copper, bronze or a universal binder from appearance.'),
 'fixing':fact('Maker DR2: one small stainless-steel fixing in centre back top third. O068 rust describes a recessed fixing on the back.', 'Retain source-specific fixing descriptions; confirm type, position and orientation on the selected cast. No load rating established.'),
 'individual_price':fact('Native/cached individual prices include O002 gold GBP 299, O009 candidate verdigris GBP 45, O039 historical gold GBP 200, O052 copper GBP 40.33 and O068 rust GBP 60.33. White references GBP 146.09 earlier / GBP 87 trade / GBP 175 named retail draft.', 'Keep offers separated by source, finish and mapping strength. WORKING GUESS for newly priced white: GBP 170–220; metallic price requires owner choice.'),
 'availability':UNKNOWN_AV,
 'conflicts':['35 × 20 × 5 cm gold, 35 × 21 × 6 cm coloured, and maker 5–7 cm side are distinct claims.','O009 is a strong design candidate rather than an exact confirmed offer-to-cast match.','Very low recent native prices and historical GBP 200/299 gold prices are not silently harmonised.','G099 plural title does not imply a separate plain-wave component in that image.'],
 'extra_refs':[OLD,TRADE+':page4, Dune Ripple spiral individual row2',RETAIL_DRAFT+':page1, Dune Ripple each-piece row',MFG+':row55'],
}

DATA['BC-DR-WAVE3']={
 'primary':None,'ready':False,
 'identity':'DR3 is a separately labelled second plain-wave mould in maker row 56, distinct from DR1 row 54. Reviewed complete white triptych images show two wave forms and the spiral, but no isolated full photograph was assigned securely to DR3.',
 'dimensions':fact('Maker row 56: approximately 35 × 20 cm with 5–7 cm side.', 'Propose 35 × 20 × 5–7 cm as a historical white DR3 template only; no exact current cast measurement.'),
 'weight':fact('Maker row 56 calculates 3–5 kg each. Generic Dune Ripple retail references give 4.5 kg earlier and 5 kg in the named draft; direct DR3 applicability remains to confirm.', 'Use 3–5 kg only as the historical DR3 white-template estimate; no weight allocation from the triptych.'),
 'material_finish':fact('Maker DR3 historical standard: White Marble Stone Finish Jesmonite AC730.', 'Use only for a maker-confirmed matching white version; coloured plain-wave casts are not automatically DR3.'),
 'fixing':fact('Maker row 56: one small stainless-steel fixing at centre back top third, aligned within series.', 'Historical instruction only; confirm actual rear and mould allocation. No load rating supplied.'),
 'individual_price':guess('No directly linked current DR3 standalone offer. Generic Dune Ripple dated retail references GBP 146.09 / named draft GBP 175.', 'GBP 170–220 for a standard-white DR3 discussion seed if the owner confirms separate supply; generic price applicability is provisional, not a fraction of a set.'),
 'availability':UNKNOWN_AV,
 'conflicts':['DR3 must not merge into DR1 merely because both are plain waves.','No secure isolated photo or coloured-member allocation; generic family offers do not establish a DR3 sale unit.'],
 'extra_refs':[MFG+':rows54/56',OLD,RETAIL_DRAFT+':page1, generic Dune Ripple reference only'],
}

for cid,primary,row,orientation in [('BC-ECHO-1','G121-1',31,'concentric oval channels ending at the right edge'),('BC-ECHO-2','G123-1',32,'concentric oval channels ending at the left edge')]:
 DATA[cid]={
  'primary':primary,
  'identity':'Complete white square textured Echo Pattern panel with '+orientation+'. Paired orientations and rotated displays do not create additional designs.',
  'dimensions':fact('Maker row '+str(row)+': approximately 30 × 30 cm, side 5–7 cm. O019 white pair: 30 × 30 × 6 cm each. O072 coloured pair: 30 × 30 × 7 cm each.', 'Propose separate white depth about 6 cm and coloured depth 7 cm as source claims; measure actual cast and intended orientation.'),
  'weight':fact('Maker calculates 3–5 kg each; earlier retail/trade table 5.5 kg each; named retail draft 6.5 kg each. O019 12 kg and O072 approximately 8 kg belong to whole offers.', 'Retain the conflicting each-piece estimates; weigh each cast. Do not derive 6 kg or 4 kg from set totals.'),
  'material_finish':fact('Maker historical white: AC730 / white marble stone finish. O057 claims gypsum composite / stone finish. O072 coloured offer says plaster with copper-bronze/verdigris effect.', 'Use version-specific substrate and finish wording. The photographed coloured surface does not identify alloy or prove AC730.'),
  'fixing':fact('Maker: one small stainless-steel fixing, centre back top third. O072 describes a recessed rear fixing; G122-2 reviewed rear view shows a small metal plate/fitting but does not identify its capacity.', 'Retain historical template and offer-specific rear-fixing claim; inspect actual selected cast and wall hardware. Rotation square/diagonal needs its own orientation confirmation.'),
  'individual_price':fact('White each-piece references: GBP 182.05 earlier estimated retail, GBP 112 trade draft, GBP 225 named retail draft. O019 GBP 480 and O072 GBP 360 are pairs; O057 GBP 480 sale quantity unresolved.', 'WORKING GUESS for standard-white individual owner discussion: GBP 220–280, anchored to named draft retail. Do not turn pair prices or O057 unclear sale quantity into individual facts.'),
  'availability':fact('No current individual stock or confirmed standalone sale unit. O057 pair photograph versus ambiguous text/SKU needs owner decision.', 'Propose individual made-to-order enquiry only after sale unit and current mould readiness are confirmed.', 'unknown_sale_unit_and_stock'),
  'conflicts':['Maker 3–5 kg, earlier 5.5 kg and named retail draft 6.5 kg per piece disagree.','O057 image has a pair while text/SKU does not unambiguously specify pair quantity.','O072 wording calls a smooth/concave wave, while the mapped Echo geometry is textured concentric channels; confirm exact object and copy.','White and coloured depth/material claims remain versioned; pair totals are not individual values.'],
  'extra_refs':[OLD,TRADE+':page3, Echo Pattern individual row'+('1' if cid.endswith('1') else '2'),RETAIL_DRAFT+':page1, Echo Pattern named each-piece row',MFG+':row'+str(row)],
 }

for cid,primary,num in [('BC-EG-1','G132-1',1),('BC-EG-2','G133-1',2)]:
 DATA[cid]={
  'primary':primary,
  'identity':'Complete white Egyptian Palm '+str(num)+' with tall curved frond channels. Draft Acanthus Palms numbered images are visually matching design candidates, not proof that every size/cast is the same. Gold/black-white and scene variants stay separately scoped.',
  'dimensions':fact('O041 white pair: 50 × 30 × 7 cm each; O042 gold single same dimensions for Egyptian Palm 1. Draft Acanthus Palms matching design candidates: 60 × 30 cm each.', 'Propose versioned 50 × 30 × 7 cm native and 60 × 30 cm draft design references. Confirm alias, size and depth before applying either to the selected white photo.'),
  'weight':fact(('O042 gold single export claims 11 kg. ' if num==1 else 'O041 22 kg is the pair and is not divided. ')+'Draft Acanthus Palms matching candidate estimates 9 kg each.', 'Retain '+('11 kg gold native versus 9 kg white Acanthus candidate as different claims.' if num==1 else '9 kg only as a dated candidate alias estimate, not a measured Egyptian Palm 2 weight. WORKING GUESS: about 8–11 kg for a comparable white mineral-composite panel, pending cast/version confirmation.')),
  'material_finish':fact(('O042 describes a surface covered in gold leaf; ' if num==1 else '')+'white photo has stone-like finish, but no component-specific binder is established.', 'WORKING GUESS for white: mineral/gypsum composite with stone finish; ask maker for material card. Do not transfer historic AC730 templates from another family.'),
  'fixing':UNKNOWN_FIX,
  'individual_price':fact(('O042 gold single GBP 600, with SOLD text. ' if num==1 else 'No native standalone Egyptian Palm 2 offer linked. ')+'O041 GBP 800 is the white pair. Candidate Acanthus draft individual trade GBP 225 and named draft retail GBP 450.', 'Propose GBP 450 only as a dated white candidate-alias retail reference subject to maker identity/version confirmation; '+('GBP 600 gold is a separate sold-offer record.' if num==1 else 'WORKING GUESS current white pricing seed GBP 450–600 if owner confirms separate supply.')+' Do not divide GBP 800.'),
  'availability':fact(('O042 says SOLD; cached stock metadata can imply InStock. ' if num==1 else '')+'Current stock and standalone white sale status unverified.', 'Owner must choose sold/commission/enquire wording for each exact cast/version; no physical inventory inferred.', 'conflicting_cached_sale_signals' if num==1 else 'unknown_owner_decision'),
  'conflicts':['Egyptian Palm / Acanthus Palm alias is a visual source candidate needing owner confirmation; 50 cm and 60 cm heights cannot be silently merged.','O041 pair price/22 kg do not become individual values.']+(['O042 SOLD text conflicts with purchase/stock flags; 11 kg gold versus candidate 9 kg white does not certify either current cast.'] if num==1 else []),
  'extra_refs':[TRADE+':page5, Acanthus Palms individual row'+str(num)+'; candidate design alias',RETAIL_DRAFT+':page1, Acanthus Palms each-piece candidate alias'],
 }

DATA['BC-EG-3']={
 'primary':'G134-1',
 'identity':'Complete white three-leaf/three-broad-arc Egyptian Palm design; visibly different from the denser-channel Egyptian Palms 1/2. No matched offer or measured design specification.',
 'dimensions':guess('No component-specific size or depth established.', 'about 50 × 30 × 6–7 cm as a planning hypothesis from the visible proportions and nearby native Egyptian Palm 1/2 size. This image has no calibrated scale; the absolute size may differ.'),
 'weight':guess('No individual weight established.', 'about 7–11 kg if this is a roughly 50 × 30 cm mineral-composite version, informed by 9 kg Acanthus candidate and 11 kg native Golden Palm. Different design/cast construction can invalidate this range.'),
 'material_finish':guess('White/off-white smooth stone-like visible finish; substrate not identified.', 'cast mineral/gypsum composite with white stone finish. No chemistry or exterior-suitability certificate follows from appearance.'),
 'fixing':UNKNOWN_FIX,
 'individual_price':guess('No mapped standalone offer or individual source price.', 'GBP 400–600 as an initial owner-discussion range, using neighbouring white Palm retail candidate GBP 450 and native gold GBP 600 as analogies only. Price is not established for Three Leaves.'),
 'availability':UNKNOWN_AV,
 'conflicts':['Three Leaves is not assigned the dimensions, weight, gold finish or offer price of Egyptian Palm 1 merely because it shares a family.'],
 'extra_refs':['O041/O042:neighbouring-design analogies only',RETAIL_DRAFT+':page1, Acanthus Palms analogy only'],
}

DATA['BC-EG-4']={
 'primary':'G135-1',
 'identity':'Complete narrow, tall white extended-palm relief with long curved channels; distinguish from the shorter/broader Egyptian Palm designs. Context image is not measured installation evidence.',
 'dimensions':guess('No component-specific face dimensions or depth found.', 'roughly 90–100 × 25–30 × 5–7 cm as a low-confidence planning range from its tall narrow proportions and related long wall-relief templates. No absolute scale is recovered from the image.'),
 'weight':guess('No individual weight established.', 'roughly 10–14 kg if near the proposed long mineral-composite size; 100 × 30 cm Leaf Growth reference estimates 12 kg but is another design. Weigh this actual cast.'),
 'material_finish':guess('White/off-white smooth stone-like appearance; substrate unestablished.', 'cast mineral composite with white stone finish; gypsum versus AC730 remains to confirm.'),
 'fixing':UNKNOWN_FIX,
 'individual_price':guess('No matched individual offer or price.', 'GBP 550–800 for owner discussion if this is a long standard-white cast, using dated 100 × 30 cm references GBP 569.49 / named draft GBP 750 as other-design analogies.'),
 'availability':UNKNOWN_AV,
 'conflicts':['Do not assign the native shorter-palm 50 × 30 cm, 11 kg or GBP 600 values to this extended form.'],
 'extra_refs':[OLD,RETAIL_DRAFT+':page2, Leaf Growth analogy only'],
}

DATA['BC-EMBED-SHELLS']={
 'primary':'G141-1',
 'identity':'Complete tall narrow white textured panel with scattered shell/spiral-like bosses. Photograph establishes visible relief motifs, not whether real shells are embedded or replicated in a cast.',
 'dimensions':guess('No labelled size, depth or scale found.', 'around 100 × 25 × 5–7 cm as a planning hypothesis from its roughly four-to-one silhouette and nearby long relief templates; all numeric dimensions remain unmeasured.'),
 'weight':guess('No individual weight found.', 'around 8–12 kg if a roughly metre-long mineral-composite panel. Analogy to long 100 × 22 cm templates is weak because thickness and backing are unknown.'),
 'material_finish':guess('White/off-white coarse stone-like finish and shell-like relief visible; binder and actual inclusions unknown.', 'cast mineral composite with white textured finish and cast shell motifs. Maker must confirm whether actual shells, a moulded surface, gypsum, AC730 or another construction is used.'),
 'fixing':UNKNOWN_FIX,
 'individual_price':guess('No matched individual sale price.', 'GBP 500–700 as a tentative owner-discussion range, informed by dated long white relief reference prices GBP 432.41 / named draft GBP 550. No exact price or inclusions premium established.'),
 'availability':UNKNOWN_AV,
 'conflicts':['The name Embedded Shells does not prove actual shell inclusions, substrate or a currently manufacturable product.'],
 'extra_refs':[OLD,RETAIL_DRAFT+':page2, long-relief analogies only'],
}

DATA['BC-FACET-MOUND']={
 'primary':'G143-1',
 'identity':'Complete gold-coloured tall rectangular panel with deep angular/scooped facets. Faceted geometry is visible; no labelled physical specification or exact native offer was identified.',
 'dimensions':guess('No object-specific face dimensions or maximum depth found.', 'roughly 70 × 25 × 7–10 cm as a low-confidence planning envelope from its tall narrow proportions and pronounced relief. This is not calibrated measurement.'),
 'weight':guess('No individual weight found.', 'roughly 6–10 kg if cast mineral composite at the proposed planning size. Deep relief, hollowing and substrate make this range especially uncertain.'),
 'material_finish':guess('Gold-coloured leaf-like surface appearance; no material card for binder or metal.', 'cast mineral/gypsum composite with an applied gold-leaf or gold-effect finish. Actual leaf, alloy and exterior suitability require maker confirmation; do not claim solid gold.'),
 'fixing':UNKNOWN_FIX,
 'individual_price':guess('No linked standalone offer or sourced individual price.', 'GBP 500–800 as an initial owner pricing discussion range for a medium/large relief with a metallic finish; informed loosely by native Golden Palm GBP 600 and Timeless Spiral GBP 500. Finish labour and metal content remain unpriced.'),
 'availability':UNKNOWN_AV,
 'conflicts':['Folder Gold Leaf and visible gold colour are not a material certificate or an exact link to another gold product offer.'],
 'extra_refs':['O042/O047:other-design price analogies only'],
}

for cid,primary,number,trade_number,name in [
 ('BC-FOLD-1','G145-1',1,1,'Swan Wing Folds'),
 ('BC-FOLD-2','G146-1',2,3,'Fan Folds'),
 ('BC-FOLD-3','G147-1',3,2,'Cultivation Folds'),
 ('BC-FOLD-4','G148-1',4,4,'Fold Unfold 4'),
]:
 native = number in (1,2,3)
 DATA[cid]={
  'primary':primary,
  'identity':'Complete white Fold Unfold '+str(number)+' / '+name+' panel reviewed. Dated Foldings source row '+str(trade_number)+' matches this geometry; source numbers 2/3 differ from internal Fold Unfold 2/3 and must be crosswalked by photograph.',
  'dimensions':fact(('Native single offer: 70 × 50 × 6 cm. ' if native else 'No linked native single-offer dimensions. ')+'Draft Foldings source matched by photograph: 75 × 50 cm. Its inch column says 31.49 × 27.55 inches, inconsistent with its centimetres.', 'Propose retaining '+('70 × 50 × 6 cm native and ' if native else '')+'75 × 50 cm draft as distinct unmeasured source versions. '+('WORKING GUESS for depth of Fold 4: around 6 cm by related native members; not a sourced Fold 4 depth.' if not native else 'Measure the actual cast and resolve the source unit error.')),
  'weight':fact(('Native single-item export claims 18 kg. ' if native else '')+'Draft matched Foldings individual row estimates 14 kg.', 'Retain '+('18 kg native versus ' if native else '')+'14 kg draft as dated source estimates. Weigh the selected cast; same weight across source rows does not prove identical construction.'),
  'material_finish':fact(('Native single offer describes white marble stone finish. ' if native else 'Reviewed white/off-white stone-like appearance. ')+'No component-specific binder record identified.', 'WORKING GUESS: cast mineral composite with white stone finish; confirm gypsum versus AC730/other binder before making a material or exterior claim.'),
  'fixing':UNKNOWN_FIX,
  'individual_price':fact(('Native single offer GBP 800. ' if native else 'No linked native standalone offer. ')+'Draft matched Foldings individual trade row GBP 500 each.', ('Use GBP 800 only as a dated linked native offer and GBP 500 only as dated trade; current owner pricing required.' if native else 'WORKING GUESS: GBP 700–900 for owner discussion if supplied as a white individual, informed by related native GBP 800 members. The only direct sourced individual price here is dated trade GBP 500.')),
  'availability':UNKNOWN_AV,
  'conflicts':['Foldings source row '+str(trade_number)+' is linked by photograph to internal Fold '+str(number)+', not by number alone.','Draft 75 × 50 cm conflicts with native 70 × 50 cm for mapped offers; the draft inch conversion is internally inconsistent.']+(['Native 18 kg versus draft 14 kg.'] if native else ['No source measures the reviewed Fold 4 depth; family analogies remain guesses.'])+['Four distinct geometries remain separate; scene-study compositions do not establish manufactured variants or stock.'],
  'extra_refs':[TRADE+':pages7-8, Foldings individual row'+str(trade_number)+' matched by photo'],
 }

for cid,side in [('BC-FP-LEFT','left'),('BC-FP-RIGHT','right')]:
 DATA[cid]={
  'primary':None,'ready':False,'exclude_groups':['G156','G158'],
  'identity':'Provisional '+side+' member of the concentric rectangular Fingerprint pair in G154/G160. No complete isolated '+side+' image or production record was established. Wavy/oval G156/G158 studies differ from the concentric pair and do not certify additional manufactured stock.',
  'dimensions':fact('No component dimensions, depth or production scale established.', 'WORKING DESIGN GUESS: two complementary short rectangular relief panels. Keep numeric dimensions open until the owner confirms the physical design and a measured drawing.', 'unconfirmed_concept_no_measurement'),
  'weight':fact('No individual mass or verified physical manufacture.', 'No useful physical weight estimate can be attached to an unconfirmed study. If production is confirmed, weigh each panel separately; do not infer from neighbouring reliefs.', 'not_evaluable_until_production_identity_confirmed'),
  'material_finish':guess('Concentric studies show verdigris-like textured appearance; binder and physical status unconfirmed.', 'if commissioned as a physical relief, a patinated cast mineral-composite construction is plausible. This is a design proposal, not identification of an existing manufactured object.'),
  'fixing':fact('No rear view, fixing drawing or confirmed manufactured panel.', 'Proposed design requirement: have maker specify rear support after size, material and physical production are confirmed. No fixing count or load rating invented.', 'not_evaluable_until_production_identity_confirmed'),
  'individual_price':fact('No matched standalone offer or price for this provisional member.', 'Proposed sales treatment: quotation after owner confirms production identity, size, material and whether supplied singly. No numeric product price is certified for a study.', 'unconfirmed_concept_no_offer'),
  'availability':fact('Physical production, mould availability and stock are unconfirmed.', 'Keep as “Design study — production status to confirm” for internal review. Do not mark available, in stock or made to order without owner confirmation.', 'production_identity_unconfirmed'),
  'conflicts':['The same family contains concentric rectangular, wavy, oval and altered studies. They are not interchangeable product views.','Folder position and scene rendering do not prove a physical '+side+' panel or mould.','G155 music-room scene does not independently establish which sculpture exists or a client installation.'],
 }

DATA['BC-FOUNTAIN-EG']={
 'primary':'G163-1',
 'identity':'Complete white Egyptian Fountain Palm / Deco Fountain panel with dense flaring channels. Draft Reed Fountain photograph matches the design as a candidate alias; it does not prove a working water feature.',
 'dimensions':fact('Native O014 single: 100 × 50 × 6 cm. Draft Reed Fountain matching photograph: 100 × 50 cm.', 'Propose 100 × 50 × 6 cm as the dated native version; confirm Reed Fountain alias and selected cast before adoption.'),
 'weight':fact('Native O014 single export claims 15 kg; draft Reed Fountain matched candidate estimates 16 kg.', 'Retain 15 kg native versus 16 kg draft; weigh actual selected panel.'),
 'material_finish':fact('O014 describes white marble stone finish. Bronze/verdigris images have metallic-coloured appearance; no exact binder for those casts established.', 'WORKING GUESS: cast mineral composite with white stone finish for primary; patinated composite for coloured variant. Do not infer solid bronze or water-service performance.'),
 'fixing':UNKNOWN_FIX,
 'individual_price':fact('Cached native O014 single GBP 900. Draft Reed Fountain matched candidate individual trade GBP 625.', 'Use GBP 900 as the dated native offer claim and GBP 625 as dated trade candidate reference. Current price/version requires owner approval; no pumping/water-feature equipment included by name alone.'),
 'availability':UNKNOWN_AV,
 'conflicts':['Fountain Palm Egyptian / Deco Fountain / Reed Fountain naming is a visual alias candidate requiring owner confirmation.','Native 15 kg versus draft 16 kg; native retail GBP 900 and draft trade GBP 625 have different price classes.','Fountain in a name is not proof of functional plumbing, a pump, waterproofing or a commissioned installation.'],
 'extra_refs':[TRADE+':page11, Reed Fountain photograph and individual row'],
}

DATA['BC-FOUNTAIN-MED']={
 'primary':'G164-1',
 'identity':'Complete white Mediterranean Fountain Palm panel with fewer, broader curved branches than Egyptian Fountain. It is a separate design despite appearing with Egyptian Fountain in G166.',
 'dimensions':guess('No component-specific dimensions or depth established.', 'about 100 × 50 × 6 cm as a planning hypothesis from similar proportions and the neighbouring native Egyptian Fountain size; this is not a measurement or a source claim for Mediterranean.'),
 'weight':guess('No individual weight established.', 'roughly 14–18 kg if a comparable 100 × 50 cm mineral-composite version, using Egyptian Fountain 15/16 kg dated values as other-design analogies.'),
 'material_finish':guess('White/off-white smooth stone-like finish in reviewed images; no substrate record.', 'cast mineral/gypsum composite with white stone finish; maker must confirm binder, coatings and intended environment.'),
 'fixing':UNKNOWN_FIX,
 'individual_price':guess('No mapped standalone Mediterranean Fountain offer or individual price.', 'GBP 800–1,000 for initial owner discussion, informed by other-design native Deco Fountain GBP 900. Do not allocate a set price or claim the Reed Fountain trade row is this design.'),
 'availability':UNKNOWN_AV,
 'conflicts':['Native O014 and draft Reed Fountain photo match the Egyptian design, not a direct Mediterranean specification.','Two Fountain Palms composition is context, not proof that the two members share dimensions, weight or fixing.'],
 'extra_refs':['O014:Egyptian Fountain analogy only',TRADE+':page11, Reed Fountain other-design analogy only'],
}

DATA['BC-FFS-1']={
 'primary':None,'ready':False,'extra_series':['F02','F06'],
 'identity':'Maker row 70 identifies three separate small moulds FFS1/FFS2/FFS3 left to right. Complete triptych images reviewed locally support that source-key order, but all 33 cached G172 assets are triptychs or crops; no isolated complete FFS1 photograph was established.',
 'dimensions':fact('Maker row 70: each approximately 70 × 15 cm with side 5–7 cm. 2016 brochure and draft Frozen Fish Series references say 70 × 15 cm each.', 'Propose 70 × 15 × 5–7 cm only as the historical small-white FFS1 template; confirm source-key left position and exact cast. Long 100 × 22 cm Frozen Fish is a distinct size.'),
 'weight':fact('Maker row 70 calculates 4–6 kg each. Earlier 2025 retail and draft trade table estimate 6.5 kg each; named retail draft says 6 kg each.', 'Retain all dated estimates; measure the actual left member. Zero draft export weight is unfilled data, not a physical weight.'),
 'material_finish':fact('Maker small-white standard: White Marble Stone Finish Jesmonite AC730.', 'Propose only for maker-confirmed matching small-white FFS1; coloured Frozen Fish and long versions remain separately scoped.'),
 'fixing':fact('Maker row 70: one small stainless-steel fixing for each panel, centre back top third, aligned across series.', 'Historical instruction only; confirm actual left cast, wall hardware and mould identity. No load rating supplied.'),
 'individual_price':fact('Earlier white reference GBP 220.99 each. Draft trade p6 explicitly prices numbered member 1 at GBP 131; named draft retail p2 generic Frozen Fish row GBP 262.50 each. Historical SH-DRAFT price 0 is unfilled.', 'WORKING GUESS for current standard-white discussion: GBP 260–320 individually, using named draft retail as a seed. No price is divided from the triptych and zero is not a free offer.'),
 'availability':fact('SH-DRAFT is a historical blank-SKU/blank-description Shopify Frozen Fish triptych export; this worker did not inspect live state. Current stock and sale decision unestablished.', 'Keep status “owner to confirm — historical draft evidence only”. Do not infer stock or current platform identity from draft price/weight zero.', 'historical_draft_not_current_stock'),
 'conflicts':['Small 70 × 15 cm FFS members must not inherit long 100 × 22 cm values.','Maker 4–6 kg versus old/trade 6.5 kg versus named draft retail 6 kg.','No isolated full FFS1 image; selected historical Shopify hero is a triptych detail crop.','SH-DRAFT blank fields/zero price and zero weight are not product specifications or verified live status.'],
 'extra_refs':[OLD,TRADE+':page6, Frozen Fish individual row1',RETAIL_DRAFT+':page2, Frozen Fish each-piece row',MFG+':row70','brochure-2016-inside-a:page1, Frozen Fish 3 caption 70 × 15 cm each'],
}


def add_first_ten_sources(manual):
    # Supplement the preserved first-ten partial without deleting its dated claims.
    extra = {
     'BC-CR-SPIRAL':('Trade draft p3 explicitly gives spiral row1 30 × 30 cm, 5.5 kg, GBP 112 trade each.',TRADE+':page3, Cupring & Spiral row1'),
     'BC-CR-RING':('Trade draft p3 explicitly gives cup-ring row2 30 × 30 cm, 5.5 kg, GBP 112 trade each.',TRADE+':page3, Cupring & Spiral row2'),
     'BC-DDR-WAVE':('Trade draft p10 individually prices 100 × 22 cm numbered wave members at GBP 275 each with 10 kg estimate; named retail draft p2 gives GBP 550 each at 10 kg. These differ from earlier GBP 432.41 reference.',TRADE+':page10; '+RETAIL_DRAFT+':page2'),
     'BC-DDR-SPIRAL':('Trade draft p10 individually prices 100 × 22 cm spiral member2 at GBP 275, 10 kg; named retail draft p2 gives GBP 550 each at 10 kg. Preserve earlier GBP 432.41 separately.',TRADE+':page10; '+RETAIL_DRAFT+':page2'),
     'BC-DP-PALM1':('Grecian Palms matched photo in trade draft p5 row2: 45 × 40 cm, 8 kg, GBP 225 trade each. Named retail draft p1: 45 × 40 cm, 8 kg, GBP 450 each. These are source versions distinct from earlier GBP 345.28 and native GBP 600.',TRADE+':page5, Grecian row2; '+RETAIL_DRAFT+':page1'),
     'BC-DP-PALM2':('Grecian Palms matched photo in trade draft p5 row3: 45 × 40 cm, 8 kg, GBP 225 trade each. Named retail draft p1: 45 × 40 cm, 8 kg, GBP 450 each. These are source versions distinct from earlier GBP 345.28 and native GBP 600.',TRADE+':page5, Grecian row3; '+RETAIL_DRAFT+':page1'),
     'BC-DP-SPIRAL':('Grecian Spiral matched photo in trade draft p5 row1: 45 × 40 cm, 8 kg, GBP 225 trade each; named retail draft p1: GBP 450 each, 8 kg. Preserve earlier GBP 345.28 and native size/finish offers separately.',TRADE+':page5, Grecian row1; '+RETAIL_DRAFT+':page1'),
    }
    for cid,(text,ref) in extra.items():
        m=manual[cid]
        m.setdefault('extra_refs',[]).append(ref)
        m.setdefault('dated_supplements',[]).append({'evidence_state':'visually_checked_dated_draft','claim':text,'source_ref':ref})
        m['conflicts'].append(text)
    m=manual['BC-CORAL']
    m['weight']=guess('No sourced individual Coral Spiral weight. Other 55 × 55 cm designs estimate 12 kg in the earlier table and 18 kg in the named retail draft.', 'roughly 10–18 kg if comparable mineral composite; this broad size-based analogy is not a measured Coral Spiral mass.')
    m['individual_price']=guess('No sourced individual Coral Spiral price. Other 55 × 55 cm designs have dated retail references GBP 562.36 earlier / GBP 756.25 named draft.', 'GBP 550–800 as a loose owner-discussion range for standard white if the dated 55 × 55 cm design size applies. It is not a quote or approved price.')
    m['extra_refs'].append(RETAIL_DRAFT+':page1, 55 × 55 cm other-design analogy only')
    m['conflicts'].append('Named retail draft estimates 18 kg and GBP 756.25 for other 55 × 55 cm designs, versus earlier 12 kg / GBP 562.36; neither is a direct Coral Spiral specification.')

