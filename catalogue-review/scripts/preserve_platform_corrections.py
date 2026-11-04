"""Transplant only artifact-authored cell changes; retain native XLSX features."""
import copy
import hashlib
import json
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as E
import zipfile

OUT=Path(sys.argv[1]).resolve()
plan=json.loads((OUT/(sys.argv[2] if len(sys.argv)>2 else 'corrections-plan.json')).read_text())
U='http://schemas.openxmlformats.org/spreadsheetml/2006/main';R='http://schemas.openxmlformats.org/officeDocument/2006/relationships'
NS={'s':U};q=lambda s:'{'+U+'}'+s
E.register_namespace('',U);E.register_namespace('r',R)
def paths(z):
    rel={e.get('Id'):'xl/'+e.get('Target').lstrip('/').removeprefix('xl/') for e in E.fromstring(z.read('xl/_rels/workbook.xml.rels'))}
    return {e.get('name'):rel[e.get('{'+R+'}id')] for e in E.fromstring(z.read('xl/workbook.xml')).find('s:sheets',NS)}
def strings(z):
    return [''.join(t.text or '' for t in e.iter(q('t'))) for e in E.fromstring(z.read('xl/sharedStrings.xml'))] if 'xl/sharedStrings.xml' in z.namelist() else []
def value(c,ss):
    if c is None:return None
    if c.get('t')=='inlineStr':return ''.join(t.text or '' for t in c.iter(q('t')))
    v=c.find('s:v',NS);t=v.text if v is not None else ''
    if c.get('t')=='s':return ss[int(t)]
    if c.get('t')=='b':return t=='1'
    if c.get('t')=='e':raise ValueError('Formula error '+str(t))
    return float(t) if t and c.get('t','n')=='n' else t
def ix(a):
    n=0
    for c in re.sub(r'\d','',a):n=n*26+ord(c)-64
    return n
