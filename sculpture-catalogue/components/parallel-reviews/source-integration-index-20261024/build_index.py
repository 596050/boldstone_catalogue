"""Index sealed evidence for the sole catalogue writer; do not rerun source audits."""
import hashlib
import html
import json
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parents[2]
REVIEWS = HERE.parent
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
esc = lambda value: html.escape(str(value), quote=True)
now = datetime.now(timezone.utc).isoformat()


def reference(path, expected=None):
    path = Path(path).resolve()
    digest = sha(path)
    if expected:
        assert digest == expected, str(path)
    return {'path': str(path), 'sha256': digest}


def write(name, value):
    with (HERE / name).open('x', encoding='utf-8') as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
        f.write('\n')


definitions = [
 ('native_inventory_and_rust', 'squarespace-admin-rust-readonly-20261024T010238Z/sealed-handoff.json', 'ae71ce73759ddb9ca906d10b1eed045699eb79375bb7daa426598b91dbe1a7b8', 'Authenticated Squarespace inventory and Rust SKU collision'),
 ('source_extension', 'squarespace-source-extension-20261024T011319Z/sealed-handoff.json', 'a3f9ae9ca5ea1c0caa87340316ce1aa54fa7910d63b91e8ff1a6a79e50ac4af8', 'Two overlap cases, four copy targets and 144 Wall Circle source variants'),
 ('outside_known_source_census', 'squarespace-unrecorded-source-census-20261024T012202Z/sealed-handoff.json', 'd77ec9876fc7df2ba55dec58cfaabef6cd656014fc45586211fb5ee5ad6a0d78', '128 exported products outside the 80 recorded source IDs'),
 ('eighty_source_fields', 'eighty-source-field-readback-20261024T012802Z/sealed-handoff.json', '8bfe9df447c8969d926b60c4aedea197a03b87ad9c15a2a5c0fc1f3e8aa26a26', '80 exact source tuples and 720 source-field comparisons'),
 ('historical_shopify_pairs', 'shopify-access-readiness-20261024T005700Z/fresh-squarespace-comparison/comparison-seal.json', '03bb4fd57450de68b41b65afa2f181d317620d9ecd9039395113c7ca50a112a0', '37 previously documented Squarespace / historical Shopify pairs'),
 ('nine_new_options', 'new-nine-options-source-screening-20261024/completed-handoff.json', '7e8ea01b4e196dc632fbafb6bc1e6b862e8a7f1ef09617c03d84c75c83016569', 'Nine new options screened; exact current variants unresolved'),
 ('shopify_access', 'shopify-access-readiness-20261024T005700Z/readiness-seal.json', 'e47a4005590dc0752f7c9b3ec8ddf31f2025bd1f3e0148f6862c016592f25f40', 'Historical Shopify sources and pending store identity'),
 ('leaf_form_owner_correction', 'leaf-form-owner-repeated-design-20261024T013207Z/sealed-handoff.json', '35bfdb1dd2102c48569353aafdbc1500d3d819f097a5445d41250af5f6f1640c', 'Owner correction: one Leaf Form design depicted twice'),
]
packets = []
payloads = {}
verified_receipt_files = {}
for key, relative, expected, title in definitions:
    path = REVIEWS / relative
    seal_ref = reference(path, expected)
    seal = read(path)
    payloads[key] = seal
    direct = list(seal.get('files', []))
    for name in ['validation', 'comparison', 'page', 'source_packet_seal', 'verification', 'summary', 'queue', 'account_observation']:
        value = seal.get(name)
        if isinstance(value, dict) and 'path' in value and 'sha256' in value:
            direct.append(value)
    for value in direct:
        ref = reference(value['path'], value['sha256'])
        verified_receipt_files[ref['path']] = ref
    if key == 'nine_new_options':
        nested = read(seal['source_packet_seal']['path'])
        for value in nested['files']:
            ref = reference(value['path'], value['sha256'])
            verified_receipt_files[ref['path']] = ref
    page = next((x['path'] for x in direct if str(x['path']).endswith('.html')), None)
    if key == 'nine_new_options':
        page = str(path.parent / 'review.html')
    packets.append({'packet_id': key, 'title': title, 'seal': seal_ref, 'recorded_utc': seal.get('recorded_utc'),
                    'existing_receipt_status': seal.get('status'), 'reported_counts': seal.get('counts'), 'review_page': page,
                    'import_scope': 'Owner interpretation only; historical source records retained' if key == 'leaf_form_owner_correction' else 'Dated source evidence only; no new option identity, physical verification or native-action authority'})

