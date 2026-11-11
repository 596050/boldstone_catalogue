"""Read-only export of image-size tasks and their exact public feed URLs."""
import csv
import hashlib
import html
import io
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
EVIDENCE = ROOT / 'outputs/channel-completion-20261108'
FEED_URL = 'https://docs.google.com/spreadsheets/d/1PVhR1H-GFaojV_G7Khh0Vt3IwFL1RBHyLLzvXGIT-BQ/export?format=csv'
SPEC_URL = 'https://help.pinterest.com/en/business/article/before-you-get-started-with-catalogs'


def fetch(url):
    with urlopen(url, timeout=90) as response:
        return response.read()


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


app = json.loads(fetch('http://127.0.0.1:8767/api/specifications'))
feed_bytes = fetch(FEED_URL)
feed = list(csv.DictReader(io.StringIO(feed_bytes.decode('utf-8-sig'))))
by_feed_id = {p['id']: p for p in feed}
assert len(by_feed_id) == len(feed), 'Duplicate feed IDs require reconciliation'
master = json.loads((EVIDENCE / 'master-platform-values.json').read_text())
review = json.loads((EVIDENCE / 'pinterest-original-resolution-review.json').read_text())
originals = {p['catalogue_id']: p for p in review['products']}
rows = []
for product in app['products']:
    pin = next(p for p in product['platform_tasks']['platforms'] if p['id'] == 'pinterest')
    tasks = [t for t in pin['tasks'] if t['id'] == 'primary_image_size']
    if not tasks:
        continue
    pid = product['id']
    old = master[pid]
    original = originals[pid]
    primary = original['primary']
    assert product['photos']['primary_listing']['image_id'] == primary['id'], 'Primary choice changed: ' + pid
    source = by_feed_id[old['pinterest_id']]
    assert source['image_link'] == old['pinterest_image_link'], 'Public feed photo changed: ' + pid
    width = old['pinterest_primary_width_px_observed']
    height = old['pinterest_primary_height_px_observed']
    assert width < 1000 or height < 1500
    candidates = original.get('higher_resolution_listing_candidates', [])
    rows.append({
        'catalogue_id': pid,
        'pinterest_product_id': source['id'],
        'title': source['title'],
        'sku': old['SKU'],
        'filename': primary['name'],
        'feed_image_url': source['image_link'],
        'dropbox_original_url': primary['url'],
        'product_url': source['link'],
        'app_url': 'http://127.0.0.1:8767/#' + pid,
        'observed_feed_width_px': width,
        'observed_feed_height_px': height,
        'dropbox_original_dimensions': primary['original']['dimensions'],
        'dimension_check_date': review['summary']['checked_at'],
        'current_app_task': tasks[0]['detail'],
        'native_pinterest_individual_rejection_confirmed': False,
        'larger_selected_listing_alternatives': len(candidates),
    })

rows.sort(key=lambda r: r['title'].casefold())
urls = list(dict.fromkeys(r['feed_image_url'] for r in rows))
dropbox_urls = list(dict.fromkeys(r['dropbox_original_url'] for r in rows))
assert len(rows) == len(originals), 'Current task scope differs from original review'
assert len(urls) == len(rows), 'Repeated feed images need an explicit shared-image note'
note = (
    'These are the selected primary photographs flagged for dimensions by the Boldstone app. '
    'Pinterest documents a main-image minimum width of 1,000 and height of 1,500 pixels. '
    'The dimensions were checked on 8 November; on 10 November the current app selections and '
    'current public feed URLs were read back and matched to those checks. '
    'They are not a list of confirmed individual Pinterest image rejections. '
    'The last native Pinterest account check, on 9 November, reported minimum product and website '
    'quality issues with zero approved products. A fresh native account check was not completed '
    'on 10 November because Chrome interaction was interrupted. No appeal was used.'
)
manifest = {
    'generated_at': datetime.now(timezone.utc).isoformat(),
    'scope': note,
    'product_count': len(rows),
    'unique_feed_image_urls': len(urls),
    'unique_dropbox_original_urls': len(dropbox_urls),
    'app_task_evidence_date': app['platform_task_summary']['snapshot_checked_at'],
    'app_revision': app['revision'],
    'public_feed_product_count': len(feed),
    'public_feed_sha256': hashlib.sha256(feed_bytes).hexdigest(),
    'public_feed_url': FEED_URL,
    'specification_source': SPEC_URL,
    'selections_changed': 0,
    'images_downloaded': 0,
    'products': rows,
}
dump(OUT / 'image-url-details.json', manifest)
(OUT / 'pinterest-image-urls.txt').write_text('\n'.join(urls) + '\n')
(OUT / 'dropbox-original-urls.txt').write_text('\n'.join(dropbox_urls) + '\n')

