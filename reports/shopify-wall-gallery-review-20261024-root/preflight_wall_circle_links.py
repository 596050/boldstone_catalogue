"""Root read-only guards for a later two-reference canonical import."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageChops, ImageOps, ImageStat

H = Path(__file__).resolve().parent
ROOT = H.parents[1]
B = ROOT / 'sculpture-catalogue'
P = B / 'components/parallel-reviews/held-identities-resumption-01a16dbc-20261024/deleted-reference-resolution'
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
digest = lambda v: hashlib.sha256(json.dumps(v, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()

checks = []
def check(name, value):
    checks.append({'check': name, 'pass': bool(value)})
    assert value, name

seal = read(P / 'sealed-handoff.json')
check('Exact sealed provider handoff', sha(P / 'sealed-handoff.json') == '393fcd0e24b77a32412e142d2efe33bb53402e475f2d07aee55455f22b9baad5')
for p, expected in seal['files'].items():
    check('Provider member unchanged ' + p, sha(p) == expected)
proposal = read(P / 'proposed-reference-replacements.json')
pointer = read(B / 'current-master.json')
check('Exact canonical baseline', sha(B / 'current-master.json') == proposal['source_pointer_sha256'])
check('Exact canonical register', sha(B / pointer['register']) == proposal['register_sha256'])
check('Exact workbook', sha(B / pointer['workbook']) == proposal['workbook_sha256'])
register = read(B / pointer['register'])
options = {o['product_id']: o for o in register['options']}
native = read(ROOT / 'reports/dropbox-wall-complete-role-review-20261024T214349Z/complete-current-native-object-map.json')
summary = []
for c in proposal['changes']:
    oid = c['option_id']
    option = options[oid]
    check('Whole option guard ' + oid, digest(option) == c['expected_whole_option_sha256'])
    check('All six full working fields guarded ' + oid, digest(option['master_fields']) == c['expected_working_fields_sha256'])
    check('All six field objects equal provider ' + oid, option['master_fields'] == c['full_qualified_working_fields_preserved'])
    check('Current old reference exact ' + oid, {k: option[k] for k in c['before']} == c['before'])
    check('Only selected file and image URL differ ' + oid, {k for k in c['before'] if c['before'][k] != c['proposed'][k]} == {'file_id', 'image_url'})
    replacement = native[c['proposed']['file_id']]
    check('Replacement current native parent exact ' + oid, replacement['parent_id'] == c['proposed']['folder_id'] == option['folder_id'])
    check('Replacement current name and path exact ' + oid, replacement['name'] == c['current_file_metadata']['name'] and replacement['display_path'] == c['current_file_metadata']['path_display'])
    images = []
    for label in ['old_local_original', 'current_local_original']:
        item = c[label]
        data = Path(item['path']).read_bytes()
        check(label + ' encoded hash ' + oid, hashlib.sha256(data).hexdigest() == item['sha256'])
        dbhash = hashlib.sha256(b''.join(hashlib.sha256(data[i:i+4194304]).digest() for i in range(0, len(data), 4194304))).hexdigest()
        check(label + ' native content hash ' + oid, dbhash == item['dropbox_content_hash'])
        with Image.open(item['path']) as opened:
            opened.load()
            im = ImageOps.exif_transpose(opened).convert('RGB')
        check(label + ' decoded dimensions and pixels ' + oid, list(im.size) == item['dimensions'] and hashlib.sha256(im.tobytes()).hexdigest() == item['decoded_rgb_sha256'])
        images.append(im)
    equal = images[0].tobytes() == images[1].tobytes()
    check('Same complete frame dimensions ' + oid, images[0].size == images[1].size)
    check('Pixel equality qualification retained ' + oid, equal == c['comparison']['decoded_RGB_equal'])
    delta = ImageStat.Stat(ImageChops.difference(*images)).mean
    check('Compression difference exact ' + oid, delta == c['comparison']['whole_frame_mean_absolute_RGB_difference_0_to_255'])
    summary.append({'option_id': oid, 'name': c['name'], 'before': c['before'], 'proposed': c['proposed'],
        'comparison': c['comparison'], 'working_field_groups_preserved': 6,
        'status': 'PREPARED_NOT_PUBLISHED'})
for p, expected in proposal['protected_source_files'].items():
    check('Protected canonical file unchanged ' + p, sha(p) == expected)
out = {'status': 'PASS_ROOT_READ_ONLY_PREFLIGHT_NOT_A_CANONICAL_IMPORT',
    'recorded_utc': datetime.now(timezone.utc).isoformat(), 'checks_passed': len(checks), 'checks_total': len(checks),
    'checks': checks, 'proposal_path': str(P / 'proposed-reference-replacements.json'),
    'proposal_sha256': sha(P / 'proposed-reference-replacements.json'),
    'provider_seal_sha256': sha(P / 'sealed-handoff.json'), 'changes': summary,
    'pending_work': 'Root to apply in one coordinated canonical release after final current-image/native handoffs. This preflight changes no master, role, physical field, identity, or source.',
    'native_or_platform_writes': 0, 'canonical_writes': 0}
(H / 'wall-circle-reference-import-preflight.json').write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'status': out['status'], 'checks': len(checks), 'prepared_references': len(summary)}, indent=2))
