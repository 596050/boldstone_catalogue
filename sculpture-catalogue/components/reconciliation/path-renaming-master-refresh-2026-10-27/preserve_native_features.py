"""Transcode declared Artifact-authored edits into the original XLSX package.

No business value or hyperlink target is invented here. The original source
tabs, tables, formatting, relationships and history remain intact. New-sheet
style and table dependencies are copied from the tool-authored export.
"""
from common import *
from copy import deepcopy
from xml.etree import ElementTree as E
from pathlib import PurePosixPath
import os, posixpath, re, zipfile

M=native.M;R=native.R;P=native.P;CT='{http://schemas.openxmlformats.org/package/2006/content-types}'
E.register_namespace('',M[1:-1]);E.register_namespace('r',R[1:-1])
def xml(x):
    # System.IO.Packaging requires unprefixed Content Types element names.
    # Keep the native root namespace as the default for each package part.
    if x.tag.startswith('{'):E.register_namespace('',x.tag.split('}')[0][1:])
    return E.tostring(x,encoding='utf-8',xml_declaration=True)
def inline(c,strings):
    c=deepcopy(c)
    if c.get('t')=='s':
        item=deepcopy(strings[int(c.findtext(M+'v'))]);item.tag=M+'is'
        c.remove(c.find(M+'v'));c.append(item);c.set('t','inlineStr')
    return c
def relpart(p):return posixpath.join(posixpath.dirname(p),'_rels',posixpath.basename(p)+'.rels')
rel_counters={}
def nextid(rels,prefix='rId'):
    key=(rels,prefix)
    if key not in rel_counters:
        nums=[int(e.get('Id')[len(prefix):]) for e in rels if re.fullmatch(prefix+r'\d+',e.get('Id',''))]
        rel_counters[key]=max(nums,default=0)
    rel_counters[key]+=1
    return prefix+str(rel_counters[key])
def cache(c):return (c.get('t'),c.findtext(M+'v'))
def findcells(root):return {c.get('r'):c for c in root.iter(M+'c')}

