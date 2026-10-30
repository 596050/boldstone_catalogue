"""Publishable current reports, retaining the preceding release as history."""
import csv
import hashlib
import html
import json
import re
import shutil
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote

H = Path(__file__).resolve().parent
B = H.parents[2]
OUT = B / 'outputs' / H.name
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
esc = lambda x: html.escape(str(x), quote=True)
def write(path, obj):
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n')

m = read(H / 'input-manifest.json')
src = read(m['source_report_verification']['snapshot'])
OLD = Path(src['output_directory'])
g = read(H / 'canonical-master-register.json')
edge = read(H / 'owner-design-edge.json')
projection = read(H / 'working-design-group-projection.json')
pair = [o for o in g['options'] if o['product_id'] in edge['owner_confirmed_option_ids']]
pages, csvs, images = {}, [], []
notice = '<section><strong>Current position:</strong> 188 active individual finish, size and build options;112 retained component IDs;110 working design groups after two separately confirmed Decowaves/Frozen Decowaves relationships. <a href="decowaves2-owner-design-equivalence.html">Number2 confirmation and image links</a>. Two Wall Circle primary references remain unresolved. The22 context cases, one Series case and Frozen Fish identity retain their holds.</section>'
for item in src['thumbnail_files']:
    source = Path(item['path'])
    assert sha(source) == item['sha256']
    dest = OUT / source.relative_to(OLD)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, dest)
    images.append({**item, 'path': str(dest)})
for item in src['pages']:
    source = Path(item['path'])
    assert sha(source) == item['sha256']
    text = source.read_text().replace(str(OLD), str(OUT))
    text = re.sub(r'<section><strong>Current (?:position|catalogue):</strong>.*?</section>', '', text, flags=re.S)
    text = text.replace('</h1>', '</h1>' + notice, 1)
    if source.name == 'decowaves1-owner-design-equivalence.html':
        text = text.replace('Number2 remains unanswered.', 'Number2 was separately confirmed by the owner later on24 October. Its exact answer is recorded in the linked current review.')
        text = text.replace('The112 retained component IDs form111 working groups after linking BC-DECO-1 and BC-FDW-1.', 'The number1 relationship first reduced the working groups to111. With the separately confirmed number2 pair, the112 retained component IDs now form110 working groups.')
        text = text.replace('Current_Working_Design_Groups_111.csv', 'Current_Working_Design_Groups_110.csv').replace('>111 working groups<', '>110 working groups<')
    dest = OUT / source.name
    dest.write_text(text)
    pages[dest.name] = {'path': str(dest), 'sha256': sha(dest), 'cards': text.count('<article')}
css = re.search(r'<style>(.*?)</style>', (OUT / 'index.html').read_text(), re.S).group(1)
cards = []
for option in pair:
    fields = ''.join('<tr><th>' + esc(k) + '</th><td>' + esc(v['display']) + '</td></tr>' for k, v in option['master_fields'].items())
    cards.append('<article id="' + esc(option['product_id']) + '"><h2>' + esc(option['name']) + '</h2><p><a href="' + esc(option['image_url']) + '">Selected image</a> · <a href="' + esc(option['folder_url']) + '">Containing folder</a></p><p>Owner-confirmed same relief design as the other number2 reference. Separate finish option and individual price retained.</p><table>' + fields + '</table><small>' + esc(option['product_id']) + ' · ' + esc(option['canonical_component_id']) + ' · ' + esc(option['file_id']) + ' · ' + esc(option['folder_id']) + '</small></article>')
