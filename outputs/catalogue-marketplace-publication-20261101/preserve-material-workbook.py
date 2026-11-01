"""Transplant only authored copy cells, and independently verify every native part."""
from pathlib import Path
import copy, hashlib, json, zipfile, xml.etree.ElementTree as E

OUT=Path(__file__).resolve().parent
changes=json.loads((OUT/'material-workbook-patches.json').read_text())
U='http://schemas.openxmlformats.org/spreadsheetml/2006/main';NS={'s':U};q=lambda s:'{'+U+'}'+s
E.register_namespace('',U)
def shared(z):
    if 'xl/sharedStrings.xml' not in z.namelist():return []
    return [''.join(t.text or '' for t in e.iter(q('t'))) for e in E.fromstring(z.read('xl/sharedStrings.xml')).findall('s:si',NS)]
def value(c,ss):
    if c is None:return None
    if c.get('t')=='inlineStr':return ''.join(t.text or '' for t in c.iter(q('t')))
    v=c.find('s:v',NS)
    if c.get('t')=='s':return ss[int(v.text)]
    f=c.find('s:f',NS)
    if f is not None:return '='+f.text
    return v.text if v is not None else None
with zipfile.ZipFile(OUT/'previous-catalogue.xlsx') as original,zipfile.ZipFile(OUT/'material-workbook-authored.xlsx') as authored:
    oldparts={n:original.read(n) for n in original.namelist()};parts=dict(oldparts)
    ss=shared(authored);oldss=shared(original)
    for i,sheet in enumerate(changes['sheets'],1):
        patches=[p for p in changes['patches'] if p['sheet']==sheet]
        if not patches:continue
        name=f'xl/worksheets/sheet{i}.xml';root=E.fromstring(parts[name]);source=E.fromstring(authored.read(name))
        src={c.get('r'):c for c in source.findall('s:sheetData/s:row/s:c',NS)}
        rows={int(r.get('r')):r for r in root.findall('s:sheetData/s:row',NS)}
        for p in patches:
            addr=p['cell'];row=rows[int(''.join(c for c in addr if c.isdigit()))]
            old=next((c for c in row if c.get('r')==addr),None)
            new=copy.deepcopy(src[addr]);actual=value(new,ss)
            assert actual==str(p['value']), (sheet,addr,actual)
            if old is not None and old.get('s'):new.set('s',old.get('s'))
            if new.get('t')=='s':
                for c in list(new):new.remove(c)
                new.set('t','inlineStr');t=E.SubElement(E.SubElement(new,q('is')),q('t'));t.text=actual;t.set('{http://www.w3.org/XML/1998/namespace}space','preserve')
            if old is None:row.append(new)
            else:
                idx=list(row).index(old);row.remove(old);row.insert(idx,new)
        parts[name]=E.tostring(root,encoding='utf-8',xml_declaration=True)
    target=OUT/'catalogue_wall_sculptures.xlsx'
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as z:
        for n,b in parts.items():z.writestr(n,b)
    checked=0;links=0
    for i,sheet in enumerate(changes['sheets'],1):
        name=f'xl/worksheets/sheet{i}.xml';a=E.fromstring(oldparts[name]);b=E.fromstring(parts[name])
        patches={p['cell']:p for p in changes['patches'] if p['sheet']==sheet}
        ac={c.get('r'):c for c in a.findall('s:sheetData/s:row/s:c',NS)};bc={c.get('r'):c for c in b.findall('s:sheetData/s:row/s:c',NS)}
        assert set(ac)==set(bc),(sheet,'cell address set changed')
        for addr,old in ac.items():
            if addr in patches:assert value(bc[addr],oldss)==str(patches[addr]['value']);checked+=1
            else:assert E.tostring(old)==E.tostring(bc[addr]),(sheet,addr,'unrelated cell changed')
        for tag in ['hyperlinks','sheetViews','autoFilter','mergeCells','tableParts','cols']:
            x=a.find('s:'+tag,NS);y=b.find('s:'+tag,NS)
            assert (E.tostring(x) if x is not None else None)==(E.tostring(y) if y is not None else None),(sheet,tag)
        links+=len(a.findall('s:hyperlinks/s:hyperlink',NS))
    changedparts=[n for n in oldparts if oldparts[n]!=parts[n]]
    assert len(changedparts)==4 and checked==len(changes['patches'])
    receipt={'status':'PASS','products':181,'cells_updated':checked,'native_parts_changed':changedparts,'hyperlinks_preserved':links,'unrelated_cells_and_native_parts_unchanged':True,'sha256':hashlib.sha256(target.read_bytes()).hexdigest()}
    (OUT/'material-workbook-verification.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt))
