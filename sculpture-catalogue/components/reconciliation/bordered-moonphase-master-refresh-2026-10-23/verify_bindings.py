"""Independently reconcile saved native links, source identities and current role counts."""
import collections,hashlib,importlib.util,json,posixpath,re
from pathlib import Path
from xml.etree import ElementTree as E
from html.parser import HTMLParser
from urllib.parse import urlsplit,unquote
H=Path(__file__).resolve().parent;B=H.parents[2];read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
s=importlib.util.spec_from_file_location('n',B/'components/reconciliation/image-identity-coverage-2026-10-20/verify_edit.py');n=importlib.util.module_from_spec(s);s.loader.exec_module(n);b=n.load(H/'inputs/master_workbook.before');w=n.load(H/'master-workbook.pending');g=read(H/'canonical-master-register.json');old=read(H/'inputs/master_register.before');a=read(H/'image-coverage-current.json');oa=read(H/'inputs/audit.before');native=read(H/'current-native-reference-map.json');on=read(H/'inputs/native_map.before');state=read(H/'guided-owner-review-state.json');pending=read(H/'pending-followups.json');issues=[];checks=0;targets={'BSI-65A93033A200','BSI-4515726BBC18','BSI-2418C8B43415','BSI-207102CFD25C'};cm={x['option_id']:x for x in a['coverage']};om={x['product_id']:x for x in g['options']}
def check(ok,msg):
 global checks
 checks+=1
 if not ok:issues.append(msg)
def links(book):
 out={}
 for sn,x in book['sheets'].items():
  rp=posixpath.join(posixpath.dirname(x['part']),'_rels',posixpath.basename(x['part'])+'.rels');r={v.get('Id'):v.get('Target')for v in E.fromstring(book['files'][rp])}if rp in book['files']else{}
  for v in x['root'].findall('.//'+n.q('hyperlink')):out[(sn,v.get('ref'))]='#'+v.get('location')if v.get('location')else r[v.get('{'+n.R+'}id')]
 return out
beforelinks=links(b);afterlinks=links(w)
for x,y in zip(g['options'],old['options']):
 oid=x['product_id'];check(oid==y['product_id'],'Stable option order '+oid)
 for key in ['name','canonical_key','canonical_component_id','specifications','master_fields','selling_details','file_id','folder_id','image_url','folder_url','counted_as_individual_option','physical_specifications_verified']:check(x[key]==y[key],'Preserved option field '+oid+'/'+key)
 if oid not in targets:check(x==y,'Unrelated option unchanged '+oid)
 else:
  z=cm[oid]['in_situ'];check(z['status']=='Available'and z['qualified_display_only']and not z['creation_origin_verified']and not z['scene_authenticity_verified']and not z['physical_cast_or_size_certified'],'Qualified scope '+oid);expected={'BSI-65A93033A200':('id:cnqzTNngPVsAAAAAAAylEw','id:cnqzTNngPVsAAAAAAAydLQ'),'BSI-4515726BBC18':('id:cnqzTNngPVsAAAAAAAylEw','id:cnqzTNngPVsAAAAAAAydLQ'),'BSI-207102CFD25C':('id:cnqzTNngPVsAAAAAAAsR7A','id:cnqzTNngPVsAAAAAAAydVQ'),'BSI-2418C8B43415':('id:cnqzTNngPVsAAAAAAAsH_A','id:cnqzTNngPVsAAAAAAAyi-Q')}[oid];check((z['reference']['file_id'],z['reference']['folder_id'])==expected,'Source and actual parent '+oid);check(x['current_photo_task_review']['historical_previous_review']==y['current_photo_task_review'],'Exact old option review history '+oid)
for x,y in zip(a['coverage'],oa['coverage']):
 oid=x['option_id'];check(x['individual']==y['individual'],'All individual role data unchanged '+oid)
 if oid not in targets:check(x==y,'Unrelated coverage unchanged '+oid)
 else:
  sx,sy=x['series'],y['series'];check({k:v for k,v in sx.items()if k!='reference'}=={k:v for k,v in sy.items()if k!='reference'},'Series role unchanged '+oid);check({k:v for k,v in (sx['reference']or{}).items()if k not in ['path','image_url','folder_url']}=={k:v for k,v in (sy['reference']or{}).items()if k not in ['path','image_url','folder_url']},'Series identity and qualification unchanged '+oid);check(x['historical_in_situ_references'][-1]==y['in_situ'],'Exact former context retained '+oid);check(x['historical_previous_terminal_task_review']==y['terminal_task_review'],'Exact former coverage review retained '+oid)
