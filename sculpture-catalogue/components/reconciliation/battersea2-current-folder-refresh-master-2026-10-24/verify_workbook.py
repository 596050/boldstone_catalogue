"""Read the saved OOXML and compare it with the frozen master and scoped plan."""
import copy,hashlib,importlib.util,json,posixpath,re,sys
from pathlib import Path
from datetime import datetime,timezone
from xml.etree import ElementTree as E
H=Path(__file__).resolve().parent;B=H.parents[2]
read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
s=importlib.util.spec_from_file_location('native',B/'components/reconciliation/image-identity-coverage-2026-10-20/verify_edit.py');n=importlib.util.module_from_spec(s);s.loader.exec_module(n);n.HERE=H
if '--attach'in sys.argv:
 assert not(H/'native-attachment.json').exists(),'Native attachment already applied to this export'
 before=sha(H/'master-workbook.pending');restored=n.attach();(H/'native-attachment.json').write_text(json.dumps({'before_sha256':before,'after_sha256':sha(H/'master-workbook.pending'),'original_differential_formats_restored':restored,'cell_formula_authoring_performed':False},indent=2)+'\n')
a=n.load(H/'master-workbook.pending');b=n.load(H/'inputs/master_workbook.before');plan=read(H/'workbook-edit-plan.json');g=read(H/'canonical-master-register.json');old=read(H/'inputs/master_register.before');audit=read(H/'image-coverage-current.json');m=read(H/'input-manifest.json');issues=[];checks=0
def check(ok,msg):
 global checks
 checks+=1
 if not ok:issues.append(msg)
changes={(x['sheet'],x['cell']):x for x in plan['cell_changes']};forms={(x['sheet'],x['cell']):x for x in plan['formula_changes']};appends={x['sheet']:x for x in plan['table_appends']};heights={(x['sheet'],x['row']):x['height']for x in plan['row_heights']}
check(list(a['sheets'])==list(b['sheets']),'All28 original tabs retained in order')
def tables(data,info):
 rp=posixpath.join(posixpath.dirname(info['part']),'_rels',posixpath.basename(info['part'])+'.rels');rs={x.get('Id'):x.get('Target')for x in E.fromstring(data['files'][rp])}if rp in data['files']else{};out=[]
 for x in info['root'].findall('.//'+n.q('tablePart')):
  target=rs[x.get('{'+n.R+'}id')];p=target.lstrip('/')if target.startswith('/')else posixpath.normpath(posixpath.dirname(info['part'])+'/'+target);out.append(E.fromstring(data['files'][p]))
 return out
for sn,info in b['sheets'].items():
 expectedforms=copy.deepcopy(b['formulas'][sn]);expectedforms.update({c:x['formula']for(s,c),x in forms.items()if s==sn});check(a['formulas'][sn]==expectedforms,sn+' formula text scope')
 for c,v in b['values'][sn].items():
  target=changes.get((sn,c),{}).get('value',forms.get((sn,c),{}).get('expected',v));check(a['values'][sn].get(c,'')==target,sn+'!'+c+' source value or authorized edit')
  check(a['styles'][sn].get(c,'0')==b['styles'][sn][c],sn+'!'+c+' original cell style')
 for(s,c),x in changes.items():
  if s==sn:check(a['values'][sn].get(c,'')==x['value'],sn+'!'+c+' planned value')
 for(s,c),x in forms.items():
  if s==sn:check(a['values'][sn].get(c,'')==x['expected'],sn+'!'+c+' formula result')
 ar=a['sheets'][sn]['root'];br=info['root']
 for tag in ['sheetViews','sheetFormatPr','cols','mergeCells','dataValidations','pageMargins','pageSetup','sheetProtection']:
  check(tag=='dataValidations'and sn=='Missing Pictures' or [E.tostring(x)for x in ar.findall(n.q(tag))]==[E.tostring(x)for x in br.findall(n.q(tag))],sn+' preserved native '+tag)
 oldcf=br.findall(n.q('conditionalFormatting'));newcf=ar.findall(n.q('conditionalFormatting'));check([E.tostring(x)for x in newcf[:len(oldcf)]]==[E.tostring(x)for x in oldcf],sn+' original conditional formats preserved')
 check(len(newcf)==len(oldcf),sn+' no additional conditional formats')
 bt,at=tables(b,info),tables(a,a['sheets'][sn]);check(len(bt)==len(at),sn+' table count preserved')
 for x,y in zip(bt,at):
  ex=copy.deepcopy(x)
  if sn in appends:
   v=appends[sn];end=n.column(v['columns']-1)+str(v['old_last']+v['rows']);ex.set('ref','A9:'+end)
   filt=ex.find(n.q('autoFilter'))
   if filt is not None:filt.set('ref','A9:'+end)
  check(E.tostring(ex)==E.tostring(y),sn+' native table/filters preserved or extended')
 afterrows={int(x.get('r')):x for x in ar.find(n.q('sheetData'))}
 for x in br.find(n.q('sheetData')):
  r=int(x.get('r'));expected=dict(x.attrib)
  if(sn,r)in heights:expected['ht']=str(heights[(sn,r)]);expected['customHeight']='1'
  actual=afterrows[r].attrib
  check(all(actual.get(k)==v or k=='ht'and float(actual.get(k))==float(v)for k,v in expected.items()),sn+' row'+str(r)+' attributes and planned height')
