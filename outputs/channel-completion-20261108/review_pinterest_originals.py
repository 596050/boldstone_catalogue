"""Review actual original metadata; do not change the owner's image selections."""
from pathlib import Path
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
import json, urllib.request

OUT=Path(__file__).parent
load=lambda name:json.loads((OUT/name).read_text())
coverage=load('app-coverage.json')['products']
master=load('master-platform-values.json')
evidence=load('platform-task-evidence.json')['products']
targets=[pid for pid,p in evidence.items() if any(t['id']=='primary_image_size' for t in p['platforms']['pinterest']['tasks'])]
assert len(targets)==96
readbacks=load('pinterest-primary-original-readbacks.json') if (OUT/'pinterest-primary-original-readbacks.json').exists() else []
originals={p['image_id']:p for p in readbacks}

def review(pid):
    with urllib.request.urlopen('http://127.0.0.1:8767/api/products/'+pid,timeout=90) as r:product=json.load(r)
    assets={a['id']:a for a in product['images']}
    c=coverage[pid];primary=c['primary_listing']['image_id'];a=assets[primary]
    pick=lambda a:{k:a.get(k) for k in ('id','name','url','folder_url','original','types','representation','cached_file')}
    if primary in originals:
        verified=originals[primary]
        assert verified['dropbox_content_hash']==a['original']['dropbox_content_hash']
        a={**a,'original':{**a['original'],'dimensions':verified['dimensions'],'sha256':verified['sha256'],
            'dimension_basis':'Exact Dropbox revision downloaded into memory; bytes/content hash/PIL dimensions independently verified',
            'locally_verified':True}}
    dimensions=a.get('original',{}).get('dimensions')
    eligible=lambda d:isinstance(d,list) and len(d)==2 and d[0]>=1000 and d[1]>=1500
    candidates=[pick(assets[i]) for i in c['listing']['image_ids'] if i!=primary and i in assets and eligible(assets[i].get('original',{}).get('dimensions'))]
    return dict(catalogue_id=pid,title=master[pid]['Retail / website name'],primary=pick(a),
                primary_original_meets_documented_dimensions=eligible(dimensions),
                original_dimensions_known=bool(dimensions),higher_resolution_listing_candidates=candidates,
                recommendation='Review supplying the genuine larger original of the SAME current primary' if eligible(dimensions) else
                    'Review a genuine larger selected Listing photograph; preserve product/finish accuracy and owner choice' if candidates else
                    'A genuinely larger suitable photograph is still required; do not upscale and claim new detail')

results=[];failures=[]
with ThreadPoolExecutor(max_workers=3) as pool:
    jobs={pool.submit(review,p):p for p in targets}
    for f in as_completed(jobs):
        try:results.append(f.result())
        except Exception as e:failures.append(dict(catalogue_id=jobs[f],error_type=type(e).__name__))
        if (len(results)+len(failures))%24==0:print(json.dumps({'checked':len(results),'failures':len(failures)}),flush=True)
results.sort(key=lambda p:p['title'])
summary=dict(checked_at=datetime.now(timezone.utc).isoformat(),targets=96,checked=len(results),failures=failures,
    current_primary_original_large_enough=sum(p['primary_original_meets_documented_dimensions'] for p in results),
    known_original_below_dimensions=sum(p['original_dimensions_known'] and not p['primary_original_meets_documented_dimensions'] for p in results),
    unknown_original_dimensions=sum(not p['original_dimensions_known'] for p in results),
    products_with_genuine_selected_listing_alternatives=sum(bool(p['higher_resolution_listing_candidates']) for p in results),
    selections_changed=0,downloaded_original_copies_retained=0,originals_streamed_into_memory=len(readbacks))
(OUT/'pinterest-original-resolution-review.json').write_text(json.dumps(dict(summary=summary,products=results),ensure_ascii=False,indent=2)+'\n')
print(json.dumps(summary),flush=True)