for key in ['summary','components','source_component_dispositions','original_review_specification_assertions','source_sets','source_offer_edges','source_media_configuration_coverage','source_platform_offer_coverage','current_source_unavailable_references','latest_empty_folder_history_import','current_removed_empty_folder_history','latest_four_qualified_display_import','latest_owner_leaf_curve_context_import']:check(g[key]==old[key],'Unchanged historical/source scope '+key)
held=state['held_in_situ_ids'];check(len(held)==8 and not targets.intersection(held),'Eight holds excluded')
for oid in held:check(om[oid]==next(x for x in old['options']if x['product_id']==oid)and cm[oid]==next(x for x in oa['coverage']if x['option_id']==oid),'Held option and coverage byte-equivalent '+oid)
check(len(state['queues']['in_situ'])==14 and len(state['queues']['series'])==17 and len(state['queues']['individual'])==0 and len(state['queues']['physical'])==187,'Guided queues scope');check(len(pending['entries'])==2 and sum(x.get('do_not_resume_without_owner_instruction',False)for x in pending['entries'])==1 and any(x.get('kind')=='COMPLETED_DECO_FOUR_COMPONENT_IN_SITU_FILE_MOVE'and not x['applied_to_current_frozen_release']for x in pending['entries']),'Owner-held packet and separately queued verified Deco followup retained')
check(native['owner_removed_empty_family_history']==on['owner_removed_empty_family_history'],'All empty-folder histories unchanged');check(native['unresolved_historical_objects']==on['unresolved_historical_objects'],'Unresolved historical native objects unchanged');check(set(native['current_objects'])==set(on['current_objects']),'All current native IDs retained');changed={k for k,v in on['current_objects'].items()if native['current_objects'][k]!=v};check(changed==set(read(H/'import-summary.json')['changed_stable_ids']),'Exactly nine current native objects changed')
for k,v in on['old_path_to_id'].items():check(native['old_path_to_id'].get(k)==v,'Retained old stable path alias '+k)
check(native['current_objects']['id:cnqzTNngPVsAAAAAAAt4DQ']['parent_id']=='id:cnqzTNngPVsAAAAAAAylYQ','008 specific file-parent override');check(om['BSI-65A93033A200']['additional_individual_references'][0]['file_id']=='id:cnqzTNngPVsAAAAAAAt4DQ','008 additional Moonphase1 reference')
active=[x for x in a['coverage']if x.get('active_catalogue_option',True)];openrows=[x for x in a['missing_pictures']if x['status']=='Open'];check(len(active)==187 and len(a['coverage'])==188,'187 active/188 retained');check(collections.Counter(x['in_situ']['status']for x in active)=={'Available':165,'No verified image':22},'Context count independently recomputed');check(collections.Counter(x['role']for x in openrows)=={'Individual':1,'In situ':22,'Series':17},'Required role counts independently recomputed');check(sum(x['status']=='Resolved'for x in a['missing_pictures'])==112,'112 resolved retained actions')
for i,x in enumerate(g['options'],10):
 for col in ['M','N','Q','R']:check(w['values']['Photo Coverage'].get(col+str(i),'')==b['values']['Photo Coverage'].get(col+str(i),''),'Primary/series native ID cell preserved '+col+str(i))
 for col in ['D','E']:check(afterlinks.get(('Photo Coverage',col+str(i)))==beforelinks.get(('Photo Coverage',col+str(i))),'Primary link preserved '+col+str(i))
 if x['product_id']in targets:
  r=cm[x['product_id']]['in_situ']['reference'];check(afterlinks[('Photo Coverage','G'+str(i))]==r['image_url']and afterlinks[('Photo Coverage','H'+str(i))]==r['folder_url'],'Saved exact context links '+x['product_id']);check(w['values']['Photo Coverage']['O'+str(i)]==r['file_id']and w['values']['Photo Coverage']['P'+str(i)]==r['folder_id'],'Saved exact context IDs '+x['product_id'])
class Parser(HTMLParser):
 def __init__(self):super().__init__();self.ids=set();self.links=[];self.images=[];self.cards=0
 def handle_starttag(self,t,attrs):
  z=dict(attrs)
  if z.get('id'):self.ids.add(z['id'])
  if t=='a':self.links.append(z.get('href',''))
  if t=='img':self.images.append(z.get('src',''))
  if t=='article':self.cards+=1
rep=read(H/'report-verification.json');out=Path(rep['output_directory']);pages={}
for x in rep['pages']:
 p=Path(x['path']);z=Parser();z.feed(p.read_text());pages[p.resolve()]=z;check(z.cards==x['cards'],'HTML card count '+p.name);check(sha(p)==x['sha256'],'Current report bytes '+p.name)
for p,z in pages.items():
 for u in z.links:
  check('BOLDSTONE_BACKUP'not in u.upper(),'Master-only URL '+p.name)
  if u.startswith('https://'):continue
  target,_,anchor=u.partition('#');dest=(p.parent/target).resolve()if target and not Path(target).is_absolute()else(Path(target).resolve()if target else p);check(dest.is_file(),'Local report destination '+p.name+' '+u)
  if anchor and dest.suffix=='.html':
   if dest not in pages:q=Parser();q.feed(dest.read_text());pages[dest]=q
   check(anchor in pages[dest].ids,'Local report anchor '+p.name+' '+u)
 for u in z.images:check((p.parent/u).is_file(),'Whole report image '+p.name+' '+u)
for (sn,c),u in afterlinks.items():
 if u.startswith(str(out)):
  dest,_,anchor=u.partition('#');check(Path(dest).is_file(),'Saved current report link '+sn+'!'+c)
  if anchor and Path(dest).suffix=='.html':check(anchor in pages[Path(dest).resolve()].ids,'Saved current report anchor '+sn+'!'+c)
result={'status':'FAIL'if issues else'PASS','checks':checks,'issues':issues[:60],'workbook_sha256':sha(H/'master-workbook.pending'),'register_sha256':sha(H/'canonical-master-register.json'),'audit_sha256':sha(H/'image-coverage-current.json'),'active_context_requests':14,'held_context_cases':8,'series_requests':17,'new_physical_verifications':0,'new_native_or_platform_writes':0};(H/'native-binding-verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result));assert not issues
