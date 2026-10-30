"""Extract all retained Squarespace galleries from the local authenticated export."""
import csv
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path

H = Path(__file__).resolve().parent
B = H.parents[1] / 'sculpture-catalogue'
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
pointer = read(B / 'current-master.json')
register = read(B / pointer['register'])
observations = register['current_authenticated_squarespace_inventory_observation']
source = observations['squarespace_source_clock']
source_path = Path(source['raw_export']['path'])
assert sha(source_path) == source['raw_export']['sha256']
with source_path.open(encoding='utf-8-sig', newline='') as stream:
    rows = list(csv.DictReader(stream))
by_product = defaultdict(list)
for number, row in enumerate(rows, 2):
    by_product[row['Product ID [Non Editable]']].append((number, row))
inventory_path = B / 'components/parallel-reviews/listing-resolution-2026-10-21/worker-01/FRESH_PUBLIC_INVENTORY.json'
prior_products = {x['native_product_id']: x for x in read(inventory_path)['products']}
records = []
for observation in observations['retained_offer_observations']:
    native = observation['observed_native_source_tuple']
    product_rows = by_product[native['product_id']]
    matching = [(n, r) for n, r in product_rows if r['Variant ID [Non Editable]'] == native['variant_id']]
    assert len(matching) == 1
    number, row = matching[0]
    assert row['SKU'] == native['sku_raw']
    gallery, seen = [], set()
    for row_number, product_row in product_rows:
        for url in re.findall(r'https?://\S+', product_row['Hosted Image URLs']):
            if url not in seen:
                seen.add(url)
                gallery.append({'gallery_index': len(gallery), 'url': url,
                    'csv_record_including_header_1based': row_number, 'source_column': 'Hosted Image URLs',
                    'variant_specific_assignment_certified': False})
    previous = prior_products.get(native['product_id'])
    prior_media = previous['native_media_items'] if previous else []
    records.append({'offer_ref': observation['offer_ref'], 'native_product_id': native['product_id'],
        'native_variant_id': native['variant_id'], 'sku_raw': native['sku_raw'], 'title': row['Title'],
        'csv_record_including_header_1based': number,
        'all_product_csv_records': [{'csv_record_including_header_1based': n, 'raw': r} for n, r in product_rows],
        'ordered_gallery': gallery, 'gallery_entry_count': len(gallery), 'captured_utc': source['captured_utc'],
        'csv_path': str(source_path), 'csv_sha256': sha(source_path),
        'prior_public_gallery': {'inventory_path': str(inventory_path), 'inventory_sha256': sha(inventory_path),
            'product_locator': previous['source_locator'] if previous else None, 'native_media_items': prior_media,
            'scope': 'Retained21Oct public capture; media IDs are preserved without asserting24Oct gallery IDs not encoded by CSV.'},
        'URL_membership_matches_prior_public_capture': seen == {m.get('assetUrl') for m in prior_media},
        'image_scope': 'Ordered product-gallery membership from local authenticated export; row association is not proof of variant-specific image assignment.'})
assert len(records) == 80
assert sum(x['gallery_entry_count'] for x in records) == 445
output = {'schema': 'boldstone.local-squarespace-full-gallery.v1',
    'status': 'COMPLETE_LOCAL_EXPORT_GALLERY_MEMBERSHIP_NOT_VISUAL_REVIEW', 'source': source,
    'baseline_current_pointer_sha256': sha(B / 'current-master.json'), 'records': records,
    'counts': {'retained_source_products': 80, 'ordered_gallery_entries': 445,
        'unique_gallery_URLs': len({m['url'] for x in records for m in x['ordered_gallery']}),
        'products_matching_prior_public_URL_membership': sum(x['URL_membership_matches_prior_public_capture'] for x in records)},
    'source_records_with_no_prior_full_public_gallery': [x['offer_ref'] for x in records if not x['prior_public_gallery']['native_media_items']],
    'new_visual_reviews': 0, 'native_or_platform_writes': 0}
destination = H / 'local-squarespace-80-full-galleries.json'
assert not destination.exists(), 'Do not overwrite an issued gallery handoff.'
destination.write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'path': str(destination), 'sha256': sha(destination), 'counts': output['counts'],
    'source_records_with_no_prior_full_public_gallery': output['source_records_with_no_prior_full_public_gallery']}))
