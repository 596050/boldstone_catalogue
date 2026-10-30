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
check(list(a['sheets'])==list(b['sheets']) and len(a['sheets'])==21,'21 existing tabs and order')
for sn,s in b['sheets'].items():
 for c in set(b['values'][sn])|set(a['values'][sn]):
  want=changes.get((sn,c),caches.get((sn,c),b['values'][sn].get(c,'')));check(a['values'][sn].get(c,'')==want,sn+'!'+c+' scoped or preserved value')
  check(a['styles'][sn].get(c,'0')==b['styles'][sn].get(c,'0'),sn+'!'+c+' original style')
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
check(len(actual)==len(oldlinks)==11197,'11197 native hyperlinks retained')
check(sum(map(len,a['formulas'].values()))==2729,'2729 original formulas retained')
for x in exp['formulas']:check(a['values'][x['sheet']][x['cell']]==x['expected'],'Recalculated summary '+x['sheet']+'!'+x['cell'])
names=read(H/'owner-decision.json')['option_names'];compnames={'BC-MSW-SPIRAL':'Moon and Shellwave 1','BC-MSW-MOON':'Moon and Shellwave 2'}
check(len(g['options'])==184 and len(g['components'])==111,'184 options on111 identified components retained')
for x,y in zip(g['options'],old['options']):
 pid=x['product_id'];check(x['product_id']==y['product_id'] and x['canonical_component_id']==y['canonical_component_id'] and x['canonical_key']==y['canonical_key'],pid+' stable canonical identity')
 check(x['master_fields']==y['master_fields'] and x['specifications']==y['specifications'],pid+' all working and source specifications unchanged')
 check(x['name']==names.get(pid,y['name']),pid+' exact approved display name')
 check(x['family']==('Moon and Shellwave' if pid in names else y['family']),pid+' scoped family')
 check(x['file_id']==y['file_id'] and x['folder_id']==y['folder_id'],pid+' stable primary file/folder IDs')
 for key in ['source_scopes','source_product_sha256','related_platform_offer_refs','source_supported_platform_scope_refs','orientation_options','size_class','build_class','customisation_policy_ref','offered_customisation_axes','other_customisations_available']:
  check(x.get(key)==y.get(key),pid+' retained '+key)
 if pid in names:check(all(v in x['retained_names'] for v in y['retained_names']),pid+' all historical names retained')
for x,y in zip(g['components'],old['components']):
 cid=x['component_id'];check(x['component_id']==y['component_id'] and x['option_ids']==y['option_ids'] and x['option_count']==y['option_count'],cid+' component and option membership')
 check(x['name']==compnames.get(cid,y['name']),cid+' approved component name')
 if cid in compnames:check(x['retained_names'][:len(y['retained_names'])]==y['retained_names'],cid+' historical names/codes retained')
# Unrelated source, policy and platform evidence layers must be byte-equivalent JSON values.
for key in ['original_review_specification_assertions','source_only_assertions_not_applied_to_options','source_component_dispositions','confirmed_arrangement_member_edges','source_integrity_policy','source_platform_offer_coverage','latest_listing_resolution','latest_listing_reconciliation','listing_resolution_source_edges','listing_resolution_native_action_drafts','wall_circle_native_options','wall_sculpture_customisation_policy','current_frozen_fish_size_policy','latest_owner_configuration_update','latest_fingerprint_component_paths','latest_moon_fishwave_current_paths']:
 if key=='source_platform_offer_coverage':
  # Source offer facts survive; only explicitly current target display labels may change.
  aa=copy.deepcopy(g[key]);bb=old[key]
  for xx,yy in zip(aa,bb):
   for kk in ['target_details','candidate_scope_details']:xx[kk]=copy.deepcopy(yy.get(kk,xx.get(kk))) if kk in xx else None
   for kk in list(xx):
    if xx[kk] is None and kk not in yy:del xx[kk]
  check(aa==bb,'Source offer coverage facts retained outside current target labels')
 else:check(g[key]==old[key],'Unchanged source/policy/platform layer '+key)
def restore(z,log):
 z=copy.deepcopy(z)
 for c in reversed(log):
  p=z
  for k in c['path'][:-1]:p=p[k]
  key=c['path'][-1]
  if c['kind']=='added':check(p[key]==c['after'],'Declared added current field');del p[key]
  elif c['kind']=='changed':check(p[key]==c['after'],'Declared changed current field');p[key]=copy.deepcopy(c['before'])
  else:p[key]=copy.deepcopy(c['before'])
 return z
