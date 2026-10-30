import json
import hashlib
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

W = Path(__file__).resolve().parent
X = json.loads((W / 'assignment.json').read_text())
A = {a['id']: a for a in X['assets']}
G = {g['group_ref']: g for g in X['groups']}
P = {p['component_id']: p for p in json.loads((W / 'primary_candidates.json').read_text())}
O = {o['offer_ref']: o for o in X['platform_records']}
S = Path('/Users/tprice/Library/Application Support/BoldstoneImageConsistency/product-evidence-resolution-20261016T201618Z')

def spec(display, proposal, state, refs, limits):
    return {
        'display': display,
        'proposal': 'WORKING PROPOSAL FOR OWNER CHECK: ' + proposal,
        'evidence_state': state,
        'basis_refs': refs,
        'requires_owner_check': True,
        'limits': limits,
    }

def claim_refs(cid, fields):
    return [c['claim_id'] + ' | ' + c['source_ref'] for c in X['claims'] if c['component_id'] == cid and c['field'] in fields]

def maker_refs(cid):
    return claim_refs(cid, ['Manufacturing component dimensions / side depth', 'Manufacturing description', 'Conditional component weight', 'Fixings instruction'])

def asset_record(fid, reason, role=None, complete=None, reviewed=False):
    a = A[fid]
    path = a.get('full')
    path = path if path and Path(path).is_file() else a['thumb']
    z = {
        'file_id': a['id'], 'folder_id': a['folder_id'], 'preview_path': path,
        'thumbnail_path': a.get('thumb'), 'historical_path': a['path'],
        'content_hash_snapshot': a.get('content_hash'), 'selection_reason': reason,
        'visual_reviewed_this_worker': reviewed,
        'metadata_state': 'Frozen local assignment; current metadata and links must be rebound by root reader',
    }
    if role:
        z['role'] = role
    if complete is not None:
        z['shows_complete_single_component'] = complete
    return z

def source_doc(ref):
    label = ref.split(':')[0]
    doc = next((d for d in X['document_sources'] if d['label'] == label), None)
    if not doc:
        return {'ref': ref, 'status': 'Logical reference retained from frozen evidence; see assignment claims/groups'}
    return {
        'ref': ref, 'local_path': doc['local_path'],
        'retrieved_utc': doc.get('retrieved_utc'),
        'file_id': doc['head']['id'], 'revision_snapshot': doc['head']['rev'],
        'sha256': doc['fingerprint'].get('backup_sha256'),
        'date_limits': 'Retrieval date is not the document publication date',
    }

VISUAL = {
 'BC-LUCIANO-1': 'A tight circular-relief surface detail. It cannot locate the left panel by itself. The maker project page separately shows the complete three-part screen.',
 'BC-LUCIANO-2': 'A tight circular-relief surface detail. It cannot locate the centre panel by itself. The maker project page separately shows the complete three-part screen.',
 'BC-LUCIANO-3': 'A tight circular-relief surface detail. It cannot locate the right panel by itself. The maker project page separately shows the complete three-part screen.',
 'BC-MS-1': 'Complete portrait panel with smooth broad upper curve flowing into a smaller lower spiral, matching labelled maker MS1; selected an uncropped timber-wall photograph instead of the first cropped view.',
 'BC-MS-2': 'Complete portrait panel with broad smooth upper arc and large lower spiral; matches labelled MS2. The native O040 hero is this member.',
 'BC-MS-3': 'Portrait relief with curved upper section and pronounced lower spiral matching labelled MS3; small foliage at the bottom of the photographed display does not establish installation provenance.',
 'BC-MOON-WATER': 'Complete near-square rectangular backing with a circular concave bowl/rim relief; the overall object is not a free-standing circular disc. Selected full brick-wall view instead of the original detail.',
 'BC-MOONWAVE': 'One complete landscape panel with a broad circular/curved central form and wave/crescent profile; O016 provides the separate Moonwave retail alias.',
 'BC-PANEL-CURVES': 'Complete square fan-and-arc relief on grass, with a pale gold/copper/pink/grey appearance. No chemical finish, genuine gold leaf, sale identity, or master/mould/cast status follows from its appearance.',
 'BC-PLANT': 'Complete compact panel with diagonally raised seed/leaf-like forms. The 2016 Plant Form price-list name/size is a documentary candidate, not a measured scale for this photo.',
 'BC-RW-SPIRAL1': 'Complete square textured panel, lower-left spiral and curved ripples; labelled maker RW4 matches Dropbox Raked Spiral 1.',
 'BC-RW-WAVE': 'Complete square textured panel with wavy parallel bands. Maker RW1 and RW3 are the same relief in different orientations; retain positions without creating a second mould.',
 'BC-RW-SPIRAL3': 'Complete square textured panel with large circular spiral, matching maker RW2; Dropbox calls this Raked Spiral 3.',
 'BC-RIYADH-1': 'A complete oblique workshop view of a long rippled wave panel, compatible with the Dune Ripple project panels pictured in various-composites p1. The local number 1 is not a maker mould code.',
 'BC-RIYADH-2': 'One complete long shell/spiral panel photographed horizontally in a workshop. Selected it over the tight spiral detail. The source portfolio also shows tall project panels; orientation does not create another design.',
 'BC-RIYADH-3': 'A complete tall narrow plain arc/moon panel. Related plain panels occur at the right of project workshop scenes; exact as-built identity and source-dimension applicability need the owner.',
 'BC-RUST-PANEL': 'One complete approximately square flat panel photographed obliquely, with turquoise and rust/brown areas. Native offer O066 supplies a claimed substrate and dimensions beyond what pixels establish.',
 'BC-SEAWEED-ROUGH': 'One complete landscape ripple relief with textured/sandy bands; distinguish it from the smoother O012 design. O026 calls this Fossil Sand Ripple.',
 'BC-SEAWEED-SMOOTH': 'One complete landscape panel with smoother flowing ripple bands. O012 calls this Smooth Sand Ripple; two-panel arrangements remain contextual.',
 'BC-SHELL-B1': 'One complete portrait textured shell/crescent relief matching maker BSM1. Chose full front instead of the tight shell detail; water-feature views are a separate configuration.',
 'BC-SHELL-B2': 'One complete portrait shell/crescent relief with an outlet visible in the spiral. Its shell geometry differs from BSM1; do not borrow BSM1 specifications as facts.',
 'BC-SHELL-I': 'One complete landscape shell within a crescent, matching labelled Islington ISM1. Dropbox Battersea Shellmoon 3 is a historical media alias.',
 'BC-SPICE': 'One complete square textured panel with seed/stick/shard-like relief forms. These may be cast impressions; the image does not prove actual organic spices or inclusions.',
 'BC-SF-1': 'Complete square left panel with a large partial circle and small fish-like raised forms; matches the left SF1 position of maker row89.',
 'BC-SF-2': 'Complete square right panel with a partial spiral at the design boundary and fish-like raised forms. The edge of the motif is intentional; selected a full panel photograph over a tight detail.',
 'BC-SM-SPIRAL': 'One complete square spiral relief against brick, matching SM1. Selected full frame rather than the first close-up.',
 'BC-SM-QUARTER': 'One complete square panel with a smooth crescent/quarter-moon arc, matching the Quarter Moon component in maker row49. QM2 is the rotated counterpart.',
 'BC-STRATA': 'One complete square ledged/stratified relief in turquoise/brown appearance. This G326 image is the captured O062 primary, chosen instead of blue-wash G325 to preserve variant scope.',
 'BC-TEXTURE-WIDE': 'One complete broad rectangular blue/brown/rust-coloured panel in a workshop; selected a full view from the 109-image group instead of a texture-only crop. Formal model and construction remain unknown.',
 'BC-TEXTURE-TALL': 'One complete tall rectangular panel with dark vertical streaks and blue-grey areas, photographed sideways in the cached image. Formal model, coating and construction remain unknown.',
 'BC-AZURE': 'One complete very tall narrow blue/white marbled panel against masonry, matching O073. The other wavy panel in room scenes is a different unallocated object.',
 'BC-WBMS-WAVE': 'One complete square spiral-wave panel, matching labelled WBMS2. Dropbox Wave and Moonshadow 1 is not the manufacturer number.',
 'BC-WBMS-MOON': 'One complete square smooth crescent panel, matching the outer WBMS1/WBMS3 form. Rotation changes position but not the underlying design.',
 'BC-MIX-SPIRALS': 'A tall narrow strip carrying five repeated spiral motifs is fully visible near the right in a mixed workshop frame. The frame includes several other sculptures; it is not a complete isolated individual example or proof of a sale unit.',
}

