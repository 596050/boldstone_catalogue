import json
from pathlib import Path
from PIL import Image, ImageOps, ImageDraw

root = Path('/Users/tprice/Documents/boldstone')
out = root / 'reports/dropbox-wall-structure-2026-10-20/step-07-review-boards'
out.mkdir(exist_ok=True)
register = json.loads((root / 'sculpture-catalogue/components/evidence/component_register.json').read_text())
assets = {x['id']: x for x in register['assets']}
index = []
for family in ['Leaf Form', 'Panel Curves', 'Textured Panels']:
    slug = family.lower().replace(' ', '-')
    baseline = json.loads((out.parent / ('step-07-matching-baseline-' + slug + '.json')).read_text())
    entries = sorted([e for e in baseline['entries'] if e['object_type'] == 'file'], key=lambda e: e['path'].lower())
    for start in range(0, len(entries), 48):
        page = entries[start:start + 48]
        canvas = Image.new('RGB', (2000, 6 * 290), 'white')
        draw = ImageDraw.Draw(canvas)
        for j, entry in enumerate(page):
            asset = assets[entry['file_id']]
            assert asset['bytes'] == entry['file']['size']
            source = Path(asset['thumb'])
            assert source.is_file()
            im = Image.open(source).convert('RGB')
            im = ImageOps.contain(im, (242, 246))
            x, y = (j % 8) * 250, (j // 8) * 290
            canvas.paste(im, (x + (250 - im.width) // 2, y))
            label = entry['name'].split('__')[-1] + ' ' + entry['file_id'][-8:]
            draw.text((x + 3, y + 249), label, fill='black')
            group = asset.get('group', '').replace(family, '').strip()
            draw.text((x + 3, y + 264), group[:34], fill='black')
            index.append({'family': family, 'board': f'{slug}-{start // 48 + 1:02d}.jpg', 'tile': j + 1, 'file_id': entry['file_id'], 'name': entry['name'], 'cached_thumb': str(source), 'current_size_matches_cached_asset': True})
        dest = out / f'{slug}-{start // 48 + 1:02d}.jpg'
        canvas.save(dest, quality=90)
        print(dest)
(out / 'index.json').write_text(json.dumps(index, indent=2))
