"""Cache current previews and create inspection-only contact sheets for the five MCP1-related folders."""
import concurrent.futures
import hashlib
import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
read = lambda p: json.loads(p.read_text())
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    census = read(HERE / 'media-census.json')
    assert all(not x['result']['has_more'] and not x['result']['cursor'] for x in census['listings'])
    files = [x for row in census['listings'] for x in row['result']['entries'] if x['object_type'] == 'file']
    assert len(files) == 69 and len({x['file_id'] for x in files}) == 69
    links = {x['file_name']: x for x in read(HERE / 'metadata-links.json')['results']}
    (HERE / 'thumbnails').mkdir(exist_ok=True)
    def cache(entry):
        path = HERE / 'thumbnails' / (entry['name'] + '.preview')
        try:
            if not path.exists():
                with urllib.request.urlopen(links[entry['file_id']]['thumbnail_url'], timeout=35) as response:
                    assert response.status == 200
                    data = response.read()
                path.write_bytes(data)
            with Image.open(path) as im:
                im.verify()
            return {'file_id': entry['file_id'], 'name': entry['name'], 'preview_path': str(path), 'sha256': sha(path)}
        except Exception as e:
            return {'file_id': entry['file_id'], 'name': entry['name'], 'error_type': type(e).__name__}
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        records = list(pool.map(cache, files))
    errors = [x for x in records if 'error_type' in x]
    assert not errors, json.dumps(errors)
    cached = {x['file_id']: x for x in records}
    sheets = []
    for listing in census['listings'][1:]:
        entries = sorted(listing['result']['entries'], key=lambda x: x['name'])
        assert all(x['object_type'] == 'file' for x in entries)
        folder_name = listing['path'].rsplit('/', 1)[-1]
        for start in range(0, len(entries), 32):
            batch = entries[start:start + 32]
            cols, cell_w, cell_h = 4, 310, 290
            rows = (len(batch) + cols - 1) // cols
            sheet = Image.new('RGB', (cols * cell_w, rows * cell_h + 35), '#eeeeee')
            draw = ImageDraw.Draw(sheet)
            draw.text((8, 10), folder_name, fill='black')
            for i, entry in enumerate(batch):
                x, y = (i % cols) * cell_w, (i // cols) * cell_h + 35
                with Image.open(cached[entry['file_id']]['preview_path']) as im:
                    im = im.convert('RGB')
                    im.thumbnail((cell_w - 12, cell_h - 53))
                    sheet.paste(im, (x + (cell_w - im.width) // 2, y))
                short = entry['name'].replace('moon-crater-phase__', '').replace('moon-crater-phase-', '')
                draw.text((x + 5, y + cell_h - 46), short, fill='black')
                draw.text((x + 5, y + cell_h - 28), entry['file_id'], fill='black')
            path = HERE / ('file-review-' + str(len(sheets) + 1) + '.jpg')
            sheet.save(path, quality=92)
            sheets.append({'path': str(path), 'folder': folder_name, 'file_ids': [x['file_id'] for x in batch], 'sha256': sha(path)})
    index = {'checked_utc': datetime.now(timezone.utc).isoformat(), 'cached_previews': records, 'contact_sheets': sheets}
    (HERE / 'image-review-index.json').write_text(json.dumps(index, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'status': 'PASS', 'previews_cached': len(records), 'contact_sheets': len(sheets)}))


if __name__ == '__main__':
    main()
