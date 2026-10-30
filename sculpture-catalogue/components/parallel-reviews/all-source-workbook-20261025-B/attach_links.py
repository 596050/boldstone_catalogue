"""Attach native hyperlinks only; Artifact Tool authored all workbook cells."""
from pathlib import Path
from xml.etree import ElementTree as E
import json,zipfile,hashlib
W=Path(__file__).resolve().parent
d=json.loads((W/'workbook-data.json').read_text());target=Path(d['output'])
S='http://schemas.openxmlformats.org/spreadsheetml/2006/main';R='http://schemas.openxmlformats.org/officeDocument/2006/relationships';P='http://schemas.openxmlformats.org/package/2006/relationships'
E.register_namespace('',S);E.register_namespace('r',R)
def col(n):
 s='';n+=1
 while n:n,k=divmod(n-1,26);s=chr(65+k)+s
 return s
with zipfile.ZipFile(target) as z:parts={n:z.read(n) for n in z.namelist()}
original=dict(parts);changed=set();total=internal=0
for k,t in enumerate(d['tabs'],1):
 if not t['links']:continue
 name=f'xl/worksheets/sheet{k}.xml';rn=f'xl/worksheets/_rels/sheet{k}.xml.rels'
 root=E.fromstring(parts[name]);old=E.fromstring(parts[name]);rels=E.fromstring(parts[rn]) if rn in parts else E.Element('{'+P+'}Relationships')
 assert root.find('{'+S+'}hyperlinks') is None
 links=E.Element('{'+S+'}hyperlinks');used={x.get('Id') for x in rels}
 for ij,v in t['links'].items():
  i,j=map(int,ij.split(','));attrs={'ref':col(j)+str(i+7),'display':v['label']};u=v['target']
  if u.startswith('#'):attrs['location']=u[1:];internal+=1
  else:
   rid='sourceLink_'+str(i)+'_'+str(j);assert rid not in used;used.add(rid)
   attrs['{'+R+'}id']=rid
   E.SubElement(rels,'{'+P+'}Relationship',{'Id':rid,'Type':R+'/hyperlink','Target':u,'TargetMode':'External'})
  E.SubElement(links,'{'+S+'}hyperlink',attrs);total+=1
 later={'printOptions','pageMargins','pageSetup','headerFooter','rowBreaks','colBreaks','customProperties','cellWatches','ignoredErrors','smartTags','drawing','legacyDrawing','legacyDrawingHF','picture','oleObjects','controls','webPublishItems','tableParts','extLst'}
 at=next((i for i,x in enumerate(root) if x.tag.rsplit('}',1)[-1] in later),len(root));root.insert(at,links)
 parts[name]=E.tostring(root,encoding='utf-8',xml_declaration=True)
 parts[rn]=E.tostring(rels,encoding='utf-8',xml_declaration=True)
 root.remove(links);assert E.tostring(root)==E.tostring(old)
 changed.update([name,rn])
for name in set(original)-changed:assert parts[name]==original[name]
temp=target.with_suffix('.pending.xlsx')
with zipfile.ZipFile(temp,'w',compression=zipfile.ZIP_DEFLATED) as z:
 for name,content in parts.items():z.writestr(name,content)
temp.replace(target)
r={'status':'PASS_NATIVE_LINKS_ATTACHED_WITHOUT_CELL_OR_STYLE_EDITS','hyperlinks':total,'internal_links':internal,'external_links':total-internal,'other_parts_identical':True,'saved_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'missing_capability':'Artifact HYPERLINK calculation is not implemented; standard OOXML hyperlink relationships used.'}
(W/'native-hyperlink-receipt.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
