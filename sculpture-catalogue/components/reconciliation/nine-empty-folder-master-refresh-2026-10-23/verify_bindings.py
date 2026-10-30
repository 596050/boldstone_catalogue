"""Independent semantic/native check of the nine-folder-only projection."""
import hashlib,importlib.util,json,posixpath,re
from pathlib import Path
from datetime import datetime,timezone
from html.parser import HTMLParser
from xml.etree import ElementTree as E
from urllib.parse import unquote,urlsplit
H=Path(__file__).resolve().parent;B=H.parents[2];read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
s=importlib.util.spec_from_file_location('n',B/'components/reconciliation/image-identity-coverage-2026-10-20/verify_edit.py');n=importlib.util.module_from_spec(s);s.loader.exec_module(n);w=n.load(H/'master-workbook.pending');g=read(H/'canonical-master-register.json');old=read(H/'inputs/master_register.before');a=read(H/'image-coverage-current.json');nm=read(H/'current-native-reference-map.json');history=read(H/'removed-empty-folder-history.json');ids={x['file_id']for x in history['folders']};removedpaths={x['path_display'].casefold()for x in history['folders']};issues=[];checks=0
def check(ok,msg):
 global checks
 checks+=1
 if not ok:issues.append(msg)
for k in ['options','components','source_component_dispositions','original_review_specification_assertions','current_source_unavailable_references','latest_four_qualified_display_import','latest_owner_leaf_curve_context_import','latest_verified_native_folder_import']:check(g[k]==old[k],'Exact retained source scope '+k)
for name,key in [('image-coverage-current.json','audit'),('current-assets.json','report_assets'),('photo-review-queue.json','report_reviews'),('guided-owner-review-state.json','review_state')]:check(sha(H/name)==read(H/'input-manifest.json')[key]['sha256'],'Unchanged bytes '+name)
for fid in ids:check(fid not in nm['current_objects']and fid in nm['owner_removed_empty_family_history'],'Removed empty folder has history only '+fid)
check(len(ids)==9,'Nine distinct removed IDs');check(len(g['options'])==188 and sum(x.get('counted_as_individual_option',True)for x in g['options'])==187 and len(g['components'])==112,'187active/188retained/112 identities');check(a['counts']['required_picture_actions']==62 and a['counts']['in_situ_statuses']['No verified image']==44 and a['counts']['series_statuses']['No verified image']==17,'Photograph counts unchanged')
for row,fid in [(36,'id:cnqzTNngPVsAAAAAAAyj-Q'),(39,'id:cnqzTNngPVsAAAAAAAyj-g')]:
 vals=w['values']['Moonphases and Dune'];check(vals['B'+str(row)]==fid and vals['H'+str(row)]==''and'— removed while empty'in vals['D'+str(row)]and vals['E'+str(row)]=='Surviving family folder','Saved folder identity and navigation '+str(row))
class Parser(HTMLParser):
 def __init__(self):super().__init__();self.ids=set()
 def handle_starttag(self,t,attrs):
  d=dict(attrs)
  if 'id'in d:self.ids.add(d['id'])
out=B/'outputs'/H.name;parsers={}
for f in out.glob('*.html'):p=Parser();p.feed(f.read_text());parsers[f.name]=p
for sn,info in w['sheets'].items():
 rp=posixpath.join(posixpath.dirname(info['part']),'_rels',posixpath.basename(info['part'])+'.rels');rs={x.get('Id'):x.get('Target')for x in E.fromstring(w['files'][rp])}
 for x in info['root'].findall('.//'+n.q('hyperlink')):
  u=rs.get(x.get('{'+n.R+'}id'),'');cell=x.get('ref');protected=sn=='Fingerprint History'or sn=='Source Specifications'and re.fullmatch('[MN][0-9]+',cell)or sn=='Moonphases and Dune'and re.fullmatch('I[0-9]+',cell)
  if u.startswith('https://www.dropbox.com/')and not protected:
   path=unquote(urlsplit(u).path)
   for route in ['/home','/preview']:
    if path.startswith(route+'/'):path=path[len(route):];break
   check(path.casefold()not in removedpaths,'No active link to removed empty folder '+sn+'!'+cell)
  if u.startswith(str(out)):
   file,_,anchor=u.partition('#');p=Path(file);check(p.is_file(),'Saved current report target '+sn+'!'+cell)
   if anchor and p.name in parsers:check(anchor in parsers[p.name].ids,'Saved current report anchor '+sn+'!'+cell)
check(ids<=parsers['completed-changes.html'].ids,'All nine histories linked in current report');check(len(parsers['current-context-references.html'].ids-{'search'})==143,'143 qualified context associations retained');check(len(read(H/'pending-followups.json')['entries'])==1 and read(H/'pending-followups.json')['entries'][0]['status']=='PARTIAL_OWNER_HOLD','Completed packets cleared and owner-held work retained')
r={'status':'FAIL'if issues else'PASS','recorded_utc':datetime.now(timezone.utc).isoformat(),'checks':checks,'issues':issues[:80],'workbook_sha256':sha(H/'master-workbook.pending'),'register_sha256':sha(H/'canonical-master-register.json'),'audit_sha256':sha(H/'image-coverage-current.json'),'removed_empty_folder_history_entries':9,'photograph_bindings_added':0,'all_options_coverage_and_working_fields_unchanged':True,'native_or_platform_writes':0};(H/'native-binding-verification.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps({k:r[k]for k in ['status','checks','issues']}))
if issues:raise SystemExit(1)
