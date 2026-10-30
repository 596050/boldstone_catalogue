"""Read native links and prepare targeted artifact-tool cell edits."""
import json
import posixpath
import zipfile
from pathlib import Path
from xml.etree import ElementTree as E
from prepare_coverage import current_url

HERE=Path(__file__).resolve().parent
read=lambda p:json.loads(Path(p).read_text())
S='http://schemas.openxmlformats.org/spreadsheetml/2006/main'
R='http://schemas.openxmlformats.org/officeDocument/2006/relationships'
q=lambda t:'{'+S+'}'+t
g=read(HERE/'canonical-master-register.json')
old=read(HERE/'inputs/master_register.before')
changes={};links={};cells={};sheet_info={}
with zipfile.ZipFile(HERE/'inputs/master_workbook.before') as z:
    shared=[''.join(x.itertext()) for x in E.fromstring(z.read('xl/sharedStrings.xml'))] if 'xl/sharedStrings.xml' in z.namelist() else []
    wb=E.fromstring(z.read('xl/workbook.xml'));wr={x.get('Id'):x.get('Target') for x in E.fromstring(z.read('xl/_rels/workbook.xml.rels'))}
    for s in wb.find(q('sheets')):
        n=s.get('name');t=wr[s.get('{'+R+'}id')];loc=t.lstrip('/') if t.startswith('/') else posixpath.normpath('xl/'+t)
        tree=E.fromstring(z.read(loc));values={}
        for c in tree.iter(q('c')):
            typ=c.get('t');v=c.find(q('v'));raw=v.text if v is not None and v.text else ''
            if typ=='s':val=shared[int(raw)]
            elif typ=='inlineStr':val=''.join(c.find(q('is')).itertext())
            elif typ=='b':val=raw=='1'
            elif typ in ['str','e']:val=raw
            elif raw:val=float(raw)
            else:val=''
            values[c.get('r')]=val
        cells[n]=values;sheet_info[n]={'part':loc,'cell_count':len(values)}
        relpath=posixpath.join(posixpath.dirname(loc),'_rels',posixpath.basename(loc)+'.rels')
        rels={r.get('Id'):r for r in E.fromstring(z.read(relpath))} if relpath in z.namelist() else {}
        for h in tree.findall('.//'+q('hyperlink')):
            target='#'+h.get('location') if h.get('location') else rels[h.get('{'+R+'}id')].get('Target')
            links[(n,h.get('ref'))]={'sheet':n,'cell':h.get('ref'),'target':current_url(target),'label':values[h.get('ref')]}

def value(sheet,addr,v):
    v=v if v is not None else ''
    if cells[sheet].get(addr,'')!=v:changes[(sheet,addr)]={'sheet':sheet,'cell':addr,'value':v,'before':cells[sheet].get(addr,'')}

def link(sheet,addr,target,label):
    if not target:return
    label=cells[sheet].get(addr,'') or label
    value(sheet,addr,label)
    links[(sheet,addr)]={'sheet':sheet,'cell':addr,'target':target,'label':label}

for i,o in enumerate(g['options']):
    r=str(i+10);n='Master Catalogue'
    link(n,'N'+r,o.get('image_url'),'Image');link(n,'O'+r,o.get('folder_url'),'Folder')
    value(n,'Q'+r,o.get('file_id') or 'Unbound');value(n,'R'+r,o.get('folder_id') or 'Unbound')
    link(n,'T'+r,o.get('context_image_url'),'Context image');link(n,'U'+r,o.get('context_folder_url'),'Context folder')
    for j in range(6):
        rr=str(10+i*6+j);n='Specifications'
        link(n,'J'+rr,o.get('image_url'),'Image');link(n,'K'+rr,o.get('folder_url'),'Folder')
        value(n,'L'+rr,o.get('file_id') or 'Unbound');value(n,'M'+rr,o.get('folder_id') or 'Unbound')
for i,o in enumerate(g['components'],10):
    n='Components';r=str(i)
    link(n,'F'+r,o.get('image_url'),'Image');link(n,'G'+r,o.get('folder_url'),'Folder');value(n,'H'+r,o.get('file_id'));value(n,'I'+r,o.get('folder_id'))
for i,o in enumerate(g['aliases'],10):
    n='Aliases';r=str(i);link(n,'F'+r,o.get('image_url'),'Image');link(n,'G'+r,o.get('folder_url'),'Folder')
    value(n,'H'+r,o.get('file_id'));value(n,'I'+r,o.get('folder_id'))
for i,o in enumerate(g['source_sets'],10):
    n='Sets and Context';r=str(i);p=o.get('current_primary_reference',{})
    link(n,'I'+r,p.get('image_url'),'Source reference');link(n,'J'+r,p.get('folder_url'),'Folder')
    if p.get('file_id'):value(n,'K'+r,p['file_id'])
    if p.get('folder_id'):value(n,'L'+r,p['folder_id'])
for i,o in enumerate(g['arrangement_context_references'],10+len(g['source_sets'])):
    n='Sets and Context';r=str(i)
    link(n,'I'+r,o.get('image_url'),'Context image');link(n,'J'+r,o.get('folder_url'),'Folder')
    if o.get('file_id'):value(n,'K'+r,o['file_id'])
    if o.get('folder_id'):value(n,'L'+r,o['folder_id'])
for i,o in enumerate(g['source_offer_edges'],10):
    p=o.get('current_primary_reference',{});n='Platform Sources';r=str(i)
    link(n,'U'+r,p.get('image_url'),'Source reference');link(n,'V'+r,p.get('folder_url'),'Folder')
    if p.get('file_id'):value(n,'W'+r,p['file_id'])
    if p.get('folder_id'):value(n,'X'+r,p['folder_id'])
plan={'base_sheet_info':sheet_info,'cell_changes':list(changes.values()),'native_hyperlinks':list(links.values()),
      'original_hyperlink_count':7768,'scope':'Current image references only. Original descriptions, approvals, formulas, historical assertion IDs and historical URLs remain intact.'}
(HERE/'workbook-edit-plan.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'planned_cell_changes':len(changes),'original_sheet_links_after_new_current_contexts':len(links)}))
