"""Compare retained source renditions with current cached references, in memory only."""
import hashlib
import json
import math
from pathlib import Path
from PIL import Image, ImageChops, ImageOps, ImageStat

H = Path(__file__).resolve().parent
B = H.parents[2]
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
pointer = read(B / 'current-master.json')
assets_path = B / pointer['current_asset_reference_map']['path']
assert sha(assets_path) == pointer['current_asset_reference_map']['sha256']
assets = read(assets_path)
index = {x['ref']: x for x in read(B / 'components/evidence/offer_review_index.json')}

def rgb(path):
    with Image.open(path) as im:
        return ImageOps.exif_transpose(im).convert('RGB')

def rmse(a, b):
    return math.sqrt(sum(x * x for x in ImageStat.Stat(ImageChops.difference(a, b)).rms) / 3)

def crop_alignment(source, native):
    """Fit one axis-aligned crop; never rotate, retouch or write an image."""
    scale = min(1.0, 180 / native.width)
    native_small = native.resize((round(native.width * scale), round(native.height * scale)), Image.Resampling.LANCZOS)
    target = source.resize((64, 64), Image.Resampling.LANCZOS)
    ratio = source.height / source.width
    nw, nh = native_small.size
    max_width = min(nw, int(nh / ratio))
    def cost(x, y, width):
        height = round(width * ratio)
        if x < 0 or y < 0 or width < 30 or x + width > nw or y + height > nh:
            return float('inf')
        return rmse(target, native_small.crop((x, y, x + width, y + height)).resize((64, 64), Image.Resampling.LANCZOS))
    best = (float('inf'), 0, 0, max_width)
    widths = sorted(set([max_width] + list(range(round(max_width * .6), max_width + 1, 5))))
    for width in widths:
        height = round(width * ratio)
        xs = sorted(set([nw - width] + list(range(0, nw - width + 1, 5))))
        ys = sorted(set([nh - height] + list(range(0, nh - height + 1, 5))))
        for x in xs:
            for y in ys:
                value = cost(x, y, width)
                if value < best[0]: best = (value, x, y, width)
    _, bx, by, bw = best
    for width in range(max(30, bw - 6), min(max_width, bw + 6) + 1):
        for x in range(max(0, bx - 6), min(nw - width, bx + 6) + 1):
            for y in range(max(0, by - 6), min(nh - round(width * ratio), by + 6) + 1):
                value = cost(x, y, width)
                if value < best[0]: best = (value, x, y, width)
    value, x, y, width = best
    return {'aligned_RGB_RMSE_0_255': value,
            'native_analysis_dimensions': [nw, nh],
            'crop_box_in_native_analysis_pixels': [x, y, x + width, y + round(width * ratio)],
            'native_input_dimensions': list(native.size),
            'source_input_dimensions': list(source.size),
            'original_byte_equivalence_proven': False}

file_map = {
    'O011': ['id:cnqzTNngPVsAAAAAAAygow', 'id:cnqzTNngPVsAAAAAAAygoQ', 'id:cnqzTNngPVsAAAAAAAygog'],
    'O003': ['id:cnqzTNngPVsAAAAAAAygmA', 'id:cnqzTNngPVsAAAAAAAygmQ', 'id:cnqzTNngPVsAAAAAAAygmg'],
    'O064': ['id:cnqzTNngPVsAAAAAAAygmA', 'id:cnqzTNngPVsAAAAAAAygmQ', 'id:cnqzTNngPVsAAAAAAAygmg'],
}
results = []
for ref, file_ids in file_map.items():
    for source, fid in zip(index[ref]['images'], file_ids):
        native = assets[fid]
        first, second = rgb(source['thumb']), rgb(native['thumb'])
        row = {'offer_ref': ref, 'source_order': source['order'], 'source_url': source['url'],
               'source_cached_path': source['thumb'], 'source_cached_sha256': sha(source['thumb']),
               'historical_source_original_path': source['path'],
               'historical_source_original_present': Path(source['path']).is_file(),
               'historical_source_original_sha256_not_reverified': source['sha256'],
               'file_id': fid, 'folder_id': native['folder_id'],
               'native_cached_path': native['thumb'], 'native_cached_sha256': sha(native['thumb']),
               'native_path': native['path'], 'image_url': native['image_url'], 'folder_url': native['folder_url'],
               'whole_frame_RGB_RMSE_96px': rmse(first.resize((96, 96), Image.Resampling.LANCZOS), second.resize((96, 96), Image.Resampling.LANCZOS)),
               'visually_reviewed_both_frames': True}
        if ref == 'O011': row['in_memory_crop_alignment'] = crop_alignment(first, second)
        results.append(row)
        print(ref, source['order'], fid, round(row.get('in_memory_crop_alignment', {}).get('aligned_RGB_RMSE_0_255', row['whole_frame_RGB_RMSE_96px']), 4), flush=True)

source_pairs = []
for first, second in zip(index['O003']['images'], index['O064']['images']):
    source_pairs.append({'source_order': first['order'], 'O003_cached_sha256': sha(first['thumb']),
                         'O064_cached_sha256': sha(second['thumb']),
                         'RGB_RMSE_96px': rmse(rgb(first['thumb']).resize((96, 96), Image.Resampling.LANCZOS), rgb(second['thumb']).resize((96, 96), Image.Resampling.LANCZOS)),
                         'same_photograph_supported_by_visual_review': True})
output = {'method': 'Retained JPEG renditions only. EXIF-normalized RGB. Entire-frame RMSE at 96x96; O011 additionally fitted to an axis-aligned crop in memory at 64x64. No image file written, edited or newly downloaded.',
          'current_asset_map': {'path': str(assets_path), 'sha256': sha(assets_path)},
          'limitations': ['Photo-level correspondence is separate from original byte identity, physical cast identity, measurement or an exact current sale configuration.',
                          'Source original temporary paths are unavailable; their recorded historical hashes are not claimed as reverified.',
                          'Crop fitting is supporting analysis; visual agreement of panel details and background features provides the interpretation.'],
          'comparisons': results, 'O003_O064_source_pairs': source_pairs}
(H / 'photo-comparisons.json').write_text(json.dumps(output, indent=2, ensure_ascii=False) + '\n')
