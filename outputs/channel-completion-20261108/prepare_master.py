"""Record verified channel outcomes in the existing master, preserving product decisions."""
from pathlib import Path
from datetime import datetime, timezone
import csv, hashlib, json, shutil, sys

ROOT=Path('/Users/tprice/Documents/boldstone');PACKET=Path(__file__).parent;OUT=PACKET/'catalogue'
OUT.mkdir(exist_ok=True)
sys.path[:0]=[str(ROOT/'catalogue-review'),str(ROOT/'catalogue-review/scripts')]
from import_saatchi_snapshot import Xlsx, column
from delete_dropbox import connection
load=lambda p:json.loads(Path(p).read_text())
sha=lambda b:hashlib.sha256(b).hexdigest()
pointer=load(ROOT/'sculpture-catalogue/current-master.json');source=pointer['current_app_review_workbook']
body=Path(source['path']).read_bytes();assert sha(body)==source['sha256']
(OUT/'source-pointer-before.json').write_text(json.dumps(pointer,indent=2)+'\n')
(OUT/'previous-catalogue.xlsx').write_bytes(body)
with connection(ROOT) as (db,_):
    m=db.files_get_metadata(source['dropbox']['id'])
    assert m.rev==source['dropbox']['rev'] and m.path_display==source['dropbox']['path_display']
    dm,r=db.files_download('rev:'+m.rev)
    try:download=r.content
    finally:r.close()
    assert dm.id==m.id and download==body
    metadata={k:str(getattr(m,k)) if k.endswith('modified') else getattr(m,k) for k in ['id','path_display','rev','size','content_hash','server_modified','client_modified']}
(OUT/'previous-dropbox-metadata.json').write_text(json.dumps(metadata,indent=2)+'\n')
shutil.copy2(PACKET/'app-specifications-final.json',OUT/'app-specifications.json')
old=Xlsx(OUT/'previous-catalogue.xlsx');sheet='Wall Sculptures'
headers={old.value(sheet,column(c)+'7'):c for c in range(1,855)}
assert len(headers)==854 and headers['pinterest_profile_website_observed']==854
by_id={old.value(sheet,'AA'+str(r)):r for r in range(8,189)};assert len(by_id)==181
new_headers=['facebook_post_url','facebook_native_post_id','facebook_post_caption','facebook_product_link',
    'facebook_product_tag_sku','facebook_published_status','facebook_checked_utc','facebook_media_sha256',
    'facebook_tag_title_observed','facebook_tag_price_gbp_observed',
    'website_title_sync_status','website_selected_photo_sync_status','website_selected_photo_count','website_policy_status','website_checked_utc',
    'google_merchant_approval_status','google_merchant_image_sync_status','pinterest_tag_id','microsoft_merchant_editorial_status',
    'brandboom_restoration_status','platform_tasks_summary','platform_tasks_json','platform_tasks_checked_utc',
    'google_manufacturer_brand_status','google_manufacturer_logo_status','google_manufacturer_checked_utc']
assert not set(new_headers)&set(headers)
first=855;headers.update({h:first+i for i,h in enumerate(new_headers)})
patches=[]
now=datetime.now(timezone.utc).isoformat()
serial=lambda t:(datetime.fromisoformat(t.replace('Z','+00:00'))-datetime(1899,12,30,tzinfo=timezone.utc)).total_seconds()/86400
def patch(h,row,value,style='text'):
    address=column(headers[h])+str(row);before=old.value(sheet,address)
    if before==value:return
    assert old.formula(sheet,address) is None,(h,address)
    assert not isinstance(value,str) or len(value)<=32767,(h,len(value))
    patches.append(dict(sheet=sheet,cell=address,before=before,value=value,style=style,field=h))
def date(h,row,t):
    before=old.value(sheet,column(headers[h])+str(row))
    patch(h,row,serial(t) if h in new_headers or isinstance(before,(int,float)) else 'Checked UTC: '+t,'utc' if h in new_headers or isinstance(before,(int,float)) else 'text')
for h in new_headers:patch(h,7,h,'header')

