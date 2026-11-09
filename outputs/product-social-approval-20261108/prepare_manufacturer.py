"""Prepare product facts without assigning or publishing unlicensed identifiers."""
import json
from pathlib import Path

OUT=Path(__file__).parent
feed=json.loads((OUT/'pinterest-public-feed.json').read_text())
audit=json.loads((OUT/'pinterest-public-audit.json').read_text())
assert len(feed)==176 and audit['summary']['price_mismatches']==0
records=[]
for p in feed:
    # Stable existing variant UUIDs; a valid SKU is not substituted for a GTIN.
    records.append(dict(id=p['id'],brand='Boldstone',title=p['title'],
                        description=p['description'],image_link=p['image_link'],
                        product_page_url=p['link'],color=p.get('color',''),
                        suggested_retail_price='GBP '+p['price'].split()[0],gtin='',
                        status='AWAITING_VERIFIED_BOLDSTONE_GS1_ASSIGNMENT'))
assert len({r['id'] for r in records})==176
packet=dict(status='PREPARED_PRODUCT_FACTS_NOT_A_VALID_UPLOAD',manufacturer_account_id='5898308482',
            approved_brand_id='301096324',approved_brand='Boldstone',linked_merchant_id='5664655454',
            products=records,assigned_gtins=0,
            blocking_action='Locate or license a genuine Boldstone-owned GS1 allocation, enter each saleable variant in My Numberbank, and verify the licensee/product assignment before export or upload.',
            controls=['No invented GTINs','No other brand barcode reuse','One stable identifier per saleable model/finish across channels','No paid licence purchased','Do not upload this incomplete JSON as a feed'])
(OUT/'manufacturer-product-facts-awaiting-gtins.json').write_text(json.dumps(packet,indent=2)+'\n')
print(json.dumps(dict(product_facts_prepared=176,assigned_gtins=0,valid_upload_created=False)))