body = '<p>The owner answered “wYes” at11:44:50 UTC and repeated it at11:46:10 UTC on24 October2026 in the session that presented this exact comparison. Both are read as one Yes to the number2 design question. The original spelling and transcript positions are preserved. No intervening question was presented.</p><p>BC-DECO-2 and BC-FDW-2 now share a working design group. The previously confirmed number1 relationship remains intact. All112 component IDs and188 current sale options remain. No measurements, material recipe, fitted fixing, physical cast count, mould count, stock or SKU configuration is inferred from this design answer.</p><nav><a href="Current_Working_Design_Groups_110.csv">110 working groups</a> · <a href="Owner_Decowaves2_Design_Equivalence_2.csv">Number2 pair</a> · <a href="decowaves1-owner-design-equivalence.html">Previously confirmed number1</a> · <a href="index.html">Current catalogue</a></nav>'
dest = OUT / 'decowaves2-owner-design-equivalence.html'
dest.write_text('<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Decowaves2 owner design relationship</title><style>' + css + '</style></head><body><main><h1>Decowaves2 owner design relationship</h1>' + notice + body + ''.join(cards) + '</main></body></html>')
pages[dest.name] = {'path': str(dest), 'sha256': sha(dest), 'cards': 2}
for item in src['csv_files']:
    source = Path(item['path'])
    assert sha(source) == item['sha256']
    if source.name == 'Current_Working_Design_Groups_111.csv':
        continue
    dest = OUT / source.name
    if source.name == 'Current_Individual_Options_188.csv':
        with source.open(encoding='utf-8-sig', newline='') as f:
            reader = csv.DictReader(f)
            headers, rows = reader.fieldnames, list(reader)
        assert len(headers) == len(set(headers))
        for row in rows:
            row['working_design_group_id'] = projection['component_id_to_working_group'].get(row['component_id'], '')
            row['owner_confirmed_design_equivalence_edge'] = next((x['edge_id'] for x in g['current_owner_design_equivalence_edges'] if row['option_id'] in x['owner_confirmed_option_ids']), '')
        with dest.open('w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            writer.writerows(rows)
    else:
        shutil.copy2(source, dest)
    csvs.append({**item, 'path': str(dest), 'sha256': sha(dest)})

def export(name, rows):
    dest = OUT / name
    with dest.open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    csvs.append({'path': str(dest), 'sha256': sha(dest), 'rows': len(rows)})

export('Current_Working_Design_Groups_110.csv', [{'working_design_group_id': x['working_design_group_id'], 'retained_component_ids': ' | '.join(x['retained_component_ids']), 'active_option_ids': ' | '.join(x['active_option_ids']), 'owner_directly_confirmed_option_ids': ' | '.join(x['owner_directly_confirmed_option_ids']), 'basis': x['grouping_basis'], 'scope': projection['scope']} for x in projection['groups']])
export('Owner_Decowaves2_Design_Equivalence_2.csv', [{'option_id': o['product_id'], 'name': o['name'], 'component_id_retained': o['canonical_component_id'], 'working_design_group_id': 'BC-DECO-2', 'edge_id': edge['edge_id'], 'image_url': o['image_url'], 'folder_url': o['folder_url'], 'file_id': o['file_id'], 'folder_id': o['folder_id'], 'owner_answer_utc': edge['owner_answer_timestamp'], 'owner_answer_verbatim': edge['owner_answer_verbatim'], 'specifications_transferred': False} for o in pair])
shutil.copy2(m['source_photo_requests']['snapshot'], OUT / 'remaining-photograph-requests.json')
count = read(m['source_count_summary']['snapshot'])
count.update(current_option_list={'path': str(OUT / 'Current_Individual_Options_188.csv'), 'sha256': sha(OUT / 'Current_Individual_Options_188.csv'), 'rows': 188}, retained_component_identity_record_count=112, grouped_working_design_identity_count=110, current_owner_design_equivalence_scope=[x['edge_id'] for x in g['current_owner_design_equivalence_edges']])
write(OUT / 'current-count-summary.json', count)

class Parser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids, self.links, self.cards = set(), [], 0
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        self.cards += tag == 'article'
        if attrs.get('id'):
            self.ids.add(attrs['id'])
        if tag in ['a', 'img']:
            self.links.append(attrs.get('href' if tag == 'a' else 'src', ''))

parsed = {}
for item in pages.values():
    path = Path(item['path']).resolve()
    parser = Parser()
    parser.feed(path.read_text())
    assert parser.cards == item['cards']
    parsed[path] = parser
for path, parser in parsed.items():
    for url in parser.links:
        assert 'BOLDSTONE_BACKUP' not in url.upper()
        if url.startswith(('https:', 'data:')):
            continue
        name, _, anchor = url.partition('#')
        target = (path.parent / unquote(name)).resolve() if name else path
        assert target.is_file(), (path.name, url)
        if anchor and target in parsed:
            assert anchor in parsed[target].ids, (path.name, url)
result = {**src, 'status': 'PASS', 'output_directory': str(OUT), 'register_sha256': sha(H / 'canonical-master-register.json'), 'audit_sha256': sha(H / 'image-coverage-current.json'), 'pages': list(pages.values()), 'csv_files': csvs, 'thumbnail_files': images, 'owner_design_equivalence_edge': edge['edge_id'], 'retained_component_id_records': 112, 'grouped_working_design_identities': 110}
write(H / 'report-verification.json', result)
print(json.dumps({'status': 'PASS', 'pages': len(pages), 'csvs': len(csvs), 'working_groups': 110}))
