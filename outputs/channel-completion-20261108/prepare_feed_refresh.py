"""Prepare exact existing-ID refreshes from saved native and public evidence."""
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import unquote, urlparse
import csv, json

OUT=Path(__file__).parent
load=lambda n:json.loads((OUT/n).read_text())
master=load('master-platform-values.json')
publication={r['catalogue_id'] for r in load('brandboom-restore-plan.json')['records']}
native={r['id']:r for r in csv.DictReader((OUT/'google-native-products-before.tsv').open(encoding='utf-8-sig',newline=''),delimiter='\t')}
website={r['Variant ID [Non Editable]']:r for r in csv.DictReader((OUT/'squarespace-final.csv').open(encoding='utf-8-sig',newline=''))}
changed={r['catalogue_id']:r for r in load('website-photo-public-verification.json')['products']}
canon=lambda u:unquote(urlparse(u).netloc+urlparse(u).path.replace('/content/v1/','/content/'))
headers=['id','title','description','price','image_link','additional_image_link','shipping_weight','custom_label_0','custom_label_1','max_handling_time']
rows=[];changes=[]
for pid,m in master.items():
    vid=m.get('pinterest_id')
    if pid not in publication:continue
    assert vid in native and vid in website,(pid,vid)
    before=native[vid];w=website[vid];urls=w['Hosted Image URLs'].split()
    # A primary must follow the app selection, never an incidental stale gallery order.
    assert canon(urls[0])==canon(m['pinterest_image_link']),(pid,'Website primary must first be reconciled with app')
    assert float(before['price'].split()[0])==float(w['Price'])
    additional=urls[1:11]
    if pid in changed and urls[-1] not in additional:
        additional=urls[1:10]+[urls[-1]]
    assert len(additional)<=10 and len(set(map(canon,additional)))==len(additional)
    row={h:before[h.replace('_',' ')] for h in headers}
    row.update(title=w['Title'],image_link=urls[0],additional_image_link=','.join(additional))
    assert row['id']==vid and row['price']==before['price']
    rows.append(row)
    for h,v in row.items():
        old=before[h.replace('_',' ')]
        if old!=v:changes.append(dict(catalogue_id=pid,variant_id=vid,field=h,before=old,after=v))
assert len(rows)==176 and len({r['id'] for r in rows})==176
assert sum(c['field']=='title' for c in changes)==62
assert all(c['field'] in ('title','image_link','additional_image_link') for c in changes)
plan=dict(prepared_utc=datetime.now(timezone.utc).isoformat(),account='5664655454',existing_source='10789003059',headers=headers,rows=rows,changes=changes,
    counts=dict(records=176,title_changes=62,primary_image_changes=sum(c['field']=='image_link' for c in changes),image_list_changes=sum(c['field']=='additional_image_link' for c in changes),price_changes=0,new_products=0),
    image_selection='Existing primary retained. Up to ten secondary images; newly selected photographs included within that platform limit.')
(OUT/'google-supplement-refresh-plan.json').write_text(json.dumps(plan,indent=2)+'\n')

# Keep the existing Google Sheet layout, public-only columns and stable row order.
s=load('pinterest-sheet-cells-before.json');rs=s['sheets'][0]['data'][0]['rowData']
value=lambda c:c.get('userEnteredValue',{}).get('stringValue','')
ph=[value(c) for c in rs[0]['values']];patches=[]
for idx,r in enumerate(rs[1:],2):
    old={h:value(c) for h,c in zip(ph,r['values'])};vid=old['id'];w=website[vid]
    assert any(m.get('pinterest_id')==vid for m in master.values())
    p=next(x for x in rows if x['id']==vid)
    updates=dict(title=w['Title'],additional_image_link=p['additional_image_link'])
    for field,new in updates.items():
        col=ph.index(field)
        if old[field]!=new:patches.append(dict(row=idx,column=col+1,field=field,id=vid,before=old[field],value=new))
assert len(rs)==177 and len({value(r['values'][0]) for r in rs[1:]})==176
(OUT/'pinterest-sheet-refresh-plan.json').write_text(json.dumps(dict(spreadsheet_id=s['spreadsheetId'],sheet_id=150703720,sheet_name='Products',patches=patches,rows=176,unchanged_primary_images=True,unchanged_prices=True),indent=2)+'\n')
print(json.dumps(plan['counts']))
print(json.dumps(dict(pinterest_cells=len(patches),pinterest_title_changes=sum(p['field']=='title' for p in patches),pinterest_image_changes=sum(p['field']=='additional_image_link' for p in patches))))
