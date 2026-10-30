"""Collect hash-bound source renditions and explicit prior visual decisions.

This creates an evidence queue, not approved product/image assignments. A prior
review's qualifications are retained verbatim. Folder names and numerical image
similarity never count as visual review.
"""
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from PIL import Image, ImageOps

H = Path(__file__).resolve().parent
B = H.parents[2]
ROOT = B.parent
OLD = Path('/Users/tprice/Library/Application Support/BoldstoneImageConsistency/product-evidence-resolution-20261016T201618Z')
def read(p): return json.loads(Path(p).read_text())
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p, d): Path(p).write_text(json.dumps(d, ensure_ascii=False, indent=2) + '\n')
def normalize(url): return (url or '').split('?')[0]

run = Path(read(H / 'current-work.json')['run'])
out = run / 'source-evidence'
out.mkdir(exist_ok=True)
manifest = {}
def input_file(path):
    path = Path(path)
    manifest[str(path)] = sha(path)
    return read(path)

gallery = input_file(run / 'source-gallery.json')
offers = input_file(B / 'components/evidence/offer_review_index.json')
offer_map = {x['ref']: x for x in offers}
cache = defaultdict(list)
reviews = defaultdict(list)
unbound_reviews = []

def cached(url, path, recorded_sha=None, representation='retained source rendition', evidence=None):
    if not url or not path or not str(path).startswith('/'):
        return
    row = {'path': str(path), 'recorded_sha256': recorded_sha,
           'representation': representation, 'evidence': evidence}
    if row not in cache[normalize(url)]:
        cache[normalize(url)].append(row)

for offer in offers:
    for row in offer['images']:
        cached(row['url'], row.get('path'), row.get('sha256'), 'retained indexed source download')
        cached(row['url'], row.get('thumb'), None, 'retained indexed thumbnail; hash established in this integration')
for row in input_file(OLD / 'Public_Gallery_References.json')['records']:
    cached(row['image_url'], row.get('image_path'), row.get('image_sha256'), 'retained public gallery rendition')
for row in input_file(B / 'evidence/established_offer_image_index.json'):
    cached(row['url'], row.get('local_path'), row.get('sha256'), 'retained established-offer source download')
downloads = H / 'source-download-receipts.json'
if downloads.exists():
    for url, row in input_file(downloads).items():
        if row.get('status') == 'DOWNLOADED_AND_DECODED':
            cached(url, row['path'], row['sha256'], 'Exact retained CDN URL fetched for this review; no historical byte identity claim', row)

index = input_file(B / read(B / 'current-master.json')['current_source_photo_review_index']['path'])
for packet in index['review_packets']:
    p = Path(packet['review_json'])
    assert sha(p) == packet['review_sha256']
    d = input_file(p)
    def add_review(row, pointer, ref=None, kind='prior_source_photo_comparison'):
        ref = row.get('offer_ref', row.get('ref', ref))
        url = row.get('source_url') or row.get('source_image_url')
        order = row.get('source_order') or row.get('gallery_order') or row.get('retained_source_gallery_order') or row.get('retained_image_order')
        if order is None and row.get('gallery_index') is not None:
            order = row['gallery_index'] + 1
        if order is None and row.get('source_gallery_index') is not None:
            order = row['source_gallery_index'] + 1
        if not url and ref and order:
            candidates = [g for g in gallery if g['offer_ref'] == ref and g['gallery_order'] == order]
            if len(candidates) == 1:
                url = candidates[0]['source_url']
        evidence = {'path': str(p), 'sha256': manifest[str(p)], 'json_pointer': pointer,
                    'kind': kind, 'offer_ref': ref, 'recorded_source_order': order,
                    'source_url': url, 'recorded_review': row}
        if url and 'squarespace-cdn.com' in url:
            reviews[(ref, normalize(url))].append(evidence)
            source = row.get('source_cached_image') or row.get('source_rendition') or {}
            if isinstance(source, dict):
                cached(url, source.get('path') or source.get('cached_path'), source.get('sha256') or source.get('cached_sha256'), 'prior reviewed source rendition', evidence)
            cached(url, row.get('source_cached_path') or row.get('source_local_path') or row.get('source_path'), row.get('source_cached_sha256') or row.get('source_sha256'), 'prior reviewed source rendition', evidence)
            if kind == 'explicit_source_rendition_visual_review':
                cached(url, row.get('path'), row.get('sha256'), 'prior visually reviewed source rendition', evidence)
        else:
            unbound_reviews.append(evidence)

    for i, case in enumerate(d.get('cases', [])):
        ref = case.get('offer_ref', case.get('ref'))
        for key in ['source_photo_comparisons', 'source_photo_correspondences', 'viewed_source_renditions']:
            for j, row in enumerate(case.get(key, [])):
                add_review(row, f'/cases/{i}/{key}/{j}', ref,
                           'explicit_source_rendition_visual_review' if key == 'viewed_source_renditions' else 'prior_source_photo_comparison')
        for j, row in enumerate(case.get('images', [])):
            if row.get('source_image_url') and row.get('visually_opened_this_turn'):
                add_review(row, f'/cases/{i}/images/{j}', ref, 'explicit_source_rendition_visual_review')
        # Root's two first-image comparisons explicitly name the source URL,
        # but their individual source-rendition rows do not repeat it.
        if p.parent.name == 'source-photo-finish-review-20261024-root':
            source_rows = [x for x in case.get('images', []) if 'public primary' in x.get('role', '')]
            for j, row in enumerate(source_rows):
                add_review({**row, 'source_url': case['source_first_image_url'], 'source_order': 1,
                            'finding': case['finding'], 'current_reference': case.get('current_reference')},
                           f'/cases/{i}', ref, 'explicit_source_rendition_visual_review')
        if p.parent.name == 'o002-o004-source-photo-review-01a16dbc-20261024':
            comparison = case.get('image_comparison', {})
            if comparison.get('gallery_position'):
                add_review({**comparison, 'source_order': comparison['gallery_position'],
                            'source_path': comparison.get('saved_source_image'),
                            'file_id': case.get('file_id')}, f'/cases/{i}/image_comparison', ref)
    for key in ['photo_bindings', 'photo_comparisons', 'source_frames_viewed']:
        rows = d.get(key, [])
        if not isinstance(rows, list):
            continue
        for i, row in enumerate(rows):
            add_review(row, f'/{key}/{i}', kind='explicit_source_rendition_visual_review' if key == 'source_frames_viewed' else 'prior_source_photo_comparison')

