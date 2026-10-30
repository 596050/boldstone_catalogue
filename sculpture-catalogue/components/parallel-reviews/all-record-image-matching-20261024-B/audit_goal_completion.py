"""Check the five original requirements against the final published artifacts.

This produces evidence for the agent's completion decision; it does not set goal
status, invent unsupported matches, change deferrals, or publish anything.
"""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import sqlite3

H = Path(__file__).resolve().parent
B = H.parents[2]
ROOT = H.parents[3]
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
objective = Path('/Users/tprice/.codex/attachments/f2d44019-b587-47ed-82bf-88cae7bd5f1b/pasted-text-1.txt')
assert sha(objective) == 'a33d5502e70d962ce513a4af202affb50b4d9286f6413c6e538a1eff32d98f90'
pointer_path = B / 'current-master.json'
pointer_sha = sha(pointer_path)
pointer = read(pointer_path)
regpath = B / pointer['register']
assert sha(regpath) == pointer['register_sha256']
assert sha(B / pointer['workbook']) == pointer['workbook_sha256']
published = pointer['current_published_gallery_projection']
seal_path = Path(published['path'])
if not seal_path.is_absolute():
    seal_path = B / seal_path
assert sha(seal_path) == published['sha256']
seal = read(seal_path)
assert seal['all_four_owner_answers_projected'] and seal['owner_questions_remaining'] == 0
assert seal['published_register_sha256'] == pointer['register_sha256']
assert seal['published_workbook_sha256'] == pointer['workbook_sha256']
run = Path(seal['run'])
current_navigation = Path(published['current_master_navigation'])
if not current_navigation.is_absolute():
    current_navigation = B / current_navigation
assert run.name in current_navigation.read_text(), 'Stable navigation must lead to the latest reader'
association_review = Path(pointer['current_source_association_scope']['review'])
if not association_review.is_absolute():
    association_review = B / association_review
assert association_review.resolve() == (run / 'source-association-review/index.html').resolve()
for rel, digest in seal['files'].items():
    assert sha(run / rel) == digest, rel
for rel in ['components/reviews/specification_review_progress.json', 'components/checkpoint.json', 'checkpoint.json']:
    assert read(B / rel)['current_master_catalogue'] == pointer, rel
general = read(run / 'integrated-reader-independent-readback.json')
identity = read(run / 'owner-identity-projection-verification.json')
assert general['status'] == identity['status'] == 'PASS'
db = sqlite3.connect('file:' + str(run / 'complete-image-platform-register.sqlite') + '?mode=ro', uri=True)
products = {pid: json.loads(blob) for pid, blob in db.execute('SELECT product_id,record_json FROM products')}
register = read(regpath)
canonical = {p['product_id']: p for p in register['options'] if p['product_id'] in register['active_option_ids']}
assert products == canonical and len(products) == 188
families = read(run / 'family-image-reader-index.json')
assert len(families) == 60 and sum(r['image_count'] for r in families) == 6360
assert {r['product_id'] for r in read(run / 'product-reader-index.json')} == set(products)
assert len(read(run / 'current-images-without-option-scope.json')) == 625
gallery = read(run / 'source-gallery-review.json')
shop = read(run / 'local-shopify-gallery-review.json')['records']
assert len(gallery) == 445 and len(shop) == 117
assert all(r['role_status'] == 'EXPLICIT_VISUAL_ROLE_REVIEW' for r in gallery)
assert sum(bool(r.get('multiple_current_version_review')) for r in gallery) == 15
assert sum(bool(r.get('bounded_crop_comparison_review')) for r in gallery) == 25
assert sum(not r['supported_photo_file_ids'] for r in gallery) == 29
assert {r['review_id'] for r in shop if not r['native_photo_correspondence']} == {'S016', 'S021', 'S022'}
assert all(r['variant_specific_assignment_certified'] is False for r in shop)
assert products['BSI-D5A939264C82']['file_id'] == 'id:cnqzTNngPVsAAAAAAAr1HA'
assert products['BSI-65520F070145']['file_id'] == 'id:cnqzTNngPVsAAAAAAAs9Pw'
assert general['every_current_file_retained']
assert general['current_native_files'] == 6360
assert general['check_categories']['dropbox_html_link_current'] > 35000
assert products['BSI-04D6E8690F30']['current_owner_identity_resolution']['same_design_as_option_id'] == 'BSI-FE10273D3655'
assert products['BSI-04D6E8690F30']['unbound_identity'] is False
for pid, name in {'BSI-CCB6CA396E9C': 'Pale Blue Marbled', 'BSI-22DA74B2107E': 'Azure Blue and White Marbled', 'BSI-1B20DCA291BB': 'Brass with World Colours'}.items():
    assert products[pid]['owner_confirmed_pattern_name'] == name
remaining = read(run / 'remaining-work.json')
assert remaining['held_identities']['owner_questions_remaining'] == []
assert remaining['deferred_photography']['installation_gaps'] == 22
assert remaining['deferred_photography']['series_gaps'] == 1
crosspath = ROOT / 'reports/local-platform-crosswalk-corrected-20261024-root/local-platform-crosswalk.json'
assert sha(crosspath) == 'ef7158d87d6402d1e57b8f209da3ca6421104887da9c8a1e3ea9413b72bce578'
cross = read(crosspath)
csvpath = '/Users/tprice/Downloads/products_export_1 (1).csv'
assert sha(csvpath) == cross['source_manifest'][csvpath]['sha256']
offers = [json.loads(r[0]) for r in db.execute('SELECT record_json FROM local_source_offers')]
pairs = [r for r in offers if r.get('shopify_local_variant')]
assert len(pairs) == 37
for pair in pairs:
    assert pair['platform_record_match'] == 'EXACT_NONEMPTY_SHARED_SKU_IN_REQUESTED_LOCAL_FILES'
    sku = pair['squarespace_native_tuple']['sku_raw']
    assert sku and sku == pair['shopify_local_variant']['sku_raw']
    assert pair['shopify_local_variant']['numeric_product_id'] is None
    assert pair['shopify_local_variant']['numeric_variant_id'] is None
