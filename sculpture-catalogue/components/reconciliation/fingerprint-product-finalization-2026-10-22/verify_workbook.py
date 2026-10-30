"""Independent saved-OOXML and register verification for the population change."""
import copy,hashlib,importlib.util,json,posixpath,re,sys
from pathlib import Path
from datetime import datetime,timezone
from xml.etree import ElementTree as E
H=Path(__file__).resolve().parent;BASE=H.parents[2]
read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
s=importlib.util.spec_from_file_location('n',BASE/'components/reconciliation/image-identity-coverage-2026-10-20/verify_edit.py');n=importlib.util.module_from_spec(s);s.loader.exec_module(n);n.HERE=H
if '--attach'in sys.argv:
 assert not(H/'native-attachment.json').exists();n.attach();(H/'native-attachment.json').write_text('{"status":"APPLIED"}\n')
b=n.load(H/'inputs/master_workbook.before');a=n.load(H/'master-workbook.pending');plan=read(H/'workbook-edit-plan.json');exp=read(H/'expected-edit.json');changes={(x['sheet'],x['cell']):x['value']for x in plan['cell_changes']};forms={(x['sheet'],x['cell']):x for x in plan['formula_changes']};heights={(x['sheet'],str(x['row'])):x['height']for x in plan['row_heights']};issues=[];checks=0
def check(ok,msg):
 global checks
 checks+=1
 if not ok:issues.append(msg)
def rels(d,s):
 loc=s['part'];p=posixpath.join(posixpath.dirname(loc),'_rels',posixpath.basename(loc)+'.rels');return{x.get('Id'):x for x in E.fromstring(d['files'][p])}if p in d['files']else{}
def tables(d,s):
 rs=rels(d,s);out=[]
 for x in s['root'].findall('.//'+n.q('tablePart')):
  p=rs[x.get('{'+n.R+'}id')].get('Target');p=p.lstrip('/')if p.startswith('/')else posixpath.normpath(posixpath.dirname(s['part'])+'/'+p);out.append(E.fromstring(d['files'][p]))
 return out
expected_ranges={'Master Catalogue':'A9:Y195','Specifications':'A9:Q1125','Components':'A9:K121','Photo Coverage':'A9:V195','Listing Resolution':'A9:X195','Draft Listings':'A9:R111','Missing Pictures':'A9:N214','Fingerprint Current':'A9:T15'}
check(list(a['sheets'])==list(b['sheets'])+['Fingerprint History'],'All25 original tabs retained in order, one explicit history view')
for sn,z in b['sheets'].items():
 for c,v in b['values'][sn].items():
  wanted=forms.get((sn,c),{}).get('expected',changes.get((sn,c),v));check(a['values'][sn].get(c,'')==wanted,sn+'!'+c+' exact planned/cached value')
  if not(sn=='Fingerprint Current'and re.fullmatch('O1[0-5]',c)):check(a['styles'][sn].get(c,'0')==b['styles'][sn][c],sn+'!'+c+' original style')
 for c,v in a['values'][sn].items():
  if c not in b['values'][sn]:check(v==forms.get((sn,c),{}).get('expected',changes.get((sn,c),'')),sn+'!'+c+' declared new value')
 for c,f in b['formulas'][sn].items():check(a['formulas'][sn].get(c)==forms.get((sn,c),{}).get('formula',f),sn+'!'+c+' preserved/planned formula')
 for tag in ['sheetViews','sheetFormatPr','cols','mergeCells','autoFilter','pageMargins','pageSetup','dataValidations','sheetProtection']:
  check([E.tostring(x)for x in z['root'].findall(n.q(tag))]==[E.tostring(x)for x in a['sheets'][sn]['root'].findall(n.q(tag))],sn+' native '+tag)
 if sn not in ['Master Catalogue','Photo Coverage']:check([E.tostring(x)for x in z['root'].findall(n.q('conditionalFormatting'))]==[E.tostring(x)for x in a['sheets'][sn]['root'].findall(n.q('conditionalFormatting'))],sn+' original conditional rules')
 else:
  oldrules=[x for cf in z['root'].findall(n.q('conditionalFormatting'))for x in cf];newrules=[x for cf in a['sheets'][sn]['root'].findall(n.q('conditionalFormatting'))for x in cf]
  for oldrule in oldrules:
   def canon(x):
    y=copy.deepcopy(x);y.attrib.pop('priority',None);return E.tostring(y)
   check(any(canon(x)==canon(oldrule)for x in newrules),sn+' original conditional rule retained')
 oldrows={x.get('r'):dict(x.attrib)for x in z['root'].find(n.q('sheetData'))};newrows={x.get('r'):dict(x.attrib)for x in a['sheets'][sn]['root'].find(n.q('sheetData'))}
 for rn,attr in oldrows.items():
  actual=copy.deepcopy(newrows[rn]);before=copy.deepcopy(attr)
  if(sn,rn)in heights:
   check(float(actual.get('ht',-1))==heights[(sn,rn)],sn+' planned row height '+rn)
   for k in ['ht','customHeight']:actual.pop(k,None);before.pop(k,None)
  check(before==actual,sn+' row attributes '+rn)
 bt=tables(b,z);at=tables(a,a['sheets'][sn]);check(len(bt)==len(at),sn+' table count')
 for ot,nt in zip(bt,at):
  oldt=copy.deepcopy(ot);newt=copy.deepcopy(nt)
  if sn in expected_ranges:
   check(newt.get('ref')==expected_ranges[sn],sn+' current table range')
   oldt.set('ref',expected_ranges[sn]);af=oldt.find(n.q('autoFilter'))
   if af is not None:af.set('ref',expected_ranges[sn])
   if sn in ['Missing Pictures','Fingerprint Current']:oldt.attrib.pop('id',None);newt.attrib.pop('id',None)
   if sn=='Fingerprint Current':oldt.find(n.q('tableColumns'))[0].set('name','Current option ID')
  check(E.tostring(oldt)==E.tostring(newt),sn+' table name/columns/style/filter/metadata preserved except declared changes')
