import concurrent.futures, hashlib, json
from pathlib import Path
from PIL import Image, ImageDraw, ImageOps
from capture_public_inventory import OUT, digest, fetch, locator, now, save

REGISTER = Path('/Users/tprice/Documents/boldstone/sculpture-catalogue/components/evidence/component_register.json')

def capture():
    cases = json.loads((OUT / 'CASE_SOURCE_RECORDS.json').read_text())['case_source_records']
    assets = json.loads(REGISTER.read_text())['assets']
    asset_by = {a['id']: (i, a) for i, a in enumerate(assets)}
    requests = []
    public_media = []
    for case in cases:
        product = case['direct_product_check'].get('detail_product') or case.get('fresh_collection_product')
        if product:
            for index, media in enumerate(product['native_media_items']):
                requests.append((case['offer_ref'], index, media, product['source_locator']))
    def one(args):
        offer, index, media, source_locator = args
        _, receipt = fetch(media['assetUrl'], 'image-' + offer + '-' + str(index).zfill(2) + '-' + media['id'])
        record = {'offer_ref': offer, 'gallery_index': index, 'native_media_id': media['id'], 'native_system_data_id': media.get('systemDataId'), 'media_source_locator': dict(source_locator, json_pointer=source_locator['json_pointer'] + '/items/' + str(index)), 'receipt': receipt}
        try:
            with Image.open(receipt['body_path']) as image:
                image.load()
                rgb = image.convert('RGB')
                record.update(image_decode_success=True, pixel_dimensions=list(rgb.size), decoded_rgb_sha256=hashlib.sha256(rgb.tobytes()).hexdigest())
        except Exception as error:
            record.update(image_decode_success=False, decode_error=str(error))
        return record
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        public_media = list(pool.map(one, requests))
    cached = []
    for case in cases:
        file_id = case['frozen_master_source_offer']['image_file_id']
        if file_id not in asset_by:
            cached.append({'offer_ref': case['offer_ref'], 'file_id': file_id, 'error': 'NOT_IN_CACHED_ASSET_REGISTER'})
            continue
        index, asset = asset_by[file_id]
        record = {'offer_ref': case['offer_ref'], 'asset': asset, 'asset_source_locator': {'path': str(REGISTER), 'json_pointer': '/assets/' + str(index), 'sha256': digest(REGISTER)}, 'available_local_images': []}
        for key in ['thumb', 'full']:
            path = Path(asset.get(key, ''))
            if asset.get(key) and path.is_file():
                record['available_local_images'].append({'kind': key, 'path': str(path), 'sha256': digest(path), 'bytes': path.stat().st_size})
        cached.append(record)
    result = {'schema': 'boldstone.listing-overlap-image-capture.v1', 'created_utc': now(), 'public_media': public_media, 'cached_source_media': cached, 'limits': ['Downloaded only public Squarespace CDN image URLs evidenced in native product JSON; cached private images were read locally only.', 'Byte/pixel equality concerns images, not equality of a physical sculpture cast.', 'Cached thumbnails are visual references, not original-file byte verification.']}
    save('CASE_IMAGE_RECEIPTS.json', result)
    contacts = []
    pairs = [('rust', ['O051', 'O067']), ('verdigris', ['O004', 'O038']), ('moonwater', ['O015', 'O059']), ('gold-historical', ['O002', 'O039']), ('silver-historical', ['O003', 'O064'])]
    for label, offers in pairs:
        tiles = []
        for offer in offers:
            for record in public_media:
                if record['offer_ref'] == offer and record.get('image_decode_success'):
                    tiles.append((record['receipt']['body_path'], offer + ' public gallery ' + str(record['gallery_index']) + '\n' + record['native_media_id']))
            for record in cached:
                if record['offer_ref'] == offer and record.get('available_local_images'):
                    available = record['available_local_images'][-1]
                    tiles.append((available['path'], offer + ' cached source selected\n' + record['asset']['id']))
        cols = min(4, len(tiles))
        rows = (len(tiles) + cols - 1) // cols
        sheet = Image.new('RGB', (cols * 400, rows * 480), 'white')
        draw = ImageDraw.Draw(sheet)
        for i, (path, caption) in enumerate(tiles):
            x, y = (i % cols) * 400, (i // cols) * 480
            with Image.open(path) as image:
                image = ImageOps.exif_transpose(image).convert('RGB')
                image.thumbnail((390, 420))
                sheet.paste(image, (x + (400-image.width)//2, y + 45 + (425-image.height)//2))
            draw.multiline_text((x + 6, y + 5), caption, fill='black')
        contact = OUT / ('CONTACT_' + label + '.jpg')
        sheet.save(contact, quality=92)
        contacts.append({'pair': label, 'offers': offers, 'path': str(contact), 'sha256': digest(contact), 'tile_count': len(tiles)})
    save('CONTACT_SHEETS.json', contacts)
    print(json.dumps({'public_media_count': len(public_media), 'successful_image_decodes': sum(r.get('image_decode_success', False) for r in public_media), 'cached_reference_images': sum(bool(r.get('available_local_images')) for r in cached), 'contacts': contacts}, indent=2))

if __name__ == '__main__':
    capture()
