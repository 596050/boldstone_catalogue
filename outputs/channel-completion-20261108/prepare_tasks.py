"""Compile explicit channel tasks. Historical observations remain historical."""
import json
import sys
from pathlib import Path
from datetime import datetime, timezone
sys.path.insert(0, str(Path(__file__).resolve().parents[2]/'catalogue-review'))
from platform_tasks import PLATFORMS
OUT=Path(__file__).parent
load=lambda name:json.loads((OUT/name).read_text())
master=load('master-platform-values.json')
specs=load('app-specifications.json')
audit=json.loads((OUT.parent/'product-social-approval-20261108/pinterest-public-audit.json').read_text())
photos={p['id']:p for p in audit['products']}
checked=datetime.now(timezone.utc).isoformat()
gallery=load('all-selected-photo-verification.json')
assert gallery['status']=='PASS_ALL_CURRENT_SELECTED_PHOTOS' and gallery['product_count']==176
google=load('google-native-refresh-verification.json')
google_pending={d['id'] for d in google['differences']}
restored=load('brandboom-restoration-receipt.json')
manufacturer=load('manufacturer-status-final.json')
assert manufacturer['brand_saved_verified'] and manufacturer['brand_status']=='Brand review pending'
preview_ids={p['catalogue_id'] for p in load('brandboom-preview50-restore-selection.json')}
posts={code:{p['catalogue_id']:p for p in load(code+'-publication-receipts.json')} for code in ('instagram','facebook','linkedin')}
for p in json.loads((OUT.parent/'product-social-approval-20261108/linkedin-ten-posts.json').read_text()):
    posts['linkedin'].setdefault(p['catalogue_id'],dict(url=p['publication']['url'],verified_utc=p['publication'].get('verified_utc',p['publication'].get('published_utc'))))
for p in json.loads((OUT.parent/'product-social-approval-20261108/instagram-publication-receipts.json').read_text()):
    posts['instagram'].setdefault(p['catalogue_id'],p)
def task(key,state,title,detail,scope='external',url=''):
    return dict(id=key,state=state,title=title,detail=detail,scope=scope,url=url)
def entry(state,summary,tasks,url=''):
    return dict(state=state,summary=summary,tasks=tasks,checked_at=checked,url=url)
