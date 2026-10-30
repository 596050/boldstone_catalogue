"""Build a local review reader without promoting folder candidates to approvals."""
from collections import Counter,defaultdict
import hashlib,html,json,sqlite3
from pathlib import Path

H=Path(__file__).resolve().parent
read=lambda p:json.loads(Path(p).read_text())
write=lambda p,v:Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
e=lambda v:html.escape(str(v or ''),quote=True)
run=Path(read(H/'current-integration.json')['run'])
seed=Path(read(H/'current-work.json')['run'])
db=sqlite3.connect(run/'complete-image-platform-register.sqlite')
products={pid:json.loads(blob) for pid,blob in db.execute('SELECT product_id,record_json FROM products')}
images={fid:json.loads(blob) for fid,blob in db.execute('SELECT file_id,record_json FROM images')}
lists=read(run/'per-product-image-lists.json')
for rows in lists.values():
    for row in rows:
        images.setdefault(row['file_id'],{'file_id':row['file_id'],'name':row.get('name'),
            'inventory_status':'REFERENCE_NOT_IN_CURRENT_ASSET_MAP','image_url':None,'folder_url':None})
sources=read(H.parents[3]/'reports/dropbox-wall-complete-role-review-20261024T214349Z/current-6360-visual-source-evidence.json')
previews={x['file_id']:x['source_image_path'] for x in sources}
current=[x for x in images.values() if x['inventory_status']=='CURRENT_NATIVE_FILE_AND_ACTUAL_PARENT_VERIFIED']
family_images=defaultdict(list)
for im in current:family_images[im['family']].append(im)
family_pages={family:hashlib.sha256(family.encode()).hexdigest()[:12]+'.html' for family in family_images}
folder_families=defaultdict(set)
for im in current:folder_families[im['folder_id']].add(im['family'])
product_family_scope={}
for pid,p in products.items():
    anchored=folder_families.get(p.get('folder_id'),set())
    if len(anchored)==1:
        product_family_scope[pid]={'family':next(iter(anchored)),'basis':'CURRENT_NATIVE_PARENT_FOLDER_ID','folder_id':p['folder_id']}
    elif p.get('family') in family_pages:
        product_family_scope[pid]={'family':p['family'],'basis':'EXISTING_CATALOGUE_FAMILY_LABEL'}
write(run/'product-family-navigation.json',product_family_scope)
platform={ref:json.loads(blob) for ref,blob in db.execute('SELECT offer_ref,record_json FROM local_source_offers')}
gallery_by_offer=defaultdict(list)
for row in read(run/'source-gallery-review.json'):gallery_by_offer[row['offer_ref']].append(row)
photo_evidence=defaultdict(list)
for row in read(run/'source-photo-correspondences.json'):photo_evidence[row['gallery_entry_id']].append(row)
shopify_by_handle=defaultdict(list)
for row in read(run/'local-shopify-gallery-review.json')['records']:shopify_by_handle[row['handle']].append(row)
product_links=defaultdict(list)
for ref,pid,relationship in db.execute('SELECT offer_ref,product_id,relationship FROM source_product_links'):
    product_links[pid].append((ref,relationship))
folder_anchors=defaultdict(list)
for pid,p in products.items():
    if p.get('folder_id'):folder_anchors[p['folder_id']].append(pid)

css='body{font:16px system-ui;max-width:1400px;margin:30px auto;padding:0 18px;line-height:1.5;color:#17251f}a{color:#1c6354}table{border-collapse:collapse;width:100%}td,th{padding:9px;border-bottom:1px solid #ddd;text-align:left}input{padding:12px;width:min(700px,90%);font:inherit}.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:18px}article{border:1px solid #ccd4cf;border-radius:8px;padding:12px;overflow-wrap:anywhere}img{width:100%;height:245px;object-fit:contain;background:#f2f3ef}.tag{display:inline-block;background:#edf1ed;padding:3px 8px;border-radius:5px}small{color:#54645a}details{margin:20px 0}summary{cursor:pointer;font-weight:600}h1{font-size:30px}h2{margin-top:34px}.notice{background:#f4f0e4;padding:12px}button,select{font:inherit;padding:7px}'
def header(title):return '<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+e(title)+'</title><style>'+css+'</style>'
def link(url,label):return '<a href="'+e(url)+'">'+e(label)+'</a>' if url else e(label)
def source_title(source):return source.get('source_title') or source.get('product',{}).get('title','')
def source_shopify_handle(source):
    if source.get('shopify_local_product'):return source['shopify_local_product'].get('handle')
    return source.get('product',{}).get('handle')
