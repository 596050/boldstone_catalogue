from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict, Counter
from decimal import Decimal, InvalidOperation
import csv
import io
import hashlib
import json
import re
import zipfile
import xml.etree.ElementTree as ET

W = Path(__file__).resolve().parent
TASK = W.parent
ROOT = W.parents[3]
MASTER = TASK / 'inputs/master-register.json'
MASTER_HASH = '30ff291d6b6fe0aad3a2bc39e121de4ef838c09afceb5f7ab11c78ea7fa71e2c'
assert hashlib.sha256(MASTER.read_bytes()).hexdigest() == MASTER_HASH
M = json.loads(MASTER.read_text())
TABLE_PATH = ROOT / 'evidence/catalogue_source_tables_2026-10-15.json'
TABLES = json.loads(TABLE_PATH.read_text())
NOW = datetime.now(timezone.utc).isoformat()
PRIMARY = Path('/Users/tprice/Downloads/products_export_1 (1).csv')
ARCHIVE = Path('/Users/tprice/Downloads/products_export_1.csv')
XLSX = Path('/Users/tprice/Downloads/Shopify Boldstone Website Exported 30.08.2024.xlsx')


def write(name, value):
    (W / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def db_hash(data):
    return sha(b''.join(hashlib.sha256(data[i:i + 4194304]).digest()
                        for i in range(0, len(data), 4194304)))


def read_csv(path):
    reader = csv.DictReader(io.StringIO(path.read_text(encoding='utf-8-sig'), newline=''))
    headers = reader.fieldnames
    rows = []
    previous_line = reader.line_num
    for i, row in enumerate(reader, 2):
        rows.append({'source_logical_row_including_header': i,
                     'physical_line_start': previous_line + 1,
                     'physical_line_end': reader.line_num, 'raw': row})
        previous_line = reader.line_num
    return headers, rows


def read_xlsx(path):
    ns = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
    z = zipfile.ZipFile(path)
    shared = []
    if 'xl/sharedStrings.xml' in z.namelist():
        for si in ET.fromstring(z.read('xl/sharedStrings.xml')).findall('s:si', ns):
            shared.append(''.join(si.itertext()))
    matrix = []
    for row in ET.fromstring(z.read('xl/worksheets/sheet1.xml')).findall('.//s:sheetData/s:row', ns):
        values = {}
        for cell in row:
            raw = cell.find('s:v', ns)
            value = raw.text if raw is not None else ''
            kind = cell.get('t')
            if kind == 's':
                value = shared[int(value)] if value else ''
            elif kind == 'inlineStr':
                value = ''.join(cell.find('s:is', ns).itertext())
            elif kind == 'b':
                value = 'true' if value == '1' else 'false'
            values[re.sub(r'\d+$', '', cell.get('r'))] = value
        matrix.append((int(row.get('r')), values))
    headers = matrix[0][1]
    rows = [{'source_logical_row_including_header': n,
             'raw': {name: cells.get(col, '') for col, name in headers.items()}}
            for n, cells in matrix[1:]]
    meta = {'sheet': 'products_export_1',
            'core_document_properties_present': 'docProps/core.xml' in z.namelist(),
            'zip_entry_timestamps': sorted({str(i.date_time) for i in z.infolist()}),
            'zip_timestamp_timezone': 'NOT_ENCODED'}
    return list(headers.values()), rows, meta


def receipt(path, source_id, role, more=None):
    data = path.read_bytes()
    st = path.stat()
    return {'source_id': source_id, 'path': str(path), 'role': role,
            'bytes': len(data), 'sha256': sha(data), 'dropbox_content_hash': db_hash(data),
            'filesystem_modified_utc': datetime.fromtimestamp(st.st_mtime, timezone.utc).isoformat(),
            'filesystem_birth_utc': datetime.fromtimestamp(st.st_birthtime, timezone.utc).isoformat() if hasattr(st, 'st_birthtime') else None,
            'filesystem_dates_are_not_export_creation_dates': True,
            **(more or {})}


HEADERS, ROWS = read_csv(PRIMARY)
AH, AROWS = read_csv(ARCHIVE)
XH, XROWS, XMETA = read_xlsx(XLSX)
assert HEADERS == AH == XH and len(ROWS) == len(AROWS) == len(XROWS)

NUMERIC_FIELDS = {'Variant Grams', 'Variant Price', 'Variant Compare At Price',
                  'Image Position', 'Cost per item'} | {
    k for k in HEADERS if k.startswith(('Price / ', 'Compare At Price / '))}


def comparable(field, value):
    if field in ['Vendor', 'Image Alt Text']:
        return value.strip()
    if field in ['Google Shopping / Custom Product',
                 'Google: Custom Product (product.metafields.mm-google-shopping.custom_product)']:
        return value.casefold()
    if field in NUMERIC_FIELDS and value != '':
        try:
            return str(Decimal(value).normalize())
        except InvalidOperation:
            pass
    return value.replace('\r\n', '\n').replace('\r', '\n')


DIFFS = []
for source, others in [('CSV_ARCHIVE', AROWS), ('XLSX_2024_ARCHIVE', XROWS)]:
    for a, b in zip(ROWS, others):
        for k in HEADERS:
            if a['raw'][k] != b['raw'][k]:
                DIFFS.append({'source_id': source,
                              'logical_row': a['source_logical_row_including_header'],
                              'field': k, 'primary_raw': a['raw'][k], 'comparison_raw': b['raw'][k],
                              'equivalent_after_explicit_normalization': comparable(k, a['raw'][k]) == comparable(k, b['raw'][k])})

SOURCE_DATES = {
    'encoded_export_creation_datetime': None,
    'encoded_product_created_updated_dates': None,
    'native_csv_export_date_state': 'NOT_ENCODED',
    'archive_filename_date': '2024-08-30',
    'archive_filename_date_source': str(XLSX),
    'dated_archive_is_not_current_admin_confirmation': True,
    'later_copy_modified_date_is_not_a_new_export_date': True,
    'snapshot_description': 'Historical product dataset, corroborated by an archive named 30.08.2024. The selected CSV copy matches the historical S09 Dropbox content hash observed 15 October 2026.',
}
RECEIPTS = [
    receipt(PRIMARY, 'SH_NATIVE_CSV_S09', 'PRIMARY_NATIVE_SNAPSHOT',
            {'data_rows': len(ROWS), 'columns': len(HEADERS),
             'matches_prior_S09_dropbox_content_hash': db_hash(PRIMARY.read_bytes()) == '5a7bae871063bb318e1c342dd3a2bcdd76bf76307de58eff26180817df08b1a1'}),
    receipt(ARCHIVE, 'CSV_ARCHIVE', 'SAME_INVENTORY_VENDOR_WHITESPACE_DIFFERENCES',
            {'data_rows': len(AROWS), 'columns': len(AH)}),
    receipt(XLSX, 'XLSX_2024_ARCHIVE', 'DATED_NATIVE_EXPORT_WORKBOOK_REPRESENTATION',
            {'data_rows': len(XROWS), 'columns': len(XH), **XMETA}),
    receipt(TABLE_PATH, 'PRESERVED_SOURCE_TABLES', 'DERIVED_WALL_SUBSETS_AND_SOURCE_REGISTER'),
    receipt(MASTER, 'FROZEN_MASTER', 'READ_ONLY_184_OPTION_CONTEXT',
            {'expected_sha256': MASTER_HASH, 'options': len(M['options'])}),
]

WALL_PRODUCTS = {x['Handle']: x for x in TABLES['SH Wall Products']}
OFFERS = defaultdict(list)
for edge in M['source_offer_edges']:
    src = edge['source_offer']
    if src.get('sh_handle'):
        OFFERS[src['sh_handle']].append({
            'offer_ref': edge['offer_ref'],
            'source_sale_unit_state': src.get('sale_unit_state'),
            'source_native_parts': src.get('native_parts'),
            'source_proposed_bom_pieces': src.get('proposed_bom_pieces'),
            'basis': 'Frozen master existing source-offer record. This is prior reconciliation evidence, not a fresh sale-unit or platform-account confirmation.',
        })

VARIANT_SIGNAL_FIELDS = ['Option1 Value', 'Option2 Value', 'Option3 Value', 'Variant SKU',
                        'Variant Grams', 'Variant Inventory Tracker', 'Variant Inventory Policy',
                        'Variant Fulfillment Service', 'Variant Price', 'Variant Compare At Price',
                        'Variant Requires Shipping', 'Variant Taxable', 'Variant Barcode',
                        'Variant Weight Unit', 'Variant Tax Code', 'Cost per item']
PRODUCTS = {}
VARIANTS = []
MEDIA = []
ROW_RECORDS = []
LAST_HANDLE = None
HEADER_COLLISIONS = []
for item in ROWS:
    r = item['raw']
    n = item['source_logical_row_including_header']
    handle = r['Handle'] or LAST_HANDLE
    assert handle is not None
    LAST_HANDLE = handle
    title = r['Title']
    has_variant = any(r.get(k, '') != '' for k in VARIANT_SIGNAL_FIELDS)
    kind = ('PRODUCT_HEADER_AND_VARIANT' if title and has_variant else
            'PRODUCT_HEADER_WITHOUT_VARIANT' if title else
            'VARIANT_CONTINUATION' if has_variant else
            'MEDIA_ONLY_CONTINUATION' if r.get('Image Src') or r.get('Variant Image') else
            'UNCLASSIFIED_CONTINUATION')
    locator = {'source_id': 'SH_NATIVE_CSV_S09', 'path': str(PRIMARY),
               'logical_row_including_header': n,
               'physical_line_start': item['physical_line_start'],
               'physical_line_end': item['physical_line_end']}
    if title:
        if handle in PRODUCTS:
            HEADER_COLLISIONS.append({'handle': handle, 'logical_rows': [PRODUCTS[handle]['source_header_row']['logical_row_including_header'], n]})
        else:
            old = WALL_PRODUCTS.get(handle, {})
            PRODUCTS[handle] = {
                'product_key': 'SH_NATIVE_CSV_S09:' + handle,
                'handle_raw': r['Handle'], 'handle': handle,
                'numeric_product_id': None, 'product_id_state': 'NOT_EXPORTED_IN_THIS_SCHEMA',
                'title': title, 'body_html': r['Body (HTML)'],
                'vendor_raw': r['Vendor'], 'vendor_normalized': r['Vendor'].strip(),
                'product_category': r['Product Category'], 'type_raw': r['Type'],
                'tags_raw': r['Tags'], 'published_raw': r['Published'],
                'status_raw': r['Status'], 'status_scope': 'HISTORICAL_SOURCE_SNAPSHOT_ONLY',
                'source_header_row': locator,
                'source_rows': [], 'variant_keys': [], 'media_row_locators': [],
                'product_url': None, 'product_url_state': 'STORE_DOMAIN_NOT_EVIDENCED',
                'relative_product_path': '/products/' + handle,
                'source_dates': SOURCE_DATES,
                'in_preserved_wall_subset': handle in WALL_PRODUCTS,
                'preserved_wall_source_locator': {'sheet': 'SH Wall Products', 'row': old.get('_row'), 'source_csv_record': old.get('CSV record')} if old else None,
                'sale_unit_evidence': {
                    'preserved_catalogue_parts_raw': old.get('Catalogue | Parts'),
                    'preserved_catalogue_evidence_and_cautions': old.get('Catalogue | Matching evidence and cautions'),
                    'frozen_master_source_offer_refs': OFFERS[handle],
                    'body_html_retained_for_exact_sale_wording': True,
                    'group_source_values_not_divided_into_individual_values': True,
                    'no_new_sale_unit_confirmation': True,
                },
                'current_admin_or_live_public_presence_verified': False,
                'physical_stock_verified': False,
            }
    assert handle in PRODUCTS, ('Continuation before product header', n, handle)
    p = PRODUCTS[handle]
    p['source_rows'].append(n)
    if has_variant:
        options = []
        header = next(x['raw'] for x in ROWS if x['source_logical_row_including_header'] == p['source_header_row']['logical_row_including_header'])
        for pos in [1, 2, 3]:
            name = r.get(f'Option{pos} Name', '') or header.get(f'Option{pos} Name', '')
            value = r.get(f'Option{pos} Value', '')
            if name or value:
                options.append({'position': pos, 'name': name, 'value': value,
                                'name_inherited_from_product_header': not bool(r.get(f'Option{pos} Name', '')) and bool(name)})
        key = handle + ':ROW' + str(n)
        v = {
            'variant_key': key, 'product_key': p['product_key'], 'handle': handle,
            'numeric_product_id': None, 'numeric_variant_id': None,
            'id_state': 'NOT_EXPORTED_IN_THIS_SCHEMA',
            'sku_raw': r['Variant SKU'], 'sku_trimmed_candidate': r['Variant SKU'].strip(),
            'sku_normalization_is_not_identity_confirmation': True,
            'option_tuple': options,
            'price_raw': r['Variant Price'], 'compare_at_price_raw': r['Variant Compare At Price'],
            'currency': None, 'currency_state': 'STORE_CURRENCY_NOT_ENCODED_IN_EXPORT',
            'grams_raw': r['Variant Grams'], 'exported_weight_unit_raw': r['Variant Weight Unit'],
            'weight_scope': 'SOURCE_VARIANT_VALUE; NOT_VERIFIED_PHYSICAL_WEIGHT_OR_COMPONENT_ALLOCATION',
            'inventory_tracker_raw': r['Variant Inventory Tracker'],
            'inventory_policy_raw': r['Variant Inventory Policy'],
            'inventory_quantity': None, 'inventory_quantity_state': 'COLUMN_NOT_EXPORTED',
            'requires_shipping_raw': r['Variant Requires Shipping'],
            'taxable_raw': r['Variant Taxable'], 'barcode_raw': r['Variant Barcode'],
            'product_status_raw': p['status_raw'], 'published_raw': p['published_raw'],
            'status_inherited_from_header': not bool(r['Status']),
            'status_scope': 'HISTORICAL_SOURCE_SNAPSHOT_ONLY',
            'source_row': locator, 'source_row_role': kind,
            'source_dates': SOURCE_DATES,
            'variant_image_raw': r['Variant Image'],
            'product_url': None, 'variant_url': None,
            'current_live_quantity_or_draft_state_verified': False,
        }
        VARIANTS.append(v)
        p['variant_keys'].append(key)
    if r.get('Image Src') or r.get('Variant Image'):
        med = {'handle': handle, 'source_row': locator, 'source_row_role': kind,
               'image_src': r['Image Src'], 'image_position_raw': r['Image Position'],
               'image_alt_raw': r['Image Alt Text'], 'variant_image_raw': r['Variant Image'],
               'is_variant_row': has_variant, 'is_media_only_continuation': kind == 'MEDIA_ONLY_CONTINUATION'}
        MEDIA.append(med)
        p['media_row_locators'].append(n)
    ROW_RECORDS.append({'handle': handle, 'source_row': locator, 'role': kind, 'raw': r})

SKU_MAP = defaultdict(list)
TUPLE_MAP = defaultdict(list)
for v in VARIANTS:
    if v['sku_raw']:
        SKU_MAP[v['sku_raw']].append(v)
    TUPLE_MAP[(v['handle'], tuple((o['position'], o['name'], o['value']) for o in v['option_tuple']))].append(v)
COLLISIONS = {
    'duplicate_product_header_handles': HEADER_COLLISIONS,
    'repeated_nonempty_skus': [{'sku_raw': k, 'variant_keys': [v['variant_key'] for v in vals],
                              'different_handle_count': len({v['handle'] for v in vals}),
                              'classification': 'SKU_COLLISION_CANDIDATE_NOT_AUTOMATIC_DUPLICATE_PRODUCT'}
                             for k, vals in SKU_MAP.items() if len(vals) > 1],
    'repeated_option_tuples_within_handle': [{'handle': k[0], 'variant_keys': [v['variant_key'] for v in vals]}
                                            for k, vals in TUPLE_MAP.items() if len(vals) > 1],
    'numeric_product_id_collisions': {'state': 'NOT_EVALUABLE_IDS_NOT_EXPORTED'},
    'numeric_variant_id_collisions': {'state': 'NOT_EVALUABLE_IDS_NOT_EXPORTED'},
    'cross_platform_same_sku_rule': 'An intentionally mirrored Squarespace/Shopify offer is an association, not automatically a duplicate product.',
    'media_only_rows_are_never_counted_as_variants': True,
}

HISTORICAL = []
for sheet, source_id in [('SH Older Wall', 'S11_OLDER_EXTRACTED_SUBSET'), ('SH Seed Wall', 'S12_SEED_EXTRACTED_SUBSET')]:
    for r in TABLES[sheet]:
        later_skus = [v['sku_raw'] for v in VARIANTS if v['handle'] == r['Handle']]
        HISTORICAL.append({
            'snapshot_id': source_id, 'handle': r['Handle'], 'title': r['Title'],
            'numeric_product_id': None, 'numeric_variant_id': None,
            'sku_raw': r['Variant SKU'],
            'option_tuple': [{'position': i, 'name': r.get(f'Option{i} Name', ''), 'value': r.get(f'Option{i} Value', '')}
                             for i in [1, 2, 3] if r.get(f'Option{i} Name') or r.get(f'Option{i} Value')],
            'source_status_raw': r.get('Status'), 'published_raw': r.get('Published'),
            'inventory_quantity_raw': r.get('Variant Inventory Qty'),
            'inventory_policy_raw': r.get('Variant Inventory Policy'),
            'inventory_tracker_raw': r.get('Variant Inventory Tracker'),
            'price_raw': r.get('Variant Price'), 'grams_raw': r.get('Variant Grams'),
            'source_locator': {'path': str(TABLE_PATH), 'sheet': sheet, 'row': r['_row'],
                               'source_file_id': r.get('Source file ID')},
            'source_fidelity': r.get('Source fidelity'),
            'scope': 'HISTORICAL_SOURCE_ASSERTION_NOT_ADDITIONAL_CURRENT_PRODUCT',
            'later_primary_handle_present': r['Handle'] in PRODUCTS,
            'later_primary_skus_raw': later_skus,
            'same_handle_sku_relation': ('BLANK_HISTORICAL_SKU_NO_EXACT_MATCH' if not r['Variant SKU'] else 'SAME_NONEMPTY_SKU_SOURCE_VERSION' if r['Variant SKU'] in later_skus else 'DIFFERENT_NONEMPTY_SKU_HISTORICAL_CANDIDATE_ONLY'),
            'same_handle_is_not_variant_or_sku_equivalence': True,
            'export_creation_date': None,
            'source_date_limits': 'Source register observed 15 October 2026 and reports server modified 8 February 2026; neither is an encoded original export date.',
            'raw': r,
        })

COUNTS = {
    'native_data_rows': len(ROWS), 'native_columns': len(HEADERS),
    'native_products_by_header_handle': len(PRODUCTS), 'native_variant_rows': len(VARIANTS),
    'native_row_roles': dict(Counter(r['role'] for r in ROW_RECORDS)),
    'product_status_snapshot': dict(Counter(p['status_raw'] for p in PRODUCTS.values())),
    'product_published_snapshot': dict(Counter(p['published_raw'] for p in PRODUCTS.values())),
    'products_in_preserved_wall_subset': sum(p['in_preserved_wall_subset'] for p in PRODUCTS.values()),
    'wall_subset_variant_rows': sum(v['handle'] in WALL_PRODUCTS for v in VARIANTS),
    'media_row_occurrences': len(MEDIA),
    'variants_with_nonempty_sku': sum(bool(v['sku_raw']) for v in VARIANTS),
    'variants_with_blank_sku': sum(not v['sku_raw'] for v in VARIANTS),
    'repeated_nonempty_skus': len(COLLISIONS['repeated_nonempty_skus']),
    'historical_extracted_wall_rows': len(HISTORICAL),
    'new_numeric_product_ids_asserted': 0, 'new_numeric_variant_ids_asserted': 0,
    'current_authenticated_products_verified': 0, 'current_public_products_verified': 0,
    'remote_calls': 0, 'platform_writes': 0, 'dropbox_writes': 0,
}

write('shopify_products.json', list(PRODUCTS.values()))
write('shopify_variants.json', VARIANTS)
write('shopify_media_rows.json', MEDIA)
write('shopify_native_rows.json', ROW_RECORDS)
write('shopify_historical_assertions.json', HISTORICAL)
write('shopify_collisions.json', COLLISIONS)
write('source_comparison.json', {
    'primary_source': 'SH_NATIVE_CSV_S09', 'differences': DIFFS,
    'difference_counts_by_source_field': dict(Counter(d['source_id'] + ':' + d['field'] for d in DIFFS)),
    'all_differences_equivalent_after_explicit_normalization': all(d['equivalent_after_explicit_normalization'] for d in DIFFS),
    'normalization': 'Trim Vendor and Image Alt Text edge whitespace; compare the two Google Custom Product boolean columns case-insensitively; compare numeric columns with Decimal; normalize CR/LF line endings. All source raw values remain retained.',
})
write('source_receipts.json', {
    'schema': 'boldstone.shopify-native-source-receipts.v1', 'observed_utc': NOW,
    'sources': RECEIPTS, 'historical_source_register': [r for r in TABLES['Source Register'] if r.get('Source ID') in ['S02', 'S09', 'S11', 'S12']],
    'native_source_dates': SOURCE_DATES,
    'completeness': {'all_rows_of_three_local_files_parsed': True,
                     'primary_local_file_parse_complete': True,
                     'storewide_export_selection_or_filter_record_present': False,
                     'current_authenticated_inventory_completeness_verified': False,
                     'historical_older_source_original_bytes_recovered_in_this_audit': False,
                     'older_source_claimed_total_headers': 12,
                     'older_source_wall_rows_preserved_and_normalized': 6,
                     'seed_source_rows_preserved_and_normalized': 3},
})
write('inventory_schema.json', {
    'schema': 'boldstone.shopify-inventory-schema.v1',
    'products_file': str(W / 'shopify_products.json'),
    'variants_file': str(W / 'shopify_variants.json'),
    'media_file': str(W / 'shopify_media_rows.json'),
    'raw_rows_file': str(W / 'shopify_native_rows.json'),
    'historical_assertions_file': str(W / 'shopify_historical_assertions.json'),
    'product_identity': 'snapshot source ID plus exact exported handle; no unexported numeric ID invented',
    'variant_identity': 'exact source logical row under parent handle, preserving raw SKU and named option tuple',
    'continuation_rule': 'Option/variant fields mark a variant row. Blank product fields alone do not make a new product. Media-only continuation rows remain media.',
    'source_row_locator': 'logical row including header, with physical start/end line numbers retained for the CSV',
    'date_limit': SOURCE_DATES,
})
write('shopify_inventory.json', {
    'schema': 'boldstone.shopify-native-inventory.v1', 'worker_number': 2,
    'prepared_utc': NOW, 'master_input': {'path': str(MASTER), 'sha256': MASTER_HASH, 'options': len(M['options'])},
    'counts': COUNTS, 'primary_source_id': 'SH_NATIVE_CSV_S09',
    'product_records_file': str(W / 'shopify_products.json'),
    'variant_records_file': str(W / 'shopify_variants.json'),
    'raw_rows_file': str(W / 'shopify_native_rows.json'),
    'source_receipts_file': str(W / 'source_receipts.json'),
    'historical_assertions_file': str(W / 'shopify_historical_assertions.json'),
    'public_inventory_state': 'STORE_DOMAIN_NOT_EVIDENCED; NO_ACCOUNT_IDENTIFIER_GUESSED',
    'authenticated_inventory_state': 'NO_CONNECTED_SHOPIFY_ADMIN_EXPORT_AVAILABLE_IN_THIS_LANE',
    'date_and_completeness_limits': SOURCE_DATES,
    'all_current_or_draft_products_completeness': 'NOT_VERIFIED_FROM_HISTORICAL_EXPORT',
    'current_inventory_completeness_verified': False,
    'absence_from_snapshot_is_not_live_absence': True,
    'source_inventory_is_not_184_canonical_option_count': True,
    'raw_source_history_preserved': True,
})
assert len(PRODUCTS) == 136 and len(VARIANTS) == 160
assert COUNTS['native_row_roles'] == {'PRODUCT_HEADER_AND_VARIANT': 136, 'MEDIA_ONLY_CONTINUATION': 256, 'VARIANT_CONTINUATION': 24}
assert set(WALL_PRODUCTS) <= set(PRODUCTS)
assert len(HISTORICAL) == 9
assert not HEADER_COLLISIONS
assert all(d['equivalent_after_explicit_normalization'] for d in DIFFS)
print(json.dumps({'output': str(W / 'shopify_inventory.json'), 'counts': COUNTS,
                  'comparison_difference_fields': dict(Counter(d['source_id'] + ':' + d['field'] for d in DIFFS))}, indent=2))
