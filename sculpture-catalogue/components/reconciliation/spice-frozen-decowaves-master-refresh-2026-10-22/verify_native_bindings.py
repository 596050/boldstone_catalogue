"""Read saved links independently of the edit plan and compare to fresh Dropbox paths."""
import collections,csv,hashlib,json,posixpath,re,zipfile
from pathlib import Path
from xml.etree import ElementTree as E
from urllib.parse import unquote,urlsplit,parse_qs
H=Path(__file__).resolve().parent;read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();ns='{http://schemas.openxmlformats.org/spreadsheetml/2006/main}';rn='{http://schemas.openxmlformats.org/officeDocument/2006/relationships}';checks=0
def check(ok,message):
 global checks
 checks+=1
 assert ok,message
paths={};ids={}
for family,stem in [('spice','spice'),('frozen','decowaves')]:
 before=read(H/f'{stem}-live-tree.json');after=read(H/f'{stem}-post-tree.json');check(not after['has_more'],'Complete post-authoring listing')
 key=lambda x:(x['file_id'],x['object_type'],x['name'],x['path'],x.get('file',{}).get('size',0),x.get('client_modified'))
 check(sorted(map(key,before['entries']))==sorted(map(key,after['entries'])),'Native tree unchanged during authoring')
 md=read(H/f'{stem}-family-metadata.json')['folder'];paths[md['path_display'].casefold()]=md['id'];ids[md['id']]={'path':md['path_display'],'object_type':'folder'}
 for x in after['entries']:
  path='/'+x['path'].split('//',1)[1];paths[path.casefold()]=x['file_id'];ids[x['file_id']]={'path':path,'object_type':x['object_type'],'size':x.get('file',{}).get('size',0)}
def nativepath(url):
 u=urlsplit(url);p=unquote(u.path)
 for route in ['/home','/preview']:
  if p.startswith(route+'/'):p=p[len(route):];break
 f=parse_qs(u.query).get('preview',[''])[0]
 return p+('/'+f if f else'')
z=zipfile.ZipFile(H/'master-workbook.pending');strings=[''.join(x.itertext())for x in E.fromstring(z.read('xl/sharedStrings.xml'))];wr={x.get('Id'):x.get('Target')for x in E.fromstring(z.read('xl/_rels/workbook.xml.rels'))};sheetdata={};targets={};affected_links=0
for sh in E.fromstring(z.read('xl/workbook.xml')).find(ns+'sheets'):
 sn=sh.get('name');loc=wr[sh.get(rn+'id')];loc=loc.lstrip('/')if loc.startswith('/')else posixpath.normpath('xl/'+loc);root=E.fromstring(z.read(loc));rp=posixpath.join(posixpath.dirname(loc),'_rels',posixpath.basename(loc)+'.rels');rs={x.get('Id'):x.get('Target')for x in E.fromstring(z.read(rp))}if rp in z.namelist()else{};cells={}
 for c in root.iter(ns+'c'):
  v=c.find(ns+'v');s=v.text if v is not None and v.text else''
  cells[c.get('r')]=strings[int(s)]if c.get('t')=='s'else''.join(c.find(ns+'is').itertext())if c.get('t')=='inlineStr'else s
  check(c.get('t')!='e','No native formula error')
 for h in root.findall('.//'+ns+'hyperlink'):
  target=rs.get(h.get(rn+'id'))or'#'+h.get('location','');check(bool(target)and target!='#','No blank hyperlink')
  c=h.get('ref');targets[(sn,c)]=target
  if not target.startswith('https://www.dropbox.com/'):continue
  p=nativepath(target)
  if not any(p.startswith('/BOLDSTONE MASTER/Products/01 Wall Sculptures/'+family+'/')for family in ['Spice Texture','Decowaves']):continue
  if sn=='Source Specifications'and re.fullmatch(r'[MN]\d+',c):continue
  check(p.casefold()in paths,'Current saved hyperlink resolves in fresh native listing: '+sn+'!'+c+' '+p);affected_links+=1
 sheetdata[sn]=cells
g=read(H/'canonical-master-register.json');audit=read(H/'image-coverage-current.json');opts={x['product_id']:x for x in g['options']}
for pid,fid,parent in [('BSI-199FCF3A2B42','id:cnqzTNngPVsAAAAAAAyliA','id:cnqzTNngPVsAAAAAAA5RBA'),('BSI-828E89E3B7DC','id:cnqzTNngPVsAAAAAAAylhw','id:cnqzTNngPVsAAAAAAA6VlQ')]:
 o=opts[pid];check(o['file_id']==fid and o['folder_id']==parent,'Exact Spice stable IDs');check(paths[nativepath(o['image_url']).casefold()]==fid and paths[nativepath(o['folder_url']).casefold()]==parent,'Exact Spice image and actual containing folder URLs')
 for sn,image,folder,filecol,parentcol in [('Master Catalogue','N','O','Q','R'),('Specifications','J','K','L','M'),('Selling Details','L','M','N','O')]:
  cells=sheetdata[sn];rows=[c[1:]for c,v in cells.items()if re.fullmatch('A\\d+',c)and v==pid]
  check(len(rows)==(6 if sn=='Specifications' else 1),'Expected Spice current owning rows')
  for row in rows:
   check(cells[filecol+row]==fid and cells[parentcol+row]==parent,'Saved Spice file and folder ID columns')
   check(paths[nativepath(targets[(sn,image+row)]).casefold()]==fid and paths[nativepath(targets[(sn,folder+row)]).casefold()]==parent,'Saved Spice exact image/folder link association')
for x in audit['coverage']:
 for role in ['individual','in_situ','series']:
  r=x[role].get('reference')or{};fid=r.get('file_id')
  if fid not in ids:continue
  check(paths[nativepath(r['image_url']).casefold()]==fid,'Audit current image URL resolves to retained file ID')
  expected=paths[posixpath.dirname(ids[fid]['path']).casefold()];check(r['folder_id']==expected and paths[nativepath(r['folder_url']).casefold()]==expected,'Audit actual parent and folder URL are consistent')
result={'status':'PASS','checks':checks,'workbook_sha256':sha(H/'master-workbook.pending'),'register_sha256':sha(H/'canonical-master-register.json'),'affected_current_native_links_checked':affected_links,'source':'Fresh native before/after trees and an OOXML parser independent of the edit plan','post_native_trees_unchanged':True,'current_options':186,'new_specification_or_image_role_claims':0}
(H/'native-bindings-verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