def native_links(fid):
    im=images.get(fid,{})
    return link(im.get('image_url'),im.get('name') or fid)+' · '+link(im.get('folder_url'),'Containing folder')
def family_card(im):
    fid=im['file_id'];ev=im.get('visual_role_evidence') or {};role=im.get('visual_role') or 'role review not yet integrated'
    card='<article id="'+e(fid)+'"><img loading="lazy" src="'+e(previews[fid])+'" alt="'+e(im['name'])+'"><p><span class="tag">'+e(role)+'</span></p><p>'+native_links(fid)+'</p>'
    if ev.get('review_note'):card+='<p>'+e(ev['review_note'])+'</p>'
    if ev.get('uncertainty_flags'):card+='<small>'+e('; '.join(ev['uncertainty_flags']))+'</small>'
    return card+'</article>'
def disposition(pid,row):
    statuses=set(row['association_statuses']);im=images[row['file_id']];p=products[pid]
    if not row['native_status'].startswith('CURRENT_NATIVE_FILE_AND_ACTUAL_PARENT_VERIFIED'):return 'historical_unavailable','Historical reference: no current verified image link'
    if 'CURRENT_ACCEPTED_REFERENCE' in statuses:return 'selected','Existing selected primary reference; its recorded qualifications still apply'
    if 'CURRENT_QUALIFIED_CONTEXT_REFERENCE' in statuses:return 'selected','Existing selected context reference'
    other=folder_anchors.get(im.get('folder_id'),[])
    if other and pid not in other:
        return 'related_scope','Folder anchors another product option; retain as related design/context evidence, not an exact finish or size assignment'
    if 'RETAINED_SOURCE_SCOPE_SUPPORT' in statuses:return 'retained_scope','Existing source-scope example; image role and current finish applicability remain separately qualified'
    if im.get('visual_role_evidence'):
        return 'reviewed_folder','Current folder association with an explicit image-role review; no new identity or finish approval inferred'
    return 'awaiting_role','Current folder candidate; per-image visual-role review not yet integrated'

gallery_out=run/'source-galleries';gallery_out.mkdir(exist_ok=True)
source_pages=[]
for ref,source in platform.items():
    title=ref+' — '+source_title(source);sq_rows=gallery_by_offer[ref]
    handle=source_shopify_handle(source);sh_rows=shopify_by_handle.get(handle,[])
    page=header(title)+'<p>'+link('../product-images.html','Products')+' · '+link('../source-galleries.html','All source galleries')+'</p><h1>'+e(title)+'</h1>'
    page+='<p class="notice">Every source-gallery image is retained. A corresponding Dropbox photograph does not assign that photograph to every finish or component in the listing. Crop, framing, exposure and cross-finish reuse qualifications remain part of the evidence. These records use the local exports.</p>'
    if source.get('squarespace_native_tuple'):page+='<p>Squarespace product / variant / SKU: '+e(json.dumps(source['squarespace_native_tuple'],ensure_ascii=False))+'</p>'
    if handle:page+='<p>Local Shopify handle: '+e(handle)+'. Numeric product and variant IDs and explicit variant images are not included in this export.</p>'
    if sq_rows:
        page+='<h2>Squarespace gallery ('+str(len(sq_rows))+')</h2><div class="grid">'
        for row in sorted(sq_rows,key=lambda x:x['gallery_order']):
            page+='<article id="sq-'+str(row['gallery_order'])+'"><img loading="lazy" src="'+e(row['selected_rendition']['path'])+'" alt="'+e(title+' gallery '+str(row['gallery_order']))+'"><p><span class="tag">'+e(row['visual_role'])+'</span></p><p>'+link(row['source_url'],'Source image '+str(row['gallery_order']))+'</p>'
            matches=photo_evidence[row['gallery_entry_id']]
            fids=sorted({m['file_id'] for m in matches})
            if fids:page+='<p>Corresponding Dropbox photographs / qualified renditions:</p>'+''.join('<p>'+native_links(fid)+'</p>' for fid in fids)
            else:page+='<p>Exact current photograph correspondence remains unresolved. The source image and its role are preserved.</p>'
            versions=row.get('multiple_current_version_review')
            if versions:page+='<p>'+e(versions['note'])+' These stored versions do not establish additional products.</p>'
            ev=row.get('current_role_evidence',{})
            note=ev.get('notes') or ev.get('note') or ev.get('review_note')
            if note and (not fids or ev.get('matched_candidate_file_id') in fids):page+='<p>'+e(note)+'</p>'
            if any('CROP_FRAMING_OR_CONTRAST' in m['status'] for m in matches):page+='<p>The correspondence includes crop, framing or contrast differences; those qualifications remain attached to the image.</p>'
            bounded=row.get('bounded_crop_comparison_review')
            if bounded:page+='<p>'+e(bounded['note'])+'</p>'
            page+='<details><summary>Matching evidence and qualifications</summary><pre style="white-space:pre-wrap">'+e(json.dumps({'current_role_evidence':ev,'photo_evidence':matches,'followup_evidence':row.get('followup_evidence',[]),'bounded_crop_comparison_review':bounded,'local_shopify_gallery_evidence':row.get('local_shopify_gallery_evidence',[])},ensure_ascii=False,indent=2))+'</pre></details></article>'
        page+='</div>'
    if sh_rows:
        page+='<h2>Local Shopify gallery ('+str(len(sh_rows))+')</h2><div class="grid">'
        for row in sorted(sh_rows,key=lambda x:x['gallery_order']):
            page+='<article id="'+e(row['review_id'])+'"><img loading="lazy" src="'+e(row['source_download']['path'])+'" alt="'+e(row['title'])+'"><p><span class="tag">'+e(row['source_visual_role'])+'</span></p><p>'+link(row['exported_gallery_row']['image_src'],'Shopify source image '+str(row['gallery_order']))+'</p><p>'+e(row['source_role_and_uncertainty_note'])+'</p>'
            candidate=row.get('native_photo_correspondence')
            if candidate:page+='<p>'+native_links(candidate['file_id'])+'</p>'
            elif row.get('native_scene_or_design_candidate'):page+='<p>Scene/design candidate only; exact photograph unresolved:</p><p>'+native_links(row['native_scene_or_design_candidate']['file_id'])+'</p>'
            page+='<details><summary>Proof grade and source row</summary><pre style="white-space:pre-wrap">'+e(json.dumps({'disposition':row['native_correspondence_disposition'],'source_row':row['exported_gallery_row']['source_row'],'variant_specific_assignment_certified':False},ensure_ascii=False,indent=2))+'</pre></details></article>'
        page+='</div>'
    (gallery_out/(ref+'.html')).write_text(page)
    source_pages.append({'offer_ref':ref,'title':source_title(source),'squarespace_images':len(sq_rows),'shopify_images':len(sh_rows),'shopify_handle':handle,'page':'source-galleries/'+ref+'.html'})