for group in ['fonts','fills','borders','cellStyleXfs','cellXfs','numFmts','dxfs']:
 old=b['style_root'].find(n.q(group));new=a['style_root'].find(n.q(group));check(old is None or new is not None and len(new)>=len(old)and all(E.tostring(x)==E.tostring(y)for x,y in zip(old,new)),group+' original resources')
for f in list(forms.values())+exp['formulas']:check(a['formulas'][f['sheet']].get(f['cell'])==f['formula']and a['values'][f['sheet']].get(f['cell'])==f['expected'],'Declared formula and cached result')
for sn,d in exp['sheets'].items():
 for j,v in enumerate(d['headers']):check(a['values'][sn].get(n.column(j)+'9')==v,'History header')
 for i,row in enumerate(d['rows'],10):
  for j,v in enumerate(row):check(a['values'][sn].get(n.column(j)+str(i),'')==v,'History field exactly preserved')
 check(len(tables(a,a['sheets'][sn]))==1,'History has a filterable table')
actual={}
for sn,z in a['sheets'].items():
 rs=rels(a,z)
 for h in z['root'].findall('.//'+n.q('hyperlink')):
  c=h.get('ref');target='#'+h.get('location')if h.get('location')else rs[h.get('{'+n.R+'}id')].get('Target');actual[(sn,c)]={'sheet':sn,'cell':c,'label':a['values'][sn].get(c,''),'target':target}
wanted={(x['sheet'],x['cell']):x for x in exp['hyperlinks']};check(actual==wanted,'Every retained, moved and new native hyperlink target/label exact')
formula_count=sum(len(v)for v in a['formulas'].values());check(formula_count==2791,'2754prior formulas plus37 new active/history formulas')
g=read(H/'canonical-master-register.json');prior=read(H/'inputs/master_register.before');audit=read(H/'image-coverage-current.json');prior_audit=read(H/'inputs/audit.before');packet=read(H/'inputs/product_packet.before');oldids=set(packet['legacy_disposition']['product_ids']);oldcids=set(packet['legacy_disposition']['component_ids'])
current={x['product_id']:x for x in g['options']};components={x['component_id']:x for x in g['components']};coverage={x['option_id']:x for x in audit['coverage']}
check(len(current)==186 and len(components)==112 and len(coverage)==186,'Current186 options/112 component identities')
for x in prior['options']:
 if x['product_id']not in oldids:check(current[x['product_id']]==x,'Unrelated current option exact '+x['product_id'])
