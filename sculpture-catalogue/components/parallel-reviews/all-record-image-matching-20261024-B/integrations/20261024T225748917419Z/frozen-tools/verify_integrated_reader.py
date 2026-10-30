"""Independent readback of the generated image readers and local platform join."""
from collections import Counter
from datetime import datetime,timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote,urlsplit,parse_qs
import hashlib,json,sqlite3

H=Path(__file__).resolve().parent
ROOT=H.parents[3]
read=lambda p:json.loads(Path(p).read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
run=Path(read(H/'current-integration.json')['run'])
directory=ROOT/'reports/dropbox-wall-complete-role-review-20261024T214349Z'
db=sqlite3.connect('file:'+str(run/'complete-image-platform-register.sqlite')+'?mode=ro',uri=True)
checks=Counter()
def check(condition,category,detail=None):
    assert condition,(category,detail)
    checks[category]+=1
check(db.execute('PRAGMA integrity_check').fetchone()[0]=='ok','sqlite_integrity')
products={pid:json.loads(blob) for pid,blob in db.execute('SELECT product_id,record_json FROM products')}
images={fid:json.loads(blob) for fid,blob in db.execute('SELECT file_id,record_json FROM images')}
native={r['file_id']:r for r in read(directory/'all-current-6360-image-folder-links.json')}
check(len(products)==188,'active_product_count')
seed=Path(read(H/'current-work.json')['run'])
seed_db=sqlite3.connect('file:'+str(seed/'image-register.sqlite')+'?mode=ro',uri=True)
seed_products={pid:json.loads(blob) for pid,blob in seed_db.execute('SELECT product_id,record_json FROM products')}
for pid,p in products.items():check(p==seed_products[pid],'all_original_option_fields_preserved',pid)
seed_db.close()
check(len(native)==6360,'current_native_count')
for fid,n in native.items():
    im=images[fid]
    for field in ['folder_id','image_url','folder_url']:
        check(im[field]==n[field],'native_field_equality',(fid,field))
    check(im['inventory_status']=='CURRENT_NATIVE_FILE_AND_ACTUAL_PARENT_VERIFIED','native_status',fid)
    folder=unquote(urlsplit(n['folder_url']).path)
    check(folder=='/home'+n['folder_path'],'actual_parent_url',fid)
    image_parts=urlsplit(n['image_url'])
    check(unquote(image_parts.path)==folder and parse_qs(image_parts.query).get('preview')==[n['name']],'image_parent_and_name',fid)
role_rows={fid:json.loads(blob) for fid,blob in db.execute('SELECT file_id,record_json FROM per_image_visual_roles')}
check(set(role_rows)<=set(native),'roles_within_current_inventory')
for fid,row in role_rows.items():
    check(row['folder_id']==native[fid]['folder_id'],'role_parent',fid)
    check(row['visual_role'] in {'individual','detail','rear','installation','group_context','uncertain'},'allowed_role',fid)

gallery=read(run/'source-gallery-review.json')
check(len(gallery)==445 and len({r['gallery_entry_id'] for r in gallery})==445,'complete_squarespace_gallery')
check(all(r['role_status']=='EXPLICIT_VISUAL_ROLE_REVIEW' for r in gallery),'all_squarespace_roles')
check(sum(bool(r['supported_photo_file_ids']) for r in gallery)==416,'qualified_squarespace_correspondences')
check(sum(bool(r.get('bounded_crop_comparison_review')) for r in gallery)==25,'bounded_comparisons_retained')
check(sum(bool(r.get('multiple_current_version_review')) for r in gallery)==15,'multiple_version_reviews_retained')
matches=read(run/'source-photo-correspondences.json')
gids={r['gallery_entry_id'] for r in gallery}
for row in matches:
    check(row['gallery_entry_id'] in gids,'photo_source_membership')
    check(row['source_to_option_assignment_automatically_created'] is False,'no_automatic_variant_assignment')
    im=images[row['file_id']]
    check(row['image_url']==im['image_url'] and row['folder_url']==im['folder_url'],'photo_navigation')
shop=read(run/'local-shopify-gallery-review.json')['records']
check(len(shop)==117 and len({r['handle'] for r in shop})==38,'complete_local_shopify_wall_gallery')
check(sum(bool(r['native_photo_correspondence']) for r in shop)==114,'qualified_shopify_correspondences')
check({r['review_id'] for r in shop if not r['native_photo_correspondence']}=={'S016','S021','S022'},'three_scene_only_shopify_frames')
for r in shop:check(r['variant_specific_assignment_certified'] is False,'shopify_variant_qualification')
check(db.execute('SELECT count(*) FROM source_product_links').fetchone()[0]==260,'retained_source_option_edges')
check(db.execute('SELECT count(*) FROM local_shopify_products').fetchone()[0]==136,'all_local_shopify_products')
check(db.execute('SELECT count(*) FROM local_shopify_variants').fetchone()[0]==160,'all_local_shopify_variant_rows')
check(db.execute('SELECT count(*) FROM local_shopify_media').fetchone()[0]==416,'all_local_shopify_media_rows')

product_index=read(run/'product-reader-index.json')
family_index=read(run/'family-image-reader-index.json')
family_navigation=read(run/'product-family-navigation.json')
check(set(family_navigation)==set(products),'all_product_family_navigation')
source_index=read(run/'source-gallery-reader-index.json')
ledger=read(run/'product-image-association-review.json')
unassigned=read(run/'current-images-without-option-scope.json')
check({r['product_id'] for r in product_index}==set(products),'all_product_reader_pages')
check(len(source_index)==81 and sum(r['squarespace_images'] for r in source_index)==445 and sum(r['shopify_images'] for r in source_index)==117,'all_source_reader_pages')
family_ids=[fid for r in family_index for fid in r['current_file_ids']]
check(len(family_index)==60 and len(family_ids)==6360 and set(family_ids)==set(native),'all_native_family_reader_pages')
used=set()
for pid,rows in ledger.items():
    check(pid in products,'product_ledger_owner')
    check(len(rows)==len({r['file_id'] for r in rows}),'unique_option_file_rows',pid)
    for row in rows:
        used.add(row['file_id'])
        if row['review_disposition']=='historical_unavailable':
            check(not row['image_url'] and not row['folder_url'],'historical_links_not_current')
        else:
            check(row['image_url'] and row['folder_url'],'current_option_links_present')
        check(row['association_qualification'],'association_qualification_present')
check((used & set(native)) | {r['file_id'] for r in unassigned}==set(native),'no_current_image_lost')
check(not ((used & set(native)) & {r['file_id'] for r in unassigned}),'unassigned_partition')

class Links(HTMLParser):
    def __init__(self):super().__init__();self.links=[];self.images=[];self.ids=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if 'id' in a:self.ids.append(a['id'])
        if tag=='a' and a.get('href'):self.links.append(a['href'])
        if tag=='img' and a.get('src'):self.images.append(a['src'])

html_files=sorted(run.rglob('*.html'))
parsed={}
valid_native_urls={im[k] for im in images.values() for k in ['image_url','folder_url'] if im.get(k)}
for page in html_files:
    p=Links();p.feed(page.read_text());parsed[page.resolve()]=p
    check(len(p.ids)==len(set(p.ids)),'unique_html_anchors',str(page))
for page,p in parsed.items():
    for url in p.links+p.images:
        parts=urlsplit(url)
        if parts.scheme in ('http','https'):
            if parts.netloc.endswith('dropbox.com'):check(url in valid_native_urls,'dropbox_html_link_current',url)
            continue
        if parts.scheme and parts.scheme!='file':continue
        target=Path(unquote(parts.path)) if parts.path.startswith('/') else page.parent/unquote(parts.path)
        if not parts.path:target=page
        target=target.resolve()
        check(target.exists(),'local_html_target_exists',(str(page),url))
        if parts.fragment and target in parsed:check(unquote(parts.fragment) in parsed[target].ids,'local_html_anchor_exists',(str(page),url))

pointer=ROOT/'sculpture-catalogue/current-master.json'
baseline=read(run/'summary.json')['baseline_pointer_sha256']
result={'status':'PASS','checked_utc':datetime.now(timezone.utc).isoformat(),'checks_passed':sum(checks.values()),'check_categories':dict(checks),'html_pages':len(html_files),'current_native_files':6360,'native_roles_integrated':len(role_rows),'source_gallery_reviewed':445,'local_shopify_wall_gallery_reviewed':117,'products':188,'family_libraries':60,'unassigned_to_exact_option_scope':len(unassigned),'every_current_file_retained':True,'current_pointer_sha256':sha(pointer),'baseline_pointer_sha256':baseline,'canonical_pointer_matches_start_baseline':sha(pointer)==baseline,'new_exact_variant_assignments':0,'no_platform_or_native_writes':True,'input_hashes':{str(run/f):sha(run/f) for f in ['summary.json','complete-image-platform-register.sqlite','product-reader-validation.json','source-gallery-review.json','source-photo-correspondences.json','family-image-reader-index.json','product-image-association-review.json']},'html_sha256':{str(p):sha(p) for p in html_files}}
(run/'integrated-reader-independent-readback.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k not in ['input_hashes','html_sha256']},indent=2))
