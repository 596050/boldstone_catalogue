"""Supplement artifact-authored XLSX with native long hyperlinks and two-axis panes."""
from pathlib import Path
import json
import sys
import zipfile
import xml.etree.ElementTree as ET

path = Path(sys.argv[1])
root = path.parent
links = json.loads((root / 'hyperlinks.json').read_text())
manifest = json.loads((root / 'expected-workbook.json').read_text())
NS = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
REL = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
PKG = 'http://schemas.openxmlformats.org/package/2006/relationships'
ET.register_namespace('', NS)
ET.register_namespace('r', REL)
with zipfile.ZipFile(path) as z:
    entries = {name:z.read(name) for name in z.namelist()}
for index, sheet in enumerate(manifest['sheets'], 1):
    name = f'xl/worksheets/sheet{index}.xml'
    relname = f'xl/worksheets/_rels/sheet{index}.xml.rels'
    xml = ET.fromstring(entries[name])
    relationships = ET.fromstring(entries[relname]) if relname in entries else ET.Element(f'{{{PKG}}}Relationships')
    used = {node.attrib['Id'] for node in relationships}
    hyperlink_node = ET.Element(f'{{{NS}}}hyperlinks')
    serial = 0
    for link in [l for l in links if l['sheet'] == sheet['name']]:
        attrs = {'ref':link['cell'], 'display':link['label']}
        if link['internal']:
            attrs['location'] = link['url']
        else:
            while True:
                serial += 1
                rid = f'rIdCatalogueLink{serial}'
                if rid not in used:
                    break
            used.add(rid)
            ET.SubElement(relationships, f'{{{PKG}}}Relationship', {'Id':rid, 'Type':REL+'/hyperlink',
                          'Target':link['url'], 'TargetMode':'External'})
            attrs[f'{{{REL}}}id'] = rid
        ET.SubElement(hyperlink_node, f'{{{NS}}}hyperlink', attrs)
    if len(hyperlink_node):
        # ECMA-376 worksheet order: hyperlinks after conditionalFormatting/dataValidations,
        # before printOptions/pageMargins/pageSetup and drawing/tableParts.
        following = {'printOptions','pageMargins','pageSetup','headerFooter','rowBreaks','colBreaks',
                     'customProperties','cellWatches','ignoredErrors','smartTags','drawing','legacyDrawing',
                     'legacyDrawingHF','picture','oleObjects','controls','webPublishItems','tableParts','extLst'}
        insertion = next((i for i,c in enumerate(xml) if c.tag.split('}')[-1] in following), len(xml))
        xml.insert(insertion, hyperlink_node)
    view = xml.find(f'{{{NS}}}sheetViews/{{{NS}}}sheetView')
    assert view is not None
    for child in list(view):
        if child.tag.split('}')[-1] in ('pane','selection'):
            view.remove(child)
    c = sheet['freeze_columns']; r = sheet['freeze_rows']
    first = chr(ord('A') + c) + str(r + 1)
    view.insert(0, ET.Element(f'{{{NS}}}pane', {'xSplit':str(c), 'ySplit':str(r), 'topLeftCell':first,
                  'activePane':'bottomRight', 'state':'frozen'}))
    view.insert(1, ET.Element(f'{{{NS}}}selection', {'pane':'bottomRight', 'activeCell':first, 'sqref':first}))
    entries[name] = ET.tostring(xml, encoding='utf-8', xml_declaration=True)
    if len(relationships):
        entries[relname] = ET.tostring(relationships, encoding='utf-8', xml_declaration=True)
temporary = path.with_suffix('.tmp.xlsx')
with zipfile.ZipFile(temporary, 'w', compression=zipfile.ZIP_DEFLATED) as z:
    for name, content in entries.items():
        z.writestr(name, content)
temporary.replace(path)
print(json.dumps({'native_hyperlinks_added':len(links), 'freeze_panes':'D8 on each sheet'}))
