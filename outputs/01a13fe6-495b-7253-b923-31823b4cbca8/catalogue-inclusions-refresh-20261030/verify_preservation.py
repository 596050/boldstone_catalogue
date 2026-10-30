"""Check that a narrow update preserved formulas, styles and native features."""
from pathlib import Path
import copy,json,zipfile
import xml.etree.ElementTree as ET

OUT=Path(__file__).resolve().parent
NS={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
changes=json.loads((OUT/'workbook-changes.json').read_text())
allowed={(r['sheet'],r['cell']) for r in changes['patches']}
allowed.update({('Wall Sculptures','A4'),('Wall Sculptures','A5'),('Images','A4'),('Specification Sources','A4'),('Upload Plan','A4')})

def canon(node):
    if node is None:return None
    return (node.tag,tuple(sorted(node.attrib.items())),node.text or '',tuple(canon(c) for c in node))

def read(path):
    with zipfile.ZipFile(path) as z:
        wb=ET.fromstring(z.read('xl/workbook.xml'))
        strings=[]
        if 'xl/sharedStrings.xml' in z.namelist():
            strings=[''.join(n.itertext()) for n in ET.fromstring(z.read('xl/sharedStrings.xml')).findall('s:si',NS)]
        st=ET.fromstring(z.read('xl/styles.xml'))
        fonts=st.find('s:fonts',NS);fills=st.find('s:fills',NS);borders=st.find('s:borders',NS)
        formats={int(n.attrib['numFmtId']):n.attrib['formatCode'] for n in st.findall('s:numFmts/s:numFmt',NS)}
        styles=[]
        for xf in st.find('s:cellXfs',NS):
            attrs=dict(xf.attrib)
            for key,items in [('fontId',fonts),('fillId',fills),('borderId',borders)]:
                attrs[key]=canon(items[int(attrs.get(key,0))])
            fmt=int(attrs.get('numFmtId',0));attrs['numFmtId']=formats.get(fmt,fmt)
            styles.append((attrs,tuple(canon(c) for c in xf)))
        sheets={}
        for i,s in enumerate(wb.findall('s:sheets/s:sheet',NS),1):
            xml=ET.fromstring(z.read(f'xl/worksheets/sheet{i}.xml'))
            cells={}
            for c in xml.findall('s:sheetData/s:row/s:c',NS):
                kind=c.attrib.get('t');v=c.find('s:v',NS);value=v.text if v is not None else None
                if kind=='s':value=strings[int(value)]
                elif kind=='inlineStr':value=''.join(c.find('s:is',NS).itertext())
                elif kind not in ('str','e','d') and value is not None:value=float(value)
                cells[c.attrib['r']]={'value':value,'formula':canon(c.find('s:f',NS)),'style':styles[int(c.attrib.get('s',0))]}
            features={tag:canon(xml.find('s:'+tag,NS)) for tag in ('cols','mergeCells','dataValidations','sheetFormatPr','sheetProtection','autoFilter','pageMargins','pageSetup','printOptions')}
            features['conditionalFormatting']=tuple(canon(x) for x in xml.findall('s:conditionalFormatting',NS))
            features['row_dimensions']=[dict(r.attrib) for r in xml.findall('s:sheetData/s:row',NS)]
            sheets[s.attrib['name']]={'cells':cells,'features':features}
        return {'sheets':sheets,'defined_names':canon(wb.find('s:definedNames',NS))}

before=read(OUT/'previous-catalogue.xlsx');after=read(OUT/'catalogue_wall_sculptures.xlsx')
assert list(before['sheets'])==list(after['sheets'])
assert before['defined_names']==after['defined_names'],'Defined names changed'
counts={'cells':0,'formulas':0};differences=[]
for name,old in before['sheets'].items():
    new=after['sheets'][name]
    assert old['features']==new['features'],(name,'Native sheet feature changed')
    assert set(old['cells'])==set(new['cells']),(name,'Cell set changed')
    for address,a in old['cells'].items():
        b=new['cells'][address];counts['cells']+=1
        assert a['formula']==b['formula'],(name,address,'Formula changed')
        assert a['style']==b['style'],(name,address,'Style changed')
        if a['formula'] is not None:counts['formulas']+=1
        if a['value']!=b['value']:
            assert (name,address) in allowed,(name,address,'Unexpected cell change',a['value'],b['value'])
            differences.append({'sheet':name,'cell':address,'before':a['value'],'after':b['value']})
report={'status':'PASS','all_seven_sheets_preserved':True,'native_features_preserved':True,'styles_preserved':True,
        'formulas_preserved':True,'counts':counts,'changed_cells':differences}
(OUT/'preservation-verification.json').write_text(json.dumps(report,indent=2))
print(json.dumps({k:v for k,v in report.items() if k!='changed_cells'}|{'changed_cell_count':len(differences)}))
