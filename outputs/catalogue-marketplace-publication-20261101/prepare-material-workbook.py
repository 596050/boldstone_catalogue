"""Read the current workbook and prepare a narrowly scoped public-copy patch."""
from pathlib import Path
import hashlib, json, sys, urllib.request
import openpyxl

ROOT=Path('/Users/tprice/Documents/boldstone'); OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'catalogue-review'))
from delete_dropbox import connection

pointer=json.loads((ROOT/'sculpture-catalogue/current-master.json').read_text())
(OUT/'source-pointer-before.json').write_text(json.dumps(pointer,indent=2))
p=pointer['current_app_review_workbook']
with connection(ROOT) as (client,root):
    m=client.files_get_metadata(p['dropbox']['id'])
    assert m.path_display=='/BOLDSTONE MASTER/Products/01 Wall Sculptures/_Documents_Catalogue/catalogue_wall_sculptures.xlsx'
    meta,response=client.files_download('rev:'+m.rev)
    try:body=response.content
    finally:response.close()
    assert meta.id==m.id and meta.rev==m.rev
    assert hashlib.sha256(body).hexdigest()==p['sha256'], 'Workbook changed; reconcile before editing.'
    (OUT/'previous-catalogue.xlsx').write_bytes(body)
    (OUT/'previous-dropbox-metadata.json').write_text(json.dumps({k:str(getattr(m,k)) if k.endswith('modified') else getattr(m,k) for k in ('id','path_display','rev','size','content_hash','server_modified','client_modified')},indent=2))
with urllib.request.urlopen('http://127.0.0.1:8767/api/specifications',timeout=120) as response: snap=json.load(response)
(OUT/'material-workbook-app-snapshot.json').write_text(json.dumps(snap,ensure_ascii=False))
products={r['id']:r for r in snap['products']}
plan=json.loads((OUT/'material-update-plan.json').read_text())
assert len(products)==len(plan['products'])==181
fields={pid:{f['key']:f for f in p['fields']+p['listing_fields']} for pid,p in products.items()}
for r in plan['products']:
    for c in r['changes']:assert fields[r['catalogue_id']][c['field']]['value']==c['after_value'], ('App copy changed',r['catalogue_id'])
book=openpyxl.load_workbook(OUT/'previous-catalogue.xlsx',read_only=False,data_only=False)
patches=[]
def put(sheet,cell,value):
    old=book[sheet][cell].value
    if old!=value:patches.append({'sheet':sheet,'cell':cell,'before':old,'value':value})
for row in range(8,189):
    pid=book['Wall Sculptures'][f'AA{row}'].value
    assert book['Manufacturing Costs'][f'C{row}'].value==book['Website Copy'][f'E{row}'].value==pid
    put('Wall Sculptures',f'F{row}',fields[pid]['Material / finish']['value'])
    put('Wall Sculptures',f'AD{row}',fields[pid]['Description']['value'])
    put('Website Copy',f'B{row}',fields[pid]['Description']['value'])
    put('Manufacturing Costs',f'AC{row}',fields[pid]['Material / finish']['value'])
for row,vals in enumerate(book['Specification Sources'].iter_rows(min_row=8,values_only=True),8):
    pid,key=vals[2],vals[4]
    if key=='Listing description':key='Description'
    if pid and key in ('Material / finish','Description'):
        f=fields[pid][key]
        for col,name in [('F','value'),('G','decision'),('H','certainty'),('L','evidence'),('M','notes')]:put('Specification Sources',f'{col}{row}',f[name])
payload={'sheets':book.sheetnames,'patches':patches,'products':181,'scope':'Material / finish and public description only; costs, prices, photography, identities and native workbook parts preserved.'}
(OUT/'material-workbook-patches.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2))
print(json.dumps({'products':181,'patches':len(patches),'revision':m.rev,'sheets':book.sheetnames}))