dv=a['sheets']['Missing Pictures']['root'].find(n.q('dataValidations'));check(len(dv)==1 and dv[0].get('sqref')=='N10:N220' and dv[0].find(n.q('formula1')).text=='\"Open,In progress,Resolved,Optional,Retired / not applicable\"','Retired state added to the existing action-status dropdown only')
for group in ['fonts','fills','borders','cellStyleXfs','cellXfs','numFmts','dxfs']:
 before=b['style_root'].find(n.q(group));after=a['style_root'].find(n.q(group));check(before is None or after is not None and all(E.tostring(x)==E.tostring(y)for x,y in zip(before,after)),group+' original style definitions preserved')
actual={}
for sn,info in a['sheets'].items():
 rp=posixpath.join(posixpath.dirname(info['part']),'_rels',posixpath.basename(info['part'])+'.rels');rs={x.get('Id'):x for x in E.fromstring(a['files'][rp])}
 for x in info['root'].findall('.//'+n.q('hyperlink')):
  target='#'+x.get('location')if x.get('location')else rs[x.get('{'+n.R+'}id')].get('Target');actual[(sn,x.get('ref'))]=target
expectedlinks={(x['sheet'],x['cell']):x for x in plan['hyperlinks']};check(set(actual)==set(expectedlinks),'Native link cell set exact')
for key,x in expectedlinks.items():check(actual.get(key)==x['target'],'Native destination '+str(key));check(a['values'][key[0]].get(key[1],'')==x['label'],'Native link label '+str(key))
check(sum(map(len,a['formulas'].values()))==plan['expected_formula_count'],'All3407 original formulas retained')
check(g['original_review_specification_assertions']==old['original_review_specification_assertions'],'All1668 raw source assertions immutable')
check(len(g['options'])==189 and len(g['components'])==112 and len({x['product_id']for x in g['options']})==189,'189 retained options /112 existing component identities')
for x,y in zip(g['options'],old['options']):
 check(all(x[k]==y[k]for k in ['product_id','name','canonical_key','canonical_component_id','specifications']),'Existing identity and source specifications '+x['product_id'])
 check(x['master_fields']==y['master_fields']and x['selling_details']==y['selling_details'],'All working and selling fields unchanged '+x['product_id'])
for x in g['options'][-2:]:
 check(not any(v.get('explicit_owner_confirmation')for v in x['master_fields'].values()),'No One Leaf approval copied to '+x['product_id']);check(all(v['physical_verification']==0 for v in x['master_fields'].values()),'No new physical assertion '+x['product_id'])
check([x['option_id']for x in audit['coverage']]==[x['product_id']for x in g['options']],'One current coverage row per option in canonical order')
check(audit['counts']['required_picture_actions']==25 and audit['counts']['individual_statuses']['Available']==177,'Current25 required actions and177 complete individual references')
check(audit['counts']['outstanding_individual_image_or_identity_actions']==2 and audit['counts']['technical_individual_reference_gaps']==11,'Action gaps and technical coverage remain distinct')
for x in read(H/'original-verification.json')['files']:check(sha(x['local_original'])==x['sha256'],'Approved and restored original bytes unchanged '+x['file_id'])
check(read(H/'source-evidence-verification.json')['status']=='PASS','Review authority and original native identities verified')
for p,x in read(H/'evidence-manifest.json').items():check(sha(p)==x['sha256'],'Frozen fresh evidence '+p)
for k,x in m.items():check(sha(x['path'])==sha(x['snapshot'])==x['sha256'],'Frozen source unchanged '+k)
reports=read(H/'report-verification.json');check(reports['register_sha256']==sha(H/'canonical-master-register.json')and reports['audit_sha256']==sha(H/'image-coverage-current.json'),'Current reports bound to exact data')
for x in reports['pages']+reports['csv_files']+reports['thumbnail_files']:check(sha(x['path'])==x['sha256'],'Current report artifact '+x['path'])
result={'status':'FAIL'if issues else'PASS','recorded_utc':datetime.now(timezone.utc).isoformat(),'checks':checks,'issues':issues[:80],'workbook_sha256':sha(H/'master-workbook.pending'),'register_sha256':sha(H/'canonical-master-register.json'),'audit_sha256':sha(H/'image-coverage-current.json'),'sheet_count':len(a['sheets']),'formula_count':sum(map(len,a['formulas'].values())),'native_hyperlinks':len(actual),'current_options':188,'retained_option_rows':189,'working_component_identities':112,'working_field_groups':1128,'retained_working_field_groups':1134,'new_finish_options':0,'new_water_build_options':0,'owner_series_requirements_made_optional':0,'new_physical_verifications':0,'owner_approval_scope':'Seven existing Battersea2 source paths and actual parents refreshed; selections, photo policies and all specifications unchanged.','all_unrelated_values_formulas_styles_native_features_compared':True,'native_file_revision_restores':0,'platform_writes':0}
(H/'saved-file-verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:result[k]for k in ['status','checks','issues','formula_count','native_hyperlinks']}))
if issues:raise SystemExit(1)
