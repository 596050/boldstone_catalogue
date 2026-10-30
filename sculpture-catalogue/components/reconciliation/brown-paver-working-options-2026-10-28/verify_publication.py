"""Independent source, CSV, gallery and native-XLSX verification of the two additions."""
from common import *
from xml.etree import ElementTree as E
from decimal import Decimal
from datetime import datetime,timezone
import csv,re,sqlite3
checks=0;errors=[]
def check(ok,why):
    global checks
    checks+=1
    if not ok:errors.append(why)
original=read(manifest['sources']['register']['snapshot'])
new=read(H/'new-paver-options.json');newids={o['product_id'] for o in new}
check(g['options'][:-2]==original['options'],'Every prior option and specification must remain unchanged')
check(g['components'][:-2]==original['components'],'Every prior component must remain unchanged')
check(g['active_option_ids'][:-2]==original['active_option_ids'],'Old active ordering')
check(set(g['active_option_ids'][-2:])==newids,'New active option IDs')
allowed={'options','components','active_option_ids','summary','current_context_owner_hold_ids'}
for k in original:
    if k not in allowed:check(g[k]==original[k],'Unrelated register section changed: '+k)
check(set(g)-set(original)=={'owner_added_working_paver_assertions','latest_brown_paver_working_options','current_context_owner_hold_ids'},'New register sections')
check(len(active)==187 and len(g['options'])==191 and len(g['retired_option_ids'])==4,'Option counts')
check(len(g['components'])==114 and g['summary']['identified_component_identities']==112,'Provisional versus identified component counts')
check(g['summary']['current_field_groups']==1122 and len(g['original_review_specification_assertions'])==1668 and len(g['owner_added_working_paver_assertions'])==12,'Working versus original assertion counts')
for o in new:
    check(len(o['master_fields'])==6 and all(v['physical_verification']==0 and v['working_recorded']==1 for v in o['master_fields'].values()),o['name']+' labelled working fields')
    check(o['catalogue_image_reference_only'] and o['current_primary_selection']['status']=='UNSELECTED' and not o['listing_images_selected'],o['name']+' no automatic saved image approvals')
    check(not o['related_platform_offer_refs'] and not o['source_supported_platform_scope_refs'],o['name']+' no unproved SKU or platform link')
    check('AC730' not in o['master_fields']['Material / finish']['display'] and 'hypothesis' in o['master_fields']['Material / finish']['display'],o['name']+' no White material transfer')
    check(o['selling_details']['estimated_price']==225 and o['selling_details']['physical_stock_quantity'] is None,o['name']+' working price; unknown stock')
    check(o['visual_design_relationships'][0]['status']=='QUALIFIED_VISUAL_CORRESPONDENCE_ONLY',o['name']+' mould/design qualification')
check(g['current_context_owner_hold_ids'][-2:]==[o['product_id'] for o in new],'Standing context hold extended only to new options')

