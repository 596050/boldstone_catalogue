"""Independent exact-scope canonical, source-gallery and native-XLSX verification."""
from common import *
from xml.etree import ElementTree as E
from decimal import Decimal
import csv,re,sqlite3
checks=0;errors=[]
def check(ok,why):
    global checks
    checks+=1
    if not ok:errors.append(why)
KEEP='BSI-9299D69FEF08';DUP='BSI-4536FDCA0DA9'
original=read(manifest['sources']['register']['snapshot']);prior={r['product_id']:r for r in original['options']}
allowed_keep={'name','retained_names','source_scopes','related_platform_offer_refs','source_supported_platform_scope_refs','file_id','folder_id','image_url','folder_url','current_primary_selection','current_saved_listing_images','photo_coverage','owner_duplicate_consolidations','merged_duplicate_reference_qualifications','merged_source_platform_scope'}
allowed_old={'counted_as_individual_option','count_class','catalogue_retirement','photo_coverage'}
for before,after in zip(original['options'],g['options']):
    pid=before['product_id'];check(pid==after['product_id'],'option row order')
    allow=allowed_keep if pid==KEEP else allowed_old if pid==DUP else set()
    for k in set(before)|set(after):
        if k not in allow:check(before.get(k)==after.get(k),pid+' unauthorised field '+k)
    check(before['specifications']==after['specifications'] and before.get('master_fields')==after.get('master_fields'),pid+' working/source specifications changed')
allowed_top={'options','active_option_ids','retired_option_ids','catalogue_retirements','latest_catalogue_retirement','aliases','summary'}
for k in original:
    if k not in allowed_top:check(g[k]==original[k],'unrelated top-level change '+k)
check(set(g)-set(original)=={'latest_dune_ripple_duplicate_consolidation'},'new register section scope')
check(g['active_option_ids']==[x for x in original['active_option_ids'] if x!=DUP],'active option scope')
check(g['retired_option_ids']==original['retired_option_ids']+[DUP],'retirement history scope')
check(g['aliases'][:-1]==original['aliases'] and g['aliases'][-1]['targets']==[KEEP],'alias history')
check(g['catalogue_retirements'][:-1]==original['catalogue_retirements'],'retirement evidence history')
check(len(active)==185 and len(g['options'])==189 and len(g['retired_option_ids'])==4,'record counts')
check(g['summary']['current_field_groups']==1110 and len(g['original_review_specification_assertions'])==1668,'field and assertion counts')
check(set(options[KEEP]['source_scopes'])==set(prior[KEEP]['source_scopes'])|set(prior[DUP]['source_scopes']),'source scopes union')
check('O009' in options[KEEP]['related_platform_offer_refs'],'O009 source lost')
check(options[KEEP]['file_id']=='id:cnqzTNngPVsAAAAAAAyegw' and len(options[KEEP]['current_saved_listing_images'])==2,'keeper Primary/listing scope')
check({r['file_id'] for r in options[KEEP]['merged_duplicate_reference_qualifications']}=={'id:cnqzTNngPVsAAAAAAAyegw','id:cnqzTNngPVsAAAAAAAykxw'},'accepted reference scope')
wb_reports=[]
for plan,receipt in zip(read(H/'workbook-edit-plan.json')['plans'],read(H/'native-preservation-receipt.json')['workbooks']):
    before,after=Book(plan['source']),Book(plan['output'])
    edits={(r['sheet'],r['cell']):r for r in plan['edits']}
    check(list(after.sheets)==list(before.sheets)+['Dune Ripple Merge'],'sheet names/order drift')
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
    cells,links=after.sheet('Dune Ripple Merge');rows=read(H/'merge-evidence-rows.json')
    for n,r in enumerate(rows,8):
        for col,key in [('A','kind'),('B','id'),('C','name'),('D','value'),('G','qualification')]:check(cells.get(col+str(n))==('text',r[key]),'merge evidence '+col+str(n))
        for col,key,label in [('E','image','Image'),('F','folder','Folder')]:
            if r[key]:check(cells.get(col+str(n))==('text',label) and links.get(col+str(n))==r[key],'merge evidence link '+col+str(n))
            else:check(cells.get(col+str(n)) is None and (col+str(n)) not in links,'unexpected merge link '+col+str(n))
    check('<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"' in after.zip.read('[Content_Types].xml').decode(),'Content Types namespace')
    wb_reports.append({'key':plan['key'],'output':plan['output'],'sha256':sha(plan['output']),'sheets':len(after.sheets),'declared_edits':len(edits),'merge_evidence_rows':len(read(H/'merge-evidence-rows.json')),'native_hyperlinks':sum(len(after.sheet(sn)[1]) for sn in after.sheets)})
    before.close();after.close()

