"""Prepare a narrow, ID-matched dispatch exception update to the current workbook."""
import hashlib, json, sys, urllib.request, zipfile, xml.etree.ElementTree as E
from pathlib import Path
ROOT=Path('/Users/tprice/Documents/boldstone')
OUT=Path(__file__).resolve().parent/'dispatch-workbook'; OUT.mkdir(exist_ok=True)
sys.path.insert(0,str(ROOT/'catalogue-review'))
from delete_dropbox import connection
from channel_content import DISPATCH_EXCEPTIONS
pointer=json.loads((ROOT/'sculpture-catalogue/current-master.json').read_text())
previous=pointer['current_app_review_workbook']
(OUT/'source-pointer-before.json').write_text(json.dumps(pointer,indent=2))
with connection(ROOT) as (client,root):
    m=client.files_get_metadata(previous['dropbox']['id'])
    assert m.path_display=='/BOLDSTONE MASTER/Products/01 Wall Sculptures/_Documents_Catalogue/catalogue_wall_sculptures.xlsx'
    meta,response=client.files_download('rev:'+m.rev)
    try: body=response.content
    finally: response.close()
    assert meta.id==m.id and meta.rev==m.rev
    assert hashlib.sha256(body).hexdigest()==previous['sha256']
    (OUT/'previous-catalogue.xlsx').write_bytes(body)
    (OUT/'previous-dropbox-metadata.json').write_text(json.dumps({k:str(getattr(m,k)) if k.endswith('modified') else getattr(m,k) for k in ('id','path_display','rev','size','content_hash','server_modified','client_modified')},indent=2))
with urllib.request.urlopen('http://127.0.0.1:8767/api/specifications',timeout=120) as response: snap=json.load(response)
(OUT/'app-snapshot.json').write_text(json.dumps(snap,ensure_ascii=False))
products={p['id']:p for p in snap['products']}; assert len(products)==181
fields={pid:{f['key']:f for f in p['fields']+p['listing_fields']} for pid,p in products.items()}
assert all(f['Dispatch exceptions']['value']==DISPATCH_EXCEPTIONS for f in fields.values())
U='http://schemas.openxmlformats.org/spreadsheetml/2006/main';NS={'s':U};q=lambda x:'{'+U+'}'+x
with zipfile.ZipFile(OUT/'previous-catalogue.xlsx') as z:
    sheets=[s.get('name') for s in E.fromstring(z.read('xl/workbook.xml')).find('s:sheets',NS)]
    ss=[''.join(t.text or '' for t in si.iter(q('t'))) for si in E.fromstring(z.read('xl/sharedStrings.xml'))] if 'xl/sharedStrings.xml' in z.namelist() else []
    cells={name:{c.get('r'):c for c in E.fromstring(z.read(f'xl/worksheets/sheet{i+1}.xml')).findall('s:sheetData/s:row/s:c',NS)} for i,name in enumerate(sheets)}
    def val(sheet,addr):
        c=cells[sheet].get(addr)
        if c is None:return None
        if c.get('t')=='inlineStr':return ''.join(t.text or '' for t in c.iter(q('t')))
        v=c.find('s:v',NS);v=v.text if v is not None else ''
        return ss[int(v)] if c.get('t')=='s' else v
    headers={a.rstrip('0123456789'):val('Channel Details',a) for a in cells['Channel Details'] if a.endswith('4') and a.rstrip('0123456789')+'4'==a}
    dispatch_col=next(c for c,v in headers.items() if v=='Dispatch exceptions')
    id_col=next(c for c,v in headers.items() if v=='Catalogue ID')
    patches=[];seen=set()
    for row in range(5,186):
        pid=val('Channel Details',f'{id_col}{row}');assert pid in products and pid not in seen;seen.add(pid)
        addr=f'{dispatch_col}{row}';old=val('Channel Details',addr)
        if old!=DISPATCH_EXCEPTIONS:patches.append({'sheet':'Channel Details','cell':addr,'before':old,'value':DISPATCH_EXCEPTIONS})
    assert seen==set(products)
    for addr in cells['Specification Sources']:
        if not addr.startswith('C') or not addr[1:].isdigit() or int(addr[1:])<8:continue
        row=int(addr[1:]);pid=val('Specification Sources',addr);key=val('Specification Sources',f'E{row}')
        if pid in fields and key=='Dispatch exceptions':
            for col,k in [('F','value'),('G','decision'),('H','certainty'),('L','evidence'),('M','notes')]:
                old=val('Specification Sources',f'{col}{row}');new=fields[pid][key][k]
                if old!=new:patches.append({'sheet':'Specification Sources','cell':f'{col}{row}','before':old,'value':new})
    assert len([p for p in patches if p['sheet']=='Channel Details'])==181
    payload={'sheets':sheets,'patches':patches,'products':181,'new_sheets':[],'render_range':f'{dispatch_col}4:{dispatch_col}7'}
    (OUT/'patches.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2))
    print(json.dumps({'products':181,'patches':len(patches),'revision':m.rev,'render_range':payload['render_range']}))
