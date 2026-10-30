"""Independent native-XLSX, register and SQLite publication readback."""
from common import *
from collections import Counter
from copy import deepcopy
from urllib.parse import unquote
from xml.etree import ElementTree as E
from html.parser import HTMLParser
import re, sqlite3
import csv

checks=0;errors=[]
def check(ok,message):
    global checks
    checks+=1
    if not ok:errors.append(message)
original=read(manifest['sources']['register']['snapshot'])
allowed={'file_id','folder_id','image_url','folder_url','context_file_id','context_folder_id','context_image_url','context_folder_url','context_status','context_description','photo_coverage','owner_confirmed_design_reference','current_primary_selection','current_series_reference','current_link_basis','historical_primary_reference','historical_series_reference'}
for before,after in zip(original['options'],g['options']):
    pid=before['product_id'];check(pid==after['product_id'],pid+' row order')
    for k in set(before)|set(after):
        if k not in allowed:check(before.get(k)==after.get(k),pid+' unauthorized register change '+k)
    if pid not in active:check(before==after,pid+' retired history changed')
    elif after.get('file_id'):
        r=files.get(after['file_id']);check(r is not None,pid+' selected Primary absent')
        if r:
            check(after['folder_id']==r['folder_id'],pid+' Primary actual parent')
            check(after['image_url']==r['image_url'],pid+' Primary URL')
for key in original:
    if key=='summary':
        for k in original[key]:
            if k!='individual_options_with_dropbox_reference':check(g[key][k]==original[key][k],'summary source field changed '+k)
        check(g[key]['individual_options_with_dropbox_reference']==sum(o['product_id'] in active and o.get('file_id') in files for o in g['options']),'summary current Primary count')
    elif key not in {'options','latest_verified_native_filename_import'}:check(g[key]==original[key],'top-level source field changed '+key)
check(len(active)==187 and len(g['options'])==189,'option count')
check(len(g['original_review_specification_assertions'])==1668,'original assertion count')
check(len(files)==manifest['current_audited_files'],'current cut file count')

