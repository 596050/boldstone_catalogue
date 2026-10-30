"""Attach immutable completed-gallery evidence without changing option fields."""
from datetime import datetime, timezone
import copy
import hashlib
import json
from pathlib import Path

H = Path(__file__).resolve().parent
B = H.parents[2]
ROOT = B.parent
G = B / 'components/parallel-reviews/all-record-image-matching-20261024-B/integrations/20261024T225748917419Z'
Q = B / 'components/parallel-reviews/all-record-image-matching-qa-01a16dbc-20261024'
N = ROOT / 'reports/dropbox-wall-complete-role-review-20261024T214349Z'
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
write = lambda p, v: Path(p).write_text(json.dumps(v, ensure_ascii=False, indent=2)+'\n')
assert sha(G/'sealed-handoff.json') == 'a93db7e5584a4cc356adf03e633ee50efdff92bce82206f65dfb75b9a2347450'
assert sha(Q/'sealed-final-handoff-qa.json') == 'fb228660cba796f27519453eb5791fbebb990a4bbf9206d5ca024ddebcf828f2'
qa = read(Q/'sealed-final-handoff-qa.json')
assert qa['checks_passed'] == qa['checks_total'] == 95016
assert all(sha(path) == expected for path, expected in qa['files'].items())
assert sha(N/'complete-6360-role-review-seal.json') == 'ad667eec400f5cc97bf320aa1fc68bb41e65cac75242b47ba28f9f5dd190d26e'
summary = read(G/'summary.json')
gallery = {'status': 'COMPLETE_REVIEW_WITH_QUALIFIED_ASSOCIATIONS_AND_EXPLICIT_UNCERTAINTIES',
    'recorded_utc': datetime.now(timezone.utc).isoformat(),
    'frozen_source_baseline_pointer_sha256': summary['baseline_pointer_sha256'],
    'source_gallery_handoff': {'path': str(G/'sealed-handoff.json'), 'sha256': sha(G/'sealed-handoff.json')},
    'independent_source_gallery_qa': {'path': str(Q/'sealed-final-handoff-qa.json'), 'sha256': sha(Q/'sealed-final-handoff-qa.json'), 'checks_passed': 95016},
    'complete_native_roles': {'path': str(N/'complete-6360-role-review-seal.json'), 'sha256': sha(N/'complete-6360-role-review-seal.json'), 'current_files': 6360, 'families': 60},
    'readers': {key: str(G/name) for key, name in [('products','product-images.html'), ('platform_galleries','source-galleries.html'), ('families','family-images.html')]},
    'native_complete_reader': str(N/'complete-review.html'),
    'remaining_work': {'path': str(G/'remaining-work.json'), 'sha256': sha(G/'remaining-work.json')},
    'counts': {'active_options': 188, 'current_wall_images_reviewed': 6360, 'current_families_reviewed': 60,
        'squarespace_gallery_occurrences_reviewed': 445, 'shopify_gallery_occurrences_reviewed': 117,
        'squarespace_photo_correspondence_frames': 416, 'squarespace_exact_photo_uncertainties': 29,
        'shopify_photo_correspondence_frames': 114, 'shopify_exact_photo_uncertainties': 3,
        'native_roles_retained_uncertain': 4, 'active_options_without_existing_platform_source_association': 65,
        'current_files_retained_at_family_scope_without_existing_exact_option_edge': 625,
        'exact_nonempty_shared_SKU_local_platform_source_pairs': 37,
        'squarespace_sources_without_nonempty_local_Shopify_SKU_match': 43,
        'blank_SKU_local_Shopify_wall_drafts': 1},
    'scope': 'Visual roles and qualified photo/source/option associations. The frozen baseline readers preserve the old selected references; current canonical selected-reference replacements are separately recorded in this release. Current reader projection follows publication. Source product galleries do not certify exact variant images, measurements, physical material, fitted fixing, stock, or new price/availability facts.',
    'new_exact_platform_variant_assignments': 0, 'new_physical_verifications': 0, 'native_or_platform_writes': 0}
before_path = H/'inputs/navigation-candidate-before-gallery-metadata.json'
if not before_path.exists():
    before_path.write_bytes((H/'canonical-master-register.json').read_bytes())
old = read(before_path)
g = read(H/'canonical-master-register.json')
assert g['options'] == old['options']
assert g['original_review_specification_assertions'] == old['original_review_specification_assertions']
g['current_complete_gallery_mapping'] = gallery
g['latest_complete_wall_navigation_candidate']['full_gallery_matching_handoff'] = gallery['source_gallery_handoff']
g['latest_complete_wall_navigation_candidate']['status'] = 'VERIFIED_CURRENT_NAVIGATION_REFERENCE_REFRESH'
audit = read(H/'image-coverage-current.json')
audit['current_complete_gallery_mapping'] = gallery
audit['latest_complete_wall_navigation_candidate'] = copy.deepcopy(g['latest_complete_wall_navigation_candidate'])
write(H/'canonical-master-register.json', g)
write(H/'image-coverage-current.json', audit)
write(H/'complete-gallery-evidence-reference.json', gallery)
write(H/'gallery-metadata-addendum-verification.json', {'status': 'PASS_METADATA_ONLY_ADDENDUM',
    'preceding_candidate_register_sha256': sha(before_path), 'final_candidate_register_sha256': sha(H/'canonical-master-register.json'),
    'all189_options_and1134_fields_unchanged_from_independently_checked_navigation_candidate': g['options'] == old['options'],
    'all_original_source_assertions_unchanged': True, 'new_gallery_counts': gallery['counts'],
    'independent_gallery_qa_seal_sha256': sha(Q/'sealed-final-handoff-qa.json'),
    'workbook_sha256': sha(H/'master-workbook.pending')})
write(H/'current-primary-navigation-health.json', {'status': 'TWO_CURRENT_EQUIVALENT_REFERENCES_VERIFIED_WITH_ORIGINAL_HISTORY_RETAINED',
    'recorded_utc': gallery['recorded_utc'], 'current_resolutions': [o['current_primary_navigation'] for o in g['options'] if o['product_id'] in ['BSI-D5A939264C82','BSI-65520F070145']],
    'historical_previous_scope': read(H/'inputs/pointer.before')['current_primary_navigation_health'],
    'same_id_context_URL_refreshes': read(ROOT/'reports/native-navigation-preflight-20261024-root/navigation-import-preflight.json')['selected_context_refreshes'],
    'held_identity_and_all_working_specification_fields_preserved': True, 'native_or_platform_writes': 0})
print(json.dumps({'status':'PASS', 'final_register_sha256':sha(H/'canonical-master-register.json'), 'gallery_qa_checks':95016},indent=2))
