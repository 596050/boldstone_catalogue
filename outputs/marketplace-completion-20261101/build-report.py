from pathlib import Path
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from html import escape
import json

OUT = Path(__file__).resolve().parent
ROOT = OUT.parent
plan = json.loads((ROOT / 'website-marketplace-refresh-20261031/website-final-plan.json').read_text())
products = {p['catalogue_id']: p for p in plan['products'] if p.get('public') and p['listing_decision'] == 'include'}
sources = [
    'website-marketplace-refresh-20261031/marketplace-receipts.json',
    'marketplace-next30-20261031/publication-receipts.json',
    'marketplace-ebay-expansion-20261031/publication-receipts.json',
    'marketplace-completion-20261101/publication-receipts.json',
]
receipts = []
for source in sources:
    receipts.extend({**r, 'receipt_source': source} for r in json.loads((ROOT / source).read_text()))
assert len(receipts) == len(products) == 176
assert len({r['catalogue_id'] for r in receipts}) == len(receipts)
assert len({r['url'] for r in receipts}) == len(receipts)
assert {r['catalogue_id'] for r in receipts} == set(products)
for r in receipts:
    p = products[r['catalogue_id']]
    assert r['title'] == p['retail_name'] + ' | Wall Sculpture'
    if 'sku' in r:
        assert r['sku'] == p['sku']
    if 'marketplace_price' in r:
        assert Decimal(str(r['marketplace_price'])) == Decimal(p['price']).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
new = json.loads((OUT / 'publication-receipts.json').read_text())
manifest = json.loads((OUT / 'manifest.json').read_text())
prepared = {r['catalogue_id']: r for r in manifest['records'] + manifest['existing_draft']}
assert len(new) == len(prepared) == 96
for r in new:
    assert (OUT / f"{r['order']}-receipt.txt").is_file()
    before_name = 'deco-dune-wave-before-publish.txt' if r['order'] == 41 else f"{r['order']}-before-publish.txt"
    assert (OUT / before_name).is_file()
    assert r['photo_count'] == len(prepared[r['catalogue_id']]['photos'])
verification = {
    'verified_utc': datetime.now(timezone.utc).isoformat(),
    'source_cutoff': plan['event_cutoff'],
    'catalogue_public_products': len(products),
    'marketplace_unique_product_ids': len(receipts),
    'marketplace_unique_listing_urls': len(receipts),
    'new_submissions_this_pass': len(new),
    'missing_products': [],
    'duplicate_products': [],
    'duplicate_listing_urls': [],
    'new_skus_prices_titles_photo_counts_match': True,
    'approval_note': 'Submission and listing receipts verified; Facebook approval is a separate process. Statuses below are from each saved receipt.',
    'ebay': {'sapr_2972': 'unchanged', 'in6192': 'conversion authorized; blocked at sign-in security code', 'prepared_new_offers': 157, 'uploaded': 0},
    'tiktok': {'prepared_products': 176, 'uploaded': 0, 'blockers': ['warehouse contact and address required', 'payment verification incomplete', 'UK SKU Handling Time access must support 10 working days before publishing made-to-order items']},
}
(OUT / 'validation.json').write_text(json.dumps(verification, ensure_ascii=False, indent=2))
(OUT / 'all-marketplace-receipts.json').write_text(json.dumps(receipts, ensure_ascii=False, indent=2))
rows = []
for r in sorted(receipts, key=lambda r: products[r['catalogue_id']]['catalogue_name'].casefold()):
    p = products[r['catalogue_id']]
    status = r.get('status', r.get('state', 'Submitted'))
    checked = r.get('verified_utc', r.get('verified_at', r.get('at', '')))
    rows.append('<tr><td>' + escape(p['catalogue_name']) + '<br><small>' + escape(r['catalogue_id']) + '</small></td><td><a href="' + escape(r['url'], quote=True) + '">' + escape(p['retail_name']) + '</a></td><td>£' + escape(p['price']) + '</td><td>' + escape(str(r.get('photo_count', 'See original receipt'))) + '</td><td>' + escape(status) + '<br><small>' + escape(checked) + '</small></td><td><a href="' + escape(p['website_url'], quote=True) + '">Website</a></td></tr>')
doc = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Boldstone Marketplace completion</title>
<style>body{font:16px/1.5 system-ui,sans-serif;margin:36px auto;max-width:1350px;padding:0 22px;color:#26302b;background:#f8f8f3}h1{font-family:Georgia,serif}a{color:#315b40}table{width:100%;border-collapse:collapse;background:white}th,td{text-align:left;vertical-align:top;padding:12px;border-bottom:1px solid #ddd}th{background:#e6ebdf;position:sticky;top:0}small{color:#68736d}input{font:inherit;padding:10px;margin:20px 0;width:min(560px,90%)}.notice{padding:20px;background:#eaf0e4;border:1px solid #b9c7ad;border-radius:10px}.pending{background:#fff4db;padding:18px;border-radius:10px}img{max-width:100%;border:1px solid #bbb}</style>
<h1>Boldstone Marketplace completion</h1><div class="notice"><b>176 included catalogue products, 176 unique Marketplace listing URLs.</b><p>96 submissions completed in this pass, including the recovered Deco Dune Wave draft. No catalogue products are missing and no duplicate catalogue IDs or listing URLs occur in the combined receipts.</p><p>Submission does not mean Facebook has approved visibility. The latest submissions were in review when checked; the table preserves the status and timestamp of each receipt.</p></div>
<h2>Other channels</h2><div class="pending"><p><b>eBay:</b> sapr_2972 remains unchanged. Conversion of in6192 is authorized but eBay requires its sign-in security code. 157 new offers are prepared, excluding existing individual sculpture offers on sapr_2972. No new eBay offers were uploaded in this pass.</p><p><b>TikTok:</b> 176 product records are prepared. Upload is disabled until pickup/returns warehouse details are supplied. Payment verification and support for the 10-working-day made-to-order handling time remain to be completed.</p></div>
<p><a href="validation.json">Validation results</a> · <a href="all-marketplace-receipts.json">All listing receipts</a> · <a href="ebay-in6192-prepared.json">Prepared eBay records</a> · <a href="tiktok-prepared-catalogue.json">Prepared TikTok records</a></p>
<input id="search" placeholder="Filter by sculpture, finish or catalogue ID" aria-label="Filter listings"><table><thead><tr><th>Catalogue component</th><th>Marketplace listing</th><th>Exact website price</th><th>Photos</th><th>Receipt status and date</th><th>Website</th></tr></thead><tbody>'''+''.join(rows)+'''</tbody></table><h2>Final verified submission</h2><img src="last-publication.png" alt="Marketplace receipt for the final sculpture"><script>document.querySelector('#search').addEventListener('input',e=>{const q=e.target.value.toLowerCase();for(const r of document.querySelectorAll('tbody tr'))r.hidden=!r.textContent.toLowerCase().includes(q)});</script></html>'''
(OUT / 'marketplace-results.html').write_text(doc)
print(json.dumps(verification, ensure_ascii=False, indent=2))