SPECIAL = {}

def put(cid, **kwargs):
    SPECIAL[cid] = kwargs

# Each tuple is factual display, labelled proposal, evidence state, logical sources, limits.
for num, pos in [(1,'left'),(2,'centre'),(3,'right')]:
    put('BC-LUCIANO-'+str(num),
        dimensions=('January 2006 project: 215 × 180 cm overall, three-part screen; individual '+pos+' panel dimensions absent.', 'About 215 × 60 cm for this positional panel only IF the three panels are equal width and the overall 180 cm includes no gaps; depth about 5–7 cm is an unverified design allowance.', 'PROJECT_TOTAL_ONLY_PLUS_CONDITIONAL_GUESS', ['luciano-garden:p1'], 'The overall screen is not an individual measurement; the photo suggests separate vertical panels but not calibrated widths or depth.'),
        weight=('No individual mass record.', 'No defensible numeric estimate of this historic panel until its thickness/frame is known. Draft “individual weight to be weighed”; if costing a new version, use a provisional 15–30 kg handling allowance per panel only.', 'UNKNOWN_ACTUAL_MASS_DESIGN_ALLOWANCE_ONLY', ['luciano-garden:p1'], 'A planning allowance is not an actual weight, a stock record, a transport limit or fixing load.'),
        material_finish=('Maker project page specifies fibrous cement and silver-sand surface texture for the three-part Luciano/Chelsea screen, January 2006.', 'Use that dated project specification conditionally for the '+pos+' part; confirm the actual part and any proposed reproduction. Treat pink/green illumination as lighting.', 'DATED_PROJECT_MATERIAL_NOT_OBJECT_TEST', ['luciano-garden:p1'], 'Not a specification for every Moonshell Lava finish; no exact binder/reinforcement or new-cast recipe established.'),
        fixing=('No per-panel rear fixing or frame record.', 'A concealed supporting frame or two rear attachment positions is a design proposal to review against the actual screen construction; keep the public fixing statement pending.', 'WORKING_DESIGN_PROPOSAL_ONLY', ['luciano-garden:p1'], 'No fixing type/count, wall anchor, hardware rating or load capacity verified.'),
        individual_price=('No standalone panel offer or quote in the supplied records.', 'Commission enquiry / price on request for this historical part. If the owner wants a new individual-panel budget to correct, suggest £1,500–2,500 as an explicit new commission hypothesis, not a division of a screen price.', 'WORKING_COMMERCIAL_GUESS_ONLY', ['luciano-garden:p1','retail-2025:70×50 size analogy'], 'No historical/current quote or permission to sell this panel; standard retail size is only a rough scale comparator.'),
        availability=('Historic private-residence project record; no current physical stock/ownership or reproduction decision.', 'Archive commission; offer new bespoke work by enquiry only if the maker approves reproduction, and quote lead time separately.', 'NO_CURRENT_STOCK_EVIDENCE', ['luciano-garden:p1'], 'This is a proposed catalogue policy, not an assertion that the original is available.'),
        conflicts=['The shared detail images do not distinguish left/centre/right; positional labels are local proposals, not certified mould numbers.', '215 × 180 cm belongs to the whole screen. Equal-width 215 × 60 cm is explicitly hypothetical.'],
        extra_sources=['luciano-garden:p1'],
        handoff=['Use the complete project page as three-panel context, not as three isolated product photographs.', 'Do not merge any other Moonshell Lava parts or infer ownership/stock from the named 2006 commission.'])

put('BC-MOON-WATER',
    dimensions=('Maker row103: approximately 51 × 48 cm, side 5–7 cm. 2025 retail table: 50.5 × 47.5 cm. Captured O059 copy says 50 cm diameter × 8 cm.', 'Use approximately 51 × 48 cm with 5–7 cm historical side-depth allowance as the leading rectangular-object draft, retaining the 2025 50.5 × 47.5 cm variation for owner correction.', 'CONFLICTING_MAKER_RETAIL_NATIVE_CLAIMS', ['manufacture-stevensons:Sheet1!row103','retail-2025:50.5×47.5','O059'], 'The source photo shows a rectangular backing; neither a circular-disc dimension nor an 8 cm depth is accepted as measured.'),
    weight=('Maker white AC730 template: calculated 10–12 kg each; 2025 retail estimate 10 kg each.', 'Draft approximately 10–12 kg for a matching white AC730 version, subject to separate actual weighing.', 'HISTORICAL_CALCULATED_EACH_COMPONENT', ['manufacture-stevensons:Sheet1!row103','retail-2025:50.5×47.5'], 'Conditional on standard white AC730 construction; no weighed current object.'),
    material_finish=('Maker row103 says white marble stone finish Jesmonite AC730. Captured O059 native/public copy instead says gypsum composite, stone finish.', 'White stone appearance; maker to choose/confirm the applicable construction. Keep AC730 historical template and gypsum offer text as separate unresolved assertions.', 'CONFLICTING_MATERIAL_ASSERTIONS', ['manufacture-stevensons:Sheet1!row103','O059'], 'A linked hero image does not validate the offer copy or establish chemical composition.'),
    fixing=('Maker row103 specifies two stainless steel fixings; O059 only says ready to hang.', 'Use two embedded stainless fixings as the historical candidate, pending a rear photograph and actual hanging instructions.', 'MAKER_TEMPLATE_NOT_BACK_INSPECTION', ['manufacture-stevensons:Sheet1!row103','O059'], 'No anchor choice, size selection or load rating established.'),
    conflicts=['Moonwater retail hero links to MWC1, but circular-disc wording and gypsum copy conflict with the rectangular maker template.', 'Do not merge Moon Water Catcher with Moonwave or Moon & Wave by alias similarity.'])

put('BC-MOONWAVE',
    dimensions=('Captured O016 single-offer claim: 74 × 35 × 9 cm.', 'Draft 74 cm wide × 35 cm high × 9 cm deep for this landscape example, after the owner confirms dimension order and the measured cast.', 'NATIVE_SINGLE_OFFER_CLAIM', ['O016'], 'The stated order is not explicitly encoded as H/W/D; no maker row or measured object linked.'),
    weight=('Captured native single-offer export claim: 18 kg.', 'Use approximately 18 kg as an unverified source-based draft for the matching version; weigh independently.', 'NATIVE_SINGLE_OFFER_UNWEIGHED', ['O016'], 'Not a measured current cast and not a generic mass for similarly named designs.'),
    material_finish=('O016 describes white marble stone finish; no object-specific binder/substrate certificate.', 'Cast stone/composite relief with a white stone appearance; confirm the actual formulation before naming a binder.', 'DOCUMENTED_APPEARANCE_CHEMISTRY_UNKNOWN', ['O016'], 'Do not infer Jesmonite, gypsum, real marble or a particular coating solely from the image or related series.'),
    fixing=('No object-specific rear/hardware record.', 'Two concealed rear hanging positions are a working proposal for the long panel; obtain the actual rear photograph and fixing instructions.', 'WORKING_DESIGN_PROPOSAL_ONLY', ['O016'], 'No count/type or load rating verified; native “garden wall” suitability is a source assertion.'),
    conflicts=['Moonwave is the mapped O016 retail design; no manufacturing code is established. Do not import dimensions or chemistry from Moon & Wave, Moonshadow or Moon Water Catcher.'])

