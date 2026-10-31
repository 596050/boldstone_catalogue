"""Restore only native hyperlinks and freeze panes unsupported by artifact round-trip."""
from pathlib import Path
import zipfile,xml.etree.ElementTree as E,json
OUT=Path(__file__).resolve().parent
NS='http://schemas.openxmlformats.org/spreadsheetml/2006/main'; R='http://schemas.openxmlformats.org/officeDocument/2006/relationships'; P='http://schemas.openxmlformats.org/package/2006/relationships'
E.register_namespace('',NS);E.register_namespace('r',R)
changes=json.loads((OUT/'workbook-changes.json').read_text())
sheet_names=['Wall Sculptures','Images','Specification Sources','Manufacturing Costs','Cost Rates','Cost Finishes','Upload Plan','Website Copy']
with zipfile.ZipFile(OUT/'previous-catalogue.xlsx') as z:before={n:z.read(n) for n in z.namelist()}
path=OUT/'catalogue_wall_sculptures.xlsx'
with zipfile.ZipFile(path) as z:after={n:z.read(n) for n in z.namelist()}
for index in range(1,len(sheet_names)+1):
 name=f'xl/worksheets/sheet{index}.xml';rn=f'xl/worksheets/_rels/sheet{index}.xml.rels'
 old=E.fromstring(before[name]) if name in before else E.Element('{'+NS+'}worksheet');cur=E.fromstring(after[name])
 rel=E.fromstring(after[rn]) if rn in after else E.Element('{'+P+'}Relationships')
 for el in list(rel):
  if el.get('Type')==R+'/hyperlink':rel.remove(el)
 used={el.get('Id') for el in rel}
 oldrel=E.fromstring(before[rn]) if rn in before else E.Element('{'+P+'}Relationships')
 byid={el.get('Id'):el for el in oldrel}
 links=old.find('{'+NS+'}hyperlinks')
 for el in list(cur):
  if el.tag=='{'+NS+'}hyperlinks':cur.remove(el)
 if links is None:links=E.Element('{'+NS+'}hyperlinks')
 if links is not None:
  for i,link in enumerate(links):
   rid=link.get('{'+R+'}id')
   if rid:
    node=byid[rid];newrid='rIdPreservedLink'+str(i)
    assert newrid not in used;node.set('Id',newrid);link.set('{'+R+'}id',newrid);rel.append(node)
  for i,item in enumerate(changes['new_hyperlinks']):
   if item['sheet']!=sheet_names[index-1]:continue
   rid='rIdWebsiteLink'+str(i)
   E.SubElement(rel,'{'+P+'}Relationship',{'Id':rid,'Type':R+'/hyperlink','Target':item['target'],'TargetMode':'External'})
   E.SubElement(links,'{'+NS+'}hyperlink',{'ref':item['cell'],'{'+R+'}id':rid})
  following={'printOptions','pageMargins','pageSetup','headerFooter','rowBreaks','colBreaks','customProperties','cellWatches','ignoredErrors','smartTags','drawing','legacyDrawing','legacyDrawingHF','picture','oleObjects','controls','webPublishItems','tableParts','extLst'}
  pos=next((i for i,e in enumerate(cur) if e.tag.split('}')[-1] in following),len(cur));cur.insert(pos,links)
 oldviews=old.find('{'+NS+'}sheetViews');newviews=cur.find('{'+NS+'}sheetViews')
 if oldviews is not None:
  pos=list(cur).index(newviews) if newviews is not None else 0
  if newviews is not None:cur.remove(newviews)
  cur.insert(pos,oldviews)
 after[name]=E.tostring(cur,encoding='utf-8',xml_declaration=True)
 if len(rel):after[rn]=E.tostring(rel,encoding='utf-8',xml_declaration=True)
with zipfile.ZipFile(path.with_suffix('.tmp.xlsx'),'w',compression=zipfile.ZIP_DEFLATED) as z:
 for n,b in after.items():z.writestr(n,b)
path.with_suffix('.tmp.xlsx').replace(path)
