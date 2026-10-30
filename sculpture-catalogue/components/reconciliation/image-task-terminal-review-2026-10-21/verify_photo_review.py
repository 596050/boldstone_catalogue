"""Saved native workbook readback and preservation checks."""
import copy,hashlib,importlib.util,json,posixpath,sys
from pathlib import Path
from datetime import datetime,timezone
from xml.etree import ElementTree as E
H=Path(__file__).resolve().parent;BASE=H.parents[2];read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
spec=importlib.util.spec_from_file_location('native',BASE/'components/reconciliation/image-identity-coverage-2026-10-20/verify_edit.py');n=importlib.util.module_from_spec(spec);spec.loader.exec_module(n);n.HERE=H
if '--attach'in sys.argv:n.attach()
b=n.load(H/'inputs/master_workbook.before');a=n.load(H/'master-workbook.pending');plan=read(H/'workbook-edit-plan.json');exp=read(H/'expected-edit.json');g=read(H/'canonical-master-register.json');old=read(H/'inputs/master_register.before');audit=read(H/'image-coverage-current.json');items=read(H/'terminal-review-items.json')
issues=[];checks=0
def check(ok,msg):
 global checks
 checks+=1
 if not ok:issues.append(msg)
def rels(d,s):
 loc=s['part'];p=posixpath.join(posixpath.dirname(loc),'_rels',posixpath.basename(loc)+'.rels');return{x.get('Id'):x for x in E.fromstring(d['files'][p])}if p in d['files']else{}
def links(d):
 out={}
 for sn,s in d['sheets'].items():
  rs=rels(d,s)
  for h in s['root'].findall('.//'+n.q('hyperlink')):
   t='#'+h.get('location')if h.get('location')else rs[h.get('{'+n.R+'}id')].get('Target');c=h.get('ref');out[(sn,c)]={'sheet':sn,'cell':c,'target':t,'label':d['values'][sn].get(c,'')}
 return out
def tables(d,s):
 rs=rels(d,s);out=[]
 for t in s['root'].findall('.//'+n.q('tablePart')):
  dest=rs[t.get('{'+n.R+'}id')].get('Target');part=dest.lstrip('/')if dest.startswith('/')else posixpath.normpath(posixpath.dirname(s['part'])+'/'+dest);out.append(d['files'][part])
 return out
changes={(x['sheet'],x['cell']):x['value']for x in plan['cell_changes']};caches={(x['sheet'],x['cell']):x['expected']for x in exp['formulas']};heights={(x['sheet'],str(x['row'])):x['height']for x in plan['row_heights']}
style_changes={(x['sheet'],x['cell']):x['font']for x in plan.get('style_changes',[])}
check(list(a['sheets'])==list(b['sheets'])and len(a['sheets'])==21,'All21 tabs retained in order')
for sn,s in b['sheets'].items():
 for c in set(b['values'][sn])|set(a['values'][sn]):
  want=changes.get((sn,c),caches.get((sn,c),b['values'][sn].get(c,'')));check(a['values'][sn].get(c,'')==want,sn+'!'+c+' scoped or preserved value')
  if(sn,c)not in style_changes:check(a['styles'][sn].get(c,'0')==b['styles'][sn].get(c,'0'),sn+'!'+c+' style preserved')
 check(a['formulas'][sn]==b['formulas'][sn],sn+' formulas preserved')
 for tag in ['sheetViews','sheetFormatPr','cols','mergeCells','conditionalFormatting','autoFilter','pageMargins','dataValidations','sheetProtection']:
  check([E.tostring(x)for x in s['root'].findall(n.q(tag))]==[E.tostring(x)for x in a['sheets'][sn]['root'].findall(n.q(tag))],sn+' preserved '+tag)
 check(tables(b,s)==tables(a,a['sheets'][sn]),sn+' native tables preserved')
 before={x.get('r'):dict(x.attrib)for x in s['root'].find(n.q('sheetData'))};after={x.get('r'):dict(x.attrib)for x in a['sheets'][sn]['root'].find(n.q('sheetData'))};check(set(before)==set(after),sn+' row identities')
 for r,attrs in before.items():
  want=copy.deepcopy(attrs);got=copy.deepcopy(after.get(r,{}))
  if(sn,r)in heights:want['ht']=heights[(sn,r)];want['customHeight']='1'
  if'ht'in got and'ht'in want:got['ht']=float(got['ht']);want['ht']=float(want['ht'])
  check(got==want,sn+' row '+r+' attributes')
 for cell in a['sheets'][sn]['root'].findall('.//'+n.q('c')):check(cell.get('t')!='e',sn+'!'+cell.get('r')+' no cached formula error')
for tag in ['fonts','fills','borders','cellStyleXfs','cellXfs','numFmts','dxfs']:
 x=b['style_root'].find(n.q(tag));y=a['style_root'].find(n.q(tag));check(x is None or y is not None and len(y)>=len(x)and all(E.tostring(i)==E.tostring(j)for i,j in zip(x,y)),tag+' original resources preserved')
for(sn,c),f in style_changes.items():
 xf=list(a['style_root'].find(n.q('cellXfs')))[int(a['styles'][sn][c])];font=list(a['style_root'].find(n.q('fonts')))[int(xf.get('fontId'))];colour=font.find(n.q('color'));u=font.find(n.q('u'))
 check(colour is not None and colour.get('rgb','').endswith(f['color'][1:]),sn+'!'+c+' current link color')
 check((u is not None and u.get('val','single')=='single')if f['underline']=='single'else(u is None or u.get('val')=='none'),sn+'!'+c+' current link underline')
