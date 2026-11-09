from pathlib import Path
import csv, json, urllib.parse
from datetime import datetime, timezone

OUT=Path(__file__).parent
ROOT=OUT.parents[1]
records=json.loads((OUT/'brandboom-restore-plan.json').read_text())['records']
photos=json.loads((OUT/'current-selected-photo-metadata.json').read_text())
public=json.loads((ROOT/'outputs/faire-gumtree-20261104/current-public-images.json').read_text())
native={x['SKU']:x for x in csv.DictReader((OUT/'squarespace-after.csv').open(encoding='utf-8-sig',newline=''))}
def canon(url):
    return urllib.parse.unquote(url.split('?')[0].replace('/content/v1/','/content/'))
rows=[]
for product in records:
    urls=native[product['sku']]['Hosted Image URLs'].split()
    actual={canon(u) for u in urls}
    missing=[]; unmapped=[]
    for iid in product['image_ids']:
        old=public.get(iid,{})
        source_hash=photos[iid].get('original',{}).get('dropbox_content_hash')
        candidates={canon(u) for u in old.get('urls',[])+[old.get('url','')] if u} if source_hash and source_hash==old.get('dropbox_content_hash') else set()
        if not candidates:
            unmapped.append(iid)
        elif not actual & candidates:
            missing.append(dict(id=iid,name=photos[iid]['name'],source_hash=source_hash,known_urls=sorted(candidates)))
    rows.append(dict(catalogue_id=product['catalogue_id'],sku=product['sku'],title=product['title'],selected_count=len(product['image_ids']),website_count=len(urls),missing_known_photos=missing,unmapped_current_photos=unmapped))
report=dict(checked_at=datetime.now(timezone.utc).isoformat(),products=rows,count_differences=[r for r in rows if r['selected_count']!=r['website_count']],known_missing_count=sum(len(r['missing_known_photos']) for r in rows),unmapped_count=sum(len(r['unmapped_current_photos']) for r in rows),pinterest_limit='1 main image plus up to 10 additional per item; ingestion is disabled pending merchant approval')
(OUT/'website-selected-photo-comparison.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k not in ('products','count_differences')}))
print('Products with count differences:',len(report['count_differences']))
print([(r['title'],r['selected_count'],r['website_count'],len(r['missing_known_photos']),len(r['unmapped_current_photos'])) for r in rows if r['missing_known_photos'] or r['unmapped_current_photos']][:25])
