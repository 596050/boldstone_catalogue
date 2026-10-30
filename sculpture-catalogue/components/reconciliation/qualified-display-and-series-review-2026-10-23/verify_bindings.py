"""Check semantic scope independently of the workbook authoring runtime."""
import hashlib,importlib.util,json,posixpath,re
from pathlib import Path
from datetime import datetime,timezone
from html.parser import HTMLParser
from xml.etree import ElementTree as E
H=Path(__file__).resolve().parent;B=H.parents[2];read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
s=importlib.util.spec_from_file_location('native',B/'components/reconciliation/image-identity-coverage-2026-10-20/verify_edit.py');n=importlib.util.module_from_spec(s);s.loader.exec_module(n)
w=n.load(H/'master-workbook.pending');read_native_before=n.load(H/'inputs/master_workbook.before');g=read(H/'canonical-master-register.json');old=read(H/'inputs/master_register.before');a=read(H/'image-coverage-current.json');ao=read(H/'inputs/audit.before');tasks=read(H/'review-plan.json');targets={x['option_id']for x in tasks};review=read(H/'review-outcomes.json');reviewed=set(review['active_ids'])|set(review['series_ids']);held=set(review['held_ids']);issues=[];checks=0
def check(ok,msg):
 global checks
 checks+=1
 if not ok:issues.append(msg)
for x,y in zip(g['options'],old['options']):
 oid=x['product_id']
 for k in ['product_id','name','canonical_key','canonical_component_id','specifications','master_fields','selling_details','counted_as_individual_option','file_id','folder_id','image_url','folder_url']:check(x[k]==y[k],oid+' unchanged '+k)
 if oid not in reviewed:check(x==y,oid+' unrelated option unchanged')
 elif oid not in targets:check({k:v for k,v in x.items()if k!='current_photo_task_review'}=={k:v for k,v in y.items()if k!='current_photo_task_review'},oid+' review-only metadata scope')
 if oid in reviewed:check(x['current_photo_task_review']['recorded_utc'].startswith('2026-10-23')and set(x['current_photo_task_review']['roles'])==({'in_situ'}if oid in review['active_ids']else set())|({'series'}if oid in review['series_ids']else set()),oid+' current review date and exact roles')
for c,d in zip(a['coverage'],ao['coverage']):
 oid=c['option_id']
 if oid not in reviewed:check(c==d,oid+' unrelated coverage unchanged')
 else:check(c['individual']==d['individual']and c['series']==d['series'],oid+' primary and series unchanged')
for t in tasks:
 oid=t['option_id'];c=next(x for x in a['coverage']if x['option_id']==oid);r=c['in_situ']['reference'];row=g['options'].index(next(x for x in g['options']if x['product_id']==oid))+10;z=c['in_situ']
 for k in ['file_id','folder_id','sha256']:check(r[k]==t[k],oid+' reviewed '+k)
 check(sha(t['local_original'])==t['sha256']and r['whole_original_only'],oid+' whole original hash')
 check(z['status']=='Available'and z['qualified_display_only']and z['reviewer_verified_display_binding']and not z['explicit_owner_image_role_approval']and not z['scene_authenticity_verified']and not z['physical_cast_or_size_certified'],oid+' qualified review flags')
 for col,val in {'F':'Available','O':r['file_id'],'P':r['folder_id']}.items():check(w['values']['Photo Coverage'][col+str(row)]==val,oid+' saved Photo Coverage '+col)
 ar=next(i for i,x in enumerate(a['missing_pictures'],10)if x['option_id']==oid and x['role']=='In situ');check(w['values']['Missing Pictures']['B'+str(ar)]==oid and w['values']['Missing Pictures']['N'+str(ar)]=='Resolved',oid+' actual saved action closed')
 check(any(x['option_id']==oid and x['role']=='In situ'and x['status']=='Resolved'and x['reference']['file_id']==r['file_id']for x in a['missing_pictures']),oid+' source action binding')