page=header('Complete source galleries')+'<h1>Complete source galleries</h1><p>'+link('product-images.html','Product image lists')+'</p><p>445 Squarespace images and 117 local Shopify images are preserved with visual roles, corresponding Dropbox images and containing-folder links.</p><table><tr><th>Source listing</th><th>Squarespace images</th><th>Local Shopify images</th></tr>'
for row in source_pages:page+='<tr><td>'+link(row['page'],row['offer_ref']+' '+row['title'])+'</td><td>'+str(row['squarespace_images'])+'</td><td>'+str(row['shopify_images'])+'</td></tr>'
(run/'source-galleries.html').write_text(page+'</table>');write(run/'source-gallery-reader-index.json',source_pages)
assert len(source_pages)==81 and sum(r['squarespace_images'] for r in source_pages)==445
assert {r['shopify_handle'] for r in source_pages if r['shopify_handle']}==set(shopify_by_handle)
family_out=run/'families';family_out.mkdir(exist_ok=True)
family_index=[]
for family,ims in sorted(family_images.items()):
    options=[{'product_id':pid,'name':p['name'],'navigation_basis':product_family_scope[pid]} for pid,p in products.items() if product_family_scope.get(pid,{}).get('family')==family]
    page=header(family+' image library')+'<p>'+link('../product-images.html','Product image lists')+' · '+link('../family-images.html','All family libraries')+'</p><h1>'+e(family)+' image library</h1><p class="notice">All current photographs filed in this Dropbox family are shown here. This is a family browsing link, not a claim that every picture depicts each product, finish or size. Group photographs remain context; processed and uncertain references retain their qualifications.</p>'
    if options:page+='<p>Related catalogue options: '+', '.join(link('../products/'+p['product_id']+'.html',p['name']) for p in options)+'.</p>'
    page+='<p>'+str(len(ims))+' current images, with verified image and containing-folder links.</p><div class="grid">'+''.join(family_card(im) for im in sorted(ims,key=lambda x:(x['folder_url'],x['name'])))+'</div>'
    (family_out/family_pages[family]).write_text(page)
    family_index.append({'family':family,'page':'families/'+family_pages[family],'image_count':len(ims),'current_file_ids':[im['file_id'] for im in ims],'related_catalogue_options':options,'relationship':'CURRENT_DROPBOX_FAMILY_SCOPE_NOT_EXACT_VARIANT_ASSIGNMENT'})
