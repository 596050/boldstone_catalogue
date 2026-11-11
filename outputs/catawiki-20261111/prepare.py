"""Read-only source extraction and Catawiki submission preparation. No platform writes."""
from pathlib import Path
from collections import Counter, defaultdict
from decimal import Decimal, ROUND_CEILING
import csv
import hashlib
import html
import json
import re
import shutil
import sqlite3
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path('/Users/tprice/Documents/boldstone')
OUT = ROOT / 'outputs/catawiki-20261111'
SOURCE = Path(json.loads((ROOT / 'sculpture-catalogue/current-master.json').read_text())['current_app_review_workbook']['path'])
NS = {'m': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main',
      'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}
EXISTING = {'BSI-C02D6DF365D3': '108492920', 'BSI-3635E3DC3434': '108497870'}


def read_sheet(z, number, header_row):
    strings = []
    if 'xl/sharedStrings.xml' in z.namelist():
        strings = [''.join(n.itertext()) for n in ET.fromstring(z.read('xl/sharedStrings.xml'))]
    rel_path = f'xl/worksheets/_rels/sheet{number}.xml.rels'
    rel = {n.attrib['Id']: n.attrib['Target'] for n in ET.fromstring(z.read(rel_path))} if rel_path in z.namelist() else {}
    root = ET.fromstring(z.read(f'xl/worksheets/sheet{number}.xml'))
    links = {n.attrib['ref']: rel.get(n.attrib.get('{' + NS['r'] + '}id'), '')
             for n in root.findall('m:hyperlinks/m:hyperlink', NS)}
    rows = {}
    for row in root.findall('m:sheetData/m:row', NS):
        vals = {}
        for c in row:
            col = re.match(r'[A-Z]+', c.attrib['r'])[0]
            v = c.find('m:v', NS)
            if c.attrib.get('t') == 's' and v is not None:
                value = strings[int(v.text)]
            elif c.attrib.get('t') == 'inlineStr':
                value = ''.join(c.find('m:is', NS).itertext())
            elif v is not None:
                value = v.text
                if c.attrib.get('t') == 'b': value = value == '1'
                elif c.attrib.get('t') not in ('str', 'e'):
                    try: value = float(value)
                    except (ValueError, TypeError): pass
            else:
                value = None
            vals[col] = {'value': value, 'url': links.get(c.attrib['r'], '')}
        rows[int(row.attrib['r'])] = vals
    headers = {col: cell['value'] for col, cell in rows[header_row].items() if cell['value']}
    return [{headers[c]: {'value': row.get(c, {}).get('value'), 'url': row.get(c, {}).get('url', '')}
             for c in headers} for n, row in rows.items() if n > header_row]


def val(row, key): return row.get(key, {}).get('value')
def url(row, key): return row.get(key, {}).get('url', '')
def ceil_eur(value): return int(value.to_integral_value(rounding=ROUND_CEILING))
def fixed_fee(price):
    return Decimal(1 if price < 150 else 2 if price < 300 else 3 if price < 500 else 5 if price < 1000 else 10)


with zipfile.ZipFile(SOURCE) as z:
    products = read_sheet(z, 1, 7)
    images = read_sheet(z, 2, 7)
    channel = {val(r, 'Catalogue ID'): r for r in read_sheet(z, 9, 4)}

ecb = ET.fromstring((OUT / 'ecb-daily.xml').read_bytes())
fx_date = next(n.attrib['time'] for n in ecb.iter() if 'time' in n.attrib)
gbp_per_eur = Decimal(next(n.attrib['rate'] for n in ecb.iter() if n.attrib.get('currency') == 'GBP'))
selected = defaultdict(list)
for r in images:
    if val(r, 'Listing') == 'Yes' and val(r, 'Excluded') != 'Yes' and val(r, 'In situ') != 'Yes':
        u = url(r, 'Website gallery image')
        if u.startswith('https://'):
            selected[val(r, 'Product ID')].append({'image_id': val(r, 'Stable image ID'),
                'name': val(r, 'File name'), 'url': u, 'dropbox_url': url(r, 'Image'),
                'types': val(r, 'Image types'), 'primary': val(r, 'Primary listing') == 'Yes',
                'order': val(r, 'Listing order') or 0, 'alt': val(r, 'Alt text'),
                'width_px': val(r, 'Original width (px)'), 'height_px': val(r, 'Original height (px)')})

template = Path('/Users/tprice/Downloads/Sculptures & Statues_template.csv')
dictionary = Path('/Users/tprice/Downloads/Sculptures & Statues_dictionary.csv')
headers = next(csv.reader(template.open(encoding='utf-8-sig')))
shutil.copyfile(template, OUT / 'official-template.csv')
shutil.copyfile(dictionary, OUT / 'official-dictionary.csv')
new_rows, records = [], []
for r in products:
    if val(r, 'pinterest_feed_eligible') not in (True, 'true', 'True', 1):
        continue
    pid = val(r, 'Product ID')
    ch = channel.get(pid, {})
    title = val(r, 'Retail / website name')
    sku = val(r, 'SKU')
    retail = Decimal(str(val(r, 'Price (GBP)')))
    eur = retail / gbp_per_eur
    catawiki_target_gbp = val(r, 'catawiki_target_price_gbp')
    catawiki_target_eur = val(r, 'catawiki_target_price_eur')
    # Planning assumptions only: 20% VAT on platform fees, 3% FX allowance.
    # Target net product proceeds equal current catalogue retail; packaging/postage extra.
    floor = ceil_eur(eur / Decimal('0.97') / Decimal('0.85'))
    while (Decimal(floor) - (Decimal(floor) * Decimal('0.125') + fixed_fee(floor)) * Decimal('1.2')) * Decimal('0.97') < eur:
        floor += 1
    photos = sorted(selected.get(pid, []), key=lambda p: (not p['primary'], p['order'], p['name']))
    photos = list({p['image_id']: p for p in photos}.values())
    desc = val(r, 'Customer-facing description') or ''
    # External purchase/social links and unsupported lead-time promises do not belong in a lot.
    desc = re.sub(r'https?://\S+', '', desc)
    desc = re.sub(r'(?im)^.*(?:dispatch|lead time|royal mail|delivery is).*(?:\n|$)', '', desc).strip()
    description = f'{title}\n\n{desc}\n\nDimensions: {val(r, "Dimensions / depth")}\nWeight: {val(r, "Weight")}\nQuantity: one individual sculpture or panel. Other pieces and room props in reference photographs are not included.'
    draft = dict.fromkeys(headers, '')
    draft.update({'Your Reference Number (optional)': pid, 'Your Reference Colour (optional)': 'Orange',
        'Auction Type (9) (optional)': 'Post-War & Contemporary Galleries', 'Object type (19499)': 'Relief',
        'Language': 'English', 'Description': description, 'D: Country of origin': 'United Kingdom',
        'D: Material': 'Plaster', 'D: Artist (optional)': 'Sally Price', 'D: Title of artwork': title,
        'D: Sold by (optional)': 'Direct from the brand', 'D: Over 200 years old': 'no',
        'Public photo URL': ';'.join(p['url'] for p in photos),
        # The owner requested a separate GBP100 Catawiki price uplift. This is
        # a seller proposal for expert review, not an independently appraised value.
        'Estimated lot value': catawiki_target_eur if catawiki_target_eur is not None else round(float(eur), 2),
        'Message to Expert (optional)': 'Contemporary gypsum-based wall relief by Sally Price for Boldstone. Surface colours are finishes, not solid precious or base metals. No numbered or limited edition is asserted. Catalogue dimensions may include working estimates. The owner-proposed Catawiki price includes GBP100 over catalogue retail, converted to EUR; please independently assess category, value and reserve eligibility.'})
    for dim in ('Height', 'Width', 'Depth'):
        n = val(r, f'ebay_{dim.lower()}_cm')
        if isinstance(n, (int, float)) and n > 0: draft[f'D: {dim}'] = f'{n:g}_cm'
    issues = ['Exclusive Catawiki listing requirement conflicts with other active channel listings',
              'Owner confirmation of terms, legal ownership/compliance and exclusivity required before upload',
              'Verify physical cast condition, signature and manufacturing era',
              'Review photographs of the actual sale item; neutral background, reverse/fixings and details',
              'Shipping profile or actual permitted destination charges not configured; dispatch deadline to check']
    if eur < 100: issues.append('Baseline catalogue retail equivalent is below EUR100. Owner-proposed Catawiki uplift does not establish an expert-approved market valuation.')
    if eur < 200: issues.append('Baseline catalogue retail equivalent is below EUR200. Expert confirmation is required for reserve eligibility; do not expose to an unprotected low bid.')
    if len(photos) < 5: issues.append(f'Only {len(photos)} selected non-in-situ website photo candidates; minimum five suitable photos required')
    if not all(draft[f'D: {d}'] for d in ('Height','Width','Depth')): issues.append('Missing dimensional fields')
    rec = {'product_id': pid, 'sku': sku, 'title': title, 'family': val(r, 'Family'),
        'website': val(r, 'Website listing'), 'dimensions': val(r, 'Dimensions / depth'), 'weight': val(r, 'Weight'),
        'material_finish': val(r, 'Internal material / finish'), 'retail_gbp': float(retail),
        'retail_eur_reference': round(float(eur),2), 'fee_protected_hammer_floor_eur_planning': floor,
        'catawiki_target_price_gbp': catawiki_target_gbp, 'catawiki_target_price_eur': catawiki_target_eur,
        'photo_candidates': photos, 'photo_candidate_count': len(photos),
        'existing_lot_id': EXISTING.get(pid), 'status': 'Existing draft: update in place' if pid in EXISTING else 'Prepared locally only',
        'issues': issues, 'draft': draft}
    records.append(rec)
    if pid not in EXISTING: new_rows.append([draft[k] for k in headers])

assert len(records) == 176 and len(new_rows) == 174
assert len({r['product_id'] for r in records}) == 176
assert len({r['sku'] for r in records}) == 176
assert set(EXISTING) <= {r['product_id'] for r in records}
assert all(not r['draft']['Reserve price (optional)'] for r in records)
assert all(not r['draft']['D: I verify that I have obtained this object legally and that I am allowed to sell it'] for r in records)
review = {'checked_utc': '2026-11-11', 'source': str(SOURCE),
    'source_sha256': hashlib.sha256(SOURCE.read_bytes()).hexdigest(), 'products': records,
    'counts': {'included': len(records), 'existing_drafts': len(EXISTING), 'new_rows': len(new_rows),
        'retail_eur_below_100': sum(r['retail_eur_reference'] < 100 for r in records),
        'retail_eur_below_200': sum(r['retail_eur_reference'] < 200 for r in records),
        'fewer_than_five_selected_photo_candidates': sum(r['photo_candidate_count'] < 5 for r in records)},
    'currency': {'source': 'https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml',
        'date': fx_date, 'gbp_per_eur': str(gbp_per_eur)},
    'pricing': {'seller_fee': '12.5% plus banded fixed EUR1/2/3/5/10, VAT extra',
        'fee_vat_planning_allowance': 0.2, 'fx_planning_allowance': 0.03,
        'hammer_floor_is_expert_valuation': False, 'packing_and_postage_included': False},
    'uploaded_by_this_run': 0, 'terms_accepted_by_this_run': False,
    'catawiki_price_policy': 'Owner-requested catalogue GBP price + GBP100; linked EUR seller proposal. Not expert approval or a saved native price.',
    'primary_blocker': 'Binding upload statement includes exclusive Catawiki listing. No other channel listings have been withdrawn.',
    'template_url': 'https://www.catawiki.com/seller/bulk_upload_objects/object_types/19499/template.csv',
    'dictionary_url': 'https://www.catawiki.com/seller/bulk_upload_objects/object_types/19499/dictionary.csv',
    'official_guidelines': 'https://cw-app-marketing.s3.amazonaws.com/assets/customer_support/customer_support/help_centre/guidelines/MODERN_ART_EN_Acceptance_Submission_Guidelines.pdf',
    'reserve_rule': 'https://www.catawiki.com/en/help/estimates-and-reserve-prices/can-i-set-a-minimum-selling-price-reserve-price'}
(OUT / 'product-review.json').write_text(json.dumps(review, indent=2, ensure_ascii=False))
(OUT / 'import-matrix.json').write_text(json.dumps({'headers': headers, 'rows': new_rows}, ensure_ascii=False))
print(json.dumps({'counts': review['counts'], 'currency': review['currency'], 'source_sha256': review['source_sha256']},indent=2))
