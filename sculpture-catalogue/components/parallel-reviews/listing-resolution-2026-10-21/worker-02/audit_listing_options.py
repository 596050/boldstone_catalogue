#!/usr/bin/env python3
"""Local evidence audit. Writes are confined to this worker directory."""
from __future__ import annotations

import collections
import copy
import hashlib
import html
import json
import pathlib
import re
from datetime import datetime, timezone

HERE = pathlib.Path(__file__).resolve().parent
ROOT = pathlib.Path('/Users/tprice/Documents/boldstone/sculpture-catalogue')
TASK = HERE.parent
PACK = pathlib.Path('/Users/tprice/Library/Application Support/BoldstoneImageConsistency/product-evidence-resolution-20261016T201618Z')
PRIOR = ROOT / 'components/parallel-reviews/listing-reconciliation-2026-10-20'
EXPECTED_MASTER = '7760b44a4d52ff3b78c893d5b86ef174814b48c29f7e41814c8a01a42af5326d'
EXPECTED_FRESH = '4445986b548ef256c7ab2f4f8c80f34ade0f590ce9e9e6adbdf4ea9118726bfd'
STATES = {'NO_SUPPORTED_INDIVIDUAL_ASSOCIATION_IN_CHECKED_SOURCES', 'RELATED_FAMILY_ONLY_NO_INDIVIDUAL_MATCH', 'GALLERY_OR_DRAFT_CONTEXT_SALE_UNIT_UNRESOLVED', 'INDIVIDUAL_LISTING_CANDIDATE_SCOPE_UNRESOLVED'}
SOURCES = {}

def sha(b):
    return hashlib.sha256(b).hexdigest()

def read(p, expected=None):
    p = pathlib.Path(p)
    b = p.read_bytes()
    digest = sha(b)
    if expected:
        assert digest == expected, (str(p), digest, expected)
    SOURCES[str(p)] = {'path': str(p), 'sha256': digest, 'bytes': len(b)}
    return b

def load(p, expected=None):
    return json.loads(read(p, expected))

def ref(p, pointer=None):
    p = str(p)
    result = copy.deepcopy(SOURCES[p])
    if pointer is not None:
        result['json_pointer'] = pointer
    return result

def save(name, data):
    p = HERE / name
    assert p.parent == HERE
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')

def plain(s):
    return ' '.join(html.unescape(re.sub(r'<[^>]*>', ' ', s or '')).split())

MASTER_PATH = TASK / 'inputs/master-register.json'
FRESH_PATH = TASK / 'worker-01/FRESH_PUBLIC_INVENTORY.json'
MODEL_PATH = ROOT / 'components/evidence/component_register.json'
PROGRESS_PATH = ROOT / 'components/reviews/specification_review_progress.json'
OWNER_PATH = ROOT / 'components/reviews/user_classifications.json'
PHOTO_PATH = ROOT / 'components/reconciliation/image-identity-coverage-2026-10-20/image-coverage-audit.json'
OLD_SS_AUDIT_PATH = PRIOR / 'worker-01/UNLINKED_SCOPE_AUDIT.json'
SH_PRODUCTS_PATH = PRIOR / 'worker-02/shopify_products.json'
SH_VARIANTS_PATH = PRIOR / 'worker-02/shopify_variants.json'
SH_AUDIT_PATH = PRIOR / 'worker-02/UNLINKED_SCOPE_AUDIT.json'
SH_RECEIPTS_PATH = PRIOR / 'worker-02/source_receipts.json'
GALLERY_PATH = PACK / 'Public_Gallery_References.json'
MAKER_PATH = PACK / 'Manufacturing_Sheet_Extract.json'
MAKER_IMAGES_PATH = PACK / 'Manufacturing_Labelled_References.json'

master = load(MASTER_PATH, EXPECTED_MASTER)
fresh = load(FRESH_PATH, EXPECTED_FRESH)
model = load(MODEL_PATH)
progress = load(PROGRESS_PATH)
owner = load(OWNER_PATH)
photos = load(PHOTO_PATH)
old_ss_audit = load(OLD_SS_AUDIT_PATH)
sh_products = load(SH_PRODUCTS_PATH)
sh_variants = load(SH_VARIANTS_PATH)
sh_audit = load(SH_AUDIT_PATH)
sh_receipts = load(SH_RECEIPTS_PATH)
gallery = load(GALLERY_PATH)
maker = load(MAKER_PATH)
maker_images = load(MAKER_IMAGES_PATH)