put('BC-PANEL-CURVES',
    dimensions=('No calibrated component dimensions.', 'About 30 × 30 cm, depth 5–7 cm, as a clearly unmeasured proposed standard size for the visible square form.', 'WORKING_SIZE_GUESS_ONLY', ['G278','retail-2025:30×30 size analogy'], 'Square proportion is visible; absolute scale is a proposed design assumption only.'),
    weight=('No component mass record.', 'Approximately 3–6 kg only as a planning guess if the owner chooses a small cast-composite 30 cm version.', 'WORKING_MASS_GUESS_ONLY', ['G278','retail-2025:30×30 size analogy'], 'Actual construction and mass unknown; not usable as a fixing or transport value.'),
    material_finish=('Multicolour gold-toned/copper/pink/grey appearance; G277 beige process form has unresolved master/mould/cast role.', 'Draft “multicolour patina effect on cast relief; substrate and recipe to be confirmed” if the owner confirms a saleable cast. Keep beige as process evidence.', 'VISIBLE_APPEARANCE_ONLY_PRODUCTION_UNKNOWN', ['G277','G278'], 'No solid metal, gold leaf, oxidation chemistry or completed manufacture certified.'),
    fixing=('No rear fixing record.', 'For a proposed 30 cm cast, one embedded stainless hanging point is a working design candidate; confirm the actual back and mass first.', 'WORKING_DESIGN_PROPOSAL_ONLY', ['manufacture-stevensons:30 cm templates by analogy','G278'], 'Not a verified fixing, count, anchor or load rating.'),
    individual_price=('No native standalone offer.', 'If confirmed as a saleable 30 cm cast with decorative finish, suggest £200–350 as a working asking range for owner correction.', 'WORKING_COMMERCIAL_GUESS_ONLY', ['retail-2025:30×30 size analogy','G278'], '£182.05 is the dated standard-size white reference, not this model/finish quote; no approved price.'),
    availability=('Production role and retail alias unresolved.', 'Hold as a design/sample record; new commission enquiry only after the owner confirms the model and production status.', 'NO_CURRENT_STOCK_EVIDENCE', ['G277','G278'], 'No finished stock, current manufacture or lead time established.'),
    conflicts=['The beige workshop form may be a master, mould or cast. It cannot establish a retail finish.', 'Gold-toned pixels do not prove gold leaf or solid metal.'])

put('BC-PLANT',
    dimensions=('2016 maker trade-list standard Plant Form appears in the 30 × 30 cm size section; no measured scale or depth bound to the selected photo.', '30 × 30 cm, depth about 5–7 cm, as a tentative standard-size draft; have the owner confirm that the photographed version is this listed standard.', 'DATED_NAME_SIZE_CANDIDATE_PLUS_DEPTH_GUESS', ['trade-2016:30×30 Plant Form','G279'], 'The cached extracted list supplies name and size section, not a source-to-image ruler measurement.'),
    weight=('No object-specific mass.', 'Approximately 3–5 kg for a proposed 30 cm cast, by analogy with similar standard small cast reliefs.', 'WORKING_MASS_GUESS_ONLY', ['manufacture-stevensons:30 cm templates by analogy','G279'], 'Actual substrate, depth and mass remain unknown; do not treat this as an AC730 certification.'),
    material_finish=('Pale white/stone-like surface appearance; no object-specific substrate record.', 'Cast composite with a white stone effect as a proposed reproduction specification; maker to confirm actual chemistry and whether this image is a finished cast.', 'VISIBLE_APPEARANCE_ONLY', ['G279','G280'], 'A colour grouping is not a material certificate.'),
    fixing=('No component rear record.', 'One concealed rear hanging point is a working candidate if the 30 cm small-cast version is confirmed.', 'WORKING_DESIGN_PROPOSAL_ONLY', ['G279','manufacture-stevensons:30 cm templates by analogy'], 'Actual hardware and load rating unknown.'),
    individual_price=('2016 trade list has a 140.00 single Plant Form entry in the 30 cm section; no current retail offer mapped.', 'For a standard 30 cm white cast, suggest £180–250 retail as an explicitly new working asking range.', 'DATED_TRADE_REFERENCE_NEW_RETAIL_GUESS', ['trade-2016:30×30 Plant Form','retail-2025:30×30 size analogy'], '2016 trade pricing and 2025 generic retail sizing are separate dated comparators; not a current quote.'),
    extra_sources=['trade-2016:30×30 Plant Form'],
    conflicts=['A historical price-list name/size section supports a candidate standard, but the selected photograph has no calibrated scale.'])

for cid in ['BC-RW-SPIRAL1','BC-RW-WAVE','BC-RW-SPIRAL3']:
    put(cid,
        dimensions=('Maker component row(s): approximately 30 × 30 cm, side 5–7 cm. O017 describes each part as 30 × 30 × 6 cm.', 'Draft one 30 × 30 cm component, with 6 cm nominal depth and the historical 5–7 cm range retained for actual measurement.', 'MAKER_EACH_COMPONENT_AND_NATIVE_EACH_CLAIM', ['O017'] + maker_refs(cid), 'The 30 × 120 cm overall belongs to the four-position arrangement; no complete-set dimension is assigned to this component.'),
        weight=('Maker standard white AC730 calculation: 3–5 kg each. 2025 retail small standard estimate: 5.5 kg each. Native 24 kg belongs to O017 four-position set.', 'Use 3–5 kg as the maker-template draft with the separate 5.5 kg retail estimate visible for owner correction; weigh the actual component.', 'CONFLICTING_DATED_EACH_WEIGHT_ESTIMATES', ['retail-2025:30×30'] + claim_refs(cid,['Conditional component weight']), 'No division of the 24 kg set; no averaging or measured cast claim.'),
        individual_price=('No standalone price established by O017; captured £800 belongs to four positions. 2025 retail lists £182.05 per standard 30 cm piece.', 'Suggest £185–225 per matching standard white component, explicitly based on the dated per-piece reference and owner costing.', 'DATED_PER_PIECE_REFERENCE_NEW_PRICE_GUESS', ['retail-2025:30×30','O017'], 'Not £800 divided by four; decorative finishes, delivery and water features require separate quotes.'),
        conflicts=['Dropbox names Raked Spiral 1/2/3 correspond to maker RW4/RW1(or rotated RW3)/RW2, not matching numeric suffixes.', 'The O017 arrangement has four positions but three working design identities; rotated RW1/RW3 positions are retained without creating another mould.', 'Maker 3–5 kg each and retail 5.5 kg each differ; retain both and obtain an actual weight.'])

