from pathlib import Path
from datetime import datetime,timezone
from html import escape
import json,hashlib
out=Path(__file__).resolve().parent
verification=json.loads((out/'marketplace-final-verification.json').read_text())
assert verification['status']=='PASS_TEN_UNIQUE_PUBLISHED_LISTINGS'
records=verification['records'];assert len(records)==len({r['listing_id'] for r in records})==10
plan=json.loads((out/'marketplace-first10.json').read_text());by_id={r['catalogue_id']:r for r in plan['records']}
rows=[]
for r in records:
 p=by_id[r['catalogue_id']]
 rows.append(f'<tr><td>{r["order"]}</td><td><img loading="lazy" src="{escape(p["photos"][0]["url"])}?format=300w" alt="{escape(r["title"])}"></td><td><a href="{escape(r["url"])}">{escape(r["title"].replace(" | Wall Sculpture",""))}</a><br><small>{escape(r["catalogue_id"])}</small><br><a href="{escape(p["website_url"])}">Website listing</a></td><td>£{r["marketplace_price"]}</td><td>£{r["catalogue_price"]}</td><td>{len(p["photos"])}</td><td>Published · awaiting Facebook review</td></tr>')
html='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Boldstone · Website and Marketplace refresh</title><style>body{margin:40px auto;max-width:1250px;padding:0 20px;font:16px/1.5 system-ui;color:#25342d;background:#f7f7f3}h1{font:38px Georgia}table{border-collapse:collapse;width:100%;background:white}td,th{border:1px solid #d8ddd4;padding:12px;text-align:left}img{width:100px;height:100px;object-fit:contain}a{color:#355c47}small{color:#6b756e}.wrap{overflow-x:auto}</style><h1>Boldstone catalogue and Marketplace</h1><p>Verified 31 October 2026, 20:46 GMT. Source: the local sculpture catalogue, event 15209.</p><ul><li>Website: all 176 products match the catalogue; 1,417 gallery placements, including 1,044 in-situ placements. Homepage: 176 correct names, links and primary photographs.</li><li>Facebook / Instagram catalogue: 176 supplement updates accepted, 0 failures and 0 issues. Native Squarespace feed also refreshed successfully.</li><li>Google Merchant Center: 176 updated and 176 matched, no file issues. Initial product approval remains pending.</li><li>Marketplace: ten unique listings published and verified after reloading. All are awaiting Facebook review. No paid promotions were started.</li></ul><p>The first ten were selected alphabetically by catalogue name from included, public products. Marketplace accepts whole-pound prices, so these are rounded to the nearest pound; the website and catalogue retain their exact prices. The 49 photographs are the currently selected catalogue images.</p><div class="wrap"><table><thead><tr><th>#</th><th>Primary</th><th>Sculpture / links</th><th>Marketplace</th><th>Website</th><th>Photos</th><th>Status</th></tr></thead><tbody>'''+''.join(rows)+'</tbody></table></div><p><a href="https://www.facebook.com/marketplace/you/selling/">Open your Marketplace listings</a></p></html>'
(out/'listing-results.html').write_text(html)
# Remove only this task's staging downloads, after all ten upload receipts exist.
removed=0;total=0
for path in sorted({a['local_path'] for r in plan['records'] for a in r['photos']}):
 f=Path(path);assert f.parent==out/'marketplace-images'
 expected=next(a['sha256'] for r in plan['records'] for a in r['photos'] if a['local_path']==path)
 if f.exists():
  raw=f.read_bytes();assert hashlib.sha256(raw).hexdigest()==expected;total+=len(raw);f.unlink();removed+=1
for r in plan['records']:
 for a in r['photos']:a['local_staging_status']='removed_after_verified_upload; re-download from source URL if needed'
(out/'marketplace-first10.json').write_text(json.dumps(plan,indent=2,ensure_ascii=False))
completion={'completed_utc':datetime.now(timezone.utc).isoformat(),'status':'WEBSITE_CURRENT_CHANNELS_REFRESHED_TEN_MARKETPLACE_LISTINGS_SUBMITTED','website_products':176,'meta_updated':176,'google_updated':176,'marketplace_submitted':10,'marketplace_pending_review':10,'marketplace_photos':49,'google_approval':'Pending initial review','temporary_downloads_removed':removed,'temporary_bytes_removed':total}
(out/'completion.json').write_text(json.dumps(completion,indent=2));print(json.dumps(completion,indent=2))
