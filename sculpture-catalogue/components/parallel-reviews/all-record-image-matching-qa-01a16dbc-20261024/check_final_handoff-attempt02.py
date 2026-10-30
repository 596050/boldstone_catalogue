"""Independent, local-only verification of the explicitly frozen B handoff.

Does not contact Dropbox, reclassify photographs, open a writable database, or
write any provider/canonical file. Earlier sealed visual QA remains its evidence.
"""
from pathlib import Path
import collections
import datetime
import hashlib
from html.parser import HTMLParser
import json
import sqlite3
from urllib.parse import urlsplit, unquote, parse_qs

ROOT = Path('/Users/tprice/Documents/boldstone')
BASE = ROOT / 'sculpture-catalogue'
RUN = BASE / 'components/parallel-reviews/all-record-image-matching-20261024-B/integrations/20261024T225748917419Z'
OUT = Path(__file__).resolve().parent
DIRECTORY = ROOT / 'reports/dropbox-wall-complete-role-review-20261024T214349Z'
SEAL_SHA = 'a93db7e5584a4cc356adf03e633ee50efdff92bce82206f65dfb75b9a2347450'
CLOSING_SHA = 'ad667eec400f5cc97bf320aa1fc68bb41e65cac75242b47ba28f9f5dd190d26e'
counts = collections.Counter()
failures = []
cache = {}
bound = {}

def read(p):
    return json.loads(Path(p).read_text())

def sha(p, fresh=False):
    p = Path(p).resolve()
    if fresh or p not in cache:
        h = hashlib.sha256()
        with p.open('rb') as f:
            for block in iter(lambda: f.read(1024 * 1024), b''):
                h.update(block)
        cache[p] = h.hexdigest()
    return cache[p]

def check(ok, category, context=''):
    counts[category] += 1
    if not ok:
        failures.append({'category': category, 'context': str(context)[:700]})

def hashcheck(p, expected, category):
    p = Path(p).resolve()
    check(p.is_file() and sha(p) == expected, category, p)
    bound[str(p)] = expected

def members(p, category):
    p = Path(p)
    items = read(p).get('files', {})
    items = [{'path': k, 'sha256': v} for k, v in items.items()] if isinstance(items, dict) else items
    for item in items:
        target = Path(item['path'])
        if not target.is_absolute():
            target = p.parent / target
        hashcheck(target, item['sha256'], category)
        if 'size' in item:
            check(target.stat().st_size == item['size'], category + '_size', target)

baseline = read(OUT / 'baseline.json')
protected = list(baseline['snapshots'].values()) + list(baseline['data_files'].values())
for item in protected:
    hashcheck(item['path'], item['sha256'], 'protected_baseline_start')
for item in baseline['snapshots'].values():
    hashcheck(item['snapshot'], item['sha256'], 'independent_baseline_snapshot')

seal_path = RUN / 'sealed-handoff.json'
hashcheck(seal_path, SEAL_SHA, 'final_B_seal')
seal = read(seal_path)
check(len(seal['files']) == 367 and len(seal['provider_seals']) == 68, 'frozen_packet_scope')
for p, expected in seal['files'].items():
    hashcheck(p, expected, 'B_member_hash')
for p, expected in seal['provider_seals'].items():
    hashcheck(p, expected, 'provider_seal_hash')
    members(p, 'provider_member_hash')

closing_path = DIRECTORY / 'complete-6360-role-review-seal.json'
hashcheck(closing_path, CLOSING_SHA, 'additive_closing_seal')
closing = read(closing_path)
members(closing_path, 'closing_member_hash')
for item in closing['family_seals']:
    hashcheck(item['path'], item['sha256'], 'closing_family_seal')
    check(seal['provider_seals'].get(item['path']) == item['sha256'], 'same_60_frozen_family_seals', item['family'])
check((closing['images'], closing['families'], closing['native_writes'], closing['canonical_writes']) == (6360, 60, 0, 0), 'closing_scope_and_no_writes')

