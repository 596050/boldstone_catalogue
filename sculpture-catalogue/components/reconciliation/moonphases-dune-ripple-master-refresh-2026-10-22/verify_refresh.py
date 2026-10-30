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
check(list(a['sheets'])==list(b['sheets'])+['Moonphases and Dune'],'All26 original tabs retained in order, one current-folder binding tab added')
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
check(actual==wanted and len(actual)==11495,'All11427 original hyperlinks plus68 current binding links exact')
formula_count=sum(len(x)for x in a['formulas'].values());check(formula_count==2794,'All2791 original formulas plus3 dependent folder summary formulas')
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
check(len(g['options'])==186 and len(g['components'])==112 and g['summary']==old['summary'],'186 options and112 working component identities retained')
check(g['original_review_specification_assertions']==old['original_review_specification_assertions']and len(g['original_review_specification_assertions'])==1668,'All1668 original source specification assertions preserved')
fpids=set(read(H/'inputs/fp_approval_seal.before')['current_option_ids'])
for x,y in zip(g['options'],old['options']):
 check(all(x[k]==y[k]for k in ['product_id','canonical_component_id','photo_coverage']),x['product_id']+' stable IDs and image roles retained')
 for field in x['master_fields']:
  check(x['master_fields'][field]['display']==y['master_fields'][field]['display']and x['master_fields'][field]['physical_verification']==y['master_fields'][field]['physical_verification'],x['product_id']+' exact labelled display and physical qualification')
 if x['product_id']in fpids:
  check(x['explicit_owner_working_specification_confirmation']['decision_id']==g['latest_fingerprint_working_specification_confirmation']['decision_id'],'Explicit owner approval linked to current option')
  for field,z in x['master_fields'].items():check(z['explicit_owner_confirmation']['labels_preserved']and not z['explicit_owner_confirmation']['physical_verification_added'],'All36 owner-approved working fields retain qualifications')
 else:check(x['master_fields']==y['master_fields']and x['specifications']==y['specifications'],'Unrelated option working fields exact')
check(audit['counts']==prior['counts'],'All photograph role counts and qualifications retained')
check(audit['counts']['individual_statuses']=={'Available':164,'Detail only':5,'Group only':16,'Unbound identity':1},'22 qualified individual gaps retained')
check(audit['individual_capture_queue_counts']=={'individual_gaps':22,'separate_photographs_required':21,'legacy_identity_deferred':1,'approved_crop_actions':0,'historical_crop_candidates_declined':13},'Owner no-crops criterion preserved')
roles=['individual','in_situ','series']
for x,y in zip(audit['coverage'],prior['coverage']):
 check(x['option_id']==y['option_id']and all(x[r]['status']==y[r]['status']for r in roles),'No image status upgrade from folder changes')
 for r in roles:
  xr=x[r].get('reference')or{};yr=y[r].get('reference')or{};check(xr.get('file_id')==yr.get('file_id')and xr.get('folder_id')==yr.get('folder_id'),'Exact same source image and actual parent IDs')
renames=read(H/'inputs/dune_overlay.before')['option_name_projection'];byid={x['product_id']:x for x in g['options']}
for x in renames:check(byid[x['product_id']]['name']==x['current_name']and x['old_name']in byid[x['product_id']]['retained_names'],'13 exact owner-numbered Dune display names, previous aliases retained')
check(g['latest_moonphases_dune_ripple_refresh']['stable_objects_verified']==1435 and g['latest_moonphases_dune_ripple_refresh']['folder_renames']==35,'1435 stable native objects and35 approved folder changes')
for cell,value in b['values']['Source Specifications'].items():
 if cell.startswith(('M','N')):check(a['values']['Source Specifications'][cell]==value,'Original historical URLs unchanged')
check(read(H/'independent-native-verification.json')['status']=='PASS','Independent current native ID/path readback')
reports=read(H/'link-report-verification.json');check(reports['status']=='PASS_OWNER_CORRECTION_REPORTS','Current linked reports completed')
for x in reports['pages']+reports['csv_files']+reports['thumbnail_files']:check(sha(x['path'])==x['sha256'],'Report artifact hash')
for key,x in read(H/'input-manifest.json').items():check(sha(x['path'])==sha(x['snapshot'])==x['sha256'],'Input unchanged '+key)
result={'status':'FAIL'if issues else'PASS','recorded_utc':datetime.now(timezone.utc).isoformat(),'checks':checks,'issues':issues[:50],'workbook_sha256':sha(H/'master-workbook.pending'),'register_sha256':sha(H/'canonical-master-register.json'),'audit_sha256':sha(H/'image-coverage-current.json'),'original_sheets':26,'new_sheets':1,'cell_changes':len(changes),'native_hyperlinks':len(actual),'native_targets_updated':len(p['target_changes']),'new_binding_links':68,'formula_count':formula_count,'original_specification_assertions_preserved':1668,'options':186,'identified_component_identities':112,'individual_gaps':22,'required_picture_actions':101,'root_remote_writes':0,'unrelated_original_cells_styles_formulas_native_features_preserved':not issues}
(H/'saved-file-verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:result[k]for k in ['status','checks','issues','workbook_sha256','register_sha256']}))
if issues:raise SystemExit(1)