for num in [1,2,3]:
    cid='BC-RIYADH-'+str(num)
    project_group={1:'G291',2:'G292',3:'G294'}[num]
    put(cid,
        dimensions=('Undated maker various-composites p1 states 100 × 275 cm each for Dune Ripple and Shellmoon project panels; exact linkage for this local member remains provisional.', 'Tentatively 275 cm high × 100 cm wide, depth about 5–7 cm as a new allowance, only if the owner confirms this pictured local member belongs to that full project panel specification.', 'UNDATED_PROJECT_EACH_PANEL_CLAIM_MAPPING_PROVISIONAL', ['various-composites:p1',project_group], 'The source supplies each-panel dimensions, not a total to divide. The selected photo may be rotated, a sample, or a variant; depth is unsourced.'),
        weight=('No individual mass, thickness, frame or construction record.', 'Actual mass remains unknown. If an initial number is needed for a new engineered panel, use 30–80 kg per panel only as a broad planning hypothesis to replace after construction is chosen.', 'UNKNOWN_ACTUAL_MASS_WORKING_ALLOWANCE_ONLY', ['various-composites:p1'], 'No density, reinforcement or substrate is certified. This range cannot support lifting, mounting or shipping decisions.'),
        material_finish=('Project portfolio captions identify silver-sand surface for Dune Ripple/Shellmoon panels and a white-marble Shellmoon detail; no formulation or finish record bound to this individual.', 'Silver-sand textured appearance for the pictured project version, conditionally; propose an engineered cast panel with substrate and support structure to be specified by the maker.', 'PROJECT_SURFACE_CLAIM_INDIVIDUAL_CHEMISTRY_UNKNOWN', ['various-composites:p1'], 'Do not import Luciano fibrous cement or a standard small Jesmonite template; white and silver-sand project views may be different versions.'),
        fixing=('Workshop supports/rods are visible in some source scenes; final wall fixing system absent.', 'Concealed engineered frame/rail attachment is a design proposal for owner/maker review; keep public fixing details pending a drawing.', 'WORKING_DESIGN_PROPOSAL_ONLY', ['various-composites:p1'], 'Workshop staging is not a certified final installation or load test; no hardware rating asserted.'),
        individual_price=('No standalone retail offer or bespoke quotation linked.', 'Price on request for the historical project part. For a new full-size bespoke panel, suggest £3,000–5,000 as a plainly tentative starting budget for the owner to correct.', 'WORKING_COMMERCIAL_GUESS_ONLY', ['various-composites:p1','retail-2025:70×50 size analogy'], 'Not a historical/current quote, not a split of a project price, and not a claim that this original is for sale.'),
        availability=('Historic project/workshop evidence; current stock and production status unknown.', 'Archive bespoke project; offer a new commission enquiry only after identity, construction, reproduction and lead time are confirmed.', 'NO_CURRENT_STOCK_EVIDENCE', ['various-composites:p1'], 'No claim that the Riyadh-installed or workshop object is owned, available, or currently made.'),
        extra_sources=['various-composites:p1'],
        conflicts=['Local Riyadh 1/2/3 labels are positional/visual working identifiers, not certified retail codes.', 'Project each-panel 100 × 275 cm is a candidate binding to this image, not a measured specification of every Riyadh-named asset.'],
        handoff=['Review the rendered various-composites p1 alongside the full primary before accepting the 100 × 275 cm project binding.', 'Do not infer exact client-location provenance for the individual primary solely from the family folder.'])

put('BC-RUST-PANEL',
    dimensions=('O066 native descriptive claim: 31.5 × 31.5 × 4 cm, despite the register summary leaving dimensions open.', 'Use 31.5 × 31.5 × 4 cm as an unverified native draft for this mapped panel; measure the actual face and depth.', 'NATIVE_SINGLE_OFFER_TEXT_CLAIM', ['O066','SS Wall Products!row71/Description/paragraph1/sentence2'], 'Source text is not a calibrated photo or physical check.'),
    weight=('No trustworthy individual mass record.', 'About 0.8–2 kg as a working guess for a small wood-board-based textured panel, subject to separate weighing.', 'WORKING_MASS_GUESS_ONLY', ['O066'], 'Depends on claimed board construction, thickness and coatings; not a verified load.'),
    material_finish=('O066 claims wood board and rust with a hand-painted faux verdigris surface.', 'Use that source wording provisionally, and confirm the actual board/coating recipe and exterior suitability with the maker.', 'NATIVE_MATERIAL_ASSERTION_NOT_TESTED', ['O066'], 'The chemistry comes from native text, not pixels; a historic “outdoor” line does not establish current weather resistance.'),
    fixing=('No rear hardware details in the supplied offer or image.', 'Two small rear hangers or a suitable concealed panel cleat is a working design choice for owner review after actual mass/back construction is known.', 'WORKING_DESIGN_PROPOSAL_ONLY', ['O066'], 'No installed count/type or capacity established.'),
    conflicts=['Native description supplies previously omitted 31.5 × 31.5 × 4 cm and wood-board assertions; they remain offer claims, not physical verification.', 'The captured £33.33 price should be checked as an actual intended selling price; its presence does not prove current availability.'])

for cid,offer in [('BC-SEAWEED-ROUGH','O026'),('BC-SEAWEED-SMOOTH','O012')]:
    put(cid,
        dimensions=('Captured '+offer+' single-offer claim: 50 × 100 × 6 cm.', 'Draft 100 cm wide × 50 cm high × 6 cm deep for the landscape version, confirming axis order and actual measurements.', 'NATIVE_SINGLE_OFFER_CLAIM', [offer], 'Do not apply to every size/finish; no component value divided from an arrangement.'),
        weight=('Native single-item claim: 18 kg.', 'Use approximately 18 kg as an unweighed source-based draft for the matching version.', 'NATIVE_SINGLE_OFFER_UNWEIGHED', [offer], 'No actual scale measurement; different sizes/finishes may differ.'),
        material_finish=('Native description says white marble stone finish, with a '+('sand-textured' if cid.endswith('ROUGH') else 'smooth flowing')+' relief surface.', 'Cast stone/composite relief in white stone effect, substrate/formulation to be confirmed by the maker.', 'DOCUMENTED_FINISH_CHEMISTRY_UNKNOWN', [offer], 'Finish wording does not prove solid marble or a specific binder.'),
        fixing=('No object-specific back/hardware record.', 'Two concealed stainless hanging positions are a working candidate for a landscape panel of this source mass; verify against the actual back.', 'WORKING_DESIGN_PROPOSAL_ONLY', [offer], 'No tested fixing count/type, anchor selection or load rating.'),
        conflicts=['Seaweed Ripple is a media-family alias; '+('Fossil Sand Ripple is the rough O026 design, separate from Smooth Sand Ripple O012.' if cid.endswith('ROUGH') else 'Smooth Sand Ripple is the smooth O012 design, separate from Fossil Sand Ripple O026.')])

put('BC-SHELL-B2',
    dimensions=('No maker code or measured dimensions tied to this distinct shell/outlet geometry.', 'About 70 × 50 cm in portrait, depth 5–7 cm, as a tentative size analogy to BSM1 only.', 'WORKING_SIZE_GUESS_BY_RELATED_FORM', ['G306','manufacture-stevensons:Sheet1!row112 by analogy'], 'Related BSM1 dimensions are not transferred as a fact.'),
    weight=('No individual mass record.', 'Approximately 12–15 kg only if a similar-size cast-composite version is confirmed; weigh the actual water-feature panel.', 'WORKING_MASS_GUESS_ONLY', ['G306','manufacture-stevensons:Sheet1!row112 by analogy'], 'No BSM1 weight inheritance; no water/plumbing mass included.'),
    material_finish=('White/stone-like textured surface and visible outlet; no actual substrate, coating or water system record.', 'Cast composite with a white stone appearance is a proposed specification; maker to confirm chemistry and a separate wet-use/plumbing design.', 'VISIBLE_APPEARANCE_ONLY', ['G306'], 'An outlet is not evidence of tested waterproofing, pump supply or serviceable installation.'),
    fixing=('No object-specific rear/hardware record.', 'Two concealed rear hanging positions as a working candidate, plus separate plumbing/service access requirements to be specified.', 'WORKING_DESIGN_PROPOSAL_ONLY', ['G306','manufacture-stevensons:Sheet1!row112 by analogy'], 'No hardware rating, actual count or water-service standard verified.'),
    individual_price=('No standalone current offer; BSM1/Islington standard 2025 table is a size comparator only.', 'Suggest £650–850 for a newly confirmed standard panel, with water-feature hardware/installation quoted separately.', 'WORKING_COMMERCIAL_GUESS_ONLY', ['retail-2025:70×50 by analogy','G306'], 'Not a BSM1 price copied as a fact or a quotation for an existing cast.'),
    conflicts=['This spiral/outlet geometry differs from maker BSM1; retain a separate local design candidate until the maker supplies its own code.'])

