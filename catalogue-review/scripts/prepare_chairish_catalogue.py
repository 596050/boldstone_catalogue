"""Prepare Chairish drafts and bounded upload assets; never publish listings.

The source catalogue remains authoritative. Native receipts are retained so a
rerun cannot quietly create another listing for an already uploaded SKU.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import io
import json
import re
from pathlib import Path
import sys
from urllib.parse import urlparse, urlencode, parse_qsl, urlunparse
from urllib.request import urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from channel_content import chairish_description


def native_bindings(path):
    rows = json.loads(path.read_text()) if path.exists() else []
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise ValueError('Malformed Chairish native receipts')
    result, owners = {}, {}
    for row in rows:
        sku, native_id = row.get('sku'), row.get('id')
        if not sku or not isinstance(native_id, str) or not native_id.isdecimal():
            raise ValueError('Incomplete Chairish native receipt')
        if sku in result and result[sku] != native_id:
            raise ValueError('Conflicting Chairish IDs for ' + sku)
        if native_id in owners and owners[native_id] != sku:
            raise ValueError('One Chairish ID belongs to multiple SKUs')
        result[sku], owners[native_id] = native_id, sku
    return result


def chairish_fulfilment(availability, parcel):
    """Use explicit catalogue availability, never infer stock from parcel size.

    Chairish exposes a production lead time for Not Yet Made listings. Its
    ordinary three-day parcel rule therefore does not override those records.
    Fourteen days is the native two-week option for the owner's ten-working-day
    allowance; this is a draft setting, not a new physical-stock assertion.
    """
    made_to_order = bool(re.match(r'^made to order(?:;|$)',
                                 str(availability or '').strip(), re.I))
    return {
        'dispatch_working_days': 10 if made_to_order or parcel is False else 3,
        'source_availability': availability or '',
        'period_made': 'NOT_MADE' if made_to_order else None,
        'lead_time': 'W2' if made_to_order else None,
        'lead_time_label': '14 days' if made_to_order else None,
    }


def download_photo(task):
    from PIL import Image
    index, photo, directory = task
    url = photo['url']
    parsed = urlparse(url)
    if parsed.scheme != 'https' or parsed.hostname != 'images.squarespace-cdn.com':
        raise ValueError('Unexpected image host')
    raw = urlopen(url, timeout=30).read()
    image = Image.open(io.BytesIO(raw))
    image.verify()
    original_size = image.size
    # Request an existing CDN rendition; do not generate, crop or upscale art.
    if max(original_size) > 2000:
        max_width = min(2000, 2000 * original_size[0] / original_size[1])
        width = max((n for n in (100, 300, 500, 750, 1000, 1500)
                     if n <= max_width), default=100)
        query = dict(parse_qsl(parsed.query)); query['format'] = str(width) + 'w'
        url = urlunparse(parsed._replace(query=urlencode(query)))
        raw = urlopen(url, timeout=30).read()
        image = Image.open(io.BytesIO(raw)); image.verify()
    if image.format not in ('JPEG', 'PNG') or max(image.size) > 2000:
        raise ValueError('Image needs a separate format or size review')
    suffix = '.png' if image.format == 'PNG' else '.jpg'
    digest = hashlib.sha256(raw).hexdigest()
    path = directory / (f'{index:02d}-{digest}' + suffix)
    path.write_bytes(raw)
    return {**photo, 'path': str(path.resolve()), 'upload_url': url,
            'bytes': len(raw), 'sha256': digest,
            'source_dimensions': list(original_size), 'dimensions': list(image.size),
            'format': image.format,
            'image_size_review': min(image.size) < 575}


def checked_download(task):
    try:
        return download_photo(task)
    except Exception as exc:
        return {'id': task[1].get('id'), 'url': task[1]['url'],
                'error': str(exc)}


def partition_upload_assets(assets):
    """Retain rejected small images as explicit gaps, never invent resolution."""
    accepted, excluded = [], []
    for photo in assets:
        dimensions = photo.get('upload_dimensions') or photo['dimensions']
        if max(dimensions) < 575:
            excluded.append({**photo, 'exclusion_reason': 'BELOW_NATIVE_UPLOAD_MINIMUM'})
        else:
            accepted.append(photo)
    return accepted, excluded


def choose_upload_assets(assets, limit=18):
    accepted, excluded = partition_upload_assets(assets)
    return accepted[:limit], excluded, accepted[limit:]


def chairish_dimensions(text):
    """Map labelled axes and square faces; never guess rectangular orientation."""
    number = r'(\d+(?:\.\d+)?)(?:\s*[–—-]\s*(\d+(?:\.\d+)?))?'
    def upper(match, start=1):
        return Decimal(match.group(start + 1) or match.group(start))
    cm = {}
    for axis, labels in [('width', 'wide|width'), ('height', 'high|height'),
                         ('depth', 'deep|(?:side |panel |body )?depth')]:
        match = re.search(number + r'\s*cm\s*(?:' + labels + ')', text, re.I)
        if match:
            cm[axis] = upper(match)
    diameter = re.search(number + r'\s*cm\s*diameter', text, re.I)
    square = re.search(number + r'\s*cm\s*square', text, re.I)
    pair = re.search(number + r'\s*[×x]\s*' + number, text, re.I)
    triple = re.search(number + r'\s*[×x]\s*' + number + r'\s*[×x]\s*' + number + r'\s*cm', text, re.I)
    if diameter:
        cm.update(width=upper(diameter), height=upper(diameter))
    elif square:
        # A square basin's explicitly stated overall height is vertical;
        # the square describes its footprint rather than a wall-facing panel.
        overall = re.search(number + r'\s*cm\s*overall height', text, re.I)
        if overall:
            cm.update(width=upper(square), depth=upper(square), height=upper(overall))
        else:
            cm.update(width=upper(square), height=upper(square))
    elif pair and upper(pair) == upper(pair, 3):
        cm.setdefault('width', upper(pair))
        cm.setdefault('height', upper(pair, 3))
    if triple:
        cm.setdefault('depth', upper(triple, 5))
    inches = {axis: str((value / Decimal('2.54')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))
              for axis, value in cm.items()}
    return {'source': text, 'unit': 'inches', 'values': inches,
            'values_cm': {axis: float(value) for axis, value in cm.items()},
            'uses_catalogue_upper_range': bool(re.search(r'\d\s*[–—-]\s*\d', text)),
            'missing_axes': [axis for axis in ('width', 'depth', 'height') if axis not in inches],
            'basis': 'Catalogue dimensions; upper endpoint where a range is given. Not a new physical measurement.'}


def reviewed_orientation_dimensions(record, plan, review, assets):
    """Assign existing face measurements using an explicitly reviewed photo.

    This is not image measurement or a general portrait/landscape heuristic.
    Each decision is bound to the exact component, source text and photo bytes.
    """
    if not review or review.get('status') != 'ORIENTATION_REVIEWED':
        return plan
    if (review.get('sku') != record['sku'] or
            review.get('catalogue_id') != record['catalogue_id'] or
            review.get('dimensions') != plan['source']):
        raise ValueError('Stale orientation source: ' + record['sku'])
    current_ids = {p.get('id') for p in record['photos']}
    photo = next((p for p in assets if p.get('id') == review.get('photo_id')), None)
    if (review.get('photo_id') not in current_ids or not photo or
            not review.get('photo_sha256') or
            (photo.get('upload_sha256') or photo.get('sha256')) != review['photo_sha256']):
        raise ValueError('Stale orientation photo: ' + record['sku'])
    local = photo.get('upload_path') or photo.get('path')
    if local and (not Path(local).is_file() or
                  hashlib.sha256(Path(local).read_bytes()).hexdigest() != review['photo_sha256']):
        raise ValueError('Changed orientation photo bytes: ' + record['sku'])
    number = r'(\d+(?:\.\d+)?)'
    pair = re.search(number + r'\s*[×x]\s*' + number, plan['source'])
    cm = {axis: Decimal(str(value)) for axis, value in review.get('face_cm', {}).items()}
    if (not pair or set(cm) != {'width', 'height'} or
            any(not n.is_finite() or n <= 0 for n in cm.values()) or
            sorted(cm.values()) != sorted(Decimal(n) for n in pair.groups())):
        raise ValueError('Orientation must preserve catalogue face measurements: ' + record['sku'])
    values = dict(plan['values'])
    for axis, value in cm.items():
        inches = str((value / Decimal('2.54')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))
        if axis in values and values[axis] != inches:
            raise ValueError('Orientation conflicts with a labelled axis: ' + record['sku'])
        values[axis] = inches
    return {**plan, 'values': values,
            'values_cm': {**plan.get('values_cm', {}), **{axis: float(value) for axis, value in cm.items()}},
            'missing_axes': [axis for axis in ('width', 'depth', 'height') if axis not in values],
            'orientation_review': {k: review[k] for k in
                                   ('photo_id', 'photo_sha256', 'face_cm', 'observation', 'reviewed_utc')},
            'basis': plan['basis'] + ' Width and height assigned in the visually reviewed photograph orientation.'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--draft-usd-per-gbp', type=Decimal, required=True,
                        help='Explicit provisional conversion for drafts; verify before publication')
    parser.add_argument('--photos-for-sku', action='append', default=[])
    parser.add_argument('--photos-for-missing-drafts', action='store_true',
                        help='Prepare selected photos for source SKUs with no saved native ID')
    parser.add_argument('--orientation-review', type=Path,
                        default=Path(__file__).resolve().parents[2] / 'channel-update-playbook' / 'chairish-orientation-review.json')
    args = parser.parse_args()
    if not args.draft_usd_per_gbp.is_finite() or args.draft_usd_per_gbp <= 0:
        raise ValueError('A positive explicit draft conversion is required')
    args.output.mkdir(parents=True, exist_ok=True)
    source = json.loads(args.source.read_text())
    records = source['records']
    orientation_rows = (json.loads(args.orientation_review.read_text())['records']
                        if args.orientation_review.exists() else [])
    if len({r['sku'] for r in orientation_rows}) != len(orientation_rows):
        raise ValueError('Duplicate orientation review SKUs')
    orientations = {r['sku']: r for r in orientation_rows}
    if len({r['sku'] for r in records}) != len(records):
        raise ValueError('Duplicate source SKUs')
    native = native_bindings(args.output / 'draft-receipts.json')
    if set(args.photos_for_sku) - {r['sku'] for r in records}:
        raise ValueError('Requested photo SKU is not in the current source')
    photo_skus = set(args.photos_for_sku)
    if args.photos_for_missing_drafts:
        photo_skus.update(r['sku'] for r in records if r['sku'] not in native)
    # Shared photographs may appear on several components. Reuse verified bytes
    # rather than downloading another copy for each component.
    asset_cache = {}
    for manifest_path in (args.output / 'photos').glob('*/manifest.json'):
        manifest = json.loads(manifest_path.read_text())
        if not isinstance(manifest, dict):
            continue
        for photo in manifest.get('all_selected_assets', manifest.get('photos', [])):
            local = Path(photo.get('upload_path') or photo.get('path') or '')
            digest = photo.get('upload_sha256') or photo.get('sha256')
            dimensions = photo.get('upload_dimensions') or photo.get('dimensions')
            if (not local.is_file() or not digest or not dimensions or
                    max(dimensions) > 2000 or
                    hashlib.sha256(local.read_bytes()).hexdigest() != digest):
                continue
            key = (photo.get('id') or photo['url'], photo.get('content_hash') or photo['url'])
            asset_cache[key] = {
                'path': str(local.resolve()), 'upload_url': photo.get('upload_url', photo['url']),
                'bytes': local.stat().st_size, 'sha256': digest,
                'source_dimensions': photo.get('source_dimensions', photo['dimensions']),
                'dimensions': dimensions, 'format': photo.get('format'),
                'image_size_review': min(dimensions) < 575,
            }
    prepared = []
    for record in records:
        shipping = record.get('us_shipping') or {}
        dims = shipping.get('packed_cm') or []
        weight = shipping.get('packed_kg')
        parcel = None
        if len(dims) == 3 and weight:
            length, width, height = sorted(dims, reverse=True)
            parcel = (weight <= 68.0388555 and length <= 274.32 and
                      length + 2 * (width + height) <= 419.1)
        fulfilment = chairish_fulfilment(record.get('availability'), parcel)
        days = fulfilment['dispatch_working_days']
        photos = record['photos']
        row = {'catalogue_id': record['catalogue_id'], 'sku': record['sku'],
               'title': record['marketplace_title'].replace('Wall sculpture', 'Wall Sculpture'),
               'description': chairish_description(record, days),
               'source_price_gbp': record['price_gbp'],
               'draft_price_usd': str((Decimal(record['price_gbp']) * args.draft_usd_per_gbp)
                                      .quantize(Decimal('1'), rounding=ROUND_HALF_UP)),
               'dispatch_working_days': days,
               'fulfilment': fulfilment,
               'parcel_from_packing_estimate': parcel,
               'structured_dimensions': chairish_dimensions(shipping.get('source', {}).get('dimensions', '')),
               'photos': photos[:18],
               'additional_selected_photos_over_platform_limit': record['photos'][18:],
               'native_id': native.get(record['sku']),
               'action': 'UPDATE_EXISTING_ONLY' if record['sku'] in native else 'RECONCILE_BEFORE_CREATE',
               'required_before_publication': [
                   'Country of manufacture and production period',
                   'Artist Collective or manufacturer eligibility',
                   'Actual stock and condition',
                   'Actual package and fixed international delivery including taxes and duties',
                   'Verify USD conversion and disable unapproved automatic discounts'],
               'status': 'PREPARED_DRAFT_ONLY'}
        if record['sku'] in photo_skus:
            directory = args.output / 'photos' / record['sku']
            directory.mkdir(parents=True, exist_ok=True)
            missing = [(i, photo, directory) for i, photo in enumerate(photos, 1)
                       if (photo.get('id') or photo['url'], photo.get('content_hash') or photo['url'])
                       not in asset_cache]
            with ThreadPoolExecutor(max_workers=4) as pool:
                fetched = list(pool.map(checked_download, missing))
            errors = [photo for photo in fetched if photo.get('error')]
            for photo in fetched:
                if photo.get('error'):
                    continue
                key = (photo.get('id') or photo['url'], photo.get('content_hash') or photo['url'])
                asset_cache[key] = {k: photo[k] for k in
                    ('path', 'upload_url', 'bytes', 'sha256', 'source_dimensions',
                     'dimensions', 'format', 'image_size_review')}
            assets = [{**photo, **asset_cache[(photo.get('id') or photo['url'],
                                             photo.get('content_hash') or photo['url'])]}
                      for photo in photos
                      if (photo.get('id') or photo['url'], photo.get('content_hash') or photo['url'])
                      in asset_cache]
            manifest = {'sku': record['sku'], 'title': record['title'], 'photos': assets,
                        'expected_photo_count': len(photos), 'photo_errors': errors,
                        'status': 'READY' if len(assets) == len(photos) else 'INCOMPLETE_DO_NOT_UPLOAD'}
            (directory / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
            row['upload_assets_status'] = manifest['status']
            print(f"Prepared {record['sku']}: {len(assets)}/{len(photos)} images; {len(errors)} errors", flush=True)
        assets = []
        manifest_path = args.output / 'photos' / record['sku'] / 'manifest.json'
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text())
            if isinstance(manifest, dict):
                assets = manifest.get('all_selected_assets', manifest.get('photos', []))
                accepted, excluded, overflow = choose_upload_assets(assets)
                manifest.setdefault('status', 'READY' if len(assets) == len(photos) else 'INCOMPLETE_DO_NOT_UPLOAD')
                manifest.update(photos=accepted, all_selected_assets=assets,
                                expected_photo_count=len(accepted),
                                catalogue_selected_photo_count=len(photos),
                                excluded_below_upload_minimum=excluded,
                                primary_photo_requires_review=any(p.get('role') == 'primary' for p in excluded))
                manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
                row['photos'] = [{k: v for k, v in photo.items() if k not in
                                 ('path', 'upload_path')} for photo in accepted]
                row['catalogue_selected_photos'] = photos
                row['selected_photos_below_native_minimum'] = excluded
                accounted_ids = {p.get('id') or p['url'] for p in accepted + excluded}
                row['additional_selected_photos_over_platform_limit'] = [
                    p for p in photos if (p.get('id') or p['url']) not in accounted_ids]
                row['primary_photo_requires_review'] = manifest['primary_photo_requires_review']
                row['upload_assets_status'] = manifest['status']
        row['structured_dimensions'] = reviewed_orientation_dimensions(
            record, row['structured_dimensions'], orientations.get(record['sku']), assets)
        prepared.append(row)
    result = {'prepared_utc': datetime.now(timezone.utc).isoformat(),
              'source': str(args.source), 'count': len(prepared),
              'draft_usd_per_gbp': str(args.draft_usd_per_gbp),
              'fx_status': 'PROVISIONAL_DRAFT_CONVERSION_REVERIFY_BEFORE_PUBLICATION',
              'status': 'PREPARED_NOT_PUBLISHED', 'records': prepared}
    (args.output / 'prepared-native-drafts.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'records': len(prepared), 'existing_native_ids': len(native)}))


if __name__ == '__main__':
    main()
