import hashlib,json,sys,urllib.request,zipfile,xml.etree.ElementTree as E
from pathlib import Path
ROOT=Path('/Users/tprice/Documents/boldstone');OUT=Path(__file__).resolve().parent/'requirements-workbook';OUT.mkdir(exist_ok=True)
sys.path.insert(0,str(ROOT/'catalogue-review'))
from delete_dropbox import connection
pointer=json.loads((ROOT/'sculpture-catalogue/current-master.json').read_text());p=pointer['current_app_review_workbook']
(OUT/'source-pointer-before.json').write_text(json.dumps(pointer,indent=2))
with connection(ROOT) as (client,root):
 m=client.files_get_metadata(p['dropbox']['id']);assert m.path_display=='/BOLDSTONE MASTER/Products/01 Wall Sculptures/_Documents_Catalogue/catalogue_wall_sculptures.xlsx'
 meta,response=client.files_download('rev:'+m.rev)
 try:body=response.content
 finally:response.close()
 assert meta.id==m.id and meta.rev==m.rev and hashlib.sha256(body).hexdigest()==p['sha256']
 (OUT/'previous-catalogue.xlsx').write_bytes(body)
 (OUT/'previous-dropbox-metadata.json').write_text(json.dumps({k:str(getattr(m,k)) if k.endswith('modified') else getattr(m,k) for k in ('id','path_display','rev','size','content_hash','server_modified','client_modified')},indent=2))
with urllib.request.urlopen('http://127.0.0.1:8767/api/specifications',timeout=120) as response:snap=json.load(response)
(OUT/'app-snapshot.json').write_text(json.dumps(snap,ensure_ascii=False))
products={p['id']:p for p in snap['products']};assert len(products)==181
fields={pid:{f['key']:f for f in p['fields']+p['listing_fields']} for pid,p in products.items()}
NS={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'};Q=lambda n:'{'+NS['s']+'}'+n
with zipfile.ZipFile(OUT/'previous-catalogue.xlsx') as z:
 sheets=[s.get('name') for s in E.fromstring(z.read('xl/workbook.xml')).find('s:sheets',NS)]
 ss=[''.join(t.text or '' for t in si.iter(Q('t'))) for si in E.fromstring(z.read('xl/sharedStrings.xml'))] if 'xl/sharedStrings.xml' in z.namelist() else []
 cells={name:{c.get('r'):c for c in E.fromstring(z.read(f'xl/worksheets/sheet{i+1}.xml')).findall('s:sheetData/s:row/s:c',NS)} for i,name in enumerate(sheets)}
 def val(name,addr):
  c=cells[name].get(addr)
  if c is None:return None
  if c.get('t')=='inlineStr':return ''.join(t.text or '' for t in c.iter(Q('t')))
  v=c.find('s:v',NS);v=v.text if v is not None else ''
  return ss[int(v)] if c.get('t')=='s' else v
 patches=[]
 def put(name,addr,value):
  old=val(name,addr)
  if old!=value:patches.append({'sheet':name,'cell':addr,'before':old,'value':value})
 for row in range(8,189):
  pid=val('Wall Sculptures',f'AA{row}');assert val('Website Copy',f'E{row}')==pid
  for col,key in [('J','Availability'),('K','Lead time'),('AD','Description')]:put('Wall Sculptures',f'{col}{row}',fields[pid][key]['value'])
  put('Website Copy',f'B{row}',fields[pid]['Description']['value'])
 for addr,c in cells['Specification Sources'].items():
  if not addr.startswith('C') or not addr[1:].isdigit() or int(addr[1:])<8:continue
  row=int(addr[1:]);pid=val('Specification Sources',addr);key=val('Specification Sources',f'E{row}')
  key={'Listing description':'Description'}.get(key,key)
  if pid in fields and key in ('Availability','Lead time','Description'):
   f=fields[pid][key]
   for col,k in [('F','value'),('G','decision'),('H','certainty'),('L','evidence'),('M','notes')]:put('Specification Sources',f'{col}{row}',f[k])
 keys=['Brand','Product type','Model / catalogue reference','Seller SKU','Colour / appearance','Quantity per sale','Marketplace title','Lead time','Dispatch exceptions','Product identifier status','Channel information gaps']
 channelrows=[[p['id'],p['retail_name'] or p['name'],p['listing_decision']]+[fields[p['id']][k]['value'] for k in keys] for p in snap['products']]
 usrows=[]
 for p in snap['products']:
  u=p['us_shipping']
  for quote in u.get('quotes',[]) or [{'status':u['status']}]:
   c=quote.get('charges',{});d=quote.get('destination',{});dims=u.get('packed_cm') or [None]*3
   usrows.append([p['id'],p['retail_name'] or p['name'],d.get('name',''),d.get('postcode',''),quote.get('status'),
     u.get('packed_kg'),*dims,quote.get('dimensional_kg'),quote.get('billable_kg'),
     *[c.get(k) for k in ('transport_gbp','residential_gbp','additional_handling_gbp','large_package_gbp','demand_gbp','surge_gbp','fuel_gbp','us_processing_gbp','collection_gbp')],
     quote.get('estimate_gbp'),quote.get('fuel_percent'),quote.get('as_of'),quote.get('valid_until'),
     u.get('packing_basis',''),quote.get('message',u.get('message','')),
     '; '.join(quote.get('exclusions',[])),quote.get('sources',{}).get('rates',''),quote.get('sources',{}).get('fuel','')])
 payload={'sheets':sheets,'patches':patches,'products':181,'new_sheets':[
 {'name':'Channel Details','title':'Channel details · 181 component records','note':'Default dispatch 10 working days; 3 only where required. TikTok two-day eligibility remains unresolved. Quantity per sale is not stock. Source: local app, 1 November 2026.',
  'headers':['Catalogue ID','Retail / website name','Listing decision',*keys],'rows':channelrows},
 {'name':'US Delivery Estimates','title':'USA delivery planning · sample destinations','note':'UPS published list-rate estimates, not checkout charges or booked quotes. Provisional packaging. Requote actual address and measured package; exclusions apply. Ten components require freight quotes.',
  'headers':['Catalogue ID','Retail / website name','Destination','Sample ZIP','Status','Packed kg','Length cm','Width cm','Height cm','Dimensional kg','Billable kg','Transport GBP','Residential GBP','Handling GBP','Large package GBP','Demand GBP','Surge GBP','Fuel GBP','US processing GBP','Collection GBP','Budget GBP','Fuel %','As of','Valid until','Packing basis','Quote qualification','Excluded costs','Rate source','Fuel source'],'rows':usrows}]}
 (OUT/'patches.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2))
 print(json.dumps({'products':181,'patches':len(patches),'new_sheets':[s['name'] for s in payload['new_sheets']],'revision':m.rev}))
