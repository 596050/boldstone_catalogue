"""Prepare evidence-preserving Saatchi records; never publish or infer provenance.

Optional image checks stream only enough public image bytes to read headers.
They do not retain downloaded pictures or change the catalogue's photo order.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import sys
from urllib.parse import urlparse
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from channel_content import saatchi_description


def native_artwork_bindings(receipts_path):
    """Retain accepted creations across preparation reruns; fail on ambiguity."""
    bindings = {'SQ0717348': '14226583', 'SQ1068535': '14379041'}
    owners = {native_id: sku for sku, native_id in bindings.items()}
    if not receipts_path.exists():
        return bindings
    receipts = json.loads(receipts_path.read_text())
    if not isinstance(receipts, list):
        raise ValueError('Native artwork receipts must be a list')
    for receipt in receipts:
        sku = receipt.get('sku') if isinstance(receipt, dict) else None
        native_id = receipt.get('artwork_id') if isinstance(receipt, dict) else None
        saved_draft = isinstance(receipt, dict) and receipt.get('status') == 'DRAFT_PRIMARY_ONLY_NOT_PUBLISHED'
        published = isinstance(receipt, dict) and receipt.get('status') == 'PUBLISHED_NATIVE_READBACK_VERIFIED'
        if published:
            public_url_value = receipt.get('public_url')
            public_url = urlparse(public_url_value if isinstance(public_url_value, str) else '')
            published = (receipt.get('verified_visibility') == 'Published' and
                         public_url.scheme == 'https' and
                         public_url.hostname in ('saatchiart.com', 'www.saatchiart.com') and
                         isinstance(native_id, str) and
                         public_url.path.endswith('/' + native_id + '/view') and
                         isinstance(receipt.get('publication_evidence'), str) and
                         bool(receipt['publication_evidence'].strip()) and
                         isinstance(receipt.get('verified_utc'), str) and
                         bool(receipt['verified_utc'].strip()))
        if (not isinstance(sku, str) or not sku.strip() or
                not isinstance(native_id, str) or not native_id.isdecimal() or
                not (saved_draft or published)):
            raise ValueError('Native artwork receipt is incomplete or unverified')
        if sku in bindings and bindings[sku] != native_id:
            raise ValueError('Conflicting native artwork IDs for ' + sku)
        if native_id in owners and owners[native_id] != sku:
            raise ValueError('A native artwork ID is assigned to multiple SKUs')
        bindings[sku] = native_id
        owners[native_id] = sku
    return bindings


def channel_primary_selection(record, photo_checks, receipts, alternatives):
    """Keep verified channel photos without changing catalogue ordering.

    A removed/reclassified image needs review rather than silently reverting to
    an unsuitable catalogue primary or using an in-situ/group photo.
    """
    saved = next((r for r in receipts if r['sku'] == record['sku']), None)
    alternative = next((r for r in alternatives if r['sku'] == record['sku']), None)
    if saved and saved.get('primary_photo_id'):
        photo_id = saved['primary_photo_id']
        strategy = 'PRESERVE_VERIFIED_NATIVE_PRIMARY'
    elif alternative:
        if alternative.get('status') not in ('READY_FOR_CHANNEL_DRAFT', 'DRAFT_PRIMARY_ONLY_NOT_PUBLISHED'):
            raise ValueError('Unreviewed channel primary for ' + record['sku'])
        photo_id = alternative['photo']['photo_id']
        strategy = 'VISUALLY_REVIEWED_LISTING_ALTERNATIVE'
    else:
        photo_id = photo_checks[0]['id'] if photo_checks else None
        strategy = 'CATALOGUE_PRIMARY'
    photo = next((p for p in photo_checks if p['id'] == photo_id), None)
    eligible = bool(photo and photo.get('role') in ('primary', 'listing') and
                    photo['header_check']['status'] == 'PASS_IMAGE_HEADER_CHECK')
    return {'photo_id': photo_id, 'strategy': strategy,
            'status': 'READY_IMAGE' if eligible else 'NEEDS_IMAGE_REVIEW',
            'catalogue_primary_unchanged': True}


def crate_required(dimensions_cm, weight_kg):
    """Apply inclusive Saatchi thresholds; missing measurements stay unknown."""
    dimensions = list(dimensions_cm or [])
    for value in dimensions + ([weight_kg] if weight_kg is not None else []):
        if (isinstance(value, bool) or not isinstance(value, (int, float)) or
                not math.isfinite(value) or value <= 0):
            raise ValueError('Artwork dimensions and weight must be positive finite numbers')
    if any(value >= 30.48 for value in dimensions):
        return True
    if weight_kg is not None and weight_kg >= 2.26796185:
        return True
    return False if len(dimensions) == 3 and weight_kg is not None else None


def image_header(url):
    from PIL import ImageFile
    result = {'url': url, 'checked_utc': datetime.now(timezone.utc).isoformat()}
    if urlparse(url).scheme != 'https' or urlparse(url).hostname != 'images.squarespace-cdn.com':
        return {**result, 'status': 'UNSUPPORTED_SOURCE_HOST'}
    try:
        request = Request(url, headers={'User-Agent': 'Boldstone catalogue image preflight',
                                       'Range': 'bytes=0-1048575'})
        parser = ImageFile.Parser()
        count = 0
        with urlopen(request, timeout=20) as response:
            length = response.headers.get('Content-Length')
            content_range = response.headers.get('Content-Range', '')
            total = (content_range.rsplit('/', 1)[-1] if '/' in content_range else
                     length if response.status == 200 else None)
            result['file_bytes'] = int(total) if total and total.isdigit() else None
            while count < 1048576:
                chunk = response.read(min(16384, 1048576-count))
                if not chunk:
                    break
                count += len(chunk)
                parser.feed(chunk)
                if parser.image:
                    break
        result['bytes_read'] = count
        if not parser.image:
            return {**result, 'status': 'DIMENSIONS_NOT_DETERMINED'}
        width, height = parser.image.size
        result.update(width=width, height=height, format=parser.image.format, mode=parser.image.mode)
        problems = []
        if width < 1500 or height < 1200:
            problems.append('BELOW_NATIVE_1500W_1200H_MINIMUM')
        if parser.image.format not in ('JPEG', 'PNG'):
            problems.append('UNSUPPORTED_FORMAT')
        if result['file_bytes'] is None:
            problems.append('FILE_SIZE_NOT_VERIFIED')
        elif result['file_bytes'] >= 50_000_000:
            problems.append('AT_OR_OVER_50_MB')
        if parser.image.mode not in ('RGB', 'RGBA'):
            problems.append('COLOUR_MODE_REQUIRES_CHECK')
        result['problems'] = problems
        result['status'] = 'PASS_IMAGE_HEADER_CHECK' if not problems else 'NEEDS_ATTENTION'
        return result
    except Exception as exc:
        return {**result, 'status': 'CHECK_FAILED', 'error': str(exc)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('source', type=Path)
    ap.add_argument('output', type=Path)
    ap.add_argument('--check-images', action='store_true')
    ap.add_argument('--native-receipts', type=Path,
                    help='Accepted native draft receipts; defaults to the output directory. Reuse the latest receipts for a new output directory.')
    ap.add_argument('--reviewed-alternatives', type=Path,
                    help='Visually reviewed listing-photo alternatives; defaults to listing-alternative-selection.json in the output directory.')
    args = ap.parse_args()
    source = json.loads(args.source.read_text())
    records = source['records']
    if len({r['sku'] for r in records}) != len(records):
        raise ValueError('Source has duplicate seller SKUs')
    args.output.mkdir(parents=True, exist_ok=True)
    receipts_path = args.native_receipts or args.output / 'primary-draft-receipts.json'
    if args.native_receipts and not receipts_path.is_file():
        raise ValueError('The supplied native receipt file is missing')
    native_bindings = native_artwork_bindings(receipts_path)
    receipts = json.loads(receipts_path.read_text()) if receipts_path.exists() else []
    alternatives_path = args.reviewed_alternatives or args.output / 'listing-alternative-selection.json'
    if args.reviewed_alternatives and not alternatives_path.is_file():
        raise ValueError('The supplied reviewed alternative file is missing')
    alternatives = json.loads(alternatives_path.read_text()) if alternatives_path.exists() else []
    if not isinstance(alternatives, list) or any(not isinstance(r, dict) or not r.get('sku') for r in alternatives):
        raise ValueError('Reviewed alternatives must be a list of SKU records')
    if len({r['sku'] for r in alternatives}) != len(alternatives):
        raise ValueError('Duplicate SKUs in reviewed alternatives')
    headers_path = args.output / 'image-header-checks.json'
    checks = json.loads(headers_path.read_text()) if headers_path.exists() else {}
    if args.check_images:
        urls = sorted({p['url'] for r in records for p in r['photos']})
        pending = [u for u in urls if u not in checks]
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = {pool.submit(image_header, u): u for u in pending}
            for n, future in enumerate(as_completed(futures), 1):
                checks[futures[future]] = future.result()
                if n % 50 == 0 or n == len(pending):
                    headers_path.write_text(json.dumps(checks, indent=2)+'\n')
                    print(f'Checked {n}/{len(pending)} image headers', flush=True)
    prepared = []
    for r in records:
        description = saatchi_description(r)
        photo_checks = [{**p, 'header_check': checks.get(p['url'], {'status': 'NOT_CHECKED'})}
                        for p in r['photos']]
        shipping = r.get('us_shipping') or {}
        dims = shipping.get('artwork_upper_cm') or []
        weight = shipping.get('artwork_upper_kg')
        crate = crate_required(dims, weight)
        prepared.append({
            'catalogue_id': r['catalogue_id'], 'sku': r['sku'], 'title': r['title'],
            'source_price_gbp': r['price_gbp'], 'description': description,
            'description_characters': len(description), 'dispatch_working_days': 3,
            'material_description': r['material'], 'surface_effect': r['surface_effect'],
            'source_dimensions_and_weight': shipping.get('source'),
            'custom_wood_crate_required_from_catalogue_estimates': crate,
            'packed_measurements_status': 'ESTIMATED_NOT_MEASURED_CRATE',
            'photos': photo_checks,
            'primary_image_header_pass': bool(photo_checks and photo_checks[0]['header_check']['status'] == 'PASS_IMAGE_HEADER_CHECK'),
            'channel_primary': channel_primary_selection(r, photo_checks, receipts, alternatives),
            'creation_year': None, 'edition_status': None, 'signature_status': None,
            'native_artwork_id': native_bindings.get(r['sku']),
            'native_action': 'UPDATE_EXISTING_ONLY' if r['sku'] in native_bindings else 'RECONCILE_BEFORE_CREATE',
            'publication_status': 'PREPARED_ONLY_MATCH_NATIVE_ID_BEFORE_UPLOAD',
            'required_before_publication': ['Actual artwork creation year', 'Truthful original/edition status',
                'Available physical stock and three-day courier readiness',
                'Applicable packing/crate measurements and costs', 'Native category and account acceptance'],
        })
    result = {'prepared_utc': datetime.now(timezone.utc).isoformat(), 'source': str(args.source),
              'source_cutoff': source.get('source_cutoff'), 'records': prepared,
              'record_count': len(prepared), 'status': 'PREPARED_NOT_UPLOADED',
              'photo_checks': len(checks),
              'primary_images_passing': sum(r['primary_image_header_pass'] for r in prepared),
              'native_receipts_source': str(receipts_path),
              'reviewed_alternatives_source': str(alternatives_path) if alternatives_path.exists() else None,
              'channel_primary_images_ready': sum(r['channel_primary']['status'] == 'READY_IMAGE' for r in prepared),
              'native_ids_already_in_use': native_bindings}
    target = args.output / 'prepared-catalogue.json'
    target.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({k: result[k] for k in ('record_count', 'photo_checks', 'primary_images_passing', 'status')}))


if __name__ == '__main__':
    main()
