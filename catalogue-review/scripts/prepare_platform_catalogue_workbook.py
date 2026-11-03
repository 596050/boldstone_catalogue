"""Prepare exact cell changes and prefixed platform fields for the master workbook."""
from datetime import datetime
from pathlib import Path
import json
import re
import sys
import xml.etree.ElementTree as E
import zipfile

OUT = Path(sys.argv[1]).resolve()
read = lambda name: json.loads((OUT / name).read_text())
app = read('app-after.json')
products = {p['id']: p for p in app['products']}
fields = {p['id']: {f['key']: f for f in p['fields'] + p['listing_fields']} for p in app['products']}
records = read('matched-platform-records.json')
issues = read('consistency-issues.json')
slug = lambda text: re.sub(r'[^a-z0-9]+', '_', str(text).lower().replace('£', 'gbp').replace('$', 'usd')).strip('_')
NS = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
q = lambda name: '{' + NS['s'] + '}' + name
R = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'


def address(index):
    text = ''
    while index:
        index, digit = divmod(index - 1, 26)
        text = chr(65 + digit) + text
    return text


with zipfile.ZipFile(OUT / 'previous-catalogue.xlsx') as z:
    shared = [''.join(t.text or '' for t in s.iter(q('t'))) for s in E.fromstring(z.read('xl/sharedStrings.xml'))]
    rels = {r.get('Id'): 'xl/' + r.get('Target').lstrip('/').removeprefix('xl/') for r in E.fromstring(z.read('xl/_rels/workbook.xml.rels'))}
    paths = {s.get('name'): rels[s.get('{' + R + '}id')] for s in E.fromstring(z.read('xl/workbook.xml')).find('s:sheets', NS)}
    cells = {name: {c.get('r'): c for c in E.fromstring(z.read(path)).findall('s:sheetData/s:row/s:c', NS)} for name, path in paths.items()}
    def value(sheet, cell):
        c = cells[sheet].get(cell)
        if c is None:
            return None
        if c.find('s:f', NS) is not None:
            return '=' + c.find('s:f', NS).text
        if c.get('t') == 'inlineStr':
            return ''.join(t.text or '' for t in c.iter(q('t')))
        v = c.find('s:v', NS)
        text = v.text if v is not None else ''
        return shared[int(text)] if c.get('t') == 's' else text
    patches = []
    def put(sheet, cell, val):
        before = value(sheet, cell)
        if before != (str(val) if val is not None else ''):
            assert before is None or not before.startswith('='), (sheet, cell, 'Preserve existing formula')
            patches.append({'sheet': sheet, 'cell': cell, 'before': before, 'value': val})
    master_rows = {}
    for row in range(8, 189):
        pid = value('Wall Sculptures', f'AA{row}')
        assert pid in products and pid not in master_rows
        master_rows[pid] = row
        assert value('Website Copy', f'E{row}') == pid
        put('Wall Sculptures', f'AV{row}', fields[pid]['Retail name']['value'])
        put('Wall Sculptures', f'AD{row}', fields[pid]['Description']['value'])
        put('Website Copy', f'A{row}', fields[pid]['Retail name']['value'])
        put('Website Copy', f'B{row}', fields[pid]['Description']['value'])
    assert set(master_rows) == set(products)
    for row in range(5, 186):
        pid = value('Channel Details', f'A{row}')
        assert pid in products
        put('Channel Details', f'B{row}', fields[pid]['Retail name']['value'])
        put('Channel Details', f'J{row}', fields[pid]['Marketplace title']['value'])
    for cell in cells['Specification Sources']:
        if not re.fullmatch(r'C\d+', cell) or int(cell[1:]) < 8:
            continue
        row = int(cell[1:]); pid = value('Specification Sources', cell)
        key = value('Specification Sources', f'E{row}')
        if pid in fields and key in ('Retail name', 'Marketplace title', 'Description'):
            source = fields[pid][key]
            for column, k in [('F', 'value'), ('G', 'decision'), ('H', 'certainty'), ('L', 'evidence'), ('M', 'notes'), ('N', 'updated_at')]:
                val = source.get(k) or ''
                if k == 'updated_at' and val:
                    val = datetime.fromisoformat(val).isoformat(timespec='milliseconds').replace('+00:00', 'Z')
                put('Specification Sources', f'{column}{row}', val)
    for sheet in ('Wall Sculptures', 'Website Copy', 'Specification Sources'):
        put(sheet, 'A4', f'App snapshot: {app["checked_at"]} (UTC). Platform snapshot fields are observed 2 November 2026; targets are prepared, not live platform updates.')
    extra = {pid: {} for pid in products}
    platform_headers = []
    for platform in ('chairish', 'ebay'):
        subset = [r for r in records if r['platform'] == platform]
        raw_headers = list(subset[0]['source'])
        columns = [platform + '_observed_' + slug(k) for k in raw_headers]
        assert len(columns) == len(set(columns))
        target_keys = sorted({k for r in subset for k in r['targets']})
        target_columns = [platform + '_' + k for k in target_keys]
        metadata = [platform + '_snapshot_scope', platform + '_source_file', platform + '_source_date',
                    platform + '_sale_unit_scope', platform + '_update_state', platform + '_issue_count']
        platform_headers += metadata + columns + target_columns
        for pid in products:
            extra[pid][platform + '_snapshot_scope'] = 'Not included in supplied platform snapshot'
        for record in subset:
            for pid in record['catalogue_ids']:
                data = extra[pid]
                data.update({column: record['source'].get(key) for key, column in zip(raw_headers, columns)})
                for key in ['Chairish ID', 'Item ID', 'Category ID', 'Condition ID']:
                    column = platform + '_observed_' + slug(key)
                    if column in data and data[column] not in ('', None):
                        data[column] = str(data[column])
                data.update({platform + '_' + k: v for k, v in record['targets'].items()})
                data[platform + '_snapshot_scope'] = 'Matched by exact SKU' if len(record['catalogue_ids']) == 1 else 'Verified Echo I and II pair offer'
                data[platform + '_source_file'] = 'Chairish_Listings_Boldstone.xlsx' if platform == 'chairish' else 'Boldstone_eBay_listings_2026-11-02 (2).xlsx'
                data[platform + '_source_date'] = '2026-11-02'
                data[platform + '_sale_unit_scope'] = 'Individual component' if len(record['catalogue_ids']) == 1 else 'Shared two-component pair offer; price/postage apply to the pair'
                data[platform + '_update_state'] = 'Catalogue-aligned targets prepared; live listing not changed by this reconciliation'
                data[platform + '_issue_count'] = sum(i['platform'] == platform and i['native_id'] == record['native_id'] for i in issues)
    assert len(platform_headers) == len(set(platform_headers))
    # One editable reference rate, kept outside the independent review sheet.
    fx = read('reference-sources.json')['fx']
    new_cells = [
        {'cell': 'BB3', 'value': 'USD per GBP reference', 'kind': 'header'},
        {'cell': 'BB4', 'value': fx['usd_per_gbp'], 'kind': 'data', 'header': 'fx_reference'},
        {'cell': 'BC3', 'value': 'Reference date', 'kind': 'header'},
        {'cell': 'BC4', 'value': fx['date'], 'kind': 'data'},
        {'cell': 'BD3', 'value': 'Reference source', 'kind': 'header'},
        {'cell': 'BD4', 'value': fx['url'], 'kind': 'data'},
        {'cell': 'BE3', 'value': 'Currency basis', 'kind': 'header'},
        {'cell': 'BE4', 'value': 'ECB reference conversion; platform settlement and bank fees may differ.', 'kind': 'data'},
        {'cell': 'BF3', 'value': 'Centimetres per inch', 'kind': 'header'},
        {'cell': 'BF4', 'value': 2.54, 'kind': 'data'},
    ]
    # All platform fields are attached to the matching component's existing row.
    start_column = 54  # BB, immediately after existing BA; no columns moved.
    column_for = {header: address(start_column + n) for n, header in enumerate(platform_headers)}
    record_for = {(r['platform'], pid): r for r in records for pid in r['catalogue_ids']}
    for offset, header in enumerate(platform_headers):
        column = address(start_column + offset)
        new_cells.append({'cell': column + '7', 'value': header, 'kind': 'header'})
        for pid, row in master_rows.items():
            val = extra[pid].get(header)
            if val not in ('', None):
                cell = {'cell': column + str(row), 'value': val, 'kind': 'data', 'header': header}
                platform = header.split('_', 1)[0]
                record = record_for.get((platform, pid))
                key = header[len(platform) + 1:]
                ref = lambda suffix: column_for[platform + '_' + suffix] + str(row)
                if record:
                    ids = record['catalogue_ids']
                    if key in ('catalogue_price_gbp', 'catalogue_components_total_gbp'):
                        cell['formula'] = '=SUM(' + ','.join('H' + str(master_rows[i]) for i in ids) + ')'
                    elif key == 'manufacturing_cost_gbp':
                        cell['formula'] = '=SUM(' + ','.join('AM' + str(master_rows[i]) for i in ids) + ')'
                    elif key == 'usd_per_gbp_reference':
                        cell['formula'] = '=$BB$4'
                    elif key == 'catalogue_price_usd':
                        cell['formula'] = '=ROUND(' + ref('catalogue_price_gbp') + '*' + ref('usd_per_gbp_reference') + ',0)'
                    elif key == 'source_price_gbp_equivalent':
                        cell['formula'] = '=ROUND(' + ref('observed_price_usd') + '/' + ref('usd_per_gbp_reference') + ',2)'
                    elif key == 'delivery_charge_gbp_equivalent':
                        cell['formula'] = '=ROUND(' + ref('observed_delivery_charge_to_buyer_usd') + '/' + ref('usd_per_gbp_reference') + ',2)'
                    elif key in ('width_in', 'depth_in', 'height_in'):
                        cell['formula'] = '=ROUND(' + ref(key.replace('_in', '_cm')) + '/$BF$4,2)'
                new_cells.append(cell)
    # Item issues and all selected eBay photo URLs remain directly inspectable.
    review_headers = ['Platform', 'Listing ID', 'Catalogue IDs', 'Field', 'Observed value', 'Catalogue or reference value', 'Required action', 'Priority']
    review_rows = [[i['platform'], i['native_id'], ', '.join(i['catalogue_ids']), i['field'],
                    str(i['observed']) if i['observed'] is not None else '',
                    str(i['catalogue_or_reference']), i['action'], i['severity']] for i in issues]
    original = read('platform-inputs.json')['Boldstone_eBay_listings_2026-11-02 (2).xlsx']['sheets'][1]
    photo_header = original['rows'][0]
    photo_headers = {re.sub(r'\d', '', k): v['value'] for k, v in photo_header['cells'].items()}
    ids = {r['native_id']: r['catalogue_ids'] for r in records if r['platform'] == 'ebay'}
    photos = []
    for row in original['rows'][1:]:
        data = {photo_headers[re.sub(r'\d', '', k)]: v['value'] for k, v in row['cells'].items()}
        native_id = str(data['Item ID'])
        if native_id in ids:
            photos.append([native_id, ', '.join(ids[native_id]), data['Title'], data['Photo #'],
                           data['Image URL (1600px)'], data['eBay image ID'], data['Also used on another listing?']])
    new_sheets = [
        {'name': 'Platform Review', 'title': 'Platform consistency review',
         'note': 'Observed platform values are from the supplied 2 November files. Targets use the current catalogue. Shipping requires actual packed measurements and destination quotes; no final charge is certified.',
         'headers': review_headers, 'rows': review_rows},
        {'name': 'eBay Photo Links', 'title': 'eBay wall-sculpture photographs',
         'note': 'URLs preserved from the supplied snapshot. Pair photographs remain linked to both Echo components; no image downloads or new product identities.',
         'headers': ['ebay_item_id', 'ebay_catalogue_ids', 'ebay_observed_title', 'ebay_photo_number', 'ebay_image_url', 'ebay_image_id', 'ebay_also_used_on_another_listing'],
         'rows': photos},
    ]
    # Source references and editable FX input are in the owning master inputs.
    sources = read('reference-sources.json')
    for pid, row in master_rows.items():
        for platform in ('chairish', 'ebay'):
            if extra[pid][platform + '_snapshot_scope'].startswith('Not included'):
                continue
            extra[pid][platform + '_usd_per_gbp_reference'] = sources['fx']['usd_per_gbp']
    payload = {'products': len(products), 'sheets': list(paths), 'patches': patches,
               'new_sheets': new_sheets, 'added_master_columns': platform_headers,
               'new_master_cells': new_cells, 'first_added_column': start_column,
               'last_added_column': start_column + len(platform_headers) - 1,
               'scope': 'Finish title clarification, observed prefixed Chairish/eBay fields and catalogue-aligned targets, dimension/currency/postage reconciliation. No native platform updates.'}
    (OUT / 'patches.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'master_patches': len(patches), 'added_platform_columns': len(platform_headers),
                      'added_platform_cells': len(new_cells), 'issues': len(review_rows), 'ebay_photo_links': len(photos)}))