receipts=[]
for plan in read(H/'workbook-edit-plan.json')['plans']:
    output=Path(plan['output']);raw=H/(plan['key']+'-artifact-authored.xlsx')
    assert output.is_file()
    if not raw.exists():raw.write_bytes(output.read_bytes())
    src,don=Book(plan['source']),Book(raw)
    parts={p:src.zip.read(p) for p in src.zip.namelist()}
    strings=E.fromstring(don.zip.read('xl/sharedStrings.xml')) if 'xl/sharedStrings.xml' in don.zip.namelist() else []
    bysheet={}
    for ed in plan['edits']:bysheet.setdefault(ed['sheet'],{})[ed['cell']]=ed
    modified=set();cachechanges=[];transferred=0;linkcount=0
    for sn,sp in src.sheets.items():
        root=E.fromstring(parts[sp]);dr=E.fromstring(don.zip.read(don.sheets[sn]));sc,dc=findcells(root),findcells(dr)
        row_by_ref={c.get('r'):row for row in root.iter(M+'row') for c in row if c.tag==M+'c'}
        edits=bysheet.get(sn,{})
        for ref,old in sc.items():
            if ref in edits or old.find(M+'f') is None:continue
            new=dc.get(ref)
            assert new is not None and new.findtext(M+'f')==old.findtext(M+'f'),(sn,ref,'formula drift')
            # The SDK preserves HYPERLINK syntax but its calculation engine
            # returns an unsupported-function message. Keep original caches
            # for untouched formulas; transcode authored links below.
            if re.match(r'HYPERLINK\(',old.findtext(M+'f') or '',re.I):continue
            if cache(old)!=cache(new):
                assert new.get('t')!='e',(sn,ref,'new formula error')
                cachechanges.append({'sheet':sn,'cell':ref,'before':cache(old),'after':cache(new)})
        needed=set(edits)|{r['cell'] for r in cachechanges if r['sheet']==sn}
        if not needed:continue
        rp=relpart(sp);rels=E.fromstring(parts[rp]) if rp in parts else E.Element(P+'Relationships')
        links=root.find(M+'hyperlinks')
        links_by_ref={x.get('ref'):x for x in links} if links is not None else {}
        for ref in sorted(needed,key=lambda s:(int(re.search(r'\d+',s)[0]),s)):
            ed=edits.get(ref);new=dc.get(ref)
            assert new is not None,(sn,ref,'missing tool-authored cell')
            old=sc.get(ref)
            if ed and ed['kind']=='hyperlink':
                expected=ed['formula'].lstrip('=')
                assert new.findtext(M+'f')==expected,(sn,ref,'target differs from declared SDK formula')
                m=re.fullmatch(r'HYPERLINK\("((?:[^"]|"")*)","((?:[^"]|"")*)"\)',expected,re.I)
                assert m
                url,label=[s.replace('""','"') for s in m.groups()]
                assert (url,label)==(ed['url'],ed['label'])
                if not ed['keep_formula']:
                    semantic=E.Element(M+'c',{'r':ref,'t':'inlineStr'})
                    E.SubElement(E.SubElement(semantic,M+'is'),M+'t').text=label
                    new=semantic
                else:
                    new=deepcopy(new);new.set('t','str')
                    cached=new.find(M+'v')
                    if cached is None:cached=E.SubElement(new,M+'v')
                    cached.text=label
                if not ed['keep_formula'] or ref in links_by_ref:
                    if links is None:
                        links=E.Element(M+'hyperlinks')
                        # Hyperlinks follow data/filters/conditional formatting
                        # and precede print settings, drawings and tableParts.
                        later={'printOptions','pageMargins','pageSetup','headerFooter','rowBreaks','colBreaks','customProperties','cellWatches','ignoredErrors','smartTags','drawing','legacyDrawing','legacyDrawingHF','picture','oleObjects','controls','webPublishItems','tableParts','extLst'}
                        idx=next((i for i,x in enumerate(root) if x.tag.split('}')[-1] in later),len(root));root.insert(idx,links)
                    if ref in links_by_ref:links.remove(links_by_ref[ref])
                    rid=nextid(rels)
                    E.SubElement(rels,P+'Relationship',{'Id':rid,'Type':R[1:-1]+'/hyperlink','Target':url,'TargetMode':'External'})
                    E.SubElement(links,M+'hyperlink',{'ref':ref,R+'id':rid});linkcount+=1
            new=inline(new,strings)
            # Keep original formatting, or inherit the preallocated row style.
            if old is not None:style=old.get('s')
            else:
                col=re.match(r'[A-Z]+',ref)[0];number=int(re.search(r'\d+',ref)[0])
                previous=[(int(re.search(r'\d+',s)[0]),c) for s,c in sc.items() if re.match(r'[A-Z]+',s)[0]==col and int(re.search(r'\d+',s)[0])<number]
                style=max(previous,key=lambda x:x[0])[1].get('s') if previous else None
            if style is None:new.attrib.pop('s',None)
            else:new.set('s',style)
            new.set('r',ref)
            if old is not None:
                for k,v in old.attrib.items():
                    if k not in {'t','s'}:new.set(k,v)
                row=row_by_ref[ref];index=list(row).index(old);row.remove(old);row.insert(index,new)
            else:
                n=re.search(r'\d+',ref)[0];row=next((r for r in root.iter(M+'row') if r.get('r')==n),None)
                if row is None:
                    previous_rows=[r for r in root.iter(M+'row') if int(r.get('r'))<int(n)]
                    attrs=dict(max(previous_rows,key=lambda r:int(r.get('r'))).attrib) if previous_rows else {}
                    attrs['r']=n;row=E.SubElement(root.find(M+'sheetData'),M+'row',attrs)
                row.append(new)
            transferred+=1
        parts[sp]=xml(root);modified.add(sp)
        if linkcount and (rp in parts or len(rels)):
            parts[rp]=xml(rels);modified.add(rp)
    if plan['new_sheet']:
        sn=plan['new_sheet'];dr=E.fromstring(don.zip.read(don.sheets[sn]))
        source_styles=E.fromstring(parts['xl/styles.xml']);don_styles=E.fromstring(don.zip.read('xl/styles.xml'))
        maps={};before_styles=deepcopy(source_styles)
        def append_style(tag,index):
            index=int(index);k=(tag,index)
            if k in maps:return maps[k]
            source=source_styles.find(M+tag); donor=don_styles.find(M+tag)
            if source is None:source=E.Element(M+tag);source_styles.insert(0,source)
            obj=deepcopy(list(donor)[index])
            if tag in {'cellXfs','cellStyleXfs'}:
                for attr,dep in [('fontId','fonts'),('fillId','fills'),('borderId','borders')]:
                    if attr in obj.attrib:obj.set(attr,str(append_style(dep,obj.get(attr))))
                if int(obj.get('numFmtId','0'))>=164:
                    dnf=next(x for x in don_styles.find(M+'numFmts') if x.get('numFmtId')==obj.get('numFmtId'))
                    snf=source_styles.find(M+'numFmts')
                    if snf is None:snf=E.Element(M+'numFmts',{'count':'0'});source_styles.insert(0,snf)
                    match=next((x for x in snf if x.get('formatCode')==dnf.get('formatCode')),None)
                    if match is None:
                        match=deepcopy(dnf);match.set('numFmtId',str(max([163]+[int(x.get('numFmtId')) for x in snf])+1));snf.append(match);snf.set('count',str(len(snf)))
                    obj.set('numFmtId',match.get('numFmtId'))
                if tag=='cellXfs' and 'xfId' in obj.attrib:obj.set('xfId',str(append_style('cellStyleXfs',obj.get('xfId'))))
            found=next((i for i,x in enumerate(source) if E.tostring(x)==E.tostring(obj)),None)
            if found is None:found=len(source);source.append(obj);source.set('count',str(len(source)))
            maps[k]=found;return found
        for c in dr.iter(M+'c'):
            if c.get('t')=='s':
                new=inline(c,strings);c.clear();c.attrib.update(new.attrib);c.extend(list(new))
            if c.get('s') is not None:c.set('s',str(append_style('cellXfs',c.get('s'))))
        for row in dr.iter(M+'row'):
            if row.get('s') is not None:row.set('s',str(append_style('cellXfs',row.get('s'))))
        for col in dr.iter(M+'col'):
            if col.get('style') is not None:col.set('style',str(append_style('cellXfs',col.get('style'))))
        # Every pre-existing style element remains at its original index.
        for group in before_styles:
            now=source_styles.find(group.tag)
            assert all(E.tostring(x)==E.tostring(list(now)[i]) for i,x in enumerate(group)),group.tag
        parts['xl/styles.xml']=xml(source_styles);modified.add('xl/styles.xml')
        num=max(int(re.search(r'sheet(\d+)\.xml',p)[1]) for p in src.sheets.values())+1
        newpath=f'xl/worksheets/sheet{num}.xml';newrels=E.Element(P+'Relationships')
        donor_rels=E.fromstring(don.zip.read(relpart(don.sheets[sn]))) if relpart(don.sheets[sn]) in don.zip.namelist() else []
        content=E.fromstring(parts['[Content_Types].xml'])
        for rel in donor_rels:
            assert rel.get('Type').endswith('/table'), 'Unexpected new sheet dependency'
            oldpart=native.resolve(don.sheets[sn],rel.get('Target'));table=E.fromstring(don.zip.read(oldpart))
            tid=max([0]+[int(re.search(r'table(\d+)\.xml',p)[1]) for p in parts if re.fullmatch(r'xl/tables/table\d+\.xml',p)])+1
            native_tid=max([0]+[int(E.fromstring(data).get('id')) for name,data in parts.items() if re.fullmatch(r'xl/tables/table\d+\.xml',name)])+1
            table.set('id',str(native_tid));target=f'xl/tables/table{tid}.xml';parts[target]=xml(table)
            E.SubElement(newrels,P+'Relationship',{'Id':rel.get('Id'),'Type':rel.get('Type'),'Target':'../tables/'+PurePosixPath(target).name})
            E.SubElement(content,CT+'Override',{'PartName':'/'+target,'ContentType':'application/vnd.openxmlformats-officedocument.spreadsheetml.table+xml'})
        # Native hyperlink cells are the supported equivalent of the SDK's
        # authored HYPERLINK formulas; URL and label come from those formulas.
        newlinks=E.SubElement(dr,M+'hyperlinks')
        for cell in list(dr.iter(M+'c')):
            formula=cell.findtext(M+'f') or ''
            if not re.match(r'HYPERLINK\(',formula,re.I):continue
            match=re.fullmatch(r'HYPERLINK\("((?:[^"]|"")*)","((?:[^"]|"")*)"\)',formula,re.I);assert match
            url,label=[s.replace('""','"') for s in match.groups()]
            rid=nextid(newrels);E.SubElement(newrels,P+'Relationship',{'Id':rid,'Type':R[1:-1]+'/hyperlink','Target':url,'TargetMode':'External'})
            E.SubElement(newlinks,M+'hyperlink',{'ref':cell.get('r'),R+'id':rid})
            attrs=dict(cell.attrib);attrs['t']='inlineStr';cell.clear();cell.attrib.update(attrs)
            E.SubElement(E.SubElement(cell,M+'is'),M+'t').text=label
        # Keep OOXML child order valid: hyperlinks precede tableParts.
        dr.remove(newlinks);tp=dr.find(M+'tableParts');dr.insert(list(dr).index(tp) if tp is not None else len(dr),newlinks)
        parts[newpath]=xml(dr)
        if len(newrels):parts[relpart(newpath)]=xml(newrels)
        wb=E.fromstring(parts['xl/workbook.xml']);wrels=E.fromstring(parts['xl/_rels/workbook.xml.rels']);rid=nextid(wrels)
        sid=max(int(x.get('sheetId')) for x in wb.find(M+'sheets'))+1
        E.SubElement(wb.find(M+'sheets'),M+'sheet',{'name':sn,'sheetId':str(sid),R+'id':rid})
        E.SubElement(wrels,P+'Relationship',{'Id':rid,'Type':R[1:-1]+'/worksheet','Target':'worksheets/'+PurePosixPath(newpath).name})
        E.SubElement(content,CT+'Override',{'PartName':'/'+newpath,'ContentType':'application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml'})
        for name,root in [('xl/workbook.xml',wb),('xl/_rels/workbook.xml.rels',wrels),('[Content_Types].xml',content)]:parts[name]=xml(root);modified.add(name)
    temp=output.with_suffix('.native-pending.xlsx')
    with zipfile.ZipFile(temp,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for p,payload in parts.items():z.writestr(p,payload)
    os.replace(temp,output)
    receipts.append({'key':plan['key'],'source_sha256':sha(plan['source']),'artifact_authored_snapshot':str(raw),'artifact_authored_sha256':sha(raw),'output':str(output),'output_sha256':sha(output),'declared_semantic_edits':len(plan['edits']),'tool_authored_cells_transferred':transferred,'hyperlink_transcodes':linkcount,'formula_cache_changes':cachechanges,'modified_existing_parts':sorted(modified),'new_parts':sorted(set(parts)-set(src.zip.namelist())),'existing_parts_byte_preserved':sum(p not in modified for p in src.zip.namelist())})
    src.close();don.close()
write(H/'native-preservation-receipt.json',{'status':'NATIVE_FEATURES_PRESERVED_PENDING_INDEPENDENT_READBACK','workbooks':receipts})
print(json.dumps([{k:r[k] for k in ['key','declared_semantic_edits','hyperlink_transcodes','existing_parts_byte_preserved']} for r in receipts]))
