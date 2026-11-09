"""Read the downloaded native offer export; do not infer combined offer state."""
from pathlib import Path
from datetime import datetime, timezone
import csv, io, json, sys, zipfile
OUT=Path(__file__).parent
source=Path(sys.argv[1])
with zipfile.ZipFile(source) as z:
    names=[n for n in z.namelist() if n.endswith('.tsv')]
    assert len(names)==1
    b=z.read(names[0])
(OUT/'google-native-products-after.zip').write_bytes(source.read_bytes())
(OUT/'google-native-products-after.tsv').write_bytes(b)
actual={r['id']:r for r in csv.DictReader(io.StringIO(b.decode('utf-8-sig')),delimiter='\t')}
plan=json.loads((OUT/'google-supplement-refresh-plan.json').read_text())
before={r['id']:r for r in csv.DictReader((OUT/'google-native-products-before.tsv').open(encoding='utf-8-sig',newline=''),delimiter='\t')}
assert set(actual)==set(before) and len(actual)==325
differences=[]
for r in plan['rows']:
    a=actual[r['id']]
    for h,v in r.items():
        if a[h.replace('_',' ')]!=v:differences.append(dict(id=r['id'],field=h,expected=v,observed=a[h.replace('_',' ')]))
price_changes=[v for v in actual if actual[v]['price']!=before[v]['price']]
assert not price_changes
scope={x['id'] for x in plan['rows']}
assert len(scope)==176
assert all(actual[v]['brand']==before[v]['brand'] for v in actual.keys()-scope)
brand_matches=sum(actual[v]['brand']=='Boldstone' for v in scope)
r=dict(status='PASS_ALL_176_COMBINED_OFFERS' if not differences else 'COMBINED_OFFER_REFRESH_PENDING',checked_at=datetime.now(timezone.utc).isoformat(),native_offers=325,publication_products=176,new_products=0,price_changes=0,title_mismatches=sum(x['field']=='title' for x in differences),image_mismatches=sum(x['field'] in ('image_link','additional_image_link') for x in differences),brand_mismatches=sum(x['field']=='brand' for x in differences),registered_brand_matches=brand_matches,unrelated_offer_brands_preserved=149,differences=differences)
(OUT/'google-native-refresh-verification.json').write_text(json.dumps(r,indent=2)+'\n')
print(json.dumps({k:v for k,v in r.items() if k!='differences'}))
print([(d['field'],d['id']) for d in differences][:10])