pointer_path = BASE / 'current-master.json'
pointer_ref = reference(pointer_path)
pointer = read(pointer_path)
register_path = BASE / pointer['register']
register_ref = reference(register_path, pointer['register_sha256'])
register = read(register_path)
active_ids = set(register['active_option_ids'])
options = {x['product_id']: x for x in register['options'] if x['product_id'] in active_ids}
offers = {x['offer_ref']: x for x in register['source_offer_edges']}
assert len(options) == 188
fields_path = REVIEWS / 'eighty-source-field-readback-20261024T012802Z/source-field-readback.json'
fields = read(fields_path)
joins = []
for n, entry in enumerate(fields['entries']):
    old = offers[entry['offer_ref']]['source_offer']
    assert old['sq_id'] == entry['native_product_id'] and old['sku'] == entry['sku']
    joins.append({k: entry[k] for k in ['offer_ref', 'native_product_id', 'native_variant_id', 'sku']} | {
        'evidence_locator': '/entries/' + str(n),
        'existing_related_option_ids': sorted(x['product_id'] for x in options.values() if entry['offer_ref'] in x.get('related_platform_offer_refs', [])),
        'association_scope': 'Existing catalogue relation only; source product/variant/SKU presence does not certify these options as exact native sale configurations'})
assert len(joins) == len({x['offer_ref'] for x in joins}) == 80
comparison_path = REVIEWS / 'shopify-access-readiness-20261024T005700Z/fresh-squarespace-comparison/comparison.json'
comparison = read(comparison_path)
shopify_joins = []
for n, row in enumerate(comparison['rows']):
    if row['result'] != 'DOCUMENTED_PAIR_PRESENT_WITH_EXACT_SKU':
        continue
    variant = row['fresh_squarespace_variant']
    shopify_joins.append({'historical_shopify_handle': row['historical_shopify_handle'], 'historical_shopify_variant_key': row['historical_shopify_variant']['variant_key'],
                         'historical_shopify_sku': row['historical_shopify_variant']['sku_raw'], 'documented_offer_refs': row['documented_offer_refs'],
                         'squarespace_product_id': variant['product_id'], 'squarespace_variant_id': variant['variant_id'], 'squarespace_sku': variant['sku_raw'],
                         'evidence_locator': '/rows/' + str(n), 'current_shopify_verified': False})
assert len(shopify_joins) == 37
extension_path = REVIEWS / 'squarespace-source-extension-20261024T011319Z/source-readback-extension.json'
extension = read(extension_path)
join_file = {'schema': 'boldstone.source-join-index.v1', 'squarespace_evidence': reference(fields_path), 'squarespace_retained_offer_joins': joins,
             'historical_shopify_pair_evidence': reference(comparison_path), 'historical_shopify_pairs': shopify_joins,
             'wall_circle_matrix': {'source': reference(extension_path), 'json_pointer': '/wall_circle_source_readback/rows', 'rows': 144,
                                    'scope': 'Native source variants only. Four existing visual assignments remain conditional; no per-variant photograph or physical configuration is certified.'},
             'unpaired_source_offer': {'offer_ref': 'SH-DRAFT', 'scope': 'Retained historical Shopify draft without a recorded Squarespace ID; deferred identity, not a proven absence'},
             'new_source_matches_created': 0}
write('exact-source-join-index.json', join_file)

link_rows = []
for o in sorted(options.values(), key=lambda x: x['name'].casefold()):
    link_rows.append({k: o.get(k) for k in ['product_id', 'name', 'file_id', 'folder_id', 'image_url', 'folder_url', 'photo_coverage']} | {
        'existing_related_platform_offer_refs': o.get('related_platform_offer_refs', []), 'new_live_dropbox_check': False})
link_directory = {'schema': 'boldstone.current-option-link-index.v1', 'source_register': register_ref, 'recorded_utc': now,
                  'scope': 'Current canonical navigation by stable option ID. Source-image binding, photographic origin and physical specifications are not newly verified.', 'rows': link_rows}
write('current-option-links.json', link_directory)
linked_count = sum(bool(x['image_url'] and str(x['image_url']).startswith('https://') and x['folder_url'] and str(x['folder_url']).startswith('https://')) for x in link_rows)
assert linked_count == 187

