"""Read-only review of the exact 117 gallery occurrences in the local Shopify CSV.

Builds analytical contact sheets only. Catalogue images and native services are
never changed. Numerical similarity is candidate triage, not a match decision.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import io
import json
import math
from pathlib import Path
import textwrap
import urllib.request

from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageOps, ImageStat

H = Path(__file__).resolve().parent
ROOT = H.parents[1]
CROSS = ROOT / 'reports/local-platform-crosswalk-corrected-20261024-root/local-platform-crosswalk.json'
B = ROOT / 'sculpture-catalogue/components/parallel-reviews/all-record-image-matching-20261024-B'
N = ROOT / 'reports/dropbox-wall-complete-role-review-20261024T214349Z'

def read(p):
    return json.loads(Path(p).read_text())

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def write(p, value):
    Path(p).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')

def clock():
    return datetime.now(timezone.utc).isoformat()

def small(p):
    with Image.open(p) as im:
        im = ImageOps.exif_transpose(im).convert('RGB')
        return im.resize((24, 24), Image.Resampling.BILINEAR)

def distance(a, b):
    values = ImageStat.Stat(ImageChops.difference(a, b)).rms
    return math.sqrt(sum(x*x for x in values) / 3)

def fetch(url):
    target = H / 'downloads' / (hashlib.sha256(url.encode()).hexdigest() + '.image')
    receipt_path = target.with_suffix('.receipt.json')
    if target.exists() and receipt_path.exists():
        r = read(receipt_path)
        assert sha(target) == r['sha256']
        return r
    start = clock()
    try:
        request = urllib.request.Request(url, headers={'User-Agent': 'BoldstoneCatalogueLocalSourceReview/1.0'})
        with urllib.request.urlopen(request, timeout=25) as response:
            raw = response.read(30_000_001)
            assert len(raw) <= 30_000_000, 'size guard'
            if response.headers.get('Content-Length'):
                assert len(raw) == int(response.headers['Content-Length'])
            with Image.open(io.BytesIO(raw)) as im:
                im.load()
                dimensions, fmt = list(im.size), im.format
            target.write_bytes(raw)
            r = {'status': 'FETCHED_AND_FULLY_DECODED', 'requested_url': url,
                 'resolved_url': response.url, 'started_utc': start, 'completed_utc': clock(),
                 'http_status': response.status, 'content_type': response.headers.get('Content-Type'),
                 'path': str(target), 'bytes': len(raw), 'sha256': sha(target),
                 'dimensions': dimensions, 'format': fmt,
                 'export_date_and_live_product_presence_not_verified': True}
        write(receipt_path, r)
        return r
    except Exception as e:
        return {'status': 'DOWNLOAD_FAILED', 'requested_url': url, 'started_utc': start,
                'completed_utc': clock(), 'error': str(e)}

def main():
    (H / 'downloads').mkdir(exist_ok=True)
    (H / 'boards').mkdir(exist_ok=True)
    (H / 'input-snapshots').mkdir(exist_ok=True)
    assert sha(CROSS) == 'ef7158d87d6402d1e57b8f209da3ca6421104887da9c8a1e3ea9413b72bce578'
    cross = read(CROSS)
    assert cross['baseline_pointer_sha256'] == sha(ROOT / 'sculpture-catalogue/current-master.json')
    native = read(N / 'complete-current-native-object-map.json')
    evidence = read(N / 'current-6360-visual-source-evidence.json')
    assert len(evidence) == 6360
    brun = Path(read(B / 'current-work.json')['run'])
    source_renditions = read(brun / 'source-evidence/source-rendition-review-register.json')
    # Retain the exact in-progress comparison input rather than a moving path.
    for name, path in [('squarespace-renditions.json', brun / 'source-evidence/source-rendition-review-register.json'),
                       ('squarespace-decisions-provisional.json', B / 'source-visual-decisions.json')]:
        snapshot = H / 'input-snapshots' / name
        if not snapshot.exists():
            snapshot.write_bytes(path.read_bytes())
    source_renditions = read(H / 'input-snapshots/squarespace-renditions.json')
    sqdec = read(H / 'input-snapshots/squarespace-decisions-provisional.json')
    wall = [p for p in cross['local_shopify_records'] if p['product']['in_preserved_wall_subset']]
    rows = []
    for product in wall:
        for position, media in enumerate(product['full_product_gallery'], 1):
            rows.append({'review_id': f'S{len(rows)+1:03}', 'handle': product['handle'],
                         'title': product['product']['title'], 'gallery_order': position,
                         'exported_gallery_row': media, 'matched_squarespace_offer_refs': product['matched_squarespace_offer_refs'],
                         'exported_skus': [v['sku_raw'] for v in product['variants']],
                         'variant_specific_assignment_certified': False})
    assert len(wall) == 38 and len(rows) == 117
    urls = sorted({x['exported_gallery_row']['image_src'] for x in rows})
    receipts = {}
    with ThreadPoolExecutor(max_workers=8) as pool:
        for future in as_completed({pool.submit(fetch, url): url for url in urls}):
            r = future.result()
            receipts[r['requested_url']] = r
    write(H / 'download-receipts.json', [receipts[u] for u in urls])
    failures = [r for r in receipts.values() if r['status'] != 'FETCHED_AND_FULLY_DECODED']
    if failures:
        print(json.dumps({'download_failures': failures}, indent=2), flush=True)
        raise RuntimeError('All source frames must be available before ranking')
    native_index = []
    native_small = []
    for item in evidence:
        assert sha(item['source_image_path']) == item['actual_visual_source_sha256']
        native_index.append(item)
        native_small.append(small(item['source_image_path']))
    sq_index = []
    sq_small = []
    for item in source_renditions:
        r = item.get('selected_rendition')
        if not r:
            continue
        assert sha(r['path']) == r['sha256']
        sq_index.append(item)
        sq_small.append(small(r['path']))
    for row in rows:
        row['source_download'] = receipts[row['exported_gallery_row']['image_src']]
        vector = small(row['source_download']['path'])
        nscores = [distance(candidate, vector) for candidate in native_small]
        row['ranked_native_candidates'] = []
        for ix in sorted(range(len(nscores)), key=nscores.__getitem__)[:5]:
            e = native_index[int(ix)]
            row['ranked_native_candidates'].append({'rmse24': float(nscores[ix]),
                'native': native[e['file_id']], 'visual_source': e})
        sscores = [distance(candidate, vector) for candidate in sq_small]
        row['ranked_squarespace_candidates'] = []
        for ix in sorted(range(len(sscores)), key=sscores.__getitem__)[:3]:
            e = sq_index[int(ix)]
            key = f"{e['offer_ref']}:{e['gallery_order']:02}"
            row['ranked_squarespace_candidates'].append({'rmse24': float(sscores[ix]),
                'offer_ref': e['offer_ref'], 'gallery_order': e['gallery_order'],
                'gallery_entry_id': e['gallery_entry_id'], 'selected_rendition': e['selected_rendition'],
                'source_url': e['source_url'], 'prior_provisional_visual_decision': sqdec.get(key),
                'decision_must_be_revalidated_in_B_final_sealed_handoff': True})
        row['status'] = 'CANDIDATES_ONLY_AWAITING_EXPLICIT_VISUAL_REVIEW'
    write(H / 'ranked-gallery-register.json', rows)
    font = ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf', 15)
    tiny = ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf', 12)
    boards = []
    for start in range(0, len(rows), 12):
        group = rows[start:start+12]
        board = Image.new('RGB', (1530, 1512), 'white')
        draw = ImageDraw.Draw(board)
        items = []
        for slot, row in enumerate(group):
            x = slot % 3 * 510
            y = slot // 3 * 378
            best = row['ranked_native_candidates'][0]
            sq = row['ranked_squarespace_candidates'][0]
            draw.text((x+4, y+4), f"{row['review_id']}  {row['title'][:47]} / {row['gallery_order']}", fill='black', font=font)
            draw.text((x+5, y+24), 'SHOPIFY             DROPBOX             SQUARESPACE', fill='black', font=tiny)
            for offset, path in [(0, row['source_download']['path']), (170, best['visual_source']['source_image_path']), (340, sq['selected_rendition']['path'])]:
                with Image.open(path) as im:
                    im = ImageOps.exif_transpose(im).convert('RGB')
                    im.thumbnail((164, 264), Image.Resampling.LANCZOS)
                    board.paste(im, (x+offset+(170-im.width)//2, y+45+(264-im.height)//2))
            caption = (f"DB {best['native']['file_id'][-5:]} {best['native']['name']} "
                       f"[{best['rmse24']:.2f}] SQ {sq['offer_ref']}/{sq['gallery_order']} [{sq['rmse24']:.2f}]")
            draw.multiline_text((x+5, y+313), '\n'.join(textwrap.wrap(caption, 68)[:4]), fill='black', font=tiny, spacing=1)
            draw.line([(x, y+377), (x+509, y+377)], fill='#aaa')
            items.append({'slot': slot+1, 'review_id': row['review_id'],
                          'shopify_source_sha256': row['source_download']['sha256'],
                          'candidate_file_id': best['native']['file_id'],
                          'candidate_source_sha256': best['visual_source']['actual_visual_source_sha256'],
                          'candidate_squarespace_entry_id': sq['gallery_entry_id']})
        path = H / 'boards' / f'board-{start//12+1:02}.jpg'
        board.save(path, quality=95, subsampling=0)
        boards.append({'path': str(path), 'sha256': sha(path), 'items': items})
    write(H / 'boards/manifest.json', boards)
    write(H / 'preparation-receipt.json', {'status': 'SOURCE_DOWNLOADS_AND_CANDIDATE_BOARDS_READY',
        'prepared_utc': clock(), 'source_gallery_occurrences': len(rows), 'products': len(wall),
        'unique_source_urls': len(urls), 'download_bytes': sum(r['bytes'] for r in receipts.values()),
        'download_failures': 0, 'native_candidates': len(native_index), 'squarespace_candidates': len(sq_index),
        'crosswalk': {'path': str(CROSS), 'sha256': sha(CROSS)},
        'original_local_shopify_csv': {'path': '/Users/tprice/Downloads/products_export_1 (1).csv',
            'sha256': sha('/Users/tprice/Downloads/products_export_1 (1).csv')},
        'baseline_pointer_sha256': cross['baseline_pointer_sha256'],
        'native_map': {'path': str(N / 'complete-current-native-object-map.json'), 'sha256': sha(N / 'complete-current-native-object-map.json')},
        'native_visual_evidence': {'path': str(N / 'current-6360-visual-source-evidence.json'), 'sha256': sha(N / 'current-6360-visual-source-evidence.json')},
        'ranking_is_identity_proof': False, 'native_or_platform_writes': 0, 'canonical_writes': 0})
    print(json.dumps({'status': 'PREPARED', 'rows': len(rows), 'unique_urls': len(urls), 'boards': len(boards)}, indent=2))

if __name__ == '__main__':
    main()
