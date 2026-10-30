"""Read the saved native workbook and independently check scoped names, paths and preservation."""
import collections,copy,hashlib,importlib.util,json,posixpath,sys
from pathlib import Path
from datetime import datetime,timezone
from urllib.parse import unquote,urlsplit,parse_qs
from xml.etree import ElementTree as E
H=Path(__file__).resolve().parent;BASE=H.parents[2]
read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
sp=importlib.util.spec_from_file_location('native',BASE/'components/reconciliation/image-identity-coverage-2026-10-20/verify_edit.py');n=importlib.util.module_from_spec(sp);sp.loader.exec_module(n);n.HERE=H
if '--attach' in sys.argv:n.attach()
b=n.load(H/'inputs/master_workbook.before');a=n.load(H/'master-workbook.pending');plan=read(H/'workbook-edit-plan.json');exp=read(H/'expected-edit.json');g=read(H/'canonical-master-register.json');old=read(H/'inputs/master_register.before');audit=read(H/'image-coverage-current.json');prioraudit=read(H/'inputs/audit.before')
issues=[];checks=0
def check(ok,msg):
 global checks
 checks+=1
 if not ok:issues.append(msg)
def rels(d,s):
 loc=s['part'];p=posixpath.join(posixpath.dirname(loc),'_rels',posixpath.basename(loc)+'.rels');return {x.get('Id'):x for x in E.fromstring(d['files'][p])} if p in d['files'] else {}
def links(d):
 out={}
 for sn,s in d['sheets'].items():
  rs=rels(d,s)
  for h in s['root'].findall('.//'+n.q('hyperlink')):
   t='#'+h.get('location') if h.get('location') else rs[h.get('{'+n.R+'}id')].get('Target');c=h.get('ref');out[(sn,c)]={'sheet':sn,'cell':c,'target':t,'label':d['values'][sn].get(c,'')}
 return out
def tables(d,s):
 rs=rels(d,s);out=[]
 for t in s['root'].findall('.//'+n.q('tablePart')):
  dest=rs[t.get('{'+n.R+'}id')].get('Target');part=dest.lstrip('/') if dest.startswith('/') else posixpath.normpath(posixpath.dirname(s['part'])+'/'+dest);out.append(d['files'][part])
 return out
changes={(x['sheet'],x['cell']):x['value'] for x in plan['cell_changes']};caches={(x['sheet'],x['cell']):x['expected'] for x in exp['formulas']};heights={(x['sheet'],str(x['row'])):x['height'] for x in plan['row_heights']}
style_changes={(x['sheet'],x['cell']):x['font']for x in plan.get('style_changes',[])}
check(list(a['sheets'])==list(b['sheets']) and len(a['sheets'])==21,'21 existing tabs and order')
for sn,s in b['sheets'].items():
 for c in set(b['values'][sn])|set(a['values'][sn]):
  want=changes.get((sn,c),caches.get((sn,c),b['values'][sn].get(c,'')));check(a['values'][sn].get(c,'')==want,sn+'!'+c+' scoped or preserved value')
  if (sn,c)not in style_changes:check(a['styles'][sn].get(c,'0')==b['styles'][sn].get(c,'0'),sn+'!'+c+' original style')
 check(a['formulas'][sn]==b['formulas'][sn],sn+' all formula text retained')
 for tag in ['sheetViews','sheetFormatPr','cols','mergeCells','conditionalFormatting','autoFilter','pageMargins','dataValidations','sheetProtection']:
  check([E.tostring(x) for x in s['root'].findall(n.q(tag))]==[E.tostring(x) for x in a['sheets'][sn]['root'].findall(n.q(tag))],sn+' preserved '+tag)
 check(tables(b,s)==tables(a,a['sheets'][sn]),sn+' original native tables')
 before={x.get('r'):dict(x.attrib) for x in s['root'].find(n.q('sheetData'))};after={x.get('r'):dict(x.attrib) for x in a['sheets'][sn]['root'].find(n.q('sheetData'))};check(set(before)==set(after),sn+' original rows')
 for r,attrs in before.items():
  want=copy.deepcopy(attrs);got=copy.deepcopy(after.get(r,{}))
  if (sn,r) in heights:want['ht']=heights[(sn,r)];want['customHeight']='1'
  if 'ht' in got and 'ht' in want:got['ht']=float(got['ht']);want['ht']=float(want['ht'])
  check(got==want,sn+' row '+r+' attributes')
 for c in a['sheets'][sn]['root'].findall('.//'+n.q('c')):check(c.get('t')!='e',sn+'!'+c.get('r')+' no cached error')
for tag in ['fonts','fills','borders','cellStyleXfs','cellXfs','numFmts','dxfs']:
 x=b['style_root'].find(n.q(tag));y=a['style_root'].find(n.q(tag));check(x is None or y is not None and len(y)>=len(x) and all(E.tostring(i)==E.tostring(j) for i,j in zip(x,y)),tag+' original resources retained')
