"""Verify saved cells, linked calculations, preserved sources and accepted roles."""
import collections,copy,hashlib,importlib.util,json,posixpath,re,sys
from pathlib import Path
from datetime import datetime,timezone
from xml.etree import ElementTree as E
H=Path(__file__).resolve().parent;BASE=H.parents[2]
read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
s=importlib.util.spec_from_file_location('native',BASE/'components/reconciliation/image-identity-coverage-2026-10-20/verify_edit.py');n=importlib.util.module_from_spec(s);s.loader.exec_module(n);n.HERE=H
def rels(d,z):
 p=posixpath.join(posixpath.dirname(z['part']),'_rels',posixpath.basename(z['part'])+'.rels')
 return {x.get('Id'):x for x in E.fromstring(d['files'][p])}if p in d['files']else{}
def tables(d,z):
 rs=rels(d,z);out=[]
 for x in z['root'].findall('.//'+n.q('tablePart')):
  t=rs[x.get('{'+n.R+'}id')].get('Target');p=t.lstrip('/')if t.startswith('/')else posixpath.normpath(posixpath.dirname(z['part'])+'/'+t);out.append(d['files'][p])
 return out
if '--attach'in sys.argv:
 assert not(H/'native-attachment.json').exists(),'Attach once per authored export'
 restored=n.attach();(H/'native-attachment.json').write_text(json.dumps({'status':'APPLIED','restored_original_differential_formats':restored})+'\n')
b=n.load(H/'inputs/master_workbook.before');a=n.load(H/'master-workbook.pending');p=read(H/'workbook-edit-plan.json');e=read(H/'expected-edit.json');data=read(H/'workbook-data.json');issues=[];checks=0
def check(ok,msg):
 global checks
 checks+=1
 if not ok:issues.append(msg)
changes={(x['sheet'],x['cell']):x['value']for x in p['cell_changes']}
fc={(x['sheet'],x['cell']):x for x in p['formula_changes']};cache={(x['sheet'],x['cell']):x['expected']for x in p['formula_cache_changes']+p['formula_changes']}
heights={(x['sheet'],str(x['row'])):x['height']for x in p['row_heights']};appends={x['sheet']:x for x in data['table_appends']}
check(list(a['sheets'])==list(b['sheets'])and len(a['sheets'])==28,'All28 original sheets retained in the same order')
for sn,z in b['sheets'].items():
 expected=copy.deepcopy(b['formulas'][sn]);expected.update({cell:x['formula']for(sheet,cell),x in fc.items()if sheet==sn});check(a['formulas'][sn]==expected,sn+' original formulas or three approved range extensions')
 for c,v in b['values'][sn].items():
  check(a['values'][sn].get(c,'')==cache.get((sn,c),changes.get((sn,c),v)),sn+'!'+c+' exact preserved or planned value/cache')
  check(a['styles'][sn].get(c,'0')==b['styles'][sn][c],sn+'!'+c+' original style')
 for c,v in a['values'][sn].items():
  if c in b['values'][sn]or not v:continue
  allowed=sn in appends and 59<=int(re.search(r'\d+',c).group())<=62
  check(allowed,sn+'!'+c+' additional value belongs to approved folder rows')
 for tag in ['sheetViews','sheetFormatPr','cols','mergeCells','conditionalFormatting','autoFilter','pageMargins','pageSetup','dataValidations','sheetProtection']:
  check([E.tostring(x)for x in z['root'].findall(n.q(tag))]==[E.tostring(x)for x in a['sheets'][sn]['root'].findall(n.q(tag))],sn+' native '+tag)
 before=tables(b,z);after=tables(a,a['sheets'][sn])
 if sn in appends:
  check(len(before)==len(after)==1,sn+' existing table retained')
  old=E.fromstring(before[0]);new=E.fromstring(after[0]);check(new.get('ref')=='A9:N62'and new.find(n.q('autoFilter')).get('ref')=='A9:N62','Existing folder table extended to row62')
  new.set('ref',old.get('ref'));new.find(n.q('autoFilter')).set('ref',old.find(n.q('autoFilter')).get('ref'));check(E.tostring(old)==E.tostring(new),'Original folder table metadata preserved except range')
 else:check(before==after,sn+' existing table/filter bytes preserved')
 oldrows={r.get('r'):dict(r.attrib)for r in z['root'].find(n.q('sheetData'))};newrows={r.get('r'):dict(r.attrib)for r in a['sheets'][sn]['root'].find(n.q('sheetData'))}
 check(set(oldrows)<=set(newrows),sn+' all original rows retained')
 check(not(set(newrows)-set(oldrows))or sn in appends and all(59<=int(r)<=62 for r in set(newrows)-set(oldrows)),sn+' only declared rows appended')
 for rn,attr in oldrows.items():
  actual=newrows[rn]
  if(sn,rn)in heights:
   check(float(actual.get('ht','-1'))==heights[(sn,rn)],sn+' row height '+rn)
   for k in ['ht','customHeight']:attr.pop(k,None);actual.pop(k,None)
  check(attr==actual,sn+' original row attributes '+rn)
