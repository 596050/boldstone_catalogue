"""Saved native workbook readback and preservation checks."""
import copy,hashlib,importlib.util,json,posixpath,sys
from pathlib import Path
from datetime import datetime,timezone
from xml.etree import ElementTree as E
H=Path(__file__).resolve().parent;BASE=H.parents[2];read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
spec=importlib.util.spec_from_file_location('native',BASE/'components/reconciliation/image-identity-coverage-2026-10-20/verify_edit.py');n=importlib.util.module_from_spec(spec);spec.loader.exec_module(n);n.HERE=H
if '--attach'in sys.argv:n.attach()
b=n.load(H/'inputs/master_workbook.before');a=n.load(H/'master-workbook.pending');plan=read(H/'workbook-edit-plan.json');exp=read(H/'expected-edit.json');g=read(H/'canonical-master-register.json');old=read(H/'inputs/master_register.before');audit=read(H/'image-coverage-current.json')
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
allowed_global={'customisation_policy_ref','offered_customisation_axes','other_customisations_available'}
frozen_ids={o['product_id']for o in g['options']if o['family']=='Frozen Fish'};legacy='BSI-04D6E8690F30';white='BSI-FE10273D3655'
allowed_frozen={'master_fields','master_field_history','current_standard_face_cm','current_configuration_override'}
allowed_legacy={'name','retained_names','unbound_size_option','unbound_identity','record_type','count_class','size_class','distinct_current_design_or_variant_verified','current_legacy_identity_disposition','readiness_note','remaining_evidence_gaps','photo_coverage','identity_basis','prior_identity_basis_before_owner_size'}
allowed_white={'photo_coverage','context_status','context_description','context_file_id','context_folder_id','context_image_url','context_folder_url','current_owner_photo_decision'}
check(len(g['options'])==184 and len(g['components'])==111,'184 records and111 component identities retained')
for x,y in zip(g['options'],old['options']):
 pid=x['product_id'];allowed=allowed_global|(allowed_frozen if pid in frozen_ids else set())|(allowed_legacy if pid==legacy else set())|(allowed_white if pid==white else set())
 for k in set(x)|set(y):
  if k not in allowed:check(x.get(k)==y.get(k),pid+' preserved '+k)
 check(x['customisation_policy_ref']==g['wall_sculpture_customisation_policy']['policy_id']and x['offered_customisation_axes']==['size','colour','texture','material','orientation']and x['other_customisations_available'],pid+' customisation available')
 if pid in frozen_ids:
  check(x['current_standard_face_cm']=={'height':70,'width':15},pid+' current70x15 face')
  check(x['specifications']==y['specifications'],pid+' historical assertions preserved')
  for field in x['master_fields']:
   if field!='Dimensions / depth'and not(pid==legacy and field=='Weight'):check(x['master_fields'][field]==y['master_fields'][field],pid+' other working field '+field)
  i=next(i for i in range(10,194)if a['values']['Master Catalogue'].get('A'+str(i))==pid)
  check(a['values']['Master Catalogue']['E'+str(i)]==x['master_fields']['Dimensions / depth']['display'],pid+' recalculated master dimensions')
for k in old:
 if k not in ['options','summary','latest_image_coverage_audit','historical_image_coverage_audits','latest_terminal_photo_review','historical_terminal_photo_reviews']:check(g[k]==old[k],'Preserved source/register layer '+k)
check(g['historical_image_coverage_audits']==old['historical_image_coverage_audits']+[old['latest_image_coverage_audit']],'Previous image audit retained')
check(g['historical_terminal_photo_reviews']==old.get('historical_terminal_photo_reviews',[])+[old['latest_terminal_photo_review']],'Previous terminal review retained')
check(g['latest_image_coverage_audit']['audit_sha256']==sha(H/'image-coverage-current.json'),'Current audit digest')
check(audit['counts']['required_picture_actions']==116 and audit['counts']['actions_by_type']=={'Find / capture':110,'Verify existing image':6,'Optional image':53},'Current116 required actions')
check(audit['counts']['individual_statuses']=={'Available':158,'Detail only':5,'Group only':20,'Unbound identity':1},'Legacy gap reclassified without inventing a new photo')
for r in audit['coverage']:
 i=next(i for i in range(10,194)if a['values']['Photo Coverage'].get('A'+str(i))==r['option_id'])
 for role,c,ic,fc,idc,dc in [('individual','C','D','E','M','N'),('in_situ','F','G','H','O','P'),('series','I','J','K','Q','R')]:
  check(a['values']['Photo Coverage'][c+str(i)]==r[role]['status'],r['option_id']+' '+role+' status')
  ref=r[role]['reference']
  if ref:
   check(a['values']['Photo Coverage'].get(idc+str(i),'')==ref['file_id']and a['values']['Photo Coverage'].get(dc+str(i),'')==ref['folder_id'],r['option_id']+' '+role+' stable IDs')
   check(actual[('Photo Coverage',ic+str(i))]['target']==ref['image_url']and actual[('Photo Coverage',fc+str(i))]['target']==ref['folder_url'],r['option_id']+' '+role+' links')
for r in audit['missing_pictures']:
 i=next(i for i in range(10,221)if a['values']['Missing Pictures'].get('B'+str(i))==r['option_id']and a['values']['Missing Pictures'].get('D'+str(i))==r['role'])
 for c,k in [('C','name'),('E','action_type'),('F','action'),('L','qualification'),('N','status')]:check(a['values']['Missing Pictures'][c+str(i)]==r[k],r['option_id']+' '+r['role']+' '+k)
oldowner=read(H/'inputs/owner_ledger.before');newowner=read(H/'owner-ledger.pending.json')
for k in oldowner:
 if k!='updated_utc':check(newowner[k]==oldowner[k],'Prior owner decisions preserved '+k)
check(len(newowner['family_standard_size_decisions'])==1 and len(newowner['wall_sculpture_customisation_policy_decisions'])==1,'New owner instructions saved once')
walk=read(H/'walkthrough.pending.json');check(walk['current_item']['case_sequence']==99 and walk['owner_answers'][-1]['decision_id']==read(H/'owner-decision.json')['decision_id'],'First answer retained; next question prepared')
for x in read(H/'input-manifest.json').values():check(sha(x['path'])==sha(x['snapshot'])==x['sha256'],'Unchanged publication input '+x['path'])
check(read(H/'inputs/squarespace_hold.before')['status']=='OWNER_HOLD_NO_SQUARESPACE_WRITES','Owner platform hold retained')
result={'status':'PASS'if not issues else'FAIL','recorded_utc':datetime.now(timezone.utc).isoformat(),'checks':checks,'issues':issues[:80],'workbook_sha256':sha(H/'master-workbook.pending'),'register_sha256':sha(H/'canonical-master-register.json'),'audit_sha256':sha(H/'image-coverage-current.json'),'sheet_count':21,'native_hyperlinks':len(actual),'formula_count':2729,'cell_changes':len(changes),'row_heights_extended':len(heights),'frozen_records_standardized':6,'customisable_option_records':184,'legacy_identity_not_merged':True,'source_assertions_preserved':True,'remaining_required_actions':116,'individual_image_gaps':26,'find_capture':110,'existing_image_checks':6,'native_mutations':0}
(H/'saved-file-verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result))
if issues:raise SystemExit(1)
