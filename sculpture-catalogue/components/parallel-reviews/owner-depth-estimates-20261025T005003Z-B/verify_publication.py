"""Verify a published depth-only update against the prepared packet and baseline."""
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET
import csv
import argparse
import hashlib
import json
import posixpath
import re
import zipfile

H=Path(__file__).resolve().parent
B=H.parents[2]
read=lambda p:json.loads(Path(p).read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
packet=read(H/'depth-estimate-packet.json')
p=read(B/'current-master.json')
parser=argparse.ArgumentParser()
parser.add_argument('--candidate-register')
parser.add_argument('--candidate-workbook')
parser.add_argument('--register-sha256')
parser.add_argument('--workbook-sha256')
args=parser.parse_args()
candidate=bool(args.candidate_register)
if candidate:
    assert args.candidate_workbook and args.register_sha256 and args.workbook_sha256
    rp=Path(args.candidate_register);wp=Path(args.candidate_workbook)
    p['register_sha256']=args.register_sha256;p['workbook_sha256']=args.workbook_sha256
else:
    rp=B/p['register'];wp=B/p['workbook']
if not candidate and p['register_sha256']==packet['base_register']['sha256']:
    print(json.dumps({'status':'PUBLICATION_PENDING','current_register_sha256':p['register_sha256']}))
    raise SystemExit(2)
r=read(rp);before=read(packet['base_register']['path'])
old={o['product_id']:o for o in before['options']};new={o['product_id']:o for o in r['options']}
targets={x['product_id']:x for x in packet['rows']}
checks=[]
def check(value,label):checks.append({'passed':bool(value),'check':label})
check(sha(rp)==p['register_sha256'],'Register matches the supplied frozen hash')
check(sha(wp)==p['workbook_sha256'],'Workbook matches the supplied frozen hash')
check(set(new)==set(old),'Every retained option ID preserved')
check(r['active_option_ids']==before['active_option_ids'],'Active option population and order preserved')
check(r['retired_option_ids']==before['retired_option_ids'],'Retired population preserved')
changed=[]
for pid,o in old.items():
    n=new[pid]
    for field,old_field in o['master_fields'].items():
        current=n['master_fields'][field]
        if current!=old_field:changed.append((pid,field))
        if pid in targets and field=='Dimensions / depth':
            expected=targets[pid]['after']
            for key in ['display','state','basis','working_recorded','physical_verification','depth_estimate']:
                check(current.get(key)==expected.get(key),pid+' requested '+key+' published')
        else:
            check(current==old_field,pid+' '+field+' unchanged')
    for field in ['name','canonical_component_id','canonical_design_id','source_scopes','image_url','folder_url','file_id','folder_id','context_image_url','context_folder_url','photo_coverage','selling_details','current_commercial_policy','offered_fixing_choices','specifications']:
        check(n.get(field)==o.get(field),pid+' '+field+' unchanged')
    check(n.get('physical_specifications_verified')==o.get('physical_specifications_verified'),pid+' physical-verification flag unchanged')
check(set(changed)=={(pid,'Dimensions / depth') for pid in targets},'Exactly 14 dimension/depth field objects changed')

NS={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
RID='{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id'
def load_book(path):
    sheets={}
    with zipfile.ZipFile(path) as z:
        strings=[]
        if 'xl/sharedStrings.xml' in z.namelist():strings=[''.join(t.text or '' for t in si.iter('{'+NS['s']+'}t')) for si in ET.fromstring(z.read('xl/sharedStrings.xml'))]
        rels={x.get('Id'):x.get('Target') for x in ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))}
        for sheet in ET.fromstring(z.read('xl/workbook.xml')).find('s:sheets',NS):
            target=rels[sheet.get(RID)];part=target.lstrip('/') if target.startswith('/') else posixpath.normpath('xl/'+target)
            rows={};formulas={};errors=[]
            for row in ET.fromstring(z.read(part)).findall('s:sheetData/s:row',NS):
                cells={}
                for cell in row:
                    addr=cell.get('r');v=cell.find('s:v',NS);value=v.text if v is not None else ''
                    if cell.get('t')=='s' and value:value=strings[int(value)]
                    elif cell.get('t')=='inlineStr':value=''.join(t.text or '' for t in cell.findall('.//s:t',NS))
                    f=cell.find('s:f',NS)
                    if f is not None:formulas[addr]=f.text
                    if cell.get('t')=='e':errors.append((addr,value))
                    cells[re.sub(r'\d','',addr)]=value
                rows[int(row.get('r'))]=cells
            sheets[sheet.get('name')]={'rows':rows,'formulas':formulas,'errors':errors}
    return sheets
