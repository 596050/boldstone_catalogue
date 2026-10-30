"""Independently compare the new reader to its frozen predecessor and master."""
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import sqlite3

H = Path(__file__).resolve().parent
B = H.parents[2]
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
run = Path(read(H / 'current-integration.json')['run'])
projection = read(run / 'publication-rebase.json')
oldrun = Path(projection['previous_published_reader'])
checks = Counter()
def check(value, category):
    assert value, category
    checks[category] += 1

check(read(run / 'integrated-reader-independent-readback.json')['status'] == 'PASS', 'full_reader_navigation_passed')
check(sha(B / 'current-master.json') == projection['published_pointer_sha256'], 'published_pointer_unchanged')
pointer = read(B / 'current-master.json')
check(sha(B / pointer['register']) == pointer['register_sha256'], 'published_register_hash')
check(sha(B / pointer['workbook']) == pointer['workbook_sha256'], 'published_workbook_hash')
db = sqlite3.connect('file:' + str(run / 'complete-image-platform-register.sqlite') + '?mode=ro', uri=True)
db.execute('ATTACH DATABASE ? AS frozen', ('file:' + str(oldrun / 'complete-image-platform-register.sqlite') + '?mode=ro',))
tables = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")]
for table in tables:
    if table in {'products', 'associations', 'metadata'}:
        continue
    check(db.execute('SELECT count(*) FROM (SELECT * FROM main."' + table + '" EXCEPT SELECT * FROM frozen."' + table + '")').fetchone()[0] == 0, 'frozen_table_no_new_rows:' + table)
    check(db.execute('SELECT count(*) FROM (SELECT * FROM frozen."' + table + '" EXCEPT SELECT * FROM main."' + table + '")').fetchone()[0] == 0, 'frozen_table_no_lost_rows:' + table)
check(db.execute('SELECT count(*) FROM (SELECT * FROM frozen.associations EXCEPT SELECT * FROM main.associations)').fetchone()[0] == 0, 'all_historical_association_rows_preserved')
check(db.execute('SELECT count(*) FROM (SELECT * FROM main.associations EXCEPT SELECT * FROM frozen.associations)').fetchone()[0] == 1, 'one_qualified_design_association_added')
check(db.execute('SELECT count(*) FROM source_product_links').fetchone()[0] == 260, 'no_selling_record_edge_inheritance')
old = {pid: json.loads(blob) for pid, blob in db.execute('SELECT product_id,record_json FROM frozen.products')}
products = {pid: json.loads(blob) for pid, blob in db.execute('SELECT product_id,record_json FROM main.products')}
for pid, name, blob in db.execute('SELECT product_id,name,record_json FROM main.products'):
    check(name == json.loads(blob)['name'], 'sql_product_name_matches_record')
    for key in ['file_id', 'folder_id', 'image_url', 'folder_url', 'context_file_id', 'context_folder_id']:
        check(products[pid].get(key) == old[pid].get(key), 'selected_photo_binding_unchanged')
