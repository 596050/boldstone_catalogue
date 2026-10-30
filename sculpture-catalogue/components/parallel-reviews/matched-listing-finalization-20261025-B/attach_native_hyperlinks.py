#!/usr/bin/env python3
"""Missing-feature adapter: add native link relationships to Artifact-authored cells.

No cell values, formulas, styles, dimensions or other workbook parts are changed.
Artifact Tool has no documented native-link API and its HYPERLINK calculation
returns an unimplemented message. The authoring script supplies the labels.
"""
import json
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

WORK=Path(__file__).resolve().parent
OUT=Path('/Users/tprice/Documents/boldstone/sculpture-catalogue/outputs/01a13fe6-495b-7253-b923-31823b4cbca8/matched-listing-2026-10-25')
TARGET=OUT/'Boldstone_Matched_Product_List_2026-10-25.xlsx'
S='http://schemas.openxmlformats.org/spreadsheetml/2006/main'
R='http://schemas.openxmlformats.org/officeDocument/2006/relationships'
P='http://schemas.openxmlformats.org/package/2006/relationships'
ET.register_namespace('',S)
ET.register_namespace('r',R)

def col(n):
    s='';n+=1
    while n:
        n,k=divmod(n-1,26);s=chr(65+k)+s
    return s

def main():
    expected=json.loads((WORK/'workbook-expected.json').read_text())
    with zipfile.ZipFile(TARGET) as z: original={n:z.read(n) for n in z.namelist()}
    patched=dict(original)
    added=0
    changed=[]
    for number,(name,info) in enumerate(expected.items(),1):
        sheetname=f'xl/worksheets/sheet{number}.xml'
        relname=f'xl/worksheets/_rels/sheet{number}.xml.rels'
        root=ET.fromstring(original[sheetname])
        relroot=ET.fromstring(original[relname]) if relname in original else ET.Element('{'+P+'}Relationships')
        for old in root.findall('{'+S+'}hyperlinks'):root.remove(old)
        for rel in list(relroot):
            if rel.get('Type','').endswith('/hyperlink'):relroot.remove(rel)
        used={r.get('Id') for r in relroot}
        hyperlinks=ET.Element('{'+S+'}hyperlinks')
        for i,row in enumerate(info['rows'],8):
            for j,label in info['linkColumns'].items():
                url=row[int(j)]
                if not url:continue
                rid=f'catalogueLink{i}_{j}'
                assert rid not in used
                used.add(rid)
                ET.SubElement(hyperlinks,'{'+S+'}hyperlink',{'ref':col(int(j))+str(i),'{'+R+'}id':rid,'display':label})
                ET.SubElement(relroot,'{'+P+'}Relationship',{'Id':rid,'Type':R+'/hyperlink','Target':url,'TargetMode':'External'})
                added+=1
        # SpreadsheetML ordering places hyperlinks after validation and before
        # print options/page setup/drawings/tableParts.
        later={'printOptions','pageMargins','pageSetup','headerFooter','rowBreaks','colBreaks','customProperties','cellWatches','ignoredErrors','smartTags','drawing','legacyDrawing','legacyDrawingHF','picture','oleObjects','controls','webPublishItems','tableParts','extLst'}
        at=next((i for i,x in enumerate(root) if x.tag.rsplit('}',1)[-1] in later),len(root))
        root.insert(at,hyperlinks)
        patched[sheetname]=ET.tostring(root,encoding='utf-8',xml_declaration=True)
        patched[relname]=ET.tostring(relroot,encoding='utf-8',xml_declaration=True)
        # Independent semantic check: removing the new link collection must
        # produce exactly the original cell/style/layout tree.
        after=ET.fromstring(patched[sheetname]);after.remove(after.find('{'+S+'}hyperlinks'))
        before=ET.fromstring(original[sheetname])
        for old in before.findall('{'+S+'}hyperlinks'):before.remove(old)
        assert ET.tostring(before)==ET.tostring(after),(name,'non-link XML changed')
        changed.extend([sheetname,relname])
    for name in set(original)-set(changed):assert patched[name]==original[name]
    temp=TARGET.with_suffix('.links-pending.xlsx')
    with zipfile.ZipFile(temp,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for n,data in patched.items():z.writestr(n,data)
    temp.replace(TARGET)
    receipt={'status':'PASS_NATIVE_HYPERLINKS_ATTACHED','hyperlinks':added,'modified_parts':changed,'other_workbook_parts_byte_identical':True,'cell_values_formulas_styles_layout_unchanged':True,'reason':'Documented HYPERLINK formula exists but evaluator returns not implemented; no documented native hyperlink setter was found.'}
    (WORK/'native-hyperlink-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(receipt))

if __name__=='__main__':main()
