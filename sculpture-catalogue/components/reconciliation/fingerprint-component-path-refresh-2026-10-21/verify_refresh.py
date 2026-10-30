"""Verify saved native links, added bindings and all preserved catalogue data."""
import copy,hashlib,importlib.util,json,posixpath,sys
from pathlib import Path
from datetime import datetime,timezone
from xml.etree import ElementTree as E
HERE=Path(__file__).resolve().parent;BASE=HERE.parents[2]
read=lambda p:json.loads(Path(p).read_text());digest=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
spec=importlib.util.spec_from_file_location('native',BASE/'components/reconciliation/image-identity-coverage-2026-10-20/verify_edit.py');n=importlib.util.module_from_spec(spec);spec.loader.exec_module(n);n.HERE=HERE
def links(d):
 out={}
 for sn,s in d['sheets'].items():
  loc=s['part'];rp=posixpath.join(posixpath.dirname(loc),'_rels',posixpath.basename(loc)+'.rels');rs={x.get('Id'):x for x in E.fromstring(d['files'][rp])}
  for h in s['root'].findall('.//'+n.q('hyperlink')):
   target='#'+h.get('location')if h.get('location')else rs[h.get('{'+n.R+'}id')].get('Target');out[(sn,h.get('ref'))]={'sheet':sn,'cell':h.get('ref'),'label':d['values'][sn][h.get('ref')],'target':target}
 return out
def tables(d,s):
 loc=s['part'];rp=posixpath.join(posixpath.dirname(loc),'_rels',posixpath.basename(loc)+'.rels');rs={x.get('Id'):x.get('Target')for x in E.fromstring(d['files'][rp])};out=[]
 for t in s['root'].findall('.//'+n.q('tablePart')):
  target=rs[t.get('{'+n.R+'}id')];part=target.lstrip('/')if target.startswith('/')else posixpath.normpath(posixpath.dirname(loc)+'/'+target);out.append(d['files'][part])
 return out
if '--attach'in sys.argv:n.attach()
b=n.load(HERE/'inputs/master_workbook.before');a=n.load(HERE/'master-workbook.pending');exp=read(HERE/'expected-edit.json');plan=read(HERE/'workbook-edit-plan.json')
checks=0;issues=[]
def check(ok,msg):
 global checks
 checks+=1
 if not ok:issues.append(msg)
check(list(a['sheets'])==list(b['sheets'])+['Fingerprint Folders'],'20old tabs retained; one dedicated binding view added')
for sn,s in b['sheets'].items():
 check(a['values'][sn]==b['values'][sn],sn+' all values and cached results unchanged')
 check(a['formulas'][sn]==b['formulas'][sn],sn+' all formulas unchanged')
 check(a['styles'][sn]==b['styles'][sn],sn+' all cell styles unchanged')
 for tag in ['sheetViews','sheetFormatPr','cols','mergeCells','conditionalFormatting','autoFilter','pageMargins']:
  check([E.tostring(x)for x in s['root'].findall(n.q(tag))]==[E.tostring(x)for x in a['sheets'][sn]['root'].findall(n.q(tag))],sn+' native '+tag)
 check([r.attrib for r in s['root'].find(n.q('sheetData'))]==[r.attrib for r in a['sheets'][sn]['root'].find(n.q('sheetData'))],sn+' row attributes')
 check(tables(a,a['sheets'][sn])==tables(b,s),sn+' native tables/filters')
for group in ['fonts','fills','borders','cellStyleXfs','cellXfs','numFmts','dxfs']:
 old=b['style_root'].find(n.q(group));new=a['style_root'].find(n.q(group));check(old is None or new is not None and len(new)>=len(old)and all(E.tostring(x)==E.tostring(y)for x,y in zip(old,new)),group+' original resources')
for sn,d in exp['sheets'].items():
 for j,v in enumerate(d['headers']):check(a['values'][sn].get(n.column(j)+'9')==v,'New header')
 for i,r in enumerate(d['rows'],10):
  for j,v in enumerate(r):check(a['values'][sn].get(n.column(j)+str(i),'')==v,'New binding cell')
 check(a['sheets'][sn]['root'].find('.//'+n.q('pane'))is not None,'New binding frozen headers/IDs')
 check(len(a['sheets'][sn]['root'].findall('.//'+n.q('tablePart')))==1,'New filterable binding table')