owner_path = REVIEWS / 'leaf-form-owner-repeated-design-20261024T013207Z/owner-correction.json'
owner = read(owner_path)
assert owner['current_interpretation']['existing_individual_option_id'] in options
assert owner['current_interpretation']['new_design_or_option_count_increment'] == 0
capture = payloads['native_inventory_and_rust']
download = read(next(x['path'] for x in capture['private_external_sources'] if x['path'].endswith('download-receipt.json')))
nine_path = REVIEWS / 'new-nine-options-source-screening-20261024/source-screening.json'
nine = read(nine_path)
raw_shopify = next(x for x in nine['sources'] if x['path'].endswith('products_export_1 (1).csv'))
index = {'schema': 'boldstone.sealed-source-integration-index.v1', 'recorded_utc': now, 'status': 'READY_FOR_MAIN_WRITER_ADDITIVE_INTEGRATION_NOT_IMPORTED',
         'source_master': register_ref, 'pointer_at_index_start': pointer_ref, 'packets': packets,
         'source_clocks': {'squarespace': {'captured_utc': download['recorded_utc'], 'raw_export': capture['raw_export'], 'scope': 'Authenticated Physical product export:208 products/376 variants. No later live refresh performed by this index.'},
                           'historical_squarespace': {'source_register': register_ref, 'scope': 'Existing historical source assertions are retained with their original individual provenance. Current export corroboration is additive.'},
                           'shopify': {'raw_export': raw_shopify, 'scope': comparison['source_time_scope'], 'current_authenticated_inventory_verified': False, 'pending_account_question_repeated': False}},
         'exact_join_index': reference(HERE / 'exact-source-join-index.json'), 'current_option_links': reference(HERE / 'current-option-links.json'),
         'counts': {'ready_packets': len(packets), 'existing_squarespace_offer_joins': 80, 'historical_shopify_pairs': 37, 'wall_circle_source_variant_rows_referenced': 144,
                    'current_option_link_records': 188, 'options_with_image_and_folder_links': 187, 'deferred_unbound_option_records': 1, 'new_identity_matches': 0},
         'current_owner_override': {'decision': reference(owner_path), 'decision_id': owner['decision_id'], 'source_offer_ref': 'O028',
                                    'option_id': owner['current_interpretation']['existing_individual_option_id'], 'image_reference': owner['image_reference'],
                                    'current_interpretation': owner['current_interpretation'], 'precedence': 'Use the new owner interpretation for current catalogue wording; preserve raw historical two-part source text as dated evidence.',
                                    'integration_state': 'Pending separate main-writer import; A owns additional field/cell locator supplement'},
         'unresolved_boundaries': [
             'Rust O051/O067 share one SKU and retain different source prices; accepted working prices and native-action holds remain unchanged.',
             'O028 depicts one Leaf Form design twice. Native pack quantity, per-copy price and duplication method are unconfirmed. Do not divide native price or weight or assign the pair SKU to the individual.',
             'Two overlap cases, four current-copy projections and four conditional Wall Circle assignments retain their specific configuration/identity qualifications.',
             'O006/O007 exact historical source-photo bindings remain unresolved. Current option navigation is not a substitute source-photo binding.',
             'Nine new options remain without an established exact individual variant; the source screen is not proof of native absence.',
             'All current photograph holds, optionality decisions and deferred Frozen Fish identity remain intact. Main owns the current physical walkthrough; B does not repeat it.',
             'No source raw stock setting establishes physical stock, no raw measurement string supplies absent units, and no historical Shopify record establishes current Shopify access.'
         ],
         'integration_boundary': 'Reference sealed source observations and owner correction separately. Main writer alone rebases against its latest register and updates canonical outputs. No native action payload, platform permission, new SKU or identity mapping is supplied.',
         'new_source_audits_performed': 0, 'new_native_or_platform_reads': 0, 'shared_or_native_writes': 0, 'new_owner_questions': 0}
write('source-integration-index.json', index)

def links(row):
    if not str(row.get('image_url', '')).startswith('https://'):
        return 'Deferred identity; no bound photograph'
    return '<a href="' + esc(row['image_url']) + '">Image</a> · <a href="' + esc(row['folder_url']) + '">Folder</a>'

