import concurrent.futures, hashlib, json
from PIL import Image, ImageDraw, ImageOps
from capture_public_inventory import OUT, OLD, digest, fetch, now, save

def capture():
    cases = json.loads((OUT / 'CASE_SOURCE_RECORDS.json').read_text())['case_source_records']
    historical = json.loads(OLD.read_text())
    requests = []
    for case in cases:
        if case['offer_ref'] not in ['O039', 'O064']:
            continue
        index, product = next((i, p) for i, p in enumerate(historical['products']) if p['native_product_id'] == case['native_product_id'])
        seen = set()
        for observation_index, observation in enumerate(product['observations']):
            for gallery_index, url in enumerate(observation.get('hosted_image_urls', [])):
                if url in seen:
                    continue
                seen.add(url)
                requests.append((case['offer_ref'], gallery_index, url, {'path': str(OLD), 'json_pointer': '/products/' + str(index) + '/observations/' + str(observation_index) + '/hosted_image_urls/' + str(gallery_index), 'sha256': digest(OLD)}, observation.get('source_locator') or observation.get('product_row_locator')))
    def one(args):
        offer, index, url, old_locator, native_locator = args
        _, receipt = fetch(url, 'historical-image-' + offer + '-' + str(index).zfill(2))
        record = {'offer_ref': offer, 'historical_gallery_index': index, 'historical_url_source_locator': old_locator, 'native_original_source_locator': native_locator, 'receipt': receipt, 'asset_access_does_not_establish_current_product_page_presence': True}
        try:
            with Image.open(receipt['body_path']) as image:
                image.load()
                rgb = image.convert('RGB')
                record.update(image_decode_success=True, pixel_dimensions=list(rgb.size), decoded_rgb_sha256=hashlib.sha256(rgb.tobytes()).hexdigest())
        except Exception as error:
            record.update(image_decode_success=False, decode_error=str(error))
        return record
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        records = list(pool.map(one, requests))
    save('HISTORICAL_MEDIA_RECEIPTS.json', {'schema': 'boldstone.historical-native-linked-public-cdn-media.v1', 'created_utc': now(), 'media': records, 'limit': 'Current access to historical CDN image URLs is distinct from the current public product page, inventory presence, physical stock or listing approval.'})
    for offer in ['O039', 'O064']:
        rows = [r for r in records if r['offer_ref'] == offer and r.get('image_decode_success')]
        cols = min(4, len(rows))
        sheet = Image.new('RGB', (cols * 400, ((len(rows)+cols-1)//cols)*480), 'white')
        draw = ImageDraw.Draw(sheet)
        for i, record in enumerate(rows):
            x, y = (i % cols)*400, (i//cols)*480
            with Image.open(record['receipt']['body_path']) as image:
                image = ImageOps.exif_transpose(image).convert('RGB')
                image.thumbnail((390,420))
                sheet.paste(image, (x+(400-image.width)//2, y+45+(425-image.height)//2))
            draw.text((x+5,y+5), offer + ' historical CDN ' + str(record['historical_gallery_index']) + '\nproduct page HTTP 404', fill='black')
        sheet.save(OUT / ('CONTACT_' + offer + '_historical_CDN.jpg'), quality=92)
    print(json.dumps({'historical_media_count': len(records), 'successful_decodes': sum(r.get('image_decode_success',False) for r in records)}))

if __name__ == '__main__':
    capture()
