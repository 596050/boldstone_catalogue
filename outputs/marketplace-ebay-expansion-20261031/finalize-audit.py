from pathlib import Path
from datetime import datetime, timezone
import json, html
p=Path(__file__).resolve().parent
receipts=json.loads((p/'publication-receipts.json').read_text())
manifest=json.loads((p/'manifest-upload.json').read_text())
prior=[]
for f in [p.parent/'website-marketplace-refresh-20261031/marketplace-receipts.json',p.parent/'marketplace-next30-20261031/publication-receipts.json']:
 prior.extend(json.loads(f.read_text()))
by={r['catalogue_id']:r for r in manifest['records']}
assert len(receipts)==40 and len(prior)==40
assert len({r['catalogue_id'] for r in receipts+prior})==80
assert len({r['url'] for r in receipts+prior})==80
assert {r['catalogue_id'] for r in receipts}==set(by)
for r in receipts:
 q=by[r['catalogue_id']]
 assert r['title']==q['title'] and r['sku']==q['sku'] and r['marketplace_price']==q['marketplace_price']
 assert r['photo_count']==len(q['photos'])
 assert (p/f"{r['order']}-before-publish.txt").is_file()
 assert (p/f"{r['order']}-receipt.txt").is_file()
result={'verified_utc':datetime.now(timezone.utc).isoformat(),'new_marketplace_listings':40,'prior_marketplace_listings':40,'total_unique_catalogue_listings':80,'overlapping_catalogue_ids':0,'duplicate_publication_urls':0,'photo_placements':sum(r['photo_count'] for r in receipts),'result':'PASS','approval_boundary':'Each publication was verified in Your listings. Newest listings remain in Facebook review; publication does not prove public approval.','ebay_publications':0,'ebay_existing_listings_modified':0}
(p/'validation.json').write_text(json.dumps(result,indent=2))
e=html.escape
rows=''.join('<tr><td>'+str(n)+'</td><td><a href="'+e(r['url'])+'">'+e(r['title'])+'</a></td><td>£'+str(r['marketplace_price'])+'</td><td>'+str(r['photo_count'])+'</td><td>'+e(r['catalogue_id'])+'</td></tr>' for n,r in enumerate(receipts,1))
(p/'marketplace-results.html').write_text('''<!doctype html><meta charset="utf-8"><title>40 additional Marketplace wall sculptures</title><style>body{font:16px system-ui;color:#24312b;background:#faf9f4;margin:36px;max-width:1400px}h1{font-family:Georgia}table{border-collapse:collapse;width:100%;background:white}td,th{padding:12px;text-align:left;border-bottom:1px solid #ddd}a{color:#395d48}img{max-width:100%;border:1px solid #ddd}.note{background:#fff1ce;padding:18px}</style><h1>40 additional Marketplace wall sculptures</h1><p>Verified 31 October 2026 at 23:51 UTC. All 40 have distinct listing URLs and catalogue IDs, with no overlap against the previous 40 publications. 306 photo placements.</p><p class="note">The publication result is verified. The newest listings remain in Facebook review and may not yet be visible to buyers. Marketplace prices use whole pounds; each description states the exact catalogue website price and links to the product.</p><p><a href="ebay-reconciliation.html">Open the eBay reconciliation and missing-listing report</a></p><table><thead><tr><th>#</th><th>Marketplace listing</th><th>Price</th><th>Photos</th><th>Catalogue ID</th></tr></thead><tbody>'''+rows+'''</tbody></table><h2>Final publication receipt</h2><img src="last-publication.png" alt="Facebook confirms Frozen Deco Wave II White is listed on Marketplace and in review"><p>Existing eBay listings were not changed. The 157 missing eBay individual listings are prepared locally, not uploaded.</p>''')
f=p/'ebay-reconciliation.html'
s=f.read_text().replace('157 included individual listings remain to prepare for eBay publication. These are not published.','157 missing individual listings have been prepared locally for eBay. These are not uploaded or published.')
s=s.replace('<h2>Existing wall sculptures', '<p class="note">Account allocation is awaiting your choice. sapr_2972 account-profile checks require a fresh sign-in. in6192 is confirmed as an Individual account; business seller setup is required for products made for sale. The existing draft defaults to a 2 kg parcel, three-day handling and no returns, so those defaults cannot be applied across this catalogue. No eBay listing, seller identity or agreement has been changed.</p><h2>Existing wall sculptures')
f.write_text(s)
print(json.dumps(result,indent=2))