wb_reports=[]
for plan,receipt in zip(read(H/'workbook-edit-plan.json')['plans'],read(H/'native-preservation-receipt.json')['workbooks']):
    before,after=Book(plan['source']),Book(plan['output'])
    edits={(r['sheet'],r['cell']):r for r in plan['edits']}
    check(list(after.sheets)==list(before.sheets)+['Brown Paver Options'],'Workbook sheet names/order')
    check(sha(plan['output'])==receipt['output_sha256'],'Workbook seal')
    for sn in before.sheets:
        bc,bl=before.sheet(sn);ac,al=after.sheet(sn)
        for ref in set(bc)|set(ac):
            ed=edits.get((sn,ref))
            if not ed:check(bc.get(ref)==ac.get(ref),sn+'!'+ref+' undeclared cell')
            elif ed['kind']=='hyperlink':
                wanted=('formula',ed['formula'].lstrip('=')) if ed['keep_formula'] else ('text',ed['label'])
                check(ac.get(ref)==wanted,sn+'!'+ref+' wrong hyperlink label/formula')
                if not ed['keep_formula']:check(al.get(ref)==ed['url'],sn+'!'+ref+' wrong URL')
            elif ed['kind']=='formula':check(ac.get(ref)==('formula',ed['formula'].lstrip('=')),sn+'!'+ref+' formula')
            else:
                v=ed['value'];wanted=None if v in ('',None) else ('number',str(Decimal(str(v)).normalize())) if isinstance(v,(int,float)) else ('text',v)
                check(ac.get(ref)==wanted,sn+'!'+ref+' value')
        for ref in set(bl)|set(al):
            ed=edits.get((sn,ref));wanted=ed['url'] if ed and ed['kind']=='hyperlink' and (not ed['keep_formula'] or ref in bl) else bl.get(ref)
            check(al.get(ref)==wanted,sn+'!'+ref+' undeclared link')
        a,b=[E.fromstring(book.zip.read(book.sheets[sn])) for book in [before,after]]
        for tag in ['cols','mergeCells','conditionalFormatting','dataValidations','tableParts','sheetViews']:
            check([E.tostring(x) for x in a.findall(native.M+tag)]==[E.tostring(x) for x in b.findall(native.M+tag)],sn+' native feature '+tag)
        for cell in b.iter(native.M+'c'):check(cell.get('t')!='e',sn+'!'+cell.get('r','')+' formula error')
        source_row_numbers={r.get('r') for r in a.iter(native.M+'row')}
        for row in b.iter(native.M+'row'):
            cols=[re.match(r'[A-Z]+',c.get('r'))[0] for c in row if c.tag==native.M+'c']
            colnum=lambda s:sum((ord(ch)-64)*26**i for i,ch in enumerate(s[::-1]))
            # Existing native source order is preserved; new rows use valid numeric column order.
            if row.get('r') not in source_row_numbers:check(cols==sorted(cols,key=colnum),sn+' appended column order')
    for part in before.zip.namelist():
        if part not in receipt['modified_existing_parts']:check(before.zip.read(part)==after.zip.read(part),'Unrelated native part '+part)
    for exp in plan['table_expansions']:
        sp=after.sheets[exp['sheet']];rp=str(Path(sp).parent/'_rels'/(Path(sp).name+'.rels'))
        t=next(E.fromstring(after.zip.read(native.resolve(sp,r.get('Target')))) for r in E.fromstring(after.zip.read(rp)) if r.get('Type').endswith('/table'))
        check(t.get('name')==exp['name'] and t.get('ref')==exp['range'],'Expanded native table '+exp['sheet'])
    for expected in plan['expected']:
        tree=E.fromstring(after.zip.read(after.sheets[expected['sheet']]))
        cell=next(c for c in tree.iter(native.M+'c') if c.get('r')==expected['cell'])
        check(cell.findtext(native.M+'v')==str(expected['value']),expected['sheet']+'!'+expected['cell']+' cached count')
    cells,links=after.sheet('Brown Paver Options');rows=read(H/'paver-evidence-rows.json')
    for n,r in enumerate(rows,8):
        for col,key in [('A','kind'),('B','id'),('C','name'),('D','value'),('G','qualification')]:check(cells.get(col+str(n))==('text',r[key]),'Brown evidence '+col+str(n))
        for col,key,label in [('E','image','Image'),('F','folder','Folder')]:check(cells.get(col+str(n))==('text',label) and links.get(col+str(n))==r[key],'Brown evidence link '+col+str(n))
    check('<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"' in after.zip.read('[Content_Types].xml').decode(),'Native Content Types namespace')
    # Both workbook views must contain the exact two native IDs and no invented SKU.
    if plan['key']=='core_workbook':
        c,_=after.sheet('Master Catalogue')
        for i,o in enumerate(new,199):
            check(c['A'+str(i)]==('text',o['product_id']) and c['Q'+str(i)]==('text',o['file_id']) and c['R'+str(i)]==('text',o['folder_id']),'Core stable IDs')
    else:
        c,_=after.sheet('Products')
        for i,o in enumerate(new,195):
            check(c['A'+str(i)]==('text',o['product_id']) and c['Z'+str(i)]==('text',o['file_id']),'Unified stable IDs')
            check(all(c.get(col+str(i)) is None for col in ['Q','R','S','T','U','V']),'Unified no fabricated platform/SKU')
    wb_reports.append({'key':plan['key'],'output':plan['output'],'sha256':sha(plan['output']),'sheets':len(after.sheets),'declared_edits':len(edits),'paver_evidence_rows':len(rows),'native_hyperlinks':sum(len(after.sheet(sn)[1]) for sn in after.sheets)})
    before.close();after.close()