assigned = [(i, o) for i, o in enumerate(master['options']) if o['current_listing_reconciliation']['overall_disposition'] in STATES]
assert len(assigned) == 99
assert collections.Counter(o['current_listing_reconciliation']['overall_disposition'] for _, o in assigned) == { 'NO_SUPPORTED_INDIVIDUAL_ASSOCIATION_IN_CHECKED_SOURCES': 57, 'RELATED_FAMILY_ONLY_NO_INDIVIDUAL_MATCH': 34, 'GALLERY_OR_DRAFT_CONTEXT_SALE_UNIT_UNRESOLVED': 6, 'INDIVIDUAL_LISTING_CANDIDATE_SCOPE_UNRESOLVED': 2 }
components = {c['component_id']: c for c in master['components']}
source_components = {c['component_id']: c for c in model['components']}
assets = {a['id']: a for a in model['assets']}
public_products = {p['native_product_id']: (i, p) for i, p in enumerate(fresh['products'])}
native_offers = {e['offer_ref']: (i, e) for i, e in enumerate(master['source_offer_edges'])}
sh_by_handle = {p['handle']: (i, p) for i, p in enumerate(sh_products)}
sh_variants_by_handle = collections.defaultdict(list)
for i, v in enumerate(sh_variants):
    sh_variants_by_handle[v['handle']].append((i, v))
photo_by_option = {p['option_id']: (i, p) for i, p in enumerate(photos['coverage'])}
edges_by_option = collections.defaultdict(list)
for i, e in enumerate(master['current_listing_match_evidence']['edges']):
    edges_by_option[e['product_id']].append((i, e))

DOC_TEXTS = {}
for directory in [PACK / 'documents', PACK / 'late-source-check/documents']:
    for p in sorted(directory.glob('*.txt')):
        if p.name.endswith('.docx.extracted.txt'):
            continue
        DOC_TEXTS[str(p)] = read(p).decode('utf-8', errors='replace')

def doc_lines(relative, first, last, applicability):
    p = PACK / relative
    lines = DOC_TEXTS[str(p)].splitlines()
    return {'source': ref(p), 'line_start': first, 'line_end': last, 'literal_text': '\n'.join(lines[first-1:last]), 'applicability': applicability}

custom_order_evidence = [
    doc_lines('documents/trade-2025.txt', 110, 115, '2025 white-standard price list; custom commissions, water features, metallic finishes and textures charged by quotation. No enumerated native variant or exact sculpture/finish recipe.'),
    doc_lines('documents/metal-effects-2025.txt', 1, 6, 'Examples of available surface effects; no design-specific SKU/size/build assertion.'),
    doc_lines('late-source-check/documents/metal-effects-4.txt', 1, 17, 'Explicit catalogue-wide made-to-order metal-effect capability; individually applied variation. It does not bind a pictured option to an existing native variant.'),
    doc_lines('documents/brochure-upper.txt', 167, 190, 'Flat-relief custom dimensions/materials and general customisation possibilities; not proof that every configuration is already a native offer.'),
    doc_lines('documents/framed-moonphases.txt', 1, 7, 'Named metal and stone effects for framed Moonphases; no part number, outer border size, native SKU or unit-price allocation.')
]

# Human-reviewed scope reasons. These are deliberately independent of title similarity.
NOTES = {}
def note(ids, text):
    for cid in ids.split():
        NOTES[cid] = text