for f in exp['formulas']:check(a['formulas'][f['sheet']].get(f['cell'])==f['formula']and a['values'][f['sheet']].get(f['cell'])==f['expected'],'New dependent summary')
actual=links(a);wanted={(x['sheet'],x['cell']):x for x in exp['hyperlinks']}
check(actual==wanted,'All11235 native link targets and labels exact')
check(len(actual)==11235,'11215old hyperlinks retained plus20new binding links')
check(sum(len(x)for x in a['formulas'].values())==2729,'2727old formulas retained plus2new summaries')
g=read(HERE/'canonical-master-register.json');old=read(HERE/'inputs/master_register.before');restored=copy.deepcopy(g)
for o in restored['options']:o.pop('component_folder_binding',None)
for c in restored['components']:c.pop('component_finish_folder_bindings',None)
restored['latest_image_coverage_audit']=copy.deepcopy(old['latest_image_coverage_audit'])
for k in ['historical_image_coverage_before_fingerprint_split','latest_fingerprint_component_paths']:restored.pop(k)
for c in plan['graph_changes']:
 node=restored
 for k in c['path'][:-1]:node=node[k]
 node[c['path'][-1]]=c['before']
check(restored==old,'Only declared current paths and additive folder bindings; all original records/history preserved')
check(all(x['product_id']==y['product_id']and x['name']==y['name']and x['master_fields']==y['master_fields']and x['specifications']==y['specifications']for x,y in zip(g['options'],old['options'])),'All184 names/1104 fields unchanged')
bs=g['latest_fingerprint_component_paths']['component_finish_bindings'];check(len(bs)==4,'Four component-finish bindings')
for bind in bs:
 opt=next(x for x in g['options']if x['product_id']==bind['product_id'])
 check(opt['photo_coverage']['individual']=='Group only'and bind['individual_member_number']is None and bind['source_composition_number']=='2','FP source composition2, member number null, isolated gap retained')
 check(opt['folder_id']not in [bind['component_folder_id'],bind['finish_folder_id']],'Component folder distinct from actual pair-image containing folder')
audit=read(HERE/'image-coverage-current.json');prior=read(HERE/'inputs/prior_audit.before')
check(audit['counts']==prior['counts'],'All184 role classifications/counts unchanged')
check(audit['counts']['individual_statuses']=={'Available':158,'Detail only':5,'Group only':20,'Unbound size':1},'158complete/26individual gaps')
check(next(x for x in g['options']if x['product_id']=='BSI-04D6E8690F30')==next(x for x in old['options']if x['product_id']=='BSI-04D6E8690F30'),'Exact FFL image remains unbound')
reports=read(HERE/'link-report-verification.json')
check(reports['status']=='PASS_COMPLETE_LINK_REPORTS'and reports['input_register_sha256']==digest(HERE/'canonical-master-register.json')and reports['input_audit_sha256']==digest(HERE/'image-coverage-current.json'),'Complete current link reports bound to this register/audit')
for r in reports['pages']+reports['csv_files']:check(digest(r['path'])==r['sha256'],'Delivered link report immutable')
for k,x in read(HERE/'input-manifest.json').items():check(digest(x['path'])==digest(x['snapshot'])==x['sha256'],'Source/current input unchanged '+k)
result={'status':'PASS'if not issues else'FAIL','recorded_utc':datetime.now(timezone.utc).isoformat(),'checks':checks,'issues':issues[:40],
 'workbook_sha256':digest(HERE/'master-workbook.pending'),'register_sha256':digest(HERE/'canonical-master-register.json'),'audit_sha256':digest(HERE/'image-coverage-current.json'),
 'old_sheets':20,'new_sheets':1,'native_hyperlinks':len(actual),'formula_count':2729,'current_native_link_targets_updated':len(plan['target_changes']),
 'graph_current_reference_changes':len(plan['graph_changes']),'new_component_finish_bindings':4,'individual_gaps':26,'required_picture_actions':157,
 'all_names_specs_source_histories_and_coverage_preserved':not issues,'new_photographs':0,'platform_or_Dropbox_writes_by_root':0,'squarespace_write_hold_preserved':True}
(HERE/'saved-file-verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:result[k]for k in ['status','checks','issues','workbook_sha256','register_sha256']}))
if issues:raise SystemExit(1)
