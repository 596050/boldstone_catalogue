from pathlib import Path
import json,collections,html,hashlib
from datetime import datetime,timezone
p=Path(__file__).resolve().parent
existing=json.loads((p/'existing-wall-listings.json').read_text())
plan=json.loads((p.parent/'website-marketplace-refresh-20261031/website-final-plan.json').read_text())
products=plan['products'];by_id={r['catalogue_id']:r for r in products}
# Catalogue SKUs corroborate eight item IDs. The remaining matches were visually reviewed
# against the workbook's current eBay primary photo and current catalogue contact sheets.
visual={'188899058652':167,'188682484002':106,'188630719758':45,'188568590316':111,'188568472583':53,'188567095547':104,'188567075857':107,'188566937534':113,'188566796861':109,'188365590301':126,'188365584318':125}
matches=[]
for r in existing:
 iid=r['Item ID']; hits=[q for q in products if q.get('sku')=='EBAY-'+iid]
 basis='Exact eBay item ID retained in catalogue SKU; photographs checked'
 if not hits and iid in visual:hits=[products[visual[iid]]];basis='Visual design and finish match; keep existing listing untouched'
 if iid=='188721196311':
  hits=[products[57],products[59]];basis='Two-piece Echo Pattern Verdigris set: distinct bundle; not an identical individual-component offer'
 assert hits,(iid,'unmatched')
 matches.append({'ebay_item_id':iid,'ebay_title':r['Title'],'ebay_url':r['Listing URL'],'catalogue_ids':[x['catalogue_id'] for x in hits],'catalogue_names':[x['catalogue_name'] for x in hits],'scope':'pair_bundle' if len(hits)>1 else 'individual','basis':basis,'existing_seller_price':r['Seller listing price'],'existing_condition':r['Condition'],'photo_url':r['photos'][0]})
covered={m['catalogue_ids'][0] for m in matches if m['scope']=='individual'}
assert len(matches)==20 and len(covered)==19
included=[q for q in products if q.get('public') and q['listing_decision']=='include']
missing=[q for q in included if q['catalogue_id'] not in covered]
assert len(included)==176 and len(missing)==157
repeated=collections.defaultdict(list)
for m in matches:repeated[m['ebay_title'].casefold()].append(m['ebay_item_id'])
repeated={t:ids for t,ids in repeated.items() if len(ids)>1}
result={'created_utc':datetime.now(timezone.utc).isoformat(),'source_workbook':'/Users/tprice/Downloads/ebay_listings_and_orders.xlsx','workbook_sha256':hashlib.sha256(Path('/Users/tprice/Downloads/ebay_listings_and_orders.xlsx').read_bytes()).hexdigest(),'source_cutoff':15209,'sapr_active_total':39,'wall_sculpture_active':20,'individual_components_already_covered':19,'pair_bundles':1,'included_catalogue':176,'missing_individual_listings':157,'in6192_active_total':0,'confirmed_duplicate_individuals':0,'repeated_title_groups':repeated,'matches':matches,'missing':missing,'publication_status':'Prepared only. Account allocation pending. Existing eBay listings untouched. Business seller setup and listing terms must be resolved before publication.'}
(p/'ebay-reconciliation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
esc=html.escape
cards=[]
for m in matches:
 cards.append('<article><img loading="lazy" src="'+esc(m['photo_url'])+'"><h3>'+esc(' / '.join(m['catalogue_names']))+'</h3><p><a href="'+esc(m['ebay_url'])+'">'+m['ebay_item_id']+'</a> · £'+m['existing_seller_price']+' · '+esc(m['existing_condition'])+'</p><p>'+esc(m['ebay_title'])+'</p><p>'+esc(m['basis'])+'</p></article>')
missing_rows=''.join('<tr><td>'+esc(q['catalogue_name'])+'</td><td>'+esc(q['retail_name'])+'</td><td>£'+q['price']+'</td><td>'+esc(q['sku'])+'</td><td><a href="'+esc(q['website_url'])+'">Website</a> · <a href="'+esc(q['app_url'])+'">App</a></td></tr>' for q in missing)
doc='''<!doctype html><meta charset="utf-8"><title>eBay sculpture reconciliation</title><style>body{font:16px system-ui;color:#24312b;background:#faf9f4;margin:36px;max-width:1500px}h1,h2{font-family:Georgia}section{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:20px}article{padding:18px;border:1px solid #ddd;background:white}img{width:100%;height:230px;object-fit:contain}table{border-collapse:collapse;width:100%;background:white}td,th{padding:10px;text-align:left;border-bottom:1px solid #ddd}a{color:#395d48}.note{background:#fff1ce;padding:18px}</style><h1>eBay sculpture reconciliation</h1><p>Checked 31 October 2026. Source: supplied workbook plus live account inventories; current catalogue event 15209.</p><p>39 active sapr_2972 listings: 20 wall-sculpture offers, comprising 19 individual catalogue components and one Echo Pattern two-piece set. in6192 has no active listings.</p><p>No confirmed identical duplicates were found among those 20 active wall-sculpture offers. Repeated titles describe different designs. Existing listings have not been edited.</p><p class="note">157 included individual listings remain to prepare for eBay publication. These are not published. The Echo Pattern individual pieces remain eligible as separate offers because the existing listing sells a pair. Do not publish identical fixed-price items on both accounts. in6192 is currently an Individual account; eBay requires business registration for items made to sell.</p><p>Existing eBay prices and descriptions differ from the current catalogue. This audit preserves them at your request. In particular, the Strata listing description refers to a spherical/lunar design although its photographs show Strata. The current catalogue remains the source for any new listings.</p><h2>Existing wall sculptures — leave unchanged</h2><section>'''+''.join(cards)+'''</section><h2>Missing individual listings (157)</h2><table><thead><tr><th>Catalogue component</th><th>Retail title</th><th>Price</th><th>SKU</th><th>Review</th></tr></thead><tbody>'''+missing_rows+'''</tbody></table><p><a href="https://www.ebay.co.uk/help/policies/listing-policies/duplicate-listings-policy?id=4255">eBay duplicate listing policy</a> · <a href="https://www.ebay.co.uk/help/policies/selling-policies/selling-practices-policy/business-seller-policy?id=4710">eBay business seller policy</a></p>'''
(p/'ebay-reconciliation.html').write_text(doc)
print(json.dumps({k:v for k,v in result.items() if k not in ['matches','missing']},indent=2))
