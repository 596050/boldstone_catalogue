"""Prepare eligible photos for existing Saatchi drafts, reusing verified files.

No photo editing, account requests or publication. Native artwork IDs are
mandatory and existing published Icarus is excluded from this draft pass.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen
import sys

from PIL import Image


def eligible(size):
    return size[0] >= 1500 and size[1] >= 1200


def select_additions(photos, limit=5):
    """Respect the native cap while retaining product and setting views."""
    if limit < 1:
        raise ValueError('At least one additional image slot is required')
    if len({p['id'] for p in photos}) != len(photos):
        raise ValueError('Duplicate photograph identity in a gallery')
    if len(photos) <= limit:
        return photos, []
    product = [p for p in photos if p['role'] != 'in_situ']
    setting = [p for p in photos if p['role'] == 'in_situ']
    setting_count = min(2, len(setting), limit)
    chosen = product[:limit - setting_count] + setting[:setting_count]
    ids = {p['id'] for p in chosen}
    for p in photos:
        if len(ids) >= limit:
            break
        ids.add(p['id'])
    return ([p for p in photos if p['id'] in ids],
            [p for p in photos if p['id'] not in ids])


def main():
    root = Path(sys.argv[1]).resolve()
    directory = root / 'saatchi-current'
    records = json.loads((directory / 'prepared-catalogue.json').read_text())['records']
    records = [r for r in records if r.get('native_artwork_id') and r['sku'] != 'SQ0717348']
    if len({r['native_artwork_id'] for r in records}) != len(records):
        raise ValueError('Duplicate native artwork IDs')
    cache = {}
    prior = directory / 'prepared-galleries.json'
    if prior.exists():
        for r in json.loads(prior.read_text())['records']:
            for p in r.get('additions', []) + r.get('gallery_overflow', []):
                local = Path(p['path'])
                if (eligible(p['dimensions']) and local.is_file()
                        and hashlib.sha256(local.read_bytes()).hexdigest() == p['sha256']):
                    cache[p['url']] = {k: p[k] for k in ('path', 'sha256', 'dimensions')}
                    cache[p['url']]['reused'] = True
    for path in (root / 'chairish-current/photos').glob('*/manifest.json'):
        manifest = json.loads(path.read_text())
        for p in manifest.get('all_selected_assets', manifest.get('photos', [])):
            size = p.get('upload_dimensions') or p.get('dimensions') or [0, 0]
            local = Path(p.get('upload_path') or p.get('path') or '')
            digest = p.get('upload_sha256') or p.get('sha256')
            if eligible(size) and local.is_file() and digest:
                if hashlib.sha256(local.read_bytes()).hexdigest() == digest:
                    cache[p['url']] = {'path': str(local), 'sha256': digest,
                        'dimensions': size, 'reused': True}
    target = directory / 'gallery-upload-files'
    target.mkdir(exist_ok=True)
    photos = {}
    for r in records:
        for p in r['photos']:
            c = p['header_check']
            if c.get('status') == 'PASS_IMAGE_HEADER_CHECK' and p['id'] != r['channel_primary']['photo_id']:
                photos[p['url']] = p

    def prepare(p):
        if p['url'] in cache:
            return p['url'], cache[p['url']]
        parsed = urlparse(p['url'])
        if parsed.scheme != 'https' or parsed.hostname != 'images.squarespace-cdn.com':
            raise ValueError('Unexpected image host')
        raw = urlopen(p['url'], timeout=30).read()
        image = Image.open(io.BytesIO(raw))
        image.verify()
        if image.format not in ('JPEG', 'PNG') or not eligible(image.size) or len(raw) >= 50_000_000:
            raise ValueError('Photo does not meet the observed native limits: ' + p['id'])
        digest = hashlib.sha256(raw).hexdigest()
        path = target / (digest + ('.jpg' if image.format == 'JPEG' else '.png'))
        if not path.exists():
            path.write_bytes(raw)
        return p['url'], {'path': str(path), 'sha256': digest, 'dimensions': list(image.size), 'reused': False}

    assets = {}
    with ThreadPoolExecutor(max_workers=4) as pool:
        for n, (url, asset) in enumerate(pool.map(prepare, photos.values()), 1):
            assets[url] = asset
            if n % 50 == 0:
                print(f'Prepared {n}/{len(photos)} unique eligible photos', flush=True)
    output = []
    for r in records:
        additions = []
        for p in r['photos']:
            if p['id'] == r['channel_primary']['photo_id'] or p['url'] not in assets:
                continue
            caption = ('Illustrative setting reference' if p['role'] == 'in_situ'
                       else 'Additional sculpture view')
            additions.append({**p, **assets[p['url']], 'caption': caption})
        additions, overflow = select_additions(additions)
        output.append({'sku': r['sku'], 'title': r['title'], 'artwork_id': r['native_artwork_id'],
            'primary_photo_id': r['channel_primary']['photo_id'], 'additions': additions,
            'expected_photo_count': 1 + len(additions),
            'gallery_overflow': overflow,
            'gallery_overflow_reason': 'Saatchi permits five additional photographs beyond the primary',
            'ineligible_selected_photos': [p['id'] for p in r['photos']
                if p['id'] != r['channel_primary']['photo_id'] and p['url'] not in assets]})
    data = {'at': datetime.now(timezone.utc).isoformat(), 'records': output,
            'status': 'PREPARED_FOR_EXISTING_DRAFTS_ONLY', 'unique_assets': len(assets),
            'reused_assets': sum(a['reused'] for a in assets.values()),
            'additional_associations': sum(len(r['additions']) for r in output),
            'overflow_associations': sum(len(r['gallery_overflow']) for r in output),
            'maximum_additional_images': 5,
            'native_limit_source': 'https://support.saatchiart.com/hc/en-us/articles/17737130295963-How-to-photograph-an-artwork'}
    (directory / 'prepared-galleries.json').write_text(json.dumps(data, indent=2) + '\n')
    print(json.dumps({k: v for k, v in data.items() if k != 'records'}))


if __name__ == '__main__':
    main()