inputs = read(RUN / 'input-manifest.json')
snapshots = seal['mutable_input_pointer_snapshots']
for p, expected in inputs.items():
    if p in snapshots:
        snap = snapshots[p]
        check(snap['sha256'] == expected, 'frozen_input_pointer_identity', p)
        hashcheck(snap['frozen_copy'], expected, 'frozen_input_pointer_hash')
    else:
        hashcheck(p, expected, 'immutable_input_hash')

opening = read(DIRECTORY / 'fresh-complete-native-inventory.json')
end = read(DIRECTORY / 'closing-complete-native-inventory.json')
def census(x):
    return {a['file_id']: {k: a.get(k) for k in ['file_id', 'path', 'name', 'size', 'object_type', 'modified_time', 'client_modified']}
            for page in x['pages'] for a in page['entries']}
check(opening['pagination_complete'] and end['pagination_complete'] and len(opening['pages']) == len(end['pages']) == 12, 'closing_complete_pagination')
check(not opening['pages'][-1]['has_more'] and not end['pages'][-1]['has_more'], 'closing_terminal_pages')
check(len(census(opening)) == len(census(end)) == 6801 and census(opening) == census(end), 'independent_open_close_6801_no_drift')

register = read(baseline['data_files']['register']['path'])
original = {x['product_id']: x for x in register['options'] if x['counted_as_individual_option']}
db_path = RUN / 'complete-image-platform-register.sqlite'
db = sqlite3.connect('file:' + str(db_path) + '?mode=ro&immutable=1', uri=True)
db.execute('pragma query_only=ON')
check(db.execute('pragma integrity_check').fetchone()[0] == 'ok', 'immutable_sqlite_integrity')
def records(table):
    return [json.loads(x[0]) for x in db.execute('select record_json from ' + table)]
products = {x['product_id']: x for x in records('products')}
check(len(products) == 188 and set(products) == set(original), '188_active_option_set')
for pid, item in original.items():
    check(products.get(pid) == item, 'complete_original_option_object', pid)

images = {x['file_id']: x for x in records('images')}
native = read(DIRECTORY / 'complete-current-native-object-map.json')
roles = {x['file_id']: x for x in read(RUN / 'current-file-visual-roles.json')}
raw_roles = {x['file_id']: x for x in read(DIRECTORY / 'all-6360-current-native-visual-roles.json')}
wall = {fid: x for fid, x in images.items() if x.get('inventory_status') == 'CURRENT_NATIVE_FILE_AND_ACTUAL_PARENT_VERIFIED'}
check(len(wall) == 6360 and set(wall) == set(roles) == set(raw_roles), 'complete_6360_current_role_set')
db_roles = {x['file_id']: x for x in records('per_image_visual_roles')}
check(db_roles == roles, 'sqlite_all_roles_equal_reviewed_JSON')
for fid, item in wall.items():
    actual = native.get(fid, {})
    check(all(item.get(k) == actual.get(k) for k in ['name', 'path', 'folder_id', 'image_url', 'folder_url']), 'native_navigation_identity', fid)
    role = roles[fid]
    check({k: role.get(k) for k in raw_roles[fid]} == raw_roles[fid], 'full_visual_role_evidence_preserved', fid)
    check(role['folder_id'] == actual['parent_id'] and role['folder_url'] == actual['folder_url'] and role['image_url'] == actual['image_url'], 'actual_parent_and_image_role_links', fid)
    check(role['visual_role'] in {'individual', 'rear', 'detail', 'group_context', 'installation', 'uncertain'}, 'allowed_explicit_role', fid)
    check(role['installation_origin_or_permanence_verified'] is False and role['catalogue_photo_selections_changed'] is False and role['native_action_applied'] == 'NONE' and role['no_new_component_identity_from_group'] is True, 'role_has_no_identity_or_native_promotion', fid)
    parsed = urlsplit(role['image_url'])
    check(parse_qs(parsed.query).get('preview') == [actual['name']] and unquote(urlsplit(role['folder_url']).path).removeprefix('/home') == actual['folder_path'], 'decoded_name_and_containing_folder', fid)