put('BC-SPICE',
    dimensions=('No calibrated dimensions.', 'About 30 × 30 cm, depth 5–7 cm, as an unmeasured standard-size hypothesis for the square form.', 'WORKING_SIZE_GUESS_ONLY', ['G311','retail-2025:30×30 size analogy'], 'No absolute scale inferred from pixels.'),
    weight=('No individual mass record.', 'Approximately 3–5 kg as a planning guess if the owner confirms a 30 cm cast-composite version.', 'WORKING_MASS_GUESS_ONLY', ['G311','manufacture-stevensons:30 cm templates by analogy'], 'Not an actual weight or material certification.'),
    material_finish=('Seed/stick/shard-like relief with a pale surface; actual inclusion material and binder undocumented.', 'Cast composite with a pale stone effect; describe the motifs as spice-like impressions until the maker confirms any real inclusions.', 'VISIBLE_APPEARANCE_ONLY', ['G311','G312'], 'Do not claim actual spices, organic content or specific chemistry from appearance/name.'),
    fixing=('No rear fixing record.', 'One concealed hanging point as a working small-panel candidate, pending actual back and mass review.', 'WORKING_DESIGN_PROPOSAL_ONLY', ['G311'], 'No installed hardware or capacity verified.'),
    individual_price=('No current single offer mapped.', 'Suggest £200–300 for a confirmed new 30 cm relief, as a draft asking range based on a dated small white standard plus extra texture.', 'WORKING_COMMERCIAL_GUESS_ONLY', ['retail-2025:30×30 size analogy','G311'], 'No source quote for Spice Texture; current costing/approval needed.'))

for cid in ['BC-SF-1','BC-SF-2']:
    put(cid,
        weight=('Maker row89: 10–12 kg EACH. 2025 retail table: estimated 12 kg EACH for the pair. Native 30 kg is the whole two-part O035 offer.', 'Use approximately 10–12 kg for this individual white standard panel, keeping the 12 kg retail estimate visible.', 'MAKER_AND_RETAIL_EACH_WEIGHT_ESTIMATES', ['manufacture-stevensons:Sheet1!row89','retail-2025:55×110 two-part table','O035'], 'No division of the 30 kg set; different bronze appearance is not automatically the same mass/material.'),
        individual_price=('No current standalone price established; O035 £1,160 and 2025 £1,094.64 are both whole-pair prices.', 'Suggest £565–650 for a confirmed white single panel using the independent 55 × 55 cm single-sculpture £562.36 dated size reference as an analogy.', 'WORKING_SINGLE_PRICE_FROM_SIZE_ANALOGY', ['retail-2025:55×55 SINGLE size table','O035'], 'Not either pair price divided by two; no approved standalone sale or exact model quote.'),
        conflicts=['The native offer sells both panels; its total dimensions, 30 kg mass and £1,160 price do not become this component’s values.', 'Bronze folders contain close details, not a verified complete bronze product specification.'])

put('BC-SM-SPIRAL',
    weight=('Maker calculated white AC730 estimate: 10–12 kg each. 2025 retail: estimated 12 kg. Native O036 single-item claim: 15 kg.', 'Keep 10–12 kg maker template and 15 kg native claim separate; use “approximately 12–15 kg, version to be confirmed” only as a visibly provisional review line.', 'CONFLICTING_SINGLE_COMPONENT_WEIGHT_CLAIMS', ['manufacture-stevensons:Sheet1!row46','retail-2025:55×55','O036'], 'The proposed bracket does not reconcile the sources or establish an actual mass.'),
    fixing=('Maker row46 description says one wall fixing, while its fixing-instruction column specifies two stainless steel fixings.', 'Two concealed stainless fixing points are the provisional candidate for owner correction; actual count and rear photograph required before publishing.', 'INTERNAL_MAKER_FIXING_CONFLICT', ['manufacture-stevensons:Sheet1!row46'], 'Do not resolve the conflicting maker columns by assumption; no load rating.'),
    conflicts=['Maker row46 has an internal one-fixing versus two-fixings contradiction.', 'The 15 kg native single-item claim differs from the 10–12 kg maker/12 kg retail estimates.'])

put('BC-SM-QUARTER',
    fixing=('Maker row49 description says one wall fixing per piece; instruction column specifies two stainless steel fixings.', 'Two concealed stainless fixing points as an explicitly unresolved candidate; owner must inspect the actual back and settle the contradiction.', 'INTERNAL_MAKER_FIXING_CONFLICT', ['manufacture-stevensons:Sheet1!row49'], 'No hardware count, anchor or load rating verified.'),
    individual_price=('2025 retail table explicitly lists a single Quarter Moon at the 55 × 55 cm size, £562.36; no current standalone offer mapped.', 'Suggest £565–650 for one standard white Quarter Moon, using the dated single-piece reference for owner correction.', 'DATED_PER_PIECE_REFERENCE_NEW_PRICE_GUESS', ['retail-2025:55×55'], 'O036 £580 is the separate SM1 offer, not an exact current Quarter Moon mapping.'),
    conflicts=['QM1 and QM2 are rotated positions of the Quarter Moon design; the three-part row49 total is not a single component.', 'Maker row49 has an internal one-fixing versus two-fixings contradiction.'])

put('BC-STRATA',
    dimensions=('O062 coloured/native description: 30 × 30 × 6 cm. Maker ST1 template: 30 × 30 cm, side 5–7 cm.', 'Draft 30 × 30 × 6 cm for the mapped verdigris offer, retaining the historical white-template depth range separately.', 'VARIANT_SCOPED_NATIVE_AND_MAKER_CLAIMS', ['O062','manufacture-stevensons:Sheet1!row116'], 'Not a measurement of every finish or size.'),
    weight=('O062 coloured/native description: 4 kg. Maker white AC730 template: calculated 3–5 kg each. 2025 white standard estimate: 5.5 kg.', 'Use 4 kg as a native claim for the mapped coloured version only, with actual weighing requested; preserve the other estimates under their own variants.', 'VARIANT_SCOPED_CONFLICTING_MASS_CLAIMS', ['O062','manufacture-stevensons:Sheet1!row116','retail-2025:30×30'], 'Do not average or treat different construction/finish variants as one weighed object.'),
    material_finish=('O062 claims cast gypsum composite with hand-applied faux verdigris. Maker ST1 white template specifies Jesmonite AC730 white marble stone finish.', 'For the G326/O062 version use “faux verdigris; substrate to confirm” while the maker checks the gypsum claim; keep white AC730 as a separate source variant.', 'VARIANT_MATERIAL_ASSERTIONS_NOT_PHYSICALLY_VERIFIED', ['O062','manufacture-stevensons:Sheet1!row116'], 'No chemical conclusion from turquoise/brown pixels; blue-wash, verdigris and white groups remain separate configurations.'),
    conflicts=['Gypsum composite in the coloured offer and AC730 in the historical white template may be different versions; source applicability remains unresolved.', '4 kg coloured native, 3–5 kg maker calculation and 5.5 kg dated white retail estimate are separate assertions.'])

