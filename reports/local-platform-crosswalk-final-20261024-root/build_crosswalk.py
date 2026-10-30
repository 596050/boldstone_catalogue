"""Connect the local Shopify export to retained Squarespace sources and Dropbox IDs."""
import csv
import hashlib
import html
import json
import re
import zipfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
import xml.etree.ElementTree as ET

H = Path(__file__).resolve().parent
ROOT = H.parents[1]
B = ROOT / 'sculpture-catalogue'
SH = B / 'components/parallel-reviews/listing-reconciliation-2026-10-20/worker-02'
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
esc = lambda s: html.escape(str(s), quote=True)
def write(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
def csv_records(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as stream:
        reader = csv.reader(stream)
        headers = next(reader)
        result = []
        start = reader.line_num + 1
        for number, row in enumerate(reader, 2):
            assert len(row) == len(headers)
            result.append({'logical_row_including_header': number, 'physical_line_start': start,
                'physical_line_end': reader.line_num, 'raw': dict(zip(headers, row))})
            start = reader.line_num + 1
    return headers, result

assert not (H / 'sealed-handoff.json').exists(), 'Do not overwrite a closed crosswalk.'
p = read(B / 'current-master.json')
assert sha(B / p['register']) == p['register_sha256']
g = read(B / p['register'])
assets = read(B / p['current_asset_reference_map']['path'])
option_by_id = {o['product_id']: o for o in g['options']}
active = [option_by_id[x] for x in g['active_option_ids']]
edges = {x['offer_ref']: x for x in g['source_offer_edges']}
gallery_path = ROOT / 'reports/local-platform-crosswalk-20261024-root/local-squarespace-80-full-galleries.json'
galleries = read(gallery_path)
sq_by_ref = {x['offer_ref']: x for x in galleries['records']}
source_csv = Path('/Users/tprice/Downloads/products_export_1 (1).csv')
old_csv = Path('/Users/tprice/Downloads/products_export_1.csv')
old_xlsx = Path('/Users/tprice/Downloads/Shopify Boldstone Website Exported 30.08.2024.xlsx')
headers, native_rows = csv_records(source_csv)
old_headers, old_rows = csv_records(old_csv)
assert headers == old_headers and len(headers) == 95 and len(native_rows) == len(old_rows) == 416
differences = []
for older, current in zip(old_rows, native_rows):
    for field in headers:
        if older['raw'][field] != current['raw'][field]:
            differences.append({'row': current['logical_row_including_header'], 'handle': current['raw']['Handle'],
                'column': field, 'older_value': older['raw'][field], 'selected_value': current['raw'][field]})
assert len(differences) == 17
assert all(x['column'] == 'Vendor' and x['older_value'] == 'Boldstone ' and x['selected_value'] == 'Boldstone' for x in differences)

# Inspect the dated workbook without editing it. Boolean/numeric cell types explain formatting differences.
ns = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
xlsx_rows, xlsx_types = [], []
with zipfile.ZipFile(old_xlsx) as archive:
    strings = [''.join(node.itertext()) for node in ET.fromstring(archive.read('xl/sharedStrings.xml')).findall('s:si', ns)] if 'xl/sharedStrings.xml' in archive.namelist() else []
    sheet = ET.fromstring(archive.read('xl/worksheets/sheet1.xml'))
    for row in sheet.findall('s:sheetData/s:row', ns):
        values, types = [''] * 95, [''] * 95
        for cell in row.findall('s:c', ns):
            letters = re.sub(r'\d', '', cell.get('r'))
            column = 0
            for letter in letters:
                column = column * 26 + ord(letter) - 64
            value_node = cell.find('s:v', ns)
            value = value_node.text if value_node is not None else ''
            kind = cell.get('t', 'n')
            if kind == 's':
                value = strings[int(value)]
            elif kind == 'inlineStr':
                value = ''.join(cell.find('s:is', ns).itertext())
            if column <= 95:
                values[column - 1], types[column - 1] = value, kind
        xlsx_rows.append(values)
        xlsx_types.append(types)
assert xlsx_rows[0] == headers and len(xlsx_rows) == 417
xlsx_differences = []
xlsx_whitespace_differences = []
typed_equivalences = Counter()
for i, row in enumerate(old_rows, 1):
    for j, field in enumerate(headers):
        a, b, kind = row['raw'][field], xlsx_rows[i][j], xlsx_types[i][j]
        if a == b:
            continue
        if field in ['Vendor', 'Image Alt Text'] and a.rstrip() == b.rstrip():
            xlsx_whitespace_differences.append({'row': i + 1, 'field': field, 'csv': a, 'xlsx': b})
            continue
        equal = False
        if kind == 'b':
            equal = a.lower() == ('true' if b == '1' else 'false')
        elif kind == 'n' and a and b and not any(x in field for x in ['SKU', 'Barcode', 'Handle', 'ID']):
            try:
                equal = Decimal(a) == Decimal(b)
            except InvalidOperation:
                pass
        if equal:
            typed_equivalences[kind] += 1
        else:
            xlsx_differences.append({'row': i + 1, 'field': field, 'csv': a, 'xlsx': b, 'cell_type': kind})
assert not xlsx_differences, xlsx_differences[:5]

products = read(SH / 'shopify_products.json')
variants = read(SH / 'shopify_variants.json')
media = read(SH / 'shopify_media_rows.json')
derived_rows = read(SH / 'shopify_native_rows.json')
assert len(products) == 136 and len(variants) == 160 and len(media) == len(derived_rows) == 416
for source, derived in zip(native_rows, derived_rows):
    assert source['raw'] == derived['raw']
    assert all(source[k] == derived['source_row'][k] for k in ['logical_row_including_header', 'physical_line_start', 'physical_line_end'])
by_handle = {x['handle']: x for x in products}
variants_by_handle, variants_by_sku, media_by_handle = defaultdict(list), defaultdict(list), defaultdict(list)
for variant in variants:
    variants_by_handle[variant['handle']].append(variant)
    if variant['sku_raw']:
        variants_by_sku[variant['sku_raw']].append(variant)
    row = native_rows[variant['source_row']['logical_row_including_header'] - 2]['raw']
    assert row['Handle'] == variant['handle'] and row['Variant SKU'] == variant['sku_raw']
    assert row['Variant Image'] == variant['variant_image_raw']
for item in media:
    media_by_handle[item['handle']].append(item)
    row = native_rows[item['source_row']['logical_row_including_header'] - 2]['raw']
    assert row['Image Src'] == item['image_src'] and row['Image Position'] == item['image_position_raw']
assert all(x['numeric_product_id'] is None for x in products)
assert all(x['numeric_variant_id'] is None for x in variants)
assert not any(x['variant_image_raw'] for x in variants)

fresh_path = ROOT / 'reports/dropbox-wall-complete-role-review-20261024T214349Z/all-current-6360-image-folder-links.json'
fresh_map = {x['file_id']: x for x in read(fresh_path)}
assert len(fresh_map) == 6360
def reference(fid, fallback=None):
    saved = assets.get(fid, fallback)
    observed = fresh_map.get(fid)
    result = {'file_id': fid, 'saved_catalogue_reference': saved, 'fresh_scoped_native_reference': observed,
        'fresh_scope': '/BOLDSTONE MASTER/Products/01 Wall Sculptures',
        'status': 'PRESENT_IN_FRESH_WALL_SCOPE' if observed else 'NOT_PRESENT_IN_THIS_SCOPED_SNAPSHOT_NO_DELETION_INFERENCE',
        'canonical_reference_changed_by_crosswalk': False}
    if saved and observed:
        result['actual_parent_matches_saved_parent'] = saved.get('folder_id') == observed['folder_id']
    return result

observations = {x['offer_ref']: x for x in g['current_authenticated_squarespace_inventory_observation']['retained_offer_observations']}
source_records, pairs, unpaired_sq = [], [], []
related_by_option = defaultdict(list)
for ref, gallery in sq_by_ref.items():
    edge = edges[ref]
    sku = gallery['sku_raw']
    candidates = variants_by_sku.get(sku, []) if sku else []
    assert len(candidates) <= 1
    expected_handle = edge['source_offer']['sh_handle']
    if expected_handle:
        assert len(candidates) == 1 and candidates[0]['handle'] == expected_handle
    else:
        assert not candidates
    targets = {x for member in edge['members'] for x in member['canonical_component_targets']}
    related = []
    for option in active:
        if option['canonical_component_id'] in targets:
            related_by_option[option['product_id']].append(ref)
            related.append({'product_id': option['product_id'], 'name': option['name'],
                'canonical_component_id': option['canonical_component_id'], 'master_fields': option['master_fields'],
                'current_reference': reference(option['file_id']),
                'relationship': 'Existing component-level source association; finish, size, build and specimen applicability remain qualified.',
                'new_exact_individual_variant_assignment': False})
    source_reference = edge.get('current_primary_reference')
    source_image_reference = reference(source_reference['file_id'], source_reference) if source_reference else {
        'file_id': None, 'saved_catalogue_reference': None, 'fresh_scoped_native_reference': None,
        'status': 'EXISTING_SOURCE_IMAGE_HOLD_NO_CURRENT_PRIMARY', 'canonical_reference_changed_by_crosswalk': False}
    record = {'offer_ref': ref, 'source_title': gallery['title'],
        'squarespace_native_tuple': {k: gallery[k] for k in ['native_product_id', 'native_variant_id', 'sku_raw']},
        'local_squarespace_gallery_record': gallery,
        'local_squarespace_nine_field_observation': observations[ref],
        'retained_source_offer': edge['source_offer'], 'retained_member_scope': edge['members'],
        'source_image_reference': source_image_reference,
        'related_current_individual_options': related,
        'platform_record_match': 'EXACT_NONEMPTY_SHARED_SKU_IN_REQUESTED_LOCAL_FILES' if candidates else 'NO_NONEMPTY_SHARED_SKU_MATCH_IN_REQUESTED_LOCAL_SHOPIFY_DATA',
        'shopify_local_variant': candidates[0] if candidates else None,
        'shopify_local_product': by_handle[candidates[0]['handle']] if candidates else None,
        'shopify_full_product_gallery': media_by_handle[candidates[0]['handle']] if candidates else [],
        'product_gallery_is_not_explicit_variant_image_assignment': True,
        'all_prices_weights_stock_and_set_quantity_claims_remain_separate': True,
        'new_platform_data_or_catalogue_writes': False}
    source_records.append(record)
    (pairs if candidates else unpaired_sq).append(record)
assert len(pairs) == 37 and len(unpaired_sq) == 43
paired_handles = {x['shopify_local_product']['handle'] for x in pairs}
wall_products = [x for x in products if x['in_preserved_wall_subset']]
shopify_only = [x for x in wall_products if x['handle'] not in paired_handles]
assert len(wall_products) == 38 and len(shopify_only) == 1
assert shopify_only[0]['handle'] == edges['SH-DRAFT']['source_offer']['sh_handle']
squarespace_associated_option_ids = set(related_by_option)
squarespace_association_count = sum(len(x) for x in related_by_option.values())
draft_targets = {target for member in edges['SH-DRAFT']['members'] for target in member['canonical_component_targets']}
draft_related = []
for option in active:
    if option['canonical_component_id'] in draft_targets:
        related_by_option[option['product_id']].append('SH-DRAFT')
        draft_related.append({'product_id': option['product_id'], 'name': option['name'],
            'canonical_component_id': option['canonical_component_id'], 'current_reference': reference(option['file_id']),
            'master_fields': option['master_fields'],
            'relationship': 'Retained proposed draft/group component association only. No nonempty SKU or exact variant assignment.',
            'new_exact_individual_variant_assignment': False})
all_local_shopify = []
for product in products:
    handle = product['handle']
    disposition = 'LOCAL_WALL_PRODUCT_WITH_EXACT_SHARED_SKU_PAIR' if handle in paired_handles else 'LOCAL_WALL_DRAFT_WITH_BLANK_SKU_NO_PAIR' if product['in_preserved_wall_subset'] else 'OUTSIDE_RETAINED_WALL_SCULPTURE_SOURCE_SCOPE'
    all_local_shopify.append({'handle': handle, 'product': product, 'variants': variants_by_handle[handle],
        'full_product_gallery': media_by_handle[handle], 'disposition': disposition,
        'matched_squarespace_offer_refs': [x['offer_ref'] for x in pairs if x['shopify_local_product']['handle'] == handle],
        'Shopify_numeric_ID_state': 'Not exported in the local CSV; handle/options/hash-bound row locators retained as actual source identifiers.',
        'explicit_variant_image_state': 'No Variant Image value exported; product gallery membership retained without variant-specific assignment.'})
options_without_source = [{'product_id': o['product_id'], 'name': o['name'], 'canonical_component_id': o['canonical_component_id'],
    'current_reference': reference(o['file_id']), 'master_fields': o['master_fields'],
    'status': 'No existing source-component edge in the retained register. Not proof of platform absence; no SKU or variant invented.'}
    for o in active if o['product_id'] not in related_by_option]

inputs = [source_csv, old_csv, old_xlsx, gallery_path, fresh_path,
    SH / 'shopify_products.json', SH / 'shopify_variants.json', SH / 'shopify_media_rows.json',
    SH / 'shopify_native_rows.json', SH / 'source_receipts.json',
    B / p['register'], B / p['current_asset_reference_map']['path']]
source_manifest = {str(x): {'sha256': sha(x), 'bytes': x.stat().st_size} for x in inputs}
controls = [B / x for x in ['current-master.json', 'components/reviews/specification_review_progress.json', 'components/checkpoint.json', 'checkpoint.json']]
protected = {str(x): sha(x) for x in [*controls, B / p['register'], B / p['workbook'],
    B / p['current_asset_reference_map']['path'], B / p['current_native_reference_map']['path'], Path(p['latest_image_coverage_audit']['path'])]}
authority = {'scope': 'User explicitly requested the locally stored Shopify records. No live Shopify verification or account access is required for this crosswalk.',
    'primary_shopify_export': {'path': str(source_csv), 'sha256': sha(source_csv), 'rows': 416, 'columns': 95,
        'export_creation_date': None, 'date_note': 'Export date not encoded. The dated2024 workbook corroborates this inventory. The later copy modification date is not a new export date.'},
    'older_csv_comparison': {'path': str(old_csv), 'sha256': sha(old_csv), 'differences': differences,
        'all_product_variant_SKU_image_fields_equal': True},
    'dated_workbook_comparison': {'path': str(old_xlsx), 'sha256': sha(old_xlsx), 'sheet': 'products_export_1',
        'rows': 416, 'columns': 95, 'typed_boolean_numeric_equivalences': dict(typed_equivalences),
        'trailing_whitespace_differences_preserved': xlsx_whitespace_differences,
        'substantive_differences_from_older_csv': xlsx_differences},
    'newest_discovered_native_inventory': 'Selected CSV S09, corroborated by the older CSV and dated workbook. Newly generated reconciliation files and image-register databases are derived outputs.'}
counts = {'local_shopify_products': len(products), 'local_shopify_variants': len(variants),
    'local_shopify_gallery_row_occurrences': len(media), 'local_wall_shopify_products': len(wall_products),
    'local_wall_shopify_variant_rows': sum(x['handle'] in {a['handle'] for a in wall_products} for x in variants),
    'local_wall_shopify_gallery_row_occurrences': sum(len(media_by_handle[x['handle']]) for x in wall_products),
    'retained_squarespace_source_records': 80, 'squarespace_gallery_entries': 445,
    'exact_nonempty_shared_SKU_local_source_pairs': len(pairs), 'unpaired_local_squarespace_sources': len(unpaired_sq),
    'unpaired_local_shopify_wall_drafts': len(shopify_only), 'other_shopify_products_outside_wall_scope': len(products) - len(wall_products),
    'active_options_with_existing_source_component_associations': len(related_by_option),
    'active_options_with_existing_Squarespace_source_component_associations': len(squarespace_associated_option_ids),
    'Squarespace_source_to_active_option_associations': squarespace_association_count,
    'retained_draft_context_to_active_option_associations': len(draft_related),
    'active_options_without_existing_source_component_associations': len(options_without_source),
    'existing_source_to_active_option_associations': sum(len(x) for x in related_by_option.values()),
    'new_exact_individual_variant_assignments': 0, 'new_numeric_Shopify_IDs_invented': 0,
    'explicit_Shopify_variant_image_values': 0, 'network_calls_by_local_crosswalk': 0, 'canonical_or_platform_writes': 0}
result = {'schema': 'boldstone.local-platform-product-variant-image-crosswalk.v1',
    'status': 'COMPLETE_REQUESTED_LOCAL_RECORD_CROSSWALK_WITH_EXPLICIT_CONFIGURATION_LIMITS',
    'prepared_utc': datetime.now(timezone.utc).isoformat(), 'source_authority': authority,
    'baseline_pointer_sha256': protected[str(B / 'current-master.json')], 'baseline_protected_files': protected,
    'source_manifest': source_manifest, 'counts': counts, 'squarespace_source_records': source_records,
    'local_shopify_records': all_local_shopify, 'matched_local_source_offer_refs': [x['offer_ref'] for x in pairs],
    'unpaired_squarespace_offer_refs': [x['offer_ref'] for x in unpaired_sq],
    'unpaired_shopify_wall_records': [{'product': x, 'variants': variants_by_handle[x['handle']],
        'full_product_gallery': media_by_handle[x['handle']], 'retained_source_offer': edges['SH-DRAFT'],
        'related_current_individual_options': draft_related,
        'status': 'Blank source SKU. Group photograph remains context; no alias or new variant assignment.'} for x in shopify_only],
    'active_options_without_existing_source_edges': options_without_source,
    'standing_holds_and_qualified_working_fields_retained': True,
    'source_variant_identifier_note': 'Squarespace product/variant IDs are encoded by the local export. Shopify numeric IDs are not exported: exact local rows retain handle, option tuple, raw SKU and source filepath/hash/row. A generated row key is not a native Shopify variant ID.',
    'image_binding_note': 'All exported gallery memberships are retained. Gallery position and a source-row association do not establish variant-specific image assignment or original-pixel correspondence; the image-review lane owns those comparisons.'}
write(H / 'local-platform-crosswalk.json', result)

cards = []
for x in source_records:
    reference_record = x['source_image_reference']
    a = reference_record['fresh_scoped_native_reference'] or reference_record['saved_catalogue_reference']
    sh = x['shopify_local_product']
    link = '<a href="' + esc(a['image_url']) + '">Dropbox image</a> · <a href="' + esc(a['folder_url']) + '">Containing folder</a>' if a else 'Dropbox reference unresolved'
    related = ''.join('<li>' + esc(o['name']) + ' · <a href="' + esc((o['current_reference']['fresh_scoped_native_reference'] or o['current_reference']['saved_catalogue_reference'])['image_url']) + '">Image</a> · <a href="' + esc((o['current_reference']['fresh_scoped_native_reference'] or o['current_reference']['saved_catalogue_reference'])['folder_url']) + '">Folder</a></li>' for o in x['related_current_individual_options'])
    sq_images = ''.join('<li><a href="' + esc(m['url']) + '">Squarespace gallery ' + str(m['gallery_index'] + 1) + '</a></li>' for m in x['local_squarespace_gallery_record']['ordered_gallery'])
    sh_images = ''.join('<li><a href="' + esc(m['image_src']) + '">Shopify gallery position ' + esc(m['image_position_raw']) + '</a></li>' for m in x['shopify_full_product_gallery'])
    cards.append('<article id="' + esc(x['offer_ref']) + '"><h2>' + esc(x['offer_ref'] + ' ' + x['source_title']) + '</h2><p>' + esc(x['platform_record_match']) + '</p><p>' + link + '</p><p>Shared SKU: ' + esc(x['squarespace_native_tuple']['sku_raw']) + '<br>Squarespace product: ' + esc(x['squarespace_native_tuple']['native_product_id']) + '<br>Squarespace variant: ' + esc(x['squarespace_native_tuple']['native_variant_id']) + '<br>Local Shopify handle: ' + esc(sh['handle'] if sh else 'No matching nonempty SKU in the local export') + '</p><p>Gallery membership is retained at product level. Exact finish/size/build applicability and variant image assignments remain separately qualified.</p><details><summary>Related existing individual options (' + str(len(x['related_current_individual_options'])) + ')</summary><ul>' + related + '</ul></details><details><summary>Complete local gallery lists</summary><ul>' + sq_images + sh_images + '</ul></details></article>')
other_rows = ''.join('<tr><td>' + esc(x['handle']) + '</td><td>' + esc(x['product']['title']) + '</td><td>' + esc(x['disposition']) + '</td><td>' + str(len(x['variants'])) + '</td><td>' + str(len(x['full_product_gallery'])) + '</td></tr>' for x in all_local_shopify)
(H / 'index.html').write_text('<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Local Shopify and Squarespace matching</title><style>body{font:17px Arial;line-height:1.5;max-width:1100px;margin:40px auto;padding:0 20px;color:#222}article{border-top:1px solid #bbb;padding:20px 0}table{width:100%;border-collapse:collapse}th,td{text-align:left;vertical-align:top;border-bottom:1px solid #ddd;padding:10px;overflow-wrap:anywhere}details{margin:12px 0}small{overflow-wrap:anywhere}</style></head><body><h1>Local Shopify and Squarespace matching</h1><p>37 exact shared-SKU source pairs,43 Squarespace sources without a local Shopify SKU match, and1 unmatched local Shopify wall draft. All136 local Shopify products,160 variants and416 gallery rows are accounted for;38 products and117 gallery rows belong to the retained wall subset.</p><p>The selected local Shopify CSV is the requested authority. Its later copy differs from the dated2024 files only in Vendor whitespace; source dates and all raw terms remain recorded. No online account access is needed for this comparison.</p><p>Shopify numeric product and variant IDs are not encoded by these local files. Handles, option tuples, raw SKUs and hash-bound row locators preserve exact local records. No numeric IDs or individual variant assignments have been invented.</p><p>All445 local Squarespace gallery entries are included. Existing component associations, including the proposed draft context, cover123 active options;65 have no source-component edge in the retained register. This is not a platform-absence or sculpture-count claim.</p><nav><a href="#O012">Start the matched records</a> · <a href="#all-shopify">All local Shopify records</a></nav>' + ''.join(cards) + '<h2 id="all-shopify">All local Shopify record dispositions</h2><table><tr><th>Handle</th><th>Title</th><th>Disposition</th><th>Variants</th><th>Gallery rows</th></tr>' + other_rows + '</table></body></html>')

assert all(sha(path) == expected for path, expected in protected.items())
assert all(sha(path) == value['sha256'] for path, value in source_manifest.items())
checks = {'all416raw_rows95columns_equal_selected_local_export': True,
    'all17olderCSVdifferences_are_vendor_whitespace_only': len(differences) == 17,
    'dated_workbook_semantically_equals_olderCSV': not xlsx_differences,
    'all136products160variants416media_rows_accounted': len(all_local_shopify) == 136,
    'all37nonempty_exactSKU_pairs_preserved': len(pairs) == 37,
    'all43unpairedSquarespace_sources_preserved': len(unpaired_sq) == 43,
    'one_blankSKU_Shopify_wall_draft_unmatched': len(shopify_only) == 1,
    'all80Squarespace_native_tuples_and445gallery_entries_bound': len(source_records) == 80,
    'all188activeoptions_have_association_or_explicit_unassigned_disposition': len(related_by_option) + len(options_without_source) == 188,
    'noShopify_numericIDs_or_variant_image_assignments_invented': counts['new_numeric_Shopify_IDs_invented'] == counts['explicit_Shopify_variant_image_values'] == 0,
    'allProtected_shared_catalogue_files_unchanged': all(sha(path) == expected for path, expected in protected.items())}
assert all(checks.values())
verification = {'status': 'PASS', 'checks_passed': sum(checks.values()), 'checks_total': len(checks),
    'checks': checks, 'counts': counts, 'review_sha256': sha(H / 'local-platform-crosswalk.json'), 'page_sha256': sha(H / 'index.html')}
write(H / 'verification.json', verification)
files = [Path(__file__), gallery_path.with_name('prepare_local_gallery.py'), gallery_path, H / 'local-platform-crosswalk.json', H / 'index.html', H / 'verification.json']
write(H / 'sealed-handoff.json', {'status': 'SEALED_REQUESTED_LOCAL_PLATFORM_CROSSWALK',
    'recorded_utc': result['prepared_utc'], 'files': {str(x): sha(x) for x in files}})
print(json.dumps({**verification, 'seal_sha256': sha(H / 'sealed-handoff.json')}))
