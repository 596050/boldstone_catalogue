"""Seal only the published-navigation projection; preserve the original review."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib, json, shutil

H = Path(__file__).resolve().parent
B = H.parents[2]
ROOT = H.parents[3]
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
run = Path(read(H / 'current-integration.json')['run'])
projection = read(run / 'publication-rebase.json')
verification = read(run / 'integrated-reader-independent-readback.json')
assert verification['status'] == 'PASS'
assert verification['canonical_pointer_matches_start_baseline']
assert sha(B / 'current-master.json') == projection['published_pointer_sha256']
assert sha(projection['published_register_path']) == projection['published_register_sha256']
assert len(projection['selected_reference_replacements']) == 2
for name, digest in projection['unchanged_source_proof_files'].items():
    assert sha(run / name) == digest
pointer = read(run / 'published-pointer-snapshot.json')
receipt_path = B / pointer['publication_receipt']
shutil.copyfile(receipt_path, run / 'main-publication-receipt.json')
shutil.copyfile(H / 'current-integration.json', run / 'integration-pointer-snapshot.json')
for name in ['project_published_navigation.py', 'build_product_image_reader.py', 'verify_integrated_reader.py', 'seal_published_reader.py']:
    shutil.copyfile(H / name, run / name)
providers = [
    Path(projection['frozen_review_handoff']),
    H / 'workbook-publication-qa/final-report-links/sealed-handoff.json',
    B / 'components/parallel-reviews/all-record-image-matching-qa-01a16dbc-20261024/sealed-final-handoff-qa.json',
    ROOT / 'reports/dropbox-wall-complete-role-review-20261024T214349Z/complete-6360-role-review-seal.json',
    ROOT / 'reports/local-platform-crosswalk-corrected-20261024-root/sealed-handoff.json',
    receipt_path,
]
seal_path = run / 'sealed-handoff.json'
assert not seal_path.exists()
seal = {
    'status': 'PUBLISHED_READER_PROJECTED_AND_VERIFIED_WITH_IDENTITY_HOLDS',
    'sealed_utc': datetime.now(timezone.utc).isoformat(),
    'reviewer_thread': '01a13fe6-495b-7253-b923-31823b4cbca8',
    'canonical_publisher_thread': '01a144ab-1a7c-7223-a403-73a4d53d70ff',
    'published_pointer_sha256': projection['published_pointer_sha256'],
    'published_register_sha256': projection['published_register_sha256'],
    'run': str(run),
    'readers': {k: str(run / k) for k in ['index.html', 'product-images.html', 'source-galleries.html', 'family-images.html']},
    'counts': read(run / 'product-reader-validation.json'),
    'independent_reader_checks_passed': verification['checks_passed'],
    'all188_product_objects_equal_published_register': True,
    'historical_selected_references_preserved': True,
    'source_proof_files_byte_identical_to_frozen_review': projection['unchanged_source_proof_files'],
    'held_identities_and_22_installation_and_one_series_deferrals_retained': True,
    'Shopify_source_authority': 'User-requested local export; no live Shopify access required or claimed.',
    'no_new_identity_or_variant_assignments': True,
    'native_or_canonical_or_platform_writes_by_reviewer': 0,
    'provider_seals_and_publication_receipt': {str(p): sha(p) for p in providers},
    'files': {str(p.relative_to(run)): sha(p) for p in sorted(run.rglob('*')) if p.is_file()},
}
seal_path.write_text(json.dumps(seal, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'seal': str(seal_path), 'sha256': sha(seal_path), 'checks_passed': verification['checks_passed'], 'reader': str(run / 'index.html')}, indent=2))
