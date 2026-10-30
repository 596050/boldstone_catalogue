"""Refresh a reviewer-only linked status page from the published master."""
from pathlib import Path
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import hashlib
import html
import json

lane = Path(__file__).resolve().parent
base = lane.parents[2]
read = lambda p: json.loads(p.read_text())
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
esc = html.escape
pointer_file = base / 'current-master.json'
pointer = read(pointer_file)
register_file = base / pointer['register']
register = read(register_file)
assert sha(register_file) == pointer['register_sha256']
assert sha(base / pointer['workbook']) == pointer['workbook_sha256']
options = {o['product_id']: o for o in register['options']}
folders = [
    'leaf-form2-gold-series-policy-20261023T233609Z',
    'moon-shellwave2-black-white-series-policy-20261023T234009Z',
    'moon-crater-phase1-verdigris-rust-series-policy-20261023T234225Z',
    'moon-crater-phase3-verdigris-rust-series-policy-20261023T234618Z',
    'moon-crater-phase4-silver-bronze-series-policy-20261023T234807Z',
    'acanthus-one-leaf-pewter-series-policy-20261023T235035Z',
]
rows = []
for folder in folders:
    receipt_file = lane.parent / folder / 'owner-approved-series-optionality.json'
    receipt = read(receipt_file)
    option = options[receipt['option_id']]
    policy = option.get('current_series_optionality_policy', {})
    published = policy.get('canonical_applied') is True and policy.get('source_sha256') == sha(receipt_file)
    rows.append({
        'product_id': option['product_id'], 'name': option['name'],
        'owner_decision': 'Group photograph optional',
        'status': 'Saved in master' if published else 'Approved; awaiting master update',
        'published': published, 'image_url': option['image_url'], 'folder_url': option['folder_url'],
        'working_details': {k: v['display'] for k, v in option['master_fields'].items()},
        'owner_receipt': str(receipt_file), 'owner_receipt_sha256': sha(receipt_file),
    })
assert len(rows) == 6 and len({r['product_id'] for r in rows}) == 6
assert all('/BOLDSTONE%20MASTER/' in r['image_url'] and '/BOLDSTONE%20MASTER/' in r['folder_url'] for r in rows)
assert read(pointer_file) == pointer
now = datetime.now(timezone.utc)
saved = sum(r['published'] for r in rows)
result = {
    'recorded_utc': now.isoformat(), 'published_entries': saved, 'approved_awaiting_publication': 6 - saved,
    'current_master_register': str(register_file), 'register_sha256': pointer['register_sha256'],
    'workbook_sha256': pointer['workbook_sha256'], 'rows': rows,
    'canonical_writes': 0, 'native_or_platform_writes': 0,
}
(lane / 'review-status.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
link = lambda label, url: '<a href="' + esc(url, quote=True) + '" target="_blank" rel="noopener">' + esc(label) + '</a>'
table_rows = ''.join(
    '<tr><th scope="row">' + esc(r['name']) + '</th><td>' + link('Image', r['image_url']) +
    ' · ' + link('Folder', r['folder_url']) + '</td><td><span class="' +
    ('saved' if r['published'] else 'queued') + '">' + esc(r['status']) + '</span></td></tr>' for r in rows
)
details = ''.join(
    '<details><summary>' + esc(r['name']) + ' — accepted working details</summary><table>' +
    ''.join('<tr><th scope="row">' + esc(k) + '</th><td>' + esc(v) + '</td></tr>'
            for k, v in r['working_details'].items()) + '</table></details>' for r in rows
)
page = '''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Group photograph decisions</title>
<style>body{font:17px/1.55 system-ui;max-width:1080px;margin:44px auto;padding:0 24px;color:#18352e;background:#f7faf8}
h1{font-size:2rem;line-height:1.2}a{color:#006d72}table{border-collapse:collapse;width:100%;background:white}
th,td{border-bottom:1px solid #cbd8d2;padding:14px;text-align:left;vertical-align:top}thead{background:#e6efeb}
.tablewrap{overflow-x:auto}.saved,.queued{display:inline-block;padding:3px 8px;border-radius:5px}
.saved{background:#d9eee1}.queued{background:#fff1d4}details{background:white;margin:14px 0;padding:15px}
summary{cursor:pointer;font-weight:600}details table{margin-top:12px}details th{width:24%}.muted{color:#4b635a}
</style></head><body><h1>Group photograph decisions</h1>'''
page += '<p>All six entries below have your approval for an optional group photograph. Their existing individual sale, images, family links and working specifications are retained.</p>'
page += '<p><strong>' + str(saved) + ' saved in the master catalogue</strong> · ' + str(6 - saved) + ' awaiting the next update.</p>'
page += '<p class="muted">Status checked ' + esc(now.astimezone(ZoneInfo('Europe/London')).strftime('%d %B %Y at %H:%M %Z')) + '.</p>'
page += '<div class="tablewrap"><table><thead><tr><th>Product</th><th>Dropbox links</th><th>Catalogue status</th></tr></thead><tbody>' + table_rows + '</tbody></table></div>'
page += '<h2>Accepted working details</h2><p>Estimates, proposals and historical source claims keep their labels. Making a group photograph optional does not confirm that no companion set exists.</p>' + details
page += '<p class="muted">Separate installation-photo requests remain on hold. This page reports catalogue decisions; it does not publish store listings or alter Dropbox files.</p></body></html>'
(lane / 'review-status.html').write_text(page)
assert page.count('<details>') == 6
assert all(esc(r['image_url'], quote=True) in page and esc(r['folder_url'], quote=True) in page for r in rows)
print(json.dumps({'page': str(lane / 'review-status.html'), 'saved': saved, 'awaiting_publication': 6 - saved,
                  'register_sha256': pointer['register_sha256']}))
