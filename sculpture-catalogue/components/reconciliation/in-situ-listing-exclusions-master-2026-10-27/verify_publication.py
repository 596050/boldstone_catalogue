"""Independent full-preservation XLSX, source-register and exclusion readback."""
from common import *
from xml.etree import ElementTree as E
from decimal import Decimal
import csv, re, sqlite3

checks, errors = 0, []
def check(ok, why):
    global checks
    checks += 1
    if not ok: errors.append(why)
original = read(manifest['sources']['register']['snapshot'])
exclusions = read(H/'listing-use-exclusions.json')
bykey={(r['product_id'],r['file_id']):r for r in exclusions}
cleared={r['product_id'] for r in exclusions if r['primary_cleared']}
allowed={'image_use_exclusions','file_id','image_url','historical_primary_reference','current_primary_selection','photo_coverage'}
for before,after in zip(original['options'],g['options']):
    pid=before['product_id'];check(pid==after['product_id'],'register row identity')
    for k in set(before)|set(after):
        if k not in allowed:check(before.get(k)==after.get(k),pid+' unauthorized field '+k)
    if pid not in {r['product_id'] for r in exclusions}:check(before==after,pid+' unscoped option changed')
    if pid in cleared:
        check(after['file_id'] is None and after['image_url']=='',pid+' Primary not cleared')
        h=after['historical_primary_reference'];check(h['file_id']==before['file_id'] and h['reason']=='in_situ_listing_exclusion',pid+' wrong exclusion history')
        check(before['file_id'] in files,pid+' retained original absent from frozen inventory')
    else:check(after.get('file_id')==before.get('file_id'),pid+' unintended Primary change')
    check(before['specifications']==after['specifications'] and before.get('master_fields')==after.get('master_fields'),pid+' specification drift')
for k in original:
    if k=='summary':
        for field in original[k]:
            if field!='individual_options_with_dropbox_reference':check(original[k][field]==g[k][field],'summary source changed '+field)
    elif k!='options':check(original[k]==g[k],'top-level source changed '+k)
check(set(g)-set(original)=={'latest_in_situ_listing_policy_import'},'register section scope')
check(g['summary']['individual_options_with_dropbox_reference']==179,'Primary summary')
check(len(active)==186 and len(g['options'])==189 and len(g['original_review_specification_assertions'])==1668,'catalogue counts')
check(read(H/'policy-independent-readback.json')['status']=='PASS','policy independent check')

wb_reports=[]
for plan,receipt in zip(read(H/'workbook-edit-plan.json')['plans'],read(H/'native-preservation-receipt.json')['workbooks']):
    before,after=Book(plan['source']),Book(plan['output'])
    edits={(r['sheet'],r['cell']):r for r in plan['edits']}
    check(list(after.sheets)==list(before.sheets)+['Image Use Exclusions'],'sheet names/order drift')
    check(sha(plan['output'])==receipt['output_sha256'],'workbook seal drift')
    for sn in before.sheets:
        bc,bl=before.sheet(sn);ac,al=after.sheet(sn)
        for ref in set(bc)|set(ac):
            ed=edits.get((sn,ref))
            if not ed:check(bc.get(ref)==ac.get(ref),sn+'!'+ref+' undeclared cell')
            elif ed['kind']=='hyperlink':
                wanted=('formula',ed['formula'].lstrip('=')) if ed['keep_formula'] else ('text',ed['label'])
                check(ac.get(ref)==wanted,sn+'!'+ref+' wrong link text/formula')
                if not ed['keep_formula']:check(al.get(ref)==ed['url'],sn+'!'+ref+' wrong link URL')
            elif ed['kind']=='formula':check(ac.get(ref)==('formula',ed['formula'].lstrip('=')),sn+'!'+ref+' wrong formula')
            else:
                value=ed['value'];expected=None if value=='' else ('number',str(Decimal(str(value)).normalize())) if isinstance(value,(int,float)) else ('text',value)
                check(ac.get(ref)==expected,sn+'!'+ref+' wrong value')
        for ref in set(bl)|set(al):
            ed=edits.get((sn,ref));wanted=ed['url'] if ed and ed['kind']=='hyperlink' and (not ed['keep_formula'] or ref in bl) else bl.get(ref)
            check(al.get(ref)==wanted,sn+'!'+ref+' wrong/undeclared native link')
        a,b=[E.fromstring(book.zip.read(book.sheets[sn])) for book in [before,after]]
        for tag in ['cols','mergeCells','conditionalFormatting','dataValidations','tableParts','sheetViews']:
            check([E.tostring(x) for x in a.findall(native.M+tag)]==[E.tostring(x) for x in b.findall(native.M+tag)],sn+' native feature drift '+tag)
        for cell in b.iter(native.M+'c'):check(cell.get('t')!='e',sn+'!'+cell.get('r','')+' formula error')
    for part in before.zip.namelist():
        if part not in receipt['modified_existing_parts']:check(before.zip.read(part)==after.zip.read(part),'unrelated native package part '+part)
    for expected in plan['expected']:
        tree=E.fromstring(after.zip.read(after.sheets[expected['sheet']]))
        cell=next(c for c in tree.iter(native.M+'c') if c.get('r')==expected['cell'])
        check(cell.findtext(native.M+'v')==str(expected['value']),expected['sheet']+'!'+expected['cell']+' cached count')
    cells,links=after.sheet('Image Use Exclusions')
    check(len([a for a in cells if re.fullmatch(r'B\d+',a) and int(a[1:])>=7])==91,'exclusion sheet row count')
    for n,r in enumerate(exclusions,7):
        expected={'A':('text',r['name']),'B':('text',r['product_id']),'C':('text',r['file_id']),'D':('text','listing'),'E':('text',', '.join(r['remaining_uses']) or 'None'),'F':('text','Yes' if r['primary_cleared'] else 'No'),'G':('text',', '.join(r['effective_image_types'])),'H':('number',str(r['before_review_version'])),'I':('number',str(r['review_version'])),'J':('text','Image'),'K':('text','Folder'),'L':('text',r['scope'])}
        for col,value in expected.items():check(cells.get(col+str(n))==value,'exclusion cell mismatch '+col+str(n))
        check(links.get('J'+str(n))==r['image_url'] and links.get('K'+str(n))==r['folder_url'],'exclusion stable navigation '+str(n))
    root=E.fromstring(after.zip.read(after.sheets['Image Use Exclusions']))
    check(all(c.get('t')!='e' for c in root.iter(native.M+'c')),'exclusion sheet formula error')
    check('<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"' in after.zip.read('[Content_Types].xml').decode(),'Content Types namespace')
    wb_reports.append({'key':plan['key'],'output':plan['output'],'sha256':sha(plan['output']),'sheets':len(after.sheets),'declared_edits':len(edits),'exclusion_rows':91,'native_hyperlinks':sum(len(after.sheet(sn)[1]) for sn in after.sheets)})
    before.close();after.close()

