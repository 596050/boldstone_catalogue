"""Verify159 cached native originals and rank24 complete-frame source comparisons."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageChops, ImageOps, ImageStat

B = Path('/Users/tprice/Documents/boldstone/sculpture-catalogue')
H = Path(__file__).resolve().parent
D = B.parent / 'reports/dropbox-wall-complete-role-review-20261024T214349Z'
R = B / 'components/parallel-reviews/held-identities-resumption-01a16dbc-20261024/wall-source-gallery-roles'
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
source_paths = [D / 'wall-circle-current-source-map-for-recovery.json', D / 'fresh-all-6360-native-hash-metadata.json',
    D / 'candidate-current-image-cache-paths.json', D / 'families/wall-circle/indexed-current-images-and-links.json',
    R / 'sealed-handoff.json', R / 'gallery-roles.json']
inputs = {str(p): sha(p) for p in source_paths}
assert inputs[str(source_paths[0])] == '28ead117d32efeabb7fdb22bb9466b5d6387620471250f4fc0a27ccc34986c87'
assert inputs[str(source_paths[1])] == '94adfd135a45e2de9cf78b1f9c83d8494bbc029c297ab33139123410f7cafb05'
assert inputs[str(R / 'sealed-handoff.json')] == '49aac21b7cd65a5114beca311e83f44949b580de49f40c58662c801d36c8e0a4'
wall = read(D / 'families/wall-circle/indexed-current-images-and-links.json')
cache = read(D / 'candidate-current-image-cache-paths.json')['candidates']
native_receipt = read(D / 'fresh-all-6360-native-hash-metadata.json')
native = {x['id']: x for x in native_receipt['entries']}
source = read(R / 'gallery-roles.json')['frames']
small = {}


def original(path):
    data = Path(path).read_bytes()
    with Image.open(path) as image:
        image.load()
        rgba = ImageOps.exif_transpose(image).convert('RGBA')
    record = {'path': str(path), 'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data),
        'dropbox_content_hash': hashlib.sha256(b''.join(hashlib.sha256(data[i:i + 4194304]).digest() for i in range(0, len(data), 4194304))).hexdigest(),
        'dimensions': list(rgba.size), 'decoded_RGBA_sha256': hashlib.sha256(rgba.tobytes()).hexdigest(), 'fully_decoded': True}
    small[str(path)] = rgba.convert('RGB').resize((64, 64), Image.Resampling.LANCZOS)
    return record


verified, mismatched = [], []
for row in wall:
    fid = row['file_id']
    current = native[fid]
    found = None
    for path in dict.fromkeys(cache[fid]['originals']):
        if not Path(path).is_file():
            continue
        record = original(path)
        if record['bytes'] == current['size'] and record['dropbox_content_hash'] == current['content_hash']:
            found = record
            break
        mismatched.append({'file_id': fid, 'path': path, 'native_hash': current['content_hash'], 'actual_hash': record['dropbox_content_hash']})
    assert found is not None, fid
    assert current['path'] == row['path']
    verified.append({'file_id': fid, 'folder_id': row['folder_id'], 'name': row['name'], 'path': row['path'],
        'image_url': row['image_url'], 'folder_url': row['folder_url'], 'current_native_metadata': current,
        'native_hash_observed_scope': {'recorded_utc': native_receipt['recorded_utc'], 'completed_utc': native_receipt['completed_utc'],
            'scope': native_receipt['scope'], 'local_original_rehashed_in_this_pass': True},
        'current_original': found})
assert len(verified) == 159 and len({x['file_id'] for x in verified}) == 159
sources = []
for frame in source:
    record = original(frame['saved_original']['path'])
    assert record['sha256'] == frame['saved_original']['sha256']
    ranked = []
    for target in verified:
        other = target['current_original']
        delta = ImageChops.difference(small[record['path']], small[other['path']])
        means = ImageStat.Stat(delta).mean
        sr = record['dimensions'][0] / record['dimensions'][1]
        tr = other['dimensions'][0] / other['dimensions'][1]
        ranked.append({'file_id': target['file_id'], 'name': target['name'], 'mean_absolute_RGB_difference_64x64': sum(means) / 3,
            'per_channel_mean_absolute_difference': means, 'relative_aspect_ratio_difference': abs(sr - tr) / sr,
            'encoded_bytes_equal': record['sha256'] == other['sha256'],
            'decoded_pixels_equal': record['dimensions'] == other['dimensions'] and record['decoded_RGBA_sha256'] == other['decoded_RGBA_sha256']})
    ranked.sort(key=lambda x: x['mean_absolute_RGB_difference_64x64'])
    sources.append({'native_media_id': frame['native_media_id'], 'gallery_order_1based': frame['gallery_order_1based'],
        'source_image_url': frame['source_image_url'], 'primary_visual_role': frame['primary_visual_role'], 'role_subtype': frame['role_subtype'],
        'source_image': record, 'encoded_exact_matches': [x for x in ranked if x['encoded_bytes_equal']],
        'decoded_exact_matches': [x for x in ranked if x['decoded_pixels_equal']], 'ranked_whole_frame_candidates': ranked[:5]})
for path, expected in inputs.items():
    assert sha(path) == expected
result = {'status': 'VERIFIED_ORIGINALS_AND_CANDIDATE_DIAGNOSTICS_ONLY', 'recorded_utc': datetime.now(timezone.utc).isoformat(),
    'source_inputs': inputs, 'native_originals': verified, 'sources': sources, 'mismatched_cache_candidates_retained': mismatched,
    'counts': {'current_native_originals_rehashed_and_fully_decoded': 159, 'source_frames_rehashed_and_decoded': 24,
        'complete_frame_comparisons': 3816, 'source_frames_with_encoded_exact_match': sum(bool(x['encoded_exact_matches']) for x in sources),
        'source_frames_with_decoded_exact_match': sum(bool(x['decoded_exact_matches']) for x in sources), 'new_downloads': 0, 'new_live_calls': 0},
    'diagnostic_scope': 'Top-five complete-frame64x64 comparisons rank candidates only. No crop, rotation, fitted transformation or acceptance threshold. Exact encoded/decoded equality is recorded independently; remaining candidate correspondences need visual adjudication.'}
(H / 'photo-candidates.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'status': result['status'], 'counts': result['counts'], 'report_sha256': sha(H / 'photo-candidates.json')}))