ffid = 'BSI-04D6E8690F30'
ff = products[ffid]
check(not ff.get('file_id'), 'legacy_primary_remains_unselected')
check(ff['current_owner_identity_resolution']['status'] == 'OWNER_CONFIRMED_SAME_RELIEF_DESIGN', 'owner_design_status')
check(ff['current_owner_identity_resolution']['same_design_as_option_id'] == 'BSI-FE10273D3655', 'exact_owner_design_pair')
row = db.execute('SELECT product_id,file_id,record_json FROM associations WHERE status=?', ('OWNER_CONFIRMED_SHARED_DESIGN_REFERENCE_ONLY',)).fetchone()
check(row[:2] == (ffid, 'id:cnqzTNngPVsAAAAAAAyk9A'), 'exact_shared_design_photo')
check(json.loads(row[2])['evidence'][0]['sha256'] == pointer['register_sha256'], 'design_reference_bound_to_publication')
expected = {'BSI-CCB6CA396E9C': 'Pale Blue Marbled', 'BSI-22DA74B2107E': 'Azure Blue and White Marbled', 'BSI-1B20DCA291BB': 'Brass with World Colours'}
for pid, name in expected.items():
    product = products[pid]
    check(product['owner_confirmed_pattern_name'] == name, 'exact_owner_pattern_name')
    check(product['master_fields'] == old[pid]['master_fields'], 'six_wall_circle_field_objects_unchanged')
    check(product['current_owner_pattern_resolution']['native_pattern_or_variant_id_assigned'] is None, 'no_native_variant_inferred')
    page = (run / 'products' / (pid + '.html')).read_text()
    check('<h1>Wall Circle — ' + name + '</h1>' in page, 'owner_name_in_product_heading')
    check('Owner-confirmed pattern name: <strong>' + name + '</strong>' in page, 'owner_name_notice_visible')
ffpage = (run / 'products' / (ffid + '.html')).read_text()
for text in ['The design question is resolved', 'Owner-confirmed shared-design reference', '../source-galleries/O049.html', '../source-galleries/O063.html', '../source-galleries/SH-DRAFT.html']:
    check(text in ffpage, 'shared_design_navigation_visible')
ledger = read(run / 'product-image-association-review.json')
designrows = [r for r in ledger[ffid] if r['review_disposition'] == 'owner_design']
check(len(designrows) == 1, 'one_shared_design_ledger_row')
check(designrows[0]['file_id'] == 'id:cnqzTNngPVsAAAAAAAyk9A', 'shared_design_ledger_exact_image')
check(not any(r['review_disposition'] == 'selected' for r in ledger[ffid]), 'no_legacy_primary_promotion')
remaining = read(run / 'remaining-work.json')
check(remaining['held_identities']['owner_questions_remaining'] == [], 'no_owner_questions_pending')
check(remaining['deferred_photography'] == read(oldrun / 'remaining-work.json')['deferred_photography'], 'photography_deferrals_unchanged')
check(remaining['deferred_photography']['installation_gaps'] == 22 and remaining['deferred_photography']['series_gaps'] == 1, 'exact_deferred_counts')
gap = read(run / 'source-association-review/all-65-case-dispositions.json')
check(len(gap) == 65, 'all_original_gap_cases_retained')
check(not any(r['disposition'] == 'OWNER_IDENTITY_QUESTION_PENDING' for r in gap), 'old_pending_case_resolved')
check(next(r for r in gap if r['product_id'] == ffid)['disposition'] == 'OWNER_CONFIRMED_SHARED_DESIGN_EXACT_LEGACY_VARIANT_UNASSIGNED', 'design_vs_sale_scope_retained')
check(read(run / 'summary.json')['held_identity_answers_complete'] is True, 'summary_answers_complete')
for name, digest in projection['unchanged_source_proof_files'].items():
    check(sha(run / name) == digest == sha(oldrun / name), 'source_photo_proof_unchanged')
check(sha(B / 'current-master.json') == projection['published_pointer_sha256'], 'final_pointer_stable')
result = {'status': 'PASS', 'checked_utc': datetime.now(timezone.utc).isoformat(), 'checks_passed': sum(checks.values()), 'check_categories': dict(checks), 'published_pointer_sha256': projection['published_pointer_sha256'], 'published_register_sha256': pointer['register_sha256'], 'published_workbook_sha256': pointer['workbook_sha256'], 'four_owner_decisions_projected': True, 'owner_questions_remaining': 0, 'selected_photo_bindings_unchanged': True, 'new_exact_variant_assignments': 0, 'all_frozen_source_tables_preserved': True, 'readback_scope': 'Full reader verifier plus independent table, owner-decision, visible label, shared-design and deferred-photography checks.'}
(run / 'owner-identity-projection-verification.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result, indent=2))
