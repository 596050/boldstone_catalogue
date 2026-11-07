"""Prepare reviewed existing In situ originals without reclassifying them."""
from pathlib import Path
from datetime import datetime,timezone
from urllib.request import urlopen
from PIL import Image
import json,sys,re,hashlib

ROOT=Path('/Users/tprice/Documents/boldstone');OUT=Path(__file__).parent
sys.path[:0]=[str(ROOT/'catalogue-review'),str(ROOT/'catalogue-review/scripts')]
from import_saatchi_snapshot import Xlsx
from prepare_saatchi_catalogue import native_artwork_bindings
from channel_content import saatchi_description,complete_description,values,appearance,has_surface_effect,product_type
from delete_dropbox import connection

cases=[
 ('BSI-1774B82C6518','id:cnqzTNngPVsAAAAAAAt-ZA','Only the tall panel on the left is supplied. The square panel and setting are not included.'),
 ('BSI-BFEE06AB14A0','id:cnqzTNngPVsAAAAAAAygfg','One panel is supplied. The photograph shows the offered design and finish mounted on a wall.'),
 ('BSI-161DFE20DFB0','id:cnqzTNngPVsAAAAAAAucmg','One panel is supplied. The photograph shows the offered spiral design and finish in a garden setting.'),
 ('BSI-FE973AD4748E','id:cnqzTNngPVsAAAAAAAuipQ','Only the centre panel in this group photograph is supplied. The other panels are sold separately.'),
 ('BSI-2AFD94C9F459','id:cnqzTNngPVsAAAAAAAuipQ','Only the left-hand panel in this group photograph is supplied. The other panels are sold separately.'),
 ('BSI-04C3A2CA2BE1','id:cnqzTNngPVsAAAAAAAuipQ','Only the right-hand panel in this group photograph is supplied. The other panels are sold separately.'),
]
read=lambda p:json.loads(p.read_text());sha=lambda b:hashlib.sha256(b).hexdigest()
with urlopen('http://127.0.0.1:8767/api/specifications',timeout=120) as r:app=json.load(r)
products={p['id']:p for p in app['products']}
bindings=native_artwork_bindings(ROOT/'outputs/catalogue-marketplace-publication-20261101/saatchi-current/primary-draft-receipts.json')
ptr=read(ROOT/'sculpture-catalogue/current-master.json')['current_app_review_workbook'];book=Path(ptr['path']);assert sha(book.read_bytes())==ptr['sha256']
x=Xlsx(book);sheet='Wall Sculptures';headers={x.value(sheet,a):re.sub(r'\d','',a) for a in x.cells[sheet] if re.fullmatch('[A-Z]+7',a)}
rows={x.value(sheet,f'AA{r}'):r for r in range(8,189)}
source=read(OUT/'saatchi-qualifying-photo-review.json');images={r['image']['id']:r for r in source}
proofs={};packets=[];photos=OUT/'qualified-originals';photos.mkdir(exist_ok=True)
with connection(ROOT) as(db,_):
 for pid,aid,disclosure in cases:
    p=products[pid];f=values(p);sku=f['Seller SKU'];row=rows[pid]
    assert sku not in bindings and x.value(sheet,'AQ'+str(row))==sku
    assert aid in {i['id'] for i in p['photos']['in_situ']['images']},'Photo is no longer selected In situ'
    if aid not in proofs:
        source_image=images[aid]['image'];head=images[aid]['header'];expected=source_image['original']['dropbox_content_hash']
        meta=db.files_get_metadata(aid)
        assert meta.content_hash==expected and meta.path_display==source_image['provenance']['path'] and meta.size<50_000_000
        path=photos/source_image['name']
        if path.exists():body=path.read_bytes()
        else:
            dm,response=db.files_download('rev:'+meta.rev)
            try:body=response.content
            finally:response.close()
            assert dm.id==aid and dm.content_hash==expected
        assert len(body)==meta.size
        actual=sha(b''.join(hashlib.sha256(body[n:n+4194304]).digest() for n in range(0,len(body),4194304)))
        assert actual==expected
        if not path.exists():path.write_bytes(body)
        with Image.open(path) as im:
            assert im.size==(head['width'],head['height']) and im.mode=='RGB'
            fmt=im.format
        proofs[aid]=dict(image_id=aid,photo_path=meta.path_display,content_hash=expected,sha256=sha(body),revision=meta.rev,bytes=meta.size,width=head['width'],height=head['height'],format=fmt,local_path=str(path),native_format_acceptance_required=fmt=='MPO',visual_review='Genuine complete sculpture(s), matching the recorded component design and finish. Primary reference compared in camera-context-current-references.jpg. Native acceptance as a contextual primary still requires an upload test.',app_use='Existing selected In situ image. No Listing tag or catalogue-primary change.',checked_utc=datetime.now(timezone.utc).isoformat())
        (OUT/'context-reviewed-originals.json').write_text(json.dumps(list(proofs.values()),ensure_ascii=False,indent=2)+'\n')
    record=dict(sku=sku,description_text=complete_description(p,sku,dispatch_days=3,channel='saatchi'),colour=appearance(p),surface_effect=has_surface_effect(p),product_type=product_type(p))
    description=disclosure+'\n\n'+saatchi_description(record,limit=1000-len(disclosure)-2)
    assert len(description)<=1000 and 'Sally Price' in description and 'gypsum-based' in description
    if record['surface_effect']:assert 'pattern will vary' in description
    dims=[x.value(sheet,headers[h]+str(row)) for h in ['saatchi_width_cm','saatchi_height_cm','saatchi_depth_cm']]
    assert all(isinstance(v,(int,float)) and v>0 for v in dims)
    packets.append(dict(catalogue_id=pid,sku=sku,title=p['retail_name'],native_artwork_id=None,native_action='RECONCILE_CURRENT_STUDIO_BEFORE_CREATE_ONCE',description=description,description_characters=len(description),quantity_per_sale=1,target_artwork_price_usd=x.value(sheet,headers['saatchi_asking_price_usd']+str(row)),dimensions_cm=dims,edition_type=x.value(sheet,headers['saatchi_art_edition_type']+str(row)),edition_cap=x.value(sheet,headers['saatchi_art_edition_size']+str(row)),edition_scope='Saatchi Art only',creation_year=x.value(sheet,headers['saatchi_art_creation_year']+str(row)),creation_year_is_estimate=True,photo=proofs[aid],publication_status='REVIEWED_CONTEXT_CANDIDATE_NATIVE_TEST_PENDING',app_photo_changes=0,source_workbook_sha256=ptr['sha256'],source_app_revision=app['revision'],required_native_checks=['Reconcile exact SKU/identity against all existing native records','Native format and contextual-primary acceptance','Correct single panel identified and disclosure visible','Current edition, price and required packing fields verified']))
    (OUT/'context-upload-packets.json').write_text(json.dumps(packets,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(dict(reviewed_context_candidates=len(packets),originals_retained=len(proofs),native_mutations=0,app_category_changes=0)))
