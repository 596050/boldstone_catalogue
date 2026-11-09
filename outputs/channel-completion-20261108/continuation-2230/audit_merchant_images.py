"""Read bounded headers from the current public feed images; retain no images."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from PIL import ImageFile
from urllib.parse import urlsplit
import json
import urllib.request

OUT=Path(__file__).parent
PLAN=OUT.parent/'google-supplement-refresh-plan.json'
rows=json.loads(PLAN.read_text())['rows']
uses={}
for row in rows:
    for role,urls in [('primary',[row['image_link']]),('additional',row['additional_image_link'].split(','))]:
        for url in filter(None,urls):
            assert urlsplit(url).hostname=='images.squarespace-cdn.com'
            uses.setdefault(url,[]).append({'offer_id':row['id'],'title':row['title'],'role':role})

def probe(url):
    parser=ImageFile.Parser();read=0
    request=urllib.request.Request(url,headers={'User-Agent':'BoldstoneCatalogueAudit/1.0','Range':'bytes=0-262143'})
    try:
        with urllib.request.urlopen(request,timeout=30) as response:
            while read<262144 and not parser.image:
                chunk=response.read(min(16384,262144-read));read+=len(chunk)
                if not chunk:break
                parser.feed(chunk)
            content_range=response.headers.get('Content-Range')
            size=int(content_range.rsplit('/',1)[-1]) if content_range else int(response.headers.get('Content-Length',0))
            return {'url':url,'http_status':response.status,'content_type':response.headers.get('Content-Type'),
                'total_response_bytes':size,'dimensions':list(parser.image.size) if parser.image else None,
                'image_format':parser.image.format if parser.image else None,'header_bytes_read':read,
                'microsoft_3_9mb_limit_exceeded':size>3_900_000,'uses':uses[url]}
    except Exception as error:
        return {'url':url,'error':str(error),'header_bytes_read':read,'uses':uses[url]}

result=[]
with ThreadPoolExecutor(max_workers=3) as pool:
    futures={pool.submit(probe,url):url for url in uses}
    for future in as_completed(futures):
        result.append(future.result())
        if len(result)%100==0:print('Checked',len(result),'of',len(uses),flush=True)
result.sort(key=lambda row:row['url'])
report={'checked_at':datetime.now(timezone.utc).isoformat(),'publication_products':len(rows),
    'distinct_public_urls':len(uses),'network_header_bytes_read':sum(r['header_bytes_read'] for r in result),
    'original_copies_retained':0,'qualification':'Transparent unauthenticated header checks; not a Bing crawler or approval test.',
    'microsoft_size_requirement_source':'https://learn.microsoft.com/en-us/advertising/shopping-content/products-resource?view=bingads-13',
    'over_limit_distinct_urls':sum(r.get('microsoft_3_9mb_limit_exceeded',False) for r in result),
    'failed_header_checks':sum('error' in r for r in result),'records':result}
(OUT/'merchant-image-header-audit.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k!='records'}),flush=True)
