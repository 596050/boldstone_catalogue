"""Create a bounded analysis sheet of existing photographs; no product/image edits."""
import io
import json
import textwrap
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen
from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path('/Users/tprice/Documents/boldstone')
OUT = Path(__file__).parent
app = json.loads((OUT / 'workbook/app-specifications.json').read_text())
library = json.loads((ROOT / 'outputs/platform-goal-continuation-20261106/resume-2250/library.json').read_text())
products = {p['id']: p for p in app['products']}
images = {i['id']: i for i in library['images']}
targets = [
    ('BSI-1AD9185411D8', 'id:cnqzTNngPVsAAAAAAAsYLw'),
    ('BSI-3EB5B16E33CC', 'id:cnqzTNngPVsAAAAAAAsYLw'),
    ('BSI-B9DA00108196', 'id:cnqzTNngPVsAAAAAAAsYLw'),
    ('BSI-406CAEC365A4', 'id:cnqzTNngPVsAAAAAAAuehw'),
    ('BSI-449C4421ABD0', 'id:cnqzTNngPVsAAAAAAAuQPA'),
    ('BSI-4C08C8E484EE', 'id:cnqzTNngPVsAAAAAAA5zrA'),
    ('BSI-C0F5BF012CFC', 'id:cnqzTNngPVsAAAAAAArtmw'),
    ('BSI-46F6DB226213', 'id:cnqzTNngPVsAAAAAAAuRMg'),
]
slots = []
for pid, aid in targets:
    product = products[pid]
    primary = product['photos']['primary_listing']['image_id']
    for label, image_id in [('CURRENT PRIMARY', primary), ('CANDIDATE', aid)]:
        image = images[image_id]
        slots.append(dict(product_id=pid, title=product['retail_name'], role=label,
                          image_id=image_id, name=image['name'],
                          content_hash=image['original']['dropbox_content_hash'],
                          original_dimensions=image['original'].get('dimensions')))

def preview(slot):
    query = urlencode(dict(id=slot['image_id'], v=slot['content_hash'], size='thumb'))
    with urlopen('http://127.0.0.1:8767/api/image?' + query, timeout=60) as response:
        body = response.read(2_000_001)
    assert len(body) < 2_000_000
    return Image.open(io.BytesIO(body)).convert('RGB')

canvas = Image.new('RGB', (1040, 415 * len(targets)), '#f4f3ef')
draw = ImageDraw.Draw(canvas)
font = ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf', 17)
with ThreadPoolExecutor(max_workers=2) as pool:
    for index, (slot, image) in enumerate(zip(slots, pool.map(preview, slots))):
        x, y = (index % 2) * 520, (index // 2) * 415
        image = ImageOps.contain(image, (500, 320))
        canvas.paste(image, (x + (520 - image.width) // 2, y))
        label = f"{index + 1}. {slot['role']}: {slot['title']}\n{slot['name']}"
        draw.multiline_text((x + 8, y + 322), '\n'.join(textwrap.wrap(label, 50)), font=font, fill='black', spacing=2)
canvas.save(OUT / 'photo-gap-review.jpg', quality=90)
(OUT / 'photo-gap-review-index.json').write_text(json.dumps(slots, indent=2) + '\n')
print(json.dumps(dict(previews=len(slots), full_original_downloads=0, platform_or_app_writes=0)))
