"""Fill only blank selected-photo alt text using versioned app writes."""
from pathlib import Path
import json, urllib.request, urllib.error, time, sys
OUT=Path(__file__).resolve().parent
BASE='http://127.0.0.1:8767'
def get(path):
    return json.load(urllib.request.urlopen(BASE+path,timeout=90))
selected=json.loads((OUT/'selected-images.json').read_text())
alts={int(n):v for n,v in (s.split('\t',1) for s in (OUT/'visual-alt-text.tsv').read_text().splitlines())}
assert sorted(alts)==list(range(1,410))
assert all(20<=len(v)<=240 and '\u2014' not in v for v in alts.values())
token=get('/api/bootstrap')['csrf_token']
grouped={}
for image in selected:
    for association in image['associations']:
        grouped.setdefault(association['product_id'],[]).append(image)
outcomes=[]
for pid,images in grouped.items():
    product=get('/api/products/'+pid)
    for image in images:
        aid=image['image']['id']
        for attempt in range(3):
            assets={x['id']:x for x in product['images']}
            review=next((r for r in product['reviews'] if r['kind']=='image' and r['item_id']==aid),{'version':0,'data':{}})
            current=review['data']
            if current.get('alt','').strip():
                result={'product_id':pid,'image_id':aid,'status':'existing_alt_preserved'};break
            if 'listing' not in current.get('uses',[]) or current.get('decision')=='exclude' or aid not in assets:
                result={'product_id':pid,'image_id':aid,'status':'selection_changed_preserved'};break
            expected=image['image']['original']['dropbox_content_hash']
            assert assets[aid]['original']['dropbox_content_hash']==expected, 'Original changed since visual review'
            body={'kind':'image','product_id':pid,'item_id':aid,'version':review['version'],
                  'member_versions':review.get('member_versions',{aid:review['version']}),
                  'data':{**current,'alt':alts[image['number']]},'expected_content_hash':expected}
            if '--apply' not in sys.argv:
                result={'product_id':pid,'image_id':aid,'status':'planned','alt':alts[image['number']]};break
            request=urllib.request.Request(BASE+'/api/reviews',data=json.dumps(body).encode(),
                headers={'Content-Type':'application/json','X-Review-Token':token,'Origin':BASE})
            try:
                saved=json.load(urllib.request.urlopen(request,timeout=90))
            except urllib.error.HTTPError as error:
                if error.code==409 and attempt<2:
                    product=get('/api/products/'+pid);continue
                raise RuntimeError(error.read().decode()) from error
            assert saved['data']['alt']==alts[image['number']]
            assert all(saved['data'].get(k)==v for k,v in current.items() if k not in ('alt','reviewed_content_hash'))
            result={'product_id':pid,'image_id':aid,'status':'saved','version':saved['version'],'alt':saved['data']['alt']};break
        else: raise RuntimeError('Concurrent review changed repeatedly')
        outcomes.append(result)
        with (OUT/'alt-write-receipts.jsonl').open('a') as f: f.write(json.dumps(result)+'\n')
    print(json.dumps({'product':pid,'processed':len(outcomes),'saved':sum(x['status']=='saved' for x in outcomes)}),flush=True)
(OUT/'alt-write-summary.json').write_text(json.dumps({'count':len(outcomes),'saved':sum(x['status']=='saved' for x in outcomes),
    'preserved':sum(x['status']=='existing_alt_preserved' for x in outcomes),'results':outcomes},indent=2))
