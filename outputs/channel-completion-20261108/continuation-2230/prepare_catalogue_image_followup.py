"""Prepare exact master-cell patches for verified image and gallery evidence."""
from pathlib import Path
from datetime import datetime,timezone
import copy,hashlib,json,sys,urllib.request

ROOT=Path('/Users/tprice/Documents/boldstone');PACKET=Path(__file__).parent.parent
OUT=PACKET/'catalogue-image-followup';OUT.mkdir(exist_ok=True)
sys.path[:0]=[str(ROOT/'catalogue-review'),str(ROOT/'catalogue-review/scripts')]
from import_saatchi_snapshot import Xlsx,column
from delete_dropbox import connection
load=lambda p:json.loads(Path(p).read_text())
pointer=load(ROOT/'sculpture-catalogue/current-master.json')
source=Path(pointer['current_app_review_workbook']['path']);body=source.read_bytes()
assert hashlib.sha256(body).hexdigest()==pointer['current_app_review_workbook']['sha256']
(OUT/'previous-catalogue.xlsx').write_bytes(body)
(OUT/'source-pointer-before.json').write_text(json.dumps(pointer,indent=2)+'\n')
old=Xlsx(source);headers={old.value('Wall Sculptures',column(i)+'7'):i for i in range(1,889)}
assert len(headers)==888
per=load(PACKET/'continuation-2230/image-followup-per-product.json')
evidence=load(PACKET/'platform-task-evidence.json')
gallery=load(PACKET/'brandboom-gallery-audit/verification.json')
google=load(PACKET/'continuation-2230/google-rendition-after-verification.json')
ms=load(PACKET/'continuation-2230/microsoft-rendition-refresh-intent.json')
mf=load(PACKET/'continuation-2230/manufacturer-status-20261109.json')
pin=load(PACKET/'continuation-2230/pinterest-merchant-status-20261109.json')
assert gallery['products']==176 and gallery['selected_photo_placements']==1437
assert google['status']=='PASS_NATIVE_COMBINED_OFFER_READBACK' and google['native_approval_counts']['approved']==325
new_headers=['brandboom_gallery_native_media_ids','brandboom_gallery_native_primary_media_id',
 'brandboom_gallery_native_image_count','brandboom_gallery_verified_utc','brandboom_gallery_native_repair_status',
 'brandboom_gallery_removed_media_ids','brandboom_gallery_upright_native_media_id','brandboom_gallery_evidence_sha256',
 'google_merchant_primary_image_link','google_merchant_additional_image_links','google_merchant_image_renditions_verified_utc',
 'microsoft_merchant_oversized_image_urls_corrected','microsoft_merchant_native_issue_messages',
 'microsoft_merchant_issue_observed_utc','microsoft_merchant_refresh_receipt_utc',
 'microsoft_merchant_refreshed_source_status','microsoft_merchant_image_compatibility_status']
assert not set(new_headers)&set(headers)
for i,header in enumerate(new_headers,889):headers[header]=i
patches=[]
def patch(cell,value,field,style='text'):
    before=old.value('Wall Sculptures',cell)
    if before==value or before is None and value in ['',None]:return
    patches.append({'sheet':'Wall Sculptures','cell':cell,'before':before,'value':value,'style':style,'field':field})
def put(row,header,value,style='text'):
    original=None
    if style!='header' and header.endswith('_utc') and isinstance(value,str):
        original=value
        moment=datetime.fromisoformat(value.replace('Z','+00:00')).astimezone(timezone.utc)
        value=(moment-datetime(1899,12,30,tzinfo=timezone.utc)).total_seconds()/86400
        style='utc'
    previous_len=len(patches)
    patch(column(headers[header])+str(row),value,header,style)
    if original and len(patches)>previous_len:patches[-1]['original_utc_iso']=original
