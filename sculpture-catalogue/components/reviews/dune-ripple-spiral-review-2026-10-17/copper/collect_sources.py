"""Read the native export and current public Copper source without modifying either."""
import concurrent.futures
import hashlib
import json
import re
import urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

import openpyxl
from PIL import Image, ImageDraw, ImageOps

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parents[4] / 'Boldstone_Wall_Sculptures_Matched_All_Fields_2026-10-15.xlsx'
SKU = 'EBAY-188654831217'
URL = 'https://boldstonesculpture.com/buy/p/wave-relief-copper-wall-sculpture'
now = lambda: datetime.now(timezone.utc).isoformat()
sha = lambda data: hashlib.sha256(data).hexdigest()


def write(name, value):
    (HERE / name).write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + '\n')


class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hidden = 0
        self.jsonld = False
        self.json_buffer = []
        self.products = []
        self.text = []

    def handle_starttag(self, tag, attrs):
        if tag in ['script', 'style']:
            self.hidden += 1
        if tag == 'script' and dict(attrs).get('type') == 'application/ld+json':
            self.jsonld = True
            self.json_buffer = []

    def handle_data(self, data):
        if self.jsonld:
            self.json_buffer.append(data)
        elif not self.hidden:
            self.text.append(data)

    def handle_endtag(self, tag):
        if tag == 'script' and self.jsonld:
            value = json.loads(''.join(self.json_buffer))
            self.find_products(value)
            self.jsonld = False
        if tag in ['script', 'style']:
            self.hidden = max(0, self.hidden - 1)

    def find_products(self, value):
        if isinstance(value, dict):
            if value.get('@type') == 'Product':
                self.products.append(value)
            for child in value.values():
                self.find_products(child)
        elif isinstance(value, list):
            for child in value:
                self.find_products(child)


def get(url, file):
    with urllib.request.urlopen(url, timeout=45) as response:
        data = response.read()
        status = response.status
    assert status == 200
    file.write_bytes(data)
    return {'status': 'PASS', 'checked_utc': now(), 'url': url, 'http_status': status,
            'local_path': str(file), 'size': len(data), 'sha256': sha(data)}


def sheet(paths, name, columns=3):
    width, height = 420, 520
    rows = (len(paths) + columns - 1) // columns
    canvas = Image.new('RGB', (columns * width, rows * height), 'white')
    draw = ImageDraw.Draw(canvas)
    for index, (path, label) in enumerate(paths):
        with Image.open(path) as original:
            photo = ImageOps.exif_transpose(original).convert('RGB')
            photo.thumbnail((width - 20, height - 55))
            x, y = (index % columns) * width, (index // columns) * height
            canvas.paste(photo, (x + (width - photo.width) // 2, y))
            draw.text((x + 8, y + height - 47), label, fill='black')
    canvas.save(HERE / name, quality=92)


def main():
    workbook_sha = sha(SOURCE.read_bytes())
    assert workbook_sha == '7e6911a88ea9c9fd3214bdf860e24d6ad72ee755302efd6a9acc4db85c52c5c9'
    workbook = openpyxl.load_workbook(SOURCE, read_only=True, data_only=True)
    matches = {}
    for tab in ['SS Wall Products', 'SH Wall Products']:
        worksheet = workbook[tab]
        headers = [cell.value for cell in next(worksheet.iter_rows(min_row=5, max_row=5))]
        sku_index = headers.index('SKU') if 'SKU' in headers else headers.index('Variant SKU')
        matches[tab] = []
        for number, row in enumerate(worksheet.iter_rows(min_row=6, values_only=True), start=6):
            if row[sku_index] == SKU:
                matches[tab].append({'row': number, 'fields': dict(zip(headers, row))})
    workbook.close()
    assert len(matches['SS Wall Products']) == 1 and matches['SS Wall Products'][0]['row'] == 57
    assert not matches['SH Wall Products']
    native = {'status': 'PASS', 'checked_utc': now(), 'source_workbook': str(SOURCE),
              'source_sha256': workbook_sha, 'sku': SKU, 'matches': matches}
    write('native-platform-source-check.json', native)
    fields = matches['SS Wall Products'][0]['fields']
    # The ordinary page GET returned 403. Preserve it and use the independently
    # successful web-tool page evidence; never retry or bypass the blocked GET.
    receipt = json.loads((HERE / 'public-page-http-receipt.json').read_text())
    assert receipt['http_status'] == 403 and not receipt['ordinary_get_retried']
    text = json.loads((HERE / 'public-web-result.json').read_text())
    assert isinstance(text, str) and URL in text
    assert '£40.33' in text and '35 x 21 x 6 cm' in text and 'plaster and sand' in text
    assert 'Add To Cart' in text
    (HERE / 'public-page-visible-text.txt').write_text(text + '\n')
    gallery_urls = fields['Hosted Image URLs'].split()
    # These five URLs were separately observed by following the current page's
    # five gallery links through web.run, including its preserved image2 timeout.
    current_gallery = [
        'https://images.squarespace-cdn.com/content/v1/66abcbd768fd043d92325d96/1784308251243-XKIHYN7M79AN2R6EB399/s-l1600.jpg',
        'https://images.squarespace-cdn.com/content/v1/66abcbd768fd043d92325d96/1784308252993-NUW9N2JQQRCF0A4SVWCE/s-l1600.jpg',
        'https://images.squarespace-cdn.com/content/v1/66abcbd768fd043d92325d96/1784308254511-IOUD2TDTFJNSL3EKBVUN/s-l1600.jpg',
        'https://images.squarespace-cdn.com/content/v1/66abcbd768fd043d92325d96/1784308255484-NNXZZOJ0GTV0FYBPCATZ/s-l1600.jpg',
        'https://images.squarespace-cdn.com/content/v1/66abcbd768fd043d92325d96/1784308256685-BDNIUZHKAEU79XW6BBHX/s-l1600.jpg']
    assert gallery_urls == current_gallery
    write('public-web-specification-check.json', {'status': 'PASS', 'checked_utc': now(),
        'source': 'public-web-result.json', 'source_url': URL, 'price': 40.33, 'currency': 'GBP',
        'dimensions_cm': [35, 21, 6], 'material_claim': 'Plaster, sand, copper surface effect',
        'visible_add_to_cart': True, 'public_schema_availability': None, 'public_sku_independently_checked': False,
        'gallery_urls': gallery_urls, 'web_gallery_image2_navigation': 'TimeoutError',
        'ordinary_page_get_403_preserved_and_not_retried': True})
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        futures = [pool.submit(get, url, HERE / f'public-gallery-{index:02d}.jpg')
                   for index, url in enumerate(gallery_urls, 1)]
        galleries = [future.result() for future in futures]
    write('public-gallery-download-receipts.json', galleries)
    originals = json.loads((HERE / 'download-receipts.json').read_text())
    originals.sort(key=lambda item: item['name'])
    sheet([(Path(item['local_path']), item['name']) for item in originals], 'dropbox-originals-review.jpg', 2)
    sheet([(Path(item['local_path']), f'Public gallery {index}') for index, item in enumerate(galleries, 1)],
          'public-gallery-review.jpg')
    assert sha(SOURCE.read_bytes()) == workbook_sha
    print(json.dumps({'status': 'PASS', 'squarespace_row': 57, 'shopify_sku_matches': 0,
                      'public_price_GBP': 40.33, 'public_gallery_images': len(galleries),
                      'source_workbook_unchanged': True}))


if __name__ == '__main__':
    main()