check(restore(g,read(H/'register-change-log.json'))==old,'All graph changes exactly journaled; prior graph recoverable')
check(restore(audit,read(H/'audit-change-log.json'))==prioraudit,'All audit changes exactly journaled; prior audit recoverable')
check(g['historical_image_coverage_audits']==old['historical_image_coverage_audits']+[old['latest_image_coverage_audit']],'Previous coverage audits retained')
check(g['historical_terminal_photo_reviews']==old.get('historical_terminal_photo_reviews',[])+[old['latest_terminal_photo_review']],'Previous terminal reviews retained')
check(g['latest_image_coverage_audit']['audit_sha256']==sha(H/'image-coverage-current.json'),'Current audit hash')
check(audit['counts']['required_picture_actions']==111 and audit['counts']['actions_by_type']=={'Find / capture':110,'Verify existing image':1,'Optional image':53},'111 required actions; one existing-image/identity check')
check(audit['counts']['individual_statuses']==prioraudit['counts']['individual_statuses'],'Individual photograph gaps remain26')
check(audit['counts']['in_situ_statuses']==prioraudit['counts']['in_situ_statuses'],'In situ roles unchanged')
check(audit['counts']['series_statuses']==dict(collections.Counter(x['series']['status'] for x in audit['coverage'])),'Series counts recomputed from184 records')
check(sum(x['status']=='Resolved' for x in audit['missing_pictures'])==47,'47 historical resolved actions retained')
for r in audit['coverage']:
 i=next(i for i in range(10,194) if a['values']['Photo Coverage'].get('A'+str(i))==r['option_id'])
 check(a['values']['Photo Coverage']['B'+str(i)]==r['name'],r['option_id']+' displayed coverage name')
 for role,sc,ic,fc,idc,dc in [('individual','C','D','E','M','N'),('in_situ','F','G','H','O','P'),('series','I','J','K','Q','R')]:
  check(a['values']['Photo Coverage'][sc+str(i)]==r[role]['status'],r['option_id']+' '+role+' status')
  ref=r[role]['reference']
  if ref:
   check(a['values']['Photo Coverage'].get(idc+str(i),'')==ref['file_id'] and a['values']['Photo Coverage'].get(dc+str(i),'')==ref['folder_id'],r['option_id']+' '+role+' stable IDs')
   check(actual[('Photo Coverage',ic+str(i))]['target']==ref['image_url'] and actual[('Photo Coverage',fc+str(i))]['target']==ref['folder_url'],r['option_id']+' '+role+' current links')
for r in audit['missing_pictures']:
 i=next(i for i in range(10,221) if a['values']['Missing Pictures'].get('B'+str(i))==r['option_id'] and a['values']['Missing Pictures'].get('D'+str(i))==r['role'])
 for col,key in [('C','name'),('F','action'),('K','scope'),('L','qualification'),('N','status')]:check(a['values']['Missing Pictures'].get(col+str(i),'')==r.get(key,''),r['option_id']+' '+r['role']+' '+key)
wf=next(x for x in audit['coverage'] if x['option_id']=='BSI-D886F539DD3E');pewter=next(x for x in audit['coverage'] if x['option_id']=='BSI-3635E3DC3434')
check(wf['series']['status']=='Available' and wf['individual']['status']=='Group only','Moon1 series resolved while isolated photo remains open')
check(pewter['series']['status']=='Available' and pewter['individual']['status']=='Detail only','Pewter series resolved while full individual photo remains open')
check(pewter['series']['member_position']=='UPRIGHT PANEL AT BACK RIGHT','Exact owner Pewter position retained')
sandstone=next(x for x in audit['coverage'] if x['option_id']=='BSI-C41824131174')
check(sandstone['series']['status']=='Available' and sandstone['individual']['status']=='Detail only','Sandstone series resolved while full individual photo remains open')
check(sandstone['series']['member_position']=='UPRIGHT PANEL AT BACK CENTRE','Exact owner Sandstone position retained')
for x in g['imported_owner_review_packets']:
 check(sha(BASE/x['path'])==x['sha256'],'Sealed owner packet '+x['decision_id'])
