"""Build an isolated evidence packet; shared catalogue and images are read-only."""
import hashlib
import html
import json
from datetime import datetime, timezone
from pathlib import Path
from PIL import Image

H = Path(__file__).resolve().parent
B = H.parents[2]
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
objsha = lambda x: hashlib.sha256(json.dumps(x,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
write = lambda p,x: Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
esc = lambda x: html.escape(str(x),quote=True)
pointer_path = B/'current-master.json'
pointer_bytes = pointer_path.read_bytes()
p = json.loads(pointer_bytes)
register_path = B/p['register']
asset_path = B/p['current_asset_reference_map']['path']
native_path = B/p['current_native_reference_map']['path']
assert sha(register_path)==p['register_sha256']
assert sha(asset_path)==p['current_asset_reference_map']['sha256']
assert sha(native_path)==p['current_native_reference_map']['sha256']
g,a = read(register_path),read(asset_path)
options = {x['product_id']:x for x in g['options']}
edges = {x['offer_ref']:x for x in g['source_offer_edges']}
observations = {x['offer_ref']:x for x in g['current_authenticated_squarespace_inventory_observation']['retained_offer_observations']}
index_path = B/'components/evidence/offer_review_index.json'
index = {x['ref']:x for x in read(index_path)}
collection_path = B/'components/parallel-reviews/listing-resolution-2026-10-21/worker-01/raw-public/collection-initial.body'
collection = read(collection_path)
assert sha(collection_path)=='548078a564dd57cca62e466b5b3a61dc47c8d584e6eedf107f362f429686ae5c'
readback_path = B/'components/parallel-reviews/eighty-source-field-readback-20261024T012802Z/source-field-readback.json'
readback = read(readback_path)
readbacks = {x['offer_ref']:x for x in readback['entries']}
triage_path = B/'components/parallel-reviews/unpaired43-next-evidence-20261024-B/next-evidence-review.json'
triage = {x['offer_ref']:x for x in read(triage_path)['rows']}
rankings = read(H/'cached-photo-ranking.json')['rows']
navigation = read(H/'selected-image-navigation-readback.json')
nav = {x['requested_id']:x['metadata'] for x in navigation['entries']}
protected = {str(x):sha(x) for x in [register_path,B/p['workbook'],register_path.parent/'image-coverage-current.json',asset_path,native_path]}
inputs = {str(x):sha(x) for x in [index_path,collection_path,readback_path,triage_path,H/'cached-photo-ranking.json',H/'selected-image-navigation-readback.json']}
for source in readback['sources']:
    assert sha(source['path'])==source['sha256']
    inputs[source['path']]=source['sha256']

def cached(path):
    path=Path(path)
    with Image.open(path) as im: size=list(im.size)
    return {'path':str(path),'sha256':sha(path),'bytes':path.stat().st_size,'dimensions':size,
            'representation':'retained thumbnail','visually_reviewed_this_turn':True,
            'original_byte_identity_reverified':False}

def image_record(fid):
    x=a[fid]
    assert '/BOLDSTONE MASTER/Products/01 Wall Sculptures/' in x['path']
    r={k:x[k] for k in ['file_id','folder_id','name','path','image_url','folder_url']}
    r['cached_image']=cached(x['thumb'])
    r['navigation_scope']='Published current asset map; live checked this turn only if listed in selected-image-navigation-readback.json'
    return r

definitions = [
    {'ref':'O061','option_id':'BSI-123AABD474C1','family':'Abstract Cave Paintings',
     'tuple':['6a9ffa254b08934e6b0d20bc','f4761dd9-0823-4d75-bcbf-8bd35c78e811','SQ0717348'],
     'photo_ids':[['id:cnqzTNngPVsAAAAAAAt_oA'],['id:cnqzTNngPVsAAAAAAAt_oQ'],['id:cnqzTNngPVsAAAAAAAyhLw']],
     'finding':'All three retained source frames correspond to current Icarus full-panel 010, detail 011 and room-setting 001. The existing Icarus / Abstract Cave Paintings 1 record remains one individually described artwork.',
     'features':['Matching feathered incisions, irregular relief divisions, panel edges, corner mark and light halo in the full and detail frames.','The room-setting frame has the same artwork composition, side table, vase and sofa.'],
     'limits':['Visible glow does not certify installed lighting, electrical equipment or a separate lighting product. The room-setting image remains qualified context with creation origin unverified.','Panel 200 × 100 × 5 cm, separate framework dimensions and approximately 60 kg remain dated source claims. The existing AC730 material-class conflict is retained.','The retained listing says 6–8 weeks; the accepted catalogue policy remains made to order with a 1–2-week lead time. Neither source history nor working policy is silently overwritten.']},
    {'ref':'O062','option_id':'BSI-A0FFC102A6F1','family':'Strata',
     'tuple':['6a9ffe924190ef386f1d85bf','c91feec3-1f08-48af-bb45-ecd9f13e2449','SQ1851097'],
     'photo_ids':[['id:cnqzTNngPVsAAAAAAAyeng'],['id:cnqzTNngPVsAAAAAAAyenQ'],['id:cnqzTNngPVsAAAAAAAyeow']],
     'finding':'The first three retained source images correspond to Strata Verdigris 001, 002 and 003. The selected primary remains 002; the alternate source hero 001 does not require a selection change.',
     'features':['Matching stacked ledges, asymmetric central divisions, turquoise patches and brown ridges.','The front and side stone-wall views have the same framing and masonry joints.'],
     'limits':['Three of seven captured gallery images reviewed; the remaining four are metadata only. No whole-gallery absence claim is made.','The 30 × 30 × 6 cm, 4 kg and cast gypsum/faux verdigris claims retain their source scope. White and Blue Wash Verdigris remain separate finish records; no material formulation is inferred from colour.']},
    {'ref':'O078','option_id':'BSI-A76B86DA7928','family':'Barbados Wave',
     'tuple':['6aa5c06a2be1b2711bb656ad','79b50fd2-9197-4ee6-9e76-d13e170ba3ba','SQ0484508'],
     'photo_ids':[['id:cnqzTNngPVsAAAAAAAyh-g'],['id:cnqzTNngPVsAAAAAAAyh-Q'],['id:cnqzTNngPVsAAAAAAAyh9Q','id:cnqzTNngPVsAAAAAAArtyg']],
     'finding':'The retained front and outdoor-setting source frames correspond to Barbados Wave 003 and selected 002. The workshop source frame has the same composition in both 008 and 009; this review retains both candidates and does not assign a unique original file.',
     'features':['Matching spiral crest, raised panel corner and shadow in the front view.','The outdoor-setting frame retains the same sculpture, bath, shower, wall and vegetation.','Both workshop candidates retain the same spiral, stepped edge, timber surround and surface marks.'],
     'limits':['Three of four captured gallery images reviewed; one remains metadata only.','The 100 × 100 × 8 cm and approximately 83 kg are source claims, not measurements from the photographs. Bath stone Jesmonite remains a listing statement.','The two workshop files are not certified byte duplicates or interchangeable originals. No deletion, deduplication, relocation, new photo role or primary-image replacement is proposed. Scene origin and installed hardware remain unverified.']},
    {'ref':'O080','option_id':'BSI-489226D6FF87','family':'Brancusi Totem',
     'tuple':['6aa688c79129ac4f52dfcaee','606e9cf6-ab79-46fb-9947-dc94300881bf','BT-1-100.22'],
     'photo_ids':[['id:cnqzTNngPVsAAAAAAAyiCQ'],['id:cnqzTNngPVsAAAAAAAyiCA']],
     'finding':'Both retained source frames correspond to the selected Brancusi Totem White 001 individual image and White In Situ 001 garden group image. The source explicitly sells a single column; repeated columns in the context image do not change the sale unit.',
     'features':['Matching opposing curved relief edges, alternating bulges, shading and end shapes in the individual image.','The group frame has matching repeated columns, wall panels, living wall and foreground plants.'],
     'limits':['The 100 × 22 × 8 cm description remains the accepted working size. Raw platform dimensions 19.7 / 9.8 / 2.4 have no encoded units; the existing conditional conflict is preserved.','Approximately 15 kg remains a provisional estimate, and Jesmonite AC730 a substrate guess. Neither is confirmed by image similarity or the raw source weight.','The group photograph remains context; no additional component identities, quantities for sale or manufactured stock are inferred.']},
]

cases=[]; cards=[]; comparisons=[]; current_images={}
for d in definitions:
    ref=d['ref'];o=options[d['option_id']];source=index[ref]
    rb=readbacks[ref];ob=observations[ref];edge=edges[ref]
    pid,vid,sku=d['tuple']
    assert [rb['native_product_id'],rb['native_variant_id'],rb['sku']]==d['tuple']
    assert ob['observed_native_source_tuple']=={'product_id':pid,'variant_id':vid,'sku_raw':sku}
    assert rb['all_nine_compared_fields_equal'] and all(x['equal'] for x in rb['fields'])
    pos,native=next((i,x) for i,x in enumerate(collection['items']) if x['id']==pid)
    variants=native['structuredContent']['variants'];assert len(variants)==1
    variant=variants[0];assert (variant['id'],variant['sku'])==(vid,sku)
    assert variant['attributes']=={} and variant['optionValues']==[] and variant['imageIds']==[] and variant['images']==[]
    assert native['items'][0]['assetUrl']==rb['source_first_image_url']==source['images'][0]['url']
    assert len(source['images'])==len(d['photo_ids'])
    rows=[]
    for s,fids in zip(source['images'],d['photo_ids']):
        ranked=next(x for x in rankings if x['ref']==ref and x['source_order']==s['order'])
        matches=[]
        for fid in fids:
            score=next(x['rmse_96px'] for x in ranked['ranking'] if x['file_id']==fid)
            assert score<1.6
            im=image_record(fid);current_images[fid]=im
            matches.append({'current_image':im,'whole_frame_RGB_RMSE_96px':score,'same_image_composition_supported':True,'exact_original_byte_identity_verified':False})
        media=next(x for x in native['items'] if x['assetUrl']==s['url'])
        row={'offer_ref':ref,'source_order':s['order'],'source_url':s['url'],'native_media_id':media['id'],
             'source_cached_image':cached(s['thumb']),'historical_original_path':s['path'],
             'historical_original_present':Path(s['path']).is_file(),'historical_original_sha256_not_reverified':s['sha256'],
             'matched_current_images':matches,'unique_corresponding_file_in_screened_cache':len(fids)==1,
             'scope_limit':'Photo/rendition correspondence only; no original byte identity, physical cast, material, dimensions, fitted hardware or stock verification.',
             'physical_verification':False,'new_photo_role':False}
        rows.append(row);comparisons.append(row)
    selected=a[o['file_id']]
    assert all(o[k]==selected[k] for k in ['file_id','folder_id','image_url','folder_url'])
    f,folder=nav[o['file_id']],nav[o['folder_id']]
    assert f['id']==o['file_id'] and folder['id']==o['folder_id']
    assert f['path_display'].rsplit('/',1)[0]==folder['path_display']
    assert selected['path'].endswith(f['path_display'])
    card={k:o[k] for k in ['product_id','canonical_design_id','name','file_id','folder_id','image_url','folder_url']}
    card.update(qualified_working_fields=o['master_fields'],working_fields_sha256=objsha(o['master_fields']),
                selected_cached_image=image_record(o['file_id']),live_selected_image_and_parent_metadata={'file':f,'folder':folder},
                sale_policy='Existing individually purchasable working record retained',new_SKU_or_configuration_assignment=False)
    cards.append(card)
    case={k:v for k,v in d.items() if k not in ['tuple','photo_ids']}
    case.update(native_tuple=ob['observed_native_source_tuple'],source_url=edge['source_offer']['source_url'],
                native_variant=variant,source_variant_locator={'path':str(collection_path),'sha256':sha(collection_path),'json_pointer':f'/items/{pos}/structuredContent/variants/0','capture_utc':'2026-10-21T12:25:34.594104+00:00'},
                source_description_html=native.get('body') or native.get('excerpt'),native_gallery_metadata=native['items'],
                retained_source_offer=edge['source_offer'],retained_BOM_members=edge['members'],
                latest_captured_export_observation=ob,source_field_readback=rb,retained_preparation=triage[ref]['current_preparation'],
                source_photo_comparisons=rows,source_frames_reviewed=len(rows),captured_gallery_media_count=len(native['items']),
                unviewed_gallery_media_count=len(native['items'])-len(rows),
                exact_current_option_configuration_certified=False,prior_source_relationship_retained=True,
                new_platform_pair=False,physical_specifications_verified=False,owner_question_opened=False)
    cases.append(case)

assert len(cases)==4 and len(cards)==4 and len(comparisons)==11 and len(current_images)==12
assert sum(len(x['qualified_working_fields']) for x in cards)==24
report={'status':'FOUR_SOURCE_PHOTO_REVIEWS_COMPLETE','recorded_utc':datetime.now(timezone.utc).isoformat(),
        'pointer_snapshot':{'sha256':hashlib.sha256(pointer_bytes).hexdigest(),'status':p['status']},
        'protected_files':protected,'source_inputs':inputs,
        'current_asset_map':{'path':str(asset_path),'sha256':sha(asset_path),'lookup':'current-master.current_asset_reference_map.path'},
        'cases':cases,'individual_options':cards,'viewed_current_images':list(current_images.values()),
        'summary':{'source_offers':4,'individual_working_options':4,'qualified_working_fields':24,
                   'source_renditions_visually_reviewed':11,'current_cached_images_visually_reviewed':12,
                   'cached_family_images_machine_ranked':66,'source_frames_with_image_correspondence':11,
                   'source_to_current_image_correspondences':12,'source_frames_with_multiple_current_file_candidates':1,
                   'gallery_records_not_visually_reviewed':5,'selected_image_metadata_verified':4,'selected_containing_folder_metadata_verified':4,
                   'new_products':0,'new_platform_pairs':0,'new_physical_verifications':0},
        'source_scope':'Retained source thumbnail index, 21 October captured public collection, retained 24 October export and published current asset map. Eight live Dropbox metadata reads cover only the selected images and containing folders.',
        'limits':['Only retained thumbnail bytes were rehashed for image comparison; unavailable temporary source originals were not independently reverified.',
                  'All 11 source thumbnails and 12 corresponding current thumbnails were visually reviewed. Sixty-six current family thumbnails were machine-ranked; that is not a visual review of 66 images.',
                  'Four Strata gallery media and one Barbados media remain unviewed. No claim covers those unviewed images.',
                  'Barbados source image 3 has two current file candidates with the same composition; no unique original-file assignment or byte-duplicate finding.',
                  'Source image correspondence retains existing catalogue associations and does not certify exact current platform size, finish, build, stock or physical specifications.',
                  'All existing photograph holds, deferred Frozen Fish identity, platform write holds and separately owned Acanthus physical question remain unchanged.'],
        'native_metadata_reads':8,'native_downloads':0,'native_writes':0,'platform_writes':0,'canonical_writes':0,
        'other_session_scopes_respected':['Main Acanthus O069/O071/O076/O077','Recovery Moonphase O010/O065/O074/O075/O070','Directory Leaf Growth/Fountain Palm and pending Bone Spiral/Chiswick work']}
write(H/'review.json',report)
write(H/'source-photo-evidence-proposal.json',{'status':'EVIDENCE_ONLY_FOR_MAIN_SESSION','apply_automatically':False,
    'baseline_register_sha256':p['register_sha256'],'baseline_asset_map_sha256':sha(asset_path),
    'cases':[{'offer_ref':c['ref'],'native_tuple':c['native_tuple'],'existing_option_id':c['option_id'],
              'photo_correspondences':[{'source_order':x['source_order'],'source_url':x['source_url'],
                   'current_file_candidates':[{k:v for k,v in z['current_image'].items() if k in ['file_id','folder_id','image_url','folder_url']} for z in x['matched_current_images']],
                   'unique_candidate_in_checked_cache':x['unique_corresponding_file_in_screened_cache'],
                   'evidence_level':'Retained rendition image correspondence only'} for x in c['source_photo_comparisons']],
              'limits':c['limits']} for c in cases],
    'new_products':0,'specification_changes':0,'new_SKU_configuration_assignments':0,'native_actions':[],'platform_actions':[],'owner_questions':[]})

sections=[];terminal=['Icarus, Strata Verdigris, Barbados Wave and Brancusi Totem','Four isolated source-image reviews; existing products and qualified specifications retained.','']
for c,card in zip(cases,cards):
    terminal += [c['ref']+' · '+card['name'],c['finding'],'Image: '+card['image_url'],'Folder: '+card['folder_url']]
    terminal += [k+': '+v['display']+' ['+v['state'].replace('\n','; ')+']' for k,v in card['qualified_working_fields'].items()]
    terminal += c['limits']+['']
    pictures=[]
    for x in c['source_photo_comparisons']:
        s=x['source_cached_image']; group='<figure><img src="'+esc(Path(s['path']).as_uri())+'"><figcaption>Retained source image '+str(x['source_order'])+' · <a href="'+esc(x['source_url'])+'">source link</a></figcaption></figure>'
        for z in x['matched_current_images']:
            im=z['current_image'];group+='<figure><img src="'+esc(Path(im['cached_image']['path']).as_uri())+'"><figcaption>'+esc(im['name'])+'<br><a href="'+esc(im['image_url'])+'">Dropbox image</a> · <a href="'+esc(im['folder_url'])+'">containing folder</a></figcaption></figure>'
        pictures.append('<div class="comparison">'+group+'</div>')
    table=''.join('<tr><th>'+esc(k)+'</th><td>'+esc(v['display'])+'<p class="qualification">'+esc(v['state'])+'</p><details><summary>Recorded basis</summary>'+esc(v['basis'])+'</details></td></tr>' for k,v in card['qualified_working_fields'].items())
    sections.append('<section id="'+c['ref']+'"><h2>'+esc(card['name'])+' · '+c['ref']+'</h2><p><a href="'+esc(card['image_url'])+'">Selected image</a> · <a href="'+esc(card['folder_url'])+'">Containing folder</a></p><p>'+esc(c['finding'])+'</p>'+''.join(pictures)+'<table>'+table+'</table><ul>'+''.join('<li>'+esc(x)+'</li>' for x in c['limits'])+'</ul><p>Captured source: '+str(c['source_frames_reviewed'])+' of '+str(c['captured_gallery_media_count'])+' images reviewed. Existing source tuple: '+esc(str(c['native_tuple']))+'.</p></section>')
page='<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Four sculpture source-image reviews</title><style>body{max-width:1120px;margin:36px auto;padding:0 20px;font:17px system-ui;line-height:1.5;color:#242424}section{margin-top:36px;border-top:1px solid #bbb;padding-top:18px}.comparison{display:flex;flex-wrap:wrap;gap:16px;margin:24px 0}figure{flex:1;min-width:240px;margin:0}img{width:100%;height:340px;object-fit:contain;background:#f4f4f4}figcaption,.qualification,details{font-size:14px}table{border-collapse:collapse;width:100%}td,th{padding:10px;vertical-align:top;text-align:left;border-bottom:1px solid #ddd;white-space:pre-line}th{width:22%}a{overflow-wrap:anywhere}@media(max-width:600px){figure{min-width:100%}}</style></head><body><h1>Four sculpture source-image reviews</h1><p>Eleven retained source images were compared visually with twelve current cached images. All four existing products and twenty-four qualified working fields are retained. Four selected images and their four actual containing folders were verified by stable ID in Dropbox.</p><p>The Barbados workshop source has two corresponding file candidates; it is not assigned to one unique original. Five other gallery records remain unviewed. Source originals were not re-downloaded; comparison hashes cover retained thumbnails.</p><p>This is a local evidence packet for the main catalogue session. No catalogue, source-platform or Dropbox files were changed.</p>'+''.join(sections)+'</body></html>'
(H/'index.html').write_text(page)
(H/'terminal-review.txt').write_text('\n'.join(terminal)+'\n')
assert all(sha(path)==expected for path,expected in protected.items())
print(json.dumps({'status':report['status'],'summary':report['summary'],'report':str(H/'index.html')}))
