"""Bounded, read-only visual comparison of retained previews; never alter source images."""
from pathlib import Path
from urllib.request import urlopen
from urllib.parse import urlencode
from concurrent.futures import ThreadPoolExecutor
from PIL import Image, ImageOps, ImageDraw, ImageFont
import io, json, textwrap, sys

OUT = Path(__file__).parent
app = json.loads((OUT / 'specifications.json').read_text())
library = json.loads((OUT / 'library.json').read_text())
products = {p['id']: p for p in app['products']}
images = {i['id']: i for i in library['images']}
targets = [
    ('BSI-8EA49F5DDB1C', ['id:cnqzTNngPVsAAAAAAAufQQ', 'id:cnqzTNngPVsAAAAAAA524w']),
    ('BSI-B42C439049D7', ['id:cnqzTNngPVsAAAAAAAuZZQ', 'id:cnqzTNngPVsAAAAAAAuVhA']),
    ('BSI-7B6291B7C7F9', ['id:cnqzTNngPVsAAAAAAAueFw', 'id:cnqzTNngPVsAAAAAAAygZA']),
    ('BSI-1CDB2BAE6105', ['id:cnqzTNngPVsAAAAAAAuZ2w']),
    ('BSI-A272AC152172', ['id:cnqzTNngPVsAAAAAAArp_w', 'id:cnqzTNngPVsAAAAAAAt7Dg']),
]
stem = 'remaining-photo-comparison'
if len(sys.argv) > 1:
    config_path = OUT / sys.argv[1]
    targets = json.loads(config_path.read_text())
    stem = config_path.stem
assert len({pid for pid, _ in targets}) == len(targets)
assert all(0 < len(candidates) <= 2 for _, candidates in targets)
slots = []
for pid, candidates in targets:
    p = products[pid]
    ids = [p['photos']['primary_listing']['image_id']] + candidates
    for n in range(3):
        if n >= len(ids):
            slots.append(None)
            continue
        im = images[ids[n]]
        slots.append({'product_id': pid, 'title': p['retail_name'], 'id': im['id'],
                      'name': im['name'], 'role': 'CURRENT PRIMARY' if n == 0 else 'CANDIDATE',
                      'original_hash': im['original']['dropbox_content_hash']})

def preview(row):
    if row is None:
        return None
    query = urlencode({'id': row['id'], 'v': row['original_hash'], 'size': 'thumb'})
    with urlopen('http://127.0.0.1:8767/api/image?' + query, timeout=60) as response:
        data = response.read(2_000_001)
    assert len(data) < 2_000_000
    return Image.open(io.BytesIO(data)).convert('RGB')

canvas = Image.new('RGB', (1260, 450 * len(targets)), '#f4f3ef')
draw = ImageDraw.Draw(canvas)
font = ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf', 17)
with ThreadPoolExecutor(max_workers=2) as pool:
    for n, (row, im) in enumerate(zip(slots, pool.map(preview, slots))):
        if row is None:
            continue
        x, y = (n % 3) * 420, (n // 3) * 450
        thumb = ImageOps.contain(im, (400, 330))
        canvas.paste(thumb, (x + (420 - thumb.width) // 2, y))
        candidate_name = row['name'] if len(row['name']) <= 88 else row['name'][:64] + '…' + row['name'][-20:]
        label = str(n + 1) + '. ' + row['role'] + ': ' + (row['title'] if row['role'] == 'CURRENT PRIMARY' else candidate_name)
        draw.multiline_text((x + 8, y + 336), '\n'.join(textwrap.wrap(label, 40)), font=font, fill='black', spacing=3)
canvas.save(OUT / (stem + '.jpg'), quality=90)
(OUT / (stem + '-index.json')).write_text(json.dumps(slots, indent=2) + '\n')
print(json.dumps({'products': len(targets), 'bounded_previews': sum(x is not None for x in slots),
                  'full_originals_downloaded': 0, 'app_or_platform_writes': 0}))
