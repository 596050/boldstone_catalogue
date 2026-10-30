"""Independent role/ID/parent readback from the saved workbook, register and fresh Dropbox metadata."""
import json,hashlib,importlib.util,posixpath,collections,re
from pathlib import Path
from datetime import datetime,timezone
from urllib.parse import quote
from xml.etree import ElementTree as E
H=Path(__file__).resolve().parent;B=H.parents[2]
read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
s=importlib.util.spec_from_file_location('n',B/'components/reconciliation/image-identity-coverage-2026-10-20/verify_edit.py');n=importlib.util.module_from_spec(s);s.loader.exec_module(n)
w=n.load(H/'master-workbook.pending');g=read(H/'canonical-master-register.json');old=read(H/'inputs/master_register.before');a=read(H/'image-coverage-current.json');olda=read(H/'inputs/audit.before');scope=read(H/'scope.json');metadata=read(H/'final-native-readback.json');originals=read(H/'original-verification.json')['files'];issues=[];checks=0
def check(ok,msg):
 global checks
 checks+=1
 if not ok:issues.append(msg)
def display(p):return '/'+p.split('//',1)[1].lstrip('/')if p.startswith('ns:')else p
links={}
for sn,z in w['sheets'].items():
 rp=posixpath.join(posixpath.dirname(z['part']),'_rels',posixpath.basename(z['part'])+'.rels');rr={x.get('Id'):x.get('Target')for x in E.fromstring(w['files'][rp])}if rp in w['files']else{}
 for x in z['root'].findall('.//'+n.q('hyperlink')):links[(sn,x.get('ref'))]='#'+x.get('location')if x.get('location')else rr[x.get('{'+n.R+'}id')]
byid={x['file_id']:x for x in originals};cov={x['option_id']:x for x in a['coverage']};oldcov={x['option_id']:x for x in olda['coverage']};opts={x['product_id']:x for x in g['options']};target=set(scope['target_option_ids'])
for x in originals:
 f=metadata[x['file_id']];p=metadata[x['folder_id']]
 check(f['metadata_type']=='file'and p['metadata_type']=='folder','Native object types '+x['file_id'])
 check(f['rev']==x['rev']and f.get('size',0)==x['size'],'Same native revision and bytes '+x['file_id'])
 check(display(f['path_display'])==x['path_display'],'Current original path '+x['file_id'])
 check(posixpath.dirname(display(f['path_display']))==display(p['path_display']),'Actual native containing folder '+x['file_id'])
 check(sha(x['local_original'])==x['sha256'],'Byte-identical downloaded original '+x['file_id'])
for o,before in zip(g['options'],old['options']):
 oid=o['product_id'];c=cov[oid]
 check(all(o.get(k)==before.get(k)for k in ['name','canonical_key','canonical_component_id','master_fields','specifications','selling_details','file_id','folder_id','image_url','folder_url','current_listing_reconciliation','current_listing_resolution']),'Identity, primary, six fields and platform state retained '+oid)
 check(c['individual']['status']==oldcov[oid]['individual']['status']and c['individual']['reference']==oldcov[oid]['individual']['reference'],'Technical individual coverage and primary unchanged '+oid)
 check(c['series']==oldcov[oid]['series'],'Series coverage unchanged '+oid)
 if oid not in target:check(o==before and c==oldcov[oid],'Unrelated option and role data unchanged '+oid)
 if oid not in target:continue
 row=next(int(cel[1:])for cel,v in w['values']['Master Catalogue'].items()if re.fullmatch('A[0-9]+',cel)and v==oid)
 item=o['current_photo_approval_import'];role=item['role'];refs=item['approved_references']
 check(w['values']['Master Catalogue']['Q'+str(row)]==before['file_id']and w['values']['Master Catalogue']['R'+str(row)]==before['folder_id'],'Saved primary IDs unchanged '+oid)
 check(links[('Photo Coverage','U'+str(row))].endswith('imported-approvals.html#'+oid),'Current owner review link '+oid)
 action=[x for x in a['missing_pictures']if x['option_id']==oid and x['role']==role]
 check(len(action)==1 and action[0]['status']=='Resolved'and bool(action[0]['historical_actions']),'Exact action resolved with prior history '+oid)
 for z in refs:
  r=z['reference'];src=byid[r['file_id']]
  check(r['folder_id']==src['folder_id']and r['image_url']==src['image_url']and r['folder_url']==src['folder_url'],'Approved role actual native IDs/URLs '+oid+' '+z['role'])
 if oid in scope['individual_qualified_reference_option_ids']:
  check(c['individual']['status']=='Group only'and not o['owner_accepted_listing_references']['separate_full_image_verified'],'Group reference exception without standalone claim '+oid)
  if oid!='BSI-B1DCB5B08396':
   check([r['role']for r in refs]==['design_reference','finish_reference'],'White design and Sandstone finish roles '+oid)
   check(refs[0]['source_image_is_white_not_a_verified_sandstone_standalone']and refs[1]['reference']['file_id']=='id:cnqzTNngPVsAAAAAAAydKg','White not promoted to Sandstone photo '+oid)
 else:
  r=c['in_situ']['reference'];check(c['in_situ']['status']=='Available'and o['context_file_id']==r['file_id'],'Qualified context available '+oid)
  for sn,ic,fc,fidc,pidc in [('Photo Coverage','G','H','O','P')]:
   check(w['values'][sn][fidc+str(row)]==r['file_id']and w['values'][sn][pidc+str(row)]==r['folder_id'],'Saved in situ IDs '+oid)
   check(links[(sn,ic+str(row))]==r['image_url']and links[(sn,fc+str(row))]==r['folder_url'],'Saved context native destinations '+oid)
  check(links[('Master Catalogue','T'+str(row))]==r['image_url']and links[('Master Catalogue','U'+str(row))]==r['folder_url'],'Master context links '+oid)
  check(not c['in_situ']['physical_cast_or_size_certified']and not c['in_situ']['scene_authenticity_verified'],'Context not physical or scene authentication '+oid)
 if oid=='BSI-923D5E50A898':
  check(c['in_situ']['owner_accepted_variation']and not c['in_situ']['exact_primary_outline_match_verified'],'Brancusi accepted variation remains qualified')
  check(c['historical_in_situ_references'][-1]==oldcov[oid]['in_situ']and oldcov[oid]['in_situ']['deep_review_state']=='CANDIDATE_EXCLUDED_CAPTURE_REQUIRED','Brancusi exclusion and observed relief differences retained as history')
