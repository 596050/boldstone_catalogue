"""Add the native hyperlink feature not exposed by the installed artifact API."""
from collections import defaultdict
from pathlib import Path
import hashlib
import json
import posixpath
import zipfile
from lxml import etree as ET

HERE = Path(__file__).resolve().parent
S = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
R = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
P = 'http://schemas.openxmlformats.org/package/2006/relationships'
qn = lambda uri, tag: '{' + uri + '}' + tag
receipt = json.loads((HERE / 'export-receipt.json').read_text())
plan_path = HERE / 'native-hyperlinks.json'
assert hashlib.sha256(plan_path.read_bytes()).hexdigest() == receipt['native_hyperlink_plan_sha256']
plan = json.loads(plan_path.read_text())
assert len({(x['sheet'], x['cell']) for x in plan}) == len(plan)
target = Path(receipt['output'])
assert hashlib.sha256(target.read_bytes()).hexdigest() == receipt['output_sha256']
by_sheet = defaultdict(list)
for link in plan:
    assert link['target'].startswith(('https://www.dropbox.com/', '#'))
    by_sheet[link['sheet']].append(link)
with zipfile.ZipFile(target) as archive:
    originals = {x.filename: (x, archive.read(x.filename)) for x in archive.infolist()}
workbook = ET.fromstring(originals['xl/workbook.xml'][1])
rels = {x.get('Id'): x.get('Target') for x in ET.fromstring(originals['xl/_rels/workbook.xml.rels'][1])}
replacements = {}
late = {'printOptions', 'pageMargins', 'pageSetup', 'headerFooter', 'rowBreaks', 'colBreaks', 'customProperties',
        'cellWatches', 'ignoredErrors', 'smartTags', 'drawing', 'legacyDrawing', 'legacyDrawingHF', 'picture',
        'oleObjects', 'controls', 'webPublishItems', 'tableParts', 'extLst'}
for sheet in workbook.find(qn(S, 'sheets')):
    links = by_sheet.get(sheet.get('name'), [])
    if not links: continue
    path = rels[sheet.get(qn(R, 'id'))]
    path = path.lstrip('/') if path.startswith('/') else posixpath.normpath('xl/' + path)
    root = ET.fromstring(originals[path][1])
    relation_path = posixpath.join(posixpath.dirname(path), '_rels', posixpath.basename(path) + '.rels')
    relation_root = ET.fromstring(originals[relation_path][1]) if relation_path in originals else ET.Element(qn(P, 'Relationships'), nsmap={None: P})
    identifiers = {x.get('Id') for x in relation_root}
    container = root.find(qn(S, 'hyperlinks'))
    if container is None:
        container = ET.Element(qn(S, 'hyperlinks'))
        index = next((i for i, child in enumerate(root) if ET.QName(child).localname in late), len(root))
        root.insert(index, container)
    refs = {x.get('ref') for x in container}
    for index, link in enumerate(links, 1):
        assert link['cell'] not in refs
        element = ET.SubElement(container, qn(S, 'hyperlink'), ref=link['cell'], display=link['label'])
        if link['target'].startswith('#'):
            element.set('location', link['target'][1:])
        else:
            identifier = 'rIdCatalogueLink' + str(index)
            assert identifier not in identifiers
            element.set(qn(R, 'id'), identifier)
            ET.SubElement(relation_root, qn(P, 'Relationship'), Id=identifier, Type=R + '/hyperlink',
                          Target=link['target'], TargetMode='External')
            identifiers.add(identifier)
    replacements[path] = ET.tostring(root, encoding='UTF-8', xml_declaration=True)
    if len(relation_root): replacements[relation_path] = ET.tostring(relation_root, encoding='UTF-8', xml_declaration=True)
temp = target.with_suffix('.native-links.tmp')
with zipfile.ZipFile(temp, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
    for path, (info, content) in originals.items(): archive.writestr(info, replacements.pop(path, content))
    for path, content in replacements.items(): archive.writestr(path, content)
temp.replace(target)
receipt['output_sha256'] = hashlib.sha256(target.read_bytes()).hexdigest()
receipt['native_hyperlinks_written'] = len(plan)
receipt['status'] = 'EXPORTED_WITH_NATIVE_HYPERLINKS;INDEPENDENT_CHECK_REQUIRED'
(HERE / 'export-receipt.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'native_hyperlinks': len(plan), 'worksheets': len(by_sheet), 'output_sha256': receipt['output_sha256']}))
