"""Independent scoped record and source-identity checks after the native-link export."""
import hashlib,importlib.util,json,posixpath
from pathlib import Path
from datetime import datetime,timezone
from xml.etree import ElementTree as E
from html.parser import HTMLParser
H=Path(__file__).resolve().parent;B=H.parents[2]
read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
s=importlib.util.spec_from_file_location('n',B/'components/reconciliation/image-identity-coverage-2026-10-20/verify_edit.py');n=importlib.util.module_from_spec(s);s.loader.exec_module(n)
g=read(H/'canonical-master-register.json');old=read(H/'inputs/master_register.before');a=read(H/'image-coverage-current.json');prior=read(H/'inputs/audit.before');nm=read(H/'current-native-reference-map.json');scope=read(H/'path-refresh-scope.json');m=read(H/'input-manifest.json');w=n.load(H/'master-workbook.pending');oid='BSI-83F1AACE15E9';checks=0;issues=[]
def check(ok,label):
 global checks
 checks+=1
 if not ok:issues.append(label)
for x,y in zip(g['options'],old['options']):
 for k in ['product_id','name','canonical_key','canonical_component_id','specifications','master_fields','selling_details','sale_unit','counted_as_individual_option','physical_specifications_verified','file_id','folder_id']:check(x[k]==y[k],'Protected option field '+x['product_id']+' '+k)
check(g['summary']==old['summary'] and len(g['options'])==188 and len(g['active_option_ids'])==187 and len(g['components'])==112,'Active/history and component populations unchanged')
check(g['latest_owner_leaf_curve_context_import']==old['latest_owner_leaf_curve_context_import'],'Leaf Curve scoped approval retained intact')
for key in ['catalogue_retirements','retired_option_ids','wall_sculpture_customisation_policy','current_frozen_fish_size_policy','original_review_specification_assertions','wall_circle_native_options']:check(g[key]==old[key],'Retained policy/source '+key)
oldmap={x['product_id']:x for x in old['options']};newmap={x['product_id']:x for x in g['options']}
for ident in ['BSI-CF0CC1EB8F96','BSI-5181D32AA24F','BSI-C41824131174','BSI-3635E3DC3434']:check(newmap[ident]==oldmap[ident],'Unchanged accepted/pending/retired record '+ident)
for x,y in zip(a['coverage'],prior['coverage']):
 for role in ['individual','in_situ','series']:
  check(x[role]['status']==('No verified image'if x['option_id']==oid and role=='in_situ'else y[role]['status']),'Role status '+x['option_id']+' '+role)
  if role!='in_situ'or x['option_id']!=oid:check((x[role].get('reference')or{}).get('file_id')==(y[role].get('reference')or{}).get('file_id'),'Source file ID '+x['option_id']+' '+role)
check(len(a['missing_pictures'])==209 and len(prior['missing_pictures'])==208,'One source-gap action added')
for x,y in zip(a['missing_pictures'],prior['missing_pictures']):
 for k in ['option_id','name','role','status','action_type','action','qualification','owner_response']:check(x.get(k)==y.get(k),'Existing action retained '+x['option_id']+' '+k)
task=a['missing_pictures'][-1];check(task['option_id']==oid and task['role']=='In situ' and task['status']=='Open','Only new Rust replacement request')
check(a['counts']['in_situ_statuses']=={'Available':139,'No verified image':48}and a['counts']['series_statuses']['No verified image']==17 and a['counts']['required_picture_actions']==66 and a['counts']['resolved_action_rows']==86 and a['counts']['retired_action_rows']==3,'Current role/action counts')
final={}
for i in range(6):
 d=read(m['overlay'+str(i)]['snapshot'])
 for z in d.get('objects',[]):final[z['file_id']]=z
