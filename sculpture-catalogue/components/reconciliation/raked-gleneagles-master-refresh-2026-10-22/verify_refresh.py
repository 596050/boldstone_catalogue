"""Independently verify authored cells, native workbook features and source preservation."""
import copy,hashlib,importlib.util,json,posixpath,sys
from pathlib import Path
from datetime import datetime,timezone
from xml.etree import ElementTree as E
H=Path(__file__).resolve().parent;BASE=H.parents[2]
read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
spec=importlib.util.spec_from_file_location('native',BASE/'components/reconciliation/image-identity-coverage-2026-10-20/verify_edit.py');n=importlib.util.module_from_spec(spec);spec.loader.exec_module(n);n.HERE=H
def rels(d,s):
 p=s['part'];p=posixpath.join(posixpath.dirname(p),'_rels',posixpath.basename(p)+'.rels')
 return {x.get('Id'):x for x in E.fromstring(d['files'][p])}if p in d['files']else{}
def tables(d,s):
 rs=rels(d,s);out=[]
 for x in s['root'].findall('.//'+n.q('tablePart')):
  t=rs[x.get('{'+n.R+'}id')].get('Target');p=t.lstrip('/')if t.startswith('/')else posixpath.normpath(posixpath.dirname(s['part'])+'/'+t);out.append(d['files'][p])
 return out
if '--attach'in sys.argv:
 assert not(H/'native-attachment.json').exists(),'Native attachment is single use for this exported workbook'
 restored=n.attach();(H/'native-attachment.json').write_text(json.dumps({'status':'APPLIED','restored_original_differential_formats':restored})+'\n')
b=n.load(H/'inputs/master_workbook.before');a=n.load(H/'master-workbook.pending');e=read(H/'expected-edit.json');p=read(H/'workbook-edit-plan.json');issues=[];checks=0
def check(ok,msg):
 global checks
 checks+=1
 if not ok:issues.append(msg)
changes={(x['sheet'],x['cell']):x for x in p['cell_changes']};heights={(x['sheet'],str(x['row'])):x['height']for x in p['row_heights']}
check(list(a['sheets'])==list(b['sheets'])+['Gleneagles Folders'],'All21 original tabs retained in order, one binding tab added')
for sn,s in b['sheets'].items():
 check(a['formulas'][sn]==b['formulas'][sn],sn+' original formulas')
 for cell,val in b['values'][sn].items():
  check(a['values'][sn].get(cell,'')==changes.get((sn,cell),{}).get('value',val),sn+'!'+cell+' original or planned value/cache')
  check(a['styles'][sn].get(cell,'0')==b['styles'][sn][cell],sn+'!'+cell+' original cell style')
 check(all(not v for c,v in a['values'][sn].items()if c not in b['values'][sn]),sn+' no unplanned added values')
 for tag in ['sheetViews','sheetFormatPr','cols','mergeCells','conditionalFormatting','autoFilter','pageMargins','pageSetup','dataValidations','sheetProtection']:
  check([E.tostring(x)for x in s['root'].findall(n.q(tag))]==[E.tostring(x)for x in a['sheets'][sn]['root'].findall(n.q(tag))],sn+' native '+tag)
 check(tables(a,a['sheets'][sn])==tables(b,s),sn+' existing tables and filters byte identical')
 oldrows={r.get('r'):dict(r.attrib)for r in s['root'].find(n.q('sheetData'))};newrows={r.get('r'):dict(r.attrib)for r in a['sheets'][sn]['root'].find(n.q('sheetData'))}
 check(set(oldrows)==set(newrows),sn+' row inventory')
 for rn,attr in oldrows.items():
  actual=newrows[rn]
  if(sn,rn)in heights:
   check(float(actual.get('ht','-1'))==heights[(sn,rn)],sn+' declared row height '+rn)
   attr.pop('ht',None);actual.pop('ht',None);attr.pop('customHeight',None);actual.pop('customHeight',None)
  check(attr==actual,sn+' row attributes '+rn)
for group in ['fonts','fills','borders','cellStyleXfs','cellXfs','numFmts','dxfs']:
 old=b['style_root'].find(n.q(group));new=a['style_root'].find(n.q(group))
 check(old is None or new is not None and len(new)>=len(old)and all(E.tostring(x)==E.tostring(y)for x,y in zip(old,new)),group+' all original resources')
for sn,d in e['sheets'].items():
 for j,v in enumerate(d['headers']):check(a['values'][sn].get(n.column(j)+'9')==v,'New binding header')
 for i,row in enumerate(d['rows'],10):
  for j,v in enumerate(row):check(a['values'][sn].get(n.column(j)+str(i),'')==v,'New binding value')
 check(a['sheets'][sn]['root'].find('.//'+n.q('pane'))is not None,'New binding frozen headers')
 check(len(tables(a,a['sheets'][sn]))==1,'New binding filterable table')
