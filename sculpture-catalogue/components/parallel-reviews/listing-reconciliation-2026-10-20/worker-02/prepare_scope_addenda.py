from pathlib import Path
from datetime import datetime, timezone
from collections import Counter
from html.parser import HTMLParser
import hashlib
import html
import json
import re

W = Path(__file__).resolve().parent
NOW = datetime.now(timezone.utc).isoformat()
P = json.loads((W / 'shopify_products.json').read_text())
V = json.loads((W / 'shopify_variants.json').read_text())
MASTER_PATH = W.parent / 'inputs/master-register.json'
M = json.loads(MASTER_PATH.read_text())
OFFERS = {e['source_offer']['sh_handle']: e['source_offer']
          for e in M['source_offer_edges'] if e['source_offer'].get('sh_handle')}


class Text(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)


def plain(value):
    t = Text()
    t.feed(value or '')
    return re.sub(r'\s+', ' ', ' '.join(t.parts)).strip()


def write(name, value):
    (W / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


OUTSIDE = []
for p in P:
    if p['in_preserved_wall_subset']:
        continue
    text = plain(p['body_html'])
    lower = text.casefold()
    kind = p['type_raw']
    evidence = None
    if kind == 'Greeting & Note Cards' and 'card' in lower and 'printed on' in lower and 'envelope' in lower:
        state = 'EXCLUDED_GREETING_CARD_MERCHANDISE'
        evidence = re.search(r'Beautiful Greetings Card printed on.*?envelope', text, re.I).group(0)
        reason = 'The native body sells a printed greeting card and envelope with paper/card-stock and card-size details. A sculpture subject in the title or brand wording does not make the sculpture the sale unit.'
    elif kind == 'Photography' and 'photographic print' in lower and 'dibond' in lower:
        state = 'EXCLUDED_PHOTOGRAPHIC_PRINT'
        evidence = text
        reason = 'The native body explicitly sells a photographic print on aluminium Dibond backing, not a carved/cast sculpture. The metal backing does not change the depicted image into a sculpture sale.'
    elif 'painted world paintings' in lower and ('cotton rag paper' in lower or '100% cotton' in lower):
        state = 'EXCLUDED_PAINTING_OR_WORK_ON_PAPER'
        evidence = text
        reason = 'The native body describes a mounted Painted World watercolour/ink work on cotton rag paper. Its painting/edition/print wording is retained without reclassifying it as a physical sculpture.'
    elif kind == 'Prints' and ('print' in lower or 'marbled moons' in lower) and ('paper' in lower or 'backing board' in lower or 'mount board' in lower):
        state = 'EXCLUDED_ART_PRINT_ON_PAPER'
        evidence = text
        reason = 'The native body identifies a paper print or mounted paper artwork with paper/backing-board details. The moon, spiral or natural-form subject does not establish a sculpture offer.'
    else:
        state = 'PLAUSIBLE_UNLINKED_PHYSICAL_SCULPTURE_CANDIDATE_OR_SCOPE_UNRESOLVED'
        evidence = text
        reason = 'No sufficiently explicit non-sculpture sale-unit wording was established by this bounded type/title/body review. Requires individual source review; no canonical identity match proposed.'
    OUTSIDE.append({
        'handle': p['handle'], 'title': p['title'], 'native_type_raw': kind,
        'native_category_raw': p['product_category'],
        'source_header_row': p['source_header_row'],
        'source_status_raw': p['status_raw'], 'source_date_limits': p['source_dates'],
        'source_skus_raw': [v['sku_raw'] for v in V if v['handle'] == p['handle']],
        'option_tuples': [v['option_tuple'] for v in V if v['handle'] == p['handle']],
        'variant_count': sum(v['handle'] == p['handle'] for v in V),
        'scope_disposition': state, 'evidence_excerpt_from_native_body': evidence,
        'native_body_text': text, 'reason': reason,
        'classification_uses_native_body_not_title_or_handle_alone': True,
        'native_type_body_caveat': ('Native Type is Prints, while the body describes an edition-one watercolour/ink painting on paper.' if kind == 'Prints' and state == 'EXCLUDED_PAINTING_OR_WORK_ON_PAPER' else None),
        'canonical_product_or_option_match': None,
        'current_live_presence_or_absence_inferred': False,
        'physical_sculpture_candidate': state.startswith('PLAUSIBLE_'),
    })

assert len(OUTSIDE) == 98
assert not any(x['physical_sculpture_candidate'] for x in OUTSIDE)
write('UNLINKED_SCOPE_AUDIT.json', {
    'schema': 'boldstone.shopify-nonwall-native-scope-audit.v1', 'prepared_utc': NOW,
    'scope': 'All 98 product headers outside the previously preserved 38-handle wall subset. Every native type, title and complete body was parsed; explicit repeated body descriptions determine the exclusions, with no title-only canonical matching.',
    'counts': {'all_native_products': 136, 'preserved_wall_products': 38,
               'outside_preserved_wall_subset': len(OUTSIDE),
               'outside_variant_rows': sum(x['variant_count'] for x in OUTSIDE),
               'native_type_counts': dict(Counter(x['native_type_raw'] for x in OUTSIDE)),
               'scope_dispositions': dict(Counter(x['scope_disposition'] for x in OUTSIDE)),
               'plausible_unlinked_physical_sculpture_candidates': 0,
               'unresolved_scope_rows': 0,
               'native_prints_type_with_painting_on_paper_body': sum(bool(x['native_type_body_caveat']) for x in OUTSIDE)},
    'products': OUTSIDE,
    'coverage_result': 'All 136 native snapshot products accounted for: 38 existing wall-source handles and 98 explicitly non-sculpture sale units. This does not certify completeness or absence in the current live account.',
})

# Each row is based on the complete native description read for that exact handle.
# The first number is a native explicit multi-part count, or null for singular wording/draft.
# Size scopes follow the order of literal size expressions in the native body.
SCOPE = {
    'O012': (None, 'ONE_SCULPTURE_DESCRIBED', ['ONE_SCULPTURE']),
    'SH-DRAFT': (None, 'UNKNOWN_BLANK_NATIVE_DESCRIPTION', []),
    'O013': (2, 'EXPLICIT_TWO_PART_SET', ['FIRST_SIZE_IN_TWO_PART_DESCRIPTION_NOT_EXPLICIT_EACH', 'WHOLE_SET_EXCLUDING_GAP']),
    'O014': (None, 'ONE_SCULPTURE_DESCRIBED', ['ONE_SCULPTURE']),
    'O015': (None, 'ONE_SCULPTURE_DESCRIBED', ['ONE_SCULPTURE_SOURCE_IDENTITY_APPLICABILITY_UNRESOLVED']),
    'O016': (None, 'ONE_SCULPTURE_DESCRIBED', ['ONE_SCULPTURE']),
    'O017': (4, 'EXPLICIT_FOUR_PART_SET', ['EACH_PART_DESCRIPTION_CONTEXT', 'WHOLE_SET_EXCLUDING_GAPS']),
    'O018': (2, 'EXPLICIT_TWO_PART_SET', ['EACH_PART_EXPLICIT', 'WHOLE_SET_EXCLUDING_GAP']),
    'O019': (2, 'EXPLICIT_TWO_PART_SET', ['EACH_PART_EXPLICIT', 'WHOLE_SET']),
    'O020': (2, 'EXPLICIT_TWO_PART_SET', ['EACH_PART_EXPLICIT', 'WHOLE_SET']),
    'O021': (2, 'EXPLICIT_TWO_PART_SET', ['EACH_PART_EXPLICIT', 'WHOLE_SET_EXCLUDING_GAP']),
    'O022': (None, 'ONE_SCULPTURE_DESCRIBED', ['ONE_SCULPTURE']),
    'O023': (None, 'ONE_SCULPTURE_DESCRIBED', ['ONE_SCULPTURE']),
    'O024': (2, 'EXPLICIT_TWO_PART_SET', ['FIRST_SIZE_IN_TWO_PART_DESCRIPTION_NOT_EXPLICIT_EACH', 'WHOLE_SET_EXCLUDING_GAP']),
    'O025': (3, 'EXPLICIT_THREE_PART_SET', ['FIRST_SIZE_IN_THREE_PART_DESCRIPTION_NOT_EXPLICIT_EACH', 'WHOLE_SET_EXCLUDING_GAPS']),
    'O026': (None, 'ONE_SCULPTURE_DESCRIBED', ['ONE_SCULPTURE']),
    'O027': (3, 'EXPLICIT_THREE_PART_SET', ['EACH_PART_EXPLICIT', 'WHOLE_SET_EXCLUDING_GAPS']),
    'O028': (2, 'EXPLICIT_TWO_PART_SET', ['EACH_PART_EXPLICIT', 'WHOLE_SET_EXCLUDING_GAP']),
    'O029': (2, 'EXPLICIT_TWO_PART_SET', ['EACH_PART_EXPLICIT', 'WHOLE_SET']),
    'O030': (5, 'EXPLICIT_FIVE_PART_SET', ['EACH_PART_EXPLICIT', 'WHOLE_SET']),
    'O031': (3, 'EXPLICIT_THREE_PART_SET', ['EACH_PART_EXPLICIT', 'WHOLE_SET_EXCLUDING_GAPS']),
    'O032': (3, 'EXPLICIT_THREE_PART_SET', ['EACH_PART_EXPLICIT', 'WHOLE_SET_EXCLUDING_GAPS']),
    'O033': (2, 'EXPLICIT_TWO_PART_SET', ['EACH_PART_EXPLICIT', 'WHOLE_SET_EXCLUDING_GAP']),
    'O034': (2, 'EXPLICIT_TWO_PART_SET_UNEQUAL_SIZES', ['FIRST_PART_UNNUMBERED', 'SECOND_PART_UNNUMBERED_WITH_UNIT_TYPO', 'WHOLE_SET_EXCLUDING_GAP']),
    'O035': (2, 'EXPLICIT_TWO_PART_SET', ['EACH_PART_EXPLICIT', 'WHOLE_SET_EXCLUDING_GAP']),
    'O036': (1, 'EXPLICIT_SINGLE_SCULPTURE', ['ONE_SCULPTURE']),
    'O037': (None, 'ONE_SCULPTURE_DESCRIBED', ['ONE_SCULPTURE']),
    'O038': (None, 'ONE_SCULPTURE_DESCRIBED_SOLD_WORK', ['ONE_SCULPTURE']),
    'O039': (None, 'ONE_SCULPTURE_DESCRIBED', ['ONE_SCULPTURE']),
    'O040': (None, 'ONE_SCULPTURE_DESCRIBED', ['ONE_SCULPTURE']),
    'O041': (2, 'EXPLICIT_TWO_PART_SET', ['EACH_PART_EXPLICIT_WITH_SPACED_NUMBER_TYPO', 'WHOLE_SET_EXCLUDING_GAP']),
    'O042': (None, 'ONE_SCULPTURE_DESCRIBED_SOLD_WORK', ['ONE_SCULPTURE']),
    'O043': (2, 'EXPLICIT_TWO_PART_SET', ['EACH_PART_EXPLICIT', 'WHOLE_SET_EXCLUDING_GAP']),
    'O044': (3, 'EXPLICIT_THREE_PART_SET', ['EACH_PART_EXPLICIT', 'WHOLE_SET_EXCLUDING_GAPS']),
    'O045': (None, 'ONE_SCULPTURE_DESCRIBED', ['ONE_SCULPTURE']),
    'O046': (None, 'ONE_SCULPTURE_DESCRIBED', ['ONE_SCULPTURE_SOURCE_VERSION_APPLICABILITY_UNRESOLVED']),
    'O047': (1, 'EXPLICIT_SINGLE_PIECE', ['ONE_SCULPTURE']),
    'O048': (2, 'EXPLICIT_TWO_PART_SET', ['EACH_PART_EXPLICIT', 'WHOLE_SET_EXCLUDING_GAP']),
}
SPECIAL = {
    'O015': 'Native title/body describe Concave Moon at 50×50×6cm. The handle is copy-of-moonwave. This does not bind the source dimensions to current MCP4 25cm or the conflicting Moon Water Catcher photo; current exact depiction applicability remains separate.',
    'O034': 'Native text states unequal part sizes and literally uses 55xm for the second part. Preserve that unit typo. The native body does not assign current Bone Spiral One/Two numbered identities. Do not divide the set price or mass or apply whole55×85×7cm to either individual.',
    'O038': 'Native body explicitly says SOLD while native product status is active/published. Preserve both as dated platform/text claims; they do not verify current stock or a new commission price.',
    'O039': 'The native size is 35×20×5cm and gold leaf is explicitly described. Retain this source version without overriding a different current working size/depth or inferring a second manufactured product.',
    'O041': 'The native each-part text literally uses 5 0cm. Preserve the spaced-number typo separately from the clear overall50×60×7cm claim. No automatic member allocation or correction is applied.',
    'O042': 'Native body explicitly says SOLD while native product status remains active/published. Gold-leaf wording is for this source product, not a second panel in a room scene.',
    'O046': 'Native body states 30×30×5cm and gold leaf. It does not name a binder or fixing. Do not apply a current45×40cm working scope to this historical size claim or invent a separate product from the discrepancy.',
    'SH-DRAFT': 'Blank native body and SKU, zero source price/grams, status draft and Published false. Retained triptych photo interpretation is separate and does not establish an individual offer or current draft inventory.',
}
number = r'\d+(?:\.\d+)?(?:\s+\d+)?'
RX = re.compile(rf'(?P<n1>{number})\s*(?P<u1>cm|xm)\s*[x×]\s*(?P<n2>{number})\s*(?P<u2>cm|xm)\s*[x×]\s*(?P<n3>{number})\s*(?P<u3>cm|xm)', re.I)
CLAIMS = []
for p in P:
    if not p['in_preserved_wall_subset']:
        continue
    o = OFFERS[p['handle']]
    ref = o['offer_ref']
    count, unit, scopes = SCOPE[ref]
    text = plain(p['body_html'])
    retained = plain(o.get('native_description', ''))
    matches = list(RX.finditer(text))
    assert len(matches) == len(scopes), (ref, text, [m.group(0) for m in matches], scopes)
    sizes = []
    for match, scope in zip(matches, scopes):
        vals = [match.group('n' + str(i)) for i in [1, 2, 3]]
        units = [match.group('u' + str(i)).lower() for i in [1, 2, 3]]
        valid = all(u == 'cm' for u in units) and all(re.fullmatch(r'\d+(?:\.\d+)?', n) for n in vals)
        sizes.append({'native_quote': match.group(0), 'ordered_numbers_as_source_text': vals,
                      'units_as_source_text': units,
                      'literal_cm_values_if_unambiguous': [float(n) if '.' in n else int(n) for n in vals] if valid else None,
                      'scope': scope, 'axis_order_not_assumed': True,
                      'source_typography_or_unit_issue': not valid,
                      'source_values_not_independent_physical_measurements': True})
    lower = text.casefold()
    finish = ('white marble stone finish' if 'white marble stone finish' in lower else
              'Verdigris copper and rust finish' if 'verdigris copper and rust finish' in lower else
              'gold leaf' if 'gold leaf' in lower else None)
    vs = [v for v in V if v['handle'] == p['handle']]
    CLAIMS.append({
        'handle': p['handle'], 'title': p['title'], 'source_offer_ref': ref,
        'native_skus_raw': [v['sku_raw'] for v in vs],
        'frozen_retained_offer_sku': o.get('sku'),
        'native_header_row': p['source_header_row'],
        'native_body_html': p['body_html'], 'native_body_text': text,
        'native_body_sha256': hashlib.sha256(p['body_html'].encode()).hexdigest(),
        'retained_source_offer_description': o.get('native_description'),
        'retained_description_source_scope': 'Frozen master source_offer.native_description. This comparison does not fetch or assume current Squarespace copy.',
        'native_equals_retained_body_after_html_whitespace_normalization': text == retained,
        'native_sale_unit': {'classification': unit, 'explicit_number_of_parts': count,
                             'number_count_is_not_mould_or_stock_count': True,
                             'singular_wording_is_not_an_explicit_number': count is None},
        'native_size_claims': sizes,
        'native_current_finish_wording': finish,
        'native_binder_explicitly_identified': False,
        'native_fixing_or_hardware_explicitly_identified': False,
        'native_sold_wording': 'SOLD' in text,
        'native_generic_other_sizes_or_surface_effects_offer': 'different sizes' in lower,
        'generic_custom_offer_is_not_an_enumerated_current_variant': True,
        'native_variant_price_and_grams': [{'variant_key': v['variant_key'], 'price_raw': v['price_raw'],
                                             'currency': v['currency'], 'grams_raw': v['grams_raw'],
                                             'quantity': v['inventory_quantity']} for v in vs],
        'status_snapshot': p['status_raw'], 'published_snapshot': p['published_raw'],
        'applicability_note': SPECIAL.get(ref, 'Literal native source claims for this exact handle are retained. No current cast, individual named component, binder, fixing, stock or current platform copy is certified by the source text.'),
        'whole_set_values_divided_or_transferred': False,
        'new_canonical_identity_match': None,
    })

assert len(CLAIMS) == 38 and all(c['native_equals_retained_body_after_html_whitespace_normalization'] for c in CLAIMS)
assert sum(c['native_sale_unit']['explicit_number_of_parts'] is not None and c['native_sale_unit']['explicit_number_of_parts'] > 1 for c in CLAIMS) == 21
write('NATIVE_BODY_AND_SALE_UNIT_CLAIMS.json', {
    'schema': 'boldstone.shopify-native-body-sale-unit-size-claims.v1', 'prepared_utc': NOW,
    'counts': {'wall_handles': 38, 'native_body_equals_frozen_retained_description': 38,
               'explicit_multi_part_offers': 21, 'blank_native_draft_description': 1,
               'literal_native_typography_or_unit_issues': sum(s['source_typography_or_unit_issue'] for c in CLAIMS for s in c['native_size_claims'])},
    'claim_scope': 'Native historical Shopify body only, independently parsed from the recovered CSV. No current Squarespace page, current catalogue working correction or whole-set allocation is inherited.',
    'products': CLAIMS,
    'limits': ['Equality to retained historical text does not validate current live product/draft inventory or exact depicted product identity.',
               'White marble stone finish is a finish label, not an AC730 or binder certificate.',
               'Raw native set prices and weights remain set/offer values and are never divided into components.',
               '5 0cm and55xm typography is preserved; unambiguous numeric measurements are not silently substituted.'],
})
print(json.dumps({'outside_scope': dict(Counter(x['scope_disposition'] for x in OUTSIDE)),
                  'outside_products': len(OUTSIDE), 'outside_variants': sum(x['variant_count'] for x in OUTSIDE),
                  'native_wall_body_claims': len(CLAIMS), 'all_retained_bodies_match': True}, indent=2))
