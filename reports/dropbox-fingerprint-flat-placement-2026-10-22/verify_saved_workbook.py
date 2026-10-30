from pathlib import Path
import json, zipfile, xml.etree.ElementTree as ET, posixpath, hashlib

HERE=Path(__file__).resolve().parent
PROJECT=HERE.parents[1]
CAT=PROJECT/'sculpture-catalogue'
MASTER=CAT/'components/reconciliation/fingerprint-numbered-master-refresh-2026-10-22'
pointer=json.loads((CAT/'current-master.json').read_text())
assert 'fingerprint-numbered-master-refresh' in pointer['register'], 'Fingerprint publication still pending'
path=CAT/pointer['workbook']
data=json.loads((MASTER/'workbook-data.json').read_text())
S='http://schemas.openxmlformats.org/spreadsheetml/2006/main'
R='http://schemas.openxmlformats.org/officeDocument/2006/relationships'
P='http://schemas.openxmlformats.org/package/2006/relationships'
def texts(node): return ''.join(n.text or '' for n in node.iter('{'+S+'}t'))
def col(n):
    result=''
    while n: n,r=divmod(n-1,26);result=chr(65+r)+result
    return result
def resolve(base,target): return target.lstrip('/') if target.startswith('/') else posixpath.normpath(posixpath.join(base,target))
def relmap(z,path):
    if path not in z.namelist(): return {}
    return {r.attrib['Id']:r.attrib['Target'] for r in ET.fromstring(z.read(path)).findall('{'+P+'}Relationship')}
checks=[]
with zipfile.ZipFile(path) as z:
    assert z.testzip() is None
    strings=[texts(n) for n in ET.fromstring(z.read('xl/sharedStrings.xml')).findall('{'+S+'}si')] if 'xl/sharedStrings.xml' in z.namelist() else []
    sheetrels=relmap(z,'xl/_rels/workbook.xml.rels')
    sheets={s.attrib['name']:resolve('xl',sheetrels[s.attrib['{'+R+'}id']]) for s in ET.fromstring(z.read('xl/workbook.xml')).findall('.//{'+S+'}sheet')}
    for name, expected in data['sheets'].items():
        sheetpath=sheets[name]
        tree=ET.fromstring(z.read(sheetpath))
        values={}
        for c in tree.findall('.//{'+S+'}sheetData/{'+S+'}row/{'+S+'}c'):
            value=c.find('{'+S+'}v')
            kind=c.attrib.get('t')
            assert kind!='e', (name,c.attrib['r'],'formula error')
            if kind=='inlineStr': value=texts(c)
            elif kind=='s': value=strings[int(value.text)] if value is not None else ''
            else: value=value.text if value is not None else ''
            values[c.attrib['r']]=value
        header_rows=[r for r in range(1,15) if values.get('A'+str(r))==expected['headers'][0]]
        assert len(header_rows)==1,(name,header_rows)
        head=header_rows[0]
        assert [values.get(col(c+1)+str(head),'') for c in range(len(expected['headers']))]==expected['headers']
        relpath=posixpath.dirname(sheetpath)+'/_rels/'+posixpath.basename(sheetpath)+'.rels'
        links=relmap(z,relpath)
        targets={n.attrib['ref']:links.get(n.attrib.get('{'+R+'}id'),n.attrib.get('location','')) for n in tree.findall('.//{'+S+'}hyperlink')}
        link_count=0
        for i,row in enumerate(expected['rows'],head+1):
            for j,v in enumerate(row,1):
                cell=col(j)+str(i)
                if isinstance(v,dict):
                    assert values.get(cell,'')==v['label'],(name,cell,'link label')
                    assert targets.get(cell)==v['target'],(name,cell,'native hyperlink')
                    link_count+=1
                elif isinstance(v,(int,float)):
                    assert float(values[cell])==v,(name,cell,'number')
                else:
                    assert values.get(cell,'')==('' if v is None else str(v)),(name,cell,'value')
        checks.append({'sheet':name,'header_row':head,'data_rows':len(expected['rows']),'columns':len(expected['headers']),'native_links_verified':link_count,'values_match_prepared_records':True,'formula_error_cells':0})
proof={'status':'PASS','workbook':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'views':checks,'native_links_verified':sum(c['native_links_verified'] for c in checks),'scope':'Saved XLSX native values, numbers and hyperlink targets in the two new Fingerprint views; no workbook writes.'}
assert proof['sha256']==pointer['workbook_sha256']
(HERE/'independent-saved-workbook-verification.json').write_text(json.dumps(proof,indent=2)+'\n')
print(json.dumps(proof,indent=2))