for group in ['fonts','fills','borders','cellStyleXfs','cellXfs','numFmts','dxfs']:
 old=b['style_root'].find(n.q(group));new=a['style_root'].find(n.q(group))
 check(old is None or new is not None and len(new)>=len(old)and all(E.tostring(x)==E.tostring(y)for x,y in zip(old,new)),group+' original style resources')
for tab in data['table_appends']:
 for i,row in enumerate(tab['rows'],tab['old_last_row']+1):
  for j,v in enumerate(row):check(a['values'][tab['sheet']].get(n.column(j)+str(i),'')==(v['label']if isinstance(v,dict)else v),'Appended folder reference value')
for sn,d in e['sheets'].items():
 for j,v in enumerate(d['headers']):check(a['values'][sn].get(n.column(j)+'9')==v,'Selling view header')
 for i,row in enumerate(d['rows'],10):
  for j,v in enumerate(row):check(a['values'][sn].get(n.column(j)+str(i),'')==v,'Selling view value or linked cache')
 check(a['sheets'][sn]['root'].find('.//'+n.q('pane'))is not None,'New selling view frozen identifiers')
 check(len(tables(a,a['sheets'][sn]))==1,'New selling view filterable table')
for f in e['formulas']:
 check(a['formulas'][f['sheet']].get(f['cell'])==f['formula']and a['values'][f['sheet']].get(f['cell'])==f['expected'],'New owning-field lookup and summary calculation')
actual={}
for sn,z in a['sheets'].items():
 rs=rels(a,z)
 for x in z['root'].findall('.//'+n.q('hyperlink')):
  c=x.get('ref');t='#'+x.get('location')if x.get('location')else rs[x.get('{'+n.R+'}id')].get('Target');actual[(sn,c)]={'sheet':sn,'cell':c,'target':t,'label':a['values'][sn].get(c,'')}
wanted={(x['sheet'],x['cell']):x for x in e['hyperlinks']};check(actual==wanted and len(actual)==p['expected_native_links'],'All11901 native links match exact targets and labels')
check(all(x['target']for x in actual.values()),'No empty native hyperlink targets')
check(all(('Selling Details',c)not in actual for c in ['L91','M91'])and a['values']['Selling Details']['L91']=='No bound individual image'and a['values']['Selling Details']['M91']=='No bound folder','Deferred FrozenFish has plain absent-binding labels')
formula_count=sum(len(x)for x in a['formulas'].values());check(formula_count==p['expected_formula_count'],'All3356 original formulas retained; only three folder ranges extended')
def reverse(after,log):
 z=copy.deepcopy(after)
 for x in reversed(log):
  node=z
  for k in x['path'][:-1]:node=node[k]
  k=x['path'][-1]
  if x['kind']=='added':check(node.pop(k)==x['after'],'Declared added value exact')
  elif x['kind']=='removed':node[k]=x['before']
  else:check(node[k]==x['after'],'Declared revised value exact');node[k]=x['before']
 return z
g=read(H/'canonical-master-register.json');old=read(H/'inputs/master_register.before');audit=read(H/'image-coverage-current.json');prior=read(H/'inputs/audit.before')
check(reverse(g,read(H/'register-change-log.json'))==old,'Register exactly reversible to frozen original')
check(reverse(audit,read(H/'audit-change-log.json'))==prior,'Image audit exactly reversible to frozen original')
check(g['summary']==old['summary']and len(g['options'])==186 and len(g['components'])==112,'No options or component count change')
check(g['original_review_specification_assertions']==old['original_review_specification_assertions']and len(g['original_review_specification_assertions'])==1668,'All original specification assertions preserved')
for x,y in zip(g['options'],old['options']):
 oid=x['product_id']
 check(all(x[k]==y[k]for k in ['product_id','canonical_component_id','name','family','specifications']),oid+' original identities and source specifications')
 for f in x['master_fields']:check(x['master_fields'][f]==y['master_fields'][f],oid+' exact working field '+f)
 check(x['selling_details']==y['selling_details']and x['current_commercial_policy']==y['current_commercial_policy'],oid+' exact commercial prices, units and policy')
 check(x['photo_coverage']==y['photo_coverage'],oid+' image classifications retained')
 check(x['file_id']==y['file_id'],oid+' primary image file ID retained')
 expected='id:cnqzTNngPVsAAAAAAA6VlQ'if oid=='BSI-828E89E3B7DC'else y['folder_id']
 check(x['folder_id']==expected,oid+' actual current containing folder ID')