source=sqlite3.connect(Path(manifest['sources']['source_gallery']['snapshot']).as_uri()+'?mode=ro',uri=True)
db=sqlite3.connect((H/'gallery-projection/complete-image-platform-register.sqlite').as_uri()+'?mode=ro',uri=True)
union=read(H/'association-union.json')
for (table,) in source.execute("SELECT name FROM sqlite_master WHERE type='table'"):
    if table in {'products','metadata'}:continue
    a=source.execute('SELECT * FROM '+table+' ORDER BY rowid').fetchall();b=db.execute('SELECT * FROM '+table+' ORDER BY rowid').fetchall()
    if table in {'associations','source_product_links'}:
        check(b[:len(a)]==a,'original source rows changed '+table)
        extra=b[len(a):]
        if table=='associations':
            check(len(extra)==2 and {r[0] for r in extra}==set(union['added_association_ids']),'accepted reference additions')
            for r in extra:
                data=__import__('json').loads(r[5]);check(r[1]==KEEP and r[2] in union['accepted_reference_ids'] and data['merged_from_option_id']==DUP,'wrong accepted reference edge')
                check(r[4] in {'CURRENT_ACCEPTED_REFERENCE','CURRENT_QUALIFIED_CONTEXT_REFERENCE'},'unexpected candidate promotion')
        else:
            check(len(extra)==len(union['qualified_platform_offer_links']) and {r[0] for r in extra}==set(union['qualified_platform_offer_links']),'qualified platform union')
            for r in extra:check(r[1]==KEEP and __import__('json').loads(r[3])['merged_from_option_id']==DUP,'wrong merged platform edge')
    else:check(a==b,'source table drift '+table)
check(source.execute('SELECT * FROM products ORDER BY product_id').fetchall()==db.execute('SELECT * FROM products_before_dune_ripple_alias_20261028 ORDER BY product_id').fetchall(),'product source history')
for pid,raw in db.execute('SELECT product_id,record_json FROM products'):check(__import__('json').loads(raw)==options[pid],'projected product '+pid)
check(db.execute('PRAGMA integrity_check').fetchone()[0]=='ok','gallery integrity');source.close();db.close()
seal=read(H/'gallery-projection/sealed-handoff.json');check(seal['database_sha256']==sha(H/'gallery-projection/complete-image-platform-register.sqlite'),'gallery seal')
for name,digest in seal['files'].items():check(sha(H/'gallery-projection'/name)==digest,'reader seal '+name)
paths=read(H/'current-reader-paths.json')
with (BASE/paths['coverage']).open() as f:rows=list(csv.DictReader(f))
check(len(rows)==185 and {r['product_id'] for r in rows}==active,'active coverage rows')
with (BASE/paths['field_checklist']).open() as f:rows=list(csv.DictReader(f))
check(len(rows)==1110,'active working field count')
for r in rows:
    v=options[r['product_id']]['master_fields'][r['field']]
    for col,k in [('working_value','display'),('state','state'),('basis','basis')]:check(r[col]==str(v.get(k,'')),'active field drift '+r['product_id']+' '+r['field'])
with (BASE/paths['active_individual_requests_csv']).open() as f:rows=list(csv.DictReader(f))
check(len(rows)==5 and not {KEEP,DUP}&{r['product_id'] for r in rows},'five scoped Primary requests')
with (BASE/paths['listing_use_exclusions_csv']).open() as f:rows=list(csv.DictReader(f))
check(len(rows)==91,'prior policy source preserved')
result={'status':'PASS_INDEPENDENT_PUBLICATION_READBACK' if not errors else 'FAIL_PUBLICATION_READBACK','checks':checks,'errors':errors,'active_options':185,'retained_options':189,'retired_options':4,'working_field_groups':1110,'source_assertions_preserved':1668,'keeper_specs_and_reviews_preserved':True,'qualified_reference_edges_added':2,'qualified_platform_source_links_added':len(union['qualified_platform_offer_links']),'unrelated_pending_imports_applied':False,'workbooks':wb_reports,'gallery_database_sha256':seal['database_sha256'],'native_app_or_platform_writes':0}
write(H/'independent-verification.json',result);print(__import__('json').dumps({k:v for k,v in result.items() if k!='workbooks'},indent=2));raise SystemExit(bool(errors))