packet_html = ''.join('<tr><td>' + esc(x['title']) + '</td><td><a href="' + esc(x['review_page'] or x['seal']['path']) + '">Review</a></td></tr>' for x in packets)
cases = [('Dune Ripple 1 — Rust', options['BSI-947F365275C5'], 'Two source listings share one SKU. Native prices remain separate from the accepted estimate.'),
         ('Leaf Form — White: one design shown twice', owner['image_reference'], 'Owner correction ready for import; commercial pack quantity remains unconfirmed.'),
         ('Dune Ripple 1 — Verdigris', options['BSI-59530C6155C2'], 'Related source surface versions remain distinct.'),
         ('Moon Water Catcher — White', options['BSI-70C7029C1DB1'], 'The conflicting Concave Moon source keeps its identity qualification.')]
case_html = ''.join('<tr><td>' + esc(name) + '<br><small>' + esc(note) + '</small></td><td>' + links(row) + '</td></tr>' for name, row, note in cases)
all_links = ''.join('<tr id="' + esc(x['product_id']) + '"><td>' + esc(x['name']) + '<br><small>' + esc(x['product_id']) + '</small></td><td>' + links(x) + '</td></tr>' for x in link_rows)
page = '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Catalogue source integration</title><style>body{font:17px system-ui;line-height:1.5;max-width:1050px;margin:36px auto;padding:0 20px;color:#253030;background:#faf9f5}h1,h2{line-height:1.2}table{border-collapse:collapse;width:100%;background:white}td,th{text-align:left;vertical-align:top;padding:13px;border-bottom:1px solid #ddd}td:last-child{min-width:125px}a{color:#075e75}small{color:#536161}details{margin:28px 0}summary{cursor:pointer;font-weight:650}</style></head><body><h1>Catalogue source integration</h1><p>Eight completed evidence packets are indexed for the main catalogue update. This page adds no new identity matches and changes no shop records.</p><p>The Squarespace export was captured on 24 October 2026. Shopify records are historical; current store access remains unresolved. Accepted specifications and photograph holds remain intact.</p><h2>Current cases</h2><table><tr><th>Item and remaining distinction</th><th>References</th></tr>' + case_html + '</table><h2>Completed evidence</h2><table>' + packet_html + '</table><p><a href="exact-source-join-index.json">Exact source-record joins</a> · <a href="source-integration-index.json">Integration index and qualifications</a></p><details><summary>Current image and folder links for all 188 options</summary><p>187 options have linked references; the deferred Frozen Fish record has no bound photograph. Group references retain their existing qualifications.</p><table>' + all_links + '</table></details></body></html>'
with (HERE / 'review.html').open('x', encoding='utf-8') as f:
    f.write(page)
assert read(HERE / 'source-integration-index.json')['counts']['ready_packets'] == 8
assert all(esc(x['image_url']) in page and esc(x['folder_url']) in page for x in link_rows if str(x.get('image_url', '')).startswith('https://'))
validation = {'status': 'PASS_INDEX_REFERENTIAL_INTEGRITY', 'recorded_utc': now, 'seal_receipts_checked': 8,
              'unique_sealed_evidence_files_digest_checked': len(verified_receipt_files), 'exact_source_joins_reference_existing_offer_ids_and_skus': 80,
              'historical_pairs_indexed': 37, 'current_option_link_rows': 188, 'linked_options': 187,
              'owner_correction_separate_from_raw_source_evidence': True, 'new_source_audits': 0, 'shared_or_native_writes': 0,
              'source_register_still_same_bytes': sha(register_path) == register_ref['sha256'], 'pointer_unchanged_during_index_build': sha(pointer_path) == pointer_ref['sha256']}
assert validation['source_register_still_same_bytes']
write('index-verification.json', validation)
seal = {'status': 'SEALED_ADDITIVE_SOURCE_INTEGRATION_INDEX_NOT_IMPORTED', 'recorded_utc': now,
        'files': [reference(HERE / name) for name in ['source-integration-index.json', 'exact-source-join-index.json', 'current-option-links.json', 'review.html', 'index-verification.json', 'build_index.py']],
        'scope': 'Compact reuse index of existing receipts. No source audits repeated, no new identity/absence claims or native action payloads.', 'shared_or_native_writes': 0}
write('sealed-handoff.json', seal)
print(json.dumps({'status': seal['status'], 'packets': len(packets), 'source_joins': len(joins), 'historical_pairs': len(shopify_joins), 'current_option_links': len(link_rows),
                  'seal': str(HERE / 'sealed-handoff.json'), 'sha256': sha(HERE / 'sealed-handoff.json')}))