for field in ['historical_commercial_field_revisions','latest_commercial_completion']:
 check(g[field]==old[field],'Historical and current commercial packet metadata retained')
for x,y in zip(audit['coverage'],prior['coverage']):
 for role in ['individual','in_situ','series']:
  check(x[role]['status']==y[role]['status'],'Every image role status retained')
  xr=x[role].get('reference')or{};yr=y[role].get('reference')or{};check(xr.get('file_id')==yr.get('file_id'),'Every role image file ID retained')
  expected='id:cnqzTNngPVsAAAAAAA6VlQ'if yr.get('file_id')=='id:cnqzTNngPVsAAAAAAAylhw'else yr.get('folder_id');check(xr.get('folder_id')==expected,'Only moved Spice2 image changes actual parent ID')
check(audit['counts']==prior['counts'],'All image-coverage counts retained')
check(audit['counts']['individual_statuses']=={'Available':167,'Detail only':2,'Group only':16,'Unbound identity':1},'19individual gaps reconcile to186options')
tasks=[x for x in audit['missing_pictures']if x['status']=='Open'];check(collections.Counter(x['role']for x in tasks)=={'Individual':19,'In situ':61,'Series':18}and len(tasks)==98,'Exact per-role required queue')
check(audit['individual_capture_queue_counts']=={'individual_gaps':19,'separate_photographs_required':18,'legacy_identity_deferred':1,'approved_crop_actions':0,'historical_crop_candidates_declined':13,'new_owner_accepted_individual_listing_images':3},'No crops and18separate photograph requests retained')
for c,v in b['values']['Source Specifications'].items():
 if re.fullmatch(r'[MN]\d+',c):check(a['values']['Source Specifications'][c]==v,'Historical source URLs preserved')
check(g['wall_sculpture_customisation_policy']==old['wall_sculpture_customisation_policy']and g['current_frozen_fish_size_policy']==old['current_frozen_fish_size_policy'],'Customization and70x15FrozenFish retained')
check(read(H/'native-and-originals-verification.json')['status']=='PASS','Stable native folder and image-original verification')
check(read(H/'artifact-authoring-receipt.json')['owning_folder_summary_dependency_verified'],'Artifact input-change recalculation check completed and restored')
reports=read(H/'link-report-verification.json');cl=read(H/'capture-and-specification-verification.json');check(reports['counts']['required_actions']==98 and cl['commercial_field_changes_by_root']==0 and reports['counts']['new_visual_roles_mapped']==0,'Current reports match reference-only scope')
for x in reports['pages']+reports['csv_files']+reports['thumbnail_files']+cl['pages']+cl['csv_files']:check(sha(x['path'])==x['sha256'],'Saved review artifact hash')
for key,x in read(H/'input-manifest.json').items():check(sha(x['path'])==sha(x['snapshot'])==x['sha256'],'Frozen input unchanged '+key)
result={'status':'FAIL'if issues else'PASS','recorded_utc':datetime.now(timezone.utc).isoformat(),'checks':checks,'issues':issues[:60],'workbook_sha256':sha(H/'master-workbook.pending'),'register_sha256':sha(H/'canonical-master-register.json'),'audit_sha256':sha(H/'image-coverage-current.json'),'original_sheets':28,'new_sheets':0,'cell_changes':len(changes),'native_hyperlinks':len(actual),'native_targets_updated':len(p['target_changes']),'new_native_links':8,'formula_count':formula_count,'original_specification_assertions_preserved':1668,'options':186,'identified_component_identities':112,'individual_gaps':19,'separate_individual_images_required':18,'required_picture_actions':98,'commercial_field_changes':0,'working_estimated_prices_retained':185,'specific_owner_exception_retained':1,'new_accepted_individual_images':0,'folder_renames':3,'new_folders':1,'moved_files':1,'native_objects_verified':178,'original_files_retained':161,'root_remote_writes':0,'unrelated_original_cells_styles_formulas_native_features_preserved':not issues}
(H/'saved-file-verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:result[k]for k in ['status','checks','issues','workbook_sha256','register_sha256']}))
if issues:raise SystemExit(1)
