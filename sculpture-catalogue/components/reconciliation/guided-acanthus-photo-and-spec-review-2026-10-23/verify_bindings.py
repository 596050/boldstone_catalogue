"""Independently inspect saved native cells and canonical source qualifications."""
import hashlib,importlib.util,json,posixpath,re
from pathlib import Path
from datetime import datetime,timezone
from urllib.parse import unquote
from xml.etree import ElementTree as E
H=Path(__file__).resolve().parent;B=H.parents[2];read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
s=importlib.util.spec_from_file_location('v',B/'components/reconciliation/image-identity-coverage-2026-10-20/verify_edit.py');v=importlib.util.module_from_spec(s);s.loader.exec_module(v)
w=v.load(H/'master-workbook.pending');g=read(H/'canonical-master-register.json');a=read(H/'image-coverage-current.json');old=read(H/'inputs/master_register.before');olda=read(H/'inputs/audit.before');prep=read(H/'preparation-verification.json');targets={x['option_id']:x for x in prep['imported_approvals']};issues=[];checks=0
def check(ok,msg):
 global checks
 checks+=1
 if not ok:issues.append(msg)
links={}
for sn,z in w['sheets'].items():
 rp=posixpath.join(posixpath.dirname(z['part']),'_rels',posixpath.basename(z['part'])+'.rels');rs={x.get('Id'):x.get('Target')for x in E.fromstring(w['files'][rp])}if rp in w['files']else{}
 for x in z['root'].findall('.//'+v.q('hyperlink')):
  u='#'+x.get('location')if x.get('location')else rs[x.get('{'+v.R+'}id')];links[(sn,x.get('ref'))]=u;check('BOLDSTONE_BACKUP'not in unquote(u).upper(),'Current native link scope '+sn+'!'+x.get('ref'))
opts={x['product_id']:x for x in g['options']};cov={x['option_id']:x for x in a['coverage']};priorcov={x['option_id']:x for x in olda['coverage']}
for x,y in zip(g['options'],old['options']):
 if x['product_id']not in targets:check(x==y,'Unrelated option preserved in full '+x['product_id'])
 for k in ['product_id','name','canonical_component_id','specifications','master_fields','selling_details','physical_specifications_verified']:check(x[k]==y[k],'Identity/physical/commercial source unchanged '+x['product_id']+'/'+k)
for oid,c in cov.items():
 for role in ['individual','in_situ','series']:
  if oid in targets and role=='in_situ':continue
  before=priorcov[oid][role];after=c[role];check(before['status']==after['status']and(before.get('reference')or{}).get('file_id')==(after.get('reference')or{}).get('file_id'),'Unchanged image role '+oid+'/'+role)
for oid,item in targets.items():
 c=cov[oid];r=c['in_situ']['reference'];row=str(g['options'].index(opts[oid])+10)
 check(c['in_situ']['status']=='Available','Context bound '+oid)
 check(w['values']['Photo Coverage']['F'+row]=='Available'and w['values']['Photo Coverage']['O'+row]==r['file_id']and w['values']['Photo Coverage']['P'+row]==r['folder_id'],'Saved context source and actual parent '+oid)
 check(links[('Photo Coverage','G'+row)]==r['image_url']and links[('Photo Coverage','H'+row)]==r['folder_url'],'Saved exact context destinations '+oid)
 check(c['in_situ']['physical_cast_or_size_certified']is False,'No physical certificate '+oid)
 check(c['individual']['reference']['file_id']==opts[oid]['file_id'],'Primary image unchanged '+oid)
check(cov['BSI-70ECBB049292']['in_situ']['display_context_only']is True,'Fountain display qualification explicit')
check(cov['BSI-70ECBB049292']['in_situ']['scene_authenticity_verified']is False,'No authenticated client installation inferred')
check(cov['BSI-70ECBB049292']['series']['status']=='No verified image','Fountain series gap stays open')
for oid in ['BSI-C41824131174','BSI-3635E3DC3434']:
 c=cov[oid];check(c['series']['status']=='No verified image'and c['series']['reference']['file_id']=='Unbound','Acanthus unavailable series remains open '+oid)
check(opts['BSI-C41824131174']['file_id']=='Unbound'and not opts['BSI-C41824131174']['image_url']and not opts['BSI-C41824131174']['folder_id'],'No false Sandstone primary or containing parent')
fresh=read(H/'fresh-fountain-evidence.json');overlay=read(H/'inputs/overlay.before');native=read(H/'current-native-reference-map.json')['current_objects'];listing=fresh['listing'];check(not listing['has_more']and not listing['cursor'],'Complete14-source folder readback')
for x in overlay['files']:
 if x['parent_changed']:check(native[x['file_id']]['parent_id']==x['folder_id']and native[x['file_id']]['path']==x['namespace_path'],'Actual parent/path native mapping '+x['file_id'])
counts=a['counts'];n=len(targets);check(counts['required_picture_actions']==72-n and counts['in_situ_statuses']['No verified image']==52-n and counts['series_statuses']['No verified image']==18,'Current source-derived action totals')
check(counts['actions_by_type']['Find / capture']==71-n and counts['resolved_action_rows']==82+n,'Find/capture and resolved totals')
spec=read(H/'specification-evidence-review.json');check(sorted(x['listed_weight_kg']for x in spec['sources'])==[5.5,6.5,6.5]and spec['physical_verifications_added']==0,'Conflicting brochure claims retained without physical upgrade')
for path in (B/'outputs'/H.name).glob('*'):
 if path.suffix in ['.html','.csv']:check('BOLDSTONE_BACKUP'not in unquote(path.read_text()).upper(),'Current report source scope '+path.name)
r={'status':'FAIL'if issues else'PASS','recorded_utc':datetime.now(timezone.utc).isoformat(),'checks':checks,'issues':issues,'workbook_sha256':sha(H/'master-workbook.pending'),'register_sha256':sha(H/'canonical-master-register.json'),'audit_sha256':sha(H/'image-coverage-current.json'),'current_option_count':188,'in_situ_gaps':52-n,'series_gaps':18,'source_scope':'BOLDSTONE MASTER only','new_native_mutations':0}
(H/'native-binding-verification.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps({k:r[k]for k in ['status','checks','issues']}));assert not issues