for cid, dims, mass, price, shape, gr in [
 ('BC-TEXTURE-WIDE','100 × 60 cm, depth 2–4 cm','5–12 kg','£350–650','broad rectangular','G329'),
 ('BC-TEXTURE-TALL','150 × 55 cm, depth 2–4 cm','8–15 kg','£450–800','tall rectangular','G330'),
]:
    put(cid,
        dimensions=('No calibrated size or depth record for the '+shape+' panel.', dims+' only as a new design/size hypothesis for the owner to correct, not a measurement of the photographed original.', 'WORKING_SIZE_GUESS_ONLY', [gr], 'The photo supports proportion, not absolute scale.'),
        weight=('No actual mass or substrate record.', mass+' only as a planning guess IF the owner confirms a light rigid-board construction at the proposed size.', 'UNKNOWN_ACTUAL_MASS_CONDITIONAL_GUESS_ONLY', [gr], 'A different substrate can change mass substantially; not a hanging, lifting or shipping value.'),
        material_finish=('Visible rust/brown and blue/grey surface, without an authoritative model or chemistry record.', 'A coated rigid-board mixed-media panel with rust/blue colour effects is a proposed construction; confirm the actual support and recipe before naming materials.', 'VISIBLE_APPEARANCE_ONLY_PRODUCTION_IDENTITY_UNKNOWN', [gr], 'No claim of real oxidation, solid metal, specific binder, gold leaf or an available manufactured product.'),
        fixing=('No rear or hardware record.', 'A concealed panel cleat or two rear hangers is a working design option if a rigid board is confirmed.', 'WORKING_DESIGN_PROPOSAL_ONLY', [gr], 'No installed hardware count/type or load capacity established.'),
        individual_price=('No native standalone offer or formal model identity.', price+' as a speculative new artwork asking range for owner correction after size/construction and sale identity are established.', 'WORKING_COMMERCIAL_GUESS_ONLY', [gr,'O073:panel price comparator only'], 'No quote for the original; the smaller/different Azure offer is only a broad commercial comparator.'),
        availability=('Workshop/product imagery exists; production role, current stock and sale decision absent.', 'Hold as an unnamed sample/design record; discuss a new commission only after maker identity and construction review.', 'NO_CURRENT_STOCK_EVIDENCE', [gr], 'A photograph of a panel is not proof of a saleable current product.'),
        conflicts=['Colour words describe appearance; no formal retail alias or substrate/coating certificate recovered.', 'Full-panel imagery and close texture details belong to one visual group, not multiple distinct buyable components.'])

put('BC-AZURE',
    dimensions=('No calibrated face dimensions or depth in the mapped O073 native copy.', 'About 120 × 22 cm, depth 2–3 cm, as an explicitly unmeasured size hypothesis for the very tall narrow form.', 'WORKING_SIZE_GUESS_ONLY', ['G344','O073'], 'The source image shows proportions but supplies no ruler or known scale.'),
    weight=('No individual weight record.', 'About 2–4 kg only if the owner confirms a light board-backed construction at the proposed size.', 'WORKING_MASS_GUESS_ONLY', ['G344','O073'], 'Actual support/relief mass unknown; not a capacity or shipping value.'),
    material_finish=('Native copy describes a hand-marbled blue/white/cream relief panel and one-off surface; substrate/formulation absent.', 'Mixed-media marbled surface on a rigid support as a proposed construction; confirm the actual base, coating and care requirements.', 'DOCUMENTED_APPEARANCE_CHEMISTRY_UNKNOWN', ['O073'], 'No solid marble, resin, specific binder or exterior durability inferred from appearance.'),
    fixing=('Native copy allows portrait or landscape display; no rear hardware record.', 'Two appropriately positioned concealed hangers or a panel cleat is a working candidate, with both orientations checked by the maker.', 'WORKING_DESIGN_PROPOSAL_ONLY', ['O073'], 'Orientation wording is not a rear inspection or load-rated installation instruction.'),
    availability=('O073 calls this a genuine one-off, while exported unlimited/visibility fields are platform metadata rather than stock evidence.', 'One-off original: availability by owner confirmation. Offer similar new commissions only if approved, without promising the identical marbling.', 'ONE_OFF_COPY_CURRENT_STOCK_UNKNOWN', ['O073'], 'Do not turn “Unlimited”, “InStock” or a live page into confirmed physical stock.'),
    conflicts=['Only one marbled panel is the mapped sale item; the other wavy panel in paired scenes is a different unresolved subject.', 'One-off descriptive copy and generic platform inventory metadata do not establish a current available quantity.'])

for cid in ['BC-WBMS-WAVE','BC-WBMS-MOON']:
    put(cid,
        weight=('Maker white AC730 calculation: 6–8 kg EACH. 2025 retail table estimates 6.5 kg EACH. Native 27 kg is the whole three-position O044 offer.', 'Use 6–8 kg as a historical per-component draft and separately show 6.5 kg retail estimate; weigh the chosen version.', 'MAKER_RETAIL_EACH_COMPONENT_ESTIMATES', ['manufacture-stevensons:Sheet1!row'+('101' if cid.endswith('WAVE') else '97'),'retail-2025:40×120 table','O044'], 'No division of the 27 kg set and no inference from quantity.'),
        individual_price=('No mapped current standalone offer. O044 £900 and 2025 £884.68 are whole three-position prices.', 'Suggest £300–375 per confirmed new white 40 cm component using independent adjacent-size single-piece retail comparators, not the set price.', 'WORKING_SINGLE_PRICE_FROM_SIZE_ANALOGY', ['retail-2025:35×35 SINGLE £241.54','retail-2025:45×40 SINGLE £345.28','O044'], 'No exact 40 cm single-price source; no set-price division or approval.'),
        conflicts=['Dropbox Wave and Moonshadow 1 is maker WBMS2; Dropbox 2 is the smooth WBMS1/WBMS3 form.', 'O044 has three positions but two design identities, with Moonshadow used twice in rotated positions.', 'Whole-set mass/price/overall dimensions remain arrangement facts.'])

put('BC-MIX-SPIRALS',
    dimensions=('No calibrated dimensions or independent component record.', 'About 90 × 15 cm, depth 5–7 cm, as a very low-confidence size hypothesis for the visible five-spiral strip; replace with measurement if the owner recognizes it.', 'WORKING_SIZE_GUESS_ONLY_IDENTITY_UNKNOWN', ['G050','id:cnqzTNngPVsAAAAAAAuTGg'], 'Perspective and unknown neighbouring sizes prevent calibrated scale; motif count is not a piece count.'),
    weight=('No mass, backing construction or finished-cast identity.', 'Actual mass unknown. If a new approximately 90 × 15 cm lightweight cast is proposed, 4–8 kg is only a conditional planning guess.', 'UNKNOWN_ACTUAL_MASS_CONDITIONAL_GUESS_ONLY', ['G050'], 'The scene could show a master/sample or finished cast; no actual manufacturing or load inference.'),
    material_finish=('Pale beige/stone-like workshop appearance; master/mould/cast role and substrate unknown.', 'Draft “stacked spiral strip, production role and material to confirm”. A pale cast composite is a design proposal only if the owner wants a reproducible version.', 'PRODUCTION_AND_MATERIAL_UNKNOWN', ['G050'], 'Do not identify real stone, gypsum, AC730 or five separate sale pieces from the image.'),
    fixing=('No identifiable rear or installation record.', 'For a newly specified strip, two separated concealed rear points may prevent rotation; actual scheme remains to be designed.', 'WORKING_DESIGN_PROPOSAL_ONLY', ['G050'], 'No observed or approved hardware, count or rating.'),
    individual_price=('No offer, approved individual identity or manufacturing cost.', 'Keep this historical object price on request/unknown. If the owner confirms a new saleable strip, suggest £250–450 only as a provisional commission budget.', 'WORKING_COMMERCIAL_GUESS_ONLY', ['G050','retail-2025:70×15 SINGLE size analogy'], 'No exact price mapping; not a sum or division of the five motifs or neighbouring sculptures.'),
    availability=('Only mixed workshop evidence; production identity, ownership and sale status unresolved.', 'Identity-first hold as a sample/design record; no offer until the owner confirms whether it is a master, mould, sample or finished sculpture.', 'NO_CURRENT_STOCK_EVIDENCE', ['G050'], 'No current manufacture, standalone stock or complete isolated photograph confirmed.'),
    conflicts=['The initially selected representative id:cnqzTNngPVsAAAAAAArqRg shows two Moonspirals and does not demonstrate this strip.', 'Five visible spirals are surface motifs on one strip; independent mould count and sale identity remain unknown.'],
    handoff=['The correct candidate id:cnqzTNngPVsAAAAAAAuTGg shows the strip near the right of the mixed workshop frame.', 'Do not identify or import the other background sculptures as this component.'])