actual=links(a);wanted={(x['sheet'],x['cell']):x for x in exp['hyperlinks']};oldlinks=links(b)
check(actual==wanted,'All native hyperlink targets and labels match the saved plan')
check(set(oldlinks)<=set(actual)and len(actual)==plan['expected_native_hyperlinks'],'All old hyperlink cells retained; only declared new role links added')
check(sum(map(len,a['formulas'].values()))==2729,'2729 original formulas retained')
for x in exp['formulas']:check(a['values'][x['sheet']][x['cell']]==x['expected'],'Recalculated summary '+x['sheet']+'!'+x['cell'])
bindings=read(H/'new-photo-bindings.json');affected={x['option_id']for x in bindings};roles={(x['option_id'],{'In situ':'in_situ','Series':'series'}[x['role']])for x in bindings}
check(len(bindings)==6 and len(affected)==5,'Exactly six new roles on five existing options')
check(len(g['options'])==184 and len(g['components'])==111,'184 working options and111 identified components retained')
allowed_option={'photo_coverage','photo_coverage_before_photo_gap_completion','current_photo_gap_review','context_before_photo_gap_completion','context_status','context_description','context_file_id','context_folder_id','context_image_url','context_folder_url'}
for x,y in zip(g['options'],old['options']):
 pid=x['product_id'];check(x['master_fields']==y['master_fields']and x['specifications']==y['specifications'],pid+' all six working fields and original assertions unchanged')
 for key in set(x)|set(y):
  if pid not in affected or key not in allowed_option:check(x.get(key)==y.get(key),pid+' original '+key)
 check(x['file_id']==y['file_id']and x['folder_id']==y['folder_id'],pid+' primary stable IDs unchanged')
for key in old:
 if key not in ['options','latest_image_coverage_audit','historical_image_coverage_audits','latest_terminal_photo_review','historical_terminal_photo_reviews']:check(g[key]==old[key],'Unchanged original graph layer '+key)
check(set(g)-set(old)=={'latest_photo_gap_completion'},'Only one new top-level current-review layer')
check(g['historical_image_coverage_audits']==old['historical_image_coverage_audits']+[old['latest_image_coverage_audit']],'All previous coverage audits retained')
check(g['historical_terminal_photo_reviews']==old['historical_terminal_photo_reviews']+[old['latest_terminal_photo_review']],'All previous terminal reviews retained')
check(g['latest_image_coverage_audit']['audit_sha256']==sha(H/'image-coverage-current.json'),'Current audit digest')
check(audit['identity_review']==prioraudit['identity_review'],'99 identity rows unchanged; no inferred FFL1 answer')
check(audit['counts']['required_picture_actions']==105 and audit['counts']['actions_by_type']=={'Verify existing image':1,'Find / capture':104,'Optional image':53},'105 remaining action rows')
check(audit['counts']['individual_statuses']==prioraudit['counts']['individual_statuses'],'Individual-image gap count26 retained until criterion is answered')
check(audit['counts']['in_situ_statuses']=={'Available':123,'No verified image':61},'123 available in situ;61 gaps')
check(audit['counts']['series_statuses']=={'Optional / no fixed set':53,'Available':113,'No verified image':18},'113 available series;18 gaps')
check(sum(x['status']=='Resolved'for x in audit['missing_pictures'])==53,'53 historical resolved actions retained')
for r in audit['coverage']:
 i=next(i for i in range(10,194)if a['values']['Photo Coverage'].get('A'+str(i))==r['option_id'])
 for role,sc,ic,fc,idc,dc in [('individual','C','D','E','M','N'),('in_situ','F','G','H','O','P'),('series','I','J','K','Q','R')]:
  check(a['values']['Photo Coverage'][sc+str(i)]==r[role]['status'],r['option_id']+' '+role+' status')
  ref=r[role]['reference']
  if ref:
   check(a['values']['Photo Coverage'].get(idc+str(i),'')==ref['file_id']and a['values']['Photo Coverage'].get(dc+str(i),'')==ref['folder_id'],r['option_id']+' '+role+' stable IDs')
   check(actual[('Photo Coverage',ic+str(i))]['target']==ref['image_url']and actual[('Photo Coverage',fc+str(i))]['target']==ref['folder_url'],r['option_id']+' '+role+' links')
for r in audit['missing_pictures']:
 i=next(i for i in range(10,221)if a['values']['Missing Pictures'].get('B'+str(i))==r['option_id']and a['values']['Missing Pictures'].get('D'+str(i))==r['role'])
 for col,key in [('F','action'),('K','scope'),('L','qualification'),('N','status')]:check(a['values']['Missing Pictures'].get(col+str(i),'')==r.get(key,''),r['option_id']+' '+r['role']+' '+key)