note('BC-AC-ONE', 'The owner-kept One Leaf design and its three finish scopes have no linked native offer. O069 is the independently reviewed Two Leaves Bronze design, not this geometry. Generic Acanthus/30 cm catalogue examples and surface-effect capability support enquiry only; they do not identify an existing One Leaf SKU.')
note('BC-AC-TWO', 'O069 is bound to the kept Bronze option. Its 30 cm plaster/Bronze offer does not enumerate White, Pale Blue/White or White/Black variants. The other kept finish scopes remain individual catalogue options without a supported native variant; no Bronze SKU is shared among them.')
note('BC-BR-1 BC-BR-2', 'O029 offers a two-part White Brancusi arrangement. The separate Gold Leaf owner-kept member is not a native variant of that set in the checked records. The 2025 Brancusi each-piece White price and general metal-effect capability support a separately quoted individual; the set SKU, set mass and price are not allocated.')
note('BC-CHELSEA', 'The kept Chelsea Moonwave individual has an owner-corrected 250 × 100 cm working face size. Project/exhibition documents and photographs are not a native sale record. Earlier £1,100 source history remains qualified after the size correction; no matching native product/variant or current quote is established.')
note('BC-CHISWICK', 'The kept Chiswick standard wall and water-feature builds are distinct owner review scopes. Project/photographic evidence and the 70 × 95 cm owner dimensions do not identify native variants. General water-feature customisation is by quotation and is not proof of plumbing, sealing or a standard/water SKU pair.')
note('BC-CORAL', 'Coral Spiral is the separately kept 55 × 55 cm owner-sized design. A generic spiral relief, a 55 cm Quarter Moon or the long Deco Dune Ripple set is not an identity join. No supported native Coral option was found in the checked inventory.')
note('BC-CR-RING BC-CR-SPIRAL', 'The labelled maker source distinguishes CRS2 Cup Ring and CRS1 Spiral, with a 30 cm historical White standard. The general Cupring & Spiral each-piece catalogue line supplies source sale scope, but no native offer/SKU. The other evidence lane owns moved-reference/FP-label review; no path label is used to assign FP1/FP2 geometry or a new native match.')
note('BC-DDR-SPIRAL BC-DDR-WAVE', 'O013 explicitly offers a two-part White 100 × 22 cm-per-part arrangement. The independently kept Verdigris member is a different finish and separate individual sale unit; the source set SKU is not its SKU. Custom metal-effect availability supports enquiry, without proving an enumerated native individual variant.')
note('BC-DECO-2', 'O060 is associated with the reviewed White Decowaves member despite its historical title-family discrepancy. The Terracotta member has a separate owner-kept reference; no native Terracotta variant is enumerated. A shared broad family photograph cannot transfer O060 to this finish.')
note('BC-DR-SPIRAL', 'The maker DR2 geometry and kept finish decisions establish the catalogue scope. Existing small Dune Ripple offers are separately tied to particular photographed finishes; folder-level Verdigris coverage cannot identify every retained finish. Historical 35 × 20 × 5 cm and later 35 × 21 × 6 cm descriptions remain dated source versions. Generic finishes/different sizes do not create new native options.')
note('BC-DR-WAVE1', 'The DR1 wave geometry is separate from the DR2 spiral. The kept White, Blue Verdigris/Bronze and Verdigris/Rust scopes cannot inherit a sibling finish SKU from broad folder coverage. Source O038 has its own single-component copper/rust wording and photo; O004 is separately tied to the Verdigris primary. Source dimension versions remain separate.')
note('BC-EG-1', 'O041 is a two-part White Palm offer; O042 depicts/offers the separate Gold Leaf single Palm. Neither enumerates the owner-kept Black/White marbled finish. The 50/60 cm source-height discrepancy remains qualified and does not authorize a new size variant or a set-SKU allocation.')
note('BC-EG-3 BC-EG-4', 'The owner-kept Three Leaves/Extended Egyptian Palm geometry has its own reviewed reference. The White two-Palm offer and single Gold Palm do not establish these shapes or builds. Their working size/material estimates are preserved; no source-native variant has been identified.')
note('BC-EMBED-SHELLS', 'The owner-kept Embedded Shells panel has owner-stated 70 × 15 cm face dimensions. A matching Frozen Fish size is not design identity. No checked native description or explicit source mapping offers this panel as a native variant.')
note('BC-FACET-MOUND', 'The Faceted Mound Gold Leaf scope is owner-kept from its own reference, with qualified working size/material estimates. A generic Gold Leaf panel or decorative item is not this design. No native individual offer was established.')
note('BC-FOLD-4', 'The Fold Unfold 4 scope has a dated 2025 75 × 50 cm source example. Existing Cultivation Folds/other-fold arrangement offers do not prove this fourth geometry as a separately offered native member. The six working fields remain unchanged and no set SKU is reused.')
note('BC-FP-LEFT BC-FP-RIGHT', 'The owner-kept Fingerprint Left/Right options and White/Verdigris appearances are not identified by the unrelated FP1/FP2 folder labels under the Cup Ring evidence. The 40 cm owner face reference and conditional comparator dimensions are retained. No native individual Fingerprint variant was established; the moved-reference lane controls any later photo overlay.')
note('BC-FOUNTAIN-EG', 'O014 explicitly describes the White 100 × 50 cm Deco Fountain. The owner-kept Bronze/Verdigris Fountain Palm Egyptian is a separately reviewed finish. Generic metallic-effect custom orders do not make its exact coating/build a native option of the White listing.')
note('BC-FOUNTAIN-MED', 'The owner-kept Mediterranean Fountain Palm geometry is distinct from the O014 Egyptian/Deco Fountain source. Shared fountain terminology or estimated 100 × 50 cm dimensions are not identity evidence. No native individual record is supported.')
note('BC-FFL-1', 'The 100 × 22 cm Frozen Fish Long option is explicitly documented as an each-piece White source offering. Its exact photograph and geometry parent remain unbound. A Short/White path or image does not establish this Long size; SH-DRAFT is blank-description, and the separate moved-reference lane supplies any later overlay.')
note('BC-FFS-1 BC-FFS-2 BC-FFS-3', 'The maker labels three Short Frozen Fish designs at the historical 70 × 15 cm standard. The frozen-fish Shopify snapshot is a draft with blank description/SKU and one unqualified Default Title row. O049/O063 imagery/body or a multipart draft photo does not enumerate all three separately purchasable native member variants. No FFL100 × 22 cm identity is inferred from the paths.')
note('BC-GLEN-1 BC-GLEN-2 BC-GLEN-3 BC-GLEN-4', 'The four Gleneagles Vine/Tendril positions have owner-directed 35 × 35 cm member faces within a 70 × 70 cm composition. Project/group images do not create four native offers; the current catalogue keeps the individual scopes while physical mould reuse, material and source account inventory remain separate.')
note('BC-KNIGHT', 'The Knightsbridge Fountain has owner-stated 100 × 100 × 50 cm working dimensions and a documented commissioned courtyard water feature. That commissioned-project evidence is not a native individual listing, and no pump, sealing, installed-hardware or current-stock certification is inferred.')
note('BC-LAVA-1 BC-LAVA-2 BC-LAVA-3', 'The owner expressly instructed each Lava Moon panel to be offered separately. The six Left/Centre/Right Sandstone/White working options and owner-directed 80 cm × 240 cm dimensions are preserved. A three-panel project image supplies context, not a native individual or set SKU; no matched individual native record was established.')
note('BC-LEAF-CURVE', 'Leaf Curve White/Gold has its own kept reference. Leaf Form, Leaf Growth and Gold Palm are distinct source geometries. No checked native description/explicit mapping establishes this Leaf Curve finish as an existing individual variant.')
note('BC-LEAF-FORM', 'The maker explicitly describes one Leaf Form mould used in opposite directions; numbered source positions do not contradict reuse. O028 offers a White pair and O058 a White single with a retained size-version issue. Neither enumerates this kept Gold finish; no White/set SKU is assigned to it.')
note('BC-LEAF-GROWTH', 'O037 explicitly offers White Leaf Growth. The kept White-and-Gold surface is a separate review scope, with conditional White-format dimensions. General Gold Leaf customisation is enquiry coverage, not an exact native variant or a binder/leaf certification.')
note('BC-MSW-MOON', 'O021 and O032/O033 offer White Half Moon/Moon-and-Shellwave scopes. The maker distinguishes two moulds and inverted Moon positions; numbered positions are not extra moulds. The kept Black/White marbled Moon finish is not enumerated as a native option of those White arrangements.')
note('BC-MSW-SPIRAL', 'O032/O033 are White Moon-and-Shellwave arrangements. The owner-kept horizontal Shellwave Water Feature is a different build and individual sale unit; rotating the panel does not prove water sealing/plumbing or native water-feature SKU. General water-feature quotation capability is retained.')
note('BC-MCP-1', 'O007 is a single 25 × 25 × 6 cm faux-verdigris-on-copper source offer, but its current gallery has no explicit MCP1/owner-finish attribute. The reviewed gallery and kept Verdigris/Rust primary are not the same photograph and have different visible patina layouts; colour and spherical wording alone do not bind the exact named option. Its White sibling is not covered by this coloured listing.')
note('BC-MCP-2', 'O008 is explicitly photo-bound by the existing owner review to MCP2 Verdigris/Rust despite its Blue title. It is not the separate Blue Splashes or White option. The owner-kept Blue Splashes markings and White source standard are retained without reusing the Verdigris/Rust native SKU.')
note('BC-MCP-3', 'O005 is already photo-bound to the coloured MCP3 Verdigris/Rust option. It does not enumerate a White native variant. The labelled White maker standard remains a separate catalogue source specification and not an existing SKU.')
note('BC-MCP-4', 'The former Concave Moon alias is retained under MCP4, without merging finish options. O006 requires its own gallery/owner-finish join; O003/O064 Silver/Bronze and O011 Verdigris are different retained finishes. O015 describes a 50 cm White offer but its bound hero is Moon Water Catcher, so it cannot establish the owner-sized White25 MCP4 option.')
note('BC-CRATER-WIDE', 'The Wide Lip Drip Rust panel is an independently kept geometry/appearance. A Rust quartet, generic spherical Verdigris product or a nearby Moon Crater file does not bind this lip form to an existing variant. No exact native individual record was established.')
note('BC-MOON-RING', 'Moon Ring White has a separate kept reference and conditional working dimensions. Cup Ring, Moon Crater, and spherical catch-all bowls are not aliases without explicit evidence. No supported native Moon Ring individual offer was found.')
note('BC-MOON-CRATER', 'The White Basin is an owner-kept basin/build scope with explicitly low-confidence size/sealing estimates. Native 25 cm painted catch-all dishes offer different finishes and functionality; spherical-relief terminology does not establish this White Basin as their variant.')
note('MOONPHASE-CURRENT-1 MOONPHASE-CURRENT-2', 'The current Moonphase names follow the preserved owner four-design crosswalk, not historical numbered filenames alone. O065/O074 primary references show unbordered White reliefs; the separately kept rectangular-border reference has no native border option/outer size. O010 gallery and O030/O031 arrangements do not enumerate a separate Gold or bordered member SKU.')
note('MOONPHASE-CURRENT-4', 'The owner assigns the plain Moon geometry to current MP4, with historical MP1/MP5 orientation retained. O070 is the White source and O030 a White arrangement, not the separately kept White-and-Gold finish. Metal/gilding capability supplies quotation coverage only.')
note('BC-MLAVA-1 BC-MLAVA-2 BC-LAVA-CORNER', 'Owner position decisions retain the two White Moonshell Lava panels and the separate Corner Curve scope. Their combined/reference photographs do not establish individual native variants. No extra wall-pair products or inherited set specifications are introduced; the Corner30 size remains owner-directed.')
note('BC-MS-1 BC-MS-3', 'Maker-labelled MS1/MS3 White Moonspiral designs have a historical 70 × 50 cm each-piece standard. Similar Moonwave/Moon Fishwave native titles or arrangement photographs are different designs/sale scopes. No native individual MS1/MS3 offer was established.')
note('BC-PANEL-CURVES', 'The Beige and Textured Gold Leaf Panel Curves scopes are owner-kept separately. Gold Leaf and the 25 cm face are owner-stated only for the relevant Gold scope; no native variant is proven by another Gold panel or process filename. Both sets of six working fields are preserved.')
note('BC-PLANT', 'The Plant Form White record retains its 2016 30 cm catalogue candidate and qualified working fields. A similarly named Palm, Leaf or printed botanical product is not this relief. No supported native individual Plant Form record was established.')
note('BC-RW-SPIRAL1 BC-RW-SPIRAL3 BC-RW-WAVE', 'O017 expressly offers four White Raked Water parts as an arrangement. The Beige kept members are separate finish/individual scopes. Historical rotated repetitions remain positions of an existing mould, not extra products; the set SKU/total price is not an individual Beige SKU/price.')
note('BC-RIYADH-1 BC-RIYADH-2 BC-RIYADH-3', 'The three Riyadh panels are kept positional design scopes. The 275 × 100 cm historical project dimension remains provisionally applicable, not a confirmed per-panel measurement. Commission/project photographs do not establish separate native offers; no source set/project dimension is silently allocated.')
note('BC-SHELL-B1 BC-SHELL-B2 BC-SHELL-I', 'Historical maker/each-piece sources support the relevant standard Battersea1/Islington geometry, while owner review keeps standard and water builds separate. Battersea2 is only the kept Water Feature scope; no extra standard White build is invented from a generic BASE heading. No native SKU pair or sealing/plumbing specification is established by custom water-feature capability.')
note('UGR-G310', 'Soundwave White has a specific owner-kept reference and 80 × 60 cm face. The generic source group code and similarly titled Echo Sound/Spice panels do not establish a native identity. No supported individual native Soundwave offer was found.')
note('CAT-SPICE-1 CAT-SPICE-2', 'The two Spice Texture White design positions are retained as separate current component identities. The historical BC-SPICE family label does not merge them or assign one native SKU to both. Their conditional 30 cm working fields remain unchanged; no native individual match was established.')
note('BC-SF-1 BC-SF-2', 'O035 offers the two-part White Spiralfish Wave & Tide arrangement. Each kept Bronze member is a separate individual appearance scope, not a native option of that set. Generic Bronze customisation is enquiry coverage; the set SKU and 110 cm overall size/price are not reused.')
note('BC-SM-QUARTER', 'The maker identifies the Quarter Moon White geometry and 55 cm historical standard. O020 is the distinct Spiralmoon single, not a Quarter Moon alias. The 2025 each-piece Quarter Moon source supports an individual quotation; no exact native product/variant is established.')
note('BC-STRATA', 'O062 is already photo-bound to the kept Rust/Bronze Strata treatment. Its faux-verdigris wording does not override the owner-scoped photo or create native Blue Wash/White variants. Historical maker White30 and general metal effects remain separate source/custom-order evidence.')
note('BC-TEXTURE-TALL BC-TEXTURE-WIDE', 'The Tall and Wide textured patina panels have separate owner-kept references and qualified working size/support hypotheses. Native Rust/Verdigris relief titles or flat decorative media do not bind these panels. No supported native individual variant was established.')

