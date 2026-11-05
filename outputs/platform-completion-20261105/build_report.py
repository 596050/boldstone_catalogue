import collections,copy,html,json,sys
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path('/Users/tprice/Documents/boldstone');OUT=Path(__file__).parent
sys.path.insert(0,str(ROOT/'catalogue-review/scripts'))
from prepare_saatchi_catalogue import native_artwork_bindings
read=lambda p:json.loads(p.read_text())
baseline=read(ROOT/'outputs/platform-live-completion-20261104/completion-worklist.json')
new=read(OUT/'saatchi-native-receipts.json');new_by_sku={r['sku']:r for r in new}
binding=native_artwork_bindings(ROOT/'outputs/catalogue-marketplace-publication-20261101/saatchi-current/primary-draft-receipts.json')
chair={r['sku']:r for r in read(OUT/'chairish-photo-save-receipts.json')}
records=copy.deepcopy(baseline['records']);remaining=[]
for r in records:
 sku=r['sku'];s=r['saatchi']
 if sku in new_by_sku:
  n=new_by_sku[sku]
  s.update(state='Published and for sale',missing=False,native_id=n['native_id'],url=n['public_url'],status_basis='5 November 2026 native Published readback and one available offer; original artwork ID retained',next_action='RETAIN_EXISTING_ARTWORK_ID',publication_receipt=n)
 if sku in chair:
  r['chairish'].update(saved_photos_verified=2,gallery_checked_date='2026-11-05',next_action='CONFIRM_ALL_INCLUSIVE_US_DELIVERY_RATE_THEN_VALIDATE_AND_SUBMIT_EXISTING_DRAFT')
 if sku not in binding:
  assert s['missing'];remaining.append({k:r[k] for k in ['catalogue_id','sku','title','app_url','folder_url']}|{'photo_review':s.get('photo_review'),'next_action':s['next_action']})