for header in new_headers:put(7,header,header,'header')
patch('A4','Channel checks updated 9 November 2026. Product facts, costs and prices are preserved. New gallery and feed fields contain dated readbacks; older sheets retain their dated source snapshots.','catalogue_lineage')
seen=set()
for row in range(8,189):
    pid=old.value('Wall Sculptures','AA'+str(row));assert pid in evidence['products']
    entries=evidence['products'][pid]['platforms']
    summary='; '.join(code+': '+entry['state'] for code,entry in entries.items())
    put(row,'platform_tasks_summary',summary)
    put(row,'platform_tasks_json',json.dumps(entries,ensure_ascii=False,separators=(',',':')))
    put(row,'platform_tasks_checked_utc',evidence['checked_at'])
    if pid not in per:
        put(row,'brandboom_gallery_native_repair_status','Not in the current 176-product publication scope')
        put(row,'microsoft_merchant_refreshed_source_status','Not targeted')
        continue
    seen.add(pid);product=per[pid];inventory=product['brandboom_inventory'];repair=product['brandboom_repair'];offer=product['google_offer']
    source_record=next(record for record in load(PACKET/'brandboom-restore-plan.json')['records'] if record['catalogue_id']==pid)
    put(row,'brandboom_source_image_ids',','.join(source_record['image_ids']))
    put(row,'brandboom_source_image_count',inventory['image_count'],'integer')
    put(row,'brandboom_image_verification','Saved native gallery checked against every current Listing/In situ selection; selected primary first. Rendered comparison and exact repaired-ID readbacks passed. Public Marketplace visibility is separate.')
    put(row,'brandboom_restoration_status','176 existing products restored; all 176 galleries verified. Fourteen excess-photo cases corrected, including three upright same-photo replacements. Owner-only 50-product preview remains separate from public Marketplace publication.')
    put(row,'brandboom_gallery_native_media_ids',','.join(image['native_media_id'] for image in inventory['images']))
    put(row,'brandboom_gallery_native_primary_media_id',inventory['images'][0]['native_media_id'])
    put(row,'brandboom_gallery_native_image_count',inventory['image_count'],'integer')
    put(row,'brandboom_gallery_verified_utc',inventory['checked_at'])
    put(row,'brandboom_gallery_evidence_sha256',hashlib.sha256((PACKET/'brandboom-gallery-audit'/(product['sku']+'.json')).read_bytes()).hexdigest())
    if repair:
        removed=repair.get('removed_association_ids',[repair.get('removed_association_media_id')])
        put(row,'brandboom_gallery_removed_media_ids',','.join(filter(None,removed)))
        put(row,'brandboom_gallery_upright_native_media_id',repair.get('new_upright_media_id',''))
        status=('Both sideways copies replaced by one upright rendition of the same selected photo; old media retained in native Media Bin.' if repair.get('new_upright_media_id') else 'One reviewed excess duplicate association moved to recoverable native Media Bin.')
        put(row,'brandboom_gallery_native_repair_status',status+' Saved and independently reopened; exact IDs, count, primary, title and wholesale price verified.')
    else:put(row,'brandboom_gallery_native_repair_status','Gallery matched current selections; no change required in this follow-up.')
    put(row,'google_merchant_checked_utc',google['checked_at'])
    put(row,'google_merchant_approval_status','Approved at the dated native check; account totals 325 approved, 0 limited/not approved/under review.')
    put(row,'google_merchant_image_sync_status','Current combined offer independently matches all 11 supplement fields. Oversized image URLs use qualified renditions of the same selected photos; existing UUID, prices, paths and image order retained.')
    put(row,'google_merchant_primary_image_link',offer['image_link'])
    put(row,'google_merchant_additional_image_links',offer['additional_image_link'])
    put(row,'google_merchant_image_renditions_verified_utc',google['checked_at'])
    put(row,'microsoft_merchant_import_status','One import requested from the independently verified Google source after the 217 same-photo size corrections. Native acknowledgement: Import scheduled. Processing and publication not yet verified.')
    put(row,'microsoft_merchant_editorial_status',product['microsoft_status'])
    put(row,'microsoft_merchant_oversized_image_urls_corrected',product['oversized_feed_image_count'],'integer')
    put(row,'microsoft_merchant_native_issue_messages','\n'.join(product['microsoft_raw_issue_messages']))
    put(row,'microsoft_merchant_issue_observed_utc','2026-11-08T23:44:00Z')
    put(row,'microsoft_merchant_refresh_receipt_utc',ms['request_action_interval_utc']['latest'])
    put(row,'microsoft_merchant_refreshed_source_status','Google native combined export verified. Microsoft acknowledged reimport; await its new completed-feed timestamp and per-offer result.')
    put(row,'microsoft_merchant_image_compatibility_status','All current Google feed URLs qualified below the 3.9 MB Microsoft cap; 217 changed renditions are below 1.5 MB. No primary photo choice or website image changed. Native Microsoft processing is pending.')
assert len(seen)==176 and len(patches)==len({patch['cell'] for patch in patches})
with urllib.request.urlopen('http://127.0.0.1:8767/api/specifications',timeout=120) as response:app=json.load(response)
(OUT/'app-specifications.json').write_text(json.dumps(app,ensure_ascii=False)+'\n')
with connection(ROOT) as (db,_):
    metadata=db.files_get_metadata('id:cnqzTNngPVsAAAAAAA7JEQ')
    assert metadata.rev==pointer['current_app_review_workbook']['dropbox']['rev']
    previous={key:str(getattr(metadata,key)) if key.endswith('modified') else getattr(metadata,key) for key in ['id','path_display','rev','size','content_hash','server_modified','client_modified']}
(OUT/'previous-dropbox-metadata.json').write_text(json.dumps(previous,indent=2)+'\n')
created=datetime.now(timezone.utc).isoformat()
plan={'created_utc':created,'source_sha256':hashlib.sha256(body).hexdigest(),
 'scope':'Dated full Brandboom gallery readbacks and 14 recoverable gallery repairs; same-photo feed renditions fitting Microsoft size limits, independently read back in Google; current pending merchant gates. Product facts, core costs, zero labour, prices, stock, GTINs, app photo choices and website images preserved.',
 'new_headers':new_headers,'first_added_column':889,'last_added_column':888+len(new_headers),'patches':patches,
 'counts':{'component_records':181,'publication_records':176,'new_columns':len(new_headers),'patched_cells':len(patches),
   'brandboom_galleries_verified':176,'brandboom_selected_photo_placements':1437,'brandboom_excess_cases_repaired':14,'brandboom_sideways_photos_replaced':3,
   'google_same_photo_feed_urls_reduced':217,'google_native_field_comparisons':1936,'google_approved_products':325,
   'microsoft_refresh_acknowledged_processing_unverified':True,'pinterest_merchant_approved':False,'pinterest_appeals_used':0,'gtins_assigned':0},
 'previews':[{'name':'gallery-evidence','range':column(889)+'7:'+column(892)+'11'},
             {'name':'gallery-repair-notes','range':column(893)+'7:'+column(896)+'11'},
             {'name':'merchant-image-evidence','range':column(897)+'7:'+column(900)+'11'},
             {'name':'microsoft-review-status','range':column(901)+'7:'+column(905)+'11'}]}
(OUT/'plan.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'source_revision':previous['rev'],'patches':len(patches),'added_fields':len(new_headers),'components':181,'publication_products':176}))