social={p['catalogue_id']:p for p in load(PACKET/'social-five-products.json')}
for code in ('instagram','facebook','linkedin'):
    posts=load(PACKET/(code+'-publication-receipts.json'))
    assert len(posts)==5 and len({p['url'] for p in posts})==5
    for p in posts:
        assert p['status']=='PUBLISHED_NATIVE_READBACK'
        pid=p['catalogue_id'];row=by_id[pid];s=social[pid]
        assert not old.value(sheet,column(headers[code+'_post_url'])+str(row)),'Do not overwrite publication history'
        if code=='linkedin':
            assert p['body_readback'] and p['purchase_url_verified']
            fields=dict(linkedin_post_url=p['url'],linkedin_native_activity_id=p['url'].rstrip('/').split(':')[-1],
                linkedin_post_caption=p['caption'],linkedin_post_alt_text=s['alt_text'],linkedin_product_link=s['tracked_urls']['linkedin'],
                linkedin_published_status='Published; native body, unique activity URL and exact tracked purchase destination verified',linkedin_media_sha256=s['sha256'])
        else:
            assert p['full_caption_readback'] and p['tag_saved_readback']
            fields={code+'_post_url':p['url'],code+'_native_post_id':p['native_post_id'],code+'_product_tag_sku':s['sku'],
                code+'_published_status':'Published; full caption, exact Commerce product tag title and price verified',
                code+'_tag_title_observed':p['tag_title'],code+'_tag_price_gbp_observed':float(str(p['tag_price']).replace('£',''))}
            if code=='facebook':fields.update(facebook_post_caption=s['captions']['facebook'],facebook_product_link=s['tracked_urls']['facebook'],facebook_media_sha256=s['sha256'])
            else:fields.update(instagram_prepared_caption=s['captions']['instagram'],instagram_prepared_alt_text=s['alt_text'],instagram_prepared_media_sha256=s['sha256'],instagram_automation_status='Published through native Chrome with focused keyboard caption input; the recorded prepared caption and media hash match the published readback. AppleScript runner remains not live-validated.')
        for h,v in fields.items():patch(h,row,v,'money' if h.endswith('_price_gbp_observed') else 'text')
        date(code+'_checked_utc',row,p['verified_utc'])

