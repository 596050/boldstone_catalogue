"""Prepare two genuine paired-photo uploads, preserving catalogue primaries."""
from pathlib import Path
from datetime import datetime,timezone
from urllib.request import urlopen
from urllib.parse import urlencode
from PIL import Image
import json,sys,re,hashlib

ROOT=Path('/Users/tprice/Documents/boldstone');OUT=Path(__file__).parent
sys.path[:0]=[str(ROOT/'catalogue-review'),str(ROOT/'catalogue-review/scripts')]
from import_saatchi_snapshot import Xlsx,column
from prepare_saatchi_catalogue import native_artwork_bindings
from delete_dropbox import connection

read=lambda p:json.loads(p.read_text())
mode=sys.argv[1] if len(sys.argv)>1 else 'ammonite'
assert mode in ['ammonite','moon-fish','lunar-phase-iv','islington']
configs={
 'ammonite':dict(image_id='id:cnqzTNngPVsAAAAAAAuSKA',pairs=[('BSI-DA27DD604F0B','left-hand','Ammonite Grande II (Right)'),('BSI-C3858B1FE67E','right-hand','Ammonite Grande I (Left)')],width=4928,height=3280,upper_weight=22,crate_allowance=20),
 'moon-fish':dict(image_id='id:cnqzTNngPVsAAAAAAAsPiA',pairs=[('BSI-992BA62AA818','left-hand','Moon Fish Wave II'),('BSI-8AC0376F7DEF','right-hand','Moon Fish Wave I')],width=4928,height=3280,upper_weight=10,crate_allowance=16),
 'lunar-phase-iv':dict(image_id='id:cnqzTNngPVsAAAAAAA52Fw',pairs=[('BSI-818D745F1357','left-hand','Lunar Phase I')],width=3598,height=2298,upper_weight=5,crate_allowance=16),
 'islington':dict(image_id='id:cnqzTNngPVsAAAAAAAyW-A',pairs=[('BSI-406CAEC365A4','whole','')],width=2272,height=1704,upper_weight=15,crate_allowance=16,archival=True),
}
cfg=configs[mode]
source=read(OUT/'app-source.json');registry=ROOT/'outputs/catalogue-marketplace-publication-20261101/saatchi-current/primary-draft-receipts.json'
bindings=native_artwork_bindings(registry)
pointer=read(ROOT/'sculpture-catalogue/current-master.json')['current_app_review_workbook']
book=Path(pointer['path']);assert hashlib.sha256(book.read_bytes()).hexdigest()==pointer['sha256']
x=Xlsx(book);sheet='Wall Sculptures';headers={x.value(sheet,a):re.sub(r'\d','',a) for a in x.cells[sheet] if re.fullmatch('[A-Z]+7',a)}
rows={x.value(sheet,f'AA{r}'):r for r in range(8,189)}
image_id=cfg['image_id']
candidates=read(OUT/'saatchi-candidate-associations.json')
if cfg.get('archival'):
    archived=next(c for c in read(OUT/'archival-original-headers.json') if c['id']==image_id)
    photo=dict(id=image_id,name=archived['name'],original=dict(dropbox_content_hash=archived['content_hash']),provenance=dict(path=archived['path']))
else:
    photo=next(c['image'] for c in candidates if c['image']['id']==image_id)
expected=photo['original']['dropbox_content_hash']
now=datetime.now(timezone.utc).isoformat()
with connection(ROOT) as (db,_):
    meta=db.files_get_metadata(image_id)
    assert meta.content_hash==expected and meta.size<50_000_000 and meta.path_display==photo['provenance']['path']
    native=dict(id=meta.id,path=meta.path_display,content_hash=meta.content_hash,revision=meta.rev,bytes=meta.size)
    if cfg.get('archival'):
        downloaded,response=db.files_download('rev:'+meta.rev)
        try:body=response.content
        finally:response.close()
        assert downloaded.id==image_id and downloaded.content_hash==expected
if not cfg.get('archival'):
    q=urlencode(dict(id=image_id,v=expected))
    with urlopen('http://127.0.0.1:8767/api/image?'+q,timeout=90) as response:
        body=response.read(50_000_001)
assert len(body)==native['bytes']<50_000_000
dropbox_hash=hashlib.sha256(b''.join(hashlib.sha256(body[o:o+4194304]).digest() for o in range(0,len(body),4194304))).hexdigest()
assert dropbox_hash==expected
photos=OUT/'qualified-originals';photos.mkdir(exist_ok=True)
path=photos/photo['name']
if path.exists():assert path.read_bytes()==body
else:path.write_bytes(body)
with Image.open(path) as im:
    assert im.size==(cfg['width'],cfg['height']) and im.mode=='RGB'
    fmt=im.format
