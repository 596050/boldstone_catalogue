"""Publish bounded native availability readers without importing app decisions."""
from pathlib import Path
from html.parser import HTMLParser
import csv
import hashlib
import html
import json

H = Path(__file__).resolve().parent
B = H.parents[2]
OUT = B / 'outputs/six-native-deletions-and-app-review-2026-10-25'
APP_REVIEW = B.parent / 'catalogue-review/reviews/specification-completion-20261025/all-sculptures.html'
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
esc = lambda x: html.escape(str(x), quote=True)
dump = lambda p, x: Path(p).write_text(json.dumps(x, ensure_ascii=False, indent=2) + '\n')
overlay = read(H / 'availability-overlay.json')
assert sha(H / 'availability-overlay.json') == '174cdf148b1483216aa5cceec69d708d96679dc95926aed068096dcf4a9d3e37'
p = read(B / 'current-master.json')
assert p['register_sha256'] == overlay['baseline_register_sha256']
assert sha(B / p['register']) == p['register_sha256']
g = read(B / p['register'])
options = {o['product_id']: o for o in g['options'] if o['product_id'] in g['active_option_ids']}
assert len(options) == 188
assets = read(B / p['current_asset_reference_map']['path'])
native = read(B / p['current_native_reference_map']['path'])
deleted = {r['file_id']: r for r in overlay['rows']}
remaining = {r['metadata']['id']: r['metadata'] for r in overlay['remaining_verified_files']}
assert len(deleted) == 6 and len(remaining) == 4
assert APP_REVIEW.is_file()
OUT.mkdir(exist_ok=True)
css = '''body{font:17px/1.5 Arial,sans-serif;max-width:1120px;margin:32px auto;padding:0 20px;color:#222}nav{margin:20px 0}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:20px}article{border:1px solid #ccc;padding:18px;margin:25px 0;overflow-wrap:anywhere}img{max-width:100%;height:340px;object-fit:contain;background:#f4f4f0}table{border-collapse:collapse;width:100%}td,th{border-bottom:1px solid #ddd;text-align:left;vertical-align:top;padding:10px}th{width:22%}small{overflow-wrap:anywhere}.status{background:#fff1d6;padding:12px}.scope{background:#f1f3ef;padding:14px}a{color:#075993}'''

def document(title, body):
    return '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>' + esc(title) + '</title><style>' + css + '</style></head><body><h1>' + esc(title) + '</h1>' + body + '</body></html>'

scope = '<p class="scope">188 active sculpture options. This review subtracts six exact owner-confirmed native file deletions from the retained 6,360-file snapshot, leaving 6,354 baseline files. It is not a new scan of the entire Dropbox root. The receipt snapshot ends at review event 347; the last confirmed native deletion event is 342. The earlier five-file publication had an explicit five-ID scope and omitted the already-recorded Icarus 007 deletion. Original specifications, source assertions and stable IDs remain unchanged.</p>'
nav = '<nav><a href="index.html">Deletion summary</a> · <a href="all-options.html">188 source option records</a> · <a href="Current_Native_Files_6354.csv">6,354 remaining baseline files</a> · <a href="Confirmed_Native_Deletions_6.csv">Six deletion records</a> · <a href="' + esc(APP_REVIEW.as_uri()) + '">188 saved app specification reviews</a> · <a href="http://127.0.0.1:8767">Live review app</a></nav>'

def source_ref(o):
    return o if o.get('file_id') else o.get('owner_confirmed_design_reference', {})

def thumbnail(fid, title):
    a = assets.get(fid, {})
    thumb = a.get('thumb') or a.get('full')
    return '<img alt="' + esc(title) + '" src="' + esc(Path(thumb).as_uri()) + '">' if thumb and Path(thumb).is_file() else ''

def card(o, fields=True):
    ref = source_ref(o)
    fid = ref.get('file_id')
    folder = ref.get('folder_url', o.get('folder_url', ''))
    if fid in deleted:
        picture = '<p class="status"><strong>Former master example is unavailable.</strong> Its owner-confirmed native deletion is recorded; its stable ID and source history are retained. This reconciliation does not select a replacement.</p>'
    else:
        picture = thumbnail(fid, o['name'])
        picture += '<p><a href="' + esc(ref.get('image_url', '')) + '">' + ('Verified existing master reference' if fid in remaining else 'Retained source image reference') + '</a></p>'
        if fid not in remaining:
            picture += '<small>This image was not rechecked during the six-file reconciliation.</small>'
    if o['product_id'] in overlay['affected_folder_option_ids']:
        folder_rows = [r for r in overlay['rows'] if r['folder_id'] == ref.get('folder_id')]
        assert folder_rows
        suffix = folder_rows[0]['historical_path'].rsplit('/', 1)[0]
        q = next(x for x in overlay['verified_folder_listings'] if x['target'].endswith(suffix))
        assert not q['has_more']
        picture += '<p>Complete direct folder check: ' + str(len(q['entries'])) + ' native file(s) remain. Availability observations do not create a new primary approval.</p>'
    specs = ('<h3>Retained master source specifications</h3><table>' + ''.join('<tr><th>' + esc(k) + '</th><td>' + esc(v['display']) + '<br><small>' + esc(v['state']) + '</small></td></tr>' for k, v in o['master_fields'].items()) + '</table>') if fields else ''
    return '<article id="' + esc(o['product_id']) + '"><h2>' + esc(o['name']) + '</h2>' + picture + '<p><a href="' + esc(folder) + '">Containing Dropbox folder</a> · <a href="http://127.0.0.1:8767/#' + esc(o['product_id']) + '">Review this sculpture</a></p><small>' + esc(o['product_id']) + ' · source file ' + esc(fid) + ' · folder ' + esc(ref.get('folder_id')) + '</small>' + specs + '</article>'

