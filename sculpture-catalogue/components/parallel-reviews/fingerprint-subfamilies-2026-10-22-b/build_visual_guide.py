from pathlib import Path
from html import escape
from html.parser import HTMLParser
from urllib.parse import urlparse
import base64
import collections
import hashlib
import json

ROOT = Path(__file__).resolve().parent
proposal = json.loads((ROOT / 'NAMING_PROPOSAL.json').read_text())
inventory = json.loads((ROOT / 'native-inventory.json').read_text())
rows = proposal['crosswalk']
by_id = {r['file_id']: r for r in rows}
groups = proposal['subfamilies']

def link(url, label):
    return f'<a href="{escape(url, quote=True)}" target="_blank" rel="noopener">{escape(label)}</a>'

def preview(row, main=False):
    path = Path(row['cached_preview'])
    data = base64.b64encode(path.read_bytes()).decode()
    alt = row['proposed_name'] or 'Room background without sculpture'
    return f'<img class="{"main" if main else "small"}" loading="lazy" alt="{escape(alt)}" src="data:image/jpeg;base64,{data}">'

def caption(row):
    appearance = row['appearance_label'] or 'Background'
    arrangement = row['visible_arrangement'] or 'Context only'
    role = 'Room scene' if row['role'] == 'contextual_scene' else 'Design reference'
    return (f'<p class="caption">{escape(appearance)} · {escape(arrangement)} · {role}</p>'
            f'<p class="links">{link(row["image_url"], "Dropbox image")} · {link(row["folder_url"], "Containing folder")}</p>'
            f'<p class="filename">{escape(row["filename"])}<br>{escape(row["file_id"])}</p>')

cards = []
for index, group in enumerate(groups, 1):
    rep = by_id[group['representative_file_id']]
    members = [by_id[i] for i in group['member_file_ids']]
    finishes = sorted({r['appearance_label'] for r in members})
    extras = [r for r in members if r['file_id'] != rep['file_id']]
    gallery = ''.join(f'<figure>{preview(r)}<figcaption>{caption(r)}</figcaption></figure>' for r in extras)
    extra_section = (f'<details><summary>Other images in this group ({len(extras)})</summary><div class="gallery">{gallery}</div></details>' if extras else '')
    cards.append(f'''<section class="card" id="{group['key']}">
<div class="heading"><span class="number">{index:02d}</span><h2>{escape(group['name'])}</h2></div>
<p>{escape(group['description'])}</p>
<p class="meta">{len(members)} image files · Appearance: {escape(', '.join(finishes))}</p>
<figure>{preview(rep, True)}<figcaption>{caption(rep)}</figcaption></figure>
<p class="aliases"><strong>Earlier or related labels:</strong> {escape('; '.join(group['aliases']))}</p>
{extra_section}</section>''')

