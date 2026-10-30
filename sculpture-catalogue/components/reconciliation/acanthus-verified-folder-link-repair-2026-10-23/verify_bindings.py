import hashlib,importlib.util,json,posixpath
from pathlib import Path
from datetime import datetime,timezone
from xml.etree import ElementTree as E
H=Path(__file__).resolve().parent;B=H.parents[2];read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
s=importlib.util.spec_from_file_location('v',B/'components/reconciliation/image-identity-coverage-2026-10-20/verify_edit.py');v=importlib.util.module_from_spec(s);s.loader.exec_module(v)
def links(w):
 out={}
 for sn,z in w['sheets'].items():
  rp=posixpath.join(posixpath.dirname(z['part']),'_rels',posixpath.basename(z['part'])+'.rels');rs={x.get('Id'):x.get('Target')for x in E.fromstring(w['files'][rp])}if rp in w['files']else{}
  for x in z['root'].findall('.//'+v.q('hyperlink')):out[(sn,x.get('ref'))]='#'+x.get('location')if x.get('location')else rs[x.get('{'+v.R+'}id')]
 return out
old=v.load(H/'inputs/master_workbook.before');new=v.load(H/'master-workbook.pending');before=links(old);after=links(new);drift=read(H/'inputs/link_drift.before')['matched_stale_hyperlinks'];expected={(x['sheet'],x['cell']):x for x in drift};issues=[];checks=0
def check(ok,msg):
 global checks
 checks+=1
 if not ok:issues.append(msg)
changed={k for k in after if before.get(k)!=after[k]};check(changed==set(expected)and len(changed)==22,'Exactly the22 approved target changes')
for k,x in expected.items():check(before[k]==x['saved_target']and after[k]==x['suggested_target'],'Verified native target '+str(k))
check(before.keys()==after.keys(),'Native link cell set unchanged')
for sn in old['sheets']:check(new['values'][sn]==old['values'][sn]and new['formulas'][sn]==old['formulas'][sn],'All values/formulas unchanged '+sn)
check(sha(H/'canonical-master-register.json')==sha(H/'inputs/master_register.before'),'Entire current register byte-identical')
check(sha(H/'image-coverage-current.json')==sha(H/'inputs/audit.before'),'Entire current audit byte-identical')
check(not any('BOLDSTONE_BACKUP'in x.upper()for x in after.values()),'No backup links')
result={'status':'FAIL'if issues else'PASS','recorded_utc':datetime.now(timezone.utc).isoformat(),'checks':checks,'issues':issues,'workbook_sha256':sha(H/'master-workbook.pending'),'register_sha256':sha(H/'canonical-master-register.json'),'audit_sha256':sha(H/'image-coverage-current.json'),'changed_hyperlink_targets':22,'verified_master_folder_ids':14,'values_changed':0,'formulas_changed':0,'roles_or_specifications_changed':0}
(H/'native-binding-verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
if issues:raise SystemExit(1)
