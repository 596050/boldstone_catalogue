import collections, hashlib, json
from pathlib import Path
from PIL import Image, ImageChops, ImageStat
from capture_public_inventory import OUT, BASE, OLD, digest, now, save

PAIRS = [('RUST-SKU-COLLISION', 'O051', 'O067'), ('VERDIGRIS-VERSIONS', 'O004', 'O038'), ('MOON-WATER-OVERLAP', 'O015', 'O059'), ('GOLD-HISTORICAL-OVERLAP', 'O002', 'O039'), ('SILVER-HISTORICAL-OVERLAP', 'O003', 'O064')]

def pointer(root, path):
    value = root
    for part in path.split('/')[1:]:
        part = part.replace('~1', '/').replace('~0', '~')
        value = value[int(part)] if isinstance(value, list) else value[part]
    return value

def esc(value):
    return str(value).replace('~', '~0').replace('/', '~1')

def deepdiff(left, right, path=''):
    if isinstance(left, dict) and isinstance(right, dict):
        rows = []
        for key in sorted(set(left) | set(right)):
            if key not in left:
                rows.append({'json_pointer': path + '/' + esc(key), 'state': 'RIGHT_ONLY', 'right': right[key]})
            elif key not in right:
                rows.append({'json_pointer': path + '/' + esc(key), 'state': 'LEFT_ONLY', 'left': left[key]})
            else:
                rows.extend(deepdiff(left[key], right[key], path + '/' + esc(key)))
        return rows
    if isinstance(left, list) and isinstance(right, list):
        rows = []
        for i in range(max(len(left), len(right))):
            if i >= len(left):
                rows.append({'json_pointer': path + '/' + str(i), 'state': 'RIGHT_ONLY', 'right': right[i]})
            elif i >= len(right):
                rows.append({'json_pointer': path + '/' + str(i), 'state': 'LEFT_ONLY', 'left': left[i]})
            else:
                rows.extend(deepdiff(left[i], right[i], path + '/' + str(i)))
        return rows
    return [] if left == right else [{'json_pointer': path, 'state': 'DIFFERENT', 'left': left, 'right': right}]

def product_summary(case):
    product = case['direct_product_check'].get('detail_product') or case.get('fresh_collection_product')
    historical = case['sealed_2026_10_20_product']
    current = bool(product)
    source = case['frozen_master_source_offer']
    value = {
        'offer_ref': case['offer_ref'], 'native_product_id': case['native_product_id'], 'title': product['title'] if current else historical['title'],
        'url': source['source_url'], 'current_public_collection_observed': bool(case.get('fresh_collection_product')),
        'current_canonical_url_http_status': case['direct_product_check']['receipt'].get('status'),
        'description_text': product['description_text'] if current else historical['description_text'],
        'description_evidence_state': 'CURRENT_PUBLIC_SOURCE_CLAIM' if current else 'HISTORICAL_CACHED_NATIVE_SOURCE_CLAIM',
        'variants': product['variants'] if current else historical['variants'],
        'native_timestamps': product.get('timestamps') if current else None,
        'timestamp_limits': 'Native added/updated/published clocks describe a platform record, not casting date or approval. Historical cache lacks native timestamps.' if not current else 'Native added/updated/published clocks describe a platform record, not casting date or approval.',
        'source_image_file_id': source['image_file_id'], 'source_image_folder_id': source['image_folder_id'],
        'public_gallery_media_ids': [a['id'] for a in product['native_media_items']] if current else [],
        'source_locator': product['source_locator'] if current else historical['preferred_source_locator'],
        'frozen_source_offer_locator': dict(case['frozen_master_source_locator'], json_pointer=case['frozen_master_source_locator']['json_pointer'] + '/source_offer')}
    return value

