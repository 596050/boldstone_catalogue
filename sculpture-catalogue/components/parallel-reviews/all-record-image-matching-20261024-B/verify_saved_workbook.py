"""Read-only, independent saved XLSX comparison for the Main publisher."""
from pathlib import Path,PurePosixPath
from collections import Counter
from datetime import datetime,timezone
import copy,hashlib,json,posixpath,zipfile,xml.etree.ElementTree as ET
H=Path(__file__).resolve().parent;B=H.parents[2];C=B/'components/reconciliation/whole-gallery-navigation-master-2026-10-24'
OUT=H/'workbook-publication-qa/final';OUT.mkdir(exist_ok=True)
read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
p=read(B/'current-master.json');baseline=B/p['workbook'];candidate=C/'master-workbook.pending';plan=read(C/'workbook-edit-plan.json')
assert sha(baseline)==p['workbook_sha256']
expected='4d78ad49271f02efc1ae0331e79509169aa41b972533fbae650d0f1cdb3e6bf5'
assert sha(candidate)==expected
NS={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main','r':'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}
R=NS['r'];S=NS['s']
def node(e):return (e.tag,tuple(sorted(e.attrib.items())),e.text or '',tuple(node(x) for x in e))
def rels(z,path):
    if path not in z.namelist():return {}
    return {x.attrib['Id']:{k:v for k,v in x.attrib.items() if k!='Id'} for x in ET.fromstring(z.read(path))}
def snapshot(path):
    z=zipfile.ZipFile(path);book=ET.fromstring(z.read('xl/workbook.xml'));br=rels(z,'xl/_rels/workbook.xml.rels');strings=[]
    if 'xl/sharedStrings.xml' in z.namelist():
        strings=[''.join(si.itertext()) for si in ET.fromstring(z.read('xl/sharedStrings.xml'))]
    result={'zip':z,'book':book,'sheets':{},'sheet_order':[]}
    for sh in book.find('s:sheets',NS):
        name=sh.attrib['name'];target=br[sh.attrib['{'+R+'}id']]['Target'];part=target.lstrip('/') if target.startswith('/') else posixpath.normpath('xl/'+target)
        root=ET.fromstring(z.read(part));rp=str(PurePosixPath(part).parent/'_rels'/(PurePosixPath(part).name+'.rels'));rr=rels(z,rp)
        cells={};formulas={};styles={};rowattrs={}
        for row in root.findall('s:sheetData/s:row',NS):
            rowattrs[row.attrib['r']]=row.attrib
            for cell in row:
                ref=cell.attrib['r'];typ=cell.attrib.get('t');v=cell.find('s:v',NS);f=cell.find('s:f',NS)
                if f is not None:formulas[ref]=node(f);value=('formula',node(f))
                elif typ=='s':value=strings[int(v.text)] if v is not None and v.text is not None else ''
                elif typ=='inlineStr':value=''.join(cell.find('s:is',NS).itertext())
                elif typ=='b':value=v is not None and v.text=='1'
                elif v is not None and v.text is not None:
                    if typ in ('str','e'):value=v.text
                    else:
                        try:value=float(v.text)
                        except ValueError:value=v.text
                else:value=None
                cells[ref]=value;styles[ref]=cell.attrib.get('s','0')
        hyperlinks={}
        for link in root.findall('s:hyperlinks/s:hyperlink',NS):
            a=link.attrib;rid=a.get('{'+R+'}id');target=rr[rid]['Target'] if rid else '#'+a.get('location','')
            hyperlinks[a['ref']]=target
        skeleton=copy.deepcopy(root)
        for tag in ['sheetData','hyperlinks']:
            partnode=skeleton.find('s:'+tag,NS)
            if partnode is not None:skeleton.remove(partnode)
        for element in skeleton.iter():
            for key,val in list(element.attrib.items()):
                if key=='{'+R+'}id':element.set(key,json.dumps(rr[val],sort_keys=True))
        result['sheet_order'].append((name,sh.attrib.get('state','visible')))
        result['sheets'][name]={'cells':cells,'formulas':formulas,'styles':styles,'rowattrs':rowattrs,'hyperlinks':hyperlinks,'structure':node(skeleton)}
    return result
