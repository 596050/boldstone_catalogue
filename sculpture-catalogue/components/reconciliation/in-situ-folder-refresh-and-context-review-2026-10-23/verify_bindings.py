import json,hashlib,importlib.util,re,posixpath
from pathlib import Path
from datetime import datetime,timezone
from urllib.parse import quote,unquote,urlsplit,parse_qs
from xml.etree import ElementTree as E
H=Path(__file__).resolve().parent;B=H.parents[2];read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();issues=[];checks=0
s=importlib.util.spec_from_file_location('n',B/'components/reconciliation/image-identity-coverage-2026-10-20/verify_edit.py');n=importlib.util.module_from_spec(s);s.loader.exec_module(n);w=n.load(H/'master-workbook.pending');g=read(H/'canonical-master-register.json');old=read(H/'inputs/master_register.before');a=read(H/'image-coverage-current.json');olda=read(H/'inputs/audit.before');cur=read(H/'current-native-reference-map.json');objects=cur['current_objects'];repl=cur['byte_identical_backup_replacements'];fresh={**read(H/'final-native-readback.json'),**read(H/'wall-circle-final-native-readback.json')};bindings=read(H/'preparation-verification.json')['imported_approvals'];cov={x['option_id']:x for x in a['coverage']};links={}
def check(ok,msg):
 global checks
 checks+=1
 if not ok:issues.append(msg)
def urlpath(u):
 z=urlsplit(u);p=unquote(z.path)
 for t in ['/home','/preview']:
  if p.startswith(t+'/'):p=p[len(t):];break
 name=parse_qs(z.query).get('preview',[''])[0];return p+('/'+name if name else '')
for sn,z in w['sheets'].items():
 rp=posixpath.join(posixpath.dirname(z['part']),'_rels',posixpath.basename(z['part'])+'.rels');rr={x.get('Id'):x.get('Target')for x in E.fromstring(w['files'][rp])}if rp in w['files']else{}
 for x in z['root'].findall('.//'+n.q('hyperlink')):links[(sn,x.get('ref'))]='#'+x.get('location')if x.get('location')else rr[x.get('{'+n.R+'}id')]
for fid,z in fresh.items():
 check(fid in objects,'Fresh native ID represented '+fid)
 if fid not in objects:continue
 check(z['path_display']==objects[fid]['display_path'],'Final live native path '+fid)
 if z['metadata_type']=='file':
  parent=objects[fid]['parent_id'];check(parent in objects,'Actual file parent represented '+fid)
  if parent in objects:check(posixpath.dirname(z['path_display'])==objects[parent]['display_path'],'Actual file parent path '+fid)
for x,y in zip(g['options'],old['options']):
 oid=x['product_id'];row=g['options'].index(x)+10;fid=repl.get(y['file_id'],y['file_id'])
 check(all(x[k]==y[k]for k in ['product_id','name','canonical_key','canonical_component_id','specifications','master_fields','selling_details']),'Identity and all qualified fields retained '+oid)
 check(x['file_id']==fid,'Only two explicit backup source-ID substitutions allowed '+oid)
 if x['file_id']in objects:
  z=objects[x['file_id']];check(x['folder_id']==z['parent_id'],'Current option actual parent '+oid);check(urlpath(x['image_url'])==z['display_path'],'Option current image path '+oid);check(urlpath(x['folder_url'])==posixpath.dirname(z['display_path']),'Option actual containing-folder URL '+oid)
  check(w['values']['Master Catalogue']['Q'+str(row)]==x['file_id']and w['values']['Master Catalogue']['R'+str(row)]==x['folder_id'],'Saved option source IDs '+oid)
  check(urlpath(links[('Master Catalogue','N'+str(row))])==z['display_path']and urlpath(links[('Master Catalogue','O'+str(row))])==posixpath.dirname(z['display_path']),'Saved option actual image/folder links '+oid)
 check(cov[oid]['individual']['status']==next(z for z in olda['coverage']if z['option_id']==oid)['individual']['status'],'No independent individual-photo coverage upgrade '+oid)
