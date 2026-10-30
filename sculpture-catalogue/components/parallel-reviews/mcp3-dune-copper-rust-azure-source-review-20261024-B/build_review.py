"""Create a local source-image review while preserving all published fields."""
import hashlib, html, json, math
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, parse_qs, unquote
from PIL import Image, ImageOps, ImageChops, ImageStat

H=Path(__file__).resolve().parent; B=H.parents[2]
read=lambda p:json.loads(Path(p).read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
write=lambda p,x:Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
esc=lambda s:html.escape(str(s),quote=True)
pointer_bytes=(B/'current-master.json').read_bytes();p=json.loads(pointer_bytes)
regpath=B/p['register'];assetpath=B/p['current_asset_reference_map']['path'];nativepath=B/p['current_native_reference_map']['path']
assert sha(regpath)==p['register_sha256'] and sha(assetpath)==p['current_asset_reference_map']['sha256'] and sha(nativepath)==p['current_native_reference_map']['sha256']
g,a=read(regpath),read(assetpath);options={x['product_id']:x for x in g['options']};edges={x['offer_ref']:x for x in g['source_offer_edges']}
observations={x['offer_ref']:x for x in g['current_authenticated_squarespace_inventory_observation']['retained_offer_observations']}
idxpath=B/'components/evidence/offer_review_index.json';idx={x['ref']:x for x in read(idxpath)}
collectionpath=B/'components/parallel-reviews/listing-resolution-2026-10-21/worker-01/raw-public/collection-initial.body';collection=read(collectionpath)
assert sha(collectionpath)=='548078a564dd57cca62e466b5b3a61dc47c8d584e6eedf107f362f429686ae5c'
readbackpath=B/'components/parallel-reviews/eighty-source-field-readback-20261024T012802Z/source-field-readback.json';readback=read(readbackpath);rbs={x['offer_ref']:x for x in readback['entries']}
triagepath=B/'components/parallel-reviews/unpaired43-next-evidence-20261024-B/next-evidence-review.json';triage={x['offer_ref']:x for x in read(triagepath)['rows']}
baseline=read(H/'baseline-before-acanthus-navigation.json');old_options={x['product_id']:x for x in baseline['scoped_options']}
nav=read(H/'selected-image-navigation-readback.json');metadata={x['requested_id']:x['metadata'] for x in nav['entries']}
protected={str(x):sha(x) for x in [regpath,B/p['workbook'],regpath.parent/'image-coverage-current.json',assetpath,nativepath]}
inputs={str(x):sha(x) for x in [idxpath,collectionpath,readbackpath,triagepath,H/'case-definitions.json',H/'cached-photo-ranking.json',H/'copper-landscape-screen.json',H/'baseline-before-acanthus-navigation.json',H/'selected-image-navigation-readback.json']}
for source in readback['sources']:
    assert sha(source['path'])==source['sha256'];inputs[source['path']]=source['sha256']

def cached(path,representation,expected=None):
    path=Path(path);digest=sha(path)
    if expected:assert digest==expected
    with Image.open(path) as im:size=list(im.size)
    return {'path':str(path),'sha256':digest,'bytes':path.stat().st_size,'dimensions':size,'representation':representation,
            'visually_reviewed_this_turn':True,'matches_retained_original_hash':bool(expected),
            'live_original_download_this_turn':False}

def current(fid):
    x=a[fid];assert '/BOLDSTONE MASTER/Products/01 Wall Sculptures/' in x['path']
    r={k:x[k] for k in ['file_id','folder_id','name','path','image_url','folder_url']}
    original=bool(x.get('original')==x['thumb'] and x.get('current_original_content_rehashed') and x.get('sha256'))
    r['cached_image']=cached(x['thumb'],'retained Dropbox original' if original else 'retained thumbnail',x['sha256'] if original else None)
    r['navigation_scope']='Published asset map; only four selected files and four containing folders were checked live this turn.'
    return r

def pixels(path):
    with Image.open(path) as im:return ImageOps.exif_transpose(im).convert('RGB').resize((96,96),Image.Resampling.LANCZOS)

def rmse(x,y):return math.sqrt(sum(v*v for v in ImageStat.Stat(ImageChops.difference(pixels(x),pixels(y))).rms)/3)

def image_url_path(url):
    u=urlsplit(url);path=unquote(u.path)
    if path.startswith('/home/'):
        return path[len('/home'):].rstrip('/')+'/'+parse_qs(u.query)['preview'][0]
    if path.startswith('/preview/'):
        return path[len('/preview'):]
    raise ValueError('Unsupported saved image URL form: '+url)

cases=[];cards=[];viewed={};correspondences=[]
for d in read(H/'case-definitions.json'):
    ref=d['ref'];o=options[d['option_id']];s=idx[ref];rb=rbs[ref];ob=observations[ref];pid,vid,sku=d['tuple']
    assert o['master_fields']==old_options[o['product_id']]['master_fields']
    assert all(o[k]==old_options[o['product_id']][k] for k in ['file_id','folder_id','image_url','folder_url'])
    assert [rb['native_product_id'],rb['native_variant_id'],rb['sku']]==d['tuple']
    assert ob['observed_native_source_tuple']=={'product_id':pid,'variant_id':vid,'sku_raw':sku}
    assert rb['all_nine_compared_fields_equal'] and all(x['equal'] for x in rb['fields'])
    position,native=next((i,x) for i,x in enumerate(collection['items']) if x['id']==pid)
    variants=native['structuredContent']['variants'];assert len(variants)==1
    variant=variants[0];assert (variant['id'],variant['sku'])==(vid,sku)
    assert not variant['attributes'] and not variant['optionValues'] and not variant['images'] and not variant['imageIds']
    assert native['items'][0]['assetUrl']==rb['source_first_image_url']==s['images'][0]['url']
    rows=[]
    for source,fids in zip(s['images'],d['photo_ids']):
        source_original=Path(source['path']).is_file()
        sr=cached(source['path'] if source_original else source['thumb'],'retained source download' if source_original else 'retained source thumbnail',source['sha256'] if source_original else None)
        matches=[]
        for fid in fids:
            im=current(fid);viewed[fid]=im
            matches.append({'current_image':im,'whole_frame_RGB_RMSE_96px':rmse(sr['path'],im['cached_image']['path']),
                            'same_image_composition_supported':True,'source_and_Dropbox_original_bytes_identical':False,
                            'binding_basis':'Direct visual comparison of composition and image details; numerical error is supporting evidence only.'})
        media=next(x for x in native['items'] if x['assetUrl']==source['url'])
        row={'offer_ref':ref,'source_order':source['order'],'source_url':source['url'],'native_media_id':media['id'],
             'source_cached_image':sr,'historical_original_path':source['path'],'historical_original_present':source_original,
             'historical_original_sha256':source['sha256'],'matched_current_images':matches,
             'file_binding_status':'UNBOUND_IN_SCOPED_REVIEW' if not matches else ('MULTIPLE_CURRENT_FILE_CANDIDATES' if len(matches)>1 else 'ONE_CORRESPONDING_FILE_IN_SCOPED_REVIEW'),
             'physical_verification':False,'new_photo_role':False}
        rows.append(row);correspondences.append(row)
    assert all(o[k]==a[o['file_id']][k] for k in ['file_id','folder_id','folder_url'])
    assert image_url_path(o['image_url'])==image_url_path(a[o['file_id']]['image_url'])
    f,folder=metadata[o['file_id']],metadata[o['folder_id']]
    assert f['path_display'].rsplit('/',1)[0]==folder['path_display'] and a[o['file_id']]['path'].endswith(f['path_display'])
    card={k:o[k] for k in ['product_id','canonical_design_id','name','file_id','folder_id','image_url','folder_url']}
    card.update(qualified_working_fields=o['master_fields'],selected_cached_image=current(o['file_id']),
                live_selected_image_and_parent_metadata={'file':f,'folder':folder},sale_policy='Existing individual working option retained',new_SKU_or_configuration_assignment=False)
    card['saved_image_URL_forms_equivalent']=image_url_path(o['image_url'])==image_url_path(a[o['file_id']]['image_url'])==f['path_display']
    cards.append(card)
    c={k:v for k,v in d.items() if k not in ['tuple','photo_ids']}
    c.update(native_tuple=ob['observed_native_source_tuple'],source_url=edges[ref]['source_offer']['source_url'],native_variant=variant,
             source_variant_locator={'path':str(collectionpath),'sha256':sha(collectionpath),'json_pointer':f'/items/{position}/structuredContent/variants/0','capture_utc':'2026-10-21T12:25:34.594104+00:00'},
             source_description_html=native.get('body') or native.get('excerpt'),native_gallery_metadata=native['items'],
             retained_source_offer=edges[ref]['source_offer'],retained_BOM_members=edges[ref]['members'],
             latest_captured_export_observation=ob,source_field_readback=rb,retained_preparation=triage[ref]['current_preparation'],
             source_photo_comparisons=rows,source_frames_reviewed=len(rows),captured_gallery_media_count=len(native['items']),
             unviewed_gallery_media_count=len(native['items'])-len(rows),prior_source_relationship_retained=True,
             exact_current_option_configuration_certified=False,physical_specifications_verified=False,new_platform_pair=False,owner_question_opened=False)
    cases.append(c)

additional=[]
for fid in ['id:cnqzTNngPVsAAAAAAAykFQ','id:cnqzTNngPVsAAAAAAAykEw']:
    im=current(fid);viewed[fid]=im;additional.append({'current_image':im,'finding':'Visually inspected Copper 001/004; neither establishes the exact source-image 2 landscape file binding.'})
assert len(cases)==4 and len(cards)==4 and len(correspondences)==12 and len(viewed)==15
assert sum(len(x['matched_current_images']) for x in correspondences)==13
summary={'source_offers':4,'individual_working_options':4,'qualified_working_fields':24,'source_frames_visually_reviewed':12,
         'source_original_downloads_rehashed':3,'source_thumbnail_only_frames':9,'current_cached_images_visually_reviewed':15,
         'current_originals_matching_retained_asset_hash':2,'unique_current_family_images_machine_ranked':655,
         'source_frames_with_image_correspondence':11,'source_to_current_file_correspondences':13,
         'source_frames_with_multiple_current_file_candidates':2,'source_frames_without_exact_file_binding':1,
         'captured_gallery_media_records':52,'gallery_records_not_visually_reviewed':40,
         'selected_image_metadata_verified':4,'selected_containing_folder_metadata_verified':4,
         'new_products':0,'new_platform_pairs':0,'new_physical_verifications':0}
report={'status':'FOUR_SOURCE_REVIEWS_COMPLETE_WITH_QUALIFIED_FILE_BINDINGS','recorded_utc':datetime.now(timezone.utc).isoformat(),
        'pointer_snapshot':{'sha256':hashlib.sha256(pointer_bytes).hexdigest(),'status':p['status']},'baseline_before_unrelated_refresh':{'path':str(H/'baseline-before-acanthus-navigation.json'),'sha256':sha(H/'baseline-before-acanthus-navigation.json')},
        'protected_files':protected,'source_inputs':inputs,'current_asset_map':{'path':str(assetpath),'sha256':sha(assetpath),'lookup':'current-master.current_asset_reference_map.path'},
        'cases':cases,'individual_options':cards,'viewed_current_images':list(viewed.values()),'additional_current_images_reviewed':additional,'summary':summary,
        'source_scope':'Saved source downloads/thumbnails, 21 October captured public collection, retained 24 October export, current asset map; eight selected-image/folder live metadata reads only.',
        'limits':['Three MCP3 source downloads and two current cached originals match retained hashes. Other viewed images are cached thumbnails. No source-to-Dropbox original byte equality is claimed.',
                  'Only twelve of fifty-two captured gallery records were visually reviewed; forty remain metadata only.',
                  'Copper source frame 2 retains no exact current file assignment. Scoped machine screening, including right-angle rotations in memory, is not a whole-library absence proof.',
                  'Azure individual source frames each have two current file candidates. JPG/WEBP format does not establish a preferred original or justify deletion.',
                  'The Copper series hold, other context/identity holds and platform write holds remain unchanged. Source stock settings, prices and weights remain distinct from accepted working estimates.',
                  'No image, crop, file move, new product or new physical specification was created.'],
        'native_metadata_reads':8,'native_downloads':0,'native_writes':0,'platform_writes':0,'canonical_writes':0}
write(H/'review.json',report)
proposal={'status':'EVIDENCE_ONLY_FOR_MAIN_SESSION','apply_automatically':False,'baseline_register_sha256':p['register_sha256'],'baseline_asset_map_sha256':sha(assetpath),
          'cases':[{'offer_ref':c['ref'],'native_tuple':c['native_tuple'],'existing_option_id':c['option_id'],'finding':c['finding'],
                    'photo_correspondences':[{'source_order':x['source_order'],'source_url':x['source_url'],'file_binding_status':x['file_binding_status'],
                        'current_file_candidates':[{k:v for k,v in z['current_image'].items() if k in ['file_id','folder_id','image_url','folder_url']} for z in x['matched_current_images']]} for x in c['source_photo_comparisons']],
                    'limits':c['limits']} for c in cases],
          'new_products':0,'specification_changes':0,'new_SKU_configuration_assignments':0,'native_actions':[],'platform_actions':[],'owner_questions':[]}
write(H/'source-photo-evidence-proposal.json',proposal)
sections=[];terminal=['MCP3, Dune Ripple 2 Copper/Rust and Azure: four source reviews','All working fields retained; Copper source frame 2 unbound; Azure alternate files preserved.','']
for c,card in zip(cases,cards):
    terminal += [c['ref']+' · '+card['name'],c['finding'],'Image: '+card['image_url'],'Folder: '+card['folder_url']]
    terminal += [k+': '+v['display']+' ['+v['state'].replace('\n','; ')+']' for k,v in card['qualified_working_fields'].items()]
    terminal += c['limits']+[''];pictures=[]
    for x in c['source_photo_comparisons']:
        s=x['source_cached_image'];group='<figure><img src="'+esc(Path(s['path']).as_uri())+'"><figcaption>Source '+str(x['source_order'])+' · '+esc(s['representation'])+' · <a href="'+esc(x['source_url'])+'">source image link</a></figcaption></figure>'
        for z in x['matched_current_images']:
            im=z['current_image'];group+='<figure><img src="'+esc(Path(im['cached_image']['path']).as_uri())+'"><figcaption>'+esc(im['name'])+'<br><a href="'+esc(im['image_url'])+'">Dropbox image</a> · <a href="'+esc(im['folder_url'])+'">folder</a></figcaption></figure>'
        if not x['matched_current_images']:group+='<p>Exact current file unassigned in this scoped review. Existing individual product image retained.</p>'
        pictures.append('<div class="comparison">'+group+'</div>')
    fields=''.join('<tr><th>'+esc(k)+'</th><td>'+esc(v['display'])+'<p class="qualification">'+esc(v['state'])+'</p><details><summary>Recorded basis</summary>'+esc(v['basis'])+'</details></td></tr>' for k,v in card['qualified_working_fields'].items())
    sections.append('<section id="'+c['ref']+'"><h2>'+esc(card['name'])+' · '+c['ref']+'</h2><p><a href="'+esc(card['image_url'])+'">Selected image</a> · <a href="'+esc(card['folder_url'])+'">Containing folder</a></p><p>'+esc(c['finding'])+'</p>'+''.join(pictures)+'<table>'+fields+'</table><ul>'+''.join('<li>'+esc(s)+'</li>' for s in c['limits'])+'</ul></section>')
extra=''.join('<figure><img src="'+esc(Path(x['current_image']['cached_image']['path']).as_uri())+'"><figcaption>'+esc(x['current_image']['name'])+' · <a href="'+esc(x['current_image']['image_url'])+'">image</a> · <a href="'+esc(x['current_image']['folder_url'])+'">folder</a><br>'+esc(x['finding'])+'</figcaption></figure>' for x in additional)
page='<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>MCP3, Dune Ripple and Azure source reviews</title><style>body{max-width:1120px;margin:36px auto;padding:0 20px;font:17px system-ui;line-height:1.5;color:#242424}section{margin-top:36px;border-top:1px solid #bbb;padding-top:18px}.comparison{display:flex;flex-wrap:wrap;gap:16px;margin:24px 0}figure{flex:1;min-width:240px;margin:0}img{width:100%;height:340px;object-fit:contain;background:#f4f4f4}figcaption,.qualification,details{font-size:14px}table{border-collapse:collapse;width:100%}td,th{padding:10px;vertical-align:top;text-align:left;border-bottom:1px solid #ddd;white-space:pre-line}th{width:22%}a{overflow-wrap:anywhere}@media(max-width:600px){figure{min-width:100%}}</style></head><body><h1>MCP3, Dune Ripple and Azure</h1><p>Four existing individual product records and twenty-four qualified working fields are retained. Twelve saved source images were reviewed; eleven have corresponding current images. Copper source image 2 has no exact current file assignment. Azure has two alternate file candidates for each individual source view.</p><p>Four selected images and their actual containing folders were checked by stable ID. Forty other captured gallery records remain unviewed. This local packet changes no catalogue, platform or Dropbox content.</p>'+''.join(sections)+'<section><h2>Additional Copper images inspected</h2><div class="comparison">'+extra+'</div></section></body></html>'
(H/'index.html').write_text(page);(H/'terminal-review.txt').write_text('\n'.join(terminal)+'\n')
assert all(sha(path)==expected for path,expected in protected.items())
print(json.dumps({'status':report['status'],'summary':summary}))