lo=next(x for x in audit['identity_review'] if x['case_id']=='SHELLWAVE-WATER-LOWER');check(lo['canonical_component_id']=='BC-MSW-MOON' and lo['canonical_option_count_increment']==0,'Lower curved moon maps to existing member2; no new option')
# Independently read back the full native scoped inventory and compare every stable object.
overlay=read(H/'dropbox-current-reference-overlay.json');native=read(H/'root-independent-dropbox-readback.json');objects={x['file_id']:x for x in overlay['objects']}
check(sha(H/'dropbox-current-reference-overlay.json')=='9e3889b2d2f13a2bd773313fdf153876960acad68c7f021e8a5cbc8de502e2d2','Sealed directory overlay hash')
for x in overlay['receipts']:check(sha(x['path'])==x['sha256'],'Sealed native operation receipt '+x['path'])
check(overlay['verification']['status']=='PASS' and overlay['verification']['counts']['pending_native_jobs']==0,'All ten native folder renames complete')
check(not native['subtree']['has_more'] and len(native['subtree']['entries'])==200,'Independent scoped native inventory complete')
ids={x['file_id'] for x in native['subtree']['entries']}|{native['family']['folder']['id']};check(ids==set(objects),'Independent live readback preserves all201 stable IDs')
for x in native['subtree']['entries']:
 o=objects[x['file_id']];check(x['path']=='ns:202238505/'+o['current_path'] and x['name']==o['current_name'] and x['object_type']==o['object_type'],'Independent current path/name/type '+x['file_id'])
 if x['object_type']=='file':check(x['file']['size']==o['size'],'Independent native size '+x['file_id'])
newroot=overlay['family']['current_path'];allpaths={x['current_path'] for x in objects.values()};newlinks=0
for key,h in actual.items():
 u=urlsplit(h['target']);p=unquote(u.path)
 check('Moon & Shellwave' not in p,'No stale Moon and Shellwave native target '+str(key))
 if p.startswith('/home'+newroot):
  newlinks+=1;folder=p[len('/home'):];preview=parse_qs(u.query).get('preview',[])
  check(folder in allpaths,'Native target folder exists '+str(key))
  if preview:check(folder+'/'+preview[0] in allpaths,'Native target image exists '+str(key))
for x in g['options']:
 if x['product_id'] in names:
  check(x['folder_url']==objects[x['folder_id']]['current_native_url'],'Current option containing-folder link '+x['product_id'])
  u=urlsplit(x['image_url']);fp=unquote(u.path)[len('/home'):].rstrip('/')+'/'+parse_qs(u.query)['preview'][0]
  check(fp==objects[x['file_id']]['current_path'],'Current option image link '+x['product_id'])
oldowner=read(H/'inputs/owner_ledger.before');newowner=read(H/'owner-ledger.pending.json')
for key in oldowner:
 if key not in ['updated_utc','image_design_identity_decisions','catalogue_naming_corrections']:check(newowner[key]==oldowner[key],'Preserved owner ledger '+key)
check(newowner['image_design_identity_decisions'][:-3]==oldowner.get('image_design_identity_decisions',[]),'All previous owner image answers retained')
check(newowner['catalogue_naming_corrections'][:-1]==oldowner['catalogue_naming_corrections'],'All previous naming answers retained')
walk=read(H/'walkthrough.pending.json');oldwalk=read(H/'inputs/guided_review.before')
check(walk['owner_answers'][:-3]==oldwalk['owner_answers'] and [x['case_sequence'] for x in walk['owner_answers'][-3:]]==[139,154,155] and walk['current_item']['case_sequence']=='legacy-FFL1','Three owner answers saved; legacy Frozen Fish remains with review lane B')
check(walk['current_item']['option_id']=='BSI-04D6E8690F30' and walk['current_item']['candidate_reference']['file_id']==next(x for x in g['options'] if x['product_id']=='BSI-FE10273D3655')['file_id'],'Legacy FFL1 question compares exact FFS2 primary')
for x in read(H/'input-manifest.json').values():check(sha(x['path'])==sha(x['snapshot'])==x['sha256'],'Unchanged publication input '+x['path'])
check(read(H/'inputs/squarespace_hold.before')['status']=='OWNER_HOLD_NO_SQUARESPACE_WRITES','Owner Squarespace hold retained')
result={'status':'PASS' if not issues else 'FAIL','recorded_utc':datetime.now(timezone.utc).isoformat(),'checks':checks,'issues':issues[:80],'workbook_sha256':sha(H/'master-workbook.pending'),'register_sha256':sha(H/'canonical-master-register.json'),'audit_sha256':sha(H/'image-coverage-current.json'),'sheet_count':21,'native_hyperlinks':len(actual),'updated_native_link_targets':sum(actual[k]['target']!=oldlinks[k]['target'] for k in actual),'current_family_link_targets_checked':newlinks,'formula_count':2729,'cell_changes':len(changes),'row_heights_extended':len(heights),'new_options':0,'new_components':0,'specification_changes':0,'remaining_required_actions':111,'existing_image_checks':1,'native_folder_renames':10,'all201_Dropbox_IDs_preserved':True,'platform_mutations':0}
(H/'saved-file-verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result))
if issues:raise SystemExit(1)
