"""Small provider thumbnails for visual comparison; no original photo copies."""
from pathlib import Path
from datetime import datetime, timezone
import io
import json
import sys
import textwrap

ROOT = Path('/Users/tprice/Documents/boldstone')
OUT = Path(__file__).parent
sys.path.insert(0, str(ROOT / 'catalogue-review'))
from delete_dropbox import connection
from dropbox.files import PathOrLink, ThumbnailFormat, ThumbnailMode, ThumbnailSize
from PIL import Image, ImageOps, ImageDraw, ImageFont

review = json.loads((OUT / 'unselected-original-header-review.json').read_text())
previous = {p['catalogue_id']: p for p in json.loads((OUT / 'pinterest-original-resolution-review.json').read_text())['products']}
targets = [p for p in review['products'] if any(a['header_check'].get('meets_documented_dimensions') for a in p['candidates'])]
assert len(targets) == 4
font = ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf', 15)
small = ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf', 12)
receipts = []
with connection(ROOT) as (db, _):
    for p in targets:
        primary = previous[p['catalogue_id']]['primary']
        candidates = [a for a in p['candidates'] if a['header_check'].get('meets_documented_dimensions')]
        photos = [(primary, True)] + [(a, False) for a in candidates]
        width, height = 300, 380
        cols = min(4, len(photos))
        rows = (len(photos) + cols - 1) // cols
        canvas = Image.new('RGB', (width * cols, rows * height + 55), '#f4f5ef')
        draw = ImageDraw.Draw(canvas)
        draw.text((15, 15), p['title'] + ' — original-photo review', fill='#263f31', font=font)
        for i, (a, is_primary) in enumerate(photos):
            metadata, response = db.files_get_thumbnail_v2(PathOrLink.path(a['id']),
                format=ThumbnailFormat.jpeg, size=ThumbnailSize.w256h256,
                mode=ThumbnailMode.strict)
            try:
                m = metadata.file_metadata
                assert m and m.id == a['id']
                assert m.content_hash == a['original']['dropbox_content_hash']
                if not is_primary:
                    assert m.rev == a['header_check']['revision']
                body = response.raw.read(512 * 1024 + 1)
                assert 0 < len(body) <= 512 * 1024
            finally:
                response.close()
            thumbnail = Image.open(io.BytesIO(body)).convert('RGB')
            x, y = i % cols * width, i // cols * height + 55
            draw.rectangle((x+5, y+5, x+width-5, y+height-5), fill='white',
                           outline='#3d6c4d' if is_primary else '#b9c5b3', width=2)
            fit = ImageOps.contain(thumbnail, (280, 260))
            canvas.paste(fit, (x+(width-fit.width)//2, y+15+(260-fit.height)//2))
            draw.text((x+14, y+280), 'CURRENT PRIMARY' if is_primary else 'UNSELECTED — REVIEW ONLY',
                      fill='#2c5a3c' if is_primary else '#6d4a1c', font=small)
            dims = a['original'].get('dimensions') if is_primary else a['header_check']['dimensions']
            label = a['name'] + '\n' + ' × '.join(map(str, dims)) + ' px'
            draw.multiline_text((x+14, y+300), '\n'.join(textwrap.wrap(label, 37)), fill='#263f31', font=small, spacing=3)
            receipts.append(dict(catalogue_id=p['catalogue_id'], image_id=a['id'],
                revision=m.rev, dropbox_content_hash=m.content_hash, thumbnail_bytes=len(body),
                primary=is_primary, original_downloaded=False))
        name = 'photo-candidates-' + p['catalogue_id'] + '.jpg'
        canvas.save(OUT / name, quality=88)
        print(json.dumps({'product':p['catalogue_id'], 'sheet':name, 'thumbnails':len(photos)}), flush=True)
(OUT / 'unselected-thumbnail-review-receipts.json').write_text(json.dumps(dict(
    checked_at=datetime.now(timezone.utc).isoformat(), photographs=receipts,
    original_copies_retained=0, publication_changes=0), indent=2) + '\n')
