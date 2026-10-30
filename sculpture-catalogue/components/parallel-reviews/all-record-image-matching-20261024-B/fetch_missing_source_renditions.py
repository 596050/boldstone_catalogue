"""Fetch only exact retained CDN URLs missing from the local review cache."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import urllib.request
from PIL import Image, ImageOps

H = Path(__file__).resolve().parent
run = Path(json.loads((H / 'current-work.json').read_text())['run'])
evidence = run / 'source-evidence'
register_path = evidence / 'source-rendition-review-register.json'
register = json.loads(register_path.read_text())
target = H / 'source-downloads'
target.mkdir(exist_ok=True)
receipt_path = H / 'source-download-receipts.json'
receipts = json.loads(receipt_path.read_text()) if receipt_path.exists() else {}
missing = {x['source_url'] for x in register if not x['selected_rendition']}

def get(url):
    assert url.startswith('https://images.squarespace-cdn.com/')
    key = hashlib.sha256(url.encode()).hexdigest()
    path = target / (key + '.image')
    old = receipts.get(url)
    if old and old.get('status') == 'DOWNLOADED_AND_DECODED' and path.exists() and hashlib.sha256(path.read_bytes()).hexdigest() == old['sha256']:
        return url, old
    stamp = datetime.now(timezone.utc).isoformat()
    try:
        request = urllib.request.Request(url, headers={'User-Agent': 'BoldstoneCatalogueImageReview/1.0'})
        with urllib.request.urlopen(request, timeout=30) as response:
            blob = response.read(25 * 1024 * 1024 + 1)
            if len(blob) > 25 * 1024 * 1024:
                raise ValueError('Source exceeded 25 MiB review-download cap')
            final_url = response.url
            assert final_url.startswith('https://images.squarespace-cdn.com/')
            content_type = response.headers.get('Content-Type')
        with Image.open(io.BytesIO(blob)) as im:
            im.load()
            fmt = im.format
            dims = list(ImageOps.exif_transpose(im).size)
        path.write_bytes(blob)
        return url, {'status': 'DOWNLOADED_AND_DECODED', 'requested_url': url,
            'response_url': final_url, 'fetched_utc': stamp, 'path': str(path),
            'sha256': hashlib.sha256(blob).hexdigest(), 'bytes': len(blob),
            'format': fmt, 'dimensions': dims, 'content_type': content_type,
            'historical_original_byte_identity_claimed': False, 'image_edited': False}
    except Exception as e:
        return url, {'status': 'DOWNLOAD_UNAVAILABLE', 'requested_url': url,
                     'attempted_utc': stamp, 'error': str(e)}

with ThreadPoolExecutor(max_workers=4) as executor:
    for count, future in enumerate(as_completed([executor.submit(get, url) for url in sorted(missing)]), 1):
        url, row = future.result()
        receipts[url] = row
        temp = receipt_path.with_suffix('.tmp')
        temp.write_text(json.dumps(receipts, ensure_ascii=False, indent=2) + '\n')
        temp.replace(receipt_path)
        if count % 20 == 0:
            print(json.dumps({'completed': count, 'requested': len(missing)}), flush=True)
print(json.dumps({'requested': len(missing), 'successful': sum(receipts[u]['status'] == 'DOWNLOADED_AND_DECODED' for u in missing),
                  'unavailable': sum(receipts[u]['status'] != 'DOWNLOADED_AND_DECODED' for u in missing),
                  'receipt': str(receipt_path)}, indent=2))
