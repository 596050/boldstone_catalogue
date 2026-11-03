"""Retain original XLSX features and transplant only artifact-authored changes."""
import copy
import hashlib
import json
from pathlib import Path
import posixpath
import re
import sys
import xml.etree.ElementTree as E
import zipfile

OUT = Path(sys.argv[1]).resolve()
plan = json.loads((OUT / 'patches.json').read_text())
U = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
R = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
PKG = 'http://schemas.openxmlformats.org/package/2006/relationships'
CT = 'http://schemas.openxmlformats.org/package/2006/content-types'
NS = {'s': U}; q = lambda name: '{' + U + '}' + name
E.register_namespace('', U); E.register_namespace('r', R)


def address(index):
    result = ''
    while index:
        index, digit = divmod(index - 1, 26)
        result = chr(65 + digit) + result
    return result


def col_index(cell):
    result = 0
    for char in re.sub(r'\d', '', cell):
        result = result * 26 + ord(char) - 64
    return result


def shared(z):
    return [''.join(t.text or '' for t in s.iter(q('t'))) for s in E.fromstring(z.read('xl/sharedStrings.xml'))] if 'xl/sharedStrings.xml' in z.namelist() else []


def value(cell, strings):
    if cell is None:
        return None
    if cell.get('t') == 'inlineStr':
        return ''.join(t.text or '' for t in cell.iter(q('t')))
    v = cell.find('s:v', NS)
    text = v.text if v is not None else ''
    if cell.get('t') == 's':
        return strings[int(text)]
    if cell.get('t') == 'e':
        raise ValueError('Formula error: ' + str(text))
    if text and cell.get('t', 'n') == 'n':
        return float(text)
    return text


def literalize(cell, strings):
    if cell.get('t') == 's':
        text = value(cell, strings)
        for child in list(cell):
            cell.remove(child)
        cell.set('t', 'inlineStr')
        t = E.SubElement(E.SubElement(cell, q('is')), q('t'))
        t.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
        t.text = text


def sheet_paths(z):
    rels = {r.get('Id'): posixpath.normpath('xl/' + r.get('Target').lstrip('/').removeprefix('xl/')) for r in E.fromstring(z.read('xl/_rels/workbook.xml.rels'))}
    return {s.get('name'): rels[s.get('{' + R + '}id')] for s in E.fromstring(z.read('xl/workbook.xml')).find('s:sheets', NS)}


