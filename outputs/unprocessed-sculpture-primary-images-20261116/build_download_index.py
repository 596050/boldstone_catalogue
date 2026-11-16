import hashlib
import html
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

BASE = Path(__file__).resolve().parent
plan = json.loads((BASE / 'download-plan.json').read_text())
remaining = json.loads((BASE.parent / 'sculpture-photo-remaining-20261116/remaining-components.json').read_text())
destination = Path(plan['destination'])
receipts = [json.loads(line) for line in (BASE / 'download-receipts.jsonl').read_text().splitlines()]
by_destination = {r['destination']: r for r in receipts if not r.get('review_candidate') and r['status'] in {'downloaded_verified', 'verified_existing', 'reference_reselected_verified'}}


def content_hash(path):
    result = hashlib.sha256()
    with path.open('rb') as stream:
        while block := stream.read(4 * 1024 * 1024):
            result.update(hashlib.sha256(block).digest())
    return result.hexdigest()


rows = []
for selection in plan['entries']:
    path = destination / selection['destination_filename']
    receipt = by_destination[str(path)]
    assert path.is_file() and path.stat().st_size == receipt['size']
    assert selection['source_file_id'] == receipt['source_file_id']
    actual_hash = content_hash(path)
    assert actual_hash == receipt['content_hash']
    rows.append({**selection, 'download': {key: receipt[key] for key in ['destination', 'size', 'content_hash', 'dimensions', 'image_format', 'sha256', 'checked_at']}, 'final_hash_verified': actual_hash})
assert len(rows) == len(remaining['remaining']) == plan['requested_components']
assert {r['component_id'] for r in rows} == {r['id'] for r in remaining['remaining']}
assert len({r['destination_filename'] for r in rows}) == len(rows)
assert {f.name for f in destination.iterdir() if f.suffix.lower() in {'.jpg', '.jpeg', '.png'}} == {r['destination_filename'] for r in rows}
counts = Counter(r['selection_method'] for r in rows)
primary = counts['current_catalogue_primary'] + counts['published_catalogue_primary']
summary = {'completed_at': datetime.now(timezone.utc).isoformat(), 'source_checked_at': remaining['summary']['checked_at'], 'requested_components': len(rows), 'downloaded_images': len(rows), 'catalogue_primary_images': primary, 'current_catalogue_primary_images': counts['current_catalogue_primary'], 'published_catalogue_primary_images': counts['published_catalogue_primary'], 'marked_reference_images': len(rows) - primary, 'backup_reference_images': counts['backup_component_reference'], 'all_sizes_and_dropbox_content_hashes_verified': True, 'total_bytes': sum(r['download']['size'] for r in rows), 'destination': str(destination), 'both_photo_sets_missing': remaining['summary']['both_folders_lack_images'], 'detail_only_missing': remaining['summary']['detail_only_lacks_images']}
manifest = {'summary': summary, 'components': rows}
(BASE / 'download-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
esc = html.escape
labels = {'current_catalogue_primary': 'Current catalogue primary', 'published_catalogue_primary': 'Published catalogue primary', 'component_reference': 'Existing component reference', 'backup_component_reference': 'Backup component reference'}
table_rows = []
for row in rows:
    filename = quote(row['destination_filename'])
    w, h = row['download']['dimensions']
    notes = '<br>'.join(esc(n) for n in row['notes']) or '—'
    row_text = esc((row['component_name'] + ' ' + row['family']).casefold(), quote=True)
    method = row['selection_method']
    table_rows.append(f'<tr data-search="{row_text}" data-reference="{str("reference" in method).lower()}"><td>{row["index"]}</td><td><a href="{filename}"><img src="{filename}" loading="lazy" alt="{esc(row["component_name"], quote=True)}"></a></td><td><strong>{esc(row["component_name"])}</strong><br><small>{esc(row["family"])}</small><br><a href="{filename}">Open downloaded image</a> · <a href="{esc(row["component_url"], quote=True)}" target="_blank" rel="noopener noreferrer">Dropbox component</a></td><td>{esc(", ".join(row["missing_roles"]))}</td><td><span class="{"reference" if "reference" in method else "primary"}">{labels[method]}</span><br><small>{w} × {h} pixels</small></td><td>{notes}</td></tr>')
page = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Unprocessed sculpture primary images</title><style>body{margin:32px;background:#f7f6f2;color:#24362c;font:15px/1.5 system-ui,sans-serif}h1{font:500 34px Georgia,serif}p{max-width:1100px}a{color:#245f4c;text-underline-offset:3px}.summary{padding:16px 20px;border:1px solid #d6dfd2;background:#ecf1e9;border-radius:8px}.controls{display:flex;gap:20px;align-items:center;margin:24px 0;flex-wrap:wrap}input[type=search]{font:inherit;padding:10px;width:380px;max-width:85vw}table{width:100%;border-collapse:collapse;background:white}th,td{padding:12px;text-align:left;vertical-align:top;border-bottom:1px solid #dce3d8}th{background:#e7eee3;position:sticky;top:0}td:nth-child(3){min-width:240px}td:last-child{max-width:430px}img{width:110px;height:105px;object-fit:contain;background:#f2f2ee}.reference{color:#97531b;font-weight:600}.primary{color:#286448}small{color:#627060}tr[hidden]{display:none}.tablewrap{overflow:auto}</style><h1>Unprocessed sculpture images</h1>'''
page += f'<p class="summary"><strong>{len(rows)} images downloaded and hash-verified</strong>, one for each component with remaining photo-folder gaps.<br>{summary["both_photo_sets_missing"]} components need both High Resolution and In Detail images; {summary["detail_only_missing"]} need In Detail images only.<br>{primary} images are catalogue primaries. {len(rows) - primary} are clearly marked existing references, including {counts["backup_component_reference"]} from backup folders.</p>'
page += '<p>The references cover components without a usable current primary selection. Where only a close-up or pattern reference exists, the notes say so. These are original downloaded files; catalogue photo selections and Dropbox contents were not changed.</p>'
page += '<div class="controls"><input id="search" type="search" placeholder="Find a component or family" aria-label="Find a component or family"><label><input id="references" type="checkbox"> Show reference substitutions only</label><span id="count"></span></div><div class="tablewrap"><table><thead><tr><th>#</th><th>Image</th><th>Component sculpture</th><th>Photo folders still needed</th><th>Downloaded image</th><th>Selection notes</th></tr></thead><tbody>' + ''.join(table_rows) + '</tbody></table></div>'
page += '<script>const search=document.getElementById("search"),references=document.getElementById("references"),rows=[...document.querySelectorAll("tbody tr")];function update(){let n=0;for(const row of rows){row.hidden=!(row.dataset.search.includes(search.value.toLowerCase())&&(!references.checked||row.dataset.reference==="true"));if(!row.hidden)n++;}document.getElementById("count").textContent=n+" component images";}search.addEventListener("input",update);references.addEventListener("change",update);update();</script></html>'
(destination / 'download-index.html').write_text(page)
(BASE / 'verification.json').write_text(json.dumps(summary, indent=2) + '\n')
print(json.dumps(summary, indent=2))