for (sn,cell),font in style_changes.items():
 xf=list(a['style_root'].find(n.q('cellXfs')))[int(a['styles'][sn][cell])];f=list(a['style_root'].find(n.q('fonts')))[int(xf.get('fontId'))];colour=f.find(n.q('color'));u=f.find(n.q('u'))
 check(colour is not None and colour.get('rgb','').endswith(font['color'][1:]),sn+'!'+cell+' new link colour')
 check(u is not None and u.get('val','single')=='single',sn+'!'+cell+' new link underline')
originals={x['file_id']:x for fn in ['context-original-verification.json','selected-original-verification.json']for x in read(H/fn)['originals']};md={x['file']['id']:x['file']for x in read(H/'selected-current-native-metadata.json')};live=read(H/'current-inventory.json');files={x['file_id']:x for x in live['entries']if x['object_type']=='file'};folders={x['file_id']:x for x in live['entries']if x['object_type']=='folder'}
check(not live['has_more']and len(files)==6633 and len(folders)==427,'Live scoped inventory complete at6633files427folders')
for fid,x in originals.items():check(sha(x['local_original'])==x['sha256'],'Verified selected original bytes '+fid)
for d in bindings:
 pid=d['option_id'];ref=d['reference'];fid=ref['file_id'];ff=files[fid];mm=md[fid];oo=originals[fid];check(ff['file']['size']==mm['size']==oo['bytes'],'Native source size '+d['binding_id']);check('ns:202238505/'+mm['path_display']==ref['path']==ff['path'],'Native source path '+d['binding_id']);check(folders[ref['folder_id']]['path']==posixpath.dirname(ff['path']),'Stable image parent '+d['binding_id']);check(oo['sha256']==d['current_original_sha256']and oo['dropbox_content_hash']==d['current_native_content_hash'],'Native original hash '+d['binding_id']);check(d['specification_changes']==d['new_options']==d['new_product_photographs']==0,'No physical/option/photo inference '+d['binding_id'])
 check(not next(x for x in audit['coverage']if x['option_id']==pid)[{'In situ':'in_situ','Series':'series'}[d['role']]]['physical_cast_or_size_certified'],'No measured cast certification '+d['binding_id'])
for x in g['options']:
 if x['product_id']in g['current_frozen_fish_size_policy']['affected_option_ids']:check('70'in x['master_fields']['Dimensions / depth']['display']and '15'in x['master_fields']['Dimensions / depth']['display'],x['product_id']+' current70×15cm face size retained')
oldowner=read(H/'inputs/owner_ledger.before');owner=read(H/'owner-ledger.pending.json')
for key in oldowner:
 if key!='updated_utc':check(owner[key]==oldowner[key],'Original owner ledger '+key)
check(owner['photo_review_scope_instructions'][-1]['decision_id']==read(H/'owner-decision.json')['decision_id'],'Owner size reaffirmation appended')
walk=read(H/'walkthrough.pending.json');oldwalk=read(H/'inputs/guided_review.before');check(walk['owner_answers']==oldwalk['owner_answers'],'No new owner identity answer fabricated')
check(walk['current_item']['case_sequence']=='exact-crop-criterion'and walk['deferred_review_items'][-1]['case_sequence']=='legacy-FFL1','Crop walkthrough replaces deferred legacy question')
queue=read(H/'photo-review-queue.json');check(len(queue)==111 and sum(x['review_state']=='RESOLVED_EXISTING_SOURCE_REFERENCE'for x in queue)==6,'All111 carried actions have review outcomes')
check(sum(x['review_state']=='EXACT_CROP_CANDIDATE_PENDING_OWNER_CRITERION'for x in queue)==17 and all(not x.get('crop_created')for x in queue),'17 crop candidates retained without an invented approval or derivative')
for x in read(H/'input-manifest.json').values():check(sha(x['path'])==sha(x['snapshot'])==x['sha256'],'Unchanged publication input '+x['path'])
check(read(H/'inputs/squarespace_hold.before')['status']=='OWNER_HOLD_NO_SQUARESPACE_WRITES','Squarespace owner hold preserved')
result={'status':'PASS'if not issues else'FAIL','recorded_utc':datetime.now(timezone.utc).isoformat(),'checks':checks,'issues':issues[:80],'workbook_sha256':sha(H/'master-workbook.pending'),'register_sha256':sha(H/'canonical-master-register.json'),'audit_sha256':sha(H/'image-coverage-current.json'),'sheet_count':21,'native_hyperlinks':len(actual),'formula_count':2729,'cell_changes':len(changes),'row_heights_extended':len(heights),'new_visual_roles':6,'new_individual_images':0,'specification_changes':0,'new_options':0,'remaining_required_actions':105,'individual_gaps':26,'in_situ_gaps':61,'series_gaps':18,'exact_crop_candidates':17,'legacy_identity_deferred':True,'native_mutations':0}
(H/'saved-file-verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result))
if issues:raise SystemExit(1)