def generic_specs(c):
    cid=c['component_id'];claims=[z for z in X['claims'] if z['component_id']==cid]
    mrefs=maker_refs(cid)
    dim=next((z for z in claims if z['field']=='Manufacturing component dimensions / side depth'),None)
    wt=next((z for z in claims if z['field']=='Conditional component weight'),None)
    fixing=next((z for z in claims if z['field']=='Fixings instruction'),None)
    hist=next((z for z in claims if z['field']=='Historic per-piece retail reference'),None)
    boms=[z for z in X['bom'] if z['component_id']==cid]
    single=next((O[b['offer_ref']] for b in boms if b['scope']=='Sale component'),None)
    dims=spec(c['dimensions_available'], 'Use the listed per-component dimensions as an unmeasured source draft, with depth checked on the actual cast.', 'SCOPED_SOURCE_CLAIM_NOT_MEASURED', claim_refs(cid,['Manufacturing component dimensions / side depth','Prior extraction: Each component (cm)']), 'Only a matching source size/version; no whole-set dimension inheritance.')
    weight=spec(c['weight_available'], 'Use the historical each-piece maker estimate conditionally for the same white AC730 template; weigh the actual component.', 'HISTORICAL_CALCULATED_EACH_COMPONENT' if wt else 'UNKNOWN', claim_refs(cid,['Conditional component weight']), 'Historical calculations are not measured current-object mass; do not divide set mass.')
    material=spec('Historical maker standard: white marble stone finish Jesmonite AC730.' if mrefs else 'No object-specific substrate evidence.', 'Use the maker white AC730 template only after the owner confirms this exact version; preserve the photographed appearance separately.' if mrefs else 'Cast composite with a pale stone effect is a proposed construction; maker to confirm substrate and recipe.', 'MAKER_TEMPLATE_VERSION_CONDITIONAL' if mrefs else 'WORKING_MATERIAL_PROPOSAL_ONLY', claim_refs(cid,['Manufacturing description']) or c['group_refs'], 'Not a material certificate for every photograph/finish; no chemical conclusion from pixels.')
    fix=spec(fixing['value'].replace('\n',' ').strip() if fixing else 'No complete object-specific rear fixing record.', 'Use the stated maker fixing scheme only as a historical candidate pending actual rear photographs, dimensions and hanging instructions.' if fixing else 'Use two concealed rear hanging positions as a working design candidate, pending actual back and mass review.', 'MAKER_TEMPLATE_NOT_BACK_INSPECTION' if fixing else 'WORKING_DESIGN_PROPOSAL_ONLY', claim_refs(cid,['Fixings instruction']), 'No anchor choice, installed hardware inspection or load rating verified.')
    if single:
        price=spec('Captured single-offer '+single['offer_ref']+': GBP '+str(single.get('public_price') or single['native_price'])+'.', 'Carry this captured single-offer ask as a provisional price for owner correction; confirm current version, tax/delivery treatment and intended ask.', 'CAPTURED_SINGLE_OFFER_PRICE_NOT_CURRENT_VERIFIED', [single['offer_ref'],single['source_url']], 'Captured price is an offer assertion, not stock or completed-sale evidence; no platform write authorized.')
    elif hist:
        price=spec(hist['value'], 'Use the dated per-piece retail reference as the base for a newly quoted individual white version; round approximately £650 for a 70 × 50 cm panel if the owner agrees.', 'DATED_PER_PIECE_REFERENCE_NOT_CURRENT_PRICE', [hist['claim_id']+' | '+hist['source_ref']], 'Dated standard white price; extra finish/water features, delivery and current costing require owner review.')
    else:
        price=spec('No current individual price established.', 'Individual price on request until the maker confirms production identity; a numerical draft may be added after identity is resolved.', 'UNKNOWN_PRICE', c['group_refs'], 'Not inherited from an arrangement.')
    if single:
        avdisplay='Captured '+single['offer_ref']+' platform metadata: visible='+str(single.get('visible'))+', stock='+str(single.get('stock'))+', public availability='+str(single.get('public_availability'))+'. No actual stock count checked.'
    else:
        avdisplay='No current standalone offer/physical stock or lead-time record established.'
    avail=spec(avdisplay, 'Made to order / enquiry, subject to maker confirmation of this version and lead time; do not promise an in-stock cast.', 'PLATFORM_METADATA_ONLY_STOCK_UNKNOWN' if single else 'NO_CURRENT_STOCK_EVIDENCE', [single['offer_ref']] if single else ['retail-2025:conditions'] if mrefs else c['group_refs'], 'Catalogue availability policy is a proposal; “Unlimited”, visibility or “InStock” is not a physical stock audit.')
    return dict(dimensions=dims,weight=weight,material_finish=material,fixing=fix,individual_price=price,availability=avail)

