"""Match every current selected Dropbox ID to a saved website gallery URL."""
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import unquote, urlparse
import csv, json
OUT=Path(__file__).parent;ROOT=OUT.parents[1]
load=lambda p:json.loads(Path(p).read_text())
records=load(OUT/'brandboom-restore-plan.json')['records']
photos=load(OUT/'current-selected-photo-metadata.json')
mapping=load(ROOT/'outputs/faire-gumtree-20261104/current-public-images.json')
for r in load(OUT/'website-photo-public-verification.json')['products']:
    iid=r['source_image_id'];url=r['images'][-1]['url'];old=mapping.get(iid,{})
    mapping[iid]=dict(**{k:v for k,v in old.items() if k not in ('url','urls','dropbox_content_hash')},url=url,urls=list(dict.fromkeys(old.get('urls',[])+[url])),dropbox_content_hash=r['source_hash'])
native={r['SKU']:r for r in csv.DictReader((OUT/'squarespace-final.csv').open(encoding='utf-8-sig',newline=''))}
canon=lambda u:unquote(urlparse(u).netloc+urlparse(u).path.replace('/content/v1/','/content/'))
verified=[]
for p in records:
    urls=native[p['sku']]['Hosted Image URLs'].split();actual=set(map(canon,urls))
    assert len(urls)==len(actual)==p['image_count']
    checked=[]
    for iid in p['image_ids']:
        a=mapping[iid];source=photos[iid]['original']['dropbox_content_hash']
        assert source==a['dropbox_content_hash'],(p['sku'],iid,'Source hash changed')
        candidates={canon(u) for u in a.get('urls',[])+[a.get('url','')] if u}
        matched=actual&candidates
        assert matched,(p['sku'],iid,'Selected photo missing')
        checked.append(dict(id=iid,source_hash=source,website_url=next(u for u in urls if canon(u) in matched)))
    assert canon(checked[0]['website_url'])==canon(urls[0]),(p['sku'],'Primary selection mismatch')
    verified.append(dict(catalogue_id=p['catalogue_id'],sku=p['sku'],selected_count=len(checked),website_count=len(urls),photos=checked,primary_matches=True))
result=dict(status='PASS_ALL_CURRENT_SELECTED_PHOTOS',checked_at=datetime.now(timezone.utc).isoformat(),products=verified,product_count=len(verified),selected_placements=sum(x['selected_count'] for x in verified),unique_selected_ids=len({x['id'] for p in verified for x in p['photos']}))
(OUT/'all-selected-photo-verification.json').write_text(json.dumps(result,indent=2)+'\n')
(OUT/'current-public-images-verified.json').write_text(json.dumps(mapping,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k!='products'}))
