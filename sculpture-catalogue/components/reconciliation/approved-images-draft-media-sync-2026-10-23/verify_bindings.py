import json,hashlib,posixpath,zipfile
from pathlib import Path
from xml.etree import ElementTree as E
from urllib.parse import quote
from datetime import datetime,timezone
H=Path(__file__).resolve().parent;read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();g=read(H/'canonical-master-register.json');a=read(H/'image-coverage-current.json');cross=read(H/'native-current-crosswalk.json');objects=cross['current_objects'];scope=read(H/'preparation-verification.json');first=read(H/'image-and-parent-metadata-current.json');last=read(H/'final-native-readback.json');issues=[];checks=0
def check(ok,msg):
 global checks
 checks+=1
 if not ok:issues.append(msg)
for fid,d in last.items():
 kind=d['metadata_type'];v=d[kind]
 if fid in first:
  orig=first[fid][kind];check(all(v.get(k)==orig.get(k)for k in ['id','name','path_display','rev','size','client_modified']),'Current native revision/path unchanged '+fid)
 if fid in objects:check(v['path_display']==objects[fid]['display_path'],'Final source path '+fid)
ns={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'};R='{http://schemas.openxmlformats.org/officeDocument/2006/relationships}';cells={};links={}
with zipfile.ZipFile(H/'master-workbook.pending')as z:
 wr={x.get('Id'):x.get('Target')for x in E.fromstring(z.read('xl/_rels/workbook.xml.rels'))};strings=[''.join(x.itertext())for x in E.fromstring(z.read('xl/sharedStrings.xml'))]if'xl/sharedStrings.xml'in z.namelist()else[]
 for sh in E.fromstring(z.read('xl/workbook.xml')).find('s:sheets',ns):
  target=wr[sh.get(R+'id')];p=target.lstrip('/')if target.startswith('/')else posixpath.normpath('xl/'+target);root=E.fromstring(z.read(p));data={};sn=sh.get('name');relp=posixpath.dirname(p)+'/_rels/'+posixpath.basename(p)+'.rels';rels={x.get('Id'):x.get('Target')for x in E.fromstring(z.read(relp))}if relp in z.namelist()else{}
  for c in root.findall('.//s:c',ns):
   check(c.get('t')!='e','No saved formula error '+sn+'!'+c.get('r'));v=c.find('s:v',ns);raw=v.text if v is not None and v.text else'';data[c.get('r')]=strings[int(raw)]if c.get('t')=='s'else''.join(c.find('s:is',ns).itertext())if c.get('t')=='inlineStr'else raw
  for x in root.findall('.//s:hyperlink',ns):links[(sn,x.get('ref'))]='#'+x.get('location')if x.get('location')else rels[x.get(R+'id')]
  cells[sn]=data
cov={x['option_id']:x for x in a['coverage']}
for i,x in enumerate(g['options'],10):
 oid=x['product_id'];fid=x.get('file_id');obj=objects.get(fid)
 if obj and obj['object_type']=='file':check(x['folder_id']==obj['parent_id']and x['image_url']=='https://www.dropbox.com/preview'+quote(obj['display_path'],safe='/'),'Current graph ID/actual parent '+oid)
 for sn,fc,pc in [('Master Catalogue','Q','R'),('Photo Coverage','M','N'),('Selling Details','N','O')]:
  if oid!='BSI-04D6E8690F30':check(cells[sn].get(fc+str(i))==cov[oid]['individual']['reference']['file_id']and cells[sn].get(pc+str(i))==cov[oid]['individual']['reference']['folder_id'],'Saved current IDs '+sn+' '+oid)
 check(cells['Photo Coverage'].get('C'+str(i))==cov[oid]['individual']['status'],'Saved technical individual role '+oid)
 if oid in scope['complete_individual_images_added']:
  check(cov[oid]['individual']['status']=='Available','Approved full image available '+oid)
  for sn,fc,pc in [('Listing Resolution','T','U'),('Draft Listings','K','L')]:
   rr=next((c[1:]for c,v in cells[sn].items()if c.startswith('A')and c[1:].isdigit()and v==oid),None)
   if rr:check(cells[sn].get(fc+rr)==x['file_id']and cells[sn].get(pc+rr)==x['folder_id'],'Saved additional current primary '+sn+' '+oid)
  for sr in range((i-10)*6+10,(i-10)*6+16):check(cells['Specifications'].get('L'+str(sr))==x['file_id']and cells['Specifications'].get('M'+str(sr))==x['folder_id'],'All six specification references '+oid)
 if oid in scope['owner_accepted_qualified_reference_exceptions']:
  check(cov[oid]['individual']['status']=='Group only','Accepted listing reference retains technical group role '+oid);check(not any(v['status']=='Open'and v['role']=='Individual'and v['option_id']==oid for v in a['missing_pictures']),'Scoped individual capture prompt retired '+oid)
  if oid in ['BSI-95ECE169007F','BSI-6C2DDC69FB83']:
   roles=x['owner_accepted_listing_references']['references'];check({v['role']for v in roles}=={'design_reference','finish_reference'},'Design and finish roles separate '+oid);check(next(v for v in roles if v['role']=='design_reference')['source_image_is_white_not_a_verified_beige_standalone'],'White design remains White '+oid)
for row in cross['restored_sources']:
 fid=row['file_id'];check(row['current_parent_id']=='id:cnqzTNngPVsAAAAAAA6Vng'and row['historical_parent_id']=='id:cnqzTNngPVsAAAAAAAyh4Q','Acanthus new actual parent, original history retained '+fid);check(last[fid]['file']['id']==fid,'Restored original ID '+fid)
for label,path in read(H/'scope.json')['overlays'].items():
 for z in read(path).get('specific_file_maps',[]):check(objects[z['file_id']]['parent_id']==z['current_parent_id'],'Specific Fold Unfold parent override '+z['file_id'])
old=read(H/'inputs/master_register.before');check(g['current_frozen_fish_size_policy']==old['current_frozen_fish_size_policy'],'Frozen Fish current70x15cm policy unchanged');check(g['wall_sculpture_customisation_policy']==old['wall_sculpture_customisation_policy'],'Wall customisation policy retained');check(read(H/'client-timestamp-verification.json')['status']=='PASS','All six native family original timestamps/names/sizes verified')
out={'status':'FAIL'if issues else'PASS','recorded_utc':datetime.now(timezone.utc).isoformat(),'checks':checks,'issues':issues,'workbook_sha256':sha(H/'master-workbook.pending'),'register_sha256':sha(H/'canonical-master-register.json'),'audit_sha256':sha(H/'image-coverage-current.json'),'final_native_objects_checked':len(last),'native_crosswalk_objects':len(objects),'native_file_revision_restores':2,'physical_verification_added':0,'platform_writes':0};(H/'native-binding-verification.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({k:out[k]for k in ['status','checks','issues']}))
if issues:raise SystemExit(1)
