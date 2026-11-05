import json, re, sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote
ROOT=Path('/Users/tprice/Documents/boldstone'); OUT=Path(__file__).parent; RUN=OUT.parent
sys.path.insert(0,str(ROOT/'catalogue-review/scripts'))
from import_saatchi_snapshot import Xlsx,column,column_index
x=Xlsx(OUT/'previous-catalogue.xlsx'); app=json.loads((OUT/'app-after.json').read_text())
read=lambda f:json.loads((RUN/f).read_text())
headers={x.value('Wall Sculptures',a):re.sub(r'\d','',a) for a in x.cells['Wall Sculptures'] if re.fullmatch(r'[A-Z]+7',a)}
rows={x.value('Wall Sculptures',f'AA{r}'):r for r in range(8,189)}
assert len(rows)==len(app['products'])==181
products={p['id']:p for p in app['products']}
assert rows.keys()==products.keys()
patches=[]; added=[]; now='UTC | '+datetime.now(timezone.utc).isoformat()
def put(sh,a,v):
 before=x.value(sh,a)
 if before!=v:patches.append(dict(sheet=sh,cell=a,before=before,value=v))
def setfield(pid,h,v):
 if h not in headers:
  headers[h]=column(max(map(column_index,headers.values()))+1);added.append(h)
  put('Wall Sculptures',headers[h]+'7',h)
 put('Wall Sculptures',headers[h]+str(rows[pid]),v)
image_rows={(x.value('Images',f'C{r}'),x.value('Images',f'AD{r}')):r for r in x.rows('Images',8)}
image_urls={x.value('Images',f'AD{r}'):'https://www.dropbox.com/preview'+quote(x.value('Images',f'AE{r}'),safe='/') for r in x.rows('Images',8) if x.value('Images',f'AE{r}')}
changes=read('additional-listing-photo-receipts.json')+read('saatchi-additional-listing-photo-receipts.json')+[read('saatchi-bone-pair-selection-receipt.json')]
assert len(changes)==15
changed_pids=set()
for r in changes:
 pid=r['request']['product_id']; iid=r['request']['item_id']; changed_pids.add(pid)
 assert iid in [p['id'] for p in products[pid]['photos']['listing']['images']]
 n=image_rows[(pid,iid)]; d=r['request']['data']
 for c,v in [('I','Yes'),('N',', '.join(d['uses'])),('O',d['decision']),('P',d.get('order',0)),('Y',d.get('alt','')),('Z',d.get('caption','')),('AB',d.get('notes',''))]:put('Images',c+str(n),v)
for pid in changed_pids:
 photos=products[pid]['photos']; listing=photos['listing']['images']; n=rows[pid]
 put('Wall Sculptures','N'+str(n),len(listing))
 setfield(pid,'saatchi_listing_image_urls','\n'.join(image_urls[p['id']] for p in listing))
 setfield(pid,'saatchi_selected_gallery_count',len({p['id'] for kind in ['listing','in_situ'] for p in photos[kind]['images']}))
 setfield(pid,'catalogue_photo_selection_checked_utc',now)
for r in read('saatchi-native-receipts.json'):
 pid=r['catalogue_id']; native=r['native_id']; assert products[pid]['listing_decision']=='include'
 assert x.value('Wall Sculptures','AQ'+str(rows[pid]))==r['sku']
 photo=r.get('photo_id') or products[pid]['photos']['primary_listing']['image_id']
 data=dict(native_artwork_id=native,public_url=r['public_url'],studio_url=f'https://www.saatchiart.com/en-gb/studio/art/{native}/overview',publication_status='Published - native readback verified',publication_checked_utc=now,primary_photo_id=photo,primary_original_url=image_urls[photo],artwork_price_usd=r['price_usd'],packaging='Crate',packed_weight_kg_estimate=r['packed_weight_kg_estimate'],packing_basis='Upper catalogue artwork mass plus conservative 16 kg crate allowance. Estimate only; final crate dimensions, mass and packing photographs must be verified before collection.',units_available_native=1,year_native=2026,year_basis='Owner-authorized current cast production planning year; not a confirmed original design date.',ready_to_hang_native='No - installed hardware not verified',publication_evidence=str((RUN/f'evidence/saatchi-{native}-published.txt').relative_to(ROOT)))
 if native=='14388967':data['publication_evidence']=str((RUN/'evidence/saatchi-wave-crate-correction.txt').relative_to(ROOT))
 for k,v in data.items():setfield(pid,'saatchi_art_'+k,v)
 setfield(pid,'saatchi_art_edition_update_state','Native Published readback verified 5 November 2026: Limited Edition 50, one offer available, Saatchi only. No serial number allocated.')
for r in read('chairish-photo-save-receipts.json'):
 pid=next(pid for pid in rows if x.value('Wall Sculptures','AQ'+str(rows[pid]))==r['sku'])
 for k,v in dict(native_listing_id=r['native_id'],gallery_checked_utc=now,photo_count_verified=2,current_native_status='Draft',photo_completion_note='Two genuine matching photos saved and reopened; primary and protected price preserved. Submission held pending confirmation of all-inclusive US delivery rates.').items():setfield(pid,'chairish_'+k,v)
for r in read('instagram-four-posts.json'):
 sku=r.get('sku') or r['product_tag_sku'];pid=next(pid for pid in rows if x.value('Wall Sculptures','AQ'+str(rows[pid]))==sku)
 assert r['published'] and r['caption_verified'] and r['product_tag_saved']
 for k,v in dict(post_url=r['instagram_url'],native_post_id=r['post_id'],product_tag_sku=sku,published_status='Published; caption and exact catalogue product tag verified',checked_utc=now).items():setfield(pid,'instagram_'+k,v)
assert len({(p['sheet'],p['cell']) for p in patches})==len(patches)
plan=dict(status='PREPARED',scope='5 November 2026: 14 verified Saatchi publications, four verified Chairish two-photo drafts, four published Instagram product-tagged posts, and 15 newly selected Listing photo associations. Existing prices, costs, dated platform observations and all other records preserved. This is a targeted publication/photo update, not a full specifications refresh.',patches=patches,added_headers=added,headers=headers,first_added_column=min(column_index(headers[h]) for h in added),last_column=max(map(column_index,headers.values())),products=181,changed_photo_products=len(changed_pids),saatchi_publications=14,chairish_galleries=4,instagram_posts=4,checked_at=now)
(OUT/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
print(json.dumps({k:v for k,v in plan.items() if k not in ['patches','headers']},indent=2));print('patches',len(patches))