page=header('All current family images')+'<h1>All current family images</h1><p>'+link('product-images.html','Product image lists')+' · '+link('source-galleries.html','Source galleries')+'</p><p>Every one of the 6,360 current wall-sculpture images is retained in these family libraries. Family membership does not certify an individual product or finish.</p><table><tr><th>Family</th><th>Images</th><th>Catalogue options in this family</th></tr>'
for row in family_index:page+='<tr><td>'+link(row['page'],row['family'])+'</td><td>'+str(row['image_count'])+'</td><td>'+str(len(row['related_catalogue_options']))+'</td></tr>'
(run/'family-images.html').write_text(page+'</table>');write(run/'family-image-reader-index.json',family_index)
assert sum(r['image_count'] for r in family_index)==6360
out=run/'products';out.mkdir(exist_ok=True)
inventory=[];ledger={};counts=Counter();used=set()
for pid,p in products.items():
    rows=[];groups=defaultdict(list)
    for raw in lists.get(pid,[]):
        row=dict(raw);fid=row['file_id'];im=images[fid];used.add(fid)
        category,note=disposition(pid,row);row['review_disposition']=category;row['association_qualification']=note
        row['current_role_evidence']=im.get('visual_role_evidence')
        row['other_product_folder_anchors']=[{'product_id':x,'name':products[x]['name']} for x in folder_anchors.get(im.get('folder_id'),[]) if x!=pid]
        rows.append(row);groups[category].append(row);counts[category]+=1
    ledger[pid]=rows
    title=p['name'];page=header(title)+'<p>'+link('../product-images.html','All products')+'</p><h1>'+e(title)+'</h1><p><small>'+e(pid)+' · '+e(p.get('family'))+'</small></p>'
    page+='<p class="notice">This reader preserves existing catalogue decisions. Folder membership, a matching source photograph and an exact sale variant are separate relationships. Group photographs remain context. Related-size and related-finish images are labelled below.</p>'
    if p.get('source_scope_notes'):page+='<details><summary>Existing product qualifications</summary><p>'+e(p['source_scope_notes'])+'</p></details>'
    page+='<p>'+str(len(rows))+' distinct image references retained for this option. Current navigation uses verified native file IDs and actual containing folders.</p>'
    if pid in product_family_scope:
        family=product_family_scope[pid]['family']
        page+='<p>'+link('../families/'+family_pages[family],'Browse all '+family+' family images')+' — includes other components, finishes and group photographs, with their qualifications.</p>'
    if product_links[pid]:
        page+='<details><summary>Local Squarespace / Shopify records</summary><table><tr><th>Source</th><th>Native Squarespace tuple</th><th>Local Shopify record</th></tr>'
        for ref,relationship in product_links[pid]:
            s=platform[ref];native=s.get('squarespace_native_tuple',{});shop=s.get('shopify_local_variant') or {};handle=source_shopify_handle(s)
            page+='<tr><td>'+link('../source-galleries/'+ref+'.html',ref+' '+source_title(s))+'<br><small>'+e(relationship)+'</small></td><td>'+e(json.dumps(native,ensure_ascii=False) if native else 'Shopify-only draft; no paired Squarespace record')+'</td><td>'+e(shop.get('variant_key') or handle or 'No exact local shared-SKU pair')+'</td></tr>'
        page+='</table><p>'+link(H.parents[3]/'reports/local-platform-crosswalk-corrected-20261024-root/index.html','Complete local platform matching report')+'</p></details>'
        page+='<p>Review all source photographs and their Dropbox matches: '+', '.join(link('../source-galleries/'+ref+'.html',ref) for ref,_ in product_links[pid])+'. Source-gallery membership remains separate from an exact finish or variant assignment.</p>'
    labels={'selected':'Selected catalogue references','retained_scope':'Additional retained source-scope references','reviewed_folder':'Additional folder images with reviewed roles','related_scope':'Related products, sizes or finishes','awaiting_role':'Folder candidates awaiting role integration','historical_unavailable':'Historical references without a verified current file'}
    for category,label in labels.items():
        rs=groups[category]
        if not rs:continue
        collapsed=category in ['related_scope','awaiting_role','historical_unavailable']
        page+=('<details><summary>'+e(label)+' ('+str(len(rs))+')</summary>' if collapsed else '<h2>'+e(label)+' ('+str(len(rs))+')</h2>')+'<div class="grid">'
        for row in sorted(rs,key=lambda r:(r.get('visual_role') or 'zz',r.get('name') or '')):
            fid=row['file_id'];im=images[fid];role=row.get('visual_role') or 'role not yet integrated';ev=im.get('visual_role_evidence') or {}
            thumb=previews.get(fid)
            if not thumb:
                saved=im.get('metadata') or {};thumb=saved.get('thumb') or saved.get('full')
            page+='<article data-role="'+e(role)+'">'
            if thumb and Path(thumb).is_file():page+='<img loading="lazy" src="'+e(thumb)+'" alt="'+e(row.get('name'))+'">'
            page+='<p><span class="tag">'+e(role)+'</span></p><p>'+link(row.get('image_url'),row.get('name') or fid)+'<br>'+link(row.get('folder_url'),'Containing folder')+'</p><p>'+e(row['association_qualification'])+'</p>'
            if ev.get('review_note'):page+='<p>'+e(ev['review_note'])+'</p>'
            if ev.get('uncertainty_flags'):page+='<small>'+e('; '.join(ev['uncertainty_flags']))+'</small>'
            if row['other_product_folder_anchors']:page+='<p><small>Folder product: '+', '.join(link(x['product_id']+'.html',x['name']) for x in row['other_product_folder_anchors'])+'</small></p>'
            page+='<details><summary>Reference evidence</summary><small>'+e(fid)+'<br>'+e('; '.join(row['association_statuses']))+'</small></details></article>'
        page+='</div>'+('</details>' if collapsed else '')
    (out/(pid+'.html')).write_text(page)
    inventory.append({'product_id':pid,'name':title,'family':p.get('family'),'image_count':len(rows),'dispositions':dict(Counter(r['review_disposition'] for r in rows)),'page':'products/'+pid+'.html'})
