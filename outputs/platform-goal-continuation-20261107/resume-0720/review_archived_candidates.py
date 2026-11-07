"""Build a labelled comparison from small native thumbnails, never publication assets."""
import io
import json
import math
import sys
import textwrap
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path('/Users/tprice/Documents/boldstone')
OUT = Path(__file__).parent
sys.path.insert(0, str(ROOT / 'catalogue-review'))
from delete_dropbox import connection
from dropbox.files import PathOrLink, ThumbnailMode, ThumbnailSize

additional = '--remaining-families' in sys.argv
folder_contents = '--folder-contents' in sys.argv
header_path = OUT / ('remaining-family-headers.json' if additional else 'archived-photo-headers.json')
stem = 'remaining-family-comparison' if additional else 'archived-photo-comparison'
if folder_contents:
    header_path = OUT / 'folder-content-headers.json'
    stem = 'folder-content-comparison'
rows = [r for r in json.loads(header_path.read_text())
        if r.get('saatchi_native_dimensions_pass')]
assert len(rows) == (23 if folder_contents else 20 if additional else 9)
app = json.loads((OUT.parent / 'resume-0645/workbook/app-specifications.json').read_text())
products = {p['id']: p for p in app['products']}
reference_ids = ['BSI-22DA74B2107E', 'BSI-1B20DCA291BB', 'BSI-5819104A663F',
    'BSI-ADD5F3BEFCF5', 'BSI-70BDE00F2855', 'BSI-AAC2DC2CFEC2', 'BSI-4C08C8E484EE']
if additional:
    reference_ids = ['BSI-718DFFB7EC5D','BSI-54F871DCF4CA','BSI-6AA659B1469F',
        'BSI-F95020D6821C','BSI-B9DA00108196','BSI-1AD9185411D8','BSI-3EB5B16E33CC']
if folder_contents:
    reference_ids = ['BSI-B42C439049D7','BSI-6AA659B1469F','BSI-718DFFB7EC5D','BSI-54F871DCF4CA']
images, index = [], []
with connection(ROOT) as (db, _):
    for row in rows:
        result, response = db.files_get_thumbnail_v2(PathOrLink.path(row['id']),
            size=ThumbnailSize.w640h480, mode=ThumbnailMode.bestfit)
        try:
            body = response.content
        finally:
            response.close()
        assert len(body) < 2000000
        assert result.file_metadata.id == row['id'] and result.file_metadata.content_hash == row['content_hash']
        images.append(Image.open(io.BytesIO(body)).convert('RGB'))
        index.append(dict(row, number=len(index)+1, role='ARCHIVE CANDIDATE'))
for pid in reference_ids:
    product = products[pid]
    aid = product['photos']['primary_listing']['image_id']
    image = next(i for i in product['photos']['listing']['images'] if i['id']==aid)
    query = urlencode(dict(id=aid, v=image['original']['dropbox_content_hash'], size='thumb'))
    with urlopen('http://127.0.0.1:8767/api/image?' + query, timeout=60) as response:
        body = response.read(2000001)
    assert len(body) < 2000000
    images.append(Image.open(io.BytesIO(body)).convert('RGB'))
    index.append(dict(id=aid, product_id=pid, name=product['retail_name'],
        number=len(index)+1, role='CURRENT PRIMARY'))
canvas = Image.new('RGB', (1260, 450*math.ceil(len(index)/3)), '#f4f3ef')
draw = ImageDraw.Draw(canvas)
font = ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf', 17)
for number, (image, row) in enumerate(zip(images, index)):
    x, y = number%3*420, number//3*450
    thumb = ImageOps.contain(image, (400, 330))
    canvas.paste(thumb, (x+(420-thumb.width)//2, y))
    label = f"{number+1}. {row['role']}: {row['name']}"
    draw.multiline_text((x+8,y+337), '\n'.join(textwrap.wrap(label,41)), font=font, fill='black', spacing=3)
canvas.save(OUT / (stem+'.jpg'), quality=90)
(OUT / (stem+'-index.json')).write_text(json.dumps(index, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(dict(archive_candidates=len(rows), current_references=len(reference_ids),
    full_originals_retained=0, platform_or_app_mutations=0)))
