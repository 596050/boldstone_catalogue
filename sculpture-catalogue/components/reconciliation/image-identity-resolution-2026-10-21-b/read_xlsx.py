"""Read-only native OOXML inspection for independent catalogue verification."""
from zipfile import ZipFile
from xml.etree import ElementTree as E
import posixpath

NS = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main',
      'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}

def read_xlsx(path):
    with ZipFile(path) as z:
        strings = [''.join(x.itertext()) for x in E.fromstring(z.read('xl/sharedStrings.xml'))] if 'xl/sharedStrings.xml' in z.namelist() else []
        rels = {r.attrib['Id']: r.attrib['Target'] for r in E.fromstring(z.read('xl/_rels/workbook.xml.rels'))}
        sheets, links = {}, {}
        for sheet in E.fromstring(z.read('xl/workbook.xml')).find('s:sheets', NS):
            name = sheet.attrib['name']
            target = rels[sheet.attrib['{' + NS['r'] + '}id']]
            part = target.lstrip('/') if target.startswith('/') else posixpath.normpath('xl/' + target)
            root = E.fromstring(z.read(part))
            cells = {}
            for cell in root.findall('.//s:sheetData/s:row/s:c', NS):
                value = cell.find('s:v', NS)
                value = value.text if value is not None else None
                kind = cell.attrib.get('t')
                if kind == 's':
                    value = strings[int(value)]
                elif kind == 'inlineStr':
                    value = ''.join(cell.find('s:is', NS).itertext())
                formula = cell.find('s:f', NS)
                cells[cell.attrib['r']] = {'value': value, 'formula': formula.text if formula is not None else None,
                                           'style': cell.attrib.get('s'), 'type': kind}
            sheets[name] = cells
            relpart = posixpath.dirname(part) + '/_rels/' + posixpath.basename(part) + '.rels'
            sheetrels = {r.attrib['Id']: r.attrib['Target'] for r in E.fromstring(z.read(relpart))} if relpart in z.namelist() else {}
            for link in root.findall('s:hyperlinks/s:hyperlink', NS):
                links[(name, link.attrib['ref'])] = sheetrels.get(link.attrib.get('{' + NS['r'] + '}id'), link.attrib.get('location'))
        return sheets, links