def source_ids(o):
    cid = o.get('canonical_component_id') or o.get('canonical_design_id')
    return components.get(cid, {}).get('source_component_ids', [o['canonical_key'].split('|')[0]])

def owner_refs(o):
    ids = set(source_ids(o)) | {o.get('canonical_component_id'), o.get('canonical_design_id')}
    variant = o['canonical_key'].split('|', 1)[1]
    files = {o.get('file_id'), o['current_listing_reconciliation'].get('context_image_file_id')} - {None}
    matches = []
    for key, values in owner.items():
        if not isinstance(values, list):
            continue
        for i, value in enumerate(values):
            if not isinstance(value, dict):
                continue
            tokens = set()
            def walk(x):
                if isinstance(x, dict):
                    for k, v in x.items():
                        if k in {'component_id', 'canonical_design_id', 'canonical_component_id', 'size_finish_variant_id', 'evidence_file_id', 'primary_file_id', 'file_id'} and isinstance(v, str):
                            tokens.add(v)
                        elif k in {'component_ids', 'components', 'historical_component_ids', 'source_component_ids'} and isinstance(v, list):
                            tokens.update(vv for vv in v if isinstance(vv, str))
                        elif isinstance(v, (dict, list)):
                            walk(v)
                elif isinstance(x, list):
                    for v in x:
                        walk(v)
            walk(value)
            if tokens & ids or variant in tokens or tokens & files:
                matches.append({'source': ref(OWNER_PATH, f'/{key}/{i}'), 'decision_id': value.get('decision_id', value.get('policy_id')), 'match_scope': 'EXPLICIT_COMPONENT_VARIANT_OR_FILE_ID; sibling decisions retained as component context, not per-option acceptance'})
    return matches