actual=links(a);wanted={(x['sheet'],x['cell']):x for x in exp['hyperlinks']};check(actual==wanted,'All native hyperlinks match saved expected targets/labels')
check(len(actual)==11197,'11197 native links after removing unverified role links')
check(sum(map(len,a['formulas'].values()))==2729,'2729 formulas retained')
for x in exp['formulas']:check(a['values'][x['sheet']][x['cell']]==x['expected'],'Summary cache '+x['sheet']+'!'+x['cell'])
allowed={'photo_coverage','current_photo_task_review','prior_context_before_terminal_review','context_status','context_description','context_image_url','context_folder_url','context_file_id','context_folder_id'}
check(len(g['options'])==184 and len(g['components'])==111,'184 options /111 component identities')
for x,y in zip(g['options'],old['options']):
 for k in set(x)|set(y):
  if k not in allowed:check(x.get(k)==y.get(k),x['product_id']+' preserved '+k)
check(sum(len(x['master_fields'])for x in g['options'])==1104,'1104 working field groups preserved')
for k in old:
 if k not in ['options','latest_image_coverage_audit','historical_image_coverage_audits']:check(g[k]==old[k],'Preserved graph layer '+k)
check(g['historical_image_coverage_audits']==old['historical_image_coverage_audits']+[old['latest_image_coverage_audit']],'Prior image audits retained')
check(g['latest_image_coverage_audit']['audit_sha256']==sha(H/'image-coverage-current.json'),'Current audit hash')
check(g['latest_terminal_photo_review']['ledger_sha256']==sha(H/'terminal-review-items.json'),'Current per-item ledger hash')
check(len(items)==157 and all(x['review_state']!='QUEUED'and x['findings']for x in items),'All157 actions individually reviewed')
check(sum(x['review_state']=='RESOLVED_VERIFIED_REFERENCE'for x in items)==15,'15 visual image associations resolved')
check(audit['counts']['required_picture_actions']==142 and audit['counts']['actions_by_type']=={'Find / capture':111,'Verify existing image':31,'Optional image':53},'142 required /111find-size /31binding /53optional')
check(audit['counts']['individual_statuses']=={'Available':158,'Detail only':5,'Group only':20,'Unbound size':1},'158 complete individual views /26 gaps unchanged')
check(len(audit['missing_pictures'])==211 and sum(x['status']=='Resolved'for x in audit['missing_pictures'])==16,'211 historical actions /16 resolved including prior Cup')
for r in audit['coverage']:
 i=next(i for i in range(10,194)if a['values']['Photo Coverage'].get('A'+str(i))==r['option_id'])
 for role,c,ic,fc,idc,dc in [('individual','C','D','E','M','N'),('in_situ','F','G','H','O','P'),('series','I','J','K','Q','R')]:
  check(a['values']['Photo Coverage'][c+str(i)]==r[role]['status'],r['option_id']+' '+role+' current status')
  ref=r[role]['reference']
  if ref:
   check(a['values']['Photo Coverage'].get(idc+str(i),'')==ref['file_id']and a['values']['Photo Coverage'].get(dc+str(i),'')==ref['folder_id'],r['option_id']+' '+role+' stable IDs')
   check(actual[("Photo Coverage",ic+str(i))]['target']==ref['image_url']and actual[("Photo Coverage",fc+str(i))]['target']==ref['folder_url'],r['option_id']+' '+role+' current hyperlinks')
  elif role!='individual':check(("Photo Coverage",ic+str(i))not in actual,r['option_id']+' '+role+' absent verified reference has no active role link')
for x in audit['missing_pictures']:
 i=next(i for i in range(10,221)if a['values']['Missing Pictures'].get('B'+str(i))==x['option_id']and a['values']['Missing Pictures'].get('D'+str(i))==x['role'])
 for c,k in [('E','action_type'),('F','action'),('K','scope'),('L','qualification'),('N','status')]:check(a['values']['Missing Pictures'].get(c+str(i),'')==x.get(k,''),x['option_id']+' action '+k)
 for c,k in [('I','file_id'),('J','folder_id')]:check(a['values']['Missing Pictures'].get(c+str(i),'')==x['reference'][k],x['option_id']+' action '+k)
 check(all(x['reference'].get(k)for k in ['file_id','folder_id','image_url','folder_url']),x['option_id']+' action complete evidence link')
for x in read(H/'input-manifest.json').values():check(sha(x['path'])==sha(x['snapshot'])==x['sha256'],'Unchanged input '+x['path'])
check(g['current_cup_colour_reference_paths']['catalogue_options_added']==0 and all(x['physical_finish_status']=='UNCONFIRMED'for x in g['current_cup_colour_reference_paths']['objects']),'Cup appearance-only folder projection')
check(not list((H/'temporary').glob('*.json')),'No private expiring download URLs retained')
result={'status':'PASS'if not issues else'FAIL','recorded_utc':datetime.now(timezone.utc).isoformat(),'checks':checks,'issues':issues[:80],'workbook_sha256':sha(H/'master-workbook.pending'),'register_sha256':sha(H/'canonical-master-register.json'),'audit_sha256':sha(H/'image-coverage-current.json'),'sheet_count':21,'native_hyperlinks':len(actual),'formula_count':2729,'cell_changes':len(changes),'row_heights_extended':len(heights),'reviewed_actions':157,'resolved_this_review':15,'remaining_required_actions':142,'individual_image_gaps':26,'find_capture_or_size_binding':111,'existing_image_checks':31,'all184_names_1104_fields_and_source_layers_preserved':not issues,'physical_claims_upgraded':0,'root_remote_mutations':0}
(H/'saved-file-verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result))
if issues:raise SystemExit(1)