for oid,pos in [('BSI-ADD5F3BEFCF5','RIGHT'),('BSI-70BDE00F2855','LEFT')]:check(cov[oid]['in_situ']['member_position']==pos,'Cup Ring/Spiral correct member '+pos)
check(len(g['imported_owner_review_packets'])==len(old['imported_owner_review_packets'])+7,'Exactly seven owner packets appended')
check(g['original_review_specification_assertions']==old['original_review_specification_assertions'],'1668 original source assertions retained')
check(len([x for x in a['missing_pictures']if x['status']=='Open'])==80,'80 open required picture actions')
check(collections.Counter(x['role']for x in a['missing_pictures']if x['status']=='Open')=={'Individual':2,'In situ':60,'Series':18},'Exact remaining role counts')
check(sum(x['status']=='Resolved'for x in a['missing_pictures'])==74,'74 resolved action rows')
check(sum(x['status']=='Optional'for x in a['missing_pictures'])==54,'54 optional rows retained')
check({x['option_id']for x in a['missing_pictures']if x['status']=='Open'and x['role']=='Individual'}=={'BSI-C41824131174','BSI-04D6E8690F30'},'Only Acanthus photo and deferred Frozen Fish identity remain')
check(w['values']['Photo Coverage']['B4']==177 and w['values']['Photo Coverage']['B5']==11 and w['values']['Photo Coverage']['D4']==128,'Saved formula counts preserve technical coverage and qualified context distinction')
check(w['values']['Missing Pictures']['B4']==79 and w['values']['Missing Pictures']['D4']==1,'Saved find/capture and deferred identity formula counts')
changed=[(x['option_id'],x['role'])for x,y in zip(a['missing_pictures'],olda['missing_pictures'])if x!=y]
check(len(changed)==7,'Only seven actions changed')
check(len(read(H/'pending-followups.json')['superseded_review_outcomes'])==1,'Earlier Lava1 Next outcome superseded by later explicit role approval')
check(all(not x['applied_to_current_frozen_release']for x in read(H/'pending-followups.json')['entries']),'Later folder and approval changes remain queued')
check(read(H/'artifact-authoring-receipt.json')['status']=='PASS','Artifact formula perturbation checks passed')
out={'status':'FAIL'if issues else'PASS','recorded_utc':datetime.now(timezone.utc).isoformat(),'checks':checks,'issues':issues,'workbook_sha256':sha(H/'master-workbook.pending'),'register_sha256':sha(H/'canonical-master-register.json'),'audit_sha256':sha(H/'image-coverage-current.json'),'fresh_native_objects_verified':14,'owner_packets_imported':7,'source_originals_verified':7,'no_primary_or_six_field_or_platform_change':True,'new_physical_verifications':0,'native_or_platform_writes':0}
(H/'native-binding-verification.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({k:out[k]for k in ['status','checks','issues']}))
if issues:raise SystemExit(1)