def native_claim(offer_ref):
    oi, edge = native_offers[offer_ref]
    s = edge['source_offer']
    result = {'offer_ref': offer_ref, 'retained_source_offer': copy.deepcopy(s), 'source': ref(MASTER_PATH, f'/source_offer_edges/{oi}/source_offer'), 'member_positions': copy.deepcopy(edge['members']), 'Squarespace': None, 'Shopify': None}
    if s.get('sq_id') in public_products:
        pi, p = public_products[s['sq_id']]
        result['Squarespace'] = {'native_product_id': p['native_product_id'], 'url': p['url'], 'description_html': p['description_html'], 'description_text': p['description_text'], 'description_source_field': p['description_source_field'], 'retained_description_equal_after_normalization': plain(p['description_html']) == plain(s['native_description']), 'variants': copy.deepcopy(p['variants']), 'native_media_items': copy.deepcopy(p['native_media_items']), 'source_locator': copy.deepcopy(p['source_locator']), 'inventory_ref': ref(FRESH_PATH, f'/products/{pi}'), 'scope': 'PUBLIC_COLLECTION_OBSERVED; NO_AUTHENTICATED_ADMIN_OR_PHYSICAL_VERIFICATION'}
    else:
        result['Squarespace'] = {'native_product_id': s.get('sq_id') or None, 'state': 'NOT_RETURNED_IN_THIS_CHECKED_PUBLIC_COLLECTION', 'hidden_draft_or_deletion_inferred': False}
    if s.get('sh_handle') in sh_by_handle:
        pi, p = sh_by_handle[s['sh_handle']]
        result['Shopify'] = {'handle': p['handle'], 'numeric_product_id': p['numeric_product_id'], 'description_html': p['body_html'], 'description_text': plain(p['body_html']), 'retained_description_equal_after_normalization': plain(p['body_html']) == plain(s['native_description']), 'status_raw': p['status_raw'], 'product_source_header_row': copy.deepcopy(p['source_header_row']), 'product_source_dates': copy.deepcopy(p['source_dates']), 'variants': [dict(copy.deepcopy(v), source_inventory_ref=ref(SH_VARIANTS_PATH, f'/{vi}')) for vi, v in sh_variants_by_handle[p['handle']]], 'inventory_ref': ref(SH_PRODUCTS_PATH, f'/{pi}'), 'scope': 'HISTORICAL_NATIVE_EXPORT_ONLY; CURRENT_LIVE_AND_DRAFT_INVENTORY_UNVERIFIED'}
    else:
        result['Shopify'] = {'handle': s.get('sh_handle') or None, 'numeric_product_id': None, 'numeric_variant_id': None, 'state': 'NO_RECORDED_HANDLE_IN_CHECKED_HISTORICAL_EXPORT', 'current_absence_inferred': False}
    return result