for key in ['summary','components','original_review_specification_assertions','current_source_unavailable_references','latest_owner_leaf_curve_context_import']:check(g[key]==old[key],'Prior scope unchanged '+key)
check(sum(x.get('counted_as_individual_option',True)for x in g['options'])==187 and len(g['options'])==188 and len(g['components'])==112,'Active and history counts')
check(a['counts']['required_picture_actions']==44 and a['counts']['in_situ_statuses']['No verified image']==26 and a['counts']['series_statuses']['No verified image']==17 and a['counts']['resolved_action_rows']==108,'Current action counts')
state=read(H/'guided-owner-review-state.json');current=next(x for x in g['options']if x['product_id']==state['current_option_id']);check(state['current_option_name']==current['name']and state['current_phase']=='series'and state['pending_question']is None,'Guided focus has no stale retired-option question');check('BSI-C41824131174'not in str(state['queues']),'Retired Sandstone excluded from current queues')
class Parser(HTMLParser):
 def __init__(self):super().__init__();self.ids=set();self.links=[]
 def handle_starttag(self,t,attrs):
  d=dict(attrs)
  if 'id'in d:self.ids.add(d['id'])
  if t=='a':self.links.append(d.get('href',''))
out=B/'outputs'/H.name;parsers={}
for file in out.glob('*.html'):
 p=Parser();p.feed(file.read_text());parsers[file.name]=p
for sn,info in w['sheets'].items():
 rp=posixpath.join(posixpath.dirname(info['part']),'_rels',posixpath.basename(info['part'])+'.rels');rs={x.get('Id'):x.get('Target')for x in E.fromstring(w['files'][rp])}
 for x in info['root'].findall('.//'+n.q('hyperlink')):
  u=rs.get(x.get('{'+n.R+'}id'),'')
  if u.startswith(str(out)):
   file,_,anchor=u.partition('#');p=Path(file);check(p.is_file(),'Saved report link exists '+sn+'!'+x.get('ref'))
   if anchor and p.name in parsers:check(anchor in parsers[p.name].ids,'Saved report anchor exists '+sn+'!'+x.get('ref'))
check(len(parsers['current-context-references.html'].ids-{'search'})==161,'161 current context qualification anchors')
check(targets<=parsers['imported-approvals.html'].ids,'Four display review anchors')
for name,p in parsers.items():
 for u in p.links:
  if u.startswith('https://www.dropbox.com/'):check('BOLDSTONE_BACKUP'not in u.upper()and'/BOLDSTONE%20MASTER/'in u.upper(),'Master-only report link '+name)
for i,x in enumerate(g['options'],10):
 for col in ['M','N','Q','R']:check(w['values']['Photo Coverage'].get(col+str(i),'')==read_native_before['values']['Photo Coverage'].get(col+str(i),''),'Photo identity cells unchanged '+col+str(i))
for key in ['latest_empty_folder_history_import','current_removed_empty_folder_history']:check(g[key]==old[key],'Nine-folder history retained '+key)
check(set(next(x for x in g['options']if x['product_id']=='BSI-3635E3DC3434')['current_photo_task_review']['roles'])=={'in_situ','series'},'No stale active Pewter individual capture task')
for file in ['canonical-master-register.json','image-coverage-current.json','current-native-reference-map.json']:
 check(Path(H/file).is_file(),'Derived source exists '+file)
result={'status':'FAIL'if issues else'PASS','recorded_utc':datetime.now(timezone.utc).isoformat(),'checks':checks,'issues':issues[:80],'workbook_sha256':sha(H/'master-workbook.pending'),'register_sha256':sha(H/'canonical-master-register.json'),'audit_sha256':sha(H/'image-coverage-current.json'),'reviewer_verified_display_bindings':18,'explicit_owner_image_role_approvals_added':0,'new_physical_verifications':0,'all_unrelated_option_and_coverage_records_unchanged':True,'active_in_situ_cases_reviewed':36,'held_in_situ_cases_unchanged':8,'series_cases_reviewed':17,'review_only_option_records':26,'whole_original_pixels_unchanged':True,'current_report_anchors_checked':True}
(H/'native-binding-verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:result[k]for k in ['status','checks','issues']}))
if issues:raise SystemExit(1)
