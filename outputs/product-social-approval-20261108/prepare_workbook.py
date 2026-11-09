"""Plan a targeted social/merchant evidence update; preserve all product data."""
import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path('/Users/tprice/Documents/boldstone')
PACKET=Path(__file__).parent
OUT=PACKET/'catalogue'
OUT.mkdir(exist_ok=True)
sys.path[:0]=[str(ROOT/'catalogue-review'),str(ROOT/'catalogue-review/scripts')]
from import_saatchi_snapshot import Xlsx, column, column_index
from delete_dropbox import connection
load=lambda p:json.loads(Path(p).read_text())
sha=lambda b:hashlib.sha256(b).hexdigest()
pointer=load(ROOT/'sculpture-catalogue/current-master.json')
source=pointer['current_app_review_workbook']
body=Path(source['path']).read_bytes()
assert sha(body)==source['sha256']
(OUT/'source-pointer-before.json').write_text(json.dumps(pointer,indent=2)+'\n')
(OUT/'previous-catalogue.xlsx').write_bytes(body)
with connection(ROOT) as (db,_):
    m=db.files_get_metadata(source['dropbox']['id'])
    assert m.rev==source['dropbox']['rev'] and m.path_display==source['dropbox']['path_display']
    dm,r=db.files_download('rev:'+m.rev)
    try: downloaded=r.content
    finally:r.close()
    assert dm.id==m.id and downloaded==body
    meta={k:str(getattr(m,k)) if k.endswith('modified') else getattr(m,k) for k in ['id','path_display','rev','size','content_hash','server_modified','client_modified']}
(OUT/'previous-dropbox-metadata.json').write_text(json.dumps(meta,indent=2)+'\n')
shutil.copy2(PACKET/'app-specifications.json',OUT/'app-specifications.json')
old=Xlsx(OUT/'previous-catalogue.xlsx')
sheet='Wall Sculptures'
headers={old.value(sheet,column(c)+'7'):c for c in range(1,839)}
assert len(headers)==838 and headers['instagram_automation_status']==837 and headers['channel_remediation_sources']==838
by_id={old.value(sheet,'AA'+str(r)):r for r in range(8,189)}
assert len(by_id)==181
new_headers=['linkedin_post_url','linkedin_native_activity_id','linkedin_post_caption','linkedin_post_alt_text',
             'linkedin_product_link','linkedin_published_status','linkedin_checked_utc','linkedin_media_sha256',
             'instagram_tag_title_observed','instagram_tag_price_gbp_observed',
             'pinterest_primary_width_px_observed','pinterest_primary_height_px_observed',
             'pinterest_primary_image_size_check','pinterest_title_match_check','pinterest_audit_checked_utc',
             'pinterest_profile_website_observed']
assert not(set(new_headers)&set(headers))
first=839
headers.update({h:first+i for i,h in enumerate(new_headers)})
patches=[]
serial=lambda text:(datetime.fromisoformat(text.replace('Z','+00:00'))-datetime(1899,12,30,tzinfo=timezone.utc)).total_seconds()/86400
def patch(header,row,value,style='text'):
    cell=column(headers[header])+str(row)
    before=old.value(sheet,cell)
    if before==value:return
    assert old.formula(sheet,cell) is None
    patches.append(dict(sheet=sheet,cell=cell,before=before,value=value,style=style,field=header))
for h in new_headers:patch(h,7,h,'header')
linkedin=load(PACKET/'linkedin-ten-posts.json')
assert len(linkedin)==10 and len({p['catalogue_id'] for p in linkedin})==10
for p in linkedin:
    receipt=p['publication']
    assert p['status']==receipt['status']=='PUBLISHED_NATIVE_READBACK'
    row=by_id[p['catalogue_id']]
    activity=receipt['url'].rstrip('/').split(':')[-1]
    assert activity.isdecimal()
    fields=dict(linkedin_post_url=receipt['url'],linkedin_native_activity_id=activity,
                linkedin_post_caption=p['caption'],linkedin_post_alt_text=p['alt_text'],
                linkedin_product_link=p['tracked_url'],linkedin_published_status='Published; native post readback and unique activity URL verified',
                linkedin_checked_utc=serial(receipt.get('verified_utc',receipt.get('published_utc'))),linkedin_media_sha256=p['sha256'])
    for h,v in fields.items():patch(h,row,v,'utc' if h.endswith('_utc') else 'text')