def build():
    data = json.loads((OUT / 'CASE_SOURCE_RECORDS.json').read_text())
    cases = {c['offer_ref']: c for c in data['case_source_records']}
    images = json.loads((OUT / 'CASE_IMAGE_RECEIPTS.json').read_text())
    historical_images = json.loads((OUT / 'HISTORICAL_MEDIA_RECEIPTS.json').read_text())['media']
    comparisons = []
    for case_id, left_ref, right_ref in PAIRS:
        left, right = cases[left_ref], cases[right_ref]
        lp = left['direct_product_check'].get('detail_product') or left.get('fresh_collection_product')
        rp = right['direct_product_check'].get('detail_product') or right.get('fresh_collection_product')
        l_images = [r for r in images['public_media'] if r['offer_ref'] == left_ref]
        r_images = [r for r in images['public_media'] if r['offer_ref'] == right_ref]
        r_images += [r for r in historical_images if r['offer_ref'] == right_ref]
        byte_equal, pixel_equal, thumbnail_metrics = [], [], []
        for li in l_images:
            for ri in r_images:
                link = {'left_gallery_index': li['gallery_index'], 'right_gallery_index': ri.get('gallery_index',ri.get('historical_gallery_index')), 'left_body_path': li['receipt']['body_path'], 'right_body_path': ri['receipt']['body_path']}
                if li['receipt']['sha256'] == ri['receipt']['sha256']:
                    byte_equal.append(link)
                if li.get('decoded_rgb_sha256') == ri.get('decoded_rgb_sha256'):
                    pixel_equal.append(link)
                if li.get('image_decode_success') and ri.get('image_decode_success'):
                    with Image.open(li['receipt']['body_path']) as image:
                        lthumb = image.convert('RGB').resize((180,240))
                    with Image.open(ri['receipt']['body_path']) as image:
                        rthumb = image.convert('RGB').resize((180,240))
                    statistics = ImageStat.Stat(ImageChops.difference(lthumb,rthumb))
                    thumbnail_metrics.append(dict(link, mean_absolute_rgb_difference_0_to_255=round(sum(statistics.mean)/3, 6)))
        comparisons.append({'case_id': case_id, 'offer_refs': [left_ref, right_ref], 'left': product_summary(left), 'right': product_summary(right),
            'current_native_records_both_available': bool(lp and rp),
            'all_native_metadata_difference_method': 'Complete recursive JSON comparison, including native IDs, nested content, media records and arrays; differing array positions retained as positions. No identity conclusion follows from equality of commercial metadata.',
            'all_native_metadata_differences': deepdiff(lp['native_record'],rp['native_record']) if lp and rp else None,
            'historical_comparison_limit': None if lp and rp else 'Unavailable product has no fresh native JSON; cached source has only exported fields. Missing native fields/timestamps are not filled from another product.',
            'encoded_image_byte_equal_pairs': byte_equal, 'decoded_rgb_pixel_equal_pairs': pixel_equal,
            'resized_image_differences': sorted(thumbnail_metrics,key=lambda v:v['mean_absolute_rgb_difference_0_to_255']),
            'image_metric_limit': 'Auxiliary difference after fixed 180x240 RGB resize, with no registration. It is not an identity decision or physical-cast verification; visual review is recorded separately.'})
    save('CASE_COMPARISONS.json', {'schema': 'boldstone.listing-overlap-native-comparisons.v1', 'created_utc': now(), 'comparisons': comparisons})
    inventory = json.loads((OUT / 'FRESH_PUBLIC_INVENTORY.json').read_text())
    old = json.loads(OLD.read_text())
    old_public = {}
    for product in old['products']:
        observations = [o for o in product['observations'] if o['source_kind'] == 'FRESH_PUBLIC_COLLECTION_JSON']
        if observations:
            old_public[product['native_product_id']] = observations[-1]
    fresh_by = {p['native_product_id']:p for p in inventory['products']}
    old_documents = {}
    changes = []
    for native_id in sorted(set(fresh_by)&set(old_public)):
        observation = old_public[native_id]
        source = observation['source_locator']
        path = source['path']
        if path not in old_documents:
            old_documents[path] = json.loads(Path(path).read_bytes())
        raw = pointer(old_documents[path],source['json_pointer'])
        differences = deepdiff(raw, fresh_by[native_id]['native_record'])
        if differences:
            changes.append({'native_product_id':native_id,'old_source_locator':source,'fresh_source_locator':fresh_by[native_id]['source_locator'],'all_native_differences':differences})
    sku_map = collections.defaultdict(list)
    for p in inventory['products']:
        for v in p['variants']:
            if v['sku']:
                sku_map[v['sku']].append({'native_product_id':p['native_product_id'],'native_variant_id':v['native_variant_id'],'title':p['title'],'url':p['url'],'option_attributes':v['option_attributes'],'source_locator':v['source_locator']})
    result = {'schema':'boldstone.public-inventory-change-and-collision-audit.v1','created_utc':now(), 'old_public_product_count':len(old_public),'fresh_public_product_count':len(fresh_by),
        'added_public_native_product_ids': sorted(set(fresh_by)-set(old_public)), 'not_returned_today_native_product_ids':sorted(set(old_public)-set(fresh_by)),
        'common_native_records_compared':len(set(fresh_by)&set(old_public)), 'native_records_with_any_json_difference_count':len(changes),'native_record_changes':changes,
        'fresh_nonempty_sku_collisions': [{'sku':sku,'native_variant_records':records,'classification':'DISTINCT_NATIVE_RECORDS_SHARED_SKU_NOT_AUTOMATIC_DELETION_OR_PHYSICAL_IDENTITY'} for sku,records in sorted(sku_map.items()) if len(records)>1],
        'old_inventory_sha256':digest(OLD),'fresh_inventory_sha256':digest(OUT/'FRESH_PUBLIC_INVENTORY.json'), 'physical_stock_or_item_equality_verified':False,'account_completeness_verified':False}
    save('INVENTORY_CHANGES_AND_COLLISIONS.json',result)
    print(json.dumps({k:v for k,v in result.items() if k not in ['native_record_changes','fresh_nonempty_sku_collisions']},indent=2))
    print('SKU collisions',len(result['fresh_nonempty_sku_collisions']))
    for comparison in comparisons:
        print(comparison['case_id'],'native differences',len(comparison['all_native_metadata_differences']) if comparison['all_native_metadata_differences'] is not None else None,'best image differences',comparison['resized_image_differences'][:2])

if __name__ == '__main__':
    build()
