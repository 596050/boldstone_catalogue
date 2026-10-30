"""Collect Gold source records and public images while preserving access failures."""
import concurrent.futures
import hashlib
import importlib.util
import json
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import openpyxl

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
now = lambda: datetime.now(timezone.utc).isoformat()
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()


def write(name, value):
    (HERE / name).write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + '\n')


def fetch(url, filename):
    path = HERE / filename
    try:
        with urllib.request.urlopen(url, timeout=45) as response:
            data, status = response.read(), response.status
        path.write_bytes(data)
        return {'status': 'PASS', 'checked_utc': now(), 'url': url, 'http_status': status,
                'local_path': str(path), 'size': len(data), 'sha256': sha(path)}
    except urllib.error.HTTPError as error:
        return {'status': 'HTTP_ACCESS_RESULT', 'checked_utc': now(), 'url': url,
                'http_status': error.code, 'retried_or_bypassed': False}


def main():
    assert not (HERE / 'public-source-receipts.json').exists(), 'Do not repeat saved source requests'
    source = ROOT.parent / 'Boldstone_Wall_Sculptures_Matched_All_Fields_2026-10-15.xlsx'
    source_sha = sha(source)
    assert source_sha == '7e6911a88ea9c9fd3214bdf860e24d6ad72ee755302efd6a9acc4db85c52c5c9'
    workbook = openpyxl.load_workbook(source, read_only=True, data_only=True)
    matches = {}
    for tab in ['SS Wall Products', 'SH Wall Products']:
        ws = workbook[tab]
        headers = [x.value for x in next(ws.iter_rows(min_row=5, max_row=5))]
        index = headers.index('SKU') if 'SKU' in headers else headers.index('Variant SKU')
        matches[tab] = [{'row': n, 'fields': dict(zip(headers, row))}
            for n, row in enumerate(ws.iter_rows(min_row=6, values_only=True), 6)
            if row[index] in ['SQ6244576', 'GDRS-1-35.20']]
    workbook.close()
    assert len(matches['SS Wall Products']) == 2 and len(matches['SH Wall Products']) == 1
    write('native-platform-source-check.json', {'status': 'PASS', 'checked_utc': now(),
        'source_workbook': str(source), 'source_sha256': source_sha, 'matches': matches})
    ss = {x['fields']['SKU']: x for x in matches['SS Wall Products']}
    urls = ['https://boldstonesculpture.com/buy/p/gold-leaf-wave-relief-sculpture',
            'https://boldstonesculpture.com/buy/p/golden-dune-ripple-and-spiral-wall-sculpture']
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(fetch, url, f'public-page-{index:02d}.html') for index, url in enumerate(urls, 1)]
        pages = [future.result() for future in futures]
    write('public-source-receipts.json', pages)
    utility_path = HERE.parent / 'copper/collect_sources.py'
    spec = importlib.util.spec_from_file_location('copper_read_utilities', utility_path)
    utility = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(utility)
    utility.HERE = HERE
    claims = []
    for receipt in pages:
        if receipt['status'] == 'PASS':
            html = Path(receipt['local_path']).read_text()
            parser = utility.Page()
            parser.feed(html)
            text = ' '.join(' '.join(parser.text).split())
            claims.append({'url': receipt['url'], 'products': parser.products, 'visible_text': text})
    write('public-page-claims.json', claims)
    gallery = ss['SQ6244576']['fields']['Hosted Image URLs'].split()
    assert len(gallery) == 5
    # Each URL was observed by following the five primary public gallery links;
    # the web image-fetch timeouts are preserved separately from these GETs.
    write('public-gallery-web-navigation.json', {'source': urls[0], 'urls': gallery,
        'web_navigation_image_results': ['TimeoutError'] * 5,
        'scope': 'Five links observed through web.run; normal individual CDN GETs below are separate requests.'})
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        futures = [pool.submit(fetch, url, f'public-gallery-{index:02d}.jpg') for index, url in enumerate(gallery, 1)]
        galleries = [future.result() for future in futures]
    write('public-gallery-download-receipts.json', galleries)
    assert all(x['status'] == 'PASS' and x['http_status'] == 200 for x in galleries)
    originals = json.loads((HERE / 'download-receipts.json').read_text())
    utility.sheet([(Path(x['local_path']), x['name'].split('__')[-1]) for x in originals],
                  'selected-originals-review.jpg')
    utility.sheet([(Path(x['local_path']), f'Public gallery {i}') for i, x in enumerate(galleries, 1)],
                  'public-gallery-review.jpg')
    assert sha(source) == source_sha
    print(json.dumps({'status': 'PASS', 'native_ss_rows': [x['row'] for x in matches['SS Wall Products']],
        'native_sh_rows': [x['row'] for x in matches['SH Wall Products']],
        'public_page_http_results': [x['http_status'] for x in pages], 'public_gallery_images': len(galleries)}))


if __name__ == '__main__':
    main()