# Preserve previously downloaded exact URLs without re-fetching them.
extra = B / 'components/parallel-reviews/dune-ripple1-rust-two-source-review-20261024-B/additional-source-downloads.json'
if extra.exists():
    data = input_file(extra)
    def descend(obj):
        if isinstance(obj, dict):
            url = obj.get('source_url') or obj.get('url')
            if url:
                cached(url, obj.get('path') or obj.get('local_path'), obj.get('sha256'), 'retained direct CDN download')
            for v in obj.values(): descend(v)
        elif isinstance(obj, list):
            for v in obj: descend(v)
    descend(data)

checks = {}
def verify(row):
    path = Path(row['path'])
    if str(path) not in checks:
        if not path.is_file():
            checks[str(path)] = {'available': False}
        else:
            try:
                digest = sha(path)
                with Image.open(path) as im:
                    im.load()
                    oriented = ImageOps.exif_transpose(im)
                    checks[str(path)] = {'available': True, 'sha256': digest,
                        'bytes': path.stat().st_size, 'format': im.format,
                        'dimensions': list(oriented.size), 'full_decode_passed': True}
            except Exception as e:
                checks[str(path)] = {'available': False, 'error': str(e)}
    checked = {**row, **checks[str(path)]}
    checked['recorded_hash_matches'] = checked.get('sha256') == row['recorded_sha256'] if row.get('recorded_sha256') else None
    if checked['recorded_hash_matches'] is False:
        checked['available'] = False
        checked['rejection_reason'] = 'Cached bytes changed from recorded source hash'
    return checked

records = []
for g in gallery:
    key = normalize(g['source_url'])
    renditions = [verify(x) for x in cache[key]]
    good = [x for x in renditions if x['available']]
    good.sort(key=lambda x: (x['recorded_hash_matches'] is True, x['dimensions'][0] * x['dimensions'][1]), reverse=True)
    prior = reviews.get((g['offer_ref'], key), [])
    records.append({**g, 'cached_renditions': renditions,
        'selected_rendition': good[0] if good else None,
        'download_status': 'HASHED_DECODED_LOCAL_RENDITION_AVAILABLE' if good else 'NO_VALIDATED_LOCAL_RENDITION',
        'prior_visual_evidence': prior,
        'visual_review_status': 'PRIOR_EXPLICIT_VISUAL_REVIEW_RETAINED_WITH_QUALIFICATIONS' if prior else 'VISUAL_REVIEW_NOT_YET_INTEGRATED',
        'visual_role': None, 'role_status': 'PER_IMAGE_ROLE_PENDING',
        'product_assignment_status': 'PRESERVE_RECORDED_QUALIFICATIONS_PENDING_GRAPH_INTEGRATION'})

summary = {'recorded_utc': datetime.now(timezone.utc).isoformat(),
           'gallery_entries': len(records), 'unique_source_urls': len({normalize(x['source_url']) for x in records}),
           'download_status': dict(Counter(x['download_status'] for x in records)),
           'review_status': dict(Counter(x['visual_review_status'] for x in records)),
           'prior_packets_verified': len(index['review_packets']),
           'unbound_prior_records': len(unbound_reviews),
           'local_files_checked': len(checks), 'current_native_or_canonical_writes': 0,
           'limits': ['Retained reviews are not a blanket approval of every image in a gallery.',
                      'Local byte hashes preserve inspected evidence; they do not certify a physical product or historical original bytes.',
                      'Visual roles and exact image-to-product assignments remain separately tracked.']}
write(out / 'source-rendition-review-register.json', records)
write(out / 'unbound-prior-review-records.json', unbound_reviews)
write(out / 'local-file-checks.json', checks)
write(out / 'input-manifest.json', manifest)
write(out / 'summary.json', summary)
print(json.dumps({'output': str(out), 'summary': summary}, indent=2))