wb_reports=[]
preservation=read(H/'native-preservation-receipt.json')
for plan,receipt in zip(read(H/'workbook-edit-plan.json')['plans'],preservation['workbooks']):
    before,after=Book(plan['source']),Book(plan['output']);planned={(e['sheet'],e['cell']):e for e in plan['edits']}
    check(sha(plan['output'])==receipt['output_sha256'],'output hash differs from preservation receipt')
    check(list(after.sheets)==list(before.sheets)+([plan['new_sheet']] if plan['new_sheet'] and not plan.get('replace_image_sheet') else []),'sheet/order drift')
    for sn in before.sheets:
        if plan.get('replace_image_sheet') and sn==plan['new_sheet']:continue
        bc,bl=before.sheet(sn);ac,al=after.sheet(sn)
        for ref in set(bc)|set(ac):
            ed=planned.get((sn,ref))
            if not ed:check(bc.get(ref)==ac.get(ref),sn+'!'+ref+' undeclared cell change')
            elif ed['kind']=='hyperlink':
                target=('formula',ed['formula'][1:]) if ed['keep_formula'] else ('text',ed['label'])
                check(ac.get(ref)==target,sn+'!'+ref+' hyperlink label/formula mismatch')
                if not ed['keep_formula']:check(al.get(ref)==ed['url'],sn+'!'+ref+' hyperlink target mismatch')
            elif ed['kind']=='formula':check(ac.get(ref)==('formula',ed['formula'][1:]),sn+'!'+ref+' formula mismatch')
            else:
                val=('number',str(ed['value'])) if isinstance(ed['value'],(int,float)) else ('text',ed['value'])
                check(ac.get(ref)==val,sn+'!'+ref+' value mismatch')
        for ref in set(bl)|set(al):
            ed=planned.get((sn,ref))
            check(al.get(ref)==(ed['url'] if ed and ed['kind']=='hyperlink' and (not ed['keep_formula'] or ref in bl) else bl.get(ref)),sn+'!'+ref+' undeclared or wrong native hyperlink')
        root=E.fromstring(after.zip.read(after.sheets[sn]))
        for c in root.iter(native.M+'c'):check(c.get('t')!='e',sn+'!'+c.get('r','')+' formula error')
        for tag in ['cols','mergeCells','conditionalFormatting','dataValidations','tableParts','sheetViews']:
            a=E.fromstring(before.zip.read(before.sheets[sn])).findall(native.M+tag);b=root.findall(native.M+tag)
            check([E.tostring(x) for x in a]==[E.tostring(x) for x in b],sn+' native feature changed '+tag)
    for part in before.zip.namelist():
        if part not in receipt['modified_existing_parts']:check(before.zip.read(part)==after.zip.read(part),'unrelated package part changed '+part)
    for ev in plan['expected']:
        root=E.fromstring(after.zip.read(after.sheets[ev['sheet']]));cell=next(c for c in root.iter(native.M+'c') if c.get('r')==ev['cell'])
        check(cell.findtext(native.M+'v')==str(ev['value']),ev['sheet']+'!'+ev['cell']+' numeric cache')
    if plan['new_sheet']:
        c,l=after.sheet(plan['new_sheet']);end=len(files)+6
        ids={c.get('E'+str(n),('',''))[1] for n in range(7,end+1)}
        check(ids==set(files),'new sheet current IDs differ')
        check({value[1] for ref,value in c.items() if re.fullmatch(r'E\d+',ref) and int(ref[1:])>=7}==set(files),'owned current index has stale residual file IDs')
        for n,r in enumerate(overlay,7):
            for col,k in [('A','name'),('E','file_id'),('F','folder_id'),('G','path'),('H','content_hash'),('L','scope')]:check(c.get(col+str(n),('',''))[1]==r[k],'current index mismatch '+col+str(n))
            for col,k,label in [('C','image_url','Image'),('D','folder_url','Folder')]:
                check(c.get(col+str(n))==('text',label) and l.get(col+str(n))==r[k],'current index link mismatch '+col+str(n))
        for cell,value in [('B4',len(files)),('D4',sum(r['scope']=='Wall Sculptures' for r in overlay)),('F4',sum(r['scope']=='Retained Workshop' for r in overlay))]:
            root=E.fromstring(after.zip.read(after.sheets[plan['new_sheet']]));cr=next(x for x in root.iter(native.M+'c') if x.get('r')==cell);check(cr.findtext(native.M+'v')==str(value),'current image count cache '+cell)
        root=E.fromstring(after.zip.read(after.sheets[plan['new_sheet']]));check(all(c.get('t')!='e' for c in root.iter(native.M+'c')),'new index formula error')
    wb_reports.append({'key':plan['key'],'output':plan['output'],'sha256':sha(plan['output']),'sheets':len(after.sheets),'declared_edits':len(planned),'native_hyperlinks':sum(len(after.sheet(sn)[1]) for sn in after.sheets)})
    before.close();after.close()

src=sqlite3.connect(Path(manifest['sources']['source_gallery']['snapshot']).as_uri()+'?mode=ro',uri=True)
new=sqlite3.connect((H/'gallery-projection/complete-image-platform-register.sqlite').as_uri()+'?mode=ro',uri=True)
tables=[r[0] for r in src.execute("SELECT name FROM sqlite_master WHERE type='table'")]
seal=read(H/'gallery-projection/sealed-handoff.json');history_map=seal['source_history_table_map']
for table in tables:
    if table in {'images','products','metadata'}:continue
    check(src.execute('SELECT * FROM '+table+' ORDER BY rowid').fetchall()==new.execute('SELECT * FROM '+history_map.get(table,table)+' ORDER BY rowid').fetchall(),'source table changed '+table)