missing=set(scope['unavailable_file_ids']);check(len(final)==539 and len(missing)==4,'539 sealed packet objects and4 explicit source exceptions')
for fid,z in final.items():
 if fid in missing:
  check(fid not in nm['current_objects']and fid in nm['unresolved_historical_objects'],'Unresolved source kept outside verified current map '+fid);continue
 x=nm['current_objects'][fid]
 for k,key in [('path','current_path'),('name','current_name'),('parent_id','current_parent_id'),('object_type','object_type')]:check(x[k]==z[key],'Verified stable object '+fid+' '+k)
 if x['object_type']=='file':check(x['size']==z['size'],'Source file size '+fid)
for c in a['coverage']:
 if c['in_situ']['status']=='Available':check((c['in_situ'].get('reference')or{}).get('file_id')not in missing,'No unavailable file remains an active context reference '+c['option_id'])
check('id:cnqzTNngPVsAAAAAAAyeeQ'not in nm['current_objects']and 'id:cnqzTNngPVsAAAAAAAyeeQ'in nm['owner_removed_empty_family_history'],'Empty Sally family position has no live link')
oldnm=read(m['native_map']['snapshot'])
for fid in ['id:cnqzTNngPVsAAAAAAA51Jg','id:cnqzTNngPVsAAAAAAAt8mA']:check(nm['current_objects'][fid]==oldnm['current_objects'][fid],'Sally workshop folder/original unchanged '+fid)
links={}
for sn,info in w['sheets'].items():
 rp=posixpath.join(posixpath.dirname(info['part']),'_rels',posixpath.basename(info['part'])+'.rels');rs={z.get('Id'):z.get('Target')for z in E.fromstring(w['files'][rp])}
 for z in info['root'].findall('.//'+n.q('hyperlink')):links[(sn,z.get('ref'))]='#'+z.get('location')if z.get('location')else rs[z.get('{'+n.R+'}id')]
for key in [('Master Catalogue','T162'),('Master Catalogue','U162'),('Photo Coverage','G162'),('Photo Coverage','H162')]:check(key not in links,'No active broken context hyperlink '+str(key))
for key,value in [(('Missing Pictures','B218'),oid),(('Missing Pictures','D218'),'In situ'),(('Missing Pictures','N218'),'Open'),(('Photo Coverage','F162'),'No verified image'),(('Photo Coverage','D4'),139),(('Missing Pictures','B4'),65)]:check(w['values'][key[0]][key[1]]==value,'Saved source/action result '+str(key))
ref=next(c for c in a['coverage']if c['option_id']==oid)['individual']['reference']
check(links[('Missing Pictures','G218')]==ref['image_url']and links[('Missing Pictures','H218')]==ref['folder_url'],'New request links to verified individual source and actual parent')
class Anchors(HTMLParser):
 def __init__(self):super().__init__();self.ids=set()
 def handle_starttag(self,t,attrs):
  d=dict(attrs)
  if d.get('id'):self.ids.add(d['id'])
for page in ['current-context-references.html','unavailable-native-references.html']:
 p=B/'outputs'/H.name/page;z=Anchors();z.feed(p.read_text())
 for target in links.values():
  if target.startswith(str(p)+'#'):check(target.split('#',1)[1]in z.ids,'Native saved proof link has actual report anchor '+target)
for key,x in m.items():check(sha(x['path'])==sha(x['snapshot'])==x['sha256'],'Frozen source '+key)
check(read(H/'source-evidence-verification.json')['status']=='PASS_WITH_EXPLICIT_SOURCE_GAP','Explicit source-gap preflight retained')
r={'status':'FAIL'if issues else'PASS','recorded_utc':datetime.now(timezone.utc).isoformat(),'checks':checks,'issues':issues,'workbook_sha256':sha(H/'master-workbook.pending'),'register_sha256':sha(H/'canonical-master-register.json'),'audit_sha256':sha(H/'image-coverage-current.json'),'current_verified_packet_objects':535,'unresolved_historical_source_ids':4,'new_native_or_platform_writes':0,'new_image_role_approvals':0,'source_gap_roles_added':1,'native_hyperlinks':len(links)}
(H/'native-binding-verification.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps({k:r[k]for k in ['status','checks','issues','native_hyperlinks']}))
if issues:raise SystemExit(1)