instagram=load(PACKET/'instagram-publication-receipts.json')
assert len(instagram)==5 and len({p['native_post_id'] for p in instagram})==5
for p in instagram:
    assert p['status']=='PUBLISHED_NATIVE_READBACK' and p['full_caption_readback'] and p['tag_saved_readback']
    row=by_id[p['catalogue_id']]
    assert not old.value(sheet,'ST'+str(row)), 'Do not overwrite existing publication history'
    values=dict(instagram_post_url=p['url'],instagram_native_post_id=p['native_post_id'],instagram_product_tag_sku=p['sku'],
                instagram_published_status='Published; full caption and saved exact Commerce variant title/price verified',
                instagram_checked_utc='UTC | '+p['verified_utc'],
                instagram_automation_status='Published through native Chrome UI with focused keyboard caption input. AppleScript runner is not live-validated.',
                instagram_tag_title_observed=p['tag_title'],instagram_tag_price_gbp_observed=(float(p['tag_price'].replace('£','')) if 'tag_price' in p else p['tag_price_gbp']))
    for h,v in values.items():patch(h,row,v,'money' if h.endswith('_price_gbp_observed') else 'text')
audit=load(PACKET/'pinterest-public-audit.json')
assert audit['summary']['products']==176 and audit['summary']['page_errors']==audit['summary']['image_errors']==0
assert audit['summary']['price_mismatches']==audit['summary']['stock_mismatches']==audit['summary']['images_size_unresolved']==0
by_pinterest={str(old.value(sheet,'XU'+str(r))):r for r in by_id.values() if old.value(sheet,'XU'+str(r))}
profile=load(PACKET/'pinterest-profile-receipt.json')
assert profile['status']=='SAVED_RELOADED_NATIVE_READBACK'
for p in audit['products']:
    row=by_pinterest[p['id']]
    img=p['image']
    fields=dict(pinterest_primary_width_px_observed=img['width'],pinterest_primary_height_px_observed=img['height'],
       pinterest_primary_image_size_check='Meets documented width >=1000 and height >=1500 pixels' if img['meets_pinterest_documented_1000x1500'] else 'Below documented width >=1000 or height >=1500 pixels; review genuine original/selected photograph. Not a native rejection diagnosis.',
       pinterest_title_match_check='Matches website product title' if p['exact_title_match'] else 'Feed adds Finish; update existing website title to catalogue wording. Current website: '+p['landing_product_title_without_site_suffix'],
       pinterest_audit_checked_utc=serial(audit['summary']['checked_utc']),pinterest_profile_website_observed=profile['website'],
       pinterest_merchant_checked_utc=serial(profile['verified_utc']),
       pinterest_merchant_status='Not approved: minimum product and website quality requirements; 0 approved products. No appeal submitted.',
       pinterest_daily_feed_status='Existing daily 07:00 London source remains disabled by merchant approval. Public feed reachable; all 176 page/image responses, GBP prices and stock checked.',
       pinterest_tag_verification='Ownership meta tag verified. No direct pintrk script found in public HTML; runtime/consent and product-event verification remains required.',
       google_manufacturer_product_status='8 November native check: no variants in account 5898308482; no genuine GTIN allocation found in current records/mailbox searches.',
       google_manufacturer_required_action='Obtain or locate Boldstone-owned GS1 allocation; verify licensee and per-variant assignment, then import. Turnover/possible existing membership requested; no paid subscription or invented GTIN.',
       gtin_allocation_source='No genuine allocation located in current master, searched local records/public results or targeted info@boldstone.co.uk GS1 searches on 8 November 2026. A licence under another email remains possible.')
    for h,v in fields.items():
        style='utc' if h.endswith('_utc') else 'integer' if h.endswith('_px_observed') else 'text'
        patch(h,row,v,style)
plan=dict(scope='Record ten published LinkedIn posts, five published and caption/tag-verified Instagram posts, saved Pinterest profile correction, 176-product public feed/page/image audit and unresolved genuine GTIN requirement. No product, price, policy, image-selection or live feed changes.',
          first_added_column=first,last_added_column=first+len(new_headers)-1,new_headers=new_headers,patches=patches,
          previews=[dict(name='instagram',range='ST7:SW11'),dict(name='linkedin',range=column(first)+'7:'+column(first+2)+'11'),dict(name='pinterest',range=column(headers['pinterest_primary_width_px_observed'])+'7:'+column(headers['pinterest_title_match_check'])+'11')],
          counts=dict(linkedin_published=10,instagram_published=5,pinterest_audited=176,pinterest_title_differences=62,pinterest_images_below_documented_dimensions=96,pinterest_appeals_used=0,gtins_assigned=0),
          prepared_utc=datetime.now(timezone.utc).isoformat())
(OUT/'plan.json').write_text(json.dumps(plan,indent=2,ensure_ascii=False)+'\n')
print(json.dumps(dict(patched_cells=len(patches),added_fields=len(new_headers),previous_revision=meta['rev'],scope=plan['scope'])))
