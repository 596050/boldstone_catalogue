"""Check candidate hosted-image geometry without retaining downloaded photographs."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json, urllib.request
from PIL import ImageFile

OUT=Path(__file__).parent
load=lambda n:json.loads((OUT/n).read_text())
review=load('pinterest-original-resolution-review.json')
mapping=load('current-public-images-verified.json')
originals={r['image_id']:r for r in load('pinterest-primary-original-readbacks.json')}
for p in review['products']:
    a=p['primary'];r=originals.get(a['id'])
    if r:
        assert a['original']['dropbox_content_hash']==r['dropbox_content_hash']
        a['original'].update(dimensions=r['dimensions'],sha256=r['sha256'],locally_verified=True,
            dimension_basis='Exact Dropbox revision verified in memory; no downloaded copy retained')
        p['original_dimensions_known']=True
        p['primary_original_meets_documented_dimensions']=r['dimensions'][0]>=1000 and r['dimensions'][1]>=1500
candidates={a['id']:a for p in review['products'] for a in p['higher_resolution_listing_candidates']}

def check(a):
    url=mapping[a['id']]['url'];parser=ImageFile.Parser();read=0
    req=urllib.request.Request(url,headers={'Range':'bytes=0-131071','User-Agent':'BoldstoneCatalogueImageAudit/1.0'})
    with urllib.request.urlopen(req,timeout=45) as r:
        assert r.headers.get_content_type().startswith('image/')
        while read<131072:
            chunk=r.read(min(8192,131072-read))
            if not chunk:break
            read+=len(chunk);parser.feed(chunk)
            if parser.image:break
    dimensions=list(parser.image.size) if parser.image else None
    return dict(image_id=a['id'],url=url,dimensions=dimensions,header_bytes_read=read,
        meets_documented_dimensions=bool(dimensions and dimensions[0]>=1000 and dimensions[1]>=1500))
with ThreadPoolExecutor(max_workers=3) as pool:checks=list(pool.map(check,candidates.values()))
by={r['image_id']:r for r in checks}
for p in review['products']:
    for a in p['higher_resolution_listing_candidates']:a['hosted_check']=by[a['id']]
summary=review['summary']
summary.update(checked_at=datetime.now(timezone.utc).isoformat(),known_original_below_dimensions=sum(p['original_dimensions_known'] and not p['primary_original_meets_documented_dimensions'] for p in review['products']),
    unknown_original_dimensions=sum(not p['original_dimensions_known'] for p in review['products']),
    products_with_already_hosted_qualifying_alternatives=sum(any(a['hosted_check']['meets_documented_dimensions'] for a in p['higher_resolution_listing_candidates']) for p in review['products']),
    unique_candidate_images_checked=len(checks),candidate_header_bytes_read=sum(r['header_bytes_read'] for r in checks))
(OUT/'pinterest-original-resolution-review.json').write_text(json.dumps(review,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(summary))