entries=[]
for c in X['components']:
    cid=c['component_id'];p=P[cid];sp=generic_specs(c);special=SPECIAL.get(cid,{})
    for key in list(sp):
        if key in special:
            sp[key]=spec(*special[key])
    complete=not(cid.startswith('BC-LUCIANO') or cid=='BC-MIX-SPIRALS')
    primary=asset_record(p['id'], VISUAL[cid], complete=complete, reviewed=True)
    primary['group_ref']=p['group_ref']
    primary['image_scope']='Individual complete main subject; surrounding display/workshop objects are context only' if complete else 'Project detail only; no individual panel allocation' if cid.startswith('BC-LUCIANO') else 'Mixed scene; target strip visible but not isolated'
    alt=[];context=[];series=[];seen={p['id']}
    for gr in c['group_refs']:
        g=G[gr]
        for fid in g['selected'][:2]:
            if fid in seen or fid not in A:
                continue
            seen.add(fid)
            role=g['role'];reason='Frozen evidence candidate from '+gr+' ('+role+'); per-file identity/provenance requires owner review.'
            z=asset_record(fid,reason,role=role)
            z['group_ref']=gr
            if role=='Context image':
                context.append(z)
            elif 'arrangement' in role.lower():
                series.append(z)
            else:
                alt.append(z)
    # Explicitly useful source-bound mixed views, with no image crop or object extraction.
    if cid.startswith('BC-LUCIANO'):
        for dest in [context,series]:
            dest.append({'source_ref':'luciano-garden:p1','file_id':next(d['head']['id'] for d in X['document_sources'] if d['label']=='luciano-garden'),'folder_id':None,'preview_path':str(W/'luciano-source-p1.jpg'),'role':'Dated maker project sheet; full three-panel screen and details','shows_complete_single_component':False,'visual_reviewed_this_worker':True,'selection_reason':'Complete three-part context supplies dated project count, whole size and material; no separately isolated left/centre/right asset.'})
    if cid.startswith('BC-RIYADH'):
        series.append({'source_ref':'various-composites:p1','file_id':next(d['head']['id'] for d in X['document_sources'] if d['label']=='various-composites'),'folder_id':None,'preview_path':str(W/'riyadh-source-p1.jpg'),'role':'Maker portfolio project context','shows_complete_single_component':False,'visual_reviewed_this_worker':True,'selection_reason':'Shows Dune Ripple/Shellmoon project panels and explicit each-panel 100 × 275 cm caption; exact individual allocation needs owner.'})
    if cid=='BC-MIX-SPIRALS':
        context.insert(0,asset_record(p['id'],'The fully visible five-spiral strip is near the right; whole frame remains mixed workshop context.',role='Mixed workshop',complete=False,reviewed=True))
    maps=[]
    for ref in dict.fromkeys(b['offer_ref'] for b in X['bom'] if b['component_id']==cid):
        o=O[ref];bs=[b for b in X['bom'] if b['component_id']==cid and b['offer_ref']==ref]
        maps.append({'offer_ref':ref,'platform':o['platform'],'squarespace_id':o['sq_id'],'shopify_handle':o['sh_handle'],'sku':o['sku'],'title':o['title'],'source_url':o['source_url'],'source_page_sha256':o.get('page_sha256'),'mapping_state':o['image_state'],'scope':bs[0]['scope'],'positions':[b['position'] for b in bs],'quantity_in_offer':sum(b['quantity'] for b in bs),'is_standalone_component_offer':bs[0]['scope']=='Sale component','captured_offer_price':{'value':o.get('public_price') or o['native_price'],'currency':o.get('public_currency') or o['native_currency'],'unit':'whole mapped native offer'},'captured_offer_weight_kg':o['source_set_weight_kg'],'component_values_not_inherited_from_set':True,'limits':o['cautions'] or 'Frozen mapping only; no new exact match or current stock assertion. Root will rebind fresh native metadata/links.'})
    refs=c['group_refs']+['asset:'+p['id']]+['manufacture-stevensons:Sheet1!row'+str(r) for r in c['maker_rows']]+list(dict.fromkeys(b['offer_ref'] for b in X['bom'] if b['component_id']==cid))+special.get('extra_sources',[])
    for ss in sp.values():
        refs.extend(ss['basis_refs'])
    refs=list(dict.fromkeys(refs))
    conflicts=special.get('conflicts',[])
    if not maps:
        conflicts.append('No exact native platform offer is established for this individual component in the frozen BOM; family/name similarity alone does not create one.')
    missing=['Actual component measurements and separately weighed mass for the specific cast/version.','Maker confirmation of exact substrate, finish recipe and applicability of historical/source claims.','Rear photograph, actual hardware instructions and wall-specific mounting scheme; no load rating established.','Owner decision on individual sale, current price, availability, reproduction policy and lead time.']
    if not complete:
        missing.insert(0,'Complete isolated individual front photograph and allocation of this exact component identity.')
    if cid.startswith('BC-RIYADH'):
        missing.insert(0,'Owner confirmation of the each-panel project dimensions and exact as-built/source-panel mapping.')
    if cid in ['BC-PANEL-CURVES','BC-TEXTURE-WIDE','BC-TEXTURE-TALL','BC-MIX-SPIRALS']:
        missing.insert(0,'Formal maker identity and master/mould/sample/finished-cast production status.')
    if not context:
        missing.append('No context candidate allocated in this packet; absence here is not proof no context photograph exists.')
    if not series:
        missing.append('No series candidate allocated in this packet; the isolated design does not imply a required set.')
    notes=['Advisory packet only: owner session 01a144ab-1a7c-7223-a403-73a4d53d70ff remains sole writer of approvals/checkpoints/register/workbooks.','All six specification proposals require owner checking; none is an approval, measurement, stock check, load specification or authority to mutate Dropbox.','Local cached visuals inspected with tools.view_image as complete frames/contact sheets; no private external uploads or generative edits.','Root must bind stable IDs to the fresh current metadata/hash/path and supply read-only review links before use.']+special.get('handoff',[])
    identity={'state':c['identity_status'],'visual_observation':VISUAL[cid],'source_refs':refs,'maker_row_image_check':bool(c['maker_rows']),'identity_limits':'A complete visual subject supports owner review, not physical manufacture, retail identity, provenance, material chemistry or availability.','physical_specs_verified':False,'owner_approval_recorded':False}
    entries.append({'component_id':cid,'proposed_name':c['name'],'family':c['family'],'identity_evidence':identity,'source_refs':refs,'primary_example':primary,'alternate_examples':alt,'context_images':context,'series_images':series,'specifications':sp,'source_conflicts':conflicts,'missing_evidence':missing,'platform_mapping':maps,'review_ready':complete,'review_ready_scope':'Ready for an owner visual/specification walkthrough with visible guesses; not listing/publication-ready' if complete else 'Identity-first advisory packet; full isolated individual example not available','handoff_notes':notes})

validation={
 'schema':'boldstone.parallel-preparation.packets.v1',
 'prepared_utc':datetime.now(timezone.utc).isoformat(),
 'ownership':'Only worker-03 output was written. No shared approval/checkpoint/register/workbook or other worker files changed by this script.',
 'source_scope':'Frozen assignment and local cached source documents, no live Dropbox API/tool calls or platform changes.',
 'tests':'No worker live reads. Root reported 74 fake-adapter tests passed before its separate live read; this packet does not present that as a worker test run or sandbox result.',
 'review_ready_definition':'True means complete individual main subject has been locally inspected and an advisory packet can be put to the owner. It does not mean source conflicts resolved or approved/publication-ready.',
 'non_review_ready_ids':[e['component_id'] for e in entries if not e['review_ready']],
 'source_snapshot_sha256':hashlib.sha256(Path(X['source_snapshot']).read_bytes()).hexdigest(),
 'source_snapshot_expected_sha256':'ba65d17e6182ba6b89f30400d2f0236bc22a1478c29fb39be4d362a48d24fb61',
 'assignment_sha256':hashlib.sha256((W/'assignment.json').read_bytes()).hexdigest(),
 'visual_review_artifacts':[str(W/f'visual-sheet-{i:02d}.jpg') for i in range(1,7)]+[str(W/'rechecked-primary-1.jpg'),str(W/'rechecked-primary-2.jpg'),str(W/'manufacturing-label-check.jpg'),str(W/'luciano-source-p1.jpg'),str(W/'riyadh-source-p1.jpg')],
 'visual_review_limits':'Sheets 01–06 were initial triage. Rechecked-primary sheets supersede the cropped/misallocated primaries identified there. Context/series candidates without visual_reviewed_this_worker=true remain frozen prior-review candidates.',
 'additional_source_documents':[source_doc(r) for r in ['luciano-garden:p1','various-composites:p1','retail-2025:tables and conditions','trade-2016:30×30 Plant Form','manufacture-stevensons:labelled rows']],
 'source_boundaries':['2025 retail values are dated estimates/standard-white prices, not current quotes.','Native public/extracted values are frozen captured claims; no current public-page refresh by this worker.','A source total is never a component weight/price/dimension. All price guesses use independent single-piece references or clearly stated new budgets.','No exact physical weight, hardware capacity, production certification, stock quantity, owner approval or new platform mapping is invented.','No BC-CONCAVE or BC-WALL-CIRCLE entry is included.'],
 'memory_used_for_method_only':['MEMORY.md:17-29; distinguish design, finish, individual identity, arrangement and native offers. All packet facts checked in present frozen sources.'],
}
counts={'assigned':len(X['component_ids']),'prepared':len(entries),'review_ready':sum(e['review_ready'] for e in entries),'identity_first_not_review_ready':sum(not e['review_ready'] for e in entries),'with_complete_single_component_primary':sum(e['primary_example']['shows_complete_single_component'] for e in entries),'with_native_mapping':sum(bool(e['platform_mapping']) for e in entries),'with_standalone_native_offer':sum(any(m['is_standalone_component_offer'] for m in e['platform_mapping']) for e in entries),'physically_verified':0,'owner_approved':0,'remote_mutations':0,'shared_state_writes':0}
out={'worker_number':3,'entries':entries,'counts':counts,'validation_notes':validation}
assert len(entries)==34 and [e['component_id'] for e in entries]==X['component_ids']
assert len({e['component_id'] for e in entries})==34
assert all(set(e['specifications'])=={'dimensions','weight','material_finish','fixing','individual_price','availability'} for e in entries)
assert all(s['requires_owner_check'] and s['proposal'].startswith('WORKING PROPOSAL') for e in entries for s in e['specifications'].values())
assert all(Path(e['primary_example']['preview_path']).is_file() for e in entries)
assert validation['source_snapshot_sha256']==validation['source_snapshot_expected_sha256']
(W/'packets.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
(W/'validation.json').write_text(json.dumps({'status':'PASS_LOCAL_PACKET_VALIDATION','counts':counts,'checks':['34 unique assigned IDs in assigned order','all six specification keys and owner-check flags present','all primary local preview paths exist','all primary IDs/folder IDs from frozen assigned assets','frozen shared component snapshot SHA256 unchanged','no active or Wall Circle component included'],'limits':validation['source_boundaries']},ensure_ascii=False,indent=2)+'\n')
print(json.dumps(counts,indent=2))
print(str(W/'packets.json'))
