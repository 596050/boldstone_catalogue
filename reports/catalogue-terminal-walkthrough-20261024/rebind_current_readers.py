"""Rebind unchanged source-review projections after a verified publication."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

H = Path(__file__).resolve().parent
B = H.parents[1] / 'sculpture-catalogue'
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
write = lambda p, value: Path(p).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
pointer = read(B / 'current-master.json')
release = B / pointer['publication_receipt']
receipt = read(release)
assert receipt['status'] == 'PASS_PUBLISHED_AND_READ_BACK'
assert sha(B / pointer['register']) == pointer['register_sha256'] == receipt['register_sha256']
assert sha(B / pointer['workbook']) == pointer['workbook_sha256'] == receipt['workbook_sha256']
g = read(B / pointer['register'])
ready_path = H / 'ready-source-triage.json'
ready = read(ready_path)
review_path = Path(ready['review']).with_name('next-evidence-review.json')
review = read(review_path)
assert sha(ready['review']) == ready['review_sha256']
assert sha(ready['sealed_handoff']) == ready['sealed_handoff_sha256']
baseline_path = Path(review['baseline']['register']['path'])
assert sha(baseline_path) == review['baseline']['register']['sha256']
old = read(baseline_path)
before = {x['product_id']: x for x in old['options']}
after = {x['product_id']: x for x in g['options']}
ids = sorted({x['product_id'] for row in review['rows'] for x in row['related_current_options']})
assert len(review['rows']) == 43 and len(ids) == 48
assert all(before[i] == after[i] for i in ids)
assert sum(len(after[i]['master_fields']) for i in ids) == 288
assert g['current_authenticated_squarespace_inventory_observation'] == old['current_authenticated_squarespace_inventory_observation']
assert [x['source_offer'] for x in g['source_offer_edges']] == [x['source_offer'] for x in old['source_offer_edges']]
assert [x['members'] for x in g['source_offer_edges']] == [x['members'] for x in old['source_offer_edges']]
for row in review['rows']:
    for projected in row['related_current_options']:
        for key in ['product_id', 'name', 'image_url', 'folder_url', 'file_id', 'folder_id', 'master_fields']:
            assert projected[key] == after[projected['product_id']][key], (row['offer_ref'], key)
attestation = {
    'status': 'PASS_UNCHANGED_SOURCE_REVIEW_REBOUND_TO_CURRENT_PUBLICATION',
    'recorded_utc': datetime.now(timezone.utc).isoformat(),
    'source_review': str(review_path), 'source_review_sha256': sha(review_path),
    'historical_review_baseline': review['baseline'],
    'current_pointer_sha256': sha(B / 'current-master.json'),
    'current_register_sha256': pointer['register_sha256'],
    'current_workbook_sha256': pointer['workbook_sha256'],
    'publication_receipt': str(release), 'publication_receipt_sha256': sha(release),
    'source_rows': 43, 'whole_option_objects_compared': 48, 'full_qualified_field_objects_compared': 288,
    'all_related_option_links_and_ids_unchanged': True,
    'raw_source_observations_and_original_bom_unchanged': True,
    'new_matches_or_physical_verifications': 0,
}
attestation_path = H / 'source-triage-current-publication-attestation.json'
write(attestation_path, attestation)
snapshot = H / 'ready-source-triage.before-combined-publication.json'
if not snapshot.exists():
    snapshot.write_bytes(ready_path.read_bytes())
ready.update(
    baseline_pointer_sha256=sha(B / 'current-master.json'),
    baseline_register_sha256=pointer['register_sha256'],
    baseline_workbook_sha256=pointer['workbook_sha256'],
    current_publication_attestation=str(attestation_path),
    current_publication_attestation_sha256=sha(attestation_path),
)
write(ready_path, ready)
queue_path = H / 'queued-native-case-corrections.json'
queue = read(queue_path)
queue_snapshot = H / 'queued-native-case-corrections.before-combined-publication.json'
if not queue_snapshot.exists():
    queue_snapshot.write_bytes(queue_path.read_bytes())
assert pointer['latest_current_url_case_normalization']['corrected_options'] == queue['option_count'] == 6
queue.update(
    status='APPLIED_AND_PUBLISHED_VERIFIED',
    publication_receipt=str(release), publication_receipt_sha256=sha(release),
    current_register_sha256=pointer['register_sha256'], current_workbook_sha256=pointer['workbook_sha256'],
    disposition='Six guarded current URL pairs are published; all stable IDs and historical source columns retained.',
)
write(queue_path, queue)
print(json.dumps({'status': attestation['status'], 'source_rows': 43, 'option_objects': 48, 'field_objects': 288, 'case_queue': queue['status']}))