families = read(RUN / 'family-image-reader-index.json')
family_flat = [fid for f in families for fid in f['current_file_ids']]
check(len(families) == 60 and len(family_flat) == len(set(family_flat)) == 6360 and set(family_flat) == set(wall), '60_family_complete_partition')
for item in families:
    check(item['image_count'] == len(item['current_file_ids']) and all(roles[fid]['family'] == item['family'] for fid in item['current_file_ids']), 'family_image_membership', item['family'])
    check(item['relationship'] == 'CURRENT_DROPBOX_FAMILY_SCOPE_NOT_EXACT_VARIANT_ASSIGNMENT', 'family_is_not_variant_assignment', item['family'])

review = read(RUN / 'product-image-association-review.json')
old_lists = read(RUN / 'per-product-image-lists.json')
index = read(RUN / 'product-reader-index.json')
nav = read(RUN / 'product-family-navigation.json')
check(set(review) == set(nav) == {x['product_id'] for x in index} == set(products), '188_product_reader_and_navigation_sets')
check(set(products) - set(old_lists) == {'BSI-04D6E8690F30'} and review['BSI-04D6E8690F30'] == [], 'legacy_FFL1_empty_images_explicit')
total = 0
option_wall = set()
historical = []
for item in index:
    pid = item['product_id']; rows = review[pid]; total += len(rows)
    check(len(rows) == item['image_count'] == len({x['file_id'] for x in rows}), 'unique_per_option_images', pid)
    check({x['file_id'] for x in rows} == {x['file_id'] for x in old_lists.get(pid, [])}, 'retained_option_image_membership', pid)
    check(all(x['association_qualification'] for x in rows), 'all_image_association_qualifications', pid)
    option_wall.update(x['file_id'] for x in rows if x['file_id'] in wall)
    historical.extend((pid, x) for x in rows if x['native_status'] == 'HISTORICAL_REFERENCE_ABSENT_FROM_CURRENT_WALL_INVENTORY')
unassigned = read(RUN / 'current-images-without-option-scope.json')
check(total == 10846 and len(historical) == 14, 'retained_image_reference_and_historical_counts')
check(len(unassigned) == 625 and {x['file_id'] for x in unassigned} == set(wall) - option_wall, '625_unassigned_current_images_retained')
check(all(x['file_id'] in set(family_flat) and 'NO_EXISTING_OPTION_SCOPE_EDGE' in x['disposition'] for x in unassigned), 'unassigned_images_kept_without_new_identity')

cross = read(ROOT / 'reports/local-platform-crosswalk-corrected-20261024-root/local-platform-crosswalk.json')
sq_records = cross['squarespace_source_records']; sh_records = cross['local_shopify_records']
check(records('local_squarespace_records') == sq_records, 'R5_80_full_Squarespace_records')
check(records('local_shopify_products') == sh_records, 'R5_136_full_Shopify_records')
check(records('local_shopify_variants') == [v for p in sh_records for v in p['variants']], 'R5_160_full_Shopify_variant_records')
check(records('local_shopify_media') == [v for p in sh_records for v in p['full_product_gallery']], 'R5_416_full_Shopify_media_records')
check(len(cross['matched_local_source_offer_refs']) == 37 and len(records('source_product_links')) == 260, 'qualified_platform_source_link_counts')
gallery = read(RUN / 'source-gallery-review.json')
gallery_map = {x['gallery_entry_id']: x for x in gallery}
expected_sq = [(p['offer_ref'], x['gallery_index'] + 1, x['url']) for p in sq_records for x in p['local_squarespace_gallery_record']['ordered_gallery']]
check(len(gallery) == 445 and sorted((x['offer_ref'], x['gallery_order'], x['source_url']) for x in gallery) == sorted(expected_sq), '445_ordered_Squarespace_gallery_occurrences')
check(records('source_gallery') == gallery, 'sqlite_full_Squarespace_gallery_rows')
check(sum(bool(x['supported_photo_file_ids']) for x in gallery) == 416, '416_qualified_source_frames')
for item in gallery:
    check(item['variant_specific_assignment_certified'] is False and item['visual_role'] in {'individual', 'rear', 'detail', 'group_context', 'installation'}, 'source_role_without_variant_promotion', item['gallery_entry_id'])
