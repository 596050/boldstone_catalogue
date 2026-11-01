"""Prepare exact current-app edits; read the template without rewriting it."""
from pathlib import Path
from datetime import datetime, timezone
import json
import openpyxl

OUT = Path(__file__).resolve().parent
snap = json.loads((OUT/'catalogue-snapshot.json').read_text())
book = openpyxl.load_workbook(OUT/'previous-catalogue.xlsx', read_only=True, data_only=False)
before = {s.title: {c.coordinate: c.value for row in s.iter_rows() for c in row if c.value is not None} for s in book}
patches, links = {}, []
def put(sheet, cell, value):
    if before[sheet].get(cell) != value:
        patches[sheet,cell] = {'sheet':sheet,'cell':cell,'before':before[sheet].get(cell),'value':value}
def link(sheet,cell,url,label,internal=False):
    links.append({'sheet':sheet,'cell':cell,'target':url or '', 'label':label,'internal':internal})
    put(sheet,cell,label if url else '')
def text(x):
    return '' if x is None else str(x).replace('\u2014','-')
def joined(x): return '; '.join(map(text,x or []))
def yn(x): return 'Yes' if x else 'No'

products={p['id']:p for p in snap['products']}
images={r['image']['id']:r['image'] for r in snap['images']}
# Refresh editable rates from the same app snapshot, including the zero labour rate.
config=snap['cost_settings']
for row,values in enumerate(book['Cost Rates'].iter_rows(min_row=8,values_only=True),8):
    key,group=values[:2]
    if not key:continue
    if group=='Global':put('Cost Rates',f'D{row}',config[key])
    else:
        rate=config[group][key]
        for col,k in [('C','label'),('D','rate'),('E','minutes'),('G','basis')]:put('Cost Rates',f'{col}{row}',rate[k])
        link('Cost Rates',f'H{row}',rate['source'],'Supplier / basis')
put('Cost Rates','G11','Owner instruction on 31 October 2026: labour cost is zero for every sculpture. The hourly rate remains editable.')
put('Cost Rates','G29','Selling price = (manufacturing cost + separate labour) x (1 + markup / 100).')
for row,values in enumerate(book['Cost Finishes'].iter_rows(min_row=8,values_only=True),8):
    if values[0]:put('Cost Finishes',f'B{row}',products[values[0]]['name'])
old_finishes={}
for values in book['Cost Finishes'].iter_rows(min_row=8,values_only=True):
    if values[0]:old_finishes.setdefault(values[0],[]).append({'id':values[2],'coverage':values[4]})
assert all(old_finishes.get(pid)==p['costing']['inputs']['finishes'] for pid,p in products.items()), 'Refresh changed finish selections before publishing.'
first={}
image_rows=[]
for row,record in enumerate(snap['images'],8):
    a,c,m=record['image'],record['choice'],record['metadata'];o=a.get('original',{})
    pid=record['product_id'];first.setdefault(pid,row)
    types=a.get('effective_types',m.get('types',a.get('types',[])))
    uses=a.get('selected_uses',c.get('uses',[]) if c.get('decision')=='reviewed' else [])
    dims=o.get('dimensions') or [];active=record['scope']=='Associated' and not a.get('excluded')
    for col,key,label in [('F','url','Open image'),('G','folder_url','Open folder')]:
        links.append({'sheet':'Images','cell':f'{col}{row}','target':a.get(key) or '', 'label':label,'internal':False})
    image_rows.append([record['product_family'],record['product_name'],pid,record['scope'],a['name'],
      'Open image' if a.get('url') else '', 'Open folder' if a.get('folder_url') else '',
      yn(active and a.get('primary_eligible')),yn(active and 'listing' in uses),yn('advertising' in uses),
      yn('reference' in uses),yn('in_situ' in types),joined([snap['image_types'].get(t,t) for t in types]),
      joined(uses),c.get('decision','pending'),c.get('order'),dims[0] if dims else None,dims[1] if len(dims)>1 else None,
      o.get('bytes'),f'=S{row}/1048576' if o.get('bytes') is not None else '',o.get('dimension_basis',''),
      joined(m.get('tags')),m.get('collection',''),m.get('rights','unknown'),c.get('alt',''),c.get('caption',''),
      c.get('edit_notes',''),joined([x for x in [c.get('notes'),m.get('notes')] if x]),a.get('source'),a['id'],
      a.get('provenance',{}).get('path',''),a.get('provenance',{}).get('revision',''),o.get('dropbox_content_hash',''),
      joined(a.get('association',{}).get('qualifications')),yn(c.get('decision')=='exclude'),joined(a.get('withheld_reasons'))])

