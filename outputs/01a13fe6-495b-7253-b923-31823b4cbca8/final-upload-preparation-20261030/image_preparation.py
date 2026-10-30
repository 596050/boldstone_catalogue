"""Pinned read-only original fetches and preview sheets for selected photographs."""
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import urlencode
from urllib.error import HTTPError
from concurrent.futures import ThreadPoolExecutor
import json, time, sys, shutil

OUT = Path(__file__).resolve().parent
BASE = 'http://127.0.0.1:8767'

def api(path, data=None):
    headers = {'Content-Type': 'application/json', 'Origin': BASE}
    if data is not None:
        headers['X-Review-Token'] = json.load(urlopen(BASE + '/api/bootstrap', timeout=90))['csrf_token']
    req = Request(BASE + path, data=json.dumps(data).encode() if data is not None else None, headers=headers)
    with urlopen(req, timeout=120) as r:
        return json.load(r)

def selected():
    snap = json.loads((OUT / 'catalogue-snapshot.json').read_text())
    products = {p['id']: p for p in snap['products']}
    items = {}
    for r in snap['images']:
        if 'listing' not in r['image'].get('selected_uses', []) or products[r['product_id']]['listing_decision'] == 'exclude':
            continue
        a = r['image']
        item = items.setdefault(a['id'], {'image': a, 'associations': []})
        item['associations'].append({'product_id': r['product_id'], 'name': r['product_name'], 'choice': r['choice'], 'metadata': r['metadata']})
    result = sorted(items.values(), key=lambda i: (i['image']['family'].casefold(), i['image']['name'].casefold(), i['image']['id']))
    for n, item in enumerate(result, 1):
        item['number'] = n
    (OUT / 'selected-images.json').write_text(json.dumps(result, indent=2, ensure_ascii=False))
    return result

def originals(items):
    path = OUT / 'original-dimensions.jsonl'
    done = {r['id']: r for r in (json.loads(l) for l in path.read_text().splitlines())} if path.exists() else {}
    queue = [i['image'] for i in items if not i['image']['original'].get('dimensions')]
    for n, a in enumerate(queue, 1):
        if (OUT / 'stop-serial').exists():
            break
        if done.get(a['id'], {}).get('status') == 'verified':
            continue
        receipt = {'id': a['id'], 'name': a['name'], 'expected_hash': a['original'].get('dropbox_content_hash')}
        for attempt in range(3):
            try:
                answer = api('/api/original', {'asset_id': a['id'], 'expected_content_hash': receipt['expected_hash']})
                original = answer['asset']['original']
                assert original['dropbox_content_hash'] == receipt['expected_hash']
                receipt.update(status='verified' if original.get('dimensions') else 'dimensions_unreadable', original=original)
                break
            except HTTPError as e:
                try: err = json.load(e).get('error', 'Request failed')
                except Exception: err = 'Request failed'
                receipt.update(status='failed', error=err, http_status=e.code)
                if e.code == 409 and 'changed' in err:
                    break
                time.sleep(3 * (attempt + 1))
            except Exception as e:
                receipt.update(status='failed', error_type=type(e).__name__)
                time.sleep(3 * (attempt + 1))
        with path.open('a') as f:
            f.write(json.dumps(receipt) + '\n')
        print(json.dumps({'checked': n, 'total': len(queue), 'status': receipt['status'], 'name': a['name']}), flush=True)

def sheets(items):
    from PIL import Image, ImageOps, ImageDraw, ImageFont
    directory = OUT / 'previews'; directory.mkdir(exist_ok=True)
    def fetch(item):
        target = directory / (str(item['number']) + '.image')
        if not target.exists():
            try:
                req = BASE + '/api/image?' + urlencode({'id': item['image']['id'], 'size': 'thumb'})
                with urlopen(req, timeout=60) as response:
                    target.write_bytes(response.read())
            except Exception: pass
        return target
    with ThreadPoolExecutor(max_workers=3) as pool:
        list(pool.map(fetch, items))
    for page, start in enumerate(range(0, len(items), 20), 1):
        canvas = Image.new('RGB', (1500, 1340), 'white'); draw = ImageDraw.Draw(canvas)
        for j, item in enumerate(items[start:start+20]):
            x, y = (j%5)*300, (j//5)*335
            try:
                im = ImageOps.exif_transpose(Image.open(directory / (str(item['number']) + '.image'))).convert('RGB')
                im.thumbnail((288, 265))
                canvas.paste(im, (x+(300-im.width)//2, y+(265-im.height)//2))
            except Exception: draw.text((x+10, y+100), 'Preview unavailable', fill='black')
            label = str(item['number']) + ': ' + item['image']['folder_label']
            for k in range(0, min(len(label), 138), 46):
                draw.text((x+5, y+270+(k//46)*17), label[k:k+46], fill='black')
        canvas.save(OUT / ('contact-%02d.jpg' % page), quality=90)
    print(json.dumps({'selected_distinct': len(items), 'contact_sheets': page}))

if __name__ == '__main__':
    items = selected()
    if sys.argv[-1] == 'originals': originals(items)
    elif sys.argv[-1] == 'sheets': sheets(items)