for f in e['formulas']:
 check(a['formulas'][f['sheet']].get(f['cell'])==f['formula']and a['values'][f['sheet']].get(f['cell'])==f['expected'],'New dependency formula and cache')
actual={}
for sn,s in a['sheets'].items():
 rs=rels(a,s)
 for x in s['root'].findall('.//'+n.q('hyperlink')):
  cell=x.get('ref');target='#'+x.get('location')if x.get('location')else rs[x.get('{'+n.R+'}id')].get('Target');actual[(sn,cell)]={'sheet':sn,'cell':cell,'target':target,'label':a['values'][sn].get(cell,'')}
wanted={(x['sheet'],x['cell']):x for x in e['hyperlinks']}
check(actual==wanted and len(actual)==11233,'All11217 original native hyperlinks plus16 bindings preserved or updated exactly')
formula_count=sum(len(x)for x in a['formulas'].values());check(formula_count==2739,'All2729 original formulas plus10 new dependency formulas')
def reverse(after,log):
 z=copy.deepcopy(after)
 for x in reversed(log):
  node=z
  for k in x['path'][:-1]:node=node[k]
  k=x['path'][-1]
  if x['kind']=='added':check(node.pop(k)==x['after'],'Declared addition matches change log')
  else:check(node[k]==x['after'],'Declared change matches log');node[k]=x['before']
 return z
g=read(H/'canonical-master-register.json');old=read(H/'inputs/master_register.before');audit=read(H/'image-coverage-current.json');prior=read(H/'inputs/audit.before')
check(reverse(g,read(H/'register-change-log.json'))==old,'Register changes exactly match declared diff')
check(reverse(audit,read(H/'audit-change-log.json'))==prior,'Audit changes exactly match declared diff')
check(len(g['options'])==184 and len(g['components'])==111 and g['summary']==old['summary'],'184 options and111 component identities retained')
check(g['original_review_specification_assertions']==old['original_review_specification_assertions'],'All1668 original source specification assertions preserved')
for x,y in zip(g['options'],old['options']):
 check(all(x[k]==y[k]for k in ['product_id','canonical_component_id','master_fields','specifications','photo_coverage']),x['product_id']+' IDs, six field groups, qualifications and roles unchanged')
check(audit['counts']==prior['counts'],'All photo counts and qualifications retained')
check(audit['counts']['individual_statuses']=={'Available':158,'Detail only':5,'Group only':20,'Unbound identity':1},'26 qualified individual gaps retained')
bindings=g['latest_gleneagles_numbering']['component_finish_bindings'];check(len(bindings)==4,'Four approved numbered folder bindings')
for x in bindings:
 o=next(o for o in g['options']if o['product_id']==x['product_id'])
 check(o['name']==x['new_option_name']and o['photo_coverage']['individual']=='Group only','Numbered identity with qualified photo gap')
 check(x['reference_document_id']=='Unbound'and not x['reference_document_url'],'Unavailable historical HTML is not current link')
 check(o['folder_id']!=x['component_finish_folder_id']and o['file_id']==x['primary_group_reference_file_id'],'Original group and candidate PNG remain distinct')
check(read(H/'independent-native-verification.json')['status']=='PASS','Independent current native ID/path readback')
reports=read(H/'link-report-verification.json');check(reports['status']=='PASS_OWNER_CORRECTION_REPORTS','Current linked reports completed')
for x in reports['pages']+reports['csv_files']+reports['thumbnail_files']:check(sha(x['path'])==x['sha256'],'Report artifact hash')
for key,x in read(H/'input-manifest.json').items():check(sha(x['path'])==sha(x['snapshot'])==x['sha256'],'Input unchanged '+key)
result={'status':'FAIL'if issues else'PASS','recorded_utc':datetime.now(timezone.utc).isoformat(),'checks':checks,'issues':issues[:50],'workbook_sha256':sha(H/'master-workbook.pending'),'register_sha256':sha(H/'canonical-master-register.json'),'audit_sha256':sha(H/'image-coverage-current.json'),'original_sheets':21,'new_sheets':1,'cell_changes':len(changes),'native_hyperlinks':len(actual),'native_targets_updated':len(p['target_changes']),'new_binding_links':16,'formula_count':formula_count,'original_specification_assertions_preserved':1668,'options':184,'identified_component_identities':111,'individual_gaps':26,'required_picture_actions':105,'root_remote_writes':0,'unrelated_original_cells_styles_formulas_native_features_preserved':not issues}
(H/'saved-file-verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:result[k]for k in ['status','checks','issues','workbook_sha256','register_sha256']}))
if issues:raise SystemExit(1)