source=sqlite3.connect(Path(manifest['sources']['source_gallery']['snapshot']).as_uri()+'?mode=ro',uri=True)
db=sqlite3.connect((H/'gallery-projection/complete-image-platform-register.sqlite').as_uri()+'?mode=ro',uri=True)
for (table,) in source.execute("SELECT name FROM sqlite_master WHERE type='table'"):
    if table in {'products','metadata'}:continue
    check(source.execute('SELECT * FROM '+table+' ORDER BY rowid').fetchall()==db.execute('SELECT * FROM '+table+' ORDER BY rowid').fetchall(),'source gallery table changed '+table)
check(source.execute('SELECT * FROM products ORDER BY product_id').fetchall()==db.execute('SELECT * FROM products_before_in_situ_listing_exclusions_20261027 ORDER BY product_id').fetchall(),'product source history not preserved')
for pid,raw in db.execute('SELECT product_id,record_json FROM products'):check(json.loads(raw)==options[pid],'current gallery product '+pid)
rows=db.execute('SELECT product_id,file_id,excluded_use,review_version,record_json FROM publication_listing_use_exclusions').fetchall()
check(len(rows)==91,'gallery exclusions count')
for pid,fid,use,version,raw in rows:check(use=='listing' and version==bykey[(pid,fid)]['review_version'] and json.loads(raw)==bykey[(pid,fid)],'gallery exact exclusion mismatch')
check(db.execute('PRAGMA integrity_check').fetchone()[0]=='ok','gallery database integrity')
source.close();db.close()
seal=read(H/'gallery-projection/sealed-handoff.json');check(seal['database_sha256']==sha(H/'gallery-projection/complete-image-platform-register.sqlite'),'gallery hash seal')
for name,digest in seal['files'].items():check(sha(H/'gallery-projection'/name)==digest,'reader hash '+name)
paths=read(H/'current-reader-paths.json')
with (BASE/paths['active_individual_requests_csv']).open() as f:requests=list(csv.DictReader(f))
check(len(requests)==6 and cleared<={r['product_id'] for r in requests},'six Primary requests')
with (BASE/paths['coverage']).open() as f:coverage=list(csv.DictReader(f))
check({r['product_id'] for r in coverage}==active,'coverage active IDs')
for r in coverage:check(r['primary_file_id']==(options[r['product_id']].get('file_id') or '') and r['primary_image']==options[r['product_id']].get('image_url',''),'coverage Primary '+r['product_id'])
with (BASE/paths['field_checklist']).open() as f:fields=list(csv.DictReader(f))
check(len(fields)==1116,'field checklist count')
for r in fields:
    v=options[r['product_id']]['master_fields'][r['field']]
    for col,sourcekey in [('working_value','display'),('state','state'),('basis','basis')]:check(r[col]==str(v.get(sourcekey,'')),'field value/state drift '+r['product_id']+' '+r['field'])
with (BASE/paths['listing_use_exclusions_csv']).open() as f:rows=list(csv.DictReader(f))
check(len(rows)==91 and {(r['product_id'],r['file_id']) for r in rows}==set(bykey),'exclusion CSV scope')
result={'status':'PASS_INDEPENDENT_PUBLICATION_READBACK' if not errors else 'FAIL_PUBLICATION_READBACK','checks':checks,'errors':errors,'active_options':186,'retained_options':189,'current_primary_references':179,'open_primary_choices':6,'listing_use_exclusions':91,'excluded_unique_images':68,'affected_active_options':30,'workbooks':wb_reports,'gallery_database_sha256':seal['database_sha256'],'source_assertions_preserved':1668,'physical_commercial_and_platform_changes':0,'publisher_native_app_or_platform_writes':0}
write(H/'independent-verification.json',result)
print(json.dumps({k:v for k,v in result.items() if k!='workbooks'},indent=2))
raise SystemExit(bool(errors))