assert len(records)==176 and len(binding)==112 and len(remaining)==64
counts=dict(saatchi_published=112,saatchi_remaining=64,instagram_new_posts=4,chairish_second_photos_fixed=4,chairish_second_photo_gaps=3,chairish_submissions_this_pass=0)
result=dict(prepared_at=datetime.now(timezone.utc).isoformat(),counts=counts,records=records,saatchi_remaining=remaining,scope='The original 176-product publication manifest; other app records have not been silently added. New native evidence overlays the dated 4 November worklist. Unchanged platform observations retain their original timestamps.')
(OUT/'completion-worklist.json').write_text(json.dumps(result,indent=2)+'\n')
(OUT/'saatchi-remaining-64.json').write_text(json.dumps(remaining,indent=2)+'\n')
esc=lambda s:html.escape(str(s or ''))
link=lambda url,label:f'<a href="{esc(url)}">{esc(label)}</a>'
table=lambda headers,rows:'<table><thead><tr>'+''.join('<th>'+esc(h)+'</th>' for h in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+v+'</td>' for v in row)+'</tr>' for row in rows)+'</tbody></table>'
posts=read(OUT/'instagram-four-posts.json')
sections=[('<h1>Boldstone publication update</h1><p>Verified 5 November 2026. This report separates saved edits, public publication and outstanding work.</p>'),
 '<p><strong>Saatchi: 112 published of the 176-product release scope.</strong> Fourteen were completed this pass: one existing draft and thirteen new artworks. Sixty-four remain. The Dropbox catalogue update passed native revision and exact byte readback at 18:43 UTC.</p>',
 '<h2>Four Instagram posts published</h2>'+table(['Product','Post','Catalogue product tag'],[[esc(p['title']),link(p['instagram_url'],'Open Instagram post'),esc(p['sku'])+' — saved and verified'] for p in posts]),
 '<h2>Saatchi artworks completed</h2>'+table(['Product','Native artwork','Artwork USD','Packing'],[[esc(r['title']),link(r['public_url'],r['native_id']),esc(r['price_usd']),f"Crate; {esc(r['packed_weight_kg_estimate'])} kg estimated, not measured"] for r in new]),
 '<p>All fourteen are limited-edition casts with a Saatchi-only cap of 50 and one offer available. No serial numbers were allocated. The 2026 planning year is qualified in the descriptions. Companion-panel photographs explicitly identify the single panel supplied. Genuine originals were used without upscaling or fabricated extra views. Public buyer prices include destination shipping and differ from the Studio artwork-only USD price.</p>',
 '<h2>Chairish</h2><p>Four genuine second photographs were added, saved and independently reopened. Existing primary photographs, SKUs and protected asking prices were preserved. No new submission occurred: the native form requires flat US delivery rates to include packaging, shipping, taxes and duties. The saved amounts are estimates, and the owner’s rate decision is pending.</p>'+table(['Product / SKU','Existing editor','Verified photos','State'],[[esc(r['sku']),link(f"https://www.chairish.com/product/{r['native_id']}/update",r['native_id']),'2','Draft — delivery rate decision pending'] for r in chair.values()]),
 '<p>Still missing a genuine second matching photo: World Colours Circle Brass (37954778), Marbled Circle Azure Blue/White (37954777), Acanthus Frond Left Pewter (37950217). No different finish was substituted.</p>',
 '<h2>Instagram unavailable warning</h2><p>The affected Ammonite Petite II record is eligible/in stock in the connected Meta catalogue. Its Europe Instagram preview showed no warning. The correct website product, cart and checkout rendered; the single test cart item was removed and no order was placed. This does not establish that the phone warning is fixed. An exact share link from the affected phone product page is still needed to distinguish the current record from an older tag. No speculative Meta shipping or shop-draft changes were made.</p>',
 '<h2>Catalogue and verification</h2><p>The targeted workbook update contains 14 native Saatchi publications, four verified Chairish galleries, four Instagram post mappings and 15 new Listing selections. It retains all 181 components, existing costs/prices, dated platform observations, 12 sheets and all 27,190 existing formulas. Only the master cells, image-purpose cells and native master-table extension changed; other ZIP parts are byte-identical. The local canonical pointer now names the updated workbook.</p>',
 '<p>The upload-preparation bug was fixed so published native receipts survive future preparation runs. Tests reject conflicting IDs and unverified published records. Crate planning now uses inclusive size/weight thresholds and retains missing measurements as unknown. All 16 preparation tests pass.</p>',
 '<p>An apparent cut-off description in accessibility text was checked against the actual public screenshot and saved editor: the complete customization and single-panel copy was present. No unnecessary copy rewrite was made.</p>',
 '<p>'+link('workbook/catalogue_wall_sculptures.xlsx','Updated local workbook')+' · '+link('workbook/dropbox-receipt.json','Dropbox revision and byte readback')+' · '+link('workbook/verification.json','Workbook preservation checks')+' · '+link('native-binding-registry-update-receipt.json','Duplicate-prevention reconciliation')+'</p>',
 '<h2>Remaining 64 Saatchi products</h2><p>These products still need qualifying complete-product originals or further photo review. The 115 additional original-header checks and reviewed family folders do not constitute an exhaustive search of all Dropbox content. Existing selected low-resolution images were not enlarged to simulate additional source detail.</p>'+table(['Product','SKU','Current action','Photo source'],[[link(r['app_url'],r['title']),esc(r['sku']),esc(r['next_action'].replace('_',' ').capitalize()),link(r['folder_url'],'Open Dropbox folder')] for r in remaining]),
 '<h2>Evidence</h2><p>'+link('evidence/saatchi-portfolio-112.png','Native portfolio count')+' · '+link('evidence/saatchi-ammonite-left-full-description.png','Complete public description')+' · '+link('evidence/instagram-four-posts-profile.png','Instagram profile after publication')+'</p>',
 '<h2>Platform packing source</h2><p>'+link('https://support.saatchiart.com/hc/en-us/articles/14709932602139-Packaging-Your-Artwork','Saatchi official sculpture packaging and measurement-photograph requirements')+'</p>']
(OUT/'publication-update.html').write_text('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Boldstone publication update — 5 November 2026</title><style>body{font:16px/1.55 system-ui,sans-serif;max-width:1200px;margin:40px auto;padding:0 22px;color:#26362e}h1,h2{color:#35533b}h2{margin-top:2em}table{width:100%;border-collapse:collapse;margin:1em 0}th,td{padding:10px;border:1px solid #d8dfd5;text-align:left;vertical-align:top}th{background:#edf2e8}a{color:#315d83}p{max-width:1050px}</style>'+''.join(sections)+'</html>')
print(json.dumps({'counts':counts,'report':str(OUT/'publication-update.html')}))
