"""Use a reviewed landscape camera original for the fountain panel, without app edits."""
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen
from PIL import Image

ROOT = Path('/Users/tprice/Documents/boldstone')
OUT = Path(__file__).parent
sys.path.insert(0,str(ROOT/'catalogue-review'))
from delete_dropbox import connection

packet_path = OUT/'packets/BSI-22E4E4F99696.json'
packet = json.loads(packet_path.read_text())
assert packet['native_artwork_id'] is None
assert packet['description'].startswith('Only the wall-mounted water-feature panel is supplied. The basin, pump, water and plumbing are not included;')
aid = 'id:cnqzTNngPVsAAAAAAArtmw'
associations = json.loads((ROOT/'outputs/platform-goal-continuation-20261106/saatchi-candidate-associations.json').read_text())
source = next(x['image'] for x in associations if x['product_id']==packet['catalogue_id'] and x['image']['id']==aid)
expected = source['original']['dropbox_content_hash']
with urlopen('http://127.0.0.1:8767/api/specifications',timeout=45) as response:
    app = json.load(response)
assert app['revision']==packet['current_source_app_revision']
photo_path = OUT/'qualified-originals'/source['name']
photo_path.parent.mkdir(exist_ok=True)
with connection(ROOT) as (db,_):
    meta = db.files_get_metadata(aid)
    assert meta.id==aid and meta.content_hash==expected and meta.size<5_000_000
    downloaded,response = db.files_download('rev:'+meta.rev)
    try:
        body=response.content
    finally:
        response.close()
    assert downloaded.id==aid and downloaded.rev==meta.rev and len(body)==meta.size
    assert hashlib.sha256(b''.join(hashlib.sha256(body[i:i+4194304]).digest() for i in range(0,len(body),4194304))).hexdigest()==expected
    photo_path.write_bytes(body)
    with Image.open(photo_path) as image:
        assert image.size==(1941,1295) and image.mode=='RGB' and image.format=='JPEG'
        assert not image.getexif().get(34853), 'GPS metadata needs separate handling before upload'
        image.verify()
    packet['previous_prepared_portrait_source']=packet['photo']
    packet['photo']=dict(image_id=aid,photo_path=meta.path_display,content_hash=expected,
                        sha256=hashlib.sha256(body).hexdigest(),revision=meta.rev,bytes=meta.size,
                        width=1941,height=1295,format='JPEG',local_path=str(photo_path),
                        native_upload_path=str(photo_path),native_upload_sha256=hashlib.sha256(body).hexdigest(),
                        visual_review='Complete White shellmoon fountain panel above its basin. The neutral-colour landscape view is a genuine camera photograph; basin, pump, water and plumbing are expressly excluded in the description. Compared with the previously reviewed portrait of the same fountain panel.',
                        app_use='Existing family In situ photograph; qualified for this platform only. App photo purposes and catalogue primary unchanged.',
                        gps_metadata_present=False,checked_utc=datetime.now(timezone.utc).isoformat())
packet_path.write_text(json.dumps(packet,ensure_ascii=False,indent=2)+'\n')
(OUT/'battersea-landscape-original-verification.json').write_text(json.dumps(dict(status='PASS_REVIEWED_ORIGINAL_REPLACEMENT_PREPARED',sku=packet['sku'],photo=packet['photo'],native_creation_or_publication=False,app_changes=0),indent=2)+'\n')
print(json.dumps(dict(status='PASS_REVIEWED_LANDSCAPE_SOURCE',width=1941,height=1295,bytes=len(body),local_path=str(photo_path))))
