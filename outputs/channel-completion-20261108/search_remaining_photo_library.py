"""Read-only search beyond the current Listing choices for 68 flagged products.

Never infer a product/finish match from a family association or filename alone.
Preserves the owner's image purposes and exclusion/reference decisions.
"""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import json
import urllib.request

OUT = Path(__file__).parent
review = json.loads((OUT / 'pinterest-original-resolution-review.json').read_text())
targets = [p for p in review['products'] if not p['higher_resolution_listing_candidates']]
assert len(targets) == 68


def get(path):
    with urllib.request.urlopen('http://127.0.0.1:8767' + path, timeout=90) as response:
        return json.load(response)


coverage = get('/api/coverage')['products']


def examine(previous):
    pid = previous['catalogue_id']
    assert coverage[pid]['primary_listing']['image_id'] == previous['primary']['id'], 'Owner primary changed; stop stale review'
    product = get('/api/products/' + pid)
    listing = set(coverage[pid]['listing']['image_ids'])
    images = {a['id']: a for a in product['images']}
    image_reviews = {r['item_id']: r['data'] for r in product['reviews']
                     if r['kind'] == 'image' and r['product_id'] == pid}
    asset_reviews = {r['item_id']: r['data'] for r in product['reviews']
                     if r['kind'] == 'asset' and r['item_id'] in images}
    primary_folder = images[previous['primary']['id']].get('folder_id')
    candidates, unknown, unknown_product_candidates = [], [], []
    for a in images.values():
        if a['id'] in listing:
            continue
        dims = a.get('original', {}).get('dimensions')
        if not dims:
            unknown.append(a['id'])
            selected = image_reviews.get(a['id'], {})
            tags = set(a.get('types', [])) | set(asset_reviews.get(a['id'], {}).get('types', []))
            uses = set(selected.get('uses', []))
            if (a.get('association', {}).get('tier') in ('accepted', 'folder')
                    and ('product' in tags or not tags and a.get('role') == 'individual')
                    and not tags.intersection({'detail', 'in_situ', 'group', 'workshop'})
                    and not (uses and 'listing' not in uses)
                    and selected.get('decision') not in ('exclude', 'excluded')):
                unknown_product_candidates.append({**{k: a.get(k) for k in ('id', 'name', 'url',
                    'folder_url', 'folder_id', 'original', 'association', 'role', 'product_ids')},
                    'types': sorted(tags), 'owner_review': selected})
            continue
        if not (dims[0] >= 1000 and dims[1] >= 1500):
            continue
        selected = image_reviews.get(a['id'], {})
        tags = set(a.get('types', [])) | set(asset_reviews.get(a['id'], {}).get('types', []))
        tier = a.get('association', {}).get('tier')
        uses = set(selected.get('uses', []))
        reasons = []
        if selected.get('decision') in ('exclude', 'excluded'):
            reasons.append('Explicitly excluded by the owner; preserve that choice')
        if uses and 'listing' not in uses:
            reasons.append('Owner uses this as ' + ', '.join(sorted(uses)) + '; do not silently repurpose it')
        if tier == 'related':
            reasons.append('Family-only candidate; component and finish identity are unverified')
        if 'in_situ' in tags:
            reasons.append('Categorised In situ; owner purpose remains unchanged')
        if 'detail' in tags:
            reasons.append('Categorised detail; a complete product view is not established')
        if 'group' in tags:
            reasons.append('Group image; may depict additional products')
        if not reasons:
            reasons.append('Unselected association; visual component/finish and full-product review still required')
        candidates.append({**{k: a.get(k) for k in ('id', 'name', 'url', 'folder_url', 'folder_id',
            'local_preview', 'remote_preview', 'representation', 'original', 'association', 'product_ids')},
            'types': sorted(tags), 'owner_review': selected,
            'same_folder_as_primary': bool(primary_folder and a.get('folder_id') == primary_folder),
            'review_reasons': reasons,
            'candidate_for_visual_review': tier in ('accepted', 'folder') and 'product' in tags
                and not tags.intersection({'detail', 'in_situ', 'group', 'workshop'})
                and not (uses and 'listing' not in uses)
                and selected.get('decision') not in ('exclude', 'excluded')})
    return dict(catalogue_id=pid, title=previous['title'], source_hash=product['source_hash'],
        primary=previous['primary'], associations_examined=len(images),
        unselected_original_dimensions_unknown=unknown, unknown_full_product_candidate_metadata=unknown_product_candidates,
        larger_unselected_associations=candidates)


products, failures = [], []
with ThreadPoolExecutor(max_workers=3) as pool:
    jobs = {pool.submit(examine, p): p['catalogue_id'] for p in targets}
    for f in as_completed(jobs):
        try:
            products.append(f.result())
        except Exception as e:
            failures.append(dict(catalogue_id=jobs[f], error=str(e)))
        if (len(products) + len(failures)) % 17 == 0:
            print(json.dumps({'products_checked': len(products), 'failures': len(failures)}), flush=True)
products.sort(key=lambda p: p['title'])
summary = dict(checked_at=datetime.now(timezone.utc).isoformat(), targets=68, checked=len(products),
    failures=failures, associations_examined=sum(p['associations_examined'] for p in products),
    products_with_any_larger_unselected_association=sum(bool(p['larger_unselected_associations']) for p in products),
    products_with_potential_full_product_visual_candidates=sum(any(a['candidate_for_visual_review']
        for a in p['larger_unselected_associations']) for p in products),
    products_with_unknown_unselected_dimensions=sum(bool(p['unselected_original_dimensions_unknown']) for p in products),
    products_with_plausible_full_product_photos_needing_dimensions=sum(bool(p['unknown_full_product_candidate_metadata']) for p in products),
    unique_plausible_full_product_photos_needing_dimensions=len({a['id'] for p in products for a in p['unknown_full_product_candidate_metadata']}),
    app_choices_changed=0, cloud_changes=0, photographs_downloaded_or_copied=0)
(OUT / 'remaining-photo-library-review.json').write_text(json.dumps(dict(summary=summary,
    products=products), ensure_ascii=False, indent=2) + '\n')
print(json.dumps(summary), flush=True)
