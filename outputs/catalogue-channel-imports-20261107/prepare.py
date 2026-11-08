"""Reconcile dated native observations; prepare a private master and public retail feed."""
import csv
import hashlib
import html
import json
import re
import shutil
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path('/Users/tprice/Documents/boldstone')
OUT = Path(__file__).parent
sys.path[:0] = [str(ROOT / 'catalogue-review/scripts'), str(ROOT / 'catalogue-review')]
from import_saatchi_snapshot import Xlsx, column, column_index
from channel_content import values, marketplace_title, product_type, description_html

read = lambda name: json.loads((OUT / name).read_text())
write = lambda name, value: (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
stamp = read('plan.json')['checked_utc'] if (OUT/'plan.json').exists() else datetime.now(timezone.utc).isoformat()
pointer = json.loads((ROOT / 'sculpture-catalogue/current-master.json').read_text())
source = pointer['current_app_review_workbook']
body = Path(source['path']).read_bytes()
assert hashlib.sha256(body).hexdigest() == source['sha256']
write('source-pointer-before.json', pointer)
write('previous-dropbox-metadata.json', source['dropbox'])
(OUT / 'previous-catalogue.xlsx').write_bytes(body)
master = Xlsx(OUT / 'previous-catalogue.xlsx')
headers = {master.value('Wall Sculptures', ad): re.sub(r'\d', '', ad)
           for ad in master.cells['Wall Sculptures'] if re.fullmatch(r'[A-Z]+7', ad)
           and master.value('Wall Sculptures', ad)}
assert len(headers) == len({h.casefold() for h in headers}) == 644
row_ids = {master.value('Wall Sculptures', 'AA' + str(n)): n for n in range(8, 189)}
app = read('app-specifications.json')
products = {p['id']: p for p in app['products']}
assert set(row_ids) == set(products) and len(products) == 181
fields = {pid: values(p) for pid, p in products.items()}
sku_ids = {f['Seller SKU']: pid for pid, f in fields.items()}
assert len(sku_ids) == 181
google = read('google-source-reconciliation.json')
g_by_pid = {g['catalogue_id']: g for g in google['wall_sculpture_matches_detail']}
assert len(g_by_pid) == 176 and not google['price_or_identity_issues']

# Exact native Faire identity joins, never title-only writes.
faire = Xlsx(OUT / 'faire-native-products.xlsx')
faire_keys = [faire.value('Products', column(i) + '3') for i in range(1, 69)]
assert all(faire_keys) and len(set(faire_keys)) == len(faire_keys)
faire_records = []
for n in range(4, 180):
    record = {key: faire.value('Products', column(i + 1) + str(n)) for i, key in enumerate(faire_keys)}
    assert record['sku'] in sku_ids
    pid = sku_ids[record['sku']]
    old_token = master.value('Wall Sculptures', headers['faire_native_product_token'] + str(row_ids[pid]))
    assert record['info_product_token'] == old_token, ('Native Faire token changed', pid)
    assert record['info_status_v2'] == record['option_status'] == 'Published'
    faire_records.append((pid, record))
assert len({pid for pid, _ in faire_records}) == 176 and {pid for pid, _ in faire_records} == set(g_by_pid)

# Native Furnitures inventory joins to the already stored title/SKU/product-ID mapping.
normalize = lambda s: re.sub(r'\s+', ' ', str(s)).strip().casefold()
title_ids = {normalize(marketplace_title(products[pid])): pid for pid in g_by_pid}
assert len(title_ids) == 176
furnitures = read('furnitures-native-inventory.json')
furn_records = []
for record in furnitures['products']:
    pid = title_ids[normalize(record['title'])]
    match = re.search(r'ACTIVE\s+(.+?)\s*·\s*£([\d,]+(?:\.\d{1,2})?)\s*·\s*(\d+)\s+in stock', record['status_line'])
    assert match, record
    category, price, stock = match.group(1).strip(), float(match.group(2).replace(',', '')), int(match.group(3))
    n = row_ids[pid]
    assert master.value('Wall Sculptures', headers['furnitures_sku'] + str(n)) == fields[pid]['Seller SKU']
    assert master.value('Wall Sculptures', headers['furnitures_native_product_id'] + str(n))
    assert abs(price - master.value('Wall Sculptures', headers['furnitures_native_price_gbp'] + str(n))) < .005
    furn_records.append((pid, dict(record, price_gbp=price, stock=stock, category=category)))
assert len({pid for pid, _ in furn_records}) == 176

schema = read('pinterest-template-schema.json')
pin_keys = schema['fields']
assert len(pin_keys) == 46
library = read('app-library.json')
image_reviews = {(r['product_id'], r['item_id']): r.get('data', {}) for r in library['reviews'] if r.get('kind') == 'image'}
pin_records = []
pin_by_pid = {}
pin_qualifications = {}
for pid, p in products.items():
    f, g = fields[pid], g_by_pid.get(pid)
    price = p['costing']['pricing']['marked_up_price']
    assert abs(price - master.value('Wall Sculptures', 'H' + str(row_ids[pid]))) < .005
    record = {k: '' for k in pin_keys}
    record.update(id=g['google_offer_id'] if g else f['Seller SKU'], title=g['google_title'] if g else p['retail_name'],
                  description=f['Description'], price=f'{price:.2f} GBP', brand='Boldstone',
                  material='Gypsum-based material', product_type='Wall Sculptures > ' + p['family'],
                  google_product_category='11', adult='false', condition='new')
    record['description_html'] = description_html(record['description'])
    colour = f['Colour / appearance']
    if len(colour) > 30:
        colour = p['retail_name'].rsplit(' - ', 1)[-1]
        colour = re.sub(r'\s+Finish$', '', colour, flags=re.I)
    if len(colour) <= 30:
        record['color'] = colour
    shipping = p.get('us_shipping') or {}
    if shipping.get('artwork_upper_cm'):
        record['size'] = ' x '.join(f'{v:g}' for v in shipping['artwork_upper_cm']) + ' cm'
    if shipping.get('packed_cm') and shipping.get('packed_kg'):
        record['shipping_weight'] = f"{shipping['packed_kg']:g} kg"
        record['shipping_width'] = f"{shipping['packed_cm'][1]:g} cm"
        record['shipping_height'] = f"{shipping['packed_cm'][2]:g} cm"
    record.update(custom_label_0='Wall Sculptures', custom_label_1=p['family'],
                  custom_label_2='Handmade by Sally Price', custom_label_3='Outdoor and indoor', custom_label_4='GBP retail')
    if g:
        record.update(link=g['website_url'], image_link=g['google_image_link'],
                      availability=g['google_row']['availability'], item_group_id=g['google_row']['item group id'])
        extras = [url for url in g['google_additional_image_link'].split(',') if url and url != record['image_link']]
        record['additional_image_link'] = ','.join(list(dict.fromkeys(extras))[:10])
        primary = p['photos']['primary_listing']['image_id']
        alt = image_reviews.get((pid, primary), {}).get('alt') or f"{record['title']} by Boldstone; {f['Colour / appearance'].rstrip('.')}"
        record['alt_text'] = alt
        assert record['availability'] in ('in stock', 'out of stock', 'preorder')
        assert all(record[k] for k in ['id', 'title', 'description', 'link', 'image_link', 'price', 'availability'])
        assert len(record['title']) <= 500 and len(record['description']) <= 10000
        assert len(record['link']) <= 511 and len(record['image_link']) <= 2000
        assert all(url.startswith('https://images.squarespace-cdn.com/') for url in [record['image_link']] + extras)
        pin_records.append(record)
    pin_by_pid[pid] = record
    omitted = [k for k, v in record.items() if v == '']
    pin_qualifications[pid] = dict(eligible=g is not None, omitted_optional_fields=omitted,
        reason='' if g else 'Not in the established 176 website publication products; no matching current published URL/primary was inferred.',
        unknown_fields='GTIN, ratings/reviews, video, sale price, tax and fixed shipping charges are not verified. Apparel-only attributes are not applicable. No review, barcode, discount or free shipping claim invented.',
        package_estimated=shipping.get('package_estimated', True), packing_basis=shipping.get('packing_basis', ''))
assert len(pin_records) == 176 and len({r['id'] for r in pin_records}) == 176
assert all(len(r[k]) <= 30 for r in pin_records for k in ('material','color','size','pattern'))
with (OUT / 'pinterest_wall_sculptures.csv').open('w', newline='', encoding='utf-8') as stream:
    writer = csv.DictWriter(stream, fieldnames=pin_keys)
    writer.writeheader(); writer.writerows(pin_records)
write('pinterest-feed-records.json', pin_records)
write('pinterest-field-qualifications.json', pin_qualifications)

new_headers = ['pinterest_' + k.lower() for k in pin_keys] + [
    'pinterest_feed_eligible','pinterest_feed_eligibility_basis','pinterest_source_checked_utc',
    'pinterest_omitted_field_basis','pinterest_packing_basis','pinterest_shipping_length_cm_estimate',
    'pinterest_catalogue_id','pinterest_data_source_id','pinterest_merchant_status','pinterest_google_sheet_url','pinterest_daily_feed_status']
# Keep the exact export's native key names as a dated snapshot, separate from proposed prices.
new_headers += ['faire_native_export_' + key for key in faire_keys]
new_headers += ['faire_native_export_sha256','faire_native_export_checked_utc','faire_native_field_gaps',
                'faire_native_customisation_consistency','furnitures_native_title','furnitures_inventory_checked_utc',
                'furnitures_native_publication_observed','furnitures_returns_policy_observed',
                'google_merchant_account_id','google_merchant_primary_source_id','google_merchant_primary_source_name',
                'google_merchant_offer_id','google_merchant_feed_label','google_merchant_language','google_merchant_native_title',
                'google_merchant_native_brand','google_merchant_native_price_gbp','google_merchant_product_url',
                'google_merchant_checked_utc','google_manufacturer_account_id','google_manufacturer_linked_merchant_id',
                'google_manufacturer_link_status','google_manufacturer_product_status','google_manufacturer_required_action',
                'microsoft_merchant_store_id','microsoft_merchant_google_import_name','microsoft_merchant_google_account_id',
                'microsoft_merchant_import_schedule','microsoft_merchant_import_status',
                'microsoft_merchant_google_import_feed_id','microsoft_merchant_manual_feed_id','microsoft_merchant_manual_feed_state',
                'brandboom_private_preview_url','brandboom_preview_product_count','brandboom_plan_product_limit',
                'catalogue_google_sheet_url','catalogue_google_sheet_owner']
assert len(set(new_headers)) == len(new_headers) and not set(new_headers) & set(headers)
first = max(column_index(c) for c in headers.values()) + 1
headers.update({h: column(first + i) for i, h in enumerate(new_headers)})
patches = []
seen = set()
def put(header, row, value):
    if row > 7 and header.endswith('_utc') and isinstance(value,str) and re.match(r'^\d{4}-\d{2}-\d{2}T',value):
        value='Checked UTC: '+value
    cell = headers[header] + str(row)
    before = master.value('Wall Sculptures', cell)
    if value in (None, '') and before in (None, ''):
        return
    if value == before:
        return
    assert cell not in seen and master.formula('Wall Sculptures', cell) is None, cell
    seen.add(cell)
    patches.append(dict(sheet='Wall Sculptures', cell=cell, before=before, value=value, header=header,
                        format='header' if row==7 else ('0.00' if isinstance(value, (int,float)) and not isinstance(value,bool) else '@')))

for h in new_headers:
    put(h, 7, h)
faire_sha = hashlib.sha256((OUT / 'faire-native-products.xlsx').read_bytes()).hexdigest()
for pid, record in faire_records:
    n = row_ids[pid]
    for key in faire_keys:
        put('faire_native_export_' + key, n, record[key])
    put('faire_native_product_name', n, record['product_name_english'])
    put('faire_native_wholesale_gbp', n, record['uk_price_wholesale'])
    put('faire_native_retail_gbp', n, record['uk_price_retail'])
    put('faire_native_product_status', n, 'Published')
    put('faire_native_option_status', n, 'Published')
    put('faire_native_product_token', n, record['info_product_token'])
    put('faire_native_checked_utc', n, 'Checked UTC: ' + stamp)
    put('faire_native_shop_status', n, 'Published in native product manager and fresh all-products export (176/176). Retailer checkout not tested.')
    put('faire_native_price_source', n, 'Fresh native all-products export, 7 November 2026; exact SKU and existing product-token join. Native prices are actual observations; profit-protected proposals are separate.')
    put('faire_native_export_sha256', n, faire_sha)
    put('faire_native_export_checked_utc', n, stamp)
    missing = [key for key in ('item_weight','item_weight_unit','item_length','item_width','item_height','item_dimensions_unit',
               'packaged_weight','packaged_weight_unit','packaged_length','packaged_width','packaged_height','packaged_dimensions_unit',
               'made_in_country','gtin','tariff_code') if record[key] in ('', None)]
    put('faire_native_field_gaps', n, ', '.join(missing))
    put('faire_native_customisation_consistency', n, 'Native Customizable is No; description offers custom design. Catalogue supports customisation; no native field write made in this refresh.' if record['has_customization']=='No' else 'No checked inconsistency')
for pid, record in furn_records:
    n = row_ids[pid]
    put('furnitures_native_title', n, record['title'])
    put('furnitures_inventory_checked_utc', n, furnitures['checked_utc'])
    put('furnitures_native_publication_observed', n, 'ACTIVE in complete native inventory (176/176); current inventory status, price and stock verified. Historical public-page evidence retained separately.')
    put('furnitures_returns_policy_observed', n, 'Site advertises 30-day returns; no new return-policy commitment made by this refresh.')
    put('furnitures_stock', n, record['stock'])
    put('furnitures_category', n, record['category'])

for pid, p in products.items():
    n, record, qual = row_ids[pid], pin_by_pid[pid], pin_qualifications[pid]
    for key in pin_keys:
        put('pinterest_' + key.lower(), n, record[key])
    put('pinterest_feed_eligible', n, qual['eligible'])
    put('pinterest_feed_eligibility_basis', n, 'Established website publication product; matched current Google product URL and catalogue price.' if qual['eligible'] else qual['reason'])
    put('pinterest_source_checked_utc', n, stamp)
    put('pinterest_omitted_field_basis', n, qual['unknown_fields'])
    put('pinterest_packing_basis', n, qual['packing_basis'])
    if p.get('us_shipping', {}).get('packed_cm'):
        put('pinterest_shipping_length_cm_estimate', n, p['us_shipping']['packed_cm'][0])
    put('pinterest_catalogue_id', n, '4814500935893')
    destinations=read('google-sheet-destinations.json')
    put('pinterest_google_sheet_url',n,destinations['pinterest_url'])
    put('catalogue_google_sheet_url',n,destinations['master_url'])
    put('catalogue_google_sheet_owner',n,destinations['owner'])
    channel_state=read('channel-state.json') if (OUT/'channel-state.json').exists() else {}
    put('pinterest_data_source_id',n,channel_state.get('pinterest_data_source_id',''))
    put('pinterest_daily_feed_status',n,channel_state.get('pinterest_status','Google Sheet prepared. Native daily URL submission validating; distribution still subject to account approval.'))
    put('pinterest_merchant_status', n, 'Account distribution blocked: minimum product requirements and minimum website quality requirements; native merchant issues read 7 November 2026.')
    put('google_manufacturer_account_id', n, '5898308482')
    put('google_manufacturer_linked_merchant_id', n, '5664655454')
    put('google_manufacturer_link_status', n, 'Active; Boldstone brand Approved; correct website account verified 7 November 2026.')
    put('google_manufacturer_product_status', n, 'No variants present; no successful import asserted.')
    put('google_manufacturer_required_action', n, 'Manufacturer Center requires valid GTINs for every product. Catalogue has no verified GS1 GTINs; seller SKUs are not barcodes. Daily automatic sync can take up to a day after eligibility/link approval.')
    if pid in g_by_pid:
        g = g_by_pid[pid]
        for key, value in dict(google_merchant_account_id='5664655454', google_merchant_primary_source_id='10788949980',
                google_merchant_primary_source_name='Squarespace-1469f13b', google_merchant_offer_id=g['google_offer_id'],
                google_merchant_feed_label=g['google_feed_label'],google_merchant_language=g['google_language'],
                google_merchant_native_title=g['google_title'],google_merchant_native_brand=g['google_brand'],
                google_merchant_native_price_gbp=float(g['google_price'].split()[0]),google_merchant_product_url=g['website_url'],
                google_merchant_checked_utc=stamp,microsoft_merchant_store_id='50112622',
                microsoft_merchant_google_import_name='Website sync - GMC 5664655454',microsoft_merchant_google_account_id='5664655454',
                microsoft_merchant_import_schedule='Daily 06:00, GMT Standard Time (London)',
                microsoft_merchant_import_status=channel_state.get('microsoft_status','Scheduled; first import queued. Product import and approval not yet verified.'),
                microsoft_merchant_google_import_feed_id='1830968',microsoft_merchant_manual_feed_id='1830841',
                microsoft_merchant_manual_feed_state='Test-only, saved and verified 7 November 2026. Old SellerSKU IDs retained for recovery; Google UUID IDs are the production source. Prevents duplicate offers when the Google import processes.',
                brandboom_private_preview_url='https://www.brandboom.com/app/a/BCB1A491121',brandboom_preview_product_count=50,
                brandboom_plan_product_limit=50).items():
            put(key,n,value)
        put('brandboom_checked_utc',n,'Checked UTC: '+stamp)
        put('brandboom_presentation_status',n,'176 records in saved editor presentation. Preview explicitly owner-only and shows 50 products. Native plan warning: Product Limit Reached (50/50). No public share link shown.')
        put('brandboom_publication_status',n,'NOT VERIFIED PUBLIC: owner-only preview; 50-product limit. Marketplace application remains unsubmitted in retained evidence.')

write('plan.json', dict(scope='Refresh current native channel records; add Pinterest template fields and a separate public retail-only feed. Preserve app core, all costs/prices/formulas, all existing non-targeted platform evidence.',
    source_sha256=source['sha256'],checked_utc=stamp,patches=patches,first_added_column=first,
    last_added_column=first+len(new_headers)-1,new_headers=new_headers,headers=headers,
    core_records=181,publication_records=176,faire_products_verified=176,furnitures_active_verified=176,
    google_wall_products_verified=176,google_products_total=325,
    source_google_merchant_id='5664655454',google_sheet_owner='info@boldstone.co.uk',
    pinterest_feed_fields=pin_keys,public_feed_rows=pin_records,
    previews=[dict(name='pinterest',range=headers['pinterest_id']+'7:'+headers['pinterest_price']+'10'),
              dict(name='faire',range=headers['faire_native_product_name']+'7:'+headers['faire_native_retail_gbp']+'11'),
              dict(name='furnitures',range=headers['furnitures_native_title']+'7:'+headers['furnitures_returns_policy_observed']+'10')]))
write('channel-reconciliation.json',dict(checked_utc=stamp,component_records=181,publication_records=176,
    faire_published=176,furnitures_active=176,brandboom_editor_records=176,brandboom_owner_preview_records=50,
    brandboom_public_share_found=False,google_products_total=325,google_wall_products_matched=176,
    matched_ids=sorted(g_by_pid),pinterest_ineligible_records=[dict(catalogue_id=pid,name=products[pid]['name'],reason=q['reason']) for pid,q in pin_qualifications.items() if not q['eligible']],
    faire_native_fields=faire_keys,pinterest_template_fields=pin_keys,added_columns=len(new_headers),planned_cells=len(patches)))
print(json.dumps(dict(status='PLAN_READY',added_columns=len(new_headers),patches=len(patches),pinterest_rows=len(pin_records),faire_records=len(faire_records),furnitures_records=len(furn_records))))