background = by_id[proposal['excluded_background_file_id']]
references = [r for r in rows if r['role'] == 'component_reference_document']
reference_list = ''.join(f'<li>{escape(r["ns_path"].split("/Fingerprint/")[-1])} — {link(r["image_url"], "Open reference")}</li>' for r in references)
nav = ''.join(f'<a href="#{g["key"]}">{escape(g["name"].replace("Fingerprint ", ""))}</a>' for g in groups)
html = '''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Fingerprint — proposed sub-family names</title>
<style>
:root{color-scheme:light;--ink:#243832;--muted:#5b6c63;--line:#d8ddd2;--paper:#f5f4ed;--accent:#35685c}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:16px/1.5 system-ui,-apple-system,sans-serif}
header,main,footer{max-width:1440px;margin:auto;padding:32px}header{padding-bottom:16px}h1{font:400 clamp(2rem,4vw,3.2rem)/1.1 Georgia,serif;margin:12px 0 20px}h2{font:400 1.5rem/1.2 Georgia,serif;margin:0}
p{margin:12px 0}.eyebrow{text-transform:uppercase;font-size:.78rem;letter-spacing:.12em;color:var(--muted)}.intro{max-width:850px}.status{display:inline-block;border:1px solid var(--accent);border-radius:20px;padding:4px 12px;font-size:.8rem}
a{color:var(--accent);text-underline-offset:3px}nav{display:flex;flex-wrap:wrap;gap:9px;margin:22px 0}nav a{padding:6px 11px;border:1px solid var(--line);border-radius:4px;font-size:.85rem;text-decoration:none}
.grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:22px;align-items:start}.card{background:white;border:1px solid var(--line);border-radius:8px;padding:22px;scroll-margin-top:20px}.heading{display:flex;gap:12px;align-items:baseline}.number{color:var(--muted);font-size:.8rem}.meta,.caption,.aliases{font-size:.85rem;color:var(--muted)}figure{margin:14px 0}img{display:block;width:100%;object-fit:contain;background:#ebece7}.main{height:300px}.small{height:240px}.links{font-size:.86rem}.filename{font:11px/1.5 ui-monospace,monospace;overflow-wrap:anywhere;color:var(--muted)}details{margin-top:18px;border-top:1px solid var(--line);padding-top:14px}summary{cursor:pointer;font-size:.9rem;color:var(--accent)}.gallery figure{padding-top:10px;border-top:1px solid var(--line)}.notes{background:#e7ece4;border-radius:8px;padding:24px;margin:26px 0;max-width:1100px}.notes h2{font-size:1.35rem}.notes p,.notes li{font-size:.9rem}footer{font-size:.8rem;color:var(--muted)}.background{max-width:440px}
@media(max-width:1100px){.grid{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:700px){.grid{grid-template-columns:1fr}header,main,footer{padding:20px}.main{height:320px}}@media print{.grid{display:block}.card{break-inside:avoid;margin:20px 0}.main{height:250px}nav,details{display:none}a{color:inherit}}
</style></head><body>'''
html += f'''<header><p class="eyebrow">Boldstone · Fingerprint collection · 22 October 2026</p>
<span class="status">Proposed names</span><h1>Thirteen sub-families, named by their design.</h1>
<div class="intro"><p>These names group the visible ridge patterns across the current Fingerprint folder. White and Verdigris are finish/appearance labels. Pairs, rows and grids describe the arrangement.</p>
<p><strong>Example:</strong> Fingerprint Concentric — Left Panel — Verdigris.</p>
<p>All 68 current image files are accounted for: 67 show sculptures and one is a room background. Four HTML files contain existing component references.</p>
<p>{link(proposal['shared_folder_url'], 'Open the Fingerprint folder in Dropbox')}</p></div><nav>{nav}</nav></header>
<main><div class="grid">{''.join(cards)}</div>
<aside class="notes"><h2>How to use these names</h2><p>These are broad design groups. The source images include design studies, variations and room scenes, so this is not a count of manufactured models. Each source retains its file identity and any existing catalogue identity.</p>
<p>Concentric contains the established Left Panel and Right Panel references. Historical composition 1 and 2 remain source labels; they do not number the Left and Right members. Contextual images remain labelled as context.</p>
<p>The naming proposal and image-by-image mapping are saved alongside this guide. Dropbox names and the shared catalogue have not been changed by this naming review.</p></aside>
<details><summary>Background image and component reference documents</summary><div class="background">{preview(background)}<p>{link(background['image_url'], 'Room background image')} · {link(background['folder_url'], 'Containing folder')}</p></div><ul>{reference_list}</ul></details>
</main><footer>Current inventory: {escape(inventory['recorded_utc'])}. Every preview is the existing cached image, embedded without image editing. Open the Dropbox link for its current source file.</footer></body></html>'''

out = ROOT / 'Fingerprint_Subfamily_Names.html'
out.write_text(html)

class Inspector(HTMLParser):
    def __init__(self):
        super().__init__(); self.ids=[]; self.images=[]; self.anchors=[]
    def handle_starttag(self, tag, attrs):
        a=dict(attrs)
        if 'id' in a: self.ids.append(a['id'])
        if tag=='img': self.images.append(a)
        if tag=='a': self.anchors.append(a.get('href',''))

check=Inspector(); check.feed(out.read_text())
native_files={r['file_id'] for r in inventory['entries'] if r['object_type']=='file'}
mapped=[i for g in groups for i in g['member_file_ids']]
assert native_files==set(by_id) and len(by_id)==72
assert len(mapped)==len(set(mapped))==67
assert len(groups)==len({g['name'] for g in groups})==13
assert len(check.images)==68
assert len(check.ids)==len(set(check.ids))==13
assert all(a['alt'] for a in check.images)
assert all(h.startswith('#') or urlparse(h).hostname=='www.dropbox.com' for h in check.anchors)
metadata=json.loads((ROOT/'representative-metadata.json').read_text())
assert {m['file_id'] for m in metadata['files']}=={g['representative_file_id'] for g in groups}
for row in metadata['files']:
    source=by_id[row['file_id']]
    assert source['ns_path'].split('//',1)[1]=='BOLDSTONE MASTER'+row['path_display'].split('/BOLDSTONE MASTER',1)[1]
    assert source['size']==row['size']

receipt={
    'status':'PASS',
    'inventory_complete':inventory['has_more'] is False,
    'native_files_accounted_for':72,
    'image_previews_embedded_without_edits':68,
    'sculpture_images_tagged_once':67,
    'subfamilies':13,
    'background_images_separate':1,
    'component_reference_documents':4,
    'representative_native_metadata_checks':13,
    'names_status':'proposal',
    'dropbox_writes':0,
    'shared_master_writes':0,
    'file_hashes':{n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in ['NAMING_PROPOSAL.json','Fingerprint_Subfamily_Names.html','native-inventory.json','current-file-evidence.json','representative-metadata.json']},
    'image_counts_by_subfamily':{g['name']:len(g['member_file_ids']) for g in groups},
}
(ROOT/'VERIFICATION.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt,indent=2))