for x in prior['components']:
 if x['component_id']not in oldcids:check(components[x['component_id']]==x,'Unrelated current component exact')
for x in prior_audit['coverage']:
 if x['option_id']not in oldids:check(coverage[x['option_id']]==x,'Unrelated visual role qualifications exact')
hist=g['historical_fingerprint_product_records'];check(hist['options']==[x for x in prior['options']if x['product_id']in oldids]and hist['components']==[x for x in prior['components']if x['component_id']in oldcids],'Four prior options/two components archived byte-semantic exact')
check(g['original_review_specification_assertions']==prior['original_review_specification_assertions']and len(g['original_review_specification_assertions'])==1668,'All1668 original assertions exact')
check([a['values']['Master Catalogue']['A'+str(r)]for r in range(10,196)]==read(H/'expected-ordered-current-option-ids.json'),'Saved current option order andIDs')
check([a['values']['Components']['A'+str(r)]for r in range(10,122)]==read(H/'expected-ordered-component-ids.json'),'Saved current component order andIDs')
check(sum(bool(x['six_working_fields_recorded'])for x in g['options'])==186,'All186 have six qualified working fields')
check(audit['counts']['individual_statuses']=={'Available':164,'Detail only':5,'Group only':16,'Unbound identity':1},'22current individual gaps')
check(audit['counts']['required_picture_actions']==101 and len(audit['missing_pictures'])==205,'101required current picture actions;205current source rows')
check(len(hist['picture_actions'])==6 and sum(x['status']=='Open'for x in hist['picture_actions'])==4,'Four open capture requests retired by scope; six historical action rows preserved')
for p in packet['options']:
 x=current[p['product_id']];check(x['file_id']==p['original_individual_photo']['file_id']and x['folder_id']==p['original_image_folder']['file_id'],'Current original JPEG and actual containing folder')
 check(x['component_folder_binding']['component_folder_id']==p['component_folder']['file_id'],'Separate stable component folder')
 for field,v in p['specifications'].items():check(x['master_fields'][field]['display']==v['display']and x['master_fields'][field]['basis']==v['basis']and x['master_fields'][field]['physical_verification']==0,'All36 qualified field displays/bases exact')
check(g['summary']['physical_stock_quantity']is None and g['summary']['physical_mould_count']is None,'No invented physical count')
reports=read(H/'link-report-verification.json');check(reports['status']=='PASS_OWNER_CORRECTION_REPORTS'and reports['counts']['individual_gaps']==22 and reports['counts']['required_actions']==101,'Current link reports/precise gap list')
for x in reports['pages']+reports['csv_files']+reports['thumbnail_files']:check(sha(x['path'])==x['sha256'],'Report immutable')
for key,x in read(H/'input-manifest.json').items():check(sha(x['path'])==sha(x['snapshot'])==x['sha256'],'Frozen input unchanged '+key)
result={'status':'FAIL'if issues else'PASS','recorded_utc':datetime.now(timezone.utc).isoformat(),'checks':checks,'issues':issues[:80],'workbook_sha256':sha(H/'master-workbook.pending'),'register_sha256':sha(H/'canonical-master-register.json'),'audit_sha256':sha(H/'image-coverage-current.json'),'current_options':186,'current_components':112,'current_working_fields':1116,'current_individual_gaps':22,'required_picture_actions':101,'current_action_rows':205,'formula_count':formula_count,'native_hyperlinks':len(actual),'original_sheets':25,'new_sheets':1,'unrelated_options_preserved':180,'legacy_options_archived':4,'original_assertions_preserved':1668,'root_remote_writes':0}
(H/'saved-file-verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:result[k]for k in ['status','checks','issues','formula_count','native_hyperlinks','workbook_sha256']}))
if issues:raise SystemExit(1)
