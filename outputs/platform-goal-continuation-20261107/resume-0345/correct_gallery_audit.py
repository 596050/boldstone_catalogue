import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

OUT=Path(__file__).parent
BASE=OUT.parent
full=json.loads((OUT/'full-gallery-reconciliation.json').read_text())
records={r['sku']:r for r in full['records']}
old=json.loads((BASE/'resume-0220/ebay-remaining-metadata-queue.json').read_text())
new=json.loads((OUT/'ebay-full-metadata-queue.json').read_text())
assert len(old)==len(new)==52
core=['sku','catalogue_id','native_draft_id','native_url','title','description','price_gbp','width_cm','height_cm','depth_cm','owner_existing_offer_hold']
assert all(all(a[k]==b[k] for k in core) for a,b in zip(old,new))
assert all(len(r['desired_gallery_ids'])==len(set(r['desired_gallery_ids'])) for r in new)
ready=json.loads((BASE/'resume-0041/ebay-draft-receipts.json').read_text())
ready_counts=[dict(sku=r['sku'],native_draft_id=r['native_draft_id'],last_native_photo_count=r['photo_count'],
                   full_selection_count=len(records[r['sku']]['desired_gallery_ids']),
                   count_matches=r['photo_count']==len(records[r['sku']]['desired_gallery_ids']),
                   last_native_verified_utc=r['verified_utc']) for r in ready]
assert all(r['count_matches'] for r in ready_counts)
result=dict(status='PREVIEW_DERIVED_CONCLUSIONS_SUPERSEDED',checked_utc=datetime.now(timezone.utc).isoformat(),
            cause='photo_preview explicitly limits each card section to six images. Its count is full but images is bounded.',
            corrected_sources=['/api/coverage full image_ids','/api/component-overview complete originals and eligibility'],
            complete_source_counts=full['difference_counts'],
            previous_preview_based_changed_selection_count=37,
            actual_changed_selection_count=9,
            original_four_replacements_require_restoration_to_complete_sets=True,
            original_four_complete_targets={'5456776872613':11,'5456776873013':10,'5454762106310':15,'5454762098610':11},
            metadata_values_and_native_bindings_preserved=52,
            earlier_fourteen_source_count_reconciliation=ready_counts,
            earlier_fourteen_saved_native_photo_placements=sum(r['last_native_photo_count'] for r in ready_counts),
            earlier_fourteen_full_source_photo_placements=sum(r['full_selection_count'] for r in ready_counts),
            earlier_fourteen_preview_only_hold_superseded=True,
            legal_acceptance_and_fresh_native_publication_check_still_required=True,
            publication_implied=False,app_writes=0,original_edits=0)
(OUT/'gallery-audit-correction.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k!='earlier_fourteen_source_count_reconciliation'},indent=2))
