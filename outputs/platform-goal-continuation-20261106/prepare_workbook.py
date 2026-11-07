"""Plan a narrow source/catalogue update without changing native publication claims."""
from pathlib import Path
from datetime import datetime,timezone
from urllib.request import urlopen
from urllib.parse import quote
import hashlib,json,sys,re

ROOT=Path('/Users/tprice/Documents/boldstone');RUN=Path(__file__).parent
context_mode='--context' in sys.argv
OUT=RUN/('workbook-context' if context_mode else 'workbook');OUT.mkdir(exist_ok=True)
sys.path[:0]=[str(ROOT/'catalogue-review'),str(ROOT/'catalogue-review/scripts')]
from import_saatchi_snapshot import Xlsx,column,column_index
from delete_dropbox import connection
read=lambda p:json.loads(p.read_text());sha=lambda b:hashlib.sha256(b).hexdigest()
pointer=read(ROOT/'sculpture-catalogue/current-master.json');current=pointer['current_app_review_workbook']
body=Path(current['path']).read_bytes();assert sha(body)==current['sha256']
assert not (OUT/'dropbox-receipt.json').exists(),'Existing upload must be reconciled first'
(OUT/'source-pointer-before.json').write_text(json.dumps(pointer,indent=2)+'\n')
(OUT/'previous-catalogue.xlsx').write_bytes(body)
with connection(ROOT) as(db,_):
    meta=db.files_get_metadata(current['dropbox']['id'])
    assert meta.rev==current['dropbox']['rev'] and meta.content_hash==current['dropbox']['content_hash']
    previous={k:str(getattr(meta,k)) if k.endswith('modified') else getattr(meta,k) for k in ['id','path_display','rev','size','content_hash','server_modified','client_modified']}
(OUT/'previous-dropbox-metadata.json').write_text(json.dumps(previous,indent=2)+'\n')
with urlopen('http://127.0.0.1:8767/api/specifications',timeout=120) as r:app=json.load(r)
(OUT/'app-specifications.json').write_text(json.dumps(app,ensure_ascii=False,indent=2)+'\n')
products={p['id']:p for p in app['products']};assert len(products)==181
previous_app=read(ROOT/'outputs/furnitures-faire-instagram-20261106/followup/app-specifications.json')
for p in previous_app['products']:
    q=products[p['id']]
    for key in ['fields','listing_fields','costing','listing_decision']:assert p[key]==q[key],(p['id'],key)
    assert p['photos']['primary_listing']==q['photos']['primary_listing']
x=Xlsx(OUT/'previous-catalogue.xlsx');sheet='Wall Sculptures'
headers={x.value(sheet,a):re.sub(r'\d','',a) for a in x.cells[sheet] if re.fullmatch(r'[A-Z]+7',a)}
rows={x.value(sheet,f'AA{r}'):r for r in range(8,189)};assert rows.keys()==products.keys()
patches=[];added=[];now='UTC | '+datetime.now(timezone.utc).isoformat()
def put(sh,cell,value):
    before=x.value(sh,cell)
    if before!=value:patches.append(dict(sheet=sh,cell=cell,before=before,value=value))
def setfield(pid,key,value):
    if key not in headers:
        headers[key]=column(max(map(column_index,headers.values()))+1);added.append(key);put(sheet,headers[key]+'7',key)
    put(sheet,headers[key]+str(rows[pid]),value)
image_rows={(x.value('Images',f'C{r}'),x.value('Images',f'AD{r}')):r for r in x.rows('Images',8)}
image_urls={x.value('Images',f'AD{r}'):'https://www.dropbox.com/preview'+quote(x.value('Images',f'AE{r}'),safe='/') for r in x.rows('Images',8) if x.value('Images',f'AE{r}')}
changes=[];packets=[]
for mode in ['ammonite','moon-fish','lunar-phase-iv']:
    proof=read(RUN/(mode+'-photo-selection-verification.json'))
    assert proof['status'].startswith('PASS_') and proof['all_primaries_preserved'] and proof['all_costs_fields_decisions_preserved']
    receipts=read(RUN/(mode+'-photo-selection-receipts.json'))
    for receipt in receipts:
        assert receipt['status']=='SAVED'
        changes.append(receipt['response'])
    packets.extend(read(RUN/(mode+'-upload-packet.json')))
assert len(changes)==len(packets)==5
external_packets=read(RUN/'islington-upload-packet.json')
assert len(external_packets)==1 and external_packets[0]['photo']['app_library_selection_status'].startswith('External Dropbox archive')
packets.extend(external_packets)
if context_mode:
    contexts=read(RUN/'context-upload-packets.json');assert len(contexts)==6
    packets.extend(contexts)
changed_pids=set()
for c in changes:
    pid,aid=c['product_id'],c['item_id'];changed_pids.add(pid);data=c['data']
    assert aid in {im['id'] for im in products[pid]['photos']['listing']['images']}
    r=image_rows[(pid,aid)]
    for col,value in [('I','Yes'),('N',', '.join(data['uses'])),('O',data['decision']),('P',data.get('order',0)),('Y',data.get('alt','')),('Z',data.get('caption','')),('AB',data.get('notes',''))]:put('Images',col+str(r),value)
for pid in changed_pids:
    photos=products[pid]['photos'];listing=photos['listing']['images']
    put(sheet,'N'+str(rows[pid]),len(listing))
    setfield(pid,'saatchi_listing_image_urls','\n'.join(image_urls[p['id']] for p in listing))
    setfield(pid,'saatchi_selected_gallery_count',len({p['id'] for kind in ['listing','in_situ'] for p in photos[kind]['images']}))
    setfield(pid,'catalogue_photo_selection_checked_utc',now)
