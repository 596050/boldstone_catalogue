"""Compare cached source compositions without changing originals or option data."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps
import hashlib
import json

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SOURCE = ROOT / 'components/parallel-reviews/wall-circle-2026-10-17/family-keep'
OUT = HERE / 'wall-circle'
OUT.mkdir(exist_ok=True)
read = lambda p: json.loads(p.read_text())
model = read(HERE / 'inputs/component_register.json')
assets = {a['id']: a for a in model['assets']}
bindings = read(SOURCE / 'native-pattern-image-bindings.json')
similarities = {r['pattern']: r for r in read(SOURCE / 'native-image-similarity-candidates.json')}


def content_hash(payload):
    return hashlib.sha256(b''.join(hashlib.sha256(payload[i:i+4194304]).digest()
                                   for i in range(0, len(payload), 4194304))).hexdigest()


def cache_image(path, file_id=None, expected_sha=None):
    path = Path(path)
    payload = path.read_bytes()
    sha = hashlib.sha256(payload).hexdigest()
    if expected_sha:
        assert sha == expected_sha, path
    ch = content_hash(payload)
    if file_id:
        assert ch == assets[file_id]['content_hash'], (file_id, ch, assets[file_id]['content_hash'])
    with Image.open(path) as im:
        im.load()
        image = ImageOps.exif_transpose(im).convert('RGB')
    return image, {'path':str(path), 'file_id':file_id, 'sha256':sha,
                   'dropbox_content_hash':ch, 'dimensions':list(image.size)}


font = ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf', 15)
columns, tile_w, tile_h, rows_per_board = 3, 410, 710, 3
records, boards = [], []
for start in range(0, len(bindings), rows_per_board):
    count = min(rows_per_board, len(bindings)-start)
    board = Image.new('RGB', (columns*tile_w, count*tile_h), 'white')
    draw = ImageDraw.Draw(board)
    for j, binding in enumerate(bindings[start:start+rows_per_board]):
        native, native_info = cache_image(binding['local_image'], expected_sha=binding['image_sha256'])
        candidates = similarities[binding['pattern']]['candidates']
        images = [(native, 'Native Squarespace image')]
        candidate_info = []
        for candidate in candidates:
            a = assets[candidate['file_id']]
            path = a.get('full') or a.get('origin_evidence',{}).get('original_path')
            assert path and Path(path).exists(), candidate['file_id']
            im, info = cache_image(path, file_id=candidate['file_id'])
            candidate_info.append({**candidate, **info})
            images.append((im, candidate['file_id']))
        for k, (im, caption) in enumerate(images):
            x, y = k*tile_w, j*tile_h
            draw.text((x+8,y+8), f'{start+j+1:02d} {caption}', fill='black', font=font)
            name = binding['pattern'].split('  ',1)[0]
            draw.text((x+8,y+32), name, fill='black', font=font)
            thumb = ImageOps.contain(im, (tile_w-16,tile_h-70))
            board.paste(thumb, (x+(tile_w-thumb.width)//2, y+62+(tile_h-70-thumb.height)//2))
        records.append({'pattern':binding['pattern'], 'native_image':native_info,
                        'native_option_ids':binding['variant_ids'], 'candidates':candidate_info})
    dest = OUT/f'native-comparison-{start//rows_per_board+1:02d}.png'
    board.save(dest)
    boards.append(str(dest))
(OUT/'native-visual-inputs.json').write_text(json.dumps({'records':records,'boards':boards,
    'originals_changed':False,'new_remote_reads':0,'scope':'Image composition only; no physical specimen, finish chemistry or variant manufacture inferred'},indent=2)+'\n')
print(json.dumps({'source_patterns':len(records),'comparisons':sum(len(r['candidates']) for r in records),
                  'boards':boards,'all_originals_hash_verified':True}))
