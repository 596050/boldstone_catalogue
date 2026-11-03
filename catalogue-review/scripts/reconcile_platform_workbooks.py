"""Reconcile supplied platform snapshots; never treat them as live platform writes."""
from collections import Counter
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
import hashlib
import json
import re
import sys
import xml.etree.ElementTree as E
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'catalogue-review'))
sys.path.insert(0, str(ROOT / 'catalogue-review/scripts'))
from channel_content import marketplace_title, has_surface_effect, chairish_description, complete_description, appearance, CUSTOMISATION, SURFACE_VARIATION
from prepare_chairish_catalogue import chairish_dimensions

OUT = Path(sys.argv[1]).resolve()
read = lambda name: json.loads((OUT / name).read_text())
write = lambda name, value: (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
app = read('app-after.json')
products = {p['id']: p for p in app['products']}
fields = lambda p: {f['key']: f['value'] for f in p['fields'] + p['listing_fields']}
by_sku = {fields(p)['Seller SKU']: p for p in products.values()}
assert len(by_sku) == len(products)
raw = read('platform-inputs.json')
prepared = json.loads((ROOT / 'outputs/catalogue-marketplace-publication-20261101/chairish-current/prepared-native-drafts.json').read_text())
prior_dims = {r['catalogue_id']: r['structured_dimensions'] for r in prepared['records']}
# ECB 2 November 2026: currencies per EUR. Information/reference conversion.
fx = Decimal('1.1216') / Decimal('0.83580')
money = lambda v: float(Decimal(str(v)).quantize(Decimal('.01'), rounding=ROUND_HALF_UP))
price = lambda p: float(re.search(r'[\d,.]+', fields(p)['Price']).group().replace(',', ''))
col = lambda address: re.sub(r'\d', '', address)
slug = lambda text: re.sub(r'[^a-z0-9]+', '_', str(text).lower().replace('£', 'gbp').replace('$', 'usd')).strip('_')


def rows(sheet, header_index):
    headers = {col(k): v['value'] for k, v in sheet['rows'][header_index]['cells'].items()}
    return headers, [{headers[col(k)]: v['value'] for k, v in row['cells'].items()}
                     for row in sheet['rows'][header_index + 1:]]


def dimensions(product):
    source = fields(product)['Dimensions / depth']
    result = chairish_dimensions(source)
    old = prior_dims.get(product['id'])
    if old and old['source'] == source and old.get('orientation_review'):
        result = old
    cm = dict(result.get('values_cm', {}))
    for axis, value in result['values'].items():
        cm.setdefault(axis, money(Decimal(value) * Decimal('2.54')))
    # Older reviewed records predate values_cm. Keep exact centimetres from
    # the current source parser, including depth, before applying face axes.
    cm.update(chairish_dimensions(source).get('values_cm', {}))
    # Retain exact face dimensions from the saved photo-orientation assessment.
    if result.get('orientation_review'):
        cm.update(result['orientation_review']['face_cm'])
    return result, cm


def number(text):
    match = re.search(r'(?<!\w)(\d+(?:\.\d+)?)', str(text))
    return float(match.group(1)) if match else None


def rm_tier(cm, kg):
    size = sorted(cm, reverse=True)
    if kg <= 2 and all(a <= b for a, b in zip(size, [45, 35, 16])):
        return 3.75, 'Small parcel up to 2 kg'
    if all(a <= b for a, b in zip(size, [61, 46, 46])):
        for cap, charge in [(2, 5.70), (10, 7.55), (20, 12.25)]:
            if kg <= cap:
                return charge, f'Medium parcel up to {cap} kg'
    return None, 'Courier or freight quote required'


chairish_headers, chairish_rows = rows(raw['Chairish_Listings_Boldstone.xlsx']['sheets'][0], 0)
ebay_headers, ebay_rows = rows(raw['Boldstone_eBay_listings_2026-11-02 (2).xlsx']['sheets'][0], 1)
_, photo_rows = rows(raw['Boldstone_eBay_listings_2026-11-02 (2).xlsx']['sheets'][1], 0)
matched, excluded, issues = [], [], []


def issue(platform, native_id, ids, key, observed, expected, action, severity='Review'):
    issues.append({'platform': platform, 'native_id': str(native_id), 'catalogue_ids': ids,
                   'field': key, 'observed': observed, 'catalogue_or_reference': expected,
                   'action': action, 'severity': severity})


for platform, source_rows in [('chairish', chairish_rows), ('ebay', ebay_rows)]:
    for row in source_rows:
        sku = row.get('SKU') if platform == 'chairish' else row.get('Custom label (SKU)')
        ids = [by_sku[sku]['id']] if sku in by_sku else []
        if not ids:
            excluded.append({'platform': platform, 'sku': sku, 'row': row,
                             'reason': 'Outside the wall-sculpture component catalogue'})
            continue
        native_id = row['Chairish ID'] if platform == 'chairish' else row['Item ID']
        record = {'platform': platform, 'native_id': str(native_id), 'sku': sku,
                  'catalogue_ids': ids, 'source': row, 'targets': {}}
        p = products[ids[0]]
        f = fields(p)
        dim, cm = dimensions(p)
        target = record['targets']
        if len(ids) == 1:
            target['catalogue_title'] = marketplace_title(p)
            if row['Title'].casefold() != target['catalogue_title'].casefold():
                issue(platform, native_id, ids, 'Title', row['Title'], target['catalogue_title'],
                      'Use the current catalogue title, including Finish for applied effects.')
        else:
            target['catalogue_title'] = 'Boldstone Echo Rhythm I & II - Verdigris Finish Wall Sculpture Pair'
            target['sale_unit'] = 'Two separately identified catalogue components; shared pair offer'
            issue(platform, native_id, ids, 'Pair scope', row['Title'], target['sale_unit'],
                  'Keep this pair offer distinct. Pair packaging and postage require their own quote.')
        gbp = sum(price(products[pid]) for pid in ids)
        target['catalogue_price_gbp'] = money(gbp) if len(ids) == 1 else None
        target['catalogue_components_total_gbp'] = money(gbp) if len(ids) > 1 else None
        target['usd_per_gbp_reference'] = float(fx)
        target['fx_date'] = '2026-11-02'
        target['catalogue_price_usd'] = int((Decimal(str(gbp)) * fx).quantize(Decimal('1'), rounding=ROUND_HALF_UP)) if len(ids) == 1 else None
        target['manufacturing_cost_gbp'] = sum(products[pid]['costing']['manufacturing_cost'] for pid in ids)
        target['brand'] = f['Brand']
        target['material_description'] = 'Made from a gypsum-based material.'
        target['finish_description'] = appearance(p) if len(ids) == 1 else 'Verdigris surface-effect finish on both components'
        target['quantity_of_components'] = len(ids)
        target['dimensions_text'] = ' | '.join(fields(products[pid])['Dimensions / depth'] for pid in ids)
        target['weight_text'] = ' | '.join(fields(products[pid])['Weight'] for pid in ids)
        target['description'] = (chairish_description({'sku': sku, 'description_text': f['Description'],
            'surface_effect': has_surface_effect(p), 'product_type': f['Product type']},
            dispatch_days=10 if str(f['Availability']).lower().startswith('made to order') or any(q['status']=='freight_quote_required' for q in p['us_shipping']['quotes']) else 3)
            if platform == 'chairish' else complete_description(p, sku, 3, 'ebay')) if len(ids) == 1 else ''
        target['dimension_basis'] = dim['basis'] if len(ids) == 1 else 'Individual component dimensions; packed pair not verified'
        for axis in ('width', 'depth', 'height'):
            target[axis + '_cm'] = cm.get(axis) if len(ids) == 1 else None
            target[axis + '_in'] = number(dim['values'].get(axis)) if len(ids) == 1 else None
        if len(ids) == 1 and dim['missing_axes']:
            issue(platform, native_id, ids, 'Dimension orientation', 'Unresolved axes', ', '.join(dim['missing_axes']),
                  'Confirm display orientation. Do not substitute guessed width/height.')
        shipping = p['us_shipping']
        target['packed_cm_estimate'] = ' × '.join(str(n) for n in shipping['packed_cm']) if len(ids) == 1 else ''
        target['packed_kg_estimate'] = shipping['packed_kg'] if len(ids) == 1 else None
        target['packing_basis'] = shipping['packing_basis'] if len(ids) == 1 else 'Pair packing must be measured separately'
        quotes = shipping['quotes']
        for q in quotes:
            target['us_' + q['destination']['id'] + '_estimate_gbp'] = q.get('estimate_gbp') if len(ids) == 1 else None
        target['us_quote_basis'] = 'App UPS list-rate planning budgets only; packing, artwork cover, duties/taxes and address charges excluded. Obtain an actual all-in quote.'
        if platform == 'chairish':
            observed_price = row['Price (USD)']
            target['source_price_gbp_equivalent'] = money(Decimal(str(observed_price)) / fx)
            if abs(observed_price - target['catalogue_price_usd']) > 1:
                issue(platform, native_id, ids, 'Price (USD)', observed_price, target['catalogue_price_usd'],
                      'Use the catalogue GBP price converted at the documented reference rate; platform commission is separate.')
            for axis in ('width', 'depth', 'height'):
                if axis not in cm:
                    continue
                for unit, tolerance in [('cm', .10), ('in', .015)]:
                    observed = row.get(axis.title() + ' (' + unit + ')')
                    expected = target[axis + '_' + unit]
                    if observed in ('', None) or abs(float(observed) - expected) > tolerance:
                        issue(platform, native_id, ids, axis.title() + ' (' + unit + ')', observed, expected,
                              'Use catalogue dimensions in the reviewed display orientation. Convert using 2.54 cm per inch.')
            for axis in ('width', 'depth', 'height'):
                inches, cms = row.get(axis.title() + ' (in)'), row.get(axis.title() + ' (cm)')
                if isinstance(inches, (int, float)) and isinstance(cms, (int, float)) and abs(inches * 2.54 - cms) > .10:
                    issue(platform, native_id, ids, axis.title() + ' unit conversion', f'{inches} in / {cms} cm', inches * 2.54,
                          'Correct the inches/centimetres conversion.')
            postage = row.get('Delivery charge to buyer (USD)')
            target['delivery_charge_gbp_equivalent'] = money(Decimal(str(postage)) / fx) if isinstance(postage, (int, float)) else None
            budgets = [q['estimate_gbp'] for q in quotes if isinstance(q.get('estimate_gbp'), (int, float))]
            if postage in ('', None):
                shipping_action = 'No buyer delivery charge recorded. Obtain and enter an inclusive destination quote; blank is not verified free delivery.'
            elif budgets and target['delivery_charge_gbp_equivalent'] < min(budgets):
                shipping_action = 'Flat charge is below both app US carrier list-rate budgets before packing, artwork cover and import costs. A discounted all-in carrier quote is required to substantiate it.'
            else:
                shipping_action = 'Flat charge has no destination-specific all-in quote in the supplied file. Check packing, carrier, artwork cover, duties/taxes and delivery location before publication.'
            if any(q['status'] == 'freight_quote_required' for q in quotes):
                shipping_action = 'Estimated package exceeds UPS parcel limits. Obtain a crate/freight quote inclusive of duties, taxes and fees; do not apply a parcel flat rate.'
            target['shipping_review'] = shipping_action
            issue(platform, native_id, ids, 'International delivery', postage, target['us_quote_basis'], shipping_action,
                  'High' if postage in ('', None) or 'below both' in shipping_action or 'freight' in shipping_action else 'Review')
            for source_key in ['Proceeds at price (USD)', 'Proceeds at reserve (USD)', 'Proceeds at auction reserve (USD)', 'Proceeds at trade price (USD)']:
                proceeds = row.get(source_key)
                if isinstance(proceeds, (int, float)) and proceeds / float(fx) < target['manufacturing_cost_gbp']:
                    issue(platform, native_id, ids, source_key, proceeds, money(target['manufacturing_cost_gbp'] * float(fx)),
                          'Recorded net proceeds are below catalogue manufacturing cost before packaging/shipping. Review the discount/commission economics.', 'High')
        else:
            observed_price = row['Price (£)']
            if len(ids) == 1 and abs(observed_price - gbp) > .011:
                issue(platform, native_id, ids, 'Price (GBP)', observed_price, money(gbp),
                      'Align the seller item price with the catalogue. The buyer-protection fee is additional, not seller revenue.')
            elif len(ids) > 1:
                issue(platform, native_id, ids, 'Pair price comparison', observed_price, money(gbp),
                      'The reference is the sum of both catalogue components, not an approved bundle price. Review the pair premium separately; no automatic price target is assigned.')
            if len(ids) == 1:
                for axis in ('width', 'height', 'depth'):
                    if axis not in cm:
                        continue
                    observed = row.get('Item ' + axis.title())
                    if number(observed) is None or abs(number(observed) - cm[axis]) > .10:
                        issue(platform, native_id, ids, 'Item ' + axis.title(), observed, cm[axis],
                              'Use the catalogue axis in cm; keep depth distinct from height and length.')
                kg = shipping['packed_kg']; size = sorted(shipping['packed_cm'], reverse=True)
                max_kg_match = re.search(r'up to (\d+) kg', row.get('Package size', ''))
                max_kg = float(max_kg_match.group(1)) if max_kg_match else None
                wrong_size = any(a > b for a, b in zip(size, [61, 46, 46]))
                wrong_weight = max_kg is not None and kg > max_kg
                if wrong_size or wrong_weight:
                    action = 'Selected parcel does not fit the app packing estimate. Select an eligible larger carrier option or obtain a measured courier/freight quote.'
                    issue(platform, native_id, ids, 'Selected parcel', row['Package size'], f'{shipping["packed_cm"]} cm / {kg} kg', action, 'High')
                else:
                    action = 'Packing estimate fits the selected tier; verify actual packed measurements. Buyer-paid eBay label price is platform-set and may differ from retail Royal Mail rates.'
                target['domestic_shipping_review'] = action
                tariff, tier = rm_tier(size, kg)
                target['royal_mail_tracked48_online_gbp'] = tariff
                target['royal_mail_tier'] = tier
            else:
                issue(platform, native_id, ids, 'Pair shipping', row['Package size'], 'Two sculptures, unverified combined packed size/weight',
                      'The file says 8 kg, while the catalogue upper weights total 10 kg before packaging. Measure the packed pair and select an eligible tier.', 'High')
                target['domestic_shipping_review'] = 'Measure the packed pair. No individual-piece parcel assumption can verify the pair charge.'
                if row.get('Number of Items in Set') in ('', None, 'n/a'):
                    issue(platform, native_id, ids, 'Number of Items in Set', row.get('Number of Items in Set'), 2,
                          'The Echo pair supplies two components. Keep order quantity distinct from the number of sculptures in the set.')
            international = row.get('International postage', '')
            if 'no services added' in str(international).lower():
                issue(platform, native_id, ids, 'International postage', international, 'No usable international service/rate evidenced',
                      'Add a supported international delivery service or verify Global Shipping Programme eligibility and buyer checkout charges. An enabled switch alone is insufficient.', 'High')
            target['international_shipping_review'] = 'No destination-specific international charge verified from the supplied snapshot. Do not charge a UK-only amount for overseas delivery.'
        matched.append(record)

assert sum(r['platform'] == 'chairish' for r in matched) == 176
assert sum(r['platform'] == 'ebay' for r in matched) == 18
assert len({r['native_id'] for r in matched if r['platform'] == 'chairish'}) == 176
write('matched-platform-records.json', matched)
write('excluded-non-wall-records.json', excluded)
write('consistency-issues.json', issues)
content_checks = []
for record in matched:
    description = str(record['source']['Description'])
    effect = has_surface_effect(products[record['catalogue_ids'][0]])
    content_checks.append({'platform': record['platform'], 'native_id': record['native_id'],
        'gypsum_material_present': 'gypsum' in description.lower(),
        'customisation_and_sally_price_present': CUSTOMISATION in description,
        'handmade_finish_disclosure_present_where_required': not effect or SURFACE_VARIATION in description,
        'brand_source_value': record['source'].get('Brand'),
        'catalogue_brand': 'Boldstone',
        'description_format_differences_are_not_automatically_errors': True})
assert all(c['gypsum_material_present'] and c['customisation_and_sally_price_present'] and c['handmade_finish_disclosure_present_where_required'] for c in content_checks)
write('description-content-checks.json', {'status': 'PASS_REQUIRED_MATERIAL_AND_OWNER_DISCLOSURES', 'records': content_checks})
write('reference-sources.json', {'fx': {'usd_per_eur': 1.1216, 'gbp_per_eur': .83580,
    'usd_per_gbp': float(fx), 'date': '2026-11-02', 'url': 'https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.en.html',
    'use': 'Reference conversion for reconciliation, not a guaranteed settlement rate'},
    'centimetres_per_inch': 2.54,
    'ebay': 'https://www.ebay.co.uk/help/selling/posting-items/setting-postage-options/simple-delivery?id=5575',
    'chairish': 'https://support.chairish.com/hc/en-us/articles/44288174467601-Purchasing-from-a-Seller-Outside-the-US',
    'royal_mail': 'https://www.royalmail.com/sending/uk/tracked-48',
    'ups': 'https://www.ups.com/gb/en/support/shipping-support/shipping-costs-rates/fuel-surcharges'})
summary = {'catalogue_components': len(products), 'chairish_matched': 176, 'ebay_individual_matched': 18,
           'ebay_pair_matched': 0, 'outside_scope': len(excluded), 'surface_effect_components': 73,
           'issues': len(issues), 'issues_by_platform_field': dict(Counter(i['platform'] + ': ' + i['field'] for i in issues)),
           'native_platform_changes': 0, 'shipping_rates_verified_as_final_charges': 0}
write('reconciliation-summary.json', summary)
print(json.dumps(summary, indent=2))