with zipfile.ZipFile(OUT/'previous-catalogue.xlsx') as oz,zipfile.ZipFile(OUT/'authored.xlsx') as az:
    parts={n:oz.read(n) for n in oz.namelist()};original=dict(parts)
    op,ap=paths(oz),paths(az);ss=strings(az);oldss=strings(oz)
    styles=E.fromstring(parts['xl/styles.xml']);authstyles=E.fromstring(az.read('xl/styles.xml'))
    def append_unique(parent,e):
        text=E.tostring(e)
        for i,existing in enumerate(parent):
            if E.tostring(existing)==text:return i
        parent.append(copy.deepcopy(e));parent.set('count',str(len(parent)));return len(parent)-1
    maps={}
    for tag in ('fonts','fills','borders'):
        dest=styles.find('s:'+tag,NS);src=authstyles.find('s:'+tag,NS)
        maps[tag]={str(i):str(append_unique(dest,e)) for i,e in enumerate(src)}
    fmts=styles.find('s:numFmts',NS);afmts=authstyles.find('s:numFmts',NS);fmtmap={}
    for e in list(afmts) if afmts is not None else []:
        found=next((f.get('numFmtId') for f in fmts if f.get('formatCode')==e.get('formatCode')),None)
        if found is None:
            found=str(max([163]+[int(f.get('numFmtId')) for f in fmts])+1)
            new=copy.deepcopy(e);new.set('numFmtId',found);fmts.append(new)
        fmtmap[e.get('numFmtId')]=found
    fmts.set('count',str(len(fmts)))
    xfs=styles.find('s:cellXfs',NS);stylemap={}
    for i,e in enumerate(authstyles.find('s:cellXfs',NS)):
        e=copy.deepcopy(e)
        for key,tag in [('fontId','fonts'),('fillId','fills'),('borderId','borders')]:
            if e.get(key) is not None:e.set(key,maps[tag][e.get(key)])
        if e.get('numFmtId') in fmtmap:e.set('numFmtId',fmtmap[e.get('numFmtId')])
        # Only ordinary worksheet cell styles are imported.
        e.set('xfId','0');stylemap[str(i)]=str(append_unique(xfs,e))
    altered={'xl/styles.xml'};preserved=patched=added=links=0
    for name,path in op.items():
        patches={p['cell']:p for p in plan['patches'] if p['sheet']==name}
        before=E.fromstring(parts[path]);after=copy.deepcopy(before)
        bc={c.get('r'):c for c in before.findall('s:sheetData/s:row/s:c',NS)}
        if patches:
            authored=E.fromstring(az.read(ap[name]));ac={c.get('r'):c for c in authored.findall('s:sheetData/s:row/s:c',NS)}
            rows={int(r.get('r')):r for r in after.findall('s:sheetData/s:row',NS)}
            for address,p in patches.items():
                new=copy.deepcopy(ac.get(address)) if ac.get(address) is not None else E.Element(q('c'),{'r':address})
                got=value(new,ss);exp=p['value']
                assert (exp is None and got in (None,'')) or (isinstance(exp,(int,float)) and not isinstance(exp,bool) and isinstance(got,(int,float)) and abs(got-exp)<.011) or got==exp,(name,address,exp,got)
                if new.get('t')=='s':
                    for child in list(new):new.remove(child)
                    new.set('t','inlineStr');t=E.SubElement(E.SubElement(new,q('is')),q('t'));t.set('{http://www.w3.org/XML/1998/namespace}space','preserve');t.text=got
                if p['formula']:assert new.find('s:f',NS).text==p['formula'][1:]
                if address in bc and not p.get('format'):new.set('s',bc[address].get('s','0'))
                else:new.set('s',stylemap[new.get('s','0')])
                n=int(re.search(r'\d+',address).group());row=rows[n]
                prior=next((c for c in row if c.get('r')==address),None)
                if prior is not None:row.remove(prior);patched+=1
                else:added+=1
                row.append(new);row[:]=sorted(row,key=lambda c:ix(c.get('r')))
            for change in plan.get('row_format_updates',[]):
                if change['sheet']==name:
                    rows[change['row']].set('ht',str(change['height']))
                    rows[change['row']].set('customHeight','1')
            for change in plan.get('column_format_updates',[]):
                if change['sheet']==name:
                    cols=after.find('s:cols',NS)
                    assert cols is not None
                    covering=[c for c in cols if int(c.get('min'))<=change['last'] and int(c.get('max'))>=change['first']]
                    assert not covering,'Existing column widths require explicit reconciliation'
                    E.SubElement(cols,q('col'),{'min':str(change['first']),'max':str(change['last']),'width':str(change['width']),'customWidth':'1'})
            if name=='Wall Sculptures':
                # Header allocation can precede writes, so use the actual final index.
                last=max(plan['headers'].values(),key=ix)
                dim=after.find('s:dimension',NS);dim.set('ref','A1:'+last+'188')
                cols=after.find('s:cols',NS)
                for number in range(plan.get('first_master_column',264),plan['last_master_column']+1):
                    if not any(int(c.get('min'))<=number<=int(c.get('max')) for c in cols):
                        E.SubElement(cols,q('col'),{'min':str(number),'max':str(number),'width':'32','customWidth':'1'})
            else:
                dim=after.find('s:dimension',NS)
                if dim is not None:
                    last=dim.get('ref').split(':')[-1]
                    maxcol=max([ix(last)]+[ix(a) for a in patches])
                    maxrow=max([int(re.search(r'\d+',last).group())]+[int(re.search(r'\d+',a).group()) for a in patches])
                    label='';n=maxcol
                    while n:n,d=divmod(n-1,26);label=chr(65+d)+label
                    dim.set('ref','A1:'+label+str(maxrow))
            parts[path]=E.tostring(after,encoding='utf-8',xml_declaration=True);altered.add(path)
        nc={c.get('r'):c for c in after.findall('s:sheetData/s:row/s:c',NS)}
        for address,c in bc.items():
            if address not in patches:assert E.tostring(c)==E.tostring(nc[address]),(name,address);preserved+=1
        for tag in ('hyperlinks','sheetViews','mergeCells','tableParts','conditionalFormatting','dataValidations'):
            assert [E.tostring(x) for x in before.findall('s:'+tag,NS)]==[E.tostring(x) for x in after.findall('s:'+tag,NS)],(name,tag)
        links+=len(before.findall('s:hyperlinks/s:hyperlink',NS))
    master=E.fromstring(parts[op['Wall Sculptures']]);rid=master.find('s:tableParts/s:tablePart',NS).get('{'+R+'}id')
    relpath='xl/worksheets/_rels/'+Path(op['Wall Sculptures']).name+'.rels'
    rels={e.get('Id'):e.get('Target') for e in E.fromstring(parts[relpath])}
    t=rels[rid].lstrip('/');tablepath=t if t.startswith('xl/') else 'xl/'+t.removeprefix('../')
    table=E.fromstring(parts[tablepath]);columns=table.find('s:tableColumns',NS)
    byindex={ix(c):h for h,c in plan['headers'].items()}
    for rename in plan.get('header_renames', []):
        tablecolumn=columns[ix(rename['column'])-1]
        assert tablecolumn.get('name')==rename['before'], rename
        tablecolumn.set('name',rename['value'])
    for i in range(len(columns)+1,plan['last_master_column']+1):E.SubElement(columns,q('tableColumn'),{'id':str(i),'name':byindex[i]})
    columns.set('count',str(len(columns)));table.set('ref','A7:'+max(plan['headers'].values(),key=ix)+'188')
    auto=table.find('s:autoFilter',NS)
    if auto is not None:auto.set('ref',table.get('ref'))
    parts[tablepath]=E.tostring(table,encoding='utf-8',xml_declaration=True);altered.add(tablepath)
    parts['xl/styles.xml']=E.tostring(styles,encoding='utf-8',xml_declaration=True)
    assert all(original[k]==v for k,v in parts.items() if k not in altered)
    target=OUT/'catalogue_wall_sculptures.xlsx'
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as z:
        for n,b in parts.items():z.writestr(n,b)
    with zipfile.ZipFile(target) as z:assert z.testzip() is None and paths(z)==op
    receipt={'status':'PASS','sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'cells_updated':patched,'cells_added':added,
             'unrelated_cells_preserved':preserved,'hyperlinks_preserved':links,'sheets':len(op),'native_features_preserved':True}
    (OUT/'verification.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
