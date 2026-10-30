"""Independent read-only QA for the single Coral Spiral wording correction."""
from datetime import datetime,timezone
from pathlib import Path
from xml.etree import ElementTree as ET
import argparse,csv,hashlib,json,posixpath,re,zipfile

H=Path(__file__).resolve().parent
B=H.parents[2]
PID='BSI-0C2CB099DDEB'
FIELD='Dimensions / depth'
read=lambda p:json.loads(Path(p).read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
parser=argparse.ArgumentParser()
parser.add_argument('--register',required=True)
parser.add_argument('--workbook',required=True)
parser.add_argument('--register-sha256',required=True)
parser.add_argument('--workbook-sha256',required=True)
parser.add_argument('--published',action='store_true')
a=parser.parse_args()
rp=Path(a.register);wp=Path(a.workbook)
manifest=read(H/'input-manifest.json')
before=read(manifest['register']['snapshot_path']);after=read(rp)
old={x['product_id']:x for x in before['options']};new={x['product_id']:x for x in after['options']}
checks=[]
def check(ok,label):checks.append({'passed':bool(ok),'check':label})
check(sha(rp)==a.register_sha256,'Frozen register hash matches')
check(sha(wp)==a.workbook_sha256,'Frozen workbook hash matches')
check(set(old)==set(new),'All189 retained IDs preserved')
check(after['active_option_ids']==before['active_option_ids'],'All188 active IDs and order preserved')
check(after['retired_option_ids']==before['retired_option_ids'],'Retired option remains retired')
changes=[]
for pid,option in old.items():
    current=new[pid]
    check({k:v for k,v in option.items() if k!='master_fields'}=={k:v for k,v in current.items() if k!='master_fields'},pid+' nonfield data and original assertions unchanged')
    for field,mf in option['master_fields'].items():
        nm=current['master_fields'][field]
        if nm!=mf:changes.append((pid,field))
        if pid==PID and field==FIELD:
            expected=mf['display'].replace('unapproved guess','accepted working estimate, not physically verified')
            check(nm['display']==expected,'Only intended approval wording changed in Coral display')
            check(re.findall(r'\d+(?:\.\d+)?',nm['display'])==re.findall(r'\d+(?:\.\d+)?',mf['display']),'All numbers in Coral display unchanged')
            for k in set(mf)|set(nm):
                if k not in {'display','basis'}:check(nm.get(k)==mf.get(k),'Coral field '+k+' unchanged')
            check('unapproved' not in nm['basis'].lower(),'Coral basis no longer contradicts accepted working state')
            check('standing' in nm['basis'].lower() and 'not' in nm['basis'].lower(),'Basis preserves standing approval and explicit limitations')
            check(nm['physical_verification']==0,'Coral remains physically unverified')
        else:
            check(nm==mf,pid+' '+field+' unchanged')
check(changes==[(PID,FIELD)],'Exactly one of1134 retained field objects changed')

NS={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
RID='{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id'
def workbook(path):
    sheets={}
    with zipfile.ZipFile(path)as z:
        strings=[]
        if 'xl/sharedStrings.xml'in z.namelist():strings=[''.join(t.text or'' for t in e.iter('{'+NS['s']+'}t'))for e in ET.fromstring(z.read('xl/sharedStrings.xml'))]
        rels={x.get('Id'):x.get('Target')for x in ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))}
        for sh in ET.fromstring(z.read('xl/workbook.xml')).find('s:sheets',NS):
            target=rels[sh.get(RID)];part=target.lstrip('/')if target.startswith('/')else posixpath.normpath('xl/'+target)
            root=ET.fromstring(z.read(part));cells={};forms={};errors=[]
            for c in root.findall('s:sheetData/s:row/s:c',NS):
                v=c.find('s:v',NS);value=v.text if v is not None else ''
                if c.get('t')=='s'and value:value=strings[int(value)]
                if c.get('t')=='inlineStr':value=''.join(t.text or'' for t in c.findall('.//s:t',NS))
                f=c.find('s:f',NS)
                if f is not None:forms[c.get('r')]=f.text
                if c.get('t')=='e':errors.append((c.get('r'),value))
                cells[c.get('r')]=value or ''
            relpart=posixpath.dirname(part)+'/_rels/'+posixpath.basename(part)+'.rels'
            hyperlink_rels=[]
            if relpart in z.namelist():hyperlink_rels=sorted((x.get('Id'),x.get('Target'),x.get('TargetMode'))for x in ET.fromstring(z.read(relpart))if x.get('Type','').endswith('/hyperlink'))
            hyperlinks=[sorted(x.attrib.items())for x in root.findall('s:hyperlinks/s:hyperlink',NS)]
            sheets[sh.get('name')]={'cells':cells,'formulas':forms,'errors':errors,'hyperlink_rels':hyperlink_rels,'hyperlinks':hyperlinks}
    return sheets