for table, count in [('local_shopify_products', 136), ('local_shopify_variants', 160), ('local_shopify_media', 416), ('source_product_links', 260)]:
    assert db.execute('SELECT count(*) FROM ' + table).fetchone()[0] == count
assert len(cross['unpaired_squarespace_offer_refs']) == 43
assert len(cross['unpaired_shopify_wall_records']) == 1
gap = read(run / 'source-association-review/summary.json')
assert gap['explicit_component_source_edge_gaps'] == 65
assert gap['existing_parent_family_associations'] == 7
assert gap['owner_identity_questions_remaining'] == 0
assert gap['additional_owner_confirmed_shared_design_navigation'] == 1
initial_qa_path = B / 'components/parallel-reviews/owner-identity-final-qa-01a16dbc-20261025/sealed-final-candidate-qa.json'
assert sha(initial_qa_path) == '4d679a794d9a430d71dbee82ee5e30391ab574cf868c573a4abf5d4f62648b4c'
assert read(initial_qa_path)['candidate_register_sha256'] == pointer['register_sha256']
qa_ref = pointer['latest_owner_identity_decision_import']['independent_qa']
qa_path = Path(qa_ref['path'])
if not qa_path.is_absolute():
    qa_path = B / qa_path
assert sha(qa_path) == qa_ref['sha256']
qa = read(qa_path)
assert qa['status'].startswith('PASS') and not qa.get('failures')
assert qa['register_sha256'] == pointer['register_sha256']
assert qa['workbook_sha256'] == pointer['workbook_sha256']
requirements = [
    {'item': 1, 'status': 'COMPLETE_WITH_EXPLICIT_IMAGE_ASSOCIATION_SCOPE', 'evidence': str(run / 'product-image-association-review.json'), 'scope': '188 option lists and all6360 current images in60 linked family libraries.625 family-level images remain accessible without unsupported exact option assignments.'},
    {'item': 2, 'status': 'COMPLETE_FULL_GALLERY_REVIEW', 'evidence': str(run / 'integrated-reader-independent-readback.json'), 'scope': '445Squarespace and117localShopify gallery occurrences reviewed;29and3exact-photo uncertainties, duplicate versions, cross-finish qualifications and4uncertain native roles retained.'},
    {'item': 3, 'status': 'COMPLETE_VERIFIED_NAVIGATION_AND_TWO_REPLACEMENTS', 'evidence': str(run / 'publication-rebase.json'), 'scope': 'All emitted current Dropbox links checked against stable IDs/actual parents; two Wall Circle replacement references current; historical deleted references preserved.'},
    {'item': 4, 'status': 'COMPLETE_FOUR_OWNER_DECISIONS_PUBLISHED', 'evidence': str(run / 'owner-identity-projection.json'), 'scope': 'FFL1/FFS2 same relief design;Pale Blue Marbled;Azure Blue and White Marbled;Brass with World Colours.22installation and1series photography gaps remain owner-deferred.'},
    {'item': 5, 'status': 'COMPLETE_LOCAL_RECORD_MATCHING_WITH_EXPLICIT_NONMATCHES', 'evidence': [str(crosspath), str(run / 'source-association-review/index.html')], 'scope': 'Owner explicitly required local Shopify records instead of live account access.136products/160variant rows/416media rows retained;37exact raw nonempty SKU pairs rechecked;43unpairedSquarespace sources and1blankSKUShopify wall draft retained.65direct component-source gaps are individually disposed, including7parent-family links and1additional qualified shared-design link. No missing native IDs or unsupported exact selling variants invented.'},
]
assert sha(pointer_path) == pointer_sha
receipt = {'status': 'PASS_FIVE_REQUIREMENT_COMPLETION_AUDIT_FOR_OWNER_REQUESTED_LOCAL_RECORD_REVIEW', 'checked_utc': datetime.now(timezone.utc).isoformat(), 'objective_file': str(objective), 'objective_sha256': sha(objective), 'objective_text': objective.read_text(), 'owner_scope_update': 'Use the local Shopify records, stored locally; no live account verification or platform publishing requested.', 'current_pointer_sha256': pointer_sha, 'register_sha256': pointer['register_sha256'], 'workbook_sha256': pointer['workbook_sha256'], 'reader_seal': str(seal_path), 'reader_seal_sha256': sha(seal_path), 'independent_candidate_qa': str(qa_path), 'independent_candidate_qa_sha256': sha(qa_path), 'requirements': requirements, 'owner_identity_questions_remaining': 0, 'unsupported_matches_remain_explicit': True, 'photography_deferrals_unchanged': True, 'pending_required_publication_work': 0, 'canonical_native_or_platform_writes_by_audit': 0, 'previous_goal_turn_classification': 'PROGRESS', 'current_goal_turn_classification': 'PROGRESS'}
out = H / ('goal-completion-audit-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '.json')
with out.open('x') as f:
    json.dump(receipt, f, ensure_ascii=False, indent=2)
    f.write('\n')
print(json.dumps({'audit': str(out), 'sha256': sha(out), 'status': receipt['status'], 'requirements': 5, 'owner_questions_remaining': 0}, indent=2))