esc = html.escape
def link(url, label):
    return f'<a href="{esc(url, quote=True)}" target="_blank" rel="noopener noreferrer">{esc(label)}</a>'

table_rows = []
for i, row in enumerate(rows, 1):
    table_rows.append(
        '<tr><td>' + str(i) + '</td><td><strong>' + esc(row['title']) + '</strong><br>'
        + esc(row['sku']) + '<br><small>' + esc(row['filename']) + '</small></td><td>'
        + str(row['observed_feed_width_px']) + ' × ' + str(row['observed_feed_height_px'])
        + '</td><td class="url">' + link(row['feed_image_url'], row['feed_image_url'])
        + '</td><td>' + link(row['dropbox_original_url'], 'Dropbox original') + '<br>'
        + link(row['product_url'], 'Website product') + '<br>' + link(row['app_url'], 'App component')
        + '</td><td>' + str(row['larger_selected_listing_alternatives']) + '</td></tr>'
    )
document = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Boldstone — Pinterest image URL list</title><style>
body{margin:32px;font:16px/1.5 system-ui,sans-serif;color:#24342b;background:#fafbf8}h1{font-size:30px}p{max-width:1000px}
.note{padding:18px;border-left:5px solid #9a6b2f;background:#fff6e8}table{width:100%;border-collapse:collapse;background:white}
th,td{padding:12px;text-align:left;border-bottom:1px solid #d8ded8;vertical-align:top}th{background:#eaf0e9;position:sticky;top:0}
.url{min-width:320px;max-width:600px;overflow-wrap:anywhere;font-size:13px}a{color:#225f45}small{overflow-wrap:anywhere}input{padding:10px;width:360px;max-width:90%;margin:12px 0}
</style><h1>Boldstone — Pinterest image URL list</h1>'''
document += f'<p><strong>{len(rows)} primary images</strong> · Prepared 10 November 2026.</p><p class="note">{esc(note)}</p>'
document += '<p>' + link(SPEC_URL, 'Official Pinterest catalogue image specification') + '</p>'
document += '<p><a href="pinterest-image-urls.txt">Download all feed-image URLs</a> · <a href="dropbox-original-urls.txt">Download all Dropbox original URLs</a></p>'
document += '<label>Find product or filename<br><input id="filter" placeholder="Search the list…"></label>'
document += '<table><thead><tr><th>#</th><th>Product and source photo</th><th>Feed dimensions</th><th>Exact image URL in Pinterest feed</th><th>Open</th><th>Larger selected alternatives</th></tr></thead><tbody>'
document += ''.join(table_rows) + '</tbody></table>'
document += '<script>document.getElementById("filter").addEventListener("input",e=>{const q=e.target.value.toLowerCase();for(const r of document.querySelectorAll("tbody tr"))r.hidden=!r.textContent.toLowerCase().includes(q)});</script></html>'
(OUT / 'image-url-list.html').write_text(document)
assert len((OUT / 'pinterest-image-urls.txt').read_text().splitlines()) == len(urls)
assert document.count('<tr>') == len(rows) + 1
print(json.dumps({k: manifest[k] for k in ['generated_at', 'product_count', 'unique_feed_image_urls', 'unique_dropbox_original_urls', 'public_feed_product_count', 'public_feed_sha256']}, indent=2))