products={}
for product in specs['products']:
    pid=product['id'];m=master[pid];variant=m.get('pinterest_id');p=photos.get(str(variant));platforms={}
    if not p:
        for code,label in PLATFORMS:
            platforms[code]=entry('not_targeted','Held or excluded from the 176-product publication set.',[])
        products[pid]={'platforms':platforms};continue
    link=p['link']
    platforms['website']=entry('verified','Current retail title, price, stock and all selected photographs match the saved website product.',[
        task('retail_title','verified','Catalogue retail title saved',p['title']+'. Existing product and variant IDs, price, stock and galleries retained.','fields',link),
        task('website_policy','verified','Dispatch and returns reconciled','Shipping, Return and Refund Policy, and FAQ saved and publicly read back. Standard catalogue dispatch is ten working days; customer pays actual change-of-mind return postage.','account'),
        task('selected_photo_sync','verified','All selected photographs saved','All 1,437 selected placements across 176 products verified against current Dropbox identities/content hashes. Existing selected primary leads each carousel.','photos',link)],link)
    pt=[task('merchant_approval','waiting','Pinterest merchant approval','The website is claimed and Instagram connected, but merchant approval has disabled ingestion. Current native issues: minimum product requirements and website quality. Pinterest offers Submit appeal for reassessment; two remain. The owner no-appeals instruction is retained. No appeal submitted. Website/feed corrections do not establish approval.','account','https://uk.pinterest.com/business/catalogs/overview/?subjectBusinessId=846254723639262523'),
        task('pinterest_tracking','action','Finish accepted-consent event verification','Tag 2612823030261 is saved on the website; 15 logic checks pass. Declined consent sent no Pinterest requests. Accepted-consent receipt remains unverified in the browser with advertising blocking present. No purchase event has been simulated.','account')]
    img=p['image']
    if not img['meets_pinterest_documented_1000x1500']:
        pt.append(task('primary_image_size','action','Review primary image resolution',f"Measured {img['width']} × {img['height']} px on {audit['summary']['checked_utc']}. Pinterest documents width >=1,000 and height >=1,500 pixels. Review a genuine higher-resolution selected original. This is a documented-dimension check, not an individual native rejection diagnosis.",'photos',p['image_link']))
    platforms['pinterest']=entry('action' if len(pt)>2 else 'waiting','Feed contains this product. Account ingestion is disabled.',pt,link)
    platforms['google_manufacturer']=entry('action','Manufacturer account 5898308482 has no imported variants.',[
        task('brand_review','waiting','Await review of the corrected brand logo','The rejected low-resolution logo was replaced with the genuine 1,254 × 1,254 Dropbox original. The existing brand saved successfully and now shows Brand review pending; it is not yet approved.','account','https://manufacturers.google.com/mc/brands?a=5898308482'),
        task('genuine_gtin','action','Obtain a genuine Boldstone GTIN','No genuine assigned GTIN is recorded. Locate the existing GS1 licence or obtain the correct licence, assign one identifier per sellable component/finish and verify licensee and assignment. A valid check digit alone does not establish ownership.','fields','https://support.google.com/manufacturers/answer/6124116?hl=en'),
        task('manufacturer_import','waiting','Import after brand approval and GTIN assignment','The correct Merchant account link is active and the 176 publication offers now use the registered Boldstone spelling. Manufacturer Center still needs an approved brand and genuinely assigned GTINs. No identifiers invented or borrowed.','external')])
    native_pending=variant in google_pending
    platforms['google_merchant']=entry('waiting' if native_pending else 'verified','Existing Merchant offer retained; latest native combined export checked.',[
        task('product_approval','verified','Google offer approved','Account 5664655454: all 325 offers approved at the dated native check; this component UUID is present. Approval is eligibility, not proof of impressions or sales.','external'),
        task('native_feed_refresh','waiting' if native_pending else 'verified','Combined offer refresh pending' if native_pending else 'Current title and feed images verified',
             'The existing supplement matched all 176 products without processing errors. This offer still differed in the early combined export; recheck without blindly resubmitting.' if native_pending else 'Saved combined offer matches the current retail title, price, primary image and up to ten secondary images. Existing UUID retained; no duplicate product created.','fields')])
    lunar=variant=='76dc58c2-9754-4b21-a7f8-c6c844dc643c'
    platforms['microsoft_merchant']=entry('action' if lunar else 'waiting','Correct Google account import is populated; no products active at the native check.',[
        task('editorial_rejection' if lunar else 'product_review','action' if lunar else 'waiting',
             'Lunar Wave incorrectly classified as a health product' if lunar else 'Await Microsoft product review',
             'Native rejected sample classifies Lunar Wave - White as Disallowed Supplements and Health Products. Review this sculpture-specific rejection. The other rejected offer is an unrelated greetings card.' if lunar else '8 November native store 50112622: 325 imported offers, 0 active, 323 pending, 2 rejected. Product issues include 311 pending image crawls and 12 manual reviews. Individual approval remains unverified.',
             'external','https://ui.ads.microsoft.com/campaign/vnext/merchantcenter/overview?aid=187335961&cid=255124527&storeId=50112622&uid=193182372')])
    bt=[task('restore_catalogue','verified','Existing catalogue restored','Native import completed: 176 products and SKUs updated, zero added. Inventory reload shows all 176. Per-image upload processing and public Marketplace publication have not been inferred.','external','https://manage.brandboom.com/products/s/111089'),
        task('marketplace_publication','action','Resolve Brandboom Marketplace publication','Owner preview is not a public Marketplace listing. Retail-price choice, plan visibility limit and Marketplace account requirements remain to resolve. No paid upgrade or new agreement accepted.','account')]
    if pid in preview_ids:
        bt.append(task('owner_preview','verified','Restored 50-product owner preview','Exact saved 50-SKU selection is present in presentation 681169. Wholesale only; prepacks off; ordering disabled. No public share link created.','external',restored['preview_url']))
    platforms['brandboom']=entry('action','All 176 restored in editor; Marketplace publication remains separate.',bt)
    platforms['faire']=entry('action','Historical native product status: '+str(m.get('faire_native_product_status') or 'not recorded'),[
        task('protected_price','action','Resolve protected wholesale pricing',str(m.get('faire_price_remediation_status') or 'Check native wholesale prices against the current protected model.')+' Proposed retail prices must remain distinct from approved live retail prices.','fields')])
    for code,label in PLATFORMS:
        if code in platforms:continue
        if code in posts and pid in posts[code]:
            post=posts[code][pid]
            detail='Published native post and purchase destination verified on 8 November. '+('Saved exact Commerce product tag and price verified. ' if code in ('instagram','facebook') else 'Tracked website product link verified. ')
            tasks=[task('product_post','verified','Product post published',detail,'fields',post['url'])]
            state='verified'
            if code in ('instagram','facebook'):
                tasks.append(task('shop_visibility','unknown','Verify customer-facing shop availability','A published tagged post does not establish public shop availability or a completed checkout. Check the product in the customer-facing shop.','external'))
                state='unknown'
            platforms[code]=entry(state,'Current product post verified; saved publication receipt retained.',tasks,post['url'])
            continue
        key={'furnitures':'furnitures_native_status','chairish':'chairish_current_native_status','saatchi_art':'saatchi_art_publication_status','instagram':'instagram_published_status','linkedin':'linkedin_published_status'}.get(code)
        observed=m.get(key) if key else ''
        detail=('Retained master observation: '+str(observed)+'. ' if observed else '')+'Verify the existing native item, current price, description and selected photographs. No new public verification has been inferred from a saved editor record.'
        platforms[code]=entry('unknown','Current per-product platform readback is required.',[task('native_readback','unknown','Verify this product on '+label,detail)])
    products[pid]={'platforms':platforms}
data=dict(checked_at=checked,source='Exact stable component IDs joined to the current master; dated native and public evidence retained in this release packet.',products=products)
(OUT/'platform-task-evidence.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'products':len(products),'pinterest_primary_image_size_tasks':sum(any(t['id']=='primary_image_size' for t in p['platforms']['pinterest']['tasks']) for p in products.values())}))