source=sqlite3.connect(Path(manifest['sources']['source_gallery']['snapshot']).as_uri()+'?mode=ro',uri=True)
db=sqlite3.connect((H/'gallery-projection/complete-image-platform-register.sqlite').as_uri()+'?mode=ro',uri=True)
adds=read(H/'association-additions.json')
for (table,) in source.execute("SELECT name FROM sqlite_master WHERE type='table'"):
    if table in {'products','metadata'}:continue
    a=source.execute('SELECT * FROM '+table+' ORDER BY rowid').fetchall();b=db.execute('SELECT * FROM '+table+' ORDER BY rowid').fetchall()
    if table=='associations':
        check(b[:len(a)]==a,'Old association rows')
        extra=b[len(a):];check(len(extra)==2 and {r[0] for r in extra}==set(adds['added_association_ids']),'Two source reference edges only')
        for r in extra:check(r[1] in newids and r[3]=='selected_working_reference' and r[4]=='CURRENT_QUALIFIED_WORKING_APPEARANCE_REFERENCE','No Listing/Primary edge')
    else:check(a==b,'Source table drift '+table)
check(source.execute('SELECT * FROM products ORDER BY product_id').fetchall()==db.execute('SELECT * FROM products_before_brown_paver_working_options_20261028 ORDER BY product_id').fetchall(),'Preserved source product history')
for pid,raw in db.execute('SELECT product_id,record_json FROM products'):check(json.loads(raw)==options[pid],'Projected product '+pid)
oldmeta=dict(source.execute('SELECT * FROM metadata'));newmeta=dict(db.execute('SELECT * FROM metadata'))
for key,val in oldmeta.items():
    if key!='current_navigation_publication':check(newmeta[key]==val,'Source metadata drift '+key)
check(set(newmeta)-set(oldmeta)=={'navigation_before_brown_paver_additions_20261028','brown_paver_working_option_admission_20261028'},'Metadata addition scope')
check(db.execute('PRAGMA integrity_check').fetchone()[0]=='ok','Gallery integrity');source.close();db.close()
seal=read(H/'gallery-projection/sealed-handoff.json')
check(seal['database_sha256']==sha(H/'gallery-projection/complete-image-platform-register.sqlite') and seal['register_sha256']==sha(H/'canonical-master-register.json'),'Gallery/register seals')
check(seal['source_history_table_map']['products']=='products_before_brown_paver_working_options_20261028','Gallery history metadata')
for name,digest in seal['files'].items():check(sha(H/'gallery-projection'/name)==digest,'HTML seal '+name)
paths=read(H/'current-reader-paths.json')
readcsv=lambda key:list(csv.DictReader((BASE/paths[key]).open()))
check(len(readcsv('coverage'))==187 and len(readcsv('field_checklist'))==1122,'CSV active counts')
check(len(readcsv('new_working_primary_choices_csv'))==2 and len(readcsv('active_individual_requests_csv'))==5,'New choices distinguished from existing requests')
check(len(readcsv('held_in_situ_cases_csv'))==30 and len(readcsv('active_series_requests_csv'))==0,'Held/optional photography')
summary=read(BASE/paths['count_summary'])
check(summary['retired_option_ids']==g['retired_option_ids'] and summary['retained_component_identity_rows']==114 and summary['active_component_ids_including_provisional']==113,'Count summary identity lists and provisional counts')
for r in readcsv('coverage'):
    if r['product_id'] in newids:check(not r['primary_file_id'] and not r['primary_image'] and bool(r['individual_reference_image']),'CSV reference is not selected Primary')
for record in manifest['sources'].values():check(sha(record['snapshot'])==record['sha256'],'Immutable input drift '+record['snapshot'])
result={'status':'PASS_INDEPENDENT_PUBLICATION_READBACK' if not errors else 'FAIL','checked_utc':datetime.now(timezone.utc).isoformat(),'checks':checks,'errors':errors[:40],'workbooks':wb_reports,'active_options':187,'retained_options':191,'retired_options':4,'working_fields':1122,'new_working_fields':12,'original_assertions_preserved':1668,'prior_option_records_unchanged':189,'prior_component_records_unchanged':112,'new_source_reference_edges':2,'new_primary_listing_or_advertising_approvals':0,'new_platform_or_sku_links':0,'new_physical_verifications':0,'unrelated_pending_imports_applied':False,'native_app_or_platform_writes':0}
write(H/'independent-verification.json',result)
print(json.dumps({k:v for k,v in result.items() if k!='workbooks'},ensure_ascii=False))
assert not errors,errors[:12]