check(src.execute('SELECT * FROM products ORDER BY product_id').fetchall()==new.execute('SELECT * FROM '+history_map['products']+' ORDER BY product_id').fetchall(),'source product records not retained')
for pid,raw in new.execute('SELECT product_id,record_json FROM products'):check(json.loads(raw)==options[pid],'current gallery product differs '+pid)
for fid,raw in src.execute('SELECT file_id,record_json FROM images'):
    before=json.loads(raw);after=json.loads(new.execute('SELECT record_json FROM images WHERE file_id=?',(fid,)).fetchone()[0]);nav={'name','folder_id','path','image_url','folder_url','in_wall_sculpture_tree','native_navigation_history','current_native_evidence','publication_native_availability'}
    for k in set(before)|set(after):
        if k not in nav:check(before.get(k)==after.get(k),'source image evidence changed '+fid+' '+k)
    if fid in files:check(after['native_navigation_history'][:-1]==before.get('native_navigation_history',[]),'earlier image navigation history lost '+fid)
for fid,r in files.items():
    parent,path,raw=new.execute('SELECT folder_id,path,record_json FROM images WHERE file_id=?',(fid,)).fetchone();im=json.loads(raw)
    check(parent==r['folder_id'] and path==r['path'] and im['image_url']==r['image_url'] and im['folder_url']==r['folder_url'],'current gallery nav mismatch '+fid)
check(new.execute('PRAGMA integrity_check').fetchone()[0]=='ok','gallery integrity')
src.close();new.close()
seal=read(H/'gallery-projection/sealed-handoff.json')
check(seal['database_sha256']==sha(H/'gallery-projection/complete-image-platform-register.sqlite'),'gallery seal hash')
for p,d in seal['files'].items():check(sha(H/'gallery-projection'/p)==d,'reader hash '+p)
reader_paths=read(H/'current-reader-paths.json')
with (BASE/reader_paths['coverage']).open(newline='') as f:coverage=list(csv.DictReader(f))
check({r['product_id'] for r in coverage}==active,'coverage CSV active option coverage')
for r in coverage:
    o=options[r['product_id']]
    for k,source in [('primary_file_id','file_id'),('primary_folder_id','folder_id'),('primary_image','image_url'),('containing_folder','folder_url')]:check(r[k]==(o.get(source) or ''),'coverage CSV reference mismatch '+r['product_id']+' '+k)
with (BASE/reader_paths['field_checklist']).open(newline='') as f:fields=list(csv.DictReader(f))
check(len(fields)==1122,'working checklist row count')
for r in fields:
    value=options[r['product_id']]['master_fields'][r['field']]
    for k,source in [('working_value','display'),('state','state'),('basis','basis')]:check(r[k]==str(value.get(source,'')),'working checklist value mismatch '+r['product_id']+' '+r['field'])
package=Book(read(H/'workbook-edit-plan.json')['plans'][1]['output'])
with (BASE/reader_paths['active_series_requests_csv']).open(newline='') as f:series_rows=list(csv.DictReader(f))
check(len(series_rows)==3 and {r['product_id'] for r in series_rows}==set(read(H/'register-preparation.json')['new_series_losses']),'three current series replacements not represented')
check('<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"' in package.zip.read('[Content_Types].xml').decode(),'native package Content Types root');package.close()

result={'status':'PASS_INDEPENDENT_PUBLICATION_READBACK' if not errors else 'FAIL_PUBLICATION_READBACK','checks':checks,'active_options':187,'retained_options':189,'current_scoped_files':len(files),'source_assertions_preserved':1668,'physical_specification_identity_price_stock_or_platform_changes':0,'workbooks':wb_reports,'gallery_database_sha256':seal['database_sha256'],'errors':errors,'native_platform_or_live_app_writes':0}
write(H/'independent-verification.json',result)
print(json.dumps({k:v for k,v in result.items() if k not in {'workbooks'}},indent=2))
raise SystemExit(bool(errors))