for row in range(8,189):
    pid=before['Wall Sculptures'][f'AA{row}'];p=products[pid]
    assert before['Manufacturing Costs'][f'C{row}']==before['Upload Plan'][f'C{row}']==pid
    f={f['key']:f['value'] for f in p['fields']+p['listing_fields']};cost=p['costing'];i=cost['inputs'];photos=p['photos']
    for sheet in ['Manufacturing Costs','Upload Plan']:
        put(sheet,f'A{row}',p['family']);put(sheet,f'B{row}',p['name'])
    for col,val in {'E':p['listing_decision'],'Z':f['Retail name'],'T':len(photos['listing_ids'])}.items():put('Upload Plan',f'{col}{row}',val)
    link('Upload Plan',f'S{row}',images.get(photos.get('primary_id'),{}).get('url'),'Open primary')
    for col,val in {'B':f.get('Family',p['family']),'C':p['name'],'D':f['Dimensions / depth'],'E':f['Weight'],
                   'F':f['Material / finish'],'G':f['Fixing'],'J':f['Availability'],'K':f['Lead time'],
                   'Y':p['listing_decision'],'Z':p['review_status'],'AC':f['Sale unit'],'AD':f['Description'],
                   'AE':p['notes'],'AV':f['Retail name'],'AQ':f.get('SKU',''),'AR':f.get('Delivery policy',''),
                   'AS':f.get('Transit time','')}.items():
        # Optional platform fields are preserved if the app has no such field.
        if col in ('AQ','AR','AS') and not val:continue
        put('Wall Sculptures',f'{col}{row}',val)
    for col,val in {'L':{'set':'Set','missing':'Not set','needs_review':'Needs review'}[photos['primary_listing']['status']],
                   'N':len(photos['listing_ids']),'O':len(photos['in_situ_ids']),'P':max(0,2-len(photos['in_situ_ids'])),
                   'Q':p['associated_count'],'R':p['candidate_count']}.items():put('Wall Sculptures',f'{col}{row}',val)
    for col,aid,label in [('M',photos.get('primary_id'),'Open primary'),('T',next(iter(photos['listing_ids']),None),'Open listing'),
                          ('U',next(iter(photos['in_situ_ids']),None),'Open in situ 1'),('V',photos['in_situ_ids'][1] if len(photos['in_situ_ids'])>1 else None,'Open in situ 2')]:
        link('Wall Sculptures',f'{col}{row}',images.get(aid,{}).get('url'),label)
    link('Wall Sculptures',f'S{row}',f"'Images'!A{first[pid]}" if pid in first else '', 'View image rows',True)
    link('Wall Sculptures',f'W{row}',p['folder_url'],'Open folder')
    put('Wall Sculptures',f'AM{row}',f"='Manufacturing Costs'!W{row}")
    put('Wall Sculptures',f'BA{row}',f'=ROUND(AM{row}+AL{row},2)')
    if cost['pricing']['mode']=='markup':put('Wall Sculptures',f'H{row}',f'=ROUND(BA{row}*(1+AO{row}/100),2)')
    put('Upload Plan',f'AD{row}',f"='Wall Sculptures'!AL{row}")
    put('Upload Plan',f'AE{row}',f"='Wall Sculptures'!BA{row}")
    for col,key in [('D','width_cm'),('E','height_cm'),('F','depth_cm'),('G','shape_factor'),('H','casting_factor'),('I','material'),('K','fixing_count'),('L','labour_hours_override'),('M','other_cost'),('AD','notes')]:
        put('Manufacturing Costs',f'{col}{row}',i[key])
    put('Manufacturing Costs',f'AC{row}',f['Material / finish'])