for p in packets:
    pid=p['catalogue_id'];photo=p['photo'];assert x.value(sheet,'AQ'+str(rows[pid]))==p['sku']
    assert not p['native_artwork_id'] and p['publication_status'] in ['PREPARED_NOT_UPLOADED','HELD_VARIANT_PHOTO_REVIEW','REVIEWED_CONTEXT_CANDIDATE_NATIVE_TEST_PENDING']
    original_url=image_urls.get(photo['image_id']) or 'https://www.dropbox.com/preview'+quote(photo['photo_path'],safe='/')
    status='Prepared only. Genuine original reviewed. Native duplicate check, image-format acceptance, packing and publication remain unverified.'
    if photo.get('app_library_selection_status'):status+=' External archive candidate, not selected in app.'
    if photo.get('requires_configuration_review'):status='Held for variant/photo review. Visible water outlet may conflict with the separate Relief offer. Do not publish until resolved. External archive candidate, not selected in app.'
    if p['publication_status']=='REVIEWED_CONTEXT_CANDIDATE_NATIVE_TEST_PENDING':status='Reviewed complete matching design and finish. Existing In situ choice retained. Native contextual-primary/format acceptance and duplicate check required before upload or publication. Not uploaded.'
    fields=dict(photo_id=photo['image_id'],original_url=original_url,width_px=photo['width'],height_px=photo['height'],description=p['description'],status=status,checked_utc='UTC | '+photo['checked_utc'])
    if context_mode:
        fields.update(app_use=photo.get('app_use') or photo.get('app_library_selection_status') or 'Additional Listing selection. Existing app primary retained.',original_file_format=photo['format'],original_sha256=photo['sha256'])
        if photo.get('native_upload_sha256'):
            fields.update(upload_file_format=photo['native_upload_format'],upload_sha256=photo['native_upload_sha256'],pixel_verification='Identical decoded pixels. Primary JPEG container extracted without crop, resizing, colour change or recompression.' if photo['format']=='MPO' else 'Unchanged single-image JPEG original. No pixel edits.')
    for key,value in fields.items():setfield(pid,'saatchi_art_upload_candidate_'+key,value)
ws=read(RUN/'wescover-current-public-verification.json');assert ws['status']=='PASS_ALL_176_PUBLIC_PRODUCTS'
for r in ws['records']:
    assert r['identity_matches'] and r['positive_available_offer'] and r['http']==200
    pid=next(pid for pid in rows if x.value(sheet,'AQ'+str(rows[pid]))==r['sku'])
    for key,value in dict(current_public_check='Public matching product with available USD offer',current_public_checked_utc='UTC | '+r['checked_utc'],current_public_check_scope='Native item ID, seller SKU, Boldstone brand and positive available offer only. Complete gallery, current copy, price alignment and checkout not verified.').items():setfield(pid,'wescover_'+key,value)
assert len({(p['sheet'],p['cell']) for p in patches})==len(patches)
first=min(column_index(headers[h]) for h in added)
sample=rows['BSI-992BA62AA818']
new_selections=sum(p['sheet']=='Images' and re.fullmatch(r'I\d+',p['cell']) is not None and p['value']=='Yes' for p in patches)
plan=dict(status='PREPARED',scope='Five genuine additional Listing photo selections and unuploaded Saatchi candidates, one additional archive candidate held because its water outlet may conflict with the Relief variant, and dated public Wescover identity/availability evidence for all 176 products. Existing primaries, specifications, costs, prices, native artwork IDs and publication status claims preserved.',patches=patches,headers=headers,added_headers=added,first_added_column=first,last_column=max(map(column_index,headers.values())),component_records=181,new_listing_selections=new_selections,saatchi_prepared_not_uploaded=5,saatchi_held_variant_photo_review=1,saatchi_context_candidates_native_test_pending=6 if context_mode else 0,saatchi_native_publications=0,wescover_public_matches=176,preview_header_range=headers['saatchi_art_upload_candidate_photo_id']+'7:'+headers['saatchi_art_upload_candidate_width_px']+'8',preview_row_range=headers['saatchi_art_upload_candidate_photo_id']+str(sample)+':'+headers['saatchi_art_upload_candidate_width_px']+str(sample),image_preview_range='I'+str(image_rows[('BSI-992BA62AA818','id:cnqzTNngPVsAAAAAAAsPiA')])+':P'+str(image_rows[('BSI-992BA62AA818','id:cnqzTNngPVsAAAAAAAsPiA')]),checked_utc=now)
if context_mode:
    sample=rows['BSI-1774B82C6518'];plan.update(scope='Add six visually reviewed existing In situ camera-original candidates for missing Saatchi products, preserving their app categories and all catalogue primaries. Record the app use separately for all twelve candidate/held rows. Earlier five Listing candidates, the held Islington outlet case, prices, costs, native IDs and actual publication status remain distinct and preserved.',preview_row_range=headers['saatchi_art_upload_candidate_photo_id']+str(sample)+':'+headers['saatchi_art_upload_candidate_width_px']+str(sample),preview_app_use_range=headers['saatchi_art_upload_candidate_app_use']+'7:'+headers['saatchi_art_upload_candidate_app_use']+'9')
(OUT/'plan.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in plan.items() if k not in ['patches','headers']},ensure_ascii=False))
print('patches',len(patches))
