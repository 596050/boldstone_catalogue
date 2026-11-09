"""Download three existing correctly oriented provider renditions for a native repair.

No image pixels are edited locally and no new photographs are generated. The
published source photographs remain the same three selected Dropbox identities.
"""
from compare_gallery import OUT,PACKET,load,fetch,source_thumb,distance
from datetime import datetime,timezone
from urllib.parse import parse_qsl,urlsplit,urlunsplit,urlencode
from pathlib import Path
from io import BytesIO
from PIL import Image,ImageOps
import hashlib,json,urllib.request

folder=OUT/'orientation-renditions';folder.mkdir(exist_ok=True)
diagnosis=load(OUT/'extra-photo-diagnosis.json')
public=load(PACKET/'current-public-images-verified.json')
results=[]
for item in diagnosis['orientation_candidates']:
    source_id=item['selected_source_id'];source=public[source_id]['url'];parts=urlsplit(source)
    assert parts.hostname=='images.squarespace-cdn.com'
    query=dict(parse_qsl(parts.query));query['format']='1500w'
    url=urlunsplit((parts.scheme,parts.netloc,parts.path,urlencode(query),parts.fragment))
    request=urllib.request.Request(url,headers={'User-Agent':'BoldstoneCatalogueImageAudit/1.0'})
    with urllib.request.urlopen(request,timeout=45) as response:
        body=response.read(3_900_001);content_type=response.headers.get_content_type()
    assert len(body)<=3_900_000
    image=Image.open(BytesIO(body));image.load();assert image.format=='JPEG'
    orientation=image.getexif().get(274,1);assert orientation==1,'Provider rendition still needs orientation metadata'
    reference=fetch({'kind':'expected','key':source_id,'url':source_thumb(source)})
    normalized=ImageOps.exif_transpose(image).convert('RGB').resize((96,96),Image.Resampling.LANCZOS)
    rendered_difference=distance({'normalized':normalized},reference)
    assert rendered_difference<2.5,(source_id,rendered_difference)
    target=folder/(item['sku']+'-selected-photo-upright.jpg');target.write_bytes(body)
    results.append({**item,'correct_provider_rendition_url':url,'local_upload_path':str(target.resolve()),
        'sha256':hashlib.sha256(body).hexdigest(),'bytes':len(body),'dimensions':list(image.size),
        'exif_orientation':orientation,'published_reference_pixel_difference':round(rendered_difference,6),
        'source_dropbox_content_hash':public[source_id]['dropbox_content_hash'],
        'provenance':'Existing selected source photo, correctly oriented by the existing Squarespace image service. Downloaded provider bytes retained without local image edits.'})
report={'prepared_at':datetime.now(timezone.utc).isoformat(),'status':'PREPARED_NOT_UPLOADED','records':results}
(OUT/'orientation-renditions-plan.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps([{k:r[k] for k in ['sku','bytes','dimensions','exif_orientation','published_reference_pixel_difference']} for r in results],indent=2))