# Every specification and note is refreshed from the same coherent app snapshot.
aliases={'Individual price':'Price','Family / collection':'Family','Listing description':'Description','Product name':'Name'}
for row,values in enumerate(book['Specification Sources'].iter_rows(min_row=8,values_only=True),8):
    pid=values[2] if len(values)>2 else None
    if not pid:continue
    p=products[pid];key=aliases.get(values[4],values[4]);f=next(x for x in p['fields']+p['listing_fields'] if x['key']==key)
    for col,val in [('A',p['family']),('B',p['name']),('F',f['value']),('G',f['decision']),('H',f['certainty']),('L',f['evidence']),('M',f['notes'])]:put('Specification Sources',f'{col}{row}',val)
    old=before['Specification Sources'].get(f'N{row}')
    # Keep the existing native timestamp if it is already the same instant.
    timestamp=datetime.fromisoformat(f['updated_at']).replace(tzinfo=None) if f.get('updated_at') else None
    if timestamp and isinstance(old,datetime) and abs((timestamp-old).total_seconds())<.001:timestamp=old
    put('Specification Sources',f'N{row}',timestamp)
for row in range(8,189):
    pid=before['Website Copy'][f'E{row}'];p=products[pid];f={x['key']:x['value'] for x in p['listing_fields']}
    put('Website Copy',f'A{row}',f['Retail name']);put('Website Copy',f'B{row}',f['Description'])

stamp=f"App snapshot: {snap['created_utc']} (UTC). Workbook edits do not update the app."
for sheet in book.sheetnames:put(sheet,'A4',stamp)
put('Wall Sculptures','A5',f"181 components | 58 catalogue families | {sum(bool(p['photos']['primary_id']) for p in products.values())} primary photos set | {snap['summary']['unique_images']} unique retained images. Descriptions are on Website Copy.")
for sheet,cell,value in [('Wall Sculptures','AM7','Manufacturing cost, excluding labour'),('Wall Sculptures','BA7','Total cost including labour'),
 ('Manufacturing Costs','W7','Manufacturing cost, excluding labour (£)'),('Manufacturing Costs','X7','Total cost including labour (£)'),
 ('Upload Plan','R7','Manufacturing cost, excluding labour (GBP)'),('Upload Plan','AD7','Separate labour (GBP)'),('Upload Plan','AE7','Total cost including labour (GBP)')]:put(sheet,cell,value)
for c in ['Y','Z','AA','AB']:put('Manufacturing Costs',c+'7',before['Manufacturing Costs'][c+'7'].replace('alternative (£)','total incl. labour (£)'))
put('Manufacturing Costs','A5','Manufacturing cost excludes labour. Total cost = manufacturing cost + separate labour. Markup selling price uses that total; labour is counted once. Packaging, delivery and sales fees are excluded.')
old_image_last=max(int(''.join(c for c in cell if c.isdigit())) for cell in before['Images'])
payload={'snapshot_utc':snap['created_utc'],'event_cutoff':snap['event_cutoff'],'patches':list(patches.values()),'image_rows':image_rows,'old_image_last':old_image_last,'new_hyperlinks':links,'sheets':book.sheetnames}
(OUT/'workbook-changes.json').write_text(json.dumps(payload,ensure_ascii=False,default=lambda v:v.isoformat()))
print(json.dumps({'patches':len(patches),'image_rows':len(image_rows),'hyperlinks_to_refresh':len(links)}))