oldbook=workbook(manifest['workbook']['snapshot_path']);book=workbook(wp)
check(list(book)==list(oldbook),'All28 workbook tabs and order preserved')
cell_changes=[]
allowed={('Specifications','D172'),('Specifications','F172'),('Master Catalogue','E37'),('Draft Listings','H21')}
for name,sheet in book.items():
    previous=oldbook[name]
    check(sheet['formulas']==previous['formulas'],name+' formulas unchanged')
    expected_links=previous['hyperlinks']
    if name=='Draft Listings':
        expected_links=[]
        for attrs in previous['hyperlinks']:
            link=dict(attrs)
            if link.get('ref')=='H21':
                link['display']=sheet['cells']['H21']
            expected_links.append(sorted(link.items()))
    check(sheet['hyperlink_rels']==previous['hyperlink_rels'] and sheet['hyperlinks']==expected_links,name+' all hyperlink targets unchanged; only corrected Coral display label allowed')
    check(not sheet['errors'],name+' no saved formula errors')
    for address in set(sheet['cells'])|set(previous['cells']):
        oldvalue=previous['cells'].get(address,'');value=sheet['cells'].get(address,'')
        if value!=oldvalue:
            cell_changes.append((name,address))
            check((name,address)in allowed,name+' '+address+' is an expected Coral cell')
        else:check(True,name+' '+address+' value unchanged')
check(set(cell_changes)==allowed,'Exactly3 authored cells and1 master result changed')
mf=new[PID]['master_fields'][FIELD]
check(book['Specifications']['cells']['D172']==mf['display'],'Saved Coral dimension display equals register')
check(book['Specifications']['cells']['F172']==mf['basis'],'Saved Coral basis equals register')
check(book['Master Catalogue']['cells']['E37']==mf['display'],'Saved master formula result equals corrected Coral display')
check(book['Draft Listings']['cells']['H21']==oldbook['Draft Listings']['cells']['H21'].replace(old[PID]['master_fields'][FIELD]['display'],mf['display']),'Draft description replaces only Coral dimension wording')
out=B/'outputs/coral-depth-wording-master-2026-10-25'
csv_paths=[out/'Specification_Verification_Checklist_1128_Fields.csv',out/'Current_Individual_Options_188.csv',out/'Physical_Verification_Input_188_Options.csv']
if all(p.exists()for p in csv_paths):
    def rows(path):
        with path.open(encoding='utf-8-sig',newline='')as f:return list(csv.DictReader(f))
    fieldrows=rows(csv_paths[0]);check(len(fieldrows)==1128,'1128 current field CSV rows')
    for row in fieldrows:
        current=new[row['option_id']]['master_fields'][row['field']]
        check(all(row[k]==current[v]for k,v in [('working_display','display'),('evidence_state','state'),('basis','basis')]),row['option_id']+' '+row['field']+' complete CSV field matches')
    options=rows(csv_paths[1]);check(len(options)==188,'188 current option CSV rows')
    for row in options:
        for field,current in new[row['option_id']]['master_fields'].items():check(row[field]==current['display'] and row[field+' evidence state']==current['state'],row['option_id']+' '+field+' option CSV matches')
    physical=rows(csv_paths[2]);check(len(physical)==188,'188 physical input rows')
    for row in physical:
        check(row['current_working_dimensions']==new[row['option_id']]['master_fields'][FIELD]['display'],row['option_id']+' physical input working dimensions match')
        for col in ['actual_width_cm','actual_height_cm','actual_maximum_depth_cm','bare_panel_measured_weight_kg','measurement_date','measured_or_inspected_by']:
            check(not row[col].strip(),row['option_id']+' '+col+' remains blank')
csvs_verified=all(p.exists()for p in csv_paths)
if a.published:
    pointer=read(B/'current-master.json')
    check(pointer['register_sha256']==a.register_sha256 and pointer['workbook_sha256']==a.workbook_sha256,'Published pointer binds current data hashes')
    g=pointer['current_published_gallery_projection']
    check(g['register_sha256']==a.register_sha256 and g['workbook_sha256']==a.workbook_sha256,'Current gallery binds corrected release')
    check(csvs_verified,'Current CSV projections exist')
failed=[x for x in checks if not x['passed']]
result={'status':'PASS_PUBLISHED_CORAL_WORDING'if a.published and not failed else 'PASS_CANDIDATE_CORAL_WORDING'if not failed else 'FAIL','checked_utc':datetime.now(timezone.utc).isoformat(),'register':str(rp),'register_sha256':sha(rp),'workbook':str(wp),'workbook_sha256':sha(wp),'checks_passed':len(checks)-len(failed),'checks_failed':len(failed),'failures':failed,'field_changes':changes,'saved_cell_changes':cell_changes,'other1133fields_unchanged':len(changes)==1,'csvs_verified':csvs_verified,'physical_verifications_added':0,'canonical_writes':0}
dest=H/(('published'if a.published else 'candidate')+'-readback-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'.json');dest.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({**result,'receipt':str(dest),'receipt_sha256':sha(dest)},ensure_ascii=False,indent=2))
raise SystemExit(1 if failed else 0)