(OUT / 'all-options.html').write_text(document('188 source options with current deletion availability', scope + nav + '<p>The app specification review is a separate saved overlay. This page retains the canonical master’s source values and qualifications.</p>' + ''.join(card(o) for o in options.values())))
summary = '<p>Acanthus Flower 001 is the only deleted master example. Acanthus and Moon retains master reference 002; Icarus retains master reference 010. Their identities, specifications and stable folder IDs are retained.</p>'
affected = ''.join(card(options[oid], False) for oid in overlay['affected_folder_option_ids'])
deletion_table = '<table><tr><th>Deleted original</th><th>Retained identity and evidence</th></tr>' + ''.join('<tr><td>' + esc(r['name']) + '<br><a href="' + esc(r['folder_url']) + '">Containing folder</a></td><td>' + esc(r['file_id']) + '<br>Revision ' + esc(r['revision_at_deletion']) + '<br>Verified absent ' + esc(r['independent_native_readback']['checked_utc']) + '</td></tr>' for r in overlay['rows']) + '</table>'
present_cards = []
for fid, meta in remaining.items():
    a = assets[fid]
    present_cards.append('<article><h3>' + esc(meta['name']) + '</h3>' + thumbnail(fid, meta['name']) + '<p><a href="' + esc(a['image_url']) + '">Image</a> · <a href="' + esc(a['folder_url']) + '">Containing folder</a></p><small>' + esc(fid) + ' · ' + esc(meta['rev']) + '</small><p>Native availability verified; no new primary approval.</p></article>')
(OUT / 'index.html').write_text(document('Six confirmed native image deletions reconciled', scope + nav + summary + affected + '<h2>Deleted native originals</h2>' + deletion_table + '<h2>Four verified surviving reference photographs</h2><div class="grid">' + ''.join(present_cards) + '</div>'))
base_files = {fid: r for fid, r in native['current_objects'].items() if r.get('object_type') == 'file' and r.get('current_wall_snapshot_present') and r.get('display_path', '').startswith('/BOLDSTONE MASTER/Products/01 Wall Sculptures/')}
assert len(base_files) == 6360 and set(deleted).issubset(base_files)
effective = {fid: r for fid, r in base_files.items() if fid not in deleted}
assert len(effective) == 6354
columns = ['file_id', 'name', 'folder_id', 'image_url', 'folder_url', 'availability_scope', 'review_event_cutoff']
with (OUT / 'Current_Native_Files_6354.csv').open('w', encoding='utf-8-sig', newline='') as f:
    w = csv.DictWriter(f, fieldnames=columns)
    w.writeheader()
    for fid, r in sorted(effective.items()):
        a = assets.get(fid, r)
        w.writerow({'file_id': fid, 'name': r['name'], 'folder_id': r.get('parent_id', a.get('folder_id')), 'image_url': a.get('image_url', r.get('image_url', '')), 'folder_url': a.get('folder_url', r.get('folder_url', '')), 'availability_scope': 'Native presence verified in this pass' if fid in remaining else 'Retained baseline after subtracting six verified deletions; not rechecked in this pass', 'review_event_cutoff': overlay['review_event_cutoff']})
cols = ['file_id', 'name', 'status', 'revision_at_deletion', 'folder_id', 'folder_url', 'operation_id', 'batch_id', 'deletion_readback_utc']
with (OUT / 'Confirmed_Native_Deletions_6.csv').open('w', encoding='utf-8-sig', newline='') as f:
    w = csv.DictWriter(f, fieldnames=cols)
    w.writeheader()
    w.writerows({k: r[k] for k in cols} for r in overlay['rows'])

class Check(HTMLParser):
    def __init__(self):
        super().__init__()
        self.images = []
        self.articles = []
    def handle_starttag(self, t, attrs):
        d = dict(attrs)
        if t == 'img':
            self.images.append(d.get('src', ''))
        if t == 'article':
            self.articles.append(d.get('id'))

parser = Check()
parser.feed((OUT / 'all-options.html').read_text())
assert len(parser.articles) == 188 and set(parser.articles) == set(options)
deleted_cache = {Path(v).as_uri() for fid in deleted for key in ['thumb', 'full'] if (v := assets[fid].get(key))}
assert not deleted_cache.intersection(parser.images)
assert (OUT / 'all-options.html').read_text().count('Former master example is unavailable.') == 1
assert all(sha(f) == s for f, s in overlay['source_evidence'].items())
manifest = {'status': 'PASS_NATIVE_AVAILABILITY_READERS', 'overlay_sha256': sha(H / 'availability-overlay.json'), 'register_sha256': p['register_sha256'], 'option_cards': 188, 'deleted_native_ids': 6, 'affected_master_examples': 1, 'effective_baseline_files': 6354, 'deleted_images_embedded_as_current': 0, 'new_primary_selections': 0, 'new_physical_verifications': 0, 'app_review_report': str(APP_REVIEW), 'app_review_report_sha256': sha(APP_REVIEW), 'outputs': {str(f): sha(f) for f in OUT.iterdir() if f.is_file()}}
dump(H / 'reader-verification.json', manifest)
print(json.dumps({k: v for k, v in manifest.items() if k != 'outputs'}, ensure_ascii=False, indent=2))