review=dict(image_id=image_id,photo_path=native['path'],content_hash=expected,sha256=hashlib.sha256(body).hexdigest(),width=cfg['width'],height=cfg['height'],format=fmt,local_path=str(path),visual_review=f'Full unobstructed frontal photograph of both matching White {mode} panels. Use only with prominent left/right single-panel disclosure. No crop, upscale, padding, replacement background or generated content.',native_format_acceptance_required=fmt=='MPO',catalogue_primary_changes=0,checked_utc=now,native_metadata=native)
if cfg.get('archival'):
    review.update(visual_review='Complete White Islington Shellmoon design in its garden-wall installation. A water outlet is visible in the left side of the face. The catalogue has separate Relief and Fountain variants, so the exact offered configuration must be resolved before using this as the Relief primary. Unaltered original, no crop, upscale, padding or generated content.',app_library_selection_status='External Dropbox archive candidate. Not added to app Listing choices.',requires_configuration_review=True)
(OUT/(mode+'-reviewed-original.json')).write_text(json.dumps(review,ensure_ascii=False,indent=2)+'\n')
packets=[]
for pid,side,companion in cfg['pairs']:
    p=next(p for p in source['products'] if p['id']==pid);f={f['key']:f['value'] for f in p['fields']+p['listing_fields']};sku=f['Seller SKU'];row=rows[pid]
    assert sku not in bindings and x.value(sheet,f'AQ{row}')==sku
    price=x.value(sheet,headers['saatchi_asking_price_usd']+str(row))
    intro={'ammonite':'An ammonite spiral recalls fossil forms and the shoreline. Curved ridges catch light across the relief. ','moon-fish':'A crescent moon and flowing fish-like forms create a relief inspired by the movement of water. ','lunar-phase-iv':'A broad crescent and gently curved surface evoke a changing moon. Natural light draws shadows across the relief. ','islington':'A textured spiral curves across a broad lunar form, recalling shells and the rhythms of the shore. Light brings out the relief and its contrasting smooth and rough surfaces. '}[mode]
    dims=[x.value(sheet,headers[h]+str(row)) for h in ['saatchi_width_cm','saatchi_height_cm','saatchi_depth_cm']]
    assert all(isinstance(v,(int,float)) and v>0 for v in dims)
    disclosure=('One wall relief is supplied. Installation and any water-feature equipment shown are not included. ' if cfg.get('archival') else f'Only the {side} panel is for sale. The photo shows the matching pair; its companion is sold separately. ')
    companion_note=f'Companion: {companion}, sold separately. ' if companion else ''
    desc=(disclosure+intro+
          f'Handmade using a gypsum-based material. Colour: White. '+companion_note+
          f'One panel supplied, {dims[1]:g} cm high × {dims[0]:g} cm wide × {dims[2]:g} cm deep. Weight: {f["Weight"]}. '
          'Suitable for outdoor use and indoor display. Keyhole fixings are usually used; French cleats and other options are available. '
          'All designs can be customised. Completely new commissions can be created with designer Sally Price. '
          'Dispatch within 3 working days; delivery transit time is additional.')
    assert len(desc)<=1000 and price>0
    packets.append(dict(catalogue_id=pid,sku=sku,title=p['retail_name'],native_artwork_id=None,native_action='RECONCILE_CURRENT_STUDIO_BEFORE_CREATE_ONCE',description=desc,description_characters=len(desc),price_gbp=p['costing']['pricing']['marked_up_price'],target_artwork_price_usd=price,quantity_per_sale=1,dimensions_cm=dims,edition_type=x.value(sheet,headers['saatchi_art_edition_type']+str(row)),edition_cap=x.value(sheet,headers['saatchi_art_edition_size']+str(row)),edition_scope='Saatchi Art only',creation_year=x.value(sheet,headers['saatchi_art_creation_year']+str(row)),creation_year_is_estimate=True,creation_year_basis=x.value(sheet,headers['saatchi_art_creation_year_basis']+str(row)),native_packaging='Crate',native_packed_weight_kg_estimate=cfg['upper_weight']+cfg['crate_allowance'],packed_dimensions_cm_estimate=[v+10 for v in dims],packing_estimate_qualification=f'{cfg["upper_weight"]} kg upper catalogue artwork mass plus provisional {cfg["crate_allowance"]} kg crate/protection allowance. Dimensions allow 5 cm protection per side. Not measured. Final crate must be weighed, measured and photographed before courier collection.',photo=review,publication_status='PREPARED_NOT_UPLOADED',required_native_checks=['Exact matching artwork does not already exist','Upload accepts this unaltered original and displays it correctly','Single left/right panel disclosure visible','Current account price, edition, availability and shipping validations accepted'],source_workbook_sha256=pointer['sha256'],source_app_revision=source['revision']))
if cfg.get('archival'):
    for packet in packets:
        packet['publication_status']='HELD_VARIANT_PHOTO_REVIEW'
        packet['required_native_checks'].insert(0,'Visible water outlet must match the offered Relief configuration; otherwise obtain a full photograph without the outlet. Do not publish this candidate while unresolved.')
(OUT/(mode+'-upload-packet.json')).write_text(json.dumps(packets,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(dict(prepared=len(packets),image_originals_retained=1,image_bytes=len(body),price_usd=price,native_mutations=0,app_photo_changes=0)))
