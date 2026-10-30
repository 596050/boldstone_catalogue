"""Read saved platform ties and protect shared/Bronze records from retirement."""
from pathlib import Path
import hashlib
import json
import sqlite3

H = Path(__file__).resolve().parent
B = H.parents[2]
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
p = read(H / 'inputs/pointer.json')
g = read(H / 'inputs/register.json')
oid = 'BSI-B0D0CCA7E318'
o = next(o for o in g['options'] if o['product_id'] == oid)
treatment = next(o for o in read(g['current_listing_treatment_plan']['register'])['options'] if o['product_id'] == oid)
assert not treatment['selected_squarespace_product_id'] and not treatment['selected_squarespace_variant_id']
assert not treatment['selected_local_shopify_handle'] and not treatment['selected_existing_source_sku']
db = (B / p['current_published_gallery_projection']['path']).parent / 'complete-image-platform-register.sqlite'
c = sqlite3.connect('file:' + str(db) + '?mode=ro', uri=True)
c.row_factory = sqlite3.Row
ties = [dict(r) for r in c.execute('SELECT offer_ref,product_id,relationship FROM source_product_links WHERE product_id=?', (oid,))]
assert {r['offer_ref'] for r in ties} <= {'O069'}
offer_row = c.execute("SELECT * FROM local_source_offers WHERE offer_ref='O069'").fetchone()
offer = json.loads(offer_row['record_json'])
protected = {'offer_ref': 'O069', 'platform': 'Squarespace', **offer['squarespace_native_tuple'],
    'title': offer['local_squarespace_gallery_record']['title']}
assert protected['native_product_id'] == '6aa01abf4b08934e6b0d3d93'
assert 'Bronze' in protected['title']
counts = {t: c.execute('SELECT COUNT(*) FROM ' + t).fetchone()[0] for t in ['local_squarespace_records', 'local_shopify_products', 'local_shopify_variants']}
text_candidates = []
for table, id_field in [('local_squarespace_records', 'native_product_id'), ('local_shopify_products', 'handle')]:
    for r in c.execute('SELECT * FROM ' + table):
        text = r['record_json'].casefold()
        if 'acanthus' in text and 'black' in text and 'white' in text:
            rec = json.loads(r['record_json'])
            text_candidates.append({'table': table, 'record_id': r[id_field],
                'text_candidate_only_not_exact_finish_identity': True,
                'top_level_keys': list(rec)})
c.close()
report = {'status': 'NO_EXACT_SAVED_PLATFORM_DELETE_TARGET', 'option_id': oid,
    'source_gallery_path': str(db), 'source_gallery_sha256': sha(db), 'saved_source_counts_checked': counts,
    'selected_exact_squarespace_product_id': '', 'selected_exact_squarespace_variant_id': '',
    'selected_exact_shopify_handle': '', 'selected_exact_source_sku': '',
    'related_source_edges_retained_as_history': ties, 'protected_bronze_record': protected,
    'text_only_candidates': text_candidates,
    'local_proposed_handle_to_remove_from_active_outputs': treatment['proposed_handle'],
    'local_proposed_sku_to_remove_from_active_outputs': treatment['proposed_listing_sku'],
    'scope': 'Saved source and local-draft evidence only. No exact White and Black native listing/variant ID is bound. O069 is a Bronze family/component record and must remain. Proposed identifiers are local plans, not observed live platform records.',
    'live_platform_access': 'No connected Squarespace/Shopify mutation tools; live listing deletion not verified or performed.',
    'platform_delete_requests': 0, 'native_mutations': 0}
(H / 'platform-scope-audit.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({k: v for k, v in report.items() if k not in ['related_source_edges_retained_as_history', 'text_only_candidates']}, indent=2))