wall_gallery = [x for x in gallery if x['offer_ref'] == 'O001']
check(len(wall_gallery) == 24 and sum(bool(x['supported_photo_file_ids']) for x in wall_gallery) == 20, 'Wall_20_supported_4_unresolved_preserved')
photo_edges = read(RUN / 'source-photo-correspondences.json')
check(records('source_photo_correspondences') == photo_edges and len(photo_edges) == 642, 'sqlite_642_full_qualified_photo_edges')
for edge in photo_edges:
    src = gallery_map.get(edge['gallery_entry_id'], {})
    check(edge['source_url'] == src.get('source_url') and edge['offer_ref'] == src.get('offer_ref'), 'photo_edge_exact_source_membership', edge['gallery_entry_id'])
    check(edge['source_to_option_assignment_automatically_created'] is False, 'no_photo_to_variant_auto_assignment', edge['gallery_entry_id'])
    check(edge['file_id'] in wall and edge['image_url'] == wall[edge['file_id']]['image_url'] and edge['folder_url'] == wall[edge['file_id']]['folder_url'], 'photo_edge_actual_current_navigation', edge['file_id'])
shopify = read(RUN / 'local-shopify-gallery-review.json')
provider_shopify = read(ROOT / 'reports/shopify-wall-gallery-review-20261024-root/shopify-wall-gallery-visual-review.json')
check(shopify == provider_shopify, '117_review_reused_without_changes')
sh_rows = shopify['records']
check(len(sh_rows) == 117 and records('local_shopify_gallery_reviews') == sh_rows, 'sqlite_117_full_Shopify_reviews')
scene_ids = {x['review_id'] for x in sh_rows if not x['native_photo_correspondence']}
check(scene_ids == {'S016', 'S021', 'S022'}, 'three_scene_only_Shopify_frames')
for item in sh_rows:
    check(all(item[k] is False for k in ['exact_encoded_original_bytes_or_pixel_identity_claimed', 'new_physical_specification_or_cast_identity_verified', 'variant_specific_assignment_certified', 'stock_price_or_configuration_field_transfer', 'installation_creation_origin_newly_verified', 'new_component_or_finish_record_created', 'canonical_binding_applied']), 'all_Shopify_proof_boundaries', item['review_id'])
source_index = read(RUN / 'source-gallery-reader-index.json')
check(len(source_index) == 81 and {x['offer_ref'] for x in source_index} == {x['offer_ref'] for x in records('local_source_offers')}, '81_source_reader_pages')

remaining = read(RUN / 'remaining-work.json')
check(remaining['held_identities']['frozen_fish_legacy_vs_FFS2'] == 'EXACT_PAIR_OWNER_ANSWER_PENDING_IN_EXISTING_PROMPT' and remaining['held_identities']['owner_thread'] == '01a16dbc-036d-7003-8ebd-34cb76b5b667', 'owned_FFL1_question_stays_pending')
check(remaining['deferred_photography']['installation_gaps'] == 22 and remaining['deferred_photography']['series_gaps'] == 1 and remaining['deferred_photography']['status'] == 'OWNER_DEFERRED_UNCHANGED', 'deferred_22_plus_1_photo_requests')
check(len(remaining['squarespace_exact_photo_unresolved']) == 29 and len(remaining['shopify_exact_photo_unresolved']) == 3 and len(remaining['four_uncertain_native_roles']) == 4, '29_3_4_uncertainties_retained')
check(len(remaining['options_without_existing_source_component_association']) == 65 and remaining['no_platform_publication'] is True and remaining['photo_correspondence_uncertainty_is_not_proof_of_absence'] is True, 'unpaired_and_absence_boundaries')
check(remaining['canonical_release']['this_packet_selected_reference_IDs_use_start_baseline'] is True, 'two_Wall_replacements_remain_Main_owned')

class Page(HTMLParser):
    def __init__(self, path):
        super().__init__(convert_charrefs=True)
        self.path = path; self.ids = []; self.targets = []; self.links = set()
        self.feed(path.read_text())
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if 'id' in a: self.ids.append(a['id'])
        for key in ('href', 'src'):
            if a.get(key):
                self.targets.append(a[key]); self.links.add(a[key])

