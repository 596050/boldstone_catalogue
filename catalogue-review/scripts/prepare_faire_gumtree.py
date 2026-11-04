"""Prepare two channel-specific packets from current app facts; never publish.

The Faire upload contains public product data and prices, not internal costs.
Gumtree offers remain blocked until actual UK possession is confirmed.
"""
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'catalogue-review'))
sys.path.insert(0, str(ROOT / 'catalogue-review/scripts'))
from channel_content import values, complete_description, marketplace_title, appearance, product_type, has_surface_effect, chairish_description
from import_saatchi_snapshot import Xlsx

D = lambda n: Decimal(str(n))
money = lambda n: float(D(n).quantize(D('.01'), rounding=ROUND_HALF_UP))
up = lambda n: float(D(n).quantize(D('.01'), rounding=ROUND_CEILING))


def prepare(out):
    app = json.loads((out / 'app-current.json').read_text())
    scope = json.loads((ROOT / 'outputs/saatchi-publication-20261104/176-publication-packet.json').read_text())['records']
    images = json.loads((out / 'current-public-images.json').read_text())
    pointer = json.loads((ROOT / 'sculpture-catalogue/current-master.json').read_text())['current_app_review_workbook']
    master = Xlsx(pointer['path'])
    website_urls = {master.value('Wall Sculptures', f'AA{r}'): master.value('Wall Sculptures', f'AW{r}') for r in range(8, 189)}
    products = {p['id']: p for p in app['products']}
    records, rows, gumtree = [], [], []
    headers = ['SKU', 'Product Name', 'Product Type', 'Description', 'Currency',
               'Unit Wholesale Price', 'Unit Retail Price', 'Case Quantity',
               'Minimum Order Quantity', 'Availability', 'Lead Time', 'Image',
               'Product URL', 'Brand', 'Colour / Finish', 'Dimensions', 'Product Weight']
    for binding in scope:
        p = products[binding['catalogue_id']]
        f = values(p); sku = f['Seller SKU']
        assert p['listing_decision'] == 'include' and sku == binding['sku']
        c = p['costing']; retail = c['pricing']['marked_up_price']
        assert c['labour_cost'] == 0 and c['pricing']['mode'] == 'markup' and c['pricing']['markup_percent'] == 100
        assert abs(retail - 2 * c['total_cost']) < .011
        wholesale = up(D(retail) * D('.8'))
        normal_first_net = money(D(wholesale) * D('.75'))
        next_day_first_net = money(D(wholesale) * D('.72'))
        # This is a reserve sensitivity, not an assertion about the brand's VAT status.
        fee_tax_reserve_net = money(D(wholesale) * (1 - D('.28') * D('1.2')))
        assert min(normal_first_net, next_day_first_net, fee_tax_reserve_net) > c['total_cost']
        primary = p['photos']['primary_listing']['image_id']
        ordered = list(dict.fromkeys([primary] + [im['id'] for im in p['photos']['listing']['images']] +
                                    [im['id'] for im in p['photos']['in_situ']['images']]))
        assert primary and primary in {im['id'] for im in p['photos']['listing']['images']}
        assert all(i in images for i in ordered)
        for im in p['photos']['listing']['images'] + p['photos']['in_situ']['images']:
            recorded_hash = im.get('original', {}).get('dropbox_content_hash')
            assert not recorded_hash or images[im['id']]['dropbox_content_hash'] == recorded_hash
        urls = [images[i]['url'] for i in ordered]
        assert all(url.startswith('https://images.squarespace-cdn.com/') for url in urls)
        complete = complete_description(p, sku, dispatch_days=10)
        source = dict(sku=sku, description_text=complete, surface_effect=has_surface_effect(p), product_type=product_type(p))
        description = chairish_description(source, dispatch_days=10)
        assert 'gypsum-based material' in description and 'Sally Price' in description
        assert not re.search(r'\bGFRC\b|\bLimited Edition\b|\bRoyal Mail\b', description, re.I)
        if has_surface_effect(p):
            assert 'surface-effect pattern will vary' in description
        public_url = f.get('Website product URL') or f.get('Website URL') or website_urls[p['id']]
        if not public_url:
            public_url = next((v for v in f.values() if isinstance(v, str) and v.startswith('https://boldstonesculpture.com/buy/p/')), None)
        assert public_url and public_url.startswith('https://boldstonesculpture.com/buy/p/'), (sku, 'No canonical website product URL')
        title = marketplace_title(p, limit=100)
        row = [sku, title, product_type(p), description, 'GBP', wholesale, retail, 1, 1,
               'Made to order', 'Within 10 working days; delivery transit time additional',
               ' '.join(urls), public_url, 'Boldstone', appearance(p), f['Dimensions / depth'], f['Weight']]
        assert len(row) == len(headers)
        rows.append(row)
        records.append(dict(catalogue_id=p['id'], sku=sku, title=title, primary_image_id=primary,
            image_ids=ordered, image_urls=urls, retail_price_gbp=retail, wholesale_price_gbp=wholesale,
            wholesale_discount_percent=money((1-D(wholesale)/D(retail))*100),
            manufacturing_cost_gbp=c['manufacturing_cost'], labour_cost_gbp=0,
            total_cost_gbp=c['total_cost'], first_order_net_gbp=normal_first_net,
            first_order_profit_gbp=money(D(normal_first_net)-D(c['total_cost'])),
            first_order_next_day_net_gbp=next_day_first_net,
            fee_tax_reserve_net_gbp=fee_tax_reserve_net,
            fee_tax_reserve_profit_gbp=money(D(fee_tax_reserve_net)-D(c['total_cost'])),
            reorder_net_gbp=money(D(wholesale)*D('.85')),
            description=description, website_url=public_url, status='PREPARED_NOT_UPLOADED'))
        gumtree.append(dict(catalogue_id=p['id'], sku=sku, title=title,
            description=complete, price_gbp=retail, seller_type='Business',
            actual_uk_possession_confirmed=False, collection_location=None,
            image_ids=ordered, image_urls=urls,
            status='DO_NOT_PUBLISH_PREORDER_STOCK_UNCONFIRMED'))
    assert len(rows) == len({r[0] for r in rows}) == 176
    packet = dict(prepared_utc=datetime.now(timezone.utc).isoformat(), app_revision=app['revision'],
        target_records=176, extra_included_records_held=['BSI-D886F539DD3E','BSI-65520F070145'],
        headers=headers, rows=rows, records=records,
        pricing=dict(wholesale_fraction_of_current_retail=.8, current_retail_prices_preserved=True,
            first_marketplace_commission=.25, reorder_commission=.15, optional_next_day_payout_fee=.03,
            fee_tax_reserve_fraction=.2, fee_tax_reserve_is_assumption_not_tax_determination=True,
            scope='Unit artwork prices only. Postage, packing and applicable transaction taxes are separate. No free-shipping or promotion commitment.',
            fee_source='https://www.faire.com/support/articles/360040446591',
            payout_settings_not_changed=True),
        stock_quantities_not_invented=True, saatchi_edition_fields_not_exported=True,
        native_publications_this_run=0)
    write = lambda name, data: (out / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    write('faire-upload.json', packet)
    write('gumtree-prepared.json', dict(records=gumtree, current_ads_before=0,
        rule_source='https://www.gumtree.com/info/safety/p/policies/gumtree-policies/gumtree-posting-policies/',
        no_ad_creation_attempted=True))
    summary = dict(target_records=176, selected_distinct_images=len({i for r in records for i in r['image_ids']}),
        selected_image_associations=sum(len(r['image_ids']) for r in records),
        wholesale_discount_target_percent=20,
        minimum_first_order_profit_gbp=min(r['first_order_profit_gbp'] for r in records),
        minimum_fee_tax_reserve_profit_gbp=min(r['fee_tax_reserve_profit_gbp'] for r in records),
        min_fee_tax_reserve_markup_percent=min(money(D(r['fee_tax_reserve_profit_gbp'])/D(r['total_cost_gbp'])*100) for r in records),
        public_image_bytes_downloaded_for_preparation=0)
    write('preparation-verification.json', dict(status='PASS', **summary))
    print(json.dumps(summary))


if __name__ == '__main__':
    prepare(Path(sys.argv[1]).resolve())
