"""Read bounded headers at exact existing Dropbox revisions, retaining no photos."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import json
import sys
import argparse

ROOT = Path('/Users/tprice/Documents/boldstone')
OUT = Path(__file__).parent
sys.path.insert(0, str(ROOT / 'catalogue-review'))
from delete_dropbox import connection
from PIL import ImageFile

review = json.loads((OUT / 'remaining-photo-library-review.json').read_text())
assets = {a['id']: a for p in review['products'] for a in p['unknown_full_product_candidate_metadata']}
assert len(assets) == 25
LIMIT = 256 * 1024


def read_group(group):
    results = []
    with connection(ROOT) as (db, _):
        for a in group:
            try:
                m = db.files_get_metadata(a['id'], include_media_info=True)
                assert m.id == a['id']
                assert m.path_lower.startswith('/boldstone master/')
                assert m.size == a['original']['bytes']
                expected_hash = a['original'].get('dropbox_content_hash')
                if expected_hash:
                    assert m.content_hash == expected_hash, 'Recorded content hash does not match current provider metadata'
                md, response = db.files_download('rev:' + m.rev)
                try:
                    assert md.id == m.id and md.rev == m.rev and md.content_hash == m.content_hash
                    parser = ImageFile.Parser()
                    read = 0
                    for chunk in response.iter_content(chunk_size=8192):
                        if not chunk:
                            continue
                        chunk = chunk[:LIMIT - read]
                        read += len(chunk)
                        parser.feed(chunk)
                        if parser.image or read >= LIMIT:
                            break
                    dims = list(parser.image.size) if parser.image else None
                finally:
                    response.close()
                results.append(dict(image_id=a['id'], current_name=m.name, revision=m.rev,
                    path=m.path_display, bytes=m.size, dropbox_content_hash=m.content_hash,
                    dimensions=dims, header_bytes_read=read,
                    catalogue_content_hash_present=bool(expected_hash),
                    meets_documented_dimensions=bool(dims and dims[0] >= 1000 and dims[1] >= 1500),
                    verification_basis='Bounded image-header read from authenticated exact Dropbox revision; '
                        'ID, revision, size and provider content-hash metadata matched. Full content hash not recomputed. '
                        + ('Catalogue fingerprint matched.' if expected_hash else
                           'Legacy catalogue fingerprint was missing; this is a new current-revision observation for review, not proof of an unchanged historical reference.'),
                    original_copy_retained=False))
            except Exception as e:
                results.append(dict(image_id=a['id'], error_type=type(e).__name__, error=str(e)[:250]))
    return results


arguments = argparse.ArgumentParser()
arguments.add_argument('--only-id')
args = arguments.parse_args()
selected = list(assets.values())
results = []
if args.only_id:
    assert args.only_id in assets
    selected = [assets[args.only_id]]
    previous = json.loads((OUT / 'unselected-original-header-review.json').read_text())
    results = [{**a['header_check']} for p in previous['products'] for a in p['candidates']
               if a['id'] != args.only_id]
groups = [selected[i::3] for i in range(3)]
with ThreadPoolExecutor(max_workers=3) as pool:
    jobs = [pool.submit(read_group, group) for group in groups if group]
    for f in as_completed(jobs):
        results.extend(f.result())
        print(json.dumps({'headers_checked': len(results)}), flush=True)
by = {r['image_id']: r for r in results}
products = []
for p in review['products']:
    candidates = [{**a, 'header_check': by[a['id']]} for a in p['unknown_full_product_candidate_metadata']]
    if candidates:
        products.append(dict(catalogue_id=p['catalogue_id'], title=p['title'], candidates=candidates))
summary = dict(checked_at=datetime.now(timezone.utc).isoformat(), originals_checked=len(results),
    errors=sum('error_type' in r for r in results), unknown_after_bounded_read=sum(not r.get('dimensions') and 'error_type' not in r for r in results),
    qualifying_originals=sum(r.get('meets_documented_dimensions', False) for r in results),
    products_with_qualifying_originals=sum(any(a['header_check'].get('meets_documented_dimensions') for a in p['candidates']) for p in products),
    header_bytes_read=sum(r.get('header_bytes_read', 0) for r in results),
    image_selections_or_cloud_records_changed=0, downloaded_original_copies_retained=0)
(OUT / 'unselected-original-header-review.json').write_text(json.dumps(dict(summary=summary,
    products=products), ensure_ascii=False, indent=2) + '\n')
print(json.dumps(summary), flush=True)