native_claims = {off: native_claim(off) for off in dict.fromkeys(e['offer_ref'] for _, o in assigned for _, e in edges_by_option[o['product_id']])}
entries = []
for option_index, o in assigned:
    cid = o.get('canonical_component_id') or o.get('canonical_design_id') or o['canonical_key'].split('|')[0]
    assert cid in NOTES, (cid, o['name'])
    sids = source_ids(o)
    edges = edges_by_option[o['product_id']]
    refs = [e['offer_ref'] for _, e in edges]
    coverage_index, coverage = photo_by_option[o['product_id']]
    claim_indices = [i for i, c in enumerate(model['claims']) if c['component_id'] in sids]
    config_indices = [i for i, c in enumerate(master['source_media_configuration_coverage']) if o['product_id'] in c.get('exact_supported_target_ids', []) or any(k in o['source_scopes'] for k in c.get('current_candidate_scope_keys', []))]
    review_indices = [i for i, v in enumerate(master['source_review_reconciliation']) if o['product_id'] in v.get('targets', [])]
    prior = o['current_listing_reconciliation']['overall_disposition']
    missing = []
    if prior == 'NO_SUPPORTED_INDIVIDUAL_ASSOCIATION_IN_CHECKED_SOURCES':
        disposition = 'NO_INDIVIDUAL_NATIVE_RECORD_SUPPORTED_IN_CHECKED_SCOPE'
        missing.append('No native individual product/variant binding in the 203-product public Squarespace collection or 136-product historical Shopify export. Hidden/admin/draft inventory remains unchecked.')
    elif prior == 'RELATED_FAMILY_ONLY_NO_INDIVIDUAL_MATCH':
        disposition = 'NO_EXACT_NATIVE_FINISH_BUILD_OR_INDIVIDUAL_UNIT_IN_CHECKED_FAMILY_RECORDS'
        missing.append('Exact design/finish/build/individual-unit native variant and SKU are not enumerated or uniquely bound by the related source records.')
    elif prior == 'GALLERY_OR_DRAFT_CONTEXT_SALE_UNIT_UNRESOLVED':
        disposition = 'GALLERY_OR_HISTORICAL_DRAFT_DOES_NOT_ESTABLISH_INDIVIDUAL_NATIVE_VARIANT'
        missing.append('A photo/gallery/draft association lacks a native option selecting this individual member/border/finish sale unit.')
    else:
        disposition = 'NAMED_FINISH_NATIVE_CANDIDATE_REQUIRES_EXACT_PHOTO_AND_CONFIGURATION_BINDING'
        missing.append('The candidate single native product needs source-photo/owner-finish scope binding; generic colour terms cannot establish this exact configuration.')
    if coverage['individual']['status'] != 'Available':
        missing.append('Existing image-coverage limitation: ' + coverage['individual']['status'] + '. ' + str(coverage['individual'].get('reason', coverage['individual'].get('note', ''))))
    draft = {'status': 'DRAFT_NOT_NATIVE; NO_PLATFORM_WRITE', 'proposed_product_group_id': 'DRAFT-PRODUCT-' + cid, 'grouping_basis': 'Immutable canonical component/design ID; separate retained size, finish and build options; no set-SKU reuse.', 'proposed_variant_reference': 'DRAFT-VARIANT-' + o['product_id'], 'proposed_sku': 'DRAFT-' + o['product_id'], 'sku_state': 'PROPOSED_ONLY_NOT_AN_EXISTING_PLATFORM_IDENTIFIER', 'title': o['name'], 'canonical_option_id': o['product_id'], 'canonical_component_id': o.get('canonical_component_id'), 'canonical_design_id': o.get('canonical_design_id'), 'canonical_key': o['canonical_key'], 'sale_unit': o['sale_unit'], 'six_working_fields': copy.deepcopy(o['master_fields']), 'six_working_fields_sha256': sha(json.dumps(o['master_fields'], sort_keys=True, ensure_ascii=False).encode()), 'fixing_choices': copy.deepcopy(o.get('offered_fixing_choices', [])), 'current_native_target': None, 'activation_condition': 'Check authenticated platform products/drafts for an existing exact individual variant before creating anything. Resolve only the stated source identity/configuration gap; no repeat blanket manufacture/name/specification approval.', 'media_condition': 'Use the already kept option-bound reference only; retain existing Group/Detail/Unbound-size restrictions and the separate moved-reference overlay.', 'physical_specs_verified': False, 'publication_performed': False}
    e = {'option_id': o['product_id'], 'master_option_index': option_index, 'canonical_key': o['canonical_key'], 'canonical_component_id': o.get('canonical_component_id'), 'canonical_design_id': o.get('canonical_design_id'), 'name': o['name'], 'family': o['family'], 'prior_disposition': prior, 'proposed_disposition': disposition, 'new_supported_native_matches': [], 'exact_logical_owner_working_configuration_match_supported': False, 'physical_configuration_verified': False, 'scope_reason': NOTES[cid], 'related_offer_refs': refs, 'source_native_claims_refs': [f'../worker-02/SOURCE_NATIVE_CLAIMS.json#/offers/{off}' for off in refs], 'source_evidence': {'frozen_option': ref(MASTER_PATH, f'/options/{option_index}'), 'kept_owner_decision_refs': owner_refs(o), 'source_component_ids': sids, 'source_component_refs': [ref(MODEL_PATH, '/components/' + str(i)) for i, c in enumerate(model['components']) if c['component_id'] in sids], 'source_claim_refs': [ref(MODEL_PATH, f'/claims/{i}') for i in claim_indices], 'review_scope_refs': [ref(MASTER_PATH, f'/source_review_reconciliation/{i}') for i in review_indices], 'source_media_configuration_refs': [ref(MASTER_PATH, f'/source_media_configuration_coverage/{i}') for i in config_indices], 'prior_edge_refs': [ref(MASTER_PATH, f'/current_listing_match_evidence/edges/{i}') for i, _ in edges], 'image_coverage_ref': ref(PHOTO_PATH, f'/coverage/{coverage_index}')}, 'current_primary_reference': {'file_id': o['file_id'], 'folder_id': o['folder_id'], 'image_url': o['image_url'], 'folder_url': o['folder_url']}, 'current_context_reference': {'file_id': o['current_listing_reconciliation'].get('context_image_file_id'), 'folder_id': o['current_listing_reconciliation'].get('context_folder_id'), 'image_url': o.get('context_image_url'), 'folder_url': o.get('context_folder_url')}, 'prior_visual_coverage': copy.deepcopy(coverage), 'custom_order_coverage': {'state': 'GENERAL_DOCUMENTED_ENQUIRY_CAPABILITY_NOT_AN_EXACT_NATIVE_VARIANT', 'explicit_catalogue_wide_metal_effect_customisation': True, 'general_white_standard_and_custom_quote_policy': True, 'exact_this_configuration_native_sku_established_by_generic_policy': False, 'evidence_ref': 'CUSTOM_ORDER_COVERAGE.json#/evidence', 'scope': 'Applies at maker-service/design-family enquiry level; no new chemistry, size, build, stock, per-member price, native option or exact cast is certified.'}, 'remaining_evidence_gaps': missing, 'platform_scope': {'Squarespace': '203 returned public products / 370 native variants; advertised208 discrepancy and hidden/admin/draft limits retained.', 'Shopify': '136 historical export products /160 variants; null unexported numeric IDs and quantity preserved; no current live/admin or storefront domain.'}, 'delta_vs_prior': {'prior_positive_association_changed': False, 'new_individual_native_link': False, 'reason_or_gap_clarified': True, 'catalogue_option_added_removed_or_merged': False, 'six_working_fields_changed': False}, 'draft_individual_listing': draft, 'review_status': 'PRELIMINARY_PENDING_VISUAL_BINDINGS_AND_MOVED_REFERENCE_OVERLAY'}
    entries.append(e)