tasks=load(PACKET/'platform-task-evidence.json')
photos=load(PACKET/'all-selected-photo-verification.json');assert photos['status']=='PASS_ALL_CURRENT_SELECTED_PHOTOS'
photo_by={p['catalogue_id']:p for p in photos['products']}
native={r['id']:r for r in csv.DictReader((PACKET/'google-native-products-after.tsv').open(encoding='utf-8-sig',newline=''),delimiter='\t')}
google=load(PACKET/'google-native-refresh-verification.json');assert google['status']=='PASS_ALL_176_COMBINED_OFFERS'
gs=load(PACKET/'google-merchant-status.json');assert gs['approved']==325 and gs['not_approved']==0
pm=load(PACKET/'pinterest-merchant-status-final.json');assert not pm['merchant_approved'] and pm['appeals_used']==0
bb=load(PACKET/'brandboom-restoration-receipt.json')
mf=load(PACKET/'manufacturer-status-final.json');assert mf['brand_saved_verified'] and mf['brand_status']=='Brand review pending'
bb_records={p['catalogue_id']:p for p in load(PACKET/'brandboom-restore-plan.json')['records']}
bb50={p['catalogue_id']:p for p in load(PACKET/'brandboom-preview50-restore-selection.json')}
pin=load(PACKET/'pinterest-sheet-cells-after.json')['sheets'][0]['data'][0]['rowData']
pv=lambda c:c.get('userEnteredValue',{}).get('stringValue','')
ph=[pv(c) for c in pin[0]['values']];pin_rows={pv(r['values'][0]):{h:pv(c) for h,c in zip(ph,r['values'])} for r in pin[1:]}
specs=load(PACKET/'app-specifications-final.json');assert len(specs['products'])==181
for pid,row in by_id.items():
    entries=tasks['products'][pid]['platforms']
    summary='; '.join(code+': '+e['state'] for code,e in entries.items())
    patch('platform_tasks_summary',row,summary)
    patch('platform_tasks_json',row,json.dumps(entries,ensure_ascii=False,separators=(',',':')))
    date('platform_tasks_checked_utc',row,tasks['checked_at'])
    patch('google_manufacturer_link_status',row,'Merchant account 5664655454 link Active; publication offers use registered Boldstone spelling. Brand review pending after genuine logo correction; not approved yet.')
    patch('google_manufacturer_product_status',row,'Zero imported variants at the dated native check. Brand logo correction saved successfully; genuine GTINs remain unassigned.')
    patch('google_manufacturer_required_action',row,'Await brand review; locate an existing Boldstone-owned GS1 allocation or obtain the correct licence with owner approval. Verify licensee and assign one genuine GTIN per sellable component/finish, then supply the same identifiers to website, Merchant and Manufacturer Center and verify the daily sync.')
    patch('google_manufacturer_brand_status',row,mf['brand_status'])
    patch('google_manufacturer_logo_status',row,'Previous low-image-quality rejection addressed with genuine 1254 × 1254 Dropbox logo original. Saved and read back; error no longer displayed. Brand approval remains pending.')
    date('google_manufacturer_checked_utc',row,mf['checked_at'])
    if pid not in photo_by:continue
    vid=str(old.value(sheet,column(headers['pinterest_id'])+str(row)));g=native[vid]
    title=old.value(sheet,column(headers['Retail / website name'])+str(row));assert title==g['title']
    patch('website_title_sync_status',row,'Current retail title saved; native CSV and public title readback verified. Finish wording applied where required.')
    patch('website_selected_photo_sync_status',row,'All current app-selected Listing and In situ photos verified in the saved main carousel; primary matches the app. No duplicate file placements.')
    patch('website_selected_photo_count',row,photo_by[pid]['website_count'],'integer')
    patch('website_policy_status',row,'Shipping, Returns and FAQ reconciled and publicly read back: ten-working-day catalogue dispatch; customer pays actual change-of-mind return postage; bespoke commissions separately agreed.')
    date('website_checked_utc',row,photos['checked_at'])
    for h,v in dict(google_merchant_native_title=g['title'],google_merchant_native_brand=g['brand'],google_merchant_native_price_gbp=float(g['price'].split()[0]),
        google_merchant_title_update_required='No; native combined offer matches current catalogue retail title',google_merchant_title_update_action='Existing offer updated through supplement 10789003059; no duplicate product. Preserve the same UUID on future refreshes.',
        google_merchant_approval_status='Approved. Native account 5664655454: 325 approved, 0 limited, 0 not approved; this publication UUID is present. Eligibility does not establish impressions or sales.',
        google_merchant_image_sync_status='Exact current primary and up to ten additional selected website photos match the native combined-offer export. All newly appended photographs included within the platform limit.').items():
        patch(h,row,v,'money' if h.endswith('_gbp') else 'text')
    date('google_merchant_checked_utc',row,gs['checked_at'])
    assert g['brand']=='Boldstone'
    p=pin_rows[vid]
    patch('pinterest_additional_image_link',row,p['additional_image_link'])
    patch('pinterest_title_match_check',row,'Exact title now matches the saved website and current retail catalogue')
    patch('pinterest_daily_feed_status',row,'Hosted 176-product CSV refreshed and publicly read back on 8 November. Daily 07:00 London schedule retained, but ingestion remains disabled pending merchant approval. No appeal submitted.')
    date('pinterest_merchant_checked_utc',row,pm['checked_at'])
    date('pinterest_source_checked_utc',row,load(PACKET/'pinterest-sheet-verification.json')['checked_at'])
    patch('pinterest_merchant_status',row,'Not approved: minimum product and website quality requirements; 0 approved products. Native reassessment route is Submit appeal; owner no-appeals instruction retained. Two appeals remain; none used.')
    patch('pinterest_tag_id',row,'2612823030261')
    patch('pinterest_tag_verification',row,'Consent-gated tag installed and public code verified. Fifteen logic checks pass. Declined consent sent no Pinterest requests. Accepted-consent event receipt and completed-purchase tracking remain unverified; no purchase event simulated.')
    patch('microsoft_merchant_import_status',row,'Native store 50112622 populated from correct Google account 5664655454: 325 imported offers, 0 active, 323 pending, 2 rejected. Image crawling/manual review pending; not live verified.')
    patch('microsoft_merchant_editorial_status',row,'Lunar Wave - White is incorrectly classified as Disallowed Supplements and Health Products; needs sculpture-specific editorial correction. No all-product review submitted.' if vid=='76dc58c2-9754-4b21-a7f8-c6c844dc643c' else 'Publication approval remains pending; do not infer visibility from the populated import. The other rejected offer is an unrelated greetings card.')
    patch('brandboom_restoration_status',row,'Restored in native editor: 176 existing products/SKUs updated, zero added. Inventory reloaded with all 176. Per-image processing and Marketplace/public publication remain unverified.')
    patch('brandboom_publication_status',row,'Restored in editor only; owner-only 50-product preview rebuilt. Not submitted to Marketplace; not 176 public listings.')
    patch('brandboom_source_image_ids',row,'\n'.join(bb_records[pid]['image_ids']))
    patch('brandboom_source_image_count',row,bb_records[pid]['image_count'],'integer')
    patch('brandboom_image_verification',row,'Current selected image manifest supplied in the existing-SKU restore. Native per-image processing not independently verified; no image re-import repeated.')
    patch('brandboom_presentation_status',row,'Old full-library presentation was removed by the owner. Rebuilt owner-only presentation 681169 contains the exact saved 50-SKU preview. Not public or Marketplace submitted.')
    patch('brandboom_private_preview_url',row,bb['preview_url'] if pid in bb50 else '')
    patch('brandboom_preview_product_count',row,50 if pid in bb50 else 0,'integer')
    for h,v in dict(brandboom_presentation_id='681169' if pid in bb50 else '',
        brandboom_presentation_edit_url=bb['preview_edit_url'] if pid in bb50 else '',
        brandboom_presentation_title='Wall Sculptures - 50 Preview' if pid in bb50 else '',
        brandboom_presentation_section='PRODUCTS' if pid in bb50 else '',
        brandboom_presentation_order_type='Ordering disabled; native blank future-shipping header is a platform display issue' if pid in bb50 else 'Not assigned to the restored preview',
        brandboom_presentation_show_prices='Wholesale Price' if pid in bb50 else '',
        brandboom_presentation_prepack_display='Off' if pid in bb50 else '').items():patch(h,row,v)
    date('brandboom_checked_utc',row,bb.get('preview_verified_at',now))
    if pid in bb50:
        for h,v in dict(brandboom_preview50_presentation_id='681169',brandboom_preview50_edit_url=bb['preview_edit_url'],
            brandboom_preview50_status='Saved and reloaded: exact 50-SKU owner preview, wholesale only, prepacks off, ordering disabled. No share links; not Marketplace submitted. Native preview retains a blank future-shipping header (platform display issue).').items():patch(h,row,v)