pages = {p.resolve(): Page(p) for p in RUN.rglob('*.html')}
check(len(pages) == 333, '333_total_reader_pages')
for p, page in pages.items():
    check(len(page.ids) == len(set(page.ids)), 'unique_HTML_anchors', p)
    for link in page.targets:
        u = urlsplit(link)
        if u.scheme in {'https', 'http', 'mailto', 'data', 'javascript'} or u.netloc:
            continue
        target = Path(unquote(u.path)) if u.path.startswith('/') else p.parent / unquote(u.path)
        target = (target if u.path else p).resolve()
        check(target.exists(), 'local_HTML_image_and_folder_target_exists', str(p) + ' -> ' + link)
        if u.fragment and target.suffix == '.html' and target.exists():
            target_page = pages.get(target) or Page(target)
            check(unquote(u.fragment) in target_page.ids, 'local_HTML_fragment_exists', str(p) + ' -> ' + link)
for item in index:
    p = (RUN / item['page']).resolve(); page = pages[p]
    text = p.read_text()
    check(item['product_id'] in text and item['name'] in __import__('html').unescape(text), 'per_product_reader_owner', item['product_id'])
    for row in review[item['product_id']]:
        if row['native_status'].startswith('CURRENT_NATIVE_FILE_AND_ACTUAL_PARENT_VERIFIED'):
            check(row['image_url'] in page.links and row['folder_url'] in page.links, 'product_current_image_folder_links_present', row['file_id'])
        elif row['native_status'] == 'HISTORICAL_REFERENCE_ABSENT_FROM_CURRENT_WALL_INVENTORY':
            check(row['image_url'] not in page.links, 'historical_unavailable_image_not_live_link', row['file_id'])
for item in families:
    page = pages[(RUN / item['page']).resolve()]
    for fid in item['current_file_ids']:
        check(roles[fid]['image_url'] in page.links and roles[fid]['folder_url'] in page.links, 'every_family_image_and_actual_folder_link', fid)
for item in source_index:
    check((RUN / item['page']).resolve() in pages, 'source_page_exists', item['offer_ref'])
db.close()
check(sha(db_path, fresh=True) == seal['files'][str(db_path)], 'sqlite_snapshot_unchanged_after_read')
for item in protected:
    check(sha(item['path'], fresh=True) == item['sha256'], 'protected_baseline_end', item['path'])
check(sha(seal_path, fresh=True) == SEAL_SHA and sha(closing_path, fresh=True) == CLOSING_SHA, 'sealed_inputs_unchanged_at_end')

result = {
    'status': 'PASS' if not failures else 'FAIL',
    'checked_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'frozen_B_handoff': {'path': str(seal_path), 'sha256': SEAL_SHA},
    'additive_directory_closing_receipt': {'path': str(closing_path), 'sha256': CLOSING_SHA},
    'baseline_pointer_sha256': baseline['pointer_sha256'],
    'checks_passed': sum(counts.values()) - len(failures),
    'checks_total': sum(counts.values()), 'check_categories': dict(counts),
    'failures': failures,
    'counts': {'catalogue_option_records': len(products), 'current_wall_images': len(roles), 'families': len(families), 'SQ_gallery_occurrences': len(gallery), 'qualified_SQ_frames': 416, 'Shopify_review_occurrences': len(sh_rows), 'qualified_Shopify_frames': 114, 'reader_HTML_pages': len(pages), 'option_image_references': total, 'family_scope_only_files': len(unassigned)},
    'scope': 'Frozen handoff integrity, original full-field identity, navigation and reader/SQLite integration. Earlier sealed visual findings are preserved, not a second visual re-review or new market/account observation.',
    'live_calls': 0, 'native_writes': 0, 'canonical_writes': 0,
    'database_opened_read_only_immutable': True,
    'two_Wall_selected_reference_replacements_not_applied_by_this_QA': True,
    'owner_question_reissued': False,
    'input_hashes': bound,
}
result_path = OUT / 'final-handoff-independent-readback.json'
result_path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n')
print(json.dumps({k: v for k, v in result.items() if k not in {'input_hashes', 'check_categories', 'scope'}}, ensure_ascii=False))