old_extra = {p['native_product_id']: (i, p) for i, p in enumerate(old_ss_audit['entries'])}
offer_ids = {e['source_offer']['sq_id']: e['offer_ref'] for e in master['source_offer_edges'] if e['source_offer'].get('sq_id')}
inventory_coverage = []
for pi, p in enumerate(fresh['products']):
    pid = p['native_product_id']
    old = old_extra.get(pid)
    inventory_coverage.append({'native_product_id': pid, 'description_text': p['description_text'], 'source_locator': p['source_locator'], 'inventory_ref': ref(FRESH_PATH, f'/products/{pi}'), 'recorded_wall_offer_ref': offer_ids.get(pid), 'prior_outside_wall_audit_ref': ref(OLD_SS_AUDIT_PATH, f'/entries/{old[0]}') if old else None, 'prior_outside_wall_classification': old[1]['classification'] if old else None, 'prior_outside_wall_scope_reason': old[1]['classification_reason'] if old else None, 'new_unreviewed_native_record': pid not in offer_ids and old is None, 'title_only_identity_match_made': False})
assert not any(p['new_unreviewed_native_record'] for p in inventory_coverage)

save('OPTION_RESOLUTION_PRELIMINARY.json', {'schema': 'boldstone.nonwall-listing-resolution.v1', 'created_utc': datetime.now(timezone.utc).isoformat(), 'worker_number': 2, 'status': 'PRELIMINARY', 'frozen_master': ref(MASTER_PATH), 'fresh_public_inventory': ref(FRESH_PATH), 'counts': {'assigned_options': len(entries), 'prior_dispositions': dict(collections.Counter(e['prior_disposition'] for e in entries)), 'canonical_component_or_documented_design_groups': len(set((e['canonical_component_id'] or e['canonical_design_id']) for e in entries))}, 'entries': entries})
save('SOURCE_NATIVE_CLAIMS.json', {'schema': 'boldstone.native-offer-claims-for-nonwall-resolution.v1', 'offers': native_claims, 'no_set_specifications_allocated_to_individuals': True, 'historical_source_and_current_public_claims_preserved_separately': True})
save('CUSTOM_ORDER_COVERAGE.json', {'schema': 'boldstone.custom-order-coverage.v1', 'conclusion': 'Explicit custom-order metal effects, stone/colour/texture variations and water-feature capability are evidenced at maker-service/design-family level. They are not an exact native configuration/SKU assignment.', 'evidence': custom_order_evidence, 'source_text_documents_checked': [{'source': ref(p), 'lines': len(t.splitlines()), 'characters': len(t)} for p, t in DOC_TEXTS.items()], 'new_native_variant_or_material_certifications': 0})
save('CHECKED_INVENTORY_SCOPE.json', {'Squarespace': {'products': inventory_coverage, 'counts': fresh['counts'], 'new_native_product_ids_outside_previously_accounted_records': 0, 'public_inventory_complete_claim': False, 'limits': fresh['limits']}, 'Shopify': {'products_checked': len(sh_products), 'variants_checked': len(sh_variants), 'products_source': ref(SH_PRODUCTS_PATH), 'variants_source': ref(SH_VARIANTS_PATH), 'outside_wall_audit_source': ref(SH_AUDIT_PATH), 'source_receipts': ref(SH_RECEIPTS_PATH), 'current_live_or_draft_absence_claim': False, 'unexported_numeric_ids_inferred': False}, 'exact_native_identity_from_title_only': 0, 'source_record_product_counts_are_not_physical_stock': True})
save('SOURCE_RECEIPTS_PRELIMINARY.json', {'sources': list(SOURCES.values()), 'remote_calls_by_this_worker': 0, 'shared_writes': 0})
print(json.dumps({'status': 'PRELIMINARY_SAVED', 'entries': len(entries), 'sources': len(SOURCES), 'doc_texts': len(DOC_TEXTS), 'native_candidate_offers': len(native_claims)}, indent=2))
