from pathlib import Path
import json
import hashlib
from PIL import Image, ImageOps, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
BASE = HERE.parents[2]
read = lambda p: json.loads(Path(p).read_text())
a = read(HERE / 'asset-index.json')
q = {x['label']: x for x in read(HERE / 'visual-queue.json')}
sources = read(BASE / 'components/parallel-reviews/wall-circle-2026-10-17/family-keep/native-pattern-image-bindings.json')
ptr = read(BASE / 'current-master.json')
graph = read(BASE / ptr['register'])
native = {x['image_id']: x for x in graph['wall_circle_native_options']}
font = ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf', 16)
titlefont = ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf', 21)


def paste(plate, source, left, top, width=285, height=235):
    with Image.open(source) as im:
        im = ImageOps.exif_transpose(im).convert('RGB')
        im.thumbnail((width, height))
        plate.paste(im, (left + (width-im.width)//2, top))


for start in range(0, len(sources), 9):
    chunk = sources[start:start+9]
    plate = Image.new('RGB', (1620, 960), '#f2f4f1')
    draw = ImageDraw.Draw(plate)
    draw.text((16, 10), 'Native Squarespace swatch (left) and Dropbox candidate (right)', font=titlefont, fill='#25382c')
    for j, s in enumerate(chunk):
        local = Path(s['local_image'])
        assert hashlib.sha256(local.read_bytes()).hexdigest() == s['image_sha256']
        candidate = native[s['image']['id']]['dropbox_image_candidates'][0]
        asset = a[candidate['file_id']]
        left, top = (j % 3)*540+8, (j//3)*300+52
        paste(plate, local, left, top, 252, 236)
        paste(plate, asset['full'] or asset['thumb'], left+268, top, 252, 236)
        draw.text((left, top+242), s['pattern'].split('  ')[0], font=font, fill='#25382c')
    plate.save(HERE/'contact-sheets'/f'wall-native-bindings-{start//9+1:02d}.jpg', quality=92)

pairs = [('W001', 'Cobalt Crumble', 'W024'), ('W141', 'Cracked Malachite', 'W051'),
         ('W144', 'Tropical Shards', 'W021'), ('W160', 'Terra Cotta Shatter', 'W075'),
         ('W166', 'Ochre Veins', 'W102')]
plate = Image.new('RGB', (1440, 1370), '#f2f4f1')
draw = ImageDraw.Draw(plate)
draw.text((15, 10), 'Wall Circle: kept visual / source swatch / Dropbox swatch candidate', font=titlefont, fill='#25382c')
for j, (label, pattern, candidate) in enumerate(pairs):
    s = next(x for x in sources if x['pattern'].startswith(pattern+'  '))
    for k, source in enumerate([a[q[label]['file_id']], s, a[q[candidate]['file_id']]]):
        local = source['local_image'] if 'local_image' in source else source['full'] or source['thumb']
        paste(plate, local, 12+k*420, 52+j*258, 390, 218)
    draw.text((18, 276+j*258), label+' / '+pattern+' / '+candidate, font=font, fill='#25382c')
plate.save(HERE/'contact-sheets'/'wall-five-pattern-comparisons.jpg', quality=93)
print(json.dumps({'source_images_rehashed': len(sources), 'plates': 3}))
