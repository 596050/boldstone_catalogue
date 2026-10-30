"""Prepare two current equivalent primary references; never publish or mutate Dropbox."""
import hashlib
import html
import io
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

from PIL import Image, ImageChops, ImageOps, ImageStat

B = Path('/Users/tprice/Documents/boldstone/sculpture-catalogue')
H = Path(__file__).resolve().parent
OUT = H / 'deleted-reference-resolution'
OUT.mkdir(exist_ok=True)
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
digest = lambda v: hashlib.sha256(json.dumps(v, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()
checks, protected = [], {}


def check(label, value):
    checks.append({'check': label, 'pass': bool(value)})
    assert value, label


def image(path):
    data = Path(path).read_bytes()
    with Image.open(io.BytesIO(data)) as opened:
        opened.load()
        rgb = ImageOps.exif_transpose(opened).convert('RGB')
    content = hashlib.sha256(b''.join(hashlib.sha256(data[i:i + 4194304]).digest() for i in range(0, len(data), 4194304))).hexdigest()
    return {'path': str(path), 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest(), 'dropbox_content_hash': content,
            'dimensions': list(rgb.size), 'decoded_rgb_sha256': hashlib.sha256(rgb.tobytes()).hexdigest(), 'full_decode_passed': True}, rgb


p = read(B / 'current-master.json')
check('Exact current source pointer', sha(B / 'current-master.json') == '64e22f7c3aaca874817b11b497294c4b40b17564b717ce7c05e41ffbc44f22b7')
g = read(B / p['register'])
a = read(B / p['current_asset_reference_map']['path'])
for f in [B / 'current-master.json', B / p['register'], B / p['workbook'], B / p['current_asset_reference_map']['path'], B / p['current_native_reference_map']['path'], (B / p['register']).parent / 'image-coverage-current.json', B / 'components/reviews/specification_review_progress.json', B / 'components/checkpoint.json', B / 'checkpoint.json']:
    protected[str(f)] = sha(f)
receipts = read(H / 'family-listing-and-history-receipts.json')['requests']
metadata = {x['requested_id']: x['result']['structuredContent'] for x in read(H / 'wall-current-file-parent-metadata.json')['requests']}
revisions = {x['requested_id']: x['result']['structuredContent'] for x in read(H / 'wall-current-revision-hashes.json')['requests']}
originals = Path('/Users/tprice/Documents/boldstone/reports/dropbox-wall-circle-finish-names-review-2026-10-23/originals')
plans = [
    ('BSI-D5A939264C82', 'id:cnqzTNngPVsAAAAAAAs9QA', 'id:cnqzTNngPVsAAAAAAAr1HA', 'terracotta-primary-history', 'wall-circle__wall-circle-marbled-4__001.png', 'wall-circle__wall-circle-marbled-4__019.png'),
    ('BSI-65520F070145', 'id:cnqzTNngPVsAAAAAAAr1IQ', 'id:cnqzTNngPVsAAAAAAAs9Pw', 'yellow-primary-history', 'wall-circle__wall-circle-yellow-and-grey-pattern-studies__011.png', 'wall-circle__wall-circle-yellow-and-grey-pattern-studies__012.webp')]
changes = []
for oid, oldid, newid, label, oldname, newname in plans:
    option = next(x for x in g['options'] if x['product_id'] == oid)
    history = next(x['result']['structuredContent'] for x in receipts if x['label'] == label)
    current, parent = metadata[newid]['file'], metadata[option['folder_id']]['folder']
    latest = revisions[newid]['entries'][0]
    old, oldrgb = image(originals / oldname)
    new, newrgb = image(originals / newname)
    check('Canonical saved ID is exact deleted file: ' + oid, option['file_id'] == oldid and history['is_deleted'] is True and history['has_more'] is False)
    check('Deleted original equals latest available historical revision: ' + oid, old['bytes'] == history['entries'][0]['size'] and old['dropbox_content_hash'] == history['entries'][0]['content_hash'])
    check('Current replacement is live at exact revision: ' + oid, not revisions[newid]['is_deleted'] and current['id'] == latest['file_id'] == newid and current['rev'] == latest['rev'])
    check('Cached replacement bytes equal current size/revision hash: ' + oid, new['bytes'] == current['size'] == latest['size'] and new['dropbox_content_hash'] == latest['content_hash'])
    check('Same actual containing folder: ' + oid, current['path_display'].rsplit('/', 1)[0] == parent['path_display'] and parent['id'] == option['folder_id'])
    check('Replacement is in complete current family listing: ' + oid, any(x.get('file_id') == newid and x.get('path') == 'ns:202238505/' + current['path_display'] for x in receipts[0]['result']['structuredContent']['entries']))
    check('Existing asset record has exact replacement hash and parent: ' + oid, a[newid]['source_content_hash'] == new['dropbox_content_hash'] and a[newid]['folder_id'] == parent['id'])
    check('Whole-frame dimensions retained: ' + oid, oldrgb.size == newrgb.size)
    equal = oldrgb.tobytes() == newrgb.tobytes()
    check('Terracotta pixels exact, Yellow/Grey encoding difference explicit: ' + oid, equal == (oid == 'BSI-D5A939264C82'))
    delta = ImageChops.difference(oldrgb, newrgb)
    oldref = {k: option[k] for k in ['file_id', 'folder_id', 'image_url', 'folder_url']}
    newref = dict(oldref, file_id=newid, image_url='https://www.dropbox.com/home' + quote(parent['path_display'], safe='/') + '?preview=' + quote(current['name'], safe=''))
    check('Only selected ID and image URL proposed: ' + oid, {k for k in oldref if oldref[k] != newref[k]} == {'file_id', 'image_url'})
    changes.append({'option_id': oid, 'name': option['name'], 'expected_whole_option_sha256': digest(option),
        'expected_working_fields_sha256': digest(option['master_fields']), 'full_qualified_working_fields_preserved': option['master_fields'],
        'before': oldref, 'proposed': newref, 'deleted_utc': history['server_deleted'],
        'old_local_original': old, 'current_local_original': new, 'current_file_metadata': current, 'current_parent_metadata': parent,
        'current_revision': latest, 'current_revision_history_has_more': revisions[newid]['has_more'],
        'comparison': {'encoded_bytes_equal': old['sha256'] == new['sha256'], 'decoded_RGB_equal': equal,
            'whole_frame_mean_absolute_RGB_difference_0_to_255': ImageStat.Stat(delta).mean,
            'visual_result': 'Identical decoded whole-frame pixels; encoded metadata/bytes differ.' if equal else 'Same full composition at identical dimensions; WEBP compression changes pixels. No crop, rotation or fitted matching transform.',
            'physical_specimen_or_new_pattern_identity_claimed': False},
        'publisher_scope': 'Replace two top-level selected-reference fields only, retaining historical evidence, image role, full fields and identity qualifications. Publisher owns any necessary current-reference projection synchronization.'})
for path, expected in protected.items():
    check('Protected source unchanged: ' + path, sha(path) == expected)
inputs = {str(H / n): sha(H / n) for n in ['OWNERSHIP.json', 'initial-metadata-receipts.json', 'family-listing-and-history-receipts.json', 'wall-current-file-parent-metadata.json', 'wall-current-revision-hashes.json']}
packet = {'status': 'READY_FOR_GUARDED_PRIMARY_REFERENCE_METADATA_IMPORT', 'recorded_utc': datetime.now(timezone.utc).isoformat(),
    'source_pointer_sha256': protected[str(B / 'current-master.json')], 'register_sha256': p['register_sha256'], 'workbook_sha256': p['workbook_sha256'],
    'changes': changes, 'source_inputs': inputs, 'protected_source_files': protected,
    'counts': {'proposed_reference_replacements': 2, 'existing_options': 2, 'full_qualified_fields_preserved': 12, 'native_restores': 0,
        'native_content_writes': 0, 'canonical_writes_by_reviewer': 0, 'new_downloads': 0, 'new_pattern_or_physical_identity_decisions': 0},
    'live_scope': '30 read-only connector calls across this identity investigation; link proof uses current file/parent metadata, latest revision hashes, complete family listings and exact deleted-file history. Seven current-file histories use limit1 and are not complete history listings.',
    'authority': 'User checklist items3 and4 resume existing-image link and identity reviews. No native restoration is needed for these equivalent current-file candidates. Canonical publication remains with the main session.'}
(OUT / 'proposed-reference-replacements.json').write_text(json.dumps(packet, ensure_ascii=False, indent=2) + '\n')
e = html.escape
local = lambda x: e(quote(os.path.relpath(x, OUT), safe='/'), quote=True)
parts = ['<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Two Wall Circle reference resolutions</title><style>body{font:17px/1.5 system-ui;max-width:1100px;margin:2rem auto;padding:0 1rem}.pair{display:grid;grid-template-columns:1fr 1fr;gap:1rem}img{width:100%;height:470px;object-fit:contain;background:#eee}section{border-top:1px solid #aaa;padding:1rem 0}pre{white-space:pre-wrap;overflow-wrap:anywhere}</style></head><body><h1>Two deleted Wall Circle references: current equivalents</h1><p>Two proposed catalogue reference replacements. No Dropbox restoration, move or other content mutation. Current identity qualifications and all12 full working fields are preserved.</p>']
for c in changes:
    parts += [f'<section id="{c["option_id"]}"><h2>{e(c["name"])}</h2><p>{e(c["comparison"]["visual_result"])}</p>',
        f'<p><a href="{e(c["proposed"]["image_url"], quote=True)}">Current equivalent Dropbox image</a> · <a href="{e(c["proposed"]["folder_url"], quote=True)}">Verified containing folder</a></p><div class="pair">',
        f'<figure><a href="{local(c["old_local_original"]["path"])}"><img src="{local(c["old_local_original"]["path"])}" alt="Retained deleted reference"></a><figcaption>Retained original of deleted reference</figcaption></figure>',
        f'<figure><a href="{local(c["current_local_original"]["path"])}"><img src="{local(c["current_local_original"]["path"])}" alt="Current equivalent image"></a><figcaption>Current file; existing cache matches fresh revision hash and size</figcaption></figure></div>',
        '<details><summary>Full evidence and qualified fields</summary><pre>' + e(json.dumps(c, ensure_ascii=False, indent=2)) + '</pre></details></section>']
parts += ['<p><a href="proposed-reference-replacements.json">Structured guarded handoff</a> · <a href="verification.json">Verification receipt</a></p></body></html>']
(OUT / 'index.html').write_text('\n'.join(parts))
verification = {'status': 'PASS', 'checks_passed': len(checks), 'checks_total': len(checks), 'checks': checks,
    'proposal_sha256': sha(OUT / 'proposed-reference-replacements.json'), 'html_sha256': sha(OUT / 'index.html')}
(OUT / 'verification.json').write_text(json.dumps(verification, indent=2) + '\n')
files = {str(H / 'build_link_resolution.py'): sha(H / 'build_link_resolution.py'), **inputs,
    **{str(OUT / n): sha(OUT / n) for n in ['proposed-reference-replacements.json', 'index.html', 'verification.json']}}
(OUT / 'sealed-handoff.json').write_text(json.dumps({'status': 'SEALED_VERIFIED_REFERENCE_REPLACEMENT_PROPOSAL', 'recorded_utc': packet['recorded_utc'], 'files': files}, indent=2) + '\n')
print(json.dumps({'status': 'PASS', 'checks_passed': len(checks), 'review': str(OUT / 'index.html'), 'seal_sha256': sha(OUT / 'sealed-handoff.json')}))