book=load_book(wp);old_book=load_book(H/'inputs/master-workbook.before.xlsx')
check(list(book)==list(old_book),'All workbook tabs and order retained')
for name,sheet in book.items():
    check(sheet['formulas']==old_book[name]['formulas'],name+' formulas unchanged')
    check(not sheet['errors'],name+' has no saved formula-error values')
spec_rows={(row.get('A'),row.get('C')):(rn,row) for rn,row in book['Specifications']['rows'].items() if row.get('A') in new}
master_rows={row.get('A'):(rn,row) for rn,row in book['Master Catalogue']['rows'].items() if row.get('A') in new}
for pid,option in new.items():
    if pid in r['retired_option_ids']:
        # Retired rows intentionally display their retirement status rather than
        # the historical field state. Require exact baseline preservation.
        for field in option['master_fields']:
            rn,row=spec_rows[(pid,field)]
            check(row==old_book['Specifications']['rows'][rn],pid+' '+field+' retired history preserved')
        rn,row=master_rows[pid]
        check(row==old_book['Master Catalogue']['rows'][rn],pid+' retired master placeholders preserved')
        continue
    for field,mf in option['master_fields'].items():
        rn,row=spec_rows[(pid,field)]
        check(row.get('D')==mf['display'],pid+' '+field+' saved workbook value matches register')
        check(row.get('E')==mf['state'],pid+' '+field+' saved workbook qualification matches')
    rn,row=master_rows[pid]
    for col,field in zip('EFGHIJ',['Dimensions / depth','Weight','Material / finish','Fixing','Individual price','Availability']):
        check(row.get(col)==option['master_fields'][field]['display'],pid+' '+field+' master formula result matches')
if candidate:
    failures=[c for c in checks if not c['passed']]
    result={'status':'PASS_CANDIDATE_CORE_CHECKS' if not failures else 'FAIL_CANDIDATE_CORE_CHECKS','checked_utc':datetime.now(timezone.utc).isoformat(),'candidate_register':str(rp),'candidate_register_sha256':sha(rp),'candidate_workbook':str(wp),'candidate_workbook_sha256':sha(wp),'checks_passed':len(checks)-len(failures),'checks_failed':len(failures),'failures':failures,'field_changes':changed,'other_1120_field_objects_unchanged':len(changed)==14,'current_publication_performed':False,'pending_checks':['Published pointer and final files','Published field and physical-input checklists','Current gallery projection binding']}
    dest=H/('candidate-readback-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'.json')
    dest.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({**result,'result_path':str(dest)},ensure_ascii=False,indent=2))
    raise SystemExit(1 if failures else 0)
with (B/p['current_specification_verification']['field_checklist']).open(encoding='utf-8-sig',newline='') as f:checklist=list(csv.DictReader(f))
check(len(checklist)==1128,'Current field checklist retains 1,128 rows')
for row in checklist:
    check(row['working_display']==new[row['option_id']]['master_fields'][row['field']]['display'],'Field checklist matches '+row['option_id']+' '+row['field'])
with (B/p['current_specification_verification']['actual_physical_measurement_input']).open(encoding='utf-8-sig',newline='') as f:measurement=list(csv.DictReader(f))
check(len(measurement)==188,'Physical input retains 188 rows')
for row in measurement:
    if row['option_id'] in targets:check(row['current_working_dimensions']==targets[row['option_id']]['after']['display'],'Measurement input working depth updated '+row['option_id'])
    for col in ['actual_width_cm','actual_height_cm','actual_maximum_depth_cm','bare_panel_measured_weight_kg','measurement_date','measured_or_inspected_by']:
        check(not row[col].strip(),'No invented '+col+' for '+row['option_id'])

current_projection=p.get('current_published_gallery_projection',{})
check(current_projection.get('register_sha256')==p['register_sha256'],'Current gallery projection bound to updated register')
check(current_projection.get('workbook_sha256')==p['workbook_sha256'],'Current gallery projection bound to updated workbook')
for key in ['physical_stock_quantity','whole_library_unique_design_total','all_actual_specifications_complete']:
    check(p.get(key)==read(H/'inputs/current-master.before.json').get(key),key+' is not upgraded by estimated depths')
failure=[c for c in checks if not c['passed']]
result={'status':'PASS' if not failure else 'FAIL','checked_utc':datetime.now(timezone.utc).isoformat(),'published_pointer_sha256':sha(B/'current-master.json'),'published_register':str(rp),'published_register_sha256':sha(rp),'published_workbook':str(wp),'published_workbook_sha256':sha(wp),'checks_passed':len(checks)-len(failure),'checks_failed':len(failure),'failures':failure,'field_changes':changed,'depth_fields_added':len(targets),'physical_measurements_added':0,'canonical_writes_by_reviewer':False}
dest=H/('publication-readback-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'.json')
dest.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({**result,'result_path':str(dest)},ensure_ascii=False,indent=2))