with zipfile.ZipFile(OUT / 'previous-catalogue.xlsx') as original, zipfile.ZipFile(OUT / 'authored.xlsx') as authored:
    old = {n: original.read(n) for n in original.namelist()}
    parts = dict(old); op = sheet_paths(original); ap = sheet_paths(authored)
    ss = shared(authored); oldss = shared(original)
    styles = E.fromstring(old['xl/styles.xml'])
    master_before = E.fromstring(old[op['Wall Sculptures']])
    basecells = {c.get('r'): c for c in master_before.findall('s:sheetData/s:row/s:c', NS)}
    header_style = basecells['A7'].get('s', '0')
    text_style = basecells['C8'].get('s', '0')
    xfs = styles.find('s:cellXfs', NS)
    formats = styles.find('s:numFmts', NS)
    if formats is None:
        formats = E.Element(q('numFmts'), {'count': '0'}); styles.insert(0, formats)
    def numeric_style(code):
        existing = next((f.get('numFmtId') for f in formats if f.get('formatCode') == code), None)
        if existing is None:
            existing = str(max([163] + [int(f.get('numFmtId')) for f in formats]) + 1)
            E.SubElement(formats, q('numFmt'), {'numFmtId': existing, 'formatCode': code})
            formats.set('count', str(len(formats)))
        xf = copy.deepcopy(xfs[int(basecells['A8'].get('s', '0'))])
        xf.set('numFmtId', existing); xf.set('applyNumberFormat', '1')
        xfs.append(xf); xfs.set('count', str(len(xfs)))
        return str(len(xfs) - 1)
    decimal_style = numeric_style('0.00')
    integer_style = numeric_style('0')
    rate_style = numeric_style('0.000000')
    percentage_style = numeric_style('0.00%')
    date_style = numeric_style('yyyy-mm-dd hh:mm')
    def style_for(cell, header='', is_header=False):
        if is_header:
            return header_style
        if cell.get('t', 'n') != 'n':
            return text_style
        if header.endswith('listing_started_uk_time'):
            return date_style
        if 'discount' in header or header.endswith('_general_ad_rate'):
            return percentage_style
        if 'usd_per_gbp_reference' in header or header == 'fx_reference':
            return rate_style
        if any(word in header for word in ['count', 'photos', 'quantity', 'photo_number']):
            return integer_style
        return decimal_style
    changed_parts = {'xl/styles.xml'}
    patched = 0; added = 0; preserved_cells = 0; preserved_links = 0
    for name, path in op.items():
        patches = {p['cell']: p for p in plan['patches'] if p['sheet'] == name}
        additions = {p['cell']: p for p in plan['new_master_cells']} if name == 'Wall Sculptures' else {}
        a = E.fromstring(old[path]); b = copy.deepcopy(a)
        if patches or additions:
            source = E.fromstring(authored.read(ap[name]))
            source_cells = {c.get('r'): c for c in source.findall('s:sheetData/s:row/s:c', NS)}
            rows = {int(r.get('r')): r for r in b.findall('s:sheetData/s:row', NS)}
            for cell_address, change in {**patches, **additions}.items():
                new = copy.deepcopy(source_cells[cell_address])
                actual = value(new, ss); expected = change['value']
                assert (isinstance(expected, (int, float)) and abs(actual - expected) < .011) or actual == expected, (name, cell_address, actual, expected)
                literalize(new, ss)
                row = rows[int(re.search(r'\d+', cell_address).group())]
                previous = next((c for c in row if c.get('r') == cell_address), None)
                if cell_address in patches:
                    assert previous is not None
                    assert str(value(previous, oldss)) == str(change['before'])
                    new.set('s', previous.get('s', '0')); row.remove(previous); patched += 1
                else:
                    assert previous is None, ('Unexpected existing cell', cell_address)
                    new.set('s', style_for(new, change.get('header', ''), change.get('kind') == 'header'))
                    added += 1
                row.append(new)
                row[:] = sorted(row, key=lambda c: col_index(c.get('r')))
            if name == 'Wall Sculptures':
                last = address(plan['last_added_column'])
                dimension = b.find('s:dimension', NS)
                if dimension is None:
                    dimension = E.Element(q('dimension'))
                    b.insert(1 if b.find('s:sheetPr', NS) is not None else 0, dimension)
                dimension.set('ref', 'A1:' + last + '188')
                rows[7].set('ht', '75'); rows[7].set('customHeight', '1')
                for n in [3, 4]:
                    rows[n].set('ht', '58'); rows[n].set('customHeight', '1')
                cols = b.find('s:cols', NS)
                E.SubElement(cols, q('col'), {'min': str(plan['first_added_column']), 'max': str(plan['last_added_column']), 'width': '32', 'customWidth': '1'})
            parts[path] = E.tostring(b, encoding='utf-8', xml_declaration=True)
            changed_parts.add(path)
        before_cells = {c.get('r'): c for c in a.findall('s:sheetData/s:row/s:c', NS)}
        after_cells = {c.get('r'): c for c in b.findall('s:sheetData/s:row/s:c', NS)}
        assert set(after_cells) - set(before_cells) == set(additions)
        for key, cell in before_cells.items():
            if key not in patches:
                assert E.tostring(cell) == E.tostring(after_cells[key]), (name, key)
                preserved_cells += 1
        for tag in ['hyperlinks', 'sheetViews', 'mergeCells', 'tableParts', 'conditionalFormatting', 'dataValidations']:
            assert [E.tostring(e) for e in a.findall('s:' + tag, NS)] == [E.tostring(e) for e in b.findall('s:' + tag, NS)], (name, tag)
        preserved_links += len(a.findall('s:hyperlinks/s:hyperlink', NS))
    assert patched == len(plan['patches']) and added == len(plan['new_master_cells'])
    # Extend the existing native master table rather than flattening it.
    rel_path = posixpath.dirname(op['Wall Sculptures']) + '/_rels/' + posixpath.basename(op['Wall Sculptures']) + '.rels'
    relations = {e.get('Id'): e.get('Target') for e in E.fromstring(old[rel_path])}
    table_id = master_before.find('s:tableParts/s:tablePart', NS).get('{' + R + '}id')
    table_target = relations[table_id].lstrip('/')
    table_path = table_target if table_target.startswith('xl/') else posixpath.normpath(posixpath.dirname(op['Wall Sculptures']) + '/' + table_target)
    table = E.fromstring(old[table_path]); columns = table.find('s:tableColumns', NS)
    new_master = E.fromstring(parts[op['Wall Sculptures']])
    headers = {col_index(c.get('r')): value(c, oldss) for c in new_master.findall('s:sheetData/s:row[@r="7"]/s:c', NS)}
    for index in range(len(columns) + 1, plan['last_added_column'] + 1):
        E.SubElement(columns, q('tableColumn'), {'id': str(index), 'name': headers[index]})
    columns.set('count', str(len(columns)))
    table.set('ref', 'A7:' + address(plan['last_added_column']) + '188')
    auto = table.find('s:autoFilter', NS)
    if auto is not None:
        auto.set('ref', table.get('ref'))
    parts[table_path] = E.tostring(table, encoding='utf-8', xml_declaration=True); changed_parts.add(table_path)
    wb = E.fromstring(parts['xl/workbook.xml']); sheets = wb.find('s:sheets', NS)
    rels = E.fromstring(parts['xl/_rels/workbook.xml.rels']); ct = E.fromstring(parts['[Content_Types].xml'])
    # Only new conditional formatting uses these appended differential styles.
    authored_styles = E.fromstring(authored.read('xl/styles.xml'))
    dxfs = styles.find('s:dxfs', NS)
    if dxfs is None:
        dxfs = E.SubElement(styles, q('dxfs'), {'count': '0'})
    dxf_map = {}
    authored_dxfs = authored_styles.find('s:dxfs', NS)
    for i, dxf in enumerate(list(authored_dxfs) if authored_dxfs is not None else []):
        dxf_map[str(i)] = str(len(dxfs)); dxfs.append(copy.deepcopy(dxf))
    dxfs.set('count', str(len(dxfs)))
    for index, data in enumerate(plan['new_sheets'], len(op) + 1):
        sheet = E.fromstring(authored.read(ap[data['name']]))
        assert sheet.find('s:drawing', NS) is None and sheet.find('s:tableParts', NS) is None
        for cell in sheet.findall('s:sheetData/s:row/s:c', NS):
            value(cell, ss); literalize(cell, ss)
            row = int(re.search(r'\d+', cell.get('r')).group())
            column_index = col_index(cell.get('r'))
            header = data['headers'][column_index - 1] if row >= 4 and column_index <= len(data['headers']) else ''
            cell.set('s', style_for(cell, header, row in (1, 4)))
        for rule in sheet.findall('s:conditionalFormatting/s:cfRule', NS):
            if rule.get('dxfId') is not None:
                rule.set('dxfId', dxf_map[rule.get('dxfId')])
        path = f'xl/worksheets/sheet{index}.xml'; assert path not in parts
        parts[path] = E.tostring(sheet, encoding='utf-8', xml_declaration=True)
        rid = f'rIdPlatformReconciliation{index}'
        E.SubElement(sheets, q('sheet'), {'name': data['name'], 'sheetId': str(index), '{' + R + '}id': rid})
        E.SubElement(rels, '{' + PKG + '}Relationship', {'Id': rid, 'Type': R + '/worksheet', 'Target': f'worksheets/sheet{index}.xml'})
        E.SubElement(ct, '{' + CT + '}Override', {'PartName': '/' + path, 'ContentType': 'application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml'})
    parts['xl/styles.xml'] = E.tostring(styles, encoding='utf-8', xml_declaration=True)
    for name, root, namespace in [('xl/workbook.xml', wb, U), ('xl/_rels/workbook.xml.rels', rels, PKG), ('[Content_Types].xml', ct, CT)]:
        E.register_namespace('', namespace); parts[name] = E.tostring(root, encoding='utf-8', xml_declaration=True); changed_parts.add(name)
    assert all(parts[name] == body for name, body in old.items() if name not in changed_parts)
    target = OUT / 'catalogue_wall_sculptures.xlsx'
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as z:
        for name, body in parts.items():
            z.writestr(name, body)
    with zipfile.ZipFile(target) as z:
        assert z.testzip() is None
        assert len(sheet_paths(z)) == len(op) + len(plan['new_sheets'])
    receipt = {'status': 'PASS', 'products': 181, 'cells_updated': patched, 'platform_cells_added': added,
               'platform_columns_added': len(plan['added_master_columns']), 'new_sheets': len(plan['new_sheets']),
               'original_cells_preserved': preserved_cells, 'hyperlinks_preserved': preserved_links,
               'unrelated_parts_preserved': True, 'existing_native_table_extended': True,
               'sha256': hashlib.sha256(target.read_bytes()).hexdigest()}
    (OUT / 'verification.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt))