counts=dict(component_records=181,publication_products=176,website_finish_titles_updated=62,website_photo_appends=20,website_primary_order_corrections=1,selected_photo_placements=1437,
    google_approved_offers=325,google_publication_products_matched=176,google_title_mismatches=0,google_image_mismatches=0,
    instagram_published=5,facebook_published=5,linkedin_published=5,pinterest_feed_image_cells_refreshed=21,pinterest_primary_image_size_tasks=96,pinterest_appeals_used=0,
    gtins_assigned=0,manufacturer_logos_corrected=1,google_brand_names_aligned=176,brandboom_products_restored=176,brandboom_new_products=0,brandboom_preview_products=50)
fb_first=column(headers['facebook_post_url']);web_first=column(headers['website_title_sync_status'])
facebook_row=by_id[next(iter(social))]
plan=dict(scope='Record verified website Finish titles, full selected galleries and policies; refreshed approved Google offers and existing Pinterest source; restored Brandboom editor/owner preview; five new native posts on each of Instagram, Facebook and LinkedIn; dated app tasks and outstanding genuine GTIN/Pinterest/Microsoft gates. No price, labour, material, identity, stock or selection decisions changed.',
    first_added_column=first,last_added_column=first+len(new_headers)-1,new_headers=new_headers,patches=patches,
    previews=[dict(name='channel-status',range=web_first+'7:'+column(headers['website_selected_photo_count'])+'9'),
        dict(name='facebook',range=fb_first+str(facebook_row)+':'+column(headers['facebook_native_post_id'])+str(facebook_row)),
        dict(name='google',range=column(headers['google_merchant_native_title'])+'7:'+column(headers['google_merchant_native_price_gbp'])+'9')],counts=counts,prepared_utc=now)
(OUT/'plan.json').write_text(json.dumps(plan,indent=2,ensure_ascii=False)+'\n')
print(json.dumps(dict(patched_cells=len(patches),added_fields=len(new_headers),previous_revision=metadata['rev'],counts=counts)))
