import html
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent
manifest = json.loads((BASE / 'manifest.json').read_text())
tabs = json.loads((BASE / 'dropbox-tabs.json').read_text())
by_label = {item['label']: item for item in tabs}
candidate_path = BASE / 'candidate-folder-matches.json'
candidates = json.loads(candidate_path.read_text()) if candidate_path.exists() else {}
esc = html.escape
rows = []
for group in manifest['groups']:
    links = []
    for source in group['files']:
        output = Path(group['output_folder']) / (source['sha256'] + '.png')
        if group['status'] == 'processed_verified':
            links.append(f'<a href="{esc(output.as_uri(), quote=True)}">{esc(source["filename"])}</a>')
        else:
            links.append(esc(source['filename']))
    label = esc(group['label'])
    if group['label'] in by_label:
        label = f'<a href="{esc(by_label[group["label"]]["url"], quote=True)}">{label}</a>'
    elif group['label'] in candidates:
        label += '<br><small>Number not confirmed. Possible Dropbox matches:</small><br>'
        label += '<br>'.join(f'<a href="{esc(item["url"], quote=True)}">{esc(item["name"])}</a>' for item in candidates[group['label']])
    rows.append(f'<tr><td>{label}</td><td>{esc(group["status"])}</td><td>' + '<br>'.join(links) + '</td></tr>')
verified = sum(len(g.get('verified_outputs', [])) for g in manifest['groups'])
page = '<!doctype html><html lang="en"><meta charset="utf-8"><title>Processed sculpture images</title><style>body{font:15px/1.5 system-ui;margin:28px;color:#243a2c;background:#f8faf7}table{width:100%;border-collapse:collapse;background:white}td,th{padding:14px;vertical-align:top;text-align:left;border-bottom:1px solid #dce4d9}a{color:#226b49}th{background:#e6eee2}</style><h1>Processed sculpture images</h1>'
page += f'<p>{verified} of {sum(len(g["files"]) for g in manifest["groups"])} images verified. Component names link to their Dropbox folders; source filenames below open their processed hash-named images.</p>'
page += '<p>Processed with AIDefector in the browser, keeping PNG format and its current pixel-processing and camera-EXIF defaults. Camera metadata is a claimed stamp. The app skips frequency/CFA processing above its 6-megapixel limit. Original files are retained in the parent folder.</p>'
page += '<table><thead><tr><th>Source sculpture label / Dropbox</th><th>Status</th><th>Processed images, labelled by original filename</th></tr></thead><tbody>' + ''.join(rows) + '</tbody></table></html>'
(Path(manifest['processed_root']) / 'processing-index.html').write_text(page)
print(json.dumps({'verified_images': verified, 'index': str(Path(manifest['processed_root']) / 'processing-index.html')}))
