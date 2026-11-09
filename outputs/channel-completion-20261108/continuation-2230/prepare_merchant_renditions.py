"""Prepare same-photo CDN renditions under Microsoft's documented size cap.

Read-only network requests. No upload and no local image editing or image copies.
"""
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import datetime,timezone
from pathlib import Path
from PIL import ImageFile
from urllib.parse import parse_qsl,urlsplit,urlunsplit,urlencode
import copy,hashlib,json,urllib.request

OUT=Path(__file__).parent
source=OUT.parent/'google-supplement-refresh-plan.json'
before=json.loads(source.read_text())
audit=json.loads((OUT/'merchant-image-header-audit.json').read_text())
assert audit['publication_products']==176 and audit['failed_header_checks']==0
oversized=[row for row in audit['records'] if row['microsoft_3_9mb_limit_exceeded']]

def candidate(original,width):
    parts=urlsplit(original['url']);assert parts.hostname=='images.squarespace-cdn.com'
    query=dict(parse_qsl(parts.query));query['format']=str(width)+'w'
    url=urlunsplit((parts.scheme,parts.netloc,parts.path,urlencode(query),parts.fragment))
    request=urllib.request.Request(url,headers={'User-Agent':'BoldstoneCatalogueAudit/1.0','Range':'bytes=0-262143'})
    parser=ImageFile.Parser();read=0
    with urllib.request.urlopen(request,timeout=45) as response:
        while read<262144 and not parser.image:
            chunk=response.read(min(16384,262144-read));read+=len(chunk)
            if not chunk:break
            parser.feed(chunk)
        content_range=response.headers.get('Content-Range')
        length=int(content_range.rsplit('/',1)[-1]) if content_range else int(response.headers.get('Content-Length',0))
        return {'url':url,'http_status':response.status,'response_bytes':length,
            'dimensions':list(parser.image.size) if parser.image else None,
            'format':parser.image.format if parser.image else None,'header_bytes_read':read,'requested_width':width}

def prepare(row):
    original_width,original_height=row['dimensions']
    minimum_width=min(500,original_width);minimum_height=min(500,original_height)
    trials=[]
    # Prefer 1000w when it preserves both minimum dimensions. Wider photographs
    # use a documented larger rendition; never invent or upscale image pixels.
    preferred=next((w for w in [1000,1500,2500] if min(w,original_width)/original_width*original_height>=minimum_height),2500)
    widths=list(dict.fromkeys([preferred]+[w for w in [1500,1000,750,500,2500] if w<=preferred]))
    for width in widths:
        expected_width=min(width,original_width)
        if expected_width<minimum_width or expected_width/original_width*original_height<minimum_height:continue
        result=candidate(row,width);trials.append(result)
        if (result['http_status'] in [200,206] and result['format'] in ['JPEG','PNG','GIF','BMP','TIFF']
            and 0<result['response_bytes']<=3_900_000 and result['dimensions']
            and result['dimensions'][0]>=minimum_width and result['dimensions'][1]>=minimum_height):
            assert result['dimensions'][0]<=original_width and result['dimensions'][1]<=original_height
            return {'old_url':row['url'],'original_response_bytes':row['total_response_bytes'],
                'original_dimensions':row['dimensions'],'uses':row['uses'],'replacement':result,'trials':trials}
    raise RuntimeError('No qualified same-photo rendition: '+row['url'])

prepared=[]
with ThreadPoolExecutor(max_workers=3) as pool:
    futures=[pool.submit(prepare,row) for row in oversized]
    for future in as_completed(futures):
        prepared.append(future.result())
        if len(prepared)%25==0:print('Prepared',len(prepared),'of',len(oversized),flush=True)
prepared.sort(key=lambda row:row['old_url'])
replacements={row['old_url']:row['replacement']['url'] for row in prepared}
after=copy.deepcopy(before);changes=[]
for old,row in zip(before['rows'],after['rows']):
    row['image_link']=replacements.get(row['image_link'],row['image_link'])
    row['additional_image_link']=','.join(replacements.get(url,url) for url in row['additional_image_link'].split(','))
    for key in old:
        if old[key]!=row[key]:
            assert key in ['image_link','additional_image_link'];changes.append({'offer_id':row['id'],'field':key,'before':old[key],'after':row[key]})
    for key in ['image_link','additional_image_link']:
        old_urls=old[key].split(',');new_urls=row[key].split(',');assert len(old_urls)==len(new_urls)
        for a,b in zip(old_urls,new_urls):
            assert urlsplit(a).netloc==urlsplit(b).netloc and urlsplit(a).path==urlsplit(b).path
after.update(prepared_utc=datetime.now(timezone.utc).isoformat(),output_filename='continuation-2230/google-microsoft-compatible-supplement.tsv',
    status='PREPARED_NOT_UPLOADED',source_manifest_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
    rendition_changes=prepared,protected_field_differences=0,changed_cells=changes,
    counts={'products':176,'distinct_rendition_urls':len(replacements),'primary_image_cells':sum(c['field']=='image_link' for c in changes),
            'additional_image_cells':sum(c['field']=='additional_image_link' for c in changes),'unrequested_field_changes':0},
    qualification='Same provider asset paths, order and photo selections. Only documented size rendition queries change. No upload performed.',
    microsoft_requirement='https://learn.microsoft.com/en-us/advertising/shopping-content/products-resource?view=bingads-13')
(OUT/'merchant-compatible-supplement-plan.json').write_text(json.dumps(after,indent=2)+'\n')
print(json.dumps(after['counts']),flush=True)
