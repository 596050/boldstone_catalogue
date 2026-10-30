"""Independent semantic and native-link readback for the exact one-role import."""
import copy,hashlib,importlib.util,json,posixpath,re
from pathlib import Path
from datetime import datetime,timezone
from xml.etree import ElementTree as E
H=Path(__file__).resolve().parent;B=H.parents[2]
read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
s=importlib.util.spec_from_file_location('native_reader',B/'components/reconciliation/image-identity-coverage-2026-10-20/verify_edit.py');n=importlib.util.module_from_spec(s);s.loader.exec_module(n)
g=read(H/'canonical-master-register.json');old=read(H/'inputs/master_register.before');a=read(H/'image-coverage-current.json');before=read(H/'inputs/audit.before');w=n.load(H/'master-workbook.pending');prior=n.load(H/'inputs/master_workbook.before');e=read(H/'leaf-native-evidence.json');m=read(H/'input-manifest.json');approval=read(m['owner_approval']['snapshot']);oid='BSI-CF0CC1EB8F96';issues=[];checks=0
def check(ok,label):
 global checks
 checks+=1
 if not ok:issues.append(label)
o=next(x for x in g['options']if x['product_id']==oid);co=next(x for x in a['coverage']if x['option_id']==oid);ref=co['in_situ']['reference'];oldco=next(x for x in before['coverage']if x['option_id']==oid)
check(len(g['options'])==188 and len(g['active_option_ids'])==187 and len(g['components'])==112,'Existing active/history counts and component identities')
for x,y in zip(g['options'],old['options']):
 check(x['product_id']==y['product_id'],'Option order stable')
 if x['product_id']!=oid:check(x==y,'Every unrelated option unchanged '+x['product_id'])
 for key in ['product_id','name','file_id','folder_id','image_url','folder_url','canonical_key','canonical_component_id','master_fields','specifications','selling_details','counted_as_individual_option']:
  check(x[key]==y[key],'Identity, primary, working and commercial values retained '+x['product_id']+' '+key)
check(g['summary']==old['summary'],'Canonical summary unchanged')
check(g['latest_four_links_and_strata_import']==old['latest_four_links_and_strata_import'],'Prior four-packet and Strata release retained intact')
check(g['catalogue_retirements']==old['catalogue_retirements'] and g['retired_option_ids']==['BSI-C41824131174'],'Exact Sandstone retirement preserved')
for x,y in zip(a['coverage'],before['coverage']):
 if x['option_id']!=oid:check(x==y,'Unrelated coverage row unchanged '+x['option_id'])
check(co['individual']==oldco['individual'] and co['series']==oldco['series'],'Target primary and series dispositions unchanged')
changed_actions=[(x,y)for x,y in zip(a['missing_pictures'],before['missing_pictures'])if x!=y]
check(len(changed_actions)==1,'Exactly one action changed')
check(changed_actions[0][0]['option_id']==oid and changed_actions[0][0]['role']=='In situ' and changed_actions[0][0]['status']=='Resolved','Only Leaf Curve in-situ action resolved')
counts=a['counts'];check(counts['required_picture_actions']==65 and counts['in_situ_statuses']=={'Available':140,'No verified image':47} and counts['series_statuses']==before['counts']['series_statuses'],'Expected65 required actions,47 context and17 series gaps')
check(counts['retired_action_rows']==3 and counts['resolved_action_rows']==86,'Retired tasks distinct from photograph findings')
check(ref['file_id']==e['context']['file']['id'] and ref['folder_id']==e['folder']['folder']['id'],'Exact native file and actual containing parent')
check(posixpath.dirname(e['context']['file']['path_display'])==e['folder']['folder']['path_display'],'Actual folder contains exact source')
check(ref['rev']==e['context']['file']['rev'] and ref['size']==e['context']['file']['size'],'Current native revision and size')
check(co['in_situ']['outdoor_display_only'] and not co['in_situ']['scene_authenticity_verified'] and not co['in_situ']['physical_cast_or_size_certified'],'Qualified outdoor display has no physical or client-installation promotion')
row=g['options'].index(o)+10;arow=next(i for i,x in enumerate(a['missing_pictures'],10)if x['option_id']==oid and x['role']=='In situ')
links={}
for sn,info in w['sheets'].items():
 rp=posixpath.join(posixpath.dirname(info['part']),'_rels',posixpath.basename(info['part'])+'.rels');rs={x.get('Id'):x for x in E.fromstring(w['files'][rp])}
 for x in info['root'].findall('.//'+n.q('hyperlink')):links[(sn,x.get('ref'))]='#'+x.get('location')if x.get('location')else rs[x.get('{'+n.R+'}id')].get('Target')
for sn,col,rr,url in [('Photo Coverage','G',row,ref['image_url']),('Photo Coverage','H',row,ref['folder_url']),('Master Catalogue','T',row,ref['image_url']),('Master Catalogue','U',row,ref['folder_url']),('Missing Pictures','G',arow,ref['image_url']),('Missing Pictures','H',arow,ref['folder_url'])]:check(links.get((sn,col+str(rr)))==url,'Saved exact native link '+sn+'!'+col+str(rr))
for sn,col,rr,val in [('Photo Coverage','O',row,ref['file_id']),('Photo Coverage','P',row,ref['folder_id']),('Photo Coverage','F',row,'Available'),('Missing Pictures','I',arow,ref['file_id']),('Missing Pictures','J',arow,ref['folder_id']),('Missing Pictures','N',arow,'Resolved')]:check(w['values'][sn][col+str(rr)]==val,'Saved binding '+sn+'!'+col+str(rr))
check(w['values']['Photo Coverage']['D4']==140 and w['values']['Missing Pictures']['B4']==64,'Saved recalculated affected summaries')
for sn in ['Specifications','Selling Details','Fingerprint History','Source Specifications']:check(w['values'][sn]==prior['values'][sn] and w['formulas'][sn]==prior['formulas'][sn],'Untouched values/formulas '+sn)
for sn in prior['formulas']:check(w['formulas'][sn]==prior['formulas'][sn],'Original formula texts '+sn)
check(len(links)==12027,'All12022 prior native links retained plus5 scoped links')
for key,x in m.items():check(sha(x['path'])==sha(x['snapshot'])==x['sha256'],'Frozen source '+key)
check(sha(approval['technical_source_qualification']['path'])==approval['technical_source_qualification']['sha256'],'Owner packet source preflight hash')
source=next(x for x in read(approval['technical_source_qualification']['path'])['original_checks']if x['file_id']==ref['file_id'])
check(sha(source['local_original_path'])==ref['sha256'],'Whole original pixels unchanged')
check(read(H/'queued-link-readback.json')['status']=='PASS_ALREADY_IMPORTED_AND_FRESH_NATIVE_READBACK','Four folder packets already imported and current')
r={'status':'FAIL'if issues else'PASS','recorded_utc':datetime.now(timezone.utc).isoformat(),'checks':checks,'issues':issues,'workbook_sha256':sha(H/'master-workbook.pending'),'register_sha256':sha(H/'canonical-master-register.json'),'audit_sha256':sha(H/'image-coverage-current.json'),'owner_role_count':1,'physical_verifications_added':0,'new_native_or_platform_writes':0,'primary_and_other_187_options_preserved':True,'native_hyperlinks':len(links)}
(H/'native-binding-verification.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps({k:r[k]for k in ['status','checks','issues','native_hyperlinks']}))
if issues:raise SystemExit(1)
