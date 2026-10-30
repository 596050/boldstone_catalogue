"""Independent checks of current source scope and affected bindings in the saved workbook."""
import hashlib,importlib.util,json,posixpath,re
from pathlib import Path
from datetime import datetime,timezone
from urllib.parse import unquote
from xml.etree import ElementTree as E
H=Path(__file__).resolve().parent;B=H.parents[2];read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
s=importlib.util.spec_from_file_location('v',B/'components/reconciliation/image-identity-coverage-2026-10-20/verify_edit.py');v=importlib.util.module_from_spec(s);s.loader.exec_module(v)
w=v.load(H/'master-workbook.pending');g=read(H/'canonical-master-register.json');a=read(H/'image-coverage-current.json');old=read(H/'inputs/master_register.before');olda=read(H/'inputs/audit.before');issues=[];checks=0
def check(test,message):
 global checks
 checks+=1
 if not test:issues.append(message)
badids={'id:cnqzTNngPVsAAAAAAA6LRw','id:cnqzTNngPVsAAAAAAA6LRQ','id:cnqzTNngPVsAAAAAAA6LRA'}
alllinks={}
for sn,z in w['sheets'].items():
 rp=posixpath.join(posixpath.dirname(z['part']),'_rels',posixpath.basename(z['part'])+'.rels');rs={x.get('Id'):x.get('Target')for x in E.fromstring(w['files'][rp])}if rp in w['files']else{}
 for x in z['root'].findall('.//'+v.q('hyperlink')):
  u='#'+x.get('location')if x.get('location')else rs[x.get('{'+v.R+'}id')];alllinks[(sn,x.get('ref'))]=u
  check('BOLDSTONE_BACKUP'not in unquote(u).upper(),'No backup native link '+sn+'!'+x.get('ref'))
 for c,x in w['values'][sn].items():
  if isinstance(x,str):check(x not in badids,'No active backup ID '+sn+'!'+c)
opts={x['product_id']:x for x in g['options']};cov={x['option_id']:x for x in a['coverage']};oldcov={x['option_id']:x for x in olda['coverage']}
for oid in ['BSI-C41824131174','BSI-3635E3DC3434']:
 row=g['options'].index(opts[oid])+10;r=str(row);c=cov[oid]
 check(c['series']['status']=='No verified image'and c['series']['reference']['file_id']=='Unbound','Current Master series unavailable '+oid)
 check(c['series'].get('owner_decision_id')==oldcov[oid]['series'].get('owner_decision_id'),'Owner identity association preserved '+oid)
 check(w['values']['Photo Coverage']['I'+r]=='No verified image'and w['values']['Photo Coverage']['Q'+r]=='Unbound','Saved series status and ID '+oid)
 check(('Photo Coverage','J'+r)not in alllinks,'No false current series hyperlink '+oid)
 actions=[x for x in a['missing_pictures']if x['option_id']==oid and x['role']=='Series'];check(len(actions)==1 and actions[0]['status']=='Open'and actions[0]['action_type']=='Find / capture','Series photo action reopened '+oid)
sand=opts['BSI-C41824131174'];check(sand['file_id']=='Unbound'and not sand['image_url']and not sand['folder_id'],'Sandstone has no current image or false containing parent')
check(sand['current_family_folder_id']=='id:cnqzTNngPVsAAAAAAAt_GA','Master family stable ID retained separately')
for x,y in zip(g['options'],old['options']):
 for key in ['product_id','name','canonical_component_id','specifications','master_fields','selling_details']:check(x[key]==y[key],'Identity/specification/offer unchanged '+x['product_id']+'/'+key)
for x in a['coverage']:
 if x['option_id']not in ['BSI-C41824131174','BSI-3635E3DC3434']:
  for role in ['individual','in_situ','series']:
   prior=oldcov[x['option_id']][role];now=x[role];check(now['status']==prior['status']and(now.get('reference')or{}).get('file_id')==(prior.get('reference')or{}).get('file_id'),'Other approved role/ID retained '+x['option_id']+'/'+role)
immutable={'specifications','master_fields','selling_details','original_review_specification_assertions','source_only_assertions_not_applied_to_options','input_manifest','master_input_manifest','source_ref','master_ref','evidence_ref'}
def scan(z,path):
 if isinstance(z,dict):
  for k,x in z.items():
   if k not in immutable and not k.startswith(('historical_','prior_','before_','candidate_review_before_')):scan(x,path+'/'+k)
 elif isinstance(z,list):
  for i,x in enumerate(z):scan(x,path+'/'+str(i))
 elif isinstance(z,str):check('BOLDSTONE_BACKUP'not in unquote(z).upper()and z not in badids,'Current source graph scope '+path)
scan(g,'register');scan(a,'audit')
for p in (B/'outputs/master-only-source-correction-2026-10-23').glob('*'):
 if p.suffix in ['.html','.csv']:check('BOLDSTONE_BACKUP'not in unquote(p.read_text()).upper(),'No backup source in current report '+p.name)
counts=a['counts'];check(counts['required_picture_actions']==73 and counts['actions_by_type']['Find / capture']==72 and counts['resolved_action_rows']==81,'Current action totals73/72/81')
check(counts['in_situ_statuses']['No verified image']==53 and counts['series_statuses']['No verified image']==18,'Context gaps53/18')
live=read(H/'live-master-evidence.json');check(not live['listing']['has_more']and len(live['listing']['entries'])==95,'Current Master folder scan complete')
check(all('/BOLDSTONE MASTER/'in x['path']for x in live['listing']['entries']),'Every checked current native object is in Master')
result={'status':'FAIL'if issues else'PASS','recorded_utc':datetime.now(timezone.utc).isoformat(),'checks':checks,'issues':issues[:50],'workbook_sha256':sha(H/'master-workbook.pending'),'register_sha256':sha(H/'canonical-master-register.json'),'audit_sha256':sha(H/'image-coverage-current.json'),'current_option_count':188,'in_situ_gaps':53,'series_gaps':18,'source_scope':'BOLDSTONE MASTER only','new_native_mutations':0}
(H/'native-binding-verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:result[k]for k in ['status','checks','issues']}))
if issues:raise SystemExit(1)
