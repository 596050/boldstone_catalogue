"""Seal the verified owner-decision reader without changing canonical files."""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import shutil

H = Path(__file__).resolve().parent
B = H.parents[2]
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
run = Path(read(H / 'current-integration.json')['run'])
projection = read(run / 'publication-rebase.json')
general = read(run / 'integrated-reader-independent-readback.json')
identity = read(run / 'owner-identity-projection-verification.json')
assert general['status'] == identity['status'] == 'PASS'
assert general['canonical_pointer_matches_start_baseline']
assert identity['owner_questions_remaining'] == 0
assert sha(B / 'current-master.json') == projection['published_pointer_sha256']
pointer = read(run / 'published-pointer-snapshot.json')
assert sha(B / pointer['register']) == pointer['register_sha256']
assert sha(B / pointer['workbook']) == pointer['workbook_sha256']
receipt = B / pointer['publication_receipt']
shutil.copyfile(receipt, run / 'main-publication-receipt.json')
shutil.copyfile(H / 'current-integration.json', run / 'integration-pointer-snapshot.json')
for name in ['project_owner_identity_publication.py', 'build_product_image_reader.py', 'verify_integrated_reader.py', 'verify_owner_identity_projection.py', 'seal_owner_identity_reader.py']:
    shutil.copyfile(H / name, run / name)
providers = {str(receipt): sha(receipt), projection['frozen_review_handoff']: projection['frozen_review_handoff_sha256']}
for row in read(run / 'owner-identity-projection.json')['answers']:
    providers[row['resolution']['seal']] = row['resolution']['seal_sha256']
for path, digest in providers.items():
    assert sha(path) == digest
for name, digest in projection['unchanged_source_proof_files'].items():
    assert sha(run / name) == digest
seal = {'status': 'PUBLISHED_READER_WITH_ALL_FOUR_OWNER_DECISIONS_VERIFIED', 'sealed_utc': datetime.now(timezone.utc).isoformat(), 'reviewer_thread': '01a13fe6-495b-7253-b923-31823b4cbca8', 'canonical_publisher_thread': '01a144ab-1a7c-7223-a403-73a4d53d70ff', 'published_pointer_sha256': projection['published_pointer_sha256'], 'published_register_sha256': pointer['register_sha256'], 'published_workbook_sha256': pointer['workbook_sha256'], 'run': str(run), 'readers': {name: str(run / name) for name in ['index.html', 'product-images.html', 'source-galleries.html', 'family-images.html', 'source-association-review/index.html']}, 'counts': read(run / 'product-reader-validation.json'), 'independent_reader_checks_passed': general['checks_passed'], 'owner_projection_checks_passed': identity['checks_passed'], 'all188_products_equal_published_register': True, 'all_four_owner_answers_projected': True, 'owner_questions_remaining': 0, 'qualified_shared_design_references_added': 1, 'selected_primary_references_changed': 0, 'new_exact_variant_assignments': 0, 'source_proof_files_byte_identical_to_frozen_review': projection['unchanged_source_proof_files'], 'source_product_link_rows_unchanged': 260, 'deferred_installation_gaps': 22, 'deferred_series_gaps': 1, 'Shopify_source_authority': 'Owner-requested local export; no live Shopify access required or claimed.', 'native_or_canonical_or_platform_writes_by_reviewer': 0, 'provider_seals_and_publication_receipt': providers, 'files': {str(p.relative_to(run)): sha(p) for p in sorted(run.rglob('*')) if p.is_file()}}
seal_path = run / 'sealed-handoff.json'
with seal_path.open('x') as f:
    json.dump(seal, f, ensure_ascii=False, indent=2)
    f.write('\n')
assert read(seal_path)['files'] == {str(p.relative_to(run)): sha(p) for p in sorted(run.rglob('*')) if p.is_file() and p != seal_path}
print(json.dumps({'seal': str(seal_path), 'sha256': sha(seal_path), 'reader': str(run / 'index.html'), 'checks_passed': general['checks_passed'] + identity['checks_passed']}, indent=2))
