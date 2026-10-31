from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import json,openpyxl
OUT=Path(__file__).resolve().parent
read=lambda f:json.loads((OUT/f).read_text())
snap=read('current-catalogue-snapshot.json');plan=read('website-final-plan.json');byid={p['catalogue_id']:p for p in plan['products']};products={p['id']:p for p in snap['products']}
w=openpyxl.load_workbook(OUT/'previous-catalogue.xlsx',read_only=True,data_only=False)
cells={s.title:{c.coordinate:c.value for row in s.iter_rows() for c in row if c.value is not None} for s in w}
patches=[];newlinks=[]
def patch(sheet,cell,value):
 old=cells[sheet].get(cell)
 if old!=value:patches.append({'sheet':sheet,'cell':cell,'before':old,'value':value})
stamp=datetime.fromisoformat(snap['created_utc']).astimezone(ZoneInfo('Europe/London')).strftime('%d/%m/%Y, %H:%M:%S')
for n in ['Wall Sculptures','Images','Specification Sources']:patch(n,'A4',f'App snapshot: {stamp} UK time. Workbook edits do not update the app.')
patch('Wall Sculptures','F7','Internal material / finish')
patch('Wall Sculptures','AD7','Customer-facing description')
patch('Wall Sculptures','A5',str(cells['Wall Sculptures'].get('A5',''))+' Full descriptions are readable on the Website Copy sheet.')
patch('Upload Plan','A4',f'App snapshot: {stamp} UK time. 178 catalogue website records: 176 public and 2 held for photography. Website copy and image sections verified separately.')
patch('Upload Plan','A5','Current native Squarespace IDs replace the previous import plan. Excluded products remain excluded. The catalogue app remains the source of truth for decisions, specifications and prices.')
patch('Upload Plan','W7','Historical matching notes')
patch('Upload Plan','X7','Historical source offers')
for row in range(8,189):
 pid=cells['Wall Sculptures'][f'AA{row}'];p=byid[pid];x=products[pid];fs={f['key']:f for f in x['fields']+x['listing_fields']}
 assert cells['Wall Sculptures'][f'C{row}']==p['catalogue_name']==x['name']
 assert fs['Description']['value']==p['website_description'] and fs['Retail name']['value']==p['retail_name']
 state='Public' if p.get('public') else ('Hidden - photography held' if p.get('product_id') else 'Excluded - not uploaded')
 patch('Wall Sculptures',f'AT{row}',f"Squarespace product {p['product_id']}; variant {p['variant_id']}" if p.get('product_id') else 'Excluded - not uploaded')
 patch('Wall Sculptures',f'AU{row}',state)
 for col,value in [('G',fs['Fixing']['value']),('AD',fs['Description']['value']),('AV',fs['Retail name']['value']),('AW',p.get('website_url','')),('AX',next(iter(p.get('website_in_situ',[])),{}).get('url','')),('AY',p.get('website_in_situ',[{},{}])[1].get('url','') if len(p.get('website_in_situ',[]))>1 else ''),('AZ',state)]:patch('Wall Sculptures',f'{col}{row}',value)
 for col,value in [('F',state),('G',p.get('product_id','')),('H',p.get('variant_id','')),('Z',p['retail_name']),('AA',p.get('website_url','')),('AB',len(p.get('website_in_situ',[]))),('AC',state),('U','Catalogue website record created; current description and context-image update' if p.get('product_id') else 'Excluded - not uploaded')]:patch('Upload Plan',f'{col}{row}',value)
 for sheet,cols in [('Wall Sculptures',['AW','AX','AY']),('Upload Plan',['AA'])]:
  for col in cols:
   item=next((i for i in patches if i['sheet']==sheet and i['cell']==f'{col}{row}'),None)
   if item and str(item['value']).startswith('https://'):newlinks.append({'sheet':sheet,'cell':item['cell'],'target':item['value']})
for col,label in [('AV','Retail / website name'),('AW','Website listing'),('AX','Website context image 1'),('AY','Website context image 2'),('AZ','Website status')]:patch('Wall Sculptures',col+'7',label)
for col,label in [('Z','Retail / website name'),('AA','Website listing'),('AB','Website context images'),('AC','Website status')]:patch('Upload Plan',col+'7',label)
rows=list(w['Specification Sources'].iter_rows(min_row=8,values_only=True));seen=set()
aliases={'Individual price':'Price','Family / collection':'Family','Listing description':'Description','Product name':'Name'}
for row,values in enumerate(rows,8):
 pid,key=values[2],values[4]
 if not pid:continue
 key=aliases.get(key,key)
 fs={f['key']:f for f in products[pid]['fields']+products[pid]['listing_fields']};f=fs[key];seen.add((pid,key))
 for col,value in [('F',f['value']),('G',f['decision']),('H',f['certainty']),('L',f['evidence']),('M',f['notes']),('N',f['updated_at'])]:patch('Specification Sources',f'{col}{row}',value)
extra=[]
for p in snap['products']:
 for f in p['fields']+p['listing_fields']:
  if (p['id'],f['key']) not in seen:extra.append([p['family'],p['name'],p['id'],f['section'],f['key'],f['value'],f['decision'],f['certainty'],f['source_value'],f['qualification'],f['basis'],f['evidence'],f['notes'],f['updated_at']])
assert len(extra)==181
website_rows=[[p['retail_name'],p['website_description'],p.get('website_url',''),len(p.get('website_in_situ',[])),p['catalogue_id']] for p in plan['products']]
for i,row in enumerate(website_rows,8):
 if row[2]:newlinks.append({'sheet':'Website Copy','cell':f'C{i}','target':row[2]})
payload={'snapshot_utc':snap['created_utc'],'event_cutoff':snap['event_cutoff'],'patches':patches,'source_append_start':8+len(rows),'source_append':extra,'new_hyperlinks':newlinks,'website_copy_rows':website_rows,'website_copy_stamp':f'App snapshot: {stamp} UK time.'}
(OUT/'workbook-changes.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2,default=lambda v:v.isoformat()));print({'patches':len(patches),'new_source_rows':len(extra),'new_links':len(newlinks)})