for x in bindings:
 oid=x['option_id'];row=next(i+10 for i,z in enumerate(g['options'])if z['product_id']==oid);rk='in_situ'if x['role']=='In situ'else'series';r=cov[oid][rk]['reference'];cols=('F','G','H','O','P')if rk=='in_situ'else('I','J','K','Q','R');status,im,fo,fi,pa=cols
 check(w['values']['Photo Coverage'][status+str(row)]=='Available','Saved current role available '+oid+rk)
 check(w['values']['Photo Coverage'][fi+str(row)]==r['file_id']and w['values']['Photo Coverage'][pa+str(row)]==r['folder_id'],'Saved binding file/parent IDs '+oid+rk)
 check(urlpath(links[('Photo Coverage',im+str(row))])==objects[r['file_id']]['display_path'],'Saved binding exact source path '+oid+rk)
 check(urlpath(links[('Photo Coverage',fo+str(row))])==objects[r['folder_id']]['display_path'],'Saved binding actual parent path '+oid+rk)
 check(not cov[oid][rk]['physical_cast_or_size_certified']and not cov[oid][rk]['scene_authenticity_verified'],'Source/scene qualifiers retained '+oid+rk)
 action=next(z for z in a['missing_pictures']if z['option_id']==oid and z['role']==x['role']);check(action['status']=='Resolved'and bool(action['historical_actions']),'Role action closed with history '+oid+rk)
 if x['role']=='Series':check(cov[oid]['in_situ']['status']=='No verified image','Bronze pair does not close separate in situ '+oid)
for f in ['original-verification.json','acanthus-download-verification.json','new-scene-download-verification.json']:
 for x in read(H/f)['files']:check(sha(x['local_original'])==x['sha256'],'Exact downloaded original bytes '+x['file_id'])
for oldid,newid in repl.items():
 check(objects[newid]['parent_id']=='id:cnqzTNngPVsAAAAAAA6LRA','Byte-identical backup has actual live parent '+newid)
 check(any(oldid in json.dumps(x)for x in g['options']),'Historical original ID retained in source lineage '+oldid)
check(g['original_review_specification_assertions']==old['original_review_specification_assertions'],'1668 raw source assertions preserved')
check(g['summary']==old['summary']and len(g['options'])==188 and len(g['components'])==112,'Catalogue counts unchanged')
for k in ['wall_sculpture_customisation_policy','current_frozen_fish_size_policy']:check(g[k]==old[k],k+' unchanged')
check(g['summary']['physical_stock_quantity']is None and g['summary']['physical_mould_count']is None,'No inferred physical stock or mould count')
check(sum(x['status']=='Open'for x in a['missing_pictures'])==71 and sum(x['status']=='Resolved'for x in a['missing_pictures'])==83,'71 required/83 resolved actions')
check(sum(x['status']=='Open'and x['role']=='In situ'for x in a['missing_pictures'])==53 and sum(x['status']=='Open'and x['role']=='Series'for x in a['missing_pictures'])==16,'53 in situ/16 series gaps')
check({x['option_id']for x in a['missing_pictures']if x['status']=='Open'and x['role']=='Individual'}=={'BSI-C41824131174','BSI-04D6E8690F30'},'Acanthus separate photograph and deferred Frozen identity remain open')
check(w['values']['Photo Coverage']['B4']==177 and w['values']['Photo Coverage']['B5']==11 and w['values']['Photo Coverage']['D4']==135 and w['values']['Photo Coverage']['F4']==118,'Saved technical versus role coverage counts')
check(w['values']['Missing Pictures']['B4']==70 and w['values']['Missing Pictures']['D4']==1,'Saved action formulas')
check(read(H/'context-review-ledger.json')['tasks_reviewed']==78,'All prior open context tasks individually accounted for')
check(read(H/'artifact-authoring-receipt.json')['status']=='PASS','Artifact count perturbation checks passed')
seal=read(H/'lava-white-pool-owner-approval-seal.json');check(sha(seal['path'])==seal['sha256']and seal['owner_event_verified'],'New direct White pool owner decision sealed')
result={'status':'FAIL'if issues else'PASS','recorded_utc':datetime.now(timezone.utc).isoformat(),'checks':checks,'issues':issues,'workbook_sha256':sha(H/'master-workbook.pending'),'register_sha256':sha(H/'canonical-master-register.json'),'audit_sha256':sha(H/'image-coverage-current.json'),'fresh_native_readback_objects':len(fresh),'owner_in_situ_bindings':7,'new_series_bindings':2,'new_physical_verifications':0,'native_or_platform_writes':0,'current_source_map_sha256':sha(H/'current-native-reference-map.json'),'final_native_readback_sha256':sha(H/'final-native-readback.json')};(H/'native-binding-verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:result[k]for k in ['status','checks','issues']}))
if issues:raise SystemExit(1)