a=snapshot(baseline);z=snapshot(candidate);checks=Counter();failures=[]
def check(ok,kind,detail=None):
    checks[kind]+=1
    if not ok:failures.append({'kind':kind,'detail':detail})
check(a['sheet_order']==z['sheet_order'] and len(z['sheet_order'])==28,'all_sheet_names_order_visibility')
check(set(a['zip'].namelist())==set(z['zip'].namelist()),'package_part_set_unchanged')
for name in a['zip'].namelist():
    if name in ('xl/styles.xml','xl/theme/theme1.xml') or any(s in name for s in ['/tables/','/drawings/','/charts/','/comments','/vba','/externalLinks/']):check(a['zip'].read(name)==z['zip'].read(name),'native_feature_part_unchanged',name)
for tag in ['definedNames','calcPr','workbookPr','workbookProtection','bookViews']:
    x=a['book'].find('s:'+tag,NS);y=z['book'].find('s:'+tag,NS)
    check((node(x) if x is not None else None)==(node(y) if y is not None else None),'workbook_metadata_preserved',tag)
planned={(x['sheet'],x['cell']):x for x in plan['cell_changes']};link_plan={(x['sheet'],x['cell']):x['target'] for x in plan['hyperlinks']}
actual_value_changes=[];actual_link_changes=[];formula_count=0;link_count=0
for name,before in a['sheets'].items():
    after=z['sheets'][name]
    check(before['structure']==after['structure'],'sheet_layout_and_native_features',name)
    check(before['rowattrs']==after['rowattrs'],'all_row_attributes',name)
    check(set(before['cells'])==set(after['cells']),'cell_address_set',name)
    check(before['formulas']==after['formulas'],'all_formula_definitions',name);formula_count+=len(after['formulas'])
    check(before['styles']==after['styles'],'all_cell_style_bindings',name)
    for ref,value in before['cells'].items():
        new=after['cells'].get(ref);key=(name,ref)
        if key in planned:
            check(value==planned[key]['before'],'planned_old_value',key);check(new==planned[key]['value'],'planned_new_value',key)
        else:check(new==value,'unrelated_cell_value_preserved',key)
        if value!=new:actual_value_changes.append(key)
    check(set(before['hyperlinks'])==set(after['hyperlinks']),'hyperlink_address_set',name)
    for ref,url in after['hyperlinks'].items():
        check(url==link_plan.get((name,ref)),'saved_link_matches_exact_plan',(name,ref));link_count+=1
        if url!=before['hyperlinks'].get(ref):actual_link_changes.append((name,ref))
check(set(actual_value_changes)==set(planned) and len(actual_value_changes)==44,'exact_44_value_changes')
check(set(actual_link_changes)=={(x['sheet'],x['cell']) for x in plan['native_link_changes']} and len(actual_link_changes)==156,'exact_156_link_changes')
check(formula_count==3407 and link_count==12206,'formula_and_hyperlink_totals')
result={'status':'PASS' if not failures else 'FAIL','checked_utc':datetime.now(timezone.utc).isoformat(),'baseline_workbook':str(baseline),'baseline_sha256':sha(baseline),'candidate_workbook':str(candidate),'candidate_sha256':sha(candidate),'plan_sha256':sha(C/'workbook-edit-plan.json'),'checks_passed':sum(checks.values())-len(failures),'checks_total':sum(checks.values()),'check_categories':dict(checks),'failures':failures,'counts':{'sheets':len(z['sheet_order']),'formulas':formula_count,'hyperlinks':link_count,'value_changes':len(actual_value_changes),'link_changes':len(actual_link_changes)},'scope':'Independent saved-file value/formula/style/native feature preservation; no workbook authoring or native Excel runtime claim.','candidate_unchanged_after_read':sha(candidate)==expected,'workbook_writes':0}
(OUT/'saved-package-readback.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k not in ['check_categories']},indent=2))
if failures:raise SystemExit(1)
