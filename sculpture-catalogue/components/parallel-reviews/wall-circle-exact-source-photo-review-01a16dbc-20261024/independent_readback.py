"""Verify serialized O001 image links without changing source or catalogue records."""
import hashlib
import json
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

H = Path(__file__).resolve().parent
B = H.parents[2]
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
checks = []


def check(label, passed):
    checks.append({'check': label, 'pass': bool(passed)})
    assert passed, label


report = read(H / 'review.json')
seal = read(H / 'sealed-handoff.json')
check('Exact final eleven-file seal', sha(H / 'sealed-handoff.json') == '651e9e097e7fa61f7207f011d09266790b6bbc75c42d02f60b7d55aef3477ef2' and len(seal['files']) == 11)
for name, expected in seal['files'].items():
    check('Sealed member exact: ' + name, sha(H / name) == expected)
for path, expected in report['source_inputs'].items():
    check('Bound input exact: ' + path, sha(path) == expected)
for path, expected in report['protected_canonical_inputs'].items():
    check('Canonical file unchanged: ' + path, sha(path) == expected)
prepared = read(H / 'photo-candidates.json')
native = {x['file_id']: x for x in prepared['native_originals']}
for row in native.values():
    check('Current cached native original exact: ' + row['file_id'], sha(row['current_original']['path']) == row['current_original']['sha256'])
source_binding = read(B / 'components/parallel-reviews/held-identities-resumption-01a16dbc-20261024/wall-native-binding-readback.json')
check('All24 source media IDs and URLs retain captured order', [(x['native_media_id'], x['source_image_url']) for x in report['frames']] == [(x['id'], x['assetUrl']) for x in source_binding['gallery']])
native_clock_path = next(path for path in report['source_inputs'] if path.endswith('fresh-all-6360-native-hash-metadata.json'))
native_clock = read(native_clock_path)
links = []
for frame in report['frames']:
    check('Retained source image exact: ' + str(frame['gallery_order_1based']), sha(frame['source_image']['path']) == frame['source_image']['sha256'])
    for match in frame['current_file_correspondences']:
        actual = native[match['current_file_id']]
        check('Exact target file, parent, image/folder URLs and cached proof: ' + match['current_file_id'], all(match[k] == actual[v] for k, v in [('current_folder_id', 'folder_id'), ('image_url', 'image_url'), ('folder_url', 'folder_url'), ('current_native_path', 'path'), ('current_original', 'current_original'), ('current_native_metadata', 'current_native_metadata')]))
        check('Original metadata clocks retained: ' + match['current_file_id'], match['native_metadata_clock']['recorded_utc'] == native_clock['recorded_utc'] and match['native_metadata_clock']['completed_utc'] == native_clock['completed_utc'])
        check('Source/native byte and full-pixel identity remain false: ' + match['current_file_id'], match['original_encoded_or_decoded_pixel_identity'] is False and not match['diagnostics']['encoded_bytes_equal'] and not match['diagnostics']['decoded_pixels_equal'])
        if frame['source_picture_match_supported']:
            check('Only whole-frame matches become source-picture links: ' + match['current_file_id'], frame['grade'] == match['relation'] == 'SAME_FULL_FRAME_IMAGE_RENDITION' and match['source_picture_match_supported'] is True)
            links.append({'offer_ref': 'O001', 'native_product_id': frame['native_product_id'], 'source_native_media_id': frame['native_media_id'],
                'source_gallery_order_1based': frame['gallery_order_1based'], 'source_image_url': frame['source_image_url'],
                'current_file_id': match['current_file_id'], 'current_folder_id': match['current_folder_id'], 'image_url': match['image_url'],
                'folder_url': match['folder_url'], 'grade': match['relation'], 'source_picture_match_supported': True,
                'original_encoded_or_full_pixel_identity_claimed': False, 'physical_or_exact_variant_identity_claimed': False,
                'review': str(H / 'index.html') + '#media-' + frame['native_media_id']})
        else:
            check('Composition-only candidates remain excluded from picture links: ' + match['current_file_id'], match['relation'] == 'CIRCULAR_COMPOSITION_ONLY' and match['source_picture_match_supported'] is False)
check('Twenty full-frame sources produce exactly38 distinct current-file links', len(links) == len({x['current_file_id'] for x in links}) == 38 and len({x['source_native_media_id'] for x in links}) == 20)
check('First three display frames and last diagram never promoted to picture matches', {x['gallery_order_1based'] for x in report['frames'] if not x['source_picture_match_supported']} == {1, 2, 3, 24})
check('Negative center-crop attempts remain explicit', sum(len(x['circular_center_crop_hypothesis']) for x in report['frames']) == 5)
check('No new calls, downloads, owner questions or identity writes', all(report['counts'][k] == 0 for k in ['new_live_calls', 'new_downloads', 'new_owner_questions', 'new_identity_decisions', 'native_or_platform_or_canonical_writes']))


class Parsed(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.local, self.ids, self.links = [], set(), []

    def handle_starttag(self, tag, attrs):
        for key, value in attrs:
            if key == 'id':
                self.ids.add(value)
            if key in ['href', 'src'] and value:
                self.links.append(value)
                parsed = urlsplit(value)
                if not parsed.scheme and parsed.path:
                    self.local.append(H / unquote(parsed.path))


html = Parsed()
html.feed((H / 'index.html').read_text())
check('All local image/report targets resolve', all(x.is_file() for x in html.local))
check('All24 per-frame report anchors resolve', all('media-' + x['native_media_id'] in html.ids for x in report['frames']))
check('Every positive picture and containing-folder link is rendered', all(x[k] in html.links for x in links for k in ['image_url', 'folder_url']))
(H / 'source-picture-links.json').write_text(json.dumps({'status': 'SUPPORTED_FULL_FRAME_RENDITION_LINKS_ONLY', 'source_frames': 20,
    'current_file_links': 38, 'links': links, 'not_included': 'Three circular composition-only frames and one unresolved fixing diagram. No physical/variant identity, encoded-byte or full-pixel equality asserted.'}, ensure_ascii=False, indent=2) + '\n')
receipt = {'status': 'PASS', 'recorded_utc': datetime.now(timezone.utc).isoformat(), 'checks_passed': len(checks), 'checks_total': len(checks), 'checks': checks,
    'source_seal_sha256': sha(H / 'sealed-handoff.json'), 'review_sha256': sha(H / 'review.json'), 'source_picture_links_sha256': sha(H / 'source-picture-links.json'), 'counts': report['counts']}
(H / 'independent-readback.json').write_text(json.dumps(receipt, indent=2) + '\n')
(H / 'sealed-readback.json').write_text(json.dumps({'status': 'PASS', 'files': {n: sha(H / n) for n in ['independent_readback.py', 'source-picture-links.json', 'independent-readback.json', 'sealed-handoff.json']}}, indent=2) + '\n')
print(json.dumps({'status': 'PASS', 'checks_passed': len(checks), 'source_seal_sha256': sha(H / 'sealed-handoff.json'), 'picture_links_sha256': sha(H / 'source-picture-links.json'), 'readback_sha256': sha(H / 'independent-readback.json'), 'readback_seal_sha256': sha(H / 'sealed-readback.json')}))
