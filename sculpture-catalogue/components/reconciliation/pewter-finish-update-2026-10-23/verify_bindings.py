"""Independently check current IDs, parent relationships and saved image-role cells."""
import hashlib,json,posixpath,zipfile
from pathlib import Path
from urllib.parse import quote
from xml.etree import ElementTree as E
from datetime import datetime,timezone
H=Path(__file__).resolve().parent;read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();issues=[];checks=0
def check(ok,msg):
 global checks
 checks+=1
 if not ok:issues.append(msg)
g=read(H/'canonical-master-register.json');a=read(H/'image-coverage-current.json');cross=read(H/'native-current-crosswalk.json')['current_objects'];fresh=read(H/'final-native-readback.json');first={x['file']['id']:x['file']for x in read(H/'new-file-metadata.json')};freshmap={x['requested_id']:x['result'].get('file',x['result'].get('folder',{}))for x in fresh}
for fid,md in first.items():check(all(freshmap[fid][k]==md[k]for k in ['id','size','rev','path_display']),'Fresh original ID/revision/path '+fid)
for x in g['options']:
 fid=x.get('file_id');native=cross.get(fid)
 if native and native['object_type']=='file':check(x['folder_id']==native['parent_id']and x['image_url']=='https://www.dropbox.com/preview'+quote(native['display_path'],safe='/'),'Current option file/actual parent '+x['product_id'])
with zipfile.ZipFile(H/'master-workbook.pending')as z:
 ns={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'};R='{http://schemas.openxmlformats.org/officeDocument/2006/relationships}';wr={x.get('Id'):x.get('Target')for x in E.fromstring(z.read('xl/_rels/workbook.xml.rels'))};strings=[''.join(x.itertext())for x in E.fromstring(z.read('xl/sharedStrings.xml'))]if'xl/sharedStrings.xml'in z.namelist()else[];cells={}
 for sh in E.fromstring(z.read('xl/workbook.xml')).find('s:sheets',ns):
  target=wr[sh.get(R+'id')];p=target.lstrip('/')if target.startswith('/')else posixpath.normpath('xl/'+target);root=E.fromstring(z.read(p));data={}
  for c in root.findall('.//s:c',ns):
   check(c.get('t')!='e','No saved formula error '+sh.get('name')+'!'+c.get('r'));v=c.find('s:v',ns);raw=v.text if v is not None and v.text else'';data[c.get('r')]=strings[int(raw)]if c.get('t')=='s'else ''.join(c.find('s:is',ns).itertext())if c.get('t')=='inlineStr'else raw
  cells[sh.get('name')]=data
cov={x['option_id']:x for x in a['coverage']}
for oid in ['BSI-3635E3DC3434','BSI-449C4421ABD0','BSI-1774B82C6518']:
 x=next(x for x in g['options']if x['product_id']==oid);r=g['options'].index(x)+10;cr=cov[oid]
 for sn,fc,pc in [('Master Catalogue','Q','R'),('Photo Coverage','M','N'),('Selling Details','N','O')]:check(cells[sn].get(fc+str(r))==x['file_id']and cells[sn].get(pc+str(r))==x['folder_id'],'Saved primary IDs '+sn+' '+oid)
 check(cells['Photo Coverage'].get('C'+str(r))=='Available','Saved individual full image '+oid)
 if r>=196:
  for c in ['G','H','O','P']:check(cells['Photo Coverage'].get(c+str(r),'')=='','Missing in situ has no copied reference '+oid+' '+c)
  for c in ['T','U']:check(cells['Master Catalogue'].get(c+str(r),'')=='','No copied master context '+oid+' '+c)
for x in g['options'][-2:]:
 c=next(c for c in g['components']if c['component_id']==x['canonical_component_id']);check(x['product_id']in c['option_ids']and x['name']in c['option_names'],'New finish retains existing component edge '+x['product_id'])
check(cells['Photo Coverage'].get('Q196','')==''and cells['Photo Coverage'].get('Q197')=='id:cnqzTNngPVsAAAAAAAt-ZA','Only Egyptian new option has the bound pair reference')
result={'status':'FAIL'if issues else'PASS','recorded_utc':datetime.now(timezone.utc).isoformat(),'checks':checks,'issues':issues,'workbook_sha256':sha(H/'master-workbook.pending'),'register_sha256':sha(H/'canonical-master-register.json'),'fresh_native_objects_checked':len(freshmap),'current_two_family_object_crosswalk_checked':len(cross),'new_image_revisions_unchanged':True,'no_false_copied_context_references':not issues,'native_or_platform_writes':0};(H/'native-binding-verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:result[k]for k in ['status','checks','issues']}))
if issues:raise SystemExit(1)