unassigned=[{'file_id':x['file_id'],'name':x['name'],'family':x['family'],'image_url':x['image_url'],'folder_url':x['folder_url'],'visual_role':x.get('visual_role'),'disposition':'NO_EXISTING_OPTION_SCOPE_EDGE; retained in current inventory, not silently assigned from filename','visual_role_evidence':x.get('visual_role_evidence')} for x in current if x['file_id'] not in used]
write(run/'product-image-association-review.json',ledger);write(run/'current-images-without-option-scope.json',unassigned);write(run/'product-reader-index.json',inventory)
page=header('Product image register')+'<h1>Product image register</h1><p>Local Shopify records are included. Each product page lists its selected references, additional reviewed images and unresolved associations with image and containing-folder links.</p><p>'+link('index.html','Progress and platform matching')+' · '+link('source-galleries.html','All 81 source galleries')+' · '+link('family-images.html','All 60 family image libraries')+' · '+link('current-images-without-option-scope.json','Current images without an existing option association')+'</p><input id="search" placeholder="Find a product or family" aria-label="Find a product or family"><table><thead><tr><th>Product</th><th>Family</th><th>Retained image references</th><th>Role review pending</th></tr></thead><tbody>'
for row in sorted(inventory,key=lambda x:x['name'].casefold()):page+='<tr data-search="'+e((row['name']+' '+str(row['family'])).casefold())+'"><td>'+link(row['page'],row['name'])+'</td><td>'+e(row['family'])+'</td><td>'+str(row['image_count'])+'</td><td>'+str(row['dispositions'].get('awaiting_role',0))+'</td></tr>'
page+='</tbody></table><script>document.getElementById("search").addEventListener("input",e=>{let q=e.target.value.toLowerCase();document.querySelectorAll("tr[data-search]").forEach(r=>r.hidden=!r.dataset.search.includes(q))})</script>'
(run/'product-images.html').write_text(page)
assert len(inventory)==188 and all((run/r['page']).exists() for r in inventory)
assert all(not r['image_url'] for rs in ledger.values() for r in rs if r['review_disposition']=='historical_unavailable')
assert all(r['image_url'] and r['folder_url'] for r in unassigned)
summary={'product_pages':len(inventory),'source_gallery_pages':len(source_pages),'family_library_pages':len(family_index),'family_library_image_count':sum(r['image_count'] for r in family_index),'distinct_option_image_references':sum(len(x) for x in ledger.values()),'disposition_counts':dict(counts),'current_wall_files_without_existing_option_scope':len(unassigned),'current_wall_files_all_retained':len(current),'no_new_identity_approvals':True,'no_canonical_or_native_writes':True,'reader':str(run/'product-images.html')}
write(run/'product-reader-validation.json',summary);print(json.dumps(summary,indent=2))
